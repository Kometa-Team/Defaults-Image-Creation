# Defaults‑Image‑Creation

This repository brings together **two complementary toolsets** for building and maintaining visual assets used across your media libraries:

- **Cross‑Platform People Posters Pipeline (Python)** — an end‑to‑end workflow that discovers missing people, fetches images, removes backgrounds, updates your People‑Images repos with a *remote‑always‑wins* strategy, generates README grids, and optionally pushes changes. See **Orchestrator** below.
- **Create Defaults (Python)** — a purpose‑built defaults generator that produces standardized “default” posters (genres, networks, countries, ratings, etc.) plus a one‑off poster composer. See **create_defaults** below.

---

## Quick Start

Default-poster Python migration review: see the [team review guide](create_defaults/REVIEW_GUIDE.md)
and [current PowerShell/Python image samples](create_defaults/review/README.md).
Use the [Python operator workflow](create_defaults/PYTHON_OPERATIONS.md) for native generation, reconciliation, exact review and draft publication staging.

Choose the path that matches your task.

### A) Build / refresh People posters (Python orchestrator)

Clone-free publishing and temporary batch workspaces are the default: no downloads
of the seven image repositories, which can occupy hundreds of gigabytes.
Full local Git clones remain an explicit fallback. See [clone-free setup, retention and migration](create_people_posters/CLONE_FREE.md)
and the [People Posters guide](create_people_posters/README.md).

People poster rendering is native Python/Pillow. PowerShell and ImageMagick are
needed only for the optional legacy renderer, not the normal People workflow.

1. Python 3.13 recommended, with `pip` installed
2. Install dependencies:
   ```bash
   cd create_people_posters
   python -m pip install -r requirements.txt
   ```
3. First‑run bootstraps `./config/.env` from the example:
   ```bash
   python orchestrator.py
   # then edit ./config/.env and set TMDB_KEY=your_api_key
   gh auth login  # needs access to the seven destination repositories
   ```
4. Typical runs:
   ```bash
   # Clone-free batch from an explicit list (includes final publication)
   python orchestrator.py --new-batch --people-list config/people_list.txt

   # Clone-free preview: generate locally, but do not publish
   python orchestrator.py --new-batch --people-list config/people_list.txt --dry-run

   # Optional full-clone fallback, with existing local repositories
   python orchestrator.py --publish-mode local_git --workspace-mode persistent --repo-root "/path/to/Kometa-People-Images"
   ```

**Highlights**
- Default updates refresh GitHub metadata; publication uploads only changed images without cloning the libraries.
- Successful batches are retained for three days, then eligible for receipt-verified cleanup; unpublished images are retained.
- Full-clone fallback uses the existing `git fetch` + `reset --hard` + `clean -fdx` workflow.
- QA helpers include `image_check.py` (single‑tree) and `compare_image_trees.py` (7‑tree matrix).

> For full details of steps, env vars, and QA utilities, see the orchestrator README in this repo.

### B) Generate default posters and overlays (Python)

Use Python 3.13 and bundled, validated fonts. From the repository root:

```powershell
python -m pip install -r create_defaults/requirements-bulk.txt
python -m create_defaults.bulk.operations generate --category Based --report config/based-generation.json
python -m create_defaults.bulk.operations overlays --group aspect --report config/aspect-overlays.json
```

Repeat `--category` or use exact `--poster` identities and authored definition files.
`--category All` selects the complete English poster catalog; overlays have their own
explicit command. Adopt the verified migration cache with the documented `adopt`
command before a full unchanged run; `--cache-only` refuses unexpected rendering.

See [Python operations and rollback](create_defaults/PYTHON_OPERATIONS.md) for
single-poster, selected/category generation, previews, exact approvals, incremental
reuse, bounded/resumable Git staging and remote verification. Publication uses one
draft PR per logical approved set and always requires explicit approval. Merging
requires a separate decision.

The PowerShell/ImageMagick implementation is retained for legacy reference and
rollback. Python rendering does not invoke it.

---

## Repository Layout

```
Defaults-Image-Creation/
├─ orchestrator.py                 # cross‑platform runner for the Python pipeline
├─ config/
│  ├─ .env.example                 # copied to ./config/.env on first run
│  └─ ...                          # pipeline config, logs, QA outputs
├─ create_defaults/
│  ├─ bulk/operations.py          # native defaults generation and review
│  ├─ bulk/operator_publication.py # exact approval and resumable draft staging
│  ├─ create_default_posters.ps1   # legacy rollback reference
│  ├─ create_poster.ps1            # legacy rollback composer
│  └─ PYTHON_OPERATIONS.md         # defaults commands, approval and rollback
└─ README.md                       # (this file) overview & entry points
```

---

## Requirements (consolidated)

- **Default posters and overlays:** Python 3.13, `create_defaults/requirements-bulk.txt`, and the bundled validated fonts. Git/GitHub CLI are needed for explicit publication operations.
- **People Python path:** Python 3.11+ (3.13 recommended), `pip`, network access to TMDB, optional Selenium/Chrome if you use background removal.
- **Legacy PowerShell reference only:** PowerShell 7+, ImageMagick CLI (`magick`), required fonts (Comfortaa, Bebas Neue, Jura, Limelight, Rye, etc.; Cairo for Arabic text).
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
python image_check.py --input_directory "/srv/Kometa-People-Images/transparent" --style transparent

# Seven-way matrix across style folders, including dimension and quality issues
python compare_image_trees.py --repo-root "/srv/Kometa-People-Images"
```

Quality rules allow grayscale only for `bw` and `diiivoy`. `original`, `rainier`,
`signature`, `diiivoycolor`, and `transparent` must be color; `transparent` must
also contain alpha transparency. Transparent head-chop detection is top-edge
alpha contact; bottom/left/right are optional edge-contact diagnostics only.

### Generate a few common default sets
```powershell
python -m create_defaults.bulk.operations generate --category Genre --category Resolution --category Studio --report config/common-defaults.json
```

---

## Troubleshooting (quick)

- **Default font/source/case errors** — Use the Python preflight diagnostics and bundled font paths; resolve the exact source spelling before generation.
- **Legacy rollback only: 'magick' not recognized** — Install ImageMagick and reopen your shell; verify with `magick -version`.
- **Legacy rollback only: missing system fonts** — Install the historical fonts required by ImageMagick.
- **Legacy rollback only: execution policy (Windows)** — `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force`
- **Nothing to push** — the push step skips commit when the working tree is clean.
- **Repo drift** — The update step resets to `origin/<branch>` each run; local changes are intentionally discarded before syncing.

---

## Credits

- PowerShell defaults scripts: bulk creators + one‑off composer
- Python pipeline: orchestrator + QA utilities (image checks & matrix)
