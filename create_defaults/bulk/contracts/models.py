"""Strict, immutable JSON value interfaces; no rendering or approval workflow."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
from typing import ClassVar, Self
import unicodedata

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from ..common import BulkError, canonical, path_key, relative_path
from ..definitions import StrictValidator


SCHEMAS = Path(__file__).with_name("schemas")
# Parser safety bounds, not visual/metric acceptance thresholds.
MAX_BYTES = 8 * 1024 * 1024
MAX_DEPTH = 40
FORMATS = FormatChecker()


@FORMATS.checks("lifecycle-path")
def _path(value):
    try:
        relative_path(value)
        return not any(0xD800 <= ord(c) <= 0xDFFF for c in value)
    except BulkError:
        return False


def _json_value(value, depth=0):
    if depth > MAX_DEPTH:
        raise BulkError("invalid_contract_json", "JSON nesting exceeds the contract parser limit")
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                raise BulkError("invalid_contract_json", "JSON object keys must be strings")
            _json_value(key, depth + 1)
            _json_value(child, depth + 1)
    elif type(value) is list:
        for child in value:
            _json_value(child, depth + 1)
    elif type(value) is str:
        if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise BulkError("invalid_contract_json", "Unpaired Unicode surrogate")
    elif value is None or type(value) in (bool, int):
        pass
    elif type(value) is float and math.isfinite(value):
        pass
    else:
        raise BulkError("invalid_contract_json", "Expected finite JSON values only")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BulkError("invalid_contract_json", f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def decode_json(encoded: bytes):
    if type(encoded) is not bytes or len(encoded) > MAX_BYTES:
        raise BulkError("invalid_contract_json", "Expected bounded UTF-8 JSON bytes")
    try:
        value = json.loads(encoded.decode("utf-8"), object_pairs_hook=_pairs)
        _json_value(value)
        return value
    except (UnicodeError, ValueError, RecursionError) as error:
        if isinstance(error, BulkError):
            raise
        raise BulkError("invalid_contract_json", "Malformed UTF-8 JSON") from error


def read_json_bytes(path: Path) -> bytes:
    """Bound disk reads before allocating/parsing an untrusted evidence file."""
    with path.open("rb") as stream:
        encoded = stream.read(MAX_BYTES + 1)
    if len(encoded) > MAX_BYTES:
        raise BulkError("invalid_contract_json", "Contract evidence exceeds parser limit")
    return encoded


@lru_cache(maxsize=4)
def _validator(name):
    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(SCHEMAS.glob("*.json"))]
    for schema in schemas:
        Draft202012Validator.check_schema(schema)
    resources = Registry().with_resources((schema["$id"], Resource.from_contents(schema)) for schema in schemas)
    # The registry contains only bundled schemas; no remote retrieval callback.
    schema = next(s for s in schemas if s["$id"].endswith("/" + name + "-v1.schema.json"))
    return StrictValidator(schema, registry=resources, format_checker=FORMATS)


def _unique(values, label):
    if len(values) != len(set(values)):
        raise BulkError("contract_collision", f"Duplicate {label}")


@dataclass(frozen=True, init=False)
class Document:
    """Canonical bytes are the value; exposed dictionaries are detached copies.

    Construct only through from_dict/from_bytes. Hashes are Package E canonical
    hashes (including literal Unicode spelling), not hashes of pretty JSON files.
    """

    encoded: bytes
    SCHEMA: ClassVar[str]
    KIND: ClassVar[str | None] = None

    def __init__(self, value):
        _json_value(value)
        encoded = canonical(value)
        if len(encoded) > MAX_BYTES:
            raise BulkError("invalid_contract_json", "Contract document exceeds parser limit")
        error = next(_validator(self.SCHEMA).iter_errors(value), None)
        if error:
            raise BulkError("invalid_contract_schema", f"{list(error.path)}: {error.message}")
        if self.KIND is not None and value.get("kind") != self.KIND:
            raise BulkError("wrong_record_kind", "Record cannot be used as a different evidence type")
        self._check(value)
        object.__setattr__(self, "encoded", encoded)

    @classmethod
    def from_dict(cls, value) -> Self:
        return cls(value)

    @classmethod
    def from_bytes(cls, encoded: bytes) -> Self:
        return cls(decode_json(encoded))

    def _check(self, value):
        pass

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.encoded).hexdigest()

    def to_dict(self) -> dict:
        return json.loads(self.encoded)


class Contract(Document):
    SCHEMA = "contract"

    def _check(self, value):
        if value["provenance"]["role"] != "maintainer" or value["provenance"]["actor"] != value["owner"]:
            raise BulkError("contract_ownership", "Package provenance must identify its maintainer owner")
        _unique([variant["id"] for variant in value["variants"]], "variant IDs")
        for variant in value["variants"]:
            design = variant["design"]
            if value["kind"] == "overlay":
                continue
            fitting, font = design["fitting"], design["typography"]
            if fitting is not None and (font is None or not fitting["minimum_size"] <= font["size"] <= fitting["maximum_size"]):
                raise BulkError("contract_fitting", "Captured font size must remain within its recorded bounds")
            caption = design["caption"]
            _unique([item["id"] for item in caption["content_types"]], "caption type IDs")
            if caption["requirement"] == "prohibited" and any(item["mode"] != "none" for item in caption["content_types"]):
                raise BulkError("contract_caption", "Prohibited captions cannot expose text types")
            if caption["requirement"] == "required" and (font is None or any(item["mode"] == "none" for item in caption["content_types"])):
                raise BulkError("contract_caption", "Required captions need typography and text-bearing types")
            if "background_proposal" in variant["contributor_fields"] and not design["background"]["proposals_allowed"]:
                raise BulkError("contract_permission", "Background proposals require explicit contract permission")

    def validate_content(self, variant_id: str, content: dict) -> dict:
        """Validate permitted intent only; never merge it into the locked design.

        Selection is from the closed package. Returned fields are requests, not
        authorized paths, identities, background assignments or logo exceptions.
        """
        _json_value(content)
        variant = next((v for v in self.to_dict()["variants"] if v["id"] == variant_id), None)
        if variant is None:
            raise BulkError("unknown_contract_variant", "Unknown closed contract variant")
        if type(content) is not dict or set(content) - set(variant["contributor_fields"]):
            raise BulkError("forbidden_contract_field", "Contributor content contains a non-permitted field")
        schema = _validator("contract").schema
        definitions = schema["$defs"]
        fields = {
            "display_name": {"type": "string", "minLength": 1, "maxLength": 2048},
            "description": {"type": "string", "maxLength": 4096},
            "source": definitions["asset"], "separate_white_source": definitions["asset"],
            "filename_proposal": definitions["path"],
            "background_proposal": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$", "minLength": 7, "maxLength": 7},
        }
        if "content_type" in content:
            fields["content_type"] = {"enum": [t["id"] for t in variant["design"]["caption"]["content_types"]]}
        validator = StrictValidator({"type": "object", "properties": fields, "additionalProperties": False}, format_checker=FORMATS)
        if next(validator.iter_errors(content), None):
            raise BulkError("invalid_contract_content", "Malformed contributor content or nested style override")
        for field in ("source", "separate_white_source", "filename_proposal"):
            if field in content:
                path = content[field] if field == "filename_proposal" else content[field]["path"]
                if unicodedata.normalize("NFC", path) != path:
                    raise BulkError("non_nfc_name", "New source/filename proposals must already be NFC")
        return json.loads(canonical(content))


class RegistryDocument(Document):
    SCHEMA = "registry"
    KIND = "category-contract-registry"

    def _check(self, value):
        if value["provenance"]["role"] != "maintainer" or value["provenance"]["actor"] != value["owner"]:
            raise BulkError("contract_ownership", "Registry must identify its maintainer owner")
        _unique([(entry["package"]["category"], entry["package"]["kind"], entry["package"]["version"]) for entry in value["entries"]], "registry package versions")
        for entry in value["entries"]:
            _unique(entry["variants"], "registry variants")
            package = entry["package"]
            if (package["category"] == "Overlays") != (package["kind"] == "overlay"):
                raise BulkError("invalid_contract_registry", "Poster/overlay category and kind must agree")


class Identity(Document):
    SCHEMA = "identity"
    KIND = "item-identity"

    def require_new_names(self) -> None:
        """Explicit new-intake validation; historical loading preserves literals.

        No historical/new flag can be supplied through contributor content.
        Assignment, adoption and rename operations are outside M1.
        """
        value = self.to_dict()
        paths = [value["source"]["path"], value["local_path"], value["public_path"]]
        if any(path is not None and unicodedata.normalize("NFC", path) != path for path in paths):
            raise BulkError("non_nfc_name", "New mappings must already be NFC")


def check_namespace(identities: list[Identity]) -> None:
    """Read-only full-namespace check; shared source paths are legitimate."""
    values = [item.to_dict() for item in identities]
    _unique([v["id"] for v in values], "stable identities")
    for field in ("local_path", "public_path"):
        _unique([path_key(v[field]) for v in values if v[field] is not None], field)
    _unique([(v["semantic_member"]["family_id"], v["semantic_member"]["key"]) for v in values if v["semantic_member"] is not None], "semantic members")


class Record(Document):
    SCHEMA = "record"


class ContractApproval(Record):
    KIND = "contract-approval"


class AdoptionRecord(Record):
    KIND = "contract-adoption"


class ExceptionRequest(Record):
    KIND = "logo-exception-request"


class PreviewManifest(Record):
    KIND = "logo-preview-manifest"


class SubmitterConfirmation(Record):
    KIND = "submitter-confirmation"


class ExceptionDecision(Record):
    KIND = "maintainer-exception-decision"


class ValidationAttestation(Record):
    KIND = "effective-job-attestation"


RECORD_TYPES = {cls.KIND: cls for cls in (ContractApproval, AdoptionRecord, ExceptionRequest, PreviewManifest, SubmitterConfirmation, ExceptionDecision, ValidationAttestation)}


def read_document(encoded: bytes, document_type: str) -> Document:
    if document_type == "record":
        value = decode_json(encoded)
        cls = RECORD_TYPES.get(value.get("kind")) if type(value) is dict else None
        if cls is None:
            raise BulkError("wrong_record_kind", "Unknown lifecycle evidence type; publication receipts are separate")
        return cls.from_dict(value)
    cls = {"contract": Contract, "registry": RegistryDocument, "identity": Identity}.get(document_type)
    if cls is None:
        raise BulkError("invalid_document_type", "Unknown contract document type")
    return cls.from_bytes(encoded)
