# Phase 4 M7 implementation and evidence dossier

Branch: `feat/lifecycle-phase4-m7-acceptance`.
Confirmed starting remote HEAD: `68179d1c568449375ca72b23239b57770dfc229e`.
M1–M6 and dependency/People maintenance were already merged. M7 adds acceptance
tests and evidence only. No existing runtime, protected production member,
approval protocol or original validation inventory is changed.

## Existing infrastructure consumed

The test fixture reuses M5's native `transaction_seed`, `reviewed`,
`update_candidate`, `Transaction.prepare` and real `apply.commit_synthetic`.
It creates an ADD and a material source UPDATE of the same assigned Genre
identity with actual encoded full-resolution compositions, real Phase 3
consumption and two explicit synthetic review stages. Original immutable
snapshots and durable receipt references remain available after later changes.

Mapping cases call unchanged M6 `prepare`, `propose`, `commit_synthetic`,
`recover`, `recover_local` and existing decision types. Both registry and
mapping markers remain in the original M1/Package E transaction. The fixture
backup/reset is only disposable test isolation and is never called recovery.
The application recovery APIs, not the backup, demonstrate rollback, retained
artifacts, exact retries and idempotent local move observations.

No synthetic authority is reconstructed from stored decisions. The original
live trial capability is required for commits/retries; cold restart is an
explicit read-only replay with writer construction prohibited. Both operational
entry points remain unavailable, and every real approval/application/READY/
ACTIVE/publication flag is false.

## Focused integration coverage

* Full ADD→UPDATE→RENAME→DELETE: stable identity, changed encoded update bytes,
  original names, two retained artwork epochs, case-only literal mapping,
  immutable tombstone, unrelated M1 history, cold process and exact retries.
* Post-UPDATE mapping failures at mapping-marker, registry-marker and commit-
  event boundaries: no partial registry or mapping head and prior records intact.
* Post-UPDATE case-copy interruptions at durable prepare, staged preimage,
  link, intermediate and destination: explicit restoration followed by exact
  retry, committed spelling and repeated read-only/idempotent observations.
* Lost success acknowledgement after actual SQLite COMMIT: one committed mapping
  and exact retry, with no double append.
* Cancellation and separately reviewed compensation retain material and history.
* Stale mapping plans and old M5 retries after M6 fail at their original guards.
* Corrupt snapshot/receipt objects and damaged immutable journal/head namespaces
  fail at the intended integrity check, without production repair.
* Actual current graph/registry projections retain child and generated-exclusion
  blockers. This does not invent a supported child/family executor.

The [T01–T22 matrix](PHASE4_M7_COVERAGE.json) references the existing mandatory
native disjoint/shared-source, companion, concurrent update, namespace, source/
PNG, translation, review, real process-death and 512 MiB worker-parent tests.
They remain in their original executors and are not copied into new full-library
test jobs. All 1,671 original pytest and 155 unittest identities remain frozen.

## Evidence producer and acceptance

`ci/phase4_m7.py` uses existing `pytest_run`, `validate_execution`, canonical
fingerprints, exact identities and report conventions. UTF-8 response files
avoid Windows command limits. A complete namespace collection must equal the
disjoint explicit M7 selections. Group reports bind the exact head/plan, test
inventory, coverage matrix, current lifecycle/schema/test source hashes,
preservation checks and complete setup/call/teardown reports.

Acceptance requires every platform/group, zero new skips/xfails and two native
sequence proofs. It verifies exported synthetic ADD/UPDATE JPEG hashes/lengths,
exact cross-platform encoded equality, retained identity/tombstone/history and
false operational flags. Missing, stale, cancelled, substituted or partial
reports/artifacts fail closed. This is additive CI evidence, not a new approval
framework, database or publication mechanism.

The original `Validation acceptance`, M6 acceptance and dependency-provenance
jobs remain independently required. The final PR indexes all final-head workflow
results and reconciles actual IDs and historical artifacts, rather than treating
the additive M7 acceptance result alone as complete Phase 4 evidence.

## Compatibility and resource evidence

The preservation checker validates exact merged dependency/People maintenance,
299 adoption-source pins and 190 protected members. One streaming `git cat-file`
reader compares all 2,927 existing baseline files without loading the complete
tree or creating a subprocess for each file. Text checkout line endings are
normalized; binary files remain exact. No current source is replaced by a
historical test view.

No existing historical capture or source-selection mechanism is modified. Final
historical counts/hashes and actual source/definition/receipt facts must come
from the existing guarded shared fixture on both platforms. Pending results are
not a compatibility claim. Local development logs remain separate from final
exact-head artifacts. The final draft PR supplies actual counts and durations.

All 15-minute CI caps and the original parent/worker memory and process limits
remain unchanged. A preliminary third native ADD duplicated the existing M5
unaffected-artwork test and exceeded a sensible bounded sequence workload;
the focused chain reuses that proof and verifies an independent immutable M1
record across the full history. Database and move failures have separate groups.
Native rendering, current validators and all original negative assertions remain
real and mandatory.

## Scope and handoff

Only tests, additive CI and lifecycle documentation change; see the
[15-file inventory](PHASE4_M7_CHANGED_FILES.md). Existing worktree changes,
including the deleted `People-Auto-Readme` gitlink, are excluded. Public artwork,
production YAML, fonts, compositions, category/logo policies, historical receipts,
existing workflow, 190/299 memberships and all original runtime files remain
unchanged. No new batch, recovery of People work, remote cleanup or activation
is performed. Phase 4 remains pending maintainer acceptance; Phase 5/6 have not
started. [Operational prerequisites](PHASE5_PREREQUISITES.md) remain blockers.
