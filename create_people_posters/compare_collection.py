"""Build local COLLECTION review artifacts without batches or publication."""

from __future__ import annotations

import argparse
import html
import json
import math
import types
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw

import create_people_poster as poster
from people_workspaces import reject_links


ORIGINAL_ARTWORK = {
    "signature": "@zbase-Signature.png",
    "rainier": "@zbase-People-Clear2.png",
    "diiivoy": "@zbase-People-Clear3.png",
    "diiivoycolor": "@zbase-People-Clear3.png",
}


def load_reference(source):
    """Load the explicitly saved pre-change Python renderer, never PowerShell."""
    module = types.ModuleType("collection_reference")
    module.__file__ = str(poster.SCRIPT_DIR / "create_people_poster.py")
    exec(compile(Path(source).read_text(encoding="utf-8"), str(source), "exec"), module.__dict__)
    return module.Renderer()


def metrics(reference, replacement):
    a = np.asarray(reference.convert("RGB"), dtype=np.int16)
    b = np.asarray(replacement.convert("RGB"), dtype=np.int16)
    delta = np.abs(a - b)
    changed = np.any(delta != 0, axis=2)
    return {"mae": float(delta.mean()), "rmse": math.sqrt(float(np.square(delta.astype(np.float64)).mean())),
            "max_channel_difference": int(delta.max()), "changed_pixels": int(changed.sum()),
            "changed_percent": float(changed.mean() * 100)}


def side_by_side(first, second):
    result = Image.new("RGB", (first.width + second.width, max(first.height, second.height)))
    result.paste(first, (0, 0))
    result.paste(second, (first.width, 0))
    return result


def union_bounds(*bounds):
    return (min(b[0] for b in bounds), min(b[1] for b in bounds),
            max(b[2] for b in bounds), max(b[3] for b in bounds))


def run_comparison(source, reference_source, output, name=None):
    output = Path(output).absolute()
    reject_links(output)
    if output.exists():
        raise ValueError("Use a fresh output directory; existing review evidence is never overwritten")
    renderer = poster.Renderer()
    reference = load_reference(reference_source)
    with Image.open(source) as image:
        image.load()
        replacements, warnings = renderer.render(image, name or Path(source).stem)
        references, reference_warnings = reference.render(image, name or Path(source).stem)
    output.mkdir(parents=True)
    report = {"source": str(Path(source).resolve()), "source_sha256": poster.digest(Path(source)),
              "reference_source": str(Path(reference_source).resolve()),
              "reference_source_sha256": poster.digest(Path(reference_source)),
              "name": name or Path(source).stem, "dimensions": poster.SIZE,
              "reference": "pre-change Python renderer with original embedded-COLLECTION artwork",
              "metrics_basis": "lossless RGB pixels; separately measured JPEGs use quality=100, subsampling=0",
              "fingerprint": poster.renderer_fingerprint(), "warnings": warnings,
              "reference_warnings": reference_warnings, "styles": {}}
    report["unchanged_styles"] = {style: metrics(references[style], replacements[style])
                                  for style in ("bw", "transparent")}
    report["transparent_alpha_unchanged"] = (references["transparent"].getchannel("A").tobytes()
                                              == replacements["transparent"].getchannel("A").tobytes())
    report["original"] = "No original photograph is rewritten; render() only consumes the cutout"
    report["font_inventory"] = [{"file": p.name, "sha256": poster.digest(p), "bytes": p.stat().st_size}
                                for p in sorted((poster.SCRIPT_DIR / "fonts").iterdir()) if p.is_file()]
    # Import only the existing local image checks; no sync or publisher is run.
    from sync_people_images import image_quality_findings
    sheet = Image.new("RGB", (1600, 640), "#242424")
    sheet_draw = ImageDraw.Draw(sheet)
    for index, style in enumerate(poster.COLLECTION_CONFIG):
        directory = output / style
        directory.mkdir()
        old, new = references[style], replacements[style]
        assert old.size == new.size == poster.SIZE
        layer = Image.new("RGBA", poster.SIZE)
        bounds = renderer.render_collection(layer, style)
        art_old = reference.art[ORIGINAL_ARTWORK[style]]
        art_new = renderer.art[poster.COLLECTION_ARTWORK[style]]
        channels = ImageChops.difference(art_old, art_new).split()
        art_delta = channels[0]
        for channel in channels[1:]:
            art_delta = ImageChops.lighter(art_delta, channel)
        old_bounds = art_delta.getbbox()
        region = union_bounds(old_bounds, bounds)
        crop = (max(0, region[0]-12), max(0, region[1]-12),
                min(poster.SIZE[0], region[2]+12), min(poster.SIZE[1], region[3]+12))
        old.save(directory / "reference.png")
        new.save(directory / "replacement.png")
        old.save(directory / "reference.jpg", "JPEG", quality=100, subsampling=0)
        new.save(directory / "replacement.jpg", "JPEG", quality=100, subsampling=0)
        side_by_side(old, new).save(directory / "comparison.png")
        side_by_side(old.crop(crop), new.crop(crop)).save(directory / "collection-comparison.png")
        difference = ImageChops.difference(old, new)
        difference.save(directory / "difference.png")
        difference.point(lambda value: min(255, value * 4)).save(directory / "difference-4x.png")
        layer.save(directory / "collection-layer.png")
        exterior = difference.copy()
        ImageDraw.Draw(exterior).rectangle((region[0], region[1], region[2]-1, region[3]-1), fill=0)
        with Image.open(directory / "reference.jpg") as a, Image.open(directory / "replacement.jpg") as b:
            jpeg_metrics = metrics(a, b)
        failures, notes = image_quality_findings(style, directory / "replacement.jpg")
        row = {"artwork": poster.COLLECTION_ARTWORK[style], "original_artwork": ORIGINAL_ARTWORK[style],
               "text": "COLLECTION", "color": "white", **poster.COLLECTION_CONFIG[style],
               "layout_engine": "Pillow BASIC, per-character getlength, unrounded tracking, trim visible alpha",
               "visible_bounds": bounds, "old_lettering_region": old_bounds, "crop_bounds": crop,
               "font_sha256": poster.digest(renderer.font_dir / poster.COLLECTION_CONFIG[style]["font"]),
               "full_image": metrics(old, new), "collection_crop": metrics(old.crop(crop), new.crop(crop)),
               "jpeg_full_image": jpeg_metrics, "outside_collection_unchanged": exterior.getbbox() is None,
               "validation": {"blocking": failures, "notes": notes},
               "remaining_differences": "Accepted font approximation: glyph shapes, spacing, weight and ink bounds differ from baked artwork"}
        (directory / "report.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
        report["styles"][style] = row
        for y, image in ((25, old), (335, new)):
            sheet.paste(image.resize((200, 300), Image.Resampling.LANCZOS), (index*400+100, y))
        sheet_draw.text((index*400+12, 6), style + " / reference above, replacement below", fill="white")
    sheet.save(output / "contact-sheet.jpg", quality=95)
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    entries = []
    for style in report["styles"]:
        label = html.escape(style)
        entries.append(f'<h2>{label}</h2><a href="{style}/comparison.png">Full resolution comparison</a> | '
                       f'<a href="{style}/replacement.jpg">Completed poster</a> | '
                       f'<a href="{style}/difference-4x.png">Difference (4x)</a> | '
                       f'<a href="{style}/report.json">Metrics</a><p>Reference left, replacement right</p>'
                       f'<img style="max-width:100%" src="{style}/collection-comparison.png">')
    (output / "index.html").write_text('<!doctype html><meta charset="utf-8"><title>COLLECTION review</title>'
                                      '<h1>People COLLECTION review</h1><p>2000 × 3000 posters. '
                                      'Lossless comparisons; calibrated lettering is approximate.</p>'
                                      '<img style="max-width:100%" src="contact-sheet.jpg">'
                                      + ''.join(entries), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Local transparent person PNG; read only")
    parser.add_argument("--reference-source", type=Path, required=True, help="Saved pre-change Python renderer source")
    parser.add_argument("--output", type=Path, required=True, help="Fresh local review directory")
    parser.add_argument("--name", help="Person label; defaults to source filename")
    args = parser.parse_args()
    report = run_comparison(args.source, args.reference_source, args.output, args.name)
    print(json.dumps({style: row["full_image"] for style, row in report["styles"].items()}, indent=2))
    return int(any(row["validation"]["blocking"] or not row["outside_collection_unchanged"]
                   for row in report["styles"].values()))


if __name__ == "__main__":
    raise SystemExit(main())
