"""Frozen effective composer jobs captured from the real PowerShell category ASTs.

This is validation data, not a replacement production category format.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import gzip
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys

import yaml
from fontTools.ttLib import TTFont

try:
    from .create_poster import ROOT, PosterOptions, digest, output_filename
    from .poster_fixtures import extract_rows, translation_file
    from .poster_text import resolve_font
except ImportError:
    from create_poster import ROOT, PosterOptions, digest, output_filename
    from poster_fixtures import extract_rows, translation_file
    from poster_text import resolve_font


SCHEMA = 1
INTS = {"logo_offset", "logo_resize", "text_offset", "font_size", "gradient", "border_width"}
BOOLS = {"avg_color", "dom_color", "border", "white_wash", "clean"}
PATHS = {"logo", "avg_color_image", "dom_color_image"}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def as_list(value):
    return value if isinstance(value, list) else ([] if value is None else [value])


def text_digest(path):
    return hashlib.sha256(Path(path).read_text(encoding="utf-8-sig").replace("\r\n", "\n").encode()).hexdigest()


def portable(value, assets):
    if isinstance(value, dict):
        return {key: portable(item, assets) for key, item in value.items()}
    if isinstance(value, list):
        return [portable(item, assets) for item in value]
    if isinstance(value, str):
        windows = PureWindowsPath(value)
        normalized = windows.as_posix() if windows.is_absolute() else value
        prefix = assets.as_posix()
        if normalized.casefold() == prefix.casefold() or normalized.casefold().startswith(prefix.casefold() + "/"):
            return "{ASSETS}" + normalized[len(prefix):]
        return value.replace(str(assets), "{ASSETS}").replace(assets.as_posix(), "{ASSETS}")
    return value


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


def safe_relative(path, root=ROOT):
    path = Path(str(path).replace("\\", "/"))
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError(f"Input escapes declared asset root: {path}")
    return path.relative_to(root.resolve()).as_posix()


def effective_parameters(raw, index, assets=ROOT):
    unknown = set(raw) - set(PosterOptions.__dataclass_fields__)
    if unknown:
        raise ValueError(f"Unknown composer parameters: {sorted(unknown)}")
    values = asdict(PosterOptions())
    values.update(raw)
    dynamic = []
    for name in INTS:
        try:
            values[name] = int(values[name])
        except (ValueError, TypeError):
            dynamic.append(f"Noncanonical numeric {name}={values[name]!r} retained verbatim; not silently repaired")
    for name in BOOLS:
        value = values[name]
        if str(value).strip().lower() not in {"true", "false", "0", "1"}:
            raise ValueError(f"Unknown boolean coercion for {name}: {value}")
        values[name] = str(value).strip().lower() in {"true", "1"}
    # Exact legacy empty-string coercions: these are execution metadata, not row edits.
    if not values["logo_resize"]:
        values["logo_resize"] = 2000
        dynamic.append("legacy numeric logo_resize=0 defaults to 2000")
    for name in PATHS:
        values[name] = safe_relative(values[name], assets) if values.get(name) else None
    for name in ("font", "font_color", "border_color", "base_color"):
        if values.get(name) is not None:
            values[name] = str(values[name]).strip()
    if not values.get("base_color"):
        # Freeze a valid draw from the original random-color domain once per job.
        value = int(fingerprint({"job": index, "parameters": values})[:8], 16) % 0xFFFFFF
        values["base_color"] = f"#{value:06X}"
        dynamic.append("original blank base_color is random; this valid draw is frozen identically for both engines")
    if not 10 <= values["font_size"] <= 500:
        dynamic.append("legacy out-of-range font_size resets to 250")
        values["font_size"] = 250
    return values, dynamic


def runtime_parameters(job, assets=ROOT):
    result = dict(job["parameters"])
    # Exercise the original composer inputs, not only their equivalent fallback values.
    for name in ("logo_resize", "font_size"):
        if name in job.get("raw_parameters", {}):
            result[name] = int(job["raw_parameters"][name])
    for name in PATHS:
        if result.get(name):
            result[name] = str((assets / result[name]).resolve())
    # An exact path prevents host-installed fonts overriding the reviewed bundled bytes.
    result["font"] = str((assets / job["font"]["path"]).resolve())
    return result


def resolve_capture_fitting(capture, cache_dir, magick, workers=4):
    """Resolve only audited caption measurements, independently of category execution."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    requests = {}
    for record in capture["jobs"]:
        fit = record.get("fitting")
        if fit and fit.get("deferred"):
            request = {name: fit[name] for name in ("text", "font_path", "box", "minimum", "maximum")}
            request["font_sha256"] = digest(request["font_path"])
            requests[fingerprint(request)] = request
    def measure(entry):
        key, request = entry
        path = cache_dir / (key + ".json")
        if path.exists():
            cached = json.loads(path.read_text())
            if cached["request"] != request:
                raise ValueError("Fitting cache request mismatch")
            return key, cached
        measured = None
        if str(request["text"]).strip():
            width, height = request["box"]
            command = [str(magick), "-size", f"{width}x{height}", "-font", request["font_path"], "-gravity", "center",
                       "-fill", "black", "caption:" + request["text"], "-format", "%[caption:pointsize]", "info:"]
            result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=45,
                                    env=dict(os.environ, MAGICK_THREAD_LIMIT="1", OMP_NUM_THREADS="1"))
            if "unable to read font" in result.stderr.lower():
                raise ValueError("Exact fitting font could not be read")
            measured = int(float(result.stdout.strip()))
        size = request["maximum"] if measured is None else min(request["maximum"], max(request["minimum"], measured))
        value = {"request": request, "measured": measured, "point_size": size}
        temporary = path.with_suffix(".tmp")
        write_json(temporary, value)
        temporary.replace(path)
        return key, value
    resolved = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(measure, entry) for entry in requests.items()]):
            key, value = future.result()
            resolved[key] = value
            if len(resolved) % 100 == 0:
                print(f"Resolved {len(resolved)}/{len(requests)} distinct caption-fitting requests", flush=True)
    for record in capture["jobs"]:
        fit = record.get("fitting")
        if fit and fit.get("deferred"):
            request = {name: fit[name] for name in ("text", "font_path", "box", "minimum", "maximum")}
            request["font_sha256"] = digest(request["font_path"])
            value = resolved[fingerprint(request)]
            record["fitting"] = {**fit, "deferred": False, "measured": value["measured"], "point_size": value["point_size"]}
            record["raw_parameters"]["font_size"] = str(value["point_size"])
    return capture


def build_manifest(capture, assets=ROOT, translations=None):
    assets = Path(assets).resolve()
    source = assets / "create_default_posters.ps1"
    if capture["source_sha256"] != digest(source):
        raise ValueError("Capture source no longer matches the bulk script")
    literal = extract_rows(source)
    literal_lines = {row["line"] for row in literal}
    row_locations = {}
    for row in literal:
        row_locations.setdefault((row["category"], fingerprint(row["row"])), []).append(row["line"])
    seen = set()
    fonts, jobs = {}, []
    shared = ["transparent.png", *("fades/" + name for name in ("@none.png", "@center-out-fade.png", "@bottom-up-fade.png", "@top-down-fade.png", "@bottom-top-fade.png"))]
    inputs = {name: digest(assets / name) for name in shared}
    output_producers = {}
    for record in capture["jobs"]:
        for target in as_list(record.get("output_paths")):
            output_producers.setdefault(target.casefold(), []).append(record["index"])
    for record in capture["jobs"]:
        if record.get("fitting", {}) and record["fitting"].get("deferred"):
            raise ValueError("Unresolved fitting cannot enter a frozen manifest")
        if record["index"] != len(jobs):
            raise ValueError("Capture indexes must be complete and contiguous")
        values, choices = effective_parameters(record["raw_parameters"], record["index"], assets)
        face = resolve_font(values["font"], assets / "fonts")
        font_path = safe_relative(face, assets)
        if font_path not in fonts:
            with TTFont(face) as font:
                names = lambda identifier: sorted({n.toUnicode() for n in font["name"].names if n.nameID == identifier})
                fonts[font_path] = {"path": font_path, "sha256": digest(face), "family": names(1), "style": names(2), "version": names(5)}
        for name in PATHS:
            if values.get(name) and values[name] not in inputs:
                path = assets / values[name]
                inputs[values[name]] = digest(path) if path.is_file() else None
        line = record.get("definition_line")
        if record.get("source_row"):
            candidates = [value for value in row_locations.get((record["category"], fingerprint(record["source_row"])), []) if value < record["producer_line"]]
            if not candidates:
                raise ValueError("Captured source row does not exactly match the literal inventory")
            line = max(candidates)
        if line is not None:
            if line not in literal_lines:
                raise ValueError("Captured definition points outside literal inventory")
            seen.add(line)
        relative = output_filename(PosterOptions(**values), values["base_color"])
        targets = sorted(as_list(record.get("output_paths")))
        for target in targets:
            if target.startswith("/") or ".." in Path(target).parts:
                raise ValueError("Captured output escapes virtual production root")
        key = {"index": record["index"], "category": record["category"], "definition_line": line,
               "producer_line": record["producer_line"], "parameters": values, "outputs": targets}
        generated = {}
        for name in PATHS:
            producers = [index for index in output_producers.get(str(values.get(name)).casefold(), []) if index < record["index"]]
            if producers:
                generated[name] = {"relative": values[name], "job_id": jobs[max(producers)]["id"],
                                   "comparison_input": "Fresh PowerShell parent output frozen identically for both engines"}
        job = {"id": f'{record["category"].lower()}-{record["index"]:05d}-{fingerprint(key)[:12]}',
               "category": record["category"], "definition_id": f'line-{line}' if line else f'direct-{record["producer_line"]}',
               "source": {"path": "create_default_posters.ps1", "definition_line": line, "producer_line": record["producer_line"]},
               "source_row": record.get("source_row", {}),
               "effective_source_row": record.get("effective_source_row"),
               "name": values.get("out_name"), "text": values.get("text"), "translated_text": values.get("text"), "language": capture["language"],
               "canvas": [2000, 3000], "parameters": values, "raw_parameters": portable(record["raw_parameters"], assets),
               "expected_composer_filename": relative, "published_relatives": targets,
               "font": fonts[font_path], "fitting": portable(record.get("fitting"), assets),
               "generated_inputs": generated,
               "dynamic": {**record["dynamic"], "frozen_choices": choices,
                           "generated_name": values.get("out_name") != record.get("source_row", {}).get("out_name"),
                           "literal_translation_key": record.get("source_row", {}).get("key_name")},
               "assets": {values[name]: inputs[values[name]] for name in PATHS if values.get(name)}}
        job["sha256"] = fingerprint(job)
        jobs.append(job)
    metadata = {"schema": SCHEMA, "language": capture["language"], "language_scope": "Default English All dispatch; other language selections are not claimed tested",
                "capture_harness_sha256": digest(assets / "capture_jobs.ps1"),
                "capture_scope": "Actual All dispatch over isolated allowlisted category ASTs; fitting recomputed from exact bundled fonts, no legacy SQLite cache",
                "literal_definitions": len(literal), "covered_literal_definitions": len(seen),
                "uncovered_literal_lines": sorted(literal_lines - seen), "effective_composer_jobs": len(jobs),
                "categories": dict(sorted(Counter(job["category"] for job in jobs).items())),
                "source_hashes": {name: digest(assets / name) for name in ("create_default_posters.ps1", "create_poster.ps1", "create_poster.py", "poster_text.py")},
                "source_text_hashes": {name: text_digest(assets / name) for name in ("create_default_posters.ps1", "create_poster.ps1", "create_poster.py", "poster_text.py")},
                "translation": {"sha256": digest(translations or translation_file(assets)), "source": "English snapshot; see fixtures/english/README.md"},
                "fonts": fonts, "asset_hashes": inputs, "overlay_operations": portable(capture["overlay_operations"], assets),
                "auxiliary_file_operations": portable(capture["file_operations"], assets), "jobs": jobs}
    collisions = {}
    for job in jobs:
        key = (job["category"], job["source"]["producer_line"], job["expected_composer_filename"].casefold())
        collisions.setdefault(key, []).append(job)
    metadata["same_queue_output_collisions"] = []
    for (category, line, filename), group in collisions.items():
        if len(group) > 1:
            metadata["same_queue_output_collisions"].append({"category": category, "producer_line": line,
                "filename": filename, "job_ids": [job["id"] for job in group],
                "note": "Production launches queued jobs concurrently; a final overwrite winner is not certified by virtual capture"})
    metadata["jobs_without_final_virtual_path"] = [job["id"] for job in jobs if not job["published_relatives"]]
    metadata["sha256"] = fingerprint(metadata)
    return metadata


def load_manifest(path):
    path = Path(path)
    data = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    value = json.loads(data)
    expected = value.pop("sha256")
    if fingerprint(value) != expected:
        raise ValueError("Frozen manifest fingerprint mismatch")
    value["sha256"] = expected
    return value


def validate_manifest(manifest, assets=ROOT, *, source_root=None):
    source_root = Path(source_root) if source_root is not None else assets
    if manifest["schema"] != SCHEMA or len(manifest["jobs"]) != manifest["effective_composer_jobs"]:
        raise ValueError("Incomplete frozen manifest")
    for name, checksum in manifest["source_text_hashes"].items():
        if text_digest(source_root / name) != checksum:
            raise ValueError(f"Frozen renderer/source changed: {name}")
    for path, checksum in manifest["asset_hashes"].items():
        try:
            from create_defaults.bulk.asset_cases import historical
        except ImportError:
            from bulk.asset_cases import historical
        if checksum is not None and digest(historical(assets, path, checksum)) != checksum:
            raise ValueError(f"Frozen asset changed: {path}")
    for font in manifest["fonts"].values():
        if digest(assets / font["path"]) != font["sha256"]:
            raise ValueError("Frozen font changed")
    if digest(translation_file(assets)) != manifest["translation"]["sha256"]:
        raise ValueError("Frozen translations changed")
    ids = set()
    for job in manifest["jobs"]:
        expected = job.pop("sha256")
        actual = fingerprint(job)
        job["sha256"] = expected
        if actual != expected or job["id"] in ids:
            raise ValueError("Job fingerprint mismatch or duplicate job id")
        ids.add(job["id"])
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--from-capture", type=Path)
    parser.add_argument("--check", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fitting-cache", type=Path)
    parser.add_argument("--fitting-workers", type=int, choices=range(1, 9), default=4)
    args = parser.parse_args(argv)
    if args.check:
        manifest = load_manifest(args.check)
        validate_manifest(manifest)
        print(f'Validated {len(manifest["jobs"])} frozen effective jobs; {manifest["literal_definitions"]} literal definitions')
        return 0
    if not args.output:
        parser.error("--output is required")
    if args.from_capture:
        capture = json.loads(args.from_capture.read_text(encoding="utf-8-sig"))
    else:
        if not args.capture_dir or not shutil.which("pwsh") or not shutil.which("magick"):
            parser.error("Capture requires --capture-dir and existing PowerShell 7/ImageMagick")
        args.capture_dir.mkdir(parents=True, exist_ok=False)
        write_json(args.capture_dir / "rows.json", extract_rows())
        write_json(args.capture_dir / "translations.json", yaml.safe_load(translation_file().read_text(encoding="utf-8-sig")))
        subprocess.run([shutil.which("pwsh"), "-NoLogo", "-NoProfile", "-File", str(ROOT / "capture_jobs.ps1"),
                        "-Source", str(ROOT / "create_default_posters.ps1"), "-Assets", str(ROOT),
                        "-TranslationJson", str(args.capture_dir / "translations.json"), "-RowsJson", str(args.capture_dir / "rows.json"),
                        "-OutputFile", str(args.capture_dir / "captured.json"), "-Magick", shutil.which("magick"), "-DeferredFitting"],
                       check=True, timeout=3600, env=dict(os.environ, MAGICK_THREAD_LIMIT="1", OMP_NUM_THREADS="1"))
        capture = json.loads((args.capture_dir / "captured.json").read_text())
    if any(record.get("fitting") and record["fitting"].get("deferred") for record in capture["jobs"]):
        if not args.fitting_cache or not shutil.which("magick"):
            parser.error("Deferred capture requires --fitting-cache and existing ImageMagick")
        capture = resolve_capture_fitting(capture, args.fitting_cache, shutil.which("magick"), args.fitting_workers)
    manifest = build_manifest(capture)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite a frozen manifest")
    data = canonical(manifest)
    args.output.write_bytes(gzip.compress(data, mtime=0) if args.output.suffix == ".gz" else data)
    print(json.dumps({k: v for k, v in manifest.items() if k in {"literal_definitions", "covered_literal_definitions", "effective_composer_jobs", "uncovered_literal_lines", "categories", "sha256"}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
