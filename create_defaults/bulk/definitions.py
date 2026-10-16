"""Production definition loading: explicit profiles, overrides and no evaluation."""

from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator, FormatChecker, validators
from referencing import Registry, Resource

from .common import BulkError, canonical, fingerprint, load_yaml, normalize_hex, path_key, relative_path
from .config import CATEGORIES, LANGUAGES


HERE = Path(__file__).resolve().parent
FORMATS = FormatChecker()
StrictValidator = validators.extend(Draft202012Validator, type_checker=Draft202012Validator.TYPE_CHECKER.redefine("integer", lambda checker, value: type(value) is int))


@FORMATS.checks("artwork-path")
def _safe_path(value):
    try:
        relative_path(value)
        return True
    except BulkError:
        return False


@FORMATS.checks("poster-stem")
def _safe_stem(value):
    # A source name such as A.C.G.T. is a safe stem: the actual destination is
    # A.C.G.T..jpg, not a Windows path ending in a period.
    return isinstance(value, str) and bool(value) and not value.endswith(" ") and all(part not in {".", ".."} for part in value.split("/")) and _safe_path(value + ".jpg")


@lru_cache(maxsize=16)
def schema_validator(name):
    schema = json.loads((HERE / "schemas" / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    registry = Registry().with_resources((item["$id"], Resource.from_contents(item)) for item in
        (json.loads(path.read_text(encoding="utf-8")) for path in (HERE / "schemas").glob("*.json")))
    return StrictValidator(schema, registry=registry, format_checker=FORMATS)


def _check_schema(value, name):
    errors = sorted(schema_validator(name).iter_errors(value), key=lambda error: str(error.path))
    if errors:
        error = errors[0]
        raise BulkError("invalid_schema", f"{'.'.join(map(str, error.path))}: {error.message}")


@lru_cache(maxsize=12000)
def _validated_small_json(encoded, name):
    _check_schema(json.loads(encoded), name)


def validate_schema(value, name):
    # Expanded definitions are immutable JSON and recur during staged/warm
    # planning. Cache successful checks only; at most 12000 * 4096 input bytes.
    try:
        encoded = canonical(value)
    except (TypeError, ValueError):
        return _check_schema(value, name)
    if len(encoded) <= 4096:
        return _validated_small_json(encoded, name)
    return _check_schema(value, name)


@lru_cache(maxsize=1)
def migration_policy():
    return json.loads((HERE / "migration-policy.json").read_text(encoding="utf-8"))


def merge(base, override):
    result = deepcopy(base)
    for key, value in override.items():
        result[key] = merge(result[key], value) if isinstance(result.get(key), dict) and isinstance(value, dict) else deepcopy(value)
    return result


@dataclass(frozen=True)
class Definition:
    id: str
    category: str
    encoded: bytes

    @classmethod
    def create(cls, value):
        validate_schema(value, "definition-v1.json")
        if value["generator"] is not None:
            validate_schema(value["generator"], "generator-v1.json")
        if value["category"] not in CATEGORIES or value["category"] == "Overlays" or any(language not in LANGUAGES for language in value["languages"]):
            raise BulkError("invalid_selector", "Unsupported poster category or language")
        if value["composer"]["text"] != "":
            raise BulkError("invalid_definition", "Caption service owns effective text; composer.text must be explicitly empty")
        if value["caption"]["mode"] == "translation" and not value["caption"]["key"]:
            raise BulkError("invalid_definition", "Translation mode requires a key")
        if value["caption"]["mode"] != "translation" and (value["caption"]["key"] or value["caption"]["template_key"]):
            raise BulkError("invalid_definition", "Shared/none captions cannot use translation keys")
        if value["caption"]["mode"] == "none" and value["caption"]["text"]:
            raise BulkError("invalid_definition", "Captionless poster has caption text")
        source = value["source"]
        if (source["line"] is None or source["row_sha256"] is None) and source.get("kind") != "authored":
            raise BulkError("invalid_definition", "New authored definitions must identify their provenance explicitly")
        if value["caption"]["mode"] != "translation" and value["caption"]["fallback"] is not None:
            raise BulkError("invalid_fallback", "Only translated captions can have fallbacks")
        policy = migration_policy()["splatter"]
        if value["source"]["row_sha256"] == policy["retired"]["row_sha256"]:
            raise BulkError("retired_definition", "D02 retires the green Splatter source row; audit only")
        target = "/".join(filter(None, (value["output"]["directory"], value["output"]["filename"])))
        if path_key(target) == path_key(policy["output"]) and (target != policy["output"] or normalize_hex(value["composer"]["base_color"]) != policy["authoritative"]["hex"] or value["composer"]["white_wash"] is not False):
            raise BulkError("unapproved_splatter", "D02 permits only the unchanged red Splatter output with white-wash disabled")
        if value["layout"]["kind"] == "captured_fit" and value["layout"]["measurement"] is None:
            raise BulkError("missing_measurement", "Captured fitting requires bound measurement evidence")
        return cls(value["id"], value["category"], canonical(value))

    @property
    def data(self):
        return json.loads(self.encoded)

    @property
    def fingerprint(self):
        return fingerprint(self.data)

    def for_language(self, language):
        data = self.data
        matching = [item for item in data["overrides"] if item["language"] == language]
        if len(matching) > 1:
            raise BulkError("invalid_definition", "Ambiguous language overrides")
        if matching:
            data = merge(data, matching[0]["changes"])
            return Definition.create(data)
        return self


def load_definitions(paths, *, profiles_path=None):
    shared = {}
    if profiles_path:
        envelope = load_yaml(profiles_path)
        if not isinstance(envelope, dict) or set(envelope) != {"schema_version", "profiles"} or type(envelope["schema_version"]) is not int or envelope["schema_version"] != 1:
            raise BulkError("invalid_schema", "Invalid shared profile envelope")
        shared = envelope["profiles"]
    if not isinstance(shared, dict):
        raise BulkError("invalid_profile", "Profiles must be a mapping")
    for name, value in shared.items():
        if not re.fullmatch(r"[a-z][a-z0-9-]*", name) or not isinstance(value, dict) or "extends" in value or any(key in value for key in ("id", "source", "category", "display_name")):
            raise BulkError("invalid_profile", "Profiles cannot inherit or assign poster identity")
        # Validate every partial profile, including unused profiles, against all field types.
        schema = json.loads((HERE / "schemas/definition-v1.json").read_text(encoding="utf-8"))
        def partial(node):
            if isinstance(node, dict):
                return {key: partial(item) for key, item in node.items() if key != "required"}
            if isinstance(node, list):
                return [partial(item) for item in node]
            return node
        if not StrictValidator(partial(schema), format_checker=FORMATS).is_valid(value):
            raise BulkError("invalid_profile", "Shared profile has invalid or unknown fields")
    result = {}
    for path in paths:
        document = load_yaml(path)
        if not isinstance(document, dict) or set(document) != {"schema_version", "category", "definitions"} or type(document["schema_version"]) is not int or document["schema_version"] != 1 or not isinstance(document["definitions"], list):
            raise BulkError("invalid_schema", "Expected a versioned per-category definition file")
        for raw in document["definitions"]:
            if not isinstance(raw, dict):
                raise BulkError("invalid_definition", "Definition must be an object")
            parent = raw.get("extends")
            if parent is not None and (not isinstance(parent, str) or parent not in shared):
                raise BulkError("invalid_profile", "Unknown shared profile")
            value = merge(shared.get(parent, {}), {key: item for key, item in raw.items() if key != "extends"})
            definition = Definition.create(value)
            if definition.category != document["category"] or definition.id in result:
                raise BulkError("duplicate_definition", "Category mismatch or duplicate stable ID")
            for override in definition.data["overrides"]:
                definition.for_language(override["language"])
            result[definition.id] = definition
    return tuple(result[key] for key in sorted(result))
