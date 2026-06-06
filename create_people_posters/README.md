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

# Single default style (used if ORCH_STYLES not set)
ORCH_STYLE=transparent

# Multi-style run (comma list). If set, overrides ORCH_STYLE in readme/sync_md steps.
ORCH_STYLES=transparent,diiivoycolor

# Optional commit/author for push
ORCH_COMMIT_MESSAGE=chore: sync posters & docs
ORCH_GIT_USER_NAME=Your Name
ORCH_GIT_USER_EMAIL=you@example.com

# Background-removal verification
SEL_DOWNLOAD_DIR=./config/sel_downloads               # where sel_remove_bg.py writes processed PNGs
ORCH_BG_EXTS=png                                      # exts to count after remove_bg (csv)
ORCH_CONTINUE_IF_EMPTY=false                          # continue run even if 0 PNGs were produced

# Hard requirements (fail fast when true)
ORCH_REQUIRE_POWERSHELL=false
ORCH_REQUIRE_BG_OUTPUT=false

# Colorizer (optional)
# If you keep a separate venv just for DeOldify, point to its python here:
COLORIZE_PYTHON=D:/Defaults-Image-Creation/create_people_posters/.venv-colorize/Scripts/python.exe
COLORIZE_PYTHON=/absolute/path/to/.venv-colorize/bin/python
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
> If Adobe blocks download behind a login/sign-up modal, the script will now pause and let you complete login in the same Chrome profile, then resume after you press Enter in the terminal.
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
11. **update** → `update_people_repos.py --op update` — fetch/reset style repos (**always runs**)  
12. **sync_images** → `sync_people_images.py` — copy new images into the repo style folders  
13. **readme** → `auto_readme.py` — generate per‑letter grids and READMEs for one or more styles  
14. **sync_md** → `sync_md.py` — mirror `*.md` back to `./config/people_dirs/<style>`  
15. **push** → `update_people_repos.py --op push` — commit & push changes (**always runs**)

> Optional QA tools (not wired by default): `image_check.py`, `compare_image_trees.py` — useful **after** step 11.
> Optional helper (outside the orchestrator): `grayscale_sweeper.py` — scan any folder tree for non‑color images and copy them into `config/Downloads/other` so `colorize_noncolor.py` can convert them.

---

## Run it

```bash
# The usual way: resume from the first incomplete step
python orchestrator.py
```

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

If you are starting fresh and just want to begin at the TMDB step, `python orchestrator.py --from tmdb` also works.

The orchestrator now continues past zero-result log scans when `people_overrides.txt` contains entries.

### Resume & checkpoints
- **Checkpoints** are JSON files in `./config/.orch/*.done.json`.
- **Run status**:
  ```bash
  python orchestrator.py --list
  ```
- **Start at a specific step** (order is still enforced afterward):
  ```bash
  python orchestrator.py --from tmdb
  ```
- **Redo from a step** (clears that checkpoint and everything after it):
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
  python orchestrator.py --from prep_dirs
  ```
- Just run **readme** and **sync_md** for **multiple styles** (uses env or CLI styles):
  ```bash
  # .env → ORCH_STYLES=transparent,diiivoycolor
  python orchestrator.py --from readme
  # or override via CLI:
  python orchestrator.py --from readme --styles transparent,diiivoycolor
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
Double‑check `TMDB_KEY` and your network. Try re‑running from `--from tmdb`.

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
# Dimensions & basic validity checks
python image_check.py

# Compare presence across style trees
python compare_image_trees.py
```

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
├─ update_people_repos.py
├─ sync_people_images.py
├─ auto_readme.py
├─ sync_md.py
├─ grayscale_sweeper.py           # optional helper (standalone)
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
   └─ people_dirs/               # local working folders
```

---

## Contributing / PRs
- Keep new scripts **idempotent** and **log‑rich**.
- Use the same logging/progress template (see other scripts for reference).
- Avoid adding step reordering; propose new steps and we’ll place them explicitly.
