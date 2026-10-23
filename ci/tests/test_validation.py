"""Negative controls for the CI-only acceptance gate."""

from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from ci import validation as v


class GateTests(unittest.TestCase):
    def setUp(self):
        self.identity = {"head": "exact-head", "platform": "Linux", "plan_sha256": "exact-plan"}
        self.plan = {"pytest_groups": {"tests": ["a.py"]}, "commands": {"core": [["compile"]]}}
        self.baseline = {"pytest": ["a.py::test_original"], "unittest": {"unit": ["original.unit"]}}
        self.data = {"nodes": self.baseline["pytest"], "exitstatus": 0, "reports": [
            {"nodeid": "a.py::test_original", "when": phase, "outcome": "passed", "seconds": 0,
             "wasxfail": False, "skip_reason": None} for phase in ("setup", "call", "teardown")]}
        self.reports = []
        for system in ("Linux", "Windows"):
            context = {**self.identity, "platform": system}
            self.reports.extend([
                {**context, "kind": "collection", "original": self.baseline["pytest"], "units": self.baseline["unittest"]},
                {**context, "kind": "group", "group": "tests", "success": True,
                 "pytest": deepcopy(self.data), "commands": [], "seconds": 1},
                {**context, "kind": "group", "group": "core", "success": True,
                 "unit_execution": {"unit": {"started_ids": ["original.unit"], "finished_ids": ["original.unit"],
                    "success": True, "failed": 0, "errors": 0, "expected_failures": 0}},
                 "commands": [{"argv": ["compile"], "exitstatus": 0}], "seconds": 1},
            ])

    def reconcile(self):
        with patch.object(v, "identity", return_value=self.identity), patch.object(v, "read", return_value=self.baseline):
            return v.reconcile(self.plan, self.reports, "base")

    def test_complete_exact_head_evidence_is_accepted(self):
        self.assertEqual(set(self.reconcile()["platforms"]), {"Linux", "Windows"})

    def test_missing_cancelled_failed_and_duplicate_groups_fail(self):
        for mode in ("missing", "failed", "duplicate"):
            with self.subTest(mode=mode):
                original = deepcopy(self.reports)
                if mode == "missing": self.reports.pop()
                elif mode == "failed": self.reports[1]["success"] = False
                else: self.reports[-1] = deepcopy(self.reports[-2])
                with self.assertRaises(ValueError): self.reconcile()
                self.reports = original

    def test_stale_head_and_changed_plan_fail(self):
        for key in ("head", "plan_sha256"):
            with self.subTest(key=key):
                original = self.reports[1][key]
                self.reports[1][key] = "stale"
                with self.assertRaises(ValueError): self.reconcile()
                self.reports[1][key] = original

    def test_cancelled_failed_skipped_missing_matrix_prevents_acceptance(self):
        v.require_jobs({"validation": {"result": "success"}, "collection": {"result": "success"}})
        for status in ("cancelled", "failure", "skipped", None):
            with self.subTest(status=status), self.assertRaises(ValueError):
                v.require_jobs({"validation": {"result": status}, "collection": {"result": "success"}})
        with self.assertRaises(ValueError): v.require_jobs({"validation": {"result": "success"}})

    def test_incomplete_unittest_execution_cannot_pass(self):
        self.reports[2]["unit_execution"]["unit"]["finished_ids"] = []
        with self.assertRaises(ValueError): self.reconcile()

    def test_missing_original_ids_fail_even_if_counts_match(self):
        self.reports[1]["pytest"]["nodes"] = ["a.py::test_replacement"]
        for report in self.reports[1]["pytest"]["reports"]: report["nodeid"] = "a.py::test_replacement"
        with self.assertRaises(ValueError): self.reconcile()

    def test_duplicate_execution_and_missing_call_fail(self):
        for mode in ("duplicate", "missing"):
            data = deepcopy(self.data)
            if mode == "duplicate": data["reports"].append(deepcopy(data["reports"][1]))
            else: data["reports"].pop(1)
            with self.subTest(mode=mode), self.assertRaises(ValueError): v.validate_execution(data)

    def test_failed_assertion_xfail_and_unfinished_pytest_fail(self):
        for key, value in (("outcome", "failed"), ("wasxfail", True)):
            data = deepcopy(self.data); data["reports"][1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): v.validate_execution(data)
        data = deepcopy(self.data); data["exitstatus"] = 2
        with self.assertRaises(ValueError): v.validate_execution(data)

    def test_existing_platform_skip_remains_visible(self):
        data = deepcopy(self.data); data["reports"].pop(1)
        data["reports"][0].update(outcome="skipped", skip_reason="Windows junctions only")
        self.assertEqual(v.validate_execution(data), {"skipped": 1})

    def test_missing_changed_or_failed_non_pytest_gate_fails(self):
        for commands in ([], [{"argv": ["wrong"], "exitstatus": 0}], [{"argv": ["compile"], "exitstatus": 1}]):
            original = deepcopy(self.reports[2]["commands"]); self.reports[2]["commands"] = commands
            with self.subTest(commands=commands), self.assertRaises(ValueError): self.reconcile()
            self.reports[2]["commands"] = original

    def test_explicit_selections_partition_original_files_without_overlap(self):
        plan = v.read(v.PLAN_PATH); baseline = v.read(v.BASELINE_PATH)
        paths = [p for group in plan["pytest_groups"].values() for p in group]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(set(paths), {n.split("::")[0] for n in baseline["pytest"]})
        self.assertEqual(len(baseline["pytest"]), 1671)
        self.assertEqual(sum(map(len, baseline["unittest"].values())), 155)

    def test_workflow_requires_every_exact_head_group_and_keeps_limits(self):
        import yaml
        workflow = yaml.safe_load((v.ROOT/".github/workflows/default-poster-validation.yml").read_text())
        jobs = workflow["jobs"]; plan = v.read(v.PLAN_PATH)
        self.assertEqual(set(jobs["validation"]["strategy"]["matrix"]["group"]), set(plan["pytest_groups"]) | set(plan["commands"]))
        for name in ("validation", "collection"):
            job = jobs[name]
            self.assertEqual(job["timeout-minutes"], 15)
            self.assertFalse(job["strategy"]["fail-fast"])
            self.assertEqual(job["steps"][0]["with"]["ref"], "${{ github.event.pull_request.head.sha }}")
            self.assertEqual(job["strategy"]["matrix"]["os"], ["ubuntu-latest", "windows-latest"])
        gate = jobs["acceptance"]
        self.assertEqual(set(gate["needs"]), {"validation", "collection"})
        self.assertEqual(gate["if"], "${{ always() }}")
        self.assertEqual(gate["env"]["REQUIRED_JOB_RESULTS"], "${{ toJSON(needs) }}")
        self.assertNotIn("continue-on-error", json.dumps(workflow))


if __name__ == "__main__":
    unittest.main()
