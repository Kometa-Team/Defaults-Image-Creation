# Background Removal Workflow Audit

Reviewed 2026-10-14 from `C:\Users\bullmoose20\Defaults-Image-Creation`.
Repository HEAD at review: `90f477a540b16bf02ad152193423b2bf417c1e6b`.

Historical snapshot: the sweeper defect recorded below is repaired by the
2026-10-22 maintenance follow-up at the end of this document. The original
observations and other findings are retained; this is not a recertification
of background removal, colorization or the orchestrator.

This is a source audit, not a successful processing-run certification. The six
requested scripts, both repository/people READMEs, both people requirements files,
and `tests/test_ddcolor_colorizer.py` were read. Supporting orchestration,
colorization, QA, and recovery helpers were inspected where they affect those
contracts. No pipeline, browser, model download, dependency install, or test suite
was run. Only this report was created by the audit.

Concurrent work changed `orchestrator.py`, `recover_edge_chops.py`, `.gitignore`,
and `.env.example`, and added a BiRefNet backend, requirements, and tests during
review. That work was not made by this audit. The six requested script contracts
and supporting Adobe recovery findings refer to the reviewed HEAD snapshot;
supporting-file line references also refer to that HEAD, not shifting lines in
the concurrent working tree. Observations explicitly labeled concurrent describe
the code seen during review, not a certification of the evolving BiRefNet work.

## Findings

| Priority | Finding | Evidence and consequence |
| --- | --- | --- |
| P1 | Standalone recovery checks and deletes against the scan root, not the generated work root. | `recover_edge_chops.py:83` defaults `people_root` to `PEOPLE_IMAGES_DIR`; `:1267` stages into local Downloads; `:871` launches the normal orchestrator. The poster script always writes local `config/people_dirs` (`create_people_poster.ps1:113`). But postcheck reads `args.people_root` (`recover_edge_chops.py:894`) and unresolved cleanup deletes there (`:925`, `:1656`). With separate clone/work roots, a fixed new image can be marked unresolved by examining the old clone image; cloned style files can be deleted while failed generated work files remain eligible for later sync. The inline call from the orchestrator explicitly supplies the local work root, so it avoids this particular default-root mismatch. |
| P1 | Accepted inline Adobe recovery loses the original-style source. | `style_file_paths` includes the local original (`recover_edge_chops.py:793`), and `recover_one` removes it (`:1005`). Adobe archives the alternate into temporary `sel_original` (`:981`, `:989`); only the generated PNG is copied back into normal staging (`:1080`). The accepted path returns without restoring/copying a local original (`:1115`). TemporaryDirectory then removes the retry archive and backup. This can leave five regenerated styles and a transparent PNG with no corresponding local original JPG. |
| P1 | Successful partial Adobe batches can checkpoint incomplete work. | `sel_remove_bg.py:2327` returns zero when both OK and ERROR results exist. Resize failures are SKIPPED (`:2104`), and skips do not make the final return fail (`:2331`). The orchestrator accepts zero, checks activity rather than per-source success, then writes `remove_bg.done.json`. Pending JPGs can remain while later posters/sync/push proceed. Resume must explicitly redo remove_bg. |
| P1 | Replacement operations are destructive and not a transaction. | Prep unlinks an existing destination before `replace` (`prep_people_dirs.py:79`); Selenium unlinks the old SRC PNG and archived JPG before moving replacements (`sel_remove_bg.py:2183`). A move failure can lose the old destination. The PNG move and original archive move are separate: PNG placement can succeed while archive movement fails. Prep logs failed moves/deletes but still exits normally. |
| P1 | Poster generation can discard inputs after native rendering failures. | Most ImageMagick commands do not inspect exit status; only font probes and canvas normalization do. The main loop calls all five renders then deletes source/temp PNGs (`create_people_poster.ps1:919`, `:925`). PowerShell nonterminating file errors also are not converted into an aggregate failure. Missing ImageMagick uses bare `exit` (`:788`), which does not explicitly signal failure. Do not equate a completed poster step with five verified outputs per input. |
| P2 | Download acceptance is not tied to the current person. | `sel_remove_bg.py:1914` chooses changed files by modification time; `:1963` can select an existing final file when a baseline `.crdownload` disappears. Acceptance checks PNG structure, not source identity, alpha, dimensions, or a completed-download stability window (`:1884`). A shared download folder, delayed prior download, or overlapping run can misattribute a PNG. Changed non-PNG/invalid downloads are deleted by the acceptance helper. |
| P2 | Timestamp-only sync can suppress replacements or modify skipped files. | `sync_people_images.py:68` copies only when source mtime is strictly greater. Different bytes with equal/older mtime are skipped. Destination transparent normalization also runs in the skipped branch (`:307`), and saving changes destination mtime. This can make future source updates lose the timestamp comparison. Git update/reset runs before sync, so newly materialized checkout files are another possible newer destination. A zero-copy run can still change destination PNG bytes; the orchestrator's zero-copy early exit can then omit push. |
| P2 | Color-required styles can inherit a grayscale intermediate. | Diiivoy converts the shared `_pushed.png` to grayscale in place (`create_people_poster.ps1:610`, `:618`). Diiivoycolor and rainier run afterward (`:922`). If the original foreground offset is already at least 500px, `Push-Down` neither rebuilds the existing intermediate nor replaces it (`:752`, `:764`), so those styles reuse the grayscale image. Sync treats grayscale as warning-only, allowing these files through. |
| P2 | QA can report misleading success and stale results. | `image_check.py:244` logs open/process failures without a dedicated issue count; it scans only expected extensions (`:249`) and never returns failure for findings (`:362`). Compare also exits normally for findings/missing trees, silently ignores non-JPG/PNG files (`compare_image_trees.py:262`), and writes dimension/quality CSVs only when issues exist (`:895`, `:928`). Old issue CSVs remain after a clean or disabled check. Neither tool is a publication gate. |
| P2 | The non-color sweeper is unusable in this snapshot. | Read-only AST parsing confirms an unterminated string at `grayscale_sweeper.py:128`; later indentation is also visibly damaged. README examples additionally use `--root`/`--dest` (`README.md:787`), while the intended parser declares `--src`/`--dest-other` (`grayscale_sweeper.py:121`). |
| P2 | Path/environment defaults do not compose automatically. | Prep resolves `POSTER_DIR` before dotenv (`prep_people_dirs.py:15`, `:38`); standalone `.env` changes cannot affect that value. Selenium defaults SRC to CWD, not local people Downloads (`sel_remove_bg.py:88`). Custom `SEL_SRC_DIR`/`SEL_ORIG_DIR` are not consumed by the poster or sync scripts. DDColor standalone does not load `.env` at all (`colorize_noncolor_ddcolor.py:34`). These overrides require coordinated staging or inherited process environment. |

P1 identifies output-loss, invalid-publication, or incomplete-workflow risks; P2
identifies correctness and operability risks. These are code-supported paths,
not claims that production assets were damaged during this audit.

## Paths and File I/O Contracts

Let `S` be this report's directory, `C = S/config`, `W = C/people_dirs`, and
`R` the external folder containing the seven style repositories. The repository
root's `config` directory is distinct from `C`. Unless explicitly expanded,
relative environment/CLI paths resolve against the process working directory.
Orchestrator subprocesses run with `cwd=S`; standalone commands launched from
the user's stated repository-root CWD do not.

### Preparation and source colorization

- `prep_people_dirs.py:94` creates `W` and `W/Downloads`, deletes every immediate
  file in `POSTER_DIR` (default `C/posters`, no extension filter), then moves every
  immediate file from `C/Downloads/color` and afterward `C/Downloads/other` into
  `W/Downloads`. It does not recurse, reject nonimages, normalize image formats,
  or clear old files already in `W/Downloads`. Same-name `other` files overwrite
  the `color` files moved earlier. Return counts describe discovered files, not
  successful operations; the supposed leftover cleanup only runs when the source
  list was empty (`:110`). It is not a retry/rollback mechanism.
- The upstream `audit_people_images.py:108` classification calls an image color
  if any RGB channel difference exceeds 30; otherwise it stages under `other`.
  `:194` and `:201` copy original bytes into a filename ending `.jpg`, without
  transcoding. Some staged `.jpg` files can therefore contain another image format.
  It deletes source files whose names are already in the online list (`:179`).
- DDColor consumes immediate supported image files in `C/Downloads/other` and
  writes `C/Downloads/color/<stem>.jpg`, unless process-env overrides redirect
  them. It preserves EXIF-oriented dimensions and validates JPEG decoding/size
  before deleting the source (`colorize_noncolor_ddcolor.py:325`). Existing
  decodable JPEGs of matching size are reused and cause source deletion (`:367`);
  validation does not establish that they are actually colorful or derived from
  the current source. Model inference loads once per pending batch. A failed
  conversion/source deletion exits 1, so the normal orchestrator stops before
  prep can move a remaining non-color file over its colorized counterpart.
- Prep's input folders are fixed. Redirecting `COLORIZE_OUTPUT_COLOR` does not
  redirect prep. The archived downstream `original` can be a colorized and
  resized source, not the original TMDB download or original grayscale bytes.

### Adobe removal: exact handoff

Source: `sel_remove_bg.py:87`, `:1993`, `:2073`, `:2183`.

```text
SEL_SRC_DIR/<name>.jpg
  -> optional in-place EXIF-oriented resize to SEL_EXPECT_WIDTH x SEL_EXPECT_HEIGHT
  -> uploaded to Adobe Express
  -> Chrome downloads an Adobe-named PNG into SEL_DOWNLOAD_DIR
  -> downloaded file is verified as a PNG
  -> MOVE downloaded file to SEL_SRC_DIR/<same-name>.png
  -> MOVE resized source JPG to SEL_ORIG_DIR/<same-name>.jpg
```

`SEL_DOWNLOAD_DIR` is a transient browser landing directory. It is not the final
PNG output directory, and a successful move leaves no corresponding downloaded
file there. Both final names come from the source JPG, not Adobe's filename.
Existing final PNG/archive JPG files are removed first. The archive is initially
flat; the poster script later sorts its JPGs into first-letter subdirectories.

Only immediate `*.jpg` paths are selected. There is no recursive, `.jpeg`, WebP,
or general image input support in this Adobe script. Files not selected remain
untouched. Browser startup occurs even when there are no matching JPGs.

Default source resizing stretches to an exact 2000x3000 rectangle rather than
fitting/cropping/padding while preserving aspect ratio. It saves through a
same-directory `<name>.tmp.jpg` before replacement. An already correctly sized
image is not rewritten; EXIF transpose happens in memory but is not saved on
that early-return path. Failed/skipped source files can already have been resized.

The downloaded PNG is not resized, checked for color, or checked for actual
transparency by `sel_remove_bg.py`. A structurally valid opaque/grayscale PNG can
be marked OK and its source archived. Poster/sync/QA apply later checks.

The script also creates/updates Chrome profiles, removes presumed stale lock
files, edits `Local State`/`Preferences` clean-exit flags, appends
`C/logs/sel_remove_bg.log`, and replaces `chromedriver.log` on browser rebuild.
Missing `C/.env` causes bootstrap plus exit 1, even for `--help`/login-only; its
template search checks `S/.env.example` and the parent, not `C/.env.example`.
Its bootstrap message asks for TMDB_KEY, although Adobe removal does not consume
that key.

### Poster generation and sorting

Source: `create_people_poster.ps1:113`, `:196`, `:714`, `:814`, `:858`, `:896`.

- Always reads immediate `W/Downloads/*.png`; it does not read `SEL_DOWNLOAD_DIR`
  or any environment-selected source folder and has no CLI path parameters.
- Resizes input width to 2000 while retaining aspect ratio, then centers/crops or
  pads on a transparent 2000x3000 canvas. This differs from Adobe source stretching
  and from original recovery's `ImageOps.fit` cropping.
- Copies normalized PNGs to flat `W/transparent` without `-Force`, validates them
  as warnings, and force-moves source PNGs to `W/tmppeople`. A preexisting flat
  transparent copy can prevent the copy while processing still continues.
- Processes every immediate PNG in `tmppeople`, including remnants of an earlier
  interrupted run. Creates five JPEG styles: `bw`, `signature`, `diiivoy`,
  `diiivoycolor`, `rainier`. Four embedded base images are rewritten under `W/base`
  each run. Four bundled font files are probed before rendering; font failure
  exits 2. It uses ImageMagick on PATH, with an IM6 identify/convert fallback.
- `_ccexpress` is removed from styled JPEG filenames, but not from transparent or
  archived JPG names. Trailing digits/parenthesized numeric suffixes are removed
  from display text only, to support duplicate-person aliases.
- Selected styles shift foreground down to reserve 500px at the top, potentially
  cropping the bottom. Signature composites the unpushed source. Temp source and
  `_pushed.png` files are deleted after rendering, without validating all outputs.
- Sorts immediate JPG/PNG files in all seven styles into
  `W/<style>/<uppercase-first-character>/Images/<filename>`, overwriting collisions
  with `Move-Item -Force`. It sorts existing originals but does not generate the
  original JPG from a PNG. Archived JPG creation belongs to Adobe removal.
- Replaces `C/logs/create_people_poster.log`. Final cleanup deletes a CWD-relative
  `tmp.txt` if present (`:1007`), although that file is not created in this script.

### Image sync

Source: `sync_people_images.py:212`, `:260`, `:326`.

Reads seven fixed recursive style trees under `W`; creates corresponding trees
under `R` and preserves basic file metadata with `copy2`. Destination precedence
is `--dest_root`, then `PEOPLE_IMAGES_DIR`, then `S/Kometa-People-Images`.
It does not mirror deletions, verify Git ownership, reject source=destination, or
remove stale destination images. Missing style sources are skipped successfully.

Preflight is enabled by default and scans recognized image suffixes anywhere,
plus every file directly inside a folder named `Images`. Nontransparent styles
require `.jpg` and 2000x3000. Transparent requires `.png` and some alpha below
255, but dimension differences are explicitly allowed as fixable. Grayscale is
warning-only for `original`, `signature`, `rainier`, `diiivoycolor`, `transparent`;
`bw`/`diiivoy` permit it. There are no edge/face checks in sync preflight.

Any blocking source finding aborts before copying any category. This protection
occurs after the orchestrator's Git reset/clean step, not before that reset.
Validation uses Pillow opening/dimensions and subsequent pixel checks; it does
not universally force full JPEG decoding or verify actual encoding equals suffix.

Copying skips `.md` by default but otherwise considers every recursive file,
including nonimage files outside `Images`, and potentially `.git` files if a
clone is mistakenly put inside a source style tree. Empty directories are copied.
Destination transparent PNGs matching source paths are resized to width 2000,
center-cropped if too tall, or vertically centered/padded to 3000, then saved in
place as RGBA PNG. That happens even for newer/equal destination files; unrelated
destination files are not scanned. Wrong sizes in other destination styles are
not repaired. Failure counts return exit 1, but there is no cross-style rollback.
`C/logs/sync_people_images.log` is overwritten on import/run.

### QA output contracts

| Tool | Read contract | Write/exit contract |
| --- | --- | --- |
| `image_check.py` | Required `--input_directory`, recursive `.png` for transparent or `.jpg`/`.jpeg` for other styles. Style is explicit, inferred from path, or defaults to transparent. Checks exact 2000x3000, rounded 2:3 ratio, width >399, height >599, exact grayscale, alpha, selected edge contacts and face risks. | Creates config/log folders and overwrites `C/logs/image_check.log` at import. Writes console summary; no CSV/image rewrite. Findings do not cause nonzero exit; absent input path exits 1. Face diagnostics may download/cache a model. |
| `compare_image_trees.py` | Exactly seven roots from `--dirs`, or `--repo-root`/`PEOPLE_IMAGES_DIR` plus categories. Recursive `.jpg`/`.png` only. Presence keys are full relative paths without suffix, not just person names. Six JPG roots and one PNG root, selected by index/name. | Overwrites log, `C/compare_image_trees.csv` (`stem` plus seven Y/blank style columns), and enabled `C/readme_issues.csv` (`directory,issue,name,detail`). Writes dimension CSV (`directory,relative_path,width,height,error`) and quality CSV (`directory,relative_path,issue`) only if issues exist. Disabled/clean issue reports leave old CSVs untouched. Findings/missing trees do not change exit status. |

Compare's default `grid` basename whitelist allows grid JPGs in the PNG root and
exempts that basename from both dimensions and quality in every root. Other
unexpected JPG/PNG extensions are logged, not given their own issue CSV. README
audit reads the root README's first-line `(N Images)` and `* [name](...)` entries,
compares basename sets, and reports drift separately from presence. Its README
sets retain original case even with `--case-insensitive`, so that option does not
fully normalize README comparisons. Duplicate basenames can be collapsed there.

Transparency tests in sync and Python QA require an explicit `A` band. Palette
PNG transparency can be rejected even when rendering would show transparency.
Grayscale QA compares full RGB channels exactly and includes hidden transparent
pixels; it is not the near-gray classification used by source/recovery helpers.
Python edge QA defaults to top only, with alpha mean >0.06 OR foreground coverage
>0.015, where foreground alpha is >8. `EDGE_CHOP_THRESHOLD` is consumed by recovery,
not these QA callers' fixed default mean threshold. Poster warning 3 uses mean
only. Bottom/left/right contact and YuNet chin/side findings are diagnostics, not
proof of a cropped face. No detected face yields no face-risk finding.

## Environment Consumers

The requested Python scripts load `C/.env` with the default non-overriding dotenv
behavior: inherited process variables take precedence. Prep selects POSTER_DIR
before loading it. The poster script does not load `.env` or read custom env keys.
DDColor reads only inherited process environment, normally supplied by orchestrator.

| Consumer | Keys and implementation defaults |
| --- | --- |
| Prep | `POSTER_DIR=C/posters`, read at import before dotenv. Relative paths and `~` are not expanded explicitly. |
| Adobe paths/profile | `SEL_SRC_DIR=CWD`; `SEL_ORIG_DIR=CWD/original`; `SEL_DOWNLOAD_DIR=CWD/sel_downloads`; all use `Path.resolve()` without `expanduser()`. `SEL_TOOL_URL=https://new.express.adobe.com/tools/remove-background`; `SEL_USER_DATA_DIR=C/chrome-profile`; `SEL_PROFILE_DIR=Profile 1`; `SEL_HEADLESS_USER_DATA_DIR=C/chrome-profile-headless`; `SEL_HEADLESS_PROFILE_DIR=Default`. Profile paths also resolve against CWD. |
| Adobe modes | `SEL_HEADLESS=false`; `SEL_HEADLESS_REMOTE_DEBUGGING_PIPE=true`; `SEL_HEADLESS_FALLBACK_TO_USER_PROFILE=true`; `SEL_HEADLESS_FALLBACK_TO_HEADED=true`; `SEL_HEADLESS_FALLBACK_TO_HEADED_PROFILE=true`; `SEL_WINDOW_SIZE=1400,1000` (minimum 800x600); `SEL_DISABLE_CHROME_RESTORE=true`. |
| Adobe sizing | `SEL_EXPECT_WIDTH=2000`; `SEL_EXPECT_HEIGHT=3000`; `SEL_ENFORCE_SIZE=true`. Resizing runs only when enforcement is true and both dimensions are positive. |
| Adobe flow/timeouts | `SEL_MAX_WAIT_READY_SEC=120`; `SEL_PROC_TIMEOUT=120`; `SEL_DISABLED_DOWNLOAD_STALL_SEC=45`; `SEL_NO_DOWNLOAD_CONTROL_STALL_SEC=75`; `SEL_MAX_WAIT_DL_SEC=240`; `SEL_DL_BUTTON_TIMEOUT=20`; `SEL_FAST_DL_CHECK_SEC=6` (minimum 2); `SEL_RELOAD_EACH_FILE=true`; `SEL_RESTART_BROWSER_EACH_FILE=true`; `SEL_MAX_FILE_ATTEMPTS=2` (minimum 1); `SEL_MAX_TOOL_READY_RESTARTS=5` (minimum 1); `SEL_MAX_CONSECUTIVE_PROCESSING_STALLS=3`; `SEL_PROMPT_FOR_LOGIN=true`; `SEL_LOGIN_WAIT_SEC=900` (minimum 30). Stall settings clamp to zero, which disables that stall threshold. |
| Sync | `PEOPLE_IMAGES_DIR`; `SYNC_PREFLIGHT=true`; `SYNC_MARKDOWN=false`. CLI overrides exist for all three. Paths do not explicitly expand `~`. |
| Single-tree QA | `IMAGE_CHECK_CHOP_EDGES=top`; `IMAGE_CHECK_FACE_CROP_CHECKS=chin,left,right`; `IMAGE_CHECK_FACE_CROP_SIDE_MARGIN=0.02`; `IMAGE_CHECK_FACE_CROP_CHIN_MARGIN=0.015`. CLI overrides exist; `--face-crop-checks none` disables the face detector. |
| Compare | `PEOPLE_IMAGES_DIR` (fallback `./Kometa-People-Images`, CWD-relative); `COMPARE_CATEGORIES` (seven default style names); `COMPTREE_CASE_SENSITIVE=true`; `COMPTREE_CHECK_DIMENSIONS=true`; `COMPTREE_CHECK_QUALITY=true`; `COMPTREE_CHECK_README=true`; `COMPTREE_REQUIRED_SIZE=2000x3000`; `COMPTREE_JPG_WHITELIST=grid`; `COMPTREE_PNG_INDEX` (auto-detect transparent, otherwise 6); `COMPTREE_CHOP_EDGES=top`; `COMPTREE_FACE_CROP_CHECKS=chin,left,right`; `COMPTREE_FACE_CROP_SIDE_MARGIN=0.02`; `COMPTREE_FACE_CROP_CHIN_MARGIN=0.015`. Explicit roots expand `~`/resolve. PNG index is not range-validated. |
| Shared QA helpers | `EDGE_CHOP_COVERAGE_THRESHOLD=0.015`; `EDGE_CHOP_ALPHA_MIN=8`. `FACE_CROP_MODEL_PATH`, or `FACE_CROP_MODEL_HOME=C/models/opencv`, and `FACE_CROP_MODEL_URL` select the YuNet model. Default filename is `face_detection_yunet_2026may.onnx`; URL points to OpenCV Zoo's main branch. Missing model downloads through a `.tmp` file. Face helper sets default `OPENCV_FORCE_DNN_ENGINE=4` and `OPENCV_LOG_LEVEL=ERROR`. |
| DDColor/runner | `COLORIZE_ENGINE=ddcolor` and `COLORIZE_PYTHON` are runner choices. DDColor consumes `COLORIZE_INPUT_OTHER`, `COLORIZE_OUTPUT_COLOR`, `COLORIZE_VENDOR_DIR`, `COLORIZE_DDCOLOR_VENDOR_DIR`, `COLORIZE_DDCOLOR_MODELS_DIR`, `COLORIZE_MODEL=ddcolor_modelscope`, `COLORIZE_DEVICE=cpu`, `COLORIZE_INPUT_SIZE=512`, `COLORIZE_JPEG_QUALITY=95`; defaults are the config paths above. Sets defaults for `HF_HOME`, `TORCH_HOME`, `PYTORCH_ENABLE_MPS_FALLBACK`. Input size is inference size, not output-poster dimensions. |

Adobe boolean parsing accepts only `1,true,yes,y`, lowercased without trimming;
it does not accept `on`. Sync/compare/runner parsing also trims and accepts `on`.
Several numeric values are converted at import/parser construction, so invalid
values fail before per-file handling. README timeout examples are configured
examples (60/20/12 seconds), not Adobe's code defaults (120/240/20 seconds).

Orchestration also consumes `ORCH_LOGS_DIR`, `PEOPLE_IMAGES_DIR`, `PEOPLE_BRANCH`,
`ORCH_STYLE`/`ORCH_STYLES`, `ORCH_GENERATE_READMES=false`, `ORCH_GRID_IMAGES=false`,
`ORCH_COMMIT_MESSAGE`, `ORCH_GIT_USER_NAME`, `ORCH_GIT_USER_EMAIL`,
`SEL_DOWNLOAD_DIR`, `ORCH_BG_EXTS=png`, `ORCH_CONTINUE_IF_EMPTY=false`,
`ORCH_REQUIRE_BG_OUTPUT=false`, `ORCH_REQUIRE_POWERSHELL=false`, and
`ORCH_RECOVER_EDGE_CHOPS=true`. TMDB_KEY is consumed by TMDB/recovery helpers,
not the six requested rendering/sync/QA scripts themselves.

The concurrent runner additionally consumes `REMOVE_BG_ENGINE=adobe` (`adobe` or
`birefnet`) and `REMOVE_BG_PYTHON`. Its latest observed fingerprint delegates
BiRefNet settings to `remove_bg_birefnet.Settings.from_env()` and includes the
selected interpreter/model-cache path. The new backend's complete settings,
output semantics, requirements, and tests are outside this audit snapshot.
`REMOVE_BG_OVERWRITE` does not alter the reviewed Adobe script's replacement
behavior: Adobe unlinks existing final PNG/archive JPG files unconditionally.

## Orchestration and Recovery

Fixed sequence: discovery/TMDB -> truncation -> source audit -> DDColor -> prep ->
remove_bg -> poster -> inline recovery -> Git update -> image sync -> optional
local README/MD -> push. Checkpoints live at `C/.orch/*.done.json`; a run lock
protects normal orchestration, not independent direct script calls.

The observed concurrent runner skips completed steps, fingerprints background
configuration, clears downstream markers on changed/pending background settings,
and requires restaged source photographs when such a change has no inputs.
Colorize's actual marker is `colorize_noncolor.done.json`; the concurrent
`clear_from` now maps that step name correctly. The existing checkpoint test
still creates/expects `colorize.done.json`, so it needs reconciliation with this
change. Checkpoints are not per-person output manifests.

The remove_bg activity check first counts recent files in SEL_DOWNLOAD_DIR even
though successful Adobe files have moved to SRC. It falls back to a log's
`Files processed: N`, which counts attempted files including skips/errors, not
successful PNGs. Adobe log parsing takes the first matching summary from an
append-only log, so historical runs can affect this check. ORCH_REQUIRE_BG_OUTPUT
ensures the directory setting exists; it does not certify one valid PNG per
source. The concurrent runner added a ready-SRC-PNG fallback, later restricted
to BiRefNet; this does not change Adobe's transient-download/activity mismatch.

Missing PowerShell may be checkpointed as skipped unless required. The recovery
step is described as nonblocking in README/CLI copy, but the normal runner aborts
on any nonzero subprocess result, including recovery initialization/runtime
errors. Per-person exhausted/unresolved rows often return zero. The always-run
Git update uses hardreset and clean-ignored; it discards cloned repo changes before
source preflight. Push is not guaranteed merely by being called always-run:
zero-work exits can stop the loop first, including sync's zero-copy condition.

| Helper | Recovery contract and cautions |
| --- | --- |
| `recover_edge_chops.py` | Default standalone mode scans cloned transparent assets, stages one viable replacement JPG per person into local Downloads, runs orchestrator through poster with nested recovery disabled, postchecks, then requests update/sync/push if any rows pass. Refuses staging when immediate JPG/JPEG/PNG inputs already exist. No scope writes a skipped report; `--all`, names, or time scope opt in. `--audit-only` still writes log/report and can cache a face model. `--stage-only` stages without running the pipeline. See P1 root mismatch before trusting standalone postchecks/cleanup. |
| Inline recovery | Orchestrator explicitly scopes local roots and PNG modification time from its poster run. `recover_one` makes temporary backups of all seven style outputs plus staging/temp paths, downloads alternate TMDB profiles, optionally colorizes non-color candidates, runs rembg precheck, invokes Adobe with temporary SEL paths, stages its PNG, and rerenders. Failed/exhausted attempts restore backups on the explicit handled paths (`recover_edge_chops.py:958`). TemporaryDirectory is not a durable crash/interrupt backup; there is no unconditional outer restore covering every interruption. The archived JPG from the retry stays in its temporary SEL_ORIG_DIR: accepted inline recovery does not copy it into local original, while local original was included in removed style outputs. This can leave a recovered person without the matching original JPG. |
| Recovery state | Overwrites `C/edge_chop_recovery/edge_chop_recovery.csv`; appends `exhausted_names.txt` and `attempted_candidates.csv`; keeps candidate JPGs/rembg PNGs under `candidates/<safe-name>`. Normal staged mode avoids already attempted candidates and visually identical current originals. Inline retries do not use that staged attempt-skip loop. Exhausted entries are name-based across warning modes, so later warning-mode changes can still skip a person. |
| Original resolver | `resolve_original_images.py` matches transparent/rainier reference images against TMDB, then optional Google images, default similarity threshold 0.82. Even default dry-run downloads candidates and writes manifest/unresolved/review artifacts under `C/original_resolver`. `--apply` saves EXIF-oriented RGB center-fit 2000x3000 JPEGs to `W/original/<letter>/Images/<name>.jpg`; existing targets require `--force`. |
| Original verification/normalization | `verify_import_originals.py` reads imported style names and local originals in `Images` folders, prints missing/bad-size matches, returns 1 for findings without writing reports. `normalize_import_originals.py` edits matching originals in place using RGB center-fit 2000x3000; `--dry-run` avoids changes. Missing originals abort before normalization. `PEOPLE_IMPORT_DIR` redirects the import source, not the default local original destination. |
| Candidate review | `stage_original_candidates.py` downloads TMDB portraits into `C/review_original_candidates/tmdb_originals`, writes manifest and sheets. `review_tmdb_profile_alternates.py` writes per-person candidates, manifest, and sheets under its `tmdb_alternates` subdirectory. Both consume TMDB_KEY/PEOPLE_IMPORT_DIR and generate review artifacts rather than normal poster outputs. |
| Signature rerender | `rebuild_since_signature_commit.py` reads signature Git history inclusively from boundary `c2c1138c8d6dc1b775a0f44b27180a7cedeb6816` through HEAD, maps added JPGs to transparent PNGs, and writes a TXT/CSV list even in default dry-run. `--stage` copies PNGs into local Downloads, preserving mtime and overwriting collisions; missing sources require `--allow-missing`. No empty-staging guard. It rerenders from existing cutouts, not original photographs. |
| Adobe login/storage | `sel_remove_bg.py --login-only` opens the configured headed profile; `--headless-profile` prepares the separate headless profile visibly, with optional profile-path CLI overrides. Batch failure codes: 4 unresolved login, 5 repeated processing stalls, 6 remote storage full. Remaining JPGs stay queued; completed moves are kept. Adobe cleanup defaults to preview, but `--apply` deletes remote projects and `--deleted --apply` permanently deletes them. Preview/debug operations can still write local diagnostics/profile state. |
| Local cleanup | `clean_people_config.py` defaults to age-based preview (14 days), still appending its log. `--apply` prunes generated artifacts; explicit cache/checkpoint/staging/recovery-state switches broaden deletion. `--max` enables those switches with zero-day cutoff. Default preservation covers local working style outputs, live lists/env, Chrome profile, caches, checkpoints and recovery state. It validates resolved candidates stay inside the selected config root; it is cleanup, not restoration. |

Recovery environment consumers include `EDGE_CHOP_PEOPLE_ROOT`,
`EDGE_CHOP_TRANSPARENT_ROOT`, `EDGE_CHOP_DOWNLOADS_DIR`, `EDGE_CHOP_OUT_ROOT`,
`EDGE_CHOP_EXHAUSTED_FILE`, `EDGE_CHOP_ATTEMPTED_FILE`,
`EDGE_CHOP_RECOVER_WARNINGS=headchop`, `EDGE_CHOP_REPORT_EDGES=top`,
`EDGE_CHOP_RETRY_EDGES=top`, `EDGE_CHOP_THRESHOLD=0.06`,
`EDGE_CHOP_TMDB_LIMIT=12`, `EDGE_CHOP_PRECHECK_REMBG=true`,
`EDGE_CHOP_PRECHECK_THRESHOLD=0.03`,
`EDGE_CHOP_PRECHECK_COVERAGE_THRESHOLD=0.005`, `EDGE_CHOP_REMBG_MODEL=u2net`,
`REMBG_HOME`, `EDGE_CHOP_REMBG_ALPHA_MATTING=false`,
`EDGE_CHOP_REMBG_POST_PROCESS_MASK=true`, `EDGE_CHOP_REJECT_GRAYSCALE=true`,
`EDGE_CHOP_COLORIZE_GRAYSCALE=true`, `EDGE_CHOP_GRAYSCALE_SAT_THRESHOLD=35`,
`EDGE_CHOP_GRAYSCALE_SAT_QUANTILE=0.95`,
`EDGE_CHOP_GRAYSCALE_COLORFULNESS_CUTOFF=12.0`,
`EDGE_CHOP_FACE_CROP_SIDE_MARGIN`/`EDGE_CHOP_FACE_CROP_CHIN_MARGIN` (fallback
to IMAGE_CHECK margin keys), `EDGE_CHOP_SCAN_PROGRESS_EVERY=500`,
`EDGE_CHOP_SCAN_PROGRESS_SECONDS=30`, `EDGE_CHOP_STAGE_ONLY=false`,
`EDGE_CHOP_INLINE=false`, plus TMDB_KEY and DDColor/shared-QA settings.

Original recovery consumes `PEOPLE_IMPORT_DIR`, `ORIGINAL_RESOLVER_STYLES`,
`ORIGINAL_RESOLVER_ORIGINAL_ROOT`, `ORIGINAL_RESOLVER_OUT_ROOT`,
`ORIGINAL_RESOLVER_THRESHOLD`, `ORIGINAL_RESOLVER_TMDB_LIMIT=50`,
`ORIGINAL_RESOLVER_GOOGLE_LIMIT=30`, TMDB_KEY, GOOGLE_API_KEY/GOOGLE_CSE_ID
(aliases GOOGLE_SEARCH_KEY/GOOGLE_SEARCH_CX). Cleanup consumes
`CLEAN_PEOPLE_CONFIG_DAYS` from process env; it does not load `.env`.

## Requirements, Documentation, and Verification

- `requirements.txt` declares requests, Pillow, numpy, rembg[cpu,cli],
  opencv-python-headless, selenium, python-dotenv, alive-progress, tmdbapis,
  rarfile, py7zr, PyYAML with no version pins. It does not include pytest.
  ImageMagick, PowerShell, Chrome, Git, and optional gh are external executables,
  not installed by this file. The Adobe script instantiates Chrome specifically,
  despite README wording saying Chrome/Edge.
- `requirements-ddcolor.txt` uses the PyTorch CPU extra index and lower bounds
  torch>=2.14.1, torchvision>=0.29.1, Pillow>=12.3.0, numpy>=2.5.4,
  opencv-python-headless>=5.0.0.93, huggingface-hub>=2.2.0. These are ranges, not a
  reproducible lock. Availability/compatibility was not checked online or by pip.
  The separate interpreter is chosen by configured path, local `.venv-ddcolor`,
  launcher/PATH fallbacks, then the pipeline interpreter, with import probes.
- The people README accurately documents the normal staging layout and recovery
  resume commands, but its `sel_remove_bg.py -v` examples are unsupported by the
  actual argparse parser. The root README places Python files/requirements at the
  repository root and shows `--all`/`--steps` orchestrator examples that the
  reviewed parser does not implement. Use the people-directory code contracts.
- The tracked HEAD contains one Python test file: 20 test functions, 24
  parameter-expanded cases. It covers DDColor vendoring/cache loading, same-size JPEG output, batch
  reuse, corrupt-output replacement, source deletion/failure preservation,
  interpreter/backend selection, recovery colorization, and checkpoint clearing.
  It mocks model/network/subprocess behavior; it does not test actual model
  inference, Adobe download identity/alpha, archive replacement, poster styles,
  sync timestamp/normalization behavior, QA failure exits, or recovery root
  separation. The concurrent marker change makes the existing clear_from test's
  old synthetic marker expectation stale. A new untracked BiRefNet test file
  appeared during review; it is outside this test-coverage assessment.
- Tests were not executed: they import DDColor, whose module-level setup creates
  folders and truncates its real log before tmp_path monkeypatches apply. The
  five requested Python scripts were not imported/executed for the same
  side-effect reason.
- Read-only `ast.parse` checks passed for prep, Adobe removal, sync, image_check,
  compare, DDColor, recovery, the observed orchestrator, and the test source.
  Grayscale sweeper failed at line 128. PowerShell ParseFile found no syntax errors.
  A read-only Join-Path probe confirmed trailing separator behavior in the local
  PowerShell 5.1 shell; no poster rendering was attempted.

## Recommended Follow-Up

1. Separate recovery scan roots from generated-output/cleanup roots and preserve
   each accepted alternate's actual original JPG, including inline recovery.
2. Track per-source outcomes and verified output/archive paths; do not checkpoint
   pending/skipped files as a completed batch. Replace old outputs only after
   successful validation, with durable backups where restoration is promised.
3. Require successful native renders and all expected style outputs before
   deleting temp sources; regenerate color intermediates independently of BW.
4. Make staging paths explicit across steps; load env before deriving defaults;
   use SRC for completed Adobe outputs and avoid activity-only success checks.
5. Define replacement sync semantics beyond mtime, account for normalization-only
   changes before push, and clear/write empty QA reports after clean scans.
6. Repair/document the sweeper and add focused tests for root separation,
   original retention, partial runs, archive collisions, color-style isolation,
   and stale reports. Reconcile concurrent checkpoint tests before running them.

## 2026-10-22 follow-up — grayscale sweeper repair

The optional `grayscale_sweeper.py` is repaired on
`fix/people-grayscale-sweeper`, based on merged M7 `0058ac6`.
The breaking change was [e3bbfd102b231eadc8d969d8a40679dde426d2ed](https://github.com/Kometa-Team/Defaults-Image-Creation/commit/e3bbfd102b231eadc8d969d8a40679dde426d2ed)
(2025-10-11, “updated sweeper”). Its parent had functioning `exact` and `sat`
paths; the change added useful `satq`, `colorfulness` and `auto` helpers but
broke the parser string/indentation and moved detection outside the open-image
processing loop. The repair preserves those three algorithms rather than
reverting them, including the original 98% saturation rule, NumPy quantile,
colorfulness cutoff 12 and `auto` saturation floor 35.

The actual arguments are `--src` and `--dest-other`; the obsolete README
`--root`/`--dest` example is corrected. All five branches classify within the
Pillow context. Unexpected detector errors receive tracebacks and error counts
instead of being silently suppressed. Imports/help no longer create the old
processing directories or truncate `config/logs/grayscale_sweeper.log`.
Runtime logs now append to the selected destination's `.grayscale_sweeper.log`.

Synthetic regressions execute the actual CLI and cover all five methods,
RGB/RGBA/L/LA and transparent inputs, copy/move/overwrite/collision behavior,
destination pruning, root and link protections, byte/timestamp preservation,
source changes, corrupt images and partial failures. Heuristic disagreements
about near-gray pixels are explicit expected outcomes rather than visual
certification. Focused Windows/Linux CI runs these temporary fixtures only.
Pillow, NumPy and alive-progress were already declared; no model or generator
dependency changes are required. Exact test results are recorded in the repair
PR after validation.

This follow-up does not resolve or rewrite the other historical findings.
DDColor, BiRefNet, production artwork, publication destinations and orchestrator
processing behavior remain outside the repair.
