"""Local migration gate: real worker posters versus the approved Python API.

This does not claim fresh ImageMagick parity or human visual approval. Images and
databases stay below ignored config/; only the small evidence summary is tracked.
"""

import argparse
import html
import json
from pathlib import Path
import time

from create_defaults.create_poster import PosterOptions, create_poster
from .common import BulkError, atomic_bytes, canonical, confined, fingerprint, sha256
from .config import Config, ROOT
from .definitions import Definition, load_definitions
from .generation import generate
from .migration import CATALOG, definition_for, legacy, legacy_destination, reconcile
from .generators import GENERATORS
from .translations import Translations
from .workers import WorkerLimits


def write_comparison_html(root, category, comparisons, *, replace=False):
    entries = []
    for item in comparisons:
        identity = "poster." + fingerprint({"poster_id": item["poster_id"], "language": "en", "variant": "base"})[:24]
        actual = "output/defaults-en/" + item["output"]
        reference = "reference/" + identity + ".jpg"
        entries.append(f'<h2>{html.escape(item["output"])}</h2><div class="pair"><figure><figcaption>Persistent worker</figcaption><img src="{html.escape(actual)}" alt="Worker poster"></figure><figure><figcaption>Approved Pillow reference</figcaption><img src="{reference}" alt="Reference poster"></figure></div>')
    page = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(category) + ' migration comparison</title><style>body{font:16px Arial;background:#fff;color:#222;margin:24px}.pair{display:flex;gap:16px;flex-wrap:wrap}figure{margin:0;width:300px;max-width:100%}img{width:100%;height:auto;aspect-ratio:2/3;object-fit:contain}h2{font-size:18px;overflow-wrap:anywhere}</style><h1>' + html.escape(category) + '</h1><p>Byte-identical worker and approved Pillow samples. Human approval is not inferred.</p>' + ''.join(entries)
    atomic_bytes(root / "index.html", page.encode(), replace=replace)


def check_category(category, *, evidence_root, samples=1, generators=None, replace_summary=False):
    generators = GENERATORS if generators is None else generators
    definitions = load_definitions([CATALOG / (category.lower() + ".yml")], profiles_path=CATALOG / "profiles.yml")
    translations = Translations({"en": ROOT / "fixtures/english/en.yml"})
    from .planner import Planner
    expanded = tuple(Planner(generators=generators).expand(definitions)[0].values())
    contract = reconcile(category, expanded, translations)
    if not contract["contract_parity"]:
        raise BulkError("migration_discrepancy", json.dumps(contract))
    root = Path(evidence_root).resolve() / category.lower()
    config = Config(cache_dir=root / "cache", workspace_dir=root / "work", output_dir=root / "output")
    # A dependent sample forces the genuine parent stage; no sentinel hashes.
    choices = sorted(expanded, key=lambda item: (not bool(item.data["dependencies"]), item.id))[:samples]
    if category == "Genre":
        choices = [next(item for item in expanded if item.data["output"]["filename"] == "Splatter.jpg"), *choices]
    if category in {"Year", "Decade"}:
        choices.extend(next(item for item in expanded if item.data["output"]["filename"] == filename and not item.data["dependencies"])
                       for filename in ("1970.jpg", "2020.jpg"))
    choices = list({item.id: item for item in choices}.values())
    options = dict(config=config, limits=WorkerLimits(workers=2), generators=generators, posters=[item.id for item in choices])
    started = time.monotonic()
    cold = generate(definitions, translations, **options)
    if cold["status"] != "verified":
        raise BulkError("render_failed", json.dumps(cold))
    warm = generate(definitions, translations, **options)
    if any(stage["execution"]["metrics"]["executed"] for stage in warm["stages"]):
        raise BulkError("cache_failed", "Warm restart rendered an unchanged output")
    capture = legacy()
    originals = {legacy_destination(job): job for job in capture["jobs"] if job["category"] == category and not (category == "Genre" and job["source"]["definition_line"] == 4883)}
    structure = json.loads((ROOT / "phase2/evidence/source-structure.json").read_text(encoding="utf-8"))
    calls = next(item["translation_calls"] for item in structure["functions"] if item["category"] == category)
    paths = {job["id"]: job["published_relatives"][0] for job in capture["jobs"] if job["published_relatives"]}
    comparisons = []
    combined = {}
    for stage in cold["stages"]:
        combined.update({job["id"]: job for job in stage["manifest"]["jobs"]})
    last = dict(cold["stages"][-1]["manifest"], jobs=list(combined.values()))
    for job in last["jobs"]:
        relative = job["local_relative"].removeprefix("defaults-en/")
        original = originals[relative]
        definition = definition_for(original, translations, calls, paths)
        from .planner import effective_parameters
        parameters = effective_parameters(dict(definition["composer"], text=original["text"]))
        for role in ("logo", "font", "avg_color_image"):
            if parameters[role]:
                base = config.output_dir if any(item["input"] == role for item in definition["dependencies"]) else config.asset_dir
                parameters[role] = str(confined(base, parameters[role], must_exist=True))
        reference = root / "reference" / (job["id"] + ".jpg")
        reference.parent.mkdir(parents=True, exist_ok=True)
        metadata = create_poster(PosterOptions(**parameters), output_path=reference, asset_dir=config.asset_dir, font_dir=config.asset_dir / "fonts")
        actual = confined(config.output_dir, job["local_relative"], must_exist=True)
        identical = sha256(actual) == sha256(reference)
        comparisons.append({"poster_id": job["poster_id"], "output": relative, "sha256": sha256(actual), "reference_sha256": sha256(reference),
                            "byte_identical": identical, "composer_metadata": metadata,
                            "reference": "Fresh approved Pillow API using corrected captured parameters; generated inputs use verified Python parents"})
        if not identical:
            raise BulkError("pixel_parity_failed", f"Worker differs from direct approved API: {relative}")
    # Exercise changed-definition ownership and a subsequent fresh-pool resume.
    selected = choices[0].id
    changed = []
    for definition in expanded:
        if definition.id == selected:
            value = definition.data
            value["composer"]["base_color"] = "#123456" if value["composer"]["base_color"] != "#123456" else "#654321"
            if category == "Genre" and value["output"]["filename"] == "Splatter.jpg":
                value["composer"]["font_color"] = "#FFFFFE"
                value["composer"]["base_color"] = "#990000"
            definition = Definition.create(value)
        changed.append(definition)
    changed_run = generate(tuple(changed), translations, **dict(options, generators=None))
    restored = generate(definitions, translations, **options)
    resumed = generate(definitions, translations, **options)
    for run in (changed_run, restored, resumed):
        if run["status"] != "verified":
            raise BulkError("incremental_failed", "Changed/restored/resumed category sample did not verify")
    if any(stage["execution"]["metrics"]["executed"] for stage in resumed["stages"]):
        raise BulkError("resume_failed", "Restored restart was not a verified cache hit")
    report = dict(contract, sample_comparisons=comparisons, cold_metrics=[stage["execution"]["metrics"] for stage in cold["stages"]],
                  warm_metrics=[stage["execution"]["metrics"] for stage in warm["stages"]],
                  incremental_metrics=[stage["execution"]["metrics"] for stage in changed_run["stages"]],
                  restore_metrics=[stage["execution"]["metrics"] for stage in restored["stages"]],
                  resume_metrics=[stage["execution"]["metrics"] for stage in resumed["stages"]], wall_seconds=time.monotonic() - started,
                  status="automated_sample_passed", human_visual_approval=False,
                  evidence_directory=root.relative_to(ROOT.parent).as_posix() if root.is_relative_to(ROOT.parent) else None,
                  limitations=["Fresh direct Pillow parity, not a new legacy ImageMagick comparison", "English only; full multilingual layout belongs to D", "Representative sample, not every category output rendered"])
    atomic_bytes(root / "evidence.json", canonical(report) + b"\n")
    write_comparison_html(root, category, comparisons)
    summary = CATALOG / "audit" / (category.lower() + "-render.json")
    if replace_summary or not summary.exists():
        atomic_bytes(summary, json.dumps(report, indent=2, default=str).encode() + b"\n", replace=replace_summary)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("category", nargs="+")
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--export", action="store_true", help="Export this category immediately before its own validation gate")
    parser.add_argument("--refresh-export", action="store_true", help="Explicitly replace this category's development-generated data and audit")
    parser.add_argument("--refresh-summary", action="store_true", help="Replace the tracked summary after generating fresh evidence in a new directory")
    args = parser.parse_args(argv)
    for category in args.category:
        if args.refresh_export or (args.export and not (CATALOG / (category.lower() + ".yml")).exists()):
            from .migration import export_category
            export_category(category, replace_generated=args.refresh_export)
        result = check_category(category, evidence_root=args.evidence_root, samples=args.samples, replace_summary=args.refresh_summary)
        print(json.dumps({key: result[key] for key in ("category", "active_jobs", "status", "wall_seconds")}), flush=True)


if __name__ == "__main__":
    main()
