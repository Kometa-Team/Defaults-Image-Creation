"""Local policy/transport simulations; no claim of native hosted enforcement."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from create_defaults.bulk import canary_staging as s,canary_private as private,canary_protection as protection
from create_defaults.bulk.common import BulkError,canonical,fingerprint


def seal(value):
    value={k:v for k,v in value.items() if k!='sha256'};value['sha256']=fingerprint(value);return value


def ready_artifact():
    return seal({'enabled':True,'repository':private.REPOSITORY,'repository_id':1234,'visibility':'private','commit':'8'*40,'git_blob':'7'*40,
        'path':private.ARCHIVE_PATH,'bytes':7256318,'sha256_archive':s.BUNDLE_SHA,
        'retain_until_utc':(datetime.now(timezone.utc)+timedelta(days=120)).isoformat(),'durable_backup_confirmed':True,'deletion_requires_separate_authorization':True})


def ready_setup(environment_sha='4'*64):
    now=datetime.now(timezone.utc)
    return seal({'verified':True,'method':'github_settings_ui_and_hosted_probe','repository':s.SOURCE,'environment':'english-canary-stage',
        'environment_id':101,'environment_snapshot_sha256':environment_sha,'implementation_commit':'1'*40,'checked_by':'badja-dev','checked_by_id':180163201,
        'source_branch_protection_reviewed':True,'admin_bypass_disabled_ui_observed':True,'ui_evidence_retained_privately':True,'ui_evidence_sha256':'a'*64,'hidden_setting_machine_verified':False,
        'checked_at_utc':(now-timedelta(minutes=2)).isoformat(),'expires_at_utc':(now+timedelta(hours=1)).isoformat(),
        'hosted_verification':{'verified':True,'passed_cases':sorted(protection.REQUIRED_HOSTED_CASES),'report_sha256':'b'*64,'run_ids':list(range(301,307)),'outside_dispatch_not_applicable':True}})


class Sink:
    def __init__(self):self.events=[]
    def add(self,kind,payload):self.events.append((kind,payload))


@pytest.mark.parametrize('mutation',['disabled','public','wrong_repo','missing_id','bad_commit','bad_blob','bad_hash','wrong_case','retention','backup','delete'])
def test_private_config_fails_closed(mutation):
    value=ready_artifact()
    key,changed={'disabled':('enabled',False),'public':('visibility','public'),'wrong_repo':('repository',s.TARGET),'missing_id':('repository_id',None),
        'bad_commit':('commit','main'),'bad_blob':('git_blob','latest'),'bad_hash':('sha256_archive','f'*64),'wrong_case':('path','Canary/english-canary-review-bundle.zip'),
        'retention':('retain_until_utc',datetime.now(timezone.utc).isoformat()),'backup':('durable_backup_confirmed',False),'delete':('deletion_requires_separate_authorization',False)}[mutation]
    value[key]=changed
    with pytest.raises(BulkError):private.validate_config(value)


@pytest.mark.parametrize('mutation',['missing','bypass','expired','too_long','wrong_source','wrong_snapshot','wrong_impl','wrong_inspector','wrong_id','no_ui_evidence','claims_machine_proof','no_hosted','missing_case','no_runs'])
def test_supported_setup_receipt_rejects_missing_stale_or_invented_evidence(mutation):
    receipt=ready_setup();auth={'setup_receipt_sha256':receipt['sha256'],'expires_at_utc':(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat()}
    if mutation=='missing':receipt['verified']=False
    elif mutation=='bypass':receipt['admin_bypass_disabled_ui_observed']=False
    elif mutation=='expired':receipt['expires_at_utc']='2000-01-01T00:00:00Z'
    elif mutation=='too_long':receipt['expires_at_utc']=(datetime.now(timezone.utc)+timedelta(days=3)).isoformat()
    elif mutation=='wrong_source':receipt['repository']='outside/source'
    elif mutation=='wrong_snapshot':receipt['environment_snapshot_sha256']='f'*64
    elif mutation=='wrong_impl':receipt['implementation_commit']='f'*40
    elif mutation=='wrong_inspector':receipt['checked_by']='bullmoose20'
    elif mutation=='wrong_id':receipt['checked_by_id']=999
    elif mutation=='no_ui_evidence':receipt['ui_evidence_retained_privately']=False
    elif mutation=='claims_machine_proof':receipt['hidden_setting_machine_verified']=True
    elif mutation=='no_hosted':receipt['hosted_verification']['verified']=False
    elif mutation=='missing_case':receipt['hosted_verification']['passed_cases'].pop()
    elif mutation=='no_runs':receipt['hosted_verification']['run_ids']=[]
    with pytest.raises(BulkError):protection.validate_receipt(receipt,environment_sha='4'*64,implementation='1'*40,auth=auth)


def hosted_get(receipt, *, outside=False, mutation=None):
    ids=receipt['hosted_verification']['run_ids'];names=list(s.MAINTAINERS)
    def get(endpoint):
        if '/collaborators?' in endpoint:
            result=[{'login':n,'id':s.MAINTAINERS[n]} for n in names]
            if mutation=='outside_writer':result.append({'login':'outside-writer','permissions':{'push':True},'role_name':'write'})
            return result
        number=int(endpoint.split('/actions/runs/')[1].split('/')[0]);index=ids.index(number)
        actor=names[index] if index<5 else (('outside-writer' if outside else names[0]))
        approver=actor if index<5 else names[1]
        if endpoint.endswith('/approvals'):
            return [{'state':'approved','comment':'english-canary-approval-check','user':{'login':approver,'id':s.MAINTAINERS[approver]},'environments':[{'id':101,'name':'english-canary-stage'}]}]
        return {'id':number,'repository':{'full_name':s.SOURCE},'head_sha':'f'*40 if mutation=='wrong_sha' else '1'*40,'head_branch':'main',
            'event':'workflow_dispatch','path':'.github/workflows/english-canary-approval-check.yml','conclusion':'failure' if mutation=='failed' else 'success','run_attempt':2 if mutation=='rerun' else 1,
            'actor':{'login':actor,'id':s.MAINTAINERS.get(actor,999)}}
    return get


def test_hosted_evidence_parser_requires_actual_native_self_and_cross_records():
    receipt=ready_setup();protection.verify_hosted_runs(receipt,'1'*40,hosted_get(receipt))
    receipt['hosted_verification']['run_ids'].append(307)
    # Include an outside positive run in addition to five self approvals and cross.
    base=hosted_get(receipt)
    def get(endpoint):
        value=base(endpoint)
        if endpoint.endswith('/307'):value['actor']={'login':'outside-writer','id':999}
        return value
    protection.verify_hosted_runs(receipt,'1'*40,get)


@pytest.mark.parametrize('mutation',['wrong_sha','failed','rerun','outside_writer','missing_self','duplicate'])
def test_hosted_evidence_drift_rejected(mutation):
    receipt=ready_setup()
    if mutation=='missing_self':receipt['hosted_verification']['run_ids'].pop(0)
    if mutation=='duplicate':receipt['hosted_verification']['run_ids'].append(301)
    with pytest.raises(BulkError):protection.verify_hosted_runs(receipt,'1'*40,hosted_get(receipt,mutation=mutation))


class Response:
    def __init__(self,value,status=200):self.value=value;self.status_code=status
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def iter_content(self,size):yield json.dumps(self.value).encode()


def private_responses(config,data,mutation=None):
    repository={'id':1234,'full_name':private.REPOSITORY,'private':True,'visibility':'private','permissions':{'push':False,'admin':False}}
    scope={'total_count':1,'repositories':[deepcopy(repository)]}
    if mutation=='extra_scope':scope['total_count']=2
    if mutation=='write_scope':scope['repositories'][0]['permissions']['push']=True
    if mutation=='public':repository.update(private=False,visibility='public')
    tree={'sha':'9'*40,'truncated':False,'tree':[{'path':private.ARCHIVE_PATH,'type':'blob','mode':'100644','sha':config['git_blob']}]}
    if mutation=='truncated':tree['truncated']=True
    if mutation=='wrong_path':tree['tree'][0]['path']='other.zip'
    if mutation=='link':tree['tree'][0]['mode']='120000'
    blob={'sha':config['git_blob'],'encoding':'base64','size':len(data),'content':base64.b64encode(data if mutation!='bad_bytes' else b'wrong').decode()}
    responses=[scope,repository,{'sha':config['commit'],'tree':{'sha':'9'*40}},tree,blob]
    return responses


@pytest.mark.parametrize('mutation',[None,'extra_scope','write_scope','public','truncated','wrong_path','link','bad_bytes','unavailable','redirect'])
def test_private_adapter_gets_only_pinned_private_objects_without_secret_logging(monkeypatch,mutation):
    data=b'unchanged archive fixture';monkeypatch.setattr(private,'ARCHIVE_BYTES',len(data));monkeypatch.setattr(s,'BUNDLE_SHA',hashlib.sha256(data).hexdigest())
    config=ready_artifact();config.update(bytes=len(data),git_blob=s.git_blob(data));responses=private_responses(config,data,mutation)
    calls=[]
    class Session:
        def __init__(self):self.headers={}
        def get(self,url,**kwargs):
            calls.append((url,kwargs));assert kwargs['allow_redirects'] is False
            return Response(responses.pop(0),404 if mutation=='unavailable' else 302 if mutation=='redirect' else 200)
    monkeypatch.setattr(private.requests,'Session',Session)
    sink=Sink();reader=private.PrivateReader('do-not-log-test-token',config,sink)
    if mutation is None:assert reader.retrieve()==data
    else:
        with pytest.raises(BulkError):reader.retrieve()
    assert all(url.startswith('https://api.github.com/') for url,_ in calls)
    assert 'do-not-log-test-token' not in repr(sink.events)
    assert all('Authorization' not in repr(payload) for _,payload in sink.events)
    with pytest.raises(BulkError):reader.get('repos/'+s.TARGET)


def test_disabled_private_intake_stops_before_token_or_network(monkeypatch,tmp_path):
    monkeypatch.setattr(private.requests,'Session',lambda:pytest.fail('Must stop before network'))
    with pytest.raises(BulkError,match='disabled'):private.fetch(tmp_path/'intake',Sink())


def test_workflows_separate_reader_writer_and_native_probe_without_installation():
    value=yaml.load((s.SETUP/'english-poster-canary.yml').read_text(encoding='utf-8'),Loader=yaml.BaseLoader)
    steps=value['jobs']['stage']['steps'];tokens=[i for i,v in enumerate(steps) if 'create-github-app-token@' in v.get('uses','')]
    assert len(tokens)==2
    assert steps[tokens[0]]['with']['repositories']=='english-canary-artifacts' and steps[tokens[0]]['with']['permission-contents']=='read'
    assert steps[tokens[1]]['with']['repositories']=='Default-Images' and steps[tokens[1]]['with']['permission-contents']=='write'
    assert any('authorize-metadata' in v.get('run','') for v in steps[:tokens[0]])
    assert any('canary_staging authorize' in v.get('run','') for v in steps[tokens[0]+1:tokens[1]])
    assert 'create-github-app-token' not in str(value['jobs']['verify'])
    probe=(s.SETUP/'english-canary-approval-check.yml').read_text(encoding='utf-8')
    assert 'PRIVATE_KEY' not in probe and 'create-github-app-token' not in probe
    probe_value=yaml.load(probe,Loader=yaml.BaseLoader)
    assert 'github.ref' not in probe_value['jobs']['before_gate']['if']  # non-main run reaches native branch rejection
    assert probe_value['jobs']['protected_probe']['environment']=='english-canary-stage'
    assert not (s.ROOT.parent/'.github/workflows/english-canary-approval-check.yml').exists()


@pytest.mark.parametrize('login',list(s.MAINTAINERS))
def test_stage_approval_requires_exact_run_setup_comment_even_for_trusted_self(login):
    auth={'sha256':'a'*64,'setup_receipt_sha256':'b'*64}
    comment=protection.approval_comment(auth,202)
    review={'state':'approved','comment':comment,'user':{'login':login,'id':s.MAINTAINERS[login]},'environments':[{'id':101,'name':'english-canary-stage'}]}
    assert s.check_native_approval([review],{'id':101},expected_comment=comment)
    for wrong in ['',comment.replace('202','203'),'bypass']:
        changed=deepcopy(review);changed['comment']=wrong
        with pytest.raises(BulkError):s.check_native_approval([changed],{'id':101},expected_comment=comment)


def test_independent_acceptance_failure_stops_private_intake_before_writer(monkeypatch,tmp_path):
    config=ready_artifact();monkeypatch.setattr(s,'envelope',lambda path:config)
    monkeypatch.setenv('CANARY_ARTIFACT_TOKEN','local-test-only')
    class Reader:
        def __init__(self,*args):self.session=SimpleNamespace(close=lambda:None)
        def retrieve(self):return b'fixture'
    monkeypatch.setattr(private,'PrivateReader',Reader)
    def reject(path):raise BulkError('canary_staging_stop','Independent image/acceptance hash differs')
    monkeypatch.setattr(s,'verify_bundle',reject)
    with pytest.raises(BulkError,match='acceptance'):private.fetch(tmp_path/'intake',Sink())


@pytest.mark.parametrize('value',[{'total_count':2,'repositories':[{'full_name':s.TARGET}]}, {'total_count':1,'repositories':[{'full_name':private.REPOSITORY}]}])
def test_writer_token_cannot_access_any_other_repository(value):
    response=SimpleNamespace(status_code=200,json=lambda:value,close=lambda:None)
    client=object.__new__(s.GitHub);client.session=SimpleNamespace(get=lambda *a,**k:response)
    with pytest.raises(BulkError):client.check_token_scope()
