"""M3 exact-ID offline decision consumption. Original acceptance is mandatory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ci.validation import identity, read, write, require, unique, pytest_run, validate_execution

IDS = ROOT / 'ci/phase5-m3-test-ids.json'
OUT = ROOT / 'config/ci-validation/phase5-m3'
TESTS = 'create_defaults/phase5/m3_tests'
GROUPS = ('protocol', 'artwork', 'context')
SOURCES = ('create_defaults/bulk/lifecycle/github_decisions.py',
           'create_defaults/bulk/lifecycle/github_observations.py',
           'create_defaults/bulk/lifecycle/github_observation_transport.py',
           TESTS + '/test_decisions.py', TESTS + '/helpers.py', 'ci/phase5_m3.py')


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def inputs():
    return {name: digest(ROOT / name) for name in SOURCES}


def selections():
    groups = read(IDS)
    require(set(groups) == set(GROUPS), 'Missing M3 bounded group')
    seen = set()
    for name in GROUPS:
        nodes = unique(groups[name], name)
        require(nodes and not seen & nodes and all(n.startswith(TESTS+'/test_decisions.py::') for n in nodes), 'Missing/duplicate/foreign M3 ID')
        seen |= nodes
    return groups


def native_artifacts(directory):
    from io import BytesIO
    from PIL import Image
    from create_defaults.bulk.common import canonical, fingerprint
    groups, images = {}, {}
    directory = Path(directory)
    require({p.name for p in directory.glob('*.json')} == {'Genre.json', 'Network.json'}, 'Missing M3 native cohorts')
    for category, count in [('Genre', 2), ('Network', 4)]:
        path = directory / (category + '.json')
        value = read(path)
        require(fingerprint(value['composition']) == value['composition_sha256'], 'Changed native composition')
        require(len(value['rows']) == count, 'Incomplete native artifact set')
        composed = value['composition']
        require({v['appearance'] for v in composed['views']} == {'default', 'requested'}, 'Missing full native view')
        require(all(len(v['members']) == count//2 and {m['identity'] for m in v['members']} == set(composed['required_members'])
                    for v in composed['views']), 'Missing native companion')
        require(all(value['consumption_receipt'][k] is False for k in ('authenticated', 'ready', 'active', 'publication_authorized', 'contract_approved')), 'Fixture artifact claims authority')
        for row in value['rows']:
            name, member, receipt, worker = (row[k] for k in ('file', 'member', 'receipt', 'worker'))
            require(Path(name).name == name and name not in images, 'Unsafe/duplicate native artifact')
            raw = (directory/name).read_bytes()
            require(len(raw) <= 64*1024*1024 and hashlib.sha256(raw).hexdigest() == member['sha256'] == receipt['sha256'], 'Changed actual encoded artwork')
            require(len(raw) == member['bytes'] == receipt['size'], 'Changed native bytes length')
            require(receipt['receipt_sha256'] == fingerprint({k:v for k,v in receipt.items() if k != 'receipt_sha256'}) == member['receipt_sha256'], 'Changed owned receipt')
            require(worker['status'] == 'verified' and worker['id'] == receipt['job_id'] and worker['receipt'] == canonical(receipt).decode(), 'Foreign worker receipt')
            require(fingerprint(json.loads(worker['spec'])) == worker['fingerprint'] == receipt['job_fingerprint'], 'Foreign worker specification')
            with Image.open(BytesIO(raw)) as image:
                image.load()
                require((image.format, image.mode, list(image.size)) == (member['format'], member['mode'], member['dimensions']), 'Thumbnail/geometry substitution')
            images[name] = dict(sha256=member['sha256'], bytes=len(raw), dimensions=member['dimensions'], receipt_sha256=member['receipt_sha256'])
        groups[category] = digest(path)
    require(len(images) == 6 and sum(v['bytes'] for v in images.values()) <= 64*1024*1024, 'Missing/oversized encoded native evidence')
    require({p.name for p in directory.iterdir()} == set(images) | {'Genre.json', 'Network.json'}, 'Foreign native artifact')
    return dict(groups=groups, images=images)


def verify(report, expected, *, native_directory=None):
    require(report.get('kind') == 'phase5-m3-fixture-execution' and report.get('success') is True, 'Missing/failed M3 execution')
    require(all(report.get(k) == expected[k] for k in ('head', 'plan_sha256')), 'Stale M3 head/plan')
    require(report['ids_sha256'] == digest(IDS) and report['inputs'] == inputs(), 'Changed M3 inputs')
    require(report.get('group') in GROUPS, 'Unknown M3 bounded group')
    selected = unique(selections()[report['group']], 'M3 expected')
    for field in ('collection', 'execution'):
        require(report[field]['exitstatus'] == 0 and unique(report[field]['nodes'], field) == selected, 'Missing/substituted M3 ID')
    counts = validate_execution(report['execution'])
    require(not counts.get('skipped') and report['authenticated_live_observations'] == 0
            and report['real_decisions_consumed'] == 0 and report['real_package_approvals'] == 0
            and report['operational_authority'] is False, 'Synthetic/live mismatch or skipped test')
    if report['group'] == 'artwork':
        require(set(report['native_artifacts']['groups']) == {'Genre', 'Network'} and len(report['native_artifacts']['images']) == 6, 'Missing native artifact report')
        if native_directory is not None:
            require(report['native_artifacts'] == native_artifacts(native_directory), 'Changed actual native artifacts')
    else:
        require(report['native_artifacts'] is None, 'Unexpected native artifact group')
    return counts


def run(group):
    nodes = selections()[group]
    out = OUT/group
    report = dict(**identity(), kind='phase5-m3-fixture-execution', success=False, ids_sha256=digest(IDS), inputs=inputs(),
        group=group, authenticated_live_observations=0, real_decisions_consumed=0, real_package_approvals=0, operational_authority=False)
    try:
        os.environ['M3_NATIVE_EXPORT'] = 'config/ci-validation/phase5-m3/native'
        report['collection'] = pytest_run(nodes, out / 'collection.json', collect=True)
        report['execution'] = pytest_run(nodes, out / 'execution.json')
        report['native_artifacts'] = native_artifacts(OUT / 'native') if group == 'artwork' else None
        report['success'] = True
        verify(report, identity())
    finally:
        write(out / 'report.json', report)


def accept():
    needs = json.loads(os.environ['M3_JOB_RESULTS'])
    require(set(needs) == {'m3'} and needs['m3']['result'] == 'success', 'Missing/failed M3 matrix')
    reports = [read(p) for p in (ROOT / 'config/m3-downloaded').rglob('report.json')]
    require(len(reports) == 6 and {(r['platform'],r['group']) for r in reports} == {(p,g) for p in ('Windows','Linux') for g in GROUPS}, 'Missing M3 platform/group')
    write(OUT / 'acceptance.json', dict(**identity(), kind='phase5-m3-fixture-acceptance',
        groups={r['platform']+'/'+r['group']: verify(r, identity(), native_directory=path.parent.parent/'native')
                   for path in (ROOT / 'config/m3-downloaded').rglob('report.json') for r in [read(path)]}, success=True,
        authenticated_live_observations=0, real_decisions_consumed=0, real_package_approvals=0,
        operational_authority=False, original_workflows_required=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=['run', 'accept'])
    parser.add_argument('--group', choices=GROUPS)
    args = parser.parse_args()
    if args.action == 'run':
        require(args.group in GROUPS, 'Explicit bounded group required')
        run(args.group)
    else:
        accept()
