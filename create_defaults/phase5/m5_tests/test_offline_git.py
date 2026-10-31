"""P5-T16/T23/T24/T25/T30 native artifacts and isolated Package E Git."""
import json
from pathlib import Path
import pytest

from create_defaults.bulk.common import BulkError
from create_defaults.bulk.lifecycle.catalog_preparation import git
from create_defaults.bulk.lifecycle.publication_preparation import run_offline,inspect_transport
from create_defaults.bulk.lifecycle.preparation_progress import Progress
from create_defaults.phase5.m5_tests.helpers import prepared,export_native


def test_P5_T16_current_mapping_full_native_sequence_and_plan(current_native):
    selection,patch,target,result=prepared(current_native)
    from create_defaults.bulk.common import Conflict,fingerprint
    from create_defaults.bulk.lifecycle.operations import payload
    references={(r['kind'],r['id']):r for r in payload(current_native['snapshot'].to_dict()['intent_json'])['reads']}
    absent=[h for h in result.to_dict()['native_heads'] if h['revision']==0]
    assert absent and all(h==references[h['kind'],h['id']] and h['subjects'] for h in absent)
    from create_defaults.bulk.library_transport import run
    root=target.trial.root/('m5-transport-'+result.sha256)
    progress=Progress(selection.registry.operations.root,result)
    prior=progress.append('PREPARED',0,None,expected=None)
    run(result.to_dict()['plan'],root,target.root)
    observed=inspect_transport(result,target,root)
    progress.append('OFFLINE_VERIFIED',observed['verified_batches'],observed['head'],expected=prior,target=target)
    assert observed['complete'] and result.to_dict()['members'][0]['destination']=='genre/fixture.jpg'
    assert len({s.to_dict()['artwork'][s.to_dict()['members'][0]]['sha256'] for s in current_native['snapshots']})==3
    export_native(current_native,patch,target,result,observed,name='current')
    # A validly resealed preparation cannot invent an absent head's subjects.
    # The transaction must compare the accepted intent's scope independently.
    from create_defaults.bulk.lifecycle.preparation_models import Preparation
    forged=result.to_dict()
    next(h for h in forged['native_heads'] if h['revision']==0)['subjects']=['synthetic.item.'+'f'*64]
    forged['native_heads_sha256']=fingerprint(forged['native_heads'])
    with pytest.raises(Conflict):
        Progress(selection.registry.operations.root,Preparation.from_dict(forged)).append('PREPARED',0,None,expected=None)
    assert progress.read()['state']=='OFFLINE_VERIFIED'


def test_P5_T25_multi_member_partial_batches_forward_recover(multi_native):
    selection,patch,target,result=prepared(multi_native,max_files=1)
    assert len(result.to_dict()['required_members'])==2 and len(result.to_dict()['plan']['batches'])==2
    first=run_offline(result,selection,patch,target,stop_after=1)
    assert not first['complete'] and first['verified_batches']==1
    before=first['head'];second=run_offline(result,selection,patch,target)
    assert second['complete'] and second['verified_batches']==2
    assert git(target.trial.root/('m5-transport-'+result.sha256)/'remote.git','merge-base','--is-ancestor',before,second['head'])==b''
    export_native(multi_native,patch,target,result,second,name='multi')


@pytest.mark.parametrize('mutation',['foreign_ref','unrelated_tree','symlink_mode','same_bytes_case_collision'])
def test_P5_T30_actual_tree_or_namespace_substitution_fails(native,mutation):
    selection,patch,target,result=prepared(native)
    if mutation=='same_bytes_case_collision':
        path=result.to_dict()['members'][0]['destination'];raw=Path(result.to_dict()['members'][0]['source']).read_bytes()
        from create_defaults.bulk.lifecycle.publication_preparation import OfflineDestination,plan_operation
        alternate=OfflineDestination(target.trial,existing={'genre/'+Path(path).name.upper():raw})
        with pytest.raises(BulkError):plan_operation(selection,patch,alternate)
        # Build actual NFC/NFD Git entries without relying on the host's
        # filesystem Unicode normalization or case behavior.
        import subprocess
        from create_defaults.bulk.lifecycle.publication_preparation import tree
        blob=git(target.root,'hash-object','-w',result.to_dict()['members'][0]['source']).strip()
        entries=b''.join(b'100644 blob '+blob+b'\t'+name+b'\0' for name in sorted([
            'Caf\u00e9.jpg'.encode('utf8'),'Cafe\u0301.jpg'.encode('utf8')]))
        made=subprocess.run(['git','-C',str(target.root),'mktree','-z'],input=entries,check=True,capture_output=True).stdout.decode().strip()
        with pytest.raises(BulkError):tree(target.root,made)
        return
    run_offline(result,selection,patch,target)
    root=target.trial.root/('m5-transport-'+result.sha256);work=root/'work';remote=root/'remote.git'
    if mutation=='foreign_ref':git(remote,'update-ref','refs/heads/library-offline',result.to_dict()['destination']['head'])
    elif mutation=='unrelated_tree':
        (work/'foreign.txt').write_bytes(b'unrelated');git(work,'add','foreign.txt');git(work,'commit','-m','Foreign commit')
        git(work,'push',str(remote),'HEAD:refs/heads/library-offline')
    else:
        (work/'unsafe').write_bytes(b'foreign');git(work,'add','unsafe');git(work,'update-index','--cacheinfo','120000,'+git(work,'hash-object','unsafe').decode().strip()+',unsafe')
        git(work,'commit','-m','Unsafe link mode');git(work,'push',str(remote),'HEAD:refs/heads/library-offline')
    if mutation=='foreign_ref':
        # Rolling back a known successful local-only prefix is not silently
        # treated as a complete operation, even if that ref is a known ancestor.
        observation=inspect_transport(result,target,root)
        assert not observation['complete']
    else:
        with pytest.raises(BulkError):inspect_transport(result,target,root)


@pytest.mark.parametrize('status',['OPEN','CLOSED','MERGED','wrong-head','wrong-base','not-draft','duplicate'])
def test_P5_T24_existing_draft_reconciliation_is_isolated_and_exact(plan_seed,monkeypatch,tmp_path,status):
    # Only GitHub protocol I/O is doubled. Original authorization, staging,
    # complete-tree and actual-blob validators all execute with native JPEGs.
    import subprocess
    from create_defaults.bulk import operator_publication as operator,library_stage,remote as remote_module
    from create_defaults.bulk.library_sources import save,sealed
    from create_defaults.bulk.common import fingerprint
    from create_defaults.bulk.lifecycle.publication_preparation import tree
    _,_,target,preparation=plan_seed;value=preparation.to_dict()
    policy={'mode':'isolated-offline-protocol-fixture'}
    inventory=sealed(dict(baseline=value['destination'],rows=[dict(destination=m['destination'],
        candidate_path=m['source'],candidate_sha256=m['sha256'],candidate_blob=m['git_blob'],
        published_sha256=m['previous_sha256'],published_blob=m['previous_git_blob'],hash_state='different',
        technical_valid=True,difference_class='fixture-native',context_sha256=preparation.sha256,kind='poster') for m in value['members']]))
    manifest=operator.prepare(inventory,policy,tmp_path)
    receipt=operator.approve(manifest,policy,reviewer='bullmoose20',policy_hash=fingerprint(policy),
        manifest_hash=manifest['sha256'],decision_text='ISOLATED protocol fixture; no real human or contract approval',
        accept_exceptions=True,allow_additions=[m['destination'] for m in manifest['members']])
    plan,authorization=operator.authorize(manifest,policy,receipt)
    authorization=sealed({**{k:v for k,v in authorization.items() if k!='sha256'},'test_only':True})
    local=tmp_path/'remote.git'
    subprocess.run(['git','clone','--bare',str(target.root),str(local)],check=True,capture_output=True)
    report=library_stage.run(plan,authorization,tmp_path/'transport',test_remote=local)
    git(local,'update-ref','refs/pull/1/head',report['head'])
    save(tmp_path/'approved-git-batch-plan.json',plan);save(tmp_path/'draft-staging-authorization.json',authorization)
    def entries(commit):return [dict(path=p,sha=r['blob'],mode=r['mode'],type='blob') for p,r in tree(local,commit).items()]
    save(tmp_path/'production-snapshot.json',sealed(dict(entries=entries(plan['baseline']['head']))))
    class LocalReadOnly:
        def __init__(self,repository,token):
            assert repository=='Kometa-Team/Default-Images' and token=='isolated-fixture-token'
        def head(self,branch):
            commit=git(local,'rev-parse','refs/heads/'+branch).decode().strip()
            return commit,git(local,'rev-parse',commit+'^{tree}').decode().strip()
        def tree(self,tree_id,recursive):
            assert recursive
            return dict(truncated=False,tree=entries(tree_id))
    monkeypatch.setattr(remote_module,'ReadOnlyGitHub',LocalReadOnly)
    seen=[];real_output=subprocess.check_output;real_run=subprocess.run
    def observe(args,**kwargs):
        if args[:3]==['gh','auth','token']:return 'isolated-fixture-token'
        if args[:3]!=['gh','pr','list']:return real_output(args,**kwargs)
        seen.append(args)
        item=dict(number=1,url='https://example.invalid/1',isDraft=status!='not-draft',
            state=status if status in {'CLOSED','MERGED'} else 'OPEN',
            headRefOid='0'*40 if status=='wrong-head' else report['head'],baseRefName='main' if status=='wrong-base' else 'master')
        return json.dumps([] if len(seen)==1 else [item]* (2 if status=='duplicate' else 1))
    def execute(args,**kwargs):
        if args[:3]==['gh','pr','create']:
            return subprocess.CompletedProcess(args,1,stdout='',stderr='simulated accepted creation with lost acknowledgement')
        return real_run(args,**kwargs)
    monkeypatch.setattr(subprocess,'check_output',observe);monkeypatch.setattr(subprocess,'run',execute)
    if status=='OPEN':assert operator.draft(tmp_path,'Offline fixture')['number']==1
    else:
        with pytest.raises(BulkError,match='Expected exactly one unmerged draft'):operator.draft(tmp_path,'Offline fixture')
    assert len(seen)==2
