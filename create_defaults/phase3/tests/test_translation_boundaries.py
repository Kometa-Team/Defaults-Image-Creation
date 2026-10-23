"""Real categories, overlays, bounded evidence and process isolation controls."""

from dataclasses import replace
import json
import os
import subprocess
import sys

import pytest

from create_defaults.bulk.common import BulkError, canonical, fingerprint
from create_defaults.bulk.contracts.translation_preflight import evaluate
from create_defaults.bulk.contracts.translation_preflight.engine import prepare
from create_defaults.phase3.tests.translation_samples import (
    ROOT,CATALOG,real_package,request_for,real_resolution,synthetic_request,synthetic_overlay,
    snapshot_for,selected,SyntheticCurrent,
)
from create_defaults.phase3.tests.test_translation_preflight import run


@pytest.mark.parametrize('language',['en','fr'])
def test_overlay_source_preservation_and_empty_keys(language):
    request=synthetic_overlay()
    result=run(request,requested=language).to_dict()
    assert result['required_keys']==result['results']==[]
    assert result['translation_selection'] is None and result['key_status']=='not_applicable'
    assert result['technical_eligible']==(language=='en')
    assert 'destination' in result['independent_checks']
    assert not result['publication_authorized'] and not result['ready']
    assert result['subject']['contract']['kind']=='overlay'


@pytest.mark.parametrize('mutation',['record-pin','foreign-record','variant','contract-pin','rules-pin'])
def test_overlay_exact_membership_cannot_be_substituted(mutation):
    request=synthetic_overlay()
    changes={'record-pin':{'record_sha256':'f'*64},'foreign-record':{'record':None},'variant':{'variant':'foreign'},
             'contract-pin':{'contract_sha256':'f'*64},'rules-pin':{'rules_sha256':'f'*64}}
    with pytest.raises(BulkError):run(replace(request,**changes[mutation]))


def test_real_captionless_category_has_no_inferred_embedded_logo_text():
    from create_defaults.bulk.contracts.expanded.resolution import resolve
    resolution=resolve([CATALOG/'aspect.yml'])
    package=real_package('Aspect')
    definition=next(iter(resolution.data()['expanded'].values()))
    _,members=package.data()
    request=request_for(resolution,package,identity=definition['id'],variant=members[definition['id']]['variant'])
    result=run(request).to_dict()
    assert result['required_keys']==[] and result['technical_eligible']
    assert result['resolved_caption']==''


def test_real_generated_caption_template_keys_from_expanded_definitions():
    from create_defaults.bulk.contracts.expanded.resolution import resolve
    resolution=resolve([CATALOG/'audiolanguage.yml'])
    package=real_package('AudioLanguage')
    definition=next(iter(resolution.data()['expanded'].values()))
    assert definition['caption']['template_key']
    _,members=package.data()
    request=request_for(resolution,package,identity=definition['id'],variant=members[definition['id']]['variant'])
    raw=(ROOT/'create_defaults/fixtures/english/en.yml').read_bytes()
    result=run(request,snapshot_for({'en':raw})).to_dict()
    assert {r['key'] for r in result['required_keys']}=={definition['caption']['key'],definition['caption']['template_key']}
    assert result['technical_eligible'] and len(json.loads(result['legacy_trace_json']))==2


@pytest.mark.parametrize('mutation',['output-name','output-id','foreign-contract','foreign-variant','rules-pin'])
def test_foreign_output_contract_or_variant_is_blocked(mutation):
    request=request_for(real_resolution(),real_package())
    outputs=json.loads(request.outputs_json)
    if mutation=='output-name':outputs[0]['local_path']='defaults-en/playlist/Unexpected.jpg'
    elif mutation=='output-id':outputs[0]['id']='foreign.output'
    elif mutation=='foreign-contract':request=replace(request,contract_sha256='f'*64)
    elif mutation=='foreign-variant':request=replace(request,variant='unapproved')
    else:request=replace(request,rules_sha256='f'*64)
    request=replace(request,outputs_json=canonical(outputs))
    with pytest.raises(BulkError):run(request)


def test_upstream_commit_advance_is_explicit_observation_with_scoped_content_impact(tmp_path):
    from create_defaults.bulk.languages import LanguageSnapshot
    request=synthetic_request(tmp_path)
    a=snapshot_for()
    metadata=a.snapshot.data
    provenance=dict(metadata['provenance'],commit='c'*40,tree='d'*40)
    b=replace(a,snapshot=LanguageSnapshot.create(metadata['languages'],provenance=provenance))
    before,after=run(request,a),run(request,b)
    assert before.sha256!=after.sha256  # New explicit source observation.
    assert before.to_dict()['dependency_sha256']==after.to_dict()['dependency_sha256']
    policy,_,selection,context=selected(request,a)
    with pytest.raises(BulkError):evaluate(request,policy,'en',b,selection,context=context)


def test_changed_invalid_actual_bytes_are_still_material(tmp_path):
    request=synthetic_request(tmp_path)
    a=snapshot_for()
    b=replace(a,resources=tuple((p,b'forged: one' if p=='defaults/en.yml' else raw) for p,raw in a.resources))
    c=replace(a,resources=tuple((p,b'forged: two' if p=='defaults/en.yml' else raw) for p,raw in a.resources))
    assert run(request,b).to_dict()['dependency_sha256']!=run(request,c).to_dict()['dependency_sha256']


def test_complete_required_key_coverage_includes_missing_english_for_valid_french(tmp_path):
    request=synthetic_request(tmp_path,language='fr')
    result=run(request,snapshot_for({'en':b'key_names: {}','fr':b'key_names: {TIMELINE_ORDER: Valide}'}),'fr').to_dict()
    assert len(result['results'])==2
    assert {r['language']:r['status'] for r in result['results']}=={'en':'missing','fr':'available'}
    assert not result['technical_eligible']


def test_m1_source_schema_does_not_fabricate_resource_for_fully_unavailable_selection(tmp_path):
    request=synthetic_request(tmp_path)
    result=run(request,snapshot_for({'fr':b'key_names: {TIMELINE_ORDER: Valide}'})).to_dict()
    assert result['translation_selection'] is None and result['results'][0]['status']=='resource_unavailable'
    assert result['currentness']=='unverifiable' and not result['technical_eligible']


def test_cold_import_never_reads_schema_writes_or_imports_activation():
    code=r'''
import sys
sys.dont_write_bytecode=True
def audit(event,args):
    if event in {'os.mkdir','os.remove','os.rename','sqlite3.connect','socket.connect','socket.bind','subprocess.Popen','os.system'}:
        raise AssertionError('side effect: '+event)
    if event=='open':
        path,mode,flags=args
        if isinstance(mode,str) and any(c in mode for c in 'wax+'):
            raise AssertionError('write')
        if str(path).endswith('.schema.json'):
            raise AssertionError('import-time schema read')
sys.addaudithook(audit)
import create_defaults.bulk.contracts.language_policy
inherited=set(sys.modules)
import create_defaults.bulk.contracts.translation_preflight
assert not any(k.startswith('create_defaults.bulk.contracts.activation') for k in sys.modules)
# Package E's existing parent package imports worker definitions through its
# registry; M2 must add no worker/production entry-point import or invocation.
assert 'create_defaults.bulk.workers' not in set(sys.modules)-inherited
print('isolated-m2-import-ok')
'''
    result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='isolated-m2-import-ok'


def test_actual_evaluation_has_no_writes_network_clock_workers_or_pixel_processing(monkeypatch):
    request=request_for(real_resolution(),real_package())
    policy,snapshot,selection,context=selected(request)
    expected=evaluate(request,policy,'en',snapshot,selection,context=context)
    import time,socket,sqlite3
    import requests
    from PIL import Image
    from create_defaults.bulk import workers,state
    from pathlib import Path
    def prohibited(*a,**k):raise AssertionError('M2 invoked an operational side effect')
    with monkeypatch.context() as guard:
        for obj,name in [(time,'time'),(time,'monotonic'),(time,'perf_counter'),(socket,'socket'),(sqlite3,'connect'),
                         (requests.Session,'request'),(Image,'open'),(Image,'new'),(Path,'write_bytes'),(Path,'write_text'),
                         (Path,'mkdir'),(state.Store,'__init__'),(workers.PersistentWorkers,'__init__')]:
            guard.setattr(obj,name,prohibited)
        assert evaluate(request,policy,'en',snapshot,selection,context=context).encoded==expected.encoded


def test_cross_platform_full_canonical_evidence_fixture(tmp_path):
    request=synthetic_request(tmp_path,language='fr',caption={'case':'exact'})
    report=run(request,snapshot_for({'en':b'key_names: {TIMELINE_ORDER: Timeline Order}',
        'fr':'key_names: {TIMELINE_ORDER: "Été — Ordre chronologique, déjà vu!"}'.encode()}),'fr')
    fixture=ROOT/'create_defaults/phase3/tests/translation-preflight-v1.json'
    expected=json.loads(fixture.read_text(encoding='utf8'))
    assert report.to_dict()==expected['evidence']
    assert report.sha256==expected['sha256']==fingerprint(expected['evidence'])


def test_existing_verified_package_d_snapshot_integrity_is_not_currentness():
    from create_defaults.bulk.languages import LanguageSnapshot
    from create_defaults.bulk.contracts.translation_preflight import SnapshotInput
    snapshot=LanguageSnapshot.load(ROOT/'create_defaults/bulk/evidence/package-d/translation-snapshot.json')
    repo=dict(host='github.com',repository_id=788129726,owner_id=166754869,name='Kometa-Team/Translations')
    # Reconstruct the selected historical Git LF blob from the checked-in text
    # fixture; its exact SHA-256 and Git blob must match the original snapshot.
    raw=(ROOT/'create_defaults/fixtures/english/en.yml').read_bytes().replace(b'\r\n',b'\n')
    selected_snapshot=SnapshotInput(snapshot,canonical(repo),(('defaults/en.yml',raw),))
    request=request_for(real_resolution(),real_package())
    policy,snapshot_input,selection,_=selected(request,selected_snapshot)
    report=evaluate(request,policy,'en',snapshot_input,selection).to_dict()
    assert report['technical_eligible'] and all(r['status']=='available' for r in report['results'])
    assert report['source']['commit']=='a7bddf45d0fb2cc37c794af05d5fb807880c9a80'
    assert report['source']['repository']==repo
    assert report['source']['resources'][0]['blob_sha1']=='31a4eb296d6c8d48f27075ba1e5ae52f84806dfb'
    assert report['currentness']=='unverifiable' and not report['translation_eligible']


def test_original_m1_additive_ids_and_frozen_vectors_are_preserved():
    old=json.loads(subprocess.check_output(['git','show','b8d0c1c5ba6bdff7c3e4045d2add505af0417348:ci/phase3-test-ids.json'],cwd=ROOT))
    current=json.loads((ROOT/'ci/phase3-test-ids.json').read_text())
    assert len(old)==263 and set(old)<=set(current)
    for path in ['create_defaults/phase3/tests/golden-v1.json',
                 'create_defaults/bulk/contracts/language_policy/schemas/foundations-v1.schema.json',
                 '.github/workflows/default-poster-validation.yml',
                 'create_defaults/bulk/contracts/activation/data/production-pins-v1.json']:
        baseline=subprocess.check_output(['git','show','b8d0c1c5ba6bdff7c3e4045d2add505af0417348:'+path],cwd=ROOT)
        assert baseline.replace(b'\r\n',b'\n')==(ROOT/path).read_bytes().replace(b'\r\n',b'\n')
