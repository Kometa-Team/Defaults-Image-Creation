"""Canary scope stays bounded even if language, destination or dependency drifts."""
from copy import deepcopy

import pytest

from create_defaults.bulk.common import BulkError
from create_defaults.bulk.e_canary import SELECTION, prepare, validate_scope


@pytest.fixture
def jobs():
    values = [{"id": "job." + key, "poster_id":key, "kind":"poster", "language":"en", "remote_relative":path,
               "local_relative":"defaults-en/" + path, "dependencies":[]} for key,path in SELECTION.items()]
    parent = next(j for j in values if j["poster_id"] == "year.year-2020.83bfe96a")
    child = next(j for j in values if j["poster_id"] == "year.year-best-2020.85b6933b")
    child["dependencies"] = [{"input":"logo", "job_id":parent["id"], "sha256":"a"*64}]
    return values


@pytest.mark.parametrize("field,value", [("language","fr"), ("kind","overlay"),
    ("remote_relative",None), ("remote_relative","genre/Action & adventure.jpg"),
    ("local_relative","defaults-fr/genre/Action & Adventure.jpg")])
def test_rejects_scope_drift(jobs, field, value):
    target = next(j for j in jobs if j["poster_id"] == "genre.genre-action-adventure.96dd0142")
    target[field] = value
    with pytest.raises(BulkError, match="scope|English|Unsafe"):
        validate_scope(jobs)


def test_rejects_added_artwork_or_missing_verified_parent(jobs):
    validate_scope(jobs)
    with pytest.raises(BulkError):
        validate_scope(jobs + [deepcopy(jobs[0])])
    child = next(j for j in jobs if j["poster_id"] == "year.year-best-2020.85b6933b")
    child["dependencies"][0]["sha256"] = None
    with pytest.raises(BulkError, match="parent"):
        validate_scope(jobs)


def test_preparation_refuses_unscoped_output_root(tmp_path):
    with pytest.raises(BulkError, match="fresh child"):
        prepare(tmp_path / "outside-isolated-canary-area")
    assert not (tmp_path / "outside-isolated-canary-area").exists()


def test_gate_approval_and_prepared_artifacts_preserve_scope_and_exact_evidence():
    import json
    from pathlib import Path
    from create_defaults.bulk.common import fingerprint
    from create_defaults.bulk.e_canary import APPROVED_COMMIT, reference_rows

    evidence = Path(__file__).resolve().parents[1] / "evidence"
    def load(path):
        value = json.loads(path.read_text(encoding="utf-8"))
        assert value["sha256"] == fingerprint({k:v for k,v in value.items() if k != "sha256"})
        return value
    gate = load(evidence / "package-e/gate-e-approval-20261017.json")
    gate_events = load(evidence / "package-e/gate-e-approval-20261017-events.json")
    assert gate["approved_commit"] == APPROVED_COMMIT
    assert gate_events["approval_record_sha256"] == gate["sha256"]
    assert all(e["payload"]["approval_record_sha256"] == gate["sha256"] for e in gate_events["events"])
    for name, binding in gate["bound_evidence"].items():
        assert load(evidence / "package-e" / name)["sha256"] == binding["envelope_sha256"]
    assert gate["authorization"]["english_only_local_canary_preparation"]
    for forbidden in ["execute_canary", "publish_or_overwrite_default_images", "enable_publishing_credentials",
                      "replace_or_remove_powershell_generator", "merge_or_mark_pr_ready", "production_cutover", "further_implementation_phases"]:
        assert gate["authorization"][forbidden] is False
    prepared = load(evidence / "english-canary/preparation-20261017.json")
    bundle = load(evidence / "english-canary/bundle-index-20261017.json")
    rollback = load(evidence / "english-canary/rollback-rehearsal-20261017.json")
    assert prepared["gate_e_approved_commit"] == APPROVED_COMMIT
    assert set(prepared["selection"]) == set(SELECTION)
    assert len(prepared["rows"]) == 7 and len({r["category"] for r in prepared["rows"]}) == 5
    assert not prepared["publication_authorized"] and prepared["production_changes"] == 0
    assert prepared["english_only"] and prepared["overlays"] == prepared["private_outputs"] == 0
    assert prepared["runs"]["cold"]["executed"] == 7
    assert prepared["runs"]["warm"]["executed"] == prepared["runs"]["warm"]["worker_starts"] == 0
    assert prepared["runs"]["warm"]["manifest_sha256"] == prepared["runs"]["cold"]["manifest_sha256"]
    assert prepared["published_snapshot"]["exact_existing_paths"] == 7
    assert prepared["published_snapshot"]["case_conflicts"] == prepared["published_snapshot"]["missing"] == 0
    assert all(r["method"] == "GET" for r in prepared["published_snapshot"]["requests"])
    previous = reference_rows()
    for row in prepared["rows"]:
        assert row["destination"] == SELECTION[row["poster_id"]]
        assert row["sha256"] == previous[row["poster_id"]]["receipt"]["sha256"]
        assert row["render_fingerprint"] == previous[row["poster_id"]]["job"]["render_fingerprint"]
        assert row["publication_decision"] == "pending_explicit_canary_artifact_acceptance"
        assert not row["visual_approval_transferred"]
        assert bundle["inventory"]["output/" + row["local_relative"]]["sha256"] == row["sha256"]
        assert bundle["inventory"][row["published"]["local_verified_backup"]]["sha256"] == row["published"]["sha256"]
    child = next(r for r in prepared["rows"] if r["poster_id"] == "year.year-best-2020.85b6933b")
    parent = next(r for r in prepared["rows"] if r["poster_id"] == "year.year-2020.83bfe96a")
    assert child["dependencies"][0]["job_id"] == parent["id"]
    assert child["dependencies"][0]["sha256"] == parent["sha256"]
    assert bundle["preparation_sha256"] == prepared["sha256"]
    assert bundle["offline_rollback_rehearsal"] == rollback
    assert not bundle["uploaded"] and not bundle["publication_authorized"]
    assert not rollback["remote_configured"] and rollback["production_writes"] == 0
    assert rollback["verified_restored_images"] == 7 and rollback["baseline_tree"] == rollback["restored_tree"]
    assert rollback["unrelated_sentinel_unchanged"]
