"""Read-only resource discovery and immutable, content-addressed snapshots."""

import base64
from dataclasses import dataclass
import json
from pathlib import Path
import time

from create_people_posters.github_inventory_core import blob_sha, complete_tree
from .common import BulkError, atomic_bytes, canonical, confined, fingerprint, path_key, reject_links, sha256
from .config import LANGUAGES, language_id
from .translations import Translations


REPOSITORY = "Kometa-Team/Translations"
CONTRIBUTION = {"url": "https://translations.kometa.wiki/", "level": "landing",
                "direct_key_available": False, "reason": "Anonymous site requires sign-in; component/key mappings unverified"}


def observed_client(*, token=None):
    from .remote import ReadOnlyGitHub
    client = ReadOnlyGitHub(REPOSITORY, token=token)
    client.observation = {"requests": 0, "http_statuses": {}, "errors": 0}
    def record(response, *args, **kwargs):
        observation = client.observation
        observation["requests"] += 1
        status = str(response.status_code)
        observation["http_statuses"][status] = observation["http_statuses"].get(status, 0) + 1
        observation["errors"] += int(response.status_code >= 400)
        # Record counters, never request headers, credentials or response bodies.
    client._session.hooks["response"].append(record)
    return client


@dataclass(frozen=True)
class LanguageSnapshot:
    encoded: bytes

    @classmethod
    def create(cls, records, *, provenance, aliases=None):
        aliases = aliases or {}
        records = sorted(records, key=lambda item: item["code"])
        seen = set()
        for record in records:
            code = language_id(record["code"])
            language_id(record["native_code"])
            key = path_key("defaults-" + code + "/poster.jpg")
            if key in seen:
                raise BulkError("language_collision", "Language output identifiers collide")
            seen.add(key)
            if record["availability"] not in {"available", "unavailable", "not_discovered"}:
                raise BulkError("invalid_registry", "Invalid resource availability")
            if record["availability"] == "available" and (not record.get("resource") or not record.get("sha256")):
                raise BulkError("invalid_registry", "Available resources require location and exact content identity")
            if record.get("resource"):
                path_key(record["resource"])
            if record.get("sha256") is not None and (len(record["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in record["sha256"])):
                raise BulkError("invalid_registry", "Invalid resource content hash")
        codes = {r["code"] for r in records}
        folded = {code.casefold(): code for code in codes}
        for alias, target in aliases.items():
            language_id(alias)
            if target not in codes or (alias in codes and alias != target) or (alias.casefold() in folded and folded[alias.casefold()] != target):
                raise BulkError("language_collision", "Alias collides or targets an unknown canonical identifier")
            if alias.casefold() in folded and folded[alias.casefold()] != target:
                raise BulkError("language_collision", "Case-colliding alias")
            folded[alias.casefold()] = target
        value = {"schema_version": 1, "languages": records, "aliases": aliases, "provenance": provenance,
                 "contribution": CONTRIBUTION}
        from .definitions import validate_schema
        validate_schema(value, "languages-v1.json")
        if len(canonical(value)) > 2_000_000:
            raise BulkError("invalid_registry", "Language metadata exceeds the bounded snapshot size")
        value["sha256"] = fingerprint(value)
        return cls(canonical(value))

    @property
    def data(self):
        return json.loads(self.encoded)

    @property
    def fingerprint(self):
        return self.data["sha256"]

    def select(self, requested):
        value = self.data
        codes = {r["code"] for r in value["languages"]}
        if tuple(requested) == ("all",):
            return tuple(r["code"] for r in value["languages"] if "defaults" in r["components"])
        result = []
        for code in requested:
            code = value["aliases"].get(code, code)
            if code not in codes:
                raise BulkError("undiscovered_language", "Language absent from pinned registry: " + str(code))
            result.append(code)
        return tuple(dict.fromkeys(result))

    def record(self, code):
        return next((r for r in self.data["languages"] if r["code"] == code), None)

    @classmethod
    def load(cls, path):
        path = reject_links(path)
        if path.stat().st_size > 2_000_000:
            raise BulkError("invalid_registry", "Registry exceeds metadata bound")
        data = json.loads(path.read_text(encoding="utf-8"))
        value = cls.create(data["languages"], provenance=data["provenance"], aliases=data["aliases"])
        if value.data != data:
            raise BulkError("corrupt_snapshot", "Registry hash/schema mismatch")
        return value


def local_snapshot(sources):
    """Historical IDs remain discoverable, but are not a maximum allowlist."""
    records = []
    for code in sorted(set(LANGUAGES) | set(sources)):
        available = code in sources
        records.append({"native_code": code, "code": code, "display_name": None,
                        "resource": code + ".yml" if available else None,
                        "sha256": sha256(reject_links(sources[code])) if available else None,
                        "availability": "available" if available else "not_discovered",
                        "components": ["defaults"], "font_support": "requires_variant_preflight"})
    return LanguageSnapshot.create(records, provenance={"kind": "explicit-local-files", "repository": None, "commit": None})


def refresh(cache, client):
    """Explicit network boundary; no rendering worker performs these GETs."""
    if client.repo != REPOSITORY:
        raise BulkError("invalid_repository", "Expected authoritative Translations repository")
    cache = reject_links(cache)
    started = time.perf_counter()
    commit, tree = client.head("master")
    entries = complete_tree(client.tree, tree)
    records, downloaded, reused = [], 0, 0
    for entry in entries:
        path = entry["path"]
        if entry["type"] != "blob" or not path.startswith("defaults/") or path.count("/") != 1 or not path.endswith(".yml"):
            continue
        code = language_id(Path(path).stem)
        if entry.get("mode") not in {"100644", "100755"} or entry.get("size", 8_000_001) > 8_000_000:
            raise BulkError("invalid_translation", "Unsafe translation resource")
        target = confined(cache, "blobs/" + entry["sha"] + ".yml")
        if target.is_file():
            data = target.read_bytes()
            reused += 1
        else:
            blob = client.blob(entry["sha"])
            if blob.get("encoding") != "base64" or blob.get("sha") != entry["sha"]:
                raise BulkError("corrupt_snapshot", "Invalid Git translation blob")
            data = base64.b64decode(blob["content"].replace("\n", ""), validate=True)
            if len(data) > 8_000_000 or blob_sha(data) != entry["sha"] or len(data) != entry["size"]:
                raise BulkError("corrupt_snapshot", "Translation Git blob identity/size mismatch")
            atomic_bytes(target, data)
            downloaded += 1
        if blob_sha(data) != entry["sha"] or len(data) != entry["size"]:
            raise BulkError("corrupt_snapshot", "Cached translation blob changed")
        # Parse and reject duplicate/case-ambiguous keys before publishing snapshot.
        Translations({code: target})
        records.append({"native_code": code, "code": code, "display_name": None, "resource": path,
                        "sha256": sha256(target), "git_blob": entry["sha"], "size": len(data),
                        "availability": "available", "components": ["defaults"],
                        "font_support": "requires_variant_preflight"})
    if not records or not any(r["code"] == "en" for r in records):
        raise BulkError("invalid_registry", "No source-English poster resource discovered")
    snapshot = LanguageSnapshot.create(records, provenance={"kind": "verified-git-blobs", "repository": REPOSITORY,
                                      "commit": commit, "tree": tree})
    target = confined(cache, "snapshots/" + snapshot.fingerprint + ".json")
    if not target.exists():
        atomic_bytes(target, snapshot.encoded + b"\n")
    return snapshot, {"downloaded": downloaded, "cache_reused": reused, "elapsed_seconds": time.perf_counter() - started,
                      "network": getattr(client, "observation", None),
                      "snapshot_file": str(target)}


def translations_from_snapshot(snapshot, cache):
    sources = {}
    for record in snapshot.data["languages"]:
        if record["availability"] != "available" or "defaults" not in record["components"]:
            continue
        path = confined(cache, "blobs/" + record["git_blob"] + ".yml", must_exist=True)
        if sha256(path) != record["sha256"] or blob_sha(path.read_bytes()) != record["git_blob"]:
            raise BulkError("corrupt_snapshot", "Offline translation bytes differ from pinned registry")
        sources[record["code"]] = path
    return Translations(sources)
