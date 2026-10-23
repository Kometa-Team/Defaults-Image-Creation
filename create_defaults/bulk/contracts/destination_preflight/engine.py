"""Destination-only findings bound to M2; never combined readiness or a writer."""

import re
import unicodedata

from ...common import fingerprint, path_key
from ..language_policy import LanguagePolicy, DestinationPolicy, DestinationEvidence, reference
from ..registry import require_hash
from .authority import consume
from .bindings import cohort
from .inventory import expand
from .models import DestinationAttestation, DestinationInventory
from .paths import fail, safe_path, target_path, repository_key, overlaps, CollisionIndex


def evaluate(items, language_policy, policy, evidence, inventory, *, expected_policy_sha256,
             expected_evidence_sha256, expected_inventory_sha256, context=None, verifier=None, cancel=None):
    if type(language_policy) is not LanguagePolicy or type(policy) is not DestinationPolicy:
        fail("policy_type")
    if policy.sha256 != require_hash(expected_policy_sha256) or policy.to_dict()["language_policy"] != reference(language_policy):
        fail("policy_binding")
    records, outputs, blockers, missing_companions, cohort_sha = cohort(items, language_policy)
    language = records[0]["language"]
    public = [o for o in outputs if o["public_path"] is not None]
    if evidence is None:
        if (expected_evidence_sha256 is not None or expected_inventory_sha256 is not None or inventory is not None
                or public or context is not None or verifier is not None):
            fail("missing_destination_evidence")
        target, selected_mapping, flattened, missing_pages = None, None, {}, []
        auth_status, authority_ok, observed = "not_applicable", False, None
        inventory_status, route = "not_applicable", "private_only"
    else:
        if type(evidence) is not DestinationEvidence or evidence.sha256 != require_hash(expected_evidence_sha256):
            fail("evidence_pin")
        value, p = evidence.to_dict(), policy.to_dict()
        target = value["target"]
        primary = next((i.subject for i in items if reference(i.subject) == value["subject"]), None)
        if (primary is None or not any(o["public_path"] is not None for o in primary.to_dict()["outputs"])
                or value["destination_policy"] != reference(policy) or target["language"] != language):
            fail("destination_binding")
        paths = sorted(o["public_path"] for o in public)
        if target["paths"] != paths:
            fail("output_membership")
        for path in target["paths"]:
            safe_path(path)
        if target["root"] is not None:
            safe_path(target["root"])
        if re.search(r"%[0-9a-fA-F]{2}", target["branch"]):
            fail("encoded_branch")
        selected_mapping = next((m for m in p["mappings"] if m["language"] == language), None)
        if selected_mapping is None:
            blockers.append("destination_mapping_missing")
        elif (repository_key(selected_mapping["repository"]) != repository_key(target["repository"])
                or any(selected_mapping[k] != target[k] for k in ("language", "branch", "root", "paths"))):
            blockers.append("destination_mapping_conflict")
        official = p["official_repository"]
        is_official = target["repository"]["repository_id"] == official["repository_id"]
        route = "official_english" if is_official and language == "en" else "user_english" if language == "en" else "user_non_english"
        if is_official and target["repository"]["owner_id"] != official["owner_id"]:
            blockers.append("official_owner_changed")
        if is_official and language != "en":
            blockers.append("official_non_english_prohibited")
            route = "denied"
        if is_official and (target["branch"] != "master" or target["root"] is not None):
            blockers.append("official_mapping_changed")
        # Compare actual full targets as well as roots for mappings in this repo.
        for mapping in p["mappings"]:
            if mapping["language"] == language or mapping["repository"]["repository_id"] != target["repository"]["repository_id"]:
                continue
            if unicodedata.normalize("NFC", mapping["branch"]).casefold() == unicodedata.normalize("NFC", target["branch"]).casefold():
                if mapping["branch"] != target["branch"]:
                    blockers.append("ambiguous_branch_mapping")
                if overlaps(mapping["root"], target["root"]):
                    blockers.append("overlapping_language_roots")
                other_paths = {path_key(target_path(mapping["root"], path)) for path in mapping["paths"]}
                if other_paths & {path_key(target_path(target["root"], path)) for path in paths}:
                    blockers.append("cross_language_alias")
        flattened, missing_pages = {}, []
        if inventory is None:
            if expected_inventory_sha256 is not None:
                fail("inventory_pin")
            inventory_status = "unavailable"
            blockers.append("inventory_unavailable")
        else:
            if type(inventory) is not DestinationInventory or inventory.sha256 != require_hash(expected_inventory_sha256):
                fail("inventory_pin")
            inv = DestinationInventory.from_bytes(inventory.encoded).to_dict()
            if (inventory.sha256 != target["inventory_sha256"] or repository_key(inv["repository"]) != repository_key(target["repository"])
                    or (inv["branch"], inv["commit"], inv["tree"]) != (target["branch"], target["baseline_commit"], target["baseline_tree"])):
                fail("inventory_binding")
            flattened, missing_pages = expand(inv, cancel=cancel)
            inventory_status = "incomplete" if missing_pages else "integrity_verified"
            if missing_pages:
                blockers.append("inventory_incomplete")
        auth_status, authority_ok, observed = consume(evidence, policy, inventory, cohort_sha, context, verifier)
        if not authority_ok:
            blockers.append("authority:"+auth_status)
        # A synthetic observation is evidence of test execution only. M1 has no
        # real authorized result and no live provider is installed by M3.
        if authority_ok:
            blockers.append("authority:synthetic-only")
    rows = []
    proposed = [target_path(target["root"], o["public_path"]) for o in public] if target else []
    existing_index = CollisionIndex(flattened)
    proposed_index = CollisionIndex({path: {"mode": "100644"} for path in proposed})
    duplicate_keys = set()
    seen_keys = set()
    for path in proposed:
        key = path_key(path)
        if key in seen_keys:
            duplicate_keys.add(key)
        seen_keys.add(key)
    for output in outputs:
        if cancel is not None and cancel():
            fail("interrupted")
        path = target_path(target["root"], output["public_path"]) if target and output["public_path"] is not None else None
        diagnostics = existing_index.diagnostics(path) if path is not None else []
        if path is not None:
            if path_key(path) in duplicate_keys or set(proposed_index.diagnostics(path)) - {"existing_exact"}:
                diagnostics.append("proposed_collision")
            if diagnostics:
                blockers.append("output_collision:"+output["id"])
        rows.append(dict(output=output, target_path=path, status="private" if path is None else "blocked" if diagnostics else "clear",
                         diagnostics=sorted(set(diagnostics))))
    if cancel is not None and cancel():
        fail("interrupted")
    if len(rows) != len(outputs):
        fail("incomplete_coverage")
    content_blockers = sorted(set(b for b in blockers if not b.startswith("authority:")))
    complete = (not missing_companions and "unverified_companion_membership" not in blockers
                and (route == "private_only" or (inventory_status == "integrity_verified" and authority_ok)))
    return DestinationAttestation.from_dict(dict(schema_version=1, kind="destination-attestation", stage="informational", version="1.0.0",
        language=language, language_policy=reference(language_policy), destination_policy=reference(policy),
        destination_evidence=reference(evidence) if evidence else None,
        inventory_sha256=inventory.sha256 if inventory else None, cohort=records, cohort_sha256=cohort_sha,
        outputs=rows, output_membership_sha256=fingerprint(outputs), target=target,
        policy_route=route, authority_status=auth_status, verified_observation=observed,
        inventory_currentness="not_applicable" if target is None else "synthetic-only" if authority_ok else "unverifiable",
        repository_identity_status="not_applicable" if target is None else "synthetic-only" if authority_ok else "unverifiable",
        authority_context_sha256=fingerprint(context.__dict__) if context is not None else None,
        inventory_status=inventory_status, missing_tree_pages=missing_pages, missing_companions=missing_companions,
        inventory_entries=len(flattened), proposed_outputs=len(outputs), evaluated_outputs=len(rows),
        complete=complete, evaluation_complete=True, destination_checks_passed=not content_blockers,
        simulation_eligible=authority_ok and not content_blockers and complete,
        technical_eligible=False, blockers=sorted(set(blockers)),
        dependency_sha256=fingerprint(dict(cohort=records, outputs=rows, policy=reference(policy), target=target,
            inventory=inventory.sha256 if inventory else None, observation=observed,
            authority_status=auth_status, inventory_status=inventory_status, blockers=sorted(set(blockers)),
            context=fingerprint(context.__dict__) if context is not None else None)),
        publication_authorized=False, production_enforcement=False, ready=False, active=False))


def revalidate(attestation, *, expected_sha256, **selected_inputs):
    if type(attestation) is not DestinationAttestation or attestation.sha256 != require_hash(expected_sha256):
        fail("attestation_pin")
    replay = evaluate(**selected_inputs)
    if replay.encoded != attestation.encoded:
        fail("attestation_replay")
    return replay
