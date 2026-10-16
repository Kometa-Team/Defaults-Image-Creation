"""Read-only source discovery; candidates are never approved definitions."""

from collections import defaultdict
from pathlib import Path
import warnings

from PIL import Image

from .common import BulkError, Diagnostic, confined, path_key, reject_links, sha256


def historical_asset_usage(capture):
    result = defaultdict(set)
    for job in capture["jobs"]:
        for field in ("logo", "avg_color_image"):
            path = job["parameters"][field]
            active = field == "logo" or (job["parameters"]["avg_color"] and not job["parameters"]["base_color"])
            if path and active and field not in job["generated_inputs"]:
                result[path].add("legacy." + job["category"].lower() + "." + job["definition_id"])
    return result


def discover_assets(root, directories, definitions=(), *, overlay_inputs=(), historical_assignments=None):
    root = reject_links(root).resolve()
    assigned, outputs = defaultdict(set), defaultdict(set)
    for path, owners in (historical_assignments or {}).items():
        path_key(path)
        assigned[path].update(owners)
    diagnostics = []
    for definition in definitions:
        item = definition.data
        for language in item["languages"]:
            expanded = definition.for_language(language).data
            generated = {dependency["input"] for dependency in expanded["dependencies"]}
            for field in ("logo", "avg_color_image"):
                source = expanded["composer"][field]
                active = field == "logo" or (expanded["composer"]["avg_color"] and not expanded["composer"]["base_color"])
                if source and active and field not in generated:
                    assigned[source].add(item["id"])
            output = f"defaults-{language}/{expanded['output']['directory']}/{expanded['output']['filename']}"
            outputs[path_key(output)].add(item["id"])
    for key, owners in sorted(outputs.items()):
        if len(owners) > 1:
            diagnostics.append(Diagnostic("output_collision", "error", "Potential active output collision", tuple(sorted(owners)), {"path": key}))
    files, keys, hashes = {}, defaultdict(list), defaultdict(list)
    for directory in sorted(set(directories)):
        folder = confined(root, directory)
        if not folder.is_dir():
            diagnostics.append(Diagnostic("missing_source_directory", "error", "Configured source directory is absent", details={"directory": directory}))
            continue
        # Never follow links during traversal, including nested junctions on Windows.
        pending = [folder]
        while pending:
            current = pending.pop()
            for path in sorted(current.iterdir()):
                relative = path.relative_to(root).as_posix()
                try:
                    reject_links(path)
                    confined(root, relative)
                except BulkError:
                    diagnostics.append(Diagnostic("unsafe_source_path", "error", "Source link or unsafe filename rejected", details={"path": relative}))
                    continue
                if path.is_dir():
                    pending.append(path)
                    continue
                if not path.is_file() or relative in files:
                    continue
                expected = path.suffix.lower() == ".png"
                info = {"path": relative, "sha256": sha256(path), "assigned": sorted(assigned.get(relative, ())),
                        "overlay_input": relative in overlay_inputs, "format": None, "size": None}
                try:
                    if path.stat().st_size > 30_000_000:
                        raise BulkError("invalid_image", "Image byte limit exceeded")
                    with warnings.catch_warnings():
                        warnings.simplefilter("error", Image.DecompressionBombWarning)
                        with Image.open(path) as image:
                            if image.width * image.height > 24_000_000 or getattr(image, "n_frames", 1) != 1:
                                raise BulkError("invalid_image", "Image pixel/frame limit exceeded")
                            info.update(format=image.format, size=[image.width, image.height])
                            image.verify()
                    if info["format"] != "PNG":
                        expected = False
                except (OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
                    diagnostics.append(Diagnostic("invalid_source_image", "error", "Cannot verify bounded static source image", details={"path": relative}))
                if not expected:
                    diagnostics.append(Diagnostic("unexpected_format", "warning", "Source is not an expected PNG logo", details={"path": relative}))
                files[relative] = info
                keys[path_key(relative)].append(relative)
                hashes[info["sha256"]].append(relative)
    for key, group in sorted(keys.items()):
        if len(group) > 1:
            diagnostics.append(Diagnostic("source_case_collision", "error", "Case/Unicode source filenames conflict", details={"paths": group}))
    for checksum, group in sorted(hashes.items()):
        if len(group) > 1:
            diagnostics.append(Diagnostic("duplicate_source_identity", "info", "Source files have identical bytes; association requires review", details={"sha256": checksum, "paths": group}))
    for path, owners in sorted(assigned.items()):
        try:
            confined(root, path, must_exist=True)
        except BulkError:
            diagnostics.append(Diagnostic("missing_active_logo", "error", "Definition references a missing/unsafe active source", tuple(sorted(owners)), {"path": path}))
        if len(owners) > 1:
            diagnostics.append(Diagnostic("ambiguous_association", "info", "Multiple logical posters use this source; do not infer a new identity", tuple(sorted(owners)), {"path": path}))
    return {"files": [files[key] for key in sorted(files)],
            "unassigned_candidates": sorted(path for path, item in files.items() if not item["assigned"] and not item["overlay_input"]),
            "diagnostics": [item.to_dict() for item in diagnostics], "approved_definitions_created": 0, "source_files_deleted": 0}
