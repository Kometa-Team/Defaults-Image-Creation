# Phase 5 acceptance plan

2026-10-26. Planning-only specification, not implemented test coverage or an
approval. Starting baseline is merged M7
`ef3b2713cf5dcab9b92395321c6be3fdf1efdbce`. The IDs below identify planned
acceptance families. Later authorized milestones must bind each family to exact
collected/executed test node IDs, expected boundary and encoded evidence; do not
count these table rows as tests already executed.

Read [design](PHASE5_DESIGN_PROPOSAL.md), [rules/22-package coverage](PHASE5_OPERATION_AND_PUBLICATION_RULES.md)
and [milestones](PHASE5_MILESTONE_PLAN.md) together. Every positive operation
requires an independently accepted exact adapter and operational trust scope.
Unsupported real input must fail closed; isolated synthetic positives remain
explicitly synthetic. Never widen adapters, synthesize grants or weaken old
assertions to complete a planned row.

## Planned positive and adversarial acceptance families

| ID | Exact trigger / scenario | Expected result and intended boundary | Primary proposed milestone |
| --- | --- | --- | --- |
| P5-T01 | Authenticated numeric principal/repository facts versus forged JSON, Git author, caller role flag, URL alias or public GET | Only independently observed exact identities can contribute authority; untrusted claims rejected before local/remote mutation | M2 |
| P5-T02 | Expired credential/grant, revoked account/installation/role, transferred repository or unknown custom role | Block and retain sanitized retry/revocation evidence; no archived grant resurrection or automatic privilege provisioning | M2 |
| P5-T03 | Maintainer changes after confirmation, review dismissed/edited/deleted, newer rejection/withdrawal or truncated decision pagination | Current exact two-stage decision fails consumption; no cached event or generic APPROVED substitute | M2–M3 |
| P5-T04 | Submitter self-approves, swapped confirmation/context, wrong PR/repository/commit or bot repost | Independent numeric author and causal confirmation linkage required; reject at attribution/review boundary | M3 |
| P5-T05 | Same exact native decision observed twice; replay after restart/revision/expiry | Idempotent observation/consumption for exact authorized operation only; new writes require reauthentication/current scope, never duplicate apply | M3–M6 |
| P5-T06 | Translation head/resource/key/value changes, missing required key, same caption under moved authoritative head | Explicit current provenance reverification; relevant change invalidates affected consumption, unrelated changes use scoped compatibility proof | M2–M3 |
| P5-T07 | Destination head/tree moves, ownership changes, missing/truncated subtree or stale cached inventory | Unknown/conflicting destination blocks write; no TTL-only or empty-tree success, no force rebase | M2–M6 |
| P5-T08 | Official target receives non-English or unauthorized root/branch/user target; language-neutral overlay used as bypass | Reject destination/category scope; preserve official English-only and separate user ownership/versioned language coverage | M2–M6 |
| P5-T09 | Approve one exact package versus version/hash/variant substitution or missing approval among 22 | Exact registry approval required per selected package; all-category claim requires all 22, none inferred from architecture merge | M3 |
| P5-T10 | Attempt synthetic-positive status, subclass, reviewer name or arbitrary success callback at real consumer | Existing unavailable boundary remains closed; new real provider must be explicit reviewed versioned adapter | M2–M3 |
| P5-T11 | Permission/source verification fails between prepare and consumption or per-batch write | Block further side effects, retain partial progress and require fresh trusted facts; distinguish API uncertainty from permanent absence | M2–M6 |
| P5-T12 | Full native default/requested context changed: source bytes, renderer/font, definition/profile, caption, graph, translation or destination | Invalidate affected exact review/receipts at intended current-context guard; no pixel-only waiver or post-seal resealing | M3–M4 |
| P5-T13 | Missing white/colour, standard/bigger, parent/dependent or required language member | Logical operation remains incomplete and cannot produce accepted publication manifest, catalog consumption or complete marker | M3–M6 |
| P5-T14 | All required native members/receipts present versus thumbnail/representative-only, wrong receipt owner or forged bytes | Actual full-resolution encoded artifact and owned receipt verification; partial/foreign evidence rejected | M3–M4 |
| P5-T15 | Unsupported category/variant/generator/version/new overlay job, new exception or non-English contract | Reject explicit coverage boundary before mutation; no fallback to English Genre adapter or implicit companion generation | M4 |
| P5-T16 | ADD -> UPDATE -> RENAME -> new current-mapping UPDATE of same active supported identity | Stable ID/semantic key and all old encoded epochs/aliases retained; new context/receipts/review accepted only through new exact adapter | M4 |
| P5-T17 | Old M5 UPDATE/candidate/dependency after M6 rename or retired member | Preserve current `m6_mapping_requires_current_adapter` / dependency guard; retired UPDATE/reinstatement blocked | M4 |
| P5-T18 | Concurrent UPDATE/RENAME/public namespace conflict, case-only/Unicode alias or foreign branch head | Scoped CAS/conflict, literal spelling preserved, no last-writer-wins, overwrite or ID remint | M4–M6 |
| P5-T19 | Shared source changed while unrelated consumer omitted; generator child reappears after retirement | Require full current dependent/member closure and persistent accepted exclusion adapter; unsupported generator retirement stays blocked | M4 cohort |
| P5-T20 | Candidate catalog contains unknown fields, duplicate YAML keys, path traversal or changed locked fields; round-trip alters unrelated comments/bytes | Reject at strict parser/raw-preimage/minimal-patch/effective-job boundary; zero unintended source/job changes | M5 |
| P5-T21 | Catalog source branch changes after exact patch prepared, or same bytes but new mapping/approval | Require current source CAS/review; exact-byte upload skip cannot bypass catalog/mapping authorization | M5–M6 |
| P5-T22 | Cancel/crash before/after local prepare, object persistence, transaction markers and durable commit | No partially committed local heads, no premature remote write, immutable successes preserved; exact recovery/retry | M5 |
| P5-T23 | Network stops before send, after accepted push, before acknowledgement/journal update or mid-prefix | Reobserve exact remote commits/bytes and known owned prefix; ambiguous state never inferred successful/absent from exception alone | M5–M6 |
| P5-T24 | PR creation succeeds but reply lost; existing draft differs, closed/merged/foreign or wrong base/head | Discover/reuse exactly one authorized draft; foreign/uncertain outcome blocks, no duplicate PR or merge | M6 |
| P5-T25 | Partial multi-batch or multi-repository result; withheld failed member; unrelated operation succeeds | Retain all successes but partial group stays incomplete; no silent partial set, catalog activation or whole-batch completion | M5–M6 |
| P5-T26 | Definition DELETE/public rename requests automatic blob/source deletion, path reuse or tombstone revival | Public bytes/receipts/reservations retained; destructive remote action outside scope and independently rejected | M4–M6 |
| P5-T27 | Compensate after local/remote partial success, stale rollback authorization or corrupt journal/index | New exact forward-reviewed action only; integrity failures preserve evidence and block; no remote reset/cleanup or fixture-backup “recovery” | M4–M6 |
| P5-T28 | Bypass contract, submitter stage, independent maintainer, full-context replay, current source, activation or operation scope | Each missing independent gate blocks at intended boundary; write/merge rights alone cannot supply another approval | M3–M6 |
| P5-T29 | Error contains credentials/headers/token URL/request body or unbounded cause chain | Bounded sanitized error/type/operation/input/cause/correlation evidence only; no sensitive material in log/artifact/journal | M2–M6 |
| P5-T30 | Remote actual bytes/tree/modes/paths differ, unrelated blob changes, recursive tree truncated or unsafe symlink | Reject exact remote verification; complete unchanged tree outside approved membership; no “published” result | M6 |
| P5-T31 | Existing transport technical batch/file/byte/pack/object/process budget exceeded | Existing hard limit rejects before unsafe work; original 512 MiB parent safeguard and 15-minute CI budgets retained | M5–M7 |
| P5-T32 | Reconcile historical original files/outputs/receipts/exceptions/identities/names and new adapter noninterference | All required counts/projections/hash membership exact, zero unexplained historical changes; no public regeneration as proof | Every milestone / M7 |
| P5-T33 | Evidence omits IDs/phases/platform, stale SHA/plan, xfails/new skips, partial/failed workflow or forged aggregate | Original exact-head collection/execution/acceptance rejects; every selected node has successful setup/call/teardown or documented existing skip | Every milestone / M7 |
| P5-T34 | Documentation/support matrix claims unsupported scope, approval or Phase 6 readiness | Reconcile actual implemented interfaces and all 22/278 dispositions; missing integration/authority remains explicit blocker | M1 / M7 |

## Historical acceptance and immutable projections

| Baseline | Required preservation |
| --- | ---: |
| Posters | 9,957 |
| Overlays | 4,122 |
| Total outputs | 14,079 |
| Public mappings / private Awards intermediates | 14,077 / 2 |
| Exact category packages / variants | 22 / 278 |
| Protected production members | 190 |
| Adoption-source baseline members | 299 |
| Actual physical historical input assets | 2,106 |
| Unexplained historical differences | 0 |

Preserve artwork bytes, literal filenames/case/Unicode, source transforms,
fonts/category policies, historical exceptions, permanent identities, original
receipts/mappings and every required companion/parent. Approved dependency/People
provenance successors remain exact; no rollback to older hashes or unreviewed
resealing. Future authorized intended new operations are reported separately from
the unchanged historical population, never hidden in its baseline.

| Projection / established evidence | SHA-256 |
| --- | --- |
| Ordered historical outputs | `d5ddf0d646de1968a0054acfda7fa199330848d3d57254f6611fca7ed636e476` |
| Exact names/casing/Unicode | `32d3a7492b56f007ece4ff7fb83fd2a1b7758c117d34bb92ceae5c6281301fdc` |
| Stable mapping | `6d1a49062208e8361227942549a4adafb0f2fed63c2f3a9a63c7860845ab876f` |
| Historical dependency graph | `93b01e2261249185bd06982a9cb0823a61628104d327958cedefd97788a39d7d` |
| Historical English policy coverage | `c06bd27d0c7a26825678cda3ce14c1b92b8f4140cc1e717ce47d4b77e442abee` |
| Complete accepted P3 historical envelope at merged M7 | `350e6dcc55b089029ee5a3d166fc28cba098d1c05f6634727b588a7c795263c0` |
| Current approved production protection manifest | `9c683678b051564c30106bb2dca2049722564e4bc255798208a5414e5ac9b3bf` |

Actual shared guarded capture and independent current-source/receipt inspection
must prove compatibility at future final heads. Constants and passing small unit
tests alone cannot prove historical acceptance. Do not render/decode/replace the
entire public library or rewrite historical receipts to obtain matching evidence.

## M1 validation and evidence contract

M1's exact diff is seven Markdown files under `create_defaults/lifecycle/`:
the five requested planning documents, `PHASE5_PREREQUISITES.md`, `ROADMAP.md`.
No code, schemas, production catalog/YAML, artwork, font, workflow, test body,
inventory, dependency, manifest or resource threshold changes. Preserve every
earlier roadmap decision entry and six permanent phases; mark Phase 4 complete,
Phase 5 M1 planning in progress and M2/Phase 6 unstarted.

Validate all relative documentation links, cited existing function/class paths,
all 22 package selectors/contract hashes, 278 literal variant IDs, four generator
versions, 18 branch/trim/size settings, exact changed paths and whitespace. Verify
approved dependency infrastructure/maintenance, 190 protected hashes/membership
and 299 adoption-source pins using existing verification functions. Reuse the
approved Python 3.13 environment; no new project dependencies.

Run the unchanged original Windows/Linux workflows at the exact final PR SHA.
Record all job outcomes and actual executed IDs/counts/timings from completed
reports; missing/failed jobs are failures, not omitted coverage. Existing M7 scope
guard rejects the five new documents; keep that explicit as an inherited CI
prerequisite and do not alter the check or baseline inside M1. No claim of full
green acceptance until a separately reviewed policy successor is authorized and
merged and the exact rebased planning head passes. Do not retry a deterministic
policy failure as if it were network flakiness.

The draft planning PR is the final exact-head evidence index, avoiding a source
commit solely to insert its own SHA. It must link all completed runs and record
remaining failures, exact seven-file inventory, provenance/protection outcomes,
coverage verification, proposed P5-D01–D08 decisions and the separate CI proposal.
Development/local passes and merged M7 results are labelled preparation/baseline
evidence, never substituted for current-head execution.

## Future acceptance and stopping points

For each approved implementation milestone retain original test identities,
add explicit stable regression IDs, make negative tests hit their intended guard
and inspect actual encoded complete artifacts. Fault injection must distinguish
pre-commit rollback from lost acknowledgement after real commit. Temporary fixture
reset is not application recovery. Require successful session teardown and cold
read-only replay; neither restores live authority. Partition tests within existing
budgets rather than weaken safeguards or duplicate full historical capture.

Phase 5 final acceptance requires exact implemented/blocked coverage, all mandatory
Windows/Linux reports at final SHA, independently reconciled raw IDs/artifacts,
complete original historical proof, audited current trust/consumption/transport
boundaries and recorded operational prerequisites. It does not authorize a pilot,
merge, ACTIVE state or public write. Stop at a draft PR for each separate review.
No Phase 6 or any of the six deferred Timeline Order requests in Phase 5 M1.
