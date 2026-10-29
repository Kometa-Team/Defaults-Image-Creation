"""Exact dependency-audit successors, without rewriting historical inventories."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess

from ci.people_storage_maintenance import regular

ROOT = Path(__file__).resolve().parents[1]
BASE = 'd013af718881dc5ec82178ee85540e29a0fb7ec3'
MANIFEST = ROOT / 'ci/dependabot-maintenance-v1.json'
PIN = 'ce975a74d8eec8bd29c9af1cc4c88e04fcec3db75188333a08c88ab772415e74'
MEMBERS = frozenset({
    '.github/workflows/dependency-provenance-validation.yml',
    'README.md',
    'ci/people_readme_maintenance.py',
    'ci/dependency_maintenance.py',
    'ci/dependency_tests/test_dependency_maintenance.py',
    'ci/dependency_tests/test_people_readme_maintenance.py',
    'ci/dependency_tests/test_dependabot_audit.py',
    'create_defaults/phase2/requirements.txt',
    'create_people_posters/requirements.txt',
    'create_people_posters/requirements-rembg.txt',
    'docs/DEPENDABOT_AUDIT_2026-10-29.md',
    'docs/dependabot-audit-2026-10-29.json',
})
ANCHORS = frozenset({'ci/dependabot_maintenance.py', 'ci/dependabot-maintenance-v1.json'})


@lru_cache(maxsize=128)
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
        raise ValueError('Changed exact Dependabot audit transition')
    return value


def manifest():
    return _decode(regular(ROOT, MANIFEST.relative_to(ROOT).as_posix()).read_bytes(), PIN)


def _git(root, *args):
    # Keep legacy fixtures' frozen Git interceptors scoped to their own commands.
    with subprocess.Popen(['git', *args], cwd=root, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE) as process:
        output, _ = process.communicate()
        if process.returncode:
            raise ValueError('Cannot verify dependency-audit Git history')
        return output.replace(b'\r\n', b'\n')


@lru_cache(maxsize=32)
def _old(name):
    return _git(ROOT, 'show', BASE + ':' + name)


@lru_cache(maxsize=32)
def _ancestry(root, head):
    _git(root, 'merge-base', '--is-ancestor', BASE, head)


def verify_checkout(root=None):
    root = Path(root or ROOT)
    from ci.phase5_m2_maintenance import verify_checkout as verify_m2
    verify_m2(root)
    value = manifest()
    from ci.people_colorize_maintenance import _head
    _ancestry(str(root), _head(root))
    for name, binding in value['members'].items():
        if sha(regular(root, name).read_bytes()) != binding['sha256']:
            raise ValueError('Unreviewed dependency-audit successor: ' + name)
        if binding['before_sha256'] is not None and sha(_old(name)) != binding['before_sha256']:
            raise ValueError('Changed dependency-audit predecessor: ' + name)
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
    if binding['before_sha256'] is None:
        return current
    if sha(current) != binding['sha256']:
        raise ValueError('Changed dependency-audit historical view: ' + name)
    old = _old(name)
    if sha(old) != binding['before_sha256']:
        raise ValueError('Changed dependency-audit historical predecessor: ' + name)
    return old


def scope_members():
    from ci.phase5_m2_maintenance import scope_members as m2_scope
    return MEMBERS | ANCHORS | m2_scope()


def verify_scope(root, baseline, names):
    verify_checkout(root)
    from ci.phase5_m2_maintenance import scope_members as m2_scope, verify_scope as verify_m2_scope
    m2_names = names & m2_scope()
    if m2_names:
        verify_m2_scope(root, baseline, m2_names)
    names = names - m2_names
    if not names:
        return
    if not names <= scope_members():
        raise ValueError('Unapproved dependency-audit scope')
    rows = _git(root, 'diff', '--raw', '--no-abbrev', '--no-renames', '-z',
                baseline, 'HEAD', '--', *sorted(names)).split(b'\0')
    if rows[-1] != b'' or len(rows) != 2 * len(names) + 1:
        raise ValueError('Incomplete dependency-audit diff')
    seen = set()
    for offset in range(0, len(rows) - 1, 2):
        fields, name = rows[offset].split(), rows[offset + 1].decode('utf8')
        if (name not in names or name in seen or len(fields) != 5
                or fields[:2] not in ([b':000000', b'100644'], [b':100644', b'100644'])
                or fields[4] != (b'A' if fields[0] == b':000000' else b'M')):
            raise ValueError('Dependency audit requires regular-file additions/modifications')
        regular(root, name)
        seen.add(name)
