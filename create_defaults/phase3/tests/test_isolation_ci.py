"""Cold import isolation and mandatory CI/security acceptance negative controls."""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from ci import phase3, validation
from create_defaults.bulk.common import fingerprint
from create_defaults.bulk.contracts.language_policy import check_bundle_structure
from create_defaults.phase3.tests.samples import bundle


ROOT=Path(__file__).resolve().parents[3]


def test_cold_import_has_no_schema_io_network_clock_writes_or_activation():
    code=r'''
import sys
sys.dont_write_bytecode=True
def audit(event,args):
    if event in {'os.mkdir','os.remove','os.rename','sqlite3.connect','socket.connect','socket.bind','subprocess.Popen','os.system'}:
        raise AssertionError('import side effect: '+event)
    if event=='open':
        path,mode,flags=args
        if isinstance(mode,str) and any(c in mode for c in 'wax+'):
            raise AssertionError('import file write')
        if str(path).endswith('foundations-v1.schema.json'):
            raise AssertionError('schema read at import time')
sys.addaudithook(audit)
from create_defaults.bulk.contracts import language_policy
assert 'create_defaults.bulk.contracts.activation' not in sys.modules
assert not hasattr(language_policy,'Controller')
print('isolated-import-ok')
'''
    result=subprocess.run([sys.executable,"-c",code],cwd=ROOT,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"},capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=="isolated-import-ok"


def test_canonical_values_and_structural_binding_have_no_operational_side_effects(monkeypatch):
    original=bundle()  # Warm lazy local schema validators before forbidding IO.
    import time
    import socket
    import sqlite3
    import requests
    from PIL import Image
    from create_defaults.bulk import state,workers
    def prohibited(*a,**k):raise AssertionError("canonicalization invoked operational side effect")
    with monkeypatch.context() as guard:
        for obj,name in [(time,"time"),(time,"monotonic"),(time,"perf_counter"),(socket,"socket"),
                         (sqlite3,"connect"),(requests.Session,"request"),(Image,"open"),(Path,"read_bytes"),
                         (Path,"write_bytes"),(Path,"mkdir"),(state.Store,"__init__"),(workers.PersistentWorkers,"__init__")]:
            guard.setattr(obj,name,prohibited)
        copied=tuple(type(d).from_bytes(d.encoded) for d in original)
        assert check_bundle_structure(*copied) is None
        assert [d.sha256 for d in copied]==[d.sha256 for d in original]


def test_all_190_pins_and_only_authorized_workflow_maintenance_are_preserved():
    from create_defaults.bulk.contracts.activation import protection
    path="create_defaults/bulk/contracts/activation/data/production-pins-v1.json"
    baseline=json.loads(subprocess.check_output(["git","show","78464d2d051dc5da5f305bc4fd9f03868999636f:"+path],cwd=ROOT))
    selected=json.loads((ROOT/path).read_text(encoding="utf8"))
    assert len(selected["files"])==len(baseline["files"])==190
    assert selected["files"].keys()==baseline["files"].keys()
    changed={p for p in selected["files"] if selected["files"][p]!=baseline["files"][p]}
    assert changed=={".github/workflows/default-poster-validation.yml"}
    assert selected["maintenance_context"]["phase3_previous_manifest_sha256"]==fingerprint(baseline)
    assert selected["maintenance_context"]["phase3_baseline_commit"]=="78464d2d051dc5da5f305bc4fd9f03868999636f"
    assert selected["historical_syntax_exceptions"]==baseline["historical_syntax_exceptions"]==[]
    assert protection.verify()["production_files_verified"]==190


def simulated_reports():
    data={"nodes":["fixture.py::test_required"],"exitstatus":0,"reports":[{
        "nodeid":"fixture.py::test_required","when":phase,"outcome":"passed","seconds":0,
        "wasxfail":False,"skip_reason":None} for phase in ["setup","call","teardown"]]}
    return [dict(head="head",plan_sha256="plan",platform=system,kind="phase3-foundations",success=True,
        ids_sha256="pin",schema_sha256="pin",collection={"nodes":data["nodes"],"exitstatus":0},execution=deepcopy(data),golden={"fixture":"hash"}) for system in ["Linux","Windows"]]


def verify(reports):
    def read(path):
        return ["fixture.py::test_required"] if path==phase3.IDS else {"fixture":"hash"}
    with patch.object(phase3,"identity",return_value={"head":"head","plan_sha256":"plan"}),patch.object(phase3,"read",side_effect=read),patch.object(phase3,"checksum",return_value="pin"):
        return phase3.verify_reports(reports)


def test_complete_focused_windows_linux_proof_is_accepted():
    result=verify(simulated_reports())
    assert set(result)=={"Linux","Windows"}


def test_actual_focused_producer_does_not_pollute_legacy_artifact_discovery(tmp_path,monkeypatch):
    """Exercise both producer paths and the real aggregate report selector."""
    from ci.validation import write
    from create_defaults.phase3.tests.samples import bundle
    expected=simulated_reports()[0]
    legacy={"kind":"collection","platform":"Linux","original":["legacy::test"]}
    write(tmp_path/"collection-ubuntu-latest/collection.json",legacy)
    actual_golden={d.KIND:d.sha256 for d in bundle()}
    def collected(paths,destination,collect=False):
        data=expected["collection"] if collect else expected["execution"]
        write(destination,data)
        return data
    def selected(path):
        return expected["collection"]["nodes"] if path==phase3.IDS else actual_golden
    monkeypatch.setattr(phase3,"OUT",tmp_path/"phase3-foundations-ubuntu-latest")
    monkeypatch.setattr(phase3,"identity",lambda:{"head":"head","platform":"Linux","plan_sha256":"plan"})
    monkeypatch.setattr(phase3,"checksum",lambda path:"pin")
    monkeypatch.setattr(phase3,"read",selected)
    monkeypatch.setattr(phase3,"pytest_run",collected)
    phase3.run()
    assert validation.legacy_reports(tmp_path)==[legacy]
    reports=[json.loads(p.read_text()) for p in tmp_path.rglob("phase3-report.json")]
    assert len(reports)==1 and reports[0]["success"]
    assert reports[0]["execution"]["nodes"]==expected["execution"]["nodes"]


@pytest.mark.parametrize("mutation",["missing","duplicate-platform","head","plan_sha256","ids_sha256","schema_sha256","success","golden","missing-collection-id","missing-execution-id","missing-call","xfail","skip","collection-interrupted"])
def test_missing_cancelled_stale_substituted_or_incomplete_focused_proof_fails(mutation):
    reports=simulated_reports()
    if mutation=="missing":reports.pop()
    elif mutation=="duplicate-platform":reports[1]["platform"]="Linux"
    elif mutation in ["head","plan_sha256","ids_sha256","schema_sha256"]:reports[0][mutation]="stale"
    elif mutation=="success":reports[0]["success"]=False
    elif mutation=="golden":reports[0]["golden"]={"different":"hash"}
    elif mutation=="missing-collection-id":reports[0]["collection"]["nodes"]=["fixture.py::other_same_count"]
    elif mutation=="missing-execution-id":reports[0]["execution"]["nodes"]=["fixture.py::other_same_count"]
    elif mutation=="missing-call":reports[0]["execution"]["reports"].pop(1)
    elif mutation=="xfail":reports[0]["execution"]["reports"][1]["wasxfail"]=True
    elif mutation=="skip":reports[0]["execution"]["reports"][1].update(outcome="skipped",skip_reason="not an accepted substitute")
    else:reports[0]["collection"]["exitstatus"]=2
    with pytest.raises(ValueError):verify(reports)


@pytest.mark.parametrize("status",["failure","cancelled","skipped",None])
def test_existing_mandatory_acceptance_cannot_ignore_focused_job(status):
    needs={n:{"result":"success"} for n in ["collection","validation","phase3"]}
    needs["phase3"]["result"]=status
    with pytest.raises(ValueError):validation.require_jobs(needs)


def test_frozen_schema_and_existing_test_id_snapshots_are_unchanged():
    changed=subprocess.check_output(["git","diff","--name-only","78464d2d051dc5da5f305bc4fd9f03868999636f"],cwd=ROOT,text=True).splitlines()
    assert not any(p.startswith("create_defaults/bulk/contracts/schemas/") for p in changed)
    assert "ci/original-test-ids.json" not in changed
    assert "ci/validation-plan.json" not in changed
