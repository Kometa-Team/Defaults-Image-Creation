from __future__ import annotations

import csv
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import orchestrator as orch
import recover_edge_chops as recovery
import remove_bg_birefnet as backend

UPSTREAM = ["scan_kometa_logs", "find_and_download_missing", "tmdb", "truncate",
            "audit_people_images", "colorize_noncolor", "prep_dirs"]
DOWNSTREAM = ["poster_ps1", "recover_edge_chops", "sync_images", "readme", "sync_md"]


def photo(path, color=(20, 90, 170)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 48), color).save(path)


def cutout(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (32, 48), (20, 90, 170, 0))
    image.paste((20, 90, 170, 255), (8, 8, 24, 40))
    image.save(path)


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    for key in list(os.environ):
        if key.startswith(("REMOVE_BG_", "SEL_", "ORCH_", "EDGE_CHOP_", "COLORIZE_")):
            monkeypatch.delenv(key)
    config = tmp_path / "config"
    monkeypatch.setattr(orch, "SCRIPT_DIR", tmp_path)
    monkeypatch.setattr(orch, "CONFIG_DIR", config)
    monkeypatch.setattr(orch, "STATE_DIR", config / ".orch")
    monkeypatch.setattr(orch, "LOCK_FILE", config / ".orch" / "run.lock")
    monkeypatch.setattr(orch, "load_env_or_bootstrap", lambda: None)
    monkeypatch.setattr(orch, "ps_exe", lambda: "mock-pwsh")
    monkeypatch.setattr(recovery, "CONFIG_DIR", config)
    monkeypatch.setattr(recovery, "LOGS_DIR", config / "logs")
    monkeypatch.setattr(recovery, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(recovery, "log", lambda message: None)
    monkeypatch.setenv("REMBG_HOME", str(config / "models"))
    monkeypatch.setenv("REMOVE_BG_ENGINE", "adobe")
    monkeypatch.setenv("SEL_SRC_DIR", str(config / "people_dirs" / "Downloads"))
    monkeypatch.setenv("SEL_ORIG_DIR", str(config / "people_dirs" / "original"))
    monkeypatch.setenv("SEL_DOWNLOAD_DIR", str(config / "sel_downloads"))
    repo = tmp_path / "repo"
    (repo / "transparent").mkdir(parents=True)
    monkeypatch.setenv("PEOPLE_IMAGES_DIR", str(repo))
    monkeypatch.setenv("PEOPLE_PUBLISH_MODE", "local_git")
    monkeypatch.setenv("PEOPLE_WORKSPACE_MODE", "persistent")
    monkeypatch.setenv("POSTER_ENGINE", "powershell")
    monkeypatch.setenv("ORCH_CONTINUE_IF_EMPTY", "true")
    monkeypatch.setenv("TMDB_KEY", "mock-key")


def marker(key, meta=None):
    orch.write_marker(orch.STATE_DIR / f"{key}.done.json", meta or {})


def resume_ready():
    for key in UPSTREAM:
        marker(key)


def call_main(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["orchestrator.py", *args])
    try:
        orch.main()
    except SystemExit as exc:
        return exc.code
    return 0


def mock_runner(monkeypatch, failure=0, outcome="success", processed=1):
    calls = []

    def run(title, argv, **kwargs):
        calls.append(argv)
        if "remove_bg_birefnet.py" in argv:
            path = orch.CONFIG_DIR / "logs" / "remove_bg_birefnet.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"outcome": outcome, "exit_code": failure,
                                        "processed": processed, "skipped": 0}), encoding="utf-8")
            path.with_suffix(".log").write_text(f"Files processed: {processed}\n", encoding="utf-8")
        if "sel_remove_bg.py" in argv or "remove_bg_birefnet.py" in argv:
            return failure, None, None
        return 0, None, None

    monkeypatch.setattr(orch, "run_cmd", run)
    return calls


@pytest.mark.parametrize("engine,script", [(None, "remove_bg_birefnet.py"), ("adobe", "sel_remove_bg.py"),
                                           ("birefnet", "remove_bg_birefnet.py")])
def test_backend_selection_end_to_end(monkeypatch, engine, script):
    if engine:
        monkeypatch.setenv("REMOVE_BG_ENGINE", engine)
    else:
        monkeypatch.delenv("REMOVE_BG_ENGINE")
    resume_ready()
    calls = mock_runner(monkeypatch)
    assert call_main(monkeypatch, "--stop-after", "remove_bg") == 0
    assert [argv[1] for argv in calls] == ["ensure_people_repo.py", script]
    saved = json.loads((orch.STATE_DIR / "remove_bg.done.json").read_text())
    assert saved["background_fingerprint"]["engine"] == (engine or "birefnet")
    assert not orch.LOCK_FILE.exists()


@pytest.mark.parametrize("engine", ["", "unknown", "rembg"])
def test_invalid_engine_stops_before_running(monkeypatch, engine):
    monkeypatch.setenv("REMOVE_BG_ENGINE", engine)
    calls = mock_runner(monkeypatch)
    assert call_main(monkeypatch, "--list") == 2
    assert not calls
    assert not orch.STATE_DIR.exists()


def test_adobe_ignores_local_interpreter(monkeypatch):
    monkeypatch.setenv("REMOVE_BG_PYTHON", "missing-interpreter")
    assert orch.build_background_command("pipeline-python") == ["pipeline-python", "sel_remove_bg.py"]


def test_unconfigured_engine_defaults_to_portrait_and_retains_manual_rollback(monkeypatch):
    monkeypatch.delenv("REMOVE_BG_ENGINE")
    assert orch.background_engine() == "birefnet"
    assert orch.background_fingerprint()["model"] == "birefnet-portrait"
    assert orch.build_background_command("pipeline-python")[1] == "remove_bg_birefnet.py"
    monkeypatch.setenv("REMOVE_BG_ENGINE", "adobe")
    assert orch.build_background_command("pipeline-python") == ["pipeline-python", "sel_remove_bg.py"]


def test_local_interpreter_precedence_and_no_silent_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    assert orch.build_background_command("pipeline-python")[0] == "pipeline-python"
    suffix = "Scripts/python.exe" if sys.platform.startswith("win") else "bin/python"
    local = tmp_path / ".venv-rembg" / suffix
    local.parent.mkdir(parents=True)
    local.touch()
    assert orch.build_background_command("pipeline-python")[0] == str(local)
    configured = tmp_path / "Python With Spaces" / "python.exe"
    configured.parent.mkdir()
    configured.touch()
    monkeypatch.setenv("REMOVE_BG_PYTHON", f'"{configured}"')
    assert orch.build_background_command("pipeline-python")[0] == str(configured)
    configured.unlink()
    with pytest.raises(ValueError, match="REMOVE_BG_PYTHON"):
        orch.build_background_command("pipeline-python")


def test_recovery_orchestrator_step_uses_selected_interpreter(monkeypatch, tmp_path):
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    interpreter = tmp_path / "python.exe"
    interpreter.touch()
    monkeypatch.setenv("REMOVE_BG_PYTHON", str(interpreter))
    resume_ready()
    marker("remove_bg", {"background_fingerprint": orch.background_fingerprint()})
    marker("poster_ps1")
    calls = mock_runner(monkeypatch)
    assert call_main(monkeypatch, "--stop-after", "recover_edge_chops") == 0
    assert calls[-1][:3] == [str(interpreter), "recover_edge_chops.py", "--inline"]
    assert all("sel_remove_bg.py" not in argv for argv in calls)


def test_configured_interpreter_on_path_resolves_for_recovery_relaunch(monkeypatch):
    monkeypatch.setenv("REMOVE_BG_PYTHON", "background-python")
    monkeypatch.setattr(orch.shutil, "which", lambda executable: sys.executable)
    assert orch.background_python("ignored") == str(Path(sys.executable).resolve())


def test_resume_skips_all_completed_steps(monkeypatch):
    resume_ready()
    marker("remove_bg")  # Legacy markers mean Adobe.
    marker("poster_ps1")
    calls = mock_runner(monkeypatch)
    assert call_main(monkeypatch, "--stop-after", "poster_ps1") == 0
    assert [argv[1] for argv in calls] == ["ensure_people_repo.py"]


def test_redo_remove_bg_preserves_upstream_and_reruns_downstream(monkeypatch):
    resume_ready()
    marker("remove_bg")
    for key in DOWNSTREAM:
        marker(key)
    calls = mock_runner(monkeypatch)
    assert call_main(monkeypatch, "--redo", "remove_bg", "--stop-after", "poster_ps1") == 0
    assert [argv[1] for argv in calls] == ["sel_remove_bg.py", "-NoLogo"]
    assert all((orch.STATE_DIR / f"{key}.done.json").exists() for key in UPSTREAM)
    assert not (orch.STATE_DIR / "sync_images.done.json").exists()


@pytest.mark.parametrize("old,new", [("adobe", "birefnet"), ("birefnet", "adobe")])
def test_engine_change_invalidates_downstream_without_replaying_library(monkeypatch, old, new):
    monkeypatch.setenv("REMOVE_BG_ENGINE", old)
    marker("remove_bg", {"background_fingerprint": orch.background_fingerprint()})
    resume_ready()
    for key in DOWNSTREAM:
        marker(key)
    photo(Path(os.environ["SEL_ORIG_DIR"]) / "Archived.jpg")
    monkeypatch.setenv("REMOVE_BG_ENGINE", new)
    calls = mock_runner(monkeypatch)
    assert call_main(monkeypatch, "--stop-after", "poster_ps1") == 2
    assert not (orch.STATE_DIR / "remove_bg.done.json").exists()
    assert all(not (orch.STATE_DIR / f"{key}.done.json").exists() for key in DOWNSTREAM)
    assert not Path(os.environ["SEL_SRC_DIR"]).exists()
    assert not calls
    assert call_main(monkeypatch, "--stop-after", "poster_ps1") == 2
    photo(Path(os.environ["SEL_SRC_DIR"]) / "Restaged.jpg")
    assert call_main(monkeypatch, "--stop-after", "poster_ps1") == 0
    assert not (orch.STATE_DIR / "remove_bg.pending.json").exists()


def test_engine_change_list_is_read_only(monkeypatch, capsys):
    resume_ready()
    marker("remove_bg")
    marker("poster_ps1")
    before = {p.name: p.read_bytes() for p in orch.STATE_DIR.iterdir()}
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    assert call_main(monkeypatch, "--list") == 0
    output = capsys.readouterr().out
    assert "remove_bg    : PENDING" in output
    assert "poster_ps1   : PENDING" in output
    assert {p.name: p.read_bytes() for p in orch.STATE_DIR.iterdir()} == before


def test_list_does_not_create_state_directory(monkeypatch):
    assert call_main(monkeypatch, "--list") == 0
    assert not orch.STATE_DIR.exists()


@pytest.mark.parametrize("setting,value", [("REMOVE_BG_MODEL", "birefnet-general"),
                                           ("REMOVE_BG_DEVICE", "cuda"),
                                           ("REMOVE_BG_ALPHA_MATTING", "true"),
                                           ("REMOVE_BG_DECONTAMINATE", "false")])
def test_local_config_change_invalidates_checkpoint(monkeypatch, setting, value):
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    marker("remove_bg", {"background_fingerprint": orch.background_fingerprint()})
    assert not orch.background_checkpoint_changed(orch.background_fingerprint())
    monkeypatch.setenv(setting, value)
    assert orch.background_checkpoint_changed(orch.background_fingerprint())


def test_mixed_adobe_cutout_cannot_validate_engine_switch(monkeypatch):
    marker("remove_bg")
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    cutout(Path(os.environ["SEL_SRC_DIR"]) / "Adobe.png")
    calls = mock_runner(monkeypatch)
    assert call_main(monkeypatch, "--redo", "remove_bg") == 2
    assert not calls
    assert not (orch.STATE_DIR / "remove_bg.done.json").exists()


@pytest.mark.parametrize("failure", [1, 2, 4, 127])
def test_local_failure_propagates_without_adobe_fallback(monkeypatch, capsys, failure):
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    resume_ready()
    calls = mock_runner(monkeypatch, failure=failure)
    assert call_main(monkeypatch, "--stop-after", "poster_ps1") == failure
    assert calls[-1][1] == "remove_bg_birefnet.py"
    assert not (orch.STATE_DIR / "remove_bg.done.json").exists()
    output = capsys.readouterr().err
    assert "REMBG_HOME" in output
    assert "login-only" not in output


def test_local_no_work_persists_unverified_checkpoint(monkeypatch):
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setenv("ORCH_CONTINUE_IF_EMPTY", "false")
    resume_ready()
    calls = mock_runner(monkeypatch, outcome="no_work", processed=0)
    assert call_main(monkeypatch, "--stop-after", "poster_ps1") == 0
    saved = json.loads((orch.STATE_DIR / "remove_bg.done.json").read_text())
    assert saved["outcome"] == "no_work" and saved["model_verified"] is False
    assert len(calls) == 2


def test_no_work_cannot_verify_changed_engine(monkeypatch):
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    resume_ready()
    marker("remove_bg")
    photo(Path(os.environ["SEL_SRC_DIR"]) / "Person.jpg")
    mock_runner(monkeypatch, outcome="no_work", processed=0)
    assert call_main(monkeypatch, "--stop-after", "poster_ps1") == 2
    assert not (orch.STATE_DIR / "remove_bg.done.json").exists()


def test_local_skipped_staged_png_reaches_poster(monkeypatch):
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setenv("ORCH_CONTINUE_IF_EMPTY", "false")
    resume_ready()
    cutout(Path(os.environ["SEL_SRC_DIR"]) / "Person.png")
    calls = mock_runner(monkeypatch, outcome="no_work", processed=0)
    assert call_main(monkeypatch, "--stop-after", "poster_ps1") == 0
    assert calls[-1][0] == "mock-pwsh"


class FakeRemover:
    instances = []

    def __init__(self, settings):
        self.settings = settings
        self.calls = []
        self.closed = False
        self.instances.append(self)

    def process(self, source, destination):
        self.calls.append((source, destination))
        cutout(destination)
        record = {
            **backend.validate_output(destination), "status": "processed", "duration": 0.01,
            "settings": self.settings.fingerprint(), "source_sha256": backend.sha256(source),
            "output_sha256": backend.sha256(destination), "model_identifier": "mock-model",
        }
        backend.atomic_json(backend.sidecar(destination), record)
        return record

    def close(self):
        self.closed = True


@pytest.fixture
def recovery_args(monkeypatch, tmp_path):
    FakeRemover.instances = []
    monkeypatch.setattr(backend, "LocalRemover", FakeRemover)
    monkeypatch.setattr(recovery, "build_rembg_session", lambda *args: pytest.fail("Unexpected Adobe precheck model"))
    monkeypatch.setattr(recovery, "candidate_target_issues", lambda *args, **kwargs: [])
    monkeypatch.setattr(recovery, "edge_metric_summary", lambda *args, **kwargs: "clear")
    monkeypatch.setattr(recovery, "same_as_current_original", lambda *args: "")
    monkeypatch.setattr(recovery, "normalize_to_download", lambda source, target: shutil.copy2(source, target))
    monkeypatch.setattr(recovery, "download_candidate", lambda session, candidate, target: photo(target))
    monkeypatch.setattr(recovery, "ps_exe", lambda: "mock-pwsh")
    candidates = [recovery.ProfileCandidate(f"candidate{i}", f"url{i}", f"/profile{i}.jpg", 32, 48, 1.0, 1)
                  for i in range(2)]
    monkeypatch.setattr(recovery, "tmdb_candidates", lambda *args: candidates)
    args = recovery.parser().parse_args([
        "--people-root", str(tmp_path / "work"), "--downloads-dir", os.environ["SEL_SRC_DIR"],
        "--out-root", str(tmp_path / "reports"), "--allow-grayscale",
        "--exhausted-file", str(tmp_path / "exhausted.txt"),
        "--attempted-file", str(tmp_path / "attempted.csv"),
    ])
    args.bg_engine = "birefnet"
    args.local_remover = None
    args.rembg_session = None
    return args


def test_python_recovery_uses_pillow_without_external_renderers(monkeypatch, recovery_args):
    monkeypatch.setenv("POSTER_ENGINE", "python")
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setattr(recovery, "ps_exe", lambda: pytest.fail("PowerShell lookup in Python mode"))
    monkeypatch.setattr(recovery, "run_step", lambda *args: pytest.fail("External rendering in Python mode"))
    result = recovery.recover_one(recovery_args, SimpleNamespace(), "key", "Person", "headchop")
    assert result.status == "recovered"
    from create_people_poster import STYLES, output_path
    for style in STYLES:
        assert output_path(recovery_args.people_root, style, "Person").is_file()
    assert not (recovery_args.downloads_dir / "Person.png").exists()


def test_orchestrator_local_batch_hands_valid_cutouts_and_originals_to_poster(monkeypatch, recovery_args):
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setenv("ORCH_CONTINUE_IF_EMPTY", "false")
    resume_ready()
    source = Path(os.environ["SEL_SRC_DIR"])
    originals = Path(os.environ["SEL_ORIG_DIR"])
    output = Path(os.environ["SEL_DOWNLOAD_DIR"])
    for name in ("First", "Second"):
        photo(source / f"{name}.jpg")
    inputs = {path.name: path.read_bytes() for path in source.iterdir()}
    calls = []

    def run(title, argv, **kwargs):
        calls.append(argv)
        assert "sel_remove_bg.py" not in argv
        if "remove_bg_birefnet.py" in argv:
            summary = backend.run_batch(source, originals, output, backend.Settings.from_env(), FakeRemover)
            backend.atomic_json(orch.CONFIG_DIR / "logs" / "remove_bg_birefnet.json", summary)
            return summary["exit_code"], None, None
        if argv[0] == "mock-pwsh":
            for name in ("First", "Second"):
                backend.validate_output(source / f"{name}.png", (32, 48))
                assert (source / f"{name}.png").read_bytes() == (output / f"{name}.png").read_bytes()
                assert (originals / f"{name}.jpg").read_bytes() == inputs[f"{name}.jpg"]
                assert backend.sidecar(source / f"{name}.png").exists()
            assert not list(source.glob("*.jpg"))
        return 0, None, None

    monkeypatch.setattr(orch, "run_cmd", run)
    assert call_main(monkeypatch, "--stop-after", "poster_ps1") == 0
    assert len(FakeRemover.instances) == 1 and len(FakeRemover.instances[0].calls) == 2
    assert FakeRemover.instances[0].closed
    assert len(calls) == 3
    saved = json.loads((orch.STATE_DIR / "remove_bg.done.json").read_text())
    assert saved["outcome"] == "success" and saved["model_verified"] is True


def test_normal_resume_after_no_work_processes_new_jpegs_once_without_selenium(monkeypatch, recovery_args):
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setenv("ORCH_CONTINUE_IF_EMPTY", "false")
    resume_ready()
    source = Path(os.environ["SEL_SRC_DIR"])
    source.mkdir(parents=True)
    calls = []

    def run(title, argv, **kwargs):
        calls.append(argv)
        assert "sel_remove_bg.py" not in argv
        if "remove_bg_birefnet.py" in argv:
            summary = backend.run_batch(source, Path(os.environ["SEL_ORIG_DIR"]),
                                        Path(os.environ["SEL_DOWNLOAD_DIR"]),
                                        backend.Settings.from_env(), FakeRemover)
            backend.atomic_json(orch.CONFIG_DIR / "logs" / "remove_bg_birefnet.json", summary)
            (orch.CONFIG_DIR / "logs" / "remove_bg_birefnet.log").write_text(
                f"Files processed: {summary['processed']}\n", encoding="utf-8")
            return summary["exit_code"], None, None
        return 0, None, None

    monkeypatch.setattr(orch, "run_cmd", run)
    assert call_main(monkeypatch, "--stop-after", "poster_ps1") == 0
    assert not FakeRemover.instances
    checkpoint = orch.STATE_DIR / "remove_bg.done.json"
    initial = checkpoint.read_bytes()
    assert json.loads(initial)["outcome"] == "no_work"
    fingerprint = orch.background_fingerprint()
    assert not orch.background_checkpoint_changed(fingerprint)
    marker("poster_ps1")
    marker("sync_images")
    photo(source / "First.jpg")
    photo(source / "Second.jpeg")
    assert orch.background_checkpoint_changed(fingerprint)
    assert call_main(monkeypatch, "--list") == 0
    assert checkpoint.read_bytes() == initial
    assert call_main(monkeypatch, "--stop-after", "poster_ps1") == 0
    assert sum("remove_bg_birefnet.py" in argv for argv in calls) == 2
    assert len(FakeRemover.instances) == 1 and len(FakeRemover.instances[0].calls) == 2
    assert FakeRemover.instances[0].closed
    assert (source / "First.png").exists() and (source / "Second.png").exists()
    assert not list(source.glob("*.jpg")) and not list(source.glob("*.jpeg"))
    assert not (orch.STATE_DIR / "sync_images.done.json").exists()
    assert json.loads(checkpoint.read_text())["outcome"] == "success"
    assert not orch.background_checkpoint_changed(fingerprint)


@pytest.mark.parametrize("suffix", sorted(backend.INPUT_EXTS) + [".WEBP"])
def test_local_recovery_blocks_all_pending_backend_formats_before_staging(monkeypatch, recovery_args, suffix):
    args = recovery_args
    args.all = True
    queued = args.downloads_dir / f"Pending{suffix}"
    photo(queued)
    original = queued.read_bytes()
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setattr(recovery, "parser", lambda: SimpleNamespace(parse_args=lambda: args))
    monkeypatch.setattr(recovery, "background_python", lambda default: default)
    monkeypatch.setattr(recovery, "find_recovery_targets", lambda *args, **kwargs: ([('Person', Path('unused'), 'headchop')], 0))
    monkeypatch.setattr(recovery, "stage_one_for_orchestrator", lambda *args: pytest.fail("Pending batch must not stage recovery"))
    monkeypatch.setattr(recovery, "run_orchestrator_from_remove_bg", lambda **kwargs: pytest.fail("Pending batch must not launch"))
    monkeypatch.setattr(recovery, "write_marker", lambda *args: pytest.fail("Pending batch must not checkpoint"))
    assert recovery.main() == 2
    assert queued.read_bytes() == original
    assert list(args.downloads_dir.iterdir()) == [queued]
    assert not FakeRemover.instances
    assert not (orch.STATE_DIR / "remove_bg.done.json").exists()


def test_adobe_recovery_retains_legacy_pending_format_guard(monkeypatch, recovery_args):
    args = recovery_args
    args.all = True
    args.precheck_rembg = False
    queued = args.downloads_dir / "Pending.webp"
    photo(queued)
    original = queued.read_bytes()
    monkeypatch.setattr(recovery, "parser", lambda: SimpleNamespace(parse_args=lambda: args))
    monkeypatch.setattr(recovery, "find_recovery_targets", lambda *args, **kwargs: ([('Person', Path('unused'), 'headchop')], 0))
    monkeypatch.setattr(recovery.requests, "Session", lambda: SimpleNamespace(close=lambda: None))
    staged = []

    def stage(*stage_args):
        staged.append(stage_args[3])
        return recovery.RecoveryRow(name="Person", status="exhausted")

    monkeypatch.setattr(recovery, "stage_one_for_orchestrator", stage)
    assert recovery.main() == 0
    assert staged == ["Person"]
    assert queued.read_bytes() == original


def test_inline_adobe_preserves_precheck_and_selenium_order(monkeypatch, recovery_args):
    args = recovery_args
    args.bg_engine = "adobe"
    args.rembg_session = object()
    prechecks, calls = [], []

    def remove(image, **kwargs):
        prechecks.append(kwargs)
        result = image.convert("RGBA")
        result.putalpha(128)
        return result

    monkeypatch.setitem(sys.modules, "rembg", SimpleNamespace(remove=remove))

    def run(title, argv, env):
        calls.append(argv)
        if "sel_remove_bg.py" in argv:
            src = Path(env["SEL_SRC_DIR"])
            cutout(src / "Person.png")
            shutil.move(src / "Person.jpg", Path(env["SEL_ORIG_DIR"]) / "Person.jpg")
        else:
            cutout(recovery.final_transparent_path(args.people_root, "Person"))
        return 0

    monkeypatch.setattr(recovery, "run_step", run)
    row = recovery.recover_one(args, SimpleNamespace(), "key", "Person", "headchop")
    assert row.status == "recovered"
    assert calls[0] == [sys.executable, "sel_remove_bg.py"]
    assert calls[1][0] == "mock-pwsh"
    assert prechecks[0]["session"] is args.rembg_session
    assert prechecks[0]["post_process_mask"] is args.rembg_post_process_mask
    assert not FakeRemover.instances


@pytest.mark.parametrize("precheck", [True, False])
def test_inline_local_reuses_one_model_and_one_inference_per_candidate(monkeypatch, recovery_args, precheck):
    args = recovery_args
    args.precheck_rembg = precheck
    calls = []

    def run(title, argv, env):
        calls.append(argv)
        assert "sel_remove_bg.py" not in argv
        cutout(recovery.final_transparent_path(args.people_root, "Person"))
        return 0

    checks = iter([["headchop"], [], []]) if precheck else iter([[], []])
    monkeypatch.setattr(recovery, "candidate_target_issues", lambda *args, **kwargs: next(checks))
    monkeypatch.setattr(recovery, "run_step", run)
    row = recovery.recover_one(args, SimpleNamespace(), "key", "Person", "headchop")
    assert row.status == "recovered"
    assert len(FakeRemover.instances) == 1
    assert len(FakeRemover.instances[0].calls) == (2 if precheck else 1)
    assert row.attempts == (2 if precheck else 1)
    assert len(calls) == 1  # Poster subprocess only.
    assert (Path(os.environ["SEL_ORIG_DIR"]) / "Person.jpg").is_file()
    assert FakeRemover.instances[0].settings.overwrite is True


def test_local_staging_reuses_precheck_and_records_attempt_order(monkeypatch, recovery_args):
    args = recovery_args
    checks = iter([["headchop"], []])
    monkeypatch.setattr(recovery, "candidate_target_issues", lambda *args, **kwargs: next(checks))
    monkeypatch.setattr(recovery, "run_step", lambda *args: pytest.fail("Unexpected subprocess"))
    attempted, records = set(), []
    row = recovery.stage_one_for_orchestrator(args, SimpleNamespace(), "key", "Person", "headchop", attempted, records)
    assert row.status == "staged" and row.chosen_label == "candidate1"
    assert [record.status for record in records] == ["precheck_rejected", "staged"]
    assert len(FakeRemover.instances) == 1 and len(FakeRemover.instances[0].calls) == 2
    staged = args.downloads_dir / "Person.png"
    assert staged.read_bytes() == (Path(os.environ["SEL_DOWNLOAD_DIR"]) / staged.name).read_bytes()
    assert backend.sidecar(staged).exists()
    assert not (args.downloads_dir / "Person.jpg").exists()


def test_local_staging_preserves_old_original_and_publishes_exact_basename(recovery_args):
    original = Path(os.environ["SEL_ORIG_DIR"]) / "Person.jpg"
    photo(original, color=(180, 10, 30))
    old_bytes = original.read_bytes()
    old_hash = backend.sha256(original)
    recovery.stage_one_for_orchestrator(recovery_args, SimpleNamespace(), "key", "Person", "headchop", set(), [])
    assert original.read_bytes() != old_bytes
    assert (original.parent / ".history" / old_hash / original.name).read_bytes() == old_bytes


def test_local_staging_requires_explicit_overwrite_for_existing_output(recovery_args):
    destination = Path(os.environ["SEL_DOWNLOAD_DIR"]) / "Person.png"
    cutout(destination)
    old_bytes = destination.read_bytes()
    with pytest.raises(RuntimeError, match="REMOVE_BG_OVERWRITE"):
        recovery.stage_one_for_orchestrator(recovery_args, SimpleNamespace(), "key", "Person", "headchop", set(), [])
    assert destination.read_bytes() == old_bytes
    assert not (Path(os.environ["SEL_ORIG_DIR"]) / "Person.jpg").exists()


def test_recovery_temp_overwrite_cannot_target_production_directory(recovery_args):
    args = recovery_args
    args.local_work_root = args.out_root / "temporary"
    with pytest.raises(RuntimeError, match="temporary work directory"):
        recovery.local_candidate(args, Path("source.jpg"), args.downloads_dir / "Person.png")
    assert not FakeRemover.instances


@pytest.mark.parametrize("override", [True, False])
def test_local_recovery_cache_override_preserves_primary_model_options(monkeypatch, recovery_args, tmp_path, override):
    args = recovery_args
    monkeypatch.setenv("REMOVE_BG_MODEL", "birefnet-general")
    monkeypatch.setenv("REMOVE_BG_ALPHA_MATTING", "true")
    monkeypatch.setenv("REMOVE_BG_DECONTAMINATE", "false")
    expected_home = Path(os.environ["REMBG_HOME"])
    if override:
        expected_home = tmp_path / "cli-model-cache"
        args.rembg_home = recovery.parser().parse_args(["--rembg-home", str(expected_home)]).rembg_home
    else:
        del args.rembg_home
    args.local_work_root = tmp_path / "temporary"
    source = args.local_work_root / "Person.jpg"
    photo(source)
    for index in range(2):
        recovery.local_candidate(args, source, args.local_work_root / f"candidate{index}.png")
    assert len(FakeRemover.instances) == 1
    settings = FakeRemover.instances[0].settings
    assert settings.home == expected_home
    assert settings.model == "birefnet-general"
    assert settings.alpha_matting is True and settings.decontaminate is False
    assert settings.overwrite is True
    assert not expected_home.exists()
    args.local_remover.close()


def test_recovery_failed_local_initialization_is_actionable(monkeypatch, recovery_args):
    monkeypatch.setattr(backend, "LocalRemover", lambda settings: (_ for _ in ()).throw(RuntimeError("missing model weights")))
    with pytest.raises(RuntimeError, match="missing model weights"):
        recovery.stage_one_for_orchestrator(recovery_args, SimpleNamespace(), "key", "Person", "headchop", set(), [])
    assert not (recovery_args.downloads_dir / "Person.png").exists()


def test_recovery_main_closes_shared_remover_and_locks_checkpoint(monkeypatch, recovery_args):
    args = recovery_args
    args.all = True
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setattr(recovery, "parser", lambda: SimpleNamespace(parse_args=lambda: args))
    monkeypatch.setattr(recovery, "background_python", lambda default: default)
    monkeypatch.setattr(recovery, "find_recovery_targets", lambda *args, **kwargs: ([('Person', Path('unused'), 'headchop')], 0))
    monkeypatch.setattr(recovery.requests, "Session", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(recovery, "postcheck_staged_outputs", lambda *args: 1)
    seen = []

    def locked_marker(path, meta):
        assert orch.LOCK_FILE.exists()
        orch.write_marker(path, meta)

    monkeypatch.setattr(recovery, "write_marker", locked_marker)
    monkeypatch.setattr(recovery, "run_orchestrator_from_remove_bg", lambda **kwargs: seen.append(kwargs) or 0)
    assert recovery.main() == 0
    assert seen == [{"stop_after": "poster_ps1", "background_ready": True}]
    assert FakeRemover.instances[0].closed
    assert not orch.LOCK_FILE.exists()
    assert json.loads((orch.STATE_DIR / "remove_bg.done.json").read_text())["background_fingerprint"]["engine"] == "birefnet"


def test_local_postcheck_and_cleanup_use_generated_tree_not_reference_clone(monkeypatch, recovery_args):
    args = recovery_args
    args.all = True
    reference = args.people_root
    original = reference / "original" / "P" / "Images" / "Person.jpg"
    transparent = recovery.final_transparent_path(reference, "Person")
    photo(original)
    cutout(transparent)
    before = {path.relative_to(reference): path.read_bytes() for path in reference.rglob("*") if path.is_file()}
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setattr(recovery, "parser", lambda: SimpleNamespace(parse_args=lambda: args))
    monkeypatch.setattr(recovery, "background_python", lambda default: default)
    monkeypatch.setattr(recovery, "find_recovery_targets", lambda *args, **kwargs: ([('Person', transparent, 'headchop')], 0))
    monkeypatch.setattr(recovery.requests, "Session", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(recovery, "run_orchestrator_from_remove_bg", lambda **kwargs: 0)
    roots = []

    def postcheck(rows, checked_args):
        roots.append(checked_args.people_root)
        rows[0].status = "unresolved"
        return 1

    monkeypatch.setattr(recovery, "postcheck_staged_outputs", postcheck)
    actual_cleanup = recovery.remove_unresolved_work_outputs

    def cleanup(rows, root):
        roots.append(root)
        return actual_cleanup(rows, root)

    monkeypatch.setattr(recovery, "remove_unresolved_work_outputs", cleanup)
    assert recovery.main() == 1
    assert roots == [recovery.CONFIG_DIR / "people_dirs"] * 2
    assert {path.relative_to(reference): path.read_bytes() for path in reference.rglob("*") if path.is_file()} == before


def test_inline_main_preserves_reference_files_and_accepted_original(monkeypatch, recovery_args):
    args = recovery_args
    args.inline = True
    args.all = True
    reference = args.people_root
    transparent = recovery.final_transparent_path(reference, "Person")
    cutout(transparent)
    before = transparent.read_bytes()
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setattr(recovery, "parser", lambda: SimpleNamespace(parse_args=lambda: args))
    monkeypatch.setattr(recovery, "background_python", lambda default: default)
    monkeypatch.setattr(recovery, "find_recovery_targets", lambda *args, **kwargs: ([('Person', transparent, 'headchop')], 0))
    monkeypatch.setattr(recovery.requests, "Session", lambda: SimpleNamespace(close=lambda: None))

    def run(title, argv, env):
        assert "sel_remove_bg.py" not in argv
        cutout(recovery.final_transparent_path(recovery.CONFIG_DIR / "people_dirs", "Person"))
        return 0

    monkeypatch.setattr(recovery, "run_step", run)
    assert recovery.main() == 0
    assert transparent.read_bytes() == before
    assert (Path(os.environ["SEL_ORIG_DIR"]) / "Person.jpg").is_file()
    assert FakeRemover.instances[0].closed


def test_inline_local_keeps_originals_until_accepted_source_is_archived(monkeypatch, recovery_args):
    args = recovery_args
    args.people_root = recovery.CONFIG_DIR / "people_dirs"
    archive = Path(os.environ["SEL_ORIG_DIR"])
    originals = [archive / "Person.jpg", archive / "P" / "Images" / "Person.jpg"]
    for index, path in enumerate(originals):
        photo(path, color=(180, 20 + index * 40, 10))
    preserved = [(path, path.read_bytes(), backend.sha256(path)) for path in originals]
    source_jpg = args.people_root / "Downloads" / "Person.jpg"
    photo(source_jpg, color=(5, 170, 20))
    source_bytes = source_jpg.read_bytes()

    def download(session, candidate, target):
        for path, content, digest in preserved:
            assert path.read_bytes() == content
        assert source_jpg.read_bytes() == source_bytes
        photo(target)

    monkeypatch.setattr(recovery, "download_candidate", download)
    monkeypatch.setattr(recovery, "run_step", lambda title, argv, env: cutout(recovery.final_transparent_path(args.people_root, "Person")) or 0)
    row = recovery.recover_one(args, SimpleNamespace(), "key", "Person", "headchop")
    assert row.status == "recovered"
    for path, content, digest in preserved:
        assert (archive / ".history" / digest / path.name).read_bytes() == content
    assert (archive / "Person.jpg").read_bytes() == (args.out_root / "candidates" / "Person" / "candidate0.jpg").read_bytes()
    assert source_jpg.read_bytes() == source_bytes
    assert not args.local_work_root.exists()


@pytest.mark.parametrize("engine", ["adobe", "birefnet"])
def test_unresolved_cleanup_preserves_sources_only_for_local(monkeypatch, recovery_args, engine):
    monkeypatch.setenv("REMOVE_BG_ENGINE", engine)
    root = recovery.CONFIG_DIR / "people_dirs"
    originals = [root / "original" / "Person.jpg", root / "original" / "P" / "Images" / "Person.jpg",
                 root / "Downloads" / "Person.jpg"]
    for path in originals:
        photo(path)
    history = root / "original" / ".history" / "old" / "Person.jpg"
    photo(history)
    generated = [root / "transparent" / "P" / "Images" / "Person.png", root / "bw" / "Person.jpg",
                 root / "Downloads" / "Person.png"]
    for path in generated:
        cutout(path) if path.suffix == ".png" else photo(path)
    preserved = {path: path.read_bytes() for path in originals + [history]}
    row = recovery.RecoveryRow(name="Person", status="unresolved", chosen_url="candidate-url")
    recovery.remove_unresolved_work_outputs([row], root)
    assert all(not path.exists() for path in generated)
    if engine == "birefnet":
        assert all(path.read_bytes() == content for path, content in preserved.items())
    else:
        assert all(not path.exists() for path in originals)
        assert history.read_bytes() == preserved[history]


@pytest.mark.parametrize("inline", [False, True])
@pytest.mark.parametrize("status,expected", [("unresolved", 1), ("exhausted", 0), ("error", 2)])
def test_local_recovery_status_distinguishes_exhaustion_from_failure(monkeypatch, recovery_args, status, expected, inline):
    args = recovery_args
    args.all = True
    args.inline = inline
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setattr(recovery, "parser", lambda: SimpleNamespace(parse_args=lambda: args))
    monkeypatch.setattr(recovery, "background_python", lambda default: default)
    monkeypatch.setattr(recovery, "find_recovery_targets", lambda *args, **kwargs: ([('Person', Path('unused'), 'headchop')], 0))
    monkeypatch.setattr(recovery.requests, "Session", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(recovery, "stage_one_for_orchestrator", lambda *args: recovery.RecoveryRow(name="Person", status=status))
    monkeypatch.setattr(recovery, "recover_one", lambda *args: recovery.RecoveryRow(name="Person", status=status))
    assert recovery.main() == expected


@pytest.mark.parametrize("failure,expected", [("fatal", 2), ("unresolved", 1)])
def test_partial_local_staging_failure_preserves_inputs_without_launch_or_checkpoint(monkeypatch, recovery_args, failure, expected):
    args = recovery_args
    args.all = True
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setattr(recovery, "parser", lambda: SimpleNamespace(parse_args=lambda: args))
    monkeypatch.setattr(recovery, "background_python", lambda default: default)
    monkeypatch.setattr(recovery, "find_recovery_targets", lambda *args, **kwargs: ([('First', Path('unused'), 'headchop'), ('Second', Path('unused'), 'headchop')], 0))
    monkeypatch.setattr(recovery.requests, "Session", lambda: SimpleNamespace(close=lambda: None))
    stage = recovery.stage_one_for_orchestrator

    def stage_then_fail(*stage_args):
        if stage_args[3] == "Second":
            if failure == "fatal":
                raise RuntimeError("fatal inference failure")
            return recovery.RecoveryRow(name="Second", status=failure)
        return stage(*stage_args)

    monkeypatch.setattr(recovery, "stage_one_for_orchestrator", stage_then_fail)
    monkeypatch.setattr(recovery, "run_orchestrator_from_remove_bg", lambda **kwargs: pytest.fail("Partial failed batch must not launch"))
    monkeypatch.setattr(recovery, "write_marker", lambda *args: pytest.fail("Partial failed batch must not checkpoint"))
    assert recovery.main() == expected
    assert (args.downloads_dir / "First.png").is_file()
    assert (Path(os.environ["SEL_ORIG_DIR"]) / "First.jpg").is_file()
    assert FakeRemover.instances[0].closed
    assert not (orch.STATE_DIR / "remove_bg.done.json").exists()


def test_exhausted_search_does_not_block_accepted_staged_candidates(monkeypatch, recovery_args):
    args = recovery_args
    args.all = True
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setattr(recovery, "parser", lambda: SimpleNamespace(parse_args=lambda: args))
    monkeypatch.setattr(recovery, "background_python", lambda default: default)
    monkeypatch.setattr(recovery, "find_recovery_targets", lambda *args, **kwargs: (
        [("First", Path("unused"), "headchop"), ("Second", Path("unused"), "headchop")], 0))
    monkeypatch.setattr(recovery.requests, "Session", lambda: SimpleNamespace(close=lambda: None))
    stage = recovery.stage_one_for_orchestrator

    def stage_then_exhaust(*stage_args):
        if stage_args[3] == "Second":
            return recovery.RecoveryRow(name="Second", status="exhausted", initial_issues="headchop")
        return stage(*stage_args)

    monkeypatch.setattr(recovery, "stage_one_for_orchestrator", stage_then_exhaust)
    calls = []
    monkeypatch.setattr(recovery, "run_orchestrator_from_remove_bg", lambda **kwargs: calls.append(kwargs) or 0)

    def postcheck(rows, check_args):
        assert rows[1].status == "exhausted"
        rows[0].status = "recovered"
        return 1

    monkeypatch.setattr(recovery, "postcheck_staged_outputs", postcheck)
    monkeypatch.setattr(recovery, "run_orchestrator_from_update", lambda: calls.append("sync") or 0)
    assert recovery.main() == 0
    assert calls == [{"stop_after": "poster_ps1", "background_ready": True}, "sync"]
    assert (args.downloads_dir / "First.png").is_file()
    assert not (args.downloads_dir / "Second.png").exists()
    assert (Path(os.environ["SEL_ORIG_DIR"]) / "First.jpg").is_file()
    assert FakeRemover.instances[0].closed


@pytest.mark.parametrize("has_candidates", [False, True])
def test_inline_exhaustion_preserves_posters_sources_and_warning_report(monkeypatch, recovery_args, has_candidates):
    args = recovery_args
    args.inline = True
    args.all = True
    args.precheck_rembg = True
    root = orch.CONFIG_DIR / "people_dirs"
    args.people_root = root
    args.transparent_root = root / "transparent"
    transparent = recovery.final_transparent_path(root, "Person")
    cutout(transparent)
    for style in ("bw", "diiivoy", "diiivoycolor", "rainier", "signature", "original"):
        photo(root / style / "P" / "Images" / "Person.jpg")
    previous = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    if not has_candidates:
        monkeypatch.setattr(recovery, "tmdb_candidates", lambda *args: [])
    monkeypatch.setattr(recovery, "candidate_target_issues", lambda *args, **kwargs: ["headchop"])
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setattr(recovery, "parser", lambda: SimpleNamespace(parse_args=lambda: args))
    monkeypatch.setattr(recovery, "background_python", lambda default: default)
    monkeypatch.setattr(recovery, "find_recovery_targets", lambda *args, **kwargs: (
        [("Person", transparent, "headchop")], 0))
    monkeypatch.setattr(recovery.requests, "Session", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(recovery, "run_step", lambda *args: pytest.fail("Rejected candidates must not render or use Adobe"))
    monkeypatch.setattr(recovery, "run_orchestrator_from_remove_bg", lambda **kwargs: pytest.fail("Inline recovery must not launch another orchestrator"))
    monkeypatch.setattr(recovery, "write_marker", lambda *args: pytest.fail("Inline recovery must not checkpoint a replacement"))
    assert recovery.main() == 0
    assert all(path.read_bytes() == content for path, content in previous.items())
    assert recovery.load_exhausted_names(args.exhausted_file) == {"person"}
    with (args.out_root / "edge_chop_recovery.csv").open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row["status"] == "exhausted"
    assert row["initial_issues"] == "headchop"
    assert not row["chosen_url"]
    if has_candidates:
        assert row["final_issues"] == "headchop"
        assert row["precheck_rejected"] == "2"
        assert "before Adobe" not in row["note"]
        assert FakeRemover.instances[0].closed


def test_inline_poster_failure_is_fatal_and_restores_existing_outputs(monkeypatch, recovery_args):
    args = recovery_args
    args.inline = True
    args.all = True
    root = orch.CONFIG_DIR / "people_dirs"
    args.people_root = root
    transparent = recovery.final_transparent_path(root, "Person")
    cutout(transparent)
    poster = root / "bw" / "P" / "Images" / "Person.jpg"
    original = root / "original" / "P" / "Images" / "Person.jpg"
    photo(poster)
    photo(original)
    previous = {path: path.read_bytes() for path in (transparent, poster, original)}
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setattr(recovery, "parser", lambda: SimpleNamespace(parse_args=lambda: args))
    monkeypatch.setattr(recovery, "background_python", lambda default: default)
    monkeypatch.setattr(recovery, "find_recovery_targets", lambda *args, **kwargs: (
        [("Person", transparent, "headchop")], 0))
    monkeypatch.setattr(recovery.requests, "Session", lambda: SimpleNamespace(close=lambda: None))

    def failed_poster(title, argv, env):
        assert "sel_remove_bg.py" not in argv
        photo(poster, color=(210, 80, 20))
        return 7

    monkeypatch.setattr(recovery, "run_step", failed_poster)
    assert recovery.main() == 2
    assert all(path.read_bytes() == content for path, content in previous.items())
    assert not (args.downloads_dir / "Person.png").exists()
    assert not recovery.load_exhausted_names(args.exhausted_file)
    assert len(FakeRemover.instances[0].calls) == 1
    assert FakeRemover.instances[0].closed
    with (args.out_root / "edge_chop_recovery.csv").open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row["status"] == "error"
    assert "poster generation failed with exit code 7" in row["note"]


@pytest.mark.parametrize("scope", [[], ["--audit-only", "--all"]])
def test_recovery_no_work_does_not_initialize_models(monkeypatch, recovery_args, scope):
    args = recovery_args
    args.audit_only = "--audit-only" in scope
    args.all = "--all" in scope
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setattr(recovery, "parser", lambda: SimpleNamespace(parse_args=lambda: args))
    monkeypatch.setattr(recovery, "background_python", lambda default: default)
    monkeypatch.setattr(recovery, "find_recovery_targets", lambda *args, **kwargs: ([], 0))
    assert recovery.main() == 0
    assert not FakeRemover.instances


@pytest.mark.parametrize("engine,ready,step", [("adobe", False, "remove_bg"), ("birefnet", False, "remove_bg"),
                                              ("birefnet", True, "poster_ps1")])
def test_recovery_batch_command_selects_python_and_reuses_ready_cutout(monkeypatch, engine, ready, step):
    monkeypatch.setenv("REMOVE_BG_ENGINE", engine)
    monkeypatch.setattr(recovery, "background_python", lambda default: "local-python")
    calls = []
    monkeypatch.setattr(recovery, "run_step", lambda title, argv, env: calls.append(argv) or 0)
    assert recovery.run_orchestrator_from_remove_bg("poster_ps1", background_ready=ready) == 0
    assert calls[0][:4] == ["local-python" if engine == "birefnet" else sys.executable,
                           "orchestrator.py", "--redo", step]
