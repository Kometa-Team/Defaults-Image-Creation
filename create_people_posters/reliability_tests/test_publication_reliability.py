"""No network: canonical Git objects, fault injection and temporary real SQLite."""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
import requests
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'create_people_posters'))
from people_github import GitHubClient, GitHubError, REPOSITORIES
from people_publication_state import PublicationState
from people_remote_inventory import RemoteInventory, blob_sha
from publish_people_github import Publisher

spec = importlib.util.spec_from_file_location('legacy_fake', ROOT/'create_people_posters/tests/test_people_github.py')
legacy = importlib.util.module_from_spec(spec); spec.loader.exec_module(legacy)
BATCH = '20261104T141304-52ea09305f3a'


class Restart(BaseException):
    pass


class Clock:
    value = 1800000000.0
    def __call__(self): return self.value
    def sleep(self, seconds): self.value += seconds


class Git(legacy.FakeGitHub):
    def __init__(self):
        self.flat = {}; self.recursive = {}; self.records = {}; self.failures = []; self.mutations = []
        super().__init__()

    def pack(self, files):
        entries = {p:dict(v, path=p) for p,v in files.items() if v['type'] != 'tree'}
        folders = {''}
        for path in entries:
            parts = path.split('/')
            folders.update('/'.join(parts[:n]) for n in range(1,len(parts)))
        root = None
        for folder in sorted(folders,key=lambda p:(p.count('/'),len(p)),reverse=True):
            prefix = folder+'/' if folder else ''
            children = [dict(v,path=p[len(prefix):]) for p,v in entries.items() if p.startswith(prefix) and '/' not in p[len(prefix):]]
            sha = Publisher.tree_identity(children)
            self.trees[sha] = {e['path']:e for e in children}
            self.recursive[sha] = [dict(v,path=p[len(prefix):]) for p,v in entries.items() if p.startswith(prefix)]
            self.flat[sha] = {p[len(prefix):]:dict(v) for p,v in entries.items() if p.startswith(prefix) and v['type']!='tree'}
            if folder: entries[folder] = dict(path=folder,sha=sha,type='tree',mode='040000')
            else: root = sha
        return root

    def advance(self, repo, files):
        tree = self.pack(files)
        person = dict(name='Fixture', email='fixture@example.invalid', date='2026-11-05T00:00:00Z')
        payload = dict(tree=tree,parents=[self.heads[repo]] if repo in self.heads else [],
                       message='fixture '+self.new_sha()+'\n',author=person,committer=person)
        sha = Publisher.commit_identity(payload)
        self.commits[sha]=tree;self.records[sha]=payload;self.heads[repo]=sha
        return sha

    def generate_readmes(self, repo):
        from urllib.parse import quote
        files=copy.deepcopy(self.flat[self.commits[self.heads[repo]]])
        images=[p for p in files if '/Images/' in p]
        for path in ['README.md']+sorted({p.split('/')[0]+'/README.md' for p in images}):
            data='\n'.join(f'* [{Path(p).stem}](https://raw.githubusercontent.com/{repo}/master/{quote(p)})'
                for p in images if path=='README.md' or p.startswith(path.split('/')[0]+'/')).encode()
            sha=blob_sha(data);self.blobs[sha]=data
            files[path]=dict(sha=sha,type='blob',mode='100644',size=len(data))
        self.advance(repo,files)

    def request(self,method,path,payload=None):
        repo='/'.join(path.split('/')[2:4]);route='/'.join(path.split('/')[4:])
        point='ref' if method=='PATCH' else route.split('/')[1] if route.startswith('git/') else 'other'
        failure=next((f for f in self.failures if f['method']==method and f['point']==point),None)
        if failure and not failure.get('after'):
            self.failures.remove(failure);raise failure['error']
        if method=='GET' and route.startswith('git/trees/'):
            sha=route.split('/')[2].split('?')[0]
            if sha not in self.trees: raise GitHubError('missing',404)
            result=dict(sha=sha,tree=self.recursive[sha] if '?' in route else list(self.trees[sha].values()),truncated=False)
        elif method=='GET' and route.startswith('git/blobs/'):
            sha=route.split('/')[2]
            if sha not in self.blobs: raise GitHubError('missing',404)
            result=dict(sha=sha,encoding='base64',content=base64.b64encode(self.blobs[sha]).decode())
        elif method=='GET' and route.startswith('git/commits/'):
            sha=route.split('/')[2]
            if sha not in self.records: raise GitHubError('missing',404)
            p=self.records[sha];result=dict(p,sha=sha,tree={'sha':p['tree']},parents=[{'sha':x} for x in p['parents']])
        elif method=='POST' and route=='git/trees':
            files=copy.deepcopy(self.flat[payload['base_tree']])
            for e in payload['tree']:files[e['path']]=dict(e,size=len(self.blobs[e['sha']]))
            result=dict(sha=self.pack(files));self.mutations.append(('tree',result['sha']))
        elif method=='POST' and route=='git/commits':
            sha=Publisher.commit_identity(payload)
            self.commits[sha]=payload['tree'];self.records[sha]=copy.deepcopy(payload)
            result=dict(sha=sha);self.mutations.append(('commit',sha))
        elif method=='GET' and route.startswith('compare/'):
            before,after=route.split('/')[1].split('...')
            old=self.flat[self.commits[before]];new=self.flat[self.commits[after]]
            result=dict(status='ahead',total_commits=1,files=[dict(filename=p,sha=v['sha'],status='modified' if p in old else 'added')
                for p,v in new.items() if p not in old or v['sha']!=old[p]['sha']])
        else:
            result=super().request(method,path,payload)
            if method=='PATCH':self.mutations.append(('ref',payload['sha']))
            if method=='POST' and route=='git/blobs':self.mutations.append(('blob',result['sha']))
            if failure and failure.get('after'):
                self.failures.remove(failure);raise failure['error']
            return result
        self.calls.append((method,path,payload))
        if failure and failure.get('after'):
            self.failures.remove(failure);raise failure['error']
        return result


def rows(root, count, style='bw'):
    root.mkdir(parents=True,exist_ok=True)
    result=[]
    for i in range(count):
        data=(style+f'-approved-{i}').encode();path=root/(str(i)+'.jpg');path.write_bytes(data)
        digest=hashlib.sha256(data).hexdigest()
        result.append(dict(style=style,repo=REPOSITORIES[style],path=f'A/Images/Person {i:05d}.jpg',
            source=str(path),prepared=str(path),source_hash=digest,published_hash=digest,blob=blob_sha(data),person=f'Person {i:05d}'))
    return result


def setup_run(tmp_path, monkeypatch, count=3, style='bw', completed=0):
    monkeypatch.setenv('PEOPLE_RELIABLE_PUBLISH','true')
    monkeypatch.setenv('UPDATE_TRIGGER_READMES','true')
    monkeypatch.setenv('PEOPLE_README_POLL_INTERVAL','0.001')
    client=Git();entries=rows(tmp_path/'images',count,style);repo=REPOSITORIES[style]
    initial={r['path']:dict(sha=r['blob'],type='blob',mode='100644',size=1) for r in entries[:completed]}
    client.advance(repo,initial)
    monkeypatch.setenv('PEOPLE_PUBLICATION_EXPECTED_HEAD',client.heads[repo])
    ledger=PublicationState(tmp_path/'state');ledger.plan(BATCH,'master',entries)
    if completed:
        ledger.mark(BATCH,repo,[r['path'] for r in entries[:completed]],'published',client.heads[repo])
        ledger.mark(BATCH,repo,[r['path'] for r in entries[completed:]],'failed',error='error_category=github_api http_status=422 publisher_line=237')
        monkeypatch.setenv('PEOPLE_PUBLICATION_LEGACY_REVIEW_SHA256',ledger.legacy_review(BATCH,repo))
    inventory=RemoteInventory(client,tmp_path/'inventory.db','master');inventory.repositories={style:repo}
    clock=Clock()
    return client,entries,ledger,inventory,clock


def run(client,ledger,inventory,clock,hook=None):
    Publisher(client,inventory,ledger,clock=clock,sleep=clock.sleep,jitter=lambda:0,checkpoint_hook=hook).publish(BATCH)


@pytest.mark.parametrize('stage',['prepared','blobs_ack','blobs_uploaded','trees_ack','tree_created','commits_ack',
    'commit_created','ref_ack','branch_updated','remote_verified','published'])
def test_every_durable_and_ambiguous_crash_boundary(tmp_path,monkeypatch,stage):
    client,entries,ledger,inv,clock=setup_run(tmp_path,monkeypatch)
    hit=[]
    def crash(point):
        if point==stage and not hit:hit.append(point);raise Restart()
    with pytest.raises(Restart):run(client,ledger,inv,clock,crash)
    ledger.close();ledger=PublicationState(tmp_path/'state')
    run(client,ledger,inv,clock)
    assert ledger.verified(BATCH)
    assert len([m for m in client.mutations if m[0]=='commit'])==1
    assert len([m for m in client.mutations if m[0]=='ref'])==1
    assert len([m for m in client.mutations if m[0]=='blob'])==len(entries)
    ledger.close();inv.close()


@pytest.mark.parametrize('point',['blobs','trees','commits','ref'])
def test_lost_write_response_reconciles_before_replay(tmp_path,monkeypatch,point):
    client,entries,ledger,inv,clock=setup_run(tmp_path,monkeypatch)
    client.failures=[dict(method='PATCH' if point=='ref' else 'POST',point=point,after=True,
        error=GitHubClient.reliability_error('network',retryable=True,ambiguous=True))]
    run(client,ledger,inv,clock)
    assert ledger.verified(BATCH)
    assert len([m for m in client.mutations if m[0]=='commit'])==1
    assert len([m for m in client.mutations if m[0]=='tree'])==1
    assert ledger.db.execute('select count(*) from publication_units').fetchone()[0]==2
    ledger.close();inv.close()


@pytest.mark.parametrize('category,status',[('validation',422),('unclassified',422),('permission',403),('remote_conflict',409)])
def test_permanent_or_unknown_errors_stop_only_current_unit(tmp_path,monkeypatch,category,status):
    client,entries,ledger,inv,clock=setup_run(tmp_path,monkeypatch,count=101)
    client.failures=[dict(method='POST',point='trees',error=GitHubClient.reliability_error(category,status))]
    with pytest.raises(GitHubError):run(client,ledger,inv,clock)
    progress=ledger.reliability_progress(BATCH,entries[0]['repo'])
    assert progress['pending']==51
    assert progress['permanently_failed' if category=='validation' else 'blocked']==50
    assert all(r['status']=='pending' for r in ledger.rows(BATCH))
    assert not any('dispatches' in p for _,p,_ in client.calls)
    ledger.close();inv.close()


def test_retry_deadline_and_budget_survive_restart(tmp_path,monkeypatch):
    client,entries,ledger,inv,clock=setup_run(tmp_path,monkeypatch)
    error=GitHubClient.reliability_error('rate_limit',429,True,False,{'rate_limit':{'retry_after_seconds':7200,'remaining':0,'reset':clock()+8000}})
    client.failures=[dict(method='POST',point='trees',error=error)]
    def crash(point):
        if point=='blobs_uploaded':
            data=ledger.db.execute('select data from publication_units').fetchone()
            if data and json.loads(data[0])['status']=='retrying':raise Restart()
    with pytest.raises(Restart):run(client,ledger,inv,clock,crash)
    data=json.loads(ledger.db.execute('select data from publication_units').fetchone()[0]);deadline=data['not_before']
    assert deadline==clock()+8000 and data['attempts']==1
    ledger.close();ledger=PublicationState(tmp_path/'state');run(client,ledger,inv,clock)
    assert clock()>=deadline and ledger.verified(BATCH)
    ledger.close();inv.close()


def test_interrupted_receipt_transaction_rolls_back_and_resumes(tmp_path,monkeypatch):
    client,entries,ledger,inv,clock=setup_run(tmp_path,monkeypatch)
    ledger.reliability_schema()
    ledger.db.execute("CREATE TRIGGER interrupted BEFORE UPDATE ON publication_controls BEGIN SELECT RAISE(ABORT,'fixture interruption'); END")
    with pytest.raises(sqlite3.IntegrityError):run(client,ledger,inv,clock)
    assert all(r['status']=='pending' for r in ledger.rows(BATCH))
    ledger.db.execute('DROP TRIGGER interrupted');ledger.db.commit();run(client,ledger,inv,clock)
    assert ledger.verified(BATCH) and len([m for m in client.mutations if m[0]=='commit'])==1
    ledger.close();inv.close()


def test_unexpected_head_and_exclusive_writer_stop_safely(tmp_path,monkeypatch):
    client,entries,ledger,inv,clock=setup_run(tmp_path,monkeypatch)
    with ledger.publication_lock():
        other=PublicationState(tmp_path/'state')
        with pytest.raises(OSError):run(client,other,inv,clock)
        other.close()
    client.advance(entries[0]['repo'],{})
    with pytest.raises(GitHubError):run(client,ledger,inv,clock)
    assert not client.mutations
    ledger.close();inv.close()


def test_git_identities_match_native_git():
    author=dict(name='Fixture',email='fixture@example.invalid',date='2026-11-05T00:00:00Z')
    p=dict(tree='a'*40,parents=['b'*40],message='fixture\n',author=author,committer=author)
    raw=('tree '+'a'*40+'\nparent '+'b'*40+'\nauthor Fixture <fixture@example.invalid> 1793836800 +0000\n'
         'committer Fixture <fixture@example.invalid> 1793836800 +0000\n\nfixture\n').encode()
    assert Publisher.commit_identity(p)==subprocess.check_output(['git','hash-object','-t','commit','--stdin'],input=raw).decode().strip()


def test_ambiguous_readme_dispatch_reuses_existing_correlation(tmp_path,monkeypatch):
    client,entries,ledger,inv,clock=setup_run(tmp_path,monkeypatch)
    client.failures=[dict(method='POST',point='other',after=True,error=GitHubClient.reliability_error('network',retryable=True,ambiguous=True))]
    run(client,ledger,inv,clock)
    assert ledger.verified(BATCH)
    assert len([p for m,p,_ in client.calls if m=='POST' and 'dispatches' in p])==1
    ledger.close();inv.close()


@pytest.mark.parametrize('status,body,headers,category,retryable',[
    (422,{'message':'Validation Failed','errors':[{'resource':'Tree','field':'sha','code':'invalid'}]}, {},'validation',False),
    (422,{'message':'unknown provider text'}, {},'unclassified',False),
    (422,{'message':'Validation Failed','errors':[]}, {},'unclassified',False),
    (422,{'message':'Validation Failed','errors':[{'resource':'Tree','code':'custom'}]}, {},'unclassified',False),
    (403,{'message':'permission denied'}, {},'permission',False),
    (401,{'message':'bad credentials'}, {},'authentication',False),
    (409,{'message':'conflict'}, {},'remote_conflict',False),
    (429,{'message':'rate limit'},{'X-RateLimit-Remaining':'0','X-RateLimit-Reset':'1800000600'},'rate_limit',True),
    (403,{'message':'You have exceeded a secondary rate limit. Please wait a few minutes before you try again.'},{'Retry-After':'3600'},'rate_limit',True),
    (503,{'message':'unavailable'}, {},'service',True),
    (429,{'message':'limit','authorization':'never-log-this'}, {},'unclassified',False),
])
def test_reliable_transport_never_replays_writes_and_classifies(monkeypatch,capsys,status,body,headers,category,retryable):
    monkeypatch.setenv('PEOPLE_RELIABLE_PUBLISH','true')
    monkeypatch.delenv('PEOPLE_GITHUB_WRITE_INTERVAL',raising=False)
    response=requests.Response();response.status_code=status;response._content=json.dumps(body).encode();response.headers.update(headers)
    calls=[];clock=Clock()
    session=SimpleNamespace(headers={},request=lambda *a,**k:calls.append((a,k)) or response)
    client=GitHubClient('offline-reliability-only-not-a-real-credential',session=session,sleep=clock.sleep)
    with pytest.raises(GitHubError) as caught:client.request('POST','/repos/Kometa-Team/People-Images-bw/git/trees',{})
    assert len(calls)==1 and client.write_interval==15
    assert caught.value.category==category and caught.value.retryable is retryable
    assert 'never-log-this' not in capsys.readouterr().err


def test_legacy_review_is_required_and_migration_preserves_rows(tmp_path,monkeypatch):
    client,entries,ledger,inv,clock=setup_run(tmp_path,monkeypatch,count=10,completed=9)
    before=ledger.rows(BATCH)
    monkeypatch.delenv('PEOPLE_PUBLICATION_LEGACY_REVIEW_SHA256')
    with pytest.raises(ValueError,match='matching review digest'):run(client,ledger,inv,clock)
    assert ledger.rows(BATCH)==before and not client.mutations
    monkeypatch.setenv('PEOPLE_PUBLICATION_LEGACY_REVIEW_SHA256',ledger.legacy_review(BATCH,entries[0]['repo']))
    run(client,ledger,inv,clock)
    assert ledger.rows(BATCH)[:9]==before[:9]
    ledger.close();inv.close()


def test_retry_exhaustion_blocks_without_mass_failure(tmp_path,monkeypatch):
    client,entries,ledger,inv,clock=setup_run(tmp_path,monkeypatch,count=51)
    monkeypatch.setenv('PEOPLE_PUBLICATION_MAX_ATTEMPTS','2')
    client.failures=[dict(method='POST',point='trees',error=GitHubClient.reliability_error('service',503,True)) for _ in range(2)]
    with pytest.raises(GitHubError,match='budget'):run(client,ledger,inv,clock)
    progress=ledger.reliability_progress(BATCH,entries[0]['repo'])
    assert progress['blocked']==50 and progress['pending']==1 and progress['permanently_failed']==0
    assert all(r['status']=='pending' for r in ledger.rows(BATCH))
    ledger.close();inv.close()


def test_5000_records_five_styles_900_legacy_completed_and_restarts(tmp_path,monkeypatch):
    total=0;commits=0;faults=0
    for style in ('bw','diiivoy','diiivoycolor','rainier','signature'):
        folder=tmp_path/style
        client,entries,ledger,inv,clock=setup_run(folder,monkeypatch,count=1000,style=style,completed=900 if style=='bw' else 0)
        frozen=ledger.unit_binding(ledger.rows(BATCH));completed=[r for r in ledger.rows(BATCH) if r['status']=='published']
        origin=client.heads[REPOSITORIES[style]]
        client.failures=[dict(method='POST',point='trees',after=True,error=GitHubClient.reliability_error('network',retryable=True,ambiguous=True)),
            dict(method='POST',point='commits',after=True,error=GitHubClient.reliability_error('service',503,True,True)),
            dict(method='PATCH',point='ref',after=True,error=GitHubClient.reliability_error('network',retryable=True,ambiguous=True))]
        crashes=set()
        def crash(point):
            if point in {'tree_created','commit_created','branch_updated'} and point not in crashes:
                crashes.add(point);raise Restart()
        for attempt in range(10):
            try:run(client,ledger,inv,clock,crash);break
            except Restart:
                ledger.close();ledger=PublicationState(folder/'state')
        else:pytest.fail('did not converge')
        assert ledger.verified(BATCH) and ledger.unit_binding(ledger.rows(BATCH))==frozen
        assert [r for r in ledger.rows(BATCH) if r['path'] in {c['path'] for c in completed}]==completed
        image_commits=[x[1] for x in client.mutations if x[0]=='commit']
        assert len(image_commits)==len(set(image_commits))==(2 if style=='bw' else 20)
        assert not client.failures
        assert all(row['blob']==inv.lookup(style,row['path'])['sha'] for row in ledger.rows(BATCH))
        dispatch=next(i for i,(_,path,_) in enumerate(client.calls) if 'dispatches' in path)
        assert all(i<dispatch for i,(method,_,_) in enumerate(client.calls) if method=='PATCH')
        total+=len(entries);commits+=len(image_commits);faults+=len(crashes)+3
        ledger.close();inv.close()
    assert total==5000 and commits==82 and faults==30
