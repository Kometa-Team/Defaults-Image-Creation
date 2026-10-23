# Phase 3 proposal: translation and destination safeguards

2026-10-23. **P3/M1–M2 merged through PR #27; P3/M3 is explicitly authorized and implemented pending review. Phase 3 IN PROGRESS.** See the [M3 dossier](PHASE3_M3_IMPLEMENTATION.md), [M2 preflight](PHASE3_M2_IMPLEMENTATION.md), [M1 foundation](PHASE3_M1_IMPLEMENTATION.md), [behaviour audit](PHASE3_EXISTING_BEHAVIOUR_AUDIT.md) and [six-phase roadmap](ROADMAP.md). The approved architecture and P3-D01–D04 below remain authoritative. P3/M4–M5 and Phases 4–6 remain NOT STARTED and require separate authorization. Earlier milestone implementation/review descriptions below are historical checkpoints, superseded only for status.

The merged D01–D09 architecture, 22 packages, stable identities, exact filenames, original receipts and all historical exceptions remain authoritative. This phase grants none of the 22 missing contract approvals. It does not activate contracts, render artwork, publish, change production entry points, implement lifecycle operations, or process the six deferred Timeline Order requests.

## Policy supplied by the maintainer

1. Official `Kometa-Team/Default-Images` publication is English-only. Every non-English request needs an explicit, validated user-owned destination; missing/ambiguous configuration never falls back to official publication.
2. A repository name establishes neither identity, ownership nor authorization. Validation establishes technical compliance, never permission to publish.
3. Required translations must be enumerated before readiness. Missing required non-English content blocks the affected request. Unrelated languages/designs remain independent. Length differences alone do not block.
4. Exact language, translation inputs/provenance and destination context are material evidence. Relevant changes invalidate prior readiness evidence. Existing category/design restrictions remain an independent gate.
5. Phase 3 is isolated and fail-closed. All actual contract approvals/activation remain pending; Phases 4–6 remain NOT STARTED.

These requirements are not optional recommendations. The implementation choices below are proposed for review.

### Approved maintainer policy decisions — 2026-10-22 M1 authorization

The maintainer originally supplied these positions for the planning refresh against CI repair PR #25, main `9022c7c7639f3a2238e5941ec79cc250e4a8ca85`. After planning PR #24 merged, the maintainer **explicitly approved all four for implementation and authorized P3/M1 only**. Their rationale and foundation boundaries are recorded in the [M1 dossier](PHASE3_M1_IMPLEMENTATION.md). Policy approval is not approval of real contracts, publication, activation or later milestones.

| Decision ID | Approved maintainer policy | Required boundary |
| --- | --- | --- |
| P3-D01 | Verified commit/content-based translation freshness, with explicit reverification before readiness. | Bind verified repository/commit/tree/blob provenance and exact resource/key/value hashes. A timestamp, cached report or unchanged rendered string cannot prove currentness. Unknown or failed reverification blocks the affected readiness contribution. |
| P3-D02 | Ownership and authorization must be externally authenticated; unavailable authority fails closed. | No self-asserted owner flag, repository name, caller string or token-shaped value establishes a grant. The foundation interface defaults to unavailable; a real provider and its trust/grant scope require separate review. |
| P3-D03 | English may use an explicitly authorized user-owned repository. | Require the same exact identity, branch/root/path, inventory and current external authorization checks as other user destinations. Official publication remains English-only; choosing a user target grants no publication permission. |
| P3-D04 | Real non-English category coverage requires separately reviewed, versioned contracts. | Preserve all current packages and English-only restrictions. Translation availability, language-neutral pixels or a user-owned target cannot bypass an existing contract. Synthetic test contracts confer no real authority. |

## Proposed architecture

Add an isolated `create_defaults/bulk/contracts/language_policy/` package, with its own versioned strict schema and canonical documents. Names and paths here are **proposed**, not available commands/APIs. Reuse M1 parsing, canonical hashing and immutable references; Package E transactions/events and M4/M7 sidecar conventions where explicit evidence archival is needed. Do not add unknown record types to frozen M1 schemas, rewrite old receipts, change the M6 release, or loosen M7 gates.

| Proposed object | Binding and purpose |
| --- | --- |
| LanguagePolicy | Maintainer-selected version/hash, exact registered language IDs and explicit aliases, supported category/variant scope, authoritative source selection and explicit freshness requirements. Discovery and policy support are separate facts. |
| TranslationSelection | Pinned LanguageSnapshot, selected-language resource/blob hashes, source repository/commit/tree provenance where present, exact required key/value traces and verification context. Local fixtures remain labeled local. |
| DestinationPolicy | Version/hash, official repository identity, explicit language-to-target/root mappings, exact base branch, permitted path scope and ownership-evidence requirements. No ambient Config default fills a missing non-English target. |
| DestinationEvidence | Exact repository/owner IDs and canonical name, branch/verified tree baseline, principal/authorization scope and externally authenticated provenance, evidence version/expiry/revocation context. JSON claims are not trusted evidence. |
| ValidationSubject | Read-only projection of existing stable item/output IDs, selected category/variant/package hashes, expanded-definition context, language and exact output membership. It is not an ADD/UPDATE operation or a replacement identity registry. |
| Phase3Attestation | Exact subject, policy, translation, destination, dependency and authority-context hashes; deterministic diagnostic coverage; technical outcome; `publication_authorized=false`, `production_enforcement=false`. A hash alone cannot authenticate or make an old report current. |

Pure evaluators accept immutable input and explicit verification context. They never refresh a network source, instantiate workers, open writable production state or record approvals. An explicit report export may write only an isolated evidence artifact. Any opt-in audit archival uses an additive, versioned isolated sidecar on existing storage, with observation events rather than approval/activation events. Opening an archive is not required for read-only preflight.

The current M1 type readers, M5 graph kinds and M7 gate set are closed. P3/M1 defines separate schema/type boundaries; P3/M4 binds a companion to existing hashes and read-only impact reports. It does not pretend that a new destination node or new M7 transition is already supported. Any required public storage adapter is reviewed explicitly, rather than silently widening existing `pin`/record APIs.

### Language identity and source selection

Validate using the existing safe language syntax. Resolve exact registered IDs first, then only explicitly registered, validated aliases. Preserve requested spelling for diagnostics and exact canonical/native identifiers for evidence. Keep `nb_NO` and `pt-br`; do not silently lower-case, substitute separators, strip invalid input or treat a country/logo filename as a language. Comparison keys may detect ambiguity without rewriting identifiers or text.

The 14 currently discovered resources are not automatically supported languages. The 11 compatibility IDs are not a ceiling either. Effective category/variant applicability and a maintainer-selected language policy must both permit a request. Under approved P3-D04, the current English-only Playlist package cannot be bypassed by finding a French string. Use synthetic multilingual contracts only for tests; real non-English scope requires separately reviewed, versioned category contracts, preserving the 22 current packages and their exact historical scope.

Authoritative Git-backed provenance identifies verified repository/commit/tree/blob and SHA-256 values. It does not invent Weblate review/translator metadata. Do not guess component URLs, tokens, permission APIs or an authentication service. Source refresh is a separate explicit operation; preflight consumes a selected verified snapshot. The existing frozen English fixture stays unchanged as the production input.

### Required-key preflight

1. Consume the actual M5-expanded definition and enabled caption content type, not just submitted YAML. Enumerate both caption and template keys, plus any real approved resolution dependencies. Reject hidden key/language/path overrides outside the category contract.
2. Check authoritative English source-key validity and the selected-language values. Distinguish absent key, unavailable resource, invalid UTF-8/YAML/key structure, empty/non-string/sentinel/unresolved content and stale provenance. Keep applicability/not-applicable separate from missing content.
3. Retain raw strings and exact source/value hashes. Record category-controlled casing/template/suffix resolution separately with existing legacy semantics. Never normalize away punctuation, accents or Unicode or fabricate a translation.
4. Missing required non-English content blocks that request even if a legacy fallback could produce English text. No new fallback exception is inferred. Existing historical fallback records/output classifications are preserved, without promoting them to new readiness authorization. Missing required English also blocks the affected English request.
5. Shared/absent captions and source-preserving overlays have an accurately empty translation-key set. Their request language and destination still require validation. Embedded logo text is not an invented caption key.
6. Emit sorted, bounded canonical results per subject/language, with complete requested scope and invalid/missing/available/stale categories. An aborted or incomplete audit cannot claim complete coverage. Different text lengths are informational; existing glyph, RTL, fitting and design-review gates remain independent and are never disabled to accept a longer string.

Use explicit source-verification context rather than wall-clock calls inside content hashing. A fixed input and fixed `as_of`/policy/authority context must produce identical bytes. Unknown freshness requirements or unverifiable current source block a readiness claim. No arbitrary TTL is invented in this proposal.

Under approved P3-D01, explicitly reverify the selected authoritative Git commit and relevant content before a readiness consumer accepts the attestation. Verify repository identity, commit/tree/blob linkage and resource content hashes, including authoritative English source-key context, against the policy-selected source. Bind that verification outcome and exact context to the consumed evidence. A previously pinned snapshot proves its own integrity, not that it is still the current authorized selection. A moved upstream head requires a new verified provenance decision even when relevant content is unchanged; it is not automatic artwork regeneration, translation approval or a demand to repeat an unchanged visual review. Unrelated resource changes retain scoped dependency handling. The permitted verification-to-consumption interval and revalidation of an intervening source change need an explicit technical protocol before operational readiness; absent a verifiable current context, block. This specifies an evidence boundary, not a new Weblate API or an implemented network adapter.

### Destination decision matrix

| Request and target | Required result |
| --- | --- |
| Exact `en`, explicit official repository/branch/root, valid paths and all other gates | Official-language policy check may pass; publication and actual READY remain unauthorized. |
| Any non-English ID, official repository identity, including case/URL aliases | Reject official eligibility, even with complete translations, identical pixels, shared artwork or a submitter's purported permission. |
| Non-English, explicit validated user-owned repository/branch/root and current externally verified ownership scope | User-destination technical check may pass; never a publication grant. Missing real authority blocks. |
| Missing, conflicting or ambiguous target/root/branch; unknown ownership or revoked/expired evidence | Block that scope. No fallback or repository-name heuristic. |
| English, explicitly authorized user-owned target | Under approved P3-D03, permit the same user-destination technical checks; official English-only policy does not require every English output to be official. Independent contract/authority checks and publication approval remain required. |
| Private/unconfirmed historical output (`remote_relative=null`) | Preserve private status; never promote to public membership or invent a destination. |

Bind official identity to verified repository/owner IDs and exact policy-selected branch, not a string prefix. At audit time official repository ID is `474155312`; a future move/rename changes verification context and needs explicit revalidation. Resolve case-insensitive repository spelling to verified identity; preserve exact Git branch casing. A user fork is not official merely because of its name, and is not authorized merely because it exists.

Under approved P3-D02, user destinations require evidence from a controlled, externally authenticated boundary identifying principal, actual owner/repository, exact branch/path/language scope and current grant status. Reuse M1's separation between typed evidence and trusted caller context, not its maintainer allowlist as a substitute for user ownership. The default provider is unavailable/fail-closed. Test providers are explicitly synthetic; no CLI `owner_verified=true`, actor string, token-shaped value or self-hashed grant can establish authority. Unavailable, expired, revoked or unverifiable authority blocks readiness. Credentials, authorization headers and tokens must never appear in reports or archived evidence. Live authentication/provider integration is unresolved and must not be fabricated here or smuggled in from future Phase 5. No publishing credentials or live ownership provider are supplied by this proposal.

Preserve canonical relative filenames derived from existing naming authority. Validate proposed members and a complete explicitly supplied destination inventory together. Compare `(repository identity, exact branch, path)` with NFC+casefold path collision keys; detect duplicate/case/Unicode-equivalent files, overlapping language roots and cross-language aliases. Empty or incomplete inventory cannot prove an existing target collision-free. Reject traversal, absolute paths, drive/UNC/ADS forms, `.git`, reserved/unsafe components, link escapes and ambiguous encoding; never silently rename or normalize output bytes. Historical aliases require their existing exact evidence, not a blanket waiver. Do not treat unchanged content hashes as permission for cross-language path reuse.

No `en/`, `fr/` or repository naming layout is assumed. Existing official paths remain unchanged; user roots/mappings must be explicitly configured. Language-neutral overlays preserve existing paths, branches, source basenames and standard/bigger companions. A non-English overlay request still cannot target official publication by claiming its image has no translated caption.

### Freshness, readiness and replay

The attestation binds stable subject/output membership, contract/rules/exception selection, expanded-definition context, request language, exact required translations/resource provenance, destination policy/configuration, owner authority scope and verified target baseline. Recompute from actual current selected inputs when consuming evidence. Reject altered payloads, wrong expected hashes, foreign subjects, partial memberships, stale policies, expired/revoked grants and old evidence replayed after a newer review/context.

Preserve M5's exact resource **and** key/value dependency binding. A relevant translation source change invalidates affected readiness even if rendered text happens to remain equal. A resource used only by an unrelated language/design does not block the selected request. Reverification is not automatic regeneration or a blanket demand to repeat unchanged visual reviews. A moved upstream head needs explicit verified provenance/currentness; it cannot be mistaken for a new translation approval.

Return technical preflight status and blockers, not an M7 state transition. A future readiness consumer must require this exact current attestation **in addition to** every existing M1–M7 prerequisite. All 22 real contract approvals remain absent; a perfect Phase 3 report cannot create actual READY/ACTIVE status. Language/source/destination changes invalidate the relevant Phase 3 readiness contribution. Phase 3 reads M7 inspection/impact interfaces but never invokes its transition controller or patches gates to trust caller booleans. It guarantees the isolated boundary only; retrofitting generation/publication entry points belongs to separately authorized integration.

## Small implementation PRs, in order

Each milestone needs explicit authorization and stops for review. P3/M1–M2 are merged; P3/M3 is explicitly authorized and implemented pending review. P3/M4–M5 remain NOT STARTED and require separate authorization.

| Milestone / proposed PR | Scope | Acceptance and boundary |
| --- | --- | --- |
| **P3/M1 — policy schemas and isolated evidence interfaces** | New `contracts/language_policy/` types/schema/README; strict versioning/canonical hashes; exact language/reference/path fields; trusted-authority interface defaulting to unavailable; synthetic schema/security tests. | Reject unknown fields, malformed pins/IDs, ambiguous mappings, self-asserted authority and wrong record stages. Unchanged inputs/context hash identically on Windows/Linux. Imports/help cause no network, image access or production-state writes. No preflight engine, live auth, contract edit or activation yet. |
| **P3/M2 — read-only translation preflight** | Adapter over actual expanded definitions and selected existing translation snapshots; required-key enumeration, content/provenance/freshness diagnostics, deterministic scoped reports. | English and multilingual synthetic controls; missing versus invalid; caption+template keys; long/accented/Unicode text preserved; missing required values block; fallback cannot hide missing required non-English content; unrelated designs/languages unaffected. No new fitting algorithm, font override or image rendering. |
| **P3/M3 — destination policy validation** | Explicit official/user target rules, authority consumption, repository/branch/root/path context, complete inventory and collision checks. | Non-English official attempts always fail; valid synthetic owned-user cases pass only technical checks; unauthorized/expired/changed evidence, conflicting roots, Unicode/case/path attacks and cross-language aliases fail. No remote writer or guessed ownership API. |
| **P3/M4 — context, freshness and evidence consumption** | Bind P3 companions to M1 exact packages/records, M5 subject/dependency/review hashes and M7 read-only inspection; explicit isolated report/audit archival where needed. | Mutation/replay/revocation and changed language/source/target invalidate affected evidence; immutable receipts are not rewritten; unrelated scope stays unchanged. State-writer/controller/network/render fault hooks prove pure inspection. All 22 real approvals still missing; zero actual READY/ACTIVE. |
| **P3/M5 — historical acceptance and CI handoff** | Complete adversarial matrix, exact historical projection/reconciliation, changed-file inventory, reproducible commands and final-head Windows/Linux evidence. | All 14,079 outputs accounted for, 14,077 public / two private; unchanged 22 packages / 278 variants / original exceptions and filenames; zero unexplained differences; all 190 production integrity checks and original resource checks pass. No production activation/integration or deferred request processing. |

### Proposed first implementation PR

Title: **`feat(lifecycle): add isolated Phase 3 policy and evidence foundations`**.
Implementation branch: `feat/lifecycle-phase3-m1-policy-foundations`, newly based on merged planning main. The [M1 dossier](PHASE3_M1_IMPLEMENTATION.md) records its actual schema/model/authority, synthetic test and CI inventory. Current category packages, frozen schemas/receipts, People code, renderers, translations, assets, generators and publication entry points remain unchanged.

The proposed separate Phase 3 workflow is superseded by an equally isolated matrix in the existing bounded workflow. Its focused `create_defaults/phase3/tests/` jobs on both Windows and Linux are direct prerequisites of mandatory **Validation acceptance**. The aggregate verifies complete focused IDs and canonical vectors in addition to every original test and non-pytest gate. This keeps the new checks mandatory through the existing aggregate without introducing another optional check. The explicit authorization permits the narrowly scoped workflow source-pin/provenance maintenance; all 190 memberships and other source hashes remain intact. All jobs retain exact-head checkout, read-only permissions and the 15-minute cap. No repository settings change is made. Review M1 before authorizing P3/M2.

## Adversarial and historical acceptance matrix

| Evidence family | Required negative/control cases |
| --- | --- |
| Language routing | English/official control; valid synthetic non-English/user control; non-English/official rejection; empty/unknown/aliased/case/Unicode-lookalike codes; shared/overlay content cannot bypass routing. |
| Translation correctness | Missing source English/key/template, unavailable file, invalid YAML/UTF-8/value/sentinel/placeholder, empty value, stale blob/provenance, legitimate length and accent differences, no unrelated-language blockers. |
| Destination identity/authority | Official spelling aliases and user forks, exact branch case, missing owner evidence, untrusted JSON claims, wrong repo/owner/principal/scope, expiration/revocation, changed config after review. |
| Naming and membership | Traversal/absolute/drive/UNC/ADS/reserved/link escapes, NFC/NFD/case collisions, overlapping mappings, incomplete tree, identical-image cross-language collisions, private outputs, exact historical filenames and existing paired/size companions. |
| Evidence integrity | Altered reports/pins/record stages, cross-subject or cross-language replay, stale review/policy/target baseline, missing members, state mutation and forged publication/READY flags. |
| Regression/isolation | Existing M1–M7 adversarial/recovery/resource suites; fresh full historical audit; 14,079 records and original classifications; unchanged 22 package hashes; 190-file protection; no production generation/network-write/controller calls. |

Synthetic translations are explicitly test strings, never catalog contributions. Real non-English category permission or ownership must not be faked to turn a control green. Existing accepted historical exceptions remain facts, not new exemptions from destination policy.

## CI organization and resource limits

Merged PR #25 supplies the current bounded Windows/Linux validation architecture; see its [measurement and coverage design](../../ci/README.md). Its [successful exact-head run](https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/39878142195) passed all 19 checks at `40b95e22dd7e30ee620f90374c510f2196b0ab8f`, whose tree equals refreshed main. Eight explicit groups per OS retain every original test and non-pytest gate; separate collection jobs and mandatory **Validation acceptance** prove full node-ID coverage and reject failed, cancelled, skipped or missing groups. All three complete historical-fixture consumer modules remain together to avoid repeated capture. Collection, setup/call/teardown and real resource evidence are retained. The earlier timeouts remain historical evidence, not a current unresolved CI repair.

Preserve that complete bounded workflow, original assertions, 15-minute cap, 512 MiB worker-parent safeguard, worker/total-worker budgets, all 190 protected files and historical validation of all 14,079 outputs. New Phase 3 string/metadata-only tests should not start render workers or unnecessarily duplicate full audit captures. Reuse verified immutable context with explicit release rather than introducing production caches or cross-run authority caches. Any future alteration of a production-pinned workflow/source requires an explicit narrow pin/provenance review, never an automatic checksum refresh. Do not skip tests, weaken checks, suppress failures or raise limits to obtain green CI. No CI implementation changes are part of this three-document PR.

Each implementation PR reports exact head, test selection/counts, skips with reasons, Windows/Linux job conclusions, resource evidence and historical coverage. A passing prior head, a timed-out run or frozen report alone is not fresh final acceptance. Planning-doc validation and baseline CI must be labeled separately from unimplemented Phase 3 evidence.

## Decisions and real integration gaps

| Decision / gap | Proposed safe position | Needed before |
| --- | --- | --- |
| Approved policies P3-D01–D04 | Commit/content reverification, external authority, explicitly authorized English user targets and separately versioned non-English coverage are approved. M1 implements foundations only, not operational readiness or real contract approval. | P3/M1 review now; P3/M2–M5 require separate explicit authorization. |
| Freshness verification protocol | Decide the controlled verifier/trust boundary, authoritative source selection/advancement and atomicity or permitted interval between explicit reverification and readiness consumption. Bind exact commits and relevant content; unknown currentness blocks. No arbitrary TTL or timestamp-only rule. | Operational readiness in P3/M2–M4; M1 may represent unavailable verification. |
| Ownership provider and scope | Select an actual externally authenticated provider and reviewed evidence/grant/revocation protocol. Personal ownership must be verified; organization/delegated repositories remain denied unless explicitly covered. No provider, credential scope or live adapter is invented. | Any real user-destination readiness; synthetic unavailable-authority foundations need no live provider. |
| User-destination mappings | Select explicit repository IDs, branch/root/path/language scope and complete inventory evidence, including authorized English user targets under P3-D03. No default naming layout or implicit publication permission. | Real DestinationPolicy selection in P3/M3. |
| Real non-English contract coverage | Select and separately review the actual versioned category/variant packages and typography/assets needed by each intended language. Existing English-only packages are never bypassed or widened. | Any real non-English request passing every category gate. |
| Authenticated Weblate component/review metadata | Preserve verified Git provenance and mark per-key review unknown; use only the verified contribution landing link. | Any feature claiming Weblate-specific review authority; none is required for the initial Git-backed preflight. |

**P3/M3 review checkpoint:** review the isolated destination safeguards and exact-head evidence in the [M3 dossier](PHASE3_M3_IMPLEMENTATION.md) and draft PR. P3-D01–D04 remain approved; real authority, contract approval, combined readiness, production activation, publication and merging remain separate. P3/M4–M5 and Phases 4–6 require explicit future authorization.
