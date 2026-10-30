"""Startup retention for owned terminal jobs. Never sweep persistent artwork.

Publication receipts and deletion intents live in state, outside expiring jobs.
The fixed historical artwork cleaner is deliberately a separate scope.
"""
from contextlib import closing
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import time

from create_people_posters.people_workspaces import ID_PATTERN, reject_links
from create_people_posters.people_retention_state import (
    RetentionBlocked, atomic_json, inspect, member, processing_exclusion,
    read_json, readonly_db, unlink_verified,
)

SCOPE = 'terminal-jobs-v2'
SUCCESS = {'published', 'cleanup_eligible', 'complete'}
TERMINAL = SUCCESS | {'failed', 'validation_only', 'no_work'}
IMAGE = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}


def number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
        raise RetentionBlocked('invalid_lifecycle_timestamp')
    return value


def days(key, default):
    return number(float(os.getenv(key, str(default))))


def evidence(config, state):
    """No writable managers, schema creation or evidence reconstruction."""
    with closing(readonly_db(state / 'publication_state.db')) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result = {name: [dict(r) for r in db.execute('SELECT * FROM ' + name)]
                  if name in tables else [] for name in ('jobs', 'batches', 'publications', 'readmes')}
    result['historical'] = {}
    marker = state / 'verified-retention/enrollment.json'
    # A broken historical enrollment affects unregistered historical jobs only.
    try:
        historical = read_json(marker).get('historical_evidence') if marker.exists() else None
        if historical:
            from create_people_posters.people_verified_cleanup import HISTORICAL_EVIDENCE
            source = Path(historical['path'])
            reject_links(source)
            raw = source.read_bytes()
            if historical['sha256'] != HISTORICAL_EVIDENCE or hashlib.sha256(raw).hexdigest() != HISTORICAL_EVIDENCE:
                raise RetentionBlocked('historical_evidence_changed')
            archive = json.loads(raw)
            if archive.get('read_only') is not True or archive.get('source_head') != 'ded9f33759f9fe3ed4ddf5f315dff01b163594ad':
                raise RetentionBlocked('historical_evidence_provenance_changed')
            for row in archive['ledger']['jobs']:
                result['historical'][row['id']] = dict(row=row,
                    manifest_hash=archive['files']['jobs/' + row['id'] + '/manifest.json']['sha256'])
            for name in ('batches', 'publications', 'readmes'):
                current = {r.get('id', r.get('batch')) for r in result[name]}
                result[name].extend(r for r in archive['ledger'][name] if r.get('id', r.get('batch')) not in current)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        result['historical'] = {}
    return result


def contents(folder, *, hashes=True):
    files, directories = {}, []
    reject_links(folder)
    def failed(error):
        raise error
    for root, dirs, names in os.walk(folder, followlinks=False, onerror=failed):
        for name in dirs + names:
            reject_links(Path(root) / name)
        directories.extend((Path(root) / name).relative_to(folder).as_posix() for name in dirs)
        for name in names:
            p = Path(root) / name
            files[p.relative_to(folder).as_posix()] = inspect(p) if hashes else {'bytes': p.stat().st_size}
    return files, directories


def recovery_blocker(folder):
    """Leases and rollback evidence require explicit reconciliation, never age/PID theft."""
    for root, dirs, names in os.walk(folder, followlinks=False):
        for name in dirs + names:
            reject_links(Path(root) / name)
        for name in names:
            path = Path(root) / name
            if name in {'.active', 'active', 'run.lock', 'transaction.json'} or name.endswith('.pending.json'):
                return 'active_or_recovery_or_rollback_evidence'
            if name == 'recovery-checkpoints.json':
                checkpoint = read_json(path)
                if any(r['outcome']['status'] != 'recovered' for r in checkpoint['records'].values()):
                    return 'recoverable_interrupted_job'
            if name == 'scratch.json' and read_json(path).get('state') not in {'ready', 'cleaned'}:
                return 'recoverable_interrupted_job'
    return None


def dependencies(jobs, state):
    """Only cross-job references are leases; a job's own fulfilled paths aren't.

    Scan raw metadata too: malformed JSON retains its owner and still protects
    explicit referenced job paths without disabling unrelated jobs.
    """
    protected = set()
    ids = [p.name for p in jobs.iterdir() if ID_PATTERN.fullmatch(p.name)] if jobs.exists() else []
    roots = [jobs, state.parent / '.orch', state.parent / 'edge_chop_recovery', state / 'manifests']
    for base in roots:
        try:
            reject_links(base)
        except (OSError, ValueError):
            continue
        for root, dirs, names in os.walk(base, followlinks=False):
            for name in list(dirs):
                try:
                    reject_links(Path(root) / name)
                except (OSError, ValueError):
                    dirs.remove(name)
            for name in names:
                if not name.endswith('.json'):
                    continue
                p = Path(root) / name
                try:
                    reject_links(p)
                    if p.stat().st_size > 32 * 1024 * 1024:
                        continue
                    text = p.read_text(encoding='utf-8-sig')
                    try:
                        value = json.loads(text)
                    except (ValueError, RecursionError):
                        value = {}
                    decoded, pending = [], [value]
                    while pending:
                        part = pending.pop()
                        if isinstance(part, str):
                            decoded.append(part)
                        elif isinstance(part, dict):
                            pending.extend(part.keys()); pending.extend(part.values())
                        elif isinstance(part, list):
                            pending.extend(part)
                    raw = (text + '\n' + '\n'.join(decoded)).replace('\\\\', '/').replace('\\', '/').casefold()
                    # Fulfilled state publication exports aren't recovery leases.
                    if base == state / 'manifests':
                        receipts = value.get('publications') if isinstance(value, dict) else None
                        if isinstance(receipts, list) and all(isinstance(r, dict) and r.get('status') == 'published' for r in receipts):
                            continue
                    owner = (p.relative_to(jobs).parts[0] if p.is_relative_to(jobs)
                             else p.stem if base == state / 'manifests' else None)
                    for job in ids:
                        if job != owner and (jobs / job).as_posix().casefold() in raw:
                            protected.add(job)
                except (OSError, ValueError, TypeError, AttributeError):
                    # A malformed manifest is handled by its own per-job planner.
                    continue
    return protected


def publication_proof(job, data, *, legacy_handoff=False):
    from create_people_posters.people_github import REPOSITORIES
    rows = [r for r in data['publications'] if r['batch'] == job]
    batch = next((r for r in data['batches'] if r['id'] == job), {})
    readmes = [r for r in data['readmes'] if r['batch'] == job]
    # Legacy sealed receipts used "dispatched" for a remote README workflow.
    # That workflow reads published GitHub blobs, never these local payloads.
    # Do not reinterpret pending current receipts as a completed handoff.
    allowed_readmes = {'verified', 'disabled'} | ({'dispatched'} if legacy_handoff else set())
    if (not batch.get('expected') or len(rows) != batch['expected']
            or any(r['status'] != 'published' or not r['commit_sha'] for r in rows)
            or {r['repo'] for r in rows} != {r['repo'] for r in readmes}
            or any(r['status'] not in allowed_readmes for r in readmes)):
        raise RetentionBlocked('publication_receipts_incomplete')
    cohorts = {}
    identities = set()
    for row in rows:
        identity = (row['repo'], row['path'])
        if (identity in identities or REPOSITORIES.get(row['style']) != row['repo']
                or row['branch'] != batch['branch']):
            raise RetentionBlocked('inconsistent_publication_cohort')
        identities.add(identity)
        cohorts.setdefault(row['person'], set()).add(row['style'])
    if any(styles != set(REPOSITORIES) for styles in cohorts.values()):
        raise RetentionBlocked('incomplete_seven_style_publication')
    return rows


def plan(config, jobs, state, *, now=None, only=None):
    for root in (config, jobs, state):
        reject_links(root)
    config, jobs, state = Path(config).resolve(), Path(jobs).resolve(), Path(state).resolve()
    if jobs == state or jobs in state.parents or state in jobs.parents:
        raise RetentionBlocked('overlapping_storage_roots')
    now = number(time.time() if now is None else now)
    success_days = days('PEOPLE_BATCH_RETENTION_DAYS', 3)
    failed_days = days('PEOPLE_FAILED_BATCH_RETENTION_DAYS', 14)
    validation_days = days('PEOPLE_VALIDATION_BATCH_RETENTION_DAYS', success_days)
    data = evidence(config, state)
    registered = {r['id']: r for r in data['jobs']}
    protected = dependencies(jobs, state)
    # A pending DB receipt can be newer than its exported JSON manifest.
    # Protect cross-job inputs directly from the authoritative ledger too.
    prefix = jobs.as_posix().casefold() + '/'
    job_names = {p.name.casefold(): p.name for p in jobs.iterdir() if ID_PATTERN.fullmatch(p.name)}
    for receipt in data['publications']:
        if receipt.get('status') == 'published':
            continue
        for key in ('source', 'prepared'):
            value = receipt.get(key)
            if not isinstance(value, str):
                continue
            normalized = value.replace('\\', '/').casefold()
            if normalized.startswith(prefix):
                target = value.replace('\\', '/')[len(prefix):].split('/')[0]
                if target.casefold() != str(receipt.get('batch')).casefold():
                    protected.add(job_names.get(target.casefold(), target))
    report = dict(observed=now, jobs=[], eligible_bytes=0, eligible_jobs=0, scope=SCOPE)
    for folder in sorted(jobs.iterdir()):
        if only is not None and folder.name != only:
            continue
        item = dict(id=folder.name, path=str(folder), status='unknown', eligible=False, bytes=0)
        report['jobs'].append(item)
        try:
            reject_links(folder)
            if not ID_PATTERN.fullmatch(folder.name) or not folder.is_dir():
                raise RetentionBlocked('unrecognized_job_ownership')
            files, dirs = contents(folder, hashes=False)
            item.update(bytes=sum(r['bytes'] for r in files.values()), files=files, directories=dirs)
            intent_path = state / 'job-retention' / (folder.name + '.json')
            prior = read_json(intent_path) if intent_path.exists() else None
            manifest = read_json(folder / 'manifest.json') if 'manifest.json' in files else prior['manifest'] if prior else None
            if not isinstance(manifest, dict) or manifest.get('id') != folder.name or manifest.get('managed_by') != 'kometa-people-v1':
                raise RetentionBlocked('unrecognized_job_ownership')
            item.update(status=manifest.get('status', 'unknown'), age_days=(now - number(manifest.get('created'))) / 86400)
            if any(part.casefold() in {'models', 'vendor', '.git', 'config'} for name in dirs for part in Path(name).parts):
                raise RetentionBlocked('protected_persistent_material_inside_job')
            row = registered.get(folder.name)
            from_history = row is None
            if not row:
                historical = data['historical'].get(folder.name)
                if not historical or (not prior and inspect(folder / 'manifest.json')['sha256'] != historical['manifest_hash']):
                    raise RetentionBlocked('job_missing_from_ledger_and_verified_history')
                row = historical['row']
            status = row['status']
            item.update(status=status, age_days=(now - number(row['created'])) / 86400)
            if status not in TERMINAL or manifest['status'] != status:
                raise RetentionBlocked('incomplete_or_inconsistent_lifecycle')
            timestamp = number(row['published'] if status in SUCCESS else row['updated'])
            retention = success_days if status in SUCCESS else failed_days if status == 'failed' else validation_days
            item.update(retention_days=retention, deadline=timestamp + retention * 86400, manifest=manifest, row=row)
            if now < item['deadline']:
                raise RetentionBlocked('retention_window_open')
            blocker = recovery_blocker(folder)
            if blocker:
                raise RetentionBlocked(blocker)
            if folder.name in protected:
                raise RetentionBlocked('referenced_by_another_operation')
            files, dirs = contents(folder)
            item.update(files=files, directories=dirs)
            if prior:
                if prior.get('scope') != SCOPE or prior.get('root') != str(jobs) or prior.get('id') != folder.name:
                    raise RetentionBlocked('invalid_cleanup_intent')
                if any(name not in prior['files'] or identity != prior['files'][name]
                       or name in prior['deleted'] for name, identity in files.items()):
                    raise RetentionBlocked('job_changed_after_cleanup_intent')
                if set(dirs) - set(prior['directories']):
                    raise RetentionBlocked('job_changed_after_cleanup_intent')
            if status in SUCCESS:
                receipts = publication_proof(folder.name, data, legacy_handoff=from_history)
                catalog = manifest.get('cleanup_files')
                if not isinstance(catalog, dict):
                    raise RetentionBlocked('publication_catalog_missing')
                for name, identity in files.items():
                    if Path(name).suffix.lower() in IMAGE and catalog.get(name) != identity['sha256']:
                        raise RetentionBlocked('local_image_changed_after_publication')
                for receipt in receipts:
                    for key, digest in [('source', 'source_hash'), ('prepared', 'published_hash')]:
                        p = Path(receipt[key])
                        reject_links(p)
                        if not p.is_absolute() or not p.resolve().is_relative_to(folder):
                            raise RetentionBlocked('publication_source_ownership_uncertain')
                        rel = p.relative_to(folder).as_posix()
                        if rel in files and files[rel]['sha256'] != receipt[digest]:
                            raise RetentionBlocked('publication_source_changed')
            else:
                # Partial remote writes always need recovery, including a failed job.
                receipts = [r for r in data['publications'] if r['batch'] == folder.name]
                if status == 'failed' and any(r.get('commit_sha') or r['status'] == 'published' for r in receipts):
                    raise RetentionBlocked('partial_publication_requires_recovery')
            item.update(eligible=True, reason='expired_terminal_job')
            report['eligible_jobs'] += 1
            report['eligible_bytes'] += item['bytes']
        except (OSError, ValueError, KeyError, TypeError, AttributeError, sqlite3.Error) as error:
            item['reason'] = error.args[0] if isinstance(error, RetentionBlocked) else 'invalid_or_unreadable_job_metadata'
    return report


def apply_job(item, jobs, state):
    """Intent precedes unlink. A crash can resume even after manifest removal."""
    folder = member(jobs, item['id'])
    intent_path = state / 'job-retention' / (item['id'] + '.json')
    intent = read_json(intent_path) if intent_path.exists() else dict(
        scope=SCOPE, id=item['id'], root=str(jobs), manifest=item['manifest'], row=item['row'],
        files=item['files'], directories=item['directories'], deleted=[], completed=False)
    atomic_json(intent_path, intent)
    removed = 0
    # Preserve manifest until all payloads and logs have gone.
    for name in sorted(item['files'], key=lambda name: (name == 'manifest.json', name)):
        if (folder / '.active').exists():
            raise RetentionBlocked('job_became_active')
        identity = item['files'][name]
        unlink_verified(folder, dict(path=name, identity=identity, sha256=identity['sha256']))
        removed += identity['bytes']
        intent['deleted'].append(name)
        atomic_json(intent_path, intent)
    for name in sorted(item['directories'], key=lambda name: len(Path(name).parts), reverse=True):
        p = member(folder, name)
        if p.exists():
            p.rmdir()
    reject_links(folder)
    folder.rmdir()
    intent.update(completed=True, completed_at=time.time())
    atomic_json(intent_path, intent)
    return removed


def cleanup(manager, *, dry_run=True, now=None):
    for root in (manager.config, manager.jobs, manager.state):
        reject_links(root)
    config, jobs, state = manager.config.resolve(), manager.jobs.resolve(), manager.state.resolve()
    # The shared processing lease has a canonical location. Never invent a
    # second lock for a custom storage layout.
    if jobs != (config / 'jobs').resolve() or state != (config / 'state').resolve():
        raise RetentionBlocked('custom_workspace_roots_require_retention_review')
    if dry_run:
        report = plan(config, jobs, state, now=now)
        manager.last_cleanup_report = report
        manager.last_cleanup_counts = dict(eligible=report['eligible_jobs'], deleted=0, retained=len(report['jobs']))
        return [(j['id'], 'eligible' if j['eligible'] else 'retained: ' + j['reason']) for j in report['jobs']]
    results = []
    with processing_exclusion(config, SCOPE, allow_existing=True):
        # The process may have died after removing the directory, before its
        # completion receipt or ledger update. Reconcile only our own intents.
        for path in (state / 'job-retention').glob('*.json'):
            if not ID_PATTERN.fullmatch(path.stem):
                continue
            try:
                intent = read_json(path)
                folder = member(jobs, path.stem)
                if (intent.get('scope') == SCOPE and intent.get('id') == path.stem
                        and intent.get('root') == str(jobs) and not folder.exists()):
                    with manager.db:
                        manager.db.execute("UPDATE jobs SET status='complete' WHERE id=?", (path.stem,))
                    if not intent.get('completed'):
                        intent.update(completed=True, completed_at=time.time())
                        atomic_json(path, intent)
            except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
                continue
        report = plan(config, jobs, state, now=now)
        manager.last_cleanup_report = report
        manager.last_cleanup_counts = dict(eligible=report['eligible_jobs'], deleted=0, retained=len(report['jobs']))
        for item in report['jobs']:
            if not item['eligible']:
                results.append((item['id'], 'retained: ' + item['reason']))
                continue
            try:
                # Revalidate ownership, references and membership immediately before applying.
                fresh = plan(config, jobs, state, now=now, only=item['id'])['jobs'][0]
                if not fresh['eligible'] or fresh['files'] != item['files']:
                    raise RetentionBlocked('job_changed_before_cleanup')
                apply_job(fresh, jobs, state)
                with manager.db:
                    manager.db.execute("UPDATE jobs SET status='complete',updated=? WHERE id=?", (time.time(), item['id']))
                manager.last_cleanup_counts['deleted'] += 1
                manager.last_cleanup_counts['retained'] -= 1
                results.append((item['id'], 'cleaned'))
            except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
                from create_people_posters.people_failures import failure_record
                failure = failure_record(error, 'job_cleanup', item['id'])
                try:
                    atomic_json(state / 'job-retention' / (item['id'] + '-error.json'), failure)
                except (OSError, ValueError):
                    pass
                results.append((item['id'], 'retained: cleanup_interrupted correlation_id=' + failure['correlation_id']))
    return results


def main():
    import argparse
    from datetime import datetime, UTC
    parser = argparse.ArgumentParser(description='Read-only lifecycle inventory using the startup retention policy')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True, help='New report outside the runtime config tree')
    args = parser.parse_args()
    reject_links(args.config)
    reject_links(args.report)
    config, output = args.config.resolve(), args.report.resolve()
    if output.is_relative_to(config) or output.exists():
        parser.error('Report must be a new file outside runtime config')
    from dotenv import load_dotenv
    load_dotenv(config / '.env')
    result = plan(config, config / 'jobs', config / 'state')
    result['observed_utc'] = datetime.fromtimestamp(result['observed'], UTC).isoformat()
    for job in result['jobs']:
        for key in ('files', 'directories', 'manifest', 'row'):
            job.pop(key, None)
    atomic_json(output, result)
    print(json.dumps(dict(eligible_jobs=result['eligible_jobs'], eligible_bytes=result['eligible_bytes'])))


if __name__ == '__main__':
    main()
