"""Copy verified unchanged jobs into a new, explicitly authorized validation run.

The historical checkpoint is never edited. Rendering must be started separately.
"""

from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

try:
    from . import validation_batch as batch
    from .create_poster import ROOT, digest
    from .validation_manifest import canonical, fingerprint, load_manifest, validate_manifest
except ImportError:
    import validation_batch as batch
    from create_poster import ROOT, digest
    from validation_manifest import canonical, fingerprint, load_manifest, validate_manifest


def same_metric_functions(previous, current):
    def functions(path):
        return {node.name: ast.dump(node, include_attributes=False)
                for node in ast.parse(path.read_text(encoding="utf-8-sig")).body if isinstance(node, ast.FunctionDef)}
    before, after = functions(previous), functions(current)
    names = ("compare_images", "measured", "caption_diagnostics", "prepare_legacy", "python_command",
             "invalid_legacy_font", "published_image", "picture_metadata")
    if any(before.get(name) is None or before[name] != after.get(name) for name in names):
        raise ValueError("Rendering/metric helpers changed; checkpoint reuse requires a new audit")


def copy_checkpoint(source, destination, manifest, metadata, published_repo, workers=8):
    source, destination = source.resolve(), destination.resolve()
    if source == destination or source.is_relative_to(destination) or destination.is_relative_to(source):
        raise ValueError("Checkpoint source and destination must be disjoint")
    if destination == ROOT or destination.is_relative_to(ROOT):
        raise ValueError("Checkpoint destination must be outside production assets")
    if published_repo and (destination == published_repo or destination.is_relative_to(published_repo)
                           or published_repo.is_relative_to(destination)):
        raise ValueError("Checkpoint destination and published checkout must be disjoint")
    if (source / ".running").exists() or not (source / "STOP").exists():
        raise ValueError("Source must be a stopped checkpoint")
    old = load_manifest(source / "manifest.json.gz")
    old_metadata = json.loads((source / "run.json").read_text())
    snapshot = source / "source-snapshot"
    validate_manifest(old, snapshot)
    validate_manifest(manifest)
    if old_metadata["published"] != metadata["published"] or old_metadata["versions"] != metadata["versions"]:
        raise ValueError("Published state or renderer versions changed")
    same_metric_functions(snapshot / "compare_poster_renderers.py", ROOT / "compare_poster_renderers.py")
    if digest(snapshot / "validation_manifest.py") != digest(ROOT / "validation_manifest.py"):
        raise ValueError("Manifest semantics changed")
    old_bulk = (snapshot / "create_default_posters.ps1").read_text(encoding="utf-8-sig")
    new_bulk = (ROOT / "create_default_posters.ps1").read_text(encoding="utf-8-sig")
    old_font = "1565B395F454D5C2642D0F411030051E7342FBAF6D5BFC5DA5899C47ECD3511E"
    new_font = "951C4CEA65FFEDE784A7C9672FEEC5D329A7E1E12216C42D53ECF36C90D04DEA"
    if old_bulk.count(old_font) != 1 or old_bulk.replace(old_font, new_font) != new_bulk:
        raise ValueError("Bulk change must be only the approved Monoton dependency checksum")
    if any(old["source_text_hashes"][name] != manifest["source_text_hashes"][name]
           for name in old["source_text_hashes"] if name != "create_default_posters.ps1"):
        raise ValueError("Renderer sources changed")
    if shutil.disk_usage(destination.parent).free < 5 * 1024 ** 3 + sum(p.stat().st_size for p in source.rglob("*") if p.is_file()):
        raise OSError("Insufficient space to copy evidence and retain the free-space floor")
    destination.mkdir(exist_ok=False)
    audit = {"source": str(source), "source_run_key": old_metadata["run_key"],
             "source_manifest_sha256": old["sha256"], "new_manifest_sha256": manifest["sha256"],
             "source_metadata_sha256": digest(source / "run.json"), "tool_sha256": digest(Path(__file__)),
             "semantics": "Only unchanged job fingerprints are carried forward. Existing image bytes, metrics, timings and input provenance are retained, not rerendered.",
             "complete": False, "cases": {}}
    batch.atomic_json(destination / "checkpoint-import.json", audit)
    if (source / "caption-cache").exists():
        shutil.copytree(source / "caption-cache", destination / "caption-cache")
    current = {job["id"]: job for job in manifest["jobs"]}
    previous = {job["id"]: job for job in old["jobs"]}
    paths = sorted((source / "cases").glob("*/result.json"))
    def copy_case(path):
        result = json.loads(path.read_text())
        job_id = result["id"]
        if job_id not in current or previous[job_id] != current[job_id]:
            raise ValueError(f"Completed job inputs changed: {job_id}")
        job = current[job_id]
        if batch.resumable(job, path.parent, old_metadata["run_key"], published_repo=published_repo) != result:
            raise ValueError(f"Source evidence verification failed: {job_id}")
        if (result.get("status") not in {"pass", "warning"} or set(result.get("images", {})) != {"legacy", "python"}
                or not result.get("comparisons", {}).get("A-legacy-python", {}).get("comparable")
                or any(result.get("measurements", {}).get(engine, {}).get("returncode") != 0
                       or result["measurements"][engine].get("timed_out", True) for engine in ("legacy", "python"))):
            raise ValueError(f"Source job is not a successful pair: {job_id}")
        target = batch.inside(destination / "cases" / job_id, destination)
        target.mkdir(parents=True)
        for name, checksum in result["retained_artifacts"].items():
            original, copy = batch.inside(path.parent / name, path.parent), batch.inside(target / name, target)
            shutil.copyfile(original, copy)
            if digest(copy) != checksum:
                raise ValueError(f"Copied artifact mismatch: {job_id}/{name}")
        shutil.copyfile(path, target / "source-result.json")
        revised = deepcopy(result)
        revised["run_key"] = metadata["run_key"]
        revised["checkpoint_origin"] = {"run_key": old_metadata["run_key"], "record_sha256": digest(path),
                                        "record": "source-result.json", "job_inputs_unchanged": True}
        revised["retained_artifacts"]["source-result.json"] = digest(target / "source-result.json")
        if revision := revised.pop("validation_revision", None):
            revised["checkpoint_origin"]["original_validation_revision"] = revision
        batch.atomic_json(target / "result.json", revised)
        batch.case_report(target, revised)
        return job_id, {"source_record_sha256": digest(path), "new_record_sha256": digest(target / "result.json")}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for path, future in batch.bounded_completed(pool, copy_case, paths, workers, lambda: False):
            job_id, entry = future.result()
            audit["cases"][job_id] = entry
            if len(audit["cases"]) % 500 == 0:
                print(f'Carried forward {len(audit["cases"])} verified unchanged jobs', flush=True)
    if batch.published_state(published_repo) != metadata["published"]:
        raise ValueError("Published state changed during checkpoint import")
    if digest(source / "run.json") != audit["source_metadata_sha256"]:
        raise ValueError("Source checkpoint changed during import")
    audit.update(complete=True, imported_jobs=len(audit["cases"]), finished_utc=datetime.now(timezone.utc).isoformat())
    batch.atomic_json(destination / "checkpoint-import.json", audit)
    metadata["checkpoint_import"] = {"jobs": len(audit["cases"]), "audit_sha256": digest(destination / "checkpoint-import.json"),
                                      "source_run_key": old_metadata["run_key"], "images_rerendered": False}
    import gzip
    (destination / "manifest.json.gz").write_bytes(gzip.compress(canonical(manifest), mtime=0))
    batch.atomic_json(destination / "run.json", metadata)
    results = [json.loads(path.read_text()) for path in (destination / "cases").glob("*/result.json")]
    batch.dashboard(destination, results, manifest, metadata)
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--published-repo", required=True, type=Path)
    args = parser.parse_args()
    args.published_repo = args.published_repo.resolve()
    manifest = load_manifest(args.manifest)
    powershell, magick = shutil.which("pwsh"), shutil.which("magick")
    if not powershell or not magick:
        parser.error("Existing PowerShell 7 and ImageMagick are required")
    inputs = batch.run_inputs(manifest, batch.published_state(args.published_repo), powershell, magick)
    metadata = {**inputs, "run_key": fingerprint(inputs), "started_utc": datetime.now(timezone.utc).isoformat(),
                "base_code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT.parent, text=True).strip(),
                "validation_code_uncommitted": True}
    audit = copy_checkpoint(args.source, args.destination, manifest, metadata, args.published_repo)
    print(f'Prepared {audit["imported_jobs"]} verified jobs; rendering was not started.')


if __name__ == "__main__":
    main()
