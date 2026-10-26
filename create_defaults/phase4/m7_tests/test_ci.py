"""M7 reuses exact-ID/phase validation; incomplete evidence cannot pass."""
from copy import deepcopy
import json

import pytest

from ci import phase4_m7 as ci


def rows():
    groups, nodes = ci.selections()
    result = []
    for platform in ('Windows', 'Linux'):
        for group, selected in groups.items():
            execution = dict(nodes=selected, exitstatus=0, seconds=1, reports=[
                dict(nodeid=node, when=phase, outcome='passed', wasxfail=False, skip_reason=None)
                for node in selected for phase in ('setup', 'call', 'teardown')])
            result.append(dict(kind='phase4-m7-execution', success=True, head='head', plan_sha256='plan',
                platform=platform, group=group, ids_sha256=ci.checksum(ci.IDS),
                coverage_sha256=ci.checksum(ci.COVERAGE), implementation_sha256=ci.implementation(),
                preservation=dict(baseline_commit=ci.BASE, protected_members=190, adoption_sources=299,
                    unexplained_differences=0, production_activation=False, publication_authorized=False),
                all_collection=dict(nodes=sorted(nodes), exitstatus=0),
                collection=dict(nodes=selected, exitstatus=0), execution=execution))
    return deepcopy(result)


@pytest.mark.parametrize('attack', ['missing', 'duplicate', 'head', 'plan', 'failed', 'ids', 'coverage',
    'implementation', 'namespace', 'collection', 'execution', 'skip', 'xfail', 'incomplete', 'exit', 'preservation'])
def test_m7_rejects_missing_stale_or_incomplete_evidence(attack):
    reports = rows()
    row = reports[0]
    if attack == 'missing':
        reports.pop()
    elif attack == 'duplicate':
        reports[-1] = row
    elif attack in {'head', 'plan', 'ids', 'coverage', 'implementation'}:
        row[{'plan': 'plan_sha256', 'ids': 'ids_sha256', 'coverage': 'coverage_sha256',
             'implementation': 'implementation_sha256'}.get(attack, attack)] = 'changed'
    elif attack == 'failed':
        row['success'] = False
    elif attack in {'namespace', 'collection', 'execution'}:
        row[{'namespace': 'all_collection'}.get(attack, attack)]['nodes'].pop()
    elif attack == 'skip':
        row['execution']['reports'][0].update(outcome='skipped', skip_reason='cannot satisfy acceptance')
    elif attack == 'xfail':
        row['execution']['reports'][0]['wasxfail'] = True
    elif attack == 'incomplete':
        row['execution']['reports'].pop()
    elif attack == 'exit':
        row['execution']['exitstatus'] = 2
    else:
        row['preservation']['unexplained_differences'] = 1
    with pytest.raises(ValueError):
        ci.verify_reports(reports, dict(head='head', plan_sha256='plan'))


def test_m7_accepts_every_explicit_platform_group_and_no_other_ids():
    summary = ci.verify_reports(rows(), dict(head='head', plan_sha256='plan'))
    assert set(summary) == {'Windows', 'Linux'}
    assert all(set(value) == set(ci.GROUPS) for value in summary.values())
    assert sum(group['counts']['passed'] for group in summary['Windows'].values()) == len(ci.selections()[1])


@pytest.mark.parametrize('result', ['failure', 'cancelled', 'skipped', None])
def test_m7_failed_or_missing_matrix_cannot_reach_acceptance(monkeypatch, result):
    monkeypatch.setenv('M7_JOB_RESULTS', json.dumps({} if result is None else {'m7': {'result': result}}))
    with pytest.raises(ValueError, match='matrix'):
        ci.accept()


def test_m7_does_not_modify_original_workflow_source_or_historical_evidence():
    result = ci.preservation()
    assert result['protected_members'] == 190 and result['adoption_sources'] == 299
    assert result['existing_files_checked'] == 2927 and result['unexplained_differences'] == 0
    assert not result['production_activation'] and not result['publication_authorized']


def test_t01_through_t22_have_maintained_ids_and_explicit_expected_boundaries():
    value = ci.coverage()
    assert len(value['requirements']) == 22
    assert all(row['expected_result'] and row['boundary'] for row in value['requirements'])


def test_m7_workflow_keeps_exact_head_readonly_limits_and_mandatory_groups():
    import yaml
    value = yaml.safe_load((ci.ROOT/'.github/workflows/lifecycle-m7-validation.yml').read_text())
    assert value['permissions'] == {'contents': 'read'}
    assert value['jobs']['acceptance']['needs'] == ['m7']
    assert value['jobs']['acceptance']['if'] == '${{ always() }}'
    assert value['jobs']['m7']['strategy']['fail-fast'] is False
    assert set(value['jobs']['m7']['strategy']['matrix']['group']) == set(ci.GROUPS)
    for job in value['jobs'].values():
        assert job['timeout-minutes'] == 15 and 'continue-on-error' not in job
        assert job['env']['EXPECTED_HEAD'] == '${{ github.event.pull_request.head.sha }}'
        checkout = next(step for step in job['steps'] if step.get('uses', '').startswith('actions/checkout@'))
        assert checkout['with']['ref'] == '${{ github.event.pull_request.head.sha }}'
        assert checkout['with']['persist-credentials'] is False


def native_rows(tmp_path):
    import hashlib
    proofs = []
    artifacts = {}
    for platform in ('Windows', 'Linux'):
        parent = tmp_path/platform
        (parent/'artwork').mkdir(parents=True)
        members = {}
        for name in ('add', 'update'):
            raw = ('unit evidence: '+name).encode()
            (parent/'artwork'/(name+'.jpg')).write_bytes(raw)
            members[name+'_artwork'] = dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
        proof = dict(head='head', plan_sha256='plan', platform=platform, kind='phase4-m7-native-sequence',
            operations=['ADD', 'UPDATE', 'RENAME', 'DELETE'], cold_restart_verified=True,
            exact_retries_verified=True, history_retained=True, isolated_only=True,
            permanent_id='retired', unrelated_record_sha256='b'*64, unrelated_record_preserved=True, active_members=[],
            mapping_plans=['rename', 'delete'], tombstone_sha256='a'*64, **members,
            **{key: False for key in ('authenticated', 'operation_accepted', 'applied', 'artwork_approved',
                'contract_approved', 'ready', 'active', 'production_enforcement', 'publication_authorized')})
        proof['sha256'] = ci.fingerprint(proof)
        proofs.append(proof)
        artifacts[platform] = parent
    return proofs, artifacts


@pytest.mark.parametrize('attack', ['missing', 'head', 'sequence', 'real', 'retry', 'material',
    'retention', 'tombstone', 'artifact', 'missing-artifact', 'hash'])
def test_native_acceptance_rejects_incomplete_or_substituted_sequence(tmp_path, attack):
    proofs, artifacts = native_rows(tmp_path)
    proof = proofs[0]
    if attack == 'missing':
        proofs.pop()
    elif attack == 'head':
        proof['head'] = 'stale'
    elif attack == 'sequence':
        proof['operations'].pop()
    elif attack == 'real':
        proof['ready'] = True
    elif attack == 'retry':
        proof['exact_retries_verified'] = False
    elif attack == 'material':
        proof['update_artwork'] = proof['add_artwork']
    elif attack == 'retention':
        proof['active_members'].append(proof['permanent_id'])
    elif attack == 'tombstone':
        proof['tombstone_sha256'] = None
    elif attack == 'artifact':
        (artifacts['Windows']/'artwork/add.jpg').write_bytes(b'substituted')
    elif attack == 'missing-artifact':
        (artifacts['Windows']/'artwork/add.jpg').unlink()
    if attack == 'hash':
        proof['sha256'] = '0'*64
    else:
        proof['sha256'] = ci.fingerprint({key: value for key, value in proof.items() if key != 'sha256'})
    with pytest.raises(ValueError):
        ci.verify_native(proofs, dict(head='head', plan_sha256='plan'), artifacts)


def test_native_acceptance_binds_both_exported_platform_artifacts(tmp_path):
    proofs, artifacts = native_rows(tmp_path)
    assert set(ci.verify_native(proofs, dict(head='head', plan_sha256='plan'), artifacts)) == {'Windows', 'Linux'}
