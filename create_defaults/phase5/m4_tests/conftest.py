"""Real native M5 ADD/UPDATE seed; backup is fixture isolation, never recovery."""
from create_defaults.phase4.tests.conftest import transaction_seed
from create_defaults.phase4.m7_tests.conftest import m7_seed, m7_case
from create_defaults.phase4.tests.transaction_samples import transaction_case
import pytest

# Fixture aliases preserve the original native constructor and isolation.
m4_case = m7_case


@pytest.fixture(scope='session')
def scope_context():
    from create_defaults.bulk.lifecycle.previews import CompositionTrial
    from create_defaults.phase4.tests.composition_samples import poster
    with CompositionTrial() as trial:
        yield poster(trial,'Genre')


@pytest.fixture(scope='session')
def current_seed(m7_seed):
    from create_defaults.phase5.m4_tests.helpers import rename, epoch, prepare_update
    base=dict(m7_seed,label='m4-prepared-seed')
    # Hold one independently reviewed real composition for rollback tests.
    # Restoring this fixture is isolation; the tested recovery uses real commit
    # records and never restores a backup.
    for case in transaction_case.__wrapped__(base):
        rename(case)
        selected=epoch(case)
        native,tx,snapshot=prepare_update(case,selected,label='prepared-current')
        yield dict(case,**native,selection=selected,current_tx=tx,current_snapshot=snapshot)


@pytest.fixture
def prepared_current(current_seed):
    yield from transaction_case.__wrapped__(current_seed)
