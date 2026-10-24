"""M4 proof is mandatory, exact-head and bound to independent native pixels."""
from copy import deepcopy
from unittest.mock import patch

import pytest

from ci import phase4_review as review


def proof(platform):
    r=dict(head='head',platform=platform,plan_sha256='plan',kind='phase4-m4-complete-review-proof',
        schema_sha256='schema',implementation_sha256='code',authenticated=False,ready=False,
        active=False,publication_authorized=False,contract_approvals_missing=22,
        states=['PREVIEWS_COMPLETE','SUBMITTER_CONFIRMED','MAINTAINER_APPROVED'],
        submitter='synthetic.actor.submitter',maintainer='synthetic.actor.maintainer',attribution='synthetic-only',
        all_encoded_bytes_verified=True,immutable_reopen_verified=True,cohort='playlist',
        members={a:{'member':'a'*64} for a in ['default','requested']})
    r['sha256']=review.fingerprint(r)
    return r


def verify(rows):
    pixels=[dict(platform=p,groups={'playlist':dict(views=[dict(appearance=a,members={'member':'a'*64}) for a in ['default','requested']])}) for p in ['Windows','Linux']]
    with patch.object(review,'identity',return_value=dict(head='head',plan_sha256='plan')),patch.object(review,'checksum',return_value='schema'),patch.object(review,'implementation_checksum',return_value='code'):
        return review.verify_reports(rows,pixels)


@pytest.mark.parametrize('attack',['missing','duplicate','head','plan','code','schema','states','same-actor','real','membership','unchecked','reopen','grant','hash'])
def test_missing_stale_or_rehashed_m4_proof_cannot_satisfy_acceptance(attack):
    rows=[proof('Windows'),proof('Linux')];r=rows[0]
    if attack=='missing':rows.pop()
    elif attack=='duplicate':rows[1]=deepcopy(rows[0])
    elif attack=='head':r['head']='stale'
    elif attack=='plan':r['plan_sha256']='stale'
    elif attack=='code':r['implementation_sha256']='changed'
    elif attack=='schema':r['schema_sha256']='changed'
    elif attack=='states':r['states'].pop(1)
    elif attack=='same-actor':r['maintainer']=r['submitter']
    elif attack=='real':r['authenticated']=True
    elif attack=='membership':r['members']['default']['member']='b'*64
    elif attack=='unchecked':r['all_encoded_bytes_verified']=False
    elif attack=='reopen':r['immutable_reopen_verified']=False
    elif attack=='grant':r['contract_approvals_missing']=0
    if attack!='hash':r['sha256']=review.fingerprint({k:v for k,v in r.items() if k!='sha256'})
    else:r['sha256']='0'*64
    with pytest.raises(ValueError):verify(rows)


def test_complete_m4_proof_is_only_synthetic_and_requires_both_native_producers():
    assert set(verify([proof('Windows'),proof('Linux')]))=={'Windows','Linux'}


def test_m4_extension_keeps_every_m3_id_native_source_and_original_assertion():
    assert review.baseline()


def bounded_rows():
    groups={g:['create_defaults/phase4/tests/test_review.py::'+g] for g in ['states','evidence']}
    rows=[]
    for platform in ['Windows','Linux']:
        for group,ids in groups.items():
            node=ids[0]
            execution=dict(nodes=ids,exitstatus=0,seconds=1,reports=[dict(nodeid=node,when=p,outcome='passed',seconds=0,wasxfail=False,skip_reason=None) for p in ['setup','call','teardown']])
            rows.append(dict(head='head',platform=platform,group=group,plan_sha256='plan',kind='phase4-m4-review-execution',success=True,ids_sha256='pin',schema_sha256='pin',implementation_sha256='code',collection=dict(nodes=ids,exitstatus=0),execution=deepcopy(execution)))
    return groups,rows


@pytest.mark.parametrize('attack',['missing','head','plan','selection','schema','code','failed','skipped','missing-call','omitted-node','missing-states','missing-evidence','duplicate-group'])
def test_m4_bounded_execution_is_mandatory_and_exact(attack):
    groups,rows=bounded_rows()
    r=rows[0]
    if attack=='missing':rows.pop()
    elif attack=='head':r['head']='stale'
    elif attack=='plan':r['plan_sha256']='stale'
    elif attack=='selection':r['ids_sha256']='other'
    elif attack=='schema':r['schema_sha256']='other'
    elif attack=='code':r['implementation_sha256']='other'
    elif attack=='failed':r['success']=False
    elif attack=='skipped':r['execution']['reports'][1].update(outcome='skipped',skip_reason='not accepted')
    elif attack=='missing-call':r['execution']['reports'].pop(1)
    elif attack=='omitted-node':r['execution']['nodes']=[]
    elif attack=='missing-states':rows=[r for r in rows if r['group']!='states']
    elif attack=='missing-evidence':rows=[r for r in rows if r['group']!='evidence']
    else:rows[1]=deepcopy(rows[0])
    with patch.object(review,'selections',return_value=groups),patch.object(review,'identity',return_value=dict(head='head',plan_sha256='plan')),patch.object(review,'checksum',return_value='pin'),patch.object(review,'implementation_checksum',return_value='code'):
        with pytest.raises(ValueError):review.verify_group_reports(rows)


def test_both_m4_bounded_partitions_require_independent_execution_on_both_platforms():
    groups,rows=bounded_rows()
    with patch.object(review,'selections',return_value=groups),patch.object(review,'identity',return_value=dict(head='head',plan_sha256='plan')),patch.object(review,'checksum',return_value='pin'),patch.object(review,'implementation_checksum',return_value='code'):
        result=review.verify_group_reports(rows)
        assert {p:set(v) for p,v in result.items()}=={'Windows':{'states','evidence'},'Linux':{'states','evidence'}}


def test_m4_maintenance_is_exactly_one_additive_command_and_no_production_source():
    from ci import phase4
    assert set(review.verify_maintenance()['files'])=={'ci/validation-plan.json'}
    phase4.verify_m3_maintenance()


@pytest.mark.parametrize('attack',['missing-M4','missing-evidence-command','extra-command','removed-original','extra-source','wrong-base','before-hash','after-hash'])
def test_bounded_m4_extension_cannot_expand_scope_or_relax_frozen_checks(attack):
    from ci import phase4
    if attack in {'missing-M4','missing-evidence-command','extra-command','removed-original'}:
        value=deepcopy(phase4.read(review.ROOT/'ci/validation-plan.json'))
        if attack=='missing-M4':value['commands']['contracts']=[]
        elif attack=='missing-evidence-command':value['commands']['generation']=[]
        elif attack=='extra-command':value['commands']['contracts'].append(['unapproved'])
        else:value['commands']['core'].pop()
        original=review.subprocess.check_output(['git','show',phase4.M2_BASE+':ci/validation-plan.json'],cwd=review.ROOT)
        with patch.object(phase4,'read',return_value=value):
            with pytest.raises(ValueError):phase4.verify_original_plan(original)
    else:
        value=deepcopy(review.read(review.ROOT/'ci/phase4-m4-maintenance.json'))
        if attack=='extra-source':value['files']['create_defaults/create_poster.py']={}
        elif attack=='wrong-base':value['base']='0'*40
        elif attack=='before-hash':value['files']['ci/validation-plan.json']['before_sha256']='0'*64
        else:value['files']['ci/validation-plan.json']['sha256']='0'*64
        with patch.object(review,'read',return_value=value),patch.object(review,'MAINTENANCE_PIN',review.fingerprint(value)):
            with pytest.raises(ValueError):review.verify_maintenance()
