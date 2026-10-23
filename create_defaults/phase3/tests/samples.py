"""Metadata-only synthetic fixtures; no real repositories or credentials."""

from create_defaults.bulk.common import fingerprint
from create_defaults.bulk.contracts.language_policy import (
    LanguagePolicy, TranslationSelection, DestinationPolicy, DestinationEvidence,
    ValidationSubject, Phase3Attestation, reference, AuthorityContext,
)


def h(label):
    return fingerprint(label)


def repo(number, name):
    return {"host": "github.com", "repository_id": number, "owner_id": number+1000, "name": "Fixture/"+name}


def document(kind, stage, **fields):
    return dict(schema_version=1, kind=kind, stage=stage, id="fixture."+kind, version="1.0.0", **fields)


def bundle():
    contract = dict(category="Playlist", kind="poster", version="2.0.0", sha256=h("synthetic-contract-not-approved"))
    outputs = [dict(id="fixture.output", identity_sha256=h("stable-identity"),
                    local_path="playlist/Élan (Timeline Order).jpg", public_path="playlist/Élan (Timeline Order).jpg")]
    subject = ValidationSubject.from_dict(document("validation-subject", "subject", language="pt-br", contract=contract,
        variant="timeline", expanded_definition_sha256=h("expanded"), dependencies_sha256=h("dependencies"),
        review_context_sha256=h("review"), outputs=outputs, membership_sha256=fingerprint(outputs)))
    policy = LanguagePolicy.from_dict(document("language-policy", "policy", owner="fixture.maintainer",
        languages=[dict(code="en", aliases=[]), dict(code="pt-br", aliases=["pt_BR"]), dict(code="nb_NO", aliases=["nb-NO"])],
        coverage=[dict(package=contract, variant="timeline", languages=["pt-br"])],
        freshness="verified-commit-and-content-with-explicit-reverification", external_authority_required=True,
        non_english_requires_versioned_contract=True))
    source = dict(repository=repo(101,"Translations"), commit="a"*40, tree="b"*40,
        resources=[dict(path="defaults/pt-br.yml", blob_sha1="c"*40, sha256=h("pt-br-resource")),
                   dict(path="defaults/en.yml", blob_sha1="d"*40, sha256=h("en-resource"))])
    translation = TranslationSelection.from_dict(document("translation-selection", "selection", language_policy=reference(policy),
        subject=reference(subject), requested_language="pt_BR", language="pt-br", snapshot_sha256=h("snapshot"), source=source,
        values=[dict(resource_path="defaults/pt-br.yml", key="fixture.caption", source_value_sha256=h("English"), value_sha256=h("Português"))],
        verification=dict(status="verified", issuer="fixture.source", issuer_version="1.0.0", context_sha256=h("source-context"),
                          source_sha256=fingerprint(source), checked_at="2030-01-01T00:00:00Z", synthetic=True)))
    mapping = dict(language="pt-br", repository=repo(103,"UserArtwork"), branch="Main", root="posters/pt-br", paths=["playlist/Élan (Timeline Order).jpg"])
    destination_policy = DestinationPolicy.from_dict(document("destination-policy", "policy", owner="fixture.maintainer",
        language_policy=reference(policy), official_repository=repo(102,"Official"), official_language="en", english_user_owned_allowed=True,
        external_authority_required=True, mappings=[mapping]))
    target = dict(**mapping, baseline_commit="e"*40, baseline_tree="f"*40, inventory_sha256=h("inventory"))
    auth = dict(status="verified", principal="fixture.submitter", issuer="fixture.verifier", issuer_version="1.0.0",
        assertion_sha256=h("assertion"), verification_context_sha256=h("authority-context"), verified_at="2030-01-01T00:00:00Z",
        expires_at="2030-01-02T00:00:00Z", revocation=dict(status="clear", checked_at="2030-01-01T00:00:00Z", revision_sha256=h("revocations")), synthetic=True)
    destination = DestinationEvidence.from_dict(document("destination-evidence", "observation", subject=reference(subject),
        destination_policy=reference(destination_policy), target=target, authorization=auth))
    value = subject.to_dict()
    attestation = Phase3Attestation.from_dict(document("phase3-attestation", "informational", subject=reference(subject),
        language_policy=reference(policy), translation_selection=reference(translation), destination_policy=reference(destination_policy),
        destination_evidence=reference(destination), language="pt-br", contract=contract, output_ids=[o["id"] for o in outputs],
        **{k:value[k] for k in ["membership_sha256","expanded_definition_sha256","dependencies_sha256","review_context_sha256"]},
        authority_context_sha256=h("authority-context"), verification_context_sha256=h("source-context"), status="informational",
        publication_authorized=False, production_enforcement=False, ready=False, active=False))
    return policy, translation, destination_policy, destination, subject, attestation


def context(evidence):
    value=evidence.to_dict();auth=value["authorization"]
    return AuthorityContext(evidence_sha256=evidence.sha256, subject_sha256=value["subject"]["sha256"],
        destination_policy_sha256=value["destination_policy"]["sha256"], target_sha256=fingerprint(value["target"]),
        **{k:auth[k] for k in ("assertion_sha256","verification_context_sha256","principal","issuer","issuer_version")},
        as_of="2030-01-01T12:00:00Z")
