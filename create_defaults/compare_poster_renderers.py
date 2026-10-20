"""Non-destructive, offline three-way poster comparisons and measurements."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageChops, ImageEnhance, __version__ as PILLOW_VERSION
import psutil

try:
    from .create_poster import ROOT, PosterOptions, digest, output_filename, load_image
    from .poster_fixtures import Case, build_cases, font_inventory, translation_file
    from .poster_text import FontLayout, resolve_font
except ImportError:
    from create_poster import ROOT, PosterOptions, digest, output_filename, load_image
    from poster_fixtures import Case, build_cases, font_inventory, translation_file
    from poster_text import FontLayout, resolve_font


def json_file(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")


def measured(command, cwd, log, timeout=120, sample_interval=.02):
    """Sample process-tree RSS and write counters; never launch through a shell."""
    started = time.perf_counter()
    peak, counters, timed_out = 0, {}, False
    environment = dict(os.environ, MAGICK_THREAD_LIMIT="1", OMP_NUM_THREADS="1")
    with Path(log).open("wb") as output:
        process = subprocess.Popen([str(v) for v in command], cwd=cwd, stdout=output, stderr=subprocess.STDOUT,
                                   env=environment, shell=False)
        tracked = psutil.Process(process.pid)
        while process.poll() is None:
            try:
                children = [tracked, *tracked.children(recursive=True)]
                memory = 0
                for child in children:
                    try:
                        memory += child.memory_info().rss
                        counters[child.pid] = max(counters.get(child.pid, 0), child.io_counters().write_bytes)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                peak = max(peak, memory)
            except psutil.NoSuchProcess:
                pass
            if time.perf_counter() - started > timeout:
                timed_out = True
                try:
                    descendants = tracked.children(recursive=True)
                except psutil.NoSuchProcess:
                    descendants = []
                for child in reversed(descendants):
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                process.kill()
                break
            time.sleep(sample_interval)
        code = process.wait()
    return {"seconds": time.perf_counter() - started, "returncode": code, "timed_out": timed_out,
            "sampling_interval_seconds": sample_interval,
            "sampled_peak_tree_rss_bytes": peak or None, "sampled_write_bytes": sum(counters.values()) or None,
            "command": [str(v) for v in command]}


def offline_legacy_copy(source, target, magick):
    """Retain every validation/render statement; omit only pre-start bootstrap.

    Original source remains byte-for-byte untouched. Marker checks fail closed
    when the legacy script changes, rather than executing update/install code.
    """
    text = Path(source).read_text(encoding="utf-8-sig")
    bootstrap, render = "##### PRE-START #####", '$random_name = ("{0:X6}"'
    if text.count(bootstrap) != 1 or text.count(render) != 1:
        raise ValueError("Legacy isolation markers changed; audit the composer before running it")
    before = text[:text.index(bootstrap)]
    body = text[text.index(render):]
    # magick is assigned through an environment variable, not interpolated code.
    setup = '\n$global:magick = $env:POSTER_COMPARISON_MAGICK\n$global:AutoUpdateIM = $false\n'
    copied = before + setup + body
    target.write_text(copied, encoding="utf-8-sig")
    return {"source_sha256": digest(source), "isolated_sha256": digest(target),
            "omitted": "PRE-START through random_name: version checks, self-update, Magick installation/update, host banner",
            "unchanged": "Parameter declarations, font resolution, validation, fades, composition, JPEG stages, naming, cleanup"}


def prepare_legacy(source, workspace, assets, magick):
    workspace.mkdir(parents=True, exist_ok=True)
    audit = offline_legacy_copy(source, workspace / "legacy.ps1", magick)
    shutil.copytree(assets / "fonts", workspace / "fonts")
    shutil.copytree(assets / "fades", workspace / "fades")
    shutil.copyfile(assets / "transparent.png", workspace / "transparent.png")
    wrapper = '''param([string]$ParameterFile)
$ErrorActionPreference = 'Stop'
$values = Get-Content -LiteralPath $ParameterFile -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable
. (Join-Path $PSScriptRoot 'legacy.ps1') @values
'''
    (workspace / "run.ps1").write_text(wrapper, encoding="utf-8-sig")
    return audit


def effective_parameters(case, magick, assets):
    parameters = dict(case.parameters)
    fit_metadata = None
    if case.fit and parameters.get("text") and magick:
        width, height, minimum, maximum = case.fit
        font = resolve_font(parameters["font"], assets / "fonts")
        command = [str(magick), "-size", f"{width}x{height}", "-font", font.as_posix(), "-gravity", "center",
                   "-fill", "black", "caption:" + parameters["text"], "-format", "%[caption:pointsize]", "info:"]
        completed = subprocess.run(command, capture_output=True, text=True, check=True, timeout=45,
                                   env=dict(os.environ, MAGICK_THREAD_LIMIT="1"))
        if "unable to read font" in completed.stderr.lower():
            raise ValueError("ImageMagick could not read the exact fitting font; refusing a substituted-font baseline")
        measured_size = int(float(completed.stdout.strip()))
        pointsize = min(maximum, max(minimum, measured_size))
        fit_metadata = {"command": command, "measured_pointsize": measured_size, "clamped": pointsize,
                        "note": "Read-only reproduction of bulk Get-OptimalPointSize; both composers receive this identical value"}
        # Legacy composer resets out-of-range values to 250 after bulk fitting.
        parameters["font_size"] = pointsize if 10 <= pointsize <= 500 else 250
        if pointsize != parameters["font_size"]:
            fit_metadata["composer_reset"] = 250
    return parameters, fit_metadata


def picture_metadata(path):
    with Image.open(path) as image:
        return {"path": str(path), "dimensions": image.size, "mode": image.mode, "format": image.format,
                "sha256": digest(path), "bytes": Path(path).stat().st_size}


def caption_diagnostics(parameters, font, directory, magick):
    size = int(parameters.get("font_size", 250))
    size = size if 10 <= size <= 500 else 250
    layout = FontLayout(font)
    caption, metadata = layout.caption(parameters["text"], size, parameters.get("font_color", "#FFFFFF"))
    caption.save(directory / "python-caption.png")
    metadata["centered_ink_bounds"] = caption.getchannel("A").getbbox()
    result = {"python": metadata, "note": "Compare original glyph scale/kerning and trimmed centered ink bounds; line baselines/advances are recorded for Python, original untrimmed baseline is not inferable from final legacy raster"}
    if magick:
        command = [str(magick), "-font", font.as_posix(), "-pointsize", str(size), "-fill", parameters.get("font_color", "#FFFFFF"),
                   "-gravity", "center", "-size", "1900x1000", "-background", "none", "caption:" + parameters["text"],
                   "-trim", "-gravity", "center", "-extent", "1900x1000", str(directory / "legacy-caption.png")]
        completed = subprocess.run(command, check=True, capture_output=True, timeout=45, env=dict(os.environ, MAGICK_THREAD_LIMIT="1"))
        if b"unable to read font" in completed.stderr.lower():
            raise ValueError("ImageMagick substituted a diagnostic font; comparison refused")
        with Image.open(directory / "legacy-caption.png") as image:
            bounds = image.convert("RGBA").getchannel("A").getbbox()
            result["legacy"] = {"centered_ink_bounds": bounds, "command": command}
            if bounds and metadata["centered_ink_bounds"]:
                result["ink_bound_deltas_python_minus_legacy"] = [a - b for a, b in zip(metadata["centered_ink_bounds"], bounds)]
    return result


def compare_images(first, second, directory, label, text_offset=0):
    alpha_metrics = {}
    with Image.open(first) as left, Image.open(second) as right:
        if left.size != right.size:
            return {"comparable": False, "reason": f"Dimension mismatch: {left.size} vs {right.size}"}
        transparent = any("A" in image.getbands() or "transparency" in image.info for image in (left, right))
        if transparent:
            left, right = left.convert("RGBA"), right.convert("RGBA")
            difference = ImageChops.difference(left.getchannel("A"), right.getchannel("A"))
            histogram = difference.histogram()
            pixels = left.width * left.height
            alpha_metrics = {"mean_absolute_alpha_error_0_255": sum(i * count for i, count in enumerate(histogram)) / pixels,
                             "changed_alpha_fraction": sum(histogram[1:]) / pixels,
                             "source_alpha_extrema": [left.getchannel("A").getextrema(), right.getchannel("A").getextrema()],
                             "alpha_difference": label + "-alpha-difference.png"}
            ImageEnhance.Contrast(difference).enhance(4).save(directory / alpha_metrics["alpha_difference"])
            # Hidden RGB is not visible color. Compare actual source-over output
            # on the same neutral background and report alpha error separately.
            background = Image.new("RGBA", left.size, (128, 128, 128, 255))
            left = Image.alpha_composite(background, left).convert("RGB")
            right = Image.alpha_composite(background, right).convert("RGB")
        else:
            left, right = left.convert("RGB"), right.convert("RGB")
    total = 0
    changed = 0
    histogram = np.zeros(256, dtype=np.int64)
    for y in range(0, left.height, 128):
        bounds = (0, y, left.width, min(left.height, y + 128))
        difference = np.abs(np.asarray(left.crop(bounds), dtype=np.int16) - np.asarray(right.crop(bounds), dtype=np.int16))
        total += int(difference.sum())
        changed += int(np.any(difference, axis=2).sum())
        histogram += np.bincount(difference.ravel(), minlength=256)
    mae = total / (left.width * left.height * 3)
    # Explicitly named global luminance SSIM screen, not local/windowed SSIM.
    a = np.asarray(left.resize((400, 600)).convert("L"), dtype=np.float64)
    b = np.asarray(right.resize((400, 600)).convert("L"), dtype=np.float64)
    cov = np.mean((a - a.mean()) * (b - b.mean()))
    ssim = ((2 * a.mean() * b.mean() + 6.5025) * (2 * cov + 58.5225)
            / ((a.mean() ** 2 + b.mean() ** 2 + 6.5025) * (a.var() + b.var() + 58.5225)))
    diff_name = label + "-difference.png"
    difference = ImageEnhance.Contrast(ImageChops.difference(left, right)).enhance(4)
    difference.thumbnail((666, 1000))
    difference.save(directory / diff_name)
    crop_height = min(left.height, 1000)
    top = max(0, min(left.height - crop_height, (left.height - crop_height) // 2 + int(text_offset)))
    margin = min(50, left.width // 40)
    crop = (margin, top, left.width - margin, top + crop_height)
    crop_names = []
    text_difference = ImageChops.difference(left.crop(crop), right.crop(crop))
    text_histogram = text_difference.histogram()
    text_mae = sum((i % 256) * count for i, count in enumerate(text_histogram)) / (text_difference.width * text_difference.height * 3)
    for index, image in enumerate((left, right)):
        name = f"{label}-text-{index}.png"
        image.crop(crop).resize((760, 400)).save(directory / name)
        crop_names.append(name)
    return {"comparable": True, "mean_absolute_error_0_255": mae, "global_luminance_ssim_400x600": float(ssim),
            "maximum_channel_difference_0_255": int(np.flatnonzero(histogram)[-1]),
            "channel_difference_p99_0_255": int(np.searchsorted(histogram.cumsum(), histogram.sum() * .99)),
            "meaningful_difference_definition": "p99 is the 99th percentile absolute RGB channel error; raw maximum is also retained",
            "text_region": {"bounds": crop, "mean_absolute_error_0_255": text_mae},
            "changed_pixel_fraction": changed / (left.width * left.height), "difference": diff_name,
            "text_crops": crop_names, "flag_for_review": bool(mae > 1.5 or ssim < .995 or alpha_metrics.get("mean_absolute_alpha_error_0_255", 0) > 1.5),
            "comparison_space": "RGBA source-over on #808080; hidden RGB excluded" if transparent else "RGB",
            **alpha_metrics,
            "note": "Screening thresholds flag review only; they cannot certify visual equivalence"}


def published_image(repository, relative):
    if not repository or not relative:
        return None
    for prefix in (Path(), Path("defaults-en"), Path("defaults") / "en"):
        path = repository / prefix / relative
        if path.is_file():
            return path
    return None


CSS = """body{font:15px system-ui,sans-serif;margin:24px;color:#202020;background:#fafafa;line-height:1.5}
a{color:#075e86} h1{font-size:26px} h2{font-size:20px} .images{display:flex;flex-wrap:wrap;gap:16px}
figure{margin:0;max-width:360px;min-width:220px;flex:1}img{max-width:100%;height:auto;background:#777}figcaption{font-weight:600}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eee;padding:12px}table{border-collapse:collapse;width:100%;table-layout:fixed}
td,th{text-align:left;border-bottom:1px solid #ccc;padding:8px;overflow-wrap:anywhere} .warning{color:#845100}.failure{color:#a02020}.pass{color:#17633f}
@media(max-width:600px){body{margin:12px}td,th{padding:4px;font-size:12px}h1{font-size:22px}}"""


def page(title, content):
    return f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}</style><body>{content}</body></html>'


def case_html(result, directory):
    try:
        from .validation_review import review_summary
    except ImportError:
        from validation_review import review_summary
    content = f'<a href="../index.html">All comparisons</a><h1>{html.escape(result["id"])}</h1><p class="{result["status"]}">{html.escape(result["status"])}: {html.escape("; ".join(result["notes"]))}</p><div class="images">'
    for engine in ("legacy", "python", "published"):
        if engine in result["images"]:
            name = result["images"][engine]["report_file"]
            content += f'<figure><figcaption>{engine}</figcaption><a href="{name}"><img src="{name}" alt="{engine} poster"></a></figure>'
    content += "</div>" + review_summary(result)
    if result.get("caption_diagnostics"):
        content += '<h2>Isolated Caption and Glyph Placement</h2><div class="images">'
        for engine in ("legacy", "python"):
            name = f"{engine}-caption.png"
            if (directory / name).exists():
                content += f'<figure><figcaption>{engine} caption</figcaption><img src="{name}" alt="{engine} isolated caption" style="background:#333"></figure>'
        content += '</div>'
    for label, comparison in result["comparisons"].items():
        content += f"<h2>{html.escape(label)}</h2>"
        if comparison.get("comparable"):
            content += '<div class="images">'
            for name in [comparison["difference"], *comparison["text_crops"], *([comparison["alpha_difference"]] if comparison.get("alpha_difference") else [])]:
                content += f'<figure><figcaption>{html.escape(name)}</figcaption><img src="{name}" alt="{html.escape(name)}"></figure>'
            content += "</div>"
        content += '<details><summary>Technical comparison metrics</summary><pre>' + html.escape(json.dumps(comparison, indent=2)) + '</pre></details>'
    content += '<details><summary>Parameters, fonts, hashes and measurements</summary><pre>' + html.escape(json.dumps(result, indent=2)) + '</pre></details>'
    (directory / "index.html").write_text(page(result["id"], content), encoding="utf-8")


def python_command(composer, parameters, assets, target):
    command = [sys.executable, str(composer), "--asset-dir", str(assets), "--output-path", str(target)]
    for name, value in parameters.items():
        if value is None:
            continue
        command.extend(["--" + name.replace("_", "-"), str(int(value)) if isinstance(value, bool) else str(value)])
    return command


def invalid_legacy_font(log):
    text = log.lower()
    return any(marker in text for marker in ("random font", "randomly selected", "unable to read font"))


def reuse_legacy(case, result, args, directory):
    entry = getattr(args, "legacy_cache", {}).get(case.id)
    if not entry or args.python_only:
        return False
    root, previous = entry
    # Resolve the allowed root as well as the candidate: Windows temp-directory
    # aliases/junctions may otherwise make an owned file appear outside its root.
    root = Path(root).resolve()
    if previous.get("parameters") != result["parameters"] or previous.get("input_hashes") != result["input_hashes"]:
        return False
    if previous.get("resolved_font", {}).get("sha256") != result.get("resolved_font", {}).get("sha256"):
        return False
    metadata = previous.get("images", {}).get("legacy")
    if not metadata:
        return False
    log = root / case.id / "legacy.log"
    if log.is_file() and invalid_legacy_font(log.read_text(encoding="utf-8-sig", errors="replace")):
        raise ValueError("Cached legacy output used an unreadable or random fallback font")
    source = (root / case.id / metadata["report_file"]).resolve()
    if not source.is_relative_to(root) or digest(source) != metadata["sha256"]:
        raise ValueError("Cached legacy image changed or escapes its local report")
    shutil.copyfile(source, directory / "legacy.jpg")
    result["images"]["legacy"] = dict(picture_metadata(directory / "legacy.jpg"), report_file="legacy.jpg",
                                         original_filename=metadata.get("original_filename"))
    result["legacy_reused_from"] = str(source)
    result["legacy_original_measurement"] = previous.get("measurements", {}).get("legacy")
    result["notes"].append("Earlier local legacy render reused after checking original composer, effective parameters, source hashes, font hash, and output hash; excluded from new runtime benchmark")
    return True


def run_case(case, args, workspace):
    if case.kind == "overlay-reference":
        return run_overlay_probe(case, args)
    directory = args.report_dir / case.id
    directory.mkdir()
    result = dict(id=case.id, category=case.category, kind=case.kind, source_line=case.source_line, source_row=case.source_row,
                  notes=list(case.notes), expected_failure=case.expected_failure, images={}, comparisons={}, measurements={})
    parameters, fit = effective_parameters(case, None if args.python_only else args.magick, args.assets)
    result.update(parameters=parameters, bulk_font_fitting=fit, expected_destination=case.published_relative)
    sources = [parameters.get(key) for key in ("logo", "avg_color_image", "dom_color_image") if parameters.get(key)]
    result["input_hashes"] = {str(p): digest(p) for p in sources if Path(p).is_file()}
    if parameters.get("text"):
        font = resolve_font(parameters.get("font"), args.assets / "fonts")
        result["resolved_font"] = {"path": str(font), "sha256": digest(font)}
    target = directory / "python.jpg"
    measurement = measured(python_command(args.python_composer, parameters, args.assets, target), ROOT.parent,
                           directory / "python.log", args.timeout)
    result["measurements"]["python"] = measurement
    if measurement["returncode"] == 0 and target.is_file():
        result["images"]["python"] = dict(picture_metadata(target), report_file=target.name)
        text = (directory / "python.log").read_text(encoding="utf-8", errors="replace")
        result["python_metadata"] = json.loads(text.splitlines()[-1])
    else:
        result["notes"].append("Python did not produce a poster: " + (directory / "python.log").read_text(encoding="utf-8", errors="replace")[-1000:])
    if not args.python_only and not reuse_legacy(case, result, args, directory):
        values = dict(parameters)
        for key in ("logo_offset", "text_offset"):
            values[key] = f"{int(values.get(key, 0)):+d}"
        values["font"] = Path(result["resolved_font"]["path"]).stem if "resolved_font" in result else parameters.get("font", "ComfortAa-Medium")
        # Both bodies see the same real source paths; only destinations/scratch
        # locations are redirected by PSScriptRoot to our private workspace.
        parameter_file = workspace / "parameters.json"
        json_file(parameter_file, values)
        command = [args.powershell, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", workspace / "run.ps1", "-ParameterFile", parameter_file]
        previous = list((workspace / "output").rglob("*.jpg")) if (workspace / "output").exists() else []
        for path in previous:
            path.unlink()
        relative = output_filename(PosterOptions(**parameters), parameters.get("base_color") or "#000000")
        (workspace / "output" / relative).parent.mkdir(parents=True, exist_ok=True)
        old_magick = os.environ.get("POSTER_COMPARISON_MAGICK")
        os.environ["POSTER_COMPARISON_MAGICK"] = str(args.magick)
        try:
            measurement = measured(command, workspace, directory / "legacy.log", args.timeout)
        finally:
            if old_magick is None:
                os.environ.pop("POSTER_COMPARISON_MAGICK", None)
            else:
                os.environ["POSTER_COMPARISON_MAGICK"] = old_magick
        result["measurements"]["legacy"] = measurement
        generated = list((workspace / "output").rglob("*.jpg")) if (workspace / "output").exists() else []
        legacy_log = (directory / "legacy.log").read_text(encoding="utf-8-sig", errors="replace")
        if measurement["returncode"] == 0 and len(generated) == 1 and "[ERROR]" not in legacy_log and "magick.exe:" not in legacy_log and not invalid_legacy_font(legacy_log):
            shutil.copyfile(generated[0], directory / "legacy.jpg")
            result["images"]["legacy"] = dict(picture_metadata(directory / "legacy.jpg"), report_file="legacy.jpg", original_filename=generated[0].relative_to(workspace / "output").as_posix())
        else:
            result["notes"].append("Legacy did not produce a valid poster; see legacy.log (exit code alone is insufficient)")
            if invalid_legacy_font(legacy_log):
                result["notes"].append("Unreadable/random legacy font fallback rejected; no substituted-font baseline accepted")
    published = published_image(args.published_repo, case.published_relative)
    if published:
        before = digest(published)
        shutil.copyfile(published, directory / "published.jpg")
        result["images"]["published"] = dict(picture_metadata(published), report_file="published.jpg")
        if digest(published) != before:
            raise RuntimeError("Published comparison source changed during read-only comparison")
    elif case.published_relative:
        result["notes"].append("Published counterpart unavailable at the recorded relative destination")
    for label, first, second in (("A-legacy-python", "legacy", "python"), ("B-legacy-published", "legacy", "published"), ("C-python-published", "python", "published")):
        if first in result["images"] and second in result["images"]:
            result["comparisons"][label] = compare_images(directory / result["images"][first]["report_file"], directory / result["images"][second]["report_file"], directory, label, parameters.get("text_offset", 0))
    if "python" in result["images"] and parameters.get("text"):
        result["caption_diagnostics"] = caption_diagnostics(parameters, Path(result["resolved_font"]["path"]), directory,
                                                              None if args.python_only else args.magick)
    a = result["comparisons"].get("A-legacy-python", {})
    b = result["comparisons"].get("B-legacy-published", {})
    c = result["comparisons"].get("C-python-published", {})
    if a.get("comparable") and not a.get("flag_for_review") and b.get("flag_for_review") and c.get("flag_for_review"):
        result["notes"].append("Both fresh engines differ from published artwork while agreeing with each other: historical artwork/configuration difference indicated, exact cause unproven; no code change made merely to chase it")
    engines = {"python"} if args.python_only else {"python", "legacy"}
    available = set(result["images"])
    if case.expected_failure and not engines.intersection(available):
        result["status"] = "warning"
        result["notes"].append("Expected legacy-input validation failure reproduced; no repaired baseline invented")
    elif not engines.issubset(available):
        result["status"] = "failure"
    elif args.python_only or not result["comparisons"] or any(not c.get("comparable") or c.get("flag_for_review") for c in result["comparisons"].values()):
        result["status"] = "warning"
    else:
        result["status"] = "pass"
    if "A-legacy-python" in result["comparisons"]:
        result["notes"].append("Pillow/HarfBuzz/FreeType rasterization, Lanczos kernels and JPEG intermediates require visual review even below thresholds")
    for path, before in result["input_hashes"].items():
        if digest(path) != before:
            raise RuntimeError(f"Source asset changed during comparison: {path}")
    json_file(directory / "result.json", result)
    case_html(result, directory)
    return result


def run_overlay_probe(case, args):
    directory = args.report_dir / case.id
    directory.mkdir()
    parameters = case.parameters
    source = Path(parameters["logo"])
    before = digest(source)
    image = load_image(source)
    if parameters["trim"]:
        bounds = image.getchannel("A").getbbox()
        if bounds:
            image = image.crop(bounds)
    image.thumbnail(tuple(parameters["size"]), Image.Resampling.LANCZOS, reducing_gap=None)
    image.save(directory / "python.png")
    result = dict(id=case.id, category=case.category, kind=case.kind, source_line=case.source_line,
                  parameters=parameters, expected_destination=case.published_relative, notes=list(case.notes),
                  input_hashes={str(source): before}, images={}, comparisons={}, measurements={})
    result["images"]["python"] = dict(picture_metadata(directory / "python.png"), report_file="python.png")
    if not args.python_only:
        size = parameters["size"]
        command = [str(args.magick), source.as_posix(), "-colorspace", "sRGB", "-strip"]
        if parameters["trim"]:
            command.append("-trim")
        command += ["-resize", f"{size[0]}x{size[1]}", str(directory / "legacy.png")]
        completed = subprocess.run(command, capture_output=True, check=True, timeout=45)
        result["legacy_command"] = command
        result["images"]["legacy"] = dict(picture_metadata(directory / "legacy.png"), report_file="legacy.png")
    published = published_image(args.published_repo, case.published_relative)
    if published:
        original = digest(published)
        shutil.copyfile(published, directory / "published.png")
        result["images"]["published"] = dict(picture_metadata(published), report_file="published.png")
        if digest(published) != original:
            raise RuntimeError("Published overlay changed during comparison")
    for label, first, second in (("A-legacy-python", "legacy", "python"), ("B-legacy-published", "legacy", "published"), ("C-python-published", "python", "published")):
        if first in result["images"] and second in result["images"]:
            result["comparisons"][label] = compare_images(directory / result["images"][first]["report_file"], directory / result["images"][second]["report_file"], directory, label)
    result["status"] = "warning" if args.python_only or any(not c.get("comparable") or c.get("flag_for_review") for c in result["comparisons"].values()) else "pass"
    if digest(source) != before:
        raise RuntimeError("Overlay input source changed")
    json_file(directory / "result.json", result)
    case_html(result, directory)
    return result


def index_report(args, results, inventory, audit, startup):
    for result in results:
        result["classification"] = classify_result(result)
    counts = {status: sum(r["status"] == status for r in results) for status in ("pass", "warning", "failure")}
    benchmarks = {}
    common = [r for r in results if not r.get("legacy_reused_from") and r.get("kind") != "overlay-reference" and {"legacy", "python"}.issubset(r["images"])]
    for engine in ("legacy", "python"):
        measurements = [r["measurements"][engine] for r in common]
        if measurements:
            benchmarks[engine] = {"identical_poster_count": len(measurements), "total_seconds": sum(m["seconds"] for m in measurements),
                                  "average_seconds": sum(m["seconds"] for m in measurements) / len(measurements),
                                  "maximum_sampled_tree_rss_bytes": max(m["sampled_peak_tree_rss_bytes"] or 0 for m in measurements),
                                  "sampled_write_bytes": sum(m["sampled_write_bytes"] or 0 for m in measurements),
                                  "output_bytes": sum(r["images"][engine]["bytes"] for r in common)}
    summary = {"counts": counts, "case_count": len(results), "benchmarks": benchmarks, "startup": startup,
               "reused_legacy_count": sum(bool(r.get("legacy_reused_from")) for r in results),
               "legacy_isolation": audit, "pillow": PILLOW_VERSION, "python": sys.version, "platform": sys.platform,
               "published_repo": str(args.published_repo) if args.published_repo else None,
               "measurement_notes": "Serial cold CLI processes, shared OS filesystem caches; 20ms process-tree RSS/write-counter samples are lower-bound observations, not allocator or kernel disk-write totals. Startup probes measure empty PowerShell startup and Python composer --help (imports), not equivalent workloads.",
               "acceptance": "NOT CERTIFIED: thresholds flag review only; material differences, missing baselines, font licenses and unsupported translations must be resolved before Phase 2.",
               "results": results}
    json_file(args.report_dir / "summary.json", summary)
    json_file(args.report_dir / "font-inventory.json", inventory)
    content = f'<h1>Default Poster Renderer Comparison</h1><p>{len(results)} cases: {counts["pass"]} pass screens, {counts["warning"]} warnings, {counts["failure"]} failures.</p><p>{html.escape(summary["acceptance"])}</p>'
    content += '<p><a href="summary.json">Full metrics and benchmark</a> | <a href="font-inventory.json">Font inventory and coverage</a> | <a href="manifest.json">Exact input manifest</a></p>'
    content += '<h2>Performance</h2>'
    if benchmarks:
        content += '<pre>' + html.escape(json.dumps(benchmarks, indent=2)) + '</pre>'
    else:
        content += '<p>No fresh paired poster timings: reused legacy outputs and overlay probes are excluded. Run a separate comparison without --legacy-baseline for benchmarks.</p>'
    content += '<p>' + summary["measurement_notes"] + '</p>'
    content += '<h2>Cases</h2><table><tr><th>Case</th><th>Category</th><th>Status</th><th>Legacy/Python MAE</th><th>Review Notes</th></tr>'
    for result in results:
        mae = result["comparisons"].get("A-legacy-python", {}).get("mean_absolute_error_0_255")
        metric = f"{mae:.4f}" if mae is not None else "unavailable"
        content += f'<tr><td><a href="{result["id"]}/index.html">{html.escape(result["id"])}</a></td><td>{html.escape(result["category"])}</td><td class="{result["status"]}">{result["status"]}</td><td>{metric}</td><td>{html.escape("; ".join(result["notes"]))}</td></tr>'
    content += '</table>'
    (args.report_dir / "index.html").write_text(page("Default Poster Renderer Comparison", content), encoding="utf-8")
    return summary


def classify_result(result):
    comparisons = result.get("comparisons", {})
    a = comparisons.get("A-legacy-python", {})
    if not a.get("comparable"):
        return "unresolved discrepancy"
    if a.get("flag_for_review"):
        return "Python migration difference"
    if "published" not in result.get("images", {}):
        return "missing published counterpart" if result.get("expected_destination") else "synthetic stress case; no published counterpart expected"
    if any(comparisons.get(name, {}).get("flag_for_review") for name in ("B-legacy-published", "C-python-published")):
        font = Path(result.get("resolved_font", {}).get("path", "")).name
        return "approved font replacement" if font in {"BebasNeue-Regular.ttf", "PlusJakartaSans-Bold.ttf"} else "existing historical artwork difference"
    return "expected image-encoding difference"


def refresh_report(directory, recompute_metrics=False):
    """Refresh derived report data; never invoke renderers or change their images."""
    directory = Path(directory).resolve(strict=True)
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    inventory = json.loads((directory / "font-inventory.json").read_text(encoding="utf-8"))
    cache = {}
    for result in summary["results"]:
        if not re.fullmatch(r"[a-z0-9-]+", result["id"]):
            raise ValueError("Invalid case identifier in report")
        case_directory = directory / result["id"]
        if case_directory.is_symlink() or not case_directory.resolve().is_relative_to(directory):
            raise ValueError("Case report directory escapes report root")
        observations = {}
        for source, before in result.get("input_hashes", {}).items():
            if source not in cache:
                if digest(source) != before:
                    raise ValueError(f"Source has changed since the render: {source}")
                image = load_image(source)
                counts = image.getchannel("A").histogram()
                cache[source] = {"dimensions": image.size, "alpha_extrema": image.getchannel("A").getextrema(),
                                 "transparent_pixels": counts[0], "partially_transparent_pixels": sum(counts[1:255]),
                                 "opaque_pixels": counts[255], "sha256": before}
            observations[source] = cache[source]
        result["input_image_observations"] = observations
        if recompute_metrics:
            for label, first, second in (("A-legacy-python", "legacy", "python"), ("B-legacy-published", "legacy", "published"), ("C-python-published", "python", "published")):
                if first in result["images"] and second in result["images"]:
                    paths = []
                    for engine in (first, second):
                        metadata = result["images"][engine]
                        path = (case_directory / metadata["report_file"]).resolve()
                        if not path.is_relative_to(case_directory.resolve()) or digest(path) != metadata["sha256"]:
                            raise ValueError("Rendered report image changed or escapes the case directory")
                        paths.append(path)
                    result["comparisons"][label] = compare_images(*paths, case_directory, label, result.get("parameters", {}).get("text_offset", 0))
            if result["status"] != "failure":
                missing = result.get("expected_destination") and "published" not in result["images"]
                result["status"] = "warning" if missing or "A-legacy-python" not in result["comparisons"] or any(not c.get("comparable") or c.get("flag_for_review") for c in result["comparisons"].values()) else "pass"
        result["classification"] = classify_result(result)
        if result["classification"] == "approved font replacement":
            result["notes"] = [note for note in result["notes"] if not note.startswith("Both fresh engines differ from published artwork")]
            note = "Fresh engines agree; published artwork predates the approved Bebas Neue or fixed-size Jakarta replacement"
            if note not in result["notes"]:
                result["notes"].append(note)
        json_file(case_directory / "result.json", result)
        case_html(result, case_directory)
    args = SimpleNamespace(report_dir=directory, published_repo=summary.get("published_repo"))
    index_report(args, summary["results"], inventory, summary["legacy_isolation"], summary["startup"])
    return directory / "index.html"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-composer", type=Path, default=ROOT / "create_poster.ps1")
    parser.add_argument("--python-composer", type=Path, default=ROOT / "create_poster.py")
    parser.add_argument("--assets", type=Path, default=ROOT)
    parser.add_argument("--published-repo", type=Path, default=os.getenv("DEFAULT_IMAGES_LOCAL_REPO"))
    parser.add_argument("--report-dir", type=Path, default=os.getenv("DEFAULT_POSTER_COMPARISON_DIR"))
    parser.add_argument("--powershell", default=shutil.which("pwsh") or shutil.which("powershell"))
    parser.add_argument("--magick", type=Path, default=shutil.which("magick"))
    parser.add_argument("--python-only", action="store_true")
    parser.add_argument("--case-filter", default="")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--complex-font", type=Path, help="Explicit licensed Arabic-capable font for additional shaping probes; never replaces a category font")
    parser.add_argument("--refresh-report", type=Path, help="Refresh HTML/alpha observations for a completed report; no images are rerendered")
    parser.add_argument("--recompute-metrics", action="store_true", help="With --refresh-report, recompute diagnostics from preserved rendered images")
    parser.add_argument("--legacy-baseline", type=Path, action="append", default=[], help="Reuse only verified legacy outputs from an earlier local comparison; repeat for multiple reports. Reused renders are excluded from runtime benchmarks.")
    args = parser.parse_args(argv)
    if args.refresh_report:
        print(f"Refreshed derived report only: {refresh_report(args.refresh_report, args.recompute_metrics)}")
        return 0
    args.assets = args.assets.resolve()
    args.python_composer = args.python_composer.resolve()
    args.legacy_composer = args.legacy_composer.resolve()
    args.published_repo = args.published_repo.resolve() if args.published_repo else None
    if args.published_repo and not args.published_repo.is_dir():
        parser.error("Published repository does not exist; it is never cloned or downloaded automatically")
    if not args.python_only and (not args.powershell or not args.magick):
        parser.error("Legacy comparison requires existing PowerShell and ImageMagick; neither will be installed automatically")
    if not args.report_dir:
        args.report_dir = ROOT.parent / "config" / "default-poster-comparisons" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    args.report_dir = args.report_dir.resolve()
    if args.published_repo and args.report_dir.is_relative_to(args.published_repo):
        parser.error("Reports must not be written inside the read-only published repository")
    if args.report_dir.exists():
        parser.error("Report directory already exists; use a fresh isolated destination")
    rows, cases = build_cases(args.assets)
    if args.complex_font:
        font = args.complex_font.resolve(strict=True)
        base = next(c for c in cases if c.category == "Genre")
        for label, caption in (("arabic-short", "\u0627\u0644\u0639\u0631\u0628\u064a\u0629"),
                               ("arabic-long", "\u0627\u0644\u0623\u0641\u0644\u0627\u0645 \u0648\u0627\u0644\u0645\u0633\u0644\u0633\u0644\u0627\u062a \u0627\u0644\u062a\u0644\u0641\u0632\u064a\u0648\u0646\u064a\u0629 \u0627\u0644\u0639\u0631\u0628\u064a\u0629"),
                               ("arabic-mixed", "TV 2026 \u0627\u0644\u0639\u0631\u0628\u064a\u0629"),
                               ("arabic-multiline", "\u0627\u0644\u0639\u0631\u0628\u064a\u0629\\n123")):
            cases.append(Case("complex-" + label, "Explicit shaping probe", dict(base.parameters, font=str(font), text=caption, font_size=200),
                              base.source_line, base.source_row, notes=["Explicit locally licensed test font only; not a replacement for missing Cairo or any category font; binary is not copied into source control"]))
    cases = [c for c in cases if args.case_filter in c.id]
    if args.limit is not None:
        cases = cases[:args.limit]
    if not cases:
        parser.error("No fixtures selected")
    args.report_dir.mkdir(parents=True)
    inventory = font_inventory(rows, args.assets)
    args.legacy_cache = {}
    for baseline in args.legacy_baseline:
        baseline = baseline.resolve(strict=True)
        previous = json.loads((baseline / "summary.json").read_text(encoding="utf-8"))
        if previous.get("legacy_isolation", {}).get("source_sha256") != digest(args.legacy_composer):
            raise ValueError("Legacy comparison source changed; a fresh baseline is required")
        for result in previous["results"]:
            if not re.fullmatch(r"[a-z0-9-]+", result["id"]):
                raise ValueError("Invalid cached comparison identifier")
            args.legacy_cache.setdefault(result["id"], (baseline, result))
    protected = [args.legacy_composer, ROOT / "create_default_posters.ps1", args.python_composer, ROOT / "poster_text.py",
                 *(args.assets / "fonts").glob("*.ttf"), *(args.assets / "fades").glob("*.png")]
    original_hashes = {str(p): digest(p) for p in protected}
    manifest = {"bulk_sha256": digest(ROOT / "create_default_posters.ps1"), "translation_sha256": digest(translation_file(args.assets)),
                "cases": [asdict(c) for c in cases], "source_hashes": original_hashes}
    json_file(args.report_dir / "manifest.json", manifest)
    results, startup = [], {}
    startup["python_help"] = measured([sys.executable, str(args.python_composer), "--help"], ROOT.parent, args.report_dir / "python-startup.log")
    if not args.python_only:
        startup["powershell_empty"] = measured([args.powershell, "-NoLogo", "-NoProfile", "-Command", "exit 0"], ROOT.parent, args.report_dir / "legacy-startup.log")
    with tempfile.TemporaryDirectory(prefix=".legacy-", dir=args.report_dir) as temporary:
        workspace = Path(temporary)
        audit = {} if args.python_only else prepare_legacy(args.legacy_composer, workspace, args.assets, args.magick)
        for index, case in enumerate(cases, 1):
            try:
                result = run_case(case, args, workspace)
            except Exception as error:
                directory = args.report_dir / case.id
                directory.mkdir(exist_ok=True)
                result = {"id": case.id, "category": case.category, "status": "failure", "notes": [f"{type(error).__name__}: {error}"],
                          "images": {}, "comparisons": {}, "measurements": {}}
                json_file(directory / "result.json", result)
                case_html(result, directory)
            results.append(result)
            index_report(args, results, inventory, audit, startup)
            print(f"[{index}/{len(cases)}] {case.id}: {result['status']}", flush=True)
    for path, before in original_hashes.items():
        if digest(path) != before:
            raise RuntimeError(f"Protected legacy/font/fade asset changed: {path}")
    print(f"Report: {args.report_dir / 'index.html'}")
    return 1 if any(r["status"] == "failure" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
