"""M3 exact two-stage and package consumption; every positive is offline-only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from create_defaults.bulk.common import BulkError, canonical, fingerprint
from create_defaults.bulk.lifecycle.composition import compose
from create_defaults.bulk.lifecycle.evidence import ReviewInputs
from create_defaults.bulk.lifecycle.github_decisions import (
    ConsumptionReceipt, DecisionBinding, FixtureDecisionConsumer, GitHubDecisionConsumer, ObservationQuery, PackageSelection,
)
from create_defaults.bulk.lifecycle.github_observations import GitHubObserver, Observation
from create_defaults.bulk.lifecycle.github_observation_transport import ObservationFailure
from create_defaults.bulk.lifecycle.package_e import SidecarStore
from create_defaults.bulk.lifecycle.previews import CompositionArchive, CompositionTrial
from create_defaults.bulk.lifecycle.review import ReviewArchive
from create_defaults.bulk.lifecycle.review_authority import require_operational_approval
from create_defaults.phase4.tests import composition_samples
from create_defaults.phase5.m3_tests import helpers as h

ROOT = Path(__file__).resolve().parents[3]
CATEGORIES = [p['category'] for p in json.loads((ROOT/'create_defaults/bulk/contracts/categories/data/release-v1.json').read_text())['entries']]


@pytest.fixture(scope='module')
def native_rows():
    trials = []
    class Rows(dict):
        def __missing__(self, category):
            trial = CompositionTrial()
            trials.append(trial)
            context = composition_samples.poster(trial, category, paired=category == 'Network')
            requests = [composition_samples.exception(context.candidate)] if category == 'Genre' else []
            evidence = compose(context, trial, exceptions=requests)
            self[category] = (trial, context, evidence, requests)
            return self[category]
    try:
        yield Rows()
    finally:
        for trial in reversed(trials):
            trial.close()


@pytest.fixture
def artwork_case(native_rows, request):
    return h.case(native_rows['Genre'], request.node.name)


@pytest.fixture(scope='module')
def contract_trial():
    with CompositionTrial() as trial:
        yield trial


@pytest.fixture
def case(contract_trial, request):
    return h.contract_case(contract_trial, request.node.name)


def denied(receipt):
    assert type(receipt) is ConsumptionReceipt
    value = receipt.to_dict()
    for flag in ('authenticated', 'operation_accepted', 'applied', 'artwork_approved', 'contract_approved',
                 'ready', 'active', 'production_enforcement', 'publication_authorized'):
        assert value[flag] is False, flag
    assert value['simulation'] is True
    assert not receipt.contract_approved and not receipt.readiness_authorized and not receipt.publication_authorized


def test_P5_T04_T14_native_full_artwork_consumes_two_distinct_decisions(artwork_case):
    case = artwork_case
    receipt = h.consume(case)
    h.export_native(case, receipt)
    denied(receipt)
    result = receipt.to_dict()['result']
    assert result['review_state'] == 'MAINTAINER_APPROVED'
    archive = ReviewArchive(case['trial'].config.cache_dir)
    identity = next(state.to_dict()['id'] for states in archive.history().values() for state in states if state.sha256 == result['review_state_sha256'])
    assert [s.to_dict()['state'] for s in archive.history(identity)] == ['PREVIEWS_COMPLETE', 'SUBMITTER_CONFIRMED', 'MAINTAINER_APPROVED']
    with pytest.raises(BulkError, match='real_authority_unavailable'):
        require_operational_approval(receipt)


@pytest.mark.parametrize('category', CATEGORIES)
def test_P5_T09_exact_one_package_registry_selection_without_real_approvals(contract_trial, category):
    case = h.contract_case(contract_trial, 'contract-' + category, category=category)
    receipt = h.consume(case)
    denied(receipt)
    assert receipt.to_dict()['result']['synthetic_contract_selected'] is True
    assert len(CATEGORIES) == 22
    real = json.loads((ROOT/'create_defaults/bulk/contracts/categories/data/review-registry-v1.json').read_text())
    assert real['entries'] == []


def test_P5_T05_duplicate_consumption_is_idempotent_and_has_one_package_event(case):
    first = h.consume(case)
    second = h.consume(case)
    assert first == second
    with SidecarStore.open_readonly(case['trial'].config.cache_dir).read_connection() as db:
        assert db.execute("SELECT count(*) FROM events WHERE kind='phase5_m3_consumption' AND subject=?", (case['binding'].sha256,)).fetchone()[0] == 1


def test_P5_T05_concurrent_exact_decisions_do_not_duplicate_history(case):
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda _: h.consume(case), range(2)))
    assert receipts[0] == receipts[1]
    denied(receipts[0])


def test_P5_T03_explicit_maintainer_rejection_remains_immutable(artwork_case):
    case = artwork_case
    h.install(case, action='reject')
    receipt = h.consume(case, action='reject')
    assert receipt.to_dict()['result']['review_state'] == 'MAINTAINER_REJECTED'
    denied(receipt)


def test_P5_T13_paired_network_artwork_requires_both_native_members(native_rows):
    case = h.case(native_rows['Network'], 'paired-network')
    assert len(case['row'][2].to_dict()['required_members']) == 2
    receipt = h.consume(case)
    h.export_native(case, receipt)
    denied(receipt)


@pytest.mark.parametrize('attack,reason', [
    ('generic-confirmation', 'confirmation_context'), ('edited-confirmation', 'exact_submitter_confirmation'),
    ('generic-review', 'maintainer_context'), ('edited-review', 'maintainer_context'),
    ('dismissed-review', 'exact_independent_maintainer'), ('withdrawn-approval', 'exact_independent_maintainer'),
    ('self-approval', 'exact_independent_maintainer'), ('wrong-review-identity', 'observation_invalid'),
    ('wrong-confirmation-identity', 'exact_submitter_confirmation'), ('wrong-commit', 'exact_independent_maintainer'),
    ('stage-order', 'two_stage_order'), ('unsubmitted-review', 'exact_independent_maintainer'),
])
def test_P5_T03_T04_native_revision_authorship_and_exact_context(case, attack, reason):
    def mutate(comment, review):
        if attack == 'generic-confirmation': comment['body'] = 'looks good'
        if attack == 'edited-confirmation': comment['updated_at'] = h.DECIDED
        if attack == 'generic-review': review['body'] = 'approved'
        if attack == 'edited-review': review['body'] += ' edited'
        if attack == 'dismissed-review': review['state'] = 'DISMISSED'
        if attack == 'withdrawn-approval': review['state'] = 'CHANGES_REQUESTED'
        if attack == 'self-approval': review['user'] = deepcopy(h.SUBMITTER)
        if attack == 'wrong-review-identity': review['user'] = dict(h.MAINTAINER, id=99)
        if attack == 'wrong-confirmation-identity': comment['user'] = dict(h.SUBMITTER, id=99)
        if attack == 'wrong-commit': review['commit_id'] = 'c' * 40
        if attack == 'stage-order': review['submitted_at'] = h.CONFIRMED
        if attack == 'unsubmitted-review': review.update(state='PENDING', commit_id=None, submitted_at=None)
    h.install(case, mutate=mutate)
    with pytest.raises(BulkError, match=reason):
        h.consume(case)


@pytest.mark.parametrize('attack,reason', [
    ('missing-confirmation', 'exact_submitter_confirmation'), ('missing-review', 'exact_independent_maintainer'),
    ('submitter-withdrawal', 'confirmation_superseded'), ('newer-rejection', 'maintainer_decision_superseded'),
    ('incomplete-pagination', 'observation_unavailable'), ('duplicate-object', 'observation_invalid'),
    ('detail-edited-during-read', 'observation_stale'),
])
def test_P5_T03_complete_current_history_is_required(case, attack, reason):
    def mutate(values, prefix):
        comments = values[prefix + '/issues/7/comments?per_page=100&page=1'][0]
        reviews = values[prefix + '/pulls/7/reviews?per_page=100&page=1'][0]
        if attack == 'missing-confirmation': comments.clear()
        if attack == 'missing-review': reviews.clear()
        if attack == 'submitter-withdrawal':
            later = dict(comments[0], id=507, body='withdrawn', created_at='2026-10-29T00:02:00Z', updated_at='2026-10-29T00:02:00Z')
            comments.append(later)
            values[prefix + '/issues/comments/507'] = (deepcopy(later), {})
        if attack == 'newer-rejection':
            later = dict(reviews[0], id=406, state='CHANGES_REQUESTED', submitted_at='2026-10-29T00:02:00Z')
            reviews.append(later)
            values[prefix + '/pulls/7/reviews/406'] = (deepcopy(later), {})
        if attack == 'incomplete-pagination':
            values[prefix + '/pulls/7/reviews?per_page=100&page=1'] = (reviews, {'link': '<https://api.github.com/' + prefix + '/pulls/7/reviews?per_page=100&page=2>; rel="next"'})
        if attack == 'duplicate-object': reviews.append(deepcopy(reviews[0]))
        if attack == 'detail-edited-during-read': values[prefix + '/pulls/7/reviews/404'][0]['body'] += ' changed'
    h.change_proposal(case, mutate)
    with pytest.raises(BulkError, match=reason):
        h.consume(case)


@pytest.mark.parametrize('attack,reason', [
    ('principal', 'principal_identity'), ('pr-author', 'submitter_work_relationship'),
    ('pr-id', 'full_context_changed'), ('source-commit', 'proposal_source_binding'),
    ('repository-transfer', 'observation_revoked'), ('read-revoked', 'observation_revoked'),
    ('maintainer-role', 'fixture_maintainer_permission'), ('unknown-role', 'observation_unavailable'),
])
def test_P5_T04_T11_numeric_identity_pr_source_and_permissions(case, attack, reason):
    def mutate(values, prefix):
        if attack == 'pr-author': values[prefix + '/pulls/7'][0]['user'] = dict(h.SUBMITTER, id=99)
        if attack == 'pr-id': values[prefix + '/pulls/7'][0]['id'] = 909
        if attack == 'source-commit': values[prefix + '/pulls/7'][0]['head']['sha'] = 'c' * 40
        if attack == 'repository-transfer': values[prefix][0]['owner']['id'] = 999
        if attack == 'read-revoked': values[prefix][0]['permissions']['pull'] = False
    h.change_proposal(case, mutate)
    if attack == 'principal':
        values = case['queries']['maintainer'].observer._transport.responses
        principal = dict(h.MAINTAINER, id=99, login='different-user')
        values['user'] = (principal, {})
        values['repos/Fixture/Creation/collaborators/different-user/permission'] = (dict(user=principal, role_name='maintain', permission='write'), {})
    if attack in {'maintainer-role', 'unknown-role'}:
        def role(values, prefix):
            values[prefix + '/collaborators/maintainer/permission'][0]['role_name'] = 'write' if attack == 'maintainer-role' else 'custom-admin'
        h.change_proposal(case, role)
    with pytest.raises(BulkError, match=reason):
        h.consume(case)


@pytest.mark.parametrize('field,value', [('category', 'Playlist'), ('kind', 'overlay'), ('version', '2.0.0'),
                                      ('sha256', '0'*64), ('variants', ('unapproved',))])
def test_P5_T09_exact_selected_package_cannot_be_substituted(case, field, value):
    with pytest.raises(BulkError):
        replace(case['selection'], **{field: value}).select()


def test_P5_T09_partial_package_approval_does_not_create_blanket_registry():
    selection = PackageSelection.current('Genre')
    with pytest.raises(BulkError, match='exact_package_scope'):
        replace(selection, variants=selection.variants[:1]).select(whole_package=True)
    with pytest.raises(BulkError):
        PackageSelection.current('UnknownCategory')


@pytest.mark.parametrize('scope', ['artwork', 'operation', 'activation', 'publication'])
def test_P5_T28_approval_scopes_cannot_be_exchanged(case, scope):
    with pytest.raises(BulkError, match='separate_approval_scopes'):
        case['consumer'].consume(case['binding'], confirmation_id=505, review_id=404, scope=scope)


@pytest.mark.parametrize('label,status', [('submitter', 'revoked'), ('maintainer', 'unavailable'),
                                         ('source', 'unavailable'), ('translation', 'unavailable'), ('destination', 'invalid')])
def test_P5_T11_failed_current_observations_never_reuse_archived_authority(case, label, status):
    h.consume(case)
    values = case['queries'][label].observer._transport.responses
    values['user'] = ObservationFailure(status, 'controlled-failure')
    with pytest.raises(BulkError, match='observation_' + status):
        h.consume(case)


@pytest.mark.parametrize('label', ['submitter', 'maintainer', 'source', 'translation', 'destination'])
def test_P5_T11_authority_moving_during_consumption_fails_final_reobservation(case, label):
    observer = case['queries'][label].observer
    original = observer.reobserve
    def changed(previous):
        observer._transport.responses['user'] = ObservationFailure('revoked', 'controlled-revocation')
        return original(previous)
    with patch.object(observer, 'reobserve', changed), pytest.raises(BulkError, match='authority_changed_at_consumption'):
        h.consume(case)


@pytest.mark.parametrize('label', ['translation', 'destination'])
def test_P5_T12_T30_current_authoritative_heads_are_bound_even_for_equal_values(artwork_case, label):
    case = artwork_case
    query = case['queries'][label]
    files = dict(h.translation_snapshot().resources) if label == 'translation' else {}
    values, _ = h.git_fixtures(query.observer.target, files, commit='c'*40)
    query.observer._transport.responses.update(values)
    with pytest.raises(BulkError, match='authoritative_translation_binding|current_destination_binding'):
        h.consume(case)


@pytest.mark.parametrize('kind', ['source', 'font', 'definition', 'profile'])
def test_P5_T12_full_native_current_inputs_are_replayed(artwork_case, kind):
    case = artwork_case
    ctx = case['inputs'].composition
    if kind in {'source', 'font'}:
        view = case['row'][2].to_dict()['views'][0]
        manifest = json.loads(view['manifest_json'])
        source = next(s for s in manifest['jobs'][0]['inputs'] if (s['role'] == 'font') == (kind == 'font'))
        path = ctx.candidate.config.asset_dir / source['path']
    else:
        path = ctx.candidate.paths[0] if kind == 'definition' else ctx.candidate.profiles_path
    path = Path(path)
    original = path.read_bytes()
    try:
        path.write_bytes(original + b'\nchanged-current-context')
        with pytest.raises(BulkError):
            h.consume(case)
    finally:
        path.write_bytes(original)


@pytest.mark.parametrize('kind', ['encoded-artifact', 'owned-receipt', 'composition'])
def test_P5_T14_full_resolution_objects_and_owned_receipts_are_checked(artwork_case, kind):
    case = artwork_case
    evidence = case['row'][2]
    member = evidence.to_dict()['views'][0]['members'][0]
    pin = evidence.sha256 if kind == 'composition' else member['object_sha256' if kind == 'encoded-artifact' else 'receipt_object_sha256']
    path = case['trial'].config.cache_dir / 'objects' / (pin + '.json')
    original = path.read_bytes()
    try:
        path.write_bytes(original + b'\n')
        with pytest.raises(BulkError):
            h.consume(case)
    finally:
        path.write_bytes(original)


@pytest.mark.parametrize('mutation', ['companions', 'members', 'caption', 'layout', 'renderer', 'dimensions'])
def test_P5_T12_T13_T14_rehashed_changed_visual_context_requires_new_decisions(artwork_case, mutation):
    case = artwork_case
    from create_defaults.bulk.lifecycle.composition_models import CompositionEvidence
    data = case['row'][2].to_dict()
    view = data['views'][0]
    if mutation == 'companions': view['members'][0]['companions'] = ['missing-companion']
    if mutation == 'members': view['members'] = []
    if mutation == 'caption':
        definitions = json.loads(view['definitions_json'])
        next(iter(definitions.values()))['display_name'] = 'Changed caption context'
        view['definitions_json'] = canonical(definitions).decode()
    if mutation == 'layout': view['layout_json'] = canonical({'changed': True}).decode()
    if mutation == 'renderer': data['runtime_json'] = canonical({'changed': True}).decode()
    if mutation == 'dimensions': view['members'][0]['dimensions'] = [10, 10]
    with pytest.raises(BulkError):
        forged = CompositionEvidence.from_dict(data)
        store = SidecarStore(case['trial'].config.cache_dir)
        store.put_object(forged.encoded, expected_sha256=forged.sha256)
        changed = replace(case['inputs'], composition_sha256=forged.sha256)
        case['consumer'].prepare(case['selection'], inputs=changed, review_id='synthetic.review.changed-' + mutation)


def test_P5_T05_restart_requires_fresh_observation_not_a_serialized_binding(artwork_case):
    case = artwork_case
    first = h.consume(case)
    with pytest.raises(BulkError, match='restart_or_foreign_binding'):
        case['consumer'].consume(DecisionBinding(case['binding'].encoded), confirmation_id=505, review_id=404, scope='artwork')
    old = case['consumer']
    fresh = FixtureDecisionConsumer(case['trial'], old.queries, submitter_id=11, maintainer_id=22, source_files=old.source_files)
    before = sum(len(q.observer._transport.requests) for q in old.queries.values())
    binding = fresh.prepare(case['selection'], inputs=case['inputs'], review_id=old._issued[id(case['binding'])][3].to_dict()['id'])
    with pytest.raises(BulkError, match='restart_or_foreign_binding'):
        fresh.consume(case['binding'], confirmation_id=505, review_id=404, scope='artwork')
    receipt = fresh.consume(binding, confirmation_id=505, review_id=404, scope='artwork')
    assert receipt == first
    assert sum(len(q.observer._transport.requests) for q in old.queries.values()) > before
    denied(receipt)


def test_P5_T10_fixture_receipts_and_generic_approvals_never_authorize_real_consumers(artwork_case):
    case = artwork_case
    receipt = h.consume(case)
    denied(receipt)
    real = object.__new__(GitHubDecisionConsumer)
    for value in (receipt, case['binding'], receipt.to_dict(), {'authenticated': True, 'status': 'approved'}):
        with pytest.raises(BulkError, match='real_policy_and_provider_unavailable'):
            real.consume(value)
    with pytest.raises(BulkError, match='observer_boundary'):
        GitHubDecisionConsumer(case['queries'])
    assert case['inputs'].phase3.to_dict()['m7']['exact_approvals_missing'] == 22


def test_P5_T10_observer_and_consumer_subclasses_cannot_cross_trust_boundary(case):
    class ForgedObserver(GitHubObserver):
        def observe(self, **kwargs): return Observation(canonical({'status': 'verified-current'}))
    fake = object.__new__(ForgedObserver)
    queries = {k: ObservationQuery(fake) for k in case['queries']}
    with pytest.raises(BulkError, match='observer_boundary'):
        GitHubDecisionConsumer(queries)
    class ForgedConsumer(FixtureDecisionConsumer):
        pass
    with pytest.raises(BulkError, match='fixture_trial_required'):
        ForgedConsumer(case['trial'], case['queries'], submitter_id=11, maintainer_id=22)


def test_P5_T11_fixture_expiry_and_real_policy_unavailability_are_separate(case):
    case['consumer'].as_of = case['consumer'].expires_at
    with pytest.raises(BulkError, match='fixture_expired'):
        h.consume(case)
    with pytest.raises(BulkError, match='real_policy_and_provider_unavailable'):
        object.__new__(GitHubDecisionConsumer).consume()


def test_P5_T29_native_and_remote_errors_are_redacted_without_raw_exception_chains(artwork_case):
    case = artwork_case
    secret = 'ghp_NEVER_ARCHIVE_THIS_CREDENTIAL'
    with patch.object(ReviewInputs, 'verify_bundle', side_effect=RuntimeError(secret)):
        with pytest.raises(BulkError) as failure:
            h.consume(case)
    assert secret not in str(failure.value)
    assert failure.value.__cause__ is None and failure.value.__context__ is None
    observer = case['queries']['maintainer'].observer
    with patch.object(observer._transport, 'get', side_effect=RuntimeError(secret)):
        with pytest.raises(BulkError) as failure:
            h.consume(case)
    assert secret not in str(failure.value)
    assert failure.value.__cause__ is None and failure.value.__context__ is None
    for path in (case['trial'].config.cache_dir/'objects').glob('*.json'):
        assert secret.encode() not in path.read_bytes()


def test_P5_T09_T12_current_registry_bytes_are_rechecked_at_consumption(case):
    release = json.loads((ROOT/'create_defaults/bulk/contracts/categories/data/release-v1.json').read_text())
    entry = next(v for v in release['entries'] if v['category'] == case['selection'].category)
    target = ROOT/'create_defaults/bulk/contracts'/entry['contract_path']
    original = Path.read_bytes
    def changed(path):
        raw = original(path)
        return raw + b' ' if path == target else raw
    with patch.object(Path, 'read_bytes', changed), pytest.raises(BulkError):
        h.consume(case)
    assert Path.read_bytes is original


def test_P5_T13_missing_network_companion_cannot_prepare_a_binding(native_rows):
    from create_defaults.bulk.lifecycle.composition_models import CompositionEvidence
    case = h.case(native_rows['Network'], 'missing-network-companion')
    value = case['row'][2].to_dict()
    value['views'][0]['members'] = value['views'][0]['members'][:1]
    with pytest.raises(BulkError):
        forged = CompositionEvidence.from_dict(value)
        SidecarStore(case['trial'].config.cache_dir).put_object(forged.encoded, expected_sha256=forged.sha256)
        case['consumer'].prepare(case['selection'], inputs=replace(case['inputs'], composition_sha256=forged.sha256), review_id='synthetic.review.missing-companion')


def test_P5_T14_receipt_must_still_belong_to_a_verified_owned_worker(artwork_case):
    case = artwork_case
    import sqlite3
    store = SidecarStore.open_readonly(case['trial'].config.cache_dir)
    member = case['row'][2].to_dict()['views'][0]['members'][0]
    receipt = json.loads(store.read_object(member['receipt_object_sha256']))
    with closing(sqlite3.connect(store.root/'state.sqlite3')) as db, db:
        before = db.execute('SELECT status FROM jobs WHERE id=?', (receipt['job_id'],)).fetchone()[0]
        db.execute('UPDATE jobs SET status=? WHERE id=?', ('pending', receipt['job_id']))
    try:
        with pytest.raises(BulkError):
            h.consume(case)
    finally:
        with closing(sqlite3.connect(store.root/'state.sqlite3')) as db, db:
            db.execute('UPDATE jobs SET status=? WHERE id=?', (before, receipt['job_id']))


def test_P5_T05_T10_cold_process_cannot_restore_live_authority_from_archive_json():
    code = """
from create_defaults.bulk.lifecycle.github_decisions import GitHubDecisionConsumer
from create_defaults.bulk.common import BulkError
consumer = object.__new__(GitHubDecisionConsumer)
try:
    consumer.consume({'status':'approved','authenticated':True,'context_sha256':'a'*64})
except BulkError as error:
    assert error.code == 'p5m3_real_policy_and_provider_unavailable'
    print('unavailable-no-observation-no-authority')
else:
    raise AssertionError('Archive JSON restored live permission')
"""
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True, timeout=35)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'unavailable-no-observation-no-authority'


@pytest.mark.parametrize('part', ['contract','rules','release','registry'])
def test_P5_T09_T30_exact_contract_source_bytes_must_match_current_selection(case, part):
    import base64
    query = case['queries']['source']
    prefix = 'repos/' + query.observer.target.repository
    values = query.observer._transport.responses
    files = {}
    for path in query.paths:
        expected = case['binding'].to_dict()['observations']['source']['snapshot']['selected']
        blob = next(row['blob'] for row in expected if row['path'] == path)
        files[path] = base64.b64decode(values[prefix+'/git/blobs/'+blob][0]['content'])
    chosen = next(path for path in files if
        ('/data/contracts/' in path and path.endswith('/genre-v1.json') and part == 'contract') or
        ('/rules/' in path and part == 'rules') or
        (path.endswith('/release-v1.json') and part == 'release') or
        (path.endswith('/review-registry-v1.json') and part == 'registry'))
    files[chosen] += b' changed-source'
    changed, _ = h.git_fixtures(query.observer.target, files, commit=h.HEAD)
    values.update(changed)
    with pytest.raises(BulkError, match='contract_source_bytes'):
        h.consume(case)
