# Default Posters: Phase 1 Renderer and Parity Audit

Status: experimental, alongside the unchanged production PowerShell workflow.
For the current review state, approved fonts, portable samples and next steps,
start with [the team review guide](REVIEW_GUIDE.md).
Subsequent scoped change: restricted Bebas was replaced by official OFL-licensed
Bebas Neue v2.000 for the nine Playlist definitions, with maximum size 154.
See [the replacement report](BEBAS_REPLACEMENT.md); the initial parity report
remains a historical checkpoint and is not a new-font acceptance certificate.
Do not replace published artwork or move to Phase 2 merely because metric screens
pass. See `PHASE1_RESULTS.md` for the measured run and outstanding differences.

## Scope and Entry Points

`create_poster.py` renders one 2000 x 3000 RGB JPEG using Pillow. It neither calls
PowerShell/ImageMagick nor performs downloads, installations, self-updates,
publication, category generation, translation changes, or repository syncing.
`create_default_posters.ps1` is not converted. Both existing PowerShell scripts,
their category definitions, and their copy/push workflow remain the reference.

Windows setup and a real genre example, from the repository root:

```powershell
py -3.13 -m pip install -r create_defaults/requirements.txt
py -3.13 create_defaults/create_poster.py --logo create_defaults/logos_genre/Action.png --logo-offset=-500 --logo-resize 1800 --base-color "#387DBF" --gradient 1 --text ACTION --text-offset 850 --font ComfortAa-Medium --font-size 250 --white-wash 1 --output-path config/default-poster-phase1/action-python.jpg
```

Use a fresh output filename. Existing files are never overwritten. Unix callers
use the same arguments under their Python 3.13 interpreter. No system-font
installation is required for the 17 bundled families.

Direct API, callable by a later service without launching another process:

```python
from create_defaults.create_poster import PosterOptions, render_poster, create_poster

options = PosterOptions(
    logo="create_defaults/logos_genre/Action.png", logo_offset=-500,
    logo_resize=1800, base_color="#387DBF", text="ACTION", text_offset=850,
    font="ComfortAa-Medium", font_size=250, white_wash=True,
)
image, metadata = render_poster(options)  # RGB Pillow image; no writes
saved = create_poster(options, output_path="config/action-review.jpg")
```

Both calls also accept legacy-named keyword arguments instead of `PosterOptions`.
`asset_dir` supplies the source `fades/` and `fonts/` roots; `font_dir` can override
the font directory explicitly. CLI switches accept `--logo-offset`,
`--logo_offset`, and `-logo_offset` forms. Boolean flags accept 0/1, false/true,
or an omitted value meaning true. Use `--logo-offset=-500` for negative offsets.
Relative logo/sample paths resolve beside `asset_dir` first, matching the legacy
script's working-directory behavior, then relative to the caller if no such asset
exists. Relative explicit font paths also support the legacy script directory.
Absolute paths are recommended for service callers and remove any ambiguity.

## Complete Parameter Mapping

All 20 names in the legacy `param` declaration are represented in `PosterOptions`.
The Python API uses integers for offsets and booleans for flags.

| PowerShell / Python name | Legacy default / actual behavior | Python behavior |
| --- | --- | --- |
| `logo` | `transparent.png` beside script when omitted | In-memory transparent logo when omitted; explicit source loaded read-only |
| `logo_offset` | `+0`; signed string, -1500..1500, positive moves down | 0; integer -1500..1500; identical centered geometry |
| `logo_resize` | 2000 pixels wide, height proportional; numeric 0 also defaults to 2000 | 2000; same zero/default behavior and 1..2000 range |
| `base_color` | Random `#000000`..`#FFFFFE` unless supplied/extracted | Same random range; use explicit color for determinism |
| `gradient` | 1; modes 0..4, unrecognized value selects 1 | Same five assets and integer fallback to 1 |
| `text` | Empty; ImageMagick caption, literal `\n` line breaks | Empty; Unicode caption with literal/actual line breaks |
| `text_offset` | `+0`; signed -1500..1500 | 0; integer -1500..1500; positive moves down |
| `font` | No stable default; visible-font lookup, bundled aliases, then random fallback | Exact bundled alias or explicit file; required for nonempty text; missing font raises, never random |
| `font_color` | `#FFFFFF` | `#FFFFFF`; strict `#RRGGBB` |
| `font_size` | 250 points at default 72dpi; values outside 10..500 reset to 250 | Same default and numeric range fallback; no silent font substitution |
| `out_name` | Logo stem plus `-<base_color>.jpg` unless explicit stem supplied; separator commands include child folders | Same naming and explicit color spelling; safe child folders supported under output directory; explicit `output_path`/`output_dir` available |
| `avg_color` | false; when no explicit base, resize sample to 1x1 and HSL brightness 120% | Same intended alpha-weighted sample/modulation; full precision before final rounding |
| `avg_color_image` | Transparent default; ignored if averaging disabled | Read-only sample or in-memory transparent default |
| `dom_color` | false; declared but **not implemented** | Same reserved no-op for strict Phase 1 parity; extraction is deferred |
| `dom_color_image` | Declared but unused | Accepted and ignored, including missing sample paths, as in the reference |
| `border` | false; resize the entire finished poster smaller, then add border | Same whole-composition resize then border; not a rectangle covering the edges |
| `border_width` | 15; outside 1..100 resets to 15 | Same numeric default/fallback |
| `border_color` | `#FFFFFF` | `#FFFFFF`; explicit color wins; dominant-color flags have no effect |
| `white_wash` | false; gray then 100% white, preserve alpha | White RGB with unchanged source alpha, then proportional resizing |
| `clean` | false; true removes this run's logo/fade/base/gradient/resized/white scratch copies | Accepted for compatibility; private temporary output staging is **always** cleaned |

Safety differences are deliberate: malformed colors and geometry raise meaningful
exceptions, existing outputs are not replaced, multi-frame inputs are rejected,
and paths are not interpreted as image transformation commands. Missing fonts
are errors only when text is actually requested. The legacy random font choice
even for empty captions is not preserved.

The legacy script's PowerShell coercions are significant: a *numeric* zero width
is empty/default, whereas a string containing `"0"` may behave differently. The
Python API and CLI normalize numeric widths; fixtures use the numeric values
emitted by the bulk generator. Non-numeric invalid gradient/font-size inputs
raise rather than reproducing every PowerShell coercion.

## Audited Rendering Pipeline

1. Read source logo, default transparent logo if absent. Keep Unicode paths and
   source bytes untouched; no trim of logo transparency or EXIF auto-orientation
   is added to the legacy behavior.
2. Create the solid base at 2000 x 3000, JPEG round-trip at default legacy quality
   92. Use the **original** fade PNG: 0 `@none.png` (1 x 1 transparent), 1
   `@center-out-fade.png`, 2 `@bottom-up-fade.png`, 3 `@top-down-fade.png`, 4
   `@bottom-top-fade.png`. Modes 1..4 are 2000 x 3000. No mathematical replacement
   of the artwork is made. Flatten centered and JPEG round-trip again at 92.
3. Optionally white-wash while retaining alpha, resize to requested width with
   proportional rounded height, center at x=1000/y=1500 plus vertical offset.
   Pillow's premultiplied-alpha Lanczos resize prevents transparent-edge halos.
   Composite source-over. If text/border follows, JPEG round-trip at quality 100,
   4:4:4; otherwise this is encoded once by the final save.
4. If text is present, wrap at 1900 pixels, fixed point size, into a transparent
   1900 x 1000 caption. Preserve explicit newlines. Render original font outlines
   with HarfBuzz shaping/kerning and Unicode BiDi ordering, using an in-memory
   private cmap technique like `create_people_posters/poster_fonts.py`. Trim ink,
   center-extent to 1900 x 1000, and center-composite with the text offset. Fixed
   point-size overflow is clipped, not automatically fitted to an invented size.
   Save/reload JPEG at 100 if a border follows; otherwise encode once at final save.
   Line metrics include a final glyph's right overhang before centering, matching
   [ImageMagick's terminal-glyph measurement](https://raw.githubusercontent.com/ImageMagick/ImageMagick/7.1.2-27/MagickCore/annotate.c).
5. Border mode shrinks the entire poster to `(2000-2w) x (3000-2w)`, including text
   and logo, round-trips JPEG, then adds `w` pixels on every side.
   Write a quality-100 4:4:4 RGB JPEG to a private sibling staging directory, then
   create the destination exclusively. Always clean only owned staging files.
   The final image is encoded only once, without an extra decode/re-encode
   generation. Unit tests pin the number and quality of intermediate JPEG stages.

The composer itself does not implement bulk `Get-OptimalPointSize`: that function
belongs to the deferred generator. The comparison harness reproduces its
ImageMagick caption-size calculation and min/max clamp read-only, freezes the
result, then supplies **the same** font size to both composers. A subsequent
composer reset from values over 500 to 250 is also recorded, not concealed.

Runtime bounds: at most 40 megapixels per input, 24 megapixels after logo resize,
16,384 caption characters, bounded text workspace, and an eight-font layout cache.
No full batch is held in memory. Python CLI returns 0 on success, 2 for invalid
parameters/missing assets, and 1 for rendering/output failures. Direct API callers
receive the underlying meaningful exception.

## Font Inventory

Inventory scans literal CSV data tables, generated command contexts, font checks,
`$theFont` variables, and explicit arguments, not just `-font` occurrences.
The current source has 3,352 literal data rows across 21 poster categories.
The JSON report includes exact SHA-256, file path, embedded license/copyright
strings, every mapped Unicode codepoint, unsupported probe characters, category
row counts, and requested spellings. The authorized Bebas and Helvetica
replacements bundle unchanged official OFL assets and their original notices.

| Requested name | Resolved file under `fonts/` | Categories | Mapped codepoints | License evidence |
| --- | --- | --- | ---: | --- |
| Barlow-Regular | Barlow-Regular.ttf | Decade, Year | 525 | Embedded SIL OFL 1.1 |
| Bebas Neue | BebasNeue-Regular.ttf | Playlist | 461 | Exact official OFL 1.1 asset; original notices bundled |
| BoecklinsUniverse | BoecklinsUniverse.ttf | Decade, Year | 1664 | Author OFL family evidence; exact bundled release unverified |
| Boogaloo-Regular | Boogaloo-Regular.ttf | Decade, Year | 281 | Embedded SIL OFL 1.1 |
| Cherry-Cream-Soda-Regular | CherryCreamSoda-Regular.ttf | Decade, Year | 227 | Embedded Apache 2.0 |
| ComfortAa-Medium | Comfortaa-Medium.ttf | All poster categories except Playlist | 850 | Embedded SIL OFL 1.1 |
| Plus Jakarta Sans Bold | PlusJakartaSans-Bold.ttf | Decade (2020s), Year (2020-2029) | 721 | Exact official OFL 1.1 asset; original notices bundled |
| Jura-Bold | Jura-Bold.ttf | Decade, Year | 1052 | Embedded SIL OFL 1.1 |
| Limelight-Regular | Limelight-Regular.ttf | Decade, Year | 413 | Embedded SIL OFL 1.1 |
| Monoton | Monoton-Regular.ttf | Decade, Year | 371 | Official OFL family evidence; exact bundled release unverified |
| Press-Start-2P | Press-Start-2P.ttf | Decade, Year | 556 | Embedded SIL OFL 1.1 |
| Righteous | Righteous-Regular.ttf | Decade, Year | 369 | Embedded SIL OFL 1.1 |
| Rye-Regular | Rye-Regular.ttf | Decade, Year | 258 | Embedded SIL OFL 1.1 |
| Special-Elite-Regular | SpecialElite-Regular.ttf | Decade, Year | 368 | Embedded Apache 2.0 |
| Trochut | Trochut-Regular.ttf | Decade, Year | 217 | Embedded SIL OFL 1.1 |
| UnifrakturCook | UnifrakturCook-Bold.ttf | Decade, Year | 246 | Embedded SIL OFL 1.1 |
| Yesteryear | Yesteryear-Regular.ttf | Decade, Year | 369 | Embedded SIL OFL 1.1 |
| Cairo-Regular | **Not bundled** | Comment only, no active table request | Unknown | Missing; no substitute chosen |

Embedded license declarations are evidence, not a clearance opinion. Separate
license text/provenance should be assembled before distributing fonts in a service.
See [the follow-up provenance review](FONT_PROVENANCE.md) and hash-pinned
`font_provenance.json` for primary sources, exact matches/mismatches, permission
restrictions, and the one-byte Helvetica table-boundary diagnosis. New inventories
apply that evidence only to the reviewed file hashes and require no network.
Remaining unverified binaries are not replaced or copied into new source files.
Retired Bebas/Helvetica records remain explicitly historical; tests no longer
require either restricted reference file.

None of the 17 active fonts covers Arabic. Non-Latin coverage varies markedly;
the codepoint inventory is authoritative for these exact files. Supported accented
Latin probes are rendered per font; unsupported characters produce explicit errors.
The optional `--complex-font` comparison uses an explicitly supplied local
Arabic-capable font for shaping tests **only**, never for a category substitution.
HarfBuzz plus BiDi does not require a platform-specific Pillow RAQM DLL. The Windows
validation uses existing system Arial; no proprietary binary is committed.
The retired Helvetica reference had an outline-table inconsistency rejected by
FontTools. The approved Plus Jakarta Sans Bold asset parses without that fallback; see
[its scoped comparison](HELVETICA_REPLACEMENT.md). Same-face native measurement
remains available for explicit user-supplied fonts when optional outline parsing
fails, with an offline synthetic regression rather than a restricted test asset.

## Read-Only Comparison Harness

The report includes A legacy/Python, B legacy/published, and C Python/published,
original output hashes, exact effective parameters and extracted row locations,
source hashes, font hash, dimensions/mode, difference visualizations, text crops,
isolated transparent captions, bounding-box deltas and Python line/advance metrics.
Missing published counterparts are reported, not searched by ambiguous basename.

The legacy bootstrap cannot be run safely against the working script: it queries
the release/version endpoint, can overwrite itself from `bullmoose20/Plex-Stuff`,
queries ImageMagick archive/Alpine/GitHub endpoints, can download/install portable
ImageMagick, and may install NuGet/7Zip4Powershell or change PSGallery trust.
It also probes OS/CPU/memory using platform tools. None is carried into Python.

For comparisons, an isolated copy retains parameter declarations, helper
definitions, validation and every rendering statement unchanged; it omits only
the `PRE-START` through banner/bootstrap invocation block. It points to an existing
ImageMagick executable. Update/install functions remain uncalled. Copies of fonts,
fades, transparent fallback, logs, playback and scratch outputs live only in a
private temporary workspace that is removed afterwards. The report records both
original and isolated script hashes and the exact omitted block. Original scripts,
font/fade files and selected logo/published inputs are hash-checked for preservation.

Metric screens use full-resolution RGB mean absolute error and a clearly labeled
global luminance SSIM at 400 x 600, not local/windowed SSIM. MAE >1.5 or global SSIM
<0.995 flags review. These screens **do not certify visual equivalence**. Differences
in both fresh engines versus published images are separated from migration-only
differences; unknown historical causes are not guessed away.
For RGBA overlays, metrics compare actual source-over color on the same neutral
`#808080` background and report alpha MAE separately. RGB hidden under zero alpha
is not counted as visible error. Alpha MAE >1.5 also flags review. Original PNG
previews use a neutral gray background; no rendered image is recolored by the report.

Each identical CLI workload records elapsed time, maximum sampled process-tree RSS,
sampled process write counters, and output bytes. Sampling is every 20ms and can
miss short-lived children; counters are lower-bound observations, not kernel disk
write totals. Startup probes are an empty PowerShell process versus Python composer
`--help` (which imports dependencies); they are not equivalent workloads. Rendering
measurements exclude fixture extraction, auto-fit calculation, and report creation.

Use a new report directory on every run:

```powershell
py -3.13 create_defaults/compare_poster_renderers.py --legacy-composer create_defaults/create_poster.ps1 --python-composer create_defaults/create_poster.py --assets create_defaults --published-repo "C:\path\to\Default-Images" --complex-font "C:\Windows\Fonts\arial.ttf" --report-dir config/default-poster-phase1/reproduce
```

`DEFAULT_IMAGES_LOCAL_REPO` and `DEFAULT_POSTER_COMPARISON_DIR` supply the two path
defaults. Existing report directories and report destinations inside the published
repository are rejected. There is no automatic clone, sync or network fetch.
`--powershell` and `--magick` select already-installed tools. `--case-filter`
(substring), `--limit`, `--timeout`, and `--python-only` support focused local runs.
Python-only comparison mode does not execute PowerShell or ImageMagick; without
the legacy bulk auto-fit calculation its rows are not a certified bulk baseline.
`--refresh-report <completed-directory>` refreshes HTML and adds measured source
alpha observations without invoking either renderer or changing output images.
Add `--recompute-metrics` to regenerate derived metrics/difference visualizations
from the preserved output files, verifying their hashes first.
`--legacy-baseline <local-report>` can reuse an earlier local legacy render only
after verifying the original composer, effective parameters, logo/sample hashes,
font hash and output hash. Repeat for multiple reports. It never treats published
artwork as a fresh legacy output. Reused outputs are explicitly recorded and
excluded from new performance results; use a fresh run without this option for
benchmarks.
Legacy logs indicating random-font selection or unreadable fonts are rejected,
including when attempting baseline reuse. Custom complex-font comparisons need
the corresponding ImageMagick-visible face name to match the explicit file stem;
otherwise the comparison fails visibly rather than accepting a random substitute.

Overlays deliberately remain separate: `CreateOverlays` uses `mogrify`, optionally
trimmed, at 285x85 or 440x100, and does not invoke the poster composer. Four read-only
reference probes compare those existing transforms using real genre/network logos,
with and without trim, at both sizes. They produce isolated PNGs, not poster API
outputs, and are excluded from the poster performance benchmark. The bulk overlay
workflow is neither replaced nor certified by these diagnostic probes.
The Python probe uses direct Lanczos filtering with thumbnail pre-reduction
disabled; no speed shortcut is substituted for the reference resampling.

## Offline Tests

```powershell
py -3.13 -m unittest discover -s create_defaults/tests -v
git diff --check
```

Tests use existing logos and all bundled fonts; small synthetic images are used
only for exact color/alpha arithmetic and failure injection. No network, PowerShell
or ImageMagick is required. Arabic shaping probes use an available explicitly
identified Arabic-capable font (`DEFAULT_POSTER_COMPLEX_FONT` overrides platform
test paths); absent that font, that test is skipped with an explanation.

The HTML report is a local file, not a web application. Open its `index.html`
directly. No Flask server, authentication, publication API or production replacement
is part of Phase 1. No commit/push is performed by these tools.
