"""Verify the approved 409-point Jakarta configuration against its local preview."""

from __future__ import annotations

import argparse
import html
import os
from pathlib import Path
import shutil
import json
import tempfile
from types import SimpleNamespace

from fontTools.ttLib import TTFont

try:
    from .create_poster import ROOT, digest
    from .compare_helvetica_fonts import affected_cases
    from .compare_bebas_fonts import legacy_poster
    from .compare_poster_renderers import effective_parameters, json_file, page, prepare_legacy
    from .poster_fixtures import extract_rows
except ImportError:
    from create_poster import ROOT, digest
    from compare_helvetica_fonts import affected_cases
    from compare_bebas_fonts import legacy_poster
    from compare_poster_renderers import effective_parameters, json_file, page, prepare_legacy
    from poster_fixtures import extract_rows


COMMIT = "18d1cd2f7ea10481919d2f05c1f7064b7307fc26"
FILES = {
    "PlusJakartaSans-Bold.ttf": "5f5342ef76862b5b5365d1dff1a667629dfa484e388dd602552f647219c3870f",
    "OFL.txt": "995c7199cab65954f545996326755daee7b63cc6b42b06c13da1f9502ab08a99",
    "AUTHORS.txt": "f0c3c74aa9a6492c12aa4d123aa09b839d401a1c119ae5647c51b903c7ba9f9e",
    "FONTLOG.txt": "cda8d5ef4355efcfd1033dc629e6417e596f1aeeccc0f417cd4922b908d376d4",
    "README.md": "e82e0f694ee93c8ae0d47f87d3221a9ad94d271c05c3d39695df13d058cfc901",
}


def verify_candidate(font_dir, notice_dir):
    for name, checksum in FILES.items():
        path = Path(font_dir if name.endswith(".ttf") else notice_dir) / name
        if digest(path) != checksum:
            raise ValueError(f"Official Jakarta asset hash differs: {name}")
    with TTFont(Path(font_dir) / "PlusJakartaSans-Bold.ttf") as font:
        names = lambda identifier: sorted({n.toUnicode() for n in font["name"].names if n.nameID == identifier})
        metadata = {"family": names(1), "style": names(2), "full_name": names(4),
                    "version": names(5), "character_count": len(font.getBestCmap())}
        if (metadata["family"] != ["Plus Jakarta Sans"] or metadata["style"] != ["Bold"]
                or not metadata["version"][0].startswith("Version 2.071;")):
            raise ValueError("Expected the reviewed unmodified Jakarta Bold 2.071 face")
    return metadata


def verify_source_scope(previous):
    before, after = extract_rows(previous), extract_rows()
    if len(before) != len(after) or len(after) != 3352:
        raise ValueError("Source row inventory changed")
    changed = 0
    for old, new in zip(before, after):
        expected = old["row"]
        if expected["font"] in {"Helvetica-Bold", "Liberation Sans Bold"}:
            expected = dict(expected, font="Plus Jakarta Sans Bold", font_size="409")
            changed += 1
        if new["row"] != expected or new["category"] != old["category"] or new["fit"] != old["fit"]:
            raise ValueError("Change outside the 11 approved font/size fields")
    if changed != 11:
        raise ValueError("Expected exactly 11 approved replacements")
    return len(after) - changed


def verify_preview(report):
    summary = json.loads((Path(report) / "summary.json").read_text())
    if len(summary["results"]) != 11:
        raise ValueError("Expected all 11 approved previews")
    for result in summary["results"]:
        image = result["images"]["jakarta-height"]
        if (result["captions"]["jakarta-height"]["point_size"] != 409
                or digest(Path(report) / result["id"] / image["report_file"]) != image["sha256"]):
            raise ValueError("Approved preview changed")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview-report", type=Path, required=True)
    parser.add_argument("--previous-bulk", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    metadata = verify_candidate(ROOT / "fonts", ROOT / "fonts/licenses/PlusJakartaSans")
    unchanged = verify_source_scope(args.previous_bulk)
    preview = verify_preview(args.preview_report)
    cases = affected_cases(ROOT / "create_default_posters.ps1")
    runtime = SimpleNamespace(magick=shutil.which("magick"), powershell=shutil.which("pwsh"))
    if not runtime.magick or not runtime.powershell:
        parser.error("ImageMagick and PowerShell 7 are required")
    args.report_dir = args.report_dir.resolve()
    args.report_dir.mkdir(parents=True, exist_ok=False)
    sources = [ROOT / "create_default_posters.ps1", ROOT / "create_poster.ps1", ROOT / "fonts/PlusJakartaSans-Bold.ttf"]
    protected = {path: digest(path) for path in sources}
    summary = {"approved_on": "2026-10-16", "fixed_point_size": 409, "metadata": metadata,
               "unchanged_other_rows": unchanged, "source_hashes": {str(p): h for p, h in protected.items()}, "results": []}
    previous = os.environ.get("POSTER_COMPARISON_MAGICK")
    os.environ["POSTER_COMPARISON_MAGICK"] = runtime.magick
    try:
        with tempfile.TemporaryDirectory(prefix=".legacy-", dir=args.report_dir) as temporary:
            workspace = Path(temporary)
            summary["isolation"] = prepare_legacy(ROOT / "create_poster.ps1", workspace, ROOT, runtime.magick)
            for case, reference in zip(cases, preview["results"]):
                if case.parameters["text"] != reference["name"] or case.fit is not None:
                    raise ValueError("Approved fixed-size dataset changed")
                parameters, fit = effective_parameters(case, runtime.magick, ROOT)
                if parameters["font_size"] != 409 or fit is not None:
                    raise ValueError("409-point approval was replaced by auto-fitting")
                directory = args.report_dir / case.id
                directory.mkdir()
                image = legacy_poster(runtime, workspace, parameters, "Plus Jakarta Sans Bold", directory, "installed")
                approved = reference["images"]["jakarta-height"]
                if image["sha256"] != approved["sha256"]:
                    raise ValueError(f"Updated configuration differs from approved preview: {reference['name']}")
                shutil.copyfile(args.preview_report / reference["id"] / approved["report_file"], directory / "approved.jpg")
                content = '<a href="../index.html">All verified posters</a><h1>' + html.escape(reference["name"]) + '</h1><div class="images">'
                for filename, label in (("approved.jpg", "Approved 409-point preview"), ("installed.jpg", "Updated configuration")):
                    content += f'<figure><figcaption>{label}</figcaption><img src="{filename}" alt="{label}"></figure>'
                (directory / "index.html").write_text(page(reference["name"], content + '</div>'), encoding="utf-8")
                summary["results"].append({"id": case.id, "name": reference["name"], "sha256": image["sha256"],
                                            "matches_approved_preview": True, "point_size": 409})
                print("Verified approved preview:", reference["name"], flush=True)
    finally:
        if previous is None:
            os.environ.pop("POSTER_COMPARISON_MAGICK", None)
        else:
            os.environ["POSTER_COMPARISON_MAGICK"] = previous
    for path, checksum in protected.items():
        if digest(path) != checksum:
            raise ValueError(f"Verification source changed: {path}")
    json_file(args.report_dir / "summary.json", summary)
    body = '<h1>Approved Jakarta Configuration</h1><p>All 11 updated outputs match their approved 409-point previews byte-for-byte.</p><ul>'
    body += ''.join(f'<li><a href="{r["id"]}/index.html">{r["name"]}</a></li>' for r in summary["results"])
    body += '</ul><div class="images"><figure><img src="' + summary["results"][2]["id"] + '/installed.jpg" alt="Verified 2021 poster"></figure></div>'
    (args.report_dir / "index.html").write_text(page("Approved Jakarta", body), encoding="utf-8")
    print("Report:", args.report_dir / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
