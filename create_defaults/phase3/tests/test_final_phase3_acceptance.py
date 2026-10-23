"""M5 complete synthetic chains and adversarial failures, with actual M1–M4 APIs."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from create_defaults.bulk.common import BulkError,Conflict,canonical,fingerprint
from create_defaults.bulk.contracts.destination_preflight import DestinationInventory
from create_defaults.bulk.contracts.evidence_consumption import consume,revalidate,RequestContext
from create_defaults.bulk.contracts.evidence_consumption.storage import Archive
from create_defaults.phase3.tests.acceptance_samples import routed,changed_destination,assert_blocked,integration_cases
from create_defaults.phase3.tests.consumption_samples import example,assemble,input_for,graph_change
from create_defaults.phase3.tests.translation_samples import ROOT,KEY,synthetic_request,snapshot_for,synthetic_overlay
from create_defaults.phase3.tests.destination_samples import OFFICIAL,USER


@pytest.fixture(scope='module')
def french(tmp_path_factory):return example(tmp_path_factory.mktemp('m5-french'),language='fr')


def test_complete_chain_archive_and_cross_platform_canonical_export(tmp_path):
    result=integration_cases(tmp_path)
    expected=json.loads((Path(__file__).with_name('phase3-final-acceptance-v1.json')).read_text(encoding='utf8'))
    assert result==expected['evidence'] and fingerprint(result)==expected['sha256']
    from ci.validation import identity,write
    write(ROOT/'config/phase3-ci/phase3-final-acceptance.json',{**identity(),'evidence':result,'evidence_sha256':fingerprint(result)})


@pytest.mark.parametrize('attack',['forged_translation','stale_source','unsupported_language','subject_substitution','membership_substitution'])
def test_earlier_stage_substitution_cannot_be_repaired_by_later_success(french,attack):
    item=french['inputs'][0]
    if attack=='forged_translation':
        value=item.report.to_dict();value['resolved_caption']='Forged approved caption'
        forged=type(item.report).from_dict(value)
        current=routed(french|dict(inputs=(replace(item,report=forged,expected_sha256=forged.sha256),)))
        code='p3m2_report_replay'
    elif attack=='stale_source':
        from create_defaults.bulk.languages import LanguageSnapshot
        value=item.snapshot.snapshot.data;value['provenance']['commit']='c'*40
        snapshot=replace(item.snapshot,snapshot=LanguageSnapshot.create(value['languages'],provenance=value['provenance']))
        current=french|dict(inputs=(replace(item,snapshot=snapshot),));code='p3m2_selection_binding'
    elif attack=='unsupported_language':
        current=french|dict(inputs=(replace(item,requested='unregistered'),));code='unknown_language'
    elif attack=='subject_substitution':
        current=french|dict(inputs=(replace(item,request=replace(item.request,identity='foreign.poster')),));code=None
    else:
        current=french|dict(inputs=(replace(item,request=replace(item.request,outputs_json=canonical([]))),));code='p3m2_output_mapping'
    with pytest.raises((BulkError,KeyError)) as error:consume(**current)
    if code:assert error.value.code==code


def test_reviewed_english_fallback_does_not_hide_missing_target_in_complete_chain(tmp_path):
    fallback=dict(id='acceptance.fallback',reviewer='historical-test-only',reason='Negative control',policy_version='1.0.0',text=None,language='en',key=KEY)
    request=synthetic_request(tmp_path/'request',language='fr',caption=dict(fallback=fallback))
    item,lp=input_for(request,snapshot_for({'en':b'key_names: {TIMELINE_ORDER: Timeline Order}','fr':b'key_names: {}'}),'fr')
    assert item.report.to_dict()['resolved_caption']=='TIMELINE ORDER'
    assert not item.report.to_dict()['technical_eligible']
    result=assert_blocked(consume(**assemble((item,),lp)))
    assert not result['chain_compatible'] and not result['simulation_eligible']
    assert any('fr:'+KEY+':missing' in b for b in result['blockers'])


@pytest.mark.parametrize('attack',['official_non_english','forged_owner','missing_authority','expired_authority','revoked_authority',
    'incomplete_inventory','invalid_inventory','cross_language_collision','synthetic_as_real'])
def test_destination_attacks_remain_blocked_after_fresh_m3_and_m4_consumption(french,attack):
    current=french
    ds=french['destination_inputs']
    changes={}
    if attack=='forged_owner':changes['verifier']=type(ds['verifier'])(replace(ds['verifier'].facts,principal_id=9999))
    elif attack=='missing_authority':changes['verifier']=None
    elif attack=='expired_authority':changes['context']=replace(ds['context'],as_of='2030-01-03T00:00:00Z')
    elif attack=='cross_language_collision':
        current=routed(french,extra_mappings=[dict(language='en',repository=USER,branch='Main',root=None,paths=['playlist/Reviewed.png'])])
    elif attack in {'incomplete_inventory','invalid_inventory'}:
        value=ds['inventory'].to_dict()
        if attack=='invalid_inventory':
            value['commit_hex']+='00'
            with pytest.raises(BulkError):DestinationInventory.from_dict(value)
            return
        value['pages']=[]
        inv=DestinationInventory.from_dict(value)
        changes.update(inventory=inv,expected_inventory_sha256=inv.sha256)
        evidence=ds['evidence'].to_dict();evidence['target']['inventory_sha256']=inv.sha256
        evidence=type(ds['evidence']).from_dict(evidence)
        changes.update(evidence=evidence,expected_evidence_sha256=evidence.sha256)
    else:
        value=ds['evidence'].to_dict()
        if attack=='official_non_english':
            value['target']['repository']=OFFICIAL
            inventory=ds['inventory'].to_dict();inventory['repository']=OFFICIAL
            inv=DestinationInventory.from_dict(inventory)
            value['target']['inventory_sha256']=inv.sha256
            changes.update(inventory=inv,expected_inventory_sha256=inv.sha256)
        elif attack=='revoked_authority':value['authorization']['revocation']['status']='revoked'
        else:value['authorization']['synthetic']=False
        evidence=type(ds['evidence']).from_dict(value)
        changes.update(evidence=evidence,expected_evidence_sha256=evidence.sha256)
        context=replace(ds['context'],evidence_sha256=evidence.sha256,target_sha256=fingerprint(value['target']))
        changes['context']=context
        changes['verifier']=type(ds['verifier'])(replace(ds['verifier'].facts,context=context,target_sha256=fingerprint(value['target'])))
    if changes:current=changed_destination(current,**changes)
    result=assert_blocked(consume(**current))
    assert not result['simulation_eligible']
    if attack=='official_non_english':assert 'm3:official_non_english_prohibited' in result['blockers']
    if attack=='incomplete_inventory':assert 'm3:inventory_incomplete' in result['blockers']
    if attack=='cross_language_collision':assert 'm3:cross_language_alias' in result['blockers']


def test_unicode_collision_uses_exact_source_names_without_automatic_rename(tmp_path):
    import unicodedata,yaml
    from create_defaults.bulk.contracts.expanded.resolution import resolve
    from create_defaults.phase3.tests.translation_samples import request_for
    base=example(tmp_path,language='fr');item=base['inputs'][0]
    path=tmp_path/'fixture.yml';value=yaml.safe_load(path.read_text(encoding='utf8'))
    value['definitions'][0]['output']['filename']='Élan.png'
    value['definitions'][0]['output']['remote_paths']['fr']='playlist/Élan.png'
    path.write_text(yaml.safe_dump(value,allow_unicode=True,sort_keys=True),encoding='utf8')
    request=request_for(resolve([path],profiles_path=tmp_path/'profiles.yml'),item.request.package,'fr')
    item,lp=input_for(request,language='fr')
    chain=assemble((item,),lp)
    chain=routed(chain,entries={unicodedata.normalize('NFD','playlist/Élan.png'):'100644'})
    result=assert_blocked(consume(**chain))
    assert not result['simulation_eligible']
    assert chain['destination'].to_dict()['outputs'][0]['output']['public_path']=='playlist/Élan.png'
    assert chain['destination'].to_dict()['outputs'][0]['diagnostics']


@pytest.mark.parametrize('change',['relevant_dependency','request_revision','authority_expiry','unrelated_resource'])
def test_archived_chain_replay_requires_current_material_context(french,tmp_path,change):
    original=consume(**french);archive=Archive(tmp_path/'isolated')
    archive.append(original,french['request_context'],expected_head_sha256=None,expected_context_sha256=french['request_context'].sha256)
    restored=archive.history(french['request_context'].to_dict()['id'])[0]
    if change=='relevant_dependency':
        def mutate(g):g['nodes'][next(k for k in g['nodes'] if k.startswith('asset:'))]['sha256']=fingerprint('changed-logo-bytes')
        current=graph_change(french,mutate)
    elif change=='request_revision':
        value=french['request_context'].to_dict();value.update(revision=2,previous_sha256=french['request_context'].sha256)
        context=RequestContext.from_dict(value)
        current=french|dict(request_context=context,expected_request_context_sha256=context.sha256)
    elif change=='authority_expiry':
        current=changed_destination(french,context=replace(french['destination_inputs']['context'],as_of='2030-01-03T00:00:00Z'))
    else:
        item=french['inputs'][0]
        resources={p.removeprefix('defaults/').removesuffix('.yml'):b for p,b in item.snapshot.resources}
        resources['de']=b'not_used: Unrelated\n'
        selected,lp=input_for(item.request,snapshot_for(resources),'fr')
        current=assemble((selected,),lp)
    if change=='unrelated_resource':assert revalidate(restored,expected_sha256=restored.sha256,**current).sha256==original.sha256
    else:
        with pytest.raises(BulkError) as error:revalidate(restored,expected_sha256=restored.sha256,**current)
        assert error.value.code=='p3m4_stale_consumption'


@pytest.mark.parametrize('attack',['partial','corrupt','wrong_head'])
def test_complete_chain_archival_cannot_hide_partial_corruption_or_head_replay(french,tmp_path,attack):
    archive=Archive(tmp_path/'isolated');report=consume(**french);ctx=french['request_context']
    if attack=='partial':
        def interrupted():raise KeyboardInterrupt('Synthetic interruption')
        with pytest.raises(KeyboardInterrupt):archive.append(report,ctx,expected_head_sha256=None,expected_context_sha256=ctx.sha256,before_commit=interrupted)
        assert archive.history(ctx.to_dict()['id'])==()
    else:
        archive.append(report,ctx,expected_head_sha256=None,expected_context_sha256=ctx.sha256)
        if attack=='corrupt':
            archive.contracts._blob_path(report.sha256).write_bytes(b'{')
            with pytest.raises(BulkError):archive.history(ctx.to_dict()['id'])
        else:
            with pytest.raises(Conflict):archive.append(report,ctx,expected_head_sha256='f'*64,expected_context_sha256=ctx.sha256)


def test_m7_and_render_publication_isolation_survives_complete_synthetic_success(french,monkeypatch):
    from create_defaults.bulk.contracts.activation.controller import Controller
    from create_defaults.bulk import workers,remote
    from create_defaults import create_poster
    import requests
    def prohibited(*a,**k):raise AssertionError('Acceptance invoked production operation')
    with monkeypatch.context() as guard:
        for obj,name in [(Controller,'__init__'),(workers.PersistentWorkers,'__init__'),(requests.Session,'request'),(create_poster,'create_poster')]:
            guard.setattr(obj,name,prohibited)
        value=assert_blocked(consume(**french))
        assert value['simulation'] and value['simulation_eligible']
        assert value['m7']['exact_approvals_missing']==22 and value['m7']['ready']==value['m7']['active']==0
        assert 'm7:missing_exact_hash_maintainer_approval' in value['blockers']


def test_all_existing_phase3_ids_and_production_interfaces_are_unchanged():
    import subprocess
    base='a30283fb88c6964d40e96a4ab15233592ec92243'
    old=json.loads(subprocess.check_output(['git','show',base+':ci/phase3-test-ids.json'],cwd=ROOT))
    current=json.loads((ROOT/'ci/phase3-test-ids.json').read_text())
    assert len(old)==628 and set(old)<=set(current)
    changed=subprocess.check_output(['git','diff','--name-only',base],cwd=ROOT,text=True).splitlines()
    assert not any(p.startswith('create_defaults/bulk/contracts/') and p!='create_defaults/bulk/contracts/evidence_consumption/engine.py' for p in changed)
    for path in ['.github/workflows/default-poster-validation.yml','ci/validation.py','ci/validation-plan.json','ci/phase3.py','ci/original-test-ids.json']:
        assert subprocess.check_output(['git','show',base+':'+path],cwd=ROOT).replace(b'\r\n',b'\n')==(ROOT/path).read_bytes().replace(b'\r\n',b'\n')


def test_negative_matrix_is_covered_by_exact_mandatory_test_ids():
    matrix=json.loads(Path(__file__).with_name('phase3-acceptance-matrix-v1.json').read_text(encoding='utf8'))
    required=set(json.loads((ROOT/'ci/phase3-test-ids.json').read_text()))
    assert matrix['schema_version']==1 and matrix['kind']=='phase3-security-acceptance-matrix'
    assert len(matrix['families'])==17 and len({r['id'] for r in matrix['families']})==17
    for family in matrix['families']:
        assert family['nodeids'] and set(family['nodeids'])<=required
        assert family['required_outcome']=='fail_closed'
