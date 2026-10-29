"""Additive exact-ID M2 fixture execution; all original CI remains mandatory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ci.validation import identity, read, write, require, unique, pytest_run, validate_execution

IDS = ROOT / 'ci/phase5-m2-test-ids.json'
OUT = ROOT / 'config/ci-validation/phase5-m2'
TESTS = 'create_defaults/phase5/m2_tests'
SOURCES = ('create_defaults/bulk/lifecycle/github_observations.py',
           'create_defaults/bulk/lifecycle/github_observation_transport.py',
           TESTS + '/test_observations.py', 'ci/phase5_m2.py')


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def inputs():
    return {name: digest(ROOT / name) for name in SOURCES}


def verify(report, expected):
    require(report.get('kind') == 'phase5-m2-fixture-execution' and report.get('success') is True,
            'Missing/failed M2 execution')
    require(all(report.get(k) == expected[k] for k in ('head', 'plan_sha256')), 'Stale M2 head/plan')
    require(report['ids_sha256'] == digest(IDS) and report['inputs'] == inputs(), 'Changed M2 inputs')
    selected = unique(read(IDS), 'M2 expected')
    require(selected and all(n.startswith(TESTS + '/test_observations.py::') for n in selected), 'Foreign M2 ID')
    for field in ('collection', 'execution'):
        require(report[field]['exitstatus'] == 0 and unique(report[field]['nodes'], field) == selected,
                'Missing or substituted M2 ID')
    counts = validate_execution(report['execution'])
    require(not counts.get('skipped') and report['authenticated_live_observations'] == 0
            and report['operational_authority'] is False, 'Synthetic/live evidence mismatch or skipped test')
    return counts


def run():
    report = dict(**identity(), kind='phase5-m2-fixture-execution', success=False,
        ids_sha256=digest(IDS), inputs=inputs(), authenticated_live_observations=0,
        operational_authority=False)
    try:
        report['collection'] = pytest_run([TESTS], OUT / 'collection.json', collect=True)
        report['execution'] = pytest_run([TESTS], OUT / 'execution.json')
        report['success'] = True
        verify(report, identity())
    finally:
        write(OUT / 'report.json', report)


def accept():
    needs = json.loads(os.environ['M2_JOB_RESULTS'])
    require(set(needs) == {'m2'} and needs['m2']['result'] == 'success', 'Missing/failed M2 matrix')
    reports = [read(p) for p in (ROOT / 'config/m2-downloaded').rglob('report.json')]
    require(len(reports) == 2 and {r['platform'] for r in reports} == {'Windows', 'Linux'}, 'Missing M2 platform')
    write(OUT / 'acceptance.json', dict(**identity(), kind='phase5-m2-fixture-acceptance',
        platforms={r['platform']: verify(r, identity()) for r in reports},
        success=True, authenticated_live_observations=0, operational_authority=False,
        original_workflows_required=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=['run', 'accept'])
    args = parser.parse_args()
    run() if args.action == 'run' else accept()
