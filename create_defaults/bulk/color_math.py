"""CIEDE2000 equations (Sharma/Wu/Dalal 2005), independently reference-tested.

No author MATLAB/Excel software is copied. See tests/data/CIEDE2000_REFERENCE.md.
"""

from functools import lru_cache
from math import atan2, cos, degrees, exp, hypot, isfinite, radians, sin, sqrt

from .common import normalize_hex


def delta_e_2000(first, second):
    if len(first) != 3 or len(second) != 3 or not all(isfinite(v) for v in (*first, *second)):
        raise ValueError("CIELAB triples must contain finite values")
    l1, a1, b1 = first
    l2, a2, b2 = second
    cbar = (hypot(a1, b1) + hypot(a2, b2)) / 2
    g = (1 - sqrt(cbar ** 7 / (cbar ** 7 + 25 ** 7))) / 2
    ap1, ap2 = (1 + g) * a1, (1 + g) * a2
    cp1, cp2 = hypot(ap1, b1), hypot(ap2, b2)
    h1 = degrees(atan2(b1, ap1)) % 360 if cp1 else 0
    h2 = degrees(atan2(b2, ap2)) % 360 if cp2 else 0
    dl, dc = l2 - l1, cp2 - cp1
    difference = h2 - h1
    if not cp1 * cp2:
        dh = 0
        mean_h = h1 + h2
    else:
        dh = difference if abs(difference) <= 180 else difference - 360 if difference > 180 else difference + 360
        if abs(difference) <= 180:
            mean_h = (h1 + h2) / 2
        else:
            mean_h = (h1 + h2 + (360 if h1 + h2 < 360 else -360)) / 2
    dh = 2 * sqrt(cp1 * cp2) * sin(radians(dh / 2))
    mean_l, mean_c = (l1 + l2) / 2, (cp1 + cp2) / 2
    t = 1 - .17 * cos(radians(mean_h - 30)) + .24 * cos(radians(2 * mean_h)) + .32 * cos(radians(3 * mean_h + 6)) - .20 * cos(radians(4 * mean_h - 63))
    sl = 1 + .015 * (mean_l - 50) ** 2 / sqrt(20 + (mean_l - 50) ** 2)
    sc, sh = 1 + .045 * mean_c, 1 + .015 * mean_c * t
    rt = -2 * sqrt(mean_c ** 7 / (mean_c ** 7 + 25 ** 7)) * sin(radians(60 * exp(-((mean_h - 275) / 25) ** 2)))
    return sqrt(max(0, (dl / sl) ** 2 + (dc / sc) ** 2 + (dh / sh) ** 2 + rt * (dc / sc) * (dh / sh)))


def rgb(value):
    return tuple(bytes.fromhex(normalize_hex(value)[1:]))


def linear(channel):
    value = channel / 255
    return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4


@lru_cache(maxsize=4096)
def lab(value):
    r, g, b = map(linear, rgb(value))
    xyz = ((.4124564 * r + .3575761 * g + .1804375 * b) / .95047,
           .2126729 * r + .7151522 * g + .0721750 * b,
           (.0193339 * r + .1191920 * g + .9503041 * b) / 1.08883)
    x, y, z = (v ** (1 / 3) if v > (6 / 29) ** 3 else v / (3 * (6 / 29) ** 2) + 4 / 29 for v in xyz)
    return (116 * y - 16, 500 * (x - y), 200 * (y - z))


def contrast(first, second):
    def luminance(value):
        return sum(weight * linear(channel) for weight, channel in zip((.2126, .7152, .0722), rgb(value)))
    a, b = sorted((luminance(first), luminance(second)))
    return (b + .05) / (a + .05)
