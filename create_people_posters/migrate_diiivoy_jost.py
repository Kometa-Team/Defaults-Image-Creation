"""Standalone, clone-free maintenance for only the two Diiivoy master branches."""

import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

from jost_migration import DEFAULT_ROOT, Migration, source_root, protect_source
from people_github import GitHubError


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    operations = result.add_mutually_exclusive_group()
    for name in ("scan", "render", "compare", "publish", "rollback", "status", "cleanup", "resume"):
        operations.add_argument("--" + name, action="store_true")
    result.add_argument("--migration", help="Immutable migration ID returned by --scan")
    result.add_argument("--transparent-dir", type=Path, default=os.getenv("JOST_MIGRATION_TRANSPARENT_DIR"))
    result.add_argument("--workspace", type=Path, default=DEFAULT_ROOT)
    result.add_argument("--sample", type=int, help="Restrict a new manifest to a deterministic representative sample")
    result.add_argument("--exclude-ambiguous", action="store_true", help="With --scan, explicitly record and exclude all ambiguous source entries")
    result.add_argument("--limit", type=int, help="Maximum people processed in this invocation")
    result.add_argument("--batch-size", type=int, default=int(os.getenv("JOST_MIGRATION_BATCH_SIZE", "50")))
    result.add_argument("--failed-only", action="store_true")
    result.add_argument("--dry-run", action="store_true", help="No remote mutations or file cleanup")
    result.add_argument("--apply", action="store_true", help="Apply verified-file cleanup; otherwise preview only")
    result.add_argument("--confirm", help="Publication: migration ID. Rollback: rollback:MIGRATION_ID")
    result.add_argument("--reviewed", help="SHA-256 of the visually approved review.json")
    return result


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if callable(getattr(stream, "reconfigure", None)):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    load_dotenv(Path(__file__).resolve().parent / "config/.env")
    cli = parser()
    args = cli.parse_args(argv)
    if args.batch_size < 1 or args.batch_size > 100 or (args.limit is not None and args.limit < 1):
        cli.error("Batch size must be 1-100 and limit must be positive")
    if args.sample is not None and (not args.scan or args.sample < 1):
        cli.error("--sample requires --scan and a positive count")
    if args.exclude_ambiguous and not args.scan:
        cli.error("--exclude-ambiguous is only valid for a new --scan")
    operation = next((name for name in ("scan", "render", "compare", "publish", "rollback", "status", "cleanup", "resume") if getattr(args, name)), "publish" if args.dry_run else "status")
    if operation not in {"scan", "status"} and not args.migration:
        cli.error("This operation requires --migration ID; resume never silently rescans")
    if args.apply and operation != "cleanup":
        cli.error("--apply is only for cleanup")
    # Validate overlap before constructing anything that writes SQLite or directories.
    if operation == "scan" or args.transparent_dir:
        try:
            (source_root if operation in {"scan","render","resume","compare","publish"} else protect_source)(args.transparent_dir, args.workspace)
        except (OSError, ValueError) as error:
            cli.error(str(error))
    migration = None
    try:
        migration = Migration(args.workspace, source_dir=args.transparent_dir)
        with migration.lock():
            mid = args.migration
            limit = args.limit or (25 if operation == "compare" else args.batch_size)
            if operation == "scan":
                mid = migration.scan(args.transparent_dir, args.sample, args.exclude_ambiguous)
                result = {"migration": mid, "summary": migration.export(mid)}
            elif operation in {"render", "resume"}:
                if args.dry_run:
                    raise ValueError("--render is already local-only; use --dry-run for publication previews")
                result = migration.render(mid, limit, args.failed_only)
                result["status"] = migration.export(mid)["statuses"]
            elif operation == "compare":
                from jost_migration_report import comparison_report
                result = comparison_report(migration, mid, limit)
            elif operation == "publish":
                result = migration.publish(mid, limit, args.batch_size, args.dry_run, args.confirm, args.reviewed)
                if not args.dry_run and os.getenv("JOST_MIGRATION_AUTO_CLEANUP", "true").lower() in {"true", "1", "yes"}:
                    migration.cleanup(mid, False, float(os.getenv("JOST_MIGRATION_RETENTION_DAYS", "3")))
            elif operation == "rollback":
                result = migration.rollback(mid, limit, args.batch_size, args.dry_run, args.confirm)
            elif operation == "cleanup":
                result = migration.cleanup(mid, not args.apply or args.dry_run, float(os.getenv("JOST_MIGRATION_RETENTION_DAYS", "3")))
            elif mid:
                result = migration.export(mid)
            else:
                result = [dict(row) for row in migration.db.execute("SELECT * FROM jost_runs ORDER BY created")]
            # Detailed per-person results stay in the durable JSON, not a huge terminal dump.
            if isinstance(result, dict) and "summary" in result:
                result["summary"] = {k: v for k, v in result["summary"].items() if k not in {"items", "destinations"}}
            elif isinstance(result, dict) and "items" in result:
                result = {k: v for k, v in result.items() if k not in {"items", "destinations"}}
            print(json.dumps(result, indent=2, ensure_ascii=True))
            if operation in {"render", "resume"} and any(result["status"].get(key, 0) for key in ("failed", "conflict")):
                return 1
        return 0
    except (OSError, ValueError, GitHubError) as error:
        print("[ERROR] " + str(error), file=sys.stderr)
        return 1
    finally:
        if migration:
            migration.close()


if __name__ == "__main__":
    raise SystemExit(main())
