from __future__ import annotations

from contextlib import contextmanager
import logging
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest
from PIL import Image, ImageOps


SCRIPT = Path(__file__).resolve().parents[1] / "sync_people_images.py"
TARGET = (2000, 3000)


@pytest.fixture
def sync(monkeypatch, tmp_path):
    # Redirect import-time config/log setup before executing the real script.
    module = ModuleType("isolated_background_sync")
    module.__file__ = str(tmp_path / SCRIPT.name)
    monkeypatch.setattr(logging, "FileHandler", lambda *args, **kwargs: logging.NullHandler())
    monkeypatch.setattr(logging, "basicConfig", lambda *args, **kwargs: None)
    monkeypatch.delenv("REMOVE_BG_ENGINE", raising=False)
    exec(compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec"), module.__dict__)

    @contextmanager
    def progress(*args, **kwargs):
        class Bar:
            text = ""

            def __call__(self):
                pass

        yield Bar()

    monkeypatch.setattr(module, "alive_bar", progress)
    return module


def photo(path, size=(400, 600), mode="RGB", color=(30, 100, 180)):
    path.parent.mkdir(parents=True, exist_ok=True)
    with Image.new(mode, size, color) as image:
        image.save(path, format="JPEG", quality=90)
    return path.read_bytes()


def assert_presentation(path):
    with Image.open(path) as image:
        image.load()
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert image.size == TARGET


def sync_original(sync, source, destination):
    return sync.sync_tree(source, destination, "sync original", normalize_original=True)


def test_native_archive_and_raw_png_preserved(sync, tmp_path):
    source = tmp_path / "original"
    archive = source / "A" / "Images" / "Actor.jpg"
    original_bytes = photo(archive)
    original_stat = archive.stat()
    raw_png = tmp_path / "raw" / "Actor.png"
    raw_png.parent.mkdir()
    with Image.new("RGBA", (400, 600), (30, 100, 180, 0)) as image:
        image.paste((30, 100, 180, 255), (100, 100, 300, 500))
        image.save(raw_png)
    png_bytes = raw_png.read_bytes()
    destination = tmp_path / "published"

    assert sync_original(sync, source, destination) == 0
    assert_presentation(destination / archive.relative_to(source))
    assert archive.read_bytes() == original_bytes
    assert archive.stat().st_mtime_ns == original_stat.st_mtime_ns
    with Image.open(archive) as image:
        assert image.size == (400, 600)
    assert raw_png.read_bytes() == png_bytes
    with Image.open(raw_png) as image:
        assert image.size == (400, 600)


def test_standard_rgb_jpeg_is_exact_byte_copy(sync, tmp_path):
    source = tmp_path / "original"
    archive = source / "Actor.jpg"
    original_bytes = photo(archive, TARGET)
    destination = tmp_path / "published"
    assert sync_original(sync, source, destination) == 0
    published = destination / "A" / "Images" / archive.name
    assert published.read_bytes() == original_bytes
    assert archive.read_bytes() == original_bytes
    assert_presentation(published)


@pytest.mark.parametrize("size,orientation", [((400, 500), None), ((600, 400), 6)])
def test_normalization_matches_adobe_stretch(sync, tmp_path, size, orientation):
    source = tmp_path / "original"
    archive = source / "Actor.jpg"
    photo(archive, size)
    if orientation:
        with Image.open(archive) as image:
            exif = image.getexif()
            exif[274] = orientation
            image.save(archive, exif=exif)
    original_bytes = archive.read_bytes()
    expected = tmp_path / "expected.jpg"
    with Image.open(archive) as image:
        with ImageOps.exif_transpose(image) as oriented:
            with oriented.convert("RGB") as rgb:
                with rgb.resize(TARGET, Image.Resampling.LANCZOS) as resized:
                    resized.save(expected, format="JPEG", quality=95, subsampling=0, optimize=True)
    destination = tmp_path / "published"
    assert sync_original(sync, source, destination) == 0
    assert (destination / "A" / "Images" / archive.name).read_bytes() == expected.read_bytes()
    assert archive.read_bytes() == original_bytes


def test_grayscale_original_publishes_rgb_and_keeps_warning(sync, tmp_path):
    source = tmp_path / "original"
    archive = source / "Actor.jpg"
    original_bytes = photo(archive, TARGET, "L", 120)
    blocking, warnings = sync.image_quality_findings("original", archive)
    assert not blocking
    assert warnings
    destination = tmp_path / "published"
    assert sync_original(sync, source, destination) == 0
    assert_presentation(destination / "A" / "Images" / archive.name)
    assert archive.read_bytes() == original_bytes


@pytest.mark.parametrize("size", [(400, 600), TARGET])
def test_different_newer_destination_is_replaced(sync, tmp_path, size, caplog):
    source = tmp_path / "original"
    archive = source / "Actor.jpg"
    original_bytes = photo(archive, size)
    destination = tmp_path / "published"
    published = destination / "A" / "Images" / archive.name
    previous = photo(published, TARGET, color=(180, 100, 30))
    os.utime(published, (archive.stat().st_mtime + 1000,) * 2)
    with caplog.at_level(logging.INFO):
        assert sync_original(sync, source, destination) == 0
    assert published.read_bytes() != previous
    assert archive.read_bytes() == original_bytes
    assert "copied=1, skipped=0" in caplog.text
    assert_presentation(published)


@pytest.mark.parametrize("size", [(400, 600), TARGET])
def test_unchanged_destination_skips_without_replacement(sync, monkeypatch, tmp_path, size, caplog):
    source = tmp_path / "original"
    archive = source / "Actor.jpg"
    photo(archive, size)
    destination = tmp_path / "published"
    assert sync_original(sync, source, destination) == 0
    published = destination / "A" / "Images" / archive.name
    previous = published.read_bytes()
    os.utime(published, (archive.stat().st_mtime + 1000,) * 2)
    previous_mtime = published.stat().st_mtime_ns

    def unexpected_replace(*args, **kwargs):
        pytest.fail("unchanged presentation must not be replaced")

    monkeypatch.setattr(Path, "replace", unexpected_replace)
    with caplog.at_level(logging.INFO):
        assert sync_original(sync, source, destination) == 0
    assert "copied=0, skipped=1, normalized=0, failed=0" in caplog.text
    assert published.read_bytes() == previous
    assert published.stat().st_mtime_ns == previous_mtime
    assert not list(destination.rglob(".sync-original-*"))


@pytest.mark.parametrize("failure", ["corrupt", "truncated", "save", "copy", "validation", "replace"])
def test_per_file_failure_preserves_source_and_destination(sync, monkeypatch, tmp_path, failure):
    source = tmp_path / "original"
    archive = source / "Bad.jpg"
    original_bytes = photo(archive, TARGET if failure == "copy" else (400, 600))
    if failure == "corrupt":
        archive.write_bytes(b"invalid JPEG")
    elif failure == "truncated":
        archive.write_bytes(original_bytes[: len(original_bytes) // 2])
    original_bytes = archive.read_bytes()
    destination = tmp_path / "published"
    published = destination / "B" / "Images" / archive.name
    previous = photo(published, TARGET, color=(180, 100, 30))
    previous_mtime = published.stat().st_mtime_ns

    def partial_copy(src, dst, *args, **kwargs):
        Path(dst).write_bytes(b"partial")
        raise OSError("copy failed")

    def failed_replace(*args, **kwargs):
        raise OSError("replace failed")

    real_save = Image.Image.save

    def failed_save(image, path, *args, **kwargs):
        if Path(path).name.startswith(".sync-original-"):
            Path(path).write_bytes(b"partial")
            raise OSError("save failed")
        return real_save(image, path, *args, **kwargs)

    def invalid_save(image, path, *args, **kwargs):
        with Image.new("RGB", (20, 30), (20, 60, 100)) as wrong:
            real_save(wrong, path, format="JPEG")

    if failure == "copy":
        monkeypatch.setattr(sync.shutil, "copy2", partial_copy)
    elif failure == "save":
        monkeypatch.setattr(Image.Image, "save", failed_save)
    elif failure == "validation":
        monkeypatch.setattr(Image.Image, "save", invalid_save)
    elif failure == "replace":
        monkeypatch.setattr(Path, "replace", failed_replace)
    assert sync_original(sync, source, destination) == 1
    assert archive.read_bytes() == original_bytes
    assert published.read_bytes() == previous
    assert published.stat().st_mtime_ns == previous_mtime
    assert not list(destination.rglob(".sync-original-*"))


def test_failure_continues_batch_and_main_returns_nonzero(sync, monkeypatch, tmp_path):
    source = sync.CONFIG_DIR / "people_dirs" / "original"
    photo(source / "Good.jpg")
    (source / "Bad.jpg").write_bytes(b"invalid JPEG")
    destination = tmp_path / "published"
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setattr(sys, "argv", [SCRIPT.name, "--dest_root", str(destination), "--no-preflight"])
    assert sync.main() == 1
    assert_presentation(destination / "original" / "G" / "Images" / "Good.jpg")
    assert not (destination / "original" / "B" / "Images" / "Bad.jpg").exists()


@pytest.mark.parametrize("normalize_original,expected", [(False, 1), (True, 0)])
def test_preflight_native_original_dimensions(sync, tmp_path, normalize_original, expected):
    photo(tmp_path / "people" / "original" / "A" / "Images" / "Actor.jpg")
    assert sync.preflight_sources(tmp_path / "people", normalize_original=normalize_original) == expected


@pytest.mark.parametrize("category", ["signature", "bw", "diiivoy", "rainier", "diiivoycolor"])
def test_local_preflight_still_rejects_other_native_styles(sync, tmp_path, category):
    photo(tmp_path / "people" / category / "Actor.jpg")
    assert sync.preflight_sources(tmp_path / "people", normalize_original=True) == 1


@pytest.mark.parametrize("invalid", ["corrupt", "extension"])
def test_local_preflight_still_rejects_invalid_original(sync, tmp_path, invalid):
    root = tmp_path / "people" / "original"
    if invalid == "corrupt":
        root.mkdir(parents=True)
        (root / "Actor.jpg").write_bytes(b"invalid JPEG")
    else:
        photo(root / "A" / "Images" / "Actor.gif")
    assert sync.preflight_sources(tmp_path / "people", normalize_original=True) == 1


def test_opaque_jpeg_is_valid_original_but_opaque_png_is_invalid_transparent(sync, tmp_path):
    original = tmp_path / "people" / "original" / "Actor.jpg"
    photo(original)
    assert sync.preflight_sources(tmp_path / "people", normalize_original=True) == 0
    transparent = tmp_path / "people" / "transparent" / "Actor.png"
    transparent.parent.mkdir()
    with Image.new("RGBA", (400, 600), (30, 100, 180, 255)) as image:
        image.save(transparent)
    assert sync.preflight_sources(tmp_path / "people", normalize_original=True) == 1


def test_transparent_normalization_keeps_native_source(sync, tmp_path):
    source = tmp_path / "people" / "transparent"
    source.mkdir(parents=True)
    raw = source / "Actor.png"
    with Image.new("RGBA", (400, 600), (30, 100, 180, 0)) as image:
        image.paste((30, 100, 180, 255), (100, 100, 300, 500))
        image.save(raw)
    previous = raw.read_bytes()
    assert sync.preflight_sources(source.parent) == 0
    destination = tmp_path / "published"
    assert sync.sync_tree(source, destination, "transparent", normalize_transparent=True) == 0
    assert raw.read_bytes() == previous
    with Image.open(destination / raw.name) as image:
        assert image.mode == "RGBA"
        assert image.size == TARGET
        assert sync.has_any_transparency(image)


@pytest.mark.parametrize("category", ["original", "transparent"])
@pytest.mark.parametrize("normalize_original", [False, True])
def test_history_excluded_from_files_directories_sync_and_preflight(sync, tmp_path, category,
                                                                 normalize_original):
    source = tmp_path / "people" / category
    history = source / ".history" / "digest" / "Images"
    history.mkdir(parents=True)
    photo(history / "Native.jpg")
    (history / "Corrupt.png").write_bytes(b"invalid image")
    nested = source / "A" / ".history" / "empty"
    nested.mkdir(parents=True)
    hidden = source / ".hidden"
    hidden.mkdir()
    (hidden / ".keep").write_bytes(b"other hidden file")
    (hidden / ".history").write_bytes(b"a file, not a reserved directory")
    (source / "empty").mkdir()
    assert set(sync.iter_files(source)) == {hidden / ".keep", hidden / ".history"}
    assert set(sync.iter_dirs(source)) == {source, source / "A", hidden, source / "empty"}
    assert sync.preflight_sources(source.parent, normalize_original=normalize_original) == 0
    destination = tmp_path / "published"
    assert sync.sync_tree(source, destination, category, normalize_original=normalize_original) == 0
    assert (destination / ".hidden" / ".keep").read_bytes() == b"other hidden file"
    assert (destination / ".hidden" / ".history").is_file()
    assert (destination / "empty").is_dir()
    assert not (destination / ".history").exists()
    assert not (destination / "A" / ".history").exists()


@pytest.mark.parametrize("engine,expected", [(None, 0), ("adobe", 1), ("birefnet", 0),
                                           (" BiRefNet ", 0)])
def test_main_engine_controls_native_original_publication(sync, monkeypatch, tmp_path, engine, expected):
    archive = sync.CONFIG_DIR / "people_dirs" / "original" / "Actor.jpg"
    previous = photo(archive)
    if engine is not None:
        monkeypatch.setenv("REMOVE_BG_ENGINE", engine)
    destination = tmp_path / "published"
    monkeypatch.setattr(sys, "argv", [SCRIPT.name, "--dest_root", str(destination), "--preflight"])
    assert sync.main() == expected
    if expected:
        assert not destination.exists()
    else:
        assert_presentation(destination / "original" / "A" / "Images" / archive.name)
    assert archive.read_bytes() == previous


@pytest.mark.parametrize("engine", ["adobe", "birefnet"])
def test_main_normalizes_original_only_for_local_category(sync, monkeypatch, tmp_path, engine):
    monkeypatch.setenv("REMOVE_BG_ENGINE", engine)
    calls = []
    monkeypatch.setattr(sync, "sync_tree", lambda src, dst, title, **kwargs: calls.append(
        SimpleNamespace(category=src.name, **kwargs)) or 0)
    monkeypatch.setattr(sys, "argv", [SCRIPT.name, "--dest_root", str(tmp_path / "published"),
                                      "--no-preflight"])
    assert sync.main() == 0
    assert len(calls) == len(sync.CATEGORIES)
    for call in calls:
        assert call.normalize_original == (engine == "birefnet" and call.category == "original")
        assert call.normalize_transparent == (call.category == "transparent")


def test_default_sync_preserves_timestamp_semantics_and_native_bytes(sync, tmp_path):
    source = tmp_path / "original"
    archive = source / "Actor.jpg"
    original_bytes = photo(archive)
    destination = tmp_path / "published"
    assert sync.sync_tree(source, destination, "original") == 0
    published = destination / archive.name
    assert published.read_bytes() == original_bytes
    newer_bytes = photo(published, color=(180, 100, 30))
    os.utime(published, (archive.stat().st_mtime + 1000,) * 2)
    assert sync.sync_tree(source, destination, "original") == 0
    assert published.read_bytes() == newer_bytes


@pytest.mark.parametrize("suffix,encoding", [(".jpg", "JPEG"), (".jpeg", "JPEG"),
                                             (".png", "PNG"), (".webp", "WEBP"),
                                             (".bmp", "BMP"), (".tif", "TIFF"),
                                             (".tiff", "TIFF"), (".PNG", "PNG")])
@pytest.mark.parametrize("sorted_archive", [False, True])
def test_native_formats_preserved_and_published_as_canonical_jpeg(sync, monkeypatch, tmp_path,
                                                                suffix, encoding, sorted_archive):
    source = sync.CONFIG_DIR / "people_dirs" / "original"
    relative = Path("custom") / "A" / "Images" if sorted_archive else Path()
    archive = source / relative / ("Actor" + suffix)
    archive.parent.mkdir(parents=True, exist_ok=True)
    mode = "RGBA" if encoding == "PNG" else "RGB"
    color = (30, 100, 180, 255) if mode == "RGBA" else (30, 100, 180)
    with Image.new(mode, (400, 600), color) as image:
        image.save(archive, format=encoding)
    original_bytes = archive.read_bytes()
    original_mtime = archive.stat().st_mtime_ns
    destination = tmp_path / "published"
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setattr(sys, "argv", [SCRIPT.name, "--dest_root", str(destination), "--preflight"])
    assert sync.main() == 0
    expected = (relative if sorted_archive else Path("A") / "Images") / "Actor.jpg"
    assert_presentation(destination / "original" / expected)
    assert list((destination / "original").rglob("*.*")) == [destination / "original" / expected]
    assert archive.read_bytes() == original_bytes
    assert archive.stat().st_mtime_ns == original_mtime
    with Image.open(archive) as image:
        image.load()
        assert image.size == (400, 600)
        assert image.format == encoding


@pytest.mark.parametrize("suffix", [".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"])
@pytest.mark.parametrize("category,normalize_original", [("original", False), ("signature", True)])
def test_native_extension_acceptance_is_scoped_to_local_original(sync, tmp_path, suffix, category,
                                                               normalize_original):
    path = tmp_path / "people" / category / ("Actor" + suffix)
    path.parent.mkdir(parents=True)
    with Image.new("RGB", TARGET, (30, 100, 180)) as image:
        image.save(path)
    assert sync.preflight_sources(tmp_path / "people", normalize_original=normalize_original) == 1


@pytest.mark.parametrize("second_relative", ["Actor.png", "A/Images/Actor.jpeg",
                                            "A/Images/actor.webp"])
def test_ambiguous_native_targets_abort_preflight_before_any_publication(sync, monkeypatch, tmp_path,
                                                                      second_relative, caplog):
    source = sync.CONFIG_DIR / "people_dirs" / "original"
    photo(source / "Actor.jpg")
    second = source / second_relative
    second.parent.mkdir(parents=True, exist_ok=True)
    with Image.new("RGB", (400, 600), (180, 100, 30)) as image:
        image.save(second)
    # A valid earlier style must also remain unpublished when Original collides.
    photo(source.parent / "bw" / "Actor.jpg", TARGET)
    preserved = {path: path.read_bytes() for path in source.rglob("*") if path.is_file()}
    destination = tmp_path / "published"
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setattr(sys, "argv", [SCRIPT.name, "--dest_root", str(destination), "--preflight"])
    assert sync.main() == 1
    assert "ambiguous presentation target" in caplog.text
    assert not destination.exists()
    assert all(path.read_bytes() == content for path, content in preserved.items())


def test_direct_local_sync_blocks_collisions_before_directory_creation(sync, tmp_path):
    source = tmp_path / "original"
    photo(source / "Actor.jpg")
    photo(source / "Actor.jpeg")
    destination = tmp_path / "published"
    assert sync_original(sync, source, destination) > 0
    assert not destination.exists()


def test_history_does_not_collide_with_live_native_presentation(sync, tmp_path):
    source = tmp_path / "people" / "original"
    photo(source / "Actor.jpg")
    photo(source / ".history" / "digest" / "A" / "Images" / "Actor.jpeg")
    assert sync.preflight_sources(source.parent, normalize_original=True) == 0
    destination = tmp_path / "published"
    assert sync_original(sync, source, destination) == 0
    assert_presentation(destination / "A" / "Images" / "Actor.jpg")
    assert not (destination / ".history").exists()


def test_separate_sorted_folders_with_same_stem_are_not_collisions(sync, tmp_path):
    source = tmp_path / "people" / "original"
    for directory in ("first", "second"):
        path = source / directory / "Images" / "Actor.png"
        path.parent.mkdir(parents=True)
        with Image.new("RGB", (400, 600), (30, 100, 180)) as image:
            image.save(path)
    assert sync.preflight_sources(source.parent, normalize_original=True) == 0
    destination = tmp_path / "published"
    assert sync_original(sync, source, destination) == 0
    for directory in ("first", "second"):
        assert_presentation(destination / directory / "Images" / "Actor.jpg")


@pytest.mark.parametrize("first_relative,second_relative", [
    ("JOS\u00c9.jpg", "Jose\u0301.png"),
    ("\u00c9mile.jpg", "E\u0301mile.png"),
    ("Jos\u00e9/Images/Actor.jpg", "Jose\u0301/Images/actor.png"),
    ("\u00c9mile.jpg", "\u00c9/Images/E\u0301mile.png"),
])
def test_nfc_aliases_abort_before_publication(sync, monkeypatch, tmp_path, first_relative,
                                            second_relative, caplog):
    source = sync.CONFIG_DIR / "people_dirs" / "original"
    for relative in (first_relative, second_relative):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with Image.new("RGB", (400, 600), (30, 100, 180)) as image:
            image.save(path)
    originals = {path: path.read_bytes() for path in sync.iter_files(source)}
    collisions = sync.original_presentation_collisions(source, list(originals))
    assert len(collisions) == 1
    assert set(next(iter(collisions.values()))) == set(originals)
    photo(source.parent / "bw" / "Actor.jpg", TARGET)
    destination = tmp_path / "published"
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    monkeypatch.setattr(sys, "argv", [SCRIPT.name, "--dest_root", str(destination), "--preflight"])
    assert sync.main() == 1
    assert "ambiguous presentation target" in caplog.text
    assert not destination.exists()
    assert sync_original(sync, source, destination) == 2
    assert not destination.exists()
    assert all(path.read_bytes() == content for path, content in originals.items())


@pytest.mark.parametrize("suffix", [".png", ".webp", ".tif", ".tiff"])
def test_animated_and_multipage_originals_blocked_with_or_without_preflight(sync, monkeypatch,
                                                                         tmp_path, suffix, caplog):
    source = sync.CONFIG_DIR / "people_dirs" / "original"
    source.mkdir(parents=True)
    archive = source / ("Actor" + suffix)
    with Image.new("RGB", (400, 600), (30, 100, 180)) as first:
        with Image.new("RGB", (400, 600), (180, 100, 30)) as second:
            first.save(archive, save_all=True, append_images=[second], duration=50, loop=0)
    with Image.open(archive) as image:
        assert image.n_frames == 2
    original_bytes = archive.read_bytes()
    original_mtime = archive.stat().st_mtime_ns
    destination = tmp_path / "published"
    published = destination / "original" / "A" / "Images" / "Actor.jpg"
    previous = photo(published, TARGET)
    previous_mtime = published.stat().st_mtime_ns
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    for preflight in ("--preflight", "--no-preflight"):
        monkeypatch.setattr(sys, "argv", [SCRIPT.name, "--dest_root", str(destination), preflight])
        assert sync.main() == 1
        assert archive.read_bytes() == original_bytes
        assert archive.stat().st_mtime_ns == original_mtime
        assert published.read_bytes() == previous
        assert published.stat().st_mtime_ns == previous_mtime
        assert not list(destination.rglob(".sync-original-*"))
        assert [path for path in destination.rglob("*") if path.is_file()] == [published]
    assert "Animated/multipage input is unsupported" in caplog.text
