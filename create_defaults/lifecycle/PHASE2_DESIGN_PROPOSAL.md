# Phase 2 design proposal: category contracts

**Proposal only — implementation NOT STARTED.** Prepared 2026-10-20. The maintainer accepted the Phase 1 factual baseline, not every suggested contract or permission. This document proposes decisions for review; it implements no schema, registry, validator, generator, translation or publication change. Phases 2–6 remain NOT STARTED in the [six-phase roadmap](ROADMAP.md).

This proposal is on a separate documentation branch based on Phase 1 acceptance commit `fa276ab5ba1508457c6767f92b21f835794aa483`. Its draft PR targets the Phase 1 documentation branch so the proposal's review diff is independent; **it is not part of [PR #13](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/13)**. Neither PR may be merged without separate authorization. Proposal PR: pending creation.

## Evidence and design objectives

The accepted [discovery](PHASE1_DISCOVERY.md), [category matrix](CATEGORY_RULES_MATRIX.md), [exceptions register](EXCEPTIONS_REGISTER.md) and [gap analysis](GAP_ANALYSIS.md) are the evidence. Their audited source baseline is `e7febf88d1dc8f8b93408e88da78e524b191acea`, artwork baseline `dfff31ab08446353844bb97de601c3a64edc8220`. Source/artwork heads were rechecked on 2026-10-20 and still matched. This proposal does not reclassify the accepted facts or re-review existing art.

The catalog has 4,372 declared definitions, including 102 generator families, expanding to 9,957 posters (9,955 public and two private), plus 4,122 overlays in 18 groups. These are several design families, not one poster template. [profiles.yml](../bulk/catalog/profiles.yml) supplies defaults; [definitions.py](../bulk/definitions.py) validates generic shape and paths. Neither currently makes a category's font or caption a protected design rule. Existing generated poster IDs in [generators.py](../bulk/generators.py), and overlay IDs in [overlay_definitions.py](../bulk/overlay_definitions.py), depend on paths. Those limitations motivate the following proposed architecture.

Recommended objectives are: preserve every adopted output and identity; make design ownership explicit; accept bounded content submissions without granting style control; validate every effective output and dependency; and produce an auditable impact assessment before any category-wide change. A design approval is separate from artwork approval, staging authorization and merge authorization.

## Proposed architecture and trust boundaries

| Proposed component | Responsibility | Boundary |
| --- | --- | --- |
| Contract package | Immutable category ID, schema version, contract version, content hash, named variants, field classifications, permitted content, typography/geometry/output rules and exact exception references | Maintainer-controlled; a submitter cannot declare a new trusted contract, change its hash or approve their own package. |
| Contract approval record | Exact package/version/hash, maintainer decision and scope, prior baseline, intended changes and approval provenance | Recorded from an actual authorized maintainer decision. A `reviewer` string in submitted YAML is not sufficient authority. |
| Submission content | Stable identity reference, display metadata, approved variant/content type, source asset/provenance, approved per-item content values | Strict allowlist. Exposes no arbitrary composer, profile, font, transform or generator parameters. Existing full definitions may be read by a compatibility adapter; that does not make all fields submitter-editable. |
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

These are proposed ownership classifications, distinct from Phase 1's ENFORCED/INHERITED/CONVENTION evidence labels. **LOCKED:** maintainer-controlled. **SUBMITTER:** allowed individual content within stated bounds. **DERIVED:** calculated from approved data/rules. **EXCEPTION:** exact, approved existing variation. **UNDECIDED:** a maintainer decision is required. No classification here grants permission until the proposal and implementation scope are explicitly approved.

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
| Logo/asset submission and provenance | SUBMITTER | Exact source bytes/name and permitted type; content review remains required | D02 |
| Logo resize, anchor, offsets, wash and trim | LOCKED | Explicit per variant; width scaling is not visible-ink normalization | D02 |
| Derived logo height and fitted overlay size | DERIVED | Existing approved aspect/rounding/resampling behavior; do not crop/pad or rescale by ink bounds | D02 |
| Caption position, surface and clipping policy | LOCKED | Preserve baseline dimensions/offsets; proposed new fit exceptions require review | D03 |
| New item brand background color | UNDECIDED | Recommend submitter proposal plus maintainer confirmation; decide bounded palette/brand criteria before enabling | D05 |
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
| Source treatment | Preserve current PNG pixels/alpha/internal whitespace; white wash true; no new trimming, cropping or visible-ink normalization | LOCKED |
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

For a **new** Playlist item, recommend the submitter supplies brand/display content, exact asset/provenance, an already enabled order type and proposed background/name content where permitted. The maintainer confirms its persistent ID, content/asset/color acceptance and exact mapping. The submitter cannot choose another font, fit box, logo/text offset, border, resize mode, destination repository or arbitrary caption string. New artwork still needs the existing validation and visual approval path; a structurally valid submission is not publication approval.

### Release Order and Watch Order extensions

The accepted audit found `key_names.TIMELINE_ORDER` present and the particular keys `key_names.RELEASE_ORDER` / `key_names.WATCH_ORDER` absent from the pinned English catalog. That does not prove no other suitable authoritative key could exist; a maintainer must choose and verify the exact mapping. Do not create speculative keys or English literal fallbacks in this proposal.

Recommended extension process, for future authorization:

1. Maintainer defines a new semantic order type and verifies an existing appropriate authoritative key, or separately authorizes a Weblate contribution. A contract extension cannot manufacture a translation value.
2. Review the type's exact caption, casing/template behavior, fitting at the preserved design, and language applicability. If it cannot fit at 154 under the existing layout, withhold it until a narrowly scoped typography variant/exception is approved. Do not weaken the Timeline Order variant or guess a new size.
3. Approve the new type/variant in a versioned package with its measured scope. It may inherit identical locked geometry/effects but not expose them to submitters. Assess existing nine items as unchanged; no automatic rebinding, renaming or regeneration follows from the extension.
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
| D05 — Colors/content approval | Can submitters choose a new brand color, propose one for confirmation, or select only an approved assignment? | Preserve all existing colors; new brand colors proposed for maintainer confirmation under current color checks | New color-bearing submissions |
| D06 — Identity/names | Which persistent-ID allocation and semantic family-key rules apply, and may submitters propose names? Accept NFC validation for new names? | Preserve all IDs/mappings; persistent new IDs; independent display/text/source/output names; reject non-NFC new names; explicit path confirmation | Stable identity and naming design |
| D07 — Effective checks and coverage | Accept validation after all expansion/overrides and at the actual job boundary? Which entrypoints must fail closed? | All trusted generation/approval adapters, all children/parents and overlay planners; no raw intent or normalized-value bypass | Enforcement implementation and acceptance tests |
| D08 — Review/reuse/activation | What exact contract adoption record can preserve old reviews, and what changes require bulk/individual reapproval? When can enforcement become active? | Preserve exact unchanged artifacts/context with explicit provenance; no broad warning waiver; material rule/permission changes get scoped design review; artifact/staging/merge approvals remain separate | Review compatibility, category-wide changes and activation |

These questions are grouped to support a concrete review, not an invitation to implement before answering. Accepting Phase 1 facts does not resolve them. A decision may narrow the first implementation to Playlist, but then other categories remain explicitly outside new enforcement until their own contracts are approved.

## Recommended future Phase 2 implementation sequence

Every step below is prospective and requires explicit implementation authorization. Phase 2 is **NOT STARTED** now.

1. **Resolve D01–D08 and seal design scope.** Approve exact architecture, first category/variant ownership, exception/adoption rules and cross-phase boundaries. Do not infer authorization from this proposal being merged or reviewed.
2. **Specify representation and validation interfaces.** Define strict contract/content/identity record formats, immutable version/hash semantics, approval provenance and the effective-rule result. Keep translation/publication implementation unchanged.
3. **Build read-only adoption and impact validation first.** Map existing identities and variants to approved rules without editing source definitions or generating images. Report complete coverage and unexplained differences; compare per-job rule/dependency context against accepted evidence. An audit-only mode must not silently claim active enforcement.
4. **Implement the authorized effective-definition gate and Playlist contract.** Cover profile merging, generator children, language overrides, raw/effective parameters, dependencies and typed overlay interfaces as in the approved scope. Reject unknown/unapproved data and forbidden fields, with field-path diagnostics.
5. **Verify adversarial and preservation cases.** Planned checks include profile/font override, same-effective-value clamping tricks, generator child mutation, unapproved language override, fabricated exception/reviewer, arbitrary caption, removed caption, path/Unicode collision, renamed display/source/output retaining ID, forged/stale validation binding, private-output publication and custom-overlay bypass. Compare all nine Playlist effective definitions with accepted design values; do not require a new gallery or rerender solely because the validator exists.
6. **Extend only through approved category examples.** Add era-specific Year/Decade, exact Genre exceptions, Awards private/generated branches, Network/Studio captionless/other treatments, Separators and Overlays. The remaining categories must have explicit coverage before an all-library claim. No generic catch-all contract or automatic year expansion.
7. **Return measured evidence for activation/acceptance.** Report effective-rule coverage, unchanged source/artwork proof, negative cases, unresolved decisions and intended entrypoints. If visual change or production image generation is needed later, obtain its separate authorization and use the appropriate later phase workflow. Enforcement activation and Phase 2 COMPLETE require explicit maintainer decisions.

The sequence intentionally stops short of implementing mandatory translation routing, generic rename/delete, publication adapters or the production pilot; those remain Phases 3–6. No new code, test module, config, contract file, definition, translation, font, artwork or generated image accompanies this proposal.

## Documentation-only validation and review checkpoint

The separate proposal branch must differ from Phase 1 acceptance head `fa276ab5ba1508457c6767f92b21f835794aa483` only by this Markdown document. Verify inherited Phase 1 documents remain byte-identical, the full six-phase roadmap has Phase 1 COMPLETE and Phases 2–6 NOT STARTED, links/anchors/tables resolve, all nine Playlist source values match the approved evidence, and no tracked production behavior changes exist. No render-producing local tests are needed for this document. Automatic GitHub CI is reported at its actual head, never borrowed from another commit.

Review should decide whether to accept/amend this design and answer D01–D08 before any separate implementation authorization. Until then Phase 2 remains NOT STARTED. Keep both PRs draft, do not merge, and do not generate or publish artwork.
