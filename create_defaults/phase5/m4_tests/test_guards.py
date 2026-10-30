"""Exact current-mapping, stale-caller, unsupported scope and integrity guards."""
from copy import deepcopy
from dataclasses import replace
import json
from threading import Event
from unittest.mock import patch

import pytest
import yaml

from create_defaults.bulk.common import BulkError, Conflict, canonical
from create_defaults.bulk.lifecycle import apply, mappings
from create_defaults.bulk.lifecycle.current_mapping import (
    CurrentEpoch, CurrentTransaction, _cohort, commit_operational, select_current, stage_source,
)
from create_defaults.phase4.m7_tests.helpers import prepare, commit
from create_defaults.phase4.tests.transaction_samples import transaction
from create_defaults.phase5.m4_tests.helpers import rename, epoch, candidate, prepare_update, commit_update


def test_P5_T17_old_M5_retry_still_rejects_after_RENAME(m7_case):
    case=m7_case;rename(case)
    registry=case['row'][1].registry;before=mappings.recover(registry)
    with pytest.raises(BulkError,match='m6_mapping_requires_current_adapter'):
        apply.commit_synthetic(case['update_tx'],expected_snapshot_sha256=case['update_snapshot'].sha256,
                               authority=case['authority'])
    assert mappings.recover(registry)==before


@pytest.mark.parametrize('name',['fixture','Fixture Pok\u00e9mon','Fixture (A & B)!'])
def test_P5_T18_literal_case_unicode_and_punctuation_mapping(m4_case,name):
    rename(m4_case,name=name)
    selected=epoch(m4_case)
    entry=next(iter(json.loads(selected.lineage_json)['entries'].values()))
    assert entry['names']['public_path']=='genre/'+name+'.jpg'
    selected.before.verify()


def test_P5_T18_stale_epoch_after_second_RENAME_blocks(m4_case):
    case=m4_case;rename(case)
    selected=epoch(case)
    # No source mutation before the competing RENAME; both plans use accepted
    # state, and M6's real CAS chooses the one committed mapping.
    second=prepare(case,name='Fixture Second',suffix='-second')
    commit(case,second)
    with pytest.raises((BulkError,Conflict)):
        selected.before.registry.require_head(selected.before.registry_head)
    with pytest.raises((BulkError,Conflict)):
        proposed=candidate(case,selected,mutate_source=False)
        prepare_update(case,selected,proposed=proposed,label='stale-epoch')


def test_P5_T15_retired_identity_never_selects_current_UPDATE(m4_case):
    case=m4_case;rename(case)
    deleted=prepare(case,delete=True,suffix='-delete');commit(case,deleted)
    trial,ctx,_,_=case['row']
    with pytest.raises(BulkError,match='inactive_or_unavailable_identity'):
        select_current(ctx.registry,expected=ctx.registry.view().head,paths=ctx.candidate.paths,
            profiles_path=ctx.candidate.profiles_path,posters=ctx.candidate.posters,
            content=json.loads(ctx.candidate.content_json),trial=trial)


@pytest.mark.parametrize('attack',['Playlist','Network','Streaming','Overlays','Studio','non-English',
                                  'retired','historical','generated','dependent','placeholder','family'])
def test_P5_T13_T15_T19_real_closed_cohort_guard(scope_context,attack):
    r=scope_context.registry
    i=scope_context.candidate.posters[0]
    entry=deepcopy(r.view().entry(i));d=deepcopy(scope_context.candidate.data()['effective_definitions'][i])
    if attack in {'Playlist','Network','Streaming','Overlays','Studio'}:entry['category']=attack
    elif attack=='non-English':entry['semantic']['language']='fr'
    elif attack=='retired':entry['tombstone_sha256']='a'*64
    elif attack=='historical':entry['origin']='historical-reference'
    elif attack=='dependent':entry['semantic']['parent']='foreign-parent'
    elif attack=='family':entry['semantic']['role']='family'
    elif attack=='placeholder':entry['variant']='placeholder-single-fa4978e71f7c453d'
    elif attack=='generated':d['generator']={'name':'award-years','version':1,'parameters':{}}
    with pytest.raises(BulkError) as error:
        _cohort({i:entry},{i:d},[i])
    assert error.value.code.startswith('p5m4_')


@pytest.mark.parametrize('attack',['unknown-field','duplicate-key','path-traversal','locked-font','dependency'])
def test_P5_T12_T20_changed_or_malicious_current_catalog_blocks(m4_case,attack):
    case=m4_case;rename(case);selected=epoch(case)
    trial,ctx,_,_=case['row'];data=dict(schema_version=1,category='Genre',definitions=list(selected.before.data()['effective_definitions'].values()))
    d=data['definitions'][0]
    if attack=='unknown-field':d['untrusted']=True
    if attack=='path-traversal':d['composer']['logo']='../foreign.png'
    if attack=='locked-font':d['composer']['font']='fonts/Fuggles-Regular.ttf'
    if attack=='dependency':d['dependencies']=[dict(poster_id='foreign',input='input')]
    raw=yaml.safe_dump(data)
    if attack=='duplicate-key':raw=raw.replace('schema_version: 1','schema_version: 1\nschema_version: 1')
    path=trial.root/'malicious.yml';path.write_text(raw,encoding='utf8')
    with pytest.raises((BulkError,ValueError,FileNotFoundError)):
        select_current(ctx.registry,expected=ctx.registry.view().head,paths=[path],
            profiles_path=ctx.candidate.profiles_path,posters=selected.before.posters,
            content=json.loads(selected.before.content_json),trial=trial)


@pytest.mark.parametrize('attack',['before-pin','closure-pin','accepted-snapshot','mapping-plan','foreign-registry','source-object'])
def test_P5_T12_T14_tampered_current_lineage_blocks(m4_case,attack):
    case=m4_case;rename(case);selected=epoch(case)
    value=json.loads(selected.lineage_json)
    if attack=='before-pin':value['before_sha256']='f'*64
    if attack=='closure-pin':value['closure_sha256']='f'*64
    if attack=='accepted-snapshot':value['accepted_snapshots'][value['members'][0]]='f'*64
    if attack=='mapping-plan':value['mapping_plans']=['f'*64]
    if attack=='foreign-registry':value['registry_id']='foreign'
    if attack=='source-object':value['assets'][next(iter(value['assets']))]='f'*64
    forged=CurrentEpoch(selected.before,canonical(value).decode())
    with pytest.raises((BulkError,Conflict)):
        prepare_update(case,forged,label='tamper-'+attack)


def test_P5_T26_real_operation_and_public_mutation_remain_unavailable(scope_context):
    r=scope_context.registry;before=r.operations.inspect()
    with pytest.raises(BulkError,match='real_authority_unavailable'):
        commit_operational({'authenticated':True,'delete_public':True})
    assert r.operations.inspect()==before


@pytest.mark.parametrize('attack',[None,'removed','injected'])
def test_P5_T18_exact_registry_alias_extension_only(scope_context,attack):
    from create_defaults.bulk.lifecycle.current_mapping import _same_mapping
    from create_defaults.bulk.lifecycle.identities import aliases_for
    i=scope_context.candidate.posters[0]
    before=scope_context.registry.view().entry(i);after=deepcopy(before)
    after['revision']+=1;after['names']['source']['sha256']='a'*64
    after['aliases']=[dict(namespace=n,value=v) for n,v in sorted(set(aliases_for(before['names'])))]
    if attack=='removed':after['aliases']=[]
    if attack=='injected':after['aliases'].append(dict(namespace='public',value='genre/Foreign.jpg'))
    if attack is None:_same_mapping(before,after)
    else:
        with pytest.raises(BulkError,match='alias_changed'):_same_mapping(before,after)


def test_P5_T18_cross_owner_epoch_never_creates_an_intent(scope_context):
    from create_defaults.bulk.lifecycle.current_mapping import propose_current
    from create_defaults.bulk.lifecycle.previews import CompositionTrial
    from create_defaults.phase4.tests.composition_samples import poster
    with CompositionTrial() as foreign_trial:
        foreign=poster(foreign_trial,'Genre')
        before=foreign.registry.operations.inspect()
        with pytest.raises(BulkError,match='foreign_epoch'):
            propose_current(CurrentEpoch(scope_context.candidate,'{}'),foreign.candidate,
                            identity='synthetic.operation.cross-owner')
        assert foreign.registry.operations.inspect()==before


@pytest.mark.parametrize('checkpoint',['snapshot_blob','record_index','member_head','receipt_index','before_commit'])
def test_P5_T27_atomic_faults_rollback_without_losing_history(prepared_current,checkpoint):
    case=prepared_current;selected=case['selection']
    tx,snapshot=case['current_tx'],case['current_snapshot'];native=case
    from create_defaults.bulk.lifecycle import recovery
    baseline=recovery.recover(selected.before.registry.operations.root)
    def injected(name):
        if name==checkpoint:raise RuntimeError('injected fault')
    with patch.object(apply,'_checkpoint',side_effect=injected),patch.object(recovery,'_checkpoint',side_effect=injected):
        with pytest.raises(RuntimeError,match='injected fault'):
            apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=native['authority'])
    assert recovery.recover(selected.before.registry.operations.root)==baseline
    result=apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=native['authority'])
    assert result['isolated_committed'] and not result['retry']


def test_P5_T27_cancellation_before_commit_is_not_application(prepared_current):
    case=prepared_current;selected=case['selection']
    tx,snapshot=case['current_tx'],case['current_snapshot'];native=case
    cancelled=Event();cancelled.set()
    from create_defaults.bulk.lifecycle.recovery import recover
    baseline=recover(selected.before.registry.operations.root)
    with pytest.raises(BulkError,match='cancelled'):
        apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=native['authority'],cancel=cancelled)
    assert recover(selected.before.registry.operations.root)==baseline


def test_P5_T18_concurrent_UPDATE_invalidates_earlier_exact_review(prepared_current):
    case=prepared_current;tx=case['current_tx'];snapshot=case['current_snapshot']
    from create_defaults.bulk.lifecycle.current_mapping import propose_current
    from create_defaults.bulk.lifecycle.recovery import recover
    root=case['selection'].before.registry.operations.root
    prior=recover(root)['outputs']
    propose_current(case['selection'],tx.inputs.composition.candidate,identity='synthetic.operation.concurrent-current')
    with pytest.raises((BulkError,Conflict)):
        apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=case['authority'])
    assert recover(root)['outputs']==prior


def test_P5_T18_concurrent_RENAME_cannot_adopt_uncommitted_source_revision(prepared_current):
    case=prepared_current;r=case['selection'].before.registry
    with pytest.raises(BulkError,match='uncommitted_registry_revision'):
        mappings.prepare(r,operation_id='synthetic.operation.concurrent-rename',operation='RENAME',
            definitions=case['selection'].before.data()['effective_definitions'])


def test_P5_T27_lost_acknowledgement_retries_exact_committed_operation(prepared_current):
    case=prepared_current;tx,snapshot=case['current_tx'],case['current_snapshot']
    def lost(name):
        if name=='after_commit':raise RuntimeError('lost acknowledgement')
    with patch.object(apply,'_checkpoint',side_effect=lost):
        with pytest.raises(RuntimeError,match='lost acknowledgement'):
            apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=case['authority'])
    from create_defaults.bulk.lifecycle.recovery import recover
    before=recover(case['selection'].before.registry.operations.root)
    result=apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=case['authority'])
    assert result['retry']
    assert recover(case['selection'].before.registry.operations.root)==before


@pytest.mark.parametrize('target',['lineage-object','lineage-index','owned-receipt'])
def test_P5_T14_T27_corrupt_committed_current_evidence_blocks(prepared_current,target):
    case=prepared_current;tx,snapshot=case['current_tx'],case['current_snapshot']
    apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=case['authority'])
    r=case['selection'].before.registry;store=r.operations.contracts
    if target=='lineage-index':
        # Append a duplicate through the real journal API; recovery must reject
        # the ambiguous index without treating either event as a new grant.
        from create_defaults.bulk.lifecycle.current_mapping import EVENT
        writer=__import__('create_defaults.bulk.lifecycle.package_e',fromlist=['SidecarStore']).SidecarStore(store.root)
        with writer.transaction() as db:
            writer.event(db,EVENT,snapshot.to_dict()['operation']['id'],dict(snapshot_sha256=snapshot.sha256,
                lineage_sha256=case['selection'].sha256))
        with pytest.raises(BulkError,match='lineage_index'):
            mappings.recover(r)
        return
    checksum=case['selection'].sha256 if target=='lineage-object' else next(iter(snapshot.to_dict()['artwork'].values()))['receipt_object_sha256']
    path=store.root/'objects'/(checksum+'.json');raw=path.read_bytes()
    try:
        path.write_bytes(b'{}')
        with pytest.raises(BulkError) as error:
            mappings.recover(r)
        assert error.value.code=='corrupt_contract_evidence'
    finally:
        path.write_bytes(raw)


def test_P5_T19_shared_source_requires_complete_current_closure(m4_case):
    from create_defaults.phase5.m4_tests.helpers import add_control
    from create_defaults.bulk.lifecycle.current_mapping import propose_current
    from create_defaults.bulk.lifecycle.recovery import recover
    case=m4_case
    add_control(case,shared=True)
    rename(case)
    selected=epoch(case)
    before=recover(selected.before.registry.operations.root)['outputs']
    proposed=candidate(case,selected,label='shared-omitted')
    with pytest.raises(BulkError,match='incomplete_committed_consumer_scope'):
        propose_current(selected,proposed,identity='synthetic.operation.shared-omitted')
    assert recover(selected.before.registry.operations.root)['outputs']==before


def test_P5_T18_T26_unrelated_native_identity_and_receipt_survive(m4_case):
    from create_defaults.phase5.m4_tests.helpers import add_control
    case=m4_case;control=add_control(case)
    registry=case['row'][1].registry
    identity=control.to_dict()['members'][0]
    entry=registry.view().entry(identity)
    history=registry.operations.contracts.read_object(control.sha256)
    rename(case)
    selected=epoch(case)
    native,tx,snapshot,result=commit_update(case,selected,label='with-unrelated')
    state=mappings.recover(registry)
    assert state['retained'][identity]['snapshot_sha256']==control.sha256
    assert registry.view().entry(identity)==entry
    assert registry.operations.contracts.read_object(control.sha256)==history
    assert state['retained'][identity]['artwork']==control.to_dict()['artwork'][identity]


@pytest.mark.parametrize('target',['source','definition','translation','destination','review'])
def test_P5_T12_fresh_native_context_is_required_at_commit(prepared_current,target):
    case=prepared_current;tx,snapshot=case['current_tx'],case['current_snapshot']
    candidate=tx.inputs.composition.candidate
    if target in {'source','definition'}:
        path=(candidate.config.asset_dir/next(iter(json.loads(candidate.content_json).values()))['source']['path']
              if target=='source' else candidate.paths[0])
        raw=path.read_bytes()
        try:
            path.write_bytes(raw+b'\n')
            with pytest.raises(BulkError):
                apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=case['authority'])
        finally:path.write_bytes(raw)
    elif target in {'translation','destination'}:
        # Replace an independently selected expected observation pin. The real
        # P3 consumer must reject it; no verifier or guard is mocked.
        values=dict(tx.inputs.phase3_inputs)
        field='expected_language_policy_sha256' if target=='translation' else 'expected_destination_sha256'
        values[field]='f'*64
        inputs=replace(tx.inputs,phase3_inputs=values)
        changed=replace(tx,transaction=replace(tx.transaction,inputs=inputs))
        with pytest.raises(BulkError):
            apply.commit_synthetic(changed,expected_snapshot_sha256=snapshot.sha256,authority=case['authority'])
    else:
        for decision in case['decisions']:
            case['authority'].revoked.add(decision.sha256)
        with pytest.raises(BulkError):
            apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=case['authority'])


def test_P5_T26_M6_retirement_after_current_UPDATE_retains_latest_artwork(prepared_current):
    case=prepared_current;tx,snapshot=case['current_tx'],case['current_snapshot']
    apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=case['authority'])
    r=case['selection'].before.registry;i=snapshot.to_dict()['members'][0]
    definitions=deepcopy(mappings.recover(r)['definitions'])
    definitions[i]['display_name']='Fixture Later Display'
    later=mappings.prepare(r,operation_id='synthetic.operation.after-current-rename',operation='RENAME',definitions=definitions)
    commit(case,later)
    retired=mappings.prepare(r,operation_id='synthetic.operation.after-current-delete',operation='DELETE',members=[i])
    commit(case,retired)
    final=mappings.recover(r)
    assert final['active_members']==[]
    assert final['retained'][i]['snapshot_sha256']==snapshot.sha256
    assert final['retained'][i]['artwork']==snapshot.to_dict()['artwork'][i]
    assert r.operations.contracts.read_object(snapshot.sha256)==snapshot.encoded
