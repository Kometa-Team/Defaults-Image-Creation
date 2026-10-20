import base64
from copy import deepcopy
import json
import sqlite3

from PIL import Image, ImageChops
import pytest
import yaml

from create_people_posters.github_inventory_core import blob_sha
from create_defaults.bulk.catalog import load_catalog
from create_defaults.bulk.common import BulkError, Conflict, canonical, fingerprint, sha256
from create_defaults.bulk.config import Config, ROOT
from create_defaults.bulk.definitions import Definition
from create_defaults.bulk.delta import affected_variants, translation_delta, validation_delta, regenerate
from create_defaults.bulk.generation import generate
from create_defaults.bulk.languages import LanguageSnapshot, local_snapshot, refresh, translations_from_snapshot
from create_defaults.bulk.overlays import CATALOG as OVERLAYS, plan as overlay_plan, generate as overlay_generate, render
from create_defaults.bulk.preflight import ELIGIBLE, POLICY, preflight, select_previews, variant_id
from create_defaults.bulk.review import Reviews
from create_defaults.bulk.services import propose_layout
from create_defaults.bulk.state import Store
from create_defaults.bulk.translations import Translations
from create_defaults.bulk.workers import WorkerLimits


@pytest.fixture
def config(tmp_path):
    return Config(cache_dir=tmp_path / "cache", workspace_dir=tmp_path / "work", output_dir=tmp_path / "output")


@pytest.fixture
def definition():
    value = load_catalog(["Based"])[0].data
    value["layout"] = {"kind": "fixed", "measurement": None}
    value["caption"]["case"] = "exact"
    return Definition.create(value)


def translations(tmp_path, **values):
    sources = {}
    for code, value in values.items():
        path = tmp_path / (code + ".yml")
        path.write_text(yaml.safe_dump(value, allow_unicode=True), encoding="utf-8")
        sources[code] = path
    return Translations(sources)


def captions(definition, value):
    first, second = definition.data["caption"]["key"].split(".")
    return {first: {second: value}}


def run_preflight(definition, translated, config, **options):
    return preflight((definition,), translated, config=config, posters=[definition.id], **options)[0]


def registry_record(code, **changes):
    return {"native_code": code, "code": code, "display_name": None, "resource": "defaults/" + code + ".yml",
            "sha256": "a" * 64, "availability": "available", "components": ["defaults"], "font_support": "unvalidated", **changes}


@pytest.mark.parametrize("code", ["bg", "hu", "ru", "ja", "zh-Hant", "nb_NO", "pt-br"])
def test_dynamic_languages_beyond_historical_maximum_and_exact_codes(code):
    snapshot = LanguageSnapshot.create([registry_record(code)], provenance={"kind": "test"})
    assert snapshot.select(["all"]) == (code,)
    assert snapshot.select([code]) == (code,)
    mutated = snapshot.data
    mutated["languages"][0]["code"] = "zz"
    assert snapshot.select([code]) == (code,)


@pytest.mark.parametrize("code", ["../en", "EN", "en/xx", "con", "en%20", "en\\xx", "x", "en."])
def test_malformed_language_ids_are_rejected(code):
    with pytest.raises(BulkError):
        LanguageSnapshot.create([registry_record(code)], provenance={})


def test_alias_case_collision_and_nonposter_components():
    with pytest.raises(BulkError, match="collide"):
        LanguageSnapshot.create([registry_record("pt-br"), registry_record("pt-BR")], provenance={})
    with pytest.raises(BulkError):
        LanguageSnapshot.create([registry_record("fr"), registry_record("de")], aliases={"fr": "de"}, provenance={})
    snapshot = LanguageSnapshot.create([registry_record("nb_NO"), registry_record("ja", components=["website"])], aliases={"nb-NO": "nb_NO"}, provenance={})
    assert snapshot.select(["all"]) == ("nb_NO",)
    assert snapshot.select(["nb-NO", "nb_NO"]) == ("nb_NO",)
    with pytest.raises(BulkError):
        snapshot.select(["unknown"])


class GitClient:
    repo = "Kometa-Team/Translations"
    def __init__(self):
        self.data = {"en": b"key_names:\n  book: Book\n", "bg": "key_names:\n  book: \u041a\u043d\u0438\u0433\u0430\n".encode()}
        self.calls = []

    def head(self, branch):
        self.calls.append("head")
        return "a" * 40, "b" * 40

    def tree(self, tree, recursive=False):
        self.calls.append("tree")
        return {"sha": tree, "truncated": False, "tree": [{"path": "defaults/" + code + ".yml", "sha": blob_sha(data), "type": "blob", "mode": "100644", "size": len(data)} for code, data in self.data.items()]}

    def blob(self, sha):
        self.calls.append("blob")
        data = next(data for data in self.data.values() if blob_sha(data) == sha)
        return {"sha": sha, "encoding": "base64", "content": base64.b64encode(data).decode()}


def test_live_contract_cold_warm_offline_and_corrupt_snapshot(tmp_path):
    client = GitClient()
    snapshot, cold = refresh(tmp_path, client)
    assert cold["downloaded"] == 2
    again, warm = refresh(tmp_path, client)
    assert snapshot.fingerprint == again.fingerprint and warm["cache_reused"] == 2 and warm["downloaded"] == 0
    pinned = LanguageSnapshot.load(cold["snapshot_file"])
    resolved = translations_from_snapshot(pinned, tmp_path)
    assert resolved.lookup("en", "key_names.book")[0] == "Book"
    path = tmp_path / "blobs" / (blob_sha(client.data["en"]) + ".yml")
    path.write_bytes(b"changed")
    assert resolved.lookup("en", "key_names.book")[0] == "Book"
    with pytest.raises(BulkError, match="differ"):
        translations_from_snapshot(pinned, tmp_path)
    selected = translations_from_snapshot(pinned, tmp_path, languages=["bg"])
    assert selected.lookup("bg", "key_names.book")[0] == "\u041a\u043d\u0438\u0433\u0430"
    partial = translations_from_snapshot(pinned, tmp_path, languages=["en", "bg"])
    with pytest.raises(BulkError, match="differ"):
        partial.lookup("en", "key_names.book")
    assert partial.lookup("bg", "key_names.book")[0] == "\u041a\u043d\u0438\u0433\u0430"


def test_partial_strict_audit_reports_and_language_isolation(definition, config, tmp_path):
    source = translations(tmp_path, en=captions(definition, "Book"), fr=captions(definition, "Livre"), de={"key_names": {}})
    report = run_preflight(definition, source, config, languages=["fr", "de"], policy="strict")
    assert report["status"] == "strict_blocked"
    assert [v["status"] for v in report["variants"]] == ["ready", "blocked"]
    assert report["missing_translations"][0]["english_source"] == "Book"
    assert report["missing_translations"][0]["logical_poster_count"] == 1
    assert report["metrics"]["logical_definitions"] == 1 and report["metrics"]["full_poster_renders"] == 0
    from pathlib import Path
    assert (Path(report["report_directory"]) / "translations.csv").is_file()
    result = generate((definition,), source, config=config, posters=[definition.id], languages=["fr", "de"], policy="strict")
    assert result["status"] == "strict_blocked" and not config.output_dir.exists()
    audit = generate((definition,), source, config=config, posters=[definition.id], languages=["fr"], policy="audit")
    assert audit["status"] == "audited" and not config.output_dir.exists()
    result = generate((definition,), source, config=config, posters=[definition.id], languages=["fr", "de"], limits=WorkerLimits(workers=1))
    assert result["status"] == "partial"
    assert len(result["manifest"]["jobs"]) == 1
    assert (config.output_dir / ("defaults-fr/based/" + definition.data["output"]["filename"])).is_file()
    assert not (config.output_dir / "defaults-de").exists()


def test_missing_keys_deduplicate_and_template_is_a_distinct_dependency(definition, config, tmp_path):
    value = definition.data
    value["id"] += ".second"
    value["output"]["filename"] = "Second.jpg"
    value["output"]["remote_paths"]["en"] = "based/Second.jpg"
    value["composer"]["out_name"] = "Second"
    second = Definition.create(value)
    source = translations(tmp_path, en=captions(definition, "Book"), fr={"key_names": {}})
    report, _ = preflight((definition, second), source, config=config, categories=["Based"], languages=["fr"])
    assert len(report["missing_translations"]) == 1
    assert report["missing_translations"][0]["logical_poster_count"] == 2
    assert report["missing_translations"][0]["rendered_variant_count"] == 2
    value = definition.data
    value["caption"]["template_key"] = "templates.collection"
    result = run_preflight(Definition.create(value), source, config, languages=["en"])
    assert result["missing_translations"][0]["key"] == "templates.collection"


@pytest.mark.parametrize("mode", ["none", "shared"])
def test_captionless_and_shared_do_not_require_unrelated_resources(definition, config, mode):
    value = definition.data
    value["caption"] = dict(value["caption"], mode=mode, key=None, text="" if mode == "none" else "Book")
    item = Definition.create(value)
    report = run_preflight(item, Translations({}), config, languages=["ar", "de"])
    assert all(v["status"] == "shared" for v in report["variants"])
    assert not report["missing_translations"]
    assert len({v["local_relative"] for v in report["variants"]}) == 2


def test_not_applicable_is_not_missing_resource(definition, config):
    value = definition.data
    value["applicability"]["de"] = {"status": "not_applicable", "reason": "Explicit logo restriction"}
    report = run_preflight(Definition.create(value), Translations({}), config, languages=["de"])
    assert report["variants"][0]["status"] == "not_applicable" and not report["missing_translations"]


@pytest.mark.parametrize("text,code", [("\u6f22\u5b57", "missing_glyph"), ("\u0643\u062a\u0627\u0628", "rtl_awaiting_review"), ("\ud800", "invalid_unicode"), ("W" * 100, "caption_clipping"), ("<<book>>", "unresolved_caption")])
def test_unicode_glyph_rtl_layout_and_placeholder_blockers(definition, config, tmp_path, text, code):
    source = translations(tmp_path, fr=captions(definition, text))
    report = run_preflight(definition, source, config, languages=["fr"])
    assert report["variants"][0]["status"] == "blocked"
    assert code in {d["code"] for d in report["variants"][0]["diagnostics"]}


def test_actual_french_fit_is_eligible_and_explicit_proposal_does_not_activate(config, tmp_path):
    definition = load_catalog(["Based"])[0]
    source = translations(tmp_path, fr=captions(definition, "Livre"))
    report = run_preflight(definition, source, config, languages=["fr"])
    assert report["variants"][0]["status"] in ELIGIBLE
    assert report["variants"][0]["typography"]["state"] == "fits_current"
    original = definition.encoded
    proposal = propose_layout(definition, source, "fr", config)
    assert proposal["state"] == "proposal-not-approved-or-activated" and definition.encoded == original
    approved_input = Definition.create(proposal["definition"])
    assert run_preflight(approved_input, source, config, languages=["fr"])["variants"][0]["status"] in ELIGIBLE
    assert approved_input.for_language("en").data["composer"] == definition.data["composer"]
    assert approved_input.for_language("en").data["layout"] == definition.data["layout"]


def test_scoped_catalog_does_not_load_unrelated_categories_or_assets(definition, monkeypatch, config, tmp_path):
    import create_defaults.bulk.catalog as module
    real = module.load_definitions
    paths = []
    def scoped(files, **kwargs):
        paths.extend(files)
        return real(files, **kwargs)
    monkeypatch.setattr(module, "load_definitions", scoped)
    selected = load_catalog(posters=[definition.id])
    assert len(selected) == 1 and [p.name for p in paths] == ["based.yml"]
    source = translations(tmp_path, en=captions(definition, "Book"))
    report = run_preflight(definition, source, config)
    assert report["metrics"]["logical_definitions"] == 1 and report["metrics"]["unique_inputs_hashed"] == 7


def test_delta_new_completed_removed_and_precise_variant_invalidation(definition, config, tmp_path):
    old = translations(tmp_path, en=captions(definition, "Book"), fr={"key_names": {}})
    before = run_preflight(definition, old, config, languages=["en", "fr"])
    new = translations(tmp_path, en=captions(definition, "Book"), fr=captions(definition, "Livre"), bg=captions(definition, "Book"))
    delta = translation_delta(old, new)
    assert delta["new_languages"] == ["bg"]
    assert affected_variants(delta, before)["variant_ids"] == [variant_id(definition.id, "fr")]
    reviews = Reviews(Store(config.cache_dir / "state.sqlite"), config)
    reviews.ingest(before)
    affected = reviews.invalidate_keys([(v["language"], v["key"]) for v in delta["changes"]], reason=delta["sha256"])
    assert affected == [variant_id(definition.id, "fr")]
    after = run_preflight(definition, new, config, languages=["en", "fr"])
    assert after["variants"][0]["validation_fingerprint"] == before["variants"][0]["validation_fingerprint"]
    assert after["variants"][1]["status"] == "ready"
    removed = translation_delta(new, old)
    assert any(v["kind"] == "removed" and v["language"] == "fr" for v in removed["changes"])


@pytest.fixture
def rendered(definition, config, tmp_path):
    source = translations(tmp_path, en=captions(definition, "Book"))
    result = generate((definition,), source, config=config, posters=[definition.id], limits=WorkerLimits(workers=1))
    reviews = Reviews(Store(config.cache_dir / "state.sqlite"), config)
    reviews.attach(result)
    return definition, source, result, reviews


def test_review_individual_comments_immutable_history_and_concurrency(rendered):
    definition, source, result, reviews = rendered
    identity = result["preflight"]["variants"][0]["id"]
    item = reviews.item(identity)
    approved = reviews.decide(identity, expected_version=item["version"], reviewer="maintainer", action="approve")
    assert approved["state"] == "approved"
    with pytest.raises(Conflict):
        reviews.decide(identity, expected_version=item["version"], reviewer="other", action="reject")
    commented = reviews.decide(identity, expected_version=approved["version"], reviewer="maintainer", action="comment", comment="Visual inspection recorded")
    assert commented["state"] == "approved"
    exported = reviews.export()
    assert any(e["kind"] == "review_comment" for e in exported["events"])
    with reviews.store.connection() as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM events")


def test_review_group_exact_membership_and_changed_bytes(rendered):
    _, _, result, reviews = rendered
    identity = result["preflight"]["variants"][0]["id"]
    batch = reviews.batch([identity], scope="test", inspected=[identity])
    with pytest.raises(Conflict):
        reviews.approve_group(batch["id"], membership="changed", reviewer="maintainer")
    assert reviews.approve_group(batch["id"], membership=batch["membership"], reviewer="maintainer")["approved"] == 1
    with pytest.raises(Conflict):
        reviews.approve_group(batch["id"], membership=batch["membership"], reviewer="maintainer")
    item = reviews.item(identity)
    target = reviews.config.output_dir / item["preview"]["local_relative"]
    target.write_bytes(target.read_bytes() + b"changed")
    with pytest.raises(Conflict, match="bytes changed"):
        reviews.decide(identity, expected_version=item["version"], reviewer="maintainer", action="approve")


def test_changed_caption_stales_only_relevant_approval(rendered, tmp_path):
    definition, old, result, reviews = rendered
    identity = result["preflight"]["variants"][0]["id"]
    item = reviews.item(identity)
    reviews.decide(identity, expected_version=item["version"], reviewer="maintainer", action="approve")
    new = translations(tmp_path, en=captions(definition, "Updated"))
    report = run_preflight(definition, new, reviews.config)
    reviews.ingest(report)
    assert reviews.item(identity)["state"] == "approval_stale" and reviews.item(identity)["preview"] is None
    with pytest.raises(Conflict):
        reviews.decide(identity, expected_version=reviews.item(identity)["version"], reviewer="maintainer", action="approve")


def test_risk_explicit_selection_high_risk_and_group_block(rendered):
    _, _, result, reviews = rendered
    report = deepcopy(result["preflight"])
    variant = report["variants"][0]
    assert select_previews(report, representatives=1) == [variant["id"]]
    variant["risk"] = {"version": POLICY["risk"], "level": "high", "reasons": ["new_logo"], "requires_individual": True}
    assert select_previews(report, high_risk=True) == [variant["id"]]
    assert select_previews(report, representatives=1) == []
    item = reviews.item(variant["id"])
    rejected = reviews.decide(variant["id"], expected_version=item["version"], reviewer="maintainer", action="reject")
    batch = reviews.batch([variant["id"]], scope="prior rejection")
    with pytest.raises(BulkError, match="individual"):
        reviews.approve_group(batch["id"], membership=batch["membership"], reviewer="maintainer")


def test_overlay_complete_inventory_mapping_dimensions_alpha_and_cache(config):
    catalog = json.loads(OVERLAYS.read_text())
    assert catalog["counts"] == {"groups": 18, "operations": 36, "transforms": 4122, "unique_inputs": 2061}
    audit = json.loads((ROOT / "phase2/evidence/current-source-audit.json").read_text())
    assert catalog["legacy_audit_sha256"] == fingerprint(audit["overlays"])
    manifest = overlay_plan(config, groups=["genre"], sources=["logos_genre/Experimental.png"])
    assert len(manifest["jobs"]) == 2
    assert {j["local_relative"] for j in manifest["jobs"]} == {"genre/overlays/standard/Experimental.png", "genre/overlays/bigger/Experimental.png"}
    result = overlay_generate(config, groups=["genre"], sources=["logos_genre/Experimental.png"], limits=WorkerLimits(workers=1))
    assert result["status"] == "verified"
    for job in result["manifest"]["jobs"]:
        with Image.open(config.output_dir / job["local_relative"]) as image:
            assert image.mode == "RGBA" and image.width <= job["parameters"]["box"][0] and image.height <= job["parameters"]["box"][1]
            assert image.getchannel("A").getextrema()[0] == 0
    warm = overlay_generate(config, groups=["genre"], sources=["logos_genre/Experimental.png"], limits=WorkerLimits(workers=1))
    assert warm["execution"]["metrics"]["executed"] == 0 and warm["execution"]["metrics"]["worker_starts"] == 0


def test_overlay_trimming_upscale_and_determinism(tmp_path):
    source = tmp_path / "in.png"
    image = Image.new("RGBA", (20, 20))
    image.paste((255, 0, 0, 255), (5, 5, 15, 15))
    image.save(source)
    params = {"trim": True, "box": [40, 10]}
    first, second = tmp_path / "first.png", tmp_path / "second.png"
    render(params, source, first)
    render(params, source, second)
    assert sha256(first) == sha256(second)
    with Image.open(first) as result:
        assert result.size == (10, 10) and result.getpixel((5, 5)) == (255, 0, 0, 255)
    source.write_bytes(b"not an image")
    with pytest.raises(OSError):
        render(params, source, second)


def test_french_override_and_new_language_do_not_invalidate_existing_english(definition, config, tmp_path):
    source = translations(tmp_path, en=captions(definition, "Book"), fr=captions(definition, "Livre"), bg=captions(definition, "Book"))
    before = run_preflight(definition, source, config, languages=["en", "fr"])
    value = definition.data
    value["overrides"] = [{"language": "fr", "changes": {"composer": {"text_offset": 100}}}]
    after = run_preflight(Definition.create(value), source, config, languages=["en", "fr"])
    assert validation_delta(before, after)["changed"] == [variant_id(definition.id, "fr")]
    added = run_preflight(definition, source, config, languages=["en", "fr", "bg"])
    assert validation_delta(before, added) == {"changed": [], "removed": [], "added": [variant_id(definition.id, "bg")]}


def test_shared_font_single_logo_and_category_layout_invalidate_exact_consumers(definition, config, tmp_path):
    value = definition.data
    value["id"] += ".other"
    value["output"]["filename"] = "Other.jpg"
    value["output"]["remote_paths"]["en"] = "based/Other.jpg"
    value["composer"]["out_name"] = "Other"
    definitions = (definition, Definition.create(value))
    source = translations(tmp_path, en=captions(definition, "Book"), fr=captions(definition, "Livre"))
    options = dict(config=config, categories=["Based"], languages=["en", "fr"])
    before = preflight(definitions, source, **options)[0]
    changed = []
    for item in definitions:
        value = item.data
        value["composer"]["font"] = "fonts/PlusJakartaSans-Bold.ttf"
        changed.append(Definition.create(value))
    assert len(validation_delta(before, preflight(changed, source, **options)[0])["changed"]) == 4
    value = definition.data
    value["composer"]["logo"] = "logos_playlist/Arrowverse.png"
    after = preflight((Definition.create(value), definitions[1]), source, **options)[0]
    assert set(validation_delta(before, after)["changed"]) == {variant_id(definition.id, "en"), variant_id(definition.id, "fr")}
    changed = []
    for item in definitions:
        value = item.data
        value["composer"]["text_offset"] = 100
        changed.append(Definition.create(value))
    assert len(validation_delta(before, preflight(changed, source, **options)[0])["changed"]) == 4


def test_color_conflict_proposal_stays_uncommitted(definition, config, tmp_path):
    from create_defaults.bulk.colors import ColorPolicy, ColorRegistry
    registry = ColorRegistry(Store(config.cache_dir / "state.sqlite"), ColorPolicy("test-d01", 0, 4.5))
    registry.import_historical({"assignments": [{"audit_id": "old", "category": "Based", "hex": "#131CA1"}], "generated_assignments": []})
    value = definition.data
    value["id"] = "based.proposal"
    value["source"] = {"kind": "authored", "path": "proposal.yml", "line": None, "row_sha256": None}
    value["color_assignment"]["origin"] = "independent"
    value["color_assignment"]["id"] = "based.proposal.background"
    value["composer"]["base_color"] = "#131ca1"
    proposed = Definition.create(value)
    report = run_preflight(proposed, translations(tmp_path, en=captions(definition, "Book")), config, color_registry=registry)
    assert report["variants"][0]["status"] == "blocked"
    assert "category_exact_collision" in {d["code"] for d in report["variants"][0]["diagnostics"]}
    assert proposed.encoded == Definition.create(value).encoded


def test_warning_acceptance_and_high_risk_group_rejection(definition, config, tmp_path):
    source = translations(tmp_path, en=captions(definition, "Book " * 6))
    result = generate((definition,), source, config=config, posters=[definition.id], limits=WorkerLimits(workers=1))
    reviews = Reviews(Store(config.cache_dir / "state.sqlite"), config)
    reviews.attach(result)
    identity = result["preflight"]["variants"][0]["id"]
    item = reviews.item(identity)
    warnings = sorted({d["code"] for d in item["evidence"]["variant"]["diagnostics"] if d["severity"] == "warning"})
    assert warnings
    with pytest.raises(BulkError, match="warning"):
        reviews.decide(identity, expected_version=item["version"], reviewer="maintainer", action="approve")
    batch = reviews.batch([identity], scope="warnings")
    with pytest.raises(BulkError):
        reviews.approve_group(batch["id"], membership=batch["membership"], reviewer="maintainer")
    assert reviews.decide(identity, expected_version=item["version"], reviewer="maintainer", action="approve", accepted_warnings=warnings)["state"] == "approved_with_accepted_warnings"


def test_private_intermediate_blocked_from_approval_and_policy_obsolescence(rendered):
    definition, source, result, reviews = rendered
    identity = result["preflight"]["variants"][0]["id"]
    item = reviews.item(identity)
    with pytest.raises(Conflict, match="policy"):
        reviews.decide(identity, expected_version=item["version"], reviewer="maintainer", action="approve", policy="obsolete")
    value = definition.data
    value["output"]["directory"] = "_intermediates/test"
    value["output"]["remote_paths"]["en"] = None
    report = run_preflight(Definition.create(value), source, reviews.config)
    reviews.ingest(report)
    item = reviews.item(identity)
    with pytest.raises(BulkError, match="private"):
        reviews.decide(identity, expected_version=item["version"], reviewer="maintainer", action="approve")


def probe_changed(task, target, resources):
    from create_defaults.bulk.workers import probe_renderer
    probe_renderer(task, target, resources)


def test_verified_older_worker_receipts_survive_new_wrapper_identity(config):
    from create_defaults.bulk.workers import PersistentWorkers, RenderTask, probe_renderer
    task = RenderTask("proof.version", fingerprint({"probe": 1}), "proof/result.bin", {"probe": 1})
    store = Store(config.cache_dir / "state.sqlite")
    with PersistentWorkers(store, config, WorkerLimits(workers=1), renderer=probe_renderer) as pool:
        first = pool.run([task])
    with PersistentWorkers(store, config, WorkerLimits(workers=1), renderer=probe_changed) as pool:
        changed = pool.run([task])
    assert first["jobs"][task.id]["sha256"] == changed["jobs"][task.id]["sha256"]
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM jobs WHERE status='verified'").fetchone()[0] == 2


def test_translation_delta_renders_only_changed_french_and_removed_resource_is_blocked(definition, config, tmp_path):
    old = translations(tmp_path, en=captions(definition, "Book"), fr=captions(definition, "Livre"))
    before = run_preflight(definition, old, config, languages=["en", "fr"])
    new = translations(tmp_path, en=captions(definition, "Book"), fr=captions(definition, "Roman"))
    registry = local_snapshot({code: tmp_path / (code + ".yml") for code in ("en", "fr")})
    result = regenerate(translation_delta(old, new), before, (definition,), new, registry=registry, config=config, limits=WorkerLimits(workers=1))
    assert [v["language"] for v in result["preflight"]["variants"]] == ["fr"]
    assert len(result["manifest"]["jobs"]) == 1 and result["manifest"]["jobs"][0]["language"] == "fr"
    removed = translations(tmp_path, en=captions(definition, "Book"))
    only_en = LanguageSnapshot.create([registry_record("en", sha256=removed.hashes["en"])], provenance={})
    result = regenerate(translation_delta(new, removed), before, (definition,), removed, registry=only_en, config=config)
    assert result["status"] == "partial" and result["preflight"]["variants"][0]["status"] == "blocked"


def test_registry_snapshot_cannot_be_mixed_with_new_translation_bytes(definition, config, tmp_path):
    source = translations(tmp_path, en=captions(definition, "Book"))
    registry = LanguageSnapshot.create([registry_record("en")], provenance={})
    with pytest.raises(BulkError, match="differs from pinned"):
        run_preflight(definition, source, config, registry=registry)


def test_cross_category_missing_key_report_deduplicates_with_exact_mappings():
    from create_defaults.bulk.preflight import consolidate_missing
    base = {"language": "fr", "key": "key_names.book", "reason": "missing_translation", "source_snapshot": "a" * 64, "fallback": None}
    rows = [dict(base, category="Based", poster_ids=["based.book"], variant_ids=["based.fr"]),
            dict(base, key="KEY_NAMES.BOOK", category="Playlist", poster_ids=["playlist.book"], variant_ids=["playlist.fr"])]
    result = consolidate_missing(rows)
    assert len(result) == 1 and result[0]["logical_poster_count"] == result[0]["rendered_variant_count"] == 2
    assert result[0]["category_posters"] == {"Based": ["based.book"], "Playlist": ["playlist.book"]}
    assert result[0]["key_aliases"] == ["KEY_NAMES.BOOK", "key_names.book"]


def test_cli_retains_report_and_returns_distinct_strict_partial_and_audit_codes(definition, tmp_path, capsys):
    from create_defaults.bulk.__main__ import main
    file = tmp_path / "based.yml"
    file.write_text(yaml.safe_dump({"schema_version": 1, "category": "Based", "definitions": [definition.data]}), encoding="utf-8")
    translations(tmp_path, en=captions(definition, "Book"), fr=captions(definition, "Livre"))
    common = ["--cache-dir", str(tmp_path / "cache"), "--workspace-dir", str(tmp_path / "work"), "--output-dir", str(tmp_path / "out"), "--translation-dir", str(tmp_path)]
    # Restrict local source discovery to actual language files, not definition YAML.
    source_dir = tmp_path / "translations"
    source_dir.mkdir()
    for language in ("en", "fr"):
        (tmp_path / (language + ".yml")).replace(source_dir / (language + ".yml"))
    common[-1] = str(source_dir)
    args = ["preflight", "--definitions", str(file), "--poster", definition.id, "--language", "fr", "--language", "de"]
    assert main(common + args + ["--policy", "strict"]) == 6
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "strict_blocked" and not (tmp_path / "out").exists()
    assert main(common + args + ["--policy", "audit"]) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "partial"
    assert main(common + ["generate", "--definitions", str(file), "--poster", definition.id, "--language", "fr", "--policy", "audit"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "audited"


def test_compact_audit_summary_retains_counts_without_bulk_variant_records():
    from create_defaults.bulk.d_summary import audit_summary
    row = {"language": "fr", "category": "Based", "key": "key_names.book", "reason": "missing_translation", "source_snapshot": "a" * 64,
           "fallback": None, "poster_ids": ["based.book"], "variant_ids": ["based.fr"]}
    audit = {"registry_sha256": "a" * 64, "source": {}, "languages": ["fr"], "scopes": [{"language": "fr", "coverage": {"blocked": 1}, "diagnostics": {"missing_translation": 1}}],
             "coverage": {"blocked": 1}, "missing_translations": [row], "elapsed_seconds": 1, "peak_observed_parent_rss": 100,
             "unique_sources_hashed": 0, "poster_renders": 0, "scope": "test"}
    summary, missing = audit_summary(audit)
    assert summary["variants_audited"] == summary["deduplicated_missing_or_invalid_keys"] == 1
    assert summary["by_language"]["fr"]["coverage"] == {"blocked": 1}
    assert "variants" not in summary and missing[0]["poster_ids"] == ["based.book"]


def test_unavailable_resource_blocks_only_translated_dependents_and_honors_reviewed_fallback(definition, config, tmp_path):
    translated = translations(tmp_path, fr=captions(definition, "Livre"))
    available = LanguageSnapshot.create([registry_record("fr", sha256=translated.hashes["fr"])], provenance={})
    unavailable = LanguageSnapshot.create([registry_record("fr", availability="unavailable", sha256=None)], provenance={})
    before = run_preflight(definition, translated, config, languages=["fr"], registry=available)
    shared = definition.data
    shared["id"] += ".shared"
    shared["caption"] = dict(shared["caption"], mode="none", key=None)
    shared["output"]["filename"] = "Shared.jpg"
    shared["composer"]["out_name"] = "Shared"
    shared["composer"]["base_color"] = "#010203"
    shared["output"]["remote_paths"]["en"] = None
    shared = Definition.create(shared)
    shared_before = run_preflight(shared, translated, config, languages=["fr"], registry=available)
    combined = dict(before, variants=before["variants"] + shared_before["variants"])
    delta = translation_delta(translated, translated, old_registry=available, new_registry=unavailable)
    assert delta["availability_changes"] == ["fr"] and delta["mapping_changes"] == []
    assert affected_variants(delta, combined)["variant_ids"] == [variant_id(definition.id, "fr")]
    report = run_preflight(definition, translated, config, languages=["fr"], registry=unavailable)
    assert report["variants"][0]["status"] == "blocked"
    assert run_preflight(shared, translated, config, languages=["fr"], registry=unavailable)["variants"][0]["status"] in ELIGIBLE
    value = definition.data
    value["caption"]["fallback"] = {"id": "fallback.reviewed", "language": None, "key": None, "text": "Book", "reviewer": "maintainer", "reason": "Explicit test fallback", "policy_version": "test-d1"}
    report = run_preflight(Definition.create(value), translated, config, languages=["fr"], registry=unavailable)
    assert report["variants"][0]["caption"] == "Book" and report["variants"][0]["status"] == "ready_with_warning"


@pytest.mark.parametrize("bad", ["broken: [", b"\xff"])
def test_malformed_unrelated_local_resource_does_not_block_selected_french(definition, config, tmp_path, bad):
    from dataclasses import replace
    from create_defaults.bulk.d_cli import source
    translations(tmp_path, fr=captions(definition, "Livre"))
    if isinstance(bad, bytes):
        (tmp_path / "de.yml").write_bytes(bad)
    else:
        (tmp_path / "de.yml").write_text(bad, encoding="utf-8")
    config = replace(config, translation_dir=tmp_path)
    registry, translated = source(config, languages=["fr"], definitions=(definition,))
    assert run_preflight(definition, translated, config, languages=["fr"], registry=registry)["variants"][0]["status"] == "ready"
    registry, translated = source(config, languages=["fr", "de"], definitions=(definition,))
    report = run_preflight(definition, translated, config, languages=["fr", "de"], registry=registry)
    assert [v["status"] for v in report["variants"]] == ["ready", "blocked"]


def test_blocked_child_does_not_render_otherwise_unneeded_parent(config):
    from create_defaults.bulk.generators import GENERATORS
    from create_defaults.bulk.planner import Planner
    expanded = Planner(generators=GENERATORS).expand(load_catalog(["Decade"]))[0]
    child = next(d for d in expanded.values() if d.data["output"]["directory"] == "decade/best" and d.data["output"]["filename"] == "2020.jpg")
    parent = expanded[child.data["dependencies"][0]["poster_id"]]
    result = generate((parent, child), Translations({}), config=config, posters=[child.id], languages=["de"])
    assert result["status"] == "partial" and result["stages"] == []
    assert any(v["status"] == "shared" for v in result["preflight"]["variants"])
    assert not config.output_dir.exists()


def test_shared_artwork_is_verified_reused_across_languages_and_fresh_pools(definition, config, tmp_path):
    value = definition.data
    value["caption"] = dict(value["caption"], mode="none", key=None)
    shared = Definition.create(value)
    result = generate((shared,), Translations({}), config=config, posters=[shared.id], languages=["en", "fr", "de"], limits=WorkerLimits(workers=2))
    assert result["status"] == "verified"
    assert sum(s["execution"]["metrics"]["executed"] for s in result["stages"]) == 1
    assert sum(s["execution"]["metrics"]["dedup_reuses"] for s in result["stages"]) == 2
    extra = generate((shared,), translations(tmp_path, bg={}), config=config, posters=[shared.id], languages=["bg"], limits=WorkerLimits(workers=2))
    assert extra["stages"][0]["execution"]["metrics"]["executed"] == 0
    assert extra["stages"][0]["execution"]["metrics"]["dedup_reuses"] == 1
    assert len(list(config.output_dir.rglob("*.jpg"))) == 4
    assert len({sha256(p) for p in config.output_dir.rglob("*.jpg")}) == 1


def test_historical_separator_template_is_preserved_but_recolor_is_not():
    from create_defaults.bulk.generators import GENERATORS
    from create_defaults.bulk.planner import Planner
    from create_defaults.bulk.preflight import _preserved_color
    identity = "separators.separators-amethyst-producer.41186eb8"
    definitions = load_catalog(posters=[identity])
    item = Planner(generators=GENERATORS).expand(definitions)[0][identity]
    assert item.data["color_assignment"]["origin"] == "template"
    assert _preserved_color(item.data)
    changed = item.data
    changed["composer"]["base_color"] = "#010203"
    assert not _preserved_color(changed)


@pytest.mark.parametrize("change", ["renderer", "generation"])
def test_old_preview_cannot_approve_new_renderer_or_same_bytes_new_generation(rendered, monkeypatch, change):
    definition, translated, result, reviews = rendered
    identity = result["preflight"]["variants"][0]["id"]
    item = reviews.item(identity)
    if change == "renderer":
        import create_defaults.bulk.planner as module
        current = module.renderer_identity()
        monkeypatch.setattr(module, "renderer_identity", lambda: dict(current, python="changed"))
        message = "Renderer changed"
    else:
        value = definition.data
        # The approved legacy dominant-color flag is deliberately a visual no-op,
        # but the changed input still creates a distinct owned render generation.
        value["composer"]["dom_color"] = True
        updated = generate((Definition.create(value),), translated, config=reviews.config, posters=[definition.id], limits=WorkerLimits(workers=1))
        assert updated["stages"][0]["execution"]["jobs"][identity]["sha256"] == item["preview"]["sha256"]
        message = "generation differs"
    with pytest.raises(Conflict, match=message):
        reviews.decide(identity, expected_version=item["version"], reviewer="maintainer", action="approve")
