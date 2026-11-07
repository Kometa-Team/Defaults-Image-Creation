"""Interrupted real bare-Git transport and strict immutable forward recovery."""
import json,subprocess,sys
import pytest
from create_defaults.bulk.common import BulkError,Conflict,canonical,fingerprint
from create_defaults.bulk.lifecycle.draft_transport import run_offline,OfflineProtocol
from create_defaults.bulk.lifecycle.draft_progress import DraftProgress,recover,KIND,_read
from create_defaults.bulk.lifecycle.package_e import SidecarStore
from create_defaults.bulk.lifecycle.catalog_preparation import git
from create_defaults.phase5.m6_tests.helpers import connected


@pytest.mark.parametrize('boundary',['after_commit','after_push'])
def test_M6_interrupted_push_reconciles_exact_prefix(native,boundary):
    protocol,c=connected(native)
    with pytest.raises(BulkError) as error:run_offline(protocol,fail_at=boundary)
    assert error.value.code=='injected_interruption'
    journal=DraftProgress(c.selection.registry.operations.root,c.binding)
    assert journal.read()['state']=='UNKNOWN'
    actual=OfflineProtocol.inspect(protocol)
    assert actual['verified_batches']==(boundary=='after_push')
    local=git(c.root/'transport/work','rev-parse','HEAD')
    resumed=run_offline(protocol)
    assert resumed['draft_verified'] and len(resumed['commits'])==1
    assert git(c.root/'transport/work','rev-parse','HEAD')==local


def test_M6_accepted_push_with_lost_ack_is_reobserved(native,monkeypatch):
    from create_defaults.bulk import library_stage
    protocol,c=connected(native);original=library_stage.git;fired=[]
    def lost(root,*args,**kwargs):
        result=original(root,*args,**kwargs)
        if args[0]=='push' and not fired:
            fired.append(True);raise BulkError('fixture_lost_ack','No acknowledgement')
        return result
    with monkeypatch.context() as context:
        context.setattr(library_stage,'git',lost)
        result=run_offline(protocol)
    assert fired and result['draft_verified'] and len(result['commits'])==1
    journal=json.loads((c.root/'transport/journal.json').read_bytes())
    assert any(e['event']=='ambiguous_push' for e in journal['events'])


def test_M6_cold_replay_is_read_only_and_never_authority(native):
    protocol,c=connected(native);run_offline(protocol)
    root=c.selection.registry.operations.root
    code="""
import json,sys
from unittest.mock import patch
from create_defaults.bulk.lifecycle.draft_progress import recover
from create_defaults.bulk.lifecycle.package_e import SidecarStore
with patch.object(SidecarStore,'__init__',side_effect=AssertionError('writer')):
 print(json.dumps(recover(sys.argv[1],sys.argv[2]),sort_keys=True))
"""
    result=subprocess.run([sys.executable,'-c',code,str(root),c.binding.sha256],capture_output=True,text=True,timeout=180)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)==recover(root,c.binding.sha256)
    git(c.patch.source.root,'commit','--allow-empty','-m','New offline source epoch')
    with pytest.raises(BulkError,match='stale_source'):run_offline(protocol)


def test_M6_journal_cas_and_forged_progress_fail_closed(native):
    protocol,c=connected(native);root=c.selection.registry.operations.root
    progress=DraftProgress(root,c.binding);prior=progress.read();store=SidecarStore(root)
    with pytest.raises(BulkError) as invalid:
        progress.append('UNKNOWN',expected=None,error=RuntimeError('x'))
    assert type(invalid.value) is BulkError and invalid.value.code=='p5m6_journal_unknown'
    assert progress.read()==prior
    stale=dict(prior,revision=prior['revision']-1)
    with pytest.raises(Conflict):progress.append('UNKNOWN',expected=stale,error=RuntimeError('x'))
    assert progress.read()==prior
    for attack in ('version','increase','prepared','complete','extra'):
        value={k:v for k,v in prior.items() if k!='sha256'}
        value.update(state='UNKNOWN',revision=2,previous_sha256=prior['sha256'])
        if attack=='version':value['version']=True
        elif attack=='increase':value.update(verified_batches=1,head='a'*40)
        elif attack=='prepared':value['state']='PREPARED'
        elif attack=='complete':value.update(state='OFFLINE_DRAFT_VERIFIED',verified_batches=1,head='a'*40)
        else:value['unreviewed']=True
        pin=fingerprint(value);store.put_object(canonical(value),expected_sha256=pin)
        with pytest.raises(BulkError),store.transaction() as db:
            store.event(db,KIND,c.binding.sha256,dict(sha256=pin));_read(store,db,c.binding)
        assert progress.read()==prior
    with pytest.raises(BulkError,match='actual_observation_required'):
        progress.append('OFFLINE_DRAFT_VERIFIED',expected=prior,observation={'complete':True})
    assert progress.read()==prior
