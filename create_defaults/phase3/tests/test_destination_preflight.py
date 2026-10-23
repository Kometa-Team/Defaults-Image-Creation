"""Destination routing, authorization and scoped replay adversarial controls."""

from dataclasses import replace
import json

import pytest

from create_defaults.bulk.common import BulkError,canonical,fingerprint
from create_defaults.bulk.contracts.language_policy import DestinationEvidence,DestinationPolicy,reference
from create_defaults.bulk.contracts.destination_preflight import evaluate,revalidate,read_attestation,DestinationAttestation
from create_defaults.phase3.tests.destination_samples import (
    poster,scenario,OFFICIAL,USER,SyntheticDestinationAuthority,overlay_pair,
)


def changed_evidence(s,data):
    evidence=DestinationEvidence.from_dict(data)
    return s|dict(evidence=evidence,expected_evidence_sha256=evidence.sha256)


@pytest.mark.parametrize('language,official,route',[('en',True,'official_english'),('en',False,'user_english'),('fr',False,'user_non_english'),('pt-br',False,'user_non_english'),('nb_NO',False,'user_non_english')])
def test_allowed_routes_are_synthetic_only_never_publication(tmp_path,language,official,route):
    item,lp=poster(tmp_path,language=language,filename='Élan.jpg')
    s=scenario((item,),lp,official=official)
    value=evaluate(**s).to_dict()
    assert value['policy_route']==route and value['simulation_eligible'] and value['destination_checks_passed']
    assert value['complete'] and value['authority_status']=='synthetic-only'
    assert value['outputs'][0]['target_path']=='playlist/Élan.jpg'
    assert all(value[k] is False for k in ['technical_eligible','publication_authorized','production_enforcement','ready','active'])


def test_non_english_official_rejected_by_both_foundation_and_engine(tmp_path):
    item,lp=poster(tmp_path,language='fr')
    with pytest.raises(BulkError):scenario((item,),lp,official=True)
    s=scenario((item,),lp)
    value=s['evidence'].to_dict();value['target']['repository']=OFFICIAL
    from create_defaults.bulk.contracts.destination_preflight import DestinationInventory
    inv=s['inventory'].to_dict();inv['repository']=OFFICIAL;inv=DestinationInventory.from_dict(inv)
    value['target']['inventory_sha256']=inv.sha256
    result=evaluate(**(changed_evidence(s,value)|dict(inventory=inv,expected_inventory_sha256=inv.sha256))).to_dict()
    assert 'official_non_english_prohibited' in result['blockers'] and result['policy_route']=='denied'
    assert not result['simulation_eligible']


@pytest.mark.parametrize('alias',['kometa-team/default-images','Renamed/FormerOfficial','Fixture/CompletelyDifferentName'])
def test_official_ids_not_names_determine_routing(tmp_path,alias):
    item,lp=poster(tmp_path)
    s=scenario((item,),lp,official=True)
    policy=s['policy'].to_dict();policy['official_repository']['name']=alias
    policy['mappings'][0]['repository']['name']=alias
    policy=DestinationPolicy.from_dict(policy)
    value=s['evidence'].to_dict();value['destination_policy']=reference(policy)
    evidence=DestinationEvidence.from_dict(value)
    # Independently selected fixture context approves the same actual IDs under
    # a changed policy label; target and observed repository names may differ.
    context=replace(s['context'],evidence_sha256=evidence.sha256,destination_policy_sha256=policy.sha256)
    facts=replace(s['verifier'].facts,context=context)
    value=evaluate(**(s|dict(policy=policy,expected_policy_sha256=policy.sha256,evidence=evidence,
        expected_evidence_sha256=evidence.sha256,context=context,verifier=SyntheticDestinationAuthority(facts)))).to_dict()
    assert value['policy_route']=='official_english' and value['simulation_eligible']


@pytest.mark.parametrize('name',['Fixture/Official','Kometa-Team/Default-Images'])
def test_official_looking_name_cannot_establish_official_identity(tmp_path,name):
    item,lp=poster(tmp_path)
    if name==OFFICIAL['name']:
        with pytest.raises(BulkError):scenario((item,),lp,repo=USER|dict(name=name))
        return
    s=scenario((item,),lp,repo=USER|dict(name=name))
    value=evaluate(**s).to_dict()
    assert value['policy_route']=='user_english' and value['simulation_eligible']


@pytest.mark.parametrize('field',['owner_id','repository_id','principal','issuer','assertion_sha256','verification_context_sha256','synthetic'])
def test_forged_claims_cannot_be_self_approved(tmp_path,field):
    item,lp=poster(tmp_path);s=scenario((item,),lp)
    value=s['evidence'].to_dict()
    if field in ['owner_id','repository_id']:value['target']['repository'][field]+=1
    elif field=='synthetic':value['authorization'][field]=False
    elif field in ['assertion_sha256','verification_context_sha256']:value['authorization'][field]='f'*64
    else:value['authorization'][field]='self-declared'
    try:result=evaluate(**changed_evidence(s,value)).to_dict()
    except BulkError:return
    assert not result['simulation_eligible'] and not result['technical_eligible']


@pytest.mark.parametrize('mode',['default','no-context','untrusted-dict','m1-synthetic-only-no-facts'])
def test_missing_trusted_authority_fails_closed(tmp_path,mode):
    from create_defaults.bulk.contracts.language_policy.simulation import SyntheticAuthority
    item,lp=poster(tmp_path);s=scenario((item,),lp)
    if mode=='default':s.update(verifier=None)
    elif mode=='no-context':s.update(context=None)
    elif mode=='untrusted-dict':
        with pytest.raises(BulkError):evaluate(**(s|dict(context=s['context'].__dict__)))
        return
    else:s.update(verifier=SyntheticAuthority())
    value=evaluate(**s).to_dict()
    assert not value['technical_eligible'] and not value['simulation_eligible'] and not value['complete']
    assert value['repository_identity_status']=='unverifiable'


@pytest.mark.parametrize('mutation',['revoked','expired','unknown-revocation','expiry-boundary','missing-read','missing-write','missing-pr','foreign-principal-id','organization','foreign-official','target-scope','inventory-scope','cohort-scope'])
def test_grants_revocation_expiry_permissions_and_independent_scope(tmp_path,mutation):
    item,lp=poster(tmp_path);s=scenario((item,),lp)
    if mutation in ['revoked','expired','unknown-revocation']:
        value=s['evidence'].to_dict()
        if mutation=='unknown-revocation':value['authorization']['revocation']=dict(status='unknown',checked_at=None,revision_sha256=None)
        else:value['authorization']['status']=mutation
        s=changed_evidence(s,value)
    elif mutation=='expiry-boundary':s.update(context=replace(s['context'],as_of='2030-01-02T00:00:00Z'))
    else:
        facts=s['verifier'].facts
        changes={
            'missing-read':dict(permissions=('contents:write','pull_requests:write')),
            'missing-write':dict(permissions=('contents:read','pull_requests:write')),
            'missing-pr':dict(permissions=('contents:read','contents:write')),
            'foreign-principal-id':dict(principal_id=999), 'organization':dict(owner_kind='organization'),
            'foreign-official':dict(official_owner_id=999), 'target-scope':dict(target_sha256='f'*64),
            'inventory-scope':dict(inventory_sha256='f'*64),'cohort-scope':dict(cohort_sha256='f'*64)}
        s.update(verifier=SyntheticDestinationAuthority(replace(facts,**changes[mutation])))
    value=evaluate(**s).to_dict()
    assert not value['simulation_eligible'] and not value['technical_eligible']


@pytest.mark.parametrize('field',['branch','root','paths','language'])
def test_target_scope_mismatch_cannot_change_request(tmp_path,field):
    item,lp=poster(tmp_path);s=scenario((item,),lp)
    value=s['evidence'].to_dict()
    value['target'][field]={'branch':'Other','root':'new/root','paths':['playlist/Substituted.jpg'],'language':'fr'}[field]
    try:result=evaluate(**changed_evidence(s,value)).to_dict()
    except BulkError:return
    assert not result['simulation_eligible']


def test_missing_mapping_never_falls_back_to_official(tmp_path):
    item,lp=poster(tmp_path,language='fr');s=scenario((item,),lp)
    value=s['policy'].to_dict();value['mappings']=[]
    policy=DestinationPolicy.from_dict(value)
    evidence=s['evidence'].to_dict();evidence['destination_policy']=reference(policy)
    s=changed_evidence(s,evidence)|dict(policy=policy,expected_policy_sha256=policy.sha256)
    result=evaluate(**s).to_dict()
    assert 'destination_mapping_missing' in result['blockers'] and result['policy_route']=='user_non_english'
    assert not result['simulation_eligible']


@pytest.mark.parametrize('root,other_root,other_branch,reason',[
    (None,'french','Main','overlapping_language_roots'),('posters','posters/fr','Main','overlapping_language_roots'),
    ('Posters/Été','posters/E\u0301te\u0301','Main','overlapping_language_roots'),
    ('en','fr','main','ambiguous_branch_mapping')])
def test_ambiguous_or_overlapping_language_roots(tmp_path,root,other_root,other_branch,reason):
    item,lp=poster(tmp_path)
    other=dict(language='fr',repository=USER,branch=other_branch,root=other_root,paths=['playlist/Other.jpg'])
    result=evaluate(**scenario((item,),lp,root=root,extra_mappings=[other])).to_dict()
    assert reason in result['blockers'] and not result['simulation_eligible']


def test_disjoint_explicit_roots_are_preserved(tmp_path):
    item,lp=poster(tmp_path)
    other=dict(language='fr',repository=USER,branch='Main',root='approved/fr',paths=['playlist/Other.jpg'])
    result=evaluate(**scenario((item,),lp,root='approved/en',extra_mappings=[other])).to_dict()
    assert result['simulation_eligible'] and result['outputs'][0]['target_path'].startswith('approved/en/playlist/')


def test_private_output_has_no_destination_or_fake_evidence(tmp_path):
    item,lp=poster(tmp_path,public=False)
    s=scenario((item,),lp)
    result=evaluate(**s).to_dict()
    assert result['complete'] and result['policy_route']=='private_only' and result['target'] is None
    assert result['destination_evidence'] is None and result['inventory_status']=='not_applicable'
    assert result['outputs'][0]['status']=='private' and result['outputs'][0]['target_path'] is None
    assert not result['technical_eligible'] and not result['simulation_eligible']
    with pytest.raises(BulkError):evaluate(**(s|dict(expected_evidence_sha256='f'*64)))


def test_complete_overlay_standard_bigger_membership_and_collision():
    items,lp=overlay_pair()
    s=scenario(items,lp)
    result=evaluate(**s).to_dict()
    assert result['simulation_eligible'] and len(result['outputs'])==2
    assert {r['target_path'].split('/')[-2] for r in result['outputs']}=={'standard','bigger'}
    incomplete=evaluate(**scenario(items[:1],lp)).to_dict()
    assert incomplete['missing_companions'] and not incomplete['complete']
    existing=items[0].subject.to_dict()['outputs'][0]['public_path']
    collided=evaluate(**scenario(items,lp,entries={existing:'100644'})).to_dict()
    assert sum(r['status']=='blocked' for r in collided['outputs'])==1 and not collided['simulation_eligible']
    with pytest.raises(BulkError):evaluate(**scenario((items[0],items[0]),lp))


@pytest.mark.parametrize('mutation',['missing-m2','modified-m2','foreign-subject','foreign-contract','foreign-language','foreign-policy'])
def test_m2_references_cannot_be_substituted(tmp_path,mutation):
    item,lp=poster(tmp_path);s=scenario((item,),lp)
    if mutation=='missing-m2':item=replace(item,translation=None)
    elif mutation=='modified-m2':
        from create_defaults.bulk.contracts.translation_preflight import TranslationPreflight
        value=item.translation.to_dict();value['blockers']=[]
        item=replace(item,translation=TranslationPreflight.from_dict(value))
    elif mutation=='foreign-subject':item=replace(item,subject_sha256='f'*64)
    elif mutation=='foreign-contract':item=replace(item,contract_sha256='f'*64)
    elif mutation=='foreign-language':
        from create_defaults.bulk.contracts.language_policy import ValidationSubject
        value=item.subject.to_dict();value['language']='fr'
        subject=ValidationSubject.from_dict(value);item=replace(item,subject=subject,subject_sha256=subject.sha256)
    else:
        value=lp.to_dict();value['version']='2.0.0'
        from create_defaults.bulk.contracts.language_policy import LanguagePolicy
        s['language_policy']=LanguagePolicy.from_dict(value)
    with pytest.raises(BulkError):evaluate(**(s|dict(items=(item,))))


@pytest.mark.parametrize('bad_translation,english_only',[(True,False),(False,True)])
def test_destination_never_clears_translation_or_category_blockers(tmp_path,bad_translation,english_only):
    from create_defaults.phase3.tests.translation_samples import snapshot_for
    item,lp=poster(tmp_path,language='fr',contract_languages=['en'] if english_only else None,
        snapshot=snapshot_for({'en':b'key_names: {TIMELINE_ORDER: Timeline}','fr':b'key_names: {}'}) if bad_translation else None)
    result=evaluate(**scenario((item,),lp)).to_dict()
    assert not result['simulation_eligible'] and 'translation_technical_blocked' in result['blockers']
    if english_only:assert 'contract_language_not_permitted' in result['blockers']


@pytest.mark.parametrize('mutation',['path','drop-output','incomplete','activate','publication','unknown','kind','schema','context','simulation','pin'])
def test_attestation_forgery_partial_evidence_and_replay(tmp_path,mutation):
    item,lp=poster(tmp_path);s=scenario((item,),lp);report=evaluate(**s)
    if mutation=='pin':
        with pytest.raises(BulkError):read_attestation(report.encoded,expected_sha256='f'*64)
        return
    value=report.to_dict()
    if mutation=='path':value['outputs'][0]['target_path']='unapproved/path.jpg'
    elif mutation=='drop-output':value.update(outputs=[],proposed_outputs=0,evaluated_outputs=0)
    elif mutation=='incomplete':value['complete']=False
    elif mutation=='activate':value['ready']=True
    elif mutation=='publication':value['publication_authorized']=True
    elif mutation=='unknown':value['unknown']='anything'
    elif mutation=='kind':value['kind']='phase3-attestation'
    elif mutation=='schema':value['schema_version']=2
    elif mutation=='context':value['authority_context_sha256']='f'*64
    else:value['simulation_eligible']=False
    with pytest.raises(BulkError):
        forged=DestinationAttestation.from_dict(value)
        revalidate(forged,expected_sha256=forged.sha256,**s)


def test_exact_replay_and_foreign_context_rejection(tmp_path):
    item,lp=poster(tmp_path);s=scenario((item,),lp);report=evaluate(**s)
    assert revalidate(report,expected_sha256=report.sha256,**s)==report
    changed=s|dict(context=replace(s['context'],as_of='2030-01-01T13:00:00Z'))
    with pytest.raises(BulkError):revalidate(report,expected_sha256=report.sha256,**changed)
