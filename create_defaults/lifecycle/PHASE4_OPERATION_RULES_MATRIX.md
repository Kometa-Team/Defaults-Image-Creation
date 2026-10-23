# Phase 4 operation rules and decision matrix

2026-10-23. **Documentation proposal only; no lifecycle implementation.**
Baseline and callable evidence: [audit](PHASE4_EXISTING_BEHAVIOUR_AUDIT.md).
Protocol: [design](PHASE4_DESIGN_PROPOSAL.md). Gates: [acceptance](PHASE4_ACCEPTANCE_PLAN.md).
APPROVED rows restate D01–D09/P3-D01–D04, accepted historical facts or the
maintainer's explicit public-retention default. PROPOSED rows require Phase 4
architecture review. BLOCKED rows describe current operational prerequisites.
LOCKED means maintainer-controlled; SUBMITTER means a bounded proposal, never
self-approval; DERIVED means computed from approved inputs; EXCEPTION means an
exact separately accepted departure; UNDECIDED means a new implementation choice.

## Cross-operation rules

| ID | Rule | Class / standing | Required handling |
| --- | --- | --- | --- |
| R01 | Contract/category/variant scope | LOCKED / APPROVED D01–D02 | Exact version/hash and externally attributed approval; closed selected variant. Contributor cannot invent a category, change the registry or set fixture/trust flags. All 22 current approvals are missing. |
| R02 | Ordinary request content | SUBMITTER / APPROVED D02 | Bounded display/content/source provenance and explicitly permitted background/name/exception proposals. No arbitrary YAML composer/profile/font/output routing overrides. Validate raw intent and fully expanded jobs. |
| R03 | Fonts and fitting | LOCKED + DERIVED / APPROVED D03 | Exact bytes, weight, size, measured context and approved fitting algorithm. Playlist remains Bebas Neue Regular/154. Bounds are not autoshrink permission; changed renderer/font/text/layout invalidates affected evidence. |
| R04 | Captions/language | LOCKED + DERIVED / APPROVED D04, P3-D01, P3-D04 | Exact required/conditional/prohibited caption, key/template, case and applicable language. No missing-key fallback camouflage, invented key, RTL activation or English-only bypass. Current source must be reverified explicitly. |
| R05 | Category logo treatment | LOCKED / APPROVED D09 | Playlist/Franchise/Genre/Seasonal/Universe WHITE_ONLY with exact individual SOURCE_PRESERVING exceptions; Studio SOURCE_PRESERVING; applicable Chart/Country/Network/Streaming BOTH_REQUIRED. Other variants retain historical rules. |
| R06 | Overlay treatment | LOCKED / APPROVED D09 | SOURCE_PRESERVING within existing colour/white branches, both sizes, exact transform/trim/encoding/basename. No inherited poster wash or automatic new branch. |
| R07 | New sources | SUBMITTER + LOCKED / APPROVED D09 | Valid bounded PNG, genuine transparency by default, visible foreground, integrity/quality/clip/background review. No automatic background removal. Intentional brand background uses explicit two-stage exception. |
| R08 | Historical normal alpha assets | EXCEPTION / APPROVED D09 | Preserve exact 17 accepted assets/41 historical uses without cleanup, warnings, re-review or regeneration. New bytes/use do not inherit acceptance by filename. |
| R09 | White derivation/separate white | DERIVED + LOCKED / APPROVED D09 | Existing wash preserves original and alpha. Optional separate white is compared for geometry/mask/cutouts/proportions/branding, not rejected solely for resolution/AA. Uncertain comparison remains manual; no unapproved MATCH threshold. |
| R10 | Backgrounds | SUBMITTER proposal + LOCKED assignment / APPROVED D05/D09 | Original logo RGB, treatment and poster background are separate. Proposal only where contract opts in; maintainers approve. Existing palettes/assignments/lineage remain exact. |
| R11 | Individual exceptions | EXCEPTION / APPROVED D09 | Justification, default/requested complete views, exact source/identity/contract/variant/treatment/member/context; explicit submitter confirmation then independent maintainer decision. Category default remains unchanged. |
| R12 | Stable identity | LOCKED + DERIVED / APPROVED D06 | Adopt existing IDs unchanged; new controlled category UUID assignment once, persisted semantic family/overlay lookup. No name/path-derived reminting or contributor-assigned trusted identity. |
| R13 | Literal names | LOCKED / APPROVED D06 | Definition/mapping is authority for source/local/public spelling, case, punctuation and Unicode. New names must be NFC; historical names remain literal. Collision keys detect conflict; never rewrite display spelling. |
| R14 | Effective validation | DERIVED / APPROVED D07 | Real loader/profiles/generator/language/raw-normalized/serialized-job replay; required parents and complete members. No detached JSON approval or post-validation resealing bypass. |
| R15 | Review/material reuse | DERIVED + LOCKED / APPROVED D08 | Explicit current compatibility proof for unchanged effective jobs/bytes/approvals; immutable old receipts retained. Pixel equivalence alone does not authorize a new mapping or stale review. |
| R16 | Remote byte synchronization | DERIVED / APPROVED earlier migration rule | Only actual equal candidate/published SHA-256 is synchronized. Eligible binary-different `renderer_equivalent` files stay in later upload membership after exact policy approval. No remote action in Phase 4. |
| R17 | Full composition membership | DERIVED + LOCKED / PROPOSED P4-D03 | Exact full-resolution candidates and owned receipts for every required language/presentation/size. Logo thumbnail, representative gallery or one completed companion cannot approve a new complete poster/group. |
| R18 | Operation versions/read set | DERIVED + LOCKED / PROPOSED P4-D01 | Immutable intent revisions plus append-only evidence events; CAS all affected subject/dependency/namespace heads. Concurrent changes conflict or require scoped revalidation. No last-writer-wins. |
| R19 | Authorities | LOCKED / APPROVED P3-D02; BLOCKED | Externally authenticated submitter/maintainer/current heads/source/ownership; no reviewer strings, unkeyed seals, local archive or synthetic grant as authority. P3 has no real positive authority result. |
| R20 | Destinations | LOCKED / APPROVED P3-D03, P3-D04 | Official English-only; English may target an explicitly authorized user repository. Any non-English needs reviewed versioned coverage. Current numeric repository/owner/branch/root/inventory scope must match evidence. No Phase 4 writer. |
| R21 | Operation versus review versus transport | LOCKED / APPROVED D08; PROPOSED operation binding | Logical atomic membership, visual risk population, generation workload, technical Git batches and publication PR are separate. Technical batching never waives review or companion completion. |
| R22 | Isolation/history | LOCKED / PROPOSED P4-D01; existing M1 convention | New isolated sidecars/root namespace, immutable object/index/event history. No production cache migration, old receipt edits or automatic orphan/history collection. |

## Operation-specific acceptance

| Operation / facet | Permitted request | Required before isolated acceptance/apply | Explicitly prohibited / blocked |
| --- | --- | --- | --- |
| ADD — identity/content | New item under enabled category/variant; qualifying source, allowed content and justified exceptions | Persist assigned stable identity, actual effective definition, exact approved mapping and complete output group | Contributor identity/contract approval, invented content type or accepted historical exception transfer |
| ADD — new variants | Select an already approved variant | New type/design/key requires separate immutable contract revision, impact and maintainer approval first | Arbitrary Release/Watch Order text/key and processing six deferred Timeline requests |
| ADD — composition | Complete default/requested candidates and all members | PNG/treatment/translation/fit/contract checks, owned byte receipts, explicit full submitter confirmation and independent maintainer decision | Logo-only final approval, missing colour/white or size member, simulated production eligibility |
| UPDATE — per-item source/text/background | Exact before revision and proposed material changes | Direct/transitive/companion impact, fresh evidence for changed scope, unchanged controls retained with proof | Global regeneration or blanket review invalidation inferred from file/package container change |
| UPDATE — locked style | Maintainer-controlled design revision request | Approved exact contract delta and bulk impact before affected candidate review; retain per-category rules | Contributor typography/effect/wash override or unapproved normalization/fitting change |
| UPDATE — shared input/family | Explicit shared-source or generator proposal | Re-expand both epochs, all consumers/private parents and semantic membership; unknown impact blocks completion | Pretend family fanout is minimal without per-child proof; use missing generated-parent bytes |
| RENAME — display only | Bounded display metadata change | Same stable ID, explicit untouched caption/source/local/public fields, current review-material comparison | Infer text/file/source changes from new display name |
| RENAME — rendered caption | Explicit approved content/key change | Reclassify as material UPDATE component, re-resolve translations, exact fit and full composition review | Treat it as metadata-only because the ID is unchanged |
| RENAME — source/local mapping | Exact old/new literal mapping | Same IDs/semantic members, source byte/provenance check, dependency reference updates, complete namespace and companion check; new immutable job/binding if paths change | Silent source fallback/slug, patch sealed job IDs, mutate old owned receipt |
| RENAME — public mapping | Describe an exact proposed future public transition | Version old/new mapping and retain old public file; later independent Phase 5 rename/removal authorization | Automatic remote rename/delete, reuse historical overlay-case grant for arbitrary names |
| RENAME — case/Unicode | Explicit owner-preserving case transition; new NFC spelling | Same old owner/hash, no third-party exact/NFC+casefold/file-directory collision; journaled local case move and exact Git tree checks | Count a case-only change as no-op, normalize historical Unicode, overwrite an existing target |
| DELETE — definition retirement | Exact selected definition/member revision | Incoming dependency and after-graph checks, valid complete remaining groups, tombstone and historical receipt/alias preservation | Implicit public deletion or erasure of historical evidence |
| DELETE — generated member/parent | Explicit family/member change | Supported persistent family exclusion or approved dependency changes; all retained consumers resolve | Remove only a generated output row that reappears on expansion; orphan child or required private parent |
| DELETE — public artwork | Separate proposed scope only | Independent exact path/blob/hash/baseline decision and later Phase 5 authorization/provider/inventory/transport | Any Phase 4 network deletion; absence from catalog as deletion permission |
| DELETE — physical sources/name reuse | Explicit separate request, not default | Shared-reference/retained-public check; new ID and explicit mapping/reuse decision; historical identity/alias remains reserved | Delete shared assets by reference-count guess, recycle old ID/approval or overwrite retained public art |
| CANCEL / reversal | Explicit target operation/revision | Before commit append cancellation and release owned claims only; after commit use new compensating operation with fresh CAS/impact/review | Rewrite accepted revision/events/receipts; undo remote state locally |

Removing a definition **retains public artwork by default**: confirmed maintainer
policy. Name reservations, local case-move mechanics and the operation journal
are proposed implementation choices, not new public deletion permission.

## Required review populations

| Population | Evidence / decision scope |
| --- | --- |
| Unchanged adopted output | Exact record/material/receipt/accepted-context compatibility, no repeated visual review solely for new metadata |
| New/changed complete poster | Every actual required composition; source/logo review is necessary where applicable but insufficient alone |
| BOTH_REQUIRED brand | Both rendered presentations and required outputs; one master may derive white, but neither role is implicitly approved |
| Overlay source/group | Both size outputs for each selected source branch; poster treatment does not create overlay membership |
| D09 exception | Labeled default/requested complete views, intentional-background scope if applicable, exact two-stage decision |
| Layout/font/warning exception | Exact affected content/layout/font/member evidence; existing legacy acceptance cannot waive new context |
| Rename/retirement without new pixels | Exact before/after mapping/dependency/retained-public manifest and candidate reuse proof; no new raster required solely for review |

All new previews, decisions and operations remain unimplemented. Open choices
P4-D01–D07 are in the [proposal](PHASE4_DESIGN_PROPOSAL.md); each milestone requires
its own explicit authorization. Phases 5–6 and production activation remain outside
this planning scope.
