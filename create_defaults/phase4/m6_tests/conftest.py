"""Reuse one native M3/M4/M5 composition and its original fixture isolation."""
from create_defaults.phase4.tests.conftest import transaction_seed
from create_defaults.phase4.tests.transaction_samples import transaction_case

import pytest


@pytest.fixture(scope='session')
def m6_seed(transaction_seed):
    from create_defaults.phase4.tests.transaction_samples import transaction
    from create_defaults.bulk.lifecycle.apply import commit_synthetic
    tx,snapshot=transaction(transaction_seed)
    commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=transaction_seed['authority'])
    return dict(transaction_seed,m5_snapshot=snapshot)


@pytest.fixture
def m6_case(m6_seed):
    yield from transaction_case.__wrapped__(m6_seed)
