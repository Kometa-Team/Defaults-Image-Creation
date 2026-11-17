"""Offline replay of an independently pinned GitHub export and artifact archives."""
import hashlib
import itertools
from contextlib import contextmanager
from pathlib import Path
import re
import stat
import zipfile

import yaml

from ci.validation import require, unique

PATHS = tuple('.github/workflows/'+name+'.yml' for name in (
    'default-poster-validation', 'dependency-provenance-validation',
    'lifecycle-m6-validation', 'lifecycle-m7-validation', 'people-bulk-validation',
    'people-job-retention', 'people-storage-validation', 'phase5-m2-validation',
    'phase5-m3-validation', 'phase5-m4-validation', 'phase5-m5-validation',
    'phase5-m6-validation'))
REPO = 'Kometa-Team/Defaults-Image-Creation'
SPECIAL = "${{ matrix.group == 'foundations' && format('Phase 4 operation foundations ({0})', matrix.os) || format('Phase 4 M5 transactions ({0}, {1})', matrix.os, matrix.group) }}"


def digest(path):
    with path.open('rb') as stream:
        return stream_digest(stream)


def stream_digest(stream):
    h = hashlib.sha256()
    for block in iter(lambda: stream.read(1024*1024), b''):
        h.update(block)
    return h.hexdigest()


@contextmanager
def verified_archive(path, metadata):
    # Hash and parse the same open archive, and recheck it before returning.
    # Do not hash a filename and subsequently reopen a different object.
    expected = metadata['digest'].split(':')[1]
    with path.open('rb') as stream:
        stream.seek(0, 2)
        require(stream.tell() == metadata['size_in_bytes'], 'Archive provenance digest mismatch')
        stream.seek(0)
        require(stream_digest(stream) == expected, 'Archive provenance digest mismatch')
        stream.seek(0)
        with zipfile.ZipFile(stream) as bundle:
            yield bundle
        stream.seek(0)
        require(stream_digest(stream) == expected, 'Archive changed during verification')


def render(value, matrix, head):
    if value == SPECIAL:
        return (f"Phase 4 operation foundations ({matrix['os']})" if matrix['group'] == 'foundations'
                else f"Phase 4 M5 transactions ({matrix['os']}, {matrix['group']})")
    value = value.replace('${{ github.event.pull_request.head.sha }}', head)
    value = re.sub(r'\$\{\{ matrix\.([a-z_]+) \}\}', lambda m: str(matrix[m[1]]), value)
    require('${{' not in value, 'Unreviewed workflow expression')
    return value


def job_plan(root, head):
    result = {}
    for path in PATHS:
        source = yaml.safe_load((root/path).read_text(encoding='utf8'))
        jobs, artifacts = set(), set()
        for key, job in source['jobs'].items():
            matrix = job.get('strategy', {}).get('matrix', {})
            require('exclude' not in matrix, 'Unreviewed matrix exclusion')
            if 'include' in matrix:
                require(set(matrix) == {'include'}, 'Unreviewed mixed matrix')
                choices = matrix['include']
            else:
                keys = list(matrix)
                choices = [dict(zip(keys, values)) for values in itertools.product(*(matrix[k] for k in keys))]
            for choice in choices:
                title = job.get('name', key+(' ('+', '.join(map(str, choice.values()))+')' if choice else ''))
                title = render(title, choice, head)
                require(title not in jobs, 'Duplicate planned job')
                jobs.add(title)
                for step in job['steps']:
                    if not str(step.get('uses', '')).startswith('actions/upload-artifact@'):
                        continue
                    condition = step.get('if')
                    require(condition in (None, '${{ always() }}', "${{ matrix.group == 'smoke' }}"),
                            'Unreviewed artifact condition')
                    if condition == "${{ matrix.group == 'smoke' }}" and choice.get('group') != 'smoke':
                        continue
                    name = render(step['with']['name'], choice, head)
                    require(name not in artifacts, 'Duplicate planned artifact')
                    artifacts.add(name)
        require(source['name'] not in result, 'Duplicate workflow')
        result[source['name']] = {'path': path, 'jobs': jobs, 'artifacts': artifacts}
    return result


def authenticate(root, index, snapshot, expected):
    """The caller authenticates snapshot bytes using a separately supplied digest."""
    require(set(snapshot) == {'repository', 'pull_request', 'runs'} and snapshot['repository'] == REPO,
            'Invalid GitHub provenance export')
    pr = snapshot['pull_request']
    require(pr['head']['sha'] == expected['head'] and pr['base']['sha'] == index['base']
            and pr['base']['repo']['full_name'] == REPO and pr['state'] == 'open'
            and pr['draft'] is True and pr['merged'] is False, 'Wrong final-head draft PR')
    plan = job_plan(root, expected['head'])
    indexed = {row['name']: row for row in index['workflows']}
    require(len(indexed) == len(index['workflows']) and set(indexed) == set(plan), 'Wrong indexed workflows')
    require(unique([item['run']['name'] for item in snapshot['runs']], 'exported workflow') == set(plan),
            'Missing/duplicate exported workflow')
    unique([item['run']['id'] for item in snapshot['runs']], 'run ID')
    artifact_rows = {}
    all_jobs = []
    for item in snapshot['runs']:
        require(set(item) == {'run', 'jobs', 'artifacts'}, 'Invalid exported run')
        run, jobs, artifacts = item['run'], item['jobs'], item['artifacts']
        name = run['name']
        require(type(run['id']) is int and run['id'] > 0 and run['head_sha'] == expected['head']
                and run['path'] == plan[name]['path'] and run['event'] == 'pull_request'
                and run['repository']['full_name'] == REPO
                and run['status'] == 'completed' and run['conclusion'] == 'success'
                and any(p['number'] == pr['number'] for p in run['pull_requests']), 'Wrong final-SHA run provenance')
        url = f"https://github.com/{REPO}/actions/runs/{run['id']}"
        require(run['html_url'] == url, 'Wrong run link')
        row = indexed[name]
        require((row['head'], row['status'], row['conclusion'], row['url']) ==
                (run['head_sha'], run['status'], run['conclusion'], url), 'Index/run provenance mismatch')
        require(type(jobs['total_count']) is int and jobs['total_count'] == len(jobs['jobs']), 'Truncated job pages')
        require(unique([j['name'] for j in jobs['jobs']], 'source job') == plan[name]['jobs'],
                'Missing/extra planned job')
        wanted = []
        for job in jobs['jobs']:
            require(type(job['id']) is int and job['id'] > 0 and job['run_id'] == run['id']
                    and job['head_sha'] == expected['head'] and job['status'] == 'completed'
                    and job['conclusion'] == 'success', 'Failed/stale exported job')
            wanted.append({k: job[k] for k in ('id', 'name', 'status', 'conclusion')})
            all_jobs.append(job['id'])
        require(sorted(row['jobs'], key=lambda j: j['id']) == sorted(wanted, key=lambda j: j['id']),
                'Omitted/substituted indexed job')
        require(type(artifacts['total_count']) is int and artifacts['total_count'] == len(artifacts['artifacts']),
                'Truncated artifact pages')
        require(unique([a['name'] for a in artifacts['artifacts']], 'source artifact') == plan[name]['artifacts'],
                'Missing/extra planned artifact')
        for artifact in artifacts['artifacts']:
            require(type(artifact['id']) is int and artifact['id'] > 0 and artifact['id'] not in artifact_rows
                    and artifact['expired'] is False and artifact['workflow_run']['id'] == run['id']
                    and artifact['workflow_run']['head_sha'] == expected['head']
                    and re.fullmatch('sha256:[0-9a-f]{64}', artifact['digest']) is not None,
                    'Wrong final-SHA artifact provenance')
            artifact_rows[artifact['id']] = (name, artifact)
    unique(all_jobs, 'global job ID')
    return artifact_rows


def archives(root, archive_root, index, artifact_rows, safe):
    require({p.name for p in archive_root.iterdir()} == {f'{i}.zip' for i in artifact_rows},
            'Missing/extra downloaded archive')
    groups = {i: [] for i in artifact_rows}
    for item in index['files']:
        require(item['artifact_id'] in groups, 'Unproven artifact ID')
        groups[item['artifact_id']].append(item)
    for aid, (workflow, artifact) in artifact_rows.items():
        archive = safe(archive_root, f'{aid}.zip')
        require(groups[aid] and all(f['workflow'] == workflow for f in groups[aid]), 'Artifact owner mismatch')
        files = {f['path']: f for f in groups[aid]}
        with verified_archive(archive, artifact) as bundle:
            members = []
            for entry in bundle.infolist():
                # Reject malicious names even for directory entries.
                relative = entry.filename.rstrip('/')
                require(relative and not relative.startswith('/') and '\\' not in relative and ':' not in relative
                        and all(p not in ('', '.', '..') for p in relative.split('/')), 'Unsafe archive member')
                mode = entry.external_attr >> 16
                require(stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR), 'Unsafe archive mode')
                if not entry.is_dir():
                    members.append(entry)
            names = [artifact['name']+'/'+entry.filename for entry in members]
            require(unique(names, 'ZIP member') == set(files), 'Index/archive membership mismatch')
            for entry, name in zip(members, names):
                require(entry.file_size <= 200*1024*1024, 'Encoded member size bound')
                h = hashlib.sha256()
                with bundle.open(entry) as stream:
                    for block in iter(lambda: stream.read(1024*1024), b''):
                        h.update(block)
                require(h.hexdigest() == files[name]['sha256'], 'Index/archive byte mismatch')
                require(digest(safe(root, name)) == h.hexdigest(), 'Extracted/archive byte mismatch')
