"""Offline translation snapshots, legacy casing/replacements and reviewed fallbacks."""

from dataclasses import dataclass
import json
import re

from .common import BulkError, canonical, fingerprint, load_yaml, reject_links, sha256
from .config import language_id


def legacy_case(value, mode):
    if not isinstance(value, str):
        raise BulkError("invalid_translation", "Caption translation must be a string")
    if mode == "exact":
        return value
    if mode not in {"upper", "lower"}:
        raise BulkError("invalid_translation", "Unknown value-case transform")
    # .NET string casing uses simple mappings, not Python's multi-character expansions.
    output = []
    for char in value:
        if mode == "lower" and char == "\u0130":
            output.append("i")
            continue
        transformed = char.upper() if mode == "upper" else char.lower()
        if len(transformed) != 1:
            title = char.title() if mode == "upper" else char
            transformed = title if len(title) == 1 else char
        output.append(transformed)
    return "".join(output)


def key_token(value):
    return "".join(char if char in {"\u0131", "\u017f"} else legacy_case(char, "upper") for char in value)


def replace_placeholders(text, replacement):
    if len(text) > 16384 or len(replacement) > 16384:
        raise BulkError("oversize_caption", "Placeholder inputs exceed the caption limit")
    def substitute(match):
        tokens = {"$": "$", "&": match.group(), "0": match.group(), "+": match.group(),
                  "`": text[:match.start()], "'": text[match.end():], "_": text}
        result, index = [], 0
        length = 0
        def emit(value):
            nonlocal length
            length += len(value)
            if length > 16384:
                raise BulkError("oversize_caption", "Placeholder expansion exceeds the caption limit")
            result.append(value)
        while index < len(replacement):
            if replacement[index] == "$" and index + 1 < len(replacement):
                token = replacement[index + 1]
                if token.isascii() and token.isdigit():
                    end = index + 2
                    while end < len(replacement) and replacement[end].isascii() and replacement[end].isdigit():
                        end += 1
                    number = replacement[index + 1:end]
                    emit(match.group() if all(char == "0" for char in number) else "$" + number)
                    index = end
                    continue
                if token in tokens and (not token.isdigit() or index + 2 == len(replacement) or not replacement[index + 2].isdigit()):
                    emit(tokens[token])
                    index += 2
                    continue
                if token == "{":
                    end = replacement.find("}", index + 2)
                    if end != -1 and replacement[index + 2:end] and all(char == "0" for char in replacement[index + 2:end]):
                        emit(match.group())
                        index = end + 1
                        continue
            emit(replacement[index])
            index += 1
        return "".join(result)
    output, cursor, length = [], 0, 0
    for match in re.finditer(r"<<.*?>>", text):
        prefix, value = text[cursor:match.start()], substitute(match)
        length += len(prefix) + len(value)
        if length > 16384:
            raise BulkError("oversize_caption", "Placeholder expansion exceeds the caption limit")
        output.extend((prefix, value))
        cursor = match.end()
    output.append(text[cursor:])
    if length + len(output[-1]) > 16384:
        raise BulkError("oversize_caption", "Placeholder expansion exceeds the caption limit")
    return "".join(output)


def _validate_keys(value):
    if isinstance(value, dict):
        if any(not key or len(key) > 256 for key in value):
            raise BulkError("invalid_translation", "Translation keys must be bounded nonempty strings")
        folded = [key_token(key) for key in value]
        if len(folded) != len(set(folded)):
            raise BulkError("ambiguous_translation", "Translation keys collide under case-insensitive lookup")
        for child in value.values():
            _validate_keys(child)
    elif isinstance(value, list):
        for child in value:
            _validate_keys(child)


@dataclass(frozen=True)
class ResolvedCaption:
    text: str
    mode: str
    trace: tuple

    @property
    def fingerprint(self):
        return fingerprint({"text": self.text, "mode": self.mode, "trace": self.trace})


class Translations:
    def __init__(self, sources, *, failures=None, tolerant=False):
        self.sources, self.hashes = {}, {}
        self.failures = dict(failures or {})
        for language, path in sources.items():
            language_id(language)
            try:
                path = reject_links(path)
                if not path.is_file():
                    raise BulkError("unavailable_translation", f"Translation file unavailable: {language}")
                data = load_yaml(path, limit=8_000_000)
                if not isinstance(data, dict):
                    raise BulkError("invalid_translation", "Translation snapshot must be a mapping")
                _validate_keys(data)
            except (BulkError, OSError, UnicodeError) as error:
                if not tolerant:
                    if isinstance(error, UnicodeError):
                        raise BulkError("invalid_translation", "Translation resource is not valid UTF-8") from error
                    raise
                self.failures[language] = ("invalid_translation" if isinstance(error, UnicodeError) else getattr(error, "code", "unavailable_translation"), str(error))
                continue
            self.sources[language], self.hashes[language] = data, sha256(path)

    def pinned_for(self, registry):
        value = object.__new__(Translations)
        value.sources = json.loads(canonical(self.sources))
        value.hashes, value.failures = dict(self.hashes), dict(self.failures)
        for record in registry.data["languages"]:
            if record["availability"] != "available":
                value.failures[record["code"]] = ("unavailable_translation", "Pinned registry has no available defaults resource")
        return value

    def lookup(self, language, key):
        if not isinstance(key, str) or not key or len(key) > 2048 or any(not part for part in key.split(".")):
            raise BulkError("invalid_translation", "Expected a bounded dot-separated translation key")
        if language in self.failures:
            code, message = self.failures[language]
            raise BulkError(code, message)
        if language not in self.sources:
            raise BulkError("unavailable_translation", f"Translation file unavailable: {language}")
        value = self.sources[language]
        for part in key.split("."):
            if not isinstance(value, dict):
                raise BulkError("missing_translation", f"Translation key unavailable: {key}")
            actual = next((name for name in value if key_token(name) == key_token(part)), None)
            if actual is None:
                raise BulkError("missing_translation", f"Translation key unavailable: {key}")
            value = value[actual]
        if not isinstance(value, str) or value == "TRANSLATION NOT FOUND" or len(value) > 16384:
            raise BulkError("invalid_translation", "Invalid caption value or legacy missing-key sentinel")
        return value, {"language": language, "key": key, "source_sha256": self.hashes[language], "value_sha256": fingerprint(value)}

    def resolve(self, caption, language):
        language_id(language)
        mode = caption["mode"]
        if mode not in {"none", "shared", "translation"}:
            raise BulkError("invalid_translation", "Unknown caption mode")
        trace = []
        if mode != "translation":
            text = "" if mode == "none" else caption["text"]
        else:
            try:
                text, evidence = self.lookup(language, caption["key"])
            except BulkError as error:
                if error.code not in {"missing_translation", "unavailable_translation"} or caption["fallback"] is None:
                    raise
                fallback = caption["fallback"]
                if any(not isinstance(fallback.get(key), str) or not fallback[key].strip() for key in ("id", "reviewer", "reason", "policy_version")):
                    raise BulkError("unreviewed_fallback", "Fallback requires review identity and provenance")
                if fallback["text"] is not None and fallback["language"] is None and fallback["key"] is None:
                    text, evidence = fallback["text"], {"literal_sha256": fingerprint(fallback["text"])}
                elif fallback["text"] is None and fallback["language"] is not None and fallback["key"]:
                    text, evidence = self.lookup(fallback["language"], fallback["key"])
                else:
                    raise BulkError("invalid_fallback", "Fallback must select exactly one literal or explicit source key")
                trace.append({"fallback": fallback, "trigger": error.code})
            trace.append(evidence)
            text = legacy_case(text, caption["case"])
            if caption["template_key"]:
                template, evidence = self.lookup(language, caption["template_key"])
                text = replace_placeholders(legacy_case(template, caption["case"]), text)
                trace.append(evidence)
        if mode != "translation":
            text = legacy_case(text, caption["case"])
        text += caption.get("suffix", "")
        if "<<" in text or ">>" in text or "TRANSLATION NOT FOUND" in text or len(text) > 16384:
            raise BulkError("unresolved_caption", "Caption contains unresolved placeholders/sentinel or exceeds its limit")
        return ResolvedCaption(text, mode, tuple(trace))
