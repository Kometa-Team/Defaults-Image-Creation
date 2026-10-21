"""Isolated additive Package E sidecars; immutable objects and CAS revisions.

No default root and no approval state machine. The archive accepts typed evidence
as data, not authority. Production Store migrations, reviews and receipts remain
untouched. Callers cannot open an existing Package E cache through this adapter.
"""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from ..common import BulkError, Conflict, atomic_bytes, canonical, confined, reject_links
from ..config import Config
from ..state import Store
from .models import Contract, Record, RegistryDocument, decode_json, read_document, read_json_bytes
from .registry import require_hash


MARKER = {"kind": "isolated-category-contract-state", "schema_version": 1}
SIDECAR_VERSION = 1
DDL = (
    "CREATE TABLE contract_schema (version INTEGER NOT NULL)",
    "INSERT INTO contract_schema VALUES (1)",
    "CREATE TABLE contract_versions (kind TEXT NOT NULL, identity TEXT NOT NULL, version TEXT NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(kind,identity,version))",
    "CREATE TABLE contract_records (id TEXT NOT NULL, revision INTEGER NOT NULL, kind TEXT NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(id,revision))",
    "CREATE TRIGGER contract_versions_no_update BEFORE UPDATE ON contract_versions BEGIN SELECT RAISE(ABORT,'immutable contract version'); END",
    "CREATE TRIGGER contract_versions_no_delete BEFORE DELETE ON contract_versions BEGIN SELECT RAISE(ABORT,'immutable contract version'); END",
    "CREATE TRIGGER contract_records_no_update BEFORE UPDATE ON contract_records BEGIN SELECT RAISE(ABORT,'immutable contract record'); END",
    "CREATE TRIGGER contract_records_no_delete BEFORE DELETE ON contract_records BEGIN SELECT RAISE(ABORT,'immutable contract record'); END",
)


class ContractStore:
    def __init__(self, root: Path):
        self.root = reject_links(root).resolve()
        config = Config()
        # No existing state root, source tree or generated-artifact root may be
        # used, including their parents/children. A separate empty root is needed.
        for protected in (config.asset_dir, config.cache_dir, config.workspace_dir, config.output_dir):
            protected = protected.resolve()
            if self.root.is_relative_to(protected) or protected.is_relative_to(self.root):
                raise BulkError("contract_state_isolation", "Choose an isolated state root outside production data")
        marker = self.root / "contract-state.json"
        database = self.root / "state.sqlite3"
        reject_links(marker)
        for suffix in ("", "-wal", "-shm", "-journal"):
            reject_links(str(database) + suffix)
        if marker.exists():
            if decode_json(read_json_bytes(marker)) != MARKER:
                raise BulkError("contract_state_isolation", "Unknown contract state namespace/version")
            if database.exists():
                # Check our namespace read-only BEFORE Store can run migrations.
                try:
                    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
                        versions = db.execute("SELECT version FROM contract_schema").fetchall()
                        if versions != [(SIDECAR_VERSION,)]:
                            raise BulkError("contract_state_isolation", "Unsupported sidecar version")
                except sqlite3.DatabaseError as error:
                    raise BulkError("contract_state_isolation", "Not an initialized contract database") from error
            elif (self.root / "objects").exists():
                raise BulkError("contract_state_isolation", "Evidence exists but its state database is missing")
        else:
            if self.root.exists() and any(self.root.iterdir()):
                raise BulkError("contract_state_isolation", "Cannot initialize over existing files or state")
            atomic_bytes(marker, canonical(MARKER))
        self._store = Store(database)
        with self._store.transaction() as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='contract_schema'").fetchone() is None:
                for statement in DDL:
                    db.execute(statement)

    def _blob_path(self, checksum):
        return confined(self.root, f"objects/{require_hash(checksum)}.json")

    def read_object(self, checksum: str) -> bytes:
        path = self._blob_path(checksum)
        if not path.is_file():
            raise BulkError("missing_contract_evidence", "Missing immutable evidence object")
        encoded = read_json_bytes(path)
        # Exact bytes must be canonical, not merely semantically equivalent.
        value = decode_json(encoded)
        from ..common import fingerprint
        if fingerprint(value) != checksum or canonical(value) != encoded:
            raise BulkError("corrupt_contract_evidence", "Evidence bytes differ from the approved canonical object")
        return encoded

    def _write_blob(self, document):
        path = self._blob_path(document.sha256)
        try:
            atomic_bytes(path, document.encoded)
        except FileExistsError:
            if self.read_object(document.sha256) != document.encoded:
                raise BulkError("corrupt_contract_evidence", "Existing object differs")

    def pin(self, document: Contract | RegistryDocument) -> str:
        """Archive an immutable version; storing it does not approve or activate it."""
        if not isinstance(document, (Contract, RegistryDocument)):
            raise BulkError("invalid_document_type", "Only contracts and registry snapshots have version pins")
        self._write_blob(document)  # Crash before DB commit leaves only an orphan.
        value = document.to_dict()
        kind = "contract" if isinstance(document, Contract) else "registry"
        identity = value["category"] + ":" + value["kind"] if kind == "contract" else value["id"]
        with self._store.transaction() as db:
            key = (kind, identity, value["version"])
            old = db.execute("SELECT sha256 FROM contract_versions WHERE kind=? AND identity=? AND version=?", key).fetchone()
            if old is not None:
                if old["sha256"] != document.sha256:
                    raise Conflict("A version already pins different canonical bytes")
                return document.sha256
            db.execute("INSERT INTO contract_versions VALUES (?,?,?,?)", (*key, document.sha256))
            self._store.event(db, "contract_version_pinned", identity, {"kind": kind, "version": value["version"], "sha256": document.sha256})
        return document.sha256

    def append(self, record: Record, *, expected_revision: int) -> str:
        """Append typed evidence using CAS; not an approval/exception transition.

        Immutable payload + event + revision are committed together. Semantic
        preview, two-role and compatibility acceptance belongs to later adapters.
        """
        if not isinstance(record, Record) or type(expected_revision) is not int or expected_revision < 0:
            raise BulkError("invalid_contract_record", "Expected a typed record and nonnegative integer revision")
        value = record.to_dict()
        if value["revision"] != expected_revision + 1:
            raise Conflict("Record revision must immediately follow the expected revision")
        self._write_blob(record)
        with self._store.transaction() as db:
            old = db.execute("SELECT revision,kind FROM contract_records WHERE id=? ORDER BY revision DESC LIMIT 1", (value["id"],)).fetchone()
            if (old["revision"] if old else 0) != expected_revision or (old and old["kind"] != value["kind"]):
                raise Conflict("Evidence stream changed or record kind was substituted")
            db.execute("INSERT INTO contract_records VALUES (?,?,?,?)", (value["id"], value["revision"], value["kind"], record.sha256))
            self._store.event(db, "contract_evidence_recorded", value["id"], {"revision": value["revision"], "kind": value["kind"], "sha256": record.sha256})
        return record.sha256

    def read_record(self, identity: str, revision: int) -> Record:
        if type(identity) is not str or type(revision) is not int or revision < 1:
            raise BulkError("invalid_contract_record", "An exact identity and positive integer revision are required")
        with self._store.connection() as db:
            row = db.execute("SELECT sha256,kind FROM contract_records WHERE id=? AND revision=?", (identity, revision)).fetchone()
        if row is None:
            raise BulkError("missing_contract_evidence", "No such evidence revision")
        record = read_document(self.read_object(row["sha256"]), "record")
        value = record.to_dict()
        if (value["id"], value["revision"], value["kind"]) != (identity, revision, row["kind"]):
            raise BulkError("corrupt_contract_evidence", "Record index differs from immutable payload")
        return record
