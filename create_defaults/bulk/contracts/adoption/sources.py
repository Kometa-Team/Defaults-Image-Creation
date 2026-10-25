"""Pinned local snapshots and verbatim historical JSON; no network or Store."""

from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path

from ci.dependency_maintenance import selected_hash

from ...asset_cases import canonical as canonical_asset
from ...common import BulkError, canonical, confined, fingerprint
from ...config import ROOT
from ...library_sources import check_seal
from ..models import decode_json, read_json_bytes
from .models import equal, mismatch


HERE = Path(__file__).parent
# Release pins; changing these is an explicit source change, never a force flag.
SOURCE_PINS_SHA256 = "b2006d1b1327bad2db15054871b3155d704a9c8a14a6efa651a3f90231d147e3"
MAX_EVIDENCE_BYTES = 8 * 1024 * 1024


def load_pins():
    value = decode_json(read_json_bytes(HERE / "source-pins-v1.json"))
    equal(SOURCE_PINS_SHA256, fingerprint(value), category="snapshot", identity="source-pins-v1",
          path="source-pins-v1.json", code="adoption_snapshot_pin")
    return value


def verify_sources(pins, source_root=ROOT.parent):
    """Check the exact approved source scope before invoking discovery code."""
    for item in pins["files"]:
        try:
            path = confined(source_root, item["path"], must_exist=True)
            raw = path.read_bytes()
        except (BulkError, OSError) as error:
            mismatch("adoption_source_drift", "snapshot", pins["source_commit"], item["path"], item["sha256"], str(error))
        if item["text_lf"]:
            raw = raw.replace(b"\r\n", b"\n")
        equal(selected_hash(item["path"], item["sha256"]), hashlib.sha256(raw).hexdigest(), category="snapshot", identity=pins["source_commit"],
              path=item["path"], code="adoption_source_drift")


def load_history(pins):
    """Exact original JSON bytes are gzip-wrapped; original seals are unchanged."""
    root = HERE / "evidence"
    index = decode_json(read_json_bytes(root / "index-v1.json"))
    equal(pins["history_index_sha256"], fingerprint(index), category="history", identity="index-v1",
          path="evidence/index-v1.json", code="adoption_history_pin")
    documents, native, responses = {}, {}, {}
    for binding in index["files"]:
        path = confined(root, binding["path"], must_exist=True)
        equal(binding["file_sha256"], hashlib.sha256(path.read_bytes()).hexdigest(), category="history",
              identity=binding["origin"], path=binding["path"], code="adoption_history_pin")
        with gzip.open(path, "rb") as stream:
            raw = stream.read(MAX_EVIDENCE_BYTES + 1)
        if len(raw) > MAX_EVIDENCE_BYTES:
            raise BulkError("adoption_evidence_limit", "Historical evidence page exceeds the bounded parser limit")
        equal(binding["raw_sha256"], hashlib.sha256(raw).hexdigest(), category="history", identity=binding["origin"], path=binding["path"], code="adoption_history_pin")
        value = decode_json(raw)
        equal(binding["canonical_sha256"], fingerprint(value), category="history", identity=binding["origin"], path=binding["path"])
        key = path.name.removesuffix(".json.gz")
        if binding["kind"] == "native-page":
            for row in value["rows"]:
                identity = row["job"]["id"]
                if identity in native:
                    mismatch("adoption_duplicate", "native", identity, binding["path"], "unique", identity)
                native[identity] = row | {"native_report_sha256": value["native_report_sha256"],
                                          "state_sha256": value["state_sha256"], "output_root": value["output_root"]}
        elif binding["kind"] == "response-page":
            for original in value["records_utf8"]:
                response = check_seal(decode_json(original.encode("utf-8")))
                destination = response["destination"]
                if destination in responses:
                    mismatch("adoption_duplicate", "production", destination, binding["path"], "unique", destination)
                responses[destination] = response
        else:
            documents[key] = check_seal(value) if "sha256" in value else value
    return documents, native, responses


def approval_index(documents):
    """Historical candidate-bound decisions, never current publication authority."""
    result = {}
    for group in ("group-a", "group-b", "individual", "overlay"):
        manifest = documents[group + "-candidate-manifest"]
        receipt = documents[group + ("-approval-receipt" if group == "overlay" else "-maintainer-approval-receipt")]
        policy_key = {"group-a": "approved-visual-policy", "group-b": "approved-warning-policy",
                      "individual": "approved-individual-policy", "overlay": "proposed-policy"}[group]
        policy = documents[group + "-" + policy_key]
        # Some policy files have no envelope; their complete canonical hash is
        # the pin. An existing seal is payload integrity, not a new decision.
        policy_hash = policy.get("sha256", fingerprint(policy))
        if policy_hash != manifest["policy_sha256"]:
            policy_hash = fingerprint(policy)
        for path, expected, actual in (
            ("candidate_manifest_sha256", manifest["sha256"], receipt["candidate_manifest_sha256"]),
            ("policy_sha256", manifest["policy_sha256"], receipt["policy_sha256"]),
            ("policy", manifest["policy_sha256"], policy_hash),
            ("decision", "approved", receipt["decision"]),
        ):
            equal(expected, actual, category="history", identity=group, path=path, code="adoption_approval_binding")
        if receipt["reviewer"] != "bullmoose20":
            mismatch("adoption_approval_binding", "history", group, "reviewer", "preserved original maintainer", receipt["reviewer"])
        receipt_members = {m["destination"]: m for m in receipt.get("members", [])}
        if group != "overlay":
            equal({m["destination"] for m in manifest["members"]}, set(receipt_members), category="history", identity=group, path="members")
        for member in manifest["members"]:
            destination = member["destination"]
            candidate = member.get("candidate_sha256", member.get("sha256"))
            if group != "overlay":
                equal(candidate, receipt_members[destination]["candidate_sha256"], category="history", identity=group, path=destination)
            if destination in result:
                mismatch("adoption_approval_overlap", "history", group, destination, "one migration population", result[destination]["population"])
            result[destination] = {"population": group, "candidate_sha256": candidate,
                "record_sha256": receipt["sha256"], "member_sha256": fingerprint(member),
                "scope": {"group-a": "renderer_equivalent_population", "group-b": "renderer_equivalent_population",
                          "individual": "individual_font_or_visual", "overlay": "approved_overlay_membership"}[group]}
    return result
