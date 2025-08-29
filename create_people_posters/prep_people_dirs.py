import os
import sys
import logging
from pathlib import Path
from timeit import default_timer as timer

from dotenv import load_dotenv
from alive_progress import alive_bar

# ---------- paths + logging (same template) ----------
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
POSTERS_DIR = Path(os.getenv("POSTER_DIR") or (CONFIG_DIR / "posters"))
for d in (CONFIG_DIR, LOGS_DIR, POSTERS_DIR):
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

# ---------- env (optional, kept for parity with template) ----------
load_dotenv(SCRIPT_DIR / ".env")


# ---------- helpers ----------
def list_files(dir_path: Path):
    if not dir_path.exists():
        return []
    return [p for p in dir_path.iterdir() if p.is_file()]


def delete_files_in(dir_path: Path, title: str) -> int:
    files = list_files(dir_path)
    total = len(files)
    if total == 0:
        logging.info("%s: nothing to delete in %s", title, dir_path)
        return 0
    logging.info("%s: deleting %d file(s) in %s", title, total, dir_path)
    with alive_bar(total, dual_line=True, title=title) as bar:
        for f in files:
            try:
                f.unlink()
                bar.text = f"-> deleted: {f.name}"
            except Exception as e:
                logging.warning("Failed to delete %s: %s", f, e)
                bar.text = f"-> failed:  {f.name}"
            bar()
    return total


def move_all_files(src: Path, dst: Path, title: str) -> int:
    files = list_files(src)
    total = len(files)
    if total == 0:
        logging.info("%s: no files to move from %s", title, src)
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    logging.info("%s: moving %d file(s) %s -> %s", title, total, src, dst)
    with alive_bar(total, dual_line=True, title=title) as bar:
        for f in files:
            target = dst / f.name
            try:
                if target.exists():
                    try:
                        target.unlink()
                    except Exception as e:
                        logging.warning("Could not remove existing %s: %s", target, e)
                f.replace(target)  # atomic move when possible
                bar.text = f"-> moved:   {f.name}"
            except Exception as e:
                logging.warning("Failed to move %s -> %s: %s", f, target, e)
                bar.text = f"-> failed:  {f.name}"
            bar()
    return total


# ---------- main ----------
def main():
    start = timer()

    people_dirs = CONFIG_DIR / "people_dirs"
    people_downloads = people_dirs / "Downloads"
    src_color = CONFIG_DIR / "Downloads" / "color"
    src_other = CONFIG_DIR / "Downloads" / "other"

    # mkdirs
    people_dirs.mkdir(parents=True, exist_ok=True)
    people_downloads.mkdir(parents=True, exist_ok=True)
    logging.info("Ensured folders exist: %s and %s", people_dirs, people_downloads)

    # del .\config\posters\*.*
    delete_files_in(POSTERS_DIR, "Delete posters")

    # move color -> people_dirs\Downloads, then clean leftovers
    moved_color = move_all_files(src_color, people_downloads, "Move color")
    if moved_color == 0:
        delete_files_in(src_color, "Clean color leftovers")

    # move other -> people_dirs\Downloads, then clean leftovers
    moved_other = move_all_files(src_other, people_downloads, "Move other")
    if moved_other == 0:
        delete_files_in(src_other, "Clean other leftovers")

    elapsed = timer() - start
    logging.info("Done in %.2fs", elapsed)
    print(f"Done in {elapsed:.2f}s")


if __name__ == "__main__":
    main()