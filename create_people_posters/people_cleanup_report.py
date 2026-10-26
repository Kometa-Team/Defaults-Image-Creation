"""Read-only People storage inventory; explicit owned-operation cleanup only.

Does not construct Workspaces/PublicationState (their constructors write SQLite).
Batch estimates reproduce existing retention gates without authorizing deletion.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import stat
import time

from create_people_posters.people_diagnostics import sanitize_data, safe_exception
from create_people_posters.people_workspaces import ID_PATTERN, reject_links
from create_people_posters.people_recovery_storage import cleanup, sha, StorageBlocked

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def _reason(exc):
    return exc.args[0] if type(exc) is StorageBlocked else safe_exception(exc)


def inventory(root):
    """Size only, no link traversal, reads no credentials or image contents."""
    root = Path(root).absolute()
    reject_links(root)
    entries, blocked = {}, []
    if not root.exists():
        return entries, blocked
    def walk(folder):
        with os.scandir(folder) as stream:
            for entry in stream:
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                try:
                    reject_links(path)
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        walk(path)
                    elif stat.S_ISREG(info.st_mode):
                        entries[relative] = dict(bytes=info.st_size, modified=info.st_mtime)
                    else:
                        blocked.append(dict(path=relative, reason="special file"))
                except (OSError, ValueError) as exc:
                    blocked.append(dict(path=relative, reason=type(exc).__name__ + ": unreadable or linked path"))
    walk(root)
    return entries, blocked


def _json(path):
    reject_links(path)
    if path.stat().st_size > 8 * 1024 * 1024:
        raise StorageBlocked("Metadata size limit exceeded")
    return json.loads(path.read_text(encoding="utf8"))


def _category(name):
    parts = Path(name).parts
    if "edge_chop_recovery" in parts:
        if "candidates" in parts and "operations" not in parts:
            return "legacy_candidates_unowned"
        if "operations" in parts:
            return "owned_recovery_operations"
        if "transactions" in parts:
            return "rollback_evidence"
        return "recovery_reports_history"
    if parts[0] == "jobs":
        if "logs" in parts:
            return "batch_logs"
        if "original" in parts:
            return "batch_originals"
        if "prepared" in parts:
            return "batch_publication_staging"
        return "batch_inputs_and_intermediates"
    return {"models": "model_cache", "vendor": "vendor", "state": "durable_state_receipts",
            "logs": "persistent_logs", "Downloads": "colorization_staging",
            "people_dirs": "persistent_artwork", "sel_downloads": "background_mirrors",
            "posters": "downloaded_inputs"}.get(parts[0], "other_retained")


def _batch(folder, row, db, entries, blocked, now, retention):
    result = dict(id=folder.name, files=len(entries), bytes=sum(e["bytes"] for e in entries.values()),
                  status=row["status"] if row else "unregistered", eligible_files=0, eligible_bytes=0)
    if row:
        result.update(age_days=round((now - row["created"]) / 86400, 3),
                      updated_age_days=round((now - row["updated"]) / 86400, 3))
    try:
        if blocked:
            raise StorageBlocked("unreadable, special or linked batch path")
        if not row:
            raise StorageBlocked("batch missing from durable job ledger")
        manifest = _json(folder / "manifest.json")
        if manifest.get("id") != folder.name or manifest.get("managed_by") != "kometa-people-v1":
            raise StorageBlocked("unowned batch manifest")
        if (folder / ".active").exists():
            raise StorageBlocked("active batch lease (including stale leases)")
        if row["status"] not in {"published", "cleanup_eligible"} or row["published"] is None:
            raise StorageBlocked("complete: compact evidence retained" if row["status"] == "complete"
                             else "unpublished or incomplete batch; manual recovery required")
        result["published_age_days"] = round((now - row["published"]) / 86400, 3)
        batch = db.execute("SELECT expected FROM batches WHERE id=?", (folder.name,)).fetchone()
        receipts = list(db.execute("SELECT * FROM publications WHERE batch=?", (folder.name,)))
        readmes = list(db.execute("SELECT status FROM readmes WHERE batch=?", (folder.name,)))
        if (not batch or batch["expected"] <= 0 or len(receipts) != batch["expected"]
                or any(r["status"] != "published" or not r["commit_sha"] for r in receipts)
                or not readmes or any(r["status"] not in {"dispatched", "disabled", "warning", "unchanged"} for r in readmes)):
            raise StorageBlocked("publication receipts incomplete")
        result["publication_verified"] = True
        if now - row["published"] < retention * 86400:
            raise StorageBlocked("verified-publication retention window has not elapsed")
        catalog = manifest.get("cleanup_files")
        if type(catalog) is not dict:
            raise StorageBlocked("cleanup image catalog missing")
        for name in entries:
            path = folder / name
            if path.suffix.lower() in IMAGE_SUFFIXES and sha(path) != catalog.get(name):
                raise StorageBlocked("local image changed after publication")
        for receipt in receipts:
            for key, checksum in (("prepared", "published_hash"), ("source", "source_hash")):
                path = Path(receipt[key])
                reject_links(path)
                if path.exists() and sha(path) != receipt[checksum]:
                    raise StorageBlocked("local publication source changed")
        removable = {n: e for n, e in entries.items() if n != "manifest.json" and Path(n).parts[0] != "logs"}
        result.update(eligible_files=len(removable), eligible_bytes=sum(e["bytes"] for e in removable.values()),
                      reason="eligible under existing batch policy; report grants no deletion authority")
    except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
        result["blocked"] = _reason(exc)
    return result


def report(config, *, jobs=None, state=None, recovery=None, now=None, retention_days=3):
    config = Path(config).absolute()
    jobs = Path(jobs).absolute() if jobs else config / "jobs"
    state = Path(state).absolute() if state else config / "state"
    recovery = Path(recovery).absolute() if recovery else config / "edge_chop_recovery"
    if retention_days < 0:
        raise StorageBlocked("Retention days cannot be negative")
    now = time.time() if now is None else now
    entries, blocked = inventory(config)
    categories = {}
    for name, entry in entries.items():
        category = categories.setdefault(_category(name), dict(files=0, bytes=0))
        category["files"] += 1
        category["bytes"] += entry["bytes"]
    # Explicit external roots are inventoried separately and never traversed twice.
    counted_roots = [config]
    external = sorted((("external_jobs", jobs), ("external_state", state), ("external_recovery", recovery)),
                      key=lambda item: len(item[1].parts))
    for label, root in external:
        if not any(root.is_relative_to(previous) for previous in counted_roots):
            extra, errors = inventory(root)
            categories[label] = dict(files=len(extra), bytes=sum(e["bytes"] for e in extra.values()))
            blocked.extend(dict(path=label + "/" + e["path"], reason=e["reason"]) for e in errors)
            counted_roots.append(root)
    operations = []
    roots = [recovery]
    reject_links(jobs)
    batches = []
    db = None
    database = state / "publication_state.db"
    reject_links(database)
    try:
        ledger_error = "job ledger missing"
        if database.is_file():
            # mode=ro cannot create a DB, table, job, receipt or status transition.
            db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
        rows = {r["id"]: r for r in db.execute("SELECT * FROM jobs")} if db else {}
        for folder in sorted(jobs.iterdir()) if jobs.exists() else []:
            try:
                reject_links(folder)
                if not folder.is_dir() or not ID_PATTERN.fullmatch(folder.name):
                    blocked.append(dict(path="jobs/" + folder.name, reason="unowned job path"))
                    continue
                items, errors = inventory(folder)
                batches.append(_batch(folder, rows.get(folder.name), db, items, errors, now, retention_days))
                roots.append(folder / "edge_chop_recovery")
            except (ValueError, OSError) as exc:
                blocked.append(dict(path="jobs/" + folder.name, reason=_reason(exc)))
    except sqlite3.Error:
        ledger_error = "job ledger unreadable or incompatible; batches retained"
        blocked.append(dict(path="state/publication_state.db", reason=ledger_error))
    finally:
        if db:
            db.close()
    roots = list(dict.fromkeys(roots))
    for root in roots:
        reject_links(root)
        operations_root = root / "operations"
        reject_links(operations_root)
        for folder in sorted(operations_root.iterdir()) if operations_root.exists() else []:
            try:
                operations.append(cleanup(folder, dry_run=True))
            except (ValueError, OSError, KeyError, TypeError) as exc:
                operations.append(dict(id=folder.name, blocked=_reason(exc)))
    legacy = []
    for root in roots:
        candidates = root / "candidates"
        try:
            items, errors = inventory(candidates)
            if items or errors:
                scope = candidates.relative_to(config).as_posix() if candidates.is_relative_to(config) else "external_recovery/candidates"
                legacy.append(dict(root=scope, paths=sorted(items), files=len(items), bytes=sum(e["bytes"] for e in items.values()),
                                   blocked="legacy candidates lack operation ownership and verified success evidence; manual review required"))
        except (ValueError, OSError) as exc:
            legacy.append(dict(blocked=_reason(exc)))
    return dict(schema_version=1, read_only=True, generated=now, retention_days=retention_days,
                categories=categories, retained_batch_count=sum(b["status"] != "complete" for b in batches),
                batches=batches, operations=operations, legacy_candidates=legacy, blocked_paths=blocked,
                owned_scratch_recoverable_bytes=sum(o.get("eligible_bytes", 0) for o in operations),
                batch_policy_recoverable_bytes=sum(b["eligible_bytes"] for b in batches))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, default=Path(__file__).parent / "config")
    parser.add_argument("--jobs-dir", type=Path, default=os.getenv("PEOPLE_JOBS_DIR"))
    parser.add_argument("--state-dir", type=Path, default=os.getenv("PEOPLE_STATE_DIR"))
    parser.add_argument("--recovery-root", type=Path, default=os.getenv("EDGE_CHOP_OUT_ROOT"))
    parser.add_argument("--retention-days", type=float, default=float(os.getenv("PEOPLE_BATCH_RETENTION_DAYS", "3")))
    parser.add_argument("--operation", help="One owned UUID; dry-run by default, never legacy folders or batches")
    parser.add_argument("--apply", action="store_true", help="Explicitly remove eligible files in --operation only")
    args = parser.parse_args()
    if args.apply and not args.operation:
        parser.error("--apply requires one explicit --operation UUID")
    if args.operation:
        from create_people_posters.people_recovery_storage import ID
        if not ID.fullmatch(args.operation):
            parser.error("Invalid operation UUID")
        root = args.recovery_root or args.config_dir / "edge_chop_recovery"
        try:
            result = cleanup(root / "operations" / args.operation, dry_run=not args.apply)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            result = dict(id=args.operation, blocked=_reason(exc), removed_files=0, recovered_bytes=0)
    else:
        result = report(args.config_dir, jobs=args.jobs_dir, state=args.state_dir, recovery=args.recovery_root,
                        retention_days=args.retention_days)
    print(json.dumps(sanitize_data(result), indent=2))
    return 1 if args.operation and result.get("blocked") else 0


if __name__ == "__main__":
    from create_people_posters.people_diagnostics import protect_cli, register_environment
    register_environment()
    protect_cli()
    raise SystemExit(main())
