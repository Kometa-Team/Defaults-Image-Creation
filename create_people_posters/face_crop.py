"""Face-position crop diagnostics used by image QA scripts.

These checks are intentionally report-only. A face detector can flag likely
left/right/chin crop risk, but it is not reliable enough to drive automatic
replacement decisions without manual review.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageOps


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_FACE_MODEL_HOME = SCRIPT_DIR / "config" / "models" / "opencv"
DEFAULT_FACE_MODEL_NAME = "face_detection_yunet_2026may.onnx"
DEFAULT_FACE_MODEL_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/"
    "models/face_detection_yunet/face_detection_yunet_2026may.onnx"
)
FACE_CROP_LABELS = {
    "chin": "possible chin/bottom face crop",
    "left": "possible left-side face crop",
    "right": "possible right-side face crop",
}
DEFAULT_FACE_CROP_CHECKS = ("chin", "left", "right")

_DETECTORS = {}


@dataclass(frozen=True)
class FaceCropResult:
    path: Path
    width: int = 0
    height: int = 0
    face_box: tuple[int, int, int, int] | None = None
    left_margin: float = 1.0
    right_margin: float = 1.0
    bottom_margin: float = 1.0
    side_margin_threshold: float = 0.02
    chin_margin_threshold: float = 0.015
    issues: tuple[str, ...] = ()
    error: str = ""


def parse_face_crop_checks(value: str | Iterable[str] | None, default: Iterable[str]) -> tuple[str, ...]:
    raw = default if value is None else value
    if isinstance(raw, str):
        items = [item.strip().lower() for item in raw.split(",")]
    else:
        items = [str(item).strip().lower() for item in raw]

    checks: list[str] = []
    for item in items:
        if item in {"", "none", "false", "off", "0"}:
            continue
        if item in {"side", "sides"}:
            for side in ("left", "right"):
                if side not in checks:
                    checks.append(side)
            continue
        if item == "bottom":
            item = "chin"
        if item in FACE_CROP_LABELS and item not in checks:
            checks.append(item)
    return tuple(checks)


def detect_face_crop_issues(
    path: Path,
    checks: Iterable[str] = DEFAULT_FACE_CROP_CHECKS,
    side_margin_threshold: float = 0.02,
    chin_margin_threshold: float = 0.015,
    max_detection_dim: int = 640,
    score_threshold: float = 0.75,
) -> FaceCropResult:
    watched = set(parse_face_crop_checks(checks, DEFAULT_FACE_CROP_CHECKS))
    if not watched:
        return FaceCropResult(path=path)

    try:
        os.environ.setdefault("OPENCV_FORCE_DNN_ENGINE", "4")
        os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
        cv2, bgr, width, height, scale = _load_bgr(path, max_detection_dim)
        detector = _load_detector(cv2, (bgr.shape[1], bgr.shape[0]), score_threshold)
        detector.setInputSize((bgr.shape[1], bgr.shape[0]))
        _retval, detected = detector.detect(bgr)

        if detected is None or len(detected) == 0:
            return FaceCropResult(path=path, width=width, height=height)

        sx = 1.0 / scale
        face = max(detected, key=lambda row: float(row[2]) * float(row[3]) * float(row[-1]))
        x, y, w, h = (float(face[0]), float(face[1]), float(face[2]), float(face[3]))
        face_box = (
            max(0, round(x * sx)),
            max(0, round(y * sx)),
            max(1, round(w * sx)),
            max(1, round(h * sx)),
        )

        fx, _fy, fw, fh = face_box
        left_margin = fx / width
        right_margin = max(0, width - (fx + fw)) / width
        bottom_margin = max(0, height - (_fy + fh)) / height

        issues: list[str] = []
        if "left" in watched and left_margin <= side_margin_threshold:
            issues.append("left")
        if "right" in watched and right_margin <= side_margin_threshold:
            issues.append("right")
        if "chin" in watched and bottom_margin <= chin_margin_threshold:
            issues.append("chin")

        return FaceCropResult(
            path=path,
            width=width,
            height=height,
            face_box=face_box,
            left_margin=left_margin,
            right_margin=right_margin,
            bottom_margin=bottom_margin,
            side_margin_threshold=side_margin_threshold,
            chin_margin_threshold=chin_margin_threshold,
            issues=tuple(issues),
        )
    except Exception as exc:
        return FaceCropResult(path=path, error=str(exc))


def face_crop_summary(result: FaceCropResult) -> str:
    if result.error:
        return f"error: {result.error}"
    if not result.issues:
        return ""

    x, y, w, h = result.face_box or (0, 0, 0, 0)
    parts = []
    for issue in result.issues:
        if issue in {"left", "right"}:
            margin = result.left_margin if issue == "left" else result.right_margin
            threshold = result.side_margin_threshold
        else:
            margin = result.bottom_margin
            threshold = result.chin_margin_threshold
        parts.append(f"{FACE_CROP_LABELS[issue]} margin {margin:.4f} <= {threshold:.4f}")
    return "; ".join(parts) + f"; face box {x},{y},{w},{h}"


def _load_detector(cv2, input_size: tuple[int, int], score_threshold: float):
    key = (_model_path(), input_size, score_threshold)
    if key in _DETECTORS:
        return _DETECTORS[key]

    model_path = _ensure_model(key[0])
    if not hasattr(cv2, "FaceDetectorYN"):
        raise RuntimeError("OpenCV FaceDetectorYN is unavailable in this cv2 build")

    detector = cv2.FaceDetectorYN.create(
        model=str(model_path),
        config="",
        input_size=input_size,
        score_threshold=score_threshold,
        nms_threshold=0.3,
        top_k=5000,
        backend_id=cv2.dnn.DNN_BACKEND_OPENCV,
        target_id=cv2.dnn.DNN_TARGET_CPU,
    )
    _DETECTORS[key] = detector
    return detector


def _load_bgr(path: Path, max_detection_dim: int):
    import cv2

    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        if "A" in img.getbands():
            rgba = img.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            img = Image.alpha_composite(bg, rgba).convert("RGB")
        else:
            img = img.convert("RGB")

        width, height = img.size
        scale = min(1.0, max_detection_dim / max(width, height))
        if scale < 1.0:
            img = img.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.Resampling.LANCZOS)

        rgb = np.asarray(img)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        return cv2, bgr, width, height, scale


def _model_path() -> Path:
    configured = os.getenv("FACE_CROP_MODEL_PATH", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    home = Path(os.getenv("FACE_CROP_MODEL_HOME", str(DEFAULT_FACE_MODEL_HOME))).expanduser().resolve()
    return home / DEFAULT_FACE_MODEL_NAME


def _ensure_model(model_path: Path) -> Path:
    if model_path.exists() and model_path.stat().st_size > 1024:
        return model_path

    from urllib.request import urlopen

    model_path.parent.mkdir(parents=True, exist_ok=True)
    url = os.getenv("FACE_CROP_MODEL_URL", DEFAULT_FACE_MODEL_URL)
    tmp_path = model_path.with_suffix(model_path.suffix + ".tmp")
    with urlopen(url, timeout=60) as response:
        data = response.read()
    if data.startswith(b"version https://git-lfs"):
        raise RuntimeError(f"downloaded Git LFS pointer instead of model from {url}")
    if len(data) <= 1024:
        raise RuntimeError(f"downloaded model from {url} is unexpectedly small")
    tmp_path.write_bytes(data)
    tmp_path.replace(model_path)
    return model_path
