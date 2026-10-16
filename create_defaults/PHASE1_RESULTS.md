# Default Posters: Phase 1 Results

For the current published review scope, approved fonts and portable images, see
[the team review guide](REVIEW_GUIDE.md). Historical `config/` reports referenced
below are local artifacts and are not included in the review checkout.

Historical checkpoint: this document's original metrics and source-preservation
statements describe the pre-replacement Phase 1 run. The subsequent authorized
[Bebas replacement](BEBAS_REPLACEMENT.md) changes only Playlist font selection,
fitting, and supporting font mappings/checks; it bundles original OFL notices and
removes the restricted font from distributable source. The original visual report
is preserved unchanged, not relabeled as a comparison of the new font.
The later [Helvetica replacement](HELVETICA_REPLACEMENT.md) similarly has its own
11-poster comparison. Neither replacement rewrites this historical checkpoint.

## Recommendation

**Visual review accepted; keep the production workflow unchanged.** On
2026-10-15, the user reported that visual inspection of the warning cases looked
fine. Record those differences as visually accepted for this report, not as
pixel-identical results or automatically passing metric screens. Ten poster cases
and two independent overlay probes still flag migration differences; one
additional poster flags a historical published difference.

The visual-review blocker is cleared. See the [font provenance follow-up](FONT_PROVENANCE.md)
for precise license evidence and the diagnosed Helvetica one-byte table-boundary
issue. Font permissions/provenance and optional independent Unix validation remain
follow-ups before production integration; no Linux validation has been run.
Phase 2 can be planned separately; no Phase 2 implementation or production switch
is authorized by this visual sign-off. PowerShell remains the production reference.

No original PowerShell script, category definition, translation, logo, font, fade,
or published image was changed. Work remains uncommitted on `main`. Nothing was
staged, pushed, deployed, published, or synchronized.

## Parameters and Fonts

The [complete audit and 20-parameter mapping](PYTHON_COMPOSER.md#complete-parameter-mapping)
records every legacy default, rendering stage, validation/coercion behavior,
dependency, bootstrap download, and intentional safety difference. The Python
entry point supports both a callable API and a CLI without PowerShell/ImageMagick.

Per the user's clarification, `dom_color` and `dom_color_image` stay reserved
no-ops, exactly as in legacy. No dominant-color extraction feature is implemented.
Average-color sampling remains supported. No speculative border behavior remains.

The [font inventory](PYTHON_COMPOSER.md#font-inventory) covers all 17 active families
and their categories. The report's `font-inventory.json` additionally records exact
paths, hashes, embedded license evidence, requested spellings, category row counts,
and all mapped Unicode codepoints. The source audit found 3,352 literal definition
rows across 21 poster categories, including generated-command and variable-font
usage rather than only explicit `-font` arguments.

Initial licensing evidence was 11 SIL OFL declarations, two Apache declarations,
three generic unverified labels, and proprietary Helvetica. The follow-up found
an exact author-linked Bebas EULA match with redistribution/modification
restrictions, plus upstream OFL family evidence for Boecklins Universe and Monoton;
their exact bundled-release provenance still needs confirmation. The initial
visual report is retained unchanged as a historical snapshot. Embedded declarations
and upstream family evidence are not legal clearance. No font binaries were added.
`Cairo-Regular` occurs in a comment but is not bundled or actively requested.
None of the 17 active fonts covers Arabic. Four additional Arabic/mixed-direction
probes use explicitly supplied local system Arial, never a category substitution.
Helvetica's existing malformed outline table is tolerated by rendering its exact
unchanged outlines through FreeType; it still needs asset/license review.

## Representative Cases

Open the local [129-case visual report](../config/default-poster-phase1/poster-parity/index.html).
It is a static HTML file; no server is required.

| Group | Cases |
| --- | ---: |
| Actual category definitions with recorded published destinations | 40 |
| All 17 fonts: short, long, multiline, plus 16 supported-accent probes | 67 |
| Five gradients and nine other feature variants | 14 |
| Independent overlay-reference transforms, both sizes and trim modes | 4 |
| Explicit Arabic, long Arabic, mixed-direction, and multiline shaping | 4 |
| Total | 129 |

Actual rows cover Aspect, AudioLanguage, Awards, Based, Chart, ContentRating,
Country, Decade, Franchise, Genre, Network, Playlist, Resolution, Seasonal,
Separators, Streaming, Studio, SubtitleLanguage, VideoFormat, Universe, and Year.
Feature variants cover transparent/colored logos, wash on/off, small/large logos,
positive/negative offsets, empty captions, borders, average sampling, and the
reserved dominant-color no-op. Exact effective parameters, input/font hashes,
source rows, point-size fitting, and destination names are recorded per case.

## Three-Way Results

**116 pass screens, 13 warnings, zero execution failures.** Every compared pair
has matching dimensions. Passing a metric screen is not acceptance certification.
The user has visually accepted the warning cases; the recorded metrics, warning
counts, rendered images, and historical-difference diagnosis remain unchanged.

MAE is full-resolution RGB error on a 0..255 scale. SSIM is explicitly a
400 x 600 **global luminance** measurement, not windowed SSIM. Screens flag
MAE >1.5, global SSIM <0.995, or overlay alpha MAE >1.5. Transparent overlays are
compared source-over on the same neutral gray, excluding invisible RGB data.

| Baseline | Pairs | Mean MAE | Maximum MAE | Minimum global SSIM | Flagged pairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| A: legacy / Python, posters and overlay probes | 129 | 0.204471 | 1.557610 | 0.957044 | 12 |
| A: poster composer only | 125 | 0.179866 | 1.449587 | 0.957044 | 10 |
| B: legacy / published | 44 | 0.030750 | 1.352986 | 0.990889 | 1 |
| C: Python / published | 44 | 0.208173 | 1.557610 | 0.990841 | 4 |

The 44 published counterparts comprise all 40 actual poster definitions and four
overlay probes. **43 are byte-identical to locally rendered legacy output**:
39 posters and all four overlays. Stress/feature variants intentionally have no
published destination; they are not passed off as missing historical artwork.

The remaining published poster is `genre-4652`, "1001 MOVIES YOU MUST SEE BEFORE
YOU DIE." Legacy/published MAE is 1.352986; Python/published is 1.418062. Fresh
legacy/Python agree much more closely (MAE 0.511069, global SSIM 0.998765), including
the same four-line wrap. This indicates a historical configuration/rendering
difference, but its exact cause is unproven. No migration change was made simply
to chase that historical image.

The report reused 125 legacy images rendered locally during this assignment,
after checking composer source, exact parameters, font, inputs, and output hashes;
the four overlay probes were rendered directly. Reused images are not treated as
fresh timing samples or confused with published artwork. The retained manifest
preserves the source hashes at that visual checkpoint. Subsequently removing an
uncalled dominant-color utility changed no rendering statements; the final test
suite and separate fresh benchmark use the final source.

## Remaining Visual Flags

| Case or group | MAE | Global SSIM | Observation |
| --- | ---: | ---: | --- |
| Cherry Cream Soda, long | 0.534056 | 0.994898 | Identical outer ink bounds; interior raster/spacing differs |
| Cherry Cream Soda, multiline | 0.325638 | 0.994927 | Right ink edge differs by one pixel |
| Comfortaa, multiline | 0.337400 | 0.993779 | Ink edges differ by up to one pixel |
| Monoton, actual 1970 year | 0.219621 | 0.994221 | Right ink edge differs by one pixel |
| Monoton, short | 0.104860 | 0.988843 | Thin striped glyphs amplify rasterization differences |
| Monoton, long | 1.215992 | 0.981231 | Internal glyph and line-spacing differences remain |
| Monoton, multiline | 1.449587 | 0.957044 | Largest poster difference; review isolated captions |
| Monoton, accents | 0.612255 | 0.978058 | Exact font retained; no substitute |
| Righteous, long | 0.806321 | 0.986758 | Right/bottom ink edges differ by one pixel |
| Special Elite, long | 0.526044 | 0.992199 | Right/bottom ink edges differ by one pixel |
| Genre overlay, standard | 1.557610 | 0.998948 | Alpha MAE 3.233613 |
| Genre overlay, bigger | 1.450450 | 0.998953 | Alpha MAE 3.026351 |

All measured caption outer-bound coordinates differ by at most one pixel, not
just those listed. This does not establish identical internal baselines, kerning,
or antialiasing. The remaining glyph differences are consistent with rasterization
and rounding differences, but that is not a complete root-cause proof. Caption
PNGs, advances, line heights, crops, and amplified difference images are provided
for inspection. Monoton was included in the warning cases accepted by the user;
its measured differences remain documented rather than relabeled as identical.

Both network overlay probes pass screens (visible MAE 0.492579/0.392820; alpha MAE
1.104741/0.815663). Genre probes still expose Pillow/ImageMagick alpha-resampling
differences despite direct Lanczos filtering. Overlays do not use the poster
composer; these are diagnostic references, not a converted overlay API or a
replacement for the deferred bulk generator.

## Validation

| Check | Result |
| --- | --- |
| New offline unittest suite, including font follow-up | 41 passed, 27.488 seconds; no skipped Arabic test on this machine |
| Existing People renderer/font comparison tests | 28 passed, 86.36 seconds; one existing FontTools/HarfBuzz deprecation warning |
| Five new Python files compiled | Passed |
| Both original PowerShell scripts parsed without execution | Passed |
| Static report at 1440px and 390px | Passed: images loaded, no page errors or index overflow |
| `git diff --check` | Passed |
| Published repository read-only Git status | Clean |

Tests cover every public parameter, all gradients, exact fade bytes, bounded
inputs/workspaces, JPEG stages, wrapping/overhang, all fonts, supported accents,
Arabic shaping, colors, borders, alpha, wash, extraction/no-op semantics, Unicode
paths, deterministic output, filenames, source preservation, failure cleanup,
exclusive-open races, no external renderer/network in Python mode, baseline
validation, and report compatibility/refresh without altering rendered images.

Validation was executed on Windows with Python 3.13.15, Pillow 12.0.0, PowerShell
7.6.6, and locally installed ImageMagick 7.1.2 Q16 HDRI. Python has no shell-dependent
rendering path; Unix execution has not been independently tested in this session.
Original production scripts were parsed, not run through their update/download
bootstrap. Their unchanged rendering bodies were exercised in isolated copies.

## Performance

The [fresh benchmark report](../config/default-poster-phase1/benchmark-stable/index.html)
ran one actual poster per category, serially, with both engines launched afresh.
All 21 cases passed screens, with zero warnings/failures, and the final source
integrity check passed. Each engine's 21 output hashes also matched its earlier
129-case visual checkpoint, confirming unchanged output after the deferred
dominant-color helper was removed.

| Measurement, 21 identical poster workloads | Legacy | Python |
| --- | ---: | ---: |
| Total renderer process time | 89.964 s | 20.654 s |
| Average per poster | 4.284 s | 0.984 s |
| Maximum sampled process-tree RSS | 518,819,840 bytes (494.8 MiB) | 174,092,288 bytes (166.0 MiB) |
| Sum of sampled process write counters | 20,847,618 bytes | 25,357,955 bytes |
| Total final JPEG sizes | 11,083,580 bytes | 13,282,690 bytes |
| Separate startup probe | 0.461 s, empty PowerShell | 0.291 s, Python composer `--help` |

Python was about 4.36 times faster for this measured group, not a universal
throughput promise. Its JPEGs were about 19.8% larger and observed writes were
higher; encoder-size differences have not been optimized away at the cost of
appearance. No optimization of the renderer was based on a speed assumption.

Both engines used fresh CLI processes, shared warm OS filesystem caches, and
ImageMagick/OMP thread limits of one. Measurements exclude fixture extraction,
bulk point-size fitting, report generation, and overlay-reference probes.
RSS/write sampling is every 20ms and can miss short-lived children. Process-tree
RSS can count shared pages more than once; it is not unique physical memory.
Write counters are lower-bound process observations, not guaranteed physical disk
traffic. The startup probes do different work and must not be treated as an
apples-to-apples startup comparison. No cached legacy render contributed timings.
An earlier benchmark invalidated by a source edit was discarded; only this
source-frozen successful run is reported here.

## Files

Ten new source/document files, including the subsequent font review:

- `create_defaults/create_poster.py`: callable composer and standalone CLI.
- `create_defaults/poster_text.py`: exact-font resolution and shaped glyph layout.
- `create_defaults/poster_fixtures.py`: read-only extraction and font inventory.
- `create_defaults/compare_poster_renderers.py`: isolated A/B/C reports and timing.
- `create_defaults/requirements.txt`: pinned Python dependencies.
- `create_defaults/tests/test_create_poster.py`: offline regression tests.
- `create_defaults/PYTHON_COMPOSER.md`: full API, parameter, font, and dependency audit.
- `create_defaults/PHASE1_RESULTS.md`: this report.
- `create_defaults/FONT_PROVENANCE.md`: primary-source license and file-health review.
- `create_defaults/font_provenance.json`: offline, exact-hash-bound evidence records.

The only existing tracked file changed is `create_defaults/README.md`, with a link
to the experimental documentation. Generated comparison artifacts and local QA
scripts are ignored under `config/default-poster-phase1/`; no source artwork or
binary fonts are added to version control.

## Reproduce

Run from the repository root, using a **new, nonexistent** report directory.
The comparison needs existing local PowerShell/ImageMagick; the Python composer
and ordinary unit tests do not. No tools, assets, or published repository are
downloaded automatically.

```powershell
py -3.13 -m pip install -r create_defaults/requirements.txt
py -3.13 -m unittest discover -s create_defaults/tests -v
py -3.13 create_defaults/compare_poster_renderers.py --legacy-composer create_defaults/create_poster.ps1 --python-composer create_defaults/create_poster.py --assets create_defaults --published-repo "C:\path\to\Default-Images" --complex-font "C:\Windows\Fonts\arial.ttf" --report-dir config/default-poster-phase1/reproduce
py -3.13 create_defaults/compare_poster_renderers.py --limit 21 --published-repo "C:\path\to\Default-Images" --report-dir config/default-poster-phase1/reproduce-benchmark
py -3.13 -m pytest create_people_posters/tests/test_pillow_poster.py create_people_posters/tests/test_people_font_comparison.py -q -p no:cacheprovider
git diff --check
```

The historical run rendered 129 cases, including four explicit Arabic probes.
These commands now use the checkout's current fonts; current fixture counts are
documented in the review guide rather than inferred from that historical run.
Existing People tests also need that renderer's previously declared dependencies.
For Unix, use its Python 3.13 interpreter and an explicit locally licensed
Arabic-capable font; do not assume the Windows font path exists.

The warning cases, including the font/overlay and historical-poster differences,
have received user visual approval. Before production integration, resolve the
font permission/provenance items in the follow-up review and select licensed
coverage for any future unsupported translations. Helvetica's file inconsistency
is diagnosed; no repair or substitution was made. Local Linux testing is possible
via installed Docker once its engine is started, but has not been run and is not
a mandatory scope expansion. No bulk-generator or service work is included here.
