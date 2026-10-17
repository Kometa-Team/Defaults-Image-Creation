# Package D: Gate Evidence

Status: implementation and read-only integration evidence complete; final
follow-up Linux CI pending. Gate D is not accepted automatically. Draft PR #12
remains unmerged and Package E remains unauthorized.

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
- Migration 8 adds indexed verified artwork reuse across language stages and
  fresh pools. Every required language destination keeps its own receipt/review
  identity. Blocked children do not cause unneeded parent rendering. Approval
  also checks current generation/renderer identity when output bytes match.
- Shared CLI/API services and readable local HTML previews. The CI workflow
  retains a focused review artifact, not a production image publication.

## Observed Source Integration

Read-only Translations commit `a7bddf45d0fb2cc37c794af05d5fb807880c9a80`, tree
`93e6e9d51c26b5c4903adc059f92e4f848f0f2dd`, has 14 poster YAML resources:
`ar, bg, da, de, en, es, fr, hu, it, nb_NO, nl, pt-br, ru, sv`.
Registry SHA-256 is
`4f3e741b5d252addfbb4c1a4ed3c7eadf231b5aa3636afa9d2b833816c05ed1b`.
The original eleven are no longer a permanent maximum. No repository clone or
translation write is required. Measured authenticated cold refresh: 17 GETs,
14 downloads, 7.487 seconds; warm refresh: 3 GETs, zero downloads, 14 verified
cache reuses, 4.621 seconds. All responses were HTTP 200, with zero observed
HTTP errors. Credentials and headers are not retained in evidence.

### Complete Translation Audit

All 294 category/language scopes finished: **139,398 variants**, comprising
10,688 ready, 15,090 ready with warnings, 29,150 shared and 84,470 blocked.
Every language has exactly 9,957 logical contracts. This includes the two
private Awards intermediates per language, not extra publishable images.
Non-English local paths are explicit; unverified remote mappings remain null.

The initial audit took 1,822.825 seconds, sampled peak parent RSS 164,372,480
bytes (156.8 MiB), hashed 2,049 distinct source inputs and rendered zero posters.
This was a read-only audit with other checks running, not a rendering benchmark.
Contributor reports deduplicate 4,131 language/key/reason records and retain
29,429 key-to-variant links. Links overlap when one variant requires multiple
keys; they must not be summed into an additional output/error total.

The audit revealed 38,796 redundant near-color diagnostics on 748 historical
separator-template assignments. The final rule preserves those exact immutable
baseline assignments without treating them as new independent colors or approved
exceptions. No color or similarity threshold changed. All English scopes and
every separator language were rechecked: 34 scopes, 406.187 seconds, all 9,957
historical colors verified. Coverage totals stayed unchanged; redundant color
diagnostics disappeared. One historical English clipping warning is retained
only for its exact baseline caption/font/size/offset identity, not arbitrary
future English changes. Original and corrected audit evidence are both retained.

Original audit SHA-256:
`e55ef96c57ce1e21e112ac86823ca017412fdc9f1aa6cb0d7ef9626517f24c2e`.
Corrected audit SHA-256:
`3b3e3e1e3454eedc90c61c39f4458c036d492095f634008942356b917e6f275a`.
Compact measurements/provenance are checked in under `bulk/evidence/package-d/`;
full JSON, CSV, HTML and affected-ID mappings stay in ignored local evidence:
`config/package-d/cache/contributor-audit-deduplicated/21bf9b93438be43ffdd30c3d1f26b7ba165a4a74d741dc0696e2757655c70b92/`.

English remains entirely eligible: 3,022 ready, 4,285 with documented warnings,
2,650 shared, zero blocked. The principal non-English blockers are 63,688 stale
caption-fitting measurements, missing/invalid translations, 1,434 RTL cases and
nine missing-glyph cases. These diagnostic counts can overlap and are not sums
of independent failures. Arabic has 7,306 blocked, 2,650 shared, and one eligible
ASCII-only `4/20` caption; that is explicitly not Arabic shaping readiness.

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
Authors. The checked-in notice removes trailing whitespace only; the license
hash above identifies the unchanged upstream bytes retained locally. Five
native compositor probes exercised joining, combining marks,
Arabic/Latin/numbers, punctuation and centered bounded captions. The shaped
sequences differ from isolated characters and all probe glyphs are covered.
All 57 nonempty strings in the pinned Arabic YAML (39 distinct codepoints) are
covered by the candidate, with zero missing glyphs. This is a superset-of-keys
coverage check, not comprehensive Arabic visual acceptance or font approval. The candidate
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

The actual first Linux artifact was downloaded read-only and compared with the
Windows smoke output. Both English/French JPEGs are byte-identical. Both overlay
PNGs have identical decoded RGBA pixels but different compressed bytes. Renderer
fingerprints include platform/environment; cross-platform PNG byte parity is
not claimed. No image files, databases, caches or complete audit output are
committed. The focused CI artifact deliberately contains only review images,
reports and proposal metadata, not SQLite state or secrets.

## Validation Status

| Check | Current Result |
| --- | --- |
| Phase 1 composer/font/workflow regressions | 120 passed locally |
| Package A | 35 passed locally |
| People Posters compatibility | 129 passed; one account-permission symlink skip |
| Historical Phase 1 fixture | Passed exact reconstructed-source validation |
| Corrected current fixture | Passed: 9,958 frozen calls / 3,352 literals |
| Package B/C/D tests | 169 passed locally; one permission skip before final guard cases |
| Focused final Package D tests | 55 passed locally |
| First Package D Linux CI | Passed; exact head/run below |
| Final follow-up Linux CI | Pending scoped follow-up commit/push |
| Compile and whitespace checks | Passed locally |

First Package D implementation head:
`1055c86315f7c794724b4eee5b6ed0d0398cce29`.
[Linux run 39005656222](https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/39005656222)
passed on Ubuntu 24.04/Python 3.13.16: Phase 1 120, A 35, B/C/D 163,
People 129: **447 passed, two platform-specific skips**. Both baselines,
compilation and whitespace checks passed. The run also retained the
[focused review artifact](https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/39005656222/artifacts/12091350600).
Final follow-up results will be added before handoff.

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

## Gate D Matrix

| Criterion | Evidence |
| --- | --- |
| Overlay reconciliation and real Pillow processing | 36 operations, 4,122 contracts; 38 real samples, all groups/sizes |
| Dynamic discovery and deterministic snapshot | 14 actual resources; exact Git/size/SHA checks; offline/tamper tests |
| Complete coverage/contributor audit | 139,398 audited; accurate deduplicated IDs/counts; JSON/CSV/HTML |
| Verified contribution links | Verified landing link; direct-key/component access explicitly unavailable |
| Mandatory preflight, strict/partial/audit | Shared engine and CLI; reports retained; language failures isolated |
| Scoped proposals and previews | One-poster index; explicit French fit proposal; no YAML activation |
| Translation delta and precise invalidation | Key/template/fallback/resource indexes; unrelated/shared variants retained |
| Glyph/shaping/Arabic | Native metrics; OFL candidate evaluated; RTL remains blocked/unapproved |
| English compatibility | All 9,957 English contracts eligible; both baselines; byte-identical CI smoke |
| Risk, review and concurrency | Exact versions, warning acceptance, individual high risk, immutable groups/events |
| Stale approvals | Changed inputs, bytes, generation, renderer and policy rejected |
| Resource bounds and reuse | Persistent spawn pools; verified shared reuse across stages/new pools |
| Existing regressions and Linux | First Linux pass; final follow-up run pending |
| Scope restrictions | No production replacement, publication, merge, deployment or E work |

All production PowerShell, the validated Pillow composer, original fonts,
historical fixtures and previous rendered evidence remain untouched. Default-
Images and upstream translation systems have not been modified. Gate D remains
a maintainer decision; font/layout/overlay visual approvals are not fabricated.
