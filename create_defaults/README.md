# create_defaults — Bulk Default Poster Generator (PowerShell)

This folder centers on **`create_default_posters.ps1`**, a bulk generator that produces many sets of *default* posters used across the People Images repos. It orchestrates individual creator functions and (when needed) calls the one‑off composer internally. You normally **do not** need to run the one‑off script yourself.

> Primary script: **`create_default_posters.ps1`**  
> Helper (invoked internally): `create_poster.ps1`

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

You can run any subset, or **`All`** to generate everything.

---

## Requirements

1. **PowerShell 7+** (`pwsh`)  
   - Windows: install from Microsoft Store or <https://aka.ms/powershell>  
   - macOS/Linux: `brew install --cask powershell` or your package manager
2. **ImageMagick** (`magick` CLI) — <https://imagemagick.org/script/download.php>  
   Verify with: `magick -version`
3. **Fonts** used by the default styles must be installed and visible to ImageMagick. If a font is missing, the generated poster may fall back or render oddly. (Common families used across this repo include Comfortaa, Bebas, Jura, etc.)
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

## Output

- Posters are written into category subfolders next to the script (see list above).  
- Naming and dimensions are consistent with the People Images repos. If you need a different size, adjust the size in the called composer or within the category function.

---

## Troubleshooting

- **`magick: command not found` / `'magick' is not recognized`** — Install ImageMagick and reopen your shell; confirm with `magick -version`.
- **Fonts missing or wrong glyphs** — Install the expected fonts *system‑wide* (so ImageMagick can see them). On Windows, right‑click `.ttf` → **Install for all users**.
- **Execution policy** — Run the `Set-ExecutionPolicy` command above (Windows).
- **Paths & permissions** — Ensure you have write permission to the output directories.
- **macOS/Linux** — Use `pwsh` (PowerShell 7+); ensure `magick` is on your PATH (e.g., `brew install imagemagick`).

---

## FAQ

**Do I need to run `create_poster.ps1` manually?**  
No. The bulk script calls the single‑poster composer internally where needed. Stick to aliases like `Genres`, `Network`, etc., or just `All`.

**Can I add my own default set?**  
Yes—clone an existing `Create*` function and tweak colors, gradients, logo, and text composition. Keep the output size consistent with the repo (commonly 2000×3000).

**Where do logs go?**  
Status is printed to the console. If you need persistent logs, redirect output:  
```powershell
pwsh -File ./create_default_posters.ps1 All *>&1 | Tee-Object -FilePath .\create_defaults.log
```
