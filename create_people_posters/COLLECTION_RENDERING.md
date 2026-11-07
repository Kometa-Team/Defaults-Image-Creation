# Dynamic COLLECTION lettering (Python)

Signature, rainier, diiivoy and diiivoycolor use textless overlays and one
dynamic white COLLECTION layer. Their person-name fonts, fitting, wrapping,
positions, cutout handling and color treatment remain unchanged. BW,
transparent and original handling are unchanged. JPEG output still uses
quality 100 and subsampling 0. The legacy PowerShell renderer is excluded
from this update and its validation.

| Style | Textless artwork | COLLECTION font | Size | Tracking | Stroke | Visible x, y |
| --- | --- | --- | --- | --- | --- | --- |
| signature | @zbase-Signature-no-text.png | Montserrat-SemiBold.ttf | 92 | 12.5 | 0 | 643, 2791 |
| rainier | @zbase-People-Clear2-no-text.png | Montserrat-Light.ttf | 110 | 18.0 | 0 | 201, 809 |
| diiivoy | @zbase-People-Clear3-no-text.png | Montserrat-SemiBold.ttf | 100 | 83.0 | 1 | 309, 2857 |
| diiivoycolor | @zbase-People-Clear3-no-text.png | Montserrat-SemiBold.ttf | 100 | 83.0 | 1 | 309, 2857 |

These are accepted calibration values, not pixel-exact recreations of the
embedded lettering. Coordinates anchor the top-left of visible ink, including
stroke and antialiased edge pixels, on the 2000 × 3000 canvas.

`Renderer.render_collection(poster, style)` uses bundled fonts with Pillow's
BASIC layout engine, just as the existing person-name rasterizer does. It
draws individual characters using `font.getlength(character)` plus the configured
tracking. Positions retain fractional values until Pillow rasterizes them;
the label is not horizontally rescaled or thresholded. A padded RGBA layer
preserves glyph bearings and stroke before trimming to its alpha bounds. The
method rejects lettering that would extend past the poster and returns its
visible bounds. It is called exactly once after the textless overlay is
composited and before the existing person-name layer. Selective diiivoy
rendering follows the same path. There was no `compare_collection_stroke.py`
calibration script available in this worktree to reuse.

`COLLECTION_ARTWORK` selects the three exact new filenames. All seven artwork
files (the four originals and three textless additions), five production fonts,
renderer source and font-layout source participate in the Python resource
fingerprint. Overrides must contain every required file; a missing textless
overlay or font is an error with no fallback. Jost-260 remains byte-for-byte
unchanged; see [font inventory and provenance](fonts/README.md).

Preflight confirmed all overlays are 2000 × 3000 RGBA. Original versus textless
RGBA differences are confined to these rectangles (right/bottom exclusive):

| Overlay | Changed rectangle | Alpha changes |
| --- | --- | --- |
| Signature | 645, 2789, 1358, 2860 | None |
| Clear2 | 201, 807, 1070, 890 | Confined to removed lettering |
| Clear3 | 305, 2853, 1723, 2935 | None |

Every pixel outside those areas is identical, retaining gradients, fades,
transparency and decorations. None of the input artwork or font binaries is
rewritten during rendering.

## Local review generation

Before editing the renderer, save its Python source in the ignored local
review directory. Use that explicit source as the reference; this independently
exercises the old composition and person-name logic with the original artwork.
The comparison tool does not call `render_batch`, an orchestrator, sync or a
publisher. It reads the person cutout without changing it and requires a fresh
output directory, separate from publication destinations.

```text
python create_people_posters/compare_collection.py --source "PATH/person.png" --reference-source "PATH/baseline_renderer.py.txt" --output "create_people_posters/config/collection-review-UNIQUE/previews" --name "Person Name"
```

For each style it writes full-size reference/replacement PNGs and quality-100
JPEGs; a lossless 4000 × 3000 side-by-side; a tight COLLECTION comparison; full
absolute-difference images (raw and amplified 4×); the transparent text layer;
and JSON parameters, bounds, hashes, validation results and metrics. `index.html`
and `contact-sheet.jpg` provide an overview. Metrics measure RGB MAE, RMSE,
maximum channel difference and changed pixels, separately for lossless full
images, the lettering crop and encoded JPEGs. Lossless pixels outside the union
of old/new lettering bounds must be identical. JPEG block artifacts can extend
beyond that region. The summary also checks BW pixels and transparent RGBA
against the saved reference. Accepted remaining differences concern lettering
shape, spacing, weight and ink bounds.

Run the relevant Python tests without the two legacy PowerShell audit cases:

```text
python -m pytest create_people_posters/tests/test_collection_poster.py create_people_posters/tests/test_pillow_poster.py create_people_posters/tests/test_people_font_comparison.py -k "not artwork_exactly_matches_embedded_reference and not jost_is_bundled_static_weight_260_with_license_and_no_legacy_font"
```

Those two existing cases read the legacy PowerShell script and are deliberately
excluded from this Python-only validation. No protected validation evidence is
changed. This local review does not authorize committing, pushing or publishing.
