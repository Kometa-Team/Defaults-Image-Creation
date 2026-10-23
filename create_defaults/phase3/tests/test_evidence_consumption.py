"""M4 scope, freshness, replay and missing-evidence adversarial controls."""

from dataclasses import replace
import json

import pytest

from create_defaults.bulk.common import BulkError,canonical,fingerprint
from create_defaults.bulk.contracts.evidence_consumption import consume,revalidate,RequestContext,ConsumptionAttestation,read_attestation
from create_defaults.bulk.contracts.translation_preflight import evaluate as translation
from create_defaults.bulk.contracts.language_policy import LanguagePolicy
from create_defaults.bulk.contracts.destination_preflight import evaluate as destination
from create_defaults.phase3.tests.consumption_samples import example,assemble,input_for,graph_change
from create_defaults.phase3.tests.translation_samples import snapshot_for,ROOT


@pytest.fixture(scope='module')
def chain(tmp_path_factory):
    return example(tmp_path_factory.mktemp('m4-chain'))


def test_compatible_chain_is_explicit_simulation_with_all_m7_blockers(chain):
    result=consume(**chain).to_dict()
    assert result['chain_compatible'] and result['simulation_eligible'] and result['simulation']
    assert result['m7']['selectors']==22 and result['m7']['variants']==278
    assert result['m7']['exact_approvals_missing']==22 and result['m7']['ready']==result['m7']['active']==0
    assert 'm7:missing_exact_hash_maintainer_approval' in result['blockers']
    for flag in ['publication_authorized','production_enforcement','ready','active','technical_eligible']:
        assert result[flag] is False


@pytest.mark.parametrize('missing',['m2','m3','both'])
def test_missing_companions_are_blocking_not_partial_success(chain,missing):
    s=chain.copy()
    if missing in {'m2','both'}:
        s['inputs']=(replace(s['inputs'][0],report=None,expected_sha256=None),)
    s.update(destination=None,expected_destination_sha256=None,destination_inputs=None)
    report=consume(**s).to_dict()
    assert not report['chain_compatible'] and not report['simulation_eligible']
    assert 'missing_m3' in report['blockers']
    if missing!='m3':assert any(b.startswith('missing_m2:') for b in report['blockers'])


@pytest.mark.parametrize('pin',['expected_language_policy_sha256','expected_destination_sha256','expected_request_context_sha256','expected_graph_sha256'])
def test_independently_selected_pins_cannot_be_substituted(chain,pin):
    with pytest.raises(BulkError):consume(**(chain|{pin:'f'*64}))


def test_forged_translation_pin_and_rehashed_forgery_fail(chain):
    item=chain['inputs'][0]
    with pytest.raises(BulkError):consume(**(chain|dict(inputs=(replace(item,expected_sha256='f'*64),))))
    data=item.report.to_dict();data['resolved_caption']='Forged but self-hashed'
    forged=type(item.report).from_dict(data)
    with pytest.raises(BulkError):consume(**(chain|dict(inputs=(replace(item,report=forged,expected_sha256=forged.sha256),))))


@pytest.mark.parametrize('field',['publication_authorized','production_enforcement','ready','active','technical_eligible'])
def test_report_flags_cannot_be_forged_even_with_recomputed_binding(chain,field):
    value=consume(**chain).to_dict();value[field]=True
    value['binding_sha256']=fingerprint({k:v for k,v in value.items() if k not in {'binding_sha256','graph_snapshot_sha256'}})
    with pytest.raises(BulkError):ConsumptionAttestation.from_dict(value)


@pytest.mark.parametrize('change',['id','outputs','language','variant','contract','review','dependencies'])
def test_subject_and_context_mutation_cannot_replay(chain,change):
    old=consume(**chain);item=chain['inputs'][0]
    if change=='outputs':request=replace(item.request,outputs_json=canonical([]))
    elif change=='id':request=replace(item.request,identity='foreign.subject')
    elif change=='review':request=replace(item.request,review_context_sha256=fingerprint('changed-review'))
    elif change=='variant':request=replace(item.request,variant='foreign-variant')
    elif change=='contract':request=replace(item.request,contract_sha256='f'*64)
    elif change=='dependencies':request=replace(item.request,rules_sha256='f'*64)
    else:request=item.request
    changed=replace(item,request=request,requested='en' if change=='language' else item.requested)
    with pytest.raises((BulkError,KeyError)):revalidate(old,expected_sha256=old.sha256,**(chain|dict(inputs=(changed,))))


@pytest.mark.parametrize('mutation',['relevant-comment','same-text-commit','verification-context','required-key','provenance'])
def test_material_source_changes_reject_old_evidence_even_with_same_visible_text(chain,mutation):
    item=chain['inputs'][0]
    snapshot=item.snapshot
    if mutation in {'relevant-comment','required-key'}:
        raw={path.removeprefix('defaults/').removesuffix('.yml'):data for path,data in snapshot.resources}
        raw['fr']+=b'\n# source review changed\n' if mutation=='relevant-comment' else b'\nother_key: unchanged visual output\n'
        snapshot=snapshot_for(raw)
    elif mutation in {'same-text-commit','provenance'}:
        value=snapshot.snapshot.data
        # LanguageSnapshot exposes detached data through .data; no source fetch.
        from create_defaults.bulk.languages import LanguageSnapshot
        value['provenance']['commit']='c'*40
        if mutation=='provenance':value['provenance']['repository']='Fixture/ChangedTranslations'
        snapshot=replace(snapshot,snapshot=LanguageSnapshot.create(value['languages'],provenance=value['provenance']))
        if mutation=='provenance':
            repository=json.loads(snapshot.repository_json);repository['name']='Fixture/ChangedTranslations'
            snapshot=replace(snapshot,repository_json=canonical(repository))
    label='changed-explicit-context' if mutation=='verification-context' else 'explicit-verification'
    new,lp=input_for(item.request,snapshot,item.requested,context_label=label)
    current=assemble((new,),lp)
    old=consume(**chain)
    assert new.report.to_dict()['resolved_caption']==item.report.to_dict()['resolved_caption']
    with pytest.raises(BulkError):revalidate(old,expected_sha256=old.sha256,**current)
    # Replaying old M2 against current inputs also fails before M3 consumption.
    with pytest.raises(BulkError):consume(**(current|dict(inputs=(replace(new,report=item.report,expected_sha256=item.report.sha256),))))


def test_unrelated_language_and_unused_resources_preserve_selected_consumption(chain):
    item=chain['inputs'][0]
    raw={path.removeprefix('defaults/').removesuffix('.yml'):data for path,data in item.snapshot.resources}
    raw['de']=b'unused: unrelated\n'
    new,lp=input_for(item.request,snapshot_for(raw),item.requested)
    current=assemble((new,),lp)
    old=consume(**chain)
    assert old.encoded==consume(**current).encoded
    assert revalidate(old,expected_sha256=old.sha256,**current).sha256==old.sha256


def test_unrelated_output_change_in_same_source_file_preserves_selected_context(chain):
    import yaml
    from pathlib import Path
    from create_defaults.bulk.contracts.expanded.resolution import resolve
    from create_defaults.phase3.tests.translation_samples import request_for
    item=chain['inputs'][0]
    old=consume(**chain)
    # Resolve an explicitly provided new snapshot; the consumer itself does not
    # refresh upstream input. Another row must not become this row's material.
    profile=Path(next(p for name,p,_ in item.request.resolution.source_pins if name=='profiles.yml'))
    path=Path(next(p for name,p,_ in item.request.resolution.source_pins if name!='profiles.yml'))
    original=path.read_bytes()
    try:
        data=yaml.safe_load(original)
        other=json.loads(json.dumps(data['definitions'][0]))
        other['id']='fixture.unrelated';other['output']['filename']='Unrelated.png'
        other['output']['remote_paths']={k:None for k in other['output']['remote_paths']}
        data['definitions'].append(other)
        path.write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=True),encoding='utf8')
        resolution=resolve([path],profiles_path=profile)
        request=request_for(resolution,item.request.package,item.requested,identity=item.request.identity)
        new,lp=input_for(request,item.snapshot,item.requested)
        assert new.report.encoded==item.report.encoded
        current=assemble((new,),lp)
        assert revalidate(old,expected_sha256=old.sha256,**current).sha256==old.sha256
    finally:path.write_bytes(original)


@pytest.mark.parametrize('pin',['subject','membership','policy'])
def test_request_membership_and_foreign_policy_cannot_be_rebound(chain,pin):
    if pin=='policy':
        data=chain['language_policy'].to_dict();data['version']='2.0.0'
        policy=LanguagePolicy.from_dict(data)
        current=chain|dict(language_policy=policy,expected_language_policy_sha256=policy.sha256)
    else:
        value=chain['request_context'].to_dict()
        value['subjects']=['f'*64] if pin=='subject' else sorted(value['subjects']+['f'*64])
        ctx=RequestContext.from_dict(value)
        current=chain|dict(request_context=ctx,expected_request_context_sha256=ctx.sha256)
    with pytest.raises(BulkError):consume(**current)


@pytest.mark.parametrize('change',['asset','definition','review','evidence','missing','unresolved','exception'])
def test_relevant_graph_and_evidence_changes_invalidate(chain,change):
    def mutate(g):
        identity=next(iter(g['outputs']))
        if change=='asset':g['nodes'][next(k for k in g['nodes'] if k.startswith('asset:'))]['sha256']=fingerprint('newasset')
        elif change=='definition':g['nodes']['definition:'+identity]['sha256']=fingerprint('newdefinition')
        elif change=='review':g['outputs'][identity]['context_sha256']=fingerprint('newcontext')
        elif change=='evidence':g['outputs'][identity]['evidence']['receipts']=[fingerprint('changed-receipt')]
        elif change=='missing':g['outputs'][identity]['local_path']='different/path.png'
        elif change=='unresolved':g['unresolved']=['unknown dependency']
        else:
            key='exception:'+identity+'/review'
            g['nodes'][key]=dict(kind='exception',identity=identity+'/review',sha256=fingerprint('new-exception'),dependencies=[])
            g['nodes']['output:'+identity]['dependencies'].append(key)
    current=graph_change(chain,mutate);old=consume(**chain)
    with pytest.raises(BulkError):revalidate(old,expected_sha256=old.sha256,**current)


def test_unrelated_graph_changes_preserve_selected_binding_but_record_new_observation(chain):
    def mutate(g):g['nodes']['asset:logos/unused.png']=dict(kind='asset',identity='logos/unused.png',sha256=fingerprint('unused'),dependencies=[])
    current=graph_change(chain,mutate);old=consume(**chain)
    result=revalidate(old,expected_sha256=old.sha256,**current)
    assert old.sha256!=result.sha256
    assert old.to_dict()['binding_sha256']==result.to_dict()['binding_sha256']
    assert old.to_dict()['graph_snapshot_sha256']!=result.to_dict()['graph_snapshot_sha256']


def test_request_revision_replay_is_rejected_and_expected_head_is_independent(chain):
    old=consume(**chain);data=chain['request_context'].to_dict()
    data.update(revision=2,previous_sha256=chain['request_context'].sha256)
    context=RequestContext.from_dict(data)
    with pytest.raises(BulkError):consume(**(chain|dict(request_context=context)))
    current=chain|dict(request_context=context,expected_request_context_sha256=context.sha256)
    with pytest.raises(BulkError):revalidate(old,expected_sha256=old.sha256,**current)


@pytest.mark.parametrize('change',['branch','permissions','expiry','revocation','inventory','owner','root','grant','authority-context'])
def test_current_authority_and_target_changes_cannot_replay(chain,change):
    s=chain.copy();ds=s['destination_inputs'].copy();s['destination_inputs']=ds
    if change=='permissions':
        provider=ds['verifier']
        ds['verifier']=type(provider)(replace(provider.facts,permissions=('contents:read',)))
    elif change=='expiry':ds['context']=replace(ds['context'],as_of='2030-01-03T00:00:00Z')
    elif change=='authority-context':ds['context']=replace(ds['context'],verification_context_sha256='f'*64)
    elif change=='inventory':
        from create_defaults.phase3.tests.destination_samples import inventory
        previous=ds['inventory'].to_dict()
        inv=inventory(previous['repository'],previous['branch'],{'unrelated/new.png':'100644'})
        ds.update(inventory=inv,expected_inventory_sha256=inv.sha256)
    else:
        value=ds['evidence'].to_dict()
        if change=='branch':value['target']['branch']='changed-main'
        elif change=='root':value['target']['root']='changed-root'
        elif change=='owner':value['target']['repository']['owner_id']=999
        elif change=='grant':value['authorization']['assertion_sha256']='f'*64
        elif change=='revocation':value['authorization']['revocation']['status']='revoked'
        evidence=type(ds['evidence']).from_dict(value)
        ds.update(evidence=evidence,expected_evidence_sha256=evidence.sha256)
    with pytest.raises(BulkError):consume(**s)


def test_real_source_verification_unavailable_remains_fail_closed(chain):
    item=replace(chain['inputs'][0],verifier=None)
    report=translation(item.request,chain['language_policy'],item.requested,item.snapshot,item.selection,context=item.context)
    item=replace(item,report=report,expected_sha256=report.sha256)
    current=assemble((item,),chain['language_policy'])
    result=consume(**current).to_dict()
    assert not result['simulation_eligible'] and not result['technical_eligible']
    assert any('source_currentness:unavailable' in b for b in result['blockers'])


def test_missing_m2_cannot_be_hidden_by_supplied_m3(chain):
    with pytest.raises(BulkError):consume(**(chain|dict(inputs=(replace(chain['inputs'][0],report=None,expected_sha256=None),))))


def test_cancellation_returns_no_partial_attestation(chain):
    with pytest.raises(BulkError):consume(**chain,cancel=lambda:True)


def test_canonical_attestation_roundtrip_and_external_pin(chain):
    report=consume(**chain)
    assert read_attestation(report.encoded,expected_sha256=report.sha256).encoded==canonical(report.to_dict())
    with pytest.raises(BulkError):read_attestation(report.encoded,expected_sha256='f'*64)
    with pytest.raises(BulkError):ConsumptionAttestation.from_bytes(report.encoded[:-1])


def test_full_canonical_fixture_across_platforms(tmp_path):
    report=consume(**example(tmp_path,language='fr'))
    expected=json.loads((ROOT/'create_defaults/phase3/tests/evidence-consumption-v1.json').read_text(encoding='utf8'))
    assert report.to_dict()==expected['evidence'] and report.sha256==expected['sha256']
