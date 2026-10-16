"""Compare official OFL Bebas replacements against nine actual Playlist posters."""

from __future__ import annotations

import argparse
from dataclasses import replace
import html
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request

from fontTools.ttLib import TTFont
from PIL import Image
import numpy as np
import uharfbuzz as hb
import yaml

try:
    from .create_poster import ROOT, digest
    from .poster_fixtures import extract_rows, row_case, translation_file
    from .compare_poster_renderers import (compare_images, effective_parameters, invalid_legacy_font,
                                          json_file, measured, picture_metadata, prepare_legacy, page)
except ImportError:
    from create_poster import ROOT, digest
    from poster_fixtures import extract_rows, row_case, translation_file
    from compare_poster_renderers import (compare_images, effective_parameters, invalid_legacy_font,
                                         json_file, measured, picture_metadata, prepare_legacy, page)


CANDIDATES = {
    "neue": {"repository": "Bebas-Neue", "commit": "46e72cec95ee599f72c0de4a12cfe64828949236",
             "path": "fonts/BebasNeue(2018)ByDhamraType/ttf/BebasNeue-Regular.ttf",
             "file": "BebasNeue-Regular.ttf", "family": "Bebas Neue", "alias": "BebasNeue-Regular",
             "sha256": "08e4623805102d819f58601e46e345648846075e363b2ceb23313c2d1c83ec73",
             "license_sha256": "72082f6cb4d04be2ecf7cc7d9e1e7d73787f0af8a5a278a47cade70c16b78341",
             "trademark_sha256": "de35dd6839271a6f400dc40bd9d3f4e766b908591c3e58f00861786c7a1da064"},
    "kai": {"repository": "Bebas-Kai", "commit": "f94118f4686b548f721ae364c0eae4dfe287c057",
            "path": "fonts/ttf/BebasKai.ttf", "file": "BebasKai.ttf", "family": "Bebas Kai", "alias": "BebasKai",
            "sha256": "35a74556f4a07d2e8402321fb1388310f0d3654b0276dd7c77b2d6b58290daef",
            "license_sha256": "34538917b07bfed487639af88594901822f02ac19aa1f85f6d20c58c5c229607",
            "trademark_sha256": "e8625f3ead92c4d02467fb6bae5a49ac38b876c78dabf71fefce4fac22d186d8"},
}
NOTICES = ("OFL.txt", "AUTHORS.txt", "CONTRIBUTORS.txt", "TRADEMARKS.md")


def candidate_sources(root, fetch=False):
    """Fetch only on explicit request, pinned to author commits; never overwrite."""
    root = Path(root)
    sources = {}
    for key, candidate in CANDIDATES.items():
        files = {}
        expected_hashes = {candidate["file"]: candidate["sha256"], "OFL.txt": candidate["license_sha256"],
                           "TRADEMARKS.md": candidate["trademark_sha256"],
                           "AUTHORS.txt": "3662cb2eab4a247b62e7e33cc6b49126b70b431f2018e8c67361ab019b3c7825",
                           "CONTRIBUTORS.txt": "081d6434ae1b79b8f51c3c27315de7c22251d5b1c0b48666c97c1340bd7f354a"}
        for name, upstream in [(candidate["file"], candidate["path"]), *((n, n) for n in NOTICES)]:
            url = f'https://raw.githubusercontent.com/dharmatype/{candidate["repository"]}/{candidate["commit"]}/{upstream}'
            target = root / key / name
            if fetch:
                request = urllib.request.Request(url, headers={"User-Agent": "Kometa Playlist font comparison"})
                with urllib.request.urlopen(request, timeout=30) as response:
                    data = response.read(2_000_001)
                if len(data) > 2_000_000:
                    raise ValueError("Candidate asset exceeds download bound")
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    if target.read_bytes() != data:
                        raise FileExistsError(f"Refusing to replace differing candidate asset: {target}")
                else:
                    with target.open("xb") as output:
                        output.write(data)
            if not target.is_file():
                raise FileNotFoundError(f"Missing candidate {target}; use --fetch-candidates explicitly")
            if digest(target) != expected_hashes[name]:
                raise ValueError(f"Candidate hash differs from pinned author asset: {target}")
            files[name] = {"path": str(target.resolve()), "url": url, "sha256": digest(target)}
        license_text = (root / key / "OFL.txt").read_text(encoding="utf-8-sig")
        if "SIL OPEN FONT LICENSE Version 1.1" not in license_text:
            raise ValueError("Candidate lacks the expected original OFL 1.1 notice")
        with TTFont(root / key / candidate["file"]) as font:
            names = lambda ids: sorted({n.toUnicode() for n in font["name"].names if n.nameID in ids})
            metadata = {"family_names": names({1, 16}), "style_names": names({2, 17}),
                        "versions": names({5}), "postscript_names": names({6}), "copyright": names({0})}
            if candidate["family"] not in metadata["family_names"] or "Regular" not in metadata["style_names"]:
                raise ValueError("Candidate family/style differs from the selected official face")
            if key == "neue" and not any("2.000" in version for version in metadata["versions"]):
                raise ValueError("Expected the official Dharma Type Bebas Neue v2.000, not the 2014 family")
        sources[key] = dict(candidate, files=files, metadata=metadata)
    return sources


def playlist_cases(assets=ROOT, bulk=None):
    rows = [r for r in extract_rows(bulk or ROOT / "create_default_posters.ps1") if r["category"] == "Playlist"]
    if len(rows) != 9:
        raise ValueError("Playlist source changed: review the required nine-case dataset")
    translations = yaml.safe_load(translation_file(assets).read_text(encoding="utf-8-sig"))
    return [row_case(row, translations, assets) for row in rows]


def font_metrics(path, text, size):
    """Exact font-unit metrics plus unhinted HarfBuzz advances, not raster estimates."""
    data = Path(path).read_bytes()
    with TTFont(BytesIO(data)) as font:
        units = font["head"].unitsPerEm
        cmap = font.getBestCmap()
        missing = [c for c in text if ord(c) not in cmap]
        if missing:
            raise ValueError(f"Missing glyphs in {Path(path).name}: {missing!r}")
        glyphs = font.getGlyphSet()
        from fontTools.pens.boundsPen import BoundsPen
        widths = {}
        for character in dict.fromkeys(text):
            name = cmap[ord(character)]
            pen = BoundsPen(glyphs)
            glyphs[name].draw(pen)
            advance, bearing = font["hmtx"][name]
            widths[character] = {"glyph": name, "advance_units": advance, "bearing_units": bearing,
                                 "outline_bounds_units": pen.bounds, "advance_pixels": advance * size / units}
        font_height = {"hhea_ascent_units": font["hhea"].ascent, "hhea_descent_units": font["hhea"].descent,
                       "hhea_line_gap_units": font["hhea"].lineGap}
    face = hb.Font(hb.Face(data))
    face.scale = (units, units)
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(face, buffer)
    shaped = [{"cluster": info.cluster, "glyph_id": info.codepoint, "advance_pixels": pos.x_advance * size / units,
               "x_offset_pixels": pos.x_offset * size / units, "y_offset_pixels": pos.y_offset * size / units}
              for info, pos in zip(buffer.glyph_infos, buffer.glyph_positions)]
    nominal = sum(widths[c]["advance_pixels"] for c in text)
    advance = sum(g["advance_pixels"] for g in shaped)
    return dict(units_per_em=units, point_size=size, glyphs=widths, shaped_glyphs=shaped,
                nominal_advance_pixels=nominal, shaped_advance_pixels=advance,
                shaping_adjustment_pixels=advance - nominal, **font_height)


def caption(magick, font, text, size, directory, label):
    target = directory / (label + "-caption.png")
    raw = directory / (label + "-caption-raw.png")
    command = [str(magick), "-font", Path(font).as_posix(), "-pointsize", str(size), "-fill", "white",
               "-gravity", "center", "-size", "1900x1000", "-background", "none", "caption:" + text,
               "-write", str(raw), "-trim", "-gravity", "center", "-extent", "1900x1000", str(target)]
    result = subprocess.run(command, check=True, capture_output=True, timeout=45,
                            env=dict(os.environ, MAGICK_THREAD_LIMIT="1", OMP_NUM_THREADS="1"))
    if invalid_legacy_font(result.stderr.decode(errors="replace")):
        raise ValueError("Caption comparison rejected a substituted font")
    with Image.open(target) as image:
        alpha = np.asarray(image.convert("RGBA").getchannel("A"))
    with Image.open(raw) as image:
        raw_bounds = image.convert("RGBA").getchannel("A").getbbox()
    rows = np.flatnonzero(np.any(alpha, axis=1))
    bands = []
    for group in np.split(rows, np.where(np.diff(rows) > 1)[0] + 1):
        if len(group):
            bands.append([int(group[0]), int(group[-1]) + 1])
    bounds = Image.fromarray(alpha).getbbox()
    return {"caption_file": target.name, "raw_file": raw.name, "point_size": size,
            "raw_ink_bounds": raw_bounds, "centered_ink_bounds": bounds,
            "ink_width": bounds[2] - bounds[0], "ink_height": bounds[3] - bounds[1],
            "raster_line_bands": bands, "line_band_count": len(bands),
            "font_metrics": font_metrics(font, text, size), "command": command}


def caption_difference(reference, candidate):
    with Image.open(reference) as first, Image.open(candidate) as second:
        a = np.asarray(first.convert("RGBA").getchannel("A"), dtype=np.int16)
        b = np.asarray(second.convert("RGBA").getchannel("A"), dtype=np.int16)
    union = np.logical_or(a > 0, b > 0)
    return {"foreground_alpha_mae_0_255": float(np.abs(a - b)[union].mean()) if union.any() else 0,
            "full_caption_alpha_mae_0_255": float(np.abs(a - b).mean()),
            "foreground_union_pixels": int(union.sum())}


def size_proposals(original, candidate):
    size = candidate["point_size"]
    targets = [size, size * original["ink_width"] / candidate["ink_width"],
               size * original["ink_height"] / candidate["ink_height"]]
    low, high = max(10, math.floor(min(targets)) - 3), min(500, math.ceil(max(targets)) + 3)
    if high - low > 120:
        raise ValueError("Candidate requires excessive fitting changes; manual review required")
    return range(low, high + 1)


def compare_captions(magick, fonts, case, directory):
    fits, metrics = {}, {}
    for key, path in fonts.items():
        parameters, fit = effective_parameters(replace(case, parameters=dict(case.parameters, font=str(path))), magick, ROOT)
        fits[key] = {"parameters": parameters, "bulk_fit": fit}
        metrics[key] = caption(magick, path, parameters["text"], parameters["font_size"], directory, key)
    reference = directory / metrics["original"]["caption_file"]
    for key in CANDIDATES:
        metrics[key]["difference"] = caption_difference(reference, directory / metrics[key]["caption_file"])
        options = [(metrics[key], fits[key]["parameters"]["font_size"])]
        for size in size_proposals(metrics["original"], metrics[key]):
            if size == fits[key]["parameters"]["font_size"]:
                continue
            result = caption(magick, fonts[key], case.parameters["text"], size, directory, f"{key}-{size}")
            if result["ink_width"] > case.fit[0] or result["ink_height"] > case.fit[1]:
                continue
            result["difference"] = caption_difference(reference, directory / result["caption_file"])
            options.append((result, size))
        best, size = min(options, key=lambda entry: (entry[0]["difference"]["foreground_alpha_mae_0_255"],
                                                    abs(entry[1] - metrics[key]["point_size"])))
        metrics[key + "-adjusted"] = best
        fits[key + "-adjusted"] = {"parameters": dict(fits[key]["parameters"], font_size=size),
                                    "bulk_fit": fits[key]["bulk_fit"], "adjusted_after_existing_fit": True}
    return fits, metrics


def prepare_comparison_workspace(args, workspace, fonts):
    audit = prepare_legacy(args.legacy_composer, workspace, ROOT, args.magick)
    for path in fonts.values():
        target = workspace / "fonts" / path.name
        if target.exists():
            if digest(target) != digest(path):
                raise ValueError("Comparison font filename collision")
        else:
            shutil.copyfile(path, target)
    script = workspace / "legacy.ps1"
    text = script.read_text(encoding="utf-8-sig")
    aliases = {"bebasregular": fonts["original"].name,
               **{re.sub(r"[^a-z0-9]", "", v["alias"].lower()): v["file"] for v in CANDIDATES.values()}}
    # Comparison-only font resolution: existing rendering statements stay intact.
    text, count = re.subn(r'(\$fontAliases\s*=\s*@\{)',
                         lambda match: match[0] + "\n" + "\n".join(f'    "{key}" = "{name}"' for key, name in aliases.items()
                            if not re.search(r'"' + re.escape(key) + r'"\s*=', text)), text, count=1)
    if count != 1:
        raise ValueError("Legacy font mapping changed; re-audit isolation")
    # Avoid host-installed fonts overriding the exact bundled files under test.
    text, forced = re.subn(r'if\s*\(\$visibleFonts -contains \$fontName\)',
                           'if ($false -and $visibleFonts -contains $fontName)', text, flags=re.I)
    if forced != 1:
        raise ValueError("Could not force exact bundled-font resolution in isolated composer")
    script.write_text(text, encoding="utf-8-sig")
    audit.update(isolated_sha256=digest(script), comparison_only="Added candidate aliases and forced exact bundled-file resolution; rendering statements unchanged")
    return audit


def legacy_poster(args, workspace, parameters, alias, directory, label):
    values = dict(parameters, font=alias)
    for name in ("logo_offset", "text_offset"):
        values[name] = f"{int(values[name]):+d}"
    json_file(workspace / "parameters.json", values)
    existing = list((workspace / "output").rglob("*.jpg")) if (workspace / "output").exists() else []
    for path in existing:
        path.unlink()
    command = [args.powershell, "-NoLogo", "-NoProfile", "-File", workspace / "run.ps1",
               "-ParameterFile", workspace / "parameters.json"]
    measurement = measured(command, workspace, directory / (label + ".log"))
    log = (directory / (label + ".log")).read_text(encoding="utf-8-sig", errors="replace")
    generated = list((workspace / "output").rglob("*.jpg")) if (workspace / "output").exists() else []
    if measurement["returncode"] or len(generated) != 1 or invalid_legacy_font(log) or "[ERROR]" in log or "magick.exe:" in log:
        raise RuntimeError(f"Legacy comparison failed or substituted font: {label}; see log")
    target = directory / (label + ".jpg")
    shutil.copyfile(generated[0], target)
    return dict(picture_metadata(target), report_file=target.name, measurement=measurement)


def write_report(report, results, metadata):
    labels = {"original": "Original Bebas", "neue": "Bebas Neue: existing fitting", "kai": "Bebas Kai: existing fitting",
              "neue-adjusted": "Bebas Neue: best measured size", "kai-adjusted": "Bebas Kai: best measured size"}
    body = '<h1>Playlist Bebas Replacement Comparison</h1><p>Original and both official OFL candidates. Metrics compare fonts, not rendering engines. No font binaries are included in this report.</p>'
    body += '<p><a href="summary.json">Full measurements and source provenance</a></p>'
    if metadata.get("recommendation"):
        body += '<h2>Recommendation</h2><p>' + html.escape(metadata["recommendation"]) + '</p>'
    body += '<h2>Caption Measurements</h2><table><tr><th>Variant</th><th>Size</th><th>Ink WxH</th><th>Advance</th><th>Line Bands</th><th>Foreground Alpha MAE</th></tr>'
    for key, metric in metadata["caption_metrics"].items():
        body += f'<tr><td>{labels[key]}</td><td>{metric["point_size"]}</td><td>{metric["ink_width"]} x {metric["ink_height"]}</td><td>{metric["font_metrics"]["shaped_advance_pixels"]:.3f}</td><td>{metric["line_band_count"]}</td><td>{metric.get("difference", {}).get("foreground_alpha_mae_0_255", 0):.4f}</td></tr>'
    body += '</table><h2>Exact Glyph Advances</h2><p>Pixels at each displayed point size; unhinted advance widths, not ink widths. This caption has zero HarfBuzz kerning adjustment in all three fonts.</p><table><tr><th>Character</th>'
    keys = list(metadata["caption_metrics"])
    body += ''.join('<th>' + labels[key] + '</th>' for key in keys) + '</tr>'
    for character in metadata["caption_metrics"]["original"]["font_metrics"]["glyphs"]:
        body += '<tr><td>' + html.escape(character if character != ' ' else '(space)') + '</td>'
        for key in keys:
            advance = metadata["caption_metrics"][key]["font_metrics"]["glyphs"][character]["advance_pixels"]
            body += f'<td>{advance:.3f}</td>'
        body += '</tr>'
    body += '</table><h2>Isolated Captions</h2><div class="images">'
    for key, metric in metadata["caption_metrics"].items():
        body += f'<figure>{labels[key]}<img alt="{labels[key]} caption" src="captions/{metric["caption_file"]}"></figure>'
    body += '</div><h2>Posters</h2><ul>'
    for result in results:
        body += f'<li><a href="{result["id"]}/index.html">{html.escape(result["name"])}</a></li>'
        content = f'<a href="../index.html">All Playlist comparisons</a><h1>{html.escape(result["name"])}</h1>'
        for group in (("original", "neue", "kai"), ("original", "neue-adjusted", "kai-adjusted")):
            content += '<div class="images">'
            for key in group:
                image = result["images"][key]
                content += f'<figure>{labels[key]}<img alt="{labels[key]}" src="{image["report_file"]}"></figure>'
            content += '</div>'
        content += '<h2>Text Regions and Differences</h2>'
        for key, comparison in result["comparisons"].items():
            content += f'<h3>{labels[key]}</h3><div class="images">'
            for name in [*comparison["text_crops"], comparison["difference"]]:
                content += f'<figure><img alt="{html.escape(name)}" src="{name}"></figure>'
            content += '</div>'
        content += '<h2>Exact Parameters and Metrics</h2><pre>' + html.escape(json.dumps(result, indent=2)) + '</pre>'
        (report / result["id"] / "index.html").write_text(page(result["name"], content), encoding="utf-8")
    body += '</ul><h2>Methods and Provenance</h2><pre>' + html.escape(json.dumps(metadata, indent=2)) + '</pre>'
    (report / "index.html").write_text(page("Playlist Bebas Font Comparison", body), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates-dir", type=Path, default=ROOT.parent / "config/bebas-font-candidates")
    parser.add_argument("--fetch-candidates", action="store_true")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--original-font", type=Path, default=ROOT / "fonts/Bebas-Regular.ttf")
    parser.add_argument("--bulk-definition", type=Path, default=ROOT / "create_default_posters.ps1")
    parser.add_argument("--legacy-composer", type=Path, default=ROOT / "create_poster.ps1")
    parser.add_argument("--report-dir", type=Path, default=ROOT.parent / "config/bebas-replacement")
    parser.add_argument("--magick", default=shutil.which("magick"))
    parser.add_argument("--powershell", default=shutil.which("pwsh") or shutil.which("powershell"))
    args = parser.parse_args(argv)
    sources = candidate_sources(args.candidates_dir, args.fetch_candidates)
    if args.download_only:
        print(json.dumps(sources, indent=2))
        return 0
    if not args.magick or not args.powershell:
        parser.error("Existing local ImageMagick and PowerShell are required; neither is installed automatically")
    args.original_font = args.original_font.resolve(strict=True)
    args.legacy_composer = args.legacy_composer.resolve(strict=True)
    args.report_dir = args.report_dir.resolve()
    if args.report_dir.exists():
        parser.error("Use a fresh nonexistent report directory")
    cases = playlist_cases(bulk=args.bulk_definition)
    fonts = {"original": args.original_font, **{key: Path(source["files"][source["file"]]["path"]) for key, source in sources.items()}}
    protected = [args.legacy_composer, args.bulk_definition, *fonts.values(),
                 *(Path(c.parameters["logo"]) for c in cases), *(ROOT / "fades").glob("*.png")]
    before = {str(path): digest(path) for path in protected}
    args.report_dir.mkdir(parents=True)
    directory = args.report_dir / "captions"
    directory.mkdir()
    fits, metrics = compare_captions(args.magick, fonts, cases[0], directory)
    metadata = {"sources": sources, "original_font": {"path": str(fonts["original"]), "sha256": digest(fonts["original"])},
                "caption_metrics": metrics, "fit_parameters": fits, "source_hashes": before,
                "selection_method": "Minimize measured centered-caption alpha MAE over foreground union; compare existing fit and nearby width/height-derived point sizes. Full-poster MAE is secondary because logos dominate its area.",
                "limitations": "Nine English Playlist rows share the same TIMELINE ORDER text; this is not a multilingual acceptance certificate. Font metrics are unhinted exact advances; raster ink bounds and row bands are measured separately. Report is local only and contains rendered images, never the restricted font binary."}
    results = []
    old = os.environ.get("POSTER_COMPARISON_MAGICK")
    os.environ["POSTER_COMPARISON_MAGICK"] = str(args.magick)
    try:
        with tempfile.TemporaryDirectory(prefix=".legacy-", dir=args.report_dir) as temporary:
            workspace = Path(temporary)
            metadata["legacy_isolation"] = prepare_comparison_workspace(args, workspace, fonts)
            for index, case in enumerate(cases, 1):
                output = args.report_dir / case.id
                output.mkdir()
                result = {"id": case.id, "name": case.parameters["out_name"], "source_line": case.source_line,
                          "source_row": case.source_row, "images": {}, "parameters": {}, "comparisons": {}}
                for key, fitted in fits.items():
                    font_key = key.removesuffix("-adjusted")
                    parameters = dict(case.parameters, font=str(fonts[font_key]), font_size=fitted["parameters"]["font_size"])
                    alias = "Bebas-Regular" if key == "original" else CANDIDATES[font_key]["alias"]
                    result["parameters"][key] = parameters
                    result["images"][key] = legacy_poster(args, workspace, parameters, alias, output, key)
                    if key != "original":
                        result["comparisons"][key] = compare_images(output / "original.jpg", output / (key + ".jpg"), output, key, parameters["text_offset"])
                json_file(output / "result.json", result)
                results.append(result)
                print(f'[{index}/{len(cases)}] {result["name"]}', flush=True)
    finally:
        if old is None:
            os.environ.pop("POSTER_COMPARISON_MAGICK", None)
        else:
            os.environ["POSTER_COMPARISON_MAGICK"] = old
    for path, expected in before.items():
        if digest(path) != expected:
            raise RuntimeError(f"Protected comparison source changed: {path}")
    scores = {key: {"mean_poster_mae": sum(r["comparisons"][key]["mean_absolute_error_0_255"] for r in results) / len(results),
                    "foreground_caption_mae": metrics[key]["difference"]["foreground_alpha_mae_0_255"],
                    "point_size": metrics[key]["point_size"]} for key in fits if key != "original"}
    winner = min(scores, key=lambda key: scores[key]["foreground_caption_mae"])
    metadata.update(scores=scores, measured_closest=winner, case_count=len(results))
    json_file(args.report_dir / "summary.json", dict(metadata, results=results))
    write_report(args.report_dir, results, metadata)
    print(f'Report: {args.report_dir / "index.html"}; closest measured variant: {winner}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
