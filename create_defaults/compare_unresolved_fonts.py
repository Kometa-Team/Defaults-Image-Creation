"""Compare official licensed font candidates without changing distributable assets.

Downloads only the explicitly identified font data/notices, never software.
The old fonts are used locally as references; no approval or replacement is implied.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
from zipfile import ZipFile

from fontTools.ttLib import TTFont
import yaml

try:
    from .create_poster import ROOT, PosterOptions, digest, output_filename
    from .compare_poster_renderers import (caption_diagnostics, compare_images, effective_parameters,
                                          json_file, measured, page, picture_metadata, prepare_legacy)
    from .poster_fixtures import extract_rows, row_case, translation_file
    from .poster_text import FontLayout
except ImportError:
    from create_poster import ROOT, PosterOptions, digest, output_filename
    from compare_poster_renderers import (caption_diagnostics, compare_images, effective_parameters,
                                         json_file, measured, page, picture_metadata, prepare_legacy)
    from poster_fixtures import extract_rows, row_case, translation_file
    from poster_text import FontLayout


GOOGLE = "https://raw.githubusercontent.com/google/fonts/90abd17b4f97671435798b6147b698aa9087612f/ofl/monoton/"
BOECKLIN = "https://www.peter-wiegel.de/Fonts/BoecklinsUniverse.zip"
EXPECTED = {
    "BoecklinsUniverse.ttf": "f337d1e6e75f879f952017341c819d65df5c4b441d9bb188c104c94423832f16",
    "Monoton-Regular.ttf": "951c4cea65ffede784a7c9672feec5d329a7e1e12216c42d53ecf36c90d04dea",
}


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Kometa Phase 1 font provenance validation"})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read(10_000_001)
    if len(data) > 10_000_000:
        raise ValueError("Candidate download exceeds audit size bound")
    return data


def metadata(path):
    with TTFont(path) as font:
        return {"sha256": digest(path), "bytes": path.stat().st_size, "glyphs": font["maxp"].numGlyphs,
                "names": {str(identifier): sorted({record.toUnicode() for record in font["name"].names if record.nameID == identifier})
                          for identifier in (0, 1, 2, 3, 4, 5, 6, 8, 9, 11, 12, 13, 14)}}


def candidates(directory):
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / "BoecklinsUniverse.zip"
    if not archive.exists():
        archive.write_bytes(fetch(BOECKLIN))
    boecklin = directory / "BoecklinsUniverse"
    boecklin.mkdir(exist_ok=True)
    with ZipFile(BytesIO(archive.read_bytes())) as zipped:
        for member in zipped.infolist():
            if member.file_size > 10_000_000:
                raise ValueError("Candidate archive member exceeds audit bound")
            if member.filename.lower().endswith((".ttf", ".txt")):
                # Flat, selected data-only extraction prevents archive traversal.
                (boecklin / Path(member.filename).name).write_bytes(zipped.read(member))
    monoton = directory / "Monoton"
    monoton.mkdir(exist_ok=True)
    for name in ("Monoton-Regular.ttf", "OFL.txt"):
        target = monoton / name
        if not target.exists():
            target.write_bytes(fetch(GOOGLE + name))
    paths = {"BoecklinsUniverse.ttf": boecklin / "Boecklins Universe.ttf", "Monoton-Regular.ttf": monoton / "Monoton-Regular.ttf"}
    for name, path in paths.items():
        if digest(path) != EXPECTED[name]:
            raise ValueError("Official candidate release changed; explicit re-audit required")
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    args.report_dir = args.report_dir.resolve()
    if args.report_dir == ROOT or args.report_dir.is_relative_to(ROOT):
        parser.error("Report must be outside production assets")
    args.report_dir.mkdir(parents=True, exist_ok=True)
    if (args.report_dir / "results.json").exists():
        raise FileExistsError("Refusing to overwrite existing comparison results")
    magick, powershell = shutil.which("magick"), shutil.which("pwsh")
    if not magick or not powershell:
        parser.error("Existing ImageMagick and PowerShell required; nothing will be installed")
    paths = candidates(args.report_dir / "official-candidates")
    before = {name: digest(ROOT / "fonts" / name) for name in paths}
    workspace = args.report_dir / "scratch"
    prepare_legacy(ROOT / "create_poster.ps1", workspace, ROOT, magick)
    legacy_source = (workspace / "legacy.ps1").read_text(encoding="utf-8-sig")
    os.environ["POSTER_COMPARISON_MAGICK"] = magick
    translations = yaml.safe_load(translation_file().read_text(encoding="utf-8-sig"))
    rows = [item for item in extract_rows() if item["row"]["font"].replace("-", "").replace(" ", "").lower() in {"boecklinsuniverse", "monoton", "monotonregular"}]
    if len(rows) != 22:
        raise ValueError("Expected 11 Boecklins Universe and 11 Monoton definitions")
    results = []
    import html
    content = '<h1>Unresolved Font Release Comparisons</h1><p>Original locally bundled font versus official licensed candidate, both rendered by the unchanged PowerShell/ImageMagick body. Neither candidate is installed or approved.</p>'
    for index, item in enumerate(rows):
        case = row_case(item, translations, ROOT)
        name = "BoecklinsUniverse.ttf" if "boeck" in case.parameters["font"].lower() else "Monoton-Regular.ttf"
        directory = args.report_dir / case.id
        directory.mkdir()
        result = {"id": case.id, "category": case.category, "definition_line": item["line"], "text": case.parameters["text"],
                  "original": metadata(ROOT / "fonts" / name), "candidate": metadata(paths[name]), "variants": {}}
        for label, font in (("original", ROOT / "fonts" / name), ("candidate", paths[name])):
            variant = replace(case, parameters={**case.parameters, "font": str(font)})
            parameters, fit = effective_parameters(variant, magick, ROOT)
            # Legacy resolver selects bundled filename: use a private workspace copy of the exact variant.
            shutil.copyfile(font, workspace / "fonts" / font.name)
            # Candidate keeps its official filename. Redirect only the isolated harness alias.
            isolated = legacy_source
            if label == "candidate" and name == "BoecklinsUniverse.ttf":
                if isolated.count('"BoecklinsUniverse.ttf"') != 1:
                    raise ValueError("Reference font alias changed; re-audit isolation")
                isolated = isolated.replace('"BoecklinsUniverse.ttf"', '"Boecklins Universe.ttf"')
            (workspace / "legacy.ps1").write_text(isolated, encoding="utf-8-sig")
            resolved = workspace / "fonts" / font.name
            if digest(resolved) != digest(font):
                raise ValueError("Private reference font does not match requested release")
            values = {key: value for key, value in parameters.items() if value is not None}
            for key in ("logo_offset", "text_offset"):
                values[key] = f'{int(values.get(key, 0)):+d}'
            json_file(workspace / "parameters.json", values)
            target = workspace / "output" / output_filename(PosterOptions(**parameters), parameters["base_color"])
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target.unlink()
            measurement = measured([powershell, "-NoLogo", "-NoProfile", "-File", workspace / "run.ps1", "-ParameterFile", workspace / "parameters.json"], workspace, directory / f"{label}.log")
            if measurement["returncode"] or not target.is_file():
                raise RuntimeError(f"{case.id} {label} failed; see log")
            log_text = (directory / f"{label}.log").read_text(encoding="utf-8-sig", errors="replace")
            if str(resolved) not in log_text or "randomly selected" in log_text.lower() or "[ERROR]" in log_text:
                raise RuntimeError("Reference font resolution did not use the verified private candidate")
            shutil.move(target, directory / f"{label}.jpg")
            diagnostic_dir = directory / label
            diagnostic_dir.mkdir()
            diagnostics = caption_diagnostics(parameters, font, diagnostic_dir, magick)
            fixed_caption, fixed_metrics = FontLayout(font).caption(parameters["text"], int(case.parameters["font_size"]), "#FFFFFF")
            fixed_metrics["centered_ink_bounds"] = fixed_caption.getchannel("A").getbbox()
            result["variants"][label] = {"parameters": parameters, "fit": fit, "caption": diagnostics,
                                         "isolated_font_sha256": digest(resolved), "isolated_reference_sha256": digest(workspace / "legacy.ps1"),
                                         "fixed_definition_size_metrics": fixed_metrics, "render": measurement,
                                         "image": picture_metadata(directory / f"{label}.jpg")}
        result["comparison"] = compare_images(directory / "original.jpg", directory / "candidate.jpg", directory, "original-candidate", case.parameters.get("text_offset", 0))
        json_file(directory / "result.json", result)
        content += f'<h2>{html.escape(case.id)}: {html.escape(result["text"])}</h2><div class="images">'
        for label in ("original", "candidate"):
            content += f'<figure><figcaption>{label}</figcaption><a href="{case.id}/{label}.jpg"><img loading="lazy" src="{case.id}/{label}.jpg" alt="{label} poster"></a></figure>'
        content += f'<figure><figcaption>Difference, amplified</figcaption><img loading="lazy" src="{case.id}/original-candidate-difference.png" alt="Difference"></figure></div>'
        content += '<pre>' + html.escape(json.dumps({"comparison": result["comparison"], "variants": result["variants"]}, indent=2)) + '</pre>'
        results.append(result)
        json_file(args.report_dir / "results.json", results)
        (args.report_dir / "index.html").write_text(page("Official Font Candidates", content), encoding="utf-8")
        print(f'[{index + 1}/{len(rows)}] {case.id}: MAE={result["comparison"]["mean_absolute_error_0_255"]:.6f}', flush=True)
    if before != {name: digest(ROOT / "fonts" / name) for name in paths}:
        raise RuntimeError("Original font assets changed")
    print(f"Compared {len(results)} definitions; original assets unchanged; neither candidate approved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
