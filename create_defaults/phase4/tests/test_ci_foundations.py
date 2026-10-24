"""Mandatory Phase 4 producer/aggregate rejection and authorized maintenance."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from ci import phase4,validation
from create_defaults.bulk.common import fingerprint


def reports():
    data=dict(nodes=['fixture.py::test_required'],exitstatus=0,reports=[
        dict(nodeid='fixture.py::test_required',when=phase,outcome='passed',seconds=0,wasxfail=False,skip_reason=None)
        for phase in ['setup','call','teardown']])
    return [dict(head='head',plan_sha256='plan',platform=system,kind='phase4-operation-foundations',success=True,
        ids_sha256='pin',schema_sha256='pin',golden_sha256='pin',canonical_sha256='golden',
        m2_schema_sha256='pin',m2_golden_sha256='pin',m2_canonical_sha256='golden',
        collection=dict(nodes=data['nodes'],exitstatus=0),execution=deepcopy(data)) for system in ['Linux','Windows']]


def verify(values):
    def read(path):return ['fixture.py::test_required'] if path==phase4.IDS else {'archive_sha256':'golden'}
    with patch.object(phase4,'identity',return_value=dict(head='head',plan_sha256='plan')),patch.object(phase4,'read',side_effect=read),patch.object(phase4,'checksum',return_value='pin'),patch.object(phase4,'verify_historical_reports',return_value=phase4.M2_HISTORICAL):
        return phase4.verify_reports(values)


def test_complete_windows_linux_phase4_evidence_is_required_and_verified():
    assert set(verify(reports()))=={'Windows','Linux'}


@pytest.mark.parametrize('mutation',['missing','duplicate-platform','head','plan_sha256','ids_sha256','schema_sha256',
    'golden_sha256','canonical_sha256','success','kind','missing-collection','missing-execution','missing-call',
    'duplicate-call','failed-call','skip','xfail','interrupted-collection','interrupted-execution'])
def test_missing_stale_forged_or_incomplete_new_focused_proof_cannot_satisfy_acceptance(mutation):
    values=reports()
    if mutation=='missing':values.pop()
    elif mutation=='duplicate-platform':values[1]['platform']='Linux'
    elif mutation in {'head','plan_sha256','ids_sha256','schema_sha256','golden_sha256','canonical_sha256','kind'}:values[0][mutation]='substituted'
    elif mutation=='success':values[0]['success']=False
    elif mutation=='missing-collection':values[0]['collection']['nodes']=['fixture.py::wrong_same_count']
    elif mutation=='missing-execution':values[0]['execution']['nodes']=['fixture.py::wrong_same_count']
    elif mutation=='missing-call':values[0]['execution']['reports'].pop(1)
    elif mutation=='duplicate-call':values[0]['execution']['reports'].append(deepcopy(values[0]['execution']['reports'][1]))
    elif mutation=='failed-call':values[0]['execution']['reports'][1]['outcome']='failed'
    elif mutation=='skip':values[0]['execution']['reports'][1].update(outcome='skipped',skip_reason='not acceptable')
    elif mutation=='xfail':values[0]['execution']['reports'][1]['wasxfail']=True
    elif mutation=='interrupted-collection':values[0]['collection']['exitstatus']=2
    else:values[0]['execution']['exitstatus']=2
    with pytest.raises(ValueError):verify(values)


@pytest.mark.parametrize('status',['failure','cancelled','skipped',None,'missing'])
def test_no_phase4_job_failure_cancellation_or_omission_has_an_optional_success_path(status):
    needs={n:{'result':'success'} for n in ['collection','validation','phase3','phase4']}
    if status=='missing':needs.pop('phase4')
    else:needs['phase4']['result']=status
    with pytest.raises(ValueError):validation.require_jobs(needs)


def test_actual_phase4_producer_names_do_not_pollute_any_earlier_artifact_selector(tmp_path,monkeypatch):
    fixture=reports()[0];archive={'synthetic':'only'};canonical=fingerprint(archive)
    out=tmp_path/'phase4-foundations-ubuntu-latest'
    validation.write(tmp_path/'collection-ubuntu-latest/collection.json',{'kind':'collection'})
    def selected(path):
        if path==phase4.IDS:return fixture['execution']['nodes']
        if path in {phase4.GOLDEN,phase4.M2_GOLDEN}:return dict(archive=archive,archive_sha256=canonical)
        return validation.read(path)
    def execute(paths,destination,collect=False):
        data=fixture['collection'] if collect else fixture['execution'];validation.write(destination,data);return data
    monkeypatch.setattr(phase4,'OUT',out);monkeypatch.setattr(phase4,'read',selected)
    monkeypatch.setattr(phase4,'identity',lambda:dict(head='head',platform='Linux',plan_sha256='plan'))
    monkeypatch.setattr(phase4,'checksum',lambda path:'pin');monkeypatch.setattr(phase4,'verify_maintenance',lambda:None)
    monkeypatch.setattr(phase4,'pytest_run',execute)
    validation.write(out/'phase4-canonical.json',dict(head='head',platform='Linux',plan_sha256='plan',evidence=archive,evidence_sha256=canonical))
    validation.write(out/'phase4-m2-canonical.json',dict(head='head',platform='Linux',plan_sha256='plan',evidence_sha256=canonical))
    phase4.run()
    assert validation.legacy_reports(tmp_path)==[{'kind':'collection'}]
    assert len(list(tmp_path.rglob('phase4-report.json')))==1 and validation.read(out/'phase4-report.json')['success']
    assert not list(out.glob('phase3-*'))


def test_exact_authorized_bridge_workflow_and_provenance_maintenance_is_verified():
    assert set(phase4.verify_maintenance()['files'])==phase4.MAINTAINED


def test_aggregate_maintenance_verifier_works_without_any_runtime_site_packages():
    result=subprocess.run([sys.executable,'-S','-c',
        "from ci.phase4 import verify_maintenance; verify_maintenance(); print('stdlib-only-verified')"],
        cwd=phase4.ROOT,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='stdlib-only-verified'
    value=phase4.read(phase4.ROOT/'ci/phase4-maintenance.json')
    assert phase4.fingerprint(value)==fingerprint(value)


@pytest.mark.parametrize('mutation',['unexpected-maintenance-file','substituted-maintenance-pin','changed-current-source','wrong-baseline'])
def test_maintenance_cannot_waive_additional_source_or_pin_changes(monkeypatch,mutation):
    original_read=phase4.read;value=deepcopy(original_read(phase4.ROOT/'ci/phase4-maintenance.json'))
    if mutation=='unexpected-maintenance-file':
        value['files']['create_defaults/create_poster.py']=dict(before_sha256='f'*64,sha256='f'*64)
        monkeypatch.setattr(phase4,'MAINTENANCE_PIN',fingerprint(value))
    elif mutation=='substituted-maintenance-pin':value['kind']='unapproved'
    elif mutation=='wrong-baseline':
        value['base']='f'*40;monkeypatch.setattr(phase4,'MAINTENANCE_PIN',fingerprint(value))
    else:
        original_checksum=phase4.checksum
        monkeypatch.setattr(phase4,'checksum',lambda path:'f'*64 if path==phase4.ROOT/'ci/validation.py' else original_checksum(path))
    monkeypatch.setattr(phase4,'read',lambda path:value if path.name=='phase4-maintenance.json' else original_read(path))
    with pytest.raises(ValueError):phase4.verify_maintenance()
