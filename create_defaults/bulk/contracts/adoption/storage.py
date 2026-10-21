"""Restart-safe adoption sidecars in the existing isolated M1 Store only."""

from pathlib import Path

from ...common import BulkError, Conflict
from ..models import RegistryDocument
from ..state import ContractStore
from .models import HistoricalOutput, HistoricalRegistry, audit_membership, equal, read_canonical


DDL = (
    "CREATE TABLE contract_adoption_schema (version INTEGER NOT NULL)",
    "INSERT INTO contract_adoption_schema VALUES (1)",
    "CREATE TABLE contract_adoption_snapshots (id TEXT NOT NULL, version TEXT NOT NULL, source_sha256 TEXT NOT NULL, registry_sha256 TEXT NOT NULL, PRIMARY KEY(id,version))",
    "CREATE TRIGGER contract_adoption_no_update BEFORE UPDATE ON contract_adoption_snapshots BEGIN SELECT RAISE(ABORT,'immutable adoption'); END",
    "CREATE TRIGGER contract_adoption_no_delete BEFORE DELETE ON contract_adoption_snapshots BEGIN SELECT RAISE(ABORT,'immutable adoption'); END",
)


class AdoptionArchive:
    def __init__(self, root: Path):
        self.contracts = ContractStore(root)
        # Additive namespace, same database/transactions/events, unchanged M1
        # schema marker and production migrations. Never open a production cache.
        with self.contracts._store.transaction() as db:
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'contract_adoption_%'")}
            expected = {"contract_adoption_schema", "contract_adoption_snapshots", "contract_adoption_no_update", "contract_adoption_no_delete"}
            if not names:
                for statement in DDL:
                    db.execute(statement)
            elif names != expected or [tuple(r) for r in db.execute("SELECT version FROM contract_adoption_schema")] != [(1,)]:
                raise BulkError("corrupt_adoption_state", "Incomplete or unsupported adoption sidecar schema; refusing automatic repair")

    def commit(self, registry: HistoricalRegistry, records: tuple[HistoricalOutput, ...]):
        registry.verify_schema_pins()
        value = registry.to_dict()
        expected = {m["id"]: m["sha256"] for m in value["members"]}
        audit_membership(records, expected)
        _verify_member_jobs(value, records)
        basis = RegistryDocument.from_dict(read_canonical(value["basis_registry_json"]))
        key = (value["id"], value["version"])
        with self.contracts._store.connection() as db:
            old = db.execute("SELECT registry_sha256 FROM contract_adoption_snapshots WHERE id=? AND version=?", key).fetchone()
        if old:
            if old["registry_sha256"] != registry.sha256:
                raise Conflict("Adoption version already pins another source/context/membership")
            self.load(*key, expected_sha256=registry.sha256)
            return registry.sha256
        for record in records:
            self.contracts._write_blob(record)
        self.contracts._write_blob(registry)
        self.contracts._write_blob(basis)
        # One commit publishes the complete mapping and its M1 basis version.
        # A crash while writing blobs leaves no complete-snapshot pointer.
        with self.contracts._store.transaction() as db:
            old = db.execute("SELECT registry_sha256 FROM contract_adoption_snapshots WHERE id=? AND version=?", key).fetchone()
            if old:
                if old["registry_sha256"] != registry.sha256:
                    raise Conflict("Concurrent adoption changed the selected version")
                return registry.sha256
            pin_key = ("registry", basis.to_dict()["id"], basis.to_dict()["version"])
            pin = db.execute("SELECT sha256 FROM contract_versions WHERE kind=? AND identity=? AND version=?", pin_key).fetchone()
            if pin and pin["sha256"] != basis.sha256:
                raise Conflict("M1 basis version already pins different bytes")
            if not pin:
                db.execute("INSERT INTO contract_versions VALUES (?,?,?,?)", (*pin_key, basis.sha256))
            db.execute("INSERT INTO contract_adoption_snapshots VALUES (?,?,?,?)", (*key, value["source_pins_sha256"], registry.sha256))
            self.contracts._store.event(db, "historical_adoption_committed", value["id"],
                {"version": value["version"], "registry_sha256": registry.sha256, "source_pins_sha256": value["source_pins_sha256"],
                 "outputs": len(records), "publication_authorized": False})
        return registry.sha256

    def load(self, identity: str, version: str, *, expected_sha256: str):
        with self.contracts._store.connection() as db:
            row = db.execute("SELECT * FROM contract_adoption_snapshots WHERE id=? AND version=?", (identity, version)).fetchone()
        if not row:
            raise BulkError("missing_adoption", "No committed adoption snapshot for the exact ID/version")
        if row["registry_sha256"] != expected_sha256:
            raise BulkError("adoption_registry_pin", "Exact externally selected adoption registry hash required")
        registry = HistoricalRegistry.from_bytes(self.contracts.read_object(expected_sha256))
        registry.verify_schema_pins()
        value = registry.to_dict()
        if (value["id"], value["version"], value["source_pins_sha256"]) != (identity, version, row["source_sha256"]):
            raise BulkError("corrupt_adoption", "Snapshot index differs from pinned immutable evidence")
        basis = RegistryDocument.from_bytes(self.contracts.read_object(value["basis_registry_sha256"]))
        if basis.encoded.decode() != value["basis_registry_json"]:
            raise BulkError("corrupt_adoption", "Basis registry differs from its pin")
        with self.contracts._store.connection() as db:
            pin = db.execute("SELECT sha256 FROM contract_versions WHERE kind='registry' AND identity=? AND version=?",
                             (basis.to_dict()["id"], basis.to_dict()["version"])).fetchone()
        if not pin or pin["sha256"] != basis.sha256:
            raise BulkError("corrupt_adoption", "Missing or inconsistent immutable M1 basis pin")
        records = tuple(HistoricalOutput.from_bytes(self.contracts.read_object(m["sha256"])) for m in value["members"])
        audit_membership(records, {m["id"]: m["sha256"] for m in value["members"]})
        _verify_member_jobs(value, records)
        return registry, records


def _verify_member_jobs(registry, records):
    equal({m["id"]: m["job_id"] for m in registry["members"]},
          {r.to_dict()["identity"]["id"]: r.to_dict()["job_id"] for r in records},
          category="registry", identity=registry["id"], path="member.job_id")
