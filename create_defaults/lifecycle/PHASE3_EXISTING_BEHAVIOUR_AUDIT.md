# Phase 3 existing-behaviour audit

2026-10-22. Read-only discovery for the [Phase 3 proposal](PHASE3_DESIGN_PROPOSAL.md), not implementation or approval. Source baseline: `d35b0684a096277dcdbdea70e4683e0c786325bc`, merged PR #22. Its tree is `2a83fe136e43043096c407f508838e7d5f2479c2`, identical to tested PR #22 head `bb8ba48fffea73e98944681eee6d06279eeae743`.

## Verified external sources

GitHub repository metadata, branch/commit/tree metadata, translation filenames and the Translations README were read. No image bytes were fetched, no translations submitted and no repository content changed.

| Source | Observed identity | Finding |
| --- | --- | --- |
| `Kometa-Team/Translations` | Repository ID `788129726`; owner ID `166754869`; default branch `master`; commit `a7bddf45d0fb2cc37c794af05d5fb807880c9a80`; tree `93e6e9d51c26b5c4903adc059f92e4f848f0f2dd` | `defaults/*.yml` is the verified existing format, not a hypothetical Weblate API response. |
| `Kometa-Team/Default-Images` | Repository ID `474155312`; owner ID `166754869`; default branch `master`; commit `dfff31ab08446353844bb97de601c3a64edc8220`; tree `66d0d890ab177d3d7f139c47f812999edad3a530` | Root category directories match existing public paths; no language-prefix convention may be inferred. |
| Weblate | [Service landing page](https://translations.kometa.wiki/) redirects anonymous visitors to sign-in | An authenticated component/key mapping, API adapter and translation-review identity were not verified. None is assumed. |

The [Translations README](https://github.com/Kometa-Team/Translations/blob/a7bddf45d0fb2cc37c794af05d5fb807880c9a80/README.md) directs contributions to Weblate and says not to submit translation changes to that generated repository. Git provenance is available; it does not prove that an individual value has received a particular Weblate review.

The pinned [defaults directory](https://github.com/Kometa-Team/Translations/tree/a7bddf45d0fb2cc37c794af05d5fb807880c9a80/defaults) contains **14 YAML resources**: `ar`, `bg`, `da`, `de`, `en`, `es`, `fr`, `hu`, `it`, `nb_NO`, `nl`, `pt-br`, `ru`, `sv`. Presence is not completeness, supported typography, contract applicability or publication approval. These are observations at the commit above, not a permanently hard-coded supported-language list.

## Translation inputs and behaviour

| Existing surface | Verified behaviour | Phase 3 gap |
| --- | --- | --- |
| [config.py](../bulk/config.py) | `language_id` validates a bounded ASCII identifier and returns its exact spelling. Eleven compatibility IDs include `nb_NO` and `pt-br`. | Compatibility IDs are not all discovered languages. No implicit case/hyphen/underscore rewrite is justified. |
| [languages.py](../bulk/languages.py) | `LanguageSnapshot` stores exact/native codes, availability, resource SHA-256, provenance and explicit aliases. Refresh is explicit and GET-only, from the fixed Translations repository. Complete Git trees and blob SHA-1/size are checked; offline snapshot loading checks identities. | Integrity does not establish mandatory freshness or per-value Weblate approval. Local snapshots are explicitly local provenance. |
| [translations.py](../bulk/translations.py) | Safe bounded YAML; duplicate/ambiguous key checks; legacy key matching; source/value hashes; exact raw strings; category casing, templates and suffix resolution. Missing resource/key and invalid content are distinct. | No universal authoritative-English-key requirement for a non-English value that exists locally. Lookup alone permits empty strings; preflight rejects empty required values. |
| [d_cli.py](../bulk/d_cli.py) | Existing refresh/preflight/delta commands and local/snapshot input selection. Required English/fallback resources can be selected. | Existing commands also expose generation, preview and invalidation options; calling a broad CLI is not a safe new read-only boundary. |
| [preflight.py](../bulk/preflight.py) | Scoped expanded variants, caption and template key enumeration, missing-key consolidation, explicit applicability, registry/resource binding, glyph/RTL/layout checks, `partial`/`strict`/`audit`/`review` modes. It can measure fonts without rendering posters. | Generation policy is not universally strict. A reviewed fallback may permit legacy resolution despite missing requested-language content. Phase 3 must block missing required non-English translations without rewriting historical fallback behaviour. |
| [delta.py](../bulk/delta.py) and [M5 historical graph](../bulk/contracts/expanded/historical.py) | Existing dependency analysis distinguishes relevant captions/languages. M5 currently binds exact resource hashes **and** key/value provenance. | Do not invent a key-only compatibility shortcut. Add scoped destination/provenance readiness bindings without mutating old graphs or receipts. |

The supported [Python operator](../bulk/operations.py) explicitly requests `languages=['en']` and defaults to the checked-in [English fixture](../fixtures/english/en.yml). It does not silently query Weblate. The [README](../README.md) marks PowerShell as legacy; `create_default_posters.ps1` still has its older master-branch translation download and local replacement prompt. That is historical/rollback behaviour, not a new Phase 3 intake. Neither entry point is changed here.

The [legacy-poster profile](../bulk/catalog/profiles.yml) declares English applicability and empty overrides. The definition schema already supports explicit language applicability and per-language overrides. The [planner](../bulk/planner.py) checks expanded applicability, resolves translations, derives local `defaults-<exact-code>/...` paths and requires an explicit `remote_paths[language]` entry; `null` is unconfirmed/private, not a destination fallback.

Language-specific composition must follow the actual expanded override and asset dependencies. A source filename such as a territorial content-rating logo is not evidence of request language. Branding embedded in a PNG is artwork, not a translation key. Shared/absent captions need no invented translation requirement. Overlays retain source-preserving branches and both sizes, with no caption/font translation pipeline.

## Destination and publication behaviour

[Config](../bulk/config.py) accepts repository/branch through explicit arguments, configuration and supported environment variables, defaulting to `Kometa-Team/Default-Images` / `master`. Validators establish syntax and filesystem separation, **not ownership or publish permission**. [ReadOnlyGitHub](../bulk/remote.py) and RemoteInventory provide GET-only pinned repository/branch inventory; they do not authenticate a user's ownership decision.

Existing official poster paths are category-relative, for example `playlist/Arrowverse (Timeline Order).jpg`. [Overlay catalog](../bulk/catalog/overlays-v1.json) paths include `aspect/overlays/standard/<exact-source-basename>.png` and its bigger companion. No `en/` prefix or user-repository layout is assumed. Existing names, case, punctuation, Unicode and private Awards outputs remain authoritative.

[common.py](../bulk/common.py) provides safe relative paths, confinement/link checks and NFC+casefold collision keys. [Planner manifest validation](../bulk/planner.py) and [publication path checks](../bulk/library_publication.py) already reject conflicting destinations. NFC/casefold is a comparison key, not permission to rewrite a historical filename.

[library_publication.py](../bulk/library_publication.py) binds exact policy, image/context hashes, reviewed membership and baseline. It has no remote write adapter and explicitly distinguishes hash integrity from authentication. [operator_publication.py](../bulk/operator_publication.py) binds an actual explicit maintainer decision and uses existing resumable draft transport; its official authorization/PR target is specifically Default-Images/master. It is not an existing general multilingual user-repository publisher.

**Gap:** no integrated language-to-destination policy, externally verified user-ownership capability or immutable destination-bound readiness receipt was found. Do not describe generic configuration, a reviewer string, a repository called Default-Images, a valid token-shaped string, or a complete inventory as ownership/publication authority. Current official operator generation being English-only does not mean all future callers already have a language safeguard.

## M1–M7 reuse and limits

- [M1 models](../bulk/contracts/models.py): strict bounded canonical documents, stable identities, immutable records and distinct approval/exception/validation stages. [RegistrySnapshot](../bulk/contracts/registry.py) requires externally selected exact pins and a caller-supplied trusted decision map. `TrustedDecision` explicitly is **not an authenticator**.
- [ContractStore](../bulk/contracts/state.py): isolated roots, immutable objects/revisions and Package E transactions/events. Its `pin` and record readers accept specific existing types; a new arbitrary Phase 3 record cannot simply be passed to them. [M4](../bulk/contracts/logos/storage.py) and [M7](../bulk/contracts/activation/storage.py) demonstrate additive isolated sidecars, not a competing persistence framework.
- [M5](../bulk/contracts/expanded/README.md): actual expanded definitions, final job checks, dependencies, review-context freshness and stable output identities. Its graph node-kind set is closed; destination is not an existing general node type. A Phase 3 companion is needed before proposing any graph-schema extension.
- [M6 release](../bulk/contracts/categories/release.py): 22 immutable category packages / 278 variants. [Playlist](../bulk/contracts/playlist/contract-v1.json) explicitly permits `en`; discovering a translated value cannot expand that contract. All D01–D09 designs and historical exceptions remain binding.
- [M7](PHASE2_M7_IMPLEMENTATION.md): separate compatibility, exact approval, readiness and independent activation authority. There is no operational authenticated intake. The [review registry](../bulk/contracts/categories/data/review-registry-v1.json) remains empty: **22 exact approvals outstanding**, zero actual READY/ACTIVE contracts. No lifecycle ADD/UPDATE/RENAME/DELETE request service exists for Phase 3 to invoke.

The immutable M7 dossier is a historical checkpoint; its earlier IN PROGRESS labels do not supersede the merged baseline. The [roadmap](ROADMAP.md) records current project progress separately. Do not rewrite accepted receipts or the 22 packages to make Phase 3 appear approved.

## Baseline validation and CI evidence

[PR #22 repository CI](https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/39864198685) passed at `bb8ba48fffea73e98944681eee6d06279eeae743`, whose tree equals current main above:

| Check | Windows | Linux |
| --- | --- | --- |
| Bulk, including M1–M7 | 1,541 passed | 1,539 passed; two Windows-only skips |
| Unit/font + Phase 2 | 120 + 35 passed | 120 + 35 passed |
| People compatibility | 130 passed | 129 passed; one Windows-only skip |
| Frozen effective jobs | 9,958 verified | 9,958 verified |
| Full job duration | 12m36s, Windows attempt 3 | 11m57s, attempt 1 |

Both final M7 audits accounted for **9,957 posters + 4,122 overlays = 14,079 outputs**, including two private Awards intermediates; 14,077 public outputs; 22 selectors / 278 variants; all 190 protected production files; **zero unexplained differences** and zero actual contract readiness/activation. All 22 approvals remained missing.

Two earlier Windows jobs timed out under the unchanged 15-minute cap, without reported assertion failures. The same historical capture took 188s, 294s and 145s across attempts. One timeout occurred after bulk/smoke success during final People tests. This is measured runtime variability, not evidence that assertions should be weakened or that a particular new sharding scheme already works. New Phase 3 results must name their own exact commit; the baseline above is not a claimed Phase 3 implementation test.

This audit ran only source/metadata reads and documentation validation. No current implementation milestone, fresh full-library Phase 3 compatibility acceptance, image processing, state transition, approval or publication is claimed.
