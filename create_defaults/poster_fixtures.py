"""Read-only extraction of literal bulk-generator tables for parity fixtures.

This is not a bulk generator or a replacement category-definition format. The
existing PowerShell and existing translation file remain the source of truth.
"""

from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass, field
import json
from pathlib import Path
import re

from fontTools.ttLib import TTFont
import yaml

try:
    from .create_poster import PosterOptions, ROOT, digest
    from .poster_text import FONT_FILES, resolve_font, token
except ImportError:
    from create_poster import PosterOptions, ROOT, digest
    from poster_text import FONT_FILES, resolve_font, token

FIELDS = "key_name logo logo_offset logo_resize text_offset font font_size font_color border border_width border_color avg_color_image out_name base_color gradient clean avg_color white_wash".split()
CATEGORY_DIRS = {"AudioLanguage": "audio_language", "SubtitleLanguage": "subtitle_language", "Awards": "award",
                 "ContentRating": "content_rating", "VideoFormat": "video_format", "Separators": "separator"}


def translation_file(asset_dir=ROOT):
    cached = Path(asset_dir) / "@translations/en.yml"
    return cached if cached.is_file() else ROOT / "fixtures/english/en.yml"


@dataclass
class Case:
    id: str
    category: str
    parameters: dict
    source_line: int
    source_row: dict
    published_relative: str | None = None
    notes: list[str] = field(default_factory=list)
    fit: tuple[int, int, int, int] | None = None
    expected_failure: bool = False
    kind: str = "poster"


def extract_rows(script=ROOT / "create_default_posters.ps1"):
    """Parse only complete literal CSV strings; never evaluate PowerShell code."""
    lines = Path(script).read_text(encoding="utf-8-sig").splitlines()
    category, rows, fit = None, [], {"theMaxWidth": 1800, "theMaxHeight": 1000, "minPointSize": 100, "maxPointSize": 250}
    for number, line in enumerate(lines, 1):
        function = re.match(r"(?i)^function\s+Create(\w+)\s*\{", line)
        if function:
            category = function[1]
            fit = dict(theMaxWidth=1800, theMaxHeight=1000, minPointSize=100, maxPointSize=250)
        setting = re.fullmatch(r"\s*\$(theMaxWidth|theMaxHeight|minPointSize|maxPointSize)\s*=\s*(\d+)\s*", line)
        if setting:
            fit[setting[1]] = int(setting[2])
        literal = re.fullmatch(r"\s*'((?:[^']|'')*)'\s*,?\s*", line)
        if not category or not literal or "|" not in literal[1]:
            continue
        values = next(csv.reader([literal[1].replace("''", "'")], delimiter="|", quoting=csv.QUOTE_NONE))
        values = [value.strip() for value in values]
        if values[0] == "key_name":
            if values != FIELDS:
                raise ValueError(f"Unexpected bulk fixture table schema at line {number}")
            continue
        if len(values) != len(FIELDS):
            raise ValueError(f"Malformed literal fixture row at line {number}")
        row = dict(zip(FIELDS, values))
        # The following command, not just the category, identifies root assets.
        tail = "\n".join(lines[number:])
        command = re.search(r'^\s*\$arr \+= .*?create_poster\.ps1.*$', tail, re.M)
        command = command[0] if command else ""
        directory = re.search(r'\$script_path\\(logos_\w+)\\', command)
        logo = Path(directory[1]) / row["logo"] if directory else Path(row["logo"])
        move = re.search(r'Move-Item -Path output -Destination ([^\s\r\n]+)', tail)
        destination = move[1].strip('"').replace("\\", "/") if move else CATEGORY_DIRS.get(category, category.lower())
        if destination == "output-orig":
            destination = CATEGORY_DIRS.get(category, category.lower())
        rows.append(dict(category=category, line=number, row=row, logo=str(logo), command=command,
                         destination=destination, fit=tuple(fit.values())))
    return rows


def font_inventory(rows, asset_dir=ROOT):
    inventory = []
    provenance = json.loads((ROOT / "font_provenance.json").read_text(encoding="utf-8"))
    resolved = {name: resolve_font(name, Path(asset_dir) / "fonts").name
                for name in {r["row"]["font"] for r in rows}}
    for filename in FONT_FILES:
        path = Path(asset_dir) / "fonts" / filename
        requests = [item for item in rows if resolved[item["row"]["font"]] == filename]
        item = {"file": str(path.resolve()), "requested_names": sorted({r["row"]["font"] for r in requests}),
                "categories": dict(Counter(r["category"] for r in requests)), "missing": not path.is_file()}
        if path.is_file():
            with TTFont(path) as font:
                cmap = font.getBestCmap()
                texts = lambda ids: sorted({n.toUnicode() for n in font["name"].names if n.nameID in ids})
                license_text = texts({13, 14})
                joined = " ".join(license_text)
                status = ("SIL OFL 1.1 (embedded declaration)" if "Open Font License" in joined
                          else "Apache 2.0 (embedded declaration)" if "Apache" in joined
                          else "License unverified; permission/review required before redistribution or service use")
                if filename == "Helvetica-Bold.ttf":
                    status = "Proprietary Helvetica; user must establish license for intended use; do not redistribute"
                item.update(sha256=digest(path), license_status=status, license_metadata=license_text,
                            copyright=texts({0}), family=texts({1, 2, 6}), character_count=len(cmap),
                            supported_codepoints=sorted(cmap), arabic=sum(0x600 <= c <= 0x6FF for c in cmap),
                            missing_probe_characters=[c for c in "Caf\u00e9 \u00c5ngstr\u00f6m \u0416 \u0627\u0644\u0639\u0631\u0628\u064a\u0629" if ord(c) not in cmap])
                evidence = provenance["fonts"].get(filename)
                if evidence:
                    if evidence["sha256"] == item["sha256"]:
                        item.update(license_status=evidence["license_status"], license_evidence=evidence,
                                    license_reviewed_on=provenance["reviewed_on"])
                    else:
                        item["provenance_warning"] = "Font hash differs from the reviewed asset; curated license evidence was not applied"
        inventory.append(item)
    inventory.append({"requested_names": ["Cairo-Regular"], "categories": {}, "missing": True,
                      "license_status": "Mentioned in bulk-generator comment only; no active table requests it; not bundled",
                      "note": "None of the 17 active bundled fonts covers Arabic. Never silently substitute for translated Arabic captions."})
    return inventory


def translation_caption(item, translations):
    row, category = item["row"], item["category"]
    key = row["key_name"]
    if not key:
        return ""
    if category in {"Year", "Decade"} and key[0].isdigit():
        return key
    key_names = {str(k).casefold(): v for k, v in translations.get("key_names", {}).items()}
    collections = {str(k).casefold(): v for k, v in translations.get("collections", {}).items()}
    if key.casefold() in collections and row["logo"] == "transparent.png" and not row["logo_resize"] == "0":
        value = collections[key.casefold()].get("name", "")
    else:
        if key.casefold() not in key_names:
            raise ValueError(f"Missing English translation for {key!r} at bulk line {item['line']}")
        value = key_names[key.casefold()]
    if category in {"AudioLanguage", "SubtitleLanguage"} and row["logo_resize"] == "0":
        collection = "audio_language" if category == "AudioLanguage" else "subtitle_language"
        value = re.sub(r"<<.*?>>", str(value), collections[collection]["name"])
    if category == "Separators":
        value = re.sub(r"<<.*?>>", str(value), collections["separator"]["name"])
    return str(value).upper()


def row_case(item, translations, asset_dir):
    row = item["row"]
    parameters = {k: v for k, v in row.items() if k in PosterOptions.__dataclass_fields__ and v != ""}
    for name in ("logo_offset", "logo_resize", "text_offset", "font_size", "border_width", "gradient"):
        if name in parameters:
            parameters[name] = int(parameters[name])
    for name in ("border", "clean", "avg_color", "white_wash"):
        parameters[name] = bool(int(parameters[name]))
    parameters.update(logo=str((Path(asset_dir) / item["logo"]).resolve()) if row["logo"] else None,
                      text=translation_caption(item, translations))
    if item["category"] == "Separators":
        parameters.update(logo=str((Path(asset_dir) / "@base" / "blue.png").resolve()), out_name="blue/" + row["out_name"])
    notes = []
    if not row["base_color"]:
        # The separator generator delegates a random color to the composer;
        # freeze that one nondeterministic input for identical-engine testing.
        parameters["base_color"] = "#436790"
        notes.append("Bulk separator requests a random base; comparison freezes #436790 for both engines")
    caption = parameters["text"]
    fit = item["fit"]
    if row["font_size"] and item["category"] in {"Decade", "Year"}:
        fit = (*fit[:3], int(row["font_size"]))
        if token(row["font"]) == "plusjakartasansbold":
            fit = None
            notes.append("Approved numeric Jakarta definition uses its fixed font_size, bypassing bulk auto-fitting")
    expected_failure = False
    case = Case(f"{item['category'].lower()}-{item['line']}", item["category"], parameters, item["line"], row,
                published_relative=f"{item['destination']}/{row['out_name']}.jpg", fit=fit if caption else None,
                expected_failure=expected_failure, notes=notes)
    if parameters["logo_resize"] == 0:
        case.notes.append("Unmodified real bulk row: numeric logo_resize=0 defaults to 2000 through PowerShell empty-string coercion")
    if item["category"] == "Separators":
        case.published_relative = "separators/blue/" + row["out_name"] + ".jpg"
        case.notes.append("Generated command supplies @base/blue.png and blue/ output subdirectory; not an empty logo")
    return case


def build_cases(asset_dir=ROOT, script=None):
    asset_dir = Path(asset_dir)
    rows = extract_rows(script or ROOT / "create_default_posters.ps1")
    translations = yaml.safe_load(translation_file(asset_dir).read_text(encoding="utf-8-sig"))
    selected = []
    # One real definition per poster category, including the legacy numeric
    # zero-width/default behavior in language and decade configurations.
    for category in dict.fromkeys(r["category"] for r in rows):
        choices = [r for r in rows if r["category"] == category]
        choice = next((r for r in choices if r["row"]["logo"] != "transparent.png"), choices[0])
        if category in {"Decade", "Year"}:
            choice = next(r for r in choices if r["row"]["key_name"][0].isdigit())
        selected.append(row_case(choice, translations, asset_dir))
    for category in ("AudioLanguage", "SubtitleLanguage"):
        selected.append(row_case(next(r for r in rows if r["category"] == category and r["row"]["key_name"] == "ARABIC"), translations, asset_dir))
    selected.append(row_case(next(r for r in rows if r["category"] == "Genre" and r["row"]["key_name"] == "1001_MOVIES_YOU_MUST_SEE_BEFORE_YOU_DIE"), translations, asset_dir))
    selected.append(row_case(next(r for r in rows if r["category"] == "Country" and r["row"]["key_name"] == "\u00c5LAND_ISLANDS"), translations, asset_dir))
    # Valid real year rows exercise all fifteen historical typefaces. Short,
    # long and multiline variants are explicitly labeled stress probes, not
    # misrepresented as published category configurations.
    resolved = {name: resolve_font(name, asset_dir / "fonts").name
                for name in {r["row"]["font"] for r in rows}}
    for filename in FONT_FILES:
        matching = [r for r in rows if resolved[r["row"]["font"]] == filename]
        choice = next((r for r in matching if r["category"] == "Year" and r["row"]["key_name"].isdigit()), matching[0])
        original = row_case(choice, translations, asset_dir)
        if not any(c.source_line == original.source_line for c in selected):
            selected.append(original)
        for label, caption in (("short", "TV"), ("long", "THE MOVIES THAT DEFINED OUR CHILDHOOD"), ("multiline", "MOVIES\\nAND TELEVISION")):
            parameters = dict(original.parameters, text=caption, font_size=200)
            selected.append(Case(f"font-{token(filename)}-{label}", "Font probe", parameters, original.source_line,
                                 original.source_row, notes=["Caption-only stress variant of the cited real category row"], fit=None))
        with TTFont(asset_dir / "fonts" / filename) as font:
            if all(ord(c) in font.getBestCmap() for c in "Caf\u00e9 \u00c5ngstr\u00f6m"):
                selected.append(Case(f"font-{token(filename)}-accents", "Font probe",
                                     dict(original.parameters, text="Caf\u00e9 \u00c5ngstr\u00f6m", font_size=180), original.source_line,
                                     original.source_row, notes=["Supported accented-character probe; no substituted font"], fit=None))
    base = next(c for c in selected if c.category == "Genre")
    for gradient in range(5):
        selected.append(Case(f"feature-gradient-{gradient}", "Feature probe", dict(base.parameters, gradient=gradient),
                             base.source_line, base.source_row, notes=["Gradient-only variant of real genre configuration"], fit=base.fit))
    for label, changes in (
        ("border", dict(border=True, border_width=37, border_color="#17B87A")),
        ("color-logo-positive-offset", dict(white_wash=False, logo_offset=500, text_offset=-850)),
        ("small-logo", dict(logo_resize=200)), ("large-logo", dict(logo_resize=2000)),
        ("no-caption", dict(text="")), ("average", dict(base_color="", avg_color=True, avg_color_image=base.parameters["logo"])),
        ("dominant", dict(dom_color=True, dom_color_image=base.parameters["logo"], border=True, border_color=None)),
    ):
        selected.append(Case(f"feature-{label}", "Feature probe", dict(base.parameters, **changes),
                             base.source_line, base.source_row, notes=["Explicit feature variant of real genre configuration"], fit=None))
    colored = str((asset_dir / "logos_streaming" / "Netflix.png").resolve())
    selected.append(Case("feature-colored-average", "Feature probe",
                         dict(base.parameters, base_color="", avg_color=True, avg_color_image=colored),
                         base.source_line, base.source_row,
                         notes=["Additional real colored-logo extraction probe; white logos alone cannot establish color parity"]))
    selected.append(Case("feature-colored-dominant", "Feature probe",
                         dict(base.parameters, dom_color=True, dom_color_image=colored, border=True, border_color=None),
                         base.source_line, base.source_row,
                         notes=["Legacy dominant-color flags are intentionally no-op, even with a red source image; extraction remains deferred"]))
    # These read-only reference probes are explicitly not poster/API outputs.
    for name, trim in (("Genre", False), ("Network", True)):
        source = next(c for c in selected if c.category == name)
        for label, size in (("standard", (285, 85)), ("bigger", (440, 100))):
            selected.append(Case(f"overlay-{label}-{name.lower()}", "Overlays",
                                 dict(logo=source.parameters["logo"], size=size, trim=trim), 6901, {},
                                 published_relative=f"{name.lower()}/overlays/{label}/{Path(source.parameters['logo']).name}",
                                 notes=["Read-only reproduction of the existing overlay transform, not a composer output or a replacement bulk workflow"], kind="overlay-reference"))
    return rows, selected
