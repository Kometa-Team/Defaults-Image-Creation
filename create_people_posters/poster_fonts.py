"""Read the bundled fonts' Latin layout tables without a platform RAQM DLL."""

from io import BytesIO
from math import ceil
import unicodedata

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable


class FontMetrics:
    """Use original glyph outlines, kerning, ligatures and contextual forms."""
    def __init__(self, path):
        with TTFont(path) as font:
            self.cmap = font.getBestCmap()
            self.advances = dict(font["hmtx"].metrics)
            self.units = font["head"].unitsPerEm
            self.underline = font["post"].underlinePosition - font["post"].underlineThickness / 2
            self.left = {name: getattr(font["glyf"][name], "xMin", 0) for name in font.getGlyphOrder()}
            self.pairs, self.tables, self.substitutions = {}, [], []
            if "GPOS" in font:
                table = font["GPOS"].table
                indices = {i for r in table.FeatureList.FeatureRecord if r.FeatureTag == "kern" for i in r.Feature.LookupListIndex}
                for index in sorted(indices):
                    lookup = table.LookupList.Lookup[index]
                    for subtable in lookup.SubTable:
                        if lookup.LookupType == 2:
                            self.tables.append(subtable)
                        elif lookup.LookupType == 9 and subtable.ExtensionLookupType == 2:
                            self.tables.append(subtable.ExtSubTable)
            if not self.tables and "kern" in font:
                for table in font["kern"].kernTables:
                    if table.coverage & 1:
                        self.pairs.update(table.kernTable)
            self.gsub = font["GSUB"].table if "GSUB" in font else None
            if self.gsub:
                scripts = {r.ScriptTag: r.Script for r in self.gsub.ScriptList.ScriptRecord}
                script = scripts.get("latn", scripts.get("DFLT"))
                indices = script.DefaultLangSys.FeatureIndex if script and script.DefaultLangSys else []
                for tag in ("ccmp", "locl", "rlig", "liga", "clig", "calt"):
                    self.substitutions.extend(i for index in indices for r in [self.gsub.FeatureList.FeatureRecord[index]] if r.FeatureTag == tag for i in r.Feature.LookupListIndex)
            # Private cmap entries expose the *existing* glyphs to Pillow. This
            # adjusted font exists only in memory; no modified fonts are saved.
            self.characters = {glyph: chr(0xF0000 + index) for index, glyph in enumerate(font.getGlyphOrder())}
            bridge = CmapSubtable.newSubtable(12)
            bridge.platformID, bridge.platEncID, bridge.language = 3, 10, 0
            bridge.cmap = dict(self.cmap)
            bridge.cmap.update({ord(character): glyph for glyph, character in self.characters.items()})
            font["cmap"].tables.append(bridge)
            buffer = BytesIO()
            font.save(buffer)
            self.font_data = buffer.getvalue()

    def substitute(self, glyphs, index, lookup_index, depth=0):
        if index >= len(glyphs) or depth > 8:
            return
        lookup = self.gsub.LookupList.Lookup[lookup_index]
        for table in lookup.SubTable:
            kind = lookup.LookupType
            if kind == 7:
                kind, table = table.ExtensionLookupType, table.ExtSubTable
            if kind == 1:
                replacement = table.mapping.get(glyphs[index])
                if replacement:
                    glyphs[index] = replacement
                    return
            elif kind == 4:
                for ligature in table.ligatures.get(glyphs[index], []):
                    count = len(ligature.Component)
                    if glyphs[index+1:index+1+count] == ligature.Component:
                        glyphs[index:index+1+count] = [ligature.LigGlyph]
                        return
            elif kind == 6:
                if table.Format == 3:
                    rules = [(table.BacktrackCoverage, table.InputCoverage, table.LookAheadCoverage, table.SubstLookupRecord)]
                    covered = True
                elif table.Format == 1:
                    covered = glyphs[index] in table.Coverage.glyphs
                    group = table.ChainSubRuleSet[table.Coverage.glyphs.index(glyphs[index])] if covered else None
                    rules = [([set([g]) for g in r.Backtrack], [set([glyphs[index]]), *[set([g]) for g in r.Input]],
                              [set([g]) for g in r.LookAhead], r.SubstLookupRecord) for r in group.ChainSubRule] if group else []
                else:
                    raise ValueError("Unsupported contextual font layout; use the bundled fonts or POSTER_ENGINE=powershell")
                for back, inputs, ahead, records in rules:
                    def matches(coverage, glyph):
                        return glyph in (coverage.glyphs if hasattr(coverage, "glyphs") else coverage)
                    if (covered and index >= len(back) and index + len(inputs) + len(ahead) <= len(glyphs)
                            and all(matches(c, glyphs[index-1-j]) for j,c in enumerate(back))
                            and all(matches(c, glyphs[index+j]) for j,c in enumerate(inputs))
                            and all(matches(c, glyphs[index+len(inputs)+j]) for j,c in enumerate(ahead))):
                        for record in records:
                            self.substitute(glyphs, index+record.SequenceIndex, record.LookupListIndex, depth+1)
                        return

    def glyphs(self, text):
        text = unicodedata.normalize("NFC", text)
        missing = [c for c in text if ord(c) not in self.cmap]
        if missing:
            raise ValueError(f"Required font has no glyph for {missing[0]!r}; use a supported display alias or provide the required licensed font. No font substitution was made.")
        result = [self.cmap[ord(c)] for c in text]
        for lookup in self.substitutions:
            index = 0
            while index < len(result):
                self.substitute(result, index, lookup)
                index += 1
        return result

    def kern(self, left, right):
        value = self.pairs.get((left, right), 0)
        for table in self.tables:
            if left not in table.Coverage.glyphs:
                continue
            if table.Format == 1:
                pairs = table.PairSet[table.Coverage.glyphs.index(left)].PairValueRecord
                record = next((p for p in pairs if p.SecondGlyph == right), None)
            else:
                first, second = table.ClassDef1.classDefs.get(left, 0), table.ClassDef2.classDefs.get(right, 0)
                record = table.Class1Record[first].Class2Record[second]
            value += getattr(getattr(record, "Value1", None), "XAdvance", 0)
        return value

    def positions(self, text, size):
        positions, advance, previous = [], 0, None
        scale = size / self.units
        for glyph in self.glyphs(text):
            if previous is not None:
                advance += self.kern(previous, glyph) * scale
            positions.append((self.characters[glyph], advance))
            advance += self.advances[glyph][0] * scale
            previous = glyph
        return positions, advance

    def fitted_extent(self, text, size, height):
        lines = text.splitlines()
        widths = []
        for line in lines:
            glyphs = self.glyphs(line)
            width = self.positions(line, size)[1]
            bearing = min((self.left[g] for g in glyphs), default=0) * size / self.units
            widths.append(width + (2 * ceil(-bearing + .5) if bearing < 0 else 0))
        return max(widths, default=0) + 1, height * len(lines) - self.underline * size / self.units + 1
