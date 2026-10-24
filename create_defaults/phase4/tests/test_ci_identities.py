"""M2 proofs are mandatory, exact-head and cross-platform."""
from copy import deepcopy
from unittest.mock import patch
import pytest
from ci import phase4
from create_defaults.phase4.tests.test_ci_foundations import reports,verify


@pytest.mark.parametrize('field',['m2_schema_sha256','m2_golden_sha256','m2_canonical_sha256'])
def test_changed_m2_proof_cannot_satisfy_mandatory_acceptance(field):
    values=reports();values[0][field]='substituted'
    with pytest.raises(ValueError):verify(values)


@pytest.mark.parametrize('mutation',['missing','duplicate','head','plan','count','hash'])
def test_missing_stale_or_changed_m2_historical_proof_fails_closed(mutation):
    rows=[dict(head='head',plan_sha256='plan',platform=p,evidence=deepcopy(phase4.M2_HISTORICAL),evidence_sha256=phase4.fingerprint(phase4.M2_HISTORICAL)) for p in ['Windows','Linux']]
    if mutation=='missing':rows.pop()
    elif mutation=='duplicate':rows[0]['platform']='Linux'
    elif mutation=='head':rows[0]['head']='stale'
    elif mutation=='plan':rows[0]['plan_sha256']='stale'
    elif mutation=='count':rows[0]['evidence']['outputs']=14078
    else:rows[0]['evidence_sha256']='0'*64
    with patch.object(phase4,'identity',return_value=dict(head='head',plan_sha256='plan')):
        with pytest.raises(ValueError):phase4.verify_historical_reports(rows)


def test_complete_m2_historical_proofs_accepted_without_runtime_dependencies():
    rows=[dict(head='head',plan_sha256='plan',platform=p,evidence=deepcopy(phase4.M2_HISTORICAL),evidence_sha256=phase4.fingerprint(phase4.M2_HISTORICAL)) for p in ['Windows','Linux']]
    with patch.object(phase4,'identity',return_value=dict(head='head',plan_sha256='plan')):
        assert phase4.verify_historical_reports(rows)==phase4.M2_HISTORICAL
