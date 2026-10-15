import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import orchestrator as orch


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    environment = dict(os.environ)
    for key in list(os.environ):
        if key.startswith(("PEOPLE_", "SEL_", "ORCH_", "REMOVE_BG_", "COLORIZE_", "EDGE_CHOP_")):
            os.environ.pop(key)
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setattr(orch, "CONFIG_DIR", config)
    monkeypatch.setattr(orch, "STATE_DIR", config / ".orch")
    monkeypatch.setattr(orch, "LOCK_FILE", config / ".orch/run.lock")
    monkeypatch.setattr(orch, "load_env_or_bootstrap", lambda: None)
    monkeypatch.setattr(orch, "background_fingerprint", lambda: {"engine": "adobe"})
    monkeypatch.setattr(orch, "background_checkpoint_changed", lambda _: False)
    monkeypatch.setattr(orch, "ps_exe", lambda: "pwsh")
    try:
        yield config
    finally:
        os.environ.clear()
        os.environ.update(environment)


def invoke(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["orchestrator.py", *args])
    return orch.main()


def test_api_mode_without_clones_preserves_step_names(isolated, monkeypatch):
    calls = []
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (calls.append(argv) or (0, None, None)))
    invoke(monkeypatch, "--publish-mode", "github_api", "--workspace-mode", "persistent", "--redo", "sync_images")
    api = [call for call in calls if "publish_people_github.py" in call]
    assert [call[call.index("--op") + 1] for call in api] == ["validate", "prepare", "push"]
    assert all(call[call.index("--branch") + 1] == "master" for call in api)
    assert not any("ensure_people_repo.py" in call or "update_people_repos.py" in call for call in calls)
    assert (isolated / ".orch/sync_images.done.json").exists()


def test_api_dry_run_not_checkpointed_as_publication(isolated, monkeypatch):
    calls = []
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (calls.append(argv) or (0, None, None)))
    invoke(monkeypatch, "--publish-mode", "github_api", "--workspace-mode", "persistent", "--redo", "sync_images", "--dry-run")
    assert all("--dry-run" in call for call in calls)
    assert not (isolated / ".orch/sync_images.done.json").exists()


def test_api_rejects_local_readme_generation(isolated, monkeypatch):
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--publish-mode", "github_api", "--generate-readmes")
    assert error.value.code == 2


def test_batch_paths_and_checkpoints_are_isolated(isolated, monkeypatch):
    (isolated / "people_list.txt").write_text("42|Ada\n", encoding="utf-8")
    monkeypatch.setenv("TMDB_KEY", "test")
    monkeypatch.setattr(orch, "build_colorize_command", lambda py: [py, "colorize_noncolor_ddcolor.py"])
    calls = []
    def run(title, argv, **kwargs):
        calls.append(argv)
        if "tmdb_people.py" in argv:
            path = orch.CONFIG_DIR / "posters/Ada-42.jpg"
            path.write_bytes(b"source")
        if "prep_people_dirs.py" in argv:
            path = orch.CONFIG_DIR / "people_dirs/Downloads/Ada.jpg"
            path.write_bytes(b"source")
        return 0, None, None
    monkeypatch.setattr(orch, "run_cmd", run)
    invoke(monkeypatch, "--publish-mode", "github_api", "--workspace-mode", "batch", "--new-batch",
           "--people-list", str(isolated / "people_list.txt"), "--stop-after", "prep_dirs")
    workspace = orch.CONFIG_DIR
    assert workspace.parent == isolated / "jobs"
    assert (workspace / ".orch/tmdb.done.json").exists()
    assert not (isolated / ".orch/tmdb.done.json").exists()
    assert not any("scan_kometa_logs.py" in call or "find_and_download_missing_people.py" in call for call in calls)
    assert Path(os.environ["SEL_ORIG_DIR"]).is_relative_to(workspace)
    assert not Path(os.environ["REMBG_HOME"]).is_relative_to(workspace)
    assert not (workspace / ".active").exists()
    assert not orch.LOCK_FILE.exists()


def test_batch_model_failure_preserves_sources(isolated, monkeypatch):
    (isolated / "people_list.txt").write_text("42|Ada\n", encoding="utf-8")
    monkeypatch.setenv("SEL_DOWNLOAD_DIR", str(isolated / "unused"))
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (7 if "sel_remove_bg.py" in argv else 0, None, None))
    monkeypatch.setenv("REMOVE_BG_ENGINE", "adobe")
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--publish-mode", "github_api", "--workspace-mode", "batch", "--new-batch", "--redo", "remove_bg")
    assert error.value.code == 7
    workspace = orch.CONFIG_DIR
    manifest = json.loads((workspace / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert (workspace / "input/people_list.txt").exists()


@pytest.mark.parametrize("selection", ["cli", "environment"])
def test_legacy_mode_still_invokes_local_tools(isolated, monkeypatch, selection):
    repo = isolated / "repos"
    (repo / "transparent").mkdir(parents=True)
    monkeypatch.setenv("PEOPLE_IMAGES_DIR", str(repo))
    calls = []
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (calls.append(argv) or (0, None, None)))
    args = []
    if selection == "cli":
        args = ["--publish-mode", "local_git", "--workspace-mode", "persistent"]
    else:
        monkeypatch.setenv("PEOPLE_PUBLISH_MODE", "local_git")
        monkeypatch.setenv("PEOPLE_WORKSPACE_MODE", "persistent")
    invoke(monkeypatch, *args, "--redo", "sync_images")
    assert any("sync_people_images.py" in call for call in calls)
    assert any("update_people_repos.py" in call and "push" in call for call in calls)
    assert not any("publish_people_github.py" in call for call in calls)


def test_default_run_uses_api_batch_without_clones(isolated, monkeypatch):
    calls = []
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (calls.append(argv) or (0, None, None)))
    invoke(monkeypatch, "--stop-after", "ensure_repo")
    assert os.environ["PEOPLE_PUBLISH_MODE"] == "github_api"
    assert os.environ["PEOPLE_WORKSPACE_MODE"] == "batch"
    assert orch.CONFIG_DIR.parent == isolated / "jobs"
    assert (orch.CONFIG_DIR / "manifest.json").is_file()
    assert len(calls) == 1 and "publish_people_github.py" in calls[0]
    assert calls[0][calls[0].index("--op") + 1] == "validate"
    assert not (orch.CONFIG_DIR / ".active").exists()


def test_cli_can_override_legacy_configuration(isolated, monkeypatch):
    monkeypatch.setenv("PEOPLE_PUBLISH_MODE", "local_git")
    monkeypatch.setenv("PEOPLE_WORKSPACE_MODE", "persistent")
    calls = []
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (calls.append(argv) or (0, None, None)))
    invoke(monkeypatch, "--publish-mode", "github_api", "--workspace-mode", "batch", "--stop-after", "ensure_repo")
    assert orch.CONFIG_DIR.parent == isolated / "jobs"
    assert "publish_people_github.py" in calls[0]


def test_default_api_failure_never_falls_back_to_cloning(isolated, monkeypatch):
    calls = []
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (calls.append(argv) or (7, None, None)))
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch)
    assert error.value.code == 7
    assert len(calls) == 1 and "publish_people_github.py" in calls[0]
    manifest = json.loads((orch.CONFIG_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
