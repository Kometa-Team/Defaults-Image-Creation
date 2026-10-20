"""Version-bound publication planning. This module has no remote write adapter.

Approval receipts are externally supplied, attributed maintainer decisions. Like
the existing local Reviews service, hashes establish binding, not authentication.
Never create or accept a receipt on behalf of a maintainer.
"""
from .common import BulkError, fingerprint, path_key, relative_path
from .library_sources import check_seal, sealed

REVIEWERS = {"bullmoose20", "YozoraXCII", "chazlarson", "meisnate12", "badja-dev"}


def retained_overlay_decisions(inventory):
    """Reuse only the 64 recorded exact decisions with unchanged comparisons.

    This reads the original acceptance record; it creates no approval receipt,
    attributes no new reviewer decision, and cannot extend its membership.
    """
    if inventory.get("kind") != "overlays":
        return {}
    from .config import ROOT
    from .library_sources import load_json
    from .overlays import identity
    record = check_seal(load_json(ROOT / "bulk/evidence/package-e/maintainer-visual-acceptance-20261017.json"))
    decisions = {d["id"]: d for d in record["decisions"] if d["kind"] == "overlay"}
    retained = {}
    for row in inventory["rows"]:
        decision = decisions.get(row.get("id"))
        if not decision or not row.get("technical_valid") or row["difference_class"] == "blocked":
            continue
        if (decision["image_sha256"] == row["candidate_sha256"]
                and decision["render_fingerprint"] == row["render_fingerprint"]
                and decision["validation_fingerprint"] == row["validation_fingerprint"]
                and decision["historical_pixel_difference"]["legacy_sha256"] == row["published_sha256"]
                and decision["review_context"]["renderer"] == identity()
                and decision["policy_sha256"] == fingerprint(decision["review_context"]["policy"])):
            retained[row["destination"]] = {"record_sha256": record["sha256"], "decision_id": decision["id"],
                "original_receipt_sha256": decision["receipt_sha256"], "current_receipt_sha256": row["receipt_sha256"]}
    return retained


def validate_paths(members):
    seen = set()
    for member in members:
        path = relative_path(member["destination"])
        if any(part.casefold() == ".git" for part in path.split("/")) or not path.lower().endswith((".jpg", ".jpeg", ".png")):
            raise BulkError("unexpected_path", "Publication supports canonical public image paths only")
        key = path_key(path)
        if key in seen:
            raise BulkError("path_collision", "Duplicate/case-colliding publication path")
        seen.add(key)


def publication_manifest(inventory, policy, approvals=()):
    """Build the exact eligible plan; passing visual scores alone never qualifies."""
    check_seal(inventory)
    if fingerprint(policy) != inventory["policy_sha256"]:
        raise BulkError("stale_policy", "Policy differs from compared inventory")
    decisions = {}
    for receipt in approvals:
        check_seal(receipt)
        if (receipt.get("reviewer") not in REVIEWERS or receipt.get("decision") != "approved"
                or receipt.get("inventory_sha256") != inventory["sha256"]
                or receipt.get("baseline") != inventory["baseline"]
                or receipt.get("policy_sha256") != inventory["policy_sha256"]
                or receipt.get("membership_sha256") != fingerprint(receipt.get("members"))):
            raise BulkError("stale_approval", "Approval attribution, baseline, policy or membership binding differs")
        for member in receipt["members"]:
            if member["destination"] in decisions:
                raise BulkError("duplicate_approval", "Overlapping approval receipts require reconciliation")
            decisions[member["destination"]] = (receipt, member)
    expected = {r["destination"] for r in inventory["rows"]}
    if set(decisions) - expected:
        raise BulkError("unexpected_path", "Approval contains a destination outside inventory")
    retained = retained_overlay_decisions(inventory)
    members, withheld, exact = [], [], []
    for row in inventory["rows"]:
        if row["hash_state"] == "exact_match":
            if not row.get("candidate_sha256") or row["candidate_sha256"] != row.get("published_sha256"):
                raise BulkError("false_exact_match", "Only identical actual SHA-256 hashes can skip publication")
            exact.append(row["destination"])
            continue
        if row["destination"] in retained:
            _verify_candidate(row)
            preserved = retained[row["destination"]]
            members.append({"destination": row["destination"], "source": row["candidate_path"],
                "sha256": row["candidate_sha256"], "size": row["candidate_bytes"],
                "previous_sha256": row["published_sha256"], "difference_class": row["difference_class"],
                "context_sha256": row["context_sha256"], "approval_sha256": preserved["record_sha256"],
                "historical_decision_id": preserved["decision_id"],
                "original_receipt_sha256": preserved["original_receipt_sha256"],
                "current_receipt_sha256": preserved["current_receipt_sha256"]})
            continue
        supplied = decisions.get(row["destination"])
        if not supplied or not row["technical_valid"] or row["difference_class"] == "blocked":
            withheld.append({"destination": row["destination"], "reason": "blocked" if row["difference_class"] == "blocked" else "approval_required"})
            continue
        receipt, member = supplied
        binding = {k: row.get(k) for k in ("destination", "candidate_sha256", "published_sha256", "context_sha256")}
        if member != binding:
            raise BulkError("stale_approval", "Exact image/context hashes differ from approved membership")
        scope = receipt.get("scope")
        if scope == "renderer_equivalent":
            if (not receipt.get("policy_approved") or not row.get("tolerance", {}).get("screen_pass")
                    or row.get("font_change_expected") or row.get("layout_risks")
                    or row["difference_class"] not in {"renderer_equivalence_pending_policy", "renderer_equivalent"}):
                withheld.append({"destination": row["destination"], "reason": "font_layout_or_policy_review_required"})
                continue
            classification = "renderer_equivalent"
        elif scope in {"font_layout_group", "individual", "overlay_group"}:
            if scope != "individual" and row["difference_class"] in {"unexpected_difference", "layout_changed"}:
                withheld.append({"destination": row["destination"], "reason": "individual_exception_review_required"})
                continue
            if scope == "overlay_group" and row["kind"] != "overlay":
                raise BulkError("approval_scope", "Overlay approval contains a poster")
            if scope != "individual":
                from .library_visual import evaluate
                group_policy = receipt.get("group_policy")
                if (not receipt.get("policy_approved") or not group_policy
                        or receipt.get("group_policy_sha256") != fingerprint(group_policy)):
                    raise BulkError("group_policy", "Group approval requires exact approved automated bounds")
                if (not row.get("metrics") or not evaluate(row["metrics"], group_policy)["screen_pass"]
                        or set(row.get("layout_risks", [])) - set(receipt.get("accepted_layout_warnings", []))):
                    withheld.append({"destination": row["destination"], "reason": "outside_approved_group_bounds"})
                    continue
            classification = row["difference_class"]
        else:
            raise BulkError("approval_scope", "Explicit renderer, font/layout, overlay or individual scope required")
        if not row.get("candidate_path"):
            raise BulkError("missing_candidate", "Eligible candidate has no exact output path")
        _verify_candidate(row)
        members.append({"destination": row["destination"], "source": row["candidate_path"],
                        "sha256": row["candidate_sha256"], "size": row["candidate_bytes"],
                        "previous_sha256": row["published_sha256"], "difference_class": classification,
                        "context_sha256": row["context_sha256"], "approval_sha256": receipt["sha256"]})
    members.sort(key=lambda r: r["destination"])
    validate_paths(members)
    return sealed({"schema_version": 1, "kind": "approved-library-publication-manifest",
        "inventory_sha256": inventory["sha256"], "baseline": inventory["baseline"],
        "policy_sha256": inventory["policy_sha256"], "members": members,
        "withheld": withheld, "exact_matches_skipped": exact,
        "remote_writes_authorized": False, "merge_authorized": False})


def _verify_candidate(row):
    from pathlib import Path
    from .common import reject_links, sha256
    path = reject_links(row["candidate_path"])
    if sha256(path) != row["candidate_sha256"] or Path(path).stat().st_size != row["candidate_bytes"]:
        raise BulkError("stale_candidate", "Approved candidate bytes changed before publication planning")


def batch_plan(manifest, *, max_files=300, max_bytes=200 * 1024 ** 2):
    check_seal(manifest)
    if manifest.get("kind") != "approved-library-publication-manifest":
        raise BulkError("unapproved_manifest", "Transport requires the approved publication manifest format")
    if type(max_files) is not int or type(max_bytes) is not int or min(max_files, max_bytes) < 1:
        raise BulkError("batch_limits", "Positive file and byte caps required")
    validate_paths(manifest["members"])
    batches, current, size = [], [], 0
    for member in sorted(manifest["members"], key=lambda r: r["destination"]):
        if member["size"] > max_bytes:
            raise BulkError("batch_oversize", "Single image exceeds byte cap; explicit cap adjustment required")
        if current and (len(current) == max_files or size + member["size"] > max_bytes):
            batches.append({"members": current, "bytes": size})
            current, size = [], 0
        current.append(member)
        size += member["size"]
    if current:
        batches.append({"members": current, "bytes": size})
    return sealed({"schema_version": 1, "kind": "local-git-batch-plan", "baseline": manifest["baseline"],
                   "publication_manifest_sha256": manifest["sha256"], "max_files": max_files, "max_bytes": max_bytes,
                   "max_pack_bytes": max_bytes + max_bytes // 4 + 1024 * 1024,
                   "batches": [dict(b, sequence=i + 1, membership_sha256=fingerprint(b["members"])) for i, b in enumerate(batches)],
                   "remote_writes_authorized": False})


def verify_published(manifest, actual_paths, baseline):
    """Hash actual downloaded remote bytes. A visually identical mismatch fails."""
    from .common import sha256
    check_seal(manifest)
    results = []
    for member in manifest["members"]:
        path = actual_paths.get(member["destination"])
        actual = sha256(path) if path else None
        results.append({"destination": member["destination"], "expected_sha256": member["sha256"],
                        "actual_sha256": actual, "verified": actual == member["sha256"]})
    return sealed({"baseline": baseline, "manifest_sha256": manifest["sha256"], "results": results,
                   "passed": all(r["verified"] for r in results)})
