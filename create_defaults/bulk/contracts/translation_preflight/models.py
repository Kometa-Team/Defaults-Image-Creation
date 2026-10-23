"""Closed additive M2 report; frozen M1 documents/schemas remain untouched."""

from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from ...common import canonical, fingerprint
from ...definitions import StrictValidator
from ..models import Document, decode_json
from ..registry import require_hash
from ..language_policy.models import FORMATS
from .adapters import fail


@lru_cache(maxsize=1)
def validator():
    folder = Path(__file__).parent
    schemas = [decode_json(p.read_bytes()) for p in (folder/"evidence-v1.schema.json",
               folder.parent/"language_policy/schemas/foundations-v1.schema.json")]
    for schema in schemas:
        Draft202012Validator.check_schema(schema)
    registry = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas)
    return StrictValidator(schemas[0], registry=registry, format_checker=FORMATS)


class TranslationPreflight(Document):
    KIND = "translation-preflight"

    def __init__(self, value):
        encoded = canonical(value)
        value = decode_json(encoded)  # Existing finite/depth/Unicode/8 MiB limits.
        if next(validator().iter_errors(value), None):
            fail("report_schema")
        self._check(value)
        object.__setattr__(self, "encoded", encoded)

    def _check(self, value):
        subject = value["subject"]
        if subject["language"] != value["language"] or subject["expanded_definition_sha256"] != value["effective_definition_sha256"]:
            fail("report_subject")
        if subject["membership_sha256"] != fingerprint(subject["outputs"]):
            fail("report_membership")
        keys, rows = value["required_keys"], value["results"]
        expected = sorted((code, k["key"], k["roles"]) for k in keys for code in sorted({"en", value["language"]}))
        observed = sorted((r["language"], r["key"], r["roles"]) for r in rows)
        if (expected != observed or len(set(k["key"] for k in keys)) != len(keys)
                or value["required_row_count"] != len(expected) or value["evaluated_row_count"] != len(rows)):
            fail("report_coverage")
        if keys != sorted(keys, key=lambda k: k["key"]) or rows != sorted(rows, key=lambda r: (r["key"], r["language"])):
            fail("report_order")
        if value["blockers"] != sorted(set(value["blockers"])):
            fail("report_diagnostics")
        if value["translation_eligible"] and (not value["technical_eligible"] or value["blockers"] or value["currentness"] not in {"not_applicable", "verified-current"}):
            fail("report_eligibility")
        if value["key_status"] != ("applicable" if keys else "not_applicable"):
            fail("report_applicability")


def read_report(encoded, *, expected_sha256):
    value = TranslationPreflight.from_bytes(encoded)
    if value.sha256 != require_hash(expected_sha256):
        fail("report_pin")
    return value
