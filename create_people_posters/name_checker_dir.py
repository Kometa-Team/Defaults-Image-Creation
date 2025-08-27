import os
import re
import sys
import argparse
import logging
from logging import FileHandler, StreamHandler
from pathlib import Path
from urllib.parse import unquote
import requests


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


def scan_text_files(folder_path):
    hits = {}
    online_names = set()

    # Get the list of acceptable extensions
    acceptable_extensions = ['.txt', '.log', '.1', '.2', '.3', '.4', '.5', '.6', '.7', '.8', '.9']

    # Regular expression to check if the file contains "meta" or "mess" in its name
    file_name_regex = re.compile(r'(meta|mess)', re.IGNORECASE)

    # Function to check if the file matches the file name regex and acceptable extensions
    def is_acceptable_file(file):
        return file_name_regex.search(file) and any(file.lower().endswith(ext) for ext in acceptable_extensions)

    # Regular expression to find lines with "Collection Warning: No Poster Found at"
    # warning_regex = r'Collection Warning: No Poster Found at https://raw\.githubusercontent\.com/meisnate12/Plex-Meta-Manager-People(.+?)\s+'
    warning_regex = r'Collection Warning: No Poster Found at https://raw\.githubusercontent\.com/Kometa-Team/People-Images(.+?)\s+'

    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            if is_acceptable_file(file):
                logging.info(f"Scanning {file_path}")
                print(f"Scanning {file_path}")
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    # with open(file_path, 'r', encoding='utf-8-sig') as f:
                    #     content = f.read()
                    matches = re.findall(warning_regex, content)
                    if matches:
                        for match in matches:
                            decoded_filename = extract_filename_from_url(match)
                            hits[decoded_filename] = hits.get(decoded_filename, 0) + 1
                        logging.info(f"Processed {file_path}, found {len(matches)} hits.")
                        print(f"Processed {file_path}, found {len(matches)} hits.")

    sorted_hits = sorted(hits.items(), key=lambda x: x[0])

    pre_path = CONFIG_DIR / "pre-online-checklist.txt"
    with pre_path.open("w", encoding="utf-8") as f:
        for name, count in sorted_hits:
            f.write(f"{name}\n")
            online_names.add(name)

    # Fetch the online content once
    online_content = requests.get(
        "https://raw.githubusercontent.com/Kometa-Team/People-Images-rainier/master/README.md").text
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
