"""Offline safety tests for the five-style control plane; repositories are fixtures."""
import hashlib
import errno
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import threading
import time

import pytest
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bulk_git_sync as sync
import bulk_reconcile as publication
import bulk_source as source
import bulk_regenerate as cli
import bulk_regeneration_plan as plan
import bulk_regeneration_state as state


def test_disk_full_during_partial_poster_write_preserves_existing_file(tmp_path,monkeypatch):
    target=tmp_path/'existing.jpg'
    target.write_bytes(b'previous verified output')
    before=snapshot(tmp_path)
    real=cli.tempfile.NamedTemporaryFile
    class DiskFull:
        def __init__(self,handle):self.handle=handle;self.name=handle.name
        def __enter__(self):self.handle.__enter__();return self
        def __exit__(self,*args):return self.handle.__exit__(*args)
        def write(self,payload):
            self.handle.write(payload[:32])
            raise OSError(errno.ENOSPC,'No space left on device')
    monkeypatch.setattr(cli.tempfile,'NamedTemporaryFile',lambda *a,**kw:DiskFull(real(*a,**kw)))
    with Image.new('RGB',(2000,3000)) as image:
        with pytest.raises(OSError) as caught:cli.atomic_poster(image,target,'signature')
    assert caught.value.errno==errno.ENOSPC
    assert snapshot(tmp_path)==before


def command(root,*args):
    return subprocess.run(['git','-c','core.autocrlf=false','-c','commit.gpgsign=false',
        '-c','user.name=Fixture','-c','user.email=fixture@example.invalid','-C',str(root),*args],
        check=True,capture_output=True).stdout.decode().strip()


def png(root,relative):
    path=root/relative;path.parent.mkdir(parents=True,exist_ok=True)
    with Image.new('RGBA',(16,24),(120,60,80,100)) as image:image.save(path)
    return path


@pytest.fixture
def repository(tmp_path,monkeypatch):
    remote=tmp_path/'remote.git';remote.mkdir()
    command(remote,'init','--bare','--initial-branch=master')
    author=tmp_path/'author';author.mkdir();command(author,'init','--initial-branch=master')
    for path in source.KNOWN_INPUTS:png(author,path)
    (author/'README.md').write_text('fixture\n')
    command(author,'add','.');command(author,'commit','-m','initial fixture')
    command(author,'remote','add','origin',remote.as_uri());command(author,'push','-u','origin','master')
    local=tmp_path/'source'
    command(tmp_path,'clone',remote.as_uri(),str(local))
    monkeypatch.setattr(source,'SOURCE_URL',remote.as_uri())
    monkeypatch.setattr(sync,'SOURCE_URL',remote.as_uri())
    return remote,author,local


def snapshot(root):
    return {p.relative_to(root).as_posix():(p.stat().st_mtime_ns,hashlib.sha256(p.read_bytes()).hexdigest())
            for p in root.rglob('*') if p.is_file()}


def test_explicit_canary_selects_exact_paths_and_rejects_missing_or_duplicate(repository):
    _,_,root=repository
    paths=list(source.KNOWN_INPUTS[:2])
    rows,summary=plan.inventory(root,state.STYLES,canary=2,canary_paths=paths)
    assert [row['relative'] for row in rows if row['selected']]==paths
    assert summary['planned_outputs']==10
    for bad in ([paths[0],paths[0]],[paths[0],'Z/Images/Missing.png']):
        with pytest.raises(ValueError):plan.inventory(root,state.STYLES,canary=2,canary_paths=bad)


def test_initial_partial_clone_and_incremental_sync_work_with_rest_unavailable(repository,tmp_path,monkeypatch):
    from types import SimpleNamespace
    import requests
    remote,author,_=repository
    command(remote,'config','uploadpack.allowFilter','true')
    # A large removed historical blob must remain absent after current checkout.
    old=author/'old-payload.bin';old.write_bytes(b'historical payload'*65536)
    command(author,'add','.');command(author,'commit','-m','old payload')
    old_oid=command(author,'rev-parse','HEAD:old-payload.bin')
    old.unlink();command(author,'add','-u');command(author,'commit','-m','remove old payload')
    command(author,'push','origin','master')
    monkeypatch.setattr(sync.shutil,'disk_usage',lambda *_:SimpleNamespace(free=100*1024**3))
    monkeypatch.setattr(requests.sessions.Session,'request',lambda *_a,**_k:pytest.fail('REST API is unavailable'))
    destination=tmp_path/'fresh-native'
    result=sync.initial_clone(destination,tmp_path,source_budget_gib=1)
    assert result['commit']==command(author,'rev-parse','HEAD')
    assert result['initial_clone']['rest_requests']==0
    assert result['initial_clone']['png_count']==8
    assert result['initial_clone']['source_bytes']==sum((destination/p).stat().st_size for p in source.KNOWN_INPUTS)
    assert source.audit(destination)['verified']==8
    packed=''.join(command(destination,'verify-pack','-v',str(index)) for index in (destination/'.git/objects/pack').glob('*.idx'))
    assert old_oid not in packed
    png(author,'Z/Images/Added person.png');command(author,'add','.');command(author,'commit','-m','new current PNG')
    command(author,'push','origin','master')
    assert sync.synchronize(destination)['source_files_updated']
    assert (destination/'Z/Images/Added person.png').is_file()


def test_initial_clone_refuses_capacity_before_network_and_preserves_existing_data(tmp_path,monkeypatch):
    from types import SimpleNamespace
    destination=tmp_path/'new-source'
    monkeypatch.setattr(sync.shutil,'disk_usage',lambda *_:SimpleNamespace(free=1024))
    monkeypatch.setattr(sync.subprocess,'run',lambda *_a,**_k:pytest.fail('No network allowed before capacity admission'))
    with pytest.raises(ValueError,match='free'):sync.initial_clone(destination,tmp_path)
    assert not destination.exists()
    destination.mkdir();(destination/'keep.bin').write_bytes(b'preserve')
    with pytest.raises(ValueError,match='new directory'):sync.initial_clone(destination,tmp_path)
    assert (destination/'keep.bin').read_bytes()==b'preserve'


def test_original_api_rate_limit_error_means_refused_long_wait_not_elapsed_retry_time():
    from types import SimpleNamespace
    from github_inventory_core import get_json,GitHubError
    calls=[]
    response=SimpleNamespace(status_code=403,headers={'X-RateLimit-Remaining':'0',
        'X-RateLimit-Reset':str(time.time()+3600)},
        iter_content=lambda *_:[b'{"message":"API rate limit exceeded"}'],close=lambda:None)
    session=SimpleNamespace(get=lambda url,**_:(calls.append(url) or response))
    with pytest.raises(GitHubError,match='five-minute limit') as caught:
        get_json(session,'https://api.github.com/repos/fixture/git/trees/subtree',
            sleep=lambda *_:pytest.fail('The excessive delay must be rejected without sleeping'))
    assert caught.value.status==403
    assert len(calls)==1


@pytest.mark.skipif(os.name!='posix',reason='Linux cgroup admission')
def test_eight_worker_admission_keeps_memory_and_upper_bounds(monkeypatch):
    values={'/proc/meminfo':'MemAvailable: 67108864 kB',
        '/sys/fs/cgroup/memory.max':str(24*1024**3),
        '/sys/fs/cgroup/memory.current':str(1024**3)}
    class Probe:
        def __init__(self,path):self.path=path
        def exists(self):return self.path in values
        def read_text(self):return values[self.path]
    monkeypatch.setattr(cli,'Path',Probe)
    assert cli._memory_budget(8)['workers']==8
    for bad in (0,9):
        with pytest.raises(ValueError):cli._memory_budget(bad)
    values['/sys/fs/cgroup/memory.max']=str(8*1024**3)
    with pytest.raises(ValueError,match='RAM'):cli._memory_budget(8)


def test_source_audit_verifies_git_bytes_and_all_eight(repository):
    _,_,local=repository
    before=snapshot(local)
    report=source.audit(local)
    assert report['total']==report['verified']==8 and report['failed']==0
    assert all(v=='verified' for v in report['known_inputs'].values())
    assert snapshot(local)==before


def test_corrupt_committed_png_reported_without_modifying(repository):
    _,author,local=repository
    path=author/source.KNOWN_INPUTS[0];data=bytearray(path.read_bytes());data[data.index(b'IDAT')+5]^=1;path.write_bytes(data)
    command(author,'add','.');command(author,'commit','-m','committed corrupt fixture');command(author,'push')
    sync.synchronize(local)
    before=snapshot(local);report=source.audit(local)
    assert report['failed']==1 and report['errors'][0]['path']==source.KNOWN_INPUTS[0]
    assert report['known_inputs'][source.KNOWN_INPUTS[0]]=='failed_or_missing'
    assert snapshot(local)==before


def test_audit_reopens_and_fully_decodes(repository,monkeypatch):
    _,_,local=repository;calls=[];real=Image.Image.load
    def load(image,*args,**kwargs):
        calls.append(image.format);return real(image,*args,**kwargs)
    monkeypatch.setattr(Image.Image,'load',load)
    assert source.audit(local)['failed']==0
    assert len(calls)>=8


def test_incremental_sync_fast_forward_and_rename(repository):
    _,author,local=repository
    old=command(local,'rev-parse','HEAD')
    unchanged=local/source.KNOWN_INPUTS[1];before=unchanged.stat().st_mtime_ns
    command(author,'mv',source.KNOWN_INPUTS[0],'B/Images/New Name.png')
    command(author,'commit','-m','rename fixture');command(author,'push')
    result=sync.synchronize(local)
    assert result['previous']==old and result['source_files_updated']
    assert result['changes']==[dict(status='R100',old_path=source.KNOWN_INPUTS[0],path='B/Images/New Name.png')]
    assert unchanged.stat().st_mtime_ns==before


def test_dirty_source_refuses_sync_before_fetch(repository):
    _,_,local=repository
    (local/'unexpected').write_text('preserve')
    head=command(local,'rev-parse','HEAD')
    with pytest.raises(ValueError,match='not clean'):sync.synchronize(local)
    assert command(local,'rev-parse','HEAD')==head


def test_unexpected_remote_url_refused(repository):
    _,_,local=repository;command(local,'remote','set-url','origin','https://example.invalid/unknown.git')
    with pytest.raises(ValueError,match='Unexpected'):source.sync_status(local)


def test_history_rewrite_refused_without_checkout(repository):
    remote,author,local=repository
    first=command(local,'rev-parse','HEAD')
    png(author,'N/Images/New.png');command(author,'add','.');command(author,'commit','-m','second');command(author,'push')
    sync.synchronize(local);head=command(local,'rev-parse','HEAD')
    command(author,'reset','--hard',first);command(author,'push','--force')
    with pytest.raises(ValueError):sync.synchronize(local)
    assert command(local,'rev-parse','HEAD')==head and (local/'N/Images/New.png').exists()


def test_persistent_pin_blocks_checkout_but_allows_metadata_fetch(repository,tmp_path):
    _,author,local=repository
    report=tmp_path/'audit.json';report.write_text(json.dumps(source.audit(local)))
    pin=sync.pin_source(local,'fixture-batch',report)
    head=command(local,'rev-parse','HEAD');before=(local/source.KNOWN_INPUTS[0]).read_bytes()
    png(author,'N/Images/New.png');command(author,'add','.');command(author,'commit','-m','new daily source');command(author,'push')
    result=sync.synchronize(local,fetch_only=True)
    assert result['deferred'] and result['fetched']!=head
    with pytest.raises(ValueError,match='persistently pinned'):sync.synchronize(local)
    assert command(local,'rev-parse','HEAD')==head
    assert (local/source.KNOWN_INPUTS[0]).read_bytes()==before
    assert source.validate_pin(local,local/'.git/people-bulk-pins/fixture-batch.json')['pin_sha256']==pin['pin_sha256']


def test_pin_requires_actual_readonly_mount_when_requested(repository,tmp_path):
    _,_,local=repository
    report=tmp_path/'audit.json';report.write_text(json.dumps(source.audit(local)))
    sync.pin_source(local,'fixture',report)
    with pytest.raises(ValueError,match='read-only'):
        source.validate_pin(local,local/'.git/people-bulk-pins/fixture.json',True)


def test_readonly_sync_status_writes_nothing(repository):
    _,_,local=repository;before=snapshot(local)
    value=source.sync_status(local)
    assert value['read_only'] and snapshot(local)==before


def test_source_commit_binding_rejects_changed_payload(repository):
    _,_,local=repository
    path=local/source.KNOWN_INPUTS[0];path.write_bytes(b'changed')
    with pytest.raises(ValueError,match='pinned Git blob'):source.scan_sources(local)


def test_source_pin_rejects_mutated_metadata(repository,tmp_path):
    _,_,local=repository
    report=tmp_path/'audit.json';report.write_text(json.dumps(source.audit(local)))
    sync.pin_source(local,'fixture',report)
    path=local/'.git/people-bulk-pins/fixture.json';value=json.loads(path.read_text());value['source']['commit']='a'*40;path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='digest'):source.validate_pin(local,path)


@pytest.fixture
def staged(tmp_path,repository,monkeypatch):
    remote,author,transparent=repository
    command(transparent,'remote','set-url','origin',publication.SOURCE_URL)
    destination=tmp_path/'destination';destination.mkdir();command(destination,'init','--initial-branch=master')
    png_path=destination/'B/Images/Bo Derek.jpg';png_path.parent.mkdir(parents=True)
    with Image.new('L',(2000,3000),10) as image:image.save(png_path,'JPEG')
    (destination/'README.md').write_text('old metadata')
    command(destination,'add','.');command(destination,'commit','-m','baseline')
    command(destination,'remote','add','origin','https://github.com/Kometa-Team/People-Images-bw.git')
    head=command(destination,'rev-parse','HEAD');command(destination,'update-ref','refs/remotes/origin/master',head)
    monkeypatch.setattr(publication,'observe',lambda root:command(root,'rev-parse','HEAD'))
    root=tmp_path/'batch'
    renderer=dict(fixture='1');source_git=plan.git_state(transparent)
    monkeypatch.setattr(plan,'renderer_version',lambda:renderer)
    db,manifest=cli._initial(root,transparent,['bw'],renderer,source_git,None,1,1)
    item=dict(number=0,relative=source.KNOWN_INPUTS[0],name='Bo Derek',source_hash=state.sha(transparent/source.KNOWN_INPUTS[0]),
        selected=True,eligible=True,issue='',issue_kind='',attributes={})
    summary=dict(input_total=1,eligible_image_count=1,selected_input_total=1)
    manifest=cli._commit_inventory(root,db,manifest,[item],summary,plan.estimate_storage([item],['bw'],{}))
    target=root/'bw/B/Images/Bo Derek.jpg'
    with Image.new('L',(2000,3000),100) as image:details=cli.atomic_poster(image,target,'bw')
    receipt=dict(batch_id=manifest['batch_id'],renderer_id=state.canonical(renderer),source=item['relative'],
        source_sha256=item['source_hash'],output='bw/B/Images/Bo Derek.jpg',style='bw',**details)
    rp=cli.receipt_path(root,receipt['output']);rp.parent.mkdir(parents=True);state.atomic_json(rp,receipt)
    cli._completed(db,0,[receipt])
    with db:state.set_meta(db,state='completed')
    db.close()
    baseline=publication.capture_baseline(destination,'bw',source_git['head'],state.canonical(renderer))
    return root,transparent,destination,baseline


def reconciliation(staged):
    root,transparent,destination,baseline=staged
    return publication.reconcile(root,transparent,destination,baseline,fetch=False)


def test_publication_clean_plan_is_readonly_and_not_authorized(staged):
    root,transparent,destination,_=staged
    before=[snapshot(p) for p in (root,transparent,destination)]
    value=reconciliation(staged)
    assert not value['publication_authorized'] and not value['baseline_refresh_required']
    assert value['files']['count']==1 and value['excluded']['count']==0
    assert before==[snapshot(p) for p in (root,transparent,destination)]


def test_readme_only_descendant_is_allowed(staged):
    _,_,destination,_=staged
    (destination/'README.md').write_text('automation update');command(destination,'add','.');command(destination,'commit','-m','metadata')
    command(destination,'update-ref','refs/remotes/origin/master',command(destination,'rev-parse','HEAD'))
    assert not reconciliation(staged)['baseline_refresh_required']


@pytest.mark.parametrize('path',['.github/workflows/unknown.yml','B/Images/Bo Derek.jpg'])
def test_changed_and_reverted_history_never_disappears(staged,path):
    _,_,destination,_=staged
    original=command(destination,'rev-parse','HEAD')
    changed=destination/path;changed.parent.mkdir(parents=True,exist_ok=True);changed.write_bytes(b'unauthorized fixture')
    command(destination,'add','.');command(destination,'commit','-m','change')
    command(destination,'revert','--no-edit','HEAD')
    command(destination,'update-ref','refs/remotes/origin/master',command(destination,'rev-parse','HEAD'))
    assert publication.tree(destination,original)==publication.tree(destination,'HEAD')
    value=reconciliation(staged)
    assert value['baseline_refresh_required']
    assert value['blockers']['count'] or value['excluded']['count']


def test_newer_daily_output_is_excluded(staged):
    _,_,destination,_=staged
    with Image.new('L',(2000,3000),200) as image:image.save(destination/'B/Images/Bo Derek.jpg','JPEG')
    command(destination,'add','.');command(destination,'commit','-m','legitimate newer daily output')
    command(destination,'update-ref','refs/remotes/origin/master',command(destination,'rev-parse','HEAD'))
    value=reconciliation(staged)
    assert value['files']['count']==0 and value['excluded']['count']==1
    assert 'destination_history_changed_since_baseline' in publication.unpack(value['excluded'])[0]['reasons']


def test_source_change_and_revert_requires_catchup_review(staged):
    _,transparent,_,_=staged
    path=transparent/source.KNOWN_INPUTS[0];path.write_bytes(b'changed')
    command(transparent,'add','.');command(transparent,'commit','-m','daily source changed')
    command(transparent,'revert','--no-edit','HEAD')
    command(transparent,'update-ref','refs/remotes/origin/master',command(transparent,'rev-parse','HEAD'))
    value=reconciliation(staged)
    assert value['source_changes']['count']==0 and value['excluded']['count']==1


def test_reconciliation_rejects_rewritten_baseline(staged):
    _,_,destination,_=staged
    command(destination,'checkout','--orphan','rewritten')
    command(destination,'commit','-m','unrelated root')
    command(destination,'update-ref','refs/remotes/origin/master',command(destination,'rev-parse','HEAD'))
    with pytest.raises(ValueError):reconciliation(staged)


def test_failed_style_or_tampered_jpeg_cannot_be_published(staged):
    root,_,_,_=staged
    (root/'bw/B/Images/Bo Derek.jpg').write_bytes(b'tampered')
    with pytest.raises(ValueError,match='receipt'):reconciliation(staged)


def test_private_payload_requires_exact_authorization_and_detects_remote_drift(staged,tmp_path,monkeypatch):
    value=reconciliation(staged)
    with pytest.raises(ValueError,match='authorization'):publication.stage_payload(value,tmp_path/'payload','wrong')
    real=publication.git
    def remote(root,*args,**kwargs):
        return b'1'*40+b'\trefs/heads/master\n' if args[0]=='ls-remote' else real(root,*args,**kwargs)
    monkeypatch.setattr(publication,'git',remote)
    with pytest.raises(ValueError,match='advanced'):publication.stage_payload(value,tmp_path/'payload','STAGE:'+value['plan_sha256'])


def test_private_payload_resume_preserves_sources_and_never_replaces_production(staged,tmp_path,monkeypatch):
    value=reconciliation(staged);root,transparent,destination,_=staged
    before=[snapshot(p) for p in (root,transparent,destination)]
    real=publication.git
    def remote(path,*args,**kwargs):
        if args[0]=='ls-remote':
            head=value['source_head'] if Path(path)==transparent else value['destination_head']
            return (head+'\trefs/heads/master\n').encode()
        return real(path,*args,**kwargs)
    monkeypatch.setattr(publication,'git',remote)
    target=tmp_path/'private-payload'
    assert publication.stage_payload(value,target,'STAGE:'+value['plan_sha256'])['files']==1
    poster=target/'posters/B/Images/Bo Derek.jpg';mtime=poster.stat().st_mtime_ns
    publication.stage_payload(value,target,'STAGE:'+value['plan_sha256'])
    assert poster.stat().st_mtime_ns==mtime
    assert before==[snapshot(p) for p in (root,transparent,destination)]
    assert not json.loads((target/'READY.json').read_text())['publication_authorized']


def test_resume_skips_unchanged_sqlite_output_writes(tmp_path,monkeypatch):
    root=tmp_path/'fixture';source_dir=tmp_path/'source';source_dir.mkdir()
    db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row;cli._schema(db)
    rows=[]
    for number in range(500):
        rows.append(dict(number=number,relative=str(number),selected=True,eligible=True,source_hash='hash'))
        db.execute('INSERT INTO outputs VALUES(?,?,?,?,?,?,?,?,?)',(number,'bw',str(number),'pending',None,0,'',0,1))
    db.commit();traces=[];db.set_trace_callback(traces.append)
    monkeypatch.setattr(cli,'sha',lambda _: 'hash');monkeypatch.setattr(cli,'validated_receipt',lambda *args:None)
    cli._resume_reconcile(root,db,dict(renderer={},batch_id='fixture',items=rows,source=str(source_dir),styles=['bw']),False)
    assert not [sql for sql in traces if sql.startswith('UPDATE outputs')]
    db.close()


def test_semantic_bw_mode_and_collection_contract_remain_distinct():
    from create_people_poster import Renderer,COLLECTION_CONFIG,FONTS
    assert 'bw' not in COLLECTION_CONFIG and FONTS[0]=='Comfortaa-Medium.ttf'
    assert Renderer.bw_label.__name__=='bw_label'
    assert set(state.STYLES)=={'bw','diiivoy','diiivoycolor','rainier','signature'}


def test_source_and_workflow_fingerprint_changes_still_fail_closed(tmp_path,monkeypatch):
    from test_bulk_regenerate import FakeRenderer,png as fixture_png
    source_dir=tmp_path/'source';fixture_png(source_dir)
    root=tmp_path/'batch'
    monkeypatch.setattr(plan,'renderer_version',lambda:dict(fixture='old'))
    monkeypatch.setattr(plan,'git_state',lambda _:dict(head=None,status=None,root=None))
    monkeypatch.setattr(plan,'require_space',lambda *a:10**12)
    monkeypatch.setattr(cli,'_renderer',lambda:FakeRenderer())
    assert cli.main(['--source',str(source_dir),'--output',str(root),'--styles','bw,diiivoy'])==0
    monkeypatch.setattr(plan,'renderer_version',lambda:dict(fixture='changed'))
    before={p:state.sha(p) for p in root.glob('*/*/Images/*.jpg')}
    assert cli.main(['--resume','--output',str(root)])==1
    assert before=={p:state.sha(p) for p in before}


@pytest.mark.skipif(os.name!='posix',reason='POSIX SIGTERM contract; Windows SIGINT has separate tests')
def test_sigterm_during_preflight_saves_interrupted_state(tmp_path):
    helper=tmp_path/'controlled.py'
    helper.write_text('import sys,time,signal,os\n'
        f'sys.path.insert(0,{str(Path(cli.__file__).parent)!r})\n'
        'import bulk_regenerate as c,bulk_regeneration_plan as p\n'
        'from pathlib import Path\n'
        'p.renderer_version=lambda:{}\np.git_state=lambda _:dict(head=None,status=None,root=None)\n'
        'p.require_space=lambda *a:10**12\n'
        'def inventory(*a,**kw): os.kill(os.getpid(),signal.SIGTERM);time.sleep(.1)\n'
        'p.inventory=inventory\n'
        'sys.exit(c.main(["--source",sys.argv[1],"--output",sys.argv[2]]))\n')
    source_dir=tmp_path/'source';png(source_dir,'A/Images/Ada.png')
    root=tmp_path/'state'
    result=subprocess.run([sys.executable,str(helper),str(source_dir),str(root)],capture_output=True,timeout=30)
    assert result.returncode==130,result.stderr.decode()
    assert state.inspect(root)['state']=='interrupted'


def test_checkpoint_and_recovery_metadata_have_no_cleanup_api():
    assert not hasattr(sync,'release_pin')
    assert not hasattr(publication,'cleanup') and not hasattr(publication,'push')


def test_writer_lock_remains_owned_during_failure_evidence(tmp_path,monkeypatch):
    source_dir=tmp_path/'source';png(source_dir,'A/Images/Ada.png');root=tmp_path/'batch'
    monkeypatch.setattr(plan,'renderer_version',lambda:{})
    monkeypatch.setattr(plan,'git_state',lambda _:dict(head=None,status=None,root=None))
    monkeypatch.setattr(plan,'require_space',lambda *a:10**12)
    monkeypatch.setattr(plan,'inventory',lambda *a,**k:(_ for _ in ()).throw(ValueError('fixture planning failure')))
    real=cli.evidence;checks=[]
    def evidence(root,db,*args):
        if state.metadata(db).get('phase')=='preflight_failed':
            with pytest.raises(ValueError,match='Another renderer'):
                with state.writer_lock(root):pass
            checks.append(True)
        return real(root,db,*args)
    monkeypatch.setattr(cli,'evidence',evidence)
    assert cli.main(['--source',str(source_dir),'--output',str(root)])==1
    assert checks==[True]
    with state.writer_lock(root):pass


@pytest.mark.skipif(os.name!='posix',reason='Linux native mount admission')
@pytest.mark.parametrize('filesystem',['nfs','cifs','fuse.shfs','tmpfs','overlay','zfs','ext4','xfs','btrfs'])
def test_checkpoint_mount_admission(tmp_path,monkeypatch,filesystem):
    real=Path.read_text
    def read(path,*args,**kwargs):
        if path==Path('/proc/self/mountinfo'):
            return f'123 1 0:1 / {tmp_path} rw - {filesystem} fixture rw\n'
        return real(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',read)
    if filesystem in {'zfs','ext4','xfs','btrfs'}:state.require_durable_local_state(tmp_path/'batch')
    else:
        with pytest.raises(ValueError,match='persistent native'):state.require_durable_local_state(tmp_path/'batch')


@pytest.mark.skipif(os.name!='posix',reason='Linux read-only snapshot registry protocol')
def test_zfs_registry_protocol_binds_guid_audit_and_commit(repository,tmp_path,monkeypatch):
    from types import SimpleNamespace
    import bulk_zfs_source as zfs
    _,_,local=repository
    monkeypatch.setattr(os,'statvfs',lambda path:SimpleNamespace(f_flag=os.ST_RDONLY))
    commit=command(local,'rev-parse','HEAD');registry=tmp_path/'pins';registry.mkdir()
    snapshot='tank/people/source@people-'+commit
    host_path='/srv/people/source/transparent/.zfs/snapshot/people-'+commit
    value=zfs.register(local,registry,commit,snapshot,'12345',host_path)
    assert value['verified']==8 and value['storage']['snapshot_guid']=='12345'
    assert source.validate_pin(local,registry/(commit+'.json'),True)['pin_sha256']==value['pin_sha256']
    assert zfs.register(local,registry,commit,snapshot,'12345',host_path)==value
    with pytest.raises(ValueError,match='differs'):zfs.register(local,registry,commit,snapshot,'999',host_path)
    audit_path=registry/(commit+'.audit.json');report=json.loads(audit_path.read_text());report['verified']=0;audit_path.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='audit'):source.validate_pin(local,registry/(commit+'.json'),True)
