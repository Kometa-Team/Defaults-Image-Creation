# Phase 4 lifecycle operations design proposal

2026-10-23. **Planning IN PROGRESS; implementation NOT STARTED.** This proposal
starts from Phase 3 PR #30 merge `f05d6af835da3c1536cc116c31dfdd8fda100e42`.
It authorizes no code, artwork, decision capture, activation or remote operation.
New types, modules and transitions below are **proposed**, not existing APIs.
The [audit](PHASE4_EXISTING_BEHAVIOUR_AUDIT.md) records actual interfaces and gaps;
[rules](PHASE4_OPERATION_RULES_MATRIX.md), [milestones](PHASE4_MILESTONE_PLAN.md)
and [acceptance](PHASE4_ACCEPTANCE_PLAN.md) define the implementation review gates.

## Fixed architecture and authority

Preserve [D01–D09](PHASE2_DESIGN_PROPOSAL.md) and
[P3-D01–D04](PHASE3_DESIGN_PROPOSAL.md): exact immutable contract versions/hashes,
closed variants/content fields, approved typography/fitting/captions, independent
logo treatment/background, literal filenames, stable identities, expanded-job
validation, selective reuse, two-stage D09 decisions and externally authenticated
current source/ownership. Official destinations remain English-only; explicitly
authorized user-owned targets may contain English, while real non-English still
requires separately reviewed versioned contracts. No new provider, credentials,
Weblate endpoint, TTL or automatic visual-comparison threshold is selected here.

Phase 3 implementation is COMPLETE. All 22 exact package approvals, approved
operational registry, live source reverification, ownership/permissions/revocation,
authenticated decision capture/current heads and independent activation remain
missing. P3 `AuthorityResult` has no real authorized-success outcome, and M4
consumption fixes READY/ACTIVE/publication/enforcement false. Phase 4 must consume
those results honestly; it cannot install a trusted flag to make them positive.
Future tests may exercise isolated synthetic operation acceptance with synthetic
principals and evidence, always incapable of production writes. Extending real
authority/integration is a separate reviewed Phase 5 prerequisite, not a hidden
task in these milestones.

## Reuse and ownership of new code

Use a proposed opt-in `create_defaults/bulk/lifecycle/` package for orchestration
and additive schemas/tests, leaving existing renderer, generators, planners,
contracts, workers, review archives and transport as their respective owners.
There is no new renderer, YAML engine, logo wash, translation resolver, SQLite
framework or publication client. No production entry point imports it by default.

The proposed storage adapter uses the existing isolated `ContractStore` root,
canonical blobs and Package E transaction/event primitives, with separately
versioned operation indexes. Existing readers are closed: `ContractStore.append`
cannot accept arbitrary new operation documents; neither M1 records nor P3
`RequestContext` will be extended in place. Review a minimal supported storage
bridge during P4/M1 rather than depending on a claimed public API for currently
private `_write_blob`/`_store`. Existing M4/M7/P3 sidecar patterns are the evidence
for feasibility. No production cache migration or competing approval tables.

## Proposed immutable model and acyclic evidence

Use strict bundled JSON Schema with `additionalProperties: false`, independent
integer schema and semantic protocol versions, bounded canonical JSON, exact
hash references, no executable expressions, implicit inheritance or floating
`latest`. Reuse current canonical/strict JSON validation conventions. Do not
pretend numerical parser/resource bounds are visual-acceptance thresholds.

| Proposed object | Required immutable content |
| --- | --- |
| OperationIntent | Operation ID; ADD/UPDATE/RENAME/DELETE; logical subject IDs; requester attribution reference; content revision and previous intent hash; exact base source commit/tree, live identity snapshot and all expected subject/mapping/graph heads; before state and proposed state hashes; category/variant/language choices; content-only request and explicit requested departures; rationale and cancellation target |
| IdentitySnapshotDelta | Existing or assigned stable IDs; semantic family/member and overlay source-role/size associations; exact display/caption/source/local/public names before/after; aliases and tombstones; namespace claims; previous snapshot hash and current subject versions |
| EffectiveProposal | Actual raw intent, effective expanded definitions and serialized jobs; exact contract/registry/rule/exception pins; language/source provenance; renderer/encoding/native dependency/font/asset hashes; private/generated-parent scope; before/after graph references; unsupported/unresolved diagnostics |
| ImpactPlan | Direct/transitive affected outputs, required companion closure, selected languages, retained members, render-needed/reuse/path-only/retire actions; before/after mappings; evidence needing revalidation; all expected dependency/namespace heads; complete membership hash; unresolved scope blocks completion |
| CandidateManifest | Per-output stable ID and role/language, exact mappings, job/spec/render fingerprints, artifact SHA-256 and size/format, owned worker receipt reference, parent artifact hashes; explicit absent/failed/private/reused status and complete required membership |
| CompositionPreview | Intent and effective/impact/candidate hashes; full-resolution candidate hashes; separately hashed thumbnails/contact sheets; default/requested treatments and blocked-default labels; complete companion/language group; typography/layout/readability evidence; preview code/runtime; all material context pins |
| Confirmation / Decision | Exact intent revision, preview/candidate/member/context hashes and selected treatment; explicit confirm/reject/withdraw action; separately attributed submitter and maintainer roles; approved warning/exception scope; original evidence and invalidation conditions; no publication permission |
| Inspection / LocalCommit | Current P3/M7 observations and independently selected heads, positive or blocked technical outcome; explicit local-only apply authorization; exact expected before state/namespace claims; resulting isolated state hash and previous operation event; never an invented operational grant |
| OperationEvent / Tombstone | Append sequence, prior event hash, phase/status, owned candidate/journal references, CAS result/conflict/cancellation reason; retired ID and mappings/aliases/receipts/lineage retained; public-retention default and separately requested deletion scope |

These names specify design responsibilities, not final code signatures. Avoid a
circular hash: intent pins existing base/proposal inputs, not its future approval.
Previews pin intent/effective jobs/candidates; confirmation pins previews; the
maintainer decision pins confirmation and exact preview context; current inspection
and local commit pin the decisions. Evidence events extend an append-only stream
without silently modifying the approved content revision. A content edit creates
the next intent revision; a decision cannot alter its own reviewed payload.

An exception's requested treatment can be previewed before approval only through
an explicitly labeled review-only branch. Preserve a conforming default or label
it blocked; never grant an exception to pass normal validation. After the decision,
bind the exact permitted exception to the identical reviewed job/bytes/context
through an explicit adoption/revalidation companion. Any material delta requires
new evidence; merely adding the subsequent decision reference does not force a
rerender or create a self-referential preview hash. Logo-only M1 preview kinds stay
logo-only; new full composition documents use new kinds/readers.

## Transaction, conflict and recovery protocol

Proposed progression is REQUESTED → VALIDATED → PREVIEWS_COMPLETE →
SUBMITTER_CONFIRMED → MAINTAINER_ACCEPTED → LOCAL_COMMITTED, with BLOCKED,
REJECTED, CONFLICTED, STALE and CANCELLED events. These are operation-local states,
not M7 READY/ACTIVE or publication states. Planning/testing an operation may produce
a blocked report; real accepted/apply transitions require actual external role
attribution and operational prerequisites, currently unavailable.

1. Select the trusted base and current operation/subject/graph heads externally.
   Validate before state and explicit proposal. Reserve candidate namespaces in
   isolated state with CAS; contributor-supplied current-head JSON is not authority.
2. Resolve actual definitions and both graph epochs. Include all affected subjects,
   dependencies and required members in a read set, not just the primary poster.
   Recheck the complete namespace and retained public inventory, including aliases,
   tombstones, private parents and files outside the generated catalog.
3. Generate only approved-for-preview, explicitly bounded candidates in owned
   isolated roots. Stage immutable objects/receipts before the index transaction.
   Partial companions may be retained for diagnosis/resume, never marked complete.
4. Confirm and approve the exact complete preview/membership. Replay current P3
   source/target/authority and M4 consumption plus unchanged M7 prerequisites.
   A stale graph, registry, source, renderer, authority or read-set head blocks apply.
5. In one existing Package E transaction, CAS **all** read/write subject and
   namespace heads, append operation events/decision references and advance the
   isolated definition/mapping snapshot once. Concurrent UPDATE and RENAME of the
   same item cannot both commit; a shared dependency change also conflicts. A
   global catalog revision alone need not invalidate an unrelated operation if
   independently re-resolved effective scope, namespace and all read-set pins agree.
6. Failure before commit leaves no accepted pointer, only unreferenced owned blobs.
   Recovery checks the whole canonical chain, current external heads and original
   receipts; it resumes exact work idempotently or records conflict/cancellation.
   No blind repair, automatic deletion of orphan evidence or takeover of a foreign
   workspace. Reopening the DB does not authenticate the restored head.

Recommended first implementation treats an immutable isolated definition/mapping
snapshot as the atomic unit. Multi-file production Git/catalog application needs
a separately authorized journaled exporter and activation decision; it is not
atomic merely because a SQLite row committed. If later authorized, prepare a
confined worktree from an exact commit, write an owned journal, verify every file
and expected Git head, then expose one new snapshot/commit pointer. Readers never
use partly written snapshots. Cancellation before commit only releases owned
reservations and appends evidence; after commit, reversal is a new compensating
operation with fresh impact and approvals. Remote rollback is Phase 5.

## ADD and complete logical membership

A contributor proposes content under an approved category and enabled design
variant, source provenance and optionally permitted brand background/name and D09
exception requests. The controlled maintainer boundary assigns a new
`category.<uuidhex>` identity once (D06); it is persisted before rendering and
never computed from a display string or destination. Existing identities are
looked up unchanged. Source hash changes are UPDATE, not a reason to mint a new
ID. Duplicate logical intent cannot allocate a second ID on an idempotent retry.

Validate the content allowlist, new PNG/transparency/default-or-exception, approved
source treatment, caption/type/key and exact font/fitting rules after actual
profile/generator/language expansion and final normalization. A requested filename
is only a proposal until confirmed in the authoritative definition/mapping
revision. A new content type/caption mapping or protected style needs a separately
reviewed contract revision/impact decision; ADD does not create one. All existing
English-only restrictions apply even if a translation snapshot contains French.

Build explicit complete membership: logical item, language, white/colour role,
overlay size/branch and generated/private parents as applicable. Not every new
poster implies an overlay or every source directory implies BOTH_REQUIRED. The
selected contracts determine the set. Derive white from a suitable colour master
where permitted; optional separate white must pass the existing comparison/manual
review boundary. Overlay outputs preserve source branch RGB/alpha and both sizes.
No general pure-white cleanup is implied by a `white` directory.

Run translation and category checks, collision/inventory inspection and complete
composition preview. The submitter explicitly confirms all required views and
members; an independent maintainer accepts brand/layout/text/fit, warning and
exception scope. Contract approval, artifact review, isolated operation acceptance,
operator activation, draft staging and merge remain separate decisions. In the
current blocked operational environment, this architecture supports future
isolated tests, not actual new poster additions or the six deferred requests.

## UPDATE and selective reuse

Compare exact before/after effective definitions, serialized jobs and dependency
graphs through `Index.impact` and `compare`. Use per-output material rules from
M6, not the hash of every category's aggregate container, as render dependencies.
Report direct output consumers, transitive parents/children, required companion
closure and unchanged controls. Unknown nodes/unsupported candidate coverage or
family fanout needing per-child proof block a complete/minimal-impact claim.

| Change | Required impact and approval handling |
| --- | --- |
| Source PNG bytes | Include every poster, derived white and both overlay sizes/branches that actually consume the source; new bytes lose historical alpha/exception acceptance unless exact new scope is approved. No background removal. |
| Caption/translation | Re-resolve selected language and caption/template keys; preserve resource/commit provenance and explicit reverification. Relevant resource/comment changes may stale evidence even with unchanged visible strings. Unused resources/languages remain outside scope; do not invent key-only compatibility. |
| Font/size/geometry/effect/variant | Maintainer-controlled contract change and bulk impact approval first. Record exact font/renderer and fit evidence, all affected categories/families; layout exceptions never become automatic shrink permissions. |
| Background | Separate approved brand proposal from locked palettes and source RGB/treatment. Verify lineage, contrast/readability and all consumers; existing historical assignments remain exact. |
| Shared generator/asset/parent | Re-expand actual registered generator, compare full membership and topology on both graph epochs; use real owned parent bytes. A private parent is never a public preview/publication member. |
| Overlay source | Use native transform and required standard/bigger companions; paired source branches remain independent. A poster exception does not change overlay treatment. |

Separate three reuse decisions: unchanged **render inputs** can reuse a verified
owned artifact; unchanged **review material** can retain a decision only with an
explicit current compatibility/revalidation record; unchanged **remote bytes**
need no later upload only when candidate and actual published SHA-256 match.
Path-only changes may reuse render bytes but still need mapping/identity review
and a new owned binding; never edit a receipt to claim it was created for a new
job/path. Pixel equality alone does not preserve stale authority or approval.
Binary-different eligible `renderer_equivalent` candidates remain replacements
for Phase 5 staging; visual equivalence is not synchronization.

## RENAME without identity replacement

Maintain independent display name, rendered caption/key, source filename, local
output filename, public repository filename and historical aliases. A display
edit does not imply changing text or paths. A caption edit may require new render
and layout review. A source path edit with unchanged bytes still needs dependency
and provenance revalidation. Confirm exact new spelling/case/punctuation in the
authoritative source definitions and immutable mapping delta; no slug/title-case
inference or fuzzy lookup.

Persist old/new names under the **same ID**, including generated semantic children
and overlay size roles. Reuse existing M2 IDs as the initial lookup; do not rewrite
the frozen adoption map. Because legacy generators/planners derive some IDs from
paths, a future explicit identity-resolution integration must run before sealed
jobs/dependencies are created and be independently replayed by validators. Never
patch IDs into a sealed manifest afterwards. Default legacy paths stay unchanged;
any protected source/pin maintenance requires its own narrow milestone review.

Check complete local and target namespaces, retained artwork, parent directories,
aliases, reservations and NFC+casefold collisions. Preserve historic Unicode
literally; proposed new names must already be NFC. Allow a case-only transition
only for the same proven old owner under its exact before hash, with no third
party collision. On Windows use a confined owned temporary name and journal for
the local two-step move, verify literal Git tree spelling, and recover from each
step; do not rely solely on case-insensitive filesystem lookup.

Update every affected definition/dependency reference and complete paired output
mapping in one isolated snapshot; no half-renamed companions. An alias is evidence,
not an automatic redirect or permission to resolve a wrong-case new source.
Public artwork is not renamed or removed by a Phase 4 local mapping operation.
It may describe a Phase 5 intent with exact old/new paths; later staging requires
separate explicit remote rename/removal authority and current inventory checks.
The current transport's historical overlay-case migration grant is not reused as
general rename permission. Undo is a compensating mapping revision, never erasure
of the old decision or receipt.

## DELETE with public retention

Default confirmed policy: **removing a definition retains public artwork**. A
local DELETE proposes retirement of an exact definition/mapping, not a remote
delete command. Preserve the stable ID permanently as a tombstone with original
names, revisions, candidate/approval/worker/public response receipts and lineage.
No history is garbage-collected as a consequence of deletion.

Evaluate incoming graph edges on the before graph, proposed removals and retained
consumers on the after graph. Block removal of a required parent, private Awards
intermediate, required white/colour/size companion or shared generated-family
member unless the explicitly approved complete operation resolves every dependent.
Retiring one generated child requires a supported persistent exclusion in its
authoritative family definition; deleting its output row alone will recreate it
on expansion. Shared physical source assets are retained by default; reference
count zero is insufficient authority to delete them.

Keep public mappings occupied while public artwork remains. New use of a retired
name needs a new identity, explicit maintainer mapping/reuse decision and current
inventory proof; it cannot inherit the old brand's approval or overwrite retained
public bytes. Public deletion, if requested, is a distinct exact path/blob/hash/
repository/baseline scope and independent approval deferred to Phase 5. A request
or tombstone does not execute or schedule a remote write. Cancellation/recovery
and rollback preserve the same CAS/journal/history rules as other operations.

## Full composition evidence and visual approval

P4/M3, before ADD/UPDATE acceptance, wraps the existing actual renderer and worker
path, not the logo thumbnail renderer. Review exactly encoded candidate JPEG/PNG
bytes: backgrounds/gradients, alpha treatment, font/text/case, geometry/offsets,
opacity/effects, borders, fitting and all required standard/bigger or white/colour
outputs. Contact sheets/thumbnails are navigation aids; full-resolution artifacts
and receipts remain authoritative. A generated parent is verified before children
and remains private where its established mapping is null.

Pin explicit colours, exact selected source/font hashes, native renderer/encoder/
FreeType/Pillow identity and layout/translation trace, contract/rule/exception,
operation revision and complete membership. Rehash at receipt attachment, submitter
confirmation, maintainer acceptance, recovery and eventual application. Do not
use a resized display thumbnail hash as a candidate artifact hash. Detect changed
dependencies even with unchanged mtime/size. Fixed inputs/environment must reproduce
the approved bytes; renderer/native dependency drift requires a new context.

D09 default-versus-requested views must show the **complete same composition**
for a white-default exception, preserving original source and alpha. An intentional
background exception can retain a blocked default panel with diagnostic evidence;
no fabricated transparent source. Logo correspondence remains measured/manual
until a separately sealed/calibrated/approved policy exists. Readability, clipping,
wrapping, alignment, glyphs and brand identity require complete visual review.
Do not waive all warnings; bind exact measured legacy or individual acceptance.

Longer translations must fit the existing approved rule or remain blocked pending
an explicit font/layout/language contract decision. Playlist retains Bebas Neue
Regular at 154 and captured fitting evidence; historical bounds alone grant no
autoshrink. Era/category differences remain distinct. Actual new-language artwork
is blocked by current English-only packages regardless of a hypothetical preview.

## Phase 3 integration and operation/group boundaries

Use actual M2 translation preflight and M3 destination/inventory evidence and
replay them through M4 `consume`/`revalidate`. Bind exact operation intent/evidence
head through P3's existing request payload/context references, selected language,
subject/output membership and both before/after graph epochs where relevant.
Do not compare M6/M2 definition/job context with M5 identity/definition/job/
exceptions/renderer context; validate each canonical meaning independently.
New full-composition records need operation-layer semantic verification; P3's
opaque review/receipt references do not confer that meaning or authentication.

Existing M4 accepts typed poster requests and historical overlay requests, not a
generic lifecycle request. Prospective overlays need an additive reviewed adapter;
DELETE/empty after-state needs operation-specific before-state and tombstone
checks, not an empty successful P3 cohort. RENAME must verify both old ownership
and new target inventory; new hash pins cannot make a replayed old approval current.
Do not silently widen existing types, historical membership or READY flags to
bridge these gaps. All current operational blockers remain visible.

| Unit | Responsibility; never substitutes for another unit |
| --- | --- |
| Lifecycle operation | One immutable logical intent and atomic local snapshot/read-write set; may span many outputs/parents |
| Visual approval population | Exact policy/material context and complete output membership reviewed together; may be divided by risk with explicit evidence |
| Generation workload | Dependency-ordered bounded jobs; cache/dedup/technical partitioning does not approve missing companions |
| Git transport batch | Resumable technical file/byte limit; no visual or membership authority |
| Publication PR | Separately authorized Phase 5 staging/review boundary, possibly consolidating batches; no automatic merge |

## Open implementation decisions for maintainer review

These are new Phase 4 recommendations; settled D09/P3 policies are not reopened.

| ID | Recommendation and tradeoff | Required before |
| --- | --- | --- |
| P4-D01 | Atomic isolated snapshot + multi-head/read-set CAS, with later reviewed Git exporter. Simpler recovery than in-place catalog edits; needs explicit export/integration later. | M1 implementation authorization |
| P4-D02 | New stable identity registry layered over frozen M2 IDs; semantic child/overlay lookup and explicit planner hook. More integration work than path-derived IDs, but preserves identity across rename without rewriting history. | M2; exact protected-source extension scope reviewed separately |
| P4-D03 | Full final-resolution candidate manifest for every required member; thumbnails optional. More storage than logo-only previews, but review binds actual composed/encoded bytes. No partial-group approval. | M3/M4 |
| P4-D04 | Isolated locally attributed simulation until real authority and approved contracts exist; prohibit operational acceptance/apply meanwhile. Allows tested infrastructure without manufacturing trust. Provider/capture design remains Phase 5 prerequisite. | Any real intake/apply; synthetic milestone work may proceed only when authorized |
| P4-D05 | Preserve retired identities/names and retained public namespace; explicit name-reuse decision rather than automatic reuse/garbage collection. Conservative reservation costs manual review but protects old brands/receipts. | M6 |
| P4-D06 | Journaled case-only local moves and compensating rollback; remote rename/delete remains independent Phase 5 scope. Extra lineage is preferable to in-place evidence mutation. | M6 |
| P4-D07 | Additive prospective overlay/general-candidate adapters with exact declared supported coverage and original guard replay. Unsupported categories stay blocked, not routed through fabricated historical records. | M2/M5 coverage gates |

Numeric visual/logo thresholds, new contract packages/languages and new fitting
policies are not selected here. Production decision-capture authority, external
current-head checkpoint and verification-to-consumption atomicity require a real
protocol and separate review before operational use. Approval of this architecture
or merging its documentation does not authorize any implementation milestone.
