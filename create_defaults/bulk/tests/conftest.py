"""One guarded, immutable full M2 discovery shared only while tests need it.

M2 checks actual facts/receipts; M5 checks their graph and independent oracle.
Sharing immutable values avoids repeating discovery within the existing CI
timeout. Production code has no such cache.
"""

from time import perf_counter

import pytest


@pytest.fixture(scope="session")
def category_implementation():
    from create_defaults.bulk.contracts.categories.release import Implementation,RELEASE_SHA256
    return Implementation.load(expected_sha256=RELEASE_SHA256)


@pytest.fixture(scope="module")
def category_prepared(category_implementation):
    return {p.contract.to_dict()["category"]:(p,(p.contract.to_dict(),*p.data())) for p in category_implementation.packages}


def _discover_historical():
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


@pytest.fixture(scope="session")
def _historical_discovery_cache(request):
    consumers=sum("verified_historical_discovery" in item.fixturenames for item in request.session.items)
    return {"data":None,"remaining":consumers}


@pytest.fixture
def verified_historical_discovery(_historical_discovery_cache):
    """Keep every M2/M5/M6/M7 assertion, release immutable records afterward.

    M7 adds a complete audit before the other consumers. Keeping all 14,079
    record blobs until session shutdown unnecessarily inflates later worker
    memory measurements. Discovery still runs exactly once; no source, receipt
    or output check is skipped and the 512 MiB worker-parent limit is unchanged.
    """
    cache=_historical_discovery_cache
    if cache["data"] is None:
        cache["data"]=_discover_historical()
    try:
        yield cache["data"]
    finally:
        cache["remaining"]-=1
        if cache["remaining"]==0:
            cache["data"]=None
            import gc
            gc.collect()


def _build_historical_context(verified_historical_discovery):
    """Share freshly checked immutable M5 facts across M5/M6 assertions.

    This is test-only snapshot reuse, never a production approval/cache. Every
    original M2 check still runs once, as do all physical source and M5 checks.
    """
    from create_defaults.bulk.contracts.adoption.sources import load_pins,verify_sources
    from create_defaults.bulk.contracts.categories.evidence import verify_inputs
    from create_defaults.bulk.contracts.expanded.resolution import resolve
    from create_defaults.bulk.contracts.expanded.historical import build
    import PIL.Image
    import requests
    import create_defaults.create_poster as poster
    from create_defaults.bulk import workers,state,overlays

    def prohibited(*a,**k):
        pytest.fail("Historical context invoked rendering, workers, live state or network")
    registry,records,seconds=verified_historical_discovery
    start=perf_counter()
    with pytest.MonkeyPatch.context() as guard:
        guard.setattr(PIL.Image,"open",prohibited)
        guard.setattr(poster,"create_poster",prohibited)
        guard.setattr(overlays,"render",prohibited)
        guard.setattr(workers.PersistentWorkers,"__init__",prohibited)
        guard.setattr(state.Store,"__init__",prohibited)
        guard.setattr(requests.Session,"request",prohibited)
        verify_sources(load_pins())
        sources=verify_inputs(records)
        resolution=resolve()
        graph=build(registry,records,resolution)
    return registry,records,resolution,graph,sources,seconds+perf_counter()-start


@pytest.fixture(scope="session")
def _historical_context_cache(request):
    consumers=sum("verified_historical_context" in item.fixturenames for item in request.session.items)
    return {"data":None,"remaining":consumers}


@pytest.fixture
def verified_historical_context(verified_historical_discovery,_historical_context_cache):
    """Reuse while needed, then release before bounded-worker memory tests.

    Retaining this large graph until session teardown would make unrelated
    worker parent-memory measurements include M6 audit data. Keep the existing
    worker budget intact and bound this test cache's actual lifetime instead.
    """
    cache=_historical_context_cache
    if cache["data"] is None:
        cache["data"]=_build_historical_context(verified_historical_discovery)
    try:
        yield cache["data"]
    finally:
        cache["remaining"]-=1
        if cache["remaining"]==0:
            cache["data"]=None
            import gc
            gc.collect()
