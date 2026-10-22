"""Explicitly test-only authority. Never accepts an implemented contract.

These JSON decisions simulate principals; they do not authenticate anyone. The
real controller has a blocked boundary, not a configurable reviewer allowlist.
"""

from dataclasses import dataclass
from datetime import timedelta

from ...common import BulkError, canonical, fingerprint
from ..models import Contract, ContractApproval, RegistryDocument
from ..registry import package_reference
from ..expanded.graph import Snapshot
from .models import ApprovalBinding, GateEvidence, OperatorDecision, Proposal, GATES, instant, utc_now
from .impact import assess


@dataclass(frozen=True)
class FixtureBlob:
    encoded: bytes

    @property
    def sha256(self):
        import hashlib
        return hashlib.sha256(self.encoded).hexdigest()


class SyntheticAuthority:
    synthetic = True

    def __init__(self, contract, graph, *, now=None):
        c = contract.to_dict()
        if c["provenance"]["source"] != "synthetic-m7-fixture" or c["owner"] != "synthetic-maintainer":
            raise BulkError("activation_synthetic", "Simulation requires a synthetic contract and principal")
        from ..categories.release import RELEASE_SHA256, ROOT
        from ..categories.models import Release
        from ..models import read_json_bytes
        # A synthetic marker cannot reclassify a real implemented package.
        implemented = Release.from_bytes(read_json_bytes(ROOT/"categories/data/release-v1.json"))
        if implemented.sha256 != RELEASE_SHA256 or contract.sha256 in {p["contract_sha256"] for p in implemented.to_dict()["entries"]}:
            raise BulkError("activation_synthetic", "Real contract packages cannot enter simulation")
        self.now = now or utc_now();self.contract = contract;self.graph = graph;self.current_graph = graph
        self.revoked = set();self.events = {};self.read_object = None
        self.category = c["category"]
        self.members = sorted(i for i,o in graph.index().outputs.items() if o["category"] == self.category)
        if not self.members or any(not i.startswith("synthetic.") for i in graph.index().outputs):
            raise BulkError("activation_synthetic", "Only synthetic output identities are permitted")
        self.compatibility = FixtureBlob(canonical({"kind":"synthetic-compatibility","members":self.members,
            "contract_sha256":contract.sha256,"material_sha256":self.material(graph),"compatible":True}))
        self.adoption = FixtureBlob(canonical({"kind":"synthetic-adoption","members":self.members}))
        self.record = ContractApproval.from_dict({"schema_version":1,"kind":"contract-approval","id":"synthetic.approval."+self.compatibility.sha256[:16],"revision":1,
            "provenance":{"actor":"synthetic-maintainer","role":"maintainer","source":"synthetic-m7-fixture","evidence_sha256":self.compatibility.sha256},
            "package":package_reference(contract),"decision":"approved","scope":"category-contract"})
        self.registry = RegistryDocument.from_dict({"schema_version":1,"kind":"category-contract-registry","id":"synthetic.registry","version":"1.0.0",
            "owner":"synthetic-maintainer","provenance":c["provenance"],"entries":[{"package":package_reference(contract),
            "variants":[v["id"] for v in c["variants"]],"approval_sha256":self.record.sha256,"adoption_sha256":[]}]})
        self.proposal = Proposal.from_dict({"schema_version":1,"kind":Proposal.KIND,"id":"synthetic."+self.category.lower(),
            "package":package_reference(contract),"registry_sha256":self.registry.sha256,"compatibility_sha256":self.compatibility.sha256,
            "source_commit":"0"*40,"adoption_sha256":self.adoption.sha256,"graph_sha256":graph.sha256,
            "material_sha256":self.material(graph),"namespace":"synthetic"})
        self.gates = GateEvidence.from_dict({"schema_version":1,"kind":GateEvidence.KIND,"proposal_sha256":self.proposal.sha256,
            "checks":{g:"passed" for g in GATES},"proofs":[self.compatibility.sha256,self.adoption.sha256],
            "review_kind":"historical","preview_type":"retained-historical"})
        self.objects = {o.sha256:o for o in (contract,self.registry,self.record,self.compatibility,self.adoption,graph)}

    def material(self, graph):
        index = graph.index()
        if set(self.members) != {i for i,o in index.outputs.items() if o["category"] == self.category}:
            raise BulkError("activation_membership", "Complete selected output membership changed")
        return fingerprint({i:index.material_context(i) for i in self.members})

    def attach(self, controller):
        self.read_object = controller.archive.contracts.read_object
        for document in self.objects.values():
            # The M1 approval is not indexed until its state/record/event commit.
            controller.archive.contracts._write_blob(document)

    def approve(self, **changes):
        value = {"schema_version":1,"kind":ApprovalBinding.KIND,"id":self.proposal.to_dict()["id"],"package":package_reference(self.contract),
            "registry_sha256":self.registry.sha256,"compatibility_sha256":self.compatibility.sha256,
            "record_sha256":self.record.sha256,"review_evidence":[self.compatibility.sha256],"scope":"category-contract","decision":"approved",
            "actor":"synthetic-maintainer","event_id":"synthetic.contract-decision","auth_context_sha256":fingerprint("synthetic-maintainer-session"),
            "decided_at":self.now.isoformat(),"expires_at":(self.now+timedelta(hours=1)).isoformat()}
        value.update(changes);binding = ApprovalBinding.from_dict(value)
        self._register(value["event_id"],binding.sha256)
        return binding

    def operate(self, controller, binding, **changes):
        value = {"schema_version":1,"kind":OperatorDecision.KIND,"proposal_sha256":self.proposal.sha256,"approval_sha256":binding.sha256,
            "gate_sha256":self.gates.sha256,"runtime_id":controller.runtime_id,"scope":"isolated-enforcement-activation","decision":"approved",
            "actor":"synthetic-operator","event_id":"synthetic.operator."+controller.runtime_id,
            "auth_context_sha256":fingerprint("synthetic-operator-session"),"decided_at":self.now.isoformat(),"expires_at":(self.now+timedelta(hours=1)).isoformat()}
        value.update(changes);decision = OperatorDecision.from_dict(value)
        self._register(value["event_id"],decision.sha256)
        return decision

    def _register(self, identity, checksum):
        if identity in self.events and self.events[identity] != checksum:
            raise BulkError("activation_event_reuse", "An immutable decision event cannot be reassigned")
        self.events[identity]=checksum

    def _decision(self, document, now):
        v = document.to_dict()
        if v["event_id"] in self.revoked or v["actor"] in self.revoked:
            raise BulkError("activation_revoked", "Synthetic decision/authority revoked")
        if self.events.get(v["event_id"]) != document.sha256:
            raise BulkError("activation_forged", "No independently supplied synthetic decision attribution")
        session = "synthetic-operator-session" if type(document) is OperatorDecision else "synthetic-maintainer-session"
        if v["auth_context_sha256"] != fingerprint(session):
            raise BulkError("activation_auth_context", "Decision no longer matches the current synthetic authorization context")
        if not instant(v["decided_at"]) <= now < instant(v["expires_at"]):
            raise BulkError("activation_expired", "Decision is expired or not yet valid")

    def validate(self, proposal, gates, binding, operator, runtime_id, now):
        if proposal != self.proposal or proposal.to_dict()["namespace"] != "synthetic":
            raise BulkError("activation_scope", "Contract/category/source/registry/proposal substituted")
        if gates != self.gates:
            raise BulkError("activation_gates", "Submitted booleans are not validated evidence")
        if binding is not None:
            if type(binding) is not ApprovalBinding:
                raise BulkError("activation_forged", "Typed approval binding required")
            self._decision(binding,now)
        impact = assess(self.graph,self.current_graph)
        if not impact["impact_complete"] or self.material(self.current_graph) != proposal.to_dict()["material_sha256"]:
            raise BulkError("activation_material_changed", "M5 scope is changed or unresolved")
        if self.read_object is None:
            raise BulkError("activation_evidence", "Fixture archive is not attached")
        for checksum,document in self.objects.items():
            if self.read_object(checksum) != document.encoded:
                raise BulkError("activation_evidence", "Missing or corrupted exact fixture evidence")
        if binding is not None:
            if type(binding) is not ApprovalBinding:
                raise BulkError("activation_forged", "Typed approval binding required")
            self._decision(binding,now);b = binding.to_dict();p = proposal.to_dict()
            if any(b[k] != p[k] for k in ("id","package","registry_sha256","compatibility_sha256")) or b["record_sha256"] != self.record.sha256 or b["review_evidence"] != [self.compatibility.sha256] or b["actor"] != "synthetic-maintainer":
                raise BulkError("activation_approval_scope", "Contract approval context or maintainer differs")
        if operator is not None:
            if type(operator) is not OperatorDecision or binding is None:
                raise BulkError("activation_operator", "Independent operational decision required")
            self._decision(operator,now);o = operator.to_dict()
            if o["actor"] != "synthetic-operator" or o["actor"] == binding.to_dict()["actor"] or o["event_id"] == binding.to_dict()["event_id"]:
                raise BulkError("activation_roles", "Decision stages and principals must remain independent")
            if (o["proposal_sha256"],o["approval_sha256"],o["gate_sha256"]) != (proposal.sha256,binding.sha256,gates.sha256):
                raise BulkError("activation_operator_scope", "Operational decision names other evidence")
            if o["runtime_id"] != runtime_id:
                raise BulkError("activation_restart", "Restart requires a fresh explicit operational decision")


def fixture_authority():
    """JSON-only fixture factory; no real package or authentication adapter."""
    h = fingerprint("synthetic-m7")
    contract = Contract.from_dict({"schema_version":1,"category":"Overlays","kind":"overlay","version":"1.0.0",
        "owner":"synthetic-maintainer","provenance":{"actor":"synthetic-maintainer","role":"maintainer","source":"synthetic-m7-fixture","evidence_sha256":h},
        "naming":{"new_names":"NFC","historical_names":"exact","collision_key":"NFC+casefold","identity":"persisted"},
        "variants":[{"id":"synthetic-color","contributor_fields":["source"],"exception_refs":[],"design":{"treatment":"SOURCE_PRESERVING",
        "source_branch":"original-color","trim":True,"sizes":{"standard":{"width":285,"height":85},"bigger":{"width":440,"height":100}},
        "rounding":"half-up","resampling":"Lanczos","format":"PNG","mode":"RGBA","color_space":"sRGB","compression":9,
        "preserve_basename":True,"transformation":{"id":"synthetic-overlay","sha256":h}}}]})
    nodes={"asset:synthetic.png":{"kind":"asset","identity":"synthetic.png","sha256":h,"dependencies":[]}};outputs={}
    for size in ("standard","bigger"):
        i="synthetic.overlay."+size;key="output:"+i
        nodes[key]={"kind":"output","identity":i,"sha256":h,"dependencies":["asset:synthetic.png"]}
        outputs[i]={"node":key,"category":"Overlays","kind":"overlay","variant":"synthetic-color","local_path":size+"/Synthetic.png",
            "public_path":None,"companions":["synthetic.overlay."+("bigger" if size=="standard" else "standard")],
            "evidence":{"previews":[],"confirmations":[],"decisions":[],"receipts":[]},"context_sha256":h}
    graph=Snapshot.create({"schema_version":1,"kind":"m5-dependency-snapshot","basis":h,"nodes":nodes,"outputs":outputs,"unresolved":[]})
    return SyntheticAuthority(contract,graph)


def demo(root):
    """Small JSON-only simulation. No raster creation, real contract, or network."""
    from .controller import Controller
    authority=fixture_authority();controller=Controller(root,simulation=authority);authority.attach(controller)
    for revision,target in enumerate(("IMPLEMENTED","COMPATIBLE")):
        controller.transition(authority.proposal,authority.gates,target,expected_revision=revision)
    binding=authority.approve()
    controller.transition(authority.proposal,authority.gates,"APPROVED",expected_revision=2,binding=binding,approval_record=authority.record)
    controller.transition(authority.proposal,authority.gates,"READY",expected_revision=3)
    controller.transition(authority.proposal,authority.gates,"ACTIVE",expected_revision=4,operator=authority.operate(controller,binding))
    active=controller.inspect(authority.proposal.to_dict()["id"])
    controller.rollback(authority.proposal.to_dict()["id"],expected_revision=5,restore_sha256=controller.archive.history(authority.proposal.to_dict()["id"])[1].sha256)
    return {"synthetic_only":True,"active_simulation":active,"recovered":controller.inspect(authority.proposal.to_dict()["id"]),
        "production_enforcement":False,"publication_authorized":False,"actual_contracts_activated":0}
