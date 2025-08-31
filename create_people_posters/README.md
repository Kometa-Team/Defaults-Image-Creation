# Create People Posters — Cross‑Platform Pipeline

A cross‑platform (Windows/macOS/Linux) pipeline to generate, clean, sync, and publish People posters for Kometa. This repo replaces `runit.cmd` with a Python **`orchestrator.py`** so you can run the whole flow anywhere.

## Quick Start

1) **Python 3.10+** and **pip** installed  
2) (Recommended) Create & activate a virtualenv  
3) Install deps:
   ```bash
   pip install -r requirements.txt
   ```
4) Bootstrap your env:
   ```bash
   # First run will copy .env.example to ./config/.env and exit
   python orchestrator.py --all
   # Then edit ./config/.env and set: TMDB_KEY=your_api_key
   ```

## Orchestrator

Run the whole pipeline or pick steps. Uses `sys.executable` so it works in venvs and on all OSes.

```bash
# Everything (repo required)
python orchestrator.py --all --repo-root "/path/to/Kometa-People-Images"

# Just the logs-driven discovery (no repo required)
python orchestrator.py --steps name_check,missing --logs-dir "/path/to/kometa/logs"

# Custom selection (remote always wins before syncing)
python orchestrator.py --steps ensure_repo,update,sync_images,readme,sync_md   --repo-root "/srv/Kometa-People-Images" --style transparent

# Full publish flow (includes final push)
python orchestrator.py --steps ensure_repo,update,sync_images,readme,sync_md,push   --repo-root "/srv/Kometa-People-Images" --style transparent
```

### Default step order
1. **ensure_people_repo.py** — validate Kometa‑People‑Images repo (fail‑fast if missing)  
2. **name_checker_dir.py** — scan Kometa logs for missing names  
3. **get_missing_people.py** — build missing‑people lists  
4. **tmdb_people.py** — download posters via TMDB  
5. **sel_remove_bg.py** — background removal via Adobe Express  
6. **update_people_repos.py** — **pull latest with `git fetch` + `reset --hard` + `clean -fdx` (remote always wins)**  
7. **sync_people_images.py** — copy images from `./config/people_dirs/*` → repo  
8. **auto_readme.py** — generate README grid for the chosen `style`  
9. **sync_md.py** — mirror `*.md` back to `./config/people_dirs/<style>`  
10. **push** — commit & push changes upstream

> Why update before sync? It guarantees you start from the latest upstream and avoids merge noise.

### Remote‑Always‑Wins update
By default the orchestrator calls the update step with:
- `git fetch origin`  
- `git reset --hard origin/<branch>`  
- `git clean -fdx`  

So your local repos **exactly match the remote** before any local files are added.  
If you ever want a gentler update (fast‑forward only), edit `_update_repos()` in `orchestrator.py` to remove `--mode hardreset --clean-ignored`, or run `update_people_repos.py` directly with `--mode ffonly`.

### Final push (Step 10)
The `push` step stages, commits (if there are changes), and pushes each category repo’s current branch. It uses your local Git credentials (SSH key or HTTPS token).

Example:
```bash
python orchestrator.py --steps ensure_repo,update,sync_images,readme,sync_md,push   --repo-root "/srv/Kometa-People-Images" --style transparent
```

You can customize the commit message and author via env (see below).

## Configuration — `./config/.env`

All scripts read from `./config/.env`. The first run creates it from `.env.example` and exits so you can fill in values.

**Required**
- `TMDB_KEY` — TMDB v3 API key

**Common**
- `PEOPLE_IMAGES_DIR` — absolute path to Kometa‑People‑Images (repo root)
- `PEOPLE_BRANCH` — branch for updates (leave empty to auto‑detect per repo; otherwise e.g. `master` or `main`)
- `ORCH_LOGS_DIR` — Kometa logs folder (for `name_checker_dir.py` / `get_missing_people.py`)
- `ORCH_STYLE` — style folder for README/sync_md (e.g., `transparent`)

**Push (Step 10) – optional**
- `ORCH_COMMIT_MESSAGE` — default commit message (auto-generated if not set)
- `ORCH_GIT_USER_NAME` — optional `user.name` override before committing
- `ORCH_GIT_USER_EMAIL` — optional `user.email` override before committing

**Adobe Express Remove Background (Selenium)**
- `SEL_USER_DATA_DIR`, `SEL_PROFILE_DIR`
- `SEL_SRC_DIR`, `SEL_ORIG_DIR`, `SEL_DOWNLOAD_DIR`
- `SEL_MAX_WAIT_READY_SEC`, `SEL_PROC_TIMEOUT`, `SEL_MAX_WAIT_DL_SEC`, `SEL_DL_BUTTON_TIMEOUT`
- `SEL_RELOAD_EACH_FILE`
- `SEL_EXPECT_WIDTH`, `SEL_EXPECT_HEIGHT`, `SEL_ENFORCE_SIZE`
- `SEL_TOOL_URL`

See `.env.example` for suggested defaults.

## QA Utilities

### 1) image_check.py (single‑tree validation)

Validate a single directory of images for expected dimensions and extensions before syncing.

Examples:
```bash
# Validate JPGs produced by TMDB against 2000x3000
python image_check.py --root "./config/posters" --exts jpg,jpeg --required-size 2000x3000

# Validate the 'transparent' repo folder contains PNGs with expected size
python image_check.py --root "/srv/Kometa-People-Images/transparent" --exts png --required-size 2000x3000

# Case-insensitive names & recursive scan (default behavior)
python image_check.py --root "./config/people_dirs/original"
```

Common flags (actual flags may vary slightly depending on your version):
- `--root PATH` — directory to scan (recursive)
- `--exts csv` — allowed extensions, e.g., `png` or `jpg,jpeg`
- `--required-size WxH` — e.g., `2000x3000`
- `--no-dimensions` — skip dimension checks (presence only)
- Logs and any CSV outputs are written under `./config/`

### 2) compare_image_trees.py (7‑tree matrix)

`compare_image_trees.py` verifies that stems exist across all seven style folders, flags extension rule violations (.png in the PNG dir, .jpg elsewhere), and can enforce dimensions (default 2000×3000).

Examples:
```bash
# Repo‑based (auto categories)
python compare_image_trees.py --repo-root "/srv/Kometa-People-Images"

# Explicit seven dirs
python compare_image_trees.py --dirs "/srv/PI/bw" "/srv/PI/diiivoy" "/srv/PI/diiivoycolor" "/srv/PI/rainier" "/srv/PI/original" "/srv/PI/signature" "/srv/PI/transparent"

# Disable dimension checks or change size
python compare_image_trees.py --no-dimensions
python compare_image_trees.py --required-size 2000x3000

# Case-insensitive compare
python compare_image_trees.py --case-insensitive

# If the PNG folder isn’t named “transparent”
python compare_image_trees.py --png-dir-index 6
```

Supported env overrides:  
`COMPARE_CATEGORIES`, `COMPTREE_PNG_INDEX`, `COMPTREE_CASE_SENSITIVE`, `COMPTREE_CHECK_DIMENSIONS`, `COMPTREE_REQUIRED_SIZE`, `COMPTREE_JPG_WHITELIST`.

Outputs under `./config/`:
- `compare_image_trees.csv`
- `image_dimension_issues.csv` (when enabled)

## Cross‑Platform Notes

- Use absolute paths or forward slashes in `.env`.
- Ensure Chrome/Chromedriver versions match. Consider `webdriver-manager` or document driver setup.
- Logs go to `./config/logs/<script>.log` and console.
- Git push uses your configured credentials for each repo’s `origin`. Set up SSH keys or HTTPS tokens once.

## Troubleshooting

- **Missing `./config/.env`** — first run creates it from `.env.example` and exits. Edit the file and re‑run.
- **Repo required** — steps {ensure_repo, update, sync_images, readme, sync_md, push} fail fast if `PEOPLE_IMAGES_DIR` is unset or invalid.
- **“Remote always wins” behavior** — If you *don’t* want hard reset + clean, remove `--mode hardreset --clean-ignored` in `_update_repos()` inside `orchestrator.py`.
- **No changes to commit** — the push step skips commit/push if the tree is clean.
- **Selenium stalls** — bump `SEL_PROC_TIMEOUT` or `SEL_MAX_WAIT_DL_SEC`. Make sure your Chrome profile is valid and signed into Adobe Express.
