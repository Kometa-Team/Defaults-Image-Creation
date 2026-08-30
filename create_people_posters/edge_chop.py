"""Transparent PNG edge-contact checks used by QA and recovery scripts."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable

from PIL import Image


EDGE_LABELS = {
    "top": "head/top",
    "bottom": "bottom-edge contact",
    "left": "left-edge contact",
    "right": "right-edge contact",
}
DEFAULT_ALPHA_MIN = 8
DEFAULT_COVERAGE_THRESHOLD = 0.015


@dataclass(frozen=True)
class EdgeChopResult:
    path: Path
    width: int = 0
    height: int = 0
    top: float = 0.0
    bottom: float = 0.0
    left: float = 0.0
    right: float = 0.0
    top_coverage: float = 0.0
    bottom_coverage: float = 0.0
    left_coverage: float = 0.0
    right_coverage: float = 0.0
    threshold: float = 0.06
    coverage_threshold: float = DEFAULT_COVERAGE_THRESHOLD
    alpha_min: int = DEFAULT_ALPHA_MIN
    issues: tuple[str, ...] = ()
    error: str = ""

    def values(self) -> dict[str, float]:
        return {
            "top": self.top,
            "bottom": self.bottom,
            "left": self.left,
            "right": self.right,
        }

    def coverages(self) -> dict[str, float]:
        return {
            "top": self.top_coverage,
            "bottom": self.bottom_coverage,
            "left": self.left_coverage,
            "right": self.right_coverage,
        }


def parse_edges(value: str | Iterable[str] | None, default: Iterable[str]) -> tuple[str, ...]:
    raw = default if value is None else value
    if isinstance(raw, str):
        items = [item.strip().lower() for item in raw.split(",")]
    else:
        items = [str(item).strip().lower() for item in raw]
    return tuple(item for item in items if item in EDGE_LABELS)


def _float_env(key: str, default: float) -> float:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int_env(key: str, default: int) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def detect_edge_chops(
    path: Path,
    threshold: float = 0.06,
    edges: Iterable[str] = ("top",),
    coverage_threshold: float | None = None,
    alpha_min: int | None = None,
) -> EdgeChopResult:
    watched_edges = set(parse_edges(edges, default=("top",)))
    if coverage_threshold is None:
        coverage_threshold = _float_env("EDGE_CHOP_COVERAGE_THRESHOLD", DEFAULT_COVERAGE_THRESHOLD)
    if alpha_min is None:
        alpha_min = _int_env("EDGE_CHOP_ALPHA_MIN", DEFAULT_ALPHA_MIN)
    try:
        with Image.open(path) as img:
            rgba = img.convert("RGBA")
            width, height = rgba.size
            if width <= 0 or height <= 0:
                return EdgeChopResult(
                    path=path,
                    threshold=threshold,
                    coverage_threshold=coverage_threshold,
                    alpha_min=alpha_min,
                    error="empty image",
                )

            alpha = rgba.getchannel("A")
            top, top_coverage = _region_stats(alpha, (0, 0, width, 1), alpha_min)
            bottom, bottom_coverage = _region_stats(alpha, (0, height - 1, width, height), alpha_min)
            left, left_coverage = _region_stats(alpha, (0, 0, 1, height), alpha_min)
            right, right_coverage = _region_stats(alpha, (width - 1, 0, width, height), alpha_min)
            values = {"top": top, "bottom": bottom, "left": left, "right": right}
            coverages = {
                "top": top_coverage,
                "bottom": bottom_coverage,
                "left": left_coverage,
                "right": right_coverage,
            }
            issues = tuple(
                edge for edge in ("top", "bottom", "left", "right")
                if edge in watched_edges
                and (values[edge] > threshold or coverages[edge] > coverage_threshold)
            )
            return EdgeChopResult(
                path=path,
                width=width,
                height=height,
                top=top,
                bottom=bottom,
                left=left,
                right=right,
                top_coverage=top_coverage,
                bottom_coverage=bottom_coverage,
                left_coverage=left_coverage,
                right_coverage=right_coverage,
                threshold=threshold,
                coverage_threshold=coverage_threshold,
                alpha_min=alpha_min,
                issues=issues,
            )
    except Exception as exc:
        return EdgeChopResult(
            path=path,
            threshold=threshold,
            coverage_threshold=coverage_threshold,
            alpha_min=alpha_min,
            error=str(exc),
        )


def _region_stats(alpha: Image.Image, box: tuple[int, int, int, int], alpha_min: int) -> tuple[float, float]:
    crop = alpha.crop(box)
    extrema = crop.getextrema()
    if extrema == (0, 0):
        return 0.0, 0.0
    pixels = list(crop.getdata())
    if not pixels:
        return 0.0, 0.0
    mean = float(sum(pixels) / (len(pixels) * 255.0))
    coverage = float(sum(1 for px in pixels if px > alpha_min) / len(pixels))
    return mean, coverage


def issue_summary(result: EdgeChopResult) -> str:
    if result.error:
        return f"error: {result.error}"
    if not result.issues:
        return ""
    values = result.values()
    coverages = result.coverages()
    return "; ".join(
        f"{EDGE_LABELS[edge]} edge alpha mean {values[edge]:.4f} > {result.threshold:.4f} "
        f"or coverage {coverages[edge]:.4f} > {result.coverage_threshold:.4f}"
        for edge in result.issues
    )


def has_any_issue(result: EdgeChopResult, edges: Iterable[str]) -> bool:
    watched_edges = set(parse_edges(edges, default=("top",)))
    return any(edge in watched_edges for edge in result.issues)
