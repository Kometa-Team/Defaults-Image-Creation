# M7 isolated activation safeguards

This module has no production caller, enforcement hook, activation flag,
publication command or authenticated decision intake. Default CLI inspection
does not construct Store. The 22 real packages are implemented and historically
compatible after a fresh audit; their exact-hash approvals are **missing**.

```sh
python -m create_defaults.bulk.contracts.activation
python -m create_defaults.bulk.contracts.activation missing-approvals
python -m create_defaults.bulk.contracts.activation audit --report config/m7-audit.json
python -m create_defaults.bulk.contracts.activation validate-proposal --proposal proposal.json --proposal-sha256 EXACT_SHA
python -m create_defaults.bulk.contracts.activation state --state-root EXPLICIT_ISOLATED_ROOT --identity synthetic.overlays
python -m create_defaults.bulk.contracts.activation simulate --state-root NEW_EMPTY_ISOLATED_ROOT
```

`audit` uses the existing M2/M5/M6 full read-only pipeline. Optional
`--object-root`, `--dependency-snapshot` and `--dependency-sha256` reuse explicitly
pinned immutable evidence; physical inputs and definitions are still rechecked.
No missing object is downloaded, fabricated, repaired or regenerated. `--report`
uses the existing confined immutable report writer. No implicit report or state
directory is created by default inspection.

`validate-proposal` checks an externally selected hash and exact implemented
package. It reports structural validity separately from activation eligibility;
it cannot authenticate the proposal's registry, compatibility or source claims.
The missing authenticated intake and operational authorization remain blockers.

`simulate` is JSON-only and explicitly synthetic. It creates an isolated
ContractStore, exercises IMPLEMENTED through ACTIVE, then rolls back to
SUSPENDED, retaining history. Actual package hashes cannot enter this harness.
Its simulated principals are `synthetic-maintainer` and `synthetic-operator`;
they are not members of the real M1 maintainer allowlist. A simulation registry
is not an approved operational M1 registry.

## Exact authority and existing records

No equivalent activation state machine existed in M1: ContractStore archives
typed records but grants no authority. M7 adds state revisions in the **same**
Package E SQLite database, atomic immutable objects and event transaction. It
does not modify Store migrations, M1 records, M4 approvals or old worker receipts.

The additive `ApprovalBinding` is a companion to an unchanged M1
`ContractApproval`, not an alternative approval system. It binds:

* Exact selector/category, kind, version and canonical contract SHA-256.
* Exact resulting registry SHA, M1 approval receipt SHA and material
  compatibility attestation SHA, plus review evidence references.
* Trusted decision event identity, actor, authorization-context SHA, decision,
  scope, UTC timestamp and expiry.

The resulting registry references the M1 receipt, not the companion envelope;
there is no circular hash. A **future authenticated intake adapter** must capture
the real decision, verify current maintainer authentication/authorization and
immutable event provenance, reconstruct the external `TrustedDecision` mapping,
and re-enter unchanged `RegistrySnapshot.load` for every selected variant. It
must also verify current material compatibility, evidence ownership and complete
coverage, then bind this envelope. The approved registry must be externally
selected, never inferred from its own JSON. No such adapter is available in M7.

Consequently `Controller` uses `UnavailableAuthority` for all operational
requests. It has no generic trust-provider, `--actor`, reviewer-string,
unsigned-approval or force switch. Its only injectable alternative is the
explicit synthetic harness, restricted to synthetic principals, provenance,
output IDs and nonimplemented package hashes. Fixture events are data local to
that harness, not a login or a real maintainer approval. The real 22-package
approval inventory stays empty even after simulation.

An independent `OperatorDecision` binds the exact proposal, approval envelope,
gate evidence, operational scope, authorization context and runtime identity.
Contract approval, submitter confirmation, logo/design approval, operational
activation and publication remain distinct decisions. No publication field or
single cross-stage decision can authorize staging or merge.

## States and freshness

| State | Meaning in this isolated controller |
| --- | --- |
| IMPLEMENTED | Code/package exists; no approval implied |
| COMPATIBLE | Fresh trusted verifier reports historical compatibility |
| APPROVED | Exact package/registry/material decision authenticated by the boundary |
| READY | All explicit gate checks pass; no activation is performed |
| ACTIVE | Separate exact operator decision accepted for this runtime; synthetic only in M7 |
| SUSPENDED | Inactive selection with prior evidence retained; revalidation starts at COMPATIBLE |
| REVOKED | Authority withdrawn; terminal for this stream |

Ordered transitions cannot skip a stage. All transitions above IMPLEMENTED
re-enter the authority boundary; READY/ACTIVE require every gate, and ACTIVE
requires the operator decision. Validation runs before writes and again inside
the transaction immediately before commit. Reads do not trust recorded ACTIVE:
they recheck authority, expiry, exact inputs and runtime. Changed evidence gives
an effective SUSPENDED state; withdrawn authority gives REVOKED. `reconcile`
appends that result instead of editing old revisions. Corrupt chains fail with
an error, never ACTIVE.

GateEvidence alone is unsigned data. An adapter must derive its checks from
M5 expanded/final-job validation, M4 owned reviews, complete outputs/previews,
historical compatibility, source/dependency provenance, regression evidence,
freshness and resolved exceptions. Synthetic validation accepts only the
fixture's independently prepared evidence, not caller-modified booleans.
New poster logo-only evidence can never pass complete composition review.
Historical retained reviews do not approve a new use or source replacement.

M5 `compare`/`Index.impact` supplies exact affected outputs, categories and
per-output preview/confirmation/decision hashes. Shared decisions are scoped to
affected members. Unknown nodes or unresolved generator scope block readiness.
Whole package inventory changes require new package approval, while unchanged
material output context retains its separate artwork evidence under D08.
Reports do not revoke or rewrite historical decisions automatically.

## Recovery

| Failure | Fail-closed result and operator recovery |
| --- | --- |
| Interrupted blob/proposal/approval write | Unreferenced canonical objects may remain. No committed state/receipt/event pointer exists. Re-read and retry the exact request; do not garbage-collect historical objects. |
| Termination inside state transaction | SQLite rolls back record, state revision and event together. Restart and inspect; retry with the current revision. Tests include actual child-process termination. |
| Stale revision or competing operator | One CAS transaction wins. Reload all current evidence/authority before retrying; no force overwrite. |
| Missing/corrupt state or evidence | Inspection/transition fails or reports effective suspension. Restore exact immutable bytes and a verified database snapshot from backup; never fabricate/reseal an equivalent object. |
| Contract/source/registry/context change | Suspend and prepare a new exact proposal after M5 impact and applicable reviews. No automatic rebinding or widened approval scope. |
| Expiry/authority revocation | Effective suspension/revocation immediately on inspect; append with reconcile. Revoked streams cannot reactivate from an older snapshot. |
| Restart or restored ACTIVE snapshot | Old runtime authorization is unusable. Start inactive, inspect/reconcile, obtain a fresh independent operator decision after all checks. |
| Explicit rollback | Select an earlier verified proposal/registry from the same immutable history and append SUSPENDED. Retain all intervening decisions/receipts; never restore ACTIVE from a snapshot. |
| Live WAL/journal during strictly read-only inspection | Refuse the snapshot. Close writers and obtain a clean checkpointed snapshot through normal SQLite backup/close procedures, then retry. The inspector performs no checkpoint or repair. |

There is no external monotonic checkpoint or cryptographic decision service.
M7 cannot detect every malicious whole-directory rollback in offline storage.
That limitation cannot resurrect production authority: real intake is blocked
and any restored simulated ACTIVE state requires a fresh runtime decision.
Future deployment must resolve authenticated event provenance, revocation and
anti-rollback policy before installing a production hook.

See [M7 dossier](../../../lifecycle/PHASE2_M7_IMPLEMENTATION.md) for the full
historical report, production nonintegration pins, CI evidence and later phases.
