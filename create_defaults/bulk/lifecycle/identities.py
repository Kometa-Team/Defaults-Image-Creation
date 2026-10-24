"""Persistent isolated identity snapshots using M1 CAS, blobs and events only.

UUID allocation and namespace reservation are metadata planning, never catalog
ADD/RENAME/DELETE execution. Frozen history is a read-only layer, not copied or
rewritten in the live snapshot. No additional SQL table/database is introduced.
"""

from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from types import MappingProxyType
from uuid import uuid4

from ..common import Conflict, canonical, fingerprint, path_key
from ..contracts.destination_preflight.models import DestinationInventory
from ..contracts.destination_preflight.inventory import expand
from .basis import historical_basis
from .identity_models import HEADER, RegistrySnapshot, semantic_key, portable, fail
from .models import Operation, namespace_key, key
from .package_e import SidecarStore
from .storage import OperationStore


def namespace_inventory(inventory, expected_sha256, root=None):
    if type(inventory) is not DestinationInventory:fail("namespace_inventory_type")
    inventory = DestinationInventory.from_bytes(inventory.encoded)
    if inventory.sha256 != expected_sha256:fail("namespace_inventory_pin")
    value = inventory.to_dict();rows,missing = expand(value)
    if missing:fail("incomplete_namespace_inventory")
    if root is not None:portable(root,new=True)
    prefix = root+"/" if root else ""
    selected = []
    for path,row in rows.items():
        if root and not path.startswith(prefix):continue
        relative = path[len(prefix):]
        if not relative:continue
        selected.append(dict(namespace="public",path=relative,kind="directory" if row["mode"] == "040000" else "file",
            sha256=fingerprint(row)))
    if root and (root not in rows or rows[root]["mode"] != "040000"):fail("namespace_root")
    return sorted(selected,key=lambda r:(r["namespace"],r["path"])), canonical(dict(inventory_sha256=inventory.sha256,
        repository=value["repository"],branch=value["branch"],commit=value["commit"],tree=value["tree"],root=root)).decode()


def aliases_for(names):
    rows = [("display", names["display_name"])]
    if names["source"]:rows.append(("source",names["source"]["path"]))
    for ns,field in (("local","local_path"),("public","public_path")):
        if names[field] is not None:rows.append((ns,names[field]))
    return rows


@lru_cache(maxsize=1)
def frozen_namespace():
    result = {}
    for identity in sorted(historical_basis().ids):
        value = historical_basis().row(identity)["identity"]
        for ns,field in (("local","local_path"),("public","public_path")):
            if value[field] is not None:
                k = (ns,path_key(value[field]))
                if k in result:fail("historical_name_collision")
                result[k] = (identity,"file",value[field])
    return MappingProxyType(result)


@lru_cache(maxsize=2)
def base_namespace(encoded):
    """Validate the complete immutable base once, never cache live snapshots.

    The cache key is exact canonical inventory content; every registry replay
    still verifies its stored inventory hash and complete Git tree closure.
    Including implicit parent directories catches a new file shadowing any
    frozen/external subtree without rescanning 28,000 old paths per revision.
    """
    occupied=dict(frozen_namespace());directories={}
    for r in json.loads(encoded):
        ns,path=r['namespace'],r['path'];k=(ns,path_key(path))
        if r['kind']=='directory':
            if k in directories and directories[k]!=path:fail('directory_case_collision')
            directories[k]=path
        elif k in occupied:
            if occupied[k][2]!=path:fail('name_collision')
        else:occupied[k]=('external','file',path)
    for (ns,k),(owner,kind,path) in occupied.items():
        if (ns,k) in directories:fail('file_directory_collision')
        parts=path.split('/')
        for n in range(1,len(parts)):
            prefix='/'.join(parts[:n]);pk=(ns,path_key(prefix))
            if pk in occupied:fail('file_directory_collision')
            directories.setdefault(pk,prefix)
    return MappingProxyType(occupied),MappingProxyType(directories)


def validate_namespace(snapshot, external):
    """Complete frozen plus sparse live/alias/tombstone/external namespace."""
    v = snapshot.to_dict();basis = historical_basis();entries = {e["id"]:e for e in v["entries"]}
    base,directories=base_namespace(canonical(external))
    occupied = dict(base);semantics = dict(basis.semantic_index());relevant=[]
    def claim(ns,path,owner,kind="file"):
        normalized = path_key(path);current = occupied.get((ns,normalized))
        if current and (current[0] != owner or current[1] != kind):
            # Actual inventory may contain the already reserved historical file.
            if owner != "external" or current[1] != kind:fail("name_collision")
            return
        occupied[(ns,normalized)] = (owner,kind,path)
        relevant.append((ns,normalized,owner,path))
    for e in v["entries"]:
        if e["variant"] is not None:
            rule=basis.rule(e["category"],e["variant"])
            if e["semantic"]["role"] not in rule["required_presentations"]:
                fail("unsupported_category_variant")
        sk = semantic_key(e["category"],e["semantic"])
        if sk in semantics and semantics[sk] != e["id"]:fail("semantic_collision")
        semantics[sk] = e["id"]
        parent = e["semantic"]["parent"]
        if parent is not None and parent not in basis.parents and parent not in entries and not (e["origin"] == "historical-reference" and parent == basis.entry(e["id"])["semantic"]["parent"]):
            fail("unknown_semantic_parent")
        if parent in entries and entries[parent]["category"] != e["category"]:fail("cross_category_parent")
        if e["origin"] == "historical-reference":
            old = basis.entry(e["id"])
            if any(e[f] != old[f] for f in ("category","historical_sha256","semantic","original_names")):
                fail("historical_substitution")
        elif e["id"] in basis.ids or e["id"] in basis.parents:fail("historical_substitution")
        for ns,path in aliases_for(e["names"])+[(a["namespace"],a["value"]) for a in e["aliases"]]:
            if ns in {"local","public"}:claim(ns,path,e["id"])
    # Files may not be parents of other files; directory spelling is exact.
    for ns,normalized,owner,path in relevant:
        parts = path.split("/")
        if (ns,normalized) in directories:fail("file_directory_collision")
        for n in range(1,len(parts)):
            prefix = "/".join(parts[:n]);pk = path_key(prefix)
            if (ns,pk) in occupied:fail("file_directory_collision")
            if owner in entries and (ns,pk) in directories and directories[(ns,pk)] != prefix:
                fail("directory_case_collision")
    # Parent references form an acyclic identity graph, even for containers.
    for identity in entries:
        seen = set();current = identity
        while current in entries:
            if current in seen:fail("identity_cycle")
            seen.add(current);entry=entries[current];parent=entry["semantic"]["parent"]
            # Historical paired designs use one existing member as their frozen
            # group key; this is not an allocated container dependency edge.
            if entry["origin"]=="historical-reference" and parent==current:break
            current=parent


@dataclass(frozen=True)
class RegistryHead:
    revision: int
    snapshot_sha256: str
    record_sha256: str
    event_sha256: str


@dataclass(frozen=True)
class RegistryView:
    snapshot: RegistrySnapshot
    head: RegistryHead

    def entries(self):return self.snapshot.to_dict()["entries"]

    def lookup(self, category, parent, child, role="single", language="en"):
        target = (category,parent,child,role,language)
        for e in self.entries():
            if semantic_key(e["category"],e["semantic"]) == target:return e["id"]
        value = historical_basis().semantic_index().get(target)
        if value is None:fail("unallocated_semantic_identity")
        return value

    def entry(self, identity):
        for e in self.entries():
            if e["id"] == identity:return e
        return historical_basis().entry(identity)


def transition(before, after, external):
    a,b = before.to_dict(),after.to_dict()
    if b["revision"] != a["revision"]+1 or b["previous_sha256"] != before.sha256:fail("registry_revision")
    for field in ("id","basis_sha256","mapping_sha256","namespace_sha256","namespace_context_json"):
        if a[field] != b[field]:fail("registry_basis_changed")
    old,new = {e["id"]:e for e in a["entries"]},{e["id"]:e for e in b["entries"]}
    if not old.keys() <= new.keys():fail("identity_erasure")
    for identity,e in old.items():
        next_entry = new[identity]
        if e == next_entry:continue
        for field in ("id","category","origin","historical_sha256","semantic","variant","original_names"):
            if e[field] != next_entry[field]:fail("identity_reassignment")
        required = set(aliases_for(e["names"])) | {(r["namespace"],r["value"]) for r in e["aliases"]}
        observed = {(r["namespace"],r["value"]) for r in next_entry["aliases"]}
        if next_entry["revision"] != e["revision"]+1 or not required <= observed:fail("lost_alias")
        if e["tombstone_sha256"] is not None:fail("tombstone_reuse")
    for identity in new.keys()-old.keys():
        if new[identity]["revision"] != 1:fail("allocation_revision")
    requests = {r["token"]:r for r in b["requests"]}
    if len(b["requests"]) != len(a["requests"])+1 or any(requests.get(r["token"]) != r for r in a["requests"]):fail("request_erasure")
    validate_namespace(after,external)


class IdentityRegistry:
    def __init__(self, root, identity):
        self.operations = OperationStore(root)
        self.identity = identity
        self.operation_id = "synthetic.operation.p4m2-registry-"+fingerprint(identity)
        self.subject = "synthetic.registry."+fingerprint(identity)
        self.view()

    @classmethod
    def create(cls, root, identity, *, inventory, expected_inventory_sha256, destination_root=None):
        store = OperationStore.create(root)
        external,context = namespace_inventory(inventory,expected_inventory_sha256,destination_root)
        value = dict(**HEADER,kind="identity-registry",id=identity,revision=1,previous_sha256=None,
            basis_sha256=historical_basis().registry_sha256,mapping_sha256=historical_basis().mapping_sha256,
            entries=[],requests=[],namespace_sha256=fingerprint(external),namespace_context_json=context)
        snapshot = RegistrySnapshot.from_dict(value);validate_namespace(snapshot,external)
        self = object.__new__(cls);self.operations=store;self.identity=identity
        self.operation_id="synthetic.operation.p4m2-registry-"+fingerprint(identity);self.subject="synthetic.registry."+fingerprint(identity)
        if store.history(self.operation_id):
            existing=self.view()
            initial=self.history()[0]
            if initial.snapshot.sha256 != snapshot.sha256:raise Conflict("Registry namespace already initialized differently")
            return self
        writer=SidecarStore(store.root);writer.put_object(inventory.encoded,expected_sha256=inventory.sha256)
        self._append(snapshot,None)
        return self

    def history(self):
        history=self.operations.history(self.operation_id);events={e.to_dict()["record_sha256"]:e for e in self.operations.journal()}
        if not history:fail("missing_identity_registry")
        result=[];budget=0;external=None
        for record in history:
            r=record.to_dict()
            if len(r["subjects"])!=1 or r["subjects"][0]["id"]!=self.subject or r["state"]!="draft" or r["operation"]!="UPDATE":fail("registry_operation")
            raw=self.operations.contracts.read_object(r["subjects"][0]["proposed_sha256"])
            budget+=len(raw)
            if budget>64*1024*1024:fail("registry_archive_bound")
            snap=RegistrySnapshot.from_bytes(raw)
            v=snap.to_dict()
            if v["id"]!=self.identity or v["revision"]!=r["revision"] or r["request_sha256"]!=snap.sha256:fail("registry_index")
            if (v["basis_sha256"],v["mapping_sha256"])!=(historical_basis().registry_sha256,historical_basis().mapping_sha256):fail("historical_basis")
            if result:transition(result[-1].snapshot,snap,external)
            else:
                if v["revision"]!=1 or v["entries"] or v["requests"]:fail("registry_initial")
                context=json.loads(v["namespace_context_json"])
                inv=DestinationInventory.from_bytes(self.operations.contracts.read_object(context["inventory_sha256"]))
                rows,encoded=namespace_inventory(inv,context["inventory_sha256"],context["root"])
                if fingerprint(rows)!=v["namespace_sha256"] or encoded!=v["namespace_context_json"]:fail("namespace_substitution")
                external=rows;validate_namespace(snap,external)
            event=events[record.sha256]
            result.append(RegistryView(snap,RegistryHead(v["revision"],snap.sha256,record.sha256,event.sha256)))
        return tuple(result)

    def view(self):return self.history()[-1]

    def require_head(self, expected):
        if type(expected) is not RegistryHead or self.view().head!=expected:raise Conflict("Identity registry head changed")

    def _append(self, snapshot, previous):
        writer=SidecarStore(self.operations.root);writer.put_object(snapshot.encoded,expected_sha256=snapshot.sha256)
        current={key(h):h for h in self.operations.inspect()["heads"]}
        keys=[dict(kind="evidence",id=self.subject),dict(kind="subject",id=self.subject)]
        revision=snapshot.to_dict()["revision"]
        value=dict(schema_version=1,protocol_version="1.0.0",scope="isolated-synthetic-records",
            **{k:v for k,v in HEADER.items() if k not in {"schema_version","protocol_version","scope"}},kind="operation-record",
            id=self.operation_id,operation="UPDATE",revision=revision,content_revision=revision,
            previous_sha256=previous.record_sha256 if previous else None,previous_event_sha256=previous.event_sha256 if previous else None,
            state="draft",reason=None,request_sha256=snapshot.sha256,
            subjects=[dict(id=self.subject,before_sha256=previous.snapshot_sha256 if previous else fingerprint({"empty_registry":self.identity}),proposed_sha256=snapshot.sha256)],
            reads=[dict(**k,subjects=[self.subject],revision=current.get(key(k),{}).get("revision",0),sha256=current.get(key(k),{}).get("sha256")) for k in keys],writes=keys,namespaces=[],
            references=[dict(kind="evidence",id="synthetic.registry.snapshot",subject=self.subject,sha256=snapshot.sha256)])
        record=Operation.from_dict(value)
        return self.operations.append(record,expected_revision=revision-1,
            expected_sha256=previous.record_sha256 if previous else None,expected_event_sha256=previous.event_sha256 if previous else None)

    def _mutate(self, token, request, expected, action):
        before=self.view();v=before.snapshot.to_dict();request_hash=fingerprint(request)
        for r in v["requests"]:
            if r["token"]==token:
                if r["request_sha256"]!=request_hash:raise Conflict("Idempotency token already binds another request")
                return before.entry(r["result_id"])
        self.require_head(expected)
        entry=action(deepcopy(v["entries"]),before)
        v["entries"]=[e for e in v["entries"] if e["id"]!=entry["id"]]+[entry]
        v["entries"].sort(key=lambda e:e["id"])
        v["requests"].append(dict(token=token,request_sha256=request_hash,result_id=entry["id"]))
        v["requests"].sort(key=lambda r:r["token"])
        v.update(revision=v["revision"]+1,previous_sha256=before.snapshot.sha256)
        context=json.loads(v["namespace_context_json"])
        inv=DestinationInventory.from_bytes(self.operations.contracts.read_object(context["inventory_sha256"]))
        external,_=namespace_inventory(inv,context["inventory_sha256"],context["root"])
        after=RegistrySnapshot.from_dict(v);transition(before.snapshot,after,external)
        self._append(after,expected)
        return deepcopy(entry)

    def allocate(self, *, category, semantic, variant, names, token, expected):
        request=dict(action="allocate",category=category,semantic=semantic,variant=variant,names=names)
        def action(entries,view):
            target=semantic_key(category,semantic)
            if target in historical_basis().semantic_index() or any(semantic_key(e["category"],e["semantic"])==target for e in entries):raise Conflict("Semantic identity is already allocated or reserved")
            identity=category.lower()+"."+uuid4().hex
            if identity in historical_basis().ids or any(e["id"]==identity for e in entries):fail("uuid_collision")
            return dict(id=identity,category=category,origin="assigned",historical_sha256=None,revision=1,
                semantic=deepcopy(semantic),variant=variant,names=deepcopy(names),original_names=deepcopy(names),aliases=[],tombstone_sha256=None)
        return self._mutate(token,request,expected,action)

    def reference(self, identity, *, token, expected):
        def action(entries,view):
            if any(e["id"]==identity for e in entries):raise Conflict("Historical identity already referenced")
            return historical_basis().entry(identity)
        return self._mutate(token,dict(action="reference",identity=identity),expected,action)

    def revise(self, identity, names, *, entry_revision, token, expected, tombstone_sha256=None):
        request=dict(action="revise-reservation",identity=identity,names=names,entry_revision=entry_revision,tombstone_sha256=tombstone_sha256)
        def action(entries,view):
            entry=next((e for e in entries if e["id"]==identity),None)
            if entry is None or entry["revision"]!=entry_revision:raise Conflict("Exact allocated entry revision required")
            if entry["tombstone_sha256"] is not None:fail("tombstone_reuse")
            old={(a["namespace"],a["value"]) for a in entry["aliases"]}|set(aliases_for(entry["names"]))
            entry.update(names=deepcopy(names),revision=entry_revision+1,tombstone_sha256=tombstone_sha256,
                aliases=[dict(namespace=n,value=p) for n,p in sorted(old)])
            return entry
        return self._mutate(token,request,expected,action)
