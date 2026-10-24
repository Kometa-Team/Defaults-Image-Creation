"""Native isolated ADD/UPDATE, atomic visibility and crash recovery."""
from dataclasses import replace
import json
from threading import Event

import pytest

from create_defaults.bulk.common import BulkError, Conflict, canonical
from create_defaults.bulk.lifecycle import apply
from create_defaults.bulk.lifecycle.operations import propose
from create_defaults.bulk.lifecycle.recovery import recover
from create_defaults.bulk.lifecycle.storage import OperationStore
from create_defaults.phase4.tests.transaction_samples import transaction_case, transaction, reviewed, update_candidate


def commit(case, tx, snap, **kw):
    return apply.commit_synthetic(tx,expected_snapshot_sha256=snap.sha256,authority=case['authority'],**kw)


def test_native_add_atomic_reopen_and_exact_retry(transaction_case):
    case=transaction_case;tx,snapshot=transaction(case)
    root=case['row'][0].config.cache_dir
    before=OperationStore(root).inspect()
    assert not recover(root)['outputs']
    result=commit(case,tx,snapshot)
    recovered=recover(root)
    import subprocess,sys
    code="""
import json,sys
from unittest.mock import patch
from create_defaults.bulk.lifecycle.package_e import SidecarStore
from create_defaults.bulk.lifecycle.recovery import recover
with patch.object(SidecarStore,'__init__',side_effect=AssertionError('recovery attempted a write')):
 print(json.dumps(recover(sys.argv[1]),sort_keys=True))
"""
    restart=subprocess.run([sys.executable,'-c',code,str(root)],capture_output=True,text=True,timeout=60)
    assert restart.returncode==0,restart.stderr
    assert json.loads(restart.stdout)==recovered
    assert result['isolated_committed'] and not result['retry']
    assert sorted(recovered['outputs'])==snapshot.to_dict()['members']
    for i,m in snapshot.to_dict()['artwork'].items():
        assert recovered['outputs'][i]['artwork']==m
    assert len(OperationStore(root).journal())==before['sequence']+1
    # The original M1 schema stays record-only/draft; the separate immutable
    # snapshot marker is isolated state, never real operational acceptance.
    assert OperationStore(root).history(tx.inputs.composition.impact.to_dict()['operation']['id'])[-1].to_dict()['state']=='draft'
    retry=commit(case,tx,snapshot)
    assert retry['retry'] and retry['snapshot_sha256']==result['snapshot_sha256']
    assert recover(root)==recovered
    for key in ('authenticated','operation_accepted','applied','ready','active','publication_authorized','contract_approved'):
        assert result[key] is False and recovered[key] is False
    from ci.validation import identity,write
    from ci.phase4_transactions import implementation_checksum, SCHEMA
    from ci.phase4 import checksum,fingerprint
    proof=dict(**identity(),kind='phase4-m5-native-transaction-proof',implementation_sha256=implementation_checksum(),
        schema_sha256=checksum(SCHEMA),snapshot_sha256=snapshot.sha256,members=snapshot.to_dict()['artwork'],
        appearance=snapshot.to_dict()['selected_appearance'],cohort='genre',contract_approvals_missing=22,
        isolated_committed=True,restart_verified=True,retry_verified=True,**{k:result[k] for k in ('authenticated','operation_accepted','applied','ready','active','publication_authorized','contract_approved')})
    proof['sha256']=fingerprint(proof)
    write(__import__('pathlib').Path('config/ci-validation/phase4-m5/phase4-m5-native-proof.json'),proof)


@pytest.mark.parametrize('point',['before_review','after_review','snapshot_blob','record_blob','event_blob','record_index','member_head','journal_index','receipt_index','before_commit'])
def test_fault_before_commit_preserves_all_prior_heads(transaction_case,monkeypatch,point):
    case=transaction_case;tx,snapshot=transaction(case);root=case['row'][0].config.cache_dir
    before=OperationStore(root).inspect();reviews=case['archive'].history()
    def fail(name):
        if name==point:raise OSError('injected '+point)
    monkeypatch.setattr(apply,'_checkpoint',fail)
    with pytest.raises(OSError,match='injected'):
        commit(case,tx,snapshot)
    assert OperationStore(root).inspect()==before
    assert case['archive'].history()==reviews
    assert recover(root)['outputs']=={} and recover(root)['commits']=={}
    monkeypatch.setattr(apply,'_checkpoint',lambda _:None)
    assert commit(case,tx,snapshot)['isolated_committed']


def test_crash_after_commit_recovers_without_double_application(transaction_case,monkeypatch):
    case=transaction_case;tx,snapshot=transaction(case);root=case['row'][0].config.cache_dir
    def crash(name):
        if name=='after_commit':raise OSError('lost success acknowledgement')
    monkeypatch.setattr(apply,'_checkpoint',crash)
    with pytest.raises(OSError,match='acknowledgement'):commit(case,tx,snapshot)
    state=recover(root);assert len(state['commits'])==1
    monkeypatch.setattr(apply,'_checkpoint',lambda _:None)
    assert commit(case,tx,snapshot)['retry']
    assert recover(root)==state


@pytest.mark.parametrize('point',['before','after_review','receipt_index'])
def test_cancellation_never_exposes_a_snapshot(transaction_case,monkeypatch,point):
    case=transaction_case;tx,snapshot=transaction(case);cancel=Event()
    if point=='before':cancel.set()
    def checkpoint(name):
        if name==point:cancel.set()
    monkeypatch.setattr(apply,'_checkpoint',checkpoint)
    with pytest.raises(BulkError,match='cancelled'):commit(case,tx,snapshot,cancel=cancel)
    assert not recover(case['row'][0].config.cache_dir)['commits']


def test_native_minimal_update_preserves_identity_and_old_evidence(transaction_case):
    case=transaction_case;tx,snapshot=transaction(case);first=commit(case,tx,snapshot)
    trial,ctx,_,_=case['row'];old=ctx.candidate
    before=recover(trial.config.cache_dir);old_review=case['archive'].history()
    candidate,frozen=update_candidate(case)
    next_ctx=propose(ctx.registry,before=frozen,candidate=candidate,identity='synthetic.operation.update',operation='UPDATE')
    next_case=reviewed(trial,next_ctx,label='updated')
    next_tx,next_snapshot=transaction(next_case,{i:first['snapshot_sha256'] for i in candidate.graph.index().outputs})
    result=commit(next_case,next_tx,next_snapshot)
    after=recover(trial.config.cache_dir)
    assert set(after['outputs'])==set(before['outputs'])
    assert len(after['commits'])==2 and result['snapshot_sha256']!=first['snapshot_sha256']
    assert next_snapshot.to_dict()['before_sha256']==old.sha256
    assert next_snapshot.to_dict()['entries'].keys()==snapshot.to_dict()['entries'].keys()
    for i in after['outputs']:
        assert after['outputs'][i]['artwork']['sha256']!=before['outputs'][i]['artwork']['sha256']
        assert next_snapshot.to_dict()['entries'][i]['names']['public_path']==snapshot.to_dict()['entries'][i]['names']['public_path']
        assert next_snapshot.to_dict()['entries'][i]['names']['source']['path']==snapshot.to_dict()['entries'][i]['names']['source']['path']
    assert {k:v for k,v in next_case['archive'].history().items() if k in old_review}==old_review
    # Old receipt/blob hashes and immutable commits still pass restart replay.
    assert before['commits'][ctx.impact.to_dict()['operation']['id']]==after['commits'][ctx.impact.to_dict()['operation']['id']]
