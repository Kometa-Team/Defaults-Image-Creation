from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import warnings

import pytest
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import remove_bg_birefnet as bg


def make_source(path, size=(31, 47), color=(60, 100, 140)):
    path.parent.mkdir(parents=True, exist_ok=True)
    with Image.new("RGB", size, color) as image:
        image.save(path)
    return path.read_bytes()


def cutout(size, color=(30, 80, 130)):
    image = Image.new("RGBA", size, (*color, 0))
    image.paste((*color, 255), (size[0] // 3, 0, size[0], size[1]))
    image.paste((*color, 128), (size[0] // 3, 0, size[0] // 3 + 1, size[1]))
    return image


def save_cutout(path, size=(31, 47), color=(30, 80, 130)):
    path.parent.mkdir(parents=True, exist_ok=True)
    with cutout(size, color) as image:
        image.save(path, format="PNG")


def assert_no_temporary_files(root):
    assert not list(root.rglob(".bg-*"))


@pytest.fixture
def fake_backend(monkeypatch, tmp_path):
    """Exercise real initialization and file handling without importing inference deps."""
    weights = tmp_path / "models" / "birefnet-portrait.onnx"
    weights.parent.mkdir()
    weights.write_bytes(b"test-only model weights")
    monkeypatch.setitem(
        bg.MODEL_CHECKSUMS, "birefnet-portrait",
        hashlib.md5(weights.read_bytes()).hexdigest(),
    )
    monkeypatch.delenv("MODEL_CHECKSUM_DISABLED", raising=False)
    # Restore both variables after LocalRemover changes them directly.
    monkeypatch.setenv("REMBG_HOME", str(weights.parent))
    monkeypatch.setenv("U2NET_HOME", str(weights.parent))
    state = SimpleNamespace(
        settings=bg.Settings(home=weights.parent), weights=weights,
        available=["CPUExecutionProvider"], active=["CPUExecutionProvider"],
        sessions=[], calls=[], downloads=[], instances=[], closed=[],
        masks=[], matting_calls=[], matting_error=None, matting_warning=None,
        infer=lambda image: cutout(image.size), init_error=None,
    )

    class Model:
        @classmethod
        def name(cls):
            return "birefnet-portrait"

        @classmethod
        def download_models(cls):
            state.downloads.append(weights)
            return str(weights)

    def new_session(model, providers):
        if state.init_error is not None:
            raise state.init_error
        session = SimpleNamespace(
            inner_session=SimpleNamespace(get_providers=lambda: state.active),
        )
        state.sessions.append((model, providers, session))
        return session

    def remove(image, session, alpha_matting, decontaminate, post_process_mask, only_mask=False):
        state.calls.append({
            "session": session, "size": image.size, "mode": image.mode,
            "alpha_matting": alpha_matting, "decontaminate": decontaminate,
            "post_process_mask": post_process_mask, "only_mask": only_mask,
        })
        result = state.infer(image)
        if only_mask:
            try:
                mask = result.getchannel("A")
            finally:
                result.close()
            state.masks.append(mask)
            return mask
        return result

    def alpha_matting_cutout(image, mask, foreground_threshold, background_threshold, erode_size):
        state.matting_calls.append({
            "size": image.size, "mode": image.mode,
            "mask_size": mask.size, "mask_mode": mask.mode,
            "thresholds": (foreground_threshold, background_threshold, erode_size),
        })
        if state.matting_warning is not None:
            warnings.warn(state.matting_warning, RuntimeWarning)
        if state.matting_error is not None:
            raise state.matting_error
        result = image.convert("RGBA")
        result.putalpha(mask)
        return result

    ort = ModuleType("onnxruntime")
    ort.get_available_providers = lambda: state.available
    rembg = ModuleType("rembg")
    rembg.new_session = new_session
    rembg.remove = remove
    sessions = ModuleType("rembg.sessions")
    sessions.sessions_class = [Model]
    rembg.sessions = sessions
    rembg_bg = ModuleType("rembg.bg")
    rembg_bg.alpha_matting_cutout = alpha_matting_cutout
    rembg.bg = rembg_bg
    monkeypatch.setitem(sys.modules, "onnxruntime", ort)
    monkeypatch.setitem(sys.modules, "rembg", rembg)
    monkeypatch.setitem(sys.modules, "rembg.sessions", sessions)
    monkeypatch.setitem(sys.modules, "rembg.bg", rembg_bg)
    monkeypatch.setattr(bg, "version", lambda package: "test-rembg")
    real_close = bg.LocalRemover.close

    def close(remover):
        state.closed.append(remover)
        real_close(remover)

    monkeypatch.setattr(bg.LocalRemover, "close", close)

    def factory(settings):
        remover = bg.LocalRemover(settings)
        state.instances.append(remover)
        return remover

    state.factory = factory
    return state


@pytest.fixture
def folders(tmp_path):
    source, archive, output = (tmp_path / name for name in ("queue", "originals", "output"))
    source.mkdir()
    return SimpleNamespace(source=source, archive=archive, output=output)


def batch(folders, backend, settings=None):
    return bg.run_batch(
        folders.source, folders.archive, folders.output,
        settings or backend.settings, remover_factory=backend.factory,
    )


@pytest.mark.parametrize("extension", [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"])
def test_single_image_preserves_source_dimensions_and_soft_rgba(tmp_path, fake_backend, extension):
    source = tmp_path / ("Ada Lovelace" + extension)
    original = make_source(source, size=(37, 53))
    target = tmp_path / "result" / "Ada Lovelace.png"
    remover = fake_backend.factory(fake_backend.settings)
    try:
        record = remover.process(source, target)
    finally:
        remover.close()

    assert source.read_bytes() == original
    with Image.open(target) as image:
        assert (image.format, image.mode, image.size) == ("PNG", "RGBA", (37, 53))
        histogram = image.getchannel("A").histogram()
        assert {alpha for alpha, count in enumerate(histogram) if count} == {0, 128, 255}
    assert record["status"] == "processed"
    assert record["dimensions"] == [37, 53]
    assert record["metrics"]["soft_alpha_fraction"] > 0
    assert record["metrics"]["alpha_min"] == 0
    assert record["metrics"]["alpha_max"] == 255
    assert record["source_sha256"] == bg.sha256(source)
    assert record["output_sha256"] == bg.sha256(target)
    assert record["model_identifier"].endswith(bg.sha256(fake_backend.weights))
    assert json.loads(bg.sidecar(target).read_text()) == record
    assert fake_backend.calls[0]["mode"] == "RGB"
    assert fake_backend.calls[0]["post_process_mask"] is False
    assert_no_temporary_files(tmp_path)


def test_batch_archives_exact_originals_and_initializes_one_session(folders, fake_backend):
    originals = {
        name: make_source(folders.source / name)
        for name in ("one.jpg", "two.webp", "three.png")
    }

    summary = batch(folders, fake_backend)

    assert (summary["exit_code"], summary["outcome"]) == (0, "success")
    assert (summary["processed"], summary["skipped"], summary["failed"]) == (3, 0, 0)
    assert len(summary["files"]) == 3
    assert summary["duration"] >= 0
    assert len(fake_backend.sessions) == len(fake_backend.downloads) == 1
    assert len(fake_backend.calls) == 3
    session = fake_backend.sessions[0][2]
    assert all(call["session"] is session for call in fake_backend.calls)
    assert fake_backend.closed == fake_backend.instances
    assert fake_backend.instances[0].session is None
    for name, original in originals.items():
        assert (folders.archive / name).read_bytes() == original
        staged = folders.source / (Path(name).stem + ".png")
        target = folders.output / staged.name
        assert staged.read_bytes() == target.read_bytes()
        assert bg.sidecar(staged).read_bytes() == bg.sidecar(target).read_bytes()
        bg.validate_output(staged, (31, 47))
        if Path(name).suffix != ".png":
            assert not (folders.source / name).exists()
    assert_no_temporary_files(folders.source.parent)


@pytest.mark.parametrize("stage", ["inference", "mask", "matting"])
def test_runtime_warning_is_persisted_and_logged_on_success(tmp_path, fake_backend, caplog, stage):
    source = tmp_path / "portrait.jpg"
    original = make_source(source)
    target = tmp_path / "output" / "portrait.png"
    message = "overflow encountered in exp"
    expected = "RuntimeWarning: " + message

    def infer(image):
        warnings.warn(message, RuntimeWarning)
        return cutout(image.size)

    if stage == "matting":
        fake_backend.matting_warning = message
    else:
        fake_backend.infer = infer
    settings = replace(fake_backend.settings, alpha_matting=stage != "inference")
    remover = fake_backend.factory(settings)
    try:
        with caplog.at_level(logging.WARNING, logger=bg.LOG.name):
            # Runtime warnings must still be recorded when the caller suppresses them.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                record = remover.process(source, target)
    finally:
        remover.close()

    assert record["status"] == "processed"
    assert record["warnings"] == [expected]
    assert json.loads(bg.sidecar(target).read_text())["warnings"] == [expected]
    assert source.read_bytes() == original
    bg.validate_output(target, (31, 47))
    logged = [entry.getMessage() for entry in caplog.records
              if entry.name == bg.LOG.name and entry.levelno == logging.WARNING]
    assert len(logged) == 1
    assert expected in logged[0]
    assert "input=" + source.name in logged[0]
    assert "model=" + remover.model_identifier in logged[0]
    assert len(fake_backend.calls) == 1
    assert len(fake_backend.matting_calls) == (0 if stage == "inference" else 1)
    assert_no_temporary_files(tmp_path)


def test_batch_runtime_warnings_stay_per_image_and_reuse_one_model(folders, fake_backend, caplog):
    originals = {name: make_source(folders.source / name)
                 for name in ("a-one.jpg", "b-two.webp")}
    originals["c-clean.png"] = make_source(folders.source / "c-clean.png", color=(200, 20, 30))
    expected = "RuntimeWarning: overflow encountered in exp"

    def infer(image):
        if image.getpixel((0, 0))[0] < 100:
            warnings.warn("overflow encountered in exp", RuntimeWarning)
        return cutout(image.size)

    fake_backend.infer = infer
    with caplog.at_level(logging.WARNING, logger=bg.LOG.name):
        summary = batch(folders, fake_backend)

    assert (summary["exit_code"], summary["processed"], summary["failed"]) == (0, 3, 0)
    assert len(fake_backend.instances) == len(fake_backend.sessions) == len(fake_backend.downloads) == 1
    assert len(fake_backend.calls) == 3
    assert all(call["session"] is fake_backend.sessions[0][2] for call in fake_backend.calls)
    logged = [entry.getMessage() for entry in caplog.records
              if entry.name == bg.LOG.name and entry.levelno == logging.WARNING]
    assert len(logged) == 2
    for record in summary["files"]:
        source = Path(record["source"])
        expected_warnings = [] if source.name == "c-clean.png" else [expected]
        assert record["warnings"] == expected_warnings
        target = Path(record["output"])
        staged = folders.source / target.name
        assert json.loads(bg.sidecar(target).read_text())["warnings"] == expected_warnings
        assert json.loads(bg.sidecar(staged).read_text())["warnings"] == expected_warnings
        assert (folders.archive / source.name).read_bytes() == originals[source.name]
        bg.validate_output(target, (31, 47))
        if expected_warnings:
            matching = [message for message in logged if "input=" + source.name in message]
            assert len(matching) == 1
            assert "model=" + record["model_identifier"] in matching[0]
            assert expected in matching[0]
    assert_no_temporary_files(folders.source.parent)


def test_empty_queue_ignores_auxiliary_files_without_initializing(folders, fake_backend):
    (folders.source / ".hidden.jpg").write_bytes(b"ignored")
    (folders.source / "person.png.bg.json").write_text("{}")
    (folders.source / "subdirectory").mkdir()

    summary = batch(folders, fake_backend)

    assert (summary["exit_code"], summary["outcome"]) == (0, "no_work")
    assert (summary["processed"], summary["skipped"], summary["failed"]) == (0, 0, 0)
    assert summary["files"] == []
    assert not fake_backend.sessions
    assert not folders.archive.exists()
    assert not folders.output.exists()


@pytest.mark.parametrize("name, reason", [("broken.jpg", "cannot identify image"), ("document.txt", "Unsupported input format")])
def test_unreadable_or_unsupported_inputs_fail_without_model(folders, fake_backend, name, reason):
    source = folders.source / name
    source.write_bytes(b"not an image")

    summary = batch(folders, fake_backend)

    assert (summary["exit_code"], summary["outcome"], summary["failed"]) == (1, "partial_failure", 1)
    assert reason in summary["files"][0]["reason"]
    assert source.read_bytes() == b"not an image"
    assert not fake_backend.sessions
    assert not folders.archive.exists()
    assert not folders.output.exists()


def test_partial_failure_continues_and_preserves_failed_source(folders, fake_backend):
    bad = make_source(folders.source / "a-bad.jpg", color=(255, 0, 0))
    good = make_source(folders.source / "b-good.jpg", color=(0, 255, 0))

    def infer(image):
        if image.getpixel((0, 0))[0] > 200:
            raise RuntimeError("inference failed for red image")
        return cutout(image.size)

    fake_backend.infer = infer
    summary = batch(folders, fake_backend)

    assert (summary["exit_code"], summary["outcome"]) == (1, "partial_failure")
    assert (summary["processed"], summary["failed"]) == (1, 1)
    assert "error_category=internal_error" in summary["files"][0]["reason"]
    assert "inference failed for red image" not in summary["files"][0]["reason"]
    assert (folders.source / "a-bad.jpg").read_bytes() == bad
    assert not (folders.archive / "a-bad.jpg").exists()
    assert not (folders.output / "a-bad.png").exists()
    assert (folders.archive / "b-good.jpg").read_bytes() == good
    assert not (folders.source / "b-good.jpg").exists()
    assert len(fake_backend.sessions) == 1
    assert len(fake_backend.calls) == 2
    assert fake_backend.closed == fake_backend.instances
    assert_no_temporary_files(folders.source.parent)


def test_fatal_initialization_stops_batch_without_touching_sources(folders, fake_backend):
    originals = {name: make_source(folders.source / name) for name in ("one.jpg", "two.jpg")}
    fake_backend.init_error = RuntimeError("missing model weights")

    summary = batch(folders, fake_backend)

    assert (summary["exit_code"], summary["outcome"]) == (2, "fatal")
    assert "missing model weights" in summary["initialization_error"]
    assert summary["processed"] == 0
    assert len(fake_backend.downloads) == 1
    assert not fake_backend.calls
    assert len(fake_backend.closed) == 1
    for name, original in originals.items():
        assert (folders.source / name).read_bytes() == original
    assert not folders.archive.exists()
    assert not folders.output.exists()


def test_validate_output_rejects_uniform_soft_alpha_128(tmp_path):
    target = tmp_path / "uniform-soft.png"
    with Image.new("RGBA", (31, 47), (60, 100, 140, 128)) as image:
        image.save(target, format="PNG")
    original = target.read_bytes()

    with pytest.raises(ValueError, match="Uniform alpha mask"):
        bg.validate_output(target, (31, 47))

    assert target.read_bytes() == original


@pytest.mark.parametrize("kind", ["opaque", "transparent", "uniform_soft_128", "nearly_empty", "wrong_size", "rgb", "bytes"])
@pytest.mark.parametrize("extension", [".jpg", ".png"])
def test_invalid_inference_result_preserves_source_and_existing_output(tmp_path, fake_backend, kind, extension):
    source = tmp_path / "input" / ("person" + extension)
    original = make_source(source)
    target = tmp_path / "person.png"
    save_cutout(target)
    old_output = target.read_bytes()
    bg.sidecar(target).write_text('{"old": true}')
    old_sidecar = bg.sidecar(target).read_bytes()

    def invalid(image):
        if kind == "opaque":
            return Image.new("RGBA", image.size, (1, 2, 3, 255))
        if kind == "transparent":
            return Image.new("RGBA", image.size, (1, 2, 3, 0))
        if kind == "uniform_soft_128":
            return Image.new("RGBA", image.size, (1, 2, 3, 128))
        if kind == "nearly_empty":
            result = Image.new("RGBA", image.size, (1, 2, 3, 0))
            result.putpixel((0, 0), (1, 2, 3, 255))
            return result
        if kind == "wrong_size":
            return cutout((image.width + 1, image.height))
        if kind == "rgb":
            return Image.new("RGB", image.size)
        return b"not a PIL image"

    fake_backend.infer = invalid
    remover = fake_backend.factory(replace(fake_backend.settings, overwrite=True))
    try:
        with pytest.raises(ValueError, match="Uniform alpha mask" if kind == "uniform_soft_128" else None):
            remover.process(source, target)
    finally:
        remover.close()
    assert source.read_bytes() == original
    assert target.read_bytes() == old_output
    assert bg.sidecar(target).read_bytes() == old_sidecar
    assert_no_temporary_files(tmp_path)


def test_matching_existing_output_skips_inference(tmp_path, fake_backend):
    source = tmp_path / "person.jpg"
    original = make_source(source)
    target = tmp_path / "person.png"
    remover = fake_backend.factory(fake_backend.settings)
    try:
        first = remover.process(source, target)
        output_before = target.read_bytes()
        metadata_before = bg.sidecar(target).read_bytes()
        second = remover.process(source, target)
    finally:
        remover.close()
    assert first["status"] == "processed"
    assert second["status"] == "skipped"
    assert len(fake_backend.calls) == 1
    assert source.read_bytes() == original
    assert target.read_bytes() == output_before
    assert bg.sidecar(target).read_bytes() == metadata_before


@pytest.mark.parametrize("validation_warning", [False, True])
def test_skip_preserves_inference_warnings_without_duplicates_or_reprocessing(tmp_path, fake_backend, validation_warning):
    source = tmp_path / "person.jpg"
    original = make_source(source, size=(100, 100))
    target = tmp_path / "output" / "person.png"
    inference_warning = "RuntimeWarning: overflow encountered in exp"

    def infer(image):
        warnings.warn("overflow encountered in exp", RuntimeWarning)
        if validation_warning:
            result = Image.new("RGBA", image.size, (60, 100, 140, 255))
            result.putpixel((0, 0), (60, 100, 140, 0))
            return result
        return cutout(image.size)

    fake_backend.infer = infer
    remover = fake_backend.factory(fake_backend.settings)
    try:
        first = remover.process(source, target)
        output_before = target.read_bytes()
        metadata_before = bg.sidecar(target).read_bytes()
        skipped = [remover.process(source, target) for _ in range(2)]
    finally:
        remover.close()

    assert first["status"] == "processed"
    assert first["warnings"].count(inference_warning) == 1
    assert len(first["warnings"]) == (2 if validation_warning else 1)
    for record in skipped:
        assert record["status"] == "skipped"
        assert record["warnings"] == first["warnings"]
    assert len(fake_backend.calls) == 1
    assert source.read_bytes() == original
    assert target.read_bytes() == output_before
    assert bg.sidecar(target).read_bytes() == metadata_before
    assert json.loads(metadata_before)["warnings"] == first["warnings"]
    assert_no_temporary_files(tmp_path)


def test_batch_reuses_existing_output_for_exact_restaged_original(folders, fake_backend):
    source = folders.source / "person.jpg"
    original = make_source(source)
    assert batch(folders, fake_backend)["processed"] == 1
    staged = folders.source / "person.png"
    source.write_bytes(original)
    target = folders.output / staged.name
    output_before = target.read_bytes()

    summary = batch(folders, fake_backend)

    assert (summary["exit_code"], summary["processed"], summary["skipped"]) == (0, 0, 1)
    assert len(fake_backend.calls) == 1
    assert target.read_bytes() == staged.read_bytes() == output_before
    assert (folders.archive / source.name).read_bytes() == original
    assert not source.exists()


@pytest.mark.parametrize("existing", ["corrupt", "rgb", "wrong_dimensions"])
def test_invalid_existing_output_requires_explicit_overwrite(tmp_path, fake_backend, existing):
    source = tmp_path / "person.jpg"
    original = make_source(source)
    target = tmp_path / "person.png"
    if existing == "corrupt":
        target.write_bytes(b"not a png")
    elif existing == "rgb":
        make_source(target)
    else:
        save_cutout(target, size=(32, 47))
    previous_output = target.read_bytes()
    remover = fake_backend.factory(fake_backend.settings)
    try:
        with pytest.raises((OSError, ValueError)):
            remover.process(source, target)
    finally:
        remover.close()
    assert source.read_bytes() == original
    assert target.read_bytes() == previous_output
    assert not fake_backend.calls
    assert not bg.sidecar(target).exists()


def test_animated_input_is_rejected_without_inference(tmp_path, fake_backend):
    source = tmp_path / "animated.webp"
    with Image.new("RGB", (31, 47), (255, 0, 0)) as first:
        with Image.new("RGB", (31, 47), (0, 255, 0)) as second:
            first.save(source, save_all=True, append_images=[second], duration=100, loop=0)
    original = source.read_bytes()
    target = tmp_path / "animated.png"
    remover = fake_backend.factory(fake_backend.settings)
    try:
        with pytest.raises(ValueError, match="Animated/multipage input is unsupported"):
            remover.process(source, target)
    finally:
        remover.close()
    assert source.read_bytes() == original
    assert not target.exists()
    assert not fake_backend.calls


@pytest.mark.parametrize("extension", [".gif", ".txt"])
def test_process_rejects_unsupported_suffix_even_for_decodable_image(tmp_path, fake_backend, extension):
    source = tmp_path / ("person" + extension)
    with Image.new("RGB", (31, 47), (60, 100, 140)) as image:
        image.save(source, format="PNG")
    original = source.read_bytes()
    target = tmp_path / "person.png"
    remover = fake_backend.factory(fake_backend.settings)
    try:
        with pytest.raises(ValueError, match="Unsupported input format"):
            remover.process(source, target)
    finally:
        remover.close()
    assert source.read_bytes() == original
    assert not target.exists()
    assert not fake_backend.calls


@pytest.mark.parametrize("drift", ["missing_sidecar", "corrupt_sidecar", "settings", "model_identifier", "source", "output"])
def test_provenance_drift_refuses_existing_output(tmp_path, fake_backend, drift):
    source = tmp_path / "person.jpg"
    make_source(source)
    target = tmp_path / "person.png"
    remover = fake_backend.factory(fake_backend.settings)
    try:
        remover.process(source, target)
        metadata_path = bg.sidecar(target)
        if drift == "missing_sidecar":
            metadata_path.unlink()
        elif drift == "corrupt_sidecar":
            metadata_path.write_text("not json")
        elif drift in {"settings", "model_identifier"}:
            metadata = json.loads(metadata_path.read_text())
            metadata[drift] = {"engine": "adobe"} if drift == "settings" else "other-weights"
            metadata_path.write_text(json.dumps(metadata))
        elif drift == "source":
            make_source(source, color=(200, 20, 30))
        else:
            save_cutout(target, color=(200, 20, 30))
        expected_source, expected_output = source.read_bytes(), target.read_bytes()
        with pytest.raises(FileExistsError, match="provenance differs or is unknown"):
            remover.process(source, target)
    finally:
        remover.close()
    assert source.read_bytes() == expected_source
    assert target.read_bytes() == expected_output
    assert len(fake_backend.calls) == 1


def test_explicit_overwrite_reprocesses_and_updates_provenance(tmp_path, fake_backend):
    source = tmp_path / "person.jpg"
    original = make_source(source)
    target = tmp_path / "person.png"
    save_cutout(target, color=(200, 20, 30))
    prior = target.read_bytes()
    remover = fake_backend.factory(replace(fake_backend.settings, overwrite=True))
    try:
        record = remover.process(source, target)
    finally:
        remover.close()
    assert record["status"] == "processed"
    assert target.read_bytes() != prior
    assert source.read_bytes() == original
    assert json.loads(bg.sidecar(target).read_text())["source_sha256"] == bg.sha256(source)
    assert len(fake_backend.calls) == 1


def test_staged_cutout_rerun_skips_without_loading_model(folders, fake_backend):
    make_source(folders.source / "person.jpg")
    assert batch(folders, fake_backend)["processed"] == 1
    originals = {path: path.read_bytes() for path in folders.source.iterdir()}
    summary = batch(folders, fake_backend)
    assert (summary["exit_code"], summary["outcome"], summary["skipped"]) == (0, "no_work", 1)
    assert len(fake_backend.sessions) == len(fake_backend.calls) == 1
    assert all(path.read_bytes() == content for path, content in originals.items())


@pytest.mark.parametrize("overwrite", [False, True])
@pytest.mark.parametrize("drift", ["missing", "settings", "output"])
def test_unknown_or_changed_staged_cutout_is_never_used_as_source(folders, fake_backend, overwrite, drift):
    staged = folders.source / "person.png"
    save_cutout(staged)
    metadata = {"settings": fake_backend.settings.fingerprint(), "output_sha256": bg.sha256(staged)}
    if drift == "settings":
        metadata["settings"] = {"engine": "adobe"}
    if drift != "missing":
        bg.sidecar(staged).write_text(json.dumps(metadata))
    if drift == "output":
        save_cutout(staged, color=(200, 10, 10))
    original = staged.read_bytes()

    summary = batch(folders, fake_backend, replace(fake_backend.settings, overwrite=overwrite))

    assert (summary["exit_code"], summary["failed"]) == (1, 1)
    assert "provenance" in summary["files"][0]["reason"]
    assert staged.read_bytes() == original
    assert not fake_backend.sessions
    assert not folders.archive.exists()


def test_process_rejects_source_as_destination_even_with_overwrite(tmp_path, fake_backend):
    source = tmp_path / "person.png"
    original = make_source(source)
    remover = fake_backend.factory(replace(fake_backend.settings, overwrite=True))
    try:
        with pytest.raises(ValueError, match="must differ from the source"):
            remover.process(source, source)
    finally:
        remover.close()
    assert source.read_bytes() == original
    assert not fake_backend.calls


@pytest.mark.parametrize("names", [
    ("person.jpg", "person.webp"),
    ("Person.jpg", "person.png"),
    ("Ren\u00e9.jpg", "Rene\u0301.webp"),
])
def test_basename_collisions_preserve_all_inputs(folders, fake_backend, names):
    originals = {name: make_source(folders.source / name) for name in names}
    summary = batch(folders, fake_backend)
    assert (summary["exit_code"], summary["failed"]) == (1, 2)
    assert all("Ambiguous input basenames" in record["reason"] for record in summary["files"])
    assert all((folders.source / name).read_bytes() == data for name, data in originals.items())
    assert not fake_backend.sessions
    assert not folders.archive.exists()
    assert not folders.output.exists()


@pytest.mark.parametrize("identical", [False, True])
@pytest.mark.parametrize("extension", [".jpg", ".png"])
@pytest.mark.parametrize("layout", ["flat", "sorted"])
def test_archive_collision_never_overwrites_original(folders, fake_backend, identical, extension, layout):
    source = folders.source / ("person" + extension)
    original = make_source(source)
    flat_archive = folders.archive / source.name
    archived = (flat_archive if layout == "flat"
                else folders.archive / "P" / "Images" / source.name)
    archived.parent.mkdir(parents=True)
    archived.write_bytes(original if identical else b"previous original")
    archive_before = archived.read_bytes()

    summary = batch(folders, fake_backend)

    assert archived.read_bytes() == archive_before
    if identical:
        assert (summary["exit_code"], summary["processed"]) == (0, 1)
        assert flat_archive.read_bytes() == original
        bg.validate_output(folders.output / (source.stem + ".png"), (31, 47))
        if extension == ".png":
            bg.validate_output(source, (31, 47))
        else:
            assert not source.exists()
    else:
        assert (summary["exit_code"], summary["failed"]) == (1, 1)
        assert "Preserved original differs" in summary["files"][0]["reason"]
        assert str(archived) in summary["files"][0]["reason"]
        assert source.read_bytes() == original
        assert not fake_backend.sessions
        assert not folders.output.exists()
        if layout == "sorted":
            assert not flat_archive.exists()


@pytest.mark.parametrize("extension", [".jpg", ".png"])
@pytest.mark.parametrize("identical", [False, True])
def test_archive_source_checks_sorted_original_even_when_flat_archive_matches(folders, extension, identical):
    source = folders.source / ("person" + extension)
    original = make_source(source)
    flat_archive = folders.archive / source.name
    sorted_archive = folders.archive / "P" / "Images" / source.name
    sorted_archive.parent.mkdir(parents=True)
    flat_archive.write_bytes(original)
    sorted_before = make_source(sorted_archive, color=(200, 20, 30)) if not identical else original
    sorted_archive.write_bytes(sorted_before)

    if identical:
        assert bg.archive_source(source, folders.archive) == flat_archive
    else:
        with pytest.raises(FileExistsError, match="Preserved original differs") as exc:
            bg.archive_source(source, folders.archive)
        assert str(sorted_archive) in str(exc.value)

    assert source.read_bytes() == flat_archive.read_bytes() == original
    assert sorted_archive.read_bytes() == sorted_before
    assert_no_temporary_files(folders.source.parent)


@pytest.mark.parametrize("extension", [".jpg", ".png"])
def test_sorted_archive_collision_created_during_inference_preserves_queued_photo(folders, fake_backend, extension):
    source = folders.source / ("person" + extension)
    original = make_source(source)
    sorted_archive = folders.archive / "P" / "Images" / source.name
    preserved = []

    def infer(image):
        preserved.append(make_source(sorted_archive, color=(200, 20, 30)))
        return cutout(image.size)

    fake_backend.infer = infer
    summary = batch(folders, fake_backend)

    assert (summary["exit_code"], summary["processed"], summary["failed"]) == (1, 0, 1)
    assert str(sorted_archive) in summary["files"][0]["reason"]
    assert "Preserved original differs" in summary["files"][0]["reason"]
    assert source.read_bytes() == original
    assert sorted_archive.read_bytes() == preserved[0]
    assert not (folders.archive / source.name).exists()
    target = folders.output / (source.stem + ".png")
    bg.validate_output(target, (31, 47))
    if extension == ".jpg":
        assert not (folders.source / target.name).exists()
    assert len(fake_backend.calls) == 1
    assert fake_backend.closed == fake_backend.instances
    assert_no_temporary_files(folders.source.parent)


@pytest.mark.parametrize("same_as", ["source", "output"])
def test_archive_directory_cannot_alias_working_directories(folders, fake_backend, same_as):
    with pytest.raises(ValueError, match="SEL_ORIG_DIR must differ"):
        bg.run_batch(folders.source, getattr(folders, same_as), folders.output,
                     fake_backend.settings, remover_factory=fake_backend.factory)
    assert not fake_backend.sessions


def test_missing_input_directory_is_actionable(folders, fake_backend):
    with pytest.raises(ValueError, match="Input folder does not exist"):
        bg.run_batch(folders.source / "missing", folders.archive, folders.output,
                     fake_backend.settings, remover_factory=fake_backend.factory)
    assert not fake_backend.sessions


@pytest.mark.parametrize("overwrite", [False, True])
def test_existing_staged_output_requires_explicit_overwrite(folders, fake_backend, overwrite):
    source = folders.source / "person.jpg"
    original = make_source(source)
    staged = folders.source / "person.png"
    save_cutout(staged)
    staged_before = staged.read_bytes()
    summary = batch(folders, fake_backend, replace(fake_backend.settings, overwrite=overwrite))
    if overwrite:
        assert (summary["exit_code"], summary["processed"], summary["failed"]) == (0, 1, 0)
        assert (folders.archive / source.name).read_bytes() == original
        assert not source.exists()
        assert staged.read_bytes() == (folders.output / staged.name).read_bytes()
        assert len(fake_backend.calls) == 1
    else:
        assert (summary["exit_code"], summary["failed"]) == (1, 1)
        assert "explicit overwrite required" in summary["files"][0]["reason"]
        assert source.read_bytes() == original
        assert staged.read_bytes() == staged_before
        assert not fake_backend.calls
        assert not folders.archive.exists()
        assert not folders.output.exists()


@pytest.mark.parametrize("operation", ["output_replace", "archive_copy", "staged_copy", "sidecar_copy", "source_unlink"])
def test_publication_failures_keep_jpeg_source_and_clean_temporary_files(monkeypatch, folders, fake_backend, operation):
    source = folders.source / "person.jpg"
    original = make_source(source)
    target = folders.output / "person.png"
    staged = folders.source / target.name
    real_replace, real_copy, real_unlink = Path.replace, bg.atomic_copy, Path.unlink

    def fail_replace(path, destination):
        if operation == "output_replace" and Path(destination) == target:
            assert path.parent == target.parent
            bg.validate_output(path, (31, 47))
            assert source.read_bytes() == original
            raise PermissionError("output replacement blocked")
        return real_replace(path, destination)

    def fail_copy(src, dst):
        selected = {
            "archive_copy": folders.archive / source.name,
            "staged_copy": staged,
            "sidecar_copy": bg.sidecar(staged),
        }.get(operation)
        if dst == selected:
            raise PermissionError("copy blocked: " + operation)
        return real_copy(src, dst)

    def fail_unlink(path, *args, **kwargs):
        if operation == "source_unlink" and path == source:
            raise PermissionError("source locked")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "replace", fail_replace)
    monkeypatch.setattr(bg, "atomic_copy", fail_copy)
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    summary = batch(folders, fake_backend)

    assert (summary["exit_code"], summary["processed"], summary["failed"]) == (1, 0, 1)
    assert source.read_bytes() == original
    if operation in {"staged_copy", "sidecar_copy", "source_unlink"}:
        assert (folders.archive / source.name).read_bytes() == original
    if operation == "output_replace":
        assert not target.exists()
    assert fake_backend.closed == fake_backend.instances
    assert_no_temporary_files(folders.source.parent)


def test_png_original_remains_archived_when_staging_metadata_copy_fails(monkeypatch, folders, fake_backend):
    source = folders.source / "person.png"
    original = make_source(source)
    real_copy = bg.atomic_copy

    def fail_copy(src, dst):
        if dst == bg.sidecar(source):
            raise PermissionError("staging metadata locked")
        return real_copy(src, dst)

    monkeypatch.setattr(bg, "atomic_copy", fail_copy)
    summary = batch(folders, fake_backend)

    assert (summary["exit_code"], summary["processed"], summary["failed"]) == (1, 0, 1)
    assert "error_category=permission" in summary["files"][0]["reason"]
    assert "staging metadata locked" not in summary["files"][0]["reason"]
    assert (folders.archive / source.name).read_bytes() == original
    # PNG handoff replaces the queue photograph only after archiving its bytes.
    bg.validate_output(source, (31, 47))
    assert source.read_bytes() == (folders.output / source.name).read_bytes()
    assert fake_backend.closed == fake_backend.instances
    assert_no_temporary_files(folders.source.parent)


def test_png_queue_is_replaced_only_after_output_validation_and_verified_archive(monkeypatch, folders, fake_backend):
    source = folders.source / "person.png"
    original = make_source(source)
    target = folders.output / source.name
    archived = folders.archive / source.name
    real_copy = bg.atomic_copy
    staging_calls = []

    def copy_after_archive(src, dst):
        if dst == source:
            assert src == target
            assert source.read_bytes() == archived.read_bytes() == original
            bg.validate_output(target, (31, 47))
            staging_calls.append(dst)
        return real_copy(src, dst)

    monkeypatch.setattr(bg, "atomic_copy", copy_after_archive)
    summary = batch(folders, fake_backend)

    assert (summary["exit_code"], summary["processed"]) == (0, 1)
    assert staging_calls == [source]
    assert archived.read_bytes() == original
    assert source.read_bytes() == target.read_bytes()
    assert source.read_bytes() != original


def test_png_archive_copy_failure_keeps_queue_photograph(monkeypatch, folders, fake_backend):
    source = folders.source / "person.png"
    original = make_source(source)
    real_copy = bg.atomic_copy

    def fail_archive_copy(src, dst):
        if dst == folders.archive / source.name:
            raise PermissionError("archive locked")
        return real_copy(src, dst)

    monkeypatch.setattr(bg, "atomic_copy", fail_archive_copy)
    summary = batch(folders, fake_backend)

    assert (summary["exit_code"], summary["processed"], summary["failed"]) == (1, 0, 1)
    assert "error_category=permission" in summary["files"][0]["reason"]
    assert "archive locked" not in summary["files"][0]["reason"]
    assert source.read_bytes() == original
    assert not (folders.archive / source.name).exists()
    bg.validate_output(folders.output / source.name, (31, 47))
    assert_no_temporary_files(folders.source.parent)


@pytest.mark.parametrize("kind", ["json", "copy"])
def test_atomic_helpers_preserve_existing_destination_on_replace_failure(monkeypatch, tmp_path, kind):
    source = tmp_path / "source.bin"
    source.write_bytes(b"new contents")
    destination = tmp_path / "destination.bin"
    destination.write_bytes(b"old contents")
    real_replace = Path.replace

    def fail_replace(path, target):
        if Path(target) == destination:
            assert path.parent == destination.parent
            assert path.name.startswith(".bg-")
            raise PermissionError("destination locked")
        return real_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(PermissionError, match="destination locked"):
        if kind == "json":
            bg.atomic_json(destination, {"status": "processed"})
        else:
            bg.atomic_copy(source, destination)
    assert destination.read_bytes() == b"old contents"
    assert source.read_bytes() == b"new contents"
    assert_no_temporary_files(tmp_path)


def test_atomic_copy_rejects_corrupt_copy(monkeypatch, tmp_path):
    source, destination = tmp_path / "source.bin", tmp_path / "destination.bin"
    source.write_bytes(b"original")
    destination.write_bytes(b"previous")
    monkeypatch.setattr(bg.shutil, "copyfile", lambda src, dst: Path(dst).write_bytes(b"corrupt"))
    with pytest.raises(OSError, match="Copy verification failed"):
        bg.atomic_copy(source, destination)
    assert source.read_bytes() == b"original"
    assert destination.read_bytes() == b"previous"
    assert_no_temporary_files(tmp_path)


def test_constructor_rejects_cached_checksum_mismatch(fake_backend):
    fake_backend.weights.write_bytes(b"corrupted cached weights")
    with pytest.raises(RuntimeError, match="Model checksum mismatch"):
        fake_backend.factory(fake_backend.settings)
    assert not fake_backend.sessions
    assert not fake_backend.calls


@pytest.mark.parametrize("failure", ["disabled_checksum", "unavailable_provider", "missing_model", "missing_weights", "inactive_provider"])
def test_constructor_errors_are_actionable(monkeypatch, fake_backend, failure):
    expected = {
        "disabled_checksum": "Unset MODEL_CHECKSUM_DISABLED",
        "unavailable_provider": "CPUExecutionProvider unavailable",
        "missing_model": "does not support birefnet-portrait",
        "missing_weights": "Cannot initialize birefnet-portrait",
        "inactive_provider": "Requested CPUExecutionProvider",
    }[failure]
    if failure == "disabled_checksum":
        monkeypatch.setenv("MODEL_CHECKSUM_DISABLED", "false")
    elif failure == "unavailable_provider":
        fake_backend.available = []
    elif failure == "missing_model":
        monkeypatch.setattr(sys.modules["rembg.sessions"], "sessions_class", [])
    elif failure == "missing_weights":
        fake_backend.weights.unlink()
    else:
        fake_backend.active = ["CUDAExecutionProvider"]
    with pytest.raises(RuntimeError, match=expected):
        fake_backend.factory(fake_backend.settings)
    assert not fake_backend.calls


@pytest.mark.parametrize("decontaminate", [False, True])
def test_inference_options_and_cpu_provider_are_forwarded(tmp_path, fake_backend, decontaminate):
    source = tmp_path / "person.jpg"
    original = make_source(source)
    settings = replace(fake_backend.settings, alpha_matting=True, decontaminate=decontaminate)
    remover = fake_backend.factory(settings)
    try:
        remover.process(source, tmp_path / "person.png")
    finally:
        remover.close()
    assert fake_backend.sessions[0][:2] == ("birefnet-portrait", ["CPUExecutionProvider"])
    assert len(fake_backend.calls) == 1
    assert fake_backend.calls[0]["only_mask"] is True
    assert fake_backend.calls[0]["alpha_matting"] is False
    assert fake_backend.calls[0]["decontaminate"] is False
    assert fake_backend.calls[0]["post_process_mask"] is False
    assert fake_backend.matting_calls == [{
        "size": (31, 47), "mode": "RGB", "mask_size": (31, 47),
        "mask_mode": "L", "thresholds": (240, 10, 10),
    }]
    assert source.read_bytes() == original
    assert remover._matting is None
    assert remover._remove is None
    assert remover.session is None
    with pytest.raises(ValueError, match="closed image"):
        fake_backend.masks[0].getpixel((0, 0))


@pytest.mark.parametrize("alpha_matting", [False, True])
def test_matting_dependency_is_required_only_when_enabled(monkeypatch, fake_backend, alpha_matting):
    monkeypatch.setitem(sys.modules, "rembg.bg", None)
    settings = replace(fake_backend.settings, alpha_matting=alpha_matting)
    if alpha_matting:
        with pytest.raises(RuntimeError, match="Cannot initialize birefnet-portrait"):
            fake_backend.factory(settings)
        assert len(fake_backend.closed) == 1
        assert fake_backend.closed[0]._matting is None
        assert fake_backend.closed[0].session is None
    else:
        remover = fake_backend.factory(settings)
        try:
            assert remover._matting is None
            assert remover.session is not None
        finally:
            remover.close()
    assert not fake_backend.calls


@pytest.mark.parametrize("extension", [".jpg", ".png"])
@pytest.mark.parametrize("existing_output", [False, True])
def test_strict_matting_solver_failure_preserves_source_without_publishing(tmp_path, fake_backend, extension, existing_output):
    source = tmp_path / "input" / ("person" + extension)
    original = make_source(source)
    target = tmp_path / "output" / "person.png"
    if existing_output:
        save_cutout(target)
        bg.sidecar(target).write_text('{"prior": true}')
        previous_output = target.read_bytes()
        previous_metadata = bg.sidecar(target).read_bytes()
    fake_backend.matting_error = ValueError("matting solver failed")
    settings = replace(fake_backend.settings, alpha_matting=True, overwrite=True)
    remover = fake_backend.factory(settings)
    try:
        with pytest.raises(ValueError, match="matting solver failed") as exc:
            remover.process(source, target)
        assert exc.value is fake_backend.matting_error
    finally:
        remover.close()

    assert source.read_bytes() == original
    if existing_output:
        assert target.read_bytes() == previous_output
        assert bg.sidecar(target).read_bytes() == previous_metadata
    else:
        assert not target.exists()
        assert not bg.sidecar(target).exists()
    assert len(fake_backend.calls) == len(fake_backend.matting_calls) == 1
    assert fake_backend.calls[0]["only_mask"] is True
    assert fake_backend.calls[0]["alpha_matting"] is False
    assert fake_backend.calls[0]["decontaminate"] is False
    assert remover._matting is None
    assert remover.session is None
    with pytest.raises(ValueError, match="closed image"):
        fake_backend.masks[0].getpixel((0, 0))
    assert_no_temporary_files(tmp_path)


@pytest.mark.parametrize("extension", [".jpg", ".png"])
def test_runtime_warnings_are_logged_when_matting_fails_and_existing_output_is_retained(tmp_path, fake_backend, caplog, extension):
    source = tmp_path / "input" / ("portrait" + extension)
    original = make_source(source)
    target = tmp_path / "output" / "portrait.png"
    save_cutout(target)
    previous_output = target.read_bytes()
    bg.sidecar(target).write_text('{"warnings": ["previous output warning"]}')
    previous_metadata = bg.sidecar(target).read_bytes()

    def infer(image):
        warnings.warn("overflow encountered in exp", RuntimeWarning)
        return cutout(image.size)

    fake_backend.infer = infer
    fake_backend.matting_warning = "matting solver produced non-finite values"
    fake_backend.matting_error = ValueError("matting solver failed")
    settings = replace(fake_backend.settings, alpha_matting=True, overwrite=True)
    remover = fake_backend.factory(settings)
    try:
        with caplog.at_level(logging.WARNING, logger=bg.LOG.name):
            with pytest.raises(ValueError, match="matting solver failed") as exc:
                remover.process(source, target)
        assert exc.value is fake_backend.matting_error
    finally:
        remover.close()

    assert source.read_bytes() == original
    assert target.read_bytes() == previous_output
    assert bg.sidecar(target).read_bytes() == previous_metadata
    logged = [entry.getMessage() for entry in caplog.records
              if entry.name == bg.LOG.name and entry.levelno == logging.WARNING]
    assert len(logged) == 2
    for message in logged:
        assert "input=" + source.name in message
        assert "model=" + remover.model_identifier in message
    assert any("RuntimeWarning: overflow encountered in exp" in message for message in logged)
    assert any("RuntimeWarning: matting solver produced non-finite values" in message for message in logged)
    assert len(fake_backend.calls) == len(fake_backend.matting_calls) == 1
    assert fake_backend.closed == fake_backend.instances
    assert_no_temporary_files(tmp_path)


@pytest.mark.parametrize("extension", [".jpg", ".png"])
def test_batch_strict_matting_solver_failure_keeps_queue_and_blocks_handoff(folders, fake_backend, extension):
    source = folders.source / ("person" + extension)
    original = make_source(source)
    fake_backend.matting_error = ValueError("matting solver failed")

    summary = batch(folders, fake_backend, replace(fake_backend.settings, alpha_matting=True))

    assert (summary["exit_code"], summary["outcome"]) == (1, "partial_failure")
    assert (summary["processed"], summary["failed"]) == (0, 1)
    assert "error_category=invalid_data" in summary["files"][0]["reason"]
    assert "matting solver failed" not in summary["files"][0]["reason"]
    assert source.read_bytes() == original
    assert not folders.archive.exists()
    assert not (folders.output / "person.png").exists()
    assert not bg.sidecar(folders.output / "person.png").exists()
    assert not bg.sidecar(folders.source / "person.png").exists()
    assert len(fake_backend.calls) == len(fake_backend.matting_calls) == 1
    assert fake_backend.closed == fake_backend.instances
    assert fake_backend.instances[0]._matting is None
    assert_no_temporary_files(folders.source.parent)


@pytest.fixture
def isolated_cli(monkeypatch, tmp_path, fake_backend):
    monkeypatch.setattr(bg, "CONFIG_DIR", tmp_path / "config")
    dotenv = ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "dotenv", dotenv)
    for key in ("REMOVE_BG_MODEL", "REMOVE_BG_DEVICE", "REMOVE_BG_DECONTAMINATE",
                "REMOVE_BG_ALPHA_MATTING", "REMOVE_BG_OVERWRITE"):
        monkeypatch.delenv(key, raising=False)
    # Leave pytest's logging handlers in place; CLI logs stay under tmp_path.
    monkeypatch.setattr(bg.logging, "basicConfig", lambda **kwargs: [handler.close() for handler in kwargs["handlers"]])
    return tmp_path / "summary.json"


@pytest.mark.parametrize("fails", [False, True])
def test_single_image_cli_writes_summary_and_preserves_input(tmp_path, fake_backend, isolated_cli, fails):
    source = tmp_path / "person.jpg"
    original = make_source(source)
    target = tmp_path / "person.png"
    if fails:
        fake_backend.init_error = RuntimeError("weights unavailable")
    code = bg.main(["--input", str(source), "--output", str(target), "--summary", str(isolated_cli)])
    summary = json.loads(isolated_cli.read_text())
    assert code == summary["exit_code"] == (2 if fails else 0)
    assert summary["outcome"] == ("fatal" if fails else "success")
    assert source.read_bytes() == original
    if fails:
        assert "weights unavailable" in summary["reason"]
        assert not target.exists()
    else:
        assert summary["files"][0]["status"] == "processed"
        assert len(fake_backend.closed) == 1
        assert fake_backend.closed[0].session is None


def test_batch_cli_uses_existing_directory_environment_and_propagates_failure(monkeypatch, folders, fake_backend, isolated_cli):
    (folders.source / "bad.jpg").write_bytes(b"corrupt")
    make_source(folders.source / "good.jpg")
    monkeypatch.setenv("SEL_SRC_DIR", str(folders.source))
    monkeypatch.setenv("SEL_ORIG_DIR", str(folders.archive))
    monkeypatch.setenv("SEL_DOWNLOAD_DIR", str(folders.output))
    code = bg.main(["--summary", str(isolated_cli)])
    summary = json.loads(isolated_cli.read_text())
    assert code == summary["exit_code"] == 1
    assert summary["outcome"] == "partial_failure"
    assert (summary["processed"], summary["failed"]) == (1, 1)
    assert (folders.source / "bad.jpg").read_bytes() == b"corrupt"
    assert (folders.archive / "good.jpg").exists()


def test_real_model_smoke_only_with_explicit_input_and_verified_cached_weights(monkeypatch, tmp_path):
    input_value = os.getenv("REMOVE_BG_SMOKE_INPUT")
    if not input_value:
        pytest.skip("Set REMOVE_BG_SMOKE_INPUT and REMBG_HOME to opt into cached-model inference")
    source = Path(input_value).expanduser().resolve()
    if not source.is_file():
        pytest.fail("REMOVE_BG_SMOKE_INPUT is not an existing photograph")
    settings = replace(bg.Settings.from_env(), device="cpu", overwrite=False)
    candidates = (
        settings.home / "models" / settings.model / (settings.model + ".onnx"),
        settings.home / (settings.model + ".onnx"),
    )
    weights = next((path for path in candidates if path.is_file()), None)
    if weights is None:
        pytest.skip("Smoke test requires already cached weights: " + ", ".join(map(str, candidates)))
    with weights.open("rb") as handle:
        checksum = hashlib.file_digest(handle, "md5").hexdigest()
    if checksum != bg.MODEL_CHECKSUMS[settings.model]:
        pytest.fail("Cached smoke-test weights do not match the published checksum")
    pytest.importorskip("onnxruntime")
    pytest.importorskip("rembg")
    from rembg.sessions import sessions_class

    model_class = next((cls for cls in sessions_class if cls.name() == settings.model), None)
    assert model_class is not None, "Installed rembg does not support the smoke model"
    # new_session also calls this method; bypass its downloader in both places.
    monkeypatch.setattr(model_class, "download_models", classmethod(lambda cls, *args, **kwargs: str(weights)))
    monkeypatch.setenv("REMBG_HOME", str(settings.home))
    monkeypatch.setenv("U2NET_HOME", str(settings.home))
    before = bg.sha256(source)
    with Image.open(source) as image:
        expected_size = image.size
    remover = bg.LocalRemover(settings)
    try:
        record = remover.process(source, tmp_path / "smoke.png")
    finally:
        remover.close()
    assert record["status"] == "processed"
    bg.validate_output(tmp_path / "smoke.png", expected_size)
    assert bg.sha256(source) == before
    assert_no_temporary_files(tmp_path)


@pytest.mark.parametrize("layout", ["nested", "flat", "both"])
def test_smoke_cache_discovery_with_fake_model(monkeypatch, tmp_path, fake_backend, layout):
    source = tmp_path / "portrait.jpg"
    original = make_source(source)
    if layout in {"nested", "both"}:
        nested = fake_backend.settings.home / "models" / "birefnet-portrait" / "birefnet-portrait.onnx"
        nested.parent.mkdir(parents=True)
        nested.write_bytes(fake_backend.weights.read_bytes())
        if layout == "nested":
            fake_backend.weights.unlink()
        else:
            fake_backend.weights.write_bytes(b"legacy cache must not take precedence")
    monkeypatch.setenv("REMOVE_BG_SMOKE_INPUT", str(source))
    monkeypatch.setenv("REMOVE_BG_MODEL", "birefnet-portrait")
    monkeypatch.setenv("REMOVE_BG_DEVICE", "cpu")
    monkeypatch.setenv("REMOVE_BG_DECONTAMINATE", "true")
    monkeypatch.setenv("REMOVE_BG_ALPHA_MATTING", "false")
    monkeypatch.setenv("REMOVE_BG_OVERWRITE", "false")

    try:
        test_real_model_smoke_only_with_explicit_input_and_verified_cached_weights(monkeypatch, tmp_path)
    except pytest.skip.Exception as exc:
        pytest.fail("Available cached weights must run the smoke test: " + str(exc))

    assert len(fake_backend.sessions) == len(fake_backend.calls) == 1
    assert len(fake_backend.closed) == 1
    assert source.read_bytes() == original
