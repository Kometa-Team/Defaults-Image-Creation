# Category contract foundations — M1

This package is opt-in metadata infrastructure. It ships **no active registry,
category packages, identity adoption map, CLI or production adapter**. Importing
it opens no state and changes no existing generation or publication behavior.
The approved architecture is [the Phase 2 proposal](../../lifecycle/PHASE2_DESIGN_PROPOSAL.md).
M2–M7 and enforcement activation still require separate authorization.

## Interfaces

| Interface | Responsibility |
| --- | --- |
| `Contract.from_dict/from_bytes` | Validate the closed v1 schema, maintainer ownership/provenance, unique named variants, pinned typography/fitting/captions, permitted content fields and separate poster/overlay designs. |
| `Document.encoded/sha256/to_dict` | Immutable canonical JSON bytes, deterministic Package E SHA-256, and detached data copies. |
| `Contract.validate_content(variant, content)` | Validate only explicit semantic content/request fields, including nested asset shape. Never merge input into locked design or grant approval. |
| `RegistryDocument` / `RegistrySnapshot.load` | Validate a versioned registry; load exact hash-pinned packages, complete variant sets and exact contract approvals. Require an externally selected registry hash and operator-supplied trusted decision attribution. |
| `RegistrySnapshot.select` | Exact category/kind/version/hash/variant selection, with no floating version or fallback. |
| `Identity` / `check_namespace` | Separate stable ID, display, caption, source, local/public paths and optional semantic member. Preserve literal historic Unicode/case; check exact/NFC+casefold output collisions and duplicate IDs/member assignments. Shared sources are allowed. |
| `ContractStore(root)` | Explicit isolated root, existing Package E Store transactions/events, immutable version pins and canonical evidence blobs. No current cache migration. |
| `ContractStore.append/read_record` | Typed, immutable evidence revisions with optimistic expected-revision checks. These archive data; they do not execute an approval state machine. |

Four bundled Draft 2020-12 schemas live in `schemas/`: contract, registry,
identity and typed record. Every object is closed; versions, hashes, ownership
and required fields are explicit. References resolve only against bundled schemas.
The separate schema directory avoids changing the production definition resolver.
Contracts cannot contain arbitrary inheritance, expressions or executable values;
cyclic inheritance is rejected as an unknown field rather than traversed.

Canonicalization reuses `bulk.common.canonical/fingerprint`: sorted keys,
ASCII Unicode escapes, compact separators, finite JSON numbers. Contract pins
hash canonical payloads, not pretty-file bytes. Literal Unicode is never
normalized before hashing. Duplicate JSON keys, non-string mapping keys,
surrogates, nonfinite values and over-limit/deep inputs fail closed. The 8 MiB /
40-level bounds protect the parser; they are not visual acceptance thresholds.
Content-addressed store blobs must have the exact canonical bytes.

Schema version 1 is independent of exact `major.minor.patch` contract versions.
An existing category/kind/version or registry-ID/version cannot be rebound to new
bytes, including metadata edits. Labels confer no approval. Material design or
permission changes require a major release, additive independent variants a minor
release, and nonbehavioral metadata corrections a patch release, with explicit
approval of each new package. M1 checks syntax and immutability; it does not
automatically classify cross-version material impact or adopt a newer version.

## D01–D09 boundaries

| Decision | M1 representation / boundary |
| --- | --- |
| D01 | Strict versioned packages, ownership/provenance, canonical hash pins, immutable archive and externally attributed contract approval. No trusted flags in content. |
| D02 | Closed variants and fixed semantic contributor fields; fonts, transforms, paths of official outputs and role/approval controls are absent from contributor input. |
| D03 | Exact font path/hash/family/weight/size, measurement hash and captured fitting bounds. Representation does not execute fitting or authorize autoshrink. |
| D04 | Pinned language registry, caption requirement/case and closed type-to-text/key/template bindings. No resource changes, translation resolution or language activation. |
| D05 | Original source, treatment and background assignments/proposals are separate. Background requests require contract opt-in and never become approved assignments here. |
| D06 | Stable existing IDs are accepted literally; no IDs are minted from filenames or during rendering. New naming checks reject non-NFC; historical loading preserves literal spelling. No rename or identity assignment operation. |
| D07 | Typed effective-job/dependency/rule/context attestations only; no loader/planner/preflight/worker gate is installed. |
| D08 | Package E canonical bytes, Store transactions/events and immutable evidence/expected-revision pattern. Existing approvals, worker receipts and render fingerprints are untouched. |
| D09 | WHITE_ONLY, SOURCE_PRESERVING, BOTH_REQUIRED and retained historical/special treatments; exact exception/preview/two-role record types. Overlay schema requires SOURCE_PRESERVING with separate source branch and both sizes, and prohibits poster typography/wash controls. No pixel processing, thresholds, previews or exception acceptance is implemented. |

Actual category-specific policies and historical exceptions are **not adopted or
enforced yet**. The fixtures in the tests are synthetic schemas, not approved
Playlist designs. M3/M6 must encode the real accepted contracts. The 17 accepted
historical assets receive no cleanup, warnings, regeneration or new review.

## Evidence and authority

Typed records distinguish contract approval, adoption, exception request, preview
manifest, submitter confirmation, maintainer exception decision and effective-job
attestation. Preview records distinguish blocked default/requested panels and
complete member artifacts/worker-receipt references; records bind exact source,
package, variant, identities, transformations and material context. A later
workflow must verify receipt ownership, complete required variants, revisions,
two-stage decisions and invalidation. Structural validity alone proves none of
those semantics, and reading an adoption record does not adopt any job.

`TrustedDecision` is supplied by controlled operator code from an actual decision,
outside submitted JSON. It reuses the existing Package E maintainer allowlist.
There is no default trust map. A matching reviewer string or canonical checksum
cannot authenticate a decision. The registry loader compares the exact approval
hash, actor, decision evidence, package and approval scope with that external
attribution. Future intake adapters must preserve that boundary; this is not a
new authentication platform. Archiving an approval-shaped record does not put it
in the trusted map or authorize a package. No lifecycle record can serve as a
publication/staging/merge receipt.

Adoption records reference a `basis_registry_sha256`: the snapshot used to prepare
adoption. A subsequent immutable registry may index that record. This avoids a
circular registry-hash → adoption-hash → same-registry-hash dependency. M2 must
validate the actual compatibility/member/owned-receipt evidence and provenance.
Exception references are hash-pinned evidence pointers, not implemented waivers.

## Isolated storage and recovery

Provide a new empty directory outside source assets and configured default
production cache/workspace/output roots. Existing nonempty roots without the
exact namespace marker are rejected. An existing marked database is inspected
read-only for its sidecar version **before** Package E Store can migrate it.
Foreign state, unknown versions, symlinks/reparse points and missing databases
with retained evidence fail closed. Never point this API at a production cache.

The isolated database uses unchanged Package E migrations plus separately
versioned `contract_*` tables and immutable triggers; no changes are made to
`bulk.state.MIGRATIONS`. Objects are written atomically and verified before a
transaction commits a pin/revision and event. Failure rolls back both references
and events. A crash may leave an unreferenced content-addressed blob; retry can
reuse it. There is no automatic garbage collection or destructive recovery.
An interrupted initial sidecar creation or unsupported state needs explicit
inspection; this adapter does not repair/migrate a foreign database. Existing
production state has no dependency on this directory and remains unchanged.

Run the focused tests with:

```sh
python -m pytest create_defaults/bulk/tests/test_contract_foundations.py -q
```

They use JSON/temporary SQLite state only, including rollback/restart, concurrent
CAS, immutable history, tampering, authority replay, naming and nested override
negatives. Existing main-targeted CI discovers these tests on Windows and Linux.
No additional workflow or dependency is needed.
