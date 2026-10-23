# P3/M4 explicit context and evidence consumption

This opt-in metadata API consumes current M1/M2/M3 companions and existing M5/M6
context. It is not wired into any production caller, renderer, lifecycle operation,
publication path or activation transition. Every result has `technical_eligible`,
`publication_authorized`, `production_enforcement`, `ready` and `active` **false**.

## Controlled inputs and trust

`consume(inputs, language_policy, destination, destination_inputs, request_context,
graph, *, expected_language_policy_sha256, expected_destination_sha256,
expected_request_context_sha256, expected_graph_sha256, implementation,
expected_release_sha256, references=(), cancel=None)` returns a
`ConsumptionAttestation`. Each `TranslationInput` contains the current real
M2 `PosterRequest` or `OverlayRequest`, requested language, detached snapshot,
selection, report, independent expected report hash, explicit source context and
optional verifier. `destination_inputs` contains M3's policy/evidence/inventory,
their independent pins and explicit authority context/verifier. M4 constructs
the M3 cohort itself; overriding `items` or `language_policy` is rejected.

The controlled caller must select **current** request and evidence heads and
independent expected pins. Copying expected hashes from submitted JSON does not
authenticate them. M4 supplies no external intake/provider, clock, TTL, network
refresh, credentials or real-success authority extension. An explicit historical
snapshot or unchanged hash cannot establish live source/owner currentness.

Load the unchanged `Implementation` explicitly through
`Implementation.load(expected_sha256=RELEASE_SHA256)`. One immutable instance may
be shared inside a read-only inspection session. M4 checks its exact type, closed
release pin, complete 22 package pins and selected packages. This avoids repeated
full package loading per item without caching authority or claiming a fresh
historical compatibility audit. No caller-provided compatibility/READY boolean
is accepted. Existing M7 `inventory(implementation)` reports all 22 missing
approvals, zero READY/ACTIVE and the fresh-audit/integration/operator blockers.
M4 neither invokes the controller nor modifies a gate.

## Binding and replay

1. Re-enter M2's actual source-pinned loader/expander, contract/variant and
   source-selection replay. Full required-key coverage, raw bytes, Git provenance,
   language policy, source context and independent verification status must match.
2. Bind stable subject hashes and complete exact output identities/paths to the
   immutable request revision. Inspect the supplied independently pinned M5
   `Snapshot` using its existing validator and per-output `material_context`.
   Definitions, paths, category/kind, review contexts, required companions and
   historical exception evidence must agree. Capture selected design, rule,
   member and exception hashes separately from their package provenance.
3. Re-enter M3 with the reconstructed full cohort and explicitly selected
   policy, target, repository/owner/branch/root, full Git inventory, independent
   authority observation, permissions, revocation and expiry context. Exact
   replay rejects any substituted report, even a self-consistent rehashed one.
4. Read actual M7 inventory, retaining every independent approval, historical,
   visual, provenance, intake and activation prerequisite. Companion compatibility
   does not satisfy these gates.

The additive closed [schema](evidence-v1.schema.json) describes `RequestContext`
and `ConsumptionAttestation`; original M1 records and M5 graph kinds are unchanged.
`RequestContext` pins stable request ID, revision, previous context, original
payload hash, exact selected subjects and optional request/review/receipt/exception
references. Its externally selected hash is the current request head. The
consumer is not a request editor or state machine.

References include role, exact native ID/revision, canonical blob hash, subject
and reviewed-context hashes. Supply their exact canonical bytes as `references`.
Original M1 exception records use the unchanged reader and must match package,
variant, identities and material context. Existing Package E worker receipts use
their native `job_id`/`job_fingerprint` and self-pin; reviews may use their existing
variant ID/validation fingerprint. These hash revisions are not converted into
invented integer history. Other explicitly pinned ID/revision objects remain
opaque data. This inspection never authenticates a receipt, review actor or
decision, verifies an image, or replaces the original owned-artifact/approval
validation. Referenced decisions add an explicit unauthenticated blocker.

Missing M2/M3 yields negative completeness findings; malformed or stale supplied
evidence raises `BulkError` without a partial successful report. Interrupted or
oversized input also yields no report. `chain_compatible` describes only replayed
technical companions; it never means source/authority or M7 approval. A positive
synthetic chain is explicitly `simulation=true`, `simulation_eligible=true` and
retains synthetic/currentness and M7 blockers. Real unavailable authority remains
fail-closed. Captionless/private outputs waive no M7 prerequisite.

`read_attestation(raw, expected_sha256=...)` verifies structure and the external
pin only. `revalidate(attestation, expected_sha256=..., **current_inputs)` performs
all current replay/inspection again. Never treat deserialization as validation.

## Selective freshness

All material/context fields contribute to `binding_sha256`. Changed request
revision, language/policy, selected source bytes (including same-text comments),
commit/provenance/verification context, target/grant/inventory, selected package,
variant, exception, effective definition, dependency closure or evidence reference
invalidates replay. No implicit source or request refresh is performed.

M5's enclosing graph hash is recorded as provenance but excluded from the scoped
binding. An unrelated graph node/output can therefore change without invalidating
selected evidence. The per-output closure, membership, companions, exception hashes
and evidence lists remain bound. `revalidate` returns a **new current observation**
when only this enclosing graph hash changes; it does not rewrite the old report.
Unrelated languages/unused resources stay outside M2's scoped projection. When a
shared YAML container changes, a caller must explicitly supply a freshly resolved
snapshot; unchanged selected rows preserve their material context. No stale
file-pinned `Resolution` is silently repaired. Unresolved graph diagnostics block
compatibility conservatively, because their impact cannot be proven unrelated.

## Optional isolated archival

`storage.Archive(root)` explicitly opens a separate M1 `ContractStore` namespace;
it is never called by `consume` or `revalidate`. It reuses Package E atomic
exclusive content-addressed blobs, transactions, events, isolation checks and
immutable triggers. The additive `phase3_consumption_schema`/`phase3_consumption`
index is version 1. Existing receipts and approval/activation tables are untouched.

`append(report, context, expected_head_sha256=..., expected_context_sha256=...)`
requires exact typed canonical objects, current context pin, immediately following
request revision and exact previous context/report heads. It checks the existing
chain before appending. A crash during blob creation or before transaction commit
leaves, at worst, unindexed orphan blobs; no head advances. Retrying exact bytes is
safe. `history(id)` verifies every indexed canonical object and linked context.
Corrupt, substituted, partial, missing or noncanonical sidecars fail closed.

The archive retains the complete companion/context hashes and scoped provenance,
not a duplicate of every source artifact. Referenced immutable source/M2/M3 records
must remain available in their original archives and be independently revalidated
before reuse. Local archival cannot authenticate external evidence, establish
currentness or supply an external anti-rollback checkpoint. The only new event is
`phase3_evidence_archived`; it confers no approval, activation or publication.

Parser bounds reuse the original 8 MiB/depth-40 JSON limit, M5's 128 MiB snapshot
limit and at most 20,000 selected subjects/outputs. These are resource bounds,
not visual/authorization tolerances. No original CI/resource guard changes.

See the [implementation dossier](../../../lifecycle/PHASE3_M4_IMPLEMENTATION.md)
for tests, changed-file scope, CI acceptance and the separately authorized M5 handoff.
