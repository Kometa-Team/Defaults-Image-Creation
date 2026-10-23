# P3/M3 destination and ownership safeguards

Opt-in metadata inspection only. No production import, CLI, state writer, network
client, image operation, repository mutation, publication or readiness transition
is installed. See the [implementation dossier](../../../lifecycle/PHASE3_M3_IMPLEMENTATION.md).

## Exact inputs and M2 boundary

`BoundTranslation` holds the unchanged M1 `ValidationSubject`, exact M2
`TranslationPreflight`, independently selected hashes for both, exact M6 `Package`
and contract/rules pins. `evaluate(items, language_policy, policy, evidence,
inventory, *, expected_policy_sha256, expected_evidence_sha256,
expected_inventory_sha256, context=None, verifier=None, cancel=None)` takes a
nonempty immutable tuple of those companions. No ambient destination is selected.
Every policy/evidence/inventory pin is required independently; an explicitly
absent inventory/evidence uses null pins, never an automatic repository fallback.

M3 rechecks closed M1/M2 types, subject equality, requested/resolved language,
policy reference, exact contract/category/variant and actual contract-language
coverage. A missing/invalid M2 report fails; M2 technical blockers and English-only
category restrictions remain blocking. It retains M2's exact hash, source/context
reference and blockers. It neither substitutes a translation snapshot nor repeats
M2 source reverification or implements M4's combined readiness consumption.

A complete output group binds every selected subject, M2 report, contract/rules,
language, ordered output and membership hash. M1 DestinationEvidence references
one selected public subject; its exact target paths and trusted M3 observation
bind the **whole group**. Overlay standard/bigger and historical paired-logo
companions come from M6's exact member map. Foreign companion contracts, missing
members, unknown overlay membership and changed overlay record/review context
fail. New paired designs without an established membership assignment fail closed;
M3 does not infer new pairs or implement lifecycle additions.

Private outputs retain null public/target paths and remain in the complete group.
They are excluded from every remote path scope. An entirely private group requires
no DestinationEvidence, inventory, authority context or provider, and reports
`private_only` with no target. The two actual private Awards intermediates are
tested from real expanded definitions; no destinations are invented for them.

## Repository identity, routing and scope

Approved P3-D02/D03 permit English official or explicitly authorized user-owned
targets, and require an explicitly authorized user-owned target for every
non-English language. Names, URLs, casing, actor strings, identical image hashes
and self-declared booleans establish no ownership. Repository host/numeric ID and
owner ID must match independent verifier facts. A rename/URL alias cannot disguise
the official identity; an ownership transfer invalidates prior scope. Private or
public user targets do not receive an implicit language directory.

`policy_route` records the **declared policy classification by numeric IDs**;
`repository_identity_status` separately states whether those identities were
independently observed. A route label alone is never verified identity or success.
Non-English official attempts are denied, including aliases. Current official
mapping is exact `master`, null root and existing source-authority filenames.
M3 preserves that historical mapping; a branch/root change requires a separate
reviewed policy/implementation decision. User branch/root choices must be explicit.

M1 mapping paths remain relative to the explicitly selected root. Full targets
are exact `root/path` or `path` at null repository root. M3 never renames, Unicode
normalizes, repairs punctuation or adds `en/`/`fr/`. Missing or conflicting mappings,
overlapping language roots, case/Unicode branch ambiguity and cross-language full
target aliases block. Checks compare stable repository IDs, exact branch/root and
conservative NFC+casefold path keys; original spelling is preserved in evidence.

## Trusted authority consumption

`DestinationAuthority` extends the unchanged M1 `AuthorityVerifier.verify` protocol
with `observe`, returning immutable `DestinationFacts` from trusted code. Facts
bind the M1 AuthorityContext, independently observed repository/owner kind and
numeric principal ID, independent official IDs, full target/group/inventory pins,
permissions, issuer/context, explicit verification time, expiry and revocation.
The M1 target hash covers exact repository, branch/root/path/language scope and
commit/tree/inventory baseline. Every context field must match; facts cannot be
replayed after a changed grant, subject, group, branch, root, baseline or policy.

User destinations require personal ownership (`principal_id == owner_id`) plus
an externally verified scope grant. Organization/delegated user targets remain
unsupported. Official identity is a distinct exact-ID policy scope and still
needs an explicit grant. Required logical capabilities are `contents:read`,
`contents:write`, `pull_requests:write` for eventual draft staging. These describe
capabilities, **not OAuth token scopes**, credentials or a live API integration.
No capability or successful inspection authorizes actual staging/publication.

The default is M1 `UnavailableAuthority`, even for a perfectly hashed verified
claim. The live ownership/repository-currentness provider does not exist. M1's
result enum intentionally has no real authorized-success state. M3 preserves it:
**`technical_eligible` is always false in this version**. Missing, unavailable,
unverifiable, expired, revoked and scope-mismatched authority fails closed.

The only positive controls use a provider defined exclusively under the test
tree, independently retaining fixture facts. It yields M1 `synthetic-only`,
never real authentication. Production M3 imports no simulation or test provider,
has no registration switch and cannot convert synthetic evidence into authority.
`simulation_eligible` allows testing complete positive policy/inventory/scope
paths, with all operational flags false. Adding real success requires a separately
reviewed authority interface/provider decision; M3 does not invent one.

Trusted Python code, bundled schemas and controlled selection are inside the trust
boundary. Do not hydrate contexts/facts or choose expected hashes directly from
submitted JSON. These objects are binding interfaces, not authenticators or a
sandbox against arbitrary Python execution. M4 must revalidate selected M2/source
companions through a controlled boundary before any future combined readiness
consumption. M3 never supplies that readiness decision.

## Complete offline inventory

`DestinationInventory` is a closed additive immutable document: repository,
branch, commit/tree, exact raw commit hex, and direct-entry Git tree pages.
`inventory.git_object` and `tree_sha` verify actual Git object encoding, directory
sort order, mode/name/blob IDs, and commit-to-root-tree binding. A native
`git hash-object -t tree --stdin` parity test independently verifies the encoding;
it writes no Git object. No network or filesystem scan is used by inspection.

Every reachable subtree must be present. Missing root/subtree pages produce
`inventory_status=incomplete`, explicit missing object IDs and `complete=false`.
Wrong hashes, duplicate pages/names, unreachable extra pages and unsafe entries
fail. A supplied complete boolean cannot hide omissions because there is no such
input field. Recomputed object hashes still establish integrity only; trusted
facts must independently bind actual repository/branch/baseline/currentness.
Historical inventory integrity is never automatically current authorization.

Regular files, executable blobs, directories, symlinks and Git links are retained
as metadata. Symlinks/Git links are never followed; target or ancestor collisions
block. UTF-8 names must be representable by strict JSON and pass existing portable
path validation plus explicit `.git` and percent-encoding ambiguity rejection.
Traversal, absolute/drive/UNC/ADS, reserved Windows components, controls, surrogates
and unsafe encodings fail. No URL decoding/background path repair is performed.

Collision indexes compare exact/case/NFC+casefold paths and ancestors/descendants
without a quadratic whole-library scan for every output. Existing exact files,
aliases, directory aliases, file/directory conflicts, symlink ancestors and
proposed duplicate/aliased paths block. **Existing bytes/hash equality never
permits overwriting**. M3 defines no conflict-resolution or overwrite exception.

## Evidence, completeness and revalidation

[evidence-v1.schema.json](evidence-v1.schema.json) has closed inventory and
attestation definitions, local frozen M1 references and Package E canonical JSON.
`DestinationAttestation` records all subject/M2/contract/membership references,
target, policy route, independent observation/currentness, complete inventory pin,
per-output path diagnostics, explicit verification context and dependency hash.
All lists are deterministic for identical selected inputs. Sorted outputs preserve
literal names; canonical hashing consults no wall clock or TTL.

`evaluation_complete=true` means every supplied output was examined, not that the
inputs passed. `complete=false` if required companions, inventory closure or
trusted observation are incomplete/unavailable. An all-private group is complete
without remote context. `destination_checks_passed` describes the content/scope/
path/inventory checks independently of external authority. Only complete synthetic
observations can set `simulation_eligible`; `technical_eligible`,
`publication_authorized`, `production_enforcement`, `ready`, `active` remain false.

`read_attestation(..., expected_sha256=...)` checks structure and an independent
pin. `revalidate(attestation, expected_sha256=..., **selected_inputs)` recomputes
all findings and requires exact canonical equality. Loading/self-hashing does not
authenticate evidence. Changed authorization, owner, branch baseline, tree/pages,
policy, M2 source/context, contract, language or outputs invalidate the affected
attestation/dependency hash even when image bytes would be identical. No prior
report is rewritten or source silently refreshed.

Existing 8 MiB/depth-40 JSON bounds apply. Commit metadata is bounded to 256 KiB;
tree expansion to 100,000 entries/depth 40; group/output counts to 20,000. These
are fail-closed parser/resource limits, not policy acceptance tolerances. Overflow
or interruption returns an error and **no truncated complete report**. A partial
but hash-consistent tree can yield an explicitly incomplete diagnostic report.

## Tests and CI

Run `python ci/phase3.py run` using Python 3.13 and existing bulk requirements.
All previous 387 M1/M2 IDs remain, plus 142 M3 cases. Both focused platform jobs
remain prerequisites of mandatory **Validation acceptance**, which reconciles
complete collected/executed IDs, all legacy suites and unchanged M1 vectors.
The [full synthetic M3 fixture](../../../phase3/tests/destination-preflight-v1.json)
must match on Windows/Linux, alongside the unchanged M2 evidence fixture. Original
15-minute caps, 512 MiB worker-parent guard, 190-source protection, historical
capture, non-pytest commands and existing artifact names remain unchanged.
