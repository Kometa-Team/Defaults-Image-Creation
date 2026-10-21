"""Additive historical-fact types using the unchanged M1 immutable value API.

M1's ContractApproval/AdoptionRecord concern approved category packages. M2 must
not fabricate those before M3/M6. These types record facts and leave category
compatibility explicitly unassessed; they cannot enter the publication gates.
"""

import json
from functools import lru_cache
from pathlib import Path

from ...common import BulkError, canonical, fingerprint, path_key
from ...definitions import Definition, schema_validator
from ...planner import _composer_validator, effective_parameters
from ..models import Document, Identity, RegistryDocument, decode_json
from ..registry import require_hash


class AdoptionError(BulkError):
    def __init__(self, code, *, category, identity, path, expected, observed):
        self.details = json.loads(json.dumps({"category": category, "record": identity, "path": path,
                        "expected": expected, "observed": observed}, default=lambda value: sorted(value) if isinstance(value, set) else str(value)))
        super().__init__(code, canonical(self.details).decode())


def mismatch(code, category, identity, path, expected, observed):
    raise AdoptionError(code, category=category, identity=identity, path=path,
                        expected=expected, observed=observed)


def equal(expected, observed, *, category, identity, path, code="adoption_mismatch"):
    if expected != observed:
        mismatch(code, category, identity, path, expected, observed)


def encoded_json(value):
    return canonical(value).decode("utf-8")


def read_canonical(value):
    result = decode_json(value.encode("utf-8"))
    if encoded_json(result) != value:
        raise BulkError("adoption_canonical", "Embedded evidence must use M1 canonical JSON")
    return result


def fingerprints(definition, job, exceptions):
    parameters = job["parameters"]
    style = {key: value for key, value in parameters.items()
             if key not in {"text", "out_name", "logo", "input"}}
    values = {
        "effective_definition": definition,
        "sources": sorted(job["inputs"], key=lambda row: (row["role"], row["path"])),
        "font": [row for row in job["inputs"] if row["role"] == "font"],
        "caption": {"language": job["language"], "translation": job["translation"],
                    "text": parameters.get("text"), "language_behavior": job["language_behavior"]},
        "style": {"parameters": style, "layout": job["layout_evidence"], "color": job["color_assignment"]},
        "membership": {key: job[key] for key in ("id", "poster_id", "kind", "variant", "local_relative", "remote_relative")},
        "dependencies": sorted(job["dependencies"], key=lambda row: row["job_id"]),
        "transformation": {"kind": job["kind"], "parameters": parameters},
        "exceptions": exceptions,
        "material_context": {key: job[key] for key in ("kind", "parameters", "inputs", "dependencies", "language_behavior", "layout_evidence", "translation")},
    }
    return {name: fingerprint(value) for name, value in values.items()}


@lru_cache(maxsize=1)
def _job_validator():
    parent = schema_validator("manifest-v1.json")
    schema = parent.schema
    return parent.evolve(schema={"$id": schema["$id"], "$defs": schema["$defs"], **schema["properties"]["jobs"]["items"]})


class HistoricalOutput(Document):
    SCHEMA = "historical-output"
    KIND = "historical-output-adoption"

    def _check(self, value):
        identity = Identity.from_dict(value["identity"]).to_dict()
        job = read_canonical(value["job_json"])
        definition = read_canonical(value["effective_definition_json"])
        category, record = identity["category"], identity["id"]
        if not _job_validator().is_valid(job):
            mismatch("adoption_job_schema", category, record, "job_json", "existing strict Package E job schema", "invalid job")
        if job["kind"] == "poster":
            Definition.create(definition)
            equal(identity["id"], definition["id"], category=category, identity=record, path="definition.id")
            equal(category, definition["category"], category=category, identity=record, path="definition.category")
            if not _composer_validator().is_valid(job["raw_parameters"]):
                mismatch("adoption_job_schema", category, record, "raw_parameters", "strict composer schema", "invalid composer")
            equal(effective_parameters(job["raw_parameters"]), job["parameters"], category=category, identity=record, path="effective_parameters")
        else:
            equal(job["id"], identity["id"], category=category, identity=record, path="overlay.identity")
            equal({"group", "parameters", "transform"}, set(definition), category=category, identity=record, path="overlay.definition")
            equal(job["parameters"], definition["parameters"], category=category, identity=record, path="overlay.parameters")
        for path, expected, observed in [
            ("job_id", value["job_id"], job["id"]),
            ("local_path", identity["local_path"], job["local_relative"]),
            ("public_path", identity["public_path"], job["remote_relative"]),
            ("observed_variant", value["observed_variant"], job["variant"]),
            ("fingerprints", value["fingerprints"], fingerprints(definition, job, value["historical_exceptions"])),
        ]:
            equal(expected, observed, category=category, identity=record, path=path)
        if (category == "Overlays") != (job["kind"] == "overlay"):
            mismatch("adoption_kind", category, record, "kind", category, job["kind"])
        if value["source_kind"] == "generated_parent" and not job["dependencies"]:
            mismatch("adoption_dependency", category, record, "dependencies", "generated parent", [])
        if job["kind"] == "overlay" and ("white_wash" in job["parameters"] or job["parameters"]["box"] not in ([285, 85], [440, 100])):
            mismatch("adoption_overlay", category, record, "parameters", "source-preserving standard/bigger", job["parameters"])
        if value["source_kind"] != "generated_parent":
            matches = [i for i in job["inputs"] if i["path"] == identity["source"]["path"]]
            if not matches or any(i["sha256"] != identity["source"]["sha256"] for i in matches):
                mismatch("adoption_source_mapping", category, record, identity["source"]["path"], identity["source"]["sha256"], matches)
        equal(bool(value["evidence"]["approval_refs"]), value["maintainer_approval"] == "historical_record_found",
              category=category, identity=record, path="historical_approval_evidence")


class HistoricalRegistry(Document):
    SCHEMA = "historical-registry"
    KIND = "historical-adoption-registry"

    def _check(self, value):
        basis = RegistryDocument.from_dict(read_canonical(value["basis_registry_json"]))
        equal(value["basis_registry_sha256"], basis.sha256, category="registry", identity=value["id"], path="basis_registry_sha256")
        if basis.to_dict()["entries"]:
            mismatch("adoption_contract_scope", "registry", value["id"], "entries", "no M3/M6 contracts", basis.to_dict()["entries"])
        for field in ("id", "job_id"):
            seen = set()
            for member in value["members"]:
                if member[field] in seen:
                    mismatch("adoption_duplicate", "registry", member["id"], field, "unique", member[field])
                seen.add(member[field])
        read_canonical(value["audit_json"])

    def verify_schema_pins(self):
        root = Path(__file__).parents[1] / "schemas"
        for pin in self.to_dict()["schema_pins"]:
            if Path(pin["path"]).name != pin["path"]:
                raise BulkError("adoption_schema_pin", "Only bundled schema basenames are permitted")
            path = root / pin["path"]
            actual = fingerprint(json.loads(path.read_bytes())) if path.is_file() else None
            equal(pin["sha256"], actual, category="registry", identity=self.sha256, path=pin["path"], code="adoption_schema_pin")
        expected = {p.name for p in root.glob("*.schema.json")}
        equal(expected, {p["path"] for p in self.to_dict()["schema_pins"]}, category="registry", identity=self.sha256, path="schema_pins", code="adoption_schema_pin")


def audit_membership(records, expected_members=None):
    values = [r.to_dict() for r in records]
    ids, jobs, local, public, semantic = {}, {}, {}, {}, {}
    by_id = {v["identity"]["id"]: v for v in values}
    by_job = {v["job_id"]: v for v in values}
    for value in values:
        item = value["identity"]
        category, identity = item["category"], item["id"]
        for field, actual, table in (("stable_id", identity, ids), ("job_id", value["job_id"], jobs),
                                    ("local_path", item["local_path"], local), ("public_path", item["public_path"], public)):
            if actual is None:
                continue
            key = path_key(actual) if field.endswith("path") else actual
            if key in table:
                mismatch("adoption_collision", category, identity, actual, "unique " + field, table[key])
            table[key] = identity
        family = value["family"]
        if family:
            key = (family["id"], family["member_key"])
            if key in semantic:
                mismatch("adoption_collision", category, identity, "semantic_member", "unique", semantic[key])
            semantic[key] = identity
    for value in values:
        identity = value["identity"]
        pair = value["paired_identity"]
        if pair is not None and (pair not in ids or pair == identity["id"]):
            mismatch("adoption_pair", identity["category"], identity["id"], "paired_identity", "existing partner", pair)
        if pair is not None:
            partner = by_id[pair]
            equal(identity["id"], partner["paired_identity"], category=identity["category"], identity=identity["id"], path="paired_identity")
            equal(identity["category"], partner["identity"]["category"], category=identity["category"], identity=identity["id"], path="pair.category")
        job = read_canonical(value["job_json"])
        for dependency in job["dependencies"]:
            if dependency["job_id"] not in jobs:
                mismatch("adoption_dependency", identity["category"], identity["id"], "dependencies", "existing parent job", dependency["job_id"])
            parent = by_job[dependency["job_id"]]
            equal(parent["evidence"]["output_sha256"], dependency["sha256"], category=identity["category"], identity=identity["id"], path="dependency.sha256")
            if value["source_kind"] == "generated_parent" and value["source_identity"] == parent["identity"]["id"]:
                equal(parent["identity"]["local_path"], identity["source"]["path"], category=identity["category"], identity=identity["id"], path="generated.source_path")
                equal(parent["evidence"]["output_sha256"], identity["source"]["sha256"], category=identity["category"], identity=identity["id"], path="generated.source_sha256")
    observed = {value["identity"]["id"]: fingerprint(value) for value in values}
    if expected_members is not None:
        for identity in sorted(set(observed) | set(expected_members)):
            equal(expected_members.get(identity), observed.get(identity), category="membership", identity=identity,
                  path="frozen_adoption_mapping", code="adoption_membership")
    return observed
