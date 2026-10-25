"""Native-artifact M6 mapping, CAS, retention and recovery adversaries."""
from copy import deepcopy
from threading import Event
from unittest.mock import patch
import json
import subprocess
import sys

import pytest

from create_defaults.bulk.common import BulkError, Conflict, canonical, fingerprint
from create_defaults.bulk.lifecycle import apply, mappings as m6, mapping_moves as moves
from create_defaults.bulk.lifecycle.evidence import HEADER, ReviewDecision
from create_defaults.bulk.lifecycle.identities import IdentityRegistry
from create_defaults.bulk.lifecycle.previews import CompositionArchive
from create_defaults.bulk.lifecycle.storage import OperationStore
from create_defaults.phase4.tests.transaction_samples import transaction


@pytest.fixture
def case(m6_case,request):
    case=m6_case;snapshot=case['m5_snapshot']
    case=dict(case);case['m6_label']=fingerprint(request.node.nodeid)[:20]
    case['m5_snapshot']=snapshot
    return case


def prepare(case,*,label='',name=None,display=None,source=None,delete=False,key=None,compensates=None):
    trial,ctx,_,_=case['row'];r=ctx.registry
    i=next(iter(ctx.candidate.graph.index().outputs))
    d=deepcopy(ctx.candidate.data()['effective_definitions'][i])
    if name is not None:
        d['composer']['out_name']=name
        d['output']['filename']=name+'.jpg'
        d['output']['remote_paths']['en']='genre/'+name+'.jpg'
    if display is not None:d['display_name']=display
    if source is not None:d['composer']['logo']=source
    return m6.prepare(r,operation_id='synthetic.operation.m6-'+case['m6_label']+label,
        operation='DELETE' if delete else 'RENAME',definitions=None if delete else {i:d},members=[i],
        definition_keys={i:key} if key else None,compensates=compensates)


def decisions(case,plan):
    actor=case['authority'];result=[]
    for role,action in [('submitter','confirm'),('maintainer','approve')]:
        person=next(iter(actor.roles[role]))
        value=dict(**HEADER,kind='composition-review-decision',
            review_id='synthetic.review.m6-'+fingerprint(plan.to_dict()['operation_id']),
            bundle_sha256=plan.sha256,context_sha256=plan.sha256,
            previous_sha256=result[0].sha256 if result else plan.sha256,actor=person,role=role,action=action,
            confirmation_sha256=result[0].sha256 if result else None)
        d=ReviewDecision.from_dict(value);actor.authorize(d,actor=person,role=role);result.append(d)
    return result


def commit(case,plan,**kw):
    r=case['row'][1].registry
    m6.propose(r,plan)
    return m6.commit_synthetic(r,plan,authority=case['authority'],decisions=decisions(case,plan),**kw)


@pytest.mark.parametrize('kind',['display','filename','case','unicode','punctuation','definition-key','source'])
def test_names_are_independent_and_identity_and_bytes_survive(case,kind):
    trial,ctx,_,_=case['row'];r=ctx.registry;i=next(iter(ctx.candidate.graph.index().outputs))
    original=r.view().entry(i);old_archive=case['m5_snapshot'].encoded
    args={
        'display':dict(display='A new display'), 'filename':dict(name='Fixture Renamed'),
        'case':dict(name='fixture'), 'unicode':dict(name='Fixture Pok\u00e9mon'),
        'punctuation':dict(name="Fixture (A & B)!"),'definition-key':dict(key='Definition (new)!'),
        'source':dict(source='logos/Fixture renamed.png')}[kind]
    if kind=='source':
        src=original['names']['source'];args['source']=str(__import__('pathlib').PurePosixPath(src['path']).parent)+'/Fixture renamed.png'
        target=trial.config.asset_dir/args['source'];target.write_bytes((trial.config.asset_dir/src['path']).read_bytes())
    plan=prepare(case,**args);result=commit(case,plan)
    e=r.view().entry(i);report=m6.recover(r)
    assert e['id']==i and e['semantic']==original['semantic'] and e['original_names']==original['original_names']
    assert e['names']['rendered_caption']==original['names']['rendered_caption']
    assert report['active_members']==[i] and not report['publication_authorized'] and not result['applied']
    assert case['m5_snapshot'].encoded==old_archive
    retained=report['retained'][i]['artwork']
    assert retained==case['m5_snapshot'].to_dict()['artwork'][i]
    assert CompositionArchive(r.operations.root,readonly=True).read_bytes(retained['object_sha256'])
    assert m6.commit_synthetic(r,plan,authority=case['authority'],decisions=decisions(case,plan))['retry']



def test_fresh_process_replays_case_rename_and_retained_receipts(case):
    r=case['row'][1].registry;plan=prepare(case,name='fixture');commit(case,plan)
    report=m6.recover(r)
    code='import json,sys;from create_defaults.bulk.lifecycle.identities import IdentityRegistry;from create_defaults.bulk.lifecycle.mappings import recover;print(json.dumps(recover(IdentityRegistry(sys.argv[1],sys.argv[2])),sort_keys=True))'
    child=subprocess.run([sys.executable,'-c',code,str(r.operations.root),r.identity],capture_output=True,text=True,timeout=300)
    assert child.returncode==0,child.stderr
    assert json.loads(child.stdout)==report



def test_delete_retains_artwork_receipts_aliases_and_tombstone(case):
    r=case['row'][1].registry;i=next(iter(case['row'][1].candidate.graph.index().outputs))
    before=case['m5_snapshot'].encoded
    plan=prepare(case,delete=True);commit(case,plan)
    report=m6.recover(r);e=r.view().entry(i)
    assert report['active_members']==[] and i in report['retained'] and report['tombstones'][i]==e['tombstone_sha256']
    assert before==case['m5_snapshot'].encoded
    assert r.operations.contracts.read_object(e['tombstone_sha256'])==canonical(plan.to_dict()['tombstones'][i])
    with pytest.raises(BulkError):r.revise(i,e['names'],entry_revision=e['revision'],token='reuse',expected=r.view().head)
    with pytest.raises(BulkError):prepare(case,name='Reanimated',label='again')
    # Old public filename remains occupied even though the definition is gone.
    with pytest.raises(BulkError):
        r.allocate(category=e['category'],semantic=dict(e['semantic'],key='replacement'),variant=e['variant'],
            names=e['names'],token='replacement',expected=r.view().head)


@pytest.mark.parametrize('attack',['style','caption','id','directory','wrong-filename','wrong-public','nfd','reserved','non-png-source'])
def test_rename_cannot_smuggle_material_changes_or_unsafe_names(case,attack):
    ctx=case['row'][1];r=ctx.registry;i=next(iter(ctx.candidate.graph.index().outputs))
    d=deepcopy(ctx.candidate.data()['effective_definitions'][i])
    if attack=='style':d['composer']['font_size']+=1
    elif attack=='caption':d['caption']['text']='DIFFERENT'
    elif attack=='id':d['id']='genre.substituted'
    elif attack=='directory':d['output']['directory']='somewhere'
    elif attack=='wrong-filename':d['output']['filename']='Other.jpg'
    elif attack=='wrong-public':d['output']['remote_paths']['en']='genre/Other.jpg'
    elif attack in {'nfd','reserved'}:
        name='Cafe\u0301' if attack=='nfd' else 'CON'
        d['composer']['out_name']=name;d['output']['filename']=name+'.jpg';d['output']['remote_paths']['en']='genre/'+name+'.jpg'
    elif attack=='non-png-source':d['composer']['logo']='logos/Fixture.jpg'
    with pytest.raises(BulkError):m6.prepare(r,operation_id='synthetic.operation.attack',operation='RENAME',definitions={i:d})


@pytest.mark.parametrize('attack',['none','dict','missing','revoked','expired','context','chain'])
def test_exact_two_stage_authority_is_required(case,attack):
    plan=prepare(case,display='Changed');r=case['row'][1].registry;m6.propose(r,plan)
    pair=decisions(case,plan);actor=case['authority']
    if attack=='none':actor=None
    elif attack=='dict':actor={'authenticated':True}
    elif attack=='missing':actor.grants.clear()
    elif attack=='revoked':actor.revoke(pair[1].sha256)
    elif attack=='expired':actor.as_of=100
    elif attack=='context':
        v=pair[1].to_dict();v['context_sha256']='0'*64;pair[1]=ReviewDecision.from_dict(v)
    elif attack=='chain':pair.reverse()
    before=r.operations.inspect()
    with pytest.raises(BulkError):m6.commit_synthetic(r,plan,authority=actor,decisions=pair)
    assert before==r.operations.inspect()


@pytest.mark.parametrize('attack',['root','offline'])
def test_trial_ownership_cannot_be_rebound_through_mutable_config(case,monkeypatch,attack):
    from dataclasses import replace
    trial=case['row'][0];r=case['row'][1].registry
    plan=prepare(case,display='Changed');m6.propose(r,plan);pair=decisions(case,plan)
    before=r.operations.inspect()
    if attack=='root':monkeypatch.setattr(trial,'root',trial.root/'not-the-owned-trial')
    else:monkeypatch.setattr(trial,'config',replace(trial.config,offline=False))
    with pytest.raises(BulkError):m6.commit_synthetic(r,plan,authority=case['authority'],decisions=pair)
    assert r.operations.inspect()==before


@pytest.mark.parametrize('point',['mapping_marker','registry_marker','commit_event'])
def test_atomic_cas_leaves_no_half_registry_or_mapping(case,monkeypatch,point):
    r=case['row'][1].registry;plan=prepare(case,display='Changed');m6.propose(r,plan)
    pair=decisions(case,plan);before=r.operations.inspect();view=r.view()
    def crash(name):
        if name==point:raise OSError('injected')
    monkeypatch.setattr(m6,'_checkpoint',crash)
    with pytest.raises(OSError,match='injected'):m6.commit_synthetic(r,plan,authority=case['authority'],decisions=pair)
    assert r.operations.inspect()==before and r.view()==view
    assert m6.recover(r)['commits']=={}
    monkeypatch.setattr(m6,'_checkpoint',lambda _:None)
    assert m6.commit_synthetic(r,plan,authority=case['authority'],decisions=pair)['isolated_committed']


@pytest.mark.parametrize('point',['journal_prepared','prepared','linked','intermediate','destination'])
def test_case_only_interruption_recovery_and_retry(case,monkeypatch,point):
    class Killed(BaseException):pass
    r=case['row'][1].registry;plan=prepare(case,name='fixture');m6.propose(r,plan);pair=decisions(case,plan)
    before=r.operations.inspect()
    def crash(name):
        if name==point:raise Killed()
    monkeypatch.setattr(moves,'_checkpoint',crash)
    with pytest.raises(Killed):m6.commit_synthetic(r,plan,authority=case['authority'],decisions=pair)
    assert r.operations.inspect()==before and not m6.recover(r)['commits']
    monkeypatch.setattr(moves,'_checkpoint',lambda _:None)
    assert m6.recover_local(r)=={plan.to_dict()['operation_id']:'restored-preimage'}
    assert m6.commit_synthetic(r,plan,authority=case['authority'],decisions=pair)['isolated_committed']
    assert m6.recover_local(r)=={plan.to_dict()['operation_id']:'committed-spelling'}
    # Literal Git tree spelling is independent of core.ignorecase on NTFS.
    root=moves._root(r.operations.contracts,plan.to_dict()['operation_id'])
    subprocess.run(['git','init','-q',str(root)],check=True,capture_output=True)
    subprocess.run(['git','-C',str(root),'add','.'],check=True,capture_output=True)
    paths=subprocess.check_output(['git','-C',str(root),'ls-files','-z']).decode().split('\0')
    assert any(p.endswith('/fixture.jpg') for p in paths) and not any(p.endswith('/Fixture.jpg') for p in paths)


def test_cancel_before_commit_and_compensating_operation_after_commit(case):
    r=case['row'][1].registry;plan=prepare(case,name='Renamed');event=Event();event.set()
    m6.propose(r,plan);before=r.operations.inspect()
    with pytest.raises(BulkError):m6.commit_synthetic(r,plan,authority=case['authority'],decisions=decisions(case,plan),cancel=event)
    assert r.operations.inspect()==before
    commit(case,plan)
    inverse=prepare(case,label='-compensate',name='Fixture',compensates=plan.sha256)
    commit(case,inverse)
    assert len(m6.recover(r)['commits'])==2
    assert r.view().entry(plan.to_dict()['members'][0])['names']['local_path'].endswith('/Fixture.jpg')
    assert len(r.operations.history(plan.to_dict()['operation_id']))==2


def test_competing_rename_and_delete_stale_registry_are_rejected(case):
    r=case['row'][1].registry;rename=prepare(case,display='Changed');delete=prepare(case,label='-delete',delete=True)
    m6.propose(r,rename);m6.propose(r,delete)
    # Proposing another operation advances overlapping M1 heads; neither caller
    # can refresh its stale reads merely by claiming the same registry hash.
    with pytest.raises(Conflict):m6.commit_synthetic(r,rename,authority=case['authority'],decisions=decisions(case,rename))
    assert not m6.recover(r)['commits']
    assert m6.commit_synthetic(r,delete,authority=case['authority'],decisions=decisions(case,delete))['isolated_committed']
    with pytest.raises(BulkError):m6.commit_synthetic(r,rename,authority=case['authority'],decisions=decisions(case,rename))


def test_m5_cannot_resurrect_a_retired_or_renamed_mapping(case):
    r=case['row'][1].registry;plan=prepare(case,delete=True);commit(case,plan)
    store=r.operations.contracts
    with store.read_connection() as db:
        with pytest.raises(BulkError,match='current_adapter'):m6.require_m5_compatible(store.root,store,db,case['row'][1].candidate)


def test_real_entry_points_fail_closed_without_any_write():
    with pytest.raises(BulkError,match='real_authority_unavailable'):m6.commit_operational()


@pytest.mark.parametrize('kind',['occupied','case-collision','unicode-collision','historical-alias','source-owner'])
def test_namespace_occupancy_includes_retained_aliases(case,kind):
    r=case['row'][1].registry;i=next(iter(case['row'][1].candidate.graph.index().outputs))
    original=r.view().entry(i);names=deepcopy(original['names'])
    name='Pok\u00e9mon' if kind=='unicode-collision' else 'Reserved'
    names.update(display_name='Another',local_path='defaults-en/genre/'+name+'.jpg',public_path='genre/'+name+'.jpg')
    names['source']=dict(path='logos/Fixture other.png',sha256=original['names']['source']['sha256'])
    e=r.allocate(category=original['category'],semantic=dict(original['semantic'],key='other'),variant=original['variant'],
        names=names,token='other',expected=r.view().head)
    if kind=='historical-alias':
        changed=deepcopy(names);changed.update(local_path='defaults-en/genre/Moved.jpg',public_path='genre/Moved.jpg')
        r.revise(e['id'],changed,entry_revision=e['revision'],token='moved',expected=r.view().head)
    with pytest.raises(BulkError):
        if kind=='source-owner':prepare(case,source=names['source']['path'])
        else:prepare(case,name=name.lower() if kind=='case-collision' else name)


def test_concurrent_commits_have_one_winner_and_no_partial_identity(case):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    r=case['row'][1].registry
    plans=[prepare(case,label='-one',display='One'),prepare(case,label='-two',display='Two')]
    for plan in plans:m6.propose(r,plan)
    pairs=[decisions(case,p) for p in plans];barrier=Barrier(2)
    def execute(n):
        barrier.wait(timeout=30)
        try:return m6.commit_synthetic(r,plans[n],authority=case['authority'],decisions=pairs[n])['isolated_committed']
        except Conflict:return False
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(execute,range(2)))
    assert sorted(results)==[False,True]
    report=m6.recover(r);assert len(report['commits'])==1
    assert r.view().entry(plans[0].to_dict()['members'][0])==plans[1].to_dict()['after'][plans[1].to_dict()['members'][0]]


def test_update_and_rename_share_the_original_m1_cas_keys(case):
    from create_defaults.bulk.lifecycle.models import Operation
    r=case['row'][1].registry;plan=prepare(case,display='Changed');m6.propose(r,plan)
    # An independent UPDATE reservation uses M2's unchanged subject/dependency/
    # namespace keys; it cannot coexist with an old RENAME read set.
    row=m6._request(r,plan).to_dict();row.update(id='synthetic.operation.competing-update',operation='UPDATE')
    update=Operation.from_dict(row)
    r.operations.append(update,expected_revision=0,expected_sha256=None,expected_event_sha256=None)
    with pytest.raises(Conflict):m6.commit_synthetic(r,plan,authority=case['authority'],decisions=decisions(case,plan))
    assert not m6.recover(r)['commits']


def test_concurrent_case_only_retry_has_one_commit_and_owned_copy(case):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    r=case['row'][1].registry;plan=prepare(case,name='fixture');m6.propose(r,plan)
    pair=decisions(case,plan);barrier=Barrier(2)
    def execute(_):
        barrier.wait(timeout=30)
        try:return m6.commit_synthetic(r,plan,authority=case['authority'],decisions=pair)['retry']
        except Conflict:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(execute,range(2)))
    assert sum(v is False for v in result)==1 and all(v in (False,True,'conflict') for v in result)
    assert m6.commit_synthetic(r,plan,authority=case['authority'],decisions=pair)['retry']
    report=m6.recover(r);assert len(report['commits'])==1
    assert len(r.operations.history(plan.to_dict()['operation_id']))==2
    assert all(m['positions']==['new'] for m in report['local_moves'][plan.to_dict()['operation_id']]['members'].values())


def test_withdrawal_releases_only_its_owned_pending_move(case,monkeypatch):
    class Killed(BaseException):pass
    r=case['row'][1].registry;plan=prepare(case,name='fixture');record=m6.propose(r,plan);pair=decisions(case,plan)
    def interrupt(point):
        if point=='intermediate':raise Killed()
    monkeypatch.setattr(moves,'_checkpoint',interrupt)
    with pytest.raises(Killed):m6.commit_synthetic(r,plan,authority=case['authority'],decisions=pair)
    monkeypatch.setattr(moves,'_checkpoint',lambda _:None)
    v=pair[0].to_dict();v['action']='withdraw';withdrawal=ReviewDecision.from_dict(v)
    case['authority'].authorize(withdrawal,actor=v['actor'],role='submitter')
    cancelled=m6.cancel_synthetic(r,plan,expected_record_sha256=record.sha256,authority=case['authority'],withdrawal=withdrawal)
    assert cancelled.to_dict()['state']=='cancelled' and not m6.recover(r)['commits']
    next_plan=prepare(case,label='-next',display='Next')
    assert commit(case,next_plan)['isolated_committed']


@pytest.mark.parametrize('attack',['target','bytes','link'])
def test_local_move_never_overwrites_unowned_or_substituted_files(case,monkeypatch,attack):
    from pathlib import Path
    class Killed(BaseException):pass
    r=case['row'][1].registry;plan=prepare(case,name='Renamed');m6.propose(r,plan);pair=decisions(case,plan)
    def interrupt(point):
        if point=='prepared':raise Killed()
    monkeypatch.setattr(moves,'_checkpoint',interrupt)
    with pytest.raises(Killed):m6.commit_synthetic(r,plan,authority=case['authority'],decisions=pair)
    monkeypatch.setattr(moves,'_checkpoint',lambda _:None)
    i=plan.to_dict()['members'][0];base=moves._root(r.operations.contracts,plan.to_dict()['operation_id'])/fingerprint(i)
    old=base/plan.to_dict()['before'][i]['names']['local_path'];target=base/plan.to_dict()['after'][i]['names']['local_path']
    if attack=='target':target.write_bytes(old.read_bytes())  # Equal bytes do NOT establish ownership.
    elif attack=='bytes':old.write_bytes(b'unexpected')
    else:
        external=case['row'][0].root/'unowned.jpg';external.write_bytes(old.read_bytes());old.unlink()
        # Directory symlinks need Windows privileges. A hard link to an external
        # file is also rejected by the staged-file link-count invariant.
        __import__('os').link(external,old)
    with pytest.raises(BulkError):m6.commit_synthetic(r,plan,authority=case['authority'],decisions=pair)
    with r.operations.contracts.read_connection() as db:
        assert not m6._ledger(r.operations.contracts,db)[1]
    with pytest.raises(BulkError):m6.recover(r)


@pytest.fixture(scope='session')
def schema_plan(m6_seed):
    case=dict(m6_seed,m6_label='schema-fixture')
    return prepare(case,display='Schema fixture')


@pytest.mark.parametrize('attack',['extra','missing','authority','type','id','semantic','revision','alias','tombstone','definition-key','unicode'])
def test_mapping_documents_are_closed_and_cannot_reassign_identity(schema_plan,attack):
    v=schema_plan.to_dict();i=v['members'][0]
    if attack=='extra':v['remote_delete']=True
    elif attack=='missing':v.pop('retained')
    elif attack=='authority':v['publication_authorized']=True
    elif attack=='type':v['schema_version']=True
    elif attack=='id':v['after'][i]['id']='forged'
    elif attack=='semantic':v['after'][i]['semantic']['key']='new-owner'
    elif attack=='revision':v['after'][i]['revision']+=1
    elif attack=='alias':v['after'][i]['aliases']=[dict(namespace='public',value='../bad')]
    elif attack=='tombstone':v['after'][i]['tombstone_sha256']='a'*64
    elif attack=='definition-key':v['definition_keys'][i]=True
    elif attack=='unicode':v['after'][i]['names']['local_path']='defaults-en/genre/Cafe\u0301.jpg'
    with pytest.raises(BulkError):m6.MappingPlan.from_dict(v)
