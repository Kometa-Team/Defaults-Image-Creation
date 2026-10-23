# Phase 3 / M4 implementation and review dossier

2026-10-23. **P3/M1–M3 merged; M4 implemented pending maintainer review.** Phase 3
remains IN PROGRESS. P3/M5 and Phases 4–6 remain NOT STARTED.

## Verified baseline and authorized scope

Fetched latest main and verified prerequisite merges: M1 PR #26
`b8d0c1c5ba6bdff7c3e4045d2add505af0417348`, M2 PR #27
`6add7daa21e0d9570c73be9bae9901baa6047244`, M3 PR #28
`f8c5782fa0609fe34642f7b0c121538d2c9f7c4c`. The fresh branch
`feat/lifecycle-phase3-m4-evidence-consumption` starts at that exact main.
Existing work and ignored migration evidence are preserved.

The [approved architecture](PHASE3_DESIGN_PROPOSAL.md),
[M1 foundation](PHASE3_M1_IMPLEMENTATION.md),
[M2 preflight](PHASE3_M2_IMPLEMENTATION.md),
[M3 destinations](PHASE3_M3_IMPLEMENTATION.md) and
[six-phase roadmap](ROADMAP.md) remain authoritative. Original M1 immutable
records/storage, M5 Snapshot/material-context/impact interfaces and M7
readiness/storage/transition boundaries were inspected before implementation.

## Delivered components and exact bindings

The [API, replay and storage specification](../bulk/contracts/evidence_consumption/README.md)
documents the complete calling contract and diagnostics. Code is isolated in
`contracts/evidence_consumption/`, with no production import, command or hook.

| Component | Delivered behavior |
| --- | --- |
| Current evidence consumer | Re-enter real M2 expansion/source replay and M3 cohort/target/authority replay using independently selected pins and explicit current inputs |
| Subject and M6 scope | Stable subject, full output identities and exact paths, contract/rules/variant/design/member/exception hashes and complete required companions |
| M5 scope | Existing strict Snapshot, actual effective-definition/review-context binding, selected dependency closures, original exception nodes and evidence lists; no new graph kinds |
| Freshness | Exact resources, required-key coverage, provenance and verification context; exact destination, inventory, grants, permissions, expiry/revocation context; no clock/TTL/implicit refresh |
| Request/review references | Additive immutable request revision/context, independent current head, exact original records and native Package E receipt/review hash revisions; evidence never grants approval |
| M7 inspection | Exact typed current 22-package inventory; unchanged readonly inventory reports all missing approvals and independent gates; no controller transitions or readiness bool intake |
| Canonical companion | Closed additive schema with deterministic hashes, scoped binding, explicit negative results and simulation labeling; every operational flag stays false |
| Optional archive | Explicit isolated M1 ContractStore sidecar, immutable blobs/triggers, exact-head CAS and previous-context chain, transactional events and safe orphan-only interrupted failure |

`chain_compatible` means replayed technical companions agree; source currentness,
external authority and M7 approval remain independent blockers. Synthetic positives
set simulation fields only. Real source/ownership providers are absent. Every
outcome retains `technical_eligible=false`, `publication_authorized=false`,
`production_enforcement=false`, `ready=false` and `active=false`.

No original approval or frozen record schema is extended, no receipt is rewritten,
and no M7 gate trusts submitted compatibility JSON. One explicitly loaded immutable
M6 inventory can be reused within an inspection session; the consumer verifies
its closed release/package pins and continues to report historical compatibility
as not freshly checked. This removes repeated full-inventory setup without an
authority cache or an extra full historical capture in the focused job.

## Selective impact and replay protection

The attestation binds every selected subject, policy, source/authority context,
M2/M3 evidence, M5 closure, M6 rule/exception/member and request/review/receipt
reference. A material change invalidates its scoped binding even when rendered
strings or image hashes are unchanged. Replay with an old independently selected
request/evidence head fails. The consumer never fetches, refreshes or re-signs an
upstream observation.

The encompassing M5 graph hash is retained as provenance but excluded from
`binding_sha256`; selected closures, evidence lists and companions remain included.
An unrelated output/node can produce a new observation without invalidating the
selected scope. Unused translation resources/languages preserve M2 evidence.
Explicitly re-resolved unchanged YAML rows likewise preserve scope after another
row changes. A stale file-pinned Resolution is rejected rather than repaired.
Unknown graph impact remains conservatively blocked.

Request contexts carry exact ID/revision/previous-context and payload/subject
pins. Optional archival checks immediate revision and report/context heads with
CAS. It validates old chains before append and all canonical indexed sidecars on
read. Partial writes or transaction interruption cannot advance the head. Original
referenced artifacts remain in their own archives; the sidecar stores their exact
provenance references and never claims to authenticate them. An external current
head/trust boundary is still needed to detect external rollback or stale selection.

## Test and CI inventory

The mandatory focused selection retains **all 529 M1–M3 IDs**, adding **99 M4
cases** for **628 total**. No tests are removed, skipped, weakened or silently
deselected. New controls cover all 20 requested families:

* Compatible simulation and missing/foreign/partial M2/M3; independently wrong
  hashes, rehashed forgeries, subject/language/policy/contract/variant/membership
  and complete overlay-pair scope.
* Selected resource/comment changes with unchanged visible strings, changed
  commit/provenance/context, unrelated languages/resources/YAML rows/graph nodes,
  and selected dependency/review/exception/evidence changes.
* Changed destination inventory, owner/branch/root/grant, permission scope,
  revocation/expiry/context, and unavailable real authority/source verification.
* Replay across request revisions/expected heads; native Package E review/worker
  hash references; missing/substituted/foreign reference bytes; typed M7 inventory
  substitution; original current Playlist contract remaining unapproved.
* Interrupted/partial archive blob and transaction writes, recovery, corruption,
  missing/noncanonical/substituted sidecars, namespace versions and immutable
  indexes; full canonical fixture parity across Windows and Linux.
* Cold import and guarded warm evaluation/replay with forbidden clocks, network,
  images, workers, state constructors/writers and activation controller access;
  actual read-only M7 inventory consultation without submitted compatibility.

The [full canonical M4 evidence](../phase3/tests/evidence-consumption-v1.json)
hash is `b2fc04d5908fa392dfed840a7a75579f67cd4fd74f996fb1e40e8a232ae4144c`.
All six M1 vectors and full M2/M3 fixtures remain unchanged. M4 uses synthetic
metadata plus a small unchanged real Playlist selection, with no image generation
or additional whole-library historical fixture.

Reproduce using `python ci/phase3.py run`. Final focused results, exact commit,
all 21 Windows/Linux checks, per-job counts/runtimes, original and additive ID
reconciliation, fresh historical integrity and 512 MiB worker-parent evidence are
recorded in the draft PR acceptance report after the complete exact-head run.
Prior-head, local or frozen evidence never substitutes for that hosted run.

The established bounded workflow, runner, legacy selection, non-pytest commands,
15-minute per-job timeout and protected production pins remain unchanged. The
maintained focused ID file adds every M4 case to both platform jobs, already direct
prerequisites of mandatory **Validation acceptance**. No branch settings change.

Required fresh regression invariants: **22 packages / 278 variants / 14,079 outputs /
14,077 public references**, two private Awards outputs; 299 historical source pins;
all **190 protected production files**; zero unexplained differences; all 22 real
approvals still missing; zero real READY/ACTIVE states. No accepted exception,
filename, source asset, translation, renderer or runtime behavior changes.

## Complete changed-file inventory

* New `bulk/contracts/evidence_consumption/`: `__init__.py`, `engine.py`,
  `models.py`, `storage.py`, `evidence-v1.schema.json`, `README.md`.
* New `phase3/tests/`: `consumption_samples.py`, `test_evidence_consumption.py`,
  `test_consumption_archive.py`, `test_consumption_boundaries.py`,
  `evidence-consumption-v1.json`.
* Updated additive `ci/phase3-test-ids.json` only.
* New this dossier; progress-only `PHASE3_DESIGN_PROPOSAL.md` and `ROADMAP.md`,
  preserving original policy decisions, historical entries and six roadmap phases.

No other tracked file may change. In particular no production source, original
M1–M3 module/schema/fixture, M5 graph/impact interface, M6 package, M7 gate, workflow,
artwork/font/definition, translation, publication destination or receipt changes.

## Explicit P3/M5 handoff and unresolved operational boundaries

M4 is implemented pending maintainer review; P3/M5 needs separate authorization.
M5 should perform the approved final Phase 3 historical/adversarial acceptance and
CI handoff using this isolated consumer, current exact companions and original
historical safeguards. It must not turn simulation compatibility, local archival
or CI into a contract approval or operational grant.

Live trusted source reverification, authoritative source advancement, externally
authenticated owner/grant/permission/revocation observations, externally selected
current request heads and their verification-to-consumption atomicity remain real
integration dependencies. None is invented here. M1/M3 still have no real positive
authority result; any future extension/provider requires separate review. Real
non-English coverage still needs separately approved versioned contracts. All
independent typography/layout/visual/brand/submitter/maintainer/operator reviews
and production integration remain outstanding where applicable.

No P3/M5, Phase 4–6, lifecycle operation, live provider, remote writer, production
activation, deferred Timeline Order processing, artwork generation/publication or
merge is authorized. Stop after the green draft PR for maintainer review.
