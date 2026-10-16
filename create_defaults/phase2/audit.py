"""Read-only current-source audit. Requires an independently captured manifest.

This development tool does not render, discover remote files, or modify inputs.
It deliberately reuses Phase 1 extraction only for audit evidence, not runtime.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import unicodedata

from create_defaults.create_poster import ROOT, digest
from create_defaults.poster_fixtures import extract_rows, translation_file
from create_defaults.validation_manifest import fingerprint, load_manifest, text_digest, validate_manifest


def collision_key(path):
    return unicodedata.normalize("NFC", path).casefold()


def color_inventory(rows, jobs):
    """Keep literal and generator backgrounds separate from text/border/random."""
    uses = Counter(job["source"]["definition_line"] for job in jobs
                   if job["raw_parameters"].get("base_color") == job["source_row"].get("base_color"))
    assignments, excluded = [], []
    groups = defaultdict(list)
    for item in rows:
        row = item["row"]
        reference = f"create_default_posters.ps1:L{item['line']}"
        entry = {"audit_id": f"legacy-row-{item['line']}", "category": item["category"],
                 "name": row["out_name"], "source": reference, "row_sha256": fingerprint(row),
                 "effective_jobs": uses[item["line"]]}
        value = row["base_color"]
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            excluded.append(dict(entry, value=value, reason="blank/random or nonliteral; not an approved HEX assignment"))
            continue
        entry.update(hex=value.upper(), source_hex=value, approval="historical-unreviewed",
                     related_variants="jobs linked by source line; reuse is observed, not approved")
        assignments.append(entry)
        groups[entry["hex"]].append(entry)
    generated = {}
    for job in jobs:
        raw = job["raw_parameters"].get("base_color")
        if raw and re.fullmatch(r"#[0-9a-fA-F]{6}", raw) and raw != job["source_row"].get("base_color"):
            key = (job["category"], job["source"]["producer_line"], raw.upper())
            if key not in generated:
                generated[key] = {"audit_id": f"generated-{key[0]}-{key[1]}-{key[2][1:]}", "category": key[0],
                    "source": f"create_default_posters.ps1:L{key[1]}", "hex": key[2], "effective_jobs": 0,
                    "approval": "historical-unreviewed", "origin": "explicit generator/direct invocation, not a random draw"}
            generated[key]["effective_jobs"] += 1
    duplicates = [{"hex": color, "assignments": [item["audit_id"] for item in group],
                   "categories": dict(sorted(Counter(item["category"] for item in group).items())),
                   "status": "observed reuse; intent and scope require maintainer decision"}
                  for color, group in sorted(groups.items()) if len(group) > 1]
    all_groups = defaultdict(list)
    for item in [*assignments, *generated.values()]:
        all_groups[item["hex"]].append(item["audit_id"])
    return {"schema_version": 1, "identity_note": "Audit row IDs are source coordinates, not future stable poster IDs.",
            "assignments": assignments, "excluded_backgrounds": excluded, "duplicate_groups": duplicates,
            "generated_assignments": list(generated.values()),
            "all_explicit_duplicate_groups": [{"hex": color, "assignments": ids, "approval": "unreviewed"}
                                              for color, ids in sorted(all_groups.items()) if len(ids) > 1],
            "summary": {"literal_assignments": len(assignments), "distinct_hex": len(groups),
                        "global_duplicate_groups": len(duplicates),
                        "within_category_duplicate_groups": sum(n > 1 for group in duplicates for n in group["categories"].values()),
                        "excluded_literal_rows": len(excluded), "explicit_generated_groups": len(generated)},
            "intentional_reuse": "No exceptions are inferred or approved by this audit."}


def audit(manifest, structure, root=ROOT):
    root = Path(root)
    validate_manifest(manifest, assets=root)
    if structure.get("source_sha256") != digest(root / "create_default_posters.ps1"):
        raise ValueError("Structural audit is stale; inspect the current source AST again")
    rows, jobs = extract_rows(root / "create_default_posters.ps1"), manifest["jobs"]
    referenced = {name for job in jobs for name in job["assets"]}
    generated = {entry["relative"] for job in jobs for entry in job["generated_inputs"].values()}
    folders = sorted([*root.glob("logos_*"), root / "@base"], key=lambda path: path.name)
    assets = [path.relative_to(root).as_posix() for folder in folders if folder.is_dir()
              for path in sorted(folder.rglob("*")) if path.is_file()]
    overlay_operations, overlay_sources = [], set()
    for operation in manifest["overlay_operations"]:
        args = operation["arguments"]
        pattern = args[-1].removeprefix("{ASSETS}/").replace("\\", "/")
        parent = root / str(PurePosixPath(pattern).parent)
        files = sorted(path.relative_to(root).as_posix() for path in parent.iterdir()
                       if path.is_file() and path.suffix.lower() == ".png") if parent.is_dir() else []
        overlay_sources.update(files)
        overlay_operations.append({"source_line": operation["line"], "input_pattern": pattern,
            "destination": args[args.index("-path") + 1].removeprefix("{ASSETS}/").replace("\\", "/"),
            "resize_box": args[args.index("-resize") + 1], "trim": "-trim" in args,
            "matching_files": len(files), "inputs": files})
    used = referenced | overlay_sources
    groups = defaultdict(list)
    for path in assets:
        groups[collision_key(path)].append(path)
    categories = {}
    for name in sorted({job["category"] for job in jobs}):
        subset = [job for job in jobs if job["category"] == name]
        literal = [item for item in rows if item["category"] == name]
        categories[name] = {"literal_rows": len(literal), "effective_jobs": len(subset),
            "covered_literal_rows": len({job["source"]["definition_line"] for job in subset if job["source"]["definition_line"]}),
            "producer_lines": sorted({job["source"]["producer_line"] for job in subset}),
            "fonts": dict(sorted(Counter(job["font"]["path"] for job in subset).items())),
            "output_directories": sorted({str(PurePosixPath(path).parent) for job in subset for path in job["published_relatives"]}),
            "nonempty_caption_jobs": sum(bool(job["text"]) for job in subset),
            "fitted_jobs": sum(bool(job["fitting"]) for job in subset),
            "generated_input_jobs": sum(bool(job["generated_inputs"]) for job in subset),
            "random_base_jobs": sum(any("random" in note for note in job["dynamic"]["frozen_choices"]) for job in subset),
            "literal_key_names": sorted({item["row"]["key_name"] for item in literal if item["row"]["key_name"]})}
    paths = defaultdict(list)
    for job in jobs:
        for path in job["published_relatives"]:
            paths[collision_key(path)].append({"job": job["id"], "exact_path": path})
    missing, inactive = [], []
    for path, sha in manifest["asset_hashes"].items():
        if sha is not None or path in generated:
            continue
        consumers = [job for job in jobs if path in job["assets"]]
        active = any(job["parameters"]["logo"] == path or
                     (job["parameters"]["avg_color"] and job["parameters"]["avg_color_image"] == path)
                     for job in consumers)
        (missing if active else inactive).append(path)
    audit_data = {"schema_version": 1, "scope": "Fresh English AST capture; no new image rendering or multilingual parity claimed",
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root.parent, text=True).strip(),
        "manifest_sha256": manifest["sha256"], "source_sha256": manifest["source_hashes"],
        "source_text_sha256": manifest["source_text_hashes"], "capture_harness_sha256": manifest["capture_harness_sha256"],
        "translation": {"path": "@translations/en.yml or bundled fixtures/english/en.yml", "sha256": digest(translation_file(root))},
        "supported_languages": structure["supported_languages"],
        "available_languages": sorted(path.stem for path in (root / "@translations").glob("*.yml")),
        "functions": [{"category": item["category"], "line": item["line"]} for item in structure["functions"]],
        "aliases": structure["aliases"], "all_dispatch": structure["all_dispatch"],
        "summary": {"literal_rows": len(rows), "covered_literal_rows": manifest["covered_literal_definitions"],
            "effective_jobs": len(jobs), "categories": len(categories), "fonts": len(manifest["fonts"]),
            "generated_input_jobs": sum(bool(job["generated_inputs"]) for job in jobs),
            "overlay_operations": len(overlay_operations), "overlay_unique_source_files": len(overlay_sources),
            "overlay_file_transforms": sum(item["matching_files"] for item in overlay_operations),
            "jobs_without_final_virtual_path": len(manifest["jobs_without_final_virtual_path"])},
        "categories": categories, "fonts": manifest["fonts"], "overlays": overlay_operations,
        "assets": {"source_files": len(assets), "by_folder": dict(sorted(Counter(path.split('/')[0] for path in assets).items())),
            "by_suffix": dict(sorted(Counter(PurePosixPath(path).suffix.lower() for path in assets).items())),
            "unassigned_candidates": sorted(set(assets) - used),
            "note": "Unassigned means not consumed by this English poster/overlay capture, not safe to delete or necessarily a new poster.",
            "unexpected_non_png": [path for path in assets if PurePosixPath(path).suffix.lower() != ".png"],
            "missing_inputs": sorted(missing), "inactive_missing_inputs": sorted(inactive),
            "case_unicode_collisions": [group for group in groups.values() if len(group) > 1]},
        "outputs": {"final_path_count": len(paths), "path_collisions": [group for group in paths.values() if len(group) > 1],
            "same_queue_collisions": manifest["same_queue_output_collisions"],
            "no_final_virtual_path": [{"job": job["id"], "name": job["name"], "category": job["category"],
                                      "source": job["source"]} for job in jobs if not job["published_relatives"]]},
        "normalized_bulk_sha256": text_digest(root / "create_default_posters.ps1")}
    historical = load_manifest(root / "fixtures/effective-jobs-en-cmap-compat.json.gz")
    material = ("category", "parameters", "source_row", "effective_source_row", "published_relatives", "font", "generated_inputs")
    changes = []
    for index in range(max(len(jobs), len(historical["jobs"]))):
        before = historical["jobs"][index] if index < len(historical["jobs"]) else None
        after = jobs[index] if index < len(jobs) else None
        fields = [key for key in material if before is None or after is None or before[key] != after[key]]
        if fields:
            changes.append({"index": index, "old_name": before["name"] if before else None,
                            "new_name": after["name"] if after else None, "fields": fields})
    audit_data["historical_comparison"] = {"manifest_sha256": historical["sha256"],
        "mode": "positional captured-invocation material-field comparison; not image parity",
        "historical_jobs": len(historical["jobs"]), "current_jobs": len(jobs), "changed_jobs": changes}
    return audit_data, color_inventory(rows, jobs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--structure", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--replace-evidence", action="store_true", help="Explicitly replace only this tool's generated JSON reports")
    parser.add_argument("--examples", type=Path, help="Also export selected current capture jobs for the YAML examples")
    args = parser.parse_args(argv)
    manifest = load_manifest(args.manifest)
    result, colors = audit(manifest, json.loads(args.structure.read_text(encoding="utf-8-sig")))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports = [("current-source-audit.json", result), ("historical-colors.json", colors)]
    if args.examples:
        from .definitions import validate_file
        reports.append(("sample-manifest.json", sample_manifest(validate_file(args.examples), manifest, result["source_commit"])))
    if not args.replace_evidence and any((args.output_dir / name).exists() for name, _ in reports):
        raise FileExistsError("Audit reports already exist; use a fresh directory or --replace-evidence")
    for name, value in reports:
        destination = args.output_dir / name
        with destination.open("w" if args.replace_evidence else "x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=True, sort_keys=True, indent=2)
            stream.write("\n")
    print(json.dumps({"audit": result["summary"], "colors": colors["summary"]}, indent=2))
    return 0


def sample_manifest(definitions, capture, commit):
    """Export measured capture evidence, not a Python replacement planner."""
    from .definitions import schema_check
    renderer = {"composer_text_sha256": capture["source_text_hashes"]["create_poster.py"],
                "text_engine_text_sha256": capture["source_text_hashes"]["poster_text.py"],
                "encoding": {"format": "JPEG", "quality": 100, "subsampling": 0}}
    result = {"schema_version": 1, "scope": "package-a-capture-sample-not-rendered",
        "source": {"commit": commit, "bulk_text_sha256": capture["source_text_hashes"]["create_default_posters.ps1"],
                   "capture_sha256": capture["sha256"], "translation_sha256": capture["translation"]["sha256"]},
        "renderer": renderer, "jobs": []}
    for item in definitions:
        candidates = [job for job in capture["jobs"] if job["source"]["definition_line"] == item["source"]["line"]]
        if len(candidates) != 1 or fingerprint(candidates[0]["source_row"]) != item["source"]["row_sha256"]:
            raise ValueError("Sample must identify exactly one unchanged current capture job")
        job = candidates[0]
        if len(job["published_relatives"]) != 1 or job["generated_inputs"]:
            raise ValueError("Sample exporter does not expand dependent jobs or ambiguous outputs")
        effective = dict(job["parameters"], font=job["font"]["path"])
        inputs = dict(capture["asset_hashes"], **{job["font"]["path"]: job["font"]["sha256"]})
        needed = {"transparent.png", *("fades/" + name for name in
                  ("@none.png", "@center-out-fade.png", "@bottom-up-fade.png", "@top-down-fade.png", "@bottom-top-fade.png")),
                  *job["assets"], job["font"]["path"]}
        entry = {"poster_id": item["id"], "language": job["language"], "variant": "base", "legacy_job_id": job["id"],
            "definition": {"line": item["source"]["line"], "producer_line": job["source"]["producer_line"], "row_sha256": item["source"]["row_sha256"]},
            "effective": effective, "canvas": job["canvas"],
            "inputs": [{"path": path, "sha256": inputs[path]} for path in sorted(needed)],
            "local_relative": "defaults-en/" + job["published_relatives"][0], "remote_relative": job["published_relatives"][0]}
        entry["spec_sha256"] = fingerprint({key: entry[key] for key in ("language", "effective", "canvas", "inputs")} | {"renderer": renderer})
        result["jobs"].append(entry)
    schema_check(result, "manifest-v1.schema.json")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
