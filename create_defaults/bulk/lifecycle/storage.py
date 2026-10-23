"""Append-only record coordination in the existing isolated Package E database.

Head movement coordinates synthetic proposals; it never applies their before/
proposed state, allocates item identities or accepts a name/operation/approval.
Every inspection replays canonical journal, record, head and Package E indexes.
"""

from pathlib import Path
import re

from ..common import Conflict, atomic_bytes, canonical, reject_links
from ..contracts.models import decode_json, read_json_bytes
from .models import Operation, Event, key, successor, fail


def require_hash(value):
    from ..contracts.registry import require_hash as check
    return check(value)


def _contracts():
    # Existing ContractStore imports its older registry/worker-related modules.
    # Load that framework only for an explicit storage action, never on import.
    from .package_e import SidecarStore
    return SidecarStore


# Bounded record-only prototype metadata, not image/visual acceptance thresholds.
MAX_EVENTS = 4096
MAX_HEAD_VERSIONS = 65536
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
VERSION = (1, "1.0.0")
MARKER = dict(kind="p4m1-operation-state",schema_version=1,protocol_version="1.0.0",scope="isolated-synthetic-records")
TABLES = (
    "CREATE TABLE p4m1_schema (version INTEGER NOT NULL, protocol TEXT NOT NULL)",
    "CREATE TABLE p4m1_records (id TEXT NOT NULL, revision INTEGER NOT NULL, sha256 TEXT NOT NULL UNIQUE, PRIMARY KEY(id,revision))",
    "CREATE TABLE p4m1_journal (sequence INTEGER PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, package_event INTEGER NOT NULL UNIQUE)",
    "CREATE TABLE p4m1_heads (kind TEXT NOT NULL, identity TEXT NOT NULL, revision INTEGER NOT NULL, sha256 TEXT NOT NULL, subjects TEXT NOT NULL, event_sha256 TEXT NOT NULL, PRIMARY KEY(kind,identity,revision))",
)
TRIGGERS = tuple(
    f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable operation evidence'); END"
    for table in ("p4m1_schema", "p4m1_records", "p4m1_journal", "p4m1_heads") for action in ("UPDATE", "DELETE")
)
DDL = TABLES + TRIGGERS
NAMESPACE = {sql.split()[2]:sql for sql in DDL}


def _namespace(db):
    found = {r["name"]:r["sql"] for r in db.execute("SELECT name,sql FROM sqlite_master WHERE name LIKE 'p4m1_%'")}
    if found != NAMESPACE or [tuple(r) for r in db.execute("SELECT version,protocol FROM p4m1_schema")] != [VERSION]:
        fail("archive_namespace")


def _rows(db, sql, limit):
    result = db.execute(sql+" LIMIT ?", (limit+1,)).fetchall()
    if len(result) > limit:
        fail("archive_limit")
    return result


def _changes(record, heads):
    v = record.to_dict()
    reads = {key(r):r for r in v["reads"]}
    for k,r in reads.items():
        current = heads.get(k, dict(revision=0, sha256=None))
        if (r["revision"],r["sha256"]) != (current["revision"],current["sha256"]):
            raise Conflict("A selected subject, namespace, evidence or dependency head changed")
    return [dict(key=w,subjects=reads[key(w)]["subjects"],
        before={f:reads[key(w)][f] for f in ("revision","sha256")},
        after=dict(revision=reads[key(w)]["revision"]+1,sha256=record.sha256)) for w in v["writes"]]


def _index_budget(db):
    # Reject oversized forged indexes in SQLite before allocating their strings
    # in the parent. Canonical object reads have the independent M1 8 MiB bound.
    index_bytes = 0
    for table,fields,where in (
        ("p4m1_records",("id","sha256"),""),
        ("p4m1_journal",("sha256",),""),
        ("p4m1_heads",("kind","identity","sha256","subjects","event_sha256"),""),
        ("events",("subject","payload")," WHERE kind='phase4_operation_recorded'"),
    ):
        sizes = "+".join("length(CAST("+f+" AS BLOB))" for f in fields)
        index_bytes += db.execute("SELECT coalesce(sum("+sizes+"),0) FROM "+table+where).fetchone()[0]
        if index_bytes > MAX_ARCHIVE_BYTES:
            fail("archive_limit")


def _replay(contracts, db):
    _namespace(db)
    _index_budget(db)
    rows = _rows(db,"SELECT id,revision,sha256 FROM p4m1_records ORDER BY id,revision",MAX_EVENTS)
    journals = _rows(db,"SELECT sequence,sha256,package_event FROM p4m1_journal ORDER BY sequence",MAX_EVENTS)
    head_rows = _rows(db,"SELECT kind,identity,revision,sha256,subjects,event_sha256 FROM p4m1_heads ORDER BY kind,identity,revision",MAX_HEAD_VERSIONS)
    package_rows = _rows(db,"SELECT sequence,subject,payload FROM events WHERE kind='phase4_operation_recorded' ORDER BY sequence",MAX_EVENTS)
    budget = 0
    def read(pin, cls):
        nonlocal budget
        raw = contracts.read_object(require_hash(pin))
        budget += len(raw)
        if budget > MAX_ARCHIVE_BYTES:
            fail("archive_limit")
        value = cls.from_bytes(raw)
        if value.sha256 != pin:
            fail("archive_object")
        return value
    records = {}
    for row in rows:
        r = read(row["sha256"],Operation);v = r.to_dict()
        if (v["id"],v["revision"]) != (row["id"],row["revision"]):
            fail("archive_record_index")
        records[(v["id"],v["revision"])] = r
    latest, heads, events, expected_heads, expected_package, used = {}, {}, [], [], [], set()
    previous = None
    for number,row in enumerate(journals,1):
        event = read(row["sha256"],Event);e = event.to_dict()
        if e["sequence"] != number or row["sequence"] != number or e["previous_sha256"] != previous:
            fail("archive_journal")
        rk = (e["operation_id"],e["operation_revision"])
        record = records.get(rk)
        if record is None or rk in used or record.sha256 != e["record_sha256"]:
            fail("archive_record_index")
        used.add(rk);v = record.to_dict();prior = latest.get(v["id"])
        if (v["previous_sha256"],v["previous_event_sha256"]) != ((prior[0].sha256,prior[1].sha256) if prior else (None,None)):
            fail("archive_operation_chain")
        successor(prior[0].to_dict() if prior else None,v)
        if (e["state"],e["previous_record_sha256"],e["previous_operation_event_sha256"]) != (v["state"],v["previous_sha256"],v["previous_event_sha256"]):
            fail("archive_operation_chain")
        try:
            changes = _changes(record,heads)
        except Conflict:
            fail("archive_read_set")
        if e["changes"] != changes:
            fail("archive_head_changes")
        for change in changes:
            k = key(change["key"])
            heads[k] = dict(**change["key"],subjects=change["subjects"],**change["after"])
            expected_heads.append((*k,change["after"]["revision"],record.sha256,canonical(change["subjects"]).decode(),event.sha256))
        payload = dict(sequence=number,sha256=event.sha256,record_sha256=record.sha256,revision=v["revision"])
        expected_package.append((row["package_event"],v["id"],canonical(payload).decode()))
        latest[v["id"]] = (record,event);events.append(event);previous = event.sha256
    if used != records.keys() or [tuple(r) for r in head_rows] != sorted(expected_heads) or [tuple(r) for r in package_rows] != expected_package:
        fail("archive_indexes")
    return records, tuple(events), latest, heads


class OperationStore:
    """Opening/inspection is read-only. create/append are explicit local writes."""

    def __init__(self, root):
        if ".." in Path(root).parts:
            fail("archive_root")
        self.root = reject_links(Path(root)).resolve()
        marker = reject_links(self.root/"operation-state.json")
        if not marker.is_file() or decode_json(read_json_bytes(marker)) != MARKER:
            fail("archive_namespace")
        self.contracts = _contracts().open_readonly(self.root)
        self.inspect()

    @classmethod
    def create(cls, root):
        if ".." in Path(root).parts:
            fail("archive_root")
        root = reject_links(Path(root))
        if root.exists() and not root.is_dir():
            fail("archive_root")
        if root.exists() and any(root.iterdir()):
            # Never initialize or repair a foreign/partial namespace.
            return cls(root)
        contracts = _contracts()(root)
        with contracts.transaction() as db:
            for sql in DDL:
                db.execute(sql)
            db.execute("INSERT INTO p4m1_schema VALUES (?,?)",VERSION)
        atomic_bytes(contracts.root/"operation-state.json",canonical(MARKER))
        return cls(root)

    def inspect(self, *, expected_journal_sha256=None):
        with self.contracts.read_connection() as db:
            records,events,latest,heads = _replay(self.contracts,db)
        pin = events[-1].sha256 if events else None
        if expected_journal_sha256 is not None and pin != require_hash(expected_journal_sha256):
            raise Conflict("The independently selected journal checkpoint differs")
        return dict(schema_version=1,kind="operation-store-inspection",scope="isolated-synthetic-records",
            journal_sha256=pin,sequence=len(events),records=len(records),
            heads=[heads[k] for k in sorted(heads)],operations=[dict(id=k,revision=latest[k][0].to_dict()["revision"],
                sha256=latest[k][0].sha256,event_sha256=latest[k][1].sha256,state=latest[k][0].to_dict()["state"]) for k in sorted(latest)],
            currentness="checkpoint-matched" if expected_journal_sha256 is not None else "integrity-only-currentness-unknown",
            operation_accepted=False,applied=False,contract_approved=False,artwork_approved=False,
            production_enforcement=False,publication_authorized=False,ready=False,active=False)

    def history(self, identity):
        if type(identity) is not str or not re.fullmatch(r"synthetic\.operation\.[a-z0-9][a-z0-9._-]{0,140}",identity):
            fail("operation_identity")
        with self.contracts.read_connection() as db:
            records,_,_,_ = _replay(self.contracts,db)
        return tuple(r for (i,_),r in sorted(records.items()) if i == identity)

    def journal(self):
        with self.contracts.read_connection() as db:
            return _replay(self.contracts,db)[1]

    def append(self, record, *, expected_revision, expected_sha256, expected_event_sha256):
        if type(record) is not Operation:
            fail("record_type")
        record = Operation.from_bytes(record.encoded);v = record.to_dict()
        if type(expected_revision) is not int or expected_revision < 0 or expected_revision+1 != v["revision"]:
            raise Conflict("Exact previous operation revision required")
        for pin in (expected_sha256,expected_event_sha256):
            if pin is not None:require_hash(pin)
        if (expected_sha256,expected_event_sha256) != (v["previous_sha256"],v["previous_event_sha256"]):
            raise Conflict("Independent operation and journal pins differ")
        # Validate existing namespace before opening any writable Store/migrations.
        self.inspect()
        writer = _contracts()(self.root)
        writer.put_object(record.encoded,expected_sha256=record.sha256)
        with writer.transaction() as db:
            records,events,latest,heads = _replay(writer,db)
            existing = records.get((v["id"],v["revision"]))
            if existing is not None:
                if existing.sha256 != record.sha256:
                    raise Conflict("Operation ID/revision already binds different content")
                return next(e for e in events if e.to_dict()["record_sha256"] == record.sha256)
            prior = latest.get(v["id"])
            if (prior[0].to_dict()["revision"] if prior else 0) != expected_revision or ((prior[0].sha256,prior[1].sha256) if prior else (None,None)) != (expected_sha256,expected_event_sha256):
                raise Conflict("Operation head changed")
            successor(prior[0].to_dict() if prior else None,v)
            changes = _changes(record,heads)
            if len(events)+1 > MAX_EVENTS or sum(len(e.to_dict()["changes"]) for e in events)+len(changes) > MAX_HEAD_VERSIONS:
                fail("archive_limit")
            e = {k:v[k] for k in ("schema_version","protocol_version","scope","simulation","record_only",
                "operation_accepted","applied","artwork_approved","contract_approved","ready","active","production_enforcement","publication_authorized")}
            e.update(kind="operation-event",sequence=len(events)+1,previous_sha256=events[-1].sha256 if events else None,
                operation_id=v["id"],operation_revision=v["revision"],record_sha256=record.sha256,
                previous_record_sha256=v["previous_sha256"],previous_operation_event_sha256=v["previous_event_sha256"],state=v["state"],changes=changes)
            event = Event.from_dict(e)
            # Check the same cumulative budget that read/restart enforces.
            size = sum(len(r.encoded) for r in records.values())+sum(len(e.encoded) for e in events)+len(record.encoded)+len(event.encoded)
            if size > MAX_ARCHIVE_BYTES:fail("archive_limit")
            writer.put_object(event.encoded,expected_sha256=event.sha256)
            db.execute("INSERT INTO p4m1_records VALUES (?,?,?)",(v["id"],v["revision"],record.sha256))
            for c in changes:
                db.execute("INSERT INTO p4m1_heads VALUES (?,?,?,?,?,?)",(*key(c["key"]),c["after"]["revision"],record.sha256,canonical(c["subjects"]).decode(),event.sha256))
            pe = writer.event(db,"phase4_operation_recorded",v["id"],dict(sequence=e["sequence"],sha256=event.sha256,record_sha256=record.sha256,revision=v["revision"]))
            db.execute("INSERT INTO p4m1_journal VALUES (?,?,?)",(e["sequence"],event.sha256,pe))
            # The next read must accept this archive under the same independent
            # index budget. Reject within this transaction, never after commit.
            _index_budget(db)
        return event
