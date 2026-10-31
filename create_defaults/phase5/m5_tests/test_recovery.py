"""P5-T22/T23/T25/T27 actual commits/pushes and immutable forward recovery."""
import json
import subprocess
import sys

import pytest
from create_defaults.bulk.common import BulkError,Conflict,canonical,fingerprint
from create_defaults.bulk.lifecycle.catalog_preparation import git
from create_defaults.bulk.lifecycle.publication_preparation import run_offline,inspect_transport
from create_defaults.bulk.lifecycle.preparation_progress import Progress,recover,KIND
from create_defaults.bulk.lifecycle.package_e import SidecarStore
from create_defaults.phase5.m5_tests.helpers import prepared


@pytest.mark.parametrize('boundary',['before_intent','intent_object','after_intent','progress_object','before_progress_commit','after_progress_commit'])
def test_P5_T22_intent_and_transaction_faults_are_recoverable(native,boundary):
    selection,patch,target,result=prepared(native)
    fired=[]
    def checkpoint(name):
        if name==boundary and not fired:fired.append(name);raise RuntimeError('injected')
    with pytest.raises(RuntimeError):run_offline(result,selection,patch,target,checkpoint=checkpoint)
    assert fired==[boundary]
    report=run_offline(result,selection,patch,target)
    assert report['complete'] and report['network_writes']==0


@pytest.mark.parametrize('point',['after_commit','after_push'])
def test_P5_T23_actual_commit_and_ambiguous_push_reobserve_before_retry(native,point):
    selection,patch,target,result=prepared(native)
    with pytest.raises(BulkError) as interrupted:
        run_offline(result,selection,patch,target,fail_at=point)
    assert interrupted.value.code=='injected_interruption'
    progress=Progress(selection.registry.operations.root,result).read()
    assert progress['state']=='UNKNOWN'
    root=target.trial.root/('m5-transport-'+result.sha256)
    observation=inspect_transport(result,target,root)
    assert observation['verified_batches']==(1 if point=='after_push' else 0)
    local=git(root/'work','rev-parse','HEAD')
    report=run_offline(result,selection,patch,target)
    assert report['complete'] and git(root/'work','rev-parse','HEAD')==local
    assert len(report['commits'])==1


def test_P5_T22_cancel_before_transport_preserves_intent(native):
    selection,patch,target,result=prepared(native)
    with pytest.raises(BulkError,match='cancelled'):run_offline(result,selection,patch,target,cancel=lambda:True)
    assert Progress(selection.registry.operations.root,result).read()['state']=='PREPARED'
    assert run_offline(result,selection,patch,target)['complete']


def test_P5_T27_cold_read_only_replay_requires_fresh_observation(native):
    selection,patch,target,result=prepared(native)
    assert run_offline(result,selection,patch,target)['complete']
    code="""
import json,sys
from unittest.mock import patch
from create_defaults.bulk.lifecycle.preparation_progress import recover
from create_defaults.bulk.lifecycle.package_e import SidecarStore
with patch.object(SidecarStore,'__init__',side_effect=AssertionError('writer on cold replay')):
 print(json.dumps(recover(sys.argv[1],sys.argv[2]),sort_keys=True))
"""
    child=subprocess.run([sys.executable,'-c',code,str(selection.registry.operations.root),result.sha256],capture_output=True,text=True,timeout=180)
    assert child.returncode==0,child.stderr
    assert json.loads(child.stdout)==recover(selection.registry.operations.root,result.sha256)
    assert not json.loads(child.stdout)['publication_authorized']
    # Reobservation, not the archived complete flag, is required on resume.
    git(patch.source.root,'commit','--allow-empty','-m','New source epoch')
    with pytest.raises(BulkError,match='stale_source'):run_offline(result,selection,patch,target)


def test_P5_T27_missing_immutable_progress_object_blocks(native):
    selection,patch,target,result=prepared(native)
    run_offline(result,selection,patch,target)
    store=SidecarStore(selection.registry.operations.root)
    with store.read_connection() as db:
        ref=json.loads(db.execute('SELECT payload FROM events WHERE kind=? ORDER BY sequence DESC',(KIND,)).fetchone()[0])['sha256']
    path=store.root/'objects'/(ref+'.json');raw=path.read_bytes()
    try:
        path.write_bytes(b'{}')
        with pytest.raises(BulkError):recover(store.root,result.sha256)
    finally:path.write_bytes(raw)


def test_P5_T25_partial_membership_cannot_be_marked_complete(native):
    selection,patch,target,result=prepared(native)
    progress=Progress(selection.registry.operations.root,result)
    prior=progress.append('PREPARED',0,None,expected=None)
    with pytest.raises(BulkError,match='actual_observation_required'):
        progress.append('OFFLINE_VERIFIED',1,'0'*40,expected=prior)
    assert progress.read()==prior


def test_P5_T22_progress_CAS_rejects_stale_writer(native):
    selection,patch,target,result=prepared(native)
    progress=Progress(selection.registry.operations.root,result)
    prior=progress.append('PREPARED',0,None,expected=None)
    with pytest.raises(Conflict):progress.append('UNKNOWN',0,None,expected=None,error=RuntimeError('x'))
    assert progress.read()==prior


def test_P5_T27_resealed_journal_cannot_forge_types_or_progress(native):
    from create_defaults.bulk.lifecycle.preparation_progress import _read
    selection,patch,target,result=prepared(native)
    store=SidecarStore(selection.registry.operations.root)
    progress=Progress(store.root,result)
    prior=progress.append('PREPARED',0,None,expected=None)
    for mutation in ('version_bool','missing_observation','unknown_increase','prepared_again','extra_field'):
        forged={k:v for k,v in prior.items() if k!='sha256'}
        forged.update(revision=2,previous_sha256=prior['sha256'],state='UNKNOWN')
        if mutation=='version_bool':forged['version']=True
        elif mutation=='missing_observation':forged.update(state='OFFLINE_VERIFIED',verified_batches=1)
        elif mutation=='unknown_increase':forged.update(verified_batches=1,head='a'*40)
        elif mutation=='prepared_again':forged['state']='PREPARED'
        else:forged['unreviewed']='extra'
        checksum=fingerprint(forged)
        store.put_object(canonical(forged),expected_sha256=checksum)
        # An actual sealed object/event still cannot legitimize these records.
        # The failed transaction rolls back only this adversarial fixture insert.
        with pytest.raises(BulkError),store.transaction() as db:
            store.event(db,KIND,result.sha256,dict(sha256=checksum))
            _read(store,db,result)
        assert progress.read()==prior


@pytest.mark.parametrize('command',['add','commit'])
def test_P5_T22_local_object_or_commit_failure_finishes_only_owned_staging(native,monkeypatch,command):
    from create_defaults.bulk import library_transport
    selection,patch,target,result=prepared(native)
    original=library_transport.git;fired=[]
    def inject(root,*args,**kwargs):
        if args[0]==command and not fired:fired.append(command);raise BulkError('fixture_git_failure','injected')
        return original(root,*args,**kwargs)
    with monkeypatch.context() as context:
        context.setattr(library_transport,'git',inject)
        with pytest.raises(BulkError,match='injected'):run_offline(result,selection,patch,target)
    assert fired
    completed=run_offline(result,selection,patch,target)
    assert completed['complete'] and len(completed['commits'])==1
