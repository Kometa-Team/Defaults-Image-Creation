"""Explicit composition geometry; future styles define their own constraints."""
from dataclasses import dataclass

# The historical contract pins the whole module for its white-wash transform.
# This exact successor retains the legacy path; bounded layout is separately
# selected and fingerprinted. No unknown implementation/encoding is admitted.
LEGACY_RENDERER_SOURCE = 'ff748c9c8422a46f662f36a094a3ef523d2f9c4c23d622729f18c1f1894e0717'
BOUNDED_RENDERER_SOURCE = '279c955e5ccd90ab0be7fdf199bb5876c888f42d7bb93aa47f1cf930e920ff1a'


def compatible_renderer_source(observed, recorded):
    return observed == recorded or (recorded == LEGACY_RENDERER_SOURCE
                                    and observed == BOUNDED_RENDERER_SOURCE)


@dataclass(frozen=True)
class PosterStyle:
    id: str
    canvas: tuple[int, int]
    logo_box: tuple[int, int, int, int]
    caption_box: tuple[int, int, int, int]
    minimum_vertical_gap: int
    logo_vertical_alignment: str
    caption_measurement: tuple[int, int]
    caption_offset: int
    caption_font_size: int


# Preserve the existing 2000x3000 canvas, logo center (1000,1300), caption
# center (1000,1950), 1900px text width and 154pt caption. Reserve 200px for
# that unchanged single-line caption and 100px above it. The symmetric logo
# box around its original center therefore has height 900px and width 1600px.
_CANVAS = (2000, 3000)
_CAPTION_Y = _CANVAS[1]//2+450
_LOGO_Y = _CANVAS[1]//2-200
_CAPTION_TOP = _CAPTION_Y-100
_LOGO_BOTTOM = _CAPTION_TOP-100
PLAYLIST = PosterStyle('playlist-contained-v1', _CANVAS,
    (200, 2*_LOGO_Y-_LOGO_BOTTOM, 1800, _LOGO_BOTTOM),
    (50, _CAPTION_TOP, 1950, _CAPTION_Y+100), 100, 'center',
    (1900, 1000), 450, 154)


def get_style(name):
    if name == PLAYLIST.id:
        return PLAYLIST
    raise ValueError('Unknown poster composition style: '+str(name))
