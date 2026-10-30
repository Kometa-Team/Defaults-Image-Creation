"""Startup cleanup regressions, additive to the original frozen test IDs."""
import json

import pytest

from test_people_api_orchestrator import isolated, invoke, orch


@pytest.mark.parametrize('resume_mode', ['new', 'automatic', 'explicit'])
def test_startup_cleanup_runs_and_protects_resumed_job(isolated, monkeypatch, resume_mode):
    import time
    from people_workspaces import Workspaces
    manager = Workspaces(isolated)
    old = manager.create(cleanup=False)
    manager.set_status(old, 'no_work')
    resume = manager.create(cleanup=False)
    manager.set_status(resume, 'failed')
    manager.db.execute('UPDATE jobs SET created=?,updated=?', (time.time() - 30 * 86400,) * 2)
    manager.db.commit()
    manager.close()
    checks = []
    real = Workspaces.cleanup
    def cleanup(self, **kwargs):
        checks.append((self.path(resume) / '.active').exists())
        return real(self, **kwargs)
    monkeypatch.setattr(Workspaces, 'cleanup', cleanup)
    monkeypatch.setattr(orch, 'run_cmd', lambda *args, **kwargs: (0, None, None))
    monkeypatch.setattr(orch, 'build_colorize_command', lambda py: [py, 'colorize_noncolor_ddcolor.py'])
    monkeypatch.setenv('TMDB_KEY', 'NOT_A_REAL_TMDB_FIXTURE_SECRET_20261024')
    args = ['--publish-mode', 'github_api', '--workspace-mode', 'batch', '--stop-after', 'ensure_repo']
    args += ['--new-batch'] if resume_mode == 'new' else ['--batch-id', resume] if resume_mode == 'explicit' else []
    invoke(monkeypatch, *args)
    assert checks == [resume_mode != 'new']
    assert not (isolated / 'jobs' / old).exists()
    assert (isolated / 'jobs' / resume).exists() == (resume_mode != 'new')


@pytest.mark.parametrize('content', ['{broken', '[]', 'null'])
def test_corrupt_automatic_resume_does_not_prevent_other_startup_cleanup(isolated, monkeypatch, content):
    import time
    from people_workspaces import Workspaces
    manager = Workspaces(isolated)
    good = manager.create(cleanup=False)
    manager.set_status(good, 'no_work')
    manager.db.execute('UPDATE jobs SET updated=? WHERE id=?', (time.time() - 4 * 86400, good))
    manager.db.commit()
    bad = manager.create(cleanup=False)
    manager.set_status(bad, 'failed')
    (manager.path(bad) / 'manifest.json').write_text(content)
    manager.close()
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, '--stop-after', 'ensure_repo')
    assert error.value.code == 2
    assert not (isolated / 'jobs' / good).exists()
    assert (isolated / 'jobs' / bad).exists()


def test_launch_cleanup_failure_persists_safe_stack_and_same_correlation(isolated, capsys):
    import re
    from types import SimpleNamespace
    def fail(**kwargs):
        raise ValueError('private provider diagnostic must not escape')
    manager = SimpleNamespace(state=isolated / 'state', cleanup=fail)
    orch.cleanup_on_launch(manager)
    output = capsys.readouterr()
    correlation = re.search(r'correlation_id=([0-9a-f]{32})', output.err).group(1)
    receipt = (manager.state / 'job-retention/launch-error.json').read_text()
    value = json.loads(receipt)
    assert value['correlation_id'] == correlation
    assert value['locations']
    assert 'private provider diagnostic' not in receipt + output.err


