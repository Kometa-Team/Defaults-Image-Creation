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
    logging.info("Logging → %s", log_file)
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


def sync_tree(src_root: Path, dst_root: Path, title: str):
    """
    Rough equivalent of:
      robocopy <src> <dst> /E /COPY:DAT /DCOPY:T /XO
    """
    if not src_root.exists():
        logging.info("%s: source does not exist, skipping (%s)", title, src_root)
        return

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
    copied = skipped = failed = 0

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
                    bar.text = f"-> copied:  {rel}"
                    copied += 1
                else:
                    bar.text = f"-> skipped: {rel} (dest newer/same)"
                    skipped += 1
            except Exception as e:
                failed += 1
                bar.text = f"-> failed:  {rel}"
                logging.warning("Failed to copy %s -> %s: %s", f, df, e)
            bar()

    logging.info(
        "%s: dirs created=%d, copied=%d, skipped=%d, failed=%d",
        title, created_dirs, copied, skipped, failed
    )


def main():
    ap = argparse.ArgumentParser(description="Sync people poster folders (robocopy-like).")
    ap.add_argument(
        "--dest_root",
        type=Path,
        default=Path(os.getenv("PEOPLE_IMAGES_DIR") or (SCRIPT_DIR / "Kometa-People-Images")),
        help="Destination root (default: PEOPLE_IMAGES_DIR env or ./Kometa-People-Images)",
    )
    args = ap.parse_args()

    src_base = CONFIG_DIR / "people_dirs"
    dest_base = args.dest_root

    start = timer()
    logging.info("Source base: %s", src_base)
    logging.info("Destination base: %s", dest_base)

    for cat in CATEGORIES:
        src = src_base / cat
        dst = dest_base / cat
        title = f"sync {cat}"
        logging.info("---- %s ----", title)
        sync_tree(src, dst, title)

    elapsed = timer() - start
    logging.info("All done in %.2fs", elapsed)
    print(f"Done in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
