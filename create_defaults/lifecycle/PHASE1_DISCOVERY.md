# Phase 1 discovery and baseline

**Status: IN PROGRESS. Maintainer acceptance: PENDING.** Scope is documentation and read-only discovery. See the [roadmap](ROADMAP.md), [complete category inventory](CATEGORY_RULES_MATRIX.md), [exceptions register](EXCEPTIONS_REGISTER.md) and [prioritized gaps](GAP_ANALYSIS.md).

## Pinned baseline and method

Fresh GitHub API reads on **2026-10-20** confirmed:

| Repository / branch | Exact commit | Interpretation |
| --- | --- | --- |
| Defaults-Image-Creation / main | `e7febf88d1dc8f8b93408e88da78e524b191acea` | Source audit baseline; repository default branch and PR target. No subsequent commits at initial check. |
| Default-Images / master | `dfff31ab08446353844bb97de601c3a64edc8220` | Production artwork baseline, including PR #202. No subsequent commits at initial check. |
| Translations / master | `a7bddf45d0fb2cc37c794af05d5fb807880c9a80` | Separately pinned live translation snapshot; does not replace production's frozen English input. |

The source merge's tree equals the tested PR #12 head `66666cd89616b17b94647080f76083074e03988e`. Its first parent `57ef136833a3f54da2bf1e4ddef98addfa36d583` is the documented source rollback baseline. This historical cutover is separate from the current documentation-only authorization. The committed [production evidence](../bulk/evidence/production-20261019/README.md) describes its earlier checkpoint, including then-pending overlay/cutover steps; those historical statements must not be treated as current head status. Actual merged state is visible in [source PR #12](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/12) and [artwork PR #202](https://github.com/Kometa-Team/Default-Images/pull/202).

Discovery derives selectors from [config.py](../bulk/config.py), loads every poster category through [catalog.py](../bulk/catalog.py) / [definitions.py](../bulk/definitions.py), and expands the complete versioned generator graph with `Planner.expand` in [planner.py](../bulk/planner.py). This operation validates definitions without calling the renderer or workers. The separate [overlay catalog](../bulk/catalog/overlays-v1.json) supplies every overlay group and transform. Exact measured counts, source links and category-specific values are in the category matrix. All nine Playlist PNGs were inspected directly, with original dimensions, alpha bounds and SHA-256 read from their source bytes. No new poster or review gallery was generated.

Measured coverage is **4,372 declared definitions** (4,270 static and 102 generator families), **9,957 concrete posters** (9,955 public and two private) in **21 poster categories**, plus **18 overlay groups / 4,122 transforms**. Read-only validation rehashed **2,049 unique historical nongenerated input path/hash identities** through the explicit byte-bound case ledger, checked every one of the **2,061 overlay input spellings**, and found zero exact or NFC/casefold output collisions. All five documents passed relative-link/anchor and table-shape validation. These checks create no production images.

Rule labels throughout this baseline mean: **ENFORCED** = code check; **INHERITED** = profile/generator default; **CONVENTION** = observed content without a category-specific guard; **EXCEPTION** = intentional or historical divergence; **UNKNOWN** = evidence or maintainer decision outstanding. Proposed submitter permissions and future contract locks are recommendations, never existing enforcement or approval.

## What the current design system actually guarantees

The single [legacy-poster profile](../bulk/catalog/profiles.yml) supplies complete defaults. Definitions can override composer, captions, layouts and other schema-permitted values. [Strict schemas](../bulk/schemas/definition-v1.json) constrain types, ranges, paths and relationships; they do **not** encode Playlist's font, a category's mandatory caption, or submitter-specific edit permissions. All current category languages inherit English; historical definitions can acquire local-only language applicability through [effective_language](../bulk/preflight.py). Authored definitions must declare their support explicitly.

[create_poster.py](../create_poster.py) fixes poster output to 2000 × 3000 RGB JPEG, quality 100 and subsampling 0. Logos resize to a requested **width**, preserving aspect ratio; they are horizontally centered and vertically centered plus `logo_offset`. Caption raster space is 1900 × 1000, centered plus `text_offset`. Positive offsets move downward. Historical captured fitting often measured a **1600 × 1000** box; it is not the same object as the caption raster canvas. Captured measurements bind exact text, font bytes and size, rather than authorizing arbitrary future captions at that size. [poster_text.py](../poster_text.py), [preflight.py](../bulk/preflight.py) and [typography.py](../bulk/typography.py) handle actual text bounds and translation fitting proposals.

The profile's Comfortaa Medium, size 250, white text, white wash, gradient 1, no border and uppercasing are **INHERITED**, not universal category contracts. The matrix measures where content diverges. Font approval is an **ENFORCED global hash/provenance boundary** in [approved-fonts.json](../bulk/baselines/approved-fonts.json); it is not approval to substitute any approved font in any category. Font family, subfamily and numerical weight were read from the bundled font name/OS/2 tables, not inferred from filenames.

## Playlist: all nine definitions and source assets

Source: [playlist.yml](../bulk/catalog/playlist.yml), historical rows 5350–5358 in [create_default_posters.ps1](../create_default_posters.ps1), and the nine [logos_playlist](../logos_playlist) PNGs. The matrix includes each exact stable ID, source filename, source dimensions and background.

| Property | Observed baseline | Classification / proposed boundary |
| --- | --- | --- |
| Caption | Every definition requires `key_names.TIMELINE_ORDER`; current English resolves to `TIMELINE ORDER` after uppercasing | CONVENTION for category requirement; translation lookup and captured measurement are ENFORCED. Propose a required order-type caption from an approved catalog key. |
| Font | Bundled `fonts/BebasNeue-Regular.ttf`, family Bebas Neue, Regular, OS/2 weight 400; SHA-256 `08e4623805102d819f58601e46e345648846075e363b2ceb23313c2d1c83ec73` | Existing approved bytes; propose category lock, not a submitter choice. |
| Size and fitting | All nine size 154, captured bounds 1600 × 1000, minimum 100 / maximum 154; each measurement has separate evidence | CONVENTION plus ENFORCED exact measurement binding. No automatic promise that a different caption fits. |
| Logo | Exact per-brand PNG; width 1600, horizontal center, vertical center −200 | Logo varies per poster; geometry is a proposed category lock. Embedded branding lettering belongs to artwork, not translations. |
| Caption placement | Centered caption surface, vertical center +450; white text | CONVENTION / INHERITED; propose geometry/color lock with reviewed language-specific fitting exceptions. |
| Background / effects | Nine brand colors; gradient 1, white wash true, border false; no average/dominant background sampling | Brand color intentionally varies. Effects are shared conventions proposed for locking. |
| Identity and name | Explicit persisted ID; display/output stems `Brand (Timeline Order)`; source names may differ (DragonBall, dca, X-men) | ID, display, text and asset names must remain independent. No universal slugging or filename cleanup. |
| Destinations | English `defaults-en/playlist/<exact stem>.jpg` locally; `playlist/<exact stem>.jpg` officially | Explicit schema/planner mapping. Historical non-English applicability produces local-only paths; no official multilingual route is inferred. |

All nine logo files were visually inspected. Their intentionally different aspect ratios, embedded brand text, transparency and internal whitespace must be preserved; width-based sizing is not visible-ink normalization. A source that appears white on a white viewer background needs its alpha channel considered, not an inferred blank-image rejection. The metadata table binds the original source bytes; this inspection does not create new publication approvals.

**Proposed new submission content:** brand/display name, requested persistent identity (assigned or confirmed by the maintainer), exact logo filename and provenance, an approved order type/key, appropriate brand color, and proposed local/public path mapping. The maintainer-controlled contract should supply font/weight, fitting policy, placement, logo treatment, effects, output encoding and naming rules. Which colors and order types normal submitters may choose is a Phase 2 decision. Neither the schema nor the current CLI implements those permissions.

**Future order types:** the live translation key findings are recorded in the matrix. Release Order and Watch Order must resolve through existing approved authoritative keys or a separately authorized translation contribution; do not invent a key or silently use an English literal. Supporting another order type also needs explicit filename/identity rules and new caption-bound fitting evidence. Preserve Timeline Order unchanged. This is design investigation only: no additional Playlist definition, poster, key or contract was created.

## Translation architecture and preflight

The [Translations repository](https://github.com/Kometa-Team/Translations) describes itself as synchronized from Kometa's [Weblate service](https://translations.kometa.wiki/), where contributions belong. Anonymous access currently redirects to sign-in; a component-specific contribution URL and live Weblate key metadata could not be independently verified. **UNKNOWN:** exact authenticated Weblate component mapping. The safe existing contribution link is the service landing page, not a guessed key URL.

[languages.refresh](../bulk/languages.py) uses a GET-only [GitHub client](../bulk/remote.py), fixes the authoritative repository to `Kometa-Team/Translations`, discovers `defaults/*.yml`, verifies complete Git trees, blob SHA-1/size and content SHA-256, parses duplicate/case-ambiguous keys, and seals a content-addressed registry. [translations_from_snapshot](../bulk/languages.py) verifies offline resource identities. Explicit local snapshots also exist. Compatibility codes in [config.py](../bulk/config.py) are eleven historical codes, **not** the ceiling on supported discovery. Exact identifiers such as `nb_NO` and `pt-br` cannot be silently aliased.

Ordinary English [operator generation](../bulk/operations.py) defaults to the checked-in [English fixture](../fixtures/english/en.yml); it does not query Weblate or automatically refresh GitHub. The read-only live audit and fixture comparison in the matrix document current drift without changing that input. The snapshot contains available resources, not blanket glyph/layout/publication approval for every language.

| Condition | Current behavior and limitation |
| --- | --- |
| Key absent from catalog / English | `Translations.lookup` raises `missing_translation` for the requested language. English preflight blocks the affected translated variant; no separate semantic authoritative-source-key gate exists for a non-English variant whose own value is present. |
| Non-English value absent/unavailable | Preflight enumerates missing required caption **and template** keys, records language/key/snapshot, affected IDs, categories, fallback and English source, and deduplicates across posters. Missing resource differs from missing key. |
| Empty, invalid or unresolved text | Lookup rejects non-string values, legacy missing sentinel and excessive length; preflight additionally rejects empty required strings. Unresolved placeholders are rejected by resolution. |
| Not applicable | Explicit language/component not-applicable is informational, not a missing translation. Unknown applicability blocks; historical local expansion is separate from authored declarations. |
| Fallback | Only missing/unavailable values permit explicit literal or exact language/key fallback with ID, reviewer, reason and policy version. Invalid values do not silently fall back. The fields record provenance; they do not independently authenticate a maintainer's approval. Fallback remains visible in reports. |
| Glyphs and layout | Font SHA whitelist, Unicode controls, glyph availability, clipping, wrapping and near-edge checks already exist. Captured English fitting binds caption/font/size; translated fitting proposals remain inactive until exact review. Existing measured legacy warnings are not a waiver for new designs. |
| RTL / directionality | Current preflight returns `rtl_awaiting_review` for RTL/directional cases pending script-font, joining, bidi and anchor review. Discovery of Arabic is not production RTL acceptance. |
| Translation changes | [delta.py](../bulk/delta.py) indexes value/key/resource/language changes against key dependencies, selects affected variants, and invalidates relevant reviews. Shared/none captions do not require unrelated translation resources. |

**Can it enumerate missing translations without rendering? Yes, within an explicitly selected and bounded scope.** [preflight.py](../bulk/preflight.py) walks the expanded graph and checks both required keys before caption/font/layout work. Its report retains missing keys even when caption resolution fails. It may load fonts and compute text metrics, but does not render posters. Use an explicit registry plus every intended language; a selected subset is not a complete all-language audit. A hard scope/registry parse failure cannot be mislabeled as a completed enumeration. The scope safety bound is 200,000 variants. The live matrix's key-only enumeration likewise does not claim full all-language typography acceptance.

Phase 3 still needs mandatory authoritative snapshot freshness and required-English-source validation at every supported generation entrypoint, a maintainer-defined supported-language contract, and report-before-full-generation behavior. Current generation defaults to **partial** policy; `strict` and `audit` preflight modes exist, but mandatory all-scope blocking is not universal. Official operator generation is English/overlays; robust user-repository multilingual routing and its destination guard contract remain future work. Existing [test_package_d.py](../bulk/tests/test_package_d.py) covers missing/template keys, partial/strict/audit modes, exact language IDs, applicability, fallbacks, glyphs/RTL and delta selection.

## Identities, paths and impact

| Independent property | Actual source | Risk / guarantee |
| --- | --- | --- |
| Stable poster ID | `definition.id`; generated children use `generators.poster_id(category, output)` | Declared IDs persist independently if maintained. Generated child IDs include output-path slug plus hash: a path rename changes identity today. |
| Display name | `display_name` | Metadata, not necessarily caption or filename. Its change affects definition/review context but not render bytes by itself. |
| Rendered text | Caption mode/key/template/literal/suffix/case | Translation-derived; may differ by language independently of identity and filename. |
| Source filename | Composer logo/font/assets; overlay input | Exact on-disk case checked through directory enumeration even on Windows. |
| Local output | Output directory/filename and language-local root | Schema checks portability; planner checks collisions. Not inferred from display text at publication time. |
| GitHub destination | Explicit `remote_paths`; overlay group/size mapping | Separate, nullable for private/local-only jobs. Official staging is exact manifest membership, not a directory-wide upload. |

[common.relative_path/path_key](../bulk/common.py) reject traversal, absolute/Windows-unsafe components, controls, reserved names and trailing dots/spaces, then compare using NFC normalization plus casefold. [planner.validate_manifest](../bulk/planner.py) rejects duplicate IDs and active local/remote collisions. [asset_cases.py](../bulk/asset_cases.py) enumerates physical entries and permits only explicitly byte-bound historical aliases for frozen evidence. It does not make ordinary inputs case-insensitive. Accents, punctuation and spaces remain literal: `Pokémon`, `Dragon Ball`, `A.C.G.T..jpg`, and `Tokyo MX.png` illustrate why display normalization cannot rewrite source/public names. Current collision measurements are in the matrix; absence of current collisions does not resolve future rename identity.

| Change | Existing impact calculation | Remaining lifecycle gap |
| --- | --- | --- |
| Logo / source artwork | Input content hashes invalidate exact consumers; overlays have two size consumers. Exact case and source basename are guarded. | No generic asset rename transaction or submitter ownership rules. |
| Font | Content hash, approved provenance and renderer/typography context invalidate all consumers. Unapproved bytes block. | No category-contract bulk approval boundary; global approved font is not category permission. |
| Translation value / template | Value traces and delta index select corresponding language/poster variants; changed context stales approvals. | Mandatory authoritative source and destination preflight is incomplete. |
| Profile / category layout | Deep-merged effective values change relevant render fingerprints. Metadata-only edits can preserve pixels but change review context. | No versioned category design contract or automatic scoped bulk authorization. |
| Generator | Version, callback source hash, parameters and parent fingerprint enter generated provenance; explicit bounded year ranges never follow the wall clock automatically. | Generated IDs are path-coupled; expanding/removing family members needs lifecycle semantics. |
| Generated parent poster | Topological dependencies include actual parent artifact bytes; downstream render invalidation follows changed parents. | No general tombstone/rename/delete impact workflow. |
| Renderer / encoding libraries | Python/platform, source, loaded library versions and encoding form renderer identity; operator runtime guard refuses mixed native caches. | No promise of cross-environment SHA equality unless native identities match. |

Workers recheck source hashes and verified receipt/output identities and reuse only valid matching artifacts. Changed inputs render only affected jobs, with generated dependencies revisited as needed. See [test_package_e.py](../bulk/tests/test_package_e.py) for exact rerender sets, unchanged-size/mtime edits, font rejection, metadata cache integrity and two-size overlay invalidation; see [test_definitions_planner.py](../bulk/tests/test_definitions_planner.py) for display-name independence, collisions and dependency cycles. Phase 1 reads these existing tests; it does not rerun render-producing suites.

## Lifecycle and publication capability matrix

FULL means an existing executable capability in its stated scope, not a complete future lifecycle product. PARTIAL means reusable foundations with explicit missing operation semantics.

| Capability | Coverage | Evidence / scope and gap |
| --- | --- | --- |
| ADD | PARTIAL | Authored definitions, exact selectors, overlay definitions, new-destination approval exist. No category contract or unified submitter transaction. |
| UPDATE | PARTIAL | Fingerprint-based generation, previews and exact replacement staging work. No general lifecycle operation model or editable-field authorization. |
| RENAME | PARTIAL | Exact approved **overlay case-only source-basename corrections** work. General poster/display/asset/path rename with stable identity is missing. |
| DELETE | MISSING | No approved generic deletion operation. Final staging reconciliation reports zero deletions; definition omission must not imply remote deletion. |
| Category-wide design update | PARTIAL | Category selection and effective parameter invalidation work. Versioned category contract, impact receipt and bulk design approval are missing. |
| Translation regeneration | FULL, indexed scope | Delta selection, preflight, review invalidation and workers exist. Mandatory catalog/destination safeguards remain separate gaps. |
| Shared-asset regeneration | FULL, indexed scope | Content/dependency fingerprints and verified caches affect actual consumers. Generic rename/removal management missing. |
| Production comparison | FULL, current English/overlays | Pinned inventory, actual bytes/hashes and complete tree reconciliation; unchanged outside paths protected. |
| Preview and approval | FULL, current framework | Exact candidate/context/policy/membership binding, reviews, warnings and stale-decision invalidation. Not implicit category approval. |
| Draft staging | FULL, approved current operations | Non-force resumable technical batches, one draft PR, baseline checks, separate merge authorization. Not a generic delete/rename engine. |
| Remote verification | FULL | Downloaded response SHA-256, Git blob, sizes and complete remote diff; no success from GitHub summary counts alone. |
| Safe rollback | PARTIAL | Production/source commits and retained PowerShell rollback documented; transport interruption recovery proven. No generic reverse transaction for lifecycle rename/delete/dependencies. |

Evidence: [PYTHON_OPERATIONS.md](../PYTHON_OPERATIONS.md), [operator_publication.py](../bulk/operator_publication.py), [library_stage.py](../bulk/library_stage.py), [production_verify.py](../bulk/production_verify.py), [reviews](../review/README.md), [test_operator_workflow.py](../bulk/tests/test_operator_workflow.py), [test_library_stage.py](../bulk/tests/test_library_stage.py).

The binary synchronization rule remains explicit: only equal SHA-256 is `exact_match` and skipped; an approved `renderer_equivalent` with differing bytes is a replacement. Visual approval populations, technical Git batches and publication PR grouping are separate. Neither a preview nor a draft-staging receipt authorizes a merge.

## Phase 1 validation and acceptance boundary

Delivery changes exactly the five Markdown files under `create_defaults/lifecycle/`. Definition loading, graph expansion, font/PNG metadata inspection, local collision checks and verified translation GETs are read-only with respect to tracked source and production. Audit scratch/cache files are ignored under `config/lifecycle-phase1-20261020/` and are not product features. No renderer, definition, profile, font, asset, translation pipeline, production image or Default-Images ref is modified.

Validation checks exact changed-file allowlisting, baseline source diff, relative documentation targets, measured count consistency and PR target/draft state. Existing rendering tests are cited as evidence of implemented behavior, not falsely reported as newly executed. Any automatic PR CI results must be attributed to their actual commit/run. Phase 1 remains IN PROGRESS / PENDING after draft delivery; acceptance and Phase 2 authorization are separate maintainer decisions.
