"""Read-only coverage consistency and explicitly unapproved fitting/Arabic evidence."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import shutil

from .catalog import load_catalog
from .common import BulkError, fingerprint, sha256, reject_links, confined, atomic_bytes
from .config import ROOT
from .d_summary import audit_summary
from .e_validation import configuration, save
from .languages import LanguageSnapshot, translations_from_snapshot
from .preflight import preflight, export_report, variant_id
from .review import Reviews
from .services import propose_layout, preview
from .definitions import Definition
from .state import Store


def copy_pinned_resources(snapshot, source_cache, destination_cache):
    """Stage verified snapshot blobs for an isolated existing evaluator."""
    from .remote import git_sha
    copied = 0
    for resource in snapshot.data["languages"]:
        if resource["availability"] != "available" or "defaults" not in resource["components"]:
            continue
        relative = "blobs/" + git_sha(resource["git_blob"]) + ".yml"
        source = confined(source_cache, relative, must_exist=True)
        if source.stat().st_size != resource["size"] or sha256(source) != resource["sha256"]:
            raise BulkError("corrupt_snapshot", "Pinned resource changed before isolated evaluation")
        target = confined(destination_cache, relative)
        if target.exists():
            if sha256(target) != resource["sha256"]:
                raise BulkError("corrupt_snapshot", "Isolated evaluator cache differs from pinned resource")
        else:
            atomic_bytes(target, source.read_bytes())
        copied += 1
    return copied


def proposals(root, snapshot_root):
    root, snapshot_root = reject_links(root).resolve(), Path(snapshot_root).resolve()
    config = configuration(root)
    record = json.loads((snapshot_root / "translation-refresh.json").read_text())
    snapshot = LanguageSnapshot.load(record["metrics"]["snapshot_file"])
    translated = translations_from_snapshot(snapshot, snapshot_root / "cache/translations")
    accepted = json.loads((ROOT / "bulk/evidence/package-d/maintainer-visual-acceptance-20261017.json").read_text())
    rows = []
    definitions = load_catalog(["Based"])
    book = next(d for d in definitions if d.id == "based.based-book.217e49bd")
    for language, selected in (("fr", definitions), ("de", [book]), ("bg", [book])):
        for definition in selected:
            try:
                proposal = propose_layout(definition, translated, language, config)
                file = root / "proposals" / language / (definition.id + ".json")
                save(file, proposal)
                reviews = Reviews(Store(config.cache_dir / "state.sqlite"), config)
                result = preview((Definition.create(proposal["definition"]),), translated,
                    config=config, posters=[definition.id], languages=[language], reviews=reviews,
                    explicit=[variant_id(definition.id, language)])
                rows.append({"id": variant_id(definition.id, language), "language": language,
                    "poster": definition.id, "proposal_sha256": sha256(file),
                    "measurement": proposal["measurement"], "status": result["status"],
                    "preflight_sha256": result["preflight"]["sha256"],
                    "preview": result["review_html"], "new_acceptance_granted": False,
                    "matches_prior_accepted_french_proposal": language == "fr" and definition.id == "based.based-book.217e49bd" and sha256(file) == accepted["french_proposal"]["file_sha256"]})
            except (BulkError, ValueError) as error:
                rows.append({"language": language, "poster": definition.id, "status": "blocked",
                    "reason": getattr(error, "code", type(error).__name__), "message": str(error), "new_acceptance_granted": False})
    # Candidate font/license stay in isolated evaluation, never production fonts.
    from .d_evidence import arabic
    arabic_config = configuration(root / "arabic")
    candidate = arabic_config.cache_dir / "arabic-evaluation"
    candidate.mkdir(parents=True, exist_ok=True)
    original = ROOT.parent / "config/package-d/cache/arabic-evaluation"
    for name in ("NotoSansArabic[wdth,wght].ttf", "OFL.txt"):
        target = candidate / name
        if not target.exists():
            shutil.copyfile(original / name, target)
        assert sha256(target) == sha256(original / name)
    copy_pinned_resources(snapshot, snapshot_root / "cache/translations", arabic_config.cache_dir / "translations")
    save(arabic_config.cache_dir / "translation-refresh.json", record)
    evaluated = arabic(arabic_config)
    result = {"proposals": rows, "arabic": evaluated,
              "new_visual_approvals": 0, "production_font_installs": 0,
              "scope": "Representative fitting proposals and candidate joining/bidi/anchor probes only; all new views pending actual maintainer review"}
    save(root / "proposal-summary.json", result)
    print(json.dumps({"proposals": len(rows), "status": dict(Counter(r["status"] for r in rows)),
                      "arabic": evaluated["status"], "new_visual_approvals": 0}), flush=True)
    return result


def coverage(root, baseline):
    root, baseline = reject_links(root).resolve(), reject_links(baseline).resolve()
    audit = json.loads((root / "cache/complete-audit.json").read_text())
    summary, missing = audit_summary(audit)
    summary["raw_audit_sha256"] = sha256(root / "cache/complete-audit.json")
    summary["contributor_mapping_sha256"] = fingerprint(missing)
    export_report({"status": "partial", "registry_sha256": summary["registry_sha256"],
        "variants": [], "missing_translations": missing},
        root / "cache/contributor-audit-deduplicated" / fingerprint(missing))
    before = json.loads((baseline / "baseline.json").read_text())
    all_report = json.loads((baseline / "cache/preflight" / before["preflight_sha256"] / "preflight.json").read_text())
    expected = {v["id"]: v["validation_fingerprint"] for v in all_report["variants"]}
    actual, groups = {}, defaultdict(list)
    for path in (root / "cache/preflight").glob("*/preflight.json"):
        report = json.loads(path.read_text())
        assert fingerprint({k: v for k, v in report.items() if k != "sha256"}) == report["sha256"]
        for v in report["variants"]:
            if v["language"] == "en":
                actual[v["id"]] = v["validation_fingerprint"]
            if v["language"] != "en" and v.get("caption") and v["inputs"].get("font") and v.get("layout_probe"):
                key = fingerprint({"language": v["language"], "exact_caption": v["caption"],
                    "font_sha256": v["inputs"]["font"]["sha256"], "probe": v["layout_probe"],
                    "layout_policy": report["policy"]["layout"]})
                groups[key].append({"id": v["id"], "validation": v["validation_fingerprint"],
                    "definition": v["definition_fingerprint"], "status": v["status"],
                    "risk": v["risk"], "inputs_sha256": fingerprint(v["inputs"])})
    differences = sorted(identity for identity in expected.keys() | actual.keys() if expected.get(identity) != actual.get(identity))
    record = json.loads((root / "translation-refresh.json").read_text())
    registry = LanguageSnapshot.load(record["metrics"]["snapshot_file"])
    translated = translations_from_snapshot(registry, root / "cache/translations")
    book = load_catalog(posters=["based.based-book.217e49bd"])
    single = preflight(book, translated, config=configuration(root), posters=["based.based-book.217e49bd"],
                       languages=["en"], registry=registry, policy="audit")[0]
    one = single["variants"][0]
    summary["scope_consistency"] = {"full_catalog_english": len(expected), "category_english": len(actual),
        "differences": differences, "single_book_matches": one["validation_fingerprint"] == expected[one["id"]]}
    summary["fitting_measurement_groups"] = {"groups": len(groups),
        "members": sum(len(v) for v in groups.values()), "repeated_groups": sum(len(v) > 1 for v in groups.values()),
        "scope": "Exact caption/font/native metric measurement reuse candidates, not artwork review/approval groups",
        "current_policy": "Any translated caption remains high risk under review-risk-d1; no policy change or group approval"}
    save(root / "fitting-measurement-groups.json", dict(groups))
    save(root / "complete-language-summary.json", summary)
    if differences or not summary["scope_consistency"]["single_book_matches"]:
        raise BulkError("scope_inconsistency", "One-poster/category/full English validation identities differ")
    print(json.dumps(summary), flush=True)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["proposals", "coverage"])
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--snapshot-root", type=Path)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args(argv)
    if args.operation == "proposals" and args.snapshot_root:
        proposals(args.root, args.snapshot_root)
    elif args.operation == "coverage" and args.baseline:
        coverage(args.root, args.baseline)
    else:
        parser.error("proposals requires --snapshot-root; coverage requires --baseline")


if __name__ == "__main__":
    main()
