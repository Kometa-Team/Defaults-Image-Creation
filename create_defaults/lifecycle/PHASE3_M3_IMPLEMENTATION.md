# Phase 3 / M3 implementation and review dossier

2026-10-23. **P3/M1–M2 merged; M3 implemented pending maintainer review.** Phase 3
remains IN PROGRESS. P3/M4–M5 and Phases 4–6 remain NOT STARTED.

## Baseline and scope

Fetched latest main and confirmed PR #24 `78464d2d051dc5da5f305bc4fd9f03868999636f`,
PR #25 `9022c7c7639f3a2238e5941ec79cc250e4a8ca85`, PR #26
`b8d0c1c5ba6bdff7c3e4045d2add505af0417348`, and PR #27
`6add7daa21e0d9570c73be9bae9901baa6047244` merged. The fresh branch
`feat/lifecycle-phase3-m3-destination-safeguards` starts from that exact current
main, preserving existing work. No prior milestone branch is used as its base.

The [approved architecture](PHASE3_DESIGN_PROPOSAL.md),
[behaviour audit](PHASE3_EXISTING_BEHAVIOUR_AUDIT.md),
[M1 foundations](PHASE3_M1_IMPLEMENTATION.md),
[M2 preflight](PHASE3_M2_IMPLEMENTATION.md) and
[six-phase roadmap](ROADMAP.md) remain authoritative. P3-D02/D03 routing and
authority restrictions are implemented without changing actual category language
coverage, original filename mappings, contracts or production behavior.

## Delivered components and semantics

See [API, diagnostic, trust and inventory specification](../bulk/contracts/destination_preflight/README.md).

| Component | Delivered behavior |
| --- | --- |
| M2 bindings | Exact subject/M2/policy/contract/rules hashes, unchanged language, output membership; M2 technical/category blockers remain blocking |
| Group membership | Complete selected subjects/outputs; M6 overlay standard/bigger and historical pair mapping; private outputs retain null targets |
| Routing | Official numeric IDs/owner scope is English-only; English/non-English user targets require explicit mappings and independent personal ownership; no default fallback/prefix |
| Authority consumption | Unchanged M1 verify interface plus independently observed ID/principal/permission/target/inventory/group/issuer/expiry/revocation context; default unavailable |
| Git inventory | Actual commit/tree object hashes and full reachable subtree closure, independently bound baseline; symlink/Git-link metadata retained without following |
| Paths and collisions | Exact source names, safe relative paths, case/NFC aliases, roots, branches, proposed and existing file/directory/symlink conflicts; no automatic overwrite or rename |
| Attestation | New closed versioned canonical schema/model, per-output diagnostics, completeness/currentness/context and dependency hashes, full explicit-input replay |

M1 intentionally has no real authorized-success result and no live ownership
provider exists. M3 preserves that architecture: real `technical_eligible` is
fixed false. Only the provider under the **test tree** returns synthetic-only
scope observations; complete positive controls can set `simulation_eligible`.
M3's production package imports no synthetic provider. Policy classification is
separate from independently verified repository identity. No route label, hash,
actor string, URL or synthetic result authorizes publication.

Required logical draft capabilities (`contents:read`, `contents:write`,
`pull_requests:write`) describe future permission evidence, not OAuth/token scope
configuration. Personal user ownership is checked by numeric principal/owner IDs;
organization/delegated user destinations remain unsupported. Official exact-ID
scope still requires a grant. Adding real authentication/success is a separate
future reviewed decision; no provider/API/credential integration is fabricated.

M3 binds independently selected M2 evidence and retains its restrictions. It does
not repeat source verification, authenticate arbitrary self-selected hashes,
consume readiness or invoke an activation controller. M4 must eventually combine
fresh companions through a controlled boundary with all existing gates. This PR
does not implement that combined evaluation.

Inventory source pages cannot claim completeness with a boolean: all reachable
Git objects are verified. Missing pages produce explicit incomplete findings;
bad objects fail. Existing-file collisions block even for identical bytes. New
paired designs lacking exact companion assignments fail closed. Entirely private
groups require no remote evidence; tests cover both actual private Awards
intermediates from real M5 definitions without inventing destinations.

## Validation and compatibility requirements

The maintained focused list contains **529 tests: all 387 M1/M2 IDs plus 142 M3
cases**. Positives/negatives cover all language routes; official aliases/renames;
forged actors/owners/booleans/results; unavailable, revoked, expired and
insufficient grants; branch/root/path scope; incomplete or tampered Git trees;
native Git encoding parity; exact/case/Unicode/root/cross-language conflicts;
unsafe encodings and portable paths; overlays and actual private intermediates;
missing or foreign M2 contexts; immutable evidence replay; changed baseline with
unchanged tree bytes; interruption/bounds; cold import and warmed
network/clock/filesystem/image/worker isolation.

The [full canonical M3 fixture](../phase3/tests/destination-preflight-v1.json) hash
is `bf626ea610bcaba2904ac99638dece81ab166ce1d18a8c652c891c68fbfc7896`.
Both platforms must reproduce the complete value and SHA-256, with all six M1
vectors and M2 fixture unchanged. No extra full-library historical capture is
added to focused tests; only small real definition selections and private Awards
metadata are resolved. M3 itself renders nothing and performs no filesystem IO
after lazy schema loading.

Run `python ci/phase3.py run`. Final exact commit, all 21 required Windows/Linux
checks, per-job pass/fail/skip counts and times, original/additive ID reconciliation,
historical and resource results are recorded in the draft PR's final acceptance
report after its complete final-head run. Prior-head/local results do not replace
that evidence. The workflow and CI runner/selections remain unchanged, with all
new tests required by existing **Validation acceptance**. No repository settings,
15-minute timeout, 512 MiB worker-parent check or integrity safeguard changes.

Local validation passed 529 focused tests with no skips and complete ID
reconciliation; compilation, whitespace, 37 relative documentation links and
byte-for-byte preservation of the permanent six-phase roadmap also passed.
Final-head hosted evidence remains separate and is recorded in the draft PR.

Full regression must retain **22 packages / 278 variants / 14,079 outputs / 14,077
public references**, all 190 protected files and 299 historical source pins; zero
unexplained differences; 22 real approvals missing; zero real READY/ACTIVE states.
No actual source artwork, fonts, definitions, translations, filename, runtime
entry point, publication destination or frozen historical receipt changes.

## Complete changed-file inventory

* New `bulk/contracts/destination_preflight/`: `__init__.py`, `authority.py`,
  `bindings.py`, `engine.py`, `inventory.py`, `models.py`, `paths.py`,
  `evidence-v1.schema.json`, `README.md`.
* New `phase3/tests/`: `destination_samples.py`, `test_destination_preflight.py`,
  `test_destination_inventory_paths.py`, `test_destination_isolation.py`,
  `destination-preflight-v1.json`.
* Updated additive `ci/phase3-test-ids.json`.
* New this dossier; status-only updates to `PHASE3_DESIGN_PROPOSAL.md` and
  `ROADMAP.md`, retaining all approved policies, historical entries and six phases.

All prior M1/M2 schemas, interfaces, code and fixtures are unchanged. No protected
maintenance pin is needed. All implementation changes are isolated opt-in files;
there is no production import or integration.

## Explicit P3/M4 handoff and limitations

M4 needs separate authorization. Its controlled caller must revalidate the exact
selected M2/source companions, M3 group/target/baseline and policy/context hashes
before any combined readiness decision; a self-hashed JSON report is not trust.
It must preserve independent contract approval, source/typography/layout/visual
checks, exact output membership, missing real authority/currentness and M7 gates.

Live authenticated repository/ownership/permission/currentness providers and any
real-success interface extension remain unimplemented and require separate review.
No arbitrary TTL, wall clock, automatic fetch, OAuth, tokens, live Weblate,
organization/delegated integration, remote writer or credentials are supplied.
Selected Git metadata proves integrity, not live upstream currentness or ownership.

Official mapping changes and new real non-English category contracts require
independent versioned policy/contract review. Unknown new paired membership remains
blocked. Standard/bigger outputs are validated together but transport/review/PR
grouping is not implemented by M3. No M4 readiness consumer, M5 final acceptance,
contract approval/activation, Timeline Order processing, Phase 4–6 work or merge
is authorized. Stop after this draft for maintainer review.
