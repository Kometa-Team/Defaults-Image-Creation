"""Capture the full accepted M2 facts without rewriting receipts or rendering."""

from collections import defaultdict

from ...common import BulkError, fingerprint
from ...definitions import Definition
from ..adoption.inventory import discover
from ..adoption.models import audit_membership, read_canonical
from ..playlist.validation import CONTRACT_SHA256, M2_SHA256
from .graph import Snapshot, node_id
from .resolution import resolve


def build(registry, records, resolution):
    """M2 membership pins are facts, not approval of a future contract.

    Whole raw/effective jobs are included in per-output context hashes. File
    containers are provenance; per-row and inherited-leaf projections prevent a
    different row in the same YAML file from invalidating unrelated artwork.
    """
    if registry.sha256 != M2_SHA256:
        raise BulkError("m5_adoption_pin", "Select the accepted complete M2 baseline")
    registry.verify_schema_pins()
    members = {m["id"]:m for m in registry.to_dict()["members"]}
    records = tuple(records)
    if {r.to_dict()["identity"]["id"] for r in records} != members.keys() or len(records) != len(members):
        raise BulkError("m5_adoption_membership", "The complete 14,079 pinned historical records are required")
    audit_membership(records)
    nodes, outputs = {}, {}
    resolved = resolution.data()
    family_for = {child:parent for parent,children in resolved["families"].items() for child in children}
    by_job = {r.to_dict()["job_id"]:r.to_dict()["identity"]["id"] for r in records}
    overlay_pairs = defaultdict(list)
    for r in records:
        v = r.to_dict()
        if v["identity"]["category"] == "Overlays":
            overlay_pairs[v["identity"]["source"]["path"]].append(v["identity"]["id"])

    def put(kind, identity, checksum, dependencies=()):
        key = node_id(kind, identity)
        row = {"kind":kind,"identity":identity,"sha256":checksum,"dependencies":sorted(set(dependencies))}
        if key in nodes and nodes[key] != row:
            raise BulkError("m5_dependency_substitution", "Conflicting hash or ownership for "+key)
        nodes[key] = row
        return key

    for record in records:
        value = record.to_dict()
        item, job = value["identity"], read_canonical(value["job_json"])
        identity = item["id"]
        if record.sha256 != members[identity]["sha256"] or value["job_id"] != members[identity]["job_id"]:
            raise BulkError("m5_adoption_record", "Historical record differs from its exact accepted member")
        definition = read_canonical(value["effective_definition_json"])
        deps = [put("asset",a["path"],a["sha256"]) for a in job["inputs"]]
        # A parent's output context, not merely a matching path/hash, owns each
        # generated input. M2 separately checks original owned worker receipts.
        deps += [node_id("output",by_job[d["job_id"]]) for d in job["dependencies"]]
        origin_deps = []
        if job["kind"] == "poster":
            if job["poster_id"] not in resolved["expanded"]:
                raise BulkError("m5_unknown_child", "Historical job is not an actual expanded definition")
            effective = Definition.create(resolved["expanded"][job["poster_id"]]).for_language(job["language"]).data
            if fingerprint(effective) != fingerprint(definition):
                raise BulkError("m5_effective_mismatch", "Current expanded definition differs from accepted M2 facts")
            declared = family_for.get(identity,identity)
            provenance = resolved["provenance"][declared]
            origin_deps.append(put("row",provenance["file"]+"#"+declared,provenance["row_sha256"]))
            if provenance["profile"]:
                origin_deps.append(put("profile",provenance["profile_file"]+"#"+provenance["profile"]+"#"+declared,
                                       provenance["inherited_sha256"]))
            if value["family"]:
                family = value["family"]
                if family_for.get(identity) != family["id"]:
                    raise BulkError("m5_orphan_child", "Generated child has no matching declared family")
                origin = resolved["origins"][identity]
                origin_deps.append(put("generator",origin["specification"]["name"]+"@"+str(origin["specification"]["version"]),origin["code_sha256"]))
                # Per-child realized parameters live in definition/job hashes;
                # this membership pin captures complete actual family expansion.
                origin_deps.append(put("family",family["id"],fingerprint(sorted(resolved["families"][family["id"]]))))
            if item["category"] == "Playlist":
                deps.append(put("rules","Playlist/timeline-order/review-only",CONTRACT_SHA256))
        else:
            # Overlay group/branch/size and source-preserving transform are
            # already explicit in the strict M2 overlay definition.
            origin_deps.append(put("row","overlays-v1.json#"+definition["group"],fingerprint(definition["transform"])))
        deps.append(put("definition",identity,fingerprint(definition),origin_deps))
        deps.append(put("transform",job["kind"],value["baseline_renderer_sha256"]))
        deps.append(put("background",identity,fingerprint({"color":job["parameters"].get("base_color"),"assignment":job["color_assignment"]})))
        for trace in job["translation"]["trace"]:
            # Exact resource hash AND key/value provenance are material today;
            # no speculative key-only compatibility bridge is manufactured.
            deps.append(put("caption",trace["language"]+"/"+trace["key"],fingerprint(trace)))
        for exception in value["historical_exceptions"]:
            deps.append(put("exception",identity+"/"+exception["code"],exception["evidence_sha256"]))
        context = fingerprint({"identity":item,"definition":definition,"job":job,
            "exceptions":value["historical_exceptions"],"renderer":value["baseline_renderer_sha256"]})
        output_node = put("output",identity,context,deps)
        ev = value["evidence"]
        companions = [value["paired_identity"]] if value["paired_identity"] else []
        if job["kind"] == "overlay":
            companions = [i for i in overlay_pairs[item["source"]["path"]] if i != identity]
        outputs[identity] = {"node":output_node,"category":item["category"],"kind":job["kind"],"variant":job["variant"],
            "local_path":item["local_path"],"public_path":item["public_path"],"companions":sorted(companions),
            "context_sha256":context,"evidence":{"previews":[],"confirmations":[],
                "decisions":[a["record_sha256"] for a in ev["approval_refs"]],
                "receipts":[ev["owned_receipt_sha256"],ev["original_receipt_sha256"]]}}
    return Snapshot.create({"schema_version":1,"kind":"m5-dependency-snapshot","basis":registry.sha256,
        "nodes":nodes,"outputs":outputs,"unresolved":[]})


def capture(*, progress=None):
    """Revalidate live sources, all expansion paths and 14,079 original receipts."""
    registry, records = discover(progress=progress)
    resolution = resolve()
    graph = build(registry,records,resolution)
    return registry, records, resolution, graph
