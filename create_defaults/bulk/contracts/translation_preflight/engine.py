"""Deterministic metadata-only evaluation; no READY/ACTIVE or write interface."""

import hashlib

from ...common import BulkError, canonical, fingerprint
from ...translations import Translations
from ..language_policy import LanguagePolicy, TranslationSelection, reference
from ..language_policy import SourceVerificationContext
from ..registry import require_hash
from .adapters import PosterRequest, OverlayRequest, fail
from .models import TranslationPreflight
from .sources import lookup, value_traces, currentness


def prepare(request, policy, requested):
    if type(request) not in (PosterRequest, OverlayRequest) or type(policy) is not LanguagePolicy:
        fail("request_type")
    language = policy.resolve(requested)
    vs, definition, dependencies, caption, applicable, allowed, caption_allowed = request.expand(language)
    keys = {}
    if applicable and caption["mode"] == "translation":
        for role, key in (("caption", caption["key"]), ("template", caption["template_key"])):
            if key:
                lookup({}, key)  # Bound/validate legacy dot-separated syntax.
                keys.setdefault(key, []).append(role)
    keys = {key: sorted(roles) for key, roles in sorted(keys.items())}
    coverage = any(row["package"] == vs.to_dict()["contract"] and row["variant"] == request.variant
                   and language in row["languages"] for row in policy.to_dict()["coverage"])
    return vs, definition, dependencies, caption, applicable, allowed and coverage, caption_allowed, keys


def key_value(resources, language, key, roles):
    status, data, path, source_hash = resources.get(language, ("resource_unavailable", None, None, None))
    found, value, actual = lookup(data, key) if status == "available" else (False, None, None)
    if status == "available":
        if not found:
            status = "missing"
        elif type(value) is not str or not value.strip() or len(value) > 16384:
            status = "invalid_translation"
        elif "TRANSLATION NOT FOUND" in value or (("<<" in value or ">>" in value) and "template" not in roles):
            status = "unresolved_placeholder"
    return dict(language=language, key=key, roles=roles, status=status, resource_path=path,
        source_sha256=source_hash, actual_key=actual, value=value if type(value) is str else None,
        raw_json=canonical(value).decode("utf8") if found else None,
        value_sha256=fingerprint(value) if found else None)


def evaluate(request, policy, requested, snapshot, selection, *, context=None, verifier=None, cancel=None):
    """Complete evaluation only. Bound violations/interruption produce no evidence.

    Source checks/aliases/contract pins are independent of raw YAML intake.
    A caller supplies the selected M1 evidence; it must match actual enumeration,
    provenance and bytes. A matching JSON claim alone never verifies currentness.
    """
    if context is not None and type(context) is not SourceVerificationContext:
        fail("source_context_type")
    vs, definition, dependencies, caption, applicable, allowed, caption_allowed, keys = prepare(request, policy, requested)
    language = policy.resolve(requested)
    records, snapshot_pin, source = snapshot.selected(["en", language] if keys else [])
    resources = snapshot.values(records)
    raw_resources = dict(snapshot.resources)
    observations = [dict(language=code, resource_path=row.get("resource"), declared_sha256=row.get("sha256"),
        observed_sha256=hashlib.sha256(raw_resources[row["resource"]]).hexdigest()
        if type(raw_resources.get(row.get("resource"))) is bytes else None,
        status=resources[code][0]) for code, row in sorted(records.items())]
    expected_values = value_traces(resources, keys, language)
    if source["resources"]:
        if type(selection) is not TranslationSelection:
            fail("selection_required")
        ts = selection.to_dict()
        expected = dict(language_policy=reference(policy), subject=reference(vs), requested_language=requested,
                        language=language, snapshot_sha256=snapshot_pin, source=source, values=expected_values)
        if any(ts[k] != v for k, v in expected.items()):
            fail("selection_binding")
    elif selection is not None:
        fail("unexpected_selection")
    freshness = currentness(selection, context, verifier) if selection is not None else ("not_applicable" if not keys else "unverifiable")
    blockers, rows = [], []
    if not applicable:
        blockers.append("definition_not_applicable")
    if not allowed:
        blockers.append("contract_language_not_permitted")
    if not caption_allowed:
        blockers.append("effective_definition_outside_contract")
    for key, roles in keys.items():
        for code in sorted({"en", language}):
            if cancel is not None and cancel():
                fail("incomplete")
            row = key_value(resources, code, key, roles)
            row["provenance_status"] = freshness
            if row["status"] != "available":
                blockers.append(code+":"+key+":"+row["status"])
            rows.append(row)
    # Reuse the legacy resolver on these exact parsed bytes. It records reviewed
    # fallback/casing/template/suffix history, never rescues a missing required row.
    translations = object.__new__(Translations)
    translations.sources = {k: r[1] for k, r in resources.items() if r[0] == "available"}
    translations.hashes = {k: r[3] for k, r in resources.items() if r[0] == "available"}
    translations.failures = {k: ("unavailable_translation", "Selected resource unavailable") for k, r in resources.items() if r[0] != "available"}
    resolved, trace, resolution_error = None, "[]", None
    if applicable:
        try:
            result = translations.resolve(caption, language)
            resolved, trace = result.text, canonical(result.trace).decode("utf8")
        except BulkError as error:
            resolution_error = error.code
            blockers.append("caption_resolution:"+error.code)
    if cancel is not None and cancel():
        fail("incomplete")
    technical = not blockers
    if freshness not in {"verified-current", "not_applicable"}:
        blockers.append("source_currentness:"+freshness)
    # Content impact is scoped: exact used resource bytes (not key-only), values,
    # contract, effective definition and review context. Global commit movement
    # is separately retained by immutable observation and explicit reverification.
    material = {"subject": reference(vs), "policy": reference(policy), "keys": keys,
                "rows": [{k: v for k, v in row.items() if k != "provenance_status"} for row in rows],
                "repository": source["repository"], "resources": source["resources"], "resource_observations": observations,
                "definition_dependencies": dependencies}
    value = dict(schema_version=1, kind="translation-preflight", stage="informational", version="1.0.0",
        subject=vs.to_dict(), language_policy=reference(policy), translation_selection=reference(selection) if selection else None,
        requested_language=requested, language=language, snapshot_sha256=snapshot_pin, source=source,
        resource_observations=observations,
        effective_definition_sha256=fingerprint(definition), definition_dependencies_json=canonical(dependencies).decode("utf8"),
        required_keys=[dict(key=k, roles=v) for k, v in keys.items()], results=rows,
        required_row_count=len(keys)*len({"en", language}), evaluated_row_count=len(rows),
        key_status="applicable" if keys else "not_applicable", complete=True,
        currentness=freshness, technical_eligible=technical, translation_eligible=technical and not blockers,
        resolved_caption=resolved, legacy_trace_json=trace, resolution_error=resolution_error,
        fallback_json=canonical(caption["fallback"]).decode("utf8"),
        dependency_sha256=fingerprint(material), blockers=sorted(set(blockers)),
        verification_context_sha256=fingerprint(context.__dict__) if context is not None else None,
        independent_checks=["contract-approval", "destination", "font-glyphs", "layout", "logo", "visual-review"],
        publication_authorized=False, production_enforcement=False, ready=False, active=False)
    return TranslationPreflight.from_dict(value)


def revalidate(report, *, expected_sha256, request, policy, requested, snapshot, selection, context=None, verifier=None):
    """Exact replay under explicitly selected inputs, never an ambient refresh.

    A trusted caller must select the expected immutable hash. Structural loading
    alone is not validation; even a rehashed forgery fails this full recomputation.
    """
    if type(report) is not TranslationPreflight or report.sha256 != require_hash(expected_sha256):
        fail("report_pin")
    observed = evaluate(request, policy, requested, snapshot, selection, context=context, verifier=verifier)
    if observed.encoded != report.encoded:
        fail("report_replay")
    return observed
