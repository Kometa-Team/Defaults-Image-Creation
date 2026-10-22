"""Append-only M7 index in the unchanged Package E transaction/event store."""

from contextlib import closing
import sqlite3

from ...common import BulkError, Conflict, reject_links
from ..models import ContractApproval
from ..state import ContractStore
from .models import Revision, read


DDL = (
    "CREATE TABLE contract_activation_schema (version INTEGER NOT NULL)",
    "INSERT INTO contract_activation_schema VALUES (1)",
    "CREATE TABLE contract_activation_revisions (id TEXT NOT NULL, revision INTEGER NOT NULL, sha256 TEXT NOT NULL UNIQUE, PRIMARY KEY(id,revision))",
    "CREATE TRIGGER contract_activation_no_update BEFORE UPDATE ON contract_activation_revisions BEGIN SELECT RAISE(ABORT,'immutable activation revision'); END",
    "CREATE TRIGGER contract_activation_no_delete BEFORE DELETE ON contract_activation_revisions BEGIN SELECT RAISE(ABORT,'immutable activation revision'); END",
)


class Archive:
    def __init__(self, root):
        self.contracts = ContractStore(root)
        self.store = self.contracts._store
        with self.store.transaction() as db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "contract_activation_schema" not in tables:
                if "contract_activation_revisions" in tables:
                    raise BulkError("activation_storage", "Incomplete M7 namespace")
                for sql in DDL:
                    db.execute(sql)
            elif [r[0] for r in db.execute("SELECT version FROM contract_activation_schema")] != [1] or "contract_activation_revisions" not in tables:
                raise BulkError("activation_storage", "Unknown or incomplete M7 namespace")

    def commit(self, revision, documents=(), *, approval_record=None, before_commit=None):
        if type(revision) is not Revision:
            raise BulkError("activation_revision", "A typed immutable state revision is required")
        v = revision.to_dict()
        for document in (*documents, revision):
            self.contracts._write_blob(document)
        if approval_record is not None:
            if type(approval_record) is not ContractApproval or approval_record.to_dict()["revision"] != 1:
                raise BulkError("activation_approval", "New exact M1 approval evidence is required")
            self.contracts._write_blob(approval_record)
        with self.store.transaction() as db:
            old = db.execute("SELECT revision,sha256 FROM contract_activation_revisions WHERE id=? ORDER BY revision DESC LIMIT 1", (v["id"],)).fetchone()
            if (old["revision"] if old else 0) != v["revision"]-1 or (old["sha256"] if old else None) != v["previous_sha256"]:
                raise Conflict("Activation stream advanced; reload and revalidate")
            if approval_record is not None:
                a = approval_record.to_dict()
                prior = db.execute("SELECT revision,kind,sha256 FROM contract_records WHERE id=?", (a["id"],)).fetchall()
                if prior and (len(prior) != 1 or tuple(prior[0]) != (1, a["kind"], approval_record.sha256)):
                    raise Conflict("Approval event identity already names other evidence")
                if not prior:
                    db.execute("INSERT INTO contract_records VALUES (?,?,?,?)", (a["id"],1,a["kind"],approval_record.sha256))
                    self.store.event(db,"contract_evidence_recorded",a["id"],{"revision":1,"kind":a["kind"],"sha256":approval_record.sha256})
            db.execute("INSERT INTO contract_activation_revisions VALUES (?,?,?)",(v["id"],v["revision"],revision.sha256))
            self.store.event(db,"contract_activation_revision",v["id"],{"revision":v["revision"],"sha256":revision.sha256,"state":v["state"],"production_enforcement":False})
            if before_commit is not None:
                before_commit()  # Test-only fault injection; the transaction rolls back on BaseException.
        return revision

    def history(self, identity):
        with self.store.connection() as db:
            rows = db.execute("SELECT revision,sha256 FROM contract_activation_revisions WHERE id=? ORDER BY revision",(identity,)).fetchall()
        return self._verify(rows, identity, self.contracts.read_object)

    @staticmethod
    def _verify(rows, identity, read_object):
        # One fresh read per immutable hash within this inspection only. Each
        # revision/reference is still checked; no evidence/authority cache lives
        # across calls or bypasses the final transition/source revalidation.
        objects={}
        def load(checksum):
            if checksum not in objects:
                objects[checksum]=read_object(checksum)
            return objects[checksum]
        result = [];previous = None;consumed_operators=set()
        for number, checksum in rows:
            revision = Revision.from_bytes(load(checksum));v = revision.to_dict()
            if (revision.sha256,v["id"],v["revision"],v["previous_sha256"]) != (checksum,identity,len(result)+1,previous) or number != len(result)+1:
                raise BulkError("activation_chain", "State index/immutable chain differs")
            for key in ("proposal_sha256","gate_sha256","approval_sha256","operator_sha256","restored_from_sha256"):
                if v[key] is not None:
                    document = read(load(v[key]))
                    expected = {"proposal_sha256":"activation-proposal","gate_sha256":"activation-gate-evidence",
                        "approval_sha256":"activation-contract-approval-binding","operator_sha256":"activation-operator-decision",
                        "restored_from_sha256":"activation-state-revision"}[key]
                    if document.KIND != expected or document.sha256 != v[key]:
                        raise BulkError("activation_reference", "Missing or substituted typed state evidence")
                    if key == "approval_sha256":
                        a = document.to_dict()
                        record = ContractApproval.from_bytes(load(a["record_sha256"]))
                        if record.sha256 != a["record_sha256"]:
                            raise BulkError("activation_reference", "M1 approval receipt changed")
            proposal = read(load(v["proposal_sha256"])).to_dict()
            gates = read(load(v["gate_sha256"])).to_dict()
            if proposal["id"] != identity or gates["proposal_sha256"] != v["proposal_sha256"]:
                raise BulkError("activation_reference", "State identity/proposal/gate references disagree")
            if v["state"] == "ACTIVE":
                if not v["operator_sha256"] or v["operator_sha256"] in consumed_operators:
                    raise BulkError("activation_operator_replay", "State history reuses or omits its independent activation decision")
                consumed_operators.add(v["operator_sha256"])
            result.append(revision);previous = checksum
        return tuple(result)

    @classmethod
    def inspect_readonly(cls, root, identity):
        """No Store construction/migration, directory creation or mutable writes."""
        from ..models import decode_json, read_json_bytes
        from ..state import MARKER
        from ...common import canonical, fingerprint, confined
        root = reject_links(root).resolve()
        if decode_json(read_json_bytes(reject_links(root/"contract-state.json"))) != MARKER:
            raise BulkError("activation_storage", "Not isolated contract state")
        database = reject_links(root/"state.sqlite3")
        for suffix in ("-wal","-shm","-journal"):
            reject_links(str(database)+suffix)
        def signature():
            result=[]
            for name in (database,root/"state.sqlite3-wal",root/"state.sqlite3-journal"):
                if name.exists():
                    info=reject_links(name).stat();result.append((name.name,info.st_size,info.st_mtime_ns,info.st_ino))
                    if name != database and info.st_size:
                        raise BulkError("activation_busy", "Use a closed, checkpointed state snapshot for strictly read-only inspection")
            return result
        before=signature()
        # SQLite mode=ro alone can create WAL/SHM sidecars. immutable=1 avoids
        # those writes; reject nonempty journals and concurrent file changes
        # rather than silently inspect a database without its committed WAL.
        with closing(sqlite3.connect(database.as_uri()+"?mode=ro&immutable=1",uri=True)) as db:
            if db.execute("SELECT version FROM contract_activation_schema").fetchall() != [(1,)]:
                raise BulkError("activation_storage", "Unknown M7 schema")
            rows = db.execute("SELECT revision,sha256 FROM contract_activation_revisions WHERE id=? ORDER BY revision",(identity,)).fetchall()
        if signature() != before:
            raise BulkError("activation_busy", "State changed during read-only inspection; retry a closed snapshot")
        def reader(checksum):
            from ..registry import require_hash
            raw = read_json_bytes(confined(root,"objects/"+require_hash(checksum)+".json",must_exist=True))
            value = decode_json(raw)
            if canonical(value) != raw or fingerprint(value) != checksum:
                raise BulkError("activation_reference", "Corrupted immutable object")
            return raw
        return cls._verify(rows,identity,reader)
