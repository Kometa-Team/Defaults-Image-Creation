#!/usr/bin/env python3
"""
Bulk extract Kometa config sections from mess/meta logs, including logs stored
inside nested archives.

The script writes one deterministic `parsed_*.yml` file per source log that
contains a redacted config block. If the target file already exists, that source
is treated as already processed and skipped on reruns unless `--force` is used.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import logging
import os
import re
import shutil
import sys
import tarfile
import tempfile
import zipfile
from logging import FileHandler, StreamHandler
from pathlib import Path
from typing import Iterator

import yaml

try:
    import rarfile
except Exception:
    rarfile = None

try:
    import py7zr
except Exception:
    py7zr = None


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
DEFAULT_OUTPUT_DIR = CONFIG_DIR / "parsed_configs"
LOG_FILE = LOGS_DIR / f"{SCRIPT_PATH.stem}.log"

TEXT_EXTENSIONS = {
    ".txt", ".log", ".1", ".2", ".3", ".4", ".5", ".6", ".7", ".8", ".9"
}
ARCHIVE_EXTENSIONS = {".zip", ".tar", ".tar.gz", ".gz", ".rar", ".7z"}
MAX_ARCHIVE_RECURSION_DEPTH = 3
MAX_ARCHIVE_MEMBER_BYTES = 500 * 1024 * 1024
MAX_CAPTURE_LINES = 10000
SCHEMA_URL = "https://raw.githubusercontent.com/kometa-team/kometa/nightly/json-schema/config-schema.json"
RAR_BACKEND_MISSING_MESSAGE = "RAR backend not found (install UnRAR or 7-Zip, or add it to PATH)"

CONFIG_TAG_RE = re.compile(
    r"""
    ^(?:\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3}\]\s+)?   # optional timestamp
    \[(?P<file>config\.py):(?P<lineno>\d+)\]\s+                # [config.py:###]
    \[(?P<level>[A-Z]+)\]\s*\|(?P<body>.*)$                    # body after logger pipe
    """,
    re.VERBOSE,
)

_RAR_BACKEND_CHECKED = False
_RAR_BACKEND_PATH: str | None = None


def configure_stdio() -> None:
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


def setup_logging() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            FileHandler(LOG_FILE, encoding="utf-8", mode="w"),
            StreamHandler(sys.stdout),
        ],
        force=True,
    )


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


def has_numeric_log_suffix(name: str) -> bool:
    return bool(re.search(r"\.\d+$", name.lower()))


def has_supported_text_extension(name: str) -> bool:
    lowered = name.lower()
    return any(lowered.endswith(ext) for ext in TEXT_EXTENSIONS) or has_numeric_log_suffix(lowered)


def has_supported_scan_extension(name: str) -> bool:
    lowered = name.lower()
    return any(lowered.endswith(ext) for ext in TEXT_EXTENSIONS | ARCHIVE_EXTENSIONS) or has_numeric_log_suffix(lowered)


def is_candidate_log_name(name: str) -> bool:
    lowered = name.lower()
    return ("meta" in lowered or "mess" in lowered) and has_supported_text_extension(name)


def decode_bytes_with_fallback(content_bytes: bytes) -> str:
    try:
        return content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return content_bytes.decode("utf-8", errors="replace")


def warn_archive_skip(display_name: str, reason: str) -> None:
    logging.warning("Skipping %s: %s", display_name, reason)
    print(f"!! Skipping {display_name}: {reason}", file=sys.stderr, flush=True)


def _resolve_tool_path(candidate: str) -> str | None:
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
            resolved = _resolve_tool_path(candidate)
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


def extract_config_lines_from_stream(lines_iterable) -> list[str]:
    extraction_started = False
    extracted_lines: list[str] = []
    current_file = None

    for lineno, line in enumerate(lines_iterable, start=1):
        line = line.rstrip("\r\n")
        if not extraction_started:
            if "Redacted Config" in line:
                extraction_started = True
            continue

        if "Config Warning: " in line:
            logging.info("Config extraction ended on Config Warning at line %s", lineno)
            break
        if "Initializing cache database at" in line:
            logging.info("Config extraction ended on cache database marker at line %s", lineno)
            break

        match = CONFIG_TAG_RE.match(line)
        if not match:
            logging.info("Config extraction ended when config.py tag stopped matching at line %s", lineno)
            break

        file_name = match.group("file")
        body = match.group("body").rstrip(" |")
        if current_file is None:
            current_file = file_name
        elif file_name != "config.py":
            logging.info("Config extraction ended when file changed from %s to %s at line %s", current_file, file_name, lineno)
            break

        extracted_lines.append(body)

        if len(extracted_lines) >= MAX_CAPTURE_LINES:
            logging.warning("Config extraction hit MAX_CAPTURE_LINES=%s at line %s", MAX_CAPTURE_LINES, lineno)
            break

    if len(extracted_lines) > 1:
        extracted_lines = extracted_lines[:-1]
    return extracted_lines


def iter_candidate_configs(archive_source, display_name: str, archive_name: str, depth: int = 1) -> Iterator[tuple[str, list[str]]]:
    if depth > MAX_ARCHIVE_RECURSION_DEPTH:
        warn_archive_skip(display_name, f"nested archive depth exceeds {MAX_ARCHIVE_RECURSION_DEPTH}")
        return

    archive_type = detect_archive_type(archive_name)
    if archive_type is None:
        return

    def handle_member_bytes(member_name: str, content_bytes: bytes) -> Iterator[tuple[str, list[str]]]:
        base_name = os.path.basename(member_name.rstrip("/\\"))
        if not base_name:
            return

        nested_display_name = f"{display_name}::{member_name}"
        nested_archive_type = detect_archive_type(base_name)
        if nested_archive_type is not None and has_supported_scan_extension(base_name):
            yield from iter_candidate_configs(content_bytes, nested_display_name, base_name, depth + 1)
            return

        if not is_candidate_log_name(base_name):
            return

        with io.TextIOWrapper(io.BytesIO(content_bytes), encoding="utf-8", errors="replace") as text_reader:
            yield nested_display_name, extract_config_lines_from_stream(text_reader)

    try:
        if archive_type == "gz":
            extracted_name = archive_name[:-3] if archive_name.lower().endswith(".gz") else archive_name
            if not extracted_name:
                return
            nested_archive_type = detect_archive_type(extracted_name)
            if nested_archive_type is not None and has_supported_scan_extension(extracted_name):
                if isinstance(archive_source, (str, Path)):
                    with gzip.open(archive_source, "rb") as gz_file:
                        content_bytes = read_limited_bytes(gz_file, display_name)
                else:
                    with gzip.GzipFile(fileobj=io.BytesIO(archive_source), mode="rb") as gz_file:
                        content_bytes = read_limited_bytes(gz_file, display_name)
                if content_bytes is None:
                    return
                yield from handle_member_bytes(extracted_name, content_bytes)
            elif is_candidate_log_name(extracted_name):
                if isinstance(archive_source, (str, Path)):
                    with gzip.open(archive_source, "rt", encoding="utf-8", errors="replace") as text_reader:
                        yield f"{display_name}::{extracted_name}", extract_config_lines_from_stream(text_reader)
                else:
                    with gzip.GzipFile(fileobj=io.BytesIO(archive_source), mode="rb") as gz_file:
                        with io.TextIOWrapper(gz_file, encoding="utf-8", errors="replace") as text_reader:
                            yield f"{display_name}::{extracted_name}", extract_config_lines_from_stream(text_reader)
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
                        if nested_archive_type is not None and has_supported_scan_extension(base_name):
                            with zf.open(zi, "r") as raw:
                                content_bytes = read_limited_bytes(raw, nested_display_name, zi.file_size)
                            if content_bytes is None:
                                continue
                            yield from handle_member_bytes(inner_name, content_bytes)
                        elif is_candidate_log_name(base_name):
                            with zf.open(zi, "r") as raw, io.TextIOWrapper(raw, encoding="utf-8", errors="replace") as text_reader:
                                yield nested_display_name, extract_config_lines_from_stream(text_reader)
                    except Exception as exc:
                        logging.exception("Failed to read zip entry: %s", nested_display_name)
                        print(f"!! Failed to read zip entry: {nested_display_name} ({exc})", file=sys.stderr, flush=True)
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
                            if nested_archive_type is not None and has_supported_scan_extension(base_name):
                                content_bytes = read_limited_bytes(extracted, nested_display_name, member.size)
                                if content_bytes is None:
                                    continue
                                yield from handle_member_bytes(inner_name, content_bytes)
                            elif is_candidate_log_name(base_name):
                                with io.TextIOWrapper(extracted, encoding="utf-8", errors="replace") as text_reader:
                                    yield nested_display_name, extract_config_lines_from_stream(text_reader)
                    except Exception as exc:
                        logging.exception("Failed to read tar entry: %s", nested_display_name)
                        print(f"!! Failed to read tar entry: {nested_display_name} ({exc})", file=sys.stderr, flush=True)
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
                                if nested_archive_type is not None and has_supported_scan_extension(base_name):
                                    content_bytes = read_limited_bytes(raw, nested_display_name, member.file_size)
                                    if content_bytes is None:
                                        continue
                                    yield from handle_member_bytes(inner_name, content_bytes)
                                elif is_candidate_log_name(base_name):
                                    with io.TextIOWrapper(raw, encoding="utf-8", errors="replace") as text_reader:
                                        yield nested_display_name, extract_config_lines_from_stream(text_reader)
                        except Exception as exc:
                            logging.exception("Failed to read rar entry: %s", nested_display_name)
                            print(f"!! Failed to read rar entry: {nested_display_name} ({exc})", file=sys.stderr, flush=True)
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
            with tempfile.TemporaryDirectory(prefix="bulk_extract_7z_") as temp_dir:
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
                            if nested_archive_type is not None and has_supported_scan_extension(base_name):
                                size_bytes = extracted_path.stat().st_size
                                if size_bytes > MAX_ARCHIVE_MEMBER_BYTES:
                                    warn_archive_skip(nested_display_name, f"entry exceeds {MAX_ARCHIVE_MEMBER_BYTES} bytes")
                                    continue
                                yield from handle_member_bytes(inner_name, extracted_path.read_bytes())
                            elif is_candidate_log_name(base_name):
                                with extracted_path.open("r", encoding="utf-8", errors="replace") as text_reader:
                                    yield nested_display_name, extract_config_lines_from_stream(text_reader)
                        except Exception as exc:
                            logging.exception("Failed to read 7z entry: %s", nested_display_name)
                            print(f"!! Failed to read 7z entry: {nested_display_name} ({exc})", file=sys.stderr, flush=True)
            return
    except Exception as exc:
        logging.exception("Failed to open archive: %s", display_name)
        print(f"!! Failed to open archive: {display_name} ({exc})", file=sys.stderr, flush=True)


def iter_input_logs(input_directory: Path) -> Iterator[tuple[str, list[str]]]:
    for root, _, files in os.walk(input_directory):
        for file_name in files:
            file_path = Path(root) / file_name
            archive_type = detect_archive_type(file_name)

            if archive_type is not None:
                if not has_supported_scan_extension(file_name):
                    continue
                yield from iter_candidate_configs(file_path, str(file_path), file_path.name)
                continue

            if not is_candidate_log_name(file_name):
                continue

            try:
                with file_path.open("r", encoding="utf-8", errors="replace") as text_reader:
                    yield str(file_path), extract_config_lines_from_stream(text_reader)
            except Exception as exc:
                logging.exception("Failed to read log: %s", file_path)
                print(f"!! Failed to read log: {file_path} ({exc})", file=sys.stderr, flush=True)


def extract_config_lines_from_raw(raw_content: str) -> list[str]:
    return extract_config_lines_from_stream(raw_content.splitlines())


def strip_one_leading_space_each_line(text: str) -> str:
    return "\n".join(line[1:] if line.startswith(" ") else line for line in text.splitlines())


def build_output_text(source_name: str, yaml_text: str) -> str:
    lines = yaml_text.splitlines()
    header_lines = [f"# Extracted from: {source_name}"]
    if not lines or "yaml-language-server" not in lines[0]:
        header_lines.insert(0, f"# yaml-language-server: $schema={SCHEMA_URL}")
    return "\n".join(header_lines + ["", yaml_text]).rstrip() + "\n"


def validate_yaml_text(yaml_text: str) -> tuple[bool, str]:
    try:
        yaml.safe_load(yaml_text)
        return True, "valid"
    except yaml.YAMLError as exc:
        return False, str(exc).splitlines()[0]


def build_output_filename(source_name: str) -> str:
    parts = source_name.replace("\\", "/").split("::")
    tail_parts = []
    if len(parts) >= 2:
        tail_parts.append(Path(parts[-2]).name)
    tail_parts.append(Path(parts[-1]).name)
    readable = "__".join(part for part in tail_parts if part)
    readable = re.sub(r"[^A-Za-z0-9._-]+", "_", readable).strip("._-") or "config"
    readable = readable[:80]
    digest = hashlib.sha1(source_name.encode("utf-8", errors="surrogatepass")).hexdigest()[:10]
    return f"parsed_{readable}_{digest}.yml"


def process_log_source(source_name: str, config_lines: list[str], output_directory: Path, force: bool) -> str:
    output_path = output_directory / build_output_filename(source_name)
    if output_path.exists() and not force:
        logging.info("Skipping already extracted config: %s -> %s", source_name, output_path.name)
        return "skipped_existing"

    if not config_lines:
        logging.info("No config block found in %s", source_name)
        return "no_config"

    yaml_text = strip_one_leading_space_each_line("\n".join(config_lines))
    is_valid, validation_message = validate_yaml_text(yaml_text)
    output_text = build_output_text(source_name, yaml_text)
    output_path.write_text(output_text, encoding="utf-8")

    if is_valid:
        logging.info("Wrote %s", output_path)
        return "written_valid"

    logging.warning("Wrote %s with invalid YAML: %s", output_path, validation_message)
    return "written_invalid"


def main() -> None:
    configure_stdio()
    setup_logging()

    parser = argparse.ArgumentParser(description="Bulk extract Kometa config sections from mess/meta logs and archives.")
    parser.add_argument("--input_directory", help="Directory tree containing Kometa logs and/or archives.")
    parser.add_argument(
        "--output_directory",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Directory for parsed_*.yml files. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite parsed_*.yml files that already exist.")
    args = parser.parse_args()

    if args.input_directory:
        input_directory = Path(args.input_directory)
    else:
        user_input = input("Enter folder (press Enter for current directory): ").strip()
        input_directory = Path(user_input or ".")

    input_directory = input_directory.expanduser().resolve()
    output_directory = Path(args.output_directory).expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)

    logging.info("Logging -> %s", LOG_FILE)
    logging.info("Scanning %s", input_directory)
    logging.info("Writing parsed configs to %s", output_directory)

    counts = {
        "written_valid": 0,
        "written_invalid": 0,
        "skipped_existing": 0,
        "no_config": 0,
    }

    for source_name, content_bytes in iter_input_logs(input_directory):
        result = process_log_source(source_name, content_bytes, output_directory, args.force)
        counts[result] = counts.get(result, 0) + 1

    print(
        "Done. "
        f"valid={counts['written_valid']} "
        f"invalid={counts['written_invalid']} "
        f"skipped={counts['skipped_existing']} "
        f"no_config={counts['no_config']}"
    )


if __name__ == "__main__":
    main()
