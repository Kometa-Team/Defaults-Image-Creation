# Native poster renderer

Current standard: **Jost weight 260, 190px preferred size** for diiivoy and
diiivoycolor in both engines, with existing long-name auto-fit. The exact tested
static `fonts/Jost-260.ttf` and its OFL notice are bundled. No system font install
or runtime download is required. Futura's font file and embedded PowerShell copy
have been removed from the current working tree; historical reports below are
retained as evidence, not current font-selection instructions.

## Reference audit

The original reference was `create_people_poster.ps1` v2.7 (1012 lines, including
eight base64 literals: four artwork, four fonts). The current PowerShell fallback
retains its rendering operations but uses the approved Jost font and size instead
of Futura. Fonts load from `fonts/`; the unused legacy Futura literal was removed.
The artwork in `assets/people/` is decoded byte-for-byte from literals 1, 2, 3 and
8, not redrawn or regenerated.

| Operation | Reference behavior | Pillow equivalent |
| --- | --- | --- |
| Input | Flat `PEOPLE_CONFIG_DIR/people_dirs/Downloads/*.png`; unfinished PNGs in `tmppeople` | Same staged cutouts; no inference or online access |
| Normalize | Resize to width 2000, round height, center extent/crop to 2000x3000 | Premultiplied-alpha resampling, centered RGBA canvas |
| Placement | Trim bounding-box top; splice down until foreground starts at row 500; north extent clips overflow | Alpha bounding box, transparent translation on fixed canvas |
| Compositing | Over on embedded gray base, then exact transparent artwork | `alpha_composite` in encoded RGB, same layer order |
| Grayscale | `-colorspace gray -set colorspace gray` | Rec.709 luma, not Pillow's default Rec.601 conversion |
| Text | Local TTF, size-to-fit `label:`, trim, gravity/extent, then composite | Explicit FreeType font, measured/fitted labels, trim and matching anchors |
| JPEG | `-quality 100%`; output gray or RGB JPEG | Quality 100, 4:4:4; encoder rounding may differ |
| PNG | Normalized transparent PNG copied before placement | RGBA PNG, lossless alpha; never flatten to an opaque background |
| Naming | Remove `_ccexpress` in five composed filenames; strip trailing digits/`(N)` only from label; uppercase labels except signature | Same rules, Unicode filenames retained |
| Sorting | First uppercase filename character / `Images` / filename | Same relative paths |
| Temporary work | Move cutouts into tmppeople; repeatedly rewrite `_pushed.png`, then delete | In-memory intermediates and per-person temporary directory; retain failed source |
| QA | Gray, opaque, top alpha mean > .06, ratio, source size and canvas warnings | Same warning categories plus existing publication preflight before success |

The script has no generated shadows or borders. Its gradients, collection footer,
fades and decoration are baked into the four artwork files. Montserrat is checked
by the reference but is not used in any style's text drawing.

| Style | Derivation |
| --- | --- |
| original | Sort the preserved native photograph without changing its bytes. The existing publisher later creates its 2000x3000 RGB JPEG presentation. Never reconstruct a photo from a cutout. |
| transparent | Copy the width-normalized, centered 2000x3000 RGBA cutout before the 500px subject shift. |
| bw | Gray base + shifted gray cutout; Comfortaa 183, 1900x500 top label. A long 2-4-word name breaks after its first word. |
| signature | Gray base + **unshifted color** cutout + signature artwork; fitted Fuggles label in 1900x600, bottom offset 250. |
| diiivoy | Gray base + shifted grayscale subject + Clear3 artwork; centered Jost weight 260 at 190px/fitted label, 1900x580, top offset 80. |
| diiivoycolor | Same as diiivoy, retaining subject color. It re-creates the shifted cutout after diiivoy's gray temporary file; it is not a tinted grayscale poster. |
| rainier | Gray base + shifted color subject + Clear2 artwork; west-aligned Comfortaa label, 1600x580, top offset 80, with the reference's 1-4-word and JR. wrapping rules. |

`bw` changes its function-local uppercased label; PowerShell's scope rules mean
diiivoy and rainier still receive the original label, not BW's line breaks.
Signature always uses its separate mixed-case label.

High-margin legacy quirk: if the normalized foreground starts at/below row 500,
`Push-Down` does not regenerate `_pushed.png`. Diiivoy converts that file to gray,
so subsequent diiivoycolor and rainier unexpectedly retain the gray foreground.
Python deliberately preserves this observed behavior. Correcting it is a separate
style-behavior change, not part of the renderer migration.

## Fonts and rights

Bundled files: Comfortaa Medium, Fuggles Regular, Jost static weight 260 and
Montserrat SemiBold. No platform font lookup or unrelated substitution is
allowed. A font directory override must contain the same filenames, including
`Jost-260.ttf`; an old Futura-only directory is insufficient.

All four bundled fonts identify SIL OFL 1.1 in their
name tables. Preserve their notices and license when redistributing. Upstream
license references: [Comfortaa](https://github.com/google/fonts/blob/main/ofl/comfortaa/OFL.txt),
[Fuggles](https://github.com/google/fonts/blob/main/ofl/fuggles/OFL.txt),
[Montserrat](https://github.com/google/fonts/blob/main/ofl/montserrat/OFL.txt),
[Jost](https://github.com/google/fonts/blob/main/ofl/jost/OFL.txt).
See [font provenance](fonts/README.md) for the exact source and bundled Jost
hashes and generation settings. The selected font is the same 61 KB static
instance used in the approved weight-260 trial. Current rendering no longer
requires, uses or redistributes Futura. Historical Git revisions and ignored
local trial inputs are not rewritten and do not gain a license from this change.

## Usage

The Python engine uses Pillow, python-dotenv, alive-progress (shared publication
preflight), and fontTools. The extra fontTools dependency is narrowly required
for OpenType kerning, ligatures and contextual script forms on Pillow builds
without RAQM. It has a universal pure-Python distribution and needs no system
DLLs. Pillow remains the rasterizer/compositor; no ImageMagick subprocess or
other graphics backend is used. Font binaries are not modified on disk.

Install `requirements.txt` in the normal orchestrator environment and
`requirements-rembg.txt` in the selected recovery/background environment.
For standalone rendering in a clean Python 3.13 environment, the minimum is:

```bash
python -m pip install Pillow fonttools python-dotenv alive-progress
python create_people_poster.py --config config
python create_people_poster.py --config config/jobs/JOB_ID --names "Chae Soo-bin"
```

Each queued cutout needs its preserved source photograph, normally
`people_dirs/original/NAME.jpg` or its sorted `INITIAL/Images/NAME.jpg` archive.
Input cutouts must be single-frame transparent PNGs. Original archives retain
their native JPEG, PNG, WebP, BMP or TIFF format; composed styles are quality-100
JPEGs and transparent is 2000x3000 RGBA
PNG. Publication keeps its existing original-presentation normalization rules.

Configuration:

```dotenv
POSTER_ENGINE=python
POSTER_FONT_DIR=                 # default: repository fonts/
POSTER_ASSET_DIR=                # default: repository assets/people/
```

Use `POSTER_ENGINE=powershell` for the legacy rendering engine with the same
bundled Jost font and approved size; that explicit
selection requires PowerShell and ImageMagick. There is no automatic engine
fallback. Invalid values fail before processing. Neither engine selection
changes the publishing backend, destination branch, models or cleanup policy.

The orchestrator step remains `poster_ps1`:

```bash
python orchestrator.py --redo poster_ps1 --stop-after poster_ps1
```

A renderer/resource/version change invalidates that step and downstream
checkpoints only. A legacy PowerShell marker cannot satisfy a Python render.
The current batch's accepted cutouts are restaged from its transparent outputs
when needed, using the bounded input-name record, not a full library scan.
Older markers can recover those names from their last PowerShell log. Missing
retained inputs fail clearly and ask for explicit restaging, without rerunning
DDColor/BiRefNet. Do not change engines mid-publication: existing validated
receipts deliberately reject changed files. Finish the old batch with its old
engine or preserve it and create a new batch for reviewed replacement outputs.

Per-person outputs are encoded in a safe temporary directory and validated
before atomic file replacement. Successful inputs are removed from the queue;
failed inputs stay for retry. An interrupted multi-file replacement has no
successful receipt and can be retried. There is no cross-file atomic transaction.
Receipts hash the resources, inputs, native original and all seven outputs;
unchanged retries preserve bytes and modification times.

Logs remain `logs/create_people_poster.log`, with a structured
`logs/create_people_poster.json` summary and `.orch/poster-render.json` receipts.
Individual failures do not stop other portraits; the CLI exits 1 if any remain.
Configuration/resource errors exit 2. Native source archives are never
reconstructed from cutouts. Recovery renders alternates in isolation, preserves
previous outputs on failure, and archives accepted photographs using the existing
history safeguards before finalizing their sorted original path.

Missing fonts/assets are reported with their exact path. Unsupported glyphs fail
that person with an actionable error; there is no operating-system font fallback.
The font-layout adapter covers the bundled fonts' Latin kerning/ligature/context
tables, not arbitrary complex-script shaping. Accented Unicode labels and paths
are supported where the exact fonts contain those glyphs.

## Visual regression

Create isolated comparisons from preserved real pipeline jobs:

```bash
python compare_people_renderers.py --source-config config/jobs/JOB_ONE config/jobs/JOB_TWO --variants --output config/renderer-comparison/UNIQUE_RUN
```

Only this comparison command requires PowerShell/ImageMagick for its reference.
It never invokes the orchestrator or publisher and never modifies production
repositories. Source jobs are read-only. Derived cases are explicitly recorded
as variants, not represented as separately sourced people. `--variants` adds
grayscale, wide, edge-touching, long-label and accented-Unicode cases using an
actual source portrait.

Open the generated `index.html` and inspect every style's paired sheet. The JSON
report records source paths/hashes, timings, formats, dimensions, modes, alpha
error, visible-pixel MAE/RMSE and global SSIM. Foreground bounds are derived from
the paired alpha masks and known placement; originals have no alpha mask and
their subject bounds are explicitly unavailable. RGB under zero alpha is not
treated as visible error. Grayscale-alpha references are composited as alpha
images too. These metrics are screening aids, not a substitute for visual review.

Reports flag SSIM below .99, MAE above 3/255, or alpha MAE above 1/255 for
inspection. Small FreeType rasterization, resampling, JPEG encoder and rounding
differences are expected. Filenames, canvas sizes, formats and required alpha
properties are hard contracts. Comparison directories are manual local evidence,
not managed jobs: preserve reports and remove their test images/venvs explicitly
when no longer needed. Ordinary batch cleanup remains receipt-aware and unchanged.

## Font replacement trials

`compare_people_fonts.py` is an opt-in, local-only font audition utility. It does
not change `FONTS`, the private `.env`, orchestrator checkpoints or production
outputs. It reuses the Pillow renderer with an isolated in-memory font slot and
copies only trial Jost instances and their license into the requested report
directory. No font is renamed to masquerade as Futura. No additional dependencies
or rendering engines are needed.

Use the official Google Fonts [Jost variable font](https://github.com/google/fonts/tree/main/ofl/jost)
and its [SIL OFL 1.1 notice](https://github.com/google/fonts/blob/main/ofl/jost/OFL.txt).
Keep that notice with trial or redistributed font binaries. Jost has a continuous
100-900 weight axis, so 250 or 260 can be tested between the named ExtraLight 200
and Light 300 weights; they are actual font instances, not synthetic bolding.

```powershell
python compare_people_fonts.py --jost PATH/Jost-variable.ttf --license PATH/OFL-Jost.txt --output config/renderer-comparison/jost-UNIQUE --weights 200 250 300 --source-config config/jobs/JOB_ONE config/jobs/JOB_TWO
```

The report tests 14 uppercase names/specimens, including the four user-supplied
names, accents, punctuation, long labels and the alphabet. Unchanged 200px trials
are separate from trials that match the reference's rendered capital-H height. The
existing 1900x580 auto-fit remains active; no horizontal stretching or extra
tracking is applied. An alphabet specimen helps expose shape differences that
width/ink measurements alone cannot capture. A signed median ink-density change
is not a universal stroke-width measurement and can hide individual differences.

The utility now defaults to the bundled Jost reference at 190px. An external
reference can be supplied explicitly with `--reference-font PATH/font.ttf
--reference-size 200`; its licensing is the caller's responsibility. No legacy
font is fetched, bundled or required by the utility or its ordinary tests.

Historical pre-adoption auditions on 2026-10-15 used Futura at 200px:

- [Initial 200/250/300 comparison](config/renderer-comparison/jost-font-fit/review-v1/index.html):
  all 14 labels, both affected styles on three real preserved portraits.
- [Refined 250/260/275 comparison](config/renderer-comparison/jost-font-fit/refined/index.html):
  the same 14 labels and both affected styles on the long Naravit name.

| Jost weight | Matched-cap preferred size | Median absolute width difference | Median absolute ink-density difference |
| --- | --- | --- | --- |
| 200 | 190px | 2.86% | 26.76% |
| 250 | 190px | 1.59% | 4.64% |
| 260 | 190px | 1.48% | 2.45% |
| 275 | 189px | 1.51% | 7.25% |
| 300 | 190px | 1.35% | 17.30% |

The user-approved standard is **Jost 260, 190px preferred size**, matching
Futura's 133px H height at its original 200px setting. Its signed median width
change is -1.32%, and ink-density change +0.21%; the absolute differences above
are the more useful indication of variation across names. None of these 14 cases
changed the auto-fit branch or touched the label-box edges. This is a small test
set, not proof that every possible future name will fit identically.

The real-poster previews and enlarged label/alphabet sheets were inspected.
Jost 200 is too thin and 300 too heavy for the existing appearance; 260 is the
closest tested balance of size, weight and width. Jost is not a geometric clone:
capital J/Q, punctuation, accents and some spacing remain different. The user
approved the replacement after these trials. Both engines now use it, and their
renderer/resource fingerprints invalidate old poster/downstream checkpoints
without rerunning upstream inference. A full-library rebuild remains a separate
operation: no production image repository was regenerated or published.

The comparison utility's five focused tests cover trial isolation, calibrated
sizing, report/notice generation, refusing overwrite, and unclipped accented
glyphs/descenders in specimen sheets. Its font/report inputs are hashed for
reproducibility. Generated comparison fonts, images and JSON remain ignored local
evidence; they are not required for ordinary rendering.

## Jost adoption validation

Both updated engines rendered Chae Soo-bin and Naravit Lertratkosum from the
same preserved inputs. All **14 output contracts passed**, with no automated
review flags. Both side-by-side sheets were also visually inspected. Evidence:
[`Jost comparison`](config/renderer-comparison/jost-adopted-2/index.html),
[`metrics`](config/renderer-comparison/jost-adopted-2/report.json), and
[`adoption checks`](config/renderer-comparison/jost-adopted-2/adoption-validation.json).

- Diiivoy: maximum visible MAE 1.072 / 255; minimum global SSIM 0.999499.
- Diiivoycolor: maximum visible MAE 1.142 / 255; minimum global SSIM 0.999512.
- Both Naravit Jost outputs are byte-identical to the approved weight-260 previews.
- All five other styles are byte-identical to their pre-adoption Pillow outputs
  for both portraits (10/10 checks), using the retained receipt hashes.
- Font metadata confirms a static, non-variable font with weight class 260;
  tests cover preferred size, fitted long names, absence of Futura in the bundle
  and PowerShell script, and checkpoint invalidation for both engines.
- Full suite after adoption: **518 passed, 4 skipped, 20 existing warnings in
  149.52 s**, using the regression command below. The new local comparison CLI
  also ran against the bundled Jost default across all 14 labels; the matched
  weight-260 trial had zero width/density differences from that reference.
- No full-library rebuild, production image publication, commit or push was
  performed. Private publishing/background/workspace settings remain unchanged.

## Pre-Jost Phase 3 results

Validated locally on Windows x64, Python 3.13.15, Pillow 12.3.0 and fontTools
4.67.0. Python is now the default in code, `.env.example` and the private local
`.env`; the latter retains BiRefNet Portrait and `github_api`/`batch` settings.
No commit, push or production image-repository modification was performed.

The pre-Jost renderer-migration evidence is
[`phase3.html`](config/renderer-comparison/representative/phase3.html) and
[`report-phase3.json`](config/renderer-comparison/representative/report-phase3.json).
These ignored files are deliberately local, not assets needed by the renderer.
Three preserved pipeline portraits (Chae Soo-bin, Naravit Lertratkosum and a
Tom Hanks validation alias) plus five explicitly derived variants cover light
and dark source backgrounds, fine alpha edges, grayscale, wide/edge portraits,
long labels and accented names. All eight paired sheets were visually inspected.
There were 56 successful format/dimension/alpha contracts, with subject bounds
derived from the paired masks differing by at most two pixels.

| Style | Maximum visible MAE / 255 | Minimum global SSIM | Result across eight cases |
| --- | --- | --- | --- |
| original | 0.000 | 1.000000 | Eight byte-identical native archives |
| bw | 1.876 | 0.980350 | Same gray treatment, placement and label wrapping |
| diiivoy | 1.624 | 0.994396 | Same gray subject, artwork and Futura label |
| diiivoycolor | 1.694 | 0.994542 | Same color treatment, including documented high-margin legacy quirk |
| rainier | 1.486 | 0.972133 | Same artwork, west alignment and wrapping |
| signature | 2.559 | 0.983661 | Same color subject, footer and contextual script forms |
| transparent | 1.065 | 0.999946 | RGBA preserved; maximum alpha MAE 0.1083 / 255 |

The threshold flags were the Tom Hanks alias's BW and rainier labels and the
grayscale variant's signature label. All three were inspected at enlarged size
in `representative/review-flags.jpg`: the remaining differences are small glyph
rasterization and integer fitted-size/position differences, not missing text,
changed wrapping or materially different placement. Pixel-perfect equivalence
is not claimed. The original crop/placement rules, including existing clipping
and the high-margin gray-intermediate quirk, were preserved rather than redesigned.

Fresh-input timing for the same eight staged cases: **PowerShell 262.583 s;
Python 35.180 s**, approximately **7.5x faster** in this single local measurement.
Both timings cover the complete rendering command, not staging or comparison
metrics; Python includes interpreter/import/font startup and file I/O. All eight
were rendered, none skipped, with the Python process's `PATH` empty. A separate
clean Python 3.13 venv containing only the documented standalone dependencies
also produced all seven styles with an empty `PATH`. Python rendering and inline
recovery tests prohibit external rendering subprocesses.

Full regression command, from `create_people_posters/`:

```powershell
.\.venv-rembg\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

Pre-Jost result: **508 passed, 4 skipped, 20 warnings, 182.39 s**. The warnings are the
existing Pillow `getdata` deprecation in `edge_chop.py`; skipped tests include
opt-in/platform-dependent checks. Coverage includes Unicode directories and
filenames, all styles, partial failures/retry, idempotence, native originals,
checkpoint changes, both engine selections, actual Pillow inline recovery,
existing downstream preflight and preparing all seven GitHub API payloads.
Existing remote inventory, publication receipts/retries, batch retention/cleanup
and local Git tests pass. Both runtime venvs pass `pip check`. No new live GitHub
publication, model download/inference benchmark or separate Linux/macOS deployment
exercise was performed for this rendering migration.

## Changed files

Added:

- `create_people_poster.py`: rendering, validation, retry receipts and recovery API.
- `poster_fonts.py`: bundled-font layout adapter; Pillow still draws every glyph.
- `poster_renderer.py`: shared engine selection, fingerprints and bounded restaging.
- `compare_people_renderers.py`: isolated reference/comparison utility.
- `compare_people_fonts.py`: local auditions with optional external reference.
- `assets/people/`: four exact decoded artwork files from the original script.
- `fonts/Jost-260.ttf`, `fonts/README.md` and four `OFL-*.txt` files: the selected
  font, provenance and license notices.
- `tests/test_pillow_poster.py`, `tests/test_poster_selection.py` and
  `tests/test_people_font_comparison.py`.
- `POSTER_RENDERER.md`: this audit, operation/style mapping and validation record.

Modified:

- `orchestrator.py`: selected renderer under the existing `poster_ps1` step.
- `recover_edge_chops.py`: reuse the Python API or the explicit legacy fallback.
- `sync_people_images.py`: only guard CLI logging/dotenv initialization so importing
  the existing shared preflight has no CLI side effects; validation rules unchanged.
- `requirements.txt` and `requirements-rembg.txt`: portable fontTools and recovery
  preflight dependencies; inference versions unchanged.
- `tests/test_background_orchestrator.py`: preserve explicit legacy test selection
  and exercise real Python inline recovery.
- `.env.example`, People `README.md`, `CLONE_FREE.md` and root `README.md`:
  native default, usage and optional legacy dependencies.
- Private ignored `config/.env`: `POSTER_ENGINE=python` only.
- `create_people_poster.ps1`: approved Jost font/size, removal of the unused
  embedded Futura font and updated font checks/logging; other rendering unchanged.

Removed: `fonts/FuturaTEELig.ttf` from the current bundle.

The other existing fonts, DDColor/BiRefNet implementations, GitHub
publishing/inventory/receipt modules and batch cleanup implementation are
unchanged. Destination branches remain controlled by the existing configuration.

## Before service deployment

- Retain all four OFL notices and font copyright records with distribution.
  Historical snapshots containing Futura have not been relicensed or rewritten.
- Validate installation and output on the eventual service OS. This phase tested
  Windows, not a Linux/macOS deployment, and does not add a service worker,
  scheduler or Logscan integration.
- The exact bundled fonts still limit supported glyphs/scripts. Arbitrary
  complex-script shaping or a replacement typeface requires separate work and
  renewed visual comparison; there is no silent system-font substitution.
- Preserve publication receipts when changing engines: finish an in-progress
  publication with its original engine or start a new reviewed batch.
