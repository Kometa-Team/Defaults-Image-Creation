# Package D: Gate Evidence

Status: implementation and final verification in progress. Gate D is not yet
claimed ready. Draft PR #12 remains unmerged and Package E remains unauthorized.

Started from the clean remote branch at approved checkpoint
`fe55011c2cf94a7e3a8213a82735fff13d18c415`; PR #12 was open/draft against `main`
with successful Package C Linux CI. No later remote commits were overwritten.

## Implemented Scope

- Dynamic, safe language identifiers and immutable, schema-validated snapshots.
  Explicit read-only Git discovery verifies the complete `defaults/*.yml`
  inventory and exact blob/size/SHA-256 identities; warm/offline caches revalidate
  bytes. Historical exact `nb_NO` and `pt-br` destinations remain unchanged.
- Mandatory shared preflight for single/category/catalog generation and preview.
  Strict, partial, audit and review selection remain distinct. Reports retain
  missing keys, invalid values/templates, unavailable resources, applicability,
  font/glyph/RTL/layout diagnostics and exact affected logical/variant identities.
- Exact existing-composer shaping/wrapping/FreeType measurements without full
  poster rasterization. Translated fitting requires explicit, versioned,
  caption/font-bound proposals; English pixels are not changed to accommodate
  translations. Proposals never activate definitions or rewrite source YAML.
- Indexed single-poster catalog loading, scoped generated dependencies, exact
  variant translation deltas and fallback-key indexing. Asset/font/layout/policy
  fingerprints invalidate relevant review records at explicit re-preflight.
- D01 registry integration, historical-color distinction, logical assignment
  collision checks and explicit related/exception handling. Existing reservation
  and authorized override APIs remain transactional; previews never recolor.
- Versioned overlay catalog: 36 operations, 18 groups, two sizes, 2,061 distinct
  PNG inputs and 4,122 transforms. Actual Pillow transforms use the existing
  bounded persistent spawn workers, owned claims, atomic outputs and receipts.
- SQLite migration 7 adds immutable review revisions/batches, current state and
  indexed translation dependencies. Individual/group decisions retain versions,
  exact image/input/policy fingerprints, warnings, comments and real inspection
  scope. Blocked/private/stale/changed outputs cannot be approved; high-risk
  transforms and prior rejections/stale items require individual review.
- Shared CLI/API services and readable local HTML previews. The CI workflow
  retains a focused review artifact, not a production image publication.

## Observed Source Integration

Read-only Translations commit `a7bddf45d0fb2cc37c794af05d5fb807880c9a80`, tree
`93e6e9d51c26b5c4903adc059f92e4f848f0f2dd`, has 14 poster YAML resources:
`ar, bg, da, de, en, es, fr, hu, it, nb_NO, nl, pt-br, ru, sv`.
Registry SHA-256 is
`4f3e741b5d252addfbb4c1a4ed3c7eadf231b5aa3636afa9d2b833816c05ed1b`.
The original eleven are no longer a permanent maximum. No repository clone or
translation write is required. Complete all-resource preflight coverage and
deduplicated contributor report measurements will be recorded after the active
read-only audit finishes; no full poster batch is being rendered.

The repository README directs contributions to
[Kometa Weblate](https://translations.kometa.wiki/). Anonymous browsing redirects
to sign-in and public component/key mappings were not verifiable. Reports use
that verified landing link and explicitly mark direct-key navigation unavailable.
Display names remain null where no authoritative mapping was verified.

## Arabic Font Evaluation

Isolated candidate: original `NotoSansArabic[wdth,wght].ttf` from
[Google Fonts](https://github.com/google/fonts/tree/main/ofl/notosansarabic),
upstream [Noto Arabic](https://github.com/notofonts/arabic).

- Font Git blob: `f1d01edce4ebaedcbe9a06fc75fec07b304ec3df`.
- Font SHA-256: `63111b5b2e074dd48cc67692e0a2726d86ee94c1c37fe8598257b7b4e87e869e`.
- License Git blob: `14c589f6384505ede3f8e52627d397513af3662d`.
- License SHA-256: `07fc70bfeb985cc1a87a8587d0a0c80bab11c86c9dc3fd95b6f0cb332f983e96`.

The original SIL OFL 1.1 notice identifies copyright 2022 The Noto Project
Authors. Five native compositor probes exercised joining, combining marks,
Arabic/Latin/numbers, punctuation and centered bounded captions. The shaped
sequences differ from isolated characters and all probe glyphs are covered.
This is not comprehensive Arabic acceptance or font approval. The candidate
is not installed into the approved production font set; RTL variants remain
explicitly blocked pending font, language-specific layout and visual acceptance.
No OS font fallback is used. Local probes: `config/package-d/cache/arabic-evaluation/`.

## Rendering Evidence

Initial 38-overlay sample covered all 18 groups and both sizes: two spawn
workers, 20.694 seconds, 38 executed, zero failures/retries; repeat 1.371 seconds,
38 verified cache hits, zero worker starts. These are small Windows observations
with other checks running, not production-versus-legacy performance claims.

Four preserved Phase 1 ImageMagick references retain exact source/output hashes.
Dimensions match. Raw RGB MAE ranges 12.88-50.95, alpha MAE 0.82-3.23; the raw
RGBA maximum remains 255. Black-composited RGB MAE is 0.81-3.23 and white-
composited MAE 0.038-0.134. Both raw and visible-composite metrics are retained;
hidden RGB differences do not justify claiming exact pixel parity. No accepted
threshold was changed. Overlay differences require explicit visual review.
Local comparison: `config/package-d/cache/overlay-review/index.html`.

The offline CI proof uses the original composer for one English and one French
preview, records a missing Arabic resource as blocked, renders two overlays and
creates five review records with zero approvals/publications. The French layout
is an explicit unapproved proposal. It is not a production-language readiness
claim. Human-readable preview artifacts are retained by CI for team inspection.

## Validation Status

| Check | Current Result |
| --- | --- |
| Phase 1 composer/font/workflow regressions | 120 passed locally |
| Package A | 35 passed locally |
| People Posters compatibility | 129 passed; one account-permission symlink skip |
| Historical Phase 1 fixture | Passed exact reconstructed-source validation |
| Corrected current fixture | Passed: 9,958 frozen calls / 3,352 literals |
| Package B/C/D tests | Final combined run in progress |
| Focused Package D tests | 43 passed before final integration refinements |
| Linux CI at Package D head | Pending scoped commit/push |
| Compile and whitespace checks | Final pass pending |

An intermediate regression caught the legacy non-executable overlay contract
being rejected; executable PNG contracts are now checked separately without
weakening the old test. Adding the read-only pinned artifact action required
extending the workflow-boundary assertion: it now also checks the exact action
SHA, retention and restricted artifact paths, and still forbids renderer CLIs,
write permissions and publication commands. No visual thresholds were weakened.

## Limits and Decisions

1. Most non-English captured-fit captions still need explicit language fitting
   evidence/approval. Missing or partial upstream translations remain blocked;
   discovery never implies complete coverage. No unsupported script is forced
   through an English font/layout.
2. Arabic font and RTL/mixed-bidi/anchor acceptance remain maintainer decisions.
   The OFL candidate has not been silently approved.
3. Pillow/ImageMagick overlay differences remain visible review evidence, not
   accepted parity by assumption. Broader reconciliation and soak belong to E.
4. Weblate direct-key/component verification requires authenticated access not
   available in the approved anonymous check; trustworthy landing links remain.
5. Precise invalidation requires explicit refresh/delta or scoped preflight after
   external edits. No filesystem watcher or deployed approval service exists.
6. CLI reviewer identity is development attribution only. Production review
   authorization, Flask, publishing and deployment are not implemented.
7. No full 9,957-contract production rendering, all-language acceptance/soak,
   detailed legacy throughput benchmark or cutover recommendation is claimed.

All production PowerShell, the validated Pillow composer, original fonts,
historical fixtures and previous rendered evidence remain untouched. Default-
Images and upstream translation systems have not been modified. Final head/CI,
complete audit counts and Gate D matrix will replace the pending entries before
the final maintainer handoff.
