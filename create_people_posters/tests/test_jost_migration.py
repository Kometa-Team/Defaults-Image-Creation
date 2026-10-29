import copy
import hashlib
from io import BytesIO, TextIOWrapper
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jost_migration as jm
from jost_migration_report import comparison_report
from create_people_poster import Renderer, normalize_cutout, shifted_cutout, FONTS, SIZE, digest
from people_github import GitHubError, REPOSITORIES
from people_remote_inventory import blob_sha
from test_people_github import FakeGitHub


def cutout(size=(100, 150), high=False):
    image = Image.new("RGBA", size)
    ImageDraw.Draw(image).ellipse((size[0]//4, size[1]//2 if high else 0, size[0]*3//4, size[1]-1), fill=(160, 60, 90, 255))
    return image


@pytest.fixture(scope="module")
def renderer():
    return Renderer()


@pytest.mark.parametrize("styles", [("diiivoy",), ("diiivoycolor",), jm.STYLES])
@pytest.mark.parametrize("kind", ["raw", "normalized", "high_margin"])
def test_selective_exactly_matches_normal_renderer(renderer, styles, kind, monkeypatch):
    image = cutout((200,100) if kind == "high_margin" else (100,150), kind == "high_margin")
    if kind == "normalized":
        image = normalize_cutout(image)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("No external rendering/inference"))
    all_styles, warnings = renderer.render(image, "Zo\u00eb Garc\u00eda1")
    selected, notes = renderer.render_styles(image, "Zo\u00eb Garc\u00eda1", styles)
    assert set(selected) == set(styles) and notes == warnings
    for style in styles:
        assert selected[style].mode == "RGB" and selected[style].size == SIZE
        assert selected[style].tobytes() == all_styles[style].tobytes()
    normalized = normalize_cutout(image)
    assert normalized.tobytes() == normalize_cutout(normalized).tobytes()
    assert shifted_cutout(normalized).tobytes() == shifted_cutout(normalize_cutout(normalized)).tobytes()


@pytest.mark.parametrize("styles", [(), ("bw",), ("original",), ("transparent",), ("diiivoy", "diiivoy")])
def test_selective_rejects_unrelated_styles(renderer, styles):
    with pytest.raises(ValueError, match="only diiivoy"):
        renderer.render_styles(cutout(), "Person", styles)


def test_selective_never_draws_other_style_labels(renderer, monkeypatch):
    original = renderer.label
    calls = []
    def label(text, font, box, pointsize=None, **kwargs):
        calls.append((font, pointsize))
        return original(text, font, box, pointsize, **kwargs)
    monkeypatch.setattr(renderer, "label", label)
    renderer.render_styles(cutout(), "BoA")
    assert calls == [(FONTS[2],190), (FONTS[2],190)]


class MigrationGitHub(FakeGitHub):
    def request(self, method, path, payload=None):
        if method == "POST" and path.endswith("/git/trees") and any(r["sha"] is None for r in payload["tree"]):
            self.calls.append((method,path,payload))
            tree = self.new_sha()
            self.trees[tree] = copy.deepcopy(self.trees[payload["base_tree"]])
            for row in payload["tree"]:
                if row["sha"] is None:
                    self.trees[tree].pop(row["path"],None)
                else:
                    self.trees[tree][row["path"]] = dict(row,size=len(self.blobs[row["sha"]]))
            return {"sha":tree}
        return super().request(method,path,payload)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    for key in ("JOST_MIGRATION_TRANSPARENT_DIR", "POSTER_FONT_DIR", "POSTER_ASSET_DIR", "PEOPLE_SANDBOX_CONFIG"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PEOPLE_GITHUB_TARGET","production")
    monkeypatch.setenv("UPDATE_TRIGGER_READMES","true")
    monkeypatch.setenv("UPDATE_REQUIRE_README_DISPATCH","true")
    source = tmp_path / "transparent"
    source.mkdir()
    client = MigrationGitHub()
    migration = jm.Migration(tmp_path / "migration", client, source_dir=source)
    yield migration, client, source
    migration.close()


def stage(source, name="Person", folder=None):
    path = source / (folder or name[0].upper()) / "Images" / (name+".png")
    path.parent.mkdir(parents=True,exist_ok=True)
    cutout().save(path)
    return path


def existing(client, name="Person", styles=jm.STYLES):
    data = BytesIO()
    Image.new("RGB",SIZE,(30,40,60)).save(data,"JPEG")
    blob = blob_sha(data.getvalue())
    client.blobs[blob] = data.getvalue()
    for style in styles:
        repo = jm.TARGETS[style]
        files = copy.deepcopy(client.trees[client.commits[client.heads[repo]]])
        files[name[0].upper()+"/Images/"+name+".jpg"] = {"sha":blob,"type":"blob","mode":"100644","size":len(data.getvalue())}
        client.advance(repo,files)
    return blob


def ready(setup):
    migration, client, source = setup
    stage(source)
    old = existing(client)
    mid = migration.scan(source)
    migration.render(mid)
    report = comparison_report(migration,mid)
    return mid, report["review_sha256"], old


def publish(migration, mid, token):
    migration.publish(mid,dry_run=False,confirm=mid,reviewed=token)


def test_inventory_readonly_and_unknown_provenance(setup):
    migration, client, source = setup
    path = stage(source,"Zo\u00eb Garc\u00eda1")
    old = existing(client,"Zo\u00eb Garc\u00eda1")
    before = (digest(path),path.stat().st_mtime_ns)
    mid = migration.scan(source,1)
    manifest = migration.load(mid)
    assert manifest["items"][0]["destinations"]["diiivoy"]["previous_blob"] == old
    assert manifest["items"][0]["name"] == "Zo\u00eb Garc\u00eda1"
    assert all(call[0] == "GET" for call in client.calls)
    assert migration.export(mid)["classification"] == {"confirmed_pre_jost":0,"confirmed_jost":0,"unknown":2}
    assert before == (digest(path),path.stat().st_mtime_ns)


@pytest.mark.parametrize("kind",["case","unicode"])
def test_collisions_fail_before_remote_access(setup,kind):
    migration,client,source=setup
    stage(source,"Person" if kind=="case" else "Zo\u00eb", "A")
    stage(source,"person" if kind=="case" else "Zoe\u0308", "B")
    with pytest.raises(ValueError,match="Ambiguous"):
        migration.scan(source)
    assert not client.calls


def test_missing_empty_and_overlapping_source(setup):
    migration,client,source=setup
    with pytest.raises(ValueError,match="does not exist"):
        migration.scan(source/"missing")
    with pytest.raises(ValueError,match="empty"):
        migration.scan(source)
    with pytest.raises(ValueError,match="disjoint"):
        jm.Migration(source/"bad",client,source_dir=source)
    assert not (source/"bad").exists()


def test_render_partial_corrupt_and_wrong_format(setup):
    migration,client,source=setup
    stage(source,"Good")
    stage(source,"Broken").write_bytes(b"invalid")
    disguised=stage(source,"FakePNG")
    Image.new("RGB",(100,150),"red").save(disguised,"JPEG")
    mid=migration.scan(source)
    before={p: (digest(p),p.stat().st_mtime_ns) for p in source.rglob("*.png")}
    migration.render(mid)
    result=migration.export(mid)
    assert result["statuses"] == {"failed":2,"validated":1}
    assert before == {p:(digest(p),p.stat().st_mtime_ns) for p in before}
    assert set(p.parent.parent.parent.name for p in migration.job(mid).rglob("*.jpg")) == set(jm.STYLES)


def test_manifest_source_and_renderer_changes_require_reconciliation(setup,monkeypatch):
    migration,client,source=setup
    path=stage(source)
    mid=migration.scan(source)
    path.write_bytes(b"changed")
    migration.render(mid)
    assert migration.export(mid)["statuses"] == {"conflict":1}
    manifest=migration.job(mid)/"manifest.json"
    before=manifest.read_bytes()
    manifest.write_text("{}",encoding="utf-8")
    with pytest.raises(ValueError,match="integrity"):
        migration.load(mid)
    manifest.write_bytes(before)
    monkeypatch.setattr(jm,"migration_fingerprint",lambda:{"changed":True})
    with pytest.raises(ValueError,match="fingerprint changed"):
        migration.load(mid)


@pytest.mark.parametrize("path",["../escape.png","A/Images/../../escape.png","/absolute.png","A\\Images\\escape.png"])
def test_manifest_path_traversal_is_rejected(setup,path):
    migration,client,source=setup
    stage(source)
    mid=migration.scan(source)
    manifest=migration.load(mid)
    row=dict(manifest["items"][0],relative=path)
    with pytest.raises(ValueError):
        migration.source(manifest,row)


def test_symlink_source_is_not_followed(setup,tmp_path):
    migration,client,source=setup
    directory=source/"A/Images"
    directory.mkdir(parents=True)
    target=tmp_path/"external.png"
    cutout().save(target)
    try:
        (directory/"Alias.png").symlink_to(target)
    except OSError:
        pytest.skip("Account cannot create symlinks")
    with pytest.raises(ValueError,match="Symlink"):
        migration.scan(source)


@pytest.mark.parametrize("repo",[r for r in REPOSITORIES.values() if r not in jm.TARGETS.values()])
def test_transport_blocks_unrelated_repositories(repo):
    transport=jm.MigrationTransport(MigrationGitHub(),True)
    with pytest.raises(ValueError,match="allowlisted"):
        transport.request("POST",f"/repos/{repo}/git/blobs",{})


@pytest.mark.parametrize("method,route,payload",[
    ("PATCH","git/refs/heads/master",{"force":True}),
    ("PATCH","git/refs/heads/main",{"force":False}),
    ("DELETE","git/refs/heads/master",{}),
    ("POST","git/refs",{}),
    ("GET","contents/A%2fImages",None),
    ("POST","git/trees",{"base_tree":"x","tree":[{"path":"unrelated.jpg","mode":"100644","type":"blob","sha":"bad"}]}),
])
def test_transport_blocks_unsafe_routes_and_tree_changes(method,route,payload):
    transport=jm.MigrationTransport(MigrationGitHub(),True)
    with pytest.raises(ValueError):
        transport.request(method,"/repos/"+jm.TARGETS["diiivoy"]+"/"+route,payload)


def test_report_dry_run_and_explicit_approval(setup):
    migration,client,source=setup
    mid,token,old=ready(setup)
    assert migration.review(mid,token)["font"]["weight"] == 260
    client.calls.clear()
    plan=migration.publish(mid)
    assert len(plan)==2 and all(row["action"]=="replace" for row in plan)
    assert all(call[0]=="GET" for call in client.calls)
    with pytest.raises(ValueError,match="confirm"):
        migration.publish(mid,dry_run=False)
    with pytest.raises(ValueError,match="token"):
        migration.publish(mid,dry_run=False,confirm=mid,reviewed="wrong")


def test_partial_publication_resume_does_not_duplicate_commits(setup):
    migration,client,source=setup
    mid,token,old=ready(setup)
    client.fail_repo=jm.TARGETS["diiivoycolor"]
    client.calls.clear()
    with pytest.raises(GitHubError,match="Partial migration"):
        publish(migration,mid,token)
    assert sum(row["state"]=="verified" for row in migration.outputs(mid))==1
    assert len([c for c in client.calls if c[0]=="PATCH"])==1
    client.fail_repo=None
    client.calls.clear()
    publish(migration,mid,token)
    assert len([c for c in client.calls if c[0]=="PATCH"])==1
    assert len([c for c in client.calls if "dispatches" in c[1]])==2
    client.calls.clear()
    publish(migration,mid,token)
    assert not any(c[0]!="GET" for c in client.calls)
    second=migration.scan(source)
    assert migration.export(second)["selected"]==0
    assert migration.export(second)["classification"]["confirmed_jost"]==2
    assert not any(row["needs_rebuild"] for row in migration.export(second)["destinations"])


def test_new_scan_does_not_reuse_receipts_from_an_old_renderer(setup,monkeypatch):
    migration,client,source=setup
    mid,token,old=ready(setup)
    publish(migration,mid,token)
    monkeypatch.setattr(jm,"migration_fingerprint",lambda:{"changed":True})
    second=migration.scan(source)
    result=migration.export(second)
    assert result["selected"]==1
    assert result["classification"]["unknown"]==2
    assert all(row["needs_rebuild"] for row in result["destinations"])


def test_unexpected_destination_edit_blocks_publication(setup):
    migration,client,source=setup
    mid,token,old=ready(setup)
    existing(client,styles=("diiivoy",))
    repo=jm.TARGETS["diiivoy"]
    files=copy.deepcopy(client.trees[client.commits[client.heads[repo]]])
    files["P/Images/Person.jpg"]["sha"]="c"*40
    client.advance(repo,files)
    with pytest.raises(GitHubError,match="Partial migration"):
        publish(migration,mid,token)
    assert next(r for r in migration.outputs(mid) if r["style"]=="diiivoy")["state"]=="conflict"


def test_crash_after_ref_update_is_idempotent_on_resume(setup,monkeypatch):
    migration,client,source=setup
    mid,token,old=ready(setup)
    original=client.request
    crash=[True]
    def request(method,path,payload=None):
        result=original(method,path,payload)
        if method=="PATCH" and crash[0]:
            crash[0]=False
            raise SystemExit("simulated process interruption")
        return result
    monkeypatch.setattr(client,"request",request)
    with pytest.raises(SystemExit):
        publish(migration,mid,token)
    client.calls.clear()
    publish(migration,mid,token)
    assert len([c for c in client.calls if c[0]=="PATCH"])==1


@pytest.mark.parametrize("existed",[True,False])
def test_rollback_restores_old_blobs_or_removes_new_paths(setup,existed):
    migration,client,source=setup
    if existed:
        mid,token,old=ready(setup)
    else:
        stage(source)
        mid=migration.scan(source)
        migration.render(mid)
        token=comparison_report(migration,mid)["review_sha256"]
        old=None
    publish(migration,mid,token)
    client.calls.clear()
    assert len(migration.rollback(mid))==2
    assert all(c[0]=="GET" for c in client.calls)
    with pytest.raises(ValueError,match="confirm"):
        migration.rollback(mid,dry_run=False)
    migration.rollback(mid,dry_run=False,confirm="rollback:"+mid)
    assert all(row["rollback_state"]=="rolled_back" for row in migration.outputs(mid))
    for style in jm.STYLES:
        entry=migration.inventory.lookup(style,"P/Images/Person.jpg")
        assert (entry["sha"] if entry else None)==old
    client.calls.clear()
    migration.rollback(mid,dry_run=False,confirm="rollback:"+mid)
    assert not any(c[0]!="GET" for c in client.calls)


def test_cleanup_requires_verified_receipts_and_preserves_sources_reports(setup):
    migration,client,source=setup
    mid,token,old=ready(setup)
    before={p:(digest(p),p.stat().st_mtime_ns) for p in source.rglob("*.png")}
    assert migration.cleanup(mid,False,0)==[]
    publish(migration,mid,token)
    manifest=migration.load(mid)
    target=migration.target(mid,manifest["items"][0],"diiivoy")
    assert migration.cleanup(mid,True,0) and target.exists()
    assert migration.cleanup(mid,False,0) and not target.exists()
    assert (migration.job(mid)/"manifest.json").exists()
    assert (migration.root/"reports"/mid/"index.html").exists()
    assert before=={p:(digest(p),p.stat().st_mtime_ns) for p in before}
    assert migration.cleanup(mid,False,0)==[]


def test_changed_output_prevents_cleanup(setup):
    migration,client,source=setup
    mid,token,old=ready(setup)
    publish(migration,mid,token)
    path=migration.target(mid,migration.load(mid)["items"][0],"diiivoy")
    path.write_bytes(b"manual edit")
    with pytest.raises(ValueError,match="changed"):
        migration.cleanup(mid,False,0)
    assert path.exists()


def test_explicit_collision_exclusion_records_both_without_modifying_source(setup):
    migration,client,source=setup
    stage(source,"Person","A")
    stage(source,"person","B")
    stage(source,"Unambiguous")
    mid=migration.scan(source,exclude_ambiguous=True)
    manifest=migration.load(mid)
    assert len(manifest["items"])==3
    assert sum(r["selected"] for r in manifest["items"])==1
    assert migration.export(mid)["excluded_conflicts"]==2
    assert len(list(source.rglob("*.png")))==3


def test_distinct_whitespace_filenames_are_preserved(setup):
    migration,client,source=setup
    stage(source,"Dorothy  Steel")
    stage(source,"Dorothy Steel")
    mid=migration.scan(source)
    assert {r["destination"] for r in migration.load(mid)["items"]} == {"D/Images/Dorothy  Steel.jpg","D/Images/Dorothy Steel.jpg"}


def test_resume_after_closing_database_uses_same_manifest(setup):
    migration,client,source=setup
    mid,token,old=ready(setup)
    before=migration.load(mid)
    root=migration.root
    migration.close()
    reopened=jm.Migration(root,client)
    try:
        stage(source,"Added After Scan")
        assert reopened.load(mid)==before
        assert reopened.render(mid)["attempted"]==0
        publish(reopened,mid,token)
        assert all(r["state"]=="verified" for r in reopened.outputs(mid))
    finally:
        reopened.close()
        # Restore an open connection for fixture teardown.
        replacement=jm.Migration(root,client)
        migration.ledger,migration.db,migration.inventory=replacement.ledger,replacement.db,replacement.inventory


def test_interrupted_cleanup_can_resume_without_deleting_reports(setup,monkeypatch):
    migration,client,source=setup
    mid,token,old=ready(setup)
    publish(migration,mid,token)
    original=Path.unlink
    count=[0]
    def unlink(path,*args,**kwargs):
        if path.suffix==".jpg":
            count[0]+=1
            if count[0]==2:
                raise OSError("simulated interrupted cleanup")
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,"unlink",unlink)
    with pytest.raises(OSError,match="interrupted"):
        migration.cleanup(mid,False,0)
    monkeypatch.setattr(Path,"unlink",original)
    assert migration.cleanup(mid,False,0)
    assert (migration.root/"reports"/mid/"review.json").exists()
    assert migration.review(mid,token)["migration"]==mid


def test_rollback_blocks_intervening_content_change(setup):
    migration,client,source=setup
    mid,token,old=ready(setup)
    publish(migration,mid,token)
    repo=jm.TARGETS["diiivoy"]
    files=copy.deepcopy(client.trees[client.commits[client.heads[repo]]])
    files["P/Images/Person.jpg"]["sha"]="f"*40
    client.advance(repo,files)
    client.calls.clear()
    with pytest.raises(GitHubError,match="Intervening"):
        migration.rollback(mid,dry_run=False,confirm="rollback:"+mid)
    assert all(c[0]=="GET" for c in client.calls)


def test_default_cli_is_status_not_publish(tmp_path,monkeypatch,capsys):
    import migrate_diiivoy_jost as cli
    monkeypatch.setattr(cli,"load_dotenv",lambda *a,**k:None)
    monkeypatch.delenv("JOST_MIGRATION_TRANSPARENT_DIR",raising=False)
    monkeypatch.setattr(jm.Migration,"publish",lambda *a,**k:pytest.fail("Unexpected publication"))
    assert cli.main(["--workspace",str(tmp_path/"new")])==0
    assert "[]" in capsys.readouterr().out


def test_cli_supports_unicode_names_with_legacy_windows_streams(tmp_path,monkeypatch):
    import migrate_diiivoy_jost as cli
    monkeypatch.setattr(cli,"load_dotenv",lambda *a,**k:None)
    monkeypatch.delenv("JOST_MIGRATION_TRANSPARENT_DIR",raising=False)
    stdout,stderr=BytesIO(),BytesIO()
    streams=[TextIOWrapper(stdout,encoding="cp1252"),TextIOWrapper(stderr,encoding="cp1252")]
    with monkeypatch.context() as context:
        context.setattr(sys,"stdout",streams[0])
        context.setattr(sys,"stderr",streams[1])
        assert cli.main(["--workspace",str(tmp_path/"migration")])==0
        for stream in streams:
            print("\ubc15\uc9c0",file=stream,flush=True)
        assert "\ubc15\uc9c0".encode("utf-8") in stdout.getvalue()
        assert stderr.getvalue().decode("utf-8").splitlines()==["\ubc15\uc9c0"]


def test_unrelated_concurrent_commit_is_preserved_and_other_repos_untouched(setup,monkeypatch):
    migration,client,source=setup
    mid,token,old=ready(setup)
    untouched={repo:head for repo,head in client.heads.items() if repo not in jm.TARGETS.values()}
    original=client.request
    raced=[False]
    def request(method,path,payload=None):
        result=original(method,path,payload)
        if method=="POST" and path.endswith("/git/commits") and not raced[0]:
            raced[0]=True
            repo=path.split('/repos/')[1].rsplit('/git/',1)[0]
            files=copy.deepcopy(client.trees[client.commits[client.heads[repo]]])
            files['sentinel.txt']={'sha':'a'*40,'type':'blob','mode':'100644','size':1}
            client.advance(repo,files)
        return result
    monkeypatch.setattr(client,"request",request)
    publish(migration,mid,token)
    assert all(client.heads[repo]==head for repo,head in untouched.items())
    assert any('sentinel.txt' in client.trees[client.commits[client.heads[repo]]] for repo in jm.TARGETS.values())
    assert all('README.md' in client.trees[client.commits[client.heads[repo]]] for repo in jm.TARGETS.values())


def test_bad_github_blob_hash_is_not_accepted(setup,monkeypatch):
    migration,client,source=setup
    mid,token,old=ready(setup)
    original=client.request
    def request(method,path,payload=None):
        result=original(method,path,payload)
        if method=="POST" and path.endswith('/git/blobs'):
            return {'sha':'f'*40}
        return result
    monkeypatch.setattr(client,"request",request)
    with pytest.raises(GitHubError,match="unexpected blob"):
        publish(migration,mid,token)
    assert not any(r['state']=='verified' for r in migration.outputs(mid))


def test_rollback_readme_failure_can_be_retried_without_more_image_commits(setup,monkeypatch):
    migration,client,source=setup
    mid,token,old=ready(setup)
    publish(migration,mid,token)
    original=client.request
    fail=[True]
    def request(method,path,payload=None):
        if method=='POST' and 'dispatches' in path and fail[0]:
            raise GitHubError('dispatch unavailable',503)
        return original(method,path,payload)
    monkeypatch.setattr(client,'request',request)
    with pytest.raises(GitHubError,match='README'):
        migration.rollback(mid,dry_run=False,confirm='rollback:'+mid)
    fail[0]=False
    client.calls.clear()
    migration.rollback(mid,dry_run=False,confirm='rollback:'+mid)
    assert not any(c[0]=='PATCH' for c in client.calls)
    assert len([c for c in client.calls if 'dispatches' in c[1]])==2


def test_identical_remote_content_is_not_committed_or_rolled_back(setup):
    migration,client,source=setup
    mid,token,old=ready(setup)
    for row in migration.outputs(mid):
        repo=jm.TARGETS[row['style']]
        files=copy.deepcopy(client.trees[client.commits[client.heads[repo]]])
        files['P/Images/Person.jpg']={'sha':row['blob'],'type':'blob','mode':'100644','size':10}
        client.advance(repo,files)
        # Identical remote publication includes indexes as well as image bytes.
        client.generate_readmes(repo)
    client.calls.clear()
    publish(migration,mid,token)
    assert all(c[0]=='GET' for c in client.calls)
    assert all(row['rollback_state']=='not_changed' for row in migration.outputs(mid))
    client.calls.clear()
    assert migration.rollback(mid,dry_run=False,confirm='rollback:'+mid)==[]
    assert all(c[0]=='GET' for c in client.calls)


def test_full_rollout_reuses_verified_sample_and_cleans_generated_batches(setup,monkeypatch):
    from run_jost_migration import run_batches
    import run_jost_migration as runner
    migration,client,source=setup
    sample,token,old=ready(setup)
    publish(migration,sample,token)
    path=stage(source,"Second")
    with Image.open(path) as image:
        normalized=normalize_cutout(image)
    normalized.save(path)
    before=(digest(path),path.stat().st_mtime_ns)
    mid=migration.scan(source)
    monkeypatch.setattr(runner.time,"sleep",lambda _:None)
    stop=migration.root/'state/rollout.stop'
    stop.write_text('{}',encoding='utf-8')
    state=run_batches(migration,mid,sample,token,1,{})
    assert state['status']=='stopped'
    assert migration.export(mid)['statuses']=={'discovered':1}
    stop.unlink()
    result=run_batches(migration,mid,sample,token,1,state)
    assert result["status"]=="completed"
    assert migration.export(mid)["statuses"]=={"verified":1}
    assert not list(migration.job(mid).rglob("*.jpg"))
    assert before==(digest(path),path.stat().st_mtime_ns)
    assert migration.review(mid,token,sample)["outputs"]
    writes=len([r for r in client.calls if r[0]=="PATCH"])
    run_batches(migration,mid,sample,token,1,result)
    assert len([r for r in client.calls if r[0]=="PATCH"])==writes


def test_full_rollout_holds_noncanonical_and_skips_missing_glyphs(setup,monkeypatch):
    from run_jost_migration import run_batches
    import run_jost_migration as runner
    migration,client,source=setup
    sample,token,old=ready(setup)
    publish(migration,sample,token)
    stage(source,"Other")
    stage(source,"\ubc15\uc9c0")
    mid=migration.scan(source)
    monkeypatch.setattr(runner.time,"sleep",lambda _:None)
    client.calls.clear()
    result=run_batches(migration,mid,sample,token,2,{})
    assert result["status"]=="completed_with_exceptions"
    assert result["counts"]=={"review_required":1,"skipped":1}
    assert not any(r[0]!="GET" for r in client.calls)
    assert len(list(migration.job(mid).rglob("*.jpg")))==2


def test_full_rollout_rejects_unverified_or_changed_sample(setup):
    migration,client,source=setup
    sample,token,old=ready(setup)
    stage(source,"Other")
    mid=migration.scan(source)
    with pytest.raises(ValueError,match="verified publication"):
        migration.review(mid,token,sample)
    publish(migration,sample,token)
    mid=migration.scan(source)
    assert migration.review(mid,token,sample)
    next(source.rglob("Person.png")).write_bytes(b"changed")
    with pytest.raises(ValueError,match="changed"):
        migration.review(mid,token,sample)


def test_unattended_render_does_not_retry_failed_entries(setup):
    migration,client,source=setup
    stage(source,"Bad").write_bytes(b"invalid")
    mid=migration.scan(source)
    assert migration.render(mid,retry_failed=False)["attempted"]==1
    stage(source,"Good")
    assert migration.render(mid,retry_failed=False)["attempted"]==0


def test_rollout_quarantines_remote_conflict_and_continues_other_people(setup,monkeypatch):
    from run_jost_migration import run_batches
    import run_jost_migration as runner
    migration,client,source=setup
    sample,token,old=ready(setup)
    publish(migration,sample,token)
    for name in ("Other","Zed"):
        path=stage(source,name)
        with Image.open(path) as image:
            normalized=normalize_cutout(image)
        normalized.save(path)
    existing(client,"Other")
    mid=migration.scan(source)
    repo=jm.TARGETS["diiivoy"]
    files=copy.deepcopy(client.trees[client.commits[client.heads[repo]]])
    files['O/Images/Other.jpg']['sha']='f'*40
    client.advance(repo,files)
    monkeypatch.setattr(runner.time,"sleep",lambda _:None)
    result=run_batches(migration,mid,sample,token,1,{})
    assert result["status"]=="completed_with_exceptions"
    assert result["counts"]=={"publication_problem":1,"verified":1}
    assert migration.inventory.lookup("diiivoy","O/Images/Other.jpg")["sha"]=='f'*40
    assert len(list(migration.job(mid).rglob('*.jpg')))==2
    problems=json.loads((migration.root/'reports'/mid/'problems.json').read_text())
    assert problems['problems'][0]['name']=='Other'
    assert problems['quarantined_units']


def test_rollout_holds_changed_source_and_finishes_healthy_people(setup,monkeypatch):
    from run_jost_migration import run_batches
    import run_jost_migration as runner
    migration,client,source=setup
    sample,token,old=ready(setup)
    publish(migration,sample,token)
    changed=stage(source,'Other')
    healthy=stage(source,'Zed')
    with Image.open(healthy) as image:
        normalized=normalize_cutout(image)
    normalized.save(healthy)
    mid=migration.scan(source)
    changed.write_bytes(b'changed since full scan')
    monkeypatch.setattr(runner.time,'sleep',lambda _:None)
    result=run_batches(migration,mid,sample,token,1,{})
    assert result['counts']=={'conflict':1,'verified':1}
    assert result['status']=='completed_with_exceptions'
    problems=json.loads((migration.root/'reports'/mid/'problems.json').read_text())
    assert problems['problems'][0]['name']=='Other'
    assert changed.read_bytes()==b'changed since full scan'
