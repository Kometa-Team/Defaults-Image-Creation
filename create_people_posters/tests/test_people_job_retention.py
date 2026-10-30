"""Lifecycle retention: isolated owned fixtures; never production paths."""
import json
import os
import time

import pytest

from test_people_workspaces import manager, published_job
from create_people_posters import people_job_retention as retention


def terminal(manager, status, age):
    batch = manager.create(cleanup=False)
    manager.set_status(batch, status)
    timestamp = time.time() - age * 86400
    manager.db.execute('UPDATE jobs SET created=?,updated=? WHERE id=?', (timestamp, timestamp, batch))
    manager.db.commit()
    return batch


@pytest.mark.parametrize('status,days', [('failed', 14), ('validation_only', 3), ('no_work', 3)])
def test_terminal_jobs_expire_at_exact_boundary(manager, monkeypatch, status, days):
    monkeypatch.setenv('PEOPLE_AUTO_CLEANUP', 'false')
    batch = terminal(manager, status, 30)
    path = manager.path(batch)
    (path / 'posters/payload.jpg').write_bytes(b'unpublished temporary payload')
    (path / 'logs/job.log').write_bytes(b'job diagnostics')
    timestamp = manager.db.execute('SELECT updated FROM jobs WHERE id=?', (batch,)).fetchone()[0]
    deadline = timestamp + days * 86400
    assert 'retention_window_open' in manager.cleanup(now=deadline - .001)[0][1]
    assert manager.cleanup(now=deadline) == [(batch, 'eligible')]
    assert path.exists()
    assert manager.cleanup(dry_run=False, now=deadline) == [(batch, 'cleaned')]
    assert not path.exists()
    receipt = json.loads((manager.state / 'job-retention' / (batch + '.json')).read_text())
    assert receipt['completed'] and receipt['manifest']['status'] == status
    assert 'logs/job.log' in receipt['deleted']
    assert manager.cleanup(dry_run=False, now=deadline) == []
    assert manager.resume_candidate() is None


@pytest.mark.parametrize('value', ['-1', 'nan', 'inf', 'nonsense'])
def test_invalid_retention_never_authorizes_deletion(manager, monkeypatch, value):
    batch = terminal(manager, 'no_work', 50)
    monkeypatch.setenv('PEOPLE_BATCH_RETENTION_DAYS', value)
    with pytest.raises(ValueError):
        manager.cleanup(dry_run=False)
    assert manager.path(batch).exists()


@pytest.mark.parametrize('status', ['pending', 'processing', 'generated', 'validated', 'partially_published', 'recovery_pending'])
def test_incomplete_jobs_are_recoverable_even_when_very_old(manager, status):
    batch = terminal(manager, status, 300)
    assert manager.cleanup(dry_run=False)[0][1].startswith('retained:')
    assert manager.path(batch).exists()


@pytest.mark.parametrize('marker', ['.active', '.orch/render.pending.json', 'edge_chop_recovery/transactions/x/transaction.json'])
def test_leases_pending_work_and_rollback_override_expiry(manager, marker):
    batch = terminal(manager, 'failed', 300)
    path = manager.path(batch) / marker
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{}')
    assert 'active_or_recovery' in manager.cleanup(dry_run=False)[0][1]
    assert path.exists()


@pytest.mark.parametrize('content', ['{broken', '[]', 'null', '{"id":"wrong"}'])
def test_corrupt_job_does_not_block_another_job(manager, content):
    bad = terminal(manager, 'no_work', 10)
    good = terminal(manager, 'no_work', 10)
    (manager.path(bad) / 'manifest.json').write_text(content)
    result = dict(manager.cleanup(dry_run=False))
    assert result[bad].startswith('retained:')
    assert result[good] == 'cleaned'
    assert manager.path(bad).exists()
    assert not manager.path(good).exists()


def test_dry_run_is_read_only_and_uses_lifecycle_not_mtime(manager):
    batch = terminal(manager, 'validation_only', 4)
    folder = manager.path(batch)
    os.utime(folder, None)
    before = {str(p): p.read_bytes() for p in manager.config.rglob('*') if p.is_file()}
    assert manager.cleanup() == [(batch, 'eligible')]
    assert before == {str(p): p.read_bytes() for p in manager.config.rglob('*') if p.is_file()}


def test_explicit_failed_and_validation_retention_overrides(manager, monkeypatch):
    failed = terminal(manager, 'failed', 5)
    validation = terminal(manager, 'validation_only', 5)
    monkeypatch.setenv('PEOPLE_FAILED_BATCH_RETENTION_DAYS', '4')
    monkeypatch.setenv('PEOPLE_VALIDATION_BATCH_RETENTION_DAYS', '7')
    result = dict(manager.cleanup())
    assert result[failed] == 'eligible'
    assert 'retention_window_open' in result[validation]


def test_referenced_job_retained_even_when_referring_metadata_is_corrupt(manager):
    target = terminal(manager, 'no_work', 100)
    other = terminal(manager, 'processing', 100)
    (manager.path(other) / 'recovery.json').write_text('{"source":' + json.dumps(str(manager.path(target))) + ',broken')
    assert 'referenced_by_another' in dict(manager.cleanup())[target]


@pytest.mark.parametrize('metadata', ['[]', 'null', '"text"', '{broken'])
def test_corrupt_state_export_does_not_block_unrelated_expired_job(manager, metadata):
    batch = terminal(manager, 'no_work', 10)
    path = manager.state / 'manifests/corrupt.json'
    path.parent.mkdir()
    path.write_text(metadata)
    assert manager.cleanup(dry_run=False) == [(batch, 'cleaned')]


def test_unicode_escaped_cross_job_reference_is_preserved(manager):
    target = terminal(manager, 'no_work', 100)
    other = terminal(manager, 'processing', 100)
    raw = json.dumps({'source': str(manager.path(target))}).replace('jobs', '\\u006aobs')
    (manager.path(other) / 'recovery.json').write_text(raw)
    assert 'referenced_by_another' in dict(manager.cleanup())[target]


def test_pending_database_reference_protects_input_without_json_export(manager):
    target = terminal(manager, 'no_work', 100)
    owner = terminal(manager, 'processing', 100)
    manager.db.execute('CREATE TABLE publications(batch TEXT,status TEXT,source TEXT,prepared TEXT)')
    source = str(manager.path(target) / 'posters/source.jpg')
    manager.db.execute('INSERT INTO publications VALUES(?,?,?,?)', (owner, 'pending', source, source))
    manager.db.commit()
    assert 'referenced_by_another' in dict(manager.cleanup())[target]


def test_interrupted_job_does_not_prevent_other_deletions(manager, monkeypatch):
    bad = terminal(manager, 'no_work', 10)
    good = terminal(manager, 'no_work', 10)
    real = retention.unlink_verified
    def fail(root, row):
        if root.name == bad:
            raise PermissionError('locked')
        return real(root, row)
    monkeypatch.setattr(retention, 'unlink_verified', fail)
    result = dict(manager.cleanup(dry_run=False))
    assert 'cleanup_interrupted' in result[bad]
    assert result[good] == 'cleaned'


def test_interrupt_after_manifest_unlink_resumes_without_manifest(manager, monkeypatch):
    batch = terminal(manager, 'no_work', 10)
    real = retention.unlink_verified
    def fail(root, row):
        real(root, row)
        if row['path'] == 'manifest.json':
            raise OSError('crash before receipt')
    monkeypatch.setattr(retention, 'unlink_verified', fail)
    assert 'cleanup_interrupted' in manager.cleanup(dry_run=False)[0][1]
    assert not (manager.path(batch) / 'manifest.json').exists()
    monkeypatch.setattr(retention, 'unlink_verified', real)
    assert manager.cleanup(dry_run=False) == [(batch, 'cleaned')]


def test_changed_payload_after_interruption_is_retained(manager, monkeypatch):
    batch = terminal(manager, 'no_work', 10)
    payload = manager.path(batch) / 'posters/payload.jpg'
    payload.write_bytes(b'owned')
    with monkeypatch.context() as patch:
        patch.setattr(retention, 'unlink_verified', lambda *args: (_ for _ in ()).throw(OSError('locked')))
        manager.cleanup(dry_run=False)
    payload.write_bytes(b'changed')
    assert 'job_changed_after_cleanup_intent' in manager.cleanup(dry_run=False)[0][1]
    assert payload.read_bytes() == b'changed'


def test_config_models_and_unknown_ownership_are_untouched(manager):
    batch = terminal(manager, 'no_work', 100)
    model = manager.path(batch) / 'models/weights.bin'
    model.parent.mkdir()
    model.write_bytes(b'preserve')
    foreign = manager.jobs / 'historical-unmanaged'
    foreign.mkdir()
    assert all(outcome.startswith('retained:') for _, outcome in manager.cleanup(dry_run=False))
    assert model.read_bytes() == b'preserve' and foreign.exists()


def test_success_age_is_publication_age(manager, monkeypatch):
    batch = published_job(manager, monkeypatch)
    published = manager.db.execute('SELECT published FROM jobs WHERE id=?', (batch,)).fetchone()[0]
    manager.db.execute('UPDATE jobs SET created=0,updated=0 WHERE id=?', (batch,))
    manager.db.commit()
    assert 'retention_window_open' in manager.cleanup(now=published + 3 * 86400 - .001)[0][1]
    assert manager.cleanup(now=published + 3 * 86400) == [(batch, 'eligible')]


def test_partial_publication_in_failed_job_is_not_expired(manager):
    batch = terminal(manager, 'failed', 100)
    manager.db.execute('CREATE TABLE publications(batch TEXT,status TEXT,commit_sha TEXT)')
    manager.db.execute('INSERT INTO publications VALUES(?,?,?)', (batch, 'published', 'abc'))
    manager.db.commit()
    assert 'partial_publication' in manager.cleanup(dry_run=False)[0][1]


def test_missing_ledger_job_requires_sealed_matching_history(manager, monkeypatch):
    import hashlib
    from create_people_posters import people_verified_cleanup as old
    batch = terminal(manager, 'no_work', 10)
    row = dict(manager.db.execute('SELECT * FROM jobs WHERE id=?', (batch,)).fetchone())
    manifest = manager.path(batch) / 'manifest.json'
    archive = dict(read_only=True, source_head='ded9f33759f9fe3ed4ddf5f315dff01b163594ad',
                   ledger=dict(jobs=[row], batches=[], publications=[], readmes=[]),
                   files={'jobs/' + batch + '/manifest.json': {'sha256': retention.inspect(manifest)['sha256']}})
    raw = json.dumps(archive).encode()
    history = manager.config.parent / 'sealed-history.json'
    history.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(old, 'HISTORICAL_EVIDENCE', digest)
    retention.atomic_json(manager.state / 'verified-retention/enrollment.json',
                          dict(historical_evidence=dict(path=str(history), sha256=digest)))
    manager.db.execute('DELETE FROM jobs WHERE id=?', (batch,))
    manager.db.commit()
    assert manager.cleanup() == [(batch, 'eligible')]
    manifest.write_text(manifest.read_text() + ' ')
    assert 'verified_history' in manager.cleanup()[0][1]


def test_cleanup_reconciles_crash_after_directory_removal(manager, monkeypatch):
    batch = terminal(manager, 'failed', 100)
    real = retention.apply_job
    def fail(*args):
        real(*args)
        raise OSError('crash before ledger update')
    with monkeypatch.context() as patch:
        patch.setattr(retention, 'apply_job', fail)
        assert 'cleanup_interrupted' in manager.cleanup(dry_run=False)[0][1]
    assert not manager.path(batch).exists()
    assert manager.cleanup(dry_run=False) == []
    assert manager.resume_candidate() is None


def test_legacy_readme_handoff_does_not_adopt_current_unverified_readmes(manager, monkeypatch):
    batch = published_job(manager, monkeypatch)
    manager.db.execute("UPDATE readmes SET status='dispatched'")
    manager.db.commit()
    assert 'publication_receipts_incomplete' in manager.cleanup(now=time.time() + 4 * 86400)[0][1]


@pytest.mark.parametrize('sql', ["UPDATE publications SET style='original' WHERE style='bw'",
                                "UPDATE publications SET branch='unexpected' WHERE style='bw'"])
def test_corrupt_publication_cohort_never_authorizes_deletion(manager, monkeypatch, sql):
    batch = published_job(manager, monkeypatch)
    manager.db.execute(sql)
    manager.db.commit()
    outcome = manager.cleanup(now=time.time() + 4 * 86400)[0][1]
    assert 'publication_cohort' in outcome or 'seven_style' in outcome
    assert manager.path(batch).exists()
