"""Exact README publication successors; preserve every historical inventory."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess

from ci.people_storage_maintenance import regular

ROOT = Path(__file__).resolve().parents[1]
BASE = 'deb9a3a2f609600a395c5be8b268805de5a5efa3'
MANIFEST = ROOT / 'ci/people-readme-maintenance-v1.json'
PIN = '4bf36581375ccf6f5a842d01688bbd096555a7f27892cdfa424dbc1f0cf01914'
ANCHORS = frozenset({'ci/people_readme_maintenance.py', 'ci/people-readme-maintenance-v1.json'})


def sha(raw):
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def manifest():
    value = json.loads(regular(ROOT, MANIFEST.relative_to(ROOT).as_posix()).read_bytes())
    if (fingerprint(value) != PIN or value['version'] != 1
            or value['baseline_commit'] != BASE or value['publication_authorized'] is not False):
        raise ValueError('Changed exact README publication transition')
    return value


def _git(root, *args):
    # Independent transport preserves legacy fixtures' frozen Git interceptors.
    with subprocess.Popen(['git', *args], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        output, _ = process.communicate()
        if process.returncode:
            raise ValueError('Cannot verify README publication Git history')
        return output.replace(b'\r\n', b'\n')


@lru_cache(maxsize=128)
def _old(name):
    return _git(ROOT, 'show', BASE + ':' + name)


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
            raise ValueError('Unreviewed README publication successor: ' + name)
        if binding['before_sha256'] is not None and sha(_old(name)) != binding['before_sha256']:
            raise ValueError('Changed README publication predecessor: ' + name)
    for name in ANCHORS:
        regular(root, name)
    return value


def selected_hash(name, expected):
    binding = manifest()['members'].get(name)
    if binding is None or binding['before_sha256'] is None or expected != binding['before_sha256']:
        return expected
    verify_checkout()
    return binding['sha256']


def historical_bytes(root, name, current):
    binding = manifest()['members'].get(name)
    if binding is None or binding['before_sha256'] is None:
        return current
    if sha(current) != binding['sha256']:
        raise ValueError('Changed README publication historical view: ' + name)
    old = _old(name)
    if sha(old) != binding['before_sha256']:
        raise ValueError('Changed README publication historical predecessor: ' + name)
    return old


def scope_members():
    return set(manifest()['members']) | ANCHORS


def test_ids():
    return list(manifest()['pytest_ids'])


def verify_scope(root, baseline, names):
    verify_checkout(root)
    if not names <= scope_members():
        raise ValueError('Unapproved README publication scope')
    rows = _git(root, 'diff', '--raw', '--no-abbrev', '--no-renames', '-z',
                baseline, 'HEAD', '--', *sorted(names)).split(b'\0')
    if rows[-1] != b'' or len(rows) != 2 * len(names) + 1:
        raise ValueError('Incomplete README publication diff')
    seen = set()
    for offset in range(0, len(rows) - 1, 2):
        fields, name = rows[offset].split(), rows[offset + 1].decode('utf8')
        if (name not in names or name in seen or len(fields) != 5
                or fields[:2] not in ([b':000000', b'100644'], [b':100644', b'100644'])
                or fields[4] != (b'A' if fields[0] == b':000000' else b'M')):
            raise ValueError('README publication requires regular-file additions/modifications')
        regular(root, name)
        seen.add(name)
