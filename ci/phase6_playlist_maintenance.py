"""Exact Phase 6 offline fixture successor; prior receipts remain immutable."""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import subprocess
from threading import get_ident

from ci.people_storage_maintenance import regular

ROOT = Path(__file__).resolve().parents[1]
BASE = 'dcbfa072dbedcb0069dd27be920ef3103687b5a4'
OWNER = 'ci/phase6_playlist_maintenance.py'
RECEIPT = 'ci/phase6-playlist-maintenance-v1.json'
PIN = 'f27647c21034237eda308f6f84c8385cf20a5922a1f6ce7d3145991431e94d37'
# Generated explicitly by the review tooling; never a directory-prefix grant.
MODIFIED = frozenset(('ci/dependabot_maintenance.py', 'ci/phase5_m7_maintenance.py', 'create_defaults/bulk/contracts/expanded/validation.py', 'create_defaults/bulk/contracts/translation_preflight/adapters.py', 'create_defaults/bulk/lifecycle/candidates.py', 'create_defaults/bulk/lifecycle/catalog_preparation.py', 'create_defaults/bulk/lifecycle/composition.py', 'create_defaults/bulk/lifecycle/operations.py', 'create_defaults/bulk/lifecycle/preparation_models.py', 'create_defaults/bulk/lifecycle/publication_preparation.py', 'create_defaults/bulk/lifecycle/schemas/preparation-v1.schema.json', 'create_defaults/bulk/operator_publication.py', 'create_defaults/bulk/planner.py', 'create_defaults/bulk/schemas/manifest-v1.json', 'create_defaults/bulk/workers.py', 'create_defaults/create_poster.py', 'create_defaults/lifecycle/ROADMAP.md'))
ADDED = frozenset(('.github/workflows/phase6-playlist-validation.yml', 'ci/dependency_tests/test_phase6_playlist_maintenance.py', 'create_defaults/image_layout.py', 'create_defaults/lifecycle/PHASE6_PLAYLIST_PILOT.md', 'create_defaults/phase6/PLAYLIST_PILOT_MANIFEST.json', 'create_defaults/phase6/STAGING_APP.md', 'create_defaults/phase6/__init__.py', 'create_defaults/phase6/assets/avp.png', 'create_defaults/phase6/assets/babylon.png', 'create_defaults/phase6/assets/bsg.png', 'create_defaults/phase6/assets/gundam.png', 'create_defaults/phase6/assets/jrrt.png', 'create_defaults/phase6/assets/sao.png', 'create_defaults/phase6/assets/stargate.png', 'create_defaults/phase6/assets/wdu.png', 'create_defaults/phase6/fixtures.py', 'create_defaults/phase6/playlist.py', 'create_defaults/phase6/render_review.py', 'create_defaults/phase6/review/EVIDENCE_INDEX.md', 'create_defaults/phase6/review/approved-transport-native-proof.json', 'create_defaults/phase6/review/approved-transport-result.json', 'create_defaults/phase6/review/candidate-integrity-result.json', 'create_defaults/phase6/review/colour-review.json', 'create_defaults/phase6/review/eight-poster-colour-proposals.png', 'create_defaults/phase6/review/historical-comparison.json', 'create_defaults/phase6/review/nine-poster-historical-comparison.png', 'create_defaults/phase6/review/replacements/README.md', 'create_defaults/phase6/review/replacements/patch-validation.json', 'create_defaults/phase6/review/replacements/replacement-plan.json', 'create_defaults/phase6/review/replacements/two-playlist-replacements.patch', 'create_defaults/phase6/review/visual-approval.json', 'create_defaults/phase6/staging_app.html', 'create_defaults/phase6/staging_app.js', 'create_defaults/phase6/staging_app.py', 'create_defaults/phase6/staging_fixtures/approved/playlist/Alien & Predator (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Babylon 5 (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Battlestar Galactica (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Middle-earth (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Mobile Suit Gundam (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Star Wars The Clone Wars (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Stargate (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Sword Art Online (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/The Walking Dead Universe (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/X-Men (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/eight-create-visual-approval.json', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Arrowverse (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/DC Animated Universe (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Dragon Ball (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Marvel Cinematic Universe (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Pokémon (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Star Trek (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Star Wars (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Star Wars The Clone Wars (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/X-Men (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/ten-item-fixtures.json', 'create_defaults/phase6/staging_fixtures/two-replacement-visual-approval.json', 'create_defaults/phase6/tests/conftest.py', 'create_defaults/phase6/tests/staging_browser.cjs', 'create_defaults/phase6/tests/test_playlist_pilot.py', 'create_defaults/phase6/tests/test_staging_app.py', 'create_defaults/phase6/verify_approved_transport.py', 'create_defaults/poster_styles.py', 'create_defaults/tests/test_playlist_layout.py'))
BINARY = frozenset(('create_defaults/phase6/assets/avp.png', 'create_defaults/phase6/assets/babylon.png', 'create_defaults/phase6/assets/bsg.png', 'create_defaults/phase6/assets/gundam.png', 'create_defaults/phase6/assets/jrrt.png', 'create_defaults/phase6/assets/sao.png', 'create_defaults/phase6/assets/stargate.png', 'create_defaults/phase6/assets/wdu.png', 'create_defaults/phase6/review/eight-poster-colour-proposals.png', 'create_defaults/phase6/review/nine-poster-historical-comparison.png', 'create_defaults/phase6/staging_fixtures/approved/playlist/Alien & Predator (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Babylon 5 (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Battlestar Galactica (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Middle-earth (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Mobile Suit Gundam (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Star Wars The Clone Wars (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Stargate (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Sword Art Online (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/The Walking Dead Universe (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/X-Men (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Arrowverse (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/DC Animated Universe (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Dragon Ball (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Marvel Cinematic Universe (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Pokémon (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Star Trek (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Star Wars (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Star Wars The Clone Wars (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/X-Men (Timeline Order).jpg'))


@lru_cache(maxsize=256)
def sha(raw):
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()


def fingerprint(value):
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
        separators=(',', ':')).encode())


@lru_cache(maxsize=256)
def member_sha(name, raw):
    return hashlib.sha256(raw if name in BINARY else raw.replace(b'\r\n', b'\n')).hexdigest()


def scope_members():
    return MODIFIED | ADDED | {OWNER, RECEIPT}


def git(*args, data=None):
    result = subprocess.run(['git', *args], cwd=ROOT, input=data, capture_output=True, timeout=180)
    if result.returncode:
        raise ValueError('Cannot authenticate offline Playlist history')
    return result.stdout


@lru_cache(maxsize=8)
def _decode(raw):
    value = json.loads(raw)
    if (fingerprint(value) != PIN or set(value) != {'version', 'baseline_commit', 'members',
            'offline_fixture_only', 'production_authorized', 'publication_authorized'}
            or value['version'] != 1 or value['baseline_commit'] != BASE
            or value['offline_fixture_only'] is not True or value['production_authorized'] is not False
            or value['publication_authorized'] is not False or set(value['members']) != MODIFIED | ADDED):
        raise ValueError('Changed exact offline Playlist receipt')
    rows = []
    for name, binding in sorted(value['members'].items()):
        if (set(binding) != {'before_sha256', 'sha256', 'text_lf'}
                or binding['text_lf'] is not (name not in BINARY)
                or (binding['before_sha256'] is None) != (name in ADDED)):
            raise ValueError('Changed offline Playlist predecessor membership')
        rows.append((name, binding['before_sha256'], binding['sha256']))
    return tuple(rows)


@lru_cache(maxsize=16)
def _tree(commit):
    entries = []
    for row in git('ls-tree', '-r', '-z', commit, '--', *sorted(scope_members())).split(b'\0'):
        if not row:
            continue
        metadata, name = row.split(b'\t', 1)
        mode, kind, oid = metadata.split()
        if mode != b'100644' or kind != b'blob':
            raise ValueError('Offline Playlist requires regular committed files')
        entries.append((name.decode(), oid.decode()))
    return tuple(entries)


@lru_cache(maxsize=16)
def _blobs(commit):
    # Immutable Git objects only. No physical bytes, HEAD or approval is cached.
    tree = _tree(commit)
    encoded = git('cat-file', '--batch', data=b''.join(oid.encode()+b'\n' for _, oid in tree))
    offset, rows = 0, []
    for name, oid in tree:
        end = encoded.index(b'\n', offset)
        header = encoded[offset:end].split()
        if len(header) != 3 or header[:2] != [oid.encode(), b'blob']:
            raise ValueError('Missing offline Playlist immutable object')
        size = int(header[2])
        if not 0 <= size <= 2*1024*1024:
            raise ValueError('Offline Playlist immutable object bound')
        offset = end+1
        raw = encoded[offset:offset+size]
        if len(raw) != size or encoded[offset+size:offset+size+1] != b'\n':
            raise ValueError('Incomplete offline Playlist immutable object')
        offset += size+1
        rows.append((name, raw))
    if offset != len(encoded):
        raise ValueError('Extra offline Playlist immutable object bytes')
    return tuple(rows)


@lru_cache(maxsize=16)
def _ancestry(head):
    git('merge-base', '--is-ancestor', BASE, head)


@lru_cache(maxsize=16)
def _diff(head, baseline=BASE):
    rows = git('diff', '--raw', '--no-abbrev', '--no-renames', '-z', baseline, head).split(b'\0')
    if rows[-1] != b'' or len(rows) % 2 != 1:
        raise ValueError('Incomplete offline Playlist scope diff')
    return tuple((rows[i], rows[i+1].decode()) for i in range(0, len(rows)-1, 2))


def _regular_diff(rows, names, *, exact=False):
    seen = set()
    for metadata, name in rows:
        if name not in names:
            if exact:
                raise ValueError('Unapproved offline Playlist path: '+name)
            continue
        fields = metadata.split()
        if (name in seen or len(fields) != 5
                or fields[:2] not in ([b':000000', b'100644'], [b':100644', b'100644'])
                or fields[4] != (b'A' if fields[0] == b':000000' else b'M')):
            raise ValueError('Offline Playlist rejects links, mode changes and nonregular changes: '+name)
        seen.add(name)
    if exact and seen != names:
        raise ValueError('Missing offline Playlist committed member')
    return seen


@dataclass(frozen=True)
class _Proof:
    head: str
    receipt: bytes
    owner_sha256: str
    rows: tuple
    selected: tuple


@lru_cache(maxsize=16)
def _immutable_checked(head, raw):
    rows = _decode(raw)
    current, before = dict(_blobs(head)), dict(_blobs(BASE))
    if set(current) != scope_members():
        raise ValueError('Missing/extra offline Playlist immutable member')
    _regular_diff(_diff(head), scope_members(), exact=True)
    for metadata, name in _diff(head):
        status = metadata.split()[4]
        if status != (b'M' if name in MODIFIED else b'A'):
            raise ValueError('Changed offline Playlist member admission: '+name)
    for name, predecessor, successor in rows:
        if member_sha(name, current[name]) != successor:
            raise ValueError('Changed committed offline Playlist successor: '+name)
        if name in MODIFIED:
            if name not in before or member_sha(name, before[name]) != predecessor:
                raise ValueError('Changed offline Playlist predecessor: '+name)
        elif name in before:
            raise ValueError('Offline Playlist addition exists in predecessor: '+name)
    if sha(raw) != sha(current[RECEIPT]):
        raise ValueError('Uncommitted offline Playlist receipt')
    return sha(current[OWNER])


def proof(root, head, *, selected=None):
    if Path(root).resolve() != ROOT.resolve():
        raise ValueError('Foreign offline Playlist checkout')
    if not isinstance(head, str) or re.fullmatch('[0-9a-f]{40}', head) is None:
        raise ValueError('Offline Playlist immutable inputs require a full SHA')
    _ancestry(head)
    raw = regular(ROOT, RECEIPT).read_bytes()
    rows = _decode(raw)
    immutable_owner = _immutable_checked(head, raw)
    selected = MODIFIED | ADDED if selected is None else frozenset(selected)
    if not selected <= MODIFIED | ADDED:
        raise ValueError('Foreign offline Playlist proof selection')
    for name, _, successor in rows:
        if name in selected and member_sha(name, regular(ROOT, name).read_bytes()) != successor:
            raise ValueError('Changed physical offline Playlist successor: '+name)
    owner = sha(regular(ROOT, OWNER).read_bytes())
    if owner != immutable_owner:
        raise ValueError('Uncommitted offline Playlist owner or receipt')
    if regular(ROOT, RECEIPT).read_bytes() != raw:
        raise ValueError('Offline Playlist receipt moved during verification')
    return _Proof(head, raw, owner, rows, tuple(sorted(selected)))


def _project(root, name, current, witness, *, owned=False):
    if Path(root).resolve() != ROOT.resolve():
        raise ValueError('Foreign offline Playlist historical projection')
    if name not in MODIFIED:
        return current
    rows = _decode(witness.receipt)
    binding = next(row for row in rows if row[0] == name)
    _, predecessor, successor = binding
    # Each historical projection checks the leaf at the point of use. A caller
    # holding old bytes cannot substitute for current physical acceptance.
    physical = current if owned else regular(root, name).read_bytes()
    if member_sha(name, physical) != successor:
        raise ValueError('Changed physical offline Playlist successor: '+name)
    if member_sha(name, current) == successor:
        before = dict(_blobs(BASE))[name]
        if member_sha(name, before) != predecessor:
            raise ValueError('Changed offline Playlist predecessor object: '+name)
        return before
    # Older sealed projection layers continue to decide which prior views they
    # accept. This does not accept a physical rollback, proved above.
    return current


def historical_bytes(root, name, current):
    if name not in MODIFIED:
        return current
    from ci import phase5_m7_maintenance as m7
    owner = m7._ACTIVE.get()
    if (owner is not None and owner[1][0] and owner[2] == (str(m7.ROOT.absolute()), get_ident())
            and len(owner[0]) == 5):
        return _project(root, name, current, owner[0][4])
    with m7._invocation(root):
        return historical_bytes(root, name, current)


def selected_hash(name, expected):
    """Select the exact physical adoption successor, not a historical view."""
    if name != 'create_defaults/bulk/operator_publication.py':
        return expected
    _, before, after = next(row for row in _decode(regular(ROOT, RECEIPT).read_bytes())
        if row[0] == name)
    if expected != before:
        return expected
    from ci.people_colorize_maintenance import _head
    entry = proof(ROOT, _head(ROOT), selected={name})
    if proof(ROOT, _head(ROOT), selected={name}) != entry:
        raise ValueError('Changed closing offline Playlist adoption successor')
    return after


def verify_scope(root, names):
    selected = names & scope_members()
    if not selected:
        return
    from ci.phase5_m7_maintenance import _cohort_proof
    entry = _cohort_proof(root, _pilot_cohort_proof)
    if entry is not None:
        # The aggregate rechecks this full physical cohort at its closing proof,
        # after all historical projections, not merely at scope-check entry.
        return
    entry = _pilot_cohort_proof(root)
    if not selected <= scope_members():
        raise ValueError('Unapproved offline Playlist scope')
    if _pilot_cohort_proof(root) != entry:
        raise ValueError('Changed closing offline Playlist scope')


def _pilot_cohort_proof(root):
    from ci.people_colorize_maintenance import _head
    return proof(root, _head(root))


def verify_checkout(root=ROOT, *, expected_head=None):
    from ci.people_colorize_maintenance import _head
    entry = proof(root, _head(root))
    if expected_head is not None and entry.head != expected_head:
        raise ValueError('Offline Playlist expected HEAD differs from committed checkout')
    if proof(root, _head(root)) != entry:
        raise ValueError('Changed closing offline Playlist owner, receipt or HEAD')
    return dict(kind='phase6-offline-playlist-provenance', head=entry.head,
        files=len(scope_members()), production_authorized=False, publication_authorized=False)


if __name__ == '__main__':
    import os
    print(json.dumps(verify_checkout(expected_head=os.environ.get('EXPECTED_HEAD')), sort_keys=True))
