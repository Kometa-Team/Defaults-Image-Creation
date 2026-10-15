"""Render the seven existing People styles with Pillow, without external tools."""

from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
import logging
import math
import os
import re
import shutil
import tempfile
import time
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat, __version__ as PILLOW_VERSION
from fontTools import __version__ as FONTTOOLS_VERSION
from fontTools.ttLib import TTLibError
from poster_fonts import FontMetrics

from people_workspaces import atomic_json, reject_links

SCRIPT_DIR = Path(__file__).resolve().parent
SIZE = (2000, 3000)
STYLES = ("original", "bw", "diiivoy", "diiivoycolor", "rainier", "signature", "transparent")
ARTWORK = ("@zbase-People.jpg", "@zbase-People-Clear2.png", "@zbase-Signature.png", "@zbase-People-Clear3.png")
FONTS = ("Comfortaa-Medium.ttf", "Fuggles-Regular.ttf", "Jost-260.ttf", "Montserrat-SemiBold.ttf")
DIIIVOY_POINT_SIZE = 190
LOG = logging.getLogger("people.poster")


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def resource_dirs():
    return (Path(os.getenv("POSTER_ASSET_DIR") or SCRIPT_DIR / "assets" / "people"),
            Path(os.getenv("POSTER_FONT_DIR") or SCRIPT_DIR / "fonts"))


def renderer_fingerprint():
    assets, fonts = resource_dirs()
    files = [Path(__file__), SCRIPT_DIR / "poster_fonts.py", *(assets / name for name in ARTWORK), *(fonts / name for name in FONTS)]
    return {"engine": "python", "pillow": PILLOW_VERSION, "fonttools": FONTTOOLS_VERSION,
            "files": {str(p.resolve()): digest(p) if p.is_file() else "missing" for p in files}}


def label_name(name: str) -> str:
    name = re.sub(r"\(\d+\)$", "", name.strip()).strip()
    return re.sub(r"\d+$", "", name).strip()


def output_path(root: Path, style: str, name: str, suffix=None):
    if not name or name in {".", ".."} or any(c in name for c in '/\\:\x00') or any(ord(c) < 32 for c in name):
        raise ValueError("Unsafe or empty person filename")
    initial = name[0].upper()
    return root / style / initial / "Images" / (name + (suffix or (".png" if style == "transparent" else ".jpg")))


def normalize_cutout(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    if rgba.width != SIZE[0]:
        height = max(1, math.floor(rgba.height * SIZE[0] / rgba.width + 0.5))
        rgba = rgba.resize((SIZE[0], height), Image.Resampling.LANCZOS)
    if rgba.height > SIZE[1]:
        top = (rgba.height - SIZE[1]) // 2
        rgba = rgba.crop((0, top, SIZE[0], top + SIZE[1]))
    canvas = Image.new("RGBA", SIZE)
    canvas.alpha_composite(rgba, (0, (SIZE[1] - rgba.height) // 2))
    return canvas


def shifted_cutout(image: Image.Image) -> Image.Image:
    bounds = image.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("Cutout has no foreground")
    offset = max(0, 500 - bounds[1])
    canvas = Image.new("RGBA", SIZE)
    canvas.alpha_composite(image, (0, offset))
    return canvas


def gray(image: Image.Image) -> Image.Image:
    luminance = image.convert("RGB").convert("L", (0.212656, 0.715158, 0.072186, 0))
    if image.mode == "RGBA":
        result = luminance.convert("RGBA")
        result.putalpha(image.getchannel("A"))
        return result
    return luminance


class Renderer:
    def __init__(self):
        asset_dir, self.font_dir = resource_dirs()
        for path in [*(asset_dir / n for n in ARTWORK), *(self.font_dir / n for n in FONTS)]:
            if not path.is_file():
                raise ValueError(f"Required poster resource missing: {path}. Set POSTER_FONT_DIR/POSTER_ASSET_DIR or restore the repository assets.")
        self.art = {}
        for name in ARTWORK:
            with Image.open(asset_dir / name) as image:
                image.load()
                if image.size != SIZE:
                    raise ValueError(f"Poster artwork must be 2000x3000: {name}")
                self.art[name] = image.convert("RGBA")
        self.fonts = {}
        try:
            self.metrics = {name: FontMetrics(self.font_dir / name) for name in FONTS}
        except TTLibError as error:
            raise ValueError(f"Unreadable required font in {self.font_dir}: {error}") from error
        for name in FONTS:
            self.font(name, 20)

    def font(self, name, size):
        key = (name, size)
        if key not in self.fonts:
            self.fonts[key] = ImageFont.truetype(BytesIO(self.metrics[name].font_data), size, layout_engine=ImageFont.Layout.BASIC)
        return self.fonts[key]

    def width(self, text, font, size):
        return max((self.metrics[font].positions(line, size)[1] for line in text.splitlines()), default=0)

    def label(self, text, font_name, box, pointsize=None, align="center", vertical="center"):
        lines = text.splitlines() or [""]
        if not any(lines):
            raise ValueError("Person label is empty after filename normalization")

        def extent(size):
            font = self.font(font_name, size)
            # ImageMagick's fitted labels reserve the font underline position.
            return self.metrics[font_name].fitted_extent(text, size, font.font.height)

        size = pointsize
        if size is None:
            low, high = 1, 1600
            while low < high:
                mid = (low + high + 1) // 2
                w, h = extent(mid)
                if w <= box[0] and h <= box[1]:
                    low = mid
                else:
                    high = mid - 1
            size = max(1, low - 1)
        font = self.font(font_name, size)
        ascent, descent = font.getmetrics()
        layouts = [self.metrics[font_name].positions(line, size) for line in lines]
        widths = [layout[1] for layout in layouts]
        line_height = font.font.height
        height = line_height * len(lines)
        mask = Image.new("RGBA", (max(1, math.ceil(max(widths)) + size * 2), height + size * 2))
        draw = ImageDraw.Draw(mask)
        for index, line in enumerate(lines):
            x = (max(widths) - widths[index]) / 2 if align == "center" else 0
            for character, offset in layouts[index][0]:
                draw.text((size + x + offset, size + ascent + index * line_height), character, font=font, fill="white", anchor="ls")
        bounds = mask.getchannel("A").getbbox()
        if bounds is None:
            raise ValueError("Font produced no visible label")
        cropped = mask.crop(bounds)
        result = Image.new("RGBA", box)
        x = (box[0] - cropped.width) // 2 if align == "center" else 0
        y = box[1] - cropped.height if vertical == "south" else (box[1] - cropped.height) // 2
        result.alpha_composite(cropped, (x, y))
        return result

    def bw_label(self, title):
        font = FONTS[0]
        if self.width(title, font, 183) <= 1900:
            return title, 183
        words = title.split(" ")
        if 2 <= len(words) <= 4:
            title = words[0] + "\n" + " ".join(words[1:])
            return title, 183 if self.width(" ".join(words[1:]), font, 183) <= 1900 else None
        return title, None

    def rainier_label(self, title):
        # Match the reference's literal-space splitting and word-count cases.
        words = title.split(" ")
        if len(words) == 1:
            return title, 183 if self.width(words[0], FONTS[0], 183) <= 1600 else None
        if len(words) == 2:
            return "\n".join(words), 183 if self.width(words[1], FONTS[0], 183) <= 1600 else None
        if len(words) == 3:
            if "JR." in title:
                text = words[0] + "\n" + " ".join(words[1:])
                fitted = max(self.width(" ".join(words[1:]), FONTS[0], 183), self.width(words[0], FONTS[0], 183)) >= 1600
            else:
                text = " ".join(words[:2]) + "\n" + words[2]
                fitted = max(self.width(" ".join(words[:2]), FONTS[0], 183), self.width(words[2], FONTS[0], 183)) >= 1600
            return text, None if fitted else 183
        if len(words) == 4:
            return " ".join(words[:2]) + "\n" + " ".join(words[2:]), 183 if self.width(" ".join(words[1:]), FONTS[0], 183) <= 1600 else None
        return title, None

    def prepare_cutout(self, source: Image.Image):
        cutout = normalize_cutout(source)
        alpha = cutout.getchannel("A")
        if not alpha.getbbox() or alpha.getextrema()[0] == 255:
            raise ValueError("Expected a nonempty transparent cutout; run background removal first")
        warnings = []
        if ImageStat.Stat(alpha.crop((0, 0, SIZE[0], 1))).mean[0] / 255 > .06:
            warnings.append("headchop: top-row alpha mean exceeds 0.06")
        rgb = cutout.convert("RGB")
        if rgb.getchannel("R").tobytes() == rgb.getchannel("G").tobytes() == rgb.getchannel("B").tobytes():
            warnings.append("grayscale: use a color photograph or DDColor")
        return cutout, warnings

    def diiivoy_styles(self, cutout, shifted, title, styles):
        # Preserve the reference's gray intermediate for high-margin portraits,
        # even when only diiivoycolor is requested.
        gray_subject = gray(shifted) if "diiivoy" in styles or cutout.getchannel("A").getbbox()[1] >= 500 else None
        color_subject = gray_subject if cutout.getchannel("A").getbbox()[1] >= 500 else shifted
        outputs = {}
        for style in styles:
            subject = gray_subject if style == "diiivoy" else color_subject
            poster = Image.alpha_composite(Image.alpha_composite(self.art[ARTWORK[0]], subject), self.art[ARTWORK[3]])
            size = DIIIVOY_POINT_SIZE if self.width(title, FONTS[2], DIIIVOY_POINT_SIZE) <= 1900 else None
            poster.alpha_composite(self.label(title, FONTS[2], (1900, 580), size), (50, 80))
            outputs[style] = poster.convert("RGB")
        return outputs

    def render_styles(self, source: Image.Image, name: str, styles=("diiivoy", "diiivoycolor")):
        styles = tuple(styles)
        if not styles or len(set(styles)) != len(styles) or set(styles) - {"diiivoy", "diiivoycolor"}:
            raise ValueError("Selective rendering supports only diiivoy and diiivoycolor")
        cutout, warnings = self.prepare_cutout(source)
        shifted = shifted_cutout(cutout)
        return self.diiivoy_styles(cutout, shifted, label_name(name).upper(), styles), warnings

    def render(self, source: Image.Image, name: str):
        cutout, warnings = self.prepare_cutout(source)
        shifted = shifted_cutout(cutout)
        base = self.art[ARTWORK[0]]
        color = Image.alpha_composite(base, shifted)
        label = label_name(name)
        title = label.upper()
        bw_title, bw_size = self.bw_label(title)
        outputs = {"transparent": cutout}
        bw = gray(color).convert("RGBA")
        bw.alpha_composite(self.label(bw_title, FONTS[0], (1900, 500), bw_size), (50, 0))
        outputs["bw"] = bw.convert("L")
        signature = Image.alpha_composite(Image.alpha_composite(base, cutout), self.art[ARTWORK[2]])
        signature.alpha_composite(self.label(label, FONTS[1], (1900, 600), vertical="south"), (50, 2150))
        outputs["signature"] = signature.convert("RGB")
        # The reference reuses diiivoy's gray temporary when Push-Down makes
        # no new image. Preserve that high-margin portrait quirk for parity.
        later_subject = gray(shifted) if cutout.getchannel("A").getbbox()[1] >= 500 else shifted
        outputs.update(self.diiivoy_styles(cutout, shifted, title, ("diiivoy", "diiivoycolor")))
        rainier = Image.alpha_composite(Image.alpha_composite(base, later_subject), self.art[ARTWORK[1]])
        rain_title, rain_size = self.rainier_label(title)
        rainier.alpha_composite(self.label(rain_title, FONTS[0], (1600, 580), rain_size, align="west"), (200, 80))
        outputs["rainier"] = rainier.convert("RGB")
        return outputs, warnings


def original_source(root, name):
    suffixes = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
    for directory in (root / "original", root / "original" / name[0].upper() / "Images"):
        matches = [p for p in directory.iterdir() if p.is_file() and p.stem == name and p.suffix.lower() in suffixes] if directory.is_dir() else []
        if len(matches) > 1:
            raise ValueError(f"Multiple preserved photographs for {name}; preserve/review the archives and select one source")
        if matches:
            return matches[0]
    raise ValueError(f"Missing preserved original photograph for {name}; expected people_dirs/original/{name}.jpg or another supported native photo format")


def render_batch(config: Path, names=None):
    config = Path(config).absolute()
    reject_links(config)
    config = config.resolve()
    root = config / "people_dirs"
    renderer = Renderer()
    fingerprint = renderer_fingerprint()
    state_path = config / ".orch" / "poster-render.json"
    previous = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    sources = {}
    for directory in (root / "tmppeople", root / "Downloads"):
        if directory.is_dir():
            for path in sorted(directory.iterdir()):
                if path.is_file() and path.suffix.lower() == ".png" and not path.stem.endswith("_pushed"):
                    sources[path.stem] = path
    if names is not None:
        sources = {name: sources.get(name, output_path(root, "transparent", name)) for name in names}
    elif not sources and previous:
        sources = {name: output_path(root, "transparent", name) for name in previous}
    report = {"engine": "python", "processed": 0, "skipped": 0, "failed": 0, "images": [], "seconds": 0}
    started = time.perf_counter()
    if not sources:
        raise ValueError("No staged transparent PNGs found in people_dirs/Downloads or tmppeople")
    destinations = set()
    for name, source in sources.items():
        result = {"name": name, "source": str(source)}
        try:
            reject_links(source)
            clean = name.replace("_ccexpress", "")
            key = unicodedata.normalize("NFC", clean).casefold()
            if key in destinations:
                raise ValueError("Two source names map to the same normalized output filename")
            destinations.add(key)
            original = original_source(root, name)
            reject_links(original)
            native_hash = digest(original)
            source_hash = digest(source)
            old = previous.get(name, {})
            if (old.get("fingerprint") == fingerprint and old.get("original_hash") == native_hash
                    and source_hash in {old.get("source_hash"), old.get("transparent_hash")}
                    and all(Path(p).is_file() and digest(Path(p)) == sha for p, sha in old.get("outputs", {}).items())
                    and len(old.get("outputs", {})) == 7):
                report["skipped"] += 1
                result["status"] = "unchanged"
            else:
                with Image.open(source) as image:
                    if image.format != "PNG" or getattr(image, "n_frames", 1) != 1:
                        raise ValueError("Expected a single-frame PNG cutout")
                    image.load()
                    outputs, warnings = renderer.render(image, clean)
                scratch = root / "tmppeople"
                scratch.mkdir(parents=True, exist_ok=True)
                reject_links(scratch)
                with tempfile.TemporaryDirectory(prefix=".poster-", dir=scratch) as temp:
                    pending = []
                    for style, image in outputs.items():
                        filename = name if style == "transparent" else clean
                        target = output_path(root, style, filename)
                        reject_links(target)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        staged = Path(temp) / (style + target.suffix)
                        if style == "transparent":
                            image.save(staged, "PNG")
                        else:
                            image.save(staged, "JPEG", quality=100, subsampling=0)
                        pending.append((style, staged, target))
                    original_target = output_path(root, "original", name, original.suffix.lower())
                    reject_links(original_target)
                    original_target.parent.mkdir(parents=True, exist_ok=True)
                    staged = Path(temp) / ("original" + original.suffix.lower())
                    shutil.copyfile(original, staged)
                    pending.append(("original", staged, original_target))
                    from sync_people_images import image_quality_findings
                    for style, staged, _ in pending:
                        blocking, notes = image_quality_findings(style, staged, allow_native_original=style == "original", allow_fixable_dimensions=style == "original")
                        with Image.open(staged) as check:
                            check.load()
                            if style == "transparent" and (check.mode != "RGBA" or check.format != "PNG"):
                                blocking.append("Transparent output must be RGBA PNG")
                            if style not in {"transparent", "original"} and check.format != "JPEG":
                                blocking.append("Expected JPEG output")
                        if blocking:
                            raise ValueError(f"{style}: {'; '.join(blocking)}")
                        warnings.extend(notes)
                    for _, staged, target in pending:
                        staged.replace(target)
                    hashes = {str(target): digest(target) for _, _, target in pending}
                previous[name] = {"fingerprint": fingerprint, "source_hash": source_hash,
                                  "original_hash": native_hash, "outputs": hashes,
                                  "transparent_hash": digest(output_path(root, "transparent", name))}
                atomic_json(state_path, previous)
                if original != original_target:
                    original.unlink()
                report["processed"] += 1
                result.update(status="rendered", warnings=sorted(set(warnings)))
                for warning in result["warnings"]:
                    LOG.warning("%s: %s", name, warning)
            if source.parent in {root / "Downloads", root / "tmppeople"}:
                source.unlink()
            LOG.info("%s: %s", name, result["status"])
        except (OSError, ValueError) as error:
            report["failed"] += 1
            result.update(status="failed", error=str(error))
            LOG.error("%s: %s", name, error)
        report["images"].append(result)
    report["seconds"] = round(time.perf_counter() - started, 3)
    atomic_json(config / "logs" / "create_people_poster.json", report)
    return report


def render_recovery_candidate(workspace, people_root, name, cutout, photograph):
    """Render one alternate in isolation; preserve the real archive until acceptance."""
    workspace = Path(workspace)
    root = workspace / "people_dirs"
    for directory in (root / "Downloads", root / "original"):
        directory.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cutout, root / "Downloads" / (name + ".png"))
    shutil.copy2(photograph, root / "original" / (name + ".jpg"))
    report = render_batch(workspace, [name])
    if report["failed"]:
        raise ValueError("Pillow recovery rendering failed: " + str(report["images"]))
    from remove_bg_birefnet import atomic_copy
    for style in STYLES:
        if style != "original":
            source = output_path(root, style, name)
            target = output_path(Path(people_root), style, name)
            reject_links(target)
            atomic_copy(source, target)
    return report


def main(argv=None):
    from dotenv import load_dotenv
    load_dotenv(SCRIPT_DIR / "config" / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(os.getenv("PEOPLE_CONFIG_DIR") or SCRIPT_DIR / "config"))
    parser.add_argument("--names", nargs="+", help="Render only named staged/retained cutouts")
    args = parser.parse_args(argv)
    logs = args.config / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    handlers = [logging.StreamHandler(), logging.FileHandler(logs / "create_people_poster.log", mode="w", encoding="utf-8")]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=handlers, force=True)
    try:
        report = render_batch(args.config, args.names)
        LOG.info("Files processed: %s; skipped: %s; failed: %s; seconds: %s", report["processed"], report["skipped"], report["failed"], report["seconds"])
        return 1 if report["failed"] else 0
    except (OSError, ValueError) as error:
        LOG.error("%s", error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
