# create_people_posters — Quick Start & Script Guide

End-to-end helpers for building consistent 2000×3000 “people poster” assets from your transparent PNGs and TMDB data, with a couple of utilities for keeping your **Kometa‑People‑Images** repo tidy and in sync.

## What’s inside

- **Cross‑platform Python scripts** (Windows/macOS/Linux)
- **Runners** for Windows (`runit_improved.cmd`) and POSIX (`runit.sh`)
- Optional **PowerShell** workflow (`create_people_poster.ps1`, requires PowerShell 7+)
- A small set of utilities to replace Windows‑only tooling (e.g., `robocopy`)

---

## Quick Start

1. **Clone or download** this repo.
2. **Copy** `.env.example` to `./config/.env` and fill in at least:
   ```env
   TMDB_KEY=<your TMDB v3 key>
   ```
   All scripts that use dotenv load from `./config/.env` (next to the scripts).
3. **Pick your runner**:
   - **Windows (CMD):**
     ```bat
     runit_improved.cmd "C:\path\to\your\Downloads"
     ```
   - **macOS / Linux (bash):**
     ```bash
     chmod +x runit.sh
     ./runit.sh "$HOME/Downloads"
     ```
   These runners will:
   - Create a venv (`./venv` on Windows, `./.venv` on bash)
   - Install `requirements.txt`
   - Ensure `./config/.env` exists (creates and stops if it’s missing)
   - Run the common pipeline (see below)
   - **Log output** to `./config/logs/`

### Common pipeline the runners execute

1. `name_checker_dir.py --input_directory <Downloads>` — scans your input folder for transparent PNGs and normalizes candidate names.
2. `get_missing_people.py --input_directory <Downloads>` — extracts missing names from your input set.
3. `tmdb_people.py` — queries TMDB for images (requires `TMDB_KEY`) and writes to `./config/posters`.

### Optional add-ons

- `ensure_people_repo.py` — verifies your **Kometa‑People‑Images** path and optional tools (e.g., `auto_readme.py`), optionally runs the README generator.
- `sync_md.py` — cross‑platform mirror for `*.md` files (replacement for `robocopy` usage).

---

## Environment (`./config/.env`)

```env
# REQUIRED
TMDB_KEY=

# OPTIONAL (sensible defaults)
PERSON_DEPTH=10
PEOPLE_LIST=./config/people_list.txt
POSTER_DIR=./config/posters

# Kometa People Images repo (used by utilities)
PEOPLE_IMAGES_DIR=./Kometa-People-Images
PEOPLE_BRANCH=master

# Adobe Express automation (used only by sel_remove_bg.py)
SEL_USER_DATA_DIR=./chrome-profile
SEL_PROFILE_DIR=Profile 1
SEL_SRC_DIR=./config/people_dirs/Downloads
SEL_ORIG_DIR=./config/people_dirs/original
SEL_DOWNLOAD_DIR=./config/sel_downloads
SEL_MAX_WAIT_READY_SEC=180
SEL_PROC_TIMEOUT=120
SEL_MAX_WAIT_DL_SEC=20
SEL_DL_BUTTON_TIMEOUT=12
SEL_RELOAD_EACH_FILE=true
SEL_EXPECT_WIDTH=2000
SEL_EXPECT_HEIGHT=3000
SEL_ENFORCE_SIZE=true
SEL_TOOL_URL=https://new.express.adobe.com/tools/remove-background
```

---

## Script catalog

### Pipeline scripts
- **`name_checker_dir.py`**  
  Scans an input folder (typically your `Downloads` of transparent PNGs), normalizes/prints candidate names.  
  **Args:** `--input_directory <path>`  
  **Output:** Console + logs in `./config/logs/`.

- **`get_missing_people.py`**  
  Further parsing of downloaded assets to identify missing names you may want to process.  
  **Args:** `--input_directory <path>`  
  **Output:** Console + logs.

- **`tmdb_people.py`**  
  Fetches person images from TMDB using `TMDB_KEY`. Saves to `POSTER_DIR` (defaults to `./config/posters`).  
  **Args:** (none required)  
  **Output:** Images in `./config/posters/` + logs.

### Quality & comparison
- **`compare_image_trees.py`**  
  Compares the presence of a given filename across a set of style folders (e.g., `bw`, `diiivoy`, `transparent`). Optionally checks image dimensions (defaults to 2000×3000).  
  **Config tip:** Replace any hard-coded paths with `PEOPLE_IMAGES_DIR` from `.env`:
  ```python
  base = Path(os.getenv("PEOPLE_IMAGES_DIR", str(SCRIPT_DIR / "Kometa-People-Images")))
  DIRS = [base / n for n in ("bw","diiivoy","diiivoycolor","rainier","original","signature","transparent")]
  ```

- **`image_check.py`**  
  Validates structures and basic image properties for consistency; logs to `./config/logs/`.

### Repo maintenance & sync
- **`update_people_repos.py`**  
  For multi-repo setups under `PEOPLE_IMAGES_DIR`, checks out/updates each style repo/branch. Requires `git`.

- **`sync_people_images.py`**  
  Cross-platform folder sync (robocopy‑like behavior using Python `shutil`) for styles from a source root to a destination root.

- **`sync_md.py`** *(new)*  
  Mirrors `*.md` files from one tree to another, recursively, preserving timestamps and skipping older sources (like `robocopy /XO`).  
  **Example:**  
  ```bash
  python sync_md.py --src "$PEOPLE_IMAGES_DIR/transparent" --dst "./people/transparent"
  ```

- **`ensure_people_repo.py`** *(new)*  
  Verifies you have the **Kometa‑People‑Images** repo. Checks for common subfolders and the optional `auto_readme.py`.  
  **Examples:**  
  ```bash
  python ensure_people_repo.py
  python ensure_people_repo.py --repo-root "/path/to/Kometa-People-Images" --run-auto-readme
  ```

### PowerShell workflow
- **`create_people_poster.ps1`**  
  Generates multiple poster styles (bw, diiivoy, diiivoycolor, rainier, signature) at 2000×3000, plus copies original/transparent for future use.  
  **Cross‑platform:** Run with **PowerShell 7+** (`pwsh`). Prefer `Join-Path` over manual `\` joins.

### Selenium automation (optional)
- **`sel_remove_bg.py`**  
  Automates Adobe Express “Remove Background” for batches. Uses your Chrome profile (`SEL_USER_DATA_DIR` + `SEL_PROFILE_DIR`) to keep you signed in; enforces image size; downloads transparent PNGs.

---

## Logs & outputs

- Logs are written under `./config/logs/` with the script’s name (and timestamps for runners).
- CSV outputs (e.g., from `compare_image_trees.py`) go into `./config/`.

---

## Cross‑platform notes

- Prefer running the **bash** or **CMD** runner for the common pipeline.  
- For a single script invocation across OSes, consider **PowerShell 7** or add a Python `orchestrator.py` that wraps the steps.
- Paths are built with `pathlib` in Python and `Join-Path` in PowerShell.

---

## Troubleshooting

- `ModuleNotFoundError`: re-run the runner to ensure `venv` + `requirements.txt` are installed.
- `TMDB_KEY missing`: edit `./config/.env` and add your key.
- Repo checks failing: set `PEOPLE_IMAGES_DIR` in `./config/.env` and ensure the path exists.

---

## Contributing

PRs welcome! Please keep paths OS-neutral and avoid hard-coded drive letters. When adding new scripts, ensure they read from `./config/.env` and write logs to `./config/logs/`.