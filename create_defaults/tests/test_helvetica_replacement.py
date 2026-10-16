from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fontTools.ttLib import TTFont

from create_defaults import compare_helvetica_fonts as comparison
from create_defaults import verify_jakarta_replacement as jakarta
from create_defaults.create_poster import ROOT, digest
from create_defaults.poster_fixtures import extract_rows, font_inventory
from create_defaults.poster_text import FontLayout, resolve_font


class HelveticaReplacementTests(unittest.TestCase):
    def test_all_eleven_actual_definitions_use_the_approved_fixed_size(self):
        cases = comparison.affected_cases(ROOT / "create_default_posters.ps1")
        self.assertEqual(len(cases), 11)
        for case in cases:
            self.assertEqual(case.parameters["font"], "Plus Jakarta Sans Bold")
            self.assertEqual(case.parameters["font_size"], 409)
            self.assertIsNone(case.fit)
            self.assertEqual(case.parameters["text_offset"], 0)

    def test_missing_or_additional_affected_rows_fail_closed(self):
        rows = extract_rows()
        unrelated = next(r for r in rows if r["row"]["font"] != "Plus Jakarta Sans Bold")
        with patch.object(comparison, "extract_rows", return_value=[r for r in rows if r is not unrelated]):
            # Removing an unrelated row must not affect the dataset.
            self.assertEqual(len(comparison.affected_cases("unused")), 11)
        filtered = [r for r in rows if not (r["category"] == "Year" and r["row"]["key_name"] == "2029")]
        with patch.object(comparison, "extract_rows", return_value=filtered), self.assertRaisesRegex(ValueError, "dataset changed"):
            comparison.affected_cases("unused")

    def test_exact_official_font_and_all_original_notices_are_bundled(self):
        font = ROOT / "fonts/PlusJakartaSans-Bold.ttf"
        self.assertEqual(digest(font), jakarta.FILES[font.name])
        notices = ROOT / "fonts/licenses/PlusJakartaSans"
        for name, checksum in jakarta.FILES.items():
            if name != font.name:
                self.assertEqual(digest(notices / name), checksum)
        with TTFont(font) as face:
            names = lambda identifier: {n.toUnicode() for n in face["name"].names if n.nameID == identifier}
            self.assertEqual(names(1), {"Plus Jakarta Sans"})
            self.assertEqual(names(2), {"Bold"})
            self.assertEqual(names(4), {"Plus Jakarta Sans Bold"})
            self.assertTrue(all(version.startswith("Version 2.071;") for version in names(5)))

    def test_real_name_aliases_resolve_without_masquerading_as_helvetica(self):
        for name in ("Plus Jakarta Sans Bold", "PlusJakartaSans-Bold", "PlusJakartaSans-Bold.ttf"):
            self.assertEqual(resolve_font(name, ROOT / "fonts").name, "PlusJakartaSans-Bold.ttf")
        self.assertFalse((ROOT / "fonts/Helvetica-Bold.ttf").exists())
        self.assertFalse((ROOT / "fonts/LiberationSans-Bold.ttf").exists())
        with self.assertRaises(FileNotFoundError):
            resolve_font("Helvetica-Bold", ROOT / "fonts")

    def test_official_font_outlines_parse_and_render_without_fallback(self):
        path = ROOT / "fonts/PlusJakartaSans-Bold.ttf"
        before = digest(path)
        layout = FontLayout(path)
        self.assertIsNotNone(layout.right_edges)
        for text in ("2020s", *(str(year) for year in range(2020, 2030))):
            image, metadata = layout.caption(text, 409, "white")
            self.assertIsNotNone(image.getchannel("A").getbbox())
            self.assertNotIn("native FreeType fallback", metadata["glyph_bounds_source"])
        self.assertEqual(digest(path), before)

    def test_offline_candidate_verification_rejects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "PlusJakartaSans-Bold.ttf").write_bytes(b"not official font bytes")
            with patch("socket.socket.connect", side_effect=AssertionError("Network")), \
                 self.assertRaisesRegex(ValueError, "hash differs"):
                jakarta.verify_candidate(directory, directory)

    def test_release_metadata_verification_is_offline_and_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            for name in jakarta.FILES:
                source = ROOT / "fonts/PlusJakartaSans-Bold.ttf" if name.endswith(".ttf") else ROOT / "fonts/licenses/PlusJakartaSans" / name
                shutil.copyfile(source, target / name)
            with patch("socket.socket.connect", side_effect=AssertionError("Network")):
                metadata = jakarta.verify_candidate(target, target)
            self.assertEqual(metadata["family"], ["Plus Jakarta Sans"])
            self.assertEqual(metadata["style"], ["Bold"])
            self.assertGreater(metadata["character_count"], 500)

    def test_incomplete_report_cannot_claim_production_verification(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "summary.json").write_text(json.dumps({"results": []}))
            with self.assertRaisesRegex(ValueError, "all 11"):
                jakarta.verify_preview(Path(directory))

    def test_changed_font_hash_does_not_inherit_release_license_evidence(self):
        from create_defaults import poster_fixtures
        original = poster_fixtures.digest
        with patch.object(poster_fixtures, "digest", side_effect=lambda path:
                          "0" * 64 if Path(path).name == "PlusJakartaSans-Bold.ttf" else original(path)):
            item = next(item for item in font_inventory(extract_rows())
                        if Path(item.get("file", "")).name == "PlusJakartaSans-Bold.ttf")
        self.assertNotIn("license_evidence", item)
        self.assertIn("hash differs", item["provenance_warning"])

    def test_legacy_resolution_uses_reviewed_asset_and_updated_checksum(self):
        for name in ("create_default_posters.ps1", "create_poster.ps1"):
            source = (ROOT / name).read_text(encoding="utf-8-sig")
            self.assertIn('"plusjakartasansbold"', source)
            self.assertIn('"PlusJakartaSans-Bold.ttf"', source)
            self.assertNotIn("LiberationSans-Bold", source)
            self.assertNotIn("Helvetica-Bold", source)
        source = (ROOT / "create_default_posters.ps1").read_text(encoding="utf-8-sig")
        self.assertIn(jakarta.FILES["PlusJakartaSans-Bold.ttf"].upper(), source)
        self.assertNotIn(comparison.ORIGINAL_SHA256.upper(), source)

    def test_fixed_size_does_not_get_refitted_to_381(self):
        from create_defaults.compare_poster_renderers import effective_parameters
        for case in comparison.affected_cases(ROOT / "create_default_posters.ps1"):
            with patch("subprocess.run", side_effect=AssertionError("Fixed styles must not auto-fit")):
                parameters, fit = effective_parameters(case, "magick", ROOT)
            self.assertEqual(parameters["font_size"], 409)
            self.assertIsNone(fit)

    def test_digit_one_has_no_bottom_foot(self):
        layout = FontLayout(ROOT / "fonts/PlusJakartaSans-Bold.ttf")
        image, _ = layout.caption("1", 409, "white")
        alpha = image.getchannel("A")
        alpha = alpha.crop(alpha.getbbox())
        bottom = alpha.crop((0, alpha.height - 4, alpha.width, alpha.height)).getbbox()
        middle = alpha.crop((0, alpha.height // 2, alpha.width, alpha.height // 2 + 4)).getbbox()
        self.assertLessEqual(bottom[2] - bottom[0], middle[2] - middle[0] + 1)

    def test_actual_bulk_command_builders_use_409_only_for_jakarta(self):
        import subprocess
        powershell = shutil.which("pwsh")
        if not powershell:
            self.skipTest("PowerShell 7 unavailable; native renderer tests remain platform-independent")
        result = subprocess.run([powershell, "-NoLogo", "-NoProfile", "-File",
                                 str(ROOT / "tests/verify_jakarta_bulk.ps1")], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all 11 real Jakarta commands use 409", result.stdout)


if __name__ == "__main__":
    unittest.main()
