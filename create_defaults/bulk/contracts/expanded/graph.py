"""Immutable dependency snapshots and indexed, conservative read-only impact."""

from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import json

from ...common import BulkError, canonical, fingerprint, path_key, relative_path
from ...config import CATEGORIES
from ..registry import require_hash


MAX_BYTES = 128 * 1024 * 1024
KINDS = {"asset", "definition", "row", "profile", "family", "generator", "caption", "background",
         "transform", "contract", "rules", "exception", "output", "review"}


def node_id(kind, identity):
    if kind not in KINDS or type(identity) is not str or not identity:
        raise BulkError("m5_node", "Unknown dependency kind or empty identity")
    return kind+":"+identity


def closed(value, fields):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise BulkError("m5_shape", "Unknown or missing fields in M5 snapshot")


@dataclass(frozen=True)
class Snapshot:
    encoded: bytes

    @classmethod
    def create(cls, value):
        try:
            raw = canonical(value)
            if len(raw) > MAX_BYTES:
                raise BulkError("m5_limit", "Dependency snapshot exceeds the bounded read size")
            result = cls(raw)
            result.index()  # Validate every edge, namespace and cycle before returning.
            return result
        except (ValueError,TypeError,KeyError,RecursionError) as error:
            if isinstance(error,BulkError):
                raise
            raise BulkError("m5_shape","Malformed dependency graph; no partial graph accepted") from error

    @classmethod
    def load(cls, raw, *, expected_sha256):
        if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != require_hash(expected_sha256):
            raise BulkError("m5_snapshot_pin", "Missing, interrupted, stale or substituted dependency snapshot")
        def unique(pairs):
            result = {}
            for k,v in pairs:
                if k in result:
                    raise BulkError("m5_duplicate_key", "Duplicate snapshot key")
                result[k] = v
            return result
        try:
            value = json.loads(raw, object_pairs_hook=unique,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite")))
            if canonical(value) != raw:
                raise ValueError("noncanonical")
            return cls.create(value)
        except (UnicodeError, ValueError, TypeError, RecursionError) as error:
            if isinstance(error, BulkError):
                raise
            raise BulkError("m5_snapshot_json", "Invalid canonical dependency JSON") from error

    @property
    def sha256(self):
        return hashlib.sha256(self.encoded).hexdigest()

    def data(self):
        return json.loads(self.encoded)

    def index(self):
        return Index(self.data())


class Index:
    """Construct once per verified snapshot; individual impact calls do no I/O."""
    def __init__(self, value):
        closed(value, "schema_version kind basis nodes outputs unresolved")
        if type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["kind"] != "m5-dependency-snapshot":
            raise BulkError("m5_version", "Unsupported dependency snapshot version")
        require_hash(value["basis"])
        if type(value["nodes"]) is not dict or type(value["outputs"]) is not dict or type(value["unresolved"]) is not list:
            raise BulkError("m5_shape", "Invalid graph tables")
        if any(type(gap) is not str or not gap for gap in value["unresolved"]):
            raise BulkError("m5_shape", "Unresolved paths must be explicit diagnostics")
        self.nodes, self.outputs, self.unresolved = value["nodes"], value["outputs"], value["unresolved"]
        self.reverse = defaultdict(set)
        self.output_nodes = {}
        paths = {"local_path": {}, "public_path": {}, "id": {}, "asset": {}}
        for key, row in self.nodes.items():
            closed(row, "kind identity sha256 dependencies")
            if key != node_id(row["kind"], row["identity"]):
                raise BulkError("m5_node", "Graph key and exact dependency identity differ")
            require_hash(row["sha256"])
            if type(row["dependencies"]) is not list or any(type(d) is not str for d in row["dependencies"]) or len(set(row["dependencies"])) != len(row["dependencies"]):
                raise BulkError("m5_edges", "Dependencies must be unique exact node identities")
            if row["kind"] == "asset":
                relative_path(row["identity"])
                normalized = path_key(row["identity"])
                if normalized in paths["asset"]:
                    raise BulkError("m5_asset_collision", "Source casing/Unicode aliases cannot substitute assets")
                paths["asset"][normalized] = key
            for dep in row["dependencies"]:
                if dep not in self.nodes:
                    raise BulkError("m5_missing_node", "Dependency graph is incomplete: "+dep)
                self.reverse[dep].add(key)
        for identity, row in self.outputs.items():
            closed(row, "node category kind variant local_path public_path companions evidence context_sha256")
            node = self.nodes.get(row["node"])
            if node is None or node["kind"] != "output" or node["identity"] != identity:
                raise BulkError("m5_output", "Output identity and owned graph node differ")
            if row["category"] not in CATEGORIES or row["kind"] not in {"poster", "overlay"} or (row["category"] == "Overlays") != (row["kind"] == "overlay"):
                raise BulkError("m5_category", "Output category/kind mismatch")
            require_hash(row["context_sha256"])
            if type(row["variant"]) is not str or not row["variant"]:
                raise BulkError("m5_variant", "Output member needs an exact variant")
            for field in ("id", "local_path", "public_path"):
                path = identity if field == "id" else row[field]
                if path is None and field == "public_path":
                    continue
                if type(path) is not str or not path:
                    raise BulkError("m5_namespace", "Missing exact output identity/path")
                if field != "id":
                    relative_path(path)
                normalized = path_key(path)
                if normalized in paths[field]:
                    raise BulkError("m5_collision", "Cross-category case/Unicode identity or output collision")
                paths[field][normalized] = identity
            if type(row["companions"]) is not list or len(set(row["companions"])) != len(row["companions"]):
                raise BulkError("m5_companion", "Invalid required variant membership")
            for companion in row["companions"]:
                if companion == identity or companion not in self.outputs or identity not in self.outputs[companion]["companions"]:
                    raise BulkError("m5_companion", "Required companion output is missing or asymmetric")
            closed(row["evidence"], "previews confirmations decisions receipts")
            for hashes in row["evidence"].values():
                if type(hashes) is not list:
                    raise BulkError("m5_evidence", "Evidence must be scoped hash lists")
                for h in hashes:
                    require_hash(h)
            self.output_nodes[row["node"]] = identity
        if {k for k,n in self.nodes.items() if n["kind"] == "output"} != set(self.output_nodes):
            raise BulkError("m5_orphan", "Orphaned/unrecognized generated output node")
        # Iterative topological check also bounds deeply nested/untrusted graphs.
        degree = {k:len(v["dependencies"]) for k,v in self.nodes.items()}
        ready = deque(k for k,n in degree.items() if n == 0)
        count = 0
        while ready:
            count += 1
            for child in self.reverse[ready.popleft()]:
                degree[child] -= 1
                if degree[child] == 0:
                    ready.append(child)
        if count != len(self.nodes):
            raise BulkError("m5_cycle", "Dependency snapshot contains a cycle")

    def material_context(self, identity):
        """Pin this output's entire dependency closure, never the global graph."""
        if identity not in self.outputs:
            raise BulkError("m5_output", "Unknown output for review binding")
        visited, queue = set(), [self.outputs[identity]["node"]]
        while queue:
            key = queue.pop()
            if key not in visited:
                visited.add(key)
                queue.extend(self.nodes[key]["dependencies"])
        return fingerprint({"output":{k:v for k,v in self.outputs[identity].items() if k != "evidence"},
            "dependencies":{k:self.nodes[k] for k in sorted(visited)}})

    def impact(self, changes):
        """Exact for the captured graph; uncertainty never becomes approval."""
        changes = set(changes)
        unknown = sorted(changes - self.nodes.keys())
        known = changes & self.nodes.keys()
        direct_nodes = known | {child for key in known for child in self.reverse[key]}
        touched, queue = set(known), deque(known)
        while queue:
            for child in self.reverse[queue.popleft()]:
                if child not in touched:
                    touched.add(child)
                    queue.append(child)
        affected = {self.output_nodes[n] for n in touched if n in self.output_nodes}
        direct = {self.output_nodes[n] for n in direct_nodes if n in self.output_nodes}
        companions = {c for identity in affected for c in self.outputs[identity]["companions"]} - affected
        invalidations = {field:[{"output":i,"sha256":h} for i in sorted(affected)
            for h in self.outputs[i]["evidence"][field]] for field in ("previews", "confirmations", "decisions")}
        unresolved = list(self.unresolved) + ["unknown changed dependency: "+k for k in unknown]
        unresolved += ["family-scoped provenance change needs per-child resolution/comparison: "+k
            for k in sorted(known) if self.nodes[k]["kind"] == "family"
            or self.nodes[k]["kind"] == "row" and len(self.reverse[k]) > 1]
        return {"changed_identities":sorted(changes), "direct_outputs":sorted(direct),
            "transitive_outputs":sorted(affected-direct), "affected_outputs":sorted(affected),
            "required_companions":sorted(companions), "evidence_requiring_review":invalidations,
            "unaffected_outputs":sorted(self.outputs.keys()-affected), "unresolved":unresolved,
            "impact_complete":not unresolved, "publication_authorized":False, "merge_authorized":False}


def compare(previous: Snapshot, proposed: Snapshot):
    """Diff semantic node content and topology; additions/removals are changes."""
    old, new = previous.index(), proposed.index()
    changed = {k for k in old.nodes.keys() | new.nodes.keys() if old.nodes.get(k) != new.nodes.get(k)}
    # Membership/evidence are material review context, even if pixels are equal.
    for identity in old.outputs.keys() | new.outputs.keys():
        if old.outputs.get(identity) != new.outputs.get(identity):
            for index in (old,new):
                if identity in index.outputs:
                    changed.add(index.outputs[identity]["node"])
    before = old.impact(changed & old.nodes.keys())
    after = new.impact(changed & new.nodes.keys())
    affected = set(before["affected_outputs"]) | set(after["affected_outputs"])
    unresolved = sorted(set(before["unresolved"]+after["unresolved"]))
    evidence = {field:sorted({(r["output"],r["sha256"]) for r in before["evidence_requiring_review"][field]})
                for field in before["evidence_requiring_review"]}
    return {"previous_sha256":previous.sha256,"proposed_sha256":proposed.sha256,
        "changed_identities":sorted(changed),"direct_outputs":sorted(set(before["direct_outputs"]+after["direct_outputs"])),
        "transitive_outputs":sorted(affected-set(before["direct_outputs"]+after["direct_outputs"])),
        "affected_outputs":sorted(affected),"required_companions":sorted(set(before["required_companions"]+after["required_companions"])-affected),
        "evidence_requiring_review":{f:[{"output":i,"sha256":h} for i,h in rows] for f,rows in evidence.items()},
        "unaffected_outputs":sorted((old.outputs.keys() | new.outputs.keys())-affected),
        "unresolved":unresolved,"impact_complete":not unresolved,"publication_authorized":False,"merge_authorized":False}
