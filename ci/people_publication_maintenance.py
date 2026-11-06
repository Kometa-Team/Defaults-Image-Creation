"""Exact additive publication successor; immutable historical receipts remain."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess

from ci.people_storage_maintenance import regular

ROOT = Path(__file__).resolve().parents[1]
BASE = 'a3c379b0681e583ec4387d83b040b504aa6bc33b'
RECEIPT = 'ci/people-publication-reliability-v1.json'
PIN = '34e0f9942b735b2110b8d6f7f63f5a9badcad040af8a0d7164baf75f6c7d7909'
MEMBERS = frozenset(('.github/workflows/people-bulk-validation.yml',
    'create_people_posters/people_github.py', 'create_people_posters/people_publication_state.py',
    'create_people_posters/publish_people_github.py',
    'create_people_posters/reliability_tests/test_publication_reliability.py',
    'create_people_posters/reliability_tests/test_tree_diagnostic.py',
    'ci/publication_tests/test_publication_maintenance.py'))
ANCHORS = frozenset((RECEIPT, 'ci/people_publication_maintenance.py'))


def digest(raw):
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


@lru_cache(maxsize=32)
def ancestry(head):
    git('merge-base', '--is-ancestor', BASE, head)


@lru_cache(maxsize=32)
def predecessor(name):
    entry = git('ls-tree', '-z', BASE, '--', name)
    if not entry:
        return None
    if not entry.startswith(b'100644 blob '):
        raise ValueError('Publication predecessor is not a regular file')
    return git('show', BASE + ':' + name)


def verify(root=ROOT):
    if Path(root).resolve() != ROOT.resolve():
        raise ValueError('Foreign publication policy checkout')
    value = json.loads(regular(ROOT, RECEIPT).read_bytes())
    if (fingerprint(value) != PIN or set(value) != {'version', 'baseline_commit', 'files', 'ci_authorized', 'publication_authorized'}
            or value['version'] != 1 or value['baseline_commit'] != BASE or set(value['files']) != MEMBERS
            or value['ci_authorized'] is not False or value['publication_authorized'] is not False):
        raise ValueError('Changed exact publication reliability receipt or authority')
    from ci.people_collection_maintenance import _head
    ancestry(_head(ROOT))
    for name, binding in value['files'].items():
        before = predecessor(name)
        if (set(binding) != {'operation', 'before_sha256', 'sha256', 'text_lf'} or binding['text_lf'] is not True
                or binding['operation'] != ('A' if before is None else 'M')
                or binding['before_sha256'] != (None if before is None else digest(before))
                or digest(regular(ROOT, name).read_bytes()) != binding['sha256']):
            raise ValueError('Changed physical publication successor: ' + name)
    return value['files']


def historical_bytes(root, name, current):
    if name not in MEMBERS:
        return current
    bindings = verify(root)
    if name in bindings and bindings[name]['before_sha256'] is not None and digest(current) == bindings[name]['sha256']:
        return predecessor(name)
    return current


def selected_hash(name, expected):
    if name not in MEMBERS:
        return expected
    binding = verify().get(name)
    return binding['sha256'] if binding and binding['before_sha256'] is not None and expected == binding['before_sha256'] else expected


def scope_members():
    return MEMBERS | ANCHORS
