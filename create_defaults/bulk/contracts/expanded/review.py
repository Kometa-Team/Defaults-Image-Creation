"""Typed M4 consumption; never recreate its confirmation/exception decisions."""

from dataclasses import dataclass

from ...common import BulkError, canonical, fingerprint
from ..adoption.models import read_canonical
from ..logos.storage import LogoArchive
from ..logos.workflow import Selection
from ..models import decode_json
from .validation import require_current as require_job_current
from .graph import Snapshot


@dataclass(frozen=True)
class ReviewBinding:
    encoded: bytes

    def data(self):
        return decode_json(self.encoded)


def consume(archive, identity, *, expected_sha256, selection, source_root, validation,
            graph, output_identity, definition, job, manifest_sha256=None,
            trusted_submitters=None, trusted_maintainers=None):
    """Call M4's existing verifier with actual externally supplied attribution.

    ``archive`` is an already opened isolated M4 archive, not a JSON review record.
    This operation writes neither state nor previews. M4 may replay its tiny
    owned evidence in memory. An end read detects concurrent/stale transitions.
    """
    if not isinstance(archive,LogoArchive) or not isinstance(selection,Selection):
        raise BulkError("m5_review_type", "Expected the existing typed M4 archive/selection interface")
    snapshot, prepared = archive.load(identity,expected_sha256=expected_sha256,selection=selection,
        source_root=source_root,trusted_submitters=trusted_submitters,trusted_maintainers=trusted_maintainers)
    spec = read_canonical(prepared.bundle.payload()["spec_json"])
    require_job_current(validation,definition=definition,job=job,manifest_sha256=manifest_sha256)
    if (spec["item"]["id"] != output_identity or validation.get("identity") != output_identity
            or spec["package"]["sha256"] != validation.get("contract_sha256")):
        raise BulkError("m5_review_context", "Review belongs to a different identity or exact category contract")
    index = graph.index()
    if output_identity not in index.outputs:
        raise BulkError("m5_review_membership", "Reviewed item is absent from the complete effective graph")
    root = index.outputs[output_identity]
    members = [output_identity]+root["companions"]
    if job["kind"] == "overlay":
        if {index.outputs[i]["variant"] for i in members} != {m["size"] for m in spec["required_outputs"]} or len(members) != len(spec["required_outputs"]):
            raise BulkError("m5_review_membership", "Both reviewed standard/bigger output members are required")
        selected = [m for m in spec["required_outputs"] if m["size"] == root["variant"]]
        if len(selected) != 1:
            raise BulkError("m5_review_membership", "Output variant is not in the reviewed membership")
        member = selected[0]
        expected = {"input":spec["sources"]["master"]["path"],"box":[member["box"]["width"],member["box"]["height"]],
            "trim":member["trim"],"colorspace":"sRGB","strip_metadata":True,"format":"PNG","resampling":"Pillow-LANCZOS"}
        if canonical(job["parameters"]) != canonical(expected):
            raise BulkError("m5_review_transform", "Final overlay differs from reviewed source-preserving transformation")
    if (spec["item"]["local_path"] != root["local_path"] or spec["item"]["public_path"] != root["public_path"]
            or (job["kind"] == "poster" and spec["background"] != job["parameters"]["base_color"])):
        raise BulkError("m5_review_context", "Reviewed mappings or proposed background changed")
    source = spec["sources"]["master"]
    source_node = index.nodes.get("asset:"+source["path"])
    # Both ownership and actual material source hash are required, not presence
    # of an unrelated same-hash asset elsewhere in the graph.
    deps = set()
    queue = [root["node"]]
    while queue:
        node = queue.pop()
        if node in deps:
            continue
        deps.add(node)
        queue.extend(index.nodes[node]["dependencies"])
    if (source_node is None or source_node["sha256"] != source["sha256"]
            or "asset:"+source["path"] not in deps):
        raise BulkError("m5_review_source", "Source bytes/path or owned dependency changed")
    if archive._latest(identity) != {"revision":snapshot.payload()["revision"],"sha256":expected_sha256}:
        raise BulkError("m5_stale_review", "M4 session changed during the read")
    phase = snapshot.payload()["phase"]
    return ReviewBinding(canonical({"schema_version":1,"kind":"m5-m4-review-binding",
        "identity":output_identity,"review_sha256":snapshot.sha256,"bundle_sha256":prepared.bundle.sha256,
        "effective_context_sha256":validation["context_sha256"],"graph_context_sha256":index.material_context(output_identity),
        "member_contexts":{i:index.material_context(i) for i in members},
        "source":source,"preview_type":spec["preview_type"],"fixture_only":spec["fixture_only"],
        "logo_review_phase":phase,"complete_poster_design_approval":False,
        "preview_sha256":fingerprint(read_canonical(prepared.bundle.payload()["preview_json"])),
        "confirmation_sha256":snapshot.payload()["confirmation_sha256"],"decision_sha256":snapshot.payload()["decision_sha256"],
        "publication_authorized":False,"merge_authorized":False}))


def require_current(binding, validation, graph, *, current_review_sha256):
    if not isinstance(binding,ReviewBinding):
        raise BulkError("m5_review_type", "Loose approval dictionaries are not M4 review bindings")
    value = binding.data()
    output = graph.index().outputs.get(value["identity"])
    index = graph.index()
    if (output is None or value["review_sha256"] != current_review_sha256
            or value["effective_context_sha256"] != validation.get("context_sha256")
            or value["graph_context_sha256"] != index.material_context(value["identity"])
            or any(i not in index.outputs or index.material_context(i) != h for i,h in value["member_contexts"].items())):
        raise BulkError("m5_stale_review", "Changed effective job, membership, dependency or M4 review requires re-review")
    return {"current":True,"complete_poster_design_approval":False,"publication_authorized":False}


def attach(graph, binding):
    """Add exact scoped M4 evidence references to an immutable reporting snapshot.

    This persists nothing, grants no authority and never changes an M4 record.
    A BOTH_REQUIRED or two-size approval scopes every reviewed companion.
    """
    if not isinstance(binding,ReviewBinding):
        raise BulkError("m5_review_type", "Typed verified M4 binding required")
    value, result, index = binding.data(),graph.data(),graph.index()
    for identity,context in value["member_contexts"].items():
        if identity not in index.outputs or index.material_context(identity) != context:
            raise BulkError("m5_stale_review", "Reviewed member dependency context changed")
        evidence = result["outputs"][identity]["evidence"]
        for field,key in (("previews","preview_sha256"),("confirmations","confirmation_sha256"),("decisions","decision_sha256")):
            if value[key] is not None:
                evidence[field] = sorted(set(evidence[field]+[value[key]]))
    return Snapshot.create(result)
