"""Complete native artwork, explicit two-stage attribution and immutable history."""
from copy import deepcopy
from dataclasses import replace
import json
import sqlite3

import pytest

from create_defaults.bulk.common import BulkError, Conflict, canonical, fingerprint
from create_defaults.bulk.lifecycle.evidence import ReviewBundle, ReviewDecision, ReviewState, selective_impact
from create_defaults.bulk.lifecycle.review import ReviewArchive, decision
from create_defaults.bulk.lifecycle.review_authority import require_operational_approval
from create_defaults.bulk.lifecycle.previews import CompositionArchive
from create_defaults.bulk.lifecycle.composition_models import CompositionEvidence
from create_defaults.bulk.contracts.expanded.graph import Snapshot
from create_defaults.phase4.tests import review_samples as samples


@pytest.fixture(scope='module')
def reviewed(composed):
    row = composed['genre']
    current = samples.inputs(row)
    archive = ReviewArchive.create(row[1].registry.operations.root)
    actor = samples.authority(row)
    pending = archive.start('synthetic.review.complete',submitter=samples.SUBMITTER,inputs=current)
    _, bundle, _ = archive.read('synthetic.review.complete',expected_sha256=pending.sha256)
    confirm = decision(bundle,pending,actor=samples.SUBMITTER,action='confirm')
    actor.authorize(confirm,actor=samples.SUBMITTER,role='submitter')
    confirmed = archive.decide(confirm,expected_sha256=pending.sha256,inputs=current,authority=actor)
    approve = decision(bundle,confirmed,actor=samples.MAINTAINER,action='approve')
    actor.authorize(approve,actor=samples.MAINTAINER,role='maintainer')
    approved = archive.decide(approve,expected_sha256=confirmed.sha256,inputs=current,authority=actor)
    return dict(row=row,inputs=current,archive=archive,authority=actor,bundle=bundle,
        pending=pending,confirmed=confirmed,approved=approved,confirm=confirm,approve=approve)


def test_complete_synthetic_review_chain_and_immutable_reopen(reviewed):
    row,current,actor,approved = (reviewed[k] for k in ('row','inputs','authority','approved'))
    reopened = ReviewArchive(row[1].registry.operations.root)
    assert reopened.current('synthetic.review.complete',expected_sha256=approved.sha256,inputs=current,authority=actor)[0] == approved
    assert [s.to_dict()['state'] for s in reopened.history('synthetic.review.complete')] == ['PREVIEWS_COMPLETE','SUBMITTER_CONFIRMED','MAINTAINER_APPROVED']
    assert reopened.assess('synthetic.review.complete',expected_sha256=approved.sha256,inputs=current,authority=actor)['authenticated'] is False


def pending(reviewed, label):
    archive = reviewed['archive']
    state = archive.start('synthetic.review.'+label,submitter=samples.SUBMITTER,inputs=reviewed['inputs'])
    bundle = archive.read('synthetic.review.'+label,expected_sha256=state.sha256)[1]
    return archive,state,bundle


@pytest.mark.parametrize('action,target',[('reject','SUBMITTER_REJECTED'),('withdraw','WITHDRAWN')])
def test_explicit_submitter_rejection_or_withdrawal_blocks_advance(reviewed,action,target):
    archive,state,bundle = pending(reviewed,action)
    actor = reviewed['authority']
    record = decision(bundle,state,actor=samples.SUBMITTER,action=action)
    actor.authorize(record,actor=samples.SUBMITTER,role='submitter')
    result = archive.decide(record,expected_sha256=state.sha256,inputs=reviewed['inputs'],authority=actor)
    assert result.to_dict()['state'] == target
    with pytest.raises(BulkError,match='inactive_review'):
        archive.current(bundle.to_dict()['id'],expected_sha256=result.sha256,inputs=reviewed['inputs'],authority=actor)


def test_maintainer_rejection_and_later_submitter_withdrawal_preserve_history(reviewed):
    archive,state,bundle = pending(reviewed,'maintainer-rejection')
    actor = reviewed['authority']
    confirm = decision(bundle,state,actor=samples.SUBMITTER,action='confirm')
    actor.authorize(confirm,actor=samples.SUBMITTER,role='submitter')
    confirmed = archive.decide(confirm,expected_sha256=state.sha256,inputs=reviewed['inputs'],authority=actor)
    rejection = decision(bundle,confirmed,actor=samples.MAINTAINER,action='reject-maintainer')
    actor.authorize(rejection,actor=samples.MAINTAINER,role='maintainer')
    result = archive.decide(rejection,expected_sha256=confirmed.sha256,inputs=reviewed['inputs'],authority=actor)
    assert result.to_dict()['state'] == 'MAINTAINER_REJECTED'
    assert len(archive.history(bundle.to_dict()['id'])) == 3
    # A rejected review is terminal; a different proposal needs a new review.
    with pytest.raises(BulkError,match='inactive_review'):
        archive.current(bundle.to_dict()['id'],expected_sha256=result.sha256,inputs=reviewed['inputs'],authority=actor)


def test_withdrawal_after_confirmation_invalidates_exact_confirmation(reviewed):
    archive,state,bundle = pending(reviewed,'confirmed-withdrawal')
    actor = reviewed['authority']
    confirm = decision(bundle,state,actor=samples.SUBMITTER,action='confirm')
    actor.authorize(confirm,actor=samples.SUBMITTER,role='submitter')
    confirmed = archive.decide(confirm,expected_sha256=state.sha256,inputs=reviewed['inputs'],authority=actor)
    withdraw = decision(bundle,confirmed,actor=samples.SUBMITTER,action='withdraw')
    actor.authorize(withdraw,actor=samples.SUBMITTER,role='submitter')
    result = archive.decide(withdraw,expected_sha256=confirmed.sha256,inputs=reviewed['inputs'],authority=actor)
    assert result.to_dict()['state'] == 'WITHDRAWN'
    assert result.to_dict()['confirmation_sha256'] == confirm.sha256


def test_missing_confirmation_cannot_advance_even_with_maintainer_grant(reviewed):
    archive,state,bundle = pending(reviewed,'missing-confirmation')
    # Strict record representation itself rejects a maintainer without a prior pin.
    with pytest.raises(BulkError,match='confirmation_reference'):
        decision(bundle,state,actor=samples.MAINTAINER,action='approve')
    value = reviewed['approve'].to_dict()|dict(review_id=bundle.to_dict()['id'],
        previous_sha256=state.sha256,bundle_sha256=bundle.sha256,context_sha256=bundle.to_dict()['context_sha256'])
    record = ReviewDecision.from_dict(value)
    reviewed['authority'].authorize(record,actor=samples.MAINTAINER,role='maintainer')
    with pytest.raises(BulkError):
        archive.decide(record,expected_sha256=state.sha256,inputs=reviewed['inputs'],authority=reviewed['authority'])


def test_same_actor_cannot_satisfy_separation_of_duties(reviewed):
    archive,state,bundle = pending(reviewed,'same-actor')
    actor = samples.authority(reviewed['row'],same_actor=True)
    confirm = decision(bundle,state,actor=samples.SUBMITTER,action='confirm')
    actor.authorize(confirm,actor=samples.SUBMITTER,role='submitter')
    confirmed = archive.decide(confirm,expected_sha256=state.sha256,inputs=reviewed['inputs'],authority=actor)
    approve = decision(bundle,confirmed,actor=samples.SUBMITTER,action='approve')
    actor.authorize(approve,actor=samples.SUBMITTER,role='maintainer')
    with pytest.raises(BulkError,match='separation_of_duties'):
        archive.decide(approve,expected_sha256=confirmed.sha256,inputs=reviewed['inputs'],authority=actor)


@pytest.mark.parametrize('attack',['none','claim','forged-provider','revoked','expired','wrong-actor','missing-record'])
def test_independent_authority_is_required_for_the_exact_decision(reviewed,attack):
    actor = samples.authority(reviewed['row'])
    record = reviewed['confirm']
    if attack != 'missing-record':
        actor.authorize(record,actor=samples.SUBMITTER,role='submitter')
    if attack == 'none':actor=None
    elif attack == 'claim':actor=dict(actor=samples.SUBMITTER,role='submitter',authenticated=True)
    elif attack == 'forged-provider':
        class Fake:
            def verify(self,*a,**kw):return dict(status='authorized',authenticated=True)
        actor=Fake()
    elif attack == 'revoked':actor.revoke(record.sha256)
    elif attack == 'expired':actor.as_of=100
    elif attack == 'wrong-actor':actor.roles['submitter']=frozenset({'synthetic.actor.other'})
    with pytest.raises(BulkError):
        reviewed['archive'].current('synthetic.review.complete',expected_sha256=reviewed['approved'].sha256,
            inputs=reviewed['inputs'],authority=actor)


def test_reissued_grant_cannot_silently_extend_a_recorded_approval(reviewed):
    actor=samples.authority(reviewed['row'])
    actor.authorize(reviewed['confirm'],actor=samples.SUBMITTER,role='submitter',expires_at=1000)
    actor.authorize(reviewed['approve'],actor=samples.MAINTAINER,role='maintainer')
    with pytest.raises(BulkError,match='authority_context_substitution'):
        reviewed['archive'].current('synthetic.review.complete',expected_sha256=reviewed['approved'].sha256,
            inputs=reviewed['inputs'],authority=actor)


@pytest.mark.parametrize('field,value',[('actor','synthetic.actor.other'),('context_sha256','0'*64),('previous_sha256','1'*64),('confirmation_sha256','2'*64),('bundle_sha256','3'*64)])
def test_rehashed_substituted_decisions_are_not_authenticated(reviewed,field,value):
    record = ReviewDecision.from_dict(reviewed['approve'].to_dict()|{field:value})
    actor = reviewed['authority']
    # A newly self-hashed document cannot inherit the original external grant.
    from create_defaults.bulk.lifecycle.review_authority import verify_authority
    with pytest.raises(BulkError):verify_authority(actor,record,root=reviewed['archive'].store.root)
    with pytest.raises((BulkError,Conflict)):
        reviewed['archive'].decide(record,expected_sha256=reviewed['approved'].sha256,inputs=reviewed['inputs'],authority=actor)


def test_replay_and_concurrent_checkpoint_conflict_do_not_append(reviewed):
    archive = reviewed['archive']
    before = archive.history('synthetic.review.complete')
    with pytest.raises(Conflict):
        archive.decide(reviewed['confirm'],expected_sha256=reviewed['pending'].sha256,inputs=reviewed['inputs'],authority=reviewed['authority'])
    assert archive.history('synthetic.review.complete') == before
    assert archive.assess('synthetic.review.complete',expected_sha256=reviewed['pending'].sha256,
        inputs=reviewed['inputs'],authority=reviewed['authority'])['state']=='CONFLICTED'


@pytest.mark.parametrize('source_kind',['source','font'])
def test_changed_source_or_font_bytes_stale_only_the_bound_artwork(reviewed,source_kind):
    trial = reviewed['row'][0]
    view = reviewed['row'][2].to_dict()['views'][0]
    manifest = json.loads(view['manifest_json'])
    source = next(s for s in manifest['jobs'][0]['inputs'] if (s['role']=='font')==(source_kind=='font'))
    path = trial.config.asset_dir/source['path']
    original = path.read_bytes()
    try:
        path.write_bytes(original+b'changed-without-an-approved-review')
        with pytest.raises(BulkError):
            reviewed['archive'].current('synthetic.review.complete',expected_sha256=reviewed['approved'].sha256,
                inputs=reviewed['inputs'],authority=reviewed['authority'])
    finally:path.write_bytes(original)


@pytest.mark.parametrize('attack',['missing-member','thumbnail','logo-only','full-canvas','receipt','parent-receipt','renderer','variant','exceptions'])
def test_full_composition_is_replayed_before_review_not_trusted_by_hash(reviewed,attack):
    row = reviewed['row']
    data = row[2].to_dict()
    view = data['views'][0]
    member = view['members'][0]
    if attack == 'missing-member':view['members']=[]
    elif attack in {'thumbnail','logo-only','full-canvas'}:
        member['sha256']='0'*64
        if attack != 'full-canvas':member['dimensions']=[100,100]
    elif attack in {'receipt','parent-receipt'}:
        member['receipt_sha256']='1'*64
        if attack=='parent-receipt':member['parent_jobs']=['substituted-parent']
    elif attack=='renderer':
        runtime=json.loads(data['runtime_json']);runtime['native_libraries']['zlib']='different'
        data['runtime_json']=canonical(runtime).decode()
    elif attack=='variant':member['variant']='substituted'
    else:
        context=json.loads(data['context_json']);spec=json.loads(context['request_json']);spec['exceptions']={}
        context['request_json']=canonical(spec).decode();data['context_json']=canonical(context).decode()
    archive = CompositionArchive(row[1].registry.operations.root)
    try:value=CompositionEvidence.from_dict(data)
    except BulkError:return
    archive.store.put_object(value.encoded,expected_sha256=value.sha256)
    with pytest.raises(BulkError):
        replace(reviewed['inputs'],composition_sha256=value.sha256).verify_bundle(reviewed['bundle'])


def test_durable_worker_receipt_substitution_is_rejected_during_review(reviewed):
    store = CompositionArchive(reviewed['archive'].store.root).store
    with store.read_connection() as db:
        job = dict(db.execute("SELECT * FROM jobs WHERE status='verified' LIMIT 1").fetchone())
    with store.transaction() as db:db.execute('UPDATE jobs SET receipt=NULL WHERE id=?',(job['id'],))
    try:
        with pytest.raises(BulkError,match='durable_receipt_substitution'):
            reviewed['inputs'].verify_bundle(reviewed['bundle'])
    finally:
        with store.transaction() as db:db.execute('UPDATE jobs SET receipt=? WHERE id=?',(job['receipt'],job['id']))


def test_unrelated_phase3_graph_observation_preserves_current_review(reviewed):
    inputs = reviewed['inputs']
    values = dict(inputs.phase3_inputs)
    data = values['graph'].data()
    data['nodes']['asset:logos/Unrelated.png']=dict(kind='asset',identity='logos/Unrelated.png',sha256='a'*64,dependencies=[])
    graph=Snapshot.create(data)
    values.update(graph=graph,expected_graph_sha256=graph.sha256)
    result = reviewed['archive'].current('synthetic.review.complete',expected_sha256=reviewed['approved'].sha256,
        inputs=replace(inputs,phase3_inputs=values),authority=reviewed['authority'])
    assert result[0] == reviewed['approved']


@pytest.mark.parametrize('attack',['missing-source-verifier','source-context','translation','destination','authority','contract','variant','request-revision'])
def test_changed_phase3_material_or_missing_currentness_is_rejected(reviewed,attack):
    inputs = reviewed['inputs']
    values = dict(inputs.phase3_inputs)
    item = values['inputs'][0]
    if attack=='missing-source-verifier':values['inputs']=(replace(item,verifier=None),)
    elif attack=='source-context':values['inputs']=(replace(item,context=None),)
    elif attack=='translation':
        import yaml
        source=yaml.safe_load(samples.english_snapshot().resources[0][1])
        key=item.report.to_dict()['required_keys'][0]['key'].split('.')
        parent=source
        for part in key[:-1]:parent=parent[part]
        parent[key[-1]]='CHANGED GENRE'
        other = samples.inputs(reviewed['row'],snapshot=samples.snapshot_for({'en':yaml.safe_dump(source).encode()}))
        values=other.phase3_inputs
    elif attack=='destination':values['expected_destination_sha256']='1'*64
    elif attack=='authority':
        target=dict(values['destination_inputs']);target['verifier']=None;values['destination_inputs']=target
    elif attack=='contract':values['inputs']=(replace(item,request=replace(item.request,contract_sha256='2'*64)),)
    elif attack=='variant':values['inputs']=(replace(item,request=replace(item.request,variant='unknown')),)
    else:values['expected_request_context_sha256']='3'*64
    with pytest.raises(BulkError):replace(inputs,phase3_inputs=values).verify_bundle(reviewed['bundle'])


def test_synthetic_review_and_legacy_logo_decisions_never_become_real_approval(reviewed):
    with pytest.raises(BulkError,match='real_authority_unavailable'):
        require_operational_approval(reviewed['approved'],authority=reviewed['authority'])
    with pytest.raises(BulkError):ReviewDecision.from_dict(dict(actor=samples.MAINTAINER,role='maintainer',decision='approved'))
    state = reviewed['approved'].to_dict()
    for field in ['authenticated','artwork_approved','contract_approved','ready','active','publication_authorized']:
        with pytest.raises(BulkError):ReviewState.from_dict(state|{field:True})


@pytest.mark.parametrize('kind',['overlay','network','family'])
def test_other_complete_native_scopes_cannot_borrow_playlist_phase3_evidence(composed,reviewed,kind):
    row = composed[kind]
    archive = CompositionArchive(row[1].registry.operations.root,readonly=True)
    assert archive.load(row[2].sha256,context=row[1]) == row[2]
    # Full bytes alone cannot hide an unsupported P3 adapter or paired cohort.
    with pytest.raises(BulkError,match='phase3_operation_binding'):
        replace(reviewed['inputs'],composition=row[1],composition_sha256=row[2].sha256).verify()


def test_standard_bigger_companion_omission_is_rejected_before_decision(composed):
    row = composed['overlay']
    data = row[2].to_dict()
    for view in data['views']:view['members']=view['members'][:1]
    with pytest.raises(BulkError):CompositionEvidence.from_dict(data)


def test_prospective_playlist_layout_gap_is_explicit_never_waived(composed):
    inputs=samples.inputs(composed['playlist'])
    assert 'effective_definition_outside_contract' in inputs.phase3_inputs['inputs'][0].report.to_dict()['blockers']
    with pytest.raises(BulkError,match='current_evidence_unavailable_or_incomplete'):inputs.verify()


def test_explicit_stale_record_retains_prior_decisions_and_cannot_be_revived(reviewed):
    archive,state,bundle = pending(reviewed,'actual-stale')
    source = reviewed['row'][0].config.asset_dir/reviewed['row'][1].registry.view().entry(bundle.to_dict()['members'][0])['names']['source']['path']
    raw = source.read_bytes()
    try:
        source.write_bytes(raw+b'changed')
        stale = archive.mark_stale(bundle.to_dict()['id'],expected_sha256=state.sha256,inputs=reviewed['inputs'])
    finally:source.write_bytes(raw)
    assert archive.history(bundle.to_dict()['id'])[0] == state
    assert stale.to_dict()['state']=='STALE'
    with pytest.raises(BulkError,match='inactive_review'):
        archive.current(bundle.to_dict()['id'],expected_sha256=stale.sha256,inputs=reviewed['inputs'])


def test_unrelated_or_unchanged_input_cannot_mark_a_review_stale(reviewed):
    with pytest.raises(BulkError,match='no_demonstrated_invalidation'):
        reviewed['archive'].mark_stale('synthetic.review.complete',expected_sha256=reviewed['approved'].sha256,
            inputs=reviewed['inputs'],authority=reviewed['authority'])


@pytest.mark.parametrize('attack',['blob','transaction'])
def test_interrupted_review_append_leaves_no_visible_head_and_recovers(reviewed,monkeypatch,attack):
    from create_defaults.bulk.lifecycle.package_e import SidecarStore
    archive = reviewed['archive']
    identity = 'synthetic.review.interrupted-'+attack
    if attack == 'blob':
        original = SidecarStore.put_object
        def interrupted(self,raw,**kw):
            if json.loads(raw).get('kind')==ReviewState.KIND:raise OSError('injected incomplete write')
            return original(self,raw,**kw)
        with monkeypatch.context() as patch:
            patch.setattr(SidecarStore,'put_object',interrupted)
            with pytest.raises(OSError):archive.start(identity,submitter=samples.SUBMITTER,inputs=reviewed['inputs'])
    else:
        writer = SidecarStore(archive.store.root)
        with writer.transaction() as db:
            db.execute("CREATE TRIGGER interrupt_p4m4_test BEFORE INSERT ON p4m4_reviews BEGIN SELECT RAISE(ABORT,'injected transaction interruption'); END")
        try:
            with pytest.raises(sqlite3.IntegrityError):archive.start(identity,submitter=samples.SUBMITTER,inputs=reviewed['inputs'])
        finally:
            with writer.transaction() as db:db.execute('DROP TRIGGER interrupt_p4m4_test')
    reopened = ReviewArchive(archive.store.root)
    assert not reopened.history(identity)
    recovered = reopened.start(identity,submitter=samples.SUBMITTER,inputs=reviewed['inputs'])
    assert reopened.start(identity,submitter=samples.SUBMITTER,inputs=reviewed['inputs']) == recovered
    assert len(reopened.history(identity)) == 1


def test_corrupt_review_blob_and_index_updates_fail_closed(reviewed):
    archive = reviewed['archive']
    path = archive.store.root/'objects'/(reviewed['approved'].sha256+'.json')
    raw = path.read_bytes()
    try:
        path.write_bytes(raw+b'corrupt')
        with pytest.raises(BulkError):ReviewArchive(archive.store.root)
    finally:path.write_bytes(raw)
    from create_defaults.bulk.lifecycle.package_e import SidecarStore
    writer = SidecarStore(archive.store.root)
    with pytest.raises(sqlite3.IntegrityError):
        with writer.transaction() as db:db.execute('UPDATE p4m4_reviews SET revision=99')
    assert ReviewArchive(archive.store.root).history('synthetic.review.complete')[-1] == reviewed['approved']


@pytest.mark.parametrize('change',['direct','transitive','shared-font','companion'])
def test_selective_invalidation_follows_actual_graph_edges_and_companions(reviewed,composed,change):
    # Actual graph scopes from M2, retaining distinct stable identities per trial.
    row = reviewed['row'];base = row[1].candidate.graph.data()
    graph = deepcopy(base)
    source = next(k for k,n in graph['nodes'].items() if n['kind']=='asset' and 'Bebas' not in k and 'fonts/' not in k)
    member = next(iter(graph['outputs']))
    other = 'fixture.unrelated'
    graph['nodes']['output:'+other]=dict(kind='output',identity=other,sha256='a'*64,dependencies=[])
    output=deepcopy(graph['outputs'][member]);output.update(node='output:'+other,local_path='defaults-en/playlist/Unrelated.jpg',public_path='playlist/Unrelated.jpg',companions=[],context_sha256='a'*64)
    graph['outputs'][other]=output
    if change=='direct':changed='output:'+member
    elif change=='transitive':changed=source
    elif change=='shared-font':
        changed=next(k for k,n in graph['nodes'].items() if n['kind']=='asset' and 'fonts/' in k)
        graph['nodes']['output:'+other]['dependencies']=[changed]
    else:
        changed='output:'+member
        graph['outputs'][member]['companions']=[other];graph['outputs'][other]['companions']=[member]
    result=selective_impact(Snapshot.create(graph),[changed],{'selected':[member],'unrelated':[other]})
    assert 'selected' in result['invalidated']
    assert ('unrelated' in result['invalidated']) == (change in {'shared-font','companion'})
    assert ('unrelated' in result['preserved']) == (change in {'direct','transitive'})


def test_generated_family_uncertainty_blocks_scope_claims_and_known_child_is_scoped(composed):
    row = composed['family'];graph=row[1].candidate.graph;ids=sorted(graph.index().outputs)
    node=next(k for k,n in graph.index().nodes.items() if n['kind']=='family')
    with pytest.raises(BulkError,match='unknown_invalidation_scope'):
        selective_impact(graph,[node],{'family':ids})
    result=selective_impact(graph,['output:'+ids[0]],{'family':ids})
    assert result['invalidated']==['family']


def test_native_review_cannot_import_activation_or_publish(reviewed,monkeypatch):
    import socket
    import requests
    from create_defaults.bulk import operator_publication
    from create_defaults.bulk.contracts.activation.controller import Controller
    def prohibited(*a,**kw):raise AssertionError('M4 attempted production integration')
    for obj,name in [(requests.Session,'request'),(socket.socket,'connect'),(operator_publication,'stage'),(operator_publication,'draft'),(Controller,'transition')]:
        monkeypatch.setattr(obj,name,prohibited)
    assert reviewed['archive'].current('synthetic.review.complete',expected_sha256=reviewed['approved'].sha256,
        inputs=reviewed['inputs'],authority=reviewed['authority'])[0]==reviewed['approved']


def test_current_operation_revision_change_rejects_prior_review(composed):
    # A separate actual native trial: never damage the shared original operation.
    from create_defaults.bulk.lifecycle.previews import CompositionTrial
    from create_defaults.bulk.lifecycle import composition
    from create_defaults.bulk.lifecycle.models import Operation
    from create_defaults.phase4.tests import composition_samples
    with CompositionTrial() as trial:
        ctx=composition_samples.poster(trial,'Genre')
        evidence=composition.compose(ctx,trial,exceptions=[composition_samples.exception(ctx.candidate)])
        row=(trial,ctx,evidence,[]);inputs=samples.inputs(row)
        archive=ReviewArchive.create(ctx.registry.operations.root)
        pending=archive.start('synthetic.review.revision',submitter=samples.SUBMITTER,inputs=inputs)
        store=ctx.registry.operations
        previous=store.history('synthetic.operation.composition')[-1]
        event=next(e for e in store.journal() if e.to_dict()['record_sha256']==previous.sha256)
        value=previous.to_dict()
        heads={(h['kind'],h['id']):h for h in store.inspect()['heads']}
        value.update(revision=2,previous_sha256=previous.sha256,previous_event_sha256=event.sha256,state='structurally_validated')
        for r in value['reads']:
            h=heads.get((r['kind'],r['id']),dict(revision=0,sha256=None))
            r.update(revision=h['revision'],sha256=h['sha256'])
        record=Operation.from_dict(value)
        store.append(record,expected_revision=1,expected_sha256=previous.sha256,expected_event_sha256=event.sha256)
        with pytest.raises(Conflict,match='M1 operation revision'):
            archive.current('synthetic.review.revision',expected_sha256=pending.sha256,inputs=inputs)


def test_m4_exact_head_native_review_and_blocker_proof(reviewed):
    from ci.validation import identity,write
    from ci.phase4_review import SCHEMA,implementation_checksum
    from ci.phase4 import checksum
    archive=reviewed['archive'];evidence=reviewed['row'][2].to_dict()
    assert archive.current('synthetic.review.complete',expected_sha256=reviewed['approved'].sha256,
        inputs=reviewed['inputs'],authority=reviewed['authority'])[0]==reviewed['approved']
    members={v['appearance']:{m['identity']:m['sha256'] for m in v['members']} for v in evidence['views']}
    value=dict(**identity(),kind='phase4-m4-complete-review-proof',schema_sha256=checksum(SCHEMA),
        implementation_sha256=implementation_checksum(),cohort='genre',members=members,
        states=[s.to_dict()['state'] for s in archive.history('synthetic.review.complete')],
        submitter=samples.SUBMITTER,maintainer=samples.MAINTAINER,attribution='synthetic-only',
        all_encoded_bytes_verified=True,immutable_reopen_verified=True,
        composition_sha256=reviewed['row'][2].sha256,review_sha256=reviewed['approved'].sha256,
        authenticated=False,ready=False,active=False,publication_authorized=False,
        contract_approvals_missing=reviewed['inputs'].phase3.to_dict()['m7']['exact_approvals_missing'])
    value['sha256']=fingerprint(value)
    from ci.phase4_composition import OUT
    write(OUT/'phase4-m4-review-proof.json',value)
