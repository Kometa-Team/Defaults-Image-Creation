"""Synthetic-only sweeper regressions, including the actual standalone CLI."""

import hashlib
from contextlib import contextmanager
import importlib.util
import logging
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

from PIL import Image
import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "grayscale_sweeper.py"
METHODS = ("exact", "sat", "satq", "colorfulness", "auto")


@pytest.fixture(scope="module")
def sweeper():
    spec = importlib.util.spec_from_file_location("tested_grayscale_sweeper", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def image(path, color=90, mode="L"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with Image.new(mode, (10, 10), color) as img:
        img.save(path, format="PNG")
    return path


def cli(root, destination, *args, env=None):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), "--src", str(root),
                           "--dest-other", str(destination), *args],
                          cwd=root.parent, capture_output=True, text=True, timeout=30, env=env)


def counts(output):
    match = re.search(r"Scanned: (\d+) \| Non-color found: (\d+) \| Placed: (\d+) \| Collisions: (\d+) \| Errors: (\d+)", output)
    assert match, output
    return tuple(map(int, match.groups()))


def test_compilation_import_and_help_are_side_effect_free(tmp_path, monkeypatch):
    compile(SCRIPT.read_bytes(), str(SCRIPT), "exec")
    copied = tmp_path / "grayscale_sweeper.py"
    shutil.copy2(SCRIPT, copied)
    log = tmp_path / "config/logs/grayscale_sweeper.log"
    log.parent.mkdir(parents=True)
    log.write_bytes(b"existing log must survive imports")
    before = {p.relative_to(tmp_path) for p in tmp_path.rglob("*")}
    handlers = tuple(logging.getLogger().handlers)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    spec = importlib.util.spec_from_file_location("isolated_sweeper_import", copied)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert tuple(logging.getLogger().handlers) == handlers
    assert log.read_bytes() == b"existing log must survive imports"
    assert {p.relative_to(tmp_path) for p in tmp_path.rglob("*")} == before
    result = subprocess.run([sys.executable, "-B", str(copied), "--help"],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0
    assert all(method in result.stdout for method in METHODS)
    assert all(option in result.stdout for option in ("--src", "--dest-other", "--move", "--overwrite",
               "--exts", "--sat-threshold", "--sat-quantile", "--colorfulness-cutoff"))
    assert {p.relative_to(tmp_path) for p in tmp_path.rglob("*")} == before


@pytest.mark.parametrize("args", [[], ["--src"], ["--method", "unknown"]])
def test_missing_required_arguments(tmp_path, args):
    result = subprocess.run([sys.executable, "-B", str(SCRIPT), *args], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 2 and "error:" in result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("flag,value", [
    ("--sat-threshold", "-1"), ("--sat-threshold", "256"), ("--sat-threshold", "1.5"),
    ("--sat-quantile", "0"), ("--sat-quantile", "-0.1"), ("--sat-quantile", "1.01"),
    ("--sat-quantile", "nan"), ("--sat-quantile", "inf"),
    ("--colorfulness-cutoff", "-1"), ("--colorfulness-cutoff", "nan"),
    ("--colorfulness-cutoff", "inf"), ("--colorfulness-cutoff", "not-a-number"),
    ("--exts", ""), ("--exts", "../png"), ("--method", "unknown"),
])
def test_invalid_arguments_fail_before_output_creation(tmp_path, flag, value):
    root = tmp_path / "src"; root.mkdir()
    destination = tmp_path / "out"
    result = cli(root, destination, flag, value)
    assert result.returncode == 2 and "error:" in result.stderr
    assert not destination.exists()


@pytest.mark.parametrize("threshold", ["0", "255"])
def test_valid_argument_boundaries(tmp_path, threshold):
    root = tmp_path / "src"; root.mkdir()
    result = cli(root, tmp_path / "out", "--sat-threshold", threshold,
                 "--sat-quantile", "1", "--colorfulness-cutoff", "0")
    assert result.returncode == 0 and counts(result.stdout) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize("method", METHODS)
def test_actual_cli_five_methods_modes_transparency_and_byte_exact_copy(tmp_path, method):
    root, destination = tmp_path / "src", tmp_path / "out"
    selected = [image(root / "gray-RGB.PNG", (90, 90, 90), "RGB"),
                image(root / "gray-L.png"), image(root / "gray-LA.png", (90, 0), "LA"),
                image(root / "gray-RGBA.png", (90, 90, 90, 96), "RGBA"),
                image(root / "gray-transparent.png", (90, 90, 90, 0), "RGBA"),
                image(root / "gray-bilevel.png", 1, "1")]
    colored = [image(root / "color.png", (255, 0, 0), "RGB"),
               image(root / "hidden-color.png", (255, 0, 0, 0), "RGBA"),
               image(root / "partial-color.png", (255, 0, 0, 100), "RGBA")]
    original = {p.name:p.read_bytes() for p in (*selected, *colored)}
    os.utime(selected[0], ns=(1_600_000_000_000_000_000, 1_600_000_000_123_456_700))
    result = cli(root, destination, "--method", method)
    assert result.returncode == 0, result.stderr
    assert counts(result.stdout) == (9, 6, 6, 0, 0)
    assert {p.name for p in destination.glob("*.png")} | {p.name for p in destination.glob("*.PNG")} == {p.name for p in selected}
    for path in (*selected, *colored):
        assert path.read_bytes() == original[path.name]
    for path in selected:
        assert (destination / path.name).read_bytes() == original[path.name]
    assert (destination / selected[0].name).stat().st_mtime_ns == selected[0].stat().st_mtime_ns
    assert (destination / ".grayscale_sweeper.log").is_file()


def test_actual_thresholds_quantile_and_colorfulness(sweeper):
    with Image.new("RGB", (10, 10), (90, 90, 90)) as img:
        for i in range(2): img.putpixel((i, 0), (255, 0, 0))
        assert sweeper.is_low_saturation(img) is True  # exactly 98%, original rule
        img.putpixel((2, 0), (255, 0, 0))
        assert sweeper.is_low_saturation(img) is False
        assert sweeper.is_near_grayscale_sat_quantile(img, 8, 0.95) is True
        assert sweeper.is_near_grayscale_sat_quantile(img, 8, 1) is False
        assert sweeper.is_low_saturation(img, 255) is True
    with Image.new("RGB", (4, 4), (255, 0, 0)) as img:
        score = sweeper._colorfulness_score(img)
        assert score == pytest.approx(0.3 * math.hypot(255, 127.5), abs=0.0001)
        assert not sweeper.is_near_grayscale_colorfulness(img, score)
        assert sweeper.is_near_grayscale_colorfulness(img, math.nextafter(score, math.inf))
    with pytest.raises(ValueError):
        sweeper.is_near_grayscale_sat_quantile(img, 8, 0)


@pytest.mark.parametrize("method,gray", [("exact", False), ("sat", False), ("satq", False),
                                      ("colorfulness", True), ("auto", True)])
def test_actual_cli_uncertain_near_gray_is_method_dependent(tmp_path, method, gray):
    root, destination = tmp_path / "src", tmp_path / "out"
    image(root / "near-gray.png", (128, 120, 120), "RGB")
    result = cli(root, destination, "--method", method, "--sat-threshold", "8")
    assert result.returncode == 0
    assert (destination / "near-gray.png").exists() is gray


def test_auto_preserves_floor_and_colorfulness_fallback(sweeper):
    with Image.new("RGB", (4, 4), (128, 120, 120)) as img:
        assert not sweeper.is_near_grayscale_sat_quantile(img, 0)
        assert sweeper.classify(img, "auto", 0, colorfulness_cutoff=0)
    with Image.new("RGB", (4, 4), (8, 0, 0)) as img:
        assert not sweeper.is_grayscale_exact(img)
        assert not sweeper.is_near_grayscale_sat_quantile(img, 35)
        assert sweeper.classify(img, "auto")
        assert not sweeper.classify(img, "auto", colorfulness_cutoff=0)
    with Image.new("L", (4, 4), 80) as img:
        assert sweeper.classify(img, "auto", colorfulness_cutoff=0)


@pytest.mark.parametrize("move", [False, True])
@pytest.mark.parametrize("overwrite", [False, True])
def test_cli_collision_skip_or_explicit_overwrite_and_move(tmp_path, move, overwrite):
    root, destination = tmp_path / "src", tmp_path / "out"
    source = image(root / "same.png", 90)
    target = image(destination / "same.png", 40)
    source_bytes, old = source.read_bytes(), target.read_bytes()
    args = (["--move"] if move else []) + (["--overwrite"] if overwrite else [])
    result = cli(root, destination, *args)
    assert result.returncode == 0, result.stderr
    assert counts(result.stdout) == (1, 1, int(overwrite), int(not overwrite), 0)
    assert target.read_bytes() == (source_bytes if overwrite else old)
    assert source.exists() is not (move and overwrite)
    assert not list(destination.glob("same_*.png"))


def test_cli_move_only_successfully_classified_files_and_continues_corrupt(tmp_path):
    root, destination = tmp_path / "src", tmp_path / "out"
    good = image(root / "b-gray.png")
    color = image(root / "c-color.png", (255, 0, 0), "RGB")
    bad = root / "a-bad.png"; bad.write_bytes(b"not an image")
    expected = good.read_bytes()
    result = cli(root, destination, "--move")
    assert result.returncode == 1
    assert counts(result.stdout) == (3, 1, 1, 0, 1)
    assert not good.exists() and color.exists() and bad.exists()
    assert (destination / good.name).read_bytes() == expected
    assert "UnidentifiedImageError" in (destination / ".grayscale_sweeper.log").read_text()


@pytest.mark.parametrize("move", [False, True])
def test_nested_duplicates_have_deterministic_winner_and_no_silent_renaming(tmp_path, move):
    root, destination = tmp_path / "src", tmp_path / "out"
    first = image(root / "a/nested/same.png", 90)
    second = image(root / "z/same.png", 40)
    expected = first.read_bytes()
    result = cli(root, destination, *(["--move"] if move else []))
    assert result.returncode == 0 and counts(result.stdout) == (2, 2, 1, 1, 0)
    assert (destination / "same.png").read_bytes() == expected
    assert first.exists() is not move and second.exists()
    assert not list(destination.glob("same_*.png"))


def test_output_subtree_is_excluded_on_repeated_scans_and_logs_append(tmp_path):
    root = tmp_path / "src"
    image(root / "gray.png")
    destination = root / "nested/other"
    image(destination / "already.png")
    (root / "ignore.txt").write_text("ignored")
    first = cli(root, destination)
    assert first.returncode == 0 and counts(first.stdout) == (1, 1, 1, 0, 0)
    log = destination / ".grayscale_sweeper.log"
    previous = log.read_bytes()
    second = cli(root, destination)
    assert second.returncode == 0 and counts(second.stdout) == (1, 1, 0, 1, 0)
    assert log.read_bytes().startswith(previous)


def test_extension_filter(tmp_path):
    root, destination = tmp_path / "src", tmp_path / "out"
    image(root / "keep.PNG")
    image(root / "ignore.jpg")
    result = cli(root, destination, "--exts", ".PNG")
    assert result.returncode == 0 and counts(result.stdout) == (1, 1, 1, 0, 0)


@pytest.mark.parametrize("case", ["same", "ancestor", "missing", "file"])
def test_invalid_roots_fail_without_modifying_source(tmp_path, case):
    root = tmp_path / "src"
    source = image(root / "gray.png")
    before = source.read_bytes()
    destination = root if case == "same" else tmp_path if case == "ancestor" else tmp_path / "out"
    if case == "missing": root = tmp_path / "missing"
    if case == "file": root = source
    result = cli(root, destination, "--move", "--overwrite")
    assert result.returncode != 0 and "Error:" in result.stderr
    assert source.read_bytes() == before


@pytest.mark.parametrize("overwrite", [False, True])
def test_same_file_hardlink_is_never_overwritten_or_moved(tmp_path, overwrite):
    root, destination = tmp_path / "src", tmp_path / "out"
    source = image(root / "same.png")
    destination.mkdir()
    try: os.link(source, destination / source.name)
    except OSError: pytest.skip("Filesystem does not permit hard links")
    before = source.read_bytes()
    result = cli(root, destination, "--move", *(["--overwrite"] if overwrite else []))
    assert result.returncode == 1 and "same file" in result.stderr
    assert counts(result.stdout) == (1, 1, 0, 0, 1)
    assert source.read_bytes() == (destination / source.name).read_bytes() == before


@pytest.mark.parametrize("case", ["source-root", "source-file", "source-directory", "destination", "log"])
def test_symlink_paths_are_not_followed(tmp_path, case):
    root, destination = tmp_path / "src", tmp_path / "out"
    source = image(root / "gray.png")
    outside = image(tmp_path / "outside/other.png")
    destination.mkdir()
    link = (tmp_path / "linked-root" if case == "source-root" else root / "linked.png"
            if case == "source-file" else root / "linked-dir" if case == "source-directory"
            else tmp_path / "linked-dest" if case == "destination" else destination / ".grayscale_sweeper.log")
    target = root if case == "source-root" else outside if case in ("source-file", "log") else outside.parent
    try: link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError: pytest.skip("OS account cannot create symlinks")
    before = outside.read_bytes()
    result = cli(link if case == "source-root" else root,
                 link if case == "destination" else destination, "--move", "--overwrite")
    assert result.returncode == 1 and "Symlink/reparse" in result.stderr
    assert outside.read_bytes() == before
    if case in ("source-root", "destination", "log"): assert source.exists()


def test_detection_runs_while_image_open_and_unexpected_errors_are_counted(tmp_path, sweeper, monkeypatch, capsys):
    root, destination = tmp_path / "src", tmp_path / "out"
    image(root / "a.png"); image(root / "b.png")
    original = sweeper.classify
    opened = []
    active = set()
    original_open = sweeper.Image.open
    @contextmanager
    def tracked_open(path):
        with original_open(path) as img:
            active.add(id(img))
            try:
                yield img
            finally:
                active.remove(id(img))
    def detect(img, *args):
        assert id(img) in active
        img.getpixel((0, 0))
        opened.append(img)
        if len(opened) == 1: raise RuntimeError("Unexpected detector failure")
        return original(img, *args)
    monkeypatch.setattr(sweeper, "classify", detect)
    monkeypatch.setattr(sweeper.Image, "open", tracked_open)
    assert sweeper.main(["--src", str(root), "--dest-other", str(destination)]) == 1
    assert counts(capsys.readouterr().out) == (2, 1, 1, 0, 1)
    assert (destination / "b.png").exists()
    assert "Unexpected detector failure" in (destination / ".grayscale_sweeper.log").read_text()
    # Pillow can retain decoded pixels after __exit__; track the real context
    # lifetime rather than incorrectly assuming getpixel must stop working.
    assert len(opened) == 2 and not active


def test_source_change_after_classification_prevents_move(tmp_path, sweeper, monkeypatch, capsys):
    root, destination = tmp_path / "src", tmp_path / "out"
    source = image(root / "gray.png")
    original = sweeper.classify
    def detect(img, *args):
        result = original(img, *args)
        source.write_bytes(b"source changed after successful classification")
        return result
    monkeypatch.setattr(sweeper, "classify", detect)
    assert sweeper.main(["--src", str(root), "--dest-other", str(destination), "--move"]) == 1
    assert counts(capsys.readouterr().out) == (1, 1, 0, 0, 1)
    assert source.exists() and not (destination / source.name).exists()


def test_concurrent_arrival_is_not_clobbered(tmp_path, sweeper, monkeypatch, capsys):
    root, destination = tmp_path / "src", tmp_path / "out"
    source = image(root / "gray.png")
    original = sweeper.shutil.copy2
    def copy(*args, **kwargs):
        result = original(*args, **kwargs)
        (destination / source.name).write_bytes(b"concurrent arrival")
        return result
    monkeypatch.setattr(sweeper.shutil, "copy2", copy)
    assert sweeper.main(["--src", str(root), "--dest-other", str(destination), "--move"]) == 0
    assert counts(capsys.readouterr().out) == (1, 1, 0, 1, 0)
    assert (destination / source.name).read_bytes() == b"concurrent arrival" and source.exists()
    assert not list(destination.glob(".grayscale-sweeper-*.tmp"))


def test_failed_staged_overwrite_preserves_existing_file(tmp_path, sweeper, monkeypatch, capsys):
    root, destination = tmp_path / "src", tmp_path / "out"
    source = image(root / "gray.png")
    target = image(destination / source.name, 40)
    before = target.read_bytes()
    def broken_copy(src, dest, **kwargs):
        Path(dest).write_bytes(b"partial staged data")
        raise OSError("Synthetic copy failure")
    monkeypatch.setattr(sweeper.shutil, "copy2", broken_copy)
    assert sweeper.main(["--src", str(root), "--dest-other", str(destination), "--overwrite", "--move"]) == 1
    assert counts(capsys.readouterr().out) == (1, 1, 0, 0, 1)
    assert target.read_bytes() == before and source.exists()
    assert not list(destination.glob(".grayscale-sweeper-*.tmp"))


def test_reserved_log_name_cannot_be_overwritten_by_image(tmp_path):
    root, destination = tmp_path / "src", tmp_path / "out"
    source = image(root / ".grayscale_sweeper.log")
    result = cli(root, destination, "--exts", "log", "--overwrite", "--move")
    assert result.returncode == 1 and source.exists()
    assert counts(result.stdout) == (1, 1, 0, 0, 1)
    assert "Reserved sweeper log filename" in (destination / source.name).read_text()


@pytest.mark.parametrize("names", [("Same.png", "same.png"), ("Caf\u00e9.png", "Cafe\u0301.png")])
def test_case_and_unicode_aliases_are_skipped_even_with_overwrite(tmp_path, names):
    root, destination = tmp_path / "src", tmp_path / "out"
    first = image(root / "a" / names[0], 90)
    second = image(root / "b" / names[1], 40)
    expected = first.read_bytes()
    result = cli(root, destination, "--overwrite", "--move")
    assert result.returncode == 0 and counts(result.stdout) == (2, 2, 1, 1, 0)
    assert {p.name for p in destination.iterdir()} == {names[0], ".grayscale_sweeper.log"}
    assert (destination / names[0]).read_bytes() == expected and second.exists()


def test_unicode_names_with_ascii_console_keep_exact_filenames(tmp_path):
    root, destination = tmp_path / "\u4eba\u7269", tmp_path / "\u51fa\u529b"
    source = image(root / "Jos\u00e9 \u4eba\u7269.png")
    result = cli(root, destination, env=dict(os.environ, PYTHONIOENCODING="ascii"))
    assert result.returncode == 0, result.stderr
    assert counts(result.stdout) == (1, 1, 1, 0, 0)
    assert (destination / source.name).read_bytes() == source.read_bytes()
    assert source.name in (destination / ".grayscale_sweeper.log").read_text(encoding="utf8")


def test_normal_other_and_color_outputs_are_pruned(tmp_path):
    copied = tmp_path / "grayscale_sweeper.py"
    shutil.copy2(SCRIPT, copied)
    image(tmp_path / "incoming/gray.png")
    image(tmp_path / "config/Downloads/other/old.png")
    image(tmp_path / "config/Downloads/color/already.png")
    result = subprocess.run([sys.executable, "-B", str(copied), "--src", str(tmp_path),
                             "--dest-other", str(tmp_path / "result")], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and counts(result.stdout) == (1, 1, 1, 0, 0)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction integration")
def test_windows_source_junction_is_not_followed(tmp_path):
    root, destination = tmp_path / "src", tmp_path / "out"
    root.mkdir()
    outside = image(tmp_path / "outside/gray.png")
    link = root / "junction"
    created = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside.parent)],
                             capture_output=True, text=True)
    if created.returncode:
        pytest.skip("OS/filesystem cannot create a test directory junction")
    expected = outside.read_bytes()
    result = cli(root, destination, "--move", "--overwrite")
    assert result.returncode == 1 and counts(result.stdout) == (0, 0, 0, 0, 1)
    assert "reparse" in result.stderr and outside.read_bytes() == expected


def test_readonly_source_can_be_copied_and_private_staging_is_cleaned(tmp_path):
    root, destination = tmp_path / "src", tmp_path / "out"
    source = image(root / "readonly.png")
    expected = source.read_bytes()
    source.chmod(stat.S_IREAD)
    try:
        result = cli(root, destination)
        assert result.returncode == 0, result.stderr
        assert counts(result.stdout) == (1, 1, 1, 0, 0)
        assert source.read_bytes() == (destination / source.name).read_bytes() == expected
        assert not list(destination.glob(".grayscale-sweeper-*.tmp"))
    finally:
        source.chmod(stat.S_IREAD | stat.S_IWRITE)
        target = destination / source.name
        if target.exists(): target.chmod(stat.S_IREAD | stat.S_IWRITE)
