#!/usr/bin/env python3
"""
Sync people poster folders to a destination root (robocopy /E /COPY:DAT /DCOPY:T /XO style).

Examples:
  python sync_people_images.py --dest_root "D:/bullmoose20/Kometa-People-Images"
  PEOPLE_IMAGES_DIR="D:/bullmoose20/Kometa-People-Images" python sync_people_images.py
"""

import os
import sys
import argparse
import logging
import shutil
from pathlib import Path
from timeit import default_timer as timer

from PIL import Image, ImageChops
from dotenv import load_dotenv
from alive_progress import alive_bar

# ---------- paths + logging (same template) ----------
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
for d in (CONFIG_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)


def setup_logging(level=logging.INFO, console=True):
    log_file = LOGS_DIR / f"{SCRIPT_PATH.stem}.log"
    handlers = [logging.FileHandler(log_file, encoding="utf-8", mode="w")]
    if console:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.info("Logging -> %s", log_file)
    return log_file


setup_logging()
load_dotenv(CONFIG_DIR / ".env")

# ---------- core ----------
CATEGORIES = [
    "bw",
    "diiivoy",
    "diiivoycolor",
    "original",
    "signature",
    "rainier",
    "transparent",
]
TARGET_TRANSPARENT_SIZE = (2000, 3000)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
COLOR_REQUIRED_CATEGORIES = {"diiivoycolor", "original", "rainier", "signature", "transparent"}


def expected_extensions(category: str) -> set[str]:
    return {".png"} if category == "transparent" else {".jpg"}


def newer_than(src: Path, dst: Path) -> bool:
    """Return True if src is strictly newer than dst (XO semantics: copy only if src > dst)."""
    try:
        return src.stat().st_mtime > dst.stat().st_mtime
    except FileNotFoundError:
        return True  # no destination -> copy


def iter_dirs(src_root: Path):
    """Yield all directories (including empty) depth-first, ensuring parents first."""
    if not src_root.exists():
        return
    # parents first: sort by parts length then lexicographically
    dirs = [p for p in src_root.rglob("*") if p.is_dir()]
    dirs.sort(key=lambda p: (len(p.parts), str(p).lower()))
    yield src_root
    for d in dirs:
        yield d


def iter_files(src_root: Path):
    if not src_root.exists():
        return []
    return [p for p in src_root.rglob("*") if p.is_file()]


def copystat_dir(src: Path, dst: Path):
    # Preserve directory timestamps (/DCOPY:T)
    try:
        shutil.copystat(src, dst, follow_symlinks=False)
    except Exception as e:
        logging.debug("copystat failed on dir %s -> %s: %s", src, dst, e)


def enforce_transparent_canvas(path: Path) -> bool:
    """Force a transparent PNG onto the standard 2000x3000 canvas."""
    if path.suffix.lower() != ".png":
        return False

    with Image.open(path) as img:
        if img.size == TARGET_TRANSPARENT_SIZE:
            return False

        rgba = img.convert("RGBA")
        if rgba.width != TARGET_TRANSPARENT_SIZE[0]:
            new_height = round(rgba.height * (TARGET_TRANSPARENT_SIZE[0] / rgba.width))
            rgba = rgba.resize((TARGET_TRANSPARENT_SIZE[0], new_height), Image.Resampling.LANCZOS)

        if rgba.height > TARGET_TRANSPARENT_SIZE[1]:
            top = max((rgba.height - TARGET_TRANSPARENT_SIZE[1]) // 2, 0)
            rgba = rgba.crop((0, top, TARGET_TRANSPARENT_SIZE[0], top + TARGET_TRANSPARENT_SIZE[1]))

        canvas = Image.new("RGBA", TARGET_TRANSPARENT_SIZE, (0, 0, 0, 0))
        y = max((TARGET_TRANSPARENT_SIZE[1] - rgba.height) // 2, 0)
        canvas.alpha_composite(rgba, (0, y))
        canvas.save(path, "PNG")
        return True


def has_any_transparency(img: Image.Image) -> bool:
    if "A" not in img.getbands():
        return False
    lo, _ = img.getchannel("A").getextrema()
    return lo < 255


def is_grayscale(img: Image.Image) -> bool:
    mode = img.mode
    if mode in ("1", "L", "LA"):
        return True
    rgb = img.convert("RGB")
    r, g, b = rgb.split()
    return (
        ImageChops.difference(r, g).getbbox() is None
        and ImageChops.difference(g, b).getbbox() is None
    )


def should_validate_file(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS or path.parent.name.lower() == "images"


def image_quality_findings(
    category: str,
    path: Path,
    allow_fixable_dimensions: bool = False,
) -> tuple[list[str], list[str]]:
    blocking: list[str] = []
    warnings: list[str] = []
    suffix = path.suffix.lower()
    expected = expected_extensions(category)
    if suffix not in expected:
        expected_text = ", ".join(sorted(expected))
        blocking.append(f"{category} files must use {expected_text}")
        if suffix not in IMAGE_EXTENSIONS:
            return blocking, warnings

    try:
        with Image.open(path) as img:
            if img.size != TARGET_TRANSPARENT_SIZE and not allow_fixable_dimensions:
                blocking.append(f"dimensions are {img.width}x{img.height}, expected 2000x3000")
            if category == "transparent" and not has_any_transparency(img):
                blocking.append("not transparent; send through remove_bg")
            if category in COLOR_REQUIRED_CATEGORIES and is_grayscale(img):
                warnings.append("grayscale; send original through DeOldify before remove_bg")
    except Exception as exc:
        blocking.append(f"unreadable image: {exc}")
    return blocking, warnings


def validate_transparent_destination(path: Path) -> int:
    if not should_validate_file(path):
        return 0

    blocking, warnings = image_quality_findings("transparent", path)
    if warnings:
        logging.warning(
            "Transparent destination warning %s: %s",
            path,
            "; ".join(warnings),
        )
    if blocking:
        logging.warning(
            "Invalid transparent destination %s: %s",
            path,
            "; ".join(blocking),
        )
        return 1
    return 0


def parse_bool_env(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def preflight_sources(src_base: Path) -> int:
    blocking_failed = 0
    warning_only = 0
    for category in CATEGORIES:
        src_root = src_base / category
        if not src_root.exists():
            logging.info("preflight %s: source does not exist, skipping (%s)", category, src_root)
            continue

        category_failed = 0
        category_warnings = 0
        for path in iter_files(src_root):
            if not should_validate_file(path):
                continue
            rel = path.relative_to(src_root)
            blocking, warnings = image_quality_findings(
                category,
                path,
                allow_fixable_dimensions=(category == "transparent"),
            )
            if blocking:
                category_failed += 1
                logging.warning("preflight %s failed for %s: %s", category, rel, "; ".join(blocking))
            if warnings:
                category_warnings += 1
                logging.warning("preflight %s warning for %s: %s", category, rel, "; ".join(warnings))

        if category_failed:
            logging.warning("preflight %s: %d blocking invalid file(s)", category, category_failed)
        if category_warnings:
            logging.warning("preflight %s: %d warning-only file(s)", category, category_warnings)
        blocking_failed += category_failed
        warning_only += category_warnings

    if blocking_failed:
        logging.error("Preflight found %d blocking invalid source file(s); aborting before syncing any style repo.", blocking_failed)
    elif warning_only:
        logging.warning("Preflight found %d warning-only source file(s); continuing sync.", warning_only)
    else:
        logging.info("Preflight passed for all source style folders.")
    return blocking_failed


def sync_tree(src_root: Path, dst_root: Path, title: str, normalize_transparent: bool = False):
    """
    Rough equivalent of:
      robocopy <src> <dst> /E /COPY:DAT /DCOPY:T /XO
    """
    if not src_root.exists():
        logging.info("%s: source does not exist, skipping (%s)", title, src_root)
        return 0

    # 1) Ensure directory tree exists at destination (and copy dir timestamps)
    created_dirs = 0
    for d in iter_dirs(src_root):
        rel = d.relative_to(src_root)
        dd = dst_root / rel
        if not dd.exists():
            dd.mkdir(parents=True, exist_ok=True)
            created_dirs += 1
        copystat_dir(d, dd)

    files = iter_files(src_root)
    total = len(files)
    copied = skipped = normalized = failed = 0

    logging.info("%s: %d file(s) to evaluate", title, total)
    with alive_bar(total, dual_line=True, title=title) as bar:
        for f in files:
            rel = f.relative_to(src_root)
            df = dst_root / rel
            df.parent.mkdir(parents=True, exist_ok=True)

            try:
                if newer_than(f, df):
                    # copy2 ≈ COPY:DAT (data + basic metadata/timestamps)
                    shutil.copy2(f, df)
                    if normalize_transparent and enforce_transparent_canvas(df):
                        normalized += 1
                    if normalize_transparent:
                        failed += validate_transparent_destination(df)
                    bar.text = f"-> copied:  {rel}"
                    copied += 1
                else:
                    if normalize_transparent and enforce_transparent_canvas(df):
                        normalized += 1
                    if normalize_transparent:
                        failed += validate_transparent_destination(df)
                    bar.text = f"-> skipped: {rel} (dest newer/same)"
                    skipped += 1
            except Exception as e:
                failed += 1
                bar.text = f"-> failed:  {rel}"
                logging.warning("Failed to copy %s -> %s: %s", f, df, e)
            bar()

    logging.info(
        "%s: dirs created=%d, copied=%d, skipped=%d, normalized=%d, failed=%d",
        title, created_dirs, copied, skipped, normalized, failed
    )
    return failed


def main():
    ap = argparse.ArgumentParser(description="Sync people poster folders (robocopy-like).")
    ap.add_argument(
        "--dest_root",
        type=Path,
        default=Path(os.getenv("PEOPLE_IMAGES_DIR") or (SCRIPT_DIR / "Kometa-People-Images")),
        help="Destination root (default: PEOPLE_IMAGES_DIR env or ./Kometa-People-Images)",
    )
    ap.add_argument(
        "--preflight",
        action=argparse.BooleanOptionalAction,
        default=parse_bool_env("SYNC_PREFLIGHT", True),
        help="Run source image QA before syncing. Fatal file issues block; grayscale is report-only. Default: true.",
    )
    args = ap.parse_args()

    src_base = CONFIG_DIR / "people_dirs"
    dest_base = args.dest_root

    start = timer()
    logging.info("Source base: %s", src_base)
    logging.info("Destination base: %s", dest_base)

    if args.preflight:
        preflight_failed = preflight_sources(src_base)
        if preflight_failed:
            return 1
    else:
        logging.info("Source preflight skipped. Use SYNC_PREFLIGHT=true to restore source QA before sync.")

    failed = 0
    for cat in CATEGORIES:
        src = src_base / cat
        dst = dest_base / cat
        title = f"sync {cat}"
        logging.info("---- %s ----", title)
        failed += sync_tree(src, dst, title, normalize_transparent=(cat == "transparent"))

    elapsed = timer() - start
    logging.info("All done in %.2fs", elapsed)
    print(f"Done in {elapsed:.2f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
