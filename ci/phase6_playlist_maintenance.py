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
PIN = '2625bc13ac87d79b6f287ae79ddb99d13bcbca0bd45d61215fce74cf46679906'
REGISTRY_BASE = '8a3acdffb5cb564e57d41de397bd16039ea97457'
REGISTRY_RECEIPT = 'ci/catalog-reservations-maintenance-v2.json'
REGISTRY_PREDECESSOR = '276ad76dbe06408a1338dec5910b918a5f8fb5ef'
REGISTRY_PRIOR_RECEIPT = 'ci/catalog-reservations-maintenance-v1.json'
REGISTRY_PRIOR_SHA256 = '188dd31b3bc1fa1902767608e16fea394649132b1f8c4ee2f056d32de593df3d'
REGISTRY_PIN = '6def6e32504a80de26748685011a31f485c21aed5cf62706e3a43fce5589aab0'
REGISTRY_ADDED = frozenset((
    '.github/workflows/catalog-reservations-validation.yml',
    'ci/dependency_tests/test_catalog_reservations_maintenance.py',
    'create_defaults/bulk/CATALOG_RESERVATIONS.md',
    'create_defaults/bulk/catalog_reservations.py',
    'create_defaults/bulk/catalog/reservations-v1.json',
    'create_defaults/phase6/tests/test_catalog_reservations.py',
    'create_defaults/phase6/review/catalog-reservations-staging.json',
))
REGISTRY_MODIFIED = frozenset((
    'ci/publication_tests/test_validation_timeouts.py',
    'ci/dependency_tests/test_phase6_playlist_maintenance.py',
))
# Exact, separately reviewed data successor. The original receipts stay sealed.
DATA_BASE = 'e58da53c03857ade7b2bdd0c743c6970c0c761a3'
DATA_PREDECESSOR = 'd94d3209b0bd498494125137ab6db93b7aadc081'
DATA_ALLOCATION = 'd3ed9ff46a77cb7a13caef57a84830f08e1d25c8'
DATA_RECEIPT = 'ci/catalog-data-successor-v1.json'
DATA_PIN = 'e4285efa27ad9d0bdaa17ab43c9d2cf2b4f8e3e9591741dca511ad216bca04b7'
DATA_MODIFIED = frozenset((
    '.github/workflows/catalog-reservations-validation.yml',
    'ci/dependency_tests/test_catalog_reservations_maintenance.py',
    'ci/dependency_tests/test_phase6_playlist_maintenance.py',
    'ci/phase5_m6_maintenance.py', 'ci/phase5_m7_maintenance.py',
    'create_defaults/bulk/catalog/reservations-v1.json',
    'create_defaults/bulk/catalog/playlist.yml', 'create_defaults/bulk/catalog/index-v1.json',
    'create_defaults/bulk/contracts/playlist/validation.py',
    'create_defaults/bulk/lifecycle/basis.py',
    'create_defaults/bulk/contracts/adoption/inventory.py',
    'create_defaults/bulk/contracts/categories/evidence.py',
    'create_defaults/bulk/contracts/expanded/historical.py',
    'create_defaults/bulk/tests/conftest.py',
    'create_defaults/bulk/tests/test_catalog_generation.py',
    'create_defaults/phase2/tests/test_package_a.py',
    'create_defaults/phase3/tests/translation_samples.py',
    'create_defaults/phase3/tests/test_final_phase3_acceptance.py',
))
DATA_ADDED = frozenset((
    'ci/dependency_tests/test_catalog_data_maintenance.py',
    'create_defaults/bulk/catalog_history.py',
    'create_defaults/phase6/tests/test_historical_catalog.py',
    'create_defaults/logos_playlist/avp.png', 'create_defaults/logos_playlist/babylon.png',
    'create_defaults/logos_playlist/bsg.png', 'create_defaults/logos_playlist/gundam.png',
    'create_defaults/logos_playlist/jrrt.png', 'create_defaults/logos_playlist/sao.png',
    'create_defaults/logos_playlist/stargate.png', 'create_defaults/logos_playlist/wdu.png',
))
DATA_BINARY = frozenset(name for name in DATA_ADDED if name.endswith('.png'))
DATA_PROTECTED = frozenset(('create_defaults/bulk/catalog/playlist.yml',
    'create_defaults/bulk/catalog/index-v1.json'))


def historical_members():
    return MODIFIED | DATA_MODIFIED | source_adapter().MEMBERS


# Generated explicitly by the review tooling; never a directory-prefix grant.
MODIFIED = frozenset(('ci/dependabot_maintenance.py', 'ci/people_unicode_maintenance.py', 'ci/phase4.py', 'ci/phase4_review.py', 'ci/phase4_transactions.py', 'ci/phase5_m5_maintenance.py', 'ci/phase5_m6_maintenance.py', 'ci/phase5_m7_maintenance.py', 'ci/publication_tests/test_validation_timeouts.py', 'create_defaults/bulk/contracts/expanded/validation.py', 'create_defaults/bulk/contracts/logos/wash.py', 'create_defaults/bulk/contracts/playlist/validation.py', 'create_defaults/bulk/contracts/translation_preflight/adapters.py', 'create_defaults/bulk/lifecycle/candidates.py', 'create_defaults/bulk/lifecycle/catalog_preparation.py', 'create_defaults/bulk/lifecycle/composition.py', 'create_defaults/bulk/lifecycle/operations.py', 'create_defaults/bulk/lifecycle/preparation_models.py', 'create_defaults/bulk/lifecycle/publication_preparation.py', 'create_defaults/bulk/lifecycle/schemas/preparation-v1.schema.json', 'create_defaults/bulk/operator_publication.py', 'create_defaults/bulk/planner.py', 'create_defaults/bulk/schemas/manifest-v1.json', 'create_defaults/bulk/tests/test_logo_workflow.py', 'create_defaults/bulk/workers.py', 'create_defaults/create_poster.py', 'create_defaults/lifecycle/ROADMAP.md', 'create_defaults/phase2/tests/test_package_a.py', 'create_defaults/phase3/tests/test_destination_isolation.py', 'create_defaults/phase3/tests/test_evidence_consumption.py', 'create_defaults/phase3/tests/test_final_phase3_acceptance.py', 'create_defaults/phase3/tests/test_translation_boundaries.py', 'create_defaults/phase4/tests/test_composition.py', 'create_defaults/validation_manifest.py'))
ADDED = frozenset(('.github/workflows/phase6-playlist-validation.yml', 'ci/dependency_tests/test_phase6_playlist_maintenance.py', 'create_defaults/image_layout.py', 'create_defaults/lifecycle/PHASE6_PLAYLIST_PILOT.md', 'create_defaults/phase6/PHASE6_CLOSEOUT_CHECKLIST.md', 'create_defaults/phase6/PLAYLIST_PILOT_MANIFEST.json', 'create_defaults/phase6/STAGING_APP.md', 'create_defaults/phase6/__init__.py', 'create_defaults/phase6/assets/avp.png', 'create_defaults/phase6/assets/babylon.png', 'create_defaults/phase6/assets/bsg.png', 'create_defaults/phase6/assets/gundam.png', 'create_defaults/phase6/assets/jrrt.png', 'create_defaults/phase6/assets/sao.png', 'create_defaults/phase6/assets/stargate.png', 'create_defaults/phase6/assets/wdu.png', 'create_defaults/phase6/canonical/destination-preflight-v1.json', 'create_defaults/phase6/canonical/evidence-consumption-v1.json', 'create_defaults/phase6/canonical/logo-calibration-pillow13.json', 'create_defaults/phase6/canonical/phase3-final-acceptance-v1.json', 'create_defaults/phase6/canonical/translation-preflight-v1.json', 'create_defaults/phase6/canonical_fixtures.py', 'create_defaults/phase6/fixtures.py', 'create_defaults/phase6/playlist.py', 'create_defaults/phase6/render_review.py', 'create_defaults/phase6/review/EVIDENCE_INDEX.md', 'create_defaults/phase6/review/action-forms/blocked-removal.png', 'create_defaults/phase6/review/action-forms/browser-result.json', 'create_defaults/phase6/review/action-forms/browser-run.json', 'create_defaults/phase6/review/action-forms/catalog.json', 'create_defaults/phase6/review/action-forms/first-two-result.json', 'create_defaults/phase6/review/action-forms/focused-checks.json', 'create_defaults/phase6/review/action-forms/replacement-side-by-side.png', 'create_defaults/phase6/review/action-forms/second-style.png', 'create_defaults/phase6/review/action-forms/staging-receipts.json', 'create_defaults/phase6/review/action-forms/ten-generated-staging.png', 'create_defaults/phase6/review/action-forms/unmapped-ellipse.png', 'create_defaults/phase6/review/action-forms/unmapped-rectangle.png', 'create_defaults/phase6/review/approved-transport-native-proof.json', 'create_defaults/phase6/review/approved-transport-result.json', 'create_defaults/phase6/review/browser/backend-and-source-checks.json', 'create_defaults/phase6/review/browser/browser-result.json', 'create_defaults/phase6/review/browser/browser-run.json', 'create_defaults/phase6/review/browser/first-two-result.json', 'create_defaults/phase6/review/browser/one-create-one-replacement.png', 'create_defaults/phase6/review/browser/rollout-review.json', 'create_defaults/phase6/review/browser/staging-receipts.json', 'create_defaults/phase6/review/browser/ten-item-staging.png', 'create_defaults/phase6/review/browser/ui-source-integrity.json', 'create_defaults/phase6/review/candidate-integrity-result.json', 'create_defaults/phase6/review/colour-review.json', 'create_defaults/phase6/review/eight-poster-colour-proposals.png', 'create_defaults/phase6/review/generated-browser/blocked-removal.png', 'create_defaults/phase6/review/generated-browser/browser-result.json', 'create_defaults/phase6/review/generated-browser/browser-run.json', 'create_defaults/phase6/review/generated-browser/catalog.json', 'create_defaults/phase6/review/generated-browser/first-two-result.json', 'create_defaults/phase6/review/generated-browser/focused-checks.json', 'create_defaults/phase6/review/generated-browser/second-style.png', 'create_defaults/phase6/review/generated-browser/staging-receipts.json', 'create_defaults/phase6/review/generated-browser/ten-generated-staging.png', 'create_defaults/phase6/review/historical-comparison.json', 'create_defaults/phase6/review/nine-poster-historical-comparison.png', 'create_defaults/phase6/review/replacements/README.md', 'create_defaults/phase6/review/replacements/patch-validation.json', 'create_defaults/phase6/review/replacements/replacement-plan.json', 'create_defaults/phase6/review/replacements/two-playlist-replacements.patch', 'create_defaults/phase6/review/visual-approval.json', 'create_defaults/phase6/staging_app.html', 'create_defaults/phase6/staging_app.js', 'create_defaults/phase6/staging_app.py', 'create_defaults/phase6/staging_fixtures/approved/playlist/Alien & Predator (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Babylon 5 (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Battlestar Galactica (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Middle-earth (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Mobile Suit Gundam (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Star Wars The Clone Wars (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Stargate (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Sword Art Online (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/The Walking Dead Universe (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/X-Men (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/eight-create-visual-approval.json', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Arrowverse (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/DC Animated Universe (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Dragon Ball (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Marvel Cinematic Universe (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Pokémon (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Star Trek (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Star Wars (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Star Wars The Clone Wars (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/X-Men (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/ten-item-fixtures.json', 'create_defaults/phase6/staging_fixtures/two-replacement-visual-approval.json', 'create_defaults/phase6/staging_lifecycle.py', 'create_defaults/phase6/tests/conftest.py', 'create_defaults/phase6/tests/staging_browser.cjs', 'create_defaults/phase6/tests/staging_lifecycle_browser.cjs', 'create_defaults/phase6/tests/test_playlist_pilot.py', 'create_defaults/phase6/tests/test_staging_app.py', 'create_defaults/phase6/tests/test_staging_lifecycle.py', 'create_defaults/phase6/verify_approved_transport.py', 'create_defaults/poster_styles.py', 'create_defaults/tests/test_playlist_layout.py'))
BINARY = frozenset(('create_defaults/phase6/assets/avp.png', 'create_defaults/phase6/assets/babylon.png', 'create_defaults/phase6/assets/bsg.png', 'create_defaults/phase6/assets/gundam.png', 'create_defaults/phase6/assets/jrrt.png', 'create_defaults/phase6/assets/sao.png', 'create_defaults/phase6/assets/stargate.png', 'create_defaults/phase6/assets/wdu.png', 'create_defaults/phase6/review/action-forms/blocked-removal.png', 'create_defaults/phase6/review/action-forms/replacement-side-by-side.png', 'create_defaults/phase6/review/action-forms/second-style.png', 'create_defaults/phase6/review/action-forms/ten-generated-staging.png', 'create_defaults/phase6/review/action-forms/unmapped-ellipse.png', 'create_defaults/phase6/review/action-forms/unmapped-rectangle.png', 'create_defaults/phase6/review/browser/one-create-one-replacement.png', 'create_defaults/phase6/review/browser/ten-item-staging.png', 'create_defaults/phase6/review/eight-poster-colour-proposals.png', 'create_defaults/phase6/review/generated-browser/blocked-removal.png', 'create_defaults/phase6/review/generated-browser/second-style.png', 'create_defaults/phase6/review/generated-browser/ten-generated-staging.png', 'create_defaults/phase6/review/nine-poster-historical-comparison.png', 'create_defaults/phase6/staging_fixtures/approved/playlist/Alien & Predator (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Babylon 5 (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Battlestar Galactica (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Middle-earth (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Mobile Suit Gundam (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Star Wars The Clone Wars (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Stargate (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/Sword Art Online (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/The Walking Dead Universe (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/approved/playlist/X-Men (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Arrowverse (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/DC Animated Universe (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Dragon Ball (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Marvel Cinematic Universe (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Pokémon (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Star Trek (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Star Wars (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/Star Wars The Clone Wars (Timeline Order).jpg', 'create_defaults/phase6/staging_fixtures/staging-baseline/playlist/X-Men (Timeline Order).jpg'))


@lru_cache(maxsize=256)
def sha(raw):
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()


def fingerprint(value):
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
        separators=(',', ':')).encode())


@lru_cache(maxsize=256)
def member_sha(name, raw):
    return hashlib.sha256(raw if name in BINARY | DATA_BINARY else raw.replace(b'\r\n', b'\n')).hexdigest()


def _pilot_members():
    return MODIFIED | ADDED | {OWNER, RECEIPT, REGISTRY_RECEIPT, REGISTRY_PRIOR_RECEIPT} | REGISTRY_ADDED | DATA_MODIFIED | DATA_ADDED | {DATA_RECEIPT}


SOURCE_ADAPTER_SHA256 = '8158b19b0bfc1c8de6e7dfe2d9356ffd623efc13bb0c73501ec1e8761e8c6032'


@lru_cache(maxsize=4)
def _source_module(raw):
    from types import ModuleType
    module=ModuleType('verified_people_source_maintenance')
    module.__file__=str(ROOT/'ci/people_source_maintenance.py')
    exec(compile(raw,module.__file__,'exec'),module.__dict__)
    return module


def source_adapter():
    raw=regular(ROOT,'ci/people_source_maintenance.py').read_bytes()
    if sha(raw)!=SOURCE_ADAPTER_SHA256:raise ValueError('Changed independently pinned People source-only adapter')
    return _source_module(raw)


def scope_members():
    return _pilot_members() | source_adapter().scope_members()


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


@lru_cache(maxsize=8)
def _decode_registry(raw):
    value = json.loads(raw)
    if (fingerprint(value) != REGISTRY_PIN or set(value) != {
            'version', 'baseline_commit', 'predecessor_owner_sha256', 'members',
            'predecessor_commit', 'predecessor_receipt_sha256',
            'production_allocations_authorized', 'catalog_changes_authorized',
            'publication_authorized'} or value['version'] != 2
            or value['baseline_commit'] != REGISTRY_BASE
            or value['predecessor_commit'] != REGISTRY_PREDECESSOR
            or value['predecessor_receipt_sha256'] != REGISTRY_PRIOR_SHA256
            or set(value['members']) != REGISTRY_ADDED | REGISTRY_MODIFIED
            or value['production_allocations_authorized'] is not False
            or value['catalog_changes_authorized'] is not False
            or value['publication_authorized'] is not False):
        raise ValueError('Changed exact catalog reservation receipt')
    rows = []
    for name, binding in sorted(value['members'].items()):
        if (set(binding) != {'before_sha256', 'sha256', 'text_lf'}
                or (binding['before_sha256'] is None) != (name in REGISTRY_ADDED)
                or binding['text_lf'] is not True):
            raise ValueError('Changed catalog reservation successor membership')
        rows.append((name, binding['before_sha256'], binding['sha256']))
    return value['predecessor_owner_sha256'], tuple(rows)


@lru_cache(maxsize=8)
def _decode_data(raw):
    value = json.loads(raw)
    if (fingerprint(value) != DATA_PIN or set(value) != {
            'version', 'baseline_commit', 'predecessor_commit', 'allocation_commit',
            'predecessor_owner_sha256', 'members', 'publication_authorized'}
            or value['version'] != 1 or value['baseline_commit'] != DATA_BASE
            or value['predecessor_commit'] != DATA_PREDECESSOR
            or value['allocation_commit'] != DATA_ALLOCATION
            or value['publication_authorized'] is not False
            or set(value['members']) != DATA_MODIFIED | DATA_ADDED):
        raise ValueError('Changed exact catalog data successor receipt')
    rows = []
    for name, binding in sorted(value['members'].items()):
        if (set(binding) != {'before_sha256', 'sha256', 'text_lf'}
                or (binding['before_sha256'] is None) != (name in DATA_ADDED)
                or binding['text_lf'] is not (name not in DATA_BINARY)):
            raise ValueError('Changed catalog data successor membership')
        rows.append((name, binding['before_sha256'], binding['sha256']))
    return value['predecessor_owner_sha256'], tuple(rows)


def current_rows(raw, registry_raw, data_raw=None):
    """Current bindings; original receipt rows keep their historical meaning."""
    if data_raw is None:
        data_raw = regular(ROOT, DATA_RECEIPT).read_bytes()
    _, registered = _decode_registry(registry_raw)
    _, data = _decode_data(data_raw)
    current = {name:(before, after) for name,before,after in _decode(raw)}
    for name,before,after in registered + data:
        current[name] = (current[name][0] if name in current else before, after)
    return tuple((name,*binding) for name,binding in sorted(current.items()))


@lru_cache(maxsize=16)
def _tree(commit):
    entries = []
    for row in git('ls-tree', '-r', '-z', commit, '--', *sorted(_pilot_members())).split(b'\0'):
        if not row:
            continue
        metadata, name = row.split(b'\t', 1)
        mode, kind, oid = metadata.split()
        if mode != b'100644' or kind != b'blob':
            raise ValueError('Offline Playlist requires regular committed files')
        entries.append((name.decode(), oid.decode()))
    return tuple(entries)


@lru_cache(maxsize=16)
def _batch_blobs(commits):
    # Batch immutable objects across baselines. No checkout/HEAD proof is cached.
    trees = tuple((commit, _tree(commit)) for commit in commits)
    objects = dict.fromkeys(oid for _,tree in trees for _,oid in tree)
    encoded = git('cat-file', '--batch', data=b''.join(oid.encode()+b'\n' for oid in objects))
    offset, decoded = 0, {}
    limits = {oid:(4*1024*1024 if name == 'create_defaults/bulk/catalog/index-v1.json'
                   else 2*1024*1024) for _,tree in trees for name,oid in tree}
    for oid in objects:
        end = encoded.index(b'\n', offset)
        header = encoded[offset:end].split()
        if len(header) != 3 or header[:2] != [oid.encode(), b'blob']:
            raise ValueError('Missing offline Playlist immutable object')
        size = int(header[2])
        if not 0 <= size <= limits[oid]:
            raise ValueError('Offline Playlist immutable object bound')
        offset = end+1
        raw = encoded[offset:offset+size]
        if len(raw) != size or encoded[offset+size:offset+size+1] != b'\n':
            raise ValueError('Incomplete offline Playlist immutable object')
        offset += size+1
        decoded[oid] = raw
    if offset != len(encoded):
        raise ValueError('Extra offline Playlist immutable object bytes')
    return tuple(tuple((name,decoded[oid]) for name,oid in tree) for _,tree in trees)


@lru_cache(maxsize=16)
def _blobs(commit):
    return _batch_blobs((commit,))[0]


@lru_cache(maxsize=16)
def _ancestry(head):
    # This reviewed descendant includes the original sealed pilot baseline.
    git('merge-base', '--is-ancestor', DATA_PREDECESSOR, head)


@lru_cache(maxsize=16)
def _diff(head, baseline=BASE):
    rows = git('diff', '--raw', '--no-abbrev', '--no-renames', '-z', baseline, head).split(b'\0')
    if rows[-1] != b'' or len(rows) % 2 != 1:
        raise ValueError('Incomplete offline Playlist scope diff')
    source=source_adapter().scope_members()-_pilot_members()
    return tuple((rows[i], rows[i+1].decode()) for i in range(0, len(rows)-1, 2)
                 if rows[i+1].decode() not in source)


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
    registry_receipt: bytes
    prior_registry_receipt: bytes
    data_receipt: bytes


@lru_cache(maxsize=16)
def _immutable_checked(head, raw, registry_raw, data_raw):
    rows = _decode(raw)
    predecessor_owner, registered = _decode_registry(registry_raw)
    data_owner, data_rows = _decode_data(data_raw)
    current, before, registry_before, data_before = map(dict,
        _batch_blobs((head, BASE, REGISTRY_BASE, DATA_BASE)))
    source=source_adapter()
    _,source_before=source._metadata(ROOT)
    current={name:source_before.get(name,raw) if name in source.MEMBERS else raw for name,raw in current.items()}
    if sha(data_before[OWNER]) != data_owner:
        raise ValueError('Changed catalog data predecessor owner')
    for name, predecessor, successor in data_rows:
        if member_sha(name, current[name]) != successor:
            raise ValueError('Changed committed catalog data successor: '+name)
        if name in DATA_MODIFIED:
            if member_sha(name, data_before[name]) != predecessor:
                raise ValueError('Changed catalog data predecessor: '+name)
        elif name in data_before:
            raise ValueError('Catalog data addition exists in predecessor: '+name)
    if (sha(registry_before[OWNER]) != predecessor_owner
            or registry_before[RECEIPT] != current[RECEIPT]):
        raise ValueError('Changed catalog reservation predecessor owner or historical receipt')
    if set(current) != _pilot_members():
        raise ValueError('Missing/extra offline Playlist immutable member')
    if sha(current[REGISTRY_PRIOR_RECEIPT]) != REGISTRY_PRIOR_SHA256:
        raise ValueError('Changed immutable prior catalog reservation receipt')
    _regular_diff(_diff(head), _pilot_members(), exact=True)
    for metadata, name in _diff(head):
        status = metadata.split()[4]
        if status != (b'M' if name in before else b'A'):
            raise ValueError('Changed offline Playlist member admission: '+name)
    for name, predecessor, successor in registered:
        if member_sha(name, data_before[name] if name in DATA_MODIFIED else current[name]) != successor:
            raise ValueError('Changed committed catalog reservation successor: '+name)
        if name in REGISTRY_MODIFIED:
            if member_sha(name, registry_before[name]) != predecessor:
                raise ValueError('Changed catalog reservation predecessor: '+name)
        elif name in registry_before:
            raise ValueError('Catalog reservation addition exists in predecessor: '+name)
    for name, predecessor, successor in rows:
        historical = (registry_before[name] if name in REGISTRY_MODIFIED
                      else data_before[name] if name in DATA_MODIFIED else current[name])
        if member_sha(name, historical) != successor:
            raise ValueError('Changed committed offline Playlist successor: '+name)
        if name in MODIFIED:
            if name not in before or member_sha(name, before[name]) != predecessor:
                raise ValueError('Changed offline Playlist predecessor: '+name)
        elif name in before:
            raise ValueError('Offline Playlist addition exists in predecessor: '+name)
    if sha(raw) != sha(current[RECEIPT]):
        raise ValueError('Uncommitted offline Playlist receipt')
    if sha(registry_raw) != sha(current[REGISTRY_RECEIPT]):
        raise ValueError('Uncommitted catalog reservation receipt')
    if sha(data_raw) != sha(current[DATA_RECEIPT]):
        raise ValueError('Uncommitted catalog data successor receipt')
    return sha(current[OWNER])


def proof(root, head, *, selected=None):
    if Path(root).resolve() != ROOT.resolve():
        raise ValueError('Foreign offline Playlist checkout')
    if not isinstance(head, str) or re.fullmatch('[0-9a-f]{40}', head) is None:
        raise ValueError('Offline Playlist immutable inputs require a full SHA')
    source_adapter()._metadata(root)
    _ancestry(head)
    raw = regular(ROOT, RECEIPT).read_bytes()
    registry_raw = regular(ROOT, REGISTRY_RECEIPT).read_bytes()
    prior_registry_raw = regular(ROOT, REGISTRY_PRIOR_RECEIPT).read_bytes()
    if sha(prior_registry_raw) != REGISTRY_PRIOR_SHA256:
        raise ValueError('Changed physical prior catalog reservation receipt')
    data_raw = regular(ROOT, DATA_RECEIPT).read_bytes()
    rows = current_rows(raw, registry_raw, data_raw)
    immutable_owner = _immutable_checked(head, raw, registry_raw, data_raw)
    members = MODIFIED | ADDED | REGISTRY_ADDED | DATA_MODIFIED | DATA_ADDED
    selected = members if selected is None else frozenset(selected)
    if not selected <= members:
        raise ValueError('Foreign offline Playlist proof selection')
    for name, _, successor in rows:
        if name in selected and member_sha(name, regular(ROOT, name).read_bytes()) != source_adapter().selected_hash(name,successor):
            raise ValueError('Changed physical offline Playlist successor: '+name)
    owner = sha(regular(ROOT, OWNER).read_bytes())
    if owner != immutable_owner:
        raise ValueError('Uncommitted offline Playlist owner or receipt')
    if regular(ROOT, RECEIPT).read_bytes() != raw:
        raise ValueError('Offline Playlist receipt moved during verification')
    if regular(ROOT, REGISTRY_RECEIPT).read_bytes() != registry_raw:
        raise ValueError('Catalog reservation receipt moved during verification')
    if regular(ROOT, REGISTRY_PRIOR_RECEIPT).read_bytes() != prior_registry_raw:
        raise ValueError('Prior catalog reservation receipt moved during verification')
    if regular(ROOT, DATA_RECEIPT).read_bytes() != data_raw:
        raise ValueError('Catalog data successor receipt moved during verification')
    return _Proof(head, raw, owner, rows, tuple(sorted(selected)), registry_raw, prior_registry_raw, data_raw)


def _project(root, name, current, witness, *, owned=False):
    if Path(root).resolve() != ROOT.resolve():
        raise ValueError('Foreign offline Playlist historical projection')
    if name not in historical_members():
        return current
    current=source_adapter().historical_bytes(root,name,current)
    if name not in MODIFIED | DATA_MODIFIED:
        return current
    rows = current_rows(witness.receipt, witness.registry_receipt, witness.data_receipt)
    binding = next(row for row in rows if row[0] == name)
    _, predecessor, successor = binding
    # Each historical projection checks the leaf at the point of use. A caller
    # holding old bytes cannot substitute for current physical acceptance.
    physical = current if owned else regular(root, name).read_bytes()
    physical=source_adapter().historical_bytes(root,name,physical)
    if member_sha(name, physical) != successor:
        raise ValueError('Changed physical offline Playlist successor: '+name)
    if name in MODIFIED:
        old_row = next(row for row in _decode(witness.receipt) if row[0] == name)
        baseline, predecessor, historical_successor = BASE, old_row[1], old_row[2]
    else:
        baseline = DATA_BASE
        predecessor = historical_successor = next(row[1] for row in _decode_data(witness.data_receipt)[1] if row[0] == name)
    if member_sha(name, current) in {successor, historical_successor}:
        before = dict(_blobs(baseline))[name]
        if member_sha(name, before) != predecessor:
            raise ValueError('Changed offline Playlist predecessor object: '+name)
        return before
    # Older sealed projection layers continue to decide which prior views they
    # accept. This does not accept a physical rollback, proved above.
    return current


def historical_bytes(root, name, current):
    if name not in historical_members():
        return current
    from ci import phase5_m7_maintenance as m7
    owner = m7._ACTIVE.get()
    if (owner is not None and owner[1][0] and owner[2] == (str(m7.ROOT.absolute()), get_ident())
            and len(owner[0]) == 5):
        return _project(root, name, current, owner[0][4])
    with m7._invocation(root):
        return historical_bytes(root, name, current)


def selected_hash(name, expected):
    """Exact protected source and CI successors, with fresh physical checks."""
    if name in DATA_PROTECTED:
        source = _decode_data(regular(ROOT, DATA_RECEIPT).read_bytes())[1]
    elif name in PROTECTED_SUCCESSORS:
        source = _decode(regular(ROOT, RECEIPT).read_bytes())
    else:
        return source_adapter().selected_hash(name,expected)
    _, before, after = next(row for row in source if row[0] == name)
    if expected != before:
        return source_adapter().selected_hash(name,expected)
    # This public path can run outside an M7 owner. Share only its source entry
    # proof; retain both protected proofs, the fresh leaf and the source close.
    with source_adapter().invocation():
        from ci.phase5_m7_maintenance import _cohort_proof
        entry = _cohort_proof(ROOT, _protected_cohort_proof)
        owned = entry is not None
        if not owned:
            entry = _protected_cohort_proof(ROOT)
        # Even an invocation-owned cohort never substitutes for this leaf read.
        if member_sha(name,regular(ROOT,name).read_bytes()) != source_adapter().selected_hash(name,after):
            raise ValueError('Changed physical offline Playlist protected successor: '+name)
        if not owned and _protected_cohort_proof(ROOT) != entry:
            raise ValueError('Changed closing offline Playlist adoption successor')
        return source_adapter().selected_hash(name,after)


PROTECTED_SUCCESSORS = frozenset({'ci/phase4.py','ci/phase4_transactions.py','ci/people_unicode_maintenance.py',
    'create_defaults/bulk/tests/test_logo_workflow.py',
    'create_defaults/bulk/operator_publication.py',
    'create_defaults/bulk/planner.py','create_defaults/bulk/workers.py',
    'create_defaults/create_poster.py','create_defaults/validation_manifest.py'})


def _protected_cohort_proof(root):
    from ci.people_colorize_maintenance import _head
    return proof(root,_head(root),selected=PROTECTED_SUCCESSORS | DATA_PROTECTED)


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
