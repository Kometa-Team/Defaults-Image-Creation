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
    auth=s.envelope(s.SETUP/'staging-authorization.json');auth.update(authorized=True,source_release_asset_id=123,owner_confirmation=True,writer_reservation_confirmed=True,artifact_retention_confirmed=True,source_commit='1'*40,helper_sha256='2'*64,workflow_sha256='3'*64,expires_at_utc=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
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


def test_environment_requires_confirmed_named_independent_review():
    env={'protection_rules':[{'type':'required_reviewers','prevent_self_review':True,'reviewers':[{'type':'User','reviewer':{'login':'bullmoose20'}}]}],'deployment_branch_policy':{'protected_branches':False,'custom_branch_policies':True}}
    s.check_environment(env,[{'name':'main','type':'branch'}])
    env['protection_rules'][0]['prevent_self_review']=False
    with pytest.raises(BulkError):s.check_environment(env,[{'name':'main','type':'branch'}])


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
    assert "vars.ENGLISH_CANARY_STAGING_ENABLED == 'true'" in stage['if']
    steps=stage['steps'];token=next(i for i,v in enumerate(steps) if 'actions/create-github-app-token@' in v.get('uses',''))
    assert any(' authorize ' in (' '+v.get('run','').replace('\n',' ')+' ') for v in steps[:token])
    assert steps[token]['with']['repositories']=='Default-Images'
    assert steps[token]['with']['skip-token-revoke']=='false'
    assert s.envelope(s.SETUP/'staging-policy.json')['staging_enabled'] is False
    assert s.envelope(s.SETUP/'staging-policy.json')['reviewer_confirmed'] is False
    assert s.envelope(s.SETUP/'staging-authorization.json')['authorized'] is False


def test_deployment_subset_and_final_dry_run_bind_current_implementation(tmp_path):
    import os, subprocess, sys
    manifest=s.envelope(s.SETUP/'deployment-files.json')
    proof=s.envelope(s.EVIDENCE/'staging-infrastructure-20261018.json')
    dry=s.envelope(s.EVIDENCE/'staging-infrastructure-dry-run-20261018.json')
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
