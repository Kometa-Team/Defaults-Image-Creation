"""Separately reviewed exact M3 successor; original M2 pins stay unchanged."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess

from ci.people_storage_maintenance import regular

ROOT = Path(__file__).resolve().parents[1]
BASE = '67525e98c79425dfb669f7e9da1141f9b3c3a00e'
MANIFEST = ROOT / 'ci/phase5-m3-maintenance-v1.json'
PIN = 'adff4fe59d59092ecdcae64ff9c573d18a72ac7cad6389a7ec0881371f407a59'
MEMBERS = frozenset({
    'ci/phase5_m2_maintenance.py', 'ci/phase5_m3.py', 'ci/phase5-m3-test-ids.json',
    'ci/dependency_tests/test_phase5_m3_maintenance.py',
    '.github/workflows/phase5-m3-validation.yml',
    'create_defaults/bulk/lifecycle/github_decisions.py',
    'create_defaults/phase5/m3_tests/helpers.py',
    'create_defaults/phase5/m3_tests/test_decisions.py',
    'create_defaults/lifecycle/PHASE5_M3_IMPLEMENTATION.md',
    'create_defaults/lifecycle/PHASE5_M3_ACCEPTANCE.json',
    'create_defaults/lifecycle/PHASE5_M3_CI_MAINTENANCE.md',
    'create_defaults/lifecycle/ROADMAP.md',
})
ANCHORS = frozenset({'ci/phase5_m3_maintenance.py', 'ci/phase5-m3-maintenance-v1.json'})


def sha(raw):
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        allow_nan=False, separators=(',', ':')).encode()).hexdigest()


@lru_cache(maxsize=8)
def _decode(raw, pin):
    value = json.loads(raw)
    if (fingerprint(value) != pin or value['version'] != 1 or value['baseline_commit'] != BASE
            or set(value['members']) != MEMBERS or value['publication_authorized'] is not False
            or value['production_intersection'] != [] or value['adoption_intersection'] != []
            or value['frozen_m7_intersection'] != []):
        raise ValueError('Changed exact M3 maintenance transition')
    return value


def manifest():
    return _decode(regular(ROOT, MANIFEST.relative_to(ROOT).as_posix()).read_bytes(), PIN)


def _git(root, *args):
    with subprocess.Popen(['git', *args], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        raw, _ = process.communicate()
        if process.returncode:
            raise ValueError('Cannot verify M3 maintenance history')
        return raw.replace(b'\r\n', b'\n')


@lru_cache(maxsize=8)
def _old(name):
    return _git(ROOT, 'show', BASE + ':' + name)


@lru_cache(maxsize=32)
def _ancestry(root, head):
    _git(root, 'merge-base', '--is-ancestor', BASE, head)


def verify_checkout(root=None):
    root = Path(root or ROOT)
    from ci.people_job_retention_maintenance import verify_checkout as verify_retention, historical_bytes as retention_history
    verify_retention(root)
    value = manifest()
    from ci.people_colorize_maintenance import _head
    _ancestry(str(root), _head(root))
    for name, binding in value['members'].items():
        if sha(retention_history(root, name, regular(root, name).read_bytes())) != binding['sha256']:
            raise ValueError('Unreviewed M3 successor: ' + name)
        if binding['before_sha256'] is not None and sha(_old(name)) != binding['before_sha256']:
            raise ValueError('Changed M3 predecessor: ' + name)
    for name in ANCHORS:
        regular(root, name)
    return value


def historical_bytes(root, name, current):
    from ci.people_job_retention_maintenance import historical_bytes as retention_history
    current = retention_history(root, name, current)
    if name not in MEMBERS:
        return current
    binding = manifest()['members'][name]
    if binding['before_sha256'] is None:
        return current
    if sha(current) != binding['sha256']:
        raise ValueError('Changed M3 historical successor: ' + name)
    before = _old(name)
    if sha(before) != binding['before_sha256']:
        raise ValueError('Changed M3 historical predecessor: ' + name)
    return before


def scope_members():
    return (MEMBERS | ANCHORS) - {'create_defaults/lifecycle/ROADMAP.md'}


def verify_scope(root, baseline, names):
    verify_checkout(root)
    if not names <= scope_members():
        raise ValueError('Unapproved M3 scope')
    if not names:
        return
    rows = _git(root, 'diff', '--raw', '--no-abbrev', '--no-renames', '-z', baseline, 'HEAD', '--', *sorted(names)).split(b'\0')
    if rows[-1] != b'' or len(rows) != 2 * len(names) + 1:
        raise ValueError('Incomplete M3 scope diff')
    seen = set()
    for offset in range(0, len(rows)-1, 2):
        fields, name = rows[offset].split(), rows[offset+1].decode('utf8')
        if (name not in names or name in seen or len(fields) != 5
                or fields[:2] not in ([b':000000', b'100644'], [b':100644', b'100644'])
                or fields[4] != (b'A' if fields[0] == b':000000' else b'M')):
            raise ValueError('M3 requires regular-file additions/modifications')
        regular(root, name)
        seen.add(name)
