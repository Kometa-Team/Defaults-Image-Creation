# Package E - end-to-end acceptance and production readiness

**Gate E: approved by the maintainer for the recorded scope at `83ed3d1`. English canary preparation authorized; execution and production cutover are not authorized.**

The maintainer formally approved Gates A-D and authorized Package E from
`166a007c00f14b166a97be8887a4532ea42078b8` on draft PR
[#12](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/12).
Earlier reports, fixtures, original Package D/E audits and the four exact Package D sample decisions remain immutable. The multilingual addendum supersedes the English-matching fitting rule; original multilingual counts below are historical evidence.
No artwork or translation was published; no production PowerShell was replaced,
production permissions granted, PR merged or ready transition performed.

**Automated Package E acceptance is complete for the recorded scope.** Gate E is approved for the recorded scope at `83ed3d1`; English canary preparation only is authorized. Publication, deployment and cutover are not authorized. The maintainer has accepted 64 exact overlay previews and six exact language poster/layout previews and resolved the public destination case; all other artwork/font/layout decisions remain pending. Historical validation identities below describe the measured pre-mapping checkpoint; the destination-only correction requires fresh production preflight and does not change renderer inputs. The corrected multilingual audit makes 41,417 variants newly technically eligible; 14,899 retain final needs_layout_review status. All 9,957 English validation identities were unchanged by the multilingual correction at that audit checkpoint. The later public destination mapping changes that one poster definition/preflight identity while preserving its render fingerprint. Technical eligibility grants no artwork approval.

## Gate E approval and authorized next scope

The maintainer explicitly approved Gate E on draft PR #12 at full commit
`83ed3d1b11576f8e258aed08a3ae7ff13bf4791c`. The
[approval record](bulk/evidence/package-e/gate-e-approval-20261017.json) binds the
accepted validation scope and original evidence identities; the separate
[audit events](bulk/evidence/package-e/gate-e-approval-20261017-events.json) preserve
that decision without rewriting any prior review record. This accepts 9,957 English
outputs/parity, technical verification of 4,122 overlays, the 64 inspected overlay
samples, six inspected translated previews, corrected multilingual reporting and
the exact `genre/Action & Adventure.jpg` public mapping. It grants no blanket
visual acceptance. Only English canary preparation, read-only comparison,
documentation and pushing preparation/CI to the existing draft PR are authorized.
Canary execution, publishing credentials, production writes, PowerShell replacement,
PR merge/ready transition and further phases remain unauthorized.

## Maintainer decisions recorded on 2026-10-17

The maintainer explicitly reports inspection and acceptance of the presented
64-sample checkerboard overlay page and all six linked language poster previews.
The [exact acceptance record](bulk/evidence/package-e/maintainer-visual-acceptance-20261017.json)
binds each decision to image/source hashes, renderer, font/layout, receipt,
validation and policy identities. The [portable audit events](bulk/evidence/package-e/maintainer-visual-acceptance-20261017-events.json)
retain the new decisions separately from the original pending/audit evidence.

| Decision | Accepted scope | Remaining boundary |
| --- | --- | --- |
| Overlays | All 64 exact presented previews; the maintainer accepts the documented Pillow/ImageMagick differences for those samples, including ICC-corrected transparency. Existing review service records 64 individual approvals with exact accepted warning codes and a fully inspected batch. | Other transforms among the 4,122 remain unapproved. No new global pixel threshold or performance/adoption decision. |
| Language poster/layout previews | French Based Book, Comic, True Story and Video Game; German Based Book; Bulgarian Based Book. Exact presented images and proposed layouts accepted. | These six use their recorded historical preflight policy. Acceptance is recorded with `review_external_sample_acceptance`; no automatic current-policy approval transfer, catalog activation or wider language approval. |
| Public destination | `genre/Action & Adventure.jpg` is the mandatory exact case and spelling. The English catalog remote mapping now uses this path. | Internal render filename and source logo retain their captured names. No published file was renamed or uploaded. |
| Production | Gate E validation scope approved at `83ed3d1`; English-only canary preparation authorized. | Execution, credentials, publishing, merge, deployment and subsequent phases remain pending. |

Original `pending-overlay-review.json`, fitting records and pixel metrics remain
unchanged historical observations. Statements of zero approvals, empty inspected
subsets and pending decisions in the original audit sections below describe their
original checkpoints; this later decision record supersedes sample status only.
The six layout acceptances do not activate proposals or resolve the remaining
14,899 audited `needs_layout_review` variants. Arabic and all other unreviewed
multilingual artwork remain pending. The 64 current overlay approvals apply only
to the recorded Windows renderer context and exact bytes; no platform transfer.

Verification: all 21 existing category/captured-contract reconciliation cases pass.
The two focused audit/destination regressions pass, including exact current preflight
and planner destination case and an unchanged render fingerprint for the mapping.

## Tested source and environment

Original full-run executable checkpoint: `690d1977b207cbbb61371a0fcb8bd02e37db85d2`, branch
`feat/default-posters-python-generator`. The English orchestration started at
`6bb5844b4ebe1ea8b681c826105a008a8f673ede`; environment snapshots record the head
observed when each command completed. Later changes affect overlay ICC conversion,
overlay acceptance duration, tests and reporting; English rendering, planning,
preflight, worker execution and catalog inputs remained unchanged for those original runs. The multilingual addendum was implemented in an isolated checkout while the original English run retained its exact source and receipts. Corrected typography has its own versioned evidence; it is not retroactively applied to the original audit. Source-file hashes
in the evidence distinguish executable identity from a later documentation commit.

Windows 11 uses Python 3.13.15, eight logical CPUs and 32 GiB physical RAM. Linux CI
uses Ubuntu 24.04 and Python 3.13.16. The patched isolated Windows environment uses
Pillow 12.3.0, fonttools 4.60.2, uharfbuzz 0.56.3 and python-bidi 0.6.11. Other direct
pins and native-library versions are recorded in
[dependency evidence](bulk/evidence/package-e/dependencies.json). Exact bundled
fonts are selected by verified paths/hashes, with no OS fallback.

The final English workload uses four explicitly selected persistent spawn workers,
512 MiB per worker, a 4 GiB sampled process-tree ceiling, 8 GiB free-disk floor,
16 GiB final-output ceiling and three-hour limit per cold/warm phase. Each phase
uses at most 15,000 jobs and recycles workers after 200 jobs. Overlay phases use
4,122 finite contracts, a 5,000-job cap, 2 GiB output ceiling, the same disk/memory
floors and an explicit 45-minute phase limit. The latter was revised from 30 minutes
after observed full-inventory throughput; no unbounded benchmark is introduced.
Reproducible commands and retained-evidence prerequisites are in
[Package E usage](PACKAGE_E_USAGE.md). Resource sampling is advisory between checks; worker limits and finite selections
provide separate bounds. All outputs, SQLite state and temporary work stay in
ignored local `config/package-e/` roots, separate from source and production.

The translated-fitting correction is introduced at executable checkpoint
`916ded8c8e0114900924e2e4585be67dd9bf9da7`. The current validation record separates
the complete Windows run at `d00403422b584f53013e60821f8964b4cc8c0ae9`, strengthened
regressions and Linux validation at `18b2b7645c24e688110ec7eb336bf22f8bf43e76`,
and later audit/documentation commits. The original full English/API/published
pipeline remained frozen throughout. All 9,957 English validation identities and
the 35-JPEG/38-overlay platform samples demonstrate unchanged English rendering.
No image-producing composer, bundled font, catalog or production PowerShell was
changed by the fitting correction.

## Complete source reconciliation

The authoritative corrected-current-source capture SHA-256 is
`968476aff980f2cbb3e0d5b870360450c723150f34f5751af9aef6dee19643ac`.
All 21 categories reconcile against its 9,958 jobs. Approved D02 retires only the
unintended green Splatter duplicate, leaving **9,957 rendering contracts**, **9,955
public destinations** and **two private Awards intermediates**. Red `#990000`
Splatter and Death in Paradise `(2011)` are retained. There are no unexplained
contract changes or duplicate destinations.

| Category | Active contracts | Contract parity |
| --- | --- | --- |
| Aspect | 9 | Passed |
| AudioLanguage | 188 | Passed |
| Awards | 4847 | Passed |
| Based | 4 | Passed |
| Chart | 1182 | Passed |
| ContentRating | 72 | Passed |
| Country | 608 | Passed |
| Decade | 31 | Passed |
| Franchise | 118 | Passed |
| Genre | 275 | Passed |
| Network | 568 | Passed |
| Playlist | 9 | Passed |
| Resolution | 15 | Passed |
| Seasonal | 23 | Passed |
| Separators | 749 | Passed |
| Streaming | 256 | Passed |
| Studio | 488 | Passed |
| SubtitleLanguage | 188 | Passed |
| Universe | 20 | Passed |
| VideoFormat | 6 | Passed |
| Year | 301 | Passed |

Private paths `defaults-en/_intermediates/award/choice/2016-2.jpg` and
`defaults-en/_intermediates/award/oscars/1930-2.jpg` have null remote destinations.
The parity ledger checks logical/source identity, source logo hashes, bundled fonts,
color, caption/translation parameters, fitting/effects/position, generated parents,
paths and private status. Generated dependencies must bind real verified parent
bytes before final render planning; baseline contract parity does not substitute
invented parent hashes. See [reconciliation evidence](bulk/evidence/package-e/catalog-reconciliation.json).

English preflight reports 3,022 ready, 4,285 with warnings and 2,650 shared; none are
blocked. All 9,957 retain historical color provenance. Existing diagnostics include
4,010 wrapped captions, 1,421 near-edge cases and one clipping warning:
`defaults-en/collectionless.jpg`. These are historical appearance diagnostics,
not authorization to change colors or layouts.

## Full English generation and renderer comparison

Recorded full workload:

```json
{
  "runs": {
    "cold": {
      "actual_renders_per_second": 0.9870580979708097,
      "cache_hits": 165,
      "dedup_reuses": 8,
      "executed": 9950,
      "failures": 0,
      "manifest_sha256": "1a28d37c96d8a5fa354b1c471c3d5651e67aeada04564c508e7ff7fcf10b67aa",
      "max_inflight": 4,
      "peak_parent_rss": 388136960,
      "peak_worker_rss": 234967040,
      "peak_workers_rss_sum": 706301952,
      "read_bytes": 42483657524,
      "retry_attempts": 1,
      "status": "verified",
      "stop_reason": null,
      "unique_outputs": 9957,
      "wall_seconds": 10080.46033,
      "worker_recycles": 47,
      "worker_starts": 52,
      "write_bytes": 14613507218
    },
    "warm": {
      "actual_renders_per_second": 0.0,
      "cache_hits": 10122,
      "dedup_reuses": 0,
      "executed": 0,
      "failures": 0,
      "manifest_sha256": "1a28d37c96d8a5fa354b1c471c3d5651e67aeada04564c508e7ff7fcf10b67aa",
      "max_inflight": 0,
      "peak_parent_rss": 561983488,
      "peak_worker_rss": 0,
      "peak_workers_rss_sum": 0,
      "read_bytes": 0,
      "retry_attempts": 0,
      "status": "verified",
      "stop_reason": null,
      "unique_outputs": 9957,
      "wall_seconds": 639.0175643000002,
      "worker_recycles": 0,
      "worker_starts": 0,
      "write_bytes": 0
    }
  },
  "verification": {
    "bytes": 7310915041,
    "decode": "final headers plus exact hashes; full decoding enforced on worker promotion",
    "duplicates": 0,
    "failed": 0,
    "ledger_sha256": "05148b279018db06c4de74b712c47a9b21b69836065f4cc24130e0f2f27b63ad",
    "missing": 0,
    "outputs": 9957,
    "private": 2,
    "publishable": 9955
  }
}
```

Reference comparison:

```json
{
  "classifications": {
    "exact_approved_api_using_current_python_parents": 165,
    "exact_approved_phase1_python_bytes": 9792
  },
  "ledger_sha256": "c14d1572403758668f0d99e522c73ad1bdcba6fea3c965b5ab3d93a1e64c4a6d",
  "new_visual_approvals": 0,
  "outputs": 9957,
  "passed": true,
  "scope": "Exact prior accepted Python byte evidence, with fresh direct approved API comparisons for changed generated-parent inputs. Historical legacy differences retain their classifications.",
  "source_reference_summary": {
    "capture_sha256": "968476aff980f2cbb3e0d5b870360450c723150f34f5751af9aef6dee19643ac",
    "classifications": {
      "Python migration difference": 703,
      "approved font replacement": 18,
      "existing historical artwork difference": 53,
      "expected image-encoding difference": 9179,
      "missing published counterpart": 3,
      "unresolved discrepancy": 1
    },
    "jobs": 9957,
    "ledger_sha256": "63ee0806e1c1af9b796f63478bf379765c30cb6113437701483dc6138989b0ec",
    "reference_final_audit_sha256": "f02557884ffd34acd51b3d8fdf35c93c8c10e2fd49ed13cea8de3d0ce530c3a0",
    "reference_manifest_sha256": "b6b1a9f189ce014ee04d0878c28cfa3cbdac6780f3a6a4b9965741e6cf8f5a6e",
    "scope": "Read-only exact result hashes from previously accepted complete Phase 1 run; D02 green duplicate excluded, two private outputs retained"
  }
}
```

The cold phase verified 9,957 destination artifacts through 9,950 render attempts,
eight deduplicated reuses and 165 parent cache checks. One timed-out attempt was
retried successfully; the final database contains 9,957 verified jobs. Attempt,
deduplication and output counts measure different things and are not summed as
independent outputs. The unchanged warm phase rendered zero and started zero
workers, with 10,122 cache checks including repeated generated-parent verification.
The full [English identity ledger](bulk/evidence/package-e/full-ledger-index.json)
and [English acceptance record](bulk/evidence/package-e/full-english.json) retain
exact manifests, source/font/layout, every receipt/image hash, recovered timeout
events and all per-output approved-API comparisons.

The full comparison requires a complete, validated manifest and matching source,
asset, font and semantic identities for every reference. Its original Phase 1
reference ledger is `63ee0806e1c1af9b796f63478bf379765c30cb6113437701483dc6138989b0ec`.
The 9,792 root outputs are compared against recorded approved Python bytes.
For 165 generated children, the approved original API is called on current,
verified Python parent bytes: old Phase 1 comparisons froze common legacy parent
images, so those old child hashes cannot be used as a silent new tolerance.
Unexpected root differences or fresh child API differences fail the command.

The comparison explicitly permits only approved D08's `(2911)` to `(2011)` output
name/path correction for Death in Paradise, with every other parameter and input
unchanged. D02 remains the red source selection. Historical Phase 1 classifications
(encoding, migration warnings, accepted fonts and missing legacy paths) remain
separate evidence; they are not blanket approval of future differences.

## Read-only published artwork reconciliation

Initial pinned Default-Images/master inventory: commit
`59e49ede8d41ac5991f971e66e93af596402329a`, tree
`e1664efb92db5872db112cf18253910da77355df`. Inventory reconciliation found **9,954
exact published paths**, **two correctly excluded private paths**, **one case
conflict** and **zero absent paths**. Expected `genre/Action & adventure.jpg` maps
to published `genre/Action & Adventure.jpg` (Git blob
`a20f8bbaab0fdae2b5bd339ee680302b05621960`, 833,624 bytes).
This was the historical pre-decision comparison. The maintainer subsequently
required exact `genre/Action & Adventure.jpg`; the catalog now explicitly maps to
that public destination. No remote rename or case-insensitive assumption was applied. Path ledger identity:
`26bbcaf5e4f156baab8925fb31d2948ca4a3512b52ae9cb009a3e47b4502957f`.

Selective comparison results:

| Classification | Images |
| --- | --- |
| approved_D02_red_source_choice_with_preserved_published_difference | 1 |
| explained_current_python_generated_parent_difference_pending_current_visual_review | 1 |
| known_accepted_phase1_difference_exact_reference_bytes | 22 |

9,930 exact published paths remain unexamined at pixel level. New unexplained differences require separate review.

The initial 24-slot budget produced 23 distinct selections because a correction
case was already represented. One generated Year child was added using the same
pinned tree, making 24 distinct comparisons across all 21 categories and the
explicit correction/dependency cases. The source summaries remain retained.
See [published comparison evidence](bulk/evidence/package-e/published-comparison.json).
Known historical classifications and the explained generated-parent difference
grant no new current artwork acceptance.

Remote access is GET-only, repository/host allowlisted, with redirect refusal,
timeouts, bounded requests/rate reserve and verified Git blob caches. No full clone,
upstream write, publication token or translation update is used. The complete
inventory verifies names and identities; it does not imply all published image
bytes were downloaded or pixel-compared. Old green Splatter's retirement does not
authorize deleting artwork outside this task.

## Overlay acceptance and the ICC defect

Inventory reconciliation preserves **36 operations**, **18 groups**, **2 sizes**,
**2,061 source images** and **4,122 transformation contracts**. The controlled legacy
harness runs the original grouped mogrify flags on copied inputs, with no production
bootstrap. This overlay path uses one mogrify operation per group/size, unlike the
poster path's independent PowerShell composer per image.

Expanded comparison exposed a real LA/grayscale ICC defect: converting LA directly
to RGBA through ImageCms lost alpha and misread color. This is not an accepted
Pillow/ImageMagick filtering difference. Header inventory identifies 230 susceptible
LA+ICC sources (460 size variants); it does not claim individual human inspection.
The fix converts color separately (L for LA, RGB for RGB/RGBA/palette inputs), then
restores source alpha before existing trimming/resizing. Five focused regressions
cover synthetic LA/RGB/RGBA white sources and actual white Chart AMC+ / Network #0.
Before correction three failed and two passed; after correction all five pass.
The initial alpha-only prototype also failed the white-color assertion and was
corrected without weakening the test.

A fresh corrected 38-output sample changes exactly four images (the two susceptible
sources at both sizes); the other 34, including both Experimental image bytes,
are unchanged. All dimensions match legacy. Alpha MAE is 0.815663..2.825727 after
correction; the original pre-fix large differences remain historical evidence.
No new visual approvals or acceptance thresholds were created. Both original and
corrected per-image metrics are retained in
[ICC evidence](bulk/evidence/package-e/overlay-icc-defect.json).

A second deterministic risk batch adds 64 transforms across all 18 groups and all
five actual source mode/profile classes (LA with/without ICC, RGBA with/without ICC,
and palette without ICC). All 64 decode as RGBA with visible alpha and match fresh
legacy dimensions. All retain pixel differences: RGB MAE 5.153..51.795 and alpha
MAE 0.699..7.160 (exact per-image values remain authoritative). Across both corrected
batches, the union is 88 distinct transforms, not 102 independent images. These
concurrent-load correctness observations do not replace isolated performance
measurements or grant acceptance. See [risk comparison](bulk/evidence/package-e/overlay-profile-risk.json).
The existing receipt/review service registers these 64 exact previews as
`ready_for_review`, with an empty inspected subset and zero approval events.
[Pending batch identities](bulk/evidence/package-e/pending-overlay-review.json)
link its local review page and exact image/validation versions.

Corrected full overlay run:

```json
{
  "catalog_counts": {
    "groups": 18,
    "operations": 36,
    "transforms": 4122,
    "unique_inputs": 2061
  },
  "catalog_payload_sha256": "7085533956e5b2d6a2f2ad694e17118fb5082168691bb70fe2b13b1d18403e81",
  "failed": 0,
  "full_overlay_catalog": true,
  "groups": 18,
  "jobs": 4122,
  "ledger_sha256": "0de153bc83670b6bc3b7f7fc52d00550f65ae027c93dda73f0b811c1a7058282",
  "missing": 0,
  "new_visual_approvals": 0,
  "runs": {
    "cold": {
      "cache_hit_rate": 0.8396409509946627,
      "cache_hits": 3461,
      "dedup_reuses": 0,
      "executed": 661,
      "failures": 0,
      "jobs_per_second": 7.728982482962483,
      "max_inflight": 4,
      "peak_parent_rss": 103383040,
      "peak_worker_rss": 256274432,
      "peak_workers_rss_sum": 485986304,
      "process_start": "spawn",
      "read_bytes": 539735281,
      "retry_attempts": 0,
      "stop_reason": null,
      "total_seconds": 557.1824715999992,
      "wall_seconds": 533.3172909999994,
      "worker_pids": [
        10872,
        18728,
        11944,
        2532
      ],
      "worker_recycles": 0,
      "worker_starts": 4,
      "write_bytes": 6802149
    },
    "warm": {
      "cache_hit_rate": 1.0,
      "cache_hits": 4122,
      "dedup_reuses": 0,
      "executed": 0,
      "failures": 0,
      "jobs_per_second": 33.086815978712195,
      "max_inflight": 0,
      "peak_parent_rss": 125157376,
      "peak_worker_rss": 0,
      "peak_workers_rss_sum": 0,
      "process_start": "spawn",
      "read_bytes": 0,
      "retry_attempts": 0,
      "stop_reason": null,
      "total_seconds": 141.4221452999991,
      "wall_seconds": 124.58134390000123,
      "worker_pids": [],
      "worker_recycles": 0,
      "worker_starts": 0,
      "write_bytes": 0
    }
  },
  "scope": "Automated transform/PNG/RGBA/cache verification only; Package D accepts exact CI images, not this entire catalog"
}
```

The first attempt stopped at its finite wall-time limit with 3461 verified outputs and 661 pending. Its complete result/resource/log bytes are archived. A single bounded resume reused the exact owned receipts and rendered the remaining 661; unchanged warm verification rendered zero. The displayed `cold` metrics are the resumed phase, not one fresh complete-catalog cold measurement.

| Observed phase | New renders | Cache hits | Seconds | Outcome |
| --- | --- | --- | --- | --- |
| Initial finite attempt | 3461 | 0 | 2710.187 | Time-bound incomplete, retained |
| Single bounded resume | 661 | 3461 | 557.182 | All 4122 verified |
| Unchanged warm | 0 | 4122 | 141.422 | Zero-worker reuse |

The four exact D sample approvals and their image/source/font/layout/validation
identities remain in `bulk/evidence/package-d/maintainer-visual-acceptance-20261017*.json`.
They comprise two Experimental overlays and English/French Based Book samples.
Documented D Pillow-versus-ImageMagick metrics are unchanged. Matching Experimental
bytes do not transfer approval to a changed renderer context, and the ICC fix does
not approve all 4,122 overlays. Remaining overlay transform reviews stay pending.

## Original multilingual audit and fitting - historical evidence

The fresh read-only translation snapshot discovers all 14 resources at commit
`a7bddf45d0fb2cc37c794af05d5fb807880c9a80`, tree
`93e6e9d51c26b5c4903adc059f92e4f848f0f2dd`; registry SHA-256
`4f3e741b5d252addfbb4c1a4ed3c7eadf231b5aa3636afa9d2b833816c05ed1b`.
All **139,398 contracts across 294 category/language scopes** were audited using
patched dependencies in 2,045.443 seconds, with 175,849,472 bytes observed parent
RSS, 2,049 unique source hashes and zero poster renders. No language disappeared;
identifiers such as `nb_NO` and `pt-br` remain exact compatibility identities.

| Language | Ready | Warning | Shared | Blocked | Complete collection readiness |
| --- | --- | --- | --- | --- | --- |
| ar | 1 | 0 | 2650 | 7306 | Historical audit; corrected assessment below |
| bg | 0 | 2852 | 0 | 7105 | Historical audit; corrected assessment below |
| da | 1308 | 17 | 2650 | 5982 | Historical audit; corrected assessment below |
| de | 1455 | 33 | 2650 | 5819 | Historical audit; corrected assessment below |
| en | 3022 | 4285 | 2650 | 0 | English assessment above |
| es | 1422 | 7 | 2650 | 5878 | Historical audit; corrected assessment below |
| fr | 1432 | 1123 | 2650 | 4752 | Historical audit; corrected assessment below |
| hu | 0 | 4088 | 0 | 5869 | Historical audit; corrected assessment below |
| it | 1466 | 14 | 2650 | 5827 | Historical audit; corrected assessment below |
| nb_NO | 52 | 4 | 2650 | 7251 | Historical audit; corrected assessment below |
| nl | 25 | 1 | 2650 | 7281 | Historical audit; corrected assessment below |
| pt-br | 42 | 0 | 2650 | 7265 | Historical audit; corrected assessment below |
| ru | 0 | 2651 | 0 | 7306 | Historical audit; corrected assessment below |
| sv | 463 | 15 | 2650 | 6829 | Historical audit; corrected assessment below |

These are preflight eligibility counts, not human approvals or permission to publish
partial collections. Every non-English full collection has blockers. Arabic's one
ready item is an ASCII caption (`4/20`), not evidence of Arabic production readiness.
Bulgarian/Hungarian/Russian also remain explicitly new-language warnings.

English validation fingerprints match all 9,957 full/category variants and a separate
single Book check, with zero differences. Additional current-snapshot checks cover
single Book and Based-category fingerprints for all 14 languages, plus complete
9,957-contract French and Arabic selections against their 21 category scopes:
all 30 observations have zero differences. A real English/French Book batch in
strict mode renders nothing when French is blocked; partial mode renders exactly
the eligible English output, with no French fallback or new approval. See
[snapshot scope evidence](bulk/evidence/package-e/snapshot-scope-consistency.json). The fresh audit reports 4,131 deduplicated
missing/invalid resource keys linked to 29,429 dependent variants (links can overlap).
Raw audit identity: `529b6d27178b210fb0b7fa58d1994a8996a56d95b8c03d3807213d04c34eaa04`;
deduplicated contributor mapping:
`21bf9b93438be43ffdd30c3d1f26b7ba165a4a74d741dc0696e2757655c70b92`.
Existing detailed D contributor reports are preserved; refreshed JSON/CSV/HTML
reports remain under local `network-translations-patched/cache/`.

Fitting analysis identifies 19,969 exact caption/language/font/native-metric groups,
91,239 members and 8,808 repeated groups. This measures potential native-metric
reuse, not artwork approval groups. Current `review-risk-d1` still requires
individual review for translated captions. A future low-risk group process would
require a separately approved policy, exact member/renderer/font/layout/validation
identities, an explicit inspected subset, preserved individual high-risk exclusions,
immutable decisions and invalidation of changed members. No such policy was enabled.

Six real previews cover all four French Based posters, German Book and Bulgarian
Book. The French Book proposal remains byte-identical to D's reviewed proposal
`dac288b0cd3e0e736e2719ad43023d250686aeb49d017e2989e4fe1488608f8e`.
Matching proposal bytes do not activate it or transfer old acceptance to new runtime
identities. New exact preview image/render/font/layout/policy identities and all
measurements are recorded in [fitting evidence](bulk/evidence/package-e/fitting-proposals.json).
Local review pages are under `config/package-e/language-proposals-final/cache/preview-reports/`.

Noto Sans Arabic remains an isolated, **unapproved** OFL 1.1 candidate. Font Git blob
`f1d01edce4ebaedcbe9a06fc75fec07b304ec3df`, SHA-256
`63111b5b2e074dd48cc67692e0a2726d86ee94c1c37fe8598257b7b4e87e869e`;
license blob `14c589f6384505ede3f8e52627d397513af3662d`, SHA-256
`07fc70bfeb985cc1a87a8587d0a0c80bab11c86c9dc3fd95b6f0cb332f983e96`.
All 57 nonempty pinned Arabic resource strings (39 distinct codepoints) have glyph
coverage. Five fresh joining, mixed Latin/numeric bidi, punctuation, combining-mark
and centered-anchor probes use the existing HarfBuzz/bidi/font-outline path.
Coverage and probe generation do not establish visual acceptance. Font selection,
RTL/mixed-script behavior and layout/anchor review remain pending; no font was
installed in production. See [upstream font provenance](https://github.com/google/fonts/tree/main/ofl/notosansarabic).

## Corrected multilingual audit and independent readiness

This controlled comparison uses the original pinned translation snapshot. Original D/E audit files remain unchanged. Only keys required by active, applicable caption definitions, templates and resolved dependencies count toward completeness. The exact key ledger retains source hashes, English references, logical IDs, categories and variant IDs.

| Language | Unique required | Valid | Missing | Invalid / empty | Key completion % | Identical English (info) | Missing posters / variants | Invalid posters / variants | Impacted union variants |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ar | 960 | 41 | 472 | 447 | 4.2708 | 1 | 2070 / 2070 | 3854 / 3854 | 5872 |
| bg | 960 | 943 | 17 | 0 | 98.2292 | 9 | 34 / 34 | 0 / 0 | 34 |
| da | 960 | 905 | 55 | 0 | 94.2708 | 314 | 275 / 275 | 0 / 0 | 275 |
| de | 960 | 960 | 0 | 0 | 100.0 | 291 | 0 / 0 | 0 / 0 | 0 |
| en | 960 | 960 | 0 | 0 | 100.0 | 0 | 0 / 0 | 0 / 0 | 0 |
| es | 960 | 960 | 0 | 0 | 100.0 | 220 | 0 / 0 | 0 / 0 | 0 |
| fr | 960 | 960 | 0 | 0 | 100.0 | 236 | 0 / 0 | 0 / 0 | 0 |
| hu | 960 | 941 | 19 | 0 | 98.0208 | 216 | 36 / 36 | 0 / 0 | 36 |
| it | 960 | 901 | 59 | 0 | 93.8542 | 277 | 86 / 86 | 0 / 0 | 86 |
| nb_NO | 960 | 285 | 472 | 203 | 29.6875 | 62 | 2070 / 2070 | 1184 / 1184 | 3206 |
| nl | 960 | 157 | 472 | 331 | 16.3542 | 27 | 2070 / 2070 | 3738 / 3738 | 5756 |
| pt-br | 960 | 242 | 472 | 246 | 25.2083 | 45 | 2070 / 2070 | 3290 / 3290 | 5360 |
| ru | 960 | 162 | 798 | 0 | 16.875 | 1 | 5773 / 5773 | 0 / 0 | 5773 |
| sv | 960 | 892 | 68 | 0 | 92.9167 | 266 | 313 / 313 | 0 / 0 | 313 |

Identical values remain valid and informational. The ledger separately tags numeric labels, acronym candidates, identifiable proper-name keys and explicitly approved unchanged values where available. Capitalization and equal character counts do not prove a translation problem. Unrelated resource keys never enter this denominator.

| Language | Old blocked | Current blocked | No caption required | Measured text fits current | Newly eligible | Fits proposal | Final needs_layout_review | Current geometric failures | Missing glyphs | RTL / shaping | Blocked parents |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ar | 7306 | 7306 | 1340 | 3539 | 0 | 0 | 0 | 0 | 0 | 1434 | 0 |
| bg | 7105 | 43 | 1340 | 5881 | 4369 | 2693 | 2693 | 2693 | 9 | 0 | 0 |
| da | 5982 | 275 | 1340 | 6775 | 4140 | 1567 | 1567 | 1567 | 0 | 0 | 0 |
| de | 5819 | 0 | 1340 | 6930 | 4132 | 1687 | 1687 | 1687 | 0 | 0 | 0 |
| en | 0 | 0 | 1340 | 8616 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| es | 5878 | 0 | 1340 | 6771 | 4032 | 1846 | 1846 | 1846 | 0 | 0 | 0 |
| fr | 4752 | 0 | 1340 | 8210 | 4345 | 407 | 407 | 407 | 0 | 0 | 0 |
| hu | 5869 | 36 | 1340 | 7197 | 4449 | 1384 | 1384 | 1384 | 0 | 0 | 0 |
| it | 5827 | 86 | 1340 | 8328 | 5538 | 203 | 203 | 203 | 0 | 0 | 0 |
| nb_NO | 7251 | 3206 | 1340 | 4228 | 2859 | 1317 | 1186 | 1317 | 0 | 0 | 0 |
| nl | 7281 | 5756 | 1340 | 4949 | 1403 | 122 | 122 | 122 | 0 | 0 | 0 |
| pt-br | 7265 | 5360 | 1340 | 4830 | 678 | 1227 | 1227 | 1227 | 0 | 0 | 0 |
| ru | 7306 | 5773 | 1340 | 1593 | 282 | 1251 | 1251 | 1251 | 0 | 0 | 0 |
| sv | 6829 | 313 | 1340 | 6978 | 5190 | 1326 | 1326 | 1326 | 0 | 0 | 0 |

Technical counts overlap and must not be summed. The fit column counts measured text; captionless artwork needs no text measurement and remains included in overall eligibility. A caption can fit while a required value is empty, leaving the variant blocked. Current clipping and a fitting proposal can also describe the same variant. Final needs_layout_review excludes candidates with another blocking error; all proposals were unapproved at that audit checkpoint. The later six-preview sample/layout acceptance above does not activate or bulk-approve this ledger. Glyph/RTL failures prevent a reliable geometric assessment rather than counting as a successful fit. Normal wrapping is informational; four or more rows and margins under 20 pixels remain warnings.

The correction makes 41,417 variants newly technically eligible. 14,899 have final needs_layout_review status. Existing typography is unchanged; smaller-size proposals never enter effective generation definitions automatically. Strict batches stop before rendering, while partial batches exclude these candidates.

| Language | Historical exact D poster samples / different current renderer contexts | Pending individual artwork review | Potential group candidates under current policy | Exact current audit approvals | Stale / rejected / invalidated current approvals |
| --- | --- | --- | --- | --- | --- |
| ar | 0 / 0 | 1309 | 1340 | 0 | 0 / 0 / 0 |
| bg | 0 / 0 | 7219 | 0 | 0 | 0 / 0 / 0 |
| da | 0 / 0 | 6773 | 1340 | 0 | 0 / 0 / 0 |
| de | 0 / 0 | 6928 | 1340 | 0 | 0 / 0 / 0 |
| en | 1 / 1 | 4285 | 5670 | 0 | 0 / 0 / 0 |
| es | 0 / 0 | 6769 | 1340 | 0 | 0 / 0 / 0 |
| fr | 1 / 1 | 8208 | 1340 | 0 | 0 / 0 / 0 |
| hu | 0 / 0 | 8535 | 0 | 0 | 0 / 0 / 0 |
| it | 0 / 0 | 8326 | 1340 | 0 | 0 / 0 / 0 |
| nb_NO | 0 / 0 | 4223 | 1340 | 0 | 0 / 0 / 0 |
| nl | 0 / 0 | 2737 | 1340 | 0 | 0 / 0 / 0 |
| pt-br | 0 / 0 | 2028 | 1340 | 0 | 0 / 0 / 0 |
| ru | 0 / 0 | 2931 | 0 | 0 | 0 / 0 / 0 |
| sv | 0 / 0 | 6976 | 1340 | 0 | 0 / 0 / 0 |

This fresh technical audit rendered no previews and imported no approvals. Pending counts describe technically eligible public variants awaiting exact artwork inspection. No prior D acceptance is transferred. The four historical sample decisions remain bound to their own exact bytes and renderer/font/layout/validation context. Zero stale or invalidated audit approvals reflects the empty isolated review store, not a claim that all historical approvals remain current under new policies.

2 historical overlay sample acceptances are separate from the poster-language table. 4 historical accepted sample contexts differ from the current renderer context. These differences already existed at the Package E dependency/platform/overlay checkpoint; the multilingual correction itself preserves current English and overlay policy/renderer identities. Their original exact decisions remain preserved; no current-runtime acceptance is inferred and no synthetic stale/rejected review event is created.

All 9,957 English validation identities match the original audit exactly. Composer sources, parameters and bundled fonts remain unchanged. The original full English and overlay runs retain their separate source hashes and receipts.

Validated examples using current parameters:

- longer: es / poster.f97fdc940e8feee8d8fe115b; English "OTHER ASPECT RATIOS"; translated "OTRAS RELACIONES DE ASPECTO". Exact validation 6eec28e8d8343de165ac8e3394d90a85143ce1202634c2d94e315667787dfa4f.

- same_length: bg / poster.bf5f77efc9d73b1c101f4118; English "INTERLINGUE AUDIO"; translated "АУДИО НА ОКДЕНТАЛ". Exact validation 64ba91065f9352199d8effa9ac6aa190c146c9e5a6f8b2d227cc77524766390a.

- shorter: hu / poster.6ddbb493f0f53fa58e2724ef; English "OTHER ASPECT RATIOS"; translated "EGYÉB KÉPARÁNYOK". Exact validation e809fc29a47f073b6fb49929c9208fa533f718778e4cccb488cd3e2940fcb47e.

Measurement reuse: 14,508 distinct groups, 74,209 members and 6,399 repeated groups. The controlled 512-measurement microbenchmark took 0.867 seconds cold and 0.156 seconds warm. Cold includes font loading. These are native in-process measurement timings, rather than a whole-render speedup. Audit cache counters and exact measurement inputs are retained in the evidence.

Cache keys bind exact caption text, font bytes, effective size/offset, compositor renderer and validation-policy version. The compositor derives shaping from Unicode text; identical native inputs can share measurements across languages while variant validations remain language-bound. Caption/font/layout/renderer/policy changes still invalidate the affected review context precisely; ingestion preserves the policy a historical report actually recorded.

Arabic retains its approved-script-font and joining/bidi/anchor review boundary. Missing translations, unsupported glyphs and geometric failures remain constraints. No wording, upstream translation, installed font or catalog typography was changed. A future risk-based process may group exact language/font/layout/template combinations and inspect representatives, but any group acceptance needs an explicit exact-membership decision. Current translated-caption policy requires individual artwork review; representatives never automatically approve uninspected variants.

See [corrected multilingual evidence](bulk/evidence/package-e/multilingual-correction.json) and its compressed key, measurement and variant ledgers. All new technical evidence grants zero artwork approvals or publication permissions.

After the heavy acceptance work completed, three sequential controls used 512 deterministic exact-input measurements across 2 approved fonts. Median cold time was 0.603568 seconds versus 0.009707 seconds warm. Every warm control recorded 512 cache hits and zero new misses. Cold includes font loading; OS caches were not cleared. These controls isolate measurement reuse rather than rendering throughput. See [quiet cache and integrity evidence](bulk/evidence/package-e/multilingual-cache-performance.json). The compact index was independently checked against all 139,398 preserved raw rows and all 74,209 measurement bindings.

## Incremental generation, review integrity and recovery

Package E integration tests compute expected changes before execution for definition,
source logo, approved color, approved alternate font and caption changes; only the
predicted variant rerenders and becomes stale, while unrelated outputs and approvals
remain valid. Separate tests reject changed unapproved font bytes without overwriting
verified output. Newly completed and removed/invalid translations, generated parents,
validation/renderer versions and output-byte changes are covered by B-D integration
and new E regressions. Overlay input changes rerender/stale exactly its two sizes.
A real dependency-version upgrade predicted 73 sample rerenders (35 posters and 38
overlays), with exactly 73 observed, no missing/unexpected jobs and no new approvals.

Individual decisions, rejection/comments, accepted warnings, version-bound group
subsets, individual high-risk requirements, stale decisions, concurrent transactions
and immutable events are exercised in isolated test databases. A concurrent four-item
synthetic group commits once and records only its exact inspected two-item subset;
it never invents individual inspection of the other members. No synthetic approval
is stored as a maintainer artwork decision.

Reliability cases cover worker crash/exception, timeout, RSS threshold, cancellation,
abrupt parent exit, expired lease/restart/resumption, known-failure retry, corrupt
output and SQLite/spec metadata, source mutation, destination mutation before
promotion, duplicate ownership, incomplete parents and token-owned cleanup.
Corruption/unowned destinations fail closed; changing size/mtime back cannot hide
changed bytes. Interrupted work preserves completed outputs and durable receipts.

The first partial full English attempt exposed buffered-success/recycling races:
a worker sent success and exited, but the parent read only one ready pipe and
misclassified another as crashed. The scheduler now drains every ready pipe and
checks buffered final success before exit/timeout classification. A deterministic
four-worker regression failed before correction and passes afterward. Failures
record reason, attempt and PID in the existing immutable event log. Generated-family
selection also now includes every child's required parents while single-child
selection stays narrow; six focused selection/budget cases pass. The comparison
CLI now exits unsuccessfully for unexplained differences.

## Measured performance and warm verification

PowerShell 7.6.7 / ImageMagick 7.1.2-34 reproduce 95 posters in five controlled
sequential batches. The composer source SHA-256 is
`cab86faa4e4ad080c96506f313a03961c3ed3f88e6248a9de325ed0bed25103f`.
The isolated harness removes only bootstrap/self-update/install/banner code,
forces exact copied bundled fonts and redirects private inputs/outputs. Composition,
parameters, fades, JPEG stages, naming and cleanup remain unchanged. Threads are
bounded to one. It does not benchmark the entire original production launcher,
its concurrent orchestration, sleeps or bootstrap.

| Workload | Outputs | Legacy sequential s | Python 1 cold / warm s | Python 2 cold / warm s | Python 4 cold / warm s | Observed legacy / Python 1 |
| --- | --- | --- | --- | --- | --- | --- |
| small | 4 | 18.404 | 8.588 / 1.205 | 8.011 / 1.074 | 7.610 / 1.087 | 2.14x |
| medium | 31 | 131.540 | 55.104 / 5.587 | 32.602 / 5.473 | 21.286 / 5.529 | 2.39x |
| larger | 32 | 178.228 | 44.345 / 3.742 | 28.610 / 2.681 | 27.463 / 2.467 | 4.02x |
| dependencies | 12 | 48.705 | 13.063 / 1.531 | 10.042 / 1.528 | 9.790 / 1.816 | 3.73x |
| mixed | 16 | 66.516 | 18.647 / 1.411 | 16.858 / 1.541 | 14.733 / 1.321 | 3.57x |

Mixed values average two runs per worker count; other workloads have one observation. Medium is all 31 Decades, larger is 32 explicit Chart outputs, dependencies is six Year children plus six parents, small is four Based posters and mixed is 16 explicit contracts.

All 18 poster observations use the actual planner/preflight/persistent renderer;
all hashes match across worker counts/repeats, cold runs have zero retry/failure and
warm runs have zero renders/worker starts. Four workers benefit the medium batch;
small/mixed work shows smaller or inconsistent gains. Recommend **two workers by
default**, with four an explicit measured-capacity choice. Maximum observed single
poster-worker RSS was about 305 MiB; per-observation parent, individual/combined
worker RSS, process starts/recycling, CPU samples, worker read/write bytes and
stage/planning overhead are retained in
[benchmark evidence](bulk/evidence/package-e/poster-benchmarks-and-historical-overlay.json).

Cold means a fresh generator cache, not a cleared OS file cache. Measurements were
sequential controlled subsets; early timings overlapped non-rendering reconciliation.
Worker I/O excludes parent/cache/preflight and includes OS-cache transfers. Legacy
RSS/I/O is sampled. SQLite lock wait was not independently timed; no lock failures
occurred and concurrent correctness is separately tested. No full-catalog speedup
is inferred from subset ratios. Full acceptance runs overlap other validation and
are completion/resource observations, not isolated performance benchmarks.

| Workers | Cold s | Warm s | Actual renders/s | Peak worker MiB | Peak combined workers MiB |
| --- | --- | --- | --- | --- | --- |
| 1 | 17.548 | 1.277 | 2.165 | 173.3 | 173.3 |
| 2 | 13.762 | 1.067 | 2.761 | 173.3 | 344.1 |
| 4 | 13.000 | 2.024 | 2.923 | 104.2 | 283.8 |

Matched fresh legacy control: 10.234 seconds elapsed, 9.784 renderer seconds for 36 grouped mogrify operations / 38 outputs. All Python worker counts match the complete corrected Windows output bytes; warm renders and starts are zero. Measurements are sequential after heavy local acceptance, with fresh generator caches and no OS cache reset. Exact metrics, current source/renderer identities and comparison rows are in [corrected overlay benchmarks](bulk/evidence/package-e/corrected-overlay-benchmarks.json). These observations grant no visual approval or complete-catalog speedup claim.

The measured Python 38-image controls did not beat the grouped legacy control. The Python timings include its planning/integrity/state overhead; no overlay speedup or whole-production throughput claim is made.

Year warm profiling keeps 301 unique outputs, 451 cache checks including repeated
parent-stage verification, 4,726 SHA calls, identical manifest
`c6e06332c32d89e6c68ba81b6cb7aa4b2d7fc7f1d2978eb0b9f11a077feb7e25`, and zero
renders/worker starts. A single profiled pair measured 51.189 -> 35.777 seconds.
Cumulative cached-artifact checks fell 15.348 -> 3.026 seconds; image checks
11.782 -> 0.140; renderer identity 6.821 -> 0.548. SHA time stayed 3.350 -> 3.306.
Nested cumulative times must not be summed. Harness sampling/font-cache variation
limits causal attribution; this is not a universal 30% speedup claim.

Warm reuse still hashes inputs/output bytes, checks exact finalized SQLite receipts
and validates image headers. It avoids full redecoding only for previously verified,
identical bytes; new atomic promotions still fully decode. Loaded library metadata
is immutable within a process; source identities are rechecked and dependency
upgrades require a fresh process. Metadata decoding and repeated package lookup
were reduced; hashing, parent verification, manifest reconstruction, SQLite and path
checks remain. No mtime trust shortcut or weaker durability was introduced.
See [profile evidence](bulk/evidence/package-e/warm-profiling.json).

## Platform tests and CI

| Suite | Windows | Linux current addendum checkpoint |
| --- | --- | --- |
| Phase 1 | 120 passed | 120 passed |
| Package A | 35 passed | 35 passed |
| B-E | 241 passed / 2 skips / 0 failures | 242 passed / 1 skip |
| People | 129 passed / 1 account skip | 129 passed / 1 platform skip |
| Manifest validators / compile | Passed | Passed |
| E smoke | 35 posters + 38 corrected overlays passed | 35 posters + 38 corrected overlays passed |

Current Linux validation totals 526 passed and two platform skips. Original 506-test evidence remains historical. Windows final bulk counts supersede the earlier run and repeated focused cases are not added to that total.

[Current correction Linux CI](https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/39070431355)
passes at executable/test checkpoint `18b2b7645c24e688110ec7eb336bf22f8bf43e76`.
The passing audit/documentation checkpoint is also recorded by
[CI 39071906102](https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/39071906102).
The new regression/platform evidence keeps these versions separate from the original
full-run and historical sample checkpoints.

[Original executable Linux CI - historical checkpoint](https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/39060962332)
is successful at workflow head `690d1977b207cbbb61371a0fcb8bd02e37db85d2`.
GitHub checked out synthetic PR merge `ebf327e65c6f7ff0d7220b2d3a8a18eabdd300b3`;
this differs from the branch head and is recorded explicitly. All 35 sample JPEG
hashes match Windows; six retained JPEGs were independently decoded. All 38 retained
RGBA overlays have identical decoded pixels across platforms and different PNG byte
hashes. Platform-specific renderer identities and exact artifact hashes remain
separate; pixel parity cannot bypass approval binding. See
[platform evidence](bulk/evidence/package-e/windows-linux.json).

People results cover the selected GitHub/workspace/orchestrator regression files,
not the independent People ML/colorization/browser pipeline or a combined dependency
environment. That pipeline has separate requirements and is outside Package E.

Both platforms exercise spawn, reuse/recycling, cancellation, crash recovery,
atomic promotion, SQLite WAL/locking, separators/case/Unicode, font identities,
path mapping and deterministic manifests. Linux skips Windows-junction tests.
The Windows account cannot create ordinary symlinks in two tests; the native
Windows junction safety test passes. These are explicit platform limits, not passes
invented for skipped cases. Both platforms originally replicated the ICC bug;
cross-platform parity alone did not prove correctness, hence independent legacy
comparison and visible-color regression tests.

The first E CI at `e0cf670` passed 492 tests/two skips but failed whitespace on eight
extra trailing blank lines. They were corrected without weakening the gate.
Intermediate `6bb5844` and `bbfa7f1` CI passed (500 and 501 tests respectively).
Four unchanged palette `Image.getdata()` deprecation warnings remain: plan maintenance
before Pillow 14; no palette/color algorithm was changed for this task.
CI retains contents:read, pinned actions and nonpersistent credentials. It runs
35 posters/38 overlays plus focused D samples, never full production generation.
Selected review artifacts expire after 14 days. Full output collections, caches,
SQLite databases and font binaries are not CI/repository payloads.

Current multilingual correction validation is retained separately in
[multilingual validation](bulk/evidence/package-e/multilingual-validation.json):
525 Windows passes with three account skips and 526 Linux passes with two platform
skips. Both manifest checks, compilation and the 35-poster/38-overlay acceptance
smoke pass. The current Windows/Linux sample ledger matches all 35 JPEG hashes
and all 38 decoded overlay pixels; PNG byte streams differ. Original regression
and platform records remain historical evidence. A targeted Git attribute preserves
exact hash-bound Package D observation bytes on Windows checkouts, without changing
its metrics or acceptance. The initial fixture and CRLF failures are retained beside
the passing correction results. No approval is transferred between these contexts.

## Security, dependencies and repository hygiene

Direct-pin advisory screening found Pillow 12.0.0 advisories and fonttools 4.60.1
GHSA-768j-98cg-p3fv. Pins were updated in an isolated trial to 12.3.0 / 4.60.2.
Forty-four real Based/Decade/Playlist outputs covering all 17 font hashes match
fresh original approved API calls byte-for-byte on identical current parents;
ledger `7e392814005b6d4c9ab26aa453787bbeb343b3f6350e494f8db27d0515ac948f`.
A new normalized-name advisory query found no matching entries for the patched
versions. Read-only repository alert reconciliation found 20 open default-branch
alerts (19 Pillow, one fonttools); all current branch pins are outside their listed
vulnerable ranges. Those alerts remain open on main and were not dismissed. The
initial mixed-case Pillow query returned only a subset; normalized queries and
repository records supersede that coverage claim. Several advisory-specific loader,
viewer and font-build paths are outside this bounded PNG/JPEG/verified-font path;
no active exploit is claimed. Windows `pip check` reports no broken installed
requirements in the isolated trial environment. This is direct-pin screening, not a complete
transitive/native SBOM. See [alert reconciliation](bulk/evidence/package-e/dependency-alert-reconciliation.json).
Primary advisories: [Pillow](https://github.com/advisories/GHSA-6r8x-57c9-28j4),
[fonttools](https://github.com/advisories/GHSA-768j-98cg-p3fv).

The runtime uses safe bounded YAML loading with duplicate-key/depth/anchor checks,
registered generators without eval, confined relative paths and Unicode/case
collision checks, reparse/link rejection, bounded image/canvas/resize dimensions,
verified font whitelist and remote blob/request limits. Read-only remote trust uses
Git identities plus exact SHA-256. SQLite uses parameter binding, owned transactions,
WAL, immutable event triggers and exact output claims. Atomic promotion refuses
unowned/corrupt destinations; cleanup requires matching token-owned workspace
identity. No archives, auth service, portal, production credential flow or publication
permission was added. License/font provenance remains explicit and unchanged.

Final complete-PR static inventory:

```json
{
  "pr_base": "57ef136833a3f54da2bf1e4ddef98addfa36d583",
  "files": 232,
  "groups": {
    "implementation tests docs or workflow": 97,
    "compressed immutable manifest fixtures": 1,
    "generated catalog and source-normalized migration audits": 88,
    "compact package audit evidence": 35,
    "compressed Package E exact output and comparison audit ledgers": 7,
    "Package A source and inventory evidence": 4
  },
  "bytes_by_group": {
    "implementation tests docs or workflow": 1014902,
    "compressed immutable manifest fixtures": 1458149,
    "generated catalog and source-normalized migration audits": 13803206,
    "compact package audit evidence": 1116668,
    "compressed Package E exact output and comparison audit ledgers": 28253446,
    "Package A source and inventory evidence": 2133232
  },
  "possible_credentials": [],
  "unexpected_generated_or_binary_payloads": [],
  "protected_changes_since_package_d": [],
  "workflow_permissions": "contents:read; credentials not persisted; local-only bounded smoke artifacts",
  "scope": "Static audit of complete PR scope and Package E additions; no secrets printed. Direct-pin advisory screening is separate; no comprehensive transitive/native SBOM claim."
}
```

Generated YAML/source-normalized inventories and immutable historical fixtures account for most of the PR size. New E evidence contains compact summaries and identities, not image/font/SQLite collections. The credential scan checks common token/private-key patterns; it is not a claim that all possible secret formats can be detected.

Retained aborted runs are not labelled successful. Original-stack full runs stopped
with 1,378 English outputs and 2,760 overlays when patched dependencies were selected.
The later pre-ICC-fix overlay run was deliberately stopped after the defect was
identified; its output/receipt/metric evidence remains. Only validated token-owned
scratch from stopped runs was removed. Earlier reports/fixtures/audits were not
rewritten to remove failures or reduce the PR size.

## Acceptance matrix and remaining decisions

| Acceptance criterion | Classification | Evidence / limitation |
| --- | --- | --- |
| Complete 21-category semantics / 9957 effective contracts | Passed | Zero unexplained contract deviations; two private intermediates excluded. |
| Full English end-to-end cold/warm / receipts | Passed | See exact output/count/hash/receipt evidence. |
| Full approved-API renderer parity | Passed | Exact per-output reference classifications retained. |
| Incremental invalidation / stale approval sets | Passed | Expected-vs-actual scoped tests and real renderer upgrade. |
| Controlled legacy performance / 1,2,4 scaling | Passed with documented limitation | Sequential isolated composer harness; no full production launcher speedup claim. |
| Warm analysis and safe optimization | Passed with documented limitation | Single paired profile; hashing/durability preserved. |
| Windows / Linux compatibility | Passed with documented limitation | Account/platform skips; 35 JPEG/38 PNG sample parity, not full Linux render. |
| Recovery / interruption / corruption / ownership | Passed | Isolated realistic failure scenarios, immutable durable state. |
| Published path inventory | Passed; case decision recorded | Historical conflict preserved; explicit remote mapping now requires `genre/Action & Adventure.jpg`. |
| Selective published-image comparison | Passed with documented limitation | Only explicitly fetched samples; classifications are scoped. |
| Corrected overlay full transform/format/cache verification | Passed with documented limitation | 4122 verified; time-bound attempt plus one resume, exact ledger and zero-render warm check. |
| Broader overlay visual approval | Partial: 64 exact current samples accepted | New inspected-batch/individual audit decisions retained; other transformations pending. |
| Fresh all-language discovery/coverage/strict-partial checks | Passed | 139398 contracts, all 14 resources; no English scope differences. |
| Complete non-English production collections | Blocked | Translation, typography and artwork approval are assessed separately in the corrected matrix. |
| Arabic font / RTL / mixed-script acceptance | Blocked | OFL candidate and probes preserved; no visual/font approval. |
| Fitting proposals / scalable group analysis | Passed with documented limitation | Native translated fitting and review-only proposals; six exact image/layout previews later accepted separately, without activation or current-policy transfer. |
| Review/invalidation integrity | Passed | Exact artifacts/version-bound subsets; synthetic decisions isolated. |
| Historical color preservation / new assignment policy | Passed | 9957 historical colors; uniqueness/concurrency/provenance regression tests. |
| Dependency/license and complete-PR static audit | Passed with documented limitation | Direct-pin advisory screen and source audit; no full transitive/native SBOM. |
| CI / regressions / documentation | Passed | Detailed report, archived evidence and safe CI. |
| Production cutover / publication / rollback execution | Not tested | Not authorized; proposed checklist only. |

Readiness recommendations are scoped:

| Scope | Technical assessment | Remaining decision |
| --- | --- | --- |
| English | All 9,957 outputs/receipts, unchanged warm reuse and exact approved-API parity pass; technically validated migration candidate. | Gate E review, fresh preflight with the resolved exact-case mapping, exact artifact acceptance and separate publication/cutover authority. |
| Overlays | All 4,122 transforms verify; selected corrected outputs reproduce across worker counts. The small Python control did not beat grouped legacy performance. | 64 exact current samples accepted; remaining visual scope and an explicit adoption/performance decision remain pending. |
| German / Spanish / French | All 960 required keys are valid; current fits and pending typography proposals are separately enumerated. | Six presented FR/DE/BG image/layout samples accepted separately; current-policy validation and explicit activation plus all other artwork review remain pending. |
| Arabic / other multilingual | Use each language's independent key/geometry/glyph/RTL assessment; Arabic script-font/RTL acceptance and Bulgarian unsupported glyph cases remain explicit. | Missing-value corrections, approved fonts/layouts where needed, and current artwork review. No complete multilingual collection is automatically production-approved. |

Priority maintainer decisions before any future production operation:

1. Review Gate E's exact evidence and independent readiness recommendations.
2. Enforce the resolved exact public path `genre/Action & Adventure.jpg` in fresh preflight; no published rename is needed.
3. Preserve the new acceptance of 64 exact overlay previews, including corrected ICC samples; review any additional transforms required for the chosen adoption scope.
4. Preserve acceptance of the six presented language image/layout previews; validate their current context and obtain explicit activation scope before changing catalog typography. Other language artwork/proposals and Arabic font/RTL/anchor decisions remain pending.
5. Approve any future low-risk group policy explicitly; no current group inference
   authorizes translated collections or missing content.
6. Separately authorize a cutover plan, publishing authority and rollback ownership.

## Proposed future cutover and rollback checklist - not executed

- Freeze the approved branch commit, dependency/native versions, bundled font hashes,
  source/translation/inventory snapshots, validator and exact review-policy versions.
- Resolve destination case/Unicode mappings explicitly; exclude both private Awards
  intermediates. Verify that the chosen scope is complete, including generated parents.
- Run a fresh isolated strict preflight and bounded full generation, then verify every
  output claim/receipt/hash, destination uniqueness and all required current approvals.
- Record/backup the existing production workflow, PowerShell source and published Git
  head. Preserve prior receipts/audits and test rollback access without writing artwork.
- Obtain separate maintainer authorization for publishing credentials, a finite canary
  scope and actual cutover. Keep unrelated language/style collections out of that scope.
- Under that separate authorization, publish only verified approved artifacts and check
  exact remote identities/counts before expanding; stop on unexplained differences.
- On failure, stop new work, retain evidence, and restore the pinned prior workflow or
  published version under separately authorized rollback. Never delete or overwrite
  unowned work, and do not erase immutable review/history records.

This checklist grants no execution authority. The PR remains draft for final
maintainer review; no future phase begins automatically.
