"""Durable, hash-verified rollback for one local recovery attempt.

The caller owns this private workspace. A crash leaves a prepared journal which
must be reconciled against the caller's exact path set before another attempt.
Backups are retained, including after an unsuccessful restoration. This is not a
publication transaction or authorization receipt.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import uuid

from create_people_posters.people_recovery_records import _read, digest
from create_people_posters.people_workspaces import atomic_json, reject_links


def _sha(path):
    with path.open("rb") as handle:
        result = hashlib.file_digest(handle, "sha256").hexdigest()
    return result


class RecoveryTransaction:
    def __init__(self, root, name, paths):
        self.paths = sorted({Path(p).absolute() for p in paths}, key=str)
        self.identity = hashlib.sha256(name.encode("utf8")).hexdigest()
        self.root = Path(root) / self.identity
        self.journal = None
        self.value = None
        self.committed = False

    def _validate(self, value, folder):
        fields = {"schema_version", "identity", "state", "entries", "sha256"}
        if (type(value) is not dict or set(value) != fields or value["schema_version"] != 1
                or value["identity"] != self.identity or value["state"] not in {"prepared", "committed", "restored"}
                or value["sha256"] != digest({k: v for k, v in value.items() if k != "sha256"})
                or type(value["entries"]) is not list or len(value["entries"]) != len(self.paths)):
            raise ValueError("Recovery transaction journal is corrupt; backups retained")
        for index, (entry, path) in enumerate(zip(value["entries"], self.paths)):
            if (type(entry) is not dict or set(entry) != {"path", "before_sha256"}
                    or entry["path"] != str(path)):
                raise ValueError("Recovery transaction path membership changed; backups retained")
            reject_links(path)
            checksum = entry["before_sha256"]
            if checksum is not None:
                backup = folder / f"{index}.bin"
                reject_links(backup)
                if type(checksum) is not str or not backup.is_file() or _sha(backup) != checksum:
                    raise ValueError("Recovery backup is missing or corrupt; operator review required")

    def _save(self, journal, value, state):
        value = {k: v for k, v in value.items() if k != "sha256"} | {"state": state}
        value["sha256"] = digest(value)
        atomic_json(journal, value)
        return value

    def _restore(self, journal, value):
        self._validate(value, journal.parent)
        # Validate ALL backups before touching ANY target. Never erase the only
        # retained copy in response to an unreadable or substituted journal.
        for index, (entry, path) in enumerate(zip(value["entries"], self.paths)):
            if entry["before_sha256"] is None:
                if path.exists():
                    if not path.is_file():raise ValueError("Recovery target type changed")
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_name(path.name + ".recovery-restore")
                reject_links(temporary)
                shutil.copy2(journal.parent / f"{index}.bin", temporary)
                if _sha(temporary) != entry["before_sha256"]:
                    raise ValueError("Recovery restoration hash mismatch; backups retained")
                temporary.replace(path)
                if _sha(path) != entry["before_sha256"]:
                    raise ValueError("Recovery restoration verification failed; backups retained")
        self._save(journal, value, "restored")

    def __enter__(self):
        reject_links(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        # Reconcile interrupted work first. Completed journals/backups remain
        # evidence; no automatic pruning or timestamp-based trust is used.
        for journal in sorted(self.root.glob("*/transaction.json")):
            value = _read(journal)
            self._validate(value, journal.parent)
            if value["state"] == "prepared":self._restore(journal, value)
        folder = self.root / uuid.uuid4().hex
        folder.mkdir()
        entries = []
        for index, path in enumerate(self.paths):
            reject_links(path)
            checksum = None
            if path.exists():
                if not path.is_file():raise ValueError("Recovery target is not a file")
                checksum = _sha(path)
                backup = folder / f"{index}.bin"
                shutil.copy2(path, backup)
                if _sha(backup) != checksum or _sha(path) != checksum:
                    raise ValueError("Recovery backup changed during capture; artwork retained")
            entries.append({"path": str(path), "before_sha256": checksum})
        self.journal = folder / "transaction.json"
        self.value = self._save(self.journal, dict(schema_version=1, identity=self.identity, entries=entries), "prepared")
        return self

    def commit(self):
        self._validate(self.value, self.journal.parent)
        self.value = self._save(self.journal, self.value, "committed")
        self.committed = True

    def __exit__(self, kind, error, traceback):
        if not self.committed:self._restore(self.journal, self.value)
        return False
