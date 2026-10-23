"""Closed P3 value schemas and structural bindings, never operational decisions."""

from datetime import datetime
from functools import lru_cache
from pathlib import Path
import re

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from ...common import BulkError, canonical, fingerprint, path_key, relative_path
from ...config import language_id, repository
from ...definitions import StrictValidator
from ..models import Document, decode_json, _json_value
from ..registry import require_hash


FORMATS = FormatChecker()


def timestamp(value):
    """Parse explicit UTC seconds only; never consult a clock or invent a TTL."""
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ValueError("Expected explicit UTC verification time")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def _path(value):
    relative_path(value)
    if any(part.casefold() == ".git" for part in value.split("/")):
        raise ValueError("Git metadata path")
    return True


def _branch(value):
    if (type(value) is not str or value in {"@", "HEAD"} or value.startswith(("-", "/"))
            or value.endswith(("/", ".")) or any(x in value for x in ("..", "@{", "//"))
            or any(ord(c) <= 32 or ord(c) == 127 or c in "~^:?*[\\" for c in value)
            or any(p.startswith(".") or p.casefold().endswith(".lock") for p in value.split("/"))):
        raise ValueError("Unsafe exact Git branch")
    return True


def _safe(check):
    def valid(value):
        try:
            return bool(check(value))
        except (TypeError, ValueError):
            return False
    return valid


for name, check in {
    "phase3-language": language_id,
    "phase3-path": _path,
    "phase3-branch": _branch,
    "phase3-time": timestamp,
    "phase3-repository": repository,
    "phase3-id": lambda v: re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,199}", v),
    "phase3-version": lambda v: re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", v),
}.items():
    FORMATS.checks(name)(_safe(check))


@lru_cache(maxsize=6)
def validator(kind):
    # Lazy local schema read, never import-time IO or remote $ref retrieval.
    schema = decode_json((Path(__file__).parent/"schemas/foundations-v1.schema.json").read_bytes())
    Draft202012Validator.check_schema(schema)
    resource = Registry().with_resource(schema["$id"], Resource.from_contents(schema))
    selected = {"$ref": schema["$id"]+"#/$defs/"+kind}
    return StrictValidator(selected, registry=resource, format_checker=FORMATS)


def unique(values):
    if len(values) != len(set(values)):
        raise BulkError("phase3_collision", "Duplicate or ambiguous Phase 3 membership")


def paths(values):
    unique([path_key(p) for p in values])


def package(value):
    if (value["category"] == "Overlays") != (value["kind"] == "overlay"):
        raise BulkError("phase3_contract_kind", "Poster/overlay contract reference mismatch")


class Phase3Document(Document):
    """Reuse frozen M1 parsing/value semantics without extending its schemas."""

    def __init__(self, value):
        # Existing parser bounds, duplicate detection, finite JSON and surrogate checks.
        _json_value(value)
        encoded = canonical(value)
        value = decode_json(encoded)
        if next(validator(self.KIND).iter_errors(value), None):
            # Never reflect arbitrary submitted content or credential values in errors.
            raise BulkError("phase3_schema", "Malformed, unknown or unsupported Phase 3 document")
        self._check(value)
        object.__setattr__(self, "encoded", encoded)

    @classmethod
    def from_bytes(cls, encoded):
        try:
            value = decode_json(encoded)
        except BulkError:
            raise BulkError("phase3_json", "Malformed or oversized Phase 3 JSON") from None
        return cls.from_dict(value)


class LanguagePolicy(Phase3Document):
    KIND = "language-policy"

    def _check(self, value):
        codes = [entry["code"] for entry in value["languages"]]
        aliases = [alias for entry in value["languages"] for alias in entry["aliases"]]
        unique(codes+aliases)
        # Case-only competing registrations are ambiguous; no spelling is rewritten.
        unique([c.casefold() for c in codes+aliases])
        unique([(r["package"]["sha256"], r["variant"]) for r in value["coverage"]])
        for row in value["coverage"]:
            package(row["package"])
            if not set(row["languages"]) <= set(codes):
                raise BulkError("phase3_language", "Contract coverage must name exact registered codes")

    def resolve(self, requested):
        language_id(requested)
        entries = self.to_dict()["languages"]
        for entry in entries:
            if entry["code"] == requested:
                return requested
        for entry in entries:
            if requested in entry["aliases"]:
                return entry["code"]
        raise BulkError("phase3_language", "Language or alias is not explicitly registered")


class ValidationSubject(Phase3Document):
    KIND = "validation-subject"

    def _check(self, value):
        package(value["contract"])
        outputs = value["outputs"]
        unique([o["id"] for o in outputs])
        paths([o["local_path"] for o in outputs])
        paths([o["public_path"] for o in outputs if o["public_path"] is not None])
        if value["membership_sha256"] != fingerprint(outputs):
            raise BulkError("phase3_membership", "Output membership differs from its exact hash")


class TranslationSelection(Phase3Document):
    KIND = "translation-selection"

    def _check(self, value):
        source = value["source"]
        paths([r["path"] for r in source["resources"]])
        unique([(v["resource_path"], v["key"]) for v in value["values"]])
        if not {v["resource_path"] for v in value["values"]} <= {r["path"] for r in source["resources"]}:
            raise BulkError("phase3_source", "Value trace names an unselected resource")
        if value["verification"]["source_sha256"] != fingerprint(source):
            raise BulkError("phase3_source", "Source verification claim differs from selected provenance")


class DestinationPolicy(Phase3Document):
    KIND = "destination-policy"

    def _check(self, value):
        mappings = value["mappings"]
        unique([m["language"] for m in mappings])
        official = value["official_repository"]
        identities = {}
        names = {}
        for repo in [official, *(m["repository"] for m in mappings)]:
            key, name = repo["repository_id"], repo["name"].casefold()
            if (key in identities and identities[key] != repo) or (name in names and names[name] != key):
                raise BulkError("phase3_repository", "Inconsistent repository identity claims")
            identities[key] = repo
            names[name] = key
        for mapping in mappings:
            paths(mapping["paths"])
            if mapping["repository"]["repository_id"] == official["repository_id"] and mapping["language"] != "en":
                raise BulkError("phase3_policy", "Official-language policy cannot declare non-English official targets")
        # This validates a policy declaration only. Inventory/eligibility is M3.


class DestinationEvidence(Phase3Document):
    KIND = "destination-evidence"

    def _check(self, value):
        paths(value["target"]["paths"])
        auth = value["authorization"]
        if auth["expires_at"] is not None and timestamp(auth["expires_at"]) <= timestamp(auth["verified_at"]):
            raise BulkError("phase3_authority", "Expiry must follow the claimed verification")
        revocation = auth["revocation"]
        if revocation["status"] != "unknown" and (revocation["checked_at"] is None or revocation["revision_sha256"] is None):
            raise BulkError("phase3_authority", "Claimed revocation observation needs exact context")


class Phase3Attestation(Phase3Document):
    KIND = "phase3-attestation"

    def _check(self, value):
        package(value["contract"])


TYPES = {cls.KIND: cls for cls in (LanguagePolicy, TranslationSelection, DestinationPolicy,
                                  DestinationEvidence, ValidationSubject, Phase3Attestation)}


def reference(document):
    if type(document) not in TYPES.values():
        raise BulkError("phase3_type", "Expected an exact Phase 3 value type")
    return {"kind": document.KIND, "version": document.to_dict()["version"], "sha256": document.sha256}


def read_document(encoded, kind, *, expected_sha256):
    require_hash(expected_sha256)
    if kind not in TYPES:
        raise BulkError("phase3_type", "Unsupported Phase 3 evidence type")
    document = TYPES[kind].from_bytes(encoded)
    if document.sha256 != expected_sha256:
        raise BulkError("phase3_hash", "Evidence differs from its externally selected exact pin")
    return document


def check_bundle_structure(policy, translation, destination_policy, destination, subject, attestation):
    """Reference/membership consistency only; no freshness/eligibility/readiness."""
    documents = [policy, translation, destination_policy, destination, subject, attestation]
    classes = [LanguagePolicy, TranslationSelection, DestinationPolicy, DestinationEvidence,
               ValidationSubject, Phase3Attestation]
    if any(type(doc) is not cls for doc, cls in zip(documents, classes)):
        raise BulkError("phase3_type", "Wrong record type or stage in bundle")
    lp, ts, dp, de, vs, at = [d.to_dict() for d in documents]
    mapping = next((m for m in dp["mappings"] if m["language"] == de["target"]["language"]), None)
    checks = [
        ts["language_policy"] == dp["language_policy"] == at["language_policy"] == reference(policy),
        ts["subject"] == de["subject"] == at["subject"] == reference(subject),
        de["destination_policy"] == at["destination_policy"] == reference(destination_policy),
        at["translation_selection"] == reference(translation), at["destination_evidence"] == reference(destination),
        policy.resolve(ts["requested_language"]) == ts["language"] == vs["language"] == de["target"]["language"] == at["language"],
        at["output_ids"] == [o["id"] for o in vs["outputs"]],
        at["contract"] == vs["contract"],
        at["authority_context_sha256"] == de["authorization"]["verification_context_sha256"],
        at["verification_context_sha256"] == ts["verification"]["context_sha256"],
        mapping is not None and all(de["target"][key] == val for key, val in mapping.items()),
        {m["language"] for m in dp["mappings"]} <= {r["code"] for r in lp["languages"]},
    ]
    checks.extend(at[k] == vs[k] for k in ("membership_sha256", "expanded_definition_sha256", "dependencies_sha256", "review_context_sha256"))
    if not all(checks):
        raise BulkError("phase3_binding", "Mismatched immutable Phase 3 references or membership")
    # Deliberately no translation enumeration, target selection, contract-language
    # eligibility, source reverification, authority grant or M7 transition.
