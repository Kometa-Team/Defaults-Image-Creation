"""Closed schemas, exact spelling, immutable pins and cross-document negatives."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path

import pytest

from create_defaults.bulk.common import BulkError, canonical, fingerprint
from create_defaults.bulk.contracts.models import read_document as read_m1
from create_defaults.bulk.contracts.language_policy import (
    LanguagePolicy, TranslationSelection, DestinationPolicy, DestinationEvidence,
    ValidationSubject, Phase3Attestation, check_bundle_structure, reference, read_document,
)
from create_defaults.phase3.tests.samples import bundle, h


@pytest.mark.parametrize("index", range(6))
def test_valid_roundtrip_detached_values_and_immutable_canonical_bytes(values,index):
    value=values[index]
    assert type(value).from_bytes(value.encoded)==value
    assert read_document(value.encoded,value.KIND,expected_sha256=value.sha256)==value
    assert value.sha256==hashlib.sha256(value.encoded).hexdigest()
    detached=value.to_dict();detached["id"]="different"
    assert value.to_dict()["id"]!="different"
    with pytest.raises(FrozenInstanceError):value.encoded=b'{}'
    assert type(value).from_dict(dict(reversed(list(value.to_dict().items())))).encoded==value.encoded


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("field,value", [("unexpected",True),("schema_version",2),("schema_version",True),("stage","approved"),("kind","contract-approval"),("version","1.0"),("version","1.0.0\n"),("id","bad\n")])
def test_unknown_fields_versions_and_wrong_record_stages_fail(values,index,field,value):
    data=values[index].to_dict();data[field]=value
    with pytest.raises(BulkError):type(values[index]).from_dict(data)


@pytest.mark.parametrize("index",range(6))
def test_missing_mandatory_fields_altered_external_pins_and_frozen_m1_rejection(values,index):
    document=values[index];data=document.to_dict();data.pop("id")
    with pytest.raises(BulkError):type(document).from_dict(data)
    with pytest.raises(BulkError):read_document(document.encoded,document.KIND,expected_sha256="0"*64)
    with pytest.raises(BulkError):read_m1(document.encoded,"record")
    with pytest.raises(BulkError):read_document(document.encoded,"contract-approval",expected_sha256=document.sha256)


@pytest.mark.parametrize("invalid",["PT-br","pt_br","nb_no","fr","", "../en","en/US","ｅｎ","en\n"," en","en ","en_US_extra_more"])
def test_only_exact_registered_codes_and_explicit_aliases_resolve(values,invalid):
    with pytest.raises(BulkError):values[0].resolve(invalid)


def test_exact_codes_then_aliases_without_silent_normalization_or_discovery_promotion(values):
    policy=values[0]
    assert policy.resolve("pt-br")=="pt-br" and policy.resolve("pt_BR")=="pt-br"
    assert policy.resolve("nb_NO")=="nb_NO" and policy.resolve("nb-NO")=="nb_NO"
    assert len(policy.to_dict()["languages"])==3
    assert policy.to_dict()["coverage"][0]["languages"]==["pt-br"]
    # Registered English is not inferred to be permitted by the synthetic contract.
    assert "en" not in policy.to_dict()["coverage"][0]["languages"]


@pytest.mark.parametrize("mutation",["duplicate-code","duplicate-alias","alias-code","ambiguous-case","unregistered-coverage","duplicate-coverage","overlay-kind"])
def test_ambiguous_language_registration_and_contract_declarations_fail(values,mutation):
    data=values[0].to_dict()
    if mutation=="duplicate-code":data["languages"].append(deepcopy(data["languages"][0]))
    elif mutation=="duplicate-alias":data["languages"][0]["aliases"]=["pt_BR"]
    elif mutation=="alias-code":data["languages"][0]["aliases"]=["pt-br"]
    elif mutation=="ambiguous-case":data["languages"].append(dict(code="pt-BR",aliases=[]))
    elif mutation=="unregistered-coverage":data["coverage"][0]["languages"]=["fr"]
    elif mutation=="duplicate-coverage":data["coverage"].append(deepcopy(data["coverage"][0]))
    else:data["coverage"][0]["package"]["kind"]="overlay"
    with pytest.raises(BulkError):LanguagePolicy.from_dict(data)


@pytest.mark.parametrize("path",["../poster.jpg","/poster.jpg","C:/poster.jpg","C:poster.jpg","\\\\host\\file","x\\y","a//b","a/./b","a/.git/config","CON.png","x.","x ","a:stream","a\x00b"])
@pytest.mark.parametrize("location",["root","path","source"])
def test_unsafe_destination_and_source_paths_fail(values,path,location):
    if location=="source":
        data=values[1].to_dict();data["source"]["resources"][0]["path"]=path
        cls=TranslationSelection
    else:
        data=values[3].to_dict()
        if location=="root":data["target"]["root"]=path
        else:data["target"]["paths"]=[path]
        cls=DestinationEvidence
    with pytest.raises(BulkError):cls.from_dict(data)


@pytest.mark.parametrize("branch",["../main","-main","a..b","a@{b","a b","a.lock",".hidden","a//b","HEAD","@","main\n"])
def test_unsafe_exact_branches_fail(values,branch):
    data=values[3].to_dict();data["target"]["branch"]=branch
    with pytest.raises(BulkError):DestinationEvidence.from_dict(data)


@pytest.mark.parametrize("field,value",[("host","evil.example"),("repository_id",True),("repository_id",0),("owner_id",-1),("name","https://github.com/Fixture/X"),("name","Fixture/X\n"),("name","user:password@host/repo")])
def test_malformed_repository_identity_rejected(values,field,value):
    data=values[3].to_dict();data["target"]["repository"][field]=value
    with pytest.raises(BulkError):DestinationEvidence.from_dict(data)


@pytest.mark.parametrize("field,value",[("commit","x"*40),("tree","a"*64),("commit","A"*40),("commit","a"*39)])
def test_malformed_source_git_pins_rejected(values,field,value):
    data=values[1].to_dict();data["source"][field]=value
    with pytest.raises(BulkError):TranslationSelection.from_dict(data)


@pytest.mark.parametrize("mutation",["resource-pin","duplicate-source","unknown-source","duplicate-value"])
def test_inconsistent_source_or_value_evidence_rejected(values,mutation):
    data=values[1].to_dict()
    if mutation=="resource-pin":data["source"]["resources"][0]["sha256"]="1"*64
    elif mutation=="duplicate-source":data["source"]["resources"].append(deepcopy(data["source"]["resources"][0]))
    elif mutation=="unknown-source":data["values"][0]["resource_path"]="defaults/fr.yml"
    else:data["values"].append(deepcopy(data["values"][0]))
    with pytest.raises(BulkError):TranslationSelection.from_dict(data)


@pytest.mark.parametrize("mutation",["duplicate-language","nonenglish-official","repo-id-conflict","repo-name-conflict","authority-disable","english-user-disable"])
def test_inconsistent_destination_policy_declarations_rejected(values,mutation):
    data=values[2].to_dict()
    if mutation=="duplicate-language":data["mappings"].append(deepcopy(data["mappings"][0]))
    elif mutation=="nonenglish-official":data["mappings"][0]["repository"]=data["official_repository"]
    elif mutation=="repo-id-conflict":data["mappings"][0]["repository"]["repository_id"]=data["official_repository"]["repository_id"]
    elif mutation=="repo-name-conflict":data["mappings"][0]["repository"]["name"]=data["official_repository"]["name"].lower()
    elif mutation=="authority-disable":data["external_authority_required"]=False
    else:data["english_user_owned_allowed"]=False
    with pytest.raises(BulkError):DestinationPolicy.from_dict(data)


def test_english_user_mapping_can_be_represented_without_eligibility_or_authority(values):
    data=values[2].to_dict();data["mappings"][0]["language"]="en"
    policy=DestinationPolicy.from_dict(data)
    assert policy.to_dict()["mappings"][0]["repository"]!=data["official_repository"]
    assert not hasattr(policy,"eligible")


@pytest.mark.parametrize("mutation",["id","local-case","unicode-collision","hash"])
def test_membership_identity_and_filename_collisions_rejected(values,mutation):
    data=values[4].to_dict();other=deepcopy(data["outputs"][0]);other.update(id="fixture.other",local_path="playlist/Other.jpg",public_path="playlist/Other.jpg")
    if mutation=="id":other["id"]=data["outputs"][0]["id"]
    elif mutation=="local-case":other["local_path"]=data["outputs"][0]["local_path"].upper()
    elif mutation=="unicode-collision":
        import unicodedata
        other["local_path"]=unicodedata.normalize("NFD",data["outputs"][0]["local_path"])
    else:data["membership_sha256"]="0"*64
    if mutation!="hash":
        data["outputs"].append(other);data["membership_sha256"]=fingerprint(data["outputs"])
    with pytest.raises(BulkError):ValidationSubject.from_dict(data)


def test_stable_id_and_exact_unicode_names_are_independent(values):
    import unicodedata
    data=values[4].to_dict();data["outputs"][0]["local_path"]=unicodedata.normalize("NFD","playlist/Élan.jpg")
    data["membership_sha256"]=fingerprint(data["outputs"])
    subject=ValidationSubject.from_dict(data)
    assert subject.to_dict()["id"]==values[4].to_dict()["id"]
    assert subject.to_dict()["outputs"][0]["local_path"]==data["outputs"][0]["local_path"]
    assert subject.sha256!=values[4].sha256


def test_complete_structure_is_only_metadata_consistency(values):
    assert check_bundle_structure(*values) is None
    att=values[-1].to_dict()
    assert all(att[k] is False for k in ["publication_authorized","production_enforcement","ready","active"])


@pytest.mark.parametrize("status",["verified","stale","unavailable","unverifiable"])
def test_source_status_claim_never_becomes_operational_currentness(values,status):
    data=values[1].to_dict();data["verification"]["status"]=status
    selection=TranslationSelection.from_dict(data)
    at=values[-1].to_dict();at["translation_selection"]=reference(selection)
    attestation=Phase3Attestation.from_dict(at)
    assert check_bundle_structure(values[0],selection,*values[2:-1],attestation) is None
    assert not attestation.to_dict()["ready"] and not attestation.to_dict()["active"]


def test_new_source_commit_with_identical_content_requires_new_pins(values):
    old=values[1];data=old.to_dict();data["source"]["commit"]="0"*40
    data["verification"]["source_sha256"]=fingerprint(data["source"])
    changed=TranslationSelection.from_dict(data)
    assert changed.to_dict()["source"]["resources"]==old.to_dict()["source"]["resources"]
    assert changed.sha256!=old.sha256
    with pytest.raises(BulkError):read_document(changed.encoded,changed.KIND,expected_sha256=old.sha256)
    with pytest.raises(BulkError):check_bundle_structure(values[0],changed,*values[2:])


@pytest.mark.parametrize("field,value",[("output_ids",["foreign.output"]),("membership_sha256","0"*64),("language","en"),("dependencies_sha256","0"*64),("review_context_sha256","0"*64),("authority_context_sha256","0"*64),("verification_context_sha256","0"*64)])
def test_rebound_or_foreign_attestation_cannot_match_original_bundle(values,field,value):
    data=values[-1].to_dict();data[field]=value
    changed=Phase3Attestation.from_dict(data)
    with pytest.raises(BulkError):check_bundle_structure(*values[:-1],changed)


@pytest.mark.parametrize("field",["publication_authorized","production_enforcement","ready","active"])
@pytest.mark.parametrize("value",[True,1,"false"])
def test_attestation_can_never_authorize_production(values,field,value):
    data=values[-1].to_dict();data[field]=value
    with pytest.raises(BulkError):Phase3Attestation.from_dict(data)


@pytest.mark.parametrize("encoded",[b'{"kind":1,"kind":2}',b'\xff',b'{"x":NaN}',b'{"x":"\\ud800"}',b'[]'])
def test_invalid_json_and_duplicate_keys_rejected(encoded):
    with pytest.raises(BulkError):LanguagePolicy.from_bytes(encoded)


@pytest.mark.parametrize("value",[float("nan"),{1:"not a string key"},{"bad"},Path("not-json")])
def test_non_json_native_values_are_rejected_before_canonicalization(values,value):
    data=values[0].to_dict();data["id"]=value
    with pytest.raises(BulkError):LanguagePolicy.from_dict(data)


def test_shared_parser_byte_and_depth_bounds_apply():
    with pytest.raises(BulkError):LanguagePolicy.from_bytes(b"x"*(8*1024*1024+1))
    value={}
    for _ in range(42):value={"nested":value}
    with pytest.raises(BulkError):LanguagePolicy.from_dict(value)


def test_cross_platform_canonical_golden_vectors(values):
    expected=json.loads(Path(__file__).with_name("golden-v1.json").read_text(encoding="utf8"))
    assert {doc.KIND:doc.sha256 for doc in values}==expected
    assert all(b'\\u00' in doc.encoded for doc in [values[3],values[4]])
    assert all(b'\r\n' not in doc.encoded for doc in values)
