# Defaults‑Image‑Creation

This repository brings together **two complementary toolsets** for building and maintaining visual assets used across your media libraries:

- **Cross‑Platform People Posters Pipeline (Python)** — an end‑to‑end workflow that discovers missing people, fetches images, removes backgrounds, updates your People‑Images repos with a *remote‑always‑wins* strategy, generates README grids, and optionally pushes changes. See **Orchestrator** below.
- **Create Defaults (PowerShell)** — a purpose‑built defaults generator that produces standardized “default” posters (genres, networks, countries, ratings, etc.) plus a one‑off poster composer. See **create_defaults** below.

---

## Quick Start

Choose the path that matches your task.

### A) Build / refresh People posters (Python orchestrator)

1. Python 3.10+ and `pip` installed
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. First‑run bootstraps `./config/.env` from the example:
   ```bash
   python orchestrator.py --all
   # then edit ./config/.env and set at least: TMDB_KEY=your_api_key
   ```
4. Typical runs:
   ```bash
   # Full publish flow (includes final push)
   python orchestrator.py --steps ensure_repo,update,sync_images,readme,sync_md,push      --repo-root "/path/to/Kometa-People-Images" --style transparent
   ```

**Highlights**
- Update step performs `git fetch` + `reset --hard` + `clean -fdx` so **remote always wins** (no local merge tangle).
- Optional final **push** step commits and pushes only if there are changes.
- QA helpers include `image_check.py` (single‑tree) and `compare_image_trees.py` (7‑tree matrix).

> For full details of steps, env vars, and QA utilities, see the orchestrator README in this repo.

### B) Generate default poster sets (PowerShell)

1. PowerShell 7+ (`pwsh`) and **ImageMagick** (`magick`) on PATH
2. Fonts used by the default styles installed system‑wide
3. From `create_defaults/`:
   ```powershell
   # Run everything
   pwsh -File ./create_defaults/create_default_posters.ps1 All

   # Or pick specific sets (run in order)
   pwsh -File ./create_defaults/create_default_posters.ps1 AudioLanguage Playlist Chart
   ```

**What it makes (examples)**
- Audio Language, Awards, Based, Charts, Content Rating, Country, Franchise, Genres, Network, Playlist, Resolution, Streaming, Studio, Seasonal, Separators, Subtitle Language, Universe, Video Format, Year, Overlays.
- One‑off composer `create_defaults/create_poster.ps1` builds a single 2000×3000 poster from base/gradient/logo/border/text layers.

> See `create_defaults/README.md` for requirements (ImageMagick, fonts, Windows execution policy), category details, and examples.

---

## Repository Layout

```
Defaults-Image-Creation/
├─ orchestrator.py                 # cross‑platform runner for the Python pipeline
├─ config/
│  ├─ .env.example                 # copied to ./config/.env on first run
│  └─ ...                          # pipeline config, logs, QA outputs
├─ create_defaults/
│  ├─ create_default_posters.ps1   # bulk defaults generator
│  ├─ create_poster.ps1            # single‑poster composer
│  └─ README.md                    # usage & requirements for PowerShell defaults
└─ README.md                       # (this file) overview & entry points
```

---

## Requirements (consolidated)

- **Python path:** Python 3.10+, `pip`, network access to TMDB, optional Selenium/Chrome if you use background removal.
- **PowerShell path:** PowerShell 7+, ImageMagick CLI (`magick`), required fonts (Comfortaa, Bebas, Jura, Limelight, Rye, etc.; Cairo for Arabic text).
- **Git:** for People‑Images updates (SSH key or HTTPS token configured for `origin`).

---

## Common Tasks

### Update repos then sync new posters
```bash
python orchestrator.py --steps ensure_repo,update,sync_images,readme,sync_md,push   --repo-root "/srv/Kometa-People-Images" --style transparent
```

### Validate generated images
```bash
# Single tree
python image_check.py --root "/srv/Kometa-People-Images/transparent" --exts png --required-size 2000x3000

# Seven-way matrix across style folders
python compare_image_trees.py --repo-root "/srv/Kometa-People-Images"
```

### Generate a few common default sets
```powershell
pwsh -File ./create_defaults/create_default_posters.ps1 Genres Resolution Studio
```

---

## Troubleshooting (quick)

- **'magick' not recognized** — Install ImageMagick and reopen your shell; verify with `magick -version`.
- **Fonts missing / wrong glyphs** — Install required fonts system‑wide so ImageMagick can find them.
- **Execution policy (Windows)** — `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force`
- **Nothing to push** — the push step skips commit when the working tree is clean.
- **Repo drift** — The update step resets to `origin/<branch>` each run; local changes are intentionally discarded before syncing.

---

## Credits

- PowerShell defaults scripts: bulk creators + one‑off composer
- Python pipeline: orchestrator + QA utilities (image checks & matrix)
