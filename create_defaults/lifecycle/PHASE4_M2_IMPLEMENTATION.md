# Phase 4 / M2 implementation and review dossier

2026-10-23. **M2 IN PROGRESS, pending final validation and maintainer review.**
M1 is COMPLETE through merged PR #32 at
`5deffb587c92d746a4611939c918ae0e6471ee30`; planning PR #31 is merged at
`c33f792992ee704150799fe16536a64630fd8964`. M3-M7 and Phases 5-6 remain NOT STARTED.

## Implemented scope

The [interface documentation](../bulk/lifecycle/IDENTITIES.md) specifies the
registry, schema, replay, public planner adapter, impact model and limits.
The [complete coverage matrix](PHASE4_M2_COVERAGE.json) inventories 21 poster
categories, 278 existing variants across 22 packages, four actual generators
and 18 overlay branches. These are explicitly conditional capabilities, not
blanket prospective or operational acceptance.

| Approved architecture | M2 implementation |
| --- | --- |
| P4-D01 | Canonical immutable identity snapshots in existing Package E objects, referenced by M1 atomic records/heads/events; original M1 protocol and limits retained |
| P4-D02 | Persisted category UUID allocation, semantic parent/child/presentation keys, independent exact names, immutable historical reference bridge |
| P4-D03 | Actual strict expanded definitions and original planner-sealed jobs; pinned inputs/renderer/variants and reasoned before/after M5 impact; composition remains M3 |
| P4-D04 | All acceptance/application/activation/publication flags false; no authenticated provider, approval integration or executor |
| P4-D05 | Original/current names, append-only aliases and tombstone reservations; complete frozen/external namespace; no file rename/delete or name release |
| P4-D06 | Registry updates use unchanged M1 CAS/recovery; no artwork transaction executor or compensation machinery |
| P4-D07 | Separate Playlist, M6 effective-poster, registered semantic-generator and overlay relationship adapters; unsupported cases fail explicitly |

The six-phase roadmap, D01-D09, all Phase 3 authority decisions, original
production definitions/designs, visual approvals, historical exceptions and
receipts remain unchanged. The six Timeline Order requests are not processed.

## Identity and impact evidence

IDs survive changes to display/caption/source/local/public names, casing and
valid Unicode. Namespace reservations use NFC+casefold collision detection while
preserving literal historical names. New paths must be portable NFC. Exact
idempotent retries return the persisted ID; concurrent semantic allocations
cannot both commit. A stale registry head fails even if proposed bytes match.
Restart verifies the original complete inventory, every immutable snapshot,
transition, record and event. Changed source bytes cannot inherit old approvals.

Historical IDs are not recomputed. The mapping remains
`6d1a49062208e8361227942549a4adafb0f2fed63c2f3a9a63c7860845ab876f`;
the M6-bound historical graph remains
`93b01e2261249185bd06982a9cb0823a61628104d327958cedefd97788a39d7d`.
New candidates are never constructed as historical adoption records.
M5 job variants (`base`, `standard`, `bigger`) and M6 category-design variants/
overlay branches are distinct namespaces. Reconciliation independently checks
both against the actual frozen mappings and assignments; candidate graph output
rows preserve M5's job-variant convention.

The original four generator implementations remain unchanged. Semantic lookup
runs in an isolated subclass at the public expansion boundary before the
original `plan` method seals jobs. Year, separator and rating variables identify
children independently of filenames. Actual private parent artifacts are still
required; missing parents do not get synthetic JPEGs or receipts.

M5 comparison computes direct/transitive impact, changed effective definitions,
required companions, mappings, complete dependency read/write closure and causal
paths. Unaffected output material contexts must match exactly. Unresolved
dependencies remain blockers; complete family expansion must be replayed before
resolving the existing conservative family provenance diagnostic. M1-bound
evidence independently verifies both record/event pins, request membership,
registry head, consumed heads and exact candidate hashes on every replay.

## Explicit limitations and M3 handoff

* New overlay **relationships and source impact** are supported; new sealed
  overlay jobs are blocked by `overlay_preseal_identity_hook_required`. Existing
  planners seal path-derived IDs. No sealed IDs are patched and no historical
  companion is fabricated. A separately reviewed minimal pre-seal identity hook
  is needed before M3 can construct such jobs.
* Poster coverage is English-only and limited to existing caption types, source
  routes, designs and complete required presentations. Unknown categories,
  generators/versions, new languages, individual treatments and new exceptions
  remain blocked. Playlist retains its existing stricter selection limitations.
* New derived-white composition and source quality/preview approval are not
  inferred from metadata. Existing accepted historical exceptions are usable
  only in their entire unchanged captured context.
* Generated-member retirement is blocked pending M6. Library-wide queries may
  exceed the unchanged per-record M1 bounds; operation-record construction then
  fails rather than widening limits or inventing an acceptance protocol.
* The namespace inventory is an immutable offline baseline, not a live ownership
  provider. Refresh/migration beyond a registry's fixed namespace is not exposed
  as an unreviewed mutation API. All real Phase 3 currentness/authority checks,
  22 missing exact contract approvals, composition and review integration remain
  independent blockers.

M3 can consume exact registry heads, stable mappings/companions, original
planner manifests, effective definitions, pinned source/font/renderer/contract
inputs and freshly revalidated impact evidence. Before/after candidates require
their immutable owned inputs to remain available for replay. It must not treat
M2 metadata completeness as artwork approval or operational readiness.

## Validation and CI acceptance

All original 204 M1 test IDs remain mandatory; M2 adds 54 focused IDs, for 258.
The new tests cover stable names/paths, aliases/tombstones, concurrency, strict
schemas, forged history, corruption/restart, actual four-generator expansion,
actual Playlist and representative other-category adapters, all 18 overlay
pair families, raw/profile/language bypasses, missing dependencies/assets,
transitive fanout/cycles, unchanged outputs, stale operation/registry heads and
substituted impact evidence. No test invokes rendering or publication.

Both existing mandatory P4 jobs collect and execute the full maintained ID set.
Canonical registry/event/record replay must match the committed vector on both
platforms. The acceptance verifier also requires two exact-head historical
reports produced by the existing shared historical fixture, without a second
full capture. It checks all 14,079 identities/records/mappings, 14,077 public
references, 22 packages, 278 variants, 190 protected production files and 299
frozen source pins. Missing, stale, cancelled or substituted proof fails closed.
The aggregate verifier remains stdlib-only. Existing workflow, timeouts,
512 MiB worker-parent safeguards and all old acceptance gates are unchanged.

The draft PR's exact-head checks and exported reports are the authoritative final
execution evidence; pending or partial runs are not a pass. Local early timing
found repeated frozen namespace scans; the implementation now caches only the
verified immutable base, while every live snapshot and CAS transition is still
checked. No assertion or historical protection was removed for runtime.
The development local suite executed all 258 tests successfully in 708.79s.
Its wrapper rejected mixed-head evidence because later corrections were pushed
during that run; it is not final-head acceptance evidence. Final execution must
be produced in an unchanged checkout and pass the wrapper as well as pytest.

A development hosted Windows contracts run hit the unchanged legacy concurrent
first-write path resolution in `ContractStore._write_blob`/`common.confined`
(436 passed, one failed). That same original group passed in the earlier run.
No frozen production/test source or path guard was modified to suppress it.
Final-head acceptance still requires that entire group and all other mandatory
checks to pass. Any recurrence remains an explicit CI reliability finding,
not an M2 approval waiver or permission to widen historical source pins.

## Changed-file inventory

New runtime modules under `bulk/lifecycle/`: `basis.py`, `identity_models.py`,
`identities.py`, `coverage.py`, `candidates.py`, `overlay_candidates.py`,
`impact.py`; new `schemas/identity-impact-v1.schema.json` and `IDENTITIES.md`.
Original M1/storage/planner/generator/renderer/definition/contract source files
remain unchanged.

New focused files under `phase4/tests/`: `test_identities_impact.py`,
`test_ci_identities.py`, `m2_samples.py`, `historical_m2.py` and
`identity-canonical-v1.json`. Existing `test_ci_foundations.py` gains additive
M2 producer/aggregation fixtures; its original IDs and negative controls remain.
Existing `bulk/tests/test_categories_historical.py` adds reconciliation over its
already verified historical context. `ci/phase4.py` and `ci/phase4-test-ids.json`
add mandatory M2 evidence/IDs. Documentation: this dossier,
`PHASE4_M2_COVERAGE.json`, and current status/decision entry in `ROADMAP.md`.

No production source protection update, workflow change, artwork generation,
definition edit, approval, merge, live provider or publication is included.
