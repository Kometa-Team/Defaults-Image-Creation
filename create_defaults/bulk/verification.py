"""Export pinned canonical category plans and compact Package C gate evidence."""

import argparse
import html
import json
import os
from pathlib import Path

from .catalog import CATALOG, load_catalog
from .common import BulkError, atomic_bytes, canonical, fingerprint, sha256
from .config import CATEGORIES, Config, ROOT
from .generators import GENERATORS
from .migration import reconcile
from .planner import Planner
from .translations import Translations


def portable(value):
    if isinstance(value, str):
        return value.replace(str(ROOT.parent), "{REPOSITORY}").replace(ROOT.parent.as_posix(), "{REPOSITORY}")
    if isinstance(value, dict):
        return {key: portable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [portable(item) for item in value]
    return value


def export(evidence_root, benchmark_root, output, *, write_summaries=False):
    translations = Translations({"en": ROOT / "fixtures/english/en.yml"})
    records, links = [], []
    for category in CATEGORIES[:-1]:
        definitions = load_catalog([category])
        artifacts = {}
        config = Config()
        benchmark = None
        if category in {"Year", "Decade"}:
            root = benchmark_root / category.lower()
            config = Config(cache_dir=root / "cache", workspace_dir=root / "work", output_dir=root / "output")
            previous = json.loads((root / "warm.json").read_text())
            for stage in previous["stages"]:
                for job in stage["manifest"]["jobs"]:
                    checksum = sha256(config.output_dir / job["local_relative"])
                    if checksum != stage["execution"]["jobs"][job["id"]]["sha256"]:
                        raise BulkError("corrupt_artifact", "Benchmark parent/output changed after verification")
                    artifacts[job["id"]] = checksum
            benchmark = json.loads((benchmark_root / (category.lower() + "-summary.json")).read_text())
        elif category == "Based":
            benchmark = json.loads((benchmark_root / "based-summary.json").read_text())
        planner = Planner(config, generators=GENERATORS, scope="Package C complete English category plan; no publication or multilingual approval")
        expanded = tuple(planner.expand(definitions)[0].values())
        parity = reconcile(category, expanded, translations)
        if not parity["contract_parity"]:
            raise BulkError("migration_discrepancy", json.dumps(parity))
        manifest = planner.plan(definitions, translations, categories=[category], dependency_artifacts=artifacts)
        atomic_bytes(output / (category.lower() + "-manifest.json"), canonical(manifest) + b"\n")
        retained = json.loads((CATALOG / "audit" / (category.lower() + "-render.json")).read_text())
        render_root = ROOT.parent / retained["evidence_directory"] if retained.get("evidence_directory") else evidence_root / category.lower()
        render = json.loads((render_root / "evidence.json").read_text())
        if render["status"] != "automated_sample_passed" or not all(item["byte_identical"] for item in render["sample_comparisons"]):
            raise BulkError("unverified_sample", "Category sample evidence has not passed")
        record = dict(parity, canonical_manifest_sha256=manifest["sha256"], yaml_sha256=sha256(CATALOG / (category.lower() + ".yml")),
                      profile_sha256=sha256(CATALOG / "profiles.yml"), jobs=len(manifest["jobs"]),
                      generated_input_jobs=sum(bool(job["dependencies"]) for job in manifest["jobs"]),
                      sample_comparisons=portable(render["sample_comparisons"]),
                      cold_metrics=render["cold_metrics"], warm_metrics=render["warm_metrics"],
                      incremental_metrics=render["incremental_metrics"], resume_metrics=render["resume_metrics"],
                      benchmark=benchmark, automated_gate="passed", maintainer_gate="awaiting_review",
                      limitations=render["limitations"])
        records.append(record)
        if write_summaries:
            atomic_bytes(CATALOG / "audit" / (category.lower() + "-parity.json"), json.dumps(parity, indent=2).encode() + b"\n", replace=True)
            atomic_bytes(CATALOG / "audit" / (category.lower() + "-render.json"), json.dumps(portable(render), indent=2).encode() + b"\n", replace=True)
        href = Path(os.path.relpath(render_root / "index.html", evidence_root)).as_posix()
        links.append('<li><a href="' + html.escape(href) + '">' + html.escape(category) + '</a>: ' + str(len(manifest["jobs"])) + ' planned; ' + str(len(render["sample_comparisons"])) + ' byte-identical sample comparisons</li>')
        print(category + ": " + str(len(manifest["jobs"])) + " canonical jobs; zero discrepancies", flush=True)
    result = {"schema_version": 1, "effective_jobs": sum(item["jobs"] for item in records), "categories": records,
              "scope": "Package C automated English migration evidence; maintainer acceptance pending. D/E and production cutover not authorized."}
    result["sha256"] = fingerprint(result)
    atomic_bytes(output / "package-c-evidence.json", canonical(result) + b"\n")
    if write_summaries:
        atomic_bytes(CATALOG / "audit/package-c-evidence.json", json.dumps(result, indent=2).encode() + b"\n", replace=True)
    page = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Package C comparisons</title><style>body{font:16px Arial;max-width:1000px;margin:32px;color:#222}li{margin:10px 0}</style><h1>Package C Poster Comparisons</h1><p>Fresh persistent-worker samples alongside the approved Pillow API reference. Published artwork is not compared here. Human approval is not inferred.</p><ul>' + ''.join(links) + '</ul>'
    atomic_bytes(evidence_root / "index.html", page.encode())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--write-summaries", action="store_true")
    args = parser.parse_args(argv)
    result = export(args.evidence_root.resolve(), args.benchmark_root.resolve(), args.output.resolve(), write_summaries=args.write_summaries)
    print("Total canonical English jobs: " + str(result["effective_jobs"]))


if __name__ == "__main__":
    main()
