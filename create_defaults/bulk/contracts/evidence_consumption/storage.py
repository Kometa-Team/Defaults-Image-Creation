"""Optional isolated append-only sidecar, using Package E immutable CAS storage.

Archival is explicit and separate from consume(). A crash before the transaction
commits can leave content-addressed orphan blobs; it cannot advance the head.
No old record/receipt, approval, activation or publication table is written.
"""

from ...common import Conflict
from ..registry import require_hash
from ..state import ContractStore
from .models import ConsumptionAttestation, RequestContext, fail


DDL = (
    "CREATE TABLE phase3_consumption_schema (version INTEGER NOT NULL)",
    "INSERT INTO phase3_consumption_schema VALUES (1)",
    "CREATE TABLE phase3_consumption (id TEXT NOT NULL, revision INTEGER NOT NULL, sha256 TEXT NOT NULL UNIQUE, previous_sha256 TEXT, context_sha256 TEXT NOT NULL, PRIMARY KEY(id,revision))",
    "CREATE TRIGGER phase3_consumption_no_update BEFORE UPDATE ON phase3_consumption BEGIN SELECT RAISE(ABORT,'immutable evidence'); END",
    "CREATE TRIGGER phase3_consumption_no_delete BEFORE DELETE ON phase3_consumption BEGIN SELECT RAISE(ABORT,'immutable evidence'); END",
)


class Archive:
    def __init__(self, root):
        self.contracts = ContractStore(root)
        self.store = self.contracts._store
        with self.store.transaction() as db:
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'phase3_consumption%' ")}
            expected = {"phase3_consumption_schema","phase3_consumption","phase3_consumption_no_update","phase3_consumption_no_delete"}
            if not names:
                for sql in DDL:
                    db.execute(sql)
            elif names != expected or [r[0] for r in db.execute("SELECT version FROM phase3_consumption_schema")] != [1]:
                fail("archive_namespace")

    def append(self, report, context, *, expected_head_sha256, expected_context_sha256, before_commit=None):
        if type(report) is not ConsumptionAttestation or type(context) is not RequestContext:
            fail("archive_type")
        report = ConsumptionAttestation.from_bytes(report.encoded)
        context = RequestContext.from_bytes(context.encoded)
        value, request = report.to_dict(), context.to_dict()
        if context.sha256 != require_hash(expected_context_sha256) or value["request_context_sha256"] != context.sha256 or (value["request_id"],value["request_revision"]) != (request["id"],request["revision"]):
            fail("archive_context")
        if expected_head_sha256 is not None:
            require_hash(expected_head_sha256)
        self.history(request["id"])  # Reject corrupted prior immutable chains before appending.
        for document in (context,report):
            self.contracts._write_blob(document)
        with self.store.transaction() as db:
            old = db.execute("SELECT revision,sha256,context_sha256 FROM phase3_consumption WHERE id=? ORDER BY revision DESC LIMIT 1",(request["id"],)).fetchone()
            if (old["sha256"] if old else None) != expected_head_sha256:
                raise Conflict("Evidence archive head changed; select and revalidate the current revision")
            if request["revision"] != (old["revision"]+1 if old else 1) or request["previous_sha256"] != (old["context_sha256"] if old else None):
                raise Conflict("Request revision must extend the exact previous context")
            db.execute("INSERT INTO phase3_consumption VALUES (?,?,?,?,?)",(request["id"],request["revision"],report.sha256,expected_head_sha256,context.sha256))
            self.store.event(db,"phase3_evidence_archived",request["id"],dict(revision=request["revision"],sha256=report.sha256,publication_authorized=False))
            if before_commit is not None:
                before_commit()
        return report.sha256

    def history(self, identity):
        if type(identity) is not str:
            fail("archive_identity")
        with self.store.connection() as db:
            rows = db.execute("SELECT revision,sha256,previous_sha256,context_sha256 FROM phase3_consumption WHERE id=? ORDER BY revision",(identity,)).fetchall()
        result, previous, previous_context = [], None, None
        for number, pin, parent, context_pin in rows:
            report = ConsumptionAttestation.from_bytes(self.contracts.read_object(pin))
            context = RequestContext.from_bytes(self.contracts.read_object(context_pin))
            r,c = report.to_dict(),context.to_dict()
            if (number,parent,c["previous_sha256"],r["request_id"],r["request_revision"],r["request_context_sha256"],c["id"],c["revision"]) != (len(result)+1,previous,previous_context,identity,number,context_pin,identity,number) or report.sha256 != pin or context.sha256 != context_pin:
                fail("archive_chain")
            result.append(report)
            previous,previous_context = pin,context_pin
        return tuple(result)
