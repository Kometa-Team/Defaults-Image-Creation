# Create People Posters — Cross‑Platform Pipeline

This repo automates generating, curating, colorizing, and publishing **Kometa People Images** (posters) across styles.  
It’s designed to be **cross‑platform**, **fixed‑order**, and **resumable** so you can stop and restart safely.

---

## Highlights
- **One command** to run the whole pipeline: `python orchestrator.py`
- **Fixed order** (no reordering) to keep outputs consistent
- **Resume after crash/CTRL‑C** via automatic checkpoints
- Works on **Windows / macOS / Linux** with native Python/Pillow poster rendering
- Consistent **logging & progress** across scripts

---

## Prerequisites

### Default Clone-Free Publishing

The defaults are `PEOPLE_PUBLISH_MODE=github_api` and
`PEOPLE_WORKSPACE_MODE=batch`: none of the seven image repositories needs to be
cloned. Full local clones can require hundreds of gigabytes, including history
and working copies, and are available only as an explicit fallback. Batch workspaces
retain only active/retryable processing images and small persistent metadata.
Models, dependencies and active batches still need local disk space.

See [Clone-Free Setup and Migration](CLONE_FREE.md) for authentication, both
platform setup examples, dry-run, recovery, retention and maintenance limits.

For an opt-in offline DDColor, BiRefNet Portrait and Pillow integration check,
see [Model Smoke Test](MODEL_SMOKE_TEST.md). It uses isolated local files and
does not publish images.

- A [supported version of Python](https://devguide.python.org/versions/) (**3.11-3.15** as of **October 12, 2026**).
- **pip** to install dependencies
- **Chrome/Edge** installed only when using Adobe/Selenium background removal;
  the local BiRefNet engine does not need a browser.
- **Pillow and fontTools**, installed with the Python requirements, plus the
  existing repository artwork and fonts. No system font installation is needed.
- **Jost weight 260** is bundled with its OFL license for diiivoy/diiivoycolor;
  both engines use a 190px preferred size and auto-fit long names. No runtime
  font download or Futura installation is required.
- **PowerShell and ImageMagick are optional legacy dependencies** only for
  `POSTER_ENGINE=powershell`; Python mode never executes them.

See [Native Poster Renderer](POSTER_RENDERER.md) for the seven-style audit,
font licensing/provenance, direct usage, visual comparisons, and known differences.
For resumable Diiivoy/Diiivoycolor maintenance runs (Jost replacement and later
approved artwork changes), see
[Diiivoy Jost Migration](JOST_MIGRATION.md). It never runs automatically with
the orchestrator and requires explicit approval before image publication.

---

## Install (base environment)

```bash
# Windows:
# 1) Clone your repo and cd into it
git clone https://github.com/Kometa-Team/Defaults-Image-Creation Defaults-Image-Creation
cd Defaults-Image-Creation
cd create_people_posters

# 2) Create and activate a virtualenv
python -m venv venv
venv\Scripts\activate

# 3) Upgrade pip and install base requirements
python -m pip install -U pip wheel
pip install -r requirements.txt
```

```bash
# macOS/Linux:
# 1) Clone your repo and cd into it
git clone https://github.com/Kometa-Team/Defaults-Image-Creation Defaults-Image-Creation
cd Defaults-Image-Creation
cd create_people_posters

# 2) Create and activate a virtualenv
python3 -m venv venv
source venv/bin/activate

# 3) Upgrade pip and install base requirements
python3 -m pip install -U pip wheel
pip install -r requirements.txt
```

---

## Configure

Create `./config/.env` (the orchestrator will auto‑create it from `.env.example` and exit once, prompting you to edit).

**Required configuration:**
```ini
TMDB_KEY=your_tmdb_api_key_here
```

Authenticate with `gh auth login`, or provide `GITHUB_TOKEN` in the process
environment. Publishing needs Contents write access to all seven destination
repositories and Actions write access for README dispatch. A token for only this
code repository is insufficient. Community contributors without destination
write access still need an authorized fork/PR workflow; automatic fork creation
is not implemented. See [authentication and publication](CLONE_FREE.md#authentication-and-publication).

Existing `.env` files are preserved. To migrate an installation that explicitly
selects the old modes, set `PEOPLE_PUBLISH_MODE=github_api` and
`PEOPLE_WORKSPACE_MODE=batch`. Authentication/API errors never trigger large
clone downloads automatically.

**Recommended:**
```ini
# Orchestrator
ORCH_LOGS_DIR=/absolute/path/to/kometa/logs          # used by steps 2–3
PEOPLE_PUBLISH_MODE=github_api                        # no full image clones
PEOPLE_WORKSPACE_MODE=batch                           # isolated jobs with retention
# PEOPLE_IMAGES_DIR=/absolute/path/to/Kometa-People-Images  # full-clone fallback only
PEOPLE_BRANCH=master                                  # optional; branch for update/push
SYNC_PREFLIGHT=true                                   # optional; source QA before sync
SYNC_MARKDOWN=false                                   # keep local sync from overwriting GitHub-generated READMEs

# Fallback style for deliberate local README/sync_md runs only
ORCH_STYLE=transparent

# Local README generation is disabled by default because GitHub Actions owns
# README generation in the People image repos.
ORCH_GENERATE_READMES=false
POSTER_ENGINE=python                               # native Pillow; powershell is optional legacy fallback

# Multi-style local README run (comma list). Used only when ORCH_GENERATE_READMES=true.
# This does not limit poster generation, image sync, or repo pushes.
# ORCH_STYLES=transparent,diiivoycolor

# Grid image generation is slow and only applies to local README generation.
ORCH_GRID_IMAGES=false

# Optional commit/author for push
ORCH_COMMIT_MESSAGE=
ORCH_GIT_USER_NAME=Your Name
ORCH_GIT_USER_EMAIL=you@example.com

# Background-removal verification
SEL_DOWNLOAD_DIR=./config/sel_downloads               # where sel_remove_bg.py writes processed PNGs
ORCH_BG_EXTS=png                                      # exts to count after remove_bg (csv)
ORCH_CONTINUE_IF_EMPTY=false                          # continue run even if 0 PNGs were produced
EDGE_CHOP_PRECHECK_REMBG=true                         # prefilter retry candidates locally before Adobe
REMBG_HOME=./config/models/rembg                       # rembg model cache for recovery
EDGE_CHOP_REJECT_GRAYSCALE=true                       # do not accept B/W TMDB alternates during recovery
EDGE_CHOP_COLORIZE_GRAYSCALE=true                     # try selected colorizer before rejecting B/W alternates
EDGE_CHOP_RECOVER_WARNINGS=headchop                   # headchop,grayscale,face-chin,face-side,all
EDGE_CHOP_COVERAGE_THRESHOLD=0.015                    # foreground edge coverage threshold for headchop checks
EDGE_CHOP_PRECHECK_THRESHOLD=0.03                     # stricter local rembg alpha-mean threshold before Adobe
EDGE_CHOP_PRECHECK_COVERAGE_THRESHOLD=0.005           # stricter local rembg foreground coverage threshold before Adobe
EDGE_CHOP_ALPHA_MIN=8                                  # alpha value counted as foreground for edge coverage
EDGE_CHOP_EXHAUSTED_FILE=./config/edge_chop_recovery/exhausted_names.txt
EDGE_CHOP_ATTEMPTED_FILE=./config/edge_chop_recovery/attempted_candidates.csv
EDGE_CHOP_STAGE_ONLY=false                            # stage candidates but do not run orchestrator
EDGE_CHOP_INLINE=false                                # internal/debug only; orchestrator passes --inline itself
EDGE_CHOP_FACE_CROP_SIDE_MARGIN=0.02
EDGE_CHOP_FACE_CROP_CHIN_MARGIN=0.015
IMAGE_CHECK_FACE_CROP_CHECKS=chin,left,right           # report-only face crop diagnostics
COMPTREE_FACE_CROP_CHECKS=chin,left,right              # same diagnostics in compare_image_trees
FACE_CROP_MODEL_HOME=./config/models/opencv            # YuNet face detector cache

# Hard requirements (fail fast when true)
ORCH_REQUIRE_POWERSHELL=false
ORCH_REQUIRE_BG_OUTPUT=false

# Colorizer (optional)
# DDColor is the supported colorizer.
COLORIZE_ENGINE=ddcolor
COLORIZE_MODEL=ddcolor_modelscope
COLORIZE_DEVICE=cpu
COLORIZE_INPUT_SIZE=512
COLORIZE_JPEG_QUALITY=95

# If you keep a separate venv just for colorization, point to its python here:
COLORIZE_PYTHON=D:/Defaults-Image-Creation/create_people_posters/.venv-ddcolor/Scripts/python.exe
COLORIZE_PYTHON=/absolute/path/to/.venv-ddcolor/bin/python

# Original resolver (optional)
PEOPLE_IMPORT_DIR=/absolute/path/to/people_dirs        # defaults to ./config/people_dirs
ORIGINAL_RESOLVER_STYLES=transparent,rainier
ORIGINAL_RESOLVER_THRESHOLD=0.82
GOOGLE_API_KEY=your_google_api_key_here                # optional Google fallback
GOOGLE_CSE_ID=your_programmable_search_engine_id_here  # optional Google fallback
```

**Selenium background removal (used by `sel_remove_bg.py`)**  
These keys are read by the script; set what you need for your environment. Common ones:

```ini
# Source/destination
SEL_SRC_DIR=./config/people_dirs/Downloads            # input JPGs
SEL_ORIG_DIR=./config/people_dirs/original            # keep original JPGs here
SEL_TOOL_URL=https://new.express.adobe.com/tools/remove-background
SEL_USER_DATA_DIR=./config/chrome-profile
SEL_PROFILE_DIR=Default
SEL_HEADLESS_USER_DATA_DIR=./config/chrome-profile-headless
SEL_HEADLESS_PROFILE_DIR=Default
SEL_DOWNLOAD_DIR=./config/sel_downloads               # output PNGs from Adobe Express

# Size enforcement (input JPGs)
SEL_EXPECT_WIDTH=2000
SEL_EXPECT_HEIGHT=3000
SEL_ENFORCE_SIZE=true

# Timeouts/tuning (seconds)
SEL_MAX_WAIT_READY_SEC=60
SEL_PROC_TIMEOUT=120
SEL_DISABLED_DOWNLOAD_STALL_SEC=45
SEL_NO_DOWNLOAD_CONTROL_STALL_SEC=75
SEL_MAX_WAIT_DL_SEC=20
SEL_DL_BUTTON_TIMEOUT=12
SEL_RESTART_BROWSER_EACH_FILE=true
SEL_MAX_FILE_ATTEMPTS=2
SEL_MAX_CONSECUTIVE_PROCESSING_STALLS=3
SEL_RELOAD_EACH_FILE=true
SEL_PROMPT_FOR_LOGIN=true
SEL_LOGIN_WAIT_SEC=900
SEL_HEADLESS=false
SEL_HEADLESS_REMOTE_DEBUGGING_PIPE=true
SEL_HEADLESS_FALLBACK_TO_USER_PROFILE=true
SEL_HEADLESS_FALLBACK_TO_HEADED=true
SEL_HEADLESS_FALLBACK_TO_HEADED_PROFILE=true
SEL_WINDOW_SIZE=1400,1000
```

> Tip: run `sel_remove_bg.py -v` once to see which env keys your build respects; the script logs the active configuration.
> If Adobe blocks download behind a login/sign-up modal, the script will pause
> for up to `SEL_LOGIN_WAIT_SEC`, let you complete login in the same Chrome
> profile, and retry after you press Enter or after it detects that the Adobe
> login gate cleared.
> You can also prepare the Selenium profile ahead of time with `python sel_remove_bg.py --login-only`, sign into Adobe in that browser window once, then rerun the full pipeline.
> If Adobe asks you to sign in during a recovery/orchestrator batch and the run
> exits with code `4`, completed downloads are kept and remaining JPGs stay in
> the source folder. Run `python sel_remove_bg.py --login-only`, then resume with
> `python orchestrator.py --redo remove_bg --no-recover-edge-chops`. The
> orchestrator also prints the aborted step and the same recovery command.
> For unattended runs, set `SEL_PROMPT_FOR_LOGIN=false`; auth/download gates
> will fail the current attempt instead of waiting for terminal input.
> `SEL_HEADLESS=true` runs Chrome without a visible browser window. Treat it as
> opt-in because Adobe Express can behave differently in headless mode. Headless
> mode uses `SEL_HEADLESS_USER_DATA_DIR`/`SEL_HEADLESS_PROFILE_DIR`, separate
> from the normal headed profile, so it does not corrupt or crash the visible
> Chrome profile. `SEL_HEADLESS_REMOTE_DEBUGGING_PIPE=true` uses ChromeDriver's
> pipe mode for startup, which avoids the old `DevToolsActivePort` file path.
> If the dedicated headless profile crashes before Adobe loads during the
> normal remove-background step, `SEL_HEADLESS_FALLBACK_TO_USER_PROFILE=true`
> tries the normal signed-in `SEL_USER_DATA_DIR` automation profile in headless
> mode before using any visible browser fallback.
> If headless Chrome itself still crashes before Adobe loads,
> `SEL_HEADLESS_FALLBACK_TO_HEADED=true` continues in a visible browser with the
> same automation profile instead of aborting the orchestrator. If that separate
> headless profile also crashes in visible Chrome,
> `SEL_HEADLESS_FALLBACK_TO_HEADED_PROFILE=true` tries the normal
> `SEL_USER_DATA_DIR` headed automation profile as the last startup fallback.
> If Adobe requires login during a headless run, the script exits instead of waiting.
> To prepare the separate headless profile, first open it visibly and sign in:
> `python sel_remove_bg.py --login-only --headless-profile`.
> If that profile crashes even in visible mode, leave it alone and use a fresh
> profile path:
> `python sel_remove_bg.py --login-only --headless-profile --headless-user-data-dir ./config/chrome-profile-headless-2`.
> Then run the batch with `$env:SEL_HEADLESS="true"; $env:SEL_PROMPT_FOR_LOGIN="false"`.
> Stale Adobe project/modals and processing/download timeouts are retried by
> restarting Chrome and reprocessing the same JPG up to `SEL_MAX_FILE_ATTEMPTS`.
> If Adobe shows a Download/Export control that remains disabled for
> `SEL_DISABLED_DOWNLOAD_STALL_SEC`, that is treated as a retryable processing
> stall instead of waiting for the full processing timeout.
> If no Download/Export control appears at all for
> `SEL_NO_DOWNLOAD_CONTROL_STALL_SEC`, that is also treated as a retryable
> processing stall.
> If `SEL_MAX_CONSECUTIVE_PROCESSING_STALLS` processing stalls happen back to
> back, the batch stops with remaining JPGs preserved so a temporary Adobe
> service/session problem does not mark hundreds of files as errors. Resume
> later with `python orchestrator.py --redo remove_bg --no-recover-edge-chops`.
> If Adobe opens the "Start from your image" chooser after upload, the Selenium
> step treats it as stale project state, restarts Chrome, and retries until it
> gets the normal upload page headed "Remove background".

---

## Optional (but recommended): colorizer setup (separate venv)

DDColor is the default colorizer (`COLORIZE_ENGINE=ddcolor`). It supports CPU
inference on Python 3.13, auto-vendors the official `piddnad/DDColor` source,
and caches Hugging Face model weights under `./config/models/ddcolor`.

DDColor is the only supported colorizer. Leave `COLORIZE_PYTHON` blank to
automatically select `.venv-ddcolor`, or set it to a custom interpreter with
`requirements-ddcolor.txt` installed. Other `COLORIZE_ENGINE` values are rejected.

Interpreter selection allows 180 seconds for DDColor dependency imports, which
can be slow on a cold Windows startup. Set `COLORIZE_PROBE_TIMEOUT` to a positive
number of seconds to adjust that limit. A timeout means the import check did not
finish; it does not establish that dependencies are missing. When no grayscale
files are waiting, the basic Python startup check retains its 30-second limit.

The previous DeOldify implementation is preserved in Git commit `5fdded4`.
Restore that version in a separate checkout to recover its code, configuration,
and installation instructions. Removed environments and caches must be recreated.

## Install (base environment)

```bash
# Windows:
# 1) Create & activate a dedicated venv
py -3.13 -m venv .venv-ddcolor
.\.venv-ddcolor\Scripts\Activate.ps1   # or Activate.bat

# 2) Upgrade pip and install base requirements
pip install -U pip setuptools wheel
pip install -r requirements-ddcolor.txt

# 3) Tell orchestrator where that Python lives (add to .env)
# COLORIZE_ENGINE=ddcolor
# COLORIZE_PYTHON=C:\path\to\create_people_posters\.venv-ddcolor\Scripts\python.exe
```

```bash
# macOS/Linux:
# Install Python 3.13 from your OS packages, pyenv, uv, or deadsnakes.
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.13 python3.13-venv

# New venv with 3.13
cd Defaults-Image-Creation/create_people_posters
python3.13 -m venv .venv-ddcolor
source .venv-ddcolor/bin/activate

# Upgrade tooling and install the DDColor reqs
pip install -U pip setuptools wheel
pip install -r requirements-ddcolor.txt

# 3) Tell orchestrator where that Python lives (add to .env)
# COLORIZE_ENGINE=ddcolor
# COLORIZE_PYTHON=/path/to/create_people_posters/.venv-ddcolor/bin/python
```

> DDColor auto-downloads the configured model on first run. The default is
> `ddcolor_modelscope`. Model weights are cached under `./config/models/ddcolor`
> and reused on subsequent runs.

---

# Optional Full-Clone Fallback Setup

Skip this entire section for normal clone-free operation. Only full-clone mode
expects **seven** repos under `PEOPLE_IMAGES_DIR`; these clones and their history
can consume hundreds of gigabytes. To deliberately select this fallback, set
the following in `config/.env`, then clone the repositories as shown below:

```dotenv
PEOPLE_PUBLISH_MODE=local_git
PEOPLE_WORKSPACE_MODE=persistent
```

For a single run, use `python orchestrator.py --publish-mode local_git --workspace-mode persistent`.

```
<PEOPLE_IMAGES_DIR>/
  original/
  bw/
  diiivoy/
  diiivoycolor/
  rainier/
  signature/
  transparent/
```

Add the root path to your `.env`:
```dotenv
# .env
PEOPLE_IMAGES_DIR=/ABSOLUTE/PATH/TO/Kometa-People-Images  # or ~/Kometa-People-Images
```

> **Notes**
> - You can use an absolute path, `~`, or a relative path; the pipeline normalizes it.
> - On Windows PowerShell and macOS/Linux, forward slashes are OK in paths.

---

## macOS / Linux (bash/zsh)
```bash
# assumes you've cd'ed into the parent directory where you want the folder created
ROOT="$PWD/Kometa-People-Images"
mkdir -p "$ROOT"

git clone https://github.com/Kometa-Team/People-Images.git               "$ROOT/original"
git clone https://github.com/Kometa-Team/People-Images-bw.git            "$ROOT/bw"
git clone https://github.com/Kometa-Team/People-Images-diiivoy.git       "$ROOT/diiivoy"
git clone https://github.com/Kometa-Team/People-Images-diiivoycolor.git  "$ROOT/diiivoycolor"
git clone https://github.com/Kometa-Team/People-Images-rainier.git       "$ROOT/rainier"
git clone https://github.com/Kometa-Team/People-Images-signature.git     "$ROOT/signature"
git clone https://github.com/Kometa-Team/People-Images-transparent.git   "$ROOT/transparent"
```

## Windows (PowerShell)
```powershell
# assumes you've Set-Location into the parent directory where you want the folder created
$ROOT = Join-Path (Get-Location) 'Kometa-People-Images'
New-Item -ItemType Directory -Force -Path $ROOT | Out-Null

git clone https://github.com/Kometa-Team/People-Images.git               (Join-Path $ROOT 'original')
git clone https://github.com/Kometa-Team/People-Images-bw.git            (Join-Path $ROOT 'bw')
git clone https://github.com/Kometa-Team/People-Images-diiivoy.git       (Join-Path $ROOT 'diiivoy')
git clone https://github.com/Kometa-Team/People-Images-diiivoycolor.git  (Join-Path $ROOT 'diiivoycolor')
git clone https://github.com/Kometa-Team/People-Images-rainier.git       (Join-Path $ROOT 'rainier')
git clone https://github.com/Kometa-Team/People-Images-signature.git     (Join-Path $ROOT 'signature')
git clone https://github.com/Kometa-Team/People-Images-transparent.git   (Join-Path $ROOT 'transparent')
```

### Quick check
```bash
ls -1 "$PEOPLE_IMAGES_DIR"
# Expect: original/ bw/ diiivoy/ diiivoycolor/ rainier/ signature/ transparent/
```

## How it works (fixed order)

The orchestrator enforces the single correct order and writes checkpoints so you can resume later:

In default API/batch mode, `ensure_repo` validates GitHub access, `update`
refreshes remote tree metadata, `sync_images` validates/prepares canonical
files, and `push` publishes through the Git Data API. No image clones are used.
Processing paths live under `config/jobs/ID/`, and background removal uses
BiRefNet Portrait by default. The script mapping below describes the full-clone
fallback; step names and ordering are the same in both modes.

1. **ensure_repo** → `ensure_people_repo.py` — validate Kometa‑People‑Images repo directory (**always runs**)  
2. **scan_kometa_logs** → `scan_kometa_logs.py` — scan Kometa logs for missing names  
3. **find_and_download_missing** → `find_and_download_missing_people.py` — build missing‑people lists from logs  
4. **tmdb** → `tmdb_people.py` — download posters via TMDB API  
5. **truncate** → `truncate_tmdb_people_names.py` — normalize/shorten person names  
6. **audit_people_images** → `audit_people_images.py` — directory‑based discovery to catch stragglers  
7. **colorize** → selected `COLORIZE_ENGINE` script — move non‑color → color (keeps basenames, JPG)  
8. **prep_dirs** → `prep_people_dirs.py` — ensure local `./config/people_dirs` scaffolds exist  
9. **remove_bg** → `sel_remove_bg.py` — background removal via Selenium (Adobe Express)  
10. **poster_ps1** → `create_people_poster.py` — native Pillow poster generation; `create_people_poster.ps1` only with `POSTER_ENGINE=powershell`
11. **recover_edge_chops** → `recover_edge_chops.py` — non-blocking TMDB alternate retry for top-edge head chops
12. **update** → `update_people_repos.py --op update` — fetch/reset style repos (**always runs**)
13. **sync_images** → `sync_people_images.py` — copy new images into the repo style folders; skips markdown by default
14. **readme** → `auto_readme.py` — optional local README generation; skipped by default because GitHub Actions owns README generation
15. **sync_md** → `sync_md.py` — optional local markdown mirror; skipped by default with local README generation disabled
16. **push** → `update_people_repos.py --op push` — commit & push changes (**always runs**)

> Optional QA tools: `image_check.py`, `compare_image_trees.py` — ad hoc reporting for grayscale, dimensions, transparency, edge chops, face-crop risk, and repo/tree consistency.
> Optional helper (outside the orchestrator): `grayscale_sweeper.py` — scan any folder tree for non‑color images and copy them into `config/Downloads/other` so `colorize_noncolor_ddcolor.py` can convert them.
> Optional helper (outside the orchestrator): `bulk_extract_configs.py` — scan mess/meta logs, including nested archives, and export redacted config sections as `parsed_*.yml`.

README generation for the People image repos is owned by each repo's
`.github/workflows/readme.yml`. Manual pushes to those repos trigger README
generation automatically. Local orchestrator runs still skip `readme` and
`sync_md` by default, and `sync_people_images.py` skips `*.md` by default, so
local image sync cannot overwrite the remotely generated README files. Scripted
pushes from `update_people_repos.py` append `[skip readme]` by default so
push-triggered README commits cannot race with multi-batch image pushes. After
all repo pushes succeed, `update_people_repos.py` dispatches `readme.yml` for
all seven People repos, including repos with no image changes, so remote README
generation stays consistent across styles. Set `ORCH_GENERATE_READMES=true` or
pass `--generate-readmes` only for a deliberate local README run; set
`SYNC_MARKDOWN=true` or pass `--sync-markdown` only when you intentionally want
local sync to copy markdown. The dispatch uses the GitHub CLI (`gh`) and is
warning-only by default; set `UPDATE_REQUIRE_README_DISPATCH=true` if a failed
dispatch should fail the run.

The `github_api` publisher waits for README workflows and verifies that the root
and affected per-letter indexes contain the batch's image links. Failed jobs
and stale indexes are retried up to three times. Unresolved failures retain the
batch and fail publication regardless of `UPDATE_REQUIRE_README_DISPATCH`.
See [README completion and retries](CLONE_FREE.md) and the coordinated
[seven-repository workflow updates](../ci/people_readme/README.md).

`sync_people_images.py` runs source-image preflight by default, but it is
split by severity. It blocks sync for wrong extensions, unreadable/corrupt
files, bad dimensions, and transparent PNGs with no alpha. Grayscale in
color-required styles is logged as warning-only and does not block sync. Use
`--no-preflight` or `SYNC_PREFLIGHT=false` only when you want sync to copy
without source QA.

---

## Run it

```bash
# The usual way: resume from the first incomplete step
python orchestrator.py
```

### Most used commands

Use this section for normal day-to-day operation. These commands assume you are
in `create_people_posters` with the venv activated, a TMDb key, and authenticated
GitHub access. No `PEOPLE_IMAGES_DIR` or full image clones are needed by default.

Start a fresh batch directly from your list, bypassing log discovery:

```bash
python orchestrator.py --new-batch --people-list config/people_list.txt
# Preview without publishing:
python orchestrator.py --new-batch --people-list config/people_list.txt --dry-run
```

Resume the pipeline from the first incomplete checkpoint:

```bash
python orchestrator.py
```

Use this after a crash, CTRL-C, reboot, or any run that printed a `[NEXT]`
resume command. The orchestrator will reuse checkpoints and continue from the
right step.

Run the normal people pipeline from a folder of Kometa logs:

```bash
python orchestrator.py --logs-dir "C:/path/to/kometa/logs"
```

Use this when the input is a batch of Kometa logs and you want the full
missing-person discovery through sync/push flow.

Retry from log scanning when you want to rescan the same folder:

```bash
python orchestrator.py --redo scan_kometa_logs --logs-dir "C:/path/to/kometa/logs"
```

Use this when new logs were added, the previous name scan was wrong, or you
changed log/name discovery settings.

Redo from TMDB download/list processing forward:

```bash
python orchestrator.py --redo tmdb
```

Use this after editing `config/people_list.txt`, after generating a TMDB popular
people list, or when you intentionally want to discard later checkpoints and run
TMDB download plus all downstream image steps again.

Build `config/people_list.txt` from TMDB popular people:

```bash
# Preview without writing.
python tmdb_top_people_list.py --limit 1000 --require-profile --dry-run

# Write the list, filtering out people already present in the configured image repos.
python tmdb_top_people_list.py --limit 1000 --require-profile

# Keep fetching popular pages until 1000 missing/non-existing people are found.
python tmdb_top_people_list.py --target-missing 1000 --require-profile

# Process the generated list through TMDB and downstream image steps.
python orchestrator.py --redo tmdb
```

Use this to grow the People repos from TMDB popularity rather than Kometa logs.
The `--require-profile` flag filters out people without usable TMDB profile
images. Use `--limit` when you want to inspect a fixed number of popular TMDB
people first. Use `--target-missing` when you want the output list to contain
that many people who do not already exist locally.

Use a smaller TMDB popular batch:

```bash
python tmdb_top_people_list.py --limit 250 --require-profile
python orchestrator.py --redo tmdb
```

Use smaller batches when you want a faster manual review cycle or when Adobe is
being unstable.

Audit warning-based recovery targets without changing files:

```bash
python recover_edge_chops.py --all --audit-only --recover-warnings headchop
```

Use audit-only first when you want to see the current backlog without staging
new files into `config/people_dirs/Downloads`.

Whole-tree recovery scans the transparent repo tree from `PEOPLE_IMAGES_DIR`
by default, not the temporary `config/people_dirs` build folders. It checks
selected recovery warnings there, including grayscale/non-color, stages viable
replacement originals into `config/people_dirs/Downloads`, then hands off to the
orchestrator. Use `compare_image_trees.py` / `image_check.py` for broad
all-style audit reports.

Recover warning-based batches through the normal orchestrator flow:

```bash
# Default/common case: top-edge head chops.
python recover_edge_chops.py --all --limit 100 --recover-warnings headchop

# Head chops plus grayscale/non-color warnings.
python recover_edge_chops.py --all --limit 100 --recover-warnings headchop,grayscale

# Face-model risk signals; keep these explicit because they are less certain.
python recover_edge_chops.py --all --limit 25 --recover-warnings face-chin,face-side

# All supported warning recovery modes.
python recover_edge_chops.py --all --limit 100 --recover-warnings all
```

Use recovery batches after audits show headchop/grayscale issues in the repo.
Recovery searches TMDB alternates, runs local rembg prechecks, skips exhausted
names, stages viable candidates, and hands off to the normal orchestrator flow.
Do not start a new recovery batch while `config/people_dirs/Downloads` still has
pending JPGs from a prior batch.

Run ad hoc QA reports:

```bash
python image_check.py --input_directory "C:/Users/bullmoose20/Kometa-People-Images/transparent" --style transparent
python compare_image_trees.py --repo-root "C:/Users/bullmoose20/Kometa-People-Images"
```

Use `image_check.py` for one style/tree when you want detailed image-quality
warnings. Use `compare_image_trees.py` for the seven local repos when you want
presence drift, dimensions, README drift, grayscale, transparency, and crop-risk
reporting in one pass.

Check local git status across the seven People repos:

```bash
python update_people_repos.py --op status --repo-root "C:/Users/bullmoose20/Kometa-People-Images"
```

Use this when a workflow push was rejected, README counts look inconsistent, or
you need to know which repos are dirty, ahead, or behind before continuing.

Push repo changes manually:

```bash
python update_people_repos.py --op push --repo-root "C:/Users/bullmoose20/Kometa-People-Images"
```

Use this only when images were already synced into the seven repos but the
orchestrator stopped before or during the push step. Normal orchestrator runs
push automatically.

Refresh Adobe login/profile:

```bash
python sel_remove_bg.py --login-only
```

Use this when Adobe auth expires, download is blocked by login, or you are
setting up a fresh Selenium/Chrome profile. After signing in, resume with the
`python orchestrator.py --redo remove_bg` command printed by the failed run.

Clean Adobe Express remote storage:

```bash
# Preview visible matching files. This deletes nothing.
python adobe_express_cleanup.py

# Delete up to 25 remove-background projects, two rows per delete cycle.
python adobe_express_cleanup.py --apply --batch-size 25

# Delete up to 500 matching files this run.
python adobe_express_cleanup.py --apply --batch-size 500

# Delete up to 1000 matching files. This moves them to Adobe Deleted.
python adobe_express_cleanup.py --apply --batch-size 1000 --select-per-delete 4 --viewports-per-delete 1

# Permanently delete matching files already in Adobe Deleted.
python adobe_express_cleanup.py --deleted --apply --batch-size 1000 --select-per-delete 4 --viewports-per-delete 1

# One-time setup for cleanup headless mode: open the headless profile visibly and sign in.
python sel_remove_bg.py --login-only --headless-profile

# If the default headless profile crashes, use a fresh stable profile path instead.
python sel_remove_bg.py --login-only --headless-profile --headless-user-data-dir ./config/chrome-profile-headless-2

# Run the same cleanup headlessly after the headless profile is signed in.
python adobe_express_cleanup.py --deleted --apply --batch-size 1000 --select-per-delete 4 --viewports-per-delete 1 --headless

# Run cleanup headlessly with that same fresh profile path.
python adobe_express_cleanup.py --deleted --apply --batch-size 1000 --select-per-delete 4 --viewports-per-delete 1 --headless --headless-user-data-dir ./config/chrome-profile-headless-2

# Select two rows, scroll, select two more, repeat for fewer Delete confirmations.
python adobe_express_cleanup.py --apply --batch-size 500 --select-per-delete 2 --viewports-per-delete 5

# Last-resort diagnostic only: allow coordinate clicks if direct checkbox selection fails.
python adobe_express_cleanup.py --apply --batch-size 10 --coordinate-fallback --select-xs 110,100,120,130,150,166,180,200

# Capture the live rendered Adobe DOM/control geometry without deleting anything.
python adobe_express_cleanup.py --debug-dump

# If Adobe's shell loads before the file rows hydrate, wait longer for rows.
python adobe_express_cleanup.py --apply --batch-size 10 --row-wait-sec 90

# Run active-file cleanup with the separate Selenium headless profile.
python adobe_express_cleanup.py --apply --batch-size 100 --select-per-delete 2 --row-wait-sec 90 --headless
```

Use this when Adobe says the account storage is full and remove-background
jobs stall with Download/Export disabled. The cleanup uses the same Selenium
Chrome profile as `sel_remove_bg.py`, opens Adobe Express "Your stuff", selects
visible rows whose text contains `Remove background project`, deletes them,
refreshes, and repeats. That first pass moves files into Adobe Deleted, where
they still count until Adobe permanently removes them. Run the same helper with
`--deleted` to open `https://www.adobe.com/files/deleted` and permanently delete
matching rows. It is destructive only with `--apply`. Keep the default query
unless you intentionally want to delete a different class of Adobe files. The
Selenium remove-background step detects Adobe's storage-full banner and prints
the active cleanup, deleted-files cleanup, and resume commands before stopping
the batch.
Adobe's file list is virtualized, so the script works on the rendered viewport
and scrolls/refreshes to hydrate more rows. By default it selects and deletes
two rows per cycle because Adobe's bottom Delete toolbar can cover lower rows
after selection. `--batch-size` is the run target when `--max-delete` is not
set. Use `--viewports-per-delete` to select two rows, scroll to hydrate more
rows, select two more, and then delete the accumulated selection with fewer
confirmations. It waits for matching asset rows after Adobe's shell/navigation loads;
increase `--row-wait-sec` if the shell is ready but rows appear late. Selection
uses Adobe's `sp-table-checkbox-cell[label]` checkbox component by default. The
older screen-coordinate fallback is disabled unless `--coordinate-fallback` or
`ADOBE_CLEANUP_COORDINATE_FALLBACK=true` is set, because missed coordinate clicks
can open the editor instead of selecting rows. Use `--debug-dump` to write a live
DOM/control JSON file and screenshot under `config/adobe_express_cleanup_debug`
when selectors need tuning. `--headless` explicitly uses the separate Selenium
headless profile, even when `SEL_HEADLESS=false` for the normal
background-removal flow. Cleanup headless mode does not fall back to the normal
headed profile, because Adobe may serve the wrong page in that combination; if
the headless profile is not signed in or fails to load, the script writes a
debug dump and prints `python sel_remove_bg.py --login-only --headless-profile`.

Clean generated `config` artifacts:

```bash
# Preview cleanup. This is the default and deletes nothing.
python clean_people_config.py

# Delete generated logs/reports/review artifacts older than 14 days.
python clean_people_config.py --apply

# Use a shorter or longer age cutoff.
python clean_people_config.py --days 7 --apply

# Most aggressive cleanup this helper allows; still preserves chrome-profile.
python clean_people_config.py --max --apply

# Preview totals without listing every path.
python clean_people_config.py --max --summary-only
```

By default, cleanup preserves live pipeline state: `.env`, `people_list.txt`,
`people_overrides.txt`, orchestrator checkpoints, the Adobe Chrome profile,
model/vendor caches, active staging folders, `config/people_dirs`, and recovery
state files such as `exhausted_names.txt` and `attempted_candidates.csv`.
Generated intermediates such as `pre-online-checklist.txt` are cleanup
candidates; `people_list.txt` is preserved because it is active input.
Cleanup output includes total candidate count/bytes, file vs tree totals,
top-level config path totals, reason totals, and per-path delete details.
Use `--summary-only` when you only want the totals. Empty generated directories
are removed after cleanup unless `--no-empty-dirs` is passed.
Heavier cleanup is explicit:

```bash
# Forces models/vendor content to download or rebuild again.
python clean_people_config.py --include-caches --apply

# Clears checkpoints, so orchestrator steps are no longer marked complete.
python clean_people_config.py --include-checkpoints --apply

# Clears active staging folders. Use only when you want to discard pending work.
python clean_people_config.py --include-staging --apply

# Makes recovery forget exhausted names and attempted TMDB candidates.
python clean_people_config.py --include-recovery-state --apply
```

`--max` is shorthand for `--days 0 --include-staging --include-checkpoints
--include-caches --include-recovery-state`.
`config/chrome-profile` is never deleted by this helper. Remove it manually only
when you intentionally want to reset the Adobe browser profile and sign in again.

Occasional helpers:

- `resolve_original_images.py` — recover original JPGs by matching transparent/rainier outputs against TMDB first, then Google Custom Search when configured.
- `grayscale_sweeper.py` — scan an arbitrary folder tree for non-color images and stage them for the selected colorizer.
- `adobe_express_cleanup.py` — delete old Adobe Express remove-background projects when the account storage is full.
- `clean_people_config.py` — prune old generated logs, reports, review artifacts, and candidate previews from `config`.
- `bulk_extract_configs.py` — extract redacted config sections from mess/meta logs and nested archives.
- `auto_readme.py` / `sync_md.py` — retained for deliberate local README work, but normal README generation is owned by the People image repo GitHub Actions.

### Manual duplicate-name overrides
When two different TMDB people share the same name, the automatic log scan cannot disambiguate them. For those cases, add a manual line to `create_people_posters/config/people_overrides.txt`.

Recommended format:
```text
TMDB_ID|AliasToUse
```

Example for the second Akshay Kumar:
```text
35070|Akshay Kumar1
```

What happens next:
- `tmdb_people.py` downloads it as `Akshay Kumar1-35070.jpg`
- `truncate_tmdb_people_names.py` renames that to `Akshay Kumar1.jpg`
- `create_people_poster.ps1` strips the trailing `1` from the poster text, so the poster still says `Akshay Kumar`

If the pipeline has already run before, re-run from TMDB with:
```bash
python orchestrator.py --redo tmdb
```

If you want to begin at the TMDB step, use `python orchestrator.py --redo tmdb`.

The orchestrator now continues past zero-result log scans when `people_overrides.txt` contains entries.

### Resume & checkpoints
- **Checkpoints** are per batch in `./config/jobs/ID/.orch/*.done.json`.
  Full-clone/persistent fallback retains `./config/.orch/*.done.json`.
- **Run status**:
  ```bash
  python orchestrator.py --list
  ```
- **Redo from a step**:
  Clears that checkpoint and everything after it, then restarts at that exact step.
  ```bash
  python orchestrator.py --redo readme
  ```
- **Force** (ignore checkpoints, start from the beginning):
  ```bash
  python orchestrator.py --force
  ```

### Start mid‑pipeline
- From **prep_dirs** onward:
  ```bash
  python orchestrator.py --redo prep_dirs
  ```
- Just run **readme** and **sync_md** locally for **multiple styles**:
  These local-library commands require the full-clone/persistent fallback
  selected in `.env`; default API mode uses destination README workflows.
  ```bash
  # Local README generation is normally disabled because GitHub Actions owns it.
  # Enable it explicitly only for a deliberate local README pass.
  # .env → ORCH_STYLES=transparent,diiivoycolor
  python orchestrator.py --redo readme --generate-readmes
  # or override via CLI:
  python orchestrator.py --redo readme --styles transparent,diiivoycolor --generate-readmes
  ```

- Include per-letter `grid.jpg` previews only when explicitly requested:
  ```bash
  python orchestrator.py --redo readme --styles bw,diiivoy,diiivoycolor,rainier,signature --generate-readmes --grid-images
  ```

### Run the colorizer standalone
```bash
# With the colorizer venv activated:
python colorize_noncolor_ddcolor.py
# Reads from:  ./config/Downloads/other
# Writes to:   ./config/Downloads/color

```

### Sweep any tree for non‑color images (helper)
```bash
python grayscale_sweeper.py --src "D:/Pictures/Headshots" --dest-other "./config/Downloads/other"
python grayscale_sweeper.py --src "D:/Pictures/Headshots" --method auto
python grayscale_sweeper.py --help
```

This is an explicit local maintenance utility outside the normal orchestrator.
It never downloads, colorizes or publishes images. **Copy is the default**;
`--move` removes a source only after classification and a successful,
byte-verified destination copy. `--overwrite` explicitly permits replacement
of existing exact-name files. Failed staged replacements preserve the old file.

| Method | Intended use and unchanged defaults |
| --- | --- |
| `exact` (default) | Strict RGB channel equality; grayscale `1`, `L` and `LA` modes remain supported. |
| `sat` | Low-saturation heuristic: at least 98% of pixels have HSV saturation at or below `--sat-threshold` (default 8). |
| `satq` | NumPy linear saturation quantile at or below the threshold; `--sat-quantile` defaults to 0.95. The CLI threshold defaults to 8. |
| `colorfulness` | Original Hasler–Süsstrunk score strictly below `--colorfulness-cutoff` (default 12). |
| `auto` | Exact first, then saturation quantile with `max(--sat-threshold, 35)`, then colorfulness. |

The four heuristic methods can disagree about near-gray images; they do not
establish visual or branding approval. RGB/RGBA conversion preserves the
historical interpretation of hidden RGB values: alpha is not composited and
transparent pixels are not discarded. A fully transparent colored RGB logo
can therefore remain classified as colored.

Thresholds must be 0–255; quantiles must satisfy `0 < q <= 1`; colorfulness
cutoffs must be finite and non-negative. `--exts` accepts comma-separated
extensions (default `jpg,jpeg,png,webp,bmp,tif,tiff`). Invalid arguments fail
before processing. Exit 0 means scanning completed without errors, including
ordinary collision skips; argument errors exit 2, and file/setup errors exit 1.
Corrupt files and detector errors are logged and counted while other files
continue.

The recursive scan prunes its destination and the normal `Downloads/other`
and `Downloads/color` trees. Source/destination symlinks and Windows reparse
paths are rejected or reported and skipped. Source and destination cannot be
the same directory/file, and the destination cannot contain the source root.
Collection is flat: original basenames are kept. Sorted traversal makes
duplicate basenames deterministic; without `--overwrite`, the first wins and
later collisions are counted and skipped. With `--overwrite`, the last
exact-name match wins. Case/Unicode-normalization aliases are skipped even
with that flag. No conflicting file is silently renamed.

Copies preserve original bytes and filesystem timestamps where supported.
Default publication uses exclusive creation, preventing a concurrent same-name
arrival from being overwritten. Each run appends its log to
`DEST/.grayscale_sweeper.log`; importing the utility or requesting help creates
no processing directories and does not configure or truncate real logs.

Focused synthetic tests, from the repository root:

```bash
python -m pytest create_people_posters/tests/test_grayscale_sweeper.py -q
```

### Resolve original portraits from styled outputs
```bash
# Dry-run: compare transparent/rainier outputs to TMDB profiles first, then Google
# Custom Search image results if GOOGLE_API_KEY and GOOGLE_CSE_ID are configured.
python resolve_original_images.py --names "Anne Hathaway" "Pedro Pascal"

# Copy accepted matches into ./config/people_dirs/original as normalized 2000x3000 JPGs.
python resolve_original_images.py --names-file ./config/people_list.txt --apply

# Process all referenced names instead of only names missing local originals.
python resolve_original_images.py --all --limit 25
```

Results are written to `./config/original_resolver/manifest.csv`. Any name that
does not match TMDB or Google above `ORIGINAL_RESOLVER_THRESHOLD` is listed in
`./config/original_resolver/unresolved.txt` and gets a review contact sheet.

### Recover image warnings
```bash
# Safe no-scope run: writes a skipped report and avoids a whole-tree retry.
python recover_edge_chops.py

# Diagnostics only: bottom/left/right are edge-contact checks, not proof of chin
# or side chops.
python image_check.py --input_directory "./config/people_dirs/transparent" --style transparent --chop-edges top,bottom,left,right

# Face-model diagnostics only: report possible chin/side face crops.
python image_check.py --input_directory "./config/people_dirs/transparent" --style transparent --face-crop-checks chin,left,right
```

The orchestrator runs `recover_edge_chops.py` after `poster_ps1` by default,
scoped to transparent PNGs generated in that same `poster_ps1` run. It retries
top-edge head chops only unless `EDGE_CHOP_RECOVER_WARNINGS` or
`--recover-warnings` says otherwise. By default, black-and-white or near-grayscale TMDB
alternates are sent through the selected `COLORIZE_ENGINE` first, then rechecked; an alternate is
skipped only if it is still non-color afterward. Each remaining alternate first
runs through `rembg` locally; alternates that still have selected recovery
warnings are skipped before the Selenium/Adobe step. The head/top edge check
uses both edge alpha mean and foreground coverage, so narrow hair/head contact
at the top edge is not hidden by transparent space across the rest of the row.
The first alternate that passes the local precheck is sent through Adobe. In
default standalone mode, recovery stages viable alternates, runs the normal
orchestrator through `remove_bg` and `poster_ps1`, then checks the final
transparent poster output before repo sync/push. If Adobe's final output still
has selected warnings, the report marks that row unresolved and removes those
generated work outputs from `config/people_dirs`; rerun the same recovery
command to skip that attempted TMDB image and try the next unattempted
candidate. If no alternate clears the check, the script restores the previous local style outputs, writes
`./config/edge_chop_recovery/edge_chop_recovery.csv`, records the person in
`./config/edge_chop_recovery/exhausted_names.txt`, and continues the pipeline.
The recovery CSV includes `precheck_metrics` and `final_metrics` columns for
headchop runs so you can compare local `rembg` alpha/coverage values against
the Adobe final-output values.
Future recovery batches skip names in that exhausted file; remove a name from the
file if you want to retry it later. Batch staging also records tried TMDB image
paths in `./config/edge_chop_recovery/attempted_candidates.csv` so the next
batch does not choose the same alternate again. If a TMDB alternate is visually
the same as the current original JPG, it is recorded as attempted and skipped
before staging so the same head-chop source is not processed again.
Set `ORCH_RECOVER_EDGE_CHOPS=false` or pass `--no-recover-edge-chops` to skip it.
Set `EDGE_CHOP_PRECHECK_REMBG=false` or pass `--no-precheck-rembg` only when you
need to diagnose the older Adobe-only retry path. `rembg` is included in
`requirements.txt`; its model weights may download to `REMBG_HOME` on first use.
Local `rembg` precheck is intentionally stricter than final QA by default:
`EDGE_CHOP_PRECHECK_THRESHOLD=0.03` and
`EDGE_CHOP_PRECHECK_COVERAGE_THRESHOLD=0.005`, while final repo/audit checks keep
using `EDGE_CHOP_THRESHOLD=0.06` and `EDGE_CHOP_COVERAGE_THRESHOLD=0.015`.
Set `EDGE_CHOP_COLORIZE_GRAYSCALE=false` to skip the colorizer attempt, or set
`EDGE_CHOP_REJECT_GRAYSCALE=false` / pass `--allow-grayscale` only for a manual
exception.
`--recover-warnings` accepts `headchop`, `grayscale`, `face-chin`,
`face-left`, `face-right`, `face-side`, or `all`. `face-chin` and `face-side`
use the same face-model diagnostics as `image_check.py`; they are risk signals,
so keep them explicit rather than default.
Whole-tree backlog cleanup is opt-in:

```bash
# Audit whole tree but do not retry.
python recover_edge_chops.py --all --audit-only

# Work a small backlog batch through the normal orchestrator remove_bg/poster flow.
python recover_edge_chops.py --all --limit 25

# Work a larger batch from the backlog. This attempts 100 not-yet-exhausted people;
# TMDB alternates per person are controlled separately by EDGE_CHOP_TMDB_LIMIT.
python recover_edge_chops.py --all --limit 100

# Target discovery logs progress while it scans repo images.
python recover_edge_chops.py --all --limit 100 --scan-progress-every 250 --scan-progress-seconds 15

# Include grayscale/non-color warnings in the recovery batch.
python recover_edge_chops.py --all --limit 100 --recover-warnings headchop,grayscale

# Explicit face-model risk recovery modes.
python recover_edge_chops.py --all --limit 25 --recover-warnings face-chin,face-side

# Stage candidates without running orchestrator, for manual inspection.
python recover_edge_chops.py --all --limit 100 --stage-only

# Retry only named people.
python recover_edge_chops.py --names "Person One" "Person Two"
```

Whole-tree recovery reads the transparent repo tree from the repo root configured
by `PEOPLE_IMAGES_DIR`.
Use `EDGE_CHOP_PEOPLE_ROOT` or `--people-root` only when you intentionally want
to scan a different local repo set; use `EDGE_CHOP_TRANSPARENT_ROOT` or
`--transparent-root` only for a custom transparent tree. Target discovery logs
`[scan]` heartbeat lines by default every 500 inspected files or 30 seconds;
adjust with `EDGE_CHOP_SCAN_PROGRESS_EVERY`, `EDGE_CHOP_SCAN_PROGRESS_SECONDS`,
`--scan-progress-every`, or `--scan-progress-seconds`.

By default, standalone recovery stages viable candidates and runs
`python orchestrator.py --redo remove_bg --no-recover-edge-chops --stop-after poster_ps1`.
That reuses the orchestrator's checkpointed Selenium batch and poster
generation without falling back into the inline recovery loop. Recovery then
postchecks the generated transparent outputs, removes unresolved work outputs,
and only runs `python orchestrator.py --redo update --no-recover-edge-chops`
when at least one staged candidate passed final QA. Local README/MD steps remain
skipped unless `ORCH_GENERATE_READMES=true` or `--generate-readmes` is used;
remote GitHub Actions regenerates People image repo READMEs after push. The next recovery batch will rescan outputs, skip attempted TMDB
candidates, and choose the next alternate for anything still chopped or still
non-color. Do not use
`--redo tmdb` unless you intend to rerun TMDB download and all downstream
image-generation steps.

### Bulk extract redacted config.yml sections (helper)
```bash
python bulk_extract_configs.py --input_directory "C:/temp"
# Writes parsed_*.yml files to: ./config/parsed_configs
# Re-runs skip files that already have a matching parsed_*.yml output.
```

---

## Cross‑platform notes
- The default `poster_ps1` step is Python/Pillow and does not need `pwsh` or
  ImageMagick. The explicit `POSTER_ENGINE=powershell` fallback uses `pwsh`, or
  `powershell.exe` on Windows. Only that fallback needs the legacy installations.
- All Python steps use `sys.executable` so your **virtualenv** is honored on every OS.

---

## Troubleshooting

**Missing `./config/.env`**  
The orchestrator will create one from `.env.example` and exit; edit it and re‑run.

**People‑Images repo not found**  
This requirement applies only to the explicit `local_git` fallback. Default
`github_api` mode does not need `PEOPLE_IMAGES_DIR`. For full-clone mode, set it
in `.env` (or pass `--repo-root`) and ensure all seven clones exist on disk.

**TMDB errors / invalid key**  
Double‑check `TMDB_KEY` and your network. Try re‑running with `--redo tmdb`.

**Colorizer errors**  
- Use `.venv-ddcolor` with Python 3.13 and install `requirements-ddcolor.txt`.
- Keep `COLORIZE_ENGINE=ddcolor` and `COLORIZE_DEVICE=cpu` for CPU inference.
- The first run downloads the official source and model weights; later runs reuse the cache.

**Selenium step fails / element not found**  
Adobe Express may change the UI. Update selectors or timeouts in `sel_remove_bg.py` or run with `-v` for detailed logs.

**Legacy PowerShell renderer unavailable**
Select `POSTER_ENGINE=python` for the native renderer, or install PowerShell 7+
and ImageMagick to keep using `POSTER_ENGINE=powershell`. Then rerun that step:
```bash
python orchestrator.py --redo poster_ps1
```
The following installation instructions are only for the optional legacy renderer.
Install PowerShell 7+ (`pwsh`) in Linux:
```bash
# 1) Add Microsoft’s repo
sudo apt-get update
sudo apt-get install -y wget apt-transport-https software-properties-common
. /etc/os-release
wget -q https://packages.microsoft.com/config/ubuntu/$VERSION_ID/packages-microsoft-prod.deb -O packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
rm packages-microsoft-prod.deb

# 2) Install PowerShell 7
sudo apt-get update
sudo apt-get install -y powershell

# 3) Verify
pwsh --version
```
Install Powershell 7+ (`pwsh`) in macOS:
```bash
# If you don't have Homebrew yet (Apple Silicon default path shown):
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# Install PowerShell 7
brew update
brew install --cask powershell

# Verify
pwsh --version
```

**Interrupted run** (CTRL‑C/crash)  
Just run `python orchestrator.py` again. It resumes where it left off.

---

**Push to repositories not working** 
```bash
# 1) (Unix) Install and sign in (device login in a browser)
sudo apt-get update && sudo apt-get install -y gh
gh auth login           # GitHub.com → HTTPS → “Login with a web browser”
gh auth setup-git       # configure git to use gh’s token
gh auth status
```

## Optional QA tools
After syncing images to the repo (step 11), you can run:

```bash
# Single-tree dimensions and style-aware validity checks
python image_check.py --input_directory "./config/people_dirs/transparent" --style transparent

# Compare local repo style trees, including README, presence, dimension, and quality issues
python compare_image_trees.py --repo-root "C:/Users/bullmoose20/Kometa-People-Images"
```

Quality rules allow grayscale only for `bw` and `diiivoy`. `original`, `rainier`,
`signature`, `diiivoycolor`, and `transparent` must be color; `transparent` must
also contain alpha transparency. Transparent QA checks top-edge head chops by
default using both edge alpha mean and foreground coverage. Bottom/left/right
edge checks are available as explicit diagnostics,
but they are not semantic chin/side-chop proof because shoulders, necks, and
body crops can legitimately touch those edges. Transparent QA also runs a
report-only OpenCV face detector for possible chin/left/right face crop risk;
those findings are written as warnings or quality CSV rows, but they do not
trigger automatic recovery. Use `--face-crop-checks none` or set
`COMPTREE_FACE_CROP_CHECKS=none` to disable those diagnostics. The detector uses
OpenCV YuNet and caches `face_detection_yunet_2026may.onnx` under
`FACE_CROP_MODEL_HOME` on first use. Use `--no-quality` on
`compare_image_trees.py` only when you want the old presence/dimension-only
report. `compare_image_trees.py` also runs a quick README audit before the
full image scan by default: it compares README heading counts and entry names
to actual files, then writes `config/readme_issues.csv`. That catches stale
remote-generated READMEs separately from real missing-file drift. Use
`--no-readme` or set `COMPTREE_CHECK_README=false` only when you want to skip
that cheap precheck.

---

## Repo layout (key files)
```
create_people_posters/
├─ orchestrator.py
├─ ensure_people_repo.py
├─ scan_kometa_logs.py
├─ find_and_download_missing_people.py
├─ tmdb_people.py
├─ truncate_tmdb_people_names.py
├─ audit_people_images.py
├─ colorize_noncolor_ddcolor.py
├─ prep_people_dirs.py
├─ sel_remove_bg.py
├─ adobe_express_cleanup.py      # optional Adobe Express remote storage cleanup
├─ create_people_poster.ps1
├─ recover_edge_chops.py          # optional/non-blocking pipeline recovery
├─ clean_people_config.py         # optional config cleanup helper
├─ update_people_repos.py
├─ sync_people_images.py
├─ auto_readme.py
├─ sync_md.py
├─ grayscale_sweeper.py           # optional helper (standalone)
├─ resolve_original_images.py     # optional original resolver (TMDB, then Google fallback)
├─ bulk_extract_configs.py        # optional helper (standalone)
├─ image_check.py                 # optional QA
├─ compare_image_trees.py         # optional QA
└─ config/
   ├─ .env.example
   ├─ .env
   ├─ .orch/                     # checkpoints
   ├─ vendor/DDColor/            # auto-vendored DDColor package
   ├─ models/ddcolor/            # DDColor Hugging Face model cache
   ├─ Downloads/
   │  ├─ other/                  # non‑color inputs for colorizer
   │  └─ color/                  # colorized outputs (JPG)
   ├─ parsed_configs/            # extracted parsed_*.yml files
   └─ people_dirs/               # local working folders
```

---

## Contributing / PRs
- Keep new scripts **idempotent** and **log‑rich**.
- Use the same logging/progress template (see other scripts for reference).
- Avoid adding step reordering; propose new steps and we’ll place them explicitly.

## Local Background Removal (BiRefNet)

BiRefNet Portrait is the default after the owner's review of all 100 benchmark
portraits as the same as or better than Adobe. `REMOVE_BG_ENGINE=birefnet` selects local
ONNX inference through [rembg](https://github.com/danielgatis/rembg), avoiding
Adobe login, browser automation and cloud image processing for this step.
Adobe remains selectable for manual rollback during this trial snapshot.
The review used source-unverified clones; successful inference alone does not
establish better quality, and no exact per-image win/tie split is claimed.

### Python 3.13 CPU Installation

Run these commands from `create_people_posters`. Keep inference dependencies in
a separate environment to avoid changing the orchestrator or DDColor environment.

```powershell
py -3.13 -m venv .venv-rembg
.\.venv-rembg\Scripts\python.exe -m pip install -r requirements-rembg.txt
.\.venv-rembg\Scripts\python.exe -m pip check
```

```bash
python3.13 -m venv .venv-rembg
.venv-rembg/bin/python -m pip install -r requirements-rembg.txt
.venv-rembg/bin/python -m pip check
```

The orchestrator discovers `.venv-rembg` automatically. Set `REMOVE_BG_PYTHON`
to an absolute Python executable for another environment. It accepts an executable
path, not a shell command. Windows x64 Python 3.13 is tested; Linux/macOS and
other architectures require compatible dependency wheels and remain unverified
by this implementation's local validation. The native poster workflow uses
Pillow/fontTools without PowerShell or ImageMagick. Browser dependencies remain
required for Adobe.

BiRefNet Portrait and General each download roughly 973 MB of weights. Allow
several GB of disk space for all benchmark models and substantial additional RAM
for inference. The benchmark measures process RSS peak and runtime on your
machine; it loads one model at a time. ISNet General is a smaller comparison
baseline, not a guaranteed faster or better portrait model.

### Configuration and Batch Processing

Background-removal logs show the queue size and per-file counters such as
`processing [1/24]` and `processed [1/24]`. Skipped and failed files count toward
completed work while retaining their own status.

Add to `config/.env`:

```ini
REMOVE_BG_ENGINE=birefnet
REMOVE_BG_MODEL=birefnet-portrait
REMOVE_BG_DEVICE=cpu
REMOVE_BG_DECONTAMINATE=true
REMOVE_BG_ALPHA_MATTING=false
REMOVE_BG_OVERWRITE=false
REMOVE_BG_PYTHON=
REMBG_HOME=./config/models/rembg
```

Supported model names are `birefnet-portrait`, `birefnet-general` and
`isnet-general-use`. Soft masks are retained; binary mask postprocessing is
disabled. Decontamination estimates foreground edge colors. Optional alpha
matting refines alpha and decontaminates internally, can be slow, and may fail
on difficult images. Failures are reported rather than silently changing modes.

Weights download once and are reused under `REMBG_HOME`. Both downloaded and
cached weights are checked against the upstream model checksums and recorded
with SHA-256 identifiers. `MODEL_CHECKSUM_DISABLED` is rejected. These publisher
checksums detect corruption, not independent cryptographic certification.

Set `REMOVE_BG_ENGINE=birefnet` to select the local backend, then:

```powershell
# Single image: preserves the photograph in place.
.\.venv-rembg\Scripts\python.exe remove_bg_birefnet.py --input portrait.jpg --output config/test/portrait.png
# Existing staged batch, then resume only through poster generation.
.\.venv-rembg\Scripts\python.exe remove_bg_birefnet.py
python orchestrator.py --redo remove_bg --no-recover-edge-chops --stop-after poster_ps1
```

```bash
.venv-rembg/bin/python remove_bg_birefnet.py --input portrait.jpg --output config/test/portrait.png
.venv-rembg/bin/python remove_bg_birefnet.py
python3 orchestrator.py --redo remove_bg --no-recover-edge-chops --stop-after poster_ps1
```

The batch reads `SEL_SRC_DIR`, writes validated `stem.png` files to
`SEL_DOWNLOAD_DIR`, and stages copies in `SEL_SRC_DIR` for the existing poster
script. Only after validation and an intact archived copy in `SEL_ORIG_DIR` does
it remove the completed source from the input queue. It preserves stored pixel
dimensions, including JPEG/PNG/WebP/BMP/TIFF inputs. Animated or multipage files
are rejected. An already-transparent staged PNG is treated as a cutout, not a
new photograph. PNG photographs without meaningful transparency are supported.
Both poster engines honor `PEOPLE_CONFIG_DIR` and its `people_dirs` layout,
including isolated batch jobs. Generated styles and transparent presentation
are normalized to 2000x3000.
Local inference and archived photographs retain their native dimensions. With
the local engine selected, Original-style sync creates validated 2000x3000 RGB
JPEG presentation copies, leaving archived bytes unchanged. Already-compliant
JPEGs are copied exactly. Flat native archives are mapped to
`firstLetter/Images/name.jpg`; ambiguous publication targets fail preflight.
Reserved recovery `.history` directories are not published. The local
single-image tool never resizes its output.

Existing cutouts require matching source, model and settings provenance to skip
successfully. To rerun, restage the specific archived source photographs, set
`REMOVE_BG_OVERWRITE=true`, and use `--redo remove_bg`. Reset overwrite afterward.
A conflicting preserved original causes a failure; move it to a safe archival
location before deliberately retrying. Do not restage the entire original library
just to rerun a small batch. `.png.bg.json` files record provenance alongside
cutouts. Logs and machine-readable summaries are in `config/logs`.

Exit 0 means full success or no work (distinguished in the JSON summary), exit 1
means unresolved per-image failures, and exit 2 means a fatal configuration/model
initialization problem. A failed image stays available for retry. The orchestrator
stops on unresolved failures and does not fall back to Adobe automatically.
Changing engine, model or inference settings invalidates background-removal and
downstream checkpoints. It requires queued originals before recording success
under the new configuration; an old Adobe checkpoint is insufficient.

Local edge-chop recovery reuses a single remover for screening and accepted
candidate cutouts, retaining the existing crop checks and retry ordering.
An exhausted TMDB search is a nonfatal warning, matching Adobe: existing posters
are retained, quality warnings remain in the report, and other accepted candidates
can proceed. Actual processing errors or unresolved recovery failures still stop
the local pipeline. Exhaustion does not mean the portrait passed quality checks.
Adobe-selected recovery retains its existing Selenium path. A dedicated local
interpreter is also used by recovery when needed.
Local recovery uses `REMOVE_BG_*` model options and accepts `--rembg-home` as
a cache override. `EDGE_CHOP_REMBG_*` options configure the Adobe candidate
precheck only, not the primary local remover.

### Optional Acceleration

CPU requires no CUDA. For NVIDIA, create another isolated environment, install
the pinned CPU profile, uninstall `onnxruntime`, then install a compatible
`onnxruntime-gpu` version and its required CUDA/cuDNN runtime. Set
`REMOVE_BG_PYTHON` to that interpreter and `REMOVE_BG_DEVICE=cuda`. Consult the
[ONNX Runtime installation matrix](https://onnxruntime.ai/docs/install/).
Do not install CPU and GPU runtime packages together. `rocm` and `coreml` require
their corresponding ONNX providers. Requested acceleration fails explicitly when
the provider cannot load. Accelerator combinations have not been tested here.

### Benchmark and Human Review

Use read-only local clones of People-Images original and transparent repositories.
The comparison command never updates or pushes them. Benchmark outputs must be
outside every reference/source directory. Default sampling is deterministic and
limited to 100; full-library inference requires `--all`. See
[BACKGROUND_REMOVAL_IMPLEMENTATION.md](BACKGROUND_REMOVAL_IMPLEMENTATION.md)
for executed validation, remaining acceptance work and benchmark commands.

Adobe is a baseline, not segmentation ground truth. IoU and alpha disagreement
flag differences for inspection. Foreground coverage, soft-alpha distribution,
suspected clipping and potential halos are heuristics, not quality scores.
Source-unverified comparisons and unreviewed portraits must not be counted as
evidence of a model's quality advantage. Preserve the exact photograph submitted
to Adobe, including colorization and resizing, when constructing a verified set.

### Troubleshooting, Rollback and Licensing

For missing dependencies, install `requirements-rembg.txt` using the executable
selected by `REMOVE_BG_PYTHON`. For unavailable downloads, prepopulate the model
cache on a connected machine using the same pinned models, then copy it locally.
For a checksum mismatch, move the corrupt weight file aside and redownload.
For memory pressure, close other workloads and run one model at a time. For
invalid/empty masks, inspect the source and try the other supported model with
explicit overwrite in a separate output folder. Failed outputs are not published
over existing valid files during inference validation.

To roll back, set `REMOVE_BG_ENGINE=adobe`, restage the desired originals and run
`python orchestrator.py --redo remove_bg`. Adobe login/profile settings are retained.
For a full version rollback, the community can use the
[Adobe Express/Selenium snapshot](https://github.com/Kometa-Team/Defaults-Image-Creation/tree/adobe-express-snapshot-2026-10-14),
tagged at `90f477a`, the last Adobe-default version before the Portrait rollout.
Private `.env` files, browser profiles and generated assets are not stored in Git;
preserve those separately when changing versions.
Adobe code, dependencies and configuration are retained for this trial snapshot.
Remove them only after the production trial succeeds and removal is approved.

[rembg code](https://github.com/danielgatis/rembg/blob/main/LICENSE.txt) and
[BiRefNet code](https://github.com/ZhengPeng7/BiRefNet/blob/main/LICENSE) use MIT
licenses. The official [Portrait](https://huggingface.co/ZhengPeng7/BiRefNet-portrait)
and [General](https://huggingface.co/ZhengPeng7/BiRefNet) model cards also identify
MIT licensing. [DIS/ISNet code](https://github.com/xuebinqin/DIS/blob/main/LICENSE.md)
uses Apache-2.0.
Check the model publishers' terms and training-data restrictions for your use;
code licenses do not license the photographs. BRIA RMBG 2.0 is excluded from
required models because its [model terms](https://huggingface.co/briaai/RMBG-2.0)
restrict the openly available weights to noncommercial use.
