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


@pytest.fixture(scope='module')
def single():
    with case(('avp',), export=EXPORT) as value:
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


def test_all_eight_playlist_additions_preserve_existing_posters(single):
    # Explicit dependency: prove one actual addition before exercising all eight.
    assert single['report']['draft_verified']
    with case(REQUESTS, export=EXPORT) as value:
        expected = {r['proposed']['persistent_identity'] for r in manifest()['requests']}
        assert set(value['snapshot'].to_dict()['members']) == expected
        assert set(value['requested']) == set(REQUESTS)
        assert value['partial']['verified_batches'] == 1 and not value['partial']['complete']
        assert not value['partial']['draft_verified']
        assert value['report']['verified_batches'] == 4
        assert all(value['final_tree'][p] == row for p,row in value['baseline_tree'].items())
        assert len(value['final_tree']) == len(value['baseline_tree'])+8
        patch = json.loads(value['catalog'].document_json)
        assert patch['unchanged_jobs'] == 9
        assert patch['files']['genre.yml']['before_sha256'] == patch['files']['genre.yml']['after_sha256']
        assert patch['files']['profiles.yml']['before_sha256'] == patch['files']['profiles.yml']['after_sha256']
        assert value['historical_artwork_regenerated'] == 0
        assert not value['production_authorized']
        summary = dict(kind='phase6-eight-playlist-offline-pilot', success=True,
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
def test_staged_logo_is_fresh_on_each_call(single, attack):
    pilot = single['pilot']
    identity = single['snapshot'].to_dict()['members'][0]
    source = pilot.entry(identity)['names']['source']
    path = single['row'][0].config.asset_dir/source['path']
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


def test_playlist_update_stays_blocked(single):
    from create_defaults.bulk.lifecycle.operations import propose
    context = single['row'][1]
    with pytest.raises(BulkError, match='playlist_pilot_add_only'):
        propose(context.registry, before=context.candidate, candidate=context.candidate,
            identity='synthetic.operation.forbidden-update', operation='UPDATE')


def test_unrecorded_quality_findings_stay_blocked(single):
    from copy import deepcopy
    from create_defaults.phase6.playlist import source_quality_fixture
    context=single['row'][1]
    identity=single['snapshot'].to_dict()['members'][0]
    row=single['pilot'].rows()[identity]
    report=deepcopy(row['fixture_quality_review']['report'])
    report['diagnostics'].append('unreviewed_new_finding')
    with pytest.raises(BulkError, match='unreviewed_fixture_quality'):
        source_quality_fixture(single['row'][0].config, context.registry.view(),
            context.registry.view().entry(identity), report)


def test_closed_pilot_cannot_be_reused():
    from create_defaults.bulk.lifecycle.previews import CompositionTrial
    from create_defaults.phase4.tests.composition_samples import registry
    from create_defaults.phase6.playlist import OfflinePlaylistPilot
    with CompositionTrial() as trial:
        pilot = OfflinePlaylistPilot(trial, registry(trial))
        assert pilot.manifest_sha256
    with pytest.raises(BulkError, match='closed_or_foreign_trial'):
        pilot.rows()


def test_capability_cannot_adopt_a_live_root():
    from create_defaults.phase6.playlist import OfflinePlaylistPilot
    with pytest.raises(BulkError, match='owned_capability'):
        OfflinePlaylistPilot(HERE, object())
