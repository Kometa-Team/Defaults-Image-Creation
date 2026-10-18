"""Reconcile immutable analysis snapshots into final local review deliverables."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

from .common import fingerprint, path_key, sha256
from .config import ROOT
from .library_publication import batch_plan, publication_manifest, retained_overlay_decisions
from .library_sources import check_seal, load_json, reference, runtime_identity, save, sealed
from .library_sync import _group_manifests, classify_difference, gallery
from .library_visual import evaluate


def reconcile(original, policy=None):
    check_seal(original)
    result = deepcopy(original)
    result.pop("sha256")
    result["analysis_inventory_sha256"] = original["sha256"]
    result["classification_version"] = "library-difference-v1-layout-risk-independent"
    if policy is not None:
        result["analysis_policy_sha256"] = original["policy_sha256"]
        result["policy_sha256"] = fingerprint(policy)
    for row in result["rows"]:
        old = row["difference_class"]
        if policy is not None and row.get("metrics"):
            row["tolerance"] = evaluate(row["metrics"], policy)
            row["analysis_context_sha256"] = row["context_sha256"]
            row["context_sha256"] = fingerprint({"analysis_context": row["context_sha256"], "policy": policy})
        row["difference_class"] = classify_difference(row)
        row["layout_review_required"] = bool(row.get("layout_risks"))
        if old != row["difference_class"]:
            row["analysis_difference_class"] = old
            row["classification_note"] = ("Historical wrapping/clipping risk requires review; it is not proof of changed layout"
                if old == "layout_changed" and row.get("metrics", {}).get("same_dimensions")
                else "Re-evaluated under the separate versioned proposed policy; no new approval")
    retained = retained_overlay_decisions(result)
    for row in result["rows"]:
        if row["destination"] in retained:
            row["approval"] = "retained_exact_historical_decision"
            row["retained_decision"] = retained[row["destination"]]
            row["publication_eligible"] = row["hash_state"] != "exact_match"
    rows = result["rows"]
    result["counts"] = dict(Counter(r["difference_class"] for r in rows))
    result["by_category"] = {c: dict(Counter(r["difference_class"] for r in rows if r["category"] == c)) for c in sorted({r["category"] for r in rows})}
    result["by_font"] = {f: dict(Counter(r["difference_class"] for r in rows if r["font"] == f)) for f in sorted({r["font"] for r in rows})}
    result["binary_different_approved"] = sum(r["publication_eligible"] for r in rows)
    result["withheld_or_blocked"] = sum(r["hash_state"] != "exact_match" and not r["publication_eligible"] for r in rows)
    result["unexplained_mismatches"] = sum(r["hash_state"] == "unequal" and r["difference_class"] == "unexpected_difference" and not r["publication_eligible"] for r in rows)
    result["layout_review_required"] = sum(r["layout_review_required"] and r["hash_state"] != "exact_match" for r in rows)
    return sealed(result)


def build(root):
    root = Path(root)
    production = check_seal(load_json(root / "production-snapshot.json"))
    english_policy = load_json(root / "proposed-tolerance-policy.json")
    inventories, plans = {}, {}
    groups = []
    for kind in ("english", "overlays"):
        policy = load_json(root / "proposed-overlay-tolerance-policy.json") if kind == "overlays" else english_policy
        original = load_json(root / (kind + "-inventory.json"))
        report = reconcile(original, policy=policy)
        jobs = {r["job"]["id"]: r["job"] for r in reference(kind)["rows"]}
        report.pop("sha256")
        report["runtime"] = runtime_identity()
        for row in report["rows"]:
            row["background_color"] = jobs[row["id"]]["parameters"].get("base_color")
        report = sealed(report)
        inventories[kind] = report
        save(root / (kind + "-reconciled-inventory.json"), report)
        manifest = publication_manifest(report, policy)
        plan = batch_plan(manifest)
        plans[kind] = manifest
        save(root / (kind + "-publication-manifest.json"), manifest)
        save(root / (kind + "-git-batch-plan.json"), plan)
        approval_groups = _group_manifests(report["rows"], policy, report["baseline"])
        save(root / (kind + "-approval-groups.json"), sealed({"inventory_sha256": report["sha256"], "groups": approval_groups}))
        review_root = root / (kind + "-review")
        review_root.mkdir(exist_ok=True)
        gallery(review_root, report["rows"], approval_groups)
        pending = defaultdict(list)
        for row in report["rows"]:
            if row["hash_state"] == "exact_match":
                continue
            key = "overlays" if kind == "overlays" else ("font:" + row["font"] if row["difference_class"] == "font_changed" else "renderer-and-layout-review")
            pending[key].append(row)
        for name, rows in sorted(pending.items()):
            groups.append({"name": name, "kind": kind, "destinations": len(rows),
                           "bytes": sum(r.get("candidate_bytes", 0) for r in rows),
                           "eligible_now": sum(r["publication_eligible"] for r in rows),
                           "members_sha256": fingerprint([{k: r.get(k) for k in ("destination", "candidate_sha256", "context_sha256")} for r in rows]),
                           "publication_authorized": False})
    save(root / "publication-groups.json", sealed({"groups": groups,
        "note": "Logical publication groups are independent of visual review groups and transport batches. Final PR count depends on approval and exceptions."}))
    calibration = check_seal(load_json(root / "tolerance-calibration.json"))
    fonts = check_seal(load_json(root / "font-impact-matrix.json"))
    benchmark_path = root / "offline-overlay-benchmark-v2/benchmark.json"
    benchmark = check_seal(load_json(benchmark_path)) if benchmark_path.exists() else None
    summary = {"schema_version": 1, "baseline": inventories["english"]["baseline"],
        "canary_remotely_hash_verified": inventories["english"]["canary_remotely_verified"],
        "inventories": {}, "calibration": {k: calibration[k] for k in ("accepted_positive_distribution", "accepted_positive_rejected", "defective_controls_missed", "policy_approved")},
        "fonts": [{k: f[k] for k in ("original_font", "replacement_font", "public_destinations", "rendered_caption_destinations", "categories")} for f in fonts["fonts"]],
        "logical_publication_groups": groups, "offline_transport": benchmark,
        "proposed_transport_defaults": {"maximum_files": 300, "maximum_bytes": 200 * 1024 ** 2,
            "pack_reserve": "Measure actual incremental packs before authorized remote staging; binary artifacts may not compress further",
            "github_push_limit_documentation": "https://docs.github.com/en/get-started/using-git/troubleshooting-the-2-gb-push-limit",
            "limits_documentation": "https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits",
            "measured_network_transport": False},
        "publication_authorized": False, "published_this_assignment": 0,
        "runtime": runtime_identity(),
        "approvals_required": ["Approve calibrated, immutable tolerance policy for its exact scope",
            "Accept exact font/layout groups and individual exceptions with version-bound manifests",
            "Accept overlay group policy and exceptions beyond the 64 retained exact samples",
            "Separately authorize exact remote artwork staging/publication operations; merges require separate authorization"],
        "source_files_sha256": {p.relative_to(ROOT.parent).as_posix(): sha256(p) for p in sorted((ROOT / "bulk").glob("library_*.py"))}}
    overlay_calibration = root / "overlay-tolerance-calibration.json"
    if overlay_calibration.exists():
        overlay = check_seal(load_json(overlay_calibration))
        summary["overlay_calibration"] = {k: overlay[k] for k in ("policy_sha256", "retained_exact_samples", "known_accepted_screen_rejections", "defective_controls_missed", "proposed_screen_passes", "policy_approved")}
    for kind, report in inventories.items():
        summary["inventories"][kind] = {k: report[k] for k in ("sha256", "expected", "private_excluded", "counts", "hash_states", "by_category", "by_font", "binary_different_approved", "withheld_or_blocked", "remaining_verified_sha256_mismatches", "verification_gaps", "layout_review_required")}
        summary["inventories"][kind]["eligible_manifest_entries"] = len(plans[kind]["members"])
        summary["inventories"][kind]["exceptions"] = [{"destination": r["destination"], "hash_state": r["hash_state"], "blockers": r["blockers"]} for r in report["rows"] if r["hash_state"] not in {"exact_match", "unequal"}]
        expected = {r["destination"] for r in report["rows"]}
        prefixes = {p.split('/')[0] for p in expected}
        extras = [e["path"] for e in production["entries"] if e["type"] == "blob" and e["path"] not in expected
            and ((kind == "overlays" and "/overlays/" in e["path"] and e["path"].endswith('.png'))
                 or (kind == "english" and e["path"].split('/')[0] in prefixes and e["path"].endswith('.jpg')))]
        summary["inventories"][kind]["additional_published_paths_outside_catalog"] = extras
        for exception in summary["inventories"][kind]["exceptions"]:
            exception["published_case_candidates"] = [e["path"] for e in production["entries"] if path_key(e["path"]) == path_key(exception["destination"])]
    summary = sealed(summary)
    save(root / "reconciliation-summary.json", summary)
    lines = ["# Full English library engineering execution", "", "No artwork was published by this assignment. Production PowerShell is unchanged.", "",
             "Production baseline: `" + summary["baseline"]["head"] + "`; canary actual remote SHA-256 checks: " + str(summary["canary_remotely_hash_verified"]) + "/7.", "",
             "| Population | Expected | Exact SHA-256 | Verified unequal | Gaps | Approved replacements | Withheld/blocked |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for kind, inv in summary["inventories"].items():
        lines.append(f"| {kind} | {inv['expected']} | {inv['hash_states'].get('exact_match', 0)} | {inv['remaining_verified_sha256_mismatches']} | {inv['verification_gaps']} | {inv['binary_different_approved']} | {inv['withheld_or_blocked']} |")
    lines += ["", "All binary-different outputs remain in complete replacement inventories. Eligible files enter exact publication manifests; appearance never suppresses replacement.", "",
              "Calibration: " + str(summary["calibration"]), "", "Font families: " + str(len(summary["fonts"])) + ". Full impact matrix and all member hashes are in `font-impact-matrix.json`.", "",
              "Review galleries: `english-review/review.html`, `overlays-review/review.html`, `calibration/review.html`.", "",
              "The proposed 300-file / 200-MiB transport caps are conservative starting values. GitHub documents a 2-GiB push limit; local rehearsal is not a network benchmark. See the linked documentation in the machine-readable summary.", "",
              "The 64 retained overlay decisions are reused only when exact candidate, rendering, validation and prior comparison identities match. Different worker receipt envelopes are retained separately; they do not change those accepted image identities.", "",
              "Complete synchronization remains pending review and separately authorized publication. Explained outstanding mismatches are not exact matches.", ""]
    (root / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    result = build(args.root)
    import json
    print(json.dumps({kind: {k: value[k] for k in ("expected", "counts", "eligible_manifest_entries")} for kind, value in result["inventories"].items()}, indent=2))


if __name__ == "__main__":
    main()
