import json
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compare_people_fonts as comparison
from create_people_poster import DIIIVOY_POINT_SIZE, FONTS, SCRIPT_DIR, Renderer, digest


@pytest.fixture
def reference(monkeypatch):
    monkeypatch.delenv("POSTER_FONT_DIR", raising=False)
    monkeypatch.delenv("POSTER_ASSET_DIR", raising=False)
    return Renderer()


def test_trial_is_isolated_and_identical_font_renders_identically(reference):
    font = SCRIPT_DIR / "fonts" / FONTS[2]
    metrics = reference.metrics[FONTS[2]]
    before = digest(font)
    trial = comparison.FontTrial(reference, font)
    target_height = comparison.cap_height(reference, 200)
    assert comparison.matched_size(trial, target_height) == 200
    original, original_measurement = comparison.label_measurement(reference, "CHAE SOO-BIN")
    new, new_measurement = comparison.label_measurement(trial, "CHAE SOO-BIN")
    assert new.tobytes() == original.tobytes()
    assert new_measurement == original_measurement
    assert reference.metrics[FONTS[2]] is metrics
    assert digest(font) == before


def test_calibrated_trial_changes_only_diiivoy_slot(reference):
    font = SCRIPT_DIR / "fonts" / FONTS[2]
    trial = comparison.FontTrial(reference, font, preferred_size=180)
    assert trial.width("PERSON", FONTS[2], DIIIVOY_POINT_SIZE) == reference.width("PERSON", FONTS[2], 180)
    assert trial.width("PERSON", FONTS[0], 183) == reference.width("PERSON", FONTS[0], 183)
    expected = reference.label("PERSON", FONTS[2], comparison.BOX, 180)
    assert trial.label("PERSON", FONTS[2], comparison.BOX, DIIIVOY_POINT_SIZE).tobytes() == expected.tobytes()


def test_local_report_has_specimens_metrics_and_license(tmp_path, monkeypatch, reference):
    variable, notice = tmp_path / "variable.ttf", tmp_path / "OFL.txt"
    variable.write_bytes(b"synthetic input; instancing mocked")
    notice.write_text("Synthetic test notice", encoding="utf-8")
    output = tmp_path / "report"
    monkeypatch.setattr(comparison, "NAMES", ("Zo\u00eb Garc\u00eda", "Long Name With Five Words"))
    monkeypatch.setattr(comparison, "Renderer", lambda: reference)
    monkeypatch.setattr(comparison, "static_instance", lambda source, weight, target: shutil.copyfile(SCRIPT_DIR / "fonts" / FONTS[2], target))
    report = comparison.run_comparison(variable, notice, output, weights=(200, 300), reference_size=200)
    assert len(report["labels"]) == 2 and len(report["summary"]) == 4
    assert report["posters"] == []
    assert all(row["median_abs_width_delta_percent"] == 0 for row in report["summary"].values())
    assert all(row["median_abs_density_delta_percent"] == 0 for row in report["summary"].values())
    assert (output / "fonts/OFL-Jost.txt").read_bytes() == notice.read_bytes()
    assert (output / "labels/1-sheet.png").is_file()
    assert "Zo\u00eb Garc\u00eda" in (output / "index.html").read_text(encoding="utf-8")
    assert json.loads((output / "report.json").read_text(encoding="utf-8"))["jost_sha256"] == digest(variable)


def test_existing_output_is_never_overwritten(tmp_path):
    with pytest.raises(ValueError, match="fresh output"):
        comparison.run_comparison(tmp_path / "missing", tmp_path / "missing", tmp_path)


def test_label_sheet_does_not_crop_accents_or_descenders(tmp_path):
    label = Image.new("RGBA", comparison.BOX)
    ImageDraw.Draw(label).rectangle((500, 171, 700, 408), fill="white")
    bounds = label.getbbox()
    target = tmp_path / "sheet.png"
    comparison.make_label_sheet([("Tall glyph", label, {"bbox": bounds})], target)
    top, bottom = bounds[1] - 8, bounds[3] + 8
    expected = Image.new("RGB", (1900, bottom - top), "#242424")
    strip = label.crop((0, top, 1900, bottom))
    expected.paste(strip, (0, 0), strip)
    with Image.open(target) as sheet:
        assert sheet.crop((0, 38, 1900, 38 + bottom - top)).tobytes() == expected.tobytes()
