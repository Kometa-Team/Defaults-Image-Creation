"""Development-attributed, version-bound human review. No authentication/publishing."""

import json
from pathlib import Path
import uuid

from .common import BulkError, Conflict, canonical, confined, fingerprint, path_key, sha256
from .preflight import ELIGIBLE, POLICY
from .translations import key_token


STATES = {"not_evaluated", "preflight_blocked", "ready_for_review", "approved", "approved_with_accepted_warnings",
          "rejected", "approval_stale"}


class Reviews:
    def __init__(self, store, config):
        self.store, self.config = store, config

    def ingest(self, report):
        payload = {k: v for k, v in report.items() if k not in {"sha256", "report_directory", "metrics"}}
        if fingerprint(payload) != report["sha256"]:
            raise BulkError("corrupt_preflight", "Preflight report hash mismatch")
        policy = fingerprint(report["policy"])
        with self.store.transaction() as db:
            for variant in report["variants"]:
                identity, validation = variant["id"], variant["validation_fingerprint"]
                evidence = {"variant": variant, "registry_sha256": report["registry_sha256"], "policy": report["policy"],
                            "renderer": report["renderer"], "preflight_sha256": report["sha256"]}
                encoded = canonical(evidence).decode()
                old = db.execute("SELECT * FROM review_variants WHERE id=?", (identity,)).fetchone()
                db.execute("INSERT OR IGNORE INTO review_revisions VALUES (?,?,?)", (identity, validation, encoded))
                if old and old["validation"] == validation and old["policy"] == policy:
                    continue
                state = "preflight_blocked" if variant["status"] not in ELIGIBLE else "not_evaluated"
                if old and old["state"] in {"approved", "approved_with_accepted_warnings", "approval_stale"}:
                    state = "approval_stale"
                db.execute("INSERT OR REPLACE INTO review_variants VALUES (?,?,?,?,?,?,NULL)",
                           (identity, old["version"] + 1 if old else 0, state, validation, policy, encoded))
                db.execute("DELETE FROM translation_dependencies WHERE variant=?", (identity,))
                for key in variant["translation_dependencies"]:
                    db.execute("INSERT OR REPLACE INTO translation_dependencies VALUES (?,?,?,?)", (key["language"], key_token(key["key"]), identity, validation))
                self.store.event(db, "review_preflight", identity, {"validation": validation, "state": state, "previous_validation": old["validation"] if old else None})

    def item(self, identity):
        with self.store.connection() as db:
            row = db.execute("SELECT * FROM review_variants WHERE id=?", (identity,)).fetchone()
        if not row:
            raise BulkError("missing_review", "Unknown review variant")
        value = dict(row)
        value["evidence"] = json.loads(value["evidence"])
        value["preview"] = json.loads(value["preview"]) if value["preview"] else None
        if value["policy"] != fingerprint(POLICY) and value["state"] in {"approved", "approved_with_accepted_warnings", "ready_for_review"}:
            value["stored_state"], value["state"] = value["state"], "approval_stale"
        return value

    def query(self, states=()):
        aliases = {"pending": {"not_evaluated", "ready_for_review"}, "blocked": {"preflight_blocked"}, "stale": {"approval_stale"},
                   "approved": {"approved", "approved_with_accepted_warnings"}}
        states = {value for state in states for value in aliases.get(state, {state})}
        if set(states) - STATES:
            raise BulkError("invalid_review_state", "Unknown review state")
        with self.store.connection() as db:
            ids = [r["id"] for r in db.execute("SELECT id FROM review_variants ORDER BY id")]
        items = [self.item(identity) for identity in ids]
        return [item for item in items if not states or item["state"] in states]

    def attach(self, result):
        """Only byte-verified shared-worker receipts can become review previews."""
        report = result["preflight"]
        self.ingest(report)
        by_id = {v["id"]: v for v in report["variants"]}
        for stage in result["stages"]:
            for job in stage["manifest"]["jobs"]:
                identity = job["id"]
                execution = stage["execution"]["jobs"].get(identity, {})
                if execution.get("status") not in {"rendered", "cache_reuse", "dedup_reuse"}:
                    continue
                target = confined(self.config.output_dir, job["local_relative"], must_exist=True)
                checksum = sha256(target)
                if checksum != execution["sha256"]:
                    raise Conflict("Preview bytes changed after worker verification")
                preview = {"sha256": checksum, "local_relative": job["local_relative"], "root": fingerprint(str(self.config.output_dir)),
                           "render_fingerprint": job["render_fingerprint"], "validation": by_id[identity]["validation_fingerprint"]}
                with self.store.transaction() as db:
                    row = db.execute("SELECT * FROM review_variants WHERE id=?", (identity,)).fetchone()
                    claim = db.execute("SELECT state_id FROM output_claims WHERE root=? AND path_key=?", (preview["root"], path_key(job["local_relative"]))).fetchone()
                    owned = db.execute("SELECT * FROM jobs WHERE id=?", (claim["state_id"],)).fetchone() if claim else None
                    receipt = json.loads(owned["receipt"]) if owned and owned["status"] == "verified" else {}
                    if receipt.get("logical_id") != identity or receipt.get("sha256") != checksum or receipt.get("render_fingerprint") != preview["render_fingerprint"]:
                        raise Conflict("Preview has no matching owned verified worker receipt")
                    if not row or row["validation"] != preview["validation"]:
                        raise Conflict("Validation changed during preview generation")
                    if row["preview"] == canonical(preview).decode():
                        continue
                    state = "approval_stale" if row["state"] in {"approved", "approved_with_accepted_warnings"} else "ready_for_review"
                    db.execute("UPDATE review_variants SET version=version+1,state=?,preview=? WHERE id=?", (state, canonical(preview).decode(), identity))
                    self.store.event(db, "preview_attached", identity, preview)

    def batch(self, identities, *, scope, inspected=()):
        members = []
        if not identities or len(set(identities)) != len(identities) or set(inspected) - set(identities):
            raise BulkError("invalid_batch", "Enumerate unique members and exact inspected subset")
        for identity in sorted(identities):
            item = self.item(identity)
            members.append({"id": identity, "version": item["version"], "validation": item["validation"],
                            "image_sha256": item["preview"]["sha256"] if item["preview"] else None, "policy": item["policy"]})
        membership = fingerprint(members)
        value = {"members": members, "scope": scope, "inspected": sorted(inspected), "membership": membership,
                 "attribution": "CLI development identity, not authenticated authorization"}
        identity = "review-batch." + uuid.uuid4().hex
        with self.store.transaction() as db:
            db.execute("INSERT INTO review_batches VALUES (?,?,?)", (identity, membership, canonical(value).decode()))
            self.store.event(db, "review_batch_created", identity, value)
        return {"id": identity, **value}

    def _current(self, db, identity, version):
        row = db.execute("SELECT * FROM review_variants WHERE id=?", (identity,)).fetchone()
        if not row or row["version"] != version:
            raise Conflict()
        return row

    def _approvable(self, row, accepted, *, individual, db):
        evidence = json.loads(row["evidence"])
        variant = evidence["variant"]
        preview = json.loads(row["preview"]) if row["preview"] else None
        if variant["status"] not in ELIGIBLE or variant["private"]:
            raise BulkError("blocked_approval", "Blocked/non-applicable/private intermediates cannot be approved")
        if not preview or preview["validation"] != row["validation"] or row["policy"] != fingerprint(POLICY):
            raise Conflict("No current preview or validation policy is obsolete")
        if preview["root"] != fingerprint(str(self.config.output_dir)) or sha256(confined(self.config.output_dir, preview["local_relative"], must_exist=True)) != preview["sha256"]:
            raise Conflict("Reviewed output bytes changed")
        claim = db.execute("SELECT j.receipt FROM output_claims c JOIN jobs j ON j.id=c.state_id WHERE c.root=? AND c.path_key=? AND j.status='verified'",
                           (preview["root"], path_key(preview["local_relative"]))).fetchone()
        receipt = json.loads(claim["receipt"]) if claim else {}
        if receipt.get("render_fingerprint") != preview["render_fingerprint"] or receipt.get("logical_id") != row["id"] or receipt.get("sha256") != preview["sha256"]:
            raise Conflict("Current output generation differs from the reviewed preview")
        from .planner import renderer_identity
        current_renderer = renderer_identity()
        if variant.get("kind") == "overlay":
            from .overlays import identity
            current_renderer = identity()
        if evidence["renderer"] != current_renderer:
            raise Conflict("Renderer changed; run preflight and preview again")
        # Recheck exact source files too: an old preview cannot approve changed assets.
        for source in variant["inputs"].values():
            if sha256(confined(self.config.asset_dir, source["path"], must_exist=True)) != source["sha256"]:
                raise Conflict("Source asset changed; run preflight and preview again")
        warnings = {d["code"] for d in variant["diagnostics"] if d["severity"] == "warning"}
        if set(accepted) != warnings:
            raise BulkError("unaccepted_warnings", "Accept exactly the current nonblocking warning codes")
        if (variant["risk"]["requires_individual"] or row["state"] in {"rejected", "approval_stale"}) and not individual:
            raise BulkError("individual_review_required", "Unresolved high-risk variants require individual review")
        return preview

    def decide(self, identity, *, expected_version, reviewer, action, accepted_warnings=(), comment="", policy=None):
        if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 256 or len(comment) > 16384:
            raise BulkError("invalid_reviewer", "Bounded nonempty development reviewer attribution required")
        if action not in {"approve", "reject", "comment", "reopen"}:
            raise BulkError("invalid_review_action", "Unknown review action")
        with self.store.transaction() as db:
            row = self._current(db, identity, expected_version)
            if policy is not None and row["policy"] != policy:
                raise Conflict("Requested validation policy changed")
            state = row["state"]
            if action == "approve":
                self._approvable(row, accepted_warnings, individual=True, db=db)
                state = "approved_with_accepted_warnings" if accepted_warnings else "approved"
            elif action == "reject":
                state = "rejected"
            elif action == "reopen":
                state = "approval_stale" if row["preview"] else "not_evaluated"
            db.execute("UPDATE review_variants SET version=version+1,state=? WHERE id=?", (state, identity))
            self.store.event(db, "review_" + action, identity, {"reviewer": reviewer, "development_attribution_only": True,
                "version": expected_version + 1, "validation": row["validation"], "policy": row["policy"],
                "preview": json.loads(row["preview"]) if row["preview"] else None, "accepted_warnings": sorted(accepted_warnings),
                "comment": comment, "decision_type": "individual"})
        return self.item(identity)

    def approve_group(self, batch_id, *, membership, reviewer, comment=""):
        if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 256 or len(comment) > 16384:
            raise BulkError("invalid_reviewer", "Bounded development attribution required")
        with self.store.transaction() as db:
            batch = db.execute("SELECT * FROM review_batches WHERE id=?", (batch_id,)).fetchone()
            if not batch or batch["membership"] != membership:
                raise Conflict("Batch membership changed or unknown")
            payload = json.loads(batch["payload"])
            for member in payload["members"]:
                row = self._current(db, member["id"], member["version"])
                preview = self._approvable(row, (), individual=False, db=db)
                if preview["sha256"] != member["image_sha256"] or row["validation"] != member["validation"] or row["policy"] != member["policy"]:
                    raise Conflict("Group evidence changed")
            for member in payload["members"]:
                db.execute("UPDATE review_variants SET version=version+1,state='approved' WHERE id=?", (member["id"],))
                self.store.event(db, "review_group_approve", member["id"], {"reviewer": reviewer, "development_attribution_only": True,
                    "batch": batch_id, "membership": membership, "member": member, "inspected": payload["inspected"],
                    "decision_type": "representative-group", "comment": comment})
        return {"batch": batch_id, "approved": len(payload["members"]), "membership": membership}

    def invalidate_keys(self, changes, *, reason, languages=(), resources=()):
        affected = set()
        with self.store.transaction() as db:
            for language, key in changes:
                affected.update(r["variant"] for r in db.execute("SELECT variant FROM translation_dependencies WHERE language=? AND key=?", (language, key_token(key))))
            for language in resources:
                affected.update(r["variant"] for r in db.execute("SELECT variant FROM translation_dependencies WHERE language=?", (language,)))
            if languages:
                for row in db.execute("SELECT id,evidence FROM review_variants"):
                    if json.loads(row["evidence"])["variant"]["language"] in languages:
                        affected.add(row["id"])
            for identity in sorted(affected):
                db.execute("UPDATE review_variants SET state='approval_stale',version=version+1,preview=NULL WHERE id=?", (identity,))
                self.store.event(db, "review_translation_stale", identity, {"reason": reason})
        return sorted(affected)

    def export(self):
        with self.store.connection() as db:
            events = [dict(r) | {"payload": json.loads(r["payload"])} for r in db.execute("SELECT * FROM events WHERE kind LIKE 'review_%' OR kind='preview_attached' ORDER BY sequence")]
            batches = [dict(r) | {"payload": json.loads(r["payload"])} for r in db.execute("SELECT * FROM review_batches ORDER BY id")]
        return {"items": self.query(), "batches": batches, "events": events, "authorization": "Development attribution only; real authorization required before production approval service"}
