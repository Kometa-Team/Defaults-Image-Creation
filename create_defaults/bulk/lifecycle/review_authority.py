"""Explicit disposable synthetic attribution; no authenticated-success path.

Legacy TrustedDecision/SubmitterAttribution are not authenticators. Do not turn
those strings or a RegistrySnapshot into a complete-artwork review grant.
"""
from dataclasses import dataclass

from ..common import fingerprint
from .evidence import ReviewDecision, fail
from .previews import CompositionTrial


@dataclass(frozen=True)
class SyntheticGrant:
    record_sha256: str
    actor: str
    role: str
    context_sha256: str
    expires_at: int


class UnavailableReviewAuthority:
    def verify(self, record, *, root):
        fail('real_authority_unavailable')


class SyntheticReviewAuthority:
    """A lifetime-scoped test capability, never an OAuth/provider substitute.

    Independent role lists, exact record/scope grants, explicit logical as-of and
    revocation are supplied by controlled fixtures, never taken from request JSON.
    Even a positive result remains SYNTHETIC_ONLY and authenticated=False.
    """
    def __init__(self, trial, *, submitters, maintainers, as_of=0):
        if type(trial) is not CompositionTrial or trial._closed:
            fail('synthetic_trial_required')
        self.trial = trial
        self.roles = {'submitter': frozenset(submitters), 'maintainer': frozenset(maintainers)}
        if not all(self.roles.values()):
            fail('synthetic_roles_required')
        self.grants = {}
        self.revoked = set()
        self.as_of = as_of

    def authorize(self, record, *, actor, role, expires_at=100):
        if type(record) is not ReviewDecision or role not in self.roles or actor not in self.roles[role]:
            fail('independent_role_attribution')
        value = ReviewDecision.from_bytes(record.encoded).to_dict()
        if (value['actor'], value['role']) != (actor, role):
            fail('independent_role_attribution')
        if type(expires_at) is not int or expires_at < 0:
            fail('authority_expiry')
        grant = SyntheticGrant(record.sha256, actor, role, value['context_sha256'], expires_at)
        if record.sha256 in self.grants and self.grants[record.sha256] != grant:
            fail('authority_grant_replacement')
        self.grants[record.sha256] = grant
        return grant

    def revoke(self, record_sha256):
        self.revoked.add(record_sha256)

    def verify(self, record, *, root):
        if self.trial._closed or root != self.trial.config.cache_dir:
            fail('foreign_or_closed_authority')
        if type(self.as_of) is not int or self.as_of < 0 or type(record) is not ReviewDecision:
            fail('authority_context')
        value = ReviewDecision.from_bytes(record.encoded).to_dict()
        grant = self.grants.get(record.sha256)
        if type(grant) is not SyntheticGrant or (grant.record_sha256, grant.actor, grant.role, grant.context_sha256) != (
                record.sha256, value['actor'], value['role'], value['context_sha256']):
            fail('missing_exact_authority')
        if grant.actor not in self.roles.get(grant.role, ()):
            fail('role_revoked')
        if record.sha256 in self.revoked:
            fail('authority_revoked')
        if self.as_of >= grant.expires_at:
            fail('authority_expired')
        return dict(status='synthetic-only', authenticated=False,
            grant_sha256=fingerprint(grant.__dict__))


def verify_authority(authority, record, *, root):
    # No user-defined success callback, role flag or subclass can become trust.
    if type(authority) is not SyntheticReviewAuthority:
        return UnavailableReviewAuthority().verify(record, root=root)
    return authority.verify(record, root=root)


def require_operational_approval(*args, **kwargs):
    """Real authority/capture/integration and all contract grants are absent."""
    fail('real_authority_unavailable')
