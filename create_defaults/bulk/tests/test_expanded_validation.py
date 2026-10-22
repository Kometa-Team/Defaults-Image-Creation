"""M5 adversarial coverage; independent impact oracle, no historical rendering."""

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
from time import perf_counter

import pytest
import yaml

from create_defaults.bulk.common import BulkError, canonical, fingerprint, path_key
from create_defaults.bulk.config import ROOT
from create_defaults.bulk.contracts.models import ContractApproval
from create_defaults.bulk.contracts.registry import TrustedDecision, package_reference
from create_defaults.bulk.contracts.expanded.graph import Snapshot, node_id, compare
from create_defaults.bulk.contracts.expanded.resolution import Resolution, resolve, contribution, plan
from create_defaults.bulk.contracts.expanded.validation import (Authority, boundary, validate_existing,
    validate_candidate, require_current)
from create_defaults.bulk.contracts.expanded.__main__ import main, write_report
from create_defaults.bulk.contracts.adoption.models import read_canonical


H = "a"*64


def graph_fixture():
    """Oracle: asset A -> P -> child; B -> Q; font -> P,Q; overlays independent."""
    nodes, outputs = {}, {}
    def put(kind,identity,deps=()):
        key = node_id(kind,identity)
        nodes[key] = {"kind":kind,"identity":identity,"sha256":fingerprint(identity),"dependencies":list(deps)}
        return key
    a,b,font,overlay = [put("asset",p) for p in ("logos/A.png","logos/B.png","fonts/Font.ttf","overlays/Logo.png")]
    p = put("output","playlist.p",[a,font])
    q = put("output","network.q",[b,font])
    child = put("output","separators.child",[p])
    ow = put("output","overlay.standard",[overlay])
    ob = put("output","overlay.bigger",[overlay])
    for identity,node,category,kind,path,companions in (
        ("playlist.p",p,"Playlist","poster","playlist/P.jpg",[]),
        ("network.q",q,"Network","poster","network/Q.jpg",[]),
        ("separators.child",child,"Separators","poster","separators/Child.jpg",[]),
        ("overlay.standard",ow,"Overlays","overlay","overlays/Logo.png",["overlay.bigger"]),
        ("overlay.bigger",ob,"Overlays","overlay","overlays/bigger/Logo.png",["overlay.standard"])):
        outputs[identity] = {"node":node,"category":category,"kind":kind,"variant":identity.split(".")[-1] if kind == "overlay" else "base","local_path":"private/"+path,
            "public_path":path,"companions":companions,"context_sha256":fingerprint(identity),
            "evidence":{f:[fingerprint((identity,f))] for f in ("previews","confirmations","decisions","receipts")}}
    return {"schema_version":1,"kind":"m5-dependency-snapshot","basis":H,"nodes":nodes,"outputs":outputs,"unresolved":[]}


@pytest.mark.parametrize("changed,direct,transitive",[
    (["asset:logos/A.png"],{"playlist.p"},{"separators.child"}),
    (["asset:logos/B.png"],{"network.q"},set()),
    (["asset:fonts/Font.ttf"],{"playlist.p","network.q"},{"separators.child"}),
    (["asset:overlays/Logo.png"],{"overlay.standard","overlay.bigger"},set()),
    (["output:playlist.p"],{"playlist.p","separators.child"},set()),
    ([],set(),set()),
])
def test_independent_expected_output_oracle(changed,direct,transitive):
    value = graph_fixture()
    report = Snapshot.create(value).index().impact(changed)
    assert set(report["direct_outputs"]) == direct
    assert set(report["transitive_outputs"]) == transitive
    assert set(report["unaffected_outputs"]) == value["outputs"].keys()-(direct|transitive)
    for field in ("previews","confirmations","decisions"):
        assert {r["output"] for r in report["evidence_requiring_review"][field]} == direct|transitive
    assert report["impact_complete"] and not report["publication_authorized"]


def test_required_companion_is_reported_without_claiming_its_unchanged_pixels_need_rendering():
    report = Snapshot.create(graph_fixture()).index().impact(["output:overlay.standard"])
    assert report["required_companions"] == ["overlay.bigger"]
    assert "overlay.bigger" in report["unaffected_outputs"]


def test_shared_approval_record_is_scoped_per_member_not_entire_migration():
    value = graph_fixture()
    for output in value["outputs"].values():
        output["evidence"]["decisions"] = [H]
    report = Snapshot.create(value).index().impact(["asset:logos/B.png"])
    assert report["evidence_requiring_review"]["decisions"] == [{"output":"network.q","sha256":H}]


@pytest.mark.parametrize("mutate",[
    lambda v:v.update(schema_version=2), lambda v:v.update(schema_version=True),
    lambda v:v.update(approved=True),lambda v:v["nodes"]["asset:logos/A.png"].update(approved=True),
    lambda v:v["nodes"]["output:playlist.p"]["dependencies"].append("asset:missing.png"),
    lambda v:v["nodes"]["asset:logos/A.png"]["dependencies"].append("output:separators.child"),
    lambda v:v["nodes"]["asset:logos/A.png"].update(sha256="bad"),
    lambda v:v["nodes"]["asset:logos/A.png"].update(identity="logos/a.png"),
    lambda v:v["outputs"]["playlist.p"].update(public_path="network/Q.jpg"),
    lambda v:v["outputs"]["playlist.p"].update(local_path="private/network/q.jpg"),
    lambda v:v["outputs"]["playlist.p"].update(public_path="../escape.jpg"),
    lambda v:v["outputs"]["playlist.p"].update(kind="overlay"),
    lambda v:v["outputs"]["playlist.p"].update(companions=["missing"]),
    lambda v:v["outputs"]["playlist.p"].update(companions=["network.q"]),
    lambda v:v["outputs"].pop("overlay.standard"),
    lambda v:v["outputs"]["playlist.p"]["evidence"].update(decisions=["bad"]),
])
def test_malformed_partial_cyclic_or_substituted_dependency_graph_fails_closed(mutate):
    value = graph_fixture();mutate(value)
    with pytest.raises(BulkError):
        Snapshot.create(value)


@pytest.mark.parametrize("paths",[("P.jpg","p.jpg"),("Pok\u00e9mon.jpg","Poke\u0301mon.jpg")])
def test_case_and_unicode_output_collisions_are_global_across_categories(paths):
    value = graph_fixture()
    value["outputs"]["playlist.p"]["public_path"] = paths[0]
    value["outputs"]["network.q"]["public_path"] = paths[1]
    with pytest.raises(BulkError):Snapshot.create(value)


def test_source_case_alias_cannot_substitute_identical_bytes():
    value = graph_fixture()
    value["nodes"]["asset:logos/a.png"] = dict(value["nodes"]["asset:logos/A.png"],identity="logos/a.png")
    with pytest.raises(BulkError):Snapshot.create(value)


def test_unknown_or_unresolved_change_blocks_completeness_instead_of_guessing():
    graph = Snapshot.create(graph_fixture())
    assert not graph.index().impact(["asset:unknown.png"])["impact_complete"]
    value = graph_fixture();value["unresolved"] = ["Unrecognized external template"]
    assert not Snapshot.create(value).index().impact([])["impact_complete"]


def test_conservative_family_scope_is_explicitly_uncertain_until_per_child_comparison():
    value=graph_fixture()
    value["nodes"]["row:category.yml#family"]={"kind":"row","identity":"category.yml#family","sha256":H,"dependencies":[]}
    for key in ("output:playlist.p","output:network.q"):
        value["nodes"][key]["dependencies"].append("row:category.yml#family")
    report=Snapshot.create(value).index().impact(["row:category.yml#family"])
    assert not report["impact_complete"] and len(report["affected_outputs"]) == 3
    assert "per-child" in report["unresolved"][0]


def test_compare_detects_topology_replacement_and_retains_only_affected_old_evidence():
    old = Snapshot.create(graph_fixture());new = old.data()
    new["nodes"]["output:playlist.p"]["dependencies"] = ["asset:logos/B.png","asset:fonts/Font.ttf"]
    report = compare(old,Snapshot.create(new))
    assert set(report["affected_outputs"]) == {"playlist.p","separators.child"}
    assert set(report["unaffected_outputs"]) == {"network.q","overlay.standard","overlay.bigger"}


@pytest.mark.parametrize("change",["rename","caption","background","contract","source"])
def test_material_changes_invalidate_even_when_source_or_output_bytes_are_unchanged(change):
    old = Snapshot.create(graph_fixture());value = old.data()
    if change == "rename":value["outputs"]["playlist.p"]["public_path"] = "playlist/Renamed.jpg"
    elif change == "source":value["nodes"]["asset:logos/A.png"]["sha256"] = H
    else:value["nodes"]["output:playlist.p"]["sha256"] = fingerprint(change)
    assert set(compare(old,Snapshot.create(value))["affected_outputs"]) == {"playlist.p","separators.child"}


def test_immutable_canonical_snapshot_roundtrip_and_stale_or_interrupted_reads():
    graph = Snapshot.create(graph_fixture())
    assert Snapshot.load(graph.encoded,expected_sha256=graph.sha256) == graph
    for raw,pin in ((graph.encoded[:-1],graph.sha256),(graph.encoded,H),(b'{"x":1,"x":2}',hashlib.sha256(b'{"x":1,"x":2}').hexdigest())):
        with pytest.raises(BulkError):Snapshot.load(raw,expected_sha256=pin)
    detached = graph.data();detached["nodes"].clear()
    assert graph.data()["nodes"]


@pytest.fixture(scope="module")
def playlist():
    return boundary()


@pytest.fixture
def definition_files(tmp_path,playlist):
    rows = [read_canonical(r.to_dict()["effective_definition_json"]) for r in playlist.records]
    path = tmp_path/"playlist.yml";profiles = tmp_path/"profiles.yml"
    profiles.write_text(yaml.safe_dump({"schema_version":1,"profiles":{}}),encoding="utf8")
    def write(rows=rows,shared=None):
        path.write_text(yaml.safe_dump({"schema_version":1,"category":"Playlist","definitions":rows},allow_unicode=True),encoding="utf8")
        if shared is not None:
            profiles.write_text(yaml.safe_dump({"schema_version":1,"profiles":shared}),encoding="utf8")
        return resolve([path],profiles_path=profiles)
    return rows,path,profiles,write


def test_all_nine_playlist_designs_compatible_without_authorizing_contract(definition_files,playlist,monkeypatch):
    rows,path,profiles,write = definition_files
    def forbidden(*a,**k):pytest.fail("Historical rendering/network/state is prohibited")
    import PIL.Image
    import requests
    import create_defaults.bulk.state as state
    import create_defaults.create_poster as poster
    monkeypatch.setattr(PIL.Image,"open",forbidden)
    monkeypatch.setattr(requests.Session,"request",forbidden)
    monkeypatch.setattr(state.Store,"__init__",forbidden)
    monkeypatch.setattr(poster,"create_poster",forbidden)
    current = write()
    for record in playlist.records:
        result = validate_existing(record,current,fixture_only=True)
        assert result["outcome"] == "compatible" and not result["contract_authorized"]
        assert not result["operational_addition_eligible"]
    with pytest.raises(BulkError):validate_existing(playlist.records[0],current)


@pytest.mark.parametrize("where",["inherited","nested","language","normalized","category","caption","background","source","destination","renamed"])
def test_protected_settings_cannot_be_smuggled_through_intermediate_definitions(definition_files,playlist,where):
    rows,path,profiles,write = definition_files
    first = rows[0];shared = {}
    if where == "inherited":
        first["composer"].pop("font_size");first["extends"]="bad";shared={"bad":{"composer":{"font_size":100}}}
    elif where == "nested":first["composer"]["logo_offset"]=-199
    elif where == "language":first["overrides"]=[{"language":"en","changes":{"composer":{"white_wash":False}}}]
    elif where == "normalized":first["composer"]["gradient"]=99 # effective renderer still uses 1
    elif where == "category":first["category"]="Studio"
    elif where == "caption":first["caption"]["case"]="lower"
    elif where == "background":first["composer"]["base_color"]="#123456"
    elif where == "source":first["composer"]["logo"]="logos_playlist/Other.png"
    elif where == "destination":first["output"]["remote_paths"]["en"]="studio/Other.jpg"
    elif where == "renamed":first["id"]="playlist.renamed"
    with pytest.raises(BulkError):
        current = write(shared=shared)
        validate_existing(playlist.records[0],current,fixture_only=True)


def test_inherited_valid_settings_use_production_merge_and_only_used_leaves_are_dependencies(definition_files,playlist):
    rows,path,profiles,write = definition_files
    for row in rows:
        row["extends"]="locked";row["composer"].pop("font_size")
    current = write(shared={"locked":{"composer":{"font_size":154,"gradient":4}}})
    assert validate_existing(playlist.records[0],current,fixture_only=True)["outcome"] == "compatible"
    assert contribution({"composer":{"font_size":154,"gradient":4}},rows[0]) == {"composer":{"font_size":154}}


@pytest.mark.parametrize("attack",["duplicate","alias","unknown","cycle","missing","id_case","id_unicode"])
def test_ambiguous_yaml_and_parent_identity_paths_block(definition_files,attack):
    rows,path,profiles,write = definition_files
    if attack == "duplicate":
        path.write_text("schema_version: 1\nschema_version: 1\ncategory: Playlist\ndefinitions: []\n")
    elif attack == "alias":
        path.write_text("schema_version: 1\ncategory: Playlist\ndefinitions: &rows []\nother: *rows\n")
    elif attack == "unknown":rows[0]["composer"]["overrides"]={"approved":True}
    elif attack == "cycle":
        rows[0]["dependencies"]=[{"poster_id":rows[1]["id"],"input":"logo"}]
        rows[1]["dependencies"]=[{"poster_id":rows[0]["id"],"input":"logo"}]
    elif attack == "missing":rows[0]["dependencies"]=[{"poster_id":"playlist.missing","input":"logo"}]
    else:
        rows[0]["id"]="playlist.Pok\u00e9mon"
        rows[1]["id"]="playlist.pok\u00e9mon" if attack == "id_case" else "playlist.Poke\u0301mon"
    with pytest.raises(BulkError):
        if attack in {"duplicate","alias"}:resolve([path],profiles_path=profiles)
        else:write()


def synthetic_authority(playlist):
    approval = ContractApproval.from_dict({"schema_version":1,"kind":"contract-approval","id":"test-only.approval","revision":1,
        "provenance":{"actor":"bullmoose20","role":"maintainer","source":"synthetic test, not a real maintainer decision","evidence_sha256":H},
        "package":package_reference(playlist.contract),"decision":"approved","scope":"category-contract"})
    trust = {approval.sha256:TrustedDecision("bullmoose20",H)}
    registry = playlist.registry_for_decision(approval,trusted_decisions=trust)
    objects = {approval.sha256:approval.encoded,playlist.contract.sha256:playlist.contract.encoded}
    return Authority(registry.encoded,registry.sha256,objects.__getitem__,trust,"Playlist","poster","1.0.0",playlist.contract.sha256,"timeline-order")


def test_exact_m1_authority_is_reverified_and_never_inferred_from_public_dataclass_or_json(definition_files,playlist):
    current = definition_files[3]();record=playlist.records[0]
    authority = synthetic_authority(playlist)
    assert validate_existing(record,current,authority=authority)["contract_authorized"]
    for forged in (replace(authority,trusted_decisions={}),replace(authority,registry_sha256=H),
                   replace(authority,category="Studio"),replace(authority,variant="fake"),
                   replace(authority,contract_sha256=H),{"approved":True},playlist.contract):
        with pytest.raises(BulkError):validate_existing(record,current,authority=forged)


def test_stale_source_hashes_and_exact_case_are_verified_without_scanning(definition_files,playlist,tmp_path):
    record=playlist.records[0];job=read_canonical(record.to_dict()["job_json"])
    root=tmp_path/"assets"
    for item in job["inputs"]:
        dest=root/item["path"];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/item["path"],dest)
    current=definition_files[3]()
    assert validate_existing(record,current,fixture_only=True,source_root=root)["outcome"] == "compatible"
    (root/job["inputs"][1]["path"]).write_bytes(b"substituted source bytes")
    with pytest.raises(BulkError):validate_existing(record,current,fixture_only=True,source_root=root)


def test_attestation_cannot_survive_post_validation_mutation(playlist):
    value=playlist.records[0].to_dict();definition=read_canonical(value["effective_definition_json"]);job=read_canonical(value["job_json"])
    report={"kind":"m5-effective-validation","definition_sha256":fingerprint(definition),"job_sha256":fingerprint(job),"manifest_sha256":H}
    assert require_current(report,definition=definition,job=job,manifest_sha256=H)["current"]
    for field in ("font_size","base_color","logo","text","white_wash"):
        changed=deepcopy(job);changed["parameters"][field]="substituted"
        with pytest.raises(BulkError):require_current(report,definition=definition,job=changed,manifest_sha256=H)
    with pytest.raises(BulkError):require_current(report,definition=definition,job=job,manifest_sha256="b"*64)


def test_cli_is_opt_in_read_only_and_never_promotes_missing_contract_approval(tmp_path,capsys):
    graph=Snapshot.create(graph_fixture());path=tmp_path/"graph.json";path.write_bytes(graph.encoded)
    assert main(["inspect",str(path),"--sha256",graph.sha256]) == 0
    assert json.loads(capsys.readouterr().out)["outputs"] == 5
    assert main(["impact",str(path),"--sha256",graph.sha256,"--changed","asset:unknown"]) == 1
    capsys.readouterr()
    assert main(["validate-playlist"]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "m5_unapproved_contract"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["graph.json"]


def test_report_writes_are_explicit_isolated_and_immutable(tmp_path):
    path=tmp_path/"report.json";write_report(path,b"one");write_report(path,b"one")
    with pytest.raises(BulkError):write_report(path,b"two")
    with pytest.raises(BulkError):write_report(ROOT/"m5-not-authorized.json",b"never written")


def test_impact_timings_are_recorded_without_using_timing_as_correctness_threshold():
    graph=Snapshot.create(graph_fixture());start=perf_counter();index=graph.index();build_seconds=perf_counter()-start
    start=perf_counter()
    for _ in range(100):index.impact(["asset:logos/A.png"])
    single=(perf_counter()-start)/100
    start=perf_counter()
    for _ in range(100):index.impact(["asset:fonts/Font.ttf"])
    shared=(perf_counter()-start)/100
    assert build_seconds>=0 and single>=0 and shared>=0


@pytest.mark.parametrize("attack",[None,"unknown_parameter","unknown_generator","protected_measurement","orphan_child"])
def test_real_generator_families_expand_through_existing_registry(tmp_path,attack):
    from create_defaults.bulk.catalog import load_catalog
    base=next(d.data for d in load_catalog(("ContentRating",)) if d.data["generator"])
    if attack == "unknown_parameter":base["generator"]["parameters"]["white_wash"]=False
    if attack == "unknown_generator":base["generator"]["name"]="unapproved-engine"
    if attack == "protected_measurement":base["generator"]["parameters"]["measurements"]["1"]["point_size"]=True
    if attack == "orphan_child":base["generator"]["parameters"]["values"].append("new-child")
    path=tmp_path/"contentrating.yml";profiles=tmp_path/"profiles.yml"
    path.write_text(yaml.safe_dump({"schema_version":1,"category":"ContentRating","definitions":[base]}))
    profiles.write_text("schema_version: 1\nprofiles: {}\n")
    if attack:
        with pytest.raises(BulkError):resolve([path],profiles_path=profiles)
    else:
        current=resolve([path],profiles_path=profiles).data()
        assert len(current["expanded"]) == 18 and len(current["families"]) == 1
        assert all(v["generator"] is None for v in current["expanded"].values())


def test_actual_planner_is_replayed_and_self_resealed_job_substitution_cannot_bypass_it(definition_files,playlist):
    from create_defaults.bulk.translations import Translations
    from create_defaults.bulk.contracts.adoption.sources import load_pins
    current=definition_files[3]();identity=playlist.records[0].to_dict()["identity"]["id"]
    translations=Translations({"en":ROOT/"fixtures/english/en.yml"})
    # Same exact-source verification/retained historical trace used by M2/M3.
    translations.hashes["en"]=load_pins()["historical_english_sha256"]
    manifest=plan(current,translations,posters=(identity,))
    report=validate_candidate(current,manifest,identity,translations,fixture_only=True)
    assert report["effective_rules_valid"] and not report["complete_poster_design_approval"]
    assert not report["operational_addition_eligible"]
    from create_defaults.bulk.contracts.expanded.candidate import graph_for_candidate
    first,reports=graph_for_candidate(current,manifest,identity,translations,fixture_only=True)
    second,_=graph_for_candidate(current,manifest,identity,translations,fixture_only=True,baseline=first)
    assert not compare(first,second)["affected_outputs"]
    assert not first.index().impact([])["impact_complete"] # Explicitly scoped, not complete library.
    forged=deepcopy(translations);forged.sources["en"]["key_names"]["TIMELINE_ORDER"]="WATCH ORDER"
    with pytest.raises(BulkError):validate_candidate(current,manifest,identity,forged,fixture_only=True)
    for attack in ("raw","logo","font","caption","background","destination","extra","partial"):
        changed=deepcopy(manifest);job=changed["jobs"][0]
        if attack == "raw":job["raw_parameters"]["gradient"]=99
        elif attack == "logo":job["parameters"]["logo"]="logos_playlist/Other.png"
        elif attack == "font":job["parameters"]["font_size"]=100
        elif attack == "caption":job["parameters"]["text"]="RELEASE ORDER"
        elif attack == "background":job["parameters"]["base_color"]="#123456"
        elif attack == "destination":job["remote_relative"]="studio/forged.jpg"
        elif attack == "extra":job["parameters"]["approved"]=True
        else:changed["jobs"]=[]
        if changed["jobs"]:
            # Attack all unkeyed seals too; integrity is not category authority.
            job["render_fingerprint"]=fingerprint({k:job[k] for k in ("kind","parameters","inputs","dependencies","language_behavior")} | {"renderer":changed["renderer"]})
        changed["sha256"]=fingerprint({k:v for k,v in changed.items() if k != "sha256"})
        with pytest.raises(BulkError):validate_candidate(current,changed,identity,translations,fixture_only=True)


def test_missing_parent_artifact_is_blocked_not_generated(definition_files):
    from create_defaults.bulk.translations import Translations
    rows,path,profiles,write=definition_files
    parent,dependent=rows[:2]
    dependent["dependencies"]=[{"poster_id":parent["id"],"input":"logo"}]
    dependent["composer"]["logo"]="defaults-en/playlist/"+parent["output"]["filename"]
    current=write()
    with pytest.raises(BulkError,match="verified parent artifact"):
        plan(current,Translations({"en":ROOT/"fixtures/english/en.yml"}),posters=(dependent["id"],))


def test_stable_read_detects_source_edits_during_expansion(definition_files,monkeypatch):
    from create_defaults.bulk.contracts.expanded import resolution as module
    rows,path,profiles,write=definition_files
    write();actual=module.Planner.expand
    def interrupted(self,definitions):
        result=actual(self,definitions)
        path.write_text(path.read_text()+"\n# concurrent edit\n")
        return result
    monkeypatch.setattr(module.Planner,"expand",interrupted)
    with pytest.raises(BulkError,match="changed while resolving"):resolve([path],profiles_path=profiles)


def test_owned_resolution_requires_fresh_source_pins_before_later_validation(definition_files,playlist):
    rows,path,profiles,write=definition_files
    current=write()
    path.write_text(path.read_text()+"\n# changed after resolution\n")
    with pytest.raises(BulkError,match="resolve again"):
        validate_existing(playlist.records[0],current,fixture_only=True)
    with pytest.raises(BulkError):
        validate_existing(playlist.records[0],Resolution(current.encoded),fixture_only=True)


def test_review_dependency_context_is_local_and_includes_transitive_sources():
    old=Snapshot.create(graph_fixture());value=old.data()
    original=old.index().material_context("separators.child")
    value["nodes"]["asset:logos/B.png"]["sha256"]=H
    assert Snapshot.create(value).index().material_context("separators.child") == original
    value["nodes"]["asset:logos/A.png"]["sha256"]=H
    assert Snapshot.create(value).index().material_context("separators.child") != original


def test_m4_evidence_is_consumed_through_existing_verifier_and_stales_on_effective_changes(tmp_path):
    from create_defaults.bulk.tests.test_logo_workflow import logo
    from create_defaults.bulk.tests.test_contract_foundations import overlay_package
    from create_defaults.bulk.contracts.models import Contract,Identity
    from create_defaults.bulk.contracts.logos.assets import encode_png
    from create_defaults.bulk.contracts.logos.workflow import Selection,prepare
    from create_defaults.bulk.contracts.logos.storage import LogoArchive
    from create_defaults.bulk.contracts.expanded.review import consume,require_current as check_review
    root=tmp_path/"sources";root.mkdir();raw=encode_png(logo());(root/"Brand.PNG").write_bytes(raw)
    source={"path":"Brand.PNG","sha256":hashlib.sha256(raw).hexdigest()}
    selection=Selection.fixture(Contract.from_dict(overlay_package()),"color")
    item=Identity.from_dict({"schema_version":1,"kind":"item-identity","id":"overlay.synthetic-brand","category":"Overlays",
        "display_name":"Brand","rendered_caption":"","source":source,"local_path":"private/Brand.PNG","public_path":None,"semantic_member":None})
    prepared=prepare(selection,source_root=root,item=item,submitter="synthetic-contributor",sources={"master":source,"white":None},
        reason="M5 synthetic pending evidence test",request_id="m5.synthetic")
    archive=LogoArchive(tmp_path/"isolated-m4")
    snapshot=archive.start("m5.synthetic",prepared,expected_revision=0,selection=selection,source_root=root)
    identity=item.to_dict()["id"];definition={"fixture":"only"};job={"kind":"overlay","parameters":{"input":"Brand.PNG","box":[285,85],
        "trim":True,"colorspace":"sRGB","strip_metadata":True,"format":"PNG","resampling":"Pillow-LANCZOS"}}
    validation={"kind":"m5-effective-validation","identity":identity,"context_sha256":fingerprint(job),
        "definition_sha256":fingerprint(definition),"job_sha256":fingerprint(job),"contract_sha256":selection.contract.sha256}
    node=node_id("output",identity)
    value={"schema_version":1,"kind":"m5-dependency-snapshot","basis":H,
        "nodes":{"asset:Brand.PNG":{"kind":"asset","identity":"Brand.PNG","sha256":source["sha256"],"dependencies":[]},
                 node:{"kind":"output","identity":identity,"sha256":fingerprint(job),"dependencies":["asset:Brand.PNG"]}},
        "outputs":{identity:{"node":node,"kind":"overlay","variant":"standard","category":"Overlays","local_path":"private/Brand.PNG","public_path":None,
            "companions":[identity+".bigger"],"context_sha256":fingerprint(job),"evidence":{f:[] for f in ("previews","confirmations","decisions","receipts")}}},"unresolved":[]}
    value["nodes"]["output:"+identity+".bigger"] = dict(value["nodes"][node],identity=identity+".bigger")
    value["outputs"][identity+".bigger"] = dict(deepcopy(value["outputs"][identity]),node="output:"+identity+".bigger",variant="bigger",
        local_path="private/bigger/Brand.PNG",companions=[identity])
    graph=Snapshot.create(value)
    binding=consume(archive,"m5.synthetic",expected_sha256=snapshot.sha256,selection=selection,source_root=root,
        validation=validation,graph=graph,output_identity=identity,definition=definition,job=job)
    assert binding.data()["logo_review_phase"] == "PREVIEWS_READY"
    assert not binding.data()["complete_poster_design_approval"]
    assert check_review(binding,validation,graph,current_review_sha256=snapshot.sha256)["current"]
    from create_defaults.bulk.contracts.expanded.review import attach
    with_evidence=attach(graph,binding)
    report=with_evidence.index().impact(["asset:Brand.PNG"])
    assert len(report["evidence_requiring_review"]["previews"]) == 2
    assert not report["evidence_requiring_review"]["decisions"]
    assert check_review(binding,validation,with_evidence,current_review_sha256=snapshot.sha256)["current"]
    with pytest.raises(BulkError):check_review(binding,dict(validation,context_sha256=H),graph,current_review_sha256=snapshot.sha256)
    changed=graph.data();changed["nodes"]["asset:Brand.PNG"]["sha256"]=H
    with pytest.raises(BulkError):check_review(binding,validation,Snapshot.create(changed),current_review_sha256=snapshot.sha256)
    with pytest.raises(BulkError):consume({},"m5.synthetic",expected_sha256=snapshot.sha256,selection=selection,source_root=root,
        validation=validation,graph=graph,output_identity=identity,definition=definition,job=job)
    with pytest.raises(BulkError):consume(archive,"m5.synthetic",expected_sha256=H,selection=selection,source_root=root,
        validation=validation,graph=graph,output_identity=identity,definition=definition,job=job)
    partial=graph.data();partial["nodes"].pop("output:"+identity+".bigger");partial["outputs"].pop(identity+".bigger")
    partial["outputs"][identity]["companions"]=[]
    with pytest.raises(BulkError):consume(archive,"m5.synthetic",expected_sha256=snapshot.sha256,selection=selection,source_root=root,
        validation=validation,graph=Snapshot.create(partial),output_identity=identity,definition=definition,job=job)
