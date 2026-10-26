"""T02/T04/T11/T15/T17/T18/T21: encoded ADD→UPDATE→RENAME→DELETE history."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import pytest

from create_defaults.bulk.common import fingerprint
from create_defaults.bulk.lifecycle import mappings
from create_defaults.bulk.lifecycle.previews import CompositionArchive
from create_defaults.bulk.lifecycle.recovery import recover
from create_defaults.phase4.tests.samples import append, sample
from create_defaults.phase4.m7_tests.helpers import (
    commit, denied_authority, prepare, preserved_snapshots,
)


def test_complete_lifecycle_preserves_identity_encoded_epochs_and_unrelated_record(m7_case):
    case = m7_case
    trial, context, _, _ = case['row']
    registry = context.registry
    identity = case['update_snapshot'].to_dict()['members'][0]
    original = case['add_snapshot'].to_dict()['entries'][identity]
    updated = registry.view().entry(identity)
    add_art = case['add_snapshot'].to_dict()['artwork'][identity]
    update_art = case['update_snapshot'].to_dict()['artwork'][identity]
    assert add_art['sha256'] != update_art['sha256']
    assert updated['id'] == original['id'] and updated['semantic'] == original['semantic']
    assert updated['original_names'] == original['original_names']

    # Existing mandatory M5 disjoint-native tests own the separately rendered
    # unrelated-artwork proof. Here an independent real M1 record exercises the
    # additional cross-milestone preservation boundary without a redundant render.
    control = sample(registry.operations, name='m7-unrelated-record', subjects=('unrelated',))
    append(registry.operations, control)
    archive = CompositionArchive(trial.config.cache_dir, readonly=True)
    review_history = case['archive'].history()

    renamed = prepare(case, name='fixture')
    result, pair = commit(case, renamed)
    denied_authority(result)
    assert mappings.commit_synthetic(registry, renamed, authority=case['authority'], decisions=pair)['retry']
    rename_state = mappings.recover(registry)
    assert rename_state['active_members'] == [identity]
    assert rename_state['retained'][identity]['artwork'] == update_art
    assert registry.view().entry(identity)['names']['rendered_caption'] == updated['names']['rendered_caption']

    retired = prepare(case, delete=True, suffix='-delete')
    result, pair = commit(case, retired)
    denied_authority(result)
    assert mappings.commit_synthetic(registry, retired, authority=case['authority'], decisions=pair)['retry']
    final = mappings.recover(registry)
    denied_authority(final)
    assert final['active_members'] == []
    assert final['retained'][identity]['artwork'] == update_art
    assert registry.operations.history(control.to_dict()['id']) == (control,)
    assert case['archive'].history() == review_history
    preserved_snapshots(case)
    assert archive.read_bytes(add_art['object_sha256']) != archive.read_bytes(update_art['object_sha256'])
    assert sha256(archive.read_bytes(add_art['object_sha256'])).hexdigest() == add_art['sha256']
    assert sha256(archive.read_bytes(update_art['object_sha256'])).hexdigest() == update_art['sha256']

    entry = registry.view().entry(identity)
    assert entry['tombstone_sha256'] == final['tombstones'][identity]
    # Existing mandatory M6/M2 tombstone-reuse tests exercise allocation
    # rejection. The integrated chain verifies both old spellings remain
    # recorded in the same immutable tombstone/aliases after the material UPDATE.
    occupied = {alias['value'] for alias in entry['aliases'] if alias['namespace'] == 'public'}
    occupied.add(entry['names']['public_path'])
    assert original['names']['public_path'] in occupied
    assert renamed.to_dict()['after'][identity]['names']['public_path'] in occupied

    # Read-only cold restart is distinct from reconstructing an authority
    # capability. Archived synthetic decisions cannot authenticate a new process.
    code = '''
import json,sys
from unittest.mock import patch
from create_defaults.bulk.lifecycle.identities import IdentityRegistry
from create_defaults.bulk.lifecycle.mappings import recover
from create_defaults.bulk.lifecycle.package_e import SidecarStore
with patch.object(SidecarStore,'__init__',side_effect=AssertionError('writer opened on recovery')):
 print(json.dumps(recover(IdentityRegistry(sys.argv[1],sys.argv[2])),sort_keys=True))
'''
    child = subprocess.run([sys.executable, '-c', code, str(registry.operations.root), registry.identity],
                            text=True, capture_output=True, timeout=300)
    assert child.returncode == 0, child.stderr
    assert json.loads(child.stdout) == final

    from ci.validation import identity as execution_identity, write
    proof = dict(**execution_identity(), kind='phase4-m7-native-sequence',
        operations=['ADD', 'UPDATE', 'RENAME', 'DELETE'], permanent_id=identity,
        original_names=original['names'], renamed_names=renamed.to_dict()['after'][identity]['names'],
        add_snapshot_sha256=case['add_snapshot'].sha256,
        update_snapshot_sha256=case['update_snapshot'].sha256,
        add_artwork=add_art, update_artwork=update_art,
        unrelated_record_sha256=control.sha256, unrelated_record_preserved=True,
        tombstone_sha256=entry['tombstone_sha256'], active_members=final['active_members'],
        mapping_plans=final['plans'], cold_restart_verified=True, exact_retries_verified=True,
        history_retained=True, isolated_only=True,
        **{key: final[key] for key in ('authenticated', 'operation_accepted', 'applied',
            'artwork_approved', 'contract_approved', 'ready', 'active', 'production_enforcement', 'publication_authorized')})
    proof['sha256'] = fingerprint(proof)
    destination = Path('config/ci-validation/m7/sequence')
    artwork = destination/'artwork'
    artwork.mkdir(parents=True, exist_ok=True)
    for name, member in (('add', add_art), ('update', update_art)):
        (artwork/(name+'.jpg')).write_bytes(archive.read_bytes(member['object_sha256']))
    write(destination/'m7-native-proof.json', proof)


def test_compensation_after_update_and_rename_appends_history(m7_case):
    case = m7_case
    registry = case['row'][1].registry
    identity = case['update_snapshot'].to_dict()['members'][0]
    before = registry.view().entry(identity)
    renamed = prepare(case, name='Fixture Compensated')
    commit(case, renamed)
    inverse = prepare(case, name=Path(before['names']['local_path']).stem,
                       suffix='-inverse', compensates=renamed.sha256)
    commit(case, inverse)
    state = mappings.recover(registry)
    assert len(state['commits']) == 2 and len(state['plans']) == 2
    assert registry.view().entry(identity)['names'] == before['names']
    assert len(registry.operations.history(renamed.to_dict()['operation_id'])) == 2
    assert state['retained'][identity]['artwork'] == case['update_snapshot'].to_dict()['artwork'][identity]
    preserved_snapshots(case)
    denied_authority(state)
