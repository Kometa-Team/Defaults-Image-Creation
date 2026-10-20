"""Package A contracts only; no network, shell capture, or full poster rendering."""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from create_defaults.create_poster import ROOT, PosterOptions, digest
from create_defaults.phase2.audit import collision_key, color_inventory
from create_defaults.phase2.definitions import (
    DefinitionError, HERE, LANGUAGES, read_yaml, safe_path, schema_check, validate_document, validate_file,
)
from create_defaults.poster_fixtures import extract_rows
from create_defaults.validation_manifest import fingerprint, text_digest
from unittest.mock import patch


EXAMPLES = HERE / "examples/current-posters.yml"


class DefinitionTests(unittest.TestCase):
    def setUp(self):
        self.document = read_yaml(EXAMPLES)

    def test_real_examples_and_inheritance_are_nonmutating(self):
        original = deepcopy(self.document)
        result = validate_document(self.document)
        self.assertEqual(len(result), 4)
        self.assertEqual(self.document, original)
        self.assertTrue(all("extends" not in item for item in result))
        self.assertEqual(result[0]["layout"]["logo_resize"], 1600)
        self.assertEqual(result[1]["layout"]["logo_resize"], 1800)

    def test_unknown_schema_rejected(self):
        self.document["schema_version"] = 2
        with self.assertRaises(DefinitionError):
            validate_document(self.document)

    def test_unknown_definition_and_nested_keys_rejected(self):
        for key, value in (("unrecognized", True), ("layout", {"typo_offset": 8})):
            with self.subTest(key=key):
                document = deepcopy(self.document)
                document["definitions"][0][key] = value
                with self.assertRaises(DefinitionError):
                    validate_document(document)

    def test_unused_invalid_profile_rejected(self):
        self.document["profiles"]["unused"] = {"unrecognized": True}
        with self.assertRaises(DefinitionError):
            validate_document(self.document)

    def test_unknown_profile_rejected(self):
        self.document["definitions"][0]["extends"] = "missing"
        with self.assertRaisesRegex(DefinitionError, "Unknown profile"):
            validate_document(self.document)

    def test_profile_cycles_and_chains_are_not_hidden(self):
        self.document["profiles"]["legacy-poster"]["extends"] = "legacy-poster"
        with self.assertRaisesRegex(DefinitionError, "chains"):
            validate_document(self.document)

    def test_duplicate_ids_rejected_independent_of_filename(self):
        self.document["definitions"][1]["id"] = self.document["definitions"][0]["id"]
        with self.assertRaisesRegex(DefinitionError, "Duplicate logical ID"):
            validate_document(self.document)

    def test_stable_id_does_not_depend_on_display_name(self):
        before = validate_document(self.document)[0]["id"]
        self.document["definitions"][0]["display_name"] = "Editorial display-only change"
        self.assertEqual(validate_document(self.document)[0]["id"], before)

    def test_types_do_not_coerce_strings_or_booleans(self):
        for value in ("409", True):
            with self.subTest(value=value):
                document = deepcopy(self.document)
                document["definitions"][-1]["typography"]["point_size"] = value
                with self.assertRaises(DefinitionError):
                    validate_document(document)

    def test_all_exact_language_identifiers_allowed_but_not_claimed_rendered(self):
        self.document["definitions"][0]["languages"] = list(LANGUAGES)
        self.assertEqual(validate_document(self.document)[0]["languages"], list(LANGUAGES))
        for invalid in ("nb-NO", "pt_BR", "EN", "xx"):
            with self.subTest(invalid=invalid):
                self.document["definitions"][0]["languages"] = [invalid]
                with self.assertRaises(DefinitionError):
                    validate_document(self.document)

    def test_path_traversal_absolute_ads_reserved_and_windows_paths_rejected(self):
        for path in ("../x.jpg", "/x.jpg", "a//x.jpg", "a/./x.jpg", "C:/x.jpg", "a\\x.jpg", "NUL.jpg", "a/CON.txt", "a./x.jpg", "a/x.jpg ", "a/x:stream", "a/\x00x.jpg"):
            with self.subTest(path=path):
                self.assertFalse(safe_path(path))
                self.document["definitions"][0]["assets"]["logo"] = path
                with self.assertRaises(DefinitionError):
                    validate_document(self.document)

    def test_case_and_unicode_output_collisions_rejected(self):
        for first, second in (("Action.jpg", "ACTION.jpg"), ("Caf\u00e9.jpg", "Cafe\u0301.jpg")):
            with self.subTest(first=first):
                document = deepcopy(self.document)
                document["definitions"][0]["output"] = {"directory": "genre", "filename": first}
                document["definitions"][1]["output"] = {"directory": "genre", "filename": second}
                with self.assertRaisesRegex(DefinitionError, "Output collision"):
                    validate_document(document)

    def test_identical_output_names_in_distinct_languages_are_not_collisions(self):
        self.document["definitions"][0]["output"] = deepcopy(self.document["definitions"][1]["output"])
        self.document["definitions"][0]["languages"] = ["fr"]
        validate_document(self.document)

    def test_translation_fallback_must_be_explicit(self):
        self.document["definitions"][1]["caption"] = {"key": None}
        with self.assertRaisesRegex(DefinitionError, "require a key"):
            validate_document(self.document)
        self.document["definitions"][1]["caption"] = {"key": "key_names.ACTION", "fallback": "literal"}
        with self.assertRaisesRegex(DefinitionError, "requires explicit text"):
            validate_document(self.document)

    def test_fixed_font_cannot_accidentally_become_fitted(self):
        item = validate_document(self.document)[-1]
        self.assertEqual((item["typography"]["mode"], item["typography"]["point_size"]), ("fixed", 409))
        self.document["definitions"][-1]["typography"]["mode"] = "fit"
        with self.assertRaisesRegex(DefinitionError, "hide a fixed"):
            validate_document(self.document)

    def test_random_color_not_falsely_persisted_as_explicit(self):
        self.document["definitions"][0]["background"] = {"mode": "legacy_random", "hex": "#123456"}
        with self.assertRaisesRegex(DefinitionError, "explicit backgrounds"):
            validate_document(self.document)

    def test_dynamic_expansion_is_not_pretended_implemented(self):
        self.document["definitions"][0]["variants"] = ["made-up-generator"]
        with self.assertRaises(DefinitionError):
            validate_document(self.document)

    def test_yaml_duplicate_keys_aliases_and_unsafe_tags_rejected(self):
        for content in ("schema_version: 1\nschema_version: 2", "a: &a [x]\nb: *a", "!!python/object:os.system {}", "[bad"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "definition.yml"
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(DefinitionError):
                    read_yaml(path)

    def test_actual_splatter_definitions_are_both_retained_and_blocked(self):
        definitions = []
        source_rows = [item for item in extract_rows() if item["category"] == "Genre" and item["row"]["out_name"] == "Splatter"]
        self.assertEqual(len(source_rows), 2)
        for source in source_rows:
            item = deepcopy(self.document["definitions"][1])
            item.update(id=f"genre.splatter-{source['line']}", display_name="Splatter",
                        source={"path": "create_default_posters.ps1", "line": source["line"], "row_sha256": fingerprint(source["row"])},
                        assets={"logo": "logos_genre/Splatter.png"}, caption={"key": "key_names.SPLATTER"},
                        background={"hex": source["row"]["base_color"]}, effects={"white_wash": source["row"]["white_wash"] == "1"},
                        output={"directory": "genre", "filename": "Splatter.jpg"})
            definitions.append(item)
        self.document["definitions"] = definitions
        with self.assertRaisesRegex(DefinitionError, "Output collision"):
            validate_document(self.document)


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = json.loads((HERE / "evidence/current-source-audit.json").read_text(encoding="utf-8"))
        cls.colors = json.loads((HERE / "evidence/historical-colors.json").read_text(encoding="utf-8"))
        cls.manifest = json.loads((HERE / "evidence/sample-manifest.json").read_text(encoding="utf-8"))
        cls.rows = extract_rows()

    def test_current_source_hashes_and_coverage_not_historical_constants(self):
        for name, expected in self.audit["source_text_sha256"].items():
            self.assertEqual(text_digest(ROOT / name), expected)
        summary = self.audit["summary"]
        self.assertEqual(summary["literal_rows"], len(self.rows))
        self.assertEqual(summary["covered_literal_rows"], len(self.rows))
        self.assertEqual(summary["effective_jobs"], sum(item["effective_jobs"] for item in self.audit["categories"].values()))
        self.assertEqual({row["category"] for row in self.rows}, set(self.audit["categories"]))

    def test_structural_inventory_languages_aliases_and_dispatch_are_source_bound(self):
        structure = json.loads((HERE / "evidence/source-structure.json").read_text(encoding="utf-8"))
        self.assertEqual(structure["source_sha256"], self.audit["source_sha256"]["create_default_posters.ps1"])
        self.assertEqual(structure["supported_languages"], list(LANGUAGES))
        categories = set(self.audit["categories"]) | {"Overlays"}
        self.assertEqual(set(structure["all_dispatch"]), categories)
        self.assertEqual(set(structure["aliases"].values()), categories)
        self.assertEqual(len(structure["functions"]), len(categories))
        self.assertTrue(all(item["translation_calls"] for item in structure["functions"] if item["category"] != "Overlays"))

    def test_stale_structural_inventory_fails_before_any_export(self):
        from create_defaults.phase2.audit import audit
        with patch("create_defaults.phase2.audit.validate_manifest"):
            with self.assertRaisesRegex(ValueError, "Structural audit is stale"):
                audit({}, {"source_sha256": "0" * 64})

    def test_color_registry_is_exactly_literal_background_fields(self):
        expected = Counter(row["row"]["base_color"].upper() for row in self.rows if row["row"]["base_color"])
        actual = Counter(item["hex"] for item in self.colors["assignments"])
        self.assertEqual(actual, expected)
        self.assertEqual(len(self.colors["excluded_backgrounds"]), sum(not row["row"]["base_color"] for row in self.rows))
        for item in self.colors["assignments"]:
            self.assertEqual(item["approval"], "historical-unreviewed")

    def test_color_extractor_does_not_count_text_or_border_colors(self):
        row = deepcopy(self.rows[0])
        row["row"].update(base_color="#123456", font_color="#ABCDEF", border_color="#FEDCBA")
        result = color_inventory([row], [])
        self.assertEqual([item["hex"] for item in result["assignments"]], ["#123456"])

    def test_direct_and_generated_explicit_colors_not_omitted_or_approved(self):
        groups = self.colors["generated_assignments"]
        self.assertTrue({"#DC9924", "#1AA931", "#2444D1", "#FFFFFF"}.issubset({item["hex"] for item in groups}))
        self.assertTrue(all(item["approval"] == "historical-unreviewed" for item in groups))
        self.assertEqual(sum(item["random_base_jobs"] for item in self.audit["categories"].values()), 22 * len(self.colors["excluded_backgrounds"]))

    def test_background_use_counts_do_not_charge_generated_overrides_to_literal_colors(self):
        records = [*self.colors["assignments"], *self.colors["excluded_backgrounds"], *self.colors["generated_assignments"]]
        self.assertEqual(sum(item["effective_jobs"] for item in records), self.audit["summary"]["effective_jobs"])
        last_year = next(item for item in self.colors["assignments"] if item["category"] == "Year" and item["name"] == "2029")
        self.assertEqual(last_year["effective_jobs"], 1)

    def test_duplicates_are_observed_not_automatically_approved_exceptions(self):
        grouped = Counter(item["hex"] for item in self.colors["assignments"])
        self.assertEqual({color for color, count in grouped.items() if count > 1}, {item["hex"] for item in self.colors["duplicate_groups"]})
        self.assertTrue(all("require maintainer" in item["status"] for item in self.colors["duplicate_groups"]))
        grouped.update(item["hex"] for item in self.colors["generated_assignments"])
        self.assertEqual({color for color, count in grouped.items() if count > 1},
                         {item["hex"] for item in self.colors["all_explicit_duplicate_groups"]})

    def test_historical_rendering_evidence_is_distinct_from_the_current_correction(self):
        comparison = self.audit["historical_comparison"]
        self.assertEqual(len(comparison["changed_jobs"]), 1)
        change = comparison["changed_jobs"][0]
        self.assertEqual(change["old_name"], "Death in Paradise (2911)")
        self.assertEqual(change["new_name"], "Death in Paradise (2011)")

    def test_overlay_globs_count_files_not_operations(self):
        from create_defaults.bulk.asset_cases import historical
        for item in self.audit["overlays"]:
            directory = ROOT / str(Path(item["input_pattern"]).parent)
            actual = {path.relative_to(ROOT).as_posix() for path in directory.iterdir() if path.suffix.lower() == ".png"}
            # Frozen observations retain their historical spellings; only the
            # explicit byte-preserving source-case ledger can bridge to today.
            expected = {historical(ROOT, path).relative_to(ROOT).as_posix() for path in item["inputs"]}
            self.assertEqual(expected, actual)
            self.assertEqual(item["matching_files"], len(actual))
        self.assertEqual(self.audit["summary"]["overlay_file_transforms"], sum(item["matching_files"] for item in self.audit["overlays"]))

    def test_inactive_legacy_path_is_not_required_missing_logo(self):
        self.assertEqual(self.audit["assets"]["missing_inputs"], [])
        self.assertIn("#D19068", self.audit["assets"]["inactive_missing_inputs"])

    def test_sample_manifest_schema_complete_composer_parameters_and_fingerprints(self):
        schema_check(self.manifest, "manifest-v1.schema.json")
        for job in self.manifest["jobs"]:
            self.assertEqual(set(job["effective"]), set(PosterOptions.__dataclass_fields__))
            payload = {key: job[key] for key in ("language", "effective", "canvas", "inputs")}
            self.assertEqual(fingerprint(payload | {"renderer": self.manifest["renderer"]}), job["spec_sha256"])
            for asset in job["inputs"]:
                self.assertEqual(digest(ROOT / asset["path"]), asset["sha256"])

    def test_examples_represent_actual_source_rows_and_capture_parameters(self):
        definitions = {item["id"]: item for item in validate_file(EXAMPLES)}
        for job in self.manifest["jobs"]:
            definition, actual = definitions[job["poster_id"]], job["effective"]
            row = next(item for item in self.rows if item["line"] == definition["source"]["line"])
            self.assertEqual(fingerprint(row["row"]), definition["source"]["row_sha256"])
            for key in ("logo_offset", "logo_resize", "text_offset"):
                self.assertEqual(definition["layout"][key], actual[key])
            for key, value in definition["effects"].items():
                self.assertEqual(value, actual[key])
            self.assertEqual(definition["font"]["file"], actual["font"])
            self.assertEqual(definition["assets"]["logo"], actual["logo"])
            self.assertEqual(definition["background"]["hex"], actual["base_color"])
            self.assertEqual(definition["typography"]["color"], actual["font_color"])
            self.assertEqual(definition["output"]["directory"] + "/" + definition["output"]["filename"], job["remote_relative"])
        numeric = next(job for job in self.manifest["jobs"] if job["poster_id"] == "year.2020")
        self.assertEqual(numeric["effective"]["font_size"], 409)
        corrected = next(job for job in self.manifest["jobs"] if job["poster_id"].startswith("franchise."))
        self.assertIn("2011", corrected["remote_relative"])
        self.assertNotIn("2911", corrected["remote_relative"])

    def test_manifest_unknown_parameters_and_absolute_paths_rejected(self):
        for field, value in (("unknown", 1), ("logo", "C:/private/file.png")):
            with self.subTest(field=field):
                manifest = deepcopy(self.manifest)
                manifest["jobs"][0]["effective"][field] = value
                with self.assertRaises(DefinitionError):
                    schema_check(manifest, "manifest-v1.schema.json")

    def test_reports_have_no_personal_paths_or_credentials(self):
        for path in (HERE / "evidence").glob("*.json"):
            content = path.read_text(encoding="utf-8").casefold()
            for forbidden in ("c:/users/", "c:\\\\users\\\\", "bearer ", "ghp_"):
                self.assertNotIn(forbidden, content)

    def test_collision_key_preserves_display_path_separately(self):
        self.assertEqual(collision_key("Caf\u00e9.jpg"), collision_key("CAFE\u0301.JPG"))


if __name__ == "__main__":
    unittest.main()
