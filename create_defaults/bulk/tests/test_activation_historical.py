"""M7 fresh whole-library reconciliation using the shared immutable M2/M5 facts."""

import json
import os
from pathlib import Path
import platform
from time import perf_counter

import pytest

from create_defaults.bulk.common import canonical
from create_defaults.bulk.contracts.activation.readiness import assemble_dossier, M6_GRAPH


def assert_final_phase2_historical_and_approval_inventory(monkeypatch,verified_historical_context,category_implementation,capsys,compatibility,contract_graph,dependency_index):
    import PIL.Image
    import requests
    import create_defaults.create_poster as poster
    from create_defaults.bulk import workers,state,overlays
    def prohibited(*a,**k):pytest.fail("M7 historical verification attempted pixels, live state, workers or network")
    for obj,name in ((PIL.Image,"open"),(poster,"create_poster"),(overlays,"render"),
                     (workers.PersistentWorkers,"__init__"),(state.Store,"__init__"),(requests.Session,"request")):
        monkeypatch.setattr(obj,name,prohibited)
    registry,records,resolution,graph,sources,capture_seconds=verified_historical_context
    started=perf_counter()
    report=assemble_dossier(category_implementation,registry,graph,sources,compatibility,contract_graph,dependency_index=dependency_index)
    compatible=report["compatibility"];readiness=report["readiness"]
    assert (compatible["outputs"],compatible["posters"],compatible["overlays"],compatible["public_outputs"])==(14079,9957,4122,14077)
    assert report["pins"]["M6_material_graph"]==M6_GRAPH and report["pins"]["source_pin_count"]==299
    assert readiness["selectors"]==22 and readiness["variants"]==278
    assert readiness["exact_approvals_present"]==0 and readiness["exact_approvals_missing"]==22
    assert readiness["ready"]==readiness["active"]==0
    assert all(p["historically_compatible"] is True and p["blockers"] for p in readiness["packages"])
    assert not compatible["incompatibilities"] and not compatible["unresolved_design_interpretations"]
    assert sum(c["receipt_accounting"]["owned_receipt_sha256"] for c in compatible["categories"])==14079
    assert sum(c["receipt_accounting"]["response_receipt_sha256"] for c in compatible["categories"])==14077
    assert next(c for c in compatible["categories"] if c["category"]=="Playlist")["outputs"]==9
    assert report["artwork_regenerated"]==report["remote_writes"]==0 and not report["production_enforcement"]
    report["performance"]={"capture_seconds":capture_seconds,"M7_audit_seconds":perf_counter()-started,"platform":platform.system()}
    # Optional local report export is explicitly named, never a production cache.
    if os.environ.get("M7_CAPTURE_REPORT"):
        Path(os.environ["M7_CAPTURE_REPORT"]).write_bytes(canonical(report))
    with capsys.disabled():
        print("M7 acceptance evidence:",json.dumps({"platform":platform.system(),"selectors":22,"variants":278,
            "outputs":14079,"public_outputs":14077,"actual_inputs":len(sources),"exact_approvals_missing":22,
            "production_files_verified":report["nonactivation"]["production_files_verified"],
            "ready":0,"active":0,"unexplained_differences":0,"pins":report["pins"],"performance":report["performance"]}),flush=True)
