"""Read-only prior-acceptance reconciliation and fresh generated-parent references."""
import argparse
from collections import Counter
import json
import gzip
from pathlib import Path
import time

from create_defaults.create_poster import PosterOptions, create_poster
from .common import BulkError, fingerprint, sha256, reject_links, confined
from .config import ROOT
from .e_validation import save, configuration
from .planner import validate_manifest
from .migration import legacy, legacy_destination


def historical_job(job, previous):
    original = previous.get(job["id"])
    exception = None
    if original is None and job["id"] == "franchise-06945-8e8134ef709a":
        original = previous["franchise-06945-682bdad094e1"]
        before, after = original["parameters"], job["parameters"]
        if (before["out_name"] != "Death in Paradise (2911)"
            or after["out_name"] != "Death in Paradise (2011)"
            or {k: v for k, v in before.items() if k != "out_name"} != {k: v for k, v in after.items() if k != "out_name"}
            or original["published_relatives"] != ["franchise/Death in Paradise (2911).jpg"]
            or job["published_relatives"] != ["franchise/Death in Paradise (2011).jpg"]):
            raise BulkError("reference_deviation", "Unknown change beyond approved D08 filename correction")
        exception = "D08: approved output-name-only Death in Paradise (2911) -> (2011) correction; image inputs unchanged"
    if original is None:
        raise BulkError("missing_reference", "No exact prior reference or enumerated approved identity correction")
    if (original["source"] != job["source"] or original["assets"] != job["assets"]
        or original["font"]["sha256"] != job["font"]["sha256"]):
        raise BulkError("reference_deviation", "Historical source/font inputs do not match corrected capture")
    return original, exception


def reference_index(root):
    root = reject_links(root).resolve()
    configuration(root)
    source = ROOT.parent / "config/phase1-validation-20261016/full-batch-monoton-ofl"
    capture = legacy()
    previous_manifest = json.loads(gzip.decompress((source / "manifest.json.gz").read_bytes()))
    assert fingerprint({k: v for k, v in previous_manifest.items() if k != "sha256"}) == previous_manifest["sha256"]
    previous = {j["id"]: j for j in previous_manifest["jobs"]}
    ledger = []
    for job in capture["jobs"]:
        if job["category"] == "Genre" and job["source"]["definition_line"] == 4883:
            continue
        original, exception = historical_job(job, previous)
        path = source / "cases" / original["id"] / "result.json"
        value = json.loads(path.read_text())
        assert value["job_sha256"] == original["sha256"]
        if not value["complete"] or value["status"] not in {"pass", "warning"}:
            raise BulkError("unaccepted_reference", "Prior full-run evidence is incomplete")
        ledger.append({"legacy_id": job["id"], "historical_id": original["id"], "approved_identity_correction": exception, "path": "defaults-en/" + legacy_destination(job),
            "category": job["category"], "job_sha256": job["sha256"],
            "reference_result_sha256": sha256(path), "python_sha256": value["images"]["python"]["sha256"],
            "legacy_sha256": value["images"]["legacy"]["sha256"],
            "previous_status": value["status"], "previous_classification": value["classification"],
            "dependencies": value["generated_input_hashes"],
            "published_counterparts": value.get("published_counterparts", [])})
    assert len(ledger) == 9957 and len({x["path"] for x in ledger}) == 9957
    save(root / "phase1-reference-ledger.json", ledger)
    summary = {"jobs": len(ledger), "ledger_sha256": fingerprint(ledger),
        "capture_sha256": capture["sha256"], "reference_manifest_sha256": sha256(source / "manifest.json.gz"),
        "reference_final_audit_sha256": sha256(source / "final-audit.json"),
        "classifications": dict(Counter(v["previous_classification"] for v in ledger)),
        "scope": "Read-only exact result hashes from previously accepted complete Phase 1 run; D02 green duplicate excluded, two private outputs retained"}
    save(root / "phase1-reference-summary.json", summary)
    print(json.dumps(summary), flush=True)
    return ledger


def compare(root, generated):
    root, generated = reject_links(root).resolve(), reject_links(generated).resolve()
    configuration(root)
    reference = json.loads((root / "phase1-reference-ledger.json").read_text())
    source_summary = json.loads((root / "phase1-reference-summary.json").read_text())
    if fingerprint(reference) != source_summary["ledger_sha256"]:
        raise BulkError("corrupt_reference", "Prior acceptance ledger differs from its recorded identity")
    current = json.loads((generated / "verified-output-ledger.json").read_text())
    result = json.loads((generated / "cold-result.json").read_text())
    validate_manifest(result["manifest"])
    jobs = {j["local_relative"]: j for j in result["manifest"]["jobs"]}
    originals = {v["path"]: v for v in reference}
    if set(jobs) != set(originals) or {v["path"] for v in current} != set(jobs):
        raise BulkError("acceptance_inventory", "Full generated/reference inventories differ")
    ledger = []
    for item in current:
        old, job = originals[item["path"]], jobs[item["path"]]
        if item["id"] != job["id"]:
            raise BulkError("corrupt_artifact", "Output ledger identity differs from the validated manifest")
        assert sha256(generated / "output" / item["path"]) == item["sha256"]
        row = {"path": item["path"], "sha256": item["sha256"],
            "phase1_python_sha256": old["python_sha256"], "phase1_legacy_sha256": old["legacy_sha256"],
            "phase1_result_sha256": old["reference_result_sha256"],
            "historical_status": old["previous_status"], "historical_classification": old["previous_classification"]}
        if item["sha256"] == old["python_sha256"]:
            row["classification"] = "exact_approved_phase1_python_bytes"
        elif job["dependencies"]:
            # Phase 1 froze common fresh-legacy parents. Production generation
            # uses real Python parents, so test the approved API on those bytes.
            parameters = dict(job["parameters"])
            inputs = list(job["inputs"])
            for dep in job["dependencies"]:
                parent = next(j for j in jobs.values() if j["id"] == dep["job_id"])
                inputs.append({"role": dep["input"], "path": parent["local_relative"],
                               "sha256": dep["sha256"], "generated": True})
            for source in inputs:
                if source["role"] in {"logo", "avg_color_image", "font"}:
                    base = generated / "output" if source.get("generated") else ROOT
                    path = confined(base, source["path"], must_exist=True)
                    assert sha256(path) == source["sha256"]
                    parameters[source["role"]] = str(path)
            target = root / "fresh-parent-references" / (fingerprint(item["id"]) + ".jpg")
            target.parent.mkdir(parents=True, exist_ok=True)
            create_poster(PosterOptions(**parameters), output_path=target, asset_dir=ROOT, font_dir=ROOT / "fonts")
            row["fresh_common_parent_reference_sha256"] = sha256(target)
            row["current_parent_hashes"] = {v["job_id"]: v["sha256"] for v in job["dependencies"]}
            row["phase1_parent_evidence"] = old["dependencies"]
            row["classification"] = "exact_approved_api_using_current_python_parents" if sha256(target) == item["sha256"] else "unexplained_difference"
        else:
            row["classification"] = "unexplained_difference"
        ledger.append(row)
    save(root / "complete-comparison-ledger.json", ledger)
    summary = {"outputs": len(ledger), "classifications": dict(Counter(v["classification"] for v in ledger)),
        "ledger_sha256": fingerprint(ledger), "source_reference_summary": json.loads((root / "phase1-reference-summary.json").read_text()),
        "new_visual_approvals": 0, "scope": "Exact prior accepted Python byte evidence, with fresh direct approved API comparisons for changed generated-parent inputs. Historical legacy differences retain their classifications."}
    summary["passed"] = summary["classifications"].get("unexplained_difference", 0) == 0
    save(root / "complete-comparison-summary.json", summary)
    print(json.dumps(summary), flush=True)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["index", "compare"])
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--generated", type=Path)
    args = parser.parse_args(argv)
    if args.operation == "index":
        reference_index(args.root)
    elif args.generated:
        if not compare(args.root, args.generated)["passed"]:
            raise BulkError("renderer_parity", "Unexplained rendering differences fail acceptance; evidence retained")
    else:
        parser.error("compare requires --generated")


if __name__ == "__main__":
    main()
