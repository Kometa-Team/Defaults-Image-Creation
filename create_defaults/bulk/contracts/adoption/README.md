# M2 — read-only historical adoption

This is an isolated factual audit, not contract activation, a new approval or a
publication operation. The [implementation report](../../../lifecycle/PHASE2_M2_IMPLEMENTATION.md)
records the baseline and findings. M3–M7 remain unauthorized. No production
entrypoint imports this package.

## Interfaces and commands

`discover()` verifies pinned local sources, loads the existing catalog through
`load_catalog` / `Planner.expand`, reads Package E's accepted ledgers through
`library_sources.reference`, and checks the preserved native worker specifications
and actual production-response receipts. It returns immutable M1 `Document`
values: one `HistoricalRegistry` and 14,079 `HistoricalOutput` records. Its default
mode opens no SQLite state, starts no workers, decodes no images and makes no
network requests. Tests explicitly prohibit those operations during discovery.

```sh
# Inspection before persistence: optional report file, no adoption state.
python -m create_defaults.bulk.contracts.adoption --report config/m2-audit.json

# Explicit metadata persistence into a separate, initially empty M1 state root.
python -m create_defaults.bulk.contracts.adoption --persist config/m2-isolated-state

# Inspect an existing exact immutable registry; never initializes a missing DB.
python -m create_defaults.bulk.contracts.adoption --inspect --persist config/m2-isolated-state --sha256 0b0c2af06124379206d43c36a4c12fb456e3861dd335343f4382865a7aab6a05
```

Report files are exclusive immutable exports: identical repeats are accepted;
different bytes require a new report path. Neither reports nor isolated state
may target production source/assets, cache, workspaces or output roots. Failed
comparisons identify category, logical record, path, expected and observed values.
There is no force flag or automatic upstream snapshot refresh.

## Factual types and M1 integration

The two additive schemas, `historical-output-v1` and `historical-registry-v1`, use
the unchanged M1 canonical JSON, `Document`, `Identity`, strict validator and
versioned registry primitives. Embedded effective definitions and jobs retain
canonical JSON and are checked against existing Package E strict schemas. Each
record separates persistent logical ID, worker job ID, source identity and kind,
display, caption/reference, expanded definition, source and font dependencies,
local/public destinations, size, family/member and actual paired-output links.

M1's `ContractApproval` / `AdoptionRecord` concern **approved category packages**.
Using those types for M2 facts would invent contracts or maintainer decisions.
M2 therefore adds factual types; it does not change M1 types or schemas. The M1
basis registry has no category-package entries. Every record explicitly says
`contract_compatibility: not_assessed_no_category_contract` and
`publication_authorized: false`. Category-specific contract authoring remains
M3/M6. Historical facts, material compatibility, historical approval evidence and
publication authority are separate properties.

`AdoptionArchive` composes the existing isolated `ContractStore`; it shares its
SQLite database, canonical object blobs, transactions and immutable event log.
The separately versioned `contract_adoption_*` sidecar uses one transaction for
the complete registry pointer, its M1 basis pin and event. All evidence blobs are
verified/written first. Interrupted writes leave only unreferenced blobs; retry
is idempotent. A committed missing/corrupt blob or inconsistent sidecar fails
closed rather than being repaired. Versions cannot overwrite earlier mappings.
No production migration or competing approval database is introduced. Archiving
typed data is not an acceptance decision; callers must use the explicitly
selected registry pin and validated discovery evidence.

## Reproducible snapshots and immutable identity

`source-pins-v1.json` fixes the M1 source commit/tree, artwork commit/tree, 299
existing source/catalog/evidence files, schema hashes, accepted exception and
D09 document identities, historical English resource hash and evidence index.
The loader also checks its exact canonical hash embedded in `sources.py`.
Text Git LF/CRLF representation is checked reversibly; source PNG/font bytes and
all literal filenames are never normalized. Caption resolution reuses the
existing `Translations` algorithm with the verified historical resource identity;
it does not modify production translation behavior or add a language/key.

Poster IDs remain existing persisted definition IDs. Overlay instance IDs remain
their existing accepted job IDs. Historically path-derived IDs are now frozen
in [the mapping](baseline/stable-mapping-v1.json.gz), independently of paths.
Family member keys freeze the existing child identity; future code cannot infer
a new identity from a rename. A changed mapping differs from the immutable
registry, even with unchanged image bytes. No rename operation is implemented.
Shared source assets, generated parent outputs, definitions, raw dependency
revisits and unique output records are counted separately. Generated parents
retain their source kind and parent identity; they are not submitted logos.

Ten fingerprints separate expanded definitions, exact source/font assignments,
captions/languages, backgrounds/geometry/effects, output membership, dependency
relationships, transformations, exceptions and material context. A source-byte
change changes context even when a hypothetical rendered byte hash is unchanged.
Current source/settings are compared with the pinned historical jobs. Historical
renderer/runtime identities and output bytes remain evidence of those original
runs; M2 does not claim a fresh render on a different runtime.

## Historical evidence and boundaries

`evidence/index-v1.json` enumerates 65 deterministic gzip metadata files. Original
approval/policy/manifest JSON bytes are preserved verbatim, with raw-file,
canonical and compressed-file SHA-256 identities. Native pages retain exact
jobs, actual owned SQLite worker specifications and receipts. Extraction used
immutable read-only connections and verified source database bytes before/after.
Production pages retain the original actual-response receipt bytes. Their seals,
plan membership, candidate hashes and pinned production commit are verified.
All these files contain metadata only; no JPEG, PNG, database or credential is
included. Original source receipts and databases are never rewritten.

Original Group A/B, individual font/visual and overlay decisions retain their
exact policy and candidate membership. Seven canary decisions come from the
existing committed acceptance record. No newly generated record attributes a
new human decision. Old draft-staging receipts remain historical evidence of
their original scope; they grant no future action through this API. Factual
records are rejected by the existing publication authorization gate.

Only explicit accepted bridges are used: eleven byte-preserving source-case
aliases, the Action & Adventure public mapping, the canonical overlay case
ledger, and additive family provenance for historically flattened children.
There is no fuzzy filename matching, visual-equivalence inference, generic
warning waiver, alpha-policy recheck or color/font substitution. All 17 accepted
historical alpha assets remain normal artwork without new warnings or reviews.
Color/white pairs preserve separate historical sources where present; overlays
keep their source-preserving white/color branches and both size transforms.

The frozen registry hash is
`0b0c2af06124379206d43c36a4c12fb456e3861dd335343f4382865a7aab6a05`.
The full read-only test recomputes it from pinned sources and compares every
record hash; negative tests use synthetic JSON only. See
[`baseline/audit-v1.json`](baseline/audit-v1.json) for complete counts and
[`baseline/stable-mapping-v1.json.gz`](baseline/stable-mapping-v1.json.gz) for all
literal identity/path relationships. No artwork is regenerated for these tests.
