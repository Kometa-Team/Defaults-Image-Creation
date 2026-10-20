"""Owned temporary data and verified atomic receipts; never source cleanup."""

import json
from pathlib import Path
import shutil
import uuid

from .common import BulkError, Conflict, atomic_bytes, canonical, confined, fingerprint, reject_links, sha256


class Workspaces:
    def __init__(self, store, root):
        self.store = store
        self.root = reject_links(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self):
        identity, token = uuid.uuid4().hex, uuid.uuid4().hex
        path = confined(self.root, identity)
        path.mkdir()
        atomic_bytes(path / "owner.json", canonical({"id": identity, "token": token}))
        with self.store.transaction() as db:
            db.execute("INSERT INTO workspaces VALUES (?,?,?,'active')", (identity, token, self.store.clock()))
            self.store.event(db, "workspace_created", identity, {})
        return {"identity": identity, "token": token}

    def owned(self, identity, token, *, allow_pending=False):
        path = confined(self.root, identity)
        with self.store.connection() as db:
            row = db.execute("SELECT * FROM workspaces WHERE id=?", (identity,)).fetchone()
        if row is None or row["token"] != token or row["status"] not in ({"active", "cleanup_pending"} if allow_pending else {"active"}):
            raise BulkError("unowned_workspace", "Workspace ownership is absent or mismatched")
        try:
            if allow_pending and row["status"] == "cleanup_pending" and path.is_dir() and not (path / "owner.json").exists():
                atomic_bytes(path / "owner.json", canonical({"id": identity, "token": token}))
            marker = json.loads(confined(path, "owner.json", must_exist=True).read_text(encoding="utf-8"))
        except (ValueError, OSError) as error:
            raise BulkError("unowned_workspace", "Workspace owner marker is corrupt") from error
        if marker != {"id": identity, "token": token}:
            raise BulkError("unowned_workspace", "Workspace marker does not match its state record")
        return path

    def receipt(self, identity, token, *, job_id, relative_artifact):
        path = self.owned(identity, token)
        self.bind_job(identity, token, job_id)
        artifact = confined(path, relative_artifact, must_exist=True)
        job = self.store.job(job_id)
        payload = {"schema_version": 1, "workspace": identity, "job_id": job_id, "job_fingerprint": job["fingerprint"],
                   "artifact": relative_artifact, "sha256": sha256(artifact), "size": artifact.stat().st_size}
        payload["receipt_sha256"] = fingerprint(payload)
        target = confined(path, "receipts/" + fingerprint(job_id) + ".json")
        if target.exists():
            if target.read_bytes() != canonical(payload):
                raise Conflict("Retained receipt binds a different artifact/version")
        else:
            atomic_bytes(target, canonical(payload))
        return payload

    def verify_receipt(self, identity, token, receipt):
        path = self.owned(identity, token)
        payload = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        if receipt.get("workspace") != identity or receipt.get("schema_version") != 1 or fingerprint(payload) != receipt.get("receipt_sha256"):
            raise BulkError("corrupt_receipt", "Receipt integrity mismatch")
        job = self.store.job(receipt["job_id"])
        artifact = confined(path, receipt["artifact"], must_exist=True)
        if job["fingerprint"] != receipt["job_fingerprint"] or artifact.stat().st_size != receipt["size"] or sha256(artifact) != receipt["sha256"]:
            raise BulkError("corrupt_artifact", "Artifact or specification differs from the retained receipt")
        return receipt

    def cleanup(self, identity, token, *, retain_seconds):
        if type(retain_seconds) is not int or retain_seconds < 0:
            raise BulkError("invalid_retention", "Explicit nonnegative retention interval required")
        path = self.owned(identity, token, allow_pending=True)
        with self.store.transaction() as db:
            row = db.execute("SELECT * FROM workspaces WHERE id=?", (identity,)).fetchone()
            if row["token"] != token or row["status"] not in {"active", "cleanup_pending"} or self.store.clock() - row["created"] < retain_seconds:
                raise Conflict("Workspace is still retained or changed ownership")
            if db.execute("SELECT 1 FROM workspace_jobs JOIN jobs ON workspace_jobs.job=jobs.id WHERE workspace=? AND jobs.status='running' AND jobs.expires>?", (identity, self.store.clock())).fetchone():
                raise Conflict("An active job still owns this workspace")
            for entry in path.rglob("*"):
                reject_links(entry)
                if not entry.resolve().is_relative_to(path):
                    raise BulkError("unsafe_cleanup", "Workspace cleanup escapes its owned directory")
            db.execute("UPDATE workspaces SET status='cleanup_pending' WHERE id=?", (identity,))
            self.store.event(db, "workspace_cleanup_requested", identity, {})
        # The resolved target is a validated direct child, never an artwork root.
        if path.parent != self.root or path.name != identity:
            raise BulkError("unsafe_cleanup", "Cleanup target is not an owned direct workspace child")
        shutil.rmtree(path)
        with self.store.transaction() as db:
            db.execute("UPDATE workspaces SET status='cleaned' WHERE id=? AND token=?", (identity, token))
            self.store.event(db, "workspace_cleaned", identity, {})

    def recover_cleanup(self):
        """Finalize deleted workspaces; do not delete anything on implicit recovery."""
        with self.store.transaction() as db:
            rows = db.execute("SELECT * FROM workspaces WHERE status='cleanup_pending'").fetchall()
            for row in rows:
                path = confined(self.root, row["id"])
                if not path.exists():
                    db.execute("UPDATE workspaces SET status='cleaned' WHERE id=?", (row["id"],))
                    self.store.event(db, "workspace_cleanup_reconciled", row["id"], {})
        return {"pending": [row["id"] for row in rows if confined(self.root, row["id"]).exists()]}

    def bind_job(self, identity, token, job_id):
        self.owned(identity, token)
        self.store.job(job_id)
        with self.store.transaction() as db:
            row = db.execute("SELECT status,token FROM workspaces WHERE id=?", (identity,)).fetchone()
            if row["status"] != "active" or row["token"] != token:
                raise Conflict("Workspace cleanup began before job binding")
            db.execute("INSERT OR IGNORE INTO workspace_jobs VALUES (?,?)", (identity, job_id))
            self.store.event(db, "workspace_job_bound", identity, {"job": job_id})
