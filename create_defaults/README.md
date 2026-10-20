# Default posters and overlays: Python operations

The supported English generation and publication workflow is Python 3.13.
See [operator commands, exact approval gates and rollback](PYTHON_OPERATIONS.md).

```powershell
python -m pip install -r create_defaults/requirements-bulk.txt
python -m create_defaults.bulk.operations generate --category Based --report config/based-generation.json
python -m create_defaults.bulk.operations overlays --group aspect --report config/aspect-overlays.json
```

Run from the repository root. Adopt verified existing migration caches before a
full unchanged run. Publication requires exact maintainer decisions and uses the
resumable draft-PR transport; generation never approves or publishes artwork.

The following PowerShell documentation is preserved as a legacy reproduction and
rollback reference. Those scripts are deprecated for normal English operations;
they remain present and are not invoked by the Python workflow.

---

## Legacy PowerShell reference

# create_defaults — Bulk Default Poster Generator (PowerShell)

This folder centers on **`create_default_posters.ps1`**, a bulk generator that produces many sets of *default* posters used across the Default Images repos. It orchestrates individual creator functions and (when needed) calls the one‑off composer internally. You normally **do not** run the helper yourself.

> Primary script: **`create_default_posters.ps1`**  
> Helper (invoked internally): `create_poster.ps1`

Native single-poster migration candidate: start with the [team review guide](REVIEW_GUIDE.md)
and [portable image comparisons](review/README.md). See [Python Composer Phase 1](PYTHON_COMPOSER.md)
for the callable Pillow API, parameter/font audit, and offline tests. PowerShell
remains the production reference; the Python renderer does not publish artwork.

---

## What it makes

The script includes creator functions for (names/aliases are case‑insensitive):

- **AudioLanguage** (`CreateAudioLanguage`)  
- **Awards** (`CreateAwards`)  
- **Based** (`CreateBased`)  
- **Charts** (`CreateChart`)  
- **ContentRating** (`CreateContentRating`)  
- **Country** (`CreateCountry`)  
- **Franchise** (`CreateFranchise`)  
- **Genres** (`CreateGenres`)  
- **Network** (`CreateNetwork`)  
- **Playlist** (`CreatePlaylist`)  
- **Resolution** (`CreateResolution`)  
- **Streaming** (`CreateStreaming`)  
- **Studio** (`CreateStudio`)  
- **Seasonal** (`CreateSeasonal`)  
- **Separators** (`CreateSeparators`)  
- **SubtitleLanguages** (`CreateSubtitleLanguages`)  
- **Universe** (`CreateUniverse`)  
- **VideoFormat** (`CreateVideoFormat`)  
- **Years** (`CreateYear`)  
- **Overlays** (`CreateOverlays`)  

Run any subset, or **`All`** to generate everything.

---

## Requirements

1. **PowerShell 7+** (`pwsh`)  
   - Windows: install from Microsoft Store or <https://aka.ms/powershell>  
   - macOS/Linux: `brew install --cask powershell` or your package manager
2. **ImageMagick** (`magick` CLI) — <https://imagemagick.org/script/download.php>  
   Verify with: `magick -version`
3. **Fonts** used by the default styles must be installed and visible to ImageMagick or resolved from the bundled files. Playlist posters use bundled OFL-licensed **Bebas Neue Regular v2.000**; see [replacement measurements and configuration](BEBAS_REPLACEMENT.md). The 2020s decade and 2020-2029 year posters use approved OFL-licensed **Plus Jakarta Sans Bold 2.071 at fixed 409 points**; see [Helvetica replacement](HELVETICA_REPLACEMENT.md). Other families include Comfortaa, Jura, Limelight, and Rye. For Arabic-capable text, use a multi-lingual font such as **Cairo-Regular**.
4. **Windows execution policy** (first run):  
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
   ```

---

## Usage

From inside this folder:

```powershell
# Run everything
pwsh -File ./create_default_posters.ps1 All

# Run specific generators (in order)
pwsh -File ./create_default_posters.ps1 AudioLanguage Playlist Chart

# More sets
pwsh -File ./create_default_posters.ps1 Genres Resolution Studio
pwsh -File ./create_default_posters.ps1 Country Network Streaming
pwsh -File ./create_default_posters.ps1 Awards ContentRating
```

### Notes
- Arguments are **aliases** for functions; you can also call the functions directly (e.g., `CreateGenres`).  
- The script validates `magick` and creates output folders on demand (e.g., `audio_language`, `award`, `chart`, `content_rating`, `country`, `franchise`, `genres`, `network`, `playlist`, `resolution`, `streaming`, `studio`, `seasonal`, `separators`, `subtitle_language`, `universe`, `video_format`, `year`, `overlays`).  
- If you only need one poster style for a new label, run the matching alias, not the helper script.

---

## Translation & Localization (built‑in)

The bulk script can **localize labels** (e.g., Genres, Networks, Countries) using YAML translation files:

- On startup it prompts for a **language code**. Supported set in the script:  
  `ar`, `en`, `da`, `de`, `es`, `fr`, `it`, `nb_NO`, `nl`, `pt-br`, `sv` (default: `en`).  
  If you press Enter, it uses the default.

- It will **download** the translation file to `@translations/<code>.yml` next to the script.  
  Source: `Kometa-Team/Translations` repo (defaults).

- Translation keys are read via:
  - `Read-Yaml` → loads the YAML as a global object
  - `Get-YamlPropertyValue -PropertyPath "<path>" -ConfigObject $global:ConfigObj`  
    with `-CaseSensitivity` options **`Exact` (default)**, **`Upper`**, or **`Lower`**.

- Some labels use templating like `<<something>>`; the helper `Set-TextBetweenDelimiters` fills these placeholders before rendering.

- Output folders also include a language stamp for defaults, e.g. `defaults-<code>`.

**Branch selection note:** There’s a `-BranchOption` parameter wired for `master|develop|nightly`, but the current script pins the translation URL to the `master` branch. If you want to switch branches, edit the line that sets `$GitHubRepository` to interpolate `$BranchOption` (and ensure the branch exists in the translations repo).

---

## Output

- Posters are written into category subfolders next to the script (see list above).  
- Naming and dimensions are consistent with the repos (commonly **2000×3000**). To change size, adjust in the per‑category function or the internal composer.

---

## Troubleshooting

- **`magick: command not found` / `'magick' is not recognized`** — Install ImageMagick and reopen your shell; confirm with `magick -version`.
- **Fonts missing or wrong glyphs** — Install the expected fonts *system‑wide* (so ImageMagick can see them). On Windows, right‑click `.ttf` → **Install for all users**.
- **Execution policy** — Run the `Set-ExecutionPolicy` command above (Windows).
- **Paths & permissions** — Ensure you have write permission to the output directories.
- **macOS/Linux** — Use `pwsh` (PowerShell 7+); ensure `magick` is on PATH (e.g., `brew install imagemagick`).

---

## FAQ

**Do I need to run `create_poster.ps1` manually?**  
No. The bulk script calls the single‑poster composer internally where needed. Stick to aliases like `Genres`, `Network`, etc., or just `All`.

**Can I add my own default set?**  
Yes—clone an existing `Create*` function and tweak colors, gradients, logo, and text composition. Keep the output size consistent (commonly 2000×3000).

**Where do logs go?**  
Status is printed to the console. If you need persistent logs, redirect output:  
```powershell
pwsh -File ./create_default_posters.ps1 All *>&1 | Tee-Object -FilePath .\create_defaults.log
```
