import base64
from dataclasses import replace
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

from create_defaults.create_poster import (FADES, ROOT, SIZE, PosterOptions, average_color,
                                          create_poster, load_image, main,
                                          output_filename, render_poster, resized_logo, jpeg_roundtrip)
from create_defaults.poster_text import FONT_FILES, FontLayout, resolve_font, token
from create_defaults.poster_fixtures import build_cases, extract_rows, font_inventory
from create_defaults.compare_poster_renderers import compare_images, offline_legacy_copy, published_image


LOGO = ROOT / "logos_genre" / "Action.png"
OPTIONS = PosterOptions(logo=LOGO, base_color="#387DBF", font="ComfortAa-Medium", text="ACTION",
                        logo_resize=1800, logo_offset=-500, text_offset=850)


class ParameterTests(unittest.TestCase):
    def test_compound_legacy_negative_offsets_preserve_reference_placement(self):
        for name, value in (("logo_offset", 500), ("text_offset", 850)):
            expected, _ = render_poster(replace(OPTIONS, **{name: -value}))
            actual, _ = render_poster(replace(OPTIONS, **{name: f"+-{value}"}))
            self.assertEqual(actual.tobytes(), expected.tobytes())
        for value in ("--500", "++500", "+--500", "+-1501"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                render_poster(replace(OPTIONS, logo_offset=value))

    def test_cli_accepts_exact_compound_offsets_without_changing_other_numeric_fields(self):
        with patch("create_defaults.create_poster.create_poster", return_value={}) as render:
            self.assertEqual(main(["--logo-offset", "+-500", "--text-offset", "+-850"]), 0)
            self.assertEqual(render.call_args.args[0].logo_offset, -500)
            self.assertEqual(render.call_args.args[0].text_offset, -850)

    def test_public_parameter_inventory_matches_legacy_declaration(self):
        text = (ROOT / "create_poster.ps1").read_text(encoding="utf-8-sig")
        declaration = next(line for line in text.splitlines() if line.startswith("param ("))
        import re
        self.assertEqual(set(re.findall(r"\$(\w+)", declaration)), set(PosterOptions.__dataclass_fields__))

    def test_invalid_colors_and_geometry_fail_without_writes(self):
        for name in ("base_color", "font_color", "border_color"):
            for value in ("red", "123456", "#123", "#GGGGGG", "#1234567"):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    render_poster(replace(OPTIONS, **{name: value}))
        for name, value in (("gradient", "bad"), ("logo_resize", -1), ("logo_resize", 2001),
                            ("logo_offset", 1501), ("text_offset", -1501), ("font_size", "bad"),
                            ("border_width", "bad")):
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                render_poster(replace(OPTIONS, **{name: value}))

    def test_filename_handling_is_portable_and_keeps_legacy_default(self):
        self.assertEqual(output_filename(OPTIONS, "#387DBF"), "Action-#387DBF.jpg")
        self.assertEqual(output_filename(replace(OPTIONS, out_name="Caf\u00e9"), "#387DBF"), "Caf\u00e9.jpg")
        self.assertEqual(output_filename(replace(OPTIONS, out_name="\\blue\\genre"), "#387DBF"), "blue/genre.jpg")
        self.assertEqual(output_filename(replace(OPTIONS, base_color="#abcdef"), "#ABCDEF"), "Action-#abcdef.jpg")
        for stem in ("A.C.G.T.", "asread.", "feel.", "P.I.C.S.", "Production +h.", "SILVER LINK.", "Studio Blanc."):
            self.assertEqual(output_filename(replace(OPTIONS, out_name=stem), "#387DBF"), stem + ".jpg")
        for value in ("../source", "dir/../file", "//server/file", "CON", "NUL.txt", "bad:", "bad./file", "bad ", "a\x00b"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                output_filename(replace(OPTIONS, out_name=value), "#387DBF")

    def test_missing_logo_and_font_are_meaningful_errors(self):
        with self.assertRaisesRegex(FileNotFoundError, "Image not found"):
            load_image(ROOT / "missing.png")
        with self.assertRaisesRegex(FileNotFoundError, "no substitution"):
            resolve_font("Not-An-Installed-Or-Bundled-Font", ROOT / "fonts")
        with self.assertRaisesRegex(ValueError, "random font"):
            resolve_font(None, ROOT / "fonts")

    def test_cli_errors_have_nonzero_exit_codes(self):
        with patch("sys.stderr", new=BytesIOText()):
            self.assertEqual(main(["--base-color", "invalid"]), 2)
        with patch("create_defaults.create_poster.create_poster", side_effect=OSError("disk failed")), patch("sys.stderr", new=BytesIOText()):
            self.assertEqual(main([]), 1)

    def test_cli_accepts_all_legacy_parameter_names(self):
        values = dict(logo=str(LOGO), logo_offset=-500, logo_resize=1800, base_color="#387DBF", gradient=4,
                      text="ACTION", text_offset=850, font="ComfortAa-Medium", font_color="#AABBCC", font_size=200,
                      out_name="Action", avg_color=False, avg_color_image=str(LOGO), dom_color=False,
                      dom_color_image=str(LOGO), border=True, border_width=37, border_color="#17B87A",
                      white_wash=True, clean=True)
        arguments = []
        for key, value in values.items():
            arguments.extend(["-" + key, str(int(value)) if isinstance(value, bool) else str(value)])
        with patch("create_defaults.create_poster.create_poster", return_value={}) as call, patch("sys.stdout", new=BytesIOText()):
            self.assertEqual(main(arguments), 0)
        self.assertEqual(call.call_args.args[0], PosterOptions(**values))


class BytesIOText:
    def write(self, value):
        return len(value)

    def flush(self):
        pass


class PixelTests(unittest.TestCase):
    def test_jpeg_stages_do_not_add_an_extra_final_generation(self):
        for text, border, expected in (("", False, 2), ("TV", False, 3), ("", True, 4), ("TV", True, 5)):
            with self.subTest(text=text, border=border), patch("create_defaults.create_poster.jpeg_roundtrip", wraps=jpeg_roundtrip) as encoding:
                render_poster(replace(OPTIONS, text=text, border=border))
                self.assertEqual(encoding.call_count, expected)
                self.assertEqual(encoding.call_args_list[0].args[1], 92)
                self.assertEqual(encoding.call_args_list[1].args[1], 92)
        # create_poster performs exactly one final encode after intermediate
        # legacy stages; copying the file never re-encodes its pixels.

    def test_original_fades_match_embedded_reference_bytes(self):
        import re
        text = (ROOT / "create_poster.ps1").read_text(encoding="utf-8-sig")
        for index, filename in enumerate(FADES):
            match = re.search(r'^\$file' + str(index) + r' = "([A-Za-z0-9+/=]+)"', text, re.M)
            self.assertIsNotNone(match)
            self.assertEqual((ROOT / "fades" / filename).read_bytes(), base64.b64decode(match[1]))

    def test_input_pixel_and_animation_limits_before_conversion(self):
        from contextlib import nullcontext
        from types import SimpleNamespace
        fake = SimpleNamespace(width=100_000, height=100_000, n_frames=1)
        with patch("PIL.Image.open", return_value=nullcontext(fake)), self.assertRaisesRegex(ValueError, "single-frame"):
            load_image(LOGO)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "animated.gif"
            Image.new("RGB", (2, 2), "red").save(path, save_all=True, append_images=[Image.new("RGB", (2, 2), "blue")])
            with self.assertRaisesRegex(ValueError, "single-frame"):
                load_image(path)

    def test_legacy_numeric_defaults_and_range_fallbacks(self):
        image, metadata = render_poster(PosterOptions(base_color="#387DBF", logo_resize=0, gradient=9,
                                                     font_size=999, border_width=999))
        self.assertEqual(image.size, SIZE)
        self.assertEqual(metadata["logo_size"], (2000, 2000))
        self.assertEqual(metadata["gradient"], 1)

    def test_font_color_and_positive_negative_text_offsets(self):
        bounds = []
        for offset in (-250, 250):
            image, metadata = render_poster(PosterOptions(base_color="#000000", gradient=0, logo_resize=1,
                text="TV", text_offset=offset, font="ComfortAa-Medium", font_color="#FF0000", font_size=100))
            mask = image.getchannel("R").point(lambda value: 255 if value > 128 else 0)
            bounds.append(mask.getbbox())
        self.assertEqual(bounds[1][1] - bounds[0][1], 500)
        self.assertEqual(bounds[1][0], bounds[0][0])

    def test_five_gradients_use_original_assets_and_have_distinct_results(self):
        hashes = set()
        for mode in range(5):
            image, metadata = render_poster(PosterOptions(base_color="#387DBF", gradient=mode, logo_resize=1))
            self.assertEqual(image.size, SIZE)
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(metadata["gradient"], mode)
            hashes.add(hashlib.sha256(image.tobytes()).hexdigest())
        self.assertEqual(len(hashes), 5)

    def test_alpha_resize_preserves_transparency_and_avoids_dark_halos(self):
        source = load_image(LOGO)
        before = source.getchannel("A").getextrema()
        result = resized_logo(source, 200)
        self.assertEqual(result.width, 200)
        self.assertEqual(before[0], 0)
        self.assertEqual(result.getchannel("A").getextrema()[0], 0)
        self.assertGreater(result.getchannel("A").getextrema()[1], 200)

    def test_average_matches_solid_hsl_modulation_and_ignores_hidden_colors(self):
        image = Image.new("RGBA", (5, 5), (100, 100, 100, 255))
        self.assertEqual(average_color(image), (120, 120, 120))
        image = Image.new("RGBA", (2, 1), (0, 255, 0, 0))
        image.putpixel((0, 0), (100, 100, 100, 255))
        self.assertEqual(average_color(image), (120, 120, 120))

    def test_border_shrinks_whole_composition_instead_of_covering_edges(self):
        options = PosterOptions(base_color="#336699", gradient=0, logo_resize=1, border=True,
                                border_width=37, border_color="#17B87A")
        image, metadata = render_poster(options)
        corner = image.getpixel((10, 10))
        self.assertTrue(all(abs(a - b) <= 2 for a, b in zip(corner, (23, 184, 122))))
        center = image.getpixel((1000, 1500))
        self.assertTrue(all(abs(a - b) <= 2 for a, b in zip(center, (51, 102, 153))))

    def test_white_wash_and_logo_offsets(self):
        washed, _ = render_poster(replace(OPTIONS, text="", white_wash=True, gradient=0))
        colored, _ = render_poster(replace(OPTIONS, text="", white_wash=False, gradient=0))
        self.assertNotEqual(washed.tobytes(), colored.tobytes())
        moved, _ = render_poster(replace(OPTIONS, text="", logo_offset=500, gradient=0))
        self.assertNotEqual(colored.tobytes(), moved.tobytes())

    def test_explicit_color_overrides_extraction_flags(self):
        _, metadata = render_poster(replace(OPTIONS, text="", avg_color=True, dom_color=True, border_color="#AABBCC"))
        self.assertEqual(metadata["base_color"], "#387DBF")
        self.assertEqual(metadata["border_color"], "#AABBCC")

    def test_average_and_dominant_parameter_paths(self):
        _, metadata = render_poster(replace(OPTIONS, text="", base_color=None, avg_color=True,
                                            avg_color_image=LOGO, border_color=None,
                                            dom_color=True, dom_color_image=LOGO))
        self.assertRegex(metadata["base_color"], r"^#[A-F0-9]{6}$")
        self.assertEqual(metadata["border_color"], "#FFFFFF")

    def test_dominant_flags_preserve_legacy_no_op_even_for_missing_sample(self):
        _, metadata = render_poster(replace(OPTIONS, text="", dom_color=True, dom_color_image="missing.png", border_color=None))
        self.assertEqual(metadata["border_color"], "#FFFFFF")

    def test_large_resize_is_rejected_before_unbounded_allocation(self):
        with self.assertRaisesRegex(ValueError, "bounded"):
            resized_logo(Image.new("RGBA", (1, 100)), 2000)


class FontTests(unittest.TestCase):
    def test_existing_windows_unicode_cmap_is_replaced_without_changing_font_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "existing-ucs4.ttf"
            with TTFont(ROOT / "fonts/Comfortaa-Medium.ttf") as font:
                table = CmapSubtable.newSubtable(12)
                table.platformID, table.platEncID, table.language = 3, 10, 0
                table.cmap = dict(font.getBestCmap())
                font["cmap"].tables.append(table)
                font.save(path)
            before = path.read_bytes()
            layout = FontLayout(path)
            with TTFont(BytesIO(layout.font_data)) as font:
                tables = [table for table in font["cmap"].tables
                          if (table.platformID, table.platEncID, table.language) == (3, 10, 0)]
                self.assertEqual(len(tables), 1)
                self.assertIn(ord(layout.characters[-1]), tables[0].cmap)
            image, _ = layout.caption("TV 2026", 200, "white")
            self.assertIsNotNone(image.getchannel("A").getbbox())
            self.assertEqual(path.read_bytes(), before)

    def test_unicode_bridge_fix_preserves_all_bundled_font_bytes(self):
        for filename in FONT_FILES:
            with self.subTest(font=filename), patch("fontTools.ttLib.tables._h_e_a_d.timestampNow", return_value=3800000000):
                path = ROOT / "fonts" / filename
                with patch("create_defaults.poster_text.install_unicode_bridge",
                           side_effect=lambda font, bridge: font["cmap"].tables.append(bridge)):
                    previous = FontLayout(path).font_data
                self.assertEqual(FontLayout(path).font_data, previous)

    def test_optional_outline_parser_error_uses_the_same_native_face(self):
        from fontTools.ttLib import TTFont, TTLibError
        from create_defaults import poster_text

        class OutlineParseFailure(TTFont):
            def save(self, *args, **kwargs):
                super().save(*args, **kwargs)
                self.fail_optional_outlines = True

            def __getitem__(self, tag):
                if tag == "glyf" and getattr(self, "fail_optional_outlines", False):
                    raise TTLibError("Synthetic optional outline parse failure")
                return super().__getitem__(tag)

        path = ROOT / "fonts" / "PlusJakartaSans-Bold.ttf"
        before = path.read_bytes()
        with patch.object(poster_text, "TTFont", OutlineParseFailure):
            layout = FontLayout(path)
        self.assertIsNone(layout.right_edges)
        image, metadata = layout.caption("1970 TV", 150, "white")
        self.assertIsNotNone(image.getchannel("A").getbbox())
        self.assertIn("native FreeType fallback", metadata["glyph_bounds_source"])
        self.assertEqual(path.read_bytes(), before)

    def test_all_seventeen_families_resolve_exact_files_and_render_probes(self):
        for filename in FONT_FILES:
            path = resolve_font(filename, ROOT / "fonts")
            self.assertEqual(path.name, filename)
            layout = FontLayout(path)
            for caption in ("TV", "THE MOVIES THAT DEFINED OUR CHILDHOOD", "MOVIES\\nAND TELEVISION"):
                with self.subTest(font=filename, caption=caption):
                    image, metadata = layout.caption(caption, 150, "white")
                    self.assertIsNotNone(image.getchannel("A").getbbox())
                    self.assertGreater(len(metadata["lines"]), 0)

    def test_aliases_are_variants_not_arbitrary_substitutes(self):
        for name, expected in (("ComfortAa-Medium", "Comfortaa-Medium.ttf"), ("UnifrakturCook", "UnifrakturCook-Bold.ttf"),
                               ("Cherry-Cream-Soda-Regular", "CherryCreamSoda-Regular.ttf"),
                               ("Special-Elite-Regular", "SpecialElite-Regular.ttf")):
            self.assertEqual(resolve_font(name, ROOT / "fonts").name, expected)

    def test_wrapping_newlines_supported_accents_and_missing_glyphs(self):
        layout = FontLayout(ROOT / "fonts" / "Comfortaa-Medium.ttf")
        self.assertEqual(layout.wrap("A\\nB", 200), ["A", "B"])
        self.assertEqual(layout.wrap("A\nB", 200), ["A", "B"])
        self.assertGreater(len(layout.wrap("THE MOVIES THAT DEFINED OUR CHILDHOOD", 250)), 1)
        self.assertEqual(layout.wrap("COLLECTIONLESS", 250), ["COLLECTIONLESS"])
        layout.validate("Caf\u00e9 \u00c5ngstr\u00f6m")
        with self.assertRaisesRegex(ValueError, "no glyph"):
            layout.validate("\u0627\u0644\u0639\u0631\u0628\u064a\u0629")
        with self.assertRaisesRegex(ValueError, "safety limit"):
            layout.caption("A" * 20_000, 200, "white")

    def test_script_terminal_overhang_is_included_in_centered_line_width(self):
        layout = FontLayout(ROOT / "fonts" / "Yesteryear-Regular.ttf")
        for text, expected in (("THE MOVIES THAT", 1683), ("DEFINED OUR", 1321), ("CHILDHOOD", 1103)):
            with self.subTest(text=text):
                self.assertAlmostEqual(layout.width(text, 200), expected, delta=1)
                self.assertGreater(layout.width(text, 200), layout.positions(text, 200)[1])

    def test_complex_script_shaping_with_explicit_available_font(self):
        candidates = [os.getenv("DEFAULT_POSTER_COMPLEX_FONT", ""), "C:/Windows/Fonts/arial.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
        path = next((Path(p) for p in candidates if p and Path(p).is_file()), None)
        if path is None:
            self.skipTest("Set DEFAULT_POSTER_COMPLEX_FONT to a licensed Arabic-capable font for shaping probe")
        layout = FontLayout(path)
        caption = "\u0644\u0627"
        positions, advance = layout.positions(caption, 200)
        self.assertLess(len(positions), len(caption), "HarfBuzz must form the Arabic lam-alef ligature")
        self.assertGreater(advance, 0)
        for text in ("\u0627\u0644\u0639\u0631\u0628\u064a\u0629", "TV 2026 \u0627\u0644\u0639\u0631\u0628\u064a\u0629", "\u0627\u0644\u0639\u0631\u0628\u064a\u0629\n123"):
            image, _ = layout.caption(text, 200, "white")
            self.assertIsNotNone(image.getchannel("A").getbbox())


class FileSafetyTests(unittest.TestCase):
    def test_legacy_script_relative_logo_and_font_paths_from_other_directory(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                image, metadata = render_poster(PosterOptions(logo="logos_genre/Action.png",
                    font="fonts/Comfortaa-Medium.ttf", text="TV", base_color="#387DBF"), asset_dir=ROOT)
                self.assertEqual(image.size, SIZE)
                self.assertEqual(Path(metadata["font"]["path"]), ROOT / "fonts" / "Comfortaa-Medium.ttf")
            finally:
                os.chdir(previous)

    def test_unicode_paths_jpeg_determinism_and_source_preservation(self):
        before = LOGO.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory) / "Caf\u00e9 \u00c5land"
            directory.mkdir()
            source = directory / "l\u00f6go.png"
            source.write_bytes(before)
            options = replace(OPTIONS, logo=source, text="Caf\u00e9", clean=True)
            first = create_poster(options, output_path=directory / "r\u00e9sultat.jpg")
            second = create_poster(options, output_path=directory / "second.jpg")
            self.assertEqual(first["sha256"], second["sha256"])
            with Image.open(first["output_path"]) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.size, SIZE)
                self.assertEqual(image.mode, "RGB")
            self.assertEqual(source.read_bytes(), before)
            self.assertFalse(list(directory.glob(".poster-*")))
            with self.assertRaises(FileExistsError):
                create_poster(options, output_path=source)
            with self.assertRaises(FileExistsError):
                create_poster(options, output_path=directory / "second.jpg")
        self.assertEqual(LOGO.read_bytes(), before)

    def test_output_does_not_replace_source_even_with_jpeg_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.jpg"
            Image.new("RGB", (20, 20), "red").save(source)
            before = source.read_bytes()
            with self.assertRaises(FileExistsError):
                create_poster(replace(OPTIONS, logo=source), output_path=source)
            self.assertEqual(source.read_bytes(), before)

    def test_cleanup_is_private_and_survives_write_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentinel = root / "unrelated.tmp"
            sentinel.write_bytes(b"keep")
            original = Image.Image.save
            def save(image, path, *args, **kwargs):
                if isinstance(path, Path) and path.name == "poster.jpg":
                    raise OSError("simulated save failure")
                return original(image, path, *args, **kwargs)
            with patch.object(Image.Image, "save", save), self.assertRaisesRegex(OSError, "simulated"):
                create_poster(replace(OPTIONS, text=""), output_path=root / "poster.jpg")
            self.assertEqual(list(root.iterdir()), [sentinel])

    def test_failed_final_copy_removes_only_its_partial_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentinel = root / "keep.txt"
            sentinel.write_bytes(b"keep")
            with patch("shutil.copyfileobj", side_effect=OSError("copy failed")), self.assertRaisesRegex(OSError, "copy failed"):
                create_poster(replace(OPTIONS, text=""), output_path=root / "failed.jpg")
            self.assertEqual(list(root.iterdir()), [sentinel])

    def test_failed_exclusive_open_does_not_delete_unowned_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "raced.jpg"
            original = Path.open
            def open_file(path, mode="r", *args, **kwargs):
                if path == target and mode == "xb":
                    with original(target, "wb") as stream:
                        stream.write(b"another writer")
                    raise PermissionError("simulated exclusive-open failure")
                return original(path, mode, *args, **kwargs)
            with patch.object(Path, "open", open_file), self.assertRaises(PermissionError):
                create_poster(replace(OPTIONS, text=""), output_path=target)
            self.assertEqual(target.read_bytes(), b"another writer")

    def test_python_renderer_never_executes_powershell_magick_or_network(self):
        with patch("subprocess.Popen", side_effect=AssertionError("external process")), \
             patch("os.system", side_effect=AssertionError("shell")), \
             patch("socket.socket.connect", side_effect=AssertionError("network")):
            image, _ = render_poster(OPTIONS)
            self.assertEqual(image.size, SIZE)


class ComparisonTests(unittest.TestCase):
    def test_packaged_english_fixture_is_exact_and_works_without_local_cache(self):
        from create_defaults.poster_fixtures import translation_file
        with tempfile.TemporaryDirectory() as directory:
            path = translation_file(Path(directory))
        self.assertEqual(path, ROOT / "fixtures/english/en.yml")
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         "5fe987030981e83c35fab37192240afd596febf7f6f4d205a9c024a272ff390f")
        self.assertEqual(hashlib.sha256(path.with_name("LICENSE").read_bytes()).hexdigest(),
                         "ec4e791bbefa93c524a162a29c1ccb7cefb182225c0372aa913182874afaccb5")
        with patch("create_defaults.poster_fixtures.translation_file", return_value=path):
            rows, cases = build_cases()
        self.assertEqual(len(rows), 3352)
        self.assertGreater(len(cases), 100)

    def test_curated_license_evidence_is_hash_pinned_and_offline(self):
        with patch("socket.socket.connect", side_effect=AssertionError("Network in inventory")):
            items = {Path(item["file"]).name: item for item in font_inventory(extract_rows()) if "file" in item}
        for filename in ("BebasNeue-Regular.ttf", "BoecklinsUniverse.ttf", "Monoton-Regular.ttf", "PlusJakartaSans-Bold.ttf"):
            with self.subTest(filename=filename):
                item = items[filename]
                self.assertEqual(item["sha256"], item["license_evidence"]["sha256"])
                self.assertTrue(item["license_evidence"]["sources"])
        self.assertIn("SIL OFL 1.1", items["BebasNeue-Regular.ttf"]["license_status"])
        self.assertNotIn("Bebas-Regular.ttf", items)
        self.assertIn("SIL OFL 1.1", items["PlusJakartaSans-Bold.ttf"]["license_status"])
        self.assertNotIn("Helvetica-Bold.ttf", items)
        self.assertIn("exact archived official", items["BoecklinsUniverse.ttf"]["license_status"])
        self.assertIn("exact official Google Fonts", items["Monoton-Regular.ttf"]["license_status"])

    def test_approved_monoton_font_notice_names_and_production_checksum(self):
        from fontTools.ttLib import TTFont
        expected = "951c4cea65ffede784a7c9672feec5d329a7e1e12216c42d53ecf36c90d04dea"
        evidence = json.loads((ROOT / "font_provenance.json").read_text())["fonts"]["Monoton-Regular.ttf"]
        path = ROOT / "fonts/Monoton-Regular.ttf"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)
        self.assertEqual(evidence["sha256"], expected)
        notice = ROOT / evidence["bundled_notices"] / "OFL.txt"
        self.assertEqual(hashlib.sha256(notice.read_bytes()).hexdigest(),
                         "585c6d2da8bcd8ffa651e0016f2e992a6891b625143a46a1dacf00699a817d9a")
        self.assertIn(b'with Reserved Font Names "Monoton"', notice.read_bytes())
        self.assertIn(b"Copyright (c) 2011 by vernon adams", notice.read_bytes())
        self.assertIn("OFL.txt -text -whitespace", notice.with_name(".gitattributes").read_text())
        self.assertIn(f'$expectedChecksum_ttf9 = "{expected.upper()}"',
                      (ROOT / "create_default_posters.ps1").read_text(encoding="utf-8-sig"))
        with TTFont(path) as font:
            self.assertEqual(font["maxp"].numGlyphs, 373)
            self.assertEqual({name.toUnicode() for name in font["name"].names if name.nameID == 1}, {"Monoton"})
            self.assertEqual({name.toUnicode() for name in font["name"].names if name.nameID == 6}, {"Monoton-Regular"})
        self.assertEqual(Path(resolve_font("Monoton", ROOT / "fonts")), path)

    def test_boecklin_exact_historical_license_notices_are_preserved(self):
        evidence = json.loads((ROOT / "font_provenance.json").read_text())["fonts"]["BoecklinsUniverse.ttf"]
        self.assertEqual(hashlib.sha256((ROOT / "fonts/BoecklinsUniverse.ttf").read_bytes()).hexdigest(), evidence["sha256"])
        notices = ROOT / evidence["bundled_notices"]
        self.assertEqual(hashlib.sha256((notices / evidence["license_member"]).read_bytes()).hexdigest(), evidence["license_sha256"])
        self.assertEqual(hashlib.sha256((notices / "OFL-FAQ.txt").read_bytes()).hexdigest(), evidence["original_faq_sha256"])
        original = (notices / evidence["license_member"]).read_bytes()
        self.assertIn(b"Copyright (c) 2013, Peter Wiegel", original)
        self.assertIn(b"SIL OPEN FONT LICENSE Version 1.1", original)
        self.assertTrue(any("20150321100356id_" in item["url"] for item in evidence["sources"]))

    def test_changed_font_hash_cannot_inherit_curated_license_evidence(self):
        from create_defaults import poster_fixtures
        original = poster_fixtures.digest
        def digest(path):
            return "0" * 64 if Path(path).name == "BebasNeue-Regular.ttf" else original(path)
        with patch.object(poster_fixtures, "digest", side_effect=digest):
            item = next(item for item in font_inventory(extract_rows()) if Path(item.get("file", "")).name == "BebasNeue-Regular.ttf")
        self.assertNotIn("license_evidence", item)
        self.assertIn("hash differs", item["provenance_warning"])
        self.assertNotIn("exact official", item["license_status"].lower())

    def test_legacy_reuse_checks_parameters_sources_fonts_and_output_hash(self):
        from types import SimpleNamespace
        from create_defaults.compare_poster_renderers import reuse_legacy
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            (baseline / "probe").mkdir(parents=True)
            source = baseline / "probe" / "legacy.jpg"
            Image.new("RGB", (20, 20), "red").save(source)
            previous = dict(parameters={"text": "TV"}, input_hashes={"logo": "source-hash"},
                            resolved_font={"sha256": "font-hash"}, images={"legacy": {
                                "report_file": "legacy.jpg", "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}},
                            measurements={"legacy": {"seconds": 1.0}})
            args = SimpleNamespace(legacy_cache={"probe": (baseline, previous)}, python_only=False)
            case = SimpleNamespace(id="probe")
            destination = root / "new"
            destination.mkdir()
            def result():
                return dict(parameters={"text": "TV"}, input_hashes={"logo": "source-hash"},
                            resolved_font={"sha256": "font-hash"}, images={}, notes=[])
            for key, changed in (("parameters", {"text": "Other"}), ("input_hashes", {"logo": "changed"}),
                                 ("resolved_font", {"sha256": "other-font"})):
                values = result()
                values[key] = changed
                self.assertFalse(reuse_legacy(case, values, args, destination))
            values = result()
            with patch("subprocess.Popen", side_effect=AssertionError("External process")):
                self.assertTrue(reuse_legacy(case, values, args, destination))
            self.assertEqual((destination / "legacy.jpg").read_bytes(), source.read_bytes())
            self.assertIn("legacy_reused_from", values)
            log = baseline / "probe" / "legacy.log"
            log.write_text("Random Font mode enabling now", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "random fallback font"):
                reuse_legacy(case, result(), args, destination)
            log.unlink()
            source.write_bytes(b"changed after baseline")
            with self.assertRaisesRegex(ValueError, "Cached legacy image changed"):
                reuse_legacy(case, result(), args, destination)

    def test_python_only_comparison_does_not_launch_legacy_or_magick(self):
        from create_defaults import compare_poster_renderers as comparison
        rows, cases = build_cases()
        selected = cases[0]
        def fake_measured(command, cwd, log, *args):
            self.assertEqual(command[0], sys.executable)
            if "--help" not in command:
                target = Path(command[command.index("--output-path") + 1])
                metadata = create_poster(PosterOptions(**selected.parameters), output_path=target)
                Path(log).write_text(json.dumps(metadata), encoding="utf-8")
            return dict(seconds=0.1, returncode=0, timed_out=False, sampled_peak_tree_rss_bytes=0, sampled_write_bytes=0)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(comparison, "measured", side_effect=fake_measured), \
             patch("subprocess.run", side_effect=AssertionError("External transform in Python-only mode")), \
             patch("subprocess.Popen", side_effect=AssertionError("Legacy process in Python-only mode")), \
             patch("sys.stdout", new=BytesIOText()):
            report = Path(directory) / "report"
            self.assertEqual(comparison.main(["--python-only", "--limit", "1", "--report-dir", str(report)]), 0)
            self.assertTrue((report / selected.id / "python.jpg").is_file())
            before = (report / selected.id / "python.jpg").read_bytes()
            self.assertEqual(comparison.main(["--refresh-report", str(report), "--recompute-metrics"]), 0)
            self.assertEqual((report / selected.id / "python.jpg").read_bytes(), before)
            refreshed = json.loads((report / selected.id / "result.json").read_text())
            self.assertTrue(refreshed["input_image_observations"])

    def test_real_fixture_coverage_and_font_inventory(self):
        rows, cases = build_cases()
        self.assertGreater(len(rows), 3000)
        self.assertGreaterEqual(len(cases), 100)
        self.assertTrue({"Genre", "Network", "Studio", "Streaming", "Awards", "Resolution", "Playlist",
                         "Country", "AudioLanguage", "SubtitleLanguage", "Overlays"}.issubset({c.category for c in cases}))
        inventory = font_inventory(rows)
        self.assertEqual(sum(not item["missing"] for item in inventory), 17)
        self.assertFalse(any("Proprietary" in item["license_status"] for item in inventory))
        self.assertTrue(all({"short", "long", "multiline"}.issubset({c.id.rsplit("-", 1)[-1] for c in cases if c.id.startswith("font-" + token(f))}) for f in FONT_FILES))
        self.assertTrue(any(c.parameters["logo_resize"] == 0 for c in cases))

    def test_legacy_isolation_retains_composition_but_never_invokes_bootstrap(self):
        source = ROOT / "create_poster.ps1"
        before = source.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "legacy.ps1"
            audit = offline_legacy_copy(source, target, Path("magick"))
            text = target.read_text(encoding="utf-8-sig")
            self.assertNotIn("$LatestScriptVersion = Get-LatestScriptVersion", text)
            self.assertNotIn("\nSetMagickLocation\n", text)
            self.assertIn("-size 1900x1000 -background none caption:", text)
            self.assertEqual(audit["source_sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(source.read_bytes(), before)

    def test_metrics_and_published_lookup_are_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "genre").mkdir()
            source = root / "genre" / "Action.jpg"
            Image.new("RGB", (2000, 3000), "red").save(source)
            before = source.read_bytes()
            self.assertEqual(published_image(root, "genre/Action.jpg"), source)
            metrics = compare_images(source, source, root, "test")
            self.assertEqual(metrics["mean_absolute_error_0_255"], 0)
            self.assertAlmostEqual(metrics["global_luminance_ssim_400x600"], 1)
            self.assertFalse(metrics["flag_for_review"])
            self.assertEqual(source.read_bytes(), before)
            json.dumps(metrics)

    def test_transparent_hidden_rgb_does_not_inflate_visible_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first.png", root / "second.png"
            Image.new("RGBA", (20, 20), (255, 0, 0, 0)).save(first)
            Image.new("RGBA", (20, 20), (0, 255, 0, 0)).save(second)
            metrics = compare_images(first, second, root, "alpha")
            self.assertEqual(metrics["mean_absolute_error_0_255"], 0)
            self.assertEqual(metrics["mean_absolute_alpha_error_0_255"], 0)
            self.assertFalse(metrics["flag_for_review"])


if __name__ == "__main__":
    unittest.main()
