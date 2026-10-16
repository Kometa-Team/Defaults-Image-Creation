"""SQLite migrations, owned transactions, versioned job state and immutable events."""

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time

from .common import BulkError, Conflict, canonical, fingerprint, reject_links


MIGRATIONS = (
    (
        "CREATE TABLE events (sequence INTEGER PRIMARY KEY, kind TEXT NOT NULL, subject TEXT NOT NULL, created REAL NOT NULL, payload TEXT NOT NULL)",
        "CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'immutable audit event'); END",
        "CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'immutable audit event'); END",
        "CREATE TABLE jobs (id TEXT PRIMARY KEY, version INTEGER NOT NULL, status TEXT NOT NULL, spec TEXT NOT NULL, fingerprint TEXT NOT NULL, owner TEXT, expires REAL, receipt TEXT)",
        "CREATE TABLE workspaces (id TEXT PRIMARY KEY, token TEXT NOT NULL, created REAL NOT NULL, status TEXT NOT NULL)",
    ),
    (
        "CREATE TABLE color_assignments (id TEXT PRIMARY KEY, poster TEXT NOT NULL, category TEXT NOT NULL, hex TEXT NOT NULL, origin TEXT NOT NULL, source TEXT NOT NULL, policy TEXT NOT NULL)",
        "CREATE INDEX color_occupancy ON color_assignments(category,hex)",
        "CREATE TABLE color_relationships (id TEXT PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL)",
        "CREATE TABLE color_exceptions (id TEXT PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL)",
        "CREATE TABLE color_reservations (id TEXT PRIMARY KEY, poster TEXT NOT NULL, category TEXT NOT NULL, hex TEXT NOT NULL, owner TEXT NOT NULL, expires REAL NOT NULL, payload TEXT NOT NULL)",
        "CREATE INDEX color_claims ON color_reservations(category,hex)",
        "CREATE TABLE remote_snapshots (repo TEXT, branch TEXT, version INTEGER NOT NULL, head TEXT NOT NULL, tree TEXT NOT NULL, checked REAL NOT NULL, failure TEXT, PRIMARY KEY(repo,branch))",
        "CREATE TABLE remote_entries (repo TEXT, tree TEXT, path TEXT, key TEXT NOT NULL, sha TEXT NOT NULL, size INTEGER, mode TEXT NOT NULL, type TEXT NOT NULL, PRIMARY KEY(repo,tree,path))",
        "CREATE INDEX remote_keys ON remote_entries(repo,tree,key)",
    ),
    (
        "CREATE TABLE remote_failures (repo TEXT, branch TEXT, status INTEGER NOT NULL, created REAL NOT NULL, PRIMARY KEY(repo,branch))",
    ),
    (
        "CREATE TABLE workspace_jobs (workspace TEXT REFERENCES workspaces(id), job TEXT REFERENCES jobs(id), PRIMARY KEY(workspace,job))",
    ),
    (
        "CREATE TABLE output_claims (root TEXT, path_key TEXT, relative TEXT NOT NULL, state_id TEXT NOT NULL, fingerprint TEXT NOT NULL, PRIMARY KEY(root,path_key))",
    ),
)


class Store:
    def __init__(self, path, *, clock=time.time):
        self.path = reject_links(path)
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection(check=True) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("BEGIN IMMEDIATE")
            try:
                version = db.execute("PRAGMA user_version").fetchone()[0]
                if version > len(MIGRATIONS):
                    raise BulkError("future_state", "State database schema is newer than this application")
                for number in range(version, len(MIGRATIONS)):
                    for statement in MIGRATIONS[number]:
                        db.execute(statement)
                    db.execute(f"PRAGMA user_version={number + 1}")
                db.commit()
            except BaseException:
                db.rollback()
                raise

    @contextmanager
    def connection(self, *, check=False):
        for suffix in ("", "-wal", "-shm", "-journal"):
            reject_links(str(self.path) + suffix)
        try:
            db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=30000")
            if check and db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                db.close()
                raise BulkError("corrupt_state", "SQLite integrity check failed")
        except sqlite3.DatabaseError as error:
            if "db" in locals():
                db.close()
            raise BulkError("corrupt_state", "Cannot open a valid SQLite state database") from error
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def event(self, db, kind, subject, payload):
        db.execute("INSERT INTO events(kind,subject,created,payload) VALUES (?,?,?,?)",
                   (kind, subject, self.clock(), canonical(payload).decode()))

    def add_job(self, identity, spec):
        with self.transaction() as db:
            self.add_job_in_transaction(db, identity, spec)
        return self.job(identity)

    def add_job_in_transaction(self, db, identity, spec):
        """Register bounded pages under a caller-owned write transaction."""
        if not db.in_transaction:
            raise BulkError("transaction_required", "Job registration requires an owned write transaction")
        encoded, checksum = canonical(spec).decode(), fingerprint(spec)
        old = db.execute("SELECT * FROM jobs WHERE id=?", (identity,)).fetchone()
        if old:
            if old["fingerprint"] != checksum or old["spec"] != encoded:
                raise Conflict("Job identity already binds a different specification")
            return
        db.execute("INSERT INTO jobs(id,version,status,spec,fingerprint) VALUES (?,0,'planned',?,?)", (identity, encoded, checksum))
        self.event(db, "job_planned", identity, {"fingerprint": checksum})

    def job(self, identity):
        with self.connection() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (identity,)).fetchone()
            if not row:
                raise BulkError("missing_job", "Unknown job identity")
            try:
                valid = fingerprint(json.loads(row["spec"])) == row["fingerprint"]
            except ValueError:
                valid = False
            if not valid:
                raise BulkError("corrupt_state", "Stored job specification fingerprint mismatch")
            return dict(row)

    def transition(self, identity, expected_version, status, *, owner=None, lease_seconds=300, receipt=None):
        if type(lease_seconds) is not int or lease_seconds <= 0:
            raise BulkError("invalid_lease", "Positive integer lease duration required")
        transitions = {"planned": {"running"}, "running": {"failed", "interrupted", "verified"}, "failed": {"running"}, "interrupted": {"running"}, "verified": set()}
        with self.transaction() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (identity,)).fetchone()
            if not row or row["version"] != expected_version:
                raise Conflict()
            try:
                valid = fingerprint(json.loads(row["spec"])) == row["fingerprint"]
            except ValueError:
                valid = False
            if not valid:
                raise BulkError("corrupt_state", "Stored job specification is corrupt")
            if status not in transitions[row["status"]] or (status == "running" and not owner):
                raise BulkError("invalid_transition", "Invalid job transition or missing lease owner")
            if row["status"] == "running" and (not owner or row["owner"] != owner or row["expires"] <= self.clock()):
                raise Conflict("Job lease is not owned or has expired")
            if status == "verified" and (not isinstance(receipt, dict) or receipt.get("job_id") != identity or receipt.get("job_fingerprint") != row["fingerprint"] or receipt.get("receipt_sha256") != fingerprint({key: value for key, value in receipt.items() if key != "receipt_sha256"})):
                raise BulkError("missing_receipt", "Verified state requires output evidence")
            db.execute("UPDATE jobs SET version=version+1,status=?,owner=?,expires=?,receipt=? WHERE id=?",
                       (status, owner if status == "running" else None, self.clock() + lease_seconds if status == "running" else None,
                        canonical(receipt).decode() if receipt is not None else None, identity))
            self.event(db, "job_" + status, identity, {"version": expected_version + 1, "owner": owner, "receipt": receipt})
        return self.job(identity)

    def recover(self):
        with self.transaction() as db:
            rows = db.execute("SELECT id FROM jobs WHERE status='running' AND expires<=?", (self.clock(),)).fetchall()
            for row in rows:
                db.execute("UPDATE jobs SET status='interrupted',version=version+1,owner=NULL,expires=NULL WHERE id=?", (row["id"],))
                self.event(db, "job_lease_expired", row["id"], {})
            expired = db.execute("SELECT id FROM color_reservations WHERE expires<=?", (self.clock(),)).fetchall()
            for row in expired:
                db.execute("DELETE FROM color_reservations WHERE id=?", (row["id"],))
                self.event(db, "color_lease_expired", row["id"], {})
        return {"jobs": len(rows), "colors": len(expired)}
