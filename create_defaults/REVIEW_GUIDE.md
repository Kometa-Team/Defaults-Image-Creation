# Default Poster Migration: Team Review

## Current State

`create_poster.ps1` has a native Python/Pillow migration candidate:
[`create_poster.py`](create_poster.py), with a callable API and CLI. It renders
without invoking PowerShell/ImageMagick, network downloads or publishing.
This is not a claim that the production workflow has switched to Python.

`create_default_posters.ps1` remains the bulk orchestrator and still calls
`create_poster.ps1`. Category generation, translations, publishing and repository
sync have not been migrated. Both PowerShell files remain available for comparison.

Approved font changes are applied to both font resolvers:

- Playlist: Bebas Neue Regular v2.000, fitting maximum 154 points.
- 2020s decade and 2020-2029 years: Plus Jakarta Sans Bold 2.071, fixed 409 points.
- Restricted Bebas and Helvetica binaries are removed from distributable source.
- Original OFL copyright/license notices accompany both replacements.
- The unapproved Liberation trial is not bundled.

## What To Review

Start with [portable before/after samples](review/README.md), then inspect
`create_poster.py`, `poster_text.py`, the fixture/comparison helpers, and tests.
The samples compare the current PowerShell reference with the Python candidate,
using the approved fonts. They are not a complete batch acceptance certificate.

The original [Phase 1 results](PHASE1_RESULTS.md) are a historical checkpoint:
129 cases, including explicit local shaping probes, had 116 passing screens,
13 review warnings and no failures. Those warning visuals received user approval.
Do not reinterpret those old-font measurements as a new-font full batch run.

The current offline fixture builder audits 3,352 literal rows in 21 categories
and builds 126 representative/stress cases. The full 3,352-row render comparison
has **not** been run. Focused current-font comparisons and the unit suite are
recorded in the draft PR validation results.

## Run Locally

Python 3.11+ is required; use the explicit 3.13 launcher on Windows:

```powershell
py -3.13 -m pip install -r create_defaults/requirements.txt
py -3.13 -m unittest discover -s create_defaults/tests -v
pwsh -NoLogo -NoProfile -File create_defaults/tests/verify_jakarta_bulk.ps1
py -3.13 create_defaults/create_poster.py --help
```

Tests work without the ignored translation cache. The original MIT-licensed
[English fixture](fixtures/english/README.md) is pinned and bundled for offline
review; it does not change production translation behavior. The isolated
PowerShell test is skipped by Python when PowerShell 7 is unavailable.

For a fresh representative comparison, install PowerShell 7 and ImageMagick
yourself, then run:

```powershell
py -3.13 create_defaults/compare_poster_renderers.py --report-dir config/team-representative-comparison
```

Use a fresh destination. Reports never overwrite published artwork and do not
install or update tooling. Optional published-image comparisons require an
explicit local read-only Default-Images checkout.

## Next Gate

After team review, run the current representative matrix and plan a full frozen
batch comparison of all real definitions against the PowerShell reference.
Inspect layout/glyph/alpha differences and retain evidence before switching any
bulk calls to Python. The current helper's default is representative coverage,
not a hidden full-batch mode. No full-batch driver or production switch is claimed.

The separate Boecklins Universe and Monoton exact-release provenance questions
remain documented in [the audit](FONT_PROVENANCE.md); they are not silently
declared resolved by the Bebas/Jakarta approvals. No merge or deployment is part
of this review publication.
