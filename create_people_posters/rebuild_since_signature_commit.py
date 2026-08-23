#!/usr/bin/env python3
"""
Build a rerender list for people posters affected by the bad signature-font window.

The source of truth is the signature repo history: collect every JPG added from
the Christian Gudegast boundary commit through HEAD, then map those names to the
matching transparent PNG source. By default this is a dry run.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"
PEOPLE_DIRS = CONFIG_DIR / "people_dirs"
DOWNLOADS_DIR = PEOPLE_DIRS / "Downloads"

DEFAULT_BOUNDARY = "c2c1138c8d6dc1b775a0f44b27180a7cedeb6816"
REBUILD_STYLES = ("bw", "rainier", "signature", "diiivoy", "diiivoycolor")


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


def resolve_repo_root(cli_value: str | None) -> Path:
    if cli_value:
        return Path(cli_value).expanduser().resolve()

    env = read_env_file(CONFIG_DIR / ".env")
    value = os.getenv("PEOPLE_IMAGES_DIR") or env.get("PEOPLE_IMAGES_DIR")
    if not value:
        raise SystemExit("PEOPLE_IMAGES_DIR is not set. Pass --repo-root or set it in config/.env.")
    return Path(value).expanduser().resolve()


def run_git(repo: Path, *args: str) -> bytes:
    cmd = ["git", "-C", str(repo), "-c", "core.quotepath=false", *args]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git failed in {repo}: {' '.join(args)}\n{stderr}")
    return result.stdout


def collect_signature_adds(signature_repo: Path, boundary: str) -> list[tuple[str, str]]:
    range_spec = f"{boundary}^..HEAD"
    output = run_git(
        signature_repo,
        "log",
        "--format=",
        "--name-only",
        "-z",
        "--diff-filter=A",
        range_spec,
        "--",
        "*.jpg",
    )

    seen: set[str] = set()
    rows: list[tuple[str, str]] = []
    for raw in output.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", errors="replace").replace("\\", "/")
        path = PurePosixPath(rel)
        if path.name.lower() == "grid.jpg":
            continue
        if path.suffix.lower() != ".jpg" or len(path.parts) < 3 or path.parts[-2] != "Images":
            continue
        name = path.stem
        if name in seen:
            continue
        seen.add(name)
        rows.append((name, rel))

    return sorted(rows, key=lambda row: row[0].casefold())


def write_outputs(rows: list[tuple[str, str]], repo_root: Path, out_prefix: Path) -> tuple[Path, Path]:
    txt_path = out_prefix.with_suffix(".txt")
    csv_path = out_prefix.with_suffix(".csv")
    transparent_repo = repo_root / "transparent"

    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text("\n".join(name for name, _ in rows) + "\n", encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["name", "signature_relpath", "transparent_relpath", "transparent_source_exists"])
        for name, signature_rel in rows:
            transparent_rel = str(PurePosixPath(signature_rel).with_suffix(".png"))
            writer.writerow([name, signature_rel, transparent_rel, (transparent_repo / transparent_rel).exists()])

    return txt_path, csv_path


def missing_sources(rows: list[tuple[str, str]], repo_root: Path) -> list[Path]:
    transparent_repo = repo_root / "transparent"
    missing: list[Path] = []
    for _, signature_rel in rows:
        src_rel = str(PurePosixPath(signature_rel).with_suffix(".png"))
        src = transparent_repo / src_rel
        if not src.exists():
            missing.append(src)
    return missing


def stage_downloads(rows: list[tuple[str, str]], repo_root: Path, allow_missing: bool) -> int:
    missing = missing_sources(rows, repo_root)
    if missing and not allow_missing:
        sample = "\n".join(str(path) for path in missing[:20])
        raise SystemExit(
            f"Refusing to stage because {len(missing)} transparent source PNG(s) are missing.\n"
            f"First missing paths:\n{sample}\n"
            "Use --allow-missing to stage the files that do exist."
        )

    transparent_repo = repo_root / "transparent"
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    for _, signature_rel in rows:
        src_rel = str(PurePosixPath(signature_rel).with_suffix(".png"))
        src = transparent_repo / src_rel
        if not src.exists():
            continue
        shutil.copy2(src, DOWNLOADS_DIR / src.name)
        copied += 1
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect and optionally stage people posters to rerender.")
    parser.add_argument("--repo-root", help="Kometa-People-Images root. Defaults to PEOPLE_IMAGES_DIR.")
    parser.add_argument("--boundary", default=DEFAULT_BOUNDARY, help="Inclusive signature commit to rebuild from.")
    parser.add_argument(
        "--out-prefix",
        default=str(CONFIG_DIR / "rebuild_since_signature_commit"),
        help="Output prefix for .txt and .csv review files.",
    )
    parser.add_argument("--stage", action="store_true", help="Copy matching transparent PNGs into people_dirs/Downloads.")
    parser.add_argument("--allow-missing", action="store_true", help="Stage existing sources even if some PNGs are missing.")
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    signature_repo = repo_root / "signature"
    if not signature_repo.exists():
        raise SystemExit(f"Signature repo not found: {signature_repo}")

    rows = collect_signature_adds(signature_repo, args.boundary)
    txt_path, csv_path = write_outputs(rows, repo_root, Path(args.out_prefix))
    missing = missing_sources(rows, repo_root)

    print(f"Boundary commit        : {args.boundary}")
    print(f"People images root     : {repo_root}")
    print(f"Styles to recreate     : {', '.join(REBUILD_STYLES)}")
    print(f"Names collected        : {len(rows)}")
    print(f"Missing transparent PNG: {len(missing)}")
    print(f"Names file             : {txt_path}")
    print(f"CSV file               : {csv_path}")

    if missing:
        print("First missing source(s):")
        for path in missing[:20]:
            print(f"  {path}")

    if args.stage:
        copied = stage_downloads(rows, repo_root, args.allow_missing)
        print(f"Staged PNGs            : {copied}")
        print(f"Downloads dir          : {DOWNLOADS_DIR}")
        print("Next command           : powershell.exe -NoProfile -ExecutionPolicy Bypass -File create_people_posters\\create_people_poster.ps1")
    else:
        print("Dry run only. Re-run with --stage to copy transparent PNGs into Downloads.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
