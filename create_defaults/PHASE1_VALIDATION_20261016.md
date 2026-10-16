# Phase 1 Validation: 2026-10-16

## Status

### Completed Approved-Font Run

**Rendering and visual validation complete; merge requires passing PR CI.** All **9,958 effective jobs** are
now paired successfully by both engines: **9,255 passing screens, 703 warnings,
zero failures and zero untested jobs**. All **3,352 literal definitions** are fully
paired, across all 21 categories and all 17 active fonts. This incorporates
6,631 audited unchanged checkpoint pairs and **3,327 freshly rendered pairs**;
the imported pairs are not claimed as new renders.

The 703 flags comprise 101 preserved checkpoint warnings and **602 new warnings**:
590 Separators, six Streaming, two SubtitleLanguage and four Year. Comfortaa has
699 total flags, Monoton three and Special Elite one; every other font has no
bulk warning. Numerical screens are review requests, not 703 confirmed defects.
The user's separate full-run visual approval is recorded below; it is not an
inference from the earlier checkpoint approval.

Start inspection at **`full-batch-monoton-ofl/warnings-ranked.html`**. All warnings
are sortable worst first, with category/font/checkpoint-source filters and direct
comparison links. The grouped new-warning view contains 34 groups. The largest
normalized fresh-engine screen is the checkpoint Best Director nominees 1976
poster; the largest new one is Luxembourgish subtitles. Exact sampled visual
inspection is recorded separately and does not claim individual inspection of
every variant. The user's full-run visual acceptance is recorded separately below.

The completed source-hash-bound run is under `full-batch-monoton-ofl/`; the old
checkpoint and STOP marker remain historical. The complete evidence audit is
`full-batch-monoton-ofl/final-audit.json`: all 9,958 job identities, retained/shared
artifact hashes, generated parents and published references verify. Imported
record hashes and original image/metric/timing fields also remain unchanged.
All renderer exits succeeded, with no timeouts. The published checkout's commit
and tracked state are unchanged. No publication or merge was performed during
validation. Subsequent PR publication/merge authorization is recorded below;
deployment, artwork publishing and production composer cutover remain out of scope.

### Full-Run Visual Sign-Off: 2026-10-16

After reviewing the completed warning report and clarifying that both fresh
engines use the same approved font files, the user stated:

> perfect. visually, all warnings are perfectly acceptable

Record this as visual acceptance of **all 703 warnings** in the completed
9,958-job approved-font run, including the 602 new continuation warnings. This
closes the outstanding visual-warning acceptance gate. It does not claim that
each individual image was inspected, change any numerical result, or convert
warning screens into numerical passes: results remain 9,255 pass, 703 warning,
zero failure. Original images, measurements and audit records stay unchanged.

That message was visual approval only, not publication or merge authorization.
The subsequent separate authorization below supersedes the earlier prohibition
on automatic PR publication and merge. Deployment, artwork publishing and
production renderer cutover remain out of scope.

### Subsequent PR Integration Authorization: 2026-10-16

The user explicitly authorized committing and pushing the scoped Phase 1 work
to existing PR #10, then requested merging that PR. Publish the validation code,
frozen manifests, notices and summary, keeping full generated evidence local.
Merge is contingent on successful PR CI and applicable repository requirements;
current integration/check status is tracked on
[PR #10](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/10).

The existing duplicate Splatter output is deferred to Phase 2's planned
`create_default_posters.ps1` generator-logic work. Both definitions pass the
Phase 1 engine comparison; preserving this existing orchestration ambiguity
does not introduce a Python renderer regression. This is not a Phase 1 behavior
change or a claim that its overwrite winner was resolved. Phase 2 will use a
separate draft PR; it is not implemented here.

### Approved Monoton and Authorized Continuation

The user subsequently approved the official Monoton replacement and explicitly
authorized resuming the remaining bulk tests. The original 6,631-job checkpoint
below remains historical and unchanged, including its STOP marker. Current work
uses a separate `full-batch-monoton-ofl/` evidence directory and the new frozen
`fixtures/effective-jobs-en-monoton-ofl.json.gz` inventory, canonical SHA-256
`b88b6da4e84faa1afc4cdfedd8fa064eed1415916b9133e9546319bf88faca33`.
The new capture has the same 9,958 jobs and parameters; only the 11 Monoton font
records changed. Its source hash also reflects the updated dependency checksum.
The earlier immutable fixture remains available with its original fingerprint.

All 11 fresh installed-font PowerShell outputs match the approved candidate
hashes. All 11 Python posters are byte-identical between the old and new fonts.
Fresh A-screen results are eight passes and three warnings, with no changed
native appearance; those warning screens are not new font replacement defects.
Evidence: `monoton-approved/index.html`. The original OFL notice is bundled in
`fonts/licenses/Monoton/`; no internal family or filename was changed.

The continuation preserves original image bytes, metrics and timings for the
6,631 completed jobs only after confirming their job fingerprints and inputs are
unchanged. `checkpoint-import.json` records original/new result hashes and the
source run. Those are imported pairs, not freshly rerendered pairs. New work
rendered the remaining 3,327 jobs with current approved fonts. Earlier partial
continuation snapshots are not separate full-completion certificates.

Reports now explain each metric trigger, isolated text-boundary shifts and what
to inspect before showing optional collapsed technical JSON. Font coverage lists
expected, completed and untested bulk jobs for every font, separately from the
126-case representative sample. No thresholds, metrics or warning statuses were
relaxed to make the report look cleaner.

The updated local suite passes **116 tests in 135.252 seconds**, including the
official Monoton asset/notice/name/checksum regression, unchanged-job inventory
comparison, safe checkpoint continuation, tampered-evidence rejection and
plain-language warning explanations, grouping and fresh-only severity ranking
without changing flags. The final presentation also passes the focused 24-test
report/reliability suite. All four ranking modes and category/font/source filters
pass browser checks at both desktop and mobile sizes, including case links.
Desktop/mobile report checks pass at
1440 and 390 pixels, including filters, counts, images, overflow and initially
collapsed technical details. Compilation and frozen-manifest checks pass.

Expected bulk font coverage is 9,784 Comfortaa jobs, 11 jobs for each of the
15 decade/year display fonts, and nine Bebas Neue Playlist jobs. The historical
checkpoint used only Comfortaa; it did not silently test or pass the other fonts.

New warnings have a compact `full-batch-monoton-ofl/review-groups.html` view,
separate from imported checkpoint flags. It shows an explicitly labeled snapshot
of completed records, groups repeated caption/rendering parameters, and links all
color/artwork variants. Neither grouping nor sampled visual inspection grants
new user approval or rewrites measured flags.
All completed warnings, including checkpoint imports, also have a sortable
`full-batch-monoton-ofl/warnings-ranked.html` index. It defaults to largest
fresh-engine difference relative to the unchanged comparison thresholds, with
alternate similarity/RGB/isolated-caption-shift sorting and category/font/source
filters. Published-font differences do not inflate that numerical priority.

The continuation has also now tested both independent Splatter jobs. Both pass
the fresh PowerShell/Python screen; their classification deliberately remains
`unresolved discrepancy` because the pre-existing concurrent production queue
targets one filename with both definitions. This is not a new renderer failure,
and no category or overwrite-policy change was made.

The current approved-font representative refresh also completed all 126 cases:
**111 pass, 15 warnings, no failures**. Every encoded image hash matches the
user-accepted report. It reused 117 hash-verified unchanged PowerShell poster
references, freshly rendered the five Monoton poster references, and reran all
four overlay probes. Python outputs were regenerated. The proof is
`representative-monoton-ofl/compatibility-proof.json`; both desktop and mobile
browser checks pass. The 15 warning screens do not represent changed visuals.

### Historical Stopped Checkpoint

**Ready for checkpoint team review; not ready for merge.** Rendering stopped at
the user's requested resumable checkpoint: **6,631 / 9,958 paired jobs**, with
**6,530 passing screens, 101 warnings, 0 failures and 3,327 untested jobs**.
All active workers finished; `STOP` remains in place. No automatic resume is
authorized. This is not a full-batch pass certificate. PR #10 stays a draft. No commit,
push, merge, ready-for-review transition, deployment or artwork publishing is
authorized or performed by this task.

Repository: `Kometa-Team/Defaults-Image-Creation`.
Branch: `feat/default-poster-python-fonts`; base: `main`.
Base code commit: `5b86f39c469ae00e7e7597196f20edb2bd3c720d`.
Validation changes are uncommitted; the report records exact renderer, runner,
font, translation and asset hashes rather than implying the base commit includes
these local changes.

### User Visual Sign-off: 2026-10-16

The user reviewed the presented comparison evidence and confirmed:
"i looked and they all look fine to me visually."

Record this as visual acceptance of the reviewed representative and completed
checkpoint outputs, including their displayed minor differences. This does not
assert that every one of the 6,631 outputs was inspected individually. The
representative report's 15 warnings and checkpoint's 101 warnings remain as
measured screening results, with this separate human visual disposition; no
image, metric, threshold or result status is changed.

This sign-off does not cover the 3,327 untested jobs, establish font permission,
authorize the proposed Monoton substitution, or authorize resume, commit, push,
merge, deployment or a production renderer switch. STOP remains in place.

## Evidence

All full generated evidence is local under ignored
`config/phase1-validation-20261016/`. HTML uses relative asset links and needs no
server. Nothing is copied into or changed in the published-artwork checkout.

| Evidence | Local Path |
| --- | --- |
| User-accepted pre-Monoton representative matrix | `representative-final/index.html` |
| Current approved-font representative matrix | `representative-monoton-ofl/index.html` |
| Original fresh paired timings for this run | `representative/summary.json` |
| Canonical-output compatibility proof | `representative-final/compatibility-proof.json` |
| Registered/bundled font equality audit | `representative-final/installed-font-proof.json` |
| Official font candidates, all 22 definitions | `font-candidates-verified/index.html` |
| Approved installed Monoton, 11 fresh pairs | `monoton-approved/index.html` |
| Exact candidate glyph, kerning and bounds metrics | `font-candidates-verified/measurements.json` |
| Nine approved Bebas outputs reverified | `bebas-approval/summary.json` |
| Eleven approved Jakarta outputs reverified | `jakarta-approval/index.html` |
| Partial full-batch checkpoint dashboard | `full-batch-complete/index.html` |
| Current approved-font continuation | `full-batch-monoton-ofl/index.html` |
| Compact newly flagged caption groups | `full-batch-monoton-ofl/review-groups.html` |
| All warnings, sortable worst first | `full-batch-monoton-ofl/warnings-ranked.html` |
| Complete retained-evidence and source-identity audit | `full-batch-monoton-ofl/final-audit.json` |
| Exact sampled visual-inspection scope | `full-batch-monoton-ofl/sampled-visual-review.json` |
| Audited unchanged-checkpoint import | `full-batch-monoton-ofl/checkpoint-import.json` |
| Exact coverage and every untested job ID | `full-batch-complete/coverage.json` |
| Verified resume/artifact/published-input integrity | `full-batch-complete/checkpoint-integrity.json` |
| Original grayscale records and correction audit | `full-batch-complete/validation-revisions/grayscale-v1/audit.json` |
| Later provenance audit, separate from render snapshot | `representative-final/provenance-addendum.json` |
| Per-job metrics and retained evidence | `full-batch-complete/cases/<job-id>/` |
| Exact four-way legacy offset probe | `compound-offsets/results.json` |
| Scope comparison against main | `source-scope.json` |

The old 129-case Phase 1 report remains historical and unchanged. An initial
font-candidate harness attempt is explicitly marked invalid because the legacy
alias selected the old Boecklins file. Its measurements are not used. Earlier
batch diagnostics/checkpoints are not added to the final run's coverage totals.

## Inventory

The complete default-English `All` dispatch resolves **3,352 literal rows into
9,958 composer invocations**, with all 3,352 rows mapped to their source locations.
There are 165 generated-input jobs and 36 separately captured overlay operations.
Other language selections are not claimed tested. The four representative
overlay probes do not imply that every bulk overlay transform was migrated.

The original checkpoint's immutable validation fixture is
[`fixtures/effective-jobs-en.json.gz`](fixtures/effective-jobs-en.json.gz), SHA-256
of its canonical manifest data:
`cbd30b1cbbfdfc8e58fa88ae33ef5e1389d506795948e1acbde41ab810da19ba`.
It is approximately 1.46 MB compressed, contains no font binaries or generated
artwork, and uses portable asset references rather than personal checkout paths.
The approved Monoton continuation uses the separate immutable
[`fixtures/effective-jobs-en-monoton-ofl.json.gz`](fixtures/effective-jobs-en-monoton-ofl.json.gz)
and canonical hash recorded in the current status above. Both retain exactly
the category inventory below.

| Category | Effective Jobs |
| --- | ---: |
| Aspect | 9 |
| AudioLanguage | 188 |
| Awards | 4,847 |
| Based | 4 |
| Chart | 1,182 |
| ContentRating | 72 |
| Country | 608 |
| Decade | 31 |
| Franchise | 118 |
| Genre | 276 |
| Network | 568 |
| Playlist | 9 |
| Resolution | 15 |
| Seasonal | 23 |
| Separators | 749 |
| Streaming | 256 |
| Studio | 488 |
| SubtitleLanguage | 188 |
| Universe | 20 |
| VideoFormat | 6 |
| Year | 301 |

The expansion comes from actual award-year loops, chart/network/streaming color
variants, 34 separator rows across 22 colors, direct/custom invocations, and
generated "Best of" jobs. Two special award commands mutate the last literal row
to `2016-2` and `1930-2`; original and effective rows are both retained. Their
lineage is captured before mutation, not guessed from the generated filename.

Two different Splatter rows target the same filename in a concurrent production
queue. Both are inventoried as independent jobs and both pass the continuation's
fresh engine comparison. Their unresolved published overwrite winner remains;
the virtual last-entry map
cannot certify the actual published overwrite winner. Three invocations have no
final virtual path because later jobs overwrite their temporary output: those
two special award jobs and the earlier Splatter job. This is reported rather
than silently changing production definitions or inventing separate outputs.

## Approved Fonts and Scope

All nine Playlist outputs match their approved Bebas Neue v2.000 hashes at the
154-point fitting maximum. All 11 Jakarta outputs match their approved previews
byte-for-byte at fixed 409 points, with no automatic fitting. Approved font and
notice hashes remain pinned by tests. Restricted Bebas, Helvetica and the rejected
Liberation trial are not distributable assets.

A structured inventory comparison against main commit
`6bbb494b44052ec87d77bffe7cdb22a29c9849d3` confirms exactly 20 approved row changes
(nine Bebas and eleven Jakarta) and 3,332 unchanged rows. The Jakarta-specific
PowerShell AST test confirms unrelated styles retain their previous fitter.
The original checkpoint did not modify either production PowerShell file.
The later approved Monoton step changes exactly one bulk-script dependency
checksum; all poster definitions and both PowerShell rendering bodies remain
unchanged. A source comparison in the continuation audit enforces this scope.

## Remaining Font Provenance

The exact existing Boecklins Universe font was recovered in a 2015 archive capture
of the author's official ZIP, alongside its original 2013 OFL notice. Its bytes
match the bundled font. The original OFL and FAQ are retained unchanged in
`fonts/licenses/BoecklinsUniverse/`; no font replacement is needed or applied.

Monoton's formerly bundled exact binary remains unverified; family-level OFL
evidence is not applied retroactively to different bytes. The user has now
approved its replacement with the verified official file and original OFL notice.
The old file remains only in private historical evidence. Boecklins stays unchanged.

| Official Candidate | Definitions | Max RGB MAE / 255 | Min Global SSIM | Layout |
| --- | ---: | ---: | ---: | --- |
| `Boecklins Universe.ttf` | 11 | 0.002995 | 0.999996 | Same fitted sizes, line breaks and centered ink bounds |
| `Monoton-Regular.ttf` | 11 | 0 | 1 | Pixel-identical reference posters |

Both comparisons have zero change in shaped advances and kerning adjustment for
the actual numeric captions. The official Monoton release and original notice
are now approved and applied. The newer
Boecklins release is optional now that the original package was recovered.
No Boecklins replacement is applied.
See [the detailed provenance audit](FONT_PROVENANCE.md) and machine-readable
[`font_provenance.json`](font_provenance.json) for exact hashes and source links.

## Representative Results

The fresh pre-Monoton paired run completed all 126 cases: **111 passing screens,
15 warnings, 0 failures**. It covers 21 categories, active fonts, five gradients,
borders, alpha, offsets, wrapping, long labels and supported Unicode.
The approved-Monoton refresh described above verifies the same image hashes,
not a new unqualified visual approval or a second independent timing benchmark.

After the two demonstrated compatibility fixes below, all 126 candidate images
were verified again. All image SHA-256 values are unchanged. The final report
reuses only the 122 hash-verified PowerShell poster outputs produced freshly in
this same validation run; the four overlay probes were rerun. Historical 129-case
outputs were not used as current-font baselines.

Three warnings concern published artwork while fresh engines agree: the approved
Playlist and Jakarta font changes and the historical 1001 Movies genre design.
The remaining warnings are the previously observed decorative-font/text and two
genre-overlay differences. Stress-case SSIM values closely match the preserved
historical report; caption-bound differences are at most one pixel per edge.
Warnings remain measured warnings, not manufactured passes. The user's later
visual acceptance is recorded separately above.

Seven non-reviewed reference font names resolved through Windows' font registry.
All seven installed files were hashed and match the bundled bytes exactly;
other selections used bundled paths. No font was installed or removed. The full
matrix forces exact bundled paths instead of relying on those registered names.

## Demonstrated Compatibility Fixes

The full inventory exposed 180 Chart calls with `+-500` offsets. The unchanged
PowerShell/ImageMagick reference produces a byte-identical poster for `+-500`
and `-500`, but different images for `+500` and `0`. The candidate API and CLI now
accept that exact compound form. Raw frozen arguments stay unchanged.

Seven Studio stems end in a period. Appending `.jpg` produces valid filenames
such as `A.C.G.T..jpg`; native validation now permits those final stems while
still rejecting traversal, invalid directory components, reserved Windows names,
invalid characters and trailing spaces. No production definitions were repaired.

The inactive Studio sample path `#D19068` is preserved but is not required as an
input when sampling is disabled, matching both renderers' actual predicate.

## Full-Batch Method

Use the checkpoint dashboard's `summary.json` and `run.json` for saved counts, engine
completion totals, warnings, failures, remaining coverage, per-category/font
breakdowns, worst comparisons, hashes, timings and storage. Do not treat a partial
dashboard as completion. Full-batch status screens A (fresh reference/candidate);
B/C published comparisons are classified separately.

The runner has bounded active and pending work, per-engine deadlines, atomic
per-job results, hash-checked resume, explicit failed-case retry, cooperative stop,
free-space protection and owned-workspace cleanup. Common generated inputs use
the same fresh PowerShell parent bytes for both engines, with their hashes
recorded, so this isolates composer parity rather than claiming an end-to-end
native bulk migration. Font paths resolve exact bundled bytes.

The full frozen record retains original expanded arguments as `raw_parameters`
and known validated fallback values as `parameters`. Both composers receive the
original numeric arguments, including resize zero and out-of-range fitted sizes;
the exact runtime values and remapped paths appear as `invocation_parameters` in
each result. Numeric validation/fallback is exercised in both engines, not skipped.

All 2,062 distinct fitting captions were audited for PowerShell wildcard escaping.
One caption contains escaped characters. An isolated execution of the original
`Get-OptimalPointSize` function measures 307 points versus the direct diagnostic's
338, but both clamp to its configured 250-point maximum. The frozen composer
argument is therefore unchanged. `fitting.measured` records the direct diagnostic,
not the original escaped-caption measurement. The exact-font probe rejects
fallback diagnostics and stubs SQLite writes; local evidence is
`config/phase1-validation-20261016/fitting-edge-proof.json`.

When published bytes have the same SHA-256 as the fresh reference, B is exactly
zero error and C is the symmetric A comparison. The runner records this explicit
provenance and reuses matching crops/differences instead of decoding and storing
duplicate evidence. Unit tests compare every numeric metric against direct B/C
calculations. Both composers still render every job; this is only analysis reuse.

A reproduced Windows race can return an equivalent `\\?\` device-prefixed path
when another thread creates a parent directory. The path guard now canonicalizes
equivalent drive/UNC forms before applying the same strict containment test.
A parallel-creation regression covers this; no boundary check is removed.

Full-batch process-tree RSS/write sampling is 250 ms, recorded per measurement,
to avoid eight simultaneous 20 ms process scans dominating runtime. Peak samples
are lower-bound observations, not allocator maxima. The serial representative
benchmark uses its original 20 ms sampling. Render thresholds are unchanged.

### Completed Approved-Font Coverage

Every category below is fully paired, with no failures or untested jobs.

| Category | Pass | Warning |
| --- | ---: | ---: |
| Aspect | 9 | 0 |
| AudioLanguage | 182 | 6 |
| Awards | 4,756 | 91 |
| Based | 4 | 0 |
| Chart | 1,179 | 3 |
| ContentRating | 72 | 0 |
| Country | 607 | 1 |
| Decade | 31 | 0 |
| Franchise | 118 | 0 |
| Genre | 276 | 0 |
| Network | 568 | 0 |
| Playlist | 9 | 0 |
| Resolution | 15 | 0 |
| Seasonal | 23 | 0 |
| Separators | 159 | 590 |
| Streaming | 250 | 6 |
| Studio | 488 | 0 |
| SubtitleLanguage | 186 | 2 |
| Universe | 20 | 0 |
| VideoFormat | 6 | 0 |
| Year | 297 | 4 |

| Font | Pass | Warning |
| --- | ---: | ---: |
| Barlow | 11 | 0 |
| Bebas Neue | 9 | 0 |
| Boecklins Universe | 11 | 0 |
| Boogaloo | 11 | 0 |
| Cherry Cream Soda | 11 | 0 |
| Comfortaa Medium | 9,085 | 699 |
| Jura | 11 | 0 |
| Limelight | 11 | 0 |
| Monoton | 8 | 3 |
| Plus Jakarta Sans | 11 | 0 |
| Press Start 2P | 11 | 0 |
| Righteous | 11 | 0 |
| Rye | 11 | 0 |
| Special Elite | 10 | 1 |
| Trochut | 11 | 0 |
| UnifrakturCook | 11 | 0 |
| Yesteryear | 11 | 0 |

Full published-artwork classifications are 9,179 expected image-encoding
differences, 703 Python migration warning screens, 53 existing historical artwork
differences, 18 approved font replacements, three missing counterparts and two
unresolved Splatter overwrite classifications. The 18 approved-font classifications
are all 11 Jakarta jobs and seven Bebas jobs; the remaining two Bebas jobs stay
within the published comparison thresholds, not untested or forcibly reclassified.
Missing counterparts are the temporary award outputs `2016-2` and `1930-2`, and
the existing Franchise definition `Death in Paradise (2911)`. No definition or
published file was changed to conceal these distinctions.

The new Year flags are Monoton's `1970`, `1975`, `1978`, and Special Elite's
`2009`. Their preview pairs were inspected, with matching visible captions and
placement. The six flagged Streaming preview pairs, both subtitle-language
preview pairs and selected separator previews/text crops were also inspected.
No material discrepancy was observed in those views; isolated caption-edge
differences in new warnings are at most one pixel. This is sampled inspection,
not a claim that every color/artwork variant was visually reviewed. The original
warning metrics and thresholds remain unchanged.

### Historical User-Requested Checkpoint

Both engines successfully rendered 6,631 jobs, all with successful exits and no
timeouts. Six categories are complete; Country has 329 of 608 jobs complete.
The bulk checkpoint has exercised only Comfortaa Medium so far. The separate
126-case representative matrix covers all 17 active fonts and 21 categories;
that does not substitute for the unfinished bulk categories.

Of 3,352 inventoried literal rows, **1,315 have all associated jobs paired** and
**2,037 have none paired**; no row is partially paired at this checkpoint.
Execution and inventory coverage are intentionally separate. The exact remaining
3,327 job IDs are stored in `full-batch-complete/coverage.json`.

| Category | Completed | Untested |
| --- | ---: | ---: |
| Aspect | 9 | 0 |
| AudioLanguage | 188 | 0 |
| Awards | 4,847 | 0 |
| Based | 4 | 0 |
| Chart | 1,182 | 0 |
| ContentRating | 72 | 0 |
| Country | 329 | 279 |
| Decade | 0 | 31 |
| Franchise | 0 | 118 |
| Genre | 0 | 276 |
| Network | 0 | 568 |
| Playlist | 0 | 9 |
| Resolution | 0 | 15 |
| Seasonal | 0 | 23 |
| Separators | 0 | 749 |
| Streaming | 0 | 256 |
| Studio | 0 | 488 |
| SubtitleLanguage | 0 | 188 |
| Universe | 0 | 20 |
| VideoFormat | 0 | 6 |
| Year | 0 | 301 |

Published classifications: 6,490 expected encoding differences, 101 Python
migration warning screens, 38 existing historical artwork differences and two
missing counterparts (temporary award intermediates). No approved-font bulk
jobs have run yet; their approvals were reverified separately. Every published
alias is considered, including incomparable dimensions; the corrected classifier
changes none of the stored classifications at this checkpoint. Per-image records
retain all A/B/C metrics and counterpart hashes.

The published checkout remains at commit
`59e49ede8d41ac5991f971e66e93af596402329a` with clean tracked status. It is strictly
read-only. Resume requires explicit user authorization, inspection of STOP and
the source snapshot's instructions; do not run the current runner against the
old run key. The archived original runner preserves its exact source identity,
then the separate grayscale validation revision is reapplied as needed.

### Reference Grayscale Validation Revision

The original batch validator incorrectly required the PowerShell reference to
emit mode RGB. ImageMagick legitimately encodes fully monochrome posters as
grayscale JPEGs (mode L); the sampled white Starz output is byte-identical to its
published counterpart. Python remains RGB. Both are comparable in decoded RGB,
and the original A/B/C metrics were already computed correctly.

At the final stopped checkpoint, all 62 originally failed records had only this
mode rejection; no engine had a nonzero exit or timeout. After the batch released
its lock, all 62 were audited and corrected to passing screens.
[`revalidate_grayscale.py`](revalidate_grayscale.py) provides a narrow, audited
correction after rendering: verify original artifact hashes and successful exits,
retain original result JSON backups, preserve output bytes/metrics/timings, add
the missing reference metadata and caption diagnostics, and record a source-hashed
validation revision. Visual flags remain flags. Four regression tests cover
preservation, unrelated failures, tampered evidence and idempotent audit records.
No candidate rendering change or numerical threshold relaxation is involved.

### Historical Checkpoint Visual Review

The 101 warnings comprise six AudioLanguage, 91 Awards, three Chart and one
Country case. All measured caption-edge deltas in these groups are at most one pixel.

The following sampled warning pairs were inspected as complete posters and text
crops. Their content, line breaks and placement agree; differences are at text
and image edges. Keep the measured flags; the user's subsequent visual
acceptance is recorded separately above, not inferred automatically from metrics.

| Group / Sample | Job ID | RGB MAE / 255 | Global Luminance SSIM |
| --- | --- | ---: | ---: |
| Audio, Luxembourgish | `audiolanguage-00108-d96de3de24b1` | 0.382158 | 0.988938 |
| Best Director nominees, 1976 | `awards-03472-105c6aad65f5` | 0.791982 | 0.986186 |
| Best Picture winner, 2007 | `awards-03815-f8b634f9213e` | 0.564662 | 0.993879 |
| Winners, 1955 | `awards-03867-c79c1c5f130d` | 0.339728 | 0.994802 |
| Best Director winners, 2004 | `awards-04020-eb44ad3ac07b` | 0.839860 | 0.988725 |
| Chart, One Million Watched Club | `chart-05073-08898f35d3fd` | 0.770546 | 0.993575 |
| Chart, Most Transcoded | `chart-05128-fbca9f792239` | 0.495166 | 0.993057 |
| Chart, Top 10, offset `+-500` | `chart-05143-05ffa2bc4b96` | 0.128335 | 0.994941 |
| Country, Central African Republic | `country-06357-d98d4f62a4bf` | 0.675929 | 0.994186 |

All six flagged audio-language pairs were visually checked. The sampled Award
layouts include one, two and three caption lines. All three Chart pairs and the
Country pair were checked as complete posters and text crops. No material layout
problem was found in these inspected samples; untested work remains unqualified.
Original thresholds and
candidate rendering code were not adjusted in response to these flags.

## Versions and Performance

Python 3.13.15; Pillow 12.0.0; FontTools 4.60.1; uharfbuzz 0.56.3;
python-bidi 0.6.11; NumPy 2.3.4; PowerShell 7.6.6;
ImageMagick 7.1.2-27 Q16-HDRI x64.

English source: Kometa-Team/Translations commit
`a7bddf45d0fb2cc37c794af05d5fb807880c9a80`, byte-identical to the packaged
MIT-licensed comparison fixture. Actual translation SHA-256 is recorded in every
manifest. No software was installed or updated for these runs.

For the 122 fresh serial representative poster pairs, PowerShell averaged
4.714 seconds and Python 1.243 seconds, approximately 3.79 times faster in this
sample. Sampled peak tree RSS was about 510 MiB and 162 MiB, respectively.
These are sample-specific observations, not a full-batch speed guarantee. Parallel
batch timings include contention and are recorded independently.

The completed continuation invocation ran from 11:39:18.744963 to
14:11:52.933373 UTC on 2026-10-16, about **2h32m34s** (including imported-record
revalidation, 3,327 fresh pairs and comparison/report work). Its preparatory
checkpoint import is not counted as rendering time. Across the 3,327 fresh pairs,
PowerShell averaged **10.827 seconds** and Python **2.486 seconds** per engine
invocation under eight-worker contention, approximately 4.35 times apart in
these sampled engine durations. This is not an end-to-end pipeline speed claim.
Across all 9,958 preserved/fresh pairs, summed engine durations are
99,545.530 seconds PowerShell and 25,189.123 seconds Python, averaging 9.997 and
2.530 seconds. Summed parallel engine time is not wall-clock time.

The complete-run sampled peak process-tree RSS is **1,242,091,520 bytes** for
PowerShell and **278,331,392 bytes** for Python. Observed write-counter sums are
6,711,039,645 and 4,905,071,557 bytes, with Python samples unavailable for 5,192
jobs (including 1,813 fresh jobs). Missing counters are not zero writes; these
sampled counters and peaks remain lower-bound observations. The new evidence
directory occupied approximately **3.35 GB** at the audit measurement, including
retained flagged images, previews, captions and private scratch/snapshots. Later
audit/browser artifacts can add small amounts. It is not a distributable artwork
or font bundle.

The historical stopped eight-worker invocation took 14,233.903 seconds (about 3h57m),
including rendering and analysis. Summed engine durations were 63,524.188 seconds
PowerShell and 16,916.868 seconds Python, averaging 9.580 and 2.551 seconds per
job under contention. These summed durations are not wall-clock execution times.
Checkpoint storage is approximately 2.04 GB including previews, flags, caption
cache and private scratch; `summary.json` records the measured bytes. Do not
distribute scratch fonts or assume the whole evidence tree is license-cleared.

The historical checkpoint integrity audit verified all 6,631 jobs' retained/shared artifacts,
generated parents, published counterpart hashes and resume inputs. All 62
grayscale originals retain identical numeric comparisons, render timings,
parameters and JPEG bytes. It also confirms STOP is present, the batch lock is
absent, and both production PowerShell source hashes are unchanged. Results are
in `full-batch-complete/checkpoint-integrity.json`.

Parallel sampled peak process-tree RSS was 602,144,768 bytes for PowerShell and
181,202,944 bytes for Python. Observed write-counter sums were 4,448,491,039 and
3,741,942,060 bytes, respectively. Python had no write-counter sample in 3,379
jobs; these are unavailable measurements, not zero writes. Counters and peaks
remain sampled lower bounds, not complete I/O totals or allocator maxima.

## Tests and CI

The current **116-test suite passes locally (135.252 seconds)**, including actual timeouts, source
preservation, exact font/notices hashes, dynamic lineage, translations, generated
dependencies, bounded queueing, Windows path normalization and resume checks.
Compilation and `git diff --check` pass. Desktop 1440 px and mobile 390 px report
checks pass with no horizontal overflow, broken case images or JavaScript errors.

The new PR-main workflow uses SHA-pinned checkout/setup-python actions with
contents-read permission and no persisted credentials. It installs Python
dependencies, compiles, tests, validates the frozen manifest and checks whitespace.
Ordinary CI requires no ImageMagick, PowerShell or private artwork repository.

**At validation completion, remote CI had not run** because the workflow and
validation changes were still local under the original task restriction.
The user subsequently authorized publication and merge subject to CI. Current
check results are tracked on PR #10 rather than inferred from local tests.
The first remote attempt stopped during checkout, before tests, because the
repository already contains an unrelated `People-Auto-Readme` gitlink without a
`.gitmodules` URL mapping. Sparse checkout alone did not avoid Git's metadata
lookup. The missing three-line mapping is restored to the verified official
`https://github.com/Kometa-Team/People-Auto-Readme.git` repository; its existing
gitlink commit `002a212e09115e431341a8ec826caefbf8ecf5aa` is unchanged and was
verified to exist there. CI does not initialize or download that submodule.
A temporary-repository regression reproduces the original error and verifies
that restoring the mapping permits credential cleanup without initialization.

## Files and Remaining Gates

Created: capture/manifest tooling, frozen gzip fixture, resumable batch/report
runner, unresolved-font comparison/summarizer, Bebas approval verifier, validation
tests, runbook, this report and the PR workflow. Modified: candidate compatibility,
comparison metrics/classifications, focused renderer tests, provenance findings
and the review guide. No unrelated module or metadata cleanup is included.

The user subsequently approved Monoton and authorized continuation; all 9,958
jobs are now paired. All 703 visual warnings have explicit user acceptance,
without rewriting numerical flags. The user has also authorized publishing and
merging PR #10, contingent on passing CI and repository requirements. The existing
Splatter ambiguity is deferred to Phase 2, not silently repaired here. The current
production workflow is preserved, and no Phase 2 implementation is included.
