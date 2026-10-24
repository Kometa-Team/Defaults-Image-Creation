"""Real threads, existing M1 CAS, native disjoint commits and complete members."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

import pytest

from create_defaults.bulk.common import BulkError, Conflict
from create_defaults.bulk.lifecycle import apply
from create_defaults.bulk.lifecycle.operations import propose
from create_defaults.bulk.lifecycle.recovery import recover
from create_defaults.bulk.lifecycle.previews import CompositionTrial
from create_defaults.phase4.tests import composition_samples as cs
from create_defaults.phase4.tests.transaction_samples import transaction_case,transaction,reviewed,additional,additional_candidate,update_candidate


def test_concurrent_identical_complete_add_commits_once(transaction_case):
    case=transaction_case;tx,snap=transaction(case);barrier=Barrier(2)
    def run(_):
        barrier.wait()
        return apply.commit_synthetic(tx,expected_snapshot_sha256=snap.sha256,authority=case['authority'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(run,range(2)))
    assert sorted(r['retry'] for r in results)==[False,True]
    assert len(recover(case['row'][0].config.cache_dir)['commits'])==1


@pytest.mark.parametrize('collision',['semantic','namespace'])
def test_concurrent_add_allocation_reserves_one_identity(transaction_case,collision):
    case=transaction_case;r=case['row'][1].registry;e=next(iter(r.view().entries()))
    head=r.view().head;barrier=Barrier(2)
    def run(n):
        names=deepcopy(e['names']);names['display_name']='Fixture concurrent'
        for f in ('local_path','public_path'):names[f]=names[f].replace('Fixture.jpg','Fixture concurrent.jpg')
        semantic=dict(e['semantic'],key='new' if collision=='semantic' else 'new-'+str(n))
        barrier.wait()
        try:
            return r.allocate(category=e['category'],semantic=semantic,variant=e['variant'],names=names,token='concurrent-'+str(n),expected=head)
        except (BulkError,Conflict):return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
    assert sum(r is not None for r in results)==1
    assert not recover(case['row'][0].config.cache_dir)['commits']


def test_disjoint_native_adds_preserve_unrelated_exact_artwork(transaction_case):
    case=transaction_case;tx,snap=transaction(case);trial,ctx,_,_=case['row']
    apply.commit_synthetic(tx,expected_snapshot_sha256=snap.sha256,authority=case['authority'])
    original=recover(trial.config.cache_dir)
    # Allocate both before sealing either current registry pin. The complete
    # committed baseline proves common immutable font/translation dependencies
    # unchanged, so M2 does not falsely write them as new ADD dependencies.
    rows=[additional(case,label) for label in ('disjoint-one','disjoint-two')]
    candidates=[additional_candidate(case,row) for row in rows]
    reviews=[]
    for n,candidate in enumerate(candidates):
        context=propose(ctx.registry,before=ctx.candidate,candidate=candidate,
            identity='synthetic.operation.disjoint-'+str(n),operation='ADD')
        reviews.append(reviewed(trial,context,label='disjoint-'+str(n)))
    prepared=[transaction(row) for row in reviews]
    barrier=Barrier(2)
    def run(n):
        barrier.wait();t,s=prepared[n]
        return apply.commit_synthetic(t,expected_snapshot_sha256=s.sha256,authority=reviews[n]['authority'])
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
    assert all(r['isolated_committed'] for r in results)
    final=recover(trial.config.cache_dir)
    assert len(final['commits'])==3 and len(final['outputs'])==3
    for i,row in original['outputs'].items():assert final['outputs'][i]==row


def test_native_paired_network_is_committed_all_or_none(monkeypatch):
    with CompositionTrial() as trial:
        ctx=cs.poster(trial,'Network',paired=True)
        case=reviewed(trial,ctx,label='network')
        tx,snapshot=transaction(case)
        assert len(snapshot.to_dict()['members'])==2
        assert {e['semantic']['role'] for e in snapshot.to_dict()['entries'].values()}=={'white','color'}
        def crash(name):
            if name=='member_head':raise OSError('second-member interrupted')
        monkeypatch.setattr(apply,'_checkpoint',crash)
        with pytest.raises(OSError,match='interrupted'):
            apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=case['authority'])
        assert not recover(trial.config.cache_dir)['outputs']
        monkeypatch.setattr(apply,'_checkpoint',lambda _:None)
        result=apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=case['authority'])
        state=recover(trial.config.cache_dir)
        assert len(state['outputs'])==2
        assert {r['snapshot_sha256'] for r in state['outputs'].values()}=={result['snapshot_sha256']}


def test_two_updates_cannot_both_replace_one_committed_subject(transaction_case):
    case=transaction_case;tx,snap=transaction(case);trial,ctx,_,_=case['row']
    first=apply.commit_synthetic(tx,expected_snapshot_sha256=snap.sha256,authority=case['authority'])
    candidate,frozen=update_candidate(case,label='concurrent-update')
    reviews=[];prepared=[]
    previous={i:first['snapshot_sha256'] for i in candidate.graph.index().outputs}
    for n in range(2):
        context=propose(ctx.registry,before=frozen,candidate=candidate,identity='synthetic.operation.concurrent-update-'+str(n),operation='UPDATE')
        row=reviewed(trial,context,label='concurrent-update-'+str(n))
        reviews.append(row);prepared.append(transaction(row,previous))
    barrier=Barrier(2)
    def run(n):
        barrier.wait();t,s=prepared[n]
        try:return apply.commit_synthetic(t,expected_snapshot_sha256=s.sha256,authority=reviews[n]['authority'])
        except (BulkError,Conflict):return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
    assert sum(r is not None for r in results)==1
    final=recover(trial.config.cache_dir)
    assert len(final['commits'])==2
    assert final['outputs'][next(iter(candidate.graph.index().outputs))]['snapshot_sha256']==results[1]['snapshot_sha256']
