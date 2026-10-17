"""Opt-in bounded overlay acceptance; generation never grants visual approval."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time
from PIL import Image, ImageChops

from .common import BulkError, fingerprint, sha256, reject_links
from .config import ROOT
from .e_validation import ResourceGuard, configuration, environment, save
from .overlays import CATALOG, generate
from .workers import WorkerLimits


def run(root, *, all_sources=False, workers=2):
    root = reject_links(root).resolve()
    config = configuration(root)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(CATALOG.read_text())
    assert catalog["counts"] == {"groups": 18, "operations": 36, "transforms": 4122, "unique_inputs": 2061}
    sources = () if all_sources else sorted({g["inputs"][0] for g in catalog["groups"]} | {"logos_genre/Experimental.png"})
    options = dict(config=config, sources=sources, limits=WorkerLimits(workers=workers,
                   total_worker_memory_bytes=workers * 512 * 1024 ** 2, max_jobs=5000))
    runs = {}
    for name in ("cold", "warm"):
        with ResourceGuard(root, seconds=1800, max_output=2 * 1024 ** 3) as guard:
            start = time.monotonic()
            result = generate(cancel=guard, **options)
            duration = time.monotonic() - start
        save(root / (name + "-result.json"), result)
        runs[name] = dict(result["execution"]["metrics"], total_seconds=duration, stop_reason=guard.reason)
        if result["status"] != "verified":
            raise BulkError("incomplete_overlay_acceptance", "Bounded overlay run incomplete; partial evidence retained")
        if name == "warm" and (runs[name]["executed"] or runs[name]["worker_starts"]):
            raise BulkError("overlay_cache", "Unchanged overlay run executed workers")
    ledger = []
    for job in result["manifest"]["jobs"]:
        output = config.output_dir / job["local_relative"]
        with Image.open(output) as image:
            image.load()
            assert image.format == "PNG" and image.mode == "RGBA"
            assert 0 < image.width <= job["parameters"]["box"][0] and 0 < image.height <= job["parameters"]["box"][1]
            ledger.append({"id": job["id"], "path": job["local_relative"], "sha256": sha256(output),
                           "dimensions": list(image.size), "alpha_extrema": list(image.getchannel("A").getextrema())})
    save(root / "output-ledger.json", ledger)
    accepted = json.loads((ROOT / "bulk/evidence/package-d/maintainer-visual-acceptance-20261017.json").read_text())
    original_artifact = ROOT.parent / "config/package-d/ci-review-39025655177"
    comparisons = []
    for d in accepted["decisions"]:
        if d["kind"] != "overlay":
            continue
        current = config.output_dir / d["artifact_image"].removeprefix("output/")
        old = original_artifact / d["artifact_image"]
        entry = {"variant_id": d["variant_id"], "accepted_ci_sha256": d["image_sha256"],
                 "current_sha256": sha256(current), "current_renderer": result["manifest"]["renderer"],
                 "approval_transferred": False}
        if old.is_file():
            assert sha256(old) == d["image_sha256"]
            with Image.open(old) as left, Image.open(current) as right:
                entry["same_decoded_pixels"] = left.size == right.size and ImageChops.difference(left.convert("RGBA"), right.convert("RGBA")).getbbox(alpha_only=False) is None
        comparisons.append(entry)
    summary = {"environment": environment(), "full_overlay_catalog": all_sources,
        "catalog_payload_sha256": catalog["sha256"], "catalog_counts": catalog["counts"],
        "jobs": len(ledger), "groups": len({j["parameters"]["group"] for j in result["manifest"]["jobs"]}) if all("group" in j["parameters"] for j in result["manifest"]["jobs"]) else len(catalog["groups"]),
        "runs": runs, "ledger_sha256": fingerprint(ledger), "missing": 0, "failed": 0,
        "package_d_scope_checks": comparisons, "new_visual_approvals": 0,
        "scope": "Automated transform/PNG/RGBA/cache verification only; Package D accepts exact CI images, not this entire catalog"}
    if all_sources and len(ledger) != 4122:
        raise BulkError("overlay_inventory", "Full overlay contract count differs")
    save(root / "overlay-summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("jobs", "groups", "missing", "failed", "new_visual_approvals")} |
        {"cold_seconds": runs["cold"]["total_seconds"], "warm_seconds": runs["warm"]["total_seconds"]}), flush=True)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--all", action="store_true", dest="all_sources")
    parser.add_argument("--workers", choices=[1, 2, 4], default=2, type=int)
    args = parser.parse_args(argv)
    run(args.root, all_sources=args.all_sources, workers=args.workers)


if __name__ == "__main__":
    main()
