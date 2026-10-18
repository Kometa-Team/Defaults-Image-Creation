"""Library synchronization, approval boundary and offline recovery regressions."""
from copy import deepcopy
import hashlib
from pathlib import Path
import subprocess

import pytest
from PIL import Image, ImageDraw

from create_defaults.bulk.common import BulkError, fingerprint, sha256
from create_defaults.bulk.library_publication import batch_plan, publication_manifest, verify_published
from create_defaults.bulk.library_sources import sealed
from create_defaults.bulk.library_sync import classify_difference, deterministic_samples, font_impacts
from create_defaults.bulk.library_transport import git, run
from create_defaults.bulk.library_visual import PROPOSED_POLICY, compare_images, evaluate


def inventory(tmp_path):
    source = tmp_path / "python.jpg"
    source.write_bytes(b"python" * 108333 + b"xx")
    row = {"destination": "genre/Example.jpg", "candidate_path": str(source),
           "candidate_sha256": sha256(source), "candidate_bytes": source.stat().st_size,
           "published_sha256": hashlib.sha256(b"legacy" * 116666 + b"xxxx").hexdigest(),
           "context_sha256": "context", "hash_state": "unequal", "technical_valid": True,
           "difference_class": "renderer_equivalence_pending_policy", "kind": "poster",
           "tolerance": {"screen_pass": True}, "layout_risks": []}
    return sealed({"schema_version": 1, "baseline": {"head": "a" * 40},
                   "policy_sha256": fingerprint(PROPOSED_POLICY), "rows": [row]})


def approve(report, **kwargs):
    members = [{k: r.get(k) for k in ("destination", "candidate_sha256", "published_sha256", "context_sha256")} for r in report["rows"]]
    return sealed(dict({"reviewer": "bullmoose20", "decision": "approved", "scope": "renderer_equivalent",
        "inventory_sha256": report["sha256"], "baseline": report["baseline"], "policy_sha256": report["policy_sha256"],
        "policy_approved": True, "members": members, "membership_sha256": fingerprint(members)}, **kwargs))


def reseal(value):
    value.pop("sha256", None)
    return sealed(value)


def test_650kb_equivalent_candidate_replaces_700kb_legacy(tmp_path):
    report = inventory(tmp_path)
    manifest = publication_manifest(report, PROPOSED_POLICY, [approve(report)])
    assert len(manifest["members"]) == 1
    assert manifest["members"][0]["difference_class"] == "renderer_equivalent"
    assert manifest["members"][0]["sha256"] == report["rows"][0]["candidate_sha256"]
    assert manifest["members"][0]["size"] == 650000
    assert not manifest["remote_writes_authorized"]
    assert len(batch_plan(manifest)["batches"]) == 1


def test_numerical_equivalence_does_not_approve(tmp_path):
    report = inventory(tmp_path)
    manifest = publication_manifest(report, PROPOSED_POLICY)
    assert not manifest["members"]
    assert len(manifest["withheld"]) == 1


def test_unapproved_policy_receipt_withholds(tmp_path):
    report = inventory(tmp_path)
    manifest = publication_manifest(report, PROPOSED_POLICY, [approve(report, policy_approved=False)])
    assert not manifest["members"]


@pytest.mark.parametrize("field,value", [("inventory_sha256", "stale"), ("baseline", {"head": "b" * 40}),
                                        ("policy_sha256", "stale"), ("reviewer", "unrecognized"),
                                        ("membership_sha256", "stale")])
def test_stale_approval_rejected(tmp_path, field, value):
    report = inventory(tmp_path)
    with pytest.raises(BulkError, match="binding differs"):
        publication_manifest(report, PROPOSED_POLICY, [approve(report, **{field: value})])


@pytest.mark.parametrize("field,value", [("candidate_sha256", "changed"), ("published_sha256", "changed"),
                                        ("context_sha256", "changed")])
def test_artifact_and_context_drift_rejected(tmp_path, field, value):
    report = inventory(tmp_path)
    decision = approve(report)
    decision["members"][0][field] = value
    decision["membership_sha256"] = fingerprint(decision["members"])
    decision = reseal(decision)
    with pytest.raises(BulkError, match="image/context"):
        publication_manifest(report, PROPOSED_POLICY, [decision])


@pytest.mark.parametrize("field,value", [("font_change_expected", True), ("layout_risks", ["clipped_caption"]),
                                        ("difference_class", "layout_changed"), ("technical_valid", False),
                                        ("difference_class", "blocked")])
def test_tolerance_never_bypasses_font_layout_or_blockers(tmp_path, field, value):
    report = inventory(tmp_path)
    report["rows"][0][field] = value
    report = reseal(report)
    assert not publication_manifest(report, PROPOSED_POLICY, [approve(report)])["members"]


def test_exact_match_skips_and_unchanged_rerun(tmp_path):
    report = inventory(tmp_path)
    report["rows"][0].update(hash_state="exact_match", difference_class="exact_match",
                             published_sha256=report["rows"][0]["candidate_sha256"])
    report = reseal(report)
    for _ in range(2):
        manifest = publication_manifest(report, PROPOSED_POLICY)
        assert not manifest["members"]
        assert manifest["exact_matches_skipped"] == ["genre/Example.jpg"]


def test_equivalent_bytes_cannot_be_marked_exact(tmp_path):
    report = inventory(tmp_path)
    report["rows"][0]["hash_state"] = "exact_match"
    with pytest.raises(BulkError, match="identical actual SHA-256"):
        publication_manifest(reseal(report), PROPOSED_POLICY)


def test_candidate_mutation_before_manifest_is_rejected(tmp_path):
    report = inventory(tmp_path)
    Path(report["rows"][0]["candidate_path"]).write_bytes(b"mutated")
    with pytest.raises(BulkError, match="candidate bytes changed"):
        publication_manifest(report, PROPOSED_POLICY, [approve(report)])


def test_remote_bytes_must_match_even_when_visually_identical(tmp_path):
    report = inventory(tmp_path)
    manifest = publication_manifest(report, PROPOSED_POLICY, [approve(report)])
    wrong = tmp_path / "remote.jpg"
    wrong.write_bytes(b"wrong encoding")
    assert not verify_published(manifest, {"genre/Example.jpg": wrong}, {"head": "new"})["passed"]
    assert verify_published(manifest, {"genre/Example.jpg": Path(report["rows"][0]["candidate_path"])}, {"head": "new"})["passed"]


def test_decoded_identical_binary_different_images(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    image = Image.new("RGB", (100, 150), "navy")
    image.save(a, compress_level=0)
    image.save(b, compress_level=9)
    assert sha256(a) != sha256(b)
    metrics = compare_images(a, b)
    assert metrics["rgb_mae"] == 0
    assert evaluate(metrics, PROPOSED_POLICY)["screen_pass"]
    assert not evaluate(metrics, PROPOSED_POLICY)["approval_granted"]


def test_transparent_white_artwork_is_measured_on_black_and_white(tmp_path):
    a, b = tmp_path / "art.png", tmp_path / "missing.png"
    image = Image.new("RGBA", (100, 150))
    ImageDraw.Draw(image).rectangle((20, 20, 80, 100), fill="white")
    image.save(a)
    Image.new("RGBA", image.size).save(b)
    metrics = compare_images(a, b)
    assert metrics["regions"]["logo"]["rgb_mae"] > 0
    assert {r["background"] for r in metrics["composites"]} == {0, 255}


def test_geometry_diagnostics_preserve_original_measurements(tmp_path):
    from create_defaults.bulk.library_visual import geometry_diagnostics
    a, b = tmp_path / "shifted.png", tmp_path / "original.png"
    original = Image.new("RGB", (100, 150), "black")
    ImageDraw.Draw(original).rectangle((25, 30, 65, 75), fill="white")
    original.save(b)
    shifted = Image.new("RGB", original.size, "black")
    shifted.paste(original, (3, 0))
    shifted.save(a)
    geometry = geometry_diagnostics(a, b)
    assert not geometry["alignment_applied"]
    assert geometry["regions"]["logo"]["bounded_projection_shift"]["x"]["candidate_shift_pixels"] == 3
    assert compare_images(a, b)["rgb_mae"] > 0


def test_tagged_colorspace_requires_review_even_when_raw_rgb_matches(tmp_path):
    from PIL import ImageCms
    a, b = tmp_path / "plain.png", tmp_path / "tagged.png"
    image = Image.new("RGB", (30, 40), "navy")
    image.save(a)
    image.save(b, icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    row = inventory(tmp_path)["rows"][0]
    row["metrics"] = compare_images(a, b)
    assert row["metrics"]["rgb_mae"] == 0
    assert classify_difference(row) == "unexpected_difference"


@pytest.mark.parametrize("defect", ["missing_logo", "changed_text", "color", "geometry", "clipping", "aspect", "alpha"])
def test_negative_controls_reject(tmp_path, defect):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    image = Image.new("RGBA", (100, 150), "navy")
    draw = ImageDraw.Draw(image)
    draw.rectangle((25, 20, 75, 70), fill="white")
    draw.text((20, 100), "APPROVED", fill="yellow")
    image.save(a)
    altered = image.copy()
    draw = ImageDraw.Draw(altered)
    if defect == "missing_logo": draw.rectangle((25, 20, 75, 70), fill="navy")
    if defect == "changed_text": draw.rectangle((10, 90, 90, 120), fill="red")
    if defect == "color": altered = Image.new("RGBA", image.size, "green")
    if defect == "geometry": altered.paste(image, (12, 0))
    if defect == "clipping": draw.rectangle((0, 40, 100, 150), fill="navy")
    if defect == "aspect": altered = altered.resize((90, 150))
    if defect == "alpha": altered.putalpha(128)
    altered.save(b)
    assert not evaluate(compare_images(b, a), PROPOSED_POLICY)["screen_pass"]


def test_sampling_is_order_independent_and_selects_extrema():
    rows = [{"destination": f"genre/{i}.jpg", "caption": "W" * i, "font_size": 100 + i,
             "metrics": {"rgb_mae": i}, "layout_risks": []} for i in range(20)]
    left = deterministic_samples(rows)
    assert left == deterministic_samples(list(reversed(rows)))
    assert {"genre/0.jpg", "genre/19.jpg"}.issubset({r["destination"] for r in left})


def test_historical_wrap_warning_does_not_claim_a_changed_layout(tmp_path):
    row = inventory(tmp_path)["rows"][0]
    row["layout_risks"] = ["wrapped_caption"]
    row["metrics"] = {"same_dimensions": True}
    assert classify_difference(row) == "renderer_equivalence_pending_policy"
    row["metrics"]["same_dimensions"] = False
    assert classify_difference(row) == "layout_changed"


def test_font_substitution_follows_generated_parent_and_grandchild(tmp_path):
    rows = [
        {"job": {"id": "year-2020", "parameters": {"font": "fonts/PlusJakartaSans-Bold.ttf", "text": "2020"}, "dependencies": []}},
        {"job": {"id": "year-best-2020", "parameters": {"font": "fonts/Comfortaa-Medium.ttf", "text": "BEST OF 2020"},
                 "dependencies": [{"job_id": "year-2020"}]}},
        {"job": {"id": "grandchild", "parameters": {"font": "fonts/Comfortaa-Medium.ttf", "text": "BEST"},
                 "dependencies": [{"job_id": "year-best-2020"}]}},
    ]
    impacts = font_impacts(rows)
    assert impacts["year-best-2020"]["direct_fonts"] == []
    assert impacts["year-best-2020"]["inherited_fonts"] == ["fonts/PlusJakartaSans-Bold.ttf"]
    assert impacts["grandchild"]["all_fonts"] == ["fonts/PlusJakartaSans-Bold.ttf"]
    report = inventory(tmp_path)
    report["rows"][0]["font_change_expected"] = bool(impacts["year-best-2020"]["all_fonts"])
    report = reseal(report)
    assert not publication_manifest(report, PROPOSED_POLICY, [approve(report)])["members"]


def test_font_dependency_cycle_is_blocked():
    rows = [{"job": {"id": "cycle", "parameters": {}, "dependencies": [{"job_id": "cycle"}]}}]
    with pytest.raises(BulkError, match="cyclic"):
        font_impacts(rows)


def test_reconciliation_preserves_original_evidence_and_outstanding_mismatch(tmp_path):
    from create_defaults.bulk.library_report import reconcile
    report = inventory(tmp_path)
    report["kind"] = "english"
    row = report["rows"][0]
    row.update(difference_class="layout_changed", category="Genre", font="Comfortaa",
               publication_eligible=False, layout_risks=["wrapped_caption"], metrics={"same_dimensions": True})
    report = reseal(report)
    result = reconcile(report)
    assert result["analysis_inventory_sha256"] == report["sha256"]
    assert report["rows"][0]["difference_class"] == "layout_changed"
    assert result["rows"][0]["difference_class"] == "renderer_equivalence_pending_policy"
    assert result["binary_different_approved"] == 0
    assert result["withheld_or_blocked"] == 1
    assert result["layout_review_required"] == 1


def test_report_rejects_changed_production_snapshot(tmp_path):
    from create_defaults.bulk.library_report import build
    from create_defaults.bulk.library_sources import save
    save(tmp_path / "production-snapshot.json", sealed({"repository": "Kometa-Team/Default-Images", "branch": "master", "head": "b" * 40, "tree": "c" * 40}))
    save(tmp_path / "proposed-tolerance-policy.json", PROPOSED_POLICY)
    save(tmp_path / "english-inventory.json", inventory(tmp_path))
    with pytest.raises(BulkError, match="Production snapshot moved"):
        build(tmp_path)


def test_retained_overlay_acceptance_requires_unchanged_comparison(monkeypatch):
    from create_defaults.bulk.config import ROOT
    from create_defaults.bulk.library_sources import load_json
    from create_defaults.bulk.library_publication import retained_overlay_decisions
    record = load_json(ROOT / "bulk/evidence/package-e/maintainer-visual-acceptance-20261017.json")
    decision = next(d for d in record["decisions"] if d["kind"] == "overlay")
    # Replay the recorded runtime for this fixture. A Linux CI process must not
    # be mistaken for the Windows renderer that produced these accepted bytes.
    monkeypatch.setattr("create_defaults.bulk.overlays.identity", lambda: decision["review_context"]["renderer"])
    row = {"id": decision["id"], "destination": decision["local_relative"], "technical_valid": True,
           "difference_class": "unexpected_difference", "candidate_sha256": decision["image_sha256"],
           "render_fingerprint": decision["render_fingerprint"], "validation_fingerprint": decision["validation_fingerprint"],
           "receipt_sha256": "new-owned-receipt-for-identical-artifact",
           "published_sha256": decision["historical_pixel_difference"]["legacy_sha256"]}
    report = {"kind": "overlays", "rows": [row]}
    assert len(retained_overlay_decisions(report)) == 1
    for field in ("candidate_sha256", "published_sha256", "render_fingerprint", "validation_fingerprint"):
        altered = deepcopy(report)
        altered["rows"][0][field] = "changed"
        assert not retained_overlay_decisions(altered)
    monkeypatch.setattr("create_defaults.bulk.overlays.identity", lambda: {"platform": "different"})
    assert not retained_overlay_decisions(report)


def offline_fixture(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    subprocess.run(["git", "init", str(base)], check=True, capture_output=True)
    git(base, "config", "user.name", "Offline fixture")
    git(base, "config", "user.email", "offline@invalid.local")
    (base / "README").write_text("baseline")
    git(base, "add", "README")
    git(base, "commit", "-m", "baseline")
    members = []
    for i in range(3):
        source = tmp_path / f"candidate-{i}.png"
        Image.new("RGB", (30, 40), (i * 70, 40, 80)).save(source)
        members.append({"destination": f"genre/{i}.png", "source": str(source), "sha256": sha256(source),
                        "size": source.stat().st_size, "approval_sha256": "test-external-approval"})
    manifest = sealed({"kind": "approved-library-publication-manifest", "baseline": {"head": git(base, "rev-parse", "HEAD")}, "members": members})
    return base, batch_plan(manifest, max_files=1, max_bytes=10000)


@pytest.mark.parametrize("failure", [None, "after_commit", "after_push"])
def test_offline_git_resume_and_exact_artifacts(tmp_path, failure):
    base, plan = offline_fixture(tmp_path)
    exercise = tmp_path / "exercise"
    if failure:
        with pytest.raises(BulkError, match="before journal"):
            run(plan, exercise, base, fail_at=failure)
    else:
        assert not run(plan, exercise, base, stop_after=1)["complete"]
    report = run(plan, exercise, base)
    assert report["complete"] and report["verified_batches"] == 3
    assert report["network_writes"] == 0
    assert run(plan, exercise, base)["commits"] == report["commits"]


def test_changed_baseline_and_artifacts_stop_transport(tmp_path):
    base, plan = offline_fixture(tmp_path)
    Path(plan["batches"][0]["members"][0]["source"]).write_bytes(b"corrupt")
    with pytest.raises(BulkError, match="Approved bytes changed"):
        run(plan, tmp_path / "exercise", base)
    (base / "README").write_text("drift")
    git(base, "add", "README"); git(base, "commit", "-m", "drift")
    with pytest.raises(BulkError, match="baseline moved"):
        run(plan, tmp_path / "other", base)


def test_incremental_pack_limit_stops_before_offline_push(tmp_path):
    base, plan = offline_fixture(tmp_path)
    plan["max_pack_bytes"] = 1
    plan = reseal(plan)
    with pytest.raises(BulkError, match="pack exceeds"):
        run(plan, tmp_path / "exercise", base)
    assert git(tmp_path / "exercise/remote.git", "rev-parse", "refs/heads/library-offline") == plan["baseline"]["head"]


def test_transport_rejects_unexpected_files_and_case_collisions(tmp_path):
    base, plan = offline_fixture(tmp_path)
    exercise = tmp_path / "exercise"
    run(plan, exercise, base, stop_after=1)
    (exercise / "work/unrelated.txt").write_text("unrelated")
    with pytest.raises(BulkError, match="unrelated modifications"):
        run(plan, exercise, base)
    plan["batches"][1]["members"][0]["destination"] = "genre/0.png"
    plan = reseal(plan)
    with pytest.raises(BulkError, match="colliding"):
        run(plan, tmp_path / "collision", base)
