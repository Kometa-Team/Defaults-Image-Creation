import base64
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import create_people_poster as poster


@pytest.fixture
def config(tmp_path, monkeypatch):
    for key in ("POSTER_FONT_DIR", "POSTER_ASSET_DIR"):
        monkeypatch.delenv(key, raising=False)
    root = tmp_path / "workspace \u00e9"
    (root / "people_dirs/Downloads").mkdir(parents=True)
    (root / "people_dirs/original").mkdir()
    return root


def stage(config, name="Person", size=(120, 180), grayscale=False):
    image = Image.new("RGBA", size)
    draw = ImageDraw.Draw(image)
    color = (90, 90, 90, 255) if grayscale else (170, 60, 95, 255)
    draw.ellipse((size[0]//4, size[1]//6, size[0]*3//4, size[1]//2), fill=color)
    draw.rectangle((size[0]//4, size[1]//3, size[0]*3//4, size[1]-1), fill=color)
    source = config / "people_dirs/Downloads" / (name + ".png")
    image.save(source)
    original = config / "people_dirs/original" / (name + ".jpg")
    image.convert("RGB").save(original, quality=95)
    return source, original


def test_artwork_exactly_matches_embedded_reference():
    script = (poster.SCRIPT_DIR / "create_people_poster.ps1").read_text(encoding="utf-8-sig")
    for number, name in zip((1, 2, 3, 8), poster.ARTWORK):
        match = re.search(r'^\$file' + str(number) + r' = "([A-Za-z0-9+/=]+)"', script, re.M)
        assert (poster.SCRIPT_DIR / "assets/people" / name).read_bytes() == base64.b64decode(match[1])


def test_all_styles_validate_and_never_launch_external_tools(config, monkeypatch):
    source, original = stage(config)
    native = original.read_bytes()
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: pytest.fail("External process in Python rendering"))
    report = poster.render_batch(config)
    assert report["processed"] == 1 and report["failed"] == 0
    from sync_people_images import image_quality_findings
    for style in poster.STYLES:
        target = poster.output_path(config / "people_dirs", style, "Person")
        with Image.open(target) as image:
            image.load()
            assert image.size == ((120, 180) if style == "original" else poster.SIZE)
            assert image.format == ("PNG" if style == "transparent" else "JPEG")
            if style == "transparent":
                assert image.mode == "RGBA" and image.getchannel("A").getextrema() == (0, 255)
            elif style == "bw":
                assert image.mode == "L"
        failures, _ = image_quality_findings(style, target, allow_native_original=style == "original", allow_fixable_dimensions=style == "original")
        assert not failures
    assert poster.output_path(config / "people_dirs", "original", "Person").read_bytes() == native
    assert not source.exists()
    assert not list((config / "people_dirs/tmppeople").iterdir())


def test_multiple_unicode_and_grayscale_inputs(config):
    stage(config, "Zo\u00eb Garc\u00eda")
    stage(config, "Gray Person", grayscale=True)
    report = poster.render_batch(config)
    assert report["processed"] == 2 and report["failed"] == 0
    assert poster.output_path(config / "people_dirs", "bw", "Zo\u00eb Garc\u00eda").is_file()
    assert any("grayscale" in warning for row in report["images"] for warning in row.get("warnings", []))


def test_repeat_run_is_byte_and_mtime_stable(config):
    stage(config)
    assert poster.render_batch(config)["processed"] == 1
    paths = [poster.output_path(config / "people_dirs", style, "Person") for style in poster.STYLES]
    before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]
    report = poster.render_batch(config)
    assert report["skipped"] == 1 and report["processed"] == report["failed"] == 0
    assert before == [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]


def test_partial_failure_retains_bad_input_for_retry(config):
    stage(config, "Good Person")
    bad, _ = stage(config, "Bad Person")
    bad.write_bytes(b"not an image")
    report = poster.render_batch(config)
    assert report["processed"] == report["failed"] == 1
    assert bad.is_file()
    stage(config, "Bad Person")
    assert poster.render_batch(config)["failed"] == 0


def test_output_failure_retains_sources_and_cleans_temp(config, monkeypatch):
    source, original = stage(config)
    save = Image.Image.save
    def fail(image, target, *args, **kwargs):
        if Path(target).name == "signature.jpg":
            raise OSError("disk full")
        return save(image, target, *args, **kwargs)
    monkeypatch.setattr(Image.Image, "save", fail)
    report = poster.render_batch(config)
    assert report["failed"] == 1 and source.exists() and original.exists()
    assert not list((config / "people_dirs/tmppeople").iterdir())
    assert not poster.output_path(config / "people_dirs", "bw", "Person").exists()


def test_missing_original_and_missing_inputs_fail_clearly(config):
    with pytest.raises(ValueError, match="No staged"):
        poster.render_batch(config)
    source, original = stage(config)
    original.unlink()
    report = poster.render_batch(config)
    assert report["failed"] == 1 and source.exists()
    assert "Missing preserved original" in report["images"][0]["error"]


@pytest.mark.parametrize("kind", ["opaque", "empty"])
def test_invalid_alpha_blocks_success(config, kind):
    source, _ = stage(config)
    Image.new("RGBA", (120, 180), (30, 60, 90, 255 if kind == "opaque" else 0)).save(source)
    report = poster.render_batch(config)
    assert report["failed"] == 1 and source.exists()


@pytest.mark.parametrize("size", [(200, 100), (100, 250), (2000, 3004)])
def test_normalize_preserves_canvas_and_alpha(size):
    source = Image.new("RGBA", size)
    ImageDraw.Draw(source).ellipse((size[0]//4, size[1]//4, size[0]*3//4, size[1]*3//4), fill=(40, 70, 90, 200))
    normalized = poster.normalize_cutout(source)
    assert normalized.size == poster.SIZE and normalized.mode == "RGBA"
    assert normalized.getchannel("A").getbbox()


def test_shift_and_label_filename_rules():
    image = Image.new("RGBA", poster.SIZE)
    ImageDraw.Draw(image).rectangle((100, 80, 300, 1200), fill="red")
    shifted = poster.shifted_cutout(image)
    assert shifted.getchannel("A").getbbox() == (100, 500, 301, 1621)
    assert poster.label_name("Akshay Kumar1") == "Akshay Kumar"
    assert poster.label_name("Akshay Kumar (2)") == "Akshay Kumar"


def test_font_missing_is_actionable(config, monkeypatch):
    monkeypatch.setenv("POSTER_FONT_DIR", str(config / "absent-fonts"))
    with pytest.raises(ValueError, match="Required poster resource missing"):
        poster.Renderer()


def test_bundled_metrics_match_reference_and_preserve_fonts():
    before = {name: poster.digest(poster.SCRIPT_DIR / "fonts" / name) for name in poster.FONTS}
    renderer = poster.Renderer()
    assert renderer.width("LERTRATKOSUM", poster.FONTS[0], 183) == pytest.approx(1561, abs=1)
    bounds = renderer.label("Naravit Lertratkosum", poster.FONTS[1], (1900,600), vertical="south").getbbox()
    assert bounds == pytest.approx((28,346,1872,600), abs=2)
    assert "o_o.ss01" in renderer.metrics[poster.FONTS[1]].glyphs("Chae Soo-bin")
    assert before == {name: poster.digest(poster.SCRIPT_DIR / "fonts" / name) for name in poster.FONTS}


def test_jost_is_bundled_static_weight_260_with_license_and_no_legacy_font():
    font = poster.SCRIPT_DIR / "fonts" / poster.FONTS[2]
    assert font.name == "Jost-260.ttf" and poster.DIIIVOY_POINT_SIZE == 190
    with TTFont(font) as table:
        assert "fvar" not in table and table["OS/2"].usWeightClass == 260
        assert "Open Font License" in table["name"].getDebugName(13)
    assert "SIL OPEN FONT LICENSE Version 1.1" in (font.parent / "OFL-Jost.txt").read_text(encoding="utf-8")
    assert not (font.parent / "FuturaTEELig.ttf").exists()
    script = (poster.SCRIPT_DIR / "create_people_poster.ps1").read_text(encoding="utf-8-sig")
    assert "futura" not in script.lower() and "$file7" not in script
    assert "'Jost-260.ttf'" in script and "$diiivoyPointSize = 190" in script
    assert script.count("Get-Width $postertitle $fontJost $diiivoyPointSize") == 2
    assert script.count("-font $fontJost -pointsize $diiivoyPointSize") == 2
    assert script.count("-font $fontJost -fill white -size 1900x580") == 2


@pytest.mark.parametrize("name,automatic", [("Chae Soo-bin", False), ("Andrew Fung Chih-Chiang", True)])
def test_both_diiivoy_styles_use_approved_jost_settings(name, automatic):
    renderer = poster.Renderer()
    bounds = renderer.font(poster.FONTS[2], poster.DIIIVOY_POINT_SIZE).getbbox("H")
    assert bounds[3] - bounds[1] == 133
    original_label = renderer.label
    calls = []
    def record(text, font_name, box, pointsize=None, **kwargs):
        result = original_label(text, font_name, box, pointsize, **kwargs)
        if font_name == poster.FONTS[2]:
            calls.append((text, pointsize, result.getbbox()))
        return result
    renderer.label = record
    image = Image.new("RGBA", (120, 180))
    ImageDraw.Draw(image).ellipse((30, 10, 90, 179), fill=(170, 60, 95, 255))
    outputs, _ = renderer.render(image, name)
    assert len(calls) == 2
    assert all(text == name.upper() and size == (None if automatic else 190) for text, size, _ in calls)
    assert all(0 < box[0] < box[2] < 1900 and 0 < box[1] < box[3] < 580 for _, _, box in calls)
    assert outputs["diiivoy"].size == outputs["diiivoycolor"].size == poster.SIZE


def test_unsupported_font_glyph_is_reported():
    with pytest.raises(ValueError, match="no glyph"):
        poster.Renderer().width("Person \U0001f600", poster.FONTS[0], 183)


def test_high_margin_cutout_preserves_reference_gray_intermediate_quirk():
    image = Image.new("RGBA", (200,100))
    ImageDraw.Draw(image).rectangle((50,20,150,99), fill=(180,60,95,255))
    outputs, _ = poster.Renderer().render(image, "Wide Portrait")
    for style in ("diiivoy", "diiivoycolor", "rainier"):
        r,g,b = outputs[style].getpixel((1000,1500))
        assert r == g == b
    r,g,b = outputs["signature"].getpixel((1000,1500))
    assert r != g


def test_native_archives_prepare_for_github_api(config):
    stage(config)
    poster.render_batch(config)
    from publish_people_github import prepare
    from people_publication_state import PublicationState
    state = PublicationState(config / "state")
    try:
        rows = prepare(config, "20261015T000000-123456abcdef", state, "master")
        assert len(rows) == 7
        for row in rows:
            with Image.open(row["prepared"]) as image:
                assert image.size == poster.SIZE
    finally:
        state.close()


@pytest.mark.parametrize("format,suffix", [("PNG",".png"),("WEBP",".webp")])
def test_native_original_formats_remain_unmodified(config, format, suffix):
    _, original = stage(config)
    target = original.with_suffix(suffix)
    with Image.open(original) as image:
        image.save(target, format)
    original.unlink()
    before = target.read_bytes()
    report = poster.render_batch(config)
    assert report["failed"] == 0
    assert poster.output_path(config / "people_dirs", "original", "Person", suffix).read_bytes() == before
