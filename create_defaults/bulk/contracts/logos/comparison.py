"""Explainable bounded mask diagnostics; no unapproved automatic MATCH policy."""

from collections import deque
from pathlib import Path

from PIL import Image, __version__ as pillow_version

from ...common import BulkError, fingerprint
from .assets import Asset
from .wash import white_wash


def topology(mask, *, foreground=True, signatures=False):
    width, height = mask.size
    data = list(mask.tobytes())
    wanted = [bool(v) == foreground for v in data]
    seen, sizes, bounds, hashes = set(), [], [], []
    directions = [(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if (x or y) and (foreground or abs(x)+abs(y) == 1)]
    for start in range(len(wanted)):
        if not wanted[start] or start in seen:
            continue
        queue, count, edge, xs, ys = deque([start]), 0, False, [], []
        seen.add(start)
        while queue:
            point = queue.popleft()
            x, y = point % width, point // width
            count += 1
            xs.append(x); ys.append(y)
            edge |= x in (0, width-1) or y in (0, height-1)
            for dx, dy in directions:
                nx, ny = x+dx, y+dy
                other = ny*width+nx
                if 0 <= nx < width and 0 <= ny < height and wanted[other] and other not in seen:
                    seen.add(other); queue.append(other)
        if foreground or not edge:
            sizes.append(count)
            bounds.append([min(xs), min(ys), max(xs)+1, max(ys)+1])
            if signatures:hashes.append(fingerprint(sorted(zip(xs,ys))))
    result={"count": len(sizes), "areas": sorted(sizes), "bounds": sorted(bounds)}
    if signatures:result["exact_pixel_component_sha256"]=sorted(hashes)
    return result


def _aligned(image, grid):
    alpha = image.getchannel("A")
    alpha = alpha.crop(alpha.getbbox())
    scale = grid / max(alpha.size)
    size = (max(1, round(alpha.width*scale)), max(1, round(alpha.height*scale)))
    resized = alpha.resize(size, Image.Resampling.LANCZOS)
    result = Image.new("L", (grid, grid))
    result.paste(resized, ((grid-size[0])//2, (grid-size[1])//2))
    return result


def _boundary(mask):
    width, height = mask.size
    values = list(mask.tobytes())
    return {y*width+x for y in range(height) for x in range(width) if values[y*width+x]
            and any(not (0 <= x+dx < width and 0 <= y+dy < height) or not values[(y+dy)*width+x+dx]
                    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)))}


def _distances(origins, targets, size):
    width, height = size
    distance = [-1] * (width*height)
    queue = deque(targets)
    for point in targets: distance[point] = 0
    while queue:
        point = queue.popleft()
        x, y = point % width, point // width
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = x+dx, y+dy
            other = ny*width+nx
            if 0 <= nx < width and 0 <= ny < height and distance[other] == -1:
                distance[other] = distance[point]+1
                queue.append(other)
    values = [distance[p] for p in origins]
    return {"sum": sum(values), "count": len(values), "maximum": max(values, default=None),
            "metric": "four_neighbour_grid_distance", "normalizing_scale": max(size)}


def compare(master: Asset, separate_white: Asset, *, grid=128):
    if type(grid) is not int or not 16 <= grid <= 256:
        raise BulkError("logo_analysis_budget", "Analysis grid must fit the bounded 256-square diagnostic budget")
    washed, transform = white_wash(master.image())
    white = separate_white.image()
    left, right = _aligned(washed, grid), _aligned(white, grid)
    a, b = list(left.tobytes()), list(right.tobytes())
    levels = []
    for level in (1, 128, 255):  # measurement probes, NOT decision thresholds
        lm = left.point(lambda v: 255 if v >= level else 0)
        rm = right.point(lambda v: 255 if v >= level else 0)
        lv, rv = list(lm.tobytes()), list(rm.tobytes())
        lb, rb = _boundary(lm), _boundary(rm)
        levels.append({"level": level, "intersection": sum(bool(x) and bool(y) for x,y in zip(lv,rv)),
                       "union": sum(bool(x) or bool(y) for x,y in zip(lv,rv)),
                       "master_components": topology(lm), "white_components": topology(rm),
                       "master_holes": topology(lm, foreground=False), "white_holes": topology(rm, foreground=False),
                       "boundary_master_to_white": _distances(lb, rb, lm.size) if lb and rb else None,
                       "boundary_white_to_master": _distances(rb, lb, rm.size) if lb and rb else None})
    native = []
    for asset in (master, separate_white):
        image = asset.image()
        alpha = image.getchannel("A")
        hist = alpha.histogram()
        # Only native, binary, already bounded topology is conclusive here. No
        # resize/AA threshold or metric tolerance can silently become a verdict.
        binary = not sum(hist[1:255]) and max(image.size) <= 256
        native.append({"binary_bounded": binary,
                       "components": topology(alpha,signatures=True) if binary else None,
                       "holes": topology(alpha, foreground=False,signatures=True) if binary else None})
    structural=False
    # Hard flags require exact native component/cutout addition or deletion in
    # the SAME canvas. Different resolutions, resampling, padding or soft-alpha
    # topology can never become a mismatch merely from component counts.
    if master.report()["dimensions"]==separate_white.report()["dimensions"] and all(n["binary_bounded"] for n in native):
        for kind in ("components","holes"):
            first=set(native[0][kind]["exact_pixel_component_sha256"])
            second=set(native[1][kind]["exact_pixel_component_sha256"])
            structural |= first < second or second < first
    rgb_analysis=white.copy()
    rgb_analysis.thumbnail((256,256),Image.Resampling.LANCZOS)
    rgba=rgb_analysis.tobytes()
    visible=[rgba[i:i+3] for i in range(0,len(rgba),4) if rgba[i+3]]
    report = {"version": "pillow-logo-diagnostics-v1", "master_sha256": master.sha256,
        "white_sha256": separate_white.sha256, "transform": transform,
        "settings": {"grid": grid, "levels": [1,128,255], "alignment": "visible-bounds-translation-uniform-scale-only",
                     "resampling": "Pillow-LANCZOS", "Pillow": pillow_version},
        "soft_alpha_absolute_sum": sum(abs(x-y) for x,y in zip(a,b)), "sample_count": len(a),
        "soft_intersection_sum": sum(min(x,y) for x,y in zip(a,b)), "soft_union_sum": sum(max(x,y) for x,y in zip(a,b)),
        "master_canvas_and_bounds": {k: master.report()[k] for k in ("dimensions", "visible_bounds")},
        "white_canvas_and_bounds": {k: separate_white.report()[k] for k in ("dimensions", "visible_bounds")},
        "levels": levels, "native_topology": native,
        "visible_white_rgb_extrema": [[min(p[c] for p in visible),max(p[c] for p in visible)] for c in range(3)],
        "rgb_analysis_size":list(rgb_analysis.size),
        "analysis_visible_nonwhite_pixels":sum(p != b'\xff\xff\xff' for p in visible),
        "outcome": "MISMATCH" if structural else "REVIEW REQUIRED",
        "reason": "exact_native_binary_component_or_cutout_addition_or_deletion" if structural else "no_approved_calibrated_MATCH_policy",
        "automatic_match_enabled": False, "publication_authorized": False}
    report["policy_sha256"] = fingerprint({"version": report["version"], "settings": report["settings"],
                                           "transform":transform,"implementation_sha256":fingerprint(Path(__file__).read_text(encoding="utf-8").replace("\r\n", "\n")),
                                           "classification": "same-canvas-exact-native-topology-proof-otherwise-review-no-match"})
    return report
