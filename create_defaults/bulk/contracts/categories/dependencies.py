"""Add reporting-only M6 contract dependencies to an unchanged M5 graph."""

from ...common import BulkError,fingerprint
from ..expanded.graph import Snapshot,node_id,compare
from ..adoption.models import read_canonical


def material_design(design,rule):
    """Exclude container/other-item evidence from this output's material rule.

    Exact per-item measurements, captions, colours and approval scopes already
    live in M5's output context and M6's pinned member, not aggregate hashes.
    """
    value=__import__("json").loads(__import__("json").dumps(design))
    if "typography" in value:
        value["caption"].pop("content_types")
        value["background"].pop("assignments_sha256")
        value["logo"].pop("historical_acceptance_refs")
        if value["fitting"] is not None:value["fitting"].pop("measurement_sha256")
    return {"design":value,"style":read_canonical(rule["style_json"]),"source_kind":rule["source_kind"],
        "treatment":rule["treatment"],"presentation":rule["presentation"],
        "required_presentations":rule["required_presentations"],"layout":read_canonical(rule["layout_json"])}


def bind(graph,implementation):
    value=graph.data()
    if value["basis"]!=implementation.release.to_dict()["basis_sha256"]:
        raise BulkError("category_graph_basis","Graph and implementation have different M2 origins")
    members_seen=set()
    for package in implementation.packages:
        c=package.contract.to_dict();rules,members=package.data()
        name="defaults."+c["category"].lower()+"."+c["kind"]+"@"+c["version"]
        contract_key=node_id("contract",name)
        row={"kind":"contract","identity":name,"sha256":package.contract.sha256,"dependencies":[]}
        if contract_key in value["nodes"] and value["nodes"][contract_key]!=row:
            raise BulkError("category_graph_conflict","Contract pin changed within one dependency snapshot")
        value["nodes"][contract_key]=row
        for identity,member in members.items():
            output=value["outputs"].get(identity)
            if output is None or output["category"]!=c["category"]:
                raise BulkError("category_graph_membership","Missing or switched category member")
            members_seen.add(identity)
            rule_key=node_id("rules","m6/"+identity)
            design=next(v["design"] for v in c["variants"] if v["id"]==member["variant"])
            # Whole package/sidecar hashes are provenance, not render/material
            # dependencies. D08 requires actual per-job deltas and a separate
            # adoption decision, rather than invalidating unchanged artwork.
            value["nodes"][rule_key]={"kind":"rules","identity":"m6/"+identity,
                "sha256":fingerprint({"rule":material_design(design,rules[member["variant"]]),"member":member}),"dependencies":[]}
            deps=value["nodes"][output["node"]]["dependencies"]
            value["nodes"][output["node"]]["dependencies"]=sorted(set(deps+[rule_key]))
            output["companions"]=member["companions"]
    if members_seen!=value["outputs"].keys():
        raise BulkError("category_graph_membership","An output has no category contract")
    return Snapshot.create(value)


def compare_implementations(graph,old,new):
    """Bulk impact assessment only; unchanged material still needs adoption.

    No compatibility attestation or new contract approval is minted here.
    """
    before,after=bind(graph,old),bind(graph,new)
    return compare(before,after) | {"old_release_sha256":old.release.sha256,"new_release_sha256":new.release.sha256,
        "package_approval_and_adoption_required":old.release.sha256!=new.release.sha256,
        "adoption_granted":False,"publication_authorized":False}
