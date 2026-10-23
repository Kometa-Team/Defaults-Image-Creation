# Phase 3 / M5 acceptance implementation dossier

2026-10-23. **Acceptance tests and handoff prepared; M5 acceptance is BLOCKED by
the real historical overlay chain failure `p3m4_graph_review_context`.** M1–M4 are merged.
No claim of production operational readiness is made. Phases 4–6 are NOT STARTED.

## Verified baseline and scope

Fetched current main and independently verified M1 PR #26
`b8d0c1c5ba6bdff7c3e4045d2add505af0417348`, M2 PR #27
`6add7daa21e0d9570c73be9bae9901baa6047244`, M3 PR #28
`f8c5782fa0609fe34642f7b0c121538d2c9f7c4c`, and M4 PR #29
`a30283fb88c6964d40e96a4ab15233592ec92243` merged. Fresh branch:
`feat/lifecycle-phase3-m5-final-acceptance`, based on that exact main.

Reviewed [architecture](PHASE3_DESIGN_PROPOSAL.md), [M1](PHASE3_M1_IMPLEMENTATION.md),
[M2](PHASE3_M2_IMPLEMENTATION.md), [M3](PHASE3_M3_IMPLEMENTATION.md),
[M4](PHASE3_M4_IMPLEMENTATION.md) and the [six-phase roadmap](ROADMAP.md).
Only acceptance tests, evidence fixtures, test-ID maintenance and documentation
are changed. Runtime implementations, schemas, contracts and entry points are
unchanged. The [acceptance report](PHASE3_ACCEPTANCE_REPORT.md) is authoritative
for findings and unresolved failures; this dossier is not an approval receipt.

## End-to-end integration and deterministic evidence

New `acceptance_samples.py` wires actual M1 policy/selection/subject values, M2
translation reports, M3 route/authority/inventory reports, M4 current-context
consumption, isolated immutable archival, reopen and full current replay. Each
stage consumes actual preceding evidence. No result is replaced with a success
boolean. Existing test-only synthetic providers are reused without a live mode.

The full fixture contains five canonical chains: official English, explicitly
mapped user English, user French under a synthetic versioned contract, private
captionless output, and a complete standard/bigger overlay pair. Source/contract
and remote context remain explicit; source and authority positives are simulations.
All original M7 approval gates and false operational flags remain in the outputs.
The archived objects are read back and revalidated before inclusion in the fixture.

Full evidence hash:
`836afeb792e064e78ff91965b1c47a4feca165aab72655aa0cf61581984cc06b`.
The existing six M1 vectors and full M2–M4 fixtures remain unchanged. Both platform
focused jobs must reproduce the entire new value and hash, not just a test count.

The [17-family security matrix](../phase3/tests/phase3-acceptance-matrix-v1.json)
maps every requested attack family to exact maintained mandatory node IDs. Its
own test rejects empty families or references outside the mandatory selection.
New attacks include forged/rehashed translation, stale provenance, reviewed
English fallback hiding missing French, unsupported languages, unapproved M7
packages, official non-English routing, forged owner, absent/expired/revoked
authority, invalid/incomplete inventory, cross-language/Unicode collisions,
foreign subject/output membership, dependency changes, archived revision/authority
replay, partial/corrupt archival and wrong heads, synthetic-as-real claims, and
attempted rendering/network/controller effects.

All **628 previous focused IDs** remain; **27 M5 cases** bring the mandatory
focused selection to **655**. No test is deleted, skipped, xfailed or disabled.

## Fresh complete historical reconciliation

The existing historical test retains every M2/M5/M6/M7 assertion and then invokes
new test-only `final_acceptance.py` over its same freshly verified immutable
records, actual inputs and M6 dependency index. No second whole-library discovery
or graph materialization is introduced. The helper independently reconciles all
14,079 exact records, source/name/exception/member/dependency/evidence hashes,
22 exact packages and all 278 English coverage variants. It hashes the complete
ordered projection and exact names with streaming canonical JSON, preserving
Unicode/casing while avoiding an extra detached whole-library job collection.
Immutable package pins are computed once per package, not per historical output.

The added real overlay-chain check selects an unchanged standard/bigger pair
from these actual historical records and pins the existing M5 nodes/rows in a
small closed projection. It executes M2, M3 and M4 using genuine historical
record/contract/source/name/review contexts and explicitly synthetic remote
authority. It requires technical compatibility while retaining all real M7 and
publication blockers. It does not substitute synthetic graph review hashes for
the actual historical contexts. A failure remains a required failure.

Historical artifacts are exported inside the unchanged `config/ci-validation/**`
upload: `phase3-historical-acceptance.json` and `phase3-historical-chain.json`.
The focused export `phase3-final-acceptance.json` is included by the unchanged
`config/phase3-ci/**` upload. These names cannot masquerade as original group or
collection reports. Head/platform envelopes are separate from canonical evidence.
The final PR records exact-head URLs, conclusions, machine-readable coverage and
both historical projections, including any unresolved real-chain failure.

## Validation, boundaries and changed-file inventory

Local new integration tests: **27 passed**. A full local M1–M5 focused run and the
complete exact-head Windows/Linux pipeline are required for final evidence; the
draft PR records those results separately. All original pytest/unittest IDs,
non-pytest commands, historical assertions, 512 MiB worker-parent safeguard,
15-minute job caps, production pin manifest and mandatory acceptance remain.
No workflow, runner, original selection/baseline, repository setting or runtime
source is modified to make the new acceptance check optional or green.

Complete scope:

* New `phase3/tests/acceptance_samples.py`, `final_acceptance.py`,
  `test_final_phase3_acceptance.py`, `phase3-final-acceptance-v1.json`,
  `phase3-acceptance-matrix-v1.json`.
* Additive historical assertions in `bulk/tests/test_categories_historical.py`;
  its original node IDs and every original assertion are retained.
* Additive `ci/phase3-test-ids.json`.
* This dossier, `PHASE3_ACCEPTANCE_REPORT.md`, `PHASE4_HANDOFF.md`; current
  progress/decision entries in `PHASE3_DESIGN_PROPOSAL.md` and `ROADMAP.md`.

All prior milestone dossiers remain historical. No production Python, YAML,
fonts/logos/artwork, translations, published repository, receipt, M1–M4 schema,
M5 graph kind, M6 package, M7 gate or generation/publication entry point changes.

## Handoff and stop

See [Phase 4 prerequisites](PHASE4_HANDOFF.md) for ADD/UPDATE/RENAME/DELETE design,
stable identities, complete poster previews, dependency-aware impact, immutable
versioning, preservation and separate approvals. This is a checklist, not an
implementation or authorization. The six Timeline Order requests remain deferred
to Phase 6. No Phase 4, 5 or 6 work, actual contract approval, activation, generation,
publication or merge is performed. Any failing acceptance remains explicit and
requires separately authorized correction before claiming Phase 3 completion.
