# Create People Posters — Cross‑Platform Pipeline

This repo automates generating, curating, colorizing, and publishing **Kometa People Images** (posters) across styles.  
It’s designed to be **cross‑platform**, **fixed‑order**, and **resumable** so you can stop and restart safely.

---

## Highlights
- **One command** to run the whole pipeline: `python orchestrator.py`
- **Fixed order** (no reordering) to keep outputs consistent
- **Resume after crash/CTRL‑C** via automatic checkpoints
- Works on **Windows / macOS / Linux** (PowerShell step uses `pwsh` where available)
- Consistent **logging & progress** across scripts

---

## Prerequisites
- **Python 3.10+** (3.10 recommended for the colorizer venv)
- **pip** to install dependencies
- **Chrome/Edge** installed — required by the Selenium step
- **PowerShell** for the poster script step:
  - Preferred: **PowerShell 7+** (`pwsh`, cross‑platform)
  - Windows fallback: `powershell` / `powershell.exe`

> The orchestrator will **skip** the PowerShell step if no PS executable is found; you can re‑run just that step later (see _Resume & checkpoints_).

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

**Minimum required:**
```ini
TMDB_KEY=your_tmdb_api_key_here
```

**Recommended:**
```ini
# Orchestrator
ORCH_LOGS_DIR=/absolute/path/to/kometa/logs          # used by steps 2–3
PEOPLE_IMAGES_DIR=/absolute/path/to/Kometa-People-Images
PEOPLE_BRANCH=master                                  # optional; branch for update/push
SYNC_PREFLIGHT=true                                   # optional; source QA before sync
SYNC_MARKDOWN=false                                   # keep local sync from overwriting GitHub-generated READMEs

# Single default style (used if ORCH_STYLES not set)
ORCH_STYLE=transparent

# Local README generation is disabled by default because GitHub Actions owns
# README generation in the People image repos.
ORCH_GENERATE_READMES=false

# Multi-style local README run (comma list). Used only when ORCH_GENERATE_READMES=true.
ORCH_STYLES=transparent,diiivoycolor

# Grid image generation is slow and only applies to local README generation.
ORCH_GRID_IMAGES=false

# Optional commit/author for push
ORCH_COMMIT_MESSAGE=chore: sync posters & docs
ORCH_GIT_USER_NAME=Your Name
ORCH_GIT_USER_EMAIL=you@example.com

# Background-removal verification
SEL_DOWNLOAD_DIR=./config/sel_downloads               # where sel_remove_bg.py writes processed PNGs
ORCH_BG_EXTS=png                                      # exts to count after remove_bg (csv)
ORCH_CONTINUE_IF_EMPTY=false                          # continue run even if 0 PNGs were produced
EDGE_CHOP_PRECHECK_REMBG=true                         # prefilter retry candidates locally before Adobe
REMBG_HOME=./config/models/rembg                       # rembg model cache for recovery
EDGE_CHOP_REJECT_GRAYSCALE=true                       # do not accept B/W TMDB alternates during recovery
EDGE_CHOP_COLORIZE_GRAYSCALE=true                     # try DeOldify before rejecting B/W alternates
EDGE_CHOP_RECOVER_WARNINGS=headchop                   # headchop,grayscale,face-chin,face-side,all
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
# If you keep a separate venv just for DeOldify, point to its python here:
COLORIZE_PYTHON=D:/Defaults-Image-Creation/create_people_posters/.venv-colorize/Scripts/python.exe
COLORIZE_PYTHON=/absolute/path/to/.venv-colorize/bin/python

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
SEL_DOWNLOAD_DIR=./config/sel_downloads               # output PNGs from Adobe Express

# Size enforcement (input JPGs)
SEL_EXPECT_WIDTH=2000
SEL_EXPECT_HEIGHT=3000
SEL_ENFORCE_SIZE=true

# Timeouts/tuning (seconds)
SEL_MAX_WAIT_READY_SEC=60
SEL_PROC_TIMEOUT=120
SEL_MAX_WAIT_DL_SEC=20
SEL_DL_BUTTON_TIMEOUT=12
SEL_RELOAD_EACH_FILE=true
SEL_PROMPT_FOR_LOGIN=true
SEL_LOGIN_WAIT_SEC=900
```

> Tip: run `sel_remove_bg.py -v` once to see which env keys your build respects; the script logs the active configuration.
> If Adobe blocks download behind a login/sign-up modal, the script will pause
> for up to `SEL_LOGIN_WAIT_SEC`, let you complete login in the same Chrome
> profile, and retry after you press Enter or after it detects that the Adobe
> login gate cleared.
> You can also prepare the Selenium profile ahead of time with `python sel_remove_bg.py --login-only`, sign into Adobe in that browser window once, then rerun the full pipeline.

---

## Optional (but recommended): DeOldify colorizer setup (separate venv)

DeOldify (fastai v1) is pinned to stable, CPU‑only packages for maximum compatibility.
We recommend a **dedicated venv** (Python **3.10**) for this step.

## Install (base environment)

```bash
# Windows:
# 1) Create & activate a dedicated venv
py -3.10 -m venv .venv-colorize
.\.venv-colorize\Scripts\Activate.ps1   # or Activate.bat

# 2) Upgrade pip and install base requirements
pip install -U pip setuptools wheel
pip install -r requirements-colorize.txt

# 3) Tell orchestrator where that Python lives (add to .env)
# COLORIZE_PYTHON=C:\path\to\create_people_posters\.venv-colorize\Scripts\python.exe
```

```bash
# macOS/Linux:
# Install Python 3.10 (on 22.04 it’s in the archive; on 24.04 use deadsnakes)
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.10 python3.10-venv

# New venv *with 3.10*
cd Defaults-Image-Creation/create_people_posters
python3.10 -m venv .venv-colorize
source .venv-colorize/bin/activate

# Upgrade tooling and install the pinned reqs
pip install -U pip setuptools wheel
pip install -r requirements-colorize.txt

# 3) Tell orchestrator where that Python lives (add to .env)
# COLORIZE_PYTHON=/path/to/create_people_posters/.venv-colorize/Scripts/python3
```

> The colorizer will auto‑vendor DeOldify source and auto‑download the `ColorizeArtistic_gen.pth` weights on first run.

---

# People Images: One-Time Repository Setup

The orchestrator expects **seven** repos under one root folder (the path is read from `PEOPLE_IMAGES_DIR`). Clone them as follows.

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

1. **ensure_repo** → `ensure_people_repo.py` — validate Kometa‑People‑Images repo directory (**always runs**)  
2. **scan_kometa_logs** → `scan_kometa_logs.py` — scan Kometa logs for missing names  
3. **find_and_download_missing** → `find_and_download_missing_people.py` — build missing‑people lists from logs  
4. **tmdb** → `tmdb_people.py` — download posters via TMDB API  
5. **truncate** → `truncate_tmdb_people_names.py` — normalize/shorten person names  
6. **audit_people_images** → `audit_people_images.py` — directory‑based discovery to catch stragglers  
7. **colorize** → `colorize_noncolor.py` — **DeOldify**: move non‑color → color (keeps basenames, JPG)  
8. **prep_dirs** → `prep_people_dirs.py` — ensure local `./config/people_dirs` scaffolds exist  
9. **remove_bg** → `sel_remove_bg.py` — background removal via Selenium (Adobe Express)  
10. **poster_ps1** → `create_people_poster.ps1` — poster generation (PowerShell)  
11. **recover_edge_chops** → `recover_edge_chops.py` — non-blocking TMDB alternate retry for top-edge head chops
12. **update** → `update_people_repos.py --op update` — fetch/reset style repos (**always runs**)
13. **sync_images** → `sync_people_images.py` — copy new images into the repo style folders; skips markdown by default
14. **readme** → `auto_readme.py` — optional local README generation; skipped by default because GitHub Actions owns README generation
15. **sync_md** → `sync_md.py` — optional local markdown mirror; skipped by default with local README generation disabled
16. **push** → `update_people_repos.py --op push` — commit & push changes (**always runs**)

> Optional QA tools: `image_check.py`, `compare_image_trees.py` — ad hoc reporting for grayscale, dimensions, transparency, edge chops, face-crop risk, and repo/tree consistency.
> Optional helper (outside the orchestrator): `grayscale_sweeper.py` — scan any folder tree for non‑color images and copy them into `config/Downloads/other` so `colorize_noncolor.py` can convert them.
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

### Common operator commands

Run the normal people pipeline from a folder of Kometa logs:

```bash
python orchestrator.py --logs-dir "C:/path/to/kometa/logs"
```

Retry from log scanning when you want to rescan the same folder:

```bash
python orchestrator.py --redo scan_kometa_logs --logs-dir "C:/path/to/kometa/logs"
```

Build `config/people_list.txt` from TMDB popular people:

```bash
# Preview without writing.
python tmdb_top_people_list.py --limit 1000 --require-profile --dry-run

# Write the list, filtering out people already present in the configured image repos.
python tmdb_top_people_list.py --limit 1000 --require-profile

# Process the generated list through TMDB and downstream image steps.
python orchestrator.py --redo tmdb
```

Use a smaller TMDB popular batch:

```bash
python tmdb_top_people_list.py --limit 250 --require-profile
python orchestrator.py --redo tmdb
```

Audit warning-based recovery targets without changing files:

```bash
python recover_edge_chops.py --all --audit-only --recover-warnings headchop
```

Whole-tree recovery audits the local cloned image repos from `PEOPLE_IMAGES_DIR`
by default, not the temporary `config/people_dirs` build folders. It scans
`PEOPLE_IMAGES_DIR/transparent` for head/face-crop warnings and the configured
style repos for grayscale warnings, stages viable replacement originals into
`config/people_dirs/Downloads`, then hands off to the orchestrator.

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

Run ad hoc QA reports:

```bash
python image_check.py --input_directory "C:/Users/bullmoose20/Kometa-People-Images/transparent" --style transparent
python compare_image_trees.py --repo-root "C:/Users/bullmoose20/Kometa-People-Images"
```

Occasional helpers:

- `resolve_original_images.py` — recover original JPGs by matching transparent/rainier outputs against TMDB first, then Google Custom Search when configured.
- `grayscale_sweeper.py` — scan an arbitrary folder tree for non-color images and stage them for DeOldify.
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
- **Checkpoints** are JSON files in `./config/.orch/*.done.json`.
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
python colorize_noncolor.py
# Reads from:  ./config/Downloads/other
# Writes to:   ./config/Downloads/color
```

### Sweep any tree for non‑color images (helper)
```bash
python grayscale_sweeper.py --root "D:/Pictures/Headshots" --dest "./config/Downloads/other"
# Skips files that already exist at the destination (by name).
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
alternates are sent through DeOldify first, then rechecked; an alternate is
skipped only if it is still non-color afterward. Each remaining alternate first
runs through `rembg` locally; alternates that still have selected recovery
warnings are skipped before the Selenium/Adobe step. The first alternate that
passes the local precheck is sent through Adobe, then the final poster output is
checked again for the selected recovery warnings. If no alternate clears the check,
the script restores the previous local style outputs, writes
`./config/edge_chop_recovery/edge_chop_recovery.csv`, records the person in
`./config/edge_chop_recovery/exhausted_names.txt`, and continues the pipeline.
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
Set `EDGE_CHOP_COLORIZE_GRAYSCALE=false` to skip the DeOldify attempt, or set
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

# Include grayscale/non-color warnings in the recovery batch.
python recover_edge_chops.py --all --limit 100 --recover-warnings headchop,grayscale

# Explicit face-model risk recovery modes.
python recover_edge_chops.py --all --limit 25 --recover-warnings face-chin,face-side

# Stage candidates without running orchestrator, for manual inspection.
python recover_edge_chops.py --all --limit 100 --stage-only

# Retry only named people.
python recover_edge_chops.py --names "Person One" "Person Two"
```

Whole-tree recovery reads from the repo root configured by `PEOPLE_IMAGES_DIR`.
Use `EDGE_CHOP_PEOPLE_ROOT` or `--people-root` only when you intentionally want
to scan a different local repo set; use `EDGE_CHOP_TRANSPARENT_ROOT` or
`--transparent-root` only for a custom transparent tree.

By default, standalone recovery stages viable candidates and immediately runs
`python orchestrator.py --redo remove_bg --no-recover-edge-chops`. That reuses
the orchestrator's checkpointed Selenium batch, poster generation, repo update,
sync, and push steps without falling back into the inline recovery loop. Local
README/MD steps remain skipped unless `ORCH_GENERATE_READMES=true` or
`--generate-readmes` is used; remote GitHub Actions regenerates People image
repo READMEs after push. The next recovery batch will rescan outputs, skip attempted TMDB
candidates, and choose the next alternate for anything still chopped. Do not use
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
- The orchestrator prefers **PowerShell 7 (`pwsh`)** for the `poster_ps1` step.  
  On Windows, it will fall back to `powershell.exe` if `pwsh` isn’t present.  
  On macOS/Linux, install PowerShell from Microsoft’s package if you need that step.
- All Python steps use `sys.executable` so your **virtualenv** is honored on every OS.

---

## Troubleshooting

**Missing `./config/.env`**  
The orchestrator will create one from `.env.example` and exit; edit it and re‑run.

**People‑Images repo not found**  
Set `PEOPLE_IMAGES_DIR` in `.env` (or pass `--repo-root`) and ensure the repo exists on disk.

**TMDB errors / invalid key**  
Double‑check `TMDB_KEY` and your network. Try re‑running with `--redo tmdb`.

**Colorizer errors**  
- Use a dedicated venv (Python 3.10).  
- The first run will download ResNet34 weights and `ColorizeArtistic_gen.pth` automatically.

**Selenium step fails / element not found**  
Adobe Express may change the UI. Update selectors or timeouts in `sel_remove_bg.py` or run with `-v` for detailed logs.

**PowerShell step skipped**  
Install PowerShell 7+ (`pwsh`) or run on Windows. Then rerun just that step:
```bash
python orchestrator.py --redo poster_ps1
```
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
default. Bottom/left/right edge checks are available as explicit diagnostics,
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
├─ colorize_noncolor.py
├─ prep_people_dirs.py
├─ sel_remove_bg.py
├─ create_people_poster.ps1
├─ recover_edge_chops.py          # optional/non-blocking pipeline recovery
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
   ├─ vendor/deoldify/           # auto-vendored package (colorizer)
   ├─ models/deoldify/           # ColorizeArtistic_gen.pth
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
