"""M2 metadata-only tests. Synthetic negatives never create raster fixtures."""

from copy import deepcopy
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from create_defaults.bulk.common import BulkError, Conflict, canonical, fingerprint
from create_defaults.bulk.contracts import ContractApproval, read_document
from create_defaults.bulk.contracts.adoption import AdoptionArchive, HistoricalOutput, HistoricalRegistry, audit_membership
from create_defaults.bulk.contracts.adoption.inventory import (
    _overlay, _task, assemble_registry, discover, verify_baseline_job, verify_owned_receipt, verify_production_lane,
)
from create_defaults.bulk.contracts.adoption.models import AdoptionError, encoded_json, fingerprints
from create_defaults.bulk.contracts.adoption.sources import HERE, load_pins, verify_sources
from create_defaults.bulk.library_sources import sealed
from create_defaults.bulk.operator_publication import authorize


H = "a" * 64
OTHER = "b" * 64


@lru_cache(maxsize=1)
def template():
    return json.loads(gzip.decompress((HERE / "evidence/overlay-native-000.json.gz").read_bytes()))["rows"][0]


def synthetic(identity="overlay.synthetic-one", name="Example", size="standard", source_hash=H):
    """Clone the strict job shape, replace provenance and content with test data."""
    row = deepcopy(template())
    job = row["job"]
    parameters = dict(job["parameters"], input=f"logos/{name}.png", box=[285, 85] if size == "standard" else [440, 100])
    path = f"synthetic/overlays/{size}/{name}.png"
    job.update(id=identity, poster_id="overlay.synthetic-source", variant=size,
               parameters=parameters, raw_parameters=parameters, local_relative=path, remote_relative=path,
               dependencies=[], inputs=[{"role": "overlay_source", "path": parameters["input"], "sha256": source_hash}],
               source={"kind": "authored", "path": "synthetic.yml", "line": 1, "row_sha256": fingerprint(parameters)})
    definition = {"group": "synthetic", "parameters": parameters, "transform": job["layout_evidence"]["transform"]}
    job["definition_fingerprint"] = fingerprint(definition)
    job["render_fingerprint"] = fingerprint({key: job[key] for key in ("kind", "parameters", "inputs", "dependencies", "language_behavior")} | {"renderer": row["renderer"]})
    row["worker_spec"] = {"task": _task(job, {identity: row}, row["renderer"]).spec(), "renderer_identity": H}
    row["receipt"] = {"schema_version": 1, "job_id": "render.synthetic-owned-state", "logical_id": identity,
        "job_fingerprint": fingerprint(row["worker_spec"]), "render_fingerprint": job["render_fingerprint"],
        "renderer_identity": H, "relative": path, "sha256": H, "size": 100}
    row["receipt"]["receipt_sha256"] = fingerprint(row["receipt"])
    value = {"schema_version": 1, "kind": "historical-output-adoption",
        "identity": {"schema_version": 1, "kind": "item-identity", "id": identity, "category": "Overlays",
            "display_name": name, "rendered_caption": "", "source": {"path": parameters["input"], "sha256": source_hash},
            "local_path": path, "public_path": path, "semantic_member": None},
        "job_id": identity, "observed_variant": size, "source_identity": "source.synthetic", "source_kind": "source_asset",
        "family": None, "paired_identity": None, "effective_definition_json": encoded_json(definition), "job_json": encoded_json(job),
        "baseline_job_sha256": fingerprint(job), "baseline_renderer_sha256": fingerprint(row["renderer"]),
        "fingerprints": fingerprints(definition, job, []),
        "evidence": {"native_report_sha256": H, "owned_receipt_sha256": row["receipt"]["receipt_sha256"],
            "worker_spec_sha256": fingerprint(row["worker_spec"]), "original_receipt_sha256": H, "output_sha256": H,
            "response_receipt_sha256": H, "approval_refs": []},
        "bridges": [], "historical_exceptions": [], "historical_compatibility": "verified_unchanged_material",
        "contract_compatibility": "not_assessed_no_category_contract", "maintainer_approval": "not_found", "publication_authorized": False}
    return HistoricalOutput.from_dict(value), row


def registry(records):
    return assemble_registry(records, {"kind": "synthetic-test-audit", "records": len(records)}, load_pins())


def test_deterministic_order_and_frozen_identity_across_filename_changes():
    first, _ = synthetic()
    second, _ = synthetic("overlay.synthetic-two", "Second", "bigger")
    assert registry([first, second]).sha256 == registry([second, first]).sha256
    assert HistoricalOutput.from_bytes(first.encoded).sha256 == first.sha256
    renamed, _ = synthetic(name="New filename")
    assert renamed.to_dict()["identity"]["id"] == first.to_dict()["identity"]["id"]
    assert renamed.to_dict()["source_identity"] == first.to_dict()["source_identity"]
    with pytest.raises(AdoptionError) as error:
        audit_membership([renamed], {first.to_dict()["identity"]["id"]: first.sha256})
    assert error.value.details["record"] == first.to_dict()["identity"]["id"]


def test_source_context_changes_even_when_output_byte_hash_does_not():
    first, _ = synthetic()
    changed, _ = synthetic(source_hash=OTHER)
    assert first.to_dict()["evidence"]["output_sha256"] == changed.to_dict()["evidence"]["output_sha256"]
    for field in ("sources", "material_context"):
        assert first.to_dict()["fingerprints"][field] != changed.to_dict()["fingerprints"][field]
    with pytest.raises(BulkError):
        audit_membership([changed], {first.to_dict()["identity"]["id"]: first.sha256})


@pytest.mark.parametrize("name", ["Pok\u00e9mon", "Poke\u0301mon", "A.C.G.T.", "X-men", "Tokyo MX"])
def test_historical_unicode_case_and_punctuation_are_never_normalized(name):
    record, _ = synthetic(name=name)
    assert record.to_dict()["identity"]["public_path"].endswith(name + ".png")
    assert HistoricalOutput.from_bytes(record.encoded).to_dict() == record.to_dict()


@pytest.mark.parametrize("second", ["Pok\u00e9mon", "POK\u00c9MON", "Poke\u0301mon"])
def test_exact_casefold_and_nfc_destination_collisions(second):
    first, _ = synthetic(name="Pok\u00e9mon")
    another, _ = synthetic("overlay.synthetic-two", second)
    with pytest.raises(AdoptionError) as error:
        audit_membership([first, another])
    assert error.value.code == "adoption_collision"
    assert error.value.details["category"] == "Overlays"


def test_missing_duplicate_and_extra_membership_are_not_deduplicated():
    first, _ = synthetic()
    second, _ = synthetic("overlay.synthetic-two", "Second")
    expected = {r.to_dict()["identity"]["id"]: r.sha256 for r in (first, second)}
    for records in ([first], [first, second, synthetic("overlay.extra", "Extra")[0]], [first, first]):
        with pytest.raises(BulkError):
            audit_membership(records, expected)


def test_pair_completeness_and_invalid_mapping_references():
    first, _ = synthetic()
    value = first.to_dict()
    value["paired_identity"] = "overlay.missing"
    with pytest.raises(BulkError):
        audit_membership([HistoricalOutput.from_dict(value)])
    value = first.to_dict()
    value["identity"]["source"]["sha256"] = OTHER
    with pytest.raises(BulkError, match="adoption_source_mapping|expected"):
        HistoricalOutput.from_dict(value)


def test_owned_receipt_requires_exact_task_and_worker_spec():
    record, row = synthetic()
    verify_owned_receipt(row, {row["job"]["id"]: row})
    for mutate in (lambda v: v["receipt"].update(logical_id="other"),
                   lambda v: v["worker_spec"]["task"]["payload"]["parameters"].update(trim=False),
                   lambda v: v["receipt"].update(sha256=OTHER)):
        bad = deepcopy(row)
        mutate(bad)
        with pytest.raises(BulkError):
            verify_owned_receipt(bad, {bad["job"]["id"]: bad})
    bad = deepcopy(row)
    bad["job"]["parameters"]["trim"] = not bad["job"]["parameters"]["trim"]
    with pytest.raises(BulkError):
        verify_baseline_job(bad, row)


def test_internally_resealed_receipt_still_needs_correct_render_fingerprint():
    _, row = synthetic()
    row["job"]["render_fingerprint"] = OTHER
    row["worker_spec"]["task"]["render_fingerprint"] = OTHER
    row["receipt"]["render_fingerprint"] = OTHER
    row["receipt"]["job_fingerprint"] = fingerprint(row["worker_spec"])
    row["receipt"]["receipt_sha256"] = fingerprint({k: v for k, v in row["receipt"].items() if k != "receipt_sha256"})
    with pytest.raises(BulkError, match="calculated_render_fingerprint"):
        verify_owned_receipt(row, {row["job"]["id"]: row})


def test_overlay_definition_hash_is_recomputed():
    _, row = synthetic()
    job = row["job"]
    group = {"inputs": [job["parameters"]["input"]], "trim": job["parameters"]["trim"],
             "sizes": {"standard": {"box": job["parameters"]["box"], "destination": "synthetic/overlays/standard"}}}
    _overlay(job, {"synthetic": group})
    job["definition_fingerprint"] = OTHER
    with pytest.raises(BulkError, match="definition_fingerprint"):
        _overlay(job, {"synthetic": group})


def test_actual_response_receipt_must_match_pinned_plan_membership():
    pins = {"artwork_commit": "a" * 40, "artwork_tree": "b" * 40}
    member = {"destination": "synthetic/Example.png", "sha256": H, "git_blob": "c" * 40, "size": 100}
    plan = sealed({"members": [member], "baseline": {"head": pins["artwork_commit"], "tree": pins["artwork_tree"]}, "discrepancies": []})
    response = sealed({"destination": member["destination"], "plan_sha256": plan["sha256"], "actual_sha256": H,
                       "actual_git_blob": member["git_blob"], "bytes": 100, "commit_at_actual_download": pins["artwork_commit"]})
    verification = sealed({"plan_sha256": plan["sha256"], "response_receipts": {member["destination"]: response["sha256"]},
                           "expected": 1, "exact_sha256_matches": 1, "discrepancies": []})
    verify_production_lane(verification, plan, {member["destination"]: response}, pins)
    bad = dict(response, actual_git_blob="d" * 40)
    bad = sealed({k: v for k, v in bad.items() if k != "sha256"})
    verification["response_receipts"][member["destination"]] = bad["sha256"]
    with pytest.raises(BulkError, match="actual_git_blob"):
        verify_production_lane(verification, plan, {member["destination"]: bad}, pins)


def test_snapshot_mutation_has_actionable_diagnostics(tmp_path):
    source = tmp_path / "catalog.yml"
    source.write_bytes(b"accepted-source\n")
    pins = {"source_commit": "test-snapshot", "files": [{"path": "catalog.yml", "text_lf": True, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]}
    verify_sources(pins, tmp_path)
    source.write_bytes(b"unapproved-edit\n")
    with pytest.raises(AdoptionError) as error:
        verify_sources(pins, tmp_path)
    assert error.value.details["path"] == "catalog.yml"
    assert error.value.details["expected"] != error.value.details["observed"]
    assert error.value.code == "adoption_source_drift"


@pytest.mark.parametrize("field", ["basis_registry_sha256", "source_pins_sha256", "schema_pins", "members"])
def test_mandatory_registry_and_schema_pins(field):
    record, _ = synthetic()
    value = registry([record]).to_dict()
    value.pop(field)
    with pytest.raises(BulkError):
        HistoricalRegistry.from_dict(value)


def test_tampered_registry_and_category_contract_scope():
    record, _ = synthetic()
    value = registry([record]).to_dict()
    value["basis_registry_sha256"] = OTHER
    with pytest.raises(BulkError):
        HistoricalRegistry.from_dict(value)
    value = registry([record]).to_dict()
    value["schema_pins"][0]["sha256"] = OTHER
    with pytest.raises(BulkError):
        HistoricalRegistry.from_dict(value).verify_schema_pins()


def test_historical_v1_pins_ignore_unselected_future_schemas(tmp_path):
    record, _ = synthetic()
    snapshot = registry([record])
    for pin in snapshot.to_dict()["schema_pins"]:
        (tmp_path / pin["path"]).write_bytes((HERE.parent / "schemas" / pin["path"]).read_bytes())
    (tmp_path / "unrelated-v2.schema.json").write_bytes(canonical({"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}))
    snapshot.verify_schema_pins(schema_root=tmp_path)
    value = registry([record]).to_dict()
    value["schema_pins"] = []
    with pytest.raises(BulkError):
        HistoricalRegistry.from_dict(value).verify_schema_pins()


def test_archive_idempotence_restart_and_immutable_versions(tmp_path):
    records = (synthetic()[0], synthetic("overlay.second", "Second", "bigger")[0])
    root = tmp_path / "isolated"
    snapshot = registry(records)
    archive = AdoptionArchive(root)
    assert archive.commit(snapshot, records) == snapshot.sha256
    assert AdoptionArchive(root).commit(snapshot, records) == snapshot.sha256
    loaded, outputs = AdoptionArchive(root).load("historical-defaults-m2", "1.0.0", expected_sha256=snapshot.sha256)
    assert loaded == snapshot and {r.sha256 for r in outputs} == {r.sha256 for r in records}
    with archive.contracts._store.connection() as db:
        assert db.execute("SELECT count(*) FROM events WHERE kind='historical_adoption_committed'").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM contract_adoption_snapshots")
    changed = snapshot.to_dict()
    changed["audit_json"] = encoded_json({"kind": "changed-snapshot"})
    with pytest.raises(Conflict):
        archive.commit(HistoricalRegistry.from_dict(changed), records)


@pytest.mark.parametrize("failure", ["blob", "transaction"])
def test_interrupted_writes_leave_no_complete_pointer_and_recover(tmp_path, monkeypatch, failure):
    records = (synthetic()[0], synthetic("overlay.second", "Second")[0])
    snapshot = registry(records)
    archive = AdoptionArchive(tmp_path / "isolated")
    if failure == "blob":
        write = archive.contracts._write_blob
        calls = []
        def fail(document):
            calls.append(document.sha256)
            if len(calls) == 2:
                raise OSError("interrupted object write")
            write(document)
        monkeypatch.setattr(archive.contracts, "_write_blob", fail)
    else:
        event = archive.contracts._store.event
        def fail(*args):
            event(*args)
            raise OSError("interrupted before transaction commit")
        monkeypatch.setattr(archive.contracts._store, "event", fail)
    with pytest.raises(OSError):
        archive.commit(snapshot, records)
    with archive.contracts._store.connection() as db:
        assert db.execute("SELECT count(*) FROM contract_adoption_snapshots").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM contract_versions").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM events").fetchone()[0] == 0
    reopened = AdoptionArchive(tmp_path / "isolated")
    assert reopened.commit(snapshot, records) == snapshot.sha256


def test_corrupt_or_incomplete_state_fails_closed(tmp_path):
    record, _ = synthetic()
    snapshot = registry([record])
    root = tmp_path / "isolated"
    archive = AdoptionArchive(root)
    archive.commit(snapshot, (record,))
    archive.contracts._blob_path(record.sha256).write_bytes(b"{}")
    with pytest.raises(BulkError):
        archive.load("historical-defaults-m2", "1.0.0", expected_sha256=snapshot.sha256)
    with pytest.raises(BulkError):
        archive.commit(snapshot, (record,))  # no implicit repair of committed missing/corrupt evidence
    with archive.contracts._store.connection() as db:
        db.execute("DROP TRIGGER contract_adoption_no_update")
    with pytest.raises(BulkError, match="Incomplete"):
        AdoptionArchive(root)


def test_no_adoption_record_can_authorize_publication_or_fabricate_approval():
    record, _ = synthetic()
    snapshot = registry([record])
    for value in (record.to_dict(), snapshot.to_dict()):
        with pytest.raises(BulkError):
            read_document(canonical(value), "record")
        with pytest.raises(BulkError):
            ContractApproval.from_dict(value)
        bad = dict(value, publication_authorized=True)
        with pytest.raises(BulkError):
            type(record if value["kind"] == record.KIND else snapshot).from_dict(bad)
        manifest = sealed({"kind": "proposed-operator-membership", "members": [{}], "policy_sha256": fingerprint({}), "baseline": {}})
        with pytest.raises(BulkError):
            authorize(manifest, {}, sealed(value))


def test_complete_historical_inventory_against_frozen_mapping(monkeypatch, verified_historical_discovery):
    """One real read-only discovery; no full image generation or live state."""
    import requests
    from create_defaults import create_poster
    from create_defaults.bulk import overlays
    from create_defaults.bulk.state import Store
    from create_defaults.bulk.workers import PersistentWorkers
    def prohibited(*args, **kwargs):
        pytest.fail("M2 discovery attempted rendering, live state or network access")
    monkeypatch.setattr(create_poster, "create_poster", prohibited)
    monkeypatch.setattr(overlays, "render", prohibited)
    monkeypatch.setattr(PersistentWorkers, "__init__", prohibited)
    monkeypatch.setattr(Store, "__init__", prohibited)
    monkeypatch.setattr(requests.Session, "request", prohibited)
    snapshot, records, _ = verified_historical_discovery
    frozen = HistoricalRegistry.from_bytes(gzip.decompress((HERE / "baseline/frozen-registry-v1.json.gz").read_bytes()))
    assert snapshot.encoded == frozen.encoded
    report = json.loads(snapshot.to_dict()["audit_json"])
    assert (report["records"], report["posters"], report["overlays"]) == (14079, 9957, 4122)
    assert (report["poster_public"], report["poster_private"], report["public_records"]) == (9955, 2, 14077)
    assert len(report["poster_categories"]) == 21 and report["overlay_groups"] == 18
    assert report["owned_worker_specs_verified"] == report["verified_historical_output_hashes"] == 14079
    assert report["historical_approvals"] == {"historical_record_found": 14077, "not_found_private": 2}
    assert set(report["paired_logo_outputs"]) == {"Chart", "Country", "Network", "Streaming"}
    assert not report["unexplained_differences"] and not report["publication_authorized"]
    assert report["artwork_regenerated"] == report["remote_writes"] == report["category_contracts_assessed"] == 0
    values = [r.to_dict() for r in records]
    playlist = [v for v in values if v["identity"]["category"] == "Playlist"]
    assert len(playlist) == 9
    assert {json.loads(v["job_json"])["parameters"]["font_size"] for v in playlist} == {154}
    assert all("BebasNeue-Regular.ttf" in v["job_json"] for v in playlist)
    assert any(v["identity"]["public_path"] == "genre/Action & Adventure.jpg" and "Action & adventure" in v["identity"]["local_path"] for v in values)
    assert any(v["identity"]["public_path"] == "genre/Splatter.jpg" and json.loads(v["job_json"])["parameters"]["base_color"] == "#990000" for v in values)
    normal_sources = {v["identity"]["source"]["path"] for v in values if any(e["code"] == "D09_NORMAL_ACCEPTED_ALPHA_ASSET" for e in v["historical_exceptions"])}
    assert normal_sources == set(load_pins()["normal_historical_alpha_assets"])
    assert all(v["source_kind"] == "generated_parent" for v in values if json.loads(v["job_json"])["dependencies"])
    assert all("white_wash" not in json.loads(v["job_json"])["parameters"] for v in values if v["identity"]["category"] == "Overlays")
    assert assemble_registry(reversed(records), report, load_pins()).sha256 == snapshot.sha256
    verify_sources(load_pins())  # the audit did not mutate any pinned source/evidence
