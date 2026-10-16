"""Phase-1 native Pillow composer. The legacy PowerShell workflow is unchanged."""

from __future__ import annotations

import argparse
import colorsys
from dataclasses import asdict, dataclass
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import warnings

from PIL import Image, ImageMath, UnidentifiedImageError

try:
    from .poster_text import load_layout, resolve_font
except ImportError:
    from poster_text import load_layout, resolve_font

ROOT = Path(__file__).resolve().parent
SIZE = (2000, 3000)
FADES = ("@none.png", "@center-out-fade.png", "@bottom-up-fade.png", "@top-down-fade.png", "@bottom-top-fade.png")
MAX_INPUT_PIXELS = 40_000_000
MAX_RESIZED_PIXELS = 24_000_000


@dataclass(frozen=True)
class PosterOptions:
    logo: str | Path | None = None
    logo_offset: int = 0
    logo_resize: int = 2000
    base_color: str | None = None
    gradient: int = 1
    text: str = ""
    text_offset: int = 0
    font: str | Path | None = None
    font_color: str = "#FFFFFF"
    font_size: int = 250
    out_name: str | None = None
    avg_color: bool = False
    avg_color_image: str | Path | None = None
    dom_color: bool = False
    dom_color_image: str | Path | None = None
    border: bool = False
    border_width: int = 15
    border_color: str | None = None
    white_wash: bool = False
    clean: bool = False


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def color(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError(f"{name} must be a six-digit #RRGGBB color, got {value!r}")
    return tuple(bytes.fromhex(value[1:]))


def hex_color(rgb):
    return "#" + bytes(rgb).hex().upper()


def integer(value, name, minimum, maximum):
    if isinstance(value, bool) or not re.fullmatch(r"[+-]?\d+", str(value)):
        raise ValueError(f"{name} must be an integer")
    value = int(value)
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def load_image(path):
    path = Path(path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {path}")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(path) as source:
            if source.width * source.height > MAX_INPUT_PIXELS or getattr(source, "n_frames", 1) != 1:
                raise ValueError(f"Expected a single-frame image with at most {MAX_INPUT_PIXELS:,} pixels: {path}")
            return source.convert("RGBA")


def image_source(path, asset_dir):
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        legacy_relative = Path(asset_dir) / candidate
        if legacy_relative.is_file():
            return legacy_relative
    return candidate


def average_color(image):
    """Legacy 1x1 resize followed by HSL brightness modulation to 120%."""
    alpha = image.getchannel("A").convert("F")
    weight = alpha.resize((1, 1), Image.Resampling.LANCZOS).getpixel((0, 0))
    if not weight:
        return (0, 0, 0)
    channels = []
    for name in "RGB":
        premultiplied = ImageMath.lambda_eval(lambda values: values["a"] * values["c"],
                                             a=alpha, c=image.getchannel(name).convert("F"))
        channels.append(premultiplied.resize((1, 1), Image.Resampling.LANCZOS).getpixel((0, 0)) / weight)
    red, green, blue = channels
    hue, lightness, saturation = colorsys.rgb_to_hls(red / 255, green / 255, blue / 255)
    return tuple(min(255, max(0, math.floor(v * 255 + .5)))
                 for v in colorsys.hls_to_rgb(hue, min(1, lightness * 1.2), saturation))


def jpeg_roundtrip(image, quality=100):
    with BytesIO() as buffer:
        image.convert("RGB").save(buffer, "JPEG", quality=quality, subsampling=0)
        buffer.seek(0)
        with Image.open(buffer) as result:
            return result.convert("RGB")


def resized_logo(image, width):
    height = max(1, math.floor(image.height * width / image.width + .5))
    if width * height > MAX_RESIZED_PIXELS:
        raise ValueError("Resized logo exceeds the bounded 24-megapixel workspace")
    # Pillow's premultiplied-alpha RGBA resize avoids halos at transparent edges.
    return image.resize((width, height), Image.Resampling.LANCZOS)


def composite_center(base, overlay, offset=0):
    result = base.convert("RGBA")
    result.alpha_composite(overlay, ((base.width - overlay.width) // 2,
                                     (base.height - overlay.height) // 2 + offset))
    return result.convert("RGB")


def render_poster(options=None, *, asset_dir=ROOT, font_dir=None, **parameters):
    """Return (RGB image, metadata). No external commands, network, or writes.

    Pass PosterOptions or legacy-named keyword parameters, not both. Runtime
    adapters may call this directly; create_poster adds safe JPEG file output.
    """
    if options is not None and parameters:
        raise ValueError("Pass PosterOptions or keyword parameters, not both")
    options = options or PosterOptions(**parameters)
    if not isinstance(options, PosterOptions):
        raise TypeError("options must be a PosterOptions instance")
    asset_dir = Path(asset_dir)
    font_dir = Path(font_dir) if font_dir else asset_dir / "fonts"
    # PowerShell's untyped numeric 0 compares equal to its empty-string default.
    width = integer(options.logo_resize or 2000, "logo_resize", 1, 2000)
    logo_offset = integer(options.logo_offset, "logo_offset", -1500, 1500)
    text_offset = integer(options.text_offset, "text_offset", -1500, 1500)
    gradient = integer(options.gradient, "gradient", -1_000_000, 1_000_000)
    gradient = gradient if 0 <= gradient <= 4 else 1
    font_size = integer(options.font_size or 250, "font_size", -1_000_000, 1_000_000)
    font_size = font_size if 10 <= font_size <= 500 else 250
    border_width = integer(options.border_width or 15, "border_width", -1_000_000, 1_000_000)
    border_width = border_width if 1 <= border_width <= 100 else 15
    font_color = color(options.font_color, "font_color")
    logo = load_image(image_source(options.logo, asset_dir)) if options.logo else Image.new("RGBA", (1, 1))
    selected_base = options.base_color
    if options.avg_color and not selected_base:
        sample = load_image(image_source(options.avg_color_image, asset_dir)) if options.avg_color_image else Image.new("RGBA", (1, 1))
        selected_base = hex_color(average_color(sample))
    if not selected_base:
        selected_base = f"#{secrets.randbelow(0xFFFFFF):06X}"
    base_color = color(selected_base, "base_color")
    selected_border = options.border_color
    # Both dominant-color parameters are reserved/no-op in the reference.
    selected_border = selected_border or "#FFFFFF"
    border_color = color(selected_border, "border_color")
    fade_path = asset_dir / "fades" / FADES[gradient]
    fade = load_image(fade_path)
    if fade.size != ((1, 1) if gradient == 0 else SIZE):
        raise ValueError(f"Unexpected gradient dimensions: {fade_path}: {fade.size}")
    # Legacy first writes base and flattened gradient at ImageMagick's default
    # JPEG quality (92), then writes each subsequent composite at quality 100.
    poster = jpeg_roundtrip(Image.new("RGB", SIZE, base_color), 92)
    poster = jpeg_roundtrip(composite_center(poster, fade), 92)
    if options.white_wash:
        alpha = logo.getchannel("A")
        logo = Image.new("RGBA", logo.size, "white")
        logo.putalpha(alpha)
    logo = resized_logo(logo, width)
    poster = composite_center(poster, logo, logo_offset)
    if options.text or options.border:
        poster = jpeg_roundtrip(poster)
    metadata = {"engine": "python", "base_color": hex_color(base_color), "border_color": hex_color(border_color),
                "logo_size": logo.size, "gradient": gradient, "font": None,
                "alpha": "Source alpha retained; premultiplied-alpha Lanczos resize, source-over compositing",
                "options": {k: str(v) if isinstance(v, Path) else v for k, v in asdict(options).items()}}
    if options.text:
        path = resolve_font(options.font, font_dir)
        layout = load_layout(str(path), path.stat().st_mtime_ns)
        caption, caption_metadata = layout.caption(options.text, font_size, font_color)
        poster = composite_center(poster, caption, text_offset)
        if options.border:
            poster = jpeg_roundtrip(poster)
        metadata.update(font={"path": str(path), "sha256": digest(path)}, caption=caption_metadata)
    if options.border:
        inner = poster.resize((2000 - 2 * border_width, 3000 - 2 * border_width), Image.Resampling.LANCZOS)
        inner = jpeg_roundtrip(inner)
        poster = Image.new("RGB", SIZE, border_color)
        poster.paste(inner, (border_width, border_width))
    return poster, metadata


def output_filename(options, base_color):
    selected = options.base_color or base_color
    stem = options.out_name or f"{Path(options.logo).stem if options.logo else 'transparent'}-{selected}"
    normalized = stem.replace("\\", "/")
    if normalized.startswith("//"):
        raise ValueError("out_name cannot be a network path")
    # Join-Path treats the bulk separator's single leading slash as a child
    # path. Keep those subfolders under output_dir, never as absolute paths.
    parts = normalized.lstrip("/").split("/")
    for part in parts:
        if not part or part in {".", ".."} or part.rstrip(". ") != part or re.search(r'[<>:"|?*\x00-\x1f]', part):
            raise ValueError("out_name must contain safe relative filename components without traversal")
        if part.upper().split(".")[0] in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
            raise ValueError("out_name is a reserved Windows filename")
    return "/".join(parts) + ".jpg"


def create_poster(options=None, *, output_path=None, output_dir=None, asset_dir=ROOT, font_dir=None, **parameters):
    """Render and save a new JPEG exclusively; never replace existing assets."""
    if options is not None and parameters:
        raise ValueError("Pass PosterOptions or keyword parameters, not both")
    options = options or PosterOptions(**parameters)
    if output_path is not None and output_dir is not None:
        raise ValueError("Use output_path or output_dir, not both")
    if output_path is not None:
        target = Path(output_path).expanduser().absolute()
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"Refusing to overwrite an existing file: {target}")
        if target.suffix.lower() not in {".jpg", ".jpeg"}:
            raise ValueError("Explicit output_path must have a .jpg or .jpeg extension")
    image, metadata = render_poster(options, asset_dir=asset_dir, font_dir=font_dir)
    if output_path is None:
        target = Path(output_dir or ROOT / "output") / output_filename(options, metadata["base_color"])
    target = target.absolute()
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Refusing to overwrite an existing file: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    # A private sibling workspace limits cleanup to files owned by this call.
    with tempfile.TemporaryDirectory(prefix=".poster-", dir=target.parent) as directory:
        staged = Path(directory) / "poster.jpg"
        image.save(staged, "JPEG", quality=100, subsampling=0)
        created = False
        try:
            with target.open("xb") as destination:
                created = True
                with staged.open("rb") as source:
                    import shutil
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
        except FileExistsError:
            raise
        except BaseException:
            if created:
                target.unlink(missing_ok=True)
            raise
    metadata.update(output_path=str(target), sha256=digest(target), size_bytes=target.stat().st_size)
    return metadata


def boolean(value):
    if isinstance(value, bool):
        return value
    if value.lower().lstrip("$") in {"true", "1", "yes"}:
        return True
    if value.lower().lstrip("$") in {"false", "0", "no"}:
        return False
    raise argparse.ArgumentTypeError("Expected true/false or 1/0")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name, field in PosterOptions.__dataclass_fields__.items():
        switches = list(dict.fromkeys(["--" + name.replace("_", "-"), "--" + name, "-" + name]))
        arguments = {"dest": name, "default": field.default}
        if name in {"avg_color", "dom_color", "border", "white_wash", "clean"}:
            arguments.update(type=boolean, nargs="?", const=True)
        elif name in {"logo_offset", "logo_resize", "gradient", "text_offset", "font_size", "border_width"}:
            arguments.update(type=int)
        parser.add_argument(*switches, **arguments)
    parser.add_argument("--output-path", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--asset-dir", type=Path, default=ROOT)
    parser.add_argument("--font-dir", type=Path)
    args = vars(parser.parse_args(argv))
    extra = {key: args.pop(key) for key in ("output_path", "output_dir", "asset_dir", "font_dir")}
    try:
        result = create_poster(PosterOptions(**args), **extra)
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (ValueError, TypeError, FileNotFoundError) as error:
        print(f"Invalid poster input: {error}", file=sys.stderr)
        return 2
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        print(f"Poster rendering failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
