# Helvetica Replacement: Approved Jakarta Configuration

## Decision

On **2026-10-16**, the user approved **Plus Jakarta Sans Bold** as the Helvetica
replacement and explicitly selected the **409-point height-matched version**.
The earlier Liberation Sans Bold trial was not approved because of the foot on
its digit `1`. Jakarta's default `1` has no bottom foot.

The 2020s decade poster and all ten 2020-2029 year posters now use:

- Family: `Plus Jakarta Sans`, style `Bold`, full name `Plus Jakarta Sans Bold`.
- Original filename: `PlusJakartaSans-Bold.ttf`, internal version **2.071**.
- **Fixed 409 points**, not an automatic fitting maximum.

The numeric command-building loops bypass auto-fitting only for these Jakarta
definitions. Otherwise the fitter would choose 381 points even with a 409-point
maximum. Other fonts/categories retain their existing fitting and cache behavior.
The comparison fixtures model the same fixed-size route, rather than silently
re-fitting the approved output. Colors, gradients, borders and offsets are unchanged.

## Measurements

| Caption | Original Helvetica | Approved Jakarta |
| --- | --- | --- |
| 2020s | 1169 x 315 pixels at 430 pt | 1246 x 315 at 409 pt |
| 2020 | 932 x 315 at 430 pt | 1029 x 315 at 409 pt |
| 2021 | 870 x 315 at 430 pt | 889 x 315 at 409 pt |

Jakarta is intentionally a new typeface, not pixel-identical Helvetica. Its rounder,
proportionally spaced numerals can be wider. Most captions match the old 315-pixel
height; `2028` is 316 pixels due to glyph overshoot. All remain one raster line.
The user approved these visual differences after reviewing both fitting options.

Portable team samples are in [the review bundle](review/README.md). The complete
local trial remains at `config/jakarta-comparison/index.html`; the installed-config
verification is at `config/jakarta-installed-verification/index.html`. Those ignored
folders are local artifacts, not links reviewers must depend on.

## Official Asset

The unchanged font and notices came from the
[official Tokotype repository](https://github.com/tokotype/PlusJakartaSans/tree/18d1cd2f7ea10481919d2f05c1f7064b7307fc26),
commit `18d1cd2f7ea10481919d2f05c1f7064b7307fc26`.

- Font path: `fonts/ttf/PlusJakartaSans-Bold.ttf`.
- Font SHA-256: `5f5342ef76862b5b5365d1dff1a667629dfa484e388dd602552f647219c3870f`.
- Original [OFL notice](fonts/licenses/PlusJakartaSans/OFL.txt), `AUTHORS.txt`,
  `FONTLOG.txt` and `README.md` are retained in `fonts/licenses/PlusJakartaSans/`.
- Original license SHA-256: `995c7199cab65954f545996326755daee7b63cc6b42b06c13da1f9502ab08a99`.

SIL OFL 1.1 permits bundling under its conditions, including retaining copyright
and license notices. The font remains under OFL rather than the project code
license. Neither the file, internal names, nor outlines have been modified. No
Helvetica-to-Jakarta alias masquerades as the old font.

Both PowerShell resolvers and Python's bundled mapping use the real font name.
The reviewed bundled file takes priority over a host-installed font of that name;
missing assets fail closed. The prerequisite list and expected checksum are updated.

Helvetica is absent from the distributable tree. Its unchanged private reference
is retained only under ignored `config/helvetica-font-candidate/reference/`.
The unapproved Liberation font/notices likewise remain only in the ignored
candidate workspace. No system fonts are uninstalled and no Git history is rewritten.

## Verification

All 11 installed outputs match the approved 409-point previews **byte-for-byte**.
All 3,341 unrelated rows and global fitting settings match the pre-Jakarta snapshot,
including the approved Bebas Playlist settings. An isolated AST-based PowerShell
test executes the real numeric command builders without bootstrap/publishing:
all 11 Jakarta commands use 409, while unrelated styles still call the fitter.

Offline regressions cover pinned font/notice bytes, aliases, outline parsing,
the footless digit `1`, fixed-size fitting, and stale provenance rejection.

```powershell
py -3.13 -m unittest discover -s create_defaults/tests -v
pwsh -NoLogo -NoProfile -File create_defaults/tests/verify_jakarta_bulk.ps1
git diff --check
```

Optional local preview verification, with a fresh output directory and your
existing private trial artifacts:

```powershell
py -3.13 create_defaults/verify_jakarta_replacement.py --preview-report config/jakarta-comparison --previous-bulk config/jakarta-approval-reference/create_default_posters.ps1 --report-dir config/jakarta-reverification
```

The general Python renderer migration remains a review candidate, not a production
cutover. This font approval does not approve the full batch migration or deployment.
