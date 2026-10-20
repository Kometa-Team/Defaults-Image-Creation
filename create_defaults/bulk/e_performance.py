"""Bounded, opt-in real-workload scaling and isolated legacy launcher comparison."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from PIL import Image, ImageChops, ImageStat
from create_defaults.compare_poster_renderers import prepare_legacy, measured, invalid_legacy_font
from .catalog import load_catalog
from .common import BulkError, canonical, fingerprint, sha256, reject_links, confined
from .config import ROOT
from .e_validation import ResourceGuard, configuration, environment, save, summarize
from .generation import generate
from .generators import GENERATORS
from .planner import Planner, validate_manifest
from .translations import Translations
from .workers import WorkerLimits


def selected_workload(name):
    index = json.loads((ROOT / "bulk/catalog/index-v1.json").read_text())["posters"]
    families = {v["definition"] for k, v in index.items() if k != v["definition"]}
    by_category = lambda category: sorted(k for k, v in index.items() if v["category"] == category and k not in families)
    if name == "small":
        selected = by_category("Based")
    elif name == "medium":
        selected = by_category("Decade")
    elif name == "larger":
        selected = by_category("Chart")[:32]
    elif name == "dependencies":
        selected = sorted(k for k, v in index.items() if v["category"] == "Year" and v["dependencies"])[:6]
    elif name == "mixed":
        selected = [k for category in ("Based", "Genre", "Year", "Playlist")
                    for k in by_category(category)[:4]]
    else:
        raise BulkError("invalid_benchmark", "Unknown bounded workload")
    definitions = load_catalog(posters=selected)
    catalog, expanded_families, _ = Planner(generators=GENERATORS).expand(definitions)
    needed = set()
    def include(identity):
        if identity in needed:
            return
        needed.add(identity)
        for parent in catalog[identity].data["dependencies"]:
            include(parent["poster_id"])
    for identity in selected:
        for member in expanded_families.get(identity, [identity]):
            include(member)
    if len(needed) > 64:
        raise BulkError("benchmark_budget", "Representative benchmark exceeds its 64-output budget")
    return definitions, selected


def python_run(root, name, workers, repeat=0):
    definitions, selected = selected_workload(name)
    config = configuration(root)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    translated = Translations({"en": ROOT / "fixtures/english/en.yml"})
    runs, output_hashes = {}, None
    for temperature in ("cold", "warm"):
        with ResourceGuard(root, seconds=1800, max_output=2 * 1024 ** 3) as guard:
            start = time.monotonic()
            result = generate(definitions, translated, config=config, posters=selected,
                generators=GENERATORS, limits=WorkerLimits(workers=workers,
                    total_worker_memory_bytes=workers * 512 * 1024 ** 2), cancel=guard, policy="strict")
            duration = time.monotonic() - start
        save(root / (temperature + "-result.json"), result)
        if result["status"] != "verified":
            raise BulkError("benchmark_incomplete", "Bounded workload incomplete; retain partial evidence")
        runs[temperature] = summarize(result, duration)
        save(root / (temperature + "-summary.json"), runs[temperature])
        current = {j["id"]: sha256(config.output_dir / j["local_relative"]) for j in result["manifest"]["jobs"]}
        if output_hashes is not None and output_hashes != current:
            raise BulkError("cache_changed", "Warm run changed an output")
        output_hashes = current
        if temperature == "warm" and (runs[temperature]["executed"] or runs[temperature]["worker_starts"]):
            raise BulkError("benchmark_cache", "Warm run rendered or launched a worker")
    summary = {"workload": name, "workers": workers, "repeat": repeat, "runs": runs,
        "output_hashes": output_hashes, "environment": environment(),
        "scope": "Actual production-path Python generator; representative bounded subset, not full-category throughput except small/medium"}
    save(root / "summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("workload", "workers", "repeat")} |
        {"cold_seconds": runs["cold"]["wall_seconds"], "warm_seconds": runs["warm"]["wall_seconds"],
         "renders": runs["cold"]["executed"]}), flush=True)
    return summary


def legacy(root, python_root, *, powershell, magick, max_seconds=1800):
    root, python_root = reject_links(root).resolve(), Path(python_root).resolve()
    configuration(root)
    root.mkdir(parents=True, exist_ok=True)
    result = json.loads((python_root / "cold-result.json").read_text())
    manifest = validate_manifest(result["manifest"])
    if len(manifest["jobs"]) > 64:
        raise BulkError("legacy_budget", "Legacy comparison is limited to 64 explicitly selected posters")
    workspace = root / "workspace"
    if workspace.exists():
        raise BulkError("benchmark_exists", "Use a fresh legacy workspace; prior results are immutable")
    isolation = prepare_legacy(ROOT / "create_poster.ps1", workspace, ROOT, magick)
    # Force the existing bundled-font branch without changing rendering statements.
    script = workspace / "legacy.ps1"
    text = script.read_text(encoding="utf-8-sig")
    marker = "if ($visibleFonts -contains $fontName)"
    if text.count(marker) != 1:
        raise BulkError("legacy_isolation", "Font-resolution isolation marker changed")
    script.write_text(text.replace(marker, "if ($false -and $visibleFonts -contains $fontName)"), encoding="utf-8-sig")
    isolation["isolated_sha256"] = sha256(script)
    isolation["font_resolution"] = "Installed-font branch disabled; exact copied bundled font files only"
    before = {item["path"]: item["sha256"] for job in manifest["jobs"] for item in job["inputs"]}
    records, started = [], time.monotonic()
    old_magick = os.environ.get("POSTER_COMPARISON_MAGICK")
    os.environ["POSTER_COMPARISON_MAGICK"] = str(magick)
    try:
        for number, job in enumerate(manifest["jobs"]):
            if time.monotonic() - started >= max_seconds:
                break
            parameters = dict(job["parameters"])
            inputs = list(job["inputs"])
            for dep in job["dependencies"]:
                parent = next(j for j in manifest["jobs"] if j["id"] == dep["job_id"])
                inputs.append({"role": dep["input"], "path": parent["local_relative"],
                               "sha256": dep["sha256"], "generated": True})
            for item in inputs:
                if item["role"] not in {"logo", "avg_color_image", "font"}:
                    continue
                source = (python_root / "output" if item.get("generated") else ROOT) / item["path"]
                assert sha256(source) == item["sha256"]
                if item["role"] == "font":
                    parameters["font"] = source.stem
                else:
                    target = workspace / "inputs" / str(number) / source.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
                    assert sha256(target) == item["sha256"]
                    parameters[item["role"]] = str(target)
            parameters["out_name"] = "e-" + str(number)
            for key in ("logo_offset", "text_offset"):
                parameters[key] = f"{int(parameters.get(key, 0)):+d}"
            file = workspace / "parameters.json"
            file.write_bytes(canonical(parameters))
            (workspace / "output").mkdir(exist_ok=True)
            log = root / ("legacy-" + str(number) + ".log")
            measurement = measured([powershell, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", workspace / "run.ps1", "-ParameterFile", file], workspace, log, timeout=120)
            output = workspace / "output" / ("e-" + str(number) + ".jpg")
            log_text = log.read_text(encoding="utf-8-sig", errors="replace")
            valid = measurement["returncode"] == 0 and output.is_file() and not invalid_legacy_font(log_text)
            valid = valid and "[ERROR]" not in log_text and "magick.exe:" not in log_text
            if valid:
                with Image.open(output) as image:
                    image.load()
                    valid = image.format == "JPEG" and image.size == (2000, 3000)
            record = {"id": job["id"], "valid": valid, "measurement": measurement,
                      "sha256": sha256(output) if output.exists() else None}
            records.append(record)
            save(root / "progress.json", {"planned": len(manifest["jobs"]), "completed": len(records), "records": records})
            if not valid:
                raise BulkError("legacy_failed", "Legacy output or exact-font validation failed; no speedup claim")
    finally:
        if old_magick is None:
            os.environ.pop("POSTER_COMPARISON_MAGICK", None)
        else:
            os.environ["POSTER_COMPARISON_MAGICK"] = old_magick
    assert all(sha256(ROOT / path) == checksum for path, checksum in before.items())
    summary = {"complete": len(records) == len(manifest["jobs"]), "jobs": len(records),
        "planned": len(manifest["jobs"]), "elapsed_seconds": time.monotonic() - started,
        "renderer_seconds": sum(r["measurement"]["seconds"] for r in records),
        "isolation": isolation, "records": records,
        "limitations": ["Sequential independent PowerShell composer processes; production bulk bootstrap/translation/fitting orchestration not executed.",
            "Identical verified source/font bytes and specifications; generated parents use common verified Python parent bytes.",
            "Only output basenames redirected; no approved rendering statement changed.",
            "Magick/OMP thread limit 1, no updates, downloads, dependencies installed, upstream writes or approved-source edits.",
            "No general production speedup is inferred from incomplete or differently scoped workloads."]}
    save(root / "legacy-summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("complete", "jobs", "planned", "elapsed_seconds", "renderer_seconds")}), flush=True)
    return summary



def legacy_overlays(root, python_root, *, magick):
    """Run the captured mogrify operations on copied representative inputs."""
    root, python_root = reject_links(root).resolve(), reject_links(python_root).resolve()
    configuration(root)
    result = json.loads((python_root / "cold-result.json").read_text())
    manifest = validate_manifest(result["manifest"])
    jobs = manifest["jobs"]
    if not jobs or len(jobs) > 64 or any(j["kind"] != "overlay" for j in jobs):
        raise BulkError("legacy_budget", "Expected at most 64 explicit overlay contracts")
    workspace = root / "workspace"
    if workspace.exists():
        raise BulkError("benchmark_exists", "Use a fresh legacy overlay workspace")
    groups, original_hashes = {}, {}
    started = time.monotonic()
    for job in jobs:
        p = job["parameters"]
        source = confined(ROOT, p["input"], must_exist=True)
        checksum = job["inputs"][0]["sha256"]
        assert sha256(source) == checksum
        original_hashes[str(source)] = checksum
        key = (str(Path(job["local_relative"]).parent), p["trim"], tuple(p["box"]))
        groups.setdefault(key, []).append(job)
    operations, comparisons = [], []
    for number, ((destination, trim, box), members) in enumerate(sorted(groups.items())):
        if time.monotonic() - started > 600:
            raise BulkError("legacy_budget", "Legacy overlay comparison exceeded ten minutes")
        inputs, outputs = workspace / str(number) / "inputs", workspace / str(number) / "outputs"
        inputs.mkdir(parents=True); outputs.mkdir()
        for job in members:
            source = confined(ROOT, job["parameters"]["input"], must_exist=True)
            target = inputs / source.name
            shutil.copyfile(source, target)
            assert sha256(target) == job["inputs"][0]["sha256"]
        command = [magick, "mogrify", "-colorspace", "sRGB", "-strip"]
        if trim:
            command.append("-trim")
        command += ["-path", outputs, "-resize", f"{box[0]}x{box[1]}", *sorted(inputs.glob("*.png"))]
        measured_result = measured(command, workspace, root / f"operation-{number}.log", timeout=45)
        if measured_result["returncode"] or measured_result["timed_out"]:
            raise BulkError("legacy_failed", "Isolated legacy overlay operation failed")
        operations.append({"destination": destination, "trim": trim, "box": list(box),
                           "inputs": len(members), "measurement": measured_result})
        for job in members:
            old = outputs / Path(job["local_relative"]).name
            new = confined(python_root / "output", job["local_relative"], must_exist=True)
            with Image.open(old) as a, Image.open(new) as b:
                a.load(); b.load()
                assert a.format == b.format == "PNG"
                aa, bb = a.convert("RGBA"), b.convert("RGBA")
                row = {"id": job["id"], "path": job["local_relative"],
                    "source_sha256": job["inputs"][0]["sha256"],
                    "legacy_sha256": sha256(old), "python_sha256": sha256(new),
                    "legacy_dimensions": list(a.size), "python_dimensions": list(b.size),
                    "same_dimensions": a.size == b.size, "approval_granted": False}
                if a.size == b.size:
                    difference = ImageChops.difference(aa, bb)
                    means = ImageStat.Stat(difference).mean
                    row.update(exact_decoded_pixels=difference.getbbox(alpha_only=False) is None,
                        rgb_mae=sum(means[:3]) / 3, alpha_mae=means[3],
                        max_rgba_difference=max(v[1] for v in difference.getextrema()))
                comparisons.append(row)
    assert all(sha256(Path(path)) == checksum for path, checksum in original_hashes.items())
    save(root / "comparison-ledger.json", comparisons)
    summary = {"jobs": len(comparisons), "operations": len(operations), "complete": len(comparisons) == len(jobs),
        "elapsed_seconds": time.monotonic() - started,
        "renderer_seconds": sum(v["measurement"]["seconds"] for v in operations),
        "operations_evidence": operations, "comparison_ledger_sha256": fingerprint(comparisons),
        "dimension_differences": sum(not r["same_dimensions"] for r in comparisons),
        "exact_decoded_pixels": sum(r.get("exact_decoded_pixels", False) for r in comparisons),
        "new_visual_approvals": 0, "bulk_source_sha256": sha256(ROOT / "create_default_posters.ps1"),
        "limitations": ["Original mogrify flags and grouped operations on isolated copied inputs; bulk PowerShell bootstrap is not run.",
            "Overlay legacy path launches one mogrify per group/size, not one PowerShell process per image.",
            "Magick/OMP threads limited to one; bounded to 64 outputs, 45 seconds/operation and ten minutes total.",
            "Pillow/ImageMagick pixel differences are measured, not newly approved; previous Package D metrics stay immutable."]}
    save(root / "legacy-overlay-summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in {"operations_evidence", "limitations"}}), flush=True)
    return summary

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["python", "legacy", "legacy-overlays"])
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--workload", choices=["small", "medium", "larger", "dependencies", "mixed"], default="mixed")
    parser.add_argument("--workers", type=int, choices=[1, 2, 4], default=2)
    parser.add_argument("--repeat", type=int, default=0)
    parser.add_argument("--python-root", type=Path)
    parser.add_argument("--powershell", default=shutil.which("pwsh"))
    parser.add_argument("--magick", default=shutil.which("magick"))
    args = parser.parse_args(argv)
    if args.operation == "python":
        python_run(args.root, args.workload, args.workers, args.repeat)
    elif not args.python_root or not args.magick or (args.operation == "legacy" and not args.powershell):
        parser.error("legacy requires a completed Python workload and existing PowerShell/ImageMagick")
    elif args.operation == "legacy-overlays":
        legacy_overlays(args.root, args.python_root, magick=args.magick)
    else:
        legacy(args.root, args.python_root, powershell=args.powershell, magick=args.magick)


if __name__ == "__main__":
    main()
