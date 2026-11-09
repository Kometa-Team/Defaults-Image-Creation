"""Exact current COLLECTION provenance; historical CI records remain frozen."""
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from ci.people_storage_maintenance import regular

ROOT = Path(__file__).resolve().parents[1]
BASE = 'ae397cb8d252a62d3bc56966a6b0710a0f09a47f'
MANIFEST = 'ci/people-collection-maintenance-v1.json'
PIN = '87d074cc393c8c96f91ec11e50cd7f0e54541c769ea831953276c49909ac2b34'
MEMBERS = frozenset(('ci/dependency_tests/test_people_storage_maintenance.py', 'ci/dependency_tests/test_phase5_m5_maintenance.py', 'ci/people_job_retention_maintenance.py', 'ci/people_security.py', 'ci/phase4.py', 'ci/phase4_transactions.py', 'create_people_posters/create_people_poster.py', 'create_people_posters/tests/test_collection_poster.py'))
M5_PATHS = frozenset(('ci/people_job_retention_maintenance.py', 'ci/dependency_tests/test_phase5_m5_maintenance.py'))
SOURCE_PATHS = MEMBERS - M5_PATHS
RENDERER = 'create_people_posters/create_people_poster.py'
TEST_MODULE = 'create_people_posters/tests/test_collection_poster.py'
M7_BASE = '68179d1c568449375ca72b23239b57770dfc229e'
DELIVERY = frozenset((
    'create_people_posters/COLLECTION_RENDERING.md',
    'create_people_posters/POSTER_RENDERER.md',
    'create_people_posters/assets/people/@zbase-People-Clear2-no-text.png',
    'create_people_posters/assets/people/@zbase-People-Clear3-no-text.png',
    'create_people_posters/assets/people/@zbase-Signature-no-text.png',
    'create_people_posters/compare_collection.py',
    'create_people_posters/fonts/Montserrat-Light.ttf',
    'create_people_posters/fonts/README.md',
))


@lru_cache(maxsize=64)
def digest(raw, text_lf=True):
    # Pure immutable-byte cache; current paths/bytes are always read afresh.
    return hashlib.sha256(raw.replace(b'\r\n', b'\n') if text_lf else raw).hexdigest()


def sha(raw):
    return digest(raw)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        allow_nan=False, separators=(',', ':')).encode()).hexdigest()


@lru_cache(maxsize=64)
def _blob(commit, name):
    return _git(ROOT, 'show', commit + ':' + name)


def _committed(commit, name):
    return _blob(commit, name).replace(b'\r\n', b'\n')


def _git(root, *args):
    with subprocess.Popen(['git', *args], cwd=root, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE) as process:
        output, _ = process.communicate()
        if process.returncode:
            raise ValueError('Cannot verify COLLECTION Git provenance')
        return output


def _head(root):
    # Independent fresh resolution retains the original M5 HEAD-call contract.
    # Read supported loose Git refs afresh, including worktrees. Packed refs,
    # unusual ref names/storage and discovery overrides use Git itself.
    # No HEAD, ref contents, filesystem facts or acceptance result is cached.
    if not any(n in os.environ for n in ('GIT_DIR', 'GIT_COMMON_DIR', 'GIT_WORK_TREE', 'GIT_NAMESPACE')):
        try:
            marker = Path(root) / '.git'
            gitdir = marker
            if marker.is_file():
                descriptor = marker.read_text(encoding='utf8').strip()
                if not descriptor.startswith('gitdir: '):
                    raise ValueError('Invalid Git directory descriptor')
                gitdir = Path(descriptor[len('gitdir: '):])
                if not gitdir.is_absolute():
                    gitdir = Path(root) / gitdir
            head = (gitdir / 'HEAD').read_text(encoding='ascii').strip()
            if re.fullmatch(r'[0-9a-f]{40}', head):
                return head
            prefix = 'ref: refs/heads/'
            parts = head[len(prefix):].split('/') if head.startswith(prefix) else []
            if parts and all(re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*', part)
                    and '..' not in part and not part.endswith(('.', '.lock')) for part in parts):
                try:
                    common = (gitdir / 'commondir').read_text(encoding='utf8').strip()
                except FileNotFoundError:
                    common_dir = gitdir
                else:
                    common_dir = gitdir / common
                resolved = (common_dir / 'refs' / 'heads' / Path(*parts)).read_text(encoding='ascii').strip()
                if re.fullmatch(r'[0-9a-f]{40}', resolved):
                    return resolved
        except (OSError, UnicodeError):
            pass
    head = _git(root, 'rev-parse', 'HEAD').decode('ascii').strip()
    if not re.fullmatch(r'[0-9a-f]{40}', head):
        raise ValueError('Invalid COLLECTION HEAD')
    return head


@lru_cache(maxsize=32)
def _ancestry(root, head):
    # Only immutable commit ancestry is cached, never HEAD or acceptance.
    _git(root, 'merge-base', '--is-ancestor', BASE, head)


@lru_cache(maxsize=64)
def _entry(commit, name):
    return _git(ROOT, 'ls-tree', '-z', commit, '--', name)


def _delivery_history(name, binding):
    expected = ('100644 blob ' + binding['approved_blob'] + '\t' + name + '\0').encode()
    if (_entry(binding['approved_commit'], name) != expected
            or digest(_blob(binding['approved_commit'], name), binding['text_lf']) != binding['sha256']):
        raise ValueError('Changed approved COLLECTION delivery blob: ' + name)
    old = _entry(binding['before_commit'], name)
    if binding['before_sha256'] is None:
        if old:
            raise ValueError('COLLECTION delivery addition exists in predecessor: ' + name)
    elif (not old.startswith(b'100644 blob ')
            or digest(_blob(binding['before_commit'], name), binding['text_lf']) != binding['before_sha256']):
        raise ValueError('Changed historical COLLECTION delivery: ' + name)


def verify(root=ROOT):
    root = Path(root)
    if root.resolve() != ROOT.resolve():
        raise ValueError('Foreign COLLECTION policy checkout')
    value = json.loads(regular(root, MANIFEST).read_bytes())
    if (fingerprint(value) != PIN or value['version'] != 1
            or value['baseline_commit'] != BASE or set(value['files']) != MEMBERS
            or set(value['delivery_files']) != DELIVERY
            or value['publication_authorized'] is not False
            or len(value['pytest_ids']) != 32 or len(set(value['pytest_ids'])) != 32
            or any(not node.startswith(TEST_MODULE + '::') for node in value['pytest_ids'])):
        raise ValueError('Changed exact COLLECTION provenance')
    _ancestry(str(root), _head(root))
    from ci.people_readme_maintenance import _regular_files
    paths = _regular_files(root, MEMBERS | DELIVERY | set(value['frozen_files']))
    from ci.phase5_m5_maintenance import unicode_adapter
    successor = unicode_adapter()
    unicode_bindings,owned=successor._verify_owned(root)
    for name, binding in value['files'].items():
        current = successor._historical_owned(root,name,regular(root,name).read_bytes(),unicode_bindings,owned)
        if sha(current) != binding['sha256']:
            raise ValueError('Changed physical COLLECTION successor: ' + name)
        if sha(_committed(binding['before_commit'], name)) != binding['before_sha256']:
            raise ValueError('Changed COLLECTION predecessor: ' + name)
        if 'approved_commit' in binding and sha(_committed(binding['approved_commit'], name)) != binding['sha256']:
            raise ValueError('COLLECTION successor differs from approved committed bytes: ' + name)
    for name, binding in value['delivery_files'].items():
        if digest(paths[name].read_bytes(), binding['text_lf']) != binding['sha256']:
            raise ValueError('Changed physical COLLECTION delivery: ' + name)
        _delivery_history(name, binding)
    for name, expected in value['frozen_files'].items():
        if sha(paths[name].read_bytes()) != expected:
            raise ValueError('Changed frozen COLLECTION predecessor evidence: ' + name)
    successor._close_owned(root,owned)
    return value


def selected_hash(name, expected):
    value = verify()
    binding = value['files'].get(name)
    if binding is None or expected != binding['before_sha256']:
        return expected
    return binding['sha256']


def historical_bytes(root, name, current):
    value = verify(root)
    from ci.phase5_m5_maintenance import unicode_adapter
    current = unicode_adapter().historical_bytes(root, name, current)
    binding = value['files'].get(name)
    if binding is None:
        return current
    if sha(current) not in {binding['before_sha256'], binding['sha256']}:
        raise ValueError('Forged COLLECTION historical projection: ' + name)
    return _committed(binding['before_commit'], name)


def m5_view(root, name, current):
    # The original M5 checker retains responsibility for all other inputs and
    # its already-supported earlier projections. Physical bytes are checked
    # against the new receipt before adapting this exact known successor.
    value = verify(root)
    if name not in M5_PATHS:
        return current
    binding = value['files'][name]
    if sha(current) == binding['sha256']:
        return _committed(binding['before_commit'], name)
    return current


def m5_bindings(root):
    # One fresh full-cohort proof per M5 entry point. These immutable bindings
    # are local to that call; no path, HEAD or acceptance result is cached.
    value = verify(root)
    return {name: (value['files'][name]['sha256'],
                  _committed(value['files'][name]['before_commit'], name))
            for name in M5_PATHS}


def test_ids():
    return list(verify()['pytest_ids'])


def scope_members():
    # Enumeration grants no acceptance: verify_scope checks current evidence.
    return MEMBERS | DELIVERY | {MANIFEST, 'ci/people_collection_maintenance.py'}


def verify_scope(root, baseline, names):
    value = verify(root)
    if baseline != M7_BASE or not names <= scope_members():
        raise ValueError('Unapproved COLLECTION scope or baseline')
    if not names:
        return
    rows = _git(root, 'diff', '--raw', '--no-abbrev', '--no-renames', '-z',
                baseline, 'HEAD', '--', *sorted(names)).split(b'\0')
    if rows[-1] != b'' or len(rows) != 2 * len(names) + 1:
        raise ValueError('Incomplete COLLECTION scope diff')
    seen = set()
    for offset in range(0, len(rows) - 1, 2):
        fields, name = rows[offset].split(), rows[offset + 1].decode('utf8')
        if (name not in names or name in seen or len(fields) != 5
                or fields[:2] not in ([b':000000', b'100644'], [b':100644', b'100644'])
                or fields[4] != (b'A' if fields[0] == b':000000' else b'M')):
            raise ValueError('COLLECTION requires regular-file additions/modifications')
        if name in DELIVERY:
            binding = value['delivery_files'][name]
            if fields[3].decode('ascii') != binding['approved_blob']:
                raise ValueError('Unapproved committed COLLECTION delivery successor: ' + name)
        regular(root, name)
        seen.add(name)
