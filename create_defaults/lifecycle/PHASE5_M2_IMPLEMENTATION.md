# Phase 5 M2 — read-only GitHub observations

2026-10-29. Starting remote main: `8e0bfa22329c33bd9b342760976b23dc205eabc4`.
Fetched before creating `feat/phase5-m2-trusted-observations` in an isolated
worktree. Local main tracks `origin/main`; its unrelated edits and all existing
worktrees were retained. M1 planning #44, its separate CI maintenance #45, and
subsequent approved maintenance through #54 are ancestors of this starting main.
Earlier dated M1 documents remain historical proposals; this document supplies
the current M2 implementation status.

M2 is **IN PROGRESS, pending exact-head CI and maintainer acceptance**. The draft
PR is the final-head evidence index. M3–M7 and Phase 6 have not started. This
implementation supplies observation facts, never contract/artwork approval,
activation, catalog mutation, rendering or publication. All 22 package approvals
remain separate and unavailable.

## Reuse and the necessary new boundary

| Existing interface | M2 use / preserved limitation |
| --- | --- |
| `remote.ReadOnlyGitHub.head/tree/blob` | Reused through a narrow `_Git` transport bridge. The existing CLI session owns credentials. No second token manager or Git writer. Authenticated GitHub responses establish commit-to-tree linkage; M2 does not claim to reconstruct raw signed commit bytes. |
| `github_inventory_core.complete_tree` | Reused full-tree traversal. Partial recursive data is discarded; M2 deliberately requests independently hash-checked nonrecursive pages. Truncation/error cannot prove absence. |
| `destination_preflight.inventory.tree_sha`, path validators, `config.repository/branch_name`, `common.path_key` | Reused Git tree hashing, exact path/branch/repository checks and alias detection. Complete root/subtree membership precedes a missing-file result. |
| `translation_preflight.sources.blob_sha/parse/lookup` | Reused actual blob identity, duplicate-safe bounded YAML and exact key/value tracing. Selected bytes/values are hashed, not archived as sensitive response bodies. |
| `language_policy.models.timestamp` | Reused validation for selected native decision timestamps; arbitrary remote text cannot enter timestamp evidence. |
| `lifecycle.package_e.SidecarStore.put_object/read_object` | Reused optional immutable object archive in the same explicitly owned Package E store. No new DB, index, migration, approval record or automatic archive creation. |
| P3 `SourceVerifier`, `SourceVerificationContext`, `DestinationAuthority`, `DestinationFacts`, `AuthorityResult` | Inspected and deliberately left unchanged. Their old synthetic/unavailable contracts are not relabelled as real grants. A future separately reviewed M3 consumer must bind M2 observations to exact selections and policy. M2 does not install a verifier into those consumers. |
| `RegistrySnapshot`, `TrustedDecision`, lifecycle review authority, `operator_publication/library_stage` | Inspected, left unchanged, never called for approval or publication. Existing maintainer names, push rights and native APPROVED state cannot supply approval. |

New APIs are limited to `Target`, `GitHubObserver.observe/reobserve/archive`,
immutable `Observation`, and a distinctly labelled `FixtureObserver`. The new
transport supports only explicitly allowlisted GET endpoints on `github.com`.
It has no login, credential refresh, write, command submission or provider plugin
interface. Version 1 observation JSON is audit data, not a capability format.

## Identity and trust model

The caller selects expected numeric repository/owner IDs, branch, root and
purpose in controlled code. Those are constraints, not observed facts or grants.
`/user` independently identifies the human principal and stable numeric ID.
Repository metadata and the collaborator-permission endpoint independently bind
repository/owner/principal IDs, owner type, permission booleans and native role.
Names are retained only as exact routing/display information, never as approval.
Unknown/custom roles or missing permission facts are unavailable. No role is
mapped to maintainer approval, contract approval or publication privileges.

Only the concrete supervised observer can use the concrete CLI transport. The
fixture observer has a different issuer and permanently synthetic result status;
arbitrary injected callbacks/subclasses or fixture transports cannot produce a
real-positive observation through that interface. The threat boundary is the
trusted Python process and installed CLI, not a sandbox against malicious code
already executing in that process. Serialized JSON, hashes, dataclass instances,
Git authors and caller flags never authenticate a person. There is no observation
loader that restores trusted authority.

No live sandbox/account was selected in this request. **All M2 acceptance reads
are controlled offline fixtures; authenticated live adapter observations = 0.**
Repository-preparation `git fetch` and `gh pr` reads establish this PR's baseline,
not acceptance of a production authority provider. CI needs no GitHub credential
for M2 protocol tests and never reads a production target through this adapter.

## Decision observations, not decision consumption

An explicitly selected PR is bound to its numeric ID/number, base repository and
owner, target branch, author, head repository/commit, state and draft/merge facts.
All review and issue-comment pages are traversed under strict endpoint/page bounds.
Every listed object is fetched again at its native detail endpoint and compared.
Both full histories and the PR are then re-read, detecting changes/newer decisions
that occurred during observation. Missing pages, duplicates, wrong URLs, unknown
states and failed detail reads block complete observation.

Evidence retains numeric decision/author IDs, state, commit, whether it matches
the current PR head, native timestamps, current reviewer permission facts, and
body/revision hashes. Raw bodies, headers and exception chains are not retained.
The revision hash describes observed native content, not a server-issued monotonic
edit counter. An edit and reversal entirely between reads cannot be proven from
snapshots; a future approval consumer needs separately reviewed event/revision
semantics and remains unavailable here.
Edited/deleted/dismissed/withdrawn objects and newer rejection change observations;
re-observation marks previous facts stale. A generic APPROVED review, body hash or
write permission grants nothing. Context wording, submitter confirmation and
independent-maintainer consumption are intentionally M3 work.

## Freshness, expiration, revocation and incomplete reads

Each observation reads the current ref, exact commit/tree, complete tree closure
and requested blobs; recomputes every tree and selected Git blob/SHA-256; and
validates exact requested translation keys and value hashes. A moved authoritative
head is stale even if selected text is unchanged. Unsafe modes, symlinks,
submodules, case/NFC aliases, inconsistent hashes and unsafe paths are rejected.
Only ordinary selected source blobs are accepted. Commit linkage is independently
read from authenticated GitHub, not a caller-supplied `commit_hex` assertion.

Head and identity/permissions are read again around the whole observation.
`reobserve` requires an exact lifetime-issued receipt and performs all reads anew;
there is no TTL success cache. Changed identity/permissions revoke the previous
observation; changed input/head/review facts are stale. A changed tree under the
same commit is invalid. Archived, foreign or restarted receipts are unavailable
until a fresh observation is taken. Sixteen bounded lifetime receipts are retained;
evicted observations must be read again. Observations are point-in-time facts,
not locks or atomic authorization for a later operation. M2 exposes no such write.

| Status | Meaning |
| --- | --- |
| `verified-current` | Concrete supervised CLI independently read all required facts at this observation; never approval/authorization. Not exercised against a live account by CI. |
| `synthetic-current` | Same protocol executed against deterministic controlled fixtures; no real trust. |
| `stale` | Source/destination head or decision changed, including during a read. |
| `revoked` | Credentials rejected (401), read access explicitly removed, owner/identity transferred or prior permission facts changed. |
| `unavailable` | Access is inconclusive (including ambiguous 403/404), missing credentials/CLI, unsupported delegation/target policy, unknown role, bounded retry exhausted or incomplete data. |
| `invalid` | Numeric/type/branch/PR/path/hash inconsistency or unsafe scope. |

Credential expiry timestamps and installation/delegation boundaries are recorded
as **unknown/unavailable**, never guessed. Expired tokens fail current reads;
401 cannot restore archived success. 403/404 are not proof of absent people/files.
No absolute observation TTL is invented. Operational use remains unavailable
pending approved expiry/delegation policy. Native role labels are observed facts,
not a new authorization-role mapping.

Official-destination observations require exact `Kometa-Team/Default-Images`,
`master`, repository root and English. Other branches/roots/languages fail before
network access. Independently selected numeric IDs must still match the response.
User-destination and organization-delegation policies are not guessed; they remain
unavailable. A source observation cannot masquerade as a destination grant.

## Credential, error and resource handling

The existing supervised `gh` process owns credential selection and handling.
M2 never runs `gh auth token/login/refresh`, writes credential files, constructs
authenticated URLs or persists tokens/headers. Requests use a fixed host, explicit
GET, no-cache header and no shell. Debug/tracing/paging are disabled for child
processes. Stderr is discarded; bounded response bytes exist only in memory.
Only selected validated fields/hashes and a closed reason vocabulary leave the
boundary. Unexpected exception text/causes are discarded. Correlation IDs are
bounded 24-character content hashes with no raw request or credential data.

There are three GET attempts for transient network/5xx/429/rate-limit errors,
bounded 1/2-second backoff (Retry-After can raise it to at most 10 seconds); longer
delays are inconclusive. A process is killed on timeout/output excess. Each
observation has a 180-second/1,024-request budget; responses <=12 MB, selected
blobs <=8 MB, tree membership <=100,000, at most 20 pages per history, and at most
100 selected paths/keys. Target strings and encoded evidence (<=2 MB) are bounded.
These do not raise original CI/process/render budgets.

## Decisions and unsupported operational states

| Decision | M2 disposition / remaining separate review |
| --- | --- |
| P5-D01 | Implement only the explicitly requested supervised existing-session read path and numeric bindings. Concrete live provider acceptance, selected sandbox/account and hosted/App execution remain unapproved/unavailable. |
| P5-D02 | Observe current native roles/reviews without consuming them. Numeric maintainer policy, valid wording/context, two-stage semantics and expiry policy remain unresolved M3 prerequisites; no invented grants. |
| P5-D07 | Preserve official English/master/root constraints. User routing, delegation and non-English category contracts remain unavailable pending exact policy decisions. No publisher extension. |
| P5-D08 | No 190 production or 299 adoption member changes. The exact additive CI scope proposal is separately isolated/documented in [CI maintenance](PHASE5_M2_CI_MAINTENANCE.md), retaining every historical hash and inventory. Its acceptance is a separate review item. |

Every observation has `contract_approved`, `readiness_authorized` and
`publication_authorized` false. No submitter/maintainer approval consumer, catalog
writer, renderer change, production generator, remote push/rename/delete, draft
publisher, READY/ACTIVE transition, merge or Phase 6 entry point is implemented.
This repository's draft implementation PR is delivery for code review, not an
artwork-publication operation.

## Validation and exact inventory

[Acceptance mapping](PHASE5_M2_ACCEPTANCE.json) enumerates actual collected node
IDs for P5-T01/T02/T03/T06/T07/T08/T10/T11/T29/T30. The additive CI runner uses
the existing `ci.validation` execution reporter to reconcile exact collection,
setup/call/teardown, source fingerprints, final head, both platforms and no skips.
It labels all protocol execution fixture-only. Original inventories, workflows,
historical capture and acceptance remain independently mandatory. The draft PR
links actual final-head artifacts and reports; passing local tests is preparation,
not hosted Windows/Linux or authenticated live acceptance.

Changed paths (14, including the two exact maintenance trust anchors):

* `.github/workflows/phase5-m2-validation.yml`
* `ci/dependabot_maintenance.py`
* `ci/dependency_tests/test_phase5_m2_maintenance.py`
* `ci/phase5_m2.py`
* `ci/phase5-m2-test-ids.json`
* `ci/phase5_m2_maintenance.py`
* `ci/phase5-m2-maintenance-v1.json`
* `create_defaults/bulk/lifecycle/github_observation_transport.py`
* `create_defaults/bulk/lifecycle/github_observations.py`
* `create_defaults/phase5/m2_tests/test_observations.py`
* `create_defaults/lifecycle/PHASE5_M2_IMPLEMENTATION.md`
* `create_defaults/lifecycle/PHASE5_M2_ACCEPTANCE.json`
* `create_defaults/lifecycle/PHASE5_M2_CI_MAINTENANCE.md`
* `create_defaults/lifecycle/ROADMAP.md`

No existing runtime, approval consumer, source catalog, poster/overlay, dependency
requirement, protected manifest or frozen test ID is changed. Historical invariants
remain 9,957 posters + 4,122 overlays = 14,079 outputs; 22 packages/278 variants;
190 protected production members; 299 adoption members; and 2,927 historical
protected files checked by the unchanged M7 preservation machinery. Actual hosted
reconciliation, including existing platform skips and historical artifacts, must
be inspected at the final head before claiming validated delivery.
