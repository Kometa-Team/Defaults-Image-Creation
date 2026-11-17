"""Native Playlist ADD -> review -> catalog -> local draft; fixture approvals only."""
from contextlib import contextmanager
from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
from unittest.mock import patch
from uuid import UUID

from PIL import Image
import yaml

from create_defaults.bulk.common import canonical, fingerprint
from create_defaults.bulk.contracts.models import Identity
from create_defaults.bulk.contracts.playlist.validation import PlaylistBoundary, CONTRACT_SHA256, REGISTRY_SHA256, M2_SHA256
from create_defaults.bulk.lifecycle.previews import CompositionTrial
from create_defaults.bulk.lifecycle.candidates import poster_candidate
from create_defaults.bulk.lifecycle import operations, apply
from create_defaults.bulk.lifecycle.review import ReviewArchive, decision
from create_defaults.bulk.lifecycle.catalog_preparation import OwnedCatalog, prepare_catalog, git
from create_defaults.bulk.lifecycle.publication_preparation import NativeSelection, OfflineDestination, plan_operation, tree
from create_defaults.bulk.lifecycle.draft_transport import propose as draft_propose, bind, run_offline, _context as draft_context
from create_defaults.bulk.operator_publication import approve
from create_defaults.phase4.tests import composition_samples as cs, review_samples as rs
from .playlist import OfflinePlaylistPilot, manifest, HERE


def phase3_inputs(row, pilot):
    """Use original P3 loader/source/destination/consumption engines, not a waiver."""
    from create_defaults.bulk.contracts.translation_preflight import PosterRequest
    from create_defaults.bulk.contracts.evidence_consumption import consume, RequestContext
    from create_defaults.bulk.lifecycle.basis import historical_basis
    from create_defaults.bulk.lifecycle.candidates import resolve_stable
    from create_defaults.bulk.lifecycle.evidence import ReviewInputs, operation_payload
    from create_defaults.phase3.tests.consumption_samples import input_for, assemble
    _, ctx, composition, _ = row
    candidate, view = ctx.candidate, ctx.registry.view()
    resolution = resolve_stable(candidate.paths, candidate.profiles_path, view)
    snapshot, items, policy = rs.english_snapshot(), [], None
    for identity in composition.to_dict()['required_members']:
        entry = view.entry(identity)
        package = historical_basis().package('Playlist')
        outputs = [dict(id=identity, identity_sha256=fingerprint(entry),
            local_path=entry['names']['local_path'], public_path=entry['names']['public_path'])]
        request = PosterRequest(resolution, identity, package, package.contract.sha256,
            package.rules.sha256, 'timeline-order', canonical(outputs),
            candidate.graph.index().outputs[identity]['context_sha256'], offline_playlist_pilot=pilot)
        item, selected = input_for(request, snapshot=snapshot, language='en', context_label='phase6-owned-playlist-fixture')
        if policy is not None and policy != selected:
            raise AssertionError('Playlist cohort must share one exact language policy')
        policy = selected
        items.append(item)
    values = assemble(tuple(items), policy, graph=candidate.graph)
    operation = composition.to_dict()['operation']
    context = values['request_context'].to_dict()
    context.update(id=operation['id'], revision=operation['revision'], request_payload_sha256=operation_payload(composition))
    context = RequestContext.from_dict(context)
    values.update(request_context=context, expected_request_context_sha256=context.sha256)
    attestation = consume(**values)
    return ReviewInputs(ctx, composition.sha256, attestation, attestation.sha256, values)


def _definitions(trial, registry, labels):
    from create_defaults.bulk.tests.test_playlist_contract import proposed_definition
    boundary = PlaylistBoundary.load(contract_sha256=CONTRACT_SHA256,
        registry_sha256=REGISTRY_SHA256, adoption_sha256=M2_SHA256)
    definitions, content = [], {}
    for row in manifest()['requests']:
        if row['request'] not in labels:
            continue
        proposed, logo = row['proposed'], row['logo']
        source = trial.stage('logos_playlist/Fixture '+row['request']+'.png', (HERE/logo['file']).read_bytes())
        names = dict(display_name=proposed['display_name'], rendered_caption='TIMELINE ORDER', source=source,
            local_path=proposed['local_path'], public_path=proposed['public_path'])
        # Determinism is fixture-only. IdentityRegistry.allocate is still the
        # real reservation API; no production registry is imported or changed.
        with patch('create_defaults.bulk.lifecycle.identities.uuid4', return_value=UUID(proposed['persistent_identity'].split('.')[1])):
            entry = registry.allocate(category='Playlist', semantic=dict(parent=None,
                key=proposed['semantic_key'], role='single', language='en'), variant='timeline-order',
                names=names, token='phase6-'+row['request'], expected=registry.view().head)
        item = Identity.from_dict(dict(schema_version=1, kind='item-identity', id=entry['id'],
            category='Playlist', semantic_member=None, **names))
        content[item.to_dict()['id']] = dict(display_name=names['display_name'], source=source,
            background_proposal=proposed['fixture_background'], content_type='timeline-order')
        definition = proposed_definition(boundary, content[entry['id']], item)
        filename = PurePosixPath(names['public_path']).name
        definition['output']['filename'] = filename
        definition['composer']['out_name'] = PurePosixPath(filename).stem
        definitions.append(definition)
    path, profiles = trial.root/'candidate.yml', trial.root/'profiles.yml'
    path.write_text(yaml.safe_dump(dict(schema_version=1, category='Playlist', definitions=definitions)), encoding='utf8')
    profiles.write_text(yaml.safe_dump(dict(schema_version=1, profiles={})), encoding='utf8')
    return poster_candidate(registry, expected=registry.view().head, paths=[path], profiles_path=profiles,
        posters=sorted(content), content=content, config=trial.config)


def existing_fixture_posters():
    """Synthetic JPEG bytes at existing paths; never regenerate real artwork."""
    from create_defaults.bulk.lifecycle.basis import historical_basis
    basis = historical_basis()
    output = BytesIO()
    Image.new('RGB', (1, 1), (17, 29, 41)).save(output, format='JPEG')
    result = {}
    for category in ('Genre', 'Playlist'):
        _, members = basis.package(category).data()
        for identity in members:
            path = basis.entry(identity)['names']['public_path']
            if path is not None:
                result[path] = output.getvalue()
    return result


def verify_native_byte_responses(native, report):
    """Reuse original streaming RemoteBytes against actual local Git blobs."""
    from urllib.parse import unquote
    import requests
    from create_defaults.bulk.library_stage import RemoteBytes
    members = native.preparation.to_dict()['members']
    paths = {m['destination'] for m in members}
    prefix = 'https://raw.githubusercontent.com/Kometa-Team/Default-Images/'+report['head']+'/'
    class Response:
        def __init__(self, raw):self.raw=raw
        def __enter__(self):return self
        def __exit__(self, *args):pass
        def raise_for_status(self):pass
        def iter_content(self, size):
            for offset in range(0,len(self.raw),size):yield self.raw[offset:offset+size]
    def local_get(session, url, **kwargs):
        if not url.startswith(prefix) or kwargs != dict(stream=True, timeout=(15,90), allow_redirects=False):
            raise AssertionError('Unowned native-byte request')
        path=unquote(url[len(prefix):])
        if path not in paths:raise AssertionError('Unexpected native-byte member')
        return Response(git(native.root/'remote.git','show',report['head']+':'+path))
    with patch.object(requests.Session, 'get', local_get):
        RemoteBytes(native.root/'actual-native-byte-responses', native.binding.to_dict()['plan'])(report['head'], members)


@contextmanager
def case(labels, *, export=None):
    labels = tuple(labels)
    allowed = {r['request'] for r in manifest()['requests']}
    if not labels or len(labels) != len(set(labels)) or not set(labels) <= allowed:
        raise ValueError('Exact nonempty pilot request subset required')
    with CompositionTrial() as trial:
        registry = cs.registry(trial)
        pilot = OfflinePlaylistPilot(trial, registry)
        candidate = _definitions(trial, registry, labels)
        context = operations.propose(registry, before=None, candidate=candidate,
            identity='synthetic.operation.phase6-playlist', operation='ADD')
        evidence = operations.preview(context, trial)
        row = (trial, context, evidence, ())
        inputs = phase3_inputs(row, pilot)
        authority = rs.authority(row)
        archive = ReviewArchive.create(trial.config.cache_dir)
        review_id = 'synthetic.review.phase6-playlist'
        state = archive.start(review_id, submitter=rs.SUBMITTER, inputs=inputs)
        bundle = archive.read(review_id, expected_sha256=state.sha256)[1]
        decisions = []
        for action, actor, role in [('confirm', rs.SUBMITTER, 'submitter'), ('approve', rs.MAINTAINER, 'maintainer')]:
            record = decision(bundle, state, actor=actor, action=action)
            authority.authorize(record, actor=actor, role=role)
            state = archive.decide(record, expected_sha256=state.sha256, inputs=inputs, authority=authority)
            decisions.append(record)
        expected = {identity:None for identity in candidate.graph.index().outputs}
        transaction = operations.Transaction(inputs, review_id, state.sha256, canonical(expected).decode())
        snapshot = transaction.prepare()
        committed = apply.commit_synthetic(transaction, expected_snapshot_sha256=snapshot.sha256, authority=authority)
        if not committed['isolated_committed'] or committed['publication_authorized']:
            raise AssertionError('Only isolated synthetic commit is allowed')
        selection = NativeSelection(registry, inputs, snapshot.sha256, authority)
        source = OwnedCatalog(trial, offline_playlist_pilot=pilot)
        desired = operations.payload(snapshot.to_dict()['proposed_json'])['effective_definitions']
        catalog = prepare_catalog(source, desired)
        existing = existing_fixture_posters()
        destination = OfflineDestination(trial, existing=existing, offline_playlist_pilot=pilot)
        preparation = plan_operation(selection, catalog, destination, max_files=len(labels))
        proposal = draft_propose(preparation, selection, catalog, destination)
        receipt = approve(proposal['manifest'], proposal['policy'], reviewer='bullmoose20',
            policy_hash=fingerprint(proposal['policy']), manifest_hash=proposal['manifest']['sha256'],
            decision_text='PHASE 6 ISOLATED FIXTURE ONLY; NO REAL APPROVAL OR PUBLICATION AUTHORITY',
            accept_exceptions=True, allow_additions=[m['destination'] for m in proposal['manifest']['members']])
        protocol = bind(preparation, selection, catalog, destination, receipt)
        native = draft_context(protocol)
        initial = tree(destination.root, destination.base['head'])
        report = run_offline(protocol)
        final = tree(native.root/'remote.git', report['head'])
        expected_paths = {m['destination'] for m in preparation.to_dict()['members']}
        if (not report['complete'] or not report['draft_verified'] or report['network_writes'] != 0
                or any(report[k] for k in ('publication_authorized','operation_complete','remote_writes_authorized','ready','active'))
                or any(final.get(path) != member for path,member in initial.items())
                or set(final)-set(initial) != expected_paths):
            raise AssertionError('Incomplete or non-preserving offline draft')
        if git(native.root/'remote.git', 'rev-parse', 'refs/heads/master').decode().strip() != destination.base['head']:
            raise AssertionError('Offline base branch moved')
        verify_native_byte_responses(native, report)
        value = dict(row=row, inputs=inputs, authority=authority, archive=archive, state=state,
            bundle=bundle, decisions=decisions, snapshot=snapshot, pilot=pilot, transaction=transaction,
            source=source, selection=selection, catalog=catalog, destination=destination,
            preparation=preparation, protocol=protocol, native=native, report=report,
            baseline_tree=initial, final_tree=final, synthetic_baseline_posters=len(existing),
            requested=labels, historical_artwork_regenerated=0, production_authorized=False)
        if export is not None:
            from create_defaults.phase5.m6_tests.helpers import export_native
            old = os.environ.get('M6_NATIVE_EXPORT')
            os.environ['M6_NATIVE_EXPORT'] = str(Path(export).resolve())
            try:
                export_native(value, protocol, report, name='single' if len(labels)==1 else 'eight')
            finally:
                if old is None:os.environ.pop('M6_NATIVE_EXPORT', None)
                else:os.environ['M6_NATIVE_EXPORT'] = old
        yield value
