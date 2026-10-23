"""Additive closed documents; M1/M2 schemas and record readers stay frozen."""

from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from ...common import canonical, fingerprint
from ...definitions import StrictValidator
from ..models import Document, decode_json
from ..registry import require_hash
from ..language_policy.models import FORMATS
from .paths import fail, target_path


@lru_cache(maxsize=2)
def validator(kind):
    folder = Path(__file__).parent
    schemas = [decode_json(p.read_bytes()) for p in (folder/"evidence-v1.schema.json",
        folder.parent/"language_policy/schemas/foundations-v1.schema.json")]
    for schema in schemas:
        Draft202012Validator.check_schema(schema)
    registry = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas)
    return StrictValidator({"$ref": schemas[0]["$id"]+"#/$defs/"+kind}, registry=registry, format_checker=FORMATS)


class DestinationDocument(Document):
    def __init__(self, value):
        encoded = canonical(value)
        value = decode_json(encoded)
        if next(validator(self.KIND).iter_errors(value), None):
            fail("schema")
        self._check(value)
        object.__setattr__(self, "encoded", encoded)


class DestinationInventory(DestinationDocument):
    KIND = "destination-inventory"

    def _check(self, value):
        from .inventory import validate
        validate(value)


class DestinationAttestation(DestinationDocument):
    KIND = "destination-attestation"

    def _check(self, value):
        rows, records = value["outputs"], value["cohort"]
        outputs = [r["output"] for r in rows]
        if (value["proposed_outputs"] != len(rows) or value["evaluated_outputs"] != len(rows)
                or len({r["id"] for r in outputs}) != len(rows)
                or value["output_membership_sha256"] != fingerprint(outputs)
                or value["cohort_sha256"] != fingerprint(dict(records=records, outputs=outputs))):
            fail("coverage")
        if outputs != sorted(outputs, key=lambda o: o["id"]) or records != sorted(records, key=lambda r: r["subject"]["sha256"]):
            fail("order")
        if {r["language"] for r in records} != {value["language"]}:
            fail("language")
        for row in rows:
            path = row["output"]["public_path"]
            if path is None:
                if row["target_path"] is not None or row["status"] != "private":
                    fail("private_output")
            elif value["target"] is None or row["target_path"] != target_path(value["target"]["root"], path):
                fail("output_mapping")
            if row["diagnostics"] != sorted(set(row["diagnostics"])) or row["status"] != ("private" if path is None else "blocked" if row["diagnostics"] else "clear"):
                fail("output_diagnostics")
        if value["blockers"] != sorted(set(value["blockers"])):
            fail("diagnostics")
        if value["complete"] and (value["missing_companions"] or value["missing_tree_pages"] or "unverified_companion_membership" in value["blockers"] or value["inventory_status"] in {"unavailable", "incomplete"}):
            fail("incomplete")
        if value["complete"] and value["target"] is not None and (value["authority_status"] != "synthetic-only" or value["verified_observation"] is None):
            fail("incomplete_authority")
        if value["destination_checks_passed"] != (not any(not b.startswith("authority:") for b in value["blockers"])):
            fail("destination_checks")
        if value["simulation_eligible"] and (not value["complete"] or not value["destination_checks_passed"]
                or value["authority_status"] != "synthetic-only" or value["verified_observation"] is None):
            fail("simulation")


def read_attestation(encoded, *, expected_sha256):
    report = DestinationAttestation.from_bytes(encoded)
    if report.sha256 != require_hash(expected_sha256):
        fail("attestation_pin")
    return report
