"""Portable identities, bounded serialization, diagnostics and filesystem safety."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import unicodedata

import yaml


class BulkError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class Conflict(BulkError):
    def __init__(self, message="State changed; reload the current version"):
        super().__init__("stale_version", message)


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    message: str
    identities: tuple[str, ...] = ()
    details: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative_path(value):
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise BulkError("unsafe_path", "Expected a bounded nonempty relative POSIX path")
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
    if any(ord(c) < 32 or ord(c) == 127 or c in '\\:<>"|?*' for c in value):
        raise BulkError("unsafe_path", "Invalid filename character")
    for part in value.split("/"):
        if part in {"", ".", ".."} or part.endswith((" ", ".")) or part.split(".")[0].casefold() in reserved:
            raise BulkError("unsafe_path", "Unsafe filename component")
    return value


def path_key(value):
    return unicodedata.normalize("NFC", relative_path(value)).casefold()


def reject_links(path):
    path = Path(path).absolute()
    for item in [*reversed(path.parents), path]:
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise BulkError("unsafe_link", "Symlinks and Windows reparse points are not permitted")
    return path


def confined(root, relative, *, must_exist=False):
    relative_path(relative)
    root = reject_links(root).resolve()
    path = reject_links(root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise BulkError("unsafe_path", "Path escapes its declared root")
    if must_exist and not path.is_file():
        raise BulkError("missing_input", f"Required input is missing: {relative}")
    if must_exist:
        from .asset_cases import exact
        path = exact(root, relative)
    return path


def normalize_hex(value):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", value.strip()):
        raise BulkError("invalid_color", "Use six-digit #RRGGBB colors")
    return value.strip().upper()


def atomic_bytes(path, data, *, replace=False):
    path = reject_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_links(path.parent)
    descriptor, name = tempfile.mkstemp(prefix=".bulk-", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        reject_links(path)
        if replace:
            os.replace(temporary, path)
        else:
            # Atomic visibility and exclusive creation on NTFS and POSIX filesystems.
            os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


class SafeLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise BulkError("invalid_yaml", "YAML keys must be unique strings")
        result[key] = loader.construct_object(value_node)
    return result


SafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_yaml(path, limit=2_000_000):
    path = reject_links(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise BulkError("invalid_yaml", "YAML input is absent or exceeds the size limit")
    text = path.read_text(encoding="utf-8-sig")
    try:
        depth = 0
        for event in yaml.parse(text):
            if isinstance(event, (yaml.events.AliasEvent,)) or getattr(event, "anchor", None):
                raise BulkError("invalid_yaml", "Use explicit profiles, not YAML anchors/aliases")
            if isinstance(event, (yaml.events.MappingStartEvent, yaml.events.SequenceStartEvent)):
                depth += 1
            if depth > 40:
                raise BulkError("invalid_yaml", "YAML nesting exceeds the limit")
            if isinstance(event, (yaml.events.MappingEndEvent, yaml.events.SequenceEndEvent)):
                depth -= 1
        result = yaml.load(text, Loader=SafeLoader)
        canonical(result)
        return result
    except (yaml.YAMLError, TypeError, ValueError, RecursionError) as error:
        raise BulkError("invalid_yaml", "Invalid or non-JSON-compatible YAML") from error
