from copy import deepcopy
import json
from pathlib import Path

import pytest
import yaml

from create_defaults.bulk.common import BulkError, canonical, fingerprint, load_yaml, relative_path
from create_defaults.bulk.config import Config, LANGUAGES, select_categories, select_languages
from create_defaults.bulk.definitions import Definition, load_definitions
from create_defaults.bulk.planner import Planner, effective_parameters, validate_manifest
from create_defaults.bulk.translations import Translations, legacy_case, replace_placeholders


BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent


@pytest.fixture
def definitions():
    return load_definitions(sorted(path for path in (BASE / "examples").glob("*.yml") if path.name != "profiles.yml"), profiles_path=BASE / "examples/profiles.yml")


@pytest.fixture
def translations():
    return Translations({"en": ROOT / "fixtures/english/en.yml"})


def test_real_definitions_plan_deterministically_and_preserve_effective_parameters(definitions, translations):
    planner = Planner()
    first = planner.plan(definitions, translations, categories=["All"])
    second = planner.plan(tuple(reversed(definitions)), translations, categories=["All"])
    assert canonical(first) == canonical(second)
    assert len(first["jobs"]) == 4
    original = json.loads((ROOT / "phase2/evidence/sample-manifest.json").read_text())
    expected = {job["poster_id"]: job for job in original["jobs"]}
    for job in first["jobs"]:
        assert job["parameters"] == expected[job["poster_id"]]["effective"]
        assert job["remote_relative"] == expected[job["poster_id"]]["remote_relative"]
    assert first["jobs"][0]["raw_parameters"]["font_size"] == 0
    assert first["jobs"][0]["parameters"]["font_size"] == 250
    assert first["jobs"][-1]["parameters"]["font_size"] == 409


def test_display_name_changes_not_identity(definitions, translations):
    before = Planner().plan(definitions, translations, posters=[definitions[0].id])
    value = definitions[0].data
    value["display_name"] = "Edited title"
    after = Planner().plan((Definition.create(value),), translations, posters=[definitions[0].id])
    assert before["jobs"][0]["id"] == after["jobs"][0]["id"]
    assert before["jobs"][0]["definition_fingerprint"] != after["jobs"][0]["definition_fingerprint"]
    assert before["jobs"][0]["render_fingerprint"] == after["jobs"][0]["render_fingerprint"]


@pytest.mark.parametrize("change", [lambda d: d.update(unknown=True), lambda d: d["composer"].update(font_size=True), lambda d: d["composer"].update(font_size=250.0), lambda d: d["composer"].pop("clean")])
def test_strict_definition_schema(definitions, change):
    value = definitions[0].data
    change(value)
    with pytest.raises(BulkError):
        Definition.create(value)


@pytest.mark.parametrize("path", ["../outside", "/outside", "a//b", "C:/x", "a\\b", "NUL.txt", "x/CON", "x/../b", "a/space ", "x:ads"])
def test_portable_paths(path):
    with pytest.raises(BulkError):
        relative_path(path)


@pytest.mark.parametrize("text", ["a: 1\na: 2", "a: &a [1]\nb: *a", "!!python/object:os.system {}", "a: [bad", "a: .nan"])
def test_unsafe_yaml(tmp_path, text):
    path = tmp_path / "data.yml"
    path.write_text(text)
    with pytest.raises((BulkError, ValueError)):
        load_yaml(path)


def test_shared_profile_and_language_override(tmp_path, definitions):
    value = definitions[0].data
    identity = value.pop("id")
    source, category, display = value.pop("source"), value.pop("category"), value.pop("display_name")
    profile = tmp_path / "profiles.yml"
    profile.write_text(yaml.safe_dump({"schema_version": 1, "profiles": {"base": value}}))
    item = {"id": identity, "source": source, "category": category, "display_name": display, "extends": "base", "overrides": [{"language": "en", "changes": {"composer": {"text_offset": 100}}}]}
    path = tmp_path / "franchise.yml"
    path.write_text(yaml.safe_dump({"schema_version": 1, "category": category, "definitions": [item]}))
    loaded = load_definitions([path], profiles_path=profile)[0]
    assert loaded.for_language("en").data["composer"]["text_offset"] == 100
    assert loaded.data["composer"]["text_offset"] == 0
    bad = yaml.safe_load(profile.read_text())
    bad["profiles"]["unused"] = {"extends": "base"}
    profile.write_text(yaml.safe_dump(bad))
    with pytest.raises(BulkError):
        load_definitions([path], profiles_path=profile)


def test_retired_splatter_cannot_be_active(definitions):
    value = definitions[1].data
    value["source"]["row_sha256"] = "dfe1647bfcc9280f73712a32ef0235dca741f6d96a8569649eda33c9b691e18f"
    with pytest.raises(BulkError, match="D02"):
        Definition.create(value)


def test_duplicate_output_and_manifest_tampering_rejected(definitions, translations):
    value = definitions[0].data
    value["id"] = "another.identity"
    duplicate = Definition.create(value)
    with pytest.raises(BulkError, match="output"):
        Planner().plan((definitions[0], duplicate), translations, categories=["All"])
    manifest = Planner().plan(definitions, translations, categories=["All"])
    manifest["jobs"][0]["parameters"]["base_color"] = "#123456"
    with pytest.raises(BulkError):
        validate_manifest(manifest)


def test_dependency_cycles_and_unmaterialized_parent_rejected(definitions, translations):
    first, second = definitions[0].data, definitions[1].data
    first["dependencies"] = [{"poster_id": second["id"], "input": "logo"}]
    second["dependencies"] = [{"poster_id": first["id"], "input": "logo"}]
    with pytest.raises(BulkError, match="Cyclic"):
        Planner().plan((Definition.create(first), Definition.create(second)), translations, categories=["All"])
    second["dependencies"] = []
    with pytest.raises(BulkError, match="verified parent"):
        Planner().plan((Definition.create(first), Definition.create(second)), translations, categories=["All"])


def test_translation_changes_invalidate_captured_fitting(definitions, tmp_path):
    path = tmp_path / "en.yml"
    path.write_text("key_names:\n  ACTION: A different translation\n")
    with pytest.raises(BulkError, match="Captured fitting"):
        Planner().plan(definitions, Translations({"en": path}), posters=["genre.action"])


def test_exact_language_selectors_and_aliases():
    assert select_languages(LANGUAGES) == LANGUAGES
    assert select_categories(["genres", "Genre", "Awards", "award"]) == ("Genre", "Awards")
    with pytest.raises(BulkError):
        select_languages(["pt_BR"])


def test_config_precedence_and_writable_root_isolation(tmp_path):
    path = tmp_path / "config.yml"
    path.write_text("remote_ttl: 20\n")
    assert Config.load(file=path, environment={"DEFAULTS_REMOTE_TTL": "10"}, remote_ttl=30).remote_ttl == 30
    assert Config.load(file=path, environment={"DEFAULTS_REMOTE_TTL": "10"}).remote_ttl == 20
    with pytest.raises(BulkError):
        Config(cache_dir=ROOT / "logos_genre/cache")


def test_translation_lookup_case_templates_fallback_and_source_identity(tmp_path):
    path = tmp_path / "en.yml"
    path.write_text("key_names:\n  action: MiXeD\ncollections:\n  test: '<<one>> / <<two>>'\n")
    service = Translations({"en": path})
    caption = {"mode": "translation", "key": "KEY_NAMES.ACTION", "text": "", "template_key": "collections.test", "case": "upper", "direction": "auto", "fallback": None}
    result = service.resolve(caption, "en")
    assert result.text == "MIXED / MIXED"
    assert result.trace[0]["source_sha256"] == service.hashes["en"]
    caption.update(key="missing", template_key=None)
    with pytest.raises(BulkError):
        service.resolve(caption, "en")
    caption["fallback"] = {"id": "reviewed-fallback", "reviewer": "maintainer", "reason": "Explicit literal", "policy_version": "v1", "text": "Shared", "language": None, "key": None}
    assert service.resolve(caption, "fr").text == "SHARED"
    assert service.resolve(caption, "fr").trace[0]["fallback"]["id"] == "reviewed-fallback"
    caption["fallback"]["reviewer"] = ""
    with pytest.raises(BulkError):
        service.resolve(caption, "en")


def test_shared_caption_does_not_require_unavailable_file(tmp_path):
    caption = {"mode": "shared", "key": None, "text": "2020", "template_key": None, "case": "exact", "direction": "auto", "fallback": None}
    assert Translations({}).resolve(caption, "ar").text == "2020"
    assert legacy_case("Stra\u00dfe", "upper") == "STRA\u00dfE"
    assert replace_placeholders("a<<one>>b<<two>>c", "$$:$&:${0}:$1:\\x") == "a$:<<one>>:<<one>>:$1:\\xb$:<<two>>:<<two>>:$1:\\xc"


def test_raw_legacy_quirks_preserved(definitions):
    raw = definitions[0].data["composer"]
    raw.update(logo_offset="+-500", font_size=1000, logo_resize=0, gradient=100, border_width=0)
    effective = effective_parameters(raw)
    assert (effective["logo_offset"], effective["font_size"], effective["logo_resize"], effective["gradient"], effective["border_width"]) == (-500, 250, 2000, 1, 15)
    assert raw["logo_offset"] == "+-500" and raw["font_size"] == 1000


def test_named_generator_registry_never_evaluates_yaml_code(definitions, translations):
    value = definitions[0].data
    value["generator"] = {"name": "test.named-rule", "version": 1, "parameters": {"offset": 10}}
    source = Definition.create(value)
    with pytest.raises(BulkError, match="not registered"):
        Planner().plan((source,), translations, posters=[source.id])
    def rule(definition, parameters):
        data = definition.data
        data["generator"] = None
        data["composer"]["logo_offset"] = parameters["offset"]
        yield Definition.create(data)
    result = Planner(generators={("test.named-rule", 1): rule}).plan((source,), translations, posters=[source.id])
    assert result["jobs"][0]["parameters"]["logo_offset"] == 10
    assert result["jobs"][0]["generator_origin"]["specification"]["version"] == 1


def test_new_authored_definition_needs_no_fabricated_powershell_row(definitions):
    value = definitions[0].data
    value["source"] = {"kind": "authored", "path": "definitions/franchise.yml", "line": None, "row_sha256": None}
    assert Definition.create(value).data["source"]["row_sha256"] is None


def test_overlay_contract_kind_is_typed_and_cannot_be_claimed_render_ready(definitions, translations):
    manifest = Planner().plan((definitions[0],), translations, posters=[definitions[0].id])
    job = manifest["jobs"][0]
    parameters = {"input": "logos_genre/Action.png", "box": [285, 85], "trim": False, "colorspace": "sRGB", "strip_metadata": True, "format": "PNG", "resampling": "pending-package-d-equivalence"}
    job.update(kind="overlay", raw_parameters=parameters, parameters=parameters, render_ready=False)
    job["render_fingerprint"] = fingerprint({key: job[key] for key in ("kind", "parameters", "inputs", "dependencies", "language_behavior")} | {"renderer": manifest["renderer"]})
    manifest["sha256"] = fingerprint({key: value for key, value in manifest.items() if key != "sha256"})
    validate_manifest(manifest)
    job["render_ready"] = True
    manifest["sha256"] = fingerprint({key: value for key, value in manifest.items() if key != "sha256"})
    with pytest.raises(BulkError):
        validate_manifest(manifest)
