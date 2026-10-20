# Phase 2 Migration and Gate Plan

**Gate A and D01-D08 approved; Package B authorized and implemented locally.** Work is on
`feat/default-posters-python-generator`, created from current `main`
`57ef136833a3f54da2bf1e4ddef98addfa36d583`. No commit, push, draft PR, merge,
deployment is authorized. Packages C-E require separate authorization.
The persistent-worker addendum extends B with infrastructure tests/a small proof,
not full batch rendering, category migration or production performance claims.

## Package Dependencies

| Package | Depends on / delivers | Gate evidence |
| --- | --- | --- |
| A | Current source capture, category/color/asset/language/output audit, four design documents, minimal schemas and real-example validator. | Gate A and D01-D08 approved by maintainer. Historical audit evidence retained. |
| B | Approved A; production models/planner/CLI, neutral People primitive extraction, read-only remote metadata, color registry, translations, state/workspaces, persistent spawn workers and bounded scheduling/fingerprints. | Unit/security/cache/tree/collision tests, D01 matrix, People regressions, separate historical/current baselines and synthetic worker recovery proof. See Package B report; no production cutover. |
| C | B models/planner/direct composer adapter and accepted compatibility rules; migrate category groups and integrate persistent workers with actual workloads. | Fresh legacy versus Python manifest/image comparisons, verified dependency staging and no unexplained output/font/color/name changes. |
| D | B state/layout/translation contracts + C definitions; independent overlays, all-language preflight, risk previews, review/report and approval invalidation. | Overlay pixel/path/alpha tests, supplied-language coverage, exact-version group/concurrent review tests. No Flask. |
| E | C and D gates; full current inventory, selected remote artwork comparisons, cross-platform/reliability/performance validation. | Measure throughput/RSS/process counts/I/O/cache against legacy process-per-poster execution; no missing outputs/unexplained regressions. Cutover remains separate. |

Reviewable C groups, proposed order:

1. Straightforward static tables: Aspect, Based, Franchise, Playlist, Seasonal,
   Universe, VideoFormat, Studio. Include 2011, approved fonts and inactive-field case.
2. Shared/paired styles: Chart, Country, Network, Streaming, Resolution. Verify
   every color/white path and copied-logo contract, not only one representative table.
3. Translation-heavy templates: AudioLanguage, SubtitleLanguage and Genre. For
   Genre, apply approved D02: migrate only authoritative red Splatter line 4884
   (`#990000`, white-wash disabled); retain retired green line 4883 as audit
   evidence, never an active definition/job. Compare key resolution, placeholders
   and no-caption cases explicitly.
4. Conditional/generated values: ContentRating and Awards. Preserve every actual
   year range, prefix, national rating directory, special suffix and queue lineage.
5. Generated input DAG: Decade and Year; then Separators with explicit random
   manifest choices and all 22 background assets/root collectionless output.

At each group: allocate stable IDs and lineage map; implement only its definitions/
rules; generate a fresh Python manifest; compare to hash-bound current legacy
capture; explain every difference; run focused fresh paired render comparisons;
add regression tests; obtain acceptance before broadening. Do not hardcode 9,958
as a permanent expected job count or normalize historical source errors silently.

## D02 Genre Migration Contract

The maintainer has resolved Splatter in favor of the red source definition.
Package B does not begin Package C or change the PowerShell
generator, active definitions, frozen fixtures, rendered evidence or validation results.

During Package C:

- Map authoritative `create_default_posters.ps1:4884` to the active Splatter
  logical identity. Preserve `SPLATTER`, `Splatter.png`, translation/case behavior,
  layout, font/fitting, filename, `#990000` background and disabled white-wash.
- Keep `create_default_posters.ps1:4883` (`#416939`, white-wash enabled) as a
  retired source identity linked to D02 and its authoritative replacement.
  Exclude it from active definitions and rendering jobs, not from audit coverage.
- Preserve both original rows and fingerprints in the
  [D02 migration audit](PHASE2_CATEGORY_INVENTORY.md#d02-splatter-migration-audit).
  Do not regenerate historical captures to erase the duplicate.
- Add migration regressions asserting exactly one active `genre/Splatter.jpg`
  per selected applicable language, red `#990000`, white-wash false, unchanged
  red parameters/translation/output mapping, and no job from retired line 4883.
- Retain collision validation before manifest generation/rendering. Test that
  conflicting active definitions, including exact/case/NFC-equivalent paths,
  are rejected rather than overwritten or silently deduplicated. The Package A
  prototype already rejects both Splatter rows when submitted together as active;
  D02 does not exempt this path from collision checks.
- Report D02 as an explicit approved source-to-active-job difference. For the
  unchanged audited English All scope, the sole retirement projects Genre
  **276 -> 275** and total **9,958 -> 9,957** jobs. Keep the original 276/9,958
  evidence and validation results unchanged. Reconcile actual newly generated
  counts, list the retired source line/reason and reject unexplained differences.
  Do not confuse one fewer invocation with removing a required unique output.

## D01 Color Policy Implementation Contract

**D01 is APPROVED / RESOLVED**, initial policy `defaults-colors-v1`. B implements
the registry/policy engine without source-color edits, historical audit rewrites,
artwork renders or production migration. D02/historical evidence remain preserved.

Package B must import historical category assignments as occupied colors with
source lineage, including historical duplicates, without manufacturing approved
exceptions. Map rows/variants to logical owners rather than allocating a color
for every rendered language/output. Independent choices, inherited assignments
and template-derived colors need explicit distinct provenance and parent links.
Persist approved new choices in reviewed definitions/registry records and reuse
them deterministically; suggestions must never recolor existing posters.

Implement category-local **normalized exact** uniqueness only for new unrelated
logical posters. Cross-category exact reuse is allowed/informational. Explicitly
linked related posters, collections and generated variants may intentionally
share colors without collision warnings. Similar nonidentical colors are warnings
under configurable versioned thresholds, never automatic blockers. Named manual
exceptions require an authorized reviewer, justification, policy version and all
affected logical poster identities, not implicit permission inferred from history.
Use the [registry specification](PHASE2_ARCHITECTURE.md#color-registry-specification-d01)
for record schemas, result precedence and exact-reservation transactions.

Required B regression cases before color infrastructure acceptance:

| Case | Required result |
| --- | --- |
| `#aabbcc` vs `#AABBCC`, including surrounding input whitespace | Same normalized exact HEX; preserve source spelling and reject unsupported formats. |
| Multiple existing historical category duplicates | Preserve every source color unchanged; retain audit identity without inventing approved exceptions. |
| New unrelated poster using a historical category color | Reject exact assignment unless a valid explicit relationship or authorized named exception permits all same-category conflicts. |
| Same HEX, unrelated posters in different categories | Allow with informational owner/category collision, not warning/blocking status. |
| Explicit related/collection/generated reuse | Allow without collision warnings; unrelated owners remain protected even when one matching owner is related. |
| One logical assignment rendered into multiple languages/outputs | One logical assignment/reservation, no repeated-output uniqueness conflicts. |
| Independently assigned vs inherited/template colors | Distinct provenance; shared template name alone cannot bypass unrelated logical-owner checks. |
| Nonidentical colors inside a configured perceptual threshold | Warning with distance/method/threshold version; no automatic block, including concurrent reservations for similar but distinct HEX values. |
| Authorized named override | Exact affected IDs, reviewer identity, justification and policy version recorded; no unresolved warning for the permitted exact pair. Missing authority, stale/revoked or insufficiently scoped exceptions cannot admit a new prohibited claim. |
| Two unrelated concurrent claims for the same category/HEX | At most one succeeds; checks include historical, committed and live reserved owners in the same transaction. Related/authorized shared claims may both succeed only after all-owner checks. |
| Approval after policy/relationship/exception or definition changes | Revalidate against current versions; reject stale claims without recoloring existing assignments. |
| Interrupted persistence, expired leases and rerun | Recover the same approved HEX; reclaim only expired uncommitted claims, preserve historical reservations and audit decisions. |

During later C/D integration, use the same policy results in preview and approval
interfaces: explain normalized exact collisions, permitted cross-category use,
explicit relationships, warning-only similar colors, and named exceptions with
reviewer/justification/version. Do not present historical reuse as an unresolved
new-poster conflict or an inferred approved exception. No new font/layout/contrast
thresholds or global uniqueness mode are approved by D01.

## Historical Package A Files

New documentation: this file, `PHASE2_REQUIREMENTS.md`, `PHASE2_ARCHITECTURE.md`,
`PHASE2_CATEGORY_INVENTORY.md`.

New development prototype: `phase2/__init__.py`, `definitions.py`, `audit.py`,
`inspect_source.ps1`, `requirements.txt`, three JSON Schemas, four-example YAML,
four generated JSON evidence files, and `phase2/tests/test_package_a.py`.
Generated JSON is audit/specification evidence, not a generated image dataset.
At the Package A checkpoint all tracked files remained unchanged. Package B's
scoped tracked edits are enumerated in its report; historical fixtures remain immutable.

`phase2/requirements.txt` records the optional experiment dependency
`jsonschema==4.26.0` and existing Phase 1 requirements. It was already installed
locally; no software was installed or downloaded. Dependency acceptance/pinning
for the eventual runtime and CI is part of B. Existing fast Phase 1 CI is not
rewired by Package A. No Linux or multilingual success is claimed from Windows tests.

## Reproducing the Audit

Use Python 3.13 explicitly on Windows. These commands do not publish, clone,
download translations, or generate full posters. Run from the repository root.
The capture step requires **existing** local PowerShell 7 and ImageMagick as
development reference tools only; future Python runtime will not need either.
Use new ignored capture/output directories rather than overwriting frozen fixtures.

```powershell
py -3.13 -X utf8 create_defaults/validation_manifest.py --capture-dir config/phase2-new-capture --fitting-cache config/phase1-validation-20261016/fitting-cache --output config/phase2-new-manifest.json.gz
py -3.13 -X utf8 create_defaults/validation_manifest.py --check config/phase2-new-manifest.json.gz
pwsh -NoLogo -NoProfile -File create_defaults/phase2/inspect_source.ps1 -Source create_defaults/create_default_posters.ps1 -OutputFile config/phase2-new-source-structure.json
py -3.13 -m create_defaults.phase2.audit --manifest config/phase2-new-manifest.json.gz --structure config/phase2-new-source-structure.json --output-dir config/phase2-new-audit --examples create_defaults/phase2/examples/current-posters.yml
py -3.13 -m create_defaults.phase2.definitions create_defaults/phase2/examples/current-posters.yml
py -3.13 -m unittest discover -s create_defaults/phase2/tests -v
py -3.13 -m unittest discover -s create_defaults/tests -v
git diff --check
```

If shared fitting cache entries are absent, the reference fitting step measures
captions using installed ImageMagick; no image-batch rendering is implied. Source,
font and fitting request hashes are checked. The AST capture instruments isolated
category copies and virtual file operations, not the production bootstrap, network
translation refresh, filesystem moves or publishing. Never execute the original
bulk script wholesale merely to inventory it.

Known Windows encoding issue in the historical capture CLI: the immediate
captured.json read uses the process default encoding; a non-UTF-8 Windows process
can corrupt accented literal rows and fail lineage checks. Package A initially
encountered this, then explicitly decoded the completed capture with `utf-8-sig`
and resolved the existing fitting cache via the unchanged validation APIs. The
full build then passed every literal-row guard. `-X utf8` above avoids the faulty
entry path without editing historical tooling or suppressing lineage validation.
The capture source hash was checked before/after; all 3,352 rows are accounted for.

Audit reports refuse replacement by default. `--replace-evidence` explicitly
replaces only the audit exporter's named generated reports, not input scripts or
fixtures. Parser inspection separately refuses overwriting its report. Paths in
tracked evidence are repository-relative/sanitized; ignored local captures are not
appropriate for redistribution without review.

## Historical Package A Validation Results

Executed on Windows/Python 3.13, 2026-10-16:

- Fresh English capture and complete manifest build: **3,352/3,352 literal rows,
  9,958 jobs**, all 21 categories/17 fonts, 165 generated-input jobs, 36 overlays.
- Current manifest source/assets validation: passed through the audit exporter.
- YAML prototype: **4 real examples validated**, no image output generated.
- Focused Package A suite: **35 tests passed** in 7.454 seconds at final verification.
  Covers strict schema/types/inheritance, stable IDs, duplicate YAML keys/unsafe
  tags, path safety, exact language identifiers, output case/NFC conflicts, actual
  Splatter rejection, current source/color/overlay evidence and sample parameters.
- Current manifest CLI check: **passed**, validating 9,958 effective jobs and
  3,352 definitions against current source, assets and fingerprints.
- Python compile check: `py -3.13 -m compileall -q create_defaults/phase2` passed.
- `git diff --check` passed. All 18 new files were also checked individually with
  Git's no-index whitespace checker (accepting normal Windows CRLF line endings).
- Existing Phase 1 suite: **120 tests run, 119 passed, 1 error** in
  `FrozenInventoryTests.test_frozen_manifest_covers_all_literal_rows_and_dynamic_jobs`.
  It calls `validate_manifest` on the immutable historical fixture against the
  corrected current bulk source and correctly reports
  `Frozen renderer/source changed: create_default_posters.ps1`.
  Runtime was 60.285 seconds. No regression suite was changed or loosened.
- Material old/current capture comparison: **exactly one changed job**, the 2011
  correction already present on main; no other effective parameter/font/output
  differences. Identical counts do not disguise this source change.

D08 is now approved and B resolves this mismatch with separate baselines. The
original historical fixture is unchanged. Its wrapper reconstructs only the known
historical output-name source delta in a temporary directory, verifies original
source hashes, then runs the same complete original validation against that source.
A separate corrected-current-source fixture validates today's source directly.
Unknown changes and font/asset drift still fail; no hash checks are suppressed.
The historical 119-pass/one-error checkpoint above remains truthful history.
The post-fix Phase 1 suite passes all 120 tests. This is not a new full render run.

## Future Test Matrix

| Area | Required cases before its gate |
| --- | --- |
| Definitions/planning | Version migrations, defaults/overrides, fixed vs fit, IDs, output mapping, selection aliases, full source coverage, dependency cycles, deterministic ordering and complete parameters. |
| Colors | Approved D01 matrix: normalized category-local exact checks at logical-assignment level, reserved historical duplicates without invented exceptions, informational cross-category reuse, explicit related/template provenance, authorized named exceptions, warning-only configurable CIEDE2000 similarity, deterministic persistence, exact-concurrency exclusion without near-color blocking and crash recovery. Palette/contrast diagnostics remain separate. |
| GitHub | Auth/repo/branch separation, read-only method/repo restrictions, complete large/truncated trees, stale caches and partial failures, exact/case conflicts, snapshot pinning, selective downloads, SHA/size/base64/image validation, no clone and no secrets in diagnostics. |
| Translations/layout | All exact selectors with supplied local snapshots, key-case/value-case behavior, missing/fallback/override tracing, multiple placeholders/replacement semantics, shared text, glyphs, wrapping/clipping and Arabic shaping/direction/font availability. |
| Approval | Per-language decisions, exact-version groups, accepted warnings, sampled vs individual inspection, no approval for altered bytes, dependency invalidation, concurrent stale-version conflicts, audit export and crash reconciliation. |
| Batch/files/security | Cache corruption, missing/changed inputs, interrupted output promotion, dependency hash changes, timeouts/cancel/reap, bounded queues/memory, explicit force/overwrite, symlink/reparse traversal, ownership/cleanup isolation and Python-only execution. |
| Overlays | Trim/no-trim, both boxes, aspect/upscaling, RGBA/palette/opaque-background/empty cases, profiles/metadata/page offsets, resampling/alpha edges and exact output names. |
| Integration | New Python vs fresh legacy manifests/images, separately labelled published/approved-font differences, all required artifacts verified, realistic multilingual dedup savings and Windows/Linux resource/performance evidence. |

Fast PR CI should run offline unit/schema/security tests, immutable historical
evidence checks against its own source identity, and current-source inventory
checks against a separate current fixture. No images/network/Powershell/ImageMagick
in normal fast validation. Expensive full parity runs are separately invoked,
input-version-pinned and resumable; their reports must state exact coverage and
imports/reuse rather than imply every comparison was freshly rendered.

## Historical Package B Gate

Review [Package B Report](PACKAGE_B_REPORT.md) for actual test results, exact
file inventory, worker proof measurements and outstanding platform/workload limits.
B implements infrastructure only; no migrated production category, overlay engine,
approval UI or full batch has been run. Arabic fonts/RTL remain unvalidated.
Native Linux cleanup/atomic-write tests and real-poster resource sizing must be
demonstrated at their gates. No measured production speedup is claimed.
Stop for maintainer review and explicit Package C authorization. Do not commit,
push, open a PR, merge, deploy or publish. Keep the legacy generator available
until all later gates and separate cutover authorization are satisfied.

## Package C Authorized Implementation

Gate B was approved and Package C separately authorized. The original B stop
above records its historical boundary; it does not authorize D/E or cutover.

The English poster catalog now uses per-category YAML, a shared profile and
named Python generators. `bulk/generation.py` integrates direct composer calls
with the persistent pool and stages verified Year/Decade parents before children.
`bulk/migration.py` remains development-only; rendering never imports it.

D02 removes exactly one active green Splatter job (276 -> 275, 9,958 -> 9,957).
Both source rows remain in the immutable historical capture and the new Genre
audit. Two legacy overwritten Awards calls remain explicit private intermediates
with null remote destinations; they are not silently erased from effective-job
counts. The `(2011)` Death in Paradise output correction is retained.

Per-category acceptance evidence, canonical plan identities and sample results
are in `bulk/catalog/audit/`. Sample and benchmark images/databases stay under
ignored `config/package-c/`, not source or Default-Images. Review the exact
matrix and remaining limits in [Package C Report](PACKAGE_C_REPORT.md).

Package C does not enable overlays, complete multilingual fitting/Arabic
approval, review UI, publishing or production cutover. Stop for maintainer Gate C
approval; Packages D/E remain unauthorized.

## Package D Authorized Follow-Up

Gate C has since been approved and Package D explicitly authorized on the same
draft PR. Preserve the completed A/B/C evidence and all production PowerShell
and validated Pillow behavior. The new local migration adds dynamic translation
snapshots, mandatory scoped preflight, overlay transforms and version-bound
human review, with small real rendering proofs and read-only live source audits.

Reconcile the 36 overlay operations into 18 groups/two sizes and retain all
4,122 destination contracts. Document Pillow/ImageMagick differences explicitly;
never modify earlier fixtures, visual thresholds or historical counts to conceal
them. Retain the red-only active Splatter decision and private Awards inputs.

Gate D evidence must include all poster-relevant discovered language resources,
accurate missing-key mappings/counts, blocked font/layout cases, precise delta
invalidation, immutable decisions, existing regression results and Linux CI.
The focused CI artifact is reviewer evidence only, not publication. New font
and layout proposals remain unapproved until the maintainer explicitly accepts
them. Package D may commit/push scoped work to draft PR #12, but may not merge
or mark it ready. Stop for Gate D review; Package E requires new authorization.


## Package E authorized acceptance work

Gates A-D have now been formally approved. Package E is authorized on the existing
draft PR #12 from `166a007c00f14b166a97be8887a4532ea42078b8`. Preserve all earlier
reports, fixtures, color assignments and exact Package D sample decisions.

Acceptance separately evaluates complete English generation, overlay transforms
and every discovered language. Local full generation, controlled process-per-poster
legacy comparisons, worker scaling, fresh read-only inventories and all-language
preflight are opt-in bounded runs. Small offline CI proves platform contracts and
retains focused artifacts without publishing. Evidence must distinguish automated
verification, exact historical sample approval and still-pending human decisions.

The current work and remaining acceptance criteria are recorded in
[Package E report](PACKAGE_E_REPORT.md). Do not infer cutover authorization from
a successful test or readiness recommendation. Keep the PR draft, retain the
production PowerShell implementation and stop for final maintainer review.

Package E completion evidence separates exact contract reconciliation, full local
output verification, prior approved-API byte comparisons, selective pinned remote
comparisons and visual acceptance. A successful render or pixel comparison cannot
substitute for current approval identities. Existing D sample decisions remain
immutable; the ICC overlay correction and unreviewed translations require their
reported current review decisions.

Use the independent readiness matrix and unexecuted cutover/rollback checklist in
[Package E report](PACKAGE_E_REPORT.md), with reproducible commands in
[Package E usage](PACKAGE_E_USAGE.md). Resolve the published Action & adventure
filename case conflict explicitly before any separately authorized cutover. Do not
publish incomplete language collections, move private Awards inputs into public
paths, or infer publication permission from automated acceptance.

## Package E multilingual correction acceptance

Retain the original D/E audits as historical evidence. The corrected audit must use
the same pinned translation snapshot for its before/after comparison, count only
poster-required keys, and distinguish missing values from actual typography
constraints. Confirm unchanged English validation identities and output parameters.

Fitting translated text becomes technically eligible without matching English.
Proposals requiring changed typography remain pending version-bound layout review;
no automatic font installation, layout activation, artwork acceptance or publication
is authorized. Keep Arabic and other unreviewed variants pending artwork review
even when their translation and technical checks pass. Reconcile exact stale review
contexts without altering historical decisions, then stop for maintainer Gate E review.

## Gate E approved; English canary preparation boundary

The maintainer approved Gate E's recorded scope at `83ed3d1` on draft PR #12,
including the mandatory public path `genre/Action & Adventure.jpg`. Earlier
stop/review language above documents prior checkpoints. The additive
[approval record](bulk/evidence/package-e/gate-e-approval-20261017.json) preserves
all immutable evidence. Preparation of a seven-output English-only canary is
authorized and complete; see [the concrete canary plan](ENGLISH_CANARY_PLAN.md).

The plan isolates overlays, multilingual work and unrelated artwork, and includes
current published comparisons, a verified local backup bundle, offline rollback
rehearsal, proposed workflow/permissions and exact later approval steps. Exact
canary artifact acceptance, guarded workflow/setup, remote staging and production
publication are separately gated. Nothing is published, no credentials enabled,
PowerShell replaced, PR merged/marked ready, canary started or subsequent phase
automatically begun. Keep PR #12 draft and stop for explicit authorization.

The maintainer has now personally inspected and accepted all seven exact English
canary candidates. The separate [visual acceptance record](bulk/evidence/english-canary/visual-acceptance-20261017.json)
and [individual audit events](bulk/evidence/english-canary/visual-acceptance-20261017-events.json)
preserve image/context/published-difference bindings and all earlier evidence.
This resolves the seven-artifact visual review requirement only. Operational plan,
workflow/credential setup, owner/window and explicit staging permission remain
outstanding; no Default-Images write, PR #12 merge or production change is authorized.

Staging infrastructure has been prepared as inactive, reviewable code only. See
[configuration and implementation](canary/STAGING_INFRASTRUCTURE.md) and the
[separate authorization checklist](canary/STAGING_AUTHORIZATION_CHECKLIST.md).
All gates remain disabled; bullmoose20 roles are proposed/unconfirmed. The final-code
local dry-run creates no staging ref or remote write. App/env/credential installation,
artifact intake/sharing, infrastructure deployment and exact staging permission
remain separately required. Nothing merges PR #12, replaces PowerShell or publishes.

Trusted-maintainer staging policy was updated for the five verified users including
badja-dev. The Developers team matches all five; explicit users remain the disabled
default, with guarded optional team mode. One explicit native approval (including
self-review) is required per fresh run; no independent dispatcher or actor-based
auto-approval. Current read-only API admin-bypass verification is a fail-closed
blocker. Setup, private artifact intake and staging permission remain separate.
See the [current setup guide](canary/STAGING_INFRASTRUCTURE.md).

The maintainer has now approved Option A (five explicit users) for the reviewer model
only. Selected configuration and helper no longer support teams or require membership
lookups/organization credentials. Setup, artifact transfer, ownership and execution
still require separate approval. See the [final authorization checklist](canary/STAGING_AUTHORIZATION_CHECKLIST.md).

Infrastructure readiness engineering now selects private Git-blob archive intake with
a separate read-only App and supported UI/setup-receipt plus native hosted approval
evidence. No invented bypass API field is used. Source main protection, external setup,
actual hosted proof and exact staging authority remain unmet; no target write occurred.
