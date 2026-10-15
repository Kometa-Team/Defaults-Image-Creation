# Offline Model Smoke Test

`smoke_people_models.py` is an explicitly opt-in integration check, separate
from the orchestrator and unit tests. It requires an existing genuine grayscale
photograph, cached DDColor source/weights and cached BiRefNet Portrait weights.
It does not desaturate a color image to manufacture an input.

## Run

From `create_people_posters`, with the normal dependencies installed:

```powershell
.\venv\Scripts\python.exe -u smoke_people_models.py --run --input 'config/vendor/DDColor/assets/test_images/Audrey Hepburn.jpg'
```

The example is the native grayscale photograph in the existing DDColor vendor
checkout. Another grayscale photograph can be supplied with `--input`.
On macOS/Linux, use the normal environment's `python` for the same script and
arguments. Without `--run`, no inference or temporary workspace is created.

By default DDColor runs in `.venv-ddcolor` and removal/rendering in `.venv-rembg`
(Windows `Scripts/python.exe` or POSIX `bin/python`). When an environment is
absent, the current interpreter is used. Override interpreters/cache paths when
needed:

```powershell
python smoke_people_models.py --run --input 'path/to/grayscale.jpg' --ddcolor-python '.venv-ddcolor/Scripts/python.exe' --rembg-python '.venv-rembg/Scripts/python.exe' --vendor-dir 'config/vendor/DDColor' --model-dir 'config/models/ddcolor/ddcolor_modelscope' --rembg-home 'config/models/rembg'
```

The parent reads existing `config/.env` path/device settings without changing it.
`--model-dir` points directly at the directory containing `config.json` and
`pytorch_model.bin`. `--rembg-home` is the existing rembg cache root. Stage
networking is disabled, GitHub/TMDB credentials are stripped, and private `.env`
credentials are not reloaded inside the stages. There are no downloads or
publishing calls. Install dependencies/cache models separately before testing;
the test does not install or alter them. Each stage has a 1,800-second default
timeout, overridable with `--timeout`.

## Evidence And Artifacts

Each invocation creates a unique directory under `config/smoke-tests` (override
with `--workspace-root`). It preserves the original source and verifies its
SHA256 and modification time afterward. Only isolated staging copies are
consumed by the existing renderer. Normal pipeline workspaces, historical
`people_dirs`, repositories and model weights are not cleaned or modified.

The terminal prints the workspace, each stage and final status. Inspect:

- `summary.json`: status, source preservation, model identities and stage results.
- `ddcolor.json`: actual model forward-call count, finite tensors, dimensions,
  measurable output chroma, versions and timing.
- `rembg.json`: actual ONNX invocation count, alpha/size checks and model hash.
- `render.json`: Python/Pillow processing result and all seven output hashes.
- `colorized.jpg`, `transparent.png`, and `poster-job/people_dirs`: local outputs.
- `ddcolor.log`, `rembg.log`, `render.log`: dependency/model errors and diagnostics.

Exit code is zero only if all stages and source-preservation checks pass. A
missing interpreter/package/cache, invalid output or timeout leaves a failed
summary and logs. Check the stage's interpreter and existing requirements files
(`requirements-ddcolor.txt`, `requirements-rembg.txt`, `requirements.txt`) rather
than installing into an unrelated environment. Test artifacts are deliberately
retained for inspection, are Git-ignored by the existing config rules, and are
outside receipt-based production job cleanup. Remove only the specific printed
smoke directory after review when no test is using it.

## Local Execution Result

Validated on October 15, 2026, using the vendored Audrey Hepburn grayscale
photograph (915 x 1210), without changing the inference algorithms or renderer:

| Stage | Result |
| --- | --- |
| DDColor | One real forward call, finite output; 915 x 1210 RGB JPEG; mean channel spread 28.592 and 88.46% colored pixels; 20.877 seconds |
| BiRefNet Portrait | One real ONNX call; valid 915 x 1210 RGBA output; 47.215 seconds including loading/validation |
| Python/Pillow | One person, zero failures, all seven outputs; 9.160 seconds; six formatted styles at 2000 x 3000 |

DDColor used CPU, torch 2.14.1+cpu and torchvision 0.29.1+cpu; rembg was 2.0.85.
No missing dependencies or model issues were encountered. Source hash/time were
unchanged and stage networking was disabled. This verifies actual inference and
pipeline compatibility, not aesthetic approval of the colorization.

The local evidence is in `config/smoke-tests/ddcolor-iefpyyw8/summary.json` and
its sibling logs/outputs. Generated artifacts and cached model binaries are not
included in source control.

## Regression Check

From `create_people_posters` on the same local checkout:

```powershell
.\.venv-rembg\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

Result: **595 passed, 5 skipped**, in 733.90 seconds. The run emitted 20 existing
Pillow `Image.getdata()` deprecation warnings from `edge_chop.py`; that code was
not changed. The focused workspace/orchestrator/model-test group also passed
(125 passed, 1 skipped). These unit/regression tests do not replace the opt-in
real inference command above. The full local test log is retained at
`config/renderer-comparison/pytest-launch-cleanup.log`.
