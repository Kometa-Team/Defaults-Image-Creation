"""Real native ADD and transport, with independently retained negative gates."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from create_defaults.bulk.common import BulkError
from create_defaults.phase6.fixtures import case
from create_defaults.phase6.playlist import REQUESTS, HERE, manifest, for_candidate

EXPORT = Path(os.environ.get('PHASE6_PILOT_EXPORT', 'config/phase6-playlist-evidence/native'))


@pytest.fixture
def single():
    with case(('avp',), export=EXPORT) as value:
        yield value


@pytest.fixture(scope='module')
def cohort():
    with case(REQUESTS, export=EXPORT) as value:
        yield value


def test_one_playlist_add_reaches_local_draft(single):
    assert single['report']['complete'] and single['report']['draft_verified']
    assert len(single['snapshot'].to_dict()['members']) == 1
    assert single['inputs'].phase3.to_dict()['chain_compatible']
    assert for_candidate(single['row'][1].candidate) is single['pilot']
    snapshot, current = single['selection'].verify()
    assert snapshot['operation_type'] == 'ADD' and current['definitions']
    assert single['report']['network_writes'] == 0
    assert single['synthetic_baseline_posters'] >= 36


@pytest.mark.cohort
def test_all_eight_playlist_additions_preserve_existing_posters(cohort):
    # CI's separate job requires the successful single-addition job first.
    value = cohort
    expected = {r['proposed']['persistent_identity'] for r in manifest()['requests']}
    assert set(value['snapshot'].to_dict()['members']) == expected
    assert set(value['requested']) == set(REQUESTS)
    assert value['report']['verified_batches'] == 1
    assert all(value['final_tree'][p] == row for p,row in value['baseline_tree'].items())
    assert len(value['final_tree']) == len(value['baseline_tree'])+8
    patch = json.loads(value['catalog'].document_json)
    assert patch['unchanged_jobs'] == 9
    assert patch['files']['genre.yml']['before_sha256'] == patch['files']['genre.yml']['after_sha256']
    assert patch['files']['profiles.yml']['before_sha256'] == patch['files']['profiles.yml']['after_sha256']
    assert value['historical_artwork_regenerated'] == 0
    assert not value['production_authorized']
    summary = dict(kind='phase6-eight-playlist-offline-pilot', success=True,
        source_head=value['source_head'],
        requests=list(REQUESTS), identities=sorted(expected), additions=8,
        synthetic_baseline_posters=value['synthetic_baseline_posters'],
        baseline_tree=value['baseline_tree'], final_tree=value['final_tree'],
        catalog_sha256=value['catalog'].sha256, snapshot_sha256=value['snapshot'].sha256,
        preparation_sha256=value['preparation'].sha256, report=value['report'],
        baseline_bytes_are_synthetic=True, historical_artwork_regenerated=0,
        real_approvals=0, production_authorized=False, publication_authorized=False)
    path=EXPORT.parent/'eight-request-result.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2)+'\n', encoding='utf8')


@pytest.mark.parametrize('attack', ['tampered', 'missing', 'replaced-by-directory'])
@pytest.mark.cohort
def test_staged_logo_is_fresh_on_each_call(cohort, attack):
    pilot = cohort['pilot']
    identity = cohort['snapshot'].to_dict()['members'][0]
    source = pilot.entry(identity)['names']['source']
    path = cohort['row'][0].config.asset_dir/source['path']
    raw = path.read_bytes()
    try:
        if attack == 'tampered':
            path.write_bytes(raw+b'changed')
        else:
            path.unlink()
            if attack == 'replaced-by-directory':path.mkdir()
        with pytest.raises((BulkError, ValueError, FileNotFoundError, IsADirectoryError, PermissionError)):
            pilot.entry(identity)
    finally:
        if path.is_dir():path.rmdir()
        path.write_bytes(raw)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source['sha256']


@pytest.mark.cohort
def test_playlist_update_stays_blocked(cohort):
    from create_defaults.bulk.lifecycle.operations import propose
    context = cohort['row'][1]
    with pytest.raises(BulkError, match='playlist_pilot_add_only'):
        propose(context.registry, before=context.candidate, candidate=context.candidate,
            identity='synthetic.operation.forbidden-update', operation='UPDATE')


@pytest.mark.cohort
def test_unrecorded_quality_findings_stay_blocked(cohort):
    from copy import deepcopy
    from create_defaults.phase6.playlist import source_quality_fixture
    context=cohort['row'][1]
    identity=cohort['snapshot'].to_dict()['members'][0]
    row=cohort['pilot'].rows()[identity]
    report=deepcopy(row['fixture_quality_review']['report'])
    report['diagnostics'].append('unreviewed_new_finding')
    with pytest.raises(BulkError, match='unreviewed_fixture_quality'):
        source_quality_fixture(cohort['row'][0].config, context.registry.view(),
            context.registry.view().entry(identity), report)


@pytest.mark.cohort
def test_operator_cannot_authorize_another_playlist_path(cohort):
    from copy import deepcopy
    from create_defaults.bulk.library_sources import sealed
    from create_defaults.bulk.common import fingerprint
    from create_defaults.bulk.operator_publication import approve, authorize
    binding = cohort['native'].binding.to_dict()
    policy = binding['authorization']['policy']
    candidate = deepcopy(binding['manifest'])
    candidate['members'][0]['destination'] = 'playlist/Unapproved addition.jpg'
    candidate = sealed({k:v for k,v in candidate.items() if k != 'sha256'})
    receipt = approve(candidate, policy, reviewer='bullmoose20', policy_hash=fingerprint(policy),
        manifest_hash=candidate['sha256'], decision_text='UNAPPROVED PATH REJECTION FIXTURE ONLY',
        accept_exceptions=True, allow_additions=[m['destination'] for m in candidate['members']])
    with pytest.raises(BulkError) as rejected:
        authorize(candidate, policy, receipt)
    assert rejected.value.code == 'offline_scope'


@pytest.mark.cohort
def test_closed_pilot_cannot_be_reused():
    from create_defaults.bulk.lifecycle.previews import CompositionTrial
    from create_defaults.phase4.tests.composition_samples import registry
    from create_defaults.phase6.playlist import OfflinePlaylistPilot
    with CompositionTrial() as trial:
        pilot = OfflinePlaylistPilot(trial, registry(trial))
        assert pilot.manifest_sha256
    with pytest.raises(BulkError, match='closed_or_foreign_trial'):
        pilot.rows()


@pytest.mark.cohort
def test_capability_cannot_adopt_a_live_root():
    from create_defaults.phase6.playlist import OfflinePlaylistPilot
    with pytest.raises(BulkError, match='owned_capability'):
        OfflinePlaylistPilot(HERE, object())


@pytest.fixture(scope='module')
def planned():
    from create_defaults.bulk.lifecycle.previews import CompositionTrial
    from create_defaults.phase4.tests.composition_samples import registry
    from create_defaults.phase6.fixtures import _definitions
    from create_defaults.phase6.playlist import OfflinePlaylistPilot
    with CompositionTrial() as trial:
        identities=registry(trial)
        pilot=OfflinePlaylistPilot(trial, identities)
        candidate=_definitions(trial,identities,REQUESTS)
        yield trial, identities, pilot, candidate


def test_preflight_every_cohort_job_uses_the_existing_single_item_validator(planned):
    from create_defaults.bulk.lifecycle.candidates import resolve_stable
    from create_defaults.bulk.contracts.expanded.validation import approved_english
    from create_defaults.phase6.playlist import validation_manifests
    trial, registry, pilot, candidate=planned
    data=candidate.data()
    resolution=resolve_stable(candidate.paths,candidate.profiles_path,registry.view())
    plans=validation_manifests(registry,trial.config,resolution,data['manifest'],approved_english())
    expected={r['proposed']['persistent_identity'] for r in manifest()['requests']}
    assert set(plans)==expected=={row['identity'] for row in data['validation']}
    for job in data['manifest']['jobs']:
        assert plans[job['poster_id']]['jobs']==[job]
        assert plans[job['poster_id']]['renderer']==data['manifest']['renderer']


def test_preflight_original_validator_still_rejects_other_new_items(planned):
    from create_defaults.bulk.lifecycle.candidates import resolve_stable
    from create_defaults.bulk.contracts.expanded.validation import approved_english, validate_candidate
    from create_defaults.bulk.contracts.models import Identity
    trial, registry, pilot, candidate=planned
    identity=candidate.posters[0]
    entry=registry.view().entry(identity)
    assigned=Identity.from_dict(dict(schema_version=1,kind='item-identity',id=identity,
        category='Playlist',semantic_member=None,**entry['names']))
    resolution=resolve_stable(candidate.paths,candidate.profiles_path,registry.view())
    with pytest.raises(BulkError) as rejected:
        validate_candidate(resolution,candidate.data()['manifest'],identity,approved_english(),
            fixture_only=True,config=trial.config,content=json.loads(candidate.content_json)[identity],
            assigned_identity=assigned)
    assert rejected.value.code == 'm5_membership'


def test_preflight_resealed_omitted_cohort_job_is_rejected(planned):
    from copy import deepcopy
    from create_defaults.bulk.common import fingerprint
    from create_defaults.bulk.lifecycle.candidates import resolve_stable
    from create_defaults.bulk.contracts.expanded.validation import approved_english
    from create_defaults.phase6.playlist import validation_manifests
    trial, registry, pilot, candidate=planned
    value=deepcopy(candidate.data()['manifest'])
    value['jobs'].pop()
    value['sha256']=fingerprint({k:v for k,v in value.items() if k!='sha256'})
    resolution=resolve_stable(candidate.paths,candidate.profiles_path,registry.view())
    with pytest.raises(BulkError):
        validation_manifests(registry,trial.config,resolution,value,approved_english())


def test_preflight_owner_checks_remain_fresh_without_repeating_trial_history(planned):
    from dataclasses import replace
    trial, registry, pilot, candidate=planned
    assert for_candidate(candidate) is pilot
    foreign=replace(candidate,config=replace(candidate.config,offline=False))
    with pytest.raises(BulkError,match='candidate_root'):
        for_candidate(foreign)
    marker=trial.root/'trial.json'
    raw=marker.read_bytes()
    try:
        marker.unlink()
        with pytest.raises(BulkError,match='closed_or_foreign_trial'):
            for_candidate(candidate)
    finally:
        marker.write_bytes(raw)
    identity=candidate.posters[0]
    logo=trial.config.asset_dir/registry.view().entry(identity)['names']['source']['path']
    raw=logo.read_bytes()
    try:
        logo.write_bytes(raw+b'changed')
        with pytest.raises(BulkError,match='staged_logo_bytes'):
            for_candidate(candidate)
    finally:
        logo.write_bytes(raw)
    assert for_candidate(candidate) is pilot
