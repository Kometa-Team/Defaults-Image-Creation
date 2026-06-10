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
import tarfile
import tempfile

try:
    import rarfile
except Exception:
    rarfile = None

try:
    import py7zr
except Exception:
    py7zr = None


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
ONLINE_README_URL = "https://raw.githubusercontent.com/Kometa-Team/People-Images-bw/master/README.md"
ONLINE_README_CACHE = CONFIG_DIR / "people_images_bw_README_cache.md"
REQUEST_TIMEOUT = (10, 30)


def build_requests_session() -> requests.Session:
    session = requests.Session()
    try:
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        retry = Retry(
            total=5,
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "HEAD"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
    except Exception:
        pass
    return session


REQUESTS_SESSION = build_requests_session()


def configure_stdio() -> None:
    """
    Keep console output from crashing on Windows when paths contain characters
    that the active stdout/stderr encoding cannot represent.
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


def fetch_online_readme() -> tuple[str | None, str | None]:
    try:
        response = REQUESTS_SESSION.get(ONLINE_README_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        text = response.text
        ONLINE_README_CACHE.write_text(text, encoding="utf-8")
        logging.info("Fetched online README → %s", ONLINE_README_URL)
        return text, "live"
    except requests.RequestException as exc:
        logging.warning("Failed to fetch online README: %s", exc)
    except OSError as exc:
        logging.warning("Fetched online README but could not update cache: %s", exc)
        return response.text, "live"

    if ONLINE_README_CACHE.exists():
        try:
            cached_text = ONLINE_README_CACHE.read_text(encoding="utf-8", errors="replace")
            logging.warning("Using cached online README → %s", ONLINE_README_CACHE)
            return cached_text, "cache"
        except OSError as exc:
            logging.warning("Failed to read cached online README: %s", exc)

    return None, None


# ---------- core logic ----------
def extract_filename_from_url(url):
    return unquote(os.path.splitext(os.path.basename(url))[0])


HEARTBEAT_SECS = 1.0  # print a tiny heartbeat while scanning large files
MAX_ARCHIVE_RECURSION_DEPTH = 3
MAX_ARCHIVE_MEMBER_BYTES = 100 * 1024 * 1024


def _human_mb(n_bytes: float) -> str:
    return f"{n_bytes / 1_000_000:.1f}MB"


def _safe_getsize(path: Path) -> int | None:
    try:
        return os.path.getsize(path)
    except Exception:
        return None


def _has_supported_extension(name: str, acceptable_extensions: list[str]) -> bool:
    lowered = name.lower()
    return any(lowered.endswith(ext) for ext in acceptable_extensions)


def _detect_archive_type(name: str) -> str | None:
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


def _warn_archive_skip(display_name: str, reason: str) -> None:
    logging.warning("Skipping %s: %s", display_name, reason)
    print(f"!! Skipping {display_name}: {reason}", file=sys.stderr)


def _read_limited_bytes(reader, display_name: str, size_hint: int | None = None) -> bytes | None:
    if size_hint is not None and size_hint > MAX_ARCHIVE_MEMBER_BYTES:
        _warn_archive_skip(display_name, f"entry exceeds {MAX_ARCHIVE_MEMBER_BYTES} bytes")
        return None

    content_bytes = reader.read(MAX_ARCHIVE_MEMBER_BYTES + 1)
    if len(content_bytes) > MAX_ARCHIVE_MEMBER_BYTES:
        _warn_archive_skip(display_name, f"entry exceeds {MAX_ARCHIVE_MEMBER_BYTES} bytes")
        return None
    return content_bytes


def _iter_archive_texts(archive_source, display_name: str, archive_name: str, acceptable_extensions: list[str],
                        is_acceptable_file, depth: int = 1):
    if depth > MAX_ARCHIVE_RECURSION_DEPTH:
        _warn_archive_skip(display_name, f"nested archive depth exceeds {MAX_ARCHIVE_RECURSION_DEPTH}")
        return

    archive_type = _detect_archive_type(archive_name)
    if archive_type is None:
        return

    def handle_member(member_name: str, content_bytes: bytes, size_bytes: int | None = None):
        base_name = os.path.basename(member_name.rstrip("/\\"))
        if not base_name:
            return

        nested_display_name = f"{display_name}::{member_name}"
        nested_archive_type = _detect_archive_type(base_name)
        if nested_archive_type is not None and _has_supported_extension(base_name, acceptable_extensions):
            yield from _iter_archive_texts(
                content_bytes,
                nested_display_name,
                base_name,
                acceptable_extensions,
                is_acceptable_file,
                depth + 1,
            )
            return

        if not is_acceptable_file(base_name):
            return

        yield nested_display_name, content_bytes.decode("utf-8", errors="replace"), size_bytes or len(content_bytes)

    try:
        if archive_type == "gz":
            if isinstance(archive_source, (str, Path)):
                with gzip.open(archive_source, "rb") as gz_file:
                    content_bytes = _read_limited_bytes(gz_file, display_name)
            else:
                with gzip.GzipFile(fileobj=io.BytesIO(archive_source), mode="rb") as gz_file:
                    content_bytes = _read_limited_bytes(gz_file, display_name)

            if content_bytes is None:
                return

            extracted_name = archive_name[:-3] if archive_name.lower().endswith(".gz") else archive_name
            if extracted_name:
                yield from handle_member(extracted_name, content_bytes)
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
                        with zf.open(zi, "r") as raw:
                            content_bytes = _read_limited_bytes(raw, nested_display_name, zi.file_size)
                        if content_bytes is None:
                            continue
                        yield from handle_member(inner_name, content_bytes, zi.file_size)
                    except Exception as exc:
                        logging.exception("Failed to read zip entry: %s", nested_display_name)
                        print(f"!! Failed to read zip entry: {nested_display_name} ({exc})", file=sys.stderr)
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
                        extracted = tf.extractfile(member)
                        if extracted is None:
                            continue
                        with extracted:
                            content_bytes = _read_limited_bytes(extracted, nested_display_name, member.size)
                        if content_bytes is None:
                            continue
                        yield from handle_member(inner_name, content_bytes, member.size)
                    except Exception as exc:
                        logging.exception("Failed to read tar entry: %s", nested_display_name)
                        print(f"!! Failed to read tar entry: {nested_display_name} ({exc})", file=sys.stderr)
            return

        if archive_type == "rar":
            if rarfile is None:
                _warn_archive_skip(display_name, "rarfile is unavailable")
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
                            with rf.open(member) as raw:
                                content_bytes = _read_limited_bytes(raw, nested_display_name, member.file_size)
                            if content_bytes is None:
                                continue
                            yield from handle_member(inner_name, content_bytes, member.file_size)
                        except Exception as exc:
                            logging.exception("Failed to read rar entry: %s", nested_display_name)
                            print(f"!! Failed to read rar entry: {nested_display_name} ({exc})", file=sys.stderr)
            finally:
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
            return

        if archive_type == "7z":
            if py7zr is None:
                _warn_archive_skip(display_name, "py7zr is unavailable")
                return

            seven_zip_source = archive_source if isinstance(archive_source, (str, Path)) else io.BytesIO(archive_source)
            with py7zr.SevenZipFile(seven_zip_source, mode="r") as zf:
                extracted_map = zf.readall()
                for inner_name, bio in extracted_map.items():
                    if inner_name.endswith("/") or "__MACOSX" in inner_name:
                        continue
                    nested_display_name = f"{display_name}::{inner_name}"
                    try:
                        buffer = bio.getbuffer()
                        size_bytes = len(buffer)
                        if size_bytes > MAX_ARCHIVE_MEMBER_BYTES:
                            _warn_archive_skip(nested_display_name, f"entry exceeds {MAX_ARCHIVE_MEMBER_BYTES} bytes")
                            continue
                        content_bytes = bytes(buffer)
                        yield from handle_member(inner_name, content_bytes, size_bytes)
                    except Exception as exc:
                        logging.exception("Failed to read 7z entry: %s", nested_display_name)
                        print(f"!! Failed to read 7z entry: {nested_display_name} ({exc})", file=sys.stderr)
            return
    except Exception as exc:
        logging.exception("Failed to open archive: %s", display_name)
        print(f"!! Failed to open archive: {display_name} ({exc})", file=sys.stderr)


def _is_acceptable_file(name: str, file_name_regex: re.Pattern, acceptable_extensions: list[str]) -> bool:
    return bool(file_name_regex.search(name) and _has_supported_extension(name, acceptable_extensions))


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


def _scan_archive_text_stream(fobj: io.TextIOBase, warning_regex: re.Pattern, progress_label: str,
                              size_bytes: int | None, hits: dict) -> int:
    return _process_stream_line_by_line(
        fobj, warning_regex, progress_label=progress_label, size_bytes=size_bytes, hits=hits
    )


def scan_text_files(folder_path):
    hits = {}
    candidate_names = set()

    acceptable_extensions = [
        '.txt', '.log', '.1', '.2', '.3', '.4', '.5', '.6', '.7', '.8', '.9', '.gz', '.zip', '.tar', '.tar.gz',
        '.rar', '.7z'
    ]

    # File name must contain meta|mess
    file_name_regex = re.compile(r'(meta|mess)', re.IGNORECASE)

    # Selection function
    def is_acceptable_file(file):
        return _is_acceptable_file(file, file_name_regex, acceptable_extensions)

    # Warning regex
    warning_regex = re.compile(
        r"Collection Warning: No Poster Found at https://raw\.githubusercontent\.com/"
        r"(?:Kometa-Team/People-Images(?:-[^/\s]+)?|meisnate12/Plex-Meta-Manager-People-[^/\s]+)"
        r"(.+?)\s+"
    )

    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = Path(root) / file
            archive_type = _detect_archive_type(file)

            # Plain files keep the original (name + extension) rule.
            # Archives are accepted by extension alone so we do not miss
            # meta/message files stored inside a generically named zip/gz.
            if archive_type is not None:
                if not _has_supported_extension(file, acceptable_extensions):
                    continue
            elif not is_acceptable_file(file):
                continue

            logging.info(f"Scanning {file_path}")
            print(f"Scanning {file_path}")

            if archive_type is not None:
                for nested_name, content, size_bytes in _iter_archive_texts(
                    file_path,
                    str(file_path),
                    file_path.name,
                    acceptable_extensions,
                    is_acceptable_file,
                ):
                    count = _scan_archive_text_stream(
                        io.StringIO(content),
                        warning_regex,
                        progress_label=f"Reading {nested_name}",
                        size_bytes=size_bytes,
                        hits=hits,
                    )
                    logging.info(f"Processed {nested_name}, found {count} hits.")
                    print(f"Processed {nested_name}, found {count} hits.")
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
            candidate_names.add(name)

    online_content, online_source = fetch_online_readme()
    if online_content is None:
        not_found_names = set(candidate_names)
        logging.warning(
            "Unable to verify against the online README; writing %d unverified candidate name(s).",
            len(not_found_names),
        )
        print(
            f"Unable to verify against the online README; wrote {len(not_found_names)} unverified candidate name(s)."
        )
    else:
        not_found_names = {name for name in candidate_names if name not in online_content}
        logging.info(
            "Verified %d candidate name(s) against the %s online README.",
            len(candidate_names),
            online_source,
        )

    not_found_path = CONFIG_DIR / "people_list.txt"
    with not_found_path.open("w", encoding="utf-8") as f:
        for name in sorted(not_found_names):
            f.write(f"{name}\n")

    if online_content is None:
        logging.info("Found %d candidate names without online verification.", len(not_found_names))
        print(f"Found {len(not_found_names)} candidate names without online verification.")
    else:
        logging.info("Found %d names not found in the online source.", len(not_found_names))
        print(f"Found {len(not_found_names)} names not found in the online source.")


def main():
    configure_stdio()
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
