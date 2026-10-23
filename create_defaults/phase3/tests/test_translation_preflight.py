"""M2 positives and adversarial replay over the real expanded-definition adapter."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from create_defaults.bulk.common import BulkError, canonical, fingerprint
from create_defaults.bulk.contracts.language_policy import TranslationSelection, LanguagePolicy
from create_defaults.bulk.contracts.translation_preflight import evaluate, revalidate, read_report, TranslationPreflight
from create_defaults.bulk.contracts.translation_preflight.sources import parse, lookup
from create_defaults.phase3.tests.translation_samples import (
    KEY, ROOT, real_package, real_resolution, request_for, synthetic_request,
    policy_for, snapshot_for, selected, SyntheticCurrent,
)


def run(request, snapshot=None, requested='en', **kw):
    policy,snapshot,selection,context=selected(request,snapshot,requested,**kw)
    return evaluate(request,policy,requested,snapshot,selection,context=context,verifier=SyntheticCurrent())


def test_existing_english_snapshot_real_m5_expansion_and_exact_contract():
    request=request_for(real_resolution(),real_package())
    raw=(ROOT/'create_defaults/fixtures/english/en.yml').read_bytes()
    result=run(request,snapshot_for({'en':raw})).to_dict()
    assert result['technical_eligible'] and result['complete']
    assert result['resolved_caption']=='TIMELINE ORDER'
    assert result['required_keys']==[{'key':KEY,'roles':['caption']}]
    assert result['subject']['contract']['sha256']==real_package().contract.sha256
    assert result['currentness']=='synthetic-current'
    assert not result['translation_eligible']
    assert result['results'][0]['value']==lookup(parse(raw),KEY)[1]
    assert all(result[k] is False for k in ['publication_authorized','production_enforcement','ready','active'])


@pytest.mark.parametrize('language,value',[('en','Timeline Order'),('fr','Ordre chronologique'),('pt-br','Ordem cronológica'),('nb_NO','Kronologisk rekkefølge')])
def test_synthetic_versioned_multilingual_contract(tmp_path,language,value):
    request=synthetic_request(tmp_path,language=language)
    resources={'en':b'key_names: {TIMELINE_ORDER: Timeline Order}',language:('key_names: {TIMELINE_ORDER: '+value+'}').encode()}
    report=run(request,snapshot_for(resources),language).to_dict()
    assert report['technical_eligible'] and report['evaluated_row_count']==len({'en',language})
    assert next(r['value'] for r in report['results'] if r['language']==language)==value


@pytest.mark.parametrize('raw,status',[
    (b'key_names: {}','missing'),(b'key_names: {TIMELINE_ORDER: null}','invalid_translation'),
    (b'key_names: {TIMELINE_ORDER: 123}','invalid_translation'),(b'key_names: {TIMELINE_ORDER: []}','invalid_translation'),
    (b'key_names: {TIMELINE_ORDER: {nested: value}}','invalid_translation'),
    (b'key_names: {TIMELINE_ORDER: ""}','invalid_translation'),(b'key_names: {TIMELINE_ORDER: "   "}','invalid_translation'),
    (b'key_names: {TIMELINE_ORDER: "TRANSLATION NOT FOUND"}','unresolved_placeholder'),
    (b'key_names: {TIMELINE_ORDER: "prefix TRANSLATION NOT FOUND suffix"}','unresolved_placeholder'),
    (b'key_names: {TIMELINE_ORDER: "<<unresolved>>"}','unresolved_placeholder'),
    (b'key_names: [','invalid_source'),(b'\xff\xfe','invalid_source'),(b'[]','invalid_source'),
    (b'key_names: {TIMELINE_ORDER: Good, TIMELINE_ORDER: Evil}','invalid_source'),
    (b'key_names: {TIMELINE_ORDER: Good, timeline_order: Evil}','invalid_source'),
    (b'key_names: &anchor {TIMELINE_ORDER: Good}\nother: *anchor','invalid_source'),
    (b'!!python/object/apply:os.system [evil]','invalid_source'),
    (b'key_names: {TIMELINE_ORDER: !!binary SGVsbG8=}','invalid_source'),
])
@pytest.mark.parametrize('language',['en','fr'])
def test_invalid_required_value_is_scoped_and_blocks(tmp_path,raw,status,language):
    request=synthetic_request(tmp_path,language=language)
    resources={'en':b'key_names: {TIMELINE_ORDER: Timeline Order}',language:raw}
    report=run(request,snapshot_for(resources),language).to_dict()
    assert not report['technical_eligible'] and report['complete']
    assert next(r['status'] for r in report['results'] if r['language']==language)==status


@pytest.mark.parametrize('missing',['en','fr'])
def test_missing_resource_is_not_a_missing_key(tmp_path,missing):
    request=synthetic_request(tmp_path,language='fr')
    snapshot=snapshot_for({code:b'key_names: {TIMELINE_ORDER: Value}' for code in ['en','fr'] if code!=missing})
    result=run(request,snapshot,'fr').to_dict()
    assert next(r['status'] for r in result['results'] if r['language']==missing)=='resource_unavailable'
    assert not result['technical_eligible']


def test_missing_cached_bytes_and_substituted_blob_are_distinct(tmp_path):
    request=synthetic_request(tmp_path,language='fr')
    snapshot=snapshot_for()
    with pytest.raises(BulkError):replace(snapshot,resources=list(snapshot.resources))
    with pytest.raises(BulkError):replace(snapshot,resources=(('defaults/fr.yml',bytearray(b'mutable')),))
    for raw,status in [(None,'resource_unavailable'),(b'key_names: {TIMELINE_ORDER: Forged}','unverifiable_provenance')]:
        altered=replace(snapshot,resources=tuple((p,raw if p=='defaults/fr.yml' else b) for p,b in snapshot.resources))
        report=run(request,altered,'fr').to_dict()
        assert next(r['status'] for r in report['results'] if r['language']=='fr')==status


def test_caption_template_and_suffix_use_existing_resolver(tmp_path):
    request=synthetic_request(tmp_path,language='fr',caption={'template_key':'templates.ORDER','suffix':'!','case':'exact'})
    snapshot=snapshot_for({'en':b'key_names: {TIMELINE_ORDER: Timeline}\ntemplates: {ORDER: "<<value>> order"}',
                          'fr':'key_names: {TIMELINE_ORDER: Chronologie}\ntemplates: {ORDER: "Ordre <<value>>"}'.encode()})
    report=run(request,snapshot,'fr').to_dict()
    assert report['required_keys']==[dict(key=KEY,roles=['caption']),dict(key='templates.ORDER',roles=['template'])]
    assert len(report['results'])==4 and report['technical_eligible']
    assert report['resolved_caption']=='Ordre Chronologie!'
    assert next(r['value'] for r in report['results'] if r['key']=='templates.ORDER' and r['language']=='fr')=='Ordre <<value>>'


@pytest.mark.parametrize('language',['en','fr'])
def test_missing_template_cannot_hide_behind_available_caption(tmp_path,language):
    request=synthetic_request(tmp_path,language=language,caption={'template_key':'templates.ORDER'})
    report=run(request,snapshot_for(),language).to_dict()
    assert not report['technical_eligible']
    assert all(r['status']=='missing' for r in report['results'] if r['key']=='templates.ORDER')


def test_case_insensitive_keys_keep_exact_actual_source_spelling(tmp_path):
    request=synthetic_request(tmp_path)
    report=run(request,snapshot_for({'en':b'KEY_NAMES: {timeline_order: "MiXeD"}'})).to_dict()
    row=report['results'][0]
    assert row['actual_key']=='KEY_NAMES.timeline_order' and row['value']=='MiXeD'
    assert report['resolved_caption']=='MIXED'


def test_no_caption_has_empty_key_set_without_dummy_m1_selection(tmp_path):
    request=synthetic_request(tmp_path,mode='none')
    report=run(request).to_dict()
    assert report['required_keys']==report['results']==[]
    assert report['translation_selection'] is None and report['source']['resources']==[]
    assert report['currentness']=='not_applicable' and report['key_status']=='not_applicable'
    assert report['technical_eligible'] and report['translation_eligible']
    assert 'destination' in report['independent_checks'] and not report['ready']


def test_empty_keys_do_not_waive_contract_language_restriction(tmp_path):
    request=synthetic_request(tmp_path,language='fr',mode='none',contract_languages=['en'])
    report=run(request,requested='fr').to_dict()
    assert not report['technical_eligible'] and report['required_keys']==[]
    assert 'contract_language_not_permitted' in report['blockers']


@pytest.mark.parametrize('canonical_code,alias',[('pt-br','pt_BR'),('nb_NO','nb-NO')])
def test_only_explicit_aliases_are_resolved(tmp_path,canonical_code,alias):
    request=synthetic_request(tmp_path,language=canonical_code)
    snapshot=snapshot_for({'en':b'key_names: {TIMELINE_ORDER: Timeline}',canonical_code:b'key_names: {TIMELINE_ORDER: Translated}'})
    report=run(request,snapshot,alias).to_dict()
    assert report['requested_language']==alias and report['language']==canonical_code
    for invalid in ['PT-BR','pt_br','nb_no','nb-no']:
        with pytest.raises(BulkError):run(request,snapshot,invalid)


def test_resource_discovery_and_policy_coverage_cannot_widen_real_playlist(tmp_path):
    request=synthetic_request(tmp_path,language='fr',contract_languages=['en'])
    report=run(request,requested='fr').to_dict()
    assert all(r['status']=='available' for r in report['results'])
    assert 'contract_language_not_permitted' in report['blockers']
    actual=request_for(real_resolution(),real_package(),'fr')
    real=run(actual,requested='fr').to_dict()
    assert not real['technical_eligible'] and not real['translation_eligible']
    assert {'contract_language_not_permitted','definition_not_applicable'}<=set(real['blockers'])


def test_language_registration_is_not_contract_coverage(tmp_path):
    request=synthetic_request(tmp_path,language='fr')
    policy,snapshot,selection,context=selected(request,requested='fr')
    value=policy.to_dict();value['coverage']=[]
    policy=LanguagePolicy.from_dict(value)
    from create_defaults.bulk.contracts.translation_preflight.engine import prepare
    from create_defaults.bulk.contracts.translation_preflight.sources import selection_value
    vs,*_,keys=prepare(request,policy,'fr')
    selection=selection_value(policy,vs,'fr',snapshot,keys,verification=selection.to_dict()['verification'])
    result=evaluate(request,policy,'fr',snapshot,selection).to_dict()
    assert 'contract_language_not_permitted' in result['blockers']


def test_reviewed_legacy_english_fallback_is_recorded_but_cannot_authorize(tmp_path):
    fallback=dict(id='fixture.fallback',reviewer='historical-reviewer',reason='Historical test fixture',policy_version='1.0.0',
                  text=None,language='en',key=KEY)
    request=synthetic_request(tmp_path,language='fr',caption={'fallback':fallback})
    report=run(request,snapshot_for({'en':b'key_names: {TIMELINE_ORDER: Timeline Order}','fr':b'key_names: {}'}),'fr').to_dict()
    assert report['resolved_caption']=='TIMELINE ORDER'
    assert json.loads(report['legacy_trace_json'])[0]['fallback']==fallback
    assert json.loads(report['fallback_json'])==fallback
    assert not report['technical_eligible'] and not report['translation_eligible']


@pytest.mark.parametrize('value',['Été — Noël, déjà vu!','e\u0301 é / 漢字 / العربية / 🦋','Longue traduction '+('avec accents é et ponctuation, '*100)])
def test_raw_unicode_and_length_differences_are_preserved(tmp_path,value):
    import yaml
    request=synthetic_request(tmp_path,language='fr',caption={'case':'exact'})
    snapshot=snapshot_for({'en':b'key_names: {TIMELINE_ORDER: Short}','fr':yaml.safe_dump({'key_names':{'TIMELINE_ORDER':value}},allow_unicode=True).encode()})
    report=run(request,snapshot,'fr').to_dict()
    assert report['technical_eligible'] and report['resolved_caption']==value
    assert next(r['value'] for r in report['results'] if r['language']=='fr')==value
    assert 'font-glyphs' in report['independent_checks']


@pytest.mark.parametrize('raw',[b'key_names: {TIMELINE_ORDER: Changed}',b'# Only provenance changed\nkey_names: {TIMELINE_ORDER: Timeline Order}'])
def test_relevant_resource_or_value_changes_invalidate_even_identical_visible_text(tmp_path,raw):
    request=synthetic_request(tmp_path)
    a=run(request,snapshot_for({'en':b'key_names: {TIMELINE_ORDER: Timeline Order}'}))
    b=run(request,snapshot_for({'en':raw}))
    assert a.sha256!=b.sha256
    assert a.to_dict()['dependency_sha256']!=b.to_dict()['dependency_sha256']


def test_unrelated_languages_and_unused_resource_bytes_do_not_invalidate(tmp_path):
    request=synthetic_request(tmp_path)
    a=snapshot_for({'en':b'key_names: {TIMELINE_ORDER: Timeline Order}','fr':b'key_names: {TIMELINE_ORDER: Avant}'})
    b=snapshot_for({'en':b'key_names: {TIMELINE_ORDER: Timeline Order}','fr':'key_names: {TIMELINE_ORDER: Après}'.encode()})
    assert a.snapshot.fingerprint!=b.snapshot.fingerprint
    assert run(request,a).encoded==run(request,b).encoded
    changed=replace(b,resources=(*b.resources,('unused/unselected.yml',b'invalid: [')))
    assert run(request,a).encoded==run(request,changed).encoded


@pytest.mark.parametrize('status',['unavailable','unverifiable','stale','verified'])
def test_snapshot_integrity_never_automatically_proves_currentness(tmp_path,status):
    request=synthetic_request(tmp_path)
    policy,snapshot,selection,context=selected(request,status=status)
    report=evaluate(request,policy,'en',snapshot,selection,context=context).to_dict()
    assert report['technical_eligible'] and not report['translation_eligible']
    assert report['currentness'] in {'unavailable','unverifiable','stale'}
    assert all(r['provenance_status']==report['currentness'] for r in report['results'])
    assert any(b.startswith('source_currentness:') for b in report['blockers'])


@pytest.mark.parametrize('field',['selection_sha256','source_sha256','verification_context_sha256','commit','tree','issuer','issuer_version','as_of'])
def test_substituted_explicit_source_context_fails_closed(tmp_path,field):
    request=synthetic_request(tmp_path)
    policy,snapshot,selection,context=selected(request)
    substitute={'commit':'f'*40,'tree':'f'*40,'issuer':'different','issuer_version':'2.0.0','as_of':'2030-01-02T00:00:00Z'}.get(field,'f'*64)
    report=evaluate(request,policy,'en',snapshot,selection,context=replace(context,**{field:substitute}),verifier=SyntheticCurrent()).to_dict()
    assert report['currentness']=='unverifiable' and not report['translation_eligible']


@pytest.mark.parametrize('field',['language_policy','subject','language','requested_language','snapshot_sha256','source','values'])
def test_forged_m1_selection_cannot_be_replayed(tmp_path,field):
    request=synthetic_request(tmp_path)
    policy,snapshot,selection,context=selected(request)
    data=selection.to_dict()
    if field in ['language_policy','subject']:data[field]['sha256']='f'*64
    elif field in ['language','requested_language']:data[field]='fr'
    elif field=='source':
        data[field]['commit']='f'*40
        data['verification']['source_sha256']=fingerprint(data[field])
    elif field=='values':data[field]=[]
    else:data[field]='f'*64
    with pytest.raises(BulkError):evaluate(request,policy,'en',snapshot,TranslationSelection.from_dict(data),context=context)


@pytest.mark.parametrize('mutation',['drop-row','drop-key','wrong-subject','eligibility','complete','unknown','activation','hash'])
def test_modified_or_partial_report_fails_validation_or_replay(tmp_path,mutation):
    request=synthetic_request(tmp_path)
    policy,snapshot,selection,context=selected(request)
    report=evaluate(request,policy,'en',snapshot,selection,context=context)
    data=report.to_dict()
    if mutation=='drop-row':data['results']=[]
    elif mutation=='drop-key':data.update(required_keys=[],results=[],required_row_count=0,evaluated_row_count=0,key_status='not_applicable')
    elif mutation=='wrong-subject':data['subject']['review_context_sha256']='f'*64
    elif mutation=='eligibility':data.update(technical_eligible=True,translation_eligible=True,currentness='verified-current',blockers=[])
    elif mutation=='complete':data['complete']=False
    elif mutation=='unknown':data['unexpected']='unknown'
    elif mutation=='activation':data['ready']=True
    else:
        with pytest.raises(BulkError):read_report(report.encoded,expected_sha256='f'*64)
        return
    with pytest.raises(BulkError):
        forged=TranslationPreflight.from_dict(data)
        revalidate(forged,expected_sha256=forged.sha256,request=request,policy=policy,requested='en',snapshot=snapshot,selection=selection,context=context)


@pytest.mark.parametrize('stop_after',[1,2,3,4,5])
def test_interruption_never_returns_complete_evidence(tmp_path,stop_after):
    request=synthetic_request(tmp_path,language='fr',caption={'template_key':'templates.ORDER'})
    raw=b'key_names: {TIMELINE_ORDER: Timeline}\ntemplates: {ORDER: "<<value>> order"}'
    policy,snapshot,selection,context=selected(request,snapshot_for({'en':raw,'fr':raw}),'fr')
    calls=0
    def interrupted():
        nonlocal calls
        calls+=1
        return calls>=stop_after
    with pytest.raises(BulkError,match='incomplete'):
        evaluate(request,policy,'fr',snapshot,selection,context=context,cancel=interrupted)


def test_exact_revalidation_and_subject_replay_boundary(tmp_path):
    request=synthetic_request(tmp_path)
    policy,snapshot,selection,context=selected(request)
    report=evaluate(request,policy,'en',snapshot,selection,context=context)
    assert revalidate(report,expected_sha256=report.sha256,request=request,policy=policy,requested='en',snapshot=snapshot,selection=selection,context=context)==report
    with pytest.raises(BulkError):
        revalidate(report,expected_sha256=report.sha256,request=replace(request,review_context_sha256='f'*64),policy=policy,
                   requested='en',snapshot=snapshot,selection=selection,context=context)


def test_real_m5_resolution_cannot_be_replaced_with_loose_expanded_json():
    request=request_for(real_resolution(),real_package())
    data=request.resolution.data();data['expanded'][request.identity]['caption']['key']='key_names.FORGED'
    forged=replace(request.resolution,encoded=canonical(data))
    with pytest.raises(BulkError,match='resolution_replay'):run(replace(request,resolution=forged))
    with pytest.raises(BulkError):run(replace(request,resolution=replace(forged,source_pins=())))
    from create_defaults.bulk.contracts.categories.release import Package
    with pytest.raises(BulkError):run(replace(request,package=Package(request.package.contract,None)))


@pytest.mark.parametrize('override',[{'caption':{'mode':'none','key':None,'template_key':None}}, {'caption':{'key':'key_names.FORGED'}}, {'composer':{'font_size':1}}, {'layout':{'kind':'fixed','measurement':None}}])
def test_overrides_cannot_smuggle_protected_changes(tmp_path,override):
    request=synthetic_request(tmp_path,language='fr')
    path=tmp_path/'fixture.yml'
    import yaml
    data=yaml.safe_load(path.read_text(encoding='utf8'))
    data['definitions'][0]['overrides']=[dict(language='fr',changes=override)]
    path.write_text(yaml.safe_dump(data),encoding='utf8')
    from create_defaults.bulk.contracts.expanded.resolution import resolve
    resolution=resolve([path],profiles_path=tmp_path/'profiles.yml')
    report=run(replace(request,resolution=resolution),requested='fr').to_dict()
    assert not report['technical_eligible']
    assert 'effective_definition_outside_contract' in report['blockers']


def test_changed_definition_after_expansion_is_not_silently_refreshed(tmp_path):
    request=synthetic_request(tmp_path)
    path=tmp_path/'fixture.yml';path.write_bytes(path.read_bytes()+b'\n# changed\n')
    with pytest.raises(BulkError,match='changed'):run(request)


def test_report_bound_is_fail_closed_without_diagnostic_truncation(tmp_path):
    request=synthetic_request(tmp_path)
    # It is invalid content, not a shorter fabricated translation. No evidence
    # can falsely claim completeness after the report's explicit string bound.
    report=run(request,snapshot_for({'en':b'key_names: {TIMELINE_ORDER: "'+b'x'*17000+b'"}'})).to_dict()
    assert report['results'][0]['status']=='invalid_translation'
    assert report['results'][0]['value']=='x'*17000
    assert not report['technical_eligible']
    with pytest.raises(BulkError):TranslationPreflight.from_bytes(b' '*(8*1024*1024+1))
