"""Opt-in read-only P3/M4 evidence consumption; never operational authority."""

from .engine import consume, revalidate, TranslationInput
from .models import ConsumptionAttestation, RequestContext, read_attestation

__all__ = ["consume", "revalidate", "TranslationInput", "ConsumptionAttestation",
           "RequestContext", "read_attestation"]
