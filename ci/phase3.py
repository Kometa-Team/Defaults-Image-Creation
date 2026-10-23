"""Required P3/M1 focused collection/execution proof, separate from legacy IDs."""

import argparse
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ci.validation import identity, read, write, require, unique, pytest_run, validate_execution

IDS = ROOT/"ci/phase3-test-ids.json"
SCHEMA = ROOT/"create_defaults/bulk/contracts/language_policy/schemas/foundations-v1.schema.json"
GOLDEN = ROOT/"create_defaults/phase3/tests/golden-v1.json"
OUT = ROOT/"config/phase3-ci"


def checksum(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def run():
    result = {**identity(), "kind": "phase3-foundations", "success": False,
              "ids_sha256": checksum(IDS), "schema_sha256": checksum(SCHEMA)}
    try:
        paths = ["create_defaults/phase3/tests"]
        collection = pytest_run(paths, OUT/"phase3-collection.json", collect=True)
        execution = pytest_run(paths, OUT/"phase3-execution.json")
        expected = unique(read(IDS), "focused expected IDs")
        require(unique(collection["nodes"], "focused original collection") == expected, "Focused collection changed")
        require(unique(execution["nodes"], "focused execution") == expected, "Focused execution differs")
        counts = validate_execution(execution)
        require(not counts.get("skipped"), "Focused security tests may not be skipped")
        from create_defaults.phase3.tests.samples import bundle
        golden = {doc.KIND: doc.sha256 for doc in bundle()}
        require(golden == read(GOLDEN), "Canonical cross-platform vectors differ")
        result.update(collection=collection, execution=execution, golden=golden, success=True)
    finally:
        write(OUT/"phase3-report.json", result)


def verify_reports(reports):
    """Called by the existing mandatory Validation acceptance check."""
    require(len(reports) == 2, "Missing or duplicate focused platform reports")
    current = identity()
    require({r["platform"] for r in reports} == {"Windows", "Linux"}, "Missing focused platform")
    expected = unique(read(IDS), "focused expected IDs")
    summary = {}
    for report in reports:
        require(all(report[k] == current[k] for k in ("head", "plan_sha256")), "Stale focused head/plan")
        require(report["kind"] == "phase3-foundations" and report["success"], "Focused group failed")
        require(report["ids_sha256"] == checksum(IDS) and report["schema_sha256"] == checksum(SCHEMA), "Focused selection/schema changed")
        require(unique(report["collection"]["nodes"], "focused collection") == expected, "Missing focused collection IDs")
        require(report["collection"]["exitstatus"] == 0, "Focused collection incomplete")
        require(unique(report["execution"]["nodes"], "focused execution") == expected, "Missing focused execution IDs")
        counts = validate_execution(report["execution"])
        require(not counts.get("skipped"), "Focused skip is not acceptance")
        require(report["golden"] == read(GOLDEN), "Windows/Linux canonical vectors differ")
        summary[report["platform"]] = {"collected_ids": sorted(expected), "executed_ids": sorted(report["execution"]["nodes"]),
            "counts": counts, "golden": report["golden"], "schema_sha256": report["schema_sha256"]}
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("action", choices=["run"])
    parser.parse_args()
    run()
