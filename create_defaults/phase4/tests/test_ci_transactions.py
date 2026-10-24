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


def test_response_file_collects_every_id_beyond_windows_command_limit(tmp_path):
    from ci import phase4
    from ci.validation import pytest_run
    ids=phase4.read(phase4.IDS)
    assert len(' '.join(ids))>32768
    path=tmp_path/'exact ids.txt'
    path.write_text('\n'.join(ids)+'\n',encoding='utf8',newline='\n')
    result=pytest_run(['@'+str(path)],tmp_path/'response-collection.json',collect=True)
    assert result['exitstatus']==0 and len(result['nodes'])==len(ids)
    assert set(result['nodes'])==set(ids)


@pytest.fixture
def maintenance_copy(tmp_path, monkeypatch):
    """Copy only approved CI files; baseline reads still use the real Git tree."""
    manifest=m5.read(m5.ROOT/'ci/phase4-m5-maintenance.json')
    security=m5.read(m5.ROOT/'ci/people-security-maintenance.json')
    pins=m5.read(m5.ROOT/'create_defaults/bulk/contracts/activation/data/production-pins-v1.json')
    extra={'ci/people-security-maintenance.json','ci/people_security_maintenance.py',
        'ci/validation-plan.json','ci/original-test-ids.json','ci/phase3-test-ids.json','ci/phase4-test-ids.json',
        'ci/phase4-composition-test-ids.json','ci/phase4-review-test-ids.json','ci/phase4-transaction-test-ids.json',
        'ci/phase4-maintenance.json','ci/phase4-m3-maintenance.json','ci/phase4-m4-maintenance.json','ci/phase4-m5-maintenance.json'}
    copied=set(manifest['files'])|set(security['files'])|set(security['additions'])|set(pins['files'])|extra
    for name in sorted(copied):
        target=tmp_path/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((m5.ROOT/name).read_bytes())
    original=subprocess.check_output
    def baseline_output(args,**kwargs):
        assert args[:2]==['git','show'] and args[2].split(':',1)[0] in {m5.BASE,'46e1334504fcdd598e0c34fcd45612ff58e91074'}
        return original(args,cwd=m5.ROOT)
    monkeypatch.setattr(m5.subprocess,'check_output',baseline_output)
    m5.verify_maintenance(tmp_path)
    return tmp_path,manifest


@pytest.mark.parametrize('name',[
    'ci/validation-plan.json',
    '.github/workflows/default-poster-validation.yml',
    'create_defaults/bulk/contracts/activation/protection.py',
    'create_defaults/bulk/contracts/activation/data/production-pins-v1.json',
])
def test_ci_exception_rejects_any_unapproved_file_bytes(maintenance_copy,name):
    root,_=maintenance_copy
    with (root/name).open('ab') as stream:stream.write(b'\n# unexpected modification\n')
    with pytest.raises(ValueError,match='Changed exact M5 CI-only maintenance'):
        m5.verify_maintenance(root)


@pytest.mark.parametrize('attack',['extra-file','missing-file','baseline','hash'])
def test_ci_exception_manifest_cannot_expand_its_own_authority(maintenance_copy,attack):
    root,value=maintenance_copy
    if attack=='extra-file':value['files']['create_defaults/grayscale_sweeper.py']={}
    elif attack=='missing-file':value['files'].pop('ci/validation-plan.json')
    elif attack=='baseline':value['base']='0'*40
    else:value['files']['ci/validation-plan.json']['sha256']='0'*64
    (root/'ci/phase4-m5-maintenance.json').write_text(json.dumps(value),encoding='utf8')
    with pytest.raises(ValueError,match='Unexpected M5 CI-only protected extension'):
        m5.verify_maintenance(root)


@pytest.mark.parametrize('attack',['runtime-pin','membership','provenance','protection-algorithm','activation-import'])
def test_even_resealed_ci_metadata_cannot_change_protection(maintenance_copy,monkeypatch,attack):
    root,value=maintenance_copy
    name='create_defaults/bulk/contracts/activation/data/production-pins-v1.json'
    pins=m5.read(root/name)
    if attack in {'protection-algorithm','activation-import'}:
        name='create_defaults/bulk/contracts/activation/protection.py'
        with (root/name).open('ab') as stream:
            stream.write(b'\nimport create_defaults.bulk.contracts.activation.controller\n'
                if attack=='activation-import' else b'\nUNAPPROVED_PROTECTION_CHANGE = True\n')
    else:
        if attack=='runtime-pin':
            target=next(p for p in pins['files'] if not p.startswith('.github/'))
            pins['files'][target]='0'*64
        elif attack=='membership':pins['files'].pop(next(iter(pins['files'])))
        else:pins['maintenance_context']['phase4_m5_previous_manifest_sha256']='0'*64
        (root/name).write_text(json.dumps(pins),encoding='utf8')
    value['files'][name]['sha256']=m5.checksum(root/name)
    (root/'ci/phase4-m5-maintenance.json').write_text(json.dumps(value),encoding='utf8')
    # Exercise structural defenses independently of the exact, immutable outer
    # pin. Production never accepts a caller-provided pin or compatibility flag.
    monkeypatch.setattr(m5,'MAINTENANCE_PIN',m5.fingerprint(value))
    with pytest.raises(ValueError):m5.verify_maintenance(root)


def test_native_m5_collection_cannot_pollute_original_report_selection(tmp_path):
    from ci import validation
    def execute(ids,destination,collect=False):
        value=dict(nodes=ids,exitstatus=0,seconds=1,reports=[] if collect else [
            dict(nodeid=i,when=p,outcome='passed',seconds=0,wasxfail=False,skip_reason=None)
            for i in ids for p in ('setup','call','teardown')])
        validation.write(destination,value)
        return value
    with patch.object(m5,'OUT',tmp_path/'phase4-m5'),patch.object(m5,'pytest_run',side_effect=execute):
        m5.run('security')
    report=validation.read(tmp_path/'phase4-m5/security/phase4-m5-execution-report.json')
    assert report['success'] and len(report['collection']['nodes'])==40
    assert validation.legacy_reports(tmp_path)==[]
    original={'kind':'collection','head':'original'}
    validation.write(tmp_path/'original/collection.json',original)
    assert validation.legacy_reports(tmp_path)==[original]
