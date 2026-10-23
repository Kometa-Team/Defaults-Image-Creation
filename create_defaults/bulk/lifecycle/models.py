"""Strict immutable synthetic operation records; no lifecycle executor or grants."""

from functools import lru_cache
from pathlib import Path
import unicodedata

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from ..common import BulkError, canonical, fingerprint, path_key, relative_path
from ..definitions import StrictValidator
from ..contracts.models import Document, decode_json


def fail(code):
    raise BulkError("p4m1_"+code, "Operation record rejected: "+code)


def key(value):
    return value["kind"], value["id"]


def namespace_key(namespace, path):
    """A collision coordination key, never an item ID or filename rewrite."""
    relative_path(path)
    return dict(kind="namespace", id="synthetic.namespace."+fingerprint(dict(namespace=namespace, path=path_key(path))))


@lru_cache(maxsize=2)
def validator(kind):
    schema = decode_json((Path(__file__).parent/"schemas/operations-v1.schema.json").read_bytes())
    Draft202012Validator.check_schema(schema)
    registry = Registry().with_resource(schema["$id"], Resource.from_contents(schema))
    return StrictValidator({"$ref":schema["$id"]+"#/$defs/"+kind}, registry=registry)


class Value(Document):
    def __init__(self, value):
        try:
            if next(validator(self.KIND).iter_errors(value), None):
                fail("schema")
            encoded = canonical(value)
            value = decode_json(encoded)
        except (TypeError, ValueError, RecursionError) as error:
            if isinstance(error, BulkError):
                raise
            fail("json")
        self._check(value)
        object.__setattr__(self, "encoded", encoded)


class HeadKey(Value):
    KIND = "head-key"


class HeadRef(Value):
    KIND = "head-reference"

    def _check(self, value):
        if (value["revision"] == 0) != (value["sha256"] is None):
            fail("head_revision")
        if value["subjects"] != sorted(set(value["subjects"])):
            fail("head_subjects")
        if value["kind"] == "subject" and value["subjects"] != [value["id"]]:
            fail("head_subjects")


class Operation(Value):
    KIND = "operation-record"

    @property
    def read_set(self):
        return tuple(HeadRef.from_dict(r) for r in self.to_dict()["reads"])

    @property
    def write_set(self):
        return tuple(HeadKey.from_dict(w) for w in self.to_dict()["writes"])

    def _check(self, v):
        if (v["revision"] == 1) != (v["previous_sha256"] is None) or (v["revision"] == 1) != (v["previous_event_sha256"] is None):
            fail("revision")
        if v["content_revision"] > v["revision"]:
            fail("content_revision")
        subjects = [s["id"] for s in v["subjects"]]
        if subjects != sorted(set(subjects)):
            fail("subjects")
        if (v["state"] in {"conflicted", "stale", "cancelled"}) != (v["reason"] is not None):
            fail("reason")
        for s in v["subjects"]:
            if (s["before_sha256"] is None) != (v["operation"] == "ADD") or (s["proposed_sha256"] is None) != (v["operation"] == "DELETE"):
                fail("state_reference")
        reads = v["reads"]
        if [key(r) for r in reads] != sorted({key(r) for r in reads}):
            fail("read_set")
        for r in reads:
            HeadRef.from_dict(r)
            if not set(r["subjects"]) <= set(subjects):
                fail("cross_subject")
        indexed = {key(r):r for r in reads}
        if {i for k,i in indexed if k == "subject"} != set(subjects):
            fail("subject_heads")
        writes = [key(w) for w in v["writes"]]
        if writes != sorted(set(writes)) or not set(writes) <= indexed.keys():
            fail("write_set")
        if not {("subject", s) for s in subjects} <= set(writes):
            fail("subject_heads")
        spaces = []
        for n in v["namespaces"]:
            if unicodedata.normalize("NFC", n["path"]) != n["path"]:
                fail("namespace_path")
            nk = key(namespace_key(n["namespace"], n["path"]))
            if n["subjects"] != sorted(set(n["subjects"])) or nk not in indexed or indexed[nk]["subjects"] != n["subjects"] or nk not in writes:
                fail("namespace_heads")
            spaces.append(nk)
        if spaces != sorted(set(spaces)) or set(spaces) != {k for k in indexed if k[0] == "namespace"}:
            fail("namespace_heads")
        refs = v["references"]
        order = [(r["kind"], r["id"], r["subject"]) for r in refs]
        if order != sorted(set(order)) or any(r["subject"] not in subjects for r in refs):
            fail("references")
        tombstones = [r["subject"] for r in refs if r["kind"] == "tombstone"]
        if (v["operation"] == "DELETE" and sorted(tombstones) != subjects) or (v["operation"] != "DELETE" and tombstones):
            fail("tombstones")


def content(v):
    value = {k:v[k] for k in ("operation", "subjects", "namespaces", "references", "request_sha256")}
    value["read_scope"] = [{k:r[k] for k in ("kind","id","subjects")} for r in v["reads"]]
    value["write_scope"] = v["writes"]
    return value


TRANSITIONS = {
    "draft": {"draft", "structurally_validated", "conflicted", "stale", "cancelled"},
    "structurally_validated": {"draft", "conflicted", "stale", "cancelled"},
    "conflicted": {"draft", "cancelled"}, "stale": {"draft", "cancelled"}, "cancelled": set(),
}


def successor(before, after):
    if before is None:
        if after["revision"] != 1 or after["content_revision"] != 1 or after["state"] != "draft":
            fail("initial_state")
        return
    if after["id"] != before["id"] or after["operation"] != before["operation"] or [s["id"] for s in after["subjects"]] != [s["id"] for s in before["subjects"]]:
        fail("operation_identity")
    if after["revision"] != before["revision"]+1 or after["state"] not in TRANSITIONS[before["state"]]:
        fail("transition")
    changed = content(before) != content(after)
    if after["content_revision"] != before["content_revision"]+int(changed) or changed and after["state"] != "draft" or before["state"] == after["state"] and not changed:
        fail("content_revision")


class Event(Value):
    KIND = "operation-event"

    def _check(self, v):
        if (v["sequence"] == 1) != (v["previous_sha256"] is None):
            fail("journal_sequence")
        if (v["operation_revision"] == 1) != (v["previous_record_sha256"] is None) or (v["operation_revision"] == 1) != (v["previous_operation_event_sha256"] is None) or v["operation_revision"] > v["sequence"]:
            fail("journal_sequence")
        changes = v["changes"]
        if [key(c["key"]) for c in changes] != sorted({key(c["key"]) for c in changes}):
            fail("journal_changes")
        for c in changes:
            if c["subjects"] != sorted(set(c["subjects"])) or c["key"]["kind"] == "subject" and c["subjects"] != [c["key"]["id"]]:
                fail("journal_changes")
            if c["after"]["revision"] != c["before"]["revision"]+1 or c["after"]["sha256"] != v["record_sha256"]:
                fail("journal_changes")
            if (c["before"]["revision"] == 0) != (c["before"]["sha256"] is None):
                fail("journal_changes")
