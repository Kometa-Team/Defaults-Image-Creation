"""Regression checks for the screen-pass versus approval discrepancy."""
from copy import deepcopy

import pytest

from create_defaults.bulk.common import BulkError, fingerprint
from create_defaults.bulk.library_first_wave import proposal, transport_proposal, split_populations
from create_defaults.bulk.library_sources import sealed
from create_defaults.bulk.library_transport import run
from create_defaults.bulk.library_visual import PROPOSED_POLICY
from create_defaults.bulk.tests.test_library_sync import inventory


def inputs(tmp_path):
    value = inventory(tmp_path)
    row = value['rows'][0]
    row.update(candidate_blob='a'*40, published_blob='b'*40, render_fingerprint='render',
               validation_fingerprint='validation', receipt_sha256='receipt',
               metrics={'same_dimensions': True, 'rgb_mae': 0, 'p99': 0,
                   'changed_fraction': {'16': 0}, 'global_luminance_ssim_200x300': 1,
                   'regions': {}, 'edge_mae': 0, 'alpha_mae': 0})
    baseline = dict(repository='Kometa-Team/Default-Images', branch='master', head='a'*40, tree='b'*40)
    value.update(kind='english', baseline=baseline)
    value.pop('sha256')
    return sealed(value), sealed(dict(baseline, entries=[]))


def test_warning_members_are_retained_and_unapproved(tmp_path):
    value, snapshot = inputs(tmp_path)
    value['rows'][0]['layout_risks'] = ['wrapped_caption']
    value.pop('sha256')
    result = proposal(sealed(value), PROPOSED_POLICY, snapshot, expected=1)
    assert result['members'][0]['approval_state'] == 'unresolved_layout_diagnostics'
    assert result['reviewer'] is None and result['decision'] == 'pending'
    assert not result['remote_writes_authorized'] and not result['policy_approved']
    plan = transport_proposal(result)
    with pytest.raises(BulkError, match='sealed local Git batch plan'):
        run(plan, tmp_path/'work', tmp_path/'base')


@pytest.mark.parametrize('change', ['missing_receipt', 'changed_policy', 'baseline', 'font', 'metrics', 'count'])
def test_exact_requested_population_fails_closed(tmp_path, change):
    value, snapshot = inputs(tmp_path)
    policy = deepcopy(PROPOSED_POLICY)
    if change == 'missing_receipt':
        value['rows'][0]['receipt_sha256'] = None
    elif change == 'changed_policy':
        policy['thresholds']['rgb_mae'] = 2
    elif change == 'baseline':
        value['baseline']['head'] = 'c'*40
    elif change == 'font':
        value['rows'][0]['font_change_expected'] = True
    elif change == 'metrics':
        value['rows'][0]['metrics']['rgb_mae'] = 5
    value.pop('sha256')
    with pytest.raises(BulkError):
        proposal(sealed(value), policy, snapshot, expected=2 if change == 'count' else 1)


def test_proposal_batch_caps_and_exact_byte_membership(tmp_path):
    value, snapshot = inputs(tmp_path)
    row = value['rows'][0]
    value['rows'] = [dict(row, destination=f'genre/{n:04}.jpg', candidate_bytes=1024**2) for n in range(601)]
    value.pop('sha256')
    result = proposal(sealed(value), PROPOSED_POLICY, snapshot, expected=601)
    plan = transport_proposal(result)
    assert [len(b['members']) for b in plan['batches']] == [200, 200, 200, 1]
    assert sum(len(b['members']) for b in plan['batches']) == 601
    assert plan['max_pack_bytes'] == 263192576
    assert plan['measured_pack_bytes'] is None
    assert result['policy_sha256'] == fingerprint(PROPOSED_POLICY)


def test_disjoint_populations_do_not_force_historical_counts(tmp_path):
    value, snapshot = inputs(tmp_path)
    other = dict(value['rows'][0], destination='genre/Warning.jpg', layout_risks=['wrapped_caption'])
    excluded = dict(value['rows'][0], destination='genre/Font.jpg', difference_class='font_changed')
    value['rows'].extend([other, excluded])
    value.pop('sha256')
    source = proposal(sealed(value), PROPOSED_POLICY, snapshot, expected=None)
    groups = split_populations(source)
    assert len(groups['A']['members']) == len(groups['B']['members']) == 1
    assert not set(m['destination'] for m in groups['A']['members']) & set(m['destination'] for m in groups['B']['members'])
    assert all(not m['layout_risks'] for m in groups['A']['members'])
    assert all(m['layout_risks'] for m in groups['B']['members'])
    assert len(source['excluded']) == 1
    assert groups['A']['decision'] == groups['B']['decision'] == 'pending'
