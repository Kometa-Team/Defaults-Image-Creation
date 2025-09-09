#!/usr/bin/env python3
"""
Kometa Missing People Downloader — cross-platform paths + logging + robust parsing

What it does
------------
1) Reads Kometa logs and extracts people + poster URLs from TWO cases:
   - "Detail: tmdb_person updated poster to [URL] <...>"
   - "1 poster found ... Method: tmdb_person Poster: <...> ... Metadata: poster update not needed"
2) Also collects names from "Collection Warning: No Poster Found at ..." lines (no URL).
3) Checks Kometa-Team People-Images README(s) to see who already exists online.
4) Outputs (under ./config/Downloads/):
   - missing_people_names.txt        (all missing names; one per line)
   - missing_names_no_url.txt        (only those without a URL in logs)
   - missing_with_urls.csv           (name,url pairs for immediate downloading)
5) Downloads any missing-with-URL posters to ./config/Downloads/{color,other}

Logs under ./config/logs/:
   - get_missing_people.log
   - get_missing_people_downloads.log

CLI
---
python get_missing_people.py --input_directory "/path/to/kometa/logs"
  [--styles rainier,transparent] [--branch master] [--no-downloads]

Env (optional)
--------------
GETMISSING_STYLES   = "rainier,transparent"  (default: "rainier")
GETMISSING_BRANCH   = "master"               (default: "master")
"""

import os
import re
import sys
import csv
import html
import datetime
import logging
from logging import FileHandler, StreamHandler
from pathlib import Path
from typing import List, Tuple, Dict, Set

import requests
from PIL import Image

# ---------------- paths + logging ----------------
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
DOWNLOADS_DIR = CONFIG_DIR / "Downloads"
for d in (CONFIG_DIR, LOGS_DIR, DOWNLOADS_DIR):
    d.mkdir(parents=True, exist_ok=True)

MAIN_LOG_FILE = LOGS_DIR / f"{SCRIPT_PATH.stem}.log"
DL_LOG_FILE = LOGS_DIR / f"{SCRIPT_PATH.stem}_downloads.log"

MISSING_ALL_TXT = DOWNLOADS_DIR / "missing_people_names.txt"
MISSING_NO_URL_TXT = DOWNLOADS_DIR / "missing_names_no_url.txt"
MISSING_WITH_URLS_CSV = DOWNLOADS_DIR / "missing_with_urls.csv"
CONVERT_WARN_FILE = CONFIG_DIR / "convert_warning.log"


def setup_logging():
    root_handlers = [
        FileHandler(MAIN_LOG_FILE, encoding="utf-8", mode="w"),
        StreamHandler(sys.stdout),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=root_handlers,
        force=True,
    )
    dl_logger = logging.getLogger("downloads")
    dl_logger.setLevel(logging.INFO)
    dl_logger.addHandler(FileHandler(DL_LOG_FILE, encoding="utf-8", mode="w"))


setup_logging()
log = logging.getLogger(__name__)
dlog = logging.getLogger("downloads")


def write_to_log_file(message: str) -> None:
    log.info(message)


def write_to_download_log(message: str) -> None:
    dlog.info(message)


# ---------------- helpers ----------------
def _normalize_name(name: str) -> str:
    for suffix in (" (Director)", " (Producer)", " (Writer)", "'s Birthday"):
        name = name.replace(suffix, "")
    return name.strip()


def is_text_file(p: Path) -> bool:
    return p.suffix.lower() in {
        ".log", ".1", ".2", ".3", ".4", ".5", ".6", ".7", ".8", ".9", ".txt", ".csv", ".md", ".json"
    }


def download_file(url: str, destination: Path) -> bool:
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        write_to_log_file(f"Failed to download {url} → {e}")
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as f:
        f.write(r.content)
    write_to_log_file(f"Downloaded: {url} → {destination}")
    write_to_download_log(f"Downloaded: {url} → {destination}")
    return True


def determine_image_mode(image_path: Path) -> str:
    """Return 'RGB' or 'Grayscale' (anything not RGB = Grayscale for our routing)."""
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        r, g, b = img.split()
        color_variation_threshold = 30
        for rv, gv, bv in zip(r.getdata(), g.getdata(), b.getdata()):
            if abs(rv - gv) > color_variation_threshold or abs(rv - bv) > color_variation_threshold or abs(gv - bv) > color_variation_threshold:
                return "RGB"
    return "Grayscale"


# ---------------- log parsing (robust) ----------------
PAT_UPDATED = re.compile(
    r"\[\d{4}-\d{2}-\d{2}\s.*?\[.*?\]\s*\|\s*Detail:\s*tmdb_person updated poster to \[URL\]\s*"
    r"(https[^\s|]+)\s*\|"
    r"[\s\S]*?Finished\s+(.*?)\s+Collection",
    re.IGNORECASE
)

# Anthony Mann case: poster found via TMDB but metadata update not needed
PAT_FOUND = re.compile(
    r"1\s+poster\s+found:[\s\S]*?Method:\s*tmdb_person\s*Poster:\s*(https[^\s|]+)"
    r"[\s\S]*?Finished\s+(.*?)\s+Collection",
    re.IGNORECASE
)

# Names-only warning lines (no URL available in the log)
WARN_PATTERN = re.compile(
    r"Collection Warning:\s+No Poster Found at\s+https://raw\.githubusercontent\.com/Kometa-Team/People-Images(?:-[a-z]+)?/(?:main|master)/(.+?)\s",
    re.IGNORECASE
)


def extract_convert_warning(lines: List[str]) -> List[str]:
    convert_warning_lines = []
    for line in lines:
        if "Convert Warning:" in line:
            log_content = line.split("Convert Warning:")[-1].strip().rstrip("|").rstrip()
            if '"' not in log_content:
                convert_warning_lines.append(log_content)
    unique_lines = sorted(set(convert_warning_lines))
    with CONVERT_WARN_FILE.open("w", encoding="utf-8") as f:
        for s in unique_lines:
            f.write(f"Convert Warning: {s}\n")
    write_to_log_file(f'{len(unique_lines)} unique lines containing "Convert Warning:" written to {CONVERT_WARN_FILE.name}')
    return unique_lines


def parse_tmdb_blocks(text: str) -> Dict[str, str]:
    """
    Return dict: { normalized_name: full_url }
    Covers both 'updated poster' and 'found but not updated' cases.
    """
    out: Dict[str, str] = {}
    for url, name in PAT_UPDATED.findall(text):
        name = _normalize_name(html.unescape(name))
        out.setdefault(name, url)
    for url, name in PAT_FOUND.findall(text):
        name = _normalize_name(html.unescape(name))
        out.setdefault(name, url)
    return out


def parse_no_poster_warnings(text: str) -> Set[str]:
    names: Set[str] = set()
    t = text.replace("\r\n", "\n") + " "
    for frag in WARN_PATTERN.findall(t):
        frag = frag.lstrip("/")
        last = frag.split("/")[-1]
        if "." in last:
            last = last.rsplit(".", 1)[0]
        names.add(_normalize_name(html.unescape(last)))
    return names


# ---------------- online presence ----------------
def fetch_online_names(styles: List[str], branch: str = "master") -> Set[str]:
    """
    Parse README.md(s) for Kometa-Team People-Images-* repos and collect names already online.
    Default keeps legacy behavior: styles=["rainier"] unless overridden.
    """
    online: Set[str] = set()
    tried = set()
    for style in styles:
        for b in (branch, "main" if branch != "main" else "master"):
            url = f"https://raw.githubusercontent.com/Kometa-Team/People-Images-{style}/{b}/README.md"
            key = (style, b)
            if key in tried:
                continue
            tried.add(key)
            try:
                r = requests.get(url, timeout=20)
            except requests.RequestException:
                continue
            if r.status_code != 200:
                continue
            for line in r.text.splitlines():
                if "](https://raw.githubusercontent.com/Kometa-Team/People-Images" not in line:
                    continue
                try:
                    left = line.split("](", 1)[0]
                    name = left.split("[", 1)[1]
                    online.add(_normalize_name(html.unescape(name)))
                except Exception:
                    continue
            break
    write_to_log_file(f"Online presence checked across styles={styles} → {len(online)} names")
    return online


# ---------------- main ----------------
def main():
    import argparse

    DEFAULT_STYLES = os.getenv("GETMISSING_STYLES", "rainier").split(",")
    DEFAULT_STYLES = [s.strip() for s in DEFAULT_STYLES if s.strip()]
    DEFAULT_BRANCH = os.getenv("GETMISSING_BRANCH", "master")

    parser = argparse.ArgumentParser(description="Kometa Missing People Downloader")
    parser.add_argument("--input_directory", type=str, help="Kometa logs folder location")
    parser.add_argument("--styles", type=str, default=",".join(DEFAULT_STYLES),
                        help="Comma list of People-Images styles to check (default from GETMISSING_STYLES or 'rainier')")
    parser.add_argument("--branch", type=str, default=DEFAULT_BRANCH,
                        help="Branch to read READMEs from (default from GETMISSING_BRANCH or 'master')")
    parser.add_argument("--no-downloads", action="store_true",
                        help="Only report names; do not download images")
    args = parser.parse_args()

    input_directory = Path(args.input_directory) if args.input_directory else None
    if not input_directory or not input_directory.exists():
        print(f'Logs location "{input_directory}" not found. Exiting now...')
        sys.exit(1)

    styles = [s.strip() for s in args.styles.split(",") if s.strip()]
    branch = args.branch
    DO_DOWNLOADS = not args.no_downloads

    write_to_log_file("#### START ####")

    # Collect log files
    input_files = [
        p for p in input_directory.iterdir()
        if p.is_file() and ("meta" in p.name.lower() or "mess" in p.name.lower()) and is_text_file(p)
    ]

    total_matches = 0
    all_convert_warns: List[str] = []
    name_to_url: Dict[str, str] = {}
    names_from_warnings: Set[str] = set()

    for item in input_files:
        write_to_log_file(f"Working on: {item.name}")
        content = item.read_text(encoding="utf-8", errors="replace")
        all_convert_warns.extend(extract_convert_warning(content.splitlines()))

        # Gather URLs from both patterns (update + found/not-updated)
        block_map = parse_tmdb_blocks(content)  # name -> url
        total_matches += len(block_map)

        # merge (first wins per name)
        for n, u in block_map.items():
            name_to_url.setdefault(n, u)

        # gather names-only from No Poster Found warnings
        names_from_warnings |= parse_no_poster_warnings(content)

        if not block_map:
            write_to_log_file("0 items found...")

    # Union of candidates seen in logs
    candidate_names: Set[str] = set(name_to_url.keys()) | names_from_warnings

    # What already exists online?
    online_names = fetch_online_names(styles, branch=branch)

    # Partition
    missing_with_urls: List[Tuple[str, str]] = []
    missing_no_url: List[str] = []

    for n in sorted(candidate_names):
        if n in online_names:
            continue
        url = name_to_url.get(n)
        if url:
            missing_with_urls.append((n, url))
        else:
            missing_no_url.append(n)

    # Write outputs for later steps
    if missing_with_urls or missing_no_url:
        # All missing names (union) for quick consumption by later steps
        with MISSING_ALL_TXT.open("w", encoding="utf-8") as f:
            for n in sorted(set(missing_no_url) | {n for n, _ in missing_with_urls}):
                f.write(f"{n}\n")
        write_to_log_file(f"Wrote missing names → {MISSING_ALL_TXT}")

        # Names without any URL (for tmdb_people.py later)
        if missing_no_url:
            with MISSING_NO_URL_TXT.open("w", encoding="utf-8") as f:
                for n in missing_no_url:
                    f.write(f"{n}\n")
            write_to_log_file(f"Wrote names missing without URL → {MISSING_NO_URL_TXT}")

        # Names with URL → CSV so we can download or inspect
        if missing_with_urls:
            with MISSING_WITH_URLS_CSV.open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["name", "url"])
                for n, u in missing_with_urls:
                    w.writerow([n, u])
            write_to_log_file(f"Wrote missing_with_urls CSV → {MISSING_WITH_URLS_CSV}")
    else:
        write_to_log_file("No missing names detected (everything appears present online).")

    # Optional downloads (non-RGB => other/)
    new_downloads = 0
    if DO_DOWNLOADS and missing_with_urls:
        for n, url in missing_with_urls:
            ext = Path(url).suffix or ".jpg"
            safe_name = n  # already normalized
            temp_path = DOWNLOADS_DIR / f"{safe_name}{ext}"
            if download_file(url, temp_path):
                if temp_path.exists():
                    mode = determine_image_mode(temp_path)
                    subfolder = "color" if mode == "RGB" else "other"
                    final_dir = DOWNLOADS_DIR / subfolder
                    final_dir.mkdir(parents=True, exist_ok=True)
                    final_path = final_dir / temp_path.name
                    if final_path.exists():
                        final_path.unlink()
                    temp_path.rename(final_path)
                    write_to_download_log(f"Image mode: {mode} → {final_path}")
                    new_downloads += 1

    # Summaries for orchestrator early-exit logic
    write_to_log_file(f"TOTAL_LOG_MATCHES={total_matches}")
    write_to_log_file(f"TOTAL_MISSING_NAMES={len(missing_with_urls) + len(missing_no_url)}")
    write_to_log_file(f"TOTAL_NEW_DOWNLOADS={new_downloads}")

    if total_matches == 0:
        write_to_log_file("0 items found overall.")

    write_to_log_file("#### END ####")


if __name__ == "__main__":
    main()