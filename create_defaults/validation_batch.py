"""Resumable, bounded offline parity validation of a frozen effective-job manifest."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import html
from importlib.metadata import version
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time

from PIL import Image, __version__ as PILLOW_VERSION

try:
    from .create_poster import ROOT, digest
    from .compare_poster_renderers import (caption_diagnostics, compare_images, invalid_legacy_font,
                                          measured, page, picture_metadata, prepare_legacy,
                                          published_image, python_command)
    from .validation_manifest import (fingerprint, load_manifest, runtime_parameters, validate_manifest)
    from .validation_review import review_summary
except ImportError:
    from create_poster import ROOT, digest
    from compare_poster_renderers import (caption_diagnostics, compare_images, invalid_legacy_font,
                                         measured, page, picture_metadata, prepare_legacy,
                                         published_image, python_command)
    from validation_manifest import fingerprint, load_manifest, runtime_parameters, validate_manifest
    from validation_review import review_summary


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")
    temporary.replace(path)


def canonical_path(path):
    resolved = Path(path).resolve()
    value = str(resolved)
    if os.name == "nt":
        # Windows may retain a device prefix while another thread creates a parent.
        if value.startswith("\\\\?\\UNC\\"):
            return Path("\\\\" + value[8:])
        if value.startswith("\\\\?\\") and len(value) > 6 and value[4].isalpha() and value[5:7] == ":\\":
            return Path(value[4:])
    return resolved


def inside(path, root):
    path, root = canonical_path(path), canonical_path(root)
    if path == root or not path.is_relative_to(root):
        raise ValueError(f"Validation path must be strictly inside its owned workspace: path={path!s}; root={root!s}")
    return path


def bounded_completed(pool, execute, jobs, workers, should_stop):
    iterator = iter(jobs)
    pending = {}
    def submit():
        if should_stop():
            return False
        job = next(iterator, None)
        if job is None:
            return False
        pending[pool.submit(execute, job)] = job
        return True
    try:
        for _ in range(workers):
            if not submit():
                break
        while pending and not should_stop():
            done, _ = wait(pending, timeout=.5, return_when=FIRST_COMPLETED)
            for future in done:
                job = pending.pop(future)
                yield job, future
                submit()
    finally:
        for future in pending:
            future.cancel()


@contextmanager
def exclusive_run(root):
    lock = root / ".running"
    try:
        stream = lock.open("x", encoding="ascii")
    except FileExistsError as error:
        raise RuntimeError("Batch is already running, or a stale .running lock needs explicit inspection") from error
    try:
        with stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        lock.unlink()


def published_state(repository):
    if not repository:
        return None
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(repository), *arguments], env=env, text=True, timeout=60).strip()
    return {"commit": git("rev-parse", "HEAD"), "tracked_status": git("status", "--porcelain", "--untracked-files=no")}


def run_inputs(manifest, published, powershell, magick):
    return {"manifest_sha256": manifest["sha256"], "published": published,
            "runner_sha256": digest(Path(__file__)), "comparison_sha256": digest(ROOT / "compare_poster_renderers.py"),
            "review_sha256": digest(ROOT / "validation_review.py"),
            "manifest_module_sha256": digest(ROOT / "validation_manifest.py"),
            "versions": {"python": sys.version, "pillow": PILLOW_VERSION,
                         "fonttools": version("fonttools"), "uharfbuzz": version("uharfbuzz"),
                         "numpy": version("numpy"), "python-bidi": version("python-bidi"),
                         "magick": subprocess.check_output([magick, "-version"], text=True).strip(),
                         "powershell": subprocess.check_output([powershell, "-NoLogo", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"], text=True).strip()}}


def resumable(job, directory, run_key, retry_failed=False, published_repo=None):
    path = directory / "result.json"
    if not path.is_file():
        return None
    try:
        result = json.loads(path.read_text())
        if result["job_sha256"] != job["sha256"] or result["run_key"] != run_key:
            return None
        if retry_failed and result["status"] == "failure":
            return None
        if not result.get("complete"):
            return None
        for name, checksum in result.get("retained_artifacts", {}).items():
            candidate = inside(directory / name, directory)
            if not candidate.is_file() or digest(candidate) != checksum:
                return None
        for name, checksum in result.get("shared_artifacts", {}).items():
            candidate = inside(directory.parents[1] / name, directory.parents[1])
            if not candidate.is_file() or digest(candidate) != checksum:
                return None
        for entry in result.get("generated_input_hashes", {}).values():
            parent = inside(directory.parents[1] / "cases" / entry["job_id"] / "legacy.jpg", directory.parents[1])
            if not parent.is_file() or digest(parent) != entry["sha256"]:
                return None
        if published_repo:
            current = {}
            for relative in job["published_relatives"]:
                source = published_image(published_repo, relative)
                if source:
                    current[source.relative_to(published_repo).as_posix()] = digest(source)
            previous = {entry["relative"]: entry["sha256"] for entry in result.get("published_counterparts", [])}
            if current != previous:
                return None
        return result
    except (ValueError, KeyError, OSError):
        return None


def classification(job, comparisons, has_published):
    a = comparisons.get("A-legacy-python", {})
    if not a.get("comparable"):
        return "unresolved discrepancy"
    if a.get("flag_for_review"):
        return "Python migration difference"
    if not has_published:
        return "missing published counterpart"
    historical = any(value.get("flag_for_review") or value.get("comparable") is False
                     for name, value in comparisons.items() if name.startswith(("B-", "C-")))
    if historical:
        if Path(job["font"]["path"]).name in {"BebasNeue-Regular.ttf", "PlusJakartaSans-Bold.ttf"}:
            return "approved font replacement"
        return "existing historical artwork difference"
    return "expected image-encoding difference"


def dependency_levels(jobs):
    pending = {job["id"]: job for job in jobs}
    if len(pending) != len(jobs):
        raise ValueError("Duplicate job id")
    levels, completed = [], set()
    while pending:
        ready = [job for job in pending.values() if {entry["job_id"] for entry in job.get("generated_inputs", {}).values()} <= completed]
        if not ready:
            raise ValueError("Generated-input dependency is missing or cyclic")
        levels.append(ready)
        for job in ready:
            completed.add(job["id"])
            del pending[job["id"]]
    return levels


def required_inputs(parameters):
    names = ["logo"]
    if parameters.get("avg_color"):
        names.append("avg_color_image")
    return {parameters[name] for name in names if parameters.get(name)}


def comparison_summary(comparison):
    return {key: value for key, value in comparison.items() if key not in {"difference", "text_crops", "alpha_difference"}}


def valid_output(info, canvas, engine):
    modes = {"RGB", "L"} if engine == "legacy" else {"RGB"}
    return list(info["dimensions"]) == canvas and info["format"] == "JPEG" and info["mode"] in modes


def reuse_identical_published(label, comparison, reference_hash, published_hash, directory):
    if reference_hash != published_hash or not comparison.get("comparable") or comparison.get("comparison_space") != "RGB":
        return None
    if not label.startswith(("B-", "C-")):
        return None
    result = deepcopy(comparison)
    result["metric_provenance"] = "Published SHA-256 equals fresh reference; exact equality/symmetry reuses A evidence without another raster comparison"
    if label.startswith("C-"):
        result["text_crops"] = list(reversed(result["text_crops"]))
        return result
    for key in ("mean_absolute_error_0_255", "maximum_channel_difference_0_255", "channel_difference_p99_0_255", "changed_pixel_fraction"):
        result[key] = 0
    result["global_luminance_ssim_400x600"] = 1.0
    result["text_region"]["mean_absolute_error_0_255"] = 0
    result["flag_for_review"] = False
    result["difference"] = label + "-difference.png"
    Image.new("RGB", (500, 750), (0, 0, 0)).save(directory / result["difference"])
    result["text_crops"] = [result["text_crops"][0]] * 2
    return result


def shrink_evidence(directory):
    for path in directory.glob("*.png"):
        with Image.open(path) as source:
            image = source.copy()
        image.thumbnail((500, 750))
        image.save(path, compress_level=3)


def cached_caption(parameters, job, args):
    key = fingerprint({"text": parameters["text"], "font_sha256": job["font"]["sha256"],
                       "size": parameters["font_size"], "color": parameters["font_color"]})
    with args.caption_lock:
        lock = args.caption_locks.setdefault(key, threading.Lock())
    directory = inside(args.report_dir / "caption-cache" / key, args.report_dir)
    with lock:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "metrics.json"
        if path.is_file():
            value = json.loads(path.read_text())
            if value.get("cache_key") != key or any(digest(directory / name) != checksum for name, checksum in value.get("image_sha256", {}).items()):
                raise ValueError("Caption evidence cache changed; use a fresh validation report")
        else:
            value = caption_diagnostics(parameters, args.assets / job["font"]["path"], directory, args.magick)
            value["font_sha256"] = job["font"]["sha256"]
            value["cache_key"] = key
            value["image_sha256"] = {name: digest(directory / name) for name in ("legacy-caption.png", "python-caption.png")}
            atomic_json(path, value)
    files = [path, directory / "legacy-caption.png", directory / "python-caption.png"]
    return value, {file.relative_to(args.report_dir).as_posix(): digest(file) for file in files}


def render_job(job, args, workspace, run_key):
    directory = inside(args.report_dir / "cases" / job["id"], args.report_dir)
    directory.mkdir(parents=True, exist_ok=True)
    previous = resumable(job, directory, run_key, args.retry_failed, getattr(args, "published_repo", None))
    if previous:
        return previous, True
    # Only files under this job's private evidence directory may be replaced.
    for path in directory.iterdir():
        if path.is_file():
            path.unlink()
    result = {"id": job["id"], "category": job["category"], "font": job["font"],
              "job_sha256": job["sha256"], "run_key": run_key, "parameters": job["parameters"],
              "definition_id": job["definition_id"], "published_relatives": job["published_relatives"],
              "status": "failure", "notes": [], "images": {}, "comparisons": {}, "measurements": {}, "complete": False}
    started = time.perf_counter()
    try:
        if shutil.disk_usage(args.report_dir).free < args.min_free_gb * 1024 ** 3:
            raise OSError("Free-space safety limit reached; resume after freeing storage")
        parameters = runtime_parameters(job, args.assets)
        result["invocation_parameters"] = parameters
        generated = job.get("generated_inputs", {})
        generated_paths = {entry["relative"] for entry in generated.values()}
        required = required_inputs(job["parameters"])
        missing = [path for path, checksum in job["assets"].items() if checksum is None and path in required and path not in generated_paths]
        if missing:
            raise FileNotFoundError("Configured source assets missing: " + ", ".join(missing))
        inactive_missing = [path for path, checksum in job["assets"].items() if checksum is None and path not in required]
        if inactive_missing:
            result["notes"].append("Inactive configured sample path is not read by either renderer: " + ", ".join(inactive_missing))
        result["generated_input_hashes"] = {}
        for name, entry in generated.items():
            parent = inside(args.report_dir / "cases" / entry["job_id"] / "legacy.jpg", args.report_dir)
            if not parent.is_file():
                raise FileNotFoundError(f"Fresh PowerShell dependency unavailable: {entry['job_id']}")
            parameters[name] = str(parent)
            result["generated_input_hashes"][name] = {"job_id": entry["job_id"], "sha256": digest(parent),
                                                       "note": "Same fresh PowerShell parent bytes supplied to both engines"}
        for engine in ("legacy", "python"):
            target = directory / f"{engine}.jpg"
            if engine == "legacy":
                output = workspace / "output"
                if output.exists():
                    for path in output.rglob("*.jpg"):
                        inside(path, workspace).unlink()
                (output / job["expected_composer_filename"]).parent.mkdir(parents=True, exist_ok=True)
                values = {name: value for name, value in parameters.items() if value is not None}
                for name in ("logo_offset", "text_offset"):
                    if isinstance(values[name], int):
                        values[name] = f'{values[name]:+d}'
                atomic_json(workspace / "parameters.json", values)
                command = [args.powershell, "-NoLogo", "-NoProfile", "-File", workspace / "run.ps1",
                           "-ParameterFile", workspace / "parameters.json"]
                cwd = workspace
            else:
                command = python_command(args.assets / "create_poster.py", parameters, args.assets, target)
                cwd = ROOT.parent
            log = directory / f"{engine}.log"
            measurement = measured(command, cwd, log, args.timeout, sample_interval=args.sample_interval)
            result["measurements"][engine] = measurement
            text = log.read_text(encoding="utf-8-sig", errors="replace")
            valid = measurement["returncode"] == 0 and not measurement["timed_out"]
            if engine == "legacy":
                generated = list((workspace / "output").rglob("*.jpg"))
                valid = valid and len(generated) == 1 and not invalid_legacy_font(text) and "[ERROR]" not in text and "magick.exe:" not in text
                if valid:
                    actual = generated[0].relative_to(workspace / "output").as_posix()
                    if actual.casefold() != job["expected_composer_filename"].casefold():
                        raise ValueError(f"Legacy filename mismatch: {actual}")
                    shutil.move(str(generated[0]), target)
            if valid and target.is_file():
                info = picture_metadata(target)
                if valid_output(info, job["canvas"], engine):
                    result["images"][engine] = dict(info, report_file=target.name)
                else:
                    result["notes"].append(f"{engine}: unexpected canvas/format/mode: {info['dimensions']} {info['format']} {info['mode']}")
            else:
                result["notes"].append(f"{engine}: output rejected; timeout={measurement['timed_out']}; exit={measurement['returncode']}; see {log.name}")
        published = []
        for relative in job["published_relatives"]:
            source = published_image(args.published_repo, relative)
            if source and source not in published:
                published.append(source)
        # Usually aliases are identical. Record every counterpart; compare each distinct binary.
        by_hash = {}
        result["published_counterparts"] = []
        for source in published:
            info = picture_metadata(source)
            info["relative"] = source.relative_to(args.published_repo).as_posix()
            info.pop("path")
            result["published_counterparts"].append(info)
            by_hash.setdefault(info["sha256"], source)
        pairs = [("A-legacy-python", directory / "legacy.jpg", directory / "python.jpg")]
        for index, source in enumerate(by_hash.values()):
            suffix = "" if index == 0 else f"-alias-{index}"
            pairs.extend((f"{letter}-{engine}-published{suffix}", directory / f"{engine}.jpg", source)
                         for letter, engine in (("B", "legacy"), ("C", "python")))
        result["published_comparison_sources"] = {label: second.relative_to(args.published_repo).as_posix()
                                                   for label, _, second in pairs if "published" in label}
        for label, first, second in pairs:
            if first.is_file() and second.is_file():
                before = digest(second)
                reused = reuse_identical_published(label, result["comparisons"].get("A-legacy-python", {}),
                    result["images"].get("legacy", {}).get("sha256"), before, directory)
                result["comparisons"][label] = reused or compare_images(first, second, directory, label, parameters["text_offset"])
                if digest(second) != before:
                    raise RuntimeError("Read-only comparison input changed during metrics")
        a = result["comparisons"].get("A-legacy-python", {})
        result["classification"] = classification(job, result["comparisons"], bool(published))
        if job["id"] in args.ambiguous_jobs:
            result["classification"] = "unresolved discrepancy"
            result["notes"].append("Same-queue production output collision: a final published overwrite winner cannot be certified; both definitions are tested independently")
        if set(result["images"]) == {"legacy", "python"} and a.get("comparable"):
            result["status"] = "warning" if a.get("flag_for_review") else "pass"
            if parameters.get("text"):
                result["caption_diagnostics"], result["shared_artifacts"] = cached_caption(parameters, job, args)
                result["caption_placement"] = {"canvas_origin_before_optional_border_resize": [50, 1000 + parameters["text_offset"]],
                                                "bounds_space": "1900x1000 isolated trimmed/centered caption; final border transform not inferred"}
            result["notes"].append("Thresholds screen for review; they are not visual sign-off")
        for engine, info in result["images"].items():
            original = directory / info["report_file"]
            with Image.open(original) as source:
                thumbnail = source.convert("RGB")
            thumbnail.thumbnail((300, 450))
            preview = directory / f"{engine}-preview.jpg"
            thumbnail.save(preview, quality=90)
            info["preview"] = preview.name
            # Retain full-resolution flags plus a predictable pass representative per category.
            retain = (result["status"] != "pass" or job["id"] in args.representatives
                      or (engine == "legacy" and job["id"] in args.required_parents))
            info["full_resolution_retained"] = retain
            if not retain:
                original.unlink()
        if published:
            with Image.open(published[0]) as source:
                preview = source.convert("RGB")
            preview.thumbnail((300, 450))
            preview.save(directory / "published-preview.jpg", quality=90)
        shrink_evidence(directory)
    except Exception as error:
        result["status"] = "failure"
        result["notes"].append(f"{type(error).__name__}: {error}")
        result["classification"] = "unresolved discrepancy"
    result["seconds"] = time.perf_counter() - started
    result["complete"] = True
    result["retained_artifacts"] = {path.name: digest(path) for path in directory.iterdir()
                                    if path.is_file() and path.name not in {"result.json", "index.html"}}
    atomic_json(directory / "result.json", result)
    case_report(directory, result)
    return result, False


def case_report(directory, result):
    escaped = html.escape
    content = f'<a href="../../index.html">All jobs</a><h1>{escaped(result["id"])}</h1><p>{escaped(result["status"])}: {escaped(result.get("classification", ""))}</p><div class="images">'
    for engine in ("legacy", "python", "published"):
        filename = f"{engine}-preview.jpg"
        if not (directory / filename).exists() and (directory / f"{engine}.jpg").exists():
            filename = f"{engine}.jpg"
        if (directory / filename).exists():
            target = f"{engine}.jpg" if (directory / f"{engine}.jpg").exists() else filename
            content += f'<figure><figcaption>{engine}</figcaption><a href="{target}"><img loading="lazy" src="{filename}" alt="{engine} poster"></a></figure>'
    content += '</div>' + review_summary(result)
    if result.get("shared_artifacts"):
        content += '<h2>Exact Caption Bounds and Wrapping</h2><div class="images">'
        for name in result["shared_artifacts"]:
            if name.endswith(".png"):
                relative = "../../" + name
                content += f'<figure><figcaption>{escaped(Path(name).name)}</figcaption><img loading="lazy" src="{escaped(relative)}" alt="Isolated caption" style="background:#333"></figure>'
        content += '</div>'
    for label, comparison in result["comparisons"].items():
        content += f'<h2>{escaped(label)}</h2><div class="images">'
        for name in [comparison.get("difference"), *comparison.get("text_crops", [])]:
            if name:
                content += f'<figure><figcaption>{escaped(name)}</figcaption><img loading="lazy" src="{escaped(name)}" alt="{escaped(name)}"></figure>'
        content += '</div>'
        content += '<details><summary>Technical comparison metrics</summary><pre>' + escaped(json.dumps(comparison_summary(comparison), indent=2)) + '</pre></details>'
    content += '<details><summary>Parameters, fonts, hashes and persistent measurements</summary><pre>' + escaped(json.dumps(result, indent=2)) + '</pre></details>'
    (directory / "index.html").write_text(page(result["id"], content), encoding="utf-8")


def aggregate(results, total):
    def groups(key):
        values = defaultdict(Counter)
        for result in results:
            label = result["category"] if key == "category" else ", ".join(result["font"]["family"])
            values[label][result["status"]] += 1
        return {key: dict(value) for key, value in sorted(values.items())}
    return {"expected_jobs": total, "completed_jobs": len(results), "remaining_jobs": total - len(results),
            "status": dict(Counter(result["status"] for result in results)),
            "rendered": {engine: sum(engine in result["images"] for result in results) for engine in ("legacy", "python")},
            "classifications": dict(Counter(result.get("classification", "unresolved discrepancy") for result in results)),
            "by_category": groups("category"), "by_font": groups("font"),
            "engine_seconds": {engine: sum(result["measurements"].get(engine, {}).get("seconds", 0) for result in results) for engine in ("legacy", "python")}}


def execution_coverage(manifest, results):
    completed = {row["id"] for row in results if row.get("complete")}
    paired = {row["id"] for row in results if row.get("complete")
              and set(row.get("images", {})) == {"legacy", "python"}
              and row.get("comparisons", {}).get("A-legacy-python", {}).get("comparable")}
    definitions = defaultdict(set)
    remaining = []
    by_category = defaultdict(Counter)
    for job in manifest["jobs"]:
        if job.get("source", {}).get("definition_line") is not None:
            definitions[job["definition_id"]].add(job["id"])
        state = "completed" if job["id"] in completed else "untested"
        by_category[job["category"]][state] += 1
        if state == "untested":
            remaining.append(job["id"])
    return {"manifest_sha256": manifest["sha256"], "completed_jobs": len(completed),
            "paired_jobs": len(paired), "untested_jobs": len(remaining), "untested_job_ids": remaining,
            "literal_rows_inventoried": manifest["covered_literal_definitions"],
            "literal_rows_fully_paired": sum(ids <= paired for ids in definitions.values()),
            "literal_rows_partially_paired": sum(bool(ids & paired) and not ids <= paired for ids in definitions.values()),
            "literal_rows_not_paired": sum(not ids & paired for ids in definitions.values()),
            "by_category": {key: dict(value) for key, value in sorted(by_category.items())}}


def dashboard(root, results, manifest, metadata):
    summary = aggregate(results, len(manifest["jobs"]))
    coverage = execution_coverage(manifest, results)
    atomic_json(root / "coverage.json", coverage)
    summary["execution_coverage"] = {key: value for key, value in coverage.items() if key != "untested_job_ids"}
    expected_fonts = Counter(", ".join(job["font"]["family"]) for job in manifest["jobs"])
    summary["font_coverage"] = {name: {"expected": count,
        "completed": sum(summary["by_font"].get(name, {}).values()),
        "untested": count - sum(summary["by_font"].get(name, {}).values())}
        for name, count in sorted(expected_fonts.items())}
    addendum = root / "provenance-addendum.json"
    if addendum.is_file():
        summary["provenance_addendum"] = json.loads(addendum.read_text())
    summary.update(literal_definitions=manifest["literal_definitions"], covered_literal_definitions=manifest["covered_literal_definitions"],
                   uncovered_literal_lines=manifest["uncovered_literal_lines"], metadata=metadata,
                   manifest_sha256=manifest["sha256"], expected_by_category=manifest["categories"],
                   source_hashes=manifest["source_hashes"], fonts=manifest["fonts"], translation=manifest["translation"],
                   same_queue_output_collisions=manifest["same_queue_output_collisions"],
                   storage_bytes=sum(path.stat().st_size for path in root.rglob("*") if path.is_file()))
    atomic_json(root / "summary.json", summary)
    content = '<h1>Phase 1 Frozen Full-Batch Validation</h1><p>Offline candidate validation. Not production approval; unresolved font provenance and visual flags require disposition.</p>'
    content += f'<p><strong>{summary["completed_jobs"]:,} / {summary["expected_jobs"]:,} jobs completed</strong>; {summary["remaining_jobs"]:,} untested. A-screen statuses: {html.escape(json.dumps(summary["status"]))}.</p>'
    content += f'<p>{manifest["covered_literal_definitions"]:,} / {manifest["literal_definitions"]:,} literal rows inventoried/resolved, not necessarily executed. {coverage["literal_rows_fully_paired"]:,} rows fully paired; {coverage["literal_rows_partially_paired"]:,} partially paired. Default English only. Published artwork comparisons are classified separately from the A-screen.</p>'
    content += '<p><a href="coverage.json">Exact execution coverage and all untested job IDs</a></p>'
    if (root / "STOP").exists():
        content += '<p><strong>Stopped at the user-requested resumable checkpoint. STOP remains in place; do not resume without explicit authorization.</strong></p>'
    if addendum.is_file():
        content += '<p><a href="provenance-addendum.json">Later hash-bound font provenance audit (does not change frozen render inputs)</a></p>'
    content += '<details><summary>Coverage, Versions, Hashes, Timing, Storage and Font Blockers</summary><pre>' + html.escape(json.dumps(summary, indent=2)) + '</pre></details>'
    content += '<details><summary>Results by Category</summary><table><tr><th>Category</th><th>Expected Jobs</th><th>Completed Statuses</th></tr>'
    for category, count in sorted(manifest["categories"].items()):
        content += f'<tr><td>{html.escape(category)}</td><td>{count:,}</td><td>{html.escape(json.dumps(summary["by_category"].get(category, {})))}</td></tr>'
    content += '</table></details><details><summary>Bulk Font Coverage: Tested and Not Yet Tested</summary><table><tr><th>Font</th><th>Expected</th><th>Completed</th><th>Untested</th></tr>'
    for font, counts in summary["font_coverage"].items():
        content += f'<tr><td>{html.escape(font)}</td><td>{counts["expected"]}</td><td>{counts["completed"]}</td><td>{counts["untested"]}</td></tr>'
    content += '</table></details>'
    content += '<p>Bulk font coverage is separate from the 126-case representative run, which sampled all 17 fonts. Fonts with no completed bulk jobs are untested here, not silently passing.</p>'
    content += '<p><a href="manifest.json.gz">Frozen manifest and input hashes</a></p>'
    for key, title in (("category", "Category"), ("font", "Font"), ("status", "Status")):
        values = sorted({", ".join(row["font"]["family"]) if key == "font" else row[key] for row in results})
        content += f'<label>{title} <select id="{key}"><option value="">All</option>' + ''.join(f'<option>{html.escape(value)}</option>' for value in values) + '</select></label> '
    content += '<p id="visible"></p><table><thead><tr><th>Job</th><th>Category / Font</th><th>Status / Classification</th><th>RGB MAE / Global SSIM</th></tr></thead><tbody>'
    worst = sorted(results, key=lambda row: (-{"failure": 2, "warning": 1, "pass": 0}[row["status"]], -row["comparisons"].get("A-legacy-python", {}).get("mean_absolute_error_0_255", 0)))
    for row in worst:
        font = ", ".join(row["font"]["family"])
        a = row["comparisons"].get("A-legacy-python", {})
        attributes = ' '.join(f'data-{key}="{html.escape(value, quote=True)}"' for key, value in (("category", row["category"]), ("font", font), ("status", row["status"])))
        content += f'<tr {attributes}><td><a href="cases/{row["id"]}/index.html">{html.escape(row["id"])}</a></td><td>{html.escape(row["category"])}<br>{html.escape(font)}</td><td>{row["status"]}<br>{html.escape(row.get("classification", ""))}</td><td>{a.get("mean_absolute_error_0_255", "n/a")}<br>{a.get("global_luminance_ssim_400x600", "n/a")}</td></tr>'
    content += '''</tbody></table><script>
const filters = ['category','font','status'].map(key => document.getElementById(key));
function filterRows(){let visible=0;document.querySelectorAll('tr[data-status]').forEach(row=>{
row.hidden=filters.some(control=>control.value && row.dataset[control.id]!==control.value);
if(!row.hidden)visible++;});document.getElementById('visible').textContent=visible+' jobs shown';}
filters.forEach(control=>control.addEventListener('change',filterRows));filterRows();
</script>'''
    (root / "index.html").write_text(page("Frozen Full-Batch Validation", content), encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--published-repo", type=Path, default=os.environ.get("DEFAULT_IMAGES_LOCAL_REPO"))
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--min-free-gb", type=float, default=5)
    parser.add_argument("--sample-interval", type=float, default=.25)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)
    if args.timeout < 1 or not .02 <= args.sample_interval <= 1 or (args.limit is not None and args.limit < 1):
        parser.error("Timeout and optional smoke-test limit must be positive")
    args.assets = ROOT
    args.report_dir = args.report_dir.resolve()
    if args.report_dir == ROOT or args.report_dir.is_relative_to(ROOT):
        parser.error("Report must be outside production assets")
    if args.published_repo:
        args.published_repo = Path(args.published_repo).resolve()
        if args.report_dir == args.published_repo or args.report_dir.is_relative_to(args.published_repo) or args.published_repo.is_relative_to(args.report_dir):
            parser.error("Report and read-only published repository must be disjoint")
    args.report_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(args.manifest)
    validate_manifest(manifest)
    target_manifest = args.report_dir / "manifest.json.gz"
    if target_manifest.exists():
        if load_manifest(target_manifest)["sha256"] != manifest["sha256"]:
            raise ValueError("Refusing to mix frozen manifests in one report")
    else:
        import gzip
        try:
            from .validation_manifest import canonical
        except ImportError:
            from validation_manifest import canonical
        target_manifest.write_bytes(gzip.compress(canonical(manifest), mtime=0))
    metadata_path = args.report_dir / "run.json"
    import_path = args.report_dir / "checkpoint-import.json"
    if import_path.exists() and not json.loads(import_path.read_text()).get("complete"):
        raise ValueError("Checkpoint import is incomplete; rendering must not start")
    if args.report_only:
        with exclusive_run(args.report_dir):
            results = [json.loads(path.read_text()) for path in (args.report_dir / "cases").glob("*/result.json")]
            for result in results:
                case_report(args.report_dir / "cases" / result["id"], result)
            dashboard(args.report_dir, results, manifest, json.loads(metadata_path.read_text()))
        return 0
    args.powershell, args.magick = shutil.which("pwsh"), shutil.which("magick")
    if not args.powershell or not args.magick:
        parser.error("Existing PowerShell 7 and ImageMagick are required; nothing will be installed")
    os.environ["POSTER_COMPARISON_MAGICK"] = args.magick
    current_published = published_state(args.published_repo)
    inputs = run_inputs(manifest, current_published, args.powershell, args.magick)
    run_key = fingerprint(inputs)
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text())
        if metadata["run_key"] != run_key:
            raise ValueError("Resume inputs/renderer versions changed; use a fresh report directory")
        if metadata.get("checkpoint_import") and digest(import_path) != metadata["checkpoint_import"]["audit_sha256"]:
            raise ValueError("Checkpoint import audit changed")
    else:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT.parent, text=True).strip()
        metadata = {**inputs, "run_key": run_key, "base_code_commit": commit, "validation_code_uncommitted": True,
                    "started_utc": datetime.now(timezone.utc).isoformat(), "workers": args.workers, "timeout_seconds": args.timeout}
        atomic_json(metadata_path, metadata)
    metadata.setdefault("invocations", []).append({"started_utc": datetime.now(timezone.utc).isoformat(),
        "workers": args.workers, "smoke_limit": args.limit, "retry_failed": args.retry_failed,
        "sampling_interval_seconds": args.sample_interval})
    metadata["workers"] = args.workers
    atomic_json(metadata_path, metadata)
    args.representatives = set()
    args.caption_lock = threading.Lock()
    args.caption_locks = {}
    args.required_parents = {entry["job_id"] for job in manifest["jobs"] for entry in job.get("generated_inputs", {}).values()}
    args.ambiguous_jobs = {job_id for collision in manifest["same_queue_output_collisions"] for job_id in collision["job_ids"]}
    seen = set()
    for job in manifest["jobs"]:
        if job["category"] not in seen:
            seen.add(job["category"])
            args.representatives.add(job["id"])
    results = []
    with exclusive_run(args.report_dir):
        if (args.report_dir / "STOP").exists():
            raise RuntimeError("Cooperative STOP file exists; inspect the interrupted run before explicitly removing it")
        workspaces = queue.Queue()
        for index in range(args.workers):
            workspace = inside(args.report_dir / "scratch" / str(index), args.report_dir)
            if not workspace.exists():
                prepare_legacy(ROOT / "create_poster.ps1", workspace, ROOT, args.magick)
            workspaces.put(workspace)
        def execute(job):
            workspace = workspaces.get()
            try:
                return render_job(job, args, workspace, run_key)
            finally:
                workspaces.put(workspace)
        started = time.perf_counter()
        selected = manifest["jobs"][:args.limit] if args.limit else manifest["jobs"]
        interrupted = False
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for level in dependency_levels(selected):
                # Workers are bounded. Generated inputs are ready before dependent jobs are admitted.
                for job, future in bounded_completed(pool, execute, level, args.workers, lambda: (args.report_dir / "STOP").exists()):
                    result, reused = future.result()
                    results.append(result)
                    print(f'[{len(results)}/{len(selected)}] {result["id"]}: {result["status"]}' + (" (resumed)" if reused else ""), flush=True)
                    if len(results) % 100 == 0:
                        dashboard(args.report_dir, results, manifest, metadata)
                    if (args.report_dir / "STOP").exists():
                        interrupted = True
                        break
                if (args.report_dir / "STOP").exists():
                    interrupted = True
                if interrupted:
                    break
        if interrupted:
            results = [json.loads(path.read_text()) for path in (args.report_dir / "cases").glob("*/result.json")]
            results = [result for result in results if result.get("run_key") == run_key and result.get("complete")]
        metadata["interrupted_cooperatively"] = interrupted
        metadata["last_invocation_seconds"] = time.perf_counter() - started
        validate_manifest(manifest)
        metadata["published_after"] = published_state(args.published_repo)
        metadata["finished_utc"] = datetime.now(timezone.utc).isoformat()
        metadata["published_unchanged"] = metadata["published_after"] == current_published
        atomic_json(metadata_path, metadata)
        summary = dashboard(args.report_dir, results, manifest, metadata)
        if not metadata["published_unchanged"]:
            raise RuntimeError("Published repository state changed during validation")
    print(json.dumps({key: summary[key] for key in ("expected_jobs", "completed_jobs", "remaining_jobs", "status", "rendered", "engine_seconds")}, indent=2))
    return 2 if interrupted else (1 if summary["status"].get("failure") else 0)


if __name__ == "__main__":
    raise SystemExit(main())
