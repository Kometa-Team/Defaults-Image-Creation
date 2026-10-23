import pytest
from create_defaults.phase3.tests.samples import bundle


@pytest.fixture
def values():
    return bundle()
