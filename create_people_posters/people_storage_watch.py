"""Bounded startup/stage storage monitoring and admission, without a scheduler."""
import math
import os
from pathlib import Path
import shutil
import stat
import time

from create_people_posters.people_retention_state import atomic_json, read_json
from create_people_posters.people_workspaces import reject_links


def positive_setting(name, default):
    value = float(os.getenv(name, str(default)))
    if not math.isfinite(value) or value <= 0:
        raise ValueError('Storage limits and review periods must be finite and positive')
    return value


def usage(root):
    """No payload reads or hashing; never follow links or omit scan failures."""
    reject_links(root)
    total, groups, errors = 0, {}, []
    def failed(error):
        errors.append(type(error).__name__)
    for folder, dirs, names in os.walk(root, followlinks=False, onerror=failed):
        for name in list(dirs):
            try:
                reject_links(Path(folder) / name)
            except (OSError, ValueError):
                dirs.remove(name)
                errors.append('unsafe_directory')
        for name in names:
            path = Path(folder) / name
            try:
                reject_links(path)
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError('unowned_file')
                key = path.relative_to(root).parts[0]
                total += info.st_size
                groups[key] = groups.get(key, 0) + info.st_size
            except (OSError, ValueError):
                errors.append('unreadable_or_unsafe_file')
    return total, groups, errors


def timestamp(value, fallback):
    return value if type(value) in {int, float} and math.isfinite(value) and value >= 0 else fallback


def report(manager, *, now=None, persist=True, announce=False):
    now = time.time() if now is None else now
    budget = positive_setting('PEOPLE_JOBS_MAX_GIB', 20) * 1024 ** 3
    review_days = positive_setting('PEOPLE_RECOVERY_REVIEW_DAYS', 14)
    output = manager.state / 'job-retention/storage-report.json'
    try:
        previous = read_json(output) if output.exists() else {}
        if not isinstance(previous, dict):
            previous = {}
    except (OSError, ValueError):
        previous = {}
    jobs_bytes, by_job, job_errors = usage(manager.jobs)
    state_bytes, by_state, state_errors = usage(manager.state)
    current = {row['id']: dict(row) for row in manager.db.execute('SELECT * FROM jobs')}
    planned = {j['id']: j for j in (getattr(manager, 'last_cleanup_report', None) or {}).get('jobs', [])}
    previous_jobs = previous.get('jobs', [])
    earlier = {j['id']: j for j in previous_jobs if isinstance(j, dict) and 'id' in j} if isinstance(previous_jobs, list) else {}
    outcomes = dict(getattr(manager, 'last_cleanup_results', []))
    jobs = []
    for folder in sorted(manager.jobs.iterdir()):
        if not folder.is_dir() or folder.is_symlink():
            continue
        job = folder.name
        initial = timestamp(earlier.get(job, {}).get('first_observed'), now)
        cached = planned.get(job, {})
        row = current.get(job) or cached.get('row') or {}
        if not row:
            try:
                manifest = read_json(folder / 'manifest.json')
                row = manifest if isinstance(manifest, dict) else {}
            except (OSError, ValueError):
                pass
        status = row.get('status', cached.get('status', 'unknown'))
        base = (row.get('published') if status in {'published', 'cleanup_eligible', 'complete'} else None)
        base = timestamp(base, timestamp(row.get('updated'), timestamp(row.get('created'), initial)))
        deadline = base + review_days * 86400
        deadline = min(deadline, timestamp(earlier.get(job, {}).get('review_deadline'), deadline))
        outcome = outcomes.get(job)
        reason = (outcome.removeprefix('retained: ') if outcome and outcome != 'cleaned'
                  else cached.get('reason', earlier.get(job, {}).get('reason', 'awaiting_lifecycle_cleanup')))
        jobs.append(dict(id=job, bytes=by_job.get(job, 0), status=status, reason=reason,
                         first_observed=initial, review_deadline=deadline, review_overdue=now >= deadline))
    total = jobs_bytes + state_bytes
    measurement_complete = not job_errors and not state_errors
    free = min(shutil.disk_usage(manager.jobs).free, shutil.disk_usage(manager.state).free)
    overdue = [j for j in jobs if j['review_overdue']]
    reasons = []
    if not measurement_complete:
        reasons.append('storage_measurement_incomplete')
    if total >= budget:
        reasons.append('workspace_storage_limit_reached')
    if free < 256 * 1024 ** 2:
        reasons.append('insufficient_free_disk_space')
    if overdue:
        reasons.append('retained_jobs_require_review')
    result = dict(version=1, observed=now, jobs_bytes=jobs_bytes, state_bytes=state_bytes,
                  cleanup_receipt_bytes=by_state.get('job-retention', 0), total_bytes=total,
                  growth_bytes=total - timestamp(previous.get('total_bytes'), total), budget_bytes=budget,
                  free_disk_bytes=free, measurement_complete=measurement_complete,
                  overdue_jobs=len(overdue), jobs=jobs, blockers=reasons,
                  warning=total >= .8 * budget, review_days=review_days)
    if persist:
        # One overwritten report; do not accumulate a new report on each launch.
        atomic_json(output, result)
    if announce or reasons or result['warning']:
        print('[STORAGE] jobs_bytes={jobs_bytes} state_bytes={state_bytes} growth_bytes={growth_bytes} '
              'budget_bytes={budget_bytes} overdue_jobs={overdue_jobs}'.format(**result))
        for item in overdue:
            print('[STORAGE] REVIEW REQUIRED job={id} bytes={bytes} reason={reason} '
                  'deadline={review_deadline}'.format(**item))
        if reasons:
            print('[STORAGE] New batches blocked: ' + ', '.join(reasons) +
                  '; resolve retained jobs or resume existing recovery. Report: ' + str(output))
        elif result['warning']:
            print('[STORAGE] Warning: workspace storage is at least 80% of its configured limit.')
    manager.last_storage_report = result
    return result


def check(manager, *, admitting=False):
    result = report(manager)
    blockers = result['blockers'] if admitting else [r for r in result['blockers'] if r != 'retained_jobs_require_review']
    if blockers:
        raise ValueError('Workspace storage budget/admission blocked; inspect state/job-retention/storage-report.json')
    return result
