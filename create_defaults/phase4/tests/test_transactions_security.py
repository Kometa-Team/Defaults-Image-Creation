"""Adversarial complete-review consumption; native fixture, no mocked renderer."""
from dataclasses import replace
import json

import pytest
import yaml

from create_defaults.bulk.common import BulkError, Conflict, canonical
from create_defaults.bulk.lifecycle import apply
from create_defaults.bulk.lifecycle.operations import DefinitionSnapshot, Transaction, propose
from create_defaults.bulk.lifecycle.recovery import recover
from create_defaults.bulk.lifecycle.storage import OperationStore
from create_defaults.phase4.tests import samples
from create_defaults.phase4.tests.transaction_samples import transaction_case,transaction


@pytest.mark.parametrize('attack',['missing','claim','revoked','expired','wrong-maintainer','reissued-grant','foreign-root'])
def test_synthetic_authority_is_exact_current_and_never_operational(transaction_case,attack):
    case=transaction_case;tx,snap=transaction(case);actor=case['authority']
    if attack=='missing':actor=None
    elif attack=='claim':actor={'authenticated':True,'role':'maintainer'}
    elif attack=='revoked':actor.revoke(case['decisions'][1].sha256)
    elif attack=='expired':actor.as_of=100
    elif attack=='wrong-maintainer':actor.roles['maintainer']=frozenset({'synthetic.actor.other'})
    elif attack=='reissued-grant':
        from create_defaults.phase4.tests.review_samples import authority,MAINTAINER
        actor=authority(case['row'])
        for record in case['decisions']:
            r=record.to_dict();actor.authorize(record,actor=r['actor'],role=r['role'],expires_at=1000)
    elif attack=='foreign-root':
        from create_defaults.bulk.lifecycle.previews import CompositionTrial
        from create_defaults.bulk.lifecycle.review_authority import SyntheticReviewAuthority
        with CompositionTrial() as trial:
            actor=SyntheticReviewAuthority(trial,submitters=['synthetic.actor.submitter'],maintainers=['synthetic.actor.maintainer'])
        # Even a closed foreign capability cannot be rehomed to this request.
    with pytest.raises(BulkError):
        apply.commit_synthetic(tx,expected_snapshot_sha256=snap.sha256,authority=actor)
    with pytest.raises(BulkError,match='real_authority_unavailable'):
        apply.commit_operational(tx,expected_snapshot_sha256=snap.sha256,authority=case['authority'])
    assert not recover(case['row'][0].config.cache_dir)['commits']


@pytest.mark.parametrize('attack',['operation-cancelled','operation-revised','review-withdrawn','review-unconfirmed','wrong-review','destination','phase3','candidate'])
def test_changed_heads_and_material_context_cannot_commit(transaction_case,attack):
    case=transaction_case;tx,snap=transaction(case);ctx=tx.inputs.composition;store=ctx.registry.operations
    if attack.startswith('operation-'):
        before=store.history(ctx.impact.to_dict()['operation']['id'])[-1]
        record=samples.next_record(store,before,state='cancelled' if attack=='operation-cancelled' else 'structurally_validated')
        samples.append(store,record)
    elif attack=='review-withdrawn':
        from create_defaults.bulk.lifecycle.review import decision
        from create_defaults.phase4.tests.review_samples import SUBMITTER
        record=decision(case['bundle'],case['state'],actor=SUBMITTER,action='withdraw')
        case['authority'].authorize(record,actor=SUBMITTER,role='submitter')
        case['archive'].decide(record,expected_sha256=case['state'].sha256,inputs=case['inputs'],authority=case['authority'])
    elif attack=='review-unconfirmed':
        from create_defaults.phase4.tests.review_samples import SUBMITTER
        state=case['archive'].start('synthetic.review.unconfirmed',submitter=SUBMITTER,inputs=case['inputs'])
        tx=replace(tx,review_id='synthetic.review.unconfirmed',review_sha256=state.sha256)
    elif attack=='wrong-review':tx=replace(tx,review_sha256='0'*64)
    elif attack=='destination':
        values=dict(tx.inputs.phase3_inputs)
        values['expected_destination_sha256']='0'*64
        tx=replace(tx,inputs=replace(tx.inputs,phase3_inputs=values))
    elif attack=='phase3':tx=replace(tx,inputs=replace(tx.inputs,expected_phase3_sha256='0'*64))
    else:
        c=ctx.candidate
        tx=replace(tx,inputs=replace(tx.inputs,composition=replace(ctx,candidate=replace(c,encoded=canonical(c.data()|{'complete':False})))))
    with pytest.raises((BulkError,Conflict)):
        apply.commit_synthetic(tx,expected_snapshot_sha256=snap.sha256,authority=case['authority'])
    assert not recover(case['row'][0].config.cache_dir)['commits']


@pytest.mark.parametrize('attack',['source','font','style','type','composition','receipt','partial-member'])
def test_changed_native_artifacts_and_locked_fields_fail_closed(transaction_case,monkeypatch,attack):
    case=transaction_case;tx,snap=transaction(case);trial,ctx,evidence,_=case['row']
    store=ctx.registry.operations.contracts
    if attack in {'source','font'}:
        manifest=json.loads(evidence.to_dict()['views'][0]['manifest_json'])
        asset=next(i['path'] for j in manifest['jobs'] for i in j['inputs'] if (i['path'].startswith('fonts/'))==(attack=='font'))
        path=trial.config.asset_dir/asset
        raw=path.read_bytes()
        try:
            path.write_bytes(raw+b'changed')
            with pytest.raises((BulkError,Conflict)):
                apply.commit_synthetic(tx,expected_snapshot_sha256=snap.sha256,authority=case['authority'])
        finally:path.write_bytes(raw)
    elif attack in {'style','type'}:
        path=ctx.candidate.paths[0];raw=path.read_bytes()
        try:
            value=yaml.safe_load(raw)
            if attack=='style':value['definitions'][0]['composer']['font_size']+=1
            else:value['definitions'][0]['category']='Studio'
            path.write_text(yaml.safe_dump(value),encoding='utf8')
            with pytest.raises((BulkError,Conflict)):
                apply.commit_synthetic(tx,expected_snapshot_sha256=snap.sha256,authority=case['authority'])
        finally:path.write_bytes(raw)
    else:
        pin=evidence.sha256 if attack=='composition' else evidence.to_dict()['views'][0]['members'][0]['receipt_object_sha256' if attack=='receipt' else 'object_sha256']
        path=store.root/'objects'/(pin+'.json');raw=path.read_bytes()
        try:
            if attack=='partial-member':path.unlink()
            else:path.write_bytes(b'{}')
            with pytest.raises((BulkError,Conflict,FileNotFoundError)):
                apply.commit_synthetic(tx,expected_snapshot_sha256=snap.sha256,authority=case['authority'])
        finally:path.write_bytes(raw)
    assert not recover(trial.config.cache_dir)['commits']


def test_revocation_during_replay_and_invalid_cancellation_object(transaction_case,monkeypatch):
    case=transaction_case;tx,snap=transaction(case)
    def revoke(name):
        if name=='after_review':case['authority'].revoke(case['decisions'][1].sha256)
    monkeypatch.setattr(apply,'_checkpoint',revoke)
    with pytest.raises(BulkError,match='authority_revoked'):
        apply.commit_synthetic(tx,expected_snapshot_sha256=snap.sha256,authority=case['authority'])
    with pytest.raises(BulkError,match='cancellation_object_required'):
        apply.commit_synthetic(tx,expected_snapshot_sha256=snap.sha256,authority=case['authority'],cancel=lambda:False)


def test_revision_replay_cannot_replace_content_after_commit(transaction_case):
    case=transaction_case;tx,snap=transaction(case)
    result=apply.commit_synthetic(tx,expected_snapshot_sha256=snap.sha256,authority=case['authority'])
    root=case['row'][0].config.cache_dir;original=recover(root)
    for changed in (replace(tx,review_sha256='0'*64),replace(tx,expected_snapshots_json=canonical({i:'1'*64 for i in snap.to_dict()['members']}).decode())):
        with pytest.raises(BulkError,match='revision_replay'):
            apply.commit_synthetic(changed,expected_snapshot_sha256=snap.sha256,authority=case['authority'])
    with pytest.raises(BulkError,match='revision_replay'):
        apply.commit_synthetic(tx,expected_snapshot_sha256='0'*64,authority=case['authority'])
    assert recover(root)==original and result['isolated_committed']


@pytest.mark.parametrize('attack',['orphan','snapshot','commit-event','head'])
def test_restart_retains_orphans_but_rejects_corrupt_authoritative_state(transaction_case,attack):
    case=transaction_case;tx,snap=transaction(case);root=case['row'][0].config.cache_dir
    apply.commit_synthetic(tx,expected_snapshot_sha256=snap.sha256,authority=case['authority'])
    before=recover(root)
    from create_defaults.bulk.lifecycle.package_e import SidecarStore
    writer=SidecarStore(root)
    if attack=='orphan':
        raw=canonical({'kind':'unindexed-interrupted-data','version':1})
        from create_defaults.bulk.common import fingerprint
        writer.put_object(raw,expected_sha256=fingerprint(json.loads(raw)))
        assert recover(root)==before
        return
    if attack=='snapshot':
        path=root/'objects'/(snap.sha256+'.json');raw=path.read_bytes()
        try:
            path.write_bytes(b'{}')
            with pytest.raises(BulkError):recover(root)
        finally:path.write_bytes(raw)
    elif attack=='commit-event':
        with writer.transaction() as db:
            writer.event(db,'phase4_isolated_commit','synthetic.operation.forged',{'claim':'approved'})
        with pytest.raises(BulkError,match='commit_event_index'):recover(root)
    else:
        with writer.transaction() as db:
            db.execute('DROP TRIGGER p4m1_heads_no_update')
            db.execute("UPDATE p4m1_heads SET sha256=? WHERE kind='subject'",('0'*64,))
        with pytest.raises(BulkError):recover(root)


def test_snapshot_canonical_roundtrip_and_unreviewed_member_substitution(transaction_case):
    case=transaction_case;_,snap=transaction(case)
    assert DefinitionSnapshot.from_bytes(snap.encoded)==snap
    with pytest.raises(BulkError):DefinitionSnapshot.from_bytes(snap.encoded+b'\n')
    for field,value in [('publication_authorized',True),('unexpected','field'),('members',[]),('review_sha256','not-a-hash'),('observation_pins_json','{}')]:
        with pytest.raises(BulkError):DefinitionSnapshot.from_dict(snap.to_dict()|{field:value})
    value=snap.to_dict();next(iter(value['artwork'].values()))['sha256']='0'*64
    with pytest.raises(BulkError,match='artwork_binding'):DefinitionSnapshot.from_dict(value)


def test_changed_dependency_head_after_confirmation_cannot_commit(transaction_case):
    case=transaction_case;tx,snap=transaction(case);store=tx.inputs.composition.registry.operations
    intent=store.history(tx.inputs.composition.impact.to_dict()['operation']['id'])[-1].to_dict()
    dependency=next({k:r[k] for k in ('kind','id')} for r in intent['reads'] if r['kind']=='dependency')
    changed=samples.sample(store,name='shared-source-change',operation='UPDATE',paths=[],extra_heads=[dependency],write_extras=True)
    samples.append(store,changed)
    with pytest.raises((BulkError,Conflict)):
        apply.commit_synthetic(tx,expected_snapshot_sha256=snap.sha256,authority=case['authority'])
    assert not recover(case['row'][0].config.cache_dir)['commits']


@pytest.mark.parametrize('kind',['playlist','overlay','family'])
def test_unsupported_prospective_adapters_are_named_and_never_committed(kind):
    from create_defaults.bulk.lifecycle.previews import CompositionTrial
    from create_defaults.phase4.tests import composition_samples as cs
    from create_defaults.bulk.lifecycle.operations import require_adapter
    with CompositionTrial() as trial:
        ctx=cs.poster(trial,'Playlist') if kind=='playlist' else cs.overlays(trial) if kind=='overlay' else cs.family(trial)
        with pytest.raises(BulkError,match='unsupported_transaction_category|unsupported_prospective_phase3_adapter'):
            require_adapter(ctx.candidate)


def test_cancelled_native_generation_has_no_commit_or_review(transaction_case):
    from threading import Event
    from create_defaults.bulk.lifecycle.operations import preview
    case=transaction_case;trial,ctx,_,_=case['row'];cancel=Event();cancel.set()
    before=case['archive'].history();store=OperationStore(trial.config.cache_dir).inspect()
    with pytest.raises(BulkError):preview(ctx,trial,cancel=cancel)
    assert case['archive'].history()==before
    assert OperationStore(trial.config.cache_dir).inspect()==store
    assert not recover(trial.config.cache_dir)['commits']


def test_native_shared_source_update_requires_complete_fanout():
    from create_defaults.bulk.lifecycle.previews import CompositionTrial
    from create_defaults.phase4.tests.transaction_samples import shared_cohort,shared_update,reviewed
    with CompositionTrial() as trial:
        ctx=shared_cohort(trial);case=reviewed(trial,ctx,label='shared-add');tx,snap=transaction(case)
        first=apply.commit_synthetic(tx,expected_snapshot_sha256=snap.sha256,authority=case['authority'])
        old=recover(trial.config.cache_dir)
        candidate,frozen=shared_update(case)
        next_ctx=propose(ctx.registry,before=frozen,candidate=candidate,identity='synthetic.operation.shared-update',operation='UPDATE')
        details=json.loads(next_ctx.impact.to_dict()['details_json'])
        assert set(details['affected_outputs'])==set(candidate.graph.index().outputs) and len(details['affected_outputs'])==2
        source=next(iter(snap.to_dict()['entries'].values()))['names']['source']['path']
        assert all(any(reason['cause']=='asset:'+source for reason in details['reasons'][i]) for i in details['affected_outputs'])
        updated=reviewed(trial,next_ctx,label='shared-update');next_tx,next_snap=transaction(updated,{i:first['snapshot_sha256'] for i in details['affected_outputs']})
        result=apply.commit_synthetic(next_tx,expected_snapshot_sha256=next_snap.sha256,authority=updated['authority'])
        final=recover(trial.config.cache_dir)
        assert len(final['commits'])==2 and len(final['outputs'])==2
        for i in old['outputs']:
            assert final['outputs'][i]['artwork']['sha256']!=old['outputs'][i]['artwork']['sha256']
            assert final['outputs'][i]['snapshot_sha256']==result['snapshot_sha256']


@pytest.mark.parametrize('attack',['source','definition','phase3'])
def test_inputs_changed_after_full_review_are_rechecked_at_commit(transaction_case,monkeypatch,attack):
    case=transaction_case;tx,snap=transaction(case);trial,ctx,_,_=case['row']
    path=trial.config.asset_dir/next(iter(snap.to_dict()['entries'].values()))['names']['source']['path'] if attack=='source' else ctx.candidate.paths[0]
    raw=path.read_bytes();pins=dict(tx.inputs.phase3_inputs)
    def change(name):
        if name=='after_review':
            if attack=='phase3':tx.inputs.phase3_inputs['expected_destination_sha256']='0'*64
            else:path.write_bytes(raw+b'changed-after-review')
    monkeypatch.setattr(apply,'_checkpoint',change)
    try:
        diagnostic={'source':'source_changed_during_commit','definition':'definition_changed_during_commit','phase3':'phase3_observations_changed_during_commit'}[attack]
        with pytest.raises(BulkError,match=diagnostic):apply.commit_synthetic(tx,expected_snapshot_sha256=snap.sha256,authority=case['authority'])
    finally:
        path.write_bytes(raw);tx.inputs.phase3_inputs.clear();tx.inputs.phase3_inputs.update(pins)
    assert not recover(trial.config.cache_dir)['commits']


def test_unselected_definition_cannot_be_smuggled_into_snapshot(transaction_case):
    from create_defaults.bulk.lifecycle.operations import require_adapter
    candidate=transaction_case['row'][1].candidate
    data=candidate.data();data['effective_definitions']['unselected.ghost']=next(iter(data['effective_definitions'].values()))
    forged=replace(candidate,encoded=canonical(data))
    with pytest.raises(BulkError,match='unselected_definition_requires_scoped_proposal'):require_adapter(forged)
