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
- Monoton: approved official Google Fonts release; original OFL notice bundled.
  All 11 numeric PowerShell outputs match the approved comparison; Python's
  old/new font outputs are also byte-identical. Only its dependency checksum changed.

## What To Review

Start with [portable before/after samples](review/README.md), then inspect
`create_poster.py`, `poster_text.py`, the fixture/comparison helpers, and tests.
The samples compare the current PowerShell reference with the Python candidate,
using the approved fonts. They are not a complete batch acceptance certificate.

The original [Phase 1 results](PHASE1_RESULTS.md) are a historical checkpoint:
129 cases, including explicit local shaping probes, had 116 passing screens,
13 review warnings and no failures. Those warning visuals received user approval.
Do not reinterpret those old-font measurements as a new-font full batch run.

The frozen default-English inventory now resolves all 3,352 literal rows into
9,958 effective composer invocations in 21 categories, including 165 generated
input dependencies. It records 36 overlay transforms separately. The expanded
offline runner, resume semantics and CI boundary are documented in the
[validation runbook](VALIDATION_RUNBOOK.md). The original 129-case evidence stays
historical; the refreshed current-font matrix contains 126 cases.

The [2026-10-16 checkpoint report](PHASE1_VALIDATION_20261016.md) records the
user-requested stop at 6,631 paired jobs: 6,530 passing screens, 101 warnings,
zero failures and 3,327 untested jobs. It is ready for checkpoint review, not
merge. Its historical STOP marker stays in place; continuation uses the separate
approved-font directory described below.

The user subsequently authorized continuation. The original checkpoint and its
STOP marker are preserved; a separately audited continuation uses
`fixtures/effective-jobs-en-monoton-ofl.json.gz` and copies only hash-verified
unchanged jobs. New bulk work is under
`config/phase1-validation-20261016/full-batch-monoton-ofl/`.
That continuation is now complete: all 9,958 jobs and all 3,352 literal rows are
paired, across all 17 fonts and 21 categories. Results are 9,255 passing screens,
703 warnings and no failures. Of those flags, 602 are newly rendered continuation
warnings. The user subsequently explicitly accepted all 703 visual warnings in
the completed run; the visual-warning acceptance gate is now closed. Counts,
metrics and original warning statuses remain unchanged. This does not claim
individual inspection of every image. Publication and merge received subsequent,
separate authorization, as recorded in the validation report.

Earlier on 2026-10-16 the user visually accepted the presented representative/checkpoint
comparisons. Measured warning counts remain unchanged, with human sign-off
recorded separately in the checkpoint report. This does not cover untested jobs
or, by itself, newly rendered continuation warnings. Full-run visual acceptance
was subsequently given separately as documented above. Monoton and continuation received
separate subsequent authorization. The user has since also authorized publishing
and merging Phase 1 through PR #10, contingent on CI and repository requirements;
deployment and artwork publishing remain outside scope.

### Font Coverage and Warning Review

The first 6,631 bulk cases used only Comfortaa because those categories execute
first. The 126-case representative matrix covers all 17 fonts independently.
The full English inventory contains 9,784 Comfortaa jobs, 11 jobs for each of
15 decade/year display fonts, and nine Bebas Neue Playlist jobs. Check the bulk
dashboard's font table for completed versus untested jobs; representative sample
coverage is not a substitute for full inventory coverage.

Start with all completed warnings, sorted worst first:
`config/phase1-validation-20261016/full-batch-monoton-ofl/warnings-ranked.html`.
Sort by the largest difference relative to the unchanged fresh-engine thresholds,
lowest similarity, largest RGB difference or largest isolated caption-edge shift.
Category, font and checkpoint/new filters retain independent evidence links.
Ranking is numerical prioritization, not proof of a visible defect; intentional
differences from historical published artwork do not inflate this ranking.

For grouped newly flagged continuation results, open
`config/phase1-validation-20261016/full-batch-monoton-ofl/review-groups.html`.
It groups repeated captions and rendering parameters across color/artwork
variants, shows the worst numerically ranked sample side by side, and explains the actual warning
trigger. Expand a group's variant list to inspect individual artwork. One sample
does not establish that every variant was visually reviewed. The page labels its
completed-record snapshot; regenerate it after further testing. Grouping never
changes numerical metrics, warning statuses or human approval.

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

All 703 full-run visual warnings now have explicit user acceptance. PR publication
and merge are authorized, subject to successful CI and repository requirements.
The existing Splatter overwrite ambiguity is deferred to Phase 2's generator-logic
work in a separate draft PR. A production cutover still requires explicit approval.
The representative
helper remains separate from the explicit full-batch driver; neither changes the
production workflow. Generated full evidence stays local under ignored `config/`.

The [font audit](FONT_PROVENANCE.md) now links the exact Boecklins Universe font
to its archived original author package; its unchanged notices are bundled.
Monoton's official licensed release has now been explicitly approved and applied,
with pixel-identical outputs for the 11 affected numeric definitions. Merging
the candidate does not deploy it or switch production bulk calls to Python.
