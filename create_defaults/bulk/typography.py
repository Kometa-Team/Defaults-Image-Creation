"""Exact-input translated typography evidence; proposals never activate typography."""
from copy import deepcopy
from functools import lru_cache
from io import BytesIO
import unicodedata

from PIL import ImageFont
from create_defaults.poster_text import FontLayout
from .common import BulkError, fingerprint, sha256

VERSION = "translated-native-fit-e2"
POLICY = {"version": VERSION, "box": [1900, 1000], "near_edge_pixels": 20,
          "unusual_wrap_lines": 4, "proposal_minimum": 100, "proposal_step": 10,
          "proposal_activation": "explicit-version-bound-review-required"}

@lru_cache(maxsize=64)
def _font(path, digest):
    if sha256(path) != digest:
        raise BulkError("changed_input", "Font bytes differ from the measurement identity")
    return FontLayout(path)

def validate_text(text, direction="auto"):
    if len(text) > 16384:
        raise BulkError("oversize_caption", "Caption exceeds the bounded text contract")
    if any(unicodedata.category(c) in {"Cs", "Co", "Cn"} or
           (unicodedata.category(c) == "Cc" and c not in "\t\n\r") for c in text):
        raise BulkError("invalid_unicode", "Caption contains unsupported Unicode or control characters")
    if direction != "auto" or any(unicodedata.bidirectional(c) in
            {"R", "AL", "AN", "RLE", "RLO", "RLI", "LRE", "LRO", "LRI", "FSI", "PDI", "PDF"} for c in text):
        raise BulkError("rtl_awaiting_review", "RTL requires approved script font and joining/bidi/anchor review")

@lru_cache(maxsize=32768)
def _measure(path, digest, text, size, offset, renderer, version):
    layout = _font(path, digest)
    layout.validate(text)
    lines = layout.wrap(text, size, 1900)
    font = ImageFont.truetype(BytesIO(layout.font_data), size, layout_engine=ImageFont.Layout.BASIC)
    ascent, descent = font.getmetrics()
    height = ascent + descent
    if len(lines) * height > 24000:
        raise BulkError("caption_clipping", "Wrapped caption exceeds the bounded compositor workspace")
    top = (1000 - len(lines) * height) // 2
    bounds, widths = None, []
    for index, line in enumerate(lines):
        positions, width = layout.positions(line, size, legacy_width=True)
        widths.append(width)
        for glyph, x, y in positions:
            left, upper, right, lower = font.getbbox(glyph, anchor="ls")
            if right <= left or lower <= upper:
                continue
            box = ((1900 - width) / 2 + x + left, top + ascent + index * height + y + upper,
                   (1900 - width) / 2 + x + right, top + ascent + index * height + y + lower)
            bounds = box if bounds is None else (min(bounds[0], box[0]), min(bounds[1], box[1]),
                                                max(bounds[2], box[2]), max(bounds[3], box[3]))
    clipped = bool(bounds and (bounds[0] < 0 or bounds[1] < 0 or bounds[2] > 1900 or bounds[3] > 1000))
    near = bool(bounds and (bounds[0] < 20 or bounds[1] < 20 or bounds[2] > 1880 or bounds[3] > 980))
    # The compositor trims and centers ink within the caption box, then centers
    # that box on the poster and adds text_offset. Check that actual extent too.
    ink_height = bounds[3] - bounds[1] if bounds else 0
    poster_bounds = [1000 - (bounds[2] - bounds[0]) / 2, 1500 + offset - ink_height / 2,
                     1000 + (bounds[2] - bounds[0]) / 2, 1500 + offset + ink_height / 2] if bounds else None
    outside = bool(poster_bounds and (poster_bounds[0] < 0 or poster_bounds[1] < 0 or
                                     poster_bounds[2] > 2000 or poster_bounds[3] > 3000))
    return {"lines": lines, "line_widths": widths, "line_height": height,
            "ink_bounds": list(bounds) if bounds else None, "clipped": clipped,
            "near_edge": near, "poster_ink_bounds": poster_bounds, "outside_image": outside,
            "method": "existing-FontLayout-and-FreeType-no-poster-raster"}

def measure(path, digest, text, size, offset, renderer):
    return deepcopy(_measure(str(path), digest, text, size, offset, renderer, fingerprint(POLICY)))

def evaluate(path, digest, text, size, offset, renderer, *, direction="auto", proposals=True):
    validate_text(text, direction)
    current = measure(path, digest, text, size, offset, renderer)
    inputs = {"caption": text, "font_sha256": digest, "point_size": size,
              "text_offset": offset, "renderer": renderer, "policy": POLICY}
    result = {"version": VERSION, "inputs": inputs, "measurement_key": fingerprint(inputs),
              "current": current, "state": "fits_current", "proposal": None,
              "artwork_approval": "not_granted"}
    if current["clipped"] or current["outside_image"]:
        result["state"] = "geometric_failure"
        if proposals:
            # Only propose smaller supported sizes; never change current inputs.
            minimum = min(size, POLICY["proposal_minimum"])
            sizes = list(range(size - POLICY["proposal_step"], minimum - 1, -POLICY["proposal_step"]))
            if minimum < size and minimum not in sizes:
                sizes.append(minimum)
            for candidate in sizes:
                metrics = measure(path, digest, text, candidate, offset, renderer)
                if not metrics["clipped"] and not metrics["outside_image"]:
                    proposal = {"font_size": candidate, "text_offset": offset,
                                "metrics": metrics, "inputs": dict(inputs, point_size=candidate),
                                "activation": "not_approved_or_activated"}
                    proposal["sha256"] = fingerprint(proposal)
                    result["proposal"], result["state"] = proposal, "needs_layout_review"
                    break
    result["sha256"] = fingerprint(result)
    return result

def cache_info():
    return {"measurements": _measure.cache_info()._asdict(), "fonts": _font.cache_info()._asdict()}
