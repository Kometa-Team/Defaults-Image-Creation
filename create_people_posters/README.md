# Create People Posters — Cross‑Platform Pipeline

This repo automates generating, curating, and publishing **Kometa People Images** (posters) across styles.  
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
- **Python 3.9+** (3.10+ recommended)
- **pip** to install dependencies
- **Chrome** (or Edge) installed — required by the Selenium step
- **PowerShell** for the poster script step:
  - Preferred: **PowerShell 7+** (`pwsh`, cross‑platform)
  - Windows fallback: `powershell` / `powershell.exe`

> The orchestrator will **skip** the PowerShell step if no PS executable is found; you can rerun just that step later (see _Resume & checkpoints_).

---

## Install

```bash
# 1) Clone your repo and cd into it
git clone <your-fork-or-repo-url> create_people_posters
cd create_people_posters

# 2) (Optional) create and activate a virtualenv
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3) Install dependencies
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
ORCH_STYLE=transparent                                # style used for README/sync (default: transparent)
ORCH_COMMIT_MESSAGE=chore: sync posters & docs
ORCH_GIT_USER_NAME=Your Name                          # optional
ORCH_GIT_USER_EMAIL=you@example.com                   # optional
```

**Selenium background removal (used by `sel_remove_bg.py`)**  
These keys are read by the script; set what you need for your environment. Common ones:

```ini
# Source/destination
SEL_SRC_DIR=./config/people_dirs/transparent/originals
SEL_ORIG_DIR=./config/people_dirs/transparent/originals       # if you keep originals separate
SEL_DOWNLOAD_DIR=./config/people_dirs/transparent/transparent # where processed images land

# Tool and browser profile
SEL_TOOL_URL=https://express.adobe.com/tools/remove-background
SEL_PROFILE_DIR=~/.config/chrome-profile                       # or Windows user data dir
SEL_USER_DATA_DIR=                                             # alternative profile key if used

# Output sanity limits
SEL_EXPECT_WIDTH=1000
SEL_EXPECT_HEIGHT=1500
SEL_ENFORCE_SIZE=1                                             # 1 to enforce, 0 to warn

# Timeouts/tuning (seconds)
SEL_MAX_WAIT_READY_SEC=30
SEL_MAX_WAIT_DL_SEC=120
SEL_PROC_TIMEOUT=60
SEL_DL_BUTTON_TIMEOUT=20
SEL_RELOAD_EACH_FILE=0
```

> Tip: run `sel_remove_bg.py -v` once to see which env keys your build respects; the script logs the active configuration.

---

## How it works (fixed order)

The orchestrator enforces the single correct order and writes checkpoints so you can resume later:

1. **ensure_repo** → `ensure_people_repo.py` — validate Kometa‑People‑Images repo directory (always runs)  
2. **name_check** → `name_checker_dir.py` — scan Kometa logs for missing names  
3. **missing** → `get_missing_people.py` — build missing‑people lists from logs  
4. **tmdb** → `tmdb_people.py` — download posters via TMDB API  
5. **truncate** → `truncate_tmdb_people_names.py` — normalize/shorten person names  
6. **missing_dir** → `get_missing_people_dir.py` — directory‑based discovery to catch stragglers  
7. **prep_dirs** → `prep_people_dirs.py` — ensure local `./config/people_dirs` scaffolds exist  
8. **remove_bg** → `sel_remove_bg.py` — background removal via Selenium (Adobe Express)  
9. **poster_ps1** → `create_people_poster.ps1` — poster generation step (PowerShell)  
10. **update** → `update_people_repos.py --op update` — fetch/reset style repos (always runs)  
11. **sync_images** → `sync_people_images.py` — copy new images into the repo style folders  
12. **readme** → `auto_readme.py` — generate per‑letter grids and READMEs for the chosen style  
13. **sync_md** → `sync_md.py` — mirror `*.md` back to `./config/people_dirs/<style>`  
14. **push** → `update_people_repos.py --op push` — commit & push changes (always runs)

> Optional QA tools (not wired by default): `image_check.py`, `compare_image_trees.py` — useful **after** step 11.

---

## Run it

```bash
# The usual way: resume from the first incomplete step
python orchestrator.py
```

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

### Environment overrides at runtime
```bash
# Example: set repo root and style on the command line
python orchestrator.py --repo-root "/path/to/Kometa-People-Images" --style transparent
```

---

## Cross‑platform notes
- The orchestrator prefers **PowerShell 7 (`pwsh`)** for the `poster_ps1` step.  
  On Windows, it will fall back to `powershell.exe` if `pwsh` isn’t present.  
  On macOS/Linux, install PowerShell from Microsoft’s package if you need that step.
- All Python steps use `sys.executable` so your **virtualenv** is honored on every OS.

---

## Troubleshooting

**“Missing ./config/.env”**  
The orchestrator will create one from `.env.example` and exit; edit it and re‑run.

**“People‑Images repo not found”**  
Set `PEOPLE_IMAGES_DIR` in `.env` (or pass `--repo-root`) and ensure the repo exists on disk.

**TMDB errors / invalid key**  
Double‑check `TMDB_KEY` and your network. Try re‑running from `--from tmdb`.

**Selenium step fails / element not found**  
Adobe Express may change the UI. Update selectors or timeouts in `sel_remove_bg.py` or run with `-v` for detailed logs.

**PowerShell step skipped**  
Install PowerShell 7+ (`pwsh`) or run on Windows. Then rerun just that step:
```bash
python orchestrator.py --redo poster_ps1
```

**Interrupted run** (CTRL‑C/crash)  
Just run `python orchestrator.py` again. It resumes where it left off.

---

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
├─ name_checker_dir.py
├─ get_missing_people.py
├─ tmdb_people.py
├─ truncate_tmdb_people_names.py
├─ get_missing_people_dir.py
├─ prep_people_dirs.py
├─ sel_remove_bg.py
├─ create_people_poster.ps1
├─ update_people_repos.py
├─ sync_people_images.py
├─ auto_readme.py
├─ sync_md.py
├─ image_check.py                # optional QA
├─ compare_image_trees.py        # optional QA
└─ config/
   ├─ .env.example
   ├─ .env
   ├─ .orch/                     # checkpoints
   └─ people_dirs/               # local working folders
```

---

## Contributing / PRs
- Keep new scripts **idempotent** and **log‑rich**.
- Use the same logging/progress template (see other scripts for reference).
- Avoid adding step reordering; propose new steps and we’ll place them explicitly.
