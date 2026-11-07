"""Standalone staging contracts: recovery, bounded work and read-only status."""
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0,str(next(p for p in Path(__file__).resolve().parents if (p/'bulk_regenerate.py').is_file())))
import bulk_regenerate as cli
import bulk_regeneration_plan as plan
import bulk_regeneration_state as state
from create_people_poster import SIZE, output_path

class FakeRenderer:
    def render_collection(self, image, style):
        return (0,0,1,1)
    def render_styles(self,image,name,styles=state.STYLES):
        result = {}
        for style in styles:
            poster = Image.new("L",SIZE,90) if style=="bw" else Image.new("RGB",SIZE,(110,70,90))
            if style!="bw": self.render_collection(poster,style)
            result[style] = poster
        return result,[]
    def render(self,image,name):
        return self.render_styles(image,name)

def png(root,name="Alice",size=(80,120)):
    path = root/name[0].upper()/"Images"/(name+".png")
    path.parent.mkdir(parents=True,exist_ok=True)
    with Image.new("RGBA",size) as image:
        ImageDraw.Draw(image).rectangle((10,0,size[0]-10,size[1]-1),fill=(180,60,100,255))
        image.save(path)
    return path

@pytest.fixture
def batch(tmp_path,monkeypatch):
    source,output = tmp_path/"transparent",tmp_path/"staging"
    png(source)
    monkeypatch.setattr(plan,"renderer_version",lambda: {"test_renderer":"1"})
    monkeypatch.setattr(cli,"_renderer",lambda: FakeRenderer())
    monkeypatch.setattr(plan,"git_state",lambda root: dict(head=None,status=None,root=None))
    monkeypatch.setattr(plan,"require_space",lambda *a: 10**12)
    return source,output

def run(source,output,*args):
    return cli.main(["--source",str(source),"--output",str(output),*args])

def snapshot(root):
    return {p.relative_to(root).as_posix():(p.stat().st_mtime_ns,p.stat().st_size,state.sha(p))
            for p in root.rglob("*") if p.is_file()}

def test_full_inventory_and_readonly_dry_run(batch,capsys):
    source,output = batch
    before = snapshot(source)
    assert run(source,output,"--dry-run")==0
    result = json.loads(capsys.readouterr().out)
    assert result["input_total"]==1 and result["planned_outputs"]==len(state.STYLES)
    assert result["read_only"] and not output.exists()
    assert snapshot(source)==before

def test_full_planning_count_15434_without_rendering(monkeypatch):
    rows = [dict(selected=True)]*15434
    value = plan.estimate_storage(rows,state.STYLES,{})
    assert sum(v["estimated_total_bytes"]//v["estimated_bytes_per_output"]
               for v in value["per_style"].values())==77170
    assert value["required_free_bytes"]>150*1024**3

def test_representative_canary(batch):
    source,_ = batch
    for name,size in [("A Very Very Very Long Person Name",(80,120)),
                      ("Zo\u00eb Garc\u00eda",(80,120)),("O'Brien",(200,100)),
                      ("Ren\u00e9e",(80,120)),("Other",(80,120))]:
        png(source,name,size)
    rows,summary = plan.inventory(source,state.STYLES,canary=5)
    chosen = [r["name"] for r in rows if r["selected"]]
    assert len(chosen)==5 and summary["planned_outputs"]==25
    assert "O'Brien" in chosen and "Zo\u00eb Garc\u00eda" in chosen
    assert any(r["attributes"]["dimensions"]!=[2000,3000] for r in rows if r["selected"])

@pytest.mark.parametrize("names",[
    ("Alice","alice"),("Zo\u00eb","Zoe\u0308"),("Name","Name_ccexpress")])
def test_unicode_case_collisions_and_exact_filenames(batch,names):
    source,_ = batch
    # Separate initial directories permit case variants on Windows.
    for i,name in enumerate(names):
        p=png(source,name)
        dest=source/str(i)/"Images"/p.name
        dest.parent.mkdir(parents=True,exist_ok=True)
        p.replace(dest)
    rows,summary = plan.inventory(source,state.STYLES)
    matching=[r for r in rows if r["name"] in names]
    if names[1].endswith("_ccexpress"):
        assert all(r["eligible"] for r in matching)
        assert matching[1]["destination"].endswith("_ccexpress.jpg")
    else:
        assert all(r["issue_kind"]=="collision" for r in matching)
        assert summary["collisions"]

def test_corrupt_source_is_quarantined_and_recorded(batch):
    source,output = batch
    (source/"A/Images/Alice.png").write_bytes(b"not png")
    assert run(source,output)==1
    status=state.inspect(output)
    assert status["state"]=="failed" and status["failed"]==len(state.STYLES)
    assert not list(output.glob("*/?/Images/*.jpg"))

def test_atomic_failure_preserves_previous_file(tmp_path,monkeypatch):
    target=tmp_path/"poster.jpg"
    target.write_bytes(b"previous")
    def fail(*a,**kw):
        raise OSError("simulated replace failure")
    monkeypatch.setattr(os,"replace",fail)
    with Image.new("RGB",SIZE) as image, pytest.raises(OSError):
        cli.atomic_poster(image,target)
    assert target.read_bytes()==b"previous"
    assert sorted(p.name for p in tmp_path.iterdir())==["poster.jpg"]

def test_low_disk_refuses_before_creating_batch(batch,monkeypatch):
    source,output=batch
    monkeypatch.setattr(plan,"require_space",lambda *a: (_ for _ in ()).throw(ValueError("Insufficient staging space")))
    assert run(source,output)==1
    assert not output.exists()

@pytest.mark.parametrize("place",["inside_source","git_destination","overlap"])
def test_forbidden_staging(batch,place):
    source,output=batch
    if place=="inside_source":
        output=source/"generated"
    elif place=="overlap":
        output=source.parent
    else:
        output.mkdir(); (output/".git").write_text("gitdir: elsewhere")
    with pytest.raises(ValueError):
        plan.check_paths(source,output,new=True)

def test_completed_status_and_noop_resume(batch,monkeypatch):
    source,output=batch
    assert run(source,output)==0
    before=snapshot(output)
    assert state.inspect(output)["completed"]==len(state.STYLES)
    def forbidden(*a,**kw):
        pytest.fail("Completed outputs must not rerender")
    monkeypatch.setattr(cli,"_renderer",forbidden)
    assert cli.main(["--resume","--output",str(output)])==0
    assert state.inspect(output)["completed"]==len(state.STYLES)
    after=snapshot(output)
    assert {k:v for k,v in after.items() if k.endswith(".jpg")}=={k:v for k,v in before.items() if k.endswith(".jpg")}
    assert state.inspect(output)["reused_validated_outputs"]==len(state.STYLES)

def test_resume_repairs_only_tampered_output_and_adopts_orphan_receipt(batch):
    source,output=batch
    assert run(source,output)==0
    original={s:state.sha(output_path(output,s,"Alice")) for s in state.STYLES}
    output_path(output,"diiivoy","Alice").write_bytes(b"tampered")
    db=state.database(output)
    with db:
        db.execute("UPDATE outputs SET status='running' WHERE style='rainier'")
    db.close()
    assert cli.main(["--resume","--output",str(output)])==0
    assert {s:state.sha(output_path(output,s,"Alice")) for s in state.STYLES}==original
    assert state.inspect(output)["reused_validated_outputs"]==len(state.STYLES)-1

def test_missing_or_forged_receipt_not_filename_trusted(batch):
    source,output=batch
    assert run(source,output)==0
    receipt=cli.receipt_path(output,"rainier/A/Images/Alice.jpg")
    value=state.read_json(receipt); value["style"]="signature"
    state.atomic_json(receipt,value)
    assert cli.validated_receipt(output,{"name":"Alice","relative":"A/Images/Alice.png",
           "source_hash":state.sha(source/"A/Images/Alice.png")},"rainier",
           state.canonical({"test_renderer":"1"}),state.inspect(output)["batch_id"]) is None
    assert cli.main(["--resume","--output",str(output)])==0
    assert state.inspect(output)["reused_validated_outputs"]==len(state.STYLES)-1

@pytest.mark.parametrize("change",["source","renderer","inventory"])
def test_resume_rejects_changed_provenance(batch,monkeypatch,change):
    source,output=batch
    assert run(source,output)==0
    if change=="source":
        png(source,"Alice",(90,130))
    elif change=="renderer":
        monkeypatch.setattr(plan,"renderer_version",lambda:{"test_renderer":"2"})
    else:
        p=output/state.STATE/"inventory.json"
        data=state.read_json(p); data["chunks"][0][0]["name"]="Forged"; state.atomic_json(p,data)
    before={p:state.sha(p) for p in output.glob("*/*/Images/*.jpg")}
    assert cli.main(["--resume","--output",str(output)])==1
    assert {p:state.sha(p) for p in before}==before

def test_multiworker_consistency(batch):
    source,first=batch
    png(source,"Bob")
    assert run(source,first,"--workers","1")==0
    second=first.with_name("parallel")
    assert run(source,second,"--workers","2")==0
    def hashes(root):
        return {p.relative_to(root).as_posix():state.sha(p) for p in root.glob("*/*/Images/*.jpg")}
    assert hashes(first)==hashes(second)
    value=state.inspect(second)
    assert value["completed"]==2*len(state.STYLES) and value["processed_inputs"]==2
    assert all(v["completed"]==2 and v["planned"]==2 for v in value["per_style"].values())

@pytest.mark.parametrize("mode",["completed","failed","interrupted","dead","reused","stale"])
def test_readonly_status_all_lifecycle_states(batch,monkeypatch,mode):
    source,output=batch
    assert run(source,output)==0
    db=state.database(output)
    with db:
        state.set_meta(db,state=mode if mode in {"completed","failed","interrupted"} else "running",
                       pid=os.getpid(),process_identity=state.process_identity(os.getpid()),
                       updated=time.time()-120 if mode=="stale" else time.time())
    db.close()
    if mode in {"dead","reused"}:
        monkeypatch.setattr(state,"process_identity",lambda p:None if mode=="dead" else "another-process")
    before=snapshot(output)
    with patch.object(state,"atomic_json",side_effect=AssertionError("status wrote")),\
         patch.object(cli,"_renderer",side_effect=AssertionError("status rendered")),\
         patch.object(subprocess,"run",side_effect=AssertionError("status called Git")),\
         state.writer_lock(output):
        started=time.monotonic(); value=state.inspect(output)
        assert time.monotonic()-started<1
    # lock file is initialized by the writer; compare all other files.
    after=snapshot(output)
    before.pop(".bulk/runner.lock",None); after.pop(".bulk/runner.lock",None)
    assert before==after
    assert value["read_only"]
    assert value["state"]==("interrupted" if mode in {"dead","reused"} else "running" if mode=="stale" else mode)
    if mode=="stale":
        assert value["process_verified"] and value["stale_progress"] and value["warnings"]

@pytest.mark.parametrize("damage",["busy","corrupt_db","partial_manifest","partial_progress"])
def test_status_partial_or_unavailable_checkpoint(batch,damage):
    source,output=batch
    assert run(source,output)==0
    db=None
    if damage=="busy":
        db=state.database(output); db.execute("BEGIN EXCLUSIVE")
    elif damage=="corrupt_db":
        (output/state.STATE/"checkpoint.sqlite3").write_bytes(b"broken sqlite")
    else:
        (output/state.STATE/("manifest.json" if damage=="partial_manifest" else "progress.json")).write_text("{")
    before=snapshot(output)
    value=state.inspect(output)
    assert value["state"]=="completed" and value["completed"]==len(state.STYLES)
    assert value["warnings"] and before==snapshot(output)
    if db: db.rollback(); db.close()

def test_status_unknown_workspace_never_creates_files(tmp_path):
    missing=tmp_path/"not-a-batch"
    assert state.inspect(missing)["state"]=="unavailable"
    assert not missing.exists()

def test_active_status_and_graceful_interrupt(batch):
    source,output=batch
    png(source,"Bob")
    entered,release,stop=threading.Event(),threading.Event(),threading.Event()
    result=[]
    real=cli.render_one
    def worker(*args):
        entered.set(); assert release.wait(5)
        return real(*args)
    def run():
        db,manifest=cli._initial(output,source,state.STYLES,{"test_renderer":"1"},
                                plan.git_state(source),None,1,2)
        rows,summary=plan.inventory(source,state.STYLES)
        manifest=cli._commit_inventory(output,db,manifest,rows,summary,plan.estimate_storage(rows,state.STYLES,{}))
        try:
            with state.writer_lock(output):
                result.append(cli.run_batch(output,db,manifest,stop=stop,worker=worker))
        finally: db.close()
    thread=threading.Thread(target=run); thread.start()
    try:
        assert entered.wait(10)
        value=state.inspect(output)
        assert value["state"]=="running" and value["process_verified"] and value["in_progress"]==len(state.STYLES)
        stop.set(); release.set()
    finally:
        release.set(); thread.join(20)
    assert result==[130]
    value=state.inspect(output)
    assert value["state"]=="interrupted" and value["completed"]==len(state.STYLES) and value["remaining"]==len(state.STYLES)
    assert cli.main(["--resume","--output",str(output)])==0
    assert state.inspect(output)["completed"]==2*len(state.STYLES)

def test_resume_recovers_manifest_replace_crash(batch):
    source,output=batch
    assert run(source,output)==0
    (output/state.STATE/"manifest.json").write_text("{}")
    assert cli.main(["--resume","--output",str(output)])==0
    assert state.inspect(output)["state"]=="completed"

def test_retry_failed_explicit(batch,monkeypatch):
    source,output=batch
    def fail():
        raise ValueError("simulated decoder failure")
    monkeypatch.setattr(cli,"_renderer",fail)
    assert run(source,output)==1
    monkeypatch.setattr(cli,"_renderer",lambda:FakeRenderer())
    assert cli.main(["--resume","--output",str(output)])==1
    assert cli.main(["--resume","--retry-failed","--output",str(output)])==0
    assert state.inspect(output)["completed"]==len(state.STYLES)

def test_real_worker_matches_merged_renderer_and_only_five_outputs(tmp_path,monkeypatch):
    from create_people_poster import Renderer
    source,output=tmp_path/"source",tmp_path/"stage"
    image=png(source,"Zo\u00eb O'Brien",(180,240))
    renderer=Renderer()
    monkeypatch.setattr(cli,"_renderer",lambda:renderer)
    item=dict(name=image.stem,relative=image.relative_to(source).as_posix(),source_hash=state.sha(image))
    receipts=cli.render_one(output,source,item,state.STYLES,"renderer","batch")
    with Image.open(image) as cutout:
        frames,_=renderer.render(cutout,image.stem)
    try:
        for receipt in receipts:
            style=receipt["style"]
            target=tmp_path/(style+".jpg")
            frames[style].save(target,"JPEG",quality=100,subsampling=0)
            assert state.sha(target)==receipt["sha256"]
            assert receipt["collection_calls"].get(style,0)==(0 if style=="bw" else 1)
    finally:
        for frame in frames.values(): frame.close()
    assert {p.name for p in output.iterdir()}=={*state.STYLES,state.STATE}

def test_powershell_launched_sigint_and_unexpected_process_exit(batch,tmp_path):
    source,output=batch
    png(source,"Bob")
    helper=tmp_path/"worker.py"
    helper.write_text(
        "import sys,signal,time\n"
        f"sys.path.insert(0,{str(Path(cli.__file__).parent)!r})\n"
        f"sys.path.insert(0,{str(Path(__file__).parent)!r})\n"
        "import bulk_regenerate as c, bulk_regeneration_plan as p\n"
        "from test_bulk_regenerate import FakeRenderer\n"
        "mode=sys.argv[3]\n"
        "class Controlled(FakeRenderer):\n"
        " def render(self,image,name):\n"
        "  if mode=='interrupt':\n"
        "   signal.raise_signal(signal.SIGINT); time.sleep(.4)\n"
        "  if mode=='wait': time.sleep(120)\n"
        "  return super().render(image,name)\n"
        "c._renderer=lambda:Controlled()\n"
        "p.renderer_version=lambda:{'test_renderer':'1'}\n"
        "p.git_state=lambda root:dict(head=None,status=None,root=None)\n"
        "p.require_space=lambda *a:10**12\n"
        # This fixture verifies an exact one-person interruption boundary.
        "args=['--output',sys.argv[2],'--progress-seconds','0.1','--workers','1']\n"
        "args+=['--resume'] if mode=='resume' else ['--source',sys.argv[1]]\n"
        "sys.exit(c.main(args))\n",encoding="utf8")
    if os.name=="nt":
        quote=lambda v:"'"+str(v).replace("'","''")+"'"
        command="& "+" ".join(map(quote,[sys.executable,helper,source,output,"interrupt"]))+"; exit $LASTEXITCODE"
        result=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command",command],
                              capture_output=True,timeout=120)
        assert result.returncode==130,result.stderr.decode(errors="replace")
        value=state.inspect(output)
        assert value["state"]=="interrupted" and value["completed"]==len(state.STYLES) and value["remaining"]==len(state.STYLES)
        result=subprocess.run([sys.executable,str(helper),str(source),str(output),"resume"],
                              capture_output=True,timeout=120)
        assert result.returncode==0,result.stderr.decode(errors="replace")
    killed=output.with_name("terminated")
    with (tmp_path/"owned-process.log").open("wb") as stream:
        process=subprocess.Popen([sys.executable,str(helper),str(source),str(killed),"wait"],
                                 stdout=stream,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                status=state.inspect(killed)
                if status.get("in_progress"):
                    break
                time.sleep(.1)
            assert status["state"]=="running" and status["in_progress"]==len(state.STYLES)
            (process.terminate if os.name=="nt" else process.kill)(); process.wait(timeout=10)
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=10)
    assert state.inspect(killed)["state"]=="interrupted"
    result=subprocess.run([sys.executable,str(helper),str(source),str(killed),"resume"],
                          capture_output=True,timeout=120)
    assert result.returncode==0,result.stderr.decode(errors="replace")
    assert state.inspect(killed)["completed"]==2*len(state.STYLES)

def test_shallow_inventory_does_not_hash_and_deep_validation_catches_crc(batch,monkeypatch):
    import bulk_source
    source,_=batch
    image=source/"A/Images/Alice.png"
    data=bytearray(image.read_bytes())
    position=data.index(b"IDAT")
    data[position+5]^=1
    image.write_bytes(data)
    def no_hash(*a):
        pytest.fail("Metadata-only inventory read a full source hash")
    with monkeypatch.context() as context:
        context.setattr(bulk_source,"content_hashes",no_hash)
        rows,_=plan.inventory(source,state.STYLES,deep=False)
        assert rows[0]["source_hash"]=="" and rows[0]["eligible"]
    rows,_=plan.inventory(source,state.STYLES,deep=True)
    assert not rows[0]["eligible"] and rows[0]["issue_kind"]=="invalid_input"

@pytest.mark.parametrize("filename",["manifest.json","progress.json"])
def test_status_structurally_corrupt_snapshot(batch,filename):
    source,output=batch
    assert run(source,output)==0
    (output/state.STATE/filename).write_text("[]")
    before=snapshot(output)
    value=state.inspect(output)
    assert value["state"]=="completed" and value["warnings"]
    assert before==snapshot(output)

def test_inventory_15434_records_preserves_guarded_writer_limit(tmp_path):
    root=tmp_path/"batch"
    source=tmp_path/"source"; source.mkdir()
    rows=[dict(number=i,name="Person"+str(i),relative="P/Images/Person"+str(i)+".png",
               source_hash="a"*64,selected=False,eligible=True,issue="",issue_kind="") for i in range(15434)]
    db,manifest=cli._initial(root,source,state.STYLES,{"test_renderer":"1"},{},None,1,len(rows))
    summary=dict(input_total=len(rows),eligible_image_count=len(rows),selected_input_total=0)
    try:
        cli._commit_inventory(root,db,manifest,rows,summary,plan.estimate_storage(rows,state.STYLES,{}))
    finally:
        db.close()
    assert state.read_inventory(root)==rows
    value=state.read_json(root/state.STATE/"inventory.json")
    value["count"]+=1
    state.atomic_json(root/state.STATE/"inventory.json",value)
    with pytest.raises(ValueError,match="count/type"):
        state.read_inventory(root)

def test_inventory_import_does_not_initialize_sync_or_model_directories(tmp_path):
    target=tmp_path/"must-not-exist"
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PEOPLE_CONFIG_DIR=str(target))
    command=("import sys; sys.path.insert(0,"+repr(str(Path(cli.__file__).parent))+"); "
             "import bulk_regeneration_plan,bulk_source; assert 'sync_people_images' not in sys.modules; "
             "assert not any(n in sys.modules for n in ['torch','rembg','ddcolor','tmdbapis'])")
    result=subprocess.run([sys.executable,"-c",command],capture_output=True,env=env,timeout=30)
    assert result.returncode==0,result.stderr.decode(errors="replace")
    assert not target.exists()


@pytest.mark.parametrize('styles',[('diiivoy',),state.STYLES])
def test_readonly_validate_accepts_single_and_multiple_styles(batch,styles,capsys):
    source,output=batch
    assert run(source,output,'--styles',*styles)==0
    before=snapshot(output);capsys.readouterr()
    assert cli.main(['--validate','--output',str(output),'--json'])==0
    value=json.loads(capsys.readouterr().out)
    assert value['valid'] and value['verified']==len(styles) and value['read_only']
    assert not value['publication_authorized']
    assert snapshot(output)==before


@pytest.mark.parametrize('damage',['jpeg','receipt','inventory','checkpoint','extra_jpeg'])
def test_readonly_validate_detects_damage_without_repair(batch,damage):
    source,output=batch
    assert run(source,output,'--styles','diiivoy')==0
    poster=next(output.glob('*/*/Images/*.jpg'))
    if damage=='jpeg':poster.write_bytes(b'invalid JPEG')
    elif damage=='receipt':
        path=cli.receipt_path(output,poster.relative_to(output).as_posix())
        value=state.read_json(path);value['batch_id']='wrong';state.atomic_json(path,value)
    elif damage=='inventory':
        path=output/state.STATE/'inventory.json';value=state.read_json(path)
        value['chunks'][0][0]['name']='Changed';state.atomic_json(path,value)
    elif damage=='extra_jpeg':poster.with_name('Unexpected.jpg').write_bytes(poster.read_bytes())
    else:
        with sqlite3.connect(output/state.STATE/'checkpoint.sqlite3') as db:
            db.execute("UPDATE outputs SET sha256='changed'")
    before=snapshot(output)
    assert cli.main(['--validate','--output',str(output)])==1
    assert snapshot(output)==before


def test_readonly_validate_refuses_active_writer(batch):
    source,output=batch
    assert run(source,output,'--styles','diiivoy')==0
    with state.writer_lock(output):
        before=snapshot(output)
        assert cli.main(['--validate','--output',str(output)])==2
        assert snapshot(output)==before


def test_bulk_default_workers_is_two():
    assert cli.parser().parse_args(['--output','batch']).workers==2
