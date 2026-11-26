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


@pytest.fixture
def source_only(tmp_path,monkeypatch):
    monkeypatch.setenv('PEOPLE_OUTPUT_CONTRACT',jobs.SOURCE_CONTRACT)
    monkeypatch.setenv('PEOPLE_PUBLISH_MODE','local')
    monkeypatch.setenv('PEOPLE_AUTO_CLEANUP','false')
    for key in ('PEOPLE_GITHUB_TARGET','PEOPLE_SANDBOX_CONFIG','PEOPLE_STATE_DIR','PEOPLE_JOBS_DIR'):
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
