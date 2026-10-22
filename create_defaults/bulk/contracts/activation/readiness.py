"""All 22 exact packages: compatibility is separate from approval and activation."""

from ...common import BulkError, fingerprint
from ..categories.audit import audit
from ..categories.dependencies import bind
from ..categories.release import RELEASE_SHA256
from ..adoption.sources import load_pins, SOURCE_PINS_SHA256
from .protection import verify


BASE = "c00a0f0b8efcb98857d24da659a30eb06043d6b0"
M6_GRAPH = "93b01e2261249185bd06982a9cb0823a61628104d327958cedefd97788a39d7d"
COMMITS = {
    "M1":"3d97bb888a2c3787609e4a0c88d5ee3e99bdcae2",
    "M2":"f2b7843fd1d832e2aecc36d66046b1010ed7fd5d",
    "M3":"22ab7c2eb73ca4199ec1f4b68be4290470f47663",
    "M4":"f10e95107501a029b206e87e19723ddf47a7f7ad",
    "M5":"e611076e23cab31efa578ee92f1514bc993e9f93",
    "M6":BASE,
}


def inventory(implementation, compatibility=None):
    """Missing approval is factual: the exact M6 review registry is empty.

    A caller-supplied compatibility dictionary never grants authority. The CLI
    only supplies one after audit(); default inspection says not freshly checked.
    """
    categories = {r["category"]:r for r in compatibility["categories"]} if compatibility else {}
    rows = []
    for package in implementation.packages:
        c = package.contract.to_dict();item = categories.get(c["category"])
        compatible = bool(item and not compatibility["incompatibilities"] and not compatibility["unresolved_design_interpretations"])
        rows.append({"category":c["category"],"kind":c["kind"],"version":c["version"],"contract_sha256":package.contract.sha256,
            "rules_sha256":package.rules.sha256,"variant_count":len(c["variants"]),"implemented":True,
            "historically_compatible":compatible if compatibility else "not_freshly_checked",
            "exact_contract_approval":"missing","approved_registry_context":"missing",
            "enforcement_state":"COMPATIBLE" if compatible else "IMPLEMENTED","production_enforcement":False,
            "prerequisites":{"historical_compatibility":"passed" if compatible else "requires_fresh_audit",
                "exact_package_approval":"missing","authenticated_intake":"unavailable","approved_operational_registry":"missing",
                "current_authorization":"unavailable","effective_coverage":"passed" if compatible else "requires_fresh_audit",
                "source_dependency_provenance":"passed" if compatible else "requires_fresh_audit",
                "m4_new_artifact_reviews":"not_requested_no_new_artwork",
                "complete_new_poster_previews":"later_workflow_required_for_new_posters",
                "required_historical_outputs":"passed" if compatible else "requires_fresh_audit",
                "exact_final_head_ci":"separate_ci_evidence","operator_activation_decision":"missing",
                "production_integration":"not_implemented_not_authorized"},
            "blockers":["missing_exact_hash_maintainer_approval","missing_approved_operational_registry",
                "authenticated_decision_intake_not_integrated","independent_operator_activation_not_authorized",
                "production_integration_not_implemented_or_authorized"]+([] if compatible else ["fresh_complete_historical_audit_required"])})
    return {"kind":"m7-contract-readiness","release_sha256":implementation.release.sha256,
        "review_registry_sha256":implementation.release.to_dict()["approval_registry_sha256"],
        "selectors":len(rows),"variants":sum(r["variant_count"] for r in rows),"packages":rows,
        "exact_approvals_present":0,"exact_approvals_missing":len(rows),"ready":0,"active":0,
        "authenticated_intake":"blocked_integration_boundary","production_enforcement":False,"publication_authorized":False}


def dossier(implementation, registry, records, resolution, graph, sources):
    """Fresh full read-only M2/M5/M6 reconciliation; never consumes signed claims."""
    report = audit(implementation,registry,records,resolution,graph)
    contract_graph = bind(graph,implementation)
    return assemble_dossier(implementation,registry,graph,sources,report,contract_graph)


def assemble_dossier(implementation,registry,graph,sources,report,contract_graph,*,dependency_index=None):
    """Assemble data from the actual same-run audit; never approval authority.

    The CLI calls dossier() above. The combined regression passes its already
    computed M6 audit and graph here, retaining every old/new assertion without
    constructing a second complete 87,142-node graph in the worker parent.
    Neither this report nor submitted compatibility JSON can approve a package.
    """
    if (report["release_sha256"],report["M2_registry_sha256"],report["M5_graph_sha256"]) != (implementation.release.sha256,registry.sha256,graph.sha256):
        raise BulkError("activation_audit_scope", "Audit and current immutable context differ")
    if (report["outputs"],report["posters"],report["overlays"],report["public_outputs"],len(sources)) != (14079,9957,4122,14077,2106):
        raise BulkError("activation_historical_counts", "Accepted full baseline differs; no repair attempted")
    if contract_graph.sha256 != M6_GRAPH or implementation.release.sha256 != RELEASE_SHA256:
        raise BulkError("activation_baseline", "Exact M6 implementation/dependency graph changed")
    readiness = inventory(implementation,report)
    if readiness["selectors"] != 22 or readiness["variants"] != 278:
        raise BulkError("activation_coverage", "Closed category/variant coverage differs")
    index = dependency_index if dependency_index is not None else contract_graph.index()
    small_impact = index.impact(["asset:logos_playlist/Arrowverse.png"])
    font_impact = index.impact(["asset:fonts/BebasNeue-Regular.ttf"])
    unknown = index.impact(["asset:unknown-new-dependency.png"])
    if len(small_impact["affected_outputs"]) != 3 or unknown["impact_complete"]:
        raise BulkError("activation_impact", "Dependency negative/control scopes differ")
    return {"schema_version":1,"kind":"m7-phase2-acceptance-dossier","base_commit":BASE,
        "merged_milestones":COMMITS,"M7_status":"IN PROGRESS","Phase2_status":"IN PROGRESS",
        "later_phases":{str(n):"NOT STARTED" for n in range(3,7)},
        "pins":{"M2_registry":registry.sha256,"M2_source_pins":SOURCE_PINS_SHA256,"M5_graph":graph.sha256,
            "M6_release":implementation.release.sha256,"M6_material_graph":contract_graph.sha256,
            "physical_input_set":fingerprint(sources),"source_pin_count":len(load_pins()["files"])},
        "compatibility":report,"readiness":readiness,"nonactivation":verify(),
        "impact_evidence":{"single_logo_affected_outputs":small_impact["affected_outputs"],
            "single_logo_affected_categories":sorted({index.outputs[i]["category"] for i in small_impact["affected_outputs"]}),
            "shared_font_affected_outputs":len(font_impact["affected_outputs"]),"unknown_scope_blocked":not unknown["impact_complete"]},
        "validation":{"historical":"fresh_full_readonly_pass","adversarial_and_recovery":"see exact-head pytest/CI evidence",
            "windows_linux_ci":"must be green at final PR head; see PR checks, not a prior commit"},
        "limitations":["no authenticated contract/activation intake","all 22 exact contract approvals missing",
            "no approved operational registry or activation decision","no production hook",
            "M4 logo-only previews cannot approve new poster composition","automatic logo correspondence remains uncalibrated/manual",
            "isolated ACTIVE simulations confer neither production nor publication authority",
            "no external anti-rollback checkpoint; restored ACTIVE snapshots require fresh runtime authorization"],
        "handoff":{"3":["authoritative translations and completeness/provenance","English official/non-English user destinations"],
            "4":["ADD UPDATE RENAME DELETE with stable IDs and dependencies","complete new poster composition and preview workflow"],
            "5":["authenticated approval capture and independent activation authorization","Package E exact artifact staging, reviewed publication, remote verification/recovery"],
            "6":["six outstanding Timeline Order requests remain unprocessed","genuine source submissions, complete previews, submitter confirmation, separate maintainer decision, exact publication verification"]},
        "artwork_regenerated":0,"remote_writes":0,"production_enforcement":False,"publication_authorized":False}
