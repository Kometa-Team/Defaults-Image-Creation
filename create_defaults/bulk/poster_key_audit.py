"""Poster-required key coverage, independent from typography and artwork review."""
from collections import Counter
import re
import unicodedata

from .common import BulkError, fingerprint
from .translations import key_token

VERSION = "poster-key-audit-e2"

def identical_exemption(text, key, approved_unchanged=()):
    if (key, text) in approved_unchanged:
        return "explicitly_approved_unchanged"
    if re.fullmatch(r"[\d\s.,:/()+%-]+", text):
        return "number_or_numeric_label"
    if text.isupper() and sum(c.isalpha() for c in text) <= 10:
        return "acronym_candidate"
    # Names cannot be reliably inferred from capitalization alone.
    if key.split(".")[0].casefold() in {"studio", "studios", "network", "networks", "franchise", "universe"}:
        return "proper_name_key"
    return None

def poster_key_audit(reports, translations, registry, *, approved_unchanged=()):
    variants = {v["id"]: v for report in reports for v in report["variants"]}
    required = {}
    for v in variants.values():
        if v["status"] == "not_applicable":
            continue
        for dependency in v["translation_dependencies"]:
            language, key = v["language"], dependency["key"]
            token = (language, key_token(key))
            row = required.setdefault(token, {"language": language, "key": key, "key_aliases": set(),
                "poster_ids": set(), "variant_ids": set(), "categories": set(), "category_posters": {}})
            row["key_aliases"].add(key)
            row["poster_ids"].add(v["poster_id"])
            row["variant_ids"].add(v["id"])
            row["categories"].add(v["category"])
            row["category_posters"].setdefault(v["category"], set()).add(v["poster_id"])
    rows = []
    for (language, token), value in sorted(required.items()):
        row = {k: sorted(v) if isinstance(v, set) else v for k, v in value.items()}
        row["category_posters"] = {k: sorted(v) for k, v in row["category_posters"].items()}
        row["key_token"] = token
        row["source"] = registry.record(language)
        row["source_snapshot"] = registry.fingerprint
        row["english_reference"], row["english_value_sha256"] = None, None
        try:
            english, trace = translations.lookup("en", row["key"])
            row["english_reference"], row["english_value_sha256"] = english, trace["value_sha256"]
        except BulkError:
            english = None
        row.update(status="valid", identical_to_english=False, identical_exemption=None, value_sha256=None)
        try:
            text, trace = translations.lookup(language, row["key"])
            if not text.strip() or any(unicodedata.category(c) in {"Cs", "Co", "Cn"} or
                    (unicodedata.category(c) == "Cc" and c not in "\t\n\r") for c in text):
                raise BulkError("invalid_translation", "Empty or unsupported Unicode translation value")
            row["value_sha256"] = trace["value_sha256"]
            row["identical_to_english"] = language != "en" and text == english
            if row["identical_to_english"]:
                row["identical_exemption"] = identical_exemption(text, row["key"], approved_unchanged)
        except BulkError as error:
            row["status"] = "missing" if error.code in {"missing_translation", "unavailable_translation"} else "invalid"
            row["reason"], row["message"] = error.code, str(error)
        row["logical_poster_count"], row["language_variant_count"] = len(row["poster_ids"]), len(row["variant_ids"])
        rows.append(row)
    matrix = {}
    for language in registry.select(["all"]):
        keys = [r for r in rows if r["language"] == language]
        counts = Counter(r["status"] for r in keys)
        impact = {state: sorted({i for r in keys if r["status"] == state for i in r["variant_ids"]})
                  for state in ("missing", "invalid")}
        matrix[language] = {"required_unique_keys": len(keys), "valid": counts["valid"],
            "missing": counts["missing"], "invalid_or_empty": counts["invalid"],
            "completion_percent": round(100 * counts["valid"] / len(keys), 4) if keys else 100,
            "identical_to_english_informational": sum(r["identical_to_english"] for r in keys),
            "identical_exemptions": dict(Counter(r["identical_exemption"] for r in keys if r["identical_exemption"])),
            "missing_impacted_variants": len(impact["missing"]), "invalid_impacted_variants": len(impact["invalid"]),
            "missing_or_invalid_impacted_variants": len(set(impact["missing"]) | set(impact["invalid"])),
            "missing_impacted_logical_posters": len({i for r in keys if r["status"] == "missing" for i in r["poster_ids"]}),
            "invalid_impacted_logical_posters": len({i for r in keys if r["status"] == "invalid" for i in r["poster_ids"]})}
    result = {"version": VERSION, "registry_sha256": registry.fingerprint, "matrix": matrix, "keys": rows,
              "scope": "Only active applicable caption keys and resolved dependencies; unrelated resource keys excluded",
              "overlap": "Missing and invalid impacted variants may overlap; union is reported separately",
              "artwork_approval": "none"}
    result["sha256"] = fingerprint(result)
    return result
