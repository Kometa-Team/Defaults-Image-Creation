"""Controlled Package E acceptance runs; local outputs only, no publication.

Expensive workloads require explicit CLI selection and enforce wall-time, free-disk,
output-size and sampled process-memory limits. Prior package evidence is read-only.
"""
import argparse
from collections import Counter
import cProfile
import json
import os
from pathlib import Path
import platform
import pstats
import re
import shutil
import subprocess
import threading
import time

from PIL import Image
import psutil

from .catalog import load_catalog
from .common import BulkError, atomic_bytes, canonical, fingerprint, sha256, reject_links
from .config import CATEGORIES, Config, ROOT
from .generation import generate
from .generators import GENERATORS
from .migration import reconcile
from .planner import Planner, renderer_identity, validate_manifest
from .preflight import preflight
from .state import Store
from .translations import Translations
from .workers import WorkerLimits

GIB = 1024 ** 3


def save(path, value):
    atomic_bytes(Path(path), canonical(value) + b"\n", replace=True)


def environment():
    process = psutil.Process()
    return {
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT.parent, text=True).strip(),
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT.parent, text=True).strip(),
        "platform": platform.platform(), "python": platform.python_version(),
        "renderer": renderer_identity(), "logical_cpus": os.cpu_count(),
        "memory_available": psutil.virtual_memory().available,
        "disk_free": shutil.disk_usage(ROOT.parent).free,
        "parent_rss": process.memory_info().rss,
        "source_files": {p.relative_to(ROOT).as_posix(): sha256(p) for p in sorted((ROOT / "bulk").glob("*.py"))},
    }


def configuration(root):
    root = reject_links(root).resolve()
    return Config(cache_dir=root / "cache", workspace_dir=root / "work", output_dir=root / "output")


class ResourceGuard:
    """Sampled acceptance-run limits; worker limits remain independently active."""
    def __init__(self, root, *, seconds=10800, min_free=8 * GIB, max_output=16 * GIB,
                 max_process_rss=4 * GIB):
        self.root, self.seconds = Path(root), seconds
        self.min_free, self.max_output, self.max_process_rss = min_free, max_output, max_process_rss
        self.started = time.monotonic()
        self.reason = None
        self.samples = []
        self.stop = threading.Event()
        self.thread = None

    def __enter__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.thread = threading.Thread(target=self._monitor, daemon=True)
        self.thread.start()
        return self

    def _sample(self):
        parent = psutil.Process()
        processes = [parent, *parent.children(recursive=True)]
        rss, cpu = 0, 0
        for process in processes:
            try:
                rss += process.memory_info().rss
                times = process.cpu_times()
                cpu += times.user + times.system
            except psutil.Error:
                pass
        size = sum(p.stat().st_size for p in (self.root / "output").rglob("*") if p.is_file()) if (self.root / "output").exists() else 0
        sample = {"elapsed_seconds": time.monotonic() - self.started, "rss_sum": rss,
                  "live_processes": len(processes), "cpu_seconds_live_processes": cpu,
                  "disk_free": shutil.disk_usage(self.root).free, "output_bytes": size}
        if sample["elapsed_seconds"] > self.seconds:
            self.reason = "wall_time_limit"
        elif sample["disk_free"] < self.min_free:
            self.reason = "free_disk_floor"
        elif size > self.max_output:
            self.reason = "output_byte_limit"
        elif rss > self.max_process_rss:
            self.reason = "sampled_process_memory_limit"
        elif (self.root / "STOP").exists():
            self.reason = "explicit_stop_file"
        self.samples.append(sample)
        # 3 hours / 10 seconds = 1080 bounded small samples.
        save(self.root / "resource-status.json", {"reason": self.reason, "latest": sample})
        return sample

    def _monitor(self):
        while not self.stop.is_set():
            try:
                sample = self._sample()
                if len(self.samples) % 3 == 1:
                    print("[RESOURCE] " + json.dumps(sample), flush=True)
            except (OSError, psutil.Error) as error:
                self.reason = "resource_monitor_failed:" + type(error).__name__
            self.stop.wait(10)

    def is_set(self):
        return self.reason is not None

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=15)


def baseline(root):
    config = configuration(root)
    translated = Translations({"en": ROOT / "fixtures/english/en.yml"})
    definitions = load_catalog(["all"])
    planner = Planner(config, generators=GENERATORS)
    expanded = planner.expand(definitions)[0]
    categories = []
    for category in CATEGORIES[:-1]:
        selected = tuple(item for item in expanded.values() if item.category == category)
        result = reconcile(category, selected, translated)
        categories.append(result)
        print("[RECONCILED] " + category + " " + str(result["active_jobs"]), flush=True)
    report, effective = preflight(definitions, translated, config=config,
        generators=GENERATORS, categories=["all"], languages=["en"], policy="audit")
    private = [v for v in report["variants"] if v["private"]]
    paths = [v["local_relative"] for v in report["variants"]]
    result = {"environment": environment(), "categories": categories,
        "jobs": len(report["variants"]), "published_contracts": len(report["variants"]) - len(private),
        "private_intermediates": [{"id": v["id"], "path": v["local_relative"], "remote": v["remote_relative"]} for v in private],
        "preflight_sha256": report["sha256"], "coverage": report["coverage"],
        "diagnostics": dict(Counter(d["code"] for v in report["variants"] for d in v["diagnostics"])),
        "duplicate_paths": len(paths) - len(set(paths)), "full_poster_renders": report["metrics"]["full_poster_renders"]}
    result["passed"] = (result["jobs"] == 9957 and result["published_contracts"] == 9955
        and len(private) == 2 and not report["coverage"].get("blocked")
        and all(c["contract_parity"] for c in categories) and result["duplicate_paths"] == 0
        and all(v["remote_relative"] is None for v in private))
    save(Path(root) / "baseline.json", result)
    if not result["passed"]:
        raise BulkError("acceptance_reconciliation", "Full catalog reconciliation/preflight did not pass")
    return result


def summarize(result, seconds):
    stages = [s["execution"]["metrics"] for s in result["stages"]]
    totals = {key: sum(s[key] for s in stages) for key in
        ("executed", "cache_hits", "dedup_reuses", "worker_starts", "worker_recycles", "read_bytes", "write_bytes", "retry_attempts", "failures")}
    for key in ("peak_worker_rss", "peak_workers_rss_sum", "peak_parent_rss", "max_inflight"):
        totals[key] = max((s[key] for s in stages), default=0)
    totals.update(status=result["status"], wall_seconds=seconds,
        actual_renders_per_second=totals["executed"] / seconds if seconds else 0,
        stage_metrics=stages, manifest_sha256=result.get("manifest", {}).get("sha256"),
        unique_outputs=len(result.get("manifest", {}).get("jobs", [])))
    return totals


def verify(result, config, *, decode=False):
    manifest = result["manifest"]
    validate_manifest(manifest)
    store = Store(config.cache_dir / "state.sqlite")
    with store.connection() as db:
        rows = {r["relative"]: dict(r) for r in db.execute(
            "SELECT c.relative,j.status,j.spec,j.fingerprint,j.receipt FROM output_claims c "
            "JOIN jobs j ON j.id=c.state_id WHERE c.root=?", (fingerprint(str(config.output_dir)),))}
    ledger = []
    for job in manifest["jobs"]:
        path = config.output_dir / job["local_relative"]
        row = rows[job["local_relative"]]
        receipt = json.loads(row["receipt"])
        assert row["status"] == "verified" and fingerprint(json.loads(row["spec"])) == row["fingerprint"]
        assert receipt["receipt_sha256"] == fingerprint({k: v for k, v in receipt.items() if k != "receipt_sha256"})
        assert receipt["logical_id"] == job["id"] and receipt["render_fingerprint"] == job["render_fingerprint"]
        assert sha256(path) == receipt["sha256"] and path.stat().st_size == receipt["size"]
        with Image.open(path) as image:
            assert image.format == "JPEG" and image.mode == "RGB" and image.size == (2000, 3000)
            if decode:
                image.load()
            else:
                image.verify()
        ledger.append({"id": job["id"], "path": job["local_relative"], "sha256": receipt["sha256"],
            "bytes": receipt["size"], "render_fingerprint": job["render_fingerprint"],
            "private": job["remote_relative"] is None})
    result = {"outputs": len(ledger), "private": sum(v["private"] for v in ledger),
        "publishable": sum(not v["private"] for v in ledger), "missing": 0, "failed": 0,
        "duplicates": len(ledger) - len({v["path"] for v in ledger}),
        "bytes": sum(v["bytes"] for v in ledger), "ledger_sha256": fingerprint(ledger),
        "decode": "full" if decode else "final headers plus exact hashes; full decoding enforced on worker promotion"}
    save(config.cache_dir.parent / "verified-output-ledger.json", ledger)
    save(config.cache_dir.parent / "output-verification.json", result)
    return result


def workload(root, *, categories, workers, full=False, profile=False, warm_only=False, record_prefix=""):
    if record_prefix and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", record_prefix):
        raise BulkError("invalid_record_prefix", "Record prefix must be a short lowercase label, not a path")
    root = reject_links(root).resolve()
    config = configuration(root)
    definitions = load_catalog(categories)
    translated = Translations({"en": ROOT / "fixtures/english/en.yml"})
    config.output_dir.mkdir(parents=True, exist_ok=True)
    limits = WorkerLimits(workers=workers, total_worker_memory_bytes=workers * 512 * 1024 ** 2,
        recycle_after=200, max_jobs=15000)
    runs = {}
    for name in (("warm",) if warm_only else ("cold", "warm")):
        record_name = (record_prefix + "-" if record_prefix else "") + name
        profiler = cProfile.Profile() if profile and name == "warm" else None
        with ResourceGuard(root) as guard:
            started = time.monotonic()
            if profiler:
                profiler.enable()
            result = generate(definitions, translated, config=config, generators=GENERATORS,
                categories=categories, limits=limits, cancel=guard, policy="strict")
            if profiler:
                profiler.disable()
            seconds = time.monotonic() - started
        save(root / (record_name + "-result.json"), result)
        summary = summarize(result, seconds)
        summary["resource_samples"] = guard.samples
        summary["stop_reason"] = guard.reason
        runs[name] = summary
        save(root / (record_name + "-summary.json"), summary)
        if profiler:
            profiler.dump_stats(str(root / (record_name + "-profile.pstats")))
            with (root / (record_name + "-profile.txt")).open("w", encoding="utf-8") as stream:
                pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(45)
        print("[WORKLOAD] " + json.dumps({k: v for k, v in summary.items() if k not in ("stage_metrics", "resource_samples")}), flush=True)
        if result["status"] != "verified":
            raise BulkError("incomplete_acceptance_run", "Partial evidence retained; full success is not claimed")
        if name == "warm" and (summary["executed"] or summary["worker_starts"]):
            raise BulkError("acceptance_cache", "Unchanged run rendered outputs or started workers")
        if full and summary["unique_outputs"] != 9957:
            raise BulkError("acceptance_count", "Full English output count is incomplete")
        verification = verify(result, config)
        if full and (verification["publishable"] != 9955 or verification["private"] != 2):
            raise BulkError("acceptance_count", "Full English destination/private counts differ")
    value = {"environment": environment(), "categories": categories, "workers": workers,
        "runs": runs, "verification": verification, "production_publication": False}
    save(root / ((record_prefix + "-" if record_prefix else "") + "workload.json"), value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["baseline", "workload"])
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--category", nargs="+", default=["all"])
    parser.add_argument("--workers", type=int, choices=[1, 2, 4], default=2)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--warm-only", action="store_true")
    parser.add_argument("--record-prefix", default="")
    args = parser.parse_args(argv)
    if args.operation == "baseline":
        baseline(args.root)
    else:
        if args.full and args.category != ["all"]:
            parser.error("--full requires --category all")
        workload(args.root, categories=args.category, workers=args.workers, full=args.full,
                 profile=args.profile, warm_only=args.warm_only, record_prefix=args.record_prefix)


if __name__ == "__main__":
    main()

