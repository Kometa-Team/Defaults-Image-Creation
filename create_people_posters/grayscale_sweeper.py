#!/usr/bin/env python3
"""Collect grayscale/near-grayscale images using explicit local maintenance.

Run ``python grayscale_sweeper.py --help`` for the five detection methods.
Imports and --help perform no directory creation, logging setup or processing.
RGB values, including hidden RGB under transparency, retain their original
meaning: alpha is neither composited nor used to discard pixels.
"""

import argparse
import hashlib
import logging
import math
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import unicodedata

import numpy as np
from PIL import Image, ImageChops
from alive_progress import alive_bar


CONFIG_DIR = Path(__file__).resolve().parent / "config"
DEFAULT_DEST = CONFIG_DIR / "Downloads" / "other"
DEFAULT_EXCLUDE = (DEFAULT_DEST, CONFIG_DIR / "Downloads" / "color")
METHODS = ("exact", "sat", "satq", "colorfulness", "auto")
LOG_NAME = ".grayscale_sweeper.log"


def _message(text, *, file=None):
    stream = sys.stdout if file is None else file
    encoding = getattr(stream, "encoding", None) or "utf8"
    print(str(text).encode(encoding, errors="backslashreplace").decode(encoding), file=stream)


def is_grayscale_exact(img: Image.Image) -> bool:
    """Strict RGB equality, retaining the original 1/L/LA support."""
    if img.mode in ("1", "L", "LA"):
        return True
    rgb = img.convert("RGB")
    r, g, b = rgb.split()
    return (ImageChops.difference(r, g).getbbox() is None
            and ImageChops.difference(g, b).getbbox() is None)


def is_low_saturation(img: Image.Image, s_thresh: int = 8) -> bool:
    """The original inclusive saturation threshold and 98% population rule."""
    saturation = img.convert("RGB").convert("HSV").getchannel("S")
    below = sum(saturation.histogram()[:max(0, min(255, s_thresh)) + 1])
    return below / max(1, saturation.width * saturation.height) >= 0.98


def is_near_grayscale_sat_quantile(img: Image.Image, sat_threshold: int = 35,
                                 q: float = 0.95) -> bool:
    """NumPy's linear HSV saturation quantile, inclusive of the threshold."""
    if not math.isfinite(q) or not 0 < q <= 1:
        raise ValueError("sat quantile q must be in (0, 1].")
    saturation = np.asarray(img.convert("RGB").convert("HSV"))[..., 1].astype(np.uint8)
    return bool(np.quantile(saturation, q, method="linear") <= sat_threshold)


def _colorfulness_score(img: Image.Image) -> float:
    """The existing Hasler-Suesstrunk calculation, unchanged."""
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    red, green, blue = arr[..., 0], arr[..., 1], arr[..., 2]
    rg = red - green
    yb = 0.5 * (red + green) - blue
    return float(np.hypot(rg.std(), yb.std())
                 + 0.3 * np.hypot(np.abs(rg).mean(), np.abs(yb).mean()))


def is_near_grayscale_colorfulness(img: Image.Image, cutoff: float = 12.0) -> bool:
    return _colorfulness_score(img) < cutoff


def classify(img, method, sat_threshold=8, sat_quantile=0.95, colorfulness_cutoff=12.0):
    if method == "exact":
        return is_grayscale_exact(img)
    if method == "sat":
        return is_low_saturation(img, sat_threshold)
    if method == "satq":
        return is_near_grayscale_sat_quantile(img, sat_threshold, sat_quantile)
    if method == "colorfulness":
        return is_near_grayscale_colorfulness(img, colorfulness_cutoff)
    if method == "auto":
        return (is_grayscale_exact(img)
                or is_near_grayscale_sat_quantile(img, max(sat_threshold, 35), sat_quantile)
                or is_near_grayscale_colorfulness(img, colorfulness_cutoff))
    raise ValueError("Unknown detection method: " + method)


def _no_links(path):
    """Check lexical ancestors before resolving, including Windows junctions."""
    path = Path(os.path.abspath(Path(path).expanduser()))
    for component in reversed((path, *path.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise OSError("Symlink/reparse paths are not supported: " + str(component))
    return path


def _signature(path):
    info = _no_links(path).stat()
    if not stat.S_ISREG(info.st_mode):
        raise OSError("Expected a regular source file: " + str(path))
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _inside(path, directory):
    return path == directory or directory in path.parents


def iter_images(root, exts, exclude_dirs, on_error=None):
    """Sorted traversal prunes outputs and never follows symlinks/junctions."""
    root = _no_links(root)
    excluded = tuple(Path(os.path.abspath(p)) for p in exclude_dirs)

    def report(error):
        if on_error is None:
            raise error
        on_error(error)

    for directory, dirs, files in os.walk(root, topdown=True, followlinks=False, onerror=report):
        directory = Path(directory)
        if any(_inside(directory, ex) for ex in excluded):
            dirs[:] = []
            continue
        try:
            _no_links(directory)
        except OSError as error:
            dirs[:] = []
            report(error)
            continue
        safe = []
        for name in sorted(dirs):
            child = directory / name
            if any(_inside(child, ex) for ex in excluded):
                continue
            try:
                _no_links(child)
                safe.append(name)
            except OSError as error:
                report(error)
        dirs[:] = safe
        for name in sorted(files):
            source = directory / name
            if source.suffix.lower().lstrip(".") in exts:
                try:
                    _signature(source)
                    yield source
                except OSError as error:
                    report(error)


def _name_key(name):
    return unicodedata.normalize("NFC", name).casefold()


def _digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class PlacementError(OSError):
    """A copy was published, but the move could not safely remove its source."""


class DestinationCollision(FileExistsError):
    """Exclusive destination creation found an existing/concurrent arrival."""


def place(source, target, source_signature, *, move=False, overwrite=False):
    """Stage complete bytes first; default publication uses exclusive creation."""
    _no_links(target.parent)
    _no_links(target)
    if target.exists() and os.path.samefile(source, target):
        raise OSError("Source and destination are the same file: " + str(source))
    if _signature(source) != source_signature:
        raise OSError("Source changed after classification: " + str(source))
    fd, temporary = tempfile.mkstemp(prefix=".grayscale-sweeper-", suffix=".tmp", dir=target.parent)
    os.close(fd)
    temporary = Path(temporary)
    published = False
    try:
        shutil.copy2(source, temporary, follow_symlinks=False)
        if _signature(source) != source_signature:
            raise OSError("Source changed during copying: " + str(source))
        _no_links(target)
        if target.exists() and os.path.samefile(source, target):
            raise OSError("Source and destination are the same file: " + str(source))
        if overwrite:
            os.replace(temporary, target)
        else:
            created = None
            try:
                # Unlike exists()+copy2(), exclusive creation cannot clobber
                # an existing file, dangling link or a concurrent arrival.
                try:
                    output = target.open("xb")
                except FileExistsError as error:
                    raise DestinationCollision(str(target)) from error
                with output:
                    created = target.stat()
                    with temporary.open("rb") as staged:
                        shutil.copyfileobj(staged, output)
                shutil.copystat(temporary, target, follow_symlinks=False)
            except Exception:
                if created is not None:
                    current = target.lstat()
                    if (current.st_dev, current.st_ino) == (created.st_dev, created.st_ino):
                        target.unlink()
                raise
        published = True
        if move:
            target_signature = _signature(target)
            if (_signature(source) != source_signature or _digest(source) != _digest(target)
                    or _signature(source) != source_signature or _signature(target) != target_signature):
                raise OSError("Source changed or copied bytes differ; source retained")
            source.unlink()
    except Exception as error:
        if published:
            raise PlacementError("Destination was written; source retained: " + str(error)) from error
        raise
    finally:
        if temporary.exists():
            # copy2 also copies read-only permissions. Only our private stage
            # may be made writable for Windows cleanup; never change source
            # or published destination permissions to make a move succeed.
            _no_links(temporary)
            temporary.chmod(temporary.stat().st_mode | stat.S_IWUSR)
        temporary.unlink(missing_ok=True)


def _saturation(value):
    number = int(value)
    if not 0 <= number <= 255:
        raise argparse.ArgumentTypeError("saturation threshold must be 0 through 255")
    return number


def _quantile(value):
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= 1:
        raise argparse.ArgumentTypeError("saturation quantile must be greater than 0 and at most 1")
    return number


def _cutoff(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("colorfulness cutoff must be finite and non-negative")
    return number


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", required=True, help="Root directory to scan recursively")
    parser.add_argument("--dest-other", default=str(DEFAULT_DEST), help="Destination directory")
    parser.add_argument("--move", action="store_true", help="Move successfully classified files instead of copying")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing exact-name destination files")
    parser.add_argument("--exts", default="jpg,jpeg,png,webp,bmp,tif,tiff", help="Comma-separated image extensions")
    parser.add_argument("--method", choices=METHODS, default="exact", help="Detection algorithm (default: exact)")
    parser.add_argument("--sat-threshold", type=_saturation, default=8, help="HSV saturation threshold, 0-255 (default: 8)")
    parser.add_argument("--sat-quantile", type=_quantile, default=0.95, help="HSV saturation quantile, 0 < q <= 1 (default: 0.95)")
    parser.add_argument("--colorfulness-cutoff", type=_cutoff, default=12.0, help="Non-negative colorfulness cutoff (default: 12)")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    extensions = {part.strip().lower().lstrip(".") for part in args.exts.split(",") if part.strip()}
    if not extensions or any(not re.fullmatch(r"[a-z0-9]+", ext) for ext in extensions):
        parser.error("--exts requires a non-empty comma-separated list of extensions")
    try:
        root, destination = _no_links(args.src), _no_links(args.dest_other)
        if not root.is_dir():
            raise OSError("Source must be an existing directory: " + str(root))
        if _inside(root, destination):
            raise OSError("Destination must not equal or contain the source directory")
        destination.mkdir(parents=True, exist_ok=True)
        _no_links(destination)
        log_file = _no_links(destination / LOG_NAME)
        if log_file.exists() and (not log_file.is_file() or log_file.stat().st_nlink != 1):
            raise OSError("Log must be a regular file with no hard-link aliases")
        handler = logging.FileHandler(log_file, mode="a", encoding="utf8")
    except OSError as error:
        _message("Error: " + str(error), file=sys.stderr)
        return 1
    logger = logging.Logger("grayscale_sweeper", level=logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    counts = {"scanned":0, "noncolor":0, "placed":0, "collisions":0, "errors":0}

    def scan_error(error):
        counts["errors"] += 1
        logger.error("Scan failed: %s", error)
        _message("Error: " + str(error), file=sys.stderr)

    try:
        logger.info("START src=%s dest=%s method=%s move=%s overwrite=%s sat=%s quantile=%s cutoff=%s",
                    root, destination, args.method, args.move, args.overwrite,
                    args.sat_threshold, args.sat_quantile, args.colorfulness_cutoff)
        files = list(iter_images(root, extensions, (*DEFAULT_EXCLUDE, destination), scan_error))
        _message(f"Scanning {len(files)} image(s) under {root}")
        names = {}
        for target in destination.iterdir():
            names.setdefault(_name_key(target.name), []).append(target.name)
        with alive_bar(len(files) or 1, title="Collect non-color", stats=False,
                       theme="classic", file=sys.stdout) as bar:
            for source in files:
                try:
                    signature = _signature(source)
                    with Image.open(source) as image:
                        image.load()
                        noncolor = classify(image, args.method, args.sat_threshold,
                                            args.sat_quantile, args.colorfulness_cutoff)
                    if not noncolor:
                        continue
                    counts["noncolor"] += 1
                    if _name_key(source.name) == _name_key(LOG_NAME):
                        raise OSError("Reserved sweeper log filename cannot be collected")
                    target = destination / source.name
                    _no_links(target)
                    if target.exists() and os.path.samefile(source, target):
                        raise OSError("Source and destination are the same file: " + str(source))
                    aliases = names.get(_name_key(source.name), [])
                    if aliases and (not args.overwrite or aliases != [source.name]):
                        counts["collisions"] += 1
                        logger.info("Skip destination collision: %s -> %s", source, aliases)
                        continue
                    try:
                        place(source, target, signature, move=args.move, overwrite=args.overwrite)
                    except DestinationCollision:
                        counts["collisions"] += 1
                        logger.info("Skip concurrent destination collision: %s", target)
                        continue
                    counts["placed"] += 1
                    names[_name_key(source.name)] = [source.name]
                    logger.info("%s: %s -> %s", "Moved" if args.move else "Copied", source, target)
                except Exception as error:
                    if isinstance(error, PlacementError):
                        counts["placed"] += 1
                    counts["errors"] += 1
                    logger.exception("Failed on %s", source)
                    _message(f"Error: {source}: {error}", file=sys.stderr)
                finally:
                    counts["scanned"] += 1
                    bar()
        logger.info("SUMMARY %s", counts)
        _message("\n=== SUMMARY ===")
        _message(f"Scanned: {counts['scanned']} | Non-color found: {counts['noncolor']} | "
              f"Placed: {counts['placed']} | Collisions: {counts['collisions']} | Errors: {counts['errors']}")
        _message(f"Details in log -> {log_file}")
        return int(counts["errors"] > 0)
    finally:
        handler.close()
        logger.removeHandler(handler)


if __name__ == "__main__":
    sys.exit(main())
