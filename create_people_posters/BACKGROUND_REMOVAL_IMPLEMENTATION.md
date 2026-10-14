# Local Background Removal Implementation and Validation

Validation date: 2026-10-14. Local snapshot for `main`; online publication is deferred.
Approved trial default: **BiRefNet Portrait**, with Adobe retained for rollback.
Source confidence: **source-unverified**, as requested for the available clones.

## Delivered Behavior

`remove_bg_birefnet.py` provides local CPU ONNX inference via pinned rembg, with
Portrait, General and ISNet model selection. It checks downloaded and cached
weights, initializes one session per batch, preserves source dimensions, validates
RGBA PNGs and stages outputs for the existing poster workflow. Temporary-file
replacement, archived-source checks and provenance hashes protect files and retries.
Recoverable failures continue through the batch and return nonzero. Initialization
failures return an actionable error. There is no implicit Adobe fallback.

The orchestrator retains its step order and `remove_bg` key. It selects Portrait by
default, supports a dedicated `REMOVE_BG_PYTHON`, records engine configuration in
checkpoints, and invalidates background/downstream markers on configuration changes.
Changing engines requires actual queued source photographs, not old Adobe cutouts.
Local recovery reuses inferred candidate cutouts, preserves archived photographs,
and limits local postchecks/cleanup to the generated working tree.
Exhausted TMDB searches remain nonfatal, matching the Adobe workflow: existing
posters and original archives are preserved and warnings remain in the report.
Actual errors and unresolved recovery failures still return nonzero. The initial
local integration incorrectly classified exhaustion as failure; this was corrected
after the first production trial exposed it for BoA.

Local Original-style sync publishes validated, atomic 2000x3000 RGB JPEG
presentation copies while preserving native archives. Compliant JPEGs retain
exact bytes. Other supported archive formats and dimensions are converted only
in the presentation copy. Publication target collisions fail preflight and
reserved recovery `.history` folders are excluded. Adobe normalization and
other style behavior are unchanged.

The comparison tool snapshots read-only references into separate benchmark
folders, matches normalized Unicode paths/basenames without guessing ambiguous
matches, records source hashes and confidence, and initializes models sequentially.
It generates portable HTML, CSV/JSON metrics, deterministic manifests, category
filters, full-resolution inspection and persistent/exportable/importable reviews.
Report-only regeneration preserves validated historical measurements.

## Executed Validation

- All three local environments were updated against all four repository
  requirements files and passed package constraints, `pip check`, module imports
  and `orchestrator.py --list`: main `venv` (Python 3.12.10), `.venv-ddcolor`
  (Python 3.13.15) and `.venv-rembg` (Python 3.13.15). CPU Torch 2.14.1,
  torchvision 0.29.1, rembg 2.0.85 and ONNX Runtime 1.31.0 are installed.
- Old optional Gradio packages in the main environment were updated to resolve
  their incompatible Hugging Face constraints. No project environment was deleted.
- Clean Windows x64 Python 3.13.15 CPU inference installation and `pip check` passed.
- A second installation from `requirements-rembg.txt` into an isolated target
  passed imports with site packages disabled (`-I -S`).
- Final automated suite after the approved default switch and recovery fix:
  358 passed, 3 skipped in 53.27 seconds. The skips
  cover opt-in cached-model/browser checks and a permission-dependent link test.
  Twenty warnings are the existing `edge_chop.py` Pillow `getdata` deprecation.
- The browser smoke check was separately enabled and passed: images, model/flag
  filters, four backgrounds, full-resolution modal, browser persistence, JSON/CSV
  export/import, desktop/mobile bounds and nonblank screenshot pixels.
- The final 100-portrait report passed that browser check separately in 87.69
  seconds. All 500 source/baseline/local assets are embedded; PNG previews use
  lossless WebP only when smaller and byte-exact after RGBA decoding. Color
  metadata is retained. The portable report is roughly 1.6 GiB and can take
  substantial time and memory to open; pagination limits active image decoding.
- One real single-image Portrait smoke test produced a valid 2000x3000 RGBA PNG
  in 33.65 seconds, leaving its source intact.
- The final opt-in cached-model test passed separately after the warning-handling
  edits, checking model integrity, real inference, source preservation and cleanup.
- A real three-image comparison produced nine valid local outputs plus Adobe
  baselines. All dimensions remained 2000x3000; no processing failures occurred.
- An isolated real PowerShell/ImageMagick smoke passed 46 checks: five styles
  and transparent output were 2000x3000, Original sync published an RGB JPEG
  at 2000x3000, and the 400x600 source archive's hash stayed unchanged. Cached
  assets were resized to simulate this handoff, without new inference or a
  native-resolution quality claim. The unchanged poster script needed an
  `Out-String` width wrapper under Windows PowerShell 5.1 for its long isolated
  font path; captured sync output needed `PYTHONIOENCODING=utf-8`. Initial failed
  attempts and successful checks are retained in `config/validation/native-pipeline`.
- Inventory: 15,324 originals and 15,324 Adobe images, all uniquely matched, with
  no missing/ambiguous/duplicate entries. A deterministic seed-42 sample of 100
  Adobe files passed integrity, alpha and dimension checks.
- Both reference repositories had clean tracked-file status after the initial
  benchmark. No cloning, source edits, repository updates or pushes were performed.

The full 100-image, three-model CPU benchmark completed inference in
`config/benchmarks/background-removal/acceptance-100`. All 300 local outputs and
100 Adobe baselines passed integrity, alpha and native-dimension checks. It uses
the seed-42 manifest and visually screened category labels for difficult examples,
including two partially cropped heads inspected at full resolution. All sources
remain unverified. The owner subsequently reported reviewing all 100 and finding
Portrait the same as or better than Adobe. Individual review choices in the
generated report remain blank because no per-image win/tie split was provided.

A final read-only pass with the current backend validated 300/300 local outputs
under strict RGBA/nonuniform-alpha/native-dimension rules, with zero hash,
configuration or model-identifier mismatches and 100/100 source snapshots
unchanged. Details are in `reports/current-backend-validation.json`.

### Full 100-Image CPU Measurements

| Model | Valid / Attempted | Mean Seconds | Median Seconds | Peak RSS GiB |
| --- | ---: | ---: | ---: | ---: |
| BiRefNet Portrait | 100 / 100 | 26.93 | 25.55 | 13.61 |
| BiRefNet General | 100 / 100 | 24.15 | 23.73 | 13.59 |
| ISNet General | 100 / 100 | 5.09 | 4.92 | 2.43 |

Measurements use `OMP_NUM_THREADS=4` on Windows x64 Python 3.13.15, eight logical
CPUs and 32 GiB physical RAM. RSS is sampled total process memory, including
initialization and allocator retention, not isolated model allocations. General
emitted a numerical sigmoid-overflow warning during the run; its outputs passed
validation, but human inspection is still required. The current backend captures
inference warnings in per-image logs and provenance; the earlier running benchmark
did not identify the warning's image, so no per-image attribution is invented.

Heuristic flags are inspection aids, not confirmed defects: possible clipping
was flagged on 98 Adobe, 98 Portrait, 98 General and 97 ISNet samples, largely
because shoulders contact canvas edges. Possible halos were flagged on 3, 11,
7 and 3 respectively. These counts do not establish a model's quality advantage.

### Initial Three-Image CPU Measurements

These are smoke measurements, not final acceptance results or quality wins.
RAM figures are sampled **total process RSS**, including initialization and
allocator retention between models; they are not isolated model allocations.

| Model | Images | Mean Seconds | Median Seconds | Peak RSS GiB |
| --- | ---: | ---: | ---: | ---: |
| BiRefNet Portrait | 3 | 32.85 | 34.51 | 8.97 |
| BiRefNet General | 3 | 32.44 | 27.45 | 13.55 |
| ISNet General | 3 | 4.77 | 4.74 | 2.26 |

Default ONNX threading was used for those measurements. A separate four-thread
Portrait run took 28.82 seconds on one image, with 9.06 GiB process RSS. The full
sample uses `OMP_NUM_THREADS=4`. Allow roughly 16 GiB free RAM for BiRefNet and
additional memory for the operating system/other applications. Model weights use
about 973 MB each for Portrait/General and 179 MB for ISNet.

## Reproduce the Benchmark

Commands below run from `create_people_posters`. Supply your local clone paths;
the tool accepts relative or absolute paths. It does not need GitHub credentials.

```powershell
$env:OMP_NUM_THREADS = '4'
.\.venv-rembg\Scripts\python.exe compare_background_removers.py `
  --originals 'C:/path/to/Kometa-People-Images/original' `
  --adobe 'C:/path/to/Kometa-People-Images/transparent' `
  --output config/benchmarks/background-removal/new-run --limit 100 --seed 42 `
  --kometa-background 'config/people_dirs/base/@zbase-People.jpg'
```

```bash
OMP_NUM_THREADS=4 .venv-rembg/bin/python compare_background_removers.py \
  --originals /data/Kometa-People-Images/original \
  --adobe /data/Kometa-People-Images/transparent \
  --output config/benchmarks/background-removal/new-run --limit 100 --seed 42 \
  --kometa-background 'config/people_dirs/base/@zbase-People.jpg'
```

Use `--prepare-only` to create the manifest without inference. Reproduce the exact
sample with `--sample-manifest PREVIOUS/reports/sample-manifest.json`; the selected
source and Adobe hashes must still match. Use a separate `--output` for a new run.
`--categories categories.json` supplies reviewed image labels and `priority` flags,
and can override labels when replaying a manifest. A category file has this shape:

```json
{"images": [{"original": "A/Images/Example Person.jpg", "categories": ["eyeglasses", "fine hair"], "priority": true}]}
```

`--all` is required for full-library selection. `--models isnet-general-use` runs
only the small baseline. `--overwrite` explicitly regenerates local benchmark
outputs. `--clone` is the only mode that clones missing reference repositories.
Benchmark outputs and model caches must not overlap reference/staging/production
directories; generated assets are ignored by Git.

### Update Local Environments

From `create_people_posters`, apply the complete compatible dependency set to
each existing environment, then check it:

```powershell
foreach ($environment in @('venv', '.venv-ddcolor', '.venv-rembg')) {
  $interpreter = Join-Path $environment 'Scripts/python.exe'
  & $interpreter -m pip install --upgrade -r requirements.txt -r requirements-ddcolor.txt -r requirements-rembg.txt -r ../People-Auto-Readme/requirements.txt
  if ($LASTEXITCODE -ne 0) { throw "Dependency update failed: $environment" }
  & $interpreter -m pip check
  if ($LASTEXITCODE -ne 0) { throw "Dependency check failed: $environment" }
}
.\venv\Scripts\python.exe orchestrator.py --list
# Keep progress output compatible with the orchestrator's UTF-8 log reader.
$env:PYTHONIOENCODING = 'utf-8'
.\venv\Scripts\python.exe orchestrator.py
```

Run the orchestrator from this directory with the venv interpreter. Activating
the environment is optional; using its executable avoids accidentally running
the unrelated system Python. Keep inference/model processing stopped while
changing packages in its active environment.

The isolated validation selected Windows PowerShell 5.1. Read-only font probes passed
for all four fonts at the current production path and 120-column formatting
width, but failed with 80-column wrapping. The smoke's deeper isolated path
required the width wrapper described above. Interactive Python stdout was
UTF-8; piped stdout was cp1252 without the explicit environment setting. These
are host/output constraints, not missing venv dependencies.
The owner's subsequent real run used PowerShell 7.6.6 and passed all font probes.
Portrait processed Andrew Fung Chih-Chiang at 405x607 and BoA at 774x1161; the
unchanged poster script generated all five styles and transparent presentations.
Recovery found no uncropped alternative for BoA. That is a nonfatal exhausted
search, not a model failure; the local-only fatal-exhaustion regression is fixed.

## Review the Results

Open `reports/comparison.html` directly in a browser. The report contains its image
assets and needs no server. It supports checkerboard, white, black and the supplied
Kometa background. Select a portrait image to inspect its original resolution.
Diagnostics flag coverage, soft alpha, mask IoU/disagreement, possible halos and
edge contact. Face-crop checks are optional and require a cached detector; they
do not download it implicitly. Adobe masks are not ground truth.

Choose a review outcome and add notes. Export JSON/CSV for durable storage;
browser storage alone is not a portable record. Import reviews back into HTML or
regenerate aggregate data with `--report-only --reviews /path/to/reviews.json`
using the same source sample and output folder. Generated output paths are still
checked and cannot replace the input review/manifest files.

The owner reviewed all 100 images and approved Portrait for the production trial.
No individual review choices were supplied, so numerical wins/ties are not
invented and report aggregates remain unreviewed until those choices are imported.
Verified and unverified groups have separate counts, defect statistics and wins.
For verified comparisons, provide the exact submitted source plus a provenance
manifest with source/Adobe/evidence hashes and a submission attestation; see
`compare_background_removers.py --help` for its schema. Filenames alone cannot
verify colorization or transformations before Adobe processing.

## Remaining Acceptance Work and Limits

The owner requested local-only testing before deciding what to publish. Both
`config/.env` and `.env.example` select `REMOVE_BG_ENGINE=birefnet` with
`REMOVE_BG_MODEL=birefnet-portrait`. The orchestrator and Original sync use the
same default when the engine setting is absent. Adobe remains explicitly
selectable with `REMOVE_BG_ENGINE=adobe`; its code, profiles and dependencies
are retained. After local testing, the owner requested merging all work into
local `main`. The snapshot includes the implementation, tests and documentation;
private configuration, environments, model caches and benchmark images remain
untracked. Online publication remains deferred.

The owner's 100-image review and explicit approval support this trial default
switch. The source-unverified run can guide inspection but cannot prove
a model is better than Adobe. The production repositories use normalized
2000x3000 images; varying original capture resolutions still need a deliberately
documented acceptance set.
The category labels came from source previews, not completed edge-quality reviews.

Linux/macOS, GPU providers and live Adobe authentication have not been tested.
The PowerShell poster/sync/push workflow was not run against reference repositories.
Recovery and checkpoint handoffs were tested with mocked external tools. Local
inference retains native dimensions, while existing style generation and the
local-only Original presentation conversion satisfy the 2000x3000 publication
contract. Native-format sync tests use isolated temporary destinations and verify
archive preservation, exact-copy compliant JPEGs, collisions and history exclusion.
Unrelated existing workflow risks are documented in BACKGROUND_REMOVAL_AUDIT.md.

rembg's optional CLI/Gradio server stack is excluded from base requirements to
allow the current DDColor and pinned inference profiles to install together. The
pipeline uses rembg's Python API; Adobe Selenium dependencies are retained.
Code/model licensing references and rollback instructions are in README.md.
