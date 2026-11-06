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
GIT_RECEIPT = 'ci/people-publication-git-v2.json'
GIT_PIN = 'c94ab21b0330c22e4fea05c268ec0fa4dd9509b8409bc0c835295e690bd40b21'
GIT_MEMBERS = frozenset(('create_people_posters/publish_people_github.py',
    'create_people_posters/people_publication_state.py', 'create_people_posters/people_git_transport.py',
    'create_people_posters/reliability_tests/test_git_publication.py',
    'ci/publication_tests/test_git_publication_maintenance.py',
    'create_people_posters/people_native_operator.py',
    'create_people_posters/reliability_tests/test_native_operator.py'))


def git_bindings(root=ROOT):
    """Exact additive v2; embedded v1 bytes remain bound to the immutable receipt."""
    if Path(root).resolve() != ROOT.resolve():
        raise ValueError('Foreign native Git policy checkout')
    value = json.loads(regular(ROOT, GIT_RECEIPT).read_bytes())
    if (fingerprint(value) != GIT_PIN or set(value) != {'version', 'files', 'ci_authorized', 'publication_authorized', 'historical_receipt_sha256'}
            or value['version'] != 2 or set(value['files']) != GIT_MEMBERS
            or value['ci_authorized'] is not False or value['publication_authorized'] is not False
            or digest(regular(ROOT, RECEIPT).read_bytes()) != value['historical_receipt_sha256']):
        raise ValueError('Changed exact native Git receipt or authority')
    historical = json.loads(regular(ROOT, RECEIPT).read_bytes())['files']
    for name, binding in value['files'].items():
        if (set(binding) != {'operation','before_sha256','sha256','text_lf','predecessor_lf'}
                or binding['text_lf'] is not True or digest(regular(ROOT,name).read_bytes()) != binding['sha256']):
            raise ValueError('Changed physical native Git successor: '+name)
        if name in historical:
            if (binding['operation'] != 'M' or type(binding['predecessor_lf']) is not str
                    or digest(binding['predecessor_lf'].encode()) != binding['before_sha256']
                    or binding['before_sha256'] != historical[name]['sha256']):
                raise ValueError('Changed native Git qualified predecessor')
        elif binding['operation'] != 'A' or binding['before_sha256'] is not None or binding['predecessor_lf'] is not None or predecessor(name) is not None:
            raise ValueError('Expanded native Git addition scope')
    return value['files']


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
    successors = git_bindings(root)
    effective = {}
    for name, binding in value['files'].items():
        before = predecessor(name)
        physical = regular(ROOT, name).read_bytes()
        historical_current = successors[name]['predecessor_lf'].encode() if name in successors else physical
        if (set(binding) != {'operation', 'before_sha256', 'sha256', 'text_lf'} or binding['text_lf'] is not True
                or binding['operation'] != ('A' if before is None else 'M')
                or binding['before_sha256'] != (None if before is None else digest(before))
                or digest(historical_current) != binding['sha256']):
            raise ValueError('Changed physical publication successor: ' + name)
        effective[name] = dict(binding, sha256=successors[name]['sha256']) if name in successors else binding
    return effective


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
    return MEMBERS | ANCHORS | GIT_MEMBERS | {GIT_RECEIPT}
