#!/usr/bin/env python3
"""Verify imported transparent names have matching local original files."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"
load_dotenv(CONFIG_DIR / ".env")
DEFAULT_IMPORT_ROOT = Path(os.getenv("PEOPLE_IMPORT_DIR") or (CONFIG_DIR / "people_dirs"))
DEFAULT_ORIGINAL_ROOT = SCRIPT_DIR / "config" / "people_dirs" / "original"


def image_stems(root: Path) -> set[str]:
    stems: set[str] = set()
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"} and path.parent.name.lower() == "images":
            stems.add(path.stem)
    return stems


def image_paths_by_stem(root: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"} and path.parent.name.lower() == "images":
            paths[path.stem] = path
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import-root", type=Path, default=DEFAULT_IMPORT_ROOT)
    parser.add_argument("--style", default="transparent")
    parser.add_argument("--original-root", type=Path, default=DEFAULT_ORIGINAL_ROOT)
    args = parser.parse_args()

    imported = image_stems(args.import_root / args.style)
    original_paths = image_paths_by_stem(args.original_root)
    originals = set(original_paths)
    missing = sorted(imported - originals)
    dimension_issues: list[tuple[str, int, int, Path]] = []
    for name in sorted(imported & originals):
        path = original_paths[name]
        with Image.open(path) as img:
            width, height = img.size
        if (width, height) != (2000, 3000):
            dimension_issues.append((name, width, height, path))

    print(f"Imported {args.style} names: {len(imported)}")
    print(f"Matching local original names: {len(imported & originals)}")
    print(f"Missing originals from import set: {len(missing)}")
    print(f"Original dimension issues: {len(dimension_issues)}")
    for name in missing:
        print(f"MISSING {name}")
    for name, width, height, path in dimension_issues:
        print(f"DIMENSION {name}: {width}x{height} {path}")
    return 0 if not missing and not dimension_issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
