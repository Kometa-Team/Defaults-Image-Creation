"""Explicit immutable snapshot bytes, scoped integrity and unavailable freshness."""

from dataclasses import dataclass
import hashlib
from typing import Protocol

import yaml

from ...common import BulkError, SafeLoader, canonical, fingerprint
from ...translations import key_token, _validate_keys
from ..language_policy import TranslationSelection, SourceVerificationContext, reference
from .adapters import fail


def blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def parse(raw):
    """Same bounded, duplicate/alias/case-safe YAML semantics, without file IO."""
    if type(raw) is not bytes or len(raw) > 8_000_000:
        raise BulkError("invalid_source", "Resource absent or oversized")
    try:
        text = raw.decode("utf-8-sig")
        depth = 0
        for event in yaml.parse(text):
            if isinstance(event, yaml.events.AliasEvent) or getattr(event, "anchor", None):
                raise ValueError("aliases")
            if isinstance(event, (yaml.events.MappingStartEvent, yaml.events.SequenceStartEvent)):
                depth += 1
            if depth > 40:
                raise ValueError("depth")
            if isinstance(event, (yaml.events.MappingEndEvent, yaml.events.SequenceEndEvent)):
                depth -= 1
        data = yaml.load(text, Loader=SafeLoader)
        if type(data) is not dict:
            raise ValueError("mapping")
        canonical(data)
        _validate_keys(data)
        return data
    except (UnicodeError, yaml.YAMLError, ValueError, TypeError, RecursionError):
        raise BulkError("invalid_source", "Invalid UTF-8 or YAML structure") from None


def lookup(data, key):
    actual = []
    if type(key) is not str or not key or len(key) > 2048 or any(not p for p in key.split(".")):
        fail("key")
    for part in key.split("."):
        if type(data) is not dict:
            return False, None, None
        name = next((k for k in data if key_token(k) == key_token(part)), None)
        if name is None:
            return False, None, None
        actual.append(name)
        data = data[name]
    return True, data, ".".join(actual)


@dataclass(frozen=True)
class SnapshotInput:
    """Explicit selected Package E snapshot plus immutable detached raw resources.

    No path loading, cache lookup, network refresh or authentication occurs here.
    Repository numeric identity is separately supplied by the controlled caller;
    it must agree with the selected M1 evidence and Git snapshot name.
    """

    snapshot: object
    repository_json: bytes
    resources: tuple[tuple[str, bytes | None], ...]

    def selected(self, languages):
        from ...languages import LanguageSnapshot
        from ..models import decode_json
        if type(self.snapshot) is not LanguageSnapshot:
            fail("snapshot_type")
        data = self.snapshot.data
        rebuilt = LanguageSnapshot.create(data["languages"], provenance=data["provenance"], aliases=data["aliases"])
        if rebuilt.encoded != self.snapshot.encoded:
            fail("snapshot_integrity")
        repo = decode_json(self.repository_json)
        provenance = data["provenance"]
        if provenance["kind"] != "verified-git-blobs" or provenance["repository"] != repo["name"]:
            fail("snapshot_provenance")
        if len({p for p, _ in self.resources}) != len(self.resources):
            fail("resource_collision")
        records = {code: self.snapshot.record(code) for code in sorted(set(languages))}
        records = {code: r for code, r in records.items() if r is not None and "defaults" in r["components"]}
        # A scoped snapshot is an explicit projection, not a substituted global
        # snapshot receipt. Unused languages/resources cannot enter dependencies.
        projection = {"repository": repo, "languages": [records[k] for k in sorted(records)]}
        source = dict(repository=repo, commit=provenance["commit"], tree=provenance["tree"], resources=[
            dict(path=r["resource"], blob_sha1=r["git_blob"], sha256=r["sha256"])
            for r in sorted(records.values(), key=lambda r: r.get("resource") or "")
            if r["availability"] == "available" and r.get("git_blob")])
        return records, fingerprint(projection), source

    def values(self, records):
        raw = dict(self.resources)
        result = {}
        for language, record in records.items():
            path = record.get("resource")
            data = raw.get(path)
            status, parsed = "available", None
            if record["availability"] != "available" or data is None:
                status = "resource_unavailable"
            elif type(data) is not bytes or len(data) > 8_000_000:
                status = "invalid_source"
            elif (hashlib.sha256(data).hexdigest() != record["sha256"] or not record.get("git_blob")
                    or blob_sha(data) != record["git_blob"] or record.get("size", len(data)) != len(data)):
                status = "unverifiable_provenance"
            else:
                try:
                    parsed = parse(data)
                except BulkError:
                    status = "invalid_source"
            result[language] = (status, parsed, path, record.get("sha256"))
        return result


class SourceVerifier(Protocol):
    """Trusted code boundary, never selected/deserialized by an evidence document.

    A future authorized adapter must independently reobserve upstream Git facts.
    M2 implements no such adapter. Checksums/context objects are not authenticators.
    """

    def verify(self, selection: TranslationSelection, context: SourceVerificationContext) -> str: ...


class UnavailableSourceVerifier:
    def verify(self, selection, context):
        return "unavailable"


def currentness(selection, context, verifier):
    value = selection.to_dict()
    claim = value["verification"]
    if claim["status"] == "stale":
        return "stale"
    if context is None or type(context) is not SourceVerificationContext:
        return "unverifiable"
    expected = {"selection_sha256": selection.sha256, "source_sha256": fingerprint(value["source"]),
        "verification_context_sha256": claim["context_sha256"], "commit": value["source"]["commit"],
        "tree": value["source"]["tree"], "issuer": claim["issuer"], "issuer_version": claim["issuer_version"],
        "as_of": claim["checked_at"]}
    if any(getattr(context, k) != v for k, v in expected.items()) or claim["status"] != "verified":
        return "unverifiable"
    status = (verifier or UnavailableSourceVerifier()).verify(selection, context)
    if status not in {"unavailable", "unverifiable", "stale", "verified-current", "synthetic-current"}:
        fail("source_verifier_result")
    if status == "verified-current" and claim["synthetic"]:
        return "synthetic-current"
    return status


def selection_value(policy, subject, requested, snapshot, keys, *, verification):
    """Construct M1 selection from actual scoped bytes, including only valid traces.

    Verification is a claim requiring independent SourceVerificationContext and
    a trusted verifier at evaluation. This helper cannot certify currentness.
    """
    language = policy.resolve(requested)
    records, snapshot_pin, source = snapshot.selected(["en", language] if keys else [])
    resources = snapshot.values(records)
    values = value_traces(resources, keys, language)
    if not source["resources"]:
        # M1's frozen source schema requires at least one resource. No dummy
        # resource/translation may be invented for empty or unavailable inputs.
        return None
    return TranslationSelection.from_dict(dict(schema_version=1, kind="translation-selection", stage="selection",
        id="translation."+subject.to_dict()["id"], version="1.0.0", language_policy=reference(policy),
        subject=reference(subject), requested_language=requested, language=language, snapshot_sha256=snapshot_pin,
        source=source, values=values, verification=verification | {"source_sha256": fingerprint(source)}))


def value_traces(resources, keys, language):
    values = []
    for key in sorted(keys):
        entries = []
        for code in ("en", language):
            status, data, path, _ = resources.get(code, ("resource_unavailable", None, None, None))
            found, value, _ = lookup(data, key) if status == "available" else (False, None, None)
            entries.append((found, value, path))
        (ef, en, _), (tf, target, path) = entries
        if ef and tf and type(en) is str and type(target) is str:
            values.append(dict(resource_path=path, key=key, source_value_sha256=fingerprint(en), value_sha256=fingerprint(target)))
    return sorted(values, key=lambda v: (v["resource_path"], v["key"]))
