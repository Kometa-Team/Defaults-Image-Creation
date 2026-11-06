"""Real disposable Git remotes + SQLite, no production network or credentials."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'create_people_posters')]
from people_git_transport import GitTransport, NativePublication, canonical, digest, failure, SOURCE_MEMBERS
from people_publication_state import PublicationState
from publish_people_github import Publisher
from people_remote_inventory import blob_sha

BATCH='20261104T141304-52ea09305f3a';REPO='Kometa-Team/People-Images-bw'

class Crash(BaseException):pass
class Clock:
    value=1800000000.0
    def __call__(self):return self.value
    def sleep(self,t):self.value+=t

def bare(path,*args,data=None):
    env={k:v for k,v in os.environ.items() if not k.startswith(('GIT_','GH_','GITHUB_'))}
    env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT='0')
    p=subprocess.run(['git','--git-dir',str(path),'-c','protocol.file.allow=always',*args],input=data,capture_output=True,env=env)
    assert p.returncode==0, 'Offline fixture Git failure'
    return p.stdout

class API:
    token='fake-offline-no-network-913742'
    def __init__(self,remote):self.remote=remote;self.calls=[]
    def head(self,repo,branch):
        self.calls.append(('head',repo));sha=bare(self.remote,'rev-parse','refs/heads/'+branch).strip().decode()
        return sha,bare(self.remote,'rev-parse',sha+'^{tree}').strip().decode()

class Inventory:
    branch='master';repositories={'bw':REPO}
    def __init__(self,api,transport):self.client=api;self.transport=transport;self.files={}
    def refresh(self,style,force=False):
        head,tree=self.client.head(REPO,'master');self.transport.fetch(head);self.files=self.transport.tree(head)
        return head,tree
    def lookup(self,style,path):
        if path in self.files:return dict(self.files[path],path=path)
        if any(p.startswith(path+'/') for p in self.files):return dict(path=path,type='tree',mode='040000',sha='0'*40)

def setup(tmp,mp,count=101,completed=0,target=1_500_000_000,pack=1_850_000_000,sample_paths=None,style='bw'):
    from people_github import REPOSITORIES
    repo=REPOSITORIES[style]
    mp.setenv('PEOPLE_RELIABLE_PUBLISH','true');mp.setenv('PEOPLE_GITHUB_WRITE_INTERVAL','15')
    remote=tmp/'remote.git';remote.mkdir();bare(remote,'init','--bare')
    data=b'blob\nmark :1\ndata 4\nkeep\n'
    data+=b'commit refs/heads/master\nmark :2\ncommitter Fixture <fixture@example.invalid> 1800000000 +0000\ndata 8\ninitial\nM 100644 :1 unrelated.txt\n\n'
    bare(remote,'fast-import','--quiet',data=data)
    rows=[];images=tmp/'images';images.mkdir()
    for i in range(count):
        if sample_paths is None:
            content=(f'approved-real-Git-fixture-{i}-'+('é' if i%2 else 'a')).encode();path=images/f'{i}.jpg';path.write_bytes(content)
        else:path=sample_paths[i];content=path.read_bytes()
        rows.append(dict(style=style,repo=repo,path=f'A/Images/Person {i:05d} é.jpg',source=str(path),prepared=str(path),
            source_hash=hashlib.sha256(content).hexdigest(),published_hash=hashlib.sha256(content).hexdigest(),blob=blob_sha(content),person=f'Person {i:05d} é'))
    if completed:
        prior=bare(remote,'rev-parse','master').strip()
        stream=b'commit refs/heads/master\ncommitter Fixture <fixture@example.invalid> 1800000001 +0000\ndata 9\nexisting\nfrom '+prior+b'\n'
        for row in rows[:completed]:
            content=Path(row['prepared']).read_bytes();stream+=('M 100644 inline '+row['path']+'\n').encode()+f'data {len(content)}\n'.encode()+content+b'\n'
        bare(remote,'fast-import','--quiet',data=stream+b'\n')
    api=API(remote);head=api.head(repo,'master')[0]
    state=tmp/'state';ledger=PublicationState(state/'bw');ledger.plan(BATCH,'master',rows)
    for row in rows:ledger.baseline(BATCH,repo,row['path'],row['blob'] if rows.index(row)<completed else None)
    if completed:ledger.mark(BATCH,repo,[r['path'] for r in rows[:completed]],'published',head)
    clock=Clock();transport=GitTransport(tmp/'workspace',repo,'master',api.token,local_remote=remote)
    inventory=Inventory(api,transport);inventory.repositories={style:repo};p=Publisher(api,inventory,ledger,clock=clock,sleep=clock.sleep,jitter=lambda:0)
    ledger.reliability_schema();settings=p.reliable_settings()
    mp.setenv('PEOPLE_PUBLICATION_EXPECTED_HEAD',head)
    review=ledger.legacy_review(BATCH,repo);mp.setenv('PEOPLE_PUBLICATION_LEGACY_REVIEW_SHA256',review)
    control=ledger.reliability_control(BATCH,repo,head,settings,review)
    frozen=ledger.rows(BATCH,repo)
    plan=dict(styles={style:dict(unit=BATCH,entries_sha256=ledger.unit_binding(frozen),
        baselines={r['path']:r['blob'] if i<completed else None for i,r in enumerate(rows)},filename_case_conflicts=[])})
    raw=canonical(plan);(state/'reconciliation.json').write_bytes(raw)
    a=dict(version=2,backend='git-pack-v2',batch=BATCH,repo=repo,branch='master',origin_head=head,origin_review_sha256=review,
        reconciliation_sha256=hashlib.sha256(raw).hexdigest(),rows_binding=ledger.unit_binding(frozen),initial_head=head,
        initial_published_paths=[r['path'] for r in frozen if r['status']=='published'],
        published_rows_sha256=digest([r for r in frozen if r['status']=='published']),units_sha256=digest([]),
        settings_sha256=hashlib.sha256(control['settings'].encode()).hexdigest(),
        source_bindings={n:hashlib.sha256((ROOT/'create_people_posters'/n).read_bytes()).hexdigest() for n in SOURCE_MEMBERS},
        target_source_bytes=target,max_pack_bytes=pack,max_posters=0,git_timeout=7200,previous_approval='')
    readmes=[]
    def readme(batch,settings):
        assert all(r['status']=='published' for r in p.ledger.rows(batch));readmes.append(True);p.ledger.readme(batch,repo,'verified')
    p.publish_readme_reliable=readme
    return SimpleNamespace(p=p,t=transport,a=a,ledger=ledger,remote=remote,clock=clock,rows=frozen,readmes=readmes)

def run(x):return NativePublication(x.p,transport=x.t,contract=x.a,approval=digest(x.a)).publish(BATCH)
def windows(x):return [json.loads(r[0]) for r in x.ledger.db.execute('SELECT data FROM publication_git_windows ORDER BY number')]

def test_one_commit_per_window_and_receipts(tmp_path,monkeypatch):
    x=setup(tmp_path,monkeypatch,target=2000);run(x);ws=windows(x)
    assert len(ws)>1 and len(x.readmes)==1
    assert bare(x.remote,'rev-list','--count','master').strip()==str(1+len(ws)).encode()
    assert len(x.ledger.rows(BATCH))==101 and x.ledger.verified(BATCH)
    assert x.ledger.db.execute("SELECT count(*) FROM publication_units WHERE unit!='readme'").fetchone()[0]==0
    assert all(w['stage']=='completed' and w['pack_bytes']<=x.a['max_pack_bytes'] for w in ws)
    assert all(r['commit_sha'] in {w['tip'] for w in ws} for r in x.ledger.rows(BATCH))
    assert 'unrelated.txt' in x.t.tree(ws[-1]['tip'])
    before=bare(x.remote,'rev-list','--count','master');run(x);assert bare(x.remote,'rev-list','--count','master')==before

@pytest.mark.parametrize('point',['git_preparing','git_object_prepared','git_prepared','git_push_intent','git_push_ack','git_pushed','git_remote_verified','git_completed'])
def test_restart_at_every_boundary(tmp_path,monkeypatch,point):
    x=setup(tmp_path,monkeypatch,count=51);hit=[]
    def crash(stage):
        if stage==point and not hit:hit.append(stage);raise Crash()
    x.p.checkpoint_hook=crash
    with pytest.raises(Crash):run(x)
    x.ledger.close();x.ledger=PublicationState(tmp_path/'state/bw');x.p.ledger=x.ledger;x.p.checkpoint_hook=lambda s:None
    run(x);assert x.ledger.verified(BATCH) and len(windows(x))==1
    assert bare(x.remote,'rev-list','--count','master').strip()==b'2'
    assert x.ledger.db.execute('SELECT count(*) FROM publication_git_members WHERE object_sha!=""').fetchone()[0]==51

def test_ack_lost_and_transient_network_recovery(tmp_path,monkeypatch):
    x=setup(tmp_path,monkeypatch,count=4);original=x.t.push;calls=[]
    def push(parent,tip):
        calls.append((parent,tip))
        if len(calls)<3:raise failure('git_network',True,True)
        original(parent,tip);raise failure('git_network',True,True)
    x.t.push=push;run(x)
    assert len(calls)==3 and windows(x)[0]['attempts']==2 and x.clock.value>=1800000180
    assert bare(x.remote,'rev-list','--count','master').strip()==b'2'

def test_unknown_write_not_replayed_when_outcome_is_parent(tmp_path,monkeypatch):
    x=setup(tmp_path,monkeypatch,count=3);calls=[]
    def push(*args):calls.append(args);raise failure('git_rejected',False,True)
    x.t.push=push
    with pytest.raises(Exception):run(x)
    assert len(calls)==1 and windows(x)[0]['status']=='blocked'
    assert x.ledger.reliability_progress(BATCH,REPO)['blocked']==3

def test_oversized_pack_splits_before_push(tmp_path,monkeypatch):
    x=setup(tmp_path,monkeypatch,count=20,pack=10000);original=x.t.pack_size;splits=[]
    x.t.pack_size=lambda tip,parent:max(original(tip,parent),20000 if len(x.t.tree(tip))>10+len(x.t.tree(parent)) else 0)
    x.p.checkpoint_hook=lambda stage:splits.append(stage) if stage=='git_window_split' else None
    run(x);assert splits and len(windows(x))>1 and all(w['pack_bytes']<=10000 for w in windows(x))
    assert sum(len(x.ledger.git_members(BATCH,REPO,w['number'])) for w in windows(x))==20

@pytest.mark.parametrize('kind',['corrupt','case','remote','auth','config','alternate','helper','object_link'])
def test_integrity_and_security_rejections(tmp_path,monkeypatch,kind):
    x=setup(tmp_path,monkeypatch,count=3)
    if kind=='corrupt':Path(x.rows[0]['prepared']).write_bytes(b'corrupt')
    elif kind=='case':
        with x.ledger.db:x.ledger.db.execute('UPDATE publications SET path=? WHERE path=?',(x.rows[0]['path'].upper(),x.rows[1]['path']))
    elif kind=='remote':
        bare(x.remote,'update-ref','refs/heads/master','0'*40) # Delete only the disposable fixture ref.
    elif kind=='auth':x.a['published_rows_sha256']='0'*64
    elif kind=='config':
        bare(x.t.directory,'config','url.https://evil.invalid.insteadOf','https://github.com/')
        with pytest.raises(ValueError):GitTransport(x.t.root,REPO,'master',x.p.client.token,local_remote=x.remote)
        return
    elif kind=='alternate':
        (x.t.directory/'objects/info/alternates').write_text(str(tmp_path/'foreign-objects'))
        with pytest.raises(ValueError):GitTransport(x.t.root,REPO,'master',x.p.client.token,local_remote=x.remote)
        return
    elif kind=='helper':(x.t.root/'guard.py').write_text('raise SystemExit(0)\n')
    elif kind=='object_link':
        foreign=tmp_path/'foreign-objects';foreign.mkdir();link=x.t.directory/'objects/ab'
        try:link.symlink_to(foreign,target_is_directory=True)
        except OSError as error:
            if os.name!='nt' or getattr(error,'winerror',None)!=1314:raise
            import _winapi
            _winapi.CreateJunction(str(foreign),str(link))
            assert link.is_junction()
    with pytest.raises(Exception):run(x)
    assert not x.readmes

def test_1700_existing_receipts_are_unchanged(tmp_path,monkeypatch):
    x=setup(tmp_path,monkeypatch,count=1751,completed=1700)
    before=[r for r in x.ledger.rows(BATCH) if r['status']=='published'];run(x)
    assert [r for r in x.ledger.rows(BATCH) if r['path'] in set(x.a['initial_published_paths'])]==before
    assert bare(x.remote,'rev-list','--count','master').strip()==b'3'
    assert len(windows(x))==1 and x.ledger.reliability_progress(BATCH,REPO)['published']==1751

def test_fake_pat_absent_from_git_arguments_config_and_failures(tmp_path,monkeypatch,capsys):
    x=setup(tmp_path,monkeypatch,count=3);secret='fake-SECRET-746213-never-record'
    x.t._auth=secret;monkeypatch.setenv('GIT_TRACE',secret);monkeypatch.setenv('GITHUB_TOKEN',secret)
    original=subprocess.Popen;commands=[]
    def spy(args,**kwargs):
        assert secret not in repr(args);commands.append(args)
        env=kwargs['env'];assert 'GIT_TRACE' not in env and 'GITHUB_TOKEN' not in env
        return original(args,**kwargs)
    monkeypatch.setattr(subprocess,'Popen',spy);run(x)
    assert commands and secret not in (x.t.directory/'config').read_text()
    assert secret not in ''.join(capsys.readouterr())
    assert secret.encode() not in x.ledger.state.joinpath('publication_state.db').read_bytes()

def test_pre_push_guard_rejects_even_a_concurrent_rewind(tmp_path,monkeypatch):
    x=setup(tmp_path,monkeypatch,count=3,completed=1);original=x.t.git;rewound=[]
    ancestor=bare(x.remote,'rev-parse','master^').strip().decode()
    def race(*args,**kw):
        if args[0]=='push' and not rewound:
            rewound.append(True);bare(x.remote,'update-ref','refs/heads/master',ancestor)
        return original(*args,**kw)
    x.t.git=race
    with pytest.raises(Exception):run(x)
    assert rewound and bare(x.remote,'rev-parse','master').strip().decode()==ancestor
    assert windows(x)[0]['status']=='blocked'

def test_private_askpass_pipe_and_unknown_prompt_rejection(tmp_path,monkeypatch,capsys):
    secret='fake-private-PAT-99182766';t=GitTransport(tmp_path/'credential-test',REPO,'master',secret)
    env=t.environment(network=True)
    assert secret not in t.url and secret not in (t.directory/'config').read_text()
    env['GIT_TRACE']='injected-trace';assert 'GIT_TRACE' not in t.environment(network=True)
    env=t.environment(network=True)
    prompt="Password for 'https://x-access-token@github.com/"+REPO+".git': "
    result=subprocess.run([sys.executable,str(t.root/'askpass.py'),prompt],capture_output=True,env=env)
    assert result.returncode==0 and result.stdout==secret.encode()+os.linesep.encode() and not result.stderr
    result=subprocess.run([sys.executable,str(t.root/'askpass.py'),"Password for 'https://evil.invalid': "],capture_output=True,env=env)
    assert result.returncode!=0 and secret.encode() not in result.stdout+result.stderr
    fields=dict(line.split(b'=',1) for line in t.git('credential','fill',data=b'protocol=https\nhost=github.com\n\n',network=True).splitlines() if b'=' in line)
    assert fields[b'password']==secret.encode()
    assert secret not in ''.join(capsys.readouterr())

def test_retry_after_success_is_bounded_and_persisted(tmp_path,monkeypatch):
    x=setup(tmp_path,monkeypatch,count=3);original=x.t.fetch;failed=[]
    def unavailable(head):
        if bare(x.remote,'rev-list','--count','master').strip()==b'2' and len(failed)<3:
            failed.append(True);raise failure('git_network',True)
        return original(head)
    x.t.fetch=unavailable;run(x)
    assert windows(x)[0]['attempts']==3 and x.clock.value>=1800000420
    assert bare(x.remote,'rev-list','--count','master').strip()==b'2'

def test_canary_then_explicit_successor_authorization(tmp_path,monkeypatch):
    x=setup(tmp_path,monkeypatch,count=7);x.a['max_posters']=3;run(x)
    assert len([r for r in x.ledger.rows(BATCH) if r['status']=='published'])==3 and not x.readmes
    old_approval=digest(x.a);new=dict(x.a,previous_approval=old_approval,max_posters=0)
    new['initial_head']=x.p.client.head(REPO,'master')[0]
    prior=[r for r in x.ledger.rows(BATCH) if r['status']=='published']
    new['initial_published_paths']=[r['path'] for r in prior];new['published_rows_sha256']=digest(prior)
    x.a=new;run(x)
    assert x.ledger.verified(BATCH) and len(windows(x))==2
    assert [r for r in x.ledger.rows(BATCH) if r['path'] in new['initial_published_paths']]==prior

def test_receipt_transaction_rolls_back_after_mid_update_failure(tmp_path,monkeypatch):
    x=setup(tmp_path,monkeypatch,count=4)
    stop=x.rows[1]['path'].replace("'","''")
    x.ledger.db.execute("CREATE TRIGGER interrupt_receipts BEFORE UPDATE ON publications WHEN NEW.path='"+stop+"' BEGIN SELECT RAISE(ABORT,'offline injected interruption'); END")
    with pytest.raises(Exception):run(x)
    assert all(r['status']=='pending' for r in x.ledger.rows(BATCH))
    assert x.ledger.db.execute('SELECT head FROM publication_controls').fetchone()[0]==x.a['initial_head']
    assert bare(x.remote,'rev-list','--count','master').strip()==b'2'
    x.ledger.db.execute('DROP TRIGGER interrupt_receipts');x.ledger.db.commit()
    run(x);assert x.ledger.verified(BATCH) and bare(x.remote,'rev-list','--count','master').strip()==b'2'

def test_noexec_workspace_is_rejected(tmp_path,monkeypatch):
    access=os.access
    monkeypatch.setattr(os,'access',lambda p,mode:False if Path(p).name=='pre-push' else access(p,mode))
    with pytest.raises(ValueError):GitTransport(tmp_path/'noexec',REPO,'master','fake-noexec-credential')

def test_unknown_write_with_unavailable_outcome_never_becomes_retryable(tmp_path,monkeypatch):
    x=setup(tmp_path,monkeypatch,count=3);calls=[];real_head=x.t.remote_head;reads=[]
    def push(*args):calls.append(args);raise failure('git_rejected',False,True)
    def head():
        if calls and not reads:reads.append(True);raise failure('git_network',True)
        return real_head()
    x.t.push=push;x.t.remote_head=head
    with pytest.raises(ValueError):run(x)
    assert len(calls)==1 and windows(x)[0]['status']=='blocked'

def test_final_artwork_audit_rate_limit_uses_durable_readme_budget(tmp_path,monkeypatch):
    x=setup(tmp_path,monkeypatch,count=3);refresh=x.p.inventory.refresh;failed=[]
    def limited(*args,**kwargs):
        if not failed:
            failed.append(True);error=failure('rate_limit',True);error.status=429
            error.diagnostic=dict(rate_limit=dict(retry_after_seconds=3600));raise error
        return refresh(*args,**kwargs)
    x.p.inventory.refresh=limited;run(x)
    state=x.ledger.unit(BATCH,REPO,'readme',[])
    assert state['attempts']==1 and x.clock.value>=1800003600 and x.ledger.verified(BATCH)
    assert bare(x.remote,'rev-list','--count','master').strip()==b'2'

def test_native_readme_handoff_restart_preserves_correlation(tmp_path,monkeypatch):
    x=setup(tmp_path,monkeypatch,count=3);dispatched=[];identity='a'*32
    def helper(batch,settings):
        status=x.ledger.readme_state(batch,REPO)
        if status['status']!='waiting':
            dispatched.append(identity);x.ledger.readme(batch,REPO,'waiting',details=dict(dispatch_id=identity));raise Crash()
        assert status['details']['dispatch_id']==identity
        x.ledger.readme(batch,REPO,'verified',details=status['details'])
    x.p.publish_readme_reliable=helper
    with pytest.raises(Crash):run(x)
    run(x);assert dispatched==[identity] and x.ledger.verified(BATCH)
    assert bare(x.remote,'rev-list','--count','master').strip()==b'2'

def test_credential_bearing_remote_rejection_is_ram_only(tmp_path,monkeypatch,capsys):
    x=setup(tmp_path,monkeypatch,count=3);secret='fake-remote-secret-DO-NOT-PERSIST-634812'
    original=subprocess.Popen
    def hostile(args,**kw):
        assert secret not in repr(args)
        if 'push' in args:
            # A failed transport child emits an arbitrary credential-bearing error.
            kw['env']=dict(kw['env'],OFFLINE_FAKE_ERROR=secret)
            args=[sys.executable,'-c','import os,sys;sys.stderr.write("fatal: rejected "+os.environ["OFFLINE_FAKE_ERROR"]);sys.exit(1)']
        return original(args,**kw)
    monkeypatch.setattr(subprocess,'Popen',hostile)
    with pytest.raises(Exception) as caught:run(x)
    assert secret not in str(caught.value)+''.join(capsys.readouterr())
    assert all(secret.encode() not in p.read_bytes() for p in x.t.root.rglob('*') if p.is_file())
    assert secret.encode() not in (x.ledger.state/'publication_state.db').read_bytes()

@pytest.mark.parametrize('style',['diiivoy','diiivoycolor','rainier','signature'])
def test_other_styles_use_same_versioned_backend_offline_only(tmp_path,monkeypatch,style):
    x=setup(tmp_path,monkeypatch,count=3,style=style);run(x)
    assert x.ledger.verified(BATCH) and len(windows(x))==1
    assert {r['style'] for r in x.ledger.rows(BATCH)}=={style}
    assert bare(x.remote,'rev-list','--count','master').strip()==b'2'

def test_tampered_prepared_intent_and_rest_fallback_are_rejected(tmp_path,monkeypatch):
    x=setup(tmp_path,monkeypatch,count=3)
    x.p.checkpoint_hook=lambda stage:(_ for _ in ()).throw(Crash()) if stage=='git_prepared' else None
    with pytest.raises(Crash):run(x)
    x.p.checkpoint_hook=lambda stage:None
    with pytest.raises(ValueError):x.p.publish(BATCH)  # REST is disabled once native ownership is registered.
    window=windows(x)[0];window['commit_payload']['message']='unauthorized intent\n'
    x.ledger.git_window(BATCH,REPO,0,window)
    with pytest.raises(ValueError):run(x)
    assert bare(x.remote,'rev-list','--count','master').strip()==b'1'

def test_between_push_pacing_survives_process_restart(tmp_path,monkeypatch):
    x=setup(tmp_path,monkeypatch,count=4,target=70);crashed=[];push=x.t.push;times=[]
    def record(*args):times.append(x.clock());return push(*args)
    x.t.push=record
    def stop(stage):
        if stage=='git_completed' and not crashed:crashed.append(True);raise Crash()
    x.p.checkpoint_hook=stop
    with pytest.raises(Crash):run(x)
    x.p.checkpoint_hook=lambda s:None;run(x)
    assert len(times)>1 and all(b-a>=60 for a,b in zip(times,times[1:]))

def test_partial_fetch_keeps_unchanged_historical_blobs_missing(tmp_path,monkeypatch):
    x=setup(tmp_path,monkeypatch,count=4,completed=1)
    bare(x.remote,'config','uploadpack.allowFilter','true')
    x.t.git('config','remote.origin.promisor','true')
    x.t.git('config','remote.origin.partialclonefilter','blob:none')
    def partial(expected):
        assert x.t.remote_head()==expected
        x.t.git('fetch','--filter=blob:none','--depth=1','--no-tags','origin','refs/heads/master',network=True)
        assert x.t.git('rev-parse','FETCH_HEAD').strip().decode()==expected
    x.t.fetch=partial
    partial(x.a['initial_head'])
    historical=x.rows[0]['blob']
    with pytest.raises(Exception):x.t.git('cat-file','-e',historical)
    run(x)
    assert x.ledger.verified(BATCH)
    with pytest.raises(Exception):x.t.git('cat-file','-e',historical)
    assert bare(x.remote,'rev-list','--count','master').strip()==b'3'

def test_missing_new_object_cannot_use_inherited_blob_exception(tmp_path,monkeypatch):
    x=setup(tmp_path,monkeypatch,count=3)
    x.p.checkpoint_hook=lambda stage:(_ for _ in ()).throw(Crash()) if stage=='git_object_prepared' else None
    with pytest.raises(Crash):run(x)
    sha=x.rows[0]['blob'];(x.t.directory/'objects'/sha[:2]/sha[2:]).unlink()
    x.p.checkpoint_hook=lambda stage:None
    with pytest.raises(Exception):run(x)
    assert bare(x.remote,'rev-list','--count','master').strip()==b'1'

def test_real_push_interrupted_during_received_pack_resumes(tmp_path,monkeypatch):
    import signal,threading,time
    sample=tmp_path/'synthetic-transfer-fixture.jpg';sample.write_bytes(os.urandom(64*1024**2))
    x=setup(tmp_path,monkeypatch,count=1,sample_paths=[sample]);stop=threading.Event();observed=[]
    def interrupt_transfer():
        while not stop.wait(0.002):
            for path in (x.remote/'objects').glob('tmp_objdir-incoming-*/**/*'):
                try:ready=path.is_file() and path.stat().st_size>32768
                except FileNotFoundError:continue
                if ready:
                    observed.append(True)
                    if os.name == "nt":signal.raise_signal(signal.SIGINT)
                    else:os.kill(os.getpid(),signal.SIGINT)
                    return
    thread=threading.Thread(target=interrupt_transfer,daemon=True);thread.start()
    try:
        with pytest.raises(KeyboardInterrupt):run(x)
    finally:stop.set();thread.join(timeout=5)
    assert observed and windows(x)[0]['stage']=='push_intent'
    run(x);assert x.ledger.verified(BATCH)
    assert bare(x.remote,'rev-list','--count','master').strip()==b'2'


def config_transport(tmp_path):
    remote=tmp_path/'config-remote.git';remote.mkdir();bare(remote,'init','--bare')
    return GitTransport(tmp_path/'config-workspace',REPO,'master','fake-config-test-credential',local_remote=remote),remote


def test_git_init_symlink_capability_false_is_accepted(tmp_path):
    transport,remote=config_transport(tmp_path)
    transport.git('config','core.symlinks','false')
    resumed=GitTransport(transport.root,REPO,'master','fake-config-test-credential',local_remote=remote)
    assert resumed.git('config','--get','core.symlinks').strip()==b'false'


@pytest.mark.parametrize('key,value',[
    ('core.symlinks','true'),('core.symlinks','yes'),('core.symlinks','0'),
    ('core.symlinks','nonsense'),('core.symlinks',''),
    ('credential.helper','!unsafe-helper'),
    ('http.extraHeader','AUTHORIZATION: fake-config-test-credential'),
    ('remote.origin.url','https://evil.invalid/repository.git'),
    ('remote.origin.pushurl','https://evil.invalid/repository.git'),
    ('url.https://evil.invalid/.insteadOf','https://github.com/'),
    ('core.hooksPath','unsafe-hooks'),('core.sshCommand','unsafe-helper'),
    ('filter.unsafe.clean','unsafe-helper'),
])
def test_symlink_setting_does_not_expand_config_authority(tmp_path,capsys,key,value):
    transport,remote=config_transport(tmp_path)
    transport.git('config',key,value)
    with pytest.raises(ValueError,match='Native Git approval, artifact or checkpoint integrity mismatch'):
        GitTransport(transport.root,REPO,'master','fake-config-test-credential',local_remote=remote)
    assert 'fake-config-test-credential' not in ''.join(capsys.readouterr())
