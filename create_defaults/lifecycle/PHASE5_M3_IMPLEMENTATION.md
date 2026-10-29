# Phase 5 M3 — exact two-stage decision consumption

2026-10-29. Starting fetched main and merged M2 PR #55:
`67525e98c79425dfb669f7e9da1141f9b3c3a00e`. Upstream remains
`Kometa-Team/Defaults-Image-Creation`, branch `main`. M1/M2 are COMPLETE.
M3 alone is authorized on `feat/phase5-m3-exact-decisions`; existing edits and
unrelated worktrees remain intact. M3 is **IN PROGRESS pending final-head
Windows/Linux validation and maintainer review**. The draft PR is the final SHA,
exact file inventory and hosted acceptance index. Earlier dated documents retain
their historical statuses. M4–M7 and Phase 6 are not implemented or authorized.

## Existing boundaries reused

| Existing interface | M3 use and preserved limitation |
| --- | --- |
| M2 `GitHubObserver`, `FixtureObserver`, `Target`, immutable `Observation`, `observe/reobserve/archive` | The only identity, native history, role, head/tree/blob and translation observation boundary. Concrete-type checks preserve synthetic versus supervised results. No new HTTP client, authentication provider, token retrieval or live session selection. |
| `Implementation.load/select` | Exact current 22-package release and empty review-registry validation. Expensive immutable parsing is memoized only after matching reads; every selection rereads/hashes all 46 release/contract/rules/registry files. A current-byte change blocks rather than refreshing a pin. |
| `ContractApproval`, `RegistrySnapshot.load/select`, `TrustedDecision` | A single exact package's closed variant set is exercised in an owned disposable registry. The numeric fixture actor maps to the legacy fixture attribution only inside this synthetic bridge. No trusted map or registry is returned as real authority; the real registry stays empty. |
| `ReviewInputs`, P3 `consume/revalidate`, original translation lookup and validators | Replays current request, graph, contract, required members, translation values/heads and destination evidence. Legacy requested-key spelling is mapped through the original lookup to M2's exact literal key. Both traces remain context-bound; M2 checks are unchanged. |
| `CompositionArchive`, native composition and owned receipts | Full native default/requested images, source bytes, renderer/font/layout/configuration, companion/dependency membership and actual durable worker receipts are replayed before consumption. No thumbnail, filename or similarity substitute. |
| `ReviewArchive`, `decision`, `SyntheticReviewAuthority` | The original two-stage immutable records, local CAS, explicit rejection, attribution and current-bundle replay. The fixture bridge never subclasses or changes their authority gates. Real `require_operational_approval` remains unavailable. |
| Package E `SidecarStore` objects/events/transactions | Exact observations, receipt lineage and audit objects share the existing isolated database. One exact consumption event per binding; duplicate identical input returns the same receipt. No approval database, new SQL namespace, production state adoption or network call within a write transaction. |

## Minimum new interface

`bulk/lifecycle/github_decisions.py` adds `PackageSelection`, `ObservationQuery`,
an opaque lifetime-issued `DecisionBinding`, an audit `ConsumptionReceipt`, and
`GitHubDecisionConsumer` with a distinct concrete `FixtureDecisionConsumer`.
These connect current M2 facts to the unchanged contract and P3/P4 consumers.
There is no generic injected success callback, arbitrary observer subclass,
archive loader that restores trust, or positive operational result type.

The live adapter can obtain current read-only M2 observations. Its `consume`
gate is always **unavailable** until P5-D02/D03 policy and provider acceptance
are supplied through a separately reviewed implementation. No policy parameter
or caller boolean enables it. The concrete fixture adapter exercises the exact
protocol and existing synthetic consumers in a lifetime-owned `CompositionTrial`.
Its result has every original operational/approval/READY/ACTIVE/publication flag
false. Passing fixtures is technical integration evidence, not real acceptance.

As with the existing Python consumers, installed code, the process and local
filesystem remain trusted; these object/type checks are not isolation against
arbitrary code execution or monkeypatching inside the same interpreter.

No sandbox/account or real operational proposal was selected. Authenticated live
M3 observations, real decisions consumed and real package approvals are all zero.
Preparation reads and this implementation's draft PR are not production authority.

## Two native stages and complete history

Five explicit M2 selections bind submitter and maintainer sessions, proposed-work
source, authoritative translation resource and current destination. The PR must
be open and unmerged, with exact numeric repository/owner/PR identity, submitter
author and source repository/head. Each participant's independently observed
numeric principal must match its selection and differ from the other principal.
Login strings never supply that relationship.

Stage A selects an exact native submitter comment. Its author must be the
independently observed submitter and PR author. The comment must be unedited and
must explicitly confirm this binding. A generic comment, bot repost, body hash
without authorship, or an older confirmation superseded by a later submitter
comment fails. Stage B selects a later native maintainer review with its own
numeric principal, current eligible fixture role, exact source commit, current
state and explicit reference to the confirmation's native ID and revision hash.
Self-approval and swapped confirmation/context/PR/source/package fail.

M2 traverses all review/comment pages, fetches native details and brackets both
histories and the PR. M3 also rejects a selected maintainer decision superseded
by a later eligible review. M2 accepts explicit UTC seconds only; malformed or
offset timestamps are rejected at that existing observation boundary. Dismissed, edited, withdrawn, missing, unsubmitted or
mismatched reviews cannot become approval. Explicit rejection is recorded using
the original immutable `MAINTAINER_REJECTED` transition; it grants nothing.

`fixture_message` is an explicitly labelled **offline-only fixture grammar**,
not accepted production approval language. Logical fixture expiry and native
maintain/admin fixture roles are deterministic controls, not production expiry
or role policy. M2's content revision hashes are not a monotonic server edit
counter; an edit/reversal entirely between snapshots is not proven absent.
Real revision/withdrawal/expiry semantics remain an unavailable policy decision.

## Exact packages, separate scopes and current context

Each selection identifies category, kind, exact version, canonical contract hash
and exact variants from the current release. A contract decision requires the
entire closed variant set demanded by the existing registry protocol. The M2
source tree must contain the exact current contract, rules, release and empty
registry bytes for that selection; each selected blob is independently checked. The
adapter creates one disposable contract record and one-entry fixture registry,
then re-enters `RegistrySnapshot.load/select`. Approving that package supplies no
other package, artwork, operation, activation, destination or publication grant.
All 22 selectors are independently exercised; no blanket decision is created.

Artwork bindings additionally pin the original `ReviewBundle` and material
context, operation ID/revision/type and selected identities. Current replay binds:

* Complete encoded default/requested poster members and owned worker receipts.
* Exact source image, definition and profile bytes selected from the proposed
  source commit; renderer, fonts, captions, layout and exception context.
* Required white/colour members, parent/dependent closure and current mappings.
* Original P3 request/graph/translation evidence, source heads, resource blobs,
  required keys, exact values and their literal versus requested key spelling.
  A caption with no translation keys must replay P3's explicit zero-key
  `not_applicable` result; its authoritative source identity/head is still bound.
* Destination numeric repository/owner, branch/root and current complete head/tree.
* Exact package/variant selection, registry and immutable receipt lineage.

The proposal fingerprint excludes later native decision histories to avoid a
cyclic approval hash. Those complete current histories, current object revisions,
attributed authors and all observation hashes enter the consumption evidence.
Every consumption first observes all facts again, checks the complete context,
reobserves each M2 receipt, and repeats native/P3 replay before indexing review
state. Relevant changes require a new binding and fresh native decisions.

Duplicate exact decisions are idempotent in the same fixture lifetime and are
serialized locally; conflicting evidence cannot replace an existing consumption
event. P4 CAS remains authoritative for concurrent review revisions. Interrupted
confirmation can be resumed only after fresh native facts, with the original
records and exact current bundle. No archived evidence alone reconstructs a
permission. Restart rejects old binding objects; a new adapter must prepare a
new lifetime binding from current observations before any fixture replay.

An observation is a point-in-time fact, not a lock across GitHub and SQLite.
M3 exposes no operation execution or publishing action and makes no distributed
atomicity claim. Old P3 real/synthetic result distinctions are unchanged.

## Validation and resource boundaries

[Acceptance mapping](PHASE5_M3_ACCEPTANCE.json) enumerates actual stable test IDs
for P5-T03/T04/T05/T09/T10/T11/T12/T13/T14/T28/T29/T30. The additive runner reuses
`ci.validation` to verify collection, successful setup/call/teardown, current
source fingerprints, final head, both platforms and no skip/xfail substitution.
Original six workflows remain independently mandatory at the same final commit.

The M3 artifact includes full actual Genre default/requested JPEGs and both
Network companion members in both appearances, plus their native composition
and owned durable worker rows/receipts. Genre exercises positive synthetic
two-stage consumption. Prospective Network companion identities remain
**unavailable** under the unchanged P3 `unverified_companion_membership` gate:
the complete pair is exported with its blocked P3 attestation and no decision
receipt. Complete images alone cannot bypass that restriction. The missing-pair
case independently re-enters the native archive verifier and fails.
Acceptance independently decodes all six
encoded images, checks exact dimensions/formats/bytes, canonical receipt hashes,
worker specifications and complete member/view coverage. These are controlled
fixtures, not production artwork or a second visual approval scheme.

Original 512 MiB worker-parent protection, native worker limits, 15-minute jobs
and M2 per-observation request/page/process/blob/tree bounds remain unchanged.
M3 adds no larger limit: evidence <=2 MB, <=100 selected local/source bindings,
16 lifetime bindings, and serialized consumption. Raw errors/headers/body text
are not archived. Public-boundary exceptions discard unexpected native/remote
messages and chains in favour of closed diagnostics; evidence contains only
selected IDs/hashes/facts and the existing sanitized M2 correlation data.

Historical counts remain 9,957 posters, 4,122 overlays and 14,079 combined
outputs; 22 packages/278 variants; 190 production members and 299 adopted source
members. None is edited or regenerated. Original historical bytes, names, case,
fonts, exceptions, receipts and mappings remain unchanged. Final-head raw reports
and acceptance artifacts, rather than these constants, must prove preservation.

## Decisions still requiring maintainer acceptance

* Production numeric maintainer/submitter policy, accepted exact confirmation
  and review language, expiry and edit/withdrawal/reversal rules (P5-D02).
* Real provider/account/delegation acceptance and any separately authorized
  sandbox; no account or live observation is inferred from CLI availability.
* Each of the 22 real exact package approvals and their selected real registry
  successor (P5-D03). Current real approval count remains zero.
* Any positive real P3/P4/operation consumer, supported M4 current-mapping cohort,
  destination ownership/delegation extension, production activation or publishing.

Operational scopes remain **unavailable**, not approved by this fixture suite.
No production catalog/YAML edit, public artwork generation or remote write,
protected-branch push, People repository action, artwork-publication PR/merge,
public rename/deletion, READY/ACTIVE transition or M4–M7/Phase 6 path exists here.
Stop at the validated draft implementation PR for independent review.
