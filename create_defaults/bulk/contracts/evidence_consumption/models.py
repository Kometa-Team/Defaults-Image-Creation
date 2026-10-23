"""Additive canonical companions; frozen record schemas/readers stay unchanged."""

from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from ...common import BulkError, canonical, fingerprint
from ...definitions import StrictValidator
from ..models import Document, decode_json
from ..language_policy.models import FORMATS
from ..registry import require_hash


def fail(code):
    raise BulkError("p3m4_"+code, "Evidence consumption rejected: "+code)


@lru_cache(maxsize=2)
def validator(kind):
    schema = decode_json(Path(__file__).with_name("evidence-v1.schema.json").read_bytes())
    Draft202012Validator.check_schema(schema)
    registry = Registry().with_resource(schema["$id"], Resource.from_contents(schema))
    return StrictValidator({"$ref": schema["$id"]+"#/$defs/"+kind}, registry=registry, format_checker=FORMATS)


class Companion(Document):
    def __init__(self, value):
        encoded = canonical(value)
        value = decode_json(encoded)
        if next(validator(self.KIND).iter_errors(value), None):
            fail("schema")
        self._check(value)
        object.__setattr__(self, "encoded", encoded)


class RequestContext(Companion):
    """Selected immutable request revision, not a request/approval state machine."""

    KIND = "evidence-request-context"

    def _check(self, value):
        if (value["revision"] == 1) != (value["previous_sha256"] is None):
            fail("request_revision")
        subjects = value["subjects"]
        if subjects != sorted(set(subjects)) or not subjects:
            fail("request_subjects")
        refs = value["references"]
        keys = [(r["role"], r["id"], canonical(r["revision"])) for r in refs]
        if keys != sorted(set(keys)) or any(r["subject_sha256"] not in subjects for r in refs):
            fail("request_references")


class ConsumptionAttestation(Companion):
    KIND = "evidence-consumption"

    def _check(self, value):
        material = {k: v for k, v in value.items() if k not in {"binding_sha256", "graph_snapshot_sha256"}}
        if value["binding_sha256"] != fingerprint(material):
            fail("binding_hash")
        if value["blockers"] != sorted(set(value["blockers"])):
            fail("blockers")
        subjects = value["subjects"]
        if [s["subject_sha256"] for s in subjects] != sorted({s["subject_sha256"] for s in subjects}):
            fail("subject_order")
        outputs = [o for s in subjects for o in s["outputs"]]
        if len({o["id"] for o in outputs}) != len(outputs) or value["output_membership_sha256"] != fingerprint(sorted(outputs, key=lambda o: o["id"])):
            fail("membership")
        if value["chain_compatible"] and (not value["destination_sha256"] or any(not s["translation_sha256"] for s in subjects)):
            fail("incomplete_chain")
        if value["simulation_eligible"] and (not value["chain_compatible"] or not value["simulation"]):
            fail("simulation")
        if not value["m7"]["blockers"] or value["technical_eligible"]:
            fail("m7_gate")


def read_attestation(raw, *, expected_sha256):
    result = ConsumptionAttestation.from_bytes(raw)
    if result.sha256 != require_hash(expected_sha256):
        fail("attestation_pin")
    return result
