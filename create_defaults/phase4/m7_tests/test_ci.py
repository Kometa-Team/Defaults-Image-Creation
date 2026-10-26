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
    'retention', 'tombstone', 'artifact', 'missing-artifact', 'oversize-artifact', 'hash'])
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
    elif attack == 'oversize-artifact':
        with (artifacts['Windows']/'artwork/add.jpg').open('wb') as output:
            output.truncate(5*1024*1024+1)
    if attack == 'hash':
        proof['sha256'] = '0'*64
    else:
        proof['sha256'] = ci.fingerprint({key: value for key, value in proof.items() if key != 'sha256'})
    with pytest.raises(ValueError, match='Native artwork resource bound' if attack == 'oversize-artifact' else None):
        ci.verify_native(proofs, dict(head='head', plan_sha256='plan'), artifacts)


def test_native_acceptance_binds_both_exported_platform_artifacts(tmp_path):
    proofs, artifacts = native_rows(tmp_path)
    assert set(ci.verify_native(proofs, dict(head='head', plan_sha256='plan'), artifacts)) == {'Windows', 'Linux'}


@pytest.fixture
def scope_repository(tmp_path, monkeypatch):
    """Actual isolated Git metadata; never edit the implementation checkout."""
    import subprocess
    def create(existing=()):
        root = tmp_path/'scope'
        root.mkdir()
        def git(*args, data=None):
            return subprocess.check_output(['git', '-C', str(root), *args], input=data,
                                           stderr=subprocess.PIPE).decode().strip()
        git('init', '--quiet')
        git('config', 'user.name', 'Scope regression')
        git('config', 'user.email', 'scope@invalid.local')
        git('config', 'core.autocrlf', 'false')
        git('config', 'core.ignorecase', 'false')
        git('config', 'core.hooksPath', str(tmp_path/'no-hooks'))
        for name in ('README.md', *existing):
            path = root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('original\n', encoding='utf8')
        git('add', '--all')
        git('commit', '--quiet', '-m', 'isolated baseline')
        monkeypatch.setattr(ci, 'ROOT', root)
        monkeypatch.setattr(ci, 'BASE', git('rev-parse', 'HEAD'))
        return root, git
    return create


def test_planning_scope_keeps_original_baseline_and_exact_allowances():
    assert ci.BASE == '68179d1c568449375ca72b23239b57770dfc229e'
    assert len(ci.ALLOWED) == 15
    assert ci.PLANNING_DOCUMENTS == frozenset('create_defaults/lifecycle/'+name+'.md' for name in (
        'PHASE5_EXISTING_BEHAVIOUR_AUDIT', 'PHASE5_DESIGN_PROPOSAL',
        'PHASE5_OPERATION_AND_PUBLICATION_RULES', 'PHASE5_MILESTONE_PLAN', 'PHASE5_ACCEPTANCE_PLAN'))
    assert not ci.PLANNING_DOCUMENTS & ci.ALLOWED


@pytest.mark.parametrize('name', sorted(ci.PLANNING_DOCUMENTS), ids=lambda name: name.rsplit('/', 1)[1])
def test_planning_scope_accepts_each_exact_regular_addition(scope_repository, name):
    root, git = scope_repository()
    path = root/name
    path.parent.mkdir(parents=True)
    path.write_text('planning only\n', encoding='utf8')
    git('add', '--all')
    git('commit', '--quiet', '-m', 'planning addition')
    assert ci.changed_scope() == {name}


def test_planning_scope_accepts_complete_set_and_existing_status_paths(scope_repository):
    status = {'create_defaults/lifecycle/ROADMAP.md', 'create_defaults/lifecycle/PHASE5_PREREQUISITES.md'}
    root, git = scope_repository(status)
    for name in ci.PLANNING_DOCUMENTS | status:
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('planning status\n', encoding='utf8')
    git('add', '--all')
    git('commit', '--quiet', '-m', 'complete planning proposal')
    assert ci.changed_scope() == ci.PLANNING_DOCUMENTS | status


@pytest.mark.parametrize('name', [
    'create_defaults/bulk/lifecycle/apply.py', 'create_defaults/bulk/catalog/genre.yml',
    '.github/workflows/new-policy.yml', 'create_defaults/lifecycle/PHASE5_OTHER.md',
    'create_defaults/lifecycle/PHASE5_ACCEPTANCE_PLAN.MD'])
def test_planning_scope_rejects_unauthorized_source_yaml_and_other_paths(scope_repository, name):
    root, git = scope_repository((name,))
    (root/name).write_text('unauthorized change\n', encoding='utf8')
    git('add', '--all')
    git('commit', '--quiet', '-m', 'unauthorized change')
    with pytest.raises(ValueError, match='existing runtime, policy, workflow or evidence boundary'):
        ci.changed_scope()


@pytest.mark.parametrize('attack', ['modify', 'delete', 'rename', 'executable', 'git-symlink'])
def test_planning_scope_rejects_nonadditions_and_unsafe_git_modes(scope_repository, attack):
    name = 'create_defaults/lifecycle/PHASE5_ACCEPTANCE_PLAN.md'
    root, git = scope_repository((name,) if attack in {'modify', 'delete', 'rename'} else ())
    path = root/name
    if attack == 'delete':
        path.unlink()
    elif attack == 'rename':
        path.rename(root/'create_defaults/lifecycle/PHASE5_DESIGN_PROPOSAL.md')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('changed planning document\n', encoding='utf8')
    git('add', '--all')
    if attack == 'executable':
        git('update-index', '--chmod=+x', '--', name)
    elif attack == 'git-symlink':
        # Actual symlink Git object, portable without Windows symlink privilege.
        blob = git('hash-object', '-w', '--stdin', data=b'README.md')
        git('update-index', '--cacheinfo', '120000,'+blob+','+name)
    git('commit', '--quiet', '-m', 'nonadditive or unsafe document')
    with pytest.raises(ValueError, match='regular-file addition'):
        ci.changed_scope()


def test_planning_scope_rejects_existing_source_deletion(scope_repository):
    name = 'create_defaults/bulk/catalog/genre.yml'
    root, git = scope_repository((name,))
    (root/name).unlink()
    git('add', '--all')
    git('commit', '--quiet', '-m', 'forbidden catalog deletion')
    with pytest.raises(ValueError, match='existing runtime, policy, workflow or evidence boundary'):
        ci.changed_scope()


@pytest.mark.parametrize('attack', ['file-link', 'parent-link', 'reparse', 'directory'])
def test_planning_scope_rejects_unsafe_physical_checkout(scope_repository, monkeypatch, attack):
    from pathlib import Path
    import stat
    from types import SimpleNamespace
    name = 'create_defaults/lifecycle/PHASE5_ACCEPTANCE_PLAN.md'
    root, git = scope_repository()
    path = root/name
    path.parent.mkdir(parents=True)
    path.write_text('planning document\n', encoding='utf8')
    git('add', '--all')
    git('commit', '--quiet', '-m', 'regular Git addition')
    original = Path.lstat
    target = path.parent if attack == 'parent-link' else path
    def observed(part, *args, **kwargs):
        info = original(part, *args, **kwargs)
        if part != target:
            return info
        return SimpleNamespace(st_mode=stat.S_IFLNK if attack.endswith('link') else
                               stat.S_IFDIR if attack == 'directory' else info.st_mode,
                               st_file_attributes=0x400 if attack == 'reparse' else 0)
    monkeypatch.setattr(Path, 'lstat', observed)
    with pytest.raises(ValueError, match='regular file' if attack == 'directory' else 'links or reparse points'):
        ci.changed_scope()


@pytest.mark.parametrize('attack', ['protected-bytes', 'adoption-bytes', 'historical-bytes',
                                   'protected-membership', 'adoption-membership'])
def test_planning_allowance_preserves_real_production_adoption_and_historical_checks(monkeypatch, attack):
    from pathlib import Path
    original_bytes, original_text = Path.read_bytes, Path.read_text
    names = {
        'protected-bytes': 'create_defaults/bulk/examples/genre.yml',
        'adoption-bytes': 'create_defaults/bulk/catalog/audit/genre.json',
        'historical-bytes': 'ci/evidence/before.json',
        'protected-membership': 'create_defaults/bulk/contracts/activation/data/production-pins-v1.json',
        'adoption-membership': 'create_defaults/bulk/contracts/adoption/source-pins-v1.json',
    }
    target = ci.ROOT/names[attack]
    if attack.endswith('bytes'):
        def corrupted(path):
            raw = original_bytes(path)
            return raw+b'\nunauthorized drift' if path == target else raw
        monkeypatch.setattr(Path, 'read_bytes', corrupted)
    else:
        def corrupted(path, *args, **kwargs):
            text = original_text(path, *args, **kwargs)
            if path != target:
                return text
            value = json.loads(text)
            if attack == 'protected-membership':
                value['files'].pop(next(iter(value['files'])))
            else:
                value['files'].pop()
            return json.dumps(value)
        monkeypatch.setattr(Path, 'read_text', corrupted)
    expected = {
        'protected-bytes': 'Changed protected production bytes:',
        'adoption-bytes': 'Changed adopted source:',
        'historical-bytes': 'Changed frozen M7 baseline file:',
        'protected-membership': 'Changed 190-file protected membership',
        'adoption-membership': 'Changed adoption membership',
    }
    with pytest.raises(ValueError, match=expected[attack]):
        ci.preservation()
