"""Closed, immutable M2 metadata companions; M1 and prior schemas stay frozen."""

from functools import lru_cache
from pathlib import Path
import re
import unicodedata

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from ..common import BulkError, canonical, fingerprint, path_key, relative_path
from ..config import CATEGORIES
from ..definitions import StrictValidator
from ..contracts.models import Document, decode_json


FLAGS = dict(simulation=True, record_only=True, operation_accepted=False,
    applied=False, contract_approved=False, artwork_approved=False, ready=False,
    active=False, production_enforcement=False, publication_authorized=False)
HEADER = dict(schema_version=1, protocol_version="1.0.0",
    scope="isolated-prospective-planning", **FLAGS)


def fail(code):
    raise BulkError("p4m2_"+code, "Prospective metadata rejected: "+code)


@lru_cache(maxsize=3)
def validator(kind):
    schema = decode_json((Path(__file__).parent/"schemas/identity-impact-v1.schema.json").read_bytes())
    Draft202012Validator.check_schema(schema)
    resources = Registry().with_resource(schema["$id"], Resource.from_contents(schema))
    return StrictValidator({"$ref":schema["$id"]+"#/$defs/"+kind}, registry=resources)


class Value(Document):
    def __init__(self, value):
        encoded = canonical(value)
        value = decode_json(encoded)
        if next(validator(self.KIND).iter_errors(value), None):
            fail("schema")
        self._check(value)
        object.__setattr__(self, "encoded", encoded)


def semantic_key(category, semantic):
    return category, semantic["parent"], semantic["key"], semantic["role"], semantic["language"]


def portable(value, *, new=False):
    relative_path(value)
    if new and unicodedata.normalize("NFC", value) != value:
        fail("non_nfc_name")


def entry_check(e):
    if e["category"] not in CATEGORIES:
        fail("category")
    if e["origin"] == "assigned":
        if not re.fullmatch(re.escape(e["category"].lower())+r"\.[0-9a-f]{32}", e["id"]) or e["historical_sha256"] is not None:
            fail("assigned_identity")
    elif e["historical_sha256"] is None:
        fail("historical_reference")
    container = e["semantic"]["role"] in {"family", "group"}
    if container != (e["variant"] is None) or container != (e["names"]["local_path"] is None):
        fail("member_shape")
    if container and e['names']['public_path'] is not None:fail('container_output_path')
    for name in (e["names"], e["original_names"]):
        for field in ("local_path", "public_path"):
            if name[field] is not None:
                portable(name[field], new=e["origin"] == "assigned")
        if name["source"] is not None:
            portable(name["source"]["path"], new=e["origin"] == "assigned")
    aliases = [(a["namespace"], a["value"]) for a in e["aliases"]]
    if aliases != sorted(set(aliases)):
        fail("aliases")
    for a in e["aliases"]:
        if a["namespace"] != "display":portable(a["value"])


class RegistrySnapshot(Value):
    KIND = "identity-registry"

    def _check(self, v):
        if (v["revision"] == 1) != (v["previous_sha256"] is None):
            fail("registry_revision")
        ids = [e["id"] for e in v["entries"]]
        if ids != sorted(set(ids)):
            fail("identity_collision")
        semantics = []
        for e in v["entries"]:
            entry_check(e);semantics.append(semantic_key(e["category"], e["semantic"]))
        if len(set(semantics)) != len(semantics):fail("semantic_collision")
        tokens = [r["token"] for r in v["requests"]]
        if tokens != sorted(set(tokens)) or any(r["result_id"] not in ids for r in v["requests"]):
            fail("request_index")
        context=decode_json(v["namespace_context_json"].encode())
        if type(context) is not dict or set(context)!={"inventory_sha256","repository","branch","commit","tree","root"} or canonical(context).decode()!=v["namespace_context_json"]:
            fail("namespace_context")


class ImpactEvidence(Value):
    KIND = "prospective-impact"

    def _check(self, v):
        details = decode_json(v["details_json"].encode())
        if canonical(details).decode() != v["details_json"]:
            fail("impact_canonical")
        required = {"comparison", "affected_outputs", "unaffected_outputs", "required_companions",
            "reasons", "read_set", "write_set", "before_mappings", "after_mappings",
            "changed_effective_definitions", "complete", "blockers", "unaffected_sha256"}
        if type(details) is not dict or set(details) != required:
            fail("impact_shape")
        for field in ("affected_outputs", "unaffected_outputs", "required_companions", "blockers"):
            if type(details[field]) is not list or any(type(i) is not str for i in details[field]) or details[field] != sorted(set(details[field])):fail("impact_order")
        if set(details["affected_outputs"]) & set(details["unaffected_outputs"]):fail("impact_overlap")
        if type(details["complete"]) is not bool or details["complete"] != (not details["blockers"]):
            fail("impact_completeness")
        for field in ("read_set","write_set","changed_effective_definitions"):
            rows=details[field]
            if type(rows) is not list or any(type(i) is not str for i in rows) or rows!=sorted(set(rows)):fail("impact_set")
        if type(details["reasons"]) is not dict or set(details["reasons"])!=set(details["affected_outputs"]):fail("impact_reasons")
        for rows in details["reasons"].values():
            if type(rows) is not list or not rows:fail("impact_reasons")
            for row in rows:
                if type(row) is not dict or set(row)!={"cause","path"} or type(row["cause"]) is not str or type(row["path"]) is not list or not row["path"] or any(type(i) is not str for i in row["path"]):fail("impact_reason_shape")
        for field in ("before_mappings","after_mappings"):
            rows=details[field]
            if type(rows) is not dict or not set(rows)<=set(details["affected_outputs"]):fail("impact_mappings")
            for row in rows.values():
                if type(row) is not dict or set(row)!={"local_path","public_path","category","variant"} or row["category"] not in CATEGORIES or type(row["variant"]) is not str:fail("impact_mapping_shape")
                portable(row["local_path"])
                if row["public_path"] is not None:portable(row["public_path"])
        comparison=details["comparison"]
        fields={"previous_sha256","proposed_sha256","changed_identities","direct_outputs","transitive_outputs","affected_outputs","required_companions","evidence_requiring_review","unaffected_outputs","unresolved","impact_complete","publication_authorized","merge_authorized","per_child_resolution"}
        if type(comparison) is not dict or set(comparison)!=fields or comparison["publication_authorized"] is not False or comparison["merge_authorized"] is not False:fail("impact_comparison")
        if (comparison["previous_sha256"],comparison["proposed_sha256"])!=(v["before_sha256"],v["after_sha256"]):fail("impact_graph_binding")
        if not re.fullmatch('[0-9a-f]{64}',str(details["unaffected_sha256"])):fail("impact_unaffected_pin")
