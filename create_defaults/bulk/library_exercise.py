"""Benchmark approved artifacts against a synthetic, isolated offline baseline."""
import argparse
from pathlib import Path
import shutil
import subprocess
import time

from .common import BulkError, confined, sha256
from .library_publication import batch_plan
from .library_sources import check_seal, load_json, save, sealed
from .library_transport import git, run


def benchmark(manifest, inventory, root):
    check_seal(manifest); check_seal(inventory)
    if not manifest["members"]:
        raise BulkError("empty_exercise", "No approved artifacts available for transport benchmark")
    if manifest["inventory_sha256"] != inventory["sha256"]:
        raise BulkError("stale_inventory", "Benchmark inventory differs from approved manifest")
    root = Path(root).resolve()
    if root.exists():
        raise BulkError("existing_exercise", "Retain prior exercises; choose a fresh benchmark root")
    base = root / "synthetic-baseline"
    base.mkdir(parents=True)
    subprocess.run(["git", "init", str(base)], check=True, capture_output=True)
    git(base, "config", "user.name", "Offline library benchmark")
    git(base, "config", "user.email", "offline-library@invalid.local")
    git(base, "config", "core.autocrlf", "false")
    rows = {r["destination"]: r for r in inventory["rows"]}
    for member in manifest["members"]:
        row = rows[member["destination"]]
        if member["previous_sha256"]:
            if sha256(row["published_path"]) != member["previous_sha256"]:
                raise BulkError("baseline_hash", "Inventoried baseline bytes changed")
            target = confined(base, member["destination"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(row["published_path"], target)
    (base / "OFFLINE-EXERCISE.txt").write_text("Synthetic baseline for approved-artifact transport tests only.\n", encoding="utf-8")
    git(base, "add", "--all")
    git(base, "commit", "-m", "Synthetic offline baseline; production untouched")
    baseline = git(base, "rev-parse", "HEAD")
    exercise_manifest = sealed({k: v for k, v in manifest.items() if k not in {"sha256", "baseline"}} | {
        "baseline": {"head": baseline}, "rehearsal_of_manifest_sha256": manifest["sha256"],
        "production_baseline": manifest["baseline"]})
    plan = batch_plan(exercise_manifest, max_files=16, max_bytes=1024 * 1024)
    save(root / "rehearsal-manifest.json", exercise_manifest)
    save(root / "batch-plan.json", plan)
    events = []
    start = time.monotonic()
    work = root / "transport"
    for failure in ("after_commit", "after_push"):
        try:
            run(plan, work, base, fail_at=failure)
        except BulkError as error:
            if error.code != "injected_interruption":
                raise
            events.append({"injected": failure, "observed": str(error)})
    result = run(plan, work, base)
    repeated = run(plan, work, base)
    if repeated["commits"] != result["commits"]:
        raise BulkError("resume_identity", "Unchanged resume created extra commits")
    git(work / "remote.git", "repack", "-a", "-d")
    pack_bytes = sum(p.stat().st_size for p in (work / "remote.git/objects/pack").glob("*.pack"))
    report = sealed({"approved_production_manifest_sha256": manifest["sha256"],
        "artifact_count": len(manifest["members"]), "artifact_bytes": sum(m["size"] for m in manifest["members"]),
        "production_baseline": manifest["baseline"], "synthetic_baseline": baseline,
        "complete": result["complete"], "verified_batches": result["verified_batches"],
        "interruption_exercises": events, "idempotent_resume": True,
        "network_writes": 0, "pack_bytes": pack_bytes, "seconds": time.monotonic() - start,
        "limitation": "Local filesystem transport measurement; not evidence of GitHub network throughput or server limits"})
    save(root / "benchmark.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    import json
    print(json.dumps(benchmark(load_json(args.manifest), load_json(args.inventory), args.root), indent=2))


if __name__ == "__main__":
    main()
