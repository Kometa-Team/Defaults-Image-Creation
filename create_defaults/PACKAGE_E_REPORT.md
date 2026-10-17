# Package E - end-to-end acceptance and production readiness

**Gate E: awaiting final maintainer review. Production cutover: not authorized.**

The maintainer formally approved Gates A-D and authorized Package E from
`166a007c00f14b166a97be8887a4532ea42078b8` on draft PR
[#12](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/12).
Earlier reports, fixtures and four exact Package D sample decisions remain immutable.
No artwork or translation was published; no production PowerShell was replaced,
production permissions granted, PR merged or ready transition performed.

**Acceptance is still in progress.** English full generation, corrected full overlays and selective published-image comparison are not yet complete. No final production-readiness pass is claimed. Every non-English collection remains blocked, and broader overlay visual decisions remain pending.

## Tested source and environment

Final executable checkpoint: `690d1977b207cbbb61371a0fcb8bd02e37db85d2`, branch
`feat/default-posters-python-generator`. The English orchestration started at
`6bb5844b4ebe1ea8b681c826105a008a8f673ede`; environment snapshots record the head
observed when each command completed. Later changes affect overlay ICC conversion,
overlay acceptance duration, tests and reporting; English rendering, planning,
preflight, worker execution and catalog inputs remain unchanged. Source-file hashes
in the evidence distinguish executable identity from a later documentation commit.

Windows 11 uses Python 3.13.15, eight logical CPUs and 32 GiB physical RAM. Linux CI
uses Ubuntu 24.04 and Python 3.13.16. The patched isolated Windows environment uses
Pillow 12.3.0, fonttools 4.60.2, uharfbuzz 0.56.3 and python-bidi 0.6.11. Other direct
pins and native-library versions are recorded in
[dependency evidence](bulk/evidence/package-e/dependencies.json). Exact bundled
fonts are selected by verified paths/hashes, with no OS fallback.

The final English workload uses four explicitly selected persistent spawn workers,
512 MiB per worker, a 4 GiB sampled process-tree ceiling, 8 GiB free-disk floor,
16 GiB final-output ceiling and three-hour limit per cold/warm phase. Each phase
uses at most 15,000 jobs and recycles workers after 200 jobs. Overlay phases use
4,122 finite contracts, a 5,000-job cap, 2 GiB output ceiling, the same disk/memory
floors and an explicit 45-minute phase limit. The latter was revised from 30 minutes
after observed full-inventory throughput; no unbounded benchmark is introduced.
Resource sampling is advisory between checks; worker limits and finite selections
provide separate bounds. All outputs, SQLite state and temporary work stay in
ignored local `config/package-e/` roots, separate from source and production.

## Complete source reconciliation

The authoritative corrected-current-source capture SHA-256 is
`968476aff980f2cbb3e0d5b870360450c723150f34f5751af9aef6dee19643ac`.
All 21 categories reconcile against its 9,958 jobs. Approved D02 retires only the
unintended green Splatter duplicate, leaving **9,957 rendering contracts**, **9,955
public destinations** and **two private Awards intermediates**. Red `#990000`
Splatter and Death in Paradise `(2011)` are retained. There are no unexplained
contract changes or duplicate destinations.

| Category | Active contracts | Contract parity |
| --- | --- | --- |
| Aspect | 9 | Passed |
| AudioLanguage | 188 | Passed |
| Awards | 4847 | Passed |
| Based | 4 | Passed |
| Chart | 1182 | Passed |
| ContentRating | 72 | Passed |
| Country | 608 | Passed |
| Decade | 31 | Passed |
| Franchise | 118 | Passed |
| Genre | 275 | Passed |
| Network | 568 | Passed |
| Playlist | 9 | Passed |
| Resolution | 15 | Passed |
| Seasonal | 23 | Passed |
| Separators | 749 | Passed |
| Streaming | 256 | Passed |
| Studio | 488 | Passed |
| SubtitleLanguage | 188 | Passed |
| Universe | 20 | Passed |
| VideoFormat | 6 | Passed |
| Year | 301 | Passed |

Private paths `defaults-en/_intermediates/award/choice/2016-2.jpg` and
`defaults-en/_intermediates/award/oscars/1930-2.jpg` have null remote destinations.
The parity ledger checks logical/source identity, source logo hashes, bundled fonts,
color, caption/translation parameters, fitting/effects/position, generated parents,
paths and private status. Generated dependencies must bind real verified parent
bytes before final render planning; baseline contract parity does not substitute
invented parent hashes. See [reconciliation evidence](bulk/evidence/package-e/catalog-reconciliation.json).

English preflight reports 3,022 ready, 4,285 with warnings and 2,650 shared; none are
blocked. All 9,957 retain historical color provenance. Existing diagnostics include
4,010 wrapped captions, 1,421 near-edge cases and one clipping warning:
`defaults-en/collectionless.jpg`. These are historical appearance diagnostics,
not authorization to change colors or layouts.

## Full English generation and renderer comparison

In progress: last recorded 2,604 verified of 9,957 required. This is incomplete evidence, not a full pass.

The full comparison requires a complete, validated manifest and matching source,
asset, font and semantic identities for every reference. Its original Phase 1
reference ledger is `63ee0806e1c1af9b796f63478bf379765c30cb6113437701483dc6138989b0ec`.
The 9,792 root outputs are compared against recorded approved Python bytes.
For 165 generated children, the approved original API is called on current,
verified Python parent bytes: old Phase 1 comparisons froze common legacy parent
images, so those old child hashes cannot be used as a silent new tolerance.
Unexpected root differences or fresh child API differences fail the command.

The comparison explicitly permits only approved D08's `(2911)` to `(2011)` output
name/path correction for Death in Paradise, with every other parameter and input
unchanged. D02 remains the red source selection. Historical Phase 1 classifications
(encoding, migration warnings, accepted fonts and missing legacy paths) remain
separate evidence; they are not blanket approval of future differences.

## Read-only published artwork reconciliation

Pinned Default-Images/master inventory: commit
`59e49ede8d41ac5991f971e66e93af596402329a`, tree
`e1664efb92db5872db112cf18253910da77355df`. Inventory reconciliation found **9,954
exact published paths**, **two correctly excluded private paths**, **one case
conflict** and **zero absent paths**. Expected `genre/Action & adventure.jpg` maps
to published `genre/Action & Adventure.jpg` (Git blob
`a20f8bbaab0fdae2b5bd339ee680302b05621960`, 833,624 bytes).
An explicit mapping/case decision is required before a future cutover; no rename
or case-insensitive assumption was applied. Path ledger identity:
`26bbcaf5e4f156baab8925fb31d2948ca4a3512b52ae9cb009a3e47b4502957f`.

Selective published-image comparisons await the verified full English outputs. No byte/pixel result is claimed for an image not yet fetched.

Remote access is GET-only, repository/host allowlisted, with redirect refusal,
timeouts, bounded requests/rate reserve and verified Git blob caches. No full clone,
upstream write, publication token or translation update is used. The complete
inventory verifies names and identities; it does not imply all published image
bytes were downloaded or pixel-compared. Old green Splatter's retirement does not
authorize deleting artwork outside this task.

## Overlay acceptance and the ICC defect

Inventory reconciliation preserves **36 operations**, **18 groups**, **2 sizes**,
**2,061 source images** and **4,122 transformation contracts**. The controlled legacy
harness runs the original grouped mogrify flags on copied inputs, with no production
bootstrap. This overlay path uses one mogrify operation per group/size, unlike the
poster path's independent PowerShell composer per image.

Expanded comparison exposed a real LA/grayscale ICC defect: converting LA directly
to RGBA through ImageCms lost alpha and misread color. This is not an accepted
Pillow/ImageMagick filtering difference. Header inventory identifies 230 susceptible
LA+ICC sources (460 size variants); it does not claim individual human inspection.
The fix converts color separately (L for LA, RGB for RGB/RGBA/palette inputs), then
restores source alpha before existing trimming/resizing. Five focused regressions
cover synthetic LA/RGB/RGBA white sources and actual white Chart AMC+ / Network #0.
Before correction three failed and two passed; after correction all five pass.
The initial alpha-only prototype also failed the white-color assertion and was
corrected without weakening the test.

A fresh corrected 38-output sample changes exactly four images (the two susceptible
sources at both sizes); the other 34, including both Experimental image bytes,
are unchanged. All dimensions match legacy. Alpha MAE is 0.815663..2.825727 after
correction; the original pre-fix large differences remain historical evidence.
No new visual approvals or acceptance thresholds were created. Both original and
corrected per-image metrics are retained in
[ICC evidence](bulk/evidence/package-e/overlay-icc-defect.json).

In progress: last recorded 1,479 verified of 4,122 required. This is incomplete evidence, not a full pass.

The four exact D sample approvals and their image/source/font/layout/validation
identities remain in `bulk/evidence/package-d/maintainer-visual-acceptance-20261017*.json`.
They comprise two Experimental overlays and English/French Based Book samples.
Documented D Pillow-versus-ImageMagick metrics are unchanged. Matching Experimental
bytes do not transfer approval to a changed renderer context, and the ICC fix does
not approve all 4,122 overlays. Remaining overlay transform reviews stay pending.

## Multilingual validation and fitting

The fresh read-only translation snapshot discovers all 14 resources at commit
`a7bddf45d0fb2cc37c794af05d5fb807880c9a80`, tree
`93e6e9d51c26b5c4903adc059f92e4f848f0f2dd`; registry SHA-256
`4f3e741b5d252addfbb4c1a4ed3c7eadf231b5aa3636afa9d2b833816c05ed1b`.
All **139,398 contracts across 294 category/language scopes** were audited using
patched dependencies in 2,045.443 seconds, with 175,849,472 bytes observed parent
RSS, 2,049 unique source hashes and zero poster renders. No language disappeared;
identifiers such as `nb_NO` and `pt-br` remain exact compatibility identities.

| Language | Ready | Warning | Shared | Blocked | Complete collection readiness |
| --- | --- | --- | --- | --- | --- |
| ar | 1 | 0 | 2650 | 7306 | Not ready; pending specified translation/font/layout review |
| bg | 0 | 2852 | 0 | 7105 | Not ready; pending specified translation/font/layout review |
| da | 1308 | 17 | 2650 | 5982 | Not ready; pending specified translation/font/layout review |
| de | 1455 | 33 | 2650 | 5819 | Not ready; pending specified translation/font/layout review |
| en | 3022 | 4285 | 2650 | 0 | English assessment above |
| es | 1422 | 7 | 2650 | 5878 | Not ready; pending specified translation/font/layout review |
| fr | 1432 | 1123 | 2650 | 4752 | Not ready; pending specified translation/font/layout review |
| hu | 0 | 4088 | 0 | 5869 | Not ready; pending specified translation/font/layout review |
| it | 1466 | 14 | 2650 | 5827 | Not ready; pending specified translation/font/layout review |
| nb_NO | 52 | 4 | 2650 | 7251 | Not ready; pending specified translation/font/layout review |
| nl | 25 | 1 | 2650 | 7281 | Not ready; pending specified translation/font/layout review |
| pt-br | 42 | 0 | 2650 | 7265 | Not ready; pending specified translation/font/layout review |
| ru | 0 | 2651 | 0 | 7306 | Not ready; pending specified translation/font/layout review |
| sv | 463 | 15 | 2650 | 6829 | Not ready; pending specified translation/font/layout review |

These are preflight eligibility counts, not human approvals or permission to publish
partial collections. Every non-English full collection has blockers. Arabic's one
ready item is an ASCII caption (`4/20`), not evidence of Arabic production readiness.
Bulgarian/Hungarian/Russian also remain explicitly new-language warnings.

English validation fingerprints match all 9,957 full/category variants and a separate
single Book check, with zero differences. The fresh audit reports 4,131 deduplicated
missing/invalid resource keys linked to 29,429 dependent variants (links can overlap).
Raw audit identity: `529b6d27178b210fb0b7fa58d1994a8996a56d95b8c03d3807213d04c34eaa04`;
deduplicated contributor mapping:
`21bf9b93438be43ffdd30c3d1f26b7ba165a4a74d741dc0696e2757655c70b92`.
Existing detailed D contributor reports are preserved; refreshed JSON/CSV/HTML
reports remain under local `network-translations-patched/cache/`.

Fitting analysis identifies 19,969 exact caption/language/font/native-metric groups,
91,239 members and 8,808 repeated groups. This measures potential native-metric
reuse, not artwork approval groups. Current `review-risk-d1` still requires
individual review for translated captions. A future low-risk group process would
require a separately approved policy, exact member/renderer/font/layout/validation
identities, an explicit inspected subset, preserved individual high-risk exclusions,
immutable decisions and invalidation of changed members. No such policy was enabled.

Six real previews cover all four French Based posters, German Book and Bulgarian
Book. The French Book proposal remains byte-identical to D's reviewed proposal
`dac288b0cd3e0e736e2719ad43023d250686aeb49d017e2989e4fe1488608f8e`.
Matching proposal bytes do not activate it or transfer old acceptance to new runtime
identities. New exact preview image/render/font/layout/policy identities and all
measurements are recorded in [fitting evidence](bulk/evidence/package-e/fitting-proposals.json).
Local review pages are under `config/package-e/language-proposals-final/cache/preview-reports/`.

Noto Sans Arabic remains an isolated, **unapproved** OFL 1.1 candidate. Font Git blob
`f1d01edce4ebaedcbe9a06fc75fec07b304ec3df`, SHA-256
`63111b5b2e074dd48cc67692e0a2726d86ee94c1c37fe8598257b7b4e87e869e`;
license blob `14c589f6384505ede3f8e52627d397513af3662d`, SHA-256
`07fc70bfeb985cc1a87a8587d0a0c80bab11c86c9dc3fd95b6f0cb332f983e96`.
All 57 nonempty pinned Arabic resource strings (39 distinct codepoints) have glyph
coverage. Five fresh joining, mixed Latin/numeric bidi, punctuation, combining-mark
and centered-anchor probes use the existing HarfBuzz/bidi/font-outline path.
Coverage and probe generation do not establish visual acceptance. Font selection,
RTL/mixed-script behavior and layout/anchor review remain pending; no font was
installed in production. See [upstream font provenance](https://github.com/google/fonts/tree/main/ofl/notosansarabic).

## Incremental generation, review integrity and recovery

Package E integration tests compute expected changes before execution for definition,
source logo, approved color, approved alternate font and caption changes; only the
predicted variant rerenders and becomes stale, while unrelated outputs and approvals
remain valid. Separate tests reject changed unapproved font bytes without overwriting
verified output. Newly completed and removed/invalid translations, generated parents,
validation/renderer versions and output-byte changes are covered by B-D integration
and new E regressions. Overlay input changes rerender/stale exactly its two sizes.
A real dependency-version upgrade predicted 73 sample rerenders (35 posters and 38
overlays), with exactly 73 observed, no missing/unexpected jobs and no new approvals.

Individual decisions, rejection/comments, accepted warnings, version-bound group
subsets, individual high-risk requirements, stale decisions, concurrent transactions
and immutable events are exercised in isolated test databases. A concurrent four-item
synthetic group commits once and records only its exact inspected two-item subset;
it never invents individual inspection of the other members. No synthetic approval
is stored as a maintainer artwork decision.

Reliability cases cover worker crash/exception, timeout, RSS threshold, cancellation,
abrupt parent exit, expired lease/restart/resumption, known-failure retry, corrupt
output and SQLite/spec metadata, source mutation, destination mutation before
promotion, duplicate ownership, incomplete parents and token-owned cleanup.
Corruption/unowned destinations fail closed; changing size/mtime back cannot hide
changed bytes. Interrupted work preserves completed outputs and durable receipts.

The first partial full English attempt exposed buffered-success/recycling races:
a worker sent success and exited, but the parent read only one ready pipe and
misclassified another as crashed. The scheduler now drains every ready pipe and
checks buffered final success before exit/timeout classification. A deterministic
four-worker regression failed before correction and passes afterward. Failures
record reason, attempt and PID in the existing immutable event log. Generated-family
selection also now includes every child's required parents while single-child
selection stays narrow; six focused selection/budget cases pass. The comparison
CLI now exits unsuccessfully for unexplained differences.

## Measured performance and warm verification

PowerShell 7.6.7 / ImageMagick 7.1.2-34 reproduce 95 posters in five controlled
sequential batches. The composer source SHA-256 is
`cab86faa4e4ad080c96506f313a03961c3ed3f88e6248a9de325ed0bed25103f`.
The isolated harness removes only bootstrap/self-update/install/banner code,
forces exact copied bundled fonts and redirects private inputs/outputs. Composition,
parameters, fades, JPEG stages, naming and cleanup remain unchanged. Threads are
bounded to one. It does not benchmark the entire original production launcher,
its concurrent orchestration, sleeps or bootstrap.

| Workload | Outputs | Legacy sequential s | Python 1 cold / warm s | Python 2 cold / warm s | Python 4 cold / warm s | Observed legacy / Python 1 |
| --- | --- | --- | --- | --- | --- | --- |
| small | 4 | 18.404 | 8.588 / 1.205 | 8.011 / 1.074 | 7.610 / 1.087 | 2.14x |
| medium | 31 | 131.540 | 55.104 / 5.587 | 32.602 / 5.473 | 21.286 / 5.529 | 2.39x |
| larger | 32 | 178.228 | 44.345 / 3.742 | 28.610 / 2.681 | 27.463 / 2.467 | 4.02x |
| dependencies | 12 | 48.705 | 13.063 / 1.531 | 10.042 / 1.528 | 9.790 / 1.816 | 3.73x |
| mixed | 16 | 66.516 | 18.647 / 1.411 | 16.858 / 1.541 | 14.733 / 1.321 | 3.57x |

Mixed values average two runs per worker count; other workloads have one observation. Medium is all 31 Decades, larger is 32 explicit Chart outputs, dependencies is six Year children plus six parents, small is four Based posters and mixed is 16 explicit contracts.

All 18 poster observations use the actual planner/preflight/persistent renderer;
all hashes match across worker counts/repeats, cold runs have zero retry/failure and
warm runs have zero renders/worker starts. Four workers benefit the medium batch;
small/mixed work shows smaller or inconsistent gains. Recommend **two workers by
default**, with four an explicit measured-capacity choice. Maximum observed single
poster-worker RSS was about 305 MiB; per-observation parent, individual/combined
worker RSS, process starts/recycling, CPU samples, worker read/write bytes and
stage/planning overhead are retained in
[benchmark evidence](bulk/evidence/package-e/poster-benchmarks-and-historical-overlay.json).

Cold means a fresh generator cache, not a cleared OS file cache. Measurements were
sequential controlled subsets; early timings overlapped non-rendering reconciliation.
Worker I/O excludes parent/cache/preflight and includes OS-cache transfers. Legacy
RSS/I/O is sampled. SQLite lock wait was not independently timed; no lock failures
occurred and concurrent correctness is separately tested. No full-catalog speedup
is inferred from subset ratios. Full acceptance runs overlap other validation and
are completion/resource observations, not isolated performance benchmarks.

Corrected overlay scaling measurements are pending completion of the heavier acceptance work. Historical pre-fix 38-output timings are preserved but are not a performance result for corrected output. The fixed 38-output sample ran successfully under concurrent load; its timing is not an isolated benchmark.

Year warm profiling keeps 301 unique outputs, 451 cache checks including repeated
parent-stage verification, 4,726 SHA calls, identical manifest
`c6e06332c32d89e6c68ba81b6cb7aa4b2d7fc7f1d2978eb0b9f11a077feb7e25`, and zero
renders/worker starts. A single profiled pair measured 51.189 -> 35.777 seconds.
Cumulative cached-artifact checks fell 15.348 -> 3.026 seconds; image checks
11.782 -> 0.140; renderer identity 6.821 -> 0.548. SHA time stayed 3.350 -> 3.306.
Nested cumulative times must not be summed. Harness sampling/font-cache variation
limits causal attribution; this is not a universal 30% speedup claim.

Warm reuse still hashes inputs/output bytes, checks exact finalized SQLite receipts
and validates image headers. It avoids full redecoding only for previously verified,
identical bytes; new atomic promotions still fully decode. Loaded library metadata
is immutable within a process; source identities are rechecked and dependency
upgrades require a fresh process. Metadata decoding and repeated package lookup
were reduced; hashing, parent verification, manifest reconstruction, SQLite and path
checks remain. No mtime trust shortcut or weaker durability was introduced.
See [profile evidence](bulk/evidence/package-e/warm-profiling.json).

## Platform tests and CI

| Suite | Windows | Linux executable checkpoint |
| --- | --- | --- |
| Phase 1 | 120 passed | 120 passed |
| Package A | 35 passed | 35 passed |
| B-E | 221 passed / 2 skips / 0 failures | 222 passed / 1 skip |
| People | 129 passed / 1 account skip | 129 passed / 1 platform skip |
| Manifest validators / compile | Passed | Passed |
| E smoke | 35 posters + 38 corrected overlays passed | 35 posters + 38 corrected overlays passed |

Linux totals 506 passed and two platform skips. Windows final bulk counts supersede the earlier run and repeated focused cases are not added to that total.

[Final executable Linux CI](https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/39060962332)
is successful at workflow head `690d1977b207cbbb61371a0fcb8bd02e37db85d2`.
GitHub checked out synthetic PR merge `ebf327e65c6f7ff0d7220b2d3a8a18eabdd300b3`;
this differs from the branch head and is recorded explicitly. All 35 sample JPEG
hashes match Windows; six retained JPEGs were independently decoded. All 38 retained
RGBA overlays have identical decoded pixels across platforms and different PNG byte
hashes. Platform-specific renderer identities and exact artifact hashes remain
separate; pixel parity cannot bypass approval binding. See
[platform evidence](bulk/evidence/package-e/windows-linux.json).

Both platforms exercise spawn, reuse/recycling, cancellation, crash recovery,
atomic promotion, SQLite WAL/locking, separators/case/Unicode, font identities,
path mapping and deterministic manifests. Linux skips Windows-junction tests.
The Windows account cannot create ordinary symlinks in two tests; the native
Windows junction safety test passes. These are explicit platform limits, not passes
invented for skipped cases. Both platforms originally replicated the ICC bug;
cross-platform parity alone did not prove correctness, hence independent legacy
comparison and visible-color regression tests.

The first E CI at `e0cf670` passed 492 tests/two skips but failed whitespace on eight
extra trailing blank lines. They were corrected without weakening the gate.
Intermediate `6bb5844` and `bbfa7f1` CI passed (500 and 501 tests respectively).
Four unchanged palette `Image.getdata()` deprecation warnings remain: plan maintenance
before Pillow 14; no palette/color algorithm was changed for this task.
CI retains contents:read, pinned actions and nonpersistent credentials. It runs
35 posters/38 overlays plus focused D samples, never full production generation.
Selected review artifacts expire after 14 days. Full output collections, caches,
SQLite databases and font binaries are not CI/repository payloads.

## Security, dependencies and repository hygiene

Direct-pin advisory screening found Pillow 12.0.0 advisories and fonttools 4.60.1
GHSA-768j-98cg-p3fv. Pins were updated in an isolated trial to 12.3.0 / 4.60.2.
Forty-four real Based/Decade/Playlist outputs covering all 17 font hashes match
fresh original approved API calls byte-for-byte on identical current parents;
ledger `7e392814005b6d4c9ab26aa453787bbeb343b3f6350e494f8db27d0515ac948f`.
A new advisory query found no matching entries for the patched versions. The
listed trigger APIs are not called by this bounded rendering path; no active exploit
is claimed. This is a 12-direct-pin screen, not a complete transitive/native SBOM.
Primary advisories: [Pillow](https://github.com/advisories/GHSA-6r8x-57c9-28j4),
[fonttools](https://github.com/advisories/GHSA-768j-98cg-p3fv).

The runtime uses safe bounded YAML loading with duplicate-key/depth/anchor checks,
registered generators without eval, confined relative paths and Unicode/case
collision checks, reparse/link rejection, bounded image/canvas/resize dimensions,
verified font whitelist and remote blob/request limits. Read-only remote trust uses
Git identities plus exact SHA-256. SQLite uses parameter binding, owned transactions,
WAL, immutable event triggers and exact output claims. Atomic promotion refuses
unowned/corrupt destinations; cleanup requires matching token-owned workspace
identity. No archives, auth service, portal, production credential flow or publication
permission was added. License/font provenance remains explicit and unchanged.

Final complete-PR static inventory:

```json
{
  "pr_base": "57ef136833a3f54da2bf1e4ddef98addfa36d583",
  "files": 203,
  "groups": {
    "implementation tests docs or workflow": 91,
    "compressed immutable manifest fixtures": 1,
    "generated catalog and source-normalized migration audits": 88,
    "compact package audit evidence": 19,
    "Package A source and inventory evidence": 4
  },
  "bytes_by_group": {
    "implementation tests docs or workflow": 942341,
    "compressed immutable manifest fixtures": 1458149,
    "generated catalog and source-normalized migration audits": 13803206,
    "compact package audit evidence": 411056,
    "Package A source and inventory evidence": 2133232
  },
  "possible_credentials": [],
  "unexpected_generated_or_binary_payloads": [],
  "protected_changes_since_package_d": [],
  "workflow_permissions": "contents:read; credentials not persisted; local-only bounded smoke artifacts",
  "scope": "Static audit of complete PR scope and Package E additions; no secrets printed. Direct-pin advisory screening is separate; no comprehensive transitive/native SBOM claim."
}
```

Generated YAML/source-normalized inventories and immutable historical fixtures account for most of the PR size. New E evidence contains compact summaries and identities, not image/font/SQLite collections. The credential scan checks common token/private-key patterns; it is not a claim that all possible secret formats can be detected.

Retained aborted runs are not labelled successful. Original-stack full runs stopped
with 1,378 English outputs and 2,760 overlays when patched dependencies were selected.
The later pre-ICC-fix overlay run was deliberately stopped after the defect was
identified; its output/receipt/metric evidence remains. Only validated token-owned
scratch from stopped runs was removed. Earlier reports/fixtures/audits were not
rewritten to remove failures or reduce the PR size.

## Acceptance matrix and remaining decisions

| Acceptance criterion | Classification | Evidence / limitation |
| --- | --- | --- |
| Complete 21-category semantics / 9957 effective contracts | Passed | Zero unexplained contract deviations; two private intermediates excluded. |
| Full English end-to-end cold/warm / receipts | Not tested | Controlled full run still in progress. |
| Full approved-API renderer parity | Not tested | Full exact comparison still pending. |
| Incremental invalidation / stale approval sets | Passed | Expected-vs-actual scoped tests and real renderer upgrade. |
| Controlled legacy performance / 1,2,4 scaling | Passed with documented limitation | Sequential isolated composer harness; no full production launcher speedup claim. |
| Warm analysis and safe optimization | Passed with documented limitation | Single paired profile; hashing/durability preserved. |
| Windows / Linux compatibility | Passed with documented limitation | Account/platform skips; 35 JPEG/38 PNG sample parity, not full Linux render. |
| Recovery / interruption / corruption / ownership | Passed | Isolated realistic failure scenarios, immutable durable state. |
| Published path inventory | Passed with documented limitation | One case conflict needs a mapping decision. |
| Selective published-image comparison | Not tested | Pending full outputs. |
| Corrected overlay full transform/format/cache verification | Not tested | Full corrected run pending. |
| Broader overlay visual approval | Blocked | D sample decisions retained; unreviewed transformations pending. |
| Fresh all-language discovery/coverage/strict-partial checks | Passed | 139398 contracts, all 14 resources; no English scope differences. |
| Complete non-English production collections | Blocked | Every non-English language has translation/font/fitting blockers. |
| Arabic font / RTL / mixed-script acceptance | Blocked | OFL candidate and probes preserved; no visual/font approval. |
| Fitting proposals / scalable group analysis | Passed with documented limitation | Six actual previews; no policy change or new approvals. |
| Review/invalidation integrity | Passed | Exact artifacts/version-bound subsets; synthetic decisions isolated. |
| Historical color preservation / new assignment policy | Passed | 9957 historical colors; uniqueness/concurrency/provenance regression tests. |
| Dependency/license and complete-PR static audit | Passed with documented limitation | Direct-pin advisory screen and source audit; no full transitive/native SBOM. |
| CI / regressions / documentation | Passed | Detailed report, archived evidence and safe CI. |
| Production cutover / publication / rollback execution | Not tested | Not authorized; proposed checklist only. |

Priority maintainer decisions before any future production operation:

1. Review Gate E's exact evidence and independent readiness recommendations.
2. Resolve the Action & adventure/Action & Adventure destination case mapping.
3. Review broader overlay behavior and the corrected ICC sample identities; existing
   D acceptance covers its exact reviewed samples only.
4. Review/activate each translated fitting proposal in its current version context;
   decide Arabic font/RTL/anchor behavior and preserve high-risk individual review.
5. Approve any future low-risk group policy explicitly; no current group inference
   authorizes translated collections or missing content.
6. Separately authorize a cutover plan, publishing authority and rollback ownership.

## Proposed future cutover and rollback checklist - not executed

- Freeze the approved branch commit, dependency/native versions, bundled font hashes,
  source/translation/inventory snapshots, validator and exact review-policy versions.
- Resolve destination case/Unicode mappings explicitly; exclude both private Awards
  intermediates. Verify that the chosen scope is complete, including generated parents.
- Run a fresh isolated strict preflight and bounded full generation, then verify every
  output claim/receipt/hash, destination uniqueness and all required current approvals.
- Record/backup the existing production workflow, PowerShell source and published Git
  head. Preserve prior receipts/audits and test rollback access without writing artwork.
- Obtain separate maintainer authorization for publishing credentials, a finite canary
  scope and actual cutover. Keep unrelated language/style collections out of that scope.
- Under that separate authorization, publish only verified approved artifacts and check
  exact remote identities/counts before expanding; stop on unexplained differences.
- On failure, stop new work, retain evidence, and restore the pinned prior workflow or
  published version under separately authorized rollback. Never delete or overwrite
  unowned work, and do not erase immutable review/history records.

This checklist grants no execution authority. The PR remains draft for final
maintainer review; no future phase begins automatically.
