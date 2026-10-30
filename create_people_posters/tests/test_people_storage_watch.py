"""Storage exceptions must be visible and bounded without deleting recovery."""
import json
import os
import time
from unittest.mock import patch

import pytest

from test_people_workspaces import manager
from test_people_job_retention import terminal
from create_people_posters import people_storage_watch as watch


def test_overdue_recovery_blocks_new_batches_and_remains_resumable(manager, capsys):
    batch = terminal(manager, 'recovery_pending', 30)
    evidence = manager.path(batch) / 'posters/source.jpg'
    evidence.write_bytes(b'needed for recovery')
    manager.cleanup(dry_run=False)
    snapshot = manager.last_storage_report
    assert snapshot['overdue_jobs'] == 1
    assert snapshot['jobs'][0]['bytes'] >= len(b'needed for recovery')
    assert 'REVIEW REQUIRED' in capsys.readouterr().out
    before = set(manager.jobs.iterdir())
    with pytest.raises(ValueError, match='admission blocked'):
        manager.create(cleanup=False)
    assert set(manager.jobs.iterdir()) == before
    assert manager.select(batch) == batch
    manager.check_budget()  # Existing recovery can continue below the cap.
    assert evidence.read_bytes() == b'needed for recovery'


def test_budget_counts_state_and_stops_next_step_without_deleting(manager, monkeypatch):
    batch = manager.create(cleanup=False)
    payload = manager.state / 'retained-receipts.bin'
    payload.write_bytes(b'x' * (2 * 1024 ** 2))
    monkeypatch.setenv('PEOPLE_JOBS_MAX_GIB', str(1 / 1024))
    with pytest.raises(ValueError, match='budget'):
        manager.check_budget()
    assert payload.exists() and manager.path(batch).exists()
    assert 'workspace_storage_limit_reached' in manager.last_storage_report['blockers']
    assert manager.last_storage_report['state_bytes'] >= payload.stat().st_size


def test_growth_during_last_step_is_reported_when_job_releases_lease(manager, monkeypatch):
    batch = manager.create(cleanup=False)
    manager.activate(batch)
    monkeypatch.setenv('PEOPLE_JOBS_MAX_GIB', str(1 / 1024))
    (manager.path(batch) / 'posters/payload.jpg').write_bytes(b'x' * (2 * 1024 ** 2))
    manager.deactivate(batch)
    assert 'workspace_storage_limit_reached' in manager.last_storage_report['blockers']
    assert not (manager.path(batch) / '.active').exists()


@pytest.mark.parametrize('setting', ['PEOPLE_JOBS_MAX_GIB', 'PEOPLE_RECOVERY_REVIEW_DAYS'])
@pytest.mark.parametrize('value', ['0', '-1', 'nan', 'inf', 'bad'])
def test_limits_cannot_be_disabled_or_bypassed(manager, monkeypatch, setting, value):
    monkeypatch.setenv(setting, value)
    with pytest.raises(ValueError):
        manager.check_budget()


def test_warning_growth_and_persistent_report_do_not_accumulate(manager, monkeypatch, capsys):
    batch = manager.create(cleanup=False)
    first = watch.report(manager)
    payload = manager.path(batch) / 'posters/source.jpg'
    payload.write_bytes(b'x' * 100000)
    actual = watch.usage(manager.jobs)[0] + watch.usage(manager.state)[0]
    monkeypatch.setenv('PEOPLE_JOBS_MAX_GIB', str(actual / .85 / 1024 ** 3))
    result = watch.report(manager)
    assert result['growth_bytes'] >= 100000
    assert result['warning']
    assert '80%' in capsys.readouterr().out
    file = manager.state / 'job-retention/storage-report.json'
    assert json.loads(file.read_text())['total_bytes'] == result['total_bytes']
    watch.report(manager)
    assert list(file.parent.glob('storage-report*.json')) == [file]
    assert first['observed'] <= result['observed']


def test_retry_does_not_silently_extend_review_deadline(manager):
    batch = terminal(manager, 'failed', 30)
    first = watch.report(manager)
    manager.set_status(batch, 'processing')
    second = watch.report(manager)
    assert second['jobs'][0]['review_deadline'] == first['jobs'][0]['review_deadline']
    assert second['overdue_jobs'] == 1


def test_completed_receipts_expire_but_interrupted_intents_remain(manager):
    done = terminal(manager, 'no_work', 30)
    manager.cleanup(dry_run=False)
    receipt = manager.state / 'job-retention' / (done + '.json')
    value = json.loads(receipt.read_text())
    value['completed_at'] = time.time() - 15 * 86400
    receipt.write_text(json.dumps(value))
    interrupted = terminal(manager, 'no_work', 30)
    from create_people_posters import people_job_retention as retention
    with patch.object(retention, 'unlink_verified', side_effect=OSError('locked')):
        manager.cleanup(dry_run=False)
    # Receipt pruning was also interrupted; retry the normal startup pass with
    # a real deletion primitive while the job itself remains protected.
    marker = manager.path(interrupted) / '.active'
    marker.write_text('unresolved recovery')
    manager.cleanup(dry_run=False)
    assert not receipt.exists()
    assert (manager.state / 'job-retention' / (interrupted + '.json')).exists()
    assert marker.exists()


def test_unreadable_tree_blocks_admission_instead_of_reporting_zero(manager):
    manager.create(cleanup=False)
    with patch.object(watch, 'usage', return_value=(0, {}, ['unreadable'])):
        with pytest.raises(ValueError, match='admission blocked'):
            manager.check_budget(admitting=True)
    assert manager.last_storage_report['measurement_complete'] is False


def test_corrupt_previous_storage_report_is_replaced_safely(manager):
    manager.create(cleanup=False)
    path = manager.state / 'job-retention/storage-report.json'
    for raw in ['[]', '{broken', '{"jobs":null,"total_bytes":"bad"}']:
        path.write_text(raw)
        assert watch.report(manager)['measurement_complete']
