"""Controlled before/after multilingual audit against immutable Package E evidence."""
import argparse
from collections import Counter, defaultdict
import gc
import gzip
import json
from pathlib import Path
import time

import psutil
from .catalog import load_catalog
from .common import BulkError, canonical, fingerprint, reject_links, sha256
from .config import CATEGORIES
from .e_languages import copy_pinned_resources
from .e_validation import configuration, environment, save
from .generators import GENERATORS
from .languages import LanguageSnapshot, translations_from_snapshot
from .planner import Planner
from .poster_key_audit import poster_key_audit
from .preflight import ELIGIBLE, preflight
from .typography import cache_info, measure, _measure, _font

def audit(root, previous):
    root, previous = reject_links(root).resolve(), reject_links(previous).resolve()
    if (root / "multilingual-summary.json").exists():
        raise BulkError("immutable_audit", "Choose a fresh audit directory; completed evidence is not overwritten")
    config = configuration(root)
    pin = json.loads((previous / "translation-refresh.json").read_text(encoding="utf-8"))
    snapshot = LanguageSnapshot.load(pin["metrics"]["snapshot_file"])
    copy_pinned_resources(snapshot, previous / "cache/translations", config.cache_dir / "translations")
    translated = translations_from_snapshot(snapshot, config.cache_dir / "translations")
    historical_path = previous / "cache/complete-audit.json"
    historical_digest = sha256(historical_path)
    historical = json.loads(historical_path.read_text(encoding="utf-8"))
    old_scopes = {(s["category"], s["language"]): s for s in historical["scopes"]}
    resources, minimal, groups, matrix, scopes = {}, {}, {}, defaultdict(Counter), []
    examples, english_differences = {}, []
    started, peak = time.perf_counter(), 0
    process = psutil.Process()
    ledger_path = root / "variant-decisions.jsonl.gz"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("wb") as stream, gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=0) as ledger:
        for category in CATEGORIES:
            if category == "Overlays":
                continue
            definitions = load_catalog([category])
            prepared = Planner(config, generators=GENERATORS).expand(definitions)
            for language in snapshot.select(["all"]):
                import shutil
                if time.perf_counter() - started > 5400 or shutil.disk_usage(root).free < 8 * 1024 ** 3:
                    raise BulkError("audit_resource_limit", "Bounded audit time/free-disk limit reached")
                old_scope = old_scopes[(category, language)]
                path = previous / "cache/preflight" / old_scope["sha256"] / "preflight.json"
                old = json.loads(path.read_text(encoding="utf-8"))
                if fingerprint({k: v for k, v in old.items() if k != "sha256"}) != old_scope["sha256"]:
                    raise BulkError("corrupt_preflight", "Historical audit identity mismatch")
                old_by_id = {v["id"]: v for v in old["variants"]}
                report, effective = preflight(definitions, translated, config=config, generators=GENERATORS,
                    categories=[category], languages=[language], registry=snapshot, policy="audit",
                    resources=resources, prepared=prepared)
                counts = Counter()
                for v in report["variants"]:
                    if v["id"] in minimal:
                        raise BulkError("duplicate_variant", "Full audit must count each category variant once")
                    minimal[v["id"]] = {k: v[k] for k in ("id", "poster_id", "language", "category", "status", "translation_dependencies")}
                    prior = old_by_id[v["id"]]
                    codes = {d["code"] for d in v["diagnostics"]}
                    typography = v.get("typography")
                    counts["variants"] += 1
                    counts["before_" + prior["status"]] += 1
                    counts["after_" + v["status"]] += 1
                    counts["newly_technically_eligible"] += prior["status"] not in ELIGIBLE and v["status"] in ELIGIBLE
                    counts["old_english_matching_blocker"] += any(d["code"] == "stale_measurement" for d in prior["diagnostics"])
                    counts["missing_glyph"] += "missing_glyph" in codes
                    counts["rtl_shaping_limitation"] += "rtl_awaiting_review" in codes
                    counts["blocked_dependencies"] += "blocked_dependency" in codes
                    probe = v.get("layout_probe")
                    counts["actual_current_clipping_or_image_failure"] += bool(probe and (probe["clipped"] or probe.get("outside_image")))
                    counts["fits_current_parameters"] += bool(probe and not probe["clipped"] and not probe.get("outside_image"))
                    counts["fits_after_proposal"] += bool(typography and typography["proposal"])
                    counts["requires_layout_review"] += bool(typography and typography["state"] == "needs_layout_review")
                    counts["pending_individual_artwork_review"] += v["status"] in ELIGIBLE and not v["private"] and v["risk"]["requires_individual"]
                    counts["potential_future_group_review_candidates"] += v["status"] in ELIGIBLE and not v["private"] and not v["risk"]["requires_individual"]
                    counts["private_intermediates"] += v["private"]
                    if language == "en" and v["validation_fingerprint"] != prior["validation_fingerprint"]:
                        english_differences.append(v["id"])
                    measurement_key = None
                    if typography:
                        measurement_key = typography["measurement_key"]
                        group = groups.setdefault(measurement_key, {"evidence": typography, "members": []})
                        group["members"].append(v["id"])
                        try:
                            definition = prepared[0][v["poster_id"]]
                            from .preflight import effective_language
                            english = translated.resolve(effective_language(definition, "en")["caption"], "en").text
                            comparison = "longer" if len(v["caption"]) > len(english) else "shorter" if len(v["caption"]) < len(english) else "same_length"
                            if typography["state"] == "fits_current" and language != "en" and v["caption"] != english and comparison not in examples:
                                examples[comparison] = {"id": v["id"], "language": language, "english": english,
                                    "translated": v["caption"], "evidence": typography, "validation": v["validation_fingerprint"]}
                        except BulkError:
                            pass
                    row = {k: v.get(k) for k in ("id", "poster_id", "language", "category", "status", "private",
                        "definition_fingerprint", "validation_fingerprint", "inputs", "translation_dependencies", "dependencies")}
                    row.update(before_status=prior["status"], before_validation=prior["validation_fingerprint"],
                        diagnostic_codes=sorted(codes), measurement_key=measurement_key, new_artwork_approval=False)
                    ledger.write(canonical(row) + b"\n")
                scopes.append({"category": category, "language": language, "before_preflight": old["sha256"],
                    "after_preflight": report["sha256"], "counts": dict(counts)})
                matrix[language].update(counts)
                peak = max(peak, process.memory_info().rss)
                print(json.dumps(scopes[-1]), flush=True)
                del report, effective, old, old_by_id
                gc.collect()
    key_audit = poster_key_audit([{"variants": list(minimal.values())}], translated, snapshot)
    save(root / "poster-required-keys.json", key_audit)
    save(root / "measurement-groups.json", groups)
    if english_differences:
        save(root / "english-identity-differences.json", english_differences)
        raise BulkError("english_identity_changed", "The correction changed frozen English validation identities")
    # A controlled microbenchmark of actual distinct audit measurements. Font
    # loading is recorded separately; warm means the same in-process cache only.
    sample = list(groups.values())[:512]
    observed_cache = cache_info()
    _measure.cache_clear()
    _font.cache_clear()
    timings = []
    for _ in range(2):
        begin = time.perf_counter()
        for group in sample:
            i = group["evidence"]["inputs"]
            from .config import ROOT
            approved = json.loads((ROOT / "bulk/baselines/approved-fonts.json").read_text(encoding="utf-8"))["fonts"]
            font_relative = next(k for k, digest in approved.items() if digest == i["font_sha256"])
            measure(config.asset_dir / font_relative, i["font_sha256"], i["caption"],
                    i["point_size"], i["text_offset"], i["renderer"])
        timings.append(time.perf_counter() - begin)
    if sha256(historical_path) != historical_digest:
        raise BulkError("historical_evidence_changed", "Original audit changed during evaluation")
    result = {"version": "multilingual-addendum-e2", "environment": environment(),
        "translation_snapshot": snapshot.data, "historical_audit_file_sha256": historical_digest,
        "historical_audit_unchanged": True, "matrix": {k: dict(v) for k, v in matrix.items()},
        "poster_key_coverage": key_audit["matrix"], "scopes": scopes, "examples": examples,
        "english_variants_identity_checked": matrix["en"]["variants"], "english_identity_differences": [],
        "measurement_groups": {"unique": len(groups), "members": sum(len(g["members"]) for g in groups.values()),
            "repeated": sum(len(g["members"]) > 1 for g in groups.values()), "audit_cache": observed_cache,
            "microbenchmark_distinct_measurements": len(sample), "cold_seconds": timings[0], "warm_seconds": timings[1],
            "cache_after_microbenchmark": cache_info(), "scope": "In-process native measurement reuse, not whole rendering speedup"},
        "identities": {"variants_file_sha256": sha256(ledger_path), "poster_keys_file_sha256": sha256(root / "poster-required-keys.json"),
            "measurement_groups_file_sha256": sha256(root / "measurement-groups.json")},
        "elapsed_seconds": time.perf_counter() - started, "peak_parent_rss": peak,
        "human_artwork_approval": {"new_approvals": 0, "exact_approved_current_audit_outputs": 0,
            "stale_current_audit_records": 0, "rejected_current_audit_records": 0,
            "invalidated_current_audit_approvals": 0,
            "scope": "Fresh isolated technical audit without rendering or approval import; existing D decisions remain bound to their own exact bytes"},
        "overlap": "Technical diagnostic counts overlap; fitting proposals and current clipping may describe the same variant",
        "publication": False}
    result["sha256"] = fingerprint(result)
    save(root / "multilingual-summary.json", result)
    print(json.dumps({"status": "complete", "variants": len(minimal), "english_identity_differences": 0,
        "newly_eligible": sum(m["newly_technically_eligible"] for m in matrix.values()), "new_artwork_approvals": 0}), flush=True)
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--previous", required=True, type=Path)
    args = parser.parse_args()
    audit(args.root, args.previous)

if __name__ == "__main__":
    main()
