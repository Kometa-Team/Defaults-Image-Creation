"""M3 metadata/adversarial tests: no image generation or production activation."""

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from create_defaults.bulk.common import BulkError, Conflict, canonical, fingerprint
from create_defaults.bulk.contracts import (
    Contract, ContractApproval, ContractStore, ExceptionRequest, Identity,
    RegistrySnapshot, TrustedDecision,
)
from create_defaults.bulk.contracts.adoption.models import HistoricalOutput, read_canonical
from create_defaults.bulk.contracts.playlist import ExceptionState, PlaylistBoundary
from create_defaults.bulk.contracts.playlist.validation import (
    CONTRACT_SHA256, HERE, HISTORICAL_SHA256, M2_SHA256, REGISTRY_SHA256, VARIANT,
)
from create_defaults.bulk.contracts.registry import package_reference


@pytest.fixture(scope="module")
def boundary():
    return PlaylistBoundary.load(contract_sha256=CONTRACT_SHA256, registry_sha256=REGISTRY_SHA256,
                                 adoption_sha256=M2_SHA256)


@pytest.fixture
def proposal(tmp_path):
    root = tmp_path / "sources"
    path = root / "logos_playlist" / "Brand.png"
    path.parent.mkdir(parents=True)
    # Intentionally NOT a PNG: M3 checks references/bytes, never claims pixels
    # or transparency were inspected. Actual decoding/alpha validation is M4.
    path.write_bytes(b"synthetic metadata test, not image data")
    content = {"display_name": "Brand", "source": {"path": "logos_playlist/Brand.png", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
               "background_proposal": "#123456", "content_type": VARIANT}
    identity = Identity.from_dict({"schema_version": 1, "kind": "item-identity", "id": "playlist." + "1" * 32,
        "category": "Playlist", "display_name": "Brand", "rendered_caption": "TIMELINE ORDER", "source": content["source"],
        "local_path": "defaults-en/playlist/Brand (Timeline Order).jpg", "public_path": "playlist/Brand (Timeline Order).jpg", "semantic_member": None})
    return root, content, identity


def exception(boundary, content, identity, *, treatment="SOURCE_PRESERVING", intentional=False):
    return ExceptionRequest.from_dict({"schema_version": 1, "kind": "logo-exception-request", "id": "request.synthetic", "revision": 1,
        "provenance": {"role": "submitter", "actor": "synthetic-contributor", "source": "synthetic-test", "evidence_sha256": "a" * 64},
        "context": boundary.request_context(identity, content), "requested_treatment": treatment,
        "intentional_background": intentional, "justification": "Retain this brand's approved original colour treatment."})


def proposed_definition(boundary, content, identity):
    d = read_canonical(boundary.records[0].to_dict()["effective_definition_json"])
    i = identity.to_dict()
    d.update(id=i["id"], display_name=i["display_name"], source={"kind": "authored", "path": "catalog/proposed-playlist.yml", "line": None, "row_sha256": None},
        layout={"kind": "fixed", "measurement": None}, applicability={"en": {"status": "applicable", "reason": "Prospective English metadata only"}},
        color_assignment={"id": i["id"] + ".background", "origin": "independent", "parent": None, "relationship": None, "exception": None},
        output={"directory": "playlist", "filename": "Brand (Timeline Order).jpg", "remote_paths": {"en": i["public_path"]}})
    d["composer"].update(logo=content["source"]["path"], base_color=content["background_proposal"], out_name="Brand (Timeline Order)")
    return d


def test_all_nine_current_items_and_complete_design_are_compatible_without_rendering(boundary, monkeypatch):
    def prohibited(*a, **kw):
        pytest.fail("M3 invoked image processing, workers, live state or network")
    import PIL.Image
    import requests
    import create_defaults.create_poster as poster
    from create_defaults.bulk import workers, state, overlays
    monkeypatch.setattr(PIL.Image, "open", prohibited)
    monkeypatch.setattr(poster, "create_poster", prohibited)
    monkeypatch.setattr(overlays, "render", prohibited)
    monkeypatch.setattr(workers.PersistentWorkers, "__init__", prohibited)
    monkeypatch.setattr(state.Store, "__init__", prohibited)
    monkeypatch.setattr(requests.Session, "request", prohibited)
    report = boundary.audit()
    assert report["compatible"] and report["membership_exact"]
    assert report["M2_total_outputs"] == 14079
    assert len(report["items"]) == 9
    assert all(item["outcome"] == "compatible" for item in report["items"])
    expected = json.loads((HERE / "compatibility-v1.json").read_bytes())
    assert canonical(report) == canonical(expected)
    assert not report["production_enforcement"] and not report["publication_authorized"]
    assert not report["phase3_translation_gate"] and not report["new_asset_pixels_inspected"]
    assert report["locked_design"]["typography"]["size"] == 154
    assert report["locked_design"]["logo"]["treatment"] == "WHITE_ONLY"
    assert fingerprint([r.to_dict() for r in boundary.records]) == HISTORICAL_SHA256


@pytest.mark.parametrize("field,value", [
    ("font", "fonts/Comfortaa-Medium.ttf"), ("font_size", 153), ("font_size", 100),
    ("logo_offset", -199), ("logo_resize", 1599), ("text_offset", 449),
    ("font_color", "#000000"), ("gradient", 0), ("gradient", 99),
    ("border", True), ("border_width", 0), ("border_color", "#000000"),
    ("white_wash", False), ("base_color", "#123456"), ("clean", False),
    ("avg_color", True), ("dom_color", True), ("avg_color_image", "transparent.png"),
    ("base_color", "#2b8f40"), ("logo_offset", "-200"),
])
def test_historical_raw_and_expanded_style_overrides_fail(boundary, field, value):
    r = boundary.records[0].to_dict()
    d, job = read_canonical(r["effective_definition_json"]), read_canonical(r["job_json"])
    # Attack actual expanded context even if a caller supplies the original job.
    d["composer"][field] = value
    with pytest.raises(BulkError):
        boundary.validate_existing(r["identity"]["id"], d, job)
    d = read_canonical(r["effective_definition_json"])
    job["raw_parameters"][field] = value
    # In particular gradient=99 normalizes back to 1, but raw intent must fail.
    with pytest.raises(BulkError):
        boundary.validate_existing(r["identity"]["id"], d, job)


@pytest.mark.parametrize("mutate", [
    lambda d: d["caption"].update(case="lower"),
    lambda d: d["caption"].update(key="key_names.RELEASE_ORDER"),
    lambda d: d["caption"].update(fallback={"approved": True}),
    lambda d: d["layout"]["measurement"].update(point_size=100),
    lambda d: d["layout"]["measurement"].update(evidence_sha256="b" * 64),
    lambda d: d["overrides"].append({"language": "en", "changes": {"composer": {"white_wash": False}}}),
    lambda d: d["overrides"].append({"language": "fr", "changes": {"composer": {"font_size": 100}}}),
    lambda d: d.update(category="Studio"),
    lambda d: d.update(extends="legacy-poster"),
    lambda d: d["composer"].update(format="PNG"),
    lambda d: d["composer"].update(approved=True),
    lambda d: d["output"]["remote_paths"].update(en="studio/forged.jpg"),
    lambda d: d["dependencies"].append({"poster_id": "other", "input": "logo"}),
    lambda d: d.update(languages=["en", "fr"]),
])
def test_inherited_nested_caption_paths_and_measurement_bypasses_fail(boundary, mutate):
    r = boundary.records[0].to_dict()
    d, job = read_canonical(r["effective_definition_json"]), read_canonical(r["job_json"])
    mutate(d)
    with pytest.raises(BulkError):
        boundary.validate_existing(r["identity"]["id"], d, job)


@pytest.mark.parametrize("mutate", [
    lambda j: j["inputs"][0].update(sha256="0" * 64),
    lambda j: j["inputs"][1].update(sha256="0" * 64),
    lambda j: j["inputs"][1].update(path="logos_playlist/arrowverse.png"),
    lambda j: j.update(poster_id="playlist.somebody-else"),
    lambda j: j.update(definition_fingerprint="0" * 64),
    lambda j: j.update(render_fingerprint="0" * 64),
    lambda j: j.update(dependencies=[{"job_id": "forged", "input": "logo", "sha256": "0" * 64, "render_fingerprint": "0" * 64}]),
    lambda j: j["translation"]["trace"][0].update(key="unapproved.KEY"),
    lambda j: j["translation"]["trace"][0].update(source_sha256="0" * 64),
    lambda j: j.update(publication_authorized=True),
    lambda j: j["parameters"].update(text="Timeline Order"),
])
def test_tampered_material_and_dependency_context_fail_even_with_same_output_bytes(boundary, mutate):
    r = boundary.records[0].to_dict()
    d, job = read_canonical(r["effective_definition_json"]), read_canonical(r["job_json"])
    mutate(job)
    with pytest.raises(BulkError):
        boundary.validate_existing(r["identity"]["id"], d, job)


@pytest.mark.parametrize("extra", [
    {"font": "fonts/Other.ttf"}, {"font_size": 100}, {"weight": 900},
    {"logo_offset": 0}, {"logo_resize": 2000}, {"text_offset": 0},
    {"caption": {"case": "lower"}}, {"caption_key": "key_names.WATCH_ORDER"},
    {"content_type": "release-order"}, {"white_wash": False},
    {"gradient": 0}, {"border": True}, {"width": 1000}, {"format": "PNG"},
    {"background": "#123456"}, {"base_color": "#123456"},
    {"schema_version": 2}, {"contract_version": "2.0.0"}, {"variant": "colored"},
    {"destination": "Kometa-Team/Default-Images/master"}, {"approved": True},
    {"reviewer": "bullmoose20"}, {"approval_state": "approved"},
    {"exception": {"requested_treatment": "SOURCE_PRESERVING", "approved": True}},
    {"source": {"path": "logos_playlist/Brand.png", "sha256": "a" * 64, "white_wash": False}},
    {"source": {"path": "logos_playlist/Brand.png", "sha256": "a" * 64, "approved": True}},
    {"source": {"path": "../Brand.png", "sha256": "a" * 64}},
    {"display_name": {"name": "Brand", "font_size": 100}},
    {"background_proposal": {"color": "#123456", "reviewer": "bullmoose20"}},
    {"background_proposal": "#123456\n"},
])
def test_contributor_content_cannot_smuggle_locked_values_or_authority(boundary, proposal, extra):
    root, content, _ = proposal
    content.update(extra)
    with pytest.raises(BulkError):
        boundary.validate_submission(content, source_root=root)


def test_standard_metadata_is_pending_and_does_not_prove_png_transparency(boundary, proposal):
    root, content, identity = proposal
    result = boundary.validate_submission(content, source_root=root, identity=identity)
    assert result.conditions == (ExceptionState.DEFAULT_SELECTED,)
    assert result.default_treatment == "WHITE_ONLY"
    assert result.background_status == "pending_maintainer_approval"
    assert result.asset_status == "reference_hash_verified_pixels_not_inspected"
    assert result.publication_authorized is False
    assert result.to_dict()["content"] == content
    assert boundary.validate_proposed_definition(identity, content, proposed_definition(boundary, content, identity), source_root=root) == result
    content["background_proposal"] = "#000000"
    assert result.to_dict()["content"]["background_proposal"] == "#123456"
    with pytest.raises(FrozenInstanceError):
        result.publication_authorized = True


@pytest.mark.parametrize("field", ["display_name", "source", "background_proposal"])
def test_missing_mandatory_proposed_content(boundary, proposal, field):
    root, content, _ = proposal
    content.pop(field)
    with pytest.raises(BulkError):
        boundary.validate_submission(content, source_root=root)


def test_real_reference_hash_and_exact_case_are_required(boundary, proposal):
    root, content, _ = proposal
    content["source"]["sha256"] = "0" * 64
    with pytest.raises(BulkError):
        boundary.validate_submission(content, source_root=root)
    content["source"]["path"] = "logos_playlist/brand.png"
    with pytest.raises(BulkError):
        boundary.validate_submission(content, source_root=root)
    content["source"]["path"] = "logos_playlist/Poke\u0301mon.png"
    with pytest.raises(BulkError):
        boundary.validate_submission(content, source_root=root)


def test_source_preserving_and_intentional_background_requests_are_only_pending(boundary, proposal):
    root, content, identity = proposal
    for treatment, intentional in [("SOURCE_PRESERVING", False), ("SOURCE_PRESERVING", True), ("WHITE_ONLY", True)]:
        request = exception(boundary, content, identity, treatment=treatment, intentional=intentional)
        result = boundary.validate_submission(content, source_root=root, identity=identity, request=request)
        assert ExceptionState.PENDING in result.conditions
        assert (ExceptionState.REQUESTED in result.conditions) == (treatment == "SOURCE_PRESERVING")
        assert result.default_treatment == "WHITE_ONLY" and result.requested_treatment == treatment
        assert result.request_sha256 == request.sha256
        assert ExceptionState.APPROVED not in result.conditions
        assert ExceptionState.REJECTED not in result.conditions
        assert result.publication_authorized is False
        assert boundary.validate_proposed_definition(identity, content, proposed_definition(boundary, content, identity), source_root=root, request=request) == result


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(approved=True), lambda r: r.update(decision="approved"),
    lambda r: r.update(reviewer="bullmoose20"), lambda r: r["provenance"].update(role="maintainer"),
    lambda r: r.update(justification="   "), lambda r: r.update(requested_treatment="BOTH_REQUIRED"),
    lambda r: r["context"].update(variant="colored"),
    lambda r: r["context"]["package"].update(version="2.0.0"),
    lambda r: r["context"]["source"].update(sha256="0" * 64),
    lambda r: r["context"].update(material_context_sha256="0" * 64),
    lambda r: r["context"]["transformations"][0].update(sha256="0" * 64),
    lambda r: r["context"].update(identities=["playlist.forged"]),
])
def test_exception_requests_cannot_self_approve_or_transfer_context(boundary, proposal, mutate):
    root, content, identity = proposal
    value = exception(boundary, content, identity).to_dict()
    mutate(value)
    with pytest.raises(BulkError):
        request = ExceptionRequest.from_dict(value)
        boundary.validate_submission(content, source_root=root, identity=identity, request=request)


def test_changed_source_or_background_invalidates_request_even_with_same_filename(boundary, proposal):
    root, content, identity = proposal
    request = exception(boundary, content, identity)
    content["background_proposal"] = "#654321"
    with pytest.raises(BulkError):
        boundary.validate_submission(content, source_root=root, identity=identity, request=request)
    content["background_proposal"] = "#123456"
    (root / content["source"]["path"]).write_bytes(b"changed source")
    content["source"]["sha256"] = hashlib.sha256(b"changed source").hexdigest()
    i = identity.to_dict()
    i["source"] = content["source"]
    with pytest.raises(BulkError):
        boundary.validate_submission(content, source_root=root, identity=Identity.from_dict(i), request=request)


@pytest.mark.parametrize("mutate", [
    lambda d: d["composer"].update(font_size=100),
    lambda d: d["composer"].update(white_wash=False),
    lambda d: d["composer"].update(gradient=99),
    lambda d: d["composer"].update(border_width=0),
    lambda d: d["composer"].update(base_color="#654321"),
    lambda d: d["caption"].update(key="key_names.RELEASE_ORDER"),
    lambda d: d["caption"].update(case="lower"),
    lambda d: d["overrides"].append({"language": "en", "changes": {"composer": {"white_wash": False}}}),
    lambda d: d["overrides"].append({"language": "fr", "changes": {"caption": {"text": "forged"}}}),
    lambda d: d["output"].update(filename="Other.jpg"),
    lambda d: d["output"]["remote_paths"].update(fr="playlist/Brand.jpg"),
    lambda d: d["color_assignment"].update(origin="historical"),
    lambda d: d.update(category="Studio"),
    lambda d: d.update(approved=True),
    lambda d: d["layout"].update(kind="captured_fit", measurement={}),
])
def test_prospective_expanded_definition_rejects_normalization_and_inheritance_bypasses(boundary, proposal, mutate):
    root, content, identity = proposal
    d = proposed_definition(boundary, content, identity)
    mutate(d)
    with pytest.raises(BulkError):
        boundary.validate_proposed_definition(identity, content, d, source_root=root)


@pytest.mark.parametrize("change", ["duplicate_id", "exact", "case", "nfc", "wrong_category"])
def test_new_assigned_identity_collisions_fail(boundary, proposal, change):
    root, content, identity = proposal
    original = next(r.to_dict()["identity"] for r in boundary.records if "pok-mon" in r.to_dict()["identity"]["id"])
    value = identity.to_dict()
    if change == "duplicate_id":
        value["id"] = original["id"]
    elif change == "wrong_category":
        value["category"] = "Studio"
    else:
        value["local_path"] = original["local_path"]
        if change == "case": value["local_path"] = value["local_path"].upper()
        if change == "nfc": value["local_path"] = value["local_path"].replace("\u00e9", "e\u0301")
    with pytest.raises(BulkError):
        boundary.validate_submission(content, source_root=root, identity=Identity.from_dict(value))


def test_m2_membership_missing_extra_duplicate_and_association_tampering(boundary):
    for records in (boundary.records[:-1], boundary.records + (boundary.records[0],),
                    (boundary.records[1],) + boundary.records[1:]):
        with pytest.raises(BulkError):
            boundary.verify_membership(records)
    value = boundary.records[0].to_dict()
    value["fingerprints"]["dependencies"] = "0" * 64
    with pytest.raises(BulkError):
        HistoricalOutput.from_dict(value)
    value = boundary.records[0].to_dict()
    value["identity"]["id"] = boundary.records[1].to_dict()["identity"]["id"]
    with pytest.raises(BulkError):
        HistoricalOutput.from_dict(value)
    # A structurally valid fact cannot replace the frozen record either.
    value = boundary.records[0].to_dict()
    value["evidence"]["output_sha256"] = "0" * 64
    record = HistoricalOutput.from_dict(value)
    with pytest.raises(BulkError):
        boundary.verify_membership((record,) + boundary.records[1:])


@pytest.mark.parametrize("argument", ["contract_sha256", "registry_sha256", "adoption_sha256"])
def test_invalid_external_pins_fail(argument):
    pins = {"contract_sha256": CONTRACT_SHA256, "registry_sha256": REGISTRY_SHA256, "adoption_sha256": M2_SHA256}
    pins[argument] = "0" * 64
    with pytest.raises(BulkError):
        PlaylistBoundary.load(**pins)


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(schema_version=2), lambda d: d.update(schema_version=True),
    lambda d: d.update(category="Studio"),
    lambda d: d["variants"][0]["design"]["typography"]["asset"].update(sha256="0" * 64),
    lambda d: d["variants"][0]["design"]["logo"].update(treatment="SOURCE_PRESERVING"),
    lambda d: d["variants"][0]["design"]["fitting"].update(minimum_size=90),
    lambda d: d["variants"][0]["contributor_fields"].append("white_wash"),
    lambda d: d.update(publication_authorized=True),
])
def test_real_contract_changes_fail_schema_or_release_pin(boundary, mutate):
    value = boundary.contract.to_dict()
    mutate(value)
    with pytest.raises(BulkError):
        contract = Contract.from_dict(value)
        replace(boundary, contract=contract).verify_design()


def test_canonical_loading_immutability_and_package_e_store(boundary, tmp_path):
    encoded = json.dumps(boundary.contract.to_dict(), indent=4, ensure_ascii=False).encode()
    assert Contract.from_bytes(encoded).sha256 == CONTRACT_SHA256
    assert canonical(boundary.contract.to_dict()) == boundary.contract.encoded
    assert Contract.from_dict(dict(reversed(list(boundary.contract.to_dict().items())))) == boundary.contract
    with pytest.raises(FrozenInstanceError):
        boundary.contract.encoded = b"{}"
    store = ContractStore(tmp_path / "isolated-contract-state")
    assert store.pin(boundary.contract) == CONTRACT_SHA256
    assert store.pin(boundary.registry) == REGISTRY_SHA256
    assert store.pin(boundary.contract) == CONTRACT_SHA256
    modified = boundary.contract.to_dict()
    modified["variants"][0]["design"]["typography"]["size"] = 153
    with pytest.raises(Conflict):
        store.pin(Contract.from_dict(modified))
    reopened = ContractStore(tmp_path / "isolated-contract-state")
    assert reopened.read_object(CONTRACT_SHA256) == boundary.contract.encoded
    snapshot = RegistrySnapshot.load(reopened.read_object(REGISTRY_SHA256), expected_sha256=REGISTRY_SHA256,
        read_object=reopened.read_object, trusted_decisions={})
    with pytest.raises(BulkError):
        snapshot.select("Playlist", "poster", "1.0.0", CONTRACT_SHA256, VARIANT)


def test_approved_registry_handoff_requires_separately_attributed_decision(boundary):
    # Synthetic approval exists ONLY in this test. Never committed as a real
    # approval or used by the bundled review registry/CLI.
    approval = ContractApproval.from_dict({"schema_version": 1, "kind": "contract-approval", "id": "synthetic.approval", "revision": 1,
        "provenance": {"actor": "bullmoose20", "role": "maintainer", "source": "synthetic-test-only", "evidence_sha256": "a" * 64},
        "package": package_reference(boundary.contract), "decision": "approved", "scope": "category-contract"})
    with pytest.raises(BulkError):
        boundary.registry_for_decision(approval, trusted_decisions={})
    with pytest.raises(BulkError):
        boundary.registry_for_decision(approval, trusted_decisions={approval.sha256: {"actor": "bullmoose20", "evidence_sha256": "a" * 64}})
    trust = {approval.sha256: TrustedDecision("bullmoose20", "a" * 64)}
    registry = boundary.registry_for_decision(approval, trusted_decisions=trust)
    objects = {approval.sha256: approval.encoded, boundary.contract.sha256: boundary.contract.encoded}
    snapshot = RegistrySnapshot.load(registry.encoded, expected_sha256=registry.sha256, read_object=objects.__getitem__, trusted_decisions=trust)
    assert snapshot.select("Playlist", "poster", "1.0.0", CONTRACT_SHA256, VARIANT) == boundary.contract
    with pytest.raises(BulkError):
        TrustedDecision("synthetic-contributor", "a" * 64)
    rejected = approval.to_dict()
    rejected["decision"] = "rejected"
    record = ContractApproval.from_dict(rejected)
    with pytest.raises(BulkError):
        boundary.registry_for_decision(record, trusted_decisions={record.sha256: TrustedDecision("bullmoose20", "a" * 64)})


def test_factual_and_contract_metadata_cannot_authorize_publication(boundary):
    from create_defaults.bulk.operator_publication import authorize
    from create_defaults.bulk.library_sources import sealed
    manifest = sealed({"kind": "proposed-operator-membership", "members": [{}], "policy_sha256": fingerprint({}), "baseline": {}})
    for document in (boundary.contract, boundary.registry, boundary.records[0]):
        with pytest.raises(BulkError):
            authorize(manifest, {}, sealed(document.to_dict()))


def test_changed_expanded_context_appears_as_an_incompatible_audit_row(boundary, monkeypatch):
    from create_defaults.bulk.contracts.playlist import validation
    actual = validation.load_catalog(("Playlist",))
    first = actual[0].data
    first["composer"]["font_size"] = 100
    changed = validation.Definition.create(first)
    monkeypatch.setattr(validation, "load_catalog", lambda _: (changed,) + actual[1:])
    report = boundary.audit()
    assert report["compatible"] is False
    failed = [r for r in report["items"] if r["outcome"] == "incompatible"]
    assert len(failed) == 1 and failed[0]["identity"] == changed.id
    assert failed[0]["code"] == "playlist_material_mismatch"


def test_extra_definition_fails_complete_membership_not_a_partial_success(boundary, monkeypatch):
    from create_defaults.bulk.contracts.playlist import validation
    actual = validation.load_catalog(("Playlist",))
    value = actual[0].data
    value["id"] = "playlist.extra"
    monkeypatch.setattr(validation, "load_catalog", lambda _: actual + (validation.Definition.create(value),))
    report = boundary.audit()
    assert len(report["items"]) == 9
    assert report["membership_exact"] is False and report["compatible"] is False


def test_tampered_historical_extraction_fails_before_use(tmp_path):
    for name in ("contract-v1.json", "registry-v1.json", "historical-outputs-v1.json"):
        shutil.copyfile(HERE / name, tmp_path / name)
    path = tmp_path / "historical-outputs-v1.json"
    rows = json.loads(path.read_bytes())
    rows[0]["identity"]["source"]["sha256"] = "0" * 64
    path.write_bytes(canonical(rows))
    with pytest.raises(BulkError):
        PlaylistBoundary.load(contract_sha256=CONTRACT_SHA256, registry_sha256=REGISTRY_SHA256, adoption_sha256=M2_SHA256, root=tmp_path)


def test_deterministic_loading(boundary):
    other = PlaylistBoundary.load(contract_sha256=CONTRACT_SHA256, registry_sha256=REGISTRY_SHA256, adoption_sha256=M2_SHA256)
    assert other == boundary
