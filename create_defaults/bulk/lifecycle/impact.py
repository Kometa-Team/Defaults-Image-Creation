"""Pinned M5 before/after impact and M1 request consumption; no executor.

An impact attestation is replayable metadata. It cannot turn M1 coordination,
an unkeyed hash or missing Phase 3 authorities into operational acceptance.
"""

from collections import deque
from dataclasses import dataclass
import json

from ..common import Conflict,canonical,fingerprint,path_key
from ..contracts.expanded.graph import Snapshot,compare
from .basis import historical_basis,HISTORICAL_GRAPH_SHA256
from .candidates import PosterCandidate
from .overlay_candidates import OverlayCandidate
from .identities import RegistryHead
from .identity_models import HEADER,ImpactEvidence,fail
from .models import Operation,namespace_key,key


@dataclass(frozen=True)
class HistoricalGraph:
    graph: Snapshot

    @classmethod
    def select(cls,snapshot):
        # Never accept a caller's "historical/compatible" flag or self-selected
        # baseline hash. This is the actual unchanged complete M5+M6 graph.
        snapshot=Snapshot.load(snapshot.encoded,expected_sha256=HISTORICAL_GRAPH_SHA256)
        index=snapshot.index();basis=historical_basis()
        if snapshot.data()["basis"]!=basis.registry_sha256 or index.outputs.keys()!=basis.ids:fail("historical_graph_membership")
        for i,row in index.outputs.items():
            item=basis.row(i)["identity"];assigned=basis.assignment(i)
            if (row["category"],row["local_path"],row["public_path"],row["companions"])!=(item["category"],item["local_path"],item["public_path"],assigned["companions"]):fail("historical_graph_substitution")
            if row['variant']!=basis.row(i)['observed_variant']:fail('historical_job_variant_substitution')
        return cls(snapshot)

    @property
    def sha256(self):return self.graph.sha256

    def verify(self):return self.select(self.graph)


@dataclass(frozen=True)
class OperationHead:
    id: str
    revision: int
    sha256: str
    event_sha256: str


def operation_head(store,identity):
    history=store.history(identity)
    if not history:fail("missing_operation")
    record=history[-1]
    event=next((e for e in store.journal() if e.to_dict()["record_sha256"]==record.sha256),None)
    if event is None:fail("missing_operation_event")
    return OperationHead(identity,record.to_dict()["revision"],record.sha256,event.sha256)


def _check_candidate(value):
    if type(value) not in {PosterCandidate,OverlayCandidate,HistoricalGraph}:fail("unsupported_candidate_adapter")
    return value.verify()


def _empty():
    return Snapshot.create(dict(schema_version=1,kind="m5-dependency-snapshot",basis=historical_basis().registry_sha256,nodes={},outputs={},unresolved=[]))


def epochs(before,after):
    if before is not None:_check_candidate(before)
    _check_candidate(after)
    previous=before.graph if before is not None else _empty()
    if type(after) is HistoricalGraph:fail("prospective_adapter_required")
    after.registry.require_head(after.registry_head)
    if type(before) is PosterCandidate and type(after) is PosterCandidate:
        old_families,new_families=before.data()["families"],after.data()["families"]
        for family,members in old_families.items():
            if family not in new_families or not set(members)<=set(new_families[family]):
                fail("generator_member_retirement_requires_m6")
    # The actual scoped adapter is applied as an immutable overlay on the
    # complete pinned historical epoch, preserving all unrelated output rows.
    value=previous.data();candidate=after.graph.data()
    value["nodes"].update(candidate["nodes"])
    value["outputs"].update(candidate["outputs"])
    value["unresolved"]=sorted(set(value["unresolved"]+candidate["unresolved"]))
    proposed=Snapshot.create(value)
    return previous,proposed


def _closure(index,identities):
    visited=set();pending=[index.outputs[i]["node"] for i in identities if i in index.outputs]
    while pending:
        node=pending.pop()
        if node not in visited:visited.add(node);pending.extend(index.nodes[node]["dependencies"])
    return visited


def _reasons(index,changed):
    reasons={}
    for cause in sorted(set(changed)&index.nodes.keys()):
        pending=deque([(cause,[cause])]);visited=set()
        while pending:
            node,path=pending.popleft()
            if node in visited:continue
            visited.add(node)
            if node in index.output_nodes:
                identity=index.output_nodes[node]
                reasons.setdefault(identity,[]).append(dict(cause=cause,path=path))
            for child in sorted(index.reverse[node]):pending.append((child,path+[child]))
    return reasons


def _details(before,after):
    old,new=epochs(before,after);a,b=old.index(),new.index();comparison=compare(old,new)
    affected=set(comparison["affected_outputs"]);companions=set()
    pending=list(affected)
    while pending:
        identity=pending.pop()
        for index in (a,b):
            if identity not in index.outputs:continue
            for companion in index.outputs[identity]["companions"]:
                if companion not in affected and companion not in companions:companions.add(companion);pending.append(companion)
    all_affected=affected|companions
    reasons=_reasons(a,comparison["changed_identities"])
    for identity,rows in _reasons(b,comparison["changed_identities"]).items():
        combined={canonical(r):r for r in reasons.get(identity,[])+rows};reasons[identity]=[combined[k] for k in sorted(combined)]
    for identity in companions:
        causes=sorted(i for index in (a,b) for i in all_affected if i in index.outputs and identity in index.outputs[i]["companions"])
        reasons.setdefault(identity,[]).append(dict(cause="required-companion",path=sorted(set(causes))))
    if any(i not in reasons for i in all_affected):fail("unexplained_impact")
    blockers=list(comparison["unresolved"])
    # Family provenance only becomes complete when both actual adapters have
    # resolved every expanded child, not from a caller's compatibility claim.
    proven=[]
    for gap in list(blockers):
        prefix="family-scoped provenance change needs per-child resolution/comparison: "
        if not gap.startswith(prefix):continue
        node=gap[len(prefix):]
        family=node.removeprefix("family:") if node.startswith("family:") else node.rsplit("#",1)[-1]
        relevant=[]
        for plan in (before,after):
            if type(plan) is PosterCandidate:
                data=plan.data();members=data["families"].get(family)
                actual={j["poster_id"] for j in data["manifest"]["jobs"]}
                if members is not None:relevant.append(set(members)<=actual)
        if relevant and all(relevant):
            blockers.remove(gap);proven.append(dict(family=family,proof="actual complete expanded members replayed",node=node))
    comparison["per_child_resolution"]=proven
    if type(after) is OverlayCandidate:blockers.append("overlay_preseal_identity_hook_required")
    unaffected=sorted((a.outputs.keys()|b.outputs.keys())-all_affected)
    preserved={}
    for identity in unaffected:
        if identity not in a.outputs or identity not in b.outputs or a.material_context(identity)!=b.material_context(identity):fail("unaffected_output_changed")
        preserved[identity]=a.material_context(identity)
    reads=sorted(_closure(a,all_affected)|_closure(b,all_affected))
    changed=set(comparison["changed_identities"])
    definitions=sorted(k for k in changed if (a.nodes.get(k) or b.nodes.get(k))["kind"]=="definition")
    details=dict(comparison=comparison,affected_outputs=sorted(all_affected),unaffected_outputs=unaffected,
        required_companions=sorted(companions),reasons={i:reasons[i] for i in sorted(all_affected)},
        read_set=reads,write_set=sorted(changed|{b.outputs[i]["node"] if i in b.outputs else a.outputs[i]["node"] for i in all_affected}),
        before_mappings={i:{f:a.outputs[i][f] for f in ("local_path","public_path","category","variant")} for i in sorted(all_affected) if i in a.outputs},
        after_mappings={i:{f:b.outputs[i][f] for f in ("local_path","public_path","category","variant")} for i in sorted(all_affected) if i in b.outputs},
        changed_effective_definitions=definitions,complete=not blockers,blockers=sorted(set(blockers)),unaffected_sha256=fingerprint(preserved))
    return old,new,details


def _subject(identity):return "synthetic.item."+fingerprint(identity)
def _dependency(node):return dict(kind="dependency",id="synthetic.dependency."+fingerprint(node))


def _coordination(registry,details):
    ids=details["affected_outputs"]
    subjects=sorted(_subject(i) for i in ids)
    keys={key(k):k for k in [dict(kind="subject",id=s) for s in subjects]+[_dependency(n) for n in details["read_set"]]+[dict(kind="evidence",id=registry.subject)]}
    writes={key(k):k for k in [dict(kind="subject",id=s) for s in subjects]+[_dependency(n) for n in details["write_set"]]}
    for k in writes:keys[k]=writes[k]
    namespaces={}
    for mappings in (details["before_mappings"],details["after_mappings"]):
        for i,m in mappings.items():
            for field in ("local_path","public_path"):
                if m[field] is None:continue
                # Hash the normalized claim only; exact literal mappings remain
                # independently pinned in the candidate/impact document.
                path="claims/"+fingerprint(dict(namespace=field,path=path_key(m[field])))+".json"
                row=dict(namespace="synthetic.lifecycle",path=path,subjects=subjects)
                k=namespace_key(row["namespace"],path);namespaces[key(k)]=row;keys[key(k)]=k;writes[key(k)]=k
    if any(len(x)>4096 for x in (subjects,keys,writes,namespaces)):fail("m1_record_scope_limit")
    return subjects,keys,writes,namespaces


def preview_impact(before,after):
    """Unaccepted read-only query, including library-wide scopes above M1 caps."""
    old,new,details=_details(before,after)
    return dict(**HEADER,kind="prospective-impact-query",before_sha256=old.sha256,after_sha256=new.sha256,details=details)


def request_record(registry,before,after,*,identity,operation="UPDATE"):
    """Represent a request with measured M1 read/write closure; never apply it."""
    if operation not in {"ADD","UPDATE","RENAME"}:fail("unsupported_operation_semantics")
    if operation!='ADD' and before is None:fail('prior_epoch_required')
    registry.require_head(after.registry_head)
    old,new,details=_details(before,after)
    ids=details["affected_outputs"]
    if not ids:fail("empty_impact_request")
    if operation=="ADD" and any(i in old.index().outputs for i in ids):fail("mixed_add_update_scope")
    store=registry.operations;heads={key(h):h for h in store.inspect()["heads"]}
    if store.history(identity):raise Conflict("Request identity already has a record; use an explicit next M1 revision")
    subjects,keys,writes,namespaces=_coordination(registry,details)
    record=dict(schema_version=1,protocol_version="1.0.0",scope="isolated-synthetic-records",
        **{k:v for k,v in HEADER.items() if k not in {"schema_version","protocol_version","scope"}},kind="operation-record",
        id=identity,operation=operation,revision=1,content_revision=1,previous_sha256=None,previous_event_sha256=None,state="draft",reason=None,
        request_sha256=fingerprint(dict(before=before.sha256 if before else None,after=after.sha256,registry=after.registry_head.snapshot_sha256,details=details)),
        subjects=[dict(id=s,before_sha256=None if operation=="ADD" else before.sha256 if before else old.sha256,proposed_sha256=after.sha256) for s in subjects],
        reads=[dict(**keys[k],subjects=[keys[k]["id"]] if keys[k]["kind"]=="subject" else subjects,
            revision=heads.get(k,{}).get("revision",0),sha256=heads.get(k,{}).get("sha256")) for k in sorted(keys)],
        writes=[writes[k] for k in sorted(writes)],namespaces=[namespaces[k] for k in sorted(namespaces)],
        references=[dict(kind="evidence",id="synthetic.registry.snapshot",subject=s,sha256=after.registry_head.snapshot_sha256) for s in subjects])
    return Operation.from_dict(record)


def analyze(registry,before,after,*,operation,expected_operation_sha256):
    if type(operation) is not OperationHead or operation.sha256!=expected_operation_sha256:fail("operation_binding")
    if operation_head(registry.operations,operation.id)!=operation:raise Conflict("M1 operation revision/event changed")
    registry.require_head(after.registry_head)
    history=registry.operations.history(operation.id);record=history[-1];value=record.to_dict()
    if record.sha256!=operation.sha256:raise Conflict('M1 operation changed during consumption')
    if value["state"] not in {"draft","structurally_validated"}:fail("inactive_operation")
    if value['operation'] not in {'ADD','UPDATE','RENAME'} or (value['operation']!='ADD' and before is None):fail('operation_semantics')
    old,new,details=_details(before,after)
    subjects,keys,writes,namespaces=_coordination(registry,details)
    if value['operation']=='ADD' and any(i in old.index().outputs for i in details['affected_outputs']):fail('mixed_add_update_scope')
    if [s["id"] for s in value["subjects"]]!=subjects:fail("operation_membership_substitution")
    if [key(r) for r in value["reads"]]!=sorted(keys) or [key(r) for r in value["writes"]]!=sorted(writes) or value["namespaces"]!=[namespaces[k] for k in sorted(namespaces)]:fail("operation_closure_substitution")
    expected_request=fingerprint(dict(before=before.sha256 if before else None,after=after.sha256,registry=after.registry_head.snapshot_sha256,details=details))
    if value["request_sha256"]!=expected_request or value["references"]!=[dict(kind="evidence",id="synthetic.registry.snapshot",subject=s,sha256=after.registry_head.snapshot_sha256) for s in subjects]:fail("operation_request_substitution")
    for s in value["subjects"]:
        if s["proposed_sha256"]!=after.sha256 or s["before_sha256"]!=(None if value["operation"]=="ADD" else before.sha256 if before else old.sha256):fail("operation_epoch_substitution")
    # The original M1 append already checked these heads atomically. The report
    # also checks unchanged read-only dependencies/evidence at consumption time.
    event=next(e.to_dict() for e in registry.operations.journal() if e.sha256==operation.event_sha256)
    heads={key(h):h for h in registry.operations.inspect()["heads"]}
    changes={key(c["key"]):c["after"] for c in event["changes"]}
    for r in value["reads"]:
        expected=changes.get(key(r),r)
        observed=heads.get(key(r),dict(revision=0,sha256=None))
        if (observed["revision"],observed["sha256"])!=(expected["revision"],expected["sha256"]):raise Conflict("A consumed M1 read/write head changed")
    return ImpactEvidence.from_dict(dict(**HEADER,kind="prospective-impact",operation=operation.__dict__,
        registry_sha256=after.registry_head.snapshot_sha256,before_sha256=old.sha256,after_sha256=new.sha256,
        inputs_sha256=fingerprint(dict(before=before.sha256 if before else None,after=after.sha256,operation=value)),
        details_json=canonical(details).decode()))


def revalidate(evidence,*,expected_sha256,registry,before,after):
    if type(evidence) is not ImpactEvidence or evidence.sha256!=expected_sha256:fail("impact_pin")
    value=evidence.to_dict();binding=OperationHead(**value["operation"])
    current=analyze(registry,before,after,operation=binding,expected_operation_sha256=binding.sha256)
    if current.encoded!=evidence.encoded:fail("impact_replay_substitution")
    return current
