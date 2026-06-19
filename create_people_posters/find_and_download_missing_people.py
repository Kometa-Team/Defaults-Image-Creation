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
   - find_and_download_missing_people.log
   - find_and_download_missing_people_downloads.log

CLI
---
python find_and_download_missing_people.py --input_directory "/path/to/kometa/logs"
  [--styles bw,transparent] [--branch master] [--no-downloads]
python find_and_download_missing_people.py --resume-downloads
  [--resume-csv ./config/Downloads/missing_with_urls.csv]

Env (optional)
--------------
GETMISSING_STYLES   = "bw,transparent"  (default: "bw")
GETMISSING_BRANCH   = "master"               (default: "master")
"""

import os
import re
import sys
import csv
import html
import datetime
import logging
import io
import gzip
import zipfile
import tarfile
import shutil
import tempfile
from logging import FileHandler, StreamHandler
from pathlib import Path
from typing import Iterator, List, Tuple, Dict, Set

import requests
from PIL import Image

try:
    import rarfile
except Exception:
    rarfile = None

try:
    import py7zr
except Exception:
    py7zr = None

# ======== NEW: print unbuffered + resilient requests (minimal behavioral change) ========
def configure_stdio() -> None:
    """
    Keep console output from crashing on Windows when file names contain
    characters that stdout/stderr cannot encode with the active code page.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            kwargs = {"errors": "backslashreplace"}
            if stream_name == "stdout":
                kwargs["line_buffering"] = True
            reconfigure(**kwargs)
        except Exception:
            pass


configure_stdio()

# retrying requests session with sensible timeouts; we monkey-patch requests.get so the rest of the script is unchanged
_DEFAULT_TIMEOUT = (10, 30)  # (connect, read) seconds
try:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    _retry = Retry(
        total=5,
        backoff_factor=0.6,  # 0.6s, 1.2s, 2.4s, ...
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
        raise_on_status=False,
    )
    _sess = requests.Session()
    _sess.mount("http://", HTTPAdapter(max_retries=_retry))
    _sess.mount("https://", HTTPAdapter(max_retries=_retry))

    _orig_get = requests.get
    def _get_with_defaults(*args, **kwargs):
        kwargs.setdefault("timeout", _DEFAULT_TIMEOUT)
        return _sess.get(*args, **kwargs)
    requests.get = _get_with_defaults  # type: ignore[assignment]
except Exception:
    # fallback: at least enforce timeout even if urllib3 Retry isn't available
    _orig_get = requests.get
    def _get_with_timeout(*args, **kwargs):
        kwargs.setdefault("timeout", _DEFAULT_TIMEOUT)
        return _orig_get(*args, **kwargs)
    requests.get = _get_with_timeout  # type: ignore[assignment]

# simple heartbeat so long loops always show life
_last_beat = 0.0
def heartbeat(label: str, every_sec: float = 1.0) -> None:
    global _last_beat
    now = datetime.datetime.now().timestamp()
    if now - _last_beat >= every_sec:
        print(label, flush=True)
        _last_beat = now
# ========================================================================================


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
MAX_ARCHIVE_RECURSION_DEPTH = 3
MAX_ARCHIVE_MEMBER_BYTES = 500 * 1024 * 1024
RAR_BACKEND_MISSING_MESSAGE = "RAR backend not found (install UnRAR or 7-Zip, or add it to PATH)"
_RAR_BACKEND_CHECKED = False
_RAR_BACKEND_PATH: str | None = None


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


def sanitize_filename(name: str) -> str:
    """
    Make a filesystem-safe filename on Windows while keeping the display name readable.
    """
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().rstrip(". ")
    return sanitized or "unnamed"


def is_text_file(p: Path) -> bool:
    return p.suffix.lower() in {".log", ".txt", ".csv", ".md", ".json"} or bool(re.search(r"\.\d+$", p.name.lower()))


def has_supported_log_extension(name: str) -> bool:
    lowered = name.lower()
    return (
        any(
            lowered.endswith(ext)
            for ext in {".log", ".txt", ".csv", ".md", ".json", ".gz", ".zip", ".tar", ".tar.gz", ".rar", ".7z"}
        )
        or bool(re.search(r"\.\d+$", lowered))
    )


def is_candidate_log_name(name: str) -> bool:
    lowered = name.lower()
    return ("meta" in lowered or "mess" in lowered) and has_supported_log_extension(name)


def detect_archive_type(name: str) -> str | None:
    lowered = name.lower()
    if lowered.endswith(".tar.gz"):
        return "tar"
    if lowered.endswith(".zip"):
        return "zip"
    if lowered.endswith(".tar"):
        return "tar"
    if lowered.endswith(".gz"):
        return "gz"
    if lowered.endswith(".rar"):
        return "rar"
    if lowered.endswith(".7z"):
        return "7z"
    return None


def warn_archive_skip(display_name: str, reason: str) -> None:
    log.warning("Skipping %s: %s", display_name, reason)
    print(f"!! Skipping {display_name}: {reason}", file=sys.stderr, flush=True)


def resolve_tool_path(candidate: str) -> str | None:
    if os.path.isabs(candidate):
        return candidate if os.path.exists(candidate) else None
    return shutil.which(candidate)


def ensure_rar_backend() -> str | None:
    global _RAR_BACKEND_CHECKED, _RAR_BACKEND_PATH
    if _RAR_BACKEND_CHECKED:
        return _RAR_BACKEND_PATH

    _RAR_BACKEND_CHECKED = True
    if rarfile is None:
        return None

    try:
        rarfile.tool_setup(force=True)
        _RAR_BACKEND_PATH = "PATH"
        return _RAR_BACKEND_PATH
    except Exception:
        pass

    tool_candidates = [
        ("UNRAR_TOOL", ["unrar", r"C:\Program Files\WinRAR\UnRAR.exe", r"C:\Program Files (x86)\WinRAR\UnRAR.exe"]),
        ("SEVENZIP_TOOL", ["7z", r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe"]),
        ("SEVENZIP2_TOOL", ["7zz"]),
        ("BSDTAR_TOOL", ["bsdtar", r"C:\Windows\System32\bsdtar.exe"]),
        ("UNAR_TOOL", ["unar"]),
    ]
    seen_paths: set[str] = set()

    for attr_name, candidates in tool_candidates:
        for candidate in candidates:
            resolved = resolve_tool_path(candidate)
            if not resolved or resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            setattr(rarfile, attr_name, resolved)
            try:
                rarfile.tool_setup(force=True)
                _RAR_BACKEND_PATH = resolved
                return _RAR_BACKEND_PATH
            except Exception:
                continue

    return None


def read_limited_bytes(reader, display_name: str, size_hint: int | None = None) -> bytes | None:
    if size_hint is not None and size_hint > MAX_ARCHIVE_MEMBER_BYTES:
        warn_archive_skip(display_name, f"entry exceeds {MAX_ARCHIVE_MEMBER_BYTES} bytes")
        return None

    content_bytes = reader.read(MAX_ARCHIVE_MEMBER_BYTES + 1)
    if len(content_bytes) > MAX_ARCHIVE_MEMBER_BYTES:
        warn_archive_skip(display_name, f"entry exceeds {MAX_ARCHIVE_MEMBER_BYTES} bytes")
        return None
    return content_bytes


def iter_archive_texts(archive_source, display_name: str, archive_name: str, depth: int = 1) -> Iterator[Tuple[str, str]]:
    if depth > MAX_ARCHIVE_RECURSION_DEPTH:
        warn_archive_skip(display_name, f"nested archive depth exceeds {MAX_ARCHIVE_RECURSION_DEPTH}")
        return

    archive_type = detect_archive_type(archive_name)
    if archive_type is None:
        return

    def handle_member(member_name: str, content_bytes: bytes):
        base_name = os.path.basename(member_name.rstrip("/\\"))
        if not base_name:
            return

        nested_display_name = f"{display_name}::{member_name}"
        nested_archive_type = detect_archive_type(base_name)
        if nested_archive_type is not None and has_supported_log_extension(base_name):
            yield from iter_archive_texts(content_bytes, nested_display_name, base_name, depth + 1)
            return

        if not is_candidate_log_name(base_name):
            return

        yield nested_display_name, content_bytes.decode("utf-8", errors="replace")

    try:
        if archive_type == "gz":
            extracted_name = archive_name[:-3] if archive_name.lower().endswith(".gz") else archive_name
            if not extracted_name:
                return
            nested_archive_type = detect_archive_type(extracted_name)
            if nested_archive_type is not None and has_supported_log_extension(extracted_name):
                if isinstance(archive_source, (str, Path)):
                    with gzip.open(archive_source, "rb") as gz_file:
                        content_bytes = read_limited_bytes(gz_file, display_name)
                else:
                    with gzip.GzipFile(fileobj=io.BytesIO(archive_source), mode="rb") as gz_file:
                        content_bytes = read_limited_bytes(gz_file, display_name)
                if content_bytes is None:
                    return
                yield from handle_member(extracted_name, content_bytes)
            elif is_candidate_log_name(extracted_name):
                if isinstance(archive_source, (str, Path)):
                    with gzip.open(archive_source, "rt", encoding="utf-8", errors="replace") as text_reader:
                        yield f"{display_name}::{extracted_name}", text_reader.read()
                else:
                    with gzip.GzipFile(fileobj=io.BytesIO(archive_source), mode="rb") as gz_file:
                        with io.TextIOWrapper(gz_file, encoding="utf-8", errors="replace") as text_reader:
                            yield f"{display_name}::{extracted_name}", text_reader.read()
            return

        if archive_type == "zip":
            zip_source = archive_source if isinstance(archive_source, (str, Path)) else io.BytesIO(archive_source)
            with zipfile.ZipFile(zip_source) as zf:
                for zi in zf.infolist():
                    inner_name = zi.filename
                    if zi.is_dir() or "__MACOSX" in inner_name:
                        continue
                    nested_display_name = f"{display_name}::{inner_name}"
                    try:
                        base_name = os.path.basename(inner_name.rstrip("/\\"))
                        nested_archive_type = detect_archive_type(base_name)
                        if nested_archive_type is not None and has_supported_log_extension(base_name):
                            with zf.open(zi, "r") as raw:
                                content_bytes = read_limited_bytes(raw, nested_display_name, zi.file_size)
                            if content_bytes is None:
                                continue
                            yield from handle_member(inner_name, content_bytes)
                        elif is_candidate_log_name(base_name):
                            with zf.open(zi, "r") as raw, io.TextIOWrapper(raw, encoding="utf-8", errors="replace") as text_reader:
                                yield nested_display_name, text_reader.read()
                    except Exception:
                        log.exception("Failed to read zip entry: %s", nested_display_name)
                        print(f"!! Failed to read zip entry: {nested_display_name}", file=sys.stderr, flush=True)
            return

        if archive_type == "tar":
            if isinstance(archive_source, (str, Path)):
                tar_ctx = tarfile.open(archive_source, "r:*")
            else:
                tar_ctx = tarfile.open(fileobj=io.BytesIO(archive_source), mode="r:*")
            with tar_ctx as tf:
                for member in tf.getmembers():
                    inner_name = member.name
                    if not member.isfile() or "__MACOSX" in inner_name:
                        continue
                    nested_display_name = f"{display_name}::{inner_name}"
                    try:
                        base_name = os.path.basename(inner_name.rstrip("/\\"))
                        nested_archive_type = detect_archive_type(base_name)
                        extracted = tf.extractfile(member)
                        if extracted is None:
                            continue
                        with extracted:
                            if nested_archive_type is not None and has_supported_log_extension(base_name):
                                content_bytes = read_limited_bytes(extracted, nested_display_name, member.size)
                                if content_bytes is None:
                                    continue
                                yield from handle_member(inner_name, content_bytes)
                            elif is_candidate_log_name(base_name):
                                with io.TextIOWrapper(extracted, encoding="utf-8", errors="replace") as text_reader:
                                    yield nested_display_name, text_reader.read()
                    except Exception:
                        log.exception("Failed to read tar entry: %s", nested_display_name)
                        print(f"!! Failed to read tar entry: {nested_display_name}", file=sys.stderr, flush=True)
            return

        if archive_type == "rar":
            if rarfile is None:
                warn_archive_skip(display_name, "rarfile is unavailable")
                return
            if ensure_rar_backend() is None:
                warn_archive_skip(display_name, RAR_BACKEND_MISSING_MESSAGE)
                return

            temp_path = None
            try:
                rar_source = archive_source
                if not isinstance(archive_source, (str, Path)):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".rar") as temp_file:
                        temp_file.write(archive_source)
                        temp_path = temp_file.name
                    rar_source = temp_path

                with rarfile.RarFile(rar_source) as rf:
                    for member in rf.infolist():
                        inner_name = member.filename
                        if member.isdir() or "__MACOSX" in inner_name:
                            continue
                        nested_display_name = f"{display_name}::{inner_name}"
                        try:
                            base_name = os.path.basename(inner_name.rstrip("/\\"))
                            nested_archive_type = detect_archive_type(base_name)
                            with rf.open(member) as raw:
                                if nested_archive_type is not None and has_supported_log_extension(base_name):
                                    content_bytes = read_limited_bytes(raw, nested_display_name, member.file_size)
                                    if content_bytes is None:
                                        continue
                                    yield from handle_member(inner_name, content_bytes)
                                elif is_candidate_log_name(base_name):
                                    with io.TextIOWrapper(raw, encoding="utf-8", errors="replace") as text_reader:
                                        yield nested_display_name, text_reader.read()
                        except Exception:
                            log.exception("Failed to read rar entry: %s", nested_display_name)
                            print(f"!! Failed to read rar entry: {nested_display_name}", file=sys.stderr, flush=True)
            finally:
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
            return

        if archive_type == "7z":
            if py7zr is None:
                warn_archive_skip(display_name, "py7zr is unavailable")
                return

            seven_zip_source = archive_source if isinstance(archive_source, (str, Path)) else io.BytesIO(archive_source)
            with tempfile.TemporaryDirectory(prefix="missing_people_7z_") as temp_dir:
                with py7zr.SevenZipFile(seven_zip_source, mode="r") as zf:
                    zf.extractall(path=temp_dir)

                for root, _, files in os.walk(temp_dir):
                    for file_name in files:
                        extracted_path = Path(root) / file_name
                        inner_name = str(extracted_path.relative_to(temp_dir)).replace("\\", "/")
                        if "__MACOSX" in inner_name:
                            continue
                        nested_display_name = f"{display_name}::{inner_name}"
                        try:
                            base_name = os.path.basename(inner_name.rstrip("/\\"))
                            nested_archive_type = detect_archive_type(base_name)
                            size_bytes = extracted_path.stat().st_size
                            if nested_archive_type is not None and has_supported_log_extension(base_name):
                                if size_bytes > MAX_ARCHIVE_MEMBER_BYTES:
                                    warn_archive_skip(nested_display_name, f"entry exceeds {MAX_ARCHIVE_MEMBER_BYTES} bytes")
                                    continue
                                yield from handle_member(inner_name, extracted_path.read_bytes())
                            elif is_candidate_log_name(base_name):
                                with extracted_path.open("r", encoding="utf-8", errors="replace") as text_reader:
                                    yield nested_display_name, text_reader.read()
                        except Exception:
                            log.exception("Failed to read 7z entry: %s", nested_display_name)
                            print(f"!! Failed to read 7z entry: {nested_display_name}", file=sys.stderr, flush=True)
            return
    except Exception:
        log.exception("Failed to open archive: %s", display_name)
        print(f"!! Failed to open archive: {display_name}", file=sys.stderr, flush=True)


def iter_log_contents(input_directory: Path) -> Iterator[Tuple[str, str]]:
    for root, _, files in os.walk(input_directory):
        for file_name in files:
            file_path = Path(root) / file_name
            archive_type = detect_archive_type(file_name)

            if archive_type is not None:
                if not has_supported_log_extension(file_name):
                    continue
            elif not is_candidate_log_name(file_name):
                continue

            if archive_type is not None:
                yield from iter_archive_texts(file_path, str(file_path), file_path.name)
                continue

            try:
                yield str(file_path), file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                log.exception("Failed to read log: %s", file_path)
                print(f"!! Failed to read log: {file_path}", file=sys.stderr, flush=True)


def collect_top_level_log_candidates(input_directory: Path) -> List[Path]:
    candidate_files: List[Path] = []
    write_to_log_file(f"Counting top-level files under {input_directory}")
    print(f"Counting top-level files under {input_directory} ...", flush=True)

    for root, _, files in os.walk(input_directory):
        for file_name in files:
            file_path = Path(root) / file_name
            archive_type = detect_archive_type(file_name)

            if archive_type is not None:
                if not has_supported_log_extension(file_name):
                    continue
            elif not is_candidate_log_name(file_name):
                continue

            candidate_files.append(file_path)
            heartbeat(f"Counting top-level files: {len(candidate_files)} found so far ...")

    return candidate_files


def iter_log_contents_from_path(file_path: Path) -> Iterator[Tuple[str, str]]:
    archive_type = detect_archive_type(file_path.name)

    if archive_type is not None:
        if not has_supported_log_extension(file_path.name):
            return
        yield from iter_archive_texts(file_path, str(file_path), file_path.name)
        return

    if not is_candidate_log_name(file_path.name):
        return

    try:
        yield str(file_path), file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        log.exception("Failed to read log: %s", file_path)
        print(f"!! Failed to read log: {file_path}", file=sys.stderr, flush=True)


def download_file(url: str, destination: Path) -> bool:
    try:
        r = requests.get(url)  # timeout + retries injected above
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


def read_missing_with_urls_csv(csv_path: Path) -> List[Tuple[str, str]]:
    items: List[Tuple[str, str]] = []
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = _normalize_name((row.get("name") or "").strip())
            url = (row.get("url") or "").strip()
            if name and url:
                items.append((name, url))
    return items


def route_downloaded_image(temp_path: Path) -> Path:
    mode = determine_image_mode(temp_path)
    subfolder = "color" if mode == "RGB" else "other"
    final_dir = DOWNLOADS_DIR / subfolder
    final_dir.mkdir(parents=True, exist_ok=True)
    final_path = final_dir / temp_path.name
    if final_path.exists():
        final_path.unlink()
    temp_path.rename(final_path)
    write_to_download_log(f"Image mode: {mode} → {final_path}")
    return final_path


def process_download_batch(missing_with_urls: List[Tuple[str, str]]) -> Tuple[int, int]:
    new_downloads = 0
    skipped_existing = 0

    for idx, (n, url) in enumerate(missing_with_urls, 1):
        heartbeat(f"Downloading {idx}/{len(missing_with_urls)} …")
        ext = Path(url).suffix or ".jpg"
        safe_name = sanitize_filename(n)
        temp_path = DOWNLOADS_DIR / f"{safe_name}{ext}"
        color_path = DOWNLOADS_DIR / "color" / temp_path.name
        other_path = DOWNLOADS_DIR / "other" / temp_path.name

        if color_path.exists() or other_path.exists():
            skipped_existing += 1
            write_to_download_log(f"Skipping existing download: {n} → {color_path if color_path.exists() else other_path}")
            continue

        if temp_path.exists():
            route_downloaded_image(temp_path)
            skipped_existing += 1
            continue

        if download_file(url, temp_path) and temp_path.exists():
            route_downloaded_image(temp_path)
            new_downloads += 1

    return new_downloads, skipped_existing


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
    existing_lines: Set[str] = set()
    if CONVERT_WARN_FILE.exists():
        try:
            for line in CONVERT_WARN_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
                if "Convert Warning:" in line:
                    existing_content = line.split("Convert Warning:")[-1].strip()
                    if existing_content:
                        existing_lines.add(existing_content)
        except OSError:
            pass
    new_lines = [s for s in unique_lines if s not in existing_lines]
    if new_lines:
        needs_newline = False
        if CONVERT_WARN_FILE.exists():
            try:
                with CONVERT_WARN_FILE.open("rb") as f:
                    f.seek(0, os.SEEK_END)
                    if f.tell() > 0:
                        f.seek(-1, os.SEEK_END)
                        last = f.read(1)
                        needs_newline = last not in (b"\n", b"\r")
            except OSError:
                pass
        with CONVERT_WARN_FILE.open("a", encoding="utf-8") as f:
            if needs_newline:
                f.write("\n")
            for s in new_lines:
                f.write(f"Convert Warning: {s}\n")
    total_unique = len(existing_lines) + len(new_lines)
    write_to_log_file(
        f'{len(new_lines)} new lines containing "Convert Warning:" appended to {CONVERT_WARN_FILE.name} '
        f'({total_unique} total)'
    )
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
    Default keeps legacy behavior: styles=["bw"] unless overridden.
    """
    online: Set[str] = set()
    tried = set()
    total_checks = len(styles) * 2  # branch + fallback
    done = 0

    for style in styles:
        for b in (branch, "main" if branch != "main" else "master"):
            url = f"https://raw.githubusercontent.com/Kometa-Team/People-Images-{style}/{b}/README.md"
            key = (style, b)
            if key in tried:
                continue
            tried.add(key)
            try:
                r = requests.get(url)  # timeout + retries injected above
            except requests.RequestException:
                done += 1
                heartbeat(f"Checking online names… {done}/{total_checks}")
                continue
            if r.status_code != 200:
                done += 1
                heartbeat(f"Checking online names… {done}/{total_checks}")
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
            done += 1
            heartbeat(f"Checking online names… {done}/{total_checks}")
            break
    write_to_log_file(f"Online presence checked across styles={styles} → {len(online)} names")
    return online


# ---------------- main ----------------
def main():
    import argparse

    DEFAULT_STYLES = os.getenv("GETMISSING_STYLES", "bw").split(",")
    DEFAULT_STYLES = [s.strip() for s in DEFAULT_STYLES if s.strip()]
    DEFAULT_BRANCH = os.getenv("GETMISSING_BRANCH", "master")

    parser = argparse.ArgumentParser(description="Kometa Missing People Downloader")
    parser.add_argument("--input", dest="input_directory", type=str, help="Alias for --input_directory")
    parser.add_argument("--input_directory", dest="input_directory", type=str, help="Kometa logs folder location")
    parser.add_argument("--styles", type=str, default=",".join(DEFAULT_STYLES),
                        help="Comma list of People-Images styles to check (default from GETMISSING_STYLES or 'bw')")
    parser.add_argument("--branch", type=str, default=DEFAULT_BRANCH,
                        help="Branch to read READMEs from (default from GETMISSING_BRANCH or 'master')")
    parser.add_argument("--no-downloads", action="store_true",
                        help="Only report names; do not download images")
    parser.add_argument("--resume-downloads", action="store_true",
                        help="Skip log scanning and resume downloads from missing_with_urls.csv")
    parser.add_argument("--resume-csv", type=str, default=str(MISSING_WITH_URLS_CSV),
                        help="CSV used with --resume-downloads (default: ./config/Downloads/missing_with_urls.csv)")
    args = parser.parse_args()

    styles = [s.strip() for s in args.styles.split(",") if s.strip()]
    branch = args.branch
    DO_DOWNLOADS = not args.no_downloads
    resume_downloads = args.resume_downloads
    input_directory = Path(args.input_directory) if args.input_directory else None

    write_to_log_file("#### START ####")
    if resume_downloads:
        write_to_log_file("Resume mode enabled: skipping log scan and loading download list from CSV.")
    elif not input_directory or not input_directory.exists():
        print(f'Logs location "{input_directory}" not found. Exiting now...')
        sys.exit(1)

    total_matches = 0
    missing_with_urls: List[Tuple[str, str]] = []
    missing_no_url: List[str] = []
    all_convert_warns: List[str] = []
    name_to_url: Dict[str, str] = {}
    names_from_warnings: Set[str] = set()

    if resume_downloads:
        input_directory = DOWNLOADS_DIR

    try:
        candidate_files = collect_top_level_log_candidates(input_directory)
        total_candidate_files = len(candidate_files)
        write_to_log_file(
            f"Found {total_candidate_files} top-level file(s) to scan. Nested archive members are not included in this count."
        )
        print(
            f"Found {total_candidate_files} top-level file(s) to scan. "
            "Nested archive members are not included in this count.",
            flush=True,
        )

        item_index = 0
        for top_level_index, file_path in enumerate(candidate_files, 1):
            progress_prefix = f"[{top_level_index}/{total_candidate_files}]"
            write_to_log_file(f"{progress_prefix} Scanning {file_path}")
            print(f"{progress_prefix} Scanning {file_path}", flush=True)
            input_items = iter_log_contents_from_path(file_path)
            for item_name, content in input_items:
                item_index += 1
                try:
                    write_to_log_file(f"Working on: {item_name}")
                    print(f"Reading {item_name} ({item_index}) …", flush=True)

                    # heartbeat while parsing (useful on very large logs)
                    heartbeat(f"{progress_prefix} Parsing {item_name} …")

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
                except Exception as exc:
                    log.exception("Failed while processing %s", item_name)
                    print(f"!! Failed while processing {item_name} ({exc})", file=sys.stderr, flush=True)
                    continue
    except OSError as exc:
        write_to_log_file(f"Failed to enumerate logs in {input_directory}: {exc}")
        print(f'Failed to enumerate logs in "{input_directory}": {exc}')
        sys.exit(1)

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

    if resume_downloads:
        resume_csv = Path(args.resume_csv)
        missing_with_urls = read_missing_with_urls_csv(resume_csv)
        missing_no_url = []
        write_to_log_file(f"Loaded {len(missing_with_urls)} download item(s) from {resume_csv}")

    # Optional downloads (non-RGB => other/)
    new_downloads = 0
    skipped_existing = 0
    if DO_DOWNLOADS and missing_with_urls:
        new_downloads, skipped_existing = process_download_batch(missing_with_urls)

    # Summaries for orchestrator early-exit logic
    write_to_log_file(f"TOTAL_LOG_MATCHES={total_matches}")
    write_to_log_file(f"TOTAL_MISSING_NAMES={len(missing_with_urls) + len(missing_no_url)}")
    write_to_log_file(f"TOTAL_NEW_DOWNLOADS={new_downloads}")
    write_to_log_file(f"TOTAL_SKIPPED_EXISTING_DOWNLOADS={skipped_existing}")

    if total_matches == 0:
        write_to_log_file("0 items found overall.")

    write_to_log_file("#### END ####")


if __name__ == "__main__":
    main()
