"""M7 synthetic authority only. No real package decisions or production state."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import shutil
import subprocess
import sys

import pytest

from create_defaults.bulk.common import BulkError, Conflict, canonical, fingerprint
from create_defaults.bulk.contracts.activation import Controller, Proposal, GateEvidence, ApprovalBinding, OperatorDecision
from create_defaults.bulk.contracts.activation.__main__ import main
from create_defaults.bulk.contracts.activation.models import GATES
from create_defaults.bulk.contracts.activation.storage import Archive
from create_defaults.bulk.contracts.activation.simulation import SyntheticAuthority, fixture_authority, demo
from create_defaults.bulk.contracts.activation.impact import assess
from create_defaults.bulk.contracts.activation.protection import verify
from create_defaults.bulk.contracts.expanded.graph import Snapshot
from create_defaults.bulk.contracts.models import Contract, ContractApproval


@pytest.fixture(scope="module")
def empty_archive_seed(tmp_path_factory):
    """Copy only empty synthetic state, never authority or prior transitions.

    Each case still has its own database and immutable blobs. Avoid repeating
    the same Package E schema setup dozens of times within the existing CI cap.
    """
    authority=fixture_authority();root=tmp_path_factory.mktemp("m7-seed")/"state"
    controller=Controller(root,simulation=authority);authority.attach(controller)
    authority.read_object=None
    return authority,root


@pytest.fixture
def isolated(tmp_path,empty_archive_seed):
    prototype,seed=empty_archive_seed
    authority=deepcopy(prototype)
    root=tmp_path/"activation";shutil.copytree(seed,root)
    controller = Controller(root,simulation=authority,clock=lambda:authority.now)
    authority.read_object=controller.archive.contracts.read_object
    return authority,controller


def move(a,c,state,revision,**kwargs):
    return c.transition(a.proposal,a.gates,state,expected_revision=revision,**kwargs)


def approved(a,c):
    move(a,c,"IMPLEMENTED",0);move(a,c,"COMPATIBLE",1)
    binding = a.approve()
    move(a,c,"APPROVED",2,binding=binding,approval_record=a.record)
    return binding


def active(a,c):
    binding=approved(a,c);move(a,c,"READY",3)
    move(a,c,"ACTIVE",4,operator=a.operate(c,binding))
    return binding


def test_default_boundary_cannot_be_replaced_by_json_or_reviewer_strings(tmp_path,isolated):
    a,_=isolated;c=Controller(tmp_path/"blocked")
    move(a,c,"IMPLEMENTED",0)
    with pytest.raises(BulkError,match="authenticated"):
        move(a,c,"COMPATIBLE",1,binding=a.approve())
    for forged in ({"actor":"bullmoose20"},"bullmoose20",object()):
        with pytest.raises(BulkError):Controller(tmp_path/"forged",simulation=forged)
    assert c.inspect(a.proposal.to_dict()["id"])["state"]=="IMPLEMENTED"


def test_simulation_registry_and_principals_are_not_real_m1_authority(isolated):
    from create_defaults.bulk.contracts.registry import RegistrySnapshot
    a,c=isolated
    with pytest.raises(BulkError):
        RegistrySnapshot.load(a.registry.encoded,expected_sha256=a.registry.sha256,
            read_object=c.archive.contracts.read_object,trusted_decisions={})
    binding=a.approve()
    with pytest.raises(BulkError):a.approve(auth_context_sha256="b"*64)
    assert a.events[binding.to_dict()["event_id"]]==binding.sha256


def test_separate_stages_no_skips_no_unapproved_active_and_no_publication(isolated):
    a,c=isolated
    for state in ("APPROVED","READY","ACTIVE"):
        with pytest.raises(BulkError):move(a,c,state,0)
    move(a,c,"IMPLEMENTED",0);move(a,c,"COMPATIBLE",1)
    with pytest.raises(BulkError):move(a,c,"APPROVED",2)
    binding=a.approve();move(a,c,"APPROVED",2,binding=binding,approval_record=a.record)
    with pytest.raises(BulkError):move(a,c,"ACTIVE",3,operator=a.operate(c,binding))
    move(a,c,"READY",3)
    with pytest.raises(BulkError):move(a,c,"ACTIVE",4)
    move(a,c,"ACTIVE",4,operator=a.operate(c,binding))
    status=c.inspect(a.proposal.to_dict()["id"])
    assert status["state"]=="ACTIVE" and not status["production_enforcement"] and not status["publication_authorized"]
    assert c.archive.contracts.read_record(a.record.to_dict()["id"],1)==a.record


def test_receipt_cannot_be_smuggled_into_implementation_transition(isolated):
    a,c=isolated
    with pytest.raises(BulkError):move(a,c,"IMPLEMENTED",0,approval_record=a.record)
    with pytest.raises(BulkError):c.archive.contracts.read_record(a.record.to_dict()["id"],1)
    assert not c.archive.history(a.proposal.to_dict()["id"])


@pytest.mark.parametrize("change",[
    {"actor":"synthetic-contributor"},{"registry_sha256":"b"*64},
    {"compatibility_sha256":"c"*64},{"record_sha256":"d"*64},
    {"package":{"category":"Playlist","kind":"poster","version":"1.0.0","sha256":"e"*64}},
    {"package":{"category":"Overlays","kind":"overlay","version":"1.0.0","sha256":"e"*64}},
    {"auth_context_sha256":"f"*64},{"review_evidence":[]},{"id":"synthetic.other"},
])
def test_forged_and_wrong_scope_approvals_never_advance(isolated,change):
    a,c=isolated;move(a,c,"IMPLEMENTED",0);move(a,c,"COMPATIBLE",1)
    binding=a.approve();v=binding.to_dict();v.update(change)
    forged=ApprovalBinding.from_dict(v)
    with pytest.raises(BulkError):move(a,c,"APPROVED",2,binding=forged,approval_record=a.record)
    assert len(c.archive.history(a.proposal.to_dict()["id"]))==2


@pytest.mark.parametrize("change",[
    {"actor":"synthetic-contributor"},{"package":{"category":"Playlist","kind":"poster","version":"1.0.0","sha256":"c"*64}},
    {"registry_sha256":"d"*64},{"compatibility_sha256":"e"*64},{"record_sha256":"f"*64},
])
def test_attributed_but_scope_wrong_decisions_still_block(isolated,change):
    a,c=isolated;move(a,c,"IMPLEMENTED",0);move(a,c,"COMPATIBLE",1)
    binding=a.approve(**change)
    with pytest.raises(BulkError):move(a,c,"APPROVED",2,binding=binding,approval_record=a.record)


@pytest.mark.parametrize("field",["registry_sha256","material_sha256","graph_sha256","source_commit","adoption_sha256"])
def test_replayed_proposal_changed_pins_are_rejected(isolated,field):
    a,c=isolated;move(a,c,"IMPLEMENTED",0)
    v=a.proposal.to_dict();v[field]="b"*(40 if field=="source_commit" else 64)
    with pytest.raises(BulkError):c.transition(Proposal.from_dict(v),a.gates,"COMPATIBLE",expected_revision=1)


@pytest.mark.parametrize("gate",GATES)
def test_missing_or_forged_gate_never_ready(isolated,gate):
    a,c=isolated;approved(a,c)
    value=a.gates.to_dict();value["checks"][gate]="missing"
    with pytest.raises(BulkError):c.transition(a.proposal,GateEvidence.from_dict(value),"READY",expected_revision=3)
    # Even a trusted fixture verifier reporting a missing prerequisite blocks.
    a.gates=GateEvidence.from_dict(value)
    with pytest.raises(BulkError):move(a,c,"READY",3)


@pytest.mark.parametrize("change",[
    {"actor":"synthetic-maintainer"},{"event_id":"synthetic.contract-decision"},
    {"proposal_sha256":"b"*64},{"approval_sha256":"c"*64},{"gate_sha256":"d"*64},{"runtime_id":"synthetic.other-runtime"},
])
def test_independent_operator_exact_context_not_artwork_or_contract_approval(isolated,change):
    a,c=isolated;binding=approved(a,c);move(a,c,"READY",3)
    with pytest.raises(BulkError):
        decision=a.operate(c,binding,**change)
        move(a,c,"ACTIVE",4,operator=decision)
    assert len(c.archive.history(a.proposal.to_dict()["id"]))==4


def test_expiry_revocation_and_restart_never_reanimate_active(isolated):
    a,c=isolated;binding=active(a,c);identity=a.proposal.to_dict()["id"]
    reopened=Controller(c.archive.contracts.root,simulation=a,clock=lambda:a.now);a.attach(reopened)
    assert reopened.inspect(identity)["state"]=="SUSPENDED"
    assert reopened.inspect(identity)["blockers"]==["activation_restart"]
    c.clock=lambda:a.now+timedelta(hours=2)
    assert c.inspect(identity)["state"]=="SUSPENDED"
    c.clock=lambda:a.now;a.revoked.add(binding.to_dict()["event_id"])
    assert c.inspect(identity)["state"]=="REVOKED"
    with pytest.raises(BulkError):c.rollback(identity,expected_revision=5,restore_sha256=c.archive.history(identity)[0].sha256)
    c.reconcile(identity,expected_revision=5)
    with pytest.raises(BulkError):c.rollback(identity,expected_revision=6,restore_sha256=c.archive.history(identity)[0].sha256)
    assert c.inspect(identity)["state"]=="REVOKED"
    assert c.archive.contracts.read_record(a.record.to_dict()["id"],1)==a.record


def test_source_change_suspends_active_and_preserves_all_receipts(isolated):
    a,c=isolated;active(a,c);value=a.graph.data()
    value["nodes"]["asset:synthetic.png"]["sha256"]=fingerprint("different same-size bytes")
    a.current_graph=Snapshot.create(value)
    result=c.inspect(a.proposal.to_dict()["id"])
    assert result["state"]=="SUSPENDED" and result["blockers"]==["activation_material_changed"]
    c.reconcile(a.proposal.to_dict()["id"],expected_revision=5)
    assert len(c.archive.history(a.proposal.to_dict()["id"]))==6
    assert c.archive.contracts.read_record(a.record.to_dict()["id"],1)==a.record


def test_new_material_proposal_cannot_reuse_old_contract_decision(isolated):
    a,c=isolated;binding=active(a,c);identity=a.proposal.to_dict()["id"]
    value=a.graph.data();value["nodes"]["asset:synthetic.png"]["sha256"]=fingerprint("replacement synthetic source")
    a.current_graph=Snapshot.create(value);c.reconcile(identity,expected_revision=5)
    replacement=SyntheticAuthority(a.contract,a.current_graph,now=a.now)
    fresh=Controller(c.archive.contracts.root,simulation=replacement,clock=lambda:a.now);replacement.attach(fresh)
    move(replacement,fresh,"COMPATIBLE",6)
    # Even an otherwise externally attributed prior decision cannot be replayed
    # onto the new material attestation/registry. Retain its old receipt.
    replacement.events[binding.to_dict()["event_id"]]=binding.sha256
    with pytest.raises(BulkError):move(replacement,fresh,"APPROVED",7,binding=binding,approval_record=a.record)
    assert fresh.archive.contracts.read_record(a.record.to_dict()["id"],1)==a.record
    assert fresh.archive.history(identity)[-1].to_dict()["approval_sha256"] is None


def test_unreviewed_added_pair_cannot_bypass_complete_selected_membership(isolated):
    a,c=isolated;active(a,c);value=a.graph.data()
    for size,other in (("standard","bigger"),("bigger","standard")):
        identity="synthetic.added."+size;key="output:"+identity
        value["nodes"][key]={"kind":"output","identity":identity,"sha256":fingerprint(identity),"dependencies":["asset:synthetic.png"]}
        row=deepcopy(value["outputs"]["synthetic.overlay."+size])
        row.update(node=key,local_path=size+"/Added.png",companions=["synthetic.added."+other])
        value["outputs"][identity]=row
    a.current_graph=Snapshot.create(value)
    status=c.inspect(a.proposal.to_dict()["id"])
    assert status["state"]=="SUSPENDED" and status["blockers"]==["activation_membership"]


def test_unrelated_source_change_keeps_selected_material_approval_current(tmp_path):
    prototype=fixture_authority();v=prototype.graph.data();h=fingerprint("synthetic unrelated")
    v["nodes"]["asset:unrelated.png"]={"kind":"asset","identity":"unrelated.png","sha256":h,"dependencies":[]}
    v["nodes"]["output:synthetic.unrelated"]={"kind":"output","identity":"synthetic.unrelated","sha256":h,"dependencies":["asset:unrelated.png"]}
    v["outputs"]["synthetic.unrelated"]={"node":"output:synthetic.unrelated","category":"Playlist","kind":"poster","variant":"synthetic",
        "local_path":"unrelated/Synthetic.jpg","public_path":None,"companions":[],"context_sha256":h,
        "evidence":{"previews":[],"confirmations":[],"decisions":[],"receipts":[]}}
    a=SyntheticAuthority(prototype.contract,Snapshot.create(v));c=Controller(tmp_path/"unrelated",simulation=a,clock=lambda:a.now);a.attach(c)
    active(a,c);v["nodes"]["asset:unrelated.png"]["sha256"]=fingerprint("changed unrelated")
    a.current_graph=Snapshot.create(v)
    assert c.inspect(a.proposal.to_dict()["id"])["state"]=="ACTIVE"


def test_revocation_between_preflight_and_transaction_commit_never_commits_active(isolated):
    a,c=isolated;binding=approved(a,c);move(a,c,"READY",3)
    decision=a.operate(c,binding)
    with pytest.raises(BulkError):
        move(a,c,"ACTIVE",4,operator=decision,before_commit=lambda:a.revoked.add(binding.to_dict()["event_id"]))
    assert len(c.archive.history(a.proposal.to_dict()["id"]))==4
    assert c.inspect(a.proposal.to_dict()["id"])["state"]=="REVOKED"


def test_actual_m5_impact_preserves_unaffected_decisions_and_reports_unknown_scope():
    from create_defaults.bulk.tests.test_expanded_validation import graph_fixture
    before=Snapshot.create(graph_fixture());v=before.data()
    v["nodes"]["asset:logos/A.png"]["sha256"]=fingerprint("changed source")
    after=Snapshot.create(v);report=assess(before,after)
    assert set(report["affected_outputs"])=={"playlist.p","separators.child"}
    assert report["affected_contracts"]==["Playlist","Separators"]
    assert "network.q" in report["unaffected_outputs"]
    assert {x["output"] for x in report["evidence_requiring_review"]["decisions"]}=={"playlist.p","separators.child"}
    unknown=assess(before,after,changed=["asset:not-in-graph.png"])
    assert unknown["activation_blocked"] and not unknown["impact_complete"]
    font=assess(before,before,changed=["asset:fonts/Font.ttf"])
    assert set(font["affected_outputs"])=={"playlist.p","network.q","separators.child"}
    assert set(font["direct_outputs"])=={"playlist.p","network.q"}
    assert font["transitive_outputs"]==["separators.child"]
    companion=assess(before,before,changed=["output:overlay.standard"])
    assert companion["required_companions"]==["overlay.bigger"]


def test_directory_namespace_change_with_preserved_timestamp_blocks_readiness(tmp_path,monkeypatch):
    import os
    from create_defaults.bulk.contracts.categories import evidence
    from create_defaults.bulk.tests.test_categories_sources import record
    source=tmp_path/"Logo.png";source.write_bytes(b"original")
    before=tmp_path.stat();original=evidence.sha256
    def changed(path):
        checksum=original(path)
        (tmp_path/"Unreviewed.png").write_bytes(b"new entry")
        os.utime(tmp_path,ns=(before.st_atime_ns,before.st_mtime_ns))
        return checksum
    monkeypatch.setattr(evidence,"sha256",changed)
    with pytest.raises(BulkError,match="entries changed"):
        evidence.verify_inputs([record([{"path":"Logo.png","sha256":hashlib.sha256(b"original").hexdigest()}])],tmp_path)


@pytest.mark.parametrize("missing",["synthetic.overlay.standard","synthetic.overlay.bigger"])
def test_missing_companion_variants_block_before_approval(isolated,missing):
    a,c=isolated;value=a.graph.data();del value["outputs"][missing];del value["nodes"]["output:"+missing]
    with pytest.raises(BulkError):Snapshot.create(value)
    assert not c.archive.history(a.proposal.to_dict()["id"])


def test_new_poster_logo_only_and_forged_publication_are_rejected(isolated):
    a,c=isolated;value=a.gates.to_dict();value.update(review_kind="new-poster",preview_type="logo-only")
    with pytest.raises(BulkError,match="composition"):GateEvidence.from_dict(value)
    for cls,doc in ((GateEvidence,a.gates),(ApprovalBinding,a.approve()),(OperatorDecision,a.operate(c,a.approve()))):
        value=doc.to_dict();value["publication_authorized"]=True
        with pytest.raises(BulkError):cls.from_dict(value)


@pytest.mark.parametrize("content",[
    {"source":{"path":"synthetic.png","sha256":"a"*64,"white_wash":True}},
    {"composer":{"white_wash":True}},{"profile":{"font_size":1}},
    {"generated_child":{"composer":{"font_size":1}}},{"approved_exception":True},
    {"source":{"path":"synthetic.png","sha256":"a"*64,"intentional_background_approved":True}},
])
def test_bypass_intent_cannot_become_approval(isolated,content):
    a,c=isolated
    with pytest.raises(BulkError):a.contract.validate_content("synthetic-color",content)
    # After rejected intent there is still no compatible/approved/active stream.
    assert not c.archive.history(a.proposal.to_dict()["id"])


@pytest.mark.parametrize("corrupt",[False,True])
@pytest.mark.parametrize("blob",["contract","registry","compatibility","adoption"])
def test_missing_or_corrupted_immutable_evidence_never_active(isolated,corrupt,blob):
    a,c=isolated;active(a,c)
    document=getattr(a,blob);path=c.archive.contracts._blob_path(document.sha256)
    if corrupt:path.write_bytes(b'{}')
    else:path.unlink()  # An individual synthetic blob, never a production receipt.
    result=c.inspect(a.proposal.to_dict()["id"])
    assert result["state"]=="SUSPENDED"


def test_corrupted_state_chain_fails_closed_and_readonly_inspection_preserves_files(isolated):
    a,c=isolated;active(a,c);identity=a.proposal.to_dict()["id"]
    root=c.archive.contracts.root
    before={str(p.relative_to(root)):(p.stat().st_size,p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
    assert len(Archive.inspect_readonly(root,identity))==5
    after={str(p.relative_to(root)):(p.stat().st_size,p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
    assert before==after
    c.archive.contracts._blob_path(c.archive.history(identity)[1].sha256).write_bytes(b'{}')
    with pytest.raises(BulkError):c.inspect(identity)


@pytest.mark.parametrize("at",["proposal","approval","activation"])
def test_interrupted_transaction_rolls_back_state_record_and_event(isolated,at):
    a,c=isolated
    def crash():raise SystemExit("synthetic process interruption")
    if at=="proposal":target="IMPLEMENTED";revision=0;kwargs={}
    elif at=="approval":
        move(a,c,"IMPLEMENTED",0);move(a,c,"COMPATIBLE",1)
        target="APPROVED";revision=2;kwargs={"binding":a.approve(),"approval_record":a.record}
    else:
        binding=approved(a,c);move(a,c,"READY",3)
        target="ACTIVE";revision=4;kwargs={"operator":a.operate(c,binding)}
    with pytest.raises(SystemExit):move(a,c,target,revision,before_commit=crash,**kwargs)
    assert len(c.archive.history(a.proposal.to_dict()["id"]))==revision
    with c.archive.store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM events WHERE kind='contract_activation_revision'").fetchone()[0]==revision
    if at=="approval":
        with pytest.raises(BulkError):c.archive.contracts.read_record(a.record.to_dict()["id"],1)
    # Same exact proposal is safe to retry after rollback; orphan blobs confer no authority.
    move(a,c,target,revision,**kwargs)


def test_actual_process_termination_mid_transaction_and_restart(isolated):
    a,c=isolated;root=c.archive.contracts.root
    code="""import os,sys
from pathlib import Path
from create_defaults.bulk.contracts.activation import Controller
from create_defaults.bulk.contracts.activation.simulation import fixture_authority
a=fixture_authority();c=Controller(Path(sys.argv[1]),simulation=a);a.attach(c)
c.transition(a.proposal,a.gates,'IMPLEMENTED',expected_revision=0,before_commit=lambda:os._exit(23))
"""
    result=subprocess.run([sys.executable,"-c",code,str(root)],capture_output=True,text=True,timeout=60)
    assert result.returncode==23,result.stderr
    restarted=Controller(root,simulation=a);a.attach(restarted)
    assert restarted.archive.history(a.proposal.to_dict()["id"])==()
    move(a,restarted,"IMPLEMENTED",0)


def test_simultaneous_operators_compare_and_swap_and_stale_revision(isolated):
    a,c=isolated;move(a,c,"IMPLEMENTED",0)
    def attempt():
        try:return move(a,c,"COMPATIBLE",1).sha256
        except Conflict:return "stale"
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:attempt(),range(2)))
    assert results.count("stale")==1
    with pytest.raises(Conflict):move(a,c,"APPROVED",1,binding=a.approve(),approval_record=a.record)
    assert len(c.archive.history(a.proposal.to_dict()["id"]))==2


def test_rollback_restore_valid_snapshot_never_restores_active_authority(isolated):
    a,c=isolated;active(a,c);identity=a.proposal.to_dict()["id"];history=c.archive.history(identity)
    restored=c.rollback(identity,expected_revision=5,restore_sha256=history[1].sha256)
    assert restored.to_dict()["state"]=="SUSPENDED" and restored.to_dict()["restored_from_sha256"]==history[1].sha256
    assert len(c.archive.history(identity))==6
    assert c.archive.contracts.read_record(a.record.to_dict()["id"],1)==a.record
    with c.archive.store.transaction() as db:
        with pytest.raises(sqlite3.DatabaseError):db.execute("DELETE FROM contract_activation_revisions")


def test_restored_database_snapshot_rechecks_current_external_revocation(tmp_path,isolated):
    a,c=isolated;binding=active(a,c);identity=a.proposal.to_dict()["id"]
    snapshot=tmp_path/"restored-snapshot";shutil.copytree(c.archive.contracts.root,snapshot)
    a.revoked.add(binding.to_dict()["event_id"])
    restored=Controller(snapshot,simulation=a,clock=lambda:a.now);a.read_object=restored.archive.contracts.read_object
    assert restored.inspect(identity)["recorded_state"]=="ACTIVE"
    assert restored.inspect(identity)["state"]=="REVOKED"
    assert len(restored.archive.history(identity))==5


def test_committed_operator_decision_cannot_reactivate_after_rollback(isolated):
    a,c=isolated;binding=active(a,c);identity=a.proposal.to_dict()["id"];history=c.archive.history(identity)
    old_operator=OperatorDecision.from_bytes(c.archive.contracts.read_object(history[-1].to_dict()["operator_sha256"]))
    c.rollback(identity,expected_revision=5,restore_sha256=history[1].sha256)
    move(a,c,"COMPATIBLE",6)
    move(a,c,"APPROVED",7,binding=binding,approval_record=a.record)
    move(a,c,"READY",8)
    with pytest.raises(BulkError,match="reactivation"):
        move(a,c,"ACTIVE",9,operator=old_operator)
    fresh=a.operate(c,binding,event_id="synthetic.operator.after-rollback")
    move(a,c,"ACTIVE",9,operator=fresh)
    assert c.inspect(identity)["state"]=="ACTIVE"
    assert len(c.archive.history(identity))==10


def test_exact_proposal_validation_never_authenticates_unsigned_context(tmp_path,isolated,category_implementation,monkeypatch,capsys):
    from create_defaults.bulk.contracts.categories.release import Implementation
    from create_defaults.bulk.contracts.registry import package_reference
    a,_=isolated;v=a.proposal.to_dict();package=category_implementation.select("Overlays")
    v.update(id="defaults.overlays.overlay",namespace="isolated",package=package_reference(package.contract))
    proposal=Proposal.from_dict(v);path=tmp_path/"proposal.json";path.write_bytes(proposal.encoded)
    monkeypatch.setattr(Implementation,"load",lambda **kw:category_implementation)
    assert main(["validate-proposal","--proposal",str(path),"--proposal-sha256",proposal.sha256])==0
    result=json.loads(capsys.readouterr().out)
    assert result["structurally_valid"] and not result["activation_eligible"]
    assert result["pins"]["registry"]=="missing_authenticated_selection"
    assert main(["validate-proposal","--proposal",str(path),"--proposal-sha256","f"*64])==1
    assert not json.loads(capsys.readouterr().out)["production_enforcement"]


def test_production_integration_pins_and_cli_are_readonly(tmp_path,monkeypatch,capsys,category_implementation):
    report=verify();assert report["production_files_verified"]==190
    assert report["actual_contracts_active"]==report["production_hooks"]==report["production_flags"]==0
    def prohibited(*a,**k):pytest.fail("read-only CLI opened a state writer")
    monkeypatch.setattr(Archive,"__init__",prohibited)
    from create_defaults.bulk.contracts.categories.release import Implementation
    monkeypatch.setattr(Implementation,"load",lambda **kw:category_implementation)
    assert main([])==0
    result=json.loads(capsys.readouterr().out)
    assert result["selectors"]==22 and result["variants"]==278
    assert result["exact_approvals_missing"]==22 and result["ready"]==result["active"]==0
    assert all(p["enforcement_state"]=="IMPLEMENTED" for p in result["packages"])


def test_changes_outside_explicit_m7_scope_are_rejected():
    # Audit the accepted M7 implementation, not every future maintenance PR.
    # Current production bytes remain checked by verify() against all 190 pins.
    root=Path(__file__).parents[3]
    changed=subprocess.check_output(["git","diff","--name-only","c00a0f0b8efcb98857d24da659a30eb06043d6b0","0b6f479f2ddb3c8d11fc48a92b9d0cfddd3b4293"],cwd=root,text=True).splitlines()
    allowed=("create_defaults/bulk/contracts/activation/",
        "create_defaults/bulk/tests/test_activation","create_defaults/bulk/tests/conftest.py",
        "create_defaults/bulk/tests/test_categories_historical.py","create_defaults/bulk/contracts/categories/evidence.py",
        "create_defaults/lifecycle/PHASE2_M7_",
        "create_defaults/lifecycle/evidence/phase2-m7-","create_defaults/lifecycle/ROADMAP.md")
    assert all(n.startswith(allowed) for n in changed),changed


def test_authorized_people_maintenance_preserves_other_m7_pins():
    from create_defaults.bulk.contracts.activation import protection
    root=Path(__file__).parents[3]
    path="create_defaults/bulk/contracts/activation/data/production-pins-v1.json"
    accepted=json.loads(subprocess.check_output(["git","show",
        "0b6f479f2ddb3c8d11fc48a92b9d0cfddd3b4293:"+path],cwd=root))
    selected=json.loads((root/path).read_text(encoding="utf8"))
    sweeper="create_people_posters/grayscale_sweeper.py"
    workflow=".github/workflows/default-poster-validation.yml"
    assert len(accepted["files"])==len(selected["files"])==190
    assert accepted["files"].keys()==selected["files"].keys()
    # Explicitly authorized CI maintenance changes one additional protected file.
    # Keep the accepted M7 and People source identities independently anchored.
    assert {n for n in accepted["files"] if accepted["files"][n]!=selected["files"][n]}=={sweeper,workflow}
    assert selected["files"][sweeper]==hashlib.sha256((root/sweeper).read_bytes().replace(b"\r\n",b"\n")).hexdigest()
    assert selected["historical_syntax_exceptions"]==[]
    assert selected["maintenance_context"]["previous_manifest_sha256"]==fingerprint(accepted)
    # Overrides record the historical People/CI transition, not the later
    # separately approved M5 workflow transition. Verify both exact steps;
    # never rewrite old provenance or treat the two hashes as interchangeable.
    from ci.phase4_transactions import verify_maintenance as verify_m5_maintenance
    verify_m5_maintenance(root)
    prior=json.loads(subprocess.check_output(["git","show",
        "d05dc70167a4b3c4185fc20e81fdf91a88dde020:"+path],cwd=root))
    assert selected["maintenance_context"]["overrides"]==prior["maintenance_context"]["overrides"]
    assert selected["maintenance_context"]["overrides"]==[{
        "path":sweeper,"previous_sha256":accepted["files"][sweeper],"sha256":selected["files"][sweeper]},
        {"path":workflow,"previous_sha256":accepted["files"][workflow],"sha256":prior["files"][workflow]}]
    people_baseline=json.loads(subprocess.check_output(["git","show",
        "d35b0684a096277dcdbdea70e4683e0c786325bc:"+path],cwd=root))
    assert selected["maintenance_context"]["ci_previous_manifest_sha256"]==fingerprint(people_baseline)
    assert {n for n in people_baseline["files"] if people_baseline["files"][n]!=selected["files"][n]}=={workflow}
    assert selected["files"][sweeper]==people_baseline["files"][sweeper]
    assert fingerprint(selected)==protection.PRODUCTION_PINS_SHA256
    assert verify()["production_files_verified"]==190


@pytest.fixture
def production_guard_copy(tmp_path,monkeypatch):
    """Disposable copies only; never mutate real source or activation state."""
    from create_defaults.bulk.contracts.activation import protection
    root=Path(__file__).parents[3]
    pins=json.loads((protection.HERE/"data/production-pins-v1.json").read_text(encoding="utf8"))
    copied=tmp_path/"source"
    for name in pins["files"]:
        target=copied/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/name,target)
    here=tmp_path/"guard";data=here/"data/production-pins-v1.json"
    data.parent.mkdir(parents=True);data.write_bytes(canonical(pins))
    monkeypatch.setattr(protection,"HERE",here)
    assert protection.verify(root=copied)["production_files_verified"]==190
    return protection,copied,pins,data


@pytest.mark.parametrize("name",[
    "create_people_posters/grayscale_sweeper.py",
    "create_defaults/create_poster.py",
    ".github/workflows/default-poster-validation.yml",
])
def test_production_guard_rejects_unexpected_source_changes(production_guard_copy,name):
    protection,root,_,_=production_guard_copy
    path=root/name;path.write_bytes(path.read_bytes()+b"\n# unauthorized change\n")
    with pytest.raises(BulkError) as error:protection.verify(root=root)
    assert error.value.code=="activation_production_changed"
    assert name in str(error.value)


@pytest.mark.parametrize("addition",[
    b"\nimport create_defaults.bulk.contracts.activation\n",
    b"\nfrom create_defaults.bulk.contracts.activation import Controller\n",
    b"\nactivation_command = 'activation-controller'\n",
])
def test_production_guard_rejects_activation_even_with_matching_test_pin(production_guard_copy,monkeypatch,addition):
    protection,root,pins,data=production_guard_copy
    name="create_people_posters/grayscale_sweeper.py";path=root/name
    path.write_bytes(path.read_bytes()+addition)
    # A matching synthetic pin deliberately gets past integrity validation to
    # exercise the independent AST nonintegration guard. Never import/execute it.
    pins["files"][name]=hashlib.sha256(path.read_bytes().replace(b"\r\n",b"\n")).hexdigest()
    data.write_bytes(canonical(pins))
    monkeypatch.setattr(protection,"PRODUCTION_PINS_SHA256",fingerprint(pins))
    with pytest.raises(BulkError) as error:protection.verify(root=root)
    assert error.value.code=="activation_production_import"


def test_production_guard_rejects_unapproved_pin_removal(production_guard_copy):
    protection,root,pins,data=production_guard_copy
    del pins["files"]["create_people_posters/grayscale_sweeper.py"]
    data.write_bytes(canonical(pins))
    with pytest.raises(BulkError) as error:protection.verify(root=root)
    assert error.value.code=="activation_production_pin"


def test_simulation_cli_round_trip_never_activates_actual_contracts(tmp_path,capsys):
    assert main(["simulate","--state-root",str(tmp_path/"simulation")])==0
    result=json.loads(capsys.readouterr().out)
    assert result["synthetic_only"] and result["active_simulation"]["state"]=="ACTIVE"
    assert result["recovered"]["state"]=="SUSPENDED" and result["actual_contracts_activated"]==0
