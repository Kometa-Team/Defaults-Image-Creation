"""Staging is inert; exact scope, evidence, freshness and mutation routes fail closed."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import zipfile
import hashlib

import pytest
import yaml

from create_defaults.bulk import canary_staging as s
from create_defaults.bulk.common import BulkError,canonical,fingerprint


class Sink:
    def __init__(self):self.events=[]
    def add(self,kind,payload):self.events.append((kind,payload))


@pytest.fixture
def bundle():
    p=s.envelope(s.EVIDENCE/'preparation-20261017.json');rows=deepcopy(p['rows']);members={}
    for row in rows:
        data=('proposed test bytes '+row['destination']).encode();row['sha256']=hashlib.sha256(data).hexdigest()
        members['output/'+row['local_relative']]=data
    return SimpleNamespace(rows=rows,members=members)


class Fake:
    def __init__(self,bundle,heads=None,extra=False):
        self.bundle=bundle;self.heads=list(heads or ['a'*40]);self.writes=[];self.extra=extra
        self.original={r['destination']:{'sha':r['published']['git_blob'],'mode':'100644','type':'blob'} for r in bundle.rows}
        self.original['unrelated.txt']={'sha':'e'*40,'mode':'100644','type':'blob'}
    def head(self):return self.heads.pop(0) if len(self.heads)>1 else self.heads[0]
    def snapshot(self):return self.head(),'b'*40,deepcopy(self.original)
    def blob(self,data):self.writes.append('blob');return s.git_blob(data)
    def tree(self,base,replacements):
        self.writes.append('tree');self.candidate=deepcopy(self.original)
        for path,value in replacements.items():self.candidate[path]={'sha':value,'mode':'100644','type':'blob'}
        if self.extra:self.candidate['unrelated.txt']['sha']='f'*40
        return 'c'*40
    def files(self,tree):return self.candidate
    def commit(self,tree,parent,message):self.writes.append('commit');assert parent=='a'*40;return 'd'*40
    def create_ref(self,branch,commit):self.writes.append('new_ref');assert branch.startswith('canary/english-')
    def pull(self,branch,commit,auth):self.writes.append('draft_pr');return {'draft':True}


def test_stage_algorithm_has_exact_seven_diff_and_never_updates_master(bundle):
    client=Fake(bundle);audit=Sink()
    result=s.stage_objects(client,bundle,'a'*40,'canary/english-'+'1'*12,'1'*64,audit)
    assert set(result['paths'])==s.DESTINATIONS
    assert client.writes==['blob']*7+['tree','commit','new_ref','draft_pr']
    assert client.candidate['unrelated.txt']==client.original['unrelated.txt']
    assert audit.events[-1][1]['production_ref_updated'] is False


@pytest.mark.parametrize('heads,expected', [(['f'*40],[]),(['a'*40,'f'*40],[]),(['a'*40,'a'*40,'f'*40],['blob']*7+['tree','commit']),(['a'*40,'a'*40,'a'*40,'f'*40],['blob']*7+['tree','commit','new_ref']),(['a'*40,'a'*40,'a'*40,'a'*40,'f'*40],['blob']*7+['tree','commit','new_ref','draft_pr'])])
def test_head_drift_stops_before_first_write_or_ref(bundle,heads,expected):
    client=Fake(bundle,heads)
    with pytest.raises(BulkError,match='HEAD drift'):s.stage_objects(client,bundle,'a'*40,'canary/english-'+'1'*12,'1'*64,Sink())
    assert client.writes==expected


@pytest.mark.parametrize('mutation',['extra','case','old_blob','extra_candidate'])
def test_scope_or_baseline_drift_stops_without_ref(bundle,mutation):
    client=Fake(bundle,extra=mutation=='extra_candidate')
    if mutation=='extra':bundle.rows.append(deepcopy(bundle.rows[0]))
    elif mutation=='case':bundle.rows[3]['destination']='genre/Action & adventure.jpg'
    elif mutation=='old_blob':client.original[bundle.rows[0]['destination']]['sha']='f'*40
    with pytest.raises(BulkError):s.stage_objects(client,bundle,'a'*40,'canary/english-'+'1'*12,'1'*64,Sink())
    assert 'new_ref' not in client.writes and 'draft_pr' not in client.writes


def test_disabled_policy_blocks_cli_and_transport_before_credentials_or_network(tmp_path,monkeypatch):
    monkeypatch.setattr(s.requests,'Session',lambda:pytest.fail('Network session must not be constructed'))
    with pytest.raises(BulkError,match='disabled'):s.GitHub('unused',Sink(),'a'*40,'1'*64)
    with pytest.raises(BulkError,match='disabled'):s.execute_staging(tmp_path/'unused.zip','123',tmp_path/'audit')
    assert s.verify_audit(tmp_path/'audit')


@pytest.fixture
def authorized():
    policy=s.envelope(s.SETUP/'staging-policy.json');policy.update(staging_enabled=True,reviewer_confirmed=True,rollback_owner_confirmed=True)
    auth=s.envelope(s.SETUP/'staging-authorization.json');auth.update(authorized=True,source_release_asset_id=123,owner_confirmation=True,writer_reservation_confirmed=True,artifact_retention_confirmed=True,source_commit='1'*40,helper_sha256='2'*64,workflow_sha256='3'*64,environment_snapshot_sha256='4'*64,expires_at_utc=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
    return policy,auth


def test_exact_separate_authorization_required(authorized):
    policy,auth=authorized
    assert s.validate_authorization(policy,auth,source_sha='1'*40,helper_sha='2'*64,workflow_sha='3'*64).startswith('canary/english-')


@pytest.mark.parametrize('field,value',[('authorized',False),('source_release_asset_id',None),('owner_confirmation',False),('writer_reservation_confirmed',False),('artifact_retention_confirmed',False),('bundle_sha256','f'*64),('acceptance_sha256','f'*64),('target_repository','other/repository'),('publish_authorized',True),('merge_authorized',True),('source_commit','f'*40),('helper_sha256','f'*64),('workflow_sha256','f'*64),('expires_at_utc','2000-01-01T00:00:00Z')])
def test_bad_authorization_is_rejected(authorized,field,value):
    policy,auth=authorized;auth[field]=value
    with pytest.raises(BulkError):s.validate_authorization(policy,auth,source_sha='1'*40,helper_sha='2'*64,workflow_sha='3'*64)


@pytest.mark.parametrize('method,endpoint,payload',[
 ('PATCH','git/refs/heads/master',{'sha':'d'*40,'force':False}),
 ('PUT','pulls/12/merge',{}),('DELETE','git/refs/heads/canary/english-123456789abc',{}),
 ('POST','git/refs',{'ref':'refs/heads/master','sha':'d'*40}),
 ('POST','git/refs',{'ref':'refs/heads/canary/english-123456789abc','sha':'d'*40,'force':True}),
 ('POST','pulls',{'head':'canary/english-123456789abc','base':'master','draft':False}),
 ('POST','git/commits',{'tree':'c'*40,'parents':['f'*40]}),
 ('POST','git/trees',{'base_tree':'b'*40,'tree':[]}),
 ('POST','git/blobs',{'encoding':'base64','content':'bm90LWFjY2VwdGVk'})])
def test_mutation_transport_cannot_publish_force_merge_or_widen_scope(monkeypatch,method,endpoint,payload):
    monkeypatch.setattr(s,'runtime_write_gate',lambda value:None)
    client=object.__new__(s.GitHub);client.audit=Sink();client.expected_head='a'*40;client.staging_commit='d'*40;client.authorization_sha='1'*64;client.accepted_image_hashes={'f'*64}
    client.session=SimpleNamespace(request=lambda *a,**k:pytest.fail('Forbidden request reached network'))
    with pytest.raises(BulkError):client.call(method,endpoint,payload)


@pytest.fixture
def native_environment():
    return {'id':101,'name':'english-canary-stage','can_admins_bypass':False,
        'protection_rules':[{'type':'required_reviewers','prevent_self_review':False,
            'reviewers':[{'type':'User','reviewer':{'login':login,'id':uid}} for login,uid in s.MAINTAINERS.items()]}],
        'deployment_branch_policy':{'protected_branches':False,'custom_branch_policies':True}}


def review(login, environment_id=101, state='approved'):
    return {'state':state,'environments':[{'id':environment_id,'name':'english-canary-stage'}],
        'user':{'login':login,'id':s.MAINTAINERS.get(login,999)}}


def run_context(actor):
    context={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':s.SOURCE,'GITHUB_EVENT_NAME':'workflow_dispatch',
        'GITHUB_REF':'refs/heads/main','CANARY_STAGING_CONFIRMED':'true','CANARY_POLICY_VARIABLE':'true',
        'GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_ID':'202','GITHUB_ACTOR':actor}
    run={'id':202,'run_attempt':1,'repository':{'full_name':s.SOURCE},'head_sha':'a'*40,
        'head_branch':'main','event':'workflow_dispatch','path':'.github/workflows/english-poster-canary.yml'}
    return context,run


@pytest.mark.parametrize('initiator,approver',[(initiator,approver) for initiator in [*s.MAINTAINERS,'outside-writer'] for approver in s.MAINTAINERS])
def test_local_policy_allows_trusted_self_or_other_review_but_never_infers_approval(native_environment,initiator,approver):
    context,run=run_context(initiator)
    s.validate_run_context(context,run,'a'*40)
    assert s.check_environment(native_environment,[{'name':'main','type':'branch'}])
    with pytest.raises(BulkError,match='approval absent'):s.check_native_approval([],native_environment)
    proof=s.check_native_approval([review(approver)],native_environment)
    assert proof['approvers']==[{'login':approver,'id':s.MAINTAINERS[approver]}]
    assert proof['production_authorized'] is False  # Staging approval grants no production permission.


@pytest.mark.parametrize('mutation',['missing_reviewers','extra_writer','missing_maintainer','wrong_id',
    'duplicate_user','self_review_prevented','self_review_unspecified','bypass_enabled','bypass_unobservable',
    'team_missing','team_changed','wrong_branch','tag_branch','wrong_environment'])
def test_local_environment_policy_fails_closed(native_environment,mutation):
    env=native_environment;rule=env['protection_rules'][0];branches=[{'name':'main','type':'branch'}]
    if mutation=='missing_reviewers':env['protection_rules']=[]
    elif mutation=='extra_writer':rule['reviewers'].append({'type':'User','reviewer':{'login':'outside-writer','id':999}})
    elif mutation=='missing_maintainer':rule['reviewers'].pop()
    elif mutation=='wrong_id':rule['reviewers'][0]['reviewer']['id']=999
    elif mutation=='duplicate_user':rule['reviewers'][-1]=deepcopy(rule['reviewers'][0])
    elif mutation=='self_review_prevented':rule['prevent_self_review']=True
    elif mutation=='self_review_unspecified':rule.pop('prevent_self_review')
    elif mutation=='bypass_enabled':env['can_admins_bypass']=True
    elif mutation=='bypass_unobservable':env.pop('can_admins_bypass')
    elif mutation in {'team_missing','team_changed'}:rule['reviewers']=[{'type':'Team','reviewer':{'slug':'image-publishing-approvers' if mutation=='team_missing' else 'developers','id':13883129}}]
    elif mutation=='wrong_branch':branches[0]['name']='*'
    elif mutation=='tag_branch':branches[0]['type']='tag'
    elif mutation=='wrong_environment':env['name']='english-canary-production'
    with pytest.raises(BulkError):s.check_environment(env,branches)


@pytest.mark.parametrize('mutation',['team_mode','policy_team_field','policy_receipt','authorization_receipt','authorization_team_mode'])
def test_option_a_rejects_team_substitution_or_changed_model_decision(authorized,mutation):
    policy,auth=deepcopy(authorized)
    if mutation=='team_mode':policy['reviewer_representation']=auth['reviewer_representation']='team'
    elif mutation=='policy_team_field':policy['reviewer_team']={'id':13883129,'slug':'developers'}
    elif mutation=='policy_receipt':policy['reviewer_model_approval_sha256']='f'*64
    elif mutation=='authorization_receipt':auth['reviewer_model_approval_sha256']='f'*64
    elif mutation=='authorization_team_mode':auth['reviewer_representation']='team'
    with pytest.raises(BulkError):s.validate_authorization(policy,auth,source_sha='1'*40,helper_sha='2'*64,workflow_sha='3'*64)


def test_option_a_records_only_model_acceptance_without_organization_lookup_or_setup_authority():
    decision=s.envelope(s.EVIDENCE/'explicit-user-model-decision-20261018.json')
    policy=s.envelope(s.SETUP/'staging-policy.json');auth=s.envelope(s.SETUP/'staging-authorization.json')
    assert decision['sha256']==policy['reviewer_model_approval_sha256']==auth['reviewer_model_approval_sha256']==s.REVIEWER_MODEL_SHA
    assert decision['decision']=='accepted' and decision['reviewer_representation']=='explicit_users'
    assert decision['authorized_maintainers']==policy['authorized_maintainers']==s.MAINTAINERS
    assert decision['required_approvals']==1 and decision['prevent_self_review'] is False
    assert decision['organization_team_lookup_required'] is False and 'reviewer_team' not in policy
    assert policy['reviewer_confirmed'] is True and policy['rollback_owner_confirmed'] is False
    assert policy['staging_enabled'] is auth['authorized'] is False
    assert not any(decision[k] for k in ['workflow_installation_authorized','environment_creation_authorized',
        'credentials_authorized','artifact_upload_authorized','staging_authorized','publication_authorized','merge_authorized'])
    assert 'orgs/Kometa-Team/teams' not in Path(s.__file__).read_text(encoding='utf-8')


@pytest.mark.parametrize('history',[[review('outside-writer')],[review('unlisted-admin')],
    [review('bullmoose20',state='rejected')],[review('bullmoose20',environment_id=102)],
    [{'state':'approved','environments':[{'id':101,'name':'english-canary-production'}],'user':{'login':'bullmoose20','id':12549033}}],
    [{'state':'approved','environments':[{'id':101,'name':'english-canary-stage'}],'user':{'login':'bullmoose20','id':999}}],None])
def test_outsiders_wrong_environment_and_spoofed_id_cannot_satisfy_approval(native_environment,history):
    with pytest.raises(BulkError):s.check_native_approval(history,native_environment)


@pytest.mark.parametrize('mutation',['rerun','wrong_sha','pull_request','other_repo','wrong_workflow','unconfirmed'])
def test_run_identity_prevents_approval_reuse_and_input_bypass(mutation):
    context,run=run_context('outside-writer')
    if mutation=='rerun':context['GITHUB_RUN_ATTEMPT']='2';run['run_attempt']=2
    elif mutation=='wrong_sha':run['head_sha']='f'*40
    elif mutation=='pull_request':run['event']='pull_request'
    elif mutation=='other_repo':run['repository']['full_name']='outside/fork'
    elif mutation=='wrong_workflow':run['path']='.github/workflows/untrusted.yml'
    elif mutation=='unconfirmed':context['CANARY_STAGING_CONFIRMED']='false'
    with pytest.raises(BulkError):s.validate_run_context(context,run,'a'*40)


@pytest.mark.parametrize('side',['policy','authorization'])
def test_mutated_roster_or_pr_configuration_cannot_add_an_approver(authorized,side):
    policy,auth=deepcopy(authorized)
    (policy if side=='policy' else auth)['authorized_maintainers']['outside-writer']=999
    with pytest.raises(BulkError):s.validate_authorization(policy,auth,source_sha='1'*40,helper_sha='2'*64,workflow_sha='3'*64)


@pytest.mark.parametrize('bad',['../escape','/absolute','link','duplicate','checksum'])
def test_archive_structure_and_checksum_guards(tmp_path,bad):
    data=b'fixture';name=bad if bad in {'../escape','/absolute'} else 'member'
    inventory={name:{'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}}
    if bad=='checksum':inventory[name]['sha256']='f'*64
    path=tmp_path/'archive.zip'
    with zipfile.ZipFile(path,'w') as z:
        entry=zipfile.ZipInfo(name)
        if bad=='link':entry.external_attr=0o120777<<16
        z.writestr(entry,data)
        if bad=='duplicate':
            with pytest.warns(UserWarning):z.writestr(name,data)
        z.writestr('SHA256SUMS.json',canonical(inventory))
    with pytest.raises(BulkError):s.read_archive(path,s.sha256(path),inventory)


def test_audit_is_append_only_and_tampering_is_detected(tmp_path):
    audit=s.Audit(tmp_path/'audit');audit.add('one',{'status':'checked'});audit.add('two',{'status':'stopped'})
    assert s.verify_audit(audit.root)==audit.previous
    with audit.store.connection() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute('UPDATE events SET kind=?',('changed',))
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM events')
    path=audit.root/'0001.json';item=json.loads(path.read_text());item['payload']['status']='altered';path.write_text(json.dumps(item))
    with pytest.raises(BulkError):s.verify_audit(audit.root)


def test_workflow_template_is_uninstalled_and_defaults_disabled():
    assert not (s.ROOT.parent/'.github/workflows/english-poster-canary.yml').exists()
    value=yaml.load((s.SETUP/'english-poster-canary.yml').read_text(),Loader=yaml.BaseLoader)
    assert set(value['on'])=={'workflow_dispatch'}
    inputs=value['on']['workflow_dispatch']['inputs']
    assert inputs['mode']['options']==['verify','stage'] and inputs['mode']['default']=='verify'
    assert inputs['confirm_staging']['default']=='false'
    assert value['permissions']=={'contents':'read','actions':'read'}
    stage=value['jobs']['stage'];assert stage['environment']=='english-canary-stage'
    assert 'github.actor' not in stage['if'] and 'github.triggering_actor' not in stage['if']
    assert 'environment' not in value['jobs']['verify']
    assert "vars.ENGLISH_CANARY_STAGING_ENABLED == 'true'" in stage['if']
    steps=stage['steps'];token=next(i for i,v in enumerate(steps) if 'actions/create-github-app-token@' in v.get('uses',''))
    assert any(' authorize ' in (' '+v.get('run','').replace('\n',' ')+' ') for v in steps[:token])
    assert steps[token]['with']['repositories']=='Default-Images'
    assert steps[token]['with']['skip-token-revoke']=='false'
    assert s.envelope(s.SETUP/'staging-policy.json')['staging_enabled'] is False
    assert s.envelope(s.SETUP/'staging-policy.json')['reviewer_confirmed'] is True
    assert s.envelope(s.SETUP/'staging-authorization.json')['authorized'] is False


def test_deployment_subset_and_final_dry_run_bind_current_implementation(tmp_path):
    import os, subprocess, sys
    manifest=s.envelope(s.SETUP/'deployment-files.json')
    proof=s.envelope(s.EVIDENCE/'explicit-user-infrastructure-20261018.json')
    dry=s.envelope(s.EVIDENCE/'explicit-user-dry-run-20261018.json')
    assert proof['deployment_manifest_sha256']==manifest['sha256']
    assert proof['local_dry_run']==dry
    assert dry['archive_sha256']==s.BUNDLE_SHA and dry['acceptance_sha256']==s.ACCEPTANCE_SHA
    assert dry['helper_sha256']==hashlib.sha256(Path(s.__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    assert dry['network_requests']==dry['remote_writes']==dry['staging_branches_created']==dry['pull_requests_created']==0
    assert dry['verified_candidate_hashes']==7 and dry['local_refs_unchanged'] and dry['local_worktree_unchanged']
    assert proof['staging_enabled'] is proof['workflow_installed'] is proof['credentials_enabled'] is proof['roles_confirmed'] is False
    runtime=tmp_path/'isolated-runtime';runtime.mkdir()
    for entry in manifest['files']:
        data=(s.ROOT.parent/entry['source']).read_bytes().replace(b'\r\n',b'\n')
        assert hashlib.sha256(data).hexdigest()==entry['sha256_normalized_lf']
        target=runtime/entry['future_target'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    # A local fixture validates the separate minimal deployment, never GitHub installation.
    env=dict(os.environ,PYTHONPATH=str(runtime));env.pop('CANARY_APP_TOKEN',None);env.pop('GH_TOKEN',None)
    result=subprocess.run([sys.executable,'-m','create_defaults.bulk.canary_staging','stage','--bundle','unused.zip','--asset-id','123','--audit-root',str(tmp_path/'disabled-fixture-audit')],cwd=runtime,env=env,capture_output=True,text=True)
    assert result.returncode!=0 and 'Staging remains disabled' in result.stderr
    assert not (s.ROOT.parent/'.github/workflows/english-poster-canary.yml').exists()


def test_permission_addendum_verifies_fifth_account_without_rewriting_initial_observations():
    old=s.envelope(s.EVIDENCE/'trusted-maintainer-permissions-20261018.json')
    current=s.envelope(s.EVIDENCE/'trusted-maintainer-permissions-20261018-v2.json')
    assert current['supersedes_intended_roster_from_sha256']==old['sha256']
    assert current['intended_maintainers']==s.MAINTAINERS
    rows=current['additional_observations']
    roles=[r['response'] for r in rows if '/collaborators/badja-dev/permission' in r['endpoint']]
    assert len(roles)==2 and all(r['login']=='badja-dev' and r['role_name']=='admin' for r in roles)
    members=next(r['response'] for r in rows if '/members?' in r['endpoint'])
    assert {r['login']:r['id'] for r in members}==s.MAINTAINERS


@pytest.mark.parametrize('scenario',['authorized','no_review','outside_review','changed_environment','unobservable_bypass','forbidden_team_mode','production_requested'])
def test_preflight_requires_native_proof_before_target_token(authorized,native_environment,tmp_path,monkeypatch,scenario):
    policy,auth=deepcopy(authorized)
    root=tmp_path/'create_defaults';root.mkdir()
    workflow=root.parent/'.github/workflows/english-poster-canary.yml';workflow.parent.mkdir(parents=True);workflow.write_bytes(b'fixture workflow')
    auth.update(helper_sha256=hashlib.sha256(Path(s.__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        workflow_sha256=hashlib.sha256(workflow.read_bytes()).hexdigest(),admin_bypass_disabled_confirmed=True)
    branches=[{'name':'main','type':'branch'}]
    auth['environment_snapshot_sha256']=s.check_environment(native_environment,branches)
    auth['destinations']=sorted(s.DESTINATIONS)
    context,run=run_context('badja-dev');run['head_sha']='1'*40
    for key,value in context.items():monkeypatch.setenv(key,value)
    monkeypatch.setattr(s,'ROOT',root)
    def envelopes(path):return deepcopy(policy if Path(path).name=='staging-policy.json' else auth)
    monkeypatch.setattr(s,'envelope',envelopes)
    monkeypatch.setattr(s.subprocess,'check_output',lambda args,**kw:'1'*40 if args[1]=='rev-parse' else '')
    monkeypatch.setattr(s.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=0))
    monkeypatch.setattr(s,'verify_bundle',lambda path:SimpleNamespace(rows=[{'destination':d} for d in sorted(s.DESTINATIONS)],preparation={'published_snapshot':{'head':auth['expected_target_head']}}))
    monkeypatch.setattr(s,'GitHub',lambda *a,**kw:pytest.fail('No target token/client during authorize or failed preflight'))
    history=[review('badja-dev')]
    if scenario=='no_review':history=[]
    elif scenario=='outside_review':history=[review('outside-writer')]
    elif scenario=='changed_environment':auth['environment_snapshot_sha256']='f'*64
    elif scenario=='unobservable_bypass':native_environment.pop('can_admins_bypass')
    elif scenario=='forbidden_team_mode':policy['reviewer_representation']=auth['reviewer_representation']='team'
    elif scenario=='production_requested':auth['publish_authorized']=True
    def api(endpoint):
        if endpoint.endswith('/environments/english-canary-stage'):return native_environment
        if endpoint.endswith('/deployment-branch-policies'):return {'total_count':1,'branch_policies':branches}
        if endpoint.endswith('/approvals'):return history
        if endpoint.endswith('/actions/runs/202'):return run
        if endpoint.startswith('orgs/'):
            pytest.fail('No organization/team API call is permitted for Option A')
        pytest.fail('Unexpected API endpoint: '+endpoint)
    monkeypatch.setattr(s,'gh_json',api)
    if scenario=='authorized':
        # Stubbed APIs validate integration/policy only, not GitHub's server-side gate.
        s.execute_staging('fixture.zip','123',tmp_path/'audit',preflight_only=True)
        event=__import__('json').loads((tmp_path/'audit/0001.json').read_text(encoding='utf-8'))
        assert event['payload']['native_approval']['approvers'][0]['login']=='badja-dev'
        assert event['payload']['native_approval']['production_authorized'] is False
    else:
        with pytest.raises(BulkError):s.execute_staging('fixture.zip','123',tmp_path/'audit',preflight_only=True)
