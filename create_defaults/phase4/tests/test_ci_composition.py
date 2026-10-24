"""Mandatory M3 groups cannot be omitted, stale or selectively accepted."""
from copy import deepcopy
import subprocess
import sys
from unittest.mock import patch

import pytest
from ci import phase4_composition as m3


def reports():
    groups={'pixels':['composition::pixels'],'security':['composition::security']};reports=[]
    for platform in ['Windows','Linux']:
        for group,ids in groups.items():
            execution=dict(nodes=ids,exitstatus=0,seconds=1,reports=[dict(nodeid=ids[0],when=p,outcome='passed',seconds=0,wasxfail=False,skip_reason=None) for p in ('setup','call','teardown')])
            reports.append(dict(head='head',plan_sha256='plan',platform=platform,group=group,kind='phase4-m3-group',success=True,ids_sha256='pin',schema_sha256='pin',implementation_sha256='code',collection=dict(nodes=ids,exitstatus=0),execution=execution,pixels=dict(groups={k:dict(views=[dict(appearance=a,members={k:'a'*64}) for a in ('default','requested')]) for k in m3.KINDS})))
    return groups,reports


def verify(rows):
    groups,_=reports()
    with patch.object(m3,'selections',return_value=groups),patch.object(m3,'identity',return_value=dict(head='head',plan_sha256='plan')),patch.object(m3,'checksum',return_value='pin'),patch.object(m3,'implementation_checksum',return_value='code'),patch.object(m3,'verify_pixels',side_effect=lambda r,_:r):
        return m3.verify_reports(rows)


@pytest.mark.parametrize('attack',['missing','duplicate','head','plan','failure','ids','schema','implementation','collection','execution','skip','xfail','cancelled'])
def test_m3_missing_or_forged_execution_cannot_satisfy_acceptance(attack):
    _,rows=reports();r=rows[0]
    if attack=='missing':rows.pop()
    elif attack=='duplicate':rows[0]=deepcopy(rows[1])
    elif attack=='head':r['head']='stale'
    elif attack=='plan':r['plan_sha256']='stale'
    elif attack=='failure':r['success']=False
    elif attack in {'ids','schema','implementation'}:r[attack+'_sha256']='wrong'
    elif attack=='collection':r['collection']['nodes']=['different::same_count']
    elif attack=='execution':r['execution']['reports'].pop(1)
    elif attack=='skip':r['execution']['reports'][1]['outcome']='skipped'
    elif attack=='xfail':r['execution']['reports'][1]['wasxfail']=True
    else:r['execution']['exitstatus']=2
    with pytest.raises(ValueError):verify(rows)


def test_complete_cross_platform_byte_comparison_is_explicit_not_a_reuse_grant():
    _,rows=reports();rows[0]['pixels']['groups']['playlist']['views'][0]['members']['playlist']='b'*64
    result=verify(rows)
    assert result['cross_platform']['different']==1 and result['cross_platform']['exact']==9
    assert result['cross_platform']['reuse']=='blocked-across-environments-even-if-bytes-match'


def test_m3_schema_and_group_verifier_have_no_runtime_dependency_or_optional_path():
    result=subprocess.run([sys.executable,'-S','-c',
        'from ci.phase4_composition import selections,implementation_checksum; selections(); print(implementation_checksum())'],cwd=m3.ROOT,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()==m3.implementation_checksum()
    groups=m3.selections();assert not set(groups['pixels'])&set(groups['security'])


@pytest.mark.parametrize('attack',['extra-command','missing-M3','missing-original','changed-selection','changed-original','extra-maintenance','changed-maintenance-source'])
def test_narrow_ci_maintenance_cannot_relax_original_plan_or_expand_scope(attack):
    from ci import phase4
    original=subprocess.check_output(['git','show',phase4.M2_BASE+':ci/validation-plan.json'],cwd=m3.ROOT)
    current=deepcopy(phase4.read(m3.ROOT/'ci/validation-plan.json'))
    if attack=='extra-command':current['commands']['people'].append(['unapproved'])
    elif attack=='missing-M3':current['commands']['people']=[]
    elif attack=='missing-original':current['commands']['core'].pop()
    elif attack=='changed-selection':current['pytest_groups']['people'].pop()
    elif attack=='changed-original':original+=b'\n'
    elif attack=='extra-maintenance':
        value=deepcopy(phase4.read(m3.ROOT/'ci/phase4-m3-maintenance.json'));value['files']['create_defaults/create_poster.py']={}
        with patch.object(phase4,'read',return_value=value),patch.object(phase4,'M3_MAINTENANCE_PIN',phase4.fingerprint(value)):
            with pytest.raises(ValueError):phase4.verify_m3_maintenance()
        return
    else:
        with patch.object(phase4,'checksum',return_value='0'*64):
            with pytest.raises(ValueError):phase4.verify_m3_maintenance()
        return
    with patch.object(phase4,'read',return_value=current):
        with pytest.raises(ValueError):phase4.verify_original_plan(original)
