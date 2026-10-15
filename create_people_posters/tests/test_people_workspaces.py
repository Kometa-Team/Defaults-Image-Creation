import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from people_workspaces import Workspaces, atomic_json, process_alive
from people_publication_state import PublicationState
from people_github import REPOSITORIES
from test_people_github import plan, FakeGitHub
from people_remote_inventory import RemoteInventory
from publish_people_github import Publisher


@pytest.fixture
def manager(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith(("PEOPLE_", "SEL_", "EDGE_CHOP_", "COLORIZE_")):
            monkeypatch.delenv(key)
    config = tmp_path / "config"
    config.mkdir()
    (config / "people_list.txt").write_text("Ada|42|Ada\n", encoding="utf-8")
    manager = Workspaces(config)
    yield manager
    manager.close()


def published_job(manager, monkeypatch):
    import test_people_github as support
    batch = manager.create()
    monkeypatch.setattr(support, "BATCH", batch)
    ledger = PublicationState(manager.state)
    client = FakeGitHub()
    inventory = RemoteInventory(client, manager.state / "inventory.db", "master")
    rows = plan(manager.path(batch), ledger)
    monkeypatch.setenv("UPDATE_TRIGGER_READMES", "false")
    Publisher(client, inventory, ledger).publish(batch)
    manager.confirm_published(batch, ledger)
    inventory.close()
    ledger.close()
    return batch


def test_isolated_creation_and_input_preservation(manager):
    one, two = manager.create(), manager.create()
    assert one != two
    assert manager.path(one) != manager.path(two)
    assert (manager.path(one) / "input/people_list.txt").read_bytes() == (manager.config / "people_list.txt").read_bytes()
    assert manager.record(one)[0]["status"] == "pending"


def test_select_resumes_failed_job(manager):
    batch = manager.create()
    manager.set_status(batch, "failed", "power loss")
    assert manager.select() == batch
    assert manager.select(batch) == batch
    assert manager.select(new=True) != batch


def test_configure_paths_without_model_movement(manager, monkeypatch):
    batch = manager.create()
    old_env = dict(os.environ)
    try:
        path = manager.configure(batch)
        assert Path(os.environ["SEL_SRC_DIR"]).is_relative_to(path)
        assert not Path(os.environ["REMBG_HOME"]).is_relative_to(path)
        assert Path(os.environ["PEOPLE_STATE_DIR"]) == manager.state
        assert Path(os.environ["COLORIZE_DDCOLOR_MODELS_DIR"]).parent == manager.config / "models"
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def test_successful_cleanup_retains_receipts_models_and_logs(manager, monkeypatch):
    batch = published_job(manager, monkeypatch)
    model = manager.config / "models/rembg/model.onnx"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"persistent")
    log = manager.path(batch) / "logs/run.log"
    log.write_bytes(b"x" * 100000)
    future = time.time() + 4 * 86400
    assert manager.cleanup(dry_run=True, now=future) == [(batch, "eligible")]
    assert (manager.path(batch) / "prepared").exists()
    assert manager.cleanup(dry_run=False, now=future) == [(batch, "cleaned")]
    assert not (manager.path(batch) / "prepared").exists()
    assert model.read_bytes() == b"persistent"
    assert (manager.state / "publication_state.db").exists()
    assert (manager.state / "manifests" / (batch + ".json")).exists()
    assert log.stat().st_size == 32768
    assert manager.record(batch)[0]["status"] == "complete"


@pytest.mark.parametrize("status", ["pending", "processing", "generated", "validated", "partially_published", "failed"])
def test_unpublished_files_never_expire(manager, status):
    batch = manager.create()
    image = manager.path(batch) / "posters/unpublished.jpg"
    image.write_bytes(b"only-copy")
    manager.set_status(batch, status)
    result = manager.cleanup(dry_run=False, now=time.time() + 100 * 86400)
    assert result == [(batch, "retained: unpublished; manual recovery required")]
    assert image.read_bytes() == b"only-copy"


def test_cleanup_requires_ledger_not_just_manifest(manager):
    batch = manager.create()
    manager.set_status(batch, "cleanup_eligible")
    with manager.db:
        manager.db.execute("UPDATE jobs SET published=? WHERE id=?", (time.time() - 10 * 86400, batch))
    assert manager.cleanup(dry_run=False)[0][1] == "retained: publication receipts incomplete"


def test_cleanup_interrupt_resumes(manager, monkeypatch):
    batch = published_job(manager, monkeypatch)
    import people_workspaces
    original = people_workspaces.shutil.rmtree
    def fail(path):
        raise OSError("interrupted cleanup")
    monkeypatch.setattr(people_workspaces.shutil, "rmtree", fail)
    with pytest.raises(OSError, match="interrupted"):
        manager.cleanup(dry_run=False, now=time.time() + 4 * 86400)
    assert manager.record(batch)[0]["status"] == "cleanup_eligible"
    monkeypatch.setattr(people_workspaces.shutil, "rmtree", original)
    manager.cleanup(dry_run=False, now=time.time() + 4 * 86400)
    assert manager.record(batch)[0]["status"] == "complete"


@pytest.mark.parametrize("batch", ["..", "../outside", "/absolute", "C:/outside", "", "bad-id"])
def test_batch_traversal_prevented(manager, batch):
    with pytest.raises(ValueError):
        manager.path(batch)


def test_symlink_prevents_any_cleanup(manager, monkeypatch, tmp_path):
    batch = published_job(manager, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "important.jpg").write_bytes(b"do-not-delete")
    link = manager.path(batch) / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("OS account cannot create symlinks")
    with pytest.raises(ValueError, match="Symlink"):
        manager.cleanup(dry_run=False, now=time.time() + 4 * 86400)
    assert (outside / "important.jpg").read_bytes() == b"do-not-delete"


def test_active_job_not_cleaned(manager, monkeypatch):
    batch = published_job(manager, monkeypatch)
    manager.activate(batch)
    try:
        assert manager.cleanup(dry_run=False, now=time.time() + 4 * 86400) == []
    finally:
        manager.deactivate(batch)


def test_new_unpublished_image_after_success_is_retained(manager, monkeypatch):
    batch = published_job(manager, monkeypatch)
    image = manager.path(batch) / "posters/new-unpublished.jpg"
    image.write_bytes(b"only copy")
    result = manager.cleanup(dry_run=False, now=time.time() + 4 * 86400)
    assert result == [(batch, "retained: local image changed after publication")]
    assert image.read_bytes() == b"only copy"


@pytest.mark.skipif(os.name != "nt", reason="Windows junctions only")
def test_windows_junction_prevents_cleanup(manager, monkeypatch, tmp_path):
    import subprocess
    batch = published_job(manager, monkeypatch)
    outside = tmp_path / "junction-target"
    outside.mkdir()
    image = outside / "important.jpg"
    image.write_bytes(b"do not delete")
    link = manager.path(batch) / "junction"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
    if result.returncode:
        pytest.skip("Account/filesystem cannot create junctions")
    try:
        with pytest.raises(ValueError, match="reparse"):
            manager.cleanup(dry_run=False, now=time.time() + 4 * 86400)
        assert image.exists()
    finally:
        os.rmdir(link)


def test_alive_check_never_terminates_current_process():
    assert process_alive(os.getpid())


def test_model_cache_inside_jobs_rejected(manager, monkeypatch):
    batch = manager.create()
    environment = dict(os.environ)
    try:
        monkeypatch.setenv("REMBG_HOME", str(manager.path(batch) / "models"))
        with pytest.raises(ValueError, match="outside managed"):
            manager.configure(batch)
    finally:
        os.environ.clear()
        os.environ.update(environment)


def test_validation_job_not_resumed(manager):
    batch = manager.create()
    manager.set_status(batch, "validation_only")
    assert manager.select() != batch
    with pytest.raises(ValueError, match="validation-only"):
        manager.select(batch)


def test_budget_rejects_more_work_without_deleting(manager, monkeypatch):
    batch = manager.create()
    image = manager.path(batch) / "posters/photo.jpg"
    image.write_bytes(b"x" * 1000)
    monkeypatch.setenv("PEOPLE_JOBS_MAX_GIB", "0.0000001")
    with pytest.raises(ValueError, match="budget"):
        manager.create()
    assert image.exists()


def test_local_git_default_is_unchanged(monkeypatch):
    import orchestrator
    assert "ensure_people_repo.py" in Path(orchestrator.__file__).read_text(encoding="utf-8")
    assert os.getenv("PEOPLE_PUBLISH_MODE", "local_git") == "local_git"
