"""Bounded new-source PNG inspection. No background removal or format repair."""

from dataclasses import dataclass
from io import BytesIO
import hashlib
import struct
import warnings
import zlib

from PIL import Image, ImageChops

from ...common import BulkError, fingerprint

# Memory/parser safety budgets, NOT perceptual acceptance thresholds. At most
# 64 MiB for the decoded RGBA surface; diagnostics use a bounded analysis copy.
MAX_BYTES = 16 * 1024 * 1024
MAX_PIXELS = 16 * 1024 * 1024
MAX_EDGE = 8192
MAX_CHUNKS = 65536
PNG = b"\x89PNG\r\n\x1a\n"


def fail(code, message):
    raise BulkError(code, message)


def png_integrity(raw):
    """Check every chunk CRC and termination, not only Pillow's IDAT decode."""
    if type(raw) is not bytes or not raw.startswith(PNG) or len(raw) > MAX_BYTES:
        fail("logo_png_signature", "Expected bounded actual PNG bytes; formats are never converted")
    pos, kinds, count = 8, [], 0
    while pos < len(raw):
        if pos + 12 > len(raw) or count >= MAX_CHUNKS:
            fail("logo_png_chunks", "Truncated or excessive PNG chunks")
        size = struct.unpack(">I", raw[pos:pos + 4])[0]
        kind = raw[pos + 4:pos + 8]
        if any(not (65 <= byte <= 90 or 97 <= byte <= 122) for byte in kind) or not 65 <= kind[2] <= 90:
            fail("logo_png_chunks", "Invalid PNG chunk type or reserved bit")
        if 65 <= kind[0] <= 90 and kind not in {b"IHDR",b"PLTE",b"IDAT",b"IEND"}:
            fail("logo_png_chunks", "Unknown critical PNG chunk cannot be safely interpreted")
        end = pos + size + 12
        if end > len(raw) or size > MAX_BYTES:
            fail("logo_png_chunks", "Invalid PNG chunk extent")
        if zlib.crc32(raw[pos + 4:end - 4]) & 0xffffffff != struct.unpack(">I", raw[end - 4:end])[0]:
            fail("logo_png_crc", "PNG CRC mismatch")
        if kind in {b"acTL", b"fcTL", b"fdAT"}:
            fail("logo_png_animation", "Only single-frame PNG sources are supported")
        kinds.append(kind)
        pos, count = end, count + 1
        if kind == b"IHDR":
            if count != 1 or size != 13:
                fail("logo_png_header", "IHDR must be the first unique PNG header")
            width, height = struct.unpack(">II", raw[end - 17:end - 9])
            if raw[end-9] not in {1,2,4,8}:
                fail("logo_png_depth", "Only supported at-most-8-bit PNG samples are accepted; no silent precision reduction")
            if not width or not height or max(width, height) > MAX_EDGE or width * height > MAX_PIXELS:
                fail("logo_png_resource", "PNG exceeds decoded-pixel/edge safety budget")
        if kind == b"IEND":
            if size or pos != len(raw):
                fail("logo_png_termination", "PNG has invalid IEND or trailing data")
            break
    if kinds.count(b"IHDR") != 1 or b"IDAT" not in kinds or not kinds or kinds[-1] != b"IEND":
        fail("logo_png_chunks", "PNG header, image data and terminator are required")


def encode_png(image):
    output = BytesIO()
    image.save(output, format="PNG", compress_level=9)
    return output.getvalue()


@dataclass(frozen=True)
class Asset:
    encoded: bytes
    report_json: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.encoded).hexdigest()

    def report(self):
        import json
        return json.loads(self.report_json)

    def image(self):
        # Already bounded and CRC checked at construction. Return a detached copy.
        with Image.open(BytesIO(self.encoded)) as image:
            image.load()
            return image.convert("RGBA")


def inspect_png(raw):
    from ...common import canonical
    png_integrity(raw)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as opened:
                if opened.format != "PNG" or opened.mode not in {"RGBA", "RGB", "P", "LA", "L", "1"} or getattr(opened, "n_frames", 1) != 1:
                    fail("logo_png_mode", "Unsupported PNG mode or frame count")
                mode, size = opened.mode, opened.size
                # Color conversion with ICC is not silently inferred here. The
                # original profile remains bound; overlays use their existing
                # approved ICC adapter. Human review resolves source color intent.
                profile = opened.info.get("icc_profile")
                opened.verify()
            with Image.open(BytesIO(raw)) as opened:
                opened.load()
                image = opened.convert("RGBA")
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        if isinstance(error, BulkError):
            raise
        raise BulkError("logo_png_decode", "PNG integrity/decode failed") from error
    alpha = image.getchannel("A")
    histogram = alpha.histogram()
    bounds = alpha.getbbox()
    if bounds is None:
        fail("logo_empty", "Fully transparent logos are invalid even with an exception")
    pixels = size[0] * size[1]
    edges = [alpha.crop(box).histogram() for box in [(0, 0, size[0], 1), (0, size[1]-1, size[0], size[1]),
                                                    (0, 0, 1, size[1]), (size[0]-1, 0, size[0], size[1])]]
    contacts = [sum(h[1:]) for h in edges]
    opaque_edges = [h[255] for h in edges]
    # Necessary transparency and a fully clear outer boundary are different
    # facts. Border contact can mean a legitimate tight export OR clipping/matte.
    # Never infer a complete letter/brand from alpha alone.
    blockers = [] if histogram[0] else ["no_fully_transparent_pixels"]
    diagnostics = []
    if any(contacts): diagnostics.append("foreground_edge_contact_requires_review")
    if all(opaque_edges): diagnostics.append("rectangular_matte_or_clipping_requires_review")
    if histogram[0] and all(opaque_edges) and bounds == (0, 0, *size):
        blockers.append("rectangular_alpha_background_not_proven_transparent")
    if histogram[0] and sum(contacts) and bounds == (0, 0, *size):
        diagnostics.append("alpha_channel_does_not_prove_clean_background")
    if profile: diagnostics.append("embedded_color_profile_requires_context_review")
    # Explicit descriptive measurements; no invented automatic halo/readability
    # threshold. Each intended output is rendered separately in the preview step.
    soft = image.copy()
    soft.thumbnail((128, 128), Image.Resampling.LANCZOS)
    soft_alpha = soft.getchannel("A")
    mid = soft_alpha.point(lambda a: 255 if 0 < a < 255 else 0)
    halo = {"soft_edge_samples": mid.histogram()[255],
            "rgb_at_soft_edges": [ImageChops.multiply(c, mid).getextrema() for c in soft.convert("RGB").split()],
            "analysis_size": list(soft.size), "interpretation": "descriptive_only_human_quality_review_required"}
    report = {"sha256": hashlib.sha256(raw).hexdigest(), "integrity": "valid", "mode": mode,
        "dimensions": list(size), "visible_bounds": list(bounds), "alpha_min": alpha.getextrema()[0],
        "clear_pixels": histogram[0], "opaque_pixels": histogram[255], "partial_pixels": sum(histogram[1:255]),
        "pixels": pixels, "edge_visible_pixels_top_bottom_left_right": contacts,
        "default_transparency_blockers": blockers, "diagnostics": diagnostics, "halo_observations": halo,
        "quality": "review_required_clipping_lettering_and_readability_not_automatically_proven",
        "icc_sha256": hashlib.sha256(profile).hexdigest() if profile else None}
    return Asset(raw, canonical(report))
