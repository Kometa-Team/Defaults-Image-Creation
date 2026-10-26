"""T03/T16/T19/T20: failures after a real committed ADD and material UPDATE."""
from contextlib import contextmanager
from threading import Event

import pytest

from create_defaults.bulk.common import BulkError
from create_defaults.bulk.lifecycle import mappings, mapping_moves
from create_defaults.bulk.lifecycle.package_e import SidecarStore
from create_defaults.bulk.lifecycle.recovery import recover
from create_defaults.phase4.tests.samples import append, sample
from create_defaults.phase4.m6_tests.test_mappings import decisions
from create_defaults.phase4.m7_tests.helpers import (
    commit, denied_authority, prepare, preserved_snapshots,
)


@pytest.mark.parametrize('point', ['mapping_marker', 'registry_marker', 'commit_event'])
def test_mapping_transaction_failure_preserves_committed_update_and_unrelated_record(m7_case, monkeypatch, point):
    case = m7_case
    registry = case['row'][1].registry
    independent = sample(registry.operations, name='m7-unrelated', subjects=('unrelated',))
    append(registry.operations, independent)
    plan = prepare(case, name='fixture')
    mappings.propose(registry, plan)
    pair = decisions(case, plan)
    before = registry.operations.inspect()
    baseline = recover(registry.operations.root)
    view = registry.view()

    def interrupt(boundary):
        if boundary == point:
            raise OSError('m7 injected '+point)
    monkeypatch.setattr(mappings, '_checkpoint', interrupt)
    with pytest.raises(OSError, match='m7 injected'):
        mappings.commit_synthetic(registry, plan, authority=case['authority'], decisions=pair)
    assert registry.operations.inspect() == before and registry.view() == view
    assert registry.operations.history(independent.to_dict()['id']) == (independent,)
    assert recover(registry.operations.root) == baseline
    assert mappings.recover(registry)['commits'] == {}
    preserved_snapshots(case)

    monkeypatch.setattr(mappings, '_checkpoint', lambda _: None)
    result = mappings.commit_synthetic(registry, plan, authority=case['authority'], decisions=pair)
    assert result['isolated_committed'] and not result['retry']
    assert mappings.commit_synthetic(registry, plan, authority=case['authority'], decisions=pair)['retry']
    assert registry.operations.history(independent.to_dict()['id']) == (independent,)
    denied_authority(result)


@pytest.mark.parametrize('point', ['journal_prepared', 'prepared', 'linked', 'intermediate', 'destination'])
def test_interrupted_case_move_after_update_restores_then_retries_exactly(m7_case, monkeypatch, point):
    class Interrupted(BaseException):
        pass
    case = m7_case
    registry = case['row'][1].registry
    plan = prepare(case, name='fixture')
    mappings.propose(registry, plan)
    pair = decisions(case, plan)
    before = registry.operations.inspect()
    baseline = recover(registry.operations.root)
    view = registry.view()

    def interrupt(boundary):
        if boundary == point:
            raise Interrupted()
    monkeypatch.setattr(mapping_moves, '_checkpoint', interrupt)
    with pytest.raises(Interrupted):
        mappings.commit_synthetic(registry, plan, authority=case['authority'], decisions=pair)
    assert registry.operations.inspect() == before and registry.view() == view
    assert recover(registry.operations.root) == baseline
    monkeypatch.setattr(mapping_moves, '_checkpoint', lambda _: None)
    operation = plan.to_dict()['operation_id']
    assert mappings.recover_local(registry) == {operation: 'restored-preimage'}
    recovered = mappings.recover(registry)
    assert not recovered['commits']
    assert mappings.recover_local(registry) == {operation: 'restored-preimage'}
    assert mappings.recover(registry) == recovered
    assert mappings.commit_synthetic(registry, plan, authority=case['authority'], decisions=pair)['isolated_committed']
    assert mappings.recover_local(registry) == {operation: 'committed-spelling'}
    committed = mappings.recover(registry)
    assert mappings.commit_synthetic(registry, plan, authority=case['authority'], decisions=pair)['retry']
    assert mappings.recover(registry) == committed
    preserved_snapshots(case)
    denied_authority(committed)


def test_lost_mapping_acknowledgement_recovers_one_commit_after_update(m7_case, monkeypatch):
    case = m7_case
    registry = case['row'][1].registry
    plan = prepare(case, name='fixture')
    mappings.propose(registry, plan)
    pair = decisions(case, plan)
    original = SidecarStore.transaction
    ready = False
    raised = False

    def reached(point):
        nonlocal ready
        if point == 'commit_event':
            ready = True

    @contextmanager
    def lose_acknowledgement(store):
        nonlocal raised
        with original(store) as db:
            yield db
        # The real transaction has COMMITTED. This cannot fake a pre-commit
        # exception or supply a substitute persistence implementation.
        if ready and not raised:
            raised = True
            raise OSError('m7 lost success acknowledgement')

    monkeypatch.setattr(mappings, '_checkpoint', reached)
    monkeypatch.setattr(SidecarStore, 'transaction', lose_acknowledgement)
    with pytest.raises(OSError, match='lost success acknowledgement'):
        mappings.commit_synthetic(registry, plan, authority=case['authority'], decisions=pair)
    assert raised
    before = mappings.recover(registry)
    assert list(before['commits']) == [plan.to_dict()['operation_id']]
    assert mappings.commit_synthetic(registry, plan, authority=case['authority'], decisions=pair)['retry']
    assert mappings.recover(registry) == before
    assert len(registry.operations.history(plan.to_dict()['operation_id'])) == 2
    preserved_snapshots(case)


def test_cancel_after_update_preserves_material_and_requires_new_compensation(m7_case):
    case = m7_case
    registry = case['row'][1].registry
    plan = prepare(case, name='fixture')
    mappings.propose(registry, plan)
    pair = decisions(case, plan)
    baseline = recover(registry.operations.root)
    cancel = Event()
    cancel.set()
    with pytest.raises(BulkError) as error:
        mappings.commit_synthetic(registry, plan, authority=case['authority'], decisions=pair, cancel=cancel)
    assert error.value.code == 'p4m5_cancelled'
    assert recover(registry.operations.root) == baseline
    assert mappings.recover(registry)['commits'] == {}
    preserved_snapshots(case)
