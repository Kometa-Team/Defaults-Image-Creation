# Phase 4 / M6 — identity-preserving mappings and retained definition retirement

Implementation branch: `feat/lifecycle-m6-rename-retirement`. Baseline:
`d6b039788315f2198304cf05f7efea5addc271c9`, including merged M5 PR #36 at
`46e1334504fcdd598e0c34fcd45612ff58e91074`. Earlier milestone documents' future
tense describes their planning baseline. M1–M5 are merged; M6 is under validation,
M7 has not started, and Phases 5–6 remain NOT STARTED.

## APIs and supported scope

`bulk/lifecycle/mappings.py` provides closed, versioned `MappingPlan` values,
`prepare`, `propose`, `commit_synthetic`, read-only `recover`, explicit
`recover_local`, and exact-record `cancel_synthetic`. `retirement.py` validates
incoming dependencies and required companions and creates immutable tombstones.
`mapping_moves.py` journals moves of copies inside an operation-owned isolated
state directory. No command exports production YAML or contacts a destination.

Execution consumes actual committed M5 snapshots, source hashes and encoded-byte
receipts. Consequently its supported committed cohort remains M5's assigned
English Genre single-logo adapter. It does not reinterpret loose YAML or an
uncommitted candidate as an existing definition. Retained-artifact history is
separate from the active definition graph, including an empty post-DELETE graph.
No fake historical poster is constructed to obtain a Phase 3 attestation.

Nonvisual RENAME can independently change display metadata, the definition lookup
key, source spelling with identical PNG bytes, or local/public filenames. The
permanent ID, semantic parent/key/presentation/language, variant and original
names remain immutable. Category routes cannot change. The actual compositor's
existing filename function checks the proposed definition; the local filename
and explicit public basename must have exactly that spelling. No slug or title
case is inferred. New spellings must be NFC and pass existing portable-path,
casefold, full frozen/inventory namespace, directory and retained-alias checks.
Source aliases and previously used definition keys also remain occupied.

Changing rendered captions/translation keys, styles or other material fields
fails closed for complete composition/translation review. A definition lookup
key is distinct from its immutable logical ID and from its rendered caption's
translation key. Neither a display edit nor a filename edit silently edits text.

## Atomic state and evidence

No new SQL tables, database, approval provider or mutable mapping index exists.
The plan, original M4 typed decisions, tombstones and new M2 registry snapshot
are immutable canonical Package E objects. An M1 proposal uses M2's unchanged
subject/dependency/namespace coordination keys. Its commit marker and the M2
registry successor share one original Package E immediate transaction, original
M1 CAS/replay, index limits and immutable journal. One failure rolls back both.

The original live `SyntheticReviewAuthority` must separately authorize exact
submitter-confirmation and maintainer-approval records for the plan hash. The
same M4 decision type is reused for mapping review, with the immutable plan as
the reviewed bundle/context; this is not a fabricated complete-artwork review
bundle. Roles, grant identity, expiry and revocation are checked again before
commit. Mapping-only review cannot approve a caption/style change. All flags
remain synthetic, unauthenticated, not applied, not READY/ACTIVE and not
publication-authorized. Before opening a writer, the M6 adapter projects the
verified M5 graph into the original M3 trial capability checks, preserving its
lifetime, root, offline and source constraints. Matching a mutable cache path
alone cannot establish ownership. `commit_operational` uses the existing unavailable
authority boundary and always rejects without writes.

Recovery replays M5 and M6 commits in their shared M1 journal order. It checks
the Package E commit cross-index, original encoded images/receipts, complete
dependency closures, prior registry snapshot and exact resulting entries. An
uncommitted reservation edit cannot be substituted for an applied definition.
Old immutable M5 snapshots and all earlier evidence remain readable. M5 cannot
reuse a renamed/retired identity or an affected pre-rename source dependency
through its old transaction adapter. Unrelated M5 history remains independent.

## Local moves, cancellation and compensation

A durable prepare event binds the plan, exact old/new/intermediate spellings,
member, archived object and image hash before staging. Only copies from the
verified immutable image archive enter `state/m6-owned/<operation>/<member>/`.
Neither production sources nor original renderer outputs/receipts are moved.

Every filename move passes through an operation-owned intermediate. Exclusive
hard-link creation followed by unlink avoids overwriting an occupied target on
NTFS and Linux. Recovery detects both intermediate states and interrupted
link/unlink states. Equal bytes alone do not establish target ownership;
unexpected paths, hashes, reparse points or external hard links block recovery.
Literal directory entries and Git index spellings distinguish case-only changes
on Windows. Committed copies must have the exact new spelling and approved hash.

Before a mapping commit, explicit recovery restores the old spelling; after a
commit it verifies/finishes the new spelling. It does not retry an operation or
recreate an approval. Pending moves block competing operations until recovery
and retry or explicit exact-record withdrawal. Implicit error recovery touches
only the failing operation. Withdrawal retains its evidence and records a new
M1 cancellation with existing CAS; it cannot cancel an already committed change.
A committed reversal is a separately reviewed RENAME that names the compensated
plan and restores its exact old names. Original commits/aliases remain retained. Concurrent retries of the same move
serialize staging under the existing write lock; they cannot race an unfinished
preimage copy. M6 event counts/bytes retain the existing M1 archive bounds, and
unchanged recovery observations are idempotent.

## DELETE and retention

DELETE retires only definitions in isolated state. It retains archived/public
artwork references, encoded bytes, original receipts, aliases, original names,
stable identities and audit evidence. Tombstones pin the selected entry revision,
operation and retained artifact evidence. M2's existing transition validator
rejects tombstone edits and identity/name recycling. Frozen and retired public
names remain occupied even when the active definition graph is empty.

Deletion blocks incomplete companions, required retained consumers/children,
private output parents, unresolved impact, and expanded generated children whose
parent has no supported persistent exclusion. There is no source cleanup,
remote deletion, remote rename, destination writer or publication operation.

## Validation and remaining boundaries

Tests use native M3 composition, M4 review and committed M5 encoded receipts;
the renderer is not mocked. They cover independent names, Unicode/punctuation,
case-only Git spelling, occupied and historical aliases, source ownership,
schema tampering, CAS/concurrency, two-stage authority, interruption at both move
legs, atomic registry rollback, withdrawal, compensation and retained tombstones.
Scoped dependency controls use actual frozen standard/bigger overlay IDs and
source hashes, without pretending they form an operational historical cohort.

The protected workflow, frozen original test selections, M1/M4 sources, all 190
production members, original 512 MiB worker-parent safeguards and 15-minute job
limits are unchanged. The existing mandatory Windows/Linux workflow still owns
the original 14,079-output, 14,077-public-mapping, 22-package, 278-variant and
299-adoption-pin acceptance proofs. M6 does not duplicate that historical capture.

An additive read-only workflow runs explicitly maintained, disjoint M6 selections
for names, security, recovery, concurrency and cold restart on both OSes. Every
job also collects the complete M6 namespace. Its acceptance check requires every
platform/group report, exact PR head, implementation/schema/ID hashes, every
collected/executed node and complete passing phases. Missing, cancelled, skipped,
xfail, failed or substituted results fail closed. No old workflow/pin is changed.
Repository administrators should require **Lifecycle M6 acceptance** alongside
**Validation acceptance**; no branch-protection setting is changed by this PR.

Measured first development run: native setup 333.58 s; the original 90 s cold
restart subprocess limit proved insufficient. Restart has its own bounded group
and a 300 s subprocess bound; the 15-minute CI limit remains unchanged. Final-head
local/remote results and the complete changed-file inventory are recorded in the
draft PR after execution; pending checks are never represented as passing.

Known unsupported execution cases: real authority/current ownership; historical
catalog export; generators/family exclusions; paired poster and overlay commits
whose existing prospective Phase 3 adapters are unavailable; material caption or
style changes without complete composition review; UPDATE of a renamed mapping
through M5's old adapter; and all physical source cleanup/remote operations.
These fail closed and retain identities/evidence rather than synthesizing missing
contracts, approvals, mappings or receipts.

## Inherited main integrity blocker

The first full workflow at `eddee0a80ef72548ff63de32878ac6766f709026`
(run `40164857538`) exposed four protected-source mismatches already present in
base `d6b039788315f2198304cf05f7efea5addc271c9`: the Defaults normal/canary
requirements and People DDColor/rembg requirements. All four last changed in
merged dependency PR #23, commit `06e3bc5959600d1bf5c5cec86f49b9ef5f5b198c`.
M6 changes none of those files, the protected manifest or its verifier. The
original workflow correctly fails closed. Full Validation acceptance cannot be
claimed until that inherited dependency/provenance issue is separately resolved.
No replacement pins or relaxed checks are introduced by M6.

Windows testing also exposed `Path.resolve()` canonicalizing old/new case-only
journal paths to the same spelling. M6 now validates confinement separately and
retains literal paths; a small Windows/Linux negative regression covers this
without weakening link ownership or byte checks. A completed competing commit
returns the same existing `Conflict` type as a changed CAS head; stale plans are
still rejected and no read set is silently refreshed.

## M7 handoff

Consume the immutable mapping/tombstone and retained-artifact projections in the
integrated operation acceptance matrix. Review the supported adapter boundaries
before extending them; do not label a blocked adapter as READY. Reconcile active,
retired and retained public sets, exercise combined ADD/UPDATE/RENAME/DELETE
histories and preserve all original historical/resource/security proofs. Any
future caption change must traverse M3/M4/P3; any publication requires Phase 5
authority and transport. Stop at M6 maintainer review. No M7 implementation,
production activation, merge or artwork publication is authorized here.
