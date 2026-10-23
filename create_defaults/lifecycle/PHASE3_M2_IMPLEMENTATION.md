# Phase 3 / M2 implementation and review dossier

2026-10-22. **P3/M1 merged; P3/M2 implemented pending maintainer review.**
Phase 3 remains IN PROGRESS. P3/M3–M5 and Phases 4–6 remain NOT STARTED.

## Authorized baseline

Fetched current main and independently verified prerequisite merges: planning
PR #24 `78464d2d051dc5da5f305bc4fd9f03868999636f`, bounded CI PR #25
`9022c7c7639f3a2238e5941ec79cc250e4a8ca85`, M1 PR #26
`b8d0c1c5ba6bdff7c3e4045d2add505af0417348`. The implementation branch is
`feat/lifecycle-phase3-m2-translation-preflight`, starting at that exact main.
The [approved proposal](PHASE3_DESIGN_PROPOSAL.md),
[behaviour audit](PHASE3_EXISTING_BEHAVIOUR_AUDIT.md),
[M1 foundation](PHASE3_M1_IMPLEMENTATION.md) and
[six-phase roadmap](ROADMAP.md) remain authoritative.

## Implementation and diagnostic contract

The [API, required-key rules and diagnostics](../bulk/contracts/translation_preflight/README.md)
describe exact callable signatures, trust boundaries, bounds and impact semantics.
New code lives solely in the opt-in `contracts/translation_preflight/` package.
There is no production import, CLI, state framework or writer. Existing M1
documents, Package E loaders, M5 expansion, M6 contracts and translation resolver
are reused without changing their schemas, source or historical behavior.

| Component | Delivered boundary |
| --- | --- |
| Real effective-definition adapter | Source pin verification plus actual loader/generator replay, exact language overrides, output names, closed contract variant/caption/style/fitting checks |
| Overlay adapter | Exact pinned historical M2 record/member/branch, source-preserving empty caption keys; no pixel-based text inference |
| Snapshot adapter | Existing LanguageSnapshot, explicit detached resource bytes, SHA-256/Git blob/size verification, scoped English/requested-language projection |
| M1 integration | Unchanged ValidationSubject, TranslationSelection, LanguagePolicy, references and SourceVerificationContext; immutable canonical hashes |
| Engine | Full key/value diagnostics, raw values/actual key spelling, existing resolution/fallback traces, independent content and provenance status, explicit completeness and technical scope |
| Evidence | Additive closed schema/model, exact subject/policy/source/dependency pins, per-key coverage and replay under independent expected hash/context |
| Currentness | Default unavailable; exact trusted-caller binding; no live verifier, arbitrary TTL, clock, fabricated review or operational grant |

P3-D01 is enforced by separating integrity, explicit source context and currentness.
P3-D04 requires both exact contract-language and policy coverage; real English-only
Playlist cannot pass French even with valid content. P3-D02/D03 stay represented
by M1 and separate future destination/authority work; M2 creates no ownership or
publication bypass. No actual non-English category contract is added.

The M1 source schema cannot encode an empty resource list. M2 explicitly uses a
null selection for zero keys or wholly unavailable resources rather than altering
the frozen schema or fabricating input. Current overlay contracts have no language
permission field; M2 preserves historical English and blocks non-English until a
separately reviewed versioned contract can represent it. These are documented
interface limits, not exceptions to policy.

Relevant resource/comment changes invalidate content-impact evidence even when
the visible text does not change. Unrelated languages/unused resources do not.
Commit/tree changes require a new explicit observation/context while unchanged
scoped content retains its impact token. Neither token nor stored report can
establish upstream currentness. Revalidation recomputes all evidence and never
silently refreshes or rewrites immutable records.

## Test and CI inventory

All **263 M1 focused IDs are retained**, with **124 additive M2 cases** (387 total).
The focused ID snapshot remains explicit. M2 includes actual Playlist and
AudioLanguage expansion/template resolution, captionless Aspect, strict overlay
records, the existing English fixture and frozen Package D Git snapshot, plus
synthetic multilingual/versioned contexts. No full-library capture is duplicated
by the focused job.

Positive and negative coverage includes malformed UTF-8/YAML/aliases/duplicate
keys, unavailable resources, missing English/requested/template keys, empty and
non-string values, placeholders, exact IDs/aliases, English-only bypasses,
reviewed fallback attempts, accent/Unicode/long strings, changed values/same-text
sources, unrelated resources, substituted source/context/policy/subject/contract,
altered or rehashed reports, incomplete coverage, interruption, strict bounds,
real YAML overrides, import/write/network/clock/image/worker isolation and exact
revalidation. Tests retain all original assertions and mandatory CI negatives.

The fixed [full canonical evidence](../phase3/tests/translation-preflight-v1.json)
hash is `345dfe0adc961576940b0f59714caa953669d08f0e07fa216cfbde2f0117cbbd`.
Both platforms must reproduce its complete bytes/value and SHA-256. The six M1
vectors and frozen foundation schema are unchanged.

Local reproduction: `python ci/phase3.py run`. Exact final commit, focused results,
all 21 Windows/Linux checks, per-job counts/times, full original and additive
node-ID reconciliation and historical/resource evidence are recorded in this
draft PR's acceptance report after the complete final-head run. This dossier's
required historical invariants are not a substitute for those fresh results.

Local validation passed: **387 focused tests**, no skips, complete fresh ID
collection/execution reconciliation and six unchanged M1 canonical vectors;
compilation, whitespace checks, 34 local documentation links and byte-for-byte
preservation of the permanent six-phase roadmap section also passed. These are
local results, separate from the final-head Windows/Linux acceptance report.

The established Phase 3 matrix and mandatory **Validation acceptance** already
execute the focused root, so no workflow, job limit, production pin, legacy
selection or non-pytest command changes. Distinct `phase3-collection.json`,
`phase3-execution.json`, `phase3-report.json` and `phase3-foundations-*` artifacts
remain separate from legacy evidence names. The 15-minute cap and 512 MiB
worker-parent safeguard remain intact. Branch-protection settings are unchanged.

## Changed-file inventory and historical requirements

* New `bulk/contracts/translation_preflight/`: `__init__.py`, `adapters.py`,
  `sources.py`, `engine.py`, `models.py`, `evidence-v1.schema.json`, `README.md`.
* New `phase3/tests/`: `translation_samples.py`, `test_translation_preflight.py`,
  `test_translation_boundaries.py`, `translation-preflight-v1.json`.
* Updated `ci/phase3-test-ids.json` only for additive focused collection.
* New this dossier; progress-only updates to `PHASE3_DESIGN_PROPOSAL.md` and
  `ROADMAP.md`, retaining approved policies and all six permanent phases.

No other tracked file may change. In particular the workflow, all 190 production
pins/sources, 22 category packages, 278 variants, definitions, artwork, fonts,
translations, publication destinations, frozen receipts and M1 vectors remain
unchanged. Full CI must retain all 14,079 historical outputs (14,077 public, two
private), zero unexplained differences, all 22 missing approvals, and zero real
READY/ACTIVE contracts. No image is generated by M2.

## Remaining limitations and P3/M3 handoff

* Operational source currentness remains unavailable without a separately
  authorized trusted verifier and explicit readiness-consumption protocol. M1's
  context object and a selected historical snapshot are not authenticators.
* M2 does not validate live ownership, destinations, repository inventories or
  credentials. M3 must consume exact subject/language/policy references, preserve
  official English-only routing and validate each target independently. Empty
  translation keys never waive those checks.
* Real non-English category permission, glyph/RTL/fitting and visual approval
  remain separate requirements. No actual multilingual package is introduced.
* Stable impact comparison is not stale-evidence reuse. P3/M4, when authorized,
  must combine current companions with all existing approval/activation gates;
  no current caller consumes these records as readiness authority.
* The existing parent contract package imports some worker definitions transitively.
  M2 adds no worker or production-entry import and invokes no workers, clocks,
  image processing, network, state or writes. Cold import and guarded real
  evaluation tests enforce those boundaries.

No P3/M3 implementation, readiness consumption, activation, publication, Timeline
Order request processing, later phase or merge is authorized. Stop for M2 review.
