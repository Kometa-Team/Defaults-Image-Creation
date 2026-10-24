# Phase 4 / M4: complete-poster two-stage review

2026-10-23. **M4 IN PROGRESS pending final-head validation and maintainer review.**
M1-M3 are COMPLETE through merged PRs #32-#34. M3 merge and this branch's base:
`e0c715f713a630a59d1e83fa30119ffa3997e1cd`.
Branch: `feat/lifecycle-phase4-m4-two-stage-review`.
M5-M7 and Phases 5-6 remain NOT STARTED. No merge or real operation is authorized.

## Architecture and storage

The approved [P4-D01-D07](PHASE4_DESIGN_PROPOSAL.md),
[operation rules](PHASE4_OPERATION_RULES_MATRIX.md),
[milestones](PHASE4_MILESTONE_PLAN.md) and
[acceptance plan](PHASE4_ACCEPTANCE_PLAN.md) remain unchanged.
M4 adds `bulk/lifecycle/evidence.py`, `review.py`, `review_authority.py` and
`schemas/review-v1.schema.json`. Complete-composition kinds are distinct from
logo previews, historical approvals and contract decisions.

New review indexes use the existing public M1 `SidecarStore`, canonical objects,
transaction and event interfaces in the **same Package E state.sqlite3**. Two
additive tables have immutable triggers and exact namespace verification. Opening
is read-only; creating the review namespace is explicit, inside an existing owned
M1 operation archive. No alternate approval database, mutable decision row,
production cache, catalog writer or operation-state transition is introduced.

Canonical bundle, decision, invalidation and state records use a closed versioned
schema, bounded canonical JSON and immutable content-addressed hashes. Whole-chain
replay checks indexes, consecutive revisions, prior hashes, actor/role/action,
confirmation/decision linkage and original Package E events. Missing/corrupt
objects, partial namespaces and unsupported versions fail closed. Metadata is
bounded to 4,096 index events and 64 MiB; these are resource limits, not visual
tolerances. Writes stage objects first and expose pointers only after transaction
checks. Interrupted writes leave orphan objects, never a complete decision head.

## State machine and independent roles

`PREVIEWS_COMPLETE -> SUBMITTER_CONFIRMED -> MAINTAINER_APPROVED` is the positive
**synthetic** chain. The submitter may explicitly reject or withdraw; the
maintainer may reject only after the exact prior confirmation. Withdrawal after
confirmation or approval invalidates that review while retaining its history.
Rejected, withdrawn, stale or conflicted evidence cannot advance. A stale actual
context can append an immutable diagnostic; concurrent checkpoints report a
conflict without changing the winning head. A material/new operation revision
needs a new complete preview/review; no old decision is retargeted.

`decision()` only creates structurally valid data. A separate exact-decision
authority observation is required. The supported test authority is confined to a
live disposable M3 `CompositionTrial`, has independently supplied submitter and
maintainer membership, and verifies exact decision/context hashes, explicit
expiry and revocation. The maintainer must differ from the submitter. A request
actor, role string, dictionary or provider-shaped callback is not authentication.
Each immutable decision state also pins the independently verified synthetic
grant hash. Reissuing the same decision with a different expiry/context cannot
silently revive or extend its recorded approval.

All records keep `simulation=true`, `record_only=true`, `authenticated=false` and
real artwork/contract/operation/application/READY/ACTIVE/enforcement/publication
flags false. Synthetic approval is not authenticated operational approval.
`require_operational_approval` always fails because no real provider/capture or
contract approvals exist. No OAuth provider, Weblate endpoint, credentials or
live successful authorization response is invented.

## Complete evidence and freshness

Every successful start, confirmation, decision and current reopen runs the
unchanged full M3 `CompositionArchive` verifier. It checks the actual encoded
bytes and decode properties of all required members and both default/requested
views, native plans, durable worker receipts, parent/dependency order, sources,
fonts, exact physical filename case, renderer/native encoding environment,
contract/variant/exception requests, M1 operation/revision and M2 registry/impact.
A thumbnail, logo-only decision, partial companion or rehashed composition
cannot substitute for those bytes. The selected appearance and complete member
set are explicit, while both reviewed views remain pinned.

M4 reuses actual Phase 3 `evidence_consumption.revalidate`, which replays translation
preflight, explicit source reverification, destination inventory/authorization
and M7 inventory blockers. The P3 request payload pins the already existing
M3 composition and exact operation; decisions are appended later, avoiding a
circular hash. P3 subjects must match every M3 identity/output, current category
contract/rules/variant and the exact selected dependency closure. Actual resolved
caption and translation traces must match the native rendered job. Destination
inventory/root must match the M2 namespace. The two established historical M6/M2
and M5 context namespaces are never compared as interchangeable hashes; all
existing dual-context tests remain mandatory and unchanged.

Checks reject missing/expired/revoked attribution or source verification, changed
source/font/renderer/translation/contract/variant/exception/membership/destination,
substituted decisions and stale operation revisions. Integrity-only records do
not create authority. The final successful current replay happens inside the
same Package E write transaction as review-index exposure, excluding concurrent
local M1/M2 writes. This is not a live external verification/consumption protocol;
real authenticated atomicity remains a separately reviewed integration prerequisite.

## Selective invalidation and unchanged decisions

`selective_impact` reuses actual M5 `Index.impact` for direct/transitive consumers
and required companion closure. Shared fonts and source/dependency edges affect
their actual populations; unrelated decisions are not deleted, rewritten or
globally marked stale. Unknown changes and unresolved family provenance block a
complete scope claim. Known generated-child changes invalidate the complete
selected family population. No uncertainty is waived.

P3's enclosing graph hash is observation provenance: an independently re-resolved
unrelated graph node can change without losing a review whose complete selected
closure, P3 binding, M3 context and authority remain valid. The immutable original
observation remains stored. Existing M3 global registry/impact pins are retained;
M4 does not relax them or claim old previews current after a changed pinned
registry. Such cases still require the upstream current compatibility/revalidation
work, not automatic byte reuse or global receipt mutation.

## Tested and explicitly unsupported scope

The positive chain uses an actual full-resolution Genre composition produced by
M3, with default white and requested source-preserving views, exact English
resource bytes, real P3 re-expansion and isolated synthetic source/destination
facts. Existing native fixtures are shared within the bounded pytest session;
all M3 pixel/receipt assertions stay unchanged. Overlay standard/bigger, paired
Network and generated-family evidence is verified through M3 and cannot borrow
another poster's P3 proof.

Investigation found a pre-existing adapter gap: prospective Playlist's approved
fixed layout passes M3's Playlist boundary, while P3's existing generic poster
adapter requires the historical M6 captured-fit shape and reports
`effective_definition_outside_contract`. M4 does **not** waive that failure,
change the fixed layout, fabricate a contract or infer a complete approval from
old logo decisions. This scope remains blocked pending a separately reviewed
compatible adapter. P3's prospective overlay adapter is also absent, and new
paired/family cohorts must satisfy its existing closed companion and expansion
guards. No historical record is fabricated to widen coverage. A complete M3
preview alone does not make these scopes eligible for a decision.

Intentional-background/new transparency exceptions, arbitrary private-parent
source routes, unsupported language/design contracts and real authority retain
their existing blockers. Historical D09 exceptions and the 17 normal alpha assets
are unchanged and are not a rerender corpus.

## Mandatory CI and acceptance evidence

The existing 23-job Windows/Linux workflow and 15-minute caps remain unchanged.
The original and M3 validation plans are preserved in an exact hash chain; M4
adds only `python ci/phase4_review.py run` to the mandatory contracts group.
`ci/phase4-m4-maintenance.json` pins that one-file extension against the M3 merge
and the independent verifier pin is
`a72d6b46c87bc3e2b3a3ef4293e66706553cedf71e014b644165f1f880369a3d`.
All original commands and the two M3 commands must remain exactly present; no
other change is accepted. The four old Phase 3 assertion files and their M3
maintenance hashes remain unchanged. M4 extends explicit foundation/security
selections and adds a disjoint bounded review selection for the more expensive
state/recovery cases. Exact IDs across all producers must equal the entire P4
namespace. No optional job, skip/xfail, deleted test
or `continue-on-error` is introduced. A shared session fixture avoids duplicate
native composition setup. M3's original test bodies are independently compared
to the merged AST, all original M3 IDs remain, and its native implementation and
schema files must match the merge byte hashes. Existing M1/M2 IDs and schema
protections remain mandatory.

The stdlib-only M4 acceptance verifier requires an exact-head proof from each OS,
complete two-stage history, distinct synthetic actors, immutable reopen and all
real authority flags false. Reviewed member hashes must also match the separate
mandatory M3 native pixel producer. Missing, stale, substituted, partial or
synthetic-as-real reports fail mandatory Validation acceptance. Final test counts,
runtimes, exact commit and all job links are indexed in the draft PR after actual
completion; pending checks are not described as success.

Original historical capture remains shared and read-only: 14,079 outputs,
14,077 public references, 22 packages/278 variants, 190 protected sources,
299 adoption pins, historical approvals/exceptions and original receipts remain
unchanged. The 512 MiB worker-parent safeguard and all native worker resource
limits remain intact. No historical image is regenerated or altered.

## M5 handoff and stop

M5 may consume a freshly verified immutable complete-review chain together with
M1/M2/M3/P3 evidence, but must add separately authorized isolated operation commit
semantics and preserve all real blockers. M4 does not accept or execute ADD,
UPDATE, RENAME or DELETE, create an operational registry, activate contracts,
stage/publish images or process the six deferred Timeline Order requests.
No M5 code is included. Stop at the green draft PR for maintainer review; no merge.
