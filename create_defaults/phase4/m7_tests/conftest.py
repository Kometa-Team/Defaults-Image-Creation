"""Integrated tests reuse the existing native trial and fixture-only DB reset."""
import pytest

from create_defaults.bulk.lifecycle import apply
from create_defaults.bulk.lifecycle.operations import propose
from create_defaults.bulk.lifecycle.recovery import recover
from create_defaults.phase4.tests.conftest import transaction_seed
from create_defaults.phase4.tests.transaction_samples import (
    reviewed, transaction, transaction_case, update_candidate,
)


@pytest.fixture(scope='session')
def m7_seed(transaction_seed):
    original = transaction_seed
    trial, context, _, _ = original['row']
    add_tx, add_snapshot = transaction(original)
    added = apply.commit_synthetic(add_tx, expected_snapshot_sha256=add_snapshot.sha256,
                                   authority=original['authority'])
    candidate, frozen = update_candidate(original, label='m7-update')
    update_context = propose(context.registry, before=frozen, candidate=candidate,
                             identity='synthetic.operation.m7-update', operation='UPDATE')
    updated = reviewed(trial, update_context, label='m7-updated')
    update_tx, update_snapshot = transaction(updated, {
        identity: added['snapshot_sha256'] for identity in candidate.graph.index().outputs
    })
    apply.commit_synthetic(update_tx, expected_snapshot_sha256=update_snapshot.sha256,
                           authority=updated['authority'])
    assert len(recover(trial.config.cache_dir)['commits']) == 2
    return dict(updated, add_snapshot=add_snapshot, update_snapshot=update_snapshot,
                update_tx=update_tx, original_case=original)


@pytest.fixture
def m7_case(m7_seed, request):
    # This backup/reset is test isolation, never the application's recovery path.
    for case in transaction_case.__wrapped__(m7_seed):
        yield dict(case, label=request.node.name)
