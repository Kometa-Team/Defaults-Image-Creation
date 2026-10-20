"""Development-only extraction/reconciliation against the corrected legacy capture.

The active catalog never reads the PowerShell source or captured job manifest.
Export one category at a time, then reconcile and render before accepting it.
"""

import argparse
import json
from pathlib import Path, PurePosixPath
import re

import yaml

from create_defaults.validation_manifest import load_manifest
from .common import BulkError, atomic_bytes, fingerprint, normalize_hex, path_key, sha256
from .config import ROOT
from .generators import GENERATORS, poster_id
from .planner import effective_parameters
from .translations import Translations


HERE = Path(__file__).resolve().parent
CATALOG = HERE / "catalog"
BASELINE = HERE / "baselines/effective-jobs-en-current.json.gz"


def legacy():
    value = load_manifest(BASELINE)
    if value["sha256"] != "968476aff980f2cbb3e0d5b870360450c723150f34f5751af9aef6dee19643ac":
        raise BulkError("changed_baseline", "Migration requires the corrected current-source capture")
    if fingerprint({key: item for key, item in value.items() if key != "sha256"}) != value["sha256"]:
        raise BulkError("changed_baseline", "Captured manifest content does not match its pinned identity")
    return value


def stable_id(category, output):
    return poster_id(category, output)


def legacy_destination(job):
    if job["published_relatives"]:
        return job["published_relatives"][0]
    if job["category"] == "Awards" and job["source"]["producer_line"] in {1912, 2226}:
        award = PurePosixPath(job["parameters"]["logo"]).stem.lower()
        return "_intermediates/award/" + award + "/" + job["name"] + ".jpg"
    raise BulkError("unmapped_intermediate", f"Unclassified overwritten intermediate: {job['id']}")


def caption_for(job, translations, calls):
    base = {"mode": "none", "key": None, "template_key": None, "text": "", "case": "upper", "direction": "auto", "fallback": None}
    if not job["text"]:
        return base
    if re.fullmatch(r"\d{4}(?:s|-2)?", job["text"]):
        return dict(base, mode="shared", text=job["text"], case="exact")
    key = (job["effective_source_row"] or {}).get("key_name", "")
    candidates = []
    for call in calls:
        if call["line"] > job["source"]["producer_line"]:
            continue
        match = re.search(r'-PropertyPath "([^"]+)"', call["expression"])
        if match:
            path = match[1].replace("$($item.key_name)", key)
            if "$" not in path:
                candidates.append(path)
    # Try the nearest source lookup first; template identity remains explicit.
    candidates = list(dict.fromkeys(reversed(candidates)))
    for path in candidates:
        for template in [None, *[item for item in candidates if item.startswith("collections.")]]:
            caption = dict(base, mode="translation", key=path, template_key=template)
            try:
                resolved = translations.resolve(caption, "en").text
            except BulkError:
                continue
            if resolved == job["text"]:
                return caption
            if job["category"] == "Awards" and job["text"].startswith(resolved + " "):
                suffix = job["text"][len(resolved):]
                if re.fullmatch(r" \d{4}(?:-2)?", suffix):
                    return dict(caption, suffix=suffix)
            if job["category"] == "ContentRating" and job["text"] in {resolved + " " + job["name"], resolved + " " + job["name"] + "+"}:
                return dict(caption, suffix=job["text"][len(resolved):])
    raise BulkError("unmapped_caption", f"No exact source translation identity for {job['id']}: {job['text']!r}")


def definition_for(job, translations, calls, paths):
    output = legacy_destination(job)
    identity = stable_id(job["category"], output)
    composer = dict(job["parameters"], font=job["font"]["path"], text="")
    composer["out_name"] = PurePosixPath(composer["out_name"].replace("\\", "/")).name
    # The legacy resolver is case-insensitive on Windows; bind the actual bundled
    # path for portable Linux rendering rather than copying misspelled aliases.
    for role in ("logo", "avg_color_image", "dom_color_image"):
        if composer[role] and role not in job["generated_inputs"]:
            matches = [path for path in job["assets"] if path.casefold() == composer[role].casefold()]
            if len(matches) != 1:
                raise BulkError("ambiguous_asset", f"Cannot bind exact asset identity: {composer[role]}")
            from .asset_cases import canonical as canonical_asset
            composer[role] = canonical_asset(matches[0])
    fitting = job["fitting"]
    measurement = None
    if fitting is not None and job["text"] and all(fitting["box"]):
        composer["font_size"] = fitting["point_size"]
        measurement = {"text": job["text"], "font_sha256": job["font"]["sha256"], "point_size": fitting["point_size"],
                       "box": fitting["box"], "minimum": fitting["minimum"], "maximum": fitting["maximum"], "evidence_sha256": job["sha256"]}
    dependencies = []
    for role, parent in job["generated_inputs"].items():
        parent_output = paths[parent["job_id"]]
        dependencies.append({"poster_id": stable_id(job["category"], parent_output), "input": role})
        composer[role] = "defaults-en/" + parent_output
    source = {"path": "create_default_posters.ps1", "line": job["source"]["definition_line"] or job["source"]["producer_line"],
              "row_sha256": fingerprint(job["source_row"])}
    return {"id": identity, "category": job["category"], "display_name": job["name"], "source": source,
            "composer": composer, "caption": caption_for(job, translations, calls),
            "layout": {"kind": "captured_fit" if measurement else "fixed", "measurement": measurement},
            "languages": ["en"], "applicability": {"en": {"status": "applicable", "reason": "English current-source migration; complete multilingual preflight deferred to Package D"}},
            "output": {"directory": str(PurePosixPath(output).parent) if "/" in output else "",
                       "filename": PurePosixPath(output).name, "remote_paths": {"en": output if job["published_relatives"] else None}},
            "dependencies": dependencies, "overrides": [], "generator": None,
            "color_assignment": {"id": identity + ".background", "origin": "template" if job["category"] == "Separators" and job["dynamic"]["color_loop"] else "historical", "parent": None, "relationship": None, "exception": None}}


def differences(base, value):
    """Readable one-layer profile overrides; lists are intentional replacements."""
    return {key: differences(base[key], item) if isinstance(item, dict) and isinstance(base.get(key), dict) else item
            for key, item in value.items() if key not in base or item != base[key]}


def compress_generators(definitions, jobs):
    groups, retained = {}, []
    for value, job in zip(definitions, jobs, strict=True):
        kind = None
        if job["generated_inputs"]:
            kind = "best-of-years"
            key = (kind, job["source"]["producer_line"])
        elif job["category"] == "Awards" and re.fullmatch(r"\d{4}", job["name"]):
            kind = "award-years"
            key = (kind, job["source"]["producer_line"])
        elif job["category"] == "Separators" and job["dynamic"]["color_loop"]:
            kind = "separator-variants"
            key = (kind, job["source"]["definition_line"])
        elif job["category"] == "ContentRating" and value["caption"]["key"] in {"key_names.age", "key_names.RATED"}:
            kind = "content-rating-series"
            key = (kind, job["source"]["producer_line"])
        if kind:
            groups.setdefault(key, []).append((value, job))
        else:
            retained.append(value)
    for (kind, _), entries in groups.items():
        base = json.loads(json.dumps(entries[0][0]))
        directory = base["output"]["directory"]
        identity = {"category": base["category"], "directory": directory if kind != "separator-variants" else "separators",
                    "caption": base["caption"]["key"], "name": base["composer"]["out_name"] if kind == "separator-variants" else kind}
        base["id"] = base["category"].lower() + ".series." + fingerprint(identity)[:24]
        base["color_assignment"]["id"] = base["id"] + ".background"
        if kind == "content-rating-series":
            parameters = {"values": [job["name"] for _, job in entries], "directory": directory,
                          "caption_suffix": "+" if base["caption"]["key"] == "key_names.age" else "",
                          "measurements": {job["name"]: {key: value["layout"]["measurement"][key] for key in ("point_size", "evidence_sha256")} for value, job in entries}}
        elif kind == "separator-variants":
            parameters = {"filename": base["output"]["filename"], "variants": [
                {"name": job["dynamic"]["color_loop"], "base_color": value["composer"]["base_color"],
                 "evidence_sha256": value["layout"]["measurement"]["evidence_sha256"]} for value, job in entries]}
        else:
            years = sorted(int(job["name"]) for _, job in entries)
            step = 10 if base["category"] == "Decade" else 1
            if years != list(range(years[0], years[-1] + step, step)):
                raise BulkError("unmapped_range", "Year series has gaps requiring an explicit migration decision")
            parameters = {"start": years[0], "stop": years[-1] + step, "step": step, "directory": directory,
                          "measurements": {job["name"]: {key: value["layout"]["measurement"][key] for key in ("point_size", "evidence_sha256")} for value, job in entries}}
            if kind == "best-of-years":
                parameters["parent_directory"] = str(PurePosixPath(entries[0][1]["generated_inputs"]["logo"]["relative"]).parent)
        base["generator"] = {"name": kind, "version": 1, "parameters": parameters}
        retained.append(base)
    return retained


def export_category(category, *, replace_generated=False):
    capture = legacy()
    jobs = [item for item in capture["jobs"] if item["category"] == category]
    if not jobs:
        raise BulkError("unknown_category", category)
    translations = Translations({"en": ROOT / "fixtures/english/en.yml"})
    structure = json.loads((ROOT / "phase2/evidence/source-structure.json").read_text(encoding="utf-8"))
    calls = next(item["translation_calls"] for item in structure["functions"] if item["category"] == category)
    paths = {job["id"]: job["published_relatives"][0] for job in capture["jobs"] if job["published_relatives"]}
    definitions, active_jobs, audit, retired = [], [], [], []
    for job in jobs:
        if category == "Genre" and job["source"]["definition_line"] == 4883:
            retired.append({"legacy_id": job["id"], "line": 4883, "reason": "D02: unintended green Splatter; red line 4884 is authoritative", "sha256": job["sha256"]})
            continue
        value = definition_for(job, translations, calls, paths)
        definitions.append(value)
        active_jobs.append(job)
        audit.append({"poster_id": value["id"], "legacy_id": job["id"], "job_sha256": job["sha256"], "source": job["source"],
                      "row_sha256": fingerprint(job["source_row"]), "frozen_choices": job["dynamic"]["frozen_choices"]})
    # One shared complete profile holds defaults; only explicit differences live
    # in per-category files. Identities/provenance are never inherited.
    profile = {key: value for key, value in definitions[0].items() if key not in {"id", "category", "display_name", "source", "generator", "color_assignment", "output"}}
    profile["composer"] = dict(profile["composer"], logo="transparent.png", out_name="poster", base_color="#FFFFFF", font_size=250)
    profile["caption"] = {"mode": "none", "key": None, "template_key": None, "text": "", "case": "upper", "direction": "auto", "fallback": None}
    profile["layout"] = {"kind": "fixed", "measurement": None}
    profile["dependencies"] = []
    profile_path = CATALOG / "profiles.yml"
    if profile_path.exists():
        from .common import load_yaml
        profile = load_yaml(profile_path)["profiles"]["legacy-poster"]
    else:
        atomic_bytes(profile_path, yaml.safe_dump({"schema_version": 1, "profiles": {"legacy-poster": profile}}, sort_keys=False).encode())
    compact = [{"extends": "legacy-poster", **differences(profile, value)} for value in compress_generators(definitions, active_jobs)]
    path = CATALOG / (category.lower() + ".yml")
    atomic_bytes(path, yaml.safe_dump({"schema_version": 1, "category": category, "definitions": compact}, sort_keys=False, allow_unicode=False).encode(), replace=replace_generated)
    atomic_bytes(CATALOG / "audit" / (category.lower() + ".json"), json.dumps({"baseline_sha256": capture["sha256"], "active": audit, "retired": retired}, indent=2).encode() + b"\n", replace=replace_generated)
    return definitions


def reconcile(category, definitions, translations):
    """Compare all resolved render contracts, without inventing parent hashes."""
    capture = legacy()
    expected = {legacy_destination(job): job for job in capture["jobs"] if job["category"] == category and not (category == "Genre" and job["source"]["definition_line"] == 4883)}
    discrepancies, seen, path_keys, hashes = [], set(), set(), {}
    for definition in definitions:
        item = definition.data
        output = "/".join(filter(None, (item["output"]["directory"], item["output"]["filename"])))
        if path_key(output) in path_keys:
            discrepancies.append({"output": output, "field": "duplicate_output"})
        seen.add(output)
        path_keys.add(path_key(output))
        job = expected.get(output)
        if job is None:
            discrepancies.append({"output": output, "field": "extra_output"})
            continue
        actual = effective_parameters(dict(item["composer"], text=translations.resolve(item["caption"], "en").text))
        original = effective_parameters(dict(job["parameters"], font=job["font"]["path"]))
        for field in ("base_color", "font_color", "border_color"):
            original[field] = normalize_hex(original[field])
        original["out_name"] = PurePosixPath(original["out_name"].replace("\\", "/")).name
        for role in ("logo", "avg_color_image", "dom_color_image"):
            if role in job["generated_inputs"]:
                original[role] = "defaults-en/" + original[role]
            elif original[role]:
                from .asset_cases import canonical as canonical_asset
                original[role] = canonical_asset(next(path for path in job["assets"] if path.casefold() == original[role].casefold()))
        for field in original:
            if actual[field] != original[field]:
                discrepancies.append({"output": output, "field": field, "expected": original[field], "actual": actual[field]})
        for path, checksum in {**job["assets"], job["font"]["path"]: job["font"]["sha256"]}.items():
            if checksum is not None:
                if path not in hashes:
                    from .asset_cases import historical
                    hashes[path] = sha256(historical(ROOT, path, checksum))
                if hashes[path] != checksum:
                    discrepancies.append({"output": output, "field": "source_asset_sha256", "path": path})
        expected_dependencies = [{"poster_id": stable_id(category, parent["relative"]), "input": role} for role, parent in job["generated_inputs"].items()]
        if item["dependencies"] != expected_dependencies:
            discrepancies.append({"output": output, "field": "generated_parent_relationship"})
        fitting = job["fitting"]
        if fitting and job["text"] and all(fitting["box"]):
            measurement = item["layout"]["measurement"]
            expected_fit = {"text": job["text"], "font_sha256": job["font"]["sha256"], "point_size": fitting["point_size"],
                            "box": fitting["box"], "minimum": fitting["minimum"], "maximum": fitting["maximum"], "evidence_sha256": job["sha256"]}
            if measurement != expected_fit:
                discrepancies.append({"output": output, "field": "captured_fitting"})
    discrepancies.extend({"output": path, "field": "missing_output"} for path in sorted(set(expected) - seen))
    return {"schema_version": 1, "category": category, "baseline_sha256": capture["sha256"], "definitions": len(definitions),
            "legacy_effective_jobs": sum(job["category"] == category for job in capture["jobs"]), "active_jobs": len(definitions),
            "discrepancies": discrepancies, "contract_parity": not discrepancies,
            "normalizations": ["HEX letter case only", "Bind actual bundled asset/font paths instead of Windows case-insensitive aliases", "Destination directories are separate from composer basenames"],
            "approved_exceptions": ["D02: 276 -> 275; green Splatter retired, red unchanged"] if category == "Genre" else [],
            "private_intermediates": [legacy_destination(job) for job in capture["jobs"] if job["category"] == category and not job["published_relatives"]] if category == "Awards" else [],
            "scope": "Resolved English contract parity; generated inputs require separately verified real parent artifacts before render planning"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("category")
    args = parser.parse_args(argv)
    export_category(args.category)
    from .definitions import load_definitions
    definitions = load_definitions([CATALOG / (args.category.lower() + ".yml")], profiles_path=CATALOG / "profiles.yml")
    from .planner import Planner
    expanded = tuple(Planner(generators=GENERATORS).expand(definitions)[0].values())
    report = reconcile(args.category, expanded, Translations({"en": ROOT / "fixtures/english/en.yml"}))
    atomic_bytes(CATALOG / "audit" / (args.category.lower() + "-parity.json"), json.dumps(report, indent=2).encode() + b"\n")
    print(json.dumps(report))
    return 0 if report["contract_parity"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
