"""Translation value deltas and exact indexed dependent-variant selection."""

from .common import fingerprint
from .translations import key_token


def _flatten(value, prefix=""):
    output = {}
    if isinstance(value, dict):
        for key, child in value.items():
            output.update(_flatten(child, prefix + ("." if prefix else "") + key_token(key)))
    else:
        output[prefix] = fingerprint(value)
    return output


def translation_delta(before, after, *, old_registry=None, new_registry=None):
    changes = []
    for language in sorted(set(before.sources) | set(after.sources)):
        old = _flatten(before.sources.get(language, {}))
        new = _flatten(after.sources.get(language, {}))
        for key in sorted(old.keys() | new.keys()):
            if old.get(key) != new.get(key):
                changes.append({"language": language, "key": key, "kind": "added" if key not in old else "removed" if key not in new else "modified",
                                "before": old.get(key), "after": new.get(key)})
    old_codes = set(r["code"] for r in old_registry.data["languages"]) if old_registry else set(before.sources)
    new_codes = set(r["code"] for r in new_registry.data["languages"]) if new_registry else set(after.sources)
    mapping_changes = []
    if old_registry and new_registry:
        for code in sorted(old_codes & new_codes):
            relevant = lambda registry: {k: v for k, v in registry.record(code).items() if k in {"code", "native_code", "components", "availability"}}
            if relevant(old_registry) != relevant(new_registry):
                mapping_changes.append(code)
        old_aliases, new_aliases = old_registry.data["aliases"], new_registry.data["aliases"]
        for alias in old_aliases.keys() | new_aliases.keys():
            if old_aliases.get(alias) != new_aliases.get(alias):
                mapping_changes.extend(code for code in (old_aliases.get(alias), new_aliases.get(alias)) if code in old_codes | new_codes)
    value = {"schema_version": 1, "changes": changes, "new_languages": sorted(new_codes - old_codes),
             "removed_languages": sorted(old_codes - new_codes), "mapping_changes": sorted(set(mapping_changes)),
             "old_snapshot": old_registry.fingerprint if old_registry else fingerprint(before.hashes),
             "new_snapshot": new_registry.fingerprint if new_registry else fingerprint(after.hashes)}
    value["sha256"] = fingerprint(value)
    return value


def affected_variants(delta, report):
    changes = {(c["language"], key_token(c["key"])) for c in delta["changes"]}
    affected = []
    for variant in report["variants"]:
        if variant["language"] in delta["removed_languages"] + delta["mapping_changes"] or any((k["language"], key_token(k["key"])) in changes for k in variant["translation_dependencies"]):
            affected.append(variant["id"])
    # New languages need scoped applicability expansion; aliases are not jobs.
    return {"variant_ids": sorted(affected), "new_languages_requiring_preflight": delta["new_languages"]}


def validation_delta(before, after):
    old = {v["id"]: v["validation_fingerprint"] for v in before["variants"]}
    new = {v["id"]: v["validation_fingerprint"] for v in after["variants"]}
    return {"added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()),
            "changed": sorted(k for k in old.keys() & new.keys() if old[k] != new[k])}


def regenerate(delta, previous_report, definitions, translations, *, registry, reviews=None, **options):
    """Selective re-preflight/render using the same generation engine and pool."""
    from .generation import generate
    from .preflight import variant_id
    selected = affected_variants(delta, previous_report)
    ids = set(selected["variant_ids"])
    previous = {v["id"]: v for v in previous_report["variants"]}
    posters = {previous[k]["poster_id"] for k in ids}
    languages = {previous[k]["language"] for k in ids}
    for language in delta["new_languages"]:
        for variant in previous_report["variants"]:
            posters.add(variant["poster_id"])
            ids.add(variant_id(variant["poster_id"], language))
        languages.add(language)
    if reviews:
        reviews.invalidate_keys([(c["language"], c["key"]) for c in delta["changes"]], reason=delta["sha256"], languages=delta["removed_languages"] + delta["mapping_changes"])
    if not ids:
        return {"status": "verified", "stages": [], "changed_variants": []}
    missing = set(languages) - {r["code"] for r in registry.data["languages"]}
    if missing:
        from .languages import LanguageSnapshot
        records = registry.data["languages"] + [{"code": code, "native_code": code, "components": ["defaults"], "availability": "unavailable", "resource": None, "sha256": None, "font_support": "unavailable", "display_name": None} for code in sorted(missing)]
        registry = LanguageSnapshot.create(records, provenance={"kind": "delta-with-unavailable-tombstones", "source_snapshot": registry.fingerprint})
    result = generate(definitions, translations, posters=sorted(posters), languages=sorted(languages), variant_ids=sorted(ids), registry=registry, **options)
    if reviews:
        reviews.attach(result)
    result["changed_variants"] = sorted(ids)
    return result
