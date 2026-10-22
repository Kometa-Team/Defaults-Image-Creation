"""Additive canonical M1 documents; no alteration of existing receipt schemas."""

from datetime import datetime, timezone
from functools import lru_cache

from ...common import BulkError, canonical
from ..models import Document, MAX_BYTES, _json_value, _validator


STATES = ("IMPLEMENTED", "COMPATIBLE", "APPROVED", "READY", "ACTIVE", "SUSPENDED", "REVOKED")
GATES = ("exact_pins", "effective_coverage", "source_dependencies", "m4_review",
         "complete_design_previews", "required_outputs", "historical_compatibility",
         "fresh_evidence", "resolved_design", "approved_exceptions", "regression")


def instant(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
            raise ValueError("UTC required")
        return result
    except (ValueError, TypeError, AttributeError) as error:
        raise BulkError("activation_timestamp", "An explicit UTC decision timestamp is required") from error


def utc_now():
    return datetime.now(timezone.utc)


@lru_cache(maxsize=1)
def activation_validator():
    # Keep the additive schema outside M1's four-slot working cache. Do not
    # change the frozen M1 source pins merely to accommodate M7's extra type.
    return _validator("activation")


class ActivationDocument(Document):
    SCHEMA = "activation"

    def __init__(self, value):
        _json_value(value)
        encoded = canonical(value)
        if len(encoded) > MAX_BYTES:
            raise BulkError("activation_json", "Evidence exceeds the M1 parser bound")
        error = next(activation_validator().iter_errors(value),None)
        if error:
            raise BulkError("activation_schema", error.message)
        if value.get("kind") != self.KIND:
            raise BulkError("activation_kind", "Evidence cannot substitute another decision stage")
        self._check(value)
        object.__setattr__(self,"encoded",encoded)

    def _check(self, value):
        if "package" in value and (value["package"]["category"] == "Overlays") != (value["package"]["kind"] == "overlay"):
            raise BulkError("activation_package", "Poster and overlay package scope cannot be interchanged")
        if "decided_at" in value:
            if instant(value["expires_at"]) <= instant(value["decided_at"]):
                raise BulkError("activation_expiry", "Expiry must follow the decision")
        if value["kind"] == "activation-gate-evidence":
            if set(value["checks"]) != set(GATES):
                raise BulkError("activation_gates", "Every activation prerequisite must be explicit")
            if value["review_kind"] == "new-poster" and value["preview_type"] != "complete-poster":
                if value["checks"]["complete_design_previews"] == "passed":
                    raise BulkError("activation_composition", "Logo-only review cannot approve a new poster composition")
        if "production_enforcement" in value and value["production_enforcement"] is not False:
            raise BulkError("activation_isolation", "M7 has no production activation capability")


class Proposal(ActivationDocument):
    KIND = "activation-proposal"


class ApprovalBinding(ActivationDocument):
    KIND = "activation-contract-approval-binding"


class OperatorDecision(ActivationDocument):
    KIND = "activation-operator-decision"


class GateEvidence(ActivationDocument):
    KIND = "activation-gate-evidence"


class Revision(ActivationDocument):
    KIND = "activation-state-revision"


TYPES = {c.KIND: c for c in (Proposal, ApprovalBinding, OperatorDecision, GateEvidence, Revision)}


def read(raw):
    from ..models import decode_json
    value = decode_json(raw)
    cls = TYPES.get(value.get("kind")) if type(value) is dict else None
    if cls is None:
        raise BulkError("activation_document", "Unknown activation evidence type")
    return cls.from_dict(value)
