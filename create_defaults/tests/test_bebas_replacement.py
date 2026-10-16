from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from PIL import Image

from create_defaults.compare_bebas_fonts import (CANDIDATES, candidate_sources, caption_difference,
                                                 font_metrics, playlist_cases, prepare_comparison_workspace, size_proposals)
from create_defaults.create_poster import ROOT, digest
from create_defaults.poster_text import resolve_font


class BebasComparisonTests(unittest.TestCase):
    def test_primary_dataset_is_all_nine_real_playlist_configurations(self):
        cases = playlist_cases()
        self.assertEqual(len(cases), 9)
        self.assertEqual(len({case.parameters["out_name"] for case in cases}), 9)
        self.assertTrue(all(case.category == "Playlist" for case in cases))
        self.assertTrue(all(case.parameters["text"] == "TIMELINE ORDER" for case in cases))
        self.assertTrue(all(case.fit == (1600, 1000, 100, 154) for case in cases))
        self.assertTrue(all(case.parameters["font"] == "Bebas Neue" for case in cases))
        self.assertTrue(all(Path(case.parameters["logo"]).is_file() for case in cases))

    def test_candidates_are_distinct_original_author_files(self):
        self.assertEqual(CANDIDATES["neue"]["file"], "BebasNeue-Regular.ttf")
        self.assertIn("2018", CANDIDATES["neue"]["path"])
        self.assertEqual(CANDIDATES["kai"]["file"], "BebasKai.ttf")
        for candidate in CANDIDATES.values():
            self.assertEqual(len(candidate["commit"]), 40)
            self.assertNotEqual(candidate["file"], "Bebas-Regular.ttf")

    def test_candidate_lookup_never_downloads_without_explicit_flag(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("urllib.request.urlopen", side_effect=AssertionError("Implicit network")), \
             self.assertRaisesRegex(FileNotFoundError, "fetch-candidates"):
            candidate_sources(directory)

    def test_candidate_cache_cannot_claim_upstream_provenance_for_changed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "neue/BebasNeue-Regular.ttf"
            target.parent.mkdir()
            target.write_bytes(b"not the pinned font")
            with self.assertRaisesRegex(ValueError, "hash differs"):
                candidate_sources(directory)

    def test_selected_font_has_original_names_and_original_license_notices(self):
        font = resolve_font("Bebas Neue", ROOT / "fonts")
        self.assertEqual(font.name, "BebasNeue-Regular.ttf")
        self.assertEqual(digest(font), CANDIDATES["neue"]["sha256"])
        notices = ROOT / "fonts/licenses/BebasNeue"
        expected = {"OFL.txt": CANDIDATES["neue"]["license_sha256"],
                    "AUTHORS.txt": "3662cb2eab4a247b62e7e33cc6b49126b70b431f2018e8c67361ab019b3c7825",
                    "CONTRIBUTORS.txt": "081d6434ae1b79b8f51c3c27315de7c22251d5b1c0b48666c97c1340bd7f354a",
                    "TRADEMARKS.md": CANDIDATES["neue"]["trademark_sha256"]}
        for name, checksum in expected.items():
            self.assertEqual(digest(notices / name), checksum)
        self.assertFalse((ROOT / "fonts/Bebas-Regular.ttf").exists())
        with self.assertRaises(FileNotFoundError):
            resolve_font("Bebas-Regular", ROOT / "fonts")

    def test_isolation_forces_exact_files_even_with_lowercase_powershell_variable(self):
        from create_defaults import compare_bebas_fonts as comparison
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fonts = {}
            for key, name in (("original", "Bebas-Regular.ttf"), ("neue", "BebasNeue-Regular.ttf"), ("kai", "BebasKai.ttf")):
                source = root / name
                source.write_bytes(key.encode())
                fonts[key] = source
            workspace = root / "workspace"
            workspace.mkdir()
            def prepare(*args):
                (workspace / "fonts").mkdir()
                (workspace / "legacy.ps1").write_text('$fontAliases = @{}\nif ($visibleFonts -contains $fontName) {}', encoding="utf-8-sig")
                return {}
            args = SimpleNamespace(legacy_composer=root / "source.ps1", magick="magick")
            with patch.object(comparison, "prepare_legacy", side_effect=prepare):
                prepare_comparison_workspace(args, workspace, fonts)
            text = (workspace / "legacy.ps1").read_text(encoding="utf-8-sig")
            self.assertIn('if ($false -and $visibleFonts -contains $fontName)', text)
            self.assertIn('"bebaskai" = "BebasKai.ttf"', text)

    def test_glyph_metrics_preserve_exact_font_units_and_shaped_spacing(self):
        metrics = font_metrics(ROOT / "fonts/Comfortaa-Medium.ttf", "TIMELINE ORDER", 140)
        self.assertEqual(metrics["point_size"], 140)
        nominal = sum(metrics["glyphs"][c]["advance_pixels"] for c in "TIMELINE ORDER")
        self.assertAlmostEqual(metrics["nominal_advance_pixels"], nominal)
        self.assertAlmostEqual(metrics["shaped_advance_pixels"],
                               sum(glyph["advance_pixels"] for glyph in metrics["shaped_glyphs"]))
        self.assertIn("outline_bounds_units", metrics["glyphs"]["T"])

    def test_size_search_covers_original_and_dimension_derived_sizes(self):
        original = {"ink_width": 748, "ink_height": 102}
        candidate = {"point_size": 140, "ink_width": 731, "ink_height": 101}
        proposals = size_proposals(original, candidate)
        self.assertIn(140, proposals)
        self.assertIn(143, proposals)
        with self.assertRaisesRegex(ValueError, "excessive"):
            size_proposals(original, {"point_size": 140, "ink_width": 1, "ink_height": 101})

    def test_caption_error_uses_alpha_and_foreground_union(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a.png", Path(directory) / "b.png"
            first = Image.new("RGBA", (10, 10), (255, 0, 0, 0))
            second = Image.new("RGBA", (10, 10), (0, 255, 0, 0))
            first.save(a)
            second.save(b)
            self.assertEqual(caption_difference(a, b)["foreground_alpha_mae_0_255"], 0)
            first.putpixel((5, 5), (255, 255, 255, 255))
            first.save(a)
            error = caption_difference(a, b)
            self.assertEqual(error["foreground_union_pixels"], 1)
            self.assertEqual(error["foreground_alpha_mae_0_255"], 255)
            self.assertEqual(error["full_caption_alpha_mae_0_255"], 2.55)


if __name__ == "__main__":
    unittest.main()
