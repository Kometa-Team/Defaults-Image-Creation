#!/usr/bin/env python3
"""Local, validated background removal with the existing People poster handoff."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import gc
import hashlib
from importlib.metadata import version
import inspect
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unicodedata
import warnings

from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"
MODEL_NAMES = ("birefnet-portrait", "birefnet-general", "isnet-general-use")
# Checksums published in the pinned rembg 2.0.85 session implementations.
MODEL_CHECKSUMS = {
    "birefnet-portrait": "c3a64a6abf20250d090cd055f12a3b67",
    "birefnet-general": "7a35a0141cbbc80de11d9c9a28f52697",
    "isnet-general-use": "fc16ebd8b0c10d971d3513d564d01e29",
}
INPUT_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
LOG = logging.getLogger("remove_bg_birefnet")


def env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    value = value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{key} must be true or false")


@dataclass(frozen=True)
class Settings:
    model: str = "birefnet-portrait"
    device: str = "cpu"
    decontaminate: bool = True
    alpha_matting: bool = False
    overwrite: bool = False
    home: Path = CONFIG_DIR / "models" / "rembg"

    def __post_init__(self):
        if self.model not in MODEL_NAMES:
            raise ValueError(f"Unsupported REMOVE_BG_MODEL={self.model}; choose {', '.join(MODEL_NAMES)}")
        if self.device not in {"cpu", "cuda", "rocm", "coreml"}:
            raise ValueError("REMOVE_BG_DEVICE must be cpu, cuda, rocm, or coreml")

    @classmethod
    def from_env(cls):
        return cls(
            model=os.getenv("REMOVE_BG_MODEL", "birefnet-portrait").strip(),
            device=os.getenv("REMOVE_BG_DEVICE", "cpu").strip().lower(),
            decontaminate=env_bool("REMOVE_BG_DECONTAMINATE", True),
            alpha_matting=env_bool("REMOVE_BG_ALPHA_MATTING", False),
            overwrite=env_bool("REMOVE_BG_OVERWRITE", False),
            home=Path(os.getenv("REMBG_HOME") or CONFIG_DIR / "models" / "rembg").expanduser().resolve(),
        )

    def fingerprint(self) -> dict:
        return {"engine": "birefnet", "model": self.model, "device": self.device,
                "decontaminate": self.decontaminate, "alpha_matting": self.alpha_matting}


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def sidecar(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".bg.json")


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".bg-", suffix=".tmp", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=True)
            handle.flush()
            os.fsync(handle.fileno())
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def atomic_copy(source: Path, destination: Path) -> None:
    if source.resolve() == destination.resolve():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".bg-", suffix=".tmp", dir=destination.parent)
    os.close(fd)
    tmp = Path(name)
    try:
        shutil.copyfile(source, tmp)
        if sha256(source) != sha256(tmp):
            raise OSError("Copy verification failed")
        tmp.replace(destination)
    finally:
        tmp.unlink(missing_ok=True)


def validate_output(path: Path, expected_size: tuple[int, int] | None = None) -> dict:
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        image.load()
        if image.format != "PNG" or image.mode != "RGBA":
            raise ValueError("Output must be an RGBA PNG")
        if expected_size is not None and image.size != tuple(expected_size):
            raise ValueError(f"Output dimensions {image.size} differ from source {expected_size}")
        histogram = image.getchannel("A").histogram()
        alpha_min, alpha_max = image.getchannel("A").getextrema()
        count = image.width * image.height
        foreground = sum(histogram[9:]) / count
        background = sum(histogram[:247]) / count
        if foreground < 0.005:
            raise ValueError(f"Empty/nearly empty foreground mask: coverage={foreground:.6f}")
        if background < 0.0001:
            raise ValueError("Opaque/nearly opaque output has no meaningful transparency")
        if alpha_min == alpha_max:
            raise ValueError("Uniform alpha mask does not separate a foreground from its background")
        warnings = []
        if foreground > 0.98:
            warnings.append("excessive foreground coverage; inspect background removal")
        metrics = {"foreground_coverage": foreground, "background_fraction": background,
                   "soft_alpha_fraction": sum(histogram[1:255]) / count,
                   "alpha_mean": sum(i * n for i, n in enumerate(histogram)) / (count * 255),
                   "alpha_min": alpha_min, "alpha_max": alpha_max}
        return {"dimensions": list(image.size), "metrics": metrics, "warnings": warnings}


class LocalRemover:
    """One ONNX session per batch; process never moves or deletes its source."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = None
        self._remove = None
        self._matting = None
        self.model_identifier = settings.model
        try:
            import onnxruntime as ort
            from rembg import new_session, remove
            from rembg.sessions import sessions_class
        except (ImportError, SystemExit) as exc:
            raise RuntimeError("Install requirements-rembg.txt in REMOVE_BG_PYTHON (Python 3.13 supported)") from exc
        if settings.decontaminate and "decontaminate" not in inspect.signature(remove).parameters:
            raise RuntimeError("Installed rembg lacks decontamination; install the pinned requirements-rembg.txt")
        if os.getenv("MODEL_CHECKSUM_DISABLED") is not None:
            raise RuntimeError("Unset MODEL_CHECKSUM_DISABLED so downloaded weights are verified")
        settings.home.mkdir(parents=True, exist_ok=True)
        # Older rembg releases use U2NET_HOME, newer releases honor REMBG_HOME.
        os.environ["REMBG_HOME"] = str(settings.home)
        os.environ["U2NET_HOME"] = str(settings.home)
        providers = {"cpu": "CPUExecutionProvider", "cuda": "CUDAExecutionProvider",
                     "rocm": "ROCMExecutionProvider", "coreml": "CoreMLExecutionProvider"}
        requested = providers[settings.device]
        if requested not in ort.get_available_providers():
            raise RuntimeError(f"{requested} unavailable; use REMOVE_BG_DEVICE=cpu or install its runtime")
        model_class = next((cls for cls in sessions_class if cls.name() == settings.model), None)
        if model_class is None:
            raise RuntimeError(f"Installed rembg does not support {settings.model}; install requirements-rembg.txt")
        try:
            model_path = Path(model_class.download_models())
            # rembg trusts existing cache files without rechecking their checksum.
            with model_path.open("rb") as handle:
                checksum = hashlib.file_digest(handle, "md5").hexdigest()
            if checksum != MODEL_CHECKSUMS[settings.model]:
                raise RuntimeError(f"Model checksum mismatch: {model_path}; move the corrupt cache file aside and retry")
            self.model_sha256 = sha256(model_path)
            self.model_identifier = f"{settings.model}:{self.model_sha256}"
            self.rembg_version = version("rembg")
            self.session = new_session(settings.model, providers=[requested] if settings.device == "cpu"
                                       else [requested, "CPUExecutionProvider"])
            active = self.session.inner_session.get_providers()
            if requested not in active:
                raise RuntimeError(f"Requested {requested}, but loaded {active}; check accelerator runtime")
            self._remove = remove
            if settings.alpha_matting:
                from rembg.bg import alpha_matting_cutout
                self._matting = alpha_matting_cutout
        except Exception as exc:
            self.close()
            raise RuntimeError(f"Cannot initialize {settings.model} in {settings.home}: {exc}. "
                               "Check model download access, cache integrity and available memory.") from exc
        LOG.info("Engine=birefnet model=%s rembg=%s device=%s providers=%s", self.model_identifier,
                 self.rembg_version, settings.device, active)
        if settings.alpha_matting and settings.decontaminate:
            LOG.info("Alpha matting performs foreground decontamination internally")

    def process(self, source: Path, destination: Path) -> dict:
        source, destination = Path(source), Path(destination)
        if source.suffix.lower() not in INPUT_EXTS:
            raise ValueError(f"Unsupported input format {source.suffix}")
        if source.resolve() == destination.resolve():
            raise ValueError("Inference output must differ from the source photograph")
        start = time.perf_counter()
        with Image.open(source) as image:
            image.load()
            size = image.size
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("Animated/multipage input is unsupported")
            # Preserve stored pixel dimensions; input is already oriented by staging.
            rgb = image.convert("RGB")
        digest = sha256(source)
        try:
            if destination.exists() and not self.settings.overwrite:
                metadata = validate_output(destination, size)
                try:
                    prior = json.loads(sidecar(destination).read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    prior = {}
                if (prior.get("settings") != self.settings.fingerprint()
                        or prior.get("source_sha256") != digest
                        or prior.get("model_identifier") != self.model_identifier
                        or prior.get("output_sha256") != sha256(destination)):
                    raise FileExistsError(f"Keep existing {destination}; provenance differs or is unknown. "
                                          "Restage its exact original and set REMOVE_BG_OVERWRITE=true to reprocess.")
                metadata["warnings"] = list(dict.fromkeys(prior.get("warnings", []) + metadata["warnings"]))
                return {**prior, **metadata, "status": "skipped", "duration": time.perf_counter() - start}
            destination.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix=".bg-", suffix=".png", dir=destination.parent)
            os.close(fd)
            tmp = Path(name)
            inference_warnings = []
            try:
                with warnings.catch_warnings(record=True) as observed:
                    warnings.simplefilter("always", RuntimeWarning)
                    try:
                        if self.settings.alpha_matting:
                            # Use rembg's solver directly; its remove() silently falls back on ValueError.
                            mask = self._remove(rgb, session=self.session, only_mask=True,
                                                alpha_matting=False, decontaminate=False, post_process_mask=False)
                            try:
                                result = self._matting(rgb, mask, 240, 10, 10)
                            finally:
                                if isinstance(mask, Image.Image):
                                    mask.close()
                        else:
                            result = self._remove(rgb, session=self.session, alpha_matting=False,
                                                  decontaminate=self.settings.decontaminate, post_process_mask=False)
                    finally:
                        for warning in observed:
                            message = f"{warning.category.__name__}: {warning.message}"
                            inference_warnings.append(message)
                            LOG.warning("model=%s input=%s %s", self.model_identifier, source.name, message)
                try:
                    if not isinstance(result, Image.Image):
                        raise ValueError("Inference returned an unexpected output type")
                    if result.mode != "RGBA":
                        raise ValueError("Inference did not return RGBA")
                    result.save(tmp, format="PNG")
                finally:
                    if isinstance(result, Image.Image):
                        result.close()
                metadata = validate_output(tmp, size)
                metadata["warnings"].extend(inference_warnings)
                tmp.replace(destination)
            finally:
                tmp.unlink(missing_ok=True)
            record = {**metadata, "engine": "birefnet", "model": self.settings.model,
                      "model_identifier": self.model_identifier, "rembg_version": self.rembg_version,
                      "device": self.settings.device, "settings": self.settings.fingerprint(),
                      "source": str(source), "output": str(destination), "source_sha256": digest,
                      "output_sha256": sha256(destination), "status": "processed",
                      "duration": time.perf_counter() - start}
            atomic_json(sidecar(destination), record)
            return record
        finally:
            rgb.close()

    def close(self):
        self.session = None
        self._remove = None
        self._matting = None
        gc.collect()


def check_archive(source: Path, archive_dir: Path) -> None:
    candidates = (archive_dir / source.name,
                  archive_dir / source.stem[:1].upper() / "Images" / source.name)
    digest = sha256(source)
    for prior in candidates:
        if prior.is_file() and sha256(prior) != digest:
            raise FileExistsError(f"Preserved original differs: {prior}; move it to a safe archive before retrying")


def archive_source(source: Path, archive_dir: Path) -> Path:
    destination = archive_dir / source.name
    if destination.resolve() == source.resolve():
        raise ValueError("SEL_ORIG_DIR must differ from SEL_SRC_DIR")
    check_archive(source, archive_dir)
    if not destination.exists():
        atomic_copy(source, destination)
    return destination


def run_batch(source_dir: Path, original_dir: Path, output_dir: Path, settings: Settings,
              remover_factory=LocalRemover) -> dict:
    start = time.perf_counter()
    summary = {"processed": 0, "skipped": 0, "failed": 0, "files": [], "exit_code": 0}
    if not source_dir.is_dir():
        raise ValueError(f"Input folder does not exist: {source_dir}")
    if original_dir.resolve() in {source_dir.resolve(), output_dir.resolve()}:
        raise ValueError("SEL_ORIG_DIR must differ from input and output folders")
    files = []
    entries = sorted(source_dir.iterdir(), key=lambda p: p.name.casefold())
    restaged = {unicodedata.normalize("NFC", p.stem).casefold() for p in entries
                if p.is_file() and p.suffix.lower() in INPUT_EXTS - {".png"}}
    for path in entries:
        if not path.is_file() or path.name.startswith(".") or path.name.endswith(".bg.json"):
            continue
        if path.suffix.lower() == ".png":
            try:
                validate_output(path)
            except Exception:
                pass
            else:
                # Already-staged cutouts must never become new source photographs.
                if unicodedata.normalize("NFC", path.stem).casefold() in restaged:
                    continue
                try:
                    prior = json.loads(sidecar(path).read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    prior = {}
                if (prior.get("settings") == settings.fingerprint()
                        and prior.get("output_sha256") == sha256(path)):
                    summary["skipped"] += 1
                    continue
                summary["failed"] += 1
                summary["files"].append({"source": str(path), "status": "failed",
                                          "reason": "Staged cutout has unknown/different engine provenance; restage exact source"})
                LOG.error("%s: staged cutout has unknown/different provenance; restage its original", path.name)
                continue
        files.append(path)
    targets: dict[str, list[Path]] = {}
    for path in files:
        targets.setdefault(unicodedata.normalize("NFC", path.stem).casefold(), []).append(path)
    remover = None
    try:
        for source in files:
            began = time.perf_counter()
            target = output_dir / (source.stem + ".png")
            staged = source_dir / target.name
            try:
                if source.suffix.lower() not in INPUT_EXTS:
                    raise ValueError(f"Unsupported input format {source.suffix}")
                if len(targets[unicodedata.normalize("NFC", source.stem).casefold()]) != 1:
                    raise ValueError("Ambiguous input basenames would overwrite the same PNG")
                with Image.open(source) as image:
                    image.load()
                    size = image.size
                # Check archive collisions before inference or publishing any output.
                check_archive(source, original_dir)
                if staged != source and staged.exists() and not settings.overwrite:
                    validate_output(staged, size)
                    if not target.exists() or sha256(staged) != sha256(target):
                        raise FileExistsError(f"Keep existing staged output {staged}; explicit overwrite required")
                if remover is None:
                    try:
                        remover = remover_factory(settings)
                    except Exception as exc:
                        summary["exit_code"] = 2
                        summary["initialization_error"] = str(exc)
                        LOG.error("Fatal model initialization: %s", exc)
                        break
                record = remover.process(source, target)
                validate_output(target, size)
                archive_source(source, original_dir)
                atomic_copy(target, staged)
                atomic_copy(sidecar(target), sidecar(staged))
                validate_output(staged, size)
                if source.resolve() != staged.resolve():
                    source.unlink()
                summary[record["status"]] += 1
                record["duration"] = time.perf_counter() - began
                summary["files"].append(record)
                LOG.info("%s input=%s output=%s dimensions=%s seconds=%.3f warnings=%s",
                         record["status"], source.name, target.name, record["dimensions"],
                         record["duration"], record["warnings"])
            except Exception as exc:
                summary["failed"] += 1
                summary["files"].append({"source": str(source), "output": str(target),
                                          "status": "failed", "duration": time.perf_counter() - began,
                                          "reason": str(exc)})
                LOG.error("failed input=%s output=%s seconds=%.3f reason=%s", source.name,
                          target.name, time.perf_counter() - began, exc)
    finally:
        if remover is not None:
            remover.close()
    if summary["failed"] and not summary["exit_code"]:
        summary["exit_code"] = 1
    summary["duration"] = time.perf_counter() - start
    summary["outcome"] = ("fatal" if summary["exit_code"] == 2 else "partial_failure" if summary["failed"]
                          else "success" if summary["processed"] else "no_work")
    LOG.info("Files processed: %d", summary["processed"])
    LOG.info("Summary: processed=%d skipped=%d failed=%d seconds=%.3f outcome=%s",
             summary["processed"], summary["skipped"], summary["failed"], summary["duration"], summary["outcome"])
    return summary


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        from dotenv import load_dotenv
        load_dotenv(CONFIG_DIR / ".env")
    except ImportError:
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Single photograph (preserved in place)")
    parser.add_argument("--output", type=Path, help="Single PNG destination")
    parser.add_argument("--source-dir", type=Path, default=Path(os.getenv("SEL_SRC_DIR") or CONFIG_DIR / "people_dirs" / "Downloads"))
    parser.add_argument("--original-dir", type=Path, default=Path(os.getenv("SEL_ORIG_DIR") or CONFIG_DIR / "people_dirs" / "original"))
    parser.add_argument("--output-dir", type=Path, default=Path(os.getenv("SEL_DOWNLOAD_DIR") or CONFIG_DIR / "sel_downloads"))
    parser.add_argument("--model", choices=MODEL_NAMES)
    parser.add_argument("--overwrite", action="store_true", default=None)
    parser.add_argument("--summary", type=Path, default=CONFIG_DIR / "logs" / "remove_bg_birefnet.json")
    args = parser.parse_args(argv)
    if bool(args.input) != bool(args.output):
        parser.error("--input and --output must be used together")
    log_dir = CONFIG_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                        handlers=[logging.FileHandler(log_dir / "remove_bg_birefnet.log", mode="w", encoding="utf-8"),
                                  logging.StreamHandler()], force=True)
    try:
        settings = Settings.from_env()
        from dataclasses import replace
        if args.model:
            settings = replace(settings, model=args.model)
        if args.overwrite is not None:
            settings = replace(settings, overwrite=args.overwrite)
        LOG.info("Engine=birefnet model=%s device=%s cache=%s", settings.model, settings.device, settings.home)
        if args.input:
            remover = LocalRemover(settings)
            try:
                record = remover.process(args.input.resolve(), args.output.resolve())
                LOG.info("%s input=%s output=%s dimensions=%s seconds=%.3f warnings=%s", record["status"],
                         args.input.name, args.output.name, record["dimensions"], record["duration"], record["warnings"])
                summary = {"exit_code": 0, "outcome": "success", "files": [record]}
            finally:
                remover.close()
        else:
            summary = run_batch(args.source_dir.resolve(), args.original_dir.resolve(), args.output_dir.resolve(), settings)
        atomic_json(args.summary, summary)
        return summary["exit_code"]
    except Exception as exc:
        LOG.error("Fatal background-removal error: %s", exc)
        atomic_json(args.summary, {"exit_code": 2, "outcome": "fatal", "reason": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
