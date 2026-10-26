"""Reviewed PR46 source cohort; immutable history, fail-closed ancestry transition.

This verifier is a new reviewed CI trust anchor, not a production/publication
allowance. Old manifests and their digests remain authoritative predecessors.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT/'ci/people-storage-maintenance-v1.json'
PIN = '4ac355d664ddd022e8c7658d9e4a1ffbe6d38ec73fdfbb921068f4a101c59b5f'
SOURCE = 'create_people_posters/recover_edge_chops.py'
COHORT = frozenset((
    '.github/workflows/people-storage-validation.yml',
    'create_people_posters/docs/PEOPLE_STORAGE_AUDIT.json',
    'create_people_posters/docs/PEOPLE_STORAGE_LIFECYCLE.md',
    'create_people_posters/people_cleanup_report.py',
    'create_people_posters/people_recovery_storage.py', SOURCE,
    'create_people_posters/tests/test_background_orchestrator.py',
    'create_people_posters/tests/test_people_recovery_storage.py',
))
INFRASTRUCTURE = frozenset(('ci/dependency_maintenance.py',
    'ci/people_security_maintenance.py', 'ci/people_security.py', 'ci/phase4_m7.py'))
ADDITIONS = frozenset(('ci/dependency_tests/test_people_storage_maintenance.py',
    'ci/PEOPLE_STORAGE_PROVENANCE.md'))
TRUST_ANCHORS = frozenset(('ci/people_storage_maintenance.py',
    'ci/people-storage-maintenance-v1.json'))


def sha(raw):
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def manifest():
    # Never cache mutable paths/mtimes or accept a caller-provided approval flag.
    regular(ROOT, MANIFEST.relative_to(ROOT).as_posix())
    value = json.loads(MANIFEST.read_bytes())
    if (fingerprint(value) != PIN or set(value['cohort']) != COHORT
            or set(value['infrastructure']) != INFRASTRUCTURE
            or set(value['additions']) != ADDITIONS
            or value['production_members'] != [SOURCE]
            or value['publication_authorized'] is not False):
        raise ValueError('Changed exact People storage transition')
    return value


def regular(root, name):
    root = Path(root).absolute()
    path = root/name
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Storage transition rejects links or reparse points: '+name)
        if part == path and not stat.S_ISREG(info.st_mode):
            raise ValueError('Storage transition requires a regular file: '+name)
        if part == root:
            return path
    raise ValueError('Storage transition path escaped root')


@lru_cache(maxsize=256)
def git_bytes(root, commit, name):
    return subprocess.run(['git', 'show', commit+':'+name], cwd=root, check=True,
                          stdout=subprocess.PIPE).stdout.replace(b'\r\n', b'\n')


@lru_cache(maxsize=64)
def _integrated(root, source_commit, head):
    # An absent object, shallow history or Git failure must not select old mode.
    subprocess.check_call(['git', 'cat-file', '-e', source_commit+'^{commit}'], cwd=root,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    result = subprocess.run(['git', 'merge-base', '--is-ancestor', source_commit, head], cwd=root)
    if result.returncode not in (0, 1):
        raise ValueError('Cannot establish reviewed storage ancestry')
    return result.returncode == 0


def integrated(root, value):
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, check=True,
                          stdout=subprocess.PIPE, text=True).stdout.strip()
    return _integrated(str(root), value['source_commit'], head)


def verify_cohort(root, value):
    active = integrated(root, value)
    field = 'sha256' if active else 'before_sha256'
    for name, binding in value['cohort'].items():
        expected = binding[field]
        path = Path(root)/name
        if expected is None:
            for parent in path.parents:
                try:
                    info = parent.lstat()
                except FileNotFoundError:
                    continue
                if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                    raise ValueError('Storage transition rejects links or reparse points: '+name)
                if parent == Path(root):
                    break
            # lexists-equivalent: dangling links and directories are not absent.
            try:
                path.lstat()
            except FileNotFoundError:
                continue
            raise ValueError('Storage successor exists before reviewed integration: '+name)
        if sha(regular(root, name).read_bytes()) != expected:
            raise ValueError('Changed or mixed People storage cohort: '+name)
    return active


def verify(root=ROOT):
    value = manifest()
    for name, binding in value['infrastructure'].items():
        if (sha(git_bytes(str(root), value['baseline_commit'], name)) != binding['before_sha256']
                or sha(regular(root, name).read_bytes()) != binding['sha256']):
            raise ValueError('Changed exact storage CI infrastructure: '+name)
    for name, expected in value['additions'].items():
        if sha(regular(root, name).read_bytes()) != expected:
            raise ValueError('Changed exact storage maintenance addition: '+name)
    for name in TRUST_ANCHORS:
        regular(root, name)
    return verify_cohort(root, value)


def selected_hash(name, expected):
    # Preserve synthetic/unknown predecessors and every unlisted source pin.
    if name not in COHORT | INFRASTRUCTURE:
        return expected
    value = manifest()
    if name in INFRASTRUCTURE:
        binding = value['infrastructure'][name]
        return binding['sha256'] if expected == binding['before_sha256'] else expected
    binding = value['cohort'][name]
    if binding['before_sha256'] is None or expected != binding['before_sha256']:
        return expected
    return binding['sha256'] if verify_cohort(ROOT, value) else expected


def extra_ids(root=ROOT):
    value = manifest()
    return list(value['storage_test_ids']) if verify_cohort(root, value) else []


def historical_bytes(root, name, current):
    """Project ONLY verified CI successors onto their exact frozen predecessors."""
    if name not in INFRASTRUCTURE:
        return current
    value = manifest()
    binding = value['infrastructure'].get(name)
    if binding is None:
        return current
    if sha(current) != binding['sha256']:
        raise ValueError('Changed storage infrastructure historical view: '+name)
    old = git_bytes(str(root), value['baseline_commit'], name)
    if sha(old) != binding['before_sha256']:
        raise ValueError('Changed storage infrastructure predecessor: '+name)
    return old


def scope_members():
    return COHORT | INFRASTRUCTURE | ADDITIONS | TRUST_ANCHORS


def verify_scope(root, baseline, names):
    verify(root)
    if not names <= scope_members():
        raise ValueError('Unapproved storage maintenance path')
    rows = subprocess.check_output(['git', 'diff', '--raw', '--no-abbrev', '--no-renames',
        '-z', baseline, 'HEAD', '--', *sorted(names)], cwd=root).split(b'\0')
    if rows[-1] != b'' or len(rows) != 2*len(names)+1:
        raise ValueError('Incomplete storage maintenance diff')
    modified = (INFRASTRUCTURE-{'ci/phase4_m7.py'}) | {
        SOURCE, 'create_people_posters/tests/test_background_orchestrator.py'}
    seen = set()
    for offset in range(0, len(rows)-1, 2):
        fields, name = rows[offset].split(), rows[offset+1].decode('utf8')
        old_mode, status = (b':100644', b'M') if name in modified else (b':000000', b'A')
        if (name not in names or name in seen or len(fields) != 5
                or fields[:2] != [old_mode, b'100644'] or fields[4] != status):
            raise ValueError('Storage maintenance requires exact regular-file additions/modifications')
        seen.add(name)
        regular(root, name)
