# Category rules matrix

**Observed baseline, not approved future contracts.** Source `e7febf88d1dc8f8b93408e88da78e524b191acea`; read-only audit 2026-10-20. [Discovery](PHASE1_DISCOVERY.md) explains enforcement and [gaps](GAP_ANALYSIS.md) separates proposals.

## Inventory and reproducibility

Selectors were obtained from [config.CATEGORIES](../bulk/config.py), not a manually assumed list. `load_catalog(["All"])` plus `Planner(generators=GENERATORS).expand(...)` validates and expands every poster definition without rendering. Overlays are independently inventoried from [overlays-v1.json](../bulk/catalog/overlays-v1.json). The older poster-only loader error for selecting just Overlays is not evidence that the separate overlay operator is unavailable.

**22 selectors: 21 poster categories and Overlays. 4,372 declared poster definitions = 4,270 static + 102 generator-family definitions. Expansion produces 9,957 concrete poster definitions: 9,955 public and two private. Overlays add 18 groups, 36 group/size operations, 2,061 source inputs and 4,122 concrete transforms. Public generated scope: 14,077 images.**

| Category | Declared | Concrete | Public English | Generator-family definitions |
| --- | ---: | ---: | ---: | --- |
| [Aspect](#aspect) | 9 | 9 | 9 | none |
| [AudioLanguage](#audiolanguage) | 188 | 188 | 188 | none |
| [Awards](#awards) | 161 | 4,847 | 4,845 | award-years: 64 |
| [Based](#based) | 4 | 4 | 4 | none |
| [Chart](#chart) | 1,182 | 1,182 | 1,182 | none |
| [ContentRating](#contentrating) | 50 | 72 | 72 | content-rating-series: 2 |
| [Country](#country) | 608 | 608 | 608 | none |
| [Decade](#decade) | 17 | 31 | 31 | best-of-years: 1 |
| [Franchise](#franchise) | 118 | 118 | 118 | none |
| [Genre](#genre) | 275 | 275 | 275 | none |
| [Network](#network) | 568 | 568 | 568 | none |
| [Playlist](#playlist) | 9 | 9 | 9 | none |
| [Resolution](#resolution) | 15 | 15 | 15 | none |
| [Seasonal](#seasonal) | 23 | 23 | 23 | none |
| [Separators](#separators) | 35 | 749 | 749 | separator-variants: 34 |
| [Streaming](#streaming) | 256 | 256 | 256 | none |
| [Studio](#studio) | 488 | 488 | 488 | none |
| [SubtitleLanguage](#subtitlelanguage) | 188 | 188 | 188 | none |
| [Universe](#universe) | 20 | 20 | 20 | none |
| [VideoFormat](#videoformat) | 6 | 6 | 6 | none |
| [Year](#year) | 152 | 301 | 301 | best-of-years: 1 |

Counts reconcile with [test_catalog_generation.py](../bulk/tests/test_catalog_generation.py). All expanded records were schema validated. The named generators are `award-years`, `best-of-years`, `separator-variants`, `content-rating-series`, version 1, in [generators.py](../bulk/generators.py); no YAML expressions are evaluated.

## Shared interpretation of every category row

**ENFORCED (E):** strict generic schema, unique IDs/portable paths, exact-case physical inputs, global approved font hashes, captured text/font/size binding, manifest collision checks and immutable render/input identities. These checks do not enforce category-specific fonts, required/prohibited captions, or submitter edit permissions. See [definitions.py](../bulk/definitions.py), [asset_cases.py](../bulk/asset_cases.py), [preflight.py](../bulk/preflight.py), [planner.py](../bulk/planner.py).

**INHERITED (I):** every current poster definition extends [legacy-poster](../bulk/catalog/profiles.yml). Defaults include Comfortaa Medium 250, uppercase, fixed layout, white text/wash, gradient 1, no border, no average/dominant sampling. Effective values below include every override and generator expansion; their category uniformity is **CONVENTION (C)** unless a specific E check is named. **EXCEPTION (X)** references the [register](EXCEPTIONS_REGISTER.md); **UNKNOWN (U)** denotes unapproved future permissions.

**E output:** 2000 × 3000 RGB JPEG, quality 100, subsampling 0. Literal output filenames/directories and `remote_paths.en` come from each linked YAML; English local root is `defaults-en/`. Shared caption raster 1900 × 1000; captured fitting boxes are independently recorded. Logo width preserves aspect ratio, horizontal center; logo/text offsets are relative to vertical center, positive downward. Font sizes below are captured effective source values, not permission to select arbitrary sizes inside a range.

**I/C language:** all current definitions declare English. Referenced caption/template keys are required only for translation-mode variants; none/shared need no translation. Historical non-English applicability can expand locally with remote path null; authored definitions require explicit language declarations. Per-category examples below are not an all-key allowlist; complete literal key assignments are in the linked source.

**E case/Unicode:** exact source/destination spellings; NFC+casefold collision detection, no accent stripping or automatic public rename. Each category inherits these checks, including those with all-ASCII current names. **U submitter permissions:** none implemented. Proposed fields below require maintainer approval and a future contract; locked design proposals never authorize current edits.

## Aspect

Source: [aspect.yml](../bulk/catalog/aspect.yml). **9 declared → 9 concrete; 9 public.** Aspect logos plus a translated other-aspect caption; preserve ratio-specific source widths.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** conditional by existing variant: none, translation; case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 250. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 1 distinct required key references; examples `collections.aspect_ratio_other.name`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** fixed: 8, captured_fit: 1. Centered; logo offsets 0; text offsets 0; logo widths 1600, 1800. Captured binding **E**. |
| Logos / source assets | **C:** roots `logos_aspect`, `transparent.png`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 9 exact base-color values; gradient 1; white_wash true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `aspect`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; no generator families; 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Aspect logos plus a translated other-aspect caption; preserve ratio-specific source widths. Measured variable composer fields: `base_color`, `logo`, `logo_resize`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `font_size`, `gradient`, `logo_offset`, `text_offset`, `white_wash`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## AudioLanguage

Source: [audiolanguage.yml](../bulk/catalog/audiolanguage.yml). **188 declared → 188 concrete; 188 public.** Text-only language captions on the shared transparent placeholder, with optional audio-language template; language identity, key, color and captured fit vary intentionally.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** required on every existing variant; case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 188, 221, 228, 238, 241, 245, 250. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 189 distinct required key references; examples `collections.audio_language.name`, `collections.audio_language_other.name`, `key_names.ABKHAZIAN`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** captured_fit: 188. Centered; logo offsets 0; text offsets 0; logo widths 1600, 2000. Captured binding **E**. |
| Logos / source assets | **C:** roots `transparent.png`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 188 exact base-color values; gradient 1; white_wash true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `audio_language`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; no generator families; 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Text-only language captions on the shared transparent placeholder, with optional audio-language template; language identity, key, color and captured fit vary intentionally. Measured variable composer fields: `base_color`, `font_size`, `logo_resize`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `gradient`, `logo_offset`, `text_offset`, `white_wash`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Awards

Source: [awards.yml](../bulk/catalog/awards.yml). **161 declared → 4,847 concrete; 4,845 public.** Award branding, year literals, best/winner/nomination captions and award-specific widths; 64 bounded year families, two private intermediates.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** conditional by existing variant: none, shared, translation; case exact, upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 20 distinct values (exact assignments in linked category YAML). Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 13 distinct required key references; examples `key_names.ALL_TIME`, `key_names.BEST_ANIMATED_FEATURE_FILM_NOMINATION`, `key_names.BEST_ANIMATED_FEATURE_FILM_WINNERS`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** fixed: 16, captured_fit: 4,831. Centered; logo offsets -500; text offsets 850; logo widths 1000, 1500, 1800, 600. Captured binding **E**. |
| Logos / source assets | **C:** roots `logos_award`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 16 exact base-color values; gradient 1; white_wash true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `_intermediates/award/choice`, `_intermediates/award/oscars`, `award/bafta`, `award/bafta/best`, `award/bafta/nomination`, `award/bafta/winner`, `award/berlinale`, `award/berlinale/best`, `award/berlinale/nomination`, `award/berlinale/winner`, `award/cannes`, `award/cannes/best`, `award/cannes/nomination`, `award/cannes/winner`, `award/cesar`, `award/cesar/best`, `award/cesar/nomination`, `award/cesar/winner`, `award/choice`, `award/choice/best`, `award/choice/nomination`, `award/choice/winner`, `award/emmys`, `award/emmys/best`, `award/emmys/nomination`, `award/emmys/winner`, `award/golden`, `award/golden/best`, `award/golden/nomination`, `award/golden/winner`, `award/nfr`, `award/oscars`, `award/oscars/best`, `award/oscars/best_director`, `award/oscars/director_nomination`, `award/oscars/nomination`, `award/oscars/picture_nomination`, `award/oscars/winner`, `award/pca`, `award/pca/best`, `award/pca/nomination`, `award/pca/winner`, `award/razzie`, `award/razzie/best`, `award/razzie/nomination`, `award/razzie/winner`, `award/sag`, `award/sag/best`, `award/sag/nomination`, `award/sag/winner`, `award/spirit`, `award/spirit/best`, `award/spirit/nomination`, `award/spirit/winner`, `award/sundance`, `award/sundance/best`, `award/sundance/nomination`, `award/sundance/winner`, `award/tiff`, `award/tiff/best`, `award/tiff/nomination`, `award/tiff/winner`, `award/venice`, `award/venice/best`, `award/venice/nomination`, `award/venice/winner`. Local root `defaults-en`; public paths explicitly `remote_paths.en`; two private Awards intermediates have null remote destination. |
| Profile / generators / dependencies | **I:** `legacy-poster`; award-years (64 families); 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Award branding, year literals, best/winner/nomination captions and award-specific widths; 64 bounded year families, two private intermediates. Measured variable composer fields: `base_color`, `font_size`, `logo`, `logo_resize`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `gradient`, `logo_offset`, `text_offset`, `white_wash`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Based

Source: [based.yml](../bulk/catalog/based.yml). **4 declared → 4 concrete; 4 public.** Four text-only translated based-on content types with distinct keys and colors, using the shared transparent logo placeholder.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** required on every existing variant; case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 250. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 4 distinct required key references; examples `key_names.BASED_ON_A_BOOK`, `key_names.BASED_ON_A_COMIC`, `key_names.BASED_ON_A_TRUE_STORY`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** captured_fit: 4. Centered; logo offsets 0; text offsets 0; logo widths 2000. Captured binding **E**. |
| Logos / source assets | **C:** roots `transparent.png`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 4 exact base-color values; gradient 1; white_wash true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `based`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; no generator families; 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Four text-only translated based-on content types with distinct keys and colors, using the shared transparent logo placeholder. Measured variable composer fields: `base_color`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `font_size`, `gradient`, `logo_offset`, `logo_resize`, `text_offset`, `white_wash`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Chart

Source: [chart.yml](../bulk/catalog/chart.yml). **1,182 declared → 1,182 concrete; 1,182 public.** Color and white source branches; translated chart captions and brand-specific widths. Raw legacy `+-500` is accepted and becomes effective −500, not an extra placement variant.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** required on every existing variant; case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 160, 171, 174, 201, 217, 221, 224, 225, 228, 229, 230, 235, 239, 243, 245, 250. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 110 distinct required key references; examples `key_names.1001_MOVIES_TO_SEE_BEFORE_YOU_DIE`, `key_names.AFI_100_YEARS_100_MOVIES`, `key_names.AIRING_TODAY`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** captured_fit: 1,182. Centered; logo offsets +-500, -500; text offsets 850; logo widths 1500, 1800. Captured binding **E**. |
| Logos / source assets | **C:** roots `logos_chart`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 32 exact base-color values; gradient 1; white_wash false; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `chart/color`, `chart/white`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; no generator families; 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Color and white source branches; translated chart captions and brand-specific widths. Raw legacy `+-500` is accepted and becomes effective −500, not an extra placement variant. Measured variable composer fields: `base_color`, `font_size`, `logo`, `logo_offset`, `logo_resize`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `gradient`, `text_offset`, `white_wash`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## ContentRating

Source: [contentrating.yml](../bulk/catalog/contentrating.yml). **50 declared → 72 concrete; 72 public.** Captionless rating-code logos and translated special labels; regional paths and two bounded rating series.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** conditional by existing variant: none, translation; case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 250. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 4 distinct required key references; examples `collections.content_ratings_other.name`, `key_names.NOT_RATED`, `key_names.RATED`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** fixed: 45, captured_fit: 27. Centered; logo offsets -500, 0; text offsets 0, 850; logo widths 1500, 1600, 1800. Captured binding **E**. |
| Logos / source assets | **C:** roots `logos_content_rating`, `transparent.png`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 36 exact base-color values; gradient 1; white_wash true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `content_rating`, `content_rating/au`, `content_rating/cs`, `content_rating/de`, `content_rating/mal`, `content_rating/nz`, `content_rating/uk`, `content_rating/us`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; content-rating-series (2 families); 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Captionless rating-code logos and translated special labels; regional paths and two bounded rating series. Measured variable composer fields: `base_color`, `logo`, `logo_offset`, `logo_resize`, `text_offset`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `font_size`, `gradient`, `white_wash`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Country

Source: [country.yml](../bulk/catalog/country.yml). **608 declared → 608 concrete; 608 public.** Color/white flag variants, deliberately varied logo widths and country keys; keep exact flag artwork and names.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** required on every existing variant; case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 196, 211, 215, 216, 225, 226, 229, 230, 233, 234, 238, 244, 245, 247, 250. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 304 distinct required key references; examples `collections.continent_other.name`, `collections.country_other.name`, `collections.region_other.name`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** captured_fit: 608. Centered; logo offsets -500, 0; text offsets 0, 850; logo widths 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 350, 450, 650, 750, 850. Captured binding **E**. |
| Logos / source assets | **C:** roots `logos_country`, `transparent.png`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 300 exact base-color values; gradient 1; white_wash false, true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `country/color`, `country/white`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; no generator families; 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Color/white flag variants, deliberately varied logo widths and country keys; keep exact flag artwork and names. Measured variable composer fields: `base_color`, `font_size`, `logo`, `logo_offset`, `logo_resize`, `text_offset`, `white_wash`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `gradient`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Decade

Source: [decade.yml](../bulk/catalog/decade.yml). **17 declared → 31 concrete; 31 public.** Era-specific fonts/styles and literal decade text; best-of children consume generated decade posters. Do not unify typography.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** conditional by existing variant: shared, translation; case exact, upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** 16 era/default fonts; see font table and exact era assignments in source (weights 400/500/700). Sizes: 200, 250, 300, 340, 342, 393, 398, 400, 409, 414, 418, 421, 425, 439, 453, 500. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 2 distinct required key references; examples `collections.decade_other.name`, `key_names.BEST_OF`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** captured_fit: 30, fixed: 1. Centered; logo offsets 0; text offsets -400, 0; logo widths 1600, 2000. Captured binding **E**. |
| Logos / source assets | **C:** roots `defaults-en`, `transparent.png`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 3 exact base-color values; gradient 1; white_wash false, true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `decade`, `decade/best`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; best-of-years (1 families); 15 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Era-specific fonts/styles and literal decade text; best-of children consume generated decade posters. Do not unify typography. Measured variable composer fields: `base_color`, `font`, `font_size`, `logo`, `logo_resize`, `text_offset`, `white_wash`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `gradient`, `logo_offset`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Franchise

Source: [franchise.yml](../bulk/catalog/franchise.yml). **118 declared → 118 concrete; 118 public.** Captionless branded logos, variable brand background and white-wash treatment; Death in Paradise year correction retained.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** composer caption absent on every existing variant (propose prohibited unless a named design variant is approved); case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 250. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 0 distinct required key references; none. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** fixed: 118. Centered; logo offsets 0; text offsets 0; logo widths 1600. Captured binding **E**. |
| Logos / source assets | **C:** roots `logos_franchise`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 112 exact base-color values; gradient 1; white_wash false, true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `franchise`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; no generator families; 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Captionless branded logos, variable brand background and white-wash treatment; Death in Paradise year correction retained. Measured variable composer fields: `base_color`, `logo`, `white_wash`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `font_size`, `gradient`, `logo_offset`, `logo_resize`, `text_offset`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Genre

Source: [genre.yml](../bulk/catalog/genre.yml). **275 declared → 275 concrete; 275 public.** Translated genre labels, multiple logo treatments and captured sizes; red Splatter is the explicitly guarded exception.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** required on every existing variant; case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 21 distinct values (exact assignments in linked category YAML). Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 274 distinct required key references; examples `collections.genre_other.name`, `key_names.1001_MOVIES_YOU_MUST_SEE_BEFORE_YOU_DIE`, `key_names.ABSURDISM`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** captured_fit: 275. Centered; logo offsets -500, 0; text offsets 0, 850; logo widths 1500, 1600, 1800. Captured binding **E**. |
| Logos / source assets | **C:** roots `logos_genre`, `transparent.png`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 266 exact base-color values; gradient 1; white_wash false, true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `genre`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; no generator families; 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Translated genre labels, multiple logo treatments and captured sizes; red Splatter is the explicitly guarded exception. Measured variable composer fields: `base_color`, `font_size`, `logo`, `logo_offset`, `logo_resize`, `text_offset`, `white_wash`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `gradient`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Network

Source: [network.yml](../bulk/catalog/network.yml). **568 declared → 568 concrete; 568 public.** Color/white logos with captioned other/kids-other cases; intentional width and wash variants.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** conditional by existing variant: none, translation; case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 250. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 2 distinct required key references; examples `collections.network_kids_other.name`, `collections.network_other.name`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** fixed: 564, captured_fit: 4. Centered; logo offsets 0; text offsets 0; logo widths 1000, 1400, 1600, 500. Captured binding **E**. |
| Logos / source assets | **C:** roots `logos_network`, `transparent.png`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 280 exact base-color values; gradient 1; white_wash false, true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `network/color`, `network/white`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; no generator families; 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Color/white logos with captioned other/kids-other cases; intentional width and wash variants. Measured variable composer fields: `base_color`, `logo`, `logo_resize`, `white_wash`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `font_size`, `gradient`, `logo_offset`, `text_offset`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Playlist

Source: [playlist.yml](../bulk/catalog/playlist.yml). **9 declared → 9 concrete; 9 public.** Nine brand logos/colors, shared Timeline Order key and Bebas Neue 154 geometry. See complete asset/identity tables below.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** required on every existing variant; case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `BebasNeue-Regular.ttf` (weight 400). Sizes: 154. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 1 distinct required key references; examples `key_names.TIMELINE_ORDER`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** captured_fit: 9. Centered; logo offsets -200; text offsets 450; logo widths 1600. Captured binding **E**. |
| Logos / source assets | **C:** roots `logos_playlist`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 9 exact base-color values; gradient 1; white_wash true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `playlist`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; no generator families; 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Nine brand logos/colors, shared Timeline Order key and Bebas Neue 154 geometry. See complete asset/identity tables below. Measured variable composer fields: `base_color`, `logo`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `font_size`, `gradient`, `logo_offset`, `logo_resize`, `text_offset`, `white_wash`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Resolution

Source: [resolution.yml](../bulk/catalog/resolution.yml). **15 declared → 15 concrete; 15 public.** Resolution icons, standards subdirectory and captioned other cases; preserve icon widths and two captured sizes.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** conditional by existing variant: none, translation; case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 232, 250. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 1 distinct required key references; examples `collections.resolutions_other.name`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** fixed: 13, captured_fit: 2. Centered; logo offsets 0; text offsets 0; logo widths 1600, 1800. Captured binding **E**. |
| Logos / source assets | **C:** roots `logos_resolution`, `transparent.png`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 10 exact base-color values; gradient 1; white_wash true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `resolution`, `resolution/standards`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; no generator families; 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Resolution icons, standards subdirectory and captioned other cases; preserve icon widths and two captured sizes. Measured variable composer fields: `base_color`, `font_size`, `logo`, `logo_resize`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `gradient`, `logo_offset`, `text_offset`, `white_wash`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Seasonal

Source: [seasonal.yml](../bulk/catalog/seasonal.yml). **23 declared → 23 concrete; 23 public.** Translated seasonal/event captions and artwork, brand/event colors and white-wash variants.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** required on every existing variant; case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 184, 211, 223, 224, 250. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 22 distinct required key references; examples `key_names.4/20`, `key_names.ASIAN_AMERICAN_PACIFIC_ISLANDER_HERITAGE_MONTH`, `key_names.BLACK_HISTORY_MONTH`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** captured_fit: 23. Centered; logo offsets -500; text offsets 850; logo widths 1800. Captured binding **E**. |
| Logos / source assets | **C:** roots `logos_seasonal`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 20 exact base-color values; gradient 1; white_wash false, true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `seasonal`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; no generator families; 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Translated seasonal/event captions and artwork, brand/event colors and white-wash variants. Measured variable composer fields: `base_color`, `font_size`, `logo`, `white_wash`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `gradient`, `logo_offset`, `logo_resize`, `text_offset`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Separators

Source: [separators.yml](../bulk/catalog/separators.yml). **35 declared → 749 concrete; 749 public.** 34 bounded named-color families plus collectionless root output; historical source templates and a no-gradient variant are intentional.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** required on every existing variant; case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 193, 195, 203. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 36 distinct required key references; examples `collections.COLLECTIONLESS.name`, `collections.separator.name`, `key_names.ACTOR`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** fixed: 1, captured_fit: 748. Centered; logo offsets -500, 0; text offsets 0, 850; logo widths 1500, 2000. Captured binding **E**. |
| Logos / source assets | **C:** roots `@base`, `logos_chart`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 749 exact base-color values; gradient 0, 1; white_wash false, true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `(root)`, `separators/amethyst`, `separators/aqua`, `separators/blue`, `separators/forest`, `separators/fuchsia`, `separators/gold`, `separators/gray`, `separators/green`, `separators/navy`, `separators/ocean`, `separators/olive`, `separators/orchid`, `separators/orig`, `separators/pink`, `separators/plum`, `separators/purple`, `separators/red`, `separators/rust`, `separators/salmon`, `separators/sand`, `separators/stb`, `separators/tan`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; separator-variants (34 families); 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** 34 bounded named-color families plus collectionless root output; historical source templates and a no-gradient variant are intentional. Measured variable composer fields: `base_color`, `font_size`, `gradient`, `logo`, `logo_offset`, `logo_resize`, `text_offset`, `white_wash`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Streaming

Source: [streaming.yml](../bulk/catalog/streaming.yml). **256 declared → 256 concrete; 256 public.** Color/white branding, captionless base plus movies/originals/shows variants; white_wash false intentionally preserves source colors.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** conditional by existing variant: none, translation; case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 250. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 3 distinct required key references; examples `key_names.MOVIES`, `key_names.ORIGINALS`, `key_names.SHOWS`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** fixed: 256. Centered; logo offsets -500, 0; text offsets 0, 850; logo widths 1000, 1400, 1600. Captured binding **E**. |
| Logos / source assets | **C:** roots `logos_streaming`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 31 exact base-color values; gradient 1; white_wash false; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `streaming/color`, `streaming/white`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; no generator families; 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Color/white branding, captionless base plus movies/originals/shows variants; white_wash false intentionally preserves source colors. Measured variable composer fields: `base_color`, `logo`, `logo_offset`, `logo_resize`, `text_offset`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `font_size`, `gradient`, `white_wash`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Studio

Source: [studio.yml](../bulk/catalog/studio.yml). **488 declared → 488 concrete; 488 public.** Studio logos with translated other/animation-other cases, variable logo sizes and exact punctuation such as A.C.G.T..jpg.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** conditional by existing variant: none, translation; case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 250. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 2 distinct required key references; examples `collections.studio_animation_other.name`, `collections.studio_other.name`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** fixed: 486, captured_fit: 2. Centered; logo offsets 0; text offsets 0; logo widths 1000, 1200, 1500, 1600. Captured binding **E**. |
| Logos / source assets | **C:** roots `logos_studio`, `transparent.png`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 486 exact base-color values; gradient 1; white_wash false, true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `studio`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; no generator families; 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Studio logos with translated other/animation-other cases, variable logo sizes and exact punctuation such as A.C.G.T..jpg. Measured variable composer fields: `avg_color_image`, `base_color`, `logo`, `logo_resize`, `white_wash`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `font_size`, `gradient`, `logo_offset`, `text_offset`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## SubtitleLanguage

Source: [subtitlelanguage.yml](../bulk/catalog/subtitlelanguage.yml). **188 declared → 188 concrete; 188 public.** Text-only language captions on the shared transparent placeholder, with optional subtitle-language template; parallel style to AudioLanguage but distinct key/destination family.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** required on every existing variant; case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 188, 221, 228, 238, 241, 245, 250. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 189 distinct required key references; examples `collections.subtitle_language.name`, `collections.subtitle_language_other.name`, `key_names.ABKHAZIAN`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** captured_fit: 188. Centered; logo offsets 0; text offsets 0; logo widths 1600, 2000. Captured binding **E**. |
| Logos / source assets | **C:** roots `transparent.png`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 188 exact base-color values; gradient 1; white_wash true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `subtitle_language`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; no generator families; 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Text-only language captions on the shared transparent placeholder, with optional subtitle-language template; parallel style to AudioLanguage but distinct key/destination family. Measured variable composer fields: `base_color`, `font_size`, `logo_resize`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `gradient`, `logo_offset`, `text_offset`, `white_wash`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Universe

Source: [universe.yml](../bulk/catalog/universe.yml). **20 declared → 20 concrete; 20 public.** Captionless universe branding with intentional logo width and wash variants.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** composer caption absent on every existing variant (propose prohibited unless a named design variant is approved); case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 250. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 0 distinct required key references; none. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** fixed: 20. Centered; logo offsets 0; text offsets 0; logo widths 1500, 1800. Captured binding **E**. |
| Logos / source assets | **C:** roots `logos_universe`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 20 exact base-color values; gradient 1; white_wash false, true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `universe`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; no generator families; 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Captionless universe branding with intentional logo width and wash variants. Measured variable composer fields: `base_color`, `logo`, `logo_resize`, `white_wash`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `font_size`, `gradient`, `logo_offset`, `text_offset`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## VideoFormat

Source: [videoformat.yml](../bulk/catalog/videoformat.yml). **6 declared → 6 concrete; 6 public.** Captionless format logos; no white wash, intentional logo widths and six background colors.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** composer caption absent on every existing variant (propose prohibited unless a named design variant is approved); case upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** `Comfortaa-Medium.ttf` (weight 500). Sizes: 250. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 0 distinct required key references; none. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** fixed: 6. Centered; logo offsets 0; text offsets 0; logo widths 1600, 1800. Captured binding **E**. |
| Logos / source assets | **C:** roots `logos_video_format`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 6 exact base-color values; gradient 1; white_wash false; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `video_format`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; no generator families; 0 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Captionless format logos; no white wash, intentional logo widths and six background colors. Measured variable composer fields: `base_color`, `logo`, `logo_resize`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `font_size`, `gradient`, `logo_offset`, `text_offset`, `white_wash`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Year

Source: [year.yml](../bulk/catalog/year.yml). **152 declared → 301 concrete; 301 public.** Era-specific fonts/styles and literal years; best-of children consume generated year posters. Explicit bounded years do not follow the current clock.

| Property | Measured rule / classification |
| --- | --- |
| Caption requirement / casing | **C:** conditional by existing variant: shared, translation; case exact, upper. Composer text must remain empty until caption resolution (**E**). |
| Fonts / weight / size | **C/I:** 16 era/default fonts; see font table and exact era assignments in source (weights 400/500/700). Sizes: 200, 250, 300, 340, 341, 342, 393, 398, 400, 409, 414, 418, 421, 425, 426, 439, 453, 500. Global hash whitelist **E**, category-specific permission **U**. |
| Translation / language | **C/I:** 2 distinct required key references; examples `collections.year_other.name`, `key_names.BEST_OF`. English declared; other languages follow shared applicability rules above. |
| Layout / fitting / alignment | **C/I:** captured_fit: 291, fixed: 10. Centered; logo offsets 0; text offsets -400, 0; logo widths 1600, 1800, 2000. Captured binding **E**. |
| Logos / source assets | **C:** roots `defaults-en`, `transparent.png`; exact per-definition source and generated-parent references in YAML. Shared fades/transparent and font inputs are fingerprinted (**E**). |
| Background / effects | **C/I:** 12 exact base-color values; gradient 1; white_wash false, true; border false; font color #FFFFFF. avg_color false / dom_color false. Exact assignments are source data, not a free-choice palette. |
| Dimensions / format / naming / case | **E:** shared JPEG contract and collision/portable-path guards above; literal source/output names retained, independent display names. |
| Directories / destinations | **C:** `year`, `year/best`. Local root `defaults-en`; public paths explicitly `remote_paths.en`. |
| Profile / generators / dependencies | **I:** `legacy-poster`; best-of-years (1 families); 150 concrete records have generated-poster dependencies. Actual source/font/translation/fade hashes also form inputs (**E**). |
| Intentional per-poster content | **C/X:** Era-specific fonts/styles and literal years; best-of children consume generated year posters. Explicit bounded years do not follow the current clock. Measured variable composer fields: `base_color`, `font`, `font_size`, `logo`, `logo_resize`, `text_offset`, `white_wash`. Display/ID/key/path variations remain separate. |
| Shared constants / exceptions | **C/I:** effective invariant fields: `avg_color`, `avg_color_image`, `border`, `border_color`, `border_width`, `clean`, `dom_color`, `dom_color_image`, `font_color`, `gradient`, `logo_offset`. Values are measured above or inherited from the profile; historical differences in [exceptions](EXCEPTIONS_REGISTER.md) take precedence over simplification proposals. |
| Proposed submitter fields / design locks | **U — proposal:** identity/display metadata, exact asset with provenance and an approved content/variant selection; existing authoritative translation key. Brand colors only where appropriate to this established variant. Maintain category/variant font, captured fitting policy, geometry, effects, output format and naming/routing under maintainer control; do not expose every YAML field as editable. |
| Actual enforcement | **E:** shared schema/input/font/measurement/path/manifest checks. **C:** category caption/font/layout/color conventions. **U:** submitter roles and versioned category contracts do not yet exist. |

## Overlay catalog

**E:** separate [overlays.py](../bulk/overlays.py) and [overlay_definitions.py](../bulk/overlay_definitions.py) preserve exact authoritative PNG basename in both size destinations, fit including upscale with half-up rounding and Lanczos, optional exact top-left RGBA-background trim, sRGB/RGBA PNG at compression 9. The bounding boxes are maxima, not fixed padded canvases: standard 285 × 85; bigger 440 × 100. No composed caption, font, translation, poster gradient or border applies. Embedded source lettering/colors/alpha remain artwork. Generic caption edits are inapplicable.

**C/I:** catalog groups below specify assets, trimming and exact destination hierarchy. Proposed submitter content is source PNG/provenance and an approved group; dimensions/encoding/trim policy/destinations and basename preservation should be locked. There is no submitter role contract today (**U**). White groups and untrimmed groups are intentional variants (**X**); do not flatten. Category E checks are in [planner.py](../bulk/planner.py), [operator workflow tests](../bulk/tests/test_operator_workflow.py) and [overlay review tests](../bulk/tests/test_overlay_review.py).

| Group | Sources | Outputs (both sizes) | Trim | Standard destination | Bigger destination |
| --- | ---: | ---: | --- | --- | --- |
| `aspect` | 8 | 16 | false | `aspect/overlays/standard` | `aspect/overlays/bigger` |
| `content_rating` | 98 | 196 | false | `content_rating/overlays/standard` | `content_rating/overlays/bigger` |
| `genre` | 272 | 544 | false | `genre/overlays/standard` | `genre/overlays/bigger` |
| `seasonal` | 21 | 42 | false | `seasonal/overlays/standard` | `seasonal/overlays/bigger` |
| `studio` | 486 | 972 | false | `studio/overlays/standard` | `studio/overlays/bigger` |
| `video_format` | 6 | 12 | false | `video_format/overlays/standard` | `video_format/overlays/bigger` |
| `award` | 16 | 32 | true | `award/overlays/standard` | `award/overlays/bigger` |
| `chart` | 33 | 66 | true | `chart/overlays/standard` | `chart/overlays/bigger` |
| `chart/white` | 33 | 66 | true | `chart/white/overlays/standard` | `chart/white/overlays/bigger` |
| `country` | 300 | 600 | true | `country/overlays/standard` | `country/overlays/bigger` |
| `franchise` | 118 | 236 | true | `franchise/overlays/standard` | `franchise/overlays/bigger` |
| `network` | 282 | 564 | true | `network/overlays/standard` | `network/overlays/bigger` |
| `network/white` | 282 | 564 | true | `network/white/overlays/standard` | `network/white/overlays/bigger` |
| `playlist` | 9 | 18 | true | `playlist/overlays/standard` | `playlist/overlays/bigger` |
| `resolution` | 13 | 26 | true | `resolution/overlays/standard` | `resolution/overlays/bigger` |
| `streaming` | 32 | 64 | true | `streaming/overlays/standard` | `streaming/overlays/bigger` |
| `streaming/white` | 32 | 64 | true | `streaming/white/overlays/standard` | `streaming/white/overlays/bigger` |
| `universe` | 20 | 40 | true | `universe/overlays/standard` | `universe/overlays/bigger` |

No exact, casefold/NFC collision or decomposed-NFC name was found in the 4,122 overlay destinations. The same basename appearing in different size/group directories is intentional, not a path collision. English posters use `.jpg`, overlays `.png`; the complete generated public path sets cannot collide with each other.

## Bundled font metadata

These 17 files are the fonts referenced across the expanded poster catalog. Weight is OS/2 `usWeightClass`; family/subfamily come from the font tables. Exact approval hashes and licenses are in [approved-fonts.json](../bulk/baselines/approved-fonts.json) and [licenses](../fonts/licenses). Default Comfortaa Medium and Press Start 2P have weight 500 even though their legacy subfamily says Regular.

| File | Family | Subfamily | Weight |
| --- | --- | --- | ---: |
| `fonts/Barlow-Regular.ttf` | Barlow | Regular | 400 |
| `fonts/BebasNeue-Regular.ttf` | Bebas Neue | Regular | 400 |
| `fonts/BoecklinsUniverse.ttf` | Boecklins Universe | Regular | 400 |
| `fonts/Boogaloo-Regular.ttf` | Boogaloo | Regular | 400 |
| `fonts/CherryCreamSoda-Regular.ttf` | Cherry Cream Soda | Regular | 400 |
| `fonts/Comfortaa-Medium.ttf` | Comfortaa Medium | Regular | 500 |
| `fonts/Jura-Bold.ttf` | Jura | Bold | 700 |
| `fonts/Limelight-Regular.ttf` | Limelight | Regular | 400 |
| `fonts/Monoton-Regular.ttf` | Monoton | Regular | 400 |
| `fonts/PlusJakartaSans-Bold.ttf` | Plus Jakarta Sans | Bold | 700 |
| `fonts/Press-Start-2P.ttf` | Press Start 2P | Regular | 500 |
| `fonts/Righteous-Regular.ttf` | Righteous | Regular | 400 |
| `fonts/Rye-Regular.ttf` | Rye | Regular | 400 |
| `fonts/SpecialElite-Regular.ttf` | Special Elite | Regular | 400 |
| `fonts/Trochut-Regular.ttf` | Trochut | Regular | 400 |
| `fonts/UnifrakturCook-Bold.ttf` | UnifrakturCook | Bold | 700 |
| `fonts/Yesteryear-Regular.ttf` | Yesteryear | Regular | 400 |

## Playlist exact identity and asset inventory

Every row shares the observed geometry/font/caption described in [discovery](PHASE1_DISCOVERY.md#playlist-all-nine-definitions-and-source-assets). Output stem is exactly its display name, `Brand (Timeline Order)`. Remote destination is `playlist/<display name>.jpg`; local is `defaults-en/playlist/<display name>.jpg`. No slug is substituted.

| Display name | Persisted ID | Source filename under logos_playlist | Source dimensions | Base color |
| --- | --- | --- | --- | --- |
| Arrowverse (Timeline Order) | `playlist.playlist-arrowverse-timeline-order.09b7e4b8` | `Arrowverse.png` | 1592 × 328 | `#2B8F40` |
| DC Animated Universe (Timeline Order) | `playlist.playlist-dc-animated-universe-timeline-order.66af9f87` | `dca.png` | 1136 × 352 | `#2832C4` |
| Dragon Ball (Timeline Order) | `playlist.playlist-dragon-ball-timeline-order.24c7063f` | `DragonBall.png` | 7336 × 2785 | `#E39D30` |
| Marvel Cinematic Universe (Timeline Order) | `playlist.playlist-marvel-cinematic-universe-timeline-order.d704757c` | `Marvel Cinematic Universe.png` | 1595 × 766 | `#AD2B2B` |
| Pokémon (Timeline Order) | `playlist.playlist-pok-mon-timeline-order.efe5925f` | `Pokémon.png` | 1597 × 583 | `#FECA06` |
| Star Trek (Timeline Order) | `playlist.playlist-star-trek-timeline-order.53320ead` | `Star Trek.png` | 1597 × 889 | `#0193DD` |
| Star Wars The Clone Wars (Timeline Order) | `playlist.playlist-star-wars-the-clone-wars-timeline-order.c6750e0c` | `Star Wars The Clone Wars.png` | 1377 × 832 | `#ED1C24` |
| Star Wars (Timeline Order) | `playlist.playlist-star-wars-timeline-order.0af9472c` | `Star Wars.png` | 1596 × 762 | `#F8C60A` |
| X-Men (Timeline Order) | `playlist.playlist-x-men-timeline-order.627ce505` | `X-men.png` | 1587 × 971 | `#636363` |

Source byte hashes (PNG metadata and direct visual inspection, no transformation):

| Source | SHA-256 |
| --- | --- |
| `Arrowverse.png` | `256787f4761e845b3a626ab2c23b943eb626ce0d006a98a92a16ded4fac01f8b` |
| `dca.png` | `94fba21cefc046ea0a4c4d813a0f376f8a9d85e9ca8441e7fc8eee651f066132` |
| `DragonBall.png` | `52f4b15178c1cce8e8c1aae9ba73e8683fa88123936b2487bd5d2b5cb0a8c799` |
| `Marvel Cinematic Universe.png` | `75b0a1f58deca7a02ab0ebf15997da40d7554d82aa643e647f2d8495af4e82e8` |
| `Pokémon.png` | `fc03b941138c112254d545e39be14d6c1f507a02c529b488a029ce1e420ecbde` |
| `Star Trek.png` | `8a84de6dc3c0e5a5d6002f136b1b7fa496de929cba3b8035b32c92da13b2f2df` |
| `Star Wars The Clone Wars.png` | `10e14d9cf5fdc3f63d06dde6690a89a0a8ae216d004e87729a09bcb793a62ebe` |
| `Star Wars.png` | `ed6408d3e9134ef2c528e164ef204feb05148edc54f60abc98cbadfbd39d7cea` |
| `X-men.png` | `f57574eeefecafbb435ac45cd8b350e51cb8303a78a83f1cdb623e9a8d2191b4` |

## Translation scope measurements

Verified GET-only snapshot: repository `Kometa-Team/Translations`, commit `a7bddf45d0fb2cc37c794af05d5fb807880c9a80`, tree `93e6e9d51c26b5c4903adc059f92e4f848f0f2dd`; canonical registry SHA-256 `4f3e741b5d252addfbb4c1a4ed3c7eadf231b5aa3636afa9d2b833816c05ed1b`. Fourteen Git blobs were downloaded and independently content/Git-blob/size verified. The head was unchanged after the read. Every caption and template key from the complete expanded catalog was enumerated: **960 distinct referenced keys**. This is key/value completeness, not a render, glyph, applicability or layout approval.

| Language | Present nonempty referenced keys | Missing/error keys | Empty values |
| --- | ---: | ---: | ---: |
| `ar` | 41 | 472 | 447 |
| `bg` | 943 | 17 | 0 |
| `da` | 905 | 55 | 0 |
| `de` | 960 | 0 | 0 |
| `en` | 960 | 0 | 0 |
| `es` | 960 | 0 | 0 |
| `fr` | 960 | 0 | 0 |
| `hu` | 941 | 19 | 0 |
| `it` | 901 | 59 | 0 |
| `nb_NO` | 285 | 472 | 203 |
| `nl` | 157 | 472 | 331 |
| `pt-br` | 242 | 472 | 246 |
| `ru` | 162 | 798 | 0 |
| `sv` | 892 | 68 | 0 |

Each row sums to 960. **English has zero missing/empty keys; all 960 referenced values match the frozen English fixture exactly.** No current input change is necessary or made. Values may be present but unusable for a language/font/layout, and an English-identical value may be legitimate; completeness does not establish translation quality. Unreferenced catalog keys were not tested as generator requirements.

Playlist key checks against this pinned English resource: `key_names.TIMELINE_ORDER` = `Timeline Order`; `key_names.RELEASE_ORDER` and `key_names.WATCH_ORDER` are absent (`missing_translation`). No key or poster was added. The [authoritative pinned resource](https://github.com/Kometa-Team/Translations/blob/a7bddf45d0fb2cc37c794af05d5fb807880c9a80/defaults/en.yml) and source YAML make these findings reproducible.

## Filename and identity measurements

| Domain | Entries | Exact duplicate paths/IDs | NFC+casefold collisions | Non-NFC names | Non-ASCII entries |
| --- | ---: | ---: | ---: | ---: | ---: |
| id | 9957 | 0 | 0 | 0 | 0 |
| local | 9957 | 0 | 0 | 0 | 36 |
| remote | 9955 | 0 | 0 | 0 | 36 |
| assets | 2192 | 0 | 0 | 0 | 26 |

The `assets` row is the **deduplicated composer logo-reference set**, including generated parent references; it is not a count of physical PNGs, all dependencies or overlay inputs. Local path assembly joins nonempty directory components, including root `collectionless.jpg`. Shared source reuse is intentional and excluded from duplicate-output checks. Overlay path checks are reported separately above. Source PNG case corrections and the independent `Action & adventure` → public `Action & Adventure` mapping are documented in the exceptions register.

No current collision explains away the identity gap: generated children still derive IDs from output paths. Future name/path changes need explicit persistent identity and destination decisions. Source case remains exact even on Windows.
