# Package C: Category Migration and Real Poster Rendering

## Gate Status

Package C is implemented on `feat/default-posters-python-generator` for draft
PR #12. Gate C remains **awaiting maintainer approval**. Windows and Linux
regression checks passed as recorded below; no production-readiness
or multilingual-acceptance claim is made.

The production PowerShell generator, validated Pillow composer/text engine,
historical Phase 1 fixtures, published Default-Images and People Posters source
are unchanged. No merge, deployment, publication or Package D/E work is authorized
by this report.

## Implementation

- All 21 categories have checked-in YAML definitions and one named profile layer.
  IDs are explicit logical identities, not source-line numbers. Static rows stay
  in data. Dynamic Awards years, Best Of years, Separator variations and Content
  Rating codes use named, bounded, strictly validated Python generators.
- `bulk/catalog.py` loads active data. `bulk/migration.py` is a development-only
  exporter/reconciler; the production generation path never reads the captured
  manifest or executes the legacy source. Source row hashes, producer lines and
  captured job identities remain traceable in `bulk/catalog/audit/`.
- `bulk/generation.py` plans roots, renders/verifies actual parent bytes, then
  plans children using those hashes. One bounded spawn pool persists across
  stages and calls the existing composer API directly. No per-poster CLI,
  PowerShell, ImageMagick or network operation is used for production rendering.
- Full graph path/case/NFC collision checks precede rendering, including outputs
  in different dependency stages. Jobs, pending requests, metadata, artifacts,
  RSS budgets, retries and recycling are bounded. Successful schema checks for
  small immutable JSON records have a bounded cache, not an unbounded image cache.
- SQLite migration 6 adds verified replacement preconditions. A changed job may
  replace only its own previously verified bytes under the output reservation
  lock. Different owners, unfinished replacements and corrupt/unowned files fail
  closed. Atomic promotion checks the previous SHA. Restoring an older definition
  creates a new generation rather than mutating a terminal historical receipt.
- Receipts and hashes support restart, verified cache reuse and incremental
  invalidation. Successful orchestration cleans its token-owned scratch workspace
  only; state, receipts and outputs remain. Interrupted workspaces remain retained
  for explicit owned cleanup/diagnosis. Network services stay outside workers.
- `generate` is an explicit local-only CLI command. No existing production
  workflow calls it. An incomplete generation has a nonzero exit status.

## Exact Reconciliation

Authoritative corrected-current-source capture:
`968476aff980f2cbb3e0d5b870360450c723150f34f5751af9aef6dee19643ac`.
Historical fixtures and their original 9,958-job counts remain unchanged.

**New effective English contracts: 9,957.** D02 removes only the unintended green
Splatter row 4883. The authoritative row 4884 retains `genre/Splatter.jpg`,
`#990000`, the original logo/layout/translation, and disabled white-wash.

The catalog contains **4,372 authoring definitions**, including named range
families and explicit color/white style definitions. This is not a one-to-one
count of the original 3,352 CSV rows: 3,351 original literal source lines remain
active and one is explicitly retired. All 9,958 original effective job identities
are accounted for as 9,957 active plus the one D02 retirement. Source-line/row
coverage and effective-job counts are distinct; neither historical count is
rewritten to conceal the migration's representation changes.

There are **9,955 published-path contracts and two private intermediates**. The
legacy Awards calls at producer lines 1912 and 2226 were subsequently overwritten
by equivalent year jobs. They remain explicit `_intermediates/award/...` local
contracts with null remote paths, rather than silently disappearing from effective
counts or colliding with active published destinations. Equivalent payloads are
eligible for verified deduplication. These intermediates are not new published
artwork. Existing special `2016-2` / `1930-2` final outputs are retained.

Death in Paradise keeps `(2011)`. Windows case-insensitive logo/font aliases bind
the actual bundled paths for Linux portability. HEX letter case is normalized,
not recolored. Legacy `+-500` offsets retain their signed effective placement.
Separator output directories are separated from composer basenames without
changing final paths or pixels. `A.C.G.T.` remains a valid stem whose output is
`A.C.G.T..jpg`. Reserved names, traversal and invalid path components still fail.

Frozen random fallback colors for Separator template variants remain explicit,
deterministic migration data with template provenance. Historical assignments are
not automatically declared approved exceptions. No existing source color is
automatically recolored. Temporary incremental test edits affect private outputs
only and are restored; active YAML colors remain the approved originals.

### Category Matrix

Every category has a resolved-contract reconciliation, complete canonical plan,
real-art sample comparison, changed-definition check and warm restart evidence.
Generated-input canonical plans use real verified benchmark parents, not invented
hashes. Exact plan/sample identities are in
`bulk/catalog/audit/package-c-evidence.json` and the per-category JSON reports.

| Category | Authoring Definitions | Legacy Jobs | Active Jobs | Automated Gate | Maintainer Gate |
| --- | ---: | ---: | ---: | --- | --- |
| Aspect | 9 | 9 | 9 | Passed | Awaiting review |
| AudioLanguage | 188 | 188 | 188 | Passed | Awaiting review |
| Awards | 161 | 4,847 | 4,847 | Passed | Awaiting review |
| Based | 4 | 4 | 4 | Passed | Awaiting review |
| Chart | 1,182 | 1,182 | 1,182 | Passed | Awaiting review |
| ContentRating | 50 | 72 | 72 | Passed | Awaiting review |
| Country | 608 | 608 | 608 | Passed | Awaiting review |
| Decade | 17 | 31 | 31 | Passed | Awaiting review |
| Franchise | 118 | 118 | 118 | Passed | Awaiting review |
| Genre | 275 | 276 | 275 | Passed, D02 documented | Awaiting review |
| Network | 568 | 568 | 568 | Passed | Awaiting review |
| Playlist | 9 | 9 | 9 | Passed | Awaiting review |
| Resolution | 15 | 15 | 15 | Passed | Awaiting review |
| Seasonal | 23 | 23 | 23 | Passed | Awaiting review |
| Separators | 35 | 749 | 749 | Passed | Awaiting review |
| Streaming | 256 | 256 | 256 | Passed | Awaiting review |
| Studio | 488 | 488 | 488 | Passed | Awaiting review |
| SubtitleLanguage | 188 | 188 | 188 | Passed | Awaiting review |
| Universe | 20 | 20 | 20 | Passed | Awaiting review |
| VideoFormat | 6 | 6 | 6 | Passed | Awaiting review |
| Year | 152 | 301 | 301 | Passed | Awaiting review |

## Visual Evidence

Local comparison index: `config/package-c/validation-02/index.html`.
Year/Decade's expanded font/dependency comparisons are under `validation-03/` and
linked from that index. Each comparison shows the actual persistent-worker JPEG
beside a fresh direct approved-Pillow-API reference using the corrected captured
parameters. Source/generated input bytes are pinned. All **50** compared outputs
are byte-identical, including approved Jakarta 409-point and Monoton examples.
All 50 final worker/reference file pairs were rechecked against recorded hashes
after the incremental restore tests.

This proves the new orchestration preserves the approved Python rendering path;
it is **not** a new full ImageMagick comparison or published-artwork reconciliation.
Pre-existing accepted Phase 1 renderer/published differences are not reclassified
or hidden. No visual thresholds were changed and human approval is not inferred.
Images, HTML, full plans, SQLite and workspace evidence remain ignored local
artifacts, not committed poster images or published Default-Images.

## Real Workload Measurements

Observed Windows / Python 3.13.15 measurements, two configured persistent workers,
actual 2000x3000 RGB JPEG outputs. Other local verification activity was running;
these are representative observations, not an isolated before/after benchmark.
Complete metric/receipt records are in `config/package-c/benchmarks-01/` and their
compact summaries in the tracked Package C evidence.

| Workload | Actual Cold Renders | Cold Seconds | Renders/Second | Cold Worker Starts | Warm Seconds | Warm Renders/Starts |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Small: Based | 4 | 5.075 | 0.788 | 2 | 1.032 | 0 / 0 |
| Medium: Decade | 31 | 29.596 | 1.047 | 2 | 7.473 | 0 / 0 |
| Larger: Year | 301 | 287.546 | 1.047 | 2 | 51.793 | 0 / 0 |

All three completed without failures or extra render attempts. The 301-job run
used the same two worker PIDs across parent and child stages; no worker recycling
was necessary. Peak sampled worker RSS was 199,651,328 bytes individually and
351,105,024 bytes combined; parent RSS peaked at 75,141,120 cold and 90,169,344
warm. Worker I/O counters recorded 1,283,411,658 read bytes and 335,854,098 write
bytes in the Year cold run. These are process I/O counters, not complete physical
disk or orchestrator I/O profiling. Limits remain configured sampled budgets,
not OS-enforced allocation ceilings.

Warm Year verification records 451 cache checks for 301 distinct outputs because
150 parents are verified again in the dependent stage. Cold Year similarly has
150 parent cache reuses after the 151-root stage. These are not extra renders.
No full 9,957-poster performance run or legacy speedup claim is made; that gate
belongs to Package E.

## Regression Validation

Windows validation completed:

- Phase 1: **120 passed**, 94.921 seconds; original constraints retained.
- Package A: **35 passed**, 8.929 seconds.
- People GitHub/sandbox/workspace/orchestrator: **129 passed, 1 skipped**,
  179.86 seconds. This account cannot create symlinks; Windows junction coverage
  remains exercised separately. People source/auth/publication behavior is unchanged.
- Historical baseline wrapper: passed against its reconstructed exact source.
- Corrected current-source baseline: **9,958 jobs / 3,352 literal rows validated**.
- Package B/C final suite: **117 passed, 1 skipped**, 294.13 seconds. The skip
  is the same Windows-account symlink permission limitation. One initial new test fixture
  accidentally added an uppercase duplicate translation key; the case-collision
  guard correctly rejected it. The fixture now edits the existing key instead.
- Compile and staged whitespace checks: **passed**. Staged scope contains 107
  source/data/documentation files, with no generated images, font binaries,
  databases, caches, workspaces, secrets or production-script changes.
- Linux PR CI: **passed** for code commit `6c6cabb949366df8898795c8c167f9724b84b2d7`.
  [Run 38981456384](https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/38981456384)
  used Ubuntu 24.04 / Python 3.13.16; job duration 3m13s. The subsequent report
  update is documentation only. The existing read-only workflow discovers the
  new offline category and real-composer tests automatically.

Local total: **401 passed, 2 platform-permission skips** across the four suites.
Third-party pytest plugin autoload was disabled for the local pytest commands;
the repository's actual test selection was unchanged.

Linux results: Phase 1 **120 passed** (38.612s), Package A **35 passed** (4.338s),
Package B/C **117 passed, 1 skipped** (111.36s), People regressions **129 passed,
1 skipped** (5.14s). Both baseline validators, compile and whitespace checks passed.
The Linux skips are explicitly Windows-only junction tests, not failed symlink
coverage. Linux total: **401 passed, 2 expected platform skips**. No executable
change was necessary to resolve Linux CI failures.

Tests cover all categories, dynamic determinism and limits, exact approved
corrections/fonts, actual parent/child rendering, no invented dependency hashes,
incremental parent/dependent regeneration, caption-language and logo selectivity,
atomic owned replacement/rollback, interruption/new-pool resume, collisions,
unsafe paths/Unicode, cleanup and existing worker fault/retry/recycling behavior.

## Limits and Review Boundary

- Not every 9,957 output was rendered. All contracts are reconciled; representative
  real samples and the complete Based/Decade/Year workloads are explicitly recorded.
- English catalog applicability only. Full multilingual layout, Arabic font/RTL
  approval, preview/reviewer workflows and actual overlays remain Package D work.
- Captured fitting deliberately binds exact approved text/font/size. New fitted
  captions or extending dynamic ranges need new fitting evidence or an explicit
  fixed layout. No silent automatic refit changes approved appearance.
- Full-production performance, complete multilingual/published reconciliation
  and a production cutover recommendation remain Package E work.
- Successful automation does not approve artwork on the maintainer's behalf.
  Stop at Gate C review. Do not merge PR #12, publish, deploy or begin D/E.
