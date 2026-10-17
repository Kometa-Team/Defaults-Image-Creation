"""Representative real-workload measurements, not Package E production acceptance."""

import argparse
import json
from pathlib import Path
import time

from .catalog import load_catalog
from .common import BulkError, atomic_bytes, canonical
from .config import Config, ROOT
from .generation import generate
from .generators import GENERATORS
from .translations import Translations
from .workers import WorkerLimits


def measure(category, root, workers):
    definitions = load_catalog([category])
    translations = Translations({"en": ROOT / "fixtures/english/en.yml"})
    config = Config(cache_dir=root / "cache", workspace_dir=root / "work", output_dir=root / "output")
    options = dict(config=config, limits=WorkerLimits(workers=workers, total_worker_memory_bytes=workers * 512 * 1024 * 1024),
                   generators=GENERATORS, categories=[category])
    runs = {}
    for name in ("cold", "warm"):
        started = time.monotonic()
        result = generate(definitions, translations, **options)
        duration = time.monotonic() - started
        if result["status"] != "verified":
            raise BulkError("benchmark_failed", "Real workload did not complete; do not claim a successful benchmark")
        atomic_bytes(root / (name + ".json"), canonical(result) + b"\n")
        metrics = [stage["execution"]["metrics"] for stage in result["stages"]]
        total = {key: sum(item[key] for item in metrics) for key in ("executed", "cache_hits", "dedup_reuses", "worker_starts", "read_bytes", "write_bytes")}
        for key in ("peak_worker_rss", "peak_workers_rss_sum", "peak_parent_rss", "max_inflight"):
            total[key] = max(item[key] for item in metrics)
        total["worker_pids"] = sorted({pid for item in metrics for pid in item["worker_pids"]})
        total["unique_outputs"] = len({job["local_relative"] for stage in result["stages"] for job in stage["manifest"]["jobs"]})
        total["failures"] = sum(entry["status"] not in {"rendered", "cache_reuse", "dedup_reuse"} for stage in result["stages"] for entry in stage["execution"]["jobs"].values())
        total["wall_seconds"] = duration
        total["rendered_per_second"] = total["executed"] / duration
        total["verified_outputs_per_second"] = total["unique_outputs"] / duration
        total["stage_metrics"] = metrics
        runs[name] = total
    if runs["warm"]["executed"] or runs["warm"]["worker_starts"]:
        raise BulkError("cache_failed", "Warm workload rendered or launched a worker")
    return {"category": category, "workers_configured": workers, "runs": runs,
            "scope": "Package C representative real JPEG workloads; no full production or legacy speedup claim"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--category", nargs="+", default=["Based", "Decade", "Year"])
    args = parser.parse_args(argv)
    for category in args.category:
        result = measure(category, args.root.resolve() / category.lower(), args.workers)
        atomic_bytes(args.root / (category.lower() + "-summary.json"), canonical(result) + b"\n")
        print(json.dumps({"category": category, "cold": {key: result["runs"]["cold"][key] for key in ("executed", "wall_seconds", "worker_starts")},
                          "warm": {key: result["runs"]["warm"][key] for key in ("executed", "wall_seconds", "worker_starts")}}), flush=True)


if __name__ == "__main__":
    main()
