"""Fail-closed controls for the additional mandatory CI namespace."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ci import people_security as gate
from create_people_posters import people_diagnostics as secure


def test_security_producer_keeps_raw_collection_out_of_legacy_acceptance(tmp_path, monkeypatch):
    from ci import validation as legacy
    node = "create_people_posters/tests/test_people_security_gate.py::synthetic_case"
    monkeypatch.setattr(gate, "OUT", tmp_path / "people-security-diagnostics-linux")
    monkeypatch.setattr(gate, "identity", lambda: {"head": "synthetic-head", "platform": "Linux", "plan_sha256": "synthetic-plan"})
    monkeypatch.setattr(gate, "selections", lambda: ({"diagnostics": [node]}, set()))
    destinations = []

    def pytest_adapter(paths, destination, collect=False):
        destinations.append(destination.name)
        value = {"nodes": [node], "exitstatus": 0, "seconds": 0.01, "reports": [] if collect else [
            dict(nodeid=node, when=phase, outcome="passed", wasxfail=False, skip_reason=None)
            for phase in ("setup", "call", "teardown")]}
        legacy.write(destination, value)
        return value

    # Only the pytest transport is synthetic here. The producer, filesystem,
    # current integrity guard, report validation and legacy selector are real.
    monkeypatch.setattr(gate, "pytest_run", pytest_adapter)
    gate.run("diagnostics")
    assert destinations == ["namespace.json", "people-collection.json", "execution.json"]
    assert legacy.legacy_reports(tmp_path) == []
    report = json.loads((gate.OUT / "diagnostics/people-security-report.json").read_text())
    assert report["success"] and report["collection"]["nodes"] == [node]
    # Reproduce the old alias: strict legacy reconciliation must still reject
    # an extra raw report, rather than silently weakening its required set.
    bad = gate.OUT / "diagnostics/collection.json"
    legacy.write(bad, report["collection"])
    with pytest.raises(ValueError, match="Missing or extra required report"):
        legacy.reconcile(legacy.read(legacy.PLAN_PATH), legacy.legacy_reports(tmp_path), "synthetic-base")
    bad.unlink()
    original = tmp_path / "collection-linux/collection.json"
    legacy.write(original, {"kind": "collection"})
    assert legacy.legacy_reports(tmp_path) == [{"kind": "collection"}]


@pytest.mark.parametrize("job", sorted(gate.REQUIRED_JOBS))
@pytest.mark.parametrize("result", ["failure", "cancelled", "skipped", None, "missing"])
def test_any_missing_failed_cancelled_or_skipped_group_prevents_acceptance(job, result):
    needs = {name: {"result": "success"} for name in gate.REQUIRED_JOBS}
    gate.require_jobs(needs)
    if result == "missing":needs.pop(job)
    else:needs[job]["result"] = result
    with pytest.raises(ValueError):gate.require_jobs(needs)


@pytest.mark.parametrize("mutation", ["head", "plan_sha256", "ids_sha256", "missing", "substitute", "skip", "xfail", "unfinished", "missing-call"])
def test_security_evidence_cannot_be_stale_substituted_skipped_or_incomplete(monkeypatch, mutation):
    node = "create_people_posters/tests/test_people_security.py::test_original"
    identity = {"head": "head", "plan_sha256": "plan"}
    data = {"nodes": [node], "exitstatus": 0, "reports": [
        dict(nodeid=node, when=phase, outcome="passed", wasxfail=False, skip_reason=None) for phase in ("setup", "call", "teardown")]}
    report = dict(**identity, kind="people-security-execution", success=True, group="diagnostics",
                  ids_sha256="ids", collection=deepcopy(data), execution=deepcopy(data))
    monkeypatch.setattr(gate, "checksum", lambda _: "ids")
    assert gate.validate_report(report, identity, {"diagnostics": [node]}) == {"passed": 1}
    if mutation in {"head", "plan_sha256", "ids_sha256"}:report[mutation] = "stale"
    elif mutation == "missing":report["execution"]["nodes"] = []
    elif mutation == "substitute":report["execution"]["nodes"] = [node + "substitution"]
    elif mutation == "skip":report["execution"]["reports"][1].update(outcome="skipped", skip_reason="not permitted")
    elif mutation == "xfail":report["execution"]["reports"][1]["wasxfail"] = True
    elif mutation == "unfinished":report["execution"]["exitstatus"] = 2
    else:report["execution"]["reports"].pop(1)
    with pytest.raises(ValueError):gate.validate_report(report, identity, {"diagnostics": [node]})


def test_redaction_is_idempotent_for_persisted_and_reexported_reports():
    value = "Authorization: Bearer NOT_A_REAL_GUARD_SECRET\napi_key=NOT_A_REAL_GUARD_SECRET"
    once = secure.sanitize_text(value)
    assert secure.sanitize_text(once) == once
    assert secure.sanitize_data({"note": once}) == {"note": once}


def test_overlong_stream_record_cannot_expose_a_suffix_after_discard():
    import io
    target = io.StringIO(); stream = secure.RedactingStream(target)
    stream.write("x" * (secure.MAX_TEXT + 1))
    stream.write("untrusted discarded suffix\nordinary safe next record\n")
    assert "untrusted discarded suffix" not in target.getvalue()
    assert "ordinary safe next record" in target.getvalue()


def test_every_tmdb_cli_client_uses_the_shared_bounded_transport():
    import ast
    root = Path(__file__).resolve().parents[1]
    names = ("recover_edge_chops.py", "tmdb_people.py", "tmdb_top_people_list.py", "resolve_original_images.py",
             "review_tmdb_profile_alternates.py", "stage_original_candidates.py")
    for name in names:
        tree = ast.parse((root / name).read_text(encoding="utf-8-sig"))
        # No authenticated raw requests entry point may slip back into these
        # clients. JSON/image input decoding stays outside diagnostic objects.
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr in {"get", "post", "request"} and isinstance(n.func.value, ast.Name)
                 and n.func.value.id in {"session", "requests"}]
        assert not calls, name
        assert any(isinstance(n, ast.ImportFrom) and n.module == "create_people_posters.people_http" for n in ast.walk(tree)), name
