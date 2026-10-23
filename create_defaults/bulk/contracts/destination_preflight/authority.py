"""Consume M1 authority plus independently observed scope; no live provider."""

from dataclasses import dataclass
from typing import Protocol

from ...common import fingerprint
from ..models import decode_json
from ..language_policy import AuthorityContext, AuthorityResult, UnavailableAuthority
from ..language_policy import AuthorityVerifier
from ..language_policy.authority import AuthorityStatus
from ..language_policy import DestinationEvidence
from ..language_policy.models import timestamp
from ..registry import require_hash
from .paths import fail, repository_key


# Logical capabilities for future draft staging, not OAuth/token scope names.
REQUIRED_PERMISSIONS = ("contents:read", "contents:write", "pull_requests:write")


@dataclass(frozen=True)
class DestinationFacts:
    """Trusted verifier output, never hydrated from contributor evidence JSON.

    Like M1 AuthorityContext this is not an authenticator. A real implementation
    must obtain facts independently; none is supplied. Synthetic tests instantiate
    it in the test tree, and can never produce real technical eligibility.
    """

    context: AuthorityContext
    repository_json: bytes
    owner_kind: str
    principal_id: int
    official_repository_id: int
    official_owner_id: int
    target_sha256: str
    inventory_sha256: str
    cohort_sha256: str
    permissions: tuple[str, ...]
    revocation_revision_sha256: str
    revocation_checked_at: str

    def __post_init__(self):
        if (type(self.context) is not AuthorityContext or type(self.repository_json) is not bytes
                or self.owner_kind not in {"user", "organization"} or type(self.permissions) is not tuple
                or any(type(p) is not str for p in self.permissions)
                or len(set(self.permissions)) != len(self.permissions)
                or any(type(n) is not int or n < 1 for n in (self.principal_id, self.official_repository_id, self.official_owner_id))):
            fail("trusted_facts_type")
        for value in (self.target_sha256, self.inventory_sha256, self.cohort_sha256, self.revocation_revision_sha256):
            require_hash(value)
        timestamp(self.revocation_checked_at)


class DestinationAuthority(AuthorityVerifier, Protocol):
    """Add independently observed facts to the unchanged M1 verify interface."""

    def observe(self, evidence: DestinationEvidence, context: AuthorityContext) -> DestinationFacts | None: ...


def consume(evidence, policy, inventory, cohort_sha256, context, verifier):
    """Only M1's unavailable/synthetic statuses exist; no implicit real success."""
    provider = verifier if verifier is not None else UnavailableAuthority()
    if context is not None and type(context) is not AuthorityContext:
        fail("authority_context_type")
    result = provider.verify(evidence, context)
    if type(result) is not AuthorityResult or result.evidence_sha256 != evidence.sha256:
        fail("authority_result")
    if result.status != AuthorityStatus.SYNTHETIC_ONLY:
        return result.status.value, False, None
    facts = provider.observe(evidence, context) if hasattr(provider, "observe") else None
    if type(facts) is not DestinationFacts or context is None or facts.context != context:
        return "unverifiable", False, None
    value = evidence.to_dict();claim = value["authorization"];target = value["target"]
    repo = decode_json(facts.repository_json)
    probe = value.copy() | {"target": target | {"repository": repo}}
    DestinationEvidence.from_dict(probe)
    expected = {"evidence_sha256": evidence.sha256, "subject_sha256": value["subject"]["sha256"],
        "destination_policy_sha256": policy.sha256, "target_sha256": fingerprint(target),
        **{k: claim[k] for k in ("assertion_sha256", "verification_context_sha256", "principal", "issuer", "issuer_version")}}
    scope = all(getattr(context, k) == v for k, v in expected.items())
    scope = scope and (facts.target_sha256 == context.target_sha256 and inventory is not None
        and facts.inventory_sha256 == inventory.sha256 == target["inventory_sha256"] and facts.cohort_sha256 == cohort_sha256
        and repository_key(repo) == repository_key(target["repository"])
        and set(REQUIRED_PERMISSIONS) <= set(facts.permissions)
        and claim["synthetic"] is True and claim["status"] == "verified"
        and claim["revocation"]["status"] == "clear"
        and facts.revocation_revision_sha256 == claim["revocation"]["revision_sha256"]
        and facts.revocation_checked_at == claim["revocation"]["checked_at"]
        and timestamp(claim["verified_at"]) <= timestamp(context.as_of)
        and timestamp(facts.revocation_checked_at) <= timestamp(context.as_of))
    if claim["expires_at"] is not None and timestamp(context.as_of) >= timestamp(claim["expires_at"]):
        return "expired", False, None
    if not scope:
        return "unverifiable", False, None
    # Policy official IDs must also match independent verifier facts. Names/URLs
    # play no role in identity; transfers to another owner invalidate the grant.
    official = policy.to_dict()["official_repository"]
    if (facts.official_repository_id, facts.official_owner_id) != (official["repository_id"], official["owner_id"]):
        return "unverifiable", False, None
    is_official = (repo["repository_id"], repo["owner_id"]) == (facts.official_repository_id, facts.official_owner_id)
    if not is_official and (facts.owner_kind != "user" or facts.principal_id != repo["owner_id"]):
        return "unverifiable", False, None
    observed = dict(repository=repo, owner_kind=facts.owner_kind, principal_id=facts.principal_id,
        official_repository_id=facts.official_repository_id, official_owner_id=facts.official_owner_id,
        target_sha256=facts.target_sha256, inventory_sha256=facts.inventory_sha256, cohort_sha256=facts.cohort_sha256,
        permissions=sorted(facts.permissions), revocation_revision_sha256=facts.revocation_revision_sha256,
        revocation_checked_at=facts.revocation_checked_at, authority_context_sha256=fingerprint(context.__dict__))
    return "synthetic-only", True, observed
