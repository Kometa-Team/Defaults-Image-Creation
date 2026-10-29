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
import sqlite3
import time
from pathlib import Path

from people_workspaces import ID_PATTERN, atomic_json, reject_links


class PublicationState:
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
        atomic_json(self.state / "manifests" / (batch + ".json"), {
            "batch_id": batch, "publications": self.rows(batch),
            "readmes": [self.readme_state(batch, r["repo"]) for r in self.db.execute("SELECT repo FROM readmes WHERE batch=?", (batch,))],
        })
