"""Opt-in lifecycle foundations. No production adapter imports this package.

Loading metadata establishes integrity, never generation/publication authority.
There are no default registry, active contracts or lifecycle operations.
"""

from .models import (
    AdoptionRecord, Contract, ContractApproval, ExceptionDecision, ExceptionRequest,
    Identity, PreviewManifest, RegistryDocument, SubmitterConfirmation,
    ValidationAttestation, check_namespace, read_document,
)
from .registry import RegistrySnapshot, TrustedDecision
from .state import ContractStore

__all__ = [
    "Contract", "Identity", "RegistryDocument", "ContractApproval", "AdoptionRecord",
    "ExceptionRequest", "PreviewManifest", "SubmitterConfirmation", "ExceptionDecision",
    "ValidationAttestation", "RegistrySnapshot", "TrustedDecision", "ContractStore",
    "check_namespace", "read_document",
]
