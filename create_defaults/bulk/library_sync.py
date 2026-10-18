"""Full-library read-only reconciliation, comparison, and local review preparation.

Run with the pinned Package E environment. No command writes to GitHub, records
human approval, merges, or changes the production generator.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time

from PIL import Image
import requests

from .common import BulkError, canonical, confined, fingerprint, path_key, reject_links, sha256
from .config import ROOT
from .library_sources import (CANARY_COMMIT, check_seal, blob_id, load_json,
                              published_file, reference, save, sealed, snapshot)
from .library_visual import PROPOSED_POLICY, compare_images, evaluate


def classify_difference(row):
    """Keep historical layout risk separate from observed rendering changes."""
    if row.get("blockers") or not row.get("technical_valid"):
        return "blocked"
    if row["hash_state"] == "exact_match":
        if row["candidate_sha256"] != row["published_sha256"]:
            raise BulkError("false_exact_match", "Exact-match status disagrees with SHA-256 hashes")
        return "exact_match"
    if row["hash_state"] == "missing_published":
        return "missing_published"
    if not row.get("metrics", {}).get("same_dimensions"):
        return "layout_changed"
    if row.get("font_change_expected"):
        return "font_changed"
    return "renderer_equivalence_pending_policy" if row.get("tolerance", {}).get("screen_pass") else "unexpected_difference"


def current_catalog(root):
    baseline = load_json(Path(root) / "baseline.json")
    preflight = load_json(Path(root) / "cache/preflight" / baseline["preflight_sha256"] / "preflight.json")
    payload = {k: v for k, v in preflight.items() if k not in {"sha256", "metrics", "report_directory"}}
    if fingerprint(payload) != preflight["sha256"] or not baseline["passed"]:
        raise BulkError("catalog_validation", "Fresh catalog/preflight evidence is not valid")
    return baseline, {v["id"]: v for v in preflight["variants"]}


def font_history():
    from .migration import legacy, legacy_destination, stable_id
    from .e_canary import SELECTION
    result = {}
    for job in legacy()["jobs"]:
        if job["category"] == "Genre" and job["source"]["definition_line"] == 4883:
            continue
        destination = legacy_destination(job)
        destination = SELECTION.get(stable_id(job["category"], destination), destination)
        result[destination] = {
            "historical_font": job["raw_parameters"]["font"],
            "resolved_historical_font": job["font"]["path"],
            "historical_font_sha256": job["font"]["sha256"], "category": job["category"],
        }
    return result


def candidate_context(row, output, data, current, input_hashes):
    job, receipt = row["job"], row["receipt"]
    path = confined(output, job["local_relative"], must_exist=True)
    if sha256(path) != receipt["sha256"] or path.stat().st_size != receipt["size"]:
        raise BulkError("candidate_hash", "Candidate bytes differ from verified worker receipt")
    from .planner import renderer_identity
    from .overlays import identity
    expected_renderer = identity() if job["kind"] == "overlay" else renderer_identity()
    if data["manifest_header"]["renderer"] != expected_renderer:
        raise BulkError("stale_renderer", "Current renderer/dependencies differ from accepted cache")
    for item in job["inputs"]:
        if input_hashes[item["path"]] != item["sha256"]:
            raise BulkError("stale_input", "Source changed: " + item["path"])
    for dep in job["dependencies"]:
        if input_hashes.get("job:" + dep["job_id"]) != dep["sha256"]:
            raise BulkError("stale_dependency", "Generated dependency differs from receipt: " + dep["job_id"])
    if job["kind"] == "poster":
        variant = current.get(job["id"])
        if (not variant or variant["remote_relative"] != job["remote_relative"]
                or variant["validation_fingerprint"] != row["validation"]["fingerprint"]):
            raise BulkError("stale_preflight", "Current catalog/layout validation differs from cached output")
        if variant["status"] not in {"ready", "ready_with_warning", "shared"}:
            raise BulkError("preflight_blocked", "Current preflight blocks candidate")
    else:
        variant = {}
    with Image.open(path) as image:
        image.verify()
        if job["kind"] == "poster" and (image.size != (2000, 3000) or image.mode != "RGB" or image.format != "JPEG"):
            raise BulkError("candidate_format", "Poster dimensions/mode/format differ")
        if job["kind"] == "overlay" and (image.mode != "RGBA" or image.format != "PNG"
                or image.width > job["parameters"]["box"][0] or image.height > job["parameters"]["box"][1]):
            raise BulkError("candidate_format", "Overlay bounds/mode/format differ")
    return path, variant


def deterministic_samples(rows, maximum=12):
    """Stratified extrema plus deterministic risk/outlier selection."""
    rows = sorted(rows, key=lambda r: r["destination"])
    if not rows:
        return []
    selected = {}
    def pick(row, reason):
        selected.setdefault(row["destination"], set()).add(reason)
    def brightness(row):
        color = row.get("background_color") or "#808080"
        return sum(weight * int(color[start:start + 2], 16) for weight, start in ((.2126, 1), (.7152, 3), (.0722, 5)))
    for reverse, label in ((False, "shortest_caption"), (True, "longest_caption")):
        pick(sorted(rows, key=lambda r: (len(r.get("caption", "")), r["destination"]), reverse=reverse)[0], label)
    predicates = {
        "multiline": lambda r: r.get("layout_risks") and "wrapped_caption" in r["layout_risks"],
        "non_ascii": lambda r: any(ord(c) > 127 for c in r.get("caption", "")),
        "numbers_punctuation": lambda r: any(c.isdigit() or (not c.isalnum() and not c.isspace()) for c in r.get("caption", "")),
        "wide_glyphs": lambda r: any(c in r.get("caption", "") for c in "MWmw"),
        "narrow_glyphs": lambda r: any(c in r.get("caption", "") for c in "Ilit1"),
        "lowercase": lambda r: any(c.islower() for c in r.get("caption", "")),
        "layout_risk": lambda r: bool(r.get("layout_risks")),
        "dark_background": lambda r: brightness(r) < 128,
        "light_background": lambda r: brightness(r) >= 128,
    }
    for label, predicate in predicates.items():
        candidates = [r for r in rows if predicate(r)]
        if candidates:
            pick(candidates[0], label)
    pick(max(rows, key=lambda r: (r.get("metrics", {}).get("rgb_mae", -1), r["destination"])), "maximum_difference")
    pick(min(rows, key=lambda r: (r.get("font_size", 250), r["destination"])), "minimum_fitted_font_size")
    pick(max(rows, key=lambda r: (r.get("font_size", 250), r["destination"])), "maximum_fitted_font_size")
    for row in rows:
        if len(selected) >= min(maximum, len(rows)):
            break
        pick(row, "deterministic_category_member")
    return [{"destination": k, "reasons": sorted(v)} for k, v in sorted(selected.items())]


def _group_manifests(rows, policy, baseline):
    groups = defaultdict(list)
    for row in rows:
        if row["difference_class"] == "exact_match":
            continue
        lane = "overlays" if row["kind"] == "overlay" else row["difference_class"]
        key = (lane, row["font"], row["category"])
        groups[key].append(row)
    output = []
    for (lane, font, category), members in sorted(groups.items()):
        bindings = [{k: r.get(k) for k in ("destination", "candidate_sha256", "published_sha256", "context_sha256")} for r in members]
        output.append(sealed({"schema_version": 1, "lane": lane, "category": category, "font": font,
                              "baseline": baseline, "policy_sha256": fingerprint(policy),
                              "members": bindings, "membership_sha256": fingerprint(bindings),
                              "samples": deterministic_samples(members), "approval": "pending",
                              "exceptions": [r["destination"] for r in members if r["difference_class"] in {"blocked", "unexpected_difference", "layout_changed"}]}))
    return output


def gallery(root, rows, groups):
    root = Path(root)
    cards = []
    by_path = {r["destination"]: r for r in rows}
    for group in groups:
        content = '<h2>' + html.escape(" / ".join((group["lane"], group["category"], group["font"]))) + '</h2>'
        content += '<p>Pending review. Group membership SHA-256: ' + group["membership_sha256"] + '</p>'
        for sample in group["samples"]:
            row = by_path[sample["destination"]]
            content += '<article><h3>' + html.escape(row["destination"]) + '</h3><p>' + html.escape(", ".join(sample["reasons"])) + '</p><div class="pair">'
            for label, field in (("Published", "published_path"), ("Python candidate", "candidate_path")):
                path = row.get(field)
                if path and Path(path).is_file():
                    key = fingerprint([row["destination"], label])[:24]
                    preview = root / "previews" / (key + ".png")
                    preview.parent.mkdir(parents=True, exist_ok=True)
                    with Image.open(path) as image:
                        image.thumbnail((400, 600))
                        image.save(preview)
                    href = Path(os.path.relpath(path, root)).as_posix()
                    content += '<figure><figcaption>' + label + '</figcaption><a href="' + html.escape(href, quote=True) + '"><img loading="lazy" alt="' + html.escape(label + ': ' + row["destination"], quote=True) + '" src="previews/' + key + '.png"></a></figure>'
            content += '</div><details><summary>Hashes, metrics and exceptions</summary><pre>' + html.escape(json.dumps(row, indent=2)) + '</pre></details></article>'
        cards.append(content)
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>English library synchronization review</title><style>body{font:16px system-ui;margin:24px;background:#eee;color:#222;overflow-wrap:anywhere}'
            '.pair{display:flex;gap:20px;flex-wrap:wrap}figure{margin:0;max-width:100%;min-width:0}img{max-width:100%;background:#888}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
            'article{background:white;padding:16px;margin:16px 0}h2{margin-top:48px}</style><h1>Library review: no publication authorized</h1>'
            '<p>Representative deterministic samples, not complete visual coverage. Click an image for full resolution. All decisions remain pending.</p>'
            + ''.join(cards) + '</html>')
    (root / "review.html").write_text(page, encoding="utf-8")


def inventory(root, *, kind, output, catalog=None, local_published=None, workers=2, seconds=10800):
    root = reject_links(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    state = check_seal(load_json(root / "production-snapshot.json"))
    data = reference(kind)
    policy_path = root / "proposed-tolerance-policy.json"
    if not policy_path.exists():
        save(policy_path, PROPOSED_POLICY)
    policy = load_json(policy_path)
    baseline, variants = current_catalog(catalog) if kind == "english" else ({}, {})
    from .overlays import plan
    from .e_validation import configuration
    if kind == "overlays":
        fresh_plan = plan(configuration(root / "overlay-preflight"))
        if fresh_plan["sha256"] != data["manifest_header"]["sha256"]:
            raise BulkError("overlay_plan_drift", "Fresh overlay catalog/inputs differ from accepted full run")
    records = [r for r in data["rows"] if r["job"]["remote_relative"] is not None]
    if kind == "english" and {v["remote_relative"] for v in variants.values() if not v["private"]} != {r["job"]["remote_relative"] for r in records}:
        raise BulkError("catalog_drift", "Current public catalog differs from verified full-run ledger")
    keys = [path_key(r["job"]["remote_relative"]) for r in records]
    if len(keys) != len(set(keys)):
        raise BulkError("path_collision", "Duplicate or case-colliding publication destinations")
    entries = {e["path"]: e for e in state["entries"]}
    remote_keys = defaultdict(list)
    for entry in state["entries"]:
        remote_keys[path_key(entry["path"])].append(entry["path"])
    history = font_history() if kind == "english" else {}
    source_paths = {i["path"] for r in records for i in r["job"]["inputs"]}
    input_hashes = {}
    for path in sorted(source_paths):
        try:
            input_hashes[path] = sha256(confined(ROOT, path, must_exist=True))
        except (OSError, BulkError):
            input_hashes[path] = None
    required_parents = {d["job_id"] for r in records for d in r["job"]["dependencies"]}
    for r in data["rows"]:
        if r["job"]["id"] not in required_parents:
            continue
        p = confined(output, r["job"]["local_relative"])
        input_hashes["job:" + r["job"]["id"]] = sha256(p) if p.is_file() else None
    comparator = sha256(Path(__file__).with_name("library_visual.py"))
    cache = root / (kind + "-comparison.sqlite")
    with sqlite3.connect(cache) as db:
        db.execute("CREATE TABLE IF NOT EXISTS comparisons (identity TEXT PRIMARY KEY, payload TEXT NOT NULL)")
    started = time.monotonic()
    canary = load_json(ROOT / "bulk/evidence/english-canary/preparation-20261017.json")
    canary_hashes = {r["destination"]: r["sha256"] for r in canary["rows"]}
    def one(reference_row):
        job = reference_row["job"]
        destination = job["remote_relative"]
        font = job["parameters"].get("font", "none")
        historical = history.get(destination, {})
        row = {"destination": destination, "id": job["id"], "kind": job["kind"],
               "category": historical.get("category", destination.split('/')[0]), "font": font,
               "caption": job["parameters"].get("text", ""), "font_size": job["parameters"].get("font_size", 0),
               "background_color": job["parameters"].get("base_color"),
               "candidate_sha256": reference_row["receipt"]["sha256"], "published_sha256": None,
               "render_fingerprint": job["render_fingerprint"],
               "validation_fingerprint": reference_row["validation"]["fingerprint"],
               "receipt_sha256": reference_row["receipt"]["receipt_sha256"],
               "identity_correction": reference_row.get("identity_correction"),
               "historical": historical, "canary_member": destination in canary_hashes,
               "approval": "pending", "publication_eligible": False, "technical_valid": False,
               "difference_class": "blocked", "hash_state": "unverifiable", "blockers": []}
        try:
            candidate, variant = candidate_context(reference_row, output, data, variants, input_hashes)
            row.update(candidate_path=str(candidate), candidate_blob=blob_id(candidate), candidate_bytes=candidate.stat().st_size,
                       technical_valid=True, layout_risks=[d["code"] for d in variant.get("diagnostics", []) if d["severity"] == "warning"],
                       layout_probe=variant.get("layout_probe"))
            row["context_sha256"] = fingerprint({"job": job, "validation": reference_row["validation"],
                "renderer": data["manifest_header"]["renderer"], "policy": policy, "baseline": state["head"]})
            if remote_keys.get(path_key(destination), []) not in ([], [destination]):
                raise BulkError("case_conflict", "Published path case conflicts with canonical destination")
            entry = entries.get(destination)
            if not entry:
                row.update(hash_state="missing_published", difference_class="missing_published")
                return row
            if time.monotonic() - started > seconds or (root / "STOP").exists():
                raise BulkError("resource_stop", "Time bound or STOP file reached; rerun to resume")
            published, provenance = published_file(root, state, entry, local_published, force_remote=destination in canary_hashes)
            row.update(published_path=str(published), published_provenance=provenance,
                       published_sha256=sha256(published), published_blob=entry["sha"], published_bytes=published.stat().st_size)
            if row["candidate_sha256"] == row["published_sha256"]:
                row.update(difference_class="exact_match", hash_state="exact_match", approval="not_required")
                row["canary_remote_verified"] = destination in canary_hashes and row["candidate_sha256"] == canary_hashes[destination]
                return row
            row["hash_state"] = "unequal"
            identity = fingerprint([row["candidate_sha256"], row["published_sha256"], comparator, job["parameters"]])
            with sqlite3.connect(cache, timeout=60) as db:
                previous = db.execute("SELECT payload FROM comparisons WHERE identity=?", (identity,)).fetchone()
            if previous:
                metrics = json.loads(previous[0])
            else:
                metrics = compare_images(candidate, published, job["parameters"])
                with sqlite3.connect(cache, timeout=60) as db:
                    db.execute("INSERT OR REPLACE INTO comparisons VALUES (?,?)", (identity, canonical(metrics).decode()))
            row["metrics"], row["tolerance"] = metrics, evaluate(metrics, policy)
            old_font = historical.get("historical_font", "")
            intentional_font = (("PlusJakarta" in font)
                                or ("BebasNeue" in font)
                                or ("Monoton" in font)) and bool(row["caption"])
            row["font_change_expected"] = intentional_font
            row["difference_class"] = classify_difference(row)
            row["layout_review_required"] = bool(variant.get("risk", {}).get("requires_individual"))
        except (OSError, BulkError, ValueError, requests.RequestException) as error:
            row["blockers"].append({"code": getattr(error, "code", type(error).__name__), "reason": str(error)})
            row["difference_class"] = "blocked"
            if not confined(output, job["local_relative"]).is_file():
                row["hash_state"] = "missing_candidate"
        return row
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for row in executor.map(one, records):
            rows.append(row)
            if len(rows) % 100 == 0:
                save(root / (kind + "-progress.json"), {"completed": len(rows), "expected": len(records),
                    "seconds": time.monotonic() - started, "classes": dict(Counter(r["difference_class"] for r in rows))})
                print(kind, len(rows), '/', len(records), flush=True)
    baseline_identity = {k: state[k] for k in ("repository", "branch", "head", "tree")}
    groups = _group_manifests(rows, policy, baseline_identity)
    report = sealed({"schema_version": 1, "kind": kind, "baseline": baseline_identity,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "observed_utc": datetime.now(timezone.utc).isoformat(), "reference_manifest": data["manifest_header"]["sha256"],
        "catalog_preflight_sha256": baseline.get("preflight_sha256"), "policy_sha256": fingerprint(policy),
        "expected": len(records), "private_excluded": len(data["rows"]) - len(records),
        "counts": dict(Counter(r["difference_class"] for r in rows)),
        "hash_states": dict(Counter(r["hash_state"] for r in rows)),
        "by_category": {c: dict(Counter(r["difference_class"] for r in rows if r["category"] == c)) for c in sorted({r["category"] for r in rows})},
        "by_font": {f: dict(Counter(r["difference_class"] for r in rows if r["font"] == f)) for f in sorted({r["font"] for r in rows})},
        "binary_different_approved": 0, "published_this_run": 0,
        "canary_remotely_verified": sum(r.get("canary_remote_verified", False) for r in rows),
        "withheld_or_blocked": sum(r["difference_class"] != "exact_match" for r in rows),
        "remaining_verified_sha256_mismatches": sum(r["hash_state"] == "unequal" for r in rows),
        "verification_gaps": sum(r["hash_state"] not in {"exact_match", "unequal"} for r in rows),
        "unexplained_mismatches": sum(r["difference_class"] == "unexpected_difference" for r in rows),
        "rows": rows, "seconds": time.monotonic() - started, "publication_authorized": False})
    save(root / (kind + "-inventory.json"), report)
    save(root / (kind + "-approval-groups.json"), sealed({"groups": groups, "inventory_sha256": report["sha256"]}))
    save(root / (kind + "-replacement-inventory.json"), sealed({"inventory_sha256": report["sha256"],
         "members": [r for r in rows if r["hash_state"] != "exact_match"], "publication_authorized": False}))
    review_root = root / (kind + "-review")
    review_root.mkdir(exist_ok=True)
    gallery(review_root, rows, groups)
    print(json.dumps({k: report[k] for k in ("kind", "expected", "counts", "hash_states", "canary_remotely_verified", "seconds")}), flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("snapshot")
    p.add_argument("--root", type=Path, required=True)
    p = sub.add_parser("inventory")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--kind", choices=("english", "overlays"), required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--catalog", type=Path)
    p.add_argument("--local-published", type=Path)
    p.add_argument("--workers", type=int, choices=(1, 2, 4), default=2)
    p.add_argument("--seconds", type=int, default=10800)
    args = parser.parse_args(argv)
    if args.command == "snapshot":
        result = snapshot(args.root)
        print(json.dumps({k: result[k] for k in ("head", "tree", "canary_merged")}))
    else:
        if args.kind == "english" and not args.catalog:
            parser.error("English inventory requires a fresh --catalog preflight root")
        inventory(args.root, kind=args.kind, output=args.output, catalog=args.catalog,
                  local_published=args.local_published, workers=args.workers, seconds=args.seconds)


if __name__ == "__main__":
    main()
