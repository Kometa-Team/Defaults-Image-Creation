from __future__ import annotations

import os
import io
import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    import numpy  # noqa: F401
except ModuleNotFoundError:
    sys.modules["numpy"] = SimpleNamespace()

import colorize_noncolor_ddcolor as ddcolor
import orchestrator
import recover_edge_chops


def make_image(path: Path, size: tuple[int, int] = (32, 48), color=(120, 120, 120)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)


def run_ddcolor_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, loader):
    input_dir = tmp_path / "other"
    output_dir = tmp_path / "color"
    monkeypatch.setattr(ddcolor, "IN_OTHER", input_dir)
    monkeypatch.setattr(ddcolor, "OUT_COLOR", output_dir)
    monkeypatch.setattr(ddcolor, "load_colorizer", loader)
    with pytest.raises(SystemExit) as exc:
        ddcolor.main()
    return exc.value.code, input_dir, output_dir


class FakeColorizer:
    def colorize(self, src: Path, dst: Path, quality: int) -> None:
        with Image.open(src) as image:
            image = image.convert("RGB")
            tinted = Image.new("RGB", image.size, (10, 80, 160))
        ddcolor.save_jpeg(tinted, dst, quality)


def test_first_vendor_download_is_importable_and_reused(monkeypatch, tmp_path):
    vendor_dir = tmp_path / "vendor"
    package_dir = vendor_dir / "DDColor"
    monkeypatch.setattr(ddcolor, "VENDOR_DIR", vendor_dir)
    monkeypatch.setattr(ddcolor, "DDCOLOR_VENDOR_DIR", package_dir)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delitem(sys.modules, "ddcolor", raising=False)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as source:
        source.writestr("DDColor-master/", "")
        source.writestr("DDColor-master/ddcolor/__init__.py", "VENDORED = True\n")
    downloads = []

    def download(url, timeout):
        downloads.append(url)
        return archive.getvalue()

    monkeypatch.setattr(ddcolor, "http_get", download)
    try:
        ddcolor.ensure_ddcolor_on_path()
        assert sys.modules["ddcolor"].VENDORED is True
        assert Path(sys.modules["ddcolor"].__file__).parent == package_dir / "ddcolor"
        ddcolor.ensure_ddcolor_on_path()
        assert len(downloads) == 1
    finally:
        sys.modules.pop("ddcolor", None)


def test_missing_vendor_dependency_does_not_redownload_source(monkeypatch, tmp_path):
    vendor_dir = tmp_path / "vendor"
    package_dir = vendor_dir / "DDColor"
    module_dir = package_dir / "ddcolor"
    module_dir.mkdir(parents=True)
    (module_dir / "__init__.py").write_text(
        "import missing_ddcolor_inference_dependency\n", encoding="utf-8"
    )
    monkeypatch.setattr(ddcolor, "VENDOR_DIR", vendor_dir)
    monkeypatch.setattr(ddcolor, "DDCOLOR_VENDOR_DIR", package_dir)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delitem(sys.modules, "ddcolor", raising=False)

    def download(*args, **kwargs):
        raise AssertionError("missing dependencies must not trigger source downloads")

    monkeypatch.setattr(ddcolor, "http_get", download)
    with pytest.raises(SystemExit) as exc:
        ddcolor.ensure_ddcolor_on_path()
    assert exc.value.code == 2


@pytest.mark.parametrize("wrapped", [False, True])
def test_cached_bin_weights_load_with_official_config(monkeypatch, tmp_path, wrapped):
    config = {"encoder_name": "convnext-l", "num_output_channels": 2}
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    state_dict = {"encoder.weight": object()}
    calls = {}

    def load(path, **kwargs):
        calls["load"] = (path, kwargs)
        return {"params": state_dict} if wrapped else state_dict

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(load=load))

    class Model:
        def __init__(self, **kwargs):
            calls["config"] = kwargs

        def load_state_dict(self, weights, strict):
            assert weights is state_dict
            calls["strict"] = strict

    assert isinstance(ddcolor.load_cached_model(Model, tmp_path), Model)
    assert calls["config"] == config
    assert calls["load"] == (
        tmp_path / "pytorch_model.bin",
        {"map_location": "cpu", "weights_only": True, "mmap": True},
    )
    assert calls["strict"] is True


def test_successful_single_image_preserves_name_and_dimensions(monkeypatch, tmp_path):
    input_dir = tmp_path / "other"
    make_image(input_dir / "Ada Lovelace.png", size=(41, 59))

    code, _, output_dir = run_ddcolor_main(monkeypatch, tmp_path, lambda: FakeColorizer())

    output = output_dir / "Ada Lovelace.jpg"
    assert code == 0
    assert output.exists()
    assert not (input_dir / "Ada Lovelace.png").exists()
    with Image.open(output) as image:
        assert image.format == "JPEG"
        assert image.size == (41, 59)


def test_successful_batch_loads_model_once(monkeypatch, tmp_path):
    input_dir = tmp_path / "other"
    make_image(input_dir / "one.jpg")
    make_image(input_dir / "two.webp")
    loads = {"count": 0}

    def loader():
        loads["count"] += 1
        return FakeColorizer()

    code, _, output_dir = run_ddcolor_main(monkeypatch, tmp_path, loader)

    assert code == 0
    assert loads["count"] == 1
    assert (output_dir / "one.jpg").exists()
    assert (output_dir / "two.jpg").exists()


def test_existing_valid_output_is_skipped_without_loading_model(monkeypatch, tmp_path):
    input_dir = tmp_path / "other"
    output_dir = tmp_path / "color"
    make_image(input_dir / "skip.bmp", size=(25, 31))
    make_image(output_dir / "skip.jpg", size=(25, 31), color=(40, 90, 140))
    existing_output = (output_dir / "skip.jpg").read_bytes()

    def loader():
        raise AssertionError("model should not load when every output is valid")

    code, _, _ = run_ddcolor_main(monkeypatch, tmp_path, loader)

    assert code == 0
    assert not (input_dir / "skip.bmp").exists()
    assert (output_dir / "skip.jpg").read_bytes() == existing_output


def test_rerun_removes_grayscale_copy_for_existing_colorized_jpeg(monkeypatch, tmp_path):
    input_dir = tmp_path / "other"
    make_image(input_dir / "rerun.jpg", size=(25, 31))
    code, _, output_dir = run_ddcolor_main(monkeypatch, tmp_path, lambda: FakeColorizer())
    assert code == 0
    existing_output = (output_dir / "rerun.jpg").read_bytes()
    make_image(input_dir / "rerun.jpg", size=(25, 31))

    def loader():
        raise AssertionError("rerun must reuse the validated output")

    code, _, _ = run_ddcolor_main(monkeypatch, tmp_path, loader)

    assert code == 0
    assert not (input_dir / "rerun.jpg").exists()
    assert (output_dir / "rerun.jpg").read_bytes() == existing_output


@pytest.mark.parametrize("existing_output", [False, True])
def test_source_removal_failure_stops_downstream_processing(monkeypatch, tmp_path, existing_output):
    src = tmp_path / "other" / "locked.jpg"
    dst = tmp_path / "color" / "locked.jpg"
    make_image(src)
    if existing_output:
        make_image(dst, color=(40, 90, 140))
    original_unlink = Path.unlink

    def unlink(path, *args, **kwargs):
        if path == src:
            raise PermissionError("source is locked")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)
    code, _, _ = run_ddcolor_main(monkeypatch, tmp_path, lambda: FakeColorizer())

    assert code == 1
    assert src.exists()
    assert ddcolor.valid_output(dst, expected_size=(32, 48))


def test_corrupt_existing_output_is_regenerated(monkeypatch, tmp_path):
    input_dir = tmp_path / "other"
    output_dir = tmp_path / "color"
    make_image(input_dir / "repair.tiff", size=(20, 30))
    output_dir.mkdir(parents=True)
    (output_dir / "repair.jpg").write_bytes(b"not a jpeg")

    code, _, _ = run_ddcolor_main(monkeypatch, tmp_path, lambda: FakeColorizer())

    assert code == 0
    assert not (input_dir / "repair.tiff").exists()
    assert ddcolor.valid_output(output_dir / "repair.jpg", expected_size=(20, 30))


def test_failure_propagates_and_preserves_source(monkeypatch, tmp_path):
    input_dir = tmp_path / "other"
    make_image(input_dir / "broken.jpeg")

    class FailingColorizer:
        def colorize(self, src: Path, dst: Path, quality: int) -> None:
            raise RuntimeError("model failure")

    code, _, output_dir = run_ddcolor_main(monkeypatch, tmp_path, lambda: FailingColorizer())

    assert code == 1
    assert (input_dir / "broken.jpeg").exists()
    assert not (output_dir / "broken.jpg").exists()


def test_empty_input_directory_exits_zero_without_model(monkeypatch, tmp_path):
    (tmp_path / "other").mkdir()

    def loader():
        raise AssertionError("model should not load for an empty input directory")

    code, _, _ = run_ddcolor_main(monkeypatch, tmp_path, loader)

    assert code == 0


def test_orchestrator_selects_ddcolor_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("COLORIZE_ENGINE", "ddcolor")
    monkeypatch.setenv("COLORIZE_PYTHON", "C:/Python313/python.exe")
    monkeypatch.setattr(orchestrator, "_colorize_candidates_exist", lambda: True)
    probes: list[tuple[tuple[str, ...], bool]] = []

    def fake_probe(prefix, require_colorize_deps):
        probes.append((tuple(prefix), require_colorize_deps))
        return True, "ok"

    monkeypatch.setattr(orchestrator, "_python_probe", fake_probe)

    argv = orchestrator.build_colorize_command("current-python")

    assert argv == ["C:/Python313/python.exe", "colorize_noncolor_ddcolor.py"]
    assert probes == [(("C:/Python313/python.exe",), True)]


def test_orchestrator_rejects_unsupported_backend_before_launch(monkeypatch):
    monkeypatch.setenv("COLORIZE_ENGINE", "legacy")

    def fake_probe(*args, **kwargs):
        raise AssertionError("an unsupported backend must not launch an interpreter")

    monkeypatch.setattr(orchestrator, "_python_probe", fake_probe)

    with pytest.raises(SystemExit) as exc:
        orchestrator.build_colorize_command("current-python")
    assert exc.value.code == 2


@pytest.mark.parametrize("setting", [None, "", " DDColor "])
def test_ddcolor_is_the_default_and_only_backend(monkeypatch, setting):
    if setting is None:
        monkeypatch.delenv("COLORIZE_ENGINE", raising=False)
    else:
        monkeypatch.setenv("COLORIZE_ENGINE", setting)
    assert orchestrator._colorize_engine() == "ddcolor"
    assert recover_edge_chops.colorize_engine() == "ddcolor"


def test_both_runners_prefer_local_ddcolor_environment(monkeypatch):
    monkeypatch.delenv("COLORIZE_PYTHON", raising=False)
    suffix = "Scripts/python.exe" if sys.platform.startswith("win") else "bin/python"
    expected = str(SCRIPT_DIR / ".venv-ddcolor" / suffix)
    assert orchestrator._colorize_python_candidates("pipeline-python")[0][1] == [expected]
    assert recover_edge_chops.colorize_python_candidates()[0] == [expected]


def test_orchestrator_dependency_failure_propagates(monkeypatch):
    monkeypatch.setenv("COLORIZE_ENGINE", "ddcolor")
    monkeypatch.setattr(orchestrator, "_colorize_candidates_exist", lambda: True)
    monkeypatch.setattr(orchestrator, "_colorize_python_candidates", lambda python: [("test", [python])])
    monkeypatch.setattr(orchestrator, "_python_probe", lambda *args, **kwargs: (False, "missing dependencies"))
    with pytest.raises(SystemExit) as exc:
        orchestrator.build_colorize_command("pipeline-python")
    assert exc.value.code == 2


def test_recovery_rejects_unsupported_backend_before_staging(monkeypatch, tmp_path):
    monkeypatch.setenv("COLORIZE_ENGINE", "legacy")
    work_root = tmp_path / "work"
    with pytest.raises(ValueError, match="Only DDColor is supported"):
        recover_edge_chops.colorize_candidate(tmp_path / "Person.jpg", work_root)
    assert not work_root.exists()


def test_recover_edge_chops_uses_ddcolor_script(monkeypatch, tmp_path):
    monkeypatch.setenv("COLORIZE_ENGINE", "ddcolor")
    monkeypatch.setattr(recover_edge_chops, "colorize_python_candidates", lambda: [["python313"]])
    staged = tmp_path / "Person.jpg"
    make_image(staged, size=(40, 60))
    seen = {}

    def fake_run(argv, cwd, env, text, encoding, errors, stdout, stderr, timeout):
        seen["argv"] = argv
        out = Path(env["COLORIZE_OUTPUT_COLOR"]) / staged.name
        make_image(out, size=(40, 60), color=(30, 100, 180))
        return SimpleNamespace(returncode=0, stdout="ok")

    monkeypatch.setattr(recover_edge_chops.subprocess, "run", fake_run)

    ok, note = recover_edge_chops.colorize_candidate(staged, tmp_path / "work")

    assert ok is True
    assert seen["argv"] == ["python313", "colorize_noncolor_ddcolor.py"]
    assert "DDColor colorized" in note


def test_recovery_ddcolor_failure_preserves_staged_source(monkeypatch, tmp_path):
    monkeypatch.setenv("COLORIZE_ENGINE", "ddcolor")
    monkeypatch.setattr(recover_edge_chops, "colorize_python_candidates", lambda: [["python313"]])
    staged = tmp_path / "Person.jpg"
    make_image(staged)
    original = staged.read_bytes()
    monkeypatch.setattr(
        recover_edge_chops.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="model failure"),
    )
    ok, note = recover_edge_chops.colorize_candidate(staged, tmp_path / "work")
    assert ok is False
    assert "DDColor failed" in note
    assert staged.read_bytes() == original


def test_checkpoint_clear_from_preserves_upstream_and_clears_downstream(monkeypatch, tmp_path):
    monkeypatch.setattr(orchestrator, "STATE_DIR", tmp_path)
    keys = ["scan", "colorize", "prep_dirs"]
    for key in keys:
        (tmp_path / f"{key}.done.json").write_text("{}", encoding="utf-8")

    orchestrator.clear_from(keys, "colorize")

    assert (tmp_path / "scan.done.json").exists()
    assert not (tmp_path / "colorize.done.json").exists()
    assert not (tmp_path / "prep_dirs.done.json").exists()
