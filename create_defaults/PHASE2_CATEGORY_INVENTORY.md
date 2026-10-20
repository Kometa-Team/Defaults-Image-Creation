# Phase 2 Current-Source Inventory

Gate A and D01-D08 are approved. Package B is authorized and implemented locally;
the audit counts below remain historical observations, not a Package C migration.
B supplies four representative definitions, preserves all historical colors and
keeps the retired green Splatter traceable. No full batch has been rendered.

Package A audit, 2026-10-16, source commit
`57ef136833a3f54da2bf1e4ddef98addfa36d583` (`main`). All paths below are relative
to `create_defaults/`. Numbers are observations, not permanent assertions about
future content. Detailed, searchable evidence:

- [Current source audit](phase2/evidence/current-source-audit.json): source/font
  hashes, category parameters, asset inventory, overlay expansion and output anomalies.
- [Parser-only source structure](phase2/evidence/source-structure.json): all
  function spans, 41 aliases, All dispatch, exact languages and every translation
  call expression/line. No source script is executed by this inspector.
- [Historical colors](phase2/evidence/historical-colors.json): every explicit
  literal background, generated/direct assignments, duplicate groups and source references.
- [Four real capture examples](phase2/evidence/sample-manifest.json), with complete
  effective composer options, asset hashes, source lineage and output mapping.

## Coverage and Source Lineage

Fresh allowlisted AST capture recorded **3,352 literal rows, all covered; 9,958
poster jobs; 21 poster categories; 17 active fonts; 165 generated-input jobs**.
Overlays are separate: 36 glob transformations, 2,061 unique matching source PNGs,
4,122 file transformations across the two sizes. No new full-image parity run is
claimed in Package A. Fitting used 2,062 hash-bound local requests.

Current normalized bulk-source SHA-256:
`56302000b4fddbba5468694b9cdb19eddcb28b1e2ac86433c11e4ca74a638bf7`.
Fresh manifest fingerprint:
`968476aff980f2cbb3e0d5b870360450c723150f34f5751af9aef6dee19643ac`.
Its complete capture remains ignored under `config/phase2-package-a-20261016/`;
no full rendering dataset has been added to Git.

Comparing material job fields against the immutable Phase 1 cmap-compatible
manifest finds exactly one changed job, index 6945: **Death in Paradise (2911)
becomes Death in Paradise (2011)**. Only the output-name field changed; the logo
already used `Death in Paradise (2011).png` and remains unchanged. Source row and final
path change together. The new schema example uses only 2011. Renderer and font
changes have not been introduced here. Phase 1's 9,255 passes/703 visually accepted
warnings describe its historical source, not a fresh validation of this correction.

## Category Coverage

Source lines identify `Create<Category>` functions. Common font C is
`fonts/Comfortaa-Medium.ttf`; P is `fonts/BebasNeue-Regular.ttf`; N is the sixteen
numeric/decade fonts listed below. Most functions fit translated uppercase
captions; blank keys deliberately produce no caption, not missing translations.
Outputs are within `defaults-<language>/` locally, with the listed relative contract.

| Category / source line | Aliases (case-insensitive) | Literal rows | Jobs | Effective outputs / source logic |
| --- | --- | ---: | ---: | --- |
| Aspect / 818 | Aspect | 9 | 9 | `aspect/`; translated Other plus eight `logos_aspect/` ratios; C. |
| AudioLanguage / 883 | AudioLanguage, AudioLanguages | 188 | 188 | `audio_language/`; transparent text posters, translated Other and language name substituted into collection template; C. |
| Awards / 1127 | Award, Awards | 148 | 4,847 | `award/<award>/`, winner/nomination/best and director variants; year loops and special one-offs; `logos_award/`; C. |
| Based / 2768 | Based | 4 | 4 | `based/`; translated captions on transparent source; C. |
| Chart / 2815 | Chart, Charts | 591 | 1,182 | `chart/color/`, `chart/white/`; table processed twice with ordinary/white logos; `logos_chart/`; C. |
| ContentRating / 3458 | ContentRating, ContentRatings | 46 | 72 | `content_rating/` plus au/cs/de/mal/nz/uk/us; generated ages 1-18 and NR, MAL rating strings, table-based national logos; C. |
| Country / 3682 | Country, Countries | 608 | 608 | `country/color/`, `country/white/`; separate tables, translated collection Other and country key names; `logos_country/`; C. |
| Decade / 4381 | Decade, Decades | 16 | 31 | `decade/`, `decade/best/`; Other + 15 numeric decades 1880-2020 + 15 derived BEST OF parents; N/C. |
| Franchise / 4481 | Franchise, Franchises | 118 | 118 | `franchise/`; predominantly captionless logo posters; preserve 2011 correction; `logos_franchise/`; C. |
| Genre / 4632 | Genre, Genres | 276 | 276 | Current legacy capture includes both Splatter rows; approved D02 selects red line 4884 and retires green line 4883 from future active Python jobs. `genre/`; collection Other plus translated genre rows; `logos_genre/`; C. |
| Network / 4963 | Network, Networks | 286 | 568 | `network/color/`, `network/white/`; common rows processed twice plus collection-specific rows; `logos_network/`; C. |
| Playlist / 5337 | Playlist, Playlists | 9 | 9 | `playlist/`; timeline-order translation, exact reviewed Bebas Neue, fit box 1600x1000/max 154; `logos_playlist/`; P. |
| Resolution / 5384 | Resolution, Resolutions | 15 | 15 | `resolution/`, `resolution/standards/`; collection defaults plus logo/text standards; `logos_resolution/`; C. |
| Seasonal / 5493 | Seasonal, Seasonals | 23 | 23 | `seasonal/`; translated/blank captions and reviewed per-row styling; `logos_seasonal/`; C. |
| Separators / 5553 | Separator, Separators | 34 | 749 | `separators/<22 bases>/` plus root `collectionless.jpg`; template substitution, 34x22 background assets plus one direct Plex poster; C. |
| Streaming / 5632 | Streaming | 128 | 256 | `streaming/color/`, `streaming/white/`; common table processed twice; ordinary/white `logos_streaming/`; C. |
| Studio / 5808 | Studio, Studios | 488 | 488 | `studio/`; translated Other plus captionless/logo-specific rows; inactive malformed sample field noted below; `logos_studio/`; C. |
| SubtitleLanguage / 6350 | SubtitleLanguage, SubtitleLanguages | 188 | 188 | `subtitle_language/`; same template mechanism as AudioLanguage but separate collection key; C. |
| Universe / 6631 | Universe, Universes | 20 | 20 | `universe/`; translated keys where present; `logos_universe/`; C. |
| VideoFormat / 6593 | VideoFormat, VideoFormats | 6 | 6 | `video_format/`; captionless/translated format rows; `logos_video_format/`; C. |
| Year / 6683 | Year, Years | 151 | 301 | `year/`, `year/best/`; Other + years 1880-2029 + 150 derived BEST OF parents; N/C. |
| Overlays / 6921 | Overlay, Overlays | separate | 36 operations | PNG transformations, not poster jobs; see overlay section. |

`All` dispatches every category in the table order, then Overlays. Although
VideoFormat is declared before Universe, dispatch runs Universe first. The
legacy no-category path calls ShowFunctions; do not turn no arguments into an
implicit expensive All run. Repeated/multiple category arguments must be deduped
by the new planner without losing requested order/dependencies.

## Dynamic Rules and Compatibility Traps

- Awards expand different year ranges per award and translated winner/nomination/
  best-director prefixes. Retain original literal row lineage alongside mutated
  effective rows and loop year. Do not infer all awards from one uniform range.
  `2016-2` and `1930-2` have invocations without a final virtual path: follow the
  complete queue/move history before declaring them orphan jobs or deleting them.
- Decade/Year BEST OF jobs consume their generated numeric parent images, not a
  shared source logo. Preserve the dependency DAG and parent image hashes. There
  are 15 + 150 such jobs, and the overlay engine is not part of this DAG by default.
- Numeric fonts: Barlow, BoecklinsUniverse, Boogaloo, CherryCreamSoda, Comfortaa,
  Jura, Limelight, Monoton, Plus Jakarta Sans Bold, Press Start 2P, Righteous,
  Rye, Special Elite, Trochut, UnifrakturCook Bold and Yesteryear. Playlist adds
  Bebas Neue as the seventeenth active font. Full byte hashes/family metadata are
  in the audit. Do not substitute host-installed faces. Jakarta 2020s/2020-2029
  remains **fixed 409**, not a 381-point automatic fit. Monoton's approved font
  and the existing cmap compatibility behavior remain unchanged.
- Raw numeric arguments may exceed the composer's range and reset to 250. Keep
  both raw and effective values in compatibility evidence; do not silently
  reinterpret a fitting cap as final valid size. Preserve the one audited
  wildcard fitting caption `MIND-F**K` behavior and legacy `+-500` offset handling.
- Separators use 22 actual `@base/*.png` assets: amethyst, aqua, blue, forest,
  fuchsia, gold, gray, green, navy, ocean, olive, orchid, orig, pink, plum, purple,
  red, rust, salmon, sand, stb, tan. All 748 table-derived jobs have blank/random
  underlying base color, gradient 0, logo resize 2000 and fit box 1900x1000/max 203.
  Capture freezes random draws for comparison; these draws are not historical
  approved colors. A new plan must persist any chosen draw for reproducibility.
- Root collectionless is a separate direct invocation at 5566, Plex logo resize
  1500, logo offset -500, text offset 850, font 195, explicit `#DC9924`, gradient 1,
  white-wash true. It must not disappear when migrating the table-based separators.
- Splatter lines 4883/4884 share logo, translation and output, but differ in
  `#416939`/white-wash true vs `#990000`/false. Production queues them concurrently.
  The virtual table's apparent last winner is not a certified production winner.
  **D02 is now APPROVED / RESOLVED:** the maintainer selected red line 4884 as
  authoritative and retired unintended green line 4883 from new active Python
  definitions. Retain both source identities in the audit; do not edit the legacy
  source. See the decision and count reconciliation below.
- Font dominant-color flags are legacy no-ops; do not enable extraction in this
  migration. Average-color inputs only matter if their effect is active and not
  overridden by explicit background. Studio line 5841 supplies `#D19068` in the
  inactive `avg_color_image` field as well as the valid background field. Record
  that oddity, but do not report it as a missing active source logo or repair it silently.

## D02 Splatter Migration Audit

**Status: APPROVED / RESOLVED by explicit maintainer decision.** This supplements
the unchanged source-capture evidence; it does not rewrite historical behavior
or claim that a Python Genre generator has already been implemented.

Source: `create_defaults/create_default_posters.ps1`, audited commit
`57ef136833a3f54da2bf1e4ddef98addfa36d583`.

| Field | Authoritative red definition | Retired green definition |
| --- | --- | --- |
| Source line | 4884 | 4883 |
| Audit identity | `legacy-row-4884` | `legacy-row-4883` |
| Source key / logo | `SPLATTER` / `Splatter.png` | `SPLATTER` / `Splatter.png` |
| Background | `#990000` | `#416939` |
| White-wash | `0` (disabled) | `1` (enabled) |
| Historical output target | `genre/Splatter.jpg` | `genre/Splatter.jpg` |
| Package C disposition | Exactly one active job per applicable selected language | Retired audit record only; no active job |
| Canonical source-row SHA-256 | `8bcb2829b0a97f6bf4f2128f823d897e8e5598c02bdfc344ad3c2011c4172aa0` | `dfe1647bfcc9280f73712a32ef0235dca741f6d96a8569649eda33c9b691e18f` |

Original definitions, preserved verbatim as source-line audit evidence (green
line 4883 first, authoritative red line 4884 second):

```text
        'SPLATTER| Splatter.png| -500| 1800| +850| ComfortAa-Medium| | #FFFFFF| 0| 15| #FFFFFF| | Splatter| #416939| 1| 1| 0| 1',
        'SPLATTER| Splatter.png| -500| 1800| +850| ComfortAa-Medium| | #FFFFFF| 0| 15| #FFFFFF| | Splatter| #990000| 1| 1| 0| 0',
```

The active Python definition must retain the red row's effective behavior:
`logos_genre/Splatter.png`, uppercase translation from `key_names.SPLATTER`,
logo offset -500/resize 1800, caption offset +850, exact bundled Comfortaa Medium
and existing fitting behavior, white text/border color, border disabled/width 15,
gradient 1, clean enabled, average color disabled, and white-wash disabled. The
output remains `genre/Splatter.jpg`; no renamed or alternate green output is approved.

Count reconciliation for Package C, **projected, not a new execution result**:
with the same audited English All selection and no other changes, removing only
the retired green invocation reduces Genre from **276 to 275 active jobs** and
the total from **9,958 to 9,957 active jobs**. The legacy source still contains
3,352 literal rows and both original Splatter definitions. Historical captures,
color usage, rendering results and the 276/9,958 baseline must remain intact.
The manifest comparison must list line 4883 as an approved D02 retirement with
delta -1, retain line 4884, and reject any additional unexplained differences.
There is still exactly one required Splatter output path, not one fewer required
unique poster. Measure actual new counts for every selection/language; do not
apply an English estimate blindly to other scopes.

This is not permission to tolerate conflicting active definitions. Future
manifest generation must reject duplicate output targets before rendering,
including case/NFC equivalents. The existing Package A collision prototype/test
continues to reject both rows if both are incorrectly presented as active.

## Historical Background Colors

The registry contains **3,318 explicit literal background assignments, 1,798
distinct HEX values, 603 globally repeated HEX groups and 416 within-category
repeated groups**. The 34 blank Separator rows are separate from these totals.
Seven additional producer groups cover explicit generated/direct assignments:
CS ages/NR `#1AA931`, MAL ratings/NR `#2444D1`, Decade/Year BEST OF `#FFFFFF`, and
direct root collectionless `#DC9924`. They are not random/template draws and are
listed separately to avoid confusing job expansion with literal assignments.

Examples explaining why duplicated colors are not automatically defects:

| HEX | Observed pattern | D01 treatment; relationships still require explicit links |
| --- | --- | --- |
| `#002BE7` | 31 Chart rows + 4 Streaming rows | Preserve all historical uses; cross-category exact reuse is informational. New unrelated Chart/Streaming posters still see their own category's occupied HEX. |
| `#002CA1` | 31 Chart rows | Preserve historical duplicates; future shared collection use needs an explicit relationship, not inferred intent. |
| `#00303E` | 4 Streaming rows | Preserve historical uses; explicit related-variant links permit intentional reuse without warnings. |
| `#0049F8` | AudioLanguage and SubtitleLanguage | Exact cross-category reuse is allowed and informational, even without a relationship. |
| `#00BFFF` | 2 Country rows | Preserve both; identify logical owners and explicit color/white variant links rather than counting every output as an independent assignment. |
| `#FFFFFF` | Explicit BEST OF generated bases | Preserve template behavior and record generated/inherited relationships; do not recolor or convert template provenance into blanket unrelated reuse permission. |

Each assignment includes exact source HEX, category, output display name, source
line, row fingerprint, effective use count and related-variant linkage. Audit
IDs such as `legacy-row-4681` are **source coordinates, not future stable IDs**.
No duplicate has been declared intentional or converted into an approved named
exception by this audit. **D01 is now APPROVED / RESOLVED:** preserve these
historical assignments, reserve their category/HEX occupancy against new unrelated
posters, allow cross-category exact reuse informationally and explicit related
reuse without warnings, warn rather than block on perceptual similarity, and
require audited authorized overrides for otherwise prohibited exact duplicates.
The raw JSON remains historical evidence with its original unreviewed-intent
labels and counts; policy preservation is not retroactive approval of intent.
Text, border, logo pixels, gradients and frozen random colors were not counted
as literal background assignments.

Map historical rows to stable logical assignments during Package B/C without
collapsing their source lineage or reserving once per rendered language/output.
Keep independent, inherited and template assignments distinguishable. D02's
retired green Splatter remains historical-only; its color record/reservation is
not silently removed. The authoritative registry's policy records, named
exceptions and reservation protocol are specified in the
[D01 color registry specification](PHASE2_ARCHITECTURE.md#color-registry-specification-d01).
This documentation update changes no source color, audit JSON or rendered result.

## Assets and Output Paths

The current `logos_*` and `@base` inventory contains **2,083 files**, all PNG,
with no case/NFC collisions, unexpected extensions or unassigned files after
including both poster and overlay consumption. This does not prove future
assets are assigned, nor that every asset needs a poster. It is source discovery
evidence only, not a complete decoded-image/alpha validation.

Folder counts: @base 22; aspect 8; award 16; chart 66; content_rating 98; country
300; franchise 118; genre 272; network 564; playlist 9; resolution 13; seasonal
21; streaming 64; studio 486; universe 20; video_format 6. Counts include nested
white-logo folders. Shared inputs also include transparent.png, five fades and
the seventeen fonts; generated numeric poster inputs are tracked separately.
There are no missing active asset inputs; `#D19068` is the one inactive oddity.

The virtual final poster inventory has **9,955 distinct paths** from 9,958 jobs.
Three jobs lack a final virtual target: the two award special invocations and
the first Splatter row. The green Splatter invocation now has an explicit D02
retirement for the future Python generator; it must still appear in comparison
accounting as an approved removal. No disposition change is approved for the two
award invocations. Same-queue collision evidence remains unchanged for the legacy
source, even though D02 resolves which Splatter style will be active in Python.
Copied `logos/`, separator `@base/`, list files and overlays are auxiliary output
contracts, not extra poster rendering jobs. Preserve their path mapping explicitly.

English remote paths in the sample use existing category-relative paths. The
local parent is `defaults-en/`; source `main` is not destination `master`.
For non-English artwork the exact destination namespace must be confirmed
against a complete remote tree before claiming publication compatibility. Keep
unconfirmed remote paths unknown, not guessed from local folder names. No
remote artwork was downloaded, cloned, or modified by this audit.

## Languages and Translation Semantics

Parser-confirmed selectors, in order: **ar, en, da, de, es, fr, it, nb_NO, nl,
pt-br, sv**. Default en. Do not normalize nb_NO to nb-NO or pt-br to pt_BR.
Only English is locally available in `@translations/`; the checked-in English
fixture remains a hash-bound offline fallback for audit. Ten missing local
translation files are not ten validated languages.

`Get-YamlPropertyValue` (453) walks dot-separated keys through PowerShell
hashtables. Key lookup is case-insensitive in the actual captured representation;
`Exact/Upper/Lower` controls the returned **value**, not key matching. Preserve
the distinction and detect casefold-ambiguous keys. Missing keys return and log
`TRANSLATION NOT FOUND`; approved D03 instead blocks missing keys by default and
permits only explicit reviewed fallbacks with provenance. Package B implements this.
`Set-TextBetweenDelimiters` (492) uses a non-greedy `<<.*?>>` regular expression,
including replacement semantics, not a single literal placeholder substitution.
Test multiple placeholders, dollar/backslash replacement cases, newlines and
case transformations against the legacy helper before runtime adoption.

Dependencies include `collections.<key>.name` for Other, `key_names.<key>` for
normal labels, `collections.audio_language.name`,
`collections.subtitle_language.name`, `collections.separator.name`,
`collections.COLLECTIONLESS.name`, age/RATED/NOT_RATED and BEST_OF prefixes.
The source-structure JSON records every call expression and exact source line,
including award prefixes, rather than pretending all captions use key_names.

None of the seventeen active bundled fonts covers Arabic. Cairo-Regular is a
comment, not an available/approved fallback. Arabic must remain selectable but
unrenderable captions must block preflight until font/applicability decisions
and shaping/RTL tests are supplied. Shared logos/no-caption artwork need a
separate explicit shared-text/applicability classification, not invented translations.

## Overlay Contract

Twelve trim groups: award, chart, chart/white, country, franchise, network,
network/white, playlist, resolution, streaming, streaming/white, universe.
Six no-trim groups: aspect, content_rating, genre, seasonal, studio, video_format.
Each group produces standard box **285x85** and bigger box **440x100**:
18 groups x 2 = 36 transformations, expanded to 4,122 actual file transforms.

Output is `<group>/overlays/<standard|bigger>/<source filename>.png`.
Resize preserves aspect ratio; these are bounding boxes, not guaranteed exact
output dimensions, and upscaling is not disabled. Legacy order is sRGB conversion,
metadata strip, optional trim, resize. Trim is ImageMagick's background-sensitive
trim, including opaque corners; substituting alpha-only bounding boxes is not
automatically equivalent. Palette transparency, premultiplied-alpha resampling,
empty/solid images, color profiles and page offsets need explicit D tests.
Do not assume the Pillow poster resize filter proves overlay equivalence.
