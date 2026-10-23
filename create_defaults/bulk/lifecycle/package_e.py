"""Public additive Package E bridge; frozen ContractStore bytes stay unchanged.

One existing database, original canonical object reader and public Store
transactions/events. No private ContractStore storage helper is called here.
"""

from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3

from ..common import BulkError, atomic_bytes, canonical, confined, reject_links
from ..config import Config
from ..state import Store
from ..contracts.models import decode_json, read_json_bytes
from ..contracts.registry import require_hash
from ..contracts.state import ContractStore, MARKER, SIDECAR_VERSION


class SidecarStore(ContractStore):
    """Supported additive sidecar API, retaining original pin/record behavior."""

    def __init__(self, root):
        super().__init__(root)
        # Public Store opens the SAME database after original root/marker guards.
        # Separate Python handles are not a second state or approval store.
        self.backend = Store(self.root / "state.sqlite3")

    def pin(self, document):
        if self.backend is None:
            raise BulkError("contract_readonly", "Explicit writable archive required")
        return super().pin(document)

    def append(self, record, *, expected_revision):
        if self.backend is None:
            raise BulkError("contract_readonly", "Explicit writable archive required")
        return super().append(record, expected_revision=expected_revision)

    @classmethod
    def open_readonly(cls, root: Path):
        """Inspect an existing isolated archive without migrations or creation.

        Additive sidecars may use read_connection/read_object, then explicitly
        construct a writable ContractStore only when performing an authorized
        local append. This method grants no decision or operational authority.
        """
        self = object.__new__(cls)
        self.root = reject_links(root).resolve()
        config = Config()
        for protected in (config.asset_dir, config.cache_dir, config.workspace_dir, config.output_dir):
            protected = protected.resolve()
            if self.root.is_relative_to(protected) or protected.is_relative_to(self.root):
                raise BulkError("contract_state_isolation", "Choose an isolated state root outside production data")
        self.backend = None
        with self.read_connection():
            pass
        return self

    @contextmanager
    def read_connection(self):
        """Existing namespace only; SQLite mode=ro and query_only, no Store init."""
        marker = reject_links(self.root / "contract-state.json")
        database = self.root / "state.sqlite3"
        for suffix in ("", "-wal", "-shm", "-journal"):
            reject_links(str(database) + suffix)
        if not marker.is_file() or decode_json(read_json_bytes(marker)) != MARKER or not database.is_file():
            raise BulkError("contract_state_isolation", "Missing or foreign existing archive")
        try:
            with closing(sqlite3.connect(database.as_uri()+"?mode=ro", uri=True, isolation_level=None)) as db:
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA query_only=ON")
                db.execute("BEGIN")
                if [tuple(r) for r in db.execute("SELECT version FROM contract_schema")] != [(SIDECAR_VERSION,)]:
                    raise BulkError("contract_state_isolation", "Unsupported sidecar version")
                yield db
        except sqlite3.DatabaseError as error:
            raise BulkError("corrupt_contract_evidence", "Cannot inspect a valid existing archive") from error

    def put_object(self, encoded: bytes, *, expected_sha256: str) -> str:
        """Write exact canonical content-addressed data; never approval or a pin.

        New sidecar readers own their type/semantic checks. Existing closed M1
        append/pin readers remain unchanged. Only explicitly writable instances
        may create blobs; an interrupted write cannot create an authoritative index.
        """
        if self.backend is None:
            raise BulkError("contract_readonly", "Explicit writable archive required")
        from ..common import fingerprint
        value = decode_json(encoded)
        checksum = require_hash(expected_sha256)
        if canonical(value) != encoded or fingerprint(value) != checksum:
            raise BulkError("corrupt_contract_evidence", "Expected exact canonical object bytes and hash")
        # Stabilize the owned parent before Windows resolves a not-yet-present
        # blob while another writer creates that same directory. All original
        # confinement/reparse/hash checks still run below and in atomic_bytes.
        reject_links(self.root / "objects").mkdir(exist_ok=True)
        path = confined(self.root, f"objects/{checksum}.json")
        try:
            atomic_bytes(path, encoded)
        except FileExistsError:
            if self.read_object(checksum) != encoded:
                raise BulkError("corrupt_contract_evidence", "Existing object differs")
        return checksum

    @contextmanager
    def transaction(self):
        """Public local sidecar transaction; index changes and events share it."""
        if self.backend is None:
            raise BulkError("contract_readonly", "Explicit writable archive required")
        with self.backend.transaction() as db:
            if not hasattr(self, "_public_transactions"):
                self._public_transactions = set()
            self._public_transactions.add(id(db))
            try:
                yield db
            finally:
                self._public_transactions.remove(id(db))

    def event(self, db, kind, subject, payload):
        """Append through Package E inside the caller-owned sidecar transaction."""
        if self.backend is None or id(db) not in getattr(self, "_public_transactions", ()) or not db.in_transaction:
            raise BulkError("transaction_required", "Writable owned transaction required")
        self.backend.event(db, kind, subject, payload)
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]
