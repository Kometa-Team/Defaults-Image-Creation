"""Measured calibration, font impact, and manifest CLI; no approval commands."""
import argparse
from collections import Counter, defaultdict
from dataclasses import replace
import json
from pathlib import Path
import statistics

from PIL import Image, ImageDraw

from .common import BulkError, confined, fingerprint, sha256
from .config import ROOT
from .library_publication import batch_plan, publication_manifest
from .library_sources import (check_seal, load_json, published_file, reference, save, sealed)
from .library_sync import FONT_REPLACEMENTS, deterministic_samples, font_history, font_impacts, gallery
from .library_visual import compare_images, evaluate, geometry_diagnostics


def font_matrix(root):
    from create_defaults.poster_fixtures import font_inventory
    data = reference("english")
    history = font_history()
    impacts = font_impacts(data["rows"])
    metadata = {Path(item["file"]).name: item for item in font_inventory([]) if item.get("file")}
    grouped = defaultdict(list)
    for row in data["rows"]:
        job = row["job"]
        if job["remote_relative"]:
            grouped[job["parameters"]["font"]].append(row)
    result = []
    for font, rows in sorted(grouped.items()):
        name = Path(font).name
        font_metadata = metadata[name]
        record = {k: font_metadata[k] for k in ("sha256", "family", "copyright", "license_status", "license_metadata", "license_evidence", "provenance_warning") if k in font_metadata}
        rendered = [r for r in rows if r["job"]["parameters"]["text"]]
        original, evidence = FONT_REPLACEMENTS.get(font, (font, None))
        members = [{"destination": r["job"]["remote_relative"], "caption": r["job"]["parameters"]["text"],
                    "font_size": r["job"]["parameters"]["font_size"], "layout_risks": r["validation"]["diagnostic_codes"],
                    "background_color": r["job"]["parameters"]["base_color"],
                    "sha256": r["receipt"]["sha256"], "render_fingerprint": r["job"]["render_fingerprint"]} for r in rows]
        result.append({"original_font": original, "replacement_font": font, "source_license": record,
                       "public_destinations": len(rows), "rendered_caption_destinations": len(rendered),
                       "categories": dict(Counter(history[r["job"]["remote_relative"]]["category"] for r in rows)),
                       "font_selection_decision": evidence or "unchanged bundled family; no substitution inferred",
                       "decision_evidence_sha256": sha256(ROOT / evidence) if evidence else None,
                       "layout_acceptance": "Not inherited from font selection",
                       "caption_lengths": {"minimum": min(len(r["caption"]) for r in members), "maximum": max(len(r["caption"]) for r in members)},
                       "font_sizes": sorted({r["font_size"] for r in members}),
                       "non_ascii_characters": sorted({c for r in members for c in r["caption"] if ord(c) > 127}),
                       "missing_caption_characters": sorted({c for r in members for c in r["caption"] if not c.isspace() and ord(c) not in font_metadata["supported_codepoints"]}),
                       "members": members, "samples": deterministic_samples(members)})
    replacement_impacts = []
    public = [r for r in data["rows"] if r["job"]["remote_relative"]]
    for font, (original, evidence) in FONT_REPLACEMENTS.items():
        affected = [r for r in public if font in impacts[r["job"]["id"]]["all_fonts"]]
        replacement_impacts.append({"original_font": original, "replacement_font": font,
            "evidence": evidence, "evidence_sha256": sha256(ROOT / evidence),
            "direct_public_destinations": sum(font in impacts[r["job"]["id"]]["direct_fonts"] for r in affected),
            "inherited_public_destinations": sum(font in impacts[r["job"]["id"]]["inherited_fonts"] for r in affected),
            "total_affected_public_destinations": len(affected),
            "members": [{"destination": r["job"]["remote_relative"], "sha256": r["receipt"]["sha256"],
                         "font_migration": impacts[r["job"]["id"]]} for r in affected]})
    report = sealed({"schema_version": 1, "public_destinations": sum(r["public_destinations"] for r in result),
                     "fonts": result, "replacement_impacts": replacement_impacts, "approval_granted": False})
    save(Path(root) / "font-impact-matrix.json", report)
    return report


def calibration(root, output, local_published):
    """Seven accepted historical comparisons, current samples, and real controls."""
    from create_defaults.create_poster import PosterOptions, create_poster
    root = Path(root)
    state = check_seal(load_json(root / "production-snapshot.json"))
    policy = load_json(root / "proposed-tolerance-policy.json")
    data = reference("english")
    impacts = font_impacts(data["rows"])
    by_path = {r["job"]["remote_relative"]: r for r in data["rows"]}
    canary = check_seal(load_json(ROOT / "bulk/evidence/english-canary/preparation-20261017.json"))
    positive, current = [], []
    calibration_root = root / "calibration"
    calibration_root.mkdir(exist_ok=True)
    for accepted in canary["rows"]:
        job = by_path[accepted["destination"]]["job"]
        candidate = confined(output, job["local_relative"], must_exist=True)
        backup = confined(ROOT.parent / "config/english-canary/preparation-20261017-v1", accepted["published"]["local_verified_backup"], must_exist=True)
        if sha256(candidate) != accepted["sha256"] or sha256(backup) != accepted["published"]["sha256"]:
            raise BulkError("calibration_identity", "Accepted candidate or original published backup changed")
        metrics = compare_images(candidate, backup, job["parameters"])
        metrics["geometry"] = geometry_diagnostics(candidate, backup, job["parameters"])
        positive.append({"destination": accepted["destination"], "candidate_sha256": sha256(candidate),
            "published_sha256": sha256(backup), "metrics": metrics, "screen": evaluate(metrics, policy),
            "font_migration": impacts[job["id"]],
            "in_renderer_equivalence_scope": not bool(impacts[job["id"]]["all_fonts"]),
            "evidence": "Exact individually accepted canary vs retained original published bytes"})
    entries = {r["path"]: r for r in state["entries"]}
    history = font_history()
    category_samples = {}
    for row in data["rows"]:
        job = row["job"]
        destination = job["remote_relative"]
        if destination:
            category_samples.setdefault(history[destination]["category"], row)
    gallery_rows = []
    for category, row in sorted(category_samples.items()):
        job, receipt = row["job"], row["receipt"]
        entry = entries.get(job["remote_relative"])
        if not entry:
            continue
        candidate = confined(output, job["local_relative"], must_exist=True)
        if sha256(candidate) != receipt["sha256"]:
            raise BulkError("candidate_hash", "Calibration candidate differs from ledger")
        published, provenance = published_file(root, state, entry, local_published)
        metrics = compare_images(candidate, published, job["parameters"])
        metrics["geometry"] = geometry_diagnostics(candidate, published, job["parameters"])
        record = {"destination": job["remote_relative"], "category": category, "font": job["parameters"]["font"],
            "caption": job["parameters"]["text"], "candidate_sha256": sha256(candidate), "published_sha256": sha256(published),
            "candidate_path": str(candidate), "published_path": str(published), "published_provenance": provenance,
            "metrics": metrics, "screen": evaluate(metrics, policy)}
        current.append(record)
        gallery_rows.append(record)
    # Preserve the generator and change explicit inputs/options for font/text/logo controls.
    selected = next(r for r in data["rows"] if r["job"]["remote_relative"] == "genre/Action & Adventure.jpg")
    job = selected["job"]
    original = confined(output, job["local_relative"], must_exist=True)
    parameters = dict(job["parameters"])
    parameters["font"] = str(confined(ROOT, parameters["font"], must_exist=True))
    parameters["logo"] = str(confined(ROOT, parameters["logo"], must_exist=True))
    options = PosterOptions(**parameters)
    negative = []
    from .planner import renderer_identity
    control_context = fingerprint({"render_fingerprint": job["render_fingerprint"],
        "renderer": renderer_identity(), "implementation": sha256(Path(__file__))})
    controls_root = calibration_root / "controls" / control_context
    controls_root.mkdir(parents=True, exist_ok=True)
    for name in ("wrong_font", "changed_text", "missing_logo", "clipped_caption", "positional_shift", "incorrect_color", "corrupt_graphic", "incorrect_aspect_ratio"):
        target = controls_root / (name + ".jpg")
        receipt_path = target.with_suffix(".json")
        reuse = target.exists()
        if reuse:
            receipt = check_seal(load_json(receipt_path))
            if receipt["context"] != control_context or receipt["sha256_image"] != sha256(target):
                raise BulkError("corrupt_control", "Negative control no longer matches its generation receipt")
        elif name in {"wrong_font", "changed_text", "missing_logo", "clipped_caption", "incorrect_color"}:
            changes = {
                "wrong_font": {"font": str(ROOT / "fonts/BebasNeue-Regular.ttf")},
                "changed_text": {"text": "WRONG TITLE"},
                "missing_logo": {"logo": str(ROOT / "transparent.png")},
                "clipped_caption": {"text_offset": 1500},
                "incorrect_color": {"base_color": "#00FF00"},
            }[name]
            create_poster(replace(options, **changes), output_path=target, asset_dir=ROOT, font_dir=ROOT / "fonts")
        elif not reuse:
            with Image.open(original) as image:
                image.load()
                if name == "positional_shift":
                    shifted = Image.new("RGB", image.size, "black")
                    shifted.paste(image, (15, 0))
                    image = shifted
                elif name == "corrupt_graphic":
                    ImageDraw.Draw(image).rectangle((500, 400, 1500, 1200), fill="magenta")
                else:
                    image = image.resize((1800, 3000))
                image.save(target, quality=100, subsampling=0)
        if not reuse:
            save(receipt_path, sealed({"context": control_context, "control": name, "sha256_image": sha256(target)}))
        metrics = compare_images(target, original, job["parameters"])
        metrics["geometry"] = geometry_diagnostics(target, original, job["parameters"])
        negative.append({"control": name, "candidate_sha256": sha256(target), "reference_sha256": sha256(original),
                         "metrics": metrics, "screen": evaluate(metrics, policy),
                         "defect_missed": evaluate(metrics, policy)["screen_pass"]})
        gallery_rows.append({"destination": "negative-control/" + name, "category": "negative-controls", "font": "control",
            "candidate_path": str(target), "published_path": str(original), "metrics": metrics})
    def distribution(rows):
        values = sorted(r["metrics"]["rgb_mae"] for r in rows if r["metrics"].get("same_dimensions"))
        return {"count": len(values), "minimum": min(values), "median": statistics.median(values), "maximum": max(values)}
    result = sealed({"schema_version": 1, "policy": policy, "policy_sha256": fingerprint(policy),
        "known_accepted_positives": positive, "current_category_samples": current, "negative_controls": negative,
        "accepted_positive_distribution": distribution(positive), "current_sample_distribution": distribution(current),
        "accepted_positive_rejected": sum(not r["screen"]["screen_pass"] for r in positive),
        "in_scope_accepted_positive_count": sum(r["in_renderer_equivalence_scope"] for r in positive),
        "in_scope_accepted_positive_rejections": sum(r["in_renderer_equivalence_scope"] and not r["screen"]["screen_pass"] for r in positive),
        "font_migration_positive_count": sum(not r["in_renderer_equivalence_scope"] for r in positive),
        "defective_controls_missed": sum(r["defect_missed"] for r in negative),
        "policy_approved": False, "limitations": "Sample calibration only; no universal visual guarantee, no automatic approval"})
    save(root / "tolerance-calibration.json", result)
    groups = [{"lane": "calibration", "category": r["category"], "font": r["font"],
               "membership_sha256": fingerprint(r["destination"]), "samples": [{"destination": r["destination"], "reasons": ["measured calibration sample"]}]} for r in gallery_rows]
    gallery(calibration_root, gallery_rows, groups)
    return result


def overlay_calibration(root):
    """Keep overlay thresholds separate; existing decisions remain exact exceptions."""
    from .library_publication import retained_overlay_decisions
    from .library_visual import PROPOSED_POLICY
    from copy import deepcopy
    root = Path(root)
    inventory = check_seal(load_json(root / "overlays-inventory.json"))
    retained = retained_overlay_decisions(inventory)
    policy = deepcopy(PROPOSED_POLICY)
    policy.update(version="overlay-library-tolerance-proposal-v1",
                  scope="unchanged overlay source, transformation, profile and placement; individually approved exceptions retained")
    policy["thresholds"].update(rgb_mae=3.0, p99=32, changed_gt16=.1,
                                minimum_global_ssim=.98, region_mae=4.0, edge_mae=6.0, alpha_mae=1.5)
    positives = [r for r in inventory["rows"] if r["destination"] in retained]
    evaluated = [{"destination": r["destination"], "screen": evaluate(r["metrics"], policy)} for r in positives]
    reference_row = max(positives, key=lambda r: r["candidate_bytes"])
    original = Path(reference_row["candidate_path"])
    directory = root / "overlay-calibration"
    directory.mkdir(exist_ok=True)
    negatives = []
    for name in ("missing_graphic", "wrong_color", "clipped_graphic", "shifted_graphic", "wrong_alpha", "incorrect_aspect_ratio", "corrupted_graphic"):
        with Image.open(original) as source:
            source.load()
            altered = source.convert("RGBA")
        if name == "missing_graphic":
            altered = Image.new("RGBA", altered.size)
        elif name == "wrong_color":
            from PIL import ImageOps
            color = ImageOps.invert(altered.convert("RGB"))
            color.putalpha(altered.getchannel("A"))
            altered = color
        elif name in {"clipped_graphic", "shifted_graphic"}:
            moved = Image.new("RGBA", altered.size)
            if name == "clipped_graphic":
                moved.paste(altered.crop((0, 0, altered.width // 2, altered.height)), (0, 0))
            else:
                moved.paste(altered, (8, 0))
            altered = moved
        elif name == "wrong_alpha":
            altered.putalpha(altered.getchannel("A").point(lambda p: p // 2))
        elif name == "incorrect_aspect_ratio":
            altered = altered.resize((max(1, altered.width * 4 // 5), altered.height))
        else:
            ImageDraw.Draw(altered).rectangle((altered.width // 4, altered.height // 4,
                altered.width * 3 // 4, altered.height * 3 // 4), fill="magenta")
        path = directory / (name + ".png")
        altered.save(path)
        metrics = compare_images(path, reference_row["published_path"])
        screen = evaluate(metrics, policy)
        negatives.append({"control": name, "sha256": sha256(path), "metrics": metrics,
                          "screen": screen, "defect_missed": screen["screen_pass"]})
    measured = [r for r in inventory["rows"] if r.get("metrics")]
    from .overlays import CATALOG
    catalog = load_json(CATALOG)
    source_profiles = []
    for relative in sorted({p for group in catalog["groups"] for p in group["inputs"]}):
        path = confined(ROOT, relative, must_exist=True)
        with Image.open(path) as image:
            source_profiles.append({"path": relative, "mode": image.mode,
                "icc_profile": bool(image.info.get("icc_profile")), "sha256": sha256(path)})
    report = sealed({"schema_version": 1, "policy": policy, "policy_sha256": fingerprint(policy),
        "retained_exact_samples": len(retained), "known_accepted_evaluation": evaluated,
        "known_accepted_screen_rejections": sum(not r["screen"]["screen_pass"] for r in evaluated),
        "negative_controls": negatives, "defective_controls_missed": sum(r["defect_missed"] for r in negatives),
        "measured_population": len(measured), "proposed_screen_passes": sum(evaluate(r["metrics"], policy)["screen_pass"] for r in measured),
        "source_modes": dict(Counter(r["mode"] for r in source_profiles)),
        "sources_with_icc": sum(r["icc_profile"] for r in source_profiles),
        "grayscale_alpha_sources": [r for r in source_profiles if r["mode"] == "LA"],
        "source_profile_inventory_sha256": fingerprint(source_profiles),
        "policy_approved": False, "note": "Proposal only. Individually accepted artifacts retain exact decisions; other candidates require policy/group approval."})
    save(root / "proposed-overlay-tolerance-policy.json", policy)
    save(root / "overlay-tolerance-calibration.json", report)
    save(root / "overlay-source-profiles.json", sealed({"sources": source_profiles}))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("fonts")
    p.add_argument("--root", type=Path, required=True)
    p = commands.add_parser("calibrate")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--local-published", type=Path, required=True)
    p = commands.add_parser("calibrate-overlays")
    p.add_argument("--root", type=Path, required=True)
    p = commands.add_parser("plan")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--approvals", type=Path, nargs="*", default=[])
    p.add_argument("--max-files", type=int, default=300)
    p.add_argument("--max-bytes", type=int, default=200 * 1024 ** 2)
    args = parser.parse_args(argv)
    if args.command == "fonts":
        result = font_matrix(args.root)
        print(json.dumps({"fonts": len(result["fonts"]), "public_destinations": result["public_destinations"]}))
    elif args.command == "calibrate":
        result = calibration(args.root, args.output, args.local_published)
        print(json.dumps({k: result[k] for k in ("accepted_positive_distribution", "accepted_positive_rejected", "defective_controls_missed")}))
    elif args.command == "calibrate-overlays":
        result = overlay_calibration(args.root)
        print(json.dumps({k: result[k] for k in ("retained_exact_samples", "known_accepted_screen_rejections", "defective_controls_missed", "proposed_screen_passes")}))
    else:
        report = check_seal(load_json(args.inventory))
        candidates = [args.root / "proposed-tolerance-policy.json", args.root / "proposed-overlay-tolerance-policy.json"]
        policies = [load_json(p) for p in candidates if p.exists()]
        policy = next((p for p in policies if fingerprint(p) == report["policy_sha256"]), None)
        if policy is None:
            raise BulkError("stale_policy", "No exact policy for the supplied inventory")
        manifest = publication_manifest(report, policy, [load_json(p) for p in args.approvals])
        plan = batch_plan(manifest, max_files=args.max_files, max_bytes=args.max_bytes)
        save(args.root / (report["kind"] + "-publication-manifest.json"), manifest)
        save(args.root / (report["kind"] + "-git-batch-plan.json"), plan)
        print(json.dumps({"eligible_replacements": len(manifest["members"]), "withheld": len(manifest["withheld"]), "batches": len(plan["batches"])}))


if __name__ == "__main__":
    main()
