# Phase 2 Requirements

Status: **Gate A approved, D01-D08 approved; Package B authorized and implemented locally**.
Audit date: 2026-10-16. Source: `main` commit
`57ef136833a3f54da2bf1e4ddef98addfa36d583`. Working branch:
`feat/default-posters-python-generator`. Packages C-E require separate authorization.
No permission to commit, push, publish, deploy or install software is implied.

## Delivered Scope

- Four Package A documents, a fresh current-source audit, historical color usage,
  parser-only category/alias/translation inspection, and a small YAML validation experiment.
- Four real examples: corrected Death in Paradise (2011), Action, Arrowverse
  timeline order, and fixed-size Jakarta Year 2020. They demonstrate representation,
  inheritance and schema validation, not a migrated production generator.
- Package B adds `bulk/` schemas, planner, read-only inventory, color registry,
  translations, state/workspaces, CLI and persistent worker infrastructure.
- Both original PowerShell scripts, the validated composer, historical Phase 1
  fixtures/reports and published Default-Images remain unchanged. People wrappers
  reuse a small neutral GitHub primitive extraction, covered by regression tests.
- No full poster batch, remote artwork download, translation refresh, package
  installation, Flask, authentication, publishing or deployment. Synthetic worker
  tests are infrastructure evidence, not production rendering performance.
- Existing PowerShell workflows remain available. PowerShell/ImageMagick are used
  only as existing local development audit tools, never required by the future runtime.

Read [Category Inventory](PHASE2_CATEGORY_INVENTORY.md) for measured findings,
[Architecture](PHASE2_ARCHITECTURE.md) for interfaces and persistence, and
[Migration Plan](PHASE2_MIGRATION_PLAN.md) for gates, reproduction and test results.

## Acceptance Contracts

| ID | Requirement | Acceptance evidence / stage |
| --- | --- | --- |
| R01 | Preserve every current category, alias, source row, dependency and output contract, with explicitly approved retirements recorded rather than hidden; never assume historical counts are permanent. | Fresh source/hash-bound inventory in A; per-category canonical manifest comparison and decision-linked differences in C; complete required outputs in E. |
| R02 | Versioned YAML, stable logical IDs, explicit defaults and inheritance, JSON expanded jobs, Python dynamic rules. | A schemas and real examples; B strict validated models; no PowerShell evaluation at runtime. |
| R03 | Preserve effective colors, fonts, dimensions, names, casing, numeric fallbacks and layout. | Explicit compatibility ledger; image comparison in C/E. Approved Jakarta remains fixed 409, Playlist Bebas Neue cap 154. |
| R04 | Safe asset discovery: unassigned logos, missing sources, unsupported formats, identity/path collisions and unused candidates. | B inventory classification; C candidate definition workflow; never delete or auto-approve assets. |
| R05 | Preserve historical colors; enforce D01 category-local exact uniqueness for new unrelated logical posters, explicit related reuse and audited manual exceptions; perceptual similarity warns only. | A literal/direct/generated audit and approved policy specification; B logical-assignment, informational cross-category collision, warning-only similarity, exception and transactional reservation tests. No historical recoloring. |
| R06 | Preserve all eleven exact language identifiers and production key/case/placeholder semantics. | A source inspection; B translation identity model; D tests with explicitly supplied local files. English evidence is not multilingual parity. |
| R07 | Offline translation files, explicit fallback, source hashes, glyph coverage, script/shaping/direction, wrapping and clipping diagnostics. | D preflight for every applicable variant; missing font coverage blocks, not silent substitution. |
| R08 | Three modes: preflight all selected variants, risk-based review previews, full required artifacts. | D/E coverage ledger distinguishes inspected, rendered, reused, untested, failed and not-applicable. |
| R09 | Language-specific review, exact-version group approval, accepted-warning evidence and invalidation. | D transactional approval tests, immutable decision history, source/spec/image SHA-256 binding. Rendering is not approval. |
| R10 | Long-running orchestrator and bounded persistent spawn workers calling the approved composer API directly; never a CLI subprocess per poster. Deterministic planning, verified cache, durable resume/retry/cancel/timeouts/recovery, recycling, memory limits and private workspaces. | B worker API, bounded synthetic proof and fault tests; C real category workloads; D overlays/previews; E measured full-system comparison. |
| R11 | Clone-free read-only GitHub inventory, complete large-tree traversal, cached metadata, exact paths and selective integrity-checked downloads. | A People reuse plan; B mocked API/cache tests; E selected published-image comparisons. |
| R12 | Distinct Python overlay pipeline preserving trim, resize, alpha, metadata and naming behavior. | A 36-operation/expanded-file inventory; D isolated pixel/dimension/path tests. Not ordinary poster jobs. |
| R13 | Safe local output and remote-path mapping, collision prevention, no accidental overwrite, no publication capability. | B/C normalized collision keys plus exact paths; confinement/link tests; implement approved D02 with exactly one red Splatter output and reject conflicting active definitions. |
| R14 | Windows/Linux, Python 3.13 primary, shared Python APIs behind CLI and any later web service. | Fast PR tests; E platform validation and performance measurements. No shell or personal path dependency. |
| R15 | Reproducible source-controlled specifications, generated manifests, review evidence and reports kept separate. | Schema versions and hashes, explicit scope, sanitized relative paths; no bulk image datasets or credentials in Git. |

## Operator Workflow

Add a logo; discover assets; resolve category/identity ambiguities; create a
candidate using category defaults; obtain ranked color proposals; select and
reserve a color; preview; approve the specification; persist reviewed YAML;
plan applicable languages; preflight; render high-risk previews; review exact
versions; render or verify retained final artifacts; approve eligible groups or
individual variants; retain local verified artifacts. Publishing is a separate,
future authorization and implementation, not a Phase 2 step.

Specification approval only permits generation. Output approval requires an
actual, verified image. Operators must be able to review a category, one poster
across languages, full-resolution images, caption/problem crops, old/new and
published comparisons, unresolved warnings and overall progress. Reports must
explain each warning in ordinary language, identify the affected region and
measured threshold, rank worst first, and group only genuinely comparable cases.
Machine JSON is supporting evidence, not the primary review experience.

## Maintainer Decisions: Gate A

**D01-D08 and Gate A are APPROVED / RESOLVED by the maintainer.** Package B
is authorized. This approval does not authorize Package C or production migration.

| Approved decision | Policy | Implementation stage |
| --- | --- | --- |
| D01 Color scope and exceptions: APPROVED / RESOLVED | Preserve every existing background, including historical duplicates. New unrelated logical posters require normalized exact HEX uniqueness within their category; cross-category exact reuse is informational. Explicitly linked related posters/collections/generated variants may intentionally reuse colors without warnings. Perceptual similarity warns only. Authorized named overrides require reviewer identity, justification, policy version and affected poster identities. | B registry/reservations implemented; D preview/review interfaces remain future |
| D02 Splatter collision: APPROVED / RESOLVED | Maintainer selected the red row at `create_default_posters.ps1:4884` as authoritative: `#990000`, white-wash `0`, output `genre/Splatter.jpg`. The unintended green duplicate at line 4883 (`#416939`, white-wash `1`) is retired from new active Python definitions only. Preserve both original source rows and historical evidence. Keep the red logo, translation, filename and layout unchanged; document the one-job removal in manifest comparison. | Apply in C Genre migration/output mapping; decision resolved, implementation not yet performed |
| D03 Translation fallback: APPROVED | Block missing keys by default; allow an explicit reviewed literal or source-key fallback per definition with provenance. Do not silently replace with English or render `TRANSLATION NOT FOUND`. | B translation loading/planning; D multilingual workflow |
| D04 Language applicability/Arabic: APPROVED | Keep all eleven selectors; explicitly mark shared/no-caption artwork vs translated text. Supply and approve Arabic-capable licensed fonts/layouts before Arabic text can pass. Missing local files are unavailable, not not-applicable. | B applicability/glyph guards; D multilingual acceptance |
| D05 Review risk/group approval: APPROVED | Block missing glyphs/overflow/unsafe paths; require individual review for high-risk RTL/fallback/layout changes. Permit exact-version group approval of automatically verified low-risk outputs with enumerated accepted warnings, reviewer/time and truthful sample-inspection records. Thresholds must be measured and versioned. | D approval eligibility; not a B review UI |
| D06 Approval storage: APPROVED | SQLite with migrations, local disk, WAL/busy timeout, optimistic versions and immutable events; JSON receipts for audit. No DB server. Future multi-host service requires a different coordination boundary, not a shared network SQLite file. | B state implementation; D approval decisions |
| D07 Definition organization: APPROVED | Category YAML files, one shared-default profile layer, explicit named Python generators and stable IDs allocated once. No implicit YAML anchors, multi-parent inheritance or expression evaluation. IDs remain unchanged after display-name edits. | B production schemas; C category rules |
| D08 Compatibility exceptions: APPROVED | Preserve raw/effective coercions, no-op dominant-color flags, captured fitting behavior and intermediate artifacts explicitly. Persist random draws in manifests, not historical color assignments. Validate corrected current source separately while keeping Phase 1 immutable. Any equivalence reuse requires explicit verified evidence. | B separate baselines; C/E parity acceptance |

### D01 Acceptance Contract

The approved initial color policy is identified as `defaults-colors-v1` (D01).
Its six rules are:

1. Preserve all existing background colors and historical duplicates unchanged;
   preservation does not declare their original intent or create approved exceptions.
2. Require normalized exact HEX uniqueness for a new unrelated logical poster
   within its category. Existing historical assignments reserve their colors.
3. Allow exact reuse across categories; report the cross-category collision as
   information, not a warning or blocker.
4. Allow intentional reuse among explicitly linked related posters, collections
   and generated variants without collision warnings. Do not infer relationships
   from shared colors, captions, filenames or category membership alone.
5. Report perceptually similar, nonidentical colors as warnings under configurable,
   versioned thresholds; similarity alone must never block reservation or approval.
6. Permit an otherwise prohibited exact duplicate only through an authorized
   manual override recording reviewer identity, justification, policy version and
   every affected poster identity, with a stable named exception and audit history.

Compare validated six-digit colors using canonical uppercase `#RRGGBB`; retain
original source spelling/provenance. Enforce at logical color-assignment level,
not once per rendered language/output. Distinguish independently selected colors
from inherited/template colors and record explicit parent/relationship links;
template provenance alone does not authorize unrelated reuse.

Persist approved new choices deterministically. Serialize reservation checks
against historical assignments, committed new choices and live reservations;
revalidate relationships, exceptions and policy versions at approval/commit.
Never automatically recolor an existing poster, silently grant an exception or
let concurrent requests bypass exact uniqueness. Future preview/review must
explain exact collisions, similar-color warnings and permitted named exceptions.
The [registry specification](PHASE2_ARCHITECTURE.md#color-registry-specification-d01)
defines the records, diagnostic precedence and concurrency contract. This update
does not change source colors, audit evidence, runtime code or rendered artifacts.

### D02 Acceptance Contract

Package C must produce exactly one active Splatter rendering job per selected
applicable language, targeting the unchanged relative path `genre/Splatter.jpg`.
Use source line 4884, `SPLATTER` / `Splatter.png`, background `#990000` and
white-wash disabled. Preserve its existing translation lookup/case behavior,
font, fitting, logo sizing/placement, caption placement, gradient and border
settings. Line 4883 must remain traceable as a retired audit entry with no active
job; it is not an optional generated variant or an approved duplicate-output exception.

Reject conflicting active definitions before manifest generation/rendering,
including case/NFC-equivalent output paths. Do not resolve conflicts by queue
order, silent overwrite, or silently discarding a definition. Preserve original
PowerShell, Phase 1 fixtures, rendered evidence and validation results. Keep
historical counts unchanged and show the approved retirement explicitly in the
new manifest comparison. Full source rows and fingerprints are retained in the
[D02 migration audit](PHASE2_CATEGORY_INVENTORY.md#d02-splatter-migration-audit).

## Gate Status

- Review package boundaries, API/CLI contracts, definition and manifest schemas.
- Accept the inventory and distinguish fresh capture from historical rendering evidence.
- D01-D08 and Gate A are approved; Package B has explicit implementation authorization.
- Review [Package B Report](PACKAGE_B_REPORT.md) for actual tests and limitations before authorizing C.
- Commits, pushes, PR creation, merging and deployment require separate authorization.
