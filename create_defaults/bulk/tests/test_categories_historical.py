"""Complete M6 contract audit; no pixels/state/network or new approvals."""

import json
import platform
from time import perf_counter

import pytest

from create_defaults.bulk.common import fingerprint
from create_defaults.bulk.contracts.categories.audit import audit
from create_defaults.bulk.contracts.categories.release import Implementation,RELEASE_SHA256
from create_defaults.bulk.contracts.categories.dependencies import bind


def test_complete_library_and_single_category_compatibility(monkeypatch,tmp_path,verified_historical_context,category_implementation,capsys,historical_stage_seconds):
    import PIL.Image
    import requests
    import create_defaults.create_poster as poster
    from create_defaults.bulk import workers,state,overlays
    def prohibited(*a,**k):
        pytest.fail("M6 audit invoked rendering, production state, worker or network")
    for obj,name in ((PIL.Image,"open"),(poster,"create_poster"),(overlays,"render"),
                     (workers.PersistentWorkers,"__init__"),(state.Store,"__init__"),(requests.Session,"request")):
        monkeypatch.setattr(obj,name,prohibited)
    registry,records,resolution,graph,sources,capture_seconds=verified_historical_context
    implementation=category_implementation
    report=audit(implementation,registry,records,resolution,graph)
    assert report["outputs"]==14079 and report["public_outputs"]==14077
    assert report["posters"]==9957 and report["overlays"]==4122
    assert len(report["categories"])==22
    assert sum(len(c["variants"]) for c in report["categories"])==278
    assert not report["incompatibilities"] and not report["unresolved_design_interpretations"]
    assert not report["production_enforcement"] and not report["publication_authorized"]
    assert report["contract_approval"]=="missing_exact_maintainer_decision"
    assert report["artwork_regenerated"]==report["remote_writes"]==0
    categories={c["category"]:c for c in report["categories"]}
    assert categories["Playlist"]["outputs"]==9
    assert categories["Awards"]["outputs"]-categories["Awards"]["public_outputs"]==2
    assert categories["Overlays"]["receipt_accounting"]["response_receipt_sha256"]==4122
    assert sum(c["historical_exceptions"].get("D09_ACCEPTED_SOURCE_PRESERVING",0) for c in report["categories"])==56
    assert sum(c["historical_exceptions"].get("D09_NORMAL_ACCEPTED_ALPHA_ASSET",0) for c in report["categories"])==41
    assert sum(c["receipt_accounting"]["owned_receipt_sha256"] for c in report["categories"])==14079
    assert sum(c["receipt_accounting"]["response_receipt_sha256"] for c in report["categories"])==14077
    single=audit(implementation,registry,records,resolution,graph,categories=["Playlist"])
    assert single["outputs"]==9 and len(single["categories"])==1
    report["performance"]={"capture_seconds":capture_seconds,"single_category_seconds":single["seconds"],
        "single_category":"Playlist","actual_inputs":len(sources),"immutable_context_reused":True}
    report["performance"]["stages_seconds"]=dict(historical_stage_seconds)
    contract_graph=bind(graph,implementation);index=contract_graph.index()
    assert len(index.outputs)==14079 and not index.unresolved
    studio_ids=[i for i,o in index.outputs.items() if o["category"]=="Studio"]
    impact=index.impact(["rules:m6/"+i for i in studio_ids])
    assert len(impact["affected_outputs"])==488
    assert all(index.outputs[i]["category"]=="Studio" for i in impact["affected_outputs"])
    assert not index.impact(["contract:defaults.studio.poster@1.0.0"])["affected_outputs"]
    assert len(index.impact(["asset:logos_playlist/Arrowverse.png"])["affected_outputs"])==3
    assert graph.sha256==report["M5_graph_sha256"]
    report["M6_contract_graph_sha256"]=contract_graph.sha256
    (tmp_path/"m6-audit.json").write_text(json.dumps(report,indent=2),encoding="utf8")
    # Emit the compact evidence on successful CI too, without changing the
    # workflow or exposing source paths/individual historical receipts.
    with capsys.disabled():
        print("M6 compatibility evidence:",json.dumps({"platform":platform.system(),
            **{k:v for k,v in report.items() if k!="categories"}}),flush=True)
    # M7 consumes this exact fresh audit/graph, without repeating its large
    # materialization in the same bounded worker-parent test process. All
    # original M6 assertions above and all M7 reconciliation assertions remain.
    from create_defaults.bulk.tests.test_activation_historical import assert_final_phase2_historical_and_approval_inventory
    assert_final_phase2_historical_and_approval_inventory(monkeypatch,verified_historical_context,
        implementation,capsys,report,contract_graph,index)
    # Additive P3/M5 acceptance over these same fresh immutable facts. Retain
    # every original M2/M5/M6/M7 assertion and avoid a second full capture.
    from create_defaults.phase3.tests.final_acceptance import reconcile_historical,export_historical,assert_actual_overlay_chain
    final = reconcile_historical(implementation,registry,records,index,report)
    exported = export_historical(final)
    with capsys.disabled():
        print("P3 final historical acceptance evidence:",json.dumps(exported),flush=True)
    assert_actual_overlay_chain(implementation,records,contract_graph,index)
