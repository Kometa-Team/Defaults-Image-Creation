"""Explicit replay of current M2/M3 inputs and scoped M5/M6/M7 inspection.

The controlled caller selects current inputs and independent expected pins. No
object here authenticates that caller, fetches a source, or grants permission.
"""

from dataclasses import dataclass

from ...common import canonical, fingerprint
from ..models import decode_json, read_document
from ..registry import require_hash
from ..language_policy import LanguagePolicy, reference
from ..translation_preflight import revalidate as replay_translation
from ..translation_preflight.adapters import PosterRequest, OverlayRequest
from ..destination_preflight import BoundTranslation, DestinationAttestation
from ..destination_preflight import revalidate as replay_destination
from ..destination_preflight.bindings import cohort
from ..expanded.graph import Snapshot
from .models import RequestContext, ConsumptionAttestation, fail


@dataclass(frozen=True)
class TranslationInput:
    request: object
    requested: str
    snapshot: object
    selection: object
    report: object
    expected_sha256: str | None
    context: object = None
    verifier: object = None


def _references(context, payloads, subjects):
    if type(payloads) is not tuple or any(type(p) is not bytes for p in payloads):
        fail("reference_payloads")
    indexed = {}
    for raw in payloads:
        value = decode_json(raw)
        if canonical(value) != raw:
            fail("noncanonical_reference")
        pin = fingerprint(value)
        if pin in indexed:
            fail("duplicate_reference")
        indexed[pin] = value
    refs = context["references"]
    if set(indexed) != {r["sha256"] for r in refs}:
        fail("reference_coverage")
    for ref in refs:
        subject = subjects[ref["subject_sha256"]]
        if ref["review_context_sha256"] != subject["review_context_sha256"]:
            fail("reference_context")
        value = indexed[ref["sha256"]]
        # Original M1 decisions are parsed by the original closed reader. Other
        # Package E request/review/receipt objects remain opaque pinned evidence,
        # never converted into approval or a new historical record kind.
        if ref["role"] == "exception":
            record = read_document(canonical(value), "record")
            if record.KIND not in {"logo-exception-request", "logo-preview-manifest", "submitter-confirmation", "maintainer-exception-decision"}:
                fail("exception_reference")
            review = record.to_dict()["context"]
            identities = {o["id"] for s in subjects.values() for o in s["outputs"]}
            if (review["package"] != subject["contract"] or review["variant"] != subject["variant"]
                    or review["material_context_sha256"] != subject["review_context_sha256"]
                    or subject["id"] not in review["identities"] or not set(review["identities"]) <= identities):
                fail("exception_scope")
        if type(value) is not dict:
            fail("reference_identity")
        if ref["role"] == "receipt" and "receipt_sha256" in value:
            # Existing Package E worker receipts use job_id/job_fingerprint,
            # not invented integer revisions. Check their native self-pin too;
            # this is integrity only, without artifact IO or ownership approval.
            if (value.get("job_id") != ref["id"] or value.get("job_fingerprint") != ref["revision"]
                    or value.get("logical_id") not in {o["id"] for o in subject["outputs"]}
                    or value["receipt_sha256"] != fingerprint({k:v for k,v in value.items() if k != "receipt_sha256"})):
                fail("receipt_reference")
        elif ref["role"] == "review" and "variant" in value:
            variant = value["variant"]
            if (type(variant) is not dict or variant.get("id") != ref["id"]
                    or variant.get("validation_fingerprint") != ref["revision"]
                    or variant.get("id") not in {o["id"] for o in subject["outputs"]}):
                fail("review_reference")
        elif value.get("id") != ref["id"] or value.get("revision") != ref["revision"]:
            fail("reference_identity")
    return refs


def _graph_scope(index, subject, package, request, current_package_pins):
    s = subject.to_dict()
    contract = package.contract.to_dict()
    variant = next(v for v in contract["variants"] if v["id"] == s["variant"])
    rules, members = package.data()
    member = members.get(s["id"])
    rows = []
    for output in s["outputs"]:
        row = index.outputs.get(output["id"])
        if row is None or any(row[k] != output[k] for k in ("local_path", "public_path")) or any(row[k] != s["contract"][k] for k in ("category", "kind")):
            fail("graph_output")
        if not set(row["companions"]) <= index.outputs.keys():
            fail("graph_companions")
        closure, pending = {}, [row["node"]]
        while pending:
            key = pending.pop()
            if key not in closure:
                closure[key] = index.nodes[key]
                pending.extend(index.nodes[key]["dependencies"])
        definition = closure.get("definition:"+s["id"])
        if definition is None or definition["sha256"] != s["expanded_definition_sha256"]:
            fail("graph_definition")
        historical_overlay = (type(request) is OverlayRequest
            and (package.contract.sha256, package.rules.sha256) in current_package_pins)
        if historical_overlay or row["context_sha256"] != s["review_context_sha256"]:
            # Historical overlays retain M6's {definition,job} review namespace
            # in M2. The unchanged M5 graph also binds identity, exceptions and
            # renderer. Verify their relationship from the exact pinned record;
            # neither context can substitute for the other or be normalized away.
            if type(request) is not OverlayRequest or member is None:
                fail("graph_review_context")
            from ..adoption.models import HistoricalOutput, read_canonical
            record = HistoricalOutput.from_bytes(request.record.encoded)
            value = record.to_dict()
            effective = read_canonical(value["effective_definition_json"])
            job = read_canonical(value["job_json"])
            member_context = fingerprint(dict(definition=effective, job=job))
            graph_context = fingerprint(dict(identity=value["identity"], definition=effective, job=job,
                exceptions=value["historical_exceptions"], renderer=value["baseline_renderer_sha256"]))
            if (record.sha256 != request.record_sha256 or record.sha256 != member["record_sha256"]
                    or value["identity"]["id"] != s["id"]
                    or member_context != s["review_context_sha256"] or member_context != member["context_sha256"]
                    or graph_context != row["context_sha256"] or closure[row["node"]]["sha256"] != graph_context):
                fail("graph_review_context")
            for source in job["inputs"]:
                node = closure.get("asset:"+source["path"])
                if node is None or node["sha256"] != source["sha256"]:
                    fail("graph_record_source")
            renderer = closure.get("transform:overlay")
            if renderer is None or renderer["sha256"] != value["baseline_renderer_sha256"]:
                fail("graph_record_renderer")
        if member is not None:
            if member["variant"] != s["variant"] or sorted(row["companions"]) != sorted(member["companions"]):
                fail("graph_member")
            for exception in member["exceptions"]:
                node = closure.get("exception:"+s["id"]+"/"+exception["code"])
                if node is None or node["sha256"] != exception["evidence_sha256"]:
                    fail("graph_exception")
        rows.append(dict(id=output["id"], material_sha256=index.material_context(output["id"]),
                         evidence=row["evidence"], companions=row["companions"]))
    return dict(contract_sha256=package.contract.sha256, rules_sha256=package.rules.sha256,
        variant=s["variant"], design_sha256=fingerprint(variant), rule_sha256=fingerprint(rules[s["variant"]]),
        exceptions_sha256=fingerprint(dict(variant=variant.get("exception_refs", []),
            member=member["exceptions"] if member else [])), member_sha256=fingerprint(member), outputs=rows)


def _m7(categories, packages, implementation, expected_release_sha256):
    # Actual closed release, not supplied compatibility JSON or a readiness bool.
    # inventory() with no audit explicitly retains fresh-audit and all approval
    # blockers. It cannot approve/activate even a synthetic compatible chain.
    from ..categories.release import Implementation, RELEASE_SHA256
    from ..activation.readiness import inventory
    from ..categories.release import Package
    from ..categories.models import Release, Rules
    from ..models import Contract
    if (type(implementation) is not Implementation or type(implementation.release) is not Release
            or implementation.release.sha256 != require_hash(expected_release_sha256) or expected_release_sha256 != RELEASE_SHA256):
        fail("m7_release_pin")
    release = Release.from_bytes(implementation.release.encoded).to_dict()
    # Reuse one explicitly loaded immutable inventory within this inspection
    # session, rather than reparsing all category documents per selected item.
    # It conveys no current compatibility/approval/authority assertion.
    if type(implementation.packages) is not tuple or len(implementation.packages) != len(release["entries"]):
        fail("m7_inventory")
    if any(type(p) is not Package or type(p.contract) is not Contract or type(p.rules) is not Rules for p in implementation.packages):
        fail("m7_inventory")
    pins = {(e["contract_sha256"],e["rules_sha256"]) for e in release["entries"]}
    actual = {(p.contract.sha256,p.rules.sha256) for p in implementation.packages if type(p) is Package}
    if actual != pins or len(actual) != len(implementation.packages):
        fail("m7_inventory")
    report = inventory(implementation)
    selected = [r for r in report["packages"] if r["category"] in categories]
    blockers = sorted({b for r in selected for b in r["blockers"]})
    for package in packages:
        actual = implementation.select(package.contract.to_dict()["category"])
        if (actual.contract.sha256, actual.rules.sha256) != (package.contract.sha256, package.rules.sha256):
            blockers.append("selected_package_not_current_m6_release")
    return dict(release_sha256=report["release_sha256"], review_registry_sha256=report["review_registry_sha256"],
        selectors=report["selectors"], variants=report["variants"], exact_approvals_missing=report["exact_approvals_missing"],
        ready=report["ready"], active=report["active"], selected=selected, blockers=sorted(set(blockers)))


def consume(inputs, language_policy, destination, destination_inputs, request_context, graph, *,
            expected_language_policy_sha256, expected_destination_sha256, expected_request_context_sha256,
            expected_graph_sha256, implementation, expected_release_sha256, references=(), cancel=None):
    """Consume current, explicitly provided evidence; never refresh or write it.

    Missing companions yield a bounded negative report. Malformed, substituted,
    stale or replayed supplied companions raise; no partial success is returned.
    """
    if (type(inputs) is not tuple or not inputs or len(inputs) > 20000
            or any(type(i) is not TranslationInput for i in inputs)):
        fail("inputs")
    if type(language_policy) is not LanguagePolicy or language_policy.sha256 != require_hash(expected_language_policy_sha256):
        fail("language_policy_pin")
    if type(request_context) is not RequestContext or request_context.sha256 != require_hash(expected_request_context_sha256):
        fail("request_head")
    context = RequestContext.from_bytes(request_context.encoded).to_dict()
    if type(graph) is not Snapshot:
        fail("graph_type")
    index = Snapshot.load(graph.encoded, expected_sha256=expected_graph_sha256).index()
    from ..categories.release import Implementation, RELEASE_SHA256
    from ..categories.models import Release
    if (type(implementation) is not Implementation or type(implementation.release) is not Release
            or implementation.release.sha256 != RELEASE_SHA256 or require_hash(expected_release_sha256) != RELEASE_SHA256):
        fail("m7_release_pin")
    current_package_pins = {(e["contract_sha256"], e["rules_sha256"]) for e in implementation.release.to_dict()["entries"]}
    blockers = ["m5_graph_unresolved"] if index.unresolved else []
    rows, bounds, packages, subjects = [], [], [], {}
    for item in inputs:
        if cancel is not None and cancel():
            fail("interrupted")
        if type(item.request) not in (PosterRequest, OverlayRequest):
            fail("request_type")
        subject = item.request.expand(language_policy.resolve(item.requested))[0]
        s = subject.to_dict()
        if subject.sha256 in subjects or s["id"] in {v["id"] for v in subjects.values()}:
            fail("duplicate_subject")
        subjects[subject.sha256] = s
        scope = _graph_scope(index, subject, item.request.package, item.request, current_package_pins)
        report = item.report
        if report is None:
            if item.expected_sha256 is not None:
                fail("missing_translation_pin")
            blockers.append("missing_m2:"+s["id"])
        else:
            report = replay_translation(report, expected_sha256=item.expected_sha256, request=item.request,
                policy=language_policy, requested=item.requested, snapshot=item.snapshot, selection=item.selection,
                context=item.context, verifier=item.verifier)
            bounds.append(BoundTranslation(subject, subject.sha256, report, report.sha256, item.request.package,
                item.request.contract_sha256, item.request.rules_sha256))
            blockers.extend("m2:"+s["id"]+":"+b for b in report.to_dict()["blockers"])
        rows.append(dict(subject_sha256=subject.sha256, subject_id=s["id"], language=s["language"], requested_language=item.requested,
            outputs=s["outputs"], expanded_definition_sha256=s["expanded_definition_sha256"], dependencies_sha256=s["dependencies_sha256"],
            review_context_sha256=s["review_context_sha256"], scope=scope,
            translation_sha256=report.sha256 if report else None, translation_dependency_sha256=report.to_dict()["dependency_sha256"] if report else None,
            selection_sha256=item.selection.sha256 if item.selection else None,
            source_context_sha256=fingerprint(item.context.__dict__) if item.context is not None else None))
        packages.append(item.request.package)
    if set(context["subjects"]) != set(subjects):
        fail("request_subjects")
    refs = _references(context, references, subjects)
    all_outputs = sorted([o for s in subjects.values() for o in s["outputs"]], key=lambda o: o["id"])
    if len({o["id"] for o in all_outputs}) != len(all_outputs) or len({s["language"] for s in subjects.values()}) != 1:
        fail("membership")
    output_ids = {o["id"] for o in all_outputs}
    if any(set(index.outputs[o]["companions"])-output_ids for o in output_ids):
        blockers.append("missing_graph_companions")
    current_destination = None
    if destination is None:
        if expected_destination_sha256 is not None:
            fail("missing_destination_pin")
        blockers.append("missing_m3")
    elif len(bounds) != len(inputs):
        fail("destination_without_m2")
    else:
        if type(destination) is not DestinationAttestation or type(destination_inputs) is not dict:
            fail("destination_type")
        # Current cohort is reconstructed by M4, never trusted from caller kwargs.
        selected = dict(destination_inputs)
        if "items" in selected or "language_policy" in selected:
            fail("destination_cohort_override")
        current_destination = replay_destination(destination, expected_sha256=expected_destination_sha256,
            items=tuple(bounds), language_policy=language_policy, **selected)
        blockers.extend("m3:"+b for b in current_destination.to_dict()["blockers"])
    # Even when M3 is missing, M6 complete membership must be checked when M2 is
    # available; no single standard/bigger or white/color output is eligible.
    if len(bounds) == len(inputs):
        blockers.extend("cohort:"+b for b in cohort(tuple(bounds), language_policy)[2])
    m7 = _m7({s["contract"]["category"] for s in subjects.values()}, packages, implementation, expected_release_sha256)
    chain = (len(bounds) == len(inputs) and current_destination is not None
        and not index.unresolved and "missing_graph_companions" not in blockers
        and all(i.report.to_dict()["technical_eligible"] for i in inputs)
        and current_destination.to_dict()["destination_checks_passed"] and current_destination.to_dict()["complete"])
    simulation = (any(i.report and i.report.to_dict()["currentness"] == "synthetic-current" for i in inputs)
        or bool(current_destination and current_destination.to_dict()["authority_status"] == "synthetic-only"))
    source_checks = all(i.report and i.report.to_dict()["currentness"] in {"not_applicable", "verified-current", "synthetic-current"} for i in inputs)
    simulated = bool(chain and simulation and source_checks and (
        current_destination.to_dict()["simulation_eligible"] or current_destination.to_dict()["policy_route"] == "private_only"))
    blockers.extend("m7:"+b for b in m7["blockers"])
    if refs:
        blockers.append("referenced_decisions_not_authenticated")
    if simulation:
        blockers.append("synthetic_evidence_is_not_authority")
    if cancel is not None and cancel():
        fail("interrupted")
    value = dict(schema_version=1, kind="evidence-consumption", version="1.0.0", stage="informational",
        request_context_sha256=request_context.sha256, request_id=context["id"], request_revision=context["revision"],
        language_policy=reference(language_policy), graph_snapshot_sha256=graph.sha256, graph_basis=graph.data()["basis"],
        subjects=sorted(rows, key=lambda r: r["subject_sha256"]), references=refs,
        output_membership_sha256=fingerprint(all_outputs), destination_sha256=current_destination.sha256 if current_destination else None,
        destination_dependency_sha256=current_destination.to_dict()["dependency_sha256"] if current_destination else None,
        m7=m7, chain_compatible=bool(chain), simulation=simulation, simulation_eligible=simulated,
        technical_eligible=False, blockers=sorted(set(blockers)), evaluation_complete=True,
        publication_authorized=False, production_enforcement=False, ready=False, active=False)
    value["binding_sha256"] = fingerprint({k: v for k, v in value.items() if k != "graph_snapshot_sha256"})
    return ConsumptionAttestation.from_dict(value)


def revalidate(attestation, *, expected_sha256, **current_inputs):
    if type(attestation) is not ConsumptionAttestation or attestation.sha256 != require_hash(expected_sha256):
        fail("attestation_pin")
    attestation = ConsumptionAttestation.from_bytes(attestation.encoded)
    current = consume(**current_inputs)
    # Only the independently pinned enclosing graph observation may change
    # without invalidation. Every selected closure/evidence/reference remains in
    # binding_sha256. Return the fresh observation, never mutate the old receipt.
    if current.to_dict()["binding_sha256"] != attestation.to_dict()["binding_sha256"]:
        fail("stale_consumption")
    return current
