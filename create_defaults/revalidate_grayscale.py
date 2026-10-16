"""Audit the original validator's RGB-only rejection of valid reference JPEGs.

No renderer, comparison threshold or numeric metric is changed. Original result
records are retained before applying this narrowly scoped validation revision.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import threading
import time

from PIL import Image

try:
    from . import validation_batch as batch
    from .create_poster import ROOT, digest
    from .compare_poster_renderers import invalid_legacy_font, picture_metadata
    from .validation_manifest import load_manifest, validate_manifest
except ImportError:
    import validation_batch as batch
    from create_poster import ROOT, digest
    from compare_poster_renderers import invalid_legacy_font, picture_metadata
    from validation_manifest import load_manifest, validate_manifest


def correction(job, result, directory, args):
    if result.get("status") != "failure" or not result.get("complete"):
        return None
    legacy = batch.inside(directory / "legacy.jpg", args.report_dir)
    if not legacy.is_file():
        return None
    info = picture_metadata(legacy)
    expected_note = f"legacy: unexpected canvas/format/mode: {tuple(job['canvas'])} JPEG L"
    other_notes = [note for note in result.get("notes", []) if note != expected_note]
    allowed_notes = ("Inactive configured sample path is not read by either renderer:",
                     "Same-queue production output collision:")
    if (expected_note not in result.get("notes", [])
            or any(not note.startswith(allowed_notes) for note in other_notes)
            or info["format"] != "JPEG" or info["mode"] != "L"
            or list(info["dimensions"]) != job["canvas"]
            or set(result.get("images", {})) != {"python"}):
        return None
    python = result["images"]["python"]
    a = result.get("comparisons", {}).get("A-legacy-python", {})
    if (python["mode"] != "RGB" or python["format"] != "JPEG"
            or list(python["dimensions"]) != job["canvas"]
            or not a.get("comparable") or a.get("comparison_space") != "RGB"
            or any(result.get("measurements", {}).get(engine, {}).get("returncode") != 0
                   or result["measurements"][engine].get("timed_out", True)
                   for engine in ("legacy", "python"))):
        return None
    if batch.resumable(job, directory, result["run_key"], published_repo=args.published_repo) != result:
        raise ValueError(f"Original result/artifact verification failed: {job['id']}")
    log = (directory / "legacy.log").read_text(encoding="utf-8-sig", errors="replace")
    if invalid_legacy_font(log) or "[ERROR]" in log or "magick.exe:" in log:
        raise ValueError("Reference diagnostics must not be hidden by mode revalidation")
    revised = deepcopy(result)
    revised["images"]["legacy"] = dict(info, report_file="legacy.jpg", preview="legacy-preview.jpg",
                                       full_resolution_retained=True)
    revised["status"] = "warning" if a.get("flag_for_review") else "pass"
    revised["notes"] = other_notes + [
        "Validation revision: reference JPEG mode L is valid grayscale; original RGB-only rejection was a harness defect.",
        "Numeric RGB comparisons, render measurements, input parameters and original output bytes are unchanged."]
    if result["parameters"].get("text"):
        revised["caption_diagnostics"], revised["shared_artifacts"] = batch.cached_caption(
            result["invocation_parameters"], job, args)
        revised["caption_placement"] = {
            "canvas_origin_before_optional_border_resize": [50, 1000 + result["parameters"]["text_offset"]],
            "bounds_space": "1900x1000 isolated trimmed/centered caption; final border transform not inferred"}
    with Image.open(legacy) as source:
        preview = source.convert("RGB")
    preview.thumbnail((300, 450))
    preview.save(directory / "legacy-preview.jpg", quality=90)
    revised["retained_artifacts"] = {path.name: digest(path) for path in directory.iterdir()
                                     if path.is_file() and path.name not in {"result.json", "index.html"}}
    return revised


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--published-repo", required=True, type=Path)
    args = parser.parse_args(argv)
    args.report_dir, args.published_repo = args.report_dir.resolve(), args.published_repo.resolve()
    if (args.report_dir == ROOT or args.report_dir.is_relative_to(ROOT)
            or args.report_dir == args.published_repo or args.report_dir.is_relative_to(args.published_repo)
            or args.published_repo.is_relative_to(args.report_dir)):
        parser.error("Audit must be isolated from production assets and the read-only published checkout")
    manifest = load_manifest(args.manifest)
    validate_manifest(manifest)
    args.assets, args.magick = ROOT, shutil.which("magick")
    if not args.magick:
        parser.error("Existing ImageMagick is required; nothing will be installed")
    args.caption_lock, args.caption_locks = threading.Lock(), {}
    started = time.perf_counter()
    with batch.exclusive_run(args.report_dir):
        metadata = json.loads((args.report_dir / "run.json").read_text())
        before_state = batch.published_state(args.published_repo)
        if before_state != metadata["published"] or metadata["manifest_sha256"] != manifest["sha256"]:
            raise ValueError("Original manifest/published state changed")
        for field, name in (("comparison_sha256", "compare_poster_renderers.py"),
                            ("manifest_module_sha256", "validation_manifest.py")):
            if digest(ROOT / name) != metadata[field]:
                raise ValueError("Original metric/manifest helpers changed")
        revision = batch.inside(args.report_dir / "validation-revisions/grayscale-v1", args.report_dir)
        revision.mkdir(parents=True, exist_ok=True)
        provenance = {"revision_source_sha256": digest(Path(__file__)),
                      "batch_helper_sha256": digest(ROOT / "validation_batch.py"),
                      "original_run_key": metadata["run_key"], "manifest_sha256": manifest["sha256"]}
        record = revision / "audit.json"
        audit = json.loads(record.read_text()) if record.exists() else {"provenance": provenance, "cases": {}}
        if audit["provenance"] != provenance:
            raise ValueError("Existing revision uses different audit sources")
        results = []
        for job in manifest["jobs"]:
            directory = batch.inside(args.report_dir / "cases" / job["id"], args.report_dir)
            path = directory / "result.json"
            if not path.is_file():
                continue
            result = json.loads(path.read_text())
            if result.get("run_key") != metadata["run_key"] or result.get("job_sha256") != job["sha256"]:
                raise ValueError("Mixed result inputs")
            previous_revision = result.get("validation_revision")
            if previous_revision:
                if any(previous_revision.get(key) != value for key, value in provenance.items()):
                    raise ValueError("Result has a different validation revision")
                backup = revision / (job["id"] + ".original.json")
                if digest(backup) != previous_revision["original_record_sha256"]:
                    raise ValueError("Original revision backup changed")
                entry = {"original_record_sha256": digest(backup), "revised_record_sha256": digest(path),
                         "status": result["status"]}
                if job["id"] in audit["cases"] and audit["cases"][job["id"]] != entry:
                    raise ValueError("Revised record changed after audit")
                audit["cases"][job["id"]] = entry
                batch.case_report(directory, result)
            revised = correction(job, result, directory, args)
            if revised is not None:
                backup = revision / (job["id"] + ".original.json")
                original_sha = digest(path)
                if backup.exists() and digest(backup) != original_sha:
                    raise ValueError("Original backup differs; refusing to overwrite")
                if not backup.exists():
                    shutil.copyfile(path, backup)
                revised["validation_revision"] = {**provenance, "original_record_sha256": original_sha,
                    "original_status": result["status"], "original_record": backup.relative_to(args.report_dir).as_posix()}
                batch.atomic_json(path, revised)
                batch.case_report(directory, revised)
                audit["cases"][job["id"]] = {"original_record_sha256": original_sha,
                    "revised_record_sha256": digest(path), "status": revised["status"]}
                batch.atomic_json(record, audit)
                result = revised
                print(f"Revalidated {job['id']}: {result['status']}", flush=True)
            results.append(result)
        after_state = batch.published_state(args.published_repo)
        validate_manifest(manifest)
        if before_state != after_state:
            raise RuntimeError("Published state changed during read-only validation")
        audit.update(finished_utc=datetime.now(timezone.utc).isoformat(), seconds=time.perf_counter() - started,
                     published_unchanged=True, corrected_cases=len(audit["cases"]))
        batch.atomic_json(record, audit)
        metadata["grayscale_validation_revision"] = {**provenance, "corrected_cases": len(audit["cases"]),
            "audit": record.relative_to(args.report_dir).as_posix(), "audit_sha256": digest(record)}
        batch.atomic_json(args.report_dir / "run.json", metadata)
        summary = batch.dashboard(args.report_dir, results, manifest, metadata)
    print(json.dumps({key: summary[key] for key in ("completed_jobs", "status", "rendered")}, indent=2))
    return int(bool(summary["status"].get("failure")))


if __name__ == "__main__":
    raise SystemExit(main())
