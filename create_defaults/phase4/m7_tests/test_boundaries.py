"""Cross-milestone stale inputs, archive corruption and unavailable authority."""
from copy import deepcopy
import sqlite3

import pytest

from create_defaults.bulk.common import BulkError, Conflict
from create_defaults.bulk.lifecycle import apply, mappings
from create_defaults.bulk.lifecycle.recovery import recover
from create_defaults.bulk.lifecycle.retirement import validate_delete
from create_defaults.phase4.m7_tests.helpers import commit, prepare, preserved_snapshots


def test_post_update_mapping_stale_plan_never_rebases_committed_history(m7_case):
    case = m7_case
    registry = case['row'][1].registry
    first = prepare(case, display='First mapping')
    stale = prepare(case, display='Stale mapping', suffix='-stale')
    commit(case, first)
    before = mappings.recover(registry)
    with pytest.raises(Conflict):
        mappings.propose(registry, stale)
    assert mappings.recover(registry) == before
    with pytest.raises(BulkError) as error:
        apply.commit_synthetic(case['update_tx'], expected_snapshot_sha256=case['update_snapshot'].sha256,
                               authority=case['authority'])
    assert error.value.code == 'p4m6_m6_mapping_requires_current_adapter'
    assert mappings.recover(registry) == before
    preserved_snapshots(case)


@pytest.mark.parametrize('target', ['snapshot', 'receipt', 'journal', 'heads'])
def test_post_update_rename_archive_corruption_fails_at_integrity_boundary(m7_case, target):
    case = m7_case
    registry = case['row'][1].registry
    plan = prepare(case, name='fixture')
    commit(case, plan)
    baseline = mappings.recover(registry)
    store = registry.operations.contracts
    if target in {'snapshot', 'receipt'}:
        snapshot = case['update_snapshot']
        pin = snapshot.sha256 if target == 'snapshot' else next(iter(snapshot.to_dict()['artwork'].values()))['receipt_object_sha256']
        path = store.root/'objects'/(pin+'.json')
        original = path.read_bytes()
        try:
            path.write_bytes(b'{}')
            with pytest.raises(BulkError) as error:
                mappings.recover(registry)
            assert error.value.code == 'corrupt_contract_evidence'
        finally:
            path.write_bytes(original)
    else:
        # Disposable fixture only: deliberately damage a real immutable index
        # after dropping its trigger. Opening/recovery must never repair it.
        table = 'p4m1_journal' if target == 'journal' else 'p4m1_heads'
        with sqlite3.connect(store.root/'state.sqlite3') as db:
            db.execute('DROP TRIGGER '+table+'_no_update')
            db.execute('UPDATE '+table+' SET sha256=? WHERE rowid=(SELECT max(rowid) FROM '+table+')', ('0'*64,))
        with pytest.raises(BulkError) as error:
            mappings.recover(registry)
        assert error.value.code == 'p4m1_archive_namespace'
        # Fixture teardown restores the backup; application recovery never does.
        return
    assert mappings.recover(registry) == baseline


def test_retirement_dependency_checks_after_update_use_real_current_graph(m7_case):
    case = m7_case
    registry = case['row'][1].registry
    graph = case['row'][1].candidate.graph
    identity = next(iter(graph.index().outputs))
    entry = registry.view().entry(identity)
    # An actual retained dependent is represented in the existing M2 semantic
    # registry projection; no unsupported child execution adapter is invented.
    child = deepcopy(entry)
    child['id'] = 'synthetic.dependent-child'
    child['semantic']['parent'] = identity
    entries = {identity: entry, child['id']: child}
    with pytest.raises(BulkError) as error:
        validate_delete(graph.index(), entries, [identity])
    assert error.value.code == 'p4m6_required_retained_child'
    generated = deepcopy(entry)
    generated['semantic']['key'] = 'year:2030'
    with pytest.raises(BulkError) as error:
        validate_delete(graph.index(), {identity: generated}, [identity])
    assert error.value.code == 'p4m6_persistent_generated_exclusion_required'
    assert mappings.recover(registry)['active_members'] == [identity]
    preserved_snapshots(case)


def test_real_authority_cannot_be_reconstructed_from_committed_synthetic_history(m7_case):
    case = m7_case
    registry = case['row'][1].registry
    plan = prepare(case, display='Unauthenticated')
    before = registry.operations.inspect()
    for action in (lambda: apply.commit_operational(case['update_tx']),
                   lambda: mappings.commit_operational(registry, plan),
                   lambda: mappings.commit_synthetic(registry, plan, authority={'authenticated': True}, decisions=[])):
        with pytest.raises(BulkError) as error:
            action()
        assert error.value.code == 'p4m4_real_authority_unavailable'
    assert registry.operations.inspect() == before
    assert mappings.recover(registry)['commits'] == {}
