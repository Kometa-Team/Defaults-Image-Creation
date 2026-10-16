"""Rerender all nine current Playlist jobs against their approved local hashes."""

import argparse
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace

try:
    from .compare_bebas_fonts import legacy_poster, playlist_cases
    from .compare_poster_renderers import effective_parameters, json_file, prepare_legacy
    from .create_poster import ROOT, digest
except ImportError:
    from compare_bebas_fonts import legacy_poster, playlist_cases
    from compare_poster_renderers import effective_parameters, json_file, prepare_legacy
    from create_poster import ROOT, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved", required=True, type=Path)
    parser.add_argument("--report-dir", required=True, type=Path)
    args = parser.parse_args()
    reference = json.loads(args.approved.read_text())
    approved = {row["name"]: row["sha256"] for row in reference["records"]}
    cases = playlist_cases()
    if len(cases) != len(approved) or len(cases) != 9:
        raise ValueError("Approved nine-Playlist dataset changed")
    args.report_dir = args.report_dir.resolve()
    if args.report_dir == ROOT or args.report_dir.is_relative_to(ROOT):
        raise ValueError("Report must be outside production assets")
    args.report_dir.mkdir(parents=True, exist_ok=False)
    runtime = SimpleNamespace(magick=shutil.which("magick"), powershell=shutil.which("pwsh"))
    if not runtime.magick or not runtime.powershell:
        raise ValueError("Existing PowerShell 7 and ImageMagick required")
    os.environ["POSTER_COMPARISON_MAGICK"] = runtime.magick
    workspace = args.report_dir / "scratch"
    prepare_legacy(ROOT / "create_poster.ps1", workspace, ROOT, runtime.magick)
    before = {name: digest(ROOT / name) for name in ("create_poster.ps1", "create_default_posters.ps1", "fonts/BebasNeue-Regular.ttf")}
    results = []
    for case in cases:
        parameters, fit = effective_parameters(case, runtime.magick, ROOT)
        if case.fit[-1] != 154 or parameters["font_size"] != 154:
            raise ValueError("Approved Bebas Neue fitting changed")
        directory = args.report_dir / case.id
        directory.mkdir()
        image = legacy_poster(runtime, workspace, parameters, "Bebas Neue", directory, "installed")
        name = parameters["out_name"]
        if image["sha256"] != approved[name]:
            raise ValueError(f"Playlist differs from approved preview: {name}")
        results.append({"id": case.id, "name": name, "point_size": 154, "fit": fit, "sha256": image["sha256"], "matches_approved": True})
        print("Verified approved Playlist:", name, flush=True)
    for name, checksum in before.items():
        if digest(ROOT / name) != checksum:
            raise ValueError("Source changed during verification")
    json_file(args.report_dir / "summary.json", {"results": results, "source_hashes": before})


if __name__ == "__main__":
    main()
