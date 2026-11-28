"""Source-only contract regressions using the existing renderer and transports."""
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import people_github as github
import people_workspaces as jobs
import create_people_poster as poster
import sync_people_images as sync
import people_remote_inventory as discovery
from create_people_posters.tests.test_people_api_orchestrator import isolated as api_isolated


@pytest.fixture
def source_only(tmp_path,monkeypatch):
    monkeypatch.setenv('PEOPLE_OUTPUT_CONTRACT',jobs.SOURCE_CONTRACT)
    monkeypatch.setenv('PEOPLE_PUBLISH_MODE','local')
    monkeypatch.setenv('PEOPLE_AUTO_CLEANUP','false')
    for key in ('PEOPLE_GITHUB_TARGET','PEOPLE_SANDBOX_CONFIG','PEOPLE_REPLACEMENT_CONFIG','PEOPLE_STATE_DIR','PEOPLE_JOBS_DIR'):
        monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(poster,'SIZE',(1000,1500))
    monkeypatch.setattr(sync,'TARGET_TRANSPARENT_SIZE',(1000,1500))
    config=tmp_path/'config'
    config.mkdir()
    monkeypatch.setenv('PEOPLE_CONFIG_DIR',str(config))
    return config


def stage(config,name='Zo\u00eb Garc\u00eda',size=(1000,1500)):
    for directory in ('Downloads','original'):
        (config/'people_dirs'/directory).mkdir(parents=True,exist_ok=True)
    image=Image.new('RGBA',size)
    draw=ImageDraw.Draw(image)
    draw.ellipse((size[0]//3,size[1]//10,size[0]*2//3,size[1]//2),fill=(170,60,95,255))
    draw.rectangle((size[0]//4,size[1]//3,size[0]*3//4,size[1]-1),fill=(170,60,95,255))
    cutout=config/'people_dirs/Downloads'/(name+'.png');image.save(cutout)
    photo=config/'people_dirs/original'/(name+'.jpg');image.convert('RGB').save(photo,quality=95)
    return cutout,photo


def test_exact_two_outputs_alpha_framing_and_repeat_without_resources(source_only,monkeypatch):
    cutout,photo=stage(source_only)
    before=cutout.read_bytes();native=photo.read_bytes()
    monkeypatch.setattr(poster,'resource_dirs',lambda:pytest.fail('Unused style assets/fonts loaded'))
    report=poster.render_batch(source_only)
    assert report['processed']==1 and report['failed']==0
    files=list((source_only/'people_dirs').glob('*/?*/Images/*'))
    assert {p.parent.parent.parent.name for p in files}=={'original','transparent'}
    transparent=next(p for p in files if p.suffix=='.png')
    original=next(p for p in files if p.suffix=='.jpg')
    import io
    with Image.open(io.BytesIO(before)) as expected,Image.open(transparent) as actual:
        assert actual.size==(1000,1500) and actual.mode=='RGBA'
        assert actual.tobytes()==expected.tobytes()
        assert actual.getchannel('A').getextrema()==(0,255)
    assert original.read_bytes()==native
    for style,path in (('original',original),('transparent',transparent)):
        assert not sync.image_quality_findings(style,path)[0]
    assert poster.render_batch(source_only)['skipped']==1
    assert poster.renderer_fingerprint()['output_contract']==jobs.SOURCE_CONTRACT
    recovered=source_only/'accepted-recovery'
    report=poster.render_recovery_candidate(source_only/'recovery-render',recovered,'Recovered',transparent,original)
    assert report['processed']==1 and report['failed']==0
    assert poster.output_path(recovered,'transparent','Recovered').is_file()
    assert {p.name for p in recovered.iterdir()}=={'transparent'}


def test_png_original_checkpoint_reuses_exact_final_jpeg(source_only):
    cutout,photo=stage(source_only)
    raw=cutout.read_bytes()
    normalized=photo.with_suffix('.png')
    with Image.open(photo) as image:image.save(normalized,'PNG')
    photo.unlink()
    input_hash=hashlib.sha256(normalized.read_bytes()).hexdigest()
    assert poster.render_batch(source_only)['processed']==1
    outputs=list((source_only/'people_dirs').glob('*/?*/Images/*'))
    before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in outputs}
    checkpoint=source_only/'.orch/poster-render.json'
    assert next(iter(json.loads(checkpoint.read_text()).values()))['original_hash']==input_hash
    retained=checkpoint.read_bytes()
    cutout.write_bytes(raw)
    assert poster.render_batch(source_only)['skipped']==1
    assert checkpoint.read_bytes()==retained
    assert all((p.read_bytes(),p.stat().st_mtime_ns)==value for p,value in before.items())


def test_early_normalization_reuses_fit_and_preserves_native(source_only,monkeypatch):
    import recover_edge_chops as recovery
    import audit_people_images as audit
    monkeypatch.setattr(recovery,'TARGET_SIZE',(1000,1500))
    monkeypatch.setattr(recovery,'CONFIG_DIR',source_only)
    monkeypatch.setattr(audit,'CONFIG_DIR',source_only)
    monkeypatch.setattr(audit,'script_log',source_only/'audit.log')
    native=source_only/'portrait.png'
    image=Image.new('RGBA',(2000,3000));ImageDraw.Draw(image).rectangle((211,321,1500,2999),fill=(170,60,95,210));image.save(native)
    raw=native.read_bytes();target=source_only/'Downloads/color/portrait.jpg'
    audit.copy_file(native,target)
    with Image.open(target.with_suffix('.png')) as working:
        expected=ImageOps.fit(image,(1000,1500),method=Image.Resampling.LANCZOS,centering=(.5,.5))
        assert working.size==(1000,1500) and working.mode=='RGBA'
        assert working.tobytes()==expected.tobytes()
    checksum=hashlib.sha256(raw).hexdigest()
    archived=source_only/'people_dirs/original/.history/recovery_sources'/checksum/'source.png'
    assert archived.read_bytes()==native.read_bytes()==raw


def test_legacy_dimensions_not_accepted_or_downscaled_at_render(source_only):
    stage(source_only,size=(2000,3000))
    assert poster.render_batch(source_only)['failed']==1
    assert not list((source_only/'people_dirs/transparent').glob('*/Images/*'))


def test_discovery_requires_only_two_correct_sized_outputs(source_only):
    stage(source_only)
    assert poster.render_batch(source_only)['processed']==1
    assert discovery.online_complete_names()=={discovery.name_key('Zo\u00eb Garc\u00eda')}
    image=next((source_only/'people_dirs/transparent').glob('*/Images/*.png'))
    with Image.open(image) as opened:opened.resize((2000,3000)).save(image)
    assert discovery.online_complete_names()==set()


def staging_targets(source_only,monkeypatch):
    root=source_only/'sandboxes';monkeypatch.setattr(github,'SANDBOX_ROOT',root)
    path=root/'test/targets.json';path.parent.mkdir(parents=True)
    data=dict(version=1,owner='test-user',branch='master',output_contract=jobs.SOURCE_CONTRACT,
        publication_authorized=True,repositories={s:'test-user/kometa-people-sandbox-'+s for s in jobs.SOURCE_STYLES})
    path.write_text(json.dumps(data))
    monkeypatch.setenv('PEOPLE_GITHUB_TARGET','sandbox');monkeypatch.setenv('PEOPLE_SANDBOX_CONFIG',str(path))
    return path,data


@pytest.mark.parametrize('production',list(github.REPOSITORIES.values()))
def test_all_production_repositories_blocked_at_transport_and_config(source_only,monkeypatch,production):
    path,data=staging_targets(source_only,monkeypatch)
    session=SimpleNamespace(headers={},request=lambda *a,**k:pytest.fail('Production network request reached'))
    client=github.GitHubClient('fixture-token',session)
    for method in ('GET','POST','PATCH'):
        with pytest.raises(ValueError):client.request(method,'/repos/'+production+'/git/blobs')
    data['repositories']['original']=production;path.write_text(json.dumps(data))
    with pytest.raises(ValueError):github.repository_mapping()
    with pytest.raises(ValueError):client.request('POST','/repos/test-user/kometa-people-sandbox-original/git/blobs')


def test_staging_requires_authorization_and_fresh_contract(source_only,monkeypatch):
    path,data=staging_targets(source_only,monkeypatch)
    calls=[]
    session=SimpleNamespace(headers={},request=lambda *a,**k:calls.append(a) or SimpleNamespace(status_code=200,json=lambda:{'ok':True}))
    client=github.GitHubClient('fixture-token',session)
    assert client.request('GET','/repos/test-user/kometa-people-sandbox-transparent')=={'ok':True}
    data['publication_authorized']=False;path.write_text(json.dumps(data))
    with pytest.raises(ValueError):client.request('POST','/repos/test-user/kometa-people-sandbox-transparent/git/blobs')
    assert len(calls)==1


def test_old_batch_cannot_resume_and_receipt_stays_readable(source_only,monkeypatch):
    manager=jobs.Workspaces(source_only)
    try:
        new=manager.create(cleanup=False)
        assert manager.record(new)[1]['output_contract']==jobs.SOURCE_CONTRACT
        manifest=manager.path(new)/'manifest.json';value=json.loads(manifest.read_bytes());value.pop('output_contract');manifest.write_text(json.dumps(value))
        prior=manifest.read_bytes()
        assert manager.record(new)[1]['managed_by']=='kometa-people-v1'
        with pytest.raises(ValueError,match='Incompatible output contract'):manager.select(new,cleanup=False)
        with pytest.raises(ValueError,match='Incompatible output contract'):manager.select(cleanup=False)
        assert manifest.read_bytes()==prior
    finally:manager.close()
    # A direct publisher retry must supply the recorded contract up front;
    # it cannot reinterpret already imported legacy dimension settings.
    import publish_people_github as publisher
    import dotenv
    (source_only/'manifest.json').write_text(json.dumps({'output_contract':jobs.SOURCE_CONTRACT}))
    with monkeypatch.context() as retry:
        retry.delenv('PEOPLE_OUTPUT_CONTRACT')
        retry.setattr(dotenv,'load_dotenv',lambda *a,**k:None)
        retry.setattr(publisher,'GitHubClient',lambda:pytest.fail('Incompatible retry reached GitHub'))
        retry.setattr(sys,'argv',['publisher','--op','validate','--config',str(source_only)])
        assert publisher.main()==1
        assert not os.getenv('PEOPLE_OUTPUT_CONTRACT')
    # Standalone renderer checkpoints also cannot adopt an old seven-style job.
    state=source_only/'.orch/poster-render.json';state.parent.mkdir()
    state.write_text(json.dumps({'Legacy':{'fingerprint':{'engine':'python'}}}))
    prior=state.read_bytes()
    with pytest.raises(ValueError,match='Incompatible output contract'):poster.render_batch(source_only)
    assert state.read_bytes()==prior


def test_unused_styles_refused_before_style_work(source_only,monkeypatch):
    renderer=poster.Renderer()
    monkeypatch.setattr(renderer,'prepare_cutout',lambda _:pytest.fail('Unused renderer reached'))
    for style in ('bw','diiivoy','diiivoycolor','rainier','signature'):
        with pytest.raises(ValueError):renderer.render_independent(None,'Person',(style,))


@pytest.mark.parametrize('selection',['automatic','explicit'])
def test_incompatible_expired_resume_is_retained_before_cleanup(api_isolated,monkeypatch,selection):
    import time
    from create_people_posters.tests.test_people_api_orchestrator import invoke,orch
    manager=jobs.Workspaces(api_isolated)
    try:
        batch=manager.create(cleanup=False)
        manager.set_status(batch,'failed')
        with manager.db:
            manager.db.execute('UPDATE jobs SET updated=? WHERE id=?',(time.time()-30*86400,batch))
        manifest=manager.path(batch)/'manifest.json';before=manifest.read_bytes()
        source=manager.path(batch)/'posters/only-source.jpg';source.write_bytes(b'native evidence')
        monkeypatch.setattr(jobs.Workspaces,'cleanup',lambda *a,**k:pytest.fail('Incompatible resume reached expiry'))
        monkeypatch.setattr(orch,'run_cmd',lambda *a,**k:pytest.fail('Incompatible resume ran a step'))
        args=['--batch-id',batch] if selection=='explicit' else []
        with pytest.raises(SystemExit) as error:invoke(monkeypatch,*args,'--stop-after','ensure_repo')
        assert error.value.code==2
        assert manifest.read_bytes()==before and source.read_bytes()==b'native evidence'
        assert not (manager.path(batch)/'.active').exists()
    finally:manager.close()


@pytest.mark.parametrize('attack',['tamper','rollback','missing'])
def test_exact_ci_successor_rejects_changed_physical_bytes(monkeypatch,attack):
    from ci.phase6_playlist_maintenance import source_adapter
    owner=source_adapter();_,before=owner.verify()
    name='create_people_posters/people_github.py';target=owner.ROOT/name
    original=Path.read_bytes
    def read(path):
        if path==target:
            if attack=='missing':raise FileNotFoundError(str(path))
            return before[name] if attack=='rollback' else original(path)+b'\nunapproved'
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',read)
    with pytest.raises((ValueError,OSError)):owner.verify()


def test_exact_ci_successor_keeps_fresh_closing_head(monkeypatch):
    from ci.phase6_playlist_maintenance import source_adapter
    owner=source_adapter();owner.verify();head=owner._head(owner.ROOT)
    reads=iter((head,'0'*40))
    monkeypatch.setattr(owner,'_head',lambda _:next(reads))
    with pytest.raises(ValueError,match='HEAD moved'):owner.verify()


@pytest.mark.parametrize('attack',['unknown-path','mode','object'])
def test_exact_ci_successor_rejects_wrong_git_evidence(monkeypatch,attack):
    from ci.phase6_playlist_maintenance import source_adapter
    owner=source_adapter();actual=owner.git
    owner.immutable.cache_clear();owner.objects.cache_clear()
    def read(*args,**kwargs):
        raw=actual(*args,**kwargs)
        if args[0]=='diff' and attack=='unknown-path':
            return raw.replace(b'create_people_posters/people_github.py',b'create_people_posters/unapproved.py',1)
        if args[0]=='ls-tree' and attack=='mode':return raw.replace(b'100644',b'120000',1)
        if args[0]=='cat-file' and attack=='object':
            end=raw.index(b'\n')+1
            return raw[:end]+bytes((raw[end]^1,))+raw[end+1:]
        return raw
    monkeypatch.setattr(owner,'git',read)
    try:
        with pytest.raises(ValueError):owner.verify()
    finally:owner.immutable.cache_clear();owner.objects.cache_clear()


def replacement_targets(source_only,monkeypatch,branch='main'):
    root=source_only/'replacements';monkeypatch.setattr(github,'REPLACEMENT_ROOT',root)
    path=root/'approved/targets.json';path.parent.mkdir(parents=True)
    data=dict(version=1,branch=branch,output_contract=jobs.SOURCE_CONTRACT,publication_authorized=True,
        repositories=dict(original='Kometa-Team/People-Images-1500',transparent='Kometa-Team/People-Images-transparent-1500'),
        repository_ids=dict(github.REPLACEMENT_IDS))
    path.write_text(json.dumps(data));monkeypatch.setenv('PEOPLE_GITHUB_TARGET','replacement')
    monkeypatch.setenv('PEOPLE_PUBLISH_MODE','github_api');monkeypatch.delenv('PEOPLE_BRANCH',raising=False)
    monkeypatch.setenv('PEOPLE_REPLACEMENT_CONFIG',str(path))
    return path,data


class ReplacementSession:
    def __init__(self,data):self.data=data;self.headers={};self.calls=[];self.metadata_change={};self.status=200
    def request(self,method,url,**kwargs):
        self.calls.append((method,url,kwargs.get('json')))
        parts=url.split('/');style=next(s for s,i in self.data['repository_ids'].items() if str(i)==parts[4])
        if len(parts)==5:
            value=dict(id=self.data['repository_ids'][style],full_name=self.data['repositories'][style],
                default_branch=self.data['branch'],permissions={'push':True})
            value.update(self.metadata_change)
        elif url.endswith('actions/workflows/readme.yml'):
            value=dict(state='active',path='.github/workflows/readme.yml')
        elif '/actions/runs/' in url:value={'head_branch':self.data['branch']}
        else:value={'ok':True}
        return SimpleNamespace(status_code=200 if len(parts)==5 else self.status,json=lambda:value,headers={},text='')


@pytest.mark.parametrize('branch',['main','master'])
def test_replacement_exact_configuration_branch_and_numeric_routing(source_only,monkeypatch,branch):
    _,data=replacement_targets(source_only,monkeypatch,branch)
    session=ReplacementSession(data);client=github.GitHubClient('fixture-token',session)
    assert github.repository_mapping()==data['repositories'] and github.branch_name()==branch
    with pytest.raises(ValueError):github.branch_name('master' if branch=='main' else 'main')
    repo=data['repositories']['original']
    assert client.request('GET',f'/repos/{repo}/git/ref/heads/{branch}')=={'ok':True}
    assert session.calls[-1][1]==f"https://api.github.com/repositories/{data['repository_ids']['original']}/git/ref/heads/{branch}"
    for method,route,payload in [('PATCH','git/refs/heads/'+branch,{'sha':'a'*40,'force':False}),
            ('POST','actions/workflows/readme.yml/dispatches',{'ref':branch,'inputs':{'batch_id':'fixture'}}),
            ('POST','actions/runs/123/rerun',{})]:
        client.request(method,f'/repos/{repo}/{route}',payload)


@pytest.mark.parametrize('attack',['missing','unauthorized','contract','id','branch','duplicate','unknown-field','mode','legacy-contract','local'])
def test_replacement_configuration_fails_closed(source_only,monkeypatch,attack):
    path,data=replacement_targets(source_only,monkeypatch)
    if attack=='missing':path.unlink()
    elif attack=='mode':monkeypatch.delenv('PEOPLE_GITHUB_TARGET')
    elif attack=='legacy-contract':monkeypatch.delenv('PEOPLE_OUTPUT_CONTRACT')
    elif attack=='local':monkeypatch.setenv('PEOPLE_PUBLISH_MODE','local')
    else:
        if attack=='unauthorized':data['publication_authorized']=False
        if attack=='contract':data['output_contract']='legacy'
        if attack=='id':data['repository_ids']['original']+=1
        if attack=='branch':data['branch']='development'
        if attack=='duplicate':data['repositories']['original']=data['repositories']['transparent']
        if attack=='unknown-field':data['unreviewed']='extra authority'
        path.write_text(json.dumps(data))
    with pytest.raises((ValueError,OSError)):github.repository_mapping()


@pytest.mark.parametrize('attack',['rename','id','branch','revoked','retry-revoked','readme-branch','write-branch'])
def test_replacement_rechecks_identity_branch_and_retry_authority(source_only,monkeypatch,attack):
    path,data=replacement_targets(source_only,monkeypatch)
    session=ReplacementSession(data);client=github.GitHubClient('fixture-token',session,sleep=lambda _:None)
    repo=data['repositories']['original'];client.request('GET','/repos/'+repo)
    session.calls.clear()
    if attack in ('rename','id','branch'):
        key={'rename':'full_name','id':'id','branch':'default_branch'}[attack]
        session.metadata_change={key:'unexpected' if key!='id' else 1}
    if attack=='revoked':
        data['publication_authorized']=False;path.write_text(json.dumps(data))
    if attack=='retry-revoked':
        session.status=503
        def revoke(_):
            data['publication_authorized']=False;path.write_text(json.dumps(data))
        client.sleep=revoke
    route='actions/workflows/readme.yml/dispatches' if attack=='readme-branch' else 'git/refs/heads/master' if attack=='write-branch' else 'git/blobs'
    payload={'ref':'master'} if attack=='readme-branch' else {'content':'fixture','force':False}
    with pytest.raises((ValueError,github.GitHubError)):client.request('PATCH' if attack=='write-branch' else 'POST','/repos/'+repo+'/'+route,payload)
    assert sum(method!='GET' for method,_,_ in session.calls)==(1 if attack=='retry-revoked' else 0)


@pytest.mark.parametrize('legacy',list(github.REPOSITORIES.values()))
def test_replacement_blocks_all_legacy_operations(source_only,monkeypatch,legacy):
    _,data=replacement_targets(source_only,monkeypatch);session=ReplacementSession(data)
    client=github.GitHubClient('fixture-token',session)
    for method,route,payload in [('GET','git/ref/heads/main',None),('POST','git/blobs',{}),
            ('PATCH','git/refs/heads/main',{'force':False}),('POST','actions/workflows/readme.yml/dispatches',{'ref':'main'})]:
        with pytest.raises(ValueError):client.request(method,'/repos/'+legacy+'/'+route,payload)
    assert not session.calls


def test_replacement_batch_binding_survives_restart_and_rejects_missing_or_changed_authority(source_only,monkeypatch):
    from people_publication_state import PublicationState
    from publish_people_github import prepare,Publisher
    from people_remote_inventory import RemoteInventory
    path,data=replacement_targets(source_only,monkeypatch)
    stage(source_only);assert poster.render_batch(source_only)['processed']==1
    state=source_only/'state';ledger=PublicationState(state)
    try:
        plan=prepare(source_only,'20261127T000000-123456abcdef',ledger,'main');assert len(plan)==2
    finally:ledger.close()
    ledger=PublicationState(state)
    try:
        assert len(prepare(source_only,'20261127T000000-123456abcdef',ledger,'main'))==2
        old=ledger.db.execute('SELECT authorization FROM replacement_targets').fetchone()[0]
        data['repositories']['original']='Kometa-Team/Approved-future-name';path.write_text(json.dumps(data))
        with pytest.raises(ValueError,match='retarget'):prepare(source_only,'20261127T000000-123456abcdef',ledger,'main')
        data['repositories']['original']='Kometa-Team/People-Images-1500';path.write_text(json.dumps(data))
        ledger.db.execute('DELETE FROM replacement_targets');ledger.db.commit()
        with pytest.raises(ValueError,match='Missing replacement'):prepare(source_only,'20261127T000000-123456abcdef',ledger,'main')
        session=ReplacementSession(data);client=github.GitHubClient('fixture-token',session)
        inventory=RemoteInventory(client,source_only/'inventory.db','main')
        try:
            with pytest.raises(ValueError,match='Missing replacement'):Publisher(client,inventory,ledger).publish('20261127T000000-123456abcdef')
            assert not session.calls
        finally:inventory.close()
        assert json.loads(old)['repository_ids']==github.REPLACEMENT_IDS
    finally:ledger.close()


def test_replacement_missing_readme_blocks_before_artwork_writes(source_only,monkeypatch):
    from people_publication_state import PublicationState
    from people_remote_inventory import RemoteInventory
    from publish_people_github import Publisher
    _,data=replacement_targets(source_only,monkeypatch);session=ReplacementSession(data)
    session.status=404;client=github.GitHubClient('fixture-token',session,attempts=1)
    ledger=PublicationState(source_only/'state');inventory=RemoteInventory(client,source_only/'inventory.db')
    try:
        with pytest.raises(github.GitHubError):Publisher(client,inventory,ledger).validate()
        assert not any(method!='GET' for method,_,_ in session.calls)
    finally:inventory.close();ledger.close()


@pytest.mark.parametrize('branch',['main','master'])
def test_replacement_existing_publisher_receipts_and_no_write_retry(source_only,monkeypatch,branch):
    from create_people_posters.tests import test_people_github as existing
    from people_publication_state import PublicationState
    from people_remote_inventory import RemoteInventory,blob_sha
    from publish_people_github import Publisher,prepare
    import copy
    _,data=replacement_targets(source_only,monkeypatch,branch)
    monkeypatch.setattr(existing,'REPOSITORIES',data['repositories'])
    peer=existing.FakeGitHub();generate=peer.generate_readmes
    def readmes(repo):
        generate(repo);files=copy.deepcopy(peer.trees[peer.commits[peer.heads[repo]]])
        for name,item in files.items():
            if name.endswith('README.md'):
                raw=peer.blobs[item['sha']].replace(b'/master/',('/'+branch+'/').encode())
                sha=blob_sha(raw);peer.blobs[sha]=raw;item.update(sha=sha,size=len(raw))
        peer.advance(repo,files)
    peer.generate_readmes=readmes
    class Session(ReplacementSession):
        def request(self,method,url,**kwargs):
            parts=url.split('/');style=next(s for s,i in data['repository_ids'].items() if str(i)==parts[4])
            repo=data['repositories'][style];route='/'.join(parts[5:])
            if not route or route=='actions/workflows/readme.yml':return super().request(method,url,**kwargs)
            self.calls.append((method,url,kwargs.get('json')))
            if method=='GET' and route.startswith('git/ref/heads/'):
                result={'object':{'sha':peer.heads[repo]}}
            elif method=='GET' and route.startswith('git/commits/'):
                result={'tree':{'sha':peer.commits[parts[-1]]}}
            else:
                # Adapt the retained master-only fake, after the real transport
                # has checked and routed the exact configured branch and ID.
                payload=copy.deepcopy(kwargs.get('json'))
                if payload and 'ref' in payload:payload['ref']='master'
                mapped=route.replace('git/refs/heads/'+branch,'git/refs/heads/master')
                result=peer.request(method,'/repos/'+repo+'/'+mapped,payload)
                for runs in peer.runs.values():
                    for run in runs:run['head_branch']=branch
            return SimpleNamespace(status_code=200,json=lambda:result,headers={},text='')
    session=Session(data);client=github.GitHubClient('fixture-token',session,sleep=lambda _:None)
    monkeypatch.setenv('UPDATE_TRIGGER_READMES','true');monkeypatch.setenv('UPDATE_REQUIRE_README_DISPATCH','true')
    monkeypatch.setenv('PEOPLE_README_POLL_INTERVAL','0.001')
    stage(source_only);assert poster.render_batch(source_only)['processed']==1
    ledger=PublicationState(source_only/'state');inventory=RemoteInventory(client,source_only/'inventory.db',branch)
    try:
        rows=prepare(source_only,'20261127T000001-123456abcdef',ledger,branch)
        publisher=Publisher(client,inventory,ledger);publisher.validate();publisher.publish('20261127T000001-123456abcdef')
        assert len(rows)==2 and ledger.verified('20261127T000001-123456abcdef')
        for row in rows:assert peer.blobs[row['blob']]==Path(row['prepared']).read_bytes()
        session.calls.clear();publisher.publish('20261127T000001-123456abcdef')
        assert not any(method!='GET' for method,_,_ in session.calls)
        monkeypatch.setenv('PEOPLE_PUBLICATION_BACKEND','git-v2')
        with pytest.raises(ValueError,match='REST publisher'):publisher.publish('20261127T000001-123456abcdef')
    finally:inventory.close();ledger.close()


def test_exact_ci_source_invocation_reuses_only_entry_proof(monkeypatch):
    from unittest.mock import patch
    from ci.phase6_playlist_maintenance import source_adapter
    owner=source_adapter();value,before=owner.verify()
    name='create_people_posters/people_github.py';binding=value['files'][name]
    raw=(owner.ROOT/name).read_bytes()
    with patch.object(owner,'verify',wraps=owner.verify) as verify:
        with owner.invocation():
            with owner.invocation():
                for _ in range(3):
                    assert owner.selected_hash(name,binding['before_sha256'])==binding['sha256']
                    assert owner.historical_bytes(owner.ROOT,name,raw)==before[name]
            assert verify.call_count==1
        assert verify.call_count==2
        owner.selected_hash(name,binding['before_sha256'])
        assert verify.call_count==3
    # Protected hash selection also runs without an M7 owner. Each public call
    # retains two complete source proofs, never one per nested selection.
    from ci import phase6_playlist_maintenance as pilot
    target='ci/people_unicode_maintenance.py'
    predecessor=next(row[1] for row in pilot._decode((owner.ROOT/pilot.RECEIPT).read_bytes()) if row[0]==target)
    with patch.object(owner,'verify',wraps=owner.verify) as verify:
        for count in (2,4):
            assert pilot.selected_hash(target,predecessor)==value['files'][target]['sha256']
            assert verify.call_count==count


@pytest.mark.parametrize('attack',['projection','closing','head','expired'])
def test_exact_ci_source_invocation_retains_freshness_and_closing_checks(monkeypatch,attack):
    from contextvars import copy_context
    from ci.phase6_playlist_maintenance import source_adapter
    owner=source_adapter();value,before=owner.verify()
    name='create_people_posters/people_github.py';binding=value['files'][name]
    raw=(owner.ROOT/name).read_bytes();read=Path.read_bytes
    if attack=='projection':
        with owner.invocation():
            for bad in (raw+b'changed',before[name],None):
                def physical(path):
                    if path!=owner.ROOT/name:return read(path)
                    if bad is None:raise FileNotFoundError(path)
                    return bad
                with monkeypatch.context() as changed:
                    changed.setattr(Path,'read_bytes',physical)
                    with pytest.raises((ValueError,OSError)):
                        owner.historical_bytes(owner.ROOT,name,raw)
            stat=Path.lstat
            with monkeypatch.context() as changed:
                changed.setattr(Path,'lstat',lambda path:SimpleNamespace(st_mode=0o040755)
                                if path==owner.ROOT/name else stat(path))
                with pytest.raises(ValueError):owner.historical_bytes(owner.ROOT,name,raw)
    elif attack=='closing':
        other=owner.ROOT/'create_people_posters/SOURCE_ONLY.md'
        with monkeypatch.context() as changed:
            with pytest.raises(ValueError,match='source-only'):
                with owner.invocation():
                    owner.selected_hash(name,binding['before_sha256'])
                    changed.setattr(Path,'read_bytes',lambda path:read(path)+b'changed' if path==other else read(path))
        from ci import phase6_playlist_maintenance as pilot
        target='ci/people_unicode_maintenance.py'
        predecessor=next(row[1] for row in pilot._decode((owner.ROOT/pilot.RECEIPT).read_bytes()) if row[0]==target)
        proof=pilot._protected_cohort_proof
        with monkeypatch.context() as changed:
            def move(root):
                result=proof(root)
                changed.setattr(Path,'read_bytes',lambda path:read(path)+b'changed' if path==other else read(path))
                return result
            changed.setattr(pilot,'_protected_cohort_proof',move)
            with pytest.raises(ValueError,match='source-only'):
                pilot.selected_hash(target,predecessor)
    elif attack=='head':
        head=owner._head(owner.ROOT)
        for stage in ('projection','closing'):
            observed=[head]
            with monkeypatch.context() as changed:
                changed.setattr(owner,'_head',lambda root:observed[0])
                with pytest.raises(ValueError,match='source-only'):
                    with owner.invocation():
                        observed[0]='0'*40
                        if stage=='projection':owner.selected_hash(name,binding['before_sha256'])
    else:
        with owner.invocation():snapshot=copy_context()
        with pytest.raises(ValueError,match='source-only'):
            snapshot.run(owner.selected_hash,name,binding['before_sha256'])
    assert owner._ACTIVE.get() is None


if not hasattr(jobs,'SOURCE_CONTRACT'):
    # The mandatory compatibility job imports the authenticated Jost runtime.
    # These new contract cases need current production imports instead. Keep
    # every parametrized ID and propagate each fresh child's result, with no
    # skipped cases, changed historical modules or alternate approval flags.
    import inspect
    import subprocess
    def _current_runtime_case(function):
        marks=getattr(function,'pytestmark',[])
        parameters=[]
        for mark in marks:
            if mark.name=='parametrize':
                names=mark.args[0].split(',') if isinstance(mark.args[0],str) else mark.args[0]
                parameters.extend(name.strip() for name in names)
        def current_case(request,**kwargs):
            result=subprocess.run([sys.executable,'-B','-m','pytest',request.node.nodeid,
                '-q','--tb=short','-p','no:cacheprovider'],cwd=Path(__file__).resolve().parents[2],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',timeout=180)
            assert result.returncode==0,result.stdout
        current_case.__name__=function.__name__
        current_case.__doc__=function.__doc__
        current_case.pytestmark=marks
        current_case.__signature__=inspect.Signature([inspect.Parameter(name,inspect.Parameter.POSITIONAL_OR_KEYWORD)
            for name in ['request',*parameters]])
        return current_case
    for _name,_function in tuple(globals().items()):
        if _name.startswith('test_') and callable(_function):globals()[_name]=_current_runtime_case(_function)
