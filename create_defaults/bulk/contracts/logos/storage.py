"""Restart-safe D09 state transitions on M1's isolated Package E Store only."""

from ...common import BulkError, Conflict, atomic_bytes, confined, fingerprint, sha256
from ..adoption.models import read_canonical
from ..models import ExceptionDecision, SubmitterConfirmation
from ..registry import TrustedDecision, require_hash
from ..state import ContractStore
from .assets import inspect_png
from .evidence import Evidence
from .workflow import Prepared, SubmitterAttribution, approvable, confirm_record, decision_record, verify


DDL = (
    "CREATE TABLE contract_logo_schema (version INTEGER NOT NULL)",
    "INSERT INTO contract_logo_schema VALUES (1)",
    "CREATE TABLE contract_logo_revisions (id TEXT NOT NULL, revision INTEGER NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(id,revision))",
    "CREATE TRIGGER contract_logo_no_update BEFORE UPDATE ON contract_logo_revisions BEGIN SELECT RAISE(ABORT,'immutable logo review'); END",
    "CREATE TRIGGER contract_logo_no_delete BEFORE DELETE ON contract_logo_revisions BEGIN SELECT RAISE(ABORT,'immutable logo review'); END",
)


class LogoArchive:
    def __init__(self, root):
        self.contracts = ContractStore(root)
        with self.contracts._store.transaction() as db:
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'contract_logo_%'")}
            expected = {"contract_logo_schema", "contract_logo_revisions", "contract_logo_no_update", "contract_logo_no_delete"}
            if not names:
                for statement in DDL: db.execute(statement)
            elif names != expected or [tuple(r) for r in db.execute("SELECT version FROM contract_logo_schema")] != [(1,)]:
                raise BulkError("logo_state_schema", "Incomplete/unsupported sidecar; no automatic repair")

    def _artifact(self, checksum):
        return confined(self.contracts.root, "logo-artifacts/"+require_hash(checksum)+".png")

    def _read_artifact(self, checksum):
        path = self._artifact(checksum)
        if not path.is_file() or sha256(path) != checksum:
            raise BulkError("logo_artifact_corrupt", "Missing/corrupt immutable preview or source evidence")
        return path.read_bytes()

    def _latest(self, identity):
        with self.contracts._store.connection() as db:
            row = db.execute("SELECT revision,sha256 FROM contract_logo_revisions WHERE id=? ORDER BY revision DESC LIMIT 1", (identity,)).fetchone()
        return dict(row) if row else None

    def _read(self, identity, expected_sha256):
        row = self._latest(identity)
        if not row or row["sha256"] != require_hash(expected_sha256):
            raise Conflict("Review changed or exact snapshot pin is missing")
        snapshot = Evidence.from_bytes(self.contracts.read_object(row["sha256"]))
        value = snapshot.payload()
        if snapshot.to_dict()["kind"] != "logo-review-session" or value["id"] != identity or value["revision"] != row["revision"]:
            raise BulkError("logo_state_corrupt", "State index and immutable snapshot disagree")
        with self.contracts._store.connection() as db:
            previous = db.execute("SELECT sha256 FROM contract_logo_revisions WHERE id=? AND revision=?", (identity, value["revision"]-1)).fetchone()
        if value["previous_sha256"] != (previous["sha256"] if previous else None):
            raise BulkError("logo_state_corrupt", "Broken immutable session chain")
        bundle = Evidence.from_bytes(self.contracts.read_object(value["bundle_sha256"]))
        if bundle.to_dict()["kind"] != "logo-review-bundle":
            raise BulkError("logo_state_corrupt", "Session points to wrong evidence kind")
        payload = bundle.payload()
        spec = read_canonical(payload["spec_json"])
        hashes = {r["sha256"] for r in spec["sources"].values() if r is not None}
        for encoded in read_canonical(payload["receipts_json"]).values():
            receipt = Evidence.from_dict(encoded)
            if self.contracts.read_object(receipt.sha256) != receipt.encoded:
                raise BulkError("logo_state_corrupt", "Receipt blob missing or substituted")
            hashes.add(receipt.payload()["artifact_sha256"])
        prepared = Prepared(bundle, tuple((h, self._read_artifact(h)) for h in sorted(hashes)))
        return snapshot, prepared

    def load(self, identity, *, expected_sha256, selection, source_root, trusted_submitters=None, trusted_maintainers=None):
        snapshot, prepared = self._read(identity, expected_sha256)
        spec, request, preview = verify(prepared, selection, source_root)
        value = snapshot.payload()
        phase = value["phase"]
        confirmation = decision = None
        if value["confirmation_sha256"] is not None:
            confirmation = SubmitterConfirmation.from_bytes(self.contracts.read_object(value["confirmation_sha256"]))
            actor = (trusted_submitters or {}).get(confirmation.sha256)
            if not isinstance(actor, SubmitterAttribution) or actor.actor != spec["submitter"] or confirm_record(prepared, actor, confirmation.to_dict()["decision"]) != confirmation:
                raise BulkError("logo_untrusted_submitter", "No matching external attribution for this exact confirmation")
        if value["decision_sha256"] is not None:
            decision = ExceptionDecision.from_bytes(self.contracts.read_object(value["decision_sha256"]))
            actor = (trusted_maintainers or {}).get(decision.sha256)
            if (not isinstance(actor, TrustedDecision) or actor.actor == spec["submitter"] or confirmation is None
                    or confirmation.to_dict()["decision"] != "approved"
                    or decision_record(prepared, confirmation, actor, decision.to_dict()["decision"]) != decision):
                raise BulkError("logo_untrusted_maintainer", "Separate actual maintainer attribution and confirmed exact previews required")
        if phase == "PREVIEWS_READY" and (confirmation or decision):
            raise BulkError("logo_phase", "Pending review cannot carry approval records")
        if phase in {"SUBMITTER_CONFIRMED", "SUBMITTER_REJECTED", "WITHDRAWN"}:
            expected = "approved" if phase == "SUBMITTER_CONFIRMED" else "rejected"
            if confirmation is None or confirmation.to_dict()["decision"] != expected or decision is not None:
                raise BulkError("logo_phase", "Submitter phase is not supported by exact current evidence")
        if phase.startswith("MAINTAINER_"):
            expected = "approved" if phase == "MAINTAINER_APPROVED" else "rejected"
            if decision is None or decision.to_dict()["decision"] != expected:
                raise BulkError("logo_phase", "Maintainer phase is not supported by exact decision evidence")
            if expected == "approved": approvable(prepared, selection, source_root)
        return snapshot, prepared

    def _commit(self, identity, expected_revision, prepared, phase, confirmation=None, decision=None):
        if type(expected_revision) is not int or expected_revision < 0:
            raise BulkError("logo_revision", "Exact nonnegative expected revision required")
        previous = None
        with self.contracts._store.connection() as db:
            row = db.execute("SELECT sha256 FROM contract_logo_revisions WHERE id=? AND revision=?", (identity, expected_revision)).fetchone()
            if row: previous = row["sha256"]
        snapshot = Evidence.make("logo-review-session", {"id":identity,"revision":expected_revision+1,"phase":phase,
            "bundle_sha256":prepared.bundle.sha256,"confirmation_sha256":confirmation.sha256 if confirmation else None,
            "decision_sha256":decision.sha256 if decision else None,"previous_sha256":previous})
        # Verify/write every dependency BEFORE a transaction can expose a pointer.
        for checksum, raw in prepared.artifacts:
            if inspect_png(raw).sha256 != checksum:
                raise BulkError("logo_artifact_corrupt", "Artifact bytes differ from the supplied immutable hash")
            try: atomic_bytes(self._artifact(checksum), raw)
            except FileExistsError:
                if self._read_artifact(checksum) != raw: raise BulkError("logo_artifact_corrupt", "Artifact conflict")
        documents = [prepared.bundle, snapshot]
        documents += [Evidence.from_dict(v) for v in read_canonical(prepared.bundle.payload()["receipts_json"]).values()]
        if confirmation is not None: documents.append(confirmation)
        if decision is not None: documents.append(decision)
        for document in documents: self.contracts._write_blob(document)
        with self.contracts._store.transaction() as db:
            current = db.execute("SELECT revision,sha256 FROM contract_logo_revisions WHERE id=? ORDER BY revision DESC LIMIT 1", (identity,)).fetchone()
            observed = current["revision"] if current else 0
            if observed == expected_revision+1 and current["sha256"] == snapshot.sha256:
                return snapshot  # Exact idempotent retry, no second event.
            if observed != expected_revision or (current["sha256"] if current else None) != previous:
                raise Conflict("Stale or concurrently changed logo-review revision")
            db.execute("INSERT INTO contract_logo_revisions VALUES (?,?,?)", (identity, snapshot.payload()["revision"], snapshot.sha256))
            self.contracts._store.event(db,"logo_review_transition",identity,{"revision":expected_revision+1,"phase":phase,"sha256":snapshot.sha256,"publication_authorized":False})
        return snapshot

    def start(self, identity, prepared, *, expected_revision, selection, source_root):
        verify(prepared, selection, source_root)
        old = self._latest(identity)
        if old and old["revision"] != expected_revision:
            # An exact initial/revision retry is safe only after checking blobs,
            # not by silently repairing missing committed evidence.
            previous, previous_review = self._read(identity, old["sha256"])
            if previous.payload()["phase"] == "PREVIEWS_READY" and previous_review == prepared and old["revision"] == expected_revision+1:
                return previous
            raise Conflict()
        if old:
            _, previous_review = self._read(identity, old["sha256"])
            old_request = read_canonical(previous_review.bundle.payload()["request_json"])
            new_request = read_canonical(prepared.bundle.payload()["request_json"])
            if new_request["id"] != old_request["id"] or new_request["revision"] != old_request["revision"]+1:
                raise Conflict("Material revisions must advance the immutable request revision once")
        return self._commit(identity,expected_revision,prepared,"PREVIEWS_READY")

    def submit(self, identity, record, *, expected_sha256, expected_revision, selection, source_root, attribution, withdraw=False):
        if not isinstance(record,SubmitterConfirmation) or not isinstance(attribution,SubmitterAttribution):
            raise BulkError("logo_untrusted_submitter","Typed record and external submitter attribution required")
        current=self._latest(identity)
        if current and current["sha256"]!=expected_sha256:
            retry,_=self.load(identity,expected_sha256=current["sha256"],selection=selection,source_root=source_root,
                              trusted_submitters={record.sha256:attribution})
            phase="WITHDRAWN" if withdraw else "SUBMITTER_CONFIRMED" if record.to_dict()["decision"]=="approved" else "SUBMITTER_REJECTED"
            value=retry.payload()
            if (value["revision"]==expected_revision+1 and value["previous_sha256"]==expected_sha256
                    and value["confirmation_sha256"]==record.sha256 and value["phase"]==phase):
                return retry
            raise Conflict()
        snapshot, prepared = self.load(identity,expected_sha256=expected_sha256,selection=selection,source_root=source_root)
        spec, _, _ = verify(prepared,selection,source_root)
        if snapshot.payload()["revision"] != expected_revision or snapshot.payload()["phase"] != "PREVIEWS_READY": raise Conflict()
        if not isinstance(record,SubmitterConfirmation) or not isinstance(attribution,SubmitterAttribution) or attribution.actor != spec["submitter"] or confirm_record(prepared,attribution,record.to_dict()["decision"]) != record:
            raise BulkError("logo_untrusted_submitter","An exact externally attributed submitter decision is required")
        if withdraw and record.to_dict()["decision"] != "rejected": raise BulkError("logo_withdrawal","Withdrawal requires an explicit rejection of the pending request")
        phase = "WITHDRAWN" if withdraw else "SUBMITTER_CONFIRMED" if record.to_dict()["decision"] == "approved" else "SUBMITTER_REJECTED"
        return self._commit(identity,expected_revision,prepared,phase,record)

    def maintain(self, identity, record, *, expected_sha256, expected_revision, selection, source_root, submitter_attribution, attribution):
        if not isinstance(record,ExceptionDecision) or not isinstance(attribution,TrustedDecision):
            raise BulkError("logo_untrusted_maintainer","Typed record and external maintainer attribution required")
        current=self._latest(identity)
        if current and current["sha256"]!=expected_sha256:
            prior,_=self._read(identity,current["sha256"])
            retry,_=self.load(identity,expected_sha256=current["sha256"],selection=selection,source_root=source_root,
                trusted_submitters={prior.payload()["confirmation_sha256"]:submitter_attribution},trusted_maintainers={record.sha256:attribution})
            value=retry.payload()
            if (value["revision"]==expected_revision+1 and value["previous_sha256"]==expected_sha256 and value["decision_sha256"]==record.sha256):
                return retry
            raise Conflict()
        old,_ = self._read(identity,expected_sha256)
        snapshot,prepared = self.load(identity,expected_sha256=expected_sha256,selection=selection,source_root=source_root,
                                     trusted_submitters={old.payload()["confirmation_sha256"]:submitter_attribution})
        spec,_,_ = verify(prepared,selection,source_root)
        if snapshot.payload()["revision"] != expected_revision or snapshot.payload()["phase"] != "SUBMITTER_CONFIRMED": raise Conflict()
        confirmation = SubmitterConfirmation.from_bytes(self.contracts.read_object(snapshot.payload()["confirmation_sha256"]))
        if (not isinstance(record,ExceptionDecision) or not isinstance(attribution,TrustedDecision) or attribution.actor == spec["submitter"]
                or decision_record(prepared,confirmation,attribution,record.to_dict()["decision"]) != record):
            raise BulkError("logo_untrusted_maintainer","Distinct, allowlisted and externally attributed maintainer required")
        if record.to_dict()["decision"] == "approved": approvable(prepared,selection,source_root)
        phase = "MAINTAINER_APPROVED" if record.to_dict()["decision"] == "approved" else "MAINTAINER_REJECTED"
        return self._commit(identity,expected_revision,prepared,phase,confirmation,record)


def status(snapshot, prepared):
    value = snapshot.payload()
    spec = read_canonical(prepared.bundle.payload()["spec_json"])
    phase = value["phase"]
    return {"phase":phase,"source_validation":"integrity_checked_policy_and_quality_separate",
        "preview_completeness":spec["preview_type"],"submitter_confirmation":phase in {"SUBMITTER_CONFIRMED","MAINTAINER_APPROVED","MAINTAINER_REJECTED"},
        "maintainer_logo_design_approval":phase == "MAINTAINER_APPROVED",
        "contract_compatibility":"fixture_only" if spec["fixture_only"] else "M5_effective_job_gate_not_implemented",
        "artifact_review":"separate_future_gate","publication_staging_authorized":False,"merge_authorized":False,
        "transparent_exception_accepted":phase == "MAINTAINER_APPROVED" and "intentional_background" in spec["exceptions"],
        "operational_addition_eligible":False}
