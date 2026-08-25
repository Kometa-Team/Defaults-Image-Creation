#!/usr/bin/env python3
"""Normalize imported original images to the repo-standard 2000x3000 JPG."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageOps


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"
load_dotenv(CONFIG_DIR / ".env")
DEFAULT_IMPORT_ROOT = Path(os.getenv("PEOPLE_IMPORT_DIR") or (CONFIG_DIR / "people_dirs"))
DEFAULT_ORIGINAL_ROOT = SCRIPT_DIR / "config" / "people_dirs" / "original"
TARGET_SIZE = (2000, 3000)


def image_stems(root: Path) -> set[str]:
    stems: set[str] = set()
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"} and path.parent.name.lower() == "images":
            stems.add(path.stem)
    return stems


def original_paths_by_stem(root: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg"} and path.parent.name.lower() == "images":
            paths[path.stem] = path
    return paths


def normalize(path: Path) -> tuple[int, int]:
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        old_size = img.size
        normalized = ImageOps.fit(img.convert("RGB"), TARGET_SIZE, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        normalized.save(path, "JPEG", quality=95, subsampling=0, optimize=True)
    return old_size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import-root", type=Path, default=DEFAULT_IMPORT_ROOT)
    parser.add_argument("--style", default="transparent")
    parser.add_argument("--original-root", type=Path, default=DEFAULT_ORIGINAL_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    imported = image_stems(args.import_root / args.style)
    originals = original_paths_by_stem(args.original_root)
    missing = sorted(imported - set(originals))
    if missing:
        for name in missing:
            print(f"MISSING {name}")
        return 1

    changed = 0
    already_ok = 0
    for name in sorted(imported):
        path = originals[name]
        with Image.open(path) as img:
            current_size = img.size
        if current_size == TARGET_SIZE:
            already_ok += 1
            print(f"OK {name}: {current_size[0]}x{current_size[1]}")
            continue
        changed += 1
        if args.dry_run:
            print(f"WOULD NORMALIZE {name}: {current_size[0]}x{current_size[1]} -> 2000x3000")
        else:
            old_w, old_h = normalize(path)
            print(f"NORMALIZED {name}: {old_w}x{old_h} -> 2000x3000")

    print(f"Imported names: {len(imported)}")
    print(f"Already 2000x3000: {already_ok}")
    print(f"Normalized: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
