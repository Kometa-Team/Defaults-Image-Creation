"""Exact additive bulk delivery scope; no production/publication authority.

Existing COLLECTION and M5 receipts and historical test inventories remain intact.
The existing M5 trust anchor pins this adapter's source independently of its receipt.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess

from ci.people_storage_maintenance import regular

ROOT = Path(__file__).resolve().parents[1]
BASE = 'fe59024c53f1bb50cd55d1bf81a3cf8a73339512'
M7_BASE = '68179d1c568449375ca72b23239b57770dfc229e'
MANIFEST = 'ci/people-bulk-maintenance-v1.json'
PIN = 'f811f9359f799e8e7fbea4f9ea948f2a614edd54c6db908cd72d2aa005380804'
MEMBERS = frozenset((
    '.dockerignore', '.gitattributes', '.gitignore',
    '.github/workflows/people-bulk-validation.yml',
    'ci/bulk_tests/test_people_bulk_maintenance.py',
    'create_people_posters/bulk/.env.example',
    'create_people_posters/bulk/Dockerfile',
    'create_people_posters/bulk/README.md',
    'create_people_posters/bulk/VALIDATION.md',
    'create_people_posters/bulk/ZFS.md',
    'create_people_posters/bulk/canary-selection.json',
    'create_people_posters/bulk/compose.yaml',
    'create_people_posters/bulk/prepare_canary_source.py',
    'create_people_posters/bulk/requirements.lock',
    'create_people_posters/bulk/runtime-release.json',
    'create_people_posters/bulk/source_snapshot.sh',
    'create_people_posters/bulk/test-requirements.lock',
    'create_people_posters/bulk/tests/test_bulk_portable.py',
    'create_people_posters/bulk/tests/test_bulk_regenerate.py',
    'create_people_posters/bulk_benchmark.py',
    'create_people_posters/bulk_git_sync.py',
    'create_people_posters/bulk_reconcile.py',
    'create_people_posters/bulk_regenerate.py',
    'create_people_posters/bulk_regeneration_plan.py',
    'create_people_posters/bulk_regeneration_report.py',
    'create_people_posters/bulk_regeneration_state.py',
    'create_people_posters/bulk_runtime.py',
    'create_people_posters/bulk_source.py',
    'create_people_posters/bulk_validate.py',
    'create_people_posters/bulk_zfs_source.py',
    'create_people_posters/requirements-bulk-regenerate.txt',
))
ANCHORS = frozenset((MANIFEST, 'ci/people_bulk_maintenance.py'))
FROZEN = frozenset((
    'ci/original-test-ids.json', 'ci/people-security-test-ids.json',
    'ci/people-collection-maintenance-v1.json', 'ci/phase5-m5-maintenance-v1.json',
    'create_people_posters/README.md',
    'create_people_posters/create_people_poster.py', 'create_people_posters/poster_fonts.py',
))


def sha(raw):
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def git(*args):
    result = subprocess.run(['git', *args], cwd=ROOT, capture_output=True)
    if result.returncode:
        raise ValueError('Cannot verify bulk delivery Git provenance')
    return result.stdout


@lru_cache(maxsize=64)
def predecessor(name):
    entry = git('ls-tree', '-z', BASE, '--', name)
    return git('show', BASE+':'+name) if entry else None


@lru_cache(maxsize=32)
def ancestry(head):
    git('merge-base', '--is-ancestor', BASE, head)


def verify(root=ROOT):
    if Path(root).resolve() != ROOT.resolve():
        raise ValueError('Foreign bulk policy checkout')
    value = json.loads(regular(ROOT, MANIFEST).read_bytes())
    if (fingerprint(value) != PIN or set(value) != {'version', 'baseline_commit', 'files', 'frozen_files', 'publication_authorized'}
            or value['version'] != 1 or value['baseline_commit'] != BASE
            or set(value['files']) != MEMBERS or set(value['frozen_files']) != FROZEN
            or value['publication_authorized'] is not False):
        raise ValueError('Changed exact bulk delivery receipt')
    from ci.people_collection_maintenance import _head
    ancestry(_head(ROOT))
    from ci.phase5_m5_maintenance import unicode_adapter
    successor = unicode_adapter()
    successor.verify(root)
    for name, binding in value['files'].items():
        if set(binding) != {'sha256', 'before_sha256'}:
            raise ValueError('Changed bulk member binding')
        old = predecessor(name)
        if binding['before_sha256'] != (sha(old) if old is not None else None):
            raise ValueError('Changed bulk predecessor: '+name)
        current = successor.historical_bytes(root, name, regular(ROOT, name).read_bytes())
        if sha(current) != binding['sha256']:
            raise ValueError('Changed physical bulk member: '+name)
    for name, expected in value['frozen_files'].items():
        current = successor.historical_bytes(root, name, regular(ROOT, name).read_bytes())
        if sha(predecessor(name)) != expected or sha(current) != expected:
            raise ValueError('Changed frozen bulk predecessor: '+name)
    return value


def scope_members():
    # Enumeration grants no approval; physical bytes are checked on acceptance.
    return MEMBERS | ANCHORS


def verify_scope(root, baseline, names):
    if baseline != M7_BASE or not names <= scope_members():
        raise ValueError('Unapproved bulk scope or baseline')
    verify(root)
    if not names:
        return
    rows = git('diff', '--raw', '--no-abbrev', '--no-renames', '-z', baseline, 'HEAD', '--', *sorted(names)).split(b'\0')
    if rows[-1] != b'' or len(rows) != 2*len(names)+1:
        raise ValueError('Incomplete bulk scope diff')
    seen = set()
    for offset in range(0, len(rows)-1, 2):
        fields, name = rows[offset].split(), rows[offset+1].decode('utf8')
        if (name not in names or name in seen or len(fields) != 5
                or fields[:2] not in ([b':000000', b'100644'], [b':100644', b'100644'])
                or fields[4] != (b'A' if fields[0] == b':000000' else b'M')):
            raise ValueError('Bulk delivery requires regular-file additions/modifications')
        regular(ROOT, name)
        seen.add(name)
