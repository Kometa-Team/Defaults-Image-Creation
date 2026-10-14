from __future__ import annotations

import os
import sys
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

    def loader():
        raise AssertionError("model should not load when every output is valid")

    code, _, _ = run_ddcolor_main(monkeypatch, tmp_path, loader)

    assert code == 0
    assert (input_dir / "skip.bmp").exists()


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
    probes: list[tuple[tuple[str, ...], str, bool]] = []

    def fake_probe(prefix, engine, require_colorize_deps):
        probes.append((tuple(prefix), engine, require_colorize_deps))
        return True, "ok"

    monkeypatch.setattr(orchestrator, "_python_probe", fake_probe)

    argv = orchestrator.build_colorize_command("current-python")

    assert argv == ["C:/Python313/python.exe", "colorize_noncolor_ddcolor.py"]
    assert probes == [(("C:/Python313/python.exe",), "ddcolor", True)]


def test_orchestrator_selects_deoldify_backend(monkeypatch):
    monkeypatch.setenv("COLORIZE_ENGINE", "deoldify")
    monkeypatch.setenv("COLORIZE_PYTHON", "C:/Python310/python.exe")
    monkeypatch.setattr(orchestrator, "_colorize_candidates_exist", lambda: True)

    def fake_probe(prefix, engine, require_colorize_deps):
        assert engine == "deoldify"
        assert require_colorize_deps is True
        return True, "ok"

    monkeypatch.setattr(orchestrator, "_python_probe", fake_probe)

    assert orchestrator.build_colorize_command("current-python") == [
        "C:/Python310/python.exe",
        "colorize_noncolor.py",
    ]


def test_recover_edge_chops_uses_ddcolor_script(monkeypatch, tmp_path):
    monkeypatch.setenv("COLORIZE_ENGINE", "ddcolor")
    monkeypatch.setattr(recover_edge_chops, "colorize_python_candidates", lambda engine=None: [["python313"]])
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


def test_checkpoint_clear_from_preserves_upstream_and_clears_downstream(monkeypatch, tmp_path):
    monkeypatch.setattr(orchestrator, "STATE_DIR", tmp_path)
    keys = ["scan", "colorize", "prep_dirs"]
    for key in keys:
        (tmp_path / f"{key}.done.json").write_text("{}", encoding="utf-8")

    orchestrator.clear_from(keys, "colorize")

    assert (tmp_path / "scan.done.json").exists()
    assert not (tmp_path / "colorize.done.json").exists()
    assert not (tmp_path / "prep_dirs.done.json").exists()
