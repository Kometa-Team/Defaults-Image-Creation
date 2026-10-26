# Phase 5 operation, publication and support rules

2026-10-26. M1 planning proposal at merged Phase 4 baseline
`ef3b2713cf5dcab9b92395321c6be3fdf1efdbce`. Existing approved D01–D09 and
P3-D01–D04 policies remain authoritative. New P5-D01–D08 decisions in the
[design](PHASE5_DESIGN_PROPOSAL.md) are proposals, not approvals or executable
commands. No production operation, publication, approval or activation in M1.

## Invariants and decisions at each boundary

| Rule | Required behaviour | Standing / owner |
| --- | --- | --- |
| P5-R01 Exact contract | Category/kind/version/canonical hash and closed variant must have an independently attributed exact contract approval | Existing D01–D02. All 22 current approvals remain absent. |
| P5-R02 Separate authorities | Request, submitter confirmation, independent maintainer decision, operation consumption, activation and merge are distinct, exact scopes | Existing two-stage policy; proposed native capture P5-D01–D03. No self-approval or caller booleans. |
| P5-R03 Complete visual context | Full-resolution native default/requested views, all companions/parents, owned receipts, source/definition/renderer/font/translation/destination context | Existing D07–D09 / M3–M4. Thumbnail or one group representative never substitutes. |
| P5-R04 Currentness | Reverify authoritative source and destination commit/tree, current identities, grants/revocation and decision state at use and before further writes | P3-D01–D02 plus proposed P5 consumption adapter. Unavailable facts block. |
| P5-R05 Official language | Official numeric repository identity and existing `master`/roots support English only | Approved P3-D03–D04. Creation-source PRs still target `main`. Other languages require separately approved coverage and user target. |
| P5-R06 Controlled catalog | Minimal exact raw file patch, unchanged permanent IDs/literal names, existing loader/profile/generator replay and scoped CAS | Proposed P5-D04–D05. No arbitrary source edits or YAML round-trip normalization. |
| P5-R07 Separate membership | Logical operation, complete review, generation workload, technical batch and publication PR have separate memberships | Existing D08. All logical required members must finish before completion/PR handoff. |
| P5-R08 Equal bytes | Only actual equal candidate/public SHA-256 may skip a byte upload | Existing migration rule. Equal pixels/bytes alone grant no mapping, catalog or review permission. |
| P5-R09 Non-force transport | Existing owned Package E draft branch, exact approved membership, verified ancestry, remote actual bytes/full tree | Existing transport boundary. No protected-branch push, force update, generic cleanup or implicit merge. |
| P5-R10 Partial outcomes | Record durable partial/uncertain state; reobserve exact commits/PR/bytes before retry; incomplete group cannot be complete/published | Proposed P5-D05, retaining existing recovery mechanisms. Unrelated independent operations may continue. |
| P5-R11 Retained output | Definition DELETE preserves public artwork, original receipt epochs, aliases, reservations and dependent references | Existing M6 policy. Remote deletion/path reuse needs separate exact authorization P5-D06. |
| P5-R12 Styles/exceptions | Preserve WHITE_ONLY/BOTH_REQUIRED/SOURCE_PRESERVING/special branches and exact approved historical exceptions | Approved D09. No category-wide wash, new threshold, cleanup or exception-by-filename. |
| P5-R13 Identity | Registry permanent ID and semantic child key remain stable across UPDATE/RENAME; retired identity never silently revived | Existing M2/M6. Literal case/Unicode preserved; collision keys only detect conflicts. |
| P5-R14 Bounded work | Existing 512 MiB worker-parent safeguard, worker/process/metadata/pack limits and 15-minute CI jobs | Existing safeguards. Partition reviewed work rather than enlarging caps. |
| P5-R15 Audit | Exact safe principal/decision/context/commit/receipt and previous revision, sanitized errors with stable correlation ID | Proposed adapter over existing immutable Package E evidence; no credentials or new database. |

## Operation and failure handling matrix

| Operation / event | Required evidence and permitted future result | Blocked or separately authorized |
| --- | --- | --- |
| ADD | New controlled permanent ID, exact supported contract/variant, complete source/transparency/parent/translation review, exact new destination membership and catalog patch | No contributor-assigned trusted IDs, implicit branch/category/member, collision reuse or approval inherited from a similar image. |
| UPDATE | Current active identity/mapping, exact current dependency closure, material review/recomposition as needed, complete companions and fresh approvals | Old M5 candidate after M6 stays rejected. Updating a retired identity or silently reusing stale paths is unsupported. |
| Post-M6 UPDATE | Proposed current-mapping adapter reconstructs latest epoch/aliases/dependencies and creates new candidate/receipts/review without changing prior snapshots | Do not remove `require_m5_compatible` or reinterpret pre-rename approval. Adapter is future M4 scope, not implemented. |
| RENAME | Same ID, exact old/new names and reservations, no unauthorized material visual change, current dependency and namespace proof | Local M6 rename is not remote delete. General public rename unsupported initially; keep old path and authorize a new mapping separately if ever allowed. |
| DELETE definition | Explicit retirement, complete dependent/exclusion analysis and exact catalog change; all public bytes and historical references retained | Remote artwork deletion, source deletion, remote branch deletion and reserved-name reuse are separate operations and outside initial transport. |
| Shared source / required pair | Complete current consumer closure, affected full previews, white/colour or standard/bigger companions and independently scoped unchanged reuse | No one-member success, orphaned consumer or hidden generated parent. |
| Concurrent namespace/head change | CAS conflict; preserve existing successful bytes/history, reobserve/replan exact affected scope | No last-writer-wins, forced push or approval transfer to a changed baseline. |
| Network/read failure | Unknown retryable observation, bounded sanitized diagnostics, no new write until facts reverified | No permanent absence/permission grant inferred from timeout/403/404 ambiguity. |
| Interrupted/uncertain push | Inspect owned remote ref, verify exact known commit prefix and actual blobs, recover existing journal/PR idempotently | No blind replay to foreign branch, duplicate logical operation or unverified complete marker. |
| Partially staged operation | Retain complete successful artifacts and verified prefix; mark incomplete and block handoff/catalog consumption | No partial publication manifest or whole-operation completion inferred from successful batches. |
| Compensation | New explicit forward proposal, current authority and reviews; append history and retain published artifacts | No remote reset/force push, forged old authority, receipt edits or automatic destructive rollback. |

## Coverage legend

The tables below are read from the exact current M6 release/contracts/rules,
existing lifecycle capability inventory and generator/overlay registries.

* **P**: existing conditional prospective poster validation through
  `lifecycle.candidates` / actual loader/planner and M6 effective checks.
* **L**: existing special Playlist M3 validation and full native preview path.
* **O**: existing overlay metadata/historical/native-preview path; **new overlay
  job planning is blocked at the pre-seal identity hook**.
* **G**: only the current assigned English Genre single-logo synthetic
  ADD/UPDATE/RENAME/DELETE cohort has positive local commit tests. This does
  not cover all 28 Genre variants, placeholders, shared children or production.
* **B**: production integration blocked, including for G. Every row is B until
  real authority, exact contract approval, current-mapping/catalog and transport
  integration for that exact scope are separately accepted.

Prospective parsing/preview support is not operational support. Required P5 work
includes current-mapping adapter, complete-member source/catalog handling and
trusted consumption; category expansions are reviewed one bounded cohort at a
time under M4. Unsupported variants/operations remain explicitly closed.

## All 22 packages and 278 variants

<!-- PACKAGE_MATRIX: generated from unchanged current release and rules. -->

| Package / kind / exact contract | Variants | Source cohorts | Preserved treatments | Existing planning / local commit | Additional integration |
| --- | ---: | --- | --- | --- | --- |
| [Aspect / poster](../bulk/contracts/categories/data/contracts/aspect-v1.json)<br>`fc14d583c50d28e4f616c2aa853acdfcebdf1a4a9626500912791a8e3baa2b08` | 2 | logo: 1, placeholder: 1 | NOT_APPLICABLE: 1, WHITE_ONLY: 1 | P / none / B | Single logo and placeholder paths separately; no caption invented |
| [AudioLanguage / poster](../bulk/contracts/categories/data/contracts/audiolanguage-v1.json)<br>`bb3c4cb548bcf2cb1f5c4d5a0d1b310ef55509fa99dceed6c835bd8ddbc8072c` | 8 | placeholder: 8 | NOT_APPLICABLE: 8 | P / none / B | Exact text/placeholder captions and controlled language content |
| [Awards / poster](../bulk/contracts/categories/data/contracts/awards-v1.json)<br>`7c0dd7e17e0c2053548d168359f3e6a676412ac8864577c191851013b407b1b9` | 35 | logo: 35 | WHITE_ONLY: 35 | P / none / B | Logo cohorts plus award-years family/parents; retain private intermediates |
| [Based / poster](../bulk/contracts/categories/data/contracts/based-v1.json)<br>`2fbcdbcfa7ead20213143fecfff7a39ab5ef3b86214f54eaf67225f9cc2f5103` | 1 | placeholder: 1 | NOT_APPLICABLE: 1 | P / none / B | Text-only caption/template; no logo-source intake |
| [Chart / poster](../bulk/contracts/categories/data/contracts/chart-v1.json)<br>`31e51f40fedc6c7b713bc8778c37fe4f2261b6190e7ff68b36088dbb08f0141f` | 36 | logo: 36 | BOTH_REQUIRED: 36 | P / none / B | Complete white/colour logo group |
| [ContentRating / poster](../bulk/contracts/categories/data/contracts/contentrating-v1.json)<br>`fb4494c27910daf618ae9c58e7df8a867a0836e4a1b40f7c64b46cff6ffbaef3` | 3 | logo: 2, placeholder: 1 | NOT_APPLICABLE: 1, WHITE_ONLY: 2 | P / none / B | Logo/placeholder cohorts plus content-rating-series children |
| [Country / poster](../bulk/contracts/categories/data/contracts/country-v1.json)<br>`bcfc3498f96b8412b016c1c93a600448fe591c485a5994f52798f14bb3ec99cd` | 56 | logo: 54, placeholder: 2 | BOTH_REQUIRED: 54, NOT_APPLICABLE: 2 | P / none / B | Complete white/colour logos and existing text-counterpart groups |
| [Decade / poster](../bulk/contracts/categories/data/contracts/decade-v1.json)<br>`e215dc4c5a41ea1fb51415f9ddf841033a066b2e3472ea648e28bffb8dedea8c` | 17 | composition: 1, placeholder: 16 | NOT_APPLICABLE: 16, SPECIAL: 1 | P / none / B | Placeholder captions, best-of-years owned parent compositions |
| [Franchise / poster](../bulk/contracts/categories/data/contracts/franchise-v1.json)<br>`3f95c0f4c80df9aba2934c5e1e4e50065bdd894e9202ec2f0a3aa5f80d19bf1b` | 2 | logo: 2 | WHITE_ONLY: 2 | P / none / B | WHITE_ONLY source/exception and current mapping |
| [Genre / poster](../bulk/contracts/categories/data/contracts/genre-v1.json)<br>`ad2bb267b9fb0b0452fd92da9630f323f9ca86c80c169b930fbf8387d96a778a` | 28 | logo: 27, placeholder: 1 | NOT_APPLICABLE: 1, WHITE_ONLY: 27 | P / G subset / B | G current-mapping UPDATE first; other cohorts/placeholder separately blocked |
| [Network / poster](../bulk/contracts/categories/data/contracts/network-v1.json)<br>`fd090570f6b7976e064660dec91f9f8207980cbb9e6e7d6e2aeafa3cc7b05b0c` | 10 | logo: 8, placeholder: 2 | BOTH_REQUIRED: 8, NOT_APPLICABLE: 2 | P / none / B | Complete white/colour logos and existing text-counterpart groups |
| [Playlist / poster](../bulk/contracts/playlist/contract-v1.json)<br>`5047d834ecd3f8e5a0ed76ae24760b6947ae6b83e95198ce602e1715e445016b` | 1 | logo: 1 | WHITE_ONLY: 1 | L / none / B | Exact timeline-order caption/background permission, fixed 154 font and current names |
| [Resolution / poster](../bulk/contracts/categories/data/contracts/resolution-v1.json)<br>`4475c9bb450380395a2a2e982fcf72cb33f8453fe3d4665ea8a171e9f6570865` | 2 | logo: 1, placeholder: 1 | NOT_APPLICABLE: 1, WHITE_ONLY: 1 | P / none / B | Distinct logo and caption/placeholder cohorts |
| [Seasonal / poster](../bulk/contracts/categories/data/contracts/seasonal-v1.json)<br>`1124fecbde06c2c78c8fba9772d16de65d9cc70ae0d29a8f203b931f2e2507c7` | 6 | logo: 6 | WHITE_ONLY: 6 | P / none / B | WHITE_ONLY source/exception and current mapping |
| [Separators / poster](../bulk/contracts/categories/data/contracts/separators-v1.json)<br>`f846c148539eebf0bcdad47cb9b2c2e68c3e7517c8566b12acf40dc7426e3331` | 3 | composition: 2, logo: 1 | SPECIAL: 2, WHITE_ONLY: 1 | P / none / B | Named separator-variants, generated base ownership and special compositions |
| [Streaming / poster](../bulk/contracts/categories/data/contracts/streaming-v1.json)<br>`89869d979fa4236590f9195eb216838feab1a63662fb35a78cc49a9c863566de` | 12 | logo: 12 | BOTH_REQUIRED: 12 | P / none / B | Complete white/colour logo group |
| [Studio / poster](../bulk/contracts/categories/data/contracts/studio-v1.json)<br>`d675c3b036fc8a44741552d8c8cf32587b986aa3302343f666da510ea83e35fd` | 6 | logo: 5, placeholder: 1 | NOT_APPLICABLE: 1, SOURCE_PRESERVING: 5 | P / none / B | Source-preserving logos; transparent text placeholders remain not applicable |
| [SubtitleLanguage / poster](../bulk/contracts/categories/data/contracts/subtitlelanguage-v1.json)<br>`dc899a0611b93ea461fb5af6ef79abf2fa6d7fab27c41bf1fb17c5b83bce9e45` | 8 | placeholder: 8 | NOT_APPLICABLE: 8 | P / none / B | Exact text/placeholder captions and language keys |
| [Universe / poster](../bulk/contracts/categories/data/contracts/universe-v1.json)<br>`e85fd297c7e3d537134de23221919d20ff7a2500ca3409c650d8448962b6809c` | 3 | logo: 3 | WHITE_ONLY: 3 | P / none / B | WHITE_ONLY source/exception and current mapping |
| [VideoFormat / poster](../bulk/contracts/categories/data/contracts/videoformat-v1.json)<br>`c872e26f91424b8eb87f7f48bac8d741eac5d479f6a61dadec01951e06c97c4f` | 2 | logo: 2 | SOURCE_PRESERVING: 2 | P / none / B | Source-preserving logo cohorts |
| [Year / poster](../bulk/contracts/categories/data/contracts/year-v1.json)<br>`9536beb851ef832f64493e7467f544db9ad77b07234f9f5dd53613bdb6fc5926` | 19 | composition: 1, placeholder: 18 | NOT_APPLICABLE: 18, SPECIAL: 1 | P / none / B | Placeholder captions, best-of-years owned parent compositions |
| [Overlays / overlay](../bulk/contracts/categories/data/contracts/overlays-v1.json)<br>`b79d5aa935a349137718109adb56dbc4a67b7bc760fc3917eccba595cb5fa551` | 18 | overlay_source: 18 | SOURCE_PRESERVING: 18 | O / none / B | Pre-seal stable identity, branch and both size companions; no new-job executor |

## Generator families

| Existing name / version | Existing mechanism | Additional integration required / blocked cases |
| --- | --- | --- |
| `award-years` / 1 | Bounded explicit year range/step, captured per-value fitting, semantic child assignment before job sealing | Persistent child IDs, complete family catalog patch/review, current dependencies and exclusions; no arbitrary range expansion or child resurrection. |
| `best-of-years` / 1 | Existing parent-directory references, shared translated caption, owned parent artifacts | Complete parent/child render scheduling and lineage, catalog/review atomic membership and persistent deletion exclusions. Missing parent stays blocked. |
| `separator-variants` / 1 | Explicit named bounded variants, source/base colour and evidence | Preserve existing named presentation styles and exact literal paths; each required member and generated source must be supported independently. |
| `content-rating-series` / 1 | Bounded exact rating codes, suffix and per-value measurements | Current semantic lookup, exact code/translation/fitting/member sets and catalog changes; no invented ratings or automatic refitting. |

Source: [generators.py](../bulk/generators.py) `GENERATORS`; prospective integration:
[candidates.py](../bulk/lifecycle/candidates.py) `StablePlanner.expand`;
[coverage.py](../bulk/lifecycle/coverage.py) `matrix`. All four are actual
generation/planning families, with **no general operational lifecycle executor**.
Current M6 retirement identifies generated-member/dependent blockers but does
not implement persistent generator exclusion/export. That remains an explicit
adapter task; deleting a child must not be undone by the next expansion.

## Overlay branches and exact companion boxes

All rows preserve source RGB/alpha, authoritative source basename/case, trim
setting, PNG encoding and both sizes. Boxes are maximum fit boxes, not a promise
that trimmed images fill the box. White branches preserve their supplied white
source; poster white-wash must never be applied. No extra branch or overlay is
inferred from a poster operation. All new operational overlay scopes remain B/O.

<!-- OVERLAY_MATRIX: generated from unchanged overlays-v1 catalog. -->

| Exact source branch | Contract variant | Trim | Standard box | Bigger box | Integration |
| --- | --- | --- | --- | --- | --- |
| `aspect` | `aspect` | false | `[285, 85]` | `[440, 100]` | O / B |
| `content_rating` | `content_rating` | false | `[285, 85]` | `[440, 100]` | O / B |
| `genre` | `genre` | false | `[285, 85]` | `[440, 100]` | O / B |
| `seasonal` | `seasonal` | false | `[285, 85]` | `[440, 100]` | O / B |
| `studio` | `studio` | false | `[285, 85]` | `[440, 100]` | O / B |
| `video_format` | `video_format` | false | `[285, 85]` | `[440, 100]` | O / B |
| `award` | `award` | true | `[285, 85]` | `[440, 100]` | O / B |
| `chart` | `chart` | true | `[285, 85]` | `[440, 100]` | O / B |
| `chart/white` | `chart.white` | true | `[285, 85]` | `[440, 100]` | O / B |
| `country` | `country` | true | `[285, 85]` | `[440, 100]` | O / B |
| `franchise` | `franchise` | true | `[285, 85]` | `[440, 100]` | O / B |
| `network` | `network` | true | `[285, 85]` | `[440, 100]` | O / B |
| `network/white` | `network.white` | true | `[285, 85]` | `[440, 100]` | O / B |
| `playlist` | `playlist` | true | `[285, 85]` | `[440, 100]` | O / B |
| `resolution` | `resolution` | true | `[285, 85]` | `[440, 100]` | O / B |
| `streaming` | `streaming` | true | `[285, 85]` | `[440, 100]` | O / B |
| `streaming/white` | `streaming.white` | true | `[285, 85]` | `[440, 100]` | O / B |
| `universe` | `universe` | true | `[285, 85]` | `[440, 100]` | O / B |

## Policy constraints across coverage

Playlist, Franchise, Genre, Seasonal and Universe keep WHITE_ONLY defaults and
their exact individual SOURCE_PRESERVING exceptions. Applicable Chart, Country,
Network and Streaming logo variants retain BOTH_REQUIRED. Studio and VideoFormat
preserve sources; intrinsically white/black/monochrome is still source preserving.
Text/placeholder/composition cohorts retain NOT_APPLICABLE/SPECIAL rules rather
than fabricated logo intake. Country's six and Network's four historical text
counterpart outputs retain existing paired destinations; their output counts
are not the number of contract cohorts or new white/colour asset variants.

Preserve the 17 accepted normal alpha/background assets and 41 historical uses
without cleanup, warnings, regeneration or new review. Preserve 56 exact accepted
source-preserving historical uses. New bytes/use cannot inherit those exceptions.
Playlist remains Bebas Neue Regular at approved size 154. Captured fitting bounds
for other contracts are evidence, not permission to change algorithms or autoshrink.
These are policy restatements, not new decisions.

Every current package is English-only. New non-English support is a versioned
contract decision, not a translation availability check, captionless-image waiver
or permission inferred from owning a user repository. Official publication stays
English-only even for language-neutral overlays. No M1 changes to policies/fonts.

## Exact variant inventory

The following lists every current variant ID under its exact package selector.
The same ID string may occur in different packages; identity here is
`(category, kind, version, contract_sha256, variant)`, never variant text alone.
The package table's source links resolve to those exact unchanged contracts.
All versions are `1.0.0`; total membership is 278 across 22 packages.

<!-- VARIANT_INVENTORY: generated from unchanged current contracts. -->

### Aspect / poster / 1.0.0 — 2 variants

`logo-single-b3ad77cb3133f479`, `placeholder-single-fa4978e71f7c453d`.

### AudioLanguage / poster / 1.0.0 — 8 variants

`placeholder-single-0a711f667b2abf0c`, `placeholder-single-2a0c824d3229540e`, `placeholder-single-5f67319cf634a91c`, `placeholder-single-63343afe99633920`, `placeholder-single-7b994db0da53b7c5`, `placeholder-single-b96a50e99998438c`, `placeholder-single-f971203202f35bc8`, `placeholder-single-fa4978e71f7c453d`.

### Awards / poster / 1.0.0 — 35 variants

`logo-single-00bd98b885de8174`, `logo-single-1d5101f6bc892f5b`, `logo-single-21cba7456fc5bfd5`, `logo-single-276ce3a3032bda18`, `logo-single-2c8df0f3d489a3a3`, `logo-single-2d4ce8c1f8038bc7`, `logo-single-2dd56c67d8d5eca7`, `logo-single-37ea3cd3ca8293b9`, `logo-single-3ed1dd9872d28e8d`, `logo-single-482e5a4c167a6147`, `logo-single-5008e5abeef32232`, `logo-single-50ba22fff6c39095`, `logo-single-57d48205233fcc7f`, `logo-single-63994adae48a4adf`, `logo-single-6a34235c92f152dc`, `logo-single-6bd447739a13499e`, `logo-single-6f74d19af2da6255`, `logo-single-73515cb81f6f6403`, `logo-single-7d4480082422a3bc`, `logo-single-7ed075f6515bbe1d`, `logo-single-8707426c6914c37d`, `logo-single-96807d6c0925ac5c`, `logo-single-9f2f89e1ddf7e207`, `logo-single-a85f6f303eac2d3e`, `logo-single-b1ae0d1c1036cb9d`, `logo-single-b5eadf8a9f2872e5`, `logo-single-b79ad00f9879fb47`, `logo-single-bc7f1548b1f6176c`, `logo-single-c50f677463571c98`, `logo-single-da25a0c8130159f4`, `logo-single-db3ee94a45014ec6`, `logo-single-e0b431a5bb5ab8e7`, `logo-single-e6b7800f6cb5dba3`, `logo-single-f39ffe02947e1699`, `logo-single-f735a2c6a16d508e`.

### Based / poster / 1.0.0 — 1 variants

`placeholder-single-efe4bc572a9ca105`.

### Chart / poster / 1.0.0 — 36 variants

`logo-color-12cf75d1e4f48a7d`, `logo-color-12dadb7ba6087df7`, `logo-color-1459346da8e79f92`, `logo-color-302bfa70c92e12e1`, `logo-color-4be498b22f5ada3f`, `logo-color-5a26d8a6169063f0`, `logo-color-5cf76e7a62ed4fcd`, `logo-color-62f4d60cfe1d4cb2`, `logo-color-7953f6085314baf8`, `logo-color-8abeee338f18ac27`, `logo-color-8ca957312ba5897e`, `logo-color-90119fcc32f5beef`, `logo-color-9a643ea888416458`, `logo-color-a0b3488c7c584597`, `logo-color-b363dab69b0b2931`, `logo-color-f2915b81ab99ef88`, `logo-color-fbb161df73d6b370`, `logo-color-fce0d71a2e3e1b2b`, `logo-white-0df6faf10c466828`, `logo-white-0f36782d97e78998`, `logo-white-1c27bfae6e170cb5`, `logo-white-1f66581aae44fea3`, `logo-white-1fec1f8e89a26a10`, `logo-white-25655ab9d1b3e584`, `logo-white-436cf0175768ad27`, `logo-white-5d0cb252c83a9228`, `logo-white-6a146bc0f5771b05`, `logo-white-77aa074eabc46c25`, `logo-white-86a0b38d9e8b36b7`, `logo-white-86ff1608d4812fba`, `logo-white-9bb0c55c37ccdfdc`, `logo-white-b4765b60d05cc57e`, `logo-white-c41067ec7adbcc53`, `logo-white-c92ce8094f1b58f0`, `logo-white-d557ac0207553aa3`, `logo-white-e16302a6ae577b92`.

### ContentRating / poster / 1.0.0 — 3 variants

`logo-single-2dd56c67d8d5eca7`, `logo-single-3a78d252fcf78440`, `placeholder-single-fa4978e71f7c453d`.

### Country / poster / 1.0.0 — 56 variants

`logo-color-0398fd670b8a5d32`, `logo-color-10687ff9f2c43e82`, `logo-color-13b0298c04e19382`, `logo-color-149ee66a45046294`, `logo-color-2236751e50a58506`, `logo-color-25330c4af1ebebaf`, `logo-color-34baa0a1bb52ab3b`, `logo-color-3b32317ac626e5f7`, `logo-color-3c598968d3d55554`, `logo-color-42d56890bc4cc85a`, `logo-color-48ec4fbd63274f8d`, `logo-color-49e4e8d490caab45`, `logo-color-5bdc7c9344410ef2`, `logo-color-81fe39deefc05175`, `logo-color-83ce13bb7779cc0a`, `logo-color-8e5beb0c01e64a1b`, `logo-color-b6f47639e87f7505`, `logo-color-c5364a569382a915`, `logo-color-c7f354001183bdde`, `logo-color-d13dabaa45a7063f`, `logo-color-dd278fd9bd4c9646`, `logo-color-deafa348158386db`, `logo-color-e7207399fc3404a5`, `logo-color-eacbd6d86df1be26`, `logo-color-f1085f9bf38c65ef`, `logo-color-f7914debd6902da1`, `logo-color-fea8e5e49ac68739`, `logo-white-00bcaaf0e73fef5c`, `logo-white-149dbf0ddcb278b5`, `logo-white-25e7e69d94a6ec06`, `logo-white-2b0695d2b6145647`, `logo-white-38a1243741adbffc`, `logo-white-3d93ea9eafffc3fd`, `logo-white-41416810c869152b`, `logo-white-4c7af1e7255f4cd5`, `logo-white-4cd48263cb332ced`, `logo-white-5050a6eaa022cc42`, `logo-white-598c88422c45734a`, `logo-white-5d4ac5c5aa25fa27`, `logo-white-5e0450e50edacb8f`, `logo-white-6599aba48adc9b94`, `logo-white-745c996fd23ecbaa`, `logo-white-7b589dbd9980ebd7`, `logo-white-86b99b27126cdf6d`, `logo-white-883a122ddca2070c`, `logo-white-9076fb0d8db65e5e`, `logo-white-b5c9aa7446ca37b0`, `logo-white-becbfc1f44438a27`, `logo-white-c14a65786ab6d73e`, `logo-white-cc138f2ed1215a02`, `logo-white-e503b271bfabf560`, `logo-white-e59c4a3898aff42b`, `logo-white-e5d2b94a489445ad`, `logo-white-e73d1d3dee570242`, `placeholder-color-c9ed5dadc46a61a9`, `placeholder-white-48e947565da62f8a`.

### Decade / poster / 1.0.0 — 17 variants

`composition-single-d258608c72064467`, `placeholder-single-055bd00a18e51d77`, `placeholder-single-12e8c38b941a0925`, `placeholder-single-6373ca59ef6fed3c`, `placeholder-single-6b6b2339da863fa5`, `placeholder-single-71799fc3ff320a91`, `placeholder-single-8f3c072657b810f9`, `placeholder-single-930661784fc17cc4`, `placeholder-single-98c1800baa45137e`, `placeholder-single-9e2d03d42104d81a`, `placeholder-single-b3ab69b1cea78521`, `placeholder-single-babee65f716f2a89`, `placeholder-single-bc5ca729b398c842`, `placeholder-single-c569182cbb9429a6`, `placeholder-single-d1b2a4f29aa9e180`, `placeholder-single-d99577fccbf15cd7`, `placeholder-single-fa4978e71f7c453d`.

### Franchise / poster / 1.0.0 — 2 variants

`logo-single-3bef1f4ee4565f08`, `logo-single-8b0feb5753113095`.

### Genre / poster / 1.0.0 — 28 variants

`logo-single-089f43d446722055`, `logo-single-09fb18859a572280`, `logo-single-1c8acfcb7a4a61dc`, `logo-single-1f0363809a14a632`, `logo-single-2dd56c67d8d5eca7`, `logo-single-2e26e8dee2642488`, `logo-single-38466fbffaa6d9ae`, `logo-single-3f4f6387ea9af884`, `logo-single-52ac1e3c40781087`, `logo-single-54b9b90e88dca67e`, `logo-single-59decc50ff063c7d`, `logo-single-5a892cbfb31d61b6`, `logo-single-6648666c8627f735`, `logo-single-8a4f3536e2285f32`, `logo-single-8abeafb0859d0adc`, `logo-single-9ae7953eb8e6f5a2`, `logo-single-adf13d7f27452a20`, `logo-single-b3fdab351cbc736d`, `logo-single-b440d84be1d85089`, `logo-single-bacf231cf7474fb0`, `logo-single-dd5c4049f4094e7e`, `logo-single-df40776539748f48`, `logo-single-dfe9fb21b047e00e`, `logo-single-e25438b4d54c9819`, `logo-single-ee3188cf31afa307`, `logo-single-fdb2defad6a7efa6`, `logo-single-ffdb1d804bad3993`, `placeholder-single-fa4978e71f7c453d`.

### Network / poster / 1.0.0 — 10 variants

`logo-color-00b143eefc278042`, `logo-color-45d15d3945fe855f`, `logo-color-67635de5394a3872`, `logo-color-990101e775009d40`, `logo-white-4e2137c2fa78928c`, `logo-white-ca5eb0deca4fb8c4`, `logo-white-dd406ab893336210`, `logo-white-ec17b599a56d3610`, `placeholder-color-c9ed5dadc46a61a9`, `placeholder-white-48e947565da62f8a`.

### Playlist / poster / 1.0.0 — 1 variants

`timeline-order`.

### Resolution / poster / 1.0.0 — 2 variants

`logo-single-b3ad77cb3133f479`, `placeholder-single-70528e5084a8fc70`.

### Seasonal / poster / 1.0.0 — 6 variants

`logo-single-1f0363809a14a632`, `logo-single-2dd56c67d8d5eca7`, `logo-single-50c797b0baee9279`, `logo-single-59decc50ff063c7d`, `logo-single-a58ef0cf093b8fdb`, `logo-single-db4122cd5c8efc19`.

### Separators / poster / 1.0.0 — 3 variants

`composition-single-638eee61722a1798`, `composition-single-c7e4aece5c2136d9`, `logo-single-30b636e3464d58b0`.

### Streaming / poster / 1.0.0 — 12 variants

`logo-color-45d15d3945fe855f`, `logo-color-582dda22db619586`, `logo-color-67635de5394a3872`, `logo-color-6f2be78b2e0b08f1`, `logo-color-990101e775009d40`, `logo-color-c783565926642577`, `logo-white-128c662517ed4dd7`, `logo-white-4e2137c2fa78928c`, `logo-white-9345c1e9154a4085`, `logo-white-c6f037b8301b6704`, `logo-white-ca5eb0deca4fb8c4`, `logo-white-ec17b599a56d3610`.

### Studio / poster / 1.0.0 — 6 variants

`logo-single-1df3b4fb5b6b6e2e`, `logo-single-2985198f0cbd1417`, `logo-single-90b14d98ff781bad`, `logo-single-a76b36d0386a574c`, `logo-single-fd21888a4572bc3c`, `placeholder-single-fa4978e71f7c453d`.

### SubtitleLanguage / poster / 1.0.0 — 8 variants

`placeholder-single-2281d27cbca2bd1f`, `placeholder-single-2ac2d80349d4e3d8`, `placeholder-single-3ea36b9a298a5c4b`, `placeholder-single-4e4adf84fcc19313`, `placeholder-single-9ab9bd86b005e4df`, `placeholder-single-9ec8eb1926d9512c`, `placeholder-single-e0780055c94adf8b`, `placeholder-single-fa4978e71f7c453d`.

### Universe / poster / 1.0.0 — 3 variants

`logo-single-3a78d252fcf78440`, `logo-single-b3ad77cb3133f479`, `logo-single-d26fdc6f4097f312`.

### VideoFormat / poster / 1.0.0 — 2 variants

`logo-single-a76b36d0386a574c`, `logo-single-fc0eb05375e8659b`.

### Year / poster / 1.0.0 — 19 variants

`composition-single-d258608c72064467`, `placeholder-single-0aae5ea161749703`, `placeholder-single-0c519b094daf5a2e`, `placeholder-single-1850c1635837ae36`, `placeholder-single-1e66bb50ef79458f`, `placeholder-single-2f26b71c8c67cd79`, `placeholder-single-3021a9f3b59f1461`, `placeholder-single-305169151886b789`, `placeholder-single-39c42b0cc233853b`, `placeholder-single-3a90e9e03a7ae0ed`, `placeholder-single-4a682c0ea4a059af`, `placeholder-single-9b4d52c711855341`, `placeholder-single-a9e7b32e17e720ba`, `placeholder-single-c56399b512c7e030`, `placeholder-single-d3fe45b577298cdc`, `placeholder-single-dca311416132278f`, `placeholder-single-f8e778eabec812b6`, `placeholder-single-fa4978e71f7c453d`, `placeholder-single-fde73f690d364a7f`.

### Overlays / overlay / 1.0.0 — 18 variants

`aspect`, `award`, `chart`, `chart.white`, `content_rating`, `country`, `franchise`, `genre`, `network`, `network.white`, `playlist`, `resolution`, `seasonal`, `streaming`, `streaming.white`, `studio`, `universe`, `video_format`.
