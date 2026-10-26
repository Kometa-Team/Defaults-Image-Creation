"""Test adapters call the unchanged public M5/M6 APIs; no substitute executor."""
from copy import deepcopy
import json

from create_defaults.bulk.common import fingerprint
from create_defaults.bulk.lifecycle import mappings
from create_defaults.phase4.m6_tests.test_mappings import decisions


def prepare(case, *, name=None, display=None, delete=False, suffix='', compensates=None):
    registry = case['row'][1].registry
    identity = case['update_snapshot'].to_dict()['members'][0]
    definitions = None
    if not delete:
        # The test changes only names/display. M6 independently replays current
        # committed definitions inside prepare; do not repeat that full replay
        # merely to construct the proposed nonvisual fields here.
        definition = deepcopy(json.loads(case['update_snapshot'].to_dict()['proposed_json'])['effective_definitions'][identity])
        if name is not None:
            definition['composer']['out_name'] = name
            definition['output']['filename'] = name+'.jpg'
            definition['output']['remote_paths']['en'] = 'genre/'+name+'.jpg'
        if display is not None:
            definition['display_name'] = display
        definitions = {identity: definition}
    return mappings.prepare(registry,
        operation_id='synthetic.operation.m7-'+fingerprint(case['label']+suffix)[:24],
        operation='DELETE' if delete else 'RENAME', definitions=definitions,
        members=[identity], compensates=compensates)


def commit(case, plan, **kwargs):
    registry = case['row'][1].registry
    mappings.propose(registry, plan)
    pair = decisions(case, plan)
    result = mappings.commit_synthetic(registry, plan, authority=case['authority'],
                                       decisions=pair, **kwargs)
    return result, pair


def preserved_snapshots(case):
    store = case['row'][1].registry.operations.contracts
    for name in ('add_snapshot', 'update_snapshot'):
        snapshot = case[name]
        assert store.read_object(snapshot.sha256) == snapshot.encoded


def denied_authority(result):
    for flag in ('authenticated', 'operation_accepted', 'applied', 'artwork_approved',
                 'contract_approved', 'ready', 'active', 'production_enforcement',
                 'publication_authorized'):
        assert result[flag] is False, flag
