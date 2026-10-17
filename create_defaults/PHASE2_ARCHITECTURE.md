# Phase 2 Architecture

**Gate A and D01-D08 approved; Package B authorized.** `bulk/` now implements
definitions/configuration, planning, inventory, colors, translations, state,
workspaces and persistent workers. Category migration (C), overlays/multilingual
review (D), complete benchmarks (E) and production cutover remain unauthorized.
Sections describing review, layout workflows and category rules remain future
contracts, not implemented services. See [Package B Report](PACKAGE_B_REPORT.md).

## Package Boundaries

Package: `create_defaults/bulk/`. Keep Phase 1 tools/fixtures independent
and retain `create_poster.py` as the single composition implementation.

| Module | Responsibility / ownership |
| --- | --- |
| `common.py`, `schemas/` | Versioned schemas, diagnostics/errors, canonical hashes, safe paths/YAML and atomic file helpers. |
| `definitions.py` | Safe YAML loading, stable IDs, shared defaults, explicit overrides and semantic validation; no dynamic code evaluation. |
| `generators/` | Small registered category rules for award years, rating strings, paired styles, separators and generated numeric parents. Pure expansion into definitions/jobs. |
| `translations.py` | Explicit local source snapshots, key lookup, transformations/templates, provenance, fallback diagnostics. Network refresh lives outside rendering. |
| `layout.py` | Exact bundled face resolution, cmap/glyph checks, shaping/direction, caption measurement, fitting and clipping evidence. Uses the validated text implementation where applicable. |
| `colors.py` | Historical assignments, policy versions, palette proposals, exact/perceptual comparisons and reservations. Never silently recolors. |
| `assets.py` | Read-only filesystem inventory, content hashes, source classification and candidate definitions; no deletion. |
| `remote.py` | Read-only Defaults inventory facade over neutral GitHub transport/tree primitives; metadata cache and selected verified blob fetches. |
| `planner.py` | Selection, dependency expansion, translation resolution, full effective jobs, output/remote mapping, collision checks and deterministic manifests. |
| `workers.py:compose` | Direct adapter to `create_poster.create_poster`, exact asset/font paths inside private workspace. No independent composition logic. |
| `overlays.py` | Separate PNG pipeline, alpha/trim/resize/profile handling, independent transform specifications/results. |
| `validation.py` | Preflight, risk ranking, output verification and fresh-legacy/published comparison classification. |
| `approvals.py` | Specification and output decisions, language-aware invalidation, exact-version group decisions, immutable audit events. |
| `workers.py` | Persistent spawn processes, bounded queues, dependency scheduling, timeout/cancel/retry/resume, recycling and verified artifact promotion. B synthetic proof only; C actual workloads. |
| `state.py`, `workspaces.py` | SQLite transactions/migrations, ownership/leases, atomic receipts, content-addressed artifacts and scoped retention. No People publication lifecycle. |
| `reports.py` | JSON + static human review reports, caption crops, old/new/published views, worst-first filters, progress. No Flask. |
| `config.py`, `__main__.py` | Validated configuration and argument parsing only; call shared services. No duplicated business rules. |

Do not create a framework, plugin system or ORM for these responsibilities.
Dataclasses, pathlib, SQLite and small injected protocols are sufficient. Separate
publishing interface may be designed later; Phase 2 exposes no write-capable
GitHub API, commit, branch update, deletion or workflow dispatch operation.

## Definition Schema and Experiment

Human YAML is distinct from expanded JSON manifests. Proposed production
organization: `definitions/<category>.yml`, one shared `profiles.yml`, small
registered Python rule modules, and checked-in JSON Schemas. A logical ID is
allocated once and retained through name, source-line and output changes. Display
names and source coordinates are not identities. Variants have stable IDs beneath
the logical poster; language is a separate dimension.

The A experiment lives under `phase2/` to avoid implying production cutover:

- `schemas/document-v1.schema.json`: versioned YAML envelope.
- `schemas/definition-v1.schema.json`: fully inherited effective definition.
- `schemas/manifest-v1.schema.json`: complete composer-job **sample** envelope.
- `examples/current-posters.yml`: four source/hash-bound real definitions.
- `evidence/sample-manifest.json`: current PowerShell-capture data for those
  examples, not newly planned/rendered Python output.

The experiment uses already installed PyYAML and jsonschema (Draft 2020-12),
strict unknown fields, unique keys/IDs, one-level named profiles, typed geometry,
safe relative paths, exact language identifiers, explicit fallback and fixed/fit
policies. Nested mappings merge; scalars/lists replace. Profiles cannot extend
other profiles; anchors/aliases/merges and duplicate YAML keys are rejected,
including cycles and unused malformed profiles. No arbitrary YAML object tags,
scripts, environment substitutions or shell expressions.

Definition fields cover identity, category, display name, source provenance,
logo/average/dominant sample assets, caption/key/template/case/fallback/direction,
exact font family/file, typography, explicit/random/image background policy,
logo/text placement, gradient, clean/white-wash/average flags, border, output,
languages, variants, dependencies and overrides. Dominant color remains false,
consistent with its approved legacy no-op. The prototype deliberately restricts
variants/dependencies/overrides to empty arrays: their production typed rule and
override schemas are a B/C deliverable, not implemented or validated expansion.
The initial schema does not claim to represent every dynamic category yet.

B production schemas are separate under `bulk/schemas/`, with strict composer
types, typed dependencies, named/versioned generators and explicit language
overrides. `bulk/examples/` contains four source-derived definitions; no complete
category has been migrated. Fitting uses hash-bound captured evidence or explicit
fixed sizes, not a replacement fitting engine. Unknown layouts fail closed.

Package B production definitions implement typed, registry-named generator configurations
(for example a year range with inclusive/exclusive bounds and explicit output
template), dependency references and language overrides, without embedding Python
code in YAML. Actual category rule implementations belong to C. At most one ordered defaults layer; any additional inheritance
requires a schema version and maintainer review. Default expansion must appear
explicitly in every canonical job and in a readable effective-definition report.

## Canonical Manifest and Fingerprints

The sample manifest demonstrates source commit/hash, capture/translation identity,
renderer source identity, source row/producer lineage, logical ID, language,
variant, all twenty `PosterOptions` fields, 2000x3000 canvas, exact font path,
input hashes, encoding (JPEG quality 100/subsampling 0), local path and remote
relative path. Its scope is explicitly `package-a-capture-sample-not-rendered`.
The exporter selects existing capture jobs; it is not a second planner or a
Python fitting implementation. Hash validation is tested independently.

The B production schema has separate poster and overlay job kinds,
selection/coverage ledger, generator identity/configuration, expanded overrides,
all raw-to-effective compatibility decisions, typed dependency DAG, source/logo/
gradient/font hashes, translation resolution trace and effective shaping/script/
direction settings. B captures Python/Pillow/fontTools/uharfbuzz/bidi versions,
platform and renderer source identity; native-build fidelity across deployments
must also be checked during C/E integration. The A sample lacks this execution
environment lock and is not sufficient for a production render-cache hit.

Canonical serialization: UTF-8 JSON, sorted keys, fixed numeric normalization,
no NaN/infinity, stable job ordering, relative POSIX paths. Preserve Unicode text
exactly; use NFC/casefold only for collision indexes, never silently modify a
caption or exact remote path. Reject duplicate IDs/paths and cycles before work.
Schema upgrades are explicit; do not reinterpret unknown future fields.

Use separate identities rather than one overloaded hash:

1. **Definition fingerprint**: expanded definition, generator config, policy
   approvals and exact revision. Tracks specification review/invalidation.
2. **Render fingerprint**: all effective composer parameters, shaping/language
   effects, actual font/asset/gradient/dependency bytes, encoding and renderer/
   environment identity. Only this complete render identity enables deduplication.
3. **Artifact SHA-256**: actual encoded bytes plus verified size/mode/dimensions.
4. **Validation fingerprint**: artifact SHA, validator/threshold versions and
   exact baseline/reference identities. Published comparisons are separate evidence.
5. **Approval binding**: poster/variant/language, source/definition/render/
   validation versions and image SHA. Compatibility transfers require an explicit
   independently evidenced event, never automatic approval for a changed image.

A French translation change invalidates affected French approvals; shared logo,
font, color or renderer changes invalidate all dependent variants. Record exact
resolved key/value hashes and whole source-file revision separately so unrelated
translation edits need not force renders. Same text alone never establishes
equivalent output. Dedup can cross languages only when complete effective render
identity, including all language-sensitive behavior, is identical. Outputs may
share cached bytes, but language approvals remain distinct.

## Asset Workflow

`discover_assets` reads configured source roots, rejects links/reparse points,
classifies PNG/allowed image formats, validates decoding/pixel/frame limits, hashes
content and keeps exact filenames separately from normalized collision keys.
Definitions distinguish active inputs from inactive legacy sample fields and
generated dependencies. Detect missing assets, unused candidates, existing valid
assignments, new logos, unexpected formats, duplicate identities and output paths.
An unassigned logo may already serve an overlay; it is not automatically a new
poster. Never delete it. Ambiguous category/name inference returns candidates and
a review request, not a committed definition. Proposed IDs require confirmation.

## Color Registry Specification (D01)

**D01 is APPROVED / RESOLVED.** The following specifies initial policy
`defaults-colors-v1`; Package B implements the registry, proposals and reservations.
Other historical prototype schema scope
values are exploratory, not authorization to enforce global uniqueness or block
similar colors. Production validation must implement the approved policy below.

### Assignments and Policy Records

| Record | Required identity/provenance |
| --- | --- |
| Logical assignment | Stable assignment ID, logical poster ID, category ID, canonical HEX, source spelling, source definition/hash and lifecycle state. Languages/outputs reference this record rather than allocating repeated colors. Distinct intentional style assignments remain traceable under the logical owner. |
| Color origin | Historical, independent manual selection, accepted palette suggestion, inherited assignment or template-derived assignment; explicit parent/template/variant references. Persist random choices in job manifests separately; do not reinterpret frozen audit draws as approved assignments. |
| Historical reservation | Source row/audit ID and category/HEX occupancy, linked to the logical owner when mapped; retained duplicates are `legacy_preserved`, not automatically approved exceptions or evidence of intentional relationships. Unresolved identity mapping leaves the color occupied, not available. |
| Explicit relationship | Stable relationship/collection ID, enumerated member logical posters/variants and permitted shared-color use, provenance and revision. Category/name similarity alone is not membership. Inherited/template origins need this link when separate logical posters share a color. |
| Named exception | Stable exception ID/name, category/HEX, affected logical poster identities (candidate and conflicting owners), authorized reviewer identity, nonempty justification, exact policy version/configuration, decision time and revision/status. No wildcard or inferred permission for future unrelated posters. |
| Policy configuration | Version/immutable configuration hash, category-local exact rule, normalization rule, perceptual method and configurable warning thresholds, plus relationship/exception semantics. Numerical warning defaults must be recorded, never silently changed. |
| Color decision/reservation | Selected normalized HEX, assignment/logical owner, policy/configuration and relationship/exception revisions, reviewer/decision metadata when approved, reservation owner nonce/lease and expected definition revision. |

Historical row-coordinate IDs remain migration evidence, not future logical IDs.
Import the complete historical category occupancy, including duplicated colors,
without recoloring, asserting intentional reuse or manufacturing exceptions.
D02's green Splatter stays historical-only; retirement must not silently erase
its historical color reservation or create an active job.

Validate six-digit `#RRGGBB` input, trim surrounding input whitespace and uppercase
for exact comparisons; reject shorthand, alpha and named colors rather than
guessing an equivalent. Preserve original source text and bytes. A language render
does not create another logical color assignment; repeated evaluation of the same
assignment is idempotent. Multiple language approvals do not consume additional
colors. Explicitly distinguish inherited/template references from independent
choices, even when their resolved HEX is identical.

### Approved Outcomes and Diagnostic Precedence

| Situation | Result |
| --- | --- |
| Existing historical assignment, including an exact duplicate | Preserve unchanged. Audit as historical reuse without asserting an approved exception or blocking its regeneration. Still reserve it against new unrelated category assignments. |
| Same logical assignment reused by language/output expansion | Reuse the assignment; no duplicate collision or extra reservation. |
| Exact category match with explicitly linked related posters, collection members or generated variants | Allow intentional sharing without color-collision warnings; show the explicit relationship in provenance. |
| New unrelated logical poster, exact occupied HEX in the same category | Block the new assignment unless a valid authorized named exception covers all conflicting owners. Do not recolor an existing owner. |
| Exact match only across different categories | Allow; informational collision with owner/category identities, not a warning or blocker. |
| Valid authorized exception for a prohibited exact duplicate | Allow; display exception name, reviewer, justification, policy version and covered identities. The authorized match is not an unresolved collision warning. |
| Nonidentical perceptually similar colors | Warning with measured distance, method, threshold/configuration version and owner identities. Never automatically block solely for similarity. |

Evaluate against **every** same-category owner/reservation, not just the first:
being related to owner A does not permit collision with unrelated owner B using
the same HEX. A named exception must cover any remaining prohibited conflicts.
Relationship reuse or an authorized exact exception must not also be relabelled
as a perceptual warning for that identical pair. Unrelated nonidentical neighbors
may still generate similarity warnings. Color permissions do not waive independent
asset, text/layout or output-path blockers; D02 still requires one active output.

The six rules do not impose global uniqueness: cross-category exact information
must not become a warning through generic duplicate handling. Collection and
template metadata are explicit relationships, not blanket scope exemptions.
Related-use permission suppresses collision warnings only for its covered use;
it cannot hide unrelated exact owners or real layout/contrast diagnostics.

B suggestions sample a bounded 96x96 image, alpha-weight visible pixels and ignore
fully transparent RGB; rank deterministic hue/lightness candidates using base
swatch contrast/visibility and policy diagnostics. This is not full gradient/text
readability validation, which belongs to D. `color_math.py` independently implements
CIEDE2000 from the reference equations and passes all 34 published reference pairs
in both directions. No unlicensed reference software was copied. Policy thresholds
are explicit/versioned, not guessed production defaults.

Perceptual thresholds are configurable warning thresholds in the immutable policy
configuration, not minimum-distance rejection rules. Rank legal candidates using
similarity/harmony/readability scores and retain warnings; if every legal candidate
is perceptually similar, still return legal choices with warnings rather than
claim no unique choice exists. Return `review_required` only when no exact-policy-
legal candidate exists or an explicit decision is needed; do not weaken exact
uniqueness or silently create an override. Never recolor existing assignments.
Contrast thresholds are separate layout/readability policy, not newly approved
numeric values under D01. Measure text/logo regions and gradient extremes, not
only the base swatch; alpha visibility is not a blanket readability guarantee.

### Concurrent Reservations and Persistence

Use SQLite `BEGIN IMMEDIATE` to serialize read/check/reserve/commit. Indexed
`(category, normalized_hex)` assignment/reservation lookups form a logical bucket;
there is no separate physical bucket table. Do not place a unique category/HEX index
on individual assignment rows: that would reject preserved historical duplicates,
explicit related reuse and authorized exceptions. Language is not part of the
uniqueness bucket; different categories have separate buckets.

Within the transaction, read historical occupancy, committed assignments and live
reservations for the bucket; validate all conflicting logical owners against the
current policy, explicit relationships and authorized exceptions; then add the
claim. Recheck policy/configuration, definition and relationship/exception versions
when converting a reservation to an approved assignment. Two unrelated requests
for the same category/HEX cannot both succeed, even when the bucket was initially
empty. Related requests or an authorized exception may share it only after checks
against every owner. Near-identical, nonidentical choices may both succeed with
warnings; do not lock them out via a perceptual uniqueness constraint.

Use owner nonces, expected revisions, lease expiry and idempotent assignment
requests. Approved choices and historical occupancy do not expire. Reclaim only
expired uncommitted claims with owner/version checks, never a whole occupied
bucket. Unauthorized/stale overrides fail closed; revocation/reconfiguration
revalidates pending claims without automatically recoloring existing assignments.
A reservation is not approval, and changing a relationship cannot silently approve
a previously prohibited assignment.

Human-reviewed YAML is authoritative for specifications; SQLite is authoritative
for approved new color selections, events/reservations/artifact status. B does not
write YAML. Future C/D persistence must reconcile a selected registry color and a
reviewed definition explicitly; contradictory values must not silently render.
A staged YAML update and DB event cannot
be assumed atomically committed together. Journal a pending definition revision
and content hash, write a unique sibling temp, fsync/atomic replace under a
definition-revision lock, then finalize the event. Reconcile pending journals
after crashes before another operation; reject externally edited/stale hashes.
Never leave YAML and registry state disagreeing about an assignment's authoritative
color. Color changes invalidate dependent approvals and release only obsolete
uncommitted reservations transactionally; historical occupancy remains reserved.

Persist approved HEX and provenance once; reruns use that assignment, not a new
palette draw. Color and relevant policy/exception/relationship changes trigger
revalidation of affected approvals without fabricating changed image bytes.
Do not silently release retained historical reservations during reconciliation.

### Preview and Approval Explanations

Future preview/review services use the same structured policy results as CLI:
exact normalized swatches, category and all conflicting logical owners, whether
the match is preserved history/explicit related use/cross-category information,
and any named exception with reviewer, justification and version. Similar-color
warnings display swatches, delta-E00 and configured threshold; state that they
are advisory, not exact-collision blockers. Explain how an authorized reviewer
can request an override without presenting it as automatic approval. Keep raw
historical duplicate findings separate from unresolved conflicts for new posters.

## Translation and Scalable Validation

Resolve explicit local YAML snapshots offline. Network refresh is a separate
operator command/service with authorization; render/preflight never fetches
missing languages automatically. Preserve selectors exactly, detect casefold
ambiguous keys, separate key matching from value Upper/Lower/Exact, retain source
revision/hash and fallback trace. Override directories permit testing corrected
translations without altering authoritative files. Missing data is unavailable;
explicitly shared text/no-caption is distinct from untranslated text.

Use the validated text engine for font bytes, glyph coverage, shaping, bidi and
measurement. Direction/script/shaping features are explicit render inputs.
No default font substitution, especially for Arabic. A local font being installed
does not imply an approved redistributed face. Language applicability and fallbacks
are decisions, not fabricated render jobs to meet a capacity estimate.

| Mode | Required work | Honest coverage result |
| --- | --- | --- |
| `preflight` | Resolve every selected applicable language variant; validate keys/placeholders/assets/schema/fonts/glyphs/scripts/direction, effective size, line wrapping, bounding boxes and estimated clipping. Deduplicate layout measurements by full layout inputs. No full-size posters required. | Planned/preflighted counts, blockers and unavailable/not-applicable with reasons; zero implied output approval. |
| `review` | Preflight full selection, rank high-risk variants and render selected full-poster previews. Missing/suspicious glyphs, longest/extra-wrapped text, clipping, fallback fonts, RTL, contrast/layout changes, changed/rejected definitions receive priority. | Exact rendered/reused/sample list; unrendered variants stay untested at output level. |
| `full` | Produce or hash-verify every required final artifact, including dependencies/overlays in scope. Check decoding, dimensions, RGB/alpha/format, file completeness, artifact hash and selected parity evidence. | Complete required output ledger, or explicit incomplete/failed status. Output verification is not human approval. |

At current English size, seven equivalent languages would mean 69,706 jobs;
English plus seven would mean 79,664. These are estimates only. Stream job
planning/results in bounded pages, cache repeated measurements, use bounded
queues and record actual render/cache/dedup savings. Do not retain duplicate
full-size copies solely for a report; generate thumbnails/crops with lazy links
to verified retained originals.

Diagnostics carry code, severity, poster/language, measured value/threshold,
region/crop and an actionable plain-language explanation. Sort blocking errors
first, then normalized threshold exceedance/risk and stable tie-breakers. Group
only cases with comparable font, fitting/layout, warning cause and baseline.
Fresh Python-versus-PowerShell parity is the primary migration comparison;
published artwork may have old fonts/historical differences and is a separate
labelled comparison, never allowed to hide a new-engine regression.

## Approval and Audit Model

Do not encode generation, human decision and publication as one status flag.
Store orthogonal axes with a derived operator view:

- Generation: defined -> planned -> rendered -> automatically validated.
- Review: pending -> approved / changes requested / rejected, with reason and
  exact current version. A changed source makes a prior decision stale, not erased.
- Applicability: applicable / explicitly not applicable with reviewer and reason.
- Eligibility: future-publication eligible only when current required outputs,
  automatic checks and applicable human approvals are complete. Publication itself
  is unavailable in Phase 2; approval does not perform it.

Append-only `decisions` records: event ID, poster/variant/language, decision kind,
approver identity supplied by CLI operator (not authenticated identity proof), UTC
time, reason, source/spec/render/artifact/validation fingerprints, accepted warning
IDs, inspection mode and superseded event. Future service authentication can
provide identity without changing decision semantics. No authentication framework now.

Group decision: freeze a versioned selection listing every exact output SHA,
language and validation fingerprint; verify no unresolved blockers in the same
transaction; record approver/time/reason, explicitly accepted warnings and inspected
sample IDs. Expand immutable membership rows for audit/invalidation. Sample review
must not be labelled individual visual inspection of all members. High-risk items
are excluded from safe bulk selection unless reviewed individually under D05.

SQLite proposal: definitions/revisions, input dependencies, plans/jobs/results,
artifacts, validations/diagnostics, decisions/group_members, current-review heads,
color assignments/reservations and remote snapshots/entries. Add schema migrations,
foreign keys, WAL, busy timeout, local-disk workspace and per-operation connections.
Use expected-version compare-and-swap when recording decisions and leases. Two
reviewers cannot overwrite each other silently; stale writes return a conflict
and current version. Append history, never mutate an old approval to match new
bytes. Multi-file JSON exports are receipts, not the mutable concurrent database.

## Clone-Free GitHub Reuse Plan

Inspected `../create_people_posters/people_github.py`,
`people_remote_inventory.py`, `people_workspaces.py` and People GitHub tests.
Destination metadata read during A confirmed `Kometa-Team/Default-Images` default
branch **master**, distinct from this source repository's main. No image clone or
download is required. Recheck configured destination metadata during explicit
future refresh; never silently fall back to another branch after an error.

| Existing code | Safe reuse / required separation |
| --- | --- |
| `GitHubError`, injected session/sleep/attempts, request timeout/backoff, rate-limit handling, JSON validation, no redirects | Extract a neutral transport in B after regression tests. Add injected allowed repo and method policy and read-only facade; keep sanitized exceptions. Defaults permits only GET against configured allowlisted repo/API endpoints. |
| `GitHubClient.head` | Reuse ref -> immutable commit -> tree algorithm, branch validation/encoding. Snapshot all lookups against that commit/tree, not a moving branch. |
| `auth_token`, `branch_name`, constructor/sandbox routing | Do not reuse directly: People env, seven repositories, sandbox policy and write-scope instructions are product-specific. Defaults supports unauthenticated public reads or read-only credentials; never requests Contents:write or Actions:write. |
| `RemoteInventory.tree_entries` | Reuse complete recursive/partitioned traversal. Discard all truncated recursive results, descend nonrecursive subtrees, and fail unknown/incomplete on any truncated nonrecursive response. Trees are not ordinary paginated Contents listings; handle pagination only on endpoints that use it. |
| `RemoteInventory.refresh` and SQLite snapshots | Reuse root-folder partitioning, unchanged-subtree SHA reuse and transactional snapshot replacement. Never replace a complete snapshot with partial data. Add fetched/verified time, commit/tree, completeness and stale/fresh/offline states. |
| `path_key`, `lookup`, `images` | Reuse safety/collision concepts, not matching behavior: People lookup casefolds, and images filters `/images/`. Defaults must match exact repository path first, report case/NFC conflicts separately and accept category-relative paths. |
| `blob_sha`, `fetch_image` | Reuse Git blob SHA-1 framing and blob-identity verification. Add strict base64, API SHA/size consistency, byte/pixel/frame limits, decoded format checks, SHA-256 cache record and unique atomic temp file. Reject symlinks/gitlinks/LFS pointers rather than treating them as ordinary artwork. |
| `Workspaces`, atomic JSON, cleanup/state helpers | Reuse ancestor link/reparse checks and transaction/ownership principles. Do not instantiate People's publication workspaces: creation can clean previous published jobs. Fixed `.tmp` filenames need unique siblings for concurrent Defaults work. |

B extraction boundary: small repo-neutral transport/tree primitives in a shared
internal module; preserve People's existing wrapper signatures, environment,
sandbox routing and write behavior through adapters and unchanged regression
tests. Defaults wraps these primitives with a GET-only capability. Never subclass
the write-capable People client or import its global repository policy. If safe
extraction cannot be proven, defer the wrapper switch rather than risk People.
No extraction or People edits were performed in A. B now shares `GitHubError`,
complete-tree traversal and Git blob framing through
`create_people_posters/github_inventory_core.py`; People write-capable transport,
environment and publication policies are unchanged. Defaults' facade exposes
GET-only head/tree/blob operations and never subclasses the People client.

Remote result contract:
`found(entry, snapshot)`; `missing(snapshot)` only from an accessible complete
verified inventory; `case_conflict(candidates)`; `inaccessible(auth/repo/branch)`;
`unknown(incomplete/offline-without-snapshot/error)`. Stale found entries remain
explicitly stale; absence in stale metadata is not authoritative missing.
401/403, rate exhaustion, private-repo 404 and network failures are never empty trees.

`fetch_selected` downloads only requested blobs necessary for comparison, pins
their snapshot SHA, verifies before cache promotion, and records provenance.
Content-address by blob SHA plus verified SHA-256, with bounded storage/retention.
Credentials stay in headers, never reports/URLs/logs. Validate all repository,
branch and endpoint segments; block arbitrary hosts/URLs and redirect credential
leakage. Keep byte limits before base64 decoding and image pixel limits before
expansion. Local fallback is explicitly configured, read-only, link-checked,
commit-identified and never refreshed/cleaned or required.

## Batch, Output and Recovery

Planner expands category aliases, selectors/languages, variants and dependencies;
then validates all paths and detects exact/case/NFC collisions before rendering.
Maintain legacy source -> logical ID -> language/variant -> job -> local output
-> expected remote path mapping. Unconfirmed non-English remote namespaces stay
unknown until verified. No selection means help/list, not generation.

Schedule DAG-ready jobs with bounded persistent process workers and bounded pending queue;
keep SQLite writes in short orchestrator transactions. Configure worker/memory
budget explicitly; do not enqueue 80,000 full image objects. Timeout/cancel kills
and reaps owned workers, records interrupted/failed jobs and keeps verified
receipts. Retry only explicit retryable statuses; never mask a corrupt output.

### Persistent Worker Contract (Maintainer Addendum)

`PersistentWorkers` owns a long-running parent and a fixed maximum number of
`multiprocessing.get_context("spawn")` workers on Windows and Linux. Each process
initializes its private resource dictionary once and consumes multiple requests.
The default renderer imports/calls the approved composer API directly, never a
PowerShell, ImageMagick or Python CLI per poster. No shared mutable option/image
objects, GitHub calls or database writes run in workers.

One task per worker is in flight; per-worker input queues have capacity one and
isolated OS result pipes carry at most one outstanding response per worker. A
terminated writer cannot corrupt another worker's channel. Metadata is capped by
`max_jobs` (100,000), 64 MiB collectively and one MB per request; there is no
collection of rendered images in RAM. Artifact
promotion reads at most `max_artifact_bytes + 1` bytes. RSS is sampled while jobs
run, over-budget workers are terminated/recovered, and workers recycle after a
configured job count or memory breach. This is a sampled application budget, not
an OS-enforced allocation ceiling; production sizing requires C/E measurements.

Dependencies must be verified before dispatch. Parent output hashes enter child
contracts; B requires those identities when planning, not hypothetical future
hashes. C must integrate staged expansion for newly generated parents. Durable
output claims prevent same-destination writers across orchestrators. Cache reuse
checks input bytes, renderer environment, finalized receipt and output bytes;
composer artifacts also require the approved JPEG dimensions/mode. Corrupt retained
outputs fail closed rather than overwrite. Verified deduplication remains explicit.

Timeouts/crashes/errors have bounded configured retries; retained failed jobs need
explicit retry authorization. Cancellation terminates/reaps only owned workers,
marks interrupted jobs and retains verified receipts. Abrupt parent loss is
recovered after lease expiry; unowned/live leases are not stolen. Private staged
outputs are promoted atomically/exclusively, with receipts finalized afterward;
resume can verify matching owned bytes after interrupted promotion.

B records throughput, worker starts/PIDs, in-flight maximum, parent/worker RSS,
worker I/O counters, recycling and cache-hit rates for synthetic tests. C validates
actual composer workloads; D adds overlay/preview adapters; E benchmarks the full
system against the legacy process-per-poster generator. No production speedup is
claimed from the B proof. Multilingual preflight remains independent of rendering.

Use isolated owned workspaces outside source/logo trees. The current composer's
exclusive final copy is not atomic visibility to readers, so call it into a private
job workspace. Verify/fsync its result, then promote a unique staged sibling to
the final destination under a versioned output reservation/lock. No blind
`os.replace` over existing unowned files; explicit force requires expected target
hash, backup/receipt and owned-path validation. Atomic promotion must be tested
on both Windows and Linux. Preserve composer behavior, not its temporary location.

Cache hit requires matching complete render fingerprint AND retained output SHA,
decoding/format/dimensions and finalized receipt. A crashed/partial file is not a
success. Generated children include actual verified parent bytes in fingerprints.
Content-addressed shared artifacts permit safe dedup; language output references
and approvals stay explicit. Retention removes only unreferenced owned cache/
temporary artifacts, never sources, review evidence or published repository files.

Overlay specs/results use their own fingerprint and expected PNG output contract;
preserve alpha, trim semantics and color handling through explicit validated
operations. Do not route them through the JPEG poster composer. Package D must
demonstrate differences or equivalence with real trim/no-trim standard/bigger cases.

## CLI and Python Contracts

Implemented entry point: `py -3.13 -m create_defaults.bulk`. B provides
`list-categories`, `list-languages`, `validate-definitions`, `audit-colors`,
`suggest-colors`, `discover-assets`, `remote-inventory` and `plan`. See `bulk/README.md`
for executable examples. The broader command table below is a future C/D/E contract:
preflight/preview/render/review/report/resume commands do not exist yet. Worker
execution is a callable B API/proof, not a production generation CLI.

| Command | Shared service contract / effect |
| --- | --- |
| `list-categories`, `list-languages` | Return supported selectors, aliases/applicability/availability; no generation/network. |
| `discover-assets` | `discover_assets(config) -> AssetReport`; read-only inventory and proposed definitions, no automatic persistence. |
| `audit-colors`, `suggest-colors --poster ID` | `audit_colors(definitions, policy)` / `suggest_colors(asset, policy, snapshot)`; ranked proposals, no approved-color mutation. |
| `plan` | `plan(selection, definitions, translations, config) -> Manifest`; no render/network. |
| `preflight` | `preflight(manifest, policy) -> ValidationReport`; all applicable selected variants, no full poster requirement. |
| `preview` | `preview(manifest, selection, risk_policy) -> BatchResult`; explicit rendered sample, no output approval. |
| `render` | `render(manifest, options, cancellation) -> BatchResult`; final local artifacts; verification required. |
| `validate --mode preflight|review|full` | `validate(manifest, mode, references) -> CoverageReport`; never infer full coverage from review. |
| `review export`, `review decide` | `export_review(selection)` / `record_decision(request, expected_versions)`; static review report or explicit per-language/group decision. |
| `compare-remote` | `inventory.refresh(config)` only with explicit refresh, then `compare_selected(manifest, snapshot, requested_paths)`; selected GET-only downloads. |
| `report` | `report(plan_id, filters) -> ReportPaths`; human-first ranking/crops/progress, JSON evidence alongside. |
| `resume` | `resume(plan_id, retry_failed=False, options=...)`; verify inputs/artifacts and ownership first, do not regenerate based solely on filenames. |

Selectors: repeatable `--category` (existing case-insensitive aliases), `--poster`
(exact stable ID), repeatable `--language`, mutually exclusive `--all-languages`.
`--all` explicitly selects everything; no selector performs no generation. `--only
missing` selects absent valid outputs; `--only changed` checks material fingerprints
and retained artifacts. Always expand required dependencies. Unavailable languages
block or are reported excluded by an explicit policy, never silently skipped.

Common controls: `--output-dir`, `--manifest`, `--dry-run`, `--force`, bounded
`--workers`, `--resume`, `--retry-failed`, `--offline`, `--remote-refresh`.
Reject incompatible flags (`--offline --remote-refresh`, ambiguous manifest vs
new selectors, force without explicit writable output ownership). Dry-run never
reserves colors, approves, renders, downloads or changes state. Default no network;
remote refresh/download operations are explicit. Exit codes proposed: 0 completed
requested operation, 2 invalid request/schema, 3 blocked/incomplete validation,
4 operational failure, 5 stale-version conflict, 130 cancelled. JSON results retain
detailed statuses even when CLI exits nonzero. Prompts are optional, never necessary.

Configuration is immutable and injected into services: CLI > explicit config file
> environment > safe defaults. Environment examples (no secrets):

```text
DEFAULTS_GITHUB_REPOSITORY=Kometa-Team/Default-Images
DEFAULTS_GITHUB_BRANCH=master
DEFAULTS_CACHE_DIR=<local-cache-directory>
DEFAULTS_WORKSPACE_DIR=<owned-workspace-directory>
DEFAULTS_TRANSLATION_DIR=<explicit-local-translations>
DEFAULTS_OUTPUT_DIR=<local-generated-output-directory>
GITHUB_TOKEN=<optional-read-only-token-from-environment>
```

`GH_TOKEN` may be an explicit credential fallback. No automatic People `.env`
loading, elevated privileges or personal absolute paths. CLI validates roots,
configuration conflicts and repository allowlists. Python callers pass typed
records and receive the same result/error contracts, without parsing CLI text.
A later Flask service can supply identity/cancellation/configuration to these
services; it must not invoke subprocess CLI wrappers or duplicate business logic.

## Package C Implementation Note

The inactive local generator now implements staged category rendering in
`bulk/generation.py`. Parent artifacts are verified before dependent planning;
the persistent pool remains alive between stages. Full selected-graph collision
checks happen before rendering, including cross-stage paths. A combined canonical
manifest preserves all staged jobs and actual dependency identities.

State schema 6 extends output claims with previous state/SHA preconditions.
Changed output replacement is limited to the same logical owner, a verified
previous receipt and exact retained bytes. Reservation/promotion serialize under
SQLite write transactions; historical verified receipts remain immutable. A
rollback to old parameters is a new generation, not resurrection of a stale
terminal job record. Corrupt/unowned outputs still block rather than being adopted.

Category data, named generators, schema checks and explicit English fitting
evidence live separately from the validated composer. Generator origins contain
bounded specification hashes rather than repeating entire year-fitting tables
inside every expanded job. Small successful schema validations are cached with
an explicit entry/byte bound; no rendered-image collection is held in RAM.

This implements Package C only. Overlay production, complete multilingual fitting,
review approval and production cutover remain outside the implemented boundary.

## Package D: Shared Preflight and Review

The previous paragraph records Package C's historical boundary. Package D is
separately authorized; cutover and Package E remain deferred.

`languages.py` provides content-addressed immutable registry snapshots, exact
compatibility identifiers and verified offline Git/YAML resource caches.
`preflight.py` resolves the selected graph and only required keys/dependencies,
using the existing compositor's shaping, wrapping and FreeType glyph metrics.
Shared per-run asset identities and bounded font/measurement caches avoid
repeated immutable work; changes between validation scopes are detected.
The checked-in metadata index enables scoped catalog loads without a full audit.

`generation.py`, `services.preview` and `delta.regenerate` all use this engine
before the existing persistent spawn pool. Dependencies retain staged real-byte
verification; no fabricated parent identities or subprocess-per-poster path is
introduced. `overlays.py` adds structured Pillow transforms to the same worker
dispatch, bounded queues, owned output claims, atomic writes and receipts.

SQLite migration 7 adds current review state, immutable revision/batch evidence
and indexed translation dependencies. Individual and group decisions use owned
write transactions and expected versions. Exact input/image/policy fingerprints
prevent stale approvals; changes in one translation do not blanket-invalidate
other languages. Review metadata separates private intermediates, shared
destination mappings and final outputs. Overlay review reuses these APIs but
requires individual acceptance of transformation warnings.

Migration 8 indexes owned render fingerprints for verified shared-artifact reuse
across language stages and new pools. Reuse checks exact payload, worker identity,
receipt and current bytes before atomically creating each required destination.
Unavailable-resource changes invalidate translation dependents, not unrelated
captionless artwork. The final approval guard also verifies current output
generation ownership and renderer identity, even when replacement bytes match.

Reports remain JSON/CSV/HTML local artifacts, not a web service. No Flask,
authentication, authorization service or publication workflow is introduced.
Source snapshots cannot refresh a running render implicitly. A fresh explicit
preflight/delta is required after external translation/definition edits.
See [Package D Usage](PACKAGE_D_USAGE.md) for the API and exit contracts.


## Package E authorized validation

The maintainer subsequently approved Gates A-D and authorized Package E from
`166a007c00f14b166a97be8887a4532ea42078b8`. Earlier boundary statements record
historical gate decisions. Deployment and production cutover remain unauthorized.

Package E adds opt-in local acceptance tools (`bulk/e_*.py`) around the existing
planner, mandatory preflight, persistent workers, read-only inventory, review and
color services. Full renders and benchmarks require explicit selection and use
separate output/cache/work roots, conservative sampled resource limits and worker
limits. Ordinary PR CI runs a bounded offline smoke and retains only selected
review artifacts. Full output collections and databases remain ignored.

Cache reuse keeps exact input/output hashing and finalized database receipt checks.
It avoids redundant full decoding of already verified immutable bytes; new atomic
promotions still require full image decoding. Loaded pinned-library metadata is
cached per process, while renderer source identities are recomputed. The worker
scheduler checks sources before starting/dispatching and drains buffered success
responses before classifying retiring workers as failed. All changes require
focused regression evidence; see [Package E report](PACKAGE_E_REPORT.md).


Scoped generated-family selection includes the dependency closure of every child,
while a single logical-child selection loads only its required definitions. The
benchmark harness separately excludes family selectors and caps its effective graph
at 64 outputs. These rules prevent missing-parent failures and accidental broad
benchmark expansion without changing any poster definition or rendering parameter.

Package E additionally preserves ICC source alpha separately from grayscale/RGB
color conversion before overlay trimming/resizing. Exact renderer source hashes
change even where a corrected transform produces identical bytes; review approval
still requires its existing exact context. The expanded legacy comparison found
this defect independently of Windows/Linux pixel parity. Source-mode inventory
and before/after evidence are retained in the Package E report.

[Package E usage](PACKAGE_E_USAGE.md) documents bounded reproducible commands,
resource/ownership constraints and the retained-reference prerequisites. These
validation helpers do not enable a publishing path or production authorization.
