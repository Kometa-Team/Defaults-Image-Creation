"""M4 synthetic/small logo fixtures only; no existing poster generation."""

from dataclasses import replace
from io import BytesIO
import base64
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import zlib

from PIL import Image, ImageDraw
import pytest

from create_defaults.bulk.common import BulkError, Conflict, canonical, fingerprint
from create_defaults.bulk.config import ROOT
from create_defaults.bulk.contracts import Contract, ContractApproval, Identity, TrustedDecision, PreviewManifest, SubmitterConfirmation, ExceptionDecision
from create_defaults.bulk.contracts.adoption.models import encoded_json, read_canonical
from create_defaults.bulk.contracts.logos.assets import encode_png, inspect_png, MAX_PIXELS, MAX_EDGE
from create_defaults.bulk.contracts.logos.calibration import HERE, CORPUS_SHA256, evaluate, load_corpus
from create_defaults.bulk.contracts.logos.comparison import compare
from create_defaults.bulk.contracts.logos.evidence import Evidence
from create_defaults.bulk.contracts.logos.historical import accepted_uses, preserve_existing
from create_defaults.bulk.contracts.logos.storage import LogoArchive, status
from create_defaults.bulk.contracts.logos.wash import white_wash, SOURCE_SHA256
from create_defaults.bulk.contracts.logos.workflow import (
    Selection, SubmitterAttribution, Prepared, prepare, verify, confirm_record, decision_record,
)
from create_defaults.bulk.contracts.playlist.validation import CONTRACT_SHA256, REGISTRY_SHA256, M2_SHA256, PlaylistBoundary
from create_defaults.bulk.tests.test_contract_foundations import package, overlay_package, registry_fixture


def logo(mode="RGBA",opaque=False):
    image=Image.new("RGBA",(64,48),(0,0,0,255 if opaque else 0))
    d=ImageDraw.Draw(image)
    d.rectangle((8,8,24,38),fill=(210,30,60,255))
    d.rectangle((13,14,18,23),fill=(0,0,0,255 if opaque else 0))
    d.polygon([(35,38),(42,7),(54,38)],fill=(210,30,60,255))
    if mode=="P":
        indexed=Image.new("P",image.size,0)
        indexed.putpalette([0,0,0,210,30,60]+[0]*762)
        indexed.putdata([1 if a else 0 for a in image.getchannel("A").tobytes()]);indexed.info["transparency"]=0
        return indexed
    return image.convert(mode)


@pytest.fixture
def setup_review(tmp_path):
    root=tmp_path/"candidate-sources";root.mkdir()
    raw=encode_png(logo());(root/"Brand.PNG").write_bytes(raw)
    source={"path":"Brand.PNG","sha256":hashlib.sha256(raw).hexdigest()}
    contract=Contract.from_dict(overlay_package())
    selected=Selection.fixture(contract,"color")
    item=Identity.from_dict({"schema_version":1,"kind":"item-identity","id":"overlay.synthetic-brand","category":"Overlays",
        "display_name":"Synthetic Brand","rendered_caption":"","source":source,"local_path":"private/Brand.PNG","public_path":None,"semantic_member":None})
    def make(selection=selected,item_value=item,**kwargs):
        return prepare(selection,source_root=root,item=item_value,submitter="synthetic-contributor",sources={"master":source,"white":None},
            reason="Synthetic M4 test, no real human approval",request_id="synthetic.request",**kwargs)
    return root,source,selected,item,make


@pytest.mark.parametrize("mode",["RGBA","P","LA"])
def test_png_modes_and_original_bytes(mode):
    raw=encode_png(logo(mode));asset=inspect_png(raw)
    assert asset.encoded==raw and asset.report()["mode"]==mode
    assert asset.report()["clear_pixels"]>0
    assert not asset.report()["default_transparency_blockers"]
    assert asset.image().mode=="RGBA"


@pytest.mark.parametrize("kind",["jpeg","gif","truncated","bad_crc","trailing","transparent","bad_signature","animated"])
def test_disguised_corrupt_and_empty_sources_fail(kind):
    image=logo();raw=encode_png(image)
    if kind in {"jpeg","gif"}:
        out=BytesIO();image.convert("RGB").save(out,format=kind);raw=out.getvalue()
    elif kind=="truncated":raw=raw[:-9]
    elif kind=="bad_crc":raw=raw[:35]+bytes([raw[35]^1])+raw[36:]
    elif kind=="trailing":raw+=b"malicious trailing bytes"
    elif kind=="transparent":raw=encode_png(Image.new("RGBA",(32,32)))
    elif kind=="bad_signature":raw=b"notpng"+raw
    else:
        out=BytesIO();image.save(out,format="PNG",save_all=True,append_images=[Image.new("RGBA",image.size,"white")]);raw=out.getvalue()
    with pytest.raises(BulkError):inspect_png(raw)


def test_resource_limits_are_checked_before_decoding(monkeypatch):
    raw=bytearray(encode_png(logo()))
    raw[16:24]=struct.pack(">II",MAX_EDGE+1,MAX_EDGE+1)
    raw[29:33]=struct.pack(">I",zlib.crc32(raw[12:29])&0xffffffff)
    monkeypatch.setattr(Image,"open",lambda *a,**k:pytest.fail("Oversized image reached decoding"))
    with pytest.raises(BulkError,match="safety budget"):inspect_png(bytes(raw))


@pytest.mark.parametrize("change",["critical_chunk","sixteen_bit"])
def test_unsupported_png_representation_is_not_silently_converted(change):
    raw=encode_png(logo())
    if change=="critical_chunk":
        kind=b"XXXX";chunk=struct.pack(">I",0)+kind+struct.pack(">I",zlib.crc32(kind)&0xffffffff)
        raw=raw[:33]+chunk+raw[33:]
    else:
        raw=bytearray(raw);raw[24]=16;raw[29:33]=struct.pack(">I",zlib.crc32(raw[12:29])&0xffffffff);raw=bytes(raw)
    with pytest.raises(BulkError):inspect_png(raw)


def test_alpha_alone_and_single_clear_pixel_do_not_prove_transparency():
    for value in (255,128):
        raw=encode_png(Image.new("RGBA",(40,40),(120,10,30,value)))
        assert inspect_png(raw).report()["default_transparency_blockers"]
    image=Image.new("RGBA",(40,40),(10,20,30,255));image.putpixel((0,0),(0,0,0,0))
    report=inspect_png(encode_png(image)).report()
    assert report["default_transparency_blockers"]
    assert "alpha_channel_does_not_prove_clean_background" in report["diagnostics"]


def test_edge_contact_clipping_and_halo_are_descriptive_not_ai_claims():
    image=logo();ImageDraw.Draw(image).line((0,0,20,20),fill=(255,255,255,128),width=3)
    report=inspect_png(encode_png(image)).report()
    assert any(report["edge_visible_pixels_top_bottom_left_right"])
    assert report["halo_observations"]["soft_edge_samples"]>0
    assert "not_automatically_proven" in report["quality"]


def test_exact_existing_wash_and_immutable_original(monkeypatch):
    from create_defaults import create_poster
    monkeypatch.setattr(create_poster,"render_poster",lambda *a,**k:pytest.fail("Full poster rendering must not run"))
    source=logo();source.putpixel((7,7),(0,80,255,123));raw=source.tobytes()
    result,provenance=white_wash(source)
    assert source.tobytes()==raw
    assert result.getchannel("A").tobytes()==source.getchannel("A").tobytes()
    assert result.convert("RGB").getextrema()==((255,255),(255,255),(255,255))
    assert provenance["source_sha256"]==SOURCE_SHA256
    assert provenance["parameters"]["preserve_original_alpha"]


def test_wash_source_drift_fails_closed(tmp_path,monkeypatch):
    from create_defaults.bulk.contracts.logos import wash
    source=tmp_path/"renderer.py";source.write_text("# changed",encoding="utf-8")
    monkeypatch.setattr(wash,"SOURCE",source)
    with pytest.raises(BulkError):white_wash(logo())


def test_comparison_resolution_padding_and_antialias_never_auto_match():
    corpus=load_corpus()
    for pair in [p for p in corpus["pairs"] if p["family"]=="family-0" and p["label"]=="equivalent"]:
        assets=[inspect_png(base64.b64decode(corpus["png_base64"][pair[k]])) for k in ("master_sha256","white_sha256")]
        report=compare(*assets,grid=64)
        assert report["outcome"]=="REVIEW REQUIRED"
        assert not report["automatic_match_enabled"]
        assert report["settings"]["alignment"]=="visible-bounds-translation-uniform-scale-only"


@pytest.mark.parametrize("case",["missing_letter","cutout_removed"])
def test_binary_topological_discrepancy_blocks_and_exposes_measurements(case):
    corpus=load_corpus();pair=next(p for p in corpus["pairs"] if p["family"]=="family-0" and p["case"]==case)
    assets=[inspect_png(base64.b64decode(corpus["png_base64"][pair[k]])) for k in ("master_sha256","white_sha256")]
    report=compare(*assets,grid=64)
    assert report["outcome"]=="MISMATCH"
    assert report["levels"][0]["master_components"]
    assert report["soft_union_sum"]>0
    assert not report["publication_authorized"]


def test_corpus_is_sealed_family_disjoint_and_evaluation_reproducible():
    report=evaluate()
    from ci.dependency_maintenance import current_calibration_expectation
    expected=current_calibration_expectation(json.loads((HERE/"calibration-v1.json").read_bytes()))
    assert canonical(report)==canonical(expected)
    assert report["corpus_sha256"]==CORPUS_SHA256 and report["family_disjoint"]
    for split in report["summaries"].values():
        assert split["false_matches"]==0 and split["false_mismatches"]==0
        assert split["automatic_matches"]==0 and split["positive_manual_reviews"]==12
    assert not report["approved_policy"]


def test_complete_overlay_sizes_preserve_source_and_context(setup_review):
    root,source,selection,item,make=setup_review
    prepared=make();spec,request,preview=verify(prepared,selection,root)
    members=preview.to_dict()["members"]
    assert {m["id"] for m in members}=={"color.standard","color.bigger"}
    assert all(m["treatment"]=="source" for m in members)
    assert spec["transform"]["id"]=="existing-source-preserving-overlay"
    assert spec["preview_type"]=="complete_overlay" and spec["fixture_only"]
    assert spec["sources"]["master"]["path"]=="Brand.PNG"


def test_white_branch_is_a_separate_preserved_source_not_an_invented_group(setup_review):
    root,source,selection,item,make=setup_review
    value=selection.contract.to_dict();value["variants"][0]["id"]="white";value["variants"][0]["design"]["source_branch"]="white-source"
    selected=Selection.fixture(Contract.from_dict(value),"white")
    prepared=make(selection=selected);spec,_,preview=verify(prepared,selected,root)
    assert {m["id"] for m in preview.to_dict()["members"]}=={"white.standard","white.bigger"}
    assert all(m["treatment"]=="source" for m in spec["required_outputs"])


def poster_setup(setup_review,category="Playlist",treatment="WHITE_ONLY",white=False):
    root,source,_,item,_=setup_review
    value=package();value["category"]=category;value["variants"][0]["design"]["logo"]["treatment"]=treatment
    selected=Selection.fixture(Contract.from_dict(value),"example")
    data=item.to_dict();data.update(category=category,id=category.lower()+".synthetic",rendered_caption="TIMELINE ORDER")
    identity=Identity.from_dict(data)
    references={"master":source,"white":None}
    if white:
        washed,_=white_wash(logo());raw=encode_png(washed);(root/"White.png").write_bytes(raw)
        references["white"]={"path":"White.png","sha256":hashlib.sha256(raw).hexdigest()}
    return root,selected,identity,references


def test_poster_exception_has_default_and_requested_but_no_fake_complete_composition(setup_review,tmp_path):
    root,selected,item,sources=poster_setup(setup_review)
    prepared=prepare(selected,source_root=root,item=item,submitter="synthetic-contributor",sources=sources,
        exception_types=["source_preserving"],background="#123456",reason="Synthetic source-colour exception",request_id="poster.request")
    spec,request,preview=verify(prepared,selected,root)
    p=preview.to_dict()
    assert p["default"]["artifact_sha256"]!=p["requested"]["artifact_sha256"]
    assert spec["preview_type"]=="logo_only"
    archive=LogoArchive(tmp_path/"state");start=archive.start("review",prepared,expected_revision=0,selection=selected,source_root=root)
    submitter=SubmitterAttribution("synthetic-contributor","a"*64);confirmation=confirm_record(prepared,submitter,"approved")
    confirmed=archive.submit("review",confirmation,expected_sha256=start.sha256,expected_revision=1,selection=selected,source_root=root,attribution=submitter)
    maintainer=TrustedDecision("bullmoose20","b"*64);decision=decision_record(prepared,confirmation,maintainer,"approved")
    with pytest.raises(BulkError,match="Logo-only"):
        archive.maintain("review",decision,expected_sha256=confirmed.sha256,expected_revision=2,selection=selected,source_root=root,submitter_attribution=submitter,attribution=maintainer)


@pytest.mark.parametrize("separate",[False,True])
def test_both_required_cannot_accept_half_pair_or_mutated_receipt(setup_review,separate):
    root,selected,item,sources=poster_setup(setup_review,"Chart","BOTH_REQUIRED",white=separate)
    prepared=prepare(selected,source_root=root,item=item,submitter="s",sources=sources,reason="Synthetic required pair",request_id="pair.request")
    spec,_,preview=verify(prepared,selected,root)
    assert {m["treatment"] for m in preview.to_dict()["members"]}=={"white","source"}
    payload=prepared.bundle.payload();p=preview.to_dict();p["members"]=p["members"][:1]
    payload["preview_json"]=PreviewManifest.from_dict(p).encoded.decode()
    tampered=Prepared(Evidence.make("logo-review-bundle",payload),prepared.artifacts)
    with pytest.raises(BulkError):verify(tampered,selected,root)


def approve_overlay(setup_review,tmp_path,*,opaque=False,exception=False):
    root,source,selection,item,make=setup_review
    if opaque:
        raw=encode_png(logo(opaque=True));(root/source["path"]).write_bytes(raw)
        source["sha256"]=hashlib.sha256(raw).hexdigest();data=item.to_dict();data["source"]=source;item=Identity.from_dict(data)
    prepared=prepare(selection,source_root=root,item=item,submitter="synthetic-contributor",sources={"master":source,"white":None},
                     exception_types=["intentional_background"] if exception else [],reason="Synthetic test review, not real approval",request_id="request.one")
    archive=LogoArchive(tmp_path/"isolated");start=archive.start("review",prepared,expected_revision=0,selection=selection,source_root=root)
    submitter=SubmitterAttribution("synthetic-contributor","a"*64);confirmation=confirm_record(prepared,submitter,"approved")
    confirmed=archive.submit("review",confirmation,expected_sha256=start.sha256,expected_revision=1,selection=selection,source_root=root,attribution=submitter)
    maintainer=TrustedDecision("bullmoose20","b"*64);decision=decision_record(prepared,confirmation,maintainer,"approved")
    return archive,prepared,start,confirmed,submitter,confirmation,maintainer,decision,root,selection


@pytest.mark.parametrize("exception",[False,True])
def test_opaque_pending_and_exact_approved_transparency_exception(setup_review,tmp_path,exception):
    archive,prepared,start,confirmed,submitter,confirmation,maintainer,decision,root,selection=approve_overlay(setup_review,tmp_path,opaque=True,exception=exception)
    assert read_canonical(prepared.bundle.payload()["preview_json"])["default"]["validation"]=="blocked"
    args=dict(expected_sha256=confirmed.sha256,expected_revision=2,selection=selection,source_root=root,submitter_attribution=submitter,attribution=maintainer)
    if not exception:
        with pytest.raises(BulkError,match="transparency exception"):archive.maintain("review",decision,**args)
    else:
        approved=archive.maintain("review",decision,**args)
        assert status(approved,prepared)["transparent_exception_accepted"]
        assert not status(approved,prepared)["publication_staging_authorized"]
        assert read_canonical(prepared.bundle.payload()["preview_json"])["default"]["validation"]=="blocked"


def test_two_stage_restart_and_no_authority_from_stored_reviewer_strings(setup_review,tmp_path):
    archive,prepared,start,confirmed,submitter,confirmation,maintainer,decision,root,selection=approve_overlay(setup_review,tmp_path)
    approved=archive.maintain("review",decision,expected_sha256=confirmed.sha256,expected_revision=2,selection=selection,source_root=root,submitter_attribution=submitter,attribution=maintainer)
    reopened=LogoArchive(archive.contracts.root)
    args=dict(expected_sha256=approved.sha256,selection=selection,source_root=root)
    for maps in ({},{"trusted_submitters":{confirmation.sha256:submitter}},
                 {"trusted_submitters":{confirmation.sha256:submitter},"trusted_maintainers":{decision.sha256:{"actor":"bullmoose20"}}}):
        with pytest.raises(BulkError):reopened.load("review",**args,**maps)
    snapshot,review=reopened.load("review",**args,trusted_submitters={confirmation.sha256:submitter},trusted_maintainers={decision.sha256:maintainer})
    assert snapshot==approved and review==prepared
    result=status(snapshot,review)
    assert result["maintainer_logo_design_approval"]
    assert result["contract_compatibility"]=="fixture_only"
    assert not result["operational_addition_eligible"] and not result["merge_authorized"]


@pytest.mark.parametrize("attack",["no_confirmation","forged_actor","self_approval","wrong_source","wrong_category","wrong_membership","stale_revision","wrong_contract"])
def test_forged_or_replayed_approval_fails(setup_review,tmp_path,attack):
    archive,prepared,start,confirmed,submitter,confirmation,maintainer,decision,root,selection=approve_overlay(setup_review,tmp_path)
    args=dict(expected_sha256=confirmed.sha256,expected_revision=2,selection=selection,source_root=root,submitter_attribution=submitter,attribution=maintainer)
    if attack=="no_confirmation":args.update(expected_sha256=start.sha256,expected_revision=1)
    elif attack=="forged_actor":args["attribution"]={"actor":"bullmoose20","evidence_sha256":"b"*64}
    elif attack=="self_approval":
        # A separately allowlisted maintainer still cannot impersonate the bound
        # contributor. Self-role exceptions are not enabled by this foundation.
        value=decision.to_dict();value["provenance"]["actor"]="synthetic-contributor";decision=ExceptionDecision.from_dict(value)
    elif attack=="wrong_source":
        value=decision.to_dict();value["context"]["source"]["sha256"]="0"*64;decision=ExceptionDecision.from_dict(value)
    elif attack=="wrong_category":
        value=decision.to_dict();value["context"]["package"]["category"]="Genre";decision=ExceptionDecision.from_dict(value)
    elif attack=="wrong_membership":
        value=decision.to_dict();value["membership_sha256"]="0"*64;decision=ExceptionDecision.from_dict(value)
    elif attack=="wrong_contract":
        value=decision.to_dict();value["context"]["package"]["sha256"]="0"*64;decision=ExceptionDecision.from_dict(value)
    else:args["expected_revision"]=1
    with pytest.raises(BulkError):archive.maintain("review",decision,**args)


@pytest.mark.parametrize("change",["source","artifact","receipt","runtime","context"])
def test_material_mutations_invalidate_owned_preview_evidence(setup_review,change):
    root,source,selection,item,make=setup_review;prepared=make()
    if change=="source":(root/source["path"]).write_bytes(encode_png(logo(opaque=True)))
    elif change=="artifact":
        artifacts=list(prepared.artifacts);h,raw=artifacts[-1];artifacts[-1]=(h,raw[:-1]+b"x");prepared=replace(prepared,artifacts=tuple(artifacts))
    else:
        payload=prepared.bundle.payload()
        if change=="receipt":
            r=read_canonical(payload["receipts_json"]);first=next(iter(r));v=Evidence.from_dict(r[first]).payload();v["source_sha256"]="0"*64;r[first]=Evidence.make("isolated-logo-preview-receipt",v).to_dict();payload["receipts_json"]=encoded_json(r)
        else:
            spec=read_canonical(payload["spec_json"])
            if change=="runtime":spec["runtime"]["Pillow"]="forged"
            else:spec["background"]="#123456"
            payload["spec_json"]=encoded_json(spec)
        prepared=replace(prepared,bundle=Evidence.make("logo-review-bundle",payload))
    with pytest.raises(BulkError):verify(prepared,selection,root)


@pytest.mark.parametrize("decision,withdraw",[("rejected",False),("rejected",True)])
def test_rejected_and_withdrawn_requests_never_reach_maintainer_approval(setup_review,tmp_path,decision,withdraw):
    root,_,selection,_,make=setup_review;prepared=make();archive=LogoArchive(tmp_path/"isolated")
    start=archive.start("review",prepared,expected_revision=0,selection=selection,source_root=root)
    actor=SubmitterAttribution("synthetic-contributor","a"*64);record=confirm_record(prepared,actor,decision)
    snapshot=archive.submit("review",record,expected_sha256=start.sha256,expected_revision=1,selection=selection,source_root=root,attribution=actor,withdraw=withdraw)
    assert snapshot.payload()["phase"]==("WITHDRAWN" if withdraw else "SUBMITTER_REJECTED")
    assert not status(snapshot,prepared)["publication_staging_authorized"]


def test_interrupted_writes_idempotent_restart_and_corruption_fail_closed(setup_review,tmp_path,monkeypatch):
    root,_,selection,_,make=setup_review;prepared=make();archive=LogoArchive(tmp_path/"isolated")
    original=archive.contracts._write_blob;calls=[]
    def interrupted(document):
        calls.append(document.sha256)
        if len(calls)==2:raise OSError("simulated interrupted blob write")
        return original(document)
    monkeypatch.setattr(archive.contracts,"_write_blob",interrupted)
    with pytest.raises(OSError):archive.start("review",prepared,expected_revision=0,selection=selection,source_root=root)
    assert archive._latest("review") is None
    monkeypatch.setattr(archive.contracts,"_write_blob",original)
    snapshot=archive.start("review",prepared,expected_revision=0,selection=selection,source_root=root)
    assert archive.start("review",prepared,expected_revision=0,selection=selection,source_root=root)==snapshot
    with archive.contracts._store.connection() as db:
        assert db.execute("SELECT count(*) FROM contract_logo_revisions").fetchone()[0]==1
    checksum=prepared.artifacts[0][0];archive._artifact(checksum).write_bytes(b"corrupt")
    with pytest.raises(BulkError):archive.start("review",prepared,expected_revision=0,selection=selection,source_root=root)


def test_all_17_historical_alpha_assets_have_no_new_diagnostics_or_regeneration(monkeypatch):
    monkeypatch.setattr(Image,"open",lambda *a,**k:pytest.fail("Historical assets must not enter new PNG diagnostics"))
    uses=accepted_uses();assert len({p for _,p,_ in uses})==17
    for item,path,checksum in uses:
        report=preserve_existing(item_id=item,source={"path":path,"sha256":checksum},source_root=ROOT)
        assert report["diagnostics"]==[] and not report["new_approval_required"] and not report["regeneration_required"]
    item,path,checksum=uses[0]
    with pytest.raises(BulkError):preserve_existing(item_id=item,source={"path":path,"sha256":"0"*64},source_root=ROOT)
    with pytest.raises(BulkError):preserve_existing(item_id="new.use",source={"path":path,"sha256":checksum},source_root=ROOT)


def test_operational_selection_requires_real_external_m1_contract_approval():
    registry,contract,decision,objects,trust=registry_fixture()
    args=dict(registry_sha256=registry.sha256,read_object=objects.__getitem__,category="Playlist",kind="poster",version="1.0.0",contract_sha256=contract.sha256,variant="example")
    with pytest.raises(BulkError):Selection.approved(registry.encoded,trusted_decisions={},**args)
    selected=Selection.approved(registry.encoded,trusted_decisions=trust,**args)
    assert not selected.fixture_only
    with pytest.raises(BulkError):Selection.approved(registry.encoded,trusted_decisions=trust,**dict(args,registry_sha256="0"*64))


def test_merged_playlist_is_still_unapproved_operationally():
    boundary=PlaylistBoundary.load(contract_sha256=CONTRACT_SHA256,registry_sha256=REGISTRY_SHA256,adoption_sha256=M2_SHA256)
    with pytest.raises(BulkError):
        Selection.approved(boundary.registry.encoded,registry_sha256=REGISTRY_SHA256,read_object=lambda _:b"{}",trusted_decisions={},
            category="Playlist",kind="poster",version="1.0.0",contract_sha256=CONTRACT_SHA256,variant="timeline-order")


def test_no_m4_record_is_a_publication_receipt(setup_review,tmp_path):
    from create_defaults.bulk.library_sources import sealed
    from create_defaults.bulk.operator_publication import authorize
    root,_,selection,_,make=setup_review;prepared=make();archive=LogoArchive(tmp_path/"state")
    snapshot=archive.start("review",prepared,expected_revision=0,selection=selection,source_root=root)
    manifest=sealed({"kind":"proposed-operator-membership","members":[{}],"policy_sha256":fingerprint({}),"baseline":{}})
    for document in (prepared.bundle,snapshot):
        with pytest.raises(BulkError):authorize(manifest,{},sealed(document.to_dict()))


def test_complete_two_stage_decisions_are_idempotent_and_logo_approval_is_not_publication(setup_review,tmp_path):
    archive,prepared,start,confirmed,submitter,confirmation,maintainer,decision,root,selection=approve_overlay(setup_review,tmp_path)
    assert archive.submit("review",confirmation,expected_sha256=start.sha256,expected_revision=1,selection=selection,source_root=root,attribution=submitter)==confirmed
    args=dict(expected_sha256=confirmed.sha256,expected_revision=2,selection=selection,source_root=root,submitter_attribution=submitter,attribution=maintainer)
    approved=archive.maintain("review",decision,**args)
    assert archive.maintain("review",decision,**args)==approved
    with archive.contracts._store.connection() as db:
        assert db.execute("SELECT count(*) FROM contract_logo_revisions").fetchone()[0]==3
    from create_defaults.bulk.library_sources import sealed
    from create_defaults.bulk.operator_publication import authorize
    manifest=sealed({"kind":"proposed-operator-membership","members":[{}],"policy_sha256":fingerprint({}),"baseline":{}})
    for document in (confirmation,decision):
        with pytest.raises(BulkError):authorize(manifest,{},sealed(document.to_dict()))


def test_actually_allowlisted_submitter_cannot_self_approve_as_maintainer(setup_review,tmp_path):
    root,source,selection,item,_=setup_review
    review=prepare(selection,source_root=root,item=item,submitter="bullmoose20",sources={"master":source,"white":None},reason="Synthetic same-person test",request_id="request.self")
    archive=LogoArchive(tmp_path/"state");start=archive.start("review",review,expected_revision=0,selection=selection,source_root=root)
    submitter=SubmitterAttribution("bullmoose20","a"*64);confirmation=confirm_record(review,submitter,"approved")
    confirmed=archive.submit("review",confirmation,expected_sha256=start.sha256,expected_revision=1,selection=selection,source_root=root,attribution=submitter)
    maintainer=TrustedDecision("bullmoose20","b"*64);decision=decision_record(review,confirmation,maintainer,"approved")
    with pytest.raises(BulkError):archive.maintain("review",decision,expected_sha256=confirmed.sha256,expected_revision=2,selection=selection,source_root=root,submitter_attribution=submitter,attribution=maintainer)


def test_maintainer_can_reject_without_promoting_policy_blocked_sources(setup_review,tmp_path):
    archive,prepared,start,confirmed,submitter,confirmation,maintainer,_,root,selection=approve_overlay(setup_review,tmp_path,opaque=True)
    decision=decision_record(prepared,confirmation,maintainer,"rejected")
    rejected=archive.maintain("review",decision,expected_sha256=confirmed.sha256,expected_revision=2,selection=selection,source_root=root,submitter_attribution=submitter,attribution=maintainer)
    assert rejected.payload()["phase"]=="MAINTAINER_REJECTED"
    assert not status(rejected,prepared)["transparent_exception_accepted"]


def test_rgb_change_stales_approval_even_when_derived_white_bytes_are_identical(setup_review):
    root,source,selection,item,make=setup_review;prepared=make()
    original=inspect_png((root/source["path"]).read_bytes());a,_=white_wash(original.image())
    changed=original.image();rgb=Image.new("RGBA",changed.size,(10,240,30,0));rgb.putalpha(changed.getchannel("A"))
    b,_=white_wash(rgb);assert encode_png(a)==encode_png(b)
    (root/source["path"]).write_bytes(encode_png(rgb))
    with pytest.raises(BulkError):verify(prepared,selection,root)


def test_fully_resealed_fake_preview_still_fails_owned_task_reproduction(setup_review):
    root,_,selection,_,make=setup_review;prepared=make();payload=prepared.bundle.payload()
    receipts=read_canonical(payload["receipts_json"]);p=read_canonical(payload["preview_json"])
    blobs=dict(prepared.artifacts)
    original=next(iter(receipts));record=Evidence.from_dict(receipts.pop(original));r=record.payload()
    image=inspect_png(blobs[r["artifact_sha256"]]).image();image.putpixel((0,0),(100,50,10,255))
    raw=encode_png(image);h=hashlib.sha256(raw).hexdigest();blobs[h]=raw
    r.update(artifact_sha256=h,bytes=len(raw));new=Evidence.make("isolated-logo-preview-receipt",r);receipts[new.sha256]=new.to_dict()
    for member in p["members"]+[p["default"],p["requested"]]:
        if member["worker_receipt_sha256"]==original:
            member["worker_receipt_sha256"]=new.sha256;member["artifact_sha256"]=h
    payload["receipts_json"]=encoded_json(receipts);payload["preview_json"]=PreviewManifest.from_dict(p).encoded.decode()
    forged=Prepared(Evidence.make("logo-review-bundle",payload),tuple(sorted(blobs.items())))
    with pytest.raises(BulkError):verify(forged,selection,root)


def test_sqlite_transaction_failure_rolls_back_session_and_event(setup_review,tmp_path,monkeypatch):
    root,_,selection,_,make=setup_review;prepared=make();archive=LogoArchive(tmp_path/"state")
    original=archive.contracts._store.event
    def interrupted(*args,**kwargs):raise OSError("simulated transaction interruption")
    monkeypatch.setattr(archive.contracts._store,"event",interrupted)
    with pytest.raises(OSError):archive.start("review",prepared,expected_revision=0,selection=selection,source_root=root)
    assert archive._latest("review") is None
    monkeypatch.setattr(archive.contracts._store,"event",original)
    assert archive.start("review",prepared,expected_revision=0,selection=selection,source_root=root).payload()["revision"]==1


def test_material_revision_resets_decisions_without_changing_an_unrelated_review(setup_review,tmp_path):
    root,source,selection,item,make=setup_review;archive=LogoArchive(tmp_path/"state");prepared=make()
    first=archive.start("review",prepared,expected_revision=0,selection=selection,source_root=root)
    raw=(root/source["path"]).read_bytes();(root/"Unrelated.png").write_bytes(raw)
    second_source={"path":"Unrelated.png","sha256":source["sha256"]};data=item.to_dict();data.update(id="overlay.unrelated",source=second_source)
    unrelated=prepare(selection,source_root=root,item=Identity.from_dict(data),submitter="other",sources={"master":second_source,"white":None},reason="Unrelated fixture",request_id="request.unrelated")
    other=archive.start("other",unrelated,expected_revision=0,selection=selection,source_root=root)
    raw=encode_png(logo(opaque=True));(root/source["path"]).write_bytes(raw);new_source=dict(source,sha256=hashlib.sha256(raw).hexdigest());data=item.to_dict();data["source"]=new_source
    revised=prepare(selection,source_root=root,item=Identity.from_dict(data),submitter="synthetic-contributor",sources={"master":new_source,"white":None},exception_types=["intentional_background"],reason="Changed bytes need new review",request_id="synthetic.request",request_revision=2)
    current=archive.start("review",revised,expected_revision=1,selection=selection,source_root=root)
    assert current.payload()["phase"]=="PREVIEWS_READY" and current.payload()["confirmation_sha256"] is None
    assert archive.load("other",expected_sha256=other.sha256,selection=selection,source_root=root)[0]==other
    with pytest.raises(BulkError):archive.load("review",expected_sha256=first.sha256,selection=selection,source_root=root)


@pytest.mark.parametrize("change",["size","wash","nested","contract","expiry"])
def test_required_outputs_and_nested_context_cannot_be_overridden(setup_review,change):
    root,_,selection,_,make=setup_review;prepared=make();payload=prepared.bundle.payload();spec=read_canonical(payload["spec_json"])
    if change=="size":spec["required_outputs"][0]["box"]["width"]=999
    elif change=="wash":spec["required_outputs"][0]["treatment"]="white"
    elif change=="nested":spec["sources"]["master"]["approved"]=True
    elif change=="contract":spec["package"]["version"]="2.0.0"
    else:spec["expires_at"]="2000-01-01T00:00:00Z"
    payload["spec_json"]=encoded_json(spec);forged=replace(prepared,bundle=Evidence.make("logo-review-bundle",payload))
    with pytest.raises(BulkError):verify(forged,selection,root)


@pytest.mark.parametrize("target_kind",["directory","png","report"])
def test_gallery_writes_reject_links_and_leave_targets_unchanged(tmp_path,target_kind):
    from create_defaults.bulk.contracts.logos.calibration import gallery
    root=tmp_path/"gallery";root.mkdir();outside=tmp_path/"unrelated";outside.mkdir()
    sentinel=outside/"original.txt";sentinel.write_bytes(b"keep unrelated files unchanged")
    corpus=load_corpus();checksum,encoded=next(iter(corpus["png_base64"].items()))
    target=outside/(checksum+".png" if target_kind=="png" else "review.html")
    target.write_bytes(base64.b64decode(encoded) if target_kind=="png" else b"existing report")
    link=tmp_path/"linked-gallery" if target_kind=="directory" else root/(checksum+".png" if target_kind=="png" else "review.html")
    try:os.symlink(outside if target_kind=="directory" else target,link,target_is_directory=target_kind=="directory")
    except OSError as error:pytest.skip("OS account cannot create test symlink: "+str(error))
    before=target.read_bytes()
    with pytest.raises(BulkError):gallery(link if target_kind=="directory" else root,{"measurements":[]})
    assert target.read_bytes()==before and sentinel.read_bytes()==b"keep unrelated files unchanged"


@pytest.mark.skipif(os.name!="nt",reason="Windows junction integration test")
def test_gallery_rejects_windows_junction_without_touching_its_target(tmp_path):
    from create_defaults.bulk.contracts.logos.calibration import gallery
    target=tmp_path/"unrelated";target.mkdir();sentinel=target/"keep.txt";sentinel.write_bytes(b"unchanged")
    link=tmp_path/"gallery-junction"
    result=subprocess.run(["cmd","/c","mklink","/J",str(link),str(target)],capture_output=True)
    if result.returncode:pytest.skip("Account/filesystem cannot create test junction")
    try:
        with pytest.raises(BulkError):gallery(link,{"measurements":[]})
        assert list(target.iterdir())==[sentinel] and sentinel.read_bytes()==b"unchanged"
    finally:os.rmdir(link)
