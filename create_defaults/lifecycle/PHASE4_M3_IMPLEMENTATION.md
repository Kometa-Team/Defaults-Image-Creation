# Phase 4 / M3 composition implementation dossier

2026-10-23. **M3 IN PROGRESS pending exact-head validation and maintainer
acceptance.** M1 and M2 are COMPLETE through merged PRs #32 and #33. Baseline
`33a20c1f5b7a73d672793f1700d48b566789ad32` includes planning PR #31 and M1 merge
`5deffb587c92d746a4611939c918ae0e6471ee30`. M4–M7 and Phases 5–6 are NOT STARTED.

## Scope and existing engine reuse

M3 produces synthetic, isolated complete pixels and immutable evidence, never
human approval, real lifecycle execution, activation or publication. P4-D01–D07,
D01–D09, all historical exceptions and the six-phase roadmap remain unchanged.
The six deferred Timeline Order requests are not processed.

`composition.py` orchestrates the public original `Planner`,
`tasks_from_manifest` and `PersistentWorkers` with its default `workers.compose`.
That unchanged compositor calls `create_poster` or `overlays.render`. Existing
PNG inspection and `typography.evaluate(proposals=False)` validate inputs and
actual native text geometry. White-wash executes inside the original renderer;
there is no second layout, font-fitting, background-removal or image engine.

Audited `generation.generate` always constructs its own planner and runs its
broader colour-registry intake/preflight. It does not expose a stable expanded-ID
planner injection interface. M3 reuses its public planning/task/pool stages
directly, with explicit colours and a closed M2 candidate, rather than copying
generation or inventing colour tolerances. Native worker receipts remain the
proof of actual encoded output bytes.

Two narrowly additive integration gaps are addressed:

* New overlay native protocol assembly resolves stable IDs **before** sealing
  jobs, with the exact M2 branch/source/geometry and original transform. It does
  not patch already sealed path-derived IDs. M2's original metadata blocker is
  retained; M3 independently constructs and verifies the native plan.
* M2 `_assignment` required `source` in contributor content even for contracts
  that forbid contributor control of placeholder/composition sources. The
  additive, unpinned lifecycle adapter now permits that source to be derived
  from the persisted registry and actual hashed job input/dependency. Supplying
  a forbidden source still fails contract validation; any supplied permitted
  source must match the registry. `check_job` and all style checks are unchanged.
  No production-pinned source, contract or historical receipt is modified.

## Supported and blocked compositions

Five synthetic cohorts use real contracts, definitions, semantic identities,
M1 request revisions and M2 graph/impact replay:

| Cohort | Complete native members per view | Treatment |
| --- | --- | --- |
| Playlist | 1 JPEG, RGB, 2000×3000 | Default white wash and separately labeled pending source-preserving request |
| Genre | 1 JPEG, RGB, 2000×3000 | Existing captured font/layout/gradient; default and requested treatments |
| Network | 2 JPEGs, RGB, 2000×3000 | Required white/colour counterparts; distinct closed design variants |
| Overlays | 2 RGBA PNGs | Original source colours/alpha, standard/bigger boxes, exact source basename/case |
| Separators | 1 generated JPEG, RGB, 2000×3000 | Original registered generator, stable semantic family/child and locked composition source |

All other M2-covered English closed designs are conditional adapters, not a
claim that every category was rendered or every future request is eligible.
Missing glyphs, actual clipping, unsupported customization, unresolved random
colour, new source transparency/quality diagnostics, missing companions,
historical-reference rendering and unknown adapters block completion. No new
numeric visual tolerance or automatic fit/repair is introduced. Historical
exceptions remain valid only in their unchanged frozen scope; new assets cannot
inherit them. Intentional opaque/transparency exceptions await their own reviewed
adapter; M3 does not fabricate approval for them.

The unchanged native parent scheduler is exercised with real generated parent
and child JPEGs, including missing/substituted receipt and missing-byte controls.
`render_parent_inputs` supplies owned prerequisite bytes before M2 seals a child
plan; those prerequisites are explicitly not complete composition evidence.
Final M3 composition includes and checks every dependency member/receipt.
Arbitrary new private-parent filenames remain blocked where an existing M2/M6
composition contract has only exact historical source routes. No fake historical
record, unapproved route expansion or reserved-name bypass resolves that limit.
The native DAG fixture proves the underlying parent interface and is **not**
presented as an accepted new category composition. Further source-route design
requires explicit review, not automatic M4 implementation.

## Immutable schema, membership and storage

`composition-v1.schema.json` contains closed versioned `composition-evidence`
and `composition-bytes` kinds, separate from logo-only previews. A complete root
pins the exact M1 record/event/revision, freshly replayed M2 candidate/registry/
impact/graph, exact definitions, requested treatment context, all required
identities/companions/parents, native manifests, source/font bytes, implementation
and native encoding environment. Per-member hashes bind full encoded bytes,
geometry/mode, mappings, source origins and actual durable worker receipts.
Original M2 before-mappings are explicit prior-state references; no missing prior
artwork hash is represented as a verified image. ADD fixtures have no prior image.

Canonical objects use the M1 `SidecarStore` public API and the existing single
Package E `state.sqlite3`. Binary bytes are losslessly base64-encoded in bounded
canonical content objects. No new database, approval table, mutable candidate
index or operation-state transition is created. The complete root is written
last; interruptions leave only orphan objects and never a complete group.

Archive reopening independently checks current contracts, M1 heads and read set,
M2 semantics, all actual archived inputs/output hashes, native full geometry,
expected definitions and exact native planner output. It verifies receipt/spec
hashes against the existing durable worker records, not caller-provided hashes.
Dependency verification rehydrates archived bytes in owned temporary storage and
uses the real planner's parent checks. Missing, extra or asymmetric membership,
altered definitions, forged receipts, logo/thumbnail substitutions and even a
forged full-size canvas cannot satisfy this evidence.

Full-resolution gallery exports contain the exact archived bytes, evidence JSON
and SHA-256 labels. They are confined to fresh ignored CI evidence children.
Images displayed at reduced CSS size link to the full artifact; no thumbnail
serves as composition evidence. All previews remain visibly unapproved.

## Reproducibility, resources and isolation

Every cohort is rendered twice into distinct owned output roots, checking final
encoded SHA-256 equality and zero cache hits. The renderer pins Python, platform,
Pillow/font libraries, source implementation, JPEG/PNG settings and native
FreeType/JPEG/zlib/RAQM versions. Cross-platform reuse is blocked even when bytes
match. CI reports actual Linux/Windows per-member hashes and differences; no
perceptual equivalence or arbitrary tolerance substitutes for equality.

Trials allocate OS temporary roots and copy approved fonts/shared support assets;
all submitted artwork is synthetic. No destination repository is accessed.
The original worker limits remain: one worker in these trials, 512 MiB per worker,
1 GiB total, 120-second attempt limit, zero retries. Original worker-parent memory
tests and all other repository safeguards remain mandatory. New metadata bounds
are 32 members, 5 MiB per binary object, 64 MiB unique archived bytes, and the
existing 8 MiB canonical JSON object bound; these are resource limits, not visual
approval thresholds. Owned trial outputs are removed at teardown; full-resolution
CI review artifacts are retained separately.

## Validation and mandatory CI

The preliminary four-composition local smoke run passed **4/4** in **571.71 s**:
Playlist 233.52 s (including cold historical metadata loading), Genre 117.69 s,
Network 142.82 s, Overlays 76.56 s. This development measurement exposed redundant
candidate replay; M3 removed only the replay already performed by M2 `revalidate`.
It does not remove a validation boundary. These are preliminary measurements,
not final-head acceptance evidence.

M3's 64 exact IDs are explicitly partitioned in
`ci/phase4-composition-test-ids.json`: 17 pixel/reproducibility IDs and 47 security
IDs. Existing mandatory People and review jobs execute the respective commands
after their original tests. No workflow, timeout, branch-protection setting,
original pytest/unittest ID, historical fixture, assertion or source pin changes.
The foundation producer still executes every original 204 M1 and 54 M2 ID, plus
15 new mandatory CI rejection controls. A complete P4 namespace collection must
equal the disjoint union of all maintained selections: 337 IDs per platform.

`Validation acceptance` requires all four exact-head/platform M3 group reports,
every collected/executed ID, zero focused skips/xfails, native byte/replay/resource
proofs and actual cross-platform comparison. Missing, failed, stale, cancelled or
substituted evidence fails closed. Verifiers use only the standard library.
Artifacts use distinct names under the already uploaded `config/ci-validation/`
namespace; original report selectors remain unchanged.

The existing shared historical job, without another capture or historical
rendering, continues to prove all 14,079 outputs/14,077 public references,
22 packages/278 variants, exact mappings/exceptions/receipts, 190 protected files,
299 adoption-source pins and unchanged Phase 3 safeguards. Original historical
evidence remains `61ca06372033f1a6f8d566251fee4bd807ec66e4048de2505dae3c47512d0cc2`.

Final commit, complete changed-file inventory, local results and all exact-head
Windows/Linux job links/runtimes/counts will be recorded in the draft PR after
validation. This document does not claim pending CI or maintainer acceptance.

## M4 handoff

M4 may consume the immutable full-composition reference, exact request context,
member bytes and native receipt proofs. It must add separately authorized
authenticated submitter confirmation and maintainer decisions with fresh evidence
consumption. M3 grants neither role, real contract approval, READY/ACTIVE state,
operation acceptance nor publication. No M4 code or real lifecycle executor is
included. All live authority, contract-approval and production-integration blockers
remain in force.
