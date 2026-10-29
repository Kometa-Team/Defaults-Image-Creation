"""Controlled offline GitHub protocol evidence, never authenticated live grants."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from create_defaults.bulk.common import canonical
from create_defaults.bulk.contracts.destination_preflight.inventory import tree_sha
from create_defaults.bulk.contracts.translation_preflight.sources import blob_sha
from create_defaults.bulk.lifecycle import github_observations as m2
from create_defaults.bulk.lifecycle import github_observation_transport as transport

REPO = 'example/source'
PREFIX = 'repos/' + REPO
NOW = '2026-10-29T00:00:00Z'
HEAD = 'a' * 40
OTHER_HEAD = 'b' * 40
USER = dict(id=11, login='operator', type='User')
REVIEWER = dict(id=22, login='reviewer', type='User')


def fixtures(*, nested=False, contents=b'caption: Example\n'):
    target = m2.Target(REPO, 101, 202, 'main')
    blob = blob_sha(contents)
    entries = [dict(path='en.yml', mode='100644', type='blob', sha=blob, size=len(contents))]
    root = tree_sha([dict(name=e['path'], mode=e['mode'], sha=e['sha']) for e in entries])
    metadata = dict(id=101, full_name=REPO, owner=dict(id=202, login='example', type='Organization'),
                    permissions=dict(pull=True, triage=True, push=True, maintain=False, admin=False))
    permission = dict(user=USER, role_name='write', permission='write')
    review_permission = dict(user=REVIEWER, role_name='maintain', permission='write')
    pull = dict(id=303, number=7, user=USER, state='open', merged=False, draft=False,
        updated_at=NOW, base=dict(repo=metadata, ref='main', sha=HEAD), head=dict(repo=metadata, sha=HEAD))
    review = dict(id=404, user=REVIEWER, state='APPROVED', body='fixture context only',
        commit_id=HEAD, submitted_at=NOW, pull_request_url='https://api.github.com/' + PREFIX + '/pulls/7')
    comment = dict(id=505, user=USER, body='fixture confirmation only', created_at=NOW, updated_at=NOW,
        issue_url='https://api.github.com/' + PREFIX + '/issues/7')
    values = {
        'user': (USER, {}), PREFIX: (metadata, {}),
        PREFIX + '/collaborators/operator/permission': (permission, {}),
        PREFIX + '/collaborators/reviewer/permission': (review_permission, {}),
        PREFIX + '/git/ref/heads/main': (dict(ref='refs/heads/main', object=dict(sha=HEAD, type='commit')), {}),
        PREFIX + '/git/commits/' + HEAD: (dict(sha=HEAD, tree=dict(sha=root)), {}),
        PREFIX + '/git/trees/' + root: (dict(sha=root, tree=entries, truncated=False), {}),
        PREFIX + '/git/blobs/' + blob: (dict(sha=blob, size=len(contents), encoding='base64',
                                          content=base64.b64encode(contents).decode()), {}),
        PREFIX + '/pulls/7': (pull, {}),
        PREFIX + '/pulls/7/reviews?per_page=100&page=1': ([review], {}),
        PREFIX + '/pulls/7/reviews/404': (review, {}),
        PREFIX + '/issues/7/comments?per_page=100&page=1': ([comment], {}),
        PREFIX + '/issues/comments/505': (comment, {}),
    }
    if nested:
        new_entries = [dict(path='translations', mode='040000', type='tree', sha=root)]
        parent = tree_sha([dict(name='translations', mode='040000', sha=root)])
        values[PREFIX + '/git/commits/' + HEAD][0]['tree']['sha'] = parent
        values[PREFIX + '/git/trees/' + parent] = (dict(sha=parent, tree=new_entries, truncated=False), {})
    return target, values


def observer(**kwargs):
    target, values = fixtures(**kwargs)
    return m2.FixtureObserver(target, values)


def result(client, **kwargs):
    return client.observe(**kwargs).to_dict()


def test_P5_T01_exact_numeric_identity_and_selected_blob():
    client = observer()
    value = result(client, paths=('en.yml',))
    assert value['status'] == 'synthetic-current'
    facts = value['facts']
    assert facts['identity']['principal']['id'] == 11
    assert facts['identity']['repository_id'] == 101
    assert facts['identity']['owner_id'] == 202
    assert facts['snapshot']['selected'][0]['blob'] == blob_sha(b'caption: Example\n')
    assert not value['publication_authorized'] and not value['contract_approved']


@pytest.mark.parametrize('change,expected', [
    ('principal-id', 'numeric_identity'), ('permission-id', 'permission_identity_mismatch'),
    ('repository-id', 'repository_or_owner_changed'), ('owner-id', 'repository_or_owner_changed'),
    ('repository-name', 'repository_name_mismatch'), ('forged-role', 'role_policy_unknown'),
    ('forged-flags', 'permissions_unverified'), ('read-revoked', 'repository_read_revoked'),
])
def test_P5_T01_T02_forged_and_revoked_identity_facts(change, expected):
    client = observer()
    values = client._transport.responses
    if change == 'principal-id': values['user'][0]['id'] = True
    if change == 'permission-id': values[PREFIX + '/collaborators/operator/permission'][0]['user']['id'] = 99
    if change == 'repository-id': values[PREFIX][0]['id'] = 99
    if change == 'owner-id': values[PREFIX][0]['owner']['id'] = 99
    if change == 'repository-name': values[PREFIX][0]['full_name'] = 'forged/repo'
    if change == 'forged-role': values[PREFIX + '/collaborators/operator/permission'][0]['role_name'] = 'custom-admin'
    if change == 'forged-flags': values[PREFIX][0]['permissions']['admin'] = 'true'
    if change == 'read-revoked': values[PREFIX][0]['permissions']['pull'] = False
    assert result(client)['reason'] == expected


def test_P5_T03_native_decisions_and_no_contract_consumption():
    value = result(observer(), pull_request=7)
    assert value['status'] == 'synthetic-current'
    decision = value['facts']['decisions']
    assert decision['id'] == 303 and decision['author_id'] == 11
    assert decision['reviews'][0]['id'] == 404
    assert decision['reviews'][0]['author_id'] == 22
    assert decision['reviews'][0]['role']['role_name'] == 'maintain'
    assert decision['comments'][0]['id'] == 505
    assert 'body' not in decision['reviews'][0]
    assert value['operational_authority'] == 'unavailable'


@pytest.mark.parametrize('change', ['dismissed', 'edited', 'withdrawn', 'deleted', 'new-rejection', 'head-moved'])
def test_P5_T03_decision_invalidation_requires_reobservation(change):
    client = observer()
    previous = client.observe(pull_request=7)
    values = client._transport.responses
    review = values[PREFIX + '/pulls/7/reviews/404'][0]
    if change == 'dismissed': review['state'] = 'DISMISSED'
    if change == 'edited': review['body'] = 'edited'
    if change == 'withdrawn': values[PREFIX + '/issues/comments/505'][0]['body'] = 'withdrawn'
    if change == 'deleted': values[PREFIX + '/issues/7/comments?per_page=100&page=1'] = ([], {})
    if change == 'new-rejection':
        extra = deepcopy(review); extra.update(id=406, state='CHANGES_REQUESTED')
        values[PREFIX + '/pulls/7/reviews?per_page=100&page=1'][0].append(extra)
        values[PREFIX + '/pulls/7/reviews/406'] = (extra, {})
    if change == 'head-moved': values[PREFIX + '/pulls/7'][0]['head']['sha'] = OTHER_HEAD
    assert client.reobserve(previous).to_dict()['status'] == 'stale'


def test_P5_T03_decision_change_between_list_and_detail_is_stale():
    client = observer()
    detail = deepcopy(client._transport.responses[PREFIX + '/pulls/7/reviews/404'][0])
    detail['body'] = 'changed after listing'
    client._transport.responses[PREFIX + '/pulls/7/reviews/404'] = (detail, {})
    assert result(client, pull_request=7)['reason'] == 'decision_changed_during_read'


def test_P5_T03_pending_review_has_no_submitted_decision():
    client = observer()
    for endpoint in (PREFIX + '/pulls/7/reviews/404', PREFIX + '/pulls/7/reviews?per_page=100&page=1'):
        row = client._transport.responses[endpoint][0]
        if type(row) is list: row = row[0]
        row.update(state='PENDING', commit_id=None, submitted_at=None)
    review = result(client, pull_request=7)['facts']['decisions']['reviews'][0]
    assert review['state'] == 'PENDING' and review['submitted_at'] is None
    assert review['matches_current_head'] is False


@pytest.mark.parametrize('change', ['wrong-pr', 'wrong-repo', 'wrong-owner', 'bad-review-url', 'bad-comment-url'])
def test_P5_T03_numeric_decision_scope_mismatches(change):
    client = observer()
    values = client._transport.responses
    pull = values[PREFIX + '/pulls/7'][0]
    if change == 'wrong-pr': pull['number'] = 8
    if change == 'wrong-repo': pull['base']['repo']['id'] = 999
    if change == 'wrong-owner': pull['base']['repo']['owner']['id'] = 999
    if change == 'bad-review-url':
        values[PREFIX + '/pulls/7/reviews/404'][0]['pull_request_url'] += '9'
        values[PREFIX + '/pulls/7/reviews?per_page=100&page=1'][0][0]['pull_request_url'] += '9'
    if change == 'bad-comment-url':
        values[PREFIX + '/issues/comments/505'][0]['issue_url'] += '9'
        values[PREFIX + '/issues/7/comments?per_page=100&page=1'][0][0]['issue_url'] += '9'
    assert result(client, pull_request=7)['status'] == 'invalid'


@pytest.mark.parametrize('field', ['number', 'repository-id', 'owner-id'])
def test_P5_T01_T03_boolean_is_not_a_numeric_decision_identity(field):
    client = observer()
    pull = client._transport.responses[PREFIX + '/pulls/7'][0]
    if field == 'number': pull['number'] = True
    if field == 'repository-id': pull['base']['repo']['id'] = True
    if field == 'owner-id': pull['base']['repo']['owner']['id'] = True
    assert result(client, pull_request=7)['reason'] == 'numeric_identity'


@pytest.mark.parametrize('change', ['page-missing', 'wrong-next-host', 'duplicate', 'empty-with-next'])
def test_P5_T03_incomplete_or_forged_pagination(change):
    client = observer()
    endpoint = PREFIX + '/pulls/7/reviews?per_page=100&page=1'
    rows, _ = client._transport.responses[endpoint]
    next_url = 'https://api.github.com/' + PREFIX + '/pulls/7/reviews?per_page=100&page=2'
    if change == 'wrong-next-host': next_url = next_url.replace('api.github.com', 'evil.example')
    if change == 'empty-with-next': rows = []
    if change == 'duplicate': rows.append(deepcopy(rows[0]))
    client._transport.responses[endpoint] = (rows, {'link': '<' + next_url + '>; rel="next"'})
    assert result(client, pull_request=7)['status'] in {'unavailable', 'invalid'}


def test_P5_T03_complete_pagination_fetches_current_details():
    client = observer()
    first = PREFIX + '/pulls/7/reviews?per_page=100&page=1'
    second = PREFIX + '/pulls/7/reviews?per_page=100&page=2'
    client._transport.responses[first][1]['link'] = '<https://api.github.com/' + second + '>; rel="next"'
    extra = deepcopy(client._transport.responses[first][0][0]); extra['id'] = 406
    client._transport.responses[second] = ([extra], {})
    client._transport.responses[PREFIX + '/pulls/7/reviews/406'] = (extra, {})
    assert len(result(client, pull_request=7)['facts']['decisions']['reviews']) == 2


def test_P5_T03_new_decision_after_first_history_page_is_stale():
    client = observer()
    key = PREFIX + '/pulls/7/reviews?per_page=100&page=1'
    first = client._transport.responses[key]
    second = deepcopy(first)
    extra = deepcopy(second[0][0]); extra.update(id=406, state='CHANGES_REQUESTED')
    second[0].append(extra)
    client._transport.responses[key] = [first, second]
    assert result(client, pull_request=7)['reason'] == 'decision_history_changed_during_read'


def test_P5_T03_malformed_pagination_cannot_hide_a_following_page():
    client = observer()
    endpoint = PREFIX + '/pulls/7/reviews?per_page=100&page=1'
    client._transport.responses[endpoint][1]['link'] = '<https://evil.example/next>; rel="not-next"'
    assert result(client, pull_request=7)['reason'] == 'pagination_scope'


def test_P5_T06_translation_values_and_nested_tree_provenance():
    value = result(observer(nested=True), paths=('translations/en.yml',), translation_keys=('caption',))
    assert value['status'] == 'synthetic-current'
    snapshot = value['facts']['snapshot']
    assert snapshot['complete'] and snapshot['inventory_entries'] == 2
    assert snapshot['selected'][0]['values'][0]['key'] == 'caption'
    assert 'Example' not in json.dumps(value)


@pytest.mark.parametrize('contents,keys', [(b'other: Example\n', ('caption',)),
    (b'caption: [bad]\n', ('caption',)), (b'caption: Example\ncaption: Duplicate\n', ('caption',))])
def test_P5_T06_missing_or_invalid_translation_values(contents, keys):
    assert result(observer(contents=contents), paths=('en.yml',), translation_keys=keys)['status'] == 'invalid'


def test_P5_T06_equal_selected_bytes_under_moved_head_still_stale():
    client = observer()
    previous = client.observe(paths=('en.yml',), translation_keys=('caption',))
    values = client._transport.responses
    values[PREFIX + '/git/ref/heads/main'][0]['object']['sha'] = OTHER_HEAD
    commit = deepcopy(values[PREFIX + '/git/commits/' + HEAD][0]); commit['sha'] = OTHER_HEAD
    values[PREFIX + '/git/commits/' + OTHER_HEAD] = (commit, {})
    assert client.reobserve(previous).to_dict()['status'] == 'stale'


@pytest.mark.parametrize('change,reason', [('truncated', 'tree_incomplete'), ('tree-hash', 'tree_hash'),
    ('symlink', 'unsafe_tree_mode'), ('submodule', 'unsafe_tree_mode'),
    ('blob', 'blob_hash'), ('missing', 'selected_file_missing')])
def test_P5_T07_T30_incomplete_trees_or_bytes_never_prove_absence(change, reason):
    client = observer()
    values = client._transport.responses
    tree_endpoint = next(k for k in values if '/git/trees/' in k)
    tree = values[tree_endpoint][0]
    if change == 'truncated': tree['truncated'] = True
    if change == 'tree-hash': tree['tree'][0]['sha'] = 'f' * 40
    if change == 'symlink': tree['tree'][0]['mode'] = '120000'
    if change == 'submodule': tree['tree'][0].update(mode='160000', type='commit')
    if change == 'blob': values[next(k for k in values if '/git/blobs/' in k)][0]['content'] = 'YmFk'
    path = 'missing.yml' if change == 'missing' else 'en.yml'
    assert result(client, paths=(path,))['reason'] == reason


def test_P5_T30_boolean_blob_size_is_rejected_even_for_exact_one_byte_content():
    client = observer(contents=b'x')
    endpoint = next(k for k in client._transport.responses if '/git/blobs/' in k)
    client._transport.responses[endpoint][0]['size'] = True
    assert result(client, paths=('en.yml',))['reason'] == 'blob_hash'


def test_P5_T07_head_moves_during_observation():
    client = observer()
    endpoint = PREFIX + '/git/ref/heads/main'
    first = client._transport.responses[endpoint]
    client._transport.responses[endpoint] = [first, (dict(ref='refs/heads/main', object=dict(sha=OTHER_HEAD, type='commit')), {})]
    commit = deepcopy(client._transport.responses[PREFIX + '/git/commits/' + HEAD][0]); commit['sha'] = OTHER_HEAD
    client._transport.responses[PREFIX + '/git/commits/' + OTHER_HEAD] = (commit, {})
    assert result(client)['status'] == 'stale'


def official_observer():
    _, values = fixtures()
    official = 'Kometa-Team/Default-Images'
    translated = {}
    for endpoint, value in values.items():
        encoded = json.dumps(value).replace(REPO, official).replace('refs/heads/main', 'refs/heads/master')
        data, headers = json.loads(encoded)
        translated[endpoint.replace(REPO, official).replace('ref/heads/main', 'ref/heads/master')] = (data, headers)
    translated['repos/' + official][0]['owner']['login'] = 'Kometa-Team'
    return m2.FixtureObserver(m2.Target(official, 101, 202, 'master', purpose='official-destination'), translated)


def test_P5_T07_official_destination_head_changes_before_consumption():
    client = official_observer()
    previous = client.observe()
    assert previous.to_dict()['status'] == 'synthetic-current'
    values = client._transport.responses
    prefix = 'repos/Kometa-Team/Default-Images'
    values[prefix + '/git/ref/heads/master'][0]['object']['sha'] = OTHER_HEAD
    commit = deepcopy(values[prefix + '/git/commits/' + HEAD][0]); commit['sha'] = OTHER_HEAD
    values[prefix + '/git/commits/' + OTHER_HEAD] = (commit, {})
    assert client.reobserve(previous).to_dict()['status'] == 'stale'


def test_P5_T07_destination_repository_transfer_revokes_previous_observation():
    client = official_observer()
    previous = client.observe()
    client._transport.responses['repos/Kometa-Team/Default-Images'][0]['owner']['id'] = 999
    assert client.reobserve(previous).to_dict()['status'] == 'revoked'


def test_P5_T07_T30_complete_hash_valid_tree_still_rejects_case_aliases():
    client = observer()
    values = client._transport.responses
    endpoint = next(k for k in values if '/git/trees/' in k)
    original = deepcopy(values[endpoint][0]['tree'][0])
    other = deepcopy(original); other['path'] = 'EN.yml'
    entries = [original, other]
    checksum = tree_sha([dict(name=e['path'], mode=e['mode'], sha=e['sha']) for e in entries])
    values[PREFIX + '/git/commits/' + HEAD][0]['tree']['sha'] = checksum
    values[PREFIX + '/git/trees/' + checksum] = (dict(sha=checksum, tree=entries, truncated=False), {})
    assert result(client)['reason'] == 'tree_alias'


@pytest.mark.parametrize('fields', [dict(language='fr'), dict(branch='main'), dict(root='posters')])
def test_P5_T08_official_language_branch_and_root_restrictions(fields):
    with pytest.raises(transport.ObservationFailure, match='official_scope'):
        m2.Target('Kometa-Team/Default-Images', 101, 202, fields.get('branch', 'master'),
                  root=fields.get('root'), language=fields.get('language', 'en'), purpose='official-destination')


def test_P5_T08_user_destination_and_org_delegation_remain_unavailable():
    with pytest.raises(transport.ObservationFailure, match='target_policy_unapproved'):
        m2.Target('example/source', 101, 202, 'main', purpose='user-destination')
    client = observer()
    client.target = m2.Target(REPO, 101, 202, 'main', root='approved')
    assert result(client, paths=('en.yml',))['reason'] == 'source_root_scope'


def test_P5_T10_fixture_evidence_is_deterministic_and_not_real_authority():
    one, two = observer(), observer()
    evidence = one.observe(paths=('en.yml',))
    assert evidence.encoded == two.observe(paths=('en.yml',)).encoded
    assert evidence.to_dict()['synthetic'] is True
    assert evidence.to_dict()['issuer'] == 'fixture'
    assert not evidence.contract_approved and not evidence.readiness_authorized and not evidence.publication_authorized
    forged = m2.Observation(evidence.encoded)
    assert one.reobserve(forged).to_dict()['status'] == 'unavailable'
    assert two.reobserve(evidence).to_dict()['status'] == 'unavailable'


def test_P5_T10_arbitrary_callback_or_subclass_cannot_claim_observation():
    class Forged(m2.GitHubObserver):
        pass
    target, values = fixtures()
    fake = Forged(target)
    fake._transport = m2._FixtureTransport(REPO, values)
    assert result(fake)['reason'] == 'observer_type'
    real = m2.GitHubObserver(target)
    real._transport = m2._FixtureTransport(REPO, values)
    assert result(real)['reason'] == 'transport_boundary'
    with pytest.raises(TypeError):
        m2.GitHubObserver(target, transport=lambda: True)


def test_P5_T11_permissions_change_before_consumption_revokes_previous_observation():
    client = observer()
    previous = client.observe()
    permission = client._transport.responses[PREFIX + '/collaborators/operator/permission'][0]
    permission.update(role_name='read', permission='read')
    assert client.reobserve(previous).to_dict()['status'] == 'revoked'


def test_P5_T11_permissions_change_within_one_observation_revokes_it():
    client = observer()
    endpoint = PREFIX + '/collaborators/operator/permission'
    old = client._transport.responses[endpoint]
    new = deepcopy(old); new[0].update(role_name='read', permission='read')
    client._transport.responses[endpoint] = [old, new]
    assert result(client)['reason'] == 'identity_or_permissions_changed_during_read'


def test_P5_T11_revoked_or_expired_credentials_not_resurrected_on_restart():
    client = observer()
    previous = client.observe()
    client._transport.responses['user'] = transport.ObservationFailure('revoked', 'credentials_rejected')
    assert client.reobserve(previous).to_dict()['status'] == 'revoked'
    restarted = observer()
    assert restarted.reobserve(previous).to_dict()['reason'] == 'restart_or_foreign_evidence'
    assert result(restarted)['status'] == 'synthetic-current'


def test_P5_T29_unexpected_exception_chains_and_bodies_are_redacted():
    client = observer()
    secret = 'TOKEN_SECRET_AUTHORIZATION_PASSWORD'
    with patch.object(client, '_identity', side_effect=RuntimeError(secret)):
        observation = client.observe()
    assert secret not in observation.encoded.decode()
    assert observation.to_dict()['reason'] == 'response_or_selection_invalid'
    assert len(observation.to_dict()['correlation_id']) == 24
    safe = result(observer(), pull_request=7)
    assert 'fixture confirmation only' not in json.dumps(safe)


def response(code=200, value=None, headers=''):
    return (f'HTTP/2.0 {code} OK\r\n{headers}\r\n' +
            json.dumps(value or {})).encode()


@pytest.mark.parametrize('code,expected', [(401, 'revoked'), (403, 'unavailable'), (404, 'unavailable'), (429, 'unavailable')])
def test_P5_T02_T29_cli_errors_never_emit_remote_credentials(code, expected):
    client = object.__new__(transport._CLI); client.repo = REPO; client.executable = 'gh'; client.begin()
    with patch.object(transport, '_bounded_process', return_value=(1, response(code, {'secret': 'NEVER_EMIT'}))), \
         patch.object(transport.time, 'sleep'):
        with pytest.raises(transport.ObservationFailure) as caught:
            client.get('user')
    assert caught.value.status == expected
    assert 'NEVER_EMIT' not in repr(caught.value)


def test_P5_T29_cli_is_fixed_host_get_only_and_retries_temporary_errors():
    client = object.__new__(transport._CLI); client.repo = REPO; client.executable = 'gh'; client.begin()
    with patch.object(transport, '_bounded_process', side_effect=[(1, response(503)), (0, response(200, USER))]) as run, \
         patch.object(transport.time, 'sleep') as sleep:
        assert client.get('user')[0] == USER
    argv = run.call_args.args[0]
    assert argv[argv.index('--method') + 1] == 'GET'
    assert argv[argv.index('--hostname') + 1] == 'github.com'
    assert '--cache' not in argv and '--paginate' not in argv
    sleep.assert_called_once_with(1)
    with pytest.raises(transport.ObservationFailure, match='endpoint_scope'):
        client.get('https://evil.example/token')


def test_P5_T29_cli_network_failure_without_stdout_is_retried():
    client = object.__new__(transport._CLI); client.repo = REPO; client.executable = 'gh'; client.begin()
    with patch.object(transport, '_bounded_process', side_effect=[(1, b''), (0, response(200, USER))]), \
         patch.object(transport.time, 'sleep') as sleep:
        assert client.get('user')[0] == USER
    sleep.assert_called_once_with(1)


def test_P5_T02_supervised_path_without_valid_credentials_is_unavailable():
    target, _ = fixtures()
    with patch.object(transport.shutil, 'which', return_value='gh'), \
         patch.object(transport, '_bounded_process', return_value=(1, response(401))):
        value = result(m2.GitHubObserver(target))
    assert value['status'] == 'revoked' and value['facts'] == {}
    assert not value['publication_authorized']


def test_P5_T29_cli_retry_and_response_bounds_fail_closed():
    client = object.__new__(transport._CLI); client.repo = REPO; client.executable = 'gh'; client.begin()
    with patch.object(transport, '_bounded_process', return_value=(1, response(429, headers='Retry-After: 999\r\n'))):
        with pytest.raises(transport.ObservationFailure, match='retry_bound'):
            client.get('user')
    with patch.object(transport.shutil, 'which', return_value=None):
        target, _ = fixtures()
        assert result(m2.GitHubObserver(target))['reason'] == 'cli_unavailable'


def test_P5_T29_process_timeout_and_output_bound_hide_stderr_and_kill_child():
    with pytest.raises(transport.ObservationFailure, match='response_bound'):
        transport._bounded_process([sys.executable, '-c', 'print("X" * 10000)'], limit=100)
    with pytest.raises(transport.ObservationFailure, match='cli_unavailable'):
        transport._bounded_process([sys.executable, '-c', 'import time; time.sleep(10)'], timeout=.05)


def test_P5_T29_total_observation_budget_is_bounded():
    client = object.__new__(transport._CLI); client.repo = REPO; client.executable = 'gh'; client.begin()
    client._calls = 1024
    with pytest.raises(transport.ObservationFailure, match='observation_budget'):
        client.get('user')


def test_P5_T29_target_and_evidence_have_explicit_size_bounds():
    with pytest.raises(transport.ObservationFailure, match='target_bound'):
        m2.Target('example/' + 'x' * 1000, 101, 202, 'main')
    client = observer()
    value = client._record('verified-current', 'observed', {'oversized': 'x' * 2_000_000}, {}).to_dict()
    assert value['status'] == 'unavailable' and value['reason'] == 'evidence_bound'
    assert value['facts'] == {}


def test_P5_T29_selected_response_timestamps_cannot_emit_secrets():
    client = observer()
    client._transport.responses[PREFIX + '/pulls/7'][0]['updated_at'] = 'SECRET_TOKEN'
    value = client.observe(pull_request=7)
    assert value.to_dict()['status'] == 'invalid'
    assert b'SECRET_TOKEN' not in value.encoded


def test_P5_T10_immutable_package_e_archive_is_data_not_restart_authority(tmp_path):
    from create_defaults.bulk.lifecycle.package_e import SidecarStore
    client = observer()
    evidence = client.observe(paths=('en.yml',))
    archive = SidecarStore(tmp_path / 'owned')
    checksum = client.archive(evidence, archive)
    assert archive.read_object(checksum) == evidence.encoded
    restarted = observer()
    assert restarted.reobserve(m2.Observation(archive.read_object(checksum))).to_dict()['status'] == 'unavailable'
