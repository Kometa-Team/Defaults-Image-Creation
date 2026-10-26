"""Offline lifecycle controls. All deletion is confined to pytest tmp_path."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_background_orchestrator import isolated, recovery_args, photo, cutout
from test_people_workspaces import manager, published_job
import recover_edge_chops as recovery
from create_people_posters import people_recovery_storage as storage
from create_people_posters import people_cleanup_report as reporting
from create_people_posters.people_recovery_records import Checkpoints
from create_people_posters.people_workspaces import atomic_json


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(requests.sessions.Session, "request", lambda *a, **k: pytest.fail("Unexpected network"))


def make_scratch(tmp_path, name="Person", ready=True):
    source = tmp_path / "original.jpg"
    source.write_bytes(b"original photograph")
    with storage.Scratch(tmp_path / "recovery", name) as scratch:
        (scratch.work / "candidates").mkdir()
        (scratch.work / "candidates/raw.jpg").write_bytes(b"candidate")
        (scratch.work / "cutout.png").write_bytes(b"transparent")
    if ready:
        scratch.accept([source])
    return scratch, source


def test_success_dry_run_and_idempotent_cleanup_preserve_evidence_and_artwork(tmp_path):
    scratch, source = make_scratch(tmp_path)
    evidence = scratch.folder / "accepted-receipt.json"
    # Unowned metadata cannot be silently deleted or ignored.
    evidence.write_text("immutable")
    with pytest.raises(ValueError, match="Unowned"):
        storage.cleanup(scratch.folder, dry_run=False)
    evidence.unlink()  # test-owned fixture only
    before = (scratch.folder / "scratch.json").read_bytes()
    dry = storage.cleanup(scratch.folder)
    assert dry["eligible_files"] == 2 and dry["eligible_bytes"] == 20 and dry["removed_files"] == 0
    assert (scratch.folder / "scratch.json").read_bytes() == before
    result = storage.cleanup(scratch.folder, dry_run=False)
    assert result["removed_files"] == 2 and result["recovered_bytes"] == 20
    assert source.read_bytes() == b"original photograph"
    assert storage.read_operation(scratch.folder)["state"] == "cleaned"
    assert storage.cleanup(scratch.folder, dry_run=False)["removed_files"] == 0


@pytest.mark.parametrize("failure", ["unresolved", "retryable", "exhausted", "error", "staged"])
def test_unsuccessful_processing_retains_all_scratch(tmp_path, failure):
    scratch, source = make_scratch(tmp_path, ready=False)
    result = storage.cleanup(scratch.folder, dry_run=False)
    assert result["removed_files"] == 0 and "incomplete" in result["blocked"]
    assert len(storage.files(scratch.work)) == 2


@pytest.mark.parametrize("tamper", ["extra", "empty_directory", "changed", "output_changed", "output_missing", "hardlink", "traversal"])
def test_ownership_and_preserved_output_checks_block_entire_cleanup(tmp_path, tamper):
    scratch, source = make_scratch(tmp_path)
    if tamper == "extra":
        (scratch.work / "unowned.txt").write_bytes(b"keep")
    elif tamper == "empty_directory":
        (scratch.work / "unexpected").mkdir()
    elif tamper == "changed":
        (scratch.work / "cutout.png").write_bytes(b"changed")
    elif tamper == "output_changed":
        source.write_bytes(b"changed")
    elif tamper == "output_missing":
        source.unlink()
    elif tamper == "hardlink":
        os.link(scratch.work / "cutout.png", tmp_path / "other.png")
    else:
        manifest = storage.read_operation(scratch.folder)
        manifest["files"]["../../original.jpg"] = dict(bytes=1, sha256="0" * 64)
        atomic_json(scratch.folder / "scratch.json", manifest)
    try:
        result = storage.cleanup(scratch.folder, dry_run=False)
        assert result["removed_files"] == 0 and result["blocked"]
    except (ValueError, OSError):
        pass
    assert (scratch.work / "candidates/raw.jpg").exists()


@pytest.mark.parametrize("which", ["file", "directory", "root"])
def test_symlink_cannot_escape_to_original_or_publication_destinations(tmp_path, which):
    scratch, source = make_scratch(tmp_path)
    outside = tmp_path / "People-Images"
    outside.mkdir()
    (outside / "original.jpg").write_bytes(b"do not touch")
    target = scratch.work / "linked"
    if which == "file":
        destination = source
    elif which == "directory":
        destination = outside
    else:
        target = tmp_path / "alias"
        destination = scratch.folder
    try:
        target.symlink_to(destination, target_is_directory=destination.is_dir())
    except OSError:
        pytest.skip("OS account cannot create symlinks")
    with pytest.raises(ValueError, match="Symlink"):
        storage.cleanup(target if which == "root" else scratch.folder, dry_run=False)
    assert (outside / "original.jpg").read_bytes() == b"do not touch"
    assert (scratch.work / "candidates/raw.jpg").is_file()


def test_interrupted_cleanup_reports_partial_counts_and_retries(tmp_path, monkeypatch):
    scratch, source = make_scratch(tmp_path)
    original = Path.unlink
    calls = []
    def interrupt(path, *args, **kwargs):
        if path.is_relative_to(scratch.work):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("simulated interruption")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", interrupt)
    first = storage.cleanup(scratch.folder, dry_run=False)
    assert first["removed_files"] == 1 and first["blocked"]
    assert storage.read_operation(scratch.folder)["state"] == "ready"
    monkeypatch.setattr(Path, "unlink", original)
    second = storage.cleanup(scratch.folder, dry_run=False)
    assert second["removed_files"] == 1
    assert first["recovered_bytes"] + second["recovered_bytes"] == 20


def test_independent_operations_and_same_person_lease(tmp_path):
    with storage.Scratch(tmp_path / "recovery", "One") as one:
        (one.work / "own.jpg").write_bytes(b"one")
        with pytest.raises(FileExistsError):
            with storage.Scratch(tmp_path / "recovery", "one"):
                pytest.fail("same person raced rollback")
        with storage.Scratch(tmp_path / "recovery", "Two") as two:
            (two.work / "own.jpg").write_bytes(b"two")
    original = tmp_path / "original.jpg"
    original.write_bytes(b"preserved")
    one.accept([original])
    storage.cleanup(one.folder, dry_run=False)
    assert (two.work / "own.jpg").read_bytes() == b"two"


def test_reparse_attribute_is_rejected_even_without_symlink_privilege(tmp_path, monkeypatch):
    scratch, source = make_scratch(tmp_path)
    target = scratch.work / "cutout.png"
    real = Path.lstat
    def substituted(path, *args, **kwargs):
        info = real(path, *args, **kwargs)
        if path == target:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=1024)
        return info
    monkeypatch.setattr(Path, "lstat", substituted)
    with pytest.raises(ValueError, match="Symlink"):
        storage.cleanup(scratch.folder, dry_run=False)
    assert target.exists()


def test_concurrent_cleaner_is_rejected_and_os_lease_releases_on_process_death(tmp_path):
    scratch, source = make_scratch(tmp_path)
    code = """
import os, sys
from pathlib import Path
from create_people_posters.people_recovery_storage import cleanup_lock
with cleanup_lock(Path(sys.argv[1])):
    print('locked', flush=True)
    sys.stdin.readline()
    os._exit(0)  # abrupt process exit, no context finalizer
"""
    process = subprocess.Popen([sys.executable, "-c", code, str(scratch.folder)], stdout=subprocess.PIPE, stdin=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "locked"
        with pytest.raises(ValueError, match="Another process"):
            storage.cleanup(scratch.folder, dry_run=False)
    finally:
        process.communicate(input="exit\n", timeout=10)
    assert storage.cleanup(scratch.folder, dry_run=False)["removed_files"] == 2


def test_processing_interruption_retains_staging_and_blocks_stale_lease(tmp_path):
    scratch = storage.Scratch(tmp_path / "recovery", "Person")
    scratch.__enter__()
    (scratch.work / "raw.jpg").write_bytes(b"retry evidence")
    # Model a process death: no context finalizer, active marker/lease remain.
    assert "active" in storage.cleanup(scratch.folder)["blocked"]
    with pytest.raises(FileExistsError):
        with storage.Scratch(tmp_path / "recovery", "Person"):
            pytest.fail("stale processing lease stolen")
    assert (scratch.work / "raw.jpg").read_bytes() == b"retry evidence"
    scratch.__exit__(None, None, None)  # release this test's own lease


def test_verified_recovery_cleans_only_after_checkpoint(monkeypatch, recovery_args):
    args = recovery_args
    monkeypatch.setenv("POSTER_ENGINE", "python")
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    # Sentinels for every destination remain byte-identical.
    from people_github import REPOSITORIES
    sentinels = []
    for repo in REPOSITORIES.values():
        path = args.out_root.parent / "publication" / repo.replace("/", "_") / "poster.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"published artwork")
        sentinels.append(path)
    row = recovery.recover_one(args, SimpleNamespace(), "FIXTURE", "Person", "headchop")
    assert row.status == "recovered"
    scratch = args.recovery_operations["Person"]
    assert storage.files(scratch.work) and not (args.out_root / "candidates").exists()
    checkpoints = Checkpoints(args.out_root / "recovery-checkpoints.json", args)
    checkpoints.save(row, recovery.style_file_paths(args.people_root, "Person"))
    recovery.finish_scratch(args, row)
    assert storage.read_operation(scratch.folder)["state"] == "cleaned"
    assert not storage.files(scratch.work)
    assert checkpoints.completed("Person")["status"] == "recovered"
    assert len(sentinels) == 7 and all(p.read_bytes() == b"published artwork" for p in sentinels)
    # Durable transaction backups and manifests are retained.
    assert list((args.out_root / "transactions").rglob("transaction.json"))


def test_stage_only_retains_raw_colorization_and_cutouts(monkeypatch, recovery_args):
    row = recovery.stage_one_for_orchestrator(recovery_args, SimpleNamespace(), "FIXTURE", "Person", "headchop", set(), [])
    assert row.status == "staged"
    recovery.finish_scratch(recovery_args, row)
    scratch = recovery_args.recovery_operations["Person"]
    assert storage.read_operation(scratch.folder)["state"] == "retained"
    assert (scratch.work / "candidates/candidate0.jpg").is_file()


def test_staged_success_requires_final_qa_checkpoint_and_preserved_source(recovery_args):
    args = recovery_args
    row = recovery.stage_one_for_orchestrator(args, SimpleNamespace(), "FIXTURE", "Person", "headchop", set(), [])
    scratch = args.recovery_operations["Person"]
    raw = (scratch.work / "candidates/candidate0.jpg").read_bytes()
    assert scratch.source_evidence.read_bytes() == raw
    cutout(recovery.final_transparent_path(args.people_root, "Person"))
    photo(args.people_root / "original/P/Images/Person.jpg")
    assert recovery.postcheck_staged_outputs([row], args) == 1 and row.status == "recovered"
    checkpoints = Checkpoints(args.out_root / "recovery-checkpoints.json", args)
    checkpoints.save(row, recovery.style_file_paths(args.people_root, "Person"))
    recovery.finish_scratch(args, row)
    assert storage.read_operation(scratch.folder)["state"] == "cleaned"
    assert scratch.source_evidence.read_bytes() == raw


def test_failed_model_attempt_retains_candidates_and_original_artwork(monkeypatch, recovery_args):
    args = recovery_args
    original = recovery.final_transparent_path(args.people_root, "Person")
    cutout(original)
    before = original.read_bytes()
    def fail(*args):
        raise RuntimeError("model failed")
    monkeypatch.setattr(recovery, "local_candidate", fail)
    with pytest.raises(RuntimeError):
        recovery.recover_one(args, SimpleNamespace(), "FIXTURE", "Person", "headchop")
    assert original.read_bytes() == before
    folders = list((args.out_root / "operations").iterdir())
    assert len(folders) == 1
    assert storage.read_operation(folders[0])["state"] == "retained"
    assert list((folders[0] / "work/candidates").glob("*.jpg"))


@pytest.mark.parametrize("name", ["../outside", "A/B", "A\\B", "C:outside", "..", "", "A\x00B"])
def test_unsafe_person_paths_are_rejected_before_writing(tmp_path, name):
    with pytest.raises(ValueError, match="Unsafe"):
        storage.Scratch(tmp_path / "recovery", name)
    assert not (tmp_path / "recovery").exists()


def test_report_is_read_only_includes_legacy_blockers_and_default_three_days(manager, monkeypatch):
    batch = published_job(manager, monkeypatch)
    candidate = manager.config / "edge_chop_recovery/candidates/Person/alternate.jpg"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"legacy")
    before = {p: p.read_bytes() for p in manager.config.rglob("*") if p.is_file()}
    young = reporting.report(manager.config)
    assert young["retention_days"] == 3 and young["batch_policy_recoverable_bytes"] == 0
    assert "window" in young["batches"][0]["blocked"]
    old = reporting.report(manager.config, now=time.time() + 4 * 86400)
    assert old["batch_policy_recoverable_bytes"] > 0 and old["legacy_candidates"][0]["files"] == 1
    assert old["owned_scratch_recoverable_bytes"] == 0
    assert before == {p: p.read_bytes() for p in manager.config.rglob("*") if p.is_file()}
    assert manager.cleanup(dry_run=True, now=time.time() + 4 * 86400) == [(batch, "eligible")]


@pytest.mark.parametrize("change", ["receipts", "catalog", "image", "failed", "active"])
def test_batch_report_agrees_with_existing_cleanup_gates(manager, monkeypatch, change):
    batch = published_job(manager, monkeypatch)
    if change == "receipts":
        with manager.db:
            manager.db.execute("UPDATE publications SET status='pending' WHERE batch=?", (batch,))
    elif change == "catalog":
        path = manager.path(batch) / "manifest.json"
        manifest = json.loads(path.read_text())
        del manifest["cleanup_files"]
        atomic_json(path, manifest)
    elif change == "image":
        (manager.path(batch) / "unpublished.png").write_bytes(b"keep")
    elif change == "failed":
        manager.set_status(batch, "failed")
    else:
        manager.activate(batch)
    result = reporting.report(manager.config, now=time.time() + 40 * 86400)
    assert result["batch_policy_recoverable_bytes"] == 0 and result["batches"][0]["blocked"]
    assert manager.cleanup(dry_run=True, now=time.time() + 40 * 86400) != [(batch, "eligible")]


def test_report_does_not_create_missing_directories_or_ledger(tmp_path):
    config = tmp_path / "absent"
    assert reporting.report(config)["categories"] == {}
    assert not config.exists()


def test_apply_requires_explicit_operation_and_cannot_target_legacy(tmp_path):
    root = Path(__file__).resolve().parents[2]
    before = set(tmp_path.rglob("*"))
    for args in (["--apply"], ["--operation", "../../People-Images", "--apply"]):
        result = subprocess.run([sys.executable, "-m", "create_people_posters.people_cleanup_report",
                                 "--config-dir", str(tmp_path), *args], cwd=root,
                                capture_output=True, text=True, timeout=20)
        assert result.returncode == 2
    assert set(tmp_path.rglob("*")) == before
