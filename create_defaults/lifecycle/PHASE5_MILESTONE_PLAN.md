# Phase 5 milestone plan: independently reviewed integration gates

2026-10-26. **Only M1 planning/validation is authorized.** M2–M7 below are
proposed implementation boundaries, each requiring separate maintainer approval
and a draft PR. Phase 4 M1–M7 are merged at
`ef3b2713cf5dcab9b92395321c6be3fdf1efdbce`. No milestone description grants a
real contract decision, activation, publication or merge.

The [audit](PHASE5_EXISTING_BEHAVIOUR_AUDIT.md) distinguishes existing APIs from
missing integration. P5-D01–D08 in the [design](PHASE5_DESIGN_PROPOSAL.md) require
review. [Coverage/rules](PHASE5_OPERATION_AND_PUBLICATION_RULES.md) and
[acceptance families](PHASE5_ACCEPTANCE_PLAN.md) define blocked scope and evidence.

## Safeguards required at every milestone

Use a clean branch from actual current merged main; retain unrelated local
changes and immutable historical evidence. Explicitly enumerate exact changed
files and production/299-source/190-protection membership impact before editing
a protected boundary. Proposed filenames below are interface locations, not
already available modules or permission to alter source pins. No blind hash
refresh or umbrella protected-file allowance; any required transition is a
separately reviewed exact maintenance patch.

Run original bounded Windows/Linux validation, original IDs/historical capture,
contract/translation/destination/review/recovery controls and exact-head acceptance.
Retain 512 MiB worker-parent protection, worker/process/object/pack budgets,
15-minute CI limits, pinned read-only actions and sanitized artifacts. Reuse the
single guarded historical capture; no duplicate full-library regeneration or
test-inventory rewrite. Add focused tests only for newly authorized interfaces.
No milestone is complete with missing/failed required checks. Unsupported scopes
must produce intended fail-closed diagnostics, not skipped tests or broken fixtures.

## M1 — evidence-based architecture and planning (current scope)

| Facet | Required boundary |
| --- | --- |
| Exact scope | Audit actual review/publication/authority/catalog paths; propose smallest integration, full coverage matrix, security/operation rules, acceptance and independently reviewed milestones. |
| Dependencies/preconditions | Verify current remote main and merged #43, read full roadmap and Phase 2–4 evidence; preserve clean implementation baseline. |
| Existing/new interfaces | Read existing APIs only. No new Python/schema/database/provider/publisher/approval or activation interface. |
| Expected files / protection | Exactly five new `PHASE5_*` planning documents, current `ROADMAP.md` and necessary `PHASE5_PREREQUISITES.md` status. No protected source or CI changes. |
| Positive/adversarial validation | Verify every existing API/path citation, 22/278/4/18 inventory, status/log preservation, exact seven-file diff, relative links, approved provenance and protection. Identify inherited M7 scope failure rather than bypassing it. |
| Windows/Linux | Run unchanged existing CI at exact PR head; record every outcome, including blocked mandatory checks. Existing local bounded validation supplements, not replaces, hosted results. |
| Completion/acceptance | Draft PR with final SHA, exact inventory, evidence, P5-D01–D08 and separate CI-maintenance recommendation. Stop for review. Technical planning may be delivered with an explicitly unresolved prerequisite; no green acceptance claim while a required gate fails. |
| Unsupported / decisions | All runtime work, real approvals/providers/writes/activation, M2 and Phase 6 remain unauthorized. Blueprint approval is not operational authority. |

## M2 — authenticated read-only identity, decision and freshness observations

| Facet | Proposed scope and review gate |
| --- | --- |
| Exact scope | Supervised existing GitHub session, numeric principal/repository/owner facts, current maintainer/destination permissions and decision-object observation; verified source/destination head/tree/blob selection. Read-only network calls and isolated evidence only. |
| Dependencies/preconditions | Accepted M1, P5-D01/D02/D07/D08, approved credential/redaction/revocation model and separate CI prerequisite. No source YAML or remote write permissions exercised. |
| Reused APIs | `ReadOnlyGitHub`, complete-tree helper, P3 source/destination protocols/types, required-key/inventory/path validators, Package E immutable evidence. |
| Genuinely new interface | Controlled authenticated observation adapter and reviewed versioned real-result boundary; exact numeric-ID policy and bounded decision pagination. Existing real-positive statuses do not exist. No new authentication platform. |
| Expected files / protection | Proposed isolated authority adapter/tests under `bulk/contracts/` or `bulk/lifecycle/`, not implemented now. Any changes to P3 result consumers, registry/role policy or protection pins require an exact prior review; identify 190/299 intersection before patch. |
| Positive/adversarial tests | P5-T01–T08, T10–T11, T29–T30: valid recorded facts versus forged/revoked/expired/edited/dismissed/misbound/paginated/unknown observations. Unit protocol tests use controlled fixture responses; real sandbox reads need explicit approved account/target, never inferred production grants. |
| Windows/Linux / safeguards | Full existing bounded checks plus deterministic protocol/redaction tests and failure diagnostics. No secrets in logs, no live credentials needed for CI. |
| Completion/acceptance | Read-only adapter has independently audited identity/provenance and unavailable behavior; no operation, READY/ACTIVE or write can consume a fabricated success. Stop before real approvals or catalog mutation. |
| Unsupported / decisions | No automatic role provisioning, org delegation, live service deployment or arbitrary providers. Exact expiry/role/revocation rules must be decided rather than hard-coded by guess. |

## M3 — exact contract and full-context decision consumption

| Facet | Proposed scope and review gate |
| --- | --- |
| Exact scope | Bind authenticated native submitter confirmation and distinct maintainer decision to full preview/context; validate explicit per-package contract decisions and current state at consumption. Prepare immutable attributed evidence; no production activation. |
| Dependencies/preconditions | Accepted M2 and P5-D02/D03; real package approvals must be individually supplied separately if requested, never manufactured by implementation tests. |
| Reused APIs | `ContractApproval`, `RegistrySnapshot.load/select`, `TrustedDecision`, `CompositionArchive`, `ReviewArchive` semantics, `ReviewInputs`, P3 `consume/revalidate`, Package E records/CAS. |
| Genuinely new interface | Reviewed real decision capture/consumption adapter over existing native GitHub objects and typed records; compatibility boundary preserving all synthetic protocols/false flags. |
| Expected files / protection | Proposed authority/decision adapter and focused tests; narrow existing consumer changes only after protected impact review. No mutation of current empty registry or old approval/receipt records without separately authorized real decisions. |
| Positive/adversarial tests | P5-T03–T05, T09–T15, T28–T30: exact decision/confirmation linkage, current role, all 22 selectors, changed context/artifact/translation, missing companions, self-approval, stale/edited decisions and attempted activation bypass. |
| Windows/Linux / safeguards | Real native complete preview reuse, actual encoded artifact hashes, setup/call/teardown evidence, existing budgets and exact maintained inventories. No simulated approval represented as real. |
| Completion/acceptance | Distinct approval scopes and exact current evidence are independently verified; missing package approval fails closed. No source writer, remote push, merge or ACTIVE path. |
| Unsupported / decisions | Blanket package approvals, image-equivalence waivers, generic PR approval without exact context, new visual thresholds and activation remain blocked. |

## M4 — current-mapping lifecycle adapter and bounded support cohorts

| Facet | Proposed scope and review gate |
| --- | --- |
| Exact scope | First implement a reviewed current-mapping UPDATE for active assigned English Genre single-logo items after nonvisual M6 RENAME. Preserve prior epochs/aliases, fresh sources/graphs/compositions/review and scoped CAS. Additional categories are separate cohort PRs, not bundled here. |
| Dependencies/preconditions | Accepted M3, exact initial P5-D04 selection and reviewed operational type/storage boundary. No production caller or live writes until later explicit integration authorization. |
| Reused APIs | Identity registry/current mapping replay, `resolve_stable`, original `Planner`, `poster_candidate`, native composition/review, existing local transaction/retention mechanisms. |
| Genuinely new interface | Current committed mapping/graph adapter; preserve stale M5 guard and immutable snapshots. Any positive operational local consumer requires separately reviewed concrete authority, not a synthetic subclass. |
| Expected files / protection | Proposed mapping-aware adapter/tests and narrowly identified existing lifecycle consumers; exact source/protection impact review before change. No renderer/font/generator/policy change or catalog writer. |
| Positive/adversarial tests | P5-T12–T20, T26–T27: ADD/UPDATE/RENAME/new UPDATE, original and current encoded epochs, stale old M5 rejection, retirement, shared/dependent/current-name changes, namespace conflicts, cancellation and fault boundaries. |
| Windows/Linux / safeguards | Actual encoded supported compositions, case-only rename and cold restart; original parent/process limits and historical identity/name/receipt projections. |
| Completion/acceptance | Exact active cohort has safe current-mapping updates and no regression of retired/stale rejection; unrelated outputs byte-identical. All other 278-variant scopes explicitly inventoried as blocked or separately validated. |
| Unsupported / decisions | UPDATE after retirement, public remote rename/deletion, new overlay jobs, persistent generated exclusions, pairs, placeholders/text and Playlist require their own adapters/PRs. No claim of all-category production coverage. |

Expansion order to review after the first cohort: ordinary single-logo contracts;
Playlist-specific caption/background controls; required white/colour pairs;
placeholder/text cohorts; generated/composition families with persistent semantic
IDs and exclusions; finally overlay pre-seal identity and exact size/branch groups.
Each step requires exact variants/operations, complete native positive/negative
tests and its own stop gate. This order is proposed, not permission to begin.

## M5 — owned catalog patch and publication preparation, offline first

| Facet | Proposed scope and review gate |
| --- | --- |
| Exact scope | Prepare minimal exact production-catalog postimages in owned staging, replay original loader/jobs and produce complete lifecycle-to-Package-E publication plan. Persist intent/progress locally; test against local bare remotes only. No production catalog writes or network publishing in this milestone by default. |
| Dependencies/preconditions | Accepted initial M4 cohort, P5-D05/D06/D08, exact approved source ownership/base and catalog patch semantics. |
| Reused APIs | Definitions/resolution/planner/category validation, `library_publication.batch_plan/validate_paths`, operator manifest checks, `library_transport.run`, original Package E store/events. |
| Genuinely new interface | Narrow catalog patch/progress artifact and complete logical-operation bridge. Prove any additive sidecar need before schema work; no second database. Existing operator manifest can withhold rows, so bridge must enforce completeness before authorization. |
| Expected files / protection | Proposed `bulk/lifecycle` preparation/export adapter/tests; source/catalog writer prototypes confined to owned temporary files. Protected production YAML changes/pin successors need their own exact proposal, never included implicitly. |
| Positive/adversarial tests | P5-T13–T25, T27–T31: unchanged raw YAML/comments/IDs, malicious fields/path, full planner replay, incomplete sets, equal bytes but changed mapping, crash after prepare/commit/push and ambiguous local-remote acknowledgements. |
| Windows/Linux / safeguards | Local bare repositories, raw case-sensitive Git object checks on Windows, bounded packs/artifacts and worker RSS; no external token/network in CI. |
| Completion/acceptance | Exact source postimages and remote candidate plan reproducible; all unrelated raw bytes/jobs preserved; each partial state explicitly incomplete and recoverable without deleting successes. No callable production writer or publisher enabled. |
| Unsupported / decisions | Catalog reserialization, unknown source roots, implicit source activation, arbitrary target routing, deletion and general public rename blocked. |

## M6 — separately authorized draft transport integration

| Facet | Proposed scope and review gate |
| --- | --- |
| Exact scope | Connect the accepted exact supported lifecycle plan to the existing Package E fixed official English draft transport, revalidate authority/current heads before each write, reconcile actual bytes/full tree and create one exact linked draft PR. Catalog proposal stays separately staged. |
| Dependencies/preconditions | Accepted M5 and all exact real contract/artwork/operation/destination permissions for the selected operation, separately authorized test destination/write scope and P5-D05/D07/D08. Missing activation/operational authority must block; implementing code does not supply it. |
| Reused APIs | `operator_publication.gate/stage/draft`, `library_stage.run/verify_diff/RemoteBytes/final_remote_diff`, owned journal and existing retry/PR reconciliation. |
| Genuinely new interface | Narrow trusted lifecycle-to-existing-transport authorization binding and fresh per-batch guard; explicit target extension only in separate review if user destinations become required. No alternate GitHub writer. |
| Expected files / protection | Exact transport/bridge tests and small approved source changes; fixed-destination/security gates are protected impacts requiring review before editing. Existing legacy migration callers retain behaviour and approved byte handling. |
| Positive/adversarial tests | P5-T01–T08, T21–T30: permission/source/base changes between checks and writes, unrelated/foreign branch, ambiguous push/PR success, incomplete prefix, full-tree mismatch, no protected-branch writes or remote deletion. |
| Windows/Linux / safeguards | Complete isolated protocol/Git tests mandatory; optional explicitly authorized sandbox exercise separate from CI and production. Exact-head proof, unchanged caps, safe credential/redaction boundaries. |
| Completion/acceptance | One exact unmerged draft for complete verified membership, no unsafe source consumption; partial publication remains incomplete; every actual byte and full tree reconciled with current scoped authority. |
| Unsupported / decisions | No automatic merge, activation, production pilot, generic user repository, non-English contract bypass, public deletion/cleanup or arbitrary public rename. |

## M7 — integration acceptance and Phase 6 handoff

| Facet | Proposed scope and review gate |
| --- | --- |
| Exact scope | Reconcile actual implemented support, all adversarial boundaries, source/catalog/draft recovery and complete historical compatibility. Produce operational limitations and explicit Phase 6 pilot prerequisites. |
| Dependencies/preconditions | Accepted M2–M6 selected scopes and decisions; no skipped unsupported cases represented as support. Exact real approval/activation state recorded independently. |
| Reused APIs | Original mandatory acceptance, shared historical capture, M1–M7 invariants, existing Package E transport proofs and all new narrowly approved adapters/tests. |
| Genuinely new interface | Acceptance evidence/matrix and handoff only; no expansion of trust/publishing scope to make acceptance pass. |
| Expected files / protection | Future focused acceptance tests/dossier/roadmap and bounded evidence additions under separately approved CI policy; no unrelated runtime or threshold changes. |
| Positive/adversarial tests | All P5-T01–T34, including complete supported chains, cancellation/crash/restart, exact retry/compensation, all 22/278 disposition and unchanged historical projections. |
| Windows/Linux / safeguards | All required final-head jobs/artifacts/actual IDs, full original historical validation, 190/299 hashes/membership, 512 MiB and 15-minute caps. Independently replay aggregate and inspect actual artifacts. |
| Completion/acceptance | Draft acceptance PR with zero unexplained historical changes, exact implemented/blocked matrix and explicit maintainer review; Phase 5 completion does not start Phase 6. |
| Unsupported / decisions | Any unimplemented category/language/provider, all remote destructive operations and six Timeline Order requests remain blocked/deferred. Real pilot/activation needs separate authorization. |

## Separate inherited CI prerequisite (not M2)

The fixed M7 allowlist and its purpose are traced in the audit. Propose a separate
small maintenance PR permitting **only additions of the five exact named Phase 5
planning Markdown files**, retaining existing M7 allowed documentation status,
all baseline/production/adoption/hash checks, unknown-path rejection and resource
limits. Add focused acceptance/rejection controls without rewriting original IDs.
No change to production allowances, existing schemas or protected baselines.
Present the exact evidence/patch/tests for approval before changing CI policy.
This M1 planning PR must not contain that maintenance patch or claim its failed
inherited check is an approved exception.
