# Bebas Replacement: Comparison and Configuration

This records the Bebas replacement checkpoint. The subsequent independent
[Helvetica replacement](HELVETICA_REPLACEMENT.md) changes 11 Decade/Year rows;
the Bebas measurements and visual sign-off below remain unchanged.

## Recommendation and Applied Change

Use **Bebas Neue Regular v2.000** from the official Dharma Type repository,
unmodified, under its SIL OFL 1.1 license. The nine Playlist definitions now use
the actual family name `Bebas Neue`, bundled file `BebasNeue-Regular.ttf`, with
the Playlist fitting maximum increased from 140 to **154 points**.

This is an intentional font replacement, not a pixel-identical migration claim.
The tuned Neue candidate has the lowest foreground caption-shape error, matching
the user's preferred candidate. **Bebas Kai at 143 points preserves the original
dimensions more closely and has slightly lower whole-poster error.** Both tradeoffs
are recorded rather than claiming that one candidate wins every measurement.

Open the [local side-by-side HTML report](../config/bebas-replacement/index.html).
It contains all nine original PowerShell/ImageMagick posters, both candidates at
the existing fitting limit, both size-adjusted candidates, text crops, differences,
per-glyph advance widths, outline bounds, shaping positions, and exact parameters.
No restricted font binary is included in that report. No web server is needed.

## Visual Sign-Off

The user approved the visual replacement on 2026-10-15: Bebas Neue Regular
v2.000, actual family `Bebas Neue`, bundled file `BebasNeue-Regular.ttf`, with
the Playlist fitting maximum set to 154 points. This approval covers the font
replacement only; it does not authorize committing, pushing, or proceeding with
the broader Python/Pillow migration.

## Measured Results

All nine real English Playlist configurations use `TIMELINE ORDER`. Thus each
candidate has the same measured caption across nine different logos/backgrounds.
The original bulk fitter measures 401 points before applying its 140-point cap.

| Variant | Points | Raster Ink WxH | Unhinted Shaped Advance | Foreground Caption Alpha MAE | Mean Full-Poster RGB MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original restricted Bebas | 140 | 748 x 102 | 755.020 | 0 | 0 |
| Bebas Neue, unchanged fitting | 140 | 685 x 102 | 688.520 | 154.152886 | 1.064404 |
| Bebas Kai, unchanged fitting | 140 | 731 x 101 | 733.880 | 119.446546 | 0.736517 |
| **Bebas Neue, selected adjustment** | **154** | **753 x 111** | **757.372** | **68.970924** | **0.421501** |
| Bebas Kai, best adjustment | 143 | 746 x 104 | 749.606 | 73.565642 | 0.414053 |

MAE uses a 0..255 scale. Caption error is normalized over the union of visible
alpha pixels, avoiding the misleading effect of a large empty caption canvas.
Whole-poster error includes the unchanged logo/background and is secondary when
judging letterforms. Its slight preference for Kai does not contradict Neue's
better foreground-normalized shape score: area and raster alpha weight the
differences differently. Similarity metrics assist visual review, not legal or
visual certification.

At 154 points, Neue's caption is five pixels wider and nine pixels taller than
original. Its shaped advance is 2.352 pixels wider. Caption ink bounds projected
into poster coordinates, before JPEG ringing/rounding, are:

- Original: `[626, 1899, 1374, 2001]`.
- Selected Neue: `[623, 1894, 1376, 2005]`.
- Tuned Kai: `[627, 1898, 1373, 2002]`.

All variants have one raster line band: no wrapping was introduced. ImageMagick
trims and centers the ink as before. The selected ink center shifts only half a
pixel in each axis due to odd dimensions; no text offset/gravity was changed.
The caption has zero HarfBuzz kerning adjustment in all three fonts. Exact glyph
advances, outline bounds and shaped positions are recorded separately from raster
ink sizes; font-unit metrics are not misrepresented as hinted pixel bounds.

Size search tested integer sizes around the width- and height-derived estimates,
including the unchanged setting, and selected the lowest measured foreground
alpha error subject to the existing 1600 x 1000 fit bounds. It selected 154 for
Neue and 143 for Kai. No horizontal stretching or altered font outlines were used.

## Official Assets and Licenses

| Candidate | Official Commit | Original Filename | Version |
| --- | --- | --- | --- |
| [Bebas Neue](https://github.com/dharmatype/Bebas-Neue) | `46e72cec95ee599f72c0de4a12cfe64828949236` | `BebasNeue-Regular.ttf` | 2.000 |
| [Bebas Kai](https://github.com/dharmatype/Bebas-Kai) | `f94118f4686b548f721ae364c0eae4dfe287c057` | `BebasKai.ttf` | 1.002 |

Neue was obtained from the repository's
`fonts/BebasNeue(2018)ByDhamraType/ttf/` directory, preserving that upstream
directory spelling. It is **not** the separate 2014 Fontfabric family also hosted
in that repository. Its SHA-256 is
`08e4623805102d819f58601e46e345648846075e363b2ceb23313c2d1c83ec73`.
Kai's SHA-256 is
`35a74556f4a07d2e8402321fb1388310f0d3654b0276dd7c77b2d6b58290daef`.

The selected font's original notices are retained without editing in
[`fonts/licenses/BebasNeue/`](fonts/licenses/BebasNeue/):

- `OFL.txt`, including the original copyright notice.
- `AUTHORS.txt`.
- `CONTRIBUTORS.txt`.
- `TRADEMARKS.md`.

Local file-scoped Git attributes preserve the original notice bytes on Windows
checkout. Original trailing whitespace in the upstream OFL/contributor notices is
retained with exemptions scoped to those notices; ordinary source checks remain
enabled. All four original notice hashes are covered by regression tests.

The [original OFL 1.1 notice](https://raw.githubusercontent.com/dharmatype/Bebas-Neue/46e72cec95ee599f72c0de4a12cfe64828949236/OFL.txt)
permits bundling and redistribution of the unmodified font with software when
the required copyright/license notices accompany it. Do not sell the font by
itself or relicense the font as project code. No family name or font filename was
changed, and no font binary was modified. The original OFL license notices for
both evaluated candidates are preserved in the local candidate workspace.

## Reference Inventory and Scope

The pre-change reference inventory found:

| Location | Restricted Bebas References | Applied Action |
| --- | --- | --- |
| `create_default_posters.ps1` | Bundled alias mapping | Replaced with actual Neue family/PostScript aliases |
| `create_default_posters.ps1` | Font prerequisite list | Changed to `Bebas Neue` |
| `create_default_posters.ps1` | Nine embedded Playlist definitions | Changed font field only |
| `CreatePlaylist` | Existing 140-point fitting maximum | Increased to 154; min/box unchanged |
| `Get-Checksum-Files` | Font filename and expected SHA-256 | Updated to exact official Neue asset |
| `create_poster.ps1` | Bundled alias mapping | Replaced; no old-name-to-new-font alias |
| PowerShell font resolution | Host-installed font priority | Neue alone prefers the reviewed bundled file; other families retain existing behavior |
| `poster_text.py` | Python's active bundled font list | Replaced restricted asset; accepts actual `Bebas Neue` family name |
| Documentation/tests/provenance | Names, license warnings, assertions | Current records updated; historical audit references retained explicitly |

The fitting cache includes the resolved font path and fitting limits in its key,
so the new filename and 154-point limit do not reuse the old Bebas cache entries.
Neue's bundled path uses forward slashes for ImageMagick on Windows; no font
installation, random substitution or modified internal family name is required.

All 3,343 non-Playlist literal definitions and their fitting settings were checked
against the pre-change source snapshot. The nine Playlist rows retain all other
fields: logo resize 1600, logo offset -200, text offset +450, colors, gradients,
white-wash, filenames, and borders. Other fonts and published artwork are untouched.
No translation, publishing, or bulk-generator redesign is included.

The restricted file was removed from `create_defaults/fonts/` **only after**
comparisons established the selection. Its unchanged local reference is kept under
ignored `config/bebas-font-candidates/reference/`, outside distributable source.
This does not rewrite Git history or uninstall the user's existing system font.
Do not add that private reference directory to a release or container image.

Original output used an installed Bebas registration whose SHA-256 was verified
identical to the local reference. Both replacement outputs used exact bundled-file
fallback, recorded in logs. A comparison-helper case-sensitivity issue was found
during verification: the initial run did not force the already-verified original
registration off. The preserved report identifies what actually happened; later
runs explicitly force exact files case-insensitively. This does not change the
validity of the initial baseline, whose actual registered file hash was verified.

## Reproduce Locally

From the repository root, using a fresh report directory:

```powershell
py -3.13 create_defaults/compare_bebas_fonts.py --fetch-candidates --original-font config/bebas-font-candidates/reference/Bebas-Regular.ttf --bulk-definition config/bebas-font-candidates/reference/create_default_posters.ps1 --legacy-composer config/bebas-font-candidates/reference/create_poster.ps1 --report-dir config/bebas-replacement-reproduce
py -3.13 -m unittest discover -s create_defaults/tests -v
git diff --check
```

`--fetch-candidates` explicitly downloads only the two OFL candidates and their
original notices at pinned author commits. Subsequent runs can omit that flag;
cached bytes must match pinned hashes. The restricted font is never downloaded by
the tool. On another checkout, supply your own authorized original font and the
pre-change source snapshots instead of expecting the ignored local references to
be distributed. No automatic install/update/publishing bootstrap is executed.

The English nine-poster comparison does not certify every translated caption.
The replacement expands mapped character coverage from 110 to 461 codepoints,
but future multilingual acceptance remains separate. No broader Python/Pillow
migration proceeds as part of this task. No commit or push is performed.

## Validation Results

- 45 comparison posters completed: nine original, nine for each candidate at
  existing fitting, and nine for each candidate at its best measured adjustment.
- All nine outputs from the updated production configuration are byte-identical
  to the selected comparison images. Verification metadata is stored locally in
  `config/bebas-installed-verification/summary.json`.
- All 3,343 non-Playlist literal definitions and fitting settings are unchanged.
- All 50 offline regression tests passed in 30.381 seconds, including the original
  41 tests and nine focused replacement/comparison tests.
- Both PowerShell scripts pass syntax parsing without executing their bootstrap.
- Index and all nine report pages pass browser checks at 1440px and 390px, with
  images loaded and no horizontal overflow or page errors.
- Original font/source snapshots and candidate assets are hash-verified. The
  restricted font is absent from distributable assets; no font is renamed or
  internally edited. The HTML report contains no font binaries.
