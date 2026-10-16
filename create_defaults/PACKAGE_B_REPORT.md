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

Three public GitHub metadata GETs verified destination `Kometa-Team/Default-Images`
branch `master`, head `59e49ede8d41ac5991f971e66e93af596402329a`, tree
`e1664efb92db5872db112cf18253910da77355df` and a complete 49-entry root response.
No live full inventory/image download was performed. Mocked integration covers
full-tree fallback, incremental snapshots, corrupt/incomplete caches, selected
verified blobs, rate limits and failures. No write-capable Defaults API is exposed.

## Outstanding Gates

- Native Linux worker/atomic-file tests have not run locally. WSL lists only the
  Docker Desktop internal distribution and the Docker daemon is unavailable. No
  distribution, container image or dependency was installed or service started.
  The Linux PR workflow includes B and relevant People compatibility tests. Its
  run/results will be recorded in the final gate evidence below.
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
and worker infrastructure are ready for Package C integration review. Native
Linux evidence remains outstanding for the cross-platform worker acceptance item.
Do not call the full production system validated or begin C without authorization.

## Final Gate Verification

Status: **in progress; Gate B is not yet ready for approval until Linux CI passes**.
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
existing People dependency `python-dotenv==1.2.4`, matching its existing rembg
requirements and the tested Windows environment. No test was removed or skipped
to hide those failures. The updated run must pass before gate sign-off.

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

### Live GitHub Coverage and Planned Gates

Live coverage is limited to the three GET metadata smoke recorded above. A complete
real `RemoteInventory.refresh()` -> SQLite -> exact lookup -> selected image fetch
has not been exercised end-to-end against Default-Images. Cold complete traversal,
warm/incremental refresh on real changing trees, actual blob/cache receipt handling,
authenticated permission boundaries and genuine rate-limit/transient failures
remain mocked, not live-tested. They must not be represented as demonstrated by
the metadata smoke or offline CI.

The next limited read-only integration check is a B3 follow-up before relying on
remote inventory for C decisions: pin a real snapshot, refresh into isolated local
state, repeat warm refresh, check exact/known-missing/case paths and selectively
verify a small existing image with its Git SHA/receipt. No clone, write or
publication is needed. Controlled live failures require a dedicated sandbox and
explicit authorization, not deliberate rate-limit exhaustion. E owns broader
published-image comparison and remote-cache/performance acceptance. Maintainer
approval must explicitly accept this live-integration limitation or require the
limited B3 check before closing Gate B.

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
