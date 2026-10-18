"""Deterministic image measurements and proposal-only tolerance evaluation.

No metric grants approval. Original geometry is always compared without alignment.
RGB arithmetic uses bounded stripes; images are decoded one pair at a time.
"""
import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageStat

from .common import BulkError, fingerprint


PROPOSED_POLICY = {
    "schema_version": 1, "version": "english-library-tolerance-proposal-v1",
    "status": "proposed", "scope": "same-font, unchanged-layout posters only",
    "thresholds": {"rgb_mae": 1.5, "p99": 16, "changed_gt16": .025,
                   "minimum_global_ssim": .995, "region_mae": 2.0,
                   "edge_mae": 3.0, "alpha_mae": 0.0},
    "limitations": ["Requires maintainer approval and negative-control calibration",
                    "Font substitutions and layout changes require scoped review",
                    "Global SSIM is a screen, not windowed structural similarity",
                    "Region boxes are conservative diagnostics, not text recognition"],
}


def metadata(image):
    if image.mode == "RGB":
        return {"dimensions": list(image.size), "mode": image.mode, "format": image.format,
                "icc_profile": bool(image.info.get("icc_profile")), "alpha_extrema": [255, 255],
                "foreground_bounds": (0, 0, image.width, image.height), "foreground_fraction": 1.0}
    alpha = image.convert("RGBA").getchannel("A")
    return {"dimensions": list(image.size), "mode": image.mode, "format": image.format,
            "icc_profile": bool(image.info.get("icc_profile")),
            "alpha_extrema": list(alpha.getextrema()), "foreground_bounds": alpha.getbbox(),
            "foreground_fraction": 1 - alpha.histogram()[0] / (image.width * image.height)}


def _measure(a, b):
    histogram = np.zeros(256, dtype=np.int64)
    totals = np.zeros(3, dtype=np.int64)
    changed = {threshold: 0 for threshold in (0, 1, 4, 16, 32)}
    pixels = a.width * a.height
    for y in range(0, a.height, 128):
        box = (0, y, a.width, min(a.height, y + 128))
        delta = ImageChops.difference(a.crop(box), b.crop(box))
        channels = np.asarray(delta.histogram(), dtype=np.int64).reshape(3, 256)
        totals += channels @ np.arange(256, dtype=np.int64)
        histogram += channels.sum(axis=0)
        red, green, blue = delta.split()
        maximum = ImageChops.lighter(ImageChops.lighter(red, green), blue).histogram()
        for threshold in changed:
            changed[threshold] += sum(maximum[threshold + 1:])
    return {"rgb_mae": float(totals.sum() / (pixels * 3)),
            "channel_mae": (totals / pixels).tolist(),
            "p95": int(np.searchsorted(histogram.cumsum(), pixels * 3 * .95)),
            "p99": int(np.searchsorted(histogram.cumsum(), pixels * 3 * .99)),
            "maximum": int(np.flatnonzero(histogram)[-1]),
            "changed_fraction": {str(k): v / pixels for k, v in changed.items()}}


def regions(size, parameters):
    width, height = size
    result = {"background_top": (0, 0, width, max(1, height // 8)),
              "background_bottom": (0, height * 7 // 8, width, height)}
    for name, offset, extent in (("text", "text_offset", 1000), ("logo", "logo_offset", 1800)):
        span = min(height, extent)
        top = max(0, min(height - span, (height - span) // 2 + int(parameters.get(offset, 0))))
        result[name] = (0, top, width, top + span)
    return result


def compare_images(candidate, published, parameters=None):
    parameters = parameters or {}
    with Image.open(candidate) as ca, Image.open(published) as pu:
        if max(ca.width * ca.height, pu.width * pu.height) > 24_000_000:
            raise BulkError("image_size", "Comparison exceeds bounded image dimensions")
        ca.load(); pu.load()
        result = {"candidate": metadata(ca), "published": metadata(pu),
                  "same_dimensions": ca.size == pu.size, "alignment_applied": False}
        if ca.size != pu.size:
            return result
        a, b = ca.copy(), pu.copy()
    transparent = min(result["candidate"]["alpha_extrema"][0], result["published"]["alpha_extrema"][0]) < 255
    if transparent:
        a, b = a.convert("RGBA"), b.convert("RGBA")
        alpha = ImageChops.difference(a.getchannel("A"), b.getchannel("A"))
        result["alpha_mae"] = ImageStat.Stat(alpha).mean[0]
        result["alpha_maximum"] = alpha.getextrema()[1]
    else:
        result["alpha_mae"] = result["alpha_maximum"] = 0
    result["alpha_bounds_changed"] = result["candidate"]["foreground_bounds"] != result["published"]["foreground_bounds"]
    backgrounds = (0, 255) if transparent else (128,)
    composites = []
    regional_composites = []
    for background in backgrounds:
        if transparent:
            base = Image.new("RGBA", a.size, (background, background, background, 255))
            left, right = Image.alpha_composite(base, a).convert("RGB"), Image.alpha_composite(base, b).convert("RGB")
        else:
            left, right = a.convert("RGB"), b.convert("RGB")
        measure = _measure(left, right)
        measure["background"] = background
        composites.append(measure)
        regional = {}
        for name, box in regions(left.size, parameters).items():
            diff = ImageChops.difference(left.crop(box), right.crop(box))
            regional[name] = {"bounds": list(box), "rgb_mae": sum(ImageStat.Stat(diff).mean) / 3}
        regional_composites.append(regional)
    result["composites"] = composites
    result.update(max(composites, key=lambda value: value["rgb_mae"]))
    result["regions"] = {name: max((r[name] for r in regional_composites), key=lambda r: r["rgb_mae"])
                         for name in regional_composites[0]}
    la, lb = [np.asarray(im.resize((200, 300)).convert("L"), dtype=np.float64) for im in (left, right)]
    covariance = float(np.mean((la - la.mean()) * (lb - lb.mean())))
    result["global_luminance_ssim_200x300"] = float(
        (2 * la.mean() * lb.mean() + 6.5025) * (2 * covariance + 58.5225)
        / ((la.mean() ** 2 + lb.mean() ** 2 + 6.5025) * (la.var() + lb.var() + 58.5225)))
    edge_a, edge_b = [im.convert("L").filter(ImageFilter.FIND_EDGES) for im in (left, right)]
    result["edge_mae"] = ImageStat.Stat(ImageChops.difference(edge_a, edge_b)).mean[0]
    result["diagnostic_limits"] = "No OCR or automatic clipping certification; font/layout provenance and preflight remain mandatory"
    return result


def evaluate(metrics, policy):
    """Return a numerical screen and policy identity, never an approval decision."""
    if policy.get("schema_version") != 1 or not policy.get("version"):
        raise BulkError("invalid_policy", "Versioned tolerance policy required")
    thresholds = policy["thresholds"]
    if set(thresholds) != set(PROPOSED_POLICY["thresholds"]) or any(
            not isinstance(v, (int, float)) or not np.isfinite(v) or v < 0 for v in thresholds.values()):
        raise BulkError("invalid_policy", "Complete finite nonnegative thresholds required")
    failures = []
    if not metrics.get("same_dimensions"):
        failures.append("dimensions")
    else:
        for name in ("rgb_mae", "p99", "edge_mae", "alpha_mae"):
            if metrics[name] > thresholds[name]:
                failures.append(name)
        if metrics["changed_fraction"]["16"] > thresholds["changed_gt16"]:
            failures.append("changed_gt16")
        if metrics["global_luminance_ssim_200x300"] < thresholds["minimum_global_ssim"]:
            failures.append("global_ssim")
        if any(r["rgb_mae"] > thresholds["region_mae"] for r in metrics["regions"].values()):
            failures.append("region_mae")
    return {"screen_pass": not failures, "failures": failures,
            "policy_sha256": fingerprint(policy), "approval_granted": False}


def geometry_diagnostics(candidate, published, parameters=None, radius=8):
    """Original-coordinate region edges and bounded displacement diagnostics.

    Projection correlation is diagnostic only. It never aligns the artwork or
    changes the unaligned visual metrics or approval eligibility.
    """
    with Image.open(candidate) as left, Image.open(published) as right:
        if left.size != right.size:
            return {"same_dimensions": False, "alignment_applied": False}
        a, b = [im.convert("L").filter(ImageFilter.FIND_EDGES) for im in (left, right)]
    result = {"same_dimensions": True, "alignment_applied": False, "radius_original_pixels": radius, "regions": {}}
    for name, box in regions(a.size, parameters or {}).items():
        region = {}
        pairs = [im.crop(box) for im in (a, b)]
        region["edge_bounds"] = [im.point(lambda p: 255 if p > 32 else 0).getbbox() for im in pairs]
        region["origin"] = list(box[:2])
        shifts = {}
        for axis in ("x", "y"):
            size = (pairs[0].width, 1) if axis == "x" else (1, pairs[0].height)
            aa, bb = [np.asarray(im.resize(size, Image.Resampling.BOX), dtype=np.float64).ravel() for im in pairs]
            scores = []
            for shift in range(-radius, radius + 1):
                x, y = (aa[shift:], bb[:len(bb) - shift]) if shift >= 0 else (aa[:len(aa) + shift], bb[-shift:])
                if len(x) < 2 or not x.std() or not y.std():
                    score = -1.0
                else:
                    score = float(np.mean((x - x.mean()) * (y - y.mean())) / (x.std() * y.std()))
                scores.append((score, -abs(shift), -shift))
            best = max(scores)
            shifts[axis] = {"candidate_shift_pixels": -best[2], "projection_correlation": best[0]}
        region["bounded_projection_shift"] = shifts
        result["regions"][name] = region
    return result
