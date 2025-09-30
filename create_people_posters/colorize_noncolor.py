#!/usr/bin/env python3
"""
colorize_noncolor.py — Colorize non-color images placed in "other" and output to "color".

- Vendors DeOldify source (if missing) into:   ./config/vendor/deoldify
- Forces CPU (no CUDA needed).
- Auto-downloads the ColorizeArtistic weights into: ./config/models/deoldify
- Reads from:  ./config/Downloads/other
- Writes to:   ./config/Downloads/color
- Keeps original filenames (NO suffix), outputs JPG.

Requires (in a dedicated venv, e.g. Python 3.10):
  pip install --extra-index-url https://download.pytorch.org/whl/cpu "torch==1.13.1+cpu" "torchvision==0.14.1+cpu"
  pip install fastai==1.0.61 pillow opencv-python-headless requests

Env (optional):
  COLORIZE_INPUT_OTHER   = ./config/Downloads/other
  COLORIZE_OUTPUT_COLOR  = ./config/Downloads/color
  COLORIZE_MODELS_DIR    = ./config/models/deoldify
  COLORIZE_VENDOR_DIR    = ./config/vendor
"""

import os, sys, io, zipfile, shutil, logging, time, urllib.request
from logging import FileHandler, StreamHandler
from pathlib import Path
from typing import Optional

# ---------- paths + logging ----------
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
VENDOR_DIR = Path(os.getenv("COLORIZE_VENDOR_DIR", CONFIG_DIR / "vendor"))
MODELS_DIR = Path(os.getenv("COLORIZE_MODELS_DIR", CONFIG_DIR / "models" / "deoldify"))
IN_OTHER = Path(os.getenv("COLORIZE_INPUT_OTHER", CONFIG_DIR / "Downloads" / "other"))
OUT_COLOR = Path(os.getenv("COLORIZE_OUTPUT_COLOR", CONFIG_DIR / "Downloads" / "color"))

for d in (CONFIG_DIR, LOGS_DIR, VENDOR_DIR, MODELS_DIR, OUT_COLOR):
    d.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOGS_DIR / "colorize_noncolor.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[FileHandler(LOG_FILE, encoding="utf-8", mode="w"), StreamHandler(sys.stdout)],
    force=True,
)
log = logging.getLogger("colorize")


# ---------- tiny http helpers ----------
def http_get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def http_get_to_file(url: str, dst: Path, timeout: int = 300) -> None:
    data = http_get(url, timeout=timeout)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("wb") as f:
        f.write(data)


# ---------- vendor DeOldify ----------
def ensure_deoldify_on_path() -> None:
    """
    Ensures we can `import deoldify` by:
    - downloading DeOldify zip (master/main) if missing
    - extracting ONLY the 'deoldify' package under ./config/vendor/deoldify
    - adding ./config/vendor (the PARENT) to sys.path
    """
    # if it imports already, nothing to do
    try:
        import deoldify  # noqa: F401
        return
    except Exception:
        pass

    # make sure parent of the package is on sys.path (this is the fix)
    parent = VENDOR_DIR
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))

    # try import again in case user already placed it there
    try:
        import deoldify  # noqa: F401
        return
    except Exception:
        pass

    # fetch + extract
    urls = [
        # master first (most repos still default to master)
        "https://codeload.github.com/jantic/DeOldify/zip/refs/heads/master",
        # fallback to main if the default changed
        "https://codeload.github.com/jantic/DeOldify/zip/refs/heads/main",
    ]
    ok = False
    for u in urls:
        try:
            log.info("DeOldify not found — downloading source ZIP …")
            data = http_get(u, timeout=120)
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                # find top folder (DeOldify-<hash>/) and its inner "deoldify/" package
                top = None
                for n in zf.namelist():
                    if n.endswith("/") and n.lower().startswith("deoldify-") and n.count("/") == 1:
                        top = n
                        break
                if not top:
                    continue
                pkg_prefix = top + "deoldify/"
                # clear any old vendor copy
                target_pkg = VENDOR_DIR / "deoldify"
                if target_pkg.exists():
                    shutil.rmtree(target_pkg, ignore_errors=True)
                # extract only package files
                extracted = 0
                for n in zf.namelist():
                    if n.startswith(pkg_prefix) and not n.endswith("/"):
                        rel = n[len(pkg_prefix):]
                        dst = target_pkg / rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(n) as src, open(dst, "wb") as out:
                            out.write(src.read())
                        extracted += 1
                log.info("DeOldify vendored into: %s (%d files)", target_pkg, extracted)
                ok = extracted > 0
                break
        except Exception as e:
            log.warning("Vendor attempt failed: %s", e)

    if not ok:
        raise RuntimeError("Unable to vendor DeOldify package.")

    # final import check
    try:
        import deoldify  # noqa: F401
    except Exception as e:
        raise RuntimeError(f"DeOldify import failed after vendoring: {e}")


# ---------- weights ----------
def ensure_weights() -> Path:
    """
    Downloads ColorizeArtistic weights if missing.
    Saves to: MODELS_DIR / ColorizeArtistic_gen.pth
    """
    dst = MODELS_DIR / "ColorizeArtistic_gen.pth"
    if dst.exists() and dst.stat().st_size > (10 * 1024 * 1024):
        return dst

    mirrors = [
        # Common stable mirror
        "https://data.deepai.org/deoldify/ColorizeArtistic_gen.pth",
        # HF mirror (query param ok)
        "https://huggingface.co/spaces/jantic/DeOldify/resolve/main/models/ColorizeArtistic_gen.pth?download=true",
    ]
    last_err: Optional[Exception] = None
    for u in mirrors:
        try:
            log.info("Downloading weights: %s", u)
            http_get_to_file(u, dst, timeout=600)
            if dst.exists() and dst.stat().st_size > (10 * 1024 * 1024):
                return dst
        except Exception as e:
            last_err = e
            log.warning("Weights attempt failed: %s", e)

    raise RuntimeError(f"Failed to fetch ColorizeArtistic weights: {last_err}")


# ---------- colorize one ----------
def colorize_one(src: Path, dst: Path, render_factor: int = 35) -> bool:
    """
    Returns True on success.
    """
    # Make sure deoldify can import (vendor + sys.path fix)
    ensure_deoldify_on_path()

    # Import stack (FastAI v1 + DeOldify)
    try:
        from deoldify import device
        from deoldify.device_id import DeviceId
        from deoldify.visualize import get_image_colorizer
    except Exception as e:
        log.error("DeOldify import failed: %s", e)
        log.error("If fastai/torch are missing, install them in this env.")
        log.error(
            'Example:\n  pip install --extra-index-url https://download.pytorch.org/whl/cpu "torch==1.13.1+cpu" "torchvision==0.14.1+cpu"\n  pip install fastai==1.0.61 pillow opencv-python-headless')
        return False

    # Force CPU
    try:
        device.set(DeviceId.CPU)
    except Exception:
        pass

    # Ensure weights, and ensure cwd contains a "models" dir DeOldify expects
    weights = ensure_weights()
    models_cwd = MODELS_DIR.parent  # ./config/models
    models_cwd.mkdir(parents=True, exist_ok=True)
    # DeOldify looks for ./models/ColorizeArtistic_gen.pth by default
    link_target = models_cwd / "models" / "ColorizeArtistic_gen.pth"
    link_target.parent.mkdir(parents=True, exist_ok=True)
    if not link_target.exists():
        try:
            # hard copy (works everywhere, avoids symlink perms)
            shutil.copy2(weights, link_target)
        except Exception:
            pass

    # Some DeOldify utilities resolve relative to CWD; run from CONFIG_DIR to be safe
    cwd_save = Path.cwd()
    try:
        os.chdir(CONFIG_DIR)
        colorizer = get_image_colorizer(artistic=True)
        # get PIL image without plotting
        result = colorizer.get_transformed_image(
            path=str(src),
            render_factor=render_factor,
            watermarked=False
        )
        # Save as high-quality JPG with original basename
        dst.parent.mkdir(parents=True, exist_ok=True)
        result.save(dst, format="JPEG", quality=95, optimize=True)
        return True
    except Exception as e:
        log.error("Colorize failed for %s: %s", src.name, e)
        return False
    finally:
        os.chdir(cwd_save)


# ---------- main ----------
def main() -> None:
    if not IN_OTHER.exists():
        log.info("Input folder does not exist: %s — nothing to do.", IN_OTHER)
        sys.exit(0)

    candidates = [p for p in IN_OTHER.iterdir() if
                  p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}]
    if not candidates:
        log.info("No candidate images found in %s — nothing to do.", IN_OTHER)
        sys.exit(0)

    processed = skipped = failed = 0
    for src in sorted(candidates):
        dst = OUT_COLOR / (src.stem + ".jpg")  # ALWAYS JPG, same basename
        if dst.exists():
            log.info("Skip (exists): %s", dst.name)
            skipped += 1
            continue
        ok = colorize_one(src, dst, render_factor=35)
        if ok:
            log.info("Colorized: %s -> %s", src.name, dst.name)
            processed += 1
        else:
            failed += 1

    log.info("Summary: processed=%d, skipped=%d, failed=%d", processed, skipped, failed)
    sys.exit(0)


if __name__ == "__main__":
    main()
