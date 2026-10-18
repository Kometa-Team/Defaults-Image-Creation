"""Exact image/context acceptance is separate from any target write authorization."""
import json
from pathlib import Path

from create_defaults.bulk.common import fingerprint

EVIDENCE = Path(__file__).resolve().parents[1] / "evidence/english-canary"


def load(name):
    value = json.loads((EVIDENCE / name).read_text(encoding="utf-8"))
    assert value["sha256"] == fingerprint({k:v for k,v in value.items() if k != "sha256"})
    return value


def test_seven_individual_approvals_bind_original_canary_bytes_and_context():
    accepted = load("visual-acceptance-20261017.json")
    audit = load("visual-acceptance-20261017-events.json")
    prepared = load("preparation-20261017.json")
    bundle = load("bundle-index-20261017.json")
    assert accepted["preparation_sha256"] == prepared["sha256"] == bundle["preparation_sha256"]
    assert accepted["bundle_archive_sha256"] == bundle["archive_sha256"]
    assert accepted["gallery"]["file_sha256"] == bundle["inventory"]["review.html"]["sha256"]
    assert accepted["gallery"]["all_seven_candidates_verified_against_report_gallery_and_archive"]
    assert accepted["published_comparison_snapshot"] == prepared["published_snapshot"]
    assert audit["acceptance_record_sha256"] == accepted["sha256"]
    rows = {r["id"]:r for r in prepared["rows"]}
    decisions = {d["id"]:d for d in accepted["decisions"]}
    assert len(accepted["decisions"]) == len(decisions) == len(rows) == 7
    assert set(decisions) == set(rows)
    assert set(audit["batch"]["inspected"]) == set(rows)
    assert audit["batch"]["membership"] == fingerprint(audit["batch"]["members"])
    assert {m["id"] for m in audit["batch"]["members"]} == set(rows)
    approvals = [e for e in audit["events"] if e["kind"] == "review_approve"]
    assert len(approvals) == 7 and {e["subject"] for e in approvals} == set(rows)
    for identity,decision in decisions.items():
        row = rows[identity]
        assert decision["language"] == "en"
        assert decision["image_sha256"] == row["sha256"]
        assert decision["image_bytes"] == row["bytes"]
        assert decision["destination"] == row["destination"]
        assert decision["render_fingerprint"] == row["render_fingerprint"]
        assert decision["validation_fingerprint"] == row["validation_fingerprint"]
        assert decision["accepted_published_comparison"] == row["published"]
        assert decision["parameters"] == row["parameters"]
        assert decision["inputs"] == row["inputs"]
        assert decision["dependencies"] == row["dependencies"]
        assert decision["layout_evidence"] == row["layout_evidence"]
        context = decision["review_context"]
        assert context["renderer"] == prepared["renderer"]
        assert context["preflight_sha256"] == prepared["preflight_sha256"]
        assert context["policy"] == decision["validation_policy"] == prepared["validation_policy"]
        assert fingerprint(context["policy"]) == decision["policy_sha256"]
        assert context["variant"]["validation_fingerprint"] == row["validation_fingerprint"]
        warnings = {d["code"] for d in context["variant"]["diagnostics"] if d["severity"] == "warning"}
        assert set(decision["accepted_warning_codes"]) == warnings
        event = next(e["payload"] for e in approvals if e["subject"] == identity)
        assert event["decision_type"] == "individual"
        assert event["version"] == decision["reviewed_version"] + 1
        assert event["validation"] == row["validation_fingerprint"]
        assert event["policy"] == decision["policy_sha256"]
        assert event["preview"]["sha256"] == row["sha256"]
        assert event["preview"]["render_fingerprint"] == row["render_fingerprint"]
        assert set(event["accepted_warnings"]) == warnings
        assert accepted["sha256"] in event["comment"]
    # Original preparation/gallery/archive identities and pending labels remain history.
    assert all(r["publication_decision"] == "pending_explicit_canary_artifact_acceptance" for r in rows.values())


def test_visual_acceptance_does_not_authorize_staging_or_production():
    accepted = load("visual-acceptance-20261017.json")
    audit = load("visual-acceptance-20261017-events.json")
    authorization = accepted["authorization"]
    assert authorization["visual_acceptance_of_enumerated_images"] is True
    assert all(value is False for key,value in authorization.items() if key != "visual_acceptance_of_enumerated_images")
    assert audit["individual_approvals_created"] == 7
    assert audit["group_approvals_created"] == audit["default_images_writes"] == 0
    assert audit["production_authorized"] is False
    assert not any(e["kind"] == "review_group_approve" for e in audit["events"])
    summary = [e for e in audit["events"] if e["kind"] == "review_canary_visual_acceptance_recorded"]
    assert len(summary) == 1
    assert summary[0]["payload"]["authorization"] == authorization
