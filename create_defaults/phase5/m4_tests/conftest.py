"""Real native M5 ADD/UPDATE seed; backup is fixture isolation, never recovery."""
from create_defaults.phase4.tests.conftest import transaction_seed
from create_defaults.phase4.m7_tests.conftest import m7_seed, m7_case
from create_defaults.phase4.tests.transaction_samples import transaction_case
import pytest

@pytest.fixture(scope='session')
def mapping_seed():
    """One real ADD is sufficient for mapping and unrelated-member guards."""
    from create_defaults.bulk.lifecycle import apply
    from create_defaults.phase4.tests.transaction_samples import transaction
    for original in transaction_seed.__wrapped__():
        tx,snapshot=transaction(original)
        apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=original['authority'])
        yield dict(original,add_snapshot=snapshot)


@pytest.fixture
def m4_case(mapping_seed):
    yield from transaction_case.__wrapped__(mapping_seed)


@pytest.fixture(scope='session')
def scope_context():
    from create_defaults.bulk.lifecycle.previews import CompositionTrial
    from create_defaults.phase4.tests.composition_samples import poster
    with CompositionTrial() as trial:
        yield poster(trial,'Genre')


@pytest.fixture(scope='session')
def current_seed():
    from create_defaults.bulk.lifecycle import apply
    from create_defaults.phase4.tests.transaction_samples import transaction
    from create_defaults.phase5.m4_tests.helpers import rename, epoch, prepare_update
    # Faults need one accepted native ADD then RENAME. The separate sequence
    # test owns the complete ADD/UPDATE/RENAME/UPDATE proof. Construct a fresh
    # original trial rather than share mutable state with that sequence seed.
    for original in transaction_seed.__wrapped__():
        add_tx,added=transaction(original)
        apply.commit_synthetic(add_tx,expected_snapshot_sha256=added.sha256,authority=original['authority'])
        base=dict(original,label='m4-prepared-seed',add_snapshot=added,update_snapshot=added,update_tx=add_tx)
        # Restoring this backup is fixture isolation only; tested application
        # recovery uses actual immutable commits and never restores a backup.
        for case in transaction_case.__wrapped__(base):
            rename(case)
            selected=epoch(case)
            native,tx,snapshot=prepare_update(case,selected,label='prepared-current')
            yield dict(case,**native,selection=selected,current_tx=tx,current_snapshot=snapshot)


@pytest.fixture
def prepared_current(current_seed):
    yield from transaction_case.__wrapped__(current_seed)
