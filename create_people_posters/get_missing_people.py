"""
Kometa Missing People Downloader — cross-platform paths + logging

Writes:
  <scriptdir>/config/logs/<scriptname>.log
  <scriptdir>/config/logs/<scriptname>_downloads.log
  <scriptdir>/config/convert_warning.log
  <scriptdir>/config/Downloads/...
"""

import os
import re
import sys
import datetime
import logging
from logging import FileHandler, StreamHandler
from pathlib import Path
from typing import List, Tuple
import requests
from PIL import Image

# -------- paths + logging (shared pattern you can paste in any script) --------
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
DOWNLOADS_DIR = CONFIG_DIR / "Downloads"
for d in (CONFIG_DIR, LOGS_DIR, DOWNLOADS_DIR):
    d.mkdir(parents=True, exist_ok=True)

MAIN_LOG_FILE = LOGS_DIR / f"{SCRIPT_PATH.stem}.log"
DL_LOG_FILE = LOGS_DIR / f"{SCRIPT_PATH.stem}_downloads.log"
CONVERT_WARN_FILE = CONFIG_DIR / "convert_warning.log"


def setup_logging():
    # root logger for general messages
    root_handlers = [
        FileHandler(MAIN_LOG_FILE, encoding="utf-8", mode="w"),
        StreamHandler(sys.stdout),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=root_handlers,
        force=True,  # avoid duplicates if re-run
    )
    # dedicated "downloads" logger (separate file)
    dl_logger = logging.getLogger("downloads")
    dl_logger.setLevel(logging.INFO)
    dl_logger.addHandler(FileHandler(DL_LOG_FILE, encoding="utf-8", mode="w"))


setup_logging()
log = logging.getLogger(__name__)
dlog = logging.getLogger("downloads")


# -------- helpers (now use logging instead of manual file writes) --------
def write_to_log_file(message: str) -> None:
    log.info(message)


def write_to_download_log(message: str) -> None:
    dlog.info(message)


def write_convert_warning_log(error_lines: List[str]) -> None:
    with CONVERT_WARN_FILE.open("w", encoding="utf-8") as error_file:
        for line in error_lines:
            error_file.write(f"{line}\n")
    write_to_log_file(f'{len(error_lines)} lines containing "Convert Warning:" written to {CONVERT_WARN_FILE.name}')


# -------- network + image utilities --------
def download_file(url: str, destination: Path) -> None:
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        write_to_log_file(f"Failed to download {url} → {e}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as f:
        f.write(r.content)
    write_to_log_file(f"Downloaded: {url} → {destination}")
    write_to_download_log(f"Downloaded: {url} → {destination}")


def check_existing_file(url: str, collection_name: str) -> bool:
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        write_to_log_file(f"Failed to check existing file list: {e}")
        return False
    if collection_name in r.text:
        write_to_log_file(f"{collection_name} already exists in the file.")
        return True
    return False


def determine_image_mode(image_path: Path) -> str:
    """Return 'RGB' or 'Grayscale'."""
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        r, g, b = img.split()
        color_variation_threshold = 30
        for rv, gv, bv in zip(r.getdata(), g.getdata(), b.getdata()):
            if (
                    abs(rv - gv) > color_variation_threshold
                    or abs(rv - bv) > color_variation_threshold
                    or abs(gv - bv) > color_variation_threshold
            ):
                return "RGB"
    return "Grayscale"


# -------- main work --------
def download_images(download_urls: List[Tuple[str, str]], online_file_url: str) -> None:
    for url, collection_name in download_urls:
        ext = Path(url).suffix
        norm_name = (
            collection_name.replace("'s Birthday", "")
            .replace(" (Director)", "")
            .replace(" (Producer)", "")
            .replace(" (Writer)", "")
        )
        file_name = f"{norm_name}{ext}"
        temp_path = DOWNLOADS_DIR / file_name  # initial target before mode sort

        if not check_existing_file(online_file_url, norm_name):
            download_file(url, temp_path)

            if not temp_path.exists():
                continue  # download failed

            image_mode = determine_image_mode(temp_path)
            if image_mode == "RGB":
                subfolder = "color"
            elif image_mode == "Grayscale":  # ← fixed logic
                subfolder = "grayscale"
            else:
                subfolder = "other"

            final_dir = DOWNLOADS_DIR / subfolder
            final_dir.mkdir(parents=True, exist_ok=True)
            final_path = final_dir / file_name

            if final_path.exists():
                final_path.unlink()
            temp_path.rename(final_path)

            write_to_download_log(f"Image mode: {image_mode} → {final_path}")


def extract_convert_warning(lines):
    convert_warning_lines = []
    for line in lines:
        if "Convert Warning:" in line:
            log_content = line.split("Convert Warning:")[-1].strip().rstrip("|").rstrip()
            if '"' not in log_content:
                convert_warning_lines.append(log_content)

    unique_lines = sorted(set(convert_warning_lines))

    with CONVERT_WARN_FILE.open("w", encoding="utf-8") as error_file:
        for error_line in unique_lines:
            error_file.write(f"Convert Warning: {error_line}\n")

    write_to_log_file(
        f'{len(unique_lines)} unique lines containing "Convert Warning:" written to {CONVERT_WARN_FILE.name}'
    )
    return unique_lines


def is_text_file(file_path: Path) -> bool:
    return file_path.suffix.lower() in {
        ".log", ".1", ".2", ".3", ".4", ".5", ".6", ".7", ".8", ".9", ".txt", ".csv", ".md"
    }


# -------- CLI --------
if __name__ == "__main__":
    online_file_url = "https://raw.githubusercontent.com/Kometa-Team/People-Images-rainier/master/README.md"

    import argparse

    parser = argparse.ArgumentParser(description="Kometa Missing People Downloader")
    parser.add_argument(
        "--input_directory",
        metavar="input_directory",
        type=str,
        help="Specify the Kometa logs folder location",
    )
    args = parser.parse_args()

    input_directory = Path(args.input_directory) if args.input_directory else None
    if not input_directory or not input_directory.exists():
        print(f'Logs location "{input_directory}" not found. Exiting now...')
        sys.exit(1)

    write_to_log_file("#### START ####")

    # find input files containing "meta" or "mess" and are text-based
    input_files = [
        p for p in input_directory.iterdir()
        if p.is_file() and ("meta" in p.name.lower() or "mess" in p.name.lower()) and is_text_file(p)
    ]

    convert_warning_lines = []
    for item in input_files:
        write_to_log_file(f"Working on: {item.name}")
        with item.open("r", encoding="utf-8", errors="replace") as fh:
            content_lines = fh.readlines()

        convert_warning_lines.extend(extract_convert_warning(content_lines))

        pattern = (
            r"\[\d\d\d\d-\d\d-\d\d .*\[.*\] *\| Detail: tmdb_person updated poster to \[URL\] (https.*)(\..*g) *\|\n.*\n.*\n.*Finished (.*) Collection"
        )
        matches = re.findall(pattern, "".join(content_lines))

        if not matches:
            write_to_log_file("0 items found...")
        else:
            download_urls = [(m[0] + m[1], m[2]) for m in matches]
            download_images(download_urls, online_file_url)

    if convert_warning_lines:
        unique_lines = sorted(set(convert_warning_lines))
        with CONVERT_WARN_FILE.open("w", encoding="utf-8") as error_file:
            for line in unique_lines:
                error_file.write(f"Convert Warning: {line}\n")
        write_to_log_file(
            f'{len(unique_lines)} lines containing "Convert Warning:" written to {CONVERT_WARN_FILE.name}'
        )

    write_to_log_file("#### END ####")
