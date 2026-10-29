"""Exact README publication successors; preserve every historical inventory."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import stat
import subprocess

from ci.people_storage_maintenance import regular

ROOT = Path(__file__).resolve().parents[1]
BASE = 'deb9a3a2f609600a395c5be8b268805de5a5efa3'
MANIFEST = ROOT / 'ci/people-readme-maintenance-v1.json'
PIN = '60f0359dbd199310bf6d646cac0bfb6af25f1b6b9c5d88ace4fac5d4f0bc42ac'
ANCHORS = frozenset({'ci/people_readme_maintenance.py', 'ci/people-readme-maintenance-v1.json'})
MEMBERS = frozenset({
    '.github/workflows/people-storage-validation.yml',
    'ci/dependency_maintenance.py',
    'ci/dependency_tests/test_people_readme_maintenance.py',
    'ci/dependency_tests/test_people_retention_maintenance.py',
    'ci/dependency_tests/test_people_storage_maintenance.py',
    'ci/people_colorize_maintenance.py',
    'ci/people_readme/README.md',
    'ci/people_readme/targets.json',
    'ci/people_readme/workflows/People-Images-bw.yml',
    'ci/people_readme/workflows/People-Images-diiivoy.yml',
    'ci/people_readme/workflows/People-Images-diiivoycolor.yml',
    'ci/people_readme/workflows/People-Images-rainier.yml',
    'ci/people_readme/workflows/People-Images-signature.yml',
    'ci/people_readme/workflows/People-Images-transparent.yml',
    'ci/people_readme/workflows/People-Images.yml',
    'ci/people_retention_maintenance.py',
    'ci/people_storage_maintenance.py',
    'create_people_posters/CLONE_FREE.md',
    'create_people_posters/README.md',
    'create_people_posters/jost_migration.py',
    'create_people_posters/people_cleanup_report.py',
    'create_people_posters/people_publication_state.py',
    'create_people_posters/people_readme_publication.py',
    'create_people_posters/people_verified_cleanup.py',
    'create_people_posters/publish_people_github.py',
    'create_people_posters/sandbox_people_github.py',
    'create_people_posters/tests/test_jost_migration.py',
    'create_people_posters/tests/test_people_github.py',
    'create_people_posters/tests/test_people_readme_publication.py',
    'create_people_posters/tests/test_people_readme_workflows.py',
    'create_people_posters/tests/test_people_workspaces.py',
})


@lru_cache(maxsize=256)
def sha(raw):
    # Only immutable byte strings are cached. Current files are read afresh.
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        allow_nan=False, separators=(',', ':')).encode()).hexdigest()


@lru_cache(maxsize=8)
def _decoded_manifest(raw, expected_pin):
    # Cache immutable bytes only; every call still reads and checks the actual
    # manifest path. Replaced bytes, including equal-length edits, miss this cache.
    value = json.loads(raw)
    if (fingerprint(value) != expected_pin or value['version'] != 1 or set(value['members']) != MEMBERS
            or value['baseline_commit'] != BASE or value['publication_authorized'] is not False):
        raise ValueError('Changed exact README publication transition')
    return value


def manifest():
    return _decoded_manifest(regular(ROOT, MANIFEST.relative_to(ROOT).as_posix()).read_bytes(), PIN)


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


@lru_cache(maxsize=32)
def _file_plan(root, names):
    # Cache path arithmetic only, without any filesystem reads or metadata.
    root = Path(root)
    paths = tuple((name, root / name) for name in names)
    directories = set()
    for name, path in paths:
        if root not in path.parents or '..' in path.relative_to(root).parts:
            raise ValueError('README publication path escaped root')
        for part in path.parents:
            directories.add(part)
            if part == root:
                break
    return paths, tuple(directories)


def _regular_files(root, names):
    """Check every file and shared directory afresh on each call."""
    paths, directories = _file_plan(str(root.absolute()), tuple(sorted(names)))
    for name, path in paths:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('README publication rejects links or reparse points: ' + name)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('README publication requires a regular file: ' + name)
    for part in directories:
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('README publication rejects links or reparse points: ' + str(part))
    return dict(paths)


def verify_checkout(root=None):
    root = Path(root or ROOT)
    value = manifest()
    from ci.people_colorize_maintenance import _head
    _ancestry(str(root), _head(root))
    paths = _regular_files(root, set(value['members']) | ANCHORS)
    for name, binding in value['members'].items():
        from ci.dependabot_maintenance import historical_bytes as dependency_history
        current = dependency_history(root, name, paths[name].read_bytes())
        if sha(current) != binding['sha256']:
            raise ValueError('Unreviewed README publication successor: ' + name)
        if binding['before_sha256'] is not None and sha(_old(name)) != binding['before_sha256']:
            raise ValueError('Changed README publication predecessor: ' + name)
    return value


def selected_hash(name, expected):
    from ci.dependabot_maintenance import selected_hash as dependency_hash
    expected = dependency_hash(name, expected)
    if name not in MEMBERS:
        return expected
    binding = manifest()['members'].get(name)
    if binding is None or binding['before_sha256'] is None or expected != binding['before_sha256']:
        return expected
    verify_checkout()
    return dependency_hash(name, binding['sha256'])


def historical_bytes(root, name, current):
    from ci.dependabot_maintenance import historical_bytes as dependency_history
    current = dependency_history(root, name, current)
    if name not in MEMBERS:
        return current
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
    from ci.dependabot_maintenance import scope_members as dependency_scope
    return set(manifest()['members']) | ANCHORS | dependency_scope()


def test_ids():
    return list(manifest()['pytest_ids'])


def verify_scope(root, baseline, names):
    verify_checkout(root)
    from ci.dependabot_maintenance import scope_members as dependency_scope, verify_scope as dependency_verify
    dependency_names = names & dependency_scope()
    if dependency_names:
        dependency_verify(root, baseline, dependency_names)
    names = names - dependency_names
    if not names:
        return
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
