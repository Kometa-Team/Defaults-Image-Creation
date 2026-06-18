import argparse
import collections
import io
import logging
import os
import re
import shutil
import sys
import tarfile
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import gzip

try:
    import rarfile
except Exception:
    rarfile = None

try:
    import py7zr
except Exception:
    py7zr = None


def ensure_config_dir(script_file: str | Path) -> Path:
    base_dir = Path(script_file).resolve().parent
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    cfg = base_dir / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    return cfg


CONFIG_DIR = ensure_config_dir(__file__)
HEARTBEAT_SECS = 1.0
MAX_ARCHIVE_RECURSION_DEPTH = 3
MAX_ARCHIVE_MEMBER_BYTES = 500 * 1024 * 1024
SUMMARY_MAX_GROUPS = 100
RAR_BACKEND_MISSING_MESSAGE = "RAR backend not found (install UnRAR or 7-Zip, or add it to PATH)"
TRACEBACK_START = "Traceback (most recent call last):"
TIMESTAMP_LINE_REGEX = re.compile(
    r"^\s*\[?\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}\]?"
)
FRAME_LINE_REGEX = re.compile(r'^\s*File "(?P<path>.+?)", line (?P<line>\d+), in (?P<func>.+)$')
ERROR_GROUP_REGEX = re.compile(r"^(?P<group>.*?\b(?:Error|Exception|Failed)\b)")
_RAR_BACKEND_CHECKED = False
_RAR_BACKEND_PATH: str | None = None


@dataclass
class TracebackBlock:
    source: str
    start_line: int
    lines: list[str]
    traceback_number: int | None = None


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
    logging.info("Logging initialized -> %s", log_file)
    return log_file


def _human_mb(n_bytes: float) -> str:
    return f"{n_bytes / 1_000_000:.1f}MB"


def _safe_getsize(path: Path) -> int | None:
    try:
        return os.path.getsize(path)
    except Exception:
        return None


def _has_supported_extension(name: str, acceptable_extensions: list[str]) -> bool:
    lowered = name.lower()
    return any(lowered.endswith(ext) for ext in acceptable_extensions) or bool(re.search(r"\.\d+$", lowered))


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


def _resolve_tool_path(candidate: str) -> str | None:
    if os.path.isabs(candidate):
        return candidate if os.path.exists(candidate) else None
    return shutil.which(candidate)


def _ensure_rar_backend() -> str | None:
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


def _read_limited_bytes(reader, display_name: str, size_hint: int | None = None) -> bytes | None:
    if size_hint is not None and size_hint > MAX_ARCHIVE_MEMBER_BYTES:
        _warn_archive_skip(display_name, f"entry exceeds {MAX_ARCHIVE_MEMBER_BYTES} bytes")
        return None

    content_bytes = reader.read(MAX_ARCHIVE_MEMBER_BYTES + 1)
    if len(content_bytes) > MAX_ARCHIVE_MEMBER_BYTES:
        _warn_archive_skip(display_name, f"entry exceeds {MAX_ARCHIVE_MEMBER_BYTES} bytes")
        return None
    return content_bytes


def _scan_stream_for_tracebacks(
    fobj: io.TextIOBase,
    *,
    progress_label: str,
    size_bytes: int | None,
    source_name: str,
) -> list[TracebackBlock]:
    last_print = time.time()
    bytes_read = 0
    line_number = 0
    blocks: list[TracebackBlock] = []
    active_lines: list[str] = []
    active_start_line: int | None = None

    for raw_line in fobj:
        line_number += 1
        bytes_read += len(raw_line)
        line = raw_line.rstrip("\r\n")

        if active_lines:
            if TIMESTAMP_LINE_REGEX.match(line):
                blocks.append(
                    TracebackBlock(
                        source=source_name,
                        start_line=active_start_line or line_number,
                        lines=active_lines[:],
                    )
                )
                active_lines = []
                active_start_line = None
            else:
                active_lines.append(line)
                now = time.time()
                if now - last_print >= HEARTBEAT_SECS:
                    if size_bytes and size_bytes > 0:
                        pct = min(100, int((bytes_read / size_bytes) * 100))
                        print(f"{progress_label}: {_human_mb(bytes_read)} / {_human_mb(size_bytes)} ({pct}%) ...")
                    else:
                        print(f"{progress_label}: processed ~{_human_mb(bytes_read)} ...")
                    last_print = now
                continue

        if TRACEBACK_START in line:
            active_lines = [line]
            active_start_line = line_number

        now = time.time()
        if now - last_print >= HEARTBEAT_SECS:
            if size_bytes and size_bytes > 0:
                pct = min(100, int((bytes_read / size_bytes) * 100))
                print(f"{progress_label}: {_human_mb(bytes_read)} / {_human_mb(size_bytes)} ({pct}%) ...")
            else:
                print(f"{progress_label}: processed ~{_human_mb(bytes_read)} ...")
            last_print = now

    if active_lines:
        blocks.append(
            TracebackBlock(
                source=source_name,
                start_line=active_start_line or line_number,
                lines=active_lines,
            )
        )

    return blocks


def _iter_archive_texts(
    archive_source,
    display_name: str,
    archive_name: str,
    acceptable_extensions: list[str],
    is_acceptable_file,
    depth: int = 1,
):
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
            extracted_name = archive_name[:-3] if archive_name.lower().endswith(".gz") else archive_name
            if not extracted_name:
                return
            nested_archive_type = _detect_archive_type(extracted_name)
            if nested_archive_type is not None and _has_supported_extension(extracted_name, acceptable_extensions):
                if isinstance(archive_source, (str, Path)):
                    with gzip.open(archive_source, "rb") as gz_file:
                        content_bytes = _read_limited_bytes(gz_file, display_name)
                else:
                    with gzip.GzipFile(fileobj=io.BytesIO(archive_source), mode="rb") as gz_file:
                        content_bytes = _read_limited_bytes(gz_file, display_name)
                if content_bytes is None:
                    return
                yield from handle_member(extracted_name, content_bytes)
            elif is_acceptable_file(extracted_name):
                nested_display_name = f"{display_name}::{extracted_name}"
                if isinstance(archive_source, (str, Path)):
                    with gzip.open(archive_source, "rt", encoding="utf-8", errors="replace") as text_reader:
                        yield nested_display_name, text_reader.read(), None
                else:
                    with gzip.GzipFile(fileobj=io.BytesIO(archive_source), mode="rb") as gz_file:
                        with io.TextIOWrapper(gz_file, encoding="utf-8", errors="replace") as text_reader:
                            yield nested_display_name, text_reader.read(), None
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
                        nested_archive_type = _detect_archive_type(base_name)
                        if nested_archive_type is not None and _has_supported_extension(base_name, acceptable_extensions):
                            with zf.open(zi, "r") as raw:
                                content_bytes = _read_limited_bytes(raw, nested_display_name, zi.file_size)
                            if content_bytes is None:
                                continue
                            yield from handle_member(inner_name, content_bytes, zi.file_size)
                        elif is_acceptable_file(base_name):
                            with zf.open(zi, "r") as raw:
                                content_bytes = raw.read()
                            yield nested_display_name, content_bytes.decode("utf-8", errors="replace"), zi.file_size
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
                        base_name = os.path.basename(inner_name.rstrip("/\\"))
                        nested_archive_type = _detect_archive_type(base_name)
                        extracted = tf.extractfile(member)
                        if extracted is None:
                            continue
                        with extracted:
                            if nested_archive_type is not None and _has_supported_extension(base_name, acceptable_extensions):
                                content_bytes = _read_limited_bytes(extracted, nested_display_name, member.size)
                                if content_bytes is None:
                                    continue
                                yield from handle_member(inner_name, content_bytes, member.size)
                            elif is_acceptable_file(base_name):
                                content_bytes = extracted.read()
                                yield nested_display_name, content_bytes.decode("utf-8", errors="replace"), member.size
                    except Exception as exc:
                        logging.exception("Failed to read tar entry: %s", nested_display_name)
                        print(f"!! Failed to read tar entry: {nested_display_name} ({exc})", file=sys.stderr)
            return

        if archive_type == "rar":
            if rarfile is None:
                _warn_archive_skip(display_name, "rarfile is unavailable")
                return
            if _ensure_rar_backend() is None:
                _warn_archive_skip(display_name, RAR_BACKEND_MISSING_MESSAGE)
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
                            nested_archive_type = _detect_archive_type(base_name)
                            with rf.open(member) as raw:
                                if nested_archive_type is not None and _has_supported_extension(base_name, acceptable_extensions):
                                    content_bytes = _read_limited_bytes(raw, nested_display_name, member.file_size)
                                    if content_bytes is None:
                                        continue
                                    yield from handle_member(inner_name, content_bytes, member.file_size)
                                elif is_acceptable_file(base_name):
                                    content_bytes = raw.read()
                                    yield nested_display_name, content_bytes.decode("utf-8", errors="replace"), member.file_size
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
            with tempfile.TemporaryDirectory(prefix="scan_7z_") as temp_dir:
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
                            nested_archive_type = _detect_archive_type(base_name)
                            size_bytes = extracted_path.stat().st_size
                            if nested_archive_type is not None and _has_supported_extension(base_name, acceptable_extensions):
                                if size_bytes > MAX_ARCHIVE_MEMBER_BYTES:
                                    _warn_archive_skip(nested_display_name, f"entry exceeds {MAX_ARCHIVE_MEMBER_BYTES} bytes")
                                    continue
                                yield from handle_member(inner_name, extracted_path.read_bytes(), size_bytes)
                            elif is_acceptable_file(base_name):
                                yield nested_display_name, extracted_path.read_text(encoding="utf-8", errors="replace"), size_bytes
                        except Exception as exc:
                            logging.exception("Failed to read 7z entry: %s", nested_display_name)
                            print(f"!! Failed to read 7z entry: {nested_display_name} ({exc})", file=sys.stderr)
            return
    except Exception as exc:
        logging.exception("Failed to open archive: %s", display_name)
        print(f"!! Failed to open archive: {display_name} ({exc})", file=sys.stderr)


def _write_traceback_report(output_path: Path, blocks: list[TracebackBlock]) -> None:
    with output_path.open("w", encoding="utf-8") as f:
        if not blocks:
            f.write("No tracebacks found.\n")
            return

        for index, block in enumerate(blocks, start=1):
            if index > 1:
                f.write("\n" + ("=" * 100) + "\n\n")
            f.write(f"Traceback #{index}\n")
            f.write(f"Source: {block.source}\n")
            f.write(f"Start line: {block.start_line}\n")
            f.write("-" * 100 + "\n")
            for line in block.lines:
                f.write(f"{line}\n")


def _initialize_traceback_report(output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as f:
        f.write("Traceback scan in progress.\n")


def _append_traceback_block(output_path: Path, block: TracebackBlock, index: int) -> None:
    with output_path.open("a", encoding="utf-8") as f:
        if index > 1:
            f.write("\n" + ("=" * 100) + "\n\n")
        else:
            f.write("\n\n")
        f.write(f"Traceback #{index}\n")
        f.write(f"Source: {block.source}\n")
        f.write(f"Start line: {block.start_line}\n")
        f.write("-" * 100 + "\n")
        for line in block.lines:
            f.write(f"{line}\n")


def _finalize_traceback_report(output_path: Path, count: int) -> None:
    if count != 0:
        return
    with output_path.open("w", encoding="utf-8") as f:
        f.write("No tracebacks found.\n")


def _collect_candidate_files(folder_path: Path, output_file: Path, acceptable_extensions: list[str]) -> list[Path]:
    candidate_files: list[Path] = []
    last_print = time.time()

    def is_acceptable_file(file_name: str) -> bool:
        return _has_supported_extension(file_name, acceptable_extensions)

    logging.info("Counting top-level files under %s", folder_path)
    print(f"Counting top-level files under {folder_path} ...")

    output_resolved = output_file.resolve()
    for root, _, files in os.walk(folder_path):
        for file_name in files:
            file_path = Path(root) / file_name
            if file_path.resolve() == output_resolved:
                continue

            archive_type = _detect_archive_type(file_name)
            if archive_type is not None:
                if not _has_supported_extension(file_name, acceptable_extensions):
                    continue
            elif not is_acceptable_file(file_name):
                continue

            candidate_files.append(file_path)
            now = time.time()
            if now - last_print >= HEARTBEAT_SECS:
                print(f"Counting top-level files: {len(candidate_files)} found so far ...")
                last_print = now

    return candidate_files


def _parse_traceback_report(report_path: Path) -> list[TracebackBlock]:
    if not report_path.exists():
        raise FileNotFoundError(f"Traceback report not found: {report_path}")

    lines = report_path.read_text(encoding="utf-8", errors="replace").splitlines()
    blocks: list[TracebackBlock] = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith("Traceback #"):
            i += 1
            continue

        try:
            traceback_number = int(line.split("#", 1)[1].strip())
        except Exception:
            traceback_number = None

        source = ""
        start_line = 0

        if i + 1 < len(lines) and lines[i + 1].startswith("Source: "):
            source = lines[i + 1][len("Source: "):]
        if i + 2 < len(lines) and lines[i + 2].startswith("Start line: "):
            try:
                start_line = int(lines[i + 2][len("Start line: "):].strip())
            except ValueError:
                start_line = 0

        i += 4
        block_lines: list[str] = []
        while i < len(lines):
            current = lines[i]
            if current.startswith("Traceback #") or current == ("=" * 100):
                break
            block_lines.append(current)
            i += 1

        while block_lines and not block_lines[-1].strip():
            block_lines.pop()

        blocks.append(
            TracebackBlock(
                source=source,
                start_line=start_line,
                lines=block_lines,
                traceback_number=traceback_number,
            )
        )

        while i < len(lines) and not lines[i].startswith("Traceback #"):
            i += 1

    return blocks


def _extract_exception_line(block: TracebackBlock) -> str:
    for line in reversed(block.lines):
        stripped = _sanitize_traceback_terminal_line(line)
        if not stripped:
            continue
        if FRAME_LINE_REGEX.match(stripped):
            continue
        if TRACEBACK_START in stripped:
            continue
        if _is_junk_terminal_line(stripped):
            continue
        if _looks_like_terminal_error_line(stripped):
            return stripped
    return "(no exception line)"


def _sanitize_traceback_terminal_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    if "|" in stripped:
        stripped = stripped.split("|", 1)[1].strip()
    return re.sub(r"\s+", " ", stripped).strip()


def _is_junk_terminal_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped in {"|", "#", "```", "``", ">>>", "> >>>"}:
        return True
    if re.fullmatch(r"[=\-_*#|`>.<]{3,}", stripped):
        return True
    if re.match(r"^(PS |\(.*?\) PS |[A-Za-z]:\\|root@|klue@|pk2@|➜ )", stripped):
        return True
    if stripped.startswith(("http://", "https://")):
        return True
    if stripped.startswith(("Options:", "Params:", "Arguments:")):
        return True
    if stripped.startswith(("Collection Run Time:", "Overlaying:", "Parsing Page ", "Current")):
        return True
    if stripped.startswith(("Other sorting options can be found at ", "** Press ANY KEY")):
        return True
    if stripped.startswith(("in \"", "in '//", "in \"C:", "in \"//")):
        return True
    if stripped.startswith(("[ls.io-init]", "Loaded", "Finished")):
        return True
    return False


def _looks_like_terminal_error_line(line: str) -> bool:
    stripped = line.strip()
    lowered = stripped.lower()

    if re.match(r"^[A-Za-z_][A-Za-z0-9_\.]*\([^)]*\)$", stripped):
        return False
    if re.match(r"^[A-Za-z_][A-Za-z0-9_\.\[\]'\"]*\s*=\s*.+$", stripped):
        return False
    if stripped in {"(no exception line)", "(unknown)"}:
        return False
    if ":" in stripped:
        return True

    signal_fragments = [
        " error",
        "exception",
        "failed",
        "invalid",
        "unable",
        "cannot",
        "can't",
        " not ",
        " no ",
        "timeout",
        "timed out",
        "unauthorized",
        "malformed",
        "unhashable",
        "missing",
        "unsupported",
    ]
    return any(fragment in lowered for fragment in signal_fragments)


def _normalize_exception_group(exception_line: str) -> str:
    sanitized = _sanitize_traceback_terminal_line(exception_line)
    if not sanitized:
        return "(unknown)"

    match = ERROR_GROUP_REGEX.match(sanitized)
    if match:
        return match.group("group").strip(" :")

    if ":" in sanitized:
        return sanitized.split(":", 1)[0].strip()

    return sanitized


def _extract_exception_type(exception_line: str) -> str:
    return _normalize_exception_group(exception_line)


def _normalize_frame_path(path: str) -> str:
    parts = [part for part in re.split(r"[\\/]+", path) if part]
    if not parts:
        return path
    return "/".join(parts[-3:]) if len(parts) > 3 else "/".join(parts)


def _extract_frames(block: TracebackBlock) -> list[dict[str, str]]:
    frames: list[dict[str, str]] = []
    for line in block.lines:
        match = FRAME_LINE_REGEX.match(line)
        if not match:
            continue
        frame_path = match.group("path")
        frames.append(
            {
                "path": frame_path,
                "normalized_path": _normalize_frame_path(frame_path),
                "line": match.group("line"),
                "func": match.group("func").strip(),
            }
        )
    return frames


def _select_last_app_frame(frames: list[dict[str, str]]) -> str:
    if not frames:
        return "(no frame found)"

    for frame in reversed(frames):
        lowered = frame["path"].replace("\\", "/").lower()
        if "/site-packages/" in lowered:
            continue
        return f'{frame["normalized_path"]}:{frame["line"]} in {frame["func"]}'

    frame = frames[-1]
    return f'{frame["normalized_path"]}:{frame["line"]} in {frame["func"]}'


def _write_summary_section(f, title: str, rows: list[str]) -> None:
    f.write(f"{title}\n")
    f.write(f"{'-' * len(title)}\n")
    if not rows:
        f.write("None\n\n")
        return
    for row in rows:
        f.write(f"{row}\n")
    f.write("\n")


def summarize_traceback_report(report_path: Path, summary_path: Path) -> list[TracebackBlock]:
    blocks = _parse_traceback_report(report_path)
    exception_line_counter: collections.Counter[str] = collections.Counter()
    normalized_group_counter: collections.Counter[str] = collections.Counter()
    source_counter: collections.Counter[str] = collections.Counter()
    grouped_stats: dict[tuple[str, str], dict[str, object]] = {}

    for block in blocks:
        exception_line = _extract_exception_line(block)
        normalized_group = _normalize_exception_group(exception_line)
        frames = _extract_frames(block)
        last_app_frame = _select_last_app_frame(frames)
        group_key = (normalized_group, last_app_frame)

        exception_line_counter[exception_line] += 1
        normalized_group_counter[normalized_group] += 1
        source_counter[block.source] += 1

        if group_key not in grouped_stats:
            grouped_stats[group_key] = {
                "count": 0,
                "sources": set(),
                "sample_source": block.source,
                "sample_start_line": block.start_line,
                "sample_traceback_number": block.traceback_number,
                "sample_exception_line": exception_line,
            }
        grouped_stats[group_key]["count"] = int(grouped_stats[group_key]["count"]) + 1
        grouped_stats[group_key]["sources"].add(block.source)

    sorted_groups = sorted(
        grouped_stats.items(),
        key=lambda item: (-int(item[1]["count"]), -len(item[1]["sources"]), item[0][0], item[0][1]),
    )
    top_group_rows: list[str] = []
    for index, ((normalized_group, last_app_frame), stats) in enumerate(sorted_groups[:SUMMARY_MAX_GROUPS], start=1):
        top_group_rows.append(
            f"{index}. count={stats['count']} | distinct_sources={len(stats['sources'])} | "
            f"group={normalized_group} | last_app_frame={last_app_frame} | "
            f"sample_last_line={stats['sample_exception_line']} | "
            f"sample_source={stats['sample_source']} | sample_start_line={stats['sample_start_line']} | "
            f"sample_traceback={stats['sample_traceback_number']}"
        )

    top_exception_line_rows = [
        f"{index}. count={count} | exception={exception_line}"
        for index, (exception_line, count) in enumerate(
            exception_line_counter.most_common(SUMMARY_MAX_GROUPS), start=1
        )
    ]
    top_normalized_group_rows = [
        f"{index}. count={count} | group={normalized_group}"
        for index, (normalized_group, count) in enumerate(
            normalized_group_counter.most_common(SUMMARY_MAX_GROUPS), start=1
        )
    ]
    top_source_rows = [
        f"{index}. count={count} | source={source}"
        for index, (source, count) in enumerate(source_counter.most_common(SUMMARY_MAX_GROUPS), start=1)
    ]

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as f:
        f.write(f"Summary generated from: {report_path}\n")
        f.write(f"Total tracebacks: {len(blocks)}\n")
        f.write(f"Distinct sources: {len(source_counter)}\n")
        f.write(f"Distinct exception lines: {len(exception_line_counter)}\n")
        f.write(f"Distinct normalized last-line groups: {len(normalized_group_counter)}\n")
        f.write(f"Distinct normalized group + last app frame groups: {len(grouped_stats)}\n\n")
        _write_summary_section(f, "Top Exception Lines", top_exception_line_rows)
        _write_summary_section(f, "Top Normalized Group + Last App Frame Groups", top_group_rows)
        _write_summary_section(f, "Top Normalized Last-Line Groups", top_normalized_group_rows)
        _write_summary_section(f, "Top Source Files", top_source_rows)

    logging.info("Wrote traceback summary for %d traceback(s) to %s", len(blocks), summary_path)
    print(f"Wrote traceback summary for {len(blocks)} traceback(s) to {summary_path}")
    return blocks


def scan_text_files(folder_path: Path, output_file: Path) -> list[TracebackBlock]:
    all_blocks: list[TracebackBlock] = []
    total_blocks = 0
    acceptable_extensions = [".txt", ".log", ".gz", ".zip", ".tar", ".tar.gz", ".rar", ".7z"]

    _initialize_traceback_report(output_file)

    def is_acceptable_file(file_name: str) -> bool:
        return _has_supported_extension(file_name, acceptable_extensions)

    candidate_files = _collect_candidate_files(folder_path, output_file, acceptable_extensions)
    total_candidate_files = len(candidate_files)
    logging.info(
        "Found %d top-level file(s) to scan. Nested archive members are not included in this count.",
        total_candidate_files,
    )
    print(
        f"Found {total_candidate_files} top-level file(s) to scan. "
        "Nested archive members are not included in this count."
    )

    for top_level_index, file_path in enumerate(candidate_files, start=1):
        archive_type = _detect_archive_type(file_path.name)
        progress_prefix = f"[{top_level_index}/{total_candidate_files}]"

        logging.info("%s Scanning %s", progress_prefix, file_path)
        print(f"{progress_prefix} Scanning {file_path}")

        if archive_type is not None:
            for nested_name, content, size_bytes in _iter_archive_texts(
                file_path,
                str(file_path),
                file_path.name,
                acceptable_extensions,
                is_acceptable_file,
            ):
                blocks = _scan_stream_for_tracebacks(
                    io.StringIO(content),
                    progress_label=f"{progress_prefix} Reading {nested_name}",
                    size_bytes=size_bytes,
                    source_name=nested_name,
                )
                all_blocks.extend(blocks)
                for block in blocks:
                    total_blocks += 1
                    _append_traceback_block(output_file, block, total_blocks)
                logging.info("Processed %s, found %d traceback(s).", nested_name, len(blocks))
                print(f"Processed {nested_name}, found {len(blocks)} traceback(s).")
            continue

        try:
            size_bytes = _safe_getsize(file_path)
            with file_path.open("r", encoding="utf-8", errors="replace") as f:
                blocks = _scan_stream_for_tracebacks(
                    f,
                    progress_label=f"{progress_prefix} Reading {file_path}",
                    size_bytes=size_bytes,
                    source_name=str(file_path),
                )
            all_blocks.extend(blocks)
            for block in blocks:
                total_blocks += 1
                _append_traceback_block(output_file, block, total_blocks)
            logging.info("Processed %s, found %d traceback(s).", file_path, len(blocks))
            print(f"Processed {file_path}, found {len(blocks)} traceback(s).")
        except Exception as exc:
            logging.exception("Failed to read file: %s", file_path)
            print(f"!! Failed to read file: {file_path} ({exc})", file=sys.stderr)

    _finalize_traceback_report(output_file, total_blocks)
    logging.info("Wrote %d traceback(s) to %s", total_blocks, output_file)
    print(f"Wrote {total_blocks} traceback(s) to {output_file}")
    return all_blocks


def main():
    configure_stdio()
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Scan logs and archives for traceback blocks and write them to a report file."
    )
    parser.add_argument(
        "--input",
        dest="input_directory",
        help="Alias for --input_directory.",
    )
    parser.add_argument(
        "--input_directory",
        dest="input_directory",
        help="Directory to scan. If omitted, you will be prompted.",
    )
    parser.add_argument(
        "--output_file",
        help="Output file path. Defaults to config/traceback_errors.txt next to this script.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Generate a summary from an existing traceback report. If used with --input_directory, scan first, then summarize.",
    )
    parser.add_argument(
        "--summary_input",
        help="Existing traceback report to summarize. Defaults to the resolved --output_file path.",
    )
    parser.add_argument(
        "--summary_output",
        help="Summary output path. Defaults to config/traceback_summary.txt next to this script.",
    )
    args = parser.parse_args()

    output_file = Path(args.output_file) if args.output_file else (CONFIG_DIR / "traceback_errors.txt")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    summary_input = Path(args.summary_input) if args.summary_input else output_file
    summary_output = Path(args.summary_output) if args.summary_output else (CONFIG_DIR / "traceback_summary.txt")

    if args.input_directory:
        folder_path = Path(args.input_directory)
        scan_text_files(folder_path, output_file)
        if args.summary:
            summarize_traceback_report(summary_input, summary_output)
        return

    if args.summary:
        summarize_traceback_report(summary_input, summary_output)
        return

    user_input = input("Enter folder (press Enter for current directory): ").strip()
    folder_path = Path(user_input or ".")
    scan_text_files(folder_path, output_file)


if __name__ == "__main__":
    main()
