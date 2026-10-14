from __future__ import annotations

import base64
import csv
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace

import pytest
from PIL import Image, features

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import compare_background_removers as benchmark


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.metadata = []
        self.assets = {}
        self._template = None
        self._data = False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "template":
            self._template = attrs.get("id")
        elif tag == "img" and self._template:
            self.assets[self._template] = attrs["src"]
        elif tag == "script" and attrs.get("id") == "data":
            self._data = True

    def handle_endtag(self, tag):
        if tag == "template":
            self._template = None
        elif tag == "script":
            self._data = False

    def handle_data(self, value):
        if self._data:
            self.metadata.append(value)


def parse_report(path):
    parser = ReportParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return json.loads("".join(parser.metadata)), parser.assets


@pytest.fixture
def no_clone(monkeypatch):
    run = benchmark.subprocess.run
    def checked(command, *args, **kwargs):
        if isinstance(command, (list, tuple)) and list(command[:2]) == ["git", "clone"]:
            pytest.fail("No automatic clone")
        return run(command, *args, **kwargs)
    monkeypatch.setattr(benchmark.subprocess, "run", checked)


def photograph(path: Path, size=(8, 8)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (100, 120, 140)).save(path)
    return path


def cutout(path: Path, size=(8, 8), color=(100, 120, 140), alpha=None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", size, (*color, 0))
    if alpha is None:
        for y in range(2, size[1] - 2):
            for x in range(2, size[0] - 2):
                image.putpixel((x, y), (*color, 255))
    else:
        image.putalpha(alpha)
    image.save(path)
    return path


@pytest.fixture
def roots(tmp_path, monkeypatch):
    for key in ("SEL_SRC_DIR", "SEL_ORIG_DIR", "SEL_DOWNLOAD_DIR", "PEOPLE_IMAGES_DIR", "POSTER_DIR"):
        monkeypatch.delenv(key, raising=False)
    originals, adobe, output, home = [tmp_path / name for name in ("originals", "adobe", "benchmark", "models")]
    originals.mkdir()
    adobe.mkdir()
    return SimpleNamespace(originals=originals, adobe=adobe, output=output, home=home)


def options(roots, **kwargs):
    return benchmark.BenchmarkOptions(originals=roots.originals, adobe=roots.adobe,
                                      output=roots.output, home=roots.home, **kwargs)


class MockRemover:
    events = []
    active = 0
    fail_name = None

    def __init__(self, settings):
        assert self.active == 0, "Only one model may be alive"
        type(self).active += 1
        self.settings = settings
        self.model_identifier = settings.model + ":mock-hash"
        self.rembg_version = "mock"
        self.events.append(("open", settings.model))

    def process(self, source, destination):
        self.events.append(("process", self.settings.model))
        if self.fail_name == self.settings.model:
            raise RuntimeError("Mock inference failure")
        with Image.open(source) as image:
            size = image.size
        cutout(destination, size)
        metadata = {"source_sha256": benchmark.sha256(source), "output_sha256": benchmark.sha256(destination),
                    "settings": {"model": self.settings.model, "device": self.settings.device,
                                 "decontaminate": self.settings.decontaminate, "alpha_matting": self.settings.alpha_matting},
                    "model_identifier": self.model_identifier, "duration": 2.5}
        destination.with_suffix(".png.bg.json").write_text(json.dumps(metadata), encoding="utf-8")
        return {"status": "processed", "dimensions": list(size), "duration": 2.5, "warnings": [], "metrics": {}}

    def close(self):
        type(self).active -= 1
        self.events.append(("close", self.settings.model))


@pytest.fixture
def mocked():
    MockRemover.events = []
    MockRemover.active = 0
    MockRemover.fail_name = None
    return {"remover_factory": MockRemover, "settings_factory": SimpleNamespace}


def test_unicode_case_extensions_and_relative_path_precedence(roots):
    photograph(roots.originals / "group" / "Jose\u0301.JPG")
    cutout(roots.adobe / "GROUP" / "JOS\u00c9.png")
    cutout(roots.adobe / "elsewhere" / "JOS\u00c9.png")
    matched = benchmark.match_images(roots.originals, roots.adobe)
    assert len(matched["matches"]) == 1
    assert matched["matches"][0]["path_confidence"] == "relative-path"
    assert any(row["kind"] == "duplicate_filename" for row in matched["issues"])
    assert any(row["kind"] == "missing_original" for row in matched["issues"])


def test_unique_basename_fallback_and_missing_inputs(roots):
    photograph(roots.originals / "a" / "person.jpg")
    photograph(roots.originals / "missing.jpg")
    cutout(roots.adobe / "b" / "PERSON.png")
    cutout(roots.adobe / "orphan.png")
    matched = benchmark.match_images(roots.originals, roots.adobe)
    assert [row["path_confidence"] for row in matched["matches"]] == ["unique-basename"]
    assert {row["kind"] for row in matched["issues"]} == {"missing_original", "missing_adobe"}


def test_ambiguous_basenames_never_choose_first(roots):
    photograph(roots.originals / "person.jpg")
    cutout(roots.adobe / "a" / "person.png")
    cutout(roots.adobe / "b" / "person.png")
    matched = benchmark.match_images(roots.originals, roots.adobe)
    assert not matched["matches"]
    assert any(row["kind"] == "ambiguous_match" for row in matched["issues"])


def test_duplicate_source_extensions_are_ambiguous(roots):
    photograph(roots.originals / "person.jpg")
    photograph(roots.originals / "person.webp")
    cutout(roots.adobe / "person.png")
    assert not benchmark.match_images(roots.originals, roots.adobe)["matches"]


def test_relative_and_basename_cannot_share_one_adobe(roots):
    photograph(roots.originals / "a" / "person.jpg")
    photograph(roots.originals / "b" / "person.jpg")
    cutout(roots.adobe / "a" / "person.png")
    matched = benchmark.match_images(roots.originals, roots.adobe)
    # The relative path is safe; ambiguous source basename fallback is rejected.
    assert [row["original"] for row in matched["matches"]] == ["a/person.jpg"]
    assert any(row["kind"] == "ambiguous_match" for row in matched["issues"])


def test_provenance_requires_evidence_and_hashes(roots, tmp_path):
    source = photograph(roots.originals / "person.jpg")
    adobe = cutout(roots.adobe / "person.png")
    evidence = tmp_path / "upload-log.txt"
    evidence.write_text("Submitted source and received Adobe result", encoding="utf-8")
    match = benchmark.match_images(roots.originals, roots.adobe)["matches"][0]
    record = {"original": "person.jpg", "adobe": "person.png", "source": "person.jpg",
              "source_sha256": benchmark.sha256(source), "adobe_sha256": benchmark.sha256(adobe),
              "submitted_to_adobe": True, "evidence": evidence.name, "evidence_sha256": benchmark.sha256(evidence)}
    index = benchmark.record_index([record])
    result = benchmark.source_details(match, roots.originals, roots.adobe, None, index, tmp_path)
    assert result["source_confidence"] == "verified-source"
    record["source_sha256"] = "0" * 64
    result = benchmark.source_details(match, roots.originals, roots.adobe, None, index, tmp_path)
    assert result["source_confidence"] == "source-unverified"
    assert any("Provenance verification failed" in warning for warning in result["warnings"])


def test_staging_basename_is_not_provenance(roots, tmp_path):
    photograph(roots.originals / "person.jpg")
    cutout(roots.adobe / "person.png")
    staging = tmp_path / "staging"
    staged = photograph(staging / "PERSON.webp")
    match = benchmark.match_images(roots.originals, roots.adobe)["matches"][0]
    result = benchmark.source_details(match, roots.originals, roots.adobe, staging, {}, tmp_path)
    assert result["source"] == str(staged.resolve())
    assert result["source_confidence"] == "source-unverified"


def test_staging_inventory_once_for_batch(roots, tmp_path, monkeypatch):
    staging = tmp_path / "staging"
    for index in range(3):
        photograph(roots.originals / f"p{index}.jpg")
        photograph(staging / f"p{index}.jpg")
        cutout(roots.adobe / f"p{index}.png")
    calls = []
    inventory = benchmark.inventory
    def counted(root):
        calls.append(root)
        return inventory(root)
    monkeypatch.setattr(benchmark, "inventory", counted)
    benchmark.run_benchmark(options(roots, staging=staging, prepare_only=True))
    assert calls.count(staging.resolve()) == 1


def test_deterministic_sample_default_100_verified_first_and_all():
    rows = [{"original": f"p{i}.jpg", "source_confidence": "verified-source" if i < 105 else "source-unverified"}
            for i in range(130)]
    selected = benchmark.select_sample(rows)
    assert len(selected) == 100
    assert selected == benchmark.select_sample(list(reversed(rows)))
    assert all(row["source_confidence"] == "verified-source" for row in selected)
    assert selected != benchmark.select_sample(rows, seed=43)
    assert len(benchmark.select_sample(rows, all_images=True)) == 130
    with pytest.raises(ValueError, match="positive"):
        benchmark.select_sample(rows, limit=0)


def test_categories_are_intentional_and_priority_included():
    rows = [{"original": f"p{i}.jpg", "source_confidence": "source-unverified"} for i in range(10)]
    categories = [{"original": "p1.jpg", "categories": ["wispy hair"], "priority": True},
                  {"original": "p2.jpg", "categories": ["glasses"]}]
    selected = benchmark.select_sample(rows, limit=2, categories=categories)
    assert {row["original"] for row in selected} == {"p1.jpg", "p2.jpg"}
    with pytest.raises(ValueError, match="no unambiguous match"):
        benchmark.select_sample(rows, categories=[{"original": "missing.jpg"}])
    with pytest.raises(ValueError, match="Duplicate"):
        benchmark.select_sample(rows, categories=[categories[0], categories[0]])


def test_alpha_metrics_iou_and_disagreement(tmp_path):
    alpha = Image.new("L", (2, 2))
    alpha.putdata([0, 128, 255, 0])
    source = cutout(tmp_path / "source.png", (2, 2), alpha=alpha)
    other = Image.new("L", (2, 2))
    other.putdata([0, 255, 255, 255])
    reference = cutout(tmp_path / "reference.png", (2, 2), alpha=other)
    result = benchmark.image_metrics(source, (2, 2), reference)
    assert result["valid"]
    assert result["metrics"]["foreground_coverage"] == 0.5
    assert result["metrics"]["soft_alpha_fraction"] == 0.25
    assert result["metrics"]["mask_iou_adobe"] == pytest.approx(2 / 3)
    assert result["metrics"]["alpha_disagreement_adobe"] == pytest.approx((127 + 255) / (4 * 255))


@pytest.mark.parametrize("kind", ["opaque", "empty", "uniform-soft", "near-empty", "rgb", "corrupt", "dimensions"])
def test_validation_failures_preserve_diagnostics(tmp_path, kind):
    path = tmp_path / "result.png"
    if kind == "corrupt":
        path.write_bytes(b"broken")
    elif kind == "rgb":
        photograph(path)
    elif kind == "near-empty":
        alpha = Image.new("L", (20, 20), 0)
        alpha.putpixel((10, 10), 255)
        cutout(path, (20, 20), alpha=alpha)
    elif kind in ("opaque", "empty", "uniform-soft"):
        cutout(path, alpha={"opaque": 255, "empty": 0, "uniform-soft": 128}[kind])
    else:
        cutout(path)
    result = benchmark.image_metrics(path, (10, 10) if kind == "dimensions" else None)
    assert not result["valid"]
    assert result["errors"]
    if kind == "uniform-soft":
        assert result["metrics"]["alpha_min"] == result["metrics"]["alpha_max"] == 128
        assert any("Uniform alpha" in error for error in result["errors"])


def test_dimension_mismatch_never_resizes_masks(tmp_path):
    path = cutout(tmp_path / "result.png")
    reference = cutout(tmp_path / "adobe.png", (12, 12))
    result = benchmark.image_metrics(path, (8, 8), reference)
    assert result["valid"]
    assert "mask_iou_adobe" not in result["metrics"]
    assert any("not resized" in warning for warning in result["warnings"])


def test_potential_halo_and_existing_edge_helper(tmp_path):
    alpha = Image.new("L", (8, 8), 128)
    alpha.putpixel((3, 3), 255)
    path = cutout(tmp_path / "result.png", color=(255, 255, 255), alpha=alpha)
    result = benchmark.image_metrics(path)
    assert result["metrics"]["potential_halo"]
    assert result["metrics"]["potential_clipping"]
    assert set(result["metrics"]["clipping_edges"]) == {"top", "left", "right"}


@pytest.mark.parametrize("target", ["inside-original", "ancestor", "same-adobe", "cache-original"])
def test_reject_overlapping_output_or_model_cache_before_writes(roots, target):
    output, home = roots.output, roots.home
    if target == "inside-original":
        output = roots.originals / "benchmark"
    elif target == "ancestor":
        output = roots.originals.parent
    elif target == "same-adobe":
        output = roots.adobe
    else:
        home = roots.originals / "weights"
    with pytest.raises(ValueError, match="overlaps"):
        benchmark.validate_roots(roots.originals, roots.adobe, output, home=home)
    assert not roots.output.exists()


def test_production_output_overlap_rejected(roots, monkeypatch):
    monkeypatch.setenv("SEL_DOWNLOAD_DIR", str(roots.output))
    with pytest.raises(ValueError, match="production"):
        benchmark.run_benchmark(options(roots, prepare_only=True))


def test_output_symlink_escape_rejected(roots, tmp_path):
    roots.output.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (roots.output / "adobe").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating Windows symlinks requires privileges")
    with pytest.raises(ValueError, match="link outside"):
        benchmark.validate_roots(roots.originals, roots.adobe, roots.output)


def test_prepare_report_self_contained_no_model_or_cloning(roots, no_clone):
    source = photograph(roots.originals / "person.jpg")
    adobe = cutout(roots.adobe / "person.png")
    hashes = benchmark.sha256(source), benchmark.sha256(adobe)
    payload = benchmark.run_benchmark(options(roots, prepare_only=True),
                                      remover_factory=lambda *_a: pytest.fail("No model initialization"))
    assert (benchmark.sha256(source), benchmark.sha256(adobe)) == hashes
    assert len(payload["images"]) == 1
    assert payload["images"][0]["source_confidence"] == "source-unverified"
    assert all(record["status"] == "not-run" for engine, record in payload["images"][0]["outputs"].items() if engine != "adobe")
    html = (roots.output / "reports" / "comparison.html").read_text(encoding="utf-8")
    assert "data:image/jpeg;base64," in html
    assert "data:image/png;base64," in html or "data:image/webp;base64," in html
    assert "localStorage" in html and "Export JSON" in html and "Export CSV" in html
    assert "<table>" not in html  # table is generated with textContent, never raw filename HTML
    assert "createElement('table')" in html
    assert 'id="aggregateDetails"' in html
    assert "model_identifier" in html and "Open full resolution" in html
    assert "__DATA__" not in html
    assert "__ASSETS__" not in html
    metadata, assets = parse_report(roots.output / "reports" / "comparison.html")
    assert "data:image/" not in json.dumps(metadata)
    original_asset = metadata["images"][0]["original_asset"]
    assert "asset" not in original_asset
    original_uri = assets[original_asset["asset_id"]]
    assert original_uri.startswith("data:image/jpeg;base64,")
    assert base64.b64decode(original_uri.split(",", 1)[1]) == source.read_bytes()
    adobe_uri = assets[metadata["images"][0]["outputs"]["adobe"]["asset_id"]]
    with Image.open(io.BytesIO(base64.b64decode(adobe_uri.split(",", 1)[1]))) as embedded, Image.open(adobe) as original:
        assert embedded.size == original.size
        assert embedded.convert("RGBA").tobytes() == original.convert("RGBA").tobytes()
    saved = json.loads((roots.output / "reports" / "benchmark.json").read_text())
    assert saved["failures"] == payload["failures"]
    assert payload["aggregates"]["source-unverified"]["actually_reviewed"] == 0


@pytest.mark.parametrize("extension,mime", [(".jpg", "image/jpeg"), (".png", "image/png"), (".webp", "image/webp")])
def test_data_uri_preserves_compressed_source_bytes(tmp_path, extension, mime):
    path = photograph(tmp_path / ("source" + extension), (120, 180))
    raw = path.read_bytes()
    uri = benchmark.data_uri(path)
    encoded = base64.b64decode(uri.split(",", 1)[1])
    assert path.read_bytes() == raw
    if extension != ".png":
        assert encoded == raw
        assert uri.startswith("data:" + mime + ";")
    else:
        with Image.open(io.BytesIO(encoded)) as embedded, Image.open(path) as original:
            assert embedded.size == original.size
            assert embedded.convert("RGBA").tobytes() == original.convert("RGBA").tobytes()
        assert len(encoded) <= len(raw)


def test_png_webp_preview_preserves_hidden_rgb_and_dimensions(tmp_path):
    if not features.check("webp"):
        pytest.skip("Pillow WebP support unavailable")
    path = tmp_path / "transparent.png"
    original = Image.new("RGBA", (96, 128), (130, 70, 15, 0))
    original.paste((20, 40, 90, 255), (24, 32, 72, 96))
    original.putpixel((0, 0), (1, 2, 3, 0))
    original.putpixel((1, 0), (140, 15, 90, 128))
    original.save(path)
    raw = path.read_bytes()
    uri = benchmark.data_uri(path)
    assert uri.startswith("data:image/webp;base64,")
    encoded = base64.b64decode(uri.split(",", 1)[1])
    assert len(encoded) < len(raw)
    with Image.open(io.BytesIO(encoded)) as embedded:
        rgba = embedded.convert("RGBA")
        assert rgba.size == original.size
        assert rgba.tobytes() == original.tobytes()
        assert rgba.getpixel((0, 0)) == (1, 2, 3, 0)
    assert path.read_bytes() == raw


def test_png_keeps_original_bytes_when_webp_is_larger(tmp_path, monkeypatch):
    path = cutout(tmp_path / "source.png")
    raw = path.read_bytes()
    save = Image.Image.save
    def larger_webp(image, target, format=None, **kwargs):
        if format == "WEBP":
            target.write(b"x" * (len(raw) + 1))
        else:
            save(image, target, format=format, **kwargs)
    monkeypatch.setattr(benchmark.features, "check", lambda _feature: True)
    monkeypatch.setattr(Image.Image, "save", larger_webp)
    uri = benchmark.data_uri(path)
    assert uri.startswith("data:image/png;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == raw


def test_png_keeps_original_if_encoder_changes_transparent_rgb(tmp_path, monkeypatch):
    path = cutout(tmp_path / "source.png", (96, 128))
    raw = path.read_bytes()
    save = Image.Image.save
    def loses_hidden_rgb(image, target, format=None, **kwargs):
        if format == "WEBP":
            altered = Image.new("RGBA", image.size, (0, 0, 0, 0))
            try:
                save(altered, target, format=format, **kwargs)
            finally:
                altered.close()
        else:
            save(image, target, format=format, **kwargs)
    monkeypatch.setattr(benchmark.features, "check", lambda _feature: True)
    monkeypatch.setattr(Image.Image, "save", loses_hidden_rgb)
    uri = benchmark.data_uri(path)
    assert uri.startswith("data:image/png;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == raw


def test_lossless_webp_preserves_icc_profile_and_exif_payload(tmp_path):
    if not features.check("webp"):
        pytest.skip("Pillow WebP support unavailable")
    cms = pytest.importorskip("PIL.ImageCms")
    profile = cms.ImageCmsProfile(cms.createProfile("sRGB")).tobytes()
    exif = Image.Exif()
    exif[0x010E] = "Preserved color-managed portrait"
    exif[0x0112] = 1
    path = tmp_path / "profile.png"
    source = Image.new("RGBA", (512, 512), (130, 70, 15, 0))
    source.paste((20, 40, 90, 255), (128, 128, 384, 384))
    source.save(path, icc_profile=profile, exif=exif, compress_level=0)
    with Image.open(path) as original:
        original_exif = original.info["exif"]
    uri = benchmark.data_uri(path)
    assert uri.startswith("data:image/webp;base64,")
    with Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1]))) as embedded:
        assert embedded.info["icc_profile"] == profile
        prefix = b"Exif\x00\x00"
        assert embedded.info["exif"].removeprefix(prefix) == original_exif.removeprefix(prefix)
        assert embedded.getexif()[0x010E] == "Preserved color-managed portrait"
        assert embedded.size == source.size
        assert embedded.convert("RGBA").tobytes() == source.tobytes()


def test_png_gamma_without_icc_profile_retains_original_color_metadata(tmp_path):
    from PIL.PngImagePlugin import PngInfo
    metadata = PngInfo()
    metadata.add(b"gAMA", struct.pack(">I", 70000))
    path = tmp_path / "gamma.png"
    Image.new("RGBA", (96, 128), (130, 70, 15, 128)).save(path, pnginfo=metadata)
    raw = path.read_bytes()
    with Image.open(path) as original:
        assert original.info["gamma"] == 0.7
    uri = benchmark.data_uri(path)
    assert uri.startswith("data:image/png;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == raw


def test_html_script_injection_is_escaped(roots):
    photograph(roots.originals / "person.jpg")
    cutout(roots.adobe / "person.png")
    payload = benchmark.run_benchmark(options(roots, prepare_only=True))
    payload["images"][0]["warnings"].append("</script><script>alert(1)</script>")
    report = roots.output / "reports" / "comparison.html"
    benchmark.write_html(report, payload, roots.output)
    html = report.read_text()
    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c/script>" in html


def test_model_at_a_time_one_session_batch_and_reference_hashes(roots, mocked):
    paths = []
    for index in range(3):
        paths.extend([photograph(roots.originals / f"p{index}.jpg"), cutout(roots.adobe / f"p{index}.png")])
    before = {p: benchmark.sha256(p) for p in paths}
    payload = benchmark.run_benchmark(options(roots), **mocked)
    assert MockRemover.events == [event for model in benchmark.MODELS for event in
                                 [("open", model), *[("process", model)] * 3, ("close", model)]]
    assert MockRemover.active == 0
    assert {p: benchmark.sha256(p) for p in paths} == before
    assert payload["failures"] == 0
    assert all(run["initialization_seconds"] is not None for run in payload["model_runs"].values())
    for row in payload["images"]:
        for model in benchmark.MODELS:
            assert row["outputs"][model]["valid"]
            assert row["outputs"][model]["metrics"]["mask_iou_adobe"] == 1
    assert payload["aggregates"]["source-unverified"]["engines"][benchmark.MODELS[0]]["average_runtime"] == 2.5


def test_inference_failures_continue_and_close(roots, mocked):
    for index in range(2):
        photograph(roots.originals / f"p{index}.jpg")
        cutout(roots.adobe / f"p{index}.png")
    MockRemover.fail_name = benchmark.MODELS[0]
    payload = benchmark.run_benchmark(options(roots), **mocked)
    assert payload["failures"] == 2
    assert MockRemover.active == 0
    assert all(row["outputs"][benchmark.MODELS[0]]["status"] == "failed" for row in payload["images"])
    assert all(row["outputs"][benchmark.MODELS[1]]["valid"] for row in payload["images"])


def test_initialization_failure_is_reported_no_silent_fallback(roots):
    photograph(roots.originals / "person.jpg")
    cutout(roots.adobe / "person.png")
    def unavailable(_settings):
        raise RuntimeError("Missing model weights")
    payload = benchmark.run_benchmark(options(roots, models=(benchmark.MODELS[0],)),
                                      remover_factory=unavailable, settings_factory=SimpleNamespace)
    assert payload["failures"] > 0
    assert payload["images"][0]["outputs"][benchmark.MODELS[0]]["status"] == "initialization-failed"
    assert "Missing model weights" in payload["model_runs"][benchmark.MODELS[0]]["errors"]


def test_report_only_preserves_validated_historical_timing_memory_and_review(roots, mocked):
    photograph(roots.originals / "person.jpg")
    cutout(roots.adobe / "person.png")
    initial = benchmark.run_benchmark(options(roots), **mocked)
    path = roots.output / "reports" / "benchmark.json"
    initial["reviews"] = {initial["images"][0]["id"]: {"result": "Equivalent", "notes": "Already reviewed"}}
    initial["model_runs"][benchmark.MODELS[0]]["peak_rss_bytes"] = 123456
    benchmark.atomic_json(path, initial)
    replayed = benchmark.run_benchmark(options(roots, report_only=True),
                                       remover_factory=lambda *_a: pytest.fail("Report must not initialize"))
    assert replayed["model_runs"][benchmark.MODELS[0]]["peak_rss_bytes"] == 123456
    assert replayed["aggregates"]["source-unverified"]["actually_reviewed"] == 1
    stats = replayed["aggregates"]["source-unverified"]["engines"][benchmark.MODELS[0]]
    assert stats["average_runtime"] == stats["median_runtime"] == 2.5
    assert replayed["images"][0]["outputs"][benchmark.MODELS[0]]["duration"] is None


def test_report_only_refuses_foreign_or_changed_model_output(roots, mocked):
    photograph(roots.originals / "person.jpg")
    cutout(roots.adobe / "person.png")
    initial = benchmark.run_benchmark(options(roots), **mocked)
    row = initial["images"][0]
    path = roots.output / row["outputs"][benchmark.MODELS[0]]["path"]
    cutout(path, color=(20, 40, 60))
    replayed = benchmark.run_benchmark(options(roots, report_only=True))
    record = replayed["images"][0]["outputs"][benchmark.MODELS[0]]
    assert not record["valid"]
    assert record["status"] == "unverified-existing"
    assert "historical_duration" not in record
    assert benchmark.MODELS[0] not in replayed["model_runs"]


def test_legacy_smoke_run_metadata_retained_only_with_validated_sidecars(roots, mocked):
    photograph(roots.originals / "person.jpg")
    cutout(roots.adobe / "person.png")
    initial = benchmark.run_benchmark(options(roots), **mocked)
    initial.pop("configuration")
    benchmark.atomic_json(roots.output / "reports" / "benchmark.json", initial)
    replayed = benchmark.run_benchmark(options(roots, report_only=True))
    assert replayed["model_runs"] == initial["model_runs"]
    assert replayed["aggregates"]["source-unverified"]["engines"][benchmark.MODELS[0]]["average_runtime"] == 2.5


def test_missing_submitted_source_falls_back_unverified(roots, tmp_path):
    source = photograph(roots.originals / "person.jpg")
    cutout(roots.adobe / "person.png")
    staging = tmp_path / "staging"
    staging.mkdir()
    match = benchmark.match_images(roots.originals, roots.adobe)["matches"][0]
    record = {"original": "person.jpg", "source": "missing.jpg", "adobe": "person.png", "evidence": "absent.txt"}
    result = benchmark.source_details(match, roots.originals, roots.adobe, staging,
                                      benchmark.record_index([record]), tmp_path)
    assert result["source"] == str(source.resolve())
    assert result["source_confidence"] == "source-unverified"


def test_sample_manifest_replay_checks_hashes_and_allows_same_report_root(roots):
    for index in range(5):
        photograph(roots.originals / f"p{index}.jpg")
        cutout(roots.adobe / f"p{index}.png")
    initial = benchmark.run_benchmark(options(roots, prepare_only=True, limit=3))
    manifest = roots.output / "reports" / "sample-manifest.json"
    replayed = benchmark.run_benchmark(options(roots, prepare_only=True, sample_manifest=manifest, limit=3))
    assert [row["id"] for row in initial["images"]] == [row["id"] for row in replayed["images"]]
    photograph(roots.originals / initial["images"][0]["original"], (10, 10))
    with pytest.raises(ValueError, match="hash mismatch"):
        benchmark.run_benchmark(options(roots, prepare_only=True, sample_manifest=manifest, limit=3))


def test_replay_can_add_intentional_categories_without_changing_sources(roots, tmp_path):
    for index in range(3):
        photograph(roots.originals / f"p{index}.jpg")
        cutout(roots.adobe / f"p{index}.png")
    initial = benchmark.run_benchmark(options(roots, prepare_only=True))
    assert not initial["manifest"]["categories_supplied"]
    manifest = roots.output / "reports" / "sample-manifest.json"
    category_file = tmp_path / "categories.json"
    category_file.write_text(json.dumps({"images": [{"original": "p1.jpg", "categories": ["glasses"], "priority": True}]}))
    replayed = benchmark.run_benchmark(options(roots, prepare_only=True, sample_manifest=manifest,
                                              categories=category_file))
    assert {row["id"] for row in initial["images"]} == {row["id"] for row in replayed["images"]}
    assert next(row for row in replayed["images"] if row["original"] == "p1.jpg")["categories"] == ["glasses"]
    assert replayed["manifest"]["categories_supplied"]


def test_review_aggregation_separates_confidence_and_unreviewed():
    rows = [{"id": "a", "source_confidence": "verified-source", "categories": ["glasses"],
             "outputs": {"adobe": {"path": "adobe/a.png", "status": "baseline", "valid": True}}},
            {"id": "b", "source_confidence": "verified-source", "categories": [], "outputs": {}},
            {"id": "c", "source_confidence": "source-unverified", "categories": [],
             "outputs": {benchmark.MODELS[0]: {"path": "portrait/c.png", "status": "processed", "valid": True,
                                                "metrics": {"mask_iou_adobe": 0.0}}}},
            {"id": "d", "source_confidence": "verified-source", "categories": [], "outputs": {}}]
    reviews = {"a": {"result": "Adobe better"}, "c": {"result": "BiRefNet Portrait better"},
               "d": {"result": "Needs review"}}
    result = benchmark.aggregate_results(rows, reviews)
    verified = result["verified-source"]
    assert verified["actually_reviewed"] == 2 and verified["decisive_reviews"] == 1
    assert verified["engines"]["adobe"]["win_percentage"] == 100
    assert verified["category_wins"] == {"glasses": {"adobe": 1}}
    assert result["source-unverified"]["engines"][benchmark.MODELS[0]]["wins"] == 1
    unreviewed = benchmark.aggregate_results(rows)
    assert unreviewed["verified-source"]["engines"]["adobe"]["win_percentage"] is None


@pytest.mark.parametrize("output", [None, {"status": "not-run"},
                                    {"path": "portrait/a.png", "status": "not-run"},
                                    {"path": "portrait/a.png", "status": "unverified-existing"},
                                    {"path": "portrait/a.png", "status": "failed"},
                                    {"path": "portrait/a.png", "status": "initialization-failed"},
                                    {"status": "processed"}, {"path": "", "status": "processed"}])
def test_unavailable_model_cannot_gain_human_win(output):
    row = {"id": "a", "original": "a.jpg", "source_confidence": "verified-source", "categories": ["glasses"],
           "outputs": {benchmark.MODELS[0]: output} if output is not None else {}}
    reviews = {"a": {"result": "BiRefNet Portrait better", "notes": "Imported stale review"}}
    result = benchmark.aggregate_results([row], reviews)["verified-source"]
    assert result["actually_reviewed"] == result["decisive_reviews"] == 0
    assert result["ignored_reviews"] == 1
    assert result["engines"][benchmark.MODELS[0]]["wins"] == 0
    assert result["engines"][benchmark.MODELS[0]]["win_percentage"] is None
    assert result["category_wins"] == {}
    with pytest.raises(ValueError, match="Choose an available output"):
        benchmark.validate_reviews([row], reviews)


@pytest.mark.parametrize("status", ["baseline", "processed", "skipped", "existing"])
def test_available_output_can_win_regardless_of_adobe_iou(status):
    row = {"id": "a", "original": "a.jpg", "source_confidence": "source-unverified", "categories": [],
           "outputs": {benchmark.MODELS[0]: {"path": "portrait/a.png", "status": status,
                                             "valid": True, "metrics": {"mask_iou_adobe": 0.0}}}}
    reviews = {"a": {"result": "BiRefNet Portrait better", "notes": "Different mask but better fine hair"}}
    benchmark.validate_reviews([row], reviews)
    stats = benchmark.aggregate_results([row], reviews)["source-unverified"]
    assert stats["actually_reviewed"] == stats["decisive_reviews"] == 1
    assert stats["engines"][benchmark.MODELS[0]]["wins"] == 1


@pytest.mark.parametrize("choice", ["Needs review", "Equivalent", "All unacceptable"])
def test_nonwinner_review_choices_remain_available_without_model_outputs(choice):
    row = {"id": "a", "original": "a.jpg", "source_confidence": "source-unverified", "categories": [], "outputs": {}}
    reviews = {"a": {"result": choice}}
    benchmark.validate_reviews([row], reviews)
    stats = benchmark.aggregate_results([row], reviews)["source-unverified"]
    assert stats["actually_reviewed"] == 1
    assert all(record["wins"] == 0 for record in stats["engines"].values())


@pytest.mark.parametrize("extension", [".json", ".csv"])
def test_prepare_only_rejects_impossible_winner_review_import(roots, tmp_path, extension):
    photograph(roots.originals / "person.jpg")
    cutout(roots.adobe / "person.png")
    initial = benchmark.run_benchmark(options(roots, prepare_only=True))
    row = {"id": initial["images"][0]["id"], "result": "BiRefNet Portrait better", "notes": "Not run"}
    path = tmp_path / ("reviews" + extension)
    if extension == ".json":
        path.write_text(json.dumps({"reviews": [row]}), encoding="utf-8")
    else:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
    with pytest.raises(ValueError, match="status=not-run.*Choose an available output"):
        benchmark.run_benchmark(options(roots, prepare_only=True, reviews=path),
                                remover_factory=lambda *_a: pytest.fail("Prepare-only must not infer"))


def test_reviews_json_csv_roundtrip_multiline_notes(tmp_path):
    row = {"id": "abc", "result": "Equivalent", "notes": 'Comma, quote " and\nnew line'}
    path = tmp_path / "reviews.json"
    path.write_text(json.dumps({"reviews": [row]}), encoding="utf-8")
    assert benchmark.load_reviews(path)["abc"]["notes"] == row["notes"]
    path = tmp_path / "reviews.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    assert benchmark.load_reviews(path)["abc"] == {k: row[k] for k in ("result", "notes")}
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps([row, row]))
    with pytest.raises(ValueError, match="Duplicate"):
        benchmark.load_reviews(path)


def test_empty_inventory_and_cli_limit_no_implicit_clone(roots, no_clone):
    payload = benchmark.run_benchmark(options(roots, prepare_only=True))
    assert payload["images"] == [] and payload["model_runs"] == {}
    code = benchmark.main(["--originals", str(roots.originals), "--adobe", str(roots.adobe),
                           "--output", str(roots.output), "--home", str(roots.home), "--limit", "0", "--prepare-only"])
    assert code == 2


def test_corrupt_source_is_reported_without_modifying_reference(roots, mocked):
    source = roots.originals / "person.jpg"
    source.write_bytes(b"invalid source")
    cutout(roots.adobe / "person.png")
    payload = benchmark.run_benchmark(options(roots), **mocked)
    assert source.read_bytes() == b"invalid source"
    assert payload["images"][0]["original_asset"]["errors"]
    assert payload["failures"] == 3
    assert MockRemover.active == 0


def test_optional_background_embedded_and_face_weights_not_downloaded(roots, tmp_path, monkeypatch):
    photograph(roots.originals / "person.jpg")
    cutout(roots.adobe / "person.png")
    background = photograph(tmp_path / "kometa.jpg")
    face = SimpleNamespace(_model_path=lambda: tmp_path / "absent.onnx",
                           detect_face_crop_issues=lambda *_a: pytest.fail("No missing detector invocation"))
    helper = benchmark.helper_module
    monkeypatch.setattr(benchmark, "helper_module", lambda name: face if name == "face_crop" else helper(name))
    payload = benchmark.run_benchmark(options(roots, prepare_only=True, face_checks=True, kometa_background=background))
    assert any("no download attempted" in w for w in payload["images"][0]["outputs"]["adobe"]["warnings"])
    html = (roots.output / "reports" / "comparison.html").read_text()
    metadata, assets = parse_report(roots.output / "reports" / "comparison.html")
    assert "data:image/" not in json.dumps(metadata)
    uri = assets[metadata["kometa_background_asset_id"]]
    assert uri.startswith("data:image/jpeg;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == background.read_bytes()


def test_stdout_summary_reports_confidence_review_counts_and_memory(roots, mocked, capsys):
    photograph(roots.originals / "person.jpg")
    cutout(roots.adobe / "person.png")
    payload = benchmark.run_benchmark(options(roots), **mocked)
    benchmark.print_summary(payload)
    output = capsys.readouterr().out
    assert "verified-source | 0 | 0" in output
    assert "source-unverified | 1 | 0 | birefnet-portrait | 0 | 0.00 | 2.50 / 2.50" in output
    assert "Peak RSS MiB" in output
