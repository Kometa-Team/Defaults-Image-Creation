from collections import Counter
import json
import shutil

from PIL import Image
import pytest
import yaml

from create_defaults.bulk.catalog import CATALOG, load_catalog
from create_defaults.bulk.common import BulkError, sha256
from create_defaults.bulk.config import CATEGORIES, Config, ROOT
from create_defaults.bulk.definitions import Definition
from create_defaults.bulk.generation import generate
from create_defaults.bulk.generators import GENERATORS
from create_defaults.bulk.migration import reconcile
from create_defaults.bulk.planner import Planner, SHARED_ASSETS
from create_defaults.bulk.translations import Translations
from create_defaults.bulk.workers import WorkerLimits


COUNTS = {"Aspect": 9, "AudioLanguage": 188, "Awards": 4847, "Based": 4, "Chart": 1182,
          "ContentRating": 72, "Country": 608, "Decade": 31, "Franchise": 118, "Genre": 275,
          "Network": 568, "Playlist": 9, "Resolution": 15, "Seasonal": 23, "Separators": 749,
          "Streaming": 256, "Studio": 488, "SubtitleLanguage": 188, "Universe": 20,
          "VideoFormat": 6, "Year": 301}


@pytest.fixture(scope="module")
def catalog():
    definitions = load_catalog(["All"])
    expanded = tuple(Planner(generators=GENERATORS).expand(definitions)[0].values())
    return definitions, expanded


@pytest.fixture(scope="module")
def translations():
    return Translations({"en": ROOT / "fixtures/english/en.yml"})


def test_all_categories_and_exact_effective_counts(catalog):
    definitions, expanded = catalog
    assert set(COUNTS) == set(CATEGORIES) - {"Overlays"}
    assert Counter(item.category for item in expanded) == COUNTS
    assert len(expanded) == 9957
    assert len({item.id for item in expanded}) == 9957
    assert len(definitions) < 5000


@pytest.mark.parametrize("category", COUNTS)
def test_each_category_matches_corrected_capture(catalog, translations, category):
    expanded = tuple(item for item in catalog[1] if item.category == category)
    result = reconcile(category, expanded, translations)
    assert result["contract_parity"], result["discrepancies"]
    assert result["active_jobs"] == COUNTS[category]


def test_approved_source_corrections_and_exact_fonts(catalog):
    expanded = catalog[1]
    splatter = [item.data for item in expanded if item.data["output"]["filename"] == "Splatter.jpg"]
    assert len(splatter) == 1
    assert splatter[0]["composer"]["base_color"] == "#990000"
    assert splatter[0]["composer"]["white_wash"] is False
    audit = json.loads((CATALOG / "audit/genre.json").read_text())
    assert audit["retired"][0]["line"] == 4883
    assert any(item["source"]["definition_line"] == 4884 for item in audit["active"])
    outputs = [item.data["output"]["filename"] for item in expanded if item.category == "Franchise"]
    assert "Death in Paradise (2011).jpg" in outputs
    assert "Death in Paradise (2911).jpg" not in outputs
    jakarta = [item.data for item in expanded if item.category in {"Year", "Decade"} and "Jakarta" in item.data["composer"]["font"]]
    assert len(jakarta) == 11
    assert all(item["composer"]["font_size"] == 409 for item in jakarta)


def test_dynamic_generators_are_deterministic_and_bounded(catalog):
    planner = Planner(generators=GENERATORS)
    first = planner.expand(catalog[0])[0]
    second = planner.expand(tuple(reversed(catalog[0])))[0]
    assert {key: item.encoded for key, item in first.items()} == {key: item.encoded for key, item in second.items()}
    for definition in catalog[0]:
        spec = definition.data["generator"]
        if spec:
            with pytest.raises(BulkError, match="require"):
                list(GENERATORS[(spec["name"], spec["version"]) ](definition, dict(spec["parameters"], unrecognized=True)))


def test_awards_overwritten_intermediates_have_no_remote_destination(catalog):
    intermediates = [item.data for item in catalog[1] if item.data["output"]["directory"].startswith("_intermediates/")]
    assert len(intermediates) == 2
    assert all(item["output"]["remote_paths"]["en"] is None for item in intermediates)
    assert {item["source"]["line"] for item in intermediates} == {1894, 2208}


def test_generated_children_cannot_be_planned_with_invented_hashes(catalog, translations, tmp_path):
    definitions = tuple(item for item in catalog[0] if item.category == "Decade")
    child = next(item for item in catalog[1] if item.category == "Decade" and item.data["dependencies"])
    config = Config(cache_dir=tmp_path / "cache", workspace_dir=tmp_path / "work", output_dir=tmp_path / "output")
    planner = Planner(config, generators=GENERATORS)
    with pytest.raises(BulkError, match="verified parent"):
        planner.plan(definitions, translations, posters=[child.id])


def test_real_composer_parent_child_incremental_resume_and_cleanup(catalog, translations, tmp_path):
    expanded = [item for item in catalog[1] if item.category == "Decade"]
    child = next(item for item in expanded if item.data["output"]["directory"] == "decade/best" and item.data["output"]["filename"] == "2020.jpg")
    parent = next(item for item in expanded if item.id == child.data["dependencies"][0]["poster_id"])
    config = Config(cache_dir=tmp_path / "cache", workspace_dir=tmp_path / "work", output_dir=tmp_path / "output")
    definitions = (parent, child)
    options = dict(config=config, posters=[child.id], limits=WorkerLimits(workers=2))
    first = generate(definitions, translations, **options)
    assert first["status"] == "verified" and len(first["stages"]) == 2
    jobs = first["stages"][-1]["manifest"]["jobs"]
    assert jobs[-1]["dependencies"][0]["sha256"] == sha256(config.output_dir / jobs[0]["local_relative"])
    for job in jobs:
        with Image.open(config.output_dir / job["local_relative"]) as image:
            assert image.format == "JPEG" and image.size == (2000, 3000) and image.mode == "RGB"
            image.load()
    warm = generate(definitions, translations, **options)
    assert all(stage["execution"]["metrics"]["executed"] == 0 for stage in warm["stages"])
    value = parent.data
    value["composer"]["base_color"] = "#123456"
    changed = generate((Definition.create(value), child), translations, **options)
    assert [stage["execution"]["metrics"]["executed"] for stage in changed["stages"]] == [1, 1]
    assert not list(config.workspace_dir.iterdir())
    assert first["stages"][-1]["manifest"]["jobs"][-1]["render_fingerprint"] != changed["stages"][-1]["manifest"]["jobs"][-1]["render_fingerprint"]


def test_caption_change_only_invalidates_affected_language_and_poster(translations, tmp_path):
    definitions = []
    for item in load_catalog(["Based"])[:2]:
        value = item.data
        value["layout"] = {"kind": "fixed", "measurement": None}
        value["languages"] = ["en", "de"]
        value["applicability"]["de"] = {"status": "applicable", "reason": "ASCII test caption, not multilingual acceptance"}
        value["output"]["remote_paths"]["de"] = "de/" + value["output"]["remote_paths"]["en"]
        definitions.append(Definition.create(value))
    source = ROOT / "fixtures/english/en.yml"
    changed = yaml.safe_load(source.read_text(encoding="utf-8"))
    target = tmp_path / "de.yml"
    target.write_text(yaml.safe_dump(changed), encoding="utf-8")
    before = Planner().plan(tuple(definitions), Translations({"en": source, "de": target}), categories=["Based"], languages=["en", "de"])
    selected_key = definitions[0].data["caption"]["key"].split(".")[-1]
    actual_key = next(key for key in changed["key_names"] if key.casefold() == selected_key.casefold())
    changed["key_names"][actual_key] = "UPDATED CAPTION"
    target.write_text(yaml.safe_dump(changed), encoding="utf-8")
    after = Planner().plan(tuple(definitions), Translations({"en": source, "de": target}), categories=["Based"], languages=["en", "de"])
    affected = [(a["poster_id"], a["language"]) for a, b in zip(before["jobs"], after["jobs"], strict=True) if a["render_fingerprint"] != b["render_fingerprint"]]
    assert affected == [(definitions[0].id, "de")]


def test_changed_logo_invalidates_only_its_consumers(translations, tmp_path):
    definitions = list(load_catalog(["Based"])[:2])
    assets = tmp_path / "assets"
    paths = {*SHARED_ASSETS, definitions[0].data["composer"]["font"]}
    for path in paths:
        target = assets / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, target)
    shutil.copyfile(ROOT / "logos_playlist/Arrowverse.png", assets / "private-logo.png")
    value = definitions[0].data
    value["composer"]["logo"] = "private-logo.png"
    definitions[0] = Definition.create(value)
    config = Config(asset_dir=assets, cache_dir=tmp_path / "cache", workspace_dir=tmp_path / "work", output_dir=tmp_path / "output")
    planner = Planner(config)
    before = planner.plan(definitions, translations, categories=["Based"])
    with Image.open(assets / "private-logo.png") as image:
        image = image.convert("RGBA")
        image.putpixel((0, 0), (10, 20, 30, 255))
        image.save(assets / "private-logo.png")
    after = planner.plan(definitions, translations, categories=["Based"])
    assert [a["poster_id"] for a, b in zip(before["jobs"], after["jobs"], strict=True) if a["render_fingerprint"] != b["render_fingerprint"]] == [definitions[0].id]


@pytest.mark.parametrize("stem", ["..", ".", "a/..", "../outside", "a/CON", "C:/bad", "a/space "])
def test_poster_stems_still_reject_unsafe_components(stem):
    value = load_catalog(["Based"])[0].data
    value["composer"]["out_name"] = stem
    with pytest.raises(BulkError):
        Definition.create(value)


def test_final_dot_in_real_studio_stem_is_preserved(catalog, translations):
    item = next(item for item in catalog[1] if item.category == "Studio" and item.data["composer"]["out_name"] == "A.C.G.T.")
    result = Planner().plan((item,), translations, posters=[item.id])
    assert result["jobs"][0]["local_relative"].endswith("/A.C.G.T..jpg")


def test_cross_stage_output_collision_is_rejected_before_state_or_render(translations, tmp_path):
    first, parent = load_catalog(["Based"])[:2]
    value = first.data
    value["output"] = parent.data["output"]
    value["composer"]["out_name"] = parent.data["composer"]["out_name"]
    value["composer"]["logo"] = "defaults-en/" + parent.data["output"]["remote_paths"]["en"]
    value["dependencies"] = [{"poster_id": parent.id, "input": "logo"}]
    config = Config(cache_dir=tmp_path / "cache", workspace_dir=tmp_path / "work", output_dir=tmp_path / "output")
    with pytest.raises(BulkError, match="across dependency stages"):
        generate((Definition.create(value), parent), translations, config=config, posters=[first.id])
    assert not config.cache_dir.exists() and not config.output_dir.exists()


def test_real_composer_interruption_and_new_process_resume(translations, tmp_path):
    import sqlite3
    definitions = load_catalog(["Based"])[:2]
    config = Config(cache_dir=tmp_path / "cache", workspace_dir=tmp_path / "work", output_dir=tmp_path / "output")
    class CancelAfterDispatch:
        def is_set(self):
            with sqlite3.connect(config.cache_dir / "state.sqlite") as db:
                return bool(db.execute("SELECT 1 FROM jobs WHERE status='running'").fetchone())
    options = dict(config=config, categories=["Based"], limits=WorkerLimits(workers=2))
    interrupted = generate(definitions, translations, cancel=CancelAfterDispatch(), **options)
    assert interrupted["status"] == "incomplete"
    # Cancellation may retain a fully verified job completed before the next
    # cancellation poll; it must never expose a partial final image.
    retained = list(config.output_dir.rglob("*.jpg"))
    assert len(retained) < 2
    for path in retained:
        with Image.open(path) as image:
            image.load()
            assert image.format == "JPEG" and image.size == (2000, 3000)
    resumed = generate(definitions, translations, **options)
    assert resumed["status"] == "verified"
    assert len(resumed["manifest"]["jobs"]) == 2
    warm = generate(definitions, translations, **options)
    assert warm["stages"][0]["execution"]["metrics"]["executed"] == 0
