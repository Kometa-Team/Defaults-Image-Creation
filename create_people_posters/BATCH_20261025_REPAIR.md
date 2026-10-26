# Failed People batch investigation and local repair

Batch: `20261025T112600-14b8bdba9a34`. This is a local proposal; no publication,
push, production batch creation, original checkpoint deletion or original-batch
mutation was performed. Test/simulation fixtures are separate. The unrelated
existing worktree changes were left alone.

## Findings and evidence

* TMDB `15370` is **recoverable**, not an invalid ID or a missing profile.
  Read-only live person details returned Gretchen Mol with a primary profile;
  downloading that profile decoded as RGB, 1280×1920. The old SDK call
  `person(15370)` reproducibly follows tagged-image movie metadata into
  `/genre/movie/list`, which the deliberately restricted `SecureTMDBSession`
  does not support. That raises `ValueError`. The downloader's broad
  `except ValueError` confused this with integer parsing and searched the
  numeric ID as a name. A subsequent exception was swallowed and the TMDB step
  exited successfully, leaving `tmdb.done.json` despite an unresolved selection.
  The repair uses `person(id, partial=None)` to load the same primary profile
  without unrelated credits/tagged media. The transport allowlist is unchanged.
  Both the failure and repaired call are tested using the real installed SDK
  and offline responses. The repaired call also passed a live read-only probe.
* The historical TMDB record retains correlation
  `b2fbc943a64c46f6bd14ab342ffe6b00`. The historical exception type/cause was
  discarded, so the old record itself cannot establish every exception in that
  run. No network failure needs to be assumed to explain the reproduced defect.
* Natachai's JPEG SHA-256 is
  `bd0d40620724ab176cd942d8f9eeb11845555f94fb7e795ae3a87db948247fce`.
  Pillow verification, full decode and RGB conversion succeed. It is RGB,
  1031×1548, one frame, with no EXIF orientation tag. The implementation preserves
  stored dimensions because staging owns orientation. The installed rembg
  preprocessing converts/resizes to RGB 1024×1024, normalizes channels and passes
  float32 NCHW input to the local ONNX session. No preprocessing or model setting
  was changed by this repair.
* Isolated inference and PNG writing passed with the original rembg 2.0.85,
  CPU, decontamination enabled, alpha matting disabled, and the exact
  `birefnet-portrait` model hash
  `1ba1c8ff5a7bbfadc8d8d13fb11d7be793f91f23d9d466549e37a854f6668f99`.
  Natachai also passed after Fuka and Joo in the original processing order.
  The resulting PNG SHA-256 was
  `3d5e5473729b1861deb35c9e07679a43a72f7f09e70acd5bc041a0be63a77195`.
  Both isolated runs produced the same bytes. Fuka's and Joo's diagnostic PNGs
  exactly match their successful batch PNGs:
  `e86b8ce5b8d734366e1ccdf2c895ba1309ff3769421cc1f54cb265ca1bcc13fc`
  and `a485768c1956907bd5188729a9b7b1606fd4b5a08ddf09f29241e0c193b378de`.
* Natachai's historical 1.946-second failure remains **unknown and retryable**.
  Correlation `c1cdcdb9059f4e5c97785199e304c7e2` was preserved. The old diagnostic
  discarded its exception type, stage and cause chain; elapsed time cannot
  establish inference failure, resource exhaustion or a filesystem fault.
  None of those faults reproduced, and the successful image probes do not prove
  what happened historically. No workaround to the model, image or environment
  is justified by the available evidence.
* The orchestrator correctly stopped on the background stage's exit code 1;
  no background success checkpoint or generation/publication followed. The
  publication database has zero batch/publication/README/baseline records for
  this batch. Its job remains failed. Neither `15370`, Gretchen Mol nor Natachai
  appears in the persistent exhausted-name list. There are seven upstream
  checkpoints. All 30 original workspace files were SHA-256 inventoried and
  remain unchanged, including logs, errors, inputs, sidecars and successful PNGs.

Local diagnostic artifacts are under
`config/validation/failed-batch-20261025/`: `tmdb-probe.json`,
`tmdb-narrow-probe.json`, `image-probe.json`, `sequence-probe.json`,
`state-probe.json`, and separately named inference PNGs. No probe wrote into
the managed batch. These local evidence files are ignored by Git.

`retry-simulation.json` records a separate fixture run with network calls
forbidden and only new model inference mocked. The actual downloader, filename
normalizer, audit, directory preparation and background handoff ran against
copied inputs/artifacts. Only Gretchen was looked up and downloaded; only
Gretchen/Natachai reached inference. Fuka/Joo artifact bytes were unchanged.
A second background pass skipped all four. This fixture had no managed manifest
or job registration. `scope-audit.json` records the final worktree, protected
membership, renderer/resource/dependency and original-batch hash checks.

## Behavior and safety decisions

Failure records contain a category, sanitized exception type, operation, input
identifier, bounded safe cause types and stack locations, retryability, action
guidance and stable correlation ID. They never serialize exception messages,
request/response objects, headers, locals or credential-bearing URLs. Known
HTTP status/transport diagnostics remain available. ONNX allocator signatures
can identify resource exhaustion without emitting provider text. Unknown
exceptions remain retryable and are never permanent person misses. A positive
HTTP 404 is distinguished from a transport failure; a missing profile is an
explicit unresolved result, with no invented exception.

TMDB writes incremental per-input receipts and returns nonzero for unresolved
people. Numeric failures cannot fall back to name search. Numeric retries reuse
identity-bound retained inputs, including the three existing inputs in this
batch. Name search retains its configured result depth and isolates failures
between selected matches. `PERSON_DEPTH=0` still selects no name-search results;
this patch does not expand the selected set. New downloads retain an additional
byte-for-byte copy under `input/tmdb/`, using atomic creation without replacement.
Existing different bytes cause a conflict rather than an overwrite.

TMDB and background removal process unrelated inputs within their stage after
a per-person failure. The stage then fails as a whole. This proposal deliberately
retains the existing barrier before downstream rendering: the renderer consumes
shared staging files, so continuing after a failed background stage requires a
separate design to select only verified cutouts. It does not silently render or
publish a partial set. Resuming reuses successful inputs and PNG checkpoints.

Publication now additionally rejects unresolved TMDB/background receipts and
explicit selections without matching identities and all seven local styles.
This closes the legacy false-success checkpoint case, including direct resumes
at sync/push and direct publisher preparation. Existing already-complete remote
selections and depth-zero name selections retain their no-local-work behavior.
Existing image quality, immutable plan, hash verification and seven-repository
rules remain in place. The repositories and `master` targets are unchanged.
No renderer source, font, asset, poster normalization or output setting changed.

Retries append logs and preserve the previous JSON summary under
`logs/history/<summary-name>-<sha256>.json`, retaining historical correlations
before replacing the latest receipt. No exhausted-name records are written by
these stages.

`--redo remove_bg` retains upstream checkpoints, clears the background and
downstream completion markers, and reruns background removal. It does not by
itself require overwrite. Matching settings/output hashes reuse staged PNGs;
matching source/model/settings/output provenance reuses existing backend
outputs. Different or unknown provenance requires restaging the exact source
and an explicit `REMOVE_BG_OVERWRITE=true`. That opt-in is **not needed** for
the matching successful PNGs in this batch, and would defeat preservation if
applied indiscriminately. Background-only retry cannot fix the missing Gretchen
lookup; publication will remain blocked until the whole selection is repaired.

The marker review found and repaired another local defect: `clear_from()` used
`colorize.done.json`, while the registered file is `colorize_noncolor.done.json`.
`--redo tmdb` now clears the actual colorize checkpoint and the legacy
`colorize.done.json` if present. Both the existing DDColor compatibility test
and a new orchestrator regression verify clearing and preservation behavior.

For this existing batch, the exact completion-marker effects are:

| Command | Existing completion files cleared | Existing completion files retained |
| --- | --- | --- |
| `--redo tmdb` | `tmdb.done.json`, `truncate.done.json`, `audit_people_images.done.json`, `colorize_noncolor.done.json`, `prep_dirs.done.json` | `scan_kometa_logs.done.json`, `find_and_download_missing.done.json` |
| `--redo remove_bg` | None currently exist at or after that stage | All seven upstream completion files |

Both redo operations also target downstream completion files if present:
`remove_bg.done.json`, `poster_ps1.done.json`, `recover_edge_chops.done.json`,
`sync_images.done.json`, `readme.done.json`, `sync_md.done.json`. All are absent
in this batch. `update` and `push` are always-run steps without registered
completion files; the helper also checks their absent legacy `update.done.json`
and `push.done.json` paths. Sidecars, native inputs, inference PNGs, error
histories and `poster-inputs.json` are not removed by `--redo`. There are no
pending fingerprint markers in this batch.
The legacy short colorize marker is absent here; compatibility with that name
does not add another existing file to the five-marker removal list.

Pillow auditing uses `get_flattened_data()` when available and falls back to
`getdata()` for older installations. Thresholds, pixel ordering and mode
classification are unchanged.

## Exact proposed recovery commands (not executed)

Run from the repository root **after approving checkpoint invalidation**.
`--redo tmdb` deletes that step's and downstream completion markers; this is
why these commands were not executed under the instruction to retain existing
checkpoints. The original input list and batch ID are reused. Automatic cleanup
is disabled. The first command stops after background removal, before rendering,
alternate recovery, synchronization or publication.

```powershell
$env:PEOPLE_CONFIG_DIR = (Resolve-Path '.\create_people_posters\config').Path
$env:PEOPLE_JOBS_DIR = Join-Path $env:PEOPLE_CONFIG_DIR 'jobs'
$env:PEOPLE_STATE_DIR = Join-Path $env:PEOPLE_CONFIG_DIR 'state'
$env:REMBG_HOME = Join-Path $env:PEOPLE_CONFIG_DIR 'models\rembg'
$env:REMOVE_BG_PYTHON = (Resolve-Path '.\create_people_posters\.venv-rembg\Scripts\python.exe').Path
$env:PEOPLE_AUTO_CLEANUP = 'false'
$env:REMOVE_BG_OVERWRITE = 'false'
$env:REMOVE_BG_ENGINE = 'birefnet'
$env:REMOVE_BG_MODEL = 'birefnet-portrait'
$env:REMOVE_BG_DEVICE = 'cpu'
$env:REMOVE_BG_DECONTAMINATE = 'true'
$env:REMOVE_BG_ALPHA_MATTING = 'false'
& .\create_people_posters\venv\Scripts\python.exe .\create_people_posters\orchestrator.py --batch-id 20261025T112600-14b8bdba9a34 --workspace-mode batch --publish-mode github_api --branch master --redo tmdb --stop-after remove_bg --no-recover-edge-chops
```

Expected: three retained TMDB inputs reused, Gretchen downloaded, Fuka/Joo
cutouts skipped unchanged, Gretchen/Natachai processed. Normalization, auditing,
the colorize check and staging run again for the newly downloaded Gretchen input.
They do not redownload or rerun inference for Fuka/Joo. If retry fails again,
successful artifacts remain retained and publication is blocked. Another retry
verifies/reuses matching artifacts; different bytes/provenance require review
rather than implicit replacement. This is safe and idempotent for the verified
settings, but cannot guarantee the historical unknown exception will not recur.

After reviewing all four cutouts and approving local generation, resume without
another redo:

```powershell
& .\create_people_posters\venv\Scripts\python.exe .\create_people_posters\orchestrator.py --batch-id 20261025T112600-14b8bdba9a34 --workspace-mode batch --publish-mode github_api --branch master --stop-after poster_ps1 --no-recover-edge-chops
```

The established renderer produces seven styles per selected person. It consumes
the staging PNG copies in `people_dirs/Downloads`, retains the backend PNGs and
sidecars in `sel_downloads`, and relocates native photographs into
`original/<letter>/Images/` without changing their bytes. This behavior is
unchanged. It skips previously rendered people when source/output hashes and
the renderer fingerprint match. This batch has no rendered poster checkpoint,
so its first generation would render all four people. Review receipts, generated
styles and artwork before separate publication approval. No publish/push
command is proposed here.

For an independently approved background-only retry with the same environment:

```powershell
& .\create_people_posters\venv\Scripts\python.exe .\create_people_posters\orchestrator.py --batch-id 20261025T112600-14b8bdba9a34 --workspace-mode batch --publish-mode github_api --branch master --redo remove_bg --stop-after remove_bg --no-recover-edge-chops
```

This should reuse two cutouts and process Natachai, but leave Gretchen unresolved.

## Changed files

Pipeline: `tmdb_people.py`, `remove_bg_birefnet.py`, `audit_people_images.py`,
`orchestrator.py`, `publish_people_github.py`, `people_diagnostics.py`,
`people_http.py`; added `people_failures.py` and `people_batch_safety.py`.

Tests: added `tests/test_people_pipeline_failures.py`; extended
`tests/test_people_http_security.py`, `tests/test_tmdb_sdk_configuration.py`,
`tests/test_people_api_orchestrator.py`, `tests/test_remove_bg_birefnet.py`,
`tests/test_background_orchestrator.py`.
This report is `BATCH_20261025_REPAIR.md`.

Required CI source maintenance: `ci/people-security-test-ids.json`,
`ci/people-security-maintenance.json`, `ci/people_security_maintenance.py`,
`create_defaults/bulk/contracts/activation/data/production-pins-v1.json`,
`create_defaults/bulk/contracts/activation/protection.py`. These register the
new regression tests and refresh exact source fingerprints. The original test
selection, all 190 protected source memberships, historical baseline hashes,
CI groups and nonactivation rules are retained. No production activation was
enabled.

There are 17 intended tracked modifications and four intended new files (21
repair files). Git also shows the pre-existing deletion of `People-Auto-Readme`
and pre-existing modernization/Plex work files; those are not this repair and
were not changed. Intended/inherited path lists are in `scope-audit.json`.
`git diff --check` passes.

## Separate cross-project dependency check

The initial missing `uharfbuzz` import was environment-only: the check used
`.venv-rembg`, which is not the cross-project CI environment.
`create_defaults/requirements.txt` already pins `uharfbuzz==0.56.3` and
`python-bidi==0.6.11`; `requirements-bulk.txt` includes it, and the workflow
installs `requirements-bulk.txt` for the relevant CI jobs. Pinned copies of
these two packages were installed only in the ignored validation directory,
with a process-local `PYTHONPATH` for those checks. The CI integrity, workflow
and protection tests then passed. No project dependency, workflow, rembg
environment or poster renderer dependency was changed.

## Validation

| Check | Passed | Failed | Skipped | Duration |
| --- | ---: | ---: | ---: | ---: |
| Final full People suite (959 collected) | 949 | 0 | 10 | 739.17 seconds (12:19.17) |
| CI integrity, workflow and production-protection controls | 137 tests + 35 subtests | 0 | 0 | 271.29 seconds |
| Registered/legacy marker clearing and focused retry regressions | 29 | 0 | 0 | 24.15 seconds |
| Sanitized diagnostics, stable correlation IDs and security regressions | 153 | 0 | 0 | 17.86 seconds |

The combined cross-project CI check uses `--import-mode=importlib` because two
existing modules are both named `test_validation.py`. CI normally runs them in
separate groups; this invocation option avoids a local combined-collection name
collision without modifying project configuration.

An earlier full run exposed the legacy short colorize-marker compatibility
failure (948 passed, one failed, 10 skipped in 797.87 seconds). That defect was
corrected, both marker cases passed the focused check, and a fresh full run
uses frozen final source. Earlier run artifacts are retained separately.

The final full run has no errors or xfails. Its 10 existing skips are eight
Windows symlink privilege cases, the opt-in background-report browser check,
and the opt-in cached-model smoke case. The separate real BiRefNet probes above
provide actual cached-model inference evidence. The 20 warnings originate from
the unchanged `edge_chop.py:162` use of `getdata()`; auditing's deprecated call
is fixed and its compatibility regression passes. This remaining edge-chop
deprecation is separate maintenance, not a functional test failure.

Final logs and JUnit reports: `people-tests-final.txt`/`.xml` and
`ci-final.txt`/`.xml` in the evidence directory. `validation-summary.json`
reconciles the totals and final batch/ledger/source-seal checks. Source
compilation and `git diff --check` also pass. These are local Windows results;
no hosted GitHub CI or publication was started.

Remaining limits: Natachai's historical exception cause cannot be reconstructed
from the discarded evidence; retry may expose a new actionable failure. Live
TMDB data and remote branch heads can change before approved recovery. Different
artifact provenance or filesystem/resource failures must be reviewed rather
than bypassing overwrite/completeness safeguards. The original batch remains
failed and intact until explicit recovery approval.
