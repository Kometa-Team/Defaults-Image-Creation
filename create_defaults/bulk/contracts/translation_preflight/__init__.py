"""Opt-in, read-only translation evidence. No production or publication hooks."""

from .engine import evaluate, revalidate
from .models import TranslationPreflight, read_report
from .sources import SnapshotInput, UnavailableSourceVerifier
from .adapters import PosterRequest, OverlayRequest

__all__ = ["evaluate", "revalidate", "TranslationPreflight", "read_report",
           "SnapshotInput", "UnavailableSourceVerifier", "PosterRequest", "OverlayRequest"]
