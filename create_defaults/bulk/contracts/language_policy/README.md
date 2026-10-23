# P3/M1 policy and evidence foundations

This opt-in package implements immutable metadata and trusted-caller interfaces
only. Production imports, translation preflight, destination eligibility,
readiness integration, lifecycle operations, rendering and publication are absent.
M1–M7 schemas, package hashes, receipts and approval/activation boundaries remain
unchanged. No document or checksum authenticates a person or authorizes an action.

## Approved policy decisions

* **P3-D01:** verified commit/content provenance and explicit reverification before
  readiness are required. A timestamp or identical content cannot prove currentness.
  This milestone represents source/verification context; it implements no source
  verifier, automatic refresh, arbitrary TTL or readiness consumer.
* **P3-D02:** ownership/authorization comes from an externally authenticated
  boundary. Unknown, expired, revoked or unverifiable authority fails closed.
  `UnavailableAuthority` is the default; no live provider or credentials exist.
* **P3-D03:** explicitly authorized English user repositories are permitted by
  policy. Official publication remains English-only. The model represents that
  policy; it does not implement request eligibility or a writer.
* **P3-D04:** non-English category permission needs separately approved versioned
  contracts. Translation discovery, registration and actual contract applicability
  remain distinct. No current English-only package is widened or bypassed.

## Versioned schema and values

[foundations-v1.schema.json](schemas/foundations-v1.schema.json) is a bundled,
closed JSON Schema 2020-12 document with six independent typed definitions.
`schema_version` is exactly integer `1`; `version` is the immutable policy/record
semantic version, distinct from the wire schema version. Unknown fields, kinds,
stages and schema versions fail. All nested structures are closed. References
bind kind, version and lowercase SHA-256, and do not select an ambient latest.

| Python value / kind | Stage | Important bindings |
| --- | --- | --- |
| LanguagePolicy / `language-policy` | policy | Owner attribution, exact registered codes/aliases, declared version/hash/variant coverage, approved freshness/authority restrictions |
| TranslationSelection / `translation-selection` | selection | Policy/subject pins, requested/resolved code, snapshot, Git repository/commit/tree/blob/resource hashes, source/value hash traces and explicit verification claim |
| DestinationPolicy / `destination-policy` | policy | Language-policy pin, declared official identity, English-only invariant, explicit per-language repository/branch/root/path mappings and English user-target permission |
| DestinationEvidence / `destination-evidence` | observation | Subject/policy pins, exact target and inventory baseline, claimed issuer/version/principal, assertion/context pins, explicit verification/expiry/revocation context |
| ValidationSubject / `validation-subject` | subject | Stable item/output IDs, exact identity and contract hashes, variant, expanded definition/dependency/review context, exact output membership and paths |
| Phase3Attestation / `phase3-attestation` | informational | All companion references, language, contract, output membership, source/authority verification contexts; READY/ACTIVE, enforcement and publication flags fixed false |

`from_dict` / `from_bytes` validate bounded strict JSON and return frozen values
whose sole instance field is canonical bytes. `to_dict` returns detached data.
The package reuses M1 `Document`, strict parsing/safety bounds, Package E
canonical JSON/SHA-256, existing language/repository/path validation and strict
integer schema validation. Local schema loading is lazy; references resolve only
through the bundled schema registry and never a remote retriever. Frozen M1
schema/readers are not extended and reject these record types.

`read_document(encoded, kind, expected_sha256=...)` requires an independently
selected pin. `reference(value)` produces exact typed references.
`check_bundle_structure(...)` checks companion pins, language resolution,
declared mapping agreement, ordered output membership and context bindings only;
it returns `None`, never a preflight, eligibility or readiness result. It does
not inspect real contract language permission, enumerate required translation
keys, verify Git objects, check a live inventory or consume external authority.
Those operational evaluations remain later milestones.

Exact codes resolve before explicit aliases, with no casing/separator rewrite.
`nb_NO` and `pt-br` retain their spelling. Duplicate or case-ambiguous registrations
are rejected, not normalized. Discovery does not populate policy registration;
registration does not grant contract coverage or approve a contract. Exact paths,
Unicode spelling, punctuation, branch casing and stable identities are preserved;
NFC+casefold is used only to reject collisions. A null root explicitly represents
repository root; null public paths preserve private membership. Paths are lexical
metadata: link confinement and complete target-inventory checks belong to M3.

## Authority interface and threat assumptions

`AuthorityVerifier` is a typed protocol. `UnavailableAuthority.verify` always
returns unavailable, including for perfectly hashed `status=verified` JSON.
`AuthorityContext` and `SourceVerificationContext` are frozen trusted-caller
inputs with exact expected evidence/subject/policy/scope/context pins and explicit
`as_of`. They have no deserializer from submitted evidence and are **not**
authenticators. Trusted code must obtain facts independently in a future reviewed
adapter. No currentness claim follows from constructing a context.

The explicitly named [simulation adapter](simulation.py) compares synthetic-only
fixtures to those independent pins, including issuer/principal/version, scope,
expiry and revocation claims. A matching fixture returns `synthetic-only`; every
`AuthorityResult` has readiness/publication authorization false. There is no real
authorized result status, production mode switch, CLI, provider registration or
M7 controller call. Synthetic evidence cannot become operational authority.

Threat boundary: submitted bytes/claims and self-selected hashes are untrusted;
the Python implementation, bundled schema and controlled caller code are trusted.
Python objects are not a sandbox against arbitrary code execution. Future intake
must not hydrate contexts from request JSON or treat this structural checker as
an authenticator. Provider selection, organizational/delegated scope, independent
revocation/currentness verification and reverification-to-consumption protocol
remain explicit integration gaps. No Weblate API/review attribution is invented.

Closed evidence has no token, password, credential or authorization-header field.
Parser/schema diagnostics do not echo arbitrary submitted keys/values. Callers
must never place secrets into ordinary identifiers; this is not a secret detector
or redactor. Credential management remains outside canonical evidence and logs.

No state database/approval framework is added. Encoded values are compatible with
existing content-addressed conventions; an eventual additive isolated sidecar
requires separate review. Do not pass new records to frozen M1 record writers or
rewrite old receipts. All canonicalization is clock/network/render/state free.

## Tests and required CI

Run `python -m pytest create_defaults/phase3/tests -q -rs -p no:cacheprovider`,
or the exact CI runner `python ci/phase3.py run` from repository root. Tests use
synthetic metadata/repository identities only. No images, live permissions or
production credentials are used. Fixed [golden vectors](../../../phase3/tests/golden-v1.json)
must match on Windows and Linux. The maintained [focused ID list](../../../../ci/phase3-test-ids.json)
must match both fresh collection and completed execution, with no focused skips.

The existing bounded workflow now has a dedicated Phase 3 matrix. Its two jobs
are direct prerequisites of existing mandatory **Validation acceptance**. Missing,
failed, cancelled, skipped, stale-head/schema/selection, substituted IDs or unequal
golden evidence fail that check. The original 1,671 pytest IDs, 155 unittest IDs,
12 CI controls, eight groups per OS, full historical audits, 190-file guard,
512 MiB worker-parent limit and 15-minute caps remain required. The workflow's
single protected-source hash is updated through explicit maintenance provenance;
the protection algorithm and all other protected source hashes are unchanged.

See [implementation and review boundaries](../../../lifecycle/PHASE3_M1_IMPLEMENTATION.md).
