"""Regression contracts for the four Python COLLECTION labels."""

import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fontTools.ttLib import TTFont
from PIL import Image, ImageChops, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import create_people_poster as poster
import compare_collection as comparison


EXPECTED = {
    "signature": {"font": "Montserrat-SemiBold.ttf", "size": 92, "tracking": 12.5, "stroke": 0, "x": 643, "y": 2791},
    "rainier": {"font": "Montserrat-Light.ttf", "size": 110, "tracking": 18.0, "stroke": 0, "x": 201, "y": 809},
    "diiivoy": {"font": "Montserrat-SemiBold.ttf", "size": 100, "tracking": 83.0, "stroke": 1, "x": 309, "y": 2857},
    "diiivoycolor": {"font": "Montserrat-SemiBold.ttf", "size": 100, "tracking": 83.0, "stroke": 1, "x": 309, "y": 2857},
}
OLD_BOUNDS = {"signature": (645, 2789, 1358, 2860), "rainier": (201, 807, 1070, 890),
              "diiivoy": (305, 2853, 1723, 2935), "diiivoycolor": (305, 2853, 1723, 2935)}


@pytest.fixture(scope="module")
def renderer():
    with patch.dict("os.environ"):
        import os
        os.environ.pop("POSTER_FONT_DIR", None)
        os.environ.pop("POSTER_ASSET_DIR", None)
        yield poster.Renderer()


@pytest.fixture
def cutout():
    image = Image.new("RGBA", (120, 180))
    ImageDraw.Draw(image).ellipse((30, 10, 90, 179), fill=(170, 60, 95, 255))
    return image


def test_exact_production_configuration_and_font_inventory():
    assert poster.COLLECTION_CONFIG == EXPECTED
    assert poster.FONTS == ("Comfortaa-Medium.ttf", "Fuggles-Regular.ttf", "Jost-260.ttf",
                            "Montserrat-SemiBold.ttf", "Montserrat-Light.ttf")
    assert {p.name for p in (poster.SCRIPT_DIR / "fonts").glob("*.ttf")} == set(poster.FONTS)
    assert poster.digest(poster.SCRIPT_DIR / "fonts/Jost-260.ttf") == "564a838df86d075f9ab39e0d1f4cfe4ef90791388988dc8b5fc732f75d1ef8f5"


@pytest.mark.parametrize("name,weight,notice", [
    ("Comfortaa-Medium.ttf", 500, "Comfortaa"), ("Fuggles-Regular.ttf", 400, "Fuggles"),
    ("Jost-260.ttf", 260, "Jost"), ("Montserrat-SemiBold.ttf", 600, "Montserrat"),
    ("Montserrat-Light.ttf", 300, "Montserrat"),
])
def test_fonts_are_valid_bundled_and_licensed(name, weight, notice, renderer):
    with TTFont(poster.SCRIPT_DIR / "fonts" / name) as font:
        assert font["OS/2"].usWeightClass == weight
        assert "Open Font License" in font["name"].getDebugName(13)
        assert all(ord(c) in font.getBestCmap() for c in "COLLECTION")
    assert "SIL OPEN FONT LICENSE Version 1.1" in (poster.SCRIPT_DIR / "fonts" / f"OFL-{notice}.txt").read_text()
    assert renderer.font(name, 100).getmask("COLLECTION").getbbox()


@pytest.mark.parametrize("style", EXPECTED)
def test_textless_artwork_preserves_every_pixel_outside_old_lettering(style, renderer):
    expected_name = {"signature": "@zbase-Signature-no-text.png", "rainier": "@zbase-People-Clear2-no-text.png",
                     "diiivoy": "@zbase-People-Clear3-no-text.png", "diiivoycolor": "@zbase-People-Clear3-no-text.png"}[style]
    assert poster.COLLECTION_ARTWORK[style] == expected_name
    old = renderer.art[comparison.ORIGINAL_ARTWORK[style]]
    new = renderer.art[expected_name]
    assert old.size == new.size == poster.SIZE
    assert new.mode == "RGBA" and new.getchannel("A").getextrema() == (0, 255)
    channels = ImageChops.difference(old, new).split()
    delta = channels[0]
    for channel in channels[1:]:
        delta = ImageChops.lighter(delta, channel)
    assert delta.getbbox() == OLD_BOUNDS[style]


@pytest.mark.parametrize("style", EXPECTED)
def test_visible_bounds_antialiasing_no_clipping_and_determinism(style, renderer):
    first, second = Image.new("RGBA", poster.SIZE), Image.new("RGBA", poster.SIZE)
    bounds = renderer.render_collection(first, style)
    assert renderer.render_collection(second, style) == bounds
    assert first.tobytes() == second.tobytes()
    assert first.getchannel("A").getbbox() == bounds
    assert bounds[:2] == (EXPECTED[style]["x"], EXPECTED[style]["y"])
    assert 0 < bounds[0] < bounds[2] < poster.SIZE[0]
    assert 0 < bounds[1] < bounds[3] < poster.SIZE[1]
    alpha = first.getchannel("A")
    assert any(0 < value < 255 for _, value in alpha.getcolors())
    # A larger surface must produce the identical mask, proving canvas edges
    # did not silently remove any stroke or antialiased pixels.
    large = Image.new("RGBA", (2400, 3400))
    assert renderer.render_collection(large, style) == bounds
    assert large.crop((0, 0, *poster.SIZE)).tobytes() == first.tobytes()
    colors = first.convert("RGB").getcolors()
    assert all(value in {(0, 0, 0), (255, 255, 255)} for _, value in colors)


def test_fractional_tracking_is_retained_until_rasterization(renderer, monkeypatch):
    calls = []
    original = ImageDraw.ImageDraw.text
    def record(draw, xy, text, *args, **kwargs):
        calls.append((xy, text))
        return original(draw, xy, text, *args, **kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw, "text", record)
    renderer.render_collection(Image.new("RGBA", poster.SIZE), "signature")
    assert "".join(text for _, text in calls) == "COLLECTION"
    font = renderer.font("Montserrat-SemiBold.ttf", 92)
    for index in range(1, len(calls)):
        assert calls[index][0][0] - calls[index-1][0][0] == font.getlength(calls[index-1][1]) + 12.5
    assert any(xy[0] % 1 == .5 for xy, _ in calls)


def test_artificial_stroke_expands_ink_and_preserves_center(renderer, monkeypatch):
    stroked = Image.new("RGBA", poster.SIZE)
    stroked_bounds = renderer.render_collection(stroked, "diiivoy")
    plain_config = dict(EXPECTED["diiivoy"], stroke=0)
    monkeypatch.setitem(poster.COLLECTION_CONFIG, "diiivoy", plain_config)
    plain = Image.new("RGBA", poster.SIZE)
    plain_bounds = renderer.render_collection(plain, "diiivoy")
    assert stroked_bounds[2] - plain_bounds[2] == 2
    assert stroked_bounds[3] - plain_bounds[3] == 2
    assert sum(stroked.getchannel("A").histogram()[1:]) > sum(plain.getchannel("A").histogram()[1:])
    # Trimming keeps each label's outer top-left at the calibrated position;
    # interior glyphs expand on all sides, rather than shifting the stroke.
    stroked_alpha = stroked.getchannel("A").crop(stroked_bounds)
    plain_alpha = plain.getchannel("A").crop(plain_bounds)
    inset = stroked_alpha.crop((1, 1, stroked_alpha.width-1, stroked_alpha.height-1))
    assert not ImageChops.subtract(plain_alpha, inset).getbbox()


def test_out_of_bounds_fails_without_modifying_poster(renderer):
    image = Image.new("RGBA", (700, 2800))
    with pytest.raises(ValueError, match="exceeds poster bounds"):
        renderer.render_collection(image, "signature")
    assert image.getbbox() is None


def test_all_styles_use_textless_art_once_and_keep_name_layout(renderer, cutout, monkeypatch):
    collections, names, selected = [], [], []
    render_collection, label = renderer.render_collection, renderer.label
    class Artwork(dict):
        def __getitem__(self, key):
            selected.append(key)
            return super().__getitem__(key)
    monkeypatch.setattr(renderer, "art", Artwork(renderer.art))
    def record_collection(image, style):
        collections.append(style)
        return render_collection(image, style)
    def record_name(*args, **kwargs):
        names.append((args, kwargs))
        return label(*args, **kwargs)
    monkeypatch.setattr(renderer, "render_collection", record_collection)
    monkeypatch.setattr(renderer, "label", record_name)
    outputs, _ = renderer.render(cutout, "Chae Soo-bin")
    assert sorted(collections) == sorted(EXPECTED)
    assert set(selected) == {poster.ARTWORK[0], *poster.COLLECTION_ARTWORK.values()}
    assert names == [
        (("CHAE SOO-BIN", "Comfortaa-Medium.ttf", (1900, 500), 183), {}),
        (("Chae Soo-bin", "Fuggles-Regular.ttf", (1900, 600)), {"vertical": "south"}),
        (("CHAE SOO-BIN", "Jost-260.ttf", (1900, 580), 190), {}),
        (("CHAE SOO-BIN", "Jost-260.ttf", (1900, 580), 190), {}),
        (("CHAE\nSOO-BIN", "Comfortaa-Medium.ttf", (1600, 580), 183), {"align": "west"}),
    ]
    # The person remains grayscale/color in the same respective styles.
    r, g, b = outputs["diiivoy"].getpixel((1000, 1500))
    assert r == g == b
    r, g, b = outputs["diiivoycolor"].getpixel((1000, 1500))
    assert r != g and g != b


def test_selective_diiivoy_has_one_label_and_matches_full_render(renderer, cutout, monkeypatch):
    full, _ = renderer.render(cutout, "Zo\u00eb Garc\u00eda")
    calls = []
    original = renderer.render_collection
    def record(image, style):
        calls.append(style)
        return original(image, style)
    monkeypatch.setattr(renderer, "render_collection", record)
    for style in ("diiivoy", "diiivoycolor"):
        selective, _ = renderer.render_styles(cutout, "Zo\u00eb Garc\u00eda", (style,))
        assert selective[style].tobytes() == full[style].tobytes()
    assert calls == ["diiivoy", "diiivoycolor"]


def test_only_collection_regions_change_and_unrelated_styles_are_identical(renderer, cutout, monkeypatch):
    replacements, _ = renderer.render(cutout, "Zo\u00eb Garc\u00eda")
    layers = {}
    for style in EXPECTED:
        layer = Image.new("RGBA", poster.SIZE)
        layers[style] = renderer.render_collection(layer, style)
    for style, filename in poster.COLLECTION_ARTWORK.items():
        monkeypatch.setitem(renderer.art, filename, renderer.art[comparison.ORIGINAL_ARTWORK[style]])
    monkeypatch.setattr(renderer, "render_collection", lambda *args: None)
    references, _ = renderer.render(cutout, "Zo\u00eb Garc\u00eda")
    for style in ("bw", "transparent"):
        assert replacements[style].tobytes() == references[style].tobytes()
    for style in EXPECTED:
        delta = ImageChops.difference(references[style], replacements[style])
        assert delta.getbbox()
        bounds = comparison.union_bounds(OLD_BOUNDS[style], layers[style])
        ImageDraw.Draw(delta).rectangle((bounds[0], bounds[1], bounds[2]-1, bounds[3]-1), fill=0)
        assert delta.getbbox() is None


def test_fingerprint_covers_every_artwork_and_font(monkeypatch, tmp_path):
    fingerprint = poster.renderer_fingerprint()
    for name in (*poster.ARTWORK, *poster.FONTS):
        path = poster.SCRIPT_DIR / ("fonts" if name in poster.FONTS else "assets/people") / name
        assert fingerprint["files"][str(path.resolve())] == poster.digest(path)
    monkeypatch.setenv("POSTER_FONT_DIR", str(tmp_path))
    missing = poster.renderer_fingerprint()
    assert all(missing["files"][str((tmp_path / name).resolve())] == "missing" for name in poster.FONTS)


@pytest.mark.parametrize("missing", (*poster.COLLECTION_ARTWORK.values(), *poster.FONTS))
def test_missing_resource_fails_without_substitution(missing, monkeypatch):
    is_file = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda path: False if path.name == missing else is_file(path))
    with pytest.raises(ValueError, match="Required poster resource missing") as error:
        poster.Renderer()
    assert missing in str(error.value)


def test_invalid_new_font_fails_before_rendering(tmp_path, monkeypatch):
    for name in poster.FONTS:
        shutil.copyfile(poster.SCRIPT_DIR / "fonts" / name, tmp_path / name)
    (tmp_path / "Montserrat-Light.ttf").write_bytes(b"invalid font")
    monkeypatch.setenv("POSTER_FONT_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="Unreadable required font"):
        poster.Renderer()


def test_metrics_and_comparison_preserve_full_resolution(tmp_path):
    a, b = Image.new("RGB", (2000, 3000)), Image.new("RGB", (2000, 3000))
    b.putpixel((20, 30), (255, 0, 0))
    row = comparison.metrics(a, b)
    assert row["changed_pixels"] == 1 and row["max_channel_difference"] == 255
    assert row["mae"] == pytest.approx(255 / (2000*3000*3))
    assert comparison.side_by_side(a, b).size == (4000, 3000)
    with pytest.raises(ValueError, match="fresh output"):
        comparison.run_comparison(tmp_path / "absent", tmp_path / "absent", tmp_path)
