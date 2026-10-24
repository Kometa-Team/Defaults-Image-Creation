"""Recovery state, transaction rollback and orchestrator continuation, offline."""
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_background_orchestrator import isolated, recovery_args, photo, cutout, marker, resume_ready, call_main
import orchestrator as orch
import recover_edge_chops as recovery
from create_people_posters import people_diagnostics as secure
from create_people_posters import people_recovery_records as records
from create_people_posters.people_recovery_transaction import RecoveryTransaction

KEY = "NOT_A_REAL_RECOVERY_SECRET_20261024"


@pytest.fixture(autouse=True)
def offline(monkeypatch, isolated):
    monkeypatch.setattr(secure, "_variants", set())
    monkeypatch.setenv("TMDB_KEY", KEY)
    monkeypatch.delenv("TMDB_READ_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(requests.sessions.Session, "request", lambda *a, **k: pytest.fail("No live security-test requests"))


@pytest.mark.parametrize("failure", [requests.exceptions.SSLError, requests.exceptions.ConnectTimeout])
def test_lookup_failure_keeps_every_byte_and_never_marks_attempt_or_exhaustion(monkeypatch, recovery_args, failure):
    args = recovery_args
    path = recovery.final_transparent_path(args.people_root, "Person")
    cutout(path); before = path.read_bytes()
    def fail(*args):raise failure("https://api.themoviedb.org/3/search/person?api_key=" + KEY)
    monkeypatch.setattr(recovery, "tmdb_candidates", fail)
    row = recovery.recover_one(args, SimpleNamespace(), KEY, "Person", "headchop")
    assert row.status == "unresolved" and row.retryable and recovery.local_recovery_status_code([row]) == 3
    assert path.read_bytes() == before and KEY not in row.note
    attempted, appended = set(), []
    staged = recovery.stage_one_for_orchestrator(args, SimpleNamespace(), KEY, "Person", "headchop", attempted, appended)
    assert staged.retryable and not attempted and not appended
    assert not recovery.load_exhausted_names(args.exhausted_file)


def test_transient_image_failure_does_not_become_exhausted_or_permanently_attempted(monkeypatch, recovery_args):
    error = secure.DiagnosticError(secure.Diagnostic("image", "download_image", "server_error", 503, True))
    def fail(*args):raise error
    monkeypatch.setattr(recovery, "download_candidate", fail)
    attempted, appended = set(), []
    row = recovery.stage_one_for_orchestrator(recovery_args, SimpleNamespace(), KEY, "Person", "headchop", attempted, appended)
    assert row.retryable and row.attempts == 2 and not appended and not attempted


def test_disk_failure_is_fatal_and_does_not_mark_a_candidate_exhausted(monkeypatch, recovery_args):
    import errno
    def fail(*args):raise OSError(errno.ENOSPC, "disk unavailable")
    monkeypatch.setattr(recovery, "download_candidate", fail)
    attempted, appended = set(), []
    with pytest.raises(RuntimeError):
        recovery.stage_one_for_orchestrator(recovery_args, SimpleNamespace(), KEY, "Person", "headchop", attempted, appended)
    assert not attempted and not appended and not recovery.load_exhausted_names(recovery_args.exhausted_file)


def test_mixed_seven_targets_checkpoint_exhaustion_and_resume_only_transient(monkeypatch, recovery_args):
    args = recovery_args
    args.inline, args.all = True, True
    names = ["RecoveredOne", "RecoveredTwo", "ExhaustedOne", "ExhaustedTwo", "ExhaustedThree", "ExhaustedFour", "Retry"]
    root = recovery.CONFIG_DIR / "people_dirs"
    args.people_root = root
    before = {}
    for name in names:
        path = recovery.final_transparent_path(root, name)
        cutout(path); before[path] = path.read_bytes()
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setattr(recovery, "background_python", lambda default: default)
    monkeypatch.setattr(recovery, "find_recovery_targets", lambda *a, **k: ([(n, recovery.final_transparent_path(root, n), "headchop") for n in names], 0))
    monkeypatch.setattr(recovery, "parser", lambda: SimpleNamespace(parse_args=lambda: args))
    calls = []
    def recover(args, session, key, name, issues):
        calls.append(name)
        if name.startswith("Recovered") or (name == "Retry" and len(calls) > 7):
            path = recovery.final_transparent_path(root, name)
            path.write_bytes(b"accepted exact output " + name.encode())
            return recovery.RecoveryRow(name, "recovered", note="accepted alternate")
        if name == "Retry":
            return recovery.RecoveryRow(name, "unresolved", diagnostic=secure.Diagnostic("TMDB", "search_person", "tls", retryable=True, endpoint="/3/search/person"))
        return recovery.RecoveryRow(name, "exhausted", final_issues="headchop")
    monkeypatch.setattr(recovery, "recover_one", recover)
    assert recovery.main() == 3
    first = records.read_summary(args.out_root / "recovery-summary.json", run_id=args.run_id)
    assert first["retry_names"] == ["Retry"] and first["changed_names"] == names[:2]
    assert records.status_code(first["rows"]) == 3
    assert recovery.load_exhausted_names(args.exhausted_file) == {n.casefold() for n in names[2:6]}
    assert all(path.read_bytes() == data for path, data in before.items() if path.stem not in names[:2])
    assert recovery.main() == 0
    # Even a conservative repeated scan must reuse recovered SHA evidence.
    assert calls.count("RecoveredOne") == calls.count("RecoveredTwo") == 1
    assert calls.count("Retry") == 2
    second = records.read_summary(args.out_root / "recovery-summary.json", run_id=args.run_id)
    assert second["changed_names"] == ["Retry"] and not second["retry_names"]


@pytest.mark.parametrize("status,code", [("recovered", 0), ("exhausted", 0), ("error", 2)])
def test_complete_and_fatal_exit_contract(status, code):
    rows = [recovery.RecoveryRow("One", status), recovery.RecoveryRow("Two", status)]
    assert recovery.local_recovery_status_code(rows) == records.status_code([records.row_data(r) for r in rows]) == code


def test_recovered_checkpoint_requires_output_and_detects_tampering(recovery_args):
    path = recovery_args.out_root / "checkpoints.json"
    checkpoints = records.Checkpoints(path, recovery_args)
    row = recovery.RecoveryRow("Person", "recovered")
    with pytest.raises(ValueError):checkpoints.save(row, [])
    target = recovery_args.people_root / "transparent" / "Person.png"
    cutout(target)
    checkpoints.save(row, [target])
    assert records.Checkpoints(path, recovery_args).completed("Person")["status"] == "recovered"
    target.write_bytes(b"substituted")
    with pytest.raises(ValueError):checkpoints.completed("Person")
    path.write_text('{"unexpected":"state"}')
    with pytest.raises(ValueError):records.Checkpoints(path, recovery_args)


@pytest.mark.parametrize("cancel", [False, True])
def test_durable_transaction_restores_original_and_absence_on_failure(tmp_path, cancel):
    old, new = tmp_path / "old.jpg", tmp_path / "new.png"
    old.write_bytes(b"original immutable bytes")
    with pytest.raises(KeyboardInterrupt if cancel else RuntimeError):
        with RecoveryTransaction(tmp_path / "journal", "Person", [old, new]):
            old.write_bytes(b"unaccepted")
            new.write_bytes(b"unaccepted")
            if cancel:raise KeyboardInterrupt
            raise RuntimeError("failure")
    assert old.read_bytes() == b"original immutable bytes" and not new.exists()
    assert list((tmp_path / "journal").rglob("*.bin"))


def test_durable_transaction_reconciles_interrupted_attempt_and_blocks_corrupt_backup(tmp_path):
    old = tmp_path / "old.jpg"; old.write_bytes(b"original")
    first = RecoveryTransaction(tmp_path / "journal", "Person", [old]); first.__enter__()
    old.write_bytes(b"interrupted candidate")
    with RecoveryTransaction(tmp_path / "journal", "Person", [old]) as resumed:
        assert old.read_bytes() == b"original"
        resumed.commit()
    backup = first.journal.parent / "0.bin"
    backup.write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        with RecoveryTransaction(tmp_path / "journal", "Person", [old]):pytest.fail("Unsafe journal accepted")
    assert old.read_bytes() == b"original" and backup.exists()


def test_recovery_cancellation_after_render_restores_native_source_and_all_posters(monkeypatch, recovery_args):
    args = recovery_args
    args.people_root = recovery.CONFIG_DIR / "people_dirs"
    output = recovery.final_transparent_path(args.people_root, "Person")
    cutout(output)
    original = Path(os.environ["SEL_ORIG_DIR"]) / "Person.jpg"; photo(original)
    before = {p: p.read_bytes() for p in (output, original)}
    def cancelled(*a):
        output.write_bytes(b"partial rendered output")
        original.write_bytes(b"partial source")
        raise KeyboardInterrupt
    monkeypatch.setattr(recovery, "run_step", cancelled)
    with pytest.raises(KeyboardInterrupt):recovery.recover_one(args, SimpleNamespace(), KEY, "Person", "headchop")
    assert all(p.read_bytes() == value for p, value in before.items())
    assert not (args.downloads_dir / "Person.png").exists()


def test_actual_recovery_csv_html_json_and_orchestrator_summary_have_no_canary(tmp_path, monkeypatch):
    secure.register_secret(KEY)
    row = recovery.RecoveryRow("Person", "unresolved", note="request api_key=" + KEY,
        diagnostic=secure.Diagnostic("TMDB", "search_person", "tls", retryable=True, endpoint="/3/search/person"))
    recovery.write_report(tmp_path, [row])
    for path in tmp_path.iterdir():
        if path.is_file():assert KEY.encode() not in path.read_bytes()
    with (tmp_path / "edge_chop_recovery.csv").open(encoding="utf8", newline="") as handle:
        value = next(csv.DictReader(handle))
    assert value["provider"] == "TMDB" and value["error_category"] == "tls" and value["retryable"] == "True"


def test_orchestrator_partial_receipt_continues_and_resume_only_retries_pending(monkeypatch):
    resume_ready(); marker("remove_bg"); marker("poster_ps1")
    calls = []
    retry = recovery.RecoveryRow("Retry", "unresolved", diagnostic=secure.Diagnostic("TMDB", "search_person", "tls", retryable=True, endpoint="/3/search/person"))
    def run(title, argv, **kwargs):
        calls.append(argv)
        if "recover_edge_chops.py" in argv:
            run_id = argv[argv.index("--run-id") + 1]
            recovery.write_report(orch.CONFIG_DIR / "edge_chop_recovery", [retry], run_id=run_id)
            return 3, None, None
        return 0, None, None
    monkeypatch.setattr(orch, "run_cmd", run)
    assert call_main(monkeypatch, "--stop-after", "recover_edge_chops") == 0
    assert (orch.STATE_DIR / "recover_edge_chops.pending.json").is_file()
    assert not (orch.STATE_DIR / "recover_edge_chops.done.json").exists()
    assert (orch.STATE_DIR / "poster_ps1.done.json").exists()
    assert call_main(monkeypatch, "--stop-after", "recover_edge_chops") == 0
    args = calls[-1]
    assert args[args.index("--names") + 1:] == ["Retry"]
    assert all("create_people_poster.py" not in a and "publish_people_github.py" not in a for a in calls)


def test_orchestrator_cannot_accept_missing_or_stale_recovery_receipt(monkeypatch):
    resume_ready(); marker("remove_bg"); marker("poster_ps1")
    recovery.write_report(orch.CONFIG_DIR / "edge_chop_recovery", [])
    monkeypatch.setattr(orch, "run_cmd", lambda *a, **k: (0, None, None))
    assert call_main(monkeypatch, "--stop-after", "recover_edge_chops") == 2
    assert not (orch.STATE_DIR / "recover_edge_chops.done.json").exists()
