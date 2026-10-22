"""Complete read-only M5 capture and a separately built expected-output oracle."""

from collections import Counter
import json
from time import perf_counter

import pytest

from create_defaults.bulk.contracts.adoption.models import read_canonical
from create_defaults.bulk.contracts.adoption.sources import load_pins,verify_sources
from create_defaults.bulk.common import confined,sha256
from create_defaults.bulk.config import ROOT
from create_defaults.bulk.contracts.expanded.historical import build
from create_defaults.bulk.contracts.expanded.resolution import resolve
from create_defaults.bulk.contracts.expanded.validation import validate_existing


def test_complete_historical_expansion_and_exact_impact_oracle_without_rendering(monkeypatch,tmp_path,verified_historical_context):
    def prohibited(*a,**k):
        pytest.fail("M5 historical audit invoked renderer, workers, production state or network")
    import PIL.Image
    import requests
    import create_defaults.create_poster as poster
    from create_defaults.bulk import workers,state,overlays
    monkeypatch.setattr(PIL.Image,"open",prohibited)
    monkeypatch.setattr(poster,"create_poster",prohibited)
    monkeypatch.setattr(overlays,"render",prohibited)
    monkeypatch.setattr(workers.PersistentWorkers,"__init__",prohibited)
    monkeypatch.setattr(state.Store,"__init__",prohibited)
    monkeypatch.setattr(requests.Session,"request",prohibited)
    # The session fixture performs the same fresh code/catalog and physical
    # input checks plus M5 build once; all assertions/oracles below are retained.
    registry,records,resolution,graph,source_hashes,capture_seconds=verified_historical_context
    index=graph.index()
    assert len(records)==len(index.outputs)==14079
    assert sum(v["public_path"] is not None for v in index.outputs.values())==14077
    counts=Counter(v["kind"] for v in index.outputs.values())
    assert counts=={"poster":9957,"overlay":4122}
    value=resolution.data()
    assert len(value["declared"])==4372 and len(value["families"])==102
    assert not index.unresolved
    values=[r.to_dict() for r in records]
    jobs={v["job_id"]:read_canonical(v["job_json"]) for v in values}
    by_job={v["job_id"]:v["identity"]["id"] for v in values}
    # This oracle inspects original verified jobs directly, never graph nodes,
    # Index.reverse, Index.impact, or a second copy of graph-building logic.
    def expected(path):
        direct={key for key,job in jobs.items() if any(i["path"]==path for i in job["inputs"])}
        affected=set(direct)
        while True:
            children={key for key,job in jobs.items() if any(d["job_id"] in affected for d in job["dependencies"])}
            expanded=affected|children
            if expanded==affected:
                break
            affected=expanded
        return {by_job[key] for key in direct},{by_job[key] for key in affected}
    paths=["logos_playlist/Arrowverse.png","fades/@none.png",
        next(i["path"] for j in jobs.values() if j["kind"]=="overlay" for i in j["inputs"])]
    timings=[]
    for path in paths:
        direct,affected=expected(path)
        start=perf_counter();report=index.impact(["asset:"+path]);seconds=perf_counter()-start
        assert set(report["direct_outputs"])==direct
        assert set(report["affected_outputs"])==affected
        assert set(report["unaffected_outputs"])==index.outputs.keys()-affected
        assert report["impact_complete"] and seconds>=0
        timings.append({"dependency":path,"direct":len(direct),"affected":len(affected),"seconds":seconds})
    playlist=[r for r in records if r.to_dict()["identity"]["category"]=="Playlist"]
    assert len(playlist)==9
    assert all(validate_existing(r,resolution,fixture_only=True)["outcome"]=="compatible" for r in playlist)
    # All branches/sizes retain literal filenames and normal accepted alpha
    # assets. M5 adds no source validation warnings or artwork cleanup.
    assert all(len(v["companions"])>=1 for v in index.outputs.values() if v["kind"]=="overlay")
    assert not index.impact(["asset:logos_playlist/Arrowverse.png"])["publication_authorized"]
    (tmp_path/"graph.json").write_bytes(graph.encoded)
    evidence={"snapshot_sha256":graph.sha256,"outputs":len(index.outputs),"nodes":len(index.nodes),
        "bytes":len(graph.encoded),"capture_seconds":capture_seconds,"impact_measurements":timings,
        "oracle":"independent scan of original verified jobs plus parent references","playlist_compatible":9,
        "unresolved":index.unresolved,"production_enforcement":False,"publication_authorized":False}
    (tmp_path/"evidence.json").write_text(json.dumps(evidence,indent=2),encoding="utf8")
    print("M5 full audit evidence:",tmp_path/"evidence.json",json.dumps(evidence))
