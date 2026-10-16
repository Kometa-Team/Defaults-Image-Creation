"""Offline, exact-file Helvetica/Liberation comparisons for the 11 real posters."""

from __future__ import annotations

import argparse
from dataclasses import replace
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from types import SimpleNamespace

from fontTools.ttLib import TTFont
from PIL import Image
import numpy as np
import uharfbuzz as hb
import yaml

try:
    from .create_poster import ROOT, digest
    from .poster_fixtures import extract_rows, row_case, translation_file
    from .compare_poster_renderers import (compare_images, effective_parameters, invalid_legacy_font,
                                          json_file, page, prepare_legacy)
    from .compare_bebas_fonts import caption_difference, legacy_poster, size_proposals
except ImportError:
    from create_poster import ROOT, digest
    from poster_fixtures import extract_rows, row_case, translation_file
    from compare_poster_renderers import (compare_images, effective_parameters, invalid_legacy_font,
                                         json_file, page, prepare_legacy)
    from compare_bebas_fonts import caption_difference, legacy_poster, size_proposals


RELEASE_URL = "https://github.com/liberationfonts/liberation-fonts/releases/tag/2.1.5"
ARCHIVE_URL = "https://github.com/liberationfonts/liberation-fonts/files/7261482/liberation-fonts-ttf-2.1.5.tar.gz"
ARCHIVE_SHA256 = "7191c669bf38899f73a2094ed00f7b800553364f90e2637010a69c0e268f25d0"
ORIGINAL_SHA256 = "d19ccd4211e3caaac2c7f1ae544456f5c67cd912e2bdfb1efb6602c090c724ee"
CANDIDATE_HASHES = {
    "LiberationSans-Bold.ttf": "788abee4c806d660e8aee46689dd8540cd4bb98da03dcc9d171ce3efd99a9173",
    "LICENSE": "93fed46019c38bbe566b479d22148e2e8a1e85ada614accb0211c37b2c61c19b",
    "AUTHORS": "b627404917ef824675cb24c32e2facd0b57650627955f3fc3d8a8863c5d0adfc",
    "README.md": "625a61d7e161cde3b1e9dd1ff8b7a86c251be536c34266bf1f1a9bd1c15c19e8",
}


def verify_candidate(directory):
    directory = Path(directory)
    for name, checksum in CANDIDATE_HASHES.items():
        if digest(directory / name) != checksum:
            raise ValueError(f"Official release asset hash differs: {name}")
    with TTFont(directory / "LiberationSans-Bold.ttf") as font:
        names = lambda identifier: sorted({n.toUnicode() for n in font["name"].names if n.nameID == identifier})
        metadata = {"family": names(1), "style": names(2), "version": names(5),
                    "postscript": names(6), "copyright": names(0), "character_count": len(font.getBestCmap())}
        if (metadata["family"] != ["Liberation Sans"] or metadata["style"] != ["Bold"]
                or metadata["version"] != ["Version 2.1.5"]):
            raise ValueError("Expected the unmodified official Liberation Sans Bold 2.1.5 face")
    return metadata


def affected_cases(bulk, assets=ROOT):
    rows = [r for r in extract_rows(bulk) if r["row"]["font"] in {"Helvetica-Bold", "Liberation Sans Bold", "Plus Jakarta Sans Bold"}]
    expected = {("Decade", "2020s"), *(("Year", str(year)) for year in range(2020, 2030))}
    if len(rows) != 11 or {(r["category"], r["row"]["key_name"]) for r in rows} != expected:
        raise ValueError("Affected poster dataset changed; review the 11 expected definitions")
    translations = yaml.safe_load(translation_file(assets).read_text(encoding="utf-8-sig"))
    return [row_case(row, translations, assets) for row in rows]


def caption(magick, font_path, text, size, directory, label):
    target = Path(directory) / (label + "-caption.png")
    command = [str(magick), "-font", Path(font_path).as_posix(), "-pointsize", str(size),
               "-fill", "white", "-gravity", "center", "-size", "1900x1000", "-background", "none",
               "caption:" + text, "-trim", "-gravity", "center", "-extent", "1900x1000", str(target)]
    completed = subprocess.run(command, capture_output=True, check=True, timeout=45,
                               env=dict(os.environ, MAGICK_THREAD_LIMIT="1", OMP_NUM_THREADS="1"))
    if invalid_legacy_font(completed.stderr.decode(errors="replace")):
        raise ValueError("Caption used a substituted font")
    with Image.open(target) as image:
        alpha = image.convert("RGBA").getchannel("A")
        bounds = alpha.getbbox()
        rows = np.flatnonzero(np.any(np.asarray(alpha), axis=1))
    if bounds is None:
        raise ValueError("Empty caption")
    bands = [group for group in np.split(rows, np.where(np.diff(rows) > 1)[0] + 1) if len(group)]
    # Read advances without parsing/repairing the restricted reference's malformed outlines.
    with TTFont(font_path) as font:
        units = font["head"].unitsPerEm
        cmap = font.getBestCmap()
        widths = {c: font["hmtx"][cmap[ord(c)]][0] * size / units for c in dict.fromkeys(text)}
    face = hb.Font(hb.Face(Path(font_path).read_bytes()))
    face.scale = (units, units)
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(face, buffer)
    advances = [position.x_advance * size / units for position in buffer.glyph_positions]
    return {"point_size": size, "file": target.name, "centered_ink_bounds": bounds,
            "ink_width": bounds[2] - bounds[0], "ink_height": bounds[3] - bounds[1],
            "line_band_count": len(bands), "glyph_advances_pixels": widths,
            "shaped_advances_pixels": advances, "shaped_advance_pixels": sum(advances), "command": command}


def prepare_workspace(source, workspace, magick, original, candidate):
    audit = prepare_legacy(source, workspace, ROOT, magick)
    for font in (original, candidate):
        target = workspace / "fonts" / font.name
        if target.exists():
            if digest(target) != digest(font):
                raise ValueError("Conflicting comparison font bytes")
        else:
            shutil.copyfile(font, target)
    script = workspace / "legacy.ps1"
    text = script.read_text(encoding="utf-8-sig")
    aliases = {"helveticabold": original.name, "liberationsansbold": candidate.name}
    additions = "\n".join(f'    "{key}" = "{filename}"' for key, filename in aliases.items()
                          if not re.search(r'"' + key + r'"\s*=', text))
    text, count = re.subn(r'(\$fontAliases\s*=\s*@\{)', lambda match: match[0] + "\n" + additions,
                         text, count=1)
    if count != 1:
        raise ValueError("Font alias table changed; review comparison isolation")
    text, count = re.subn(r'if\s*\(\$visibleFonts -contains \$fontName\)',
                         'if ($false -and $visibleFonts -contains $fontName)', text, flags=re.I)
    if count != 1:
        raise ValueError("Could not force exact-file font resolution")
    script.write_text(text, encoding="utf-8-sig")
    audit.update(isolated_sha256=digest(script), comparison_only="Exact font aliases; installed-font branch disabled; rendering statements unchanged")
    return audit


LABELS = {"original": "Original Helvetica Bold", "automatic": "Liberation Sans Bold: automatic fit",
          "selected": "Best measured per-caption size", "production": "Applied: uniform 432-point cap"}


def verify_production(report, summary):
    """Render the actual current configuration, retaining every comparison image."""
    report = Path(report)
    if len(summary["results"]) != 11:
        raise ValueError("Expected all 11 completed comparisons")
    for result in summary["results"]:
        for image in result["images"].values():
            if digest(report / result["id"] / image["report_file"]) != image["sha256"]:
                raise ValueError("Compared image changed; refusing stale verification")
    args = SimpleNamespace(magick=shutil.which("magick"), powershell=shutil.which("pwsh"))
    current = extract_rows()
    original = extract_rows(next(Path(path) for path in summary["protected_sources"]
                                 if Path(path).name == "create_default_posters.ps1"))
    if len(current) != len(original) or len(current) != 3352:
        raise ValueError("Source row inventory changed")
    unchanged = 0
    for old, new in zip(original, current):
        expected = old["row"]
        if old["row"]["font"] == "Helvetica-Bold":
            expected = dict(expected, font="Liberation Sans Bold", font_size="432")
        else:
            unchanged += 1
        if new["row"] != expected or new["category"] != old["category"] or new["fit"] != old["fit"]:
            raise ValueError("Change outside the 11 reviewed font/size fields")
    candidate = ROOT / "fonts/LiberationSans-Bold.ttf"
    if digest(candidate) != CANDIDATE_HASHES[candidate.name]:
        raise ValueError("Production font hash changed")
    environment = os.environ.get("POSTER_COMPARISON_MAGICK")
    os.environ["POSTER_COMPARISON_MAGICK"] = args.magick
    try:
        with tempfile.TemporaryDirectory(prefix=".production-", dir=report) as temporary:
            workspace = Path(temporary)
            audit = prepare_legacy(ROOT / "create_poster.ps1", workspace, ROOT, args.magick)
            for case, result in zip(affected_cases(ROOT / "create_default_posters.ps1"), summary["results"]):
                if case.parameters["text"] != result["name"]:
                    raise ValueError("Comparison order changed")
                directory = report / result["id"]
                parameters, fit = effective_parameters(case, args.magick, ROOT)
                if parameters["font_size"] != 432:
                    raise ValueError("Production did not apply the reviewed cap")
                result["parameters"]["production"], result["bulk_fits"]["production"] = parameters, fit
                metric = caption(args.magick, candidate, parameters["text"], 432, directory, "production")
                metric["difference"] = caption_difference(directory / "original-caption.png", directory / metric["file"])
                result["captions"]["production"] = metric
                image = legacy_poster(args, workspace, parameters, "Liberation Sans Bold", directory, "production")
                result["images"]["production"] = image
                if result["captions"]["selected"]["point_size"] == 432:
                    if image["sha256"] != result["images"]["selected"]["sha256"]:
                        raise ValueError("Production differs from the compared 432-point candidate")
                result["comparisons"]["production"] = compare_images(directory / "original.jpg", directory / "production.jpg",
                                                                          directory, "production", parameters["text_offset"])
                json_file(directory / "result.json", result)
                print("Production verified:", result["name"], flush=True)
    finally:
        if environment is None:
            os.environ.pop("POSTER_COMPARISON_MAGICK", None)
        else:
            os.environ["POSTER_COMPARISON_MAGICK"] = environment
    summary["production_verification"] = {"poster_count": 11, "unchanged_other_rows": unchanged,
                                           "isolation": audit, "font_sha256": digest(candidate),
                                           "bulk_source_sha256": digest(ROOT / "create_default_posters.ps1")}
    json_file(report / "summary.json", summary)
    write_report(report, summary)


def write_report(report, summary):
    body = '<h1>Helvetica / Liberation Sans Bold</h1><p><a href="summary.json">Measurements and provenance</a></p>'
    keys = [key for key in LABELS if key in summary["results"][0]["captions"]]
    body += '<table><tr><th>Poster</th>' + ''.join('<th>' + LABELS[key] + ': size / ink</th>' for key in keys) + '</tr>'
    for result in summary["results"]:
        body += f'<tr><td><a href="{result["id"]}/index.html">{html.escape(result["name"])}</a></td>'
        for key in keys:
            m = result["captions"][key]
            body += f'<td>{m["point_size"]} pt / {m["ink_width"]} x {m["ink_height"]}</td>'
        body += '</tr>'
        content = '<a href="../index.html">All comparisons</a><h1>' + html.escape(result["name"]) + '</h1><div class="images">'
        for key in keys:
            label = LABELS[key]
            content += f'<figure><figcaption>{label}</figcaption><a href="{key}.jpg"><img src="{key}.jpg" alt="{label} poster"></a></figure>'
        content += '</div><h2>Caption Crops</h2><div class="images">'
        for key in keys:
            label = LABELS[key]
            content += f'<figure><figcaption>{label}</figcaption><img src="{result["captions"][key]["file"]}" alt="{label} caption"></figure>'
        comparison = result["comparisons"].get("production", result["comparisons"]["selected"])
        content += '</div><h2>Applied Difference</h2><div class="images">'
        for name in [comparison["difference"], *comparison["text_crops"]]:
            content += f'<figure><img src="{name}" alt="Comparison crop or difference"></figure>'
        content += '</div><h2>Exact Measurements</h2><pre>' + html.escape(json.dumps(result, indent=2)) + '</pre>'
        (report / result["id"] / "index.html").write_text(page(result["name"], content), encoding="utf-8")
    body += '</table><div class="images">'
    first = summary["results"][0]
    for key in keys:
        label = LABELS[key]
        body += f'<figure><figcaption>{label}</figcaption><img src="{first["id"]}/{key}.jpg" alt="{label} 2020s poster"></figure>'
    body += '</div>'
    (report / "index.html").write_text(page("Helvetica replacement", body), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-font", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--bulk-definition", type=Path, required=True)
    parser.add_argument("--legacy-composer", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--selected-size", type=int, help="Uniform cap, otherwise search each real caption")
    parser.add_argument("--verify-production", action="store_true", help="Also render and check the current 432-point production configuration")
    args = parser.parse_args(argv)
    args.magick, args.powershell = shutil.which("magick"), shutil.which("pwsh")
    if not args.magick or not args.powershell:
        parser.error("ImageMagick and PowerShell 7 are required")
    metadata = verify_candidate(args.candidate_dir)
    args.original_font = args.original_font.resolve()
    candidate = (args.candidate_dir / "LiberationSans-Bold.ttf").resolve()
    if digest(args.original_font) != ORIGINAL_SHA256:
        raise ValueError("Original reference font hash differs")
    cases = affected_cases(args.bulk_definition)
    protected = {path: digest(path) for path in (args.original_font, candidate, args.bulk_definition, args.legacy_composer)}
    args.report_dir = args.report_dir.resolve()
    args.report_dir.mkdir(parents=True, exist_ok=False)
    summary = {"release_url": RELEASE_URL, "archive_url": ARCHIVE_URL, "archive_sha256": ARCHIVE_SHA256,
               "candidate": metadata, "candidate_hashes": CANDIDATE_HASHES, "original_sha256": ORIGINAL_SHA256,
               "protected_sources": {str(p): h for p, h in protected.items()}, "results": []}
    previous_environment = os.environ.get("POSTER_COMPARISON_MAGICK")
    os.environ["POSTER_COMPARISON_MAGICK"] = args.magick
    try:
        with tempfile.TemporaryDirectory(prefix=".legacy-", dir=args.report_dir) as temporary:
            workspace = Path(temporary)
            summary["isolation"] = prepare_workspace(args.legacy_composer, workspace, args.magick, args.original_font, candidate)
            for index, case in enumerate(cases, 1):
                directory = args.report_dir / case.id
                directory.mkdir()
                parameters, fits, captions = {}, {}, {}
                for key, path in (("original", args.original_font), ("automatic", candidate)):
                    parameters[key], fits[key] = effective_parameters(replace(case, parameters=dict(case.parameters, font=str(path))), args.magick, ROOT)
                    captions[key] = caption(args.magick, path, parameters[key]["text"], parameters[key]["font_size"], directory, key)
                reference = directory / captions["original"]["file"]
                captions["automatic"]["difference"] = caption_difference(reference, directory / captions["automatic"]["file"])
                sizes = [args.selected_size] if args.selected_size else size_proposals(captions["original"], captions["automatic"])
                options = []
                for size in sizes:
                    if not 10 <= size <= 500:
                        raise ValueError("Selected size outside composer bounds")
                    metric = caption(args.magick, candidate, parameters["automatic"]["text"], size, directory, f"size-{size}")
                    metric["difference"] = caption_difference(reference, directory / metric["file"])
                    if metric["ink_width"] <= case.fit[0] and metric["ink_height"] <= case.fit[1]:
                        options.append(metric)
                if not options:
                    raise ValueError("No candidate size fits the existing bounds")
                captions["selected"] = min(options, key=lambda m: (m["difference"]["foreground_alpha_mae_0_255"], m["point_size"]))
                parameters["selected"] = dict(parameters["automatic"], font_size=captions["selected"]["point_size"])
                result = {"id": case.id, "category": case.category, "name": case.parameters["text"], "source_row": case.source_row,
                          "parameters": parameters, "bulk_fits": fits, "captions": captions, "images": {}, "comparisons": {}}
                for key in parameters:
                    alias = "Helvetica-Bold" if key == "original" else "LiberationSans-Bold"
                    result["images"][key] = legacy_poster(args, workspace, parameters[key], alias, directory, key)
                    if key != "original":
                        result["comparisons"][key] = compare_images(directory / "original.jpg", directory / (key + ".jpg"), directory, key, parameters[key]["text_offset"])
                json_file(directory / "result.json", result)
                summary["results"].append(result)
                print(f'[{index}/{len(cases)}] {result["name"]}: selected {captions["selected"]["point_size"]} pt', flush=True)
    finally:
        if previous_environment is None:
            os.environ.pop("POSTER_COMPARISON_MAGICK", None)
        else:
            os.environ["POSTER_COMPARISON_MAGICK"] = previous_environment
    for path, checksum in protected.items():
        if digest(path) != checksum:
            raise RuntimeError(f"Comparison source changed: {path}")
    json_file(args.report_dir / "summary.json", summary)
    write_report(args.report_dir, summary)
    if args.verify_production:
        verify_production(args.report_dir, summary)
    print(f'Report: {args.report_dir / "index.html"}', flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
