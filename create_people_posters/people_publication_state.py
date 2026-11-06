"""Durable per-image receipts, separate from disposable processing jobs."""

# A single canonical diagnostic registry is shared by CLI and imported callers.
import sys as _security_sys
from pathlib import Path as _SecurityPath
_security_root = _SecurityPath(__file__).resolve().parents[1]
if (_security_root / "create_people_posters").is_dir() and str(_security_root) not in _security_sys.path:
    _security_sys.path.insert(0, str(_security_root))
from create_people_posters.people_diagnostics import (protect_cli, safe_exception, sanitize_text,
                                                     sanitize_data, secure_handler, register_environment)
from create_people_posters.people_process import guard_cli
if __name__ == "__main__":
    guard_cli()


import json
from contextlib import contextmanager
import hashlib
import os
import sqlite3
import time
from pathlib import Path

from people_workspaces import ID_PATTERN, atomic_json, reject_links


class PublicationState:
    def reliability_schema(self):
        """Additive only: no legacy row, receipt or index is rewritten."""
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
          BEGIN IMMEDIATE;
          CREATE TABLE IF NOT EXISTS publication_controls (
            batch TEXT, repo TEXT, origin_head TEXT, head TEXT, settings TEXT,
            PRIMARY KEY(batch,repo));
          CREATE TABLE IF NOT EXISTS publication_units (
            batch TEXT, repo TEXT, unit TEXT, binding TEXT, data TEXT,
            PRIMARY KEY(batch,repo,unit));
          CREATE TABLE IF NOT EXISTS publication_unit_members (
            batch TEXT, repo TEXT, path TEXT, unit TEXT,
            PRIMARY KEY(batch,repo,path));
          COMMIT;
        """)

    @contextmanager
    def publication_lock(self):
        """Kernel-owned exclusive lock: crash releases it; never delete it."""
        path = self.state / "publication.lock"
        reject_links(path)
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(descriptor).st_size == 0:
                    os.write(descriptor, b"\0")
                os.lseek(descriptor, 0, 0)
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
            yield
        finally:
            if acquired:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(descriptor, 0, 0)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @staticmethod
    def unit_binding(rows):
        keys = ("style", "repo", "path", "source", "prepared", "source_hash", "published_hash", "blob", "person", "tmdb_id")
        value = [{key: row.get(key, "") for key in keys} for row in rows]
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()

    def legacy_review(self, batch, repo):
        rows = self.rows(batch, repo)
        value = dict(batch=batch, repo=repo, binding=self.unit_binding(rows),
                     records=[(r["path"], r["status"], r["commit_sha"], r["last_attempt"], r["error"]) for r in rows])
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()

    def reliability_control(self, batch, repo, expected_head, settings, legacy_review):
        if sanitize_data(settings) != settings:
            raise ValueError("Unsafe reliability settings; nothing persisted")
        raw = json.dumps(settings, sort_keys=True, separators=(",", ":"))
        old = self.db.execute("SELECT * FROM publication_controls WHERE batch=? AND repo=?", (batch, repo)).fetchone()
        if old:
            if old["settings"] != raw or (expected_head and expected_head != old["origin_head"]):
                raise ValueError("Reliability settings or approved origin changed")
            return dict(old)
        if not expected_head or len(expected_head) != 40 or any(c not in "0123456789abcdef" for c in expected_head):
            raise ValueError("Reliability migration requires the explicitly reviewed expected HEAD")
        if any(r["last_attempt"] for r in self.rows(batch, repo)) and legacy_review != self.legacy_review(batch, repo):
            raise ValueError("Legacy attempts require an explicit matching review digest before migration")
        with self.db:
            self.db.execute("INSERT INTO publication_controls VALUES (?,?,?,?,?)", (batch, repo, expected_head, expected_head, raw))
        return dict(self.db.execute("SELECT * FROM publication_controls WHERE batch=? AND repo=?", (batch, repo)).fetchone())

    def unit(self, batch, repo, number, rows, initial=None):
        binding = self.unit_binding(rows)
        key = str(number)
        old = self.db.execute("SELECT binding,data FROM publication_units WHERE batch=? AND repo=? AND unit=?", (batch, repo, key)).fetchone()
        if old:
            if old["binding"] != binding:
                raise ValueError("Frozen publication unit changed")
            return json.loads(old["data"])
        if initial is None:
            return None
        data = dict(initial, stage=initial.get("stage", "prepared"), status="pending", done=[], intent=None,
                    attempts=0, first_failure=0, not_before=0, error={})
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"))
        if sanitize_data(data) != data:
            raise ValueError("Unsafe unit metadata")
        with self.db:
            self.db.execute("INSERT INTO publication_units VALUES (?,?,?,?,?)", (batch, repo, key, binding, raw))
            self.db.executemany("INSERT INTO publication_unit_members VALUES (?,?,?,?)", [(batch, repo, r["path"], key) for r in rows])
        return data

    def save_unit(self, batch, repo, number, data):
        if sanitize_data(data) != data:
            raise ValueError("Unsafe unit metadata")
        with self.db:
            result = self.db.execute("UPDATE publication_units SET data=? WHERE batch=? AND repo=? AND unit=?",
                (json.dumps(data, sort_keys=True, separators=(",", ":")), batch, repo, str(number)))
            if result.rowcount != 1:
                raise ValueError("Missing publication unit")

    def complete_unit(self, batch, repo, number, rows, data):
        """Remote verification precedes one atomic ownership/receipt transition."""
        value = dict(data, stage="published", status="completed", intent=None, not_before=0, error={})
        if sanitize_data(value) != value:
            raise ValueError("Unsafe unit metadata")
        with self.db:
            head = self.db.execute("SELECT head FROM publication_controls WHERE batch=? AND repo=?", (batch, repo)).fetchone()
            if not head or head[0] != data["parent"]:
                raise ValueError("Publication ownership changed")
            # Previously completed receipts retain their exact SHA and timestamps.
            self.db.executemany("UPDATE publications SET status='published',commit_sha=?,last_attempt=?,error='' "
                "WHERE batch=? AND repo=? AND path=? AND status!='published'",
                [(data["commit"], time.time(), batch, repo, r["path"]) for r in rows])
            self.db.execute("UPDATE publication_controls SET head=? WHERE batch=? AND repo=?", (data["commit"], batch, repo))
            self.db.execute("UPDATE publication_units SET data=? WHERE batch=? AND repo=? AND unit=?",
                (json.dumps(value, sort_keys=True, separators=(",", ":")), batch, repo, str(number)))

    def reliability_progress(self, batch, repo):
        units = {r["unit"]: json.loads(r["data"]) for r in self.db.execute(
            "SELECT unit,data FROM publication_units WHERE batch=? AND repo=?", (batch, repo))}
        members = dict(self.db.execute("SELECT path,unit FROM publication_unit_members WHERE batch=? AND repo=?", (batch, repo)))
        result = dict(published=0, pending=0, retrying=0, permanently_failed=0, blocked=0,
                      completed_units=sum(u["status"] == "completed" for u in units.values()))
        for row in self.rows(batch, repo):
            status = units.get(members.get(row["path"]), {}).get("status", "pending")
            key = "published" if row["status"] == "published" else "permanently_failed" if status == "permanently_failed" or row["status"] == "conflict" else status if status in {"retrying", "blocked"} else "pending"
            result[key] += 1
        return result

    def __init__(self, state):
        self.state = Path(state)
        reject_links(self.state)
        self.state.mkdir(parents=True, exist_ok=True)
        reject_links(self.state / "publication_state.db")
        self.db = sqlite3.connect(self.state / "publication_state.db", timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS batches (id TEXT PRIMARY KEY, expected INTEGER, branch TEXT);
          CREATE TABLE IF NOT EXISTS publications (
            batch TEXT, style TEXT, repo TEXT, path TEXT, source TEXT, source_hash TEXT,
            prepared TEXT, published_hash TEXT, blob TEXT, branch TEXT, person TEXT, tmdb_id TEXT,
            status TEXT, commit_sha TEXT, last_attempt REAL, error TEXT,
            PRIMARY KEY(batch, repo, path));
          CREATE TABLE IF NOT EXISTS readmes (
            batch TEXT, repo TEXT, status TEXT, error TEXT, PRIMARY KEY(batch, repo));
          CREATE TABLE IF NOT EXISTS baselines (
            batch TEXT, repo TEXT, path TEXT, sha TEXT, PRIMARY KEY(batch, repo, path));
        """)
        if "details" not in {row["name"] for row in self.db.execute("PRAGMA table_info(readmes)")}:
            self.db.execute("ALTER TABLE readmes ADD COLUMN details TEXT NOT NULL DEFAULT '{}'")
            self.db.commit()

    def close(self):
        self.db.close()

    def plan(self, batch, branch, entries):
        if not ID_PATTERN.fullmatch(batch):
            raise ValueError("Invalid publication batch identifier")
        old = self.db.execute("SELECT * FROM batches WHERE id=?", (batch,)).fetchone()
        previous = self.rows(batch)
        if old:
            before = {(r["repo"], r["path"], r["blob"], r["source_hash"]) for r in previous}
            after = {(r["repo"], r["path"], r["blob"], r["source_hash"]) for r in entries}
            if old["branch"] != branch or before != after:
                raise ValueError("Prepared batch changed after planning; use a new batch to avoid losing publication receipts")
            return
        with self.db:
            self.db.execute("INSERT INTO batches VALUES (?,?,?)", (batch, len(entries), branch))
            for row in entries:
                self.db.execute("INSERT INTO publications VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    batch, row["style"], row["repo"], row["path"], row["source"], row["source_hash"],
                    row["prepared"], row["published_hash"], row["blob"], branch, row["person"], row.get("tmdb_id", ""),
                    "pending", "", 0, ""))
                self.db.execute("INSERT OR IGNORE INTO readmes (batch,repo,status,error) VALUES (?,?,'unchanged','')", (batch, row["repo"]))
        self.export(batch)

    def rows(self, batch, repo=None):
        query = "SELECT * FROM publications WHERE batch=?"
        values = [batch]
        if repo:
            query += " AND repo=?"
            values.append(repo)
        return [dict(row) for row in self.db.execute(query + " ORDER BY repo,path", values)]

    def baseline(self, batch, repo, path, current):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO baselines VALUES (?,?,?,?)", (batch, repo, path, current or ""))
        return self.db.execute("SELECT sha FROM baselines WHERE batch=? AND repo=? AND path=?", (batch, repo, path)).fetchone()[0] or None

    def mark(self, batch, repo, paths, status, commit="", error=""):
        error = sanitize_text(error) if type(error) is str else safe_exception(error)
        with self.db:
            self.db.executemany("UPDATE publications SET status=?,commit_sha=?,last_attempt=?,error=? WHERE batch=? AND repo=? AND path=?",
                                [(status, commit, time.time(), error, batch, repo, path) for path in paths])
        self.export(batch)

    def readme_state(self, batch, repo):
        row = self.db.execute("SELECT * FROM readmes WHERE batch=? AND repo=?", (batch, repo)).fetchone()
        if row is None:
            raise ValueError("Missing README publication receipt")
        return dict(row, details=json.loads(row["details"]))

    def readme(self, batch, repo, status, error="", details=None):
        error = sanitize_text(error) if type(error) is str else safe_exception(error)
        with self.db:
            self.db.execute("UPDATE readmes SET status=?,error=? WHERE batch=? AND repo=?", (status, error, batch, repo))
            if details is not None:
                self.db.execute("UPDATE readmes SET details=? WHERE batch=? AND repo=?",
                                (json.dumps(details), batch, repo))
        self.export(batch)

    def verified(self, batch):
        row = self.db.execute("SELECT expected FROM batches WHERE id=?", (batch,)).fetchone()
        if not row or row["expected"] <= 0:
            return False
        entries = self.rows(batch)
        if len(entries) != row["expected"] or any(e["status"] != "published" or not e["commit_sha"] for e in entries):
            return False
        readmes = list(self.db.execute("SELECT repo,status FROM readmes WHERE batch=?", (batch,)))
        return ({r["repo"] for r in readmes} == {e["repo"] for e in entries}
                and all(r["status"] in {"verified", "disabled"} for r in readmes))

    def export(self, batch):
        if not ID_PATTERN.fullmatch(batch):
            raise ValueError("Invalid batch identifier")
        rows = self.rows(batch)
        if len(rows) > 4096:
            # Reuse the proven operator adapter's content-addressed export.
            # Old parts remain recovery evidence; only the index is replaced.
            chunks = []
            for offset in range(0, len(rows), 1000):
                value = dict(batch_id=batch, publications=rows[offset:offset + 1000])
                digest = hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
                name = batch + "/" + f"{offset // 1000:04d}-" + digest + ".json"
                atomic_json(self.state / "manifests" / name, value)
                chunks.append(dict(path=name, count=len(value["publications"])))
            atomic_json(self.state / "manifests" / (batch + ".json"), dict(batch_id=batch,
                publication_count=len(rows), publication_chunks=chunks,
                readmes=[self.readme_state(batch, r["repo"]) for r in self.db.execute("SELECT repo FROM readmes WHERE batch=?", (batch,))]))
            return
        atomic_json(self.state / "manifests" / (batch + ".json"), {
            "batch_id": batch, "publications": self.rows(batch),
            "readmes": [self.readme_state(batch, r["repo"]) for r in self.db.execute("SELECT repo FROM readmes WHERE batch=?", (batch,))],
        })
