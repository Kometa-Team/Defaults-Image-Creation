"""Versioned overlay inventory and bounded Pillow transforms in the shared pool."""

from io import BytesIO
import json
import math
from pathlib import Path
import time

from PIL import Image, ImageChops, ImageCms

from .common import BulkError, atomic_bytes, canonical, confined, fingerprint, path_key, sha256
from .config import Config
from .planner import renderer_identity, validate_manifest
from .state import Store


CATALOG = Path(__file__).parent / "catalog/overlays-v1.json"
TRANSFORM = {"version": "overlay-pillow-d1", "filter": "Pillow-LANCZOS", "resize": "fit-including-upscale-round-half-up",
             "trim": "top-left-RGBA-background-exact", "colorspace": "sRGB", "format": "PNG", "compress_level": 9}


def identity():
    value = renderer_identity()
    value["sources"]["bulk/overlays.py"] = fingerprint(Path(__file__).read_text(encoding="utf-8").replace("\r\n", "\n"))
    value["encoding"] = {"format": "PNG", "compress_level": 9}
    value["canvas"] = [440, 100]
    return value


def export_legacy_catalog():
    """Development-only migration; production reads only the checked-in catalog."""
    audit = json.loads((Path(__file__).parents[1] / "phase2/evidence/current-source-audit.json").read_text(encoding="utf-8"))
    groups = {}
    for operation in audit["overlays"]:
        group = operation["destination"].split("/overlays/")[0]
        size = operation["destination"].split("/")[-1]
        record = groups.setdefault(group, {"id": group, "trim": operation["trim"], "inputs": operation["inputs"], "sizes": {}})
        if record["inputs"] != operation["inputs"] or record["trim"] != operation["trim"] or size in record["sizes"]:
            raise BulkError("overlay_reconciliation", "Legacy operation groups conflict")
        record["sizes"][size] = {"box": [int(v) for v in operation["resize_box"].split("x")], "destination": operation["destination"], "source_line": operation["source_line"]}
    result = {"schema_version": 1, "transform": TRANSFORM, "legacy_audit_sha256": fingerprint(audit["overlays"]), "groups": list(groups.values())}
    result["counts"] = {"operations": sum(len(g["sizes"]) for g in groups.values()), "groups": len(groups),
                        "unique_inputs": len({p for g in groups.values() for p in g["inputs"]}),
                        "transforms": sum(len(g["inputs"]) * len(g["sizes"]) for g in groups.values())}
    result["sha256"] = fingerprint(result)
    atomic_bytes(CATALOG, canonical(result) + b"\n")
    return result["counts"]


def render(parameters, source, target):
    """One image at a time; no process launch or network in rendering workers."""
    with Image.open(source) as image:
        if image.format != "PNG" or image.width * image.height > 24_000_000 or getattr(image, "n_frames", 1) != 1:
            raise BulkError("invalid_overlay", "Overlay source must be bounded single-frame PNG")
        profile = image.info.get("icc_profile")
        image.load()
        if profile:
            try:
                image = ImageCms.profileToProfile(image, ImageCms.ImageCmsProfile(BytesIO(profile)), ImageCms.createProfile("sRGB"), outputMode="RGBA")
            except (ImageCms.PyCMSError, OSError, ValueError) as error:
                raise BulkError("invalid_colorspace", "Overlay ICC conversion failed") from error
        else:
            image = image.convert("RGBA")
        if parameters["trim"]:
            background = Image.new("RGBA", image.size, image.getpixel((0, 0)))
            channels = ImageChops.difference(image, background).split()
            mask = channels[0]
            for channel in channels[1:]:
                mask = ImageChops.lighter(mask, channel)
            bounds = mask.getbbox()
            image = image.crop(bounds) if bounds else Image.new("RGBA", (1, 1))
        box = parameters["box"]
        scale = min(box[0] / image.width, box[1] / image.height)
        size = (max(1, math.floor(image.width * scale + .5)), max(1, math.floor(image.height * scale + .5)))
        image = image.resize(size, Image.Resampling.LANCZOS, reducing_gap=None)
        # Fresh image strips inherited text, EXIF, density and color-profile metadata.
        clean = Image.new("RGBA", image.size)
        clean.paste(image)
        clean.save(target, format="PNG", compress_level=9)


def plan(config=None, *, groups=(), sizes=("standard", "bigger"), sources=()):
    config = config or Config()
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    if catalog["sha256"] != fingerprint({k: v for k, v in catalog.items() if k != "sha256"}) or catalog["transform"] != TRANSFORM:
        raise BulkError("corrupt_catalog", "Overlay catalog identity or transform policy mismatch")
    known = {g["id"] for g in catalog["groups"]}
    if set(groups) - known or set(sizes) - {"standard", "bigger"} or not sizes:
        raise BulkError("invalid_selection", "Unknown overlay groups or sizes")
    renderer, jobs, hashes, found = identity(), [], {}, set()
    for group in catalog["groups"]:
        if groups and group["id"] not in groups:
            continue
        for source in group["inputs"]:
            if sources and source not in sources:
                continue
            found.add(source)
            path = confined(config.asset_dir, source, must_exist=True)
            hashes.setdefault(source, sha256(path))
            with Image.open(path) as image:
                if image.format != "PNG" or image.width * image.height > 24_000_000:
                    raise BulkError("invalid_overlay", "Invalid overlay source")
                image.verify()
            for size in sizes:
                operation = group["sizes"][size]
                parameters = {"input": source, "box": operation["box"], "trim": group["trim"], "colorspace": "sRGB",
                              "strip_metadata": True, "format": "PNG", "resampling": "Pillow-LANCZOS"}
                relative = operation["destination"] + "/" + Path(source).name
                job = {"id": "overlay." + fingerprint(relative)[:24], "kind": "overlay", "poster_id": "overlay." + group["id"].replace("/", ".") + "." + fingerprint(source)[:12],
                       "language": "en", "variant": size, "definition_fingerprint": fingerprint({"group": group["id"], "parameters": parameters, "transform": TRANSFORM}),
                       "generator_origin": None, "source": {"path": "create_default_posters.ps1", "line": operation["source_line"], "row_sha256": catalog["legacy_audit_sha256"]},
                       "raw_parameters": parameters, "parameters": parameters, "inputs": [{"role": "overlay_source", "path": source, "sha256": hashes[source]}], "dependencies": [],
                       "translation": {"mode": "none", "trace": [], "fingerprint": fingerprint({"mode": "none"})},
                       "language_behavior": {"language": "shared", "direction": "auto"}, "local_relative": relative, "remote_relative": relative,
                       "layout_evidence": {"transform": TRANSFORM}, "color_assignment": {"id": "overlay.none", "origin": "template", "parent": None, "relationship": None, "exception": None},
                       "status": "planned", "render_ready": True}
                job["render_fingerprint"] = fingerprint({key: job[key] for key in ("kind", "parameters", "inputs", "dependencies", "language_behavior")} | {"renderer": renderer})
                jobs.append(job)
    if set(sources) - found or not jobs:
        raise BulkError("invalid_selection", "No matching overlays or unknown selected sources")
    result = {"schema_version": 1, "kind": "bulk-plan", "renderer": renderer, "jobs": jobs, "not_applicable": [],
              "selection": {"categories": ["Overlays"], "posters": list(groups), "languages": ["en"]}, "scope": "Package D local overlay review; not published"}
    result["sha256"] = fingerprint(result)
    return validate_manifest(result)


def generate(config=None, *, groups=(), sizes=("standard", "bigger"), sources=(), limits=None, audit=False):
    from .workers import PersistentWorkers, WorkerLimits, tasks_from_manifest
    config = config or Config()
    started = time.perf_counter()
    manifest = plan(config, groups=groups, sizes=sizes, sources=sources)
    from .preflight import POLICY, export_report
    report = {"schema_version": 1, "kind": "overlay-preflight", "policy": POLICY, "execution_policy": "audit" if audit else "review",
              "registry_sha256": fingerprint({"kind": "shared-overlay-catalog", "catalog": json.loads(CATALOG.read_text())["sha256"]}),
              "translation_hashes": {}, "renderer": manifest["renderer"], "languages": [], "selection": manifest["selection"],
              "variants": [], "coverage": {"ready_with_warning": len(manifest["jobs"])}, "missing_translations": [], "status": "complete"}
    for job in manifest["jobs"]:
        report["variants"].append({"id": job["id"], "poster_id": job["poster_id"], "kind": "overlay", "language": "en", "category": "Overlays",
            "selected": True, "private": False, "status": "ready_with_warning", "caption": None,
            "definition_fingerprint": job["definition_fingerprint"], "dependencies": [], "translation_dependencies": [],
            "inputs": {i["role"]: {"path": i["path"], "sha256": i["sha256"]} for i in job["inputs"]},
            "validation_fingerprint": fingerprint({"job": job, "renderer": manifest["renderer"], "policy": POLICY}),
            "local_relative": job["local_relative"], "remote_relative": job["remote_relative"],
            "diagnostics": [{"code": "overlay_transform_review", "severity": "warning", "message": "Pillow filter/alpha differences require explicit overlay review", "details": {"transform": TRANSFORM}}],
            "risk": {"version": POLICY["risk"], "level": "high", "reasons": ["overlay_transform_review"], "requires_individual": True}})
    report["sha256"] = fingerprint(report)
    export_report(report, config.cache_dir / "preflight" / report["sha256"])
    # Persist full validation before entering the worker pool, even for audit-only runs.
    path = config.cache_dir / "overlay-preflight" / (manifest["sha256"] + ".json")
    if not path.exists():
        atomic_bytes(path, canonical(manifest) + b"\n")
    if audit:
        return {"status": "audited", "manifest": manifest, "preflight": report, "stages": [], "preflight_file": str(path)}
    with PersistentWorkers(Store(config.cache_dir / "state.sqlite"), config, limits or WorkerLimits()) as pool:
        result = pool.run(tasks_from_manifest(manifest))
    success = all(v["status"] in {"rendered", "cache_reuse", "dedup_reuse"} for v in result["jobs"].values())
    if success:
        pool.workspaces.cleanup(**pool.workspace, retain_seconds=0)
    return {"status": "verified" if success else "incomplete", "manifest": manifest, "execution": result, "preflight": report,
            "stages": [{"depth": 0, "manifest": manifest, "execution": result}],
            "elapsed_seconds": time.perf_counter() - started, "preflight_file": str(path)}


if __name__ == "__main__":
    print(json.dumps(export_legacy_catalog(), sort_keys=True))
