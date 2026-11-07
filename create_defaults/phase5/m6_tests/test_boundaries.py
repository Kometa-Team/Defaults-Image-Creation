"""Exact M6 simulation admission; all vectors are synthetic rejection fixtures."""
from copy import deepcopy
import subprocess

import pytest

from create_defaults.bulk import library_stage as transport
from create_defaults.bulk import operator_publication as operator
from create_defaults.bulk.common import BulkError, fingerprint
from create_defaults.bulk.library_sources import save, sealed


OFFLINE = 'phase5-m6-offline-draft-transport'
ENTRIES = ('stage', 'run', 'diff', 'draft', 'bridge-admission')


def reseal(value, **changes):
    return sealed(dict({k: v for k, v in value.items() if k != 'sha256'}, **changes))


@pytest.fixture
def vectors(tmp_path, monkeypatch):
    # Any unexpected real command is a failed test, not a fixture fallback.
    def network_or_git(*args, **kwargs):
        pytest.fail('Simulation rejection reached subprocess/Git/publication I/O')
    monkeypatch.setattr(subprocess, 'run', network_or_git)
    monkeypatch.setattr(subprocess, 'check_output', network_or_git)
    monkeypatch.setattr(transport, 'git', network_or_git)
    import requests
    monkeypatch.setattr(requests.sessions.Session, 'request', network_or_git)
    baseline = dict(repository='Kometa-Team/Default-Images', branch='master', head='1'*40, tree='2'*40)
    member = dict(destination='genre/offline-rejection-vector.jpg', source='NOT-A-REAL-CANDIDATE',
                  sha256='3'*64, size=64, git_blob='4'*40, previous_sha256=None,
                  previous_git_blob='0'*40, context_sha256='5'*64,
                  difference_class='synthetic-rejection-vector', review_scope='individual', kind='poster')
    def make(mode=OFFLINE, *, label='original'):
        policy = dict(mode=mode)
        if mode == OFFLINE:
            policy['technical_batch_limits'] = dict(max_files=1, max_bytes=1024)
        inventory = sealed(dict(baseline=baseline, rows=[], label=label))
        manifest = sealed(dict(kind='proposed-operator-membership', inventory_sha256=inventory['sha256'],
                               baseline=baseline, policy_sha256=fingerprint(policy),
                               members=[deepcopy(member)], withheld=[], approved=False))
        # Pure vectors only: never call approve or persist a human/contract grant.
        receipt = sealed(dict(kind='operator-maintainer-decision', reviewer='bullmoose20',
                              decision='approved', decision_text='SYNTHETIC REJECTION VECTOR: '+label,
                              candidate_manifest_sha256=manifest['sha256'], policy_sha256=fingerprint(policy),
                              baseline=baseline, accepted_individual_exceptions=True,
                              allowed_additions=[member['destination']], allowed_renames=[],
                              draft_staging_authorized=True, merge_authorized=False))
        plan, auth = operator.authorize(manifest, policy, receipt)
        report = sealed(dict(plan_sha256=plan['sha256'], authorization_sha256=auth['sha256'],
                             complete=True, branch=auth['branch'], baseline=baseline['head'], head='6'*40))
        return dict(root=tmp_path, inventory=inventory, plan=plan, auth=auth, report=report)
    def install(v):
        save(tmp_path/'inventory.json', v['inventory'])
        save(tmp_path/'approved-git-batch-plan.json', v['plan'])
        save(tmp_path/'draft-staging-authorization.json', v['auth'])
        (tmp_path/'transport').mkdir(exist_ok=True)
        save(tmp_path/'transport/transport-report.json', v['report'])
        save(tmp_path/'transport/ownership.json', dict(plan_sha256=v['plan']['sha256'],
             authorization_sha256=v['auth']['sha256'], remote=str(tmp_path/'owned-remote.git')))
    return make, install


def invoke(entry, v, protocol):
    if entry == 'stage':
        return operator.stage(v['root'], test_remote=v['root']/'owned-remote.git',
                              write_guard=lambda **_: None, offline=protocol)
    if entry == 'run':
        return transport.run(v['plan'], v['auth'], v['root']/'transport',
                             test_remote=v['root']/'owned-remote.git',
                             write_guard=lambda **_: None, offline=protocol)
    if entry == 'diff':
        return transport.final_remote_diff(v['root'], v['plan'], v['auth'], v['report'], offline=protocol)
    if entry == 'draft':
        return operator.draft(v['root'], 'Synthetic rejection vector', write_guard=lambda **_: None, offline=protocol)
    return transport._offline_protocol(v['root'], v['plan'], v['auth'], protocol, report=v['report'])


@pytest.mark.parametrize('entry', ENTRIES)
@pytest.mark.parametrize('mode', ['normal-operator-policy', 'phase5-M6-offline-draft-transport', None])
def test_M6_normal_authorization_cannot_select_offline_protocol(vectors, entry, mode):
    make, install = vectors
    v = make(mode);install(v)
    with pytest.raises(BulkError) as error:
        invoke(entry, v, object())
    assert error.value.code == 'offline_authorization'


@pytest.mark.parametrize('entry', ENTRIES)
@pytest.mark.parametrize('flag', ['missing', False, 1, 'True'])
def test_M6_offline_mode_requires_exact_true_test_only(vectors, entry, flag):
    make, install = vectors
    v = make();raw = {k: value for k, value in v['auth'].items() if k not in {'sha256', 'test_only'}}
    if flag != 'missing':raw['test_only'] = flag
    v['auth'] = sealed(raw);install(v)
    with pytest.raises(BulkError) as error:
        invoke(entry, v, object())
    assert error.value.code in {'offline_authorization', 'approval_binding'}


@pytest.mark.parametrize('entry', ENTRIES)
def test_M6_normal_test_only_authorization_still_cannot_simulate(vectors, entry):
    make, install = vectors
    v = make('normal-operator-policy');v['auth'] = reseal(v['auth'], test_only=True);install(v)
    with pytest.raises(BulkError) as error:
        invoke(entry, v, object())
    assert error.value.code == 'offline_authorization'


@pytest.mark.parametrize('entry', ENTRIES)
def test_M6_normal_authorization_rejects_concrete_protocol_before_owner_proof(vectors, monkeypatch, entry):
    from create_defaults.bulk.lifecycle.draft_transport import OfflineProtocol
    make, install = vectors
    v = make('normal-operator-policy');install(v)
    def forbidden(*args, **kwargs):pytest.fail('Normal authorization reached offline owner verification')
    monkeypatch.setattr(OfflineProtocol, 'verify', forbidden)
    with pytest.raises(BulkError) as error:
        invoke(entry, v, object.__new__(OfflineProtocol))
    assert error.value.code == 'offline_authorization'


@pytest.mark.parametrize('entry', ENTRIES)
@pytest.mark.parametrize('kind', ['arbitrary', 'subclass', 'forged-concrete'])
def test_M6_forged_or_subclassed_protocol_cannot_select_simulation(vectors, entry, kind):
    from create_defaults.bulk.lifecycle.draft_transport import OfflineProtocol
    make, install = vectors
    v = make();install(v)
    if kind == 'arbitrary':protocol = object()
    elif kind == 'subclass':
        class Forged(OfflineProtocol):pass
        protocol = object.__new__(Forged)
    else:protocol = object.__new__(OfflineProtocol)
    with pytest.raises(BulkError) as error:
        invoke(entry, v, protocol)
    assert error.value.code in {'test_remote', 'p5m6_offline_ownership'}


@pytest.mark.parametrize('entry', ENTRIES)
def test_M6_offline_authorization_cannot_omit_owned_protocol(vectors, entry):
    make, install = vectors
    v = make();install(v)
    with pytest.raises(BulkError) as error:
        invoke(entry, v, None)
    assert error.value.code == 'test_remote'


@pytest.mark.parametrize('entry', ENTRIES)
def test_M6_simulated_draft_receipt_rejected_under_non_test_authorization(vectors, entry):
    make, install = vectors
    v = make('normal-operator-policy');install(v)
    receipt = sealed(dict(kind=transport.OFFLINE_DRAFT_RECEIPT, number=1,
                          url='https://example.invalid/synthetic/1', simulation=True, test_only=True,
                          plan_sha256=v['plan']['sha256'], authorization_sha256=v['auth']['sha256']))
    save(v['root']/'draft-pr.json', receipt)
    with pytest.raises(BulkError) as error:
        invoke(entry, v, None)
    assert error.value.code == 'offline_receipt'


@pytest.mark.parametrize('entry', ('diff', 'draft', 'bridge-admission'))
@pytest.mark.parametrize('attack', ['changed-authorization', 'replayed-authorization'])
def test_M6_stage_and_draft_authorization_must_remain_exact(vectors, entry, attack):
    from create_defaults.bulk.lifecycle.draft_transport import OfflineProtocol
    make, install = vectors
    old = make();new = make(label='changed-authority')
    if attack == 'changed-authorization':
        v = dict(new, report=old['report']);install(v)
    else:
        install(new);v = old
        # Replay old plan/auth/report files, retaining the actually owned
        # successor stage marker. Matching old JSON cannot replace that binding.
        save(old['root']/'approved-git-batch-plan.json', old['plan'])
        save(old['root']/'draft-staging-authorization.json', old['auth'])
        save(old['root']/'transport/transport-report.json', old['report'])
    # Exact type is deliberately not enough. The historical report/current
    # physical authorization mismatch must fail BEFORE owner proof is reached.
    protocol = object.__new__(OfflineProtocol)
    with pytest.raises(BulkError) as error:
        invoke(entry, v, protocol)
    assert error.value.code == 'offline_binding'


def test_M6_auth_change_during_owner_proof_is_rechecked(vectors, monkeypatch):
    from create_defaults.bulk.lifecycle.draft_transport import OfflineProtocol
    make, install = vectors
    v = make();install(v);replacement = make(label='changed-during-independent-proof')
    def changed(self, *args, **kwargs):install(replacement)
    # Target the post-proof freshness check, not a synthetic positive owner.
    monkeypatch.setattr(OfflineProtocol, 'verify', changed)
    with pytest.raises(BulkError) as error:
        invoke('bridge-admission', v, object.__new__(OfflineProtocol))
    assert error.value.code == 'offline_binding'


def test_M6_normal_mode_without_simulation_retains_legacy_admission(vectors):
    make, install = vectors
    v = make('normal-operator-policy');install(v)
    assert transport._offline_protocol(v['root'], v['plan'], v['auth'], None) is None


@pytest.mark.parametrize('phase', ['workspace', 'initialize', 'draft'])
def test_M6_authority_changed_inside_write_guard_rejected_before_mutation(vectors, monkeypatch, phase):
    from create_defaults.bulk.lifecycle.draft_transport import OfflineProtocol
    make, install = vectors
    v = make();install(v);replacement = make(label='changed-inside-write-guard')
    observations = []
    def owner_proof(self, *args, **kwargs):
        # Isolate the protected publisher's post-callback physical binding
        # check. This is a rejection vector, never positive ownership evidence.
        observations.append('independent-owner-proof')
    monkeypatch.setattr(OfflineProtocol, 'verify', owner_proof)
    monkeypatch.setattr(transport, 'sha256', lambda _: '3'*64)
    remote = v['root']/'owned-remote.git';remote.mkdir()
    def changed(**context):
        observations.append('write-guard')
        install(replacement)
    with pytest.raises(BulkError) as error:
        if phase == 'draft':
            operator.draft(v['root'], 'Synthetic rejection vector', write_guard=changed,
                           offline=object.__new__(OfflineProtocol))
        else:
            stage = v['root']/('new-transport' if phase == 'workspace' else 'transport')
            transport.run(v['plan'], v['auth'], stage, test_remote=remote,
                          write_guard=changed, offline=object.__new__(OfflineProtocol))
    assert error.value.code == 'offline_binding'
    assert observations[-1] == 'write-guard'
    assert 'independent-owner-proof' in observations


def test_M6_each_tree_query_rechecks_authority_and_reads_current_heads(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from create_defaults.bulk.lifecycle import draft_transport as bridge
    heads = {'master': '1'*40, 'draft': '2'*40}
    checks = []
    revoked = False
    def current(self):
        checks.append('fresh-authority')
        if revoked:raise BulkError('test_revoked', 'Synthetic revoked authority')
        return SimpleNamespace(root=tmp_path, binding=SimpleNamespace(
            to_dict=lambda: dict(authorization=dict(branch='draft'))))
    def git(repo, *args):
        assert args[0] == 'rev-parse'
        ref = args[1]
        if ref.startswith('refs/heads/'):return heads[ref.removeprefix('refs/heads/')].encode()
        assert ref.endswith('^{tree}')
        return (ref[:-7][0]*40).encode()
    monkeypatch.setattr(bridge._LocalReader, '_current', current)
    monkeypatch.setattr(bridge, 'git', git)
    monkeypatch.setattr(bridge, 'tree', lambda repo, oid: {'keep.txt': dict(mode='100644', blob=oid)})
    reader = bridge._LocalReader(object(), {})
    assert reader.tree('2'*40, recursive=True)['tree'][0]['sha'] == '2'*40
    heads['draft'] = '3'*40
    with pytest.raises(BulkError) as error:reader.tree('2'*40, recursive=True)
    assert error.value.code == 'p5m6_foreign_tree'
    assert reader.tree('3'*40, recursive=True)['tree'][0]['sha'] == '3'*40
    revoked = True
    with pytest.raises(BulkError) as error:reader.tree('3'*40, recursive=True)
    assert error.value.code == 'test_revoked' and len(checks) == 4


@pytest.mark.parametrize('phase', ['workspace', 'initialize', 'draft'])
def test_M6_revocation_inside_write_guard_reaches_fresh_proof_before_mutation(vectors, monkeypatch, phase):
    from create_defaults.bulk.lifecycle.draft_transport import OfflineProtocol
    make, install = vectors
    v = make();install(v)
    observations = [];revoked = False
    def owner_proof(self, *args, **kwargs):
        # Rejection-only vector: no positive owned-protocol substitute.
        observations.append('fresh-proof')
        if revoked:raise BulkError('fixture_revoked', 'Synthetic current authority was revoked')
    monkeypatch.setattr(OfflineProtocol, 'verify', owner_proof)
    monkeypatch.setattr(transport, 'sha256', lambda _: '3'*64)
    remote = v['root']/'owned-remote.git';remote.mkdir()
    def changed(**context):
        nonlocal revoked
        observations.append('write-guard');revoked = True
    with pytest.raises(BulkError) as error:
        if phase == 'draft':
            operator.draft(v['root'], 'Synthetic rejection vector', write_guard=changed,
                           offline=object.__new__(OfflineProtocol))
        else:
            stage = v['root']/('new-transport' if phase == 'workspace' else 'transport')
            transport.run(v['plan'], v['auth'], stage, test_remote=remote,
                          write_guard=changed, offline=object.__new__(OfflineProtocol))
    assert error.value.code == 'fixture_revoked'
    assert observations[-2:] == ['write-guard', 'fresh-proof']
