# Phase 4 acceptance and adversarial validation plan

2026-10-23. **Acceptance criteria only; no new tests/operations implemented.**
Planning base: `f05d6af835da3c1536cc116c31dfdd8fda100e42`. Use the
[audit](PHASE4_EXISTING_BEHAVIOUR_AUDIT.md), [proposal](PHASE4_DESIGN_PROPOSAL.md),
[rule matrix](PHASE4_OPERATION_RULES_MATRIX.md) and
[seven milestones](PHASE4_MILESTONE_PLAN.md). Each milestone needs explicit
implementation authorization and exact-head evidence before review. Synthetic
success never constitutes real contract, artwork, operation, activation or
publication approval.

## Current planning PR validation

The only permitted tracked changes are the five new Phase 4 Markdown documents
and current status/decision text in ROADMAP.md. Verify exact diff membership,
valid relative links/anchors, cited Python symbols, consistent approved policy,
all six permanent roadmap phases, preserved historical log entries and unchanged
source/contracts/fonts/assets/translation/workflow/receipt/test selections.
Do not generate a new pytest suite just to assert Markdown phrasing.

Run the existing unchanged bounded Windows/Linux workflow against the exact PR
head. Require all **21 checks**, including **Validation acceptance**; retain
1,671 original pytest IDs, 155 original unittest IDs, 12 CI controls and all 662
Phase 3 focused IDs per platform. Retain justified existing platform skips,
every original non-pytest command and exact canonical vectors. CI generation
tests may render their existing synthetic temporary fixtures; this planning task
does not generate new poster artwork or rerender the historical library.

Download collection/group/focused/coverage/historical artifacts and independently
reconcile actual node IDs, not counts alone. The final PR evidence index must
name one exact commit, all job links/conclusions/runtimes, pass/fail/skip outcomes,
canonical/historical hashes and complete changed-file inventory. The baseline
PR #30 run is not a substitute for this new head's complete CI.

## Future milestone proof obligations

| Proof area | Positive/control | Required adversarial outcome |
| --- | --- | --- |
| T01 — closed operation records (M1) | Canonical round-trip, independent schema/protocol versions, exact before/proposed/parent references, idempotent retry | Unknown fields/versions, duplicate keys, nonfinite/oversized/deep data, substituted schema/kind/pin or nonconsecutive revision rejected; no compatibility boolean grants trust |
| T02 — multi-head CAS (M1/M5) | One transaction advances exact operation, subjects and namespace heads with matching immutable events | Interleaved UPDATE/RENAME or shared-dependency change makes one stale/conflicted; failed CAS advances no pointer, event or accepted member |
| T03 — isolation/reopen (M1/M7) | Explicit empty isolated root; original archive readers reopen exact bytes/history | Foreign cache, symlink/junction, unknown sidecar version, corrupt/missing object or restored stale external head fails closed; no production migration/repair |
| T04 — stable identity (M2/M6) | Existing IDs retained; new category UUID allocated once; semantic family/presentation/size lookup survives rename | Destination-derived remint, duplicate logical allocation, forged assigned ID, recycled tombstone ID or post-seal ID patch rejected |
| T05 — intent/effective bypass (M2/M5) | Real loader/profile/generator/language and final job replay; category-specific controls | Unauthorized font/size/geometry/wash/category, alias/override, raw clamp-to-default, changed normalized job or invented variant/caption type cannot pass |
| T06 — source/D09 (M3/M4) | Real bounded PNG/alpha, exact wash/original preservation, permitted source-preserving/brand-background exception; historical controls untouched | Corrupt/disguised/empty PNG, forged source hash, new use inheriting old exception, arbitrary wash toggle, self-approved background or automatic background removal rejected |
| T07 — white/colour correspondence (M3/M4) | Resolution/AA/padding controls retain measured manual review; complete required roles | Significant silhouette/cutout/branding mismatch unresolved blocks acceptance. No uncalibrated MATCH or broad transparency/warning waiver |
| T08 — complete composition (M3/M4) | Actual final JPEG/PNG includes background/font/caption/geometry/effects/border and owned receipt for each required member | Logo-only view, thumbnail hash, resealed forged preview, missing default/requested context, partial companion or unrelated receipt cannot satisfy complete poster review |
| T09 — translation/fit (M3/M5) | Exact selected-language snapshot/key/template/provenance, existing approved font/fitting; captionless control | Missing/stale English or target key, hidden fallback, changed font/renderer, clipped/long text, unauthorized autoshrink/RTL/new-language package remains blocked; no English-only bypass |
| T10 — selective impact (M2/M5) | Source change fans out to actual poster/white/overlay consumers and transitive/private parents; unaffected control stays reusable | Unknown nodes, missing graph coverage, skipped generated parent, suppressed family fanout or false minimal-impact claim blocks completion |
| T11 — approval freshness/reuse (M4/M5) | Exact unchanged material/owned bytes retain current compatibility; unrelated row/resource change does not stale selected scope | Same-size/mtime source mutation, changed relevant resource with same visible string, new font/native renderer, changed member/variant/exception or replayed approved revision invalidates affected evidence |
| T12 — submitter/maintainer separation (M4) | Explicit complete-group confirm followed by separate attributed maintainer decision; rejection/withdrawal retained | Skipped confirmation, silence, stale preview, same principal self-review, forged reviewer JSON, reused logo-only decision or synthetic-as-real never accepts operation |
| T13 — destination/ownership (M4/M7) | Existing official-English and explicit owned-user mapping simulations, complete exact inventory | Official non-English, missing/expired/revoked/unavailable authority, forged owner/permission/target, incomplete tree or changed baseline remains blocked through M4 and operation layer |
| T14 — prospective adapter limits (M2/M5) | Explicit covered-category and new-overlay adapter tests, original actual historical poster/overlay controls retained | Fake historical record/member, custom manifest routed through unsupported adapter, empty DELETE after-state treated as a valid cohort or caller compatibility flag rejected |
| T15 — rename namespace (M6) | Same ID; independent six name properties; exact old/new mapping and dependent references | Existing target/file-directory/symlink conflict, case/NFC collision, automatic title casing, lost punctuation, fuzzy source fallback or half-renamed pair blocked |
| T16 — case-only move recovery (M6) | Literal Git tree case on Windows/Linux; owned temporary-name journal at each move phase | Crash before/between/after moves, wrong old owner/hash, unowned temp collision and stale CAS cannot overwrite/accept a partial mapping |
| T17 — deletion graph/retention (M6) | Definition retired, immutable tombstone; public bytes retained, complete unaffected graph | Required parent/private intermediate/companion removal, unsupported generated-child exclusion, shared asset cleanup or catalog absence used as public-delete permission rejected |
| T18 — tombstone/name reuse (M6) | Old ID/evidence permanently retained; new identity requires explicit mapping/reuse scope and current inventory | Retained public filename treated as free, old approval inherited by a new brand, alias recycled or history deleted fails |
| T19 — generation interruption (M3/M5/M7) | Owned temporary candidate creation, verified parent before child, exact idempotent retry | Worker crash/time/memory limit, candidate/input change, missing receipt or one failed group member never marks preview/group/operation complete |
| T20 — atomic local commit/recovery (M5/M7) | Read-set/namespace recheck, immutable candidate snapshot and one pointer transaction, reopen verifies chain | Crash after blob but before DB, after decision before apply, concurrent cancellation, corrupt index or partial exporter journal cannot expose partly applied state |
| T21 — cancel/compensate (M6/M7) | Pre-commit cancellation preserves evidence and releases only owned reservations; new operation reverses committed local mapping | Editing accepted history, unowned cleanup, replaying old head or local reversal claimed as remote rollback fails |
| T22 — Phase 5 boundary (all) | Local reports explicitly deny remote authorization; old historical receipts preserved | Attempted writer/activation/controller imports or network writes from pure planning/evaluation fail test guards; operation/submitter/maintainer acceptance never stages, merges, deletes or publishes |

Future test implementations must enumerate exact collected IDs for each family,
positive/unaffected controls, expected failure stage/code and retained evidence.
Use actual reused interfaces and rehashed adversarial values, not only mocks of
successful booleans or tests that repeat schema constants. Changes expected to
fail must fail at the intended boundary, not through unrelated fixture errors.

## Historical acceptance and immutable preservation

Use the existing guarded shared historical fixture in
[bulk/tests/conftest.py](../bulk/tests/conftest.py). The three original consumers
remain together; append projections only after retaining every M2/M5/M6/M7 and
P3 assertion. Do not create a second whole-library capture in a new focused job.
Historical verification prohibits rendering/image decoding/workers/production
state/network writes and compares fresh source/definition/receipt facts to the
accepted baseline. Additional prospective synthetic fixtures are separate and
can neither replace historical records nor create new historical approvals.

| Required invariant | Acceptance |
| --- | --- |
| Adopted output IDs and byte/receipt identities | All 14,079: 9,957 posters + 4,122 overlays, exactly once; no unexplained added/missing/changed record |
| Public/private accounting | 14,077 public references; two private Awards intermediates retain null public destination, never publication members |
| Actual definitions/inputs | 4,372 declarations, 102 families, all real expansions and 2,106 physical inputs; all 299 pinned historical source checks |
| Categories/contracts | All 22 original packages / 278 variants and exact hashes remain; new prospective data is separate, not a mutation of frozen adoption |
| Names and lineage | Literal source/local/public Unicode/case/punctuation, semantic children, aliases, original worker specs/receipts and actual response references unchanged |
| Accepted exceptions | E01–E15, 56 source-preserving uses, 17 normal alpha assets/41 uses, Studio/era/private/separator and accepted warning/font/visual scopes retained exactly |
| Source and nonactivation | All 190 protected production memberships and exact hashes, no unapproved pin refresh; zero real READY/ACTIVE/enforcement/publication |
| Required companions and contexts | Both overlay sizes, applicable white/colour outputs, independent canonical M6/M2 and M5 context checks, original real overlay/poster positive and adversarial controls pass |

Current canonical cross-platform evidence to retain unchanged when no authorized
historical/material change is introduced:

* Ordered historical projection:
  `d5ddf0d646de1968a0054acfda7fa199330848d3d57254f6611fca7ed636e476`.
* Exact names:
  `32d3a7492b56f007ece4ff7fb83fd2a1b7758c117d34bb92ceae5c6281301fdc`.
* Complete historical evidence:
  `cb59e78df25d7c55aa86da562323a19927e516ae1b82742877c7905a0a7f1117`.
* Full Phase 3 five-chain fixture:
  `836afeb792e064e78ff91965b1c47a4feca165aab72655aa0cf61581984cc06b`.

These historical requirements are not a perpetual ban on separately authorized
future additions: a proposed live lifecycle snapshot is baseline plus explicit
operation deltas. Keep the original adoption immutable and reconcile old, new,
retained-public and tombstoned sets in both directions. A future new-item count
cannot overwrite the original 14,079 denominator or its receipt history.

## Resources, deterministic previews and review gates

Preserve the original **512 MiB worker-parent test**, per-worker and total-worker
budgets, metadata/artifact limits, process cleanup and **15-minute per-job CI cap**.
Use existing fixed worker pools, bounded dependency stages and cache/owned byte
verification, not one subprocess per poster. No check is skipped/xfail/disabled,
timeout enlarged or memory assertion weakened to achieve acceptance. If new
focused workloads need deterministic partitioning, measure and review a bounded
mandatory producer/ID reconciliation change explicitly before integration.

Preview determinism tests pin actual source/font/renderer/native encoding context,
explicit base colours, transformations, translation resource and complete membership.
They compare full candidate bytes in the approved environment and separately
record platform/native differences if present. Do not invent a perceptual tolerance
to normalize an unexplained binary difference or regenerate historical artwork.
Worst-case full compositions, long captions, crop/edge cases, separate-white
structural negatives and every output role must appear in future reviewed fixture
coverage. Real-brand calibration labels, held-out splits and explicit exact-policy
approval precede any automatic correspondence or visual approval.

A full operation evidence package must distinguish artifact validity, contract
compatibility/approval, submitter confirmation, independent maintainer decision,
current P3 inspection, operator activation, later staging and merge authority.
Public definition deletion does not mean public artwork deletion. Failure at any
gate withholds the operation while retaining its original candidates/history.

## Final handoff/stop

Future M7 is complete only after all mandatory Windows/Linux jobs and full-ID
coverage succeed at the final head, every required adversarial family passes,
historical and unchanged-control projections agree, restart/recovery is proven,
and the dossier reports complete scope and remaining real blockers. Obtain
maintainer acceptance separately. Do not activate production, approve a contract
package or merge automatically. Phase 5 requires a separately approved authority/
publication integration design; Phase 6 and all six Timeline Order requests remain
untouched. The present task stops at this documentation PR and its actual CI evidence.
