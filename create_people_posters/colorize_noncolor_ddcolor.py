#!/usr/bin/env python3
"""
colorize_noncolor_ddcolor.py - Colorize non-color images with DDColor.

- Vendors the official piddnad/DDColor source into ./config/vendor/DDColor when needed.
- Forces CPU by default.
- Downloads and caches Hugging Face DDColor weights under ./config/models/ddcolor.
- Reads from COLORIZE_INPUT_OTHER or ./config/Downloads/other.
- Writes JPGs to COLORIZE_OUTPUT_COLOR or ./config/Downloads/color.
- Keeps original basenames and validates output before removing source files.
"""

from __future__ import annotations

import gc
import importlib
import io
import json
import logging
import os
import shutil
import sys
import time
import urllib.request
import warnings
import zipfile
from logging import FileHandler, StreamHandler
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps, UnidentifiedImageError


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = Path(os.getenv("PEOPLE_CONFIG_DIR") or SCRIPT_DIR / "config")
LOGS_DIR = CONFIG_DIR / "logs"
VENDOR_DIR = Path(os.getenv("COLORIZE_VENDOR_DIR", CONFIG_DIR / "vendor"))
DDCOLOR_VENDOR_DIR = Path(os.getenv("COLORIZE_DDCOLOR_VENDOR_DIR", VENDOR_DIR / "DDColor"))
MODELS_DIR = Path(os.getenv("COLORIZE_DDCOLOR_MODELS_DIR", CONFIG_DIR / "models" / "ddcolor"))
IN_OTHER = Path(os.getenv("COLORIZE_INPUT_OTHER", CONFIG_DIR / "Downloads" / "other"))
OUT_COLOR = Path(os.getenv("COLORIZE_OUTPUT_COLOR", CONFIG_DIR / "Downloads" / "color"))
MODEL_NAME = os.getenv("COLORIZE_MODEL", "ddcolor_modelscope").strip() or "ddcolor_modelscope"
DEVICE_NAME = os.getenv("COLORIZE_DEVICE", "cpu").strip().lower() or "cpu"
INPUT_SIZE = int(os.getenv("COLORIZE_INPUT_SIZE", "512"))
JPEG_QUALITY = int(os.getenv("COLORIZE_JPEG_QUALITY", "95"))

os.environ.setdefault("HF_HOME", str((MODELS_DIR / "hf-home").resolve()))
os.environ.setdefault("TORCH_HOME", str((CONFIG_DIR / "models" / "torch-cache").resolve()))
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

for d in (CONFIG_DIR, LOGS_DIR, VENDOR_DIR, MODELS_DIR, OUT_COLOR):
    d.mkdir(parents=True, exist_ok=True)

warnings.filterwarnings("ignore", category=UserWarning, module=r"torchvision")
logging.getLogger("PIL").setLevel(logging.ERROR)

LOG_FILE = LOGS_DIR / "colorize_noncolor_ddcolor.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[FileHandler(LOG_FILE, encoding="utf-8", mode="w"), StreamHandler(sys.stdout)],
    force=True,
)
log = logging.getLogger("colorize")

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
MODEL_REPOS = {
    "ddcolor_paper": "piddnad/ddcolor_paper",
    "ddcolor_modelscope": "piddnad/ddcolor_modelscope",
    "ddcolor_artistic": "piddnad/ddcolor_artistic",
    "ddcolor_paper_tiny": "piddnad/ddcolor_paper_tiny",
}


def http_get(url: str, timeout: int = 180) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def ensure_ddcolor_on_path() -> None:
    """Ensure the official piddnad/DDColor package is importable."""
    if str(DDCOLOR_VENDOR_DIR) not in sys.path:
        sys.path.insert(0, str(DDCOLOR_VENDOR_DIR))
    if str(VENDOR_DIR) not in sys.path:
        sys.path.insert(0, str(VENDOR_DIR))

    try:
        import ddcolor  # noqa: F401
        return
    except ModuleNotFoundError as exc:
        if exc.name != "ddcolor":
            log.error("DDColor dependency import failed: %s", exc)
            log.error("Install deps with: pip install -r requirements-ddcolor.txt")
            sys.exit(2)
    except Exception as exc:
        log.error("DDColor import failed: %s", exc)
        sys.exit(2)

    urls = [
        "https://codeload.github.com/piddnad/DDColor/zip/refs/heads/master",
        "https://codeload.github.com/piddnad/DDColor/zip/refs/heads/main",
    ]
    last_err: Optional[Exception] = None
    for url in urls:
        try:
            log.info("DDColor not found - downloading official source ZIP ...")
            data = http_get(url, timeout=240)
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                top = next(
                    (
                        name
                        for name in zf.namelist()
                        if name.endswith("/") and name.lower().startswith("ddcolor-") and name.count("/") == 1
                    ),
                    None,
                )
                if not top:
                    continue
                tmp = DDCOLOR_VENDOR_DIR.with_name(DDCOLOR_VENDOR_DIR.name + ".tmp")
                if tmp.exists():
                    shutil.rmtree(tmp, ignore_errors=True)
                tmp.mkdir(parents=True, exist_ok=True)
                extracted = 0
                for name in zf.namelist():
                    if not name.startswith(top) or name.endswith("/"):
                        continue
                    rel = name[len(top):]
                    if not rel:
                        continue
                    dst = tmp / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as src, dst.open("wb") as out:
                        shutil.copyfileobj(src, out)
                    extracted += 1
                if DDCOLOR_VENDOR_DIR.exists():
                    shutil.rmtree(DDCOLOR_VENDOR_DIR, ignore_errors=True)
                tmp.replace(DDCOLOR_VENDOR_DIR)
                importlib.invalidate_caches()
                log.info("DDColor vendored into: %s (%d files)", DDCOLOR_VENDOR_DIR, extracted)
                break
        except Exception as exc:
            last_err = exc
            log.warning("DDColor vendor attempt failed: %s", exc)

    try:
        import ddcolor  # noqa: F401
    except Exception as exc:
        log.error("DDColor import failed: %s", exc)
        if last_err:
            log.error("Last vendor download error: %s", last_err)
        log.error("Install deps with: pip install -r requirements-ddcolor.txt")
        sys.exit(2)


def model_cache_dir(model_name: str) -> Path:
    safe = model_name.replace("/", "__")
    return MODELS_DIR / safe


def model_repo_id(model_name: str) -> str:
    if Path(model_name).expanduser().exists():
        return model_name
    return MODEL_REPOS.get(model_name, model_name if "/" in model_name else f"piddnad/{model_name}")


def valid_model_cache(path: Path) -> bool:
    config_path = path / "config.json"
    weights_path = path / "pytorch_model.bin"
    if not config_path.exists() or not weights_path.exists():
        return False
    try:
        json.loads(config_path.read_text(encoding="utf-8"))
        return weights_path.stat().st_size > 50 * 1024 * 1024
    except Exception:
        return False


def download_model_snapshot(model_name: str, force: bool = False) -> Path:
    model_path = Path(model_name).expanduser()
    if model_path.exists():
        return model_path.resolve()

    cache_dir = model_cache_dir(model_name)
    if not force and valid_model_cache(cache_dir):
        return cache_dir

    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:
        log.error("huggingface_hub import failed: %s", exc)
        log.error("Install deps with: pip install -r requirements-ddcolor.txt")
        sys.exit(2)

    repo_id = model_repo_id(model_name)
    log.info("Downloading DDColor model %s into %s", repo_id, cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(cache_dir),
        allow_patterns=["config.json", "pytorch_model.bin"],
        force_download=force,
    )
    if not valid_model_cache(cache_dir):
        raise RuntimeError(f"model cache is incomplete or invalid: {cache_dir}")
    return cache_dir


def resolve_device(device_name: str):
    import torch

    requested = (device_name or "cpu").lower()
    if requested == "auto":
        requested = "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("COLORIZE_DEVICE=cuda requested but CUDA is unavailable")
    if requested in {"mps", "mps:0"} and not getattr(torch.backends, "mps", None):
        raise RuntimeError("COLORIZE_DEVICE=mps requested but MPS is unavailable")
    return torch.device(requested)


def load_cached_model(model_cls, model_dir: Path):
    import torch

    config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
    state_dict = torch.load(
        model_dir / "pytorch_model.bin", map_location="cpu", weights_only=True, mmap=True
    )
    if "params" in state_dict:
        state_dict = state_dict["params"]
    model = model_cls(**config)
    model.load_state_dict(state_dict, strict=True)
    return model


class DDColorBatchColorizer:
    def __init__(self, model_name: str, device_name: str, input_size: int):
        ensure_ddcolor_on_path()

        import cv2
        import numpy as np
        import torch
        from ddcolor import ColorizationPipeline, DDColor

        self.cv2 = cv2
        self.np = np
        self.torch = torch
        self.device = resolve_device(device_name)
        self.input_size = int(input_size)

        model_dir = download_model_snapshot(model_name)
        try:
            model = load_cached_model(DDColor, model_dir)
        except ModuleNotFoundError:
            raise
        except Exception as exc:
            log.warning("Cached DDColor model failed to load, redownloading once: %s", exc)
            model_dir = download_model_snapshot(model_name, force=True)
            model = load_cached_model(DDColor, model_dir)

        model = model.to(self.device)
        model.eval()
        self.pipeline = ColorizationPipeline(model, input_size=self.input_size, device=self.device)
        log.info("Loaded DDColor model=%s device=%s input_size=%d", model_name, self.device, self.input_size)

    def colorize(self, src: Path, dst: Path, quality: int = 95) -> None:
        with Image.open(src) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            original_size = image.size
            rgb = self.np.asarray(image)

        bgr = self.cv2.cvtColor(rgb, self.cv2.COLOR_RGB2BGR)
        out_bgr = self.pipeline.process(bgr)
        out_rgb = self.cv2.cvtColor(out_bgr, self.cv2.COLOR_BGR2RGB)
        out = Image.fromarray(out_rgb)
        if out.size != original_size:
            out = out.resize(original_size, Image.Resampling.LANCZOS)
        save_jpeg(out, dst, quality)


def load_colorizer() -> DDColorBatchColorizer:
    return DDColorBatchColorizer(MODEL_NAME, DEVICE_NAME, INPUT_SIZE)


def save_jpeg(image: Image.Image, dst: Path, quality: int) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(dst, "JPEG", quality=quality, subsampling=0, optimize=True)


def valid_output(path: Path, expected_size: tuple[int, int] | None = None) -> bool:
    if not path.exists() or path.stat().st_size <= 0:
        return False
    try:
        with Image.open(path) as image:
            if image.format != "JPEG":
                return False
            if expected_size and image.size != expected_size:
                return False
            image.verify()
        with Image.open(path) as image:
            image.load()
            if expected_size and image.size != expected_size:
                return False
        return True
    except (OSError, UnidentifiedImageError):
        return False


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image)
        return image.size


def discover_inputs(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        return []
    return sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS
    )


def colorize_one(src: Path, dst: Path, colorizer, quality: int) -> bool:
    try:
        expected_size = image_size(src)
        colorizer.colorize(src, dst, quality)
        if not valid_output(dst, expected_size=expected_size):
            log.error("Output validation failed; keeping original: %s", src.name)
            return False
        try:
            src.unlink()
            log.info("Removed original B/W: %s", src.name)
        except Exception as exc:
            log.error("Colorized but could not remove original '%s': %s", src.name, exc)
            return False
        return True
    except Exception as exc:
        log.error("Colorize failed for %s: %s", src.name, exc)
        return False
    finally:
        gc.collect()


def main() -> None:
    if not IN_OTHER.exists():
        log.info("Input folder does not exist: %s - nothing to do.", IN_OTHER)
        sys.exit(0)

    candidates = discover_inputs(IN_OTHER)
    if not candidates:
        log.info("No candidate images found in %s - nothing to do.", IN_OTHER)
        sys.exit(0)

    processed = skipped = failed = removed = 0
    pending: list[tuple[Path, Path]] = []
    for src in candidates:
        dst = OUT_COLOR / (src.stem + ".jpg")
        if dst.exists():
            try:
                expected_size = image_size(src)
            except Exception as exc:
                log.error("Input validation failed for %s: %s", src.name, exc)
                failed += 1
                continue
            if valid_output(dst, expected_size=expected_size):
                log.info("Skip (exists): %s", dst.name)
                skipped += 1
                # A leftover grayscale copy would overwrite the colorized file in prep_dirs.
                try:
                    src.unlink()
                    removed += 1
                    log.info("Removed original B/W after validating existing output: %s", src.name)
                except Exception as exc:
                    log.error("Could not remove original '%s' for existing output: %s", src.name, exc)
                    failed += 1
                continue
            log.warning("Existing output is invalid and will be regenerated: %s", dst.name)
        pending.append((src, dst))

    colorizer = None
    if pending:
        colorizer = load_colorizer()

    for src, dst in pending:
        before_exists = src.exists()
        ok = colorize_one(src, dst, colorizer, JPEG_QUALITY)
        if ok:
            log.info("Colorized: %s -> %s", src.name, dst.name)
            processed += 1
            if before_exists and not src.exists():
                removed += 1
        else:
            failed += 1

    log.info(
        "Summary: processed=%d, skipped=%d, failed=%d, removed=%d",
        processed,
        skipped,
        failed,
        removed,
    )
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
