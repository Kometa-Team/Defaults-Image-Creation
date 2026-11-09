"""Exact Unicode/Inter CI successor. No runtime or publication authorization.

The M5 loader independently pins this adapter. Every acceptance rechecks current
regular files; only immutable Git predecessors and pure byte digests are cached.
Historical receipts remain unchanged and their original verifiers still run.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess

from ci.people_storage_maintenance import regular

ROOT = Path(__file__).resolve().parents[1]
BASE = '05ea93ba4b75a6c8fbd3755bdf817cb6c8485338'
M7_BASE = '68179d1c568449375ca72b23239b57770dfc229e'
SOURCE = 'ci/people-unicode-source-v1.json'
DELIVERY = 'ci/people-unicode-ci-v1.json'
SOURCE_PIN = '6437d0994153e168fc182a4d05c1226e4ca90812340ab5f54d50a99752233a2b'
DELIVERY_PIN = '8418a67444307deba1d5205107820daea67c2785d330fec010b5c97b114c8077'
SOURCE_MEMBERS = frozenset(('.dockerignore', 'create_people_posters/bulk/Dockerfile', 'create_people_posters/bulk/requirements.lock', 'create_people_posters/bulk_regenerate.py', 'create_people_posters/bulk_regeneration_plan.py', 'create_people_posters/bulk_runtime.py', 'create_people_posters/create_people_poster.ps1', 'create_people_posters/create_people_poster.py', 'create_people_posters/fonts/Inter-Light.ttf', 'create_people_posters/fonts/OFL-Inter.txt', 'create_people_posters/poster_fonts.py', 'create_people_posters/poster_renderer.py', 'create_people_posters/requirements-bulk-regenerate.txt', 'create_people_posters/requirements.txt', 'create_people_posters/unicode/README.md', 'create_people_posters/unicode/font-provenance.json', 'create_people_posters/unicode/qualify.py', 'create_people_posters/unicode/runtime-release-v3.json', 'create_people_posters/unicode/tests/test_unicode_successor.py', 'create_people_posters/unicode_labels.py', 'create_people_posters/unicode_review.py', 'create_people_posters/unicode_runtime.py'))
CI_MEMBERS = frozenset(('.github/workflows/default-poster-validation.yml', '.github/workflows/dependency-provenance-validation.yml', '.github/workflows/lifecycle-m7-validation.yml', '.github/workflows/people-bulk-validation.yml', '.github/workflows/people-storage-validation.yml', '.github/workflows/phase5-m3-validation.yml', '.github/workflows/phase5-m4-validation.yml', '.github/workflows/phase5-m5-validation.yml', 'ci/people_bulk_maintenance.py', 'ci/people_collection_maintenance.py', 'ci/people_readme_maintenance.py', 'ci/people_unicode_profile.py', 'ci/phase4_transactions.py', 'ci/tests/test_validation.py', 'ci/unicode_tests/test_people_unicode_maintenance.py', 'ci/validation.py', 'create_defaults/phase4/m7_tests/test_ci.py', 'create_defaults/phase4/tests/test_ci_foundations.py', 'create_people_posters/tests/test_ddcolor_colorizer.py'))
ANCHORS = frozenset((SOURCE, DELIVERY, 'ci/people_unicode_maintenance.py',
                     'ci/phase5_m5_maintenance.py'))

PUBLICATION_ADAPTER_SHA256 = '39df495fe7d249113a5fd074a71c2696bc8a4602095ce2e554579a371fedd15e'


@lru_cache(maxsize=8)
def _publication_module(raw):
    from types import ModuleType
    module = ModuleType('verified_people_publication_maintenance')
    module.__file__ = str(ROOT / 'ci/people_publication_maintenance.py')
    exec(compile(raw, module.__file__, 'exec'), module.__dict__)
    return module


def publication_adapter():
    raw = regular(ROOT, 'ci/people_publication_maintenance.py').read_bytes()
    if digest(raw) != PUBLICATION_ADAPTER_SHA256:
        raise ValueError('Changed independently pinned publication adapter')
    return _publication_module(raw)


@lru_cache(maxsize=128)
def _digest_bytes(raw, text_lf):
    # Only immutable byte arithmetic is cached, never paths or verification.
    return hashlib.sha256(raw.replace(b'\r\n', b'\n') if text_lf else raw).hexdigest()


def digest(raw, text_lf=True):
    if type(raw) is bytes:
        return _digest_bytes(raw, bool(text_lf))
    return hashlib.sha256(raw.replace(b'\r\n', b'\n') if text_lf else raw).hexdigest()


def fingerprint(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=True,
        allow_nan=False, separators=(',', ':')).encode(), False)


def git(*args):
    result = subprocess.run(['git', *args], cwd=ROOT, capture_output=True)
    if result.returncode:
        raise ValueError('Cannot verify Unicode successor Git provenance')
    return result.stdout


@lru_cache(maxsize=128)
def predecessor(name):
    entry = git('ls-tree', '-z', BASE, '--', name)
    if not entry:
        return None
    if not entry.startswith(b'100644 blob '):
        raise ValueError('Unicode predecessor is not a regular file')
    return git('show', BASE+':'+name)


def receipts():
    source = json.loads(regular(ROOT, SOURCE).read_bytes())
    ci = json.loads(regular(ROOT, DELIVERY).read_bytes())
    if (fingerprint(source) != SOURCE_PIN or fingerprint(ci) != DELIVERY_PIN
            or set(source['files']) != SOURCE_MEMBERS or set(ci['files']) != CI_MEMBERS
            or ci['source_receipt_sha256'] != SOURCE_PIN
            or any(v['baseline_commit'] != BASE or v['version'] != 1
                   or v['ci_authorized'] is not False
                   or v['publication_authorized'] is not False for v in (source, ci))):
        raise ValueError('Changed exact Unicode successor receipt or authority')
    return source, ci


@lru_cache(maxsize=32)
def ancestry(head):
    # Cache only immutable commit ancestry; resolve HEAD afresh on every proof.
    git('merge-base', '--is-ancestor', BASE, head)


def _publication_identity(root, publication):
    # Reauthenticate immutable metadata at both ends of this one owner call.
    # No proof or physical input survives a later invocation.
    for name, pin in ((publication.RECEIPT, publication.PIN),
                      (publication.GIT_RECEIPT, publication.GIT_PIN),
                      (publication.RECOVERY_RECEIPT, publication.RECOVERY_PIN)):
        if publication.fingerprint(json.loads(regular(root, name).read_bytes())) != pin:
            raise ValueError('Changed invocation-local publication receipt: '+name)
    if digest(regular(root, 'ci/people_publication_maintenance.py').read_bytes()) != PUBLICATION_ADAPTER_SHA256:
        raise ValueError('Changed invocation-local publication adapter')


def _publication_close(root, publication, timeouts):
    _publication_identity(root, publication)
    # Preserve the closing full physical cohort check. Only repeated immutable
    # predecessor/schema computations from the earlier full proof are reused.
    current = {}
    for receipt in (publication.RECEIPT, publication.GIT_RECEIPT, publication.RECOVERY_RECEIPT):
        current.update(json.loads(regular(root, receipt).read_bytes())['files'])
    for name, binding in current.items():
        expected = binding['sha256']
        if name in timeouts and expected == timeouts[name]['before_sha256']:
            expected = timeouts[name]['sha256']
        if digest(regular(root, name).read_bytes()) != expected:
            raise ValueError('Changed closing publication member: '+name)
    if digest(regular(root, publication.CI_TEST_LOCK).read_bytes()) != publication.CI_TEST_LOCK_SHA:
        raise ValueError('Changed closing publication dependency')
    _publication_identity(root, publication)


def _owned_headers(root, publication):
    from ci import phase5_m6_maintenance as m6
    from ci.people_collection_maintenance import _head
    names = set(ANCHORS) | {
        'ci/phase5_m6_maintenance.py', m6.MANIFEST.relative_to(m6.ROOT).as_posix(),
        m6.TIMEOUT_RECEIPT, m6.RECOVERY_CI_RECEIPT, m6.GEOMETRY_RECEIPT,
        m6.RETENTION_GEOMETRY_RECEIPT, m6.COMPUTATION_RECEIPT,
        publication.RECEIPT, publication.GIT_RECEIPT, publication.RECOVERY_RECEIPT,
        'ci/people_publication_maintenance.py', publication.CI_TEST_LOCK}
    return _head(root), {name:(digest(regular(root,name).read_bytes()),True) for name in names}


def _owned_inputs(root, publication, physical, headers):
    from ci import phase5_m6_maintenance as m6
    expected=dict(physical)
    timeouts=m6.timeout_bindings(root)
    for name,binding in m6.manifest()['members'].items():
        expected[name]=(timeouts[name]['sha256'] if name in timeouts else binding['sha256'],True)
    expected[m6.GEOMETRY_SOURCE]=(m6.GEOMETRY_SHA,True)
    expected[m6.RETENTION_GEOMETRY_SOURCE]=(m6.RETENTION_GEOMETRY_SHA,True)
    expected.update({name:(value,True) for name,value in m6.COMPUTATION_AFTER.items()})
    for name,binding in timeouts.items():expected[name]=(binding['sha256'],True)
    current={}
    for receipt in (publication.RECEIPT,publication.GIT_RECEIPT,publication.RECOVERY_RECEIPT):
        current.update(json.loads(regular(root,receipt).read_bytes())['files'])
    for name,binding in current.items():
        selected=binding['sha256']
        if name in timeouts and selected==timeouts[name]['before_sha256']:selected=timeouts[name]['sha256']
        expected[name]=(selected,True)
    # Headers were captured before the proof; changed policy bytes cannot enter
    # this private owner witness after verification. Every path is reread below.
    expected.update(headers[1])
    return headers[0],tuple((name,*value) for name,value in sorted(expected.items()))


def _close_owned(root, owned):
    from ci.people_collection_maintenance import _head
    if _head(root)!=owned[0]:raise ValueError('Changed owner HEAD')
    for name,expected,text_lf in owned[1]:
        if digest(regular(root,name).read_bytes(),text_lf)!=expected:
            raise ValueError('Changed closing owner input: '+name)


def _historical_owned(root,name,current,bindings,owned):
    if name not in bindings:return historical_bytes(root,name,current)
    expected,text_lf=next(row[1:] for row in owned[1] if row[0]==name)
    actual=regular(root,name).read_bytes()
    if digest(actual,text_lf)!=expected or digest(current,text_lf)!=expected:
        raise ValueError('Changed owner projection input: '+name)
    binding=bindings[name]
    return predecessor(name) if binding['before_sha256'] is not None else current


def verify(root=ROOT):
    return _verify(root,False)[0]


def _verify_owned(root):
    return _verify(root,True)


def _verify(root, owned):
    if Path(root).resolve() != ROOT.resolve():
        raise ValueError('Foreign Unicode policy checkout')
    from ci.phase5_m5_maintenance import UNICODE_ADAPTER_SHA256
    if digest(regular(ROOT, 'ci/people_unicode_maintenance.py').read_bytes()) != UNICODE_ADAPTER_SHA256:
        raise ValueError('Changed independently pinned Unicode adapter')
    publication = publication_adapter()
    headers = _owned_headers(root,publication) if owned else None
    physical_hashes = {}
    source, ci = receipts()
    publication = publication_adapter()
    from ci import phase5_m6_maintenance as m6
    timeouts = m6.timeout_bindings(root)
    publication_bindings = publication.verify(root)
    _publication_identity(root, publication)
    from ci.people_collection_maintenance import _head
    ancestry(_head(ROOT))
    bindings = {**source['files'], **ci['files']}
    # The README helper is itself a successor member. Never use a modified
    # helper to authenticate its own physical bytes; use the unchanged checker.
    paths = {name: regular(ROOT, name) for name in set(bindings) | ANCHORS}
    for name, binding in bindings.items():
        if set(binding) != {'operation', 'text_lf', 'before_sha256', 'sha256'}:
            raise ValueError('Changed Unicode binding schema')
        before = predecessor(name)
        # Read independently after the full publication proof, at the point of use.
        physical = regular(root, name).read_bytes()
        current = physical
        if owned:physical_hashes[name]=(digest(physical,binding['text_lf']),binding['text_lf'])
        if name == 'create_defaults/phase4/tests/test_ci_foundations.py':
            from ci.phase5_m6_maintenance import historical_bytes as m6_bytes
            current = m6_bytes(root, name, current)
        if name in publication_bindings:
            # Reuse only this invocation's verified metadata, never its old bytes.
            # A post-proof mutation cannot be relabelled as historical artwork.
            approved = publication_bindings[name]
            if digest(physical) != approved['sha256']:
                raise ValueError('Changed post-proof publication member: '+name)
            if approved['before_sha256'] is not None:
                current = publication.predecessor(name)
        elif name in timeouts:
            timeout = timeouts[name]
            if digest(physical) != timeout['sha256']:
                raise ValueError('Changed owned timeout member: '+name)
            current = timeout['predecessor_lf'].encode() if timeout['predecessor_lf'] is not None else physical
        elif name in m6.COMPUTATION_BEFORE:
            if digest(physical) != m6.COMPUTATION_AFTER[name]:
                raise ValueError('Changed owned computation member: '+name)
            current = m6._computation_before(name)
        if (binding['operation'] != ('A' if before is None else 'M')
                or binding['before_sha256'] != (None if before is None else digest(before, binding['text_lf']))
                or digest(current, binding['text_lf']) != binding['sha256']):
            raise ValueError('Changed Unicode predecessor/successor: '+name)
    _publication_close(root, publication, timeouts)
    if m6.timeout_bindings(root) != timeouts:
        raise ValueError('Changed closing timeout metadata')
    return bindings,_owned_inputs(root,publication,physical_hashes,headers) if owned else None


def historical_bytes(root, name, current):
    from ci.phase5_m6_maintenance import historical_bytes as m6_bytes
    current = m6_bytes(root, name, current)
    current = publication_adapter().historical_bytes(root, name, current)
    if name not in SOURCE_MEMBERS | CI_MEMBERS:
        return current
    binding = verify(root)[name]
    if binding['before_sha256'] is not None and digest(current, binding['text_lf']) == binding['sha256']:
        return predecessor(name)
    # Earlier projections and forged inputs remain subject to the original
    # caller's immutable receipt. No arbitrary input is relabelled as old bytes.
    return current


def selected_hash(name, expected):
    expected = publication_adapter().selected_hash(name, expected)
    if name not in SOURCE_MEMBERS | CI_MEMBERS:
        return publication_adapter().timeout_hash(name, expected)
    binding = verify()[name]
    return publication_adapter().timeout_hash(name, binding['sha256'] if binding['before_sha256'] is not None and expected == binding['before_sha256'] else expected)


def scope_members():
    return SOURCE_MEMBERS | CI_MEMBERS | ANCHORS | publication_adapter().scope_members()


def verify_scope(root, baseline, names):
    bindings = {**verify(root), **publication_adapter().verify(root), **publication_adapter().git_bindings(root), **publication_adapter().recovery_bindings(root)}
    if baseline != M7_BASE or not names <= scope_members():
        raise ValueError('Unapproved Unicode scope or baseline')
    if not names:
        return
    rows = git('diff', '--raw', '--no-abbrev', '--no-renames', '-z', baseline,
               'HEAD', '--', *sorted(names)).split(b'\0')
    if rows[-1] != b'' or len(rows) != 2*len(names)+1:
        raise ValueError('Incomplete Unicode scope diff')
    seen = set()
    for offset in range(0, len(rows)-1, 2):
        fields, name = rows[offset].split(), rows[offset+1].decode('utf8')
        if (name not in names or name in seen or len(fields) != 5
                or fields[:2] not in ([b':000000', b'100644'], [b':100644', b'100644'])
                or fields[4] != (b'A' if fields[0] == b':000000' else b'M')):
            raise ValueError('Unicode requires regular-file additions/modifications')
        committed = git('show', 'HEAD:'+name)
        if name in bindings:
            expected = bindings[name]['sha256']
            text = bindings[name]['text_lf']
        else:
            expected = digest(regular(ROOT, name).read_bytes())
            text = True
        expected = publication_adapter().timeout_hash(name, expected)
        if digest(committed, text) != expected:
            raise ValueError('Unapproved committed Unicode successor: '+name)
        seen.add(name)
