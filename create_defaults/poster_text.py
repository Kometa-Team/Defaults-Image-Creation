"""Deterministic font resolution and glyph layout, without installed-font fallback."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import math
from pathlib import Path
import re
import unicodedata

from fontTools.ttLib import TTFont, TTLibError
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
from PIL import Image, ImageDraw, ImageFont
import uharfbuzz as hb
from bidi.algorithm import (get_empty_storage, get_base_level, get_embedding_levels,
                            explicit_embed_and_overrides, resolve_weak_types,
                            resolve_neutral_types, resolve_implicit_levels, reorder_resolved_levels)


FONT_FILES = (
    "Barlow-Regular.ttf", "BebasNeue-Regular.ttf", "BoecklinsUniverse.ttf", "Boogaloo-Regular.ttf",
    "CherryCreamSoda-Regular.ttf", "Comfortaa-Medium.ttf", "PlusJakartaSans-Bold.ttf", "Jura-Bold.ttf",
    "Limelight-Regular.ttf", "Monoton-Regular.ttf", "Press-Start-2P.ttf", "Righteous-Regular.ttf",
    "Rye-Regular.ttf", "SpecialElite-Regular.ttf", "Trochut-Regular.ttf",
    "UnifrakturCook-Bold.ttf", "Yesteryear-Regular.ttf",
)


def token(name):
    return re.sub("[^a-z0-9]", "", Path(str(name).replace("\\", "/")).stem.lower())


def resolve_font(name, font_dir):
    if not name:
        raise ValueError("A font is required for a nonempty caption; random font fallback is disabled")
    candidate = Path(name).expanduser()
    if not candidate.is_absolute() and not candidate.is_file():
        legacy_relative = Path(font_dir).parent / candidate
        if legacy_relative.is_file():
            candidate = legacy_relative
    if candidate.is_file():
        return candidate.resolve()
    if candidate.is_absolute() or "/" in str(name) or "\\" in str(name):
        raise FileNotFoundError(f"Required font file is missing: {name}; no substitution was made")
    aliases = {token(filename): filename for filename in FONT_FILES}
    aliases["bebasneue"] = "BebasNeue-Regular.ttf"
    aliases.update({"unifrakturcook": "UnifrakturCook-Bold.ttf", "monoton": "Monoton-Regular.ttf",
                    "righteous": "Righteous-Regular.ttf", "trochut": "Trochut-Regular.ttf",
                    "yesteryear": "Yesteryear-Regular.ttf"})
    filename = aliases.get(token(name))
    candidate = Path(font_dir) / filename if filename else None
    if candidate is None or not candidate.is_file():
        raise FileNotFoundError(f"Required font {name!r} is unavailable in {font_dir}; no substitution was made")
    return candidate.resolve()


def directional_runs(text):
    """Resolve the Unicode BiDi levels, then shape each original logical run."""
    storage = get_empty_storage()
    storage["base_level"] = get_base_level(text)
    storage["base_dir"] = "R" if storage["base_level"] else "L"
    get_embedding_levels(text, storage)
    for index, char in enumerate(storage["chars"]):
        char["index"] = index
    explicit_embed_and_overrides(storage)
    resolve_weak_types(storage)
    resolve_neutral_types(storage, False)
    resolve_implicit_levels(storage, False)
    runs = []
    for char in storage["chars"]:
        if not runs or runs[-1][0] != char["level"]:
            runs.append((char["level"], []))
        char["run"] = len(runs) - 1
        runs[-1][1].append(char["ch"])
    reorder_resolved_levels(storage, False)
    order = list(dict.fromkeys(char["run"] for char in storage["chars"]))
    return [("".join(runs[index][1]), "rtl" if runs[index][0] % 2 else "ltr") for index in order]


def install_unicode_bridge(font, bridge):
    # FontTools cannot sort two cmap entries with the same identity and differing maps.
    key = (bridge.platformID, bridge.platEncID, bridge.language)
    font["cmap"].tables = [table for table in font["cmap"].tables
                           if (table.platformID, table.platEncID, table.language) != key]
    font["cmap"].tables.append(bridge)


class FontLayout:
    """Expose original glyphs through an in-memory cmap, as the People renderer does.

    HarfBuzz supplies shaping/kerning/mark positions, including Arabic; Pillow
    rasterizes the original outlines. No modified font is written or distributed.
    """

    def __init__(self, path):
        self.path = Path(path)
        data = self.path.read_bytes()
        self.hb_font = hb.Font(hb.Face(data))
        self.units = self.hb_font.face.upem
        self.hb_font.scale = (self.units, self.units)
        with TTFont(BytesIO(data)) as font:
            self.cmap = font.getBestCmap()
            self.glyph_order = font.getGlyphOrder()
            self.characters = [chr(0xF0000 + i) for i in range(len(self.glyph_order))]
            bridge = CmapSubtable.newSubtable(12)
            bridge.platformID, bridge.platEncID, bridge.language = 3, 10, 0
            bridge.cmap = dict(self.cmap)
            bridge.cmap.update({ord(c): g for c, g in zip(self.characters, self.glyph_order)})
            install_unicode_bridge(font, bridge)
            buffer = BytesIO()
            # Preserve raw outline tables before attempting optional bounds
            # parsing; strict FontTools failures must not affect FreeType input.
            font.save(buffer)
            self.font_data = buffer.getvalue()
            if "glyf" in font:
                try:
                    self.right_edges = [getattr(font["glyf"][glyph], "xMax", 0) for glyph in self.glyph_order]
                except TTLibError:
                    # FreeType may accept outlines rejected by FontTools.
                    # Measure that exact face; never replace or rewrite it.
                    self.right_edges = None
            else:
                from fontTools.pens.boundsPen import BoundsPen
                glyphs = font.getGlyphSet()
                self.right_edges = []
                for glyph in self.glyph_order:
                    pen = BoundsPen(glyphs)
                    glyphs[glyph].draw(pen)
                    self.right_edges.append(pen.bounds[2] if pen.bounds else 0)
        self.native_bounds = {}
        self.measurement_font = (ImageFont.truetype(BytesIO(self.font_data), self.units, layout_engine=ImageFont.Layout.BASIC)
                                 if self.right_edges is None else None)

    def validate(self, text):
        for character in unicodedata.normalize("NFC", text):
            if character in "\n\r\t" or unicodedata.category(character) == "Cf":
                continue
            if ord(character) not in self.cmap:
                raise ValueError(f"Font {self.path.name} has no glyph for {character!r} (U+{ord(character):04X}); no substitution was made")

    def positions(self, text, size, legacy_width=False):
        self.validate(text)
        positions, advance = [], 0.0
        final_advance, final_right = 0.0, 0.0
        for run, direction in directional_runs(unicodedata.normalize("NFC", text)):
            buffer = hb.Buffer()
            buffer.add_str(run)
            buffer.guess_segment_properties()
            buffer.direction = direction
            hb.shape(self.hb_font, buffer)
            for glyph, position in zip(buffer.glyph_infos, buffer.glyph_positions):
                scale = size / self.units
                positions.append((self.characters[glyph.codepoint], advance + position.x_offset * scale,
                                  -position.y_offset * scale))
                advance += position.x_advance * scale
                final_advance = position.x_advance * scale
                if self.right_edges is None:
                    if glyph.codepoint not in self.native_bounds:
                        self.native_bounds[glyph.codepoint] = self.measurement_font.getbbox(self.characters[glyph.codepoint], anchor="ls")[2]
                    final_right = self.native_bounds[glyph.codepoint] * scale
                else:
                    final_right = self.right_edges[glyph.codepoint] * scale
        if legacy_width:
            # ImageMagick measures the last glyph by max(advance, outline xMax).
            # Ignoring a script glyph's overhang miscenters shorter caption rows.
            advance = math.ceil(advance + max(0, final_right - final_advance))
        return positions, advance

    def width(self, text, size):
        return self.positions(text, size, legacy_width=True)[1]

    def wrap(self, text, size, width=1900):
        text = text.replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n").expandtabs(4)
        self.validate(text)
        lines = []
        for paragraph in text.split("\n"):
            current = ""
            for word in paragraph.split(" "):
                proposed = current + (" " if current else "") + word
                if current and self.width(proposed, size) > width:
                    lines.append(current)
                    current = word
                else:
                    current = proposed
                # A single over-wide word is clipped, not split into invented
                # extra lines. This matters for legacy separators/display fonts.
            lines.append(current)
        return lines

    def caption(self, text, size, color, box=(1900, 1000)):
        if len(text) > 16_384:
            raise ValueError("Caption exceeds the 16,384-character safety limit")
        font = ImageFont.truetype(BytesIO(self.font_data), size, layout_engine=ImageFont.Layout.BASIC)
        lines = self.wrap(text, size, box[0])
        # ImageMagick caption baselines use ascent - descent, not FreeType's
        # recommended face height (notably different for Cherry Cream Soda).
        line_height = sum(font.getmetrics())
        if len(lines) * line_height > 24_000:
            raise ValueError("Wrapped caption exceeds the bounded text workspace")
        layouts = [self.positions(line, size, legacy_width=True) for line in lines]
        # Fixed-size legacy caption clipping occurs before trim/center extent.
        canvas = Image.new("RGBA", box)
        draw = ImageDraw.Draw(canvas)
        ascent = font.getmetrics()[0]
        top = (box[1] - len(lines) * line_height) // 2
        for index, (positions, width) in enumerate(layouts):
            for glyph, x, y in positions:
                draw.text(((box[0] - width) / 2 + x, top + ascent + index * line_height + y),
                          glyph, font=font, fill=color, anchor="ls")
        bounds = canvas.getchannel("A").getbbox()
        result = Image.new("RGBA", box)
        if bounds:
            cropped = canvas.crop(bounds)
            result.alpha_composite(cropped, ((box[0] - cropped.width) // 2, (box[1] - cropped.height) // 2))
        return result, {"lines": lines, "point_size": size, "ink_bounds": bounds,
                        "line_height": line_height, "line_widths": [w for _, w in layouts],
                        "glyph_bounds_source": "native FreeType fallback for existing outline-table parse error" if self.right_edges is None else "original font outline bounds",
                        "advances": [self.positions(line, size)[1] for line in lines]}


@lru_cache(maxsize=8)
def load_layout(path, modified_ns):
    return FontLayout(path)
