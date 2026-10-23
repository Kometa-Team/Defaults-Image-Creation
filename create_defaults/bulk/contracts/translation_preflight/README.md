# P3/M2 read-only translation preflight

This opt-in metadata API reads explicitly selected inputs. It has no CLI,
production hook, writer, state store, refresh operation or readiness transition.
Its [implementation dossier](../../../lifecycle/PHASE3_M2_IMPLEMENTATION.md)
records the authorized scope and remaining integration questions.

## Controlled input and enumeration

`PosterRequest` takes a real M5 `Resolution`, stable identity, exact M6 `Package`,
independently selected contract/rules hashes, closed variant, assigned outputs
and review-context hash. `prepare(request, policy, requested)` returns the exact
M1 `ValidationSubject` plus effective definition, dependencies, caption,
applicability, language/contract scope, effective-rule consistency and keys.
This is an inspection result, never an approved request.

The adapter verifies current source pins, re-enters Package E's real YAML/profile
loader and generator expansion, and compares the complete replay. It applies the
actual language override through `Resolution.definition`. Loose expanded JSON,
altered output names, a foreign category/variant or stale source container fails.
The selected rule's exact caption definitions, protected composer style and
fitting shape are checked. Missing category approval remains an independent gate;
checksums and implementation packages grant no authority.

For an applicable effective caption in `translation` mode, the bounded required
set is the union of `caption.key` and nonempty `caption.template_key`. Roles are
retained if both reference one key. Both requested-language and authoritative
English values are checked. `shared`/`none` captions have zero translation keys.
Explicitly inapplicable designs have zero required keys and a blocking scope
diagnostic. Logo text never contributes a key. No legacy multilingual expansion
from `preflight.effective_language` is used to widen an English-only contract.

`OverlayRequest` consumes one exact existing M2 `HistoricalOutput` and pinned M6
package/rules/member/branch. Its source-preserving definition has no caption keys.
The current overlay contract wire format has no non-English language permission;
historical English is retained and non-English fails scope. An empty key set
does not waive language policy, category approval or future destination checks.
Overlay companion-size validation remains an independent existing M6 gate.

The approved fallback specification is bound by the effective definition and
recorded verbatim. Legacy resolution uses the existing `Translations.resolve`
with exactly the selected parsed bytes, retaining case/template/suffix/fallback
traces. Missing requested content remains blocking even if that trace resolves
to English or a reviewed literal. A fallback from an unselected third-language
resource cannot be silently fetched. Fallback records grant no new approval.

## Explicit snapshot selection and trust

`SnapshotInput` takes an existing immutable Package E `LanguageSnapshot`, explicit
repository identity and detached `(exact_resource_path, bytes_or_none)` pairs.
It verifies the snapshot's schema/canonical self-pin and selects only the English
and resolved-language defaults records needed by the actual key set. Each
available selected blob must match SHA-256, Git blob SHA-1 and recorded size.
Repository numeric identities are controlled-caller inputs, checked against M1
selection metadata; no checksum authenticates their external origin.

`selection_value(...)` builds the existing M1 `TranslationSelection` from that
projection and actual source/value traces. Its `verification` argument is an
explicit **claim**, not authority. `evaluate` independently recomputes complete
coverage, all values, source bindings and the M1 references; missing or additional
selection traces fail. No prior report is rewritten.

The frozen M1 source schema requires at least one resource. For no required keys,
or wholly unavailable resources, the additive M2 report uses an explicit null M1
selection and permits an empty observed-resource list. It does not invent a
dummy translation or widen the frozen schema. Unavailable required content still
gets a complete per-key failure result. `snapshot_sha256` is explicitly the
**selected projection** hash, not the global snapshot's historical receipt hash.
The projection retains selected records and repository identity; source provenance
retains the available exact commit/tree/blob/path pins separately.

`SourceVerificationContext` is the unchanged typed M1 trusted-caller interface.
Every selection/source/commit/tree/issuer/version/time/context pin must match.
`SourceVerifier.verify` is called only after those bindings pass; provider choice
comes from trusted code, never evidence JSON. The only supplied implementation,
`UnavailableSourceVerifier`, cannot establish currentness. A future authorized
provider must independently reobserve source facts. No such live provider,
ownership provider, credentials, Weblate review data, translator attribution,
TTL, network synchronization or clock lookup is supplied here. Synthetic outcomes
remain `synthetic-current` and cannot establish real translation eligibility.

## Diagnostics and complete evidence

Each required `(key, language)` has a content status and a separate provenance
status, so valid text cannot hide stale or unverifiable context.

| Content status | Meaning |
| --- | --- |
| `available` | Exact raw string exists and passes content checks |
| `missing` | Resource parsed but key lookup failed under existing legacy matching |
| `resource_unavailable` | Resource not discovered/available or selected bytes absent |
| `invalid_source` | Invalid UTF-8/YAML/mapping, aliases, duplicates, ambiguous keys, non-JSON data or resource bound exceeded |
| `invalid_translation` | Empty/whitespace, non-string or over existing 16,384-character resolver bound |
| `unresolved_placeholder` | Sentinel or unresolved caption marker |
| `unverifiable_provenance` | Actual bytes/size disagree with selected SHA-256/Git blob |

Provenance is `unavailable`, `unverifiable`, `stale`, `verified-current` or
`synthetic-current`. With no required resource it is `not_applicable`. Root
`key_status=not_applicable` represents an accurately empty key set; no fake row
is created. A template may contain legacy replacement markers; the unchanged
resolver checks the final result for unresolved markers. Length differences from
English, accents and Unicode do not independently block. Raw values, actual
matched key spelling, canonical invalid raw JSON and their hashes remain intact.
Glyph coverage, RTL, fitting, logo and visual acceptance are independent.

[evidence-v1.schema.json](evidence-v1.schema.json) closes every object and reuses
the local frozen foundation references. It binds the full M1 subject/output
identities, policy version/hash, M1 selection, effective definition, exact relevant
dependencies, declared and observed resource hashes, all key/value/provenance
results, complete coverage counts, resolution/fallback traces and blockers.
Ordering is explicit and canonical bytes use Package E serialization unchanged.

`technical_eligible` means the complete **content/integrity/contract-language**
screen passed; it deliberately excludes currentness and the listed independent
checks. `translation_eligible` additionally requires verified currentness for
nonempty keys. All results are informational and always have
`publication_authorized=false`, `production_enforcement=false`, `ready=false`,
`active=false`. Even a true technical/translation result cannot authorize a real
contract, destination, readiness transition or publication.

Reports are bounded by the existing strict 8 MiB JSON parser; input resources by
8,000,000 bytes, YAML nesting by 40, and the existing caption resolver by 16,384
characters. The two actual caption fields imply at most two keys/four rows.
Schema bounds also cover diagnostics, traces and raw values. Any overflow,
interruption or incomplete coverage raises an error and returns **no report**;
evidence is never truncated or marked complete after partial evaluation.

## Revalidation and dependency impact

`read_report` establishes structure and an independently selected hash only.
`revalidate` additionally recomputes the entire request under explicit source,
subject, policy, contract, language and verification context, requiring exact
canonical equality. A forged/rehashed report or a stale M1 selection fails replay.
No ambient source refresh or implied reapproval is supported.

`dependency_sha256` binds selected repository identity, exact relevant resource
bytes (including source-only comment changes), observed bytes, key/value traces,
effective definition, contract/rules, policy and review context. It excludes
unused languages/resources. A change anywhere in a **used** resource remains
material even if this caption's visible text is identical; no key-only shortcut
is introduced. It is an impact token, not a freshness capability.

A global commit/tree advance creates a new explicit provenance observation and
M1 context, hence a new immutable report. When relevant resources are unchanged,
the scoped content-impact token stays stable. That does not permit replaying the
old observation as proof of currentness. An unrelated language change at the same
selected provenance leaves the scoped report itself unchanged.

## Reproduction

Use Python 3.13 and existing bulk requirements; run `python ci/phase3.py run`.
The maintained additive ID list covers all original M1 tests plus M2. Both focused
platform jobs and complete legacy groups remain mandatory through **Validation
acceptance**. The full [synthetic canonical fixture](../../../phase3/tests/translation-preflight-v1.json)
must match on both OSes, alongside the six unchanged M1 vectors. Tests also read
the checked-in English source and frozen Package D Git snapshot without network,
image generation, new historical capture or production writes.
