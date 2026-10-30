"""Exact additive M2 scope successor; frozen historical manifests stay intact."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess

from ci.people_storage_maintenance import regular

ROOT = Path(__file__).resolve().parents[1]
BASE = '8e0bfa22329c33bd9b342760976b23dc205eabc4'
MANIFEST = ROOT / 'ci/phase5-m2-maintenance-v1.json'
PIN = 'cd12550aa60052fad5dcad9389da12e902dab5ef3ead5cbfa13eb85b79ce5ce6'
MEMBERS = frozenset({
    'ci/dependabot_maintenance.py',
    'ci/dependency_tests/test_phase5_m2_maintenance.py',
    'ci/phase5_m2.py', 'ci/phase5-m2-test-ids.json',
    '.github/workflows/phase5-m2-validation.yml',
    'create_defaults/bulk/lifecycle/github_observation_transport.py',
    'create_defaults/bulk/lifecycle/github_observations.py',
    'create_defaults/phase5/m2_tests/test_observations.py',
    'create_defaults/lifecycle/PHASE5_M2_IMPLEMENTATION.md',
    'create_defaults/lifecycle/PHASE5_M2_ACCEPTANCE.json',
    'create_defaults/lifecycle/PHASE5_M2_CI_MAINTENANCE.md',
    'create_defaults/lifecycle/ROADMAP.md',
})
ANCHORS = frozenset({'ci/phase5_m2_maintenance.py', 'ci/phase5-m2-maintenance-v1.json'})


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
            or value['production_intersection'] != [] or value['adoption_intersection'] != []):
        raise ValueError('Changed exact M2 maintenance transition')
    return value


def manifest():
    return _decode(regular(ROOT, MANIFEST.relative_to(ROOT).as_posix()).read_bytes(), PIN)


def _git(root, *args):
    with subprocess.Popen(['git', *args], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        raw, _ = process.communicate()
        if process.returncode:
            raise ValueError('Cannot verify M2 maintenance history')
        return raw.replace(b'\r\n', b'\n')


@lru_cache(maxsize=8)
def _old(name):
    return _git(ROOT, 'show', BASE + ':' + name)


@lru_cache(maxsize=32)
def _ancestry(root, head):
    _git(root, 'merge-base', '--is-ancestor', BASE, head)


def verify_checkout(root=None):
    root = Path(root or ROOT)
    from ci.phase5_m3_maintenance import verify_checkout as verify_m3, historical_bytes as m3_bytes
    verify_m3(root)
    value = manifest()
    from ci.people_colorize_maintenance import _head
    _ancestry(str(root), _head(root))
    for name, binding in value['members'].items():
        if sha(m3_bytes(root, name, regular(root, name).read_bytes())) != binding['sha256']:
            raise ValueError('Unreviewed M2 successor: ' + name)
        if binding['before_sha256'] is not None and sha(_old(name)) != binding['before_sha256']:
            raise ValueError('Changed M2 predecessor: ' + name)
    for name in ANCHORS:
        regular(root, name)
    return value


def scope_members():
    # M7 already owns this status path. Keep its exact bytes bound above, but
    # do not hijack legacy planning fixtures' existing ALLOWED path routing.
    from ci.phase5_m3_maintenance import scope_members as m3_scope
    return ((MEMBERS | ANCHORS) - {'create_defaults/lifecycle/ROADMAP.md'}) | m3_scope()


def verify_scope(root, baseline, names):
    verify_checkout(root)
    from ci.phase5_m3_maintenance import scope_members as m3_scope, verify_scope as verify_m3_scope
    m3_names = names & m3_scope()
    if m3_names:
        verify_m3_scope(root, baseline, m3_names)
    names = names - m3_names
    if not names <= scope_members():
        raise ValueError('Unapproved M2 scope')
    if not names:
        return
    rows = _git(root, 'diff', '--raw', '--no-abbrev', '--no-renames', '-z',
                baseline, 'HEAD', '--', *sorted(names)).split(b'\0')
    if rows[-1] != b'' or len(rows) != 2 * len(names) + 1:
        raise ValueError('Incomplete M2 scope diff')
    seen = set()
    for offset in range(0, len(rows) - 1, 2):
        fields, name = rows[offset].split(), rows[offset + 1].decode('utf8')
        if (name not in names or name in seen or len(fields) != 5
                or fields[:2] not in ([b':000000', b'100644'], [b':100644', b'100644'])
                or fields[4] != (b'A' if fields[0] == b':000000' else b'M')):
            raise ValueError('M2 requires regular-file additions/modifications')
        regular(root, name)
        seen.add(name)
