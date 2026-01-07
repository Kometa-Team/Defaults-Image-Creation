import os
import re
import sys
import argparse
import logging
from logging import FileHandler, StreamHandler
from pathlib import Path
from urllib.parse import unquote
import requests

import time
import io
import gzip
import zipfile


# --- one place to define where "config" lives (next to the script) ---
def ensure_config_dir(script_file: str | Path) -> Path:
    # If you ever package with PyInstaller, use sys.executable's dir
    base_dir = Path(script_file).resolve().parent
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    cfg = base_dir / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    return cfg


CONFIG_DIR = ensure_config_dir(__file__)


# --- logging goes to <scriptdir>/config/logs/<scriptname>.log ---
def setup_logging(level=logging.INFO, console=True):
    log_dir = CONFIG_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{Path(__file__).stem}.log"

    handlers = [logging.FileHandler(log_file, encoding="utf-8", mode="w")]
    if console:
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.info("Logging initialized → %s", log_file)
    return log_file


# ---------- core logic ----------
def extract_filename_from_url(url):
    return unquote(os.path.splitext(os.path.basename(url))[0])


HEARTBEAT_SECS = 1.0  # print a tiny heartbeat while scanning large files


def _human_mb(n_bytes: float) -> str:
    return f"{n_bytes / 1_000_000:.1f}MB"


def _safe_getsize(path: Path) -> int | None:
    try:
        return os.path.getsize(path)
    except Exception:
        return None


def _is_acceptable_file(name: str, file_name_regex: re.Pattern, acceptable_extensions: list[str]) -> bool:
    return bool(file_name_regex.search(name) and any(name.lower().endswith(ext) for ext in acceptable_extensions))


def _process_stream_line_by_line(fobj: io.TextIOBase, warning_regex: re.Pattern, *, progress_label: str,
                                 size_bytes: int | None, hits: dict) -> int:
    """
    Stream the file line-by-line (low memory), emit a heartbeat, and tally matches.
    Returns total matches found in this stream.
    """
    last_print = time.time()
    bytes_read = 0
    matches_count = 0

    for line in fobj:
        bytes_read += len(line)

        for m in warning_regex.findall(line):
            decoded_filename = extract_filename_from_url(m)
            hits[decoded_filename] = hits.get(decoded_filename, 0) + 1
            matches_count += 1

        now = time.time()
        if now - last_print >= HEARTBEAT_SECS:
            if size_bytes and size_bytes > 0:
                pct = min(100, int((bytes_read / size_bytes) * 100))
                print(f"{progress_label}: {_human_mb(bytes_read)} / {_human_mb(size_bytes)} ({pct}%) ...")
            else:
                print(f"{progress_label}: processed ~{_human_mb(bytes_read)} ...")
            last_print = now

    return matches_count


def scan_text_files(folder_path):
    hits = {}
    online_names = set()

    acceptable_extensions = ['.txt', '.log', '.1', '.2', '.3', '.4', '.5', '.6', '.7', '.8', '.9', '.gz', '.zip']

    # File name must contain meta|mess
    file_name_regex = re.compile(r'(meta|mess)', re.IGNORECASE)

    # Selection function
    def is_acceptable_file(file):
        return _is_acceptable_file(file, file_name_regex, acceptable_extensions)

    # Warning regex
    warning_regex = re.compile(
        r'Collection Warning: No Poster Found at https://raw\.githubusercontent\.com/Kometa-Team/People-Images(.+?)\s+'
    )

    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = Path(root) / file

            # Only consider files that match your original (name + extension) rule
            if not is_acceptable_file(file):
                continue

            logging.info(f"Scanning {file_path}")
            print(f"Scanning {file_path}")

            suffix = file_path.suffix.lower()

            # --- .gz support (decompress-on-the-fly) ---
            if suffix == ".gz":
                size_bytes = _safe_getsize(file_path)  # compressed size; good enough for a rough progress bar
                try:
                    with gzip.open(file_path, 'rt', encoding='utf-8', errors='replace') as f:
                        count = _process_stream_line_by_line(
                            f, warning_regex, progress_label=f"Reading {file_path}", size_bytes=size_bytes, hits=hits
                        )
                    logging.info(f"Processed {file_path}, found {count} hits.")
                    print(f"Processed {file_path}, found {count} hits.")
                except Exception as e:
                    logging.exception("Failed to read gzip: %s", file_path)
                    print(f"!! Failed to read gzip: {file_path} ({e})", file=sys.stderr)
                continue

            # --- .zip support (scan inner entries that ALSO match your rule) ---
            if suffix == ".zip":
                try:
                    with zipfile.ZipFile(file_path) as zf:
                        for zi in zf.infolist():
                            inner = zi.filename
                            # skip directories
                            if inner.endswith('/'):
                                continue
                            # enforce the SAME selection rule on inner names to avoid regressions
                            if not is_acceptable_file(os.path.basename(inner)):
                                continue
                            # open as text safely
                            try:
                                with zf.open(zi, 'r') as raw, io.TextIOWrapper(raw, encoding='utf-8',
                                                                               errors='replace') as f:
                                    # we can use zi.file_size as a rough byte target for progress
                                    count = _process_stream_line_by_line(
                                        f, warning_regex, progress_label=f"Reading {file_path}::{inner}",
                                        size_bytes=zi.file_size, hits=hits
                                    )
                                logging.info(f"Processed {file_path}::{inner}, found {count} hits.")
                                print(f"Processed {file_path}::{inner}, found {count} hits.")
                            except Exception as e:
                                logging.exception("Failed to read zip entry: %s::%s", file_path, inner)
                                print(f"!! Failed to read zip entry: {file_path}::{inner} ({e})", file=sys.stderr)
                except Exception as e:
                    logging.exception("Failed to open zip: %s", file_path)
                    print(f"!! Failed to open zip: {file_path} ({e})", file=sys.stderr)
                continue

            # --- Plain text (streaming, with heartbeat) ---
            try:
                size_bytes = _safe_getsize(file_path)
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    count = _process_stream_line_by_line(
                        f, warning_regex, progress_label=f"Reading {file_path}", size_bytes=size_bytes, hits=hits
                    )
                logging.info(f"Processed {file_path}, found {count} hits.")
                print(f"Processed {file_path}, found {count} hits.")
            except Exception as e:
                logging.exception("Failed to read file: %s", file_path)
                print(f"!! Failed to read file: {file_path} ({e})", file=sys.stderr)

    sorted_hits = sorted(hits.items(), key=lambda x: x[0])

    pre_path = CONFIG_DIR / "pre-online-checklist.txt"
    with pre_path.open("w", encoding="utf-8") as f:
        for name, count in sorted_hits:
            f.write(f"{name}\n")
            online_names.add(name)

    # Fetch the online content once
    online_content = requests.get(
        "https://raw.githubusercontent.com/Kometa-Team/People-Images-bw/master/README.md"
    ).text
    not_found_names = set(name for name in online_names if name not in online_content)

    not_found_path = CONFIG_DIR / "people_list.txt"
    with not_found_path.open("w", encoding="utf-8") as f:
        for name in sorted(not_found_names):
            f.write(f"{name}\n")

    logging.info(f"Found {len(not_found_names)} names not found in the online source.")
    print(f"Found {len(not_found_names)} names not found in the online source.")


def main():
    setup_logging()
    parser = argparse.ArgumentParser(
        description="Scan text files for missing posters in Plex collections."
    )
    parser.add_argument(
        "--input_directory",
        help="Directory to scan. If omitted, you will be prompted.",
    )
    args = parser.parse_args()

    if args.input_directory:
        folder_path = Path(args.input_directory)
    else:
        user_input = input("Enter folder (press Enter for current directory): ").strip()
        folder_path = Path(user_input or ".")

    scan_text_files(folder_path)


if __name__ == "__main__":
    main()
