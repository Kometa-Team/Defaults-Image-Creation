#!/usr/bin/env python3
"""
Grayscale Image Copier

Copies images from an input directory into ./config/Downloads/{other,color},
classifying each file as 'Grayscale' or 'RGB' using PIL. Skips names found in
the online README list (simple text containment, same as original logic).

Input directory resolution (in this order):
  1) CLI: --input_directory
  2) .env: POSTERS_INPUT_DIR   (loaded from ./config/.env if present)
  3) Default: ./config/posters (created if missing)

Usage:
    python grayscale_copier.py --input_directory /path/to/images

Dependencies:
    - Python 3.x
    - Pillow (PIL)
    - requests
    - python-dotenv (optional; for .env support)
"""

import os
import shutil
import datetime
from pathlib import Path
from PIL import Image
import requests

# Optional .env support
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None

# ---------------- paths & logs under <scriptdir>/config/* ----------------
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
DOWNLOADS_DIR = CONFIG_DIR / "Downloads"
OTHER_DIR = DOWNLOADS_DIR / "other"
COLOR_DIR = DOWNLOADS_DIR / "color"
for d in (CONFIG_DIR, LOGS_DIR, DOWNLOADS_DIR, OTHER_DIR, COLOR_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Load .env if present (for POSTERS_INPUT_DIR)
if load_dotenv:
    env_file = CONFIG_DIR / ".env"
    if env_file.exists():
        load_dotenv(env_file)

script_log = LOGS_DIR / f"{SCRIPT_PATH.stem}.log"
download_log = LOGS_DIR / f"{SCRIPT_PATH.stem}_downloads.log"


def write_to_log_file(message: str) -> None:
    """Append a timestamped message to the script log file."""
    with script_log.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{datetime.datetime.now()} ~ {message}\n")
    print(f"{datetime.datetime.now()} ~ {message}")


def write_to_download_log(message: str) -> None:
    """Append a timestamped message to the download log file."""
    with download_log.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{datetime.datetime.now()} ~ {message}\n")
    print(f"{datetime.datetime.now()} ~ {message}")


def resolve_input_directory(cli_value: str | None) -> Path:
    """
    Preference order:
      1) CLI --input_directory
      2) POSTERS_INPUT_DIR from ./config/.env or process env
      3) ./config/posters  (created if missing)
    """
    if cli_value:
        return Path(cli_value).expanduser().resolve()
    env_val = os.getenv("POSTERS_INPUT_DIR", "").strip()
    if env_val:
        return Path(env_val).expanduser().resolve()
    default_dir = CONFIG_DIR / "posters"
    default_dir.mkdir(parents=True, exist_ok=True)
    return default_dir.resolve()


def extract_filenames_from_source_directory(directory: Path) -> set[str]:
    """Extract base filenames (without extensions) from the source directory."""
    file_names: set[str] = set()
    for root, _, files in os.walk(directory):
        for filename in files:
            name, _ = os.path.splitext(filename)
            file_names.add(name)
    return file_names


def copy_file(source: Path, destination: Path) -> None:
    """Copy a file from the source path to the destination path."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    write_to_log_file(f"Copied file from {source} => Saved as: {destination}")


def determine_image_mode(image_path: Path) -> str:
    """
    Determine the mode of an image file ('RGB' or 'Grayscale').
    Heuristic: convert to RGB and check channel variance per pixel.
    """
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        r, g, b = image.split()

        color_variation_threshold = 30
        for rv, gv, bv in zip(r.getdata(), g.getdata(), b.getdata()):
            if (
                abs(rv - gv) > color_variation_threshold
                or abs(rv - bv) > color_variation_threshold
                or abs(gv - bv) > color_variation_threshold
            ):
                return "RGB"
    return "Grayscale"


def is_image_file(file_path: Path) -> bool:
    """Return True if the file can be opened as an image."""
    try:
        with Image.open(file_path):
            return True
    except (IOError, OSError):
        return False


def fetch_online_file_names(online_url: str) -> str:
    """
    Fetch file names from an online URL.
    Returns the raw text (original behavior).
    """
    try:
        response = requests.get(online_url, timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        print(f"Failed to fetch file names from the online URL: {online_url}")
        return ""

    return response.text


def copy_grayscale_and_color_images(
    directory: Path, online_file_names: str, source_file_names: set[str]
) -> None:
    """
    Copy grayscale and color images from a directory to their respective
    download directories, excluding files whose names (without extensions)
    are found in the online file names text (simple substring check).
    """
    count_total = 0
    count_gray = 0
    count_color = 0
    count_skipped = 0

    for root, _, files in os.walk(directory):
        for filename in files:
            name, _ = os.path.splitext(filename)

            # Skip copying the file if its name (without extension) is found online
            if name and name in online_file_names:
                print(f"File {filename} found in the online list. Skipping.")
                try:
                    os.remove(os.path.join(root, filename))
                except OSError:
                    pass
                count_skipped += 1
                continue

            file_path = Path(root) / filename
            if is_image_file(file_path):
                image_mode = determine_image_mode(file_path)
                collection_name, _ = os.path.splitext(filename)
                if image_mode == "Grayscale":
                    dest = OTHER_DIR / f"{collection_name}.jpg"
                    copy_file(file_path, dest)
                    write_to_download_log(
                        f"Grayscale Image Copied: {filename} => Saved as: {dest}"
                    )
                    count_gray += 1
                else:
                    dest = COLOR_DIR / f"{collection_name}.jpg"
                    copy_file(file_path, dest)
                    write_to_download_log(
                        f"Color Image Copied: {filename} => Saved as: {dest}"
                    )
                    count_color += 1
                count_total += 1

    write_to_log_file(
        f"Summary: processed={count_total}, grayscale={count_gray}, color={count_color}, skipped_online={count_skipped}"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Grayscale Image Copier")
    parser.add_argument(
        "--input_directory",
        metavar="input_directory",
        type=str,
        help="Input directory containing images "
             "(overrides POSTERS_INPUT_DIR from ./config/.env).",
    )
    args = parser.parse_args()

    input_directory = resolve_input_directory(args.input_directory)
    write_to_log_file(f"Using input directory: {input_directory}")

    if not input_directory.exists():
        print(f'Input directory "{input_directory}" not found. Exiting now...')
        raise SystemExit(1)

    # fresh script log each run
    if script_log.exists():
        try:
            script_log.unlink()
        except OSError:
            pass

    write_to_log_file("#### START ####")

    # Fetch online content (kept minimal to match your current logic)
    online_file_url = "https://raw.githubusercontent.com/Kometa-Team/People-Images-rainier/master/README.md"
    online_file_names = fetch_online_file_names(online_file_url)

    # Extract file names from the source directory (currently unused, kept for parity with original signature)
    source_file_names = extract_filenames_from_source_directory(input_directory)

    # Copy according to mode, excluding names seen online
    copy_grayscale_and_color_images(input_directory, online_file_names, source_file_names)

    write_to_log_file("#### END ####")