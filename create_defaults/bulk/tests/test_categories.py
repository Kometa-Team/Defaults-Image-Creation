"""All closed M6 variants, synthetic mutations and fail-closed authority."""

from copy import deepcopy
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from create_defaults.bulk.common import BulkError,canonical,fingerprint
from create_defaults.bulk.config import CATEGORIES
from create_defaults.bulk.contracts.adoption.models import encoded_json,read_canonical
from create_defaults.bulk.contracts.categories.release import Implementation,RELEASE_SHA256,authorize
from create_defaults.bulk.contracts.categories.models import Rules,Release
from create_defaults.bulk.contracts.categories.audit import _assignment
from create_defaults.bulk.contracts.categories.validation import check_job,check_membership,check_names
from create_defaults.bulk.contracts.categories.policy import WHITE_DEFAULTS,PAIRED
from create_defaults.bulk.contracts.expanded.validation import Authority
from create_defaults.bulk.contracts.models import RegistryDocument,ContractApproval
from create_defaults.bulk.contracts.registry import package_reference,TrustedDecision


CASE_FILE=Path(__file__).with_name("fixtures")/"categories-v1.json.gz"
RAW=gzip.decompress(CASE_FILE.read_bytes())
assert hashlib.sha256(RAW).hexdigest()=="5477988a3ab115cea6ca8d33822dc0e70561c6c80647bb8d2fdb58fed624e36f"
CASES=json.loads(RAW)["cases"]
ONE={}
for case in CASES:ONE.setdefault((case["category"],case["variant"]),case)


@pytest.fixture(scope="module")
def release(category_implementation):
    return category_implementation


@pytest.fixture(scope="module")
def prepared(category_prepared):
    return category_prepared


def context(case,prepared):
    package,data=prepared[case["category"]];c,rules,members=data
    value={"identity":{"id":case["identity"]},"job_json":encoded_json(case["job"]),"effective_definition_json":encoded_json(case["definition"])}
    return package,data,_assignment(rules,members,value),members[case["identity"]]


@pytest.mark.parametrize("case",list(ONE.values()),ids=[c+"/"+v for c,v in ONE])
def test_every_closed_design_variant_retains_its_exact_historical_job(case,prepared):
    p,data,a,member=context(case,prepared)
    assert member["record_sha256"]==case["record_sha256"]
    result=check_job(p,case["definition"],case["job"],a,historical_member=member,_prepared=data)
    assert not result["artifact_approved"] and not result["publication_authorized"]


@pytest.mark.parametrize("category",CATEGORIES)
def test_protected_style_change_cannot_enter_any_category(category,prepared):
    case=next(c for c in CASES if c["category"]==category)
    p,data,a,member=context(case,prepared);job=deepcopy(case["job"]);d=deepcopy(case["definition"])
    field="trim" if category=="Overlays" else "logo_offset"
    changed=not job["parameters"][field] if field=="trim" else job["parameters"][field]+1
    job["raw_parameters"][field]=job["parameters"][field]=changed
    if category=="Overlays":d["parameters"][field]=changed
    else:
        d["composer"][field]=changed
        job["definition_fingerprint"]=fingerprint({"definition":d,"generator_origin":job["generator_origin"]})
    with pytest.raises(BulkError):check_job(p,d,job,a,_prepared=data)


@pytest.mark.parametrize("category",CATEGORIES)
@pytest.mark.parametrize("field",["font","white_wash","variant","composer","category","contract_sha256","approved"])
def test_contributor_allowlist_cannot_smuggle_style_or_authority(category,field,prepared):
    p,data=prepared[category];variant=data[0]["variants"][0]["id"]
    with pytest.raises(BulkError):p.contract.validate_content(variant,{"display_name":"Example",field:{"value":True}})
    with pytest.raises(BulkError):p.contract.validate_content(variant,{"source":{"path":"X.png","sha256":"a"*64,"white_wash":False}})


@pytest.mark.parametrize("category",sorted(WHITE_DEFAULTS))
def test_white_default_pending_exception_and_exact_historical_scope(category,prepared):
    case=next(c for c in CASES if c["category"]==category and c["job"]["raw_parameters"]["white_wash"])
    p,data,a,member=context(case,prepared)
    assert check_job(p,case["definition"],case["job"],a,_prepared=data)["compatibility"]=="compatible"
    d=deepcopy(case["definition"]);j=deepcopy(case["job"])
    d["composer"]["white_wash"]=j["raw_parameters"]["white_wash"]=j["parameters"]["white_wash"]=False
    j["definition_fingerprint"]=fingerprint({"definition":d,"generator_origin":j["generator_origin"]})
    # A pending/claimed exception cannot turn into a boolean override.
    with pytest.raises(BulkError):check_job(p,d,j,a,_prepared=data)
    if category!="Playlist":
        old=next(c for c in CASES if c["category"]==category and not c["job"]["raw_parameters"]["white_wash"])
        p,data,a,member=context(old,prepared)
        assert check_job(p,old["definition"],old["job"],a,historical_member=member,_prepared=data)["compatibility"]=="accepted_historical_exception"
        with pytest.raises(BulkError):check_job(p,old["definition"],old["job"],a,_prepared=data)
        with pytest.raises(BulkError):check_job(p,old["definition"],old["job"],replace(a,identity="another.item"),historical_member=member,_prepared=data)


@pytest.mark.parametrize("category",["Chart","Country","Network","Streaming","Overlays"])
def test_required_output_membership_missing_duplicate_source_swap_identity_and_wash(category,prepared):
    first=next(c for c in CASES if c["category"]==category)
    p,data,a,member=context(first,prepared)
    second=next(c for c in CASES if c["identity"]==member["companions"][0])
    result=[]
    for case in (first,second):
        p,data,a,m=context(case,prepared)
        result.append(check_job(p,case["definition"],case["job"],a,historical_member=m,_prepared=data))
    check_membership(result)
    with pytest.raises(BulkError):check_membership(result[:1])
    with pytest.raises(BulkError):check_membership(result+result[:1])
    p,data,a,m=context(first,prepared)
    with pytest.raises(BulkError):check_job(p,first["definition"],first["job"],replace(a,job_id="wrong"),_prepared=data)
    with pytest.raises(BulkError):check_job(p,first["definition"],first["job"],replace(a,source_json=encoded_json({"path":"Wrong.png","sha256":"a"*64})),_prepared=data)
    with pytest.raises(BulkError):check_job(p,first["definition"],first["job"],replace(a,presentation="bigger" if category!="Overlays" else "single"),_prepared=data)
    j=deepcopy(first["job"])
    j["raw_parameters"]["white_wash"]=j["parameters"]["white_wash"]=True
    with pytest.raises(BulkError):check_job(p,first["definition"],j,a,_prepared=data)


@pytest.mark.parametrize("category",["Studio","VideoFormat","Overlays"])
def test_source_preserving_has_no_pixel_colour_assumption(category,prepared):
    case=next(c for c in CASES if c["category"]==category and (category=="Overlays" or not c["job"]["raw_parameters"]["white_wash"]))
    p,data,a,m=context(case,prepared)
    # Black/white/monochrome sources are not reclassified by their RGB values;
    # processing and real PNG provenance remain M4's separately tested concern.
    assert check_job(p,case["definition"],case["job"],a,historical_member=m,_prepared=data)
    changed=deepcopy(case["job"])
    next(i for i in changed["inputs"] if i["path"]==m["source"]["path"])["sha256"]="b"*64
    with pytest.raises(BulkError):check_job(p,case["definition"],changed,a,_prepared=data)


@pytest.mark.parametrize("paths",[("X.jpg","x.jpg"),("Caf\u00e9.jpg","Cafe\u0301.jpg")])
def test_exact_case_unicode_collisions_are_blocked(paths):
    with pytest.raises(BulkError):check_names([{"local_relative":p,"remote_relative":None} for p in paths])


def test_complete_release_and_unapproved_registry_cannot_establish_authority(release):
    assert len(release.packages)==22
    assert sum(len(p.contract.to_dict()["variants"]) for p in release.packages)==278
    assert all(e["approval"]=="missing_exact_maintainer_decision" for e in release.release.to_dict()["entries"])
    with pytest.raises(BulkError):release.select("Invented")
    with pytest.raises(BulkError):Implementation.load(expected_sha256="a"*64)
    p=release.select("Playlist")
    with pytest.raises(BulkError):authorize(p,"timeline-order",{"approved":True})


@pytest.mark.parametrize("category",CATEGORIES)
def test_forged_approval_and_stale_contract_pin_block_every_category(category,prepared):
    p,data=prepared[category];variant=data[0]["variants"][0]["id"]
    approval=ContractApproval.from_dict({"schema_version":1,"kind":"contract-approval","package":package_reference(p.contract),
        "id":"synthetic-m6.approval","revision":1,"scope":"category-contract",
        "decision":"approved","provenance":{"actor":"bullmoose20","role":"maintainer","source":"synthetic untrusted test claim","evidence_sha256":"a"*64}})
    registry=RegistryDocument.from_dict({"schema_version":1,"kind":"category-contract-registry","id":"m6-test","version":"1.0.0","owner":"bullmoose20",
        "provenance":{"actor":"bullmoose20","role":"maintainer","source":"synthetic fixture","evidence_sha256":"a"*64},
        "entries":[{"package":package_reference(p.contract),"variants":[v["id"] for v in data[0]["variants"]],"approval_sha256":approval.sha256,"adoption_sha256":[]}]})
    objects={p.contract.sha256:p.contract.encoded,approval.sha256:approval.encoded}
    authority=Authority(registry.encoded,registry.sha256,objects.__getitem__,{},category,data[0]["kind"],"1.0.0",p.contract.sha256,variant)
    with pytest.raises(BulkError):authorize(p,variant,authority)
    with pytest.raises(BulkError):authorize(p,variant,replace(authority,registry_sha256="b"*64))
    # Test-only controlled attribution is not bundled approval or persisted
    # state. Even this cannot authorize a substituted M6 membership sidecar.
    attributed=replace(authority,trusted_decisions={approval.sha256:TrustedDecision("bullmoose20","a"*64)})
    assert authorize(p,variant,attributed).sha256==p.contract.sha256
    changed=p.rules.to_dict();members=read_canonical(changed["members_json"])
    first=next(iter(members));members[first]["context_sha256"]="b"*64
    changed["members_json"]=encoded_json(members)
    from create_defaults.bulk.contracts.categories.release import Package
    substituted=Package(p.contract,Rules.from_dict(changed))
    with pytest.raises(BulkError):authorize(substituted,variant,attributed)


@pytest.mark.parametrize("mutation",["unknown","missing","pair","hash","presentation"])
def test_rules_document_is_closed_and_companions_cannot_be_weakened(release,mutation):
    value=release.select("Country").rules.to_dict();members=read_canonical(value["members_json"])
    first=next(iter(members))
    if mutation=="unknown":value["approved"]=True
    elif mutation=="missing":del value["basis_sha256"]
    elif mutation=="pair":members[first]["companions"]=["unknown"]
    elif mutation=="hash":members[first]["record_sha256"]="invalid"
    elif mutation=="presentation":members[first]["presentation"]="invented"
    value["members_json"]=encoded_json(members)
    with pytest.raises(BulkError):Rules.from_dict(value)


@pytest.mark.parametrize("change",["background","path","dependency","caption"])
def test_historical_exception_cannot_survive_changed_material_context(change,prepared):
    case=next(c for c in CASES if c["category"]=="Franchise" and not c["job"]["raw_parameters"]["white_wash"])
    p,data,a,member=context(case,prepared);d=deepcopy(case["definition"]);j=deepcopy(case["job"])
    if change=="background":
        d["composer"]["base_color"]=j["parameters"]["base_color"]=j["raw_parameters"]["base_color"]="#112233"
        a=replace(a,background="#112233")
    elif change=="path":
        j["local_relative"]="defaults-en/franchise/Changed.jpg";j["remote_relative"]="franchise/Changed.jpg"
        a=replace(a,local_path=j["local_relative"],public_path=j["remote_relative"])
    elif change=="dependency":j["dependencies"]=[{"job_id":"forged-parent","sha256":"a"*64}]
    else:d["caption"]["text"]="Changed"
    j["definition_fingerprint"]=fingerprint({"definition":d,"generator_origin":j["generator_origin"]})
    with pytest.raises(BulkError):check_job(p,d,j,a,historical_member=member,_prepared=data)


def test_material_rule_projection_does_not_invalidate_other_items_or_metadata(prepared):
    from create_defaults.bulk.contracts.categories.dependencies import material_design
    p,data=prepared["Playlist"];c,rules,members=data
    design=deepcopy(c["variants"][0]["design"]);rule=rules["timeline-order"]
    original=material_design(design,rule)
    design["background"]["assignments_sha256"]="b"*64
    design["fitting"]["measurement_sha256"]="b"*64
    design["logo"]["historical_acceptance_refs"]=["b"*64]
    design["caption"]["content_types"].append({"id":"different-item","mode":"translation","value":"OTHER","template":"{value}"})
    assert material_design(design,rule)==original
    design["geometry"]["logo_offset"]+=1
    assert material_design(design,rule)!=original


@pytest.mark.parametrize("category",sorted(PAIRED))
def test_controlled_coloured_master_can_supply_both_presentations_without_style_input(category,prepared):
    white=next(c for c in CASES if c["category"]==category and c["job"]["remote_relative"].split("/")[1]=="white"
               and read_canonical(prepared[category][1][1][c["variant"]]["style_json"]).get("white_wash") is not None
               and prepared[category][1][1][c["variant"]]["treatment"]=="BOTH_REQUIRED")
    p,data,a,m=context(white,prepared)
    colour=next(c for c in CASES if c["identity"]==m["companions"][0])
    p,data,ca,cm=context(colour,prepared);source=cm["source"]
    d=deepcopy(white["definition"]);j=deepcopy(white["job"])
    old=read_canonical(a.source_json)["path"]
    for params in (d["composer"],j["raw_parameters"],j["parameters"]):
        params["white_wash"]=True;params["logo"]=source["path"]
    for item in j["inputs"]:
        if item["path"]==old:item.update(source)
    j["definition_fingerprint"]=fingerprint({"definition":d,"generator_origin":j["generator_origin"]})
    assigned=replace(a,source_json=encoded_json(source),derived_white=True)
    w=check_job(p,d,j,assigned,_prepared=data)
    c=check_job(p,colour["definition"],colour["job"],ca,_prepared=data)
    check_membership([w,c])
    assert not w["artifact_approved"]
    if not read_canonical(data[1][a.variant]["style_json"])["white_wash"]:
        with pytest.raises(BulkError):check_job(p,d,j,replace(assigned,derived_white=False),_prepared=data)
