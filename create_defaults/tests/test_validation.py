import gzip
from copy import deepcopy
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image
import yaml

from create_defaults.create_poster import ROOT, PosterOptions, digest
from create_defaults.compare_poster_renderers import compare_images, measured
from create_defaults import validation_batch as batch
from create_defaults import validation_manifest as manifest
from create_defaults import revalidate_grayscale as grayscale
from create_defaults.validation_review import review_summary
from create_defaults.review_validation_groups import warning_groups, warning_rank, write_groups, write_ranked_warnings
from create_defaults.poster_fixtures import extract_rows


class WorkflowBoundaryTests(unittest.TestCase):
    def test_ci_is_read_only_pinned_python_only_and_targets_main(self):
        workflow = yaml.load((ROOT.parent / ".github/workflows/default-poster-validation.yml").read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(workflow["on"], {"pull_request": {"branches": ["main"]}})
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        job = workflow["jobs"]["python-validation"]
        self.assertEqual(job["runs-on"], "ubuntu-latest")
        self.assertNotIn("permissions", job)
        actions = [step for step in job["steps"] if "uses" in step]
        self.assertEqual(len(actions), 2)
        for step in actions:
            self.assertRegex(step["uses"], r"^actions/(checkout|setup-python)@[0-9a-f]{40}$")
        self.assertEqual(actions[0]["with"]["persist-credentials"], "false")
        self.assertEqual(actions[1]["with"]["python-version"], "3.13")
        commands = "\n".join(step.get("run", "") for step in job["steps"])
        for required in ("pip install", "compileall", "unittest discover", "validation_manifest.py --check", "git diff --check"):
            self.assertIn(required, commands)
        for forbidden in ("pwsh", "magick", "validation_batch.py", "Default-Images", "git push"):
            self.assertNotIn(forbidden, commands)


class EffectiveParameterTests(unittest.TestCase):
    def test_deferred_fitting_deduplicates_clamps_and_resumes_without_magick(self):
        fit = {"text": "TIMELINE ORDER", "font_path": (ROOT / "fonts/BebasNeue-Regular.ttf").as_posix(),
               "box": [1600, 1000], "minimum": 100, "maximum": 154, "deferred": True}
        capture = {"jobs": [{"fitting": deepcopy(fit), "raw_parameters": {"font_size": "154"}} for _ in range(2)]}
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(manifest.subprocess, "run", return_value=SimpleNamespace(stdout="999", stderr="")) as run:
                resolved = manifest.resolve_capture_fitting(deepcopy(capture), temporary, "existing-magick", workers=1)
                self.assertEqual(run.call_count, 1)
                self.assertEqual(resolved["jobs"][0]["raw_parameters"]["font_size"], "154")
                self.assertFalse(resolved["jobs"][0]["fitting"]["deferred"])
            with patch.object(manifest.subprocess, "run", side_effect=AssertionError("Cache should avoid subprocess")):
                self.assertEqual(manifest.resolve_capture_fitting(capture, temporary, "existing-magick", workers=1), resolved)

    def test_exact_coercions_and_frozen_random_color(self):
        raw = dict(logo="transparent.png", font="BoecklinsUniverse", logo_resize="0", font_size="700",
                   white_wash="1", border="0", out_name="blue/genre")
        first, choices = manifest.effective_parameters(raw, 17)
        second, _ = manifest.effective_parameters(raw, 17)
        self.assertEqual(first, second)
        self.assertEqual(first["logo_resize"], 2000)
        self.assertEqual(first["font_size"], 250)
        self.assertTrue(first["white_wash"])
        self.assertFalse(first["border"])
        self.assertEqual(len(choices), 3)
        self.assertRegex(first["base_color"], r"^#[0-9A-F]{6}$")
        self.assertNotEqual(first["base_color"], manifest.effective_parameters(raw, 18)[0]["base_color"])

    def test_unknown_or_escaping_parameters_rejected(self):
        for values in ({"not_a_composer_parameter": 1}, {"logo": "../README.md"}, {"border": "maybe"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                manifest.effective_parameters(values, 0)

    def test_noncanonical_legacy_offset_is_preserved_in_frozen_parameters(self):
        values, notes = manifest.effective_parameters({"logo_offset": "+-500", "base_color": "#112233"}, 0)
        self.assertEqual(values["logo_offset"], "+-500")
        self.assertTrue(any("retained verbatim" in note for note in notes))

    def test_runtime_uses_exact_bundled_font_bytes_and_absolute_assets(self):
        job = {"parameters": {"logo": "transparent.png", "font": "Plus Jakarta Sans Bold"},
               "font": {"path": "fonts/PlusJakartaSans-Bold.ttf"}}
        values = manifest.runtime_parameters(job)
        self.assertEqual(Path(values["font"]), ROOT / "fonts/PlusJakartaSans-Bold.ttf")
        self.assertEqual(Path(values["logo"]), ROOT / "transparent.png")

    def test_runtime_preserves_prevalidation_numeric_arguments(self):
        job = {"parameters": {"logo": "transparent.png", "logo_resize": 2000, "font_size": 250},
               "raw_parameters": {"logo_resize": 0, "font_size": "700"},
               "font": {"path": "fonts/Comfortaa-Medium.ttf"}}
        values = manifest.runtime_parameters(job)
        self.assertEqual(values["logo_resize"], 0)
        self.assertEqual(values["font_size"], 700)
        self.assertEqual(job["parameters"]["logo_resize"], 2000)

    def test_portable_metadata_has_no_personal_checkout_paths(self):
        value = {"path": str(ROOT / "fonts"), "list": [ROOT.as_posix() + "/transparent.png"]}
        portable = manifest.portable(value, ROOT)
        self.assertEqual(portable, {"path": "{ASSETS}/fonts", "list": ["{ASSETS}/transparent.png"]})
        doubled = str(ROOT / "fonts").replace("\\", "\\\\")
        self.assertEqual(manifest.portable(doubled, ROOT), "{ASSETS}/fonts")

    def test_line_ending_normalization_does_not_mask_source_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            a, b = Path(temporary) / "a", Path(temporary) / "b"
            a.write_bytes(b"one\r\ntwo\r\n")
            b.write_bytes(b"one\ntwo\n")
            self.assertEqual(manifest.text_digest(a), manifest.text_digest(b))
            b.write_bytes(b"one\nchanged\n")
            self.assertNotEqual(manifest.text_digest(a), manifest.text_digest(b))

    def test_powershell_output_paths_keep_zero_one_and_many_targets(self):
        self.assertEqual(manifest.as_list(None), [])
        self.assertEqual(manifest.as_list("aspect/1.33.jpg"), ["aspect/1.33.jpg"])
        self.assertEqual(manifest.as_list(["a.jpg", "b.jpg"]), ["a.jpg", "b.jpg"])


class FrozenInventoryTests(unittest.TestCase):
    def test_only_wildcard_fitting_caption_preserves_verified_original_cap(self):
        value = manifest.load_manifest(ROOT / "fixtures/effective-jobs-en-monoton-ofl.json.gz")
        special = [job for job in value["jobs"] if job.get("fitting")
                   and any(character in job["fitting"]["text"] for character in "*?[]`")]
        self.assertEqual(len(special), 1)
        fit = special[0]["fitting"]
        self.assertEqual(fit["text"], "MIND-F**K")
        self.assertEqual((fit["minimum"], fit["maximum"]), (100, 250))
        self.assertEqual(fit["measured"], 338)
        # The isolated original fitting function measures 307 after its escaping.
        self.assertEqual(fit["point_size"], min(fit["maximum"], max(fit["minimum"], 307)))
        self.assertEqual(special[0]["parameters"]["font_size"], 250)

    def test_dynamic_award_mutations_keep_original_literal_lineage(self):
        value = manifest.load_manifest(ROOT / "fixtures/effective-jobs-en-monoton-ofl.json.gz")
        mutations = [job for job in value["jobs"] if job.get("effective_source_row") and job["source_row"] != job["effective_source_row"]]
        self.assertEqual({job["parameters"]["out_name"] for job in mutations}, {"2016-2", "1930-2"})
        self.assertTrue(all(job["source"]["definition_line"] and job["dynamic"]["generated_name"] for job in mutations))
        self.assertEqual({job["source_row"]["out_name"] for job in mutations}, {"Choice", "Oscars"})

    def test_full_graph_and_noncanonical_inputs_are_preserved(self):
        value = manifest.load_manifest(ROOT / "fixtures/effective-jobs-en-monoton-ofl.json.gz")
        self.assertEqual(value["effective_composer_jobs"], 9958)
        self.assertEqual(sum(bool(job["generated_inputs"]) for job in value["jobs"]), 165)
        self.assertEqual(sum(job["parameters"]["logo_offset"] == "+-500" for job in value["jobs"]), 180)
        self.assertEqual(len(batch.dependency_levels(value["jobs"])), 2)
        self.assertEqual(len(value["same_queue_output_collisions"]), 1)
        self.assertEqual(len(value["same_queue_output_collisions"][0]["job_ids"]), 2)
        norwegian = next(job for job in value["jobs"] if job["category"] == "AudioLanguage" and job["parameters"]["out_name"] == "nb")
        self.assertEqual(norwegian["parameters"]["text"], "NORWEGIAN BOKM\u00c5L AUDIO")

    def test_frozen_manifest_covers_all_literal_rows_and_dynamic_jobs(self):
        path = ROOT / "fixtures/effective-jobs-en-monoton-ofl.json.gz"
        self.assertTrue(path.is_file(), "Generate the frozen manifest before accepting validation")
        value = manifest.load_manifest(path)
        self.assertTrue(manifest.validate_manifest(value))
        self.assertEqual(value["literal_definitions"], len(extract_rows()))
        self.assertEqual(value["covered_literal_definitions"], 3352)
        self.assertEqual(value["uncovered_literal_lines"], [])
        self.assertEqual(len(value["categories"]), 21)
        self.assertGreater(value["effective_composer_jobs"], 3352)
        self.assertTrue(any(job["definition_id"].startswith("direct-") for job in value["jobs"]))
        self.assertTrue(value["overlay_operations"])
        separators = [job for job in value["jobs"] if job["category"] == "Separators" and job["dynamic"]["color_loop"]]
        self.assertEqual(len({job["dynamic"]["color_loop"] for job in separators}), 22)
        self.assertTrue(all(job["parameters"]["text"] and "<<" not in job["parameters"]["text"] for job in separators))
        self.assertNotIn("TRANSLATION NOT FOUND", json.dumps(value))
        self.assertNotIn(str(ROOT), json.dumps(value))

    def test_approved_font_invocations_survive_real_bulk_capture(self):
        value = manifest.load_manifest(ROOT / "fixtures/effective-jobs-en-monoton-ofl.json.gz")
        jakarta = [job for job in value["jobs"] if job["font"]["path"] == "fonts/PlusJakartaSans-Bold.ttf"]
        bebas = [job for job in value["jobs"] if job["font"]["path"] == "fonts/BebasNeue-Regular.ttf"]
        self.assertEqual(len(jakarta), 11)
        self.assertTrue(all(job["parameters"]["font_size"] == 409 and job["fitting"] is None for job in jakarta))
        self.assertEqual(len(bebas), 9)
        self.assertTrue(all(job["fitting"]["maximum"] == 154 and job["parameters"]["font_size"] <= 154 for job in bebas))

    def test_monoton_manifest_revision_preserves_old_fixture_and_unrelated_jobs(self):
        previous = manifest.load_manifest(ROOT / "fixtures/effective-jobs-en.json.gz")
        current = manifest.load_manifest(ROOT / "fixtures/effective-jobs-en-monoton-ofl.json.gz")
        self.assertEqual(previous["sha256"], "cbd30b1cbbfdfc8e58fa88ae33ef5e1389d506795948e1acbde41ab810da19ba")
        self.assertNotEqual(current["sha256"], previous["sha256"])
        changed = []
        for before, after in zip(previous["jobs"], current["jobs"]):
            self.assertEqual(before["id"], after["id"])
            if before != after:
                changed.append(after)
                expected = deepcopy(before)
                expected["font"] = after["font"]
                expected.pop("sha256")
                self.assertEqual(manifest.fingerprint(expected), after["sha256"])
        self.assertEqual(len(changed), 11)
        self.assertTrue(all(job["font"]["path"] == "fonts/Monoton-Regular.ttf" for job in changed))
        self.assertTrue(all(job["font"]["sha256"] == "951c4cea65ffede784a7c9672feec5d329a7e1e12216c42d53ecf36c90d04dea" for job in changed))
        self.assertEqual(current["asset_hashes"], previous["asset_hashes"])
        self.assertEqual(current["overlay_operations"], previous["overlay_operations"])

    def test_manifest_fingerprint_detects_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "jobs.json.gz"
            data = {"schema": 1, "jobs": []}
            data["sha256"] = manifest.fingerprint(data)
            data["jobs"].append({"tampered": True})
            path.write_bytes(gzip.compress(manifest.canonical(data)))
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                manifest.load_manifest(path)


class GrayscaleRevisionTests(unittest.TestCase):
    def fixture(self, root):
        directory = root / "cases/gray"
        directory.mkdir(parents=True)
        legacy, python = directory / "legacy.jpg", directory / "python.jpg"
        Image.new("L", (40, 60), 50).save(legacy, "JPEG")
        Image.new("RGB", (40, 60), (50, 50, 50)).save(python, "JPEG")
        (directory / "legacy.log").write_text("Successful reference render")
        job = {"id": "gray", "sha256": "job", "canvas": [40, 60], "published_relatives": []}
        result = {"id": "gray", "job_sha256": "job", "run_key": "run", "complete": True,
                  "status": "failure", "notes": ["legacy: unexpected canvas/format/mode: (40, 60) JPEG L"],
                  "parameters": {"text": ""}, "images": {"python": dict(grayscale.picture_metadata(python),
                      report_file="python.jpg", full_resolution_retained=True)},
                  "comparisons": {"A-legacy-python": compare_images(legacy, python, directory, "A")},
                  "measurements": {engine: {"returncode": 0, "timed_out": False, "seconds": 1}
                                   for engine in ("legacy", "python")}}
        result["retained_artifacts"] = {path.name: digest(path) for path in directory.iterdir()}
        batch.atomic_json(directory / "result.json", result)
        result = json.loads((directory / "result.json").read_text())
        return job, result, directory, SimpleNamespace(report_dir=root, published_repo=None)

    def test_revision_preserves_original_pixels_numeric_metrics_and_measurements(self):
        with tempfile.TemporaryDirectory() as temporary:
            job, original, directory, args = self.fixture(Path(temporary))
            before = {name: digest(directory / name) for name in ("legacy.jpg", "python.jpg", "result.json")}
            revised = grayscale.correction(job, original, directory, args)
            self.assertEqual(revised["status"], "pass")
            self.assertEqual(revised["images"]["legacy"]["mode"], "L")
            self.assertEqual(revised["images"]["python"]["mode"], "RGB")
            self.assertEqual(revised["comparisons"], original["comparisons"])
            self.assertEqual(revised["measurements"], original["measurements"])
            self.assertEqual(before, {name: digest(directory / name) for name in before})
            self.assertEqual(original["status"], "failure")

    def test_revision_does_not_hide_unrelated_errors_or_visual_flags(self):
        with tempfile.TemporaryDirectory() as temporary:
            job, original, directory, args = self.fixture(Path(temporary))
            original["notes"].append("python: output rejected; timeout=True")
            self.assertIsNone(grayscale.correction(job, original, directory, args))
            original["notes"].pop()
            original["comparisons"]["A-legacy-python"]["flag_for_review"] = True
            batch.atomic_json(directory / "result.json", original)
            self.assertEqual(grayscale.correction(job, original, directory, args)["status"], "warning")

    def test_changed_original_artifact_cannot_be_revalidated(self):
        with tempfile.TemporaryDirectory() as temporary:
            job, original, directory, args = self.fixture(Path(temporary))
            with (directory / "legacy.jpg").open("ab") as stream:
                stream.write(b"changed")
            with self.assertRaisesRegex(ValueError, "artifact verification"):
                grayscale.correction(job, original, directory, args)

    def test_cli_keeps_original_records_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "report"
            job, original, directory, _ = self.fixture(root)
            original_sha = digest(directory / "result.json")
            metadata = {"run_key": "run", "manifest_sha256": "manifest", "published": {"commit": "published"},
                        "comparison_sha256": digest(ROOT / "compare_poster_renderers.py"),
                        "manifest_module_sha256": digest(ROOT / "validation_manifest.py")}
            batch.atomic_json(root / "run.json", metadata)
            frozen = {"sha256": "manifest", "jobs": [job]}
            summary = {"completed_jobs": 1, "status": {"pass": 1}, "rendered": {"legacy": 1, "python": 1}}
            command = ["--manifest", "unused", "--report-dir", str(root), "--published-repo", str(base / "published")]
            with patch.object(grayscale, "load_manifest", return_value=frozen), patch.object(grayscale, "validate_manifest"), \
                    patch.object(grayscale.shutil, "which", return_value="not-executed"), \
                    patch.object(batch, "published_state", return_value=metadata["published"]), \
                    patch.object(batch, "dashboard", return_value=summary):
                self.assertEqual(grayscale.main(command), 0)
                self.assertEqual(grayscale.main(command), 0)
            audit = json.loads((root / "validation-revisions/grayscale-v1/audit.json").read_text())
            self.assertEqual(audit["corrected_cases"], 1)
            backup = root / "validation-revisions/grayscale-v1/gray.original.json"
            self.assertEqual(digest(backup), original_sha)
            revised = json.loads((directory / "result.json").read_text())
            self.assertEqual(revised["validation_revision"]["original_record_sha256"], original_sha)
            self.assertEqual(revised["comparisons"], original["comparisons"])


class BatchReliabilityTests(unittest.TestCase):
    def test_warning_rank_uses_fresh_thresholds_not_published_artwork_or_raw_maxima(self):
        row = {"comparisons": {"A-legacy-python": {"mean_absolute_error_0_255": 1.5,
            "global_luminance_ssim_400x600": .995, "maximum_channel_difference_0_255": 255},
            "B-legacy-published": {"mean_absolute_error_0_255": 200}},
            "caption_diagnostics": {"ink_bound_deltas_python_minus_legacy": [-1, 0, 2, 0]}}
        self.assertEqual(warning_rank(row)["score"], 1)
        self.assertEqual(warning_rank(row)["edge"], 2)
        row["comparisons"]["A-legacy-python"]["mean_absolute_alpha_error_0_255"] = 4.5
        self.assertEqual(warning_rank(row)["score"], 3)
        row["comparisons"]["A-legacy-python"] = {"global_luminance_ssim_400x600": .98}
        self.assertAlmostEqual(warning_rank(row)["score"], 4)
        self.assertEqual(warning_rank({}), {"score": 0, "mae": None, "ssim": None, "edge": None})

    def test_ranked_warnings_include_checkpoint_sort_worst_first_and_preserve_records(self):
        def row(identifier, mae, imported=False):
            return {"id": identifier, "status": "warning", "category": "A & B",
                "parameters": {"out_name": "<" + identifier + ">"}, "font": {"family": ["Example"]},
                "checkpoint_origin": {"run_key": "old"} if imported else None,
                "comparisons": {"A-legacy-python": {"mean_absolute_error_0_255": mae}}}
        rows = [row("minor", .3), row("worst", 3, imported=True), row("middle", 1.6)]
        before = deepcopy(rows)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_ranked_warnings(root, rows)
            records = json.loads((root / "warnings-ranked.json").read_text())["warnings"]
            self.assertEqual([r["id"] for r in records], ["worst", "middle", "minor"])
            self.assertEqual(records[0]["scope"], "checkpoint")
            output = (root / "warnings-ranked.html").read_text()
            self.assertLess(output.index('data-id="worst"'), output.index('data-id="minor"'))
            self.assertIn("&lt;worst&gt;", output)
            self.assertIn('id="sort"', output)
            self.assertIn('id="scope"', output)
            self.assertIn("n/a", output)
        self.assertEqual(rows, before)

    def test_grouped_review_preserves_flags_and_does_not_mix_font_sizes_or_imports(self):
        def row(identifier, color, size=203, imported=False):
            return {"id": identifier, "status": "warning", "category": "Separators",
                    "checkpoint_origin": {"run_key": "old"} if imported else None,
                    "parameters": {"text": "A & B", "base_color": color, "logo": color + ".png",
                                   "font_size": size, "out_name": identifier},
                    "font": {"family": ["Comfortaa"], "sha256": "same"},
                    "comparisons": {"A-legacy-python": {"comparable": True, "flag_for_review": True,
                        "mean_absolute_error_0_255": .2, "global_luminance_ssim_400x600": .99}}}
        rows = [row("one", "red"), row("two", "blue"), row("other-size", "red", size=204), row("old", "red", imported=True)]
        before = deepcopy(rows)
        self.assertEqual(sorted(map(len, warning_groups(rows))), [1, 2])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = write_groups(root, rows)
            self.assertEqual(record["new_warning_jobs"], 3)
            output = (root / "review-groups.html").read_text()
            self.assertIn("A &amp; B", output)
            self.assertIn("not a claim that every variant was visually inspected", output)
        self.assertEqual(rows, before)

    def test_review_explains_trigger_boundaries_and_keeps_json_secondary(self):
        result = {"id": "tiny", "status": "warning", "comparisons": {
            "A-legacy-python": {"comparable": True, "flag_for_review": True,
                "mean_absolute_error_0_255": .84, "global_luminance_ssim_400x600": .988725,
                "channel_difference_p99_0_255": 2}},
            "caption_diagnostics": {"ink_bound_deltas_python_minus_legacy": [1, 0, 0, -1]}}
        before = deepcopy(result)
        explanation = review_summary(result)
        self.assertIn("below the 0.995 cutoff, triggering a warning", explanation)
        self.assertIn("0.840 out of 255, within", explanation)
        self.assertIn("1 pixel(s)", explanation)
        self.assertIn("not a confirmed defect", explanation)
        self.assertEqual(result, before)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch.case_report(root, result)
            output = (root / "index.html").read_text()
            self.assertLess(output.index("What Was Flagged"), output.index("Technical comparison metrics"))
            self.assertIn('<details><summary>Technical comparison metrics</summary>', output)

    def test_review_handles_missing_outputs_alpha_and_escaped_errors(self):
        output = review_summary({"status": "failure", "notes": ["<script>bad</script>"],
                                 "comparisons": {"A-legacy-python": {"comparable": False}}})
        self.assertIn("&lt;script&gt;", output)
        self.assertNotIn("<script>", output)
        output = review_summary({"status": "warning", "comparisons": {"A-legacy-python": {
            "comparable": True, "flag_for_review": True, "mean_absolute_alpha_error_0_255": 2}}})
        self.assertIn("transparency difference", output)

    def test_reference_grayscale_is_valid_but_native_requires_rgb(self):
        info = {"dimensions": (40, 60), "format": "JPEG", "mode": "L"}
        self.assertTrue(batch.valid_output(info, [40, 60], "legacy"))
        self.assertFalse(batch.valid_output(info, [40, 60], "python"))
        info["mode"] = "RGB"
        self.assertTrue(batch.valid_output(info, [40, 60], "python"))
        self.assertFalse(batch.valid_output(info, [40, 61], "legacy"))
        info["format"] = "PNG"
        self.assertFalse(batch.valid_output(info, [40, 60], "legacy"))

    def test_published_aliases_and_incomparable_dimensions_are_classified(self):
        job = {"font": {"path": "fonts/Comfortaa-Medium.ttf"}}
        for difference in ({"flag_for_review": True}, {"comparable": False}):
            comparisons = {"A-legacy-python": {"comparable": True, "flag_for_review": False},
                           "B-legacy-published-alias-1": difference}
            self.assertEqual(batch.classification(job, comparisons, True), "existing historical artwork difference")

    def test_execution_coverage_does_not_confuse_inventory_with_rendering(self):
        jobs = [{"id": name, "category": "Genre", "definition_id": definition,
                 "source": {"definition_line": index}} for name, definition, index in
                (("one", "line-1", 1), ("two", "line-1", 1), ("three", "line-2", 2), ("four", "line-3", 3))]
        rows = [{"id": name, "complete": True, "images": {"legacy": {}, "python": {}},
                 "comparisons": {"A-legacy-python": {"comparable": True}}} for name in ("one", "three")]
        coverage = batch.execution_coverage({"jobs": jobs, "sha256": "manifest", "covered_literal_definitions": 3}, rows)
        self.assertEqual(coverage["literal_rows_fully_paired"], 1)
        self.assertEqual(coverage["literal_rows_partially_paired"], 1)
        self.assertEqual(coverage["literal_rows_not_paired"], 1)
        self.assertEqual(coverage["untested_job_ids"], ["two", "four"])

    def test_dashboard_filters_only_job_rows(self):
        frozen = {"jobs": [], "sha256": "manifest", "literal_definitions": 0,
                  "covered_literal_definitions": 0, "uncovered_literal_lines": [],
                  "categories": {"Genre": 0}, "source_hashes": {}, "fonts": [],
                  "translation": {}, "same_queue_output_collisions": []}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch.dashboard(root, [], frozen, {})
            html = (root / "index.html").read_text()
            self.assertIn("querySelectorAll('tr[data-status]')", html)
            self.assertNotIn("querySelectorAll('tbody tr')", html)
            self.assertIn("inventoried/resolved, not necessarily executed", html)

    def test_hash_proven_published_reuse_preserves_exact_numeric_metrics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = root / "reference.png", root / "candidate.png"
            Image.new("RGB", (40, 60), (10, 20, 30)).save(first)
            Image.new("RGB", (40, 60), (15, 20, 25)).save(second)
            a = compare_images(first, second, root, "A")
            direct_b = compare_images(first, first, root, "direct-B")
            direct_c = compare_images(second, first, root, "direct-C")
            b = batch.reuse_identical_published("B-legacy-published", a, digest(first), digest(first), root)
            c = batch.reuse_identical_published("C-python-published", a, digest(first), digest(first), root)
            for key in ("mean_absolute_error_0_255", "global_luminance_ssim_400x600", "maximum_channel_difference_0_255",
                        "channel_difference_p99_0_255", "changed_pixel_fraction", "text_region", "flag_for_review"):
                self.assertEqual(b[key], direct_b[key])
                self.assertEqual(c[key], direct_c[key])
            self.assertEqual(c["text_crops"], list(reversed(a["text_crops"])))
            self.assertIsNone(batch.reuse_identical_published("B-legacy-published", a, digest(first), digest(second), root))
            self.assertIsNone(batch.reuse_identical_published("A-legacy-python", a, digest(first), digest(first), root))

    def test_postprocessing_error_cannot_leave_a_passing_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "scratch"
            workspace.mkdir()
            args = SimpleNamespace(report_dir=root, assets=ROOT, retry_failed=False, min_free_gb=0,
                timeout=120, sample_interval=.25, powershell="fake-reference", published_repo=None,
                representatives=set(), required_parents=set(), ambiguous_jobs=set())
            job = {"id": "tiny", "category": "Genre", "font": {"path": "fonts/Comfortaa-Medium.ttf", "family": ["Comfortaa"]},
                   "sha256": "job", "parameters": asdict(PosterOptions(out_name="one", base_color="#112233")),
                   "definition_id": "line-1", "published_relatives": [], "assets": {}, "canvas": [40, 60],
                   "expected_composer_filename": "one.jpg"}
            def render(command, cwd, log, timeout, sample_interval):
                Path(log).write_text("")
                target = workspace / "output/one.jpg" if command[0] == "fake-reference" else Path(command[command.index("--output-path") + 1])
                Image.new("RGB", (40, 60), (10, 20, 30)).save(target, "JPEG")
                return {"returncode": 0, "timed_out": False, "seconds": .01}
            with patch.object(batch, "measured", side_effect=render), patch.object(batch, "shrink_evidence", side_effect=OSError("evidence write failed")):
                result, _ = batch.render_job(job, args, workspace, "run")
            self.assertEqual(result["status"], "failure")
            self.assertTrue(any("evidence write failed" in note for note in result["notes"]))

    def test_parallel_owned_directory_creation_normalizes_windows_device_prefixes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            def create(index):
                path = batch.inside(root / "cases" / str(index), root)
                path.mkdir(parents=True, exist_ok=True)
                return path
            with ThreadPoolExecutor(max_workers=8) as pool:
                paths = list(pool.map(create, range(64)))
            self.assertTrue(all(path.is_relative_to(root) for path in paths))
            if sys.platform == "win32":
                extended = Path("\\\\?\\" + str(root / "cases/0"))
                self.assertEqual(batch.inside(extended, root), root / "cases/0")

    def test_scheduler_has_bounded_pending_work_and_cancels_on_stop(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            class Counted:
                submitted = 0
                def submit(self, function, job):
                    self.submitted += 1
                    return pool.submit(function, job)
            counted = Counted()
            completed = []
            for job, future in batch.bounded_completed(counted, lambda value: value, range(30), 2, lambda: False):
                completed.append(future.result())
                self.assertLessEqual(counted.submitted - len(completed), 2)
            self.assertEqual(sorted(completed), list(range(30)))
            stopped = False
            seen = []
            for job, future in batch.bounded_completed(counted, lambda value: value, range(30), 2, lambda: stopped):
                seen.append(future.result())
                stopped = True
            self.assertLessEqual(len(seen), 2)

    def test_inactive_sampling_paths_are_not_required_assets(self):
        values = {"logo": "logo.png", "avg_color_image": "#D19068", "avg_color": False,
                  "dom_color_image": "unused.png", "dom_color": True}
        self.assertEqual(batch.required_inputs(values), {"logo.png"})
        values["avg_color"] = True
        self.assertEqual(batch.required_inputs(values), {"logo.png", "#D19068"})

    def test_generated_inputs_are_topologically_scheduled_and_cycles_rejected(self):
        parent = {"id": "parent", "generated_inputs": {}}
        child = {"id": "child", "generated_inputs": {"logo": {"job_id": "parent"}}}
        self.assertEqual(batch.dependency_levels([child, parent]), [[parent], [child]])
        with self.assertRaisesRegex(ValueError, "missing or cyclic"):
            batch.dependency_levels([child])
        parent["generated_inputs"]["logo"] = {"job_id": "child"}
        with self.assertRaisesRegex(ValueError, "missing or cyclic"):
            batch.dependency_levels([child, parent])

    def test_resume_checks_inputs_and_retained_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            artifact = directory / "preview.jpg"
            artifact.write_bytes(b"image evidence")
            result = {"job_sha256": "job", "run_key": "run", "complete": True, "status": "pass",
                      "retained_artifacts": {artifact.name: digest(artifact)}}
            batch.atomic_json(directory / "result.json", result)
            self.assertEqual(batch.resumable({"sha256": "job"}, directory, "run"), result)
            self.assertIsNone(batch.resumable({"sha256": "changed"}, directory, "run"))
            self.assertIsNone(batch.resumable({"sha256": "job"}, directory, "different"))
            artifact.write_bytes(b"changed")
            self.assertIsNone(batch.resumable({"sha256": "job"}, directory, "run"))

    def test_failures_are_persistent_but_explicitly_retryable(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            result = {"job_sha256": "job", "run_key": "run", "complete": True, "status": "failure", "retained_artifacts": {}}
            batch.atomic_json(directory / "result.json", result)
            self.assertIsNotNone(batch.resumable({"sha256": "job"}, directory, "run"))
            self.assertIsNone(batch.resumable({"sha256": "job"}, directory, "run", retry_failed=True))

    def test_resume_rechecks_generated_parent_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "cases/parent/legacy.jpg"
            parent.parent.mkdir(parents=True)
            parent.write_bytes(b"original parent")
            child = root / "cases/child"
            child.mkdir()
            result = {"job_sha256": "job", "run_key": "run", "complete": True, "status": "pass", "retained_artifacts": {},
                      "generated_input_hashes": {"logo": {"job_id": "parent", "sha256": digest(parent)}}}
            batch.atomic_json(child / "result.json", result)
            self.assertIsNotNone(batch.resumable({"sha256": "job"}, child, "run"))
            parent.write_bytes(b"changed parent")
            self.assertIsNone(batch.resumable({"sha256": "job"}, child, "run"))

    def test_lock_and_cleanup_boundaries_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with batch.exclusive_run(root):
                with self.assertRaises(RuntimeError):
                    with batch.exclusive_run(root):
                        self.fail("Second writer admitted")
            self.assertFalse((root / ".running").exists())
            for target in (root, root / ".." / "outside"):
                with self.assertRaises(ValueError):
                    batch.inside(target, root)

    def test_real_timeout_is_recorded_and_process_reaped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = measured([sys.executable, "-c", "import time; time.sleep(30)"], root, root / "timeout.log", timeout=.2)
            self.assertTrue(result["timed_out"])
            self.assertNotEqual(result["returncode"], 0)
            self.assertLess(result["seconds"], 10)

    def test_missing_input_is_job_failure_without_renderer_or_production_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = SimpleNamespace(report_dir=root, assets=ROOT, retry_failed=False, min_free_gb=0)
            job = {"id": "missing", "category": "Genre", "font": {"path": "fonts/Comfortaa-Medium.ttf", "family": ["Comfortaa"]},
                   "sha256": "job", "parameters": {"logo": "missing.png"}, "definition_id": "line-1", "published_relatives": [], "assets": {"missing.png": None}}
            before = digest(ROOT / "create_poster.ps1")
            with patch.object(batch, "measured", side_effect=AssertionError("Renderer should not run")):
                result, resumed = batch.render_job(job, args, root / "scratch", "run")
            self.assertFalse(resumed)
            self.assertEqual(result["status"], "failure")
            self.assertTrue(result["complete"])
            self.assertIn("FileNotFoundError", result["notes"][0])
            self.assertEqual(before, digest(ROOT / "create_poster.ps1"))

    def test_report_totals_distinguish_untested_and_failed(self):
        rows = [{"category": "Genre", "font": {"family": ["Comfortaa"]}, "status": "failure", "images": {}, "measurements": {}}]
        summary = batch.aggregate(rows, 100)
        self.assertEqual(summary["remaining_jobs"], 99)
        self.assertEqual(summary["status"], {"failure": 1})
        self.assertEqual(summary["rendered"], {"legacy": 0, "python": 0})

    def test_classification_does_not_hide_migration_differences_as_approved_fonts(self):
        job = {"font": {"path": "fonts/BebasNeue-Regular.ttf"}}
        a = {"comparable": True, "flag_for_review": True}
        self.assertEqual(batch.classification(job, {"A-legacy-python": a}, True), "Python migration difference")
        a["flag_for_review"] = False
        self.assertEqual(batch.classification(job, {"A-legacy-python": a, "B-legacy-published": {"flag_for_review": True}}, True), "approved font replacement")

    def test_comparison_records_raw_max_p99_and_text_region(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            Image.new("RGB", (40, 60), (0, 0, 0)).save(root / "a.png")
            Image.new("RGB", (40, 60), (5, 5, 5)).save(root / "b.png")
            result = compare_images(root / "a.png", root / "b.png", root, "test")
            self.assertEqual(result["maximum_channel_difference_0_255"], 5)
            self.assertEqual(result["channel_difference_p99_0_255"], 5)
            self.assertEqual(result["text_region"]["mean_absolute_error_0_255"], 5)


if __name__ == "__main__":
    unittest.main()
