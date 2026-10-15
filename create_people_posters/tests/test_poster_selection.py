import json
import os
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import orchestrator as orch
import poster_renderer as selection


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    environment = dict(os.environ)
    for key in list(os.environ):
        if key.startswith(("PEOPLE_", "POSTER_", "SEL_", "ORCH_", "REMOVE_BG_", "COLORIZE_", "EDGE_CHOP_")):
            os.environ.pop(key)
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setattr(orch, "CONFIG_DIR", config)
    monkeypatch.setattr(orch, "STATE_DIR", config / ".orch")
    monkeypatch.setattr(orch, "LOCK_FILE", config / ".orch/run.lock")
    monkeypatch.setattr(orch, "load_env_or_bootstrap", lambda: None)
    monkeypatch.setattr(orch, "background_fingerprint", lambda: {"engine": "birefnet"})
    monkeypatch.setattr(orch, "background_checkpoint_changed", lambda _: False)
    try:
        yield config
    finally:
        os.environ.clear()
        os.environ.update(environment)


def invoke(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["orchestrator.py", *args])
    return orch.main()


def stage(config):
    path = config / "people_dirs/Downloads/Person.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (12, 18), (30, 60, 90, 100)).save(path)
    return path


def test_python_step_keeps_key_and_checkpoints(isolated, monkeypatch):
    monkeypatch.setenv("POSTER_ENGINE", "python")
    stage(isolated)
    calls = []
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (calls.append(argv) or (0, None, None)))
    monkeypatch.setattr(orch, "ps_exe", lambda: pytest.fail("PowerShell discovery in Python mode"))
    invoke(monkeypatch, "--workspace-mode", "persistent", "--redo", "poster_ps1", "--stop-after", "poster_ps1")
    assert Path(calls[-1][1]).name == "create_people_poster.py"
    metadata = json.loads((isolated / ".orch/poster_ps1.done.json").read_text())
    assert metadata["poster_fingerprint"]["engine"] == "python"
    assert not any("magick" in arg or "powershell" in arg or "pwsh" in arg for call in calls for arg in call)


@pytest.mark.parametrize("engine", ["python", "powershell"])
def test_renderer_command_selects_exact_backend(isolated, monkeypatch, engine):
    monkeypatch.setenv("POSTER_ENGINE", engine)
    calls = []
    command = selection.renderer_command("python", find_powershell=lambda: calls.append("lookup") or "pwsh")
    assert Path(command[-1]).name == ("create_people_poster.py" if engine == "python" else "create_people_poster.ps1")
    assert calls == ([] if engine == "python" else ["lookup"])


def test_invalid_engine_fails_before_job_or_process(isolated, monkeypatch):
    monkeypatch.setenv("POSTER_ENGINE", "invalid")
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--redo", "poster_ps1")
    assert error.value.code == 2
    assert not (isolated / "jobs").exists()


def test_python_failure_does_not_fall_back(isolated, monkeypatch):
    monkeypatch.setenv("POSTER_ENGINE", "python")
    stage(isolated)
    calls = []
    def run(title, argv, **kw):
        calls.append(argv)
        return (7 if Path(argv[-1]).name == "create_people_poster.py" else 0), None, None
    monkeypatch.setattr(orch, "run_cmd", run)
    monkeypatch.setattr(orch, "ps_exe", lambda: pytest.fail("Implicit fallback"))
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--workspace-mode", "persistent", "--redo", "poster_ps1", "--stop-after", "poster_ps1")
    assert error.value.code == 7
    assert not (isolated / ".orch/poster_ps1.done.json").exists()


def test_engine_change_invalidates_only_poster_and_downstream(isolated, monkeypatch):
    monkeypatch.setenv("POSTER_ENGINE", "python")
    stage(isolated)
    state = isolated / ".orch"
    for name in ("tmdb", "remove_bg", "poster_ps1", "recover_edge_chops", "sync_images", "readme", "sync_md"):
        orch.write_marker(state / (name + ".done.json"), {})
    calls = []
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (calls.append(argv) or (0, None, None)))
    invoke(monkeypatch, "--workspace-mode", "persistent", "--redo", "push", "--stop-after", "poster_ps1")
    assert Path(calls[-1][1]).name == "create_people_poster.py"
    assert (state / "tmdb.done.json").is_file() and (state / "remove_bg.done.json").is_file()
    assert not (state / "sync_images.done.json").exists()
    assert not (state / "poster_ps1.pending.json").exists()


def test_renderer_restage_uses_accepted_cutout_not_old_download(isolated):
    source = stage(isolated)
    selection.prepare_inputs(isolated)
    source.unlink()
    accepted = isolated / "people_dirs/transparent/P/Images/Person.png"
    accepted.parent.mkdir(parents=True)
    accepted.write_bytes(b"accepted")
    raw = isolated / "sel_downloads/Person.png"
    raw.parent.mkdir()
    raw.write_bytes(b"old")
    selection.prepare_inputs(isolated, require_retained=True)
    assert source.read_bytes() == b"accepted"


def test_legacy_checkpoint_is_never_python_proof(isolated):
    state = isolated / ".orch"
    orch.write_marker(state / "poster_ps1.done.json", {})
    assert selection.checkpoint_changed(state, {"engine": "python"})
    assert not selection.checkpoint_changed(state, {"engine": "powershell"})


@pytest.mark.parametrize("engine", ["python", "powershell"])
def test_jost_replaces_legacy_font_in_renderer_checkpoint(isolated, monkeypatch, engine):
    monkeypatch.setenv("POSTER_ENGINE", engine)
    current = selection.poster_fingerprint()
    legacy = json.loads(json.dumps(current))
    jost = next(path for path in legacy["files"] if Path(path).name == "Jost-260.ttf")
    legacy["files"][str(Path(jost).with_name("FuturaTEELig.ttf"))] = legacy["files"].pop(jost)
    state = isolated / ".orch"
    orch.write_marker(state / "poster_ps1.done.json", {"poster_fingerprint": legacy})
    assert selection.checkpoint_changed(state, current)
    orch.write_marker(state / "poster_ps1.done.json", {"poster_fingerprint": current})
    assert not selection.checkpoint_changed(state, current)


def test_native_renderer_is_default_in_code_and_public_example(isolated):
    from dotenv import dotenv_values
    assert selection.poster_engine() == "python"
    settings = dotenv_values(selection.SCRIPT_DIR / ".env.example")
    assert settings["POSTER_ENGINE"] == "python"


def test_python_renderer_works_in_batch_workspace(isolated, monkeypatch):
    calls = []
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (calls.append(argv) or (0, None, None)))
    invoke(monkeypatch, "--new-batch", "--redo", "poster_ps1", "--stop-after", "poster_ps1")
    assert orch.CONFIG_DIR.parent == isolated / "jobs"
    assert Path(calls[-1][1]).name == "create_people_poster.py"
    assert (orch.CONFIG_DIR / ".orch/poster_ps1.done.json").is_file()


def test_missing_python_dependencies_give_install_instructions(isolated, monkeypatch):
    monkeypatch.setitem(sys.modules, "create_people_poster", None)
    with pytest.raises(ValueError, match="install requirements.txt"):
        selection.poster_fingerprint()
