# Poster fonts

Both renderers use local repository files, without system-font lookup or runtime
font downloads:

| File | Embedded identification | License notice |
| --- | --- | --- |
| Comfortaa-Medium.ttf | Comfortaa Medium; Copyright 2011 The Comfortaa Project Authors; reserved name Comfortaa | SIL OFL 1.1, see OFL-Comfortaa.txt |
| Fuggles-Regular.ttf | Fuggles Regular; Copyright 2021 The Fuggles Pro Project Authors | SIL OFL 1.1, see OFL-Fuggles.txt |
| Montserrat-SemiBold.ttf | Montserrat SemiBold; Copyright 2011 The Montserrat Project Authors | SIL OFL 1.1, see OFL-Montserrat.txt |
| Jost-260.ttf | Jost v3.710, upright, static weight 260; Copyright 2020 The Jost Project Authors | SIL OFL 1.1, see OFL-Jost.txt |

**Diiivoy and diiivoycolor use Jost weight 260 at a 190px preferred size**, with
the existing 1900x580 auto-fit for longer uppercase names. There is no artificial
bolding, horizontal stretching or extra tracking. The 61,084-byte font is the
exact static instance approved in the local font comparison, not a system-font
substitution. Other styles retain Comfortaa/Fuggles or have no generated text.
Montserrat is retained for the legacy font preflight, not style text rendering.

## Jost provenance

- Official source: [Google Fonts Jost](https://github.com/google/fonts/tree/main/ofl/jost).
- Variable TTF: [Jost[wght].ttf](https://raw.githubusercontent.com/google/fonts/main/ofl/jost/Jost%5Bwght%5D.ttf).
- License: [upstream OFL notice](https://github.com/google/fonts/blob/main/ofl/jost/OFL.txt),
  included here as `OFL-Jost.txt`; retain it and the embedded copyright notice
  when redistributing the font.
- Static instance generated with fontTools 4.67.0, pinning `wght=260` with
  `fontTools.varLib.instancer.instantiateVariableFont`. No variable font or
  fontTools instancing operation is required at runtime.
- Source SHA-256: `6343b70971000b04c5d401c96ae08ce371086135e999d5e1e1413039c0213076`.
- Bundled SHA-256: `564a838df86d075f9ab39e0d1f4cfe4ef90791388988dc8b5fc732f75d1ef8f5`.

The other OFL files are upstream notices from the corresponding Google Fonts
projects. Their current copyright years may differ from the older binaries'
embedded notices above; retain both when distributing those fonts.

FuturaTEELig is no longer bundled, embedded in the current PowerShell script,
required or selected by either renderer. Historical Git revisions and ignored
local comparison evidence are not rewritten by this change. Choosing Jost does
not grant rights to redistribute historical Futura font copies.

`POSTER_FONT_DIR` overrides the Python renderer's directory and requires the
four exact filenames above, including `Jost-260.ttf`. The PowerShell fallback
uses this repository directory. See [the renderer audit](../POSTER_RENDERER.md)
for layout coverage and the in-memory adapter, which does not save modified font
files during rendering.
