# Phase 4 implementation milestone plan

2026-10-23. **Seven proposed milestones; none authorized or started.**
Source baseline `f05d6af835da3c1536cc116c31dfdd8fda100e42` is the merged Phase 3
implementation. This plan is a documentation deliverable, not permission to edit
production source or process requests. Every implementation milestone starts on
a fresh separately authorized branch/draft PR and stops for review without merge.
See [architecture](PHASE4_DESIGN_PROPOSAL.md), [audit](PHASE4_EXISTING_BEHAVIOUR_AUDIT.md),
[rules](PHASE4_OPERATION_RULES_MATRIX.md), [acceptance](PHASE4_ACCEPTANCE_PLAN.md).

## Dependency order and common gates

M1 → M2 → M3 → M4 → M5 → M6 → M7. Establish immutable ownership and impact first,
then full composition and two-stage review **before** accepting ADD/UPDATE, then
mapping/retirement and integrated recovery. This deliberately does not implement
operations in roadmap enumeration order or leave composition until the end.

Paths below are **proposed files**, not present APIs. Tests should live in
`create_defaults/phase4/tests/` with explicit focused IDs and mandatory Windows/
Linux reporting. Any future CI producer/aggregation extension is reviewed in M1,
never an optional check or silent addition to the frozen original ID baseline.
Preserve all existing test IDs/assertions, 190 source protections and limits;
protect any future narrowly authorized production-source change with exact
provenance instead of silently refreshing a pin. No such change occurs now.

Every milestone must deliver: exact changed-file inventory, declared implemented/
unsupported category/entrypoint coverage, canonical Windows/Linux evidence,
meaningful positive and negative tests, read-only historical invariants and a
draft PR at its final tested head. Actual packages stay unapproved, actual
READY/ACTIVE and publication false. A controlled synthetic test mode cannot name
real packages/principals as an activated production system. Current provider,
contract-approval and authentication gaps block real operation acceptance/apply,
not separately authorized isolated infrastructure testing.

## P4/M1 — strict operation records and isolated state

**Draft PR:** `feat(lifecycle): add isolated versioned operation records and CAS`.

* **Scope / inputs:** Approved Phase 4 model and P4-D01; exact M1 schemas/storage
  and P3 `RequestContext`/archive conventions. Define operation/content revisions,
  evidence event sequence, before/proposed states, typed references, tombstones,
  conflict/cancel status and immutable read/write-set hashes. No executor yet.
* **Proposed files:** `bulk/lifecycle/models.py`, `schemas/operations-v1.schema.json`,
  `storage.py`, `README.md`; focused schema/storage tests and maintained ID file.
  A minimal supported bridge in existing ContractStore may be proposed explicitly
  if required; do not advertise its private helpers as an existing public API.
* **Reuse / genuinely new:** Reuse strict JSON/canonical/fingerprint/Identity,
  isolated root verification, blobs and Package E transaction/events. New typed
  operation indexes, multi-subject/namespace CAS and journal/event semantics are
  necessary; no alternative SQLite/approval store, no M1/P3 schema widening.
* **Security / tests:** Round-trip/hash/idempotence, duplicate/unknown fields,
  version/hash/type substitution, revision replay, lost update, multi-head CAS,
  interrupted blob/transaction writes, foreign roots/links, corrupt restart and
  externally stale heads. Actor strings never authenticate decisions. Imports
  cannot open state, render, network or activate.
* **Historical / completion:** Frozen 14,079 records/14,077 mappings, packages,
  exceptions, old receipts and source pins untouched; mandatory existing CI plus
  new exact focused IDs and vectors pass both OSes. Isolated recovery and atomic
  all-or-none index/event commit demonstrated. No operation execution, approval
  workflow, renderer integration, provider or catalog writer.

## P4/M2 — persisted identities and complete prospective impact

**Draft PR:** `feat(lifecycle): plan stable identity mappings and scoped impact`.

* **Inputs / dependency:** Reviewed M1; P4-D02/D07; frozen M2 identity map, M5
  graph/resolution, M6 packages/rules. Define new assigned UUID IDs and semantic
  keys for family members, presentations and overlay sizes without changing old
  IDs. Produce before/after mapping/graph deltas and read/write/companion closure.
* **Proposed files:** `bulk/lifecycle/identities.py`, `impact.py`, `candidates.py`,
  `coverage.py`; focused identity/impact tests and fixtures. Candidate adapters
  explicitly declare category/generator/overlay support. Do not claim the current
  Playlist-only `graph_for_candidate` or adopted-only M6 `bind` covers new items.
* **Reuse / genuinely new:** Reuse Identity/check_namespace, actual resolve/plan,
  `Snapshot`, `Index.impact`, `compare`, `material_design` and M6 assignments.
  Add persistent semantic lookup and candidate graph assembly with exact scope.
  Design any required existing planner/generator/overlay identity hook explicitly:
  it must resolve IDs before sealing jobs and independently replay at validation.
  Production-pinned changes need separately reviewed exact scope, baseline hashes
  and preservation evidence; no post-hoc job rewrite or new generator engine.
* **Security / tests:** Same ID across display/path/case changes; semantic child
  lookup, duplicate allocation retry, old/new aliases, reserved/tombstoned names,
  unknown inputs, cycles/missing/private parents, shared-source fanout, incomplete
  companions, raw/profile/language/generator bypass and unrelated-row controls.
  Forged historical member/compatibility flags cannot create new-item authority.
* **Historical / completion:** All 14,079 ID/mapping/context/receipt pins identical;
  current M6 22/278 coverage retained. Explicit prospective coverage matrix spans
  all 21 categories, four registered generator kinds and 18 overlay branches;
  unsupported semantics remain blocked until reviewed, never catch-all accepted.
  All read-only impact and identity tests pass; no image generation, production
  catalog mutation, contract modification, operational request or remote action.

## P4/M3 — complete composition candidates and preview evidence

**Draft PR:** `feat(lifecycle): add complete composition preview evidence`.

* **Inputs / dependency:** Reviewed M1/M2, exact effective proposal/impact/membership,
  selected source/font/contract/renderer, owned parent receipts and approved bounded
  fixture scope. This milestone is required before M4/M5, not an indefinite later
  UI enhancement. All real contract/provider blockers remain explicit.
* **Proposed files:** `bulk/lifecycle/composition.py`, `previews.py`, additive
  `schemas/composition-v1.schema.json`; isolated full-poster/overlay fixture tests
  and complete canonical member manifests. No actual existing artwork is used as
  a rerender/cleanup corpus; synthetic generation needs that milestone's explicit
  authorization and owned temporary roots.
* **Reuse / genuinely new:** Existing `Planner`, `generation.generate`,
  `tasks_from_manifest`, `PersistentWorkers`, `workers.compose`, `create_poster`,
  `overlays.render`, PNG/wash/LogoArchive evidence and owned-receipt checks. New
  orchestration binds complete encoded candidates to operation/member context and
  default/requested full views; it does not copy compositing/text algorithms.
* **Security / tests:** Full background/gradient/font/text/geometry/effects/border,
  default wash versus source-preserving exception, intentional blocked default,
  exact alpha/source preservation, standard/bigger and white/colour completeness,
  parent-before-child, missing/changed receipt, candidate drift, random-colour
  omission rejection, font/native renderer drift, long text/clip/glyph blockers,
  interrupted generation and immutable reopen. Thumbnail/forged logo preview
  cannot satisfy complete-poster evidence. Existing resource limits apply.
* **Historical / completion:** No historical rendering or output changes; original
  generators/renderer hashes and all 190 protections remain unchanged unless a
  separately approved narrow prerequisite says otherwise. Final encoded bytes
  and receipts reproduce in the pinned environment, both OSes pass and every
  required preview member is accounted for. No human approval, real intake,
  production write, new font/algorithm/tolerance or publication integration.

## P4/M4 — full composition two-stage review and current evidence

**Draft PR:** `feat(lifecycle): bind complete previews to two-stage operation review`.

* **Inputs / dependency:** Reviewed M1–M3, complete preview contexts and approved
  D09 exception semantics; existing M1 attribution, M4 logo decisions, P3 M2/M3/M4
  evidence and M7 inspection. Requires the acyclic review/decision model from the
  proposal. New complete-composition kinds stay distinct from logo-only records.
* **Proposed files:** `bulk/lifecycle/review.py`, `evidence.py`, additive review
  schema and operation-sidecar indexes; role/replay/composition-state tests.
* **Reuse / genuinely new:** Use Reviews owned-preview validation/group membership,
  LogoArchive confirm/maintain semantics, RegistrySnapshot/TrustedDecision and P3
  explicit replay/archive. New semantic verifier checks full context, confirmed
  membership, exception outcome and operation revision; it does not create a new
  approval database or claim existing opaque P3 references authenticate a decision.
  Additive prospective-overlay evidence integration is proposed explicitly if
  required; current `OverlayRequest` remains historical-only until then.
* **Security / tests:** Explicit confirm/reject/withdraw, distinct authenticated
  submitter/maintainer roles, no skipped confirmation, incomplete members, stale
  source/context, forged/rehashed preview/decision, replayed revision, changed
  contract/variant/destination, absent/expired/revoked authority, synthetic-as-real,
  P3 dual namespace checks and unchanged M7 blockers. No live provider invented.
* **Historical / completion:** Existing artifact/exception decisions unchanged;
  unrelated reviews retain valid scope, changed members stale selectively. Tests
  demonstrate complete synthetic chain and genuine unavailable-authority failure;
  real approvals/READY/ACTIVE/publication remain false. Both OSes pass. No ADD/
  UPDATE execution, authenticated web service, real authority extension or staging.

## P4/M5 — isolated ADD/UPDATE planning and commit semantics

**Draft PR:** `feat(lifecycle): add isolated ADD and UPDATE transactions`.

* **Inputs / dependency:** Reviewed M1–M4, approved operation rules, complete
  membership/impact and current evidence. Current real contract/authority gaps
  block actual operation acceptance; synthetic tests must not bypass that gate.
* **Proposed files:** `bulk/lifecycle/operations.py`, `apply.py`, `recovery.py` and
  ADD/UPDATE concurrency/fault tests. Deliver immutable local proposed-definition
  snapshot commits, not automatic production YAML edits. Any future production
  exporter/hook requires an explicit later authorization and preservation review.
* **Reuse / genuinely new:** Existing actual loader/expander/planner/M6 raw and
  normalized checks, impact graph, owned workers/cache, full reviews and Package E
  multi-head transaction. New coordinator joins them under exact operation heads
  and all-or-none companion acceptance. Add required prospective adapters only
  with explicit contract/category/overlay coverage; never fabricate M2 records.
* **Security / tests:** Valid synthetic ADD and minimal UPDATE; existing key/type
  selection; shared-source/white/overlay/dependent impact; unchanged artifact and
  approval reuse proof; authority failure; unauthorized style/type; foreign source;
  two concurrent operations; partial member generation; crash at every pointer/
  blob/receipt boundary; changed head after confirmation; new source under old name.
* **Historical / completion:** Read-only unchanged control set proves no unwanted
  render/review invalidation; all original 14,079/14,077/190/22/278 invariants hold.
  Successful isolated snapshot visibility is atomic; blocked/cancelled work cannot
  appear committed, and restart preserves old evidence. No production application,
  new language/key/contract, real active item or Phase 5 transport/publication.

## P4/M6 — identity-preserving RENAME and retained-artwork DELETE

**Draft PR:** `feat(lifecycle): add isolated rename and retirement semantics`.

* **Inputs / dependency:** Reviewed M1–M5, stable semantic identity integration,
  P4-D05/D06, before/after graphs, authoritative old/new definitions/mappings and
  complete current namespace. Public retention is already confirmed policy.
* **Proposed files:** `bulk/lifecycle/mappings.py`, `retirement.py`, journal/recovery
  extension and Windows/Linux case/Unicode/lineage/deletion tests.
* **Reuse / genuinely new:** Existing Identity/path checks, dependency compare,
  reservations/multi-head CAS and immutable receipt/provenance references. New
  mapping/tombstone and compensating-operation records preserve permanent IDs;
  journaled owned case-only local moves are new, not the historical transport
  case-rename permission. No remote writer/deletion API.
* **Security / tests:** Independent display/text/source/local/public/alias changes;
  same generated/overlay IDs after rename; case-only two-step crash/restart; exact
  NFC/punctuation/collision rejection; occupied public target; concurrent UPDATE/
  RENAME; dependent parent/required companion deletion; private intermediate and
  family exclusion; old-name reuse and stale approved revision; cancel before and
  compensate after local commit; preserved original public bytes/history.
* **Historical / completion:** Default definition DELETE leaves public mappings/
  artwork occupied and receipts intact. No child is orphaned or recreated by an
  unsupported family removal; partial rename groups block. Both OSes pass including
  literal Git case checks. No physical asset cleanup, remote rename/delete, ID or
  approval recycling, public deletion execution or legacy receipt rewrite.

## P4/M7 — full regression, recovery acceptance and Phase 5 handoff

**Draft PR:** `test(lifecycle): verify operation recovery and historical acceptance`.

* **Inputs / dependency:** Reviewed M1–M6 and approved acceptance protocol; exact
  final code/data/registry/fixture/operation-head pins. Do not extend scope to live
  authority or use a CI pass to activate any operation.
* **Proposed files:** `create_defaults/phase4/tests/` integration/security matrix
  and evidence exports; `lifecycle/PHASE4_ACCEPTANCE_REPORT.md`, implementation
  dossier and Phase 5 prerequisite checklist. Later names are planning targets.
* **Reuse / genuinely new:** Reuse the single guarded historical capture and all
  M1–M7/P3 checks, exact-ID mandatory CI reconciliation, canonical fixtures and
  actual owned archive/replay. New integrated operation fault/negative matrix and
  complete before/after/retained-output reconciliation are required; no duplicate
  14,079-output fixtures or second acceptance framework.
* **Security / tests:** Every scenario in the [acceptance plan](PHASE4_ACCEPTANCE_PLAN.md),
  immutable reopen/export, interleaved operations, crash/cancel/compensating recovery,
  forged/synthetic authority and attempted Phase 5 writer/activation imports.
* **Historical / completion:** All required Windows/Linux groups and mandatory
  Validation acceptance green at exact final head; full original/additive node
  IDs and non-pytest gates reconciled; no unexplained historical/receipt/name/
  exception differences; 512 MiB parent and 15-minute job caps unchanged. Complete
  unresolved operational blocker inventory remains factual. Stop for maintainer
  acceptance, not automatic COMPLETE/merge/production activation. Phases 5–6 and
  the six Timeline Order requests remain untouched.

## Decisions before implementation

Review P4-D01–D07, especially supported prospective adapters and production-source
hook boundaries, isolated snapshot atomicity, full composition membership and
name/tombstone retention. Then explicitly authorize **M1 alone** with its exact
base/scope, including any necessary mandatory CI producer integration. Do not
start M1 because this planning PR is green or merged. Contract packages, live
authority providers, actual artifact decisions, production activation and Phase 5
publishing require separate, specific authorization.
