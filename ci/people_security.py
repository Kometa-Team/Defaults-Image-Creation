"""Independent mandatory People security/recovery proof; original CI stays frozen."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ci.validation import identity, read, write, require, unique, pytest_run, validate_execution
from ci.phase4 import checksum

IDS = ROOT / "ci/people-security-test-ids.json"
OUT = ROOT / "config/ci-validation/people-security"
GROUPS = {"diagnostics", "recovery", "compatibility"}
ORIGINAL_JOBS = {"collection", "validation", "phase3", "phase4"}
REQUIRED_JOBS = ORIGINAL_JOBS | {"people_security"}


def require_jobs(needs):
    require(set(needs) == REQUIRED_JOBS and all(type(v) is dict and v.get("result") == "success" for v in needs.values()),
            "Missing, failed, cancelled or skipped required security/legacy job")
    # Keep the original independently tested gate, without pretending a new
    # namespace is part of its historical four-job contract.
    from ci.validation import require_jobs as original
    original({key: needs[key] for key in ORIGINAL_JOBS})


def selections():
    groups = read(IDS)
    require(set(groups) == GROUPS, "Changed mandatory People groups")
    seen = set()
    for name, ids in groups.items():
        selected = unique(ids, name)
        require(selected and not seen & selected, "Missing or duplicate People security selection")
        require(all(n.startswith("create_people_posters/tests/test_") for n in selected), "Unexpected security selection")
        seen |= selected
    original = {n for n in read(ROOT / "ci/original-test-ids.json")["pytest"] if n.startswith("create_people_posters/tests/")}
    require(not original & seen, "Original People IDs must remain in their existing independent group")
    return groups, original


def validate_report(report, current, groups):
    require(report.get("kind") == "people-security-execution" and report.get("success") is True, "Failed security proof")
    require(all(report.get(k) == current[k] for k in ("head", "plan_sha256")), "Stale security head/plan")
    require(report.get("ids_sha256") == checksum(IDS), "Changed security IDs")
    group = report.get("group")
    require(group in groups, "Unexpected security group")
    expected = set(groups[group])
    for key in ("collection", "execution"):
        require(report[key]["exitstatus"] == 0 and unique(report[key]["nodes"], key) == expected, "Missing/substituted security IDs")
    counts = validate_execution(report["execution"])
    # Mandatory leak/recovery/gate controls may never be skipped. Other existing
    # platform-specific tests retain their original visible reasons.
    for phase in report["execution"]["reports"]:
        if any(part in phase["nodeid"] for part in ("test_people_security", "test_people_http_security", "test_people_recovery_security", "test_people_security_gate")):
            require(phase["outcome"] != "skipped", "Security skip cannot satisfy acceptance")
    return counts


def run(group):
    groups, original = selections()
    require(group in groups, "Unknown People security group")
    result = dict(**identity(), kind="people-security-execution", group=group, success=False, ids_sha256=checksum(IDS))
    folder = OUT / group
    try:
        from ci.people_security_maintenance import verify
        verify()
        # One cheap whole-People collection proves every existing/new test has
        # exactly one mandatory executor. Rendering/model fixtures never run here.
        complete = pytest_run(["create_people_posters/tests"], folder / "namespace.json", collect=True)
        expected = original | set().union(*map(set, groups.values()))
        require(complete["exitstatus"] == 0 and unique(complete["nodes"], "People namespace") == expected,
                "Uncovered or substituted People test")
        response = folder / "selected.txt"
        response.parent.mkdir(parents=True, exist_ok=True)
        response.write_text("\n".join(groups[group]) + "\n", encoding="utf8", newline="\n")
        collection = pytest_run(["@" + str(response)], folder / "people-collection.json", collect=True)
        execution = pytest_run(["@" + str(response)], folder / "execution.json")
        result.update(collection=collection, execution=execution, namespace=complete, success=True)
        validate_report(result, identity(), groups)
    finally:
        write(folder / "people-security-report.json", result)


def verify_reports(reports):
    groups, original = selections()
    require(len(reports) == 6 and {(r.get("platform"), r.get("group")) for r in reports}
            == {(p, g) for p in ("Windows", "Linux") for g in GROUPS}, "Missing/duplicate People platform/group")
    current = identity()
    expected = original | set().union(*map(set, groups.values()))
    result = {}
    for report in reports:
        counts = validate_report(report, current, groups)
        require(report["namespace"]["exitstatus"] == 0 and unique(report["namespace"]["nodes"], "People namespace") == expected,
                "Incomplete People namespace proof")
        result.setdefault(report["platform"], {})[report["group"]] = {
            "counts": counts, "seconds": report["execution"]["seconds"], "executed_ids": report["execution"]["nodes"]}
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("action", choices=["run"])
    parser.add_argument("--group", required=True, choices=sorted(GROUPS))
    args = parser.parse_args()
    run(args.group)
