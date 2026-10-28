"""Exact People startup/progress successors; historical inventories stay sealed."""
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from ci.people_storage_maintenance import regular

ROOT = Path(__file__).resolve().parents[1]
BASE = 'fee76362f7380fb77713955289b640c11817d611'
SOURCE = 'create_people_posters/orchestrator.py'
SOURCES = frozenset({SOURCE, 'create_people_posters/remove_bg_birefnet.py'})
PINNED = SOURCES | {'create_people_posters/tests/test_remove_bg_birefnet.py'}
MANIFEST = ROOT / 'ci/people-colorize-maintenance-v1.json'
PIN = '3bf1d9f52c7b6c9fe494d261405075ec065a3a428fd92074e1f3fd7bcc2fd0b8'
MEMBERS = frozenset({
    SOURCE, 'create_people_posters/.env.example', 'create_people_posters/README.md',
    'create_people_posters/tests/test_ddcolor_colorizer.py',
    'create_people_posters/remove_bg_birefnet.py',
    'create_people_posters/tests/test_remove_bg_birefnet.py',
    'ci/people_retention_maintenance.py',
    'ci/dependency_tests/test_people_colorize_maintenance.py',
})
ANCHORS = frozenset({'ci/people_colorize_maintenance.py', 'ci/people-colorize-maintenance-v1.json'})


def sha(raw):
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def _git(root, *args):
    # Separate checked transport keeps historical fixtures' Git interceptors
    # scoped to their own original commands. No mutable file result is cached.
    with subprocess.Popen(['git', *args], cwd=root, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE) as process:
        output, error = process.communicate()
        if process.returncode:
            raise ValueError('Cannot verify DDColor maintenance Git history')
        return output.replace(b'\r\n', b'\n')


@lru_cache(maxsize=64)
def _old(root, name):
    return _git(root, 'show', BASE + ':' + name)


@lru_cache(maxsize=32)
def _ancestry(root, head):
    _git(root, 'merge-base', '--is-ancestor', BASE, head)


def _head(root):
    # Actions checks out a detached HEAD. Read that exact commit afresh instead
    # of spawning Git on every nested source check. Branches, worktrees and Git
    # discovery overrides retain Git's authoritative resolution. Ancestry below
    # is still verified for the resulting immutable commit, never a cached path.
    if not any(name in os.environ for name in ('GIT_DIR', 'GIT_COMMON_DIR', 'GIT_WORK_TREE', 'GIT_NAMESPACE')):
        try:
            head = (Path(root) / '.git' / 'HEAD').read_text(encoding='ascii').strip()
        except (OSError, UnicodeError):
            pass
        else:
            if re.fullmatch(r'[0-9a-f]{40}', head):
                return head
    return _git(root, 'rev-parse', 'HEAD').decode().strip()


def manifest():
    value = json.loads(regular(ROOT, MANIFEST.relative_to(ROOT).as_posix()).read_bytes())
    if (fingerprint(value) != PIN or value['version'] != 1
            or value['baseline_commit'] != BASE or set(value['members']) != MEMBERS
            or value['production_successors'] != sorted(SOURCES)
            or value['publication_authorized'] is not False):
        raise ValueError('Changed exact DDColor maintenance transition')
    return value


def verify_checkout(root=None):
    root = Path(root or ROOT)
    value = manifest()
    head = _head(root)
    _ancestry(str(root), head)
    for name, binding in value['members'].items():
        if sha(regular(root, name).read_bytes()) != binding['sha256']:
            raise ValueError('Changed exact DDColor maintenance source: ' + name)
        if binding['before_sha256'] is not None:
            if sha(_old(str(root), name)) != binding['before_sha256']:
                raise ValueError('Changed DDColor maintenance predecessor: ' + name)
    for name in ANCHORS:
        regular(root, name)
    return value


def selected_hash(name, expected):
    if name not in PINNED:
        return expected
    binding = manifest()['members'][name]
    if expected != binding['before_sha256']:
        return expected
    verify_checkout()
    return binding['sha256']


def scope_members():
    return MEMBERS | ANCHORS


def verify_scope(root, baseline, names):
    verify_checkout(root)
    if not names <= scope_members():
        raise ValueError('Unauthorized DDColor maintenance scope')
    rows = _git(root, 'diff', '--raw', '--no-abbrev', '--no-renames', '-z',
                baseline, 'HEAD', '--', *sorted(names)).split(b'\0')
    if rows[-1] != b'' or len(rows) != 2 * len(names) + 1:
        raise ValueError('Incomplete DDColor maintenance diff')
    seen = set()
    for offset in range(0, len(rows) - 1, 2):
        fields, name = rows[offset].split(), rows[offset + 1].decode('utf8')
        if (name not in names or name in seen or len(fields) != 5
                or fields[:2] not in ([b':000000', b'100644'], [b':100644', b'100644'])
                or fields[4] != (b'A' if fields[0] == b':000000' else b'M')):
            raise ValueError('DDColor maintenance requires exact regular-file additions/modifications')
        regular(root, name)
        seen.add(name)
