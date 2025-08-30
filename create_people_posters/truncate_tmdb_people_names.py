# rename_and_move_posters.py
import re
import sys
import shutil
import logging
from pathlib import Path
from typing import Iterable

# ---------- paths + logging ----------
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
DEFAULT_SRC = CONFIG_DIR / "posters"  # where tmdb_people.py wrote files
DEFAULT_DST = DEFAULT_SRC  # keep-in-place by default (you can override)

for d in (CONFIG_DIR, LOGS_DIR, DEFAULT_SRC):
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


setup_logging()


# ---------- core ----------
def list_files(folder: Path, ext: str = ".jpg") -> Iterable[Path]:
    ext = ext.lower()
    yield from (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ext)


def normalized_name(fname: str, ext: str = ".jpg") -> str:
    """
    Remove a trailing -<digits> before the extension.
    Example: 'First_Last-12345.jpg' -> 'First_Last.jpg'
    """
    return re.sub(rf"-\d+(?={re.escape(ext)}$)", "", fname, flags=re.IGNORECASE)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Normalize poster filenames and move duplicates.")
    parser.add_argument("--source-dir", default=str(DEFAULT_SRC),
                        help="Source folder (default: <scriptdir>/config/posters)")
    parser.add_argument("--target-dir", default=str(DEFAULT_DST), help="Target folder (default: same as source)")
    parser.add_argument("--ext", default=".jpg", help="File extension to process (default: .jpg)")
    parser.add_argument("--dup-dir-name", default="Duplicates", help="Duplicates folder name (default: Duplicates)")
    args = parser.parse_args()

    src = Path(args.source_dir).resolve()
    dst = Path(args.target_dir).resolve()
    ext = args.ext if args.ext.startswith(".") else f".{args.ext}"
    duplicates_dir = (CONFIG_DIR / args.dup_dir_name) if src == dst else (dst.parent / args.dup_dir_name)

    if not src.exists():
        logging.error("Source folder does not exist: %s", src)
        sys.exit(1)

    dst.mkdir(parents=True, exist_ok=True)
    duplicates_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    dup_count = 0
    move_count = 0

    for file in list_files(src, ext):
        new_name = normalized_name(file.name, ext=ext)
        new_src_path = file.with_name(new_name)

        # If the normalized name already exists in source and it's a different file -> treat as duplicate
        if new_src_path.exists() and new_src_path != file:
            target = duplicates_dir / file.name
            logging.info("Duplicate detected: %s -> %s", file.name, target)
            shutil.move(str(file), str(target))
            dup_count += 1
            continue

        # Rename in source if the name changed
        if new_name != file.name:
            logging.info("Renaming: %s -> %s", file.name, new_name)
            file = file.rename(new_src_path)

        # Move to destination (if destination differs)
        if src != dst:
            final_path = dst / file.name
            if final_path.exists():
                # if collision in destination, send this one to duplicates
                target = duplicates_dir / file.name
                logging.info("Collision in target; moving to duplicates: %s -> %s", file.name, target)
                shutil.move(str(file), str(target))
                dup_count += 1
            else:
                logging.info("Moving: %s -> %s", file.name, final_path)
                shutil.move(str(file), str(final_path))
                move_count += 1

        count += 1

    logging.info("Done. Processed=%d, Renamed/Kept=%d, Duplicates=%d, Moved=%d", count, count, dup_count, move_count)
    print(f"Processed={count}, Duplicates={dup_count}, Moved={move_count}")


if __name__ == "__main__":
    main()
