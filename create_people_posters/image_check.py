#!/usr/bin/env python3
# image_check.py — Pillow + quiet console + failure-only logs + proper summary
# v2.2

import sys
import os
import logging
from pathlib import Path
from timeit import default_timer as timer
from typing import Dict, Tuple

from dotenv import load_dotenv
from PIL import Image, ImageChops, ImageStat
from alive_progress import alive_bar

# ========= PATHS & LOGGING =========
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
for d in (CONFIG_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)


def setup_logging():
    """
    File-only logger (no console handler). We capture DEBUG+ to file so
    warnings and summary always land in the log. Console stays clean.
    """
    log_file = LOGS_DIR / f"{SCRIPT_PATH.stem}.log"
    handlers = [logging.FileHandler(log_file, encoding="utf-8", mode="w")]
    logging.basicConfig(
        level=logging.DEBUG,  # capture everything to file
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
        force=True,  # reset any prior config
    )
    logging.info("Logging → %s", log_file)
    return log_file


LOG_FILE = setup_logging()
load_dotenv(SCRIPT_DIR / ".env")  # harmless if missing

# ========= CONFIG =========
# (kept identical to your PowerShell checks)
REQUIRED_WIDTH = 2000
REQUIRED_HEIGHT = 3000
BASE_IMAGE_RATIO = round(1 / 1.5, 4)  # 0.6667
BASE_W_QUALITY = 399
BASE_H_QUALITY = 599


# ========= END CONFIG =====

# ---------- Pillow helpers ----------
def open_image(path: Path) -> Image.Image:
    return Image.open(path)


def get_dimensions(img: Image.Image) -> Tuple[int, int]:
    return img.size


def is_grayscale(img: Image.Image) -> bool:
    # Equivalent to IM 'Type: Gray'
    mode = img.mode
    if mode in ("1", "L", "LA"):
        return True
    rgb = img.convert("RGB")
    r, g, b = rgb.split()
    return (ImageChops.difference(r, g).getbbox() is None and
            ImageChops.difference(g, b).getbbox() is None)


def has_any_transparency(img: Image.Image) -> bool:
    # True if alpha exists and any pixel has alpha < 255
    if "A" not in img.getbands():
        return False
    lo, hi = img.getchannel("A").getextrema()
    return lo < 255


def head_chop_alpha_mean(img: Image.Image) -> float:
    # First-row alpha mean scaled to [0..1]
    w, h = img.size
    if w == 0 or h == 0:
        return 1.0
    alpha = img.getchannel("A") if "A" in img.getbands() else Image.new("L", (w, h), 255)
    first_row = alpha.crop((0, 0, w, 1))
    return float(ImageStat.Stat(first_row).mean[0] / 255.0)


# ---------- Checks (log only failures) ----------
def test_image(image_path: Path, counters: Dict[str, int]):
    filepre = str(image_path)
    name_wo_ext = image_path.stem

    try:
        with open_image(image_path) as img:
            w, h = get_dimensions(img)
            ratio = round((w / h) if h else 0.0, 4)

            # 1) Grayscale
            try:
                if is_grayscale(img):
                    counters["Counter1"] += 1
                    logging.warning(
                        "WARNING1!~%s~%s is Grayscale! Find a color image on TMDB and re-process",
                        filepre, name_wo_ext
                    )
            except Exception as e:
                logging.warning("Grayscale check error for %s (%s)", filepre, e)

            # 2) Not Transparent
            try:
                if not has_any_transparency(img):
                    counters["Counter2"] += 1
                    logging.warning(
                        "WARNING2!~%s~%s is NOT Transparent and needs background removed!",
                        filepre, name_wo_ext
                    )
            except Exception as e:
                logging.warning("Transparency check error for %s (%s)", filepre, e)

            # 3) Head chop (first row alpha mean > 0.06)
            try:
                head_val = head_chop_alpha_mean(img)
                if head_val > 0.06:
                    counters["Counter3"] += 1
                    logging.warning(
                        "WARNING3!~%s~%s likely HEAD CHOP; review/change headshot. Headchop values~%s",
                        filepre, name_wo_ext, head_val
                    )
            except Exception as e:
                logging.warning("Head-chop check error for %s (%s)", filepre, e)

            # 4) Ratio mismatch
            if ratio != BASE_IMAGE_RATIO:
                counters["Counter4"] += 1
                logging.warning(
                    "WARNING4!~%s~%s Ratio should be %s, found >%s<",
                    filepre, name_wo_ext, BASE_IMAGE_RATIO, ratio
                )

            # 5) Width quality (> BASE_W_QUALITY)
            if not (w - BASE_W_QUALITY > 0):
                counters["Counter5"] += 1
                logging.warning(
                    "WARNING5!~%s~%s Width should be > %s; found %s",
                    filepre, name_wo_ext, BASE_W_QUALITY, w
                )

            # 6) Height quality (> BASE_H_QUALITY)
            if not (h - BASE_H_QUALITY > 0):
                counters["Counter6"] += 1
                logging.warning(
                    "WARNING6!~%s~%s Height should be > %s; found %s",
                    filepre, name_wo_ext, BASE_H_QUALITY, h
                )

            # 7) Exact 2000 x 3000
            if not (w == REQUIRED_WIDTH and h == REQUIRED_HEIGHT):
                counters["Counter7"] += 1
                logging.warning(
                    "WARNING7!~%s~%s Dimensions should be %dx%d; found %dx%d",
                    filepre, name_wo_ext, REQUIRED_WIDTH, REQUIRED_HEIGHT, w, h
                )

    except Exception as e:
        logging.warning("Open/process error for %s (%s)", filepre, e)


# ---------- File iteration (PNG only) ----------
def iter_png_files(root: Path):
    if not root.exists():
        return
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() == ".png":
            yield p


# ---------- CLI ----------
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Recursive PNG image anomaly scanner (quiet console)")
    parser.add_argument("--images-location", required=True, help="Root folder (recursive, PNG only)")
    args = parser.parse_args()

    root = Path(args.images_location)
    if not root.exists():
        print(f"Images location >{root}< not found. Exiting now...")
        sys.exit(1)

    # START metadata in log (not spammy per-file info)
    logging.info("#### START ####")
    logging.info("scriptName                   : %s", SCRIPT_PATH.name)
    logging.info("images_location              : %s", root)
    logging.info("script_path                  : %s", SCRIPT_DIR)
    logging.info("scriptLog                    : %s", LOG_FILE)

    total = sum(1 for _ in iter_png_files(root))
    print(f"Planned scan: {total} PNG files under {root} (recursive)")

    start = timer()
    counters: Dict[str, int] = {f"Counter{i}": 0 for i in range(1, 8)}
    processed = 0

    # Console: progress bar only
    with alive_bar(total or 1, title="Scanning PNGs", dual_line=False, stats=False) as bar:
        for fp in iter_png_files(root):
            test_image(fp, counters)
            processed += 1
            bar()

    # ===== SUMMARY =====
    elapsed_min = round((timer() - start) / 60.0, 2)
    ppm = round((processed / elapsed_min), 2) if elapsed_min > 0 else processed
    tot_issues = sum(counters.values())
    tot_checks = processed * 7
    issues_pct = round(((tot_issues / tot_checks) * 100), 2) if processed > 0 else 0.0

    # Log the summary (always written)
    logging.info("#######################")
    logging.info("# SUMMARY")
    logging.info("#######################")
    logging.info("Elapsed time (min)           : %s", elapsed_min)
    logging.info("Files Processed              : %s", processed)
    logging.info("Posters per minute           : %s", ppm)
    logging.info("WARNING1 Grayscale Total     : %s", counters['Counter1'])
    logging.info("WARNING2 Transparent Total   : %s", counters['Counter2'])
    logging.info("WARNING3 Head Chop Total     : %s", counters['Counter3'])
    logging.info("WARNING4 Image Ratio Total   : %s", counters['Counter4'])
    logging.info("WARNING5 Quality W Total     : %s", counters['Counter5'])
    logging.info("WARNING6 Quality H Total     : %s", counters['Counter6'])
    logging.info("WARNING7 2000x3000 Total     : %s", counters['Counter7'])
    logging.info("Total issues                 : %s", tot_issues)
    logging.info("Total checks                 : %s", tot_checks)
    logging.info("Percent Issues               : %s %%", issues_pct)
    logging.info("#### END ####")

    # Console: compact summary only
    print("\n=== SUMMARY ===")
    print(f"Processed: {processed}  |  Elapsed: {elapsed_min} min  |  PPM: {ppm}")
    print(
        f"W1 Gray: {counters['Counter1']} | W2 NotTransparent: {counters['Counter2']} | W3 HeadChop: {counters['Counter3']}")
    print(
        f"W4 Ratio: {counters['Counter4']} | W5 Width: {counters['Counter5']} | W6 Height: {counters['Counter6']} | W7 2000x3000: {counters['Counter7']}")
    print(f"Issues: {tot_issues} / Checks: {tot_checks}  ({issues_pct}%)")
    print(f"Details in log → {LOG_FILE}")


if __name__ == "__main__":
    main()
