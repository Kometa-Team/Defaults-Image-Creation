"""Lifetime-bound access to the eight provisional Playlist fixture requests.

This capability can only refer to a newly created CompositionTrial and its
native identity registry. It supplies technical evidence, never live approval.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from uuid import UUID
import weakref

from create_defaults.bulk.common import BulkError, canonical, confined, fingerprint, path_key, reject_links

HERE = Path(__file__).resolve().parent
REQUESTS = ('avp', 'babylon', 'bsg', 'gundam', 'jrrt', 'sao', 'stargate', 'wdu')
_OWNED = weakref.WeakKeyDictionary()
_PREPARED = weakref.WeakKeyDictionary()


def fail(reason):
    raise BulkError('p6_playlist_'+reason, 'Offline Playlist pilot rejected: '+reason)


def manifest():
    from create_defaults.bulk.contracts.models import decode_json
    path = reject_links(HERE/'PLAYLIST_PILOT_MANIFEST.json')
    raw = path.read_bytes()
    if len(raw) > 128_000:
        fail('manifest_size')
    value = decode_json(raw)
    if (set(value) != {'version', 'kind', 'baseline', 'simulation', 'fixture_approvals_only',
            'production_authorized', 'publication_authorized', 'activation_authorized', 'requests'}
            or value['version'] != 1 or value['kind'] != 'phase6-offline-playlist-pilot-manifest'
            or value['simulation'] is not True or value['fixture_approvals_only'] is not True
            or any(value[k] is not False for k in ('production_authorized', 'publication_authorized', 'activation_authorized'))
            or tuple(r['request'] for r in value['requests']) != REQUESTS):
        fail('manifest_scope')
    ids, paths = set(), set()
    for row in value['requests']:
        logo, proposed = row['logo'], row['proposed']
        label = row['request']
        if (logo['file'] != 'assets/'+label+'.png' or row['status'] != 'PROVISIONAL_FIXTURE_ONLY'
                or proposed['semantic_key'] != 'pilot-'+label
                or proposed['source_path'] != 'logos_playlist/'+label+'.png'
                or proposed['rendered_caption'] != 'TIMELINE ORDER'
                or proposed['fixture_background'] != '#123456'):
            fail('manifest_mapping')
        identity = proposed['persistent_identity']
        if re.fullmatch(r'playlist\.[0-9a-f]{32}', identity) is None or UUID(identity.split('.')[1]).version != 4 or identity in ids:
            fail('manifest_identity')
        ids.add(identity)
        name = proposed['display_name']+' (Timeline Order).jpg'
        if (proposed['local_path'] != 'defaults-en/playlist/'+name
                or proposed['public_path'] != 'playlist/'+name
                or path_key(proposed['public_path']) in paths):
            fail('manifest_mapping')
        paths.add(path_key(proposed['public_path']))
        asset = confined(HERE, logo['file'], must_exist=True)
        reject_links(asset)
        encoded = asset.read_bytes()
        if len(encoded) != logo['bytes'] or hashlib.sha256(encoded).hexdigest() != logo['sha256']:
            fail('logo_bytes')
    return value


@dataclass(frozen=True)
class _Context:
    trial: object
    registry: object
    manifest_sha256: str
    manifest_json: str


def _context(pilot):
    from create_defaults.bulk.lifecycle.previews import CompositionTrial
    from create_defaults.bulk.lifecycle.identities import IdentityRegistry
    if type(pilot) is not OfflinePlaylistPilot or pilot not in _OWNED:
        fail('owned_capability')
    context = _OWNED[pilot]
    trial, registry = context.trial, context.registry
    if (type(trial) is not CompositionTrial or trial._closed or type(registry) is not IdentityRegistry
            or registry.operations.root != trial.config.cache_dir or not trial.config.offline
            or not (trial.root/'trial.json').is_file()):
        fail('closed_or_foreign_trial')
    for name in ('asset_dir', 'cache_dir', 'workspace_dir', 'output_dir'):
        if not reject_links(getattr(trial.config, name)).resolve().is_relative_to(trial.root):
            fail('foreign_root')
    if fingerprint(manifest()) != context.manifest_sha256:
        fail('manifest_changed')
    return context


def _rows(context):
    # Pure projection of this invocation's freshly authenticated manifest.
    value = json.loads(context.manifest_json)
    return {r['proposed']['persistent_identity']: r for r in value['requests']}


def _content(context, identity):
    rows = _rows(context)
    if identity not in rows:
        fail('unselected_identity')
    row = rows[identity]
    p = row['proposed']
    source = dict(path='logos_playlist/Fixture '+row['request']+'.png', sha256=row['logo']['sha256'])
    actual = confined(context.trial.config.asset_dir, source['path'], must_exist=True)
    reject_links(actual)
    if hashlib.sha256(actual.read_bytes()).hexdigest() != source['sha256']:
        fail('staged_logo_bytes')
    return dict(display_name=p['display_name'], source=source,
        background_proposal=p['fixture_background'], content_type='timeline-order')


def _entry(context, identity, view=None):
    row = _rows(context).get(identity)
    if row is None:
        fail('unselected_identity')
    p = row['proposed']
    entry = (context.registry.view() if view is None else view).entry(identity)
    content = _content(context, identity)
    names = dict(display_name=p['display_name'], rendered_caption='TIMELINE ORDER', source=content['source'],
        local_path=p['local_path'], public_path=p['public_path'])
    if (entry['category'] != 'Playlist' or entry['variant'] != 'timeline-order'
            or entry['origin'] != 'assigned' or entry['revision'] != 1 or entry['tombstone_sha256'] is not None
            or entry['semantic'] != dict(parent=None, key=p['semantic_key'], role='single', language='en')
            or entry['names'] != names or entry['original_names'] != names or entry['aliases']):
        fail('identity_mapping')
    return entry


def _definitions(context, definitions):
    if not definitions or not set(definitions) <= set(_rows(context)):
        fail('definition_membership')
    from create_defaults.bulk.contracts.playlist.validation import PlaylistBoundary, CONTRACT_SHA256, REGISTRY_SHA256, M2_SHA256
    from create_defaults.bulk.contracts.models import Identity
    boundary = PlaylistBoundary.load(contract_sha256=CONTRACT_SHA256, registry_sha256=REGISTRY_SHA256, adoption_sha256=M2_SHA256)
    view = context.registry.view()
    for identity, definition in definitions.items():
        entry = _entry(context, identity, view)
        assigned = Identity.from_dict(dict(schema_version=1, kind='item-identity', id=identity,
            category='Playlist', semantic_member=None, **entry['names']))
        boundary.validate_proposed_definition(assigned, _content(context, identity), definition,
            source_root=context.trial.config.asset_dir)


class OfflinePlaylistPilot:
    __slots__ = ('__weakref__',)

    def __init__(self, trial, registry):
        from create_defaults.bulk.lifecycle.previews import CompositionTrial
        from create_defaults.bulk.lifecycle.identities import IdentityRegistry
        if (type(trial) is not CompositionTrial or trial._closed or type(registry) is not IdentityRegistry
                or registry.operations.root != trial.config.cache_dir):
            fail('owned_capability')
        if any(c.registry.operations.root == registry.operations.root for c in _OWNED.values()):
            fail('duplicate_owner')
        value = manifest()
        _OWNED[self] = _Context(trial, registry, fingerprint(value), canonical(value).decode())
        _context(self)

    @property
    def manifest_sha256(self):
        return _context(self).manifest_sha256

    def require_trial(self, trial):
        if _context(self).trial is not trial:
            fail('foreign_trial')

    def rows(self):
        return _rows(_context(self))

    def content(self, identity):
        return _content(_context(self), identity)

    def entry(self, identity):
        return _entry(_context(self), identity)

    def require_definitions(self, definitions):
        _definitions(_context(self), definitions)

    def require_request(self, request, definition):
        context = _context(self)
        if (request.package.contract.to_dict()['category'] != 'Playlist' or request.variant != 'timeline-order'
                or definition['languages'] != ['en'] or request.identity not in _rows(context)):
            fail('phase3_scope')
        _definitions(context, {request.identity: definition})
        # The resolver still proves real current file bytes. Its files must be
        # owned by this same temporary trial, not a caller-supplied live root.
        for _, path, _ in request.resolution.source_pins:
            if not reject_links(path).resolve().is_relative_to(context.trial.root):
                fail('phase3_source_root')
        return context.manifest_sha256


def validation_manifests(registry, config, resolution, manifest, translations):
    """Project a complete owned cohort into existing one-item validation plans.

    This returns plans, not approvals. The candidate builder must still run the
    unchanged M3 validator for every job. Each actual replayed job must equal its
    member of the full plan. Unowned selections retain the original rejection.
    """
    if len(manifest['jobs']) <= 1:
        return {}
    for pilot, context in tuple(_OWNED.items()):
        if context.registry is not registry:
            continue
        context = _context(pilot)
        if config != context.trial.config:
            fail('candidate_root')
        from create_defaults.bulk.planner import validate_manifest
        from create_defaults.bulk.contracts.expanded.resolution import plan
        validate_manifest(manifest)
        selected = {j['poster_id'] for j in manifest['jobs']}
        data = resolution.data()
        if (len(selected) != len(manifest['jobs']) or not selected <= set(_rows(context))
                or set(data['expanded']) != selected or data['families']):
            fail('validation_cohort_membership')
        view, result = registry.view(), {}
        for job in manifest['jobs']:
            identity = job['poster_id']
            _entry(context, identity, view)
            if (job['kind'] != 'poster' or job['language'] != 'en'
                    or resolution.definition(identity)['category'] != 'Playlist'):
                fail('validation_cohort_membership')
            one = plan(resolution, translations, config=config,
                categories=manifest['selection']['categories'], posters=[identity], languages=['en'])
            if canonical(one['jobs']) != canonical([job]) or one['renderer'] != manifest['renderer']:
                fail('validation_cohort_job')
            result[identity] = one
        return result
    return {}


def for_candidate(candidate):
    from create_defaults.bulk.lifecycle.candidates import PosterCandidate
    if type(candidate) is not PosterCandidate:
        return None
    for pilot, context in tuple(_OWNED.items()):
        if context.registry is candidate.registry:
            context = _context(pilot)
            if candidate.config != context.trial.config:
                fail('candidate_root')
            # _context already proves the exact live trial/config/root owner.
            # _definitions below checks every exact Fixture source against one
            # freshly replayed registry view. Trial.require would replay that
            # same registry history again for each output. Keep its original
            # composition call sites; don't duplicate it in this pilot helper.
            definitions = candidate.data()['effective_definitions']
            if (set(definitions) != set(candidate.graph.index().outputs) or candidate.data()['families']
                    or json.loads(candidate.content_json) != {i:_content(context, i) for i in definitions}):
                fail('candidate_membership')
            _definitions(context, definitions)
            if _context(pilot) is not context:
                fail('candidate_owner_changed')
            return pilot
    return None


def require_phase3(pilot, request, definition):
    if type(pilot) is not OfflinePlaylistPilot or pilot not in _OWNED:
        fail('owned_capability')
    return pilot.require_request(request, definition)


def preparation_membership(value):
    """Closed read-only DTO shape; live capability checks remain in planning.

    Parsing an immutable value never creates an owner, decision or destination.
    NativeSelection and the original transport must still revalidate the live
    owned trial and exact review before any local fixture write.
    """
    rows = {r['proposed']['persistent_identity']:r for r in manifest()['requests']}
    if (not set(value['required_members']) <= set(rows)
            or set(value['source']['files']) != {'genre.yml','playlist.yml','profiles.yml','index-v1.json'}
            or value['source']['simulation'] is not True or value['source']['production_authorized'] is not False):
        return False
    return all(m['destination'] == rows[m['identity']]['proposed']['public_path']
        and m['previous_sha256'] is None and m['previous_git_blob'] == '0'*40 for m in value['members'])


def register_operator_preparation(pilot, preparation, selection, catalog, target):
    """Retain the actual native planner result for this trial's lifetime only."""
    from create_defaults.bulk.lifecycle.preparation_models import Preparation
    from create_defaults.bulk.lifecycle.publication_preparation import NativeSelection, OfflineDestination
    from create_defaults.bulk.lifecycle.catalog_preparation import CatalogPatch
    context = _context(pilot)
    if (type(preparation) is not Preparation or type(selection) is not NativeSelection
            or type(catalog) is not CatalogPatch or type(target) is not OfflineDestination
            or selection.registry is not context.registry or catalog.source.pilot is not pilot
            or target.pilot is not pilot or catalog.source.trial is not context.trial
            or target.trial is not context.trial or not preparation_membership(preparation.to_dict())):
        fail('operator_preparation')
    _PREPARED[preparation] = (weakref.ref(pilot), catalog.sha256)


def operator_membership(policy, members):
    """Narrow exception inside the original test-only M6 operator policy.

    No new policy flag or destination selector can mint this binding. Every
    actual stage/draft still runs the unchanged M6 current review/CAS/byte/tree
    guards; this function only recognizes the original native planner result.
    """
    for preparation, (reference, catalog_sha256) in tuple(_PREPARED.items()):
        if preparation.sha256 != policy.get('preparation_sha256'):
            continue
        pilot = reference()
        if pilot is None:
            return False
        context = _context(pilot)
        value = preparation.to_dict()
        wanted_policy = dict(mode='phase5-m6-offline-draft-transport',
            preparation_sha256=preparation.sha256, catalog_sha256=catalog_sha256,
            technical_batch_limits={k:value['plan'][k] for k in ('max_files','max_bytes')})
        expected = {m['destination']:m for m in value['members'] if m['previous_sha256'] is None}
        if (policy != wanted_policy or len(members) != len(expected)
                or {m['destination'] for m in members} != set(expected)):
            return False
        keys = ('source','size','sha256','git_blob','previous_sha256','previous_git_blob')
        view = context.registry.view()
        for member in members:
            original = expected[member['destination']]
            _entry(context, original['identity'], view)
            if (member.get('kind') != 'poster' or member.get('rename_from')
                    or member.get('context_sha256') != preparation.sha256
                    or any(member.get(k) != original[k] for k in keys)):
                return False
        return True
    return False


def source_quality_fixture(config, view, entry, report):
    """Acknowledge only recorded findings on exact owned fixture bytes.

    Findings stay in native evidence. This cannot establish real transparency,
    quality, intentional-background approval or publication authority.
    """
    for pilot, context in tuple(_OWNED.items()):
        if (config.asset_dir != context.trial.config.asset_dir
                or config.cache_dir != context.trial.config.cache_dir):
            continue
        context = _context(pilot)
        # This read-only check does not adopt or write outputs. The existing
        # archive verifier mints its own separate replay output temporary root;
        # actual render output confinement remains CompositionTrial's job.
        if not config.offline:
            fail('foreign_quality_root')
        for name in ('workspace_dir',):
            if not reject_links(getattr(config, name)).resolve().is_relative_to(context.trial.root):
                fail('foreign_quality_root')
        identity = entry['id']
        current_view = context.registry.view()
        if entry != _entry(context, identity, current_view) or view.snapshot.sha256 != current_view.snapshot.sha256:
            fail('quality_identity')
        row = _rows(context)[identity]
        review = row['fixture_quality_review']
        if (set(review) != {'kind', 'reviewer', 'decision', 'report', 'report_sha256', 'simulation',
                'real_approval', 'production_authorized', 'publication_authorized'}
                or review['kind'] != 'offline-source-quality-fixture'
                or review['reviewer'] != 'synthetic.actor.source-quality'
                or review['decision'] != 'ACKNOWLEDGED_FOR_FIXTURE_ONLY'
                or review['simulation'] is not True
                or any(review[k] is not False for k in ('real_approval','production_authorized','publication_authorized'))
                or report != review['report'] or fingerprint(report) != review['report_sha256']
                or report['sha256'] != row['logo']['sha256'] or report['integrity'] != 'valid'
                or report['mode'] != 'RGBA' or report['alpha_min'] != 0 or not report['clear_pixels']
                or set(report['default_transparency_blockers']) - {'rectangular_alpha_background_not_proven_transparent'}):
            fail('unreviewed_fixture_quality')
        return {k:v for k,v in review.items() if k != 'report'}
    return None
