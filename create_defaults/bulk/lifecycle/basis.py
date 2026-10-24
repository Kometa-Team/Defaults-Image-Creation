"""Exact frozen historical mappings and semantic bridges, never new adoption."""

from functools import lru_cache
import gzip
import json
from pathlib import Path
from types import MappingProxyType

from ..common import canonical, fingerprint
from ..contracts.adoption.models import HistoricalRegistry
from ..contracts.models import Identity
from ..contracts.categories.release import Implementation, RELEASE_SHA256
from ..contracts.expanded.resolution import resolve
from ..contracts.playlist.validation import M2_SHA256
from .identity_models import fail


MAPPING_SHA256 = "6d1a49062208e8361227942549a4adafb0f2fed63c2f3a9a63c7860845ab876f"
HISTORICAL_GRAPH_SHA256 = "93b01e2261249185bd06982a9cb0823a61628104d327958cedefd97788a39d7d"
BASE = Path(__file__).parents[1]/"contracts/adoption/baseline"
GENERATORS = {"award-years", "best-of-years", "separator-variants", "content-rating-series"}


def semantic_tokens(definition):
    """Semantic variables from validated registered parameters, never filenames."""
    g = definition["generator"]
    if g is None:return []
    if g["version"] != 1 or g["name"] not in GENERATORS:fail("unsupported_generator")
    p = g["parameters"]
    if g["name"] in {"award-years", "best-of-years"}:
        return ["year:"+str(y) for y in range(p["start"], p["stop"], p["step"])]
    if g["name"] == "separator-variants":
        return ["separator:"+v["name"] for v in p["variants"]]
    return ["rating:"+v for v in p["values"]]


class HistoricalBasis:
    def __init__(self):
        with gzip.open(BASE/"stable-mapping-v1.json.gz", "rb") as f:raw = f.read(64*1024*1024+1)
        if len(raw) > 64*1024*1024:fail("historical_bound")
        rows = json.loads(raw)
        if fingerprint(rows) != MAPPING_SHA256 or len(rows) != 14079:fail("historical_mapping_pin")
        with gzip.open(BASE/"frozen-registry-v1.json.gz", "rb") as f:
            registry = HistoricalRegistry.from_bytes(f.read(8*1024*1024+1))
        if registry.sha256 != M2_SHA256:fail("historical_registry_pin")
        registry.verify_schema_pins()
        members = {m["id"]:m for m in registry.to_dict()["members"]}
        self.implementation = Implementation.load(expected_sha256=RELEASE_SHA256)
        assignments = {};packages={};rules_index={}
        for p in self.implementation.packages:
            rules,current = p.data();assignments.update(current)
            category=p.contract.to_dict()['category'];packages[category]=p
            rules_index.update({(category,k):canonical(v) for k,v in rules.items()})
        indexed = {}
        for row in rows:
            i = Identity.from_dict(row["identity"])
            identity = i.to_dict()["id"]
            if (members[identity]["sha256"], members[identity]["job_id"]) != (row["record_sha256"], row["job_id"]):fail("historical_record_pin")
            if assignments[identity]["record_sha256"] != row["record_sha256"]:fail("historical_assignment_pin")
            indexed[identity] = canonical(row)
        if len(indexed) != 14079 or indexed.keys() != members.keys() or assignments.keys() != indexed.keys():fail("historical_membership")
        self.ids = frozenset(indexed)
        self._rows = MappingProxyType(indexed)
        self._assignments = MappingProxyType({k:canonical(v) for k,v in assignments.items()})
        self._packages=MappingProxyType(packages);self._rules=MappingProxyType(rules_index)
        self.parents = frozenset(r["family"]["id"] for r in rows if r["family"])
        self.mapping_sha256 = MAPPING_SHA256
        self.registry_sha256 = registry.sha256

    def row(self, identity):
        if identity not in self._rows:fail("unknown_historical_identity")
        return json.loads(self._rows[identity])

    def assignment(self, identity):
        if identity not in self._assignments:fail("unknown_historical_identity")
        return json.loads(self._assignments[identity])

    def package(self,category):
        if category not in self._packages:fail('unsupported_category')
        return self._packages[category]

    def rule(self,category,variant):
        if (category,variant) not in self._rules:fail('unsupported_category_variant')
        return json.loads(self._rules[(category,variant)])

    def rows(self):
        return [self.row(i) for i in sorted(self.ids)]

    @property
    def resolution(self):
        return frozen_resolution()

    def semantic_index(self):
        return historical_semantics()

    def entry(self, identity):
        row = self.row(identity);i = row["identity"];a = self.assignment(identity)
        inverse = historical_inverse()
        category,parent,key,role,language = inverse[identity]
        names = dict(display_name=i["display_name"], rendered_caption=i["rendered_caption"],
            source=i["source"], local_path=i["local_path"], public_path=i["public_path"])
        return dict(id=identity, category=category, origin="historical-reference",
            historical_sha256=row["record_sha256"], revision=1,
            semantic=dict(parent=parent,key=key,role=role,language=language),variant=a["variant"],
            names=names,original_names=json.loads(canonical(names)),aliases=[],tombstone_sha256=None)


@lru_cache(maxsize=1)
def historical_basis():
    return HistoricalBasis()


@lru_cache(maxsize=1)
def frozen_resolution():
    # No output/artifact generation: the original loader/expander only.
    value = resolve()
    actual = set(value.data()["expanded"])
    expected = {i for i in historical_basis().ids if historical_basis().row(i)["identity"]["category"] != "Overlays"}
    if actual != expected:fail("historical_expansion_membership")
    return value


@lru_cache(maxsize=1)
def historical_semantics():
    basis = historical_basis();r = frozen_resolution().data();result = {}
    generated = {}
    for parent, children in r["families"].items():
        tokens = semantic_tokens(r["declared"][parent])
        if len(tokens) != len(children) or len(set(tokens)) != len(tokens):fail("semantic_generator_membership")
        for token,identity in zip(tokens,children):generated[identity] = (parent,token)
    for identity in sorted(basis.ids):
        row = basis.row(identity);i = row["identity"];a = basis.assignment(identity)
        if i["category"] == "Overlays":
            # source_identity is frozen independently of both output filenames.
            parent = "historical.overlay."+a["variant"]+"."+row["source_identity"]
            key = "source"
        elif identity in generated:parent,key = generated[identity]
        elif a["companions"]:
            parent = min([identity,*a["companions"]]);key = "base"
        else:parent,key = None,"adopted:"+identity
        semantic = (i["category"],parent,key,a["presentation"],"en")
        if semantic in result:fail("historical_semantic_collision")
        result[semantic] = identity
    return MappingProxyType(result)


@lru_cache(maxsize=1)
def historical_inverse():
    return MappingProxyType({v:k for k,v in historical_semantics().items()})
