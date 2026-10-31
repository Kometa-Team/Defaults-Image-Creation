"""Native accepted ADD fixture; original fixture resets are test isolation only."""
import pytest
from create_defaults.phase4.tests.conftest import transaction_seed
from create_defaults.phase4.tests.transaction_samples import transaction_case,transaction
from create_defaults.bulk.lifecycle import apply


@pytest.fixture(scope='session')
def native_seed():
    for original in transaction_seed.__wrapped__():
        tx,snapshot=transaction(original)
        result=apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=original['authority'])
        assert result['isolated_committed'] and not result['publication_authorized']
        yield dict(original,snapshot=snapshot,add_snapshot=snapshot,update_snapshot=snapshot)


@pytest.fixture
def native(native_seed):
    yield from transaction_case.__wrapped__(native_seed)


@pytest.fixture(scope='session')
def plan_seed(native_seed):
    from create_defaults.phase5.m5_tests.helpers import prepared
    return prepared(native_seed)


@pytest.fixture(scope='session')
def current_native():
    from create_defaults.phase5.m4_tests.conftest import sequence_seed
    from create_defaults.phase5.m4_tests.helpers import rename,epoch,commit_update
    for base in sequence_seed.__wrapped__():
        for example in transaction_case.__wrapped__(base):
            example=dict(example,label='m5-current-sequence')
            mapping=rename(example,name='fixture')
            selected=epoch(example)
            native,_,snapshot,result=commit_update(example,selected,label='m5-current-update')
            assert result['isolated_committed']
            yield dict(example,**native,snapshot=snapshot,mapping=mapping,
                snapshots=[base['add_snapshot'],base['update_snapshot'],snapshot])


@pytest.fixture(scope='session')
def multi_native():
    from create_defaults.bulk.lifecycle.previews import CompositionTrial
    from create_defaults.phase4.tests.transaction_samples import shared_cohort,reviewed
    with CompositionTrial() as trial:
        context=shared_cohort(trial)
        case=reviewed(trial,context,label='m5-multi')
        tx,snapshot=transaction(case)
        result=apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=case['authority'])
        assert result['isolated_committed'] and len(snapshot.to_dict()['members'])==2
        yield dict(case,snapshot=snapshot)
