"""One pinned, scope-limited validation engine for audits, previews and generation."""

from collections import Counter
from functools import lru_cache
from io import BytesIO, StringIO
import csv
import html
import json
from pathlib import Path
import time
import unicodedata

from PIL import Image, ImageFont

from create_defaults.create_poster import PosterOptions, output_filename
from create_defaults.poster_text import load_layout
from .common import BulkError, atomic_bytes, canonical, confined, fingerprint, path_key, sha256, normalize_hex
from .config import Config, select_categories
from .definitions import Definition
from .languages import CONTRIBUTION, local_snapshot
from .planner import Planner, SHARED_ASSETS, effective_parameters, renderer_identity


POLICY = {"version": "preflight-d1", "layout": "composer-native-metrics-d1", "risk": "review-risk-d1",
          "near_edge_pixels": 20, "rtl": "blocked-awaiting-approved-font-and-visual-review",
          "translated_fit": "explicit-caption-font-bound-overrides-only"}
ELIGIBLE = {"ready", "ready_with_warning", "shared"}


@lru_cache(maxsize=1)
def _historical_index():
    value = json.loads((Path(__file__).parent / "catalog/index-v1.json").read_text())
    if value["sha256"] != fingerprint({k: v for k, v in value.items() if k != "sha256"}):
        raise BulkError("corrupt_catalog", "Historical identity index changed")
    return value["posters"]


def _preserved_color(item):
    original = _historical_index().get(item["id"], {})
    return (item["color_assignment"]["origin"] == "historical" and item["source"].get("kind") != "authored"
            and original.get("source_row") == item["source"]["row_sha256"]
            and original.get("historical_background") is not None
            and normalize_hex(original["historical_background"]) == normalize_hex(item["composer"]["base_color"]))


def variant_id(poster, language):
    return "poster." + fingerprint({"poster_id": poster, "language": language, "variant": "base"})[:24]


def consolidate_missing(records):
    groups = {}
    for row in records:
        token = (row["language"], row["key"], row["reason"], row["source_snapshot"])
        if token not in groups:
            groups[token] = dict(row, poster_ids=[], variant_ids=[], categories=[], category_posters={}, fallbacks={})
        merged = groups[token]
        merged["poster_ids"].extend(row["poster_ids"])
        merged["variant_ids"].extend(row["variant_ids"])
        merged["categories"].extend(row.get("categories", [row["category"]]))
        for category, posters in row.get("category_posters", {row["category"]: row["poster_ids"]}).items():
            merged["category_posters"].setdefault(category, []).extend(posters)
        merged["fallbacks"].update(row.get("fallbacks", {poster: row["fallback"] for poster in row["poster_ids"]}))
    for row in groups.values():
        row["poster_ids"], row["variant_ids"] = sorted(set(row["poster_ids"])), sorted(set(row["variant_ids"]))
        row["categories"] = sorted(set(row["categories"]))
        row["category"] = ", ".join(row["categories"])
        row["category_posters"] = {category: sorted(set(ids)) for category, ids in row["category_posters"].items()}
        row["logical_poster_count"], row["rendered_variant_count"] = len(row["poster_ids"]), len(row["variant_ids"])
    return sorted(groups.values(), key=lambda r: (r["language"], r["key"], r["reason"]))


@lru_cache(maxsize=1024)
def _metrics(font_path, modified_ns, text, size):
    """Use the composer's exact shaping, wrapping and FreeType glyph bounds."""
    layout = load_layout(font_path, modified_ns)
    layout.validate(text)
    lines = layout.wrap(text, size, 1900)
    font = ImageFont.truetype(BytesIO(layout.font_data), size, layout_engine=ImageFont.Layout.BASIC)
    ascent, descent = font.getmetrics()
    line_height = ascent + descent
    bounds, widths = None, []
    top = (1000 - len(lines) * line_height) // 2
    for row, line in enumerate(lines):
        positions, width = layout.positions(line, size, legacy_width=True)
        widths.append(width)
        for glyph, x, y in positions:
            left, upper, right, lower = font.getbbox(glyph, anchor="ls")
            if right <= left or lower <= upper:
                continue
            box = ((1900 - width) / 2 + x + left, top + ascent + row * line_height + y + upper,
                   (1900 - width) / 2 + x + right, top + ascent + row * line_height + y + lower)
            bounds = box if bounds is None else (min(bounds[0], box[0]), min(bounds[1], box[1]),
                                                max(bounds[2], box[2]), max(bounds[3], box[3]))
    clipped = bool(bounds and (bounds[0] < 0 or bounds[1] < 0 or bounds[2] > 1900 or bounds[3] > 1000))
    near = bool(bounds and (bounds[0] < 20 or bounds[1] < 20 or bounds[2] > 1880 or bounds[3] > 980))
    return {"lines": lines, "line_widths": widths, "line_height": line_height,
            "ink_bounds": list(bounds) if bounds else None, "clipped": clipped, "near_edge": near,
            "method": "existing-FontLayout-and-FreeType-no-poster-raster"}


def risk(diagnostics, *, language, caption, prior=None):
    reasons = sorted({d["code"] for d in diagnostics if d["severity"] != "info"})
    if language != "en" and caption:
        reasons.append("translated_caption")
    if prior in {"rejected", "approval_stale"}:
        reasons.append(prior)
    return {"version": POLICY["risk"], "level": "high" if reasons else "low", "reasons": sorted(set(reasons)),
            "requires_individual": bool(reasons)}


def select_previews(report, *, explicit=(), high_risk=False, representatives=0):
    eligible = [v for v in report["variants"] if v["status"] in ELIGIBLE]
    ids = {v["id"] for v in eligible}
    if set(explicit) - ids:
        raise BulkError("blocked_preview", "Explicit previews must be current eligible variants")
    chosen = set(explicit)
    if high_risk:
        chosen.update(v["id"] for v in eligible if v["risk"]["level"] == "high")
    groups = {}
    for value in sorted(eligible, key=lambda v: v["id"]):
        if value["risk"]["level"] == "low":
            groups.setdefault((value["category"], value["language"]), []).append(value["id"])
    for group in groups.values():
        chosen.update(group[:representatives])
    return sorted(chosen)


def effective_language(definition, language):
    """Explicit versioned local-only expansion; never invent remote destinations."""
    value = definition.for_language(language).data
    if language not in value["languages"] and language not in value["applicability"] and value["source"]["path"] == "create_default_posters.ps1":
        value["languages"].append(language)
        value["applicability"][language] = {"status": "applicable", "reason": "Package D defaults component policy v1; local review output only"}
        value["output"]["remote_paths"][language] = None
        for dependency in value["dependencies"]:
            name = dependency["input"]
            if value["composer"][name].startswith("defaults-en/"):
                value["composer"][name] = "defaults-" + language + "/" + value["composer"][name][len("defaults-en/"):]
    return value


def preflight(definitions, translations, *, config=None, generators=None, categories=(), posters=(),
              languages=("en",), registry=None, policy="partial", color_registry=None, resources=None, variant_ids=None, prepared=None):
    if policy not in {"partial", "strict", "audit", "review"}:
        raise BulkError("invalid_policy", "Expected partial, strict, audit or review")
    config = config or Config()
    started = time.perf_counter()
    if registry is None:
        # In-memory pinned values, not paths that could be refreshed during a run.
        records = []
        from .config import LANGUAGES
        from .languages import LanguageSnapshot
        for code in sorted(set(LANGUAGES) | set(translations.sources)):
            records.append({"code": code, "native_code": code, "display_name": None, "resource": code + ".yml",
                            "sha256": translations.hashes.get(code), "components": ["defaults"],
                            "availability": "available" if code in translations.sources else "not_discovered",
                            "font_support": "requires_variant_preflight"})
        registry = LanguageSnapshot.create(records, provenance={"kind": "explicit-loaded-values"})
    languages = registry.select(languages)
    for code, checksum in translations.hashes.items():
        resource = registry.record(code)
        if resource and resource["availability"] == "available" and resource["sha256"] != checksum:
            raise BulkError("snapshot_mismatch", "Loaded translation differs from pinned language registry: " + code)
    if not languages:
        raise BulkError("empty_selection", "No requested poster languages")
    planner = Planner(config, generators=generators)
    catalog, families, origins = prepared if prepared is not None else planner.expand(definitions)
    categories = select_categories(categories)
    wanted = set()
    for identity in posters:
        if identity in families:
            wanted.update(families[identity])
        elif identity in catalog:
            wanted.add(identity)
        else:
            raise BulkError("invalid_selection", "Unknown logical poster: " + identity)
    selected = {key for key, d in catalog.items() if (not categories or d.category in categories) and (not posters or key in wanted)}
    if not selected or not (categories or posters):
        raise BulkError("empty_selection", "Explicit poster/category/catalog selection required")
    ordered, visiting, visited = [], set(), set()
    def visit(identity):
        if identity in visiting:
            raise BulkError("dependency_cycle", "Cyclic generated-input dependency")
        if identity in visited:
            return
        if identity not in catalog:
            raise BulkError("missing_dependency", "Required logical dependency absent")
        visiting.add(identity)
        for dep in catalog[identity].data["dependencies"]:
            visit(dep["poster_id"])
        visiting.remove(identity)
        visited.add(identity)
        ordered.append(identity)
    for identity in sorted(selected):
        visit(identity)
    if len(ordered) * len(languages) > 200000:
        raise BulkError("oversize_preflight", "A single report is bounded to 200,000 variants; audit larger inventories by category/language")
    required_variants = None
    if variant_ids is not None:
        required_variants = set()
        known = {variant_id(identity, language) for identity in selected for language in languages}
        if set(variant_ids) - known:
            raise BulkError("invalid_selection", "Variant selector outside the requested logical/language scope")
        def include_variant(identity, language):
            key = variant_id(identity, language)
            if key in required_variants:
                return
            required_variants.add(key)
            for dep in catalog[identity].data["dependencies"]:
                include_variant(dep["poster_id"], language)
        for identity in selected:
            for language in languages:
                if variant_id(identity, language) in variant_ids:
                    include_variant(identity, language)
    if color_registry is None and any(not _preserved_color(catalog[key].data) for key in ordered):
        from .colors import ColorPolicy, ColorRegistry
        from .state import Store
        color_registry = ColorRegistry(Store(config.cache_dir / "state.sqlite"), ColorPolicy("D01-d1", 8.0, 4.5))
        with color_registry.store.connection() as db:
            imported = db.execute("SELECT 1 FROM color_assignments WHERE origin='historical' LIMIT 1").fetchone()
        if not imported:
            audit = json.loads((Path(__file__).parents[1] / "phase2/evidence/historical-colors.json").read_text(encoding="utf-8"))
            color_registry.import_historical(audit)
    approved = json.loads((Path(__file__).parent / "baselines/approved-fonts.json").read_text(encoding="utf-8"))["fonts"]
    renderer = renderer_identity()
    resources = resources if resources is not None else {}
    hashes = resources.setdefault("hashes", {})
    stats = resources.setdefault("stats", {})
    image_checks = resources.setdefault("images", set())
    checked = set()
    resolved_paths = {}
    initial_hashes = len(hashes)
    variants, effective, by_key, audits, paths, proposal_colors = [], {}, {}, {}, {}, {}
    def checked_hash(relative):
        if relative in checked:
            return hashes[relative]
        path = confined(config.asset_dir, relative, must_exist=True)
        resolved_paths[relative] = path
        stat = path.stat()
        token = (str(config.asset_dir), stat.st_size, stat.st_mtime_ns)
        if relative in stats and stats[relative] != token:
            raise BulkError("changed_input", "Pinned source changed during validation session")
        if relative not in hashes:
            hashes[relative] = sha256(path)
            stats[relative] = token
        checked.add(relative)
        return hashes[relative]
    for identity in ordered:
        definition = catalog[identity]
        for language in languages:
            if required_variants is not None and variant_id(identity, language) not in required_variants:
                continue
            item = effective_language(definition, language)
            caption, diagnostics, inputs, key_dependencies = None, [], {}, []
            entry = {"id": variant_id(identity, language), "poster_id": identity, "language": language, "category": definition.category,
                     "selected": identity in selected, "status": "ready", "diagnostics": diagnostics,
                     "private": item["output"]["directory"].startswith("_intermediates/"),
                     "definition_fingerprint": fingerprint(item), "dependencies": [variant_id(d["poster_id"], language) for d in item["dependencies"]]}
            def diagnose(code, message, severity="error", **details):
                diagnostics.append({"code": code, "severity": severity, "message": str(message), "details": details})
            def audit_key(key, error):
                record = registry.record(language)
                token = (language, key, error.code)
                if token not in audits:
                    try:
                        english = translations.lookup("en", key)[0]
                    except BulkError:
                        english = None
                    audits[token] = {"language": language, "display_name": record.get("display_name"), "category": definition.category,
                        "key": key, "english_source": english, "reason": error.code, "message": str(error),
                        "component": "defaults", "resource": record.get("resource"), "source_snapshot": registry.fingerprint,
                        "fallback": item["caption"]["fallback"], "fallbacks": {}, "categories": [], "category_posters": {},
                        "poster_ids": [], "variant_ids": [], "contribution": registry.data["contribution"]}
                audits[token]["poster_ids"].append(identity)
                audits[token]["variant_ids"].append(entry["id"])
                audits[token]["categories"].append(definition.category)
                audits[token]["category_posters"].setdefault(definition.category, []).append(identity)
                audits[token]["fallbacks"][identity] = item["caption"]["fallback"]
            app = item["applicability"].get(language)
            record = registry.record(language)
            if item["source"].get("kind") == "authored":
                diagnose("proposed_definition", "Proposed artwork requires individual visual review; preview does not activate it", "warning")
            from .config import LANGUAGES
            if language not in LANGUAGES:
                diagnose("new_language", "Language is outside the previously reviewed compatibility baseline", "warning")
            if "defaults" not in record["components"]:
                entry["status"] = "not_applicable"
                diagnose("component_not_applicable", "Discovered language has no poster defaults component", "info")
            elif app and app["status"] == "not_applicable":
                entry["status"] = "not_applicable"
                diagnose("not_applicable", app["reason"], "info")
            elif language not in item["languages"] or not app or app["status"] != "applicable":
                diagnose("unknown_applicability", "Definition does not explicitly support this language")
            else:
                for key in filter(None, (item["caption"]["key"], item["caption"]["template_key"])):
                    try:
                        text, trace = translations.lookup(language, key)
                        if not text.strip():
                            raise BulkError("invalid_translation", "Translation is empty")
                        key_dependencies.append({"language": language, "key": key, "value_sha256": trace["value_sha256"]})
                    except BulkError as error:
                        key_dependencies.append({"language": language, "key": key, "error": error.code})
                        audit_key(key, error)
                try:
                    caption = translations.resolve(item["caption"], language)
                    for trace in caption.trace:
                        if {"language", "key", "value_sha256"} <= trace.keys() and not any(k.get("language") == trace["language"] and k.get("key") == trace["key"] for k in key_dependencies):
                            key_dependencies.append({k: trace[k] for k in ("language", "key", "value_sha256")})
                    if caption.mode == "translation" and not caption.text.strip():
                        raise BulkError("invalid_translation", "Resolved caption is empty")
                    # A valid fallback remains visible; it does not masquerade as a completed translation.
                    if any("fallback" in trace for trace in caption.trace):
                        diagnose("approved_fallback", "Using explicit reviewer-bound fallback", "warning")
                    font_hash = checked_hash(item["composer"]["font"])
                    font_path = resolved_paths[item["composer"]["font"]]
                    inputs["font"] = {"path": item["composer"]["font"], "sha256": font_hash}
                    if approved.get(item["composer"]["font"]) != font_hash:
                        raise BulkError("unapproved_font", "Font is not hash-bound to approved bundled provenance")
                    text = caption.text
                    if any(unicodedata.category(char) in {"Cs", "Co", "Cn"} or (unicodedata.category(char) == "Cc" and char not in "\t\n\r") for char in text):
                        raise BulkError("invalid_unicode", "Caption contains unassigned, private-use, surrogate or control characters")
                    if any(unicodedata.bidirectional(char) in {"R", "AL", "AN", "RLE", "RLO", "RLI", "LRE", "LRO", "LRI", "FSI", "PDI", "PDF"} for char in text) or item["caption"]["direction"] != "auto":
                        raise BulkError("rtl_awaiting_review", "RTL/directional variant requires approved script font and joining/bidi/anchor visual validation")
                    try:
                        metrics = _metrics(str(font_path), stats[item["composer"]["font"]][2], text, effective_parameters(item["composer"])["font_size"]) if text else None
                    except ValueError as error:
                        raise BulkError("missing_glyph", str(error)) from error
                    entry["layout_probe"] = metrics
                    measure = item["layout"]["measurement"]
                    if item["layout"]["kind"] == "captured_fit" and (measure["text"] != text or measure["font_sha256"] != font_hash or measure["point_size"] != item["composer"]["font_size"]):
                        raise BulkError("stale_measurement", "Translated fitting needs an explicit caption/font-bound language override; English fitting is not reused")
                    if metrics and metrics["clipped"]:
                        diagnose("caption_clipping", "Native glyph bounds extend outside the fixed caption box", "warning" if language == "en" and item["source"].get("kind") != "authored" else "error")
                    elif metrics and metrics["near_edge"]:
                        diagnose("caption_near_edge", "Caption approaches a fixed clipping boundary", "warning")
                    if metrics and len(metrics["lines"]) > 1:
                        diagnose("wrapped_caption", "Composer wraps caption into multiple rows", "warning", lines=metrics["lines"])
                    for relative in SHARED_ASSETS:
                        inputs[relative] = {"path": relative, "sha256": checked_hash(relative)}
                    generated = {d["input"] for d in item["dependencies"]}
                    for role in ("logo", "avg_color_image"):
                        relative = item["composer"][role]
                        if relative and role not in generated and (role == "logo" or (item["composer"]["avg_color"] and not item["composer"]["base_color"])):
                            inputs[role] = {"path": relative, "sha256": checked_hash(relative)}
                            if relative not in image_checks:
                                with Image.open(confined(config.asset_dir, relative, must_exist=True)) as image:
                                    if image.width * image.height > 24_000_000 or getattr(image, "n_frames", 1) != 1:
                                        raise BulkError("invalid_image", "Logo exceeds bounded single-frame image contract")
                                    image.verify()
                                image_checks.add(relative)
                    parameters = effective_parameters(dict(item["composer"], text=text))
                    if output_filename(PosterOptions(**parameters), parameters["base_color"]) != item["output"]["filename"]:
                        raise BulkError("output_mismatch", "Declared filename differs from approved composer")
                    local = "/".join(filter(None, ("defaults-" + language, item["output"]["directory"], item["output"]["filename"])))
                    entry["local_relative"] = local
                    entry["remote_relative"] = item["output"]["remote_paths"].get(language)
                    for prefix, path in (("local:", local), ("remote:", entry["remote_relative"])):
                        if path is not None:
                            token = prefix + path_key(path)
                            if token in paths:
                                previous = by_key[paths[token]]
                                previous["diagnostics"].append({"code": "output_collision", "severity": "error", "message": "Another active variant targets this output", "details": {"conflict": entry["id"]}})
                                previous["status"] = "blocked"
                                raise BulkError("output_collision", "Conflicting active output paths across dependency stages")
                            paths[token] = entry["id"]
                    if not _preserved_color(item):
                        if color_registry is None:
                            raise BulkError("color_registry_required", "Authored/inherited assignments require D01 registry validation")
                        color = color_registry.evaluate(identity, definition.category, parameters["base_color"],
                            relationship=item["color_assignment"]["relationship"], exception=item["color_assignment"]["exception"])
                        entry["color_policy"] = color
                        diagnostics.extend(color["diagnostics"])
                        proposal_colors.setdefault((definition.category, parameters["base_color"]), {})[identity] = item["color_assignment"]
                    else:
                        diagnose("historical_color_preserved", "Existing color retained, not automatically declared an approved exception", "info")
                except (BulkError, OSError) as error:
                    diagnose(getattr(error, "code", "invalid_image"), error)
                    if getattr(error, "code", None) == "unresolved_caption":
                        for key in filter(None, (item["caption"]["key"], item["caption"]["template_key"])):
                            audit_key(key, error)
            for dependency in entry["dependencies"] if entry["status"] != "not_applicable" else ():
                parent = by_key.get(dependency)
                if not parent or parent["status"] not in ELIGIBLE:
                    diagnose("blocked_dependency", "Required parent variant is blocked or non-applicable", dependency=dependency)
            if any(d["severity"] == "error" for d in diagnostics):
                entry["status"] = "blocked"
            elif entry["status"] != "not_applicable":
                entry["status"] = "ready_with_warning" if any(d["severity"] == "warning" for d in diagnostics) else ("shared" if item["caption"]["mode"] != "translation" else "ready")
            entry["caption"] = caption.text if caption else None
            entry["translation_dependencies"] = key_dependencies
            entry["inputs"] = inputs
            entry["risk"] = risk(diagnostics, language=language, caption=entry["caption"])
            exact = dict(item, overrides=[], languages=[language], applicability={language: item["applicability"].get(language)})
            exact["output"] = dict(item["output"], remote_paths={language: item["output"]["remote_paths"].get(language)})
            origin = origins.get(identity)
            relevant = {"definition": exact, "generator": {k: v for k, v in origin.items() if k != "parent_fingerprint"} if origin else None, "inputs": inputs, "keys": key_dependencies,
                        "caption": entry["caption"], "language_mapping": {k: v for k, v in (registry.record(language) or {}).items() if k in {"code", "native_code", "components"}},
                        "parents": [by_key[d]["validation_fingerprint"] for d in entry["dependencies"] if d in by_key],
                        "renderer": renderer, "policy": POLICY, "color": entry.get("color_policy")}
            entry["validation_fingerprint"] = fingerprint(relevant)
            by_key[entry["id"]] = entry
            variants.append(entry)
            if entry["status"] in ELIGIBLE:
                effective[(identity, language)] = Definition.create(item)
    for (category, color), members in proposal_colors.items():
        if len(members) < 2:
            continue
        permitted = False
        with color_registry.store.connection() as db:
            for assignment in members.values():
                group = db.execute("SELECT payload FROM color_relationships WHERE id=?", (assignment["relationship"],)).fetchone()
                if group and set(members) <= set(json.loads(group["payload"])["members"]):
                    permitted = True
                exception = db.execute("SELECT payload FROM color_exceptions WHERE id=?", (assignment["exception"],)).fetchone()
                permit = json.loads(exception["payload"]) if exception else {}
                if permit.get("active") and permit.get("policy") == color_registry.policy.fingerprint and permit.get("category") == category and permit.get("hex") == color and set(members) <= set(permit.get("affected_ids", [])):
                    permitted = True
        if not permitted:
            for entry in variants:
                if entry["poster_id"] in members:
                    entry["status"] = "blocked"
                    entry["diagnostics"].append({"code": "scope_color_collision", "severity": "error", "message": "Unrelated proposed logical posters claim the same category HEX", "details": {"hex": color, "posters": sorted(members)}})
    # Collision eligibility and parent failures can change after an earlier row
    # was visited. Bind the final outcome and exact parent validations in order.
    for entry in variants:
        if entry["status"] in ELIGIBLE and any(by_key[d]["status"] not in ELIGIBLE for d in entry["dependencies"]):
            entry["status"] = "blocked"
            entry["diagnostics"].append({"code": "blocked_dependency", "severity": "error", "message": "Required parent became blocked", "details": {}})
        entry["validation_fingerprint"] = fingerprint({"base": entry["validation_fingerprint"], "status": entry["status"],
            "diagnostics": entry["diagnostics"], "parents": [by_key[d]["validation_fingerprint"] for d in entry["dependencies"] if d in by_key]})
    missing = []
    for row in audits.values():
        row["poster_ids"] = sorted(set(row["poster_ids"]))
        row["variant_ids"] = sorted(set(row["variant_ids"]))
        row["logical_poster_count"], row["rendered_variant_count"] = len(row["poster_ids"]), len(row["variant_ids"])
        missing.append(row)
    missing = consolidate_missing(missing)
    counts = dict(Counter(v["status"] for v in variants))
    report = {"schema_version": 1, "policy": POLICY, "execution_policy": policy, "registry_sha256": registry.fingerprint,
              "translation_hashes": translations.hashes, "renderer": renderer, "languages": list(languages),
              "selection": {"categories": list(categories), "posters": list(posters), "variant_ids": sorted(variant_ids) if variant_ids is not None else None}, "variants": variants,
              "coverage": counts, "missing_translations": missing,
              "status": "strict_blocked" if counts.get("blocked") and policy == "strict" else "partial" if counts.get("blocked") else "complete"}
    report["sha256"] = fingerprint(report)
    directory = config.cache_dir / "preflight" / report["sha256"]
    export_report(report, directory)
    report["report_directory"] = str(directory)
    report["metrics"] = {"elapsed_seconds": time.perf_counter() - started, "logical_definitions": len(ordered),
                         "variants": len(variants), "unique_inputs_hashed": len(hashes) - initial_hashes, "full_poster_renders": 0}
    return report, effective


def export_report(report, directory):
    directory = Path(directory)
    payload = {key: value for key, value in report.items() if key not in {"report_directory", "metrics"}}
    target = directory / "preflight.json"
    if not target.exists():
        atomic_bytes(target, canonical(payload) + b"\n")
    stream = StringIO(newline="")
    fields = ("language", "display_name", "category", "key", "english_source", "reason", "logical_poster_count", "rendered_variant_count", "poster_ids", "resource", "source_snapshot", "contribution")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in report["missing_translations"]:
        writer.writerow({key: (json.dumps(row[key], ensure_ascii=True) if isinstance(row.get(key), (list, dict)) else row.get(key)) for key in fields})
    if not (directory / "translations.csv").exists():
        atomic_bytes(directory / "translations.csv", stream.getvalue().encode("utf-8"))
    e = lambda value: html.escape(str(value or ""))
    rows = "".join("<tr>" + "".join("<td>" + e(v) + "</td>" for v in (r["language"], r["category"], r["key"], r["reason"], r["logical_poster_count"], r["english_source"], ", ".join(r["poster_ids"]))) + "</tr>" for r in report["missing_translations"])
    variants = "".join("<tr>" + "".join("<td>" + e(v) + "</td>" for v in (r["poster_id"], r["language"], r["status"], "; ".join(d["message"] for d in r["diagnostics"] if d["severity"] != "info"))) + "</tr>" for r in report["variants"])
    content = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Poster preflight</title><style>body{font:14px system-ui;margin:24px}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:8px;border-bottom:1px solid #ccc;overflow-wrap:anywhere}section{overflow:auto}</style><h1>Poster Preflight</h1><p>' + e(report["status"]) + ' | Snapshot ' + e(report["registry_sha256"]) + '</p><p><a href="https://translations.kometa.wiki/">Contribute translations</a>. Direct-key navigation unavailable: anonymous component mappings require sign-in.</p><h2>Missing Translations</h2><section><table><tr><th>Language<th>Category<th>Key<th>Reason<th>Posters<th>English<th>Affected IDs</tr>' + rows + '</table></section><h2>Variants</h2><section><table><tr><th>Poster<th>Language<th>Status<th>Diagnostics</tr>' + variants + '</table></section></html>'
    if not (directory / "index.html").exists():
        atomic_bytes(directory / "index.html", content.encode("utf-8"))
