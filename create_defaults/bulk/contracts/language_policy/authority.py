"""Trusted-caller interfaces; no live authenticator or operational grants in M1."""

from dataclasses import dataclass
from enum import Enum
import re
from typing import Protocol, runtime_checkable

from ...common import BulkError
from ..registry import require_hash
from .models import DestinationEvidence, timestamp


def _identity(value):
    if type(value) is not str or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,199}", value):
        raise BulkError("phase3_context", "Malformed trusted-context identity")


def _version(value):
    if type(value) is not str or not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value):
        raise BulkError("phase3_context", "Malformed trusted-context version")


@dataclass(frozen=True)
class AuthorityContext:
    """Selected by trusted code, never constructed from submitted JSON.

    This context is an exact attribution/binding interface, not an authenticator.
    A future controlled provider must establish the external facts independently.
    Even a correctly constructed M1 context grants no real readiness authority.
    """

    evidence_sha256: str
    subject_sha256: str
    destination_policy_sha256: str
    target_sha256: str
    assertion_sha256: str
    verification_context_sha256: str
    principal: str
    issuer: str
    issuer_version: str
    as_of: str

    def __post_init__(self):
        for name in ("evidence_sha256", "subject_sha256", "destination_policy_sha256", "target_sha256",
                     "assertion_sha256", "verification_context_sha256"):
            require_hash(getattr(self, name))
        _identity(self.principal)
        _identity(self.issuer)
        _version(self.issuer_version)
        timestamp(self.as_of)


@dataclass(frozen=True)
class SourceVerificationContext:
    """Future trusted source-verifier input, not an assertion of currentness.

    No verifier/refresh/TTL or readiness consumption is implemented in M1.
    Exact source and context pins remain separate from untrusted document claims.
    """

    selection_sha256: str
    source_sha256: str
    verification_context_sha256: str
    commit: str
    tree: str
    issuer: str
    issuer_version: str
    as_of: str

    def __post_init__(self):
        for name in ("selection_sha256", "source_sha256", "verification_context_sha256"):
            require_hash(getattr(self, name))
        for value in (self.commit, self.tree):
            if type(value) is not str or not re.fullmatch(r"[0-9a-f]{40}", value):
                raise BulkError("phase3_context", "Malformed source commit/tree context")
        _identity(self.issuer)
        _version(self.issuer_version)
        timestamp(self.as_of)


class AuthorityStatus(str, Enum):
    UNAVAILABLE = "unavailable"
    UNVERIFIABLE = "unverifiable"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SYNTHETIC_ONLY = "synthetic-only"


@dataclass(frozen=True)
class AuthorityResult:
    status: AuthorityStatus
    evidence_sha256: str

    def __post_init__(self):
        if type(self.status) is not AuthorityStatus:
            raise BulkError("phase3_authority", "Unknown authority interface outcome")
        require_hash(self.evidence_sha256)

    @property
    def readiness_authorized(self):
        return False

    @property
    def publication_authorized(self):
        return False


@runtime_checkable
class AuthorityVerifier(Protocol):
    def verify(self, evidence: DestinationEvidence, context: AuthorityContext | None = None) -> AuthorityResult:
        """Inspect explicitly attributed evidence; M1 never returns a real grant."""
        ...


class UnavailableAuthority:
    """Default interface: no provider, credentials, IO, clock or permissive path."""

    def verify(self, evidence: DestinationEvidence, context: AuthorityContext | None = None) -> AuthorityResult:
        if type(evidence) is not DestinationEvidence:
            raise BulkError("phase3_type", "Authority interface requires destination observation evidence")
        return AuthorityResult(AuthorityStatus.UNAVAILABLE, evidence.sha256)
