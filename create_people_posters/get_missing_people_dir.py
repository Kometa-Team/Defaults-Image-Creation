"""
Grayscale Image Copier

This script copies grayscale images from a specified input directory to a "Downloads" directory. It uses the Python Imaging Library (PIL) to determine the image mode and copy the images.

Usage:
    python script_name.py --input_directory /path/to/images

Dependencies:
    - Python 3.x
    - PIL (Python Imaging Library)
"""

import os
import shutil
import datetime
from pathlib import Path
from PIL import Image
import requests

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

script_log = LOGS_DIR / f"{SCRIPT_PATH.stem}.log"
download_log = LOGS_DIR / f"{SCRIPT_PATH.stem}_downloads.log"


def write_to_log_file(message):
    """Append a timestamped message to the script log file."""
    with script_log.open('a', encoding='utf-8') as log_file:
        log_file.write(f'{datetime.datetime.now()} ~ {message}\n')
    print(f'{datetime.datetime.now()} ~ {message}')


def write_to_download_log(message):
    """Append a timestamped message to the download log file."""
    with download_log.open('a', encoding='utf-8') as log_file:
        log_file.write(f'{datetime.datetime.now()} ~ {message}\n')
    print(f'{datetime.datetime.now()} ~ {message}')


def extract_filenames_from_source_directory(directory):
    """
    Extract filenames from the source directory (without extensions).
    """
    file_names = set()
    for root, _, files in os.walk(directory):
        for filename in files:
            name, _ = os.path.splitext(filename)
            file_names.add(name)
    return file_names


def copy_file(source, destination):
    """Copy a file from the source path to the destination path."""
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    write_to_log_file(f'Copied file from {source} => Saved as: {destination}')


def determine_image_mode(image_path):
    """
    Determine the mode of an image file ('RGB' or 'Grayscale').
    """
    with Image.open(image_path) as image:
        image = image.convert('RGB')
        r, g, b = image.split()

        color_variation_threshold = 30
        for rv, gv, bv in zip(r.getdata(), g.getdata(), b.getdata()):
            if abs(rv - gv) > color_variation_threshold or abs(rv - bv) > color_variation_threshold or abs(gv - bv) > color_variation_threshold:
                return 'RGB'
    return 'Grayscale'


def is_image_file(file_path):
    """Return True if the file can be opened as an image."""
    try:
        with Image.open(file_path):
            return True
    except (IOError, OSError):
        return False


def fetch_online_file_names(online_url):
    """
    Fetch file names from an online URL.
    """
    try:
        response = requests.get(online_url, timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        print(f"Failed to fetch file names from the online URL: {online_url}")
        return ""

    return response.text


def copy_grayscale_and_color_images(directory, online_file_names, source_file_names):
    """
    Copy grayscale and color images from a directory to their respective download directories,
    excluding files whose names are found in the online file names list.
    """
    for root, _, files in os.walk(directory):
        for filename in files:
            name, _ = os.path.splitext(filename)

            # Skip copying the file if its name (without extension) is found online
            if name in online_file_names:
                print(f"File {filename} found in the online list. Skipping.")
                try:
                    os.remove(os.path.join(root, filename))
                except OSError:
                    pass
                continue

            file_path = os.path.join(root, filename)
            if is_image_file(file_path):
                image_mode = determine_image_mode(file_path)
                if image_mode == 'Grayscale':
                    collection_name, _ = os.path.splitext(filename)
                    new_file_name = OTHER_DIR / f"{collection_name}.jpg"
                    copy_file(file_path, new_file_name)
                    write_to_download_log(f'Grayscale Image Copied: {filename} => Saved as: {new_file_name}')
                else:
                    collection_name, _ = os.path.splitext(filename)
                    new_file_name = COLOR_DIR / f"{collection_name}.jpg"
                    copy_file(file_path, new_file_name)
                    write_to_download_log(f'Color Image Copied: {filename} => Saved as: {new_file_name}')


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Grayscale Image Copier')
    parser.add_argument('--input_directory', metavar='input_directory', type=str,
                        help='Specify the input directory containing images')
    args = parser.parse_args()

    input_directory = args.input_directory

    if not input_directory or not os.path.exists(input_directory):
        print(f'Input directory "{input_directory}" not found. Exiting now...')
        raise SystemExit(1)

    # fresh script log each run
    if script_log.exists():
        try:
            script_log.unlink()
        except OSError:
            pass

    write_to_log_file("#### START ####")

    # 'Downloads/other' and 'Downloads/color' are already ensured above

    # Fetch online content (kept minimal to match your current logic)
    online_file_url = "https://raw.githubusercontent.com/Kometa-Team/People-Images-rainier/master/README.md"
    online_file_names = fetch_online_file_names(online_file_url)

    # Extract file names from the source directory
    source_file_names = extract_filenames_from_source_directory(input_directory)

    # Copy according to mode, excluding names seen online
    copy_grayscale_and_color_images(input_directory, online_file_names, source_file_names)

    write_to_log_file("#### END ####")
