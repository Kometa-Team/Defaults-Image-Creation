#!/usr/bin/env python3
"""Read-only Adobe/local-remover benchmark with a portable review report.

Examples (paths may be relative):
  python compare_background_removers.py --originals /data/original --adobe /data/transparent --prepare-only
  python compare_background_removers.py --originals /data/original --adobe /data/transparent --limit 3
  python compare_background_removers.py --originals /data/original --adobe /data/transparent --all

--categories accepts {"images": [{"original": "person.jpg", "categories":
["wispy hair"], "priority": true}]}. These are reviewer-supplied labels, not
inferred hair/skin attributes. --sample-manifest replays a generated manifest.

--provenance accepts {"records": [{"original": "person.jpg", "adobe":
"person.png", "source": "person.jpg", "source_sha256": "...",
"adobe_sha256": "...", "submitted_to_adobe": true, "evidence":
"upload-log.txt", "evidence_sha256": "..."}]}. Source paths are relative to
--staging (or --originals); evidence paths are relative to the manifest.
Verification checks bytes and this explicit submission attestation. It cannot
authenticate the historical claim in a user-supplied log/manifest.

Reports flag diagnostics for inspection. Adobe is a baseline, not ground truth.
No weights are loaded in --prepare-only/--report-only/--validate-only mode.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import gc
import hashlib
import importlib
from importlib import metadata
import io
import json
import logging
import math
import os
import platform
from pathlib import Path, PurePosixPath
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata

from PIL import Image, ImageChops, ImageStat, features

SCRIPT_DIR = Path(__file__).resolve().parent
MODELS = ("birefnet-portrait", "birefnet-general", "isnet-general-use")
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
REVIEW_CHOICES = ("Adobe better", "BiRefNet Portrait better", "BiRefNet General better",
                  "ISNet General better", "Equivalent", "All unacceptable", "Needs review")
WINNERS = {"Adobe better": "adobe", "BiRefNet Portrait better": MODELS[0],
           "BiRefNet General better": MODELS[1], "ISNet General better": MODELS[2]}
REVIEW_ELIGIBLE_STATUSES = ("baseline", "processed", "skipped", "existing")
LOG = logging.getLogger("background_benchmark")


def helper_module(name: str):
    return importlib.import_module(f"{__package__}.{name}" if __package__ else name)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def environment_details() -> dict:
    versions = {}
    for package in ("Pillow", "rembg", "onnxruntime", "onnxruntime-gpu", "psutil"):
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    return {"python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
            "processor": platform.processor(), "logical_cpus": os.cpu_count(), "packages": versions,
            "thread_environment": {name: os.getenv(name) for name in
                                   ("OMP_NUM_THREADS", "OMP_WAIT_POLICY", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                    "NUMEXPR_NUM_THREADS", "ORT_NUM_THREADS")}}


def normalized(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\\", "/")).casefold()


def path_key(value: str) -> str:
    return normalized(str(PurePosixPath(value.replace("\\", "/")).with_suffix("")))


def contained(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def safe_relative(root: Path, relative: str) -> Path:
    rel = PurePosixPath(relative.replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts or ":" in relative:
        raise ValueError(f"Expected a repository-relative path: {relative}")
    result = (root / Path(*rel.parts)).resolve()
    if not contained(result, root.resolve()):
        raise ValueError(f"Path escapes source root: {relative}")
    return result


def validate_roots(originals: Path, adobe: Path, output: Path, staging: Path | None = None,
                   home: Path | None = None, extra_inputs: tuple[Path, ...] = ()) -> None:
    protected = [originals.resolve(), adobe.resolve(), *[p.resolve() for p in extra_inputs]]
    if staging:
        protected.append(staging.resolve())
    for key in ("SEL_SRC_DIR", "SEL_ORIG_DIR", "SEL_DOWNLOAD_DIR", "PEOPLE_IMAGES_DIR", "POSTER_DIR"):
        if os.getenv(key):
            protected.append(Path(os.environ[key]).expanduser().resolve())
    for writable in [output.resolve(), *([home.resolve()] if home else [])]:
        for root in protected:
            if contained(writable, root) or contained(root, writable):
                raise ValueError(f"Writable path {writable} overlaps protected input/production path {root}")
    # Reject symlink/junction children too, before any output writes.
    for writable in [output, *([home] if home else [])]:
        if writable.exists():
            for child in writable.rglob("*"):
                if not contained(child.resolve(), writable.resolve()):
                    raise ValueError(f"Output/cache contains a link outside its root: {child}")


def inventory(root: Path) -> list[Path]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Image root is not a readable directory: {root}")
    files = []
    def on_error(exc):
        raise exc
    for directory, folders, names in os.walk(root, onerror=on_error, followlinks=False):
        folders[:] = sorted(f for f in folders if not f.startswith("."))
        for name in names:
            path = Path(directory) / name
            if path.suffix.lower() in EXTENSIONS:
                if not contained(path.resolve(), root):
                    raise ValueError(f"Reference image escapes root: {path}")
                files.append(path)
    return sorted(files, key=lambda p: (normalized(p.relative_to(root).as_posix()), p.as_posix()))


def match_images(originals: Path, adobe: Path) -> dict:
    """Prefer relative paths; only fall back to globally unique basenames."""
    originals, adobe = originals.resolve(), adobe.resolve()
    sources, outputs = inventory(originals), inventory(adobe)
    indexes = []
    issues = []
    for label, root, files in (("original", originals, sources), ("adobe", adobe, outputs)):
        paths, names = defaultdict(list), defaultdict(list)
        for path in files:
            paths[path_key(path.relative_to(root).as_posix())].append(path)
            names[normalized(path.stem)].append(path)
        for key, values in names.items():
            if len(values) > 1:
                issues.append({"kind": "duplicate_filename", "tree": label, "key": key,
                               "paths": [p.relative_to(root).as_posix() for p in values]})
        indexes.append((paths, names))
    matches, used, blocked = [], set(), set()
    for source in sources:
        relative = source.relative_to(originals).as_posix()
        key, name = path_key(relative), normalized(source.stem)
        candidates = indexes[1][0].get(key, [])
        confidence = "relative-path"
        own = indexes[0][0].get(key, [])
        if not candidates:
            candidates = indexes[1][1].get(name, [])
            own = indexes[0][1].get(name, [])
            confidence = "unique-basename"
        if len(own) > 1 or len(candidates) > 1:
            blocked.update(candidates)
            issues.append({"kind": "ambiguous_match", "original": relative,
                           "candidates": [p.relative_to(adobe).as_posix() for p in candidates]})
        elif not candidates:
            issues.append({"kind": "missing_adobe", "original": relative})
        else:
            target = candidates[0]
            used.add(target)
            matches.append({"original": relative, "adobe": target.relative_to(adobe).as_posix(),
                            "path_confidence": confidence})
    # A relative-path match and a basename fallback must not claim the same output.
    counts = Counter(row["adobe"] for row in matches)
    clean = []
    for row in matches:
        if counts[row["adobe"]] > 1:
            issues.append({"kind": "ambiguous_match", **row})
        else:
            clean.append(row)
    for target in outputs:
        if target not in used and target not in blocked:
            issues.append({"kind": "missing_original", "adobe": target.relative_to(adobe).as_posix()})
    return {"original_count": len(sources), "adobe_count": len(outputs), "matches": clean, "issues": issues}


def read_records(path: Path | None, key: str) -> list[dict]:
    if path is None:
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = data.get(key) if isinstance(data, dict) else data
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"{path} requires a {key} list of objects")
    return rows


def record_index(rows: list[dict]) -> dict:
    result = {}
    for row in rows:
        key = normalized(row["original"])
        if key in result:
            raise ValueError(f"Duplicate manifest entry: {row['original']}")
        result[key] = row
    return result


def source_details(match: dict, originals: Path, adobe: Path, staging: Path | None,
                   provenance: dict, evidence_root: Path, staging_index: dict | None = None) -> dict:
    source = safe_relative(originals, match["original"])
    notes = ["Exact Adobe submission is unverified; colorization, cropping or canvas changes may differ."]
    record = provenance.get(normalized(match["original"]))
    confidence, evidence = "source-unverified", None
    if record:
        source = safe_relative(staging or originals, record["source"])
        try:
            artifact = safe_relative(evidence_root, record["evidence"])
            checks = (record.get("submitted_to_adobe") is True,
                      normalized(record["adobe"]) == normalized(match["adobe"]),
                      sha256(source) == record.get("source_sha256"),
                      sha256(safe_relative(adobe, match["adobe"])) == record.get("adobe_sha256"),
                      sha256(artifact) == record.get("evidence_sha256"))
            if not all(checks):
                raise ValueError("Submission attestation/path/hash mismatch")
            confidence, notes = "verified-source", []
            evidence = {"artifact": str(artifact), "sha256": record["evidence_sha256"],
                        "basis": "User-supplied submission attestation and matching source/output/evidence hashes"}
        except (OSError, ValueError, KeyError) as exc:
            notes.append(f"Provenance verification failed: {exc}")
            if not source.is_file():
                source = safe_relative(originals, match["original"])
                notes.append("Submitted source artifact unavailable; repository original retained.")
    elif staging:
        if staging_index is None:
            staging_index = defaultdict(list)
            for path in inventory(staging):
                staging_index[path_key(path.relative_to(staging).as_posix())].append(path)
        candidates = staging_index.get(path_key(match["original"]), [])
        if len(candidates) == 1:
            source = candidates[0]
            notes.append("Preserved staging image selected; basename/path alone is not submission evidence.")
        elif len(candidates) > 1:
            notes.append("Ambiguous staging paths; repository original retained.")
    return {**match, "source": str(source), "source_confidence": confidence,
            "provenance": evidence, "warnings": notes}


def select_sample(rows: list[dict], limit: int = 100, seed: int = 42,
                  all_images: bool = False, categories: list[dict] | None = None) -> list[dict]:
    if limit < 1:
        raise ValueError("--limit must be positive; use --all for full-library processing")
    labels = record_index(categories or [])
    known = {normalized(row["original"]) for row in rows}
    missing = set(labels) - known
    if missing:
        raise ValueError(f"Category manifest entries have no unambiguous match: {sorted(missing)}")
    annotated = []
    for row in rows:
        item = labels.get(normalized(row["original"]), {})
        cats = item.get("categories", [])
        if not isinstance(cats, list) or not all(isinstance(c, str) and c for c in cats):
            raise ValueError("categories must be a list of nonempty reviewer-supplied labels")
        annotated.append({**row, "categories": sorted(set(cats)), "priority": bool(item.get("priority", False))})
    def order(row):
        digest = hashlib.sha256(f"{seed}:{normalized(row['original'])}".encode("utf-8")).hexdigest()
        return (row["source_confidence"] != "verified-source", digest, row["original"])
    ordered = sorted(annotated, key=order)
    if all_images:
        return ordered
    chosen = [r for r in ordered if r["priority"]]
    if len(chosen) > limit:
        raise ValueError("Priority examples exceed --limit; increase it or revise the category manifest")
    covered = {c for r in chosen for c in r["categories"]}
    for category in sorted({c for r in ordered for c in r["categories"]}):
        if category not in covered and len(chosen) < limit:
            item = next(r for r in ordered if category in r["categories"])
            chosen.append(item)
            covered.update(item["categories"])
    for row in ordered:
        if len(chosen) >= limit:
            break
        if row not in chosen:
            chosen.append(row)
    return chosen


def image_metrics(path: Path, expected_size: tuple[int, int] | None = None,
                  baseline: Path | None = None, face_checks: bool = False) -> dict:
    result = {"valid": False, "dimensions": None, "metrics": {}, "warnings": [], "errors": []}
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
            result["dimensions"] = list(image.size)
            has_alpha = "A" in image.getbands()
            result["metrics"]["alpha_channel"] = has_alpha
            if image.format != "PNG" or image.mode != "RGBA":
                result["errors"].append("Output must be RGBA PNG")
            if expected_size and image.size != tuple(expected_size):
                result["errors"].append("Dimensions differ from selected source; possible transform/poster canvas")
            rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        hist, count = alpha.histogram(), rgba.width * rgba.height
        alpha_min, alpha_max = alpha.getextrema()
        coverage = sum(hist[9:]) / count
        soft = sum(hist[1:255]) / count
        result["metrics"].update(foreground_coverage=coverage, soft_alpha_fraction=soft,
                                 alpha_min=alpha_min, alpha_max=alpha_max,
                                 alpha_mean=sum(i * n for i, n in enumerate(hist)) / (count * 255),
                                 background_fraction=sum(hist[:247]) / count)
        if alpha_min == alpha_max:
            result["errors"].append("Uniform alpha mask has no foreground/background separation")
        if coverage < 0.005:
            result["errors"].append("Empty/nearly empty foreground mask")
        if sum(hist[:247]) / count < 0.0001:
            result["errors"].append("Opaque/nearly opaque mask")
        if coverage > 0.98:
            result["warnings"].append("Excessive foreground coverage")
        soft_mask = alpha.point(lambda a: 255 if 0 < a < 255 else 0)
        luminous = rgba.convert("RGB").convert("L")
        extreme = luminous.point(lambda v: 255 if v <= 20 or v >= 235 else 0)
        soft_count = sum(soft_mask.histogram()[255:])
        halo = ImageChops.multiply(soft_mask, extreme).histogram()[255] / soft_count if soft_count else 0.0
        result["metrics"]["halo_soft_extreme_fraction"] = halo
        result["metrics"]["potential_halo"] = halo > 0.5 and soft > 0.001
        if result["metrics"]["potential_halo"]:
            result["warnings"].append("Potential halo: extreme RGB on soft-alpha pixels; light/dark hair may also trigger")
        edge = helper_module("edge_chop").detect_edge_chops(path, edges=("top", "left", "right"))
        result["metrics"]["edge_contact"] = edge.coverages()
        result["metrics"]["potential_clipping"] = bool(edge.issues)
        result["metrics"]["clipping_edges"] = list(edge.issues)
        if edge.error:
            result["warnings"].append(f"Edge check unavailable: {edge.error}")
        elif edge.issues:
            result["warnings"].append("Potential head/shoulder clipping: " + helper_module("edge_chop").issue_summary(edge))
        if face_checks:
            try:
                face = helper_module("face_crop")
                model_path = face._model_path()
                if not model_path.is_file() or model_path.stat().st_size <= 1024:
                    raise ValueError("cached face detector unavailable (no download attempted)")
                crop = face.detect_face_crop_issues(path)
                result["metrics"]["face_crop_issues"] = list(crop.issues)
                if crop.error:
                    raise ValueError(crop.error)
                if crop.issues:
                    result["metrics"]["potential_clipping"] = True
                    result["warnings"].append(face.face_crop_summary(crop))
            except (ImportError, OSError, ValueError) as exc:
                result["warnings"].append(f"Face crop check unavailable: {exc}")
        else:
            result["warnings"].append("Face detector not enabled; clipping uses edge-contact heuristic")
        if baseline:
            try:
                with Image.open(baseline) as reference:
                    reference.load()
                    if "A" not in reference.getbands() or reference.size != rgba.size:
                        raise ValueError("Adobe alpha absent or dimensions incompatible; masks were not resized")
                    other = reference.getchannel("A")
                mask = alpha.point(lambda a: 255 if a >= 128 else 0)
                reference_mask = other.point(lambda a: 255 if a >= 128 else 0)
                intersection = ImageChops.darker(mask, reference_mask).histogram()[255]
                union = ImageChops.lighter(mask, reference_mask).histogram()[255]
                result["metrics"]["mask_iou_adobe"] = intersection / union if union else None
                result["metrics"]["alpha_disagreement_adobe"] = ImageStat.Stat(ImageChops.difference(alpha, other)).mean[0] / 255
            except (OSError, ValueError) as exc:
                result["warnings"].append(f"Adobe comparison unavailable: {exc}")
        result["valid"] = not result["errors"]
    except Exception as exc:
        result["errors"].append(f"Integrity/diagnostics check failed: {exc}")
    return result


class PeakRSS:
    """Sample process RSS, including model initialization; not Python allocator peak."""
    def __init__(self):
        self.peak = None
        self.error = None
        self._stop = threading.Event()
        self._thread = None

    def __enter__(self):
        try:
            import psutil
            self._process = psutil.Process()
            self._sample()
            self._thread = threading.Thread(target=self._poll, daemon=True)
            self._thread.start()
        except (ImportError, OSError) as exc:
            self.error = f"RSS unavailable: {exc}; install optional psutil for sampled process memory"
        return self

    def _sample(self):
        rss = self._process.memory_info().rss
        self.peak = max(self.peak or 0, rss)

    def _poll(self):
        while not self._stop.wait(0.05):
            try:
                self._sample()
            except Exception as exc:
                self.error = f"RSS sampling stopped: {exc}"
                break

    def __exit__(self, *_args):
        self._stop.set()
        if self._thread:
            self._thread.join()
            try:
                self._sample()
            except Exception as exc:
                self.error = f"Final RSS sample unavailable: {exc}"


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     suffix=".tmp", delete=False) as handle:
        tmp = Path(handle.name)
        json.dump(value, handle, ensure_ascii=True, indent=2, allow_nan=False)
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def checked_copy(source: Path, destination: Path, expected_hash: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256(destination) != expected_hash:
            raise ValueError(f"Existing benchmark input differs: {destination}; choose a fresh output directory")
        return
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
        tmp = Path(handle.name)
    try:
        shutil.copyfile(source, tmp)
        if sha256(tmp) != expected_hash or sha256(source) != expected_hash:
            raise ValueError(f"Reference changed during snapshot: {source}")
        tmp.replace(destination)
    finally:
        tmp.unlink(missing_ok=True)


def load_reviews(path: Path | None) -> dict:
    if path is None:
        return {}
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    else:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = data.get("reviews", []) if isinstance(data, dict) else data
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("Review import requires a list of objects")
    result = {}
    for row in rows:
        identity, choice = row.get("id"), row.get("result", "")
        if not isinstance(identity, str) or not identity:
            raise ValueError("Review ID must be a nonempty string")
        if identity in result or choice not in ("", *REVIEW_CHOICES):
            raise ValueError(f"Duplicate/invalid review: {identity}")
        result[identity] = {"result": choice, "notes": str(row.get("notes", ""))}
    return result


def review_eligible(row: dict, choice: str) -> bool:
    if choice not in ("", *REVIEW_CHOICES):
        return False
    engine = WINNERS.get(choice)
    if engine is None:
        return True
    output = row.get("outputs", {}).get(engine, {})
    return (isinstance(output.get("path"), str) and bool(output["path"])
            and output.get("status") in REVIEW_ELIGIBLE_STATUSES)


def validate_reviews(rows: list[dict], reviews: dict) -> None:
    by_id = {row["id"]: row for row in rows}
    for identity, review in reviews.items():
        if identity not in by_id:
            raise ValueError(f"Review ID {identity} is outside the selected benchmark")
        row, choice = by_id[identity], review.get("result", "")
        if not review_eligible(row, choice):
            engine = WINNERS.get(choice)
            status = row.get("outputs", {}).get(engine, {}).get("status", "missing")
            raise ValueError(f"Review '{choice}' for {row['original']} is unavailable (status={status}). "
                             "Choose an available output, Equivalent, All unacceptable, or Needs review.")


def aggregate_results(rows: list[dict], reviews: dict | None = None) -> dict:
    reviews = reviews or {}
    groups = {}
    for confidence in ("verified-source", "source-unverified"):
        selected = [r for r in rows if r["source_confidence"] == confidence]
        reviewed = [(r, reviews.get(r["id"], {})) for r in selected
                    if reviews.get(r["id"], {}).get("result") in REVIEW_CHOICES
                    and review_eligible(r, reviews[r["id"]]["result"])]
        ignored = sum(reviews.get(r["id"], {}).get("result") in REVIEW_CHOICES
                      and not review_eligible(r, reviews[r["id"]]["result"]) for r in selected)
        decisive = [(r, v) for r, v in reviewed if v["result"] != "Needs review"]
        counts = Counter(v["result"] for _, v in reviewed)
        engines = {}
        for engine in ("adobe", *MODELS):
            records = [r["outputs"][engine] for r in selected if engine in r.get("outputs", {})]
            attempted = [v for v in records if v.get("status") != "not-run"]
            durations = [v["duration"] for v in attempted
                         if v.get("status") == "processed" and isinstance(v.get("duration"), (int, float))
                         and math.isfinite(v["duration"]) and v["duration"] >= 0]
            durations.extend(v["historical_duration"] for v in attempted
                             if v.get("status") == "existing" and isinstance(v.get("historical_duration"), (int, float))
                             and math.isfinite(v["historical_duration"]) and v["historical_duration"] >= 0)
            wins = sum(WINNERS.get(v["result"]) == engine for _, v in decisive)
            defects = Counter()
            for record in attempted:
                metrics = record.get("metrics", {})
                if metrics.get("potential_halo"):
                    defects["potential_halo"] += 1
                if metrics.get("potential_clipping"):
                    defects["potential_clipping"] += 1
            engines[engine] = {"attempted": len(attempted), "wins": wins,
                               "win_percentage": 100 * wins / len(decisive) if decisive else None,
                               "failure_percentage": 100 * sum(not v.get("valid", False) for v in attempted) / len(attempted) if attempted else None,
                               "average_runtime": statistics.mean(durations) if durations else None,
                               "median_runtime": statistics.median(durations) if durations else None,
                               "runtime_samples": len(durations), "edge_defects": dict(defects)}
        category_wins = defaultdict(Counter)
        for row, review in decisive:
            winner = WINNERS.get(review["result"])
            if winner:
                for category in row.get("categories", []):
                    category_wins[category][winner] += 1
        groups[confidence] = {"images": len(selected), "actually_reviewed": len(reviewed),
                              "ignored_reviews": ignored,
                              "decisive_reviews": len(decisive), "review_results": dict(counts),
                              "engines": engines, "category_wins": {k: dict(v) for k, v in category_wins.items()}}
    return groups


def data_uri(path: Path) -> str:
    # Preserve compressed sources; PNG previews may use byte-exact lossless WebP.
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(image.format)
        if mime:
            encoded = path.read_bytes()
            color_metadata = any(key in image.info for key in ("gamma", "chromaticity"))
            if (image.format == "PNG" and image.mode in {"RGB", "RGBA", "L", "LA", "P"}
                    and features.check("webp") and (not color_metadata or image.info.get("icc_profile"))):
                rgba = image.convert("RGBA")
                try:
                    with io.BytesIO() as handle:
                        options = {key: image.info[key] for key in ("icc_profile", "exif") if image.info.get(key)}
                        rgba.save(handle, format="WEBP", lossless=True, exact=True, method=0, quality=0, **options)
                        candidate = handle.getvalue()
                    if len(candidate) < len(encoded):
                        with Image.open(io.BytesIO(candidate)) as restored:
                            recovered = restored.convert("RGBA")
                            try:
                                equal = recovered.size == rgba.size and recovered.tobytes() == rgba.tobytes()
                            finally:
                                recovered.close()
                        if equal:
                            encoded, mime = candidate, "image/webp"
                        else:
                            LOG.warning("Keeping original PNG: lossless WebP pixel verification failed for %s", path)
                except (KeyError, OSError, ValueError) as exc:
                    LOG.warning("Keeping original PNG: WebP unavailable for %s (%s)", path, exc)
                finally:
                    rgba.close()
            return "data:" + mime + ";base64," + base64.b64encode(encoded).decode("ascii")
        image.load()
        with io.BytesIO() as handle:
            image.convert("RGBA").save(handle, format="PNG")
            return "data:image/png;base64," + base64.b64encode(handle.getvalue()).decode("ascii")


REPORT_TEMPLATE = r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Background Removal Benchmark</title>
<style>
*{box-sizing:border-box}body{font:14px system-ui,sans-serif;margin:0;color:#202423;background:#f5f6f5;letter-spacing:0}
header{padding:16px 20px;background:#fff;border-bottom:1px solid #b9c2bf}h1{font-size:22px;margin:0 0 10px}h2{font-size:17px}
.tools{display:flex;gap:10px;flex-wrap:wrap;align-items:center}label{display:flex;gap:5px;align-items:center}select,input,button,textarea{font:inherit}
.paging{display:flex;flex-wrap:wrap;align-items:center;gap:12px;padding:8px 0}.bottom-page{padding:12px 20px}button:disabled{cursor:default;opacity:.5}
button,select,input{padding:6px;border:1px solid #929e9a;border-radius:3px;background:white}button{cursor:pointer}
main{padding:0 20px}section{padding:20px 0;border-bottom:1px solid #b9c2bf}.images{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
figure{margin:0;min-width:0}figcaption{margin-bottom:5px;font-weight:600}.image{height:340px;overflow:auto;background:#fff}
.image img{display:block;width:100%;height:100%;object-fit:contain;cursor:zoom-in}.image.zoom img{width:auto;height:auto;max-width:none}
.checker .image,.checker .scroll{background-color:#fff;background-image:conic-gradient(#ddd 25%,#fff 0 50%,#ddd 0 75%,#fff 0);background-size:20px 20px}
.white .image,.white .scroll{background:#fff}.black .image,.black .scroll{background:#000}.kometa .image,.kometa .scroll{background-image:var(--kometa);background-size:cover;background-position:center}
.review{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.review textarea{min-height:44px;flex:1;min-width:180px}
.details{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;margin:6px 0}.warning{color:#9a3814}#summary{overflow:auto;margin:8px 0}table{border-collapse:collapse;font-size:12px;width:100%}th,td{text-align:left;padding:5px 8px;border-bottom:1px solid #ddd;white-space:nowrap}details{margin:5px 0}summary{cursor:pointer}
dialog{max-width:96vw;max-height:95vh;padding:8px}dialog img{display:block;max-width:none}dialog .scroll{overflow:auto;max-width:90vw;max-height:85vh}
@media(max-width:600px){main{padding:0 10px}.image{height:300px}header{padding:12px}.images{grid-template-columns:1fr}}
</style>
<header><h1>Background Removal Benchmark</h1><div class="tools">
<label>Background <select id="background"><option value="checker">Checkerboard</option><option value="white">White</option><option value="black">Black</option><option value="kometa">Kometa</option></select></label>
<label>Model <select id="model"><option value="">All</option></select></label>
<label>Category <select id="category"><option value="">All</option></select></label>
<label>Flags <select id="flag"><option value="">All</option><option value="invalid">Validation failure</option><option value="clipping">Suspected clipping</option><option value="halo">Potential halo</option><option value="unverified">Unverified source</option></select></label>
<label>Review <select id="reviewFilter"><option value="">All</option><option value="unreviewed">Unreviewed</option></select></label>
<button id="jsonExport">Export JSON</button><button id="csvExport">Export CSV</button><label>Import reviews <input id="import" type="file" accept=".json,.csv"></label>
</div><p id="status" role="status"></p><div id="summary"></div><details><summary>Aggregate details</summary><pre id="aggregateDetails" class="details"></pre></details><details><summary>Benchmark evidence</summary><pre id="evidence" class="details"></pre></details>
<nav class="paging" aria-label="Portrait pages"><button id="previousPage">Previous</button><span id="pageStatus" aria-live="polite"></span><button id="nextPage">Next</button><label>Page size <select id="pageSize"><option value="8">8</option><option value="24">24</option><option value="all">All</option></select></label></nav></header>
<main id="samples" class="checker"></main><nav class="paging bottom-page" aria-label="Portrait pages"><button id="previousPageBottom">Previous</button><span id="pageStatusBottom"></span><button id="nextPageBottom">Next</button></nav><dialog id="full"><button id="close">Close</button><div class="scroll"><img id="fullImage" alt="Full resolution portrait"></div></dialog>
__ASSETS__<script type="application/json" id="data">__DATA__</script><script>
'use strict';
const data=JSON.parse(document.getElementById('data').textContent), $=id=>document.getElementById(id), allowed=data.review_choices;
let reviews={...data.reviews},pageIndex=0,PAGE_SIZE=8;const key='kometa-background-review:'+data.dataset_id;
function imageAsset(id){return id?$(id)?.content.querySelector('img'):null;}
function eligibleChoice(row,choice){if(choice!==''&&!allowed.includes(choice))return false;const engine=data.winners[choice];if(!engine)return true;const output=row?.outputs?.[engine];return typeof output?.path==='string'&&output.path.length>0&&data.review_eligible_statuses.includes(output.status);}
function basicReview(r){return r && typeof r.id==='string' && data.images.some(x=>x.id===r.id) && (r.result===''||allowed.includes(r.result)) && typeof (r.notes??'')==='string';}
function validReview(r){return basicReview(r)&&eligibleChoice(data.images.find(x=>x.id===r.id),r.result);}
let ignoredSaved=0;for(const [id,review] of Object.entries(reviews))if(!validReview({id,...review})){delete reviews[id];ignoredSaved++;}
try{const saved=JSON.parse(localStorage.getItem(key)||'[]');if(Array.isArray(saved))for(const r of saved){if(validReview(r))reviews[r.id]={result:r.result,notes:r.notes||''};else ignoredSaved++;}}catch(e){$('status').textContent='Browser storage unavailable. Export JSON or CSV to retain reviews.';}
if(ignoredSaved)$('status').textContent=`Ignored ${ignoredSaved} unavailable/invalid saved reviews. Choose an available output, Equivalent, All unacceptable, or Needs review.`;
function persist(){try{localStorage.setItem(key,JSON.stringify(reviewRows()));$('status').textContent='Reviews stored in this browser. JSON and CSV exports are available.';}catch(e){$('status').textContent='Browser storage unavailable. Export JSON or CSV to retain reviews.';}}
function reviewRows(){return data.images.map(x=>({id:x.id,original:x.original,source_confidence:x.source_confidence,result:reviews[x.id]?.result||'',notes:reviews[x.id]?.notes||''}));}
function summarize(){const groups={};for(const confidence of ['verified-source','source-unverified']){const images=data.images.filter(x=>x.source_confidence===confidence), reviewed=images.filter(x=>allowed.includes(reviews[x.id]?.result)&&eligibleChoice(x,reviews[x.id].result)),ignored=images.filter(x=>allowed.includes(reviews[x.id]?.result)&&!eligibleChoice(x,reviews[x.id].result)).length,decisive=reviewed.filter(x=>reviews[x.id].result!=='Needs review');const engines={};for(const model of data.models){const records=images.map(x=>x.outputs[model]).filter(x=>x&&x.status!=='not-run'), times=records.map(x=>x.status==='processed'?x.duration:x.status==='existing'?x.historical_duration:null).filter(x=>Number.isFinite(x)&&x>=0).sort((a,b)=>a-b),wins=decisive.filter(x=>data.winners[reviews[x.id].result]===model).length;engines[model]={wins,win_percentage:decisive.length?100*wins/decisive.length:null,failure_percentage:records.length?100*records.filter(x=>!x.valid).length/records.length:null,average_runtime:times.length?times.reduce((a,b)=>a+b,0)/times.length:null,median_runtime:times.length?(times[Math.floor((times.length-1)/2)]+times[Math.floor(times.length/2)])/2:null,edge_defects:{potential_halo:records.filter(x=>x.metrics?.potential_halo).length,potential_clipping:records.filter(x=>x.metrics?.potential_clipping).length}};}const categories={};for(const x of decisive){const winner=data.winners[reviews[x.id].result];if(winner)for(const c of x.categories){categories[c]??={};categories[c][winner]=(categories[c][winner]||0)+1;}}groups[confidence]={images:images.length,actually_reviewed:reviewed.length,ignored_reviews:ignored,decisive_reviews:decisive.length,engines,category_wins:categories};}return groups;}
function updateSummary(){const groups=summarize(),table=document.createElement('table'),head=document.createElement('tr');for(const name of ['Source confidence','Selected / reviewed','Engine','Wins','Failures','Mean / median s','Peak RSS MiB']){const cell=document.createElement('th');cell.textContent=name;head.append(cell);}table.append(head);const number=v=>Number.isFinite(v)?v.toFixed(2):'n/a';for(const [confidence,group] of Object.entries(groups)){const active=Object.entries(group.engines).filter(([engine])=>data.models.includes(engine));for(const [index,[engine,stats]] of active.entries()){const row=document.createElement('tr'),values=[index===0?confidence:'',index===0?`${group.images} / ${group.actually_reviewed}`:'',engine,`${stats.wins} (${number(stats.win_percentage)}%)`,number(stats.failure_percentage)+'%',number(stats.average_runtime)+' / '+number(stats.median_runtime),number(data.model_runs[engine]?.peak_rss_bytes/1048576)];for(const value of values){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}table.append(row);}}$('summary').replaceChildren(table);$('aggregateDetails').textContent=JSON.stringify(groups,null,2);}
function option(select,value){const el=document.createElement('option');el.value=value;el.textContent=value;select.append(el);if(select.getAttribute('aria-label')?.startsWith('Review ')){const row=data.images.find(x=>select.getAttribute('aria-label')==='Review '+x.original);el.disabled=!eligibleChoice(row,value);}}
for(const m of data.models)option($('model'),m);for(const c of [...new Set(data.images.flatMap(x=>x.categories))].sort())option($('category'),c);for(const r of allowed)option($('reviewFilter'),r);
const kometa=imageAsset(data.kometa_background_asset_id);
if(!kometa)$('background').querySelector('[value="kometa"]').disabled=true;else document.documentElement.style.setProperty('--kometa',`url("${kometa.src}")`);
$('evidence').textContent=JSON.stringify({limitations:data.limitations,model_runs:data.model_runs,inventory:data.inventory_summary},null,2);
function visible(x){const model=$('model').value,cat=$('category').value,flag=$('flag').value,review=$('reviewFilter').value;const outputs=Object.entries(x.outputs).filter(([m])=>!model||m===model).map(([,v])=>v);return(!cat||x.categories.includes(cat))&&(!review||(review==='unreviewed'?!reviews[x.id]?.result:reviews[x.id]?.result===review))&&(!flag||(flag==='unverified'?x.source_confidence==='source-unverified':flag==='invalid'?outputs.some(v=>v.status!=='not-run'&&!v.valid):outputs.some(v=>v.metrics?.[flag==='halo'?'potential_halo':'potential_clipping'])));}
function render(){const main=$('samples'),filtered=data.images.filter(visible);pageIndex=Math.min(pageIndex,Math.max(0,Math.ceil(filtered.length/PAGE_SIZE)-1));const start=pageIndex*PAGE_SIZE,shown=filtered.slice(start,start+PAGE_SIZE);for(const id of ['pageStatus','pageStatusBottom'])$(id).textContent=filtered.length?`${start+1}-${start+shown.length} / ${filtered.length}`:'0 / 0';for(const id of ['previousPage','previousPageBottom'])$(id).disabled=pageIndex===0;for(const id of ['nextPage','nextPageBottom'])$(id).disabled=start+PAGE_SIZE>=filtered.length;main.className=$('background').value;main.replaceChildren();for(const x of shown){const section=document.createElement('section'),title=document.createElement('h2');title.textContent=x.original+' | '+x.source_confidence;section.append(title);const note=document.createElement('p');note.className='warning';note.textContent=[...x.warnings,...x.categories].join(' | ');section.append(note);const grid=document.createElement('div');grid.className='images';for(const [model,out] of [['original',x.original_asset],...Object.entries(x.outputs).filter(([m])=>!$('model').value||m===$('model').value)]){const fig=document.createElement('figure'),caption=document.createElement('figcaption');caption.textContent=model;fig.append(caption);const frame=document.createElement('div');frame.className='image';const asset=imageAsset(out.asset_id);if(asset){const img=asset.cloneNode();img.alt=x.original+' '+model;img.title='Open full resolution';img.loading='lazy';img.onclick=()=>{ $('fullImage').src=img.src;$('full').className=$('background').value;$('full').showModal();};img.ondblclick=()=>frame.classList.toggle('zoom');frame.append(img);}else frame.textContent=out.errors?.join('; ')||out.status||'Unavailable';fig.append(frame);const brief=document.createElement('p');brief.className='details';const runtime=Number.isFinite(out.duration)?out.duration:out.historical_duration;brief.textContent=[out.status,out.dimensions?.join(' x '),Number.isFinite(runtime)?runtime.toFixed(2)+' s':''].filter(Boolean).join(' | ');fig.append(brief);const disclosure=document.createElement('details'),summary=document.createElement('summary'),info=document.createElement('pre');summary.textContent='Metrics and warnings';info.className='details';info.textContent=JSON.stringify({model_identifier:out.model_identifier,historical_duration:out.historical_duration,metrics:out.metrics,warnings:out.warnings,errors:out.errors},null,2);disclosure.append(summary,info);fig.append(disclosure);grid.append(fig);}section.append(grid);const controls=document.createElement('div');controls.className='review';const choice=document.createElement('select');choice.setAttribute('aria-label','Review '+x.original);option(choice,'');choice.options[0].textContent='Unreviewed';for(const v of allowed)option(choice,v);choice.value=reviews[x.id]?.result||'';const notes=document.createElement('textarea');notes.setAttribute('aria-label','Notes '+x.original);notes.value=reviews[x.id]?.notes||'';const save=()=>{reviews[x.id]={result:choice.value,notes:notes.value};persist();updateSummary();};choice.onchange=()=>{save();if($('reviewFilter').value)render();};notes.oninput=save;controls.append(choice,notes);section.append(controls);main.append(section);}updateSummary();}
for(const id of ['background','model','category','flag','reviewFilter'])$(id).onchange=()=>{if(id!=='background')pageIndex=0;render();};$('close').onclick=()=>{$('full').close();$('fullImage').removeAttribute('src');};
for(const id of ['previousPage','previousPageBottom','nextPage','nextPageBottom'])$(id).onclick=()=>{pageIndex+=id.startsWith('previous')?-1:1;render();window.scrollTo(0,0);};
$('pageSize').onchange=()=>{PAGE_SIZE=$('pageSize').value==='all'?Math.max(1,data.images.length):Number($('pageSize').value);pageIndex=0;render();};
function download(name,content,type){const url=URL.createObjectURL(new Blob([content],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('jsonExport').onclick=()=>download('reviews.json',JSON.stringify({dataset_id:data.dataset_id,reviews:reviewRows(),aggregates:summarize()},null,2),'application/json');
const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
$('csvExport').onclick=()=>{const columns=['id','original','source_confidence','result','notes'];download('reviews.csv','\ufeff'+[columns.map(quote).join(','),...reviewRows().map(r=>columns.map(c=>quote(r[c])).join(','))].join('\r\n'),'text/csv;charset=utf-8');};
function parseCSV(text){text=text.replace(/^\uFEFF/,'');const rows=[];let row=[],cell='',quoted=false;for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}else if(c===','&&!quoted){row.push(cell);cell='';}else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);rows.push(row);row=[];cell='';}else cell+=c;}if(quoted)throw Error('Unclosed CSV quote');if(cell||row.length){row.push(cell);rows.push(row);}const columns=rows.shift()||[];if(!columns.includes('id')||!columns.includes('result'))throw Error('Missing review columns');return rows.filter(r=>r.length>1).map(r=>Object.fromEntries(columns.map((c,i)=>[c,r[i]||''])));}
$('import').onchange=async event=>{try{const file=event.target.files[0];if(!file)return;const text=await file.text();let rows;if(file.name.toLowerCase().endsWith('.csv'))rows=parseCSV(text);else{const obj=JSON.parse(text);if(obj.dataset_id&&obj.dataset_id!==data.dataset_id)throw Error('Different benchmark dataset');rows=Array.isArray(obj)?obj:obj.reviews;}if(!Array.isArray(rows)||!rows.every(basicReview)||new Set(rows.map(r=>r.id)).size!==rows.length)throw Error('Invalid, duplicate or unknown review');for(const r of rows)if(!validReview(r)){const row=data.images.find(x=>x.id===r.id);throw Error(`${row.original}: ${r.result} is unavailable. Choose an available output, Equivalent, All unacceptable, or Needs review.`);}for(const r of rows)reviews[r.id]={result:r.result,notes:r.notes||''};persist();render();}catch(e){$('status').textContent='Import failed: '+e.message;}};
render();
</script></html>'''


def write_html(path: Path, payload: dict, output: Path, background: Path | None = None) -> None:
    embedded = json.loads(json.dumps(payload))
    embedded["review_eligible_statuses"] = REVIEW_ELIGIBLE_STATUSES
    embedded["kometa_background_asset_id"] = None
    prefix, remaining = REPORT_TEMPLATE.split("__ASSETS__", 1)
    between, suffix = remaining.split("__DATA__", 1)
    encoder = json.JSONEncoder(ensure_ascii=True, allow_nan=False)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as handle:
        tmp = Path(handle.name)
        try:
            def write_json(value):
                for chunk in encoder.iterencode(value):
                    handle.write(chunk.replace("<", "\\u003c"))
            handle.write(prefix)
            asset_count = 0
            def embed_image(image_path):
                nonlocal asset_count
                uri = data_uri(image_path)
                identity = f"asset-{asset_count}"
                asset_count += 1
                handle.write(f'<template id="{identity}"><img src="')
                handle.write(uri)
                handle.write('" alt=""></template>\n')
                return identity
            # Individual inert templates avoid V8's single-string limit and eager decode.
            for row in embedded["images"]:
                for record in [row["original_asset"], *row["outputs"].values()]:
                    record.pop("asset", None)
                    image_path = record.get("path")
                    if image_path:
                        try:
                            record["asset_id"] = embed_image(safe_relative(output, image_path))
                        except (OSError, ValueError) as exc:
                            record.setdefault("errors", []).append(f"Report image unavailable: {exc}")
            if background:
                embedded["kometa_background_asset_id"] = embed_image(background)
            handle.write(between)
            write_json(embedded)
            handle.write(suffix)
        except BaseException:
            handle.close()
            tmp.unlink(missing_ok=True)
            raise
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def print_summary(payload: dict) -> None:
    print("Source confidence | Selected | Reviewed | Engine | Wins | Failures % | Mean / median s | Peak RSS MiB")
    def number(value):
        return f"{value:.2f}" if isinstance(value, (int, float)) and math.isfinite(value) else "n/a"
    for confidence, group in payload["aggregates"].items():
        if not group["images"]:
            print(f"{confidence} | 0 | 0")
            continue
        for model in payload["models"]:
            stats = group["engines"][model]
            peak = payload["model_runs"].get(model, {}).get("peak_rss_bytes")
            peak_mib = peak / 1048576 if peak is not None else None
            print(f"{confidence} | {group['images']} | {group['actually_reviewed']} | {model} | {stats['wins']} | "
                  f"{number(stats['failure_percentage'])} | {number(stats['average_runtime'])} / "
                  f"{number(stats['median_runtime'])} | {number(peak_mib)}")


def write_csv(path: Path, rows: list[dict]) -> None:
    columns = ["id", "original", "adobe", "source_confidence", "categories", "engine", "status", "valid",
               "dimensions", "duration", "metrics", "warnings", "errors"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            for model, record in row["outputs"].items():
                values = {k: row.get(k) for k in columns[:5]}
                values.update({k: record.get(k) for k in columns[6:]})
                values["engine"] = model
                for key in ("categories", "dimensions", "metrics", "warnings", "errors"):
                    values[key] = json.dumps(values[key], ensure_ascii=True)
                writer.writerow(values)


@dataclass
class BenchmarkOptions:
    originals: Path
    adobe: Path
    output: Path = SCRIPT_DIR / "config" / "benchmarks" / "background-removal"
    staging: Path | None = None
    provenance: Path | None = None
    categories: Path | None = None
    sample_manifest: Path | None = None
    reviews: Path | None = None
    kometa_background: Path | None = None
    home: Path = SCRIPT_DIR / "config" / "models" / "rembg"
    models: tuple[str, ...] = MODELS
    limit: int = 100
    seed: int = 42
    all_images: bool = False
    prepare_only: bool = False
    report_only: bool = False
    validate_only: bool = False
    face_checks: bool = False
    overwrite: bool = False
    device: str = "cpu"
    decontaminate: bool = True
    alpha_matting: bool = False


def run_benchmark(options: BenchmarkOptions, remover_factory=None, settings_factory=None) -> dict:
    """Return report payload; write only to options.output and the model cache."""
    originals, adobe, output = options.originals.resolve(), options.adobe.resolve(), options.output.resolve()
    staging = options.staging.resolve() if options.staging else None
    validate_roots(originals, adobe, output, staging, options.home)
    if not options.models or any(m not in MODELS for m in options.models) or len(set(options.models)) != len(options.models):
        raise ValueError(f"Models must be distinct members of {MODELS}")
    found = match_images(originals, adobe)
    LOG.info("Inventory originals=%d adobe=%d matched=%d issues=%d", found["original_count"],
             found["adobe_count"], len(found["matches"]), len(found["issues"]))
    provenance = record_index(read_records(options.provenance, "records"))
    evidence_root = options.provenance.resolve().parent if options.provenance else originals
    staging_index = defaultdict(list)
    if staging:
        for path in inventory(staging):
            staging_index[path_key(path.relative_to(staging).as_posix())].append(path)
    candidates = [source_details(row, originals, adobe, staging, provenance, evidence_root, staging_index)
                  for row in found["matches"]]
    if options.sample_manifest:
        replay = read_records(options.sample_manifest, "images")
        replay_index = record_index(replay)
        available = {normalized(row["original"]): row for row in candidates}
        if set(replay_index) - set(available):
            raise ValueError("Sample manifest contains missing/ambiguous originals")
        candidates = [available[normalized(row["original"])] for row in replay]
        categories = [{"original": r["original"], "categories": r.get("categories", []),
                       "priority": r.get("priority", False)} for r in replay]
        if options.categories:
            merged = record_index(categories)
            supplied = record_index(read_records(options.categories, "images"))
            for key, record in supplied.items():
                merged[key] = {**merged.get(key, {}), **record}
            categories = list(merged.values())
    else:
        replay_index = {}
        categories = read_records(options.categories, "images")
    selected = select_sample(candidates, options.limit, options.seed, options.all_images, categories)
    LOG.info("Selected %d images with seed=%d (full library=%s)", len(selected), options.seed, options.all_images)
    if not selected:
        LOG.warning("No unambiguous matched images; inventory report will contain no samples")
    # Resolve/hash all selected inputs before creating any outputs.
    for row in selected:
        row["source_sha256"] = sha256(Path(row["source"]))
        row["adobe_sha256"] = sha256(safe_relative(adobe, row["adobe"]))
        prior = replay_index.get(normalized(row["original"]))
        if prior and (prior.get("source_sha256") != row["source_sha256"] or prior.get("adobe_sha256") != row["adobe_sha256"]):
            raise ValueError(f"Sample manifest hash mismatch: {row['original']}")
        row["id"] = hashlib.sha256((normalized(row["original"]) + ":" + row["source_sha256"] + ":" + row["adobe_sha256"]).encode()).hexdigest()[:24]
    reports = output / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    configuration = {"models": list(options.models), "device": options.device, "decontaminate": options.decontaminate,
                     "alpha_matting": options.alpha_matting}
    previous = {}
    if options.report_only:
        try:
            prior = json.loads((reports / "benchmark.json").read_text(encoding="utf-8"))
            compatible_configuration = (prior.get("configuration") == configuration or
                                        ("configuration" not in prior and prior.get("models") == ["adobe", *options.models]))
            if (compatible_configuration
                    and {r["id"] for r in prior.get("images", [])} == {r["id"] for r in selected}):
                previous = prior
            else:
                LOG.warning("Prior model timing/memory discarded: configuration or selected source IDs differ")
        except (OSError, ValueError, KeyError) as exc:
            LOG.info("No reusable prior report: %s", exc)
    images = []
    for index, row in enumerate(selected, 1):
        source = Path(row["source"])
        original_copy = output / "originals" / (row["id"] + source.suffix.lower())
        adobe_copy = output / "adobe" / (row["id"] + ".png")
        checked_copy(source, original_copy, row["source_sha256"])
        checked_copy(safe_relative(adobe, row["adobe"]), adobe_copy, row["adobe_sha256"])
        original_asset = {"path": original_copy.relative_to(output).as_posix(), "status": "source", "errors": []}
        try:
            with Image.open(original_copy) as image:
                image.load()
                size = image.size
            original_asset["dimensions"] = list(size)
        except (OSError, ValueError) as exc:
            size = None
            original_asset["errors"].append(f"Invalid source image: {exc}")
            row["warnings"].append(f"Source decoding failed: {exc}")
        adobe_metrics = image_metrics(adobe_copy, size, face_checks=options.face_checks)
        outputs = {"adobe": {**adobe_metrics, "status": "baseline", "duration": None,
                             "path": adobe_copy.relative_to(output).as_posix()}}
        for model in options.models:
            destination = output / model / (row["id"] + ".png")
            outputs[model] = {"status": "not-run", "valid": False, "metrics": {},
                              "warnings": [], "errors": [], "duration": None, "dimensions": None}
            if options.report_only and destination.is_file():
                outputs[model] = {**image_metrics(destination, size, adobe_copy, options.face_checks),
                                  "status": "unverified-existing", "duration": None,
                                  "path": destination.relative_to(output).as_posix()}
                sidecar = destination.with_suffix(destination.suffix + ".bg.json")
                try:
                    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
                    if (metadata["source_sha256"] != row["source_sha256"] or metadata["output_sha256"] != sha256(destination)
                            or metadata["settings"]["model"] != model
                            or any(metadata["settings"].get(k) != configuration[k]
                                   for k in ("device", "decontaminate", "alpha_matting"))):
                        raise ValueError("Model/source/output provenance differs")
                    outputs[model]["status"] = "existing"
                    outputs[model]["model_identifier"] = metadata.get("model_identifier")
                    historical = metadata.get("duration")
                    if isinstance(historical, (int, float)) and math.isfinite(historical) and historical >= 0:
                        outputs[model]["historical_duration"] = historical
                except (OSError, ValueError, KeyError) as exc:
                    outputs[model]["valid"] = False
                    outputs[model]["errors"].append(f"Existing model output provenance unavailable: {exc}")
        images.append({**row, "original_asset": original_asset, "outputs": outputs})
        if index % 20 == 0 or index == len(selected):
            LOG.info("Prepared %d/%d images", index, len(selected))
    intentional_categories = any(record.get("categories") or record.get("priority") for record in categories)
    manifest = {"seed": options.seed, "requested_limit": options.limit, "all_images": options.all_images,
                "categories_supplied": intentional_categories, "images": [
                    {k: row[k] for k in ("id", "original", "adobe", "source", "source_sha256", "adobe_sha256",
                                         "source_confidence", "path_confidence", "categories", "priority", "provenance")} for row in images]}
    atomic_json(reports / "sample-manifest.json", manifest)
    atomic_json(reports / "inventory.json", found)
    model_runs = {}
    for model, run in previous.get("model_runs", {}).items():
        records = [row["outputs"].get(model, {}) for row in images]
        if records and all(record.get("status") == "existing"
                           and record.get("model_identifier") == run.get("model_identifier") for record in records):
            model_runs[model] = run
        else:
            LOG.warning("Discarding prior %s memory/timing metadata: current output provenance differs", model)
    inference = not (options.prepare_only or options.report_only or options.validate_only)
    if inference and images:
        if remover_factory is None or settings_factory is None:
            api = helper_module("remove_bg_birefnet")
            remover_factory = remover_factory or api.LocalRemover
            settings_factory = settings_factory or api.Settings
            if any(model not in api.MODEL_NAMES for model in options.models):
                raise ValueError("Selected models are unsupported by LocalRemover")
        for model in options.models:
            remover = None
            initialization = time.perf_counter()
            run = {"initialization_seconds": None, "peak_rss_bytes": None, "errors": [],
                   "environment": environment_details()}
            LOG.info("Initializing %s for %d samples", model, len(images))
            with PeakRSS() as memory:
                try:
                    settings = settings_factory(model=model, device=options.device, decontaminate=options.decontaminate,
                                                alpha_matting=options.alpha_matting, overwrite=options.overwrite, home=options.home)
                    remover = remover_factory(settings)
                    run["initialization_seconds"] = time.perf_counter() - initialization
                    run["model_identifier"] = getattr(remover, "model_identifier", model)
                    run["rembg_version"] = getattr(remover, "rembg_version", None)
                    for index, row in enumerate(images, 1):
                        destination = output / model / (row["id"] + ".png")
                        source = safe_relative(output, row["original_asset"]["path"])
                        baseline = safe_relative(output, row["outputs"]["adobe"]["path"])
                        started = time.perf_counter()
                        try:
                            if row["original_asset"]["errors"]:
                                raise ValueError("Invalid selected source image")
                            processed = remover.process(source, destination)
                            if processed.get("status") not in {"processed", "skipped"}:
                                raise ValueError(f"Unexpected remover status: {processed.get('status')}")
                            validation = image_metrics(destination, tuple(row["original_asset"]["dimensions"]), baseline, options.face_checks)
                            duration = processed.get("duration", time.perf_counter() - started)
                            if not isinstance(duration, (float, int)) or not math.isfinite(duration) or duration < 0:
                                raise ValueError("Remover returned an invalid duration")
                            row["outputs"][model] = {**validation, "status": processed["status"], "duration": duration,
                                                     "path": destination.relative_to(output).as_posix(),
                                                     "model_identifier": processed.get("model_identifier", run["model_identifier"])}
                            row["outputs"][model]["warnings"].extend(processed.get("warnings", []))
                        except Exception as exc:
                            row["outputs"][model] = {"status": "failed", "valid": False, "metrics": {},
                                                     "warnings": [], "errors": [str(exc)], "duration": time.perf_counter() - started}
                        LOG.info("%s %d/%d %s: %s", model, index, len(images), row["original"], row["outputs"][model]["status"])
                except Exception as exc:
                    run["errors"].append(str(exc))
                    for row in images:
                        if row["outputs"][model]["status"] == "not-run":
                            row["outputs"][model].update(status="initialization-failed", errors=[str(exc)])
                finally:
                    if remover:
                        try:
                            remover.close()
                        except Exception as exc:
                            run["errors"].append(f"Model cleanup failed: {exc}")
                    remover = None
                    gc.collect()
            run["peak_rss_bytes"] = memory.peak
            run["memory_note"] = memory.error or "Sampled total process RSS at 50ms; includes initialization, not isolated model allocation"
            model_runs[model] = run
            atomic_json(reports / f"{model}-results.json", {"run": run, "images": images})
    reviews = load_reviews(options.reviews) if options.reviews else previous.get("reviews", {})
    validate_reviews(images, reviews)
    dataset_id = hashlib.sha256(json.dumps([sorted(row["id"] for row in images), configuration], sort_keys=True).encode()).hexdigest()
    limitations = ["Adobe is a production baseline, not segmentation ground truth; IoU is not a quality score.",
                   "Source-unverified images cannot prove a model is better than Adobe.",
                   "Provenance verifies hashes and a supplied submission attestation, not historical authenticity.",
                   "Halo and edge-contact flags are heuristics; light/dark hair and intentionally cropped shoulders can trigger them.",
                   "RSS is sampled total process memory and can miss short peaks; unavailable measurements are null.",
                   "Skipped outputs are excluded from inference runtime statistics; verified existing outputs use historical timings; Adobe runtime is unknown.",
                   "Review win percentages use decisive human reviews only; Needs review is counted as reviewed but excluded from wins."]
    if not intentional_categories:
        limitations.append("No intentional category manifest supplied; deterministic sampling does not establish hair/skin/difficulty coverage.")
    if len(images) < 100:
        limitations.append(f"Only {len(images)} images selected; the 100-portrait acceptance benchmark is incomplete.")
    limitations.append(f"Selected {sum(row['source_confidence'] == 'verified-source' for row in images)} verified-source images; acceptance requires human review of representative verified sources.")
    payload = {"schema_version": 1, "dataset_id": dataset_id, "configuration": configuration,
               "report_environment": environment_details(), "models": ["adobe", *options.models],
               "review_choices": REVIEW_CHOICES, "review_eligible_statuses": REVIEW_ELIGIBLE_STATUSES,
               "winners": WINNERS, "reviews": reviews,
               "images": images, "manifest": manifest, "model_runs": model_runs, "limitations": limitations,
               "inventory_summary": {k: v for k, v in found.items() if k != "matches"},
               "aggregates": aggregate_results(images, reviews)}
    failures = sum(not record.get("valid", False) for row in images for record in row["outputs"].values()
                   if record.get("status") != "not-run")
    payload["failures"] = failures + sum(bool(run["errors"]) for run in model_runs.values())
    atomic_json(reports / "benchmark.json", payload)
    write_csv(reports / "benchmark.csv", images)
    write_html(reports / "comparison.html", payload, output, options.kometa_background)
    LOG.info("Report: %s; selected=%d; source verified=%d; failures=%d", reports / "comparison.html",
             len(images), sum(row["source_confidence"] == "verified-source" for row in images), payload["failures"])
    return payload


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--originals", "--original-repo", required=True, type=Path)
    ap.add_argument("--adobe", "--adobe-repo", required=True, type=Path)
    ap.add_argument("--output", type=Path, default=BenchmarkOptions.__dataclass_fields__["output"].default)
    ap.add_argument("--staging", type=Path)
    ap.add_argument("--provenance", type=Path)
    ap.add_argument("--categories", type=Path)
    ap.add_argument("--sample-manifest", type=Path)
    ap.add_argument("--reviews", type=Path)
    ap.add_argument("--kometa-background", type=Path)
    ap.add_argument("--home", type=Path, default=Path(os.getenv("REMBG_HOME") or SCRIPT_DIR / "config" / "models" / "rembg"))
    ap.add_argument("--models", nargs="+", choices=MODELS, default=list(MODELS))
    ap.add_argument("--limit", "--sample-size", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--all", dest="all_images", action="store_true")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--prepare-only", action="store_true", help="Inventory, sample, snapshot and report; no inference")
    mode.add_argument("--report-only", action="store_true", help="Inspect existing benchmark outputs; no inference")
    mode.add_argument("--validate-only", action="store_true", help="Read-only reference validation and report; no inference")
    ap.add_argument("--face-checks", action="store_true", help="Use existing face helper only with cached detector weights")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--device", choices=("cpu", "cuda", "rocm", "coreml"), default="cpu")
    ap.add_argument("--no-decontaminate", dest="decontaminate", action="store_false")
    ap.add_argument("--alpha-matting", action="store_true")
    ap.add_argument("--clone", action="store_true", help="Explicitly clone missing reference repositories to supplied paths")
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if args.clone:
            validate_roots(args.originals, args.adobe, args.output, args.staging, args.home)
            for path, repository in ((args.originals, "People-Images"), (args.adobe, "People-Images-transparent")):
                if not path.exists():
                    subprocess.run(["git", "clone", "--", f"https://github.com/Kometa-Team/{repository}.git", str(path.resolve())], check=True)
        values = vars(args)
        values.pop("clone")
        values["models"] = tuple(values["models"])
        payload = run_benchmark(BenchmarkOptions(**values))
        print_summary(payload)
        return 1 if payload["failures"] else 0
    except (OSError, ValueError, KeyError, ImportError, subprocess.CalledProcessError) as exc:
        LOG.error("Benchmark failed: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
