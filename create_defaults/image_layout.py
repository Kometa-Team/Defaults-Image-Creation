"""Pixel-bounded, alpha-aware image fitting shared by explicit poster styles."""
import math

from PIL import Image


def fit_visible_rgba(image, box, *, vertical_alignment='center'):
    """Uniformly contain visible source pixels, ignoring transparent padding.

    Return the fitted RGBA image, canvas position and reproducible measurements.
    The caller owns the style geometry; no filename/category heuristics apply.
    """
    left, top, right, bottom = box
    if (any(type(n) is not int for n in box) or left < 0 or top < 0
            or right <= left or bottom <= top):
        raise ValueError('Expected a positive integer image box')
    if vertical_alignment not in {'top', 'center', 'bottom'}:
        raise ValueError('Unknown vertical image alignment')
    source = image.convert('RGBA')
    bounds = source.getchannel('A').getbbox()
    if bounds is None:
        raise ValueError('A fitted logo must contain visible alpha pixels')
    visible = source.crop(bounds)
    scale = min((right-left)/visible.width, (bottom-top)/visible.height)
    width = min(right-left, max(1, math.floor(visible.width*scale+.5)))
    height = min(bottom-top, max(1, math.floor(visible.height*scale+.5)))
    fitted = visible.resize((width, height), Image.Resampling.LANCZOS)
    # Resampling can erase a faint outer pixel. Center the final visible pixels,
    # rather than reintroducing asymmetric transparent margins after resizing.
    final_bounds = fitted.getchannel('A').getbbox()
    if final_bounds is None:
        raise ValueError('Fitted logo has no visible alpha pixels')
    fitted = fitted.crop(final_bounds)
    x = left+(right-left-fitted.width)//2
    y = {'top': top, 'center': top+(bottom-top-fitted.height)//2,
         'bottom': bottom-fitted.height}[vertical_alignment]
    ink = (x, y, x+fitted.width, y+fitted.height)
    return fitted, (x, y), dict(source_alpha_bounds=list(bounds),
        fitted_size=list(fitted.size), visible_bounds=list(ink),
        box=list(box), scale=scale, vertical_alignment=vertical_alignment)
