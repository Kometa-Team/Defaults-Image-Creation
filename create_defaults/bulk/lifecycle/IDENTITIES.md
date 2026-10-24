# P4/M2 isolated identity and impact interfaces

These interfaces allocate planning metadata. They do not accept or execute real
lifecycle operations. All authority/activation/publication flags remain false.
M1's operation protocol, limits, blob format, journal and CAS rules are unchanged.

## Registry

`IdentityRegistry.create(root, identity, inventory=..., expected_inventory_sha256=...)`
explicitly initializes isolated M1 storage. Opening `IdentityRegistry(root, identity)`
only reads and verifies existing records. The complete Phase 3 destination Git
inventory must be pinned, with complete recursive tree closure. An optional
destination root is exact and must exist. This is offline namespace evidence,
not authenticated ownership or current remote authority.

`view()` provides a `RegistryView` and exact `RegistryHead` (snapshot revision/hash,
M1 operation record hash and event hash). `allocate`, `reference` and `revise`
require that exact head and an idempotency token. Repeating the same token and
request returns its existing allocation; using that token for another request
fails. Concurrent requests sharing an old head cannot both commit. A losing
request must reread/retry; it cannot silently substitute a second identity.

Assigned IDs are category-prefixed UUIDs. Semantic keys independently bind
category, parent, child key, presentation and language. Display/caption/source/
local/public names are distinct fields. Original names never change; each
revision retains previous names as reservations. Tombstones reserve metadata
only and cannot be revived. They do not delete definitions or artwork.

Frozen historical IDs are a read-only layer pinned to the original 14,079-member
mapping, registry and 22-package release. A sparse historical reference retains
the actual record hash, original names, variant and semantic membership. It
does not create an adopted output record or infer historical approval for new
bytes. No historical identifiers are reassigned.

Snapshots and the original destination inventory are canonical Package E
content objects referenced by M1 UPDATE/draft records. Registry subject and
evidence heads participate in the same transaction/journal. There is one
`state.sqlite3`, no new approval database, and no private blob/storage calls.
Restart replays every revision, verifies hashes, transitions, immutable names,
semantic membership, full namespace and original inventory. Orphaned content
objects confer no state. M1's bounds remain: 4,096 records, 65,536 head versions,
64 MiB replay budget and 8 MiB JSON objects. Registry membership is capped at
4,096 sparse entries; the frozen library is not copied into every snapshot.

## Candidate adapters

`poster_candidate` reads actual strict YAML and profiles, expands using the
registered Package E generators, resolves persisted child IDs through the
public `Planner.expand` boundary, and invokes the original sealing/planning
method. No sealed manifest is patched. Four generator semantic keys are years,
separator names and rating codes, rather than output filenames. A missing,
ambiguous, retired or substituted member blocks the plan.

Playlist uses its existing M3 prospective validator, including its fixed layout;
other poster designs use the exact M6 effective-job contract validator. The
adapter binds raw and normalized parameters, actual English resources,
definition overrides, source/font/shared assets, renderer, background, exact
output routes and required presentations. Existing historical exceptions can
only be used when the entire captured definition/job context still matches.
Changed content cannot inherit an old compatibility flag.

Composition dependencies require actual owned parent artifacts. No parent JPEG,
historical record or receipt is fabricated to make a plan pass. New caption
types, languages, styles, treatments and exceptions remain blocked. Playlist
mixed-category plans are limited by its existing validator. Generated member
retirement requires M6 and is blocked here.

`overlay_candidate` validates paired standard/bigger source membership across
all 18 branches, exact native boxes, trim, source-preserving transformation,
source bytes and variant. It produces dependency metadata, **not jobs**. Both
legacy overlay planners seal filename-derived IDs without a public pre-seal
identity hook. `jobs()` explicitly fails with
`p4m2_overlay_preseal_identity_hook_required`; impact evidence retains that
blocker. M2 does not modify either legacy planner or invent historical overlays.

The complete machine-readable inventory is
[`PHASE4_M2_COVERAGE.json`](../../lifecycle/PHASE4_M2_COVERAGE.json). It distinguishes
conditional effective-job coverage from overlay relationship-only coverage.
M5 output `variant` retains the job namespace (`base`, `standard`, `bigger`).
M6 contract variants/overlay branches remain separately bound by registry entries,
assignments and rule nodes. These values are never treated as interchangeable.

## Impact

`preview_impact(before, after)` replays supported actual candidates, reuses the
M5 graph/compare implementation and returns deterministic direct/transitive
dependency paths, companion closure, before/after mappings, affected outputs,
unaffected material-context proof and blockers. A historical starting point
must match the entire fixed M6-bound graph, not a caller-selected hash. Scoped
candidate nodes are overlaid on that immutable epoch; unrelated rows remain.
Unknown dependency impact stays blocked. Family/row fanout warnings are resolved
only by actual complete expanded-child replay and comparison.

`request_record` constructs an unaccepted M1 draft request with complete subject,
dependency, namespace and registry-evidence read/write closure. It does not append
or apply it. Its subjects remain M1's synthetic coordination keys derived from
the stable IDs; real item mappings reside in the pinned M2 evidence.
`analyze` independently verifies the committed M1 record/event, current registry,
all request/context hashes, exact membership/closure and current consumed heads.
`revalidate` repeats those checks and requires byte-identical pinned evidence.
Caller compatibility flags and self-asserted hashes confer no acceptance.

Whole-library read-only queries may exceed a single M1 record's 4,096-member/
head limits. Constructing such an operation record fails explicitly; M2 does not
raise those limits or invent a multi-record acceptance protocol.

## M3 handoff

M3 may consume an exact registry head, actual candidate manifest/effective
definitions, pinned inputs, stable member/companion mappings and freshly replayed
impact evidence. It must independently retain Phase 3 authority/currentness
checks and all 22 outstanding exact package approvals. Full composition,
preview generation, contributor/maintainer decisions and operation execution
remain outside M2. Review a minimal overlay pre-seal identity hook before using
new overlay jobs; do not patch sealed manifests. Refreshing a destination
inventory or growing beyond registry bounds requires a separately designed
version/migration decision, not a permissive fallback.
