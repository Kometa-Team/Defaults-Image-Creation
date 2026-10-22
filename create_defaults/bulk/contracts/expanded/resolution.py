"""Adapters to Package E's loaders/expander/planner, never another YAML engine."""

from dataclasses import dataclass
import json
import hashlib
from pathlib import Path

from ...catalog import CATALOG
from ...common import BulkError, canonical, fingerprint, load_yaml, path_key, reject_links
from ...config import CATEGORIES
from ...definitions import Definition, load_definitions
from ...generators import GENERATORS
from ...planner import Planner, validate_manifest


ALLOWLIST_VERSION = 1
CONTRIBUTOR_FIELDS = ("display_name", "source", "content_type", "background_proposal")


def contribution(profile, raw):
    """Only inherited leaves not replaced by this row are material to it."""
    result = {}
    for key, value in profile.items():
        if key not in raw:
            result[key] = value
        elif isinstance(value, dict) and isinstance(raw[key], dict):
            nested = contribution(value, raw[key])
            if nested:
                result[key] = nested
    return result


@dataclass(frozen=True)
class Resolution:
    encoded: bytes
    source_pins: tuple = ()

    def data(self):
        # Constructed only by the loader above, not an untrusted JSON intake.
        return json.loads(self.encoded)

    @property
    def sha256(self):
        return fingerprint(self.data())

    def definition(self, identity, language="en"):
        value = self.data()
        if identity not in value["expanded"]:
            raise BulkError("m5_unknown_child", "Identity is not an actual expanded Package E definition")
        return Definition.create(value["expanded"][identity]).for_language(language).data

    def verify_current(self, identities=None):
        """Read exact known definition inputs, not a filesystem/catalog scan."""
        if not self.source_pins:
            raise BulkError("m5_resolution_provenance","A loose expanded JSON value is not an owned loader resolution")
        value=self.data()
        parents={child:parent for parent,children in value["families"].items() for child in children}
        selected=set(value["provenance"]) if identities is None else {parents.get(i,i) for i in identities}
        needed=set()
        for identity in selected:
            if identity not in value["provenance"]:
                raise BulkError("m5_unknown_child","No actual declared owner for expanded identity")
            row=value["provenance"][identity]
            needed.update((row["file"],row["profile_file"]))
        for name,path,checksum in self.source_pins:
            if name in needed:
                current=reject_links(Path(path))
                if not current.is_file() or current.stat().st_size > 2_000_000:
                    raise BulkError("m5_stale_resolution","Definition source is absent or oversized")
                actual=current.read_bytes()
                if hashlib.sha256(actual).hexdigest() != checksum:
                    raise BulkError("m5_stale_resolution","Definition/profile source changed; resolve again before validation")


def resolve(paths=None, *, profiles_path=None):
    """Read final definitions, explicit profile contributions and family origins.

    The generator registry is the existing production registry; caller-supplied
    callbacks, recursive templates and YAML aliases are not an extension point.
    No asset pixels, output files, state store or network are touched.
    """
    paths = tuple(Path(p) for p in paths) if paths is not None else tuple(
        CATALOG / (c.lower()+".yml") for c in CATEGORIES if c != "Overlays")
    profiles_path = Path(profiles_path) if profiles_path is not None else CATALOG / "profiles.yml"
    if len({p.name for p in (*paths,profiles_path)}) != len(paths)+1:
        raise BulkError("m5_definition_source","Ambiguous definition source basenames")
    # Read twice around the production loader to detect interrupted edits.
    for path in (*paths,profiles_path):
        reject_links(path)
        if not path.is_file() or path.stat().st_size > 2_000_000:
            raise BulkError("m5_yaml_limit", "Absent or oversized Package E definition source")
    before = {str(p): p.read_bytes() for p in (*paths, profiles_path)}
    definitions = load_definitions(paths, profiles_path=profiles_path)
    catalog, families, origins = Planner(generators=GENERATORS).expand(definitions)
    shared = load_yaml(profiles_path)["profiles"]
    provenance = {}
    for path in paths:
        for raw in load_yaml(path)["definitions"]:
            parent = raw.get("extends")
            provenance[raw["id"]] = {"file": path.name, "profile_file": profiles_path.name,
                "row_sha256": fingerprint({k:v for k,v in raw.items() if k != "extends"}),
                "profile": parent, "inherited_sha256": fingerprint(contribution(shared.get(parent, {}), raw))}
    if any(p.read_bytes() != before[str(p)] for p in (*paths, profiles_path)):
        raise BulkError("m5_unstable_read", "Definitions changed while resolving; retry from a stable snapshot")
    seen = {}
    for identity in catalog:
        key = path_key(identity)
        if key in seen:
            raise BulkError("m5_identity_collision", "Case/Unicode equivalent expanded identities conflict")
        seen[key] = identity
    # Detect cycles/missing parents even before asset-dependent Planner.plan.
    pending = {key: {d["poster_id"] for d in v.data["dependencies"]} for key,v in catalog.items()}
    if any(dep not in catalog for deps in pending.values() for dep in deps):
        raise BulkError("m5_missing_dependency", "Expanded definition refers to an unknown parent")
    remaining = set(pending)
    while remaining:
        ready = {key for key in remaining if not (pending[key] & remaining)}
        if not ready:
            raise BulkError("m5_dependency_cycle", "Expanded parent dependencies contain a cycle")
        remaining -= ready
    value = {"schema_version": 1, "allowlist_version": ALLOWLIST_VERSION,
        "declared": {d.id:d.data for d in definitions},
        "expanded": {key:d.data for key,d in catalog.items()},
        "families": families, "origins": origins, "provenance": provenance}
    pins=tuple((p.name,str(p.resolve()),hashlib.sha256(before[str(p)]).hexdigest()) for p in (*paths,profiles_path))
    return Resolution(canonical(value),pins)


def plan(resolution, translations, *, config=None, categories=(), posters=(), languages=("en",), dependency_artifacts=None):
    """Optional non-rendering production planner, including real parent-byte checks.

    Missing parent artifacts block, rather than inventing receipts or generating
    parents. The returned manifest still needs contract and M4 evidence checks.
    """
    value=resolution.data()
    selected=set()
    for identity in posters:
        selected.update(value["families"].get(identity,[identity]))
    if categories:
        selected.update(k for k,v in value["expanded"].items() if v["category"] in categories)
    queue=list(selected)
    while queue:
        identity=queue.pop()
        if identity not in value["expanded"]:
            raise BulkError("m5_unknown_child","Selection is not a real expanded definition")
        for dep in value["expanded"][identity]["dependencies"]:
            if dep["poster_id"] not in selected:
                selected.add(dep["poster_id"]);queue.append(dep["poster_id"])
    resolution.verify_current(selected if selected else None)
    definitions = tuple(Definition.create(v) for v in value["declared"].values())
    return validate_manifest(Planner(config, generators=GENERATORS, scope="isolated M5 read-only plan").plan(
        definitions, translations, categories=categories, posters=posters, languages=languages,
        dependency_artifacts=dependency_artifacts))
