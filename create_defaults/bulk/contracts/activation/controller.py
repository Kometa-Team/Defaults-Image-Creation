"""No production authority adapter exists: real approvals remain blocked.

Only the explicitly synthetic harness can exercise approval/ACTIVE transitions.
Its decisions cannot name any implemented package or non-synthetic namespace.
An ACTIVE simulation is not an enforcement hook and cannot publish anything.
"""

from uuid import uuid4

from ...common import BulkError, Conflict
from ..models import ContractApproval
from .models import ApprovalBinding, GateEvidence, OperatorDecision, Proposal, Revision, instant, utc_now
from .storage import Archive


class UnavailableAuthority:
    synthetic = False

    def validate(self, *args, **kwargs):
        raise BulkError("authenticated_intake_unavailable", "No authenticated contract/activation decision source is integrated")


ALLOWED = {
    None: {"IMPLEMENTED"}, "IMPLEMENTED": {"COMPATIBLE","SUSPENDED","REVOKED"},
    "COMPATIBLE": {"APPROVED","SUSPENDED","REVOKED"},
    "APPROVED": {"READY","SUSPENDED","REVOKED"}, "READY": {"ACTIVE","SUSPENDED","REVOKED"},
    "ACTIVE": {"SUSPENDED","REVOKED"}, "SUSPENDED": {"COMPATIBLE","REVOKED"}, "REVOKED": set(),
}


class Controller:
    def __init__(self, root, *, simulation=None, clock=utc_now):
        # No generic runtime trust-provider injection or CLI --reviewer switch.
        # Replacing this boundary with a real adapter requires reviewed code.
        if simulation is not None:
            from .simulation import SyntheticAuthority
            if type(simulation) is not SyntheticAuthority:
                raise BulkError("activation_authority", "Only the test-only synthetic harness is available")
        self.authority = simulation if simulation is not None else UnavailableAuthority()
        self.archive = Archive(root)
        self.clock = clock
        self.runtime_id = "synthetic-runtime."+uuid4().hex if simulation else "isolated-runtime."+uuid4().hex

    def _fresh(self, proposal, gates, binding=None, operator=None):
        if type(proposal) is not Proposal or type(gates) is not GateEvidence:
            raise BulkError("activation_proposal", "Exact typed proposal and gate evidence required")
        p,g = proposal.to_dict(),gates.to_dict()
        if g["proposal_sha256"] != proposal.sha256:
            raise BulkError("activation_scope", "Gate evidence belongs to another proposal")
        self.authority.validate(proposal,gates,binding,operator,self.runtime_id,self.clock())
        return p,g

    def inspect(self, identity):
        history = self.archive.history(identity)
        if not history:
            return {"state":"IMPLEMENTED","revision":0,"production_enforcement":False,"publication_authorized":False,"blockers":["no_isolated_state"]}
        v = history[-1].to_dict();blockers = []
        effective = v["state"]
        if effective not in {"IMPLEMENTED","SUSPENDED","REVOKED"}:
            read = self.archive.contracts.read_object
            proposal = Proposal.from_bytes(read(v["proposal_sha256"]))
            gates = GateEvidence.from_bytes(read(v["gate_sha256"]))
            binding = ApprovalBinding.from_bytes(read(v["approval_sha256"])) if v["approval_sha256"] else None
            operator = OperatorDecision.from_bytes(read(v["operator_sha256"])) if v["operator_sha256"] else None
            try:
                self._fresh(proposal,gates,binding,operator if effective == "ACTIVE" else None)
                if effective in {"APPROVED","READY","ACTIVE"} and binding is None:
                    raise BulkError("activation_approval", "Approval missing")
                if effective in {"READY","ACTIVE"} and any(x != "passed" for x in gates.to_dict()["checks"].values()):
                    raise BulkError("activation_prerequisites", "Incomplete activation evidence")
                if effective == "ACTIVE" and operator is None:
                    raise BulkError("activation_operator", "Independent operator decision missing")
            except BulkError as error:
                blockers.append(error.code)
                effective = "REVOKED" if error.code == "activation_revoked" else "SUSPENDED"
        return {"state":effective,"recorded_state":v["state"],"revision":v["revision"],"sha256":history[-1].sha256,
            "blockers":blockers,"production_enforcement":False,"publication_authorized":False}

    def transition(self, proposal, gates, target, *, expected_revision, binding=None,
                   approval_record=None, operator=None, reason="explicit isolated transition", before_commit=None):
        if type(proposal) is not Proposal or type(gates) is not GateEvidence or gates.to_dict()["proposal_sha256"] != proposal.sha256:
            raise BulkError("activation_proposal", "A typed exact-bound proposal and gate report are required")
        if approval_record is not None and target != "APPROVED" or operator is not None and target != "ACTIVE":
            raise BulkError("activation_stage", "Decision records cannot be smuggled through a different transition")
        if binding is not None and target == "IMPLEMENTED":
            raise BulkError("activation_stage", "Implementation does not consume a contract approval")
        if type(expected_revision) is not int or expected_revision < 0:
            raise Conflict("Exact nonnegative state revision required")
        identity = proposal.to_dict()["id"]
        history = self.archive.history(identity)
        old = history[-1].to_dict() if history else None
        if len(history) != expected_revision:
            raise Conflict()
        phase = old["state"] if old else None
        if target not in ALLOWED.get(phase,set()):
            raise BulkError("activation_transition", "Invalid or skipped activation stage")
        if phase == "REVOKED":
            raise BulkError("activation_revoked", "Revocation cannot be undone by a snapshot")
        if old and old["proposal_sha256"] != proposal.sha256 and phase != "SUSPENDED":
            raise BulkError("activation_proposal_changed", "Suspend and revalidate a changed proposal")
        if old and old["approval_sha256"] and phase not in {"SUSPENDED","REVOKED"} and target != "REVOKED":
            if self.inspect(identity)["state"] == "REVOKED":
                raise BulkError("activation_revoked", "Record revocation before any other transition")
        documents = [proposal,gates]
        read = self.archive.contracts.read_object
        if binding is None and old and old["approval_sha256"] and old["proposal_sha256"] == proposal.sha256:
            binding = ApprovalBinding.from_bytes(read(old["approval_sha256"]))
        if target not in {"IMPLEMENTED","SUSPENDED","REVOKED"}:
            _,g = self._fresh(proposal,gates,binding,operator if target == "ACTIVE" else None)
            if target == "COMPATIBLE" and g["checks"]["historical_compatibility"] != "passed":
                raise BulkError("activation_compatibility", "Historical compatibility missing")
            if target in {"APPROVED","READY","ACTIVE"} and binding is None:
                raise BulkError("activation_approval", "Exact contract approval missing")
            if target in {"READY","ACTIVE"} and any(value != "passed" for value in g["checks"].values()):
                raise BulkError("activation_prerequisites", "Every prerequisite must pass")
            if target == "APPROVED":
                if type(approval_record) is not ContractApproval or binding.to_dict()["record_sha256"] != approval_record.sha256:
                    raise BulkError("activation_approval", "Exact typed M1 receipt must be archived atomically")
            if target == "ACTIVE" and operator is None:
                raise BulkError("activation_operator", "Independent operator activation decision missing")
        if binding:documents.append(binding)
        if operator:documents.append(operator)
        revision = Revision.from_dict({"schema_version":1,"kind":Revision.KIND,"id":identity,
            "revision":expected_revision+1,"previous_sha256":history[-1].sha256 if history else None,
            "state":target,"proposal_sha256":proposal.sha256,"gate_sha256":gates.sha256,
            "approval_sha256":binding.sha256 if binding else None,"operator_sha256":operator.sha256 if operator else None,
            "restored_from_sha256":None,"reason":reason,"production_enforcement":False})
        def final_check():
            if before_commit is not None:
                before_commit()
            if target not in {"IMPLEMENTED","SUSPENDED","REVOKED"}:
                self._fresh(proposal,gates,binding,operator if target == "ACTIVE" else None)
        return self.archive.commit(revision,documents,approval_record=approval_record,before_commit=final_check)

    def reconcile(self, identity, *, expected_revision):
        """Persist a fail-closed suspension/revocation; no evidence is deleted."""
        status = self.inspect(identity)
        if status["revision"] != expected_revision:
            raise Conflict()
        if status["state"] == status.get("recorded_state"):
            return status
        old = self.archive.history(identity)[-1].to_dict();read = self.archive.contracts.read_object
        return self.transition(Proposal.from_bytes(read(old["proposal_sha256"])),GateEvidence.from_bytes(read(old["gate_sha256"])),
            status["state"],expected_revision=expected_revision,reason=",".join(status["blockers"]))

    def rollback(self, identity, *, expected_revision, restore_sha256):
        """Restore an earlier registry/proposal selection into SUSPENDED only."""
        history = self.archive.history(identity)
        if len(history) != expected_revision or not history:
            raise Conflict()
        if self.inspect(identity)["state"] == "REVOKED":
            raise BulkError("activation_revoked", "A prior snapshot cannot restore revoked authority")
        chosen = next((r for r in history if r.sha256 == restore_sha256),None)
        if chosen is None:
            raise BulkError("activation_restore", "Restore target must be in this verified immutable stream")
        value = chosen.to_dict()
        value.update(revision=expected_revision+1,previous_sha256=history[-1].sha256,state="SUSPENDED",
            operator_sha256=None,restored_from_sha256=chosen.sha256,reason="explicit rollback to inactive registry/proposal; retained history")
        return self.archive.commit(Revision.from_dict(value))
