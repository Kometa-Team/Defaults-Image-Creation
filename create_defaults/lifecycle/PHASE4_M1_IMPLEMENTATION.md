# Phase 4 / M1 implementation and review dossier

2026-10-23. **M1 implemented, pending exact-head CI and maintainer review.**
Phase 4 is IN PROGRESS; M2-M7 and Phases 5-6 are NOT STARTED.

## Baseline and authorization

Planning PR #31 is merged at `c33f792992ee704150799fe16536a64630fd8964`, the
fetched main and parent of `feat/lifecycle-phase4-m1-operation-foundations`.
The maintainer explicitly approved P4-D01-D07 as architecture and authorized
**M1 only**. Earlier planning documents retain their dated historical approval
checkpoints; this dossier and the current [roadmap](ROADMAP.md) record the newer
decision. The draft PR indexes the exact final commit and CI run; acceptance
requires evidence for that head, not a previous development pass.

| Approved architecture | M1 implementation or explicit later boundary |
| --- | --- |
| P4-D01 atomic isolated snapshots | Immutable synthetic before/proposed references, multi-head/read-set CAS, same-transaction heads and journal; no live catalog changes or exporter |
| P4-D02 persistent stable identities | Immutable synthetic subject references only; actual registry/semantic lookup remains M2 |
| P4-D03 complete final-resolution evidence | Typed scoped evidence pointers only; no composition or partial-group approval; M3/M4 must verify actual bytes |
| P4-D04 fail-closed authority | Synthetic-only IDs/scope and constant false acceptance/application/approval/readiness/publication flags; no actor authentication |
| P4-D05 retain historical identities/names | Append-only history/tombstone references, no deletion/name-release API; actual retained ownership and name-reuse policy remain later work |
| P4-D06 journaled rename/recovery | Atomic record journal and rollback/restart tests; no filesystem rename or compensation executor |
| P4-D07 scoped prospective adapters | No adapters or fabricated historical candidates; actual adapter declarations/fail-closed coverage remain M2 |

The permanent six-phase roadmap, D01-D09, Phase 3 policy decisions, all historical
visual approvals/exceptions and frozen identity artifacts remain unchanged.

## Implemented interfaces and guarantees

The [module README](../bulk/lifecycle/README.md) specifies the exact schema,
states, revision semantics, API, transaction protocol, recovery and limitations.
`Operation`, `Event`, `HeadKey` and `HeadRef` reuse strict canonical immutable
Package E values. Closed schema/protocol versions reject unknown fields and
unsupported states/versions. Request identity/type/subject set cannot change
across revisions. Content changes require a new draft/content revision.

The only states are draft, structurally validated, conflicted, stale and
cancelled. They are informational records, never approval/application results.
Record heads reference the exact operation hash, not a supposedly applied
proposed snapshot. References are unverified metadata, not authenticated evidence.

One isolated Package E database contains four additive append-only M1 tables.
The additive public `SidecarStore` subclass avoids new production private-helper
calls and leaves frozen ContractStore source bytes unchanged. Multi-subject,
namespace, evidence and dependency heads are compared in
one immediate transaction with both per-operation pins and journal insertion.
Unchanged proposed bytes cannot override a stale selected read head. Disjoint
prepared requests can proceed without a false global-head conflict.

An identical retry returns the original historical event without reapplying
anything. Conflicting retries fail. Cancellation preserves immutable evidence.
Failures/process death roll back all committed indexes/heads/events together;
orphan canonical blobs remain unreferenced. Restart checks full canonical and
index linkage. An external journal pin is necessary to detect a coherent entire
archive rollback; unpinned inspections explicitly do not claim currentness.
Metadata size/count bounds apply independently of the unchanged worker limits.

## Adversarial validation

The explicitly collected 203 Phase 4 tests use temporary synthetic stores and
actual SQLite persistence, including simultaneous thread writers and subprocess
death inside an uncommitted transaction. They cover all four operation types,
schema/header/nested/encoding attacks, canonical hashes, invalid transitions,
changed scopes/content, concurrent identical and conflicting retries, overlapping
groups/casefolded namespaces, read-only evidence changes, orphan restart, immutable
SQL tables, injected failures across write stages, corrupted records/indexes,
external-checkpoint rollback, resource caps and symlink/Windows junction attacks.

Cold-import audit/profile hooks prohibit state creation, schema IO, network,
process launch and rendering/worker execution. Existing contract-framework
imports load definitions; importing definitions is not executing a renderer.
Real append/cancel/reopen tests run with actual renderer/worker/image/network/
remote publication/M7 controller entry points disabled. Forged actor flags,
actual historical IDs and all positive authority flags are rejected.

Development testing found and corrected a Windows first-object parent-creation
race, newline-terminated identity acceptance and foreign archive WAL/SHM creation
on inspection. Deterministic regressions preserve confinement checks and reject
foreign archives before SQLite is opened. These are M1 boundary fixes, not
changes to generation or existing visual policy.

The first complete hosted historical run also rejected the initial in-place
ContractStore bridge against the frozen M2 source hash. The final bridge is an
additive subclass in `bulk/lifecycle/package_e.py`; the original store was
restored exactly. No M2 source-pin exception, pin refresh or historical assertion
relaxation was added. A focused regression now verifies every frozen source pin
before accepting the bridge's storage/isolation proof.

The committed full canonical archive vector covers ADD/UPDATE/RENAME/DELETE,
record/event chains, exact accented paths and all heads/inspection results.
Archive SHA-256:
`2c934c600bd9b3841378d96e62d781e856f3617145a7b9c11df2db15338650d7`.
Windows and Linux must independently reproduce the full value and hash.

## CI and authorized source maintenance

`ci/phase4.py` adds an independent exact-ID producer on each OS. The mandatory
Validation acceptance depends on all four job families: collection, legacy
validation, Phase 3 and Phase 4. Missing, failed, cancelled, stale, skipped,
substituted or incomplete new evidence cannot produce success. Distinct artifact
names avoid contamination of earlier legacy and Phase 3 evidence selectors.

The workflow expands from 21 to 23 checks. Each job still has a 15-minute cap;
the original 512 MiB parent/worker safeguard, 1,671 original pytest IDs, 155
unittest IDs, 12 CI control tests and 662 Phase 3 IDs remain mandatory. No old
collection baseline or validation-plan selection changes. Branch protection
should require **Validation acceptance** plus the existing required checks; the
new Phase 4 matrix checks can also be required explicitly. No settings changed.

`ci/phase4-maintenance.json` pins the exact baseline and current bytes of the
seven existing files necessarily maintained for this additive CI gate.
The gate verifies that manifest's own canonical pin, each before/current hash,
unchanged 190-file membership and the workflow as the **only** changed protected
file. The previous protected-manifest hash and workflow hash remain recorded.
Unexpected source changes and production activation imports still fail the
original tests. Frozen M1/Phase 3 schemas and all other protected pins are intact.

## Historical reconciliation and final evidence contract

Both OS historical jobs must validate all 14,079 outputs, 14,077 public
references, 22 packages and 278 variants without unexplained changes. All 22
actual approvals remain missing; no real READY/ACTIVE or publication authority.
Existing historical assertions/negative controls are retained. Exact names,
receipts, definitions, assets, translations, renderer and destinations are not
changed by this PR.

The historical projection hash remains
`d5ddf0d646de1968a0054acfda7fa199330848d3d57254f6611fca7ed636e476`;
exact-name hash remains
`32d3a7492b56f007ece4ff7fb83fd2a1b7758c117d34bb92ceae5c6281301fdc`.
The complete evidence envelope legitimately changes because its protection
report embeds the authorized workflow-pin manifest. Do not describe that
envelope change as an artwork, identity or package change. Final CI artifacts
and the PR body provide per-job counts/durations, exact-head links, unchanged
historical invariants and the new envelope hash on both platforms.

This dossier describes acceptance requirements, not a claim that an unobserved
CI run passed. Review the exact-head evidence table in the draft PR before
acceptance. Local development passes supplement but do not replace both OSes.

Pre-commit Windows validation: the actual `ci/phase4.py run` producer passed all
202 exact IDs (zero skips) in 210.57 seconds and reproduced the fixed archive
hash. Existing contract-foundation, Phase 3 isolation/scope and M7 production
guard compatibility checks passed 112 tests with one existing platform skip in
108.01 seconds; all 12 CI gate controls passed. Compilation and whitespace checks
also passed. These development results are not substituted for final-head CI.
After relocating the bridge, the complete final M1 producer passed all **203**
IDs with zero skips in **137.04 seconds**, including the new frozen-source-pin
regression and concurrent rename case. The targeted additive-bridge/read-only/
parent-confinement regressions also passed (3 tests, 18.94 seconds).

## Complete changed-file inventory

Existing files, exactly scoped:

* `.github/workflows/default-poster-validation.yml`: mandatory Phase 4 matrix,
  artifact download and aggregate dependency; old jobs/limits unchanged.
* `ci/validation.py`: require/verify both Phase 4 reports in final acceptance.
* `ci/tests/test_validation.py`: extend existing required-family negative checks.
* `create_defaults/bulk/contracts/activation/protection.py`: exact manifest pin only.
* `create_defaults/bulk/contracts/activation/data/production-pins-v1.json`:
  workflow-only pin advance and explicit maintenance provenance.
* `create_defaults/phase3/tests/test_final_phase3_acceptance.py`: retain the
  original ID/core freeze while admitting only hash-pinned M1 maintenance.
* `create_defaults/phase3/tests/test_isolation_ci.py`: include mandatory Phase 4
  success in the existing Phase 3 failure-control setup.
* `create_defaults/lifecycle/ROADMAP.md`: approved architecture and M1 pending
  review; M2-M7 and later phases remain unstarted; old decision logs retained.

New files:

* `ci/phase4.py`, `ci/phase4-maintenance.json`, `ci/phase4-test-ids.json`.
* `create_defaults/bulk/lifecycle/__init__.py`, `models.py`, `storage.py`, `package_e.py`,
  `README.md`, `schemas/operations-v1.schema.json`.
* `create_defaults/phase4/__init__.py`, `tests/__init__.py`, `tests/samples.py`,
  `tests/canonical-v1.json`, `tests/test_operation_models.py`,
  `tests/test_operation_storage.py`, `tests/test_operation_isolation.py`,
  `tests/test_ci_foundations.py`.
* `create_defaults/lifecycle/PHASE4_M1_IMPLEMENTATION.md` (this dossier).

Ignored local development scripts/logs under `config/phase4-m1` are not PR files.

## M2 handoff and remaining limitations

Stop after M1 for maintainer review; a separate authorization is required for M2.
Next scope is persisted stable identities layered over frozen M2 IDs, semantic
child/overlay lookup, name ownership/retirement, declared prospective adapter
coverage, dependency/output closure and reviewed planner integration. It must
retain all existing approvals, exceptions, exact casing and historical identities
and test unsupported-category fail-closed behavior. The current synthetic schema
must not silently become a real identity registry or authenticated intake path.

M1 has no snapshot executor, identity allocation, actual collision reservation,
evidence authenticity, composition, approvals, local/remote rename/delete,
catalog exporter or automatic orphan collection. Full replay is bounded rather
than an unbounded production index. Interrupted initialization requires manual
inspection/new empty root; existing evidence is never repaired in place.
Absent live authenticated authority/integration and all 22 missing approvals
still block real operations. No M2-M7, Phase 5/6, six deferred Timeline Order
requests, merge, contract activation or artwork publication is authorized here.
