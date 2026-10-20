# Phase 2 Package B Report

Date: 2026-10-16. Branch: `feat/default-posters-python-generator`.
Base: `57ef136833a3f54da2bf1e4ddef98addfa36d583` (`main`).
Gate A and decisions D01-D08 are approved. Package B only is authorized.
The maintainer subsequently authorized committing/pushing the scoped Packages A/B
files and opening a draft PR against `main` solely for Linux CI and Gate B review.
No merge, ready-for-review transition, deployment, image publication, full poster
batch or Package C category migration is authorized or performed.

## Implemented

| Scope | Delivered evidence |
| --- | --- |
| B1 definitions/configuration | Strict versioned JSON Schemas, duplicate-safe/no-alias YAML, immutable canonical definitions, one profile layer, explicit overrides, stable IDs, safe paths and configuration precedence. Four real source-derived examples, not complete category migration. |
| B2 manifest/planner | Canonical raw/effective parameters, deterministic identities/fingerprints/order, generator registration and source identity, typed dependencies/poster/overlay contracts, exact local/remote mapping and case/NFC collision rejection. Unknown layouts/parent hashes fail closed. |
| B3 GitHub | Shared neutral error/blob/tree primitives; GET-only Defaults facade, immutable commit/tree snapshots, complete/truncated traversal, incremental transactional SQLite cache, exact lookup, freshness/offline/auth states and selective SHA/size/image-verified fetches. No clone/write methods. |
| B4 colors | All 3,318 literal and seven generated/direct historical assignments retained without invented exceptions. D01 exact-category rules, explicit relationships/authorized exceptions, configurable warning-only similarity, deterministic alpha-aware palette proposals, transactional reservations/approval/expiry and audit history. |
| B5 source discovery | Read-only bounded decoding/hashing, historical/overlay associations, candidate/missing/format/identity/case/path diagnostics; no deletion or approved-definition creation. |
| B6 persistence | Five SQLite migrations, WAL/busy timeout, caller-owned transactions, immutable events, version/lease conflicts, job/output ownership, atomic hash-bound receipts, scoped workspaces and journaled retention cleanup. |
| B7 translations | Eleven exact identifiers, offline snapshots, legacy-compatible key lookup/value casing/replacement tokens, bounded placeholder resolution, explicit applicability/shared captions and reviewed fallback provenance. Missing keys block; no silent English or sentinel text. |
| B8 interfaces | Eight non-rendering CLI commands plus callable Python services; direct composer adapter and persistent worker API. No Flask, second renderer, production render CLI or approval UI. |

`workers.py` runs a long-lived orchestrator and persistent `spawn` processes, not
one CLI process per poster. Each worker receives at most one in-flight request;
input queues are capacity one, and isolated bounded result pipes prevent a hard
exit corrupting another worker's result channel. Per-process resources initialize
once; requests/options are isolated. Network access and SQLite writes stay outside
workers. Defaults retain composer fonts, layout, encoding and canvas unchanged.

Configurable bounds cover workers, metadata/job count, artifact bytes, RSS sampling,
timeouts, retries and recycling. Dependency-ready scheduling, deterministic verified
cache/dedup classifications, atomic exclusive promotion, durable receipts, explicit
failed retries and cancellation/worker recovery are implemented. Registration is
paged in short transactions with WAL kept open, not one checkpoint per operation.

## Compatibility

- D02 policy rejects retired green Splatter and enforces red `#990000`, white-wash
  false and `genre/Splatter.jpg`. Both legacy rows remain in untouched audit/source
  evidence. No Genre category migration has happened. The eventual C-only retirement
  projects 276 -> 275 Genre jobs and 9,958 -> 9,957 English jobs; B's legacy capture
  remains 9,958 rather than rewriting history.
- D08 keeps the historical manifest byte-for-byte unchanged. Its validation wrapper
  reconstructs only the hash-proven output-name correction in a temporary source
  tree and then runs the original complete validator. Unknown edits/fonts/assets
  still fail. A separate current-source capture validates today's 9,958 jobs.
- The single old/current effective difference is `Death in Paradise (2911)` ->
  `(2011)` in `out_name`; the logo already used 2011 and is unchanged.
- Raw zero/default numeric values and compound offsets remain traceable alongside
  effective parameters. Jakarta remains fixed 409; Playlist Bebas Neue remains
  capped at 154. Dominant-color flags remain the validated legacy no-op.

## Validation

Executed locally with Windows/Python 3.13.15; no dependencies were installed.

| Command / check | Result |
| --- | --- |
| `py -3.13 -m unittest discover -s create_defaults/phase2/tests -v` | 35 passed, 8.220 s. |
| `py -3.13 -m unittest discover -s create_defaults/tests -v` | 120 passed, 70.647 s. |
| `py -3.13 -m pytest create_people_posters/tests/test_people_github.py create_people_posters/tests/test_people_sandbox.py create_people_posters/tests/test_people_workspaces.py create_people_posters/tests/test_people_api_orchestrator.py -q -rs -p no:cacheprovider` | 129 passed, one skipped, 194.05 s. |
| `py -3.13 -m pytest create_defaults/bulk/tests -q -rs -p no:cacheprovider` | 75 passed, one skipped, 212.41 s. |
| CIEDE2000 | All 34 published reference pairs in both directions, tolerance 0.00005. Independent equation implementation; reference data attribution retained. |
| Historical/current CLI baseline checks | Both passed; current capture verifies 9,958 jobs / 3,352 literal definitions. |
| Four-example CLI plan | Passed with four jobs, complete parameter/input hashes and no rendered output. Manifest SHA-256: `594e8d1d8a43e1f2eff9bf14cb66d385a592fe9178008c3977ab01dabb0bc838`. |
| Real Genre asset discovery | 272 files, zero unassigned candidates, zero definitions created or source files deleted. All 467 diagnostics are informational: 459 shared-source associations across the baseline and eight identical-byte source groups; no errors/warnings. |
| Compile / Git whitespace | Compile and tracked/untracked whitespace checks passed; repeated at final handoff. |
| Protected paths | No diff in production PowerShell, composer, text engine, fonts or historical fixtures. |

Symlink skips are account limitations: one People workspace test and one B source
path test. Portable path checks still run; the native Windows junction/reparse-point
rejection test passes. The optional original PowerShell helper reference probe ran
successfully locally; it is a development compatibility check, not a production
rendering dependency, and skips honestly when PowerShell is absent.

Development checks caught and fixed legacy Unicode/replacement edge cases, a
timer-based cancellation test race and Windows `BrokenPipeError` during worker
death polling. One intermediate rerun mixed old-parent/new-child source while
the worker protocol was edited; that run was discarded and restarted. Final
results must come from a single unchanged implementation, not combined failures.
Historical Package A's 119-pass/one-error checkpoint remains documented; the
separate-baseline fix now passes the complete 120-test Phase 1 suite.

### Worker Proof

The completed synthetic proof classifies 301 outputs: 300 executions and one
verified deduplication reuse, using exactly two worker starts with at most two
in flight. A second run hash-verifies all 301 as cache hits, with zero executions.
Requests intentionally mutate private worker copies to check state isolation.
Other focused tests cover hard exit, Python error, timeout, bounded retry, explicit
failed retry, cancellation/fresh-pool resume, dependencies, recycling, memory and
metadata bounds, corruption/collision rejection and interrupted atomic promotion.
One-versus-three-worker runs produce identical hashes.

Observed final passing isolated-channel proof: 152.086 s, 1.979 classified jobs/s,
77,721,600 bytes peak parent RSS, 24,649,728 bytes peak individual worker RSS,
49,004,544 bytes peak summed worker RSS, 5,291,529 worker read bytes and 68,048 worker
write bytes. These are small byte-artifact tests, with durable filesystem/SQLite
overhead, not poster benchmarks or a comparison against legacy performance.
Worker I/O counters are not a complete physical-disk profile; failed processes
that exit before reporting may have incomplete I/O measurements. These timings
include local filesystem contention and are not a performance acceptance result.

### Read-Only Live Smoke

This was the initial Package B metadata-only smoke. The authorized final B3
integration below supersedes its limited end-to-end coverage, without rewriting
the original smoke's scope or claiming it downloaded images.

Three public GitHub metadata GETs verified destination `Kometa-Team/Default-Images`
branch `master`, head `59e49ede8d41ac5991f971e66e93af596402329a`, tree
`e1664efb92db5872db112cf18253910da77355df` and a complete 49-entry root response.
No live full inventory/image download was performed. Mocked integration covers
full-tree fallback, incremental snapshots, corrupt/incomplete caches, selected
verified blobs, rate limits and failures. No write-capable Defaults API is exposed.

## Outstanding Gates

- Native Linux worker/atomic-file tests now pass in GitHub Actions, including
  relevant People compatibility regressions; exact evidence is recorded below.
  Local WSL/Docker remains unavailable, but is no longer a Linux-validation blocker.
  No local distribution/container image was installed or service started.
- RSS enforcement is sampled, not an OS allocation limit. Metadata is bounded but
  held in a capped catalog. Production parent/worker sizing and soak testing need
  actual category workloads in C/E; no production performance claim is made.
- New generated-parent hashes must be staged/verified before planning children;
  B does not invent future hashes. C integrates staged category expansion. D adds
  actual overlays, independent multilingual preflight/previews and approval flows.
- Only English translations are available locally. None of the 17 approved faces
  establishes Arabic coverage; Arabic rendering/RTL is not marked validated.
- B's palette contrast is a swatch-level proposal diagnostic, not complete text,
  gradient or clipping validation. Thresholds remain explicit/versioned.
- Approved new color choices persist in SQLite; reviewed YAML writing/reconciliation
  is a future workflow contract, not a hidden B writer. No historical color changed.
- Corrupt retained outputs and changed destination ownership require explicit
  operator action. No force/overwrite/publication capability is implemented.

Definitions, configuration, planning, inventory, color/state/translation services
and worker infrastructure are available for Package C integration review. Linux
CI closes the cross-platform infrastructure-test gap; the final B3 check below
now exercises real inventory/cache/download integration. Do not call the full
production system validated or begin C without authorization.

## Final Gate Verification

Status: **Linux CI and limited live B3 integration passed; ready for final maintainer Gate B approval, not automatically approved**.
The updated workflow runs only on pull requests targeting `main`, on
`ubuntu-latest` with Python 3.13 and read-only repository permissions. It includes
Phase 1 tests, both intended baseline validators, Package A/B tests and the four
relevant People regression files. No live publication or full poster generation
is part of the workflow.

### People Compatibility Review

`people_github.py` changes only the location of `GitHubError`, re-exporting the
same RuntimeError interface and `status` field. Token precedence (`GITHUB_TOKEN`,
`GH_TOKEN`, then `gh auth token`), headers, sandbox routing/allowlists, seven
repository mappings, branch selection, write pacing, retries, status handling and
sanitized authentication/publication errors are unchanged.

`people_remote_inventory.py` delegates Git blob framing and complete-tree traversal
to neutral primitives. Recursive responses still discard truncated results and
fall back to nonrecursive subtree traversal. Recoverable transport/5xx failures
retain that fallback; authentication/permission/not-found failures propagate, and
truncated nonrecursive trees fail closed before replacing the previous snapshot.
Prefixes remain applied once. Incremental subtree reuse, transactional cache
replacement, case/Unicode lookup, selected blob verification and the People
publication state/commit/ref/README-dispatch flow remain unchanged. The shared
nonrecursive-truncation diagnostic is shorter, omitting the old trailing phrase
`refusing publication`; exception type/status and fail-closed behavior are preserved.
Regression publication tests use fake GitHub services, not actual uploads.
An AST comparison against the base commit confirmed all eight People auth/
transport functions and 15 unaffected inventory/helper methods unchanged; the
moved `GitHubError` class is AST-identical. A fresh Windows regression run passed
129 tests with one account symlink-permission skip in 113.39 seconds.

### Linux Run History

Draft PR: [#12](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/12),
target `main`; it must remain draft and unmerged.

The [initial Linux run](https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/38974361064)
on `64f497527c0c034aeecb420c1522c267449d20a7` passed Phase 1 (120 tests),
Package A (35), Package B (75 passed / one Windows-only junction skip), and both
baseline validators. People regressions had 126 passes, one Windows-only junction
skip and three failures, all caused by missing `python-dotenv` on the clean runner.
No auth/publication logic failure was observed. CI requirements now pin the
existing People dependencies `python-dotenv==1.2.4` and `alive-progress==3.3.0`,
matching their existing rembg requirements and tested Windows environment. The
second import was identified by inspecting the sync helper's complete imports.
No test was removed or skipped to hide those failures.
The [intermediate run](https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/38974657351)
on `d176055bc35e9eff710a0cb3cedfc9bf1f8ce49e` confirmed the remaining two
`alive_progress` import failures (127 People passes / one Windows-only skip).
Both dependency fixes are included in the successful run below; no production
People code or validated rendering behavior was changed to obtain green CI.

### Successful Linux Evidence

[Passing run 38974842240](https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/38974842240),
job `117221671737`, tested commit `9fb6db372a5637b7902611d21e69395fba90cfa1`.
Completed 2026-10-16 at 18:18 EDT (America/Toronto). Actual runner:
`ubuntu-24.04`, runner image `20261012.334`, CPython `3.13.16`.

| Linux check | Result |
| --- | --- |
| Install pinned dependencies / compile | Passed. |
| Phase 1 / approved font and fixture tests | 120 passed, 23.271 s. |
| Historical Phase 1 validator | Passed against exact reconstructed historical source identity; historical fixture unchanged. |
| Corrected current-source validator | Passed: 9,958 effective jobs / 3,352 literal definitions. |
| Package A | 35 passed, 2.006 s. |
| Package B, including persistent spawn/recovery/atomic-output proof | 75 passed / one skipped, 18.10 s. |
| Relevant People GitHub/sandbox/workspace/orchestrator regressions | 129 passed / one skipped, 4.33 s. |
| Full-PR whitespace check / job cleanup | Passed. |

Total: **359 passed, two platform-specific skips, zero failures**. Both Linux
skips are native Windows junction tests; ordinary Linux symlink protections run
and pass. Windows junction protection was tested successfully locally. The
optional original-helper PowerShell reference probe also passed on this runner;
PowerShell is not a production-worker dependency. Tests do not publish artwork.

The successful CI validates the implementation and dependency fixes. The follow-up
report-only commit is checked by the same PR workflow; current head results are
available through [PR #12 checks](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/12/checks).
No failed run is being relabelled as successful, and synthetic timing is not
production rendering performance. `ubuntu-latest` announced a future runner-image
migration; this evidence specifically covers Ubuntu 24.04, not untested releases.

### Worker and Scope Review

The production-default adapter is `workers.compose`: it imports `PosterOptions`
and `create_poster` from the validated `create_defaults.create_poster` module and
calls that API directly into a private staged path. `_start` creates a persistent
`spawn` process per worker slot, and `_worker_main` loops over requests; there is
no per-poster PowerShell, ImageMagick or Python CLI invocation. The 300-execution
test asserts two starts, bounded in-flight work and verified cache/dedup reuse.
The injected composer-API test checks the actual adapter call independently.
These tests establish infrastructure behavior only. Full Python category
generation, actual poster worker workloads and fresh visual parity remain C;
overlays/multilingual previews remain D, and measured production comparison is E.

### Final B3 Live Read-Only Integration

Executed on 2026-10-16, beginning 18:29:20 EDT (America/Toronto), through the
existing production `ReadOnlyGitHub`, `RemoteInventory` and `Store` APIs. No
production or test implementation was changed. A local ignored harness recorded
requests and timings and enforced GET-only access to the single allowlisted
repository. Existing `gh` authentication was held only in memory, never recorded
in evidence. The harness imposed a 300-request ceiling and a 100-request remaining
quota reserve; it did not attempt to exhaust limits or provoke failures.

Pinned `Kometa-Team/Default-Images` / `master`:

- Commit: `59e49ede8d41ac5991f971e66e93af596402329a`.
- Root tree: `e1664efb92db5872db112cf18253910da77355df`.
- Inventory: **16,554 entries: 16,354 blobs and 200 trees**. These are repository
  metadata counts, not a claim that every blob is a poster or was downloaded.
- Canonical index SHA-256, ordered by exact path and binding path/blob-or-tree
  SHA/size/mode/type:
  `148c7a233efc2390a828251fbfb5fa1f4f7649c03d923b2e3f6cc63465823d5a`.

All database/cache files are under a unique isolated ignored directory:
`config/b3-live-verification/20261016T222920Z-620f94ce/`.
The complete API request ledger and phase results are in `evidence.json` there;
`independent-root-check.json` and `collision-control/evidence.json` retain the
separate controls. Local SQLite files, downloaded bytes, caches and the temporary
harness are not committed. No existing inventory/cache was reused or overwritten.

| Check | Observed API requests | Elapsed | Result |
| --- | --- | --- | --- |
| Pin current master ref and immutable commit | 2 GETs | Included in primary sequence | Commit/tree identities resolved and pinned. |
| Cold production inventory refresh | 23 GETs | 18.585 s | Complete root/partition traversal; 16,554 validated metadata entries committed into fresh SQLite. |
| Warm refresh at the same pin | 2 GETs | 0.702 s | Ref/commit rechecked; **zero tree requests**, all 16,554 entries reused, identical index digest. |
| Exact/missing/wrong-case lookups | 0 | 0.020 s | `found`, `missing`, `case_conflict` respectively; no case-insensitive alias silently accepted. |
| One selected image fetch | 1 GET | 0.368 s | Git SHA, declared/actual size, image decoding and cache receipt verified. |
| Repeated image/cache read | 0 | 0.057 s | Same verified bytes/receipt, no blob request. |
| Offline read with no API client | 0 | 0.012 s | Same verified cached file; no network. |
| Pin real first-parent commit | 1 GET | Included in primary sequence | Immutable historical commit/tree obtained from real commit ancestry. |
| Cold first-parent inventory in second fresh SQLite DB | 23 GETs | 11.813 s | Real historical snapshot; no synthetic remote mutations. |
| Historical-to-current incremental refresh | 2 GETs | 2.863 s | Root plus changed `franchise` subtree fetched; **21 unchanged root subtrees reused**. Final index exactly matches independent current cold refresh. |
| Independent complete-root recursive cross-check | 1 GET | 2.445 s | `truncated=false`; all 16,554 path/SHA/size/mode/type records match production partitioned SQLite index. |

The primary cold/warm/lookup/blob/history/incremental sequence took **36.332 s**.
The independent root check and local collision control have separate timers;
these are observed integration timings, not rendering/production benchmarks.

The historical incremental check pinned actual first parent
`d4eb01a241172337aba2bcb0848f7e16143bb512`, tree
`1b026bad766905555cd0630baf165d236b3da1bd`. It then switched only the local
read-only client's already-verified target to the current pinned pair. Both
targets are real immutable GitHub objects; no commit/tree was fabricated or
written. Unlike the normal warm check, this controlled historical transition
does not re-resolve a moving branch. No root subtrees were removed; exactly one
changed (`franchise`), and 21 were reused without requesting those trees.

Request ledger totals, including the independent completeness cross-check:

- **55 GET requests, all HTTP 200**: two ref lookups, three commit reads,
  49 tree reads and one blob read. Complete endpoints/order/status/response-byte
  counts are retained locally. No POST, PUT, PATCH, DELETE, clone or push to
  Default-Images was issued.
- **12,278,110 response-body bytes** measured through the streaming transport,
  including JSON/base64 overhead, not wire/TLS byte counts or image bytes alone.
- Minimum observed `X-RateLimit-Remaining`: **4,943**. No rate-limit, auth,
  transport, malformed-response or integrity errors were observed.
- No tree response was truncated. Live fallback for truncation was therefore
  not exercised; existing focused regression coverage still tests that branch.

#### Lookup and Collision Checks

Exact `genre/overlays/bigger/Experimental.png` returned `found`.
Wrong-case `Genre/overlays/bigger/Experimental.png` returned `case_conflict`,
not `found` or `missing`. A generated unique root path confirmed absent from the
complete index returned authoritative `missing` without another request.

There were **zero natural normalized case/Unicode collision groups** in this
snapshot. Multi-entry ambiguity was verified separately in a clearly labelled
local SQLite backup: add a case-variant metadata twin only in that copy, check
both spellings return `case_conflict` with two entries, and verify image fetch
is blocked with zero API requests. The original live-snapshot DB remained
unchanged. This 1.072-second control is not evidence of a real repository collision.

#### Selected Image and Receipt

- Existing image: `genre/overlays/bigger/Experimental.png`.
- Actual bytes and tree-declared size: **2,004**.
- Verified Git blob SHA: `1e3ec8b44efbbd59e2cd927d5d5a061ecdb5339b`.
- Verified SHA-256: `a5789cb6ad32b444410a35560f714abf27d3ec98a5c9d70ecb1a76b37710d55d`.
- Independently verified and fully decoded with Pillow: **PNG, 148x100, LA,
  one frame**. It was downloaded for inspection, not generated or modified.
- Cache receipt matches exact path, blob SHA, SHA-256, byte size, repository,
  `master` provenance and the pinned commit/tree. Second and offline reads
  validate the same cached file without GitHub calls.

No clone or complete image download collection was required; `.git` is absent
from the isolated evidence directories. Only metadata plus this one small image
were fetched. Production PowerShell/composer, historical fixtures and every
Default-Images object/ref were left untouched.

#### Regressions and Remaining Limits

No genuine implementation gap was found, so no new regression test or executable
change was needed. The existing focused inventory/assets suite was rerun:
**10 passed, one Windows account symlink-permission skip, 5.38 s**. Its existing
multi-entry case/Unicode collision, truncated traversal, stale/auth-failure,
SHA/size/corruption and transport tests remain intact. The draft PR workflow also
runs automatically for the report-only update; no production behavior changed.

This closes the previously missing limited B3 inventory -> SQLite -> lookup ->
selected-download/receipt integration evidence. Deliberate real permission
failures, quota exhaustion, actual transport outages, naturally occurring case
collisions and truncated trees were not provoked or observed. Such adverse cases
remain mocked; controlled live fault tests need separate sandbox authorization.
Broader published-image comparison, representative workload/cache performance and
long-duration integration acceptance remain E, not claims from this bounded probe.

### Gate B Recommendation

The required Linux CI, Windows compatibility evidence, both baseline validators,
direct-composer adapter review and bounded-worker proof pass. There are no
unresolved test failures after the clean-runner dependency fixes. The draft PR
is ready for maintainer review; it must not be marked ready, merged or deployed.

The authorized limited live B3 follow-up now passes, including a real changed-tree
incremental transition and independent completeness cross-check. **Gate B is ready
for final maintainer approval** on the documented Package B scope; this report
does not grant that approval or authorize C. Full poster workloads/parity (C),
overlays/multilingual review (D), controlled live failure testing and production
performance acceptance (E) remain deliberately deferred, not represented as work
completed in B. Stop here for Gate B approval; Package C has not begun.

## Exact File Inventory

Modified tracked files:

```text
.github/workflows/default-poster-validation.yml
create_defaults/tests/test_validation.py
create_defaults/validation_manifest.py
create_people_posters/people_github.py
create_people_posters/people_remote_inventory.py
```

Updated existing local Package A documents (already untracked before B):

```text
create_defaults/PHASE2_REQUIREMENTS.md
create_defaults/PHASE2_ARCHITECTURE.md
create_defaults/PHASE2_CATEGORY_INVENTORY.md
create_defaults/PHASE2_MIGRATION_PLAN.md
```

New Package B files:

```text
create_defaults/PACKAGE_B_REPORT.md
create_defaults/requirements-bulk.txt
create_people_posters/github_inventory_core.py
create_defaults/bulk/README.md
create_defaults/bulk/__init__.py
create_defaults/bulk/__main__.py
create_defaults/bulk/assets.py
create_defaults/bulk/baselines.py
create_defaults/bulk/baselines/approved-fonts.json
create_defaults/bulk/baselines/effective-jobs-en-current.json.gz
create_defaults/bulk/baselines/source-delta.json
create_defaults/bulk/build_examples.py
create_defaults/bulk/color_math.py
create_defaults/bulk/colors.py
create_defaults/bulk/common.py
create_defaults/bulk/config.py
create_defaults/bulk/definitions.py
create_defaults/bulk/examples/franchise.yml
create_defaults/bulk/examples/genre.yml
create_defaults/bulk/examples/playlist.yml
create_defaults/bulk/examples/profiles.yml
create_defaults/bulk/examples/year.yml
create_defaults/bulk/migration-policy.json
create_defaults/bulk/planner.py
create_defaults/bulk/remote.py
create_defaults/bulk/schemas/definition-v1.json
create_defaults/bulk/schemas/manifest-v1.json
create_defaults/bulk/state.py
create_defaults/bulk/tests/data/CIEDE2000_REFERENCE.md
create_defaults/bulk/tests/data/ciede2000-reference.txt
create_defaults/bulk/tests/test_baselines_cli.py
create_defaults/bulk/tests/test_colors_state.py
create_defaults/bulk/tests/test_definitions_planner.py
create_defaults/bulk/tests/test_legacy_reference.py
create_defaults/bulk/tests/test_remote_assets.py
create_defaults/bulk/tests/test_workers.py
create_defaults/bulk/translations.py
create_defaults/bulk/workers.py
create_defaults/bulk/workspaces.py
```

All pre-existing local `create_defaults/phase2/` prototype files and its historical
JSON evidence remain intact and were not rewritten by B. Ignored `config/` plans,
SQLite/cache/workspaces and pytest temporary proof receipts are generated local
evidence, not production source, publication outputs or tracked image datasets.
