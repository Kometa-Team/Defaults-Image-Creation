import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import orchestrator as orch


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    environment = dict(os.environ)
    for key in list(os.environ):
        if key.startswith(("PEOPLE_", "SEL_", "ORCH_", "REMOVE_BG_", "COLORIZE_", "EDGE_CHOP_")):
            os.environ.pop(key)
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setattr(orch, "CONFIG_DIR", config)
    monkeypatch.setattr(orch, "STATE_DIR", config / ".orch")
    monkeypatch.setattr(orch, "LOCK_FILE", config / ".orch/run.lock")
    monkeypatch.setattr(orch, "load_env_or_bootstrap", lambda: None)
    monkeypatch.setattr(orch, "background_fingerprint", lambda: {"engine": "adobe"})
    monkeypatch.setattr(orch, "background_checkpoint_changed", lambda _: False)
    monkeypatch.setattr(orch, "ps_exe", lambda: "pwsh")
    try:
        yield config
    finally:
        os.environ.clear()
        os.environ.update(environment)


def invoke(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["orchestrator.py", *args])
    return orch.main()


def test_api_mode_without_clones_preserves_step_names(isolated, monkeypatch):
    calls = []
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (calls.append(argv) or (0, None, None)))
    invoke(monkeypatch, "--publish-mode", "github_api", "--workspace-mode", "persistent", "--redo", "sync_images")
    api = [call for call in calls if "publish_people_github.py" in call]
    assert [call[call.index("--op") + 1] for call in api] == ["validate", "prepare", "push"]
    assert all(call[call.index("--branch") + 1] == "master" for call in api)
    assert not any("ensure_people_repo.py" in call or "update_people_repos.py" in call for call in calls)
    assert (isolated / ".orch/sync_images.done.json").exists()


def test_api_dry_run_not_checkpointed_as_publication(isolated, monkeypatch):
    calls = []
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (calls.append(argv) or (0, None, None)))
    invoke(monkeypatch, "--publish-mode", "github_api", "--workspace-mode", "persistent", "--redo", "sync_images", "--dry-run")
    assert all("--dry-run" in call for call in calls)
    assert not (isolated / ".orch/sync_images.done.json").exists()


def test_api_rejects_local_readme_generation(isolated, monkeypatch):
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--publish-mode", "github_api", "--generate-readmes")
    assert error.value.code == 2


def test_batch_paths_and_checkpoints_are_isolated(isolated, monkeypatch):
    (isolated / "people_list.txt").write_text("42|Ada\n", encoding="utf-8")
    monkeypatch.setenv("TMDB_KEY", "NOT_A_REAL_TMDB_FIXTURE_SECRET_20261024")
    monkeypatch.setattr(orch, "build_colorize_command", lambda py: [py, "colorize_noncolor_ddcolor.py"])
    calls = []
    def run(title, argv, **kwargs):
        calls.append(argv)
        if "tmdb_people.py" in argv:
            path = orch.CONFIG_DIR / "posters/Ada-42.jpg"
            path.write_bytes(b"source")
        if "prep_people_dirs.py" in argv:
            path = orch.CONFIG_DIR / "people_dirs/Downloads/Ada.jpg"
            path.write_bytes(b"source")
        return 0, None, None
    monkeypatch.setattr(orch, "run_cmd", run)
    invoke(monkeypatch, "--publish-mode", "github_api", "--workspace-mode", "batch", "--new-batch",
           "--people-list", str(isolated / "people_list.txt"), "--stop-after", "prep_dirs")
    workspace = orch.CONFIG_DIR
    assert workspace.parent == isolated / "jobs"
    assert (workspace / ".orch/tmdb.done.json").exists()
    assert not (isolated / ".orch/tmdb.done.json").exists()
    assert not any("scan_kometa_logs.py" in call or "find_and_download_missing_people.py" in call for call in calls)
    assert Path(os.environ["SEL_ORIG_DIR"]).is_relative_to(workspace)
    assert not Path(os.environ["REMBG_HOME"]).is_relative_to(workspace)
    assert not (workspace / ".active").exists()
    assert not orch.LOCK_FILE.exists()


def test_batch_model_failure_preserves_sources(isolated, monkeypatch):
    (isolated / "people_list.txt").write_text("42|Ada\n", encoding="utf-8")
    monkeypatch.setenv("SEL_DOWNLOAD_DIR", str(isolated / "unused"))
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (7 if "sel_remove_bg.py" in argv else 0, None, None))
    monkeypatch.setenv("REMOVE_BG_ENGINE", "adobe")
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--publish-mode", "github_api", "--workspace-mode", "batch", "--new-batch", "--redo", "remove_bg")
    assert error.value.code == 7
    workspace = orch.CONFIG_DIR
    manifest = json.loads((workspace / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert (workspace / "input/people_list.txt").exists()


@pytest.mark.parametrize("selection", ["cli", "environment"])
def test_legacy_mode_still_invokes_local_tools(isolated, monkeypatch, selection):
    repo = isolated / "repos"
    (repo / "transparent").mkdir(parents=True)
    monkeypatch.setenv("PEOPLE_IMAGES_DIR", str(repo))
    calls = []
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (calls.append(argv) or (0, None, None)))
    args = []
    if selection == "cli":
        args = ["--publish-mode", "local_git", "--workspace-mode", "persistent"]
    else:
        monkeypatch.setenv("PEOPLE_PUBLISH_MODE", "local_git")
        monkeypatch.setenv("PEOPLE_WORKSPACE_MODE", "persistent")
    invoke(monkeypatch, *args, "--redo", "sync_images")
    assert any("sync_people_images.py" in call for call in calls)
    assert any("update_people_repos.py" in call and "push" in call for call in calls)
    assert not any("publish_people_github.py" in call for call in calls)


def test_default_run_uses_api_batch_without_clones(isolated, monkeypatch):
    calls = []
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (calls.append(argv) or (0, None, None)))
    invoke(monkeypatch, "--stop-after", "ensure_repo")
    assert os.environ["PEOPLE_PUBLISH_MODE"] == "github_api"
    assert os.environ["PEOPLE_WORKSPACE_MODE"] == "batch"
    assert orch.CONFIG_DIR.parent == isolated / "jobs"
    assert (orch.CONFIG_DIR / "manifest.json").is_file()
    assert len(calls) == 1 and "publish_people_github.py" in calls[0]
    assert calls[0][calls[0].index("--op") + 1] == "validate"
    assert not (orch.CONFIG_DIR / ".active").exists()


def test_cli_can_override_legacy_configuration(isolated, monkeypatch):
    monkeypatch.setenv("PEOPLE_PUBLISH_MODE", "local_git")
    monkeypatch.setenv("PEOPLE_WORKSPACE_MODE", "persistent")
    calls = []
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (calls.append(argv) or (0, None, None)))
    invoke(monkeypatch, "--publish-mode", "github_api", "--workspace-mode", "batch", "--stop-after", "ensure_repo")
    assert orch.CONFIG_DIR.parent == isolated / "jobs"
    assert "publish_people_github.py" in calls[0]


def test_default_api_failure_never_falls_back_to_cloning(isolated, monkeypatch):
    calls = []
    monkeypatch.setattr(orch, "run_cmd", lambda title, argv, **kw: (calls.append(argv) or (7, None, None)))
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch)
    assert error.value.code == 7
    assert len(calls) == 1 and "publish_people_github.py" in calls[0]
    manifest = json.loads((orch.CONFIG_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"


@pytest.fixture
def launch_jobs(isolated,monkeypatch):
    import time
    from people_workspaces import Workspaces
    from test_people_workspaces import published_job
    manager=Workspaces(isolated)
    old=published_job(manager,monkeypatch)
    resume=manager.create(cleanup=False)
    manager.set_status(resume,"failed","recoverable")
    with manager.db:
        manager.db.execute("UPDATE jobs SET published=? WHERE id=?",(time.time()-4*86400,old))
    monkeypatch.setattr(orch,"run_cmd",lambda *a,**k:(0,None,None))
    yield manager,old,resume
    manager.close()


@pytest.mark.parametrize("selection",["new","implicit","explicit"])
def test_launch_cleanup_runs_once_under_shared_lock_including_resume(launch_jobs,monkeypatch,selection,capsys):
    from people_workspaces import Workspaces
    manager,old,resume=launch_jobs
    actual=Workspaces.cleanup
    calls=[]
    def cleanup(workspaces,**kwargs):
        assert orch._RUN_LOCK_ACQUIRED
        assert orch.LOCK_FILE==manager.state/'orchestrator.lock'
        assert orch.LOCK_FILE.is_file()
        if selection=='explicit':
            assert (manager.path(resume)/'.active').exists()
        calls.append(kwargs)
        return actual(workspaces,**kwargs)
    monkeypatch.setattr(Workspaces,'cleanup',cleanup)
    args=['--new-batch'] if selection=='new' else ['--batch-id',resume] if selection=='explicit' else []
    invoke(monkeypatch,*args,'--stop-after','ensure_repo')
    assert calls==[{'dry_run':False}]
    assert manager.record(old)[0]['status']=='complete'
    assert not (manager.path(old)/'prepared').exists()
    assert (manager.path(resume)/'input').exists()
    assert not orch.LOCK_FILE.exists()
    assert not list(manager.jobs.glob('*/.active'))
    assert '[CLEANUP] eligible=1 deleted=1 retained=1' in capsys.readouterr().out


@pytest.mark.parametrize('args',[['--dry-run'],['--new-batch','--dry-run'],['--list']])
def test_launch_preview_and_list_never_cleanup(launch_jobs,monkeypatch,args):
    from people_workspaces import Workspaces
    manager,old,resume=launch_jobs
    monkeypatch.setattr(Workspaces,'cleanup',lambda *a,**k:pytest.fail('Cleanup in preview/list'))
    invoke(monkeypatch,*args,'--stop-after','ensure_repo')
    assert (manager.path(old)/'prepared').exists()
    assert manager.record(old)[0]['status']=='cleanup_eligible'


def test_launch_auto_cleanup_can_be_disabled(launch_jobs,monkeypatch):
    from people_workspaces import Workspaces
    manager,old,resume=launch_jobs
    monkeypatch.setenv('PEOPLE_AUTO_CLEANUP','false')
    monkeypatch.setattr(Workspaces,'cleanup',lambda *a,**k:pytest.fail('Auto cleanup disabled'))
    invoke(monkeypatch,'--new-batch','--stop-after','ensure_repo')
    assert (manager.path(old)/'prepared').exists()


def test_launch_cleanup_frees_expired_data_before_new_batch_budget_check(launch_jobs,monkeypatch):
    manager,old,resume=launch_jobs
    (manager.path(old)/'logs/large.log').write_bytes(b'x'*100000)
    monkeypatch.setenv('PEOPLE_JOBS_MAX_GIB',str(50*1024/1024**3))
    invoke(monkeypatch,'--new-batch','--stop-after','ensure_repo')
    assert manager.record(old)[0]['status']=='complete'
    assert (manager.path(old)/'logs/large.log').stat().st_size==32768


def test_launch_cleanup_preserves_incomplete_active_and_external_data(launch_jobs,monkeypatch):
    import time
    from test_people_workspaces import published_job
    manager,old,resume=launch_jobs
    statuses=['pending','processing','failed','partially_published','validated','validation_only']
    protected=[]
    for status in statuses:
        batch=manager.create(cleanup=False)
        manager.set_status(batch,status)
        image=manager.path(batch)/'posters/only-copy.jpg'
        image.write_bytes(b'only-copy')
        protected.append(image)
    unverified=manager.create(cleanup=False)
    manager.set_status(unverified,'cleanup_eligible')
    with manager.db:
        manager.db.execute('UPDATE jobs SET updated=? WHERE status!=?',(time.time()-100*86400,'complete'))
        manager.db.execute('UPDATE jobs SET published=? WHERE id=?',(time.time()-4*86400,unverified))
    active=published_job(manager,monkeypatch)
    with manager.db:
        manager.db.execute('UPDATE jobs SET published=? WHERE id=?',(time.time()-4*86400,active))
    manager.activate(active)
    for relative in ('people_dirs/historical.jpg','models/cached-model.bin','clone/.git/marker','source.jpg'):
        path=manager.config/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(b'external')
        protected.append(path)
    try:
        invoke(monkeypatch,'--new-batch','--stop-after','ensure_repo')
        assert (manager.path(active)/'prepared').exists()
        assert manager.record(unverified)[0]['status']=='cleanup_eligible'
        assert all(p.read_bytes() in {b'only-copy',b'external'} for p in protected)
    finally:
        manager.deactivate(active)


def test_launch_cleanup_error_is_visible_without_failing_resumed_job(launch_jobs,monkeypatch,capsys):
    import people_workspaces
    manager,old,resume=launch_jobs
    actual=people_workspaces.shutil.rmtree
    def fail(path,*a,**kw):
        if Path(path).is_relative_to(manager.path(old)):
            raise OSError('cleanup denied')
        return actual(path,*a,**kw)
    monkeypatch.setattr(people_workspaces.shutil,'rmtree',fail)
    invoke(monkeypatch,'--batch-id',resume,'--stop-after','ensure_repo')
    output=capsys.readouterr()
    assert 'Launch cleanup incomplete' in output.err and 'error_category=io_error' in output.err
    assert 'cleanup denied' not in output.err  # Raw exception text is no longer an output contract.
    assert 'eligible=1 deleted=0 retained=2' in output.out
    assert manager.record(resume)[0]['status']=='processing'
    assert manager.record(old)[0]['status']=='cleanup_eligible'
    assert (manager.path(resume)/'input').exists()
    assert not orch.LOCK_FILE.exists()


def test_concurrent_launch_does_not_cleanup_create_or_remove_other_lock(launch_jobs,monkeypatch):
    from people_workspaces import Workspaces
    manager,old,resume=launch_jobs
    lock=manager.state/'orchestrator.lock'
    lock.write_text(str(os.getpid()),encoding='ascii')
    before=set(manager.jobs.iterdir())
    monkeypatch.setattr(Workspaces,'cleanup',lambda *a,**k:pytest.fail('Concurrent cleanup'))
    try:
        with pytest.raises(SystemExit) as error:
            invoke(monkeypatch,'--new-batch','--stop-after','ensure_repo')
        assert error.value.code==3
        assert lock.read_text(encoding='ascii')==str(os.getpid())
        assert set(manager.jobs.iterdir())==before
        assert (manager.path(old)/'prepared').exists()
    finally:
        lock.unlink()
