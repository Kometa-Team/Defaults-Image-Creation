"""Compare local Jost weight trials without changing the production renderer."""

from __future__ import annotations

import argparse
import html
import json
import shutil
from pathlib import Path
from statistics import median

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, ImageDraw, ImageFont

from compare_people_renderers import cases_from_sources, preview
from create_people_poster import DIIIVOY_POINT_SIZE, FONTS, SCRIPT_DIR, Renderer, digest, label_name
from people_workspaces import atomic_json, reject_links
from poster_fonts import FontMetrics

NAMES = (
    "BoA", "Chae Soo-bin", "Naravit Lertratkosum", "Andrew Fung Chih-Chiang",
    "Tom Hanks", "Ana de Armas", "Lupita Nyong'o", "Jean-Claude Van Damme",
    "Zo\u00eb Garc\u00eda", "Jos\u00e9 \u00c1lvarez", "WILLIAM III", "MAX WONG",
    "Long Name With Five Words", "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
)
FONT = FONTS[2]
BOX = (1900, 580)


class FontTrial(Renderer):
    """Swap only the in-memory diiivoy font slot; leave other rendering intact."""

    def __init__(self, reference, font_path, preferred_size=200):
        self.art = reference.art
        self.font_dir = reference.font_dir
        self.metrics = dict(reference.metrics)
        self.metrics[FONT] = FontMetrics(font_path)
        self.fonts = {key: value for key, value in reference.fonts.items() if key[0] != FONT}
        self.preferred_size = preferred_size

    def width(self, text, font, size):
        if font == FONT and size == DIIIVOY_POINT_SIZE:
            size = self.preferred_size
        return super().width(text, font, size)

    def label(self, text, font_name, box, pointsize=None, align="center", vertical="center"):
        if font_name == FONT and pointsize == DIIIVOY_POINT_SIZE:
            pointsize = self.preferred_size
        return super().label(text, font_name, box, pointsize, align, vertical)


def cap_height(renderer, size):
    bounds = renderer.font(FONT, size).getbbox("H")
    return bounds[3] - bounds[1]


def matched_size(renderer, target):
    estimate = round(200 * target / cap_height(renderer, 200))
    return min(range(max(1, estimate - 4), estimate + 5),
               key=lambda size: (abs(cap_height(renderer, size) - target), abs(size - estimate)))


def label_measurement(renderer, text, preferred=200):
    advance = renderer.metrics[FONT].positions(text, preferred)[1]
    automatic = advance > BOX[0]
    label = renderer.label(text, FONT, BOX, None if automatic else preferred)
    alpha = label.getchannel("A")
    bounds = alpha.getbbox()
    if not bounds:
        raise ValueError(f"Empty comparison label: {text}")
    ink = float(np.asarray(alpha, dtype=np.float64).sum() / 255)
    area = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
    return label, {"advance": advance, "preferred_pointsize": preferred,
                   "cap_height": cap_height(renderer, preferred), "auto_fitted": automatic,
                   "bbox": list(bounds), "ink_pixels": ink, "ink_density": ink / area,
                   "touches_box": bounds[0] == 0 or bounds[1] == 0 or bounds[2] == BOX[0] or bounds[3] == BOX[1]}


def make_label_sheet(rows, target):
    top = max(0, min(measurement["bbox"][1] for _, _, measurement in rows) - 8)
    bottom = min(BOX[1], max(measurement["bbox"][3] for _, _, measurement in rows) + 8)
    row_height = bottom - top + 46
    sheet = Image.new("RGB", (1900, len(rows) * row_height), "#242424")
    draw = ImageDraw.Draw(sheet)
    heading_font = ImageFont.load_default(size=24)
    for index, (title, label, measurement) in enumerate(rows):
        y = index * row_height
        draw.text((20, y + 4), title, fill="#efefef", font=heading_font)
        strip = label.crop((0, top, 1900, bottom))
        sheet.paste(strip, (0, y + 38), strip)
        draw.line((0, y + row_height - 1, 1900, y + row_height - 1), fill="#555555")
    sheet.save(target, "PNG")


def static_instance(variable_path, weight, target):
    with TTFont(variable_path) as variable:
        axes = {axis.axisTag: axis for axis in variable["fvar"].axes}
        if set(axes) != {"wght"} or not axes["wght"].minValue <= weight <= axes["wght"].maxValue:
            raise ValueError("Expected a weight-only Jost variable font and an in-range weight")
        instance = instantiateVariableFont(variable, {"wght": weight}, inplace=False)
        try:
            instance.save(target)
        finally:
            instance.close()


def run_comparison(variable_path, license_path, output, sources=(), weights=(200, 250, 300),
                   reference_font=None, reference_size=DIIIVOY_POINT_SIZE):
    output = Path(output).absolute()
    reject_links(output)
    if output.exists():
        raise ValueError("Select a fresh output directory to preserve earlier comparisons")
    variable_path, license_path = Path(variable_path).resolve(), Path(license_path).resolve()
    if not variable_path.is_file() or not license_path.is_file():
        raise ValueError("Provide the official local Jost variable TTF and its license notice")
    if not weights or len(set(weights)) != len(weights):
        raise ValueError("Provide distinct Jost weights")
    if reference_size < 1:
        raise ValueError("Reference point size must be positive")
    output.mkdir(parents=True)
    for directory in ("fonts", "labels", "posters"):
        (output / directory).mkdir()
    shutil.copy2(license_path, output / "fonts/OFL-Jost.txt")
    reference_path = Path(reference_font).resolve() if reference_font else SCRIPT_DIR / "fonts" / FONT
    reference = FontTrial(Renderer(), reference_path, reference_size)
    reference_cap = cap_height(reference, reference_size)
    trials = [("reference", f"Reference: {reference_path.stem}, {reference_size}px", reference, reference_size)]
    fonts = []
    for weight in weights:
        path = output / "fonts" / f"Jost-{weight}.ttf"
        static_instance(variable_path, weight, path)
        native = FontTrial(reference, path)
        size = matched_size(native, reference_cap)
        calibrated = FontTrial(reference, path, size)
        trials.extend([(f"jost-{weight}-native", f"Jost {weight}: unchanged 200px", native, 200),
                       (f"jost-{weight}-matched", f"Jost {weight}: matched capitals, {size}px", calibrated, size)])
        fonts.append({"weight": weight, "file": str(path), "sha256": digest(path), "matched_pointsize": size})
    report = {"reference_font": str(reference_path), "reference_pointsize": reference_size,
              "reference_sha256": digest(reference_path),
              "jost_source": str(variable_path), "jost_sha256": digest(variable_path),
              "license_sha256": digest(license_path), "fonts": fonts,
              "method": "Same Pillow/layout pipeline; uppercase labels. Compare unchanged 200px and H-height-matched preferred sizes, retaining the existing 1900x580 auto-fit. No tracking, stretching or production settings changed. Ink density is a stroke-weight proxy, not a similarity score.",
              "labels": [], "posters": []}
    sections = []
    for index, name in enumerate(NAMES, 1):
        text = label_name(name).upper()
        rows, metrics = [], {}
        for key, title, renderer, preferred in trials:
            label, measurement = label_measurement(renderer, text, preferred)
            label.save(output / "labels" / f"{index}-{key}.png")
            if key != "reference":
                measurement["width_delta_percent"] = 100 * (measurement["advance"] / metrics["reference"]["advance"] - 1)
                measurement["density_delta_percent"] = 100 * (measurement["ink_density"] / metrics["reference"]["ink_density"] - 1)
            metrics[key] = measurement
            rows.append((title, label, measurement))
        sheet = f"labels/{index}-sheet.png"
        make_label_sheet(rows, output / sheet)
        report["labels"].append({"name": name, "text": text, "trials": metrics, "sheet": sheet})
        sections.append(f'<h2>{html.escape(name)}</h2><a href="{sheet}"><img loading="lazy" src="{sheet}" alt="{html.escape(name)} font trials"></a>')
    report["summary"] = {}
    for key, title, renderer, preferred in trials[1:]:
        rows = [row["trials"][key] for row in report["labels"]]
        report["summary"][key] = {
            "title": title, "preferred_pointsize": preferred,
            "median_width_delta_percent": median(row["width_delta_percent"] for row in rows),
            "median_abs_width_delta_percent": median(abs(row["width_delta_percent"]) for row in rows),
            "median_density_delta_percent": median(row["density_delta_percent"] for row in rows),
            "median_abs_density_delta_percent": median(abs(row["density_delta_percent"]) for row in rows),
            "fit_changes": sum(row["auto_fitted"] != ref["trials"]["reference"]["auto_fitted"] for row, ref in zip(rows, report["labels"])),
            "touches_box": sum(row["touches_box"] for row in rows),
        }
    poster_sections = []
    selected = [trial for trial in trials if trial[0] == "reference" or trial[0].endswith("matched")]
    cases = cases_from_sources([Path(p).resolve() for p in sources], False) if sources else []
    for index, case in enumerate(cases, 1):
        sheet = Image.new("RGB", (len(selected) * 400, 1280), "white")
        draw = ImageDraw.Draw(sheet)
        heading_font = ImageFont.load_default(size=16)
        outputs = {}
        for column, (key, title, renderer, preferred) in enumerate(selected):
            with Image.open(case["cutout"]) as source:
                rendered, warnings = renderer.render(source, case["name"])
            draw.text((column * 400 + 8, 3), title, fill="black", font=heading_font)
            paths = {}
            for row, style in enumerate(("diiivoy", "diiivoycolor")):
                path = f"posters/{index}-{style}-{key}.jpg"
                rendered[style].save(output / path, "JPEG", quality=100, subsampling=0)
                paths[style] = path
                draw.text((column * 400 + 8, 25 + row * 625), style, fill="black")
                sheet.paste(preview(rendered[style], (392, 588)), (column * 400 + 4, 43 + row * 625))
            for image in rendered.values():
                image.close()
            outputs[key] = paths
        sheet_path = f"posters/{index}-sheet.jpg"
        sheet.save(output / sheet_path, "JPEG", quality=94)
        report["posters"].append({"name": case["name"], "source_cutout": str(case["cutout"]),
                                  "cutout_sha256": digest(case["cutout"]), "outputs": outputs, "sheet": sheet_path})
        poster_sections.append(f'<h2>{html.escape(case["name"])}</h2><a href="{sheet_path}"><img src="{sheet_path}" alt="Poster font trials"></a>')
    atomic_json(output / "report.json", report)
    rows = "".join(f'<tr><td>{html.escape(m["title"])}</td><td>{m["median_width_delta_percent"]:+.2f}%</td><td>{m["median_density_delta_percent"]:+.2f}%</td><td>{m["fit_changes"]}</td></tr>' for m in report["summary"].values())
    document = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>People font comparison</title>'
                '<style>body{font:16px system-ui;margin:24px auto;padding:0 16px;max-width:1600px;color:#222;background:#fff}img{max-width:100%;height:auto}table{border-collapse:collapse}td,th{padding:8px 16px;text-align:left;border-bottom:1px solid #ddd}h2{margin-top:32px;font-size:20px}</style>'
                '<h1>People font comparison</h1><p>' + html.escape(report["method"]) + '</p>'
                '<table><tr><th>Trial</th><th>Median width change</th><th>Median ink-density change</th><th>Auto-fit branch changes</th></tr>'
                + rows + '</table><h2>Real Poster Previews</h2>' + ''.join(poster_sections)
                + '<h2>Label Specimens</h2>' + ''.join(sections) + '</html>')
    (output / "index.html").write_text(document, encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jost", type=Path, required=True, help="Official local Jost[wght].ttf")
    parser.add_argument("--license", type=Path, required=True, dest="license_path")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-config", type=Path, nargs="*", default=[])
    parser.add_argument("--weights", type=int, nargs="+", default=[200, 250, 300])
    parser.add_argument("--reference-font", type=Path, help="Optional externally supplied reference font; defaults to bundled Jost")
    parser.add_argument("--reference-size", type=int, default=DIIIVOY_POINT_SIZE)
    args = parser.parse_args()
    try:
        report = run_comparison(args.jost, args.license_path, args.output, args.source_config, args.weights,
                                args.reference_font, args.reference_size)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
