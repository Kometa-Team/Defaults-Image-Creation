"""One guarded, immutable full M2 discovery per pytest session.

M2 checks actual facts/receipts; M5 checks their graph and independent oracle.
Sharing immutable values avoids repeating discovery within the existing CI
timeout. Production code has no such cache.
"""

from time import perf_counter

import pytest


@pytest.fixture(scope="session")
def verified_historical_discovery():
    from create_defaults.bulk.contracts.adoption.inventory import discover
    import PIL.Image
    import requests
    import create_defaults.create_poster as poster
    from create_defaults.bulk import workers,state,overlays

    def prohibited(*a,**k):
        pytest.fail("Historical discovery invoked rendering, workers, live state or network")

    started=perf_counter()
    with pytest.MonkeyPatch.context() as guard:
        guard.setattr(PIL.Image,"open",prohibited)
        guard.setattr(poster,"create_poster",prohibited)
        guard.setattr(overlays,"render",prohibited)
        guard.setattr(workers.PersistentWorkers,"__init__",prohibited)
        guard.setattr(state.Store,"__init__",prohibited)
        guard.setattr(requests.Session,"request",prohibited)
        registry,records=discover()
    # M1 Document instances are frozen canonical bytes. Native mutable ledgers
    # and worker state are not cached; all dictionaries are detached on access.
    return registry,records,perf_counter()-started
