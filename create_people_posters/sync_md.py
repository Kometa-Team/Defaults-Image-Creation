#!/usr/bin/env python3
"""
sync_md.py — Cross-platform mirror for *.md (robocopy-like /XO semantics)

- Preserves timestamps (copy2: COPY:DAT)
- Skips copy if destination is same or newer (XO)
- Recurses and creates directories as needed
- Progress bar + unified logging to ./config/logs/sync_md.log

Usage:
  python sync_md.py --src "/path/to/Kometa-People-Images/transparent" --dst "./config/people_dirs/transparent"
  python sync_md.py --src "$PEOPLE_IMAGES_DIR/transparent" --dst "./config/people_dirs/transparent" --pattern "*.md"
  python sync_md.py --src ... --dst ... --dry-run --verbose
"""
import os
import sys
import argparse
import fnmatch
import shutil
import logging
from pathlib import Path
from timeit import default_timer as timer

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # optional dependency

try:
    from alive_progress import alive_bar  # type: ignore
except Exception as e:
    print("[ERROR] alive_progress is required for progress display. Install with: pip install alive-progress", file=sys.stderr)
    raise

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


def load_env_if_present(override: bool = False):
    if load_dotenv is None:
        return
    env_path = CONFIG_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=override)


def newer_than(src: Path, dst: Path) -> bool:
    """Return True if src is strictly newer than dst (XO semantics)."""
    try:
        return src.stat().st_mtime > dst.stat().st_mtime
    except FileNotFoundError:
        return True  # no destination -> copy


def find_matching_files(root: Path, pattern: str) -> list[Path]:
    files = []
    for p in root.rglob("*"):
        if p.is_file() and fnmatch.fnmatch(p.name, pattern):
            files.append(p)
    return files


def copystat_dir(src: Path, dst: Path):
    """Preserve directory timestamps (/DCOPY:T-like)."""
    try:
        shutil.copystat(src, dst, follow_symlinks=False)
    except Exception as e:
        logging.debug("copystat failed on dir %s -> %s: %s", src, dst, e)


def mirror_md(src_root: Path, dst_root: Path, pattern: str, dry_run: bool):
    """
    Rough equivalent of:
      robocopy <src> <dst> /E /COPY:DAT /DCOPY:T /XO    (for files matching pattern only)
    """
    if not src_root.exists():
        logging.error("Source does not exist: %s", src_root)
        return 1

    # Ensure destination exists
    dst_root.mkdir(parents=True, exist_ok=True)
    copystat_dir(src_root, dst_root)

    files = find_matching_files(src_root, pattern)
    total = len(files)
    copied = skipped = failed = 0

    logging.info("Evaluating %d file(s) matching %r", total, pattern)

    with alive_bar(total, dual_line=True, title=f"sync md ({pattern})") as bar:
        for f in files:
            rel = f.relative_to(src_root)
            df = dst_root / rel
            try:
                if newer_than(f, df):
                    bar.text = f"-> copied:  {rel}"
                    if not dry_run:
                        df.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(f, df)
                    copied += 1
                else:
                    bar.text = f"-> skipped: {rel} (dest newer/same)"
                    skipped += 1
            except Exception as e:
                failed += 1
                bar.text = f"-> failed:  {rel}"
                logging.warning("Failed to copy %s -> %s: %s", f, df, e)
            bar()

    logging.info("Summary: copied=%d, skipped=%d, failed=%d", copied, skipped, failed)
    print(f"copied={copied} skipped={skipped} failed={failed}")
    return 0 if failed == 0 else 3


def main():
    setup_logging()
    load_env_if_present()

    ap = argparse.ArgumentParser(description="Mirror files (default: *.md) from src to dst, recursively.")
    ap.add_argument("--src", required=True, help="Source folder")
    ap.add_argument("--dst", required=True, help="Destination folder")
    ap.add_argument("--pattern", default="*.md", help="Glob pattern (default: *.md)")
    ap.add_argument("--dry-run", action="store_true", help="Show what would change")
    ap.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = ap.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    src = Path(os.path.expandvars(os.path.expanduser(args.src))).resolve()
    dst = Path(os.path.expandvars(os.path.expanduser(args.dst))).resolve()

    logging.info("Source: %s", src)
    logging.info("Dest  : %s", dst)
    logging.info("Pattern: %s", args.pattern)
    if args.dry_run:
        logging.info("DRY RUN: no files will be copied.")

    start = timer()
    rc = mirror_md(src, dst, args.pattern, args.dry_run)
    elapsed = timer() - start
    logging.info("Done in %.2fs (exit=%s)", elapsed, rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
