"""Bounded successor contracts; historical Jost tests/receipts stay untouched."""
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import types
import unicodedata

import pytest
from PIL import Image, ImageChops, ImageDraw
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import create_people_poster as poster
import bulk_regenerate as bulk
import bulk_regeneration_plan as plan
import bulk_regeneration_state as state
from unicode_labels import resolve_label, ReviewRequired, STYLE_FONTS, POLICY_SHA256
import unicode_runtime as release

NAMES=('Catherine Lagaʻaia','Lương Bích Hữu','Ronkẹ Adékoluẹjo','Văn Phượng')
STYLES=tuple(STYLE_FONTS)


def cutout():
    image=Image.new('RGBA',(240,360))
    draw=ImageDraw.Draw(image)
    draw.ellipse((80,30,160,140),fill=(170,65,95,255))
    draw.rectangle((55,125,185,359),fill=(75,110,155,255))
    return image


@pytest.fixture(scope='module')
def renderer():
    return poster.Renderer()


def stage(config,name):
    source=config/'people_dirs/Downloads'/(name+'.png')
    original=config/'people_dirs/original'/(name+'.jpg')
    source.parent.mkdir(parents=True,exist_ok=True)
    original.parent.mkdir(parents=True,exist_ok=True)
    with cutout() as image:
        image.save(source)
        image.convert('RGB').save(original,'JPEG',quality=95)
    return source,original


def test_official_static_inter_and_original_fonts(renderer):
    path=ROOT/'fonts/Inter-Light.ttf'
    assert poster.digest(path)==release.INTER_SHA256
    with TTFont(path) as font:
        assert font['OS/2'].usWeightClass==300 and 'fvar' not in font
        assert font['name'].getDebugName(6)=='Inter-Light'
    assert STYLE_FONTS['bw']==STYLE_FONTS['rainier']=='Comfortaa-Medium.ttf'
    assert STYLE_FONTS['signature']=='Fuggles-Regular.ttf'
    assert (ROOT/'fonts/Jost.ttf').is_file() or (ROOT/'fonts/Jost-260.ttf').is_file()
    with TTFont(BytesIO(renderer.metrics['Inter-Light.ttf'].font_data)) as font:
        keys=[(t.platformID,t.platEncID,t.language) for t in font['cmap'].tables]
        assert len(keys)==len(set(keys))
        assert font.getBestCmap()[0x1EB9]  # original Unicode cmap survives bridge


@pytest.mark.parametrize('name',NAMES)
def test_four_people_all_five_styles(name,renderer):
    with cutout() as image:
        result=renderer.render_independent(image,name,STYLES,filename=name)
    try:
        assert not result['errors'] and set(result['outputs'])==set(STYLES)
        for style,output in result['outputs'].items():
            assert output.size==poster.SIZE
            label=result['labels'][style]
            assert label['original_name']==label['filename']==name
            expected='substituted' if name==NAMES[0] and style=='signature' else 'original'
            assert label['resolution_method']==expected
            assert label['font']==STYLE_FONTS[style]
            if expected=='substituted':
                assert label['display_label']=='Catherine Laga’aia'
                assert 'ʻ' in name and '´' not in label['display_label']
    finally:
        for image in result['outputs'].values():image.close()


@pytest.mark.parametrize('style',STYLES)
def test_decomposed_clusters_and_identity(style,renderer):
    name=unicodedata.normalize('NFD',NAMES[2])
    value=resolve_label(name,name,style,renderer.metrics)
    assert value.original_name==value.filename==name
    assert value.resolution_method in {'original','normalized'}
    assert all(g!=0 for g,*_ in renderer.metrics[value.font].shaped(value.display_label))


def test_whole_label_fallback_and_unknown_script_review(renderer):
    # Inter supports Greek; Fuggles has no Greek glyphs. No mixed-font clusters.
    value=resolve_label('Αλέξανδρος','Αλέξανδρος','signature',renderer.metrics)
    assert value.resolution_method=='fallback-font' and value.font=='Inter-Light.ttf'
    with pytest.raises(ReviewRequired) as error:
        resolve_label('未知 🦄','未知 🦄','signature',renderer.metrics)
    assert error.value.record['resolution_method']=='review-required'
    assert error.value.record['publication_authorized'] is False


def test_missing_precomposed_cmap_can_render_canonical_cluster(tmp_path,renderer):
    from poster_fonts import FontMetrics
    # Derivative exists only inside this private test fixture, never runtime.
    with TTFont(ROOT/'fonts/Comfortaa-Medium.ttf') as font:
        for table in font['cmap'].tables:
            if table.isUnicode():
                table.cmap.pop(0x1EB9,None)
                table.cmap.pop(0x1EB8,None)
        fixture=tmp_path/'cluster-fixture.ttf';font.save(fixture)
    metrics=FontMetrics(fixture)
    assert 0x1EB9 not in metrics.cmap
    assert metrics.requires_shaping('RONKẸ')
    assert metrics.glyphs('RONKẸ')
    fonts=dict(renderer.metrics,**{'Comfortaa-Medium.ttf':metrics})
    value=resolve_label('Ronkẹ','Ronkẹ','bw',fonts)
    assert value.resolution_method=='original' and value.display_label=='RONKẸ'


def test_one_style_failure_keeps_five_daily_outputs(renderer,monkeypatch):
    original=renderer.render_style
    def fail(source,name,style,**kwargs):
        if style=='signature':raise ValueError('injected one-style failure')
        return original(source,name,style,**kwargs)
    monkeypatch.setattr(renderer,'render_style',fail)
    with cutout() as image:result=renderer.render_independent(image,'Valid Person')
    assert set(result['errors'])=={'signature'}
    assert set(result['outputs'])=={'bw','rainier','diiivoy','diiivoycolor','transparent'}
    for image in result['outputs'].values():image.close()


@pytest.mark.parametrize('failure',['render','write'])
def test_daily_partial_checkpoint_and_resume(tmp_path,monkeypatch,failure):
    source,original=stage(tmp_path,'Valid Person')
    render=poster.Renderer.render_style
    save=Image.Image.save
    def fail(self,image,name,style,**kwargs):
        if style=='signature':raise ValueError('injected failure')
        return render(self,image,name,style,**kwargs)
    if failure=='render':monkeypatch.setattr(poster.Renderer,'render_style',fail)
    else:
        def fail_write(image,target,*args,**kwargs):
            if Path(target).name=='signature.jpg':raise OSError('injected disk failure')
            return save(image,target,*args,**kwargs)
        monkeypatch.setattr(Image.Image,'save',fail_write)
    report=poster.render_batch(tmp_path)
    assert report['failed']==1 and report['images'][0]['status']=='partial'
    assert source.exists() and original.exists()
    paths=[poster.output_path(tmp_path/'people_dirs',s,'Valid Person') for s in ('bw','rainier','diiivoy','diiivoycolor','transparent')]
    before={p:(poster.digest(p),p.stat().st_mtime_ns) for p in paths}
    monkeypatch.setattr(poster.Renderer,'render_style',render)
    monkeypatch.setattr(Image.Image,'save',save)
    assert poster.render_batch(tmp_path)['processed']==1
    assert before=={p:(poster.digest(p),p.stat().st_mtime_ns) for p in paths}
    assert poster.render_batch(tmp_path)['skipped']==1
    assert len(json.loads((tmp_path/'.orch/poster-render.json').read_text())['Valid Person']['outputs'])==7


def test_bulk_partial_receipts_resume_and_daily_bytes(tmp_path,monkeypatch,renderer):
    name=NAMES[2]
    source,original=stage(tmp_path/'daily',name)
    inputs=tmp_path/'source';path=inputs/'R/Images'/(name+'.png')
    path.parent.mkdir(parents=True);path.write_bytes(source.read_bytes())
    item=dict(number=0,name=name,relative=path.relative_to(inputs).as_posix(),source_hash=poster.digest(path))
    output=tmp_path/'staging'
    monkeypatch.setattr(bulk,'_renderer',lambda:renderer)
    render=renderer.render_style
    def fail(image,name,style,**kwargs):
        if style=='signature':raise ValueError('injected failure')
        return render(image,name,style,**kwargs)
    monkeypatch.setattr(renderer,'render_style',fail)
    with pytest.raises(bulk.StyleFailures):bulk.render_one(output,inputs,item,STYLES,'renderer','batch')
    for style in STYLES:
        assert bool(bulk.validated_receipt(output,item,style,'renderer','batch'))==(style!='signature')
    before={p:(poster.digest(p),p.stat().st_mtime_ns) for p in output.rglob('*.jpg')}
    monkeypatch.setattr(renderer,'render_style',render)
    bulk.render_one(output,inputs,item,('signature',),'renderer','batch')
    assert all(before[p]==(poster.digest(p),p.stat().st_mtime_ns) for p in before)
    assert poster.render_batch(tmp_path/'daily')['processed']==1
    for style in STYLES:
        path=poster.output_path(output,style,name)
        assert path.read_bytes()==poster.output_path(tmp_path/'daily/people_dirs',style,name).read_bytes()
    receipt=bulk.receipt_path(output,poster.output_path(output,'bw',name).relative_to(output).as_posix())
    value=json.loads(receipt.read_text());value['label_resolution']['font']='Jost.ttf';receipt.write_text(json.dumps(value))
    assert bulk.validated_receipt(output,item,'bw','renderer','batch') is None


def test_review_artifact_cannot_be_adopted(tmp_path,renderer):
    from unicode_review import write_review
    with pytest.raises(ReviewRequired) as error:resolve_label('未知','未知','signature',renderer.metrics)
    record=write_review(tmp_path/'review',error.value.record,renderer)
    assert record['validated'] is record['publication_authorized'] is False
    assert not list(tmp_path.rglob('*.jpg')) and not list(tmp_path.rglob('*receipt*'))
    with Image.open(tmp_path/'review/REVIEW-ONLY.png') as image:
        assert 'DO NOT PUBLISH' in image.info['Status']


def test_successor_seal_tamper_and_legacy_resume_refusal(tmp_path,monkeypatch):
    manifest=tmp_path/'successor.json'
    release.emit(ROOT,manifest)
    assert release.verify_release(ROOT,manifest)['ci_authorized'] is False
    value=json.loads(manifest.read_text());value['files']['poster_fonts.py']='0'*64
    manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='resource bytes'):release.verify_release(ROOT,manifest)
    value['ci_authorized']=True;manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='Unknown'):release.verify_release(ROOT,manifest)
    from bulk_runtime import verify_release
    with pytest.raises(ValueError):verify_release(ROOT,ROOT/'bulk/runtime-release.json')


def test_daily_inter_tamper_fails_before_rendering(tmp_path,monkeypatch):
    for name in poster.FONTS:shutil.copyfile(ROOT/'fonts'/name,tmp_path/name)
    with (tmp_path/'Inter-Light.ttf').open('ab') as stream:stream.write(b'changed')
    monkeypatch.setenv('POSTER_FONT_DIR',str(tmp_path))
    with pytest.raises(ValueError,match='approved official'):poster.Renderer()


def test_orchestrator_people_list_offline_real_seven_style_renderer(tmp_path,monkeypatch):
    import orchestrator as orch
    config=tmp_path/'config';config.mkdir()
    people=config/'people_list.txt';people.write_text('123|'+NAMES[0]+'\n456|'+NAMES[2]+'\n',encoding='utf8')
    for name in (NAMES[0],NAMES[2]):stage(config,name)
    for key in list(os.environ):
        if key.startswith(('PEOPLE_','SEL_','ORCH_','REMOVE_BG_','COLORIZE_','EDGE_CHOP_')):monkeypatch.delenv(key,raising=False)
    monkeypatch.setenv('PEOPLE_CONFIG_DIR',str(config))
    monkeypatch.setenv('POSTER_ENGINE','python')
    monkeypatch.setattr(orch,'CONFIG_DIR',config)
    monkeypatch.setattr(orch,'STATE_DIR',config/'.orch')
    monkeypatch.setattr(orch,'LOCK_FILE',config/'.orch/run.lock')
    monkeypatch.setattr(orch,'load_env_or_bootstrap',lambda:None)
    monkeypatch.setattr(orch,'background_fingerprint',lambda:{'engine':'fixture-only'})
    monkeypatch.setattr(orch,'background_checkpoint_changed',lambda _:False)
    calls=[]
    def run(title,argv,**kwargs):
        calls.append(argv)
        assert Path(argv[1]).name=='create_people_poster.py', 'Acquisition/publication forbidden in fixture'
        completed=subprocess.run(argv,env=os.environ.copy(),capture_output=True,text=True)
        assert completed.returncode==0,completed.stdout+completed.stderr
        return 0,None,None
    monkeypatch.setattr(orch,'run_cmd',run)
    monkeypatch.setattr(sys,'argv',['orchestrator.py','--publish-mode','local_git','--workspace-mode','persistent',
        '--people-list',str(people),'--redo','poster_ps1','--stop-after','poster_ps1','--no-recover-edge-chops'])
    orch.main()
    assert len(calls)==1
    for name in (NAMES[0],NAMES[2]):
        for style in poster.STYLES:assert poster.output_path(config/'people_dirs',style,name).is_file()
    assert (config/'.orch/poster_ps1.done.json').is_file()


def test_powershell_bridge_uses_orchestrator_interpreter(monkeypatch):
    import poster_renderer
    monkeypatch.setenv('POSTER_ENGINE','powershell')
    command=poster_renderer.renderer_command(sys.executable,find_powershell=lambda:'pwsh')
    assert command[-2:]==['-PythonExecutable',sys.executable]
    script=(ROOT/'create_people_poster.ps1').read_text(encoding='utf8')
    assert script.index('exit $LASTEXITCODE')<script.index('$fontInter =')
    assert poster_renderer.poster_fingerprint()['backend']=='canonical-python-unicode-v1'


def test_default_workers_and_changed_policy_fingerprint(monkeypatch):
    assert bulk.parser().parse_args(['--output','unused']).workers==2
    assert poster.renderer_fingerprint()['unicode_policy_sha256']==POLICY_SHA256
    assert 'uharfbuzz' in poster.renderer_fingerprint()
    from people_workspaces import sanitize_data
    fingerprint=poster.renderer_fingerprint()
    cleaned=sanitize_data(fingerprint)
    # Report field names/types only if a dependency supplies incompatible data.
    def differences(a,b,path='fingerprint'):
        if isinstance(a,dict) and isinstance(b,dict):
            return [p for k in a for p in differences(a[k],b.get(k),path+'.'+k)]
        if json.dumps(a,sort_keys=True)!=json.dumps(b,sort_keys=True):return [(path,type(a).__name__,type(b).__name__)]
        return []
    assert not differences(fingerprint,cleaned),differences(fingerprint,cleaned)


def test_real_two_worker_interrupt_resume_validate_and_version_guard(tmp_path,monkeypatch):
    source=tmp_path/'source'
    output=tmp_path/'staging'
    for name in ('Valid Person','Other Person',NAMES[2]):
        path=source/name[0]/'Images'/(name+'.png')
        path.parent.mkdir(parents=True,exist_ok=True)
        with cutout() as image:image.save(path)
    # Capacity is independent of this tiny rendering fixture; no storage audit.
    monkeypatch.setattr(plan,'require_space',lambda *args:10**12)
    run=bulk.run_batch
    stop=threading.Event()
    def worker(*args):
        value=bulk.render_one(*args)
        stop.set()
        return value
    monkeypatch.setattr(bulk,'run_batch',lambda root,db,manifest,workers,progress:
        run(root,db,manifest,workers,progress,stop=stop,worker=worker))
    assert bulk.main(['--source',str(source),'--output',str(output),'--styles','diiivoy','diiivoycolor','--workers','2'])==130
    assert state.inspect(output)['state']=='interrupted'
    before={p:(poster.digest(p),p.stat().st_mtime_ns) for p in output.rglob('*.jpg')}
    assert len(before)==4
    monkeypatch.setattr(bulk,'run_batch',run)
    assert bulk.main(['--resume','--output',str(output),'--workers','2'])==0
    assert all(before[p]==(poster.digest(p),p.stat().st_mtime_ns) for p in before)
    from bulk_validate import validate
    result=validate(output)
    assert result['valid'] and result['verified']==6,result
    real_version=plan.renderer_version
    monkeypatch.setattr(plan,'renderer_version',lambda:dict(real_version(),unicode_policy_sha256='old-profile'))
    assert bulk.main(['--resume','--output',str(output)])==1
    assert all(before[p]==(poster.digest(p),p.stat().st_mtime_ns) for p in before)
