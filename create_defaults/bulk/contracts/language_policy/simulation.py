"""Explicit synthetic-only authority test adapter. Never a production provider."""

from ...common import fingerprint
from .authority import AuthorityContext, AuthorityResult, AuthorityStatus
from .models import DestinationEvidence, timestamp


class SyntheticAuthority:
    """Checks synthetic attribution, never asserts external authentication.

    There is no production mode, CLI toggle, registration or operational intake.
    A matching fixture always returns SYNTHETIC_ONLY with authorization false.
    """

    def verify(self, evidence, context=None):
        if type(evidence) is not DestinationEvidence:
            from ...common import BulkError
            raise BulkError("phase3_type", "Expected synthetic destination observation")
        def result(status):
            return AuthorityResult(status, evidence.sha256)
        if type(context) is not AuthorityContext:
            return result(AuthorityStatus.UNVERIFIABLE)
        value = evidence.to_dict()
        auth = value["authorization"]
        checks = [auth["synthetic"] is True, evidence.sha256 == context.evidence_sha256,
                  value["subject"]["sha256"] == context.subject_sha256,
                  value["destination_policy"]["sha256"] == context.destination_policy_sha256,
                  fingerprint(value["target"]) == context.target_sha256]
        checks.extend(auth[k] == getattr(context, k) for k in (
            "principal", "issuer", "issuer_version", "assertion_sha256", "verification_context_sha256"))
        if not all(checks):
            return result(AuthorityStatus.UNVERIFIABLE)
        if auth["status"] == "revoked" or auth["revocation"]["status"] == "revoked":
            return result(AuthorityStatus.REVOKED)
        if auth["status"] == "expired" or (auth["expires_at"] is not None and timestamp(context.as_of) >= timestamp(auth["expires_at"])):
            return result(AuthorityStatus.EXPIRED)
        if (auth["status"] != "verified" or auth["revocation"]["status"] != "clear"
                or timestamp(auth["verified_at"]) > timestamp(context.as_of)
                or timestamp(auth["revocation"]["checked_at"]) > timestamp(context.as_of)):
            return result(AuthorityStatus.UNVERIFIABLE)
        return result(AuthorityStatus.SYNTHETIC_ONLY)
