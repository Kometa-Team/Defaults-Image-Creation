# Phase 4 existing behaviour and gap audit

2026-10-23. **Discovery and planning only.** Source: current `main` at
`f05d6af835da3c1536cc116c31dfdd8fda100e42`, verified merge of
[Phase 3 PR #30](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/30).
Its tree equals tested head `e80c47012b82f134c91c30b58fd2dc6a6acd967d`;
[run 39951809741](https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/39951809741)
passed all 21 checks. That is baseline evidence, not this planning PR's CI.
Phase 3 implementation is COMPLETE; operational authority remains BLOCKED.
Phase 4 planning is IN PROGRESS; implementation is NOT STARTED.

Read alongside [design](PHASE4_DESIGN_PROPOSAL.md),
[operation rules](PHASE4_OPERATION_RULES_MATRIX.md),
[milestones](PHASE4_MILESTONE_PLAN.md), [acceptance](PHASE4_ACCEPTANCE_PLAN.md)
and the [roadmap](ROADMAP.md). Historical milestone dossiers retain their original
pending/not-started language as dated checkpoints, including the pre-merge
[handoff](PHASE4_HANDOFF.md). They do not override the verified current baseline.

## Evidence and classification

EXISTING means the stated behaviour is implemented, not operationally approved.
REUSABLE means a working primitive can support the new operation but supplies no
lifecycle orchestration. PARTIAL identifies a concrete scope/interface limit.
MISSING means the required operation or record is absent. BLOCKED means an
independent authority or approval prerequisite is unavailable. A row may identify
a reusable part and an explicitly missing integration; it does not imply that a
proposed method already exists.

| ID / capability | Status | Actual source and callable evidence | Gap / Phase 4 consequence |
| --- | --- | --- | --- |
| A01 — existing identity facts | EXISTING | [models.py](../bulk/contracts/models.py): `Identity`, `require_new_names`, `check_namespace`; [M2 mapping](../bulk/contracts/adoption/baseline/stable-mapping-v1.json.gz) | 14,079 adopted IDs and independent literal names are pinned. No lifecycle allocator or mutable live identity registry exists. Never remint adopted IDs. |
| A02 — generated/overlay identities | PARTIAL | [generators.py](../bulk/generators.py): `poster_id`, `_child`; [overlays.py](../bulk/overlays.py): `plan`; [overlay_definitions.py](../bulk/overlay_definitions.py): `plan` | Child IDs hash output paths; both overlay planners derive job IDs from destination paths. A stable rename requires a persisted semantic-member lookup and a reviewed planner integration; storing an `Identity` alone cannot fix these callers. |
| A03 — authoritative definitions/names | REUSABLE | [definitions.py](../bulk/definitions.py): `load_definitions`, `Definition.for_language`; [resolution.py](../bulk/contracts/expanded/resolution.py): `resolve`, `Resolution.verify_current`, `plan` | Real profile/generator/language expansion, exact file pins and parent checks exist. They do not perform ADD/UPDATE/RENAME/DELETE transactions. New filename spelling must be confirmed in authoritative definition/mapping revisions, not inferred from display text. |
| A04 — category contracts | EXISTING | [release.py](../bulk/contracts/categories/release.py): `Implementation.load`, `select`, `authorize`; [validation.py](../bulk/contracts/categories/validation.py): `Assignment`, `check_job`, `check_membership`, `validate_selection` | 22 packages / 278 variants, English scope, protected raw/effective rules and required roles exist. All exact package approvals remain missing. Arbitrary new captions/designs are not enabled by an ADD. |
| A05 — prospective graph coverage | PARTIAL | [candidate.py](../bulk/contracts/expanded/candidate.py): `graph_for_candidate`; [dependencies.py](../bulk/contracts/categories/dependencies.py): `bind`, `material_design`, `compare_implementations` | Candidate adapter is Playlist-only and rejects generated parents; M6 binding requires exact adopted members. Neither is a generic all-category/new-overlay lifecycle graph builder. Reuse graph primitives; add explicit scoped candidate adapters without fabricating historical members. |
| A06 — complete poster compositor | EXISTING | [create_poster.py](../create_poster.py): `PosterOptions`, `render_poster`, `create_poster` | Actual 2000 x 3000 RGB JPEG composition: base/gradient, alpha-preserving wash, resize/offset, caption, border and legacy JPEG stages. `create_poster` writes exclusively; raw renderer can choose a random base if omitted. Lifecycle previews must use deterministic validated plans with explicit assigned colours, not unconstrained renderer defaults. |
| A07 — overlay composition | REUSABLE | [overlays.py](../bulk/overlays.py): `TRANSFORM`, `render`, `plan`; [overlay_definitions.py](../bulk/overlay_definitions.py): `plan`, `generate` | Existing and explicit-new-source render paths already exist. Standard 285 x 85 and bigger 440 x 100 are fit bounds, not padded canvases. Preserve trim, sRGB, alpha, resampling, encoding and exact source basename; no poster wash. Explicit-new definitions do not establish category, mapping or publication approval. |
| A08 — new-overlay validation boundary | PARTIAL | [category validation](../bulk/contracts/categories/validation.py): `validate_overlays`; [P3 adapters](../bulk/contracts/translation_preflight/adapters.py): `OverlayRequest` | M6 replays the existing catalog planner; P3 accepts an exact historical M2 overlay record/member. A custom new overlay plan cannot be passed through those APIs as if historical. A separately reviewed prospective adapter is required; do not mint fake `HistoricalOutput` evidence. |
| A09 — logo integrity/treatments | REUSABLE | [assets.py](../bulk/contracts/logos/assets.py): `png_integrity`, `inspect_png`; [wash.py](../bulk/contracts/logos/wash.py): `white_wash`; [workflow.py](../bulk/contracts/logos/workflow.py): `Selection`, `prepare`, `verify` | PNG integrity/alpha/quality, original preservation, D09 treatments and intentional-background requests exist. Existing 17 accepted alpha/background assets remain normal at their exact 41 historical uses. No cleanup or inherited exemption for changed bytes/new use. |
| A10 — logo previews and correspondence | PARTIAL | [logo workflow](../bulk/contracts/logos/workflow.py): `prepare`, `approvable`, `confirm_record`, `decision_record`; [comparison.py](../bulk/contracts/logos/comparison.py): `compare` | Poster previews are 256-pixel logo-only views, explicitly incomplete; overlay views use the real transform. No automatic MATCH policy is approved. Existing preview record/receipt kinds cannot be relabeled as full-poster approval. |
| A11 — full generated-artifact review | REUSABLE | [generation.py](../bulk/generation.py): `generate`; [review.py](../bulk/review.py): `Reviews.attach`, `batch`, `decide`, `approve_group`; [operations.py](../bulk/operations.py): `verified_receipts`, `validate_generation`, `preview` | Full composed outputs and owned-receipt attachment/byte comparison already work. Development CLI reviewer attribution is not authentication. Missing integration is exact operation revision + complete composition manifest + two-stage decision + Phase 3/M7 gates; no second renderer or second approval database is needed. |
| A12 — required variants | REUSABLE | [category validation](../bulk/contracts/categories/validation.py): `check_membership`; [policy.py](../bulk/contracts/categories/policy.py): `PAIRED`, `companions`; [logo workflow](../bulk/contracts/logos/workflow.py): `_requirements` | Applicable white/colour pairs and both overlay sizes are checked. Their grouping is not identical to render jobs, transport batches or PRs. Cross-output lifecycle completion and atomic acceptance remain to be added. |
| A13 — text/translation/fitting | REUSABLE | [translations.py](../bulk/translations.py): `Translations`; [preflight.py](../bulk/preflight.py): `effective_language`, `_metrics`, `preflight`; [poster_text.py](../poster_text.py): `load_layout`; [P3 engine](../bulk/contracts/translation_preflight/engine.py): `evaluate`, `revalidate` | Required keys/templates, source/content provenance, glyphs/layout and explicit currentness are checked. Captured fit is not permission to shrink; RTL/new-language contracts are not enabled. Legacy partial generation defaults are not a mandatory Phase 3 production gate. |
| A14 — selective dependency impact | EXISTING | [graph.py](../bulk/contracts/expanded/graph.py): `Snapshot`, `Index.material_context`, `Index.impact`, `compare`; [historical.py](../bulk/contracts/expanded/historical.py): `build` | Full source/font/caption/background/transform/parent/family/exception graph and scoped review invalidation exist. Unknown dependencies and family provenance needing per-child comparison remain unresolved. Reports do not execute regeneration or mutate approvals. |
| A15 — immutable revisions/storage | REUSABLE | [state.py](../bulk/state.py): `Store.transaction`, `event`; [ContractStore](../bulk/contracts/state.py): `read_object`, `append`, `read_record`; [P3 storage](../bulk/contracts/evidence_consumption/storage.py): `Archive.append`, `history` | Canonical immutable blobs, revision CAS, transactional indexes/events and restart checks exist. `ContractStore.append` accepts closed M1 `Record` types, not arbitrary lifecycle JSON. P3 `RequestContext` is evidence context, not a lifecycle transaction. New typed sidecars must compose these primitives explicitly. |
| A16 — decision/exception provenance | REUSABLE | [registry.py](../bulk/contracts/registry.py): `RegistrySnapshot.load`, `TrustedDecision`; [logo storage](../bulk/contracts/logos/storage.py): `LogoArchive.submit`, `maintain`, `load` | Existing exact-attribution, submitter/maintainer separation, immutable decisions and source/context invalidation are reusable. No public authenticated decision-capture service exists. Old artifact approval is not contract approval or a new-operation grant. |
| A17 — workers/local staging/recovery | REUSABLE | [workers.py](../bulk/workers.py): `RenderTask.spec`, `tasks_from_manifest`, `compose`, `PersistentWorkers.run`; [workspaces.py](../bulk/workspaces.py): `Workspaces`; [state.py](../bulk/state.py): `recover` | Bounded shared pool, input/runtime rechecks, owned staging, receipts/cache/dedup and interrupted-job recovery exist. Local worker success does not commit a lifecycle group or approve companions. Use isolated per-operation Config roots; no default production workspace. |
| A18 — remote inventory/collisions | REUSABLE | [remote.py](../bulk/remote.py): `ReadOnlyGitHub`, `RemoteInventory`; [P3 inventory](../bulk/contracts/destination_preflight/inventory.py); [P3 engine](../bulk/contracts/destination_preflight/engine.py): `evaluate`, `revalidate` | Existing GET-only observations and strict commit/tree inventory are reusable. Cache TTL in old inventory is not P3-D01 reverification or authenticated ownership. Full current target inventory is still required before later remote changes. |
| A19 — current evidence consumption | EXISTING | [M4 engine](../bulk/contracts/evidence_consumption/engine.py): `consume`, `revalidate`, `_graph_scope`; [models](../bulk/contracts/evidence_consumption/models.py): `RequestContext` | Real M2/M3 replay, selected graph/material/member scope, independent M6/M2 and M5 overlay contexts and M7 inspection are implemented. All operational flags stay false. No generic empty/deleted/new-overlay operation consumer exists. |
| A20 — draft transport/public receipts | PARTIAL | [operator_publication.py](../bulk/operator_publication.py): `authorize`, `stage`, `draft`; [library_stage.py](../bulk/library_stage.py): `gate`, `run`, `RemoteBytes`, `final_remote_diff`; [adoption inventory](../bulk/contracts/adoption/inventory.py): `discover` | Resumable non-force Git staging, actual response hashes, final remote diff and immutable historical receipts exist. Writer targets are fixed to Default-Images/master; rename support is narrowly approved overlay case correction. They are not generic user-repository, arbitrary rename or delete writers. Integration belongs to Phase 5. |
| A21 — lifecycle operation semantics | MISSING | [M1 record schema](../bulk/contracts/schemas/record-v1.schema.json), [P3 context schema](../bulk/contracts/evidence_consumption/evidence-v1.schema.json), [handoff](PHASE4_HANDOFF.md) | No ADD/UPDATE/RENAME/DELETE request schema, multi-subject transaction/reservation, tombstone, source-definition revision writer or operation recovery journal is implemented. Add isolated versioned operation sidecars, not replacement generation/review/publication frameworks. |
| A22 — operational authority | BLOCKED | [authority.py](../bulk/contracts/language_policy/authority.py): `AuthorityStatus`, `AuthorityResult`, `UnavailableAuthority`; [readiness.py](../bulk/contracts/activation/readiness.py): `inventory`; [controller.py](../bulk/contracts/activation/controller.py): `UnavailableAuthority` | No real positive ownership result or live source verifier; no authenticated current operation/evidence head or approved production integration. All 22 package approvals are missing, zero actual READY/ACTIVE. Simulated success and merges cannot fill these gaps. |

## Preserved evidence and category distinctions

The [accepted discovery](PHASE1_DISCOVERY.md), [category matrix](CATEGORY_RULES_MATRIX.md),
[exceptions E01–E15](EXCEPTIONS_REGISTER.md), [D01–D09 architecture](PHASE2_DESIGN_PROPOSAL.md),
[M1 foundations](../bulk/contracts/README.md), Phase 2 [M2](PHASE2_M2_IMPLEMENTATION.md),
[M3](PHASE2_M3_IMPLEMENTATION.md), [M4](PHASE2_M4_IMPLEMENTATION.md),
[M5](PHASE2_M5_IMPLEMENTATION.md), [M6](PHASE2_M6_IMPLEMENTATION.md),
[M7](PHASE2_M7_IMPLEMENTATION.md), and Phase 3 [M1](PHASE3_M1_IMPLEMENTATION.md),
[M2](PHASE3_M2_IMPLEMENTATION.md), [M3](PHASE3_M3_IMPLEMENTATION.md),
[M4](PHASE3_M4_IMPLEMENTATION.md), [M5](PHASE3_M5_IMPLEMENTATION.md)
and [acceptance](PHASE3_ACCEPTANCE_REPORT.md) were used as evidence, with current
source resolving dated implementation claims.

The adopted inventory remains 4,372 declarations / 102 families, 9,957 posters
(9,955 public, two private Awards intermediates), 4,122 overlays / 18 source
branches, **14,079 outputs / 14,077 public references**. There are 22 contract
packages, 278 variants, 190 protected production files, 299 historical source
pins and 2,106 physical inputs. Original public logo and separator base trees
outside generated outputs are not missing outputs or deletion candidates.

Playlist, Franchise, Genre, Seasonal and Universe retain WHITE_ONLY defaults
with individual SOURCE_PRESERVING exceptions; Studio remains SOURCE_PRESERVING.
Applicable Chart/Country/Network/Streaming pairs remain BOTH_REQUIRED. Overlays
preserve each existing source branch and both sizes, independently of poster
wash. Year/Decade era typography, Awards/private compositions, rating/text/icon
variants and separator families remain distinct. Merging Phase 3 did not approve
new contracts, universal fitting/visual tolerances or background cleanup.

This audit performs source/metadata inspection only. The planning PR's unchanged
bounded CI supplies fresh read-only historical verification; no separate full
capture, library regeneration, remote artwork write or visual re-review is run.
