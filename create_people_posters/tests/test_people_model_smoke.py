import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import smoke_people_models as smoke


def test_inference_requires_explicit_opt_in(tmp_path,monkeypatch):
    import dotenv
    monkeypatch.setattr(dotenv,'load_dotenv',lambda *a,**k:None)
    monkeypatch.setattr(smoke.subprocess,'run',lambda *a,**k:pytest.fail('Unexpected inference'))
    with pytest.raises(SystemExit):
        smoke.main(['--workspace-root',str(tmp_path/'work')])
    assert not (tmp_path/'work').exists()


def test_real_grayscale_validation_does_not_convert_color_input(tmp_path):
    source=tmp_path/'color.png'
    Image.new('RGB',(32,48),(40,80,160)).save(source)
    before=source.read_bytes()
    with pytest.raises(ValueError,match='genuine grayscale'):
        smoke.validate_grayscale(source)
    assert source.read_bytes()==before


def test_isolated_stage_does_not_reload_private_credentials(tmp_path,monkeypatch):
    import dotenv
    monkeypatch.setattr(dotenv,'load_dotenv',lambda *a,**k:pytest.fail('Private config loaded in stage'))
    calls=[]
    monkeypatch.setattr(smoke,'run_stage',lambda stage,workspace:calls.append((stage,workspace)))
    assert smoke.main(['--run','--stage','render','--workspace',str(tmp_path)])==0
    assert calls==[('render',tmp_path.resolve())]


def test_failed_smoke_stage_preserves_source_and_records_problem(tmp_path,monkeypatch):
    import dotenv
    monkeypatch.setattr(dotenv,'load_dotenv',lambda *a,**k:None)
    source=tmp_path/'gray.png'
    image=Image.new('L',(32,48),0)
    image.paste(255,(8,8,24,40))
    image.save(source)
    before=(source.read_bytes(),source.stat().st_mtime_ns)
    def run(command,**kw):
        assert '--stage' in command
        assert kw['env']['PEOPLE_CONFIG_DIR'].startswith(str(tmp_path/'work'))
        assert 'GITHUB_TOKEN' not in kw['env'] and kw['env']['HF_HUB_OFFLINE']=='1'
        return SimpleNamespace(returncode=2)
    monkeypatch.setattr(smoke.subprocess,'run',run)
    assert smoke.main(['--run','--input',str(source),'--workspace-root',str(tmp_path/'work')])==1
    report=json.loads(next((tmp_path/'work').glob('*/summary.json')).read_text())
    assert report['status']=='failed' and report['source_unchanged']
    assert 'ddcolor exited 2' in report['error']
    assert before==(source.read_bytes(),source.stat().st_mtime_ns)
