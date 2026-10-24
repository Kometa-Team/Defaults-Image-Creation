# Phase 4 / M5: isolated ADD and UPDATE transactions

2026-10-24. **M5 IN PROGRESS pending final-head validation and maintainer review.**
Base `47e69a59fd1c306789457250ef6493bdfef7fc17` is maintainer-merged M4 PR #35.
Planning PR #31 and M1-M4 PRs #32-#35 are merged. Branch:
`feat/lifecycle-phase4-m5-add-update`. M6-M7 and Phases 5-6 are NOT STARTED.
P4-D01-D07, D01-D09 and all historical exceptions remain unchanged.

## Scope and composition of the coordinator

`bulk/lifecycle/operations.py` defines the closed, versioned immutable
`DefinitionSnapshot`, `Transaction`, explicit adapter gate, measured `propose`
and native `preview` orchestration. M2 `IdentityRegistry.allocate` remains the
only new identity allocator: assigned UUIDs and semantic keys are persisted
before the original loader/expander/planner seals an actual candidate. M2
`poster_candidate` validates contributor content and the effective expanded
definition against existing M6 contracts. `propose` uses M2 `request_record` and
`analyze`, then `preview` delegates to the unchanged M3 native compositor. There
is no independent loader, generator, graph, renderer or production entry point.

The caller explicitly supplies current Phase 3 inputs and collects M4's exact
submitter confirmation and separate maintainer decision. The coordinator does
not fabricate either. `Transaction.prepare()` prepares structural snapshot data;
it cannot commit and does not claim that a hash establishes authority.
`apply.commit_synthetic` performs complete current verification under the same
owned Package E immediate write transaction as commit. `commit_operational`
always rejects: independently authenticated providers, capture/integration and
all 22 exact contract approvals remain unavailable.

All M5 records retain `simulation=true`, `record_only=true`, `authenticated=false`
and false real operation/application/artwork/contract/READY/ACTIVE/enforcement/
publication flags. `isolated_committed=true` refers only to an immutable proposed
definition in a disposable synthetic trial, never a production catalog addition.
The exact live M3 `CompositionTrial` and independently populated M4 synthetic
authority capability are required. No arbitrary root, actor string, locally
archived grant, dictionary, callback or provider-shaped object can supply real
authority. The operational path fails before storage or rendering.

## Explicit adapter coverage

| Category / generator | M5 transaction coverage | Evidence / boundary |
| --- | --- | --- |
| Genre | Existing M6 logo/single variants, English, actual strict poster definitions | Native single ADD and minimal logo-source UPDATE; full default-white/requested-source-preserving D09 review; exact names and identity retained |
| Network | Existing M6 logo variants requiring white and colour together, English | Native paired ADD; all members and both presentations share one atomic marker; interrupted member-head writes expose neither |
| Playlist | Blocked | Approved fixed prospective layout and P3 generic historical captured-fit adapter differ; no contract/style waiver or P3 production-source change |
| Overlays | Blocked at prospective P3 consumption | M2 relationships and M3 standard/bigger native previews remain supported upstream; P3 OverlayRequest is historical-only, so M5 rejects rather than fabricating historical records |
| Generated families / registered generators | Blocked for M5 acceptance | P3 re-expands with its original identities; no universal stable-child adapter or invented historical adoption record |
| Aspect, AudioLanguage, Awards, Based, Chart, ContentRating, Country, Decade, Franchise, Network non-logo/non-paired, Genre non-logo, Resolution, Seasonal, Separators, Streaming, Studio, SubtitleLanguage, Universe, VideoFormat, Year, and any other category/shape | Not added to M5 acceptance | M2/M3 capabilities remain factual upstream capabilities; there is no catch-all category acceptance |
| Non-English or unknown contracts/variants | Blocked | Existing English-only and separately reviewed versioned language-policy boundaries remain |

The gate is category **and** source kind **and** required presentation shape.
Every admitted variant must still pass its existing exact closed contract, native
layout/source checks, complete membership and current P3/M4 replay. Native tests
exercise the selected existing Genre single and Network paired cohorts; this is
not a claim that every historical variant has been regenerated or operationally
approved. No new contracts, policies, numeric visual tolerances or exceptions
are introduced.

## Immutable snapshots and ADD semantics

`schemas/transaction-v1.schema.json` is closed and versioned. Canonical JSON and
SHA-256 reuse existing Package E conventions and the 8 MiB object bound. It pins:

* Exact reviewed M1 operation/event/revision and original intent bytes.
* Before/proposed effective definitions, graph, source-file pins and native plan.
* Current registry entries, exact names/casing/Unicode, variants and identities.
* Expected authoritative snapshot per member and actual M2 impact closure.
* Complete M3 composition, selected appearance, final encoded-byte objects and
  original durable worker receipt references. Both reviewed views remain pinned.
* Exact M4 bundle/head and independent submitter/maintainer grant linkage.
* P3 attestation and independently selected observation pins for exact retry
  identity. Archived observations never become a freshness or authority provider.

ADD requires every selected authoritative snapshot to be absent and rejects a
mixed ADD/UPDATE population. A previously committed independent baseline may be
supplied to M2 impact analysis. Every baseline member and complete dependency
scope must match actual isolated committed state. This proves common immutable
dependencies unchanged and permits genuinely disjoint additions without an
unsafe rebase of stale heads. The namespace and semantic identity must already
have passed M2's persisted reservation/collision rules. No partial member becomes
authoritative, even if all its blobs have already been written.

## UPDATE, impact and preservation

UPDATE is selected by existing stable identity, with an exact previous snapshot
for every revised output. Its old effective definition and selected dependency
closure must match that authoritative snapshot, not a caller-selected filename
or historical receipt. M2 calculates direct/transitive impact and required
companions; M3 verifies the complete candidate membership and original planner
dependencies before any commit. Output identity, category/variant and local/public
mapping changes are blocked, as are display/caption renames. Membership removal
or addition cannot become implicit DELETE/RENAME; those require M6.

The minimal supported UPDATE replaces transparent logo bytes at the exact same
source filename, revises the existing M2 hash reservation and creates a fresh
complete M3/P3/M4 chain. `freeze_before` rehydrates the original committed input
objects into an owned trial preimage and independently replays the original M2
candidate without changing its canonical bytes or graph. It copies original
archived source/font bytes; it never renders old artwork or falls back to another
source filename. Both source and output names, category/variant and stable
identity remain unchanged. A source-path change is explicitly blocked as M6
RENAME work. Replacing source bytes cannot consume the old review.

Unaffected outputs retain their existing snapshot, exact encoded bytes and
immutable receipt references. M2's material dependency comparisons prove their
scope unchanged; restart verification checks their archived bytes, decode
properties and durable receipt/spec hashes. They are not regenerated or assigned
new decisions. Affected review evidence must be rebuilt; old evidence and event
history are retained. Existing M3 global registry pins are not relaxed: an old
review whose pinned registry changed may require upstream revalidation even if
its artwork looks unchanged. Integrity preservation does not assert current
live approval after a material context change.

## One atomic commit point using original M1 CAS

There is **no new database, SQL table, snapshot index or mutable head cache**.
Snapshots and image/receipt objects use existing immutable Package E blobs.
`apply._append_m1` is a narrowly local M5 bridge around the original frozen M1
`_replay`, `_changes`, `successor`, event schema and budget validators. It assembles
the same original rows and events inside the caller's existing Package E
transaction. A regression independently compares its entire journal, heads,
records and canonical events with an original `OperationStore.append` archive.
The four frozen M1 files, original schema and golden vectors remain byte-exact.
This bridge does not introduce alternative CAS rules or modify production pins.

After actual current M4/P3/M3 replay, M5 appends one deterministic M1 successor
containing the immutable snapshot reference for **every** subject. It adds the
matching `phase4_isolated_commit` Package E event in the same transaction.
Original M1 read/write-set checks run immediately before row insertion; all
original and new restart checks run before SQLite COMMIT. Exact grants and
cancellation are checked again after expensive replay and before commit.

The reviewed intent remains immutable at its exact original revision. The M1
successor increments its content revision because an evidence reference was
added, and retains M1's `draft`, record-only semantics. It is an isolated commit
marker, **not a newly approved operational revision or a widened M1 state**.
The snapshot pins the reviewed intent and all human decisions, avoiding circular
hashes. No caller-supplied read/write head is silently refreshed.

## Conflict, cancellation, failure and recovery

M1 subject/dependency/evidence/namespace CAS, independently pinned snapshot
heads, current registry and review checkpoints are all mandatory. Shared-source
changes or a competing subject update invalidate the affected request. Separate
operations on unrelated subjects can proceed when their complete baseline and
shared dependencies are proved unchanged. M2 semantic and namespace collisions
still reject one competing allocation; same-operation concurrent retries must
produce one commit only. Original SQLite locking/timeouts remain unchanged.

A supported `threading.Event` is checked before work, after review and before
commit. Functions/booleans are not accepted cancellation objects. An inactive
M1 operation or withdrawn, stale, unconfirmed or rejected M4 review cannot commit.
Expired/revoked/reissued/substituted grants fail independently; a grant revoked
during expensive replay is checked again before exposure.

Fault injection covers snapshot/record/event blob staging, record/member-head/
journal/commit-receipt indexes, immediately before commit and lost success
acknowledgement immediately after commit. Pre-commit exceptions roll back all
indexes and authoritative heads; immutable orphan blobs are harmless and kept.
Post-commit interruption is recovered as the same immutable result, without
applying twice. Old public artwork and production definitions are never touched.

`recovery.recover` opens read-only and independently replays the complete original
M1 chain plus exact M5 marker/event pairing, snapshot lineage, original M4
decision linkage, complete byte objects and original durable receipt/spec hashes.
Missing/corrupt/partial or substituted evidence fails closed. It reports pending
coordination records and retains orphan objects; it never automatically retries,
cleans, repairs, authenticates or applies anything. Opening partial/foreign state
does not migrate it. A prior successful exact retry returns
`currentness=integrity-only-prior-commit`; that is a historical result query,
not renewed approval or permission to apply changed source bytes.

## Tests, resources and mandatory CI

The first native Genre smoke completed composition, P3 consumption, both exact
review stages, isolated commit, independent restart and exact retry in 433.63 s
on the development Windows host. The initial 33 schema/CAS/CI controls passed in
67.66 s. These are preliminary development measurements, not final-head results.

New focused tests cover positive ADD/UPDATE/paired membership, disjoint and
competing requests, concurrency, every commit boundary, cancellation, stale
heads, roles/grants, changed source/font/style/type/destination, corrupt/missing
artwork/receipts, retry substitution, orphan recovery, cold imports and blocked
operational/unsupported paths. Native rendering and M3 validators remain real.
Owned fixture SQLite backups isolate test cases; that is fixture setup, **not**
the application's recovery mechanism or permission to mutate immutable history.

The existing 23-job workflow remains unchanged, with all original 15-minute job
caps and resource guards. M5 adds three explicit mandatory commands to the exact
M4 plan: atomic tests to categories, adversarial tests to smoke, concurrency and
paired native tests to core. Prior measured Windows runtimes were 1m48s, 1m28s
and 1m50s respectively; previous review/generation jobs were already much fuller.
The one-file plan extension is sealed in `ci/phase4-m5-maintenance.json`, chained
from the unchanged M4 extension. No Phase 3 assertion, original command/test ID,
workflow, timeout, memory limit or source-protection pin is changed.

The foundation vector preserves its complete ordered M1-M4 prefix and appends
M5 metadata/CI controls. `ci/phase4-transaction-test-ids.json` explicitly maintains
disjoint native groups. Entire P4 collection must equal the exact union of all
producers. Acceptance requires six successful exact-head/platform/group reports,
two native isolated-commit/restart/retry proofs, all false real-authority flags
and comparison with the independent original M3 native pixel producer. A failed,
cancelled, skipped, missing, stale, substituted or partial producer fails closed.
The original 1,671 pytest IDs, 155 unittest IDs and 12 CI controls remain required.

All native generation remains in disposable synthetic trials under original
512 MiB worker, 1 GiB total, one-worker, 120-second attempt/zero-retry limits.
The original 512 MiB worker-parent safeguard remains required. No historical
image is rendered as a test fixture; the original shared capture alone validates
14,079 outputs, 14,077 public references, 22 packages, 278 variants, 190 protected
files, 299 adoption pins, exact historical mappings/exceptions and immutable
receipts. No competing historical capture is added.

Final tested commit, complete changed-file inventory, exact Windows/Linux job
links/counts/durations, original integrity/resource evidence and mandatory
acceptance result are recorded in the draft PR after actual completion. Pending
CI is not described as success.

## M6 handoff and stop

M6 may consume immutable proposed definitions, retained byte/receipt references,
stable identities, exact snapshot heads and complete history. It needs separate
authorization for RENAME/DELETE mapping/tombstone execution and compensating
operations. M5 does not implement those, integrated M7 acceptance, any production
YAML exporter, catalog writer, activation or publication transport. Actual
ownership/source authentication, exact contract approvals and blocked prospective
adapter work remain separate prerequisites. The six Timeline Order requests,
Default-Images and Phases 5-6 remain untouched. Stop at the green draft PR for
maintainer review; do not merge or begin M6.
