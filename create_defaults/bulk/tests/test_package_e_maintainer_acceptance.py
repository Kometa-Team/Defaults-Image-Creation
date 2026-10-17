"""Portable integrity checks for the maintainer's exact inspected sample decisions."""
import json
from pathlib import Path

from create_defaults.bulk.common import fingerprint

EVIDENCE = Path(__file__).resolve().parents[1] / "evidence/package-e"


def load(name):
    value = json.loads((EVIDENCE / name).read_text(encoding="utf-8"))
    assert value["sha256"] == fingerprint({k: v for k, v in value.items() if k != "sha256"})
    return value


def test_acceptance_matches_exact_presented_samples_and_preserves_history():
    accepted = load("maintainer-visual-acceptance-20261017.json")
    events = load("maintainer-visual-acceptance-20261017-events.json")
    original = load("pending-overlay-review.json")
    fitting = load("fitting-proposals.json")
    metrics = load("overlay-profile-risk.json")["evidence"]["comparisons"]
    assert events["acceptance_record_sha256"] == accepted["sha256"]
    for name, identity in accepted["historical_evidence"].items():
        assert load(name)["sha256"] == identity["envelope_sha256"]
    assert original["batch"]["inspected"] == [] and original["approval_events"] == 0
    overlay_decisions = {d["id"]: d for d in accepted["decisions"] if d["kind"] == "overlay"}
    poster_decisions = {d["id"]: d for d in accepted["decisions"] if d["kind"] == "poster"}
    assert len(overlay_decisions) == 64 and len(poster_decisions) == 6
    assert set(overlay_decisions) == {m["id"] for m in original["batch"]["members"]}
    assert set(poster_decisions) == {p["id"] for p in fitting["evidence"]["proposals"]}
    by_id = {m["id"]: m for m in metrics}
    for member in original["batch"]["members"]:
        decision = overlay_decisions[member["id"]]
        assert (decision["image_sha256"], decision["validation_fingerprint"], decision["policy_sha256"]) == (member["image_sha256"], member["validation"], member["policy"])
        assert decision["historical_pixel_difference"] == by_id[member["id"]]
    for proposal in fitting["evidence"]["proposals"]:
        decision = poster_decisions[proposal["id"]]
        context = proposal["exact_review_context"]
        assert decision["image_sha256"] == context["image_sha256"]
        assert decision["review_context"] == context["revision"]
        assert decision["proposal_sha256"] == proposal["proposal_sha256"]
        assert decision["measurement"] == proposal["measurement"]
        assert decision["layout_accepted"] and not decision["layout_activated"]
        assert not decision["current_policy_approval_transferred"]
    batch = events["inspected_overlay_batch"]
    assert set(batch["inspected"]) == set(overlay_decisions)
    actual = [e for e in events["overlay_service_events"] if e["kind"] == "review_approve"]
    assert len(actual) == 64 and {e["subject"] for e in actual} == set(overlay_decisions)
    for event in actual:
        decision = overlay_decisions[event["subject"]]
        payload = event["payload"]
        assert payload["decision_type"] == "individual"
        assert payload["preview"]["sha256"] == decision["image_sha256"]
        assert payload["validation"] == decision["validation_fingerprint"]
        assert set(payload["accepted_warnings"]) == set(decision["accepted_warnings"])
    external = [e for e in events["external_sample_and_mapping_events"] if e["kind"] == "review_external_sample_acceptance"]
    assert len(external) == 70
    assert {e["subject"] for e in external} == set(overlay_decisions) | set(poster_decisions)
    assert all(e["payload"]["acceptance_record_sha256"] == accepted["sha256"] for e in external)
    assert events["current_language_policy_approvals_created"] == events["catalog_layouts_activated"] == 0
    assert not accepted["scope"]["publication_authorized"]
    assert not accepted["scope"]["production_cutover_authorized"]
    assert accepted["scope"]["unreviewed_variants_approved"] == 0
