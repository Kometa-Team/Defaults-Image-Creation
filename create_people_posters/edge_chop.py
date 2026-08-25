"""Transparent PNG edge-contact checks used by QA and recovery scripts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image


EDGE_LABELS = {
    "top": "head/top",
    "bottom": "bottom-edge contact",
    "left": "left-edge contact",
    "right": "right-edge contact",
}


@dataclass(frozen=True)
class EdgeChopResult:
    path: Path
    width: int = 0
    height: int = 0
    top: float = 0.0
    bottom: float = 0.0
    left: float = 0.0
    right: float = 0.0
    threshold: float = 0.06
    issues: tuple[str, ...] = ()
    error: str = ""

    def values(self) -> dict[str, float]:
        return {
            "top": self.top,
            "bottom": self.bottom,
            "left": self.left,
            "right": self.right,
        }


def parse_edges(value: str | Iterable[str] | None, default: Iterable[str]) -> tuple[str, ...]:
    raw = default if value is None else value
    if isinstance(raw, str):
        items = [item.strip().lower() for item in raw.split(",")]
    else:
        items = [str(item).strip().lower() for item in raw]
    return tuple(item for item in items if item in EDGE_LABELS)


def detect_edge_chops(path: Path, threshold: float = 0.06, edges: Iterable[str] = ("top",)) -> EdgeChopResult:
    watched_edges = set(parse_edges(edges, default=("top",)))
    try:
        with Image.open(path) as img:
            rgba = img.convert("RGBA")
            width, height = rgba.size
            if width <= 0 or height <= 0:
                return EdgeChopResult(path=path, threshold=threshold, error="empty image")

            alpha = rgba.getchannel("A")
            top = _region_mean(alpha, (0, 0, width, 1))
            bottom = _region_mean(alpha, (0, height - 1, width, height))
            left = _region_mean(alpha, (0, 0, 1, height))
            right = _region_mean(alpha, (width - 1, 0, width, height))
            values = {"top": top, "bottom": bottom, "left": left, "right": right}
            issues = tuple(edge for edge in ("top", "bottom", "left", "right") if edge in watched_edges and values[edge] > threshold)
            return EdgeChopResult(
                path=path,
                width=width,
                height=height,
                top=top,
                bottom=bottom,
                left=left,
                right=right,
                threshold=threshold,
                issues=issues,
            )
    except Exception as exc:
        return EdgeChopResult(path=path, threshold=threshold, error=str(exc))


def _region_mean(alpha: Image.Image, box: tuple[int, int, int, int]) -> float:
    crop = alpha.crop(box)
    extrema = crop.getextrema()
    if extrema == (0, 0):
        return 0.0
    pixels = list(crop.getdata())
    return float(sum(pixels) / (len(pixels) * 255.0)) if pixels else 0.0


def issue_summary(result: EdgeChopResult) -> str:
    if result.error:
        return f"error: {result.error}"
    if not result.issues:
        return ""
    values = result.values()
    return "; ".join(
        f"{EDGE_LABELS[edge]} edge alpha mean {values[edge]:.4f} > {result.threshold:.4f}"
        for edge in result.issues
    )


def has_any_issue(result: EdgeChopResult, edges: Iterable[str]) -> bool:
    watched_edges = set(parse_edges(edges, default=("top",)))
    return any(edge in watched_edges for edge in result.issues)
