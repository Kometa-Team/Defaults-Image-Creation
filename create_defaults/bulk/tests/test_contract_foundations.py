"""M1 uses synthetic JSON only: no artwork, renderer, catalog or live state."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
import sqlite3

import pytest

from create_defaults.bulk.common import BulkError, Conflict, canonical, fingerprint
from create_defaults.bulk.contracts import (
    AdoptionRecord, Contract, ContractApproval, ContractStore, ExceptionDecision,
    ExceptionRequest, Identity, PreviewManifest, RegistryDocument, RegistrySnapshot,
    SubmitterConfirmation, TrustedDecision, ValidationAttestation,
    check_namespace, read_document,
)
from create_defaults.bulk.contracts.models import decode_json
from create_defaults.bulk.contracts.registry import package_reference
from create_defaults.bulk.state import MIGRATIONS, Store


H = "a" * 64
OTHER = "b" * 64
ACTOR = "bullmoose20"


def provenance(role="maintainer", actor=ACTOR):
    return {"actor": actor, "role": role, "source": "synthetic-test-decision", "evidence_sha256": H}


def package():
    # Deliberately synthetic, not a real Playlist adoption or production contract.
    return {
        "schema_version": 1, "category": "Playlist", "kind": "poster", "version": "1.0.0",
        "owner": ACTOR, "provenance": provenance(),
        "naming": {"new_names": "NFC", "historical_names": "exact", "collision_key": "NFC+casefold", "identity": "persisted"},
        "variants": [{"id": "example", "contributor_fields": ["display_name", "source", "separate_white_source", "content_type", "background_proposal", "filename_proposal"], "exception_refs": [], "design": {
            "typography": {"asset": {"path": "fonts/Example.ttf", "sha256": H}, "family": "Synthetic", "weight": 400, "size": 154, "color": "#FFFFFF"},
            "fitting": {"mode": "captured_fit", "measurement_sha256": H, "width": 1600, "height": 1000, "minimum_size": 100, "maximum_size": 154},
            "caption": {"requirement": "required", "case": "upper", "languages": ["en"], "registry_sha256": H, "content_types": [{"id": "example-order", "mode": "translation", "value": "example.KEY", "template": "{value}"}]},
            "logo": {"treatment": "WHITE_ONLY", "source_preserving_exception": True, "transparent_png_default": True, "intentional_background_exception": True, "transformation": {"id": "existing-white-wash", "sha256": H}, "historical_acceptance_refs": []},
            "geometry": {"logo_width": 1600, "logo_offset": -200, "caption_offset": 450, "caption_width": 1900, "caption_height": 1000},
            "background": {"mode": "assigned", "assignments_sha256": H, "proposals_allowed": True},
            "effects": {"gradient": 1, "border": False, "border_color": "#000000", "border_width": 0, "clean": False},
            "output": {"width": 2000, "height": 3000, "format": "JPEG", "mode": "RGB", "quality": 100, "subsampling": 0, "encoding_sha256": H},
        }}],
    }


def overlay_package():
    value = package()
    value.update(category="Overlays", kind="overlay")
    value["variants"] = [{"id": "color", "contributor_fields": ["display_name", "source"], "exception_refs": [], "design": {
        "treatment": "SOURCE_PRESERVING", "source_branch": "original-color", "trim": True,
        "sizes": {"standard": {"width": 285, "height": 85}, "bigger": {"width": 440, "height": 100}},
        "rounding": "half-up", "resampling": "Lanczos", "format": "PNG", "mode": "RGBA", "color_space": "sRGB",
        "compression": 9, "preserve_basename": True, "transformation": {"id": "existing-overlay", "sha256": H},
    }}]
    return value


def approval(contract, *, actor=ACTOR, role="maintainer"):
    return {"schema_version": 1, "kind": "contract-approval", "id": "approval.example", "revision": 1,
            "provenance": provenance(role, actor), "package": package_reference(contract), "decision": "approved", "scope": "category-contract"}


def registry_fixture():
    contract = Contract.from_dict(package())
    decision = ContractApproval.from_dict(approval(contract))
    registry = RegistryDocument.from_dict({"schema_version": 1, "kind": "category-contract-registry", "id": "registry.example", "version": "1.0.0", "owner": ACTOR, "provenance": provenance(),
        "entries": [{"package": package_reference(contract), "variants": ["example"], "approval_sha256": decision.sha256, "adoption_sha256": []}]})
    objects = {c.sha256: c.encoded for c in (contract, decision)}
    trust = {decision.sha256: TrustedDecision(ACTOR, H)}
    return registry, contract, decision, objects, trust


def identity(identity="playlist.existing-id", name="Pok\u00e9mon", source="logos/X-men.png", member=None):
    return Identity.from_dict({"schema_version": 1, "kind": "item-identity", "id": identity, "category": "Playlist", "display_name": name,
        "rendered_caption": "TIMELINE ORDER", "source": {"path": source, "sha256": H},
        "local_path": f"defaults-en/playlist/{name}.jpg", "public_path": f"playlist/{name}.jpg", "semantic_member": member})


def test_canonical_hash_matches_package_e_and_is_detached():
    value = package()
    contract = Contract.from_dict(value)
    assert contract.encoded == canonical(value)
    assert contract.sha256 == fingerprint(value)
    assert Contract.from_bytes(json.dumps(value, indent=4).encode()).sha256 == contract.sha256
    reordered = dict(reversed(list(value.items())))
    assert Contract.from_dict(reordered).sha256 == contract.sha256
    value["owner"] = "injected"
    detached = contract.to_dict()
    detached["variants"][0]["design"]["typography"]["size"] = 1
    assert contract.to_dict()["owner"] == ACTOR
    assert contract.to_dict()["variants"][0]["design"]["typography"]["size"] == 154
    with pytest.raises(FrozenInstanceError):
        contract.encoded = b"{}"
    # Fixed cross-platform Unicode vector, including Package E ASCII escaping.
    value = {"path": "Pok\u00e9mon.png", "a": 1}
    assert canonical(value) == b'{"a":1,"path":"Pok\\u00e9mon.png"}'
    assert fingerprint(value) == hashlib.sha256(b'{"a":1,"path":"Pok\\u00e9mon.png"}').hexdigest()


@pytest.mark.parametrize("encoded", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":"\\ud800"}', b'\xff', b'{', b'[' * 50 + b'0' + b']' * 50])
def test_strict_json_parser(encoded):
    with pytest.raises(BulkError):
        decode_json(encoded)


@pytest.mark.parametrize("mutate", [
    lambda v: v.pop("owner"), lambda v: v.update(schema_version=2),
    lambda v: v.update(schema_version=True), lambda v: v.update(version="latest"),
    lambda v: v.update(version="01.0.0"), lambda v: v.update(approved=True),
    lambda v: v.update(extends="self"), lambda v: v["variants"][0].update(extends="example"),
    lambda v: v["variants"].append(deepcopy(v["variants"][0])),
    lambda v: v["variants"][0]["design"]["typography"].update(fallback="system-font"),
    lambda v: v["variants"][0]["contributor_fields"].append("font_size"),
    lambda v: v["variants"][0]["design"]["background"].update(proposals_allowed=False),
    lambda v: v["provenance"].update(actor="contributor"),
    lambda v: v["variants"][0]["design"]["typography"].update(size=True),
    lambda v: v["variants"][0]["design"]["fitting"].update(maximum_size=120),
])
def test_strict_contract_rejects_malformed_or_permission_widening_content(mutate):
    value = package()
    mutate(value)
    with pytest.raises(BulkError):
        Contract.from_dict(value)


@pytest.mark.parametrize("content", [
    {"font_size": 80}, {"composer": {"white_wash": False}},
    {"source": {"path": "logo.png", "sha256": H, "white_wash": False}},
    {"source": {"path": "logo.png", "sha256": H, "approved": True}},
    {"source": {"path": "../logo.png", "sha256": H}},
    {"display_name": {"font": "other.ttf"}}, {"background_proposal": {"color": "#123456", "reviewer": ACTOR}},
    {"background_proposal": "#123456; white_wash=false"}, {"filename_proposal": {"value": "x.jpg", "role": "maintainer"}},
    {"variant": "example"}, {"contract": {"version": "2.0.0"}},
    {"approved": True}, {"exception_refs": [H]}, {"content_type": "injected-key"},
    {"source": {"path": "logos/Poke\u0301mon.png", "sha256": H}},
])
def test_contributor_cannot_smuggle_style_authority_or_paths(content):
    contract = Contract.from_dict(package())
    before = contract.sha256
    with pytest.raises(BulkError):
        contract.validate_content("example", content)
    assert contract.sha256 == before


def test_content_fields_are_requests_and_never_mutate_style():
    contract = Contract.from_dict(package())
    content = {"display_name": "Brand", "source": {"path": "logos/Pok\u00e9mon.png", "sha256": H}, "content_type": "example-order", "background_proposal": "#123456", "filename_proposal": "Brand (Order).jpg"}
    result = contract.validate_content("example", content)
    assert result == content
    result["background_proposal"] = "#000000"
    assert contract.to_dict()["variants"][0]["design"]["logo"]["treatment"] == "WHITE_ONLY"
    with pytest.raises(BulkError):
        contract.validate_content("new-variant", {})


@pytest.mark.parametrize("treatment", ["WHITE_ONLY", "SOURCE_PRESERVING", "BOTH_REQUIRED", "COLOR_ONLY", "SPECIAL", "NOT_APPLICABLE"])
def test_logo_policy_representation_without_processing(treatment):
    value = package()
    value["variants"][0]["design"]["logo"]["treatment"] = treatment
    assert Contract.from_dict(value).to_dict()["variants"][0]["design"]["logo"]["treatment"] == treatment


@pytest.mark.parametrize("mutation", [
    lambda v: v["variants"][0]["design"].update(treatment="WHITE_ONLY"),
    lambda v: v["variants"][0]["design"].update(typography={}),
    lambda v: v["variants"][0]["contributor_fields"].append("content_type"),
    lambda v: v.update(category="Playlist"),
])
def test_overlay_contract_cannot_inherit_poster_controls(mutation):
    value = overlay_package()
    Contract.from_dict(value).validate_content("color", {"source": {"path": "network/white/Logo.png", "sha256": H}})
    mutation(value)
    with pytest.raises(BulkError):
        Contract.from_dict(value)


def test_exact_unicode_identity_names_and_independent_fields():
    item = identity()
    item.require_new_names()
    copy = item.to_dict()
    copy.update(display_name="Renamed display", local_path="local/A.C.G.T..jpg", public_path="studio/A.C.G.T..jpg")
    assert Identity.from_dict(copy).to_dict()["id"] == item.to_dict()["id"]
    assert item.to_dict()["source"]["path"] == "logos/X-men.png"
    decomposed = identity(name="Poke\u0301mon")
    assert "e\u0301" in decomposed.to_dict()["local_path"]  # historical literal retained
    with pytest.raises(BulkError, match="NFC"):
        decomposed.require_new_names()
    check_namespace([identity("one", "First"), identity("two", "Second")])  # shared source allowed


@pytest.mark.parametrize("other", [
    lambda: identity("playlist.existing-id", "Different"),
    lambda: identity("other", "Pok\u00e9mon"),
    lambda: identity("other", "POK\u00c9MON"),
    lambda: identity("other", "Poke\u0301mon"),
])
def test_output_and_identity_collisions_on_windows_and_linux(other):
    with pytest.raises(BulkError):
        check_namespace([identity(), other()])


def test_duplicate_semantic_members_rejected_without_changing_ids():
    member = {"family_id": "family.existing", "key": "year:2020"}
    with pytest.raises(BulkError):
        check_namespace([identity("one", "First", member=member), identity("two", "Second", member=member)])


def test_registry_pins_complete_membership_and_external_authority():
    registry, contract, decision, objects, trust = registry_fixture()
    snapshot = RegistrySnapshot.load(registry.encoded, expected_sha256=registry.sha256, read_object=objects.__getitem__, trusted_decisions=trust)
    assert snapshot.select("Playlist", "poster", "1.0.0", contract.sha256, "example") == contract
    for version, checksum, variant in [("latest", contract.sha256, "example"), ("1.0.0", OTHER, "example"), ("1.0.0", contract.sha256, "new")]:
        with pytest.raises(BulkError):
            snapshot.select("Playlist", "poster", version, checksum, variant)
    with pytest.raises(BulkError, match="decision"):
        RegistrySnapshot.load(registry.encoded, expected_sha256=registry.sha256, read_object=objects.__getitem__, trusted_decisions={})
    with pytest.raises(BulkError, match="decision"):
        RegistrySnapshot.load(registry.encoded, expected_sha256=registry.sha256, read_object=objects.__getitem__, trusted_decisions={decision.sha256: TrustedDecision(ACTOR, OTHER)})
    with pytest.raises(BulkError):
        TrustedDecision("contributor", H)


def test_registry_tampering_and_stale_approval_do_not_transfer():
    registry, contract, decision, objects, trust = registry_fixture()
    changed = contract.to_dict()
    changed["variants"][0]["design"]["typography"]["size"] = 140
    new = Contract.from_dict(changed)
    objects[contract.sha256] = new.encoded
    with pytest.raises(BulkError, match="pin"):
        RegistrySnapshot.load(registry.encoded, expected_sha256=registry.sha256, read_object=objects.__getitem__, trusted_decisions=trust)
    objects[new.sha256] = new.encoded
    changed_registry = registry.to_dict()
    changed_registry["entries"][0]["package"] = package_reference(new)
    new_registry = RegistryDocument.from_dict(changed_registry)
    with pytest.raises(BulkError, match="selected pin"):
        RegistrySnapshot.load(new_registry.encoded, expected_sha256=registry.sha256, read_object=objects.__getitem__, trusted_decisions=trust)
    with pytest.raises(BulkError, match="decision"):
        RegistrySnapshot.load(new_registry.encoded, expected_sha256=new_registry.sha256, read_object=objects.__getitem__, trusted_decisions=trust)


@pytest.mark.parametrize("mutate", [
    lambda v: v.update(approved=True), lambda v: v.update(schema_version=2),
    lambda v: v["entries"].append(deepcopy(v["entries"][0])),
    lambda v: v["entries"][0]["package"].update(version="latest"),
    lambda v: v["entries"][0]["package"].update(sha256="../package"),
    lambda v: v["entries"][0].pop("approval_sha256"),
])
def test_malformed_registry_entries(mutate):
    registry, *_ = registry_fixture()
    value = registry.to_dict()
    mutate(value)
    with pytest.raises(BulkError):
        RegistryDocument.from_dict(value)


def test_registry_rejects_incomplete_variants_and_forged_named_maintainer():
    registry, contract, decision, objects, trust = registry_fixture()
    value = registry.to_dict()
    value["entries"][0]["variants"] = ["invented"]
    wrong = RegistryDocument.from_dict(value)
    with pytest.raises(BulkError, match="complete"):
        RegistrySnapshot.load(wrong.encoded, expected_sha256=wrong.sha256, read_object=objects.__getitem__, trusted_decisions=trust)
    # A self-declared allowed name does not match the actual external attribution.
    forged = ContractApproval.from_dict(approval(contract, actor="YozoraXCII"))
    objects[forged.sha256] = forged.encoded
    value = registry.to_dict()
    value["entries"][0]["approval_sha256"] = forged.sha256
    wrong = RegistryDocument.from_dict(value)
    with pytest.raises(BulkError, match="decision"):
        RegistrySnapshot.load(wrong.encoded, expected_sha256=wrong.sha256, read_object=objects.__getitem__, trusted_decisions={forged.sha256: TrustedDecision(ACTOR, H)})


def record_fixtures():
    contract = Contract.from_dict(package())
    context = {"package": package_reference(contract), "variant": "example", "identities": ["playlist.existing-id"], "source": {"path": "logos/Pok\u00e9mon.png", "sha256": H}, "material_context_sha256": H, "transformations": [{"id": "existing-white-wash", "sha256": H}]}
    base = {"schema_version": 1, "revision": 1}
    panel = {"artifact_sha256": H, "worker_receipt_sha256": H, "validation": "blocked"}
    return [
        (ContractApproval, approval(contract)),
        (AdoptionRecord, base | {"kind": "contract-adoption", "id": "adoption.example", "provenance": provenance(), "package": package_reference(contract), "basis_registry_sha256": H, "membership_sha256": H, "previous_validation_sha256": H, "compatibility_sha256": H}),
        (ExceptionRequest, base | {"kind": "logo-exception-request", "id": "request.example", "provenance": provenance("submitter", "contributor"), "context": context, "justification": "Intentional brand treatment", "requested_treatment": "SOURCE_PRESERVING", "intentional_background": True}),
        (PreviewManifest, base | {"kind": "logo-preview-manifest", "id": "preview.example", "provenance": provenance("validator", "worker"), "context": context, "request_sha256": H, "default": panel, "requested": panel | {"validation": "review_required"}, "members": [{"id": "source", "treatment": "source", "artifact_sha256": H, "worker_receipt_sha256": H}], "comparison_evidence_sha256": H}),
        (SubmitterConfirmation, base | {"kind": "submitter-confirmation", "id": "confirmation.example", "provenance": provenance("submitter", "contributor"), "context": context, "request_sha256": H, "preview_sha256": H, "membership_sha256": H, "decision": "approved"}),
        (ExceptionDecision, base | {"kind": "maintainer-exception-decision", "id": "exception.example", "provenance": provenance(), "context": context, "request_sha256": H, "preview_sha256": H, "confirmation_sha256": H, "membership_sha256": H, "selected_treatment": "SOURCE_PRESERVING", "intentional_background": True, "decision": "approved"}),
        (ValidationAttestation, base | {"kind": "effective-job-attestation", "id": "attestation.example", "provenance": provenance("validator", "worker"), "context": context, "job_sha256": H, "dependencies_sha256": H, "resolved_rules_sha256": H, "diagnostics_sha256": H, "adoption_sha256": H, "exception_sha256": [], "worker_receipt_sha256": H}),
    ]


def test_all_typed_records_roundtrip_without_authority_or_publication_flags():
    for cls, value in record_fixtures():
        record = cls.from_dict(value)
        assert type(read_document(record.encoded, "record")) is cls
        assert read_document(record.encoded, "record").sha256 == record.sha256
        for field in ("staging_authorized", "merge", "publication_approved"):
            bad = deepcopy(value)
            bad[field] = True
            with pytest.raises(BulkError):
                cls.from_dict(bad)
        bad = deepcopy(value)
        bad["provenance"]["role"] = "submitter" if value["provenance"]["role"] != "submitter" else "maintainer"
        with pytest.raises(BulkError):
            cls.from_dict(bad)
    with pytest.raises(BulkError):
        ContractApproval.from_dict(record_fixtures()[4][1])  # submitter confirmation cannot be replayed
    with pytest.raises(BulkError):
        read_document(canonical({"kind": "operator-maintainer-decision"}), "record")


def test_mandatory_fields_cannot_disappear_in_any_document_or_record():
    registry, *_ = registry_fixture()
    fixtures = [(Contract, package()), (Contract, overlay_package()), (RegistryDocument, registry.to_dict()), (Identity, identity().to_dict()), *record_fixtures()]
    for cls, value in fixtures:
        for field in value:
            bad = deepcopy(value)
            del bad[field]
            with pytest.raises(BulkError):
                cls.from_dict(bad)


def test_store_immutable_versions_records_restart_and_export(tmp_path):
    root = tmp_path / "isolated-contracts"
    store = ContractStore(root)
    contract = Contract.from_dict(package())
    assert store.pin(contract) == contract.sha256
    assert store.pin(contract) == contract.sha256
    changed = contract.to_dict()
    changed["variants"][0]["design"]["typography"]["size"] = 140
    with pytest.raises(Conflict):
        store.pin(Contract.from_dict(changed))
    changed["version"] = "2.0.0"
    new = Contract.from_dict(changed)
    store.pin(new)
    registry, *_ = registry_fixture()
    store.pin(registry)
    changed_registry = registry.to_dict()
    changed_registry["entries"] = []
    with pytest.raises(Conflict):
        store.pin(RegistryDocument.from_dict(changed_registry))
    record = ContractApproval.from_dict(approval(contract))
    store.append(record, expected_revision=0)
    next_value = record.to_dict() | {"revision": 2, "decision": "rejected"}
    store.append(ContractApproval.from_dict(next_value), expected_revision=1)
    with pytest.raises(Conflict):
        store.append(ContractApproval.from_dict(next_value), expected_revision=1)
    reopened = ContractStore(root)
    assert Contract.from_bytes(reopened.read_object(contract.sha256)) == contract
    assert reopened.read_record(record.to_dict()["id"], 1) == record
    assert reopened.read_record(record.to_dict()["id"], 2).to_dict()["decision"] == "rejected"
    with reopened._store.connection() as db:
        for table in ("contract_versions", "contract_records", "events"):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(f"DELETE FROM {table}")


def test_failed_transaction_leaves_no_reference_or_event_and_can_retry(tmp_path, monkeypatch):
    root = tmp_path / "isolated-contracts"
    store = ContractStore(root)
    contract = Contract.from_dict(package())
    event = store._store.event
    def failed_event(*args):
        event(*args)
        raise RuntimeError("simulated interrupted transaction")
    monkeypatch.setattr(store._store, "event", failed_event)
    with pytest.raises(RuntimeError):
        store.pin(contract)
    with store._store.connection() as db:
        assert db.execute("SELECT count(*) FROM contract_versions").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM events").fetchone()[0] == 0
    assert store.read_object(contract.sha256) == contract.encoded  # harmless orphan
    reopened = ContractStore(root)
    reopened.pin(contract)
    record = ContractApproval.from_dict(approval(contract))
    monkeypatch.setattr(reopened._store, "event", failed_event)
    with pytest.raises(RuntimeError):
        reopened.append(record, expected_revision=0)
    with pytest.raises(BulkError):
        ContractStore(root).read_record(record.to_dict()["id"], 1)
    ContractStore(root).append(record, expected_revision=0)


def test_concurrent_revision_has_one_winner(tmp_path):
    store = ContractStore(tmp_path / "isolated-contracts")
    contract = Contract.from_dict(package())
    value = approval(contract)
    records = [ContractApproval.from_dict(value), ContractApproval.from_dict(value | {"decision": "rejected"})]
    def append(record):
        try:
            store.append(record, expected_revision=0)
            return "committed"
        except Conflict:
            return "stale"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(append, records)) == ["committed", "stale"]


def test_existing_package_e_state_is_not_opened_or_migrated(tmp_path):
    root = tmp_path / "package-e-cache"
    original = Store(root / "state.sqlite3")
    with original.connection() as db:
        before = db.execute("PRAGMA user_version").fetchone()[0]
        tables = db.execute("SELECT name FROM sqlite_master ORDER BY name").fetchall()
    with pytest.raises(BulkError, match="existing"):
        ContractStore(root)
    with original.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == before == len(MIGRATIONS)
        assert [tuple(row) for row in db.execute("SELECT name FROM sqlite_master ORDER BY name")] == [tuple(row) for row in tables]
    # Even a fabricated namespace marker must not cause Store to migrate it.
    (root / "contract-state.json").write_bytes(canonical({"kind": "isolated-category-contract-state", "schema_version": 1}))
    with pytest.raises(BulkError, match="initialized"):
        ContractStore(root)


def test_corrupt_missing_or_reformatted_blobs_are_not_accepted(tmp_path):
    store = ContractStore(tmp_path / "isolated-contracts")
    contract = Contract.from_dict(package())
    with pytest.raises(BulkError, match="Missing"):
        store.read_object(contract.sha256)
    store.pin(contract)
    path = store._blob_path(contract.sha256)
    path.write_bytes(json.dumps(contract.to_dict(), indent=2).encode())
    with pytest.raises(BulkError, match="canonical"):
        store.read_object(contract.sha256)
    with pytest.raises(BulkError):
        store.pin(contract)
    with pytest.raises(BulkError):
        store.read_object("../escape")


def test_missing_state_and_future_sidecar_do_not_reinitialize(tmp_path):
    root = tmp_path / "isolated-contracts"
    store = ContractStore(root)
    store.pin(Contract.from_dict(package()))
    with store._store.connection() as db:
        db.execute("UPDATE contract_schema SET version=2")
    with pytest.raises(BulkError, match="Unsupported"):
        ContractStore(root)
    # Simulate a lost DB path without deleting state or attempting recovery.
    (root / "state.sqlite3").rename(root / "retained-state.sqlite3")
    with pytest.raises(BulkError, match="missing"):
        ContractStore(root)
    assert not (root / "state.sqlite3").exists()


def test_new_state_refuses_production_roots_without_creating_files():
    from create_defaults.bulk.config import Config
    config = Config()
    for root in (config.asset_dir, config.cache_dir, config.output_dir / "contracts", config.workspace_dir):
        with pytest.raises(BulkError, match="isolated"):
            ContractStore(root)


def test_blob_write_failure_precedes_any_database_reference(tmp_path, monkeypatch):
    from create_defaults.bulk.contracts import state
    store = ContractStore(tmp_path / "isolated-contracts")
    contract = Contract.from_dict(package())
    def fail_write(*args, **kwargs):
        raise OSError("simulated disk failure")
    monkeypatch.setattr(state, "atomic_bytes", fail_write)
    with pytest.raises(OSError):
        store.pin(contract)
    with store._store.connection() as db:
        assert db.execute("SELECT count(*) FROM contract_versions").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM events").fetchone()[0] == 0


def test_symlinked_evidence_is_rejected(tmp_path):
    store = ContractStore(tmp_path / "isolated-contracts")
    contract = Contract.from_dict(package())
    external = tmp_path / "external.json"
    external.write_bytes(contract.encoded)
    path = store._blob_path(contract.sha256)
    path.parent.mkdir(parents=True)
    try:
        path.symlink_to(external)
    except OSError:
        pytest.skip("OS account does not permit test symlink creation")
    with pytest.raises(BulkError, match="Symlinks"):
        store.read_object(contract.sha256)
