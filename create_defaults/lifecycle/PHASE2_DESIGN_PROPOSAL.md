# Phase 2 design proposal: category contracts

**Final architecture and implementation plan — implementation NOT STARTED.** Updated 2026-10-20. This revision uses the approved D01–D09 architecture, adopts the recommended D01–D08 defaults, and selects concrete Package E integration for the remaining technical design. Implementation evidence, calibrated metrics and activation remain untested and unauthorized; this document does not manufacture their acceptance. No schema, registry, validator, generator, translation or publication change is implemented. Phases 2–6 remain NOT STARTED in the [six-phase roadmap](ROADMAP.md).

**D09 confirmed maintainer decisions, 2026-10-20:** The remaining logo-policy review is complete. Playlist, Franchise, Genre, Seasonal and Universe default to WHITE_ONLY, with individually approved SOURCE_PRESERVING exceptions. Studio and Overlays use SOURCE_PRESERVING; applicable Chart/Country/Network/Streaming paired designs remain BOTH_REQUIRED. The 17 identified historical alpha/background assets are normal accepted artwork, with no cleanup, warnings or regeneration. New intentional brand-background exceptions use the formal two-stage process below. These decisions supersede earlier D09 mapping recommendations; numeric calibration and record/preview representation are implementation-design questions, not unresolved business policy. No implementation or new previews are authorized. PR #13 and its accepted files are unchanged.

The accepted Phase 1 head `fa276ab5ba1508457c6767f92b21f835794aa483` was merged by the maintainer through [PR #13](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/13) into `main` at `f1965cdb61f9a5d43690ec41c768b79db6b39924`. [Draft PR #14](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/14) now targets **main** and contains only this proposal document. Future implementation belongs on separate branches/PRs, not in either documentation PR. PR #14 must not be merged without authorization.

### Phase 1 merged-baseline and retarget checkpoint — 2026-10-20

Before the maintainer's merge, PR #13 had exactly the five accepted Markdown files, zero commits behind the then-current `main`, and MERGEABLE / CLEAN status. [CI run 39408697574](https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/39408697574) passed Windows and Ubuntu at its exact head `fa276ab5ba1508457c6767f92b21f835794aa483`. GitHub now confirms PR #13 MERGED at `2026-10-20T22:48:15Z`, merge commit `f1965cdb61f9a5d43690ec41c768b79db6b39924` (parents `e7febf88d1dc8f8b93408e88da78e524b191acea` and the accepted Phase 1 head). A full Git tree comparison between the accepted head and merge commit is empty: the roadmap and all accepted documentation/source bytes are preserved. This is the maintainer's completed merge, not an agent merge action. CI at the old head is not reported as new-base Phase 2 CI.

PR #14 was retargeted from `docs/defaults-lifecycle-phase1-discovery` to `main` at that merge commit. The remote diff remains exactly `create_defaults/lifecycle/PHASE2_DESIGN_PROPOSAL.md`, with no Phase 1, production-code or asset changes. Its final pushed head must be checked against this new base by the existing main-targeted Windows/Linux workflow; that result is delivery evidence at the actual head, not a reason to edit and retrigger this document repeatedly.

## Evidence and design objectives

The accepted [discovery](PHASE1_DISCOVERY.md), [category matrix](CATEGORY_RULES_MATRIX.md), [exceptions register](EXCEPTIONS_REGISTER.md) and [gap analysis](GAP_ANALYSIS.md) are the evidence. Their audited runtime-source baseline is `e7febf88d1dc8f8b93408e88da78e524b191acea`, artwork baseline `dfff31ab08446353844bb97de601c3a64edc8220`. Current source `main` adds only the merged Phase 1 documentation at `f1965cdb61f9a5d43690ec41c768b79db6b39924`; production artwork remains separately pinned. This revision neither reclassifies accepted facts nor re-reviews art.

The catalog has 4,372 declared definitions, including 102 generator families, expanding to 9,957 posters (9,955 public and two private), plus 4,122 overlays in 18 groups. These are several design families, not one poster template. [profiles.yml](../bulk/catalog/profiles.yml) supplies defaults; [definitions.py](../bulk/definitions.py) validates generic shape and paths. Neither currently makes a category's font or caption a protected design rule. Existing generated poster IDs in [generators.py](../bulk/generators.py), and overlay IDs in [overlay_definitions.py](../bulk/overlay_definitions.py), depend on paths. Those limitations motivate the following proposed architecture.

Recommended objectives are: preserve every adopted output and identity; make design ownership explicit; accept bounded content submissions without granting style control; validate every effective output and dependency; and produce an auditable impact assessment before any category-wide change. A design approval is separate from artwork approval, staging authorization and merge authorization.

## Final architecture and trust boundaries

| Selected component | Responsibility | Boundary |
| --- | --- | --- |
| Contract package | Immutable category ID, schema version, contract version, content hash, named variants, field classifications, permitted content, typography/geometry/output rules, required logo presentations by output kind, exact transformation provenance and exception references | Maintainer-controlled; a submitter cannot declare a new trusted contract, change its hash or approve their own package. |
| Contract approval record | Exact package/version/hash, maintainer decision and scope, prior baseline, intended changes and approval provenance | Recorded from an actual authorized maintainer decision. A `reviewer` string in submitted YAML is not sufficient authority. |
| Submission content | Stable identity reference, display metadata, approved variant/content type, original PNG/provenance, optional separate white PNG, justified exception requests, approved per-item content values and submitter preview decisions | Transparent PNG is the default; intentional brand backgrounds require an approved exception. Strict allowlist, with no arbitrary composer/profile/font/transform parameters or contributor self-approval. |
| Identity and mapping record | Persisted logical IDs, semantic family-member keys, exact source/local/public mappings and history | Independent of rendered text and output filenames. Existing mappings and IDs are adopted unchanged. General rename/delete execution remains Phase 4. |
| Effective contract resolver | Pinned category base + one explicitly named variant + matching, approved exception; validated content supplies only permitted leaves | Closed, deterministic composition. No arbitrary inheritance, expressions, executable YAML or "last override wins" for locked fields. Unresolved/conflicting rules fail closed. |
| Expanded-definition validator | Compares every materialized poster/overlay job and its provenance against the selected effective rules | Runs after existing profile/override/generator/language expansion and effective parameter normalization, before trusted generation. Checking only source YAML is insufficient. |
| Impact and validation record | Effective-rule hash per job, definition/input/renderer identities, rejected fields, affected membership and before/after material differences | Reuses existing fingerprint and dependency evidence; it is not permission to generate, waive warnings, stage or merge. |

The selected contract structure contains header/ownership, named variants, field permissions, caption/language policy, typography, poster composition or overlay transform, identity/naming/routing, dependencies, exception references and adoption/approval history. Use strict JSON Schema validation and canonical JSON data, reusing the project's existing [schema machinery](../bulk/definitions.py) and [canonical hashing](../bulk/common.py). A read-only versioned registry selects the exact category/variant package; legacy YAML remains input to the compatibility adapter, not the authority for protected fields. These are finalized design choices, **not implemented files or an API available today**. Illustrative examples below remain descriptive only.

### Versioning and adoption

D01 selects an integer `schema_version` independent of immutable semantic contract versions (major.minor.patch), with an exact version **and canonical SHA-256**, never floating `latest`. Representation/schema version and behavior/permission version are independent. Use major revisions for changing an existing design or permission boundary, minor revisions for approved additive variants that leave existing rules unchanged, and patch revisions only for non-behavioral metadata corrections. Every revision has a new immutable package hash; version labels never confer approval. Record both package identity and resolved material-rule hashes in provenance.

The registry is maintainer-controlled canonical JSON referencing schema, category/variant, exact package/version/hash and actual approval/adoption records. Reject unknown versions, duplicate IDs, ambiguous inheritance and contributor-supplied trust flags. Maintainer approval is required for material changes and extensions; a metadata-only update cannot silently widen policy. Existing [common.canonical/fingerprint](../bulk/common.py) supplies serialization/integrity foundations, not an approval identity system. Implementation must test schema/version compatibility and registry tamper rejection before any activation.

Initial adoption should map every existing ID to a contract/variant/exception **without editing definitions, reminting IDs, renaming files, substituting fonts or rerendering**. Use the accepted source/asset hashes and fitting evidence. Reject an unexplained mismatch; do not enlarge a rule merely to achieve a desired adoption count. Coverage must include static and generated children, both private intermediates, both overlay sizes and dependency parents. Existing behavior outside the modeled scope remains unchanged; a future enforcement switch requires its own authorization.

Use package hashes for audit and resolved material-rule hashes per job. An added independent variant or metadata revision must not invalidate unchanged artwork decisions merely because the package hash changed. D08 selects an explicit adoption/compatibility attestation linking old validation, preview and owned worker receipt to the equivalent effective job and new rule context. Require exact IDs, mappings, render parameters, caption, inputs/dependencies, candidate bytes and material approval scope to remain equivalent; otherwise mark affected approval stale. Do not rewrite old receipts or inject contract metadata into render fingerprints to force a library rerender. The future sidecar records are validation provenance, not changes to the renderer. Compatibility must be demonstrated and checked, never inferred from a matching filename or byte hash alone.

### What an ordinary submitter can provide

D02 selects an explicit content allowlist, not a general YAML override interface. A submitter may propose display metadata, an enabled content/variant selection and exact artwork/provenance, plus the confirmed D09 exception requests. Requested identity, background or filename is not authoritative until confirmed. No input may select a font, grant its own exemption or choose an official destination. The compatibility adapter validates existing explicit YAML values against their adopted exact designs without editing those definitions.

Maintainers control contract/variant creation, typography, layout, encoding, source treatment, caption-key mappings, field permissions, language/exception scope, identity assignment and public-path approval. A maintainer's role alone does not imply an image merge or bulk design authorization. Definitions can retain explicit historical style fields for compatibility, but their values must equal the adopted rule or the specifically approved exception.

## Architecture rule ownership matrix

These ownership classes differ from Phase 1's evidence labels: **LOCKED** = maintainer-controlled; **SUBMITTER** = allowed content/request, never self-approval; **DERIVED** = calculated from approved rules; **EXCEPTION** = exact approved departure. **UNDECIDED** below is limited to numeric calibration awaiting evidence, not reopened architecture/business policy. D01–D08 defaults are selected for the final architecture proposal; D09 policies are already confirmed. Nothing authorizes implementation or remote writes. Uncalibrated metrics cannot auto-approve; they do not prevent the explicit human exception process once its implementation is authorized and tested.

| Rule | Class | Selected architecture / confirmed policy | Decision |
| --- | --- | --- | --- |
| Contract owner, schema, version and approved hash | LOCKED | Immutable exact references and explicit maintainer approval | D01 |
| Version numbering and adoption authority | LOCKED | Independent integer schema version and immutable major.minor.patch contract version/hash; actual maintainer-bound adoption, no automatic upgrade | D01 |
| Category and named variant definitions | LOCKED | Closed variant set; no arbitrary profile/variant supplied by a submitter | D02 |
| Variant selection for an individual item | SUBMITTER | Select an allowed existing content variant; eligibility constraints remain enforced | D02 |
| Font family, file hash, weight and fallback font | LOCKED | Exact bundled bytes for each variant; no platform font search or unapproved substitution | D02, D03 |
| Default caption size, measurement box and fitting algorithm | LOCKED | Exact per-variant baseline; historical minimum/maximum is evidence, not permission to shrink automatically | D03 |
| Render-time fitted size after an approved fitting rule | DERIVED | Only the approved bounded algorithm, caption/font/renderer context; record exact result | D03 |
| Language-specific typography override | EXCEPTION | Explicit reviewed language/variant/font/geometry binding; historical values retained, no automatic new override | D03, D04 |
| Caption required/conditional/prohibited rule | LOCKED | Per variant; conditional rules resolve deterministically from the chosen content type | D02 |
| Approved caption/order-type selection | SUBMITTER | Choose an enabled type; not an arbitrary literal caption or translation key | D02, D04 |
| Type-to-caption-key and template/suffix mapping | LOCKED | Authoritative approved keys and exact template semantics, including shared/none modes | D04 |
| Rendered caption and capitalization | DERIVED | Resolve pinned resources and apply the contract's exact/upper/lower rule | D04 |
| Casing, language applicability and fallback permission | LOCKED | Per variant/language; no submitter-owned `fallback.reviewer` or automatic English fallback | D04 |
| Language, RTL and authoritative-source boundary | LOCKED | Pin existing registry/applicability and approved caption mappings; no new language/fallback/RTL activation; mandatory source/routing safeguards remain Phase 3 | D04 |
| Logo/asset submission and provenance | SUBMITTER | Valid PNG, genuine transparency by default; intentional opaque/partial-alpha brand backgrounds need the formal exception process; retain original hash/name | D02, D09 |
| Required logo presentations | LOCKED | Confirmed category defaults: WHITE_ONLY, SOURCE_PRESERVING, BOTH_REQUIRED or retained SPECIAL / NOT APPLICABLE; exceptions do not change defaults | D09 |
| Non-default presentation/background request | SUBMITTER | Justification and default-versus-requested preview scope; no contributor-controlled wash toggle or self-approval | D09 |
| Approved individual presentation/background exception | EXCEPTION | Exact identity/source/contract/variant/treatment/preview/scope binding; submitter confirms and maintainer separately approves; invalidate on changed source/material context | D09 |
| Logo resize, anchor, offsets, wash and trim | LOCKED | Explicit per variant; existing white-wash algorithm unchanged; contributor cannot alter category styling | D02, D09 |
| White presentation from colored master | DERIVED | Existing alpha-preserving white-wash, exact version/context and preview; original source remains unchanged | D09 |
| New PNG transparency/integrity gate | LOCKED | Decode/alpha/integrity/quality checks; transparent PNG default; withhold nonconforming backgrounds unless explicitly approved as intentional brand content; no automatic background removal | D09 |
| Seventeen reviewed historical alpha/background assets | LOCKED | Normal accepted artwork: preserve exact bytes/use, without cleanup, alpha-policy warnings, re-review or regeneration; replacement bytes do not inherit acceptance | D09 |
| Separate-white correspondence result | DERIVED | MATCH, REVIEW REQUIRED or MISMATCH from bounded deterministic geometry/mask evidence under an approved comparison policy | D09 |
| Comparison and source-quality numeric thresholds | UNDECIDED | Calibrate before implementation; resolution/anti-alias differences alone are not mismatches or grounds for auto-approval | D09 |
| Complete required variant set | LOCKED | BOTH_REQUIRED additions need both presentations validated and approved, plus the contract's required outputs; no half-complete acceptance | D09 |
| Submitter preview confirmation | SUBMITTER | Explicit approve/reject decision for exact previews and complete variant membership; never publication approval | D09 |
| Final logo/brand approval | LOCKED | Separate maintainer decision over brand identity, transparency, derived whites, consistency, category compliance and all required outputs | D09 |
| Derived logo height and fitted overlay size | DERIVED | Existing approved aspect/rounding/resampling behavior; do not crop/pad or rescale by ink bounds | D02 |
| Caption position, surface and clipping policy | LOCKED | Preserve baseline dimensions/offsets; proposed new fit exceptions require review | D03 |
| New item brand background color proposal | SUBMITTER | Only where the category permits; proposal separate from source logo colors and rendered treatment; maintainer gives final approval | D05, D09 |
| Category-specific background permission | LOCKED | Explicit per-variant opt-in, default disabled; enable proposals for the Playlist brand pilot with final maintainer approval/current color checks; preserve all existing assignments elsewhere | D05, D09 |
| Existing per-item background colors | EXCEPTION | Adopt exact assignments and lineage, including all nine Playlist colors | D05 |
| Era/family palette or derived separator color | DERIVED | Calculated from the approved named design/assignment, not arbitrary content YAML | D02, D05 |
| Gradient, border, effects, white wash and background sampling | LOCKED | Per named variant, not one universal style | D02 |
| Dimensions, encoding, metadata and transform dependencies | LOCKED | Preserve existing JPEG/PNG contracts and renderer identity boundaries | D02 |
| Display name and descriptive content metadata | SUBMITTER | Bounded text, independent of caption, ID and destination | D06 |
| Stable ID assignment, lifecycle and identity mapping | LOCKED | Existing IDs retained; new persistent IDs assigned/confirmed once; no filename-derived reminting | D06 |
| Generated child and overlay variant identities | DERIVED | Resolve persisted identity by semantic family/member or asset/size key; never recalculate from a renamed path | D06 |
| Initial filename proposal | SUBMITTER | Propose exact spelling only when the category allows it; maintainer confirms mapping | D06 |
| Existing local/public filenames and directories | LOCKED | Preserve exact independent mappings, including Action & Adventure | D06 |
| Filename spelling, case, punctuation and Unicode policy | LOCKED | Portable paths and NFC+casefold collisions; preserve literal baseline names; reject ambiguous new names | D06 |
| New-name Unicode normalization behavior | LOCKED | Require NFC for new names and reject non-NFC input with explanation; never normalize or rename accepted literal paths silently | D06 |
| Generated local path and official public mapping | DERIVED | Resolve approved mappings and language boundary; no display/translation-driven rename | D06, D04 |
| Official destination owner/repo and language boundary | LOCKED | Official English only; other languages local or explicit user repo, with Phase 3 enforcement | D04 |
| Shared generated-parent and asset dependency graph | DERIVED | Resolve exact content hashes and dependency closure; validate hidden/unselected parents too | D07 |
| Generator identity, parameters, family bounds and code | LOCKED | Named versioned deterministic generators; no submitter range expansion or executable expressions | D07 |
| Existing Splatter, private Awards and other migration differences | EXCEPTION | ID/variant/context-specific, cited acceptance; no broad catch-all "legacy" exemption | D02, D08 |
| Existing warning/visual/font acceptance | EXCEPTION | Retain exact accepted membership and scope only while bytes/material context remain valid | D08 |
| Definition/profile/language override precedence | LOCKED | Overrides cannot widen permissions or replace protected values after expansion | D07 |
| Effective parameter values, caption and naming resolution | DERIVED | Deterministic approved resolution; compare raw intent and resolved values to prevent fallback/clamping bypass | D07 |
| Category-wide design/permission changes | LOCKED | Explicit contract delta, complete impact assessment and maintainer approval; no implicit authorization from a field edit | D08 |
| Artifact skip/replacement decision | DERIVED | Equal SHA-256 skips; differing bytes remain candidates, including eligible renderer equivalents | D08 |
| Tolerance, warning policy, approval membership and staging | LOCKED | Separate explicit exact policies/receipts; a category contract never approves pixels or remote writes by itself | D08 |
| Technical batch size and PR grouping | DERIVED | Bounded transport planning separate from review groups; one approved publication scope may use multiple technical batches | D08 |

No historical exception can be self-assigned. Numeric calibration remains unapproved until the explicit evidence procedure below is completed; uncertain comparisons return REVIEW REQUIRED. A selected architecture default is not approval of an individual new source, image, exception, publication manifest or implementation change.

## D09 — Logo sources, variants, transparency and approval

### Required presentations, not required upload counts

The category or approved variant owns **WHITE_ONLY**, **SOURCE_PRESERVING**, **BOTH_REQUIRED**, or a retained **SPECIAL / NOT APPLICABLE** design. These describe resulting presentations, not upload counts. SOURCE_PRESERVING retains the original logo treatment whether naturally white, black, monochrome or colored; it does not require adding color or applying white-wash. Earlier COLOR_ONLY/source-preserving wording denotes this same source-preserving behavior, not a separate new requirement. WHITE_ONLY uses the unchanged approved white-wash by default. BOTH_REQUIRED may use one transparent master for original-color and derived-white treatments. SPECIAL must identify the retained design or lack of a logo and cannot bypass approval.

**Confirmed maintainer policy:** Playlist, Franchise, Genre, Seasonal and Universe default to WHITE_ONLY; contributors may request an individually approved SOURCE_PRESERVING exception, never disable wash arbitrarily. Studio is SOURCE_PRESERVING. Applicable Chart, Country, Network and Streaming paired designs are BOTH_REQUIRED. Overlays are SOURCE_PRESERVING across their existing white/color source branches and standard/bigger sizes, independently of poster defaults. All other Phase 1 treatments and accepted exceptions remain unchanged. BOTH_REQUIRED additions need both presentations validated and approved before acceptance; no missing overlay group is invented, and an unrelated complete addition need not wait.

### Category-by-category audit: historical facts and confirmed policy

This is a targeted logo audit, not a rerun of Phase 1. Selectors come from [config.CATEGORIES](../bulk/config.py). Counts below use the byte-verified [complete English job ledger](../bulk/evidence/package-e/full-ledger-index.json), the current linked category YAML/profile and [generator behavior](../bulk/generators.py), with source case resolved only by the explicit [case ledger](../bulk/catalog/asset-case-migrations-v1.json). No definition or image is changed. The 9,957 concrete records are classified by the **actual logo input**, excluding `transparent.png` placeholders and already generated parent/base compositions from normal logo counts. A `white_wash: true` on a blank placeholder is not evidence of a white-logo requirement. A false flag does not prove that source pixels are colored.

In the historical column, **W** means a real logo passed through the current white-wash; **P** means its source colors were preserved; **T** means no visible logo/shared transparent placeholder; **C** means a generated parent or separator base composition. These are counts of outputs/uses, not unique files. Every row totals its accepted concrete category count. A color/white filename counterpart confirms output membership, not geometry or brand equivalence.

| Category and source evidence | Confirmed historical behavior (W / P / T / C) | Confirmed maintainer policy / retained historical treatment |
| --- | --- | --- |
| [Aspect](../bulk/catalog/aspect.yml) | 8 / 0 / 1 / 0; other-aspect is text-only | WHITE_ONLY for ratio logos; NOT APPLICABLE for text-only other |
| [AudioLanguage](../bulk/catalog/audiolanguage.yml) | 0 / 0 / 188 / 0; transparent placeholder throughout | NOT APPLICABLE; language text does not authorize adding a logo |
| [Awards](../bulk/catalog/awards.yml) | 4,847 / 0 / 0 / 0 from 16 award sources; includes two private intermediates | WHITE_ONLY for poster logos; keep award-specific size/geometry and private outputs; overlay treatment remains separately scoped below |
| [Based](../bulk/catalog/based.yml) | 0 / 0 / 4 / 0; text-only | NOT APPLICABLE |
| [Chart](../bulk/catalog/chart.yml) | 0 / 1,182 / 0 / 0; color/white branches, 591 same-filename poster pairs; separate stored white sources | BOTH_REQUIRED for the paired chart design; white result may be derived, not necessarily a second upload |
| [ContentRating](../bulk/catalog/contentrating.yml) | 71 / 0 / 1 / 0; 47 distinct poster logo sources; other is text-only | WHITE_ONLY for existing poster-logo designs; NOT APPLICABLE for other; raw rating overlays are distinct designs |
| [Country](../bulk/catalog/country.yml) | 301 / 301 / 6 / 0; 304 paired poster filenames, including three text-only pairs; white flags derive from shared sources | BOTH_REQUIRED for flag posters; NOT APPLICABLE for the paired text-only cases; no invented white-overlay group |
| [Decade](../bulk/catalog/decade.yml) | 0 / 0 / 16 / 15; literal captions and generated best-of parents | SPECIAL / NOT APPLICABLE: era composition, not a free-standing logo upload |
| [Franchise](../bulk/catalog/franchise.yml) | 103 / 15 / 0 / 0; one poster per item, no paired color/white destinations | WHITE_ONLY default; individual SOURCE_PRESERVING request uses the formal two-stage exception process; existing 15 accepted treatments retained |
| [Genre](../bulk/catalog/genre.yml) | 235 / 39 / 1 / 0; 39 source-preserving uses include two Silent outputs sharing one source | WHITE_ONLY default; individual SOURCE_PRESERVING exception permitted; retain existing treatments, exact red/no-wash Splatter and text-only other |
| [Network](../bulk/catalog/network.yml) | 0 / 564 / 4 / 0; 284 paired poster filenames including two text-only pairs; separate stored white sources | BOTH_REQUIRED for applicable paired logo designs; NOT APPLICABLE for other/kids-other; reviewed historical alpha/background assets are normal accepted artwork |
| [Playlist](../bulk/catalog/playlist.yml) | 9 / 0 / 0 / 0; all nine use existing white-wash | WHITE_ONLY default; individually approved SOURCE_PRESERVING exception permitted after both-treatment previews and two-stage approval; existing nine unchanged |
| [Resolution](../bulk/catalog/resolution.yml) | 13 / 0 / 2 / 0 | WHITE_ONLY for icons; NOT APPLICABLE for text-only other variants |
| [Seasonal](../bulk/catalog/seasonal.yml) | 22 / 1 / 0 / 0; Black History retains source colors | WHITE_ONLY default; individual SOURCE_PRESERVING exception permitted; retain Black History's accepted treatment |
| [Separators](../bulk/catalog/separators.yml) | 1 / 0 / 0 / 748; collectionless uses one washed logo; remaining inputs are approved base compositions | SPECIAL: retain base-template families; WHITE_ONLY for collectionless's logo treatment; a template is not a new contributor logo |
| [Streaming](../bulk/catalog/streaming.yml) | 0 / 256 / 0 / 0; 128 paired poster filenames; separate stored white sources | BOTH_REQUIRED for paired brand/caption designs; optional white upload must correspond to the colored master |
| [Studio](../bulk/catalog/studio.yml) | 0 / 486 / 2 / 0; real logos preserve source colors; true wash flags occur on text-only placeholders | SOURCE_PRESERVING, including naturally white, black, monochrome and colored originals; NOT APPLICABLE for other/animation-other |
| [SubtitleLanguage](../bulk/catalog/subtitlelanguage.yml) | 0 / 0 / 188 / 0 | NOT APPLICABLE; preserve text-only design |
| [Universe](../bulk/catalog/universe.yml) | 19 / 1 / 0 / 0; Monsterverse preserves source colors | WHITE_ONLY default; individual SOURCE_PRESERVING exception permitted; retain Monsterverse's accepted treatment |
| [VideoFormat](../bulk/catalog/videoformat.yml) | 0 / 6 / 0 / 0 | Retained historical SOURCE_PRESERVING treatment, including intrinsically monochrome sources |
| [Overlays](../bulk/catalog/overlays-v1.json) | 18 groups, 2,061 inputs, 4,122 outputs; existing transform preserves input RGB/alpha, with no white-wash step | SOURCE_PRESERVING; retain existing white/color source branches and both output sizes; do not inherit poster white-wash defaults |
| [Year](../bulk/catalog/year.yml) | 0 / 0 / 151 / 150; literal years and generated best-of parents | SPECIAL / NOT APPLICABLE: preserve era typography and parent compositions, not a new logo rule |

The source-preserving Franchise exceptions are the exact existing outputs: 28 Days Weeks Later, Bosch, Bourne, Death in Paradise (2011), Father Brown, Game of Thrones, Hellboy, Inspector Morse, IP Man, John Wick, John Wick2, Power, Reacher, RoboCop and Spartacus. The Genre source-preserving uses are bounded by their exact 39 current definitions/contexts, not every new genre; source/display spellings can differ (Creature Feature uses `Creature Horror.png`, Surreal uses `Surrealism.png`). Together with Black History and Monsterverse, these are intentional non-washed assignments, not evidence that contributors may choose styling. Preserve the accepted source hashes, exact mappings and existing decisions; do not infer new exceptions from a matching brand string.

### Overlay requirements are independent of poster branch counts

Historical evidence is [overlays-v1.json](../bulk/catalog/overlays-v1.json) and [overlays.render](../bulk/overlays.py). **Confirmed maintainer policy is SOURCE_PRESERVING for every existing overlay group.** Retain the existing white/color source branches, trim behavior and standard/bigger sizes. A white branch preserves its approved white-source presentation; it is not permission to run poster white-wash over every source. This supersedes the earlier candidate WHITE_ONLY overlay mappings, including Playlist. No group or existing artwork is recolored, renamed, added or regenerated by this policy record.

| Existing overlay group | Sources × two sizes | Historical treatment | Confirmed overlay policy |
| --- | --- | --- | --- |
| `aspect` | 8 × 2 | Source-preserving, no trim | SOURCE_PRESERVING; retain both sizes |
| `content_rating` | 98 × 2 | Source-preserving, no trim; includes colored rating assets absent from poster-logo scope | SOURCE_PRESERVING; retain rating-source treatments and both sizes |
| `genre` | 272 × 2 | Source-preserving, no trim | SOURCE_PRESERVING; no inherited poster wash |
| `seasonal` | 21 × 2 | Source-preserving, no trim | SOURCE_PRESERVING; no inherited poster wash |
| `studio` | 486 × 2 | Source-preserving, no trim | SOURCE_PRESERVING |
| `video_format` | 6 × 2 | Source-preserving, no trim | SOURCE_PRESERVING |
| `award` | 16 × 2 | Source-preserving, trim | SOURCE_PRESERVING, independently of white-washed award posters |
| `chart`, `chart/white` | 33 × 2 each | Separate source branches, trim | SOURCE_PRESERVING within each retained color/white branch; both sizes |
| `country` | 300 × 2 | One source-preserving group, trim | SOURCE_PRESERVING; no new white-overlay group |
| `franchise` | 118 × 2 | Source-preserving, trim | SOURCE_PRESERVING, independently of poster default or exception |
| `network`, `network/white` | 282 × 2 each | Separate source branches, trim | SOURCE_PRESERVING within each retained color/white branch; both sizes |
| `playlist` | 9 × 2 | Source-preserving, trim | SOURCE_PRESERVING; poster WHITE_ONLY does not force a derived-white overlay input |
| `resolution` | 13 × 2 | Source-preserving, trim | SOURCE_PRESERVING |
| `streaming`, `streaming/white` | 32 × 2 each | Separate source branches, trim | SOURCE_PRESERVING within each retained color/white branch; both sizes |
| `universe` | 20 × 2 | Source-preserving, trim | SOURCE_PRESERVING; no inherited poster wash |

This enumerates all 18 groups. AudioLanguage, Based, Country-white, Decade, Separators, SubtitleLanguage and Year have no corresponding standalone group in the present overlay catalog; absence is not a missing required image. Overlay-only source membership can exceed poster-logo membership. A new contract must list required outputs explicitly rather than fabricate a poster or overlay from every file found in a directory.

Directory names are not proof of pure white pixels. A read-only alpha-masked raw-RGB observation of the 347 sources in the three `white` branches found 203 exactly white at every visible pixel and 144 with some nonwhite visible channel values: Chart 28/33 exact-white, Network 151/282, Streaming 24/32. Nonwhite values include grayscale/anti-alias details and retained color; **this is not a perceptual defect classification, a MATCH test, or a new cleanup queue**. Eight of nine Playlist sources also contain nonwhite visible RGB; their poster presentations are white because the renderer performs white-wash. Keep every accepted historical asset/output unchanged; validate the future resulting presentation rather than trusting a folder name.

### Formal individual exception workflow — confirmed maintainer requirement

Contributors may **propose, never self-approve**, a non-default presentation. For Playlist, Franchise, Genre, Seasonal and Universe, a SOURCE_PRESERVING request is an individual content exception to the WHITE_ONLY default. New intentional opaque or partial-alpha brand backgrounds may also be requested as a transparency exception. If a request departs from both presentation and transparency defaults, approve both departures explicitly; neither implies the other. The category default remains unchanged, and a raw `white_wash: false` or submitter-supplied approval flag grants no authority.

The future workflow must:

1. **Record the request and justification.** Bind the existing/new stable identity, original source PNG hash and exact spelling, category contract/version/variant, default and requested treatment, intentional background if any, and requested use/output scope. Explain why the brand/content needs the departure; a matching filename or another item's exception is insufficient.
2. **Show default-versus-requested previews.** For a white-default presentation request, show the unchanged approved white-wash and SOURCE_PRESERVING results under the same controlled layout/background. For an intentional-background request, show the actual default rendering/validation outcome and the requested intentional treatment side by side. Label a default that fails the transparency requirement as blocked, not as a compliant transparent default. A contributor may supply a separately hash-bound transparent counterpart; never manufacture one by background removal. No previews are generated by this documentation update.
3. **Require explicit submitter confirmation.** Approve or reject the exact comparison previews, selected requested result and complete affected required output set. Changed previews require confirmation again; silence is not consent and confirmation is not publication approval.
4. **Require separate final maintainer approval.** Review justification, brand identity, intentional background/transparency, wash results, consistency, category compliance and exact complete scope. Until approved, the exception cannot be applied. A rejection leaves the category default in force; the contributor may revise the source/request, use the compliant default, or withdraw. No arbitrary wash switch becomes submitter-editable.
5. **Persist and recheck the approval.** Use the exact record below when resolving each effective expanded job. Changed source bytes or material review context invalidate affected approvals and dependent decisions. Unaffected items and existing accepted artwork retain their decisions. A source revision cannot inherit approval from an unchanged filename, and an individual exception does not update the category-wide default or approve a bulk change.

| Exception record group | Required binding |
| --- | --- |
| Identity and source | Exact stable identity, original and any comparison-source SHA-256, exact filename/case, brand/content justification |
| Contract and departure | Category contract/version/hash, effective variant/rule context, unchanged default, selected treatment, presentation/transparency/both exception type and intentional-background description |
| Preview evidence | Default and requested preview hashes, explicit blocked-default status where applicable, transformation/runtime parameters, layout/background and comparison evidence |
| Decision and scope | Explicit submitter confirmation and separate final maintainer decision with provenance; exact approved treatment, identities, output kinds/required variants and use/approval scope |
| Validity | Source/material-context invalidation conditions, dependency links and revision/supersession history; no transfer to a new source or use without matching approval scope |

Record format, storage and role/receipt integration remain implementation-design work. The exception permission and two-stage requirements are confirmed policy. Publication, merge, delete and production-generation authorizations remain separate.

### PNG transparency, integrity and source quality

**Transparent PNG remains the default for new source logos.** Verify PNG format/signature and integrity, then reopen and fully decode within the existing bounded single-frame constraints. Check decoded alpha, including palette transparency and grayscale-plus-alpha; RGBA mode alone proves nothing. The ordinary path requires visible foreground and genuine transparency. If an opaque or partial-alpha background is an intentional part of the brand, allow the formal justified exception request above, with comparison previews, submitter confirmation and separate final maintainer approval. Without that approval, withhold the non-default source and request a compliant transparent PNG. Invalid/corrupt/truncated files, disguised non-PNGs and empty/fully transparent logos remain invalid; an intentional-background exception does not waive PNG integrity or brand/quality review. Never remove backgrounds automatically.

For the default transparent path, alpha below 255 somewhere is necessary but insufficient: one clear pixel in an otherwise opaque rectangle does not demonstrate a clean transparent logo. Report alpha distribution, bounds, dimensions/scale and edge contact; review unwanted matte/checkerboard backgrounds, halos, clipping and readability. Soft edges or glow may legitimately use intermediate alpha and are not automatically exceptions or defects. An intentional brand background is eligible for explicit approval, not automatic rejection or removal. Ambiguous new-source evidence remains REVIEW REQUIRED until resolved through the ordinary or exception path. Numeric geometry/quality thresholds still require calibration; they do not override an exact approved individual background scope.

The prior read-only audit verified **2,061 source PNGs** with no integrity errors: 2,044 have visible content and fully clear pixels, 14 have partial alpha without a zero-alpha pixel, and three are opaque. **The maintainer has now reviewed the identified 17 opaque/partial-alpha assets and confirmed them as normal accepted existing artwork. Preserve them unchanged, without cleanup, warnings, re-review or regeneration.** These historical measurements are reference facts, not active diagnostics or an exception-request queue. This update does not repeat that audit or alter Phase 1. The accepted assets are:

| Existing source family | Exact observed assets | Alpha observation / treatment |
| --- | --- | --- |
| `logos_network` | `DR1.png`, `ORF.png`, `TF1.png` | Three opaque sources; normal accepted existing artwork, unchanged with no cleanup/warning/regeneration |
| `logos_network` | `BET+.png`, `Game Show Network.png`, `TVP1.png` | Three partial-alpha sources; normal accepted existing artwork, unchanged with no cleanup/warning/regeneration |
| `logos_studio` | `TSG Entertainment.png` | Normal accepted existing artwork; preserve source and use unchanged, with no cleanup/warning/regeneration |
| `logos_content_rating` | `usgc.png`, `usnc-17c.png`, `uspg-13c.png`, `uspgc.png`, `usrc.png`, `ustv-14c.png`, `ustv-gc.png`, `ustv-mac.png`, `ustv-pgc.png`, `ustv-yc.png` | Ten normal accepted rating sources; no cleanup/warning/regeneration or change to poster/overlay treatments |

Existing acceptance applies to the approved bytes/use, not arbitrary replacement bytes under the same filename. A changed source or material context follows affected-approval invalidation and the new-source/default-or-exception process. This does not resurrect retired Splatter or waive review for new uses. Text-only placeholders and approved base/generated compositions are not contributor logos; NOT APPLICABLE cannot be self-assigned to bypass intake.

### Existing white-wash and separate color responsibilities

The current [poster renderer](../create_poster.py) loads the original image as RGBA, keeps its alpha channel, replaces RGB with white and restores that same alpha before the existing resize/compositing steps. **Reuse that exact approved transformation; do not change its algorithm, infer a new alpha mask, remove backgrounds or overwrite the source.** Derived white is a separately identified artifact with the original source hash, transform/code/runtime identity and exact parameters. Preview creation is a future authorized workflow, not an action performed by this documentation task.

For a WHITE_ONLY default, retain the qualifying PNG source unchanged and derive white with the existing transformation. A contributor can instead request a SOURCE_PRESERVING content exception, supported by both-treatment previews and the formal two-stage process; until approved, the default remains white-wash. New intentional source backgrounds need their own explicit approval scope if they depart from the transparency default. For BOTH_REQUIRED, one transparent master may supply both presentations and a separate white upload is optional. Both presentations and all required outputs must validate and complete both approval stages before acceptance.

Color-defined internal details can disappear when all RGB becomes white even though alpha is preserved exactly. The preview/brand review must catch that loss of readability or identity; ask for a suitable transparent asset or resolve a specific approved variant rather than changing the wash algorithm, auto-cutting holes or treating an unchanged alpha mask as sufficient approval.

Keep three independent quantities: **original logo RGB**, **required rendered logo treatment**, and **poster background color**. White-wash changes the second, not the saved original or the background. A contributor may propose a new brand background only where the category permits; final approval belongs to the maintainer. Contributors cannot toggle wash, recolor the logo, change group styling, or select a new contrast/effect policy through their background proposal. Existing per-item backgrounds and accepted logo treatments remain unchanged.

Overlays remain SOURCE_PRESERVING, with the existing white/color source branches and standard/bigger sizes. They do not inherit poster white-wash or an individual poster exception automatically. Any explicitly approved white-branch input is preserved as that branch's source presentation; it is not permission to recolor all overlay sources. This document changes neither `overlays.py` nor catalogs, authoritative basenames or public logo trees. Future dependency/approval adapters must honor the exact selected-source and use scope without inventing a new branch or destination.

### Optional separate-white comparison: deterministic, bounded and reviewable

If a contributor supplies colored and white PNGs, validate both under the transparent default or their exact approved intentional-background exceptions, and bind them to the same claimed brand/variant. Compare the white upload with the white-washed master; matching basenames do not establish identity. Prefer lightweight deterministic Pillow processing without large AI dependencies. If an approved background makes the alpha silhouette a filled rectangle, identical masks alone cannot yield a brand MATCH; retain background context and inspect visible branding rather than automatically cutting out the background.

Recommended future comparison steps, not an approved numeric tolerance policy:

1. Retain originals unchanged; operate on analysis copies. Compare meaningful alpha support, visible bounding boxes, aspect/proportions and internal whitespace. Exclude fully transparent RGB noise from comparisons.
2. For correspondence analysis only, align visible bounds by translation and **uniform** scale to a common bounded analysis size. Record original canvas/margins and placement separately so normalization cannot hide a clipping or layout difference. Do not rotate, mirror, stretch axes independently, fill holes or alter actual rendering inputs.
3. Measure soft-alpha differences, overlap/edge displacement at multiple alpha levels, silhouettes, connected visible parts and internal cutouts. Use bounded deterministic mask traversal where needed; small edge components may be anti-alias noise. Compare both structural evidence and the final intended-size presentations. RGB differences between colored and white masters are expected, not geometric mismatch.
4. Report source/preview hashes, normalization/resampling settings, raw metrics and explainable diagnostic overlays in a future authorized preview. Calibrate numeric thresholds with approved matching resolution/anti-alias controls and structural negative controls before allowing automatic MATCH. No such comparison gallery or new artwork is generated in this task.

| Outcome | Evidence and required disposition |
| --- | --- |
| **MATCH** | Corresponding geometry, silhouette, alpha support, proportions, cutouts and branding; exact correspondence or acceptance under an explicitly approved calibrated policy. Still requires submitter confirmation and separate final maintainer approval; never publication approval. |
| **REVIEW REQUIRED** | Resolution/anti-alias/edge differences, uncertain mask behavior, ambiguous source quality or metrics without an approved tolerance. Withhold completion pending an explicit resolution; do not call different dimensions alone a MISMATCH. |
| **MISMATCH** | Significant documented structural difference: missing/added letter or symbol, altered proportions/silhouette, lost internal hole, materially clipped branding or different brand/lockup. Block approval until corrected or resolved as a separately approved intentional variant, with fresh bound evidence; do not waive it via a broad tolerance increase. |

The normalized masks assist review; they do not prove brand identity or acceptable white treatment by themselves. A separate white brand lockup can intentionally differ from its colored counterpart, but must not receive automatic MATCH. The maintainer must explicitly resolve its identity/design exception and complete the revised preview decisions. Existing approved historical pairs are not retrospectively re-reviewed or classified by this proposal.

### Two-stage approval and exact membership

Future workflow states should distinguish source validation, previews pending, submitter accepted/rejected, maintainer pending/approved/rejected and completion. **Stage 1:** the submitter explicitly approves or rejects the reviewed white-wash result and every required variant/preview. No response is not consent; a rejected or incomplete required variant withholds the addition. **Stage 2:** a separate maintainer decision confirms brand identity, genuine transparency, source quality/clipping/backgrounds, white-wash results, visual consistency, category compliance and the complete required output set. Neither a MATCH result nor submitter approval skips Stage 2.

Bind both decisions to original and optional-white SHA-256, exact source spelling/identity, contract/variant version and effective-rule hash, comparison policy/evidence, transformation parameters/code/runtime, per-preview/output hashes, background/layout context, complete required membership and actual reviewer decisions. Any changed source, derived preview or material context invalidates only affected decisions and dependent variants. Preserve unaffected historical decisions. A source edit can change brand/approval context even when a derived-white image's bytes happen to remain identical.

**Submitter approval is never publication approval.** Final logo/design acceptance also does not authorize generation outside the reviewed scope, GitHub uploads, direct master writes, deletion or merge. Publication still requires the separate exact candidate/policy/membership authorization in D08 and the later publication phase. For an applicable paired addition, no color-only half may be accepted as complete while its required white presentation is blocked, or vice versa.

### Logo dependencies, filenames and incremental impact

Represent the future graph as original asset identity/hash → approved source-preserving or derived-white presentation → its exact consumers. Poster consumers follow their default or approved individual exception. Overlay consumers preserve their selected source branch and do not acquire a derived-white dependency merely because a poster is white-washed. Optional separate-white sources and correspondence evidence affect only uses that depend on them. Include transforms, trim/size, contract/exception scope, backgrounds and source mappings. Existing input/parent hashes and [worker invalidation evidence](../bulk/tests/test_package_e.py) are foundations, not an implemented D09 graph.

| Change | Required impact and approval handling |
| --- | --- |
| Original logo bytes | Find every actual consumer, including shared brands, derived whites and both sizes of applicable overlay groups. Revalidate affected sources/previews/decisions; preserve unrelated posters. RGB-only edits may leave a white mask unchanged, but the changed source/brand context still needs review. |
| Optional separate-white bytes | Recompare that pair and invalidate its affected preview/approval context; do not regenerate unrelated color-only outputs solely because an unused white file exists. |
| Source filename/case, same bytes | Preserve stable ID and exact source mapping; inspect all path references, shared consumers and both overlay basenames. Current path-containing fingerprints may change even when pixels do not. Recheck material exception/preview scope; do not invent aliases, remint IDs or assume a cache hit. No automatic public rename. |
| White-wash/resize/trim algorithm or rule | Category/design change requiring explicit versioned impact assessment and approval, not contributor content. The algorithm is unchanged in this task. |
| Poster background proposal | Affect only compositions using that approved assignment and their reviewed context; do not alter the original logo or background-independent overlays. |
| Shared logo used across categories | Evaluate each consumer's own default/approved exception and size mapping. A WHITE_ONLY poster does not recolor a SOURCE_PRESERVING Studio/overlay consumer or overwrite a shared master. |

Preserve source PNGs, exact case, accents and persisted IDs independently of preview/workspace names. Derive the complete affected graph before deciding what needs rendering; reuse valid unaffected outputs/receipts and compare actual hashes for affected outputs. Do not rerender or re-review the full library merely because D09 is documented. An eligible binary-different output still requires publication synchronization; equal remote SHA-256 skips artwork upload but does not manufacture a valid source-context approval.

**D09 business-policy review is complete.** Do not reopen confirmed defaults, the individual SOURCE_PRESERVING/intentional-background exception permissions, normal acceptance of the 17 existing assets, two-stage approval or overlay SOURCE_PRESERVING. Remaining implementation-design work is how to encode and persist those decisions, display blocked-default versus requested evidence, integrate exact context invalidation and calibrate deterministic geometry/quality checks before automation. Individual future exception requests still require their own explicit decisions; permission to request is not approval of any particular asset or treatment.

### Selected approval-record and receipt integration

Reuse [Store](../bulk/state.py) for SQLite transactions, versioned state and event recording, [Reviews](../bulk/review.py) for the immutable-revision/exact-membership/owned-preview/stale-approval pattern, and [canonical/sealed records](../bulk/library_sources.py) for portable evidence. These already exist; contract and two-role exception record types do not. Implement future types as additive sidecars and versioned migrations, initially in an explicitly isolated Phase 2 state root. Do not migrate the current production cache merely to inspect contracts.

The selected record model separates:

| Future record type | Identity, evidence and authority |
| --- | --- |
| Contract approval/adoption | Immutable package/registry/version/hash, exact baseline membership and real maintainer decision; includes compatibility links to retained historical approvals |
| Logo exception request/revision | Stable request and poster/source identities, monotonic revision, justification, exact source/contract/material-context hashes, requested treatment/background departure and complete use scope |
| Preview manifest | Exact default/requested artifacts, worker receipt references, source/transform/renderer context, default validation status, comparison evidence and required variant membership |
| Submitter confirmation | Actual decision and provenance over one exact request revision plus preview-manifest/member hashes; can accept/reject but cannot approve a contract or final exception |
| Maintainer exception decision | Actual authorized decision over that same revision and confirmed previews, exact selected treatment and scope; cannot approve an obsolete or partially confirmed revision |
| Effective-job contract attestation | Resolved rule/exception/adoption identities bound to the actual expanded job and dependencies; separate from render fingerprints and existing worker receipts |

Store immutable canonical payloads by content hash; persist request revisions, role-specific decisions and event references transactionally. Write/verify evidence blobs atomically before committing references so a crash cannot create an approved pointer to missing evidence. Use expected-version comparisons, like existing Reviews, to reject concurrent stale decisions. Reject new bytes under an old evidence hash, missing owned receipts, stale preview membership and mismatched contract/identity/use scope. A new source or material context creates a revision and invalidates the affected decision chain; it does not silently edit old decisions or stale unrelated items.

Integrity seals are not authentication or digital signatures. Reuse the controlled operator's actual decision capture and existing maintainer-allowlist boundary; contributor content cannot assert a trusted role or approval. The current [review module](../bulk/review.py) explicitly provides development-attributed review without authentication, so the new two-role adapter must enforce provenance/authority rather than assume a `reviewer` string proves it. Exact actor verification, transaction failure and restart behavior require implementation tests; no external identity service or new approval platform is selected.

The existing [operator publication receipt](../bulk/operator_publication.py) remains a different kind with its exact candidate/policy/membership and staging authorization. Neither submitter confirmation nor final logo/contract approval can satisfy that gate. Existing owned worker receipts, `review_revisions`, accepted visual decisions and production artifacts are never rewritten. An explicit compatibility attestation can preserve unchanged historical decisions without a repeat gallery; changed bytes or material context still invalidate affected approval.

### Selected pending-exception and preview representation

Use a bounded local preview workflow backed by Package E's workers, artifact/receipt verification, confined workspaces and review evidence patterns. A pending exception is not an eligible production job. The preview adapter must not change an existing blocked preflight status to eligible just to obtain a preview, nor pass source-preview approval to publication.

Keep the request state machine separate from the current Reviews states: **REQUESTED → SOURCE_CHECKED → PREVIEWS_READY → SUBMITTER_CONFIRMED → MAINTAINER_APPROVED**. Rejection, blocking and staleness are explicit terminal/current states with immutable history; revising inputs returns to a new unapproved revision. SOURCE_CHECKED means safe PNG integrity/decoding within limits, not that a default transparency policy has passed or an exception is approved. Do not skip either role decision or complete a BOTH_REQUIRED request with only one accepted presentation.

The preview manifest contains two labeled panels plus complete required member artifacts: default treatment and requested treatment, their exact image/evidence hashes and validation states. An intentional-background request may show an actual default rendering with **default transparency blocked**, beside the requested treatment. It must not label the default compliant, silently cut out the background, or substitute a different asset. If a contributor supplies an alternate transparent source, bind its own hash explicitly. Preserve font/layout/background across a presentation comparison so it does not hide an unrelated design change.

Preview artifacts live in a separate confined local output root and purpose namespace, without official destination mappings. Reuse verified worker receipts where a real preview is rendered and verify source/transform/context again before each decision. The existing `Reviews.attach` and `_approvable` guards are evidence to preserve, not APIs that already support every blocked/default or two-role case. The future adapter must link preview-only evidence without marking a blocked/private record as an approved poster. Corrupt, empty, disguised or unsafe inputs remain blocked even for previews; normal accepted historical assets do not enter a new warning or request queue.

This representation is finalized architecture. Whether its future UI/CLI and receipt wiring satisfy isolation, conflict/restart handling and complete membership is an implementation-test gate. No previews are created now.

### Selected deterministic metrics and evidence-based calibration procedure

Use Pillow and bounded deterministic mask/geometry analysis. Record source hashes, original dimensions/canvas/margins, alpha distribution/support, visible bounds and aspect ratio; compare translation/uniform-scale-aligned analysis copies while preserving original geometry evidence. Selected measurements are soft-alpha absolute difference, overlap at multiple alpha levels, normalized boundary displacement, component/cutout correspondence, and expected-size readability/branding evidence. No model dependency, rotation/mirroring, anisotropic fitting, mask repair or background removal is selected. Approved intentional backgrounds remain in context; identical full-rectangle masks cannot alone establish a brand MATCH.

| Metric | Selected deterministic definition | Testing/calibration gate |
| --- | --- | --- |
| Soft-alpha difference | On the common analysis grid, retain `sum(abs(A-B))` and its coverage/pixel normalization separately; use decoded alpha, ignoring RGB where alpha is zero | Pin decoding/resampling/runtime, analysis size and aggregation; do not equate a small number with approval until calibrated |
| Soft overlap and alpha-level overlap | Report `sum(min(A,B)) / sum(max(A,B))` plus intersection/union of support at policy-selected alpha levels. Empty/empty is invalid or inapplicable, never an automatic MATCH | Select alpha levels and acceptance thresholds from the corpus; record numerator/denominator so results are reproducible |
| Geometry/boundary | Retain original and visible aspect ratios/margins before alignment; measure directed edge distances in both directions, reporting mean and worst displacement relative to visible scale | Version the grid/distance/traversal rules; verify thin strokes, padding and resolution changes on held-out samples before choosing a decision boundary |
| Components/cutouts | Deterministic bounded connected-component analysis with eight-neighbor foreground and four-neighbor background; retain component/hole measures at the policy's alpha levels without editing masks | AA fragments and full-background cases are diagnostic, not automatic brand judgments; structural controls and final preview review must catch lost holes/symbols |

Metric definitions are selected; decision thresholds, analysis resolution and demonstrated numerical/resource stability remain evidence to obtain. Keep raw measures and any normalization settings with the policy version so later code cannot silently change their meaning.

**No new numeric thresholds or analysis-canvas size are adopted in this proposal.** Thresholds from poster JPEG visual-equivalence or translated typography are not automatically valid for logo correspondence. Until a calibrated policy is approved, metrics are descriptive: uncertain cases are REVIEW REQUIRED, significant demonstrated structural differences remain MISMATCH, and exact mask agreement does not waive brand identity/quality review. D09's two human decisions and required variants still apply.

Future calibration, only after explicit authorization for the isolated samples/previews, must:

1. **Seal the corpus and scope.** Enumerate exact positive pairs covering the same brand at different resolutions, edge anti-aliasing, thin details, holes, multiple parts and padding. Include accepted intentional backgrounds and naturally white/black/colored sources. Use separately authorized negative controls for removed/added letters or symbols, lost holes, stretching, clipping, wrong branding and deliberately noncorresponding lockups. Previously accepted art is evidence, not an invitation to regenerate or re-review it.
2. **Label before tuning.** Capture maintainer reference judgments and ambiguity reasons independently of candidate metric scores. Split by source/brand family into calibration and held-out sets so resized versions of one logo cannot leak into both. Record complete membership and provenance rather than choosing only easy pairs.
3. **Measure reproducibly.** Run candidate bounded analysis settings with pinned Python/Pillow and source/transform identities. Export raw metric distributions, repeatability and resource observations, plus worst/near-boundary examples. Different dimensions/anti-aliasing alone must not become automatic MISMATCH. Choose analysis resolution/alpha levels from measured stability and detail preservation, not arbitrary constants.
4. **Evaluate a candidate policy.** Freeze exact thresholds/settings/version/hash, then evaluate the held-out families without retuning. Report missed structural negatives, false rejection/review of valid positives and every unresolved case. If automatic MATCH cannot be supported conservatively, keep that scope manual REVIEW REQUIRED; do not relax criteria merely to reduce review volume.
5. **Require policy approval and negative tests.** A maintainer must explicitly approve the exact calibrated policy and intended scope before automation. Any significant structural negative incorrectly labeled MATCH blocks acceptance. Preserve intentional exceptions as exact reviewed scope rather than raising global tolerances. A policy change requires new evidence/versioning; no prior decision silently transfers to a different metric context.

The calibration artifact must bind corpus/train-held-out membership, labels, raw measurements, runtime, candidate-policy hash, results, representative evidence and actual approval. Held-out results, repeatability bounds and measured resource limits are testing outputs, not numbers invented here. The 17 normal accepted assets remain unchanged without cleanup/warnings/regeneration throughout.

## Playlist: first concrete contract example

### Preserve all nine existing items

Evidence: [playlist.yml](../bulk/catalog/playlist.yml), [nine exact identities and source hashes](CATEGORY_RULES_MATRIX.md#playlist-exact-identity-and-asset-inventory), and the [accepted Playlist deep dive](PHASE1_DISCOVERY.md#playlist-all-nine-definitions-and-source-assets). The following table is an adoption example, not a replacement catalog. Each item retains its existing stable ID, display/local name, PNG hash and public destination.

| Existing brand / source PNG | Base color to preserve | Adoption treatment |
| --- | --- | --- |
| Arrowverse / `Arrowverse.png` | `#2B8F40` | Existing exact content assignment |
| Dragon Ball / `DragonBall.png` | `#E39D30` | Source and display spellings deliberately differ |
| Marvel Cinematic Universe / `Marvel Cinematic Universe.png` | `#AD2B2B` | Preserve original source dimensions/internal whitespace |
| Star Trek / `Star Trek.png` | `#0193DD` | Existing exact content assignment |
| Pokémon / `Pokémon.png` | `#FECA06` | Preserve accented spelling and source identity |
| DC Animated Universe / `dca.png` | `#2832C4` | No automatic rename from display name |
| X-Men / `X-men.png` | `#636363` | Preserve exact source capitalization |
| Star Wars The Clone Wars / `Star Wars The Clone Wars.png` | `#ED1C24` | Existing exact content assignment |
| Star Wars / `Star Wars.png` | `#F8C60A` | Existing exact content assignment |

### Proposed locked Timeline Order variant

| Design characteristic | Exact baseline to adopt | Ownership |
| --- | --- | --- |
| Caption | Required, `key_names.TIMELINE_ORDER`, uppercase; English becomes `TIMELINE ORDER` | Key/case rule LOCKED; resolved value DERIVED |
| Font | `fonts/BebasNeue-Regular.ttf`; Bebas Neue Regular, weight 400; SHA-256 `08e4623805102d819f58601e46e345648846075e363b2ceb23313c2d1c83ec73` | LOCKED |
| Size | 154; preserve each captured measurement binding to exact text/font/size | LOCKED |
| Fitting evidence | 1600 × 1000 measurement box, historical min 100 / max 154, separately bound evidence for each existing definition | EXCEPTION / existing evidence; no runtime permission to choose any size from 100–154 |
| Caption surface and placement | Actual caption raster 1900 × 1000; centered horizontally, vertical center +450 | LOCKED |
| Logo placement | Requested width 1600 preserving aspect ratio; centered horizontally, vertical center −200 | LOCKED; resulting height DERIVED |
| Required poster logo presentation | WHITE_ONLY default; an individual SOURCE_PRESERVING content exception may be requested | Confirmed D09 default; exception needs both-treatment previews and two-stage approval |
| Source treatment | Preserve original PNG bytes/name/alpha/internal whitespace; unchanged existing wash by default; apply SOURCE_PRESERVING only for an exact approved individual exception; no background removal/cropping | Default LOCKED; approved departure EXCEPTION; source RGB alone grants no wash toggle |
| Required source/preview approval | Transparent PNG default, intentional-brand-background exception permitted; submitter confirms exact default-versus-requested evidence; separate final maintainer approval binds treatment/source/scope | Confirmed two-stage requirement; neither stage permits publication |
| Overlay treatment | SOURCE_PRESERVING for the selected overlay source; retain standard/bigger and exact basename | Confirmed D09 policy, independent of poster white default or exception |
| Background / effects | Per-item colors above; gradient 1; white font; border false; no average/dominant sampling | Colors EXCEPTION for adopted items; effects LOCKED |
| Output | 2000 × 3000 RGB JPEG, quality 100, subsampling 0 | LOCKED |
| Names and mapping | Existing `Brand (Timeline Order)` display/local stem; local `defaults-en/playlist/<stem>.jpg`; public `playlist/<stem>.jpg` | Adopted exact mapping LOCKED; path resolution DERIVED |

The 1600 × 1000 captured measurement and 1900 × 1000 caption surface are different constraints. Do not reinterpret the recorded minimum/maximum as permission to autoshrink the current English Timeline Order design. Future captions/languages must satisfy an explicitly approved fitting rule or exact reviewed typography exception, not silently replace size 154. Preserve existing reviewed warnings/decisions only within their exact scope.

### Illustrative content-to-contract record

This is descriptive notation only, **not a new YAML definition or implemented schema**:

```text
trusted category contract: Playlist / proposed initial adopted revision / exact approved hash
named design: timeline-order-existing
identity: playlist.playlist-arrowverse-timeline-order.09b7e4b8  (retained)
display content: Arrowverse (Timeline Order)
order-type selection: timeline-order  -> key_names.TIMELINE_ORDER
source content: logos_playlist/Arrowverse.png + its accepted source SHA-256
background assignment: existing #2B8F40 + accepted assignment provenance
local/public mapping: retained exact strings, independent of caption resolution
effective design: locked font/hash/154/offsets/width/effects/encoding above
result: content fields resolve into a definition that must match the adopted rules
```

For a **new** Playlist item, the submitter provides brand/display content, original PNG/provenance, an enabled order type and proposed background/name content where permitted. Transparent PNG is the default source requirement; an intentional opaque/partial-alpha brand background may be proposed through the formal exception process. The ordinary poster path retains the original and derives white using the unchanged approved wash. Layout, font/size/fitting, offsets, effects and exact naming boundaries are unchanged.

**Content-specific SOURCE_PRESERVING example:** a contributor explains why the original colored/monochrome treatment conveys this brand better. The future workflow shows both the default white-washed and requested source-preserving poster previews with the same font/layout/background. The contributor explicitly confirms the exact requested result and comparison evidence. The maintainer then separately approves or rejects the individual treatment, brand/source, any intentional background, exact identity/contract/variant, preview hashes and output/use scope. Persist the exception; changing source bytes or material context invalidates affected approval. Playlist's default stays WHITE_ONLY for every item without that exact approved exception. A contributor cannot implement the request by setting `white_wash: false` themselves.

Playlist overlays remain SOURCE_PRESERVING for their selected source, regardless of the poster's default or exception; preserve standard/bigger sizes and original basenames. Do not force the derived white poster input into overlay generation. Existing nine sources/posters/overlays and accepted decisions remain unchanged. No new exception can alter category font, fit box, offsets, border, resize mode, repository routing or unrelated settings. Submitter confirmation and maintainer logo/design approval are not publication approval; separate exact candidate/staging authorization remains required.

### Release Order and Watch Order extensions

The accepted audit found `key_names.TIMELINE_ORDER` present and the particular keys `key_names.RELEASE_ORDER` / `key_names.WATCH_ORDER` absent from the pinned English catalog. That does not prove no other suitable authoritative key could exist; a maintainer must choose and verify the exact mapping. Do not create speculative keys or English literal fallbacks in this proposal.

Recommended extension process, for future authorization:

1. Maintainer defines a new semantic order type and verifies an existing appropriate authoritative key, or separately authorizes a Weblate contribution. A contract extension cannot manufacture a translation value.
2. Review the type's exact caption, casing/template behavior, fitting at the preserved design, and language applicability. If it cannot fit at 154 under the existing layout, withhold it until a narrowly scoped typography variant/exception is approved. Do not weaken the Timeline Order variant or guess a new size.
3. Approve the new type/variant in a versioned package with its measured scope. It inherits Playlist's WHITE_ONLY poster default, formal individual SOURCE_PRESERVING exception process, transparent-source default with intentional-background requests, two-stage approval, and independent SOURCE_PRESERVING overlays. Locked geometry/effects remain unavailable to submitters. Existing nine items remain unchanged; no automatic rebinding, renaming or regeneration follows.
4. Confirm independent IDs for new poster instances and explicit destination names, such as an approved order suffix; an order-type display label or translated caption cannot rename existing files. A single brand may have several distinct order-type posters without sharing one ID accidentally.
5. Once separately authorized in the appropriate future phases, use translation preflight, individual candidate review and approved publication tooling. This proposal adds no type, key, poster, mapping or artifact.

## Other category contract examples

These examples explain how the **same structure** can represent different rules. They do not prescribe identical typography, mandatory translated captions or logo treatment across categories. Their source assignments are in the accepted [matrix](CATEGORY_RULES_MATRIX.md).

| Category | Proposed named designs and content boundary | Locked / derived behavior and exact exceptions |
| --- | --- | --- |
| Year | Era-specific year styles; literal-year and best-of variants. Approved year/member is content, not font selection. | Each era pins its own font/hash/size and effects. Best-of derives from exact generated parents. Retain the 2020s Plus Jakarta Sans Bold at 409; do not copy Playlist's Bebas Neue or font-size bounds. Existing year ranges remain explicit and bounded. |
| Decade | Era styles, literal decade, best-of and translated other. | Same contract structure, independently specified fonts and fitting by era/variant. Preserve 11 Year/Decade Jakarta outputs collectively and exact dependency mappings; no universal era font. |
| Genre | Translated label variants, logo treatments and special other cases. Submitter proposes an approved genre key/artwork/content assignment. | Typography/fit and wash depend on named design. Splatter remains the exact red `#990000`, `white_wash: false` exception; its retired green duplicate stays invalid. Preserve Action & adventure's independent public spelling. |
| Awards | Award-branded base, year series, best/winner/nomination and special award branches. | Pin award geometry and applicable caption mode (none/shared/translation). Generator bounds and per-year fitting evidence are protected. Two private intermediate IDs remain non-public, even if a submitter changes output metadata. |
| Network | Color and white logo designs; captionless brand, translated other and kids-other variants. | Logo widths/wash vary by approved brand/design rather than a common width for all. Require captions only for the appropriate named variants. Preserve literal `Tokyo MX.png` in both overlay sizes. |
| Studio | SOURCE_PRESERVING brand logos, naturally white/black/monochrome/colored; captionless normal logos and text-only other/animation-other cases. | Preserve exact source treatments and mappings, including `A.C.G.T..jpg`; no forced white-wash or punctuation cleanup. |
| Separators | Named-color families, approved historical source templates and the root collectionless output. | Derive approved family members and colors from bounded design assignments. Preserve source templates, no-gradient variant and `collectionless.jpg`; not every member has the same gradient/width/caption behavior. |
| Overlays | Confirmed SOURCE_PRESERVING typed transforms: retain trim/no-trim, existing color/white source branches and standard/bigger sizes. | **No composed caption/font or inherited poster white-wash**. Lock source basename, sRGB/RGBA PNG compression 9, Lanczos, approved trim and boxes 285 × 85 / 440 × 100 with existing rounding. Preserve all 18 groups, 21 case corrections and intrinsic source lettering/colors. |

Aspect, AudioLanguage, Based, Chart, ContentRating, Country, Franchise, Resolution, Seasonal, Streaming, SubtitleLanguage, Universe and VideoFormat also require explicit coverage from the matrix before any broad enforcement activation. For example AudioLanguage/SubtitleLanguage and Based use the shared transparent placeholder and text, whereas Franchise/Universe/VideoFormat are captionless. An implementation limited to the Playlist example must not claim all-category enforcement or silently assign one generic rule to the remaining categories.

An exception should bind the exact logical ID(s), category/variant, affected field/value or diagnostic, source/renderer/measurement context, actual maintainer approval, and invalidation conditions. Avoid exceptions matching arbitrary filenames, all historical records, all warnings or every globally approved font. A negative or changed context must fail closed. Retaining an existing decision does not mean a new candidate can reuse it.

## Stable identity and exact naming

D06 retains every adopted ID literally. For future new records, select lowercase category namespace plus a UUID hex token assigned once by the maintainer-controlled registry, within the current safe ID grammar; persist it before expansion and never allocate randomly during rendering. Generated members resolve through a persisted family/semantic-member mapping. Display/caption/source/output/contract-version changes cannot remint IDs. Existing IDs need no format conversion, and actual rename/delete execution remains Phase 4.

Generated members need a persisted mapping keyed by immutable family identity plus a stable semantic member key (for example year value and approved design variant), not its current filename. Existing generated child IDs are frozen into that mapping; do not "fix" them by rewriting all existing IDs. Overlay identity similarly needs an asset identity plus size/design variant, with current IDs adopted unchanged. Reject duplicate semantic assignments and attempts to bind one ID to unrelated objects. General transactional rename/delete, aliases and tombstones are Phase 4 work, not a side effect of Phase 2 contract adoption.

Keep six independent properties: persistent ID, display name, rendered caption, source asset path, generated local path and published destination. New filenames may be proposed under an allowed content rule but become approved literal mappings; rendering should resolve them, not infer a rename from display or translation changes. Use existing portable-path and NFC+casefold collision checks across the **complete expanded namespace**, including case-sensitive environments, generated members, dependencies and both overlay sizes. A duplicate exact path is also a conflict. Source reuse by several posters is legitimate; an output collision is not.

D06 selects NFC validation with explicit rejection of non-NFC **new** names while preserving every adopted literal spelling. No silent accent removal, title-casing, punctuation cleanup or normalization-driven remote move. Keep `Pokémon`, spaces, `X-men.png`, `dca.png`, `DragonBall.png`, `A.C.G.T..jpg` and the separate Action & Adventure public mapping. Exact directory spelling and portability remain checked. URL encoding belongs to transport. Case-only changes require an explicit identity/mapping decision; an equivalent filesystem lookup is not a rename authorization.

## Effective-definition validation: prevent override bypass

The future validator must operate on the job that would actually render, with authoritative provenance, not only the original YAML or an untrusted `validated: true` marker. Existing reusable points are [Definition/load_definitions](../bulk/definitions.py), [Planner.expand/plan/validate_manifest](../bulk/planner.py), [preflight.effective_language](../bulk/preflight.py), [generation](../bulk/generation.py) and the separate overlay planners. This section proposes their future integration; none is changed now.

Recommended sequence:

1. **Establish trusted inputs.** Resolve the approved package/version/hash and exact category/variant/identity mappings. Reject missing/unapproved packages, caller-supplied approval flags and invalid exception scope. Validate the raw content field allowlist and author role before composition.
2. **Expand deterministically.** Apply supported profiles, explicit language overrides and registered generators; materialize all children and required parent dependencies. Include compiler/generator code identities, source assignments and scope bounds. Resolve the permitted variant and caption mode for every job, not just its family parent.
3. **Resolve effective values.** Apply exact assets, approved caption/template/case/language behavior, parameters and output mappings. Compare both raw intent and normalized effective values with the contract: a forbidden `font_size` or raw legacy offset cannot be hidden by existing fallback/clamping behavior. Grandfather an exact legacy representation only through its adopted context, never as a general escape hatch.
4. **Validate every materialized result.** Check protected fields, submitter bounds, caption-required/none rules, per-variant font/hash/weight, geometry, fitting evidence, effects, output type, exact case/Unicode mappings, language destination boundary and exact exception applicability. Validate generated children and hidden parents even when not directly selected. Enforce namespace collisions at the complete affected namespace, not only a submitted YAML fragment.
5. **Bind a non-mutable result.** Record the selected package plus per-job material-rule hash, effective definition, caption/translation traces, asset/dependency hashes, renderer identity and diagnostics. Unknown or conflicting classifications, unknown fields and out-of-scope overrides fail closed. A warning is not automatically accepted because the contract validates.
6. **Recheck at trust transitions.** Future generation/review/publication adapters must verify this binding against the actual worker payload, current inputs and candidate context. Do not allow post-validation mutation, directly supplied manifests, custom overlay definitions or a different entrypoint to skip the contract gate. A standalone composer remains a drawing API, but its output is not eligible for approved publication merely because it exists on disk.

Language override and generator code cannot grant itself more authority than the parent category contract. An allowed per-language typography change requires an exact reviewed override/exception; a user-supplied override of a locked font remains invalid even when that font is globally approved. Validate after each relevant materialization boundary and finally against the serialized job; neither profile defaults nor downstream effective normalization can silently repair and accept a prohibited submission.

Phase 2 may define these interfaces and implement its approved rule checks only after separate authorization. Mandatory live authoritative translation gates, user-repository routing and RTL expansion remain Phase 3; general lifecycle transactions remain Phase 4; changing actual publication integration remains Phase 5. Documenting their required interfaces here does not authorize implementing those phases early.

## Category-wide change, impact and review

A change is category-wide in authority when it modifies a protected design rule or permission boundary, even if it affects only a named subset of that category. Examples include changing Playlist's font/offsets, expanding a fallback policy, switching a Network logo treatment, altering a separator family, changing an era style or trimming an overlay group. A permission relaxation can be material even if current poster bytes would not change. Contract metadata that changes neither behavior nor authority still needs immutable provenance but should not imply new artifact rendering.

Recommend a **read-only impact assessment first**: old/new contract hashes and rule delta; complete affected categories/variants/IDs/languages; generated dependency closure; source/asset changes; exact local/public mappings; existing approval scope; expected unchanged/changed/blocked/unknown jobs; and the warning/exception scope needed. Missing evidence is reported as unknown or blocked, not zero impact. Distinguish predicted fingerprint impact from actual rendered-byte differences; never claim a new output hash from planning alone.

An explicit maintainer design decision must approve the exact package/delta and impact membership before adopting a category-wide rule change. That is not approval of unseen candidate images. Later, separately authorized generation can reuse valid unchanged outputs and render the affected set. Apply the already approved visual policy where valid; otherwise collect appropriate font/layout/individual review. **Only equal candidate/published SHA-256 skips.** Eligible `renderer_equivalent` files with different bytes must enter the exact upload manifest. Unapproved tolerances and changed exception scope block automatic acceptance.

Before staging, bind the actual candidate hashes, policy and complete membership to the explicit publication approval. Keep visual populations, technical resumable Git batches and PR grouping separate. Verify actual remote image SHA-256 and the whole remote tree, including paths outside the approved change. No design approval, artifact approval or draft-stage approval permits automatic merging, direct master writes or deleting omitted definitions. Existing [operator publication](../bulk/operator_publication.py) and [transport](../bulk/library_stage.py) supply foundations, not automatic permission for new contract operations.

## Finalized D01–D09 architecture and testing status

The maintainer has directed use of the approved architecture. The selected defaults below are no longer open architecture questions. **Finalized architecture is not tested implementation**, and it grants no code, image generation, activation or publication permission. D09 business decisions remain settled.

| Decision | Selected architecture | Evidence still required from future implementation |
| --- | --- | --- |
| D01 — Ownership/version/adoption | Maintainer-controlled strict JSON Schema/canonical JSON contracts and registry; independent schema and semantic version; exact hash pinning; real decision provenance and explicit adoption | Unknown-field/version/hash rejection, immutable history, transaction/crash/concurrency tests, no live-state migration during audit |
| D02 — Variant and field boundary | Exact baseline designs, closed named variants, allowlisted submitter content; no arbitrary inheritance or protected YAML overrides | Coverage and negative field-permission tests, preserving intentional per-category differences |
| D03 — Typography | Existing exact font/hash/weight and per-variant captured size/fitting; Playlist English remains 154. Historical 100–154 bounds do not authorize autoshrink. New caption/language fit needs explicit measured review | Nine-item equivalence and font/size/text/measurement tamper rejection; no new font or fit-policy activation |
| D04 — Captions/languages/destinations | Exact approved caption/type/template/case mappings; preserve pinned registry/applicability/fallback evidence. New keys, languages, aliases, fallback or RTL are not enabled. Official English boundary retained; mandatory authoritative gates/routing remain Phase 3 | Missing/key/template/applicability/override cases; no changed translation pipeline or unintended multilingual official destination |
| D05 — Colors/content approval | Preserve every accepted assignment; distinguish original logo RGB, treatment and background. Per-variant background proposal opt-in defaults off; Playlist brand pilot permits proposals with final maintainer approval and existing color checks | No source RGB/wash change from background input; proposals cannot approve themselves or change locked palettes; adopted assignments remain exact |
| D06 — Identity/names | Existing IDs and six independent name/text/path properties frozen. New IDs assigned once as category namespace plus UUID hex; persisted semantic-member lookup; new names require NFC; literal historic case/punctuation preserved | Stable IDs across metadata/name changes, exact/casefold/NFC collision rejection, no automatic mapping rename or generated-ID reminting |
| D07 — Effective/dependency validation | Validate raw content intent and final expanded/normalized jobs, all profiles/languages/generator children/parents and typed overlays. Sidecar attestation binds actual job/context; fail closed at trusted boundaries | Bypass, forged/stale attestation, clamping, parent/child, collision and direct-overlay-plan tests; isolated audit mode remains the default |
| D08 — Review/reuse/activation | Reuse Store/Reviews/owned receipt primitives with typed immutable sidecars and exact compatibility attestations. Preserve unchanged approvals/receipts. Category impact, artifact review, staging and merge decisions stay separate | Selective invalidation and cross-receipt rejection; unchanged existing evidence remains valid; activation requires exact commit/registry/adoption/regression scope plus separate maintainer authorization |
| D09 — Logo policy and exceptions | Confirmed white defaults plus individual SOURCE_PRESERVING exceptions; Studio/Overlays SOURCE_PRESERVING; applicable paired designs BOTH_REQUIRED; intentional-background exception workflow; 17 existing assets normal accepted with no cleanup/warnings/regeneration | Two-role request/preview/decision state tests, exact exception invalidation and complete variants; deterministic metrics descriptive until the sealed calibration procedure supports and approves automation |

Record integration and pending-preview representation are selected in the D09 sections above. Field-level serialization, database migrations, CLI ergonomics, measured resource limits and numerical calibration will be validated in implementation; they are not reasons to reopen settled policies. A narrower first implementation must declare its exact category/entrypoint coverage rather than imply the whole library is enforced.

## Concrete implementation milestones — not authorized to start

Use **separate implementation branches and small PRs** from the reviewed source baseline selected at authorization, never add code to PR #14 or the merged PR #13. Recheck source/artwork heads before starting; future changes must not be silently folded into adoption. Each milestone is independently reviewable and must meet its gate before dependent work. The documentation PR and this plan do not authorize any milestone.

Tentative future locations are `create_defaults/bulk/contracts/` for contract support/data, the existing `bulk/schemas/` for strict schema definitions and `bulk/tests/` for focused tests. These are planning paths only: no such files are created here. The existing `create_defaults/phase2/` infrastructure is not renamed or replaced by this lifecycle project.

| Milestone | Deliverable and order | Concrete acceptance gate | Preservation boundary |
| --- | --- | --- | --- |
| **M1 — Versioned schema and registry** | Strict contract/registry/exception/adoption record schemas and read-only loader; canonical hash/version selection; typed Store sidecar/event interfaces in isolated test state | Reject unknown fields/versions, tampered hashes, duplicate identities, cycles, floating versions and fabricated approval. Verify immutable revision/export round-trip and rollback of failed transactions. No production adapter invokes enforcement by default | No renderer/YAML/catalog/font/assets changes, no current cache migration and no image generation |
| **M2 — Read-only adoption** (M1) | Sidecar mapping/report from accepted definitions, generated members and Package E evidence; exact compatibility attestations, no rewritten definitions or old receipts | Cover 4,372 declared records/102 families and all **9,957 unique poster outputs + 4,122 overlays = 14,079 outputs**. Preserve 9,955 English public plus 4,122 overlay destinations (**14,077 public**) and two private outputs. No unexplained ID/path/parameter/caption/input/dependency/approval changes; 17 assets normal with no new warnings | Plan/load/hash existing evidence only; no raster generation, uploads or reassignment of names; proof of zero non-document baseline changes |
| **M3 — Playlist contract and negative tests** (M2) | First exact nine-item contract, content allowlist, adopted IDs/names/assets/colors and formal source-preserving exception resolution | All nine expanded designs match approved font/hash/154, measurements, offsets, width, caption, effects and paths. Reject font substitution even from the global whitelist, missing/changed caption, stale fit, locked-field override, raw clamp/fallback bypass, arbitrary wash toggle, forged exception and self-approval | Do not edit nine definitions, create new order types/keys, remint IDs or run a new gallery. SOURCE_PRESERVING overlays remain independent |
| **M4 — Logo/transparency/variant validation** (M3) | New-source PNG gate, optional-white correspondence diagnostics, typed requests and two-stage decision/preview manifests; calibration harness with automation off | Reject invalid PNG; hold unapproved intentional background but accept exact approved scope. Prove submitter cannot replace maintainer/staging authority, all required variants bind the same current revision, source/context edits invalidate affected decisions, and known 17 assets stay normal. Metrics cannot auto-MATCH until corpus/held-out/policy gates pass | Test isolated, explicitly authorized fixtures only; no background removal or white-wash change. Any future sample/preview production needs its stated authorization, with no production art generated |
| **M5 — Expanded-definition/dependency validation** (M3–M4) | Opt-in audit integration around existing loader/planner/preflight/generation boundaries and overlay planners; attestation tied to actual serialized job | Reject bypass through profile/language/generator child, hidden parent, custom overlay/direct manifest or post-validation mutation. Select exact affected graph; invalidation is limited to consumers. No metadata-only change forces rerender or global review staleness; compatibility proof is explicit. Whole output namespace checked | Keep audit default; existing entrypoint behavior and production publication logic unchanged pending activation/later phase authorization |
| **M6 — Remaining contracts and exceptions** (M2, M5) | Data-focused small category cohorts below; exact era/brand/color/captionless/generated/exception mappings | Every category/variant/entrypoint reports coverage, no unknown catch-all. Preserve intentional differences, historical source/visual decisions and exact exception scopes. All 22 selectors and 18 overlay groups covered before any full-library enforcement claim | New contract sidecars only for current membership; no new posters, language expansion, year extension, deletion or mass normalization |
| **M7 — Regression and activation gates** (M1–M6) | Consolidated evidence at exact code/data hashes, audit-versus-baseline reports, review compatibility, recovery/rollback checks and scoped activation proposal | Focused tests plus existing Windows/Linux CI green; zero unexplained effective-job/public-mapping/accepted-evidence differences; negative controls and authority boundaries pass. Any uncalibrated comparison scope remains manual. No new cleanup/warning/render demand for historical assets | No automatic activation or COMPLETE status. Maintainer must separately approve exact implementation/adoption scope, any calibration policy, activation and final acceptance; generation/publication remain separately authorized |

M1–M3 can be implemented and reviewed without a calibrated automatic logo classifier once implementation is explicitly authorized. M4 can retain manual REVIEW REQUIRED for uncertain scope; missing calibration blocks automation, not schema/adoption work. Production-image experiments are not a prerequisite for schema design or read-only adoption.

### M6 review-sized category cohorts

Each cohort may be split further by contract/variant if needed; it must not become one bulk design-change PR. Every data addition cites the accepted matrix and measured adoption report.

| Cohort | Categories | Specific acceptance evidence |
| --- | --- | --- |
| M6a — Era typography/dependencies | Year, Decade | Exact era fonts/sizes, eleven Jakarta outputs, bounded ranges and generated-parent relationships; no automatic current-year expansion |
| M6b — White defaults/individual exceptions | Franchise, Genre, Seasonal, Universe | Existing source-preserving uses, exact red Splatter/retired duplicate boundary, Black History/Monsterverse and all stable mappings preserved; no contributor-controlled wash override |
| M6c — Paired brands/source-preserving Studio | Chart, Country, Network, Streaming, Studio | Complete applicable pairs, exact source branches, text-only cases and source-preserving Studio; no new white-overlay group, filename cleanup or pure-white requirement imposed on accepted sources |
| M6d — Text/icon/rating variants | Aspect, AudioLanguage, Based, ContentRating, Resolution, SubtitleLanguage, VideoFormat | Correct absent/required captions and placeholders, fitting/template/key dependencies, literal source treatments, default/conditional designs and named rating families |
| M6e — Awards/templates/overlays | Awards, Separators, Overlays | Two private Awards intermediates, award-specific widths/ranges, accepted separator bases/collectionless and all 18 source-preserving overlay groups with both sizes; preserved source case and prior renames |

Together with Playlist, these cover the 21 poster categories and Overlays without forcing them into one font, caption, palette or logo treatment.

### Regression, activation and rollback evidence

Maintain an immutable comparison manifest linking baseline source/artwork, contract/registry/adoption hashes, effective jobs, existing preview/worker receipts and accepted review scope. Audit differences in **both directions**: every expected item present once and no unexpected item added or removed. Keep topological dependency re-visits distinct from unique output counts. Where only validation metadata changes, prove unchanged render parameters/inputs/output hashes from retained evidence rather than regenerate accepted artwork to obtain the same answer.

Meaningful negative tests must show refusal of altered actual inputs and authority/context boundaries, not simply restate schema constants. Include same-size/mtime source edits, wrong-case/colliding paths, stale or missing owned receipts, cross-role decision replay, incomplete required membership, contract downgrade/hash substitution, concurrent decisions, crash between blob/DB writes, invalidation after an approved exception, and a global permission change with unchanged pixels. Test an unchanged control set alongside affected variants so selective invalidation is demonstrated.

Before activation, present an exact commit/registry/adoption/coverage scope plus current test/CI results and unresolved limitations. No phase is COMPLETE merely because tests pass. An approved activation must be explicit and scoped; audit remains the fallback until then. Rollback of the new validation gate restores its prior audit/inactive state and prior registry selection while retaining immutable evidence. It must not revert source artwork, alter accepted bytes/paths or mutate legacy receipts. Generic lifecycle rename/delete reversal remains Phase 4, not an undocumented Phase 2 rollback feature.

Mandatory authoritative translation/routing safeguards, lifecycle transactions, publication integration and end-to-end production pilot remain Phases 3–6. Phase 2 must not silently implement those through the contract adapter.

## Readiness and outstanding blockers

| Area | Status / boundary |
| --- | --- |
| Phase 1 | Merged by the maintainer; accepted tree and exact-head CI retained, with no requested edits |
| Phase 2 architecture and D09 policy | Finalized here under approved D01–D09 decisions; no settled logo policy reopened |
| Start implementation | **Blocked only on explicit maintainer authorization of the next milestone/scope and reviewed base**; this documentation task does not provide it |
| Automatic logo correspondence | **Not ready** until the sealed calibration corpus, held-out results, reproducibility/resource evidence and exact policy approval exist; no numeric thresholds invented |
| Record/preview/dependency integration | Design selected; migration, concurrency, isolation, compatibility and negative cases remain unimplemented and untested until their milestone |
| Enforcement activation / artwork writes | Not authorized; require their separate tested/approved scope. No renderer, source art, production definitions, translation/publication logic or workflows changed by this proposal |

The immediate reviewable next step, if authorized later, is **M1 alone** on a separate implementation branch. Do not start it merely because PR #14 is retargeted, green or merged.

## Documentation-only validation and review checkpoint

Against merged `main` at `f1965cdb61f9a5d43690ec41c768b79db6b39924`, PR #14 must contain only this Markdown document. Verify the accepted Phase 1 files are byte-identical, the roadmap retains Phase 1 COMPLETE and Phases 2–6 NOT STARTED, and PR #13 remains MERGED at the observed commit. Check links/anchors/tables, D01–D09 coverage, selected Package E integration, complete M1–M7 order/gates, the unchanged D09 category/default/exception policies, exact historical counts and source-preserving overlays. Retain prior audits without rerunning art generation or visual review. No code/definitions/assets/workflows change. Run the existing main-targeted CI at the final PR head/new base and report actual results; earlier stacked-base or Phase 1 checks are not a substitute.

Stop for maintainer review of the finalized plan and any subsequent explicit milestone authorization. D01–D09 architecture is retained, D09 business review remains closed and numerical automation awaits evidence. Phase 2 remains NOT STARTED; merged Phase 1 documentation stays unchanged. Keep PR #14 draft and do not merge it, activate contracts, implement code or generate/publish artwork.
