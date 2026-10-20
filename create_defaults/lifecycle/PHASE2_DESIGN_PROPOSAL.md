# Phase 2 design proposal: category contracts

**Proposal only — implementation NOT STARTED.** Prepared 2026-10-20. The maintainer accepted the Phase 1 factual baseline, not every suggested contract or permission. This document proposes decisions for review; it implements no schema, registry, validator, generator, translation or publication change. Phases 2–6 remain NOT STARTED in the [six-phase roadmap](ROADMAP.md).

**D09 update, 2026-10-20:** The maintainer supplied the logo-source, transparency, variant and two-stage approval requirements below as business requirements for this design. They do not authorize implementation or new previews now. Category mappings inferred from historical behavior and uncalibrated comparison/quality thresholds remain explicitly identified for review. PR #13 and its accepted discovery files are unchanged.

This proposal is on a separate documentation branch based on Phase 1 acceptance commit `fa276ab5ba1508457c6767f92b21f835794aa483`. Its [draft PR #14](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/14) targets the Phase 1 documentation branch so the proposal's review diff is independent; **it is not part of [PR #13](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/13)**. Neither PR may be merged without separate authorization.

## Evidence and design objectives

The accepted [discovery](PHASE1_DISCOVERY.md), [category matrix](CATEGORY_RULES_MATRIX.md), [exceptions register](EXCEPTIONS_REGISTER.md) and [gap analysis](GAP_ANALYSIS.md) are the evidence. Their audited source baseline is `e7febf88d1dc8f8b93408e88da78e524b191acea`, artwork baseline `dfff31ab08446353844bb97de601c3a64edc8220`. Source/artwork heads were rechecked on 2026-10-20 and still matched. This proposal does not reclassify the accepted facts or re-review existing art.

The catalog has 4,372 declared definitions, including 102 generator families, expanding to 9,957 posters (9,955 public and two private), plus 4,122 overlays in 18 groups. These are several design families, not one poster template. [profiles.yml](../bulk/catalog/profiles.yml) supplies defaults; [definitions.py](../bulk/definitions.py) validates generic shape and paths. Neither currently makes a category's font or caption a protected design rule. Existing generated poster IDs in [generators.py](../bulk/generators.py), and overlay IDs in [overlay_definitions.py](../bulk/overlay_definitions.py), depend on paths. Those limitations motivate the following proposed architecture.

Recommended objectives are: preserve every adopted output and identity; make design ownership explicit; accept bounded content submissions without granting style control; validate every effective output and dependency; and produce an auditable impact assessment before any category-wide change. A design approval is separate from artwork approval, staging authorization and merge authorization.

## Proposed architecture and trust boundaries

| Proposed component | Responsibility | Boundary |
| --- | --- | --- |
| Contract package | Immutable category ID, schema version, contract version, content hash, named variants, field classifications, permitted content, typography/geometry/output rules, required logo presentations by output kind, exact transformation provenance and exception references | Maintainer-controlled; a submitter cannot declare a new trusted contract, change its hash or approve their own package. |
| Contract approval record | Exact package/version/hash, maintainer decision and scope, prior baseline, intended changes and approval provenance | Recorded from an actual authorized maintainer decision. A `reviewer` string in submitted YAML is not sufficient authority. |
| Submission content | Stable identity reference, display metadata, approved variant/content type, original transparent PNG/provenance, optional separate white PNG, approved per-item content values and submitter preview decisions | Strict allowlist. Exposes no arbitrary composer, profile, font, transform or generator parameters. Source colors and proposed background colors do not grant control of rendered logo styling. |
| Identity and mapping record | Persisted logical IDs, semantic family-member keys, exact source/local/public mappings and history | Independent of rendered text and output filenames. Existing mappings and IDs are adopted unchanged. General rename/delete execution remains Phase 4. |
| Effective contract resolver | Pinned category base + one explicitly named variant + matching, approved exception; validated content supplies only permitted leaves | Closed, deterministic composition. No arbitrary inheritance, expressions, executable YAML or "last override wins" for locked fields. Unresolved/conflicting rules fail closed. |
| Expanded-definition validator | Compares every materialized poster/overlay job and its provenance against the selected effective rules | Runs after existing profile/override/generator/language expansion and effective parameter normalization, before trusted generation. Checking only source YAML is insufficient. |
| Impact and validation record | Effective-rule hash per job, definition/input/renderer identities, rejected fields, affected membership and before/after material differences | Reuses existing fingerprint and dependency evidence; it is not permission to generate, waive warnings, stage or merge. |

The recommended package layout is conceptual: header/ownership, named variants, field permissions, caption/language policy, typography, composition or overlay transform, identity/naming/routing, dependencies, exception references, and compatibility/approval history. These are design sections, **not implemented filenames or a schema API**. The illustrative examples below are not loadable definitions.

### Versioning and adoption

Recommend separate `schema_version` and immutable contract versions. Select an exact version **and canonical SHA-256**, never floating `latest`. A schema version describes representation; a contract version describes category behavior/permissions. Record package bytes/hash and resolved rule hashes in validation provenance. Existing [common.canonical/fingerprint](../bulk/common.py) are reusable foundations, but do not already supply contract approval or canonical schema migration.

Recommended version policy: a change to an existing variant's locked appearance, permission boundary or exception scope requires a new reviewed design revision; adding a named content type without changing existing variants still needs an explicitly approved extension. No version increment is automatically approved because it is labeled minor or patch. The maintainer must decide the final numbering convention (D01).

Initial adoption should map every existing ID to a contract/variant/exception **without editing definitions, reminting IDs, renaming files, substituting fonts or rerendering**. Use the accepted source/asset hashes and fitting evidence. Reject an unexplained mismatch; do not enlarge a rule merely to achieve a desired adoption count. Coverage must include static and generated children, both private intermediates, both overlay sizes and dependency parents. Existing behavior outside the modeled scope remains unchanged; a future enforcement switch requires its own authorization.

Use a package hash for audit and a resolved, material-rule hash for each job. Adding an independent variant need not stale existing artwork decisions when the effective rules, candidate bytes, dependencies and material review context are unchanged. Do not forge or rewrite historical receipts to achieve reuse. If the existing approval format cannot express the provenance bridge, require an explicit maintainer-bound adoption/compatibility record. Any changed candidate bytes or material context invalidate the affected decision. Exact reuse/invalidation criteria remain D08, not an automatic waiver.

### What an ordinary submitter can provide

Recommend an explicit content form/allowlist rather than a general YAML override interface. A submitter may propose display metadata, an approved content/variant choice and exact source artwork with provenance. Only fields marked SUBMITTER in the selected variant can be supplied. A requested identity, color or filename is a proposal until confirmed under its category rules. Source assets cannot carry an exemption, select a font or choose a publication destination.

Maintainers control contract/variant creation, typography, layout, encoding, source treatment, caption-key mappings, field permissions, language/exception scope, identity assignment and public-path approval. A maintainer's role alone does not imply an image merge or bulk design authorization. Definitions can retain explicit historical style fields for compatibility, but their values must equal the adopted rule or the specifically approved exception.

## Proposed rule decision matrix

These ownership classifications are distinct from Phase 1's ENFORCED/INHERITED/CONVENTION evidence labels. **LOCKED:** maintainer-controlled. **SUBMITTER:** allowed individual content within stated bounds. **DERIVED:** calculated from approved data/rules. **EXCEPTION:** exact, approved existing variation. **UNDECIDED:** a maintainer decision is required. D09's explicitly supplied business requirements are recorded as such; remaining proposed mappings/defaults are not approved merely by this matrix. No classification authorizes implementation, artwork generation or remote writes.

| Rule | Class | Recommended default / boundary | Decision |
| --- | --- | --- | --- |
| Contract owner, schema, version and approved hash | LOCKED | Immutable exact references and explicit maintainer approval | D01 |
| Version numbering and adoption authority | UNDECIDED | Separate representation/design versions; preserve baseline IDs, bytes and approvals through an explicit adoption record | D01 |
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
| New supported language, RTL and authoritative-source gate | UNDECIDED | Use existing preflight today; define boundaries now, implement mandatory safeguards in Phase 3 | D04 |
| Logo/asset submission and provenance | SUBMITTER | New logos must be valid genuinely transparent PNGs; original hash/name retained; optional separate white PNG is compared, not trusted by filename | D02, D09 |
| Required logo presentations | LOCKED | WHITE_ONLY, COLOR_ONLY, BOTH_REQUIRED or SPECIAL / NOT APPLICABLE per category/variant/output kind; Playlist WHITE_ONLY | D09 |
| Logo resize, anchor, offsets, wash and trim | LOCKED | Explicit per variant; existing white-wash algorithm unchanged; contributor cannot alter category styling | D02, D09 |
| White presentation from colored master | DERIVED | Existing alpha-preserving white-wash, exact version/context and preview; original source remains unchanged | D09 |
| New PNG transparency/integrity gate | LOCKED | Decode and alpha-content checks, quality/background/clipping review; reject opaque input and request a transparent PNG; never remove backgrounds automatically | D09 |
| Historical alpha/source exceptions | EXCEPTION | Adopt only exact approved assets/contexts; no retroactive rewrite and no exemption inherited by replacement bytes | D09 |
| Separate-white correspondence result | DERIVED | MATCH, REVIEW REQUIRED or MISMATCH from bounded deterministic geometry/mask evidence under an approved comparison policy | D09 |
| Comparison and source-quality numeric thresholds | UNDECIDED | Calibrate before implementation; resolution/anti-alias differences alone are not mismatches or grounds for auto-approval | D09 |
| Complete required variant set | LOCKED | BOTH_REQUIRED additions need both presentations validated and approved, plus the contract's required outputs; no half-complete acceptance | D09 |
| Submitter preview confirmation | SUBMITTER | Explicit approve/reject decision for exact previews and complete variant membership; never publication approval | D09 |
| Final logo/brand approval | LOCKED | Separate maintainer decision over brand identity, transparency, derived whites, consistency, category compliance and all required outputs | D09 |
| Derived logo height and fitted overlay size | DERIVED | Existing approved aspect/rounding/resampling behavior; do not crop/pad or rescale by ink bounds | D02 |
| Caption position, surface and clipping policy | LOCKED | Preserve baseline dimensions/offsets; proposed new fit exceptions require review | D03 |
| New item brand background color proposal | SUBMITTER | Only where the category permits; proposal separate from source logo colors and rendered treatment; maintainer gives final approval | D05, D09 |
| Category-specific background palettes/criteria | UNDECIDED | Preserve existing assignments; confirm which categories permit proposals and their bounds before enabling | D05, D09 |
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
| New-name Unicode normalization behavior | UNDECIDED | Recommend require NFC for new names and reject non-NFC input with explanation; never silently normalize existing paths | D06 |
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

No existing historical exception can be self-assigned by a new submission. Where classification is UNDECIDED, submission remains withheld pending the named decision; a recommended default is not approval.

## D09 — Logo sources, variants, transparency and approval

### Required presentations, not required upload counts

The category or approved variant owns one of four requirements: **WHITE_ONLY**, **COLOR_ONLY**, **BOTH_REQUIRED**, or **SPECIAL / NOT APPLICABLE**. These describe the resulting presentations, not the number of source uploads. COLOR_ONLY means preserving the approved original logo colors, which may themselves be monochrome; it does not require adding color to a monochrome brand. WHITE_ONLY may accept a colored transparent master and derive white. BOTH_REQUIRED may use that same master for original-color and white treatments. SPECIAL must name the allowed design/exception or explain the absence of a logo; it is not a contributor-selectable bypass.

**Confirmed new business rule: Playlist is WHITE_ONLY.** The proposed mappings for other categories below are inferred from current assignments and output branches, not newly approved category contracts. The complete output-kind matrix must specify whether each required presentation produces posters, overlays or both. A paired poster category does not automatically acquire a missing overlay group. For a BOTH_REQUIRED addition, both presentations must validate and pass both approval stages before that addition is accepted; a complete unrelated addition need not wait for it.

### Category-by-category audit: historical facts versus new policy

This is a targeted logo audit, not a rerun of Phase 1. Selectors come from [config.CATEGORIES](../bulk/config.py). Counts below use the byte-verified [complete English job ledger](../bulk/evidence/package-e/full-ledger-index.json), the current linked category YAML/profile and [generator behavior](../bulk/generators.py), with source case resolved only by the explicit [case ledger](../bulk/catalog/asset-case-migrations-v1.json). No definition or image is changed. The 9,957 concrete records are classified by the **actual logo input**, excluding `transparent.png` placeholders and already generated parent/base compositions from normal logo counts. A `white_wash: true` on a blank placeholder is not evidence of a white-logo requirement. A false flag does not prove that source pixels are colored.

In the historical column, **W** means a real logo passed through the current white-wash; **P** means its source colors were preserved; **T** means no visible logo/shared transparent placeholder; **C** means a generated parent or separator base composition. These are counts of outputs/uses, not unique files. Every row totals its accepted concrete category count. A color/white filename counterpart confirms output membership, not geometry or brand equivalence.

| Category and source evidence | Confirmed historical behavior (W / P / T / C) | Proposed requirement for new submissions and bounded exceptions |
| --- | --- | --- |
| [Aspect](../bulk/catalog/aspect.yml) | 8 / 0 / 1 / 0; other-aspect is text-only | WHITE_ONLY for ratio logos; NOT APPLICABLE for text-only other |
| [AudioLanguage](../bulk/catalog/audiolanguage.yml) | 0 / 0 / 188 / 0; transparent placeholder throughout | NOT APPLICABLE; language text does not authorize adding a logo |
| [Awards](../bulk/catalog/awards.yml) | 4,847 / 0 / 0 / 0 from 16 award sources; includes two private intermediates | WHITE_ONLY for poster logos; keep award-specific size/geometry and private outputs; overlay treatment remains separately scoped below |
| [Based](../bulk/catalog/based.yml) | 0 / 0 / 4 / 0; text-only | NOT APPLICABLE |
| [Chart](../bulk/catalog/chart.yml) | 0 / 1,182 / 0 / 0; color/white branches, 591 same-filename poster pairs; separate stored white sources | BOTH_REQUIRED for the paired chart design; white result may be derived, not necessarily a second upload |
| [ContentRating](../bulk/catalog/contentrating.yml) | 71 / 0 / 1 / 0; 47 distinct poster logo sources; other is text-only | WHITE_ONLY for existing poster-logo designs; NOT APPLICABLE for other; raw rating overlays are distinct designs |
| [Country](../bulk/catalog/country.yml) | 301 / 301 / 6 / 0; 304 paired poster filenames, including three text-only pairs; white flags derive from shared sources | BOTH_REQUIRED for flag posters; NOT APPLICABLE for the paired text-only cases; no invented white-overlay group |
| [Decade](../bulk/catalog/decade.yml) | 0 / 0 / 16 / 15; literal captions and generated best-of parents | SPECIAL / NOT APPLICABLE: era composition, not a free-standing logo upload |
| [Franchise](../bulk/catalog/franchise.yml) | 103 / 15 / 0 / 0; one poster per item, no paired color/white destinations | SPECIAL: exact item/design selects WHITE_ONLY or source-preserving COLOR_ONLY; recommend white default only after maintainer confirmation; do not infer BOTH_REQUIRED |
| [Genre](../bulk/catalog/genre.yml) | 235 / 39 / 1 / 0; 39 source-preserving uses include two Silent outputs sharing one source | SPECIAL: retain named WHITE_ONLY and source-preserving designs; exact Splatter exception remains red, no wash; NOT APPLICABLE for other |
| [Network](../bulk/catalog/network.yml) | 0 / 564 / 4 / 0; 284 paired poster filenames including two text-only pairs; separate stored white sources | BOTH_REQUIRED for logo-bearing paired designs; NOT APPLICABLE for other/kids-other; grandfather historical alpha/background observations |
| [Playlist](../bulk/catalog/playlist.yml) | 9 / 0 / 0 / 0; all nine use existing white-wash | **WHITE_ONLY — explicitly required by the maintainer**, with original layout and source hashes preserved |
| [Resolution](../bulk/catalog/resolution.yml) | 13 / 0 / 2 / 0 | WHITE_ONLY for icons; NOT APPLICABLE for text-only other variants |
| [Seasonal](../bulk/catalog/seasonal.yml) | 22 / 1 / 0 / 0; Black History retains source colors | SPECIAL: WHITE_ONLY for washed designs, COLOR_ONLY for the exact Black History treatment; no paired output requirement inferred |
| [Separators](../bulk/catalog/separators.yml) | 1 / 0 / 0 / 748; collectionless uses one washed logo; remaining inputs are approved base compositions | SPECIAL: retain base-template families; WHITE_ONLY for collectionless's logo treatment; a template is not a new contributor logo |
| [Streaming](../bulk/catalog/streaming.yml) | 0 / 256 / 0 / 0; 128 paired poster filenames; separate stored white sources | BOTH_REQUIRED for paired brand/caption designs; optional white upload must correspond to the colored master |
| [Studio](../bulk/catalog/studio.yml) | 0 / 486 / 2 / 0; real logos preserve source colors; true wash flags occur on text-only placeholders | COLOR_ONLY/source-preserving proposed, including intentionally monochrome brand sources; NOT APPLICABLE for other/animation-other; confirm any new brand-specific white-only rule separately |
| [SubtitleLanguage](../bulk/catalog/subtitlelanguage.yml) | 0 / 0 / 188 / 0 | NOT APPLICABLE; preserve text-only design |
| [Universe](../bulk/catalog/universe.yml) | 19 / 1 / 0 / 0; Monsterverse preserves source colors | SPECIAL: WHITE_ONLY for washed designs; exact Monsterverse COLOR_ONLY treatment; no paired output requirement inferred |
| [VideoFormat](../bulk/catalog/videoformat.yml) | 0 / 6 / 0 / 0 | COLOR_ONLY/source-preserving; preserve any intrinsically monochrome source |
| [Overlays](../bulk/catalog/overlays-v1.json) | 18 groups, 2,061 inputs, 4,122 outputs; existing transform preserves input RGB/alpha, with no white-wash step | SPECIAL per group/output kind, with the proposed presentation mappings below; standard/bigger sizes are required size variants, not color variants |
| [Year](../bulk/catalog/year.yml) | 0 / 0 / 151 / 150; literal years and generated best-of parents | SPECIAL / NOT APPLICABLE: preserve era typography and parent compositions, not a new logo rule |

The source-preserving Franchise exceptions are the exact existing outputs: 28 Days Weeks Later, Bosch, Bourne, Death in Paradise (2011), Father Brown, Game of Thrones, Hellboy, Inspector Morse, IP Man, John Wick, John Wick2, Power, Reacher, RoboCop and Spartacus. The Genre source-preserving uses are bounded by their exact 39 current definitions/contexts, not every new genre; source/display spellings can differ (Creature Feature uses `Creature Horror.png`, Surreal uses `Surrealism.png`). Together with Black History and Monsterverse, these are intentional non-washed assignments, not evidence that contributors may choose styling. Preserve the accepted source hashes, exact mappings and existing decisions; do not infer new exceptions from a matching brand string.

### Overlay requirements are independent of poster branch counts

Historical evidence is [overlays-v1.json](../bulk/catalog/overlays-v1.json) and [overlays.render](../bulk/overlays.py). All groups currently preserve their supplied source colors; only trim and bounding box differ. Each input has standard and bigger outputs. The following **new-submission mappings are proposals**, except Playlist's explicit WHITE_ONLY rule; existing approved outputs remain grandfathered, even when a proposed mapping would apply white treatment to a newly supplied colored master.

| Existing overlay group | Sources × two sizes | Historical treatment | Proposed new-submission presentation scope |
| --- | --- | --- | --- |
| `aspect` | 8 × 2 | Source-preserving, no trim | WHITE_ONLY candidate matching the icon design; confirm mapping before activation |
| `content_rating` | 98 × 2 | Source-preserving, no trim; includes colored rating assets absent from poster-logo scope | SPECIAL per rating design; retain original-color and historical monochrome treatments, not a universal poster white rule |
| `genre` | 272 × 2 | Source-preserving, no trim | SPECIAL per approved source/design, including source-color exceptions; do not whiten every existing genre overlay |
| `seasonal` | 21 × 2 | Source-preserving, no trim | SPECIAL per source/design, with Black History's source colors retained |
| `studio` | 486 × 2 | Source-preserving, no trim | COLOR_ONLY/source-preserving candidate |
| `video_format` | 6 × 2 | Source-preserving, no trim | COLOR_ONLY/source-preserving candidate |
| `award` | 16 × 2 | Source-preserving, trim | WHITE_ONLY candidate for the award design, pending output-kind confirmation; no historical rewrite |
| `chart`, `chart/white` | 33 × 2 each | Separate source branches, trim | BOTH_REQUIRED across the paired groups: color and white, each standard/bigger |
| `country` | 300 × 2 | One source-preserving group, trim | COLOR_ONLY/source-preserving overlay candidate despite paired poster presentations; adding a white group would require a separate design/mapping decision |
| `franchise` | 118 × 2 | Source-preserving, trim | SPECIAL per approved source/design; poster wash flags do not alone dictate overlay appearance |
| `network`, `network/white` | 282 × 2 each | Separate source branches, trim | BOTH_REQUIRED across paired groups, each standard/bigger |
| `playlist` | 9 × 2 | Source-preserving, trim | WHITE_ONLY for new presentations; a new colored master must feed a derived white node before overlay sizing, not pass colored RGB directly into the current transform |
| `resolution` | 13 × 2 | Source-preserving, trim | WHITE_ONLY candidate for icon design, pending output-kind confirmation |
| `streaming`, `streaming/white` | 32 × 2 each | Separate source branches, trim | BOTH_REQUIRED across paired groups, each standard/bigger |
| `universe` | 20 × 2 | Source-preserving, trim | SPECIAL per approved source/design; Monsterverse's historical source colors remain scoped |

This enumerates all 18 groups. AudioLanguage, Based, Country-white, Decade, Separators, SubtitleLanguage and Year have no corresponding standalone group in the present overlay catalog; absence is not a missing required image. Overlay-only source membership can exceed poster-logo membership. A new contract must list required outputs explicitly rather than fabricate a poster or overlay from every file found in a directory.

Directory names are not proof of pure white pixels. A read-only alpha-masked raw-RGB observation of the 347 sources in the three `white` branches found 203 exactly white at every visible pixel and 144 with some nonwhite visible channel values: Chart 28/33 exact-white, Network 151/282, Streaming 24/32. Nonwhite values include grayscale/anti-alias details and retained color; **this is not a perceptual defect classification, a MATCH test, or a new cleanup queue**. Eight of nine Playlist sources also contain nonwhite visible RGB; their poster presentations are white because the renderer performs white-wash. Keep every accepted historical asset/output unchanged; validate the future resulting presentation rather than trusting a folder name.

### PNG transparency, integrity and source quality

**New logo submissions must be valid PNGs with genuine transparency.** Verify PNG format/signature and integrity, then reopen and fully decode within the existing bounded single-frame image constraints. Check effective decoded alpha, including PNG palette transparency or grayscale-plus-alpha; an RGBA mode label alone proves nothing. Require visible foreground and meaningful transparent background around the intended logo. Reject fully opaque PNGs, empty/fully transparent inputs, corrupt/truncated files and disguised non-PNGs; ask the contributor to provide a valid transparent PNG. Do not create a blank preview or remove a background automatically.

Alpha below 255 somewhere is necessary but insufficient: one transparent pixel in an opaque rectangle, translucent matte/backdrop, baked checkerboard or clipped edge is not a clean transparent logo. Report alpha range/distribution, foreground bounds, edge contact, dimensions and proposed scale; inspect unwanted backgrounds, halos, clipping, readability and source quality in the later preview. A soft glow may legitimately have intermediate alpha: no invented numeric cutoff or guessed minimum resolution is approved here. Ambiguous background/quality evidence is REVIEW REQUIRED and withheld, not automatically repaired or accepted. Never mistake a logo's intentional filled brand shape/internal cutout for a removable background. Source-quality limits must be category/target-specific and calibrated before automatic decisions.

The targeted read-only audit verified and decoded **all 2,061 distinct authoritative PNG sources**: no integrity errors; 2,044 contain both visible content and fully clear pixels; 14 have partial alpha but no zero-alpha pixel; three are fully opaque. This describes alpha content, not a new full visual-quality review. All are approved historical assets and are grandfathered at their exact hashes and context, without regeneration or background edits. The 17 non-clear observations are:

| Existing source family | Exact observed assets | Alpha observation / treatment |
| --- | --- | --- |
| `logos_network` | `DR1.png`, `ORF.png`, `TF1.png` | Fully opaque RGBA (alpha 255 throughout); preserve historical assets; new submissions with this condition must be rejected |
| `logos_network` | `BET+.png`, `Game Show Network.png`, `TVP1.png` | Partial alpha, no fully clear pixel; preserve approved sources; this observation alone does not establish acceptable new-source transparency |
| `logos_studio` | `TSG Entertainment.png` | Partial alpha, no fully clear pixel; exact historical exception, not a new-upload exemption |
| `logos_content_rating` | `usgc.png`, `usnc-17c.png`, `uspg-13c.png`, `uspgc.png`, `usrc.png`, `ustv-14c.png`, `ustv-gc.png`, `ustv-mac.png`, `ustv-pgc.png`, `ustv-yc.png` | Ten colored rating sources with partial alpha and no fully clear pixel; historical overlay assets, not a reason to change poster white treatment |

Grandfathering applies to the existing approved bytes and use, not an arbitrary replacement uploaded under the same filename. It does not resurrect the retired Splatter definition or waive brand/quality review for a new use. Text-only placeholders and approved base/generated compositions are not contributor logos; a submitter cannot label a new brand logo NOT APPLICABLE to evade these checks.

### Existing white-wash and separate color responsibilities

The current [poster renderer](../create_poster.py) loads the original image as RGBA, keeps its alpha channel, replaces RGB with white and restores that same alpha before the existing resize/compositing steps. **Reuse that exact approved transformation; do not change its algorithm, infer a new alpha mask, remove backgrounds or overwrite the source.** Derived white is a separately identified artifact with the original source hash, transform/code/runtime identity and exact parameters. Preview creation is a future authorized workflow, not an action performed by this documentation task.

For a white-required presentation, accept a qualifying transparent colored master, retain its original bytes/name, derive white using the existing transformation, and prepare the exact resulting logo/output previews. The submitter must explicitly approve or reject them; the maintainer must then give a separate final decision. Already-white sources still pass transparency/identity checks. When BOTH_REQUIRED, one transparent colored master may produce both presentations; a second white upload is optional, not mandatory. Both resulting presentations and every contract-required output must complete validation and both approval stages before the addition is accepted.

Color-defined internal details can disappear when all RGB becomes white even though alpha is preserved exactly. The preview/brand review must catch that loss of readability or identity; ask for a suitable transparent asset or resolve a specific approved variant rather than changing the wash algorithm, auto-cutting holes or treating an unchanged alpha mask as sufficient approval.

Keep three independent quantities: **original logo RGB**, **required rendered logo treatment**, and **poster background color**. White-wash changes the second, not the saved original or the background. A contributor may propose a new brand background only where the category permits; final approval belongs to the maintainer. Contributors cannot toggle wash, recolor the logo, change group styling, or select a new contrast/effect policy through their background proposal. Existing per-item backgrounds and accepted logo treatments remain unchanged.

The existing overlay renderer does not implement white-wash. A future contract-directed derived-white input must therefore be explicitly modeled and validated before applying the unchanged overlay trim/size transform. This document neither changes `overlays.py` nor repoints existing catalogs. Preserve the authoritative source basename on both output sizes; a private derived node does not grant permission for public logo-tree changes or a different destination. Any necessary adapter/publication integration belongs to its separately authorized phase.

### Optional separate-white comparison: deterministic, bounded and reviewable

If a contributor supplies both colored and white PNGs, first validate both as new transparent sources and bind them to the same claimed brand/variant. Compare the white upload with the white-washed colored master; do not silently substitute a different brand asset or deem matching basenames sufficient. Prefer lightweight deterministic Pillow operations and bounded mask/geometry measurements, with no large AI model/dependency.

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

Represent the future dependency graph as original asset identity/hash → original-color or derived-white presentation → exact poster compositions and applicable standard/bigger overlays. An optional separate-white source and its correspondence evidence are additional dependencies only for the presentations/decisions that use them. Include approved transform, trim/resize parameters, category/variant context, backgrounds and source-file mappings. Existing input/parent hashes and [worker invalidation evidence](../bulk/tests/test_package_e.py) are foundations, not an implemented D09 graph.

| Change | Required impact and approval handling |
| --- | --- |
| Original logo bytes | Find every actual consumer, including shared brands, derived whites and both sizes of applicable overlay groups. Revalidate affected sources/previews/decisions; preserve unrelated posters. RGB-only edits may leave a white mask unchanged, but the changed source/brand context still needs review. |
| Optional separate-white bytes | Recompare that pair and invalidate its affected preview/approval context; do not regenerate unrelated color-only outputs solely because an unused white file exists. |
| Source filename/case, same bytes | Preserve stable ID and exact source mapping; inspect all path references, shared consumers and both overlay basenames. Current path-containing fingerprints may change even when pixels do not. Do not promise a cache hit, invent historical aliases or remint IDs; reuse only with valid explicit provenance. No automatic public rename. |
| White-wash/resize/trim algorithm or rule | Category/design change requiring explicit versioned impact assessment and approval, not contributor content. The algorithm is unchanged in this task. |
| Poster background proposal | Affect only compositions using that approved assignment and their reviewed context; do not alter the original logo or background-independent overlays. |
| Shared logo used across categories | Evaluate each consumer's own style/exception and size mapping. A WHITE_ONLY use does not recolor a COLOR_ONLY consumer or overwrite a shared master. |

Preserve source PNGs, exact case, accents and persisted IDs independently of preview/workspace names. Derive the complete affected graph before deciding what needs rendering; reuse valid unaffected outputs/receipts and compare actual hashes for affected outputs. Do not rerender or re-review the full library merely because D09 is documented. An eligible binary-different output still requires publication synchronization; equal remote SHA-256 skips artwork upload but does not manufacture a valid source-context approval.

Remaining D09 decisions are limited to confirming the proposed non-Playlist category/output-kind mappings (especially mixed styles and source-preserving overlays), calibrated correspondence/quality thresholds and intentional paired-lockup exceptions. The new PNG/no-background-removal requirement, Playlist WHITE_ONLY, permitted existing white-wash, submitter-then-maintainer decisions and complete BOTH_REQUIRED acceptance are supplied business requirements, not questions to reopen.

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
| Required logo presentation | WHITE_ONLY for all new Playlist logo presentations; source upload may be a transparent colored PNG | LOCKED by D09; source RGB is not the required rendered color |
| Source treatment | Preserve original PNG bytes/name/alpha/internal whitespace; use the unchanged existing white-wash for resulting white presentation; no background removal, cropping or visible-ink normalization | LOCKED; derived white separately bound |
| Required source/preview approval | New genuinely transparent PNG passes intake; submitter approves/rejects exact white-result previews and applicable required outputs; separate final maintainer logo/design approval follows | D09 two-stage requirement; neither stage permits publication |
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

For a **new** Playlist item, the submitter supplies brand/display content, a valid genuinely transparent PNG/provenance, an already enabled order type and proposed background/name content where permitted. A transparent colored master is acceptable: the future workflow retains it unchanged and derives the WHITE_ONLY treatment with the existing white-wash. The submitter explicitly confirms or rejects the exact white previews and complete required outputs; the maintainer separately gives final brand/transparency/consistency/category/output approval, confirms the persistent ID, background and exact mapping. New Playlist overlays must use the approved white presentation before the unchanged standard/bigger transform, rather than accidentally preserving a colored master. Existing nine sources/posters/overlays and their accepted decisions remain grandfathered unchanged. The submitter cannot choose another font, fit box, logo/text offset, border, wash/resize mode, destination repository or arbitrary caption string. Structural validity and either preview/design approval stage are not publication approval; separate exact candidate/staging authorization is still required.

### Release Order and Watch Order extensions

The accepted audit found `key_names.TIMELINE_ORDER` present and the particular keys `key_names.RELEASE_ORDER` / `key_names.WATCH_ORDER` absent from the pinned English catalog. That does not prove no other suitable authoritative key could exist; a maintainer must choose and verify the exact mapping. Do not create speculative keys or English literal fallbacks in this proposal.

Recommended extension process, for future authorization:

1. Maintainer defines a new semantic order type and verifies an existing appropriate authoritative key, or separately authorizes a Weblate contribution. A contract extension cannot manufacture a translation value.
2. Review the type's exact caption, casing/template behavior, fitting at the preserved design, and language applicability. If it cannot fit at 154 under the existing layout, withhold it until a narrowly scoped typography variant/exception is approved. Do not weaken the Timeline Order variant or guess a new size.
3. Approve the new type/variant in a versioned package with its measured scope. It inherits Playlist's WHITE_ONLY/two-stage logo requirements and may inherit identical locked geometry/effects without exposing them to submitters. Assess existing nine items as unchanged; no automatic rebinding, renaming or regeneration follows from the extension.
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
| Studio | Brand-specific logo sizes/wash, captionless normal logos, other/animation-other translated cases. | Preserve exact source and path mappings, including `A.C.G.T..jpg`; punctuation is not cleaned from filenames. New logo content is allowed only within its design boundary. |
| Separators | Named-color families, approved historical source templates and the root collectionless output. | Derive approved family members and colors from bounded design assignments. Preserve source templates, no-gradient variant and `collectionless.jpg`; not every member has the same gradient/width/caption behavior. |
| Overlays | Typed transform contracts per group: trim/no-trim, color/white branches, standard/bigger sizes. Source PNG/provenance is content. | **No composed caption/font**. Lock exact source basename, sRGB/RGBA PNG compression 9, Lanczos, approved trim behavior and boxes 285 × 85 / 440 × 100 with existing rounding. Actual fitted dimensions derive from source aspect; no fixed padded canvas. Existing 18 groups and 21 case corrections remain exact. Embedded lettering is artwork, not a prohibited caption field. |

Aspect, AudioLanguage, Based, Chart, ContentRating, Country, Franchise, Resolution, Seasonal, Streaming, SubtitleLanguage, Universe and VideoFormat also require explicit coverage from the matrix before any broad enforcement activation. For example AudioLanguage/SubtitleLanguage and Based use the shared transparent placeholder and text, whereas Franchise/Universe/VideoFormat are captionless. An implementation limited to the Playlist example must not claim all-category enforcement or silently assign one generic rule to the remaining categories.

An exception should bind the exact logical ID(s), category/variant, affected field/value or diagnostic, source/renderer/measurement context, actual maintainer approval, and invalidation conditions. Avoid exceptions matching arbitrary filenames, all historical records, all warnings or every globally approved font. A negative or changed context must fail closed. Retaining an existing decision does not mean a new candidate can reuse it.

## Stable identity and exact naming

Recommend retaining every adopted `id` literally and assigning new IDs once within the existing safe identifier grammar. Neither a display change, translated caption, source asset rename, output rename nor contract-version change should remint it. New IDs may be opaque or semantic, but must not be computed from a mutable output path. The exact new-ID format and registry ownership are D06.

Generated members need a persisted mapping keyed by immutable family identity plus a stable semantic member key (for example year value and approved design variant), not its current filename. Existing generated child IDs are frozen into that mapping; do not "fix" them by rewriting all existing IDs. Overlay identity similarly needs an asset identity plus size/design variant, with current IDs adopted unchanged. Reject duplicate semantic assignments and attempts to bind one ID to unrelated objects. General transactional rename/delete, aliases and tombstones are Phase 4 work, not a side effect of Phase 2 contract adoption.

Keep six independent properties: persistent ID, display name, rendered caption, source asset path, generated local path and published destination. New filenames may be proposed under an allowed content rule but become approved literal mappings; rendering should resolve them, not infer a rename from display or translation changes. Use existing portable-path and NFC+casefold collision checks across the **complete expanded namespace**, including case-sensitive environments, generated members, dependencies and both overlay sizes. A duplicate exact path is also a conflict. Source reuse by several posters is legitimate; an output collision is not.

Recommended new-name policy is NFC validation with explicit rejection of non-NFC input; preserve every adopted literal spelling. No silent accent removal, title-casing, punctuation cleanup or normalization-driven remote move. Keep `Pokémon`, spaces, `X-men.png`, `dca.png`, `DragonBall.png`, `A.C.G.T..jpg` and the separate Action & Adventure public mapping. Exact directory spelling and Windows portability remain checked. URL percent-encoding belongs to transport, not the filename contract. Case-only changes require an explicit identity/mapping decision; there is no "equivalent filesystem path" shortcut.

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

## Decisions required before implementation

| Decision | Maintainer question | Recommended default | Blocking scope |
| --- | --- | --- | --- |
| D01 — Ownership/version/adoption | Who can approve contracts, how are versions represented, and what exact baseline adoption record is authoritative? | Maintainer-owned immutable hash-pinned packages; actual decision receipts; no floating version or implicit migration | All contract enforcement |
| D02 — Variant and field boundary | Accept the proposed Playlist locks and the category-specific variant model? Which per-item selections are allowed? | Keep exact established designs; named variants; explicit content allowlists; complete category coverage before broad activation | Category contract authoring/enforcement |
| D03 — Typography | Is Timeline Order fixed at 154, and what approved fitting/override rules may new captions/languages use? | Preserve current English at 154; historical fit bounds are evidence only; withhold other typography until measured and approved | New caption/typography variants |
| D04 — Captions/languages/destinations | Who approves order-type keys, applicability, fallbacks, RTL and language routing, and where do later phase gates integrate? | Only approved authoritative key mappings; no invented fallback; official English-only; Phase 3 owns mandatory source/routing safeguards | New types/languages and cross-phase interfaces |
| D05 — Colors/content approval | Which categories permit brand background proposals, and what palette/brand constraints apply? | D09 fixes the boundary: contributors may propose where permitted, maintainer gives final approval; preserve existing colors and distinguish background from source RGB/rendered logo treatment | New color-bearing submissions |
| D06 — Identity/names | Which persistent-ID allocation and semantic family-key rules apply, and may submitters propose names? Accept NFC validation for new names? | Preserve all IDs/mappings; persistent new IDs; independent display/text/source/output names; reject non-NFC new names; explicit path confirmation | Stable identity and naming design |
| D07 — Effective checks and coverage | Accept validation after all expansion/overrides and at the actual job boundary? Which entrypoints must fail closed? | All trusted generation/approval adapters, all children/parents and overlay planners; no raw intent or normalized-value bypass | Enforcement implementation and acceptance tests |
| D08 — Review/reuse/activation | What exact contract adoption record can preserve old reviews, and what changes require bulk/individual reapproval? When can enforcement become active? | Preserve exact unchanged artifacts/context with explicit provenance; no broad warning waiver; material rule/permission changes get scoped design review; artifact/staging/merge approvals remain separate | Review compatibility, category-wide changes and activation |
| D09 — Logo sources, variants, transparency and approval | Confirm the proposed non-Playlist category/output-kind mappings, numeric comparison/quality criteria and handling of intentionally different paired lockups? | Supplied business rules: Playlist WHITE_ONLY; new transparent PNGs only, no automatic background removal; unchanged alpha-preserving white-wash permitted; BOTH_REQUIRED must be complete; submitter confirms previews then maintainer gives final logo/design approval; exact hashes/context and separate publication authorization. Historical assets remain grandfathered. Only the stated mapping/calibration details remain open | New-logo intake, paired correspondence, preview completeness and bound two-stage decisions; no implementation authorized |

These questions are grouped to support a concrete review, not an invitation to implement before answering. Phase 1 acceptance alone does not approve proposed contracts. D09's supplied business requirements are recorded as agreed; its proposed mappings/calibration details remain open, without reopening the fixed requirements. A decision may narrow the first implementation to Playlist, but then other categories remain explicitly outside new enforcement until their own contracts are approved.

## Recommended future Phase 2 implementation sequence

Every step below is prospective and requires explicit implementation authorization. Phase 2 is **NOT STARTED** now.

1. **Resolve open D01–D09 details and seal design scope.** Preserve D09's supplied business rules; approve remaining architecture, category/output-kind maps, numeric calibration scope, exception/adoption rules and cross-phase boundaries. Do not infer implementation authorization from review or merge of the proposal.
2. **Specify representation and validation interfaces.** Include required presentations separately from upload counts, original/optional-white sources, derived transforms, exact output-kind membership and both approval records in the strict contract/content/identity design. Keep translation/publication implementation unchanged.
3. **Build read-only adoption and impact validation first.** Map existing identities/variants/historical alpha exceptions without editing definitions or images. Preserve exact source hashes, existing color/white branches, private intermediates and absent overlay groups. Report unexplained differences, not a mass cleanup or silent enforcement activation.
4. **Implement only the authorized effective-definition and PNG intake gates.** Cover expansion/overrides and actual jobs, new-PNG decoding/alpha/integrity/quality diagnostics, exact historical exemptions, Playlist WHITE_ONLY and shared-source dependency closure. Reject forbidden overrides, opaque uploads and attempts to bypass intake through SPECIAL; never add background removal or change the white-wash algorithm.
5. **Calibrate correspondence and prepare the authorized two-stage preview path.** Use deterministic bounded Pillow analysis with positive resolution/anti-alias controls and structural negative controls; approve thresholds before automatic MATCH. In a separately authorized implementation/test scope, retain originals, use the exact existing wash, bind all required preview variants, require submitter confirmation and then separate maintainer approval. Preview preparation must never write production or authorize staging.
6. **Verify adversarial and preservation cases.** Retain D01–D08 tests for profile/font/clamping/generator/language/identity/path/forged-context/private-output/overlay bypasses. Add D09 cases for opaque RGBA, empty/corrupt/disguised PNG, valid palette transparency, tiny-transparency matte, preserved alpha/source hash, AA/resolution REVIEW REQUIRED rather than automatic MISMATCH, lost cutouts/branding structural MISMATCH, rejected/incomplete paired previews, changed source with identical derived-white bytes and filename-only impact. Keep all nine existing Playlist designs and 2,061 approved assets unchanged; no repeat gallery is required for unchanged accepted artifacts.
7. **Extend only through approved category examples.** Add era, exact Genre, Awards, Network/Studio, Separators and typed overlay rules with confirmed per-output-kind logo mappings. Both presentations must complete approval where BOTH_REQUIRED; do not fabricate Country-white overlays or expose category styling to submitters. Cover all remaining categories before claiming all-library enforcement.
8. **Return measured evidence for activation/acceptance.** Report coverage, unchanged-source/artwork proof, complete required memberships, calibration/negative controls, both decision bindings and remaining blockers. Obtain separate authorization for any future production generation/publication. Enforcement activation and Phase 2 COMPLETE require explicit maintainer decisions.

The sequence intentionally stops short of implementing mandatory translation routing, generic rename/delete, publication adapters or the production pilot; those remain Phases 3–6. No new code, test module, config, contract file, definition, translation, font, artwork or generated image accompanies this proposal.

## Documentation-only validation and review checkpoint

The separate proposal branch must differ from Phase 1 acceptance head `fa276ab5ba1508457c6767f92b21f835794aa483` only by this Markdown document. Verify PR #13 stays at that exact head, inherited Phase 1 files remain byte-identical, the six-phase roadmap retains Phase 1 COMPLETE and Phases 2–6 NOT STARTED, and links/anchors/tables resolve. Validate D09 coverage of all 21 categories and 18 overlay groups, measured logo-use totals, historical alpha observations, all nine Playlist source values and the explicit policy-versus-observation distinction. Targeted source integrity/alpha reads and raw-RGB measurements produce no image or preview files; no tracked Python, definitions, fonts, assets, translations or publication code changes accompany them. No render-producing local tests are needed for documentation. Automatic GitHub CI is reported at its actual head, never borrowed from another commit.

Review should decide whether to accept/amend this design and resolve open D01–D09 details before any separate implementation authorization. D09 business requirements supplied by the maintainer remain recorded; proposed non-Playlist mappings/calibration are not silently approved. Phase 2 remains NOT STARTED. Keep both PRs draft, do not modify PR #13, do not merge, and do not generate or publish artwork.
