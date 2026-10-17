"""Multilingual fitting evaluates actual captions without English matching."""
from copy import deepcopy
from pathlib import Path

import pytest
from create_defaults.bulk.tests.test_package_d import (config, definition, translations,
    captions, run_preflight)
from create_defaults.bulk.catalog import load_catalog
from create_defaults.bulk.common import fingerprint, sha256, BulkError
from create_defaults.bulk.definitions import Definition
from create_defaults.bulk.generation import generate
from create_defaults.bulk.languages import local_snapshot
from create_defaults.bulk.planner import Planner, renderer_identity
from create_defaults.bulk.poster_key_audit import poster_key_audit
from create_defaults.bulk.preflight import ELIGIBLE, _metrics, policy_for, effective_language
from create_defaults.bulk.typography import evaluate, cache_info, measure

@pytest.mark.parametrize("text", ["B", "Longer Words", "Tome", "Book"])
def test_different_length_same_length_and_identical_captions_fit(config, tmp_path, text):
    original = load_catalog(["Based"])[0]
    source = translations(tmp_path, en=captions(original, "Book"), fr=captions(original, text))
    report = run_preflight(original, source, config, languages=["fr"])
    variant = report["variants"][0]
    assert variant["status"] in ELIGIBLE
    assert variant["typography"]["state"] == "fits_current"
    assert "stale_measurement" not in {d["code"] for d in variant["diagnostics"]}
    if text == "Book":
        assert any(d["code"] == "identical_to_english" and d["severity"] == "info" for d in variant["diagnostics"])
    manifest = Planner(config).plan((Definition.create(effective_language(original, "fr")),), source, posters=[original.id], languages=["fr"])
    assert manifest["jobs"][0]["parameters"]["text"] == variant["caption"]

def test_normal_multiline_is_information(definition, config, tmp_path):
    source = translations(tmp_path, fr=captions(definition, "A tale of many small worlds"))
    variant = run_preflight(definition, source, config, languages=["fr"])["variants"][0]
    assert variant["status"] in ELIGIBLE
    assert len(variant["layout_probe"]["lines"]) > 1
    assert next(d for d in variant["diagnostics"] if d["code"] == "wrapped_caption")["severity"] == "info"

def test_proposal_is_review_required_and_never_activated(definition, config, tmp_path):
    source = translations(tmp_path, en=captions(definition, "Book"), fr=captions(definition, "Many translated words " * 8))
    original = definition.encoded
    report = run_preflight(definition, source, config, languages=["en", "fr"], policy="strict")
    french = next(v for v in report["variants"] if v["language"] == "fr")
    assert french["status"] == "needs_layout_review"
    proposal = french["typography"]["proposal"]
    assert proposal and not proposal["metrics"]["clipped"] and not proposal["metrics"]["outside_image"]
    assert proposal["font_size"] < definition.data["composer"]["font_size"]
    assert definition.encoded == original
    assert not report["missing_translations"]
    strict = generate((definition,), source, config=config, posters=[definition.id], languages=["en", "fr"], policy="strict")
    assert strict["status"] == "strict_blocked" and not strict["stages"]
    partial = generate((definition,), source, config=config, posters=[definition.id], languages=["fr"], policy="partial")
    assert partial["status"] == "partial" and not partial["stages"]
    with pytest.raises(BulkError, match="does not fit"):
        Planner(config).plan((Definition.create(effective_language(definition, "fr")),), source, posters=[definition.id], languages=["fr"])

def test_poster_keys_exclude_unrelated_and_deduplicate(definition, config, tmp_path):
    value = definition.data
    value["id"] = "based.another"
    value["output"]["filename"] = "Another.jpg"
    other = Definition.create(value)
    source = translations(tmp_path, en=captions(definition, "Book"),
        fr={"unrelated_weblate": {"empty": "", "wrong_type": 12}})
    from create_defaults.bulk.preflight import preflight
    report = preflight((definition, other), source, config=config, categories=["Based"], languages=["fr"])[0]
    snapshot = local_snapshot({code: tmp_path / (code + ".yml") for code in source.sources})
    audit = poster_key_audit([report], source, snapshot)
    row = audit["matrix"]["fr"]
    assert row["required_unique_keys"] == row["missing"] == 1
    assert row["invalid_or_empty"] == 0 and row["missing_impacted_variants"] == 2
    assert audit["keys"][0]["english_reference"] == "Book"
    assert set(audit["keys"][0]["poster_ids"]) == {definition.id, other.id}

@pytest.mark.parametrize("text", ["", " ", 3])
def test_empty_and_invalid_poster_keys_are_separate_from_typography(definition, config, tmp_path, text):
    source = translations(tmp_path, en=captions(definition, "Book"), fr=captions(definition, text))
    report = run_preflight(definition, source, config, languages=["fr"])
    audit = poster_key_audit([report], source, local_snapshot({code: tmp_path / (code + ".yml") for code in source.sources}))
    assert audit["matrix"]["fr"]["invalid_or_empty"] == 1
    assert audit["matrix"]["fr"]["missing"] == 0
    assert report["variants"][0]["status"] == "blocked"

def test_measurements_are_exact_cached_and_match_native_probe(definition, config):
    font = config.asset_dir / definition.data["composer"]["font"]
    digest, renderer = sha256(font), fingerprint(renderer_identity())
    first = evaluate(font, digest, "Livre", 250, 0, renderer)
    before = cache_info()["measurements"]["hits"]
    again = evaluate(font, digest, "Livre", 250, 0, renderer)
    assert first == again and cache_info()["measurements"]["hits"] == before + 1
    old = _metrics(str(font), font.stat().st_mtime_ns, "Livre", 250)
    assert all(first["current"][k] == v for k, v in old.items())
    for text, size, offset, rendering in [("Livres", 250, 0, renderer), ("Livre", 249, 0, renderer),
            ("Livre", 250, 1, renderer), ("Livre", 250, 0, "different-renderer")]:
        assert evaluate(font, digest, text, size, offset, rendering)["measurement_key"] != first["measurement_key"]
    again["current"]["lines"].append("corruption")
    assert evaluate(font, digest, "Livre", 250, 0, renderer) == first

def test_image_boundary_is_real_failure(definition, config):
    font = config.asset_dir / definition.data["composer"]["font"]
    result = evaluate(font, sha256(font), "Book", 250, 1500, fingerprint(renderer_identity()))
    assert result["current"]["outside_image"] and result["state"] == "geometric_failure"

def test_english_validation_stays_stable_when_only_french_changes(definition, config, tmp_path):
    source = translations(tmp_path, en=captions(definition, "Book"), fr=captions(definition, "Livre"))
    old = run_preflight(definition, source, config, languages=["en", "fr"])
    changed = translations(tmp_path, en=captions(definition, "Book"), fr=captions(definition, "Livres"))
    new = run_preflight(definition, changed, config, languages=["en", "fr"])
    by_language = lambda report: {v["language"]: v for v in report["variants"]}
    a, b = by_language(old), by_language(new)
    assert a["en"]["validation_fingerprint"] == b["en"]["validation_fingerprint"]
    assert a["fr"]["validation_fingerprint"] != b["fr"]["validation_fingerprint"]
    assert policy_for(a["en"]) != policy_for(a["fr"])

@pytest.mark.parametrize("change", ["font", "layout"])
def test_only_changed_french_font_or_layout_invalidates_approval(definition, config, tmp_path, change):
    from create_defaults.bulk.review import Reviews
    from create_defaults.bulk.state import Store
    source = translations(tmp_path, en=captions(definition, "Book"), fr=captions(definition, "Livre"))
    result = generate((definition,), source, config=config, posters=[definition.id], languages=["en", "fr"])
    reviews = Reviews(Store(config.cache_dir / "state.sqlite"), config)
    reviews.attach(result)
    items = {v["language"]: v for v in result["preflight"]["variants"]}
    for language in ("en", "fr"):
        item = reviews.item(items[language]["id"])
        warnings = [d["code"] for d in item["evidence"]["variant"]["diagnostics"] if d["severity"] == "warning"]
        reviews.decide(item["id"], expected_version=item["version"], reviewer="test fixture",
                       action="approve", accepted_warnings=warnings)
    value = definition.data
    changes = {"composer": {"text_offset": value["composer"]["text_offset"] + 1}}
    if change == "font":
        from create_defaults.bulk.config import ROOT
        import json
        approved = json.loads((ROOT / "bulk/baselines/approved-fonts.json").read_text(encoding="utf-8"))["fonts"]
        replacement = next(font for font in approved if font != value["composer"]["font"] and "Barlow" in font)
        changes = {"composer": {"font": replacement}}
    value["overrides"] = [{"language": "fr", "changes": changes}]
    changed = run_preflight(Definition.create(value), source, config, languages=["en", "fr"])
    reviews.ingest(changed)
    assert reviews.item(items["en"]["id"])["state"] == "approved"
    assert reviews.item(items["fr"]["id"])["state"] == "approval_stale"
    assert any(event["kind"] == "review_approve" for event in reviews.export()["events"])

def test_required_template_key_is_counted_even_when_caption_resolution_fails(definition, config, tmp_path):
    value = definition.data
    value["caption"]["template_key"] = "key_names.based"
    source = translations(tmp_path,
        en={"key_names": {"book": "Book", "based": "Based on <<item>>"}, "unrelated": {"unused": ""}},
        fr={"key_names": {"book": "Livre"}, "unrelated": {"unused": 3}})
    report = run_preflight(Definition.create(value), source, config, languages=["fr"])
    snapshot = local_snapshot({code: tmp_path / (code + ".yml") for code in source.sources})
    audit = poster_key_audit([report], source, snapshot)
    assert audit["matrix"]["fr"]["required_unique_keys"] == 2
    assert audit["matrix"]["fr"]["valid"] == audit["matrix"]["fr"]["missing"] == 1
    missing = next(k for k in audit["keys"] if k["status"] == "missing")
    assert missing["key"] == "key_names.based" and missing["english_reference"] == "Based on <<item>>"

@pytest.mark.parametrize("text,exemption", [("2026", "number_or_numeric_label"), ("BBC", "acronym_candidate"), ("Book", None)])
def test_identical_values_are_valid_and_informational(definition, config, tmp_path, text, exemption):
    source = translations(tmp_path, en=captions(definition, text), fr=captions(definition, text))
    report = run_preflight(definition, source, config, languages=["fr"])
    snapshot = local_snapshot({code: tmp_path / (code + ".yml") for code in source.sources})
    audit = poster_key_audit([report], source, snapshot)
    assert audit["matrix"]["fr"]["valid"] == 1
    assert audit["matrix"]["fr"]["identical_to_english_informational"] == 1
    assert audit["keys"][0]["identical_exemption"] == exemption
    assert report["variants"][0]["status"] in ELIGIBLE

def test_historical_ingestion_keeps_its_recorded_policy(definition, config, tmp_path):
    from create_defaults.bulk.review import Reviews
    from create_defaults.bulk.state import Store
    from create_defaults.bulk.preflight import POLICY
    source = translations(tmp_path, fr=captions(definition, "Livre"))
    report = run_preflight(definition, source, config, languages=["fr"])
    historical = deepcopy(report)
    historical["variants"][0].pop("validation_policy")
    payload = {k: v for k, v in historical.items() if k not in {"sha256", "report_directory", "metrics"}}
    historical["sha256"] = fingerprint(payload)
    reviews = Reviews(Store(config.cache_dir / "state.sqlite"), config)
    reviews.ingest(historical)
    item = reviews.item(historical["variants"][0]["id"])
    assert item["evidence"]["policy"] == POLICY
    assert item["policy"] == fingerprint(POLICY) != fingerprint(policy_for(historical["variants"][0]))
