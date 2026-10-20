"""Minimal Package A YAML/schema experiment; no planning or rendering runtime."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import unicodedata

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
import yaml


HERE = Path(__file__).resolve().parent
LANGUAGES = ("ar", "en", "da", "de", "es", "fr", "it", "nb_NO", "nl", "pt-br", "sv")
FORMATS = FormatChecker()


@FORMATS.checks("relative-artwork-path")
def safe_path(value):
    if not isinstance(value, str):
        return False
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
    return bool(value) and not any(ord(char) < 32 or ord(char) == 127 or char in '\\:<>"|?*' for char in value) and all(
        part not in {"", ".", ".."} and not part.endswith((" ", ".")) and part.split(".")[0].casefold() not in reserved
        for part in value.split("/"))


class DefinitionError(ValueError):
    pass


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise DefinitionError("YAML mapping keys must be unique strings")
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def read_yaml(path):
    path = Path(path)
    if path.stat().st_size > 2_000_000:
        raise DefinitionError("Split large YAML into category files (prototype limit: 2 MB)")
    text = path.read_text(encoding="utf-8-sig")
    try:
        # Profiles provide deliberate inheritance; implicit YAML aliases/merges do not.
        if any(isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken)) for token in yaml.scan(text)):
            raise DefinitionError("Use explicit profiles instead of YAML anchors or aliases")
        return yaml.load(text, Loader=UniqueLoader)
    except yaml.YAMLError as error:
        raise DefinitionError("Invalid YAML") from error


def merge(base, override):
    result = deepcopy(base)
    for key, value in override.items():
        result[key] = merge(result[key], value) if isinstance(result.get(key), dict) and isinstance(value, dict) else deepcopy(value)
    return result


def schema_check(value, filename):
    schema = json.loads((HERE / "schemas" / filename).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema, format_checker=FORMATS).iter_errors(value), key=lambda item: str(item.path))
    if errors:
        error = errors[0]
        raise DefinitionError(f"{'.'.join(map(str, error.path)) or 'document'}: {error.message}")


def validate_document(document):
    schema_check(document, "document-v1.schema.json")
    profiles = document["profiles"]
    # Profiles are one-level, by design. Even unused profiles must not hide a cycle.
    for name, profile in profiles.items():
        if "extends" in profile:
            raise DefinitionError(f"Profile {name}: profile inheritance/chains are not supported")
        schema = json.loads((HERE / "schemas/definition-v1.schema.json").read_text(encoding="utf-8"))
        def partial(node):
            if isinstance(node, dict):
                return {key: partial(value) for key, value in node.items() if key != "required"}
            if isinstance(node, list):
                return [partial(value) for value in node]
            return node
        try:
            Draft202012Validator(partial(schema), format_checker=FORMATS).validate(profile)
        except ValidationError as error:
            raise DefinitionError(f"Invalid profile {name}: {error.message}") from error
    effective, identities, destinations = [], set(), {}
    for definition in document["definitions"]:
        parent = definition.get("extends")
        if parent is not None and parent not in profiles:
            raise DefinitionError(f"Unknown profile: {parent}")
        item = merge(profiles.get(parent, {}), {key: value for key, value in definition.items() if key != "extends"})
        schema_check(item, "definition-v1.schema.json")
        if item["id"] in identities:
            raise DefinitionError(f"Duplicate logical ID: {item['id']}")
        identities.add(item["id"])
        caption, typography, background = item["caption"], item["typography"], item["background"]
        if caption["mode"] == "translation" and not caption["key"]:
            raise DefinitionError("Translated captions require a key")
        if caption["mode"] != "translation" and (caption["key"] is not None or caption["template_key"] is not None):
            raise DefinitionError("Only translated captions can have translation keys")
        if caption["mode"] == "none" and caption["text"]:
            raise DefinitionError("No-caption definition cannot contain caption text")
        if caption["mode"] == "translation" and caption["fallback"] == "error" and caption["text"]:
            raise DefinitionError("Error fallback cannot contain fallback text")
        if caption["fallback"] == "literal" and not caption["text"]:
            raise DefinitionError("Literal fallback requires explicit text")
        if typography["mode"] == "fixed" and typography["point_size"] is None:
            raise DefinitionError("Fixed typography requires point_size")
        if typography["mode"] == "fit" and typography["point_size"] is not None:
            raise DefinitionError("Fit typography must not hide a fixed point_size")
        if typography["minimum"] > typography["maximum"]:
            raise DefinitionError("Typography minimum exceeds maximum")
        if (background["mode"] == "explicit") != (background["hex"] is not None):
            raise DefinitionError("Only explicit backgrounds require HEX")
        for language in item["languages"]:
            output = f"{item['output']['directory']}/{item['output']['filename']}"
            key = (language, unicodedata.normalize("NFC", output).casefold())
            if key in destinations:
                raise DefinitionError(f"Output collision: {destinations[key]} and {item['id']} -> {language}/{output}")
            destinations[key] = item["id"]
        effective.append(item)
    for item in effective:
        if item["dependencies"]:
            raise DefinitionError("Generated dependency expansion is designed, not implemented in Package A")
        if item["variants"] or item["overrides"]:
            raise DefinitionError("Dynamic variants/overrides are reserved for Package B/C, not implemented in this prototype")
    return effective


def validate_file(path):
    return validate_document(read_yaml(path))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("definition", type=Path)
    args = parser.parse_args(argv)
    try:
        result = validate_file(args.definition)
    except (DefinitionError, OSError) as error:
        parser.exit(2, f"Definition validation failed: {error}\n")
    print(f"Validated {len(result)} real example definitions (schema v1); no images generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
