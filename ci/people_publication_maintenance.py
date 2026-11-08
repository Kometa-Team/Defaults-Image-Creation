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
# Exact v1 dependency successor; the historical bulk receipt remains immutable.
CI_TEST_LOCK = 'create_people_posters/bulk/test-requirements.lock'
CI_TEST_LOCK_BEFORE_SHA = 'ec7e3966bf58314bf284e9bce0f0c4ab646380daed8a01bde5fcc8a243674722'
CI_TEST_LOCK_SHA = '6536842b317555b0d34384f7bebc7a371569f2519bb90527331fae8aa64b9cc7'
GIT_RECEIPT = 'ci/people-publication-git-v2.json'
GIT_PIN = '8b942f48ef2f75174a58b846b2ce109cd8f8e1a47a466e4aa20a3202a2945b3a'
GIT_MEMBERS = frozenset(('create_people_posters/publish_people_github.py',
    'create_people_posters/people_publication_state.py', 'create_people_posters/people_git_transport.py',
    'create_people_posters/reliability_tests/test_git_publication.py',
    'ci/publication_tests/test_git_publication_maintenance.py',
    'create_people_posters/people_native_operator.py',
    'create_people_posters/reliability_tests/test_native_operator.py'))


RECOVERY_BASE = '0ad49fbec9283387aacc0378f9d6a796839d981d'
RECOVERY_RECEIPT = 'ci/people-publication-git-recovery-v1.json'
RECOVERY_PIN = 'ae385b405aafee29acd43993f8352da926ba95a396360266b802023275aa28df'
RECOVERY_MEMBERS = frozenset(('ci/publication_tests/test_git_recovery_maintenance.py', 'create_people_posters/people_git_recovery.py', 'create_people_posters/people_git_transport.py', 'create_people_posters/people_publication_state.py', 'create_people_posters/reliability_tests/test_git_recovery.py'))


def timeout_bytes(root, name, current):
    from ci.phase5_m6_maintenance import timeout_bytes as project
    return project(root, name, current)


def timeout_hash(name, expected):
    from ci.phase5_m6_maintenance import timeout_selected_hash
    return timeout_selected_hash(name, expected)


def recovery_bindings(root=ROOT):
    """Versioned exact recovery successor; historical native receipt stays intact."""
    if Path(root).resolve()!=ROOT.resolve():raise ValueError('Foreign recovery policy checkout')
    value=json.loads(regular(ROOT,RECOVERY_RECEIPT).read_bytes())
    if (fingerprint(value)!=RECOVERY_PIN or set(value)!={'version','baseline_commit','files','historical_native_receipt_sha256','ci_authorized','publication_authorized'}
            or value['version']!=1 or value['baseline_commit']!=RECOVERY_BASE or set(value['files'])!=RECOVERY_MEMBERS
            or value['ci_authorized'] is not False or value['publication_authorized'] is not False
            or digest(regular(ROOT,GIT_RECEIPT).read_bytes())!=value['historical_native_receipt_sha256']):
        raise ValueError('Changed exact recovery receipt or authority')
    old=json.loads(regular(ROOT,GIT_RECEIPT).read_bytes())
    if fingerprint(old)!=GIT_PIN:raise ValueError('Changed historical native receipt')
    from ci.people_collection_maintenance import _head
    _recovery_ancestry(_head(ROOT))
    for name,b in value['files'].items():
        if (set(b)!={'operation','text_lf','before_sha256','predecessor_lf','sha256'} or b['text_lf'] is not True
                or digest(timeout_bytes(root,name,regular(ROOT,name).read_bytes()))!=b['sha256']):raise ValueError('Changed physical recovery successor: '+name)
        before=_recovery_predecessor(name)
        if before is None:
            if b['operation']!='A' or b['before_sha256'] is not None or b['predecessor_lf'] is not None:raise ValueError('Expanded recovery addition')
        elif (b['operation']!='M' or type(b['predecessor_lf']) is not str or b['predecessor_lf'].encode()!=before
                or digest(before)!=b['before_sha256'] or old['files'].get(name,{}).get('sha256')!=b['before_sha256']):
            raise ValueError('Changed recovery predecessor')
    return value['files']


@lru_cache(maxsize=16)
def _recovery_predecessor(name):
    if name not in RECOVERY_MEMBERS:raise ValueError('Unapproved recovery predecessor')
    entry=git('ls-tree','-z',RECOVERY_BASE,'--',name)
    if not entry:return None
    if not entry.startswith(b'100644 blob '):raise ValueError('Recovery predecessor is not regular')
    return git('show',RECOVERY_BASE+':'+name).replace(b'\r\n',b'\n')


@lru_cache(maxsize=32)
def _recovery_ancestry(head):
    try:git('merge-base','--is-ancestor',RECOVERY_BASE,head)
    except subprocess.CalledProcessError:raise ValueError('Cannot verify recovery ancestry') from None


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
    recovery = recovery_bindings(root)
    historical = json.loads(regular(ROOT, RECEIPT).read_bytes())['files']
    for name, binding in value['files'].items():
        if (set(binding) != {'operation','before_sha256','sha256','text_lf','predecessor_lf'}
                or binding['text_lf'] is not True or digest(recovery[name]['predecessor_lf'].encode() if name in recovery and recovery[name]['operation']=='M' else regular(ROOT,name).read_bytes()) != binding['sha256']):
            raise ValueError('Changed physical native Git successor: '+name)
        if name in historical:
            if (binding['operation'] != 'M' or type(binding['predecessor_lf']) is not str
                    or digest(binding['predecessor_lf'].encode()) != binding['before_sha256']
                    or binding['before_sha256'] != historical[name]['sha256']):
                raise ValueError('Changed native Git qualified predecessor')
        elif binding['operation'] != 'A' or binding['before_sha256'] is not None or binding['predecessor_lf'] is not None or predecessor(name) is not None:
            raise ValueError('Expanded native Git addition scope')
    return {name:dict(b,sha256=recovery[name]['sha256']) if name in recovery else b for name,b in value['files'].items()}


def digest(raw):
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


@lru_cache(maxsize=32)
def ancestry(head):
    try:
        git('merge-base', '--is-ancestor', BASE, head)
    except subprocess.CalledProcessError:
        raise ValueError('Cannot verify publication commit ancestry') from None


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
    if (digest(regular(ROOT, CI_TEST_LOCK).read_bytes()) != CI_TEST_LOCK_SHA
            or digest(predecessor(CI_TEST_LOCK)) != CI_TEST_LOCK_BEFORE_SHA):
        raise ValueError('Changed exact Windows test dependency successor')
    successors = git_bindings(root)
    effective = {}
    for name, binding in value['files'].items():
        before = predecessor(name)
        physical = timeout_bytes(root, name, regular(ROOT, name).read_bytes())
        historical_current = successors[name]['predecessor_lf'].encode() if name in successors else physical
        if (set(binding) != {'operation', 'before_sha256', 'sha256', 'text_lf'} or binding['text_lf'] is not True
                or binding['operation'] != ('A' if before is None else 'M')
                or binding['before_sha256'] != (None if before is None else digest(before))
                or digest(historical_current) != binding['sha256']):
            raise ValueError('Changed physical publication successor: ' + name)
        effective[name] = dict(binding, sha256=timeout_hash(name, successors[name]['sha256'] if name in successors else binding['sha256']))
    return effective


def historical_bytes(root, name, current):
    current = timeout_bytes(root, name, current)
    if name == CI_TEST_LOCK:
        verify(root)
        return predecessor(name) if digest(current) == CI_TEST_LOCK_SHA else current
    if name not in MEMBERS:
        return current
    bindings = verify(root)
    if name in bindings and bindings[name]['before_sha256'] is not None and digest(current) == digest(timeout_bytes(root, name, regular(root, name).read_bytes())):
        return predecessor(name)
    return current


def selected_hash(name, expected):
    if name not in MEMBERS:
        return timeout_hash(name, expected)
    binding = verify().get(name)
    return timeout_hash(name, binding['sha256'] if binding and binding['before_sha256'] is not None and expected == binding['before_sha256'] else expected)


def scope_members():
    return MEMBERS | ANCHORS | GIT_MEMBERS | {GIT_RECEIPT, CI_TEST_LOCK, RECOVERY_RECEIPT} | RECOVERY_MEMBERS
