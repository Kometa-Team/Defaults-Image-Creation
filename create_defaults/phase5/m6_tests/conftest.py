"""Reuse historical native fixtures unchanged; resets are test isolation only."""
from create_defaults.phase5.m5_tests.conftest import (
    transaction_seed,native_seed,native,plan_seed,current_native,multi_native,
)
import pytest,subprocess


@pytest.fixture(autouse=True)
def currentness_timings(monkeypatch):
    """Opt-in diagnosis only: measure the original fresh call, never replace it."""
    import json,os,time
    from pathlib import Path
    directory=os.environ.get('M6_PROFILE_DIR')
    if not directory:return
    from create_defaults.bulk.lifecycle import draft_transport
    path=Path(directory);path.mkdir(parents=True,exist_ok=True)
    original=draft_transport.revalidate
    def measured(*args,**kwargs):
        start=time.perf_counter();passed=False
        try:
            result=original(*args,**kwargs);passed=True;return result
        finally:
            with (path/(str(os.getpid())+'.jsonl')).open('a',encoding='utf8') as out:
                out.write(json.dumps(dict(kind='original-m5-currentness',seconds=time.perf_counter()-start,passed=passed))+'\n')
    monkeypatch.setattr(draft_transport,'revalidate',measured)


@pytest.fixture(autouse=True)
def no_external_transport(monkeypatch):
    import requests
    def forbidden(*args,**kwargs):pytest.fail('M6 test attempted external transport')
    monkeypatch.setattr(requests.sessions.Session,'request',forbidden)
    real_run=subprocess.run;real_output=subprocess.check_output
    def run(args,*a,**k):
        if isinstance(args,list) and args and args[0]=='gh':forbidden()
        return real_run(args,*a,**k)
    def output(args,*a,**k):
        if isinstance(args,list) and args and args[0]=='gh':forbidden()
        return real_output(args,*a,**k)
    monkeypatch.setattr(subprocess,'run',run);monkeypatch.setattr(subprocess,'check_output',output)
