# Phase 5 M1: existing review and publication behaviour

2026-10-26. Planning only. Verified remote `main`:
`ef3b2713cf5dcab9b92395321c6be3fdf1efdbce`, also the actual merge commit of
[Phase 4 M7 PR #43](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/43).
`git fetch origin main`, the remote ref and PR merge metadata agreed before
creating `feat/lifecycle-phase5-m1-planning` in a clean separate worktree.
Unrelated changes in the original worktree are preserved and excluded.

Phase 4 M1–M7 implementation and technical acceptance are merged. Its isolated
capabilities are not production authorities. Earlier milestone documents retain
their historical pending statuses; [ROADMAP](ROADMAP.md) supplies current status.
M1 adds five planning documents and updates only current roadmap/prerequisites.
No runtime, provider, approval, activation, production YAML or artwork changes.

## Callable evidence and reuse assessment

Paths below are existing APIs at the verified baseline, not proposed interfaces.
“Reusable” means the named mechanism can be retained with its current boundary;
it never means its caller-supplied data has become authenticated.

| Path / existing function or type | Actual authority and behaviour | Limitation / safe reuse |
| --- | --- | --- |
| [categories/release.py](../bulk/contracts/categories/release.py): `Implementation.load/select`, `authorize` | Exact release, contract and rules pins; `authorize` requires external M5 authority and unchanged registry selection | Reuse selection. The implementation inventory is not the approval registry; all 22 exact approvals are missing. |
| [registry.py](../bulk/contracts/registry.py): `RegistrySnapshot.load/select`, `TrustedDecision` | Strict canonical package/version/hash/variant and exact approval provenance against a trusted-caller map; maintainer allowlist from Package E | Reuse structural checks and attribution boundary. A reviewer string/allowlist/hash is not authenticated identity or current role/revocation. |
| [activation/controller.py](../bulk/contracts/activation/controller.py): `Controller.transition/inspect/reconcile/rollback`, `UnavailableAuthority` | Exact revision/CAS, gate and independent operator decision; default authority always rejects | Reuse state semantics, not a production activation service. Only concrete synthetic harness accepted; even simulated ACTIVE has enforcement/publication false. |
| [definitions.py](../bulk/definitions.py): `Definition.create`, `load_definitions` | Closed schema, strict YAML, exact IDs, inherited profiles and controlled fields | Reuse parser. No lifecycle production editor/exporter; no write authority is supplied by successful parsing. |
| [catalog.py](../bulk/catalog.py): `load_catalog`; [expanded/resolution.py](../bulk/contracts/expanded/resolution.py): `resolve`, `Resolution.verify_current`, `plan` | Existing catalogs/profiles, source file fingerprints, generator expansion and dependency replay | Reuse current-source read/replay. No round-trip catalog writer, source-repository CAS or authorized production patch consumer. |
| [lifecycle/candidates.py](../bulk/lifecycle/candidates.py): `StablePlanner.expand`, `resolve_stable`, `poster_candidate`, `playlist_mapping` | Registry assigns persisted semantic IDs before original job sealing; exact source/name/caption routes are checked | Reuse prospective validation. Read-only and conditional, not general operational ADD/UPDATE support; cannot replace arbitrary YAML fields or post-seal jobs. |
| [translation_preflight/sources.py](../bulk/contracts/translation_preflight/sources.py): `SnapshotInput`, `SourceVerifier`, `currentness` | Repository/commit/tree/blob and exact resource/key/value binding; explicit verification context | Reuse content/provenance checks. Default `UnavailableSourceVerifier` supplies no currentness; local integrity and TTL alone do not prove current authorized selection. |
| [language_policy/authority.py](../bulk/contracts/language_policy/authority.py): `AuthorityContext`, `SourceVerificationContext`, `AuthorityResult`, `UnavailableAuthority` | Trusted-caller type boundary with unavailable/unverifiable/expired/revoked/synthetic-only statuses | No real positive status exists; `readiness_authorized` and `publication_authorized` always false. A production provider needs explicit reviewed interface work, not a permissive injected callback. |
| [destination_preflight/authority.py](../bulk/contracts/destination_preflight/authority.py): `DestinationAuthority`, `DestinationFacts`, `consume` | Independently observed numeric repository/owner/principal IDs, exact inventory/cohort/branch/root, logical permissions, expiry/revocation | Only synthetic-positive technical path. Current user-target check requires user ownership; organization delegation is not silently supported. Logical `contents:*` labels are not GitHub OAuth scopes. |
| [destination_preflight/inventory.py](../bulk/contracts/destination_preflight/inventory.py): `validate`, `expand`; [paths.py](../bulk/contracts/destination_preflight/paths.py) | Bounded complete tree linkage, exact spelling plus collision keys, branch/root/path checks | Reuse integrity/path checks. Caller inventory JSON is not proof of a live remote head or ownership. Missing/truncated inventories stay unknown. |
| [remote.py](../bulk/remote.py): `ReadOnlyGitHub.head/tree/blob`, `RemoteInventory.refresh/snapshot` | GET-only GitHub source, explicit credentials, verified commit/tree IDs, complete-tree helper, cached observations/failures | Reuse observation primitives. Cached `freshness` uses TTL; not P3 consumption authority. No authenticated role provider or atomic source/destination lock. |
| [lifecycle/composition.py](../bulk/lifecycle/composition.py): `compose`, `render_view`, `owned_receipt`; [previews.py](../bulk/lifecycle/previews.py): `CompositionTrial`, `CompositionArchive.verify/gallery` | Actual native encoded complete views, private owned worker receipts, immutable byte objects and exact context | Reuse native renderer/evidence logic. Trial is explicitly disposable/offline; its lifetime capability cannot be promoted to production trust. |
| [lifecycle/review.py](../bulk/lifecycle/review.py): `decision`, `ReviewArchive`; [review_authority.py](../bulk/lifecycle/review_authority.py): `verify_authority`, `require_operational_approval` | Explicit submitter confirmation then distinct maintainer decision, exact bundle/context/previous-state hashes, CAS, expiry and revocation in a synthetic lifetime | Reuse two-stage semantics and immutable history. `decision` constructs data only. Real authority always unavailable; archived synthetic grants cannot authenticate a restart. |
| [review.py](../bulk/review.py): `Reviews.decide/approve_group`; [operator_publication.py](../bulk/operator_publication.py): `approve` | Existing version-bound review and explicit operator decisions with exact membership/policy hashes | Development/operator attribution, not a live identity provider. `Reviews` advertises development-only attribution; CLI reviewer names and sealed receipts cannot be accepted as production role evidence. |
| [evidence_consumption/engine.py](../bulk/contracts/evidence_consumption/engine.py): `consume`, `revalidate` | Replays exact subject, graph, complete member set, category, translation and destination evidence at consumption | Reuse validators and explicit historical context namespaces. No real authority result, operational local commit or remote transport binding. |
| [lifecycle/apply.py](../bulk/lifecycle/apply.py): `commit_synthetic`, `commit_operational`; [mappings.py](../bulk/lifecycle/mappings.py): `prepare`, `commit_synthetic`, `commit_operational` | M1/Package E transaction atomically binds scoped local heads/events/snapshots; operational entry points reject | Reuse transaction/journal design. Positive executor is assigned English Genre single-logo synthetic subset, not production or all Genre variants. No local SQL transaction can atomically commit a GitHub push. |
| [mappings.py](../bulk/lifecycle/mappings.py): `require_m5_compatible`, `recover`, `recover_local`; [retirement.py](../bulk/lifecycle/retirement.py) | RENAME preserves permanent identity and aliases; DELETE retires definitions while retaining artwork, references, public reservations and tombstones | Reuse retention/conflict policy. Old M5 UPDATE rejects touched identities or asset dependencies with `m6_mapping_requires_current_adapter` / `m6_dependency_requires_current_adapter`; do not remove these guards. |
| [library_publication.py](../bulk/library_publication.py): `publication_manifest`, `batch_plan`, `validate_paths`, `verify_published` | Exact candidate membership, approved policy/evidence, equal-hash synchronization, bounded technical batches | Reuse manifest/batching/verification. Historical migration membership is not lifecycle approval, complete-review authority or general deletion authorization. |
| [operator_publication.py](../bulk/operator_publication.py): `prepare`, `approve`, `authorize`, `gate`, `stage`, `draft` | Requires exact candidates/policy and explicit additions/limited renames, fixed official target, draft-only branch, complete remote proof before PR | Reuse reviewed transport integration pattern. Can withhold invalid rows; lifecycle wrapper must block incomplete logical operations before calling it. Current authorization is legacy operator attribution and fixed destination, not P3/lifecycle trust. |
| [library_stage.py](../bulk/library_stage.py): `gate`, `run`, `remote_head`, `verify_diff`, `RemoteBytes`, `final_remote_diff` | Fixed `Kometa-Team/Default-Images`, `master` baseline, non-force draft pushes, exact ancestry/owned journal, ambiguous-push reconciliation, actual response SHA-256s and complete tree audit | Reuse this publisher, not a second GitHub writer. No generic user destination, source YAML transaction, current role/revocation gate or cross-repository atomic commit. Final recursive tree truncation blocks rather than claiming completeness. |
| [library_transport.py](../bulk/library_transport.py): `run`, `verify_batch` | Offline local bare-remote transport/recovery exercise, exact Git objects, bounded batches/packs | Reuse isolated fault tests only. Module explicitly prohibits network remotes; it is not the production publisher. |
| [state.py](../bulk/state.py): `Store`; [lifecycle/package_e.py](../bulk/lifecycle/package_e.py): `SidecarStore`; [recovery.py](../bulk/lifecycle/recovery.py): `recover` | Existing Package E SQLite/events, immutable sidecars/objects, scoped CAS and read-only consistency replay | Reuse storage with separately reviewed additive schema if needed. No new database or automatic migration/cleanup. Cold integrity replay cannot resurrect an external permission grant. |

## Concrete transport limits that the design must preserve

`library_stage.run` checks `master` before staging/push, but that observation does
not lock `master` until the write. Normal Git push prevents non-fast-forward
branch overwrite; it does not make all source/role/destination observations one
atomic operation. A multi-batch draft branch can temporarily hold an incomplete
prefix. `operator_publication.draft` refuses a PR until all batches and complete
remote bytes/tree reconcile, and resumes by discovering an existing exact draft.
Neither function merges production `master`.

`operator_publication.prepare` records withheld rows and omits synchronized bytes.
Those are useful migration primitives, but a future lifecycle bridge must prove
complete logical membership separately. Equal candidate/public SHA-256 may skip
upload; it cannot skip a mapping/catalog/review decision. Binary-different
`renderer_equivalent` members remain upload candidates under exact approval.

The operator path permits exact additions and only explicitly approved overlay
source-basename case corrections. It does not permit general artwork deletion,
arbitrary rename or arbitrary user repositories. Broadening those gates is
separate protected-runtime work. Definition DELETE is not a request to delete
its public image; general RENAME must keep the former public mapping reserved.

Git/HTTP exceptions can include remote stderr/request information. A future
trusted boundary must emit bounded sanitized diagnostics and correlation IDs,
never archive credentials, token-bearing URLs, raw headers or sensitive request
bodies. M1 does not modify error paths or reuse People Posters components.

## Coverage and historical facts

The [operation and coverage rules](PHASE5_OPERATION_AND_PUBLICATION_RULES.md)
enumerate all 22 packages, 278 exact variants, four version-1 generators and
18 overlay branches. M2 planning, M3 native previews, M5/M6 synthetic commits
and Package E transport have different support sets. None grants live use.

Retain 9,957 posters, 4,122 overlays, 14,079 outputs, 14,077 public mappings,
190 protected production members and 299 adoption-source members. The merged
[M7 evidence](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/43)
reconciles the actual historical capture on both platforms: complete envelope
`350e6dcc55b089029ee5a3d166fc28cba098d1c05f6634727b588a7c795263c0`.
This is accepted baseline evidence, not a claim that this planning PR regenerated
the library or verified live remote authorization.

## Existing CI scope constraint

[ci/phase4_m7.py](../../ci/phase4_m7.py) `preservation` compares all HEAD changes
since its fixed `68179d1c568449375ca72b23239b57770dfc229e` baseline against the
15-path M7 `ALLOWED` set, then compares physical existing baseline files.
[lifecycle-m7-validation.yml](../../.github/workflows/lifecycle-m7-validation.yml)
runs on every main-targeted PR. The five new Phase 5 documents are outside that
set; no existing exception permits them. This is a deterministic preservation
scope rejection, not evidence of a renderer, historical or network failure.

The check was introduced by `ef2aa5f` (M7 integrated acceptance), with the fixed
pre-M7 baseline and exactly the M7 delivery inventory. The dossier describes it
as an M7 source-preservation checker, and `PHASE4_M7_CHANGED_FILES.md` explicitly
describes the 15 intended M7 files. The maintained regression is
`test_m7_does_not_modify_original_workflow_source_or_historical_evidence` in
[test_ci.py](../phase4/m7_tests/test_ci.py). No reviewed document states that
every subsequent milestone is permanently limited to those same 15 paths.
This supports a **milestone-specific scope interpretation**, rather than a
policy forbidding future planning. Its unconditional workflow and fixed diff
range nevertheless make the restriction permanent in current executable CI.
That discrepancy needs an explicit successor decision, not an assumed waiver.

This M1 PR must leave the check, workflow, inventories and pins unchanged and
report the exact failure. An independently reviewed CI maintenance proposal can
authorize a narrowly specified documentation successor while retaining source,
membership, historical and unknown-path rejection. M1 does not grant or apply
that exception; failed M7 acceptance cannot be described as green acceptance.

Smallest proposed prerequisite: retain the exact current `BASE` and `ALLOWED`,
add a separate set of **only the five named new Phase 5 planning Markdown paths**,
and require each such path to be an actual Git addition relative to `BASE`.
Continue rejecting every other path and every modification/deletion/rename of
an existing frozen baseline file. `ROADMAP.md` and `PHASE5_PREREQUISITES.md`
already belong to the original M7 allowed set; no production allowance is added.
Keep all original preservation calls, complete frozen-file comparison, 190/299
memberships and hashes, accepted evidence, original inventories and workflow
budgets. A later milestone receives no wildcard documentation exception.

Proposed focused controls: exact five additions and existing status updates pass;
an unknown Markdown file, new executable/YAML, symlink/path alias, renamed/deleted
baseline file, altered production/adoption hash or manifest membership, stale
base/plan, missing preservation invocation and broadened allowlist fail. Preserve
all original IDs and run full Windows/Linux acceptance on the prerequisite's
exact head. Present the concrete local patch and these tests separately before
changing CI policy; the planning PR contains documentation only.

Read the [design](PHASE5_DESIGN_PROPOSAL.md), [milestones](PHASE5_MILESTONE_PLAN.md)
and [acceptance plan](PHASE5_ACCEPTANCE_PLAN.md) for proposed work and decisions.
