"""Standalone planning using the existing renderer and a model-free source scanner."""
from __future__ import annotations
from collections import defaultdict
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import unicodedata
import contextlib
import sys

from bulk_regeneration_state import STYLES, canonical, reject_links

RESERVE = 2 * 1024**3
MAX_SOURCE_PIXELS = 40_000_000


def git_state(root):
    def call(*args):
        result = subprocess.run(["git", "--no-optional-locks", '-c', 'safe.directory='+str(Path(root).resolve()), "-C", str(root), *args], capture_output=True)
        if result.returncode:
            return None
        return result.stdout.decode("utf8", errors="replace").strip()
    head = call("rev-parse", "HEAD")
    return dict(head=head, status=call("status", "--porcelain=v1") if head else None,
                root=call("rev-parse", "--show-toplevel") if head else None)


def check_paths(source, output, new=False):
    source, output = Path(source).expanduser().absolute(), Path(output).expanduser().absolute()
    reject_links(source); reject_links(output)
    source, output = source.resolve(), output.resolve()
    if not source.is_dir():
        raise ValueError(f"Source directory does not exist: {source}")
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Staging must be disjoint from the transparent source")
    for parent in (output, *output.parents):
        if (parent/".git").exists():
            raise ValueError(f"Staging cannot be inside any Git repository: {parent}")
    if new and output.exists():
        for path in output.iterdir():
            if path.name!='.bulk' or not path.is_dir() or any(path.iterdir()):
                raise ValueError("New staging directory is not empty; choose another directory or use --resume")
    return source, output


def image_header(path, verify=True):
    from PIL import Image
    with Image.open(path) as image:
        if image.format != "PNG" or getattr(image, "n_frames", 1) != 1:
            raise ValueError("Expected a single-frame PNG")
        width, height = image.size
        if width*height > MAX_SOURCE_PIXELS or width > 20000 or height > 20000 or height/width > 6:
            raise ValueError("Image exceeds the bounded decoding/resizing budget")
        if image.mode not in {"RGBA", "LA", "P"} and "transparency" not in image.info:
            raise ValueError("PNG has no transparency channel")
        attributes = dict(dimensions=list(image.size), mode=image.mode)
        if verify:
            image.verify()
        return attributes


def existing_sizes(parent):
    """Stat local destination posters only. Never instantiate a GitHub client."""
    result = {}
    for style in STYLES:
        directory = Path(parent)/style
        sizes = []
        if directory.is_dir():
            reject_links(directory)
            for initial in directory.iterdir():
                images = initial/"Images"
                if images.is_dir():
                    reject_links(images)
                    for poster in images.iterdir():
                        if poster.suffix.lower() in {".jpg", ".jpeg"} and poster.is_file():
                            reject_links(poster)
                            sizes.append(poster.stat().st_size)
        sizes.sort()
        result[style] = dict(count=len(sizes), total_bytes=sum(sizes),
                             mean_bytes=sum(sizes)/len(sizes) if sizes else None,
                             p95_bytes=sizes[min(len(sizes)-1, int(len(sizes)*.95))] if sizes else None,
                             max_bytes=max(sizes) if sizes else None)
    return result


def estimate_storage(rows, styles, sizes, estimate_from=None):
    observed = {}
    if estimate_from:
        from bulk_regeneration_state import database
        db = database(Path(estimate_from), readonly=True)
        try:
            for style in STYLES:
                values = [r[0] for r in db.execute("SELECT bytes FROM outputs WHERE style=? AND status='completed'", (style,))]
                if values:
                    observed[style] = max(values)
        finally:
            db.close()
    per_style = {}
    selected = sum(bool(r["selected"]) for r in rows)
    for style in styles:
        sample = sizes.get(style, {})
        # New q100 outputs can be larger than historical JPEGs. Canary maxima
        # are preferred; absent a canary use at least 2MiB/output, never mean alone.
        per_output = max(observed.get(style, 0), sample.get("p95_bytes") or 0, 2*1024**2)
        per_style[style] = dict(estimated_bytes_per_output=math.ceil(per_output*1.25),
                               estimated_total_bytes=math.ceil(per_output*1.25)*selected,
                               canary_observed_max_bytes=observed.get(style))
    return dict(per_style=per_style, estimated_output_bytes=sum(r["estimated_total_bytes"] for r in per_style.values()),
                reserve_bytes=RESERVE, required_free_bytes=sum(r["estimated_total_bytes"] for r in per_style.values())+RESERVE,
                approximate=True, basis="max(canary maximum, existing p95, 2MiB) per style plus25%, plus2GiB reserve")


def require_space(output, needed):
    parent = Path(output)
    while not parent.exists():
        parent = parent.parent
    free = shutil.disk_usage(parent).free
    if free < needed:
        raise ValueError(f"Insufficient staging space: need approximately {needed/1024**3:.2f}GiB free; "
                         f"only {free/1024**3:.2f}GiB available. Use another volume or free space.")
    return free


def inventory(source, styles, canary=None, verify=True, progress=None, deep=True,canary_paths=None):
    from bulk_source import scan_sources, sample_numbers, path_key
    from create_people_poster import output_path
    with contextlib.redirect_stdout(sys.stderr):
        rows, ignored = scan_sources(Path(source), exclude_ambiguous=True, hash_sources=deep and canary is None,progress=progress)
    groups = defaultdict(list)
    for checked, row in enumerate(rows, 1):
        # Preserve exact filename spelling; unlike the historical publication
        # rollout, do not remove _ccexpress or normalize Unicode on disk.
        destination = output_path(Path("."), styles[0], row["name"]).relative_to(styles[0]).as_posix()
        row.update(destination=destination, issue="", issue_kind="", attributes={})
        try:
            path_key(destination)
            row["attributes"] = image_header(Path(source)/row["relative"], verify=verify and deep and canary is None)
        except (OSError, ValueError, SyntaxError) as error:
            row.update(issue=str(error), issue_kind="invalid_input")
        groups[path_key(destination)].append(row)
        if checked % 100 == 0 or checked == len(rows):
            if progress:
                progress(checked, len(rows), row["relative"])
            elif checked % 500 == 0 or checked == len(rows):
                print(f"[CHECK] {checked}/{len(rows)} PNG containers; current={row['relative']}", file=sys.stderr, flush=True)
    collisions = []
    for group in groups.values():
        if len(group) > 1:
            names = [r["relative"] for r in group]
            collisions.append(names)
            for row in group:
                row.update(issue="Unicode/case-insensitive destination collision: "+repr(names), issue_kind="collision")
    for row in rows:
        row["eligible"] = not bool(row["issue"])
        row["selected"] = canary is None
    eligible = [row for row in rows if row["eligible"]]
    categories = {}
    if canary is not None:
        if not 1 <= canary <= 100:
            raise ValueError("--canary must be between1 and100")
        selected = []
        def add(row, reason):
            if row["number"] not in selected and len(selected) < canary:
                selected.append(row["number"])
                categories[str(row["number"])] = reason
        for row in sorted(eligible, key=lambda r: -len(r["name"]))[:2]:
            add(row, "long_name")
        for row in [r for r in eligible if not r["name"].isascii()][:2]:
            add(row, "accented_or_non_ascii")
        for row in [r for r in eligible if "'" in r["name"] or "\u2019" in r["name"]][:2]:
            add(row, "apostrophe")
        for row in [r for r in eligible if r["attributes"]["dimensions"] != [2000, 3000]][:3]:
            add(row, "unusual_dimensions")
        from PIL import Image
        for row in ([] if canary_paths is not None else eligible[:80]):
            if len(selected) >= max(1, canary-4):
                break
            try:
                with Image.open(Path(source)/row["relative"]) as image:
                    box = image.convert("RGBA").getchannel("A").getbbox()
                    if box and (box[1] > image.height*.17 or box[0] > image.width*.25 or box[1] == 0):
                        row["attributes"]["sample_alpha_bbox"] = box
                        add(row, "difficult_placement")
            except (OSError, ValueError, SyntaxError):
                continue
        if eligible:
            legacy = sample_numbers(eligible, min(canary, len(eligible)))
            for row in eligible:
                if row["number"] in legacy:
                    add(row, "legacy_representative_sample")
        for row in eligible:
            add(row, "additional_sample")
        if canary_paths is not None:
            requested={path_key(p) for p in canary_paths}
            if len(canary_paths)!=canary or len(requested)!=canary:
                raise ValueError('Explicit selection must match the bounded canary size without duplicates')
            chosen=[row for row in eligible if row['relative'] in canary_paths]
            if len(chosen)!=canary:
                raise ValueError('Explicit canary contains missing, differently cased or ineligible PNG paths')
            selected=[row['number'] for row in chosen]
            categories={str(row['number']):'explicit_qualification_sample' for row in chosen}
        for row in rows:
            row["selected"] = row["number"] in selected
            if row["selected"]:
                from bulk_source import content_hashes
                row["source_hash"],blob = content_hashes(Path(source)/row["relative"])
                if row.get('git_blob') and blob!=row['git_blob']:
                    raise ValueError('Canary source differs from pinned Git blob: '+row['relative'])
                try:
                    row["attributes"].update(image_header(Path(source)/row["relative"],verify=True))
                except (OSError,ValueError,SyntaxError) as error:
                    row.update(eligible=False,issue=str(error),issue_kind="invalid_input")
    return rows, dict(ignored=ignored, collisions=collisions, canary_categories=categories,
                       png_validation=("All PNG headers; selected canary payload hashes/CRC" if canary else "All PNG headers/hashes/CRC" if deep else "Headers only; full payload validation occurs during rendering or --deep-validate"),
                       input_total=len(rows), eligible_image_count=sum(r["eligible"] for r in rows),
                       selected_input_total=sum(r["selected"] for r in rows),
                       potential_five_style_outputs=len(rows)*len(STYLES),
                       planned_outputs=sum(r["selected"] for r in rows)*len(styles),
                       source_bytes=sum(r["size"] for r in rows),
                       normalization_differences=[r["relative"] for r in rows if unicodedata.normalize("NFC", r["relative"]) != r["relative"]],
                       )


def renderer_version():
    from create_people_poster import SCRIPT_DIR, renderer_fingerprint, resource_dirs
    assets, fonts = resource_dirs()
    if assets.resolve() != (SCRIPT_DIR/'assets/people').resolve() or fonts.resolve() != (SCRIPT_DIR/'fonts').resolve():
        raise ValueError('Bulk rendering requires bundled resources; override directories are not accepted')
    fingerprint = renderer_fingerprint()
    if "missing" in fingerprint["files"].values():
        raise ValueError("Required renderer resource missing")
    repo = SCRIPT_DIR.parent
    release = SCRIPT_DIR/'.bulk-runtime.json'
    if not release.is_file() and (SCRIPT_DIR/'unicode/runtime-release-v3.json').is_file():
        release = SCRIPT_DIR/'unicode/runtime-release-v3.json'
    if release.is_file():
        from bulk_runtime import verify_release
        value=verify_release(SCRIPT_DIR,release)
        if value['version']==3:
            fingerprint['verified_renderer_parent']=value['parent_commit']
            fingerprint['verified_renderer_profile']=value['profile']
        else:
            fingerprint['verified_renderer_commit']=value['renderer_commit']
        fingerprint['release_sha256']=canonical(value)
        fingerprint['python']=sys.version.split()[0]
        return fingerprint
    candidates = []
    for ref in ("origin/main", "HEAD"):
        result = subprocess.run(["git", "-C", str(repo), "rev-parse", ref], capture_output=True, text=True)
        if result.returncode == 0:
            commit = result.stdout.strip()
            blob = subprocess.run(["git", "-C", str(repo), "show", commit+":create_people_posters/create_people_poster.py"], capture_output=True)
            current = (SCRIPT_DIR/"create_people_poster.py").read_bytes().replace(b"\r\n", b"\n")
            if blob.returncode == 0 and blob.stdout.replace(b"\r\n", b"\n") == current:
                candidates.append(commit)
    if not candidates:
        raise ValueError("Renderer bytes do not match HEAD or origin/main; reconcile the merged renderer before starting")
    fingerprint["verified_renderer_commit"] = candidates[0]
    fingerprint["standalone_files"] = {name: __import__("hashlib").sha256((SCRIPT_DIR/name).read_bytes()).hexdigest()
                                       for name in ("bulk_regenerate.py", "bulk_regeneration_plan.py", "bulk_regeneration_state.py", "bulk_regeneration_report.py", "bulk_source.py")}
    fingerprint['python'] = sys.version.split()[0]
    fingerprint['styles'] = list(STYLES)
    return fingerprint
