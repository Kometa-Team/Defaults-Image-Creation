"""Owned recovery scratch, conservative resumable cleanup, no artwork deletion.

Only files inventoried by a completed operation can be removed. Legacy candidate
folders and rollback transactions are deliberately outside this protocol.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid
import unicodedata
from contextlib import contextmanager

from create_people_posters.people_workspaces import atomic_json, reject_links

class StorageBlocked(ValueError):
    """Closed, local cleanup reason containing no request or filesystem data."""


KIND = "kometa-edge-scratch-v1"
HEX = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[0-9a-f]{32}\Z")


def sha(path):
    reject_links(path)
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def files(root):
    """Never follow links/reparse points or admit special or multiply linked files."""
    root = Path(root)
    reject_links(root)
    if not root.exists():
        return {}
    if not root.is_dir():
        raise StorageBlocked("Unexpected scratch root type; retained")
    result = {}
    for folder, dirs, names in os.walk(root, followlinks=False, onerror=_walk_error):
        for name in dirs + names:
            path = Path(folder) / name
            reject_links(path)
            info = path.stat()
            if name in names:
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise StorageBlocked("Special or multiply linked scratch file; retained")
                result[path.relative_to(root).as_posix()] = dict(bytes=info.st_size, sha256=sha(path))
    return result


def _walk_error(error):
    raise error


def _relative(name):
    if (type(name) is not str or not name or "\\" in name or ":" in name
            or name.startswith("/") or any(p in {"", ".", ".."} for p in name.split("/"))):
        raise StorageBlocked("Unexpected scratch path; retained")
    return Path(name)


def directories(root):
    root = Path(root)
    reject_links(root)
    result = set()
    for folder, dirs, names in os.walk(root, followlinks=False, onerror=_walk_error):
        for name in dirs:
            path = Path(folder) / name
            reject_links(path)
            result.add(path.relative_to(root).as_posix())
    return result


def read_operation(folder):
    folder = Path(folder).absolute()
    reject_links(folder)
    if folder.parent.name != "operations" or not ID.fullmatch(folder.name):
        raise StorageBlocked("Unexpected operation path; retained")
    path = folder / "scratch.json"
    reject_links(path)
    if path.stat().st_size > 8 * 1024 * 1024:
        raise StorageBlocked("Scratch manifest too large; retained")
    value = json.loads(path.read_text(encoding="utf8"))
    if (type(value) is not dict or set(value) != {"kind", "id", "person", "created", "state", "files", "directories", "outputs"}
            or value["kind"] != KIND or value["id"] != folder.name
            or type(value["person"]) is not str or not HEX.fullmatch(value["person"])
            or type(value["created"]) not in {int, float} or not 0 < value["created"] < float("inf")
            or value["state"] not in {"retained", "ready", "cleaned"}
            or type(value["files"]) is not dict or type(value["outputs"]) is not dict
            or type(value["directories"]) is not list):
        raise StorageBlocked("Unowned or invalid scratch manifest; retained")
    for name in value["directories"]:
        _relative(name)
    if len(value["directories"]) != len(set(value["directories"])):
        raise StorageBlocked("Duplicate scratch directory membership; retained")
    for name, entry in value["files"].items():
        _relative(name)
        if (type(entry) is not dict or set(entry) != {"bytes", "sha256"}
                or type(entry["bytes"]) is not int or entry["bytes"] < 0
                or type(entry["sha256"]) is not str or not HEX.fullmatch(entry["sha256"])):
            raise StorageBlocked("Invalid scratch inventory; retained")
    for name, checksum in value["outputs"].items():
        if (not Path(name).is_absolute() or type(checksum) is not str or not HEX.fullmatch(checksum)
                or Path(name).resolve().is_relative_to(folder)):
            raise StorageBlocked("Invalid preserved output evidence; retained")
    return value


def _exclusive(path, token):
    reject_links(path)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="ascii") as handle:
        handle.write(token)
        handle.flush()
        os.fsync(handle.fileno())


def _release(path, token):
    reject_links(path)
    if path.read_text(encoding="ascii") != token:
        raise StorageBlocked("Operation lease ownership changed; retained")
    path.unlink()


@contextmanager
def cleanup_lock(folder):
    """OS lease is released even on process death; the inert lock file stays."""
    path = folder / "cleanup.lock"
    reject_links(path)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    locked = False
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise StorageBlocked("Unowned cleanup lease; retained")
        os.lseek(descriptor, 0, os.SEEK_SET)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError:
            raise StorageBlocked("Another process owns cleanup; retained") from None
        # On Windows a foreign byte lock also prevents reads. Inspect its
        # contents only after acquiring the lease, matching POSIX behavior.
        info = os.fstat(descriptor)
        if info.st_size == 0:
            os.write(descriptor, b"0")
        elif info.st_size != 1 or os.read(descriptor, 1) != b"0":
            raise StorageBlocked("Unowned cleanup lease contents; retained")
        yield
    finally:
        if locked:
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.name == "nt":
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


class Scratch:
    """Each attempt owns a UUID directory; a per-person lease prevents rollback races.

    Stale leases are never stolen automatically. Interrupted attempts remain
    retained for operator review, including staging and colorization files.
    """
    def __init__(self, root, name):
        if (type(name) is not str or not name or name in {".", ".."}
                or any(c in name for c in '<>:"/\\|?*\x00') or any(ord(c) < 32 for c in name)):
            raise StorageBlocked("Unsafe person filename; recovery retained")
        self.root = Path(root).absolute()
        self.identity = uuid.uuid4().hex
        self.person = hashlib.sha256(unicodedata.normalize("NFC", name).casefold().encode("utf8")).hexdigest()
        self.folder = self.root / "operations" / self.identity
        self.work = self.folder / "work"
        self.lease = self.root / "leases" / (self.person + ".lock")

    def __enter__(self):
        reject_links(self.folder)
        reject_links(self.lease)
        self.lease.parent.mkdir(parents=True, exist_ok=True)
        _exclusive(self.lease, self.identity)
        try:
            self.work.mkdir(parents=True)
            self.value = dict(kind=KIND, id=self.identity, person=self.person, created=time.time(),
                              state="retained", files={}, directories=[], outputs={})
            atomic_json(self.folder / "scratch.json", self.value)
            _exclusive(self.folder / "active", self.identity)
        except BaseException:
            _release(self.lease, self.identity)
            raise
        return self

    def __exit__(self, kind, error, traceback):
        try:
            self.value["files"] = files(self.work)
            self.value["directories"] = sorted(directories(self.work))
            atomic_json(self.folder / "scratch.json", self.value)
        finally:
            _release(self.folder / "active", self.identity)
            _release(self.lease, self.identity)
        return False

    def accept(self, paths):
        """Called only after transaction commit, final QA and durable checkpoint."""
        value = read_operation(self.folder)
        if (self.folder / "active").exists():
            raise StorageBlocked("Operation is still active; retained")
        outputs = {str(Path(p).absolute()): sha(p) for p in paths}
        if not outputs:
            raise StorageBlocked("No preserved outputs; scratch retained")
        value.update(state="ready", outputs=outputs)
        atomic_json(self.folder / "scratch.json", value)


def cleanup(folder, *, dry_run=True):
    """Remove only unchanged owned scratch; exact counts, safe after interruption.

    Missing inventoried files are allowed after interrupted cleanup. Added,
    changed, linked or unowned files block the whole operation before deletion.
    This API never visits publication destinations to perform a mutation.
    """
    folder = Path(folder).absolute()
    value = read_operation(folder)
    result = dict(id=folder.name, eligible_files=0, eligible_bytes=0, removed_files=0, recovered_bytes=0)
    if (folder / "active").exists():
        return result | {"blocked": "active operation (including interrupted processing)"}
    if value["state"] not in {"ready", "cleaned"} or not value["outputs"]:
        return result | {"blocked": "processing incomplete or no preserved output evidence"}
    if not dry_run:
        with cleanup_lock(folder):
            return _cleanup(folder, dry_run=False)
    return _cleanup(folder, dry_run=True)


def _cleanup(folder, *, dry_run):
    # Read again under the OS lease; a prior cleaner may have finished meanwhile.
    value = read_operation(folder)
    result = dict(id=folder.name, eligible_files=0, eligible_bytes=0, removed_files=0, recovered_bytes=0)
    try:
        allowed = {"scratch.json", "work", "cleanup.lock"}
        for entry in folder.iterdir():
            reject_links(entry)
            if entry.name not in allowed:
                raise StorageBlocked("Unowned operation entry; retained")
        # Validate complete membership and ALL preserved output bytes first.
        current = files(folder / "work")
        current_directories = directories(folder / "work")
        if not current_directories <= set(value["directories"]):
            raise StorageBlocked("Unowned scratch directory; retained")
        for name, entry in current.items():
            if value["files"].get(name) != entry:
                raise StorageBlocked("Unowned or changed scratch file; retained")
        for name, checksum in value["outputs"].items():
            if sha(Path(name)) != checksum:
                raise StorageBlocked("Preserved output missing or changed; retained")
        result.update(eligible_files=len(current), eligible_bytes=sum(e["bytes"] for e in current.values()),
                      eligible_paths=sorted(current))
        if dry_run:
            return result
        for name, entry in current.items():
            path = folder / "work" / _relative(name)
            # Recheck immediately before each unlink; never recursive delete.
            if path.stat().st_nlink != 1 or sha(path) != entry["sha256"]:
                raise StorageBlocked("Scratch changed during cleanup; remaining files retained")
            path.unlink()
            result["removed_files"] += 1
            result["recovered_bytes"] += entry["bytes"]
        # Remove only empty owned directories, deepest first. No recursive delete.
        ordered_directories = sorted((folder / "work" / p for p in current_directories),
                                     key=lambda p: len(p.parts), reverse=True)
        for path in ordered_directories:
            reject_links(path)
            path.rmdir()
        value["state"] = "cleaned"
        atomic_json(folder / "scratch.json", value)
        return result
    except OSError:
        return result | {"blocked": "filesystem interruption; remaining scratch retained; retry this operation"}
    except StorageBlocked as exc:
        if result["removed_files"]:
            return result | {"blocked": exc.args[0]}
        raise
