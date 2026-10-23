from dataclasses import asdict, replace

import pytest

from create_defaults.bulk.common import BulkError, fingerprint
from create_defaults.bulk.contracts.language_policy import (
    AuthorityContext, SourceVerificationContext, AuthorityResult, AuthorityVerifier,
    DestinationEvidence, UnavailableAuthority,
)
from create_defaults.bulk.contracts.language_policy.authority import AuthorityStatus
from create_defaults.bulk.contracts.language_policy.simulation import SyntheticAuthority
from create_defaults.phase3.tests.samples import context, h


def test_default_provider_is_typed_unavailable_even_for_matching_claims(values):
    evidence=values[3]
    assert isinstance(UnavailableAuthority(),AuthorityVerifier)
    for binding in [None,context(evidence),asdict(context(evidence))]:
        result=UnavailableAuthority().verify(evidence,binding)
        assert result.status is AuthorityStatus.UNAVAILABLE
        assert not result.readiness_authorized and not result.publication_authorized


def test_matching_synthetic_provider_never_produces_a_real_authorization(values):
    evidence=values[3]
    result=SyntheticAuthority().verify(evidence,context(evidence))
    assert result.status is AuthorityStatus.SYNTHETIC_ONLY
    assert not result.readiness_authorized and not result.publication_authorized
    assert not hasattr(result,"ready") and not hasattr(result,"active")


@pytest.mark.parametrize("field",["evidence_sha256","subject_sha256","destination_policy_sha256","target_sha256","assertion_sha256","verification_context_sha256"])
def test_exact_scope_and_external_context_mismatch_fail_closed(values,field):
    evidence=values[3]
    binding=replace(context(evidence),**{field:"0"*64})
    result=SyntheticAuthority().verify(evidence,binding)
    assert result.status is AuthorityStatus.UNVERIFIABLE and not result.readiness_authorized


@pytest.mark.parametrize("field,value",[("branch","other"),("root","other/root"),("paths",["other.jpg"]),("language","en"),("inventory_sha256","0"*64)])
def test_changed_destination_scope_cannot_replay_original_context(values,field,value):
    original=values[3];data=original.to_dict();data["target"][field]=value
    evidence=DestinationEvidence.from_dict(data)
    result=SyntheticAuthority().verify(evidence,context(original))
    assert result.status is AuthorityStatus.UNVERIFIABLE
    assert not result.readiness_authorized and not result.publication_authorized


@pytest.mark.parametrize("field,value",[("principal","other.actor"),("issuer","other.issuer"),("issuer_version","2.0.0"),("as_of","2029-12-31T23:59:59Z"),("as_of","2030-01-02T00:00:00Z")])
def test_wrong_principal_issuer_and_explicit_time_fail_closed(values,field,value):
    evidence=values[3]
    result=SyntheticAuthority().verify(evidence,replace(context(evidence),**{field:value}))
    assert result.status in {AuthorityStatus.UNVERIFIABLE,AuthorityStatus.EXPIRED}
    assert not result.readiness_authorized


@pytest.mark.parametrize("status",["unavailable","unverifiable","expired","revoked"])
def test_unverified_or_expired_revoked_claims_block_even_when_rehashed(values,status):
    data=values[3].to_dict();data["authorization"]["status"]=status
    evidence=DestinationEvidence.from_dict(data)
    result=SyntheticAuthority().verify(evidence,context(evidence))
    assert result.status is not AuthorityStatus.SYNTHETIC_ONLY and not result.readiness_authorized


@pytest.mark.parametrize("mode",["unknown-revocation","revoked","nonsynthetic","dictionary-context","none-context"])
def test_revocation_real_claims_and_user_json_never_enter_synthetic_trust(values,mode):
    data=values[3].to_dict()
    if mode=="unknown-revocation":data["authorization"]["revocation"].update(status="unknown",checked_at=None,revision_sha256=None)
    elif mode=="revoked":data["authorization"]["revocation"]["status"]="revoked"
    elif mode=="nonsynthetic":data["authorization"]["synthetic"]=False
    evidence=DestinationEvidence.from_dict(data);binding=context(evidence)
    if mode=="dictionary-context":binding=asdict(binding)
    elif mode=="none-context":binding=None
    result=SyntheticAuthority().verify(evidence,binding)
    assert result.status is not AuthorityStatus.SYNTHETIC_ONLY
    assert not result.publication_authorized


@pytest.mark.parametrize("key",["owner_verified","token","access_token","authorization_header","password","publishing_credentials"])
def test_self_asserted_authority_and_credentials_are_not_schema_fields_or_logs(values,key):
    data=values[3].to_dict();data["authorization"][key]="DO_NOT_ECHO_SECRET"
    with pytest.raises(BulkError) as error:DestinationEvidence.from_dict(data)
    assert "DO_NOT_ECHO_SECRET" not in str(error.value)


def test_duplicate_untrusted_json_key_is_not_reflected_into_parser_diagnostics():
    with pytest.raises(BulkError) as error:
        DestinationEvidence.from_bytes(b'{"DO_NOT_ECHO_SECRET":1,"DO_NOT_ECHO_SECRET":2}')
    assert "DO_NOT_ECHO_SECRET" not in str(error.value)


@pytest.mark.parametrize("field,value",[("issuer","https://user:secret@example.invalid"),("issuer_version","1.0"),("as_of","yesterday"),("target_sha256","0"*63)])
def test_malformed_trusted_context_rejected(values,field,value):
    with pytest.raises((BulkError,ValueError)):replace(context(values[3]),**{field:value})


def test_source_context_is_exact_explicit_and_not_a_currentness_grant(values):
    ts=values[1];data=ts.to_dict()
    source=SourceVerificationContext(selection_sha256=ts.sha256,source_sha256=fingerprint(data["source"]),
        verification_context_sha256=data["verification"]["context_sha256"],commit=data["source"]["commit"],tree=data["source"]["tree"],
        issuer="fixture.source",issuer_version="1.0.0",as_of="2030-01-01T12:00:00Z")
    assert not hasattr(source,"ready") and not hasattr(source,"verified")
    with pytest.raises(BulkError):replace(source,commit="bad")
    with pytest.raises(ValueError):replace(source,as_of="2030-02-30T00:00:00Z")


def test_unsupported_positive_status_and_wrong_evidence_stage_rejected(values):
    with pytest.raises(BulkError):AuthorityResult("verified",h("fake"))
    for provider in [UnavailableAuthority(),SyntheticAuthority()]:
        with pytest.raises(BulkError):provider.verify(values[-1],None)


@pytest.mark.parametrize("mutation",["missing-revocation-context","reverse-expiry","invalid-time"])
def test_inconsistent_authority_observation_shape_rejected(values,mutation):
    data=values[3].to_dict()
    if mutation=="missing-revocation-context":data["authorization"]["revocation"]["checked_at"]=None
    elif mutation=="reverse-expiry":data["authorization"]["expires_at"]="2029-12-31T00:00:00Z"
    else:data["authorization"]["verified_at"]="2030-99-99T00:00:00Z"
    with pytest.raises(BulkError):DestinationEvidence.from_dict(data)
