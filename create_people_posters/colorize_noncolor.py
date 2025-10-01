#!/usr/bin/env python3
"""
colorize_noncolor.py — Colorize non-color images placed in "other" and output to "color".

- Vendors DeOldify source (if missing) into:   ./config/vendor/deoldify
- Forces CPU (no CUDA needed).
- Auto-downloads the ColorizeArtistic weights into: ./config/models/deoldify
- Reads from:  ./config/Downloads/other
- Writes to:   ./config/Downloads/color
- Keeps original filenames (NO suffix), outputs JPG.

Run in a dedicated venv (Python 3.10 recommended) with requirements-colorize.txt installed.
"""

import os, sys, io, zipfile, shutil, logging, warnings, time, urllib.request
from logging import FileHandler, StreamHandler
from pathlib import Path
from typing import Optional

# ---------- paths + logging ----------
# Put PyTorch model cache under ./config/models/torch-cache instead of user home
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"
os.environ.setdefault("TORCH_HOME", str((CONFIG_DIR / "models" / "torch-cache").resolve()))

# NumExpr: avoid the “defaulting to 8 threads” banner
os.environ.setdefault("NUMEXPR_VERBOSE", "0")
os.environ.setdefault("NUMEXPR_MAX_THREADS", str(os.cpu_count() or 8))
os.environ.setdefault("NUMEXPR_NUM_THREADS", str(os.cpu_count() or 8))

# Fastai dummy-dataset warnings
warnings.filterwarnings("ignore", category=UserWarning, module=r"fastai\.data_block")
warnings.filterwarnings("ignore", message=r"Your training set is empty\.")
warnings.filterwarnings("ignore", message=r"Your validation set is empty\.")

# Torchvision deprecation noise
warnings.filterwarnings("ignore", category=UserWarning, module=r"torchvision\.models\._utils")
warnings.filterwarnings("ignore", message=r"Using 'weights' as positional parameter")
warnings.filterwarnings("ignore", message=r"Arguments other than a weight enum or `None` for 'weights'")

# Quiet chatty libs
logging.getLogger("PIL").setLevel(logging.ERROR)
logging.getLogger("matplotlib").setLevel(logging.ERROR)
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
logging.getLogger("numexpr").setLevel(logging.WARNING)

LOGS_DIR = CONFIG_DIR / "logs"
VENDOR_DIR = Path(os.getenv("COLORIZE_VENDOR_DIR", CONFIG_DIR / "vendor"))
MODELS_DIR = Path(os.getenv("COLORIZE_MODELS_DIR", CONFIG_DIR / "models" / "deoldify"))
IN_OTHER = Path(os.getenv("COLORIZE_INPUT_OTHER", CONFIG_DIR / "Downloads" / "other"))
OUT_COLOR = Path(os.getenv("COLORIZE_OUTPUT_COLOR", CONFIG_DIR / "Downloads" / "color"))

for d in (CONFIG_DIR, LOGS_DIR, VENDOR_DIR, MODELS_DIR, OUT_COLOR):
    d.mkdir(parents=True, exist_ok=True)

# after creating LOGS_DIR, VENDOR_DIR, MODELS_DIR, OUT_COLOR
(CONFIG_DIR / "dummy").mkdir(parents=True, exist_ok=True)

LOG_FILE = LOGS_DIR / "colorize_noncolor.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[FileHandler(LOG_FILE, encoding="utf-8", mode="w"), StreamHandler(sys.stdout)],
    force=True,
)
log = logging.getLogger("colorize")


# ---------- sanity: numpy version (fastai 1.x expects NumPy < 2) ----------
def require_numpy_v1():
    try:
        import numpy as np
        ver = tuple(int(x) for x in np.__version__.split(".", 2)[:2])
        if ver >= (2, 0):
            log.error("NumPy %s detected — DeOldify (fastai 1.x) requires NumPy < 2.\n"
                      "Fix in this venv:\n  pip uninstall -y numpy\n  pip install 'numpy<2'",
                      np.__version__)
            sys.exit(2)
    except Exception:
        pass


require_numpy_v1()


# ---------- tiny http helpers ----------
def http_get(url: str, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def http_get_to_file(url: str, dst: Path, timeout: int = 600) -> None:
    data = http_get(url, timeout=timeout)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("wb") as f:
        f.write(data)


# ---------- vendor DeOldify ----------
def ensure_deoldify_on_path() -> None:
    """
    Ensures we can `import deoldify` by:
    - adding ./config/vendor to sys.path
    - downloading DeOldify zip (master/main) and extracting ONLY the 'deoldify' package under ./config/vendor/deoldify
    """
    if str(VENDOR_DIR) not in sys.path:
        sys.path.insert(0, str(VENDOR_DIR))

    try:
        import deoldify  # noqa: F401
        return
    except Exception:
        pass

    urls = [
        "https://codeload.github.com/jantic/DeOldify/zip/refs/heads/master",
        "https://codeload.github.com/jantic/DeOldify/zip/refs/heads/main",
    ]
    for u in urls:
        try:
            log.info("DeOldify not found — downloading source ZIP …")
            data = http_get(u, timeout=180)
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                top = None
                for n in zf.namelist():
                    if n.endswith("/") and n.lower().startswith("deoldify-") and n.count("/") == 1:
                        top = n
                        break
                if not top:
                    continue
                pkg_prefix = top + "deoldify/"
                target_pkg = VENDOR_DIR / "deoldify"
                if target_pkg.exists():
                    shutil.rmtree(target_pkg, ignore_errors=True)
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
                break
        except Exception as e:
            log.warning("Vendor attempt failed: %s", e)

    try:
        import deoldify  # noqa: F401
    except Exception as e:
        log.error("DeOldify import failed: %s", e)
        log.error("Ensure this venv has: fastai==1.0.61, torch 1.13.1+cpu, torchvision 0.14.1+cpu,\n"
                  "and python packages: yt-dlp, ffmpeg-python, imageio, imageio-ffmpeg.")
        sys.exit(2)


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
        "https://data.deepai.org/deoldify/ColorizeArtistic_gen.pth",
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

    log.error("Failed to fetch ColorizeArtistic weights: %s", last_err)
    sys.exit(2)


# ---------- colorize one ----------
def colorize_one(src: Path, dst: Path, render_factor: int = 35) -> bool:

    ensure_deoldify_on_path()

    # DeOldify imports (fastai v1)
    try:
        from deoldify import device
        from deoldify.device_id import DeviceId
        from deoldify.visualize import get_image_colorizer
        import ffmpeg  # just to ensure python-ffmpeg is present
        import yt_dlp  # required by visualize even for stills
    except Exception as e:
        log.error("DeOldify import failed: %s", e)
        log.error("Missing deps? Install inside this venv:\n"
                  "  pip install -r requirements-colorize.txt")
        return False

    # Force CPU
    try:
        device.set(DeviceId.CPU)
    except Exception:
        pass

    # Weights + expected ./models path for DeOldify
    weights = ensure_weights()

    # DeOldify expects ./models/ColorizeArtistic_gen.pth under the current working dir (CONFIG_DIR)
    models_root = CONFIG_DIR / "models"
    models_root.mkdir(parents=True, exist_ok=True)
    link_target = models_root / "ColorizeArtistic_gen.pth"

    if not link_target.exists():
        shutil.copy2(weights, link_target)

    # Some DeOldify utils assume CWD context
    cwd_save = Path.cwd()
    try:
        os.chdir(CONFIG_DIR)
        colorizer = get_image_colorizer(artistic=True)
        result = colorizer.get_transformed_image(
            path=str(src),
            render_factor=render_factor,
            watermarked=False
        )
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

    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
    candidates = [p for p in IN_OTHER.iterdir() if p.is_file() and p.suffix.lower() in exts]
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
