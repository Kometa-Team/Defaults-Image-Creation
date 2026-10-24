"""Mandatory M5 groups cannot be dropped, substituted or made optional."""
from copy import deepcopy
from unittest.mock import patch
import json
import subprocess

import pytest

from ci import phase4_transactions as m5


def rows():
    groups={g:['create_defaults/phase4/tests/test_transactions.py::'+g] for g in m5.JOBS}
    reports=[]
    for platform in ('Windows','Linux'):
        for group,ids in groups.items():
            reports.append(dict(head='head',platform=platform,plan_sha256='plan',kind='phase4-m5-execution',success=True,
                group=group,ids_sha256='pin',schema_sha256='pin',implementation_sha256='code',collection=dict(nodes=ids,exitstatus=0),
                execution=dict(nodes=ids,exitstatus=0,seconds=1,reports=[dict(nodeid=i,when=p,outcome='passed',seconds=0,wasxfail=False,skip_reason=None) for i in ids for p in ('setup','call','teardown')])))
    return groups,reports


@pytest.mark.parametrize('attack',['missing','duplicate','head','plan','failure','ids','schema','code','collection','execution','skipped','xfail','cancelled'])
def test_missing_or_substituted_group_evidence_fails_closed(attack):
    groups,reports=rows();r=reports[0]
    if attack=='missing':reports.pop()
    elif attack=='duplicate':reports[-1]=deepcopy(r)
    elif attack in {'head','plan','ids','schema','code'}:
        r[{'plan':'plan_sha256','ids':'ids_sha256','schema':'schema_sha256','code':'implementation_sha256'}.get(attack,attack)]='changed'
    elif attack=='failure':r['success']=False
    elif attack in {'collection','execution'}:r[attack]['nodes']=[]
    elif attack=='skipped':r['execution']['reports'][1].update(outcome='skipped',skip_reason='not accepted')
    elif attack=='xfail':r['execution']['reports'][1]['wasxfail']=True
    else:r['execution']['exitstatus']=2
    with patch.object(m5,'baseline'),patch.object(m5,'verify_maintenance'),patch.object(m5,'identity',return_value=dict(head='head',plan_sha256='plan')),patch.object(m5,'checksum',return_value='pin'),patch.object(m5,'implementation_checksum',return_value='code'),patch.object(m5,'selections',return_value=groups):
        with pytest.raises(ValueError):m5.verify_reports(reports)


def test_original_sources_assertions_and_ids_remain_frozen():
    m5.baseline()
    m5.verify_maintenance()


@pytest.mark.parametrize('attack',['missing-original','missing-m5','extra-command','changed-original-selection'])
def test_plan_extension_is_closed_to_exact_mandatory_commands(attack):
    base=json.loads(subprocess.check_output(['git','show',m5.BASE+':ci/validation-plan.json'],cwd=m5.ROOT))
    current=deepcopy(m5.read(m5.ROOT/'ci/validation-plan.json'))
    if attack=='missing-original':current['commands']['core'].pop(0)
    elif attack=='missing-m5':current['commands']['smoke'].pop()
    elif attack=='extra-command':current['commands']['core'].append(['unapproved'])
    else:current['pytest_groups']['generation'].pop()
    with patch.object(m5,'read',return_value=current):
        with pytest.raises(ValueError):m5.verify_plan(base)


def native_rows():
    proofs=[];pixels=[]
    for platform in ('Windows','Linux'):
        p=dict(head='head',platform=platform,plan_sha256='plan',kind='phase4-m5-native-transaction-proof',
            schema_sha256='pin',implementation_sha256='code',isolated_committed=True,restart_verified=True,retry_verified=True,
            members={'genre.fixture':{'sha256':'a'*64}},appearance='requested',cohort='genre',contract_approvals_missing=22,
            authenticated=False,operation_accepted=False,applied=False,ready=False,active=False,publication_authorized=False,contract_approved=False)
        p['sha256']=m5.fingerprint(p);proofs.append(p)
        pixels.append(dict(head='head',platform=platform,plan_sha256='plan',groups={'genre':{'views':[dict(appearance='requested',members={'genre.fixture':'a'*64})]}}))
    return proofs,pixels


@pytest.mark.parametrize('attack',['missing','head','schema','code','real','incomplete','retry','restart','contracts','member','pixel','hash'])
def test_commit_proof_requires_independent_exact_native_bytes(attack):
    proofs,pixels=native_rows();p=proofs[0]
    if attack=='missing':proofs.pop()
    elif attack in {'head','schema','code'}:p[{'schema':'schema_sha256','code':'implementation_sha256'}.get(attack,attack)]='changed'
    elif attack=='real':p['operation_accepted']=True
    elif attack=='incomplete':p['isolated_committed']=False
    elif attack=='retry':p['retry_verified']=False
    elif attack=='restart':p['restart_verified']=False
    elif attack=='contracts':p['contract_approvals_missing']=0
    elif attack=='member':p['members']['genre.fixture']['sha256']='b'*64
    elif attack=='pixel':pixels.pop(0)
    if attack=='hash':p['sha256']='0'*64
    else:p['sha256']=m5.fingerprint({k:v for k,v in p.items() if k!='sha256'})
    with patch.object(m5,'identity',return_value=dict(head='head',plan_sha256='plan')),patch.object(m5,'checksum',return_value='pin'),patch.object(m5,'implementation_checksum',return_value='code'):
        with pytest.raises(ValueError):m5.verify_native_proofs(proofs,pixels)


def test_complete_native_proof_remains_synthetic_only():
    proofs,pixels=native_rows()
    with patch.object(m5,'identity',return_value=dict(head='head',plan_sha256='plan')),patch.object(m5,'checksum',return_value='pin'),patch.object(m5,'implementation_checksum',return_value='code'):
        assert set(m5.verify_native_proofs(proofs,pixels))=={'Windows','Linux'}
