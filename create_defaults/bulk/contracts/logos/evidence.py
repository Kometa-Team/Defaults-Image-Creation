"""Additive immutable preview/session evidence using M1 Document, not approvals."""

from ...common import BulkError
from ..adoption.models import encoded_json, read_canonical
from ..models import Document
from ..registry import require_hash


def closed(value, fields):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise BulkError("logo_evidence_shape", "Missing or unknown evidence fields")


class Evidence(Document):
    SCHEMA = "logo-evidence"

    @classmethod
    def make(cls, kind, payload):
        return cls.from_dict({"schema_version": 1, "kind": kind, "payload_json": encoded_json(payload)})

    def payload(self):
        return read_canonical(self.to_dict()["payload_json"])

    def _check(self, value):
        payload = read_canonical(value["payload_json"])
        kind = value["kind"]
        if kind == "isolated-logo-preview-receipt":
            closed(payload, "artifact_sha256 source_sha256 context_sha256 member_json transform_json runtime_json bytes preview_type")
            for key in ("artifact_sha256", "source_sha256", "context_sha256"): require_hash(payload[key])
            for key in ("member_json", "transform_json", "runtime_json"): read_canonical(payload[key])
            if type(payload["bytes"]) is not int or payload["bytes"] <= 0 or payload["preview_type"] not in {"logo_only", "complete_overlay"}:
                raise BulkError("logo_preview_receipt", "Invalid isolated preview receipt")
        elif kind == "logo-review-bundle":
            closed(payload, "spec_json request_json preview_json receipts_json source_reports_json comparison_json")
            for child in payload.values(): read_canonical(child)
        else:
            closed(payload, "id revision phase bundle_sha256 confirmation_sha256 decision_sha256 previous_sha256")
            if type(payload["id"]) is not str or not payload["id"] or type(payload["revision"]) is not int or payload["revision"] < 1:
                raise BulkError("logo_session", "Invalid session identity or revision")
            if payload["phase"] not in {"PREVIEWS_READY", "SUBMITTER_CONFIRMED", "SUBMITTER_REJECTED", "MAINTAINER_APPROVED", "MAINTAINER_REJECTED", "WITHDRAWN"}:
                raise BulkError("logo_session", "Unknown workflow phase")
            for key in ("bundle_sha256", "confirmation_sha256", "decision_sha256", "previous_sha256"):
                if payload[key] is not None: require_hash(payload[key])
