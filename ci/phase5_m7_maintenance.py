"""Exact M7 CI successor, independently sealed from all prior receipts."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache, wraps
import hashlib
import json
from pathlib import Path
import subprocess
from threading import get_ident

from ci.people_storage_maintenance import regular

ROOT = Path(__file__).resolve().parents[1]
BASE = '1a367cda9c8e2c07cdcab2f3d4684b0cf03130e7'
OWNER = 'ci/phase5_m7_maintenance.py'
RECEIPT = 'ci/phase5-m7-maintenance-v1.json'
PIN = '01ba3a910ff438f9add49f1d490e1aaa0165b59bce716d3a0ee0d81bc05d0aae'
MODIFIED = frozenset(('ci/phase4_m7.py', 'ci/phase4.py', 'ci/people_storage_maintenance.py',
                      'ci/phase5_m6_maintenance.py', 'create_defaults/lifecycle/ROADMAP.md',
                      'ci/dependency_tests/test_phase5_m6_maintenance.py',
                      'ci/publication_tests/test_validation_timeouts.py',
                      'ci/people_unicode_maintenance.py', 'ci/phase5_m5_maintenance.py'))
ADDED = frozenset(('ci/phase5_m7_acceptance.py',
                   'ci/phase5_m7_provenance.py',
                   'ci/dependency_tests/test_phase5_m7_admission.py',
                   'ci/dependency_tests/test_phase5_m7_followup.py'))
ROADMAP_VIEWS = ('359d467f601787c4fdf6e369e0971f6fe0a7c49df65114f7aca8c82de0514f82', '4a1fa20153c3926a2ae06cf544629b7208ceb94fe80af9fa7106fa032180286d', '79a722ebfd77be147b9375673ea77dbb44e6ef62ac325b6299bd77ec24a690e9', '8d15de091e0ff4a75f131b13ff7bce0063eadda8525e895497d190746c32a8fa', 'c830b33101d202e6118c84c7d63ccf40b0a7639eefcaa6687d73e2c9469d87fc', 'f776dea7e1d719439df2fb1f6c8ddea30297eda6bf63f30e9f93cea7f502ca96')
STORAGE_VIEWS = ('8e2420d6d6868781acea9a9a0806b2bf904ea4027095a1fd61db3885fe8394f7', 'af3e037f8b4af95d5c8d096c501b8b8f2b4a9023a7b4a1519a6fd4b46fbd4e3c')
TEST_VIEWS = ('8816f0b5d3d28951ae95af39e10d314a12a320f91b719a3b3d43dfa2a3db4bfd', 'd8f7c0b16e9daceb91f9c32af0937e797ede60d24f1e50cb9d4a6e99bb3af2ee', 'fbde4457701713547eff0ce7d5b76596f6dcfbea5ab0cdddad516cf17553f254')
PHASE4_BEFORE = 'dae564e48195a0fe9d124ab5c12ac19e4bc61062dea823f8dbdd55b6f2506dce'
PHASE4_VIEWS = ('1ce5155558ffcfb4c6c9f28d0813658df52d4170a6af44022425460951ef7a1d',
                '16e7c89d628f42d719a726b805b578483a76bc5f6183a6dbeed06e0609f24677')
_ACTIVE = ContextVar('m7_verification_owner', default=None)


@lru_cache(maxsize=128)
def sha(raw):
    # Pure byte computation only. Every physical input is still reread.
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()


def fingerprint(value):
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=True,
                          allow_nan=False, separators=(',', ':')).encode())


def git(root, *args):
    p = subprocess.run(['git', *args], cwd=root, capture_output=True)
    if p.returncode:
        raise ValueError('Cannot authenticate M7 history')
    return p.stdout


@lru_cache(maxsize=64)
def predecessor(name):
    # Fixed immutable Git objects only; never cache mutable file/receipt/HEAD proof.
    return git(ROOT, 'show', BASE+':'+name)


@lru_cache(maxsize=32)
def ancestry(head):
    git(ROOT, 'merge-base', '--is-ancestor', BASE, head)


@lru_cache(maxsize=64)
def _baseline_entry(root, base, name):
    return git(Path(root), 'ls-tree', base, '--', name)


@lru_cache(maxsize=64)
def _owner_bytes(root, head):
    return git(Path(root), 'show', head+':'+OWNER)


def scope_members():
    return MODIFIED | ADDED | {OWNER, RECEIPT}


@lru_cache(maxsize=4)
def _decode(raw, pin, base, modified, added):
    # Return immutable metadata, never a shared mutable receipt or checkout proof.
    value = json.loads(raw)
    if (fingerprint(value) != pin or set(value) != {
            'version', 'baseline_commit', 'members', 'ci_only', 'publication_authorized'}
            or value['version'] != 1 or value['baseline_commit'] != base
            or value['ci_only'] is not True or value['publication_authorized'] is not False
            or set(value['members']) != modified | added):
        raise ValueError('Changed exact M7 receipt')
    rows = []
    for name, binding in value['members'].items():
        if set(binding) != {'before_sha256', 'sha256'}:
            raise ValueError('Changed M7 binding')
        rows.append((name, binding['before_sha256'], binding['sha256']))
    return tuple(rows)


def verify_checkout(root=None, *, _witness=False):
    root = Path(root or ROOT)
    if root != ROOT and root.resolve() != ROOT.resolve():
        raise ValueError('Foreign M7 checkout')
    from ci.people_colorize_maintenance import _head
    head = _head(ROOT)
    ancestry(head)
    # Keep the independent checker: the README helper is itself an input of
    # inherited Unicode verification and cannot authenticate its own caller.
    paths = {name: regular(ROOT, name) for name in scope_members()}
    raw = paths[RECEIPT].read_bytes()
    rows = _decode(raw, PIN, BASE, MODIFIED, ADDED)
    for name, before, after in rows:
        if sha(paths[name].read_bytes()) != after:
            raise ValueError('Changed physical M7 successor: '+name)
        if name in MODIFIED:
            if sha(predecessor(name)) != before:
                raise ValueError('Changed M7 predecessor: '+name)
        elif before is not None or _baseline_entry(str(ROOT), BASE, name).strip():
            raise ValueError('M7 addition exists in predecessor')
    # The new owner is an explicit reviewed trust anchor, not a self-hash cycle.
    # Its physical source must still equal its immutable committed exact-head blob.
    owner = sha(regular(ROOT, OWNER).read_bytes())
    if owner != sha(_owner_bytes(str(ROOT), head)):
        raise ValueError('Changed uncommitted M7 owner')
    if regular(ROOT, RECEIPT).read_bytes() != raw or _head(ROOT) != head:
        raise ValueError('M7 receipt or HEAD moved during verification')
    if _witness:
        return head, raw, owner, rows
    return dict(version=1, baseline_commit=BASE, ci_only=True,
                publication_authorized=False, members={
                    name: dict(before_sha256=before, sha256=after)
                    for name, before, after in rows})


@contextmanager
def _invocation(root):
    root = Path(root or ROOT)
    if root != ROOT and root.resolve() != ROOT.resolve():
        raise ValueError('Foreign M7 checkout')
    key = str(ROOT.absolute()), get_ident()
    active = _ACTIVE.get()
    if active is not None and active[1][0] and active[2] == key:
        yield
        return
    entry = verify_checkout(root, _witness=True)
    alive = [True]
    token = _ACTIVE.set((entry, alive, key))
    try:
        yield
        # Reread the entire cohort, its modes, owner, receipt and fresh HEAD.
        # A stable proof at a different HEAD must not close this invocation.
        if verify_checkout(root, _witness=True) != entry:
            raise ValueError('Changed closing M7 owner receipt or HEAD')
    finally:
        # Copied contexts cannot keep an approval alive after its owner returns.
        alive[0] = False
        _ACTIVE.reset(token)


def owned_call(function=None, *, when=None, error_prefix=None):
    """Private invocation boundary: never reuse a proof across public calls."""
    if function is None:
        return lambda fn: owned_call(fn, when=when, error_prefix=error_prefix)
    @wraps(function)
    def invoke(*args, **kwargs):
        if when is not None and not when(*args, **kwargs):
            return function(*args, **kwargs)
        root = kwargs.get('root', args[0] if args else None)
        try:
            with _invocation(root):
                return function(*args, **kwargs)
        except ValueError as error:
            if error_prefix is None or str(error).startswith(error_prefix):
                raise
            raise ValueError(error_prefix+': '+str(error)) from error
    return invoke


def _owned_members(root):
    """Copy authenticated metadata for an existing, still-live private owner."""
    if Path(root) != ROOT and Path(root).resolve() != ROOT.resolve():
        raise ValueError('Foreign M7 owner')
    active = _ACTIVE.get()
    if (active is None or not active[1][0]
            or active[2] != (str(ROOT.absolute()), get_ident())):
        raise ValueError('No live M7 verification owner')
    return {name: dict(before_sha256=before, sha256=after)
            for name, before, after in active[0][3]}


def _read_owned_predecessor(root, name):
    """Read and project one physical successor inside a live private owner."""
    if name not in MODIFIED:
        raise ValueError('No M7 predecessor for: '+name)
    binding = _owned_members(root)[name]
    current = regular(ROOT, name).read_bytes()
    if sha(current) != binding['sha256']:
        raise ValueError('Changed physical M7 successor: '+name)
    before = predecessor(name)
    if sha(before) != binding['before_sha256']:
        raise ValueError('Changed M7 predecessor: '+name)
    return before


def historical_bytes(root, name, current, *, opaque=False):
    if name not in MODIFIED:
        return current
    active = _ACTIVE.get()
    if active is not None and active[1][0] and active[2] == (str(ROOT.absolute()), get_ident()):
        if Path(root) != ROOT and Path(root).resolve() != ROOT.resolve():
            raise ValueError('Foreign M7 historical projection')
        _, before, after = next(row for row in active[0][3] if row[0] == name)
        # Entry/closing proofs cover every member. Each actual view additionally
        # rereads its own leaf and ancestors at the point of use, independently
        # of caller bytes. Metadata lives only in this synchronous invocation.
        if sha(regular(ROOT, name).read_bytes()) != after:
            raise ValueError('Changed physical M7 successor: '+name)
        binding = dict(before_sha256=before, sha256=after)
    else:
        binding = verify_checkout(root)['members'][name]
    digest = sha(current)
    if digest == binding['sha256']:
        return predecessor(name)
    if digest == binding['before_sha256']:
        return current
    if name == 'create_defaults/lifecycle/ROADMAP.md' and digest in ROADMAP_VIEWS:
        # Preserve only already sealed older views. The actual physical successor
        # was independently authenticated above; original consumers still decide
        # which prior view they accept. Never allow a physical rollback.
        return current
    if name == 'ci/people_storage_maintenance.py' and digest in STORAGE_VIEWS:
        # Geometry/M6 consumers may already have projected these exact sealed
        # views. Physical rollback is still rejected by verify_checkout above.
        return current
    if name == 'ci/dependency_tests/test_phase5_m6_maintenance.py' and digest in TEST_VIEWS:
        return current
    if name == 'ci/phase4.py' and digest in PHASE4_VIEWS:
        # Only the unchanged M6 predecessor and retained COLLECTION view.
        return current
    if opaque:
        # Legacy projection APIs leave unknown caller bytes untouched. This is
        # never physical acceptance: the complete current cohort was proved above.
        return current
    raise ValueError('Forged M7 historical view: '+name)


def selected_hash(root, name, expected):
    if name != 'ci/phase4.py' or expected != PHASE4_BEFORE:
        return expected
    with _invocation(root):
        binding = _owned_members(root)[name]
        if binding['before_sha256'] != expected:
            raise ValueError('Changed M7 Phase 4 predecessor')
        historical_bytes(root, name, regular(ROOT, name).read_bytes())
        return binding['sha256']


def verify_scope(root, names):
    selected = names & scope_members()
    if not selected:
        return
    value = verify_checkout(root)
    rows = git(root, 'diff', '--raw', '--no-abbrev', '--no-renames', '-z',
               BASE, 'HEAD', '--', *sorted(selected)).split(b'\0')
    if rows[-1] != b'' or len(rows) != 2*len(selected)+1:
        raise ValueError('Incomplete M7 maintenance diff')
    seen = set()
    for i in range(0, len(rows)-1, 2):
        fields, name = rows[i].split(), rows[i+1].decode('utf8')
        mode, status = (b':100644', b'M') if name in MODIFIED else (b':000000', b'A')
        if (name not in selected or name in seen or len(fields) != 5
                or fields[:2] != [mode, b'100644'] or fields[4] != status):
            raise ValueError('M7 requires exact regular-file changes')
        seen.add(name)
        current = regular(root, name).read_bytes()
        if sha(current) != sha(git(root, 'show', 'HEAD:'+name)):
            raise ValueError('Changed committed M7 source: '+name)
    if seen != selected:
        raise ValueError('Missing M7 maintenance member')
    verify_checkout(root)
