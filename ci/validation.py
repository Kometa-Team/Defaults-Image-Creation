"""CI-only bounded validation and node-ID reconciliation; no production hooks."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PLAN_PATH = ROOT / "ci/validation-plan.json"
BASELINE_PATH = ROOT / "ci/original-test-ids.json"
OUTPUT = ROOT / "config/ci-validation"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity():
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(head == os.environ.get("EXPECTED_HEAD", head), "Checkout differs from exact PR head")
    return {"head": head, "platform": platform.system(),
            "plan_sha256": hashlib.sha256(PLAN_PATH.read_bytes().replace(b"\r\n", b"\n")).hexdigest()}


def unique(values, label):
    duplicates = [n for n, count in Counter(values).items() if count != 1]
    require(not duplicates, f"Duplicate {label}: {duplicates}")
    return set(values)


class PytestEvidence:
    def __init__(self, path):
        self.path = path
        self.start = perf_counter()
        self.data = {"nodes": [], "fixtures": {}, "reports": []}

    def pytest_collection_finish(self, session):
        self.data["collection_seconds"] = perf_counter() - self.start
        self.data["nodes"] = [item.nodeid for item in session.items]
        self.data["fixtures"] = {item.nodeid: item.fixturenames for item in session.items
                                 if "verified_historical_discovery" in item.fixturenames}

    def pytest_runtest_logreport(self, report):
        self.data["reports"].append({"nodeid": report.nodeid, "when": report.when,
            "outcome": report.outcome, "seconds": report.duration,
            "wasxfail": hasattr(report, "wasxfail"),
            "skip_reason": str(report.longrepr) if report.skipped else None})

    def pytest_sessionfinish(self, session, exitstatus):
        self.data.update(exitstatus=int(exitstatus), seconds=perf_counter()-self.start)
        write(self.path, self.data)


def pytest_run(paths, destination, collect=False):
    # A separate process keeps import/fixture state and worker RSS independent.
    argv = [sys.executable, str(Path(__file__).resolve()), "pytest", "--report", str(destination)]
    if collect:
        argv.append("--collect-only")
    argv.extend(["--", *paths])
    subprocess.run(argv, cwd=ROOT, check=True)
    return read(destination)


def unit_suite(root):
    return unittest.TestLoader().discover(str(ROOT/root))


def unit_ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from unit_ids(item)
        else:
            yield item.id()


class UnitEvidenceResult(unittest.TextTestResult):
    def startTest(self, test):
        if not hasattr(self, "started_ids"):
            self.started_ids, self.finished_ids = [], []
        self.started_ids.append(test.id())
        super().startTest(test)

    def stopTest(self, test):
        self.finished_ids.append(test.id())
        super().stopTest(test)


def require_jobs(needs):
    require(set(needs) == {"collection", "validation", "phase3"} and all(v["result"] == "success" for v in needs.values()),
            "Failed, cancelled, skipped or missing required job")


def collect(plan):
    result = {**identity(), "kind": "collection", "original": [], "units": {}}
    for index, paths in enumerate(plan["original_pytest_commands"]):
        data = pytest_run(paths, OUTPUT/f"collection-{index}.json", collect=True)
        result["original"].extend(data["nodes"])
        for node in data["fixtures"]:
            require(node.split("::")[0] in plan["pytest_groups"]["historical"],
                    f"Historical fixture would be duplicated outside shared job: {node}")
    baseline = read(BASELINE_PATH)
    require(unique(result["original"], "original IDs") == set(baseline["pytest"]),
            "Original test collection changed; review the explicit baseline, never silently drop IDs")
    for root in plan["unittest_roots"]:
        result["units"][root] = sorted(unit_ids(unit_suite(root)))
    require(result["units"] == baseline["unittest"], "Original unittest IDs changed")
    write(OUTPUT/"collection.json", result)


def run_group(plan, group, base):
    started = perf_counter()
    result = {**identity(), "kind": "group", "group": group, "commands": [], "success": False}
    try:
        if group in plan["pytest_groups"]:
            result["pytest"] = pytest_run(plan["pytest_groups"][group], OUTPUT/f"pytest-{group}.json")
        for argv in plan["commands"].get(group, []):
            actual = [base if a == "{base}" else a for a in argv]
            command_start = perf_counter()
            completed = subprocess.run([sys.executable if a == "{python}" else a for a in actual], cwd=ROOT)
            result["commands"].append({"argv": actual, "exitstatus": completed.returncode,
                                       "seconds": perf_counter()-command_start})
            require(completed.returncode == 0, f"Required command failed: {actual}")
        if group == "core":
            result["unit_execution"] = {root: read(OUTPUT/("unit-"+root.replace("/", "-")+".json"))
                                        for root in plan["unittest_roots"]}
        result["success"] = True
    finally:
        result["seconds"] = perf_counter()-started
        write(OUTPUT/f"group-{group}.json", result)


def validate_execution(data):
    nodes = unique(data["nodes"], "executed collection")
    require(data["exitstatus"] == 0, "pytest failed or did not finish")
    by_node = {n: {} for n in nodes}
    for report in data["reports"]:
        require(report["nodeid"] in nodes, "Unexpected executed node")
        phases = by_node[report["nodeid"]]
        require(report["when"] not in phases, "Duplicate test execution")
        require(not report["wasxfail"], "xfail is not an accepted coverage substitute")
        phases[report["when"]] = report
    counts = Counter()
    for node, phases in by_node.items():
        require("setup" in phases and "teardown" in phases, f"Incomplete execution: {node}")
        require(all(r["outcome"] in ("passed", "skipped") for r in phases.values()), f"Failed test: {node}")
        skipped = [r for r in phases.values() if r["outcome"] == "skipped"]
        if skipped:
            require(all(r["skip_reason"] for r in skipped), "Undocumented skip")
            counts["skipped"] += 1
        else:
            require(phases.get("call", {}).get("outcome") == "passed", f"Missing call: {node}")
            counts["passed"] += 1
    return dict(counts)


def reconcile(plan, reports, base):
    """Strictly require every platform/group and exact IDs, not aggregate counts."""
    expected_identity = identity()
    expected_groups = set(plan["pytest_groups"]) | set(plan["commands"])
    require(len(reports) == 2*(1+len(expected_groups)), "Missing or extra required report")
    summary = {**expected_identity, "platforms": {}}
    for system in ("Linux", "Windows"):
        selected = [r for r in reports if r["platform"] == system]
        for report in selected:
            require(all(report[k] == expected_identity[k] for k in ("head", "plan_sha256")), "Stale head/plan")
        collections = [r for r in selected if r["kind"] == "collection"]
        require(len(collections) == 1, "Missing/duplicate original collection")
        collected = collections[0]
        baseline = read(BASELINE_PATH)
        require(unique(collected["original"], "original") == set(baseline["pytest"]), "Original baseline differs")
        require(collected["units"] == baseline["unittest"], "Unittest collection differs")
        groups = {r["group"]: r for r in selected if r["kind"] == "group"}
        require(set(groups) == expected_groups and len(selected) == 1+len(groups), "Missing/duplicate required group")
        executed = []
        group_summary = {}
        for name, report in groups.items():
            require(report["success"], f"Required group failed: {system}/{name}")
            commands = [[base if a == "{base}" else a for a in cmd] for cmd in plan["commands"].get(name, [])]
            require([c["argv"] for c in report["commands"]] == commands, "Required non-pytest commands changed/missing")
            require(all(c["exitstatus"] == 0 for c in report["commands"]), "Required command failed")
            details = {"seconds": report["seconds"], "commands": report["commands"]}
            if name == "core":
                units = report["unit_execution"]
                require(set(units) == set(baseline["unittest"]), "Missing unittest execution")
                for root, data in units.items():
                    expected = set(baseline["unittest"][root])
                    require(unique(data["started_ids"], "unit starts") == expected and
                            unique(data["finished_ids"], "unit completions") == expected, "Incomplete unittest IDs")
                    require(data["success"] and data["failed"] == data["errors"] == data["expected_failures"] == 0,
                            "Unittest failure or xfail")
                details["unittest"] = units
            if name in plan["pytest_groups"]:
                data = report["pytest"]
                require({n.split("::")[0] for n in data["nodes"]} == set(plan["pytest_groups"][name]), "Group selection differs")
                details.update(validate_execution(data))
                executed.extend(data["nodes"])
            group_summary[name] = details
        require(unique(executed, "partition IDs") == set(collected["original"]), "Missing/extra partition node IDs")
        summary["platforms"][system] = {"original_nodeids": sorted(collected["original"]),
            "refactored_nodeids": sorted(executed), "missing": [], "extra": [], "duplicates": [],
            "groups": group_summary, "unittest_ids": collected["units"]}
    return summary


def legacy_reports(directory):
    return [read(p) for p in directory.rglob("*.json")
            if p.name == "collection.json" or p.name.startswith("group-")]


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("action", choices=["collect", "run", "verify", "pytest", "unit"])
    parser.add_argument("--group")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--directory", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()
    os.chdir(ROOT)
    plan = read(PLAN_PATH)
    if args.action == "pytest":
        import pytest
        options = [*args.paths, "--rootdir", str(ROOT), "-q", "-rs", "-p", "no:cacheprovider", "--durations=20"]
        if args.collect_only:
            options.append("--collect-only")
        return int(pytest.main(options, plugins=[PytestEvidence(args.report)]))
    if args.action == "unit":
        root = args.paths[0]
        suite = unit_suite(root)
        expected = read(BASELINE_PATH)["unittest"][root]
        require(sorted(unit_ids(suite)) == expected, "Unittest selection changed")
        result = unittest.TextTestRunner(verbosity=2, resultclass=UnitEvidenceResult).run(suite)
        write(OUTPUT/("unit-"+root.replace("/", "-")+".json"), {
            "started_ids": result.started_ids, "finished_ids": result.finished_ids,
            "success": result.wasSuccessful(), "tests_run": result.testsRun,
            "failed": len(result.failures), "errors": len(result.errors),
            "expected_failures": len(result.expectedFailures),
            "skipped": [(test.id(), reason) for test, reason in result.skipped]})
        require(result.testsRun == len(expected) and result.wasSuccessful(), "Unittest execution incomplete/failed")
        return 0
    if args.action == "collect":
        collect(plan)
    elif args.action == "run":
        require(args.group in set(plan["pytest_groups"]) | set(plan["commands"]), "Unknown group")
        run_group(plan, args.group, args.base)
    else:
        needs = json.loads(os.environ["REQUIRED_JOB_RESULTS"])
        require_jobs(needs)
        reports = legacy_reports(args.directory)
        summary = reconcile(plan, reports, args.base)
        from ci.phase3 import verify_reports
        summary["phase3"] = verify_reports([read(p) for p in args.directory.rglob("phase3-report.json")])
        write(OUTPUT/"coverage-equivalence.json", summary)
        print("All Windows/Linux groups passed; exact original/refactored node-ID sets are equal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
