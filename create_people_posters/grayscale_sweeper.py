#!/usr/bin/env python3
"""
collect_noncolor_to_other.py — Find grayscale / non-color images under a tree and
copy/move them into ./config/Downloads/other for colorization.

Default behavior:
  - Recurses from --src
  - Detects non-color using a strict channel-equality check (PIL)
  - Copies (not moves) into ./config/Downloads/other
  - Skips files already in the destination
  - Avoids recursing inside ./config/Downloads/{other,color}

CLI:
  python collect_noncolor_to_other.py --src D:\path\to\scan
Options:
  --dest-other PATH     Destination folder (default: ./config/Downloads/other)
  --move                Move instead of copy
  --overwrite           Overwrite if the filename exists in dest
  --exts jpg,jpeg,png,webp,bmp,tif,tiff   Extensions to scan
  --method exact|sat    exact = strict RGB-equality (default), sat = low-saturation heuristic
  --sat-threshold 8     0-255 threshold for --method sat (default: 8)

Requires: Pillow, alive-progress
"""

import os
import sys
import shutil
import logging
from pathlib import Path
from typing import Iterable, Tuple
from timeit import default_timer as timer

from PIL import Image, ImageChops
import numpy as np
from alive_progress import alive_bar

# ---------- paths & logging ----------
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
DEFAULT_DEST = CONFIG_DIR / "Downloads" / "other"
DEFAULT_EXCLUDE = { (CONFIG_DIR / "Downloads" / "other").resolve(),
                    (CONFIG_DIR / "Downloads" / "color").resolve() }

for d in (CONFIG_DIR, LOGS_DIR, DEFAULT_DEST):
    d.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOGS_DIR / f"{SCRIPT_PATH.stem}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8", mode="w")],
    force=True,
)
logging.getLogger("PIL").setLevel(logging.ERROR)


# ---------- detection ----------
def is_grayscale_exact(img: Image.Image) -> bool:
    """True if the image has no color (all RGB channels equal)."""
    if img.mode in ("1", "L", "LA"):
        return True
    rgb = img.convert("RGB")
    r, g, b = rgb.split()
    # If r==g and g==b everywhere -> no color
    return (ImageChops.difference(r, g).getbbox() is None and
            ImageChops.difference(g, b).getbbox() is None)

def is_low_saturation(img: Image.Image, s_thresh: int = 8) -> bool:
    """
    Heuristic: consider non-color if the great majority of pixels have very low saturation.
    s_thresh is 0..255 (HSV S channel). Default ~8 keeps this conservative.
    """
    hsv = img.convert("RGB").convert("HSV")
    s = hsv.split()[1]
    # Fast count: build histogram of S and sum below threshold
    hist = s.histogram()  # 256 bins
    below = sum(hist[:max(0, min(255, s_thresh)) + 1])
    total = s.size[0] * s.size[1]
    return (below / max(1, total)) >= 0.98  # 98%+ of pixels near gray


# ---------- FS helpers ----------
def iter_images(root: Path, exts: set[str], exclude_dirs: set[Path]) -> Iterable[Path]:
    root = root.resolve()
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower().lstrip(".") not in exts:
            continue
        # Skip files inside excluded directories
        try:
            if any(ex in p.resolve().parents for ex in exclude_dirs):
                continue
        except Exception:
            pass
        yield p

def unique_dest(dest_dir: Path, name: str) -> Path:
    """
    Return a non-colliding path under dest_dir, appending _1, _2, ... if needed.
    """
    base = dest_dir / name
    if not base.exists():
        return base
    stem, ext = Path(name).stem, Path(name).suffix
    i = 1
    while True:
        candidate = dest_dir / f"{stem}_{i}{ext}"
        if not candidate.exists():
            return candidate
        i += 1


# ---------- main ----------
def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Collect non-color images into ./config/Downloads/other")
    parser.add_argument("--src", required=True, help="Root directory to scan (recursive)")
    parser.add_argument("--dest-other", default=str(DEFAULT_DEST), help="Destination folder for non-color images")
    parser.add_argument("--move", action="store_true", help="Move instead of copy")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite files that already exist in dest")
    parser.add_argument("--exts", default="jpg,jpeg,png,webp,bmp,tif,tiff", help="Comma list of extensions to scan")
    parser.add_argument("--method", choices=("exact","sat","satq","colorfulness","auto"), default="exact",
                        help="Detection method: exact (RGB equality) or sat (low-saturation heuristic)")
    parser.add_argument("--sat-threshold", type=int, default=8, help="Saturation threshold (0-255) 
parser.add_argument("--sat-quantile", type=float, default=0.95, help="Quantile for satq (0<q<=1).")
for --method sat")
    
parser.add_argument("--colorfulness-cutoff", type=float, default=12.0, help="Cutoff for colorfulness (lower is stricter).")
args = parser.parse_args()

    src_root = Path(args.src).expanduser().resolve()
    dest_dir = Path(args.dest_other).expanduser().resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    if not src_root.exists():
        print(f"Source not found: {src_root}")
        sys.exit(1)

    exts = {e.strip().lower() for e in args.exts.split(",") if e.strip()}
    exclude_dirs = set(DEFAULT_EXCLUDE)
    exclude_dirs.add(dest_dir.resolve())

    logging.info("#### START ####")
    logging.info("script               : %s", SCRIPT_PATH.name)
    logging.info("src_root             : %s", src_root)
    logging.info("dest_other           : %s", dest_dir)
    logging.info("method               : %s", args.method)
    logging.info("sat_threshold        : %s", args.sat_threshold if args.method == "sat" else "-")
    logging.info("move                 : %s", args.move)
    logging.info("overwrite            : %s", args.overwrite)
    logging.info("extensions           : %s", ", ".join(sorted(exts)))
    logging.info("log                  : %s", LOG_FILE)

    files = list(iter_images(src_root, exts, exclude_dirs))
    total = len(files)
    print(f"Scanning {total} image(s) under {src_root}")

    scanned = 0
    noncolor = 0
    copied = 0
    skipped_exists = 0
    errors = 0

    with alive_bar(total or 1, title="Collect non-color", dual_line=False, stats=False) as bar:
        for fp in files:
            try:
                with Image.open(fp) as img:
                    img.load()  # ensure it actually decodes
                    if args.method == "exact":
                        is_nc = is_grayscale_exact(img)

        if args.method in ("satq", "colorfulness", "auto"):
            try:
                if args.method == "satq":
                    is_nc = is_near_grayscale_sat_quantile(img, args.sat_threshold, args.sat_quantile)
                elif args.method == "colorfulness":
                    is_nc = is_near_grayscale_colorfulness(img, args.colorfulness_cutoff)
                else:  # auto
                    if is_grayscale_exact(img):
                        is_nc = True
                    else:
                        is_nc = (is_near_grayscale_sat_quantile(img, max(getattr(args, "sat_threshold", 35), 35), args.sat_quantile)
                                 or is_near_grayscale_colorfulness(img, args.colorfulness_cutoff))
            except Exception:
                pass
                    else:
                        is_nc = is_low_saturation(img, args.sat_threshold)
                if is_nc:
                    noncolor += 1
                    dest_name = fp.name  # keep original filename
                    target = dest_dir / dest_name
                    if target.exists() and not args.overwrite:
                        logging.info("Skip (already in dest): %s", target.name)
                        skipped_exists += 1
                        continue
                    if args.move:
                        shutil.move(str(fp), str(target))
                    else:
                        shutil.copy2(str(fp), str(target))
                    copied += 1
            except Exception as e:
                logging.warning("Failed on %s — %s", fp, e)
                errors += 1
            finally:
                scanned += 1
                bar()

    logging.info("Processed files       : %d", scanned)
    logging.info("Detected non-color    : %d", noncolor)
    logging.info("Placed into 'other'   : %d", copied)
    logging.info("Name collisions       : %d", skipped_exists)
    logging.info("Errors                : %d", errors)
    logging.info("#### END ####")

    print("\n=== SUMMARY ===")
    print(f"Scanned: {scanned} | Non-color found: {noncolor} | Placed: {copied} | Collisions: {skipped_exists} | Errors: {errors}")
    print(f"Details in log → {LOG_FILE}")



def is_near_grayscale_sat_quantile(img, sat_threshold: int = 35, q: float = 0.95) -> bool:
    """
    Robust near-grayscale test: image is non-color if the q-quantile of HSV S is <= threshold.
    sat_threshold: 0..255, q in (0,1] (e.g., 0.95 = 95th percentile)
    """
    if not (0 < q <= 1):
        raise ValueError("sat quantile q must be in (0,1].")
    s = np.asarray(img.convert("HSV"))[..., 1].astype(np.uint8)  # 0..255
    return np.quantile(s, q) <= sat_threshold


def _colorfulness_score(img) -> float:
    """
    Hasler–Süsstrunk colorfulness score.
    Grayscale/near-grayscale images are typically < ~10–15.
    """
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    R, G, B = arr[..., 0], arr[..., 1], arr[..., 2]
    rg = R - G
    yb = 0.5 * (R + G) - B
    std_rg, std_yb = rg.std(), yb.std()
    mean_rg, mean_yb = np.abs(rg).mean(), np.abs(yb).mean()
    return float(np.hypot(std_rg, std_yb) + 0.3 * np.hypot(mean_rg, mean_yb))


def is_near_grayscale_colorfulness(img, cutoff: float = 12.0) -> bool:
    """Scene-level check: image is non-color if colorfulness < cutoff."""
    return _colorfulness_score(img) < cutoff
if __name__ == "__main__":
    main()
