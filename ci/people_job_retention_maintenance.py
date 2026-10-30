"""Exact startup-retention successor; historical inventories remain immutable."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess

from ci.people_storage_maintenance import regular

ROOT = Path(__file__).resolve().parents[1]
BASE = '120ed09a166ddfdc5380219aad35959c8a0de169'
MANIFEST = ROOT / 'ci/people-job-retention-maintenance-v1.json'
PIN = '7f2ef8dbbd120c6fbce410d20e249210f64d21eb574aaa22cbbf9482152074b5'
MEMBERS = frozenset({
    '.github/workflows/people-job-retention.yml',
    'ci/dependabot_maintenance.py',
    'ci/phase5_m3_maintenance.py',
    'ci/dependency_tests/test_people_colorize_maintenance.py',
    'ci/dependency_tests/test_people_retention.py',
    'ci/dependency_tests/test_people_job_retention_maintenance.py',
    'create_people_posters/.env.example',
    'create_people_posters/orchestrator.py',
    'create_people_posters/people_job_retention.py',
    'create_people_posters/people_storage_watch.py',
    'create_people_posters/people_workspaces.py',
    'create_people_posters/tests/test_people_api_orchestrator.py',
    'create_people_posters/tests/test_people_job_retention.py',
    'create_people_posters/tests/test_people_storage_watch.py',
    'create_people_posters/tests/test_people_workspaces.py',
    'docs/PEOPLE_JOB_RETENTION_INVENTORY_2026-10-30.json',
    'docs/PEOPLE_STARTUP_JOB_RETENTION.md',
})
ANCHORS = frozenset({'ci/people_job_retention_maintenance.py', 'ci/people-job-retention-maintenance-v1.json'})


def sha(raw):
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        allow_nan=False, separators=(',', ':')).encode()).hexdigest()


@lru_cache(maxsize=8)
def _decode(raw, pin):
    value = json.loads(raw)
    if (fingerprint(value) != pin or value['version'] != 1
            or value['baseline_commit'] != BASE or set(value['members']) != MEMBERS
            or value['publication_authorized'] is not False):
        raise ValueError('Changed exact startup-retention transition')
    return value


def manifest():
    return _decode(regular(ROOT, MANIFEST.relative_to(ROOT).as_posix()).read_bytes(), PIN)


def _git(root, *args):
    with subprocess.Popen(['git', *args], cwd=root, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE) as process:
        output, _ = process.communicate()
        if process.returncode:
            raise ValueError('Cannot verify startup-retention Git history')
        return output.replace(b'\r\n', b'\n')


@lru_cache(maxsize=64)
def _old(name):
    return _git(ROOT, 'show', BASE + ':' + name)


@lru_cache(maxsize=64)
def _baseline_entry(name):
    return _git(ROOT, 'ls-tree', BASE, '--', name)


@lru_cache(maxsize=32)
def _ancestry(root, head):
    _git(root, 'merge-base', '--is-ancestor', BASE, head)


def verify_checkout(root=None):
    root = Path(root or ROOT)
    value = manifest()
    from ci.people_colorize_maintenance import _head
    _ancestry(str(root), _head(root))
    for name, binding in value['members'].items():
        if sha(regular(root, name).read_bytes()) != binding['sha256']:
            raise ValueError('Unreviewed startup-retention successor: ' + name)
        if binding['before_sha256'] is None:
            if _baseline_entry(name):
                raise ValueError('Startup-retention addition already exists: ' + name)
        elif sha(_old(name)) != binding['before_sha256']:
            raise ValueError('Changed startup-retention predecessor: ' + name)
    for name in ANCHORS:
        regular(root, name)
    return value


def selected_hash(name, expected):
    if name not in MEMBERS:
        return expected
    binding = manifest()['members'][name]
    if binding['before_sha256'] is None or expected != binding['before_sha256']:
        return expected
    verify_checkout()
    return binding['sha256']


def historical_bytes(root, name, current):
    if name not in MEMBERS:
        return current
    binding = manifest()['members'][name]
    if sha(current) != binding['sha256']:
        raise ValueError('Changed startup-retention historical successor: ' + name)
    if binding['before_sha256'] is None:
        return current
    old = _old(name)
    if sha(old) != binding['before_sha256']:
        raise ValueError('Changed startup-retention historical predecessor: ' + name)
    return old


def scope_members():
    return MEMBERS | ANCHORS


def verify_scope(root, baseline, names):
    verify_checkout(root)
    if not names <= scope_members():
        raise ValueError('Unapproved startup-retention scope')
    if not names:
        return
    rows = _git(root, 'diff', '--raw', '--no-abbrev', '--no-renames', '-z',
                baseline, 'HEAD', '--', *sorted(names)).split(b'\0')
    if rows[-1] != b'' or len(rows) != 2 * len(names) + 1:
        raise ValueError('Incomplete startup-retention diff')
    seen = set()
    for offset in range(0, len(rows) - 1, 2):
        fields, name = rows[offset].split(), rows[offset + 1].decode('utf8')
        if (name not in names or name in seen or len(fields) != 5
                or fields[:2] not in ([b':000000', b'100644'], [b':100644', b'100644'])
                or fields[4] != (b'A' if fields[0] == b':000000' else b'M')):
            raise ValueError('Startup retention requires regular-file additions/modifications')
        regular(root, name)
        seen.add(name)
