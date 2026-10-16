# Frozen Offline Phase 1 Validation

The new tooling validates the existing draft PR candidate. It does not change
production category generation or publish artwork. The default English `All`
dispatch contains 3,352 literal rows but **9,958 composer invocations**, plus 36
separate overlay transforms. Other language selections are not claimed tested.

## Capture and Freeze

Use existing PowerShell 7, ImageMagick and Python 3.13 installations. Nothing is
installed or updated by these comparison commands.

```powershell
py -3.13 create_defaults/validation_manifest.py --capture-dir config/new-capture --fitting-cache config/new-fitting-cache --output config/new-manifest.json.gz
py -3.13 create_defaults/validation_manifest.py --check config/new-manifest.json.gz
```

The capture imports only allowlisted category ASTs and four read-only helpers.
It never runs the bulk bootstrap, dispatcher, process launcher, file mutations,
downloads or publishing. Actual translation substitutions, loops, direct calls
and virtual moves are captured. Full literal rows identify source locations,
including two distinct Splatter definitions with the same key and output name.

Translation maps retain production's case-insensitive PowerShell hashtable
lookup. Unknown commands/methods, unresolved expressions/translations, source
changes, escaping paths and unsupported composer parameters fail closed.

Caption fitting is deferred only after an AST check establishes that fitted
sizes are not used to select category control flow. Bounded ImageMagick workers
then reproduce the original read-only caption measurement and clamp rules.
Measurements are cached by request plus exact font hash for resumability.
Jakarta's actual fixed-409 bypass is preserved, not approximated by a fitting cap.
The legacy SQLite cache is not consulted. Original random separator colors are
frozen to valid explicit values, identical in both composers.

The gzip JSON is an immutable validation fixture, not a new production category
format. It includes all effective parameters, fonts, input hashes, source rows,
producer locations, generated-input dependencies, output mappings and explicit
scope. Raw source hashes retain byte provenance; normalized text hashes allow
read-only verification across Windows/Linux checkout line endings.

`raw_parameters` retains the fully expanded invocation; `parameters` documents
known post-validation fallback values. Runtime restores the original numeric
arguments (including resize zero and out-of-range fitted sizes) into both
engines, and each result records the actual `invocation_parameters`. Only paths
are remapped to exact local assets and nondeterministic colors are frozen. The
comparison does not bypass either renderer's numeric fallback behavior.

## Bounded Full Batch

```powershell
$env:DEFAULT_IMAGES_LOCAL_REPO = 'C:\repos\Default-Images'
py -3.13 create_defaults/validation_batch.py --manifest create_defaults/fixtures/effective-jobs-en-monoton-ofl.json.gz --report-dir config/full-validation --workers 4 --timeout 120
```

Repeat the identical command to resume. Add `--retry-failed` to explicitly retry
failed jobs. `--limit N` is a smoke test, never a full-coverage certificate.
`--report-only` regenerates HTML from persistent results without rendering.

### Current User-Requested Stop

This section describes the historical checkpoint. The user subsequently
authorized continuing with the approved official Monoton file. The new frozen
inventory is `fixtures/effective-jobs-en-monoton-ofl.json.gz`, canonical SHA-256
`b88b6da4e84faa1afc4cdfedd8fa064eed1415916b9133e9546319bf88faca33`.
The earlier fixture remains unchanged and describes the old font/checksum.
The approved-font continuation completed all 9,958 paired jobs, with 9,255
passing screens, 703 warnings and no failures. All 3,352 literal rows are fully
paired. See `PHASE1_VALIDATION_20261016.md` for current totals and review gates;
historical checkpoint totals below are not the current completion state.
The original private source snapshot now includes its exact fonts, pinned assets
and translation fixture so historical inputs remain reproducible.

`continue_validation.py` prepares a disjoint continuation directory, rejects
changed completed jobs, verifies copied evidence and published hashes, and
retains original result records alongside an explicit import audit. It proves
the bulk source changed only in Monoton's checksum, checks metric/helper ASTs
and unchanged renderer sources, and requires the same tool versions/published
state. Imported image bytes, metrics and timings are retained, not rerendered.
Changed Monoton jobs were not yet executed at the old checkpoint, so all 6,631
completed job fingerprints remain valid; only the remaining 3,327 need rendering.

```powershell
py -3.13 create_defaults/continue_validation.py --source config/phase1-validation-20261016/full-batch-complete --destination config/phase1-validation-20261016/full-batch-monoton-ofl --manifest create_defaults/fixtures/effective-jobs-en-monoton-ofl.json.gz --published-repo C:/Users/bullmoose20/Default-Images
py -3.13 create_defaults/validation_batch.py --manifest create_defaults/fixtures/effective-jobs-en-monoton-ofl.json.gz --report-dir config/phase1-validation-20261016/full-batch-monoton-ofl --published-repo C:/Users/bullmoose20/Default-Images --workers 8 --timeout 120 --sample-interval 0.25
```

Do not rerun the import into an existing directory. Repeat only the batch command
to resume that same continuation under its exact hashes. The old STOP file is
not removed. An incomplete import cannot launch rendering. Report pages now
explain cutoff triggers and caption shifts before collapsed technical JSON, and
font coverage explicitly distinguishes untested fonts from completed bulk jobs.

For a compact, presentation-only review of newly flagged continuation jobs:

```powershell
py -3.13 create_defaults/review_validation_groups.py --report-dir config/phase1-validation-20261016/full-batch-monoton-ofl --published-repo C:/Users/bullmoose20/Default-Images
```

Open `warnings-ranked.html` for all completed warnings, including checkpoint
imports, sorted worst first. Category, font and source filters combine with
sorting by threshold ratio, similarity, RGB difference or caption-edge shift.
The ratio uses fresh PowerShell/Python comparisons only: the largest of RGB
error / 1.5, (1 - similarity) / 0.005, and alpha error / 1.5 where available.
This is a numerical inspection priority, not a visible-defect score. Historical
published-image differences are deliberately excluded from this priority.

Open `review-groups.html` for grouped new warnings. The snapshot groups identical
caption/font/rendering parameters except color, logo and output name; source
artwork can still differ. Each group links every flagged variant. Samples are
chosen by highest fresh-engine threshold ratio, not by visual
approval. Imported checkpoint warnings remain in the full dashboard instead of
being duplicated here. Regeneration does not rewrite results or their flags.

The historical 2026-10-16 run stopped at 6,631 of 9,958 jobs. Its STOP marker
remains preserved. Exact remaining job IDs at that checkpoint are in
`config/phase1-validation-20261016/full-batch-complete/coverage.json`; results are
6,530 passing screens, 101 warnings and no failures after the audited grayscale
checker correction. This is not full-batch acceptance.

The current runner includes later checker/presentation fixes, so its hash cannot
resume the original run key. The old source snapshot is private historical
reproduction evidence, not the current continuation command. Use the approved-font
continuation above; it already accepts valid legacy grayscale JPEGs and does not
need the historical grayscale correction reapplied. Do not bypass a mismatch or
restore source automatically.
Resume requires matching manifest/job hashes, runner versions, comparison code,
published repository state and retained evidence hashes. A lock rejects two
writers. Source and published repository state are checked before and after.

To stop safely, create a `STOP` file in the report directory. Pending jobs are
cancelled, active jobs finish within their deadlines, and partial results and
coverage are written before exit. Inspect the run and explicitly remove that
single file before resuming. Do not terminate only the outer Windows launcher:
it can leave Python child processes running.

Each worker owns an isolated reference workspace. Only pre-start update/install
bootstrap is omitted from the copied PowerShell reference. Rendering statements
are unchanged. Exact bundled font paths bypass installed-font name preferences.
Processes have per-job deadlines; timed-out process trees are killed and reaped.
No renderer is launched when required input assets are missing. Exceptions become
persistent per-job failures instead of aborting all other jobs.

Generated-input jobs are scheduled after their parent jobs. Both engines receive
the **same fresh PowerShell parent output**, with its runtime SHA-256 recorded.
This isolates composer parity rather than conflating it with upstream image
differences. It is not a claim of a migrated end-to-end bulk workflow.

Passing jobs keep previews, metrics, hashes and small differences; full-resolution
flags and category representatives remain. Parent reference images needed by
dependent jobs are also retained. A free-space floor prevents filling the disk.
Cleanup is restricted to verified paths inside the validation workspace.

## Interpretation

The inventory exposed two demonstrated compatibility gaps in the candidate:
180 Chart calls use `+-500`, which the unchanged reference renders byte-identical
to `-500`; seven Studio names end in a period, producing valid `stem..jpg` final
filenames. Native handling now supports those exact cases. Compound-offset API
and CLI tests and filename regressions cover them. Traversal, trailing-period
directories, invalid characters and reserved Windows names remain rejected.
The original invocations remain unchanged in the frozen manifest and production
scripts. The local four-way reference probe is under
`config/phase1-validation-20261016/compound-offsets/`.

One Studio definition supplies `#D19068` as an inactive average-color sample path.
Both renderers ignore it while average-color sampling is disabled. It is recorded
verbatim, not treated as a required missing input or silently corrected.

Full-batch pass/warning/failure is the **A: fresh PowerShell/Python** screen.
B/C comparisons and classifications separately track published differences,
approved font replacements, encoding differences, missing counterparts and
unresolved cases. Synthetic representative stress cases have no historical
counterpart by design. Thresholds remain RGB MAE > 1.5 or global luminance SSIM
< 0.995, with separate alpha checks; they screen for review, not visual sign-off.

Reports label SSIM as global luminance at 400x600, not windowed SSIM. They retain
raw maximum channel error, p99 channel error (the documented meaningful-difference
screen), text-region error, metadata, timing and diagnostic caption bounds for
flagged text. Before/after evidence and relative links work directly from HTML.
Large generated evidence stays under ignored `config/`, never in Git by default.
Private worker scratch directories contain copied fonts and must not be included
in a shared artifact or treated as a cleared redistribution package. Share only
reviewed, sanitized evidence; retain original font notices with any approved
font assets that are deliberately redistributed.

If published SHA-256 equals the fresh reference SHA-256, B's equality and C's
symmetry are exact. The report explicitly records this metric reuse and shares
existing evidence rather than re-decoding identical bytes. Tests verify reused
numeric metrics against direct comparisons. Every poster is still freshly
rendered in both engines.

The two Splatter rows target the same output while the production launcher uses
concurrent processes. The virtual map's last queued entry does **not** certify
the real final overwrite winner. Both invocations are independent manifest jobs,
still untested at the current checkpoint. The published-path ambiguity is
reported; no production fix is authorized here.

## Grayscale Reference Audit

This is historical audit documentation, not a step for the current continuation.
The 62 corrections were completed before Monoton was replaced and are preserved
in the original checkpoint and imported source records. The current validator
accepts valid reference JPEG modes L and RGB, so no new RGB-only correction is
needed. Do not rerun the command below against historical inputs using today's
changed fonts/source tree, or bypass its input/source guards. Historical replay
requires its exact archived inputs and helper versions.

The original validation run falsely rejected fully monochrome reference JPEGs
because it checked mode RGB only. Mode L is legitimate ImageMagick JPEG encoding,
not a rendering failure. Native output remains RGB; comparison explicitly uses
decoded RGB, while both original modes and output hashes stay recorded.

After that run exits and releases `.running`, apply the narrowly scoped audit:

```powershell
py -3.13 create_defaults/revalidate_grayscale.py --manifest create_defaults/fixtures/effective-jobs-en.json.gz --report-dir config/phase1-validation-20261016/full-batch-complete --published-repo C:/Users/bullmoose20/Default-Images
```

This verifies all retained original artifacts and successful engine exits before
correcting an RGB-only mode rejection. It cannot clear other errors or visual
flags. Original result records are copied byte-for-byte under
`validation-revisions/grayscale-v1/`; the audit records source hashes and original
and revised record hashes. Output JPEG bytes, numeric A/B/C metrics and original
timings are unchanged. Missing caption diagnostics/previews are completed, not
substituted for the original images. Repeated invocation is idempotent and checks
the saved revision. It never writes to the published checkout or production
assets. The frozen original runner and this revision reproduce both stages of
the historical validation, without presenting a checker correction as a rerender.

## CI Boundary

The PR workflow installs only Python dependencies and runs compilation, unit
tests (including approved font/notices hash checks), frozen-manifest verification
and whitespace checks. Actions are commit-pinned with contents-read permission
and no persisted checkout credentials. It does not require ImageMagick, PowerShell
or a private artwork checkout. Full rendering remains an explicit offline task.

Pins verified against official releases on 2026-10-16:
[checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1) at
`3d3c42e5aac5ba805825da76410c181273ba90b1` and
[setup-python v7.0.0](https://github.com/actions/setup-python/releases/tag/v7.0.0)
at `5fda3b95a4ea91299a34e894583c3862153e4b97`. Both use Node 24 on the hosted
Ubuntu runner. An offline regression checks the trigger, pins, permissions,
Python version and separation from the offline rendering toolchain.

Until these local changes are explicitly authorized for commit/push, the new
workflow cannot operate on PR #10. A local test pass is not a remote CI success.
