"""Additive bounded M7 evidence using existing CI execution/replay contracts.

This verifies tests and historical compatibility, never operational authority.
The original Validation acceptance and separate M6 acceptance remain mandatory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ci.validation import identity, read, write, require, unique, pytest_run, validate_execution
from ci.phase4 import checksum, fingerprint

BASE = '68179d1c568449375ca72b23239b57770dfc229e'
IDS = ROOT/'ci/phase4-m7-test-ids.json'
COVERAGE = ROOT/'create_defaults/lifecycle/PHASE4_M7_COVERAGE.json'
OUT = ROOT/'config/ci-validation/m7'
GROUPS = ('controls', 'sequence', 'atomic', 'moves', 'boundaries')
NEW = frozenset((
    '.github/workflows/lifecycle-m7-validation.yml',
    'ci/phase4_m7.py', 'ci/phase4-m7-test-ids.json',
    'create_defaults/phase4/m7_tests/conftest.py',
    'create_defaults/phase4/m7_tests/helpers.py',
    'create_defaults/phase4/m7_tests/test_sequence.py',
    'create_defaults/phase4/m7_tests/test_recovery.py',
    'create_defaults/phase4/m7_tests/test_boundaries.py',
    'create_defaults/phase4/m7_tests/test_ci.py',
    'create_defaults/lifecycle/PHASE4_ACCEPTANCE_REPORT.md',
    'create_defaults/lifecycle/PHASE4_M7_IMPLEMENTATION.md',
    'create_defaults/lifecycle/PHASE4_M7_COVERAGE.json',
    'create_defaults/lifecycle/PHASE4_M7_CHANGED_FILES.md',
    'create_defaults/lifecycle/PHASE5_PREREQUISITES.md',
))
ALLOWED = NEW | {'create_defaults/lifecycle/ROADMAP.md'}


def implementation():
    paths = list((ROOT/'create_defaults/bulk/lifecycle').rglob('*.py'))
    paths += list((ROOT/'create_defaults/bulk/lifecycle/schemas').glob('*.json'))
    paths += list((ROOT/'create_defaults/phase4/m7_tests').glob('*.py'))
    paths += [Path(__file__).resolve()]
    return fingerprint({p.relative_to(ROOT).as_posix(): checksum(p) for p in sorted(paths)})


def selections():
    groups = read(IDS)
    require(set(groups) == set(GROUPS), 'Missing M7 group')
    seen = set()
    for name, nodes in groups.items():
        selected = unique(nodes, 'M7 '+name)
        require(selected and not selected & seen, 'Missing/duplicate M7 ID')
        require(all(n.startswith('create_defaults/phase4/m7_tests/test_') for n in selected), 'Foreign M7 ID')
        seen |= selected
    return groups, seen


def maintained_ids():
    """Explicit existing inventories only; no new test is silently discovered."""
    result = set(read(ROOT/'ci/original-test-ids.json')['pytest'])
    for name in ('phase3-test-ids.json', 'phase4-test-ids.json',
                 'phase4-composition-test-ids.json', 'phase4-review-test-ids.json',
                 'phase4-transaction-test-ids.json', 'phase4-m6-test-ids.json'):
        value = read(ROOT/'ci'/name)
        if isinstance(value, list):
            result |= set(value)
        else:
            result |= set().union(*(set(nodes) for nodes in value.values()))
    return result | selections()[1]


def coverage():
    value = read(COVERAGE)
    require(value['schema_version'] == 1 and value['baseline_commit'] == BASE, 'Changed M7 coverage baseline')
    require(value['operational_authority'] is False, 'Coverage cannot grant authority')
    require([r['id'] for r in value['requirements']] == ['T%02d'%n for n in range(1, 23)], 'Incomplete T01-T22 matrix')
    known = maintained_ids()
    for row in value['requirements']:
        require(row['expected_result'] and row['boundary'] and row['tests'], 'Missing expected boundary/result')
        require(unique(row['tests'], row['id']) <= known, 'Unmaintained coverage test')
    covered = set().union(*(set(row['tests']) for row in value['requirements']))
    require(selections()[1] - set(read(IDS)['controls']) <= covered, 'Unmapped native M7 regression')
    return value


def preservation():
    """Verify actual current source bytes and immutable approved provenance."""
    from ci.people_security_maintenance import verify
    from ci.dependency_maintenance import selected_hash, verify_infrastructure
    verify(ROOT)
    verify_infrastructure(ROOT)
    pins = read(ROOT/'create_defaults/bulk/contracts/adoption/source-pins-v1.json')
    require(len(pins['files']) == 299, 'Changed adoption membership')
    for item in pins['files']:
        raw = (ROOT/item['path']).read_bytes()
        if item['text_lf']:
            raw = raw.replace(b'\r\n', b'\n')
        require(hashlib.sha256(raw).hexdigest() == selected_hash(item['path'], item['sha256']),
                'Changed adopted source: '+item['path'])
    changed = set(subprocess.check_output(['git', 'diff', '--name-only', BASE, 'HEAD'], cwd=ROOT, text=True).splitlines())
    require(changed <= ALLOWED, 'M7 changed an existing runtime, policy, workflow or evidence boundary')
    # Existing runtime, test IDs, historical receipts and original CI source
    # must also remain physically unchanged in a local uncommitted checkout.
    entries = subprocess.check_output(['git', 'ls-tree', '-r', '-z', BASE,
        'ci', '.github/workflows', 'create_defaults'], cwd=ROOT).split(b'\0')
    # One streaming Git reader, one bounded blob at a time. Do not materialize
    # the whole artwork/source tree or start 2,928 subprocesses per CI job.
    reader = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=ROOT,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    checked = 0
    try:
        for entry in filter(None, entries):
            metadata, path = entry.split(b'\t', 1)
            name = path.decode('utf8')
            if name == 'create_defaults/lifecycle/ROADMAP.md':
                continue
            mode, kind, object_id = metadata.split()
            require(kind == b'blob' and mode in (b'100644', b'100755'), 'Unexpected baseline file type')
            reader.stdin.write(object_id+b'\n')
            reader.stdin.flush()
            header = reader.stdout.readline().split()
            require(len(header) == 3 and header[:2] == [object_id, b'blob'], 'Missing Git baseline object')
            old = reader.stdout.read(int(header[2]))
            require(reader.stdout.read(1) == b'\n', 'Incomplete Git baseline object')
            current = (ROOT/name).read_bytes()
            try:
                old.decode('utf8')
                is_text = b'\0' not in old
            except UnicodeDecodeError:
                is_text = False
            if is_text:
                current, old = current.replace(b'\r\n', b'\n'), old.replace(b'\r\n', b'\n')
            require(current == old, 'Changed frozen M7 baseline file: '+name)
            checked += 1
    finally:
        reader.stdin.close()
        reader.stdout.close()
        reader.stderr.close()
        reader.wait(timeout=30)
    require(reader.returncode == 0, 'Git baseline reader failed')
    return dict(baseline_commit=BASE, protected_members=190, adoption_sources=299,
                existing_files_checked=checked, changed_files=sorted(changed),
                unexplained_differences=0, production_activation=False, publication_authorized=False)


def verify_report(report, expected):
    require(report.get('kind') == 'phase4-m7-execution' and report.get('success') is True, 'Missing/failed M7 report')
    require(all(report.get(k) == expected[k] for k in ('head', 'plan_sha256')), 'Stale M7 head/plan')
    require(report['ids_sha256'] == checksum(IDS) and report['coverage_sha256'] == checksum(COVERAGE)
            and report['implementation_sha256'] == implementation(), 'Changed M7 evidence inputs')
    groups, nodes = selections()
    require(report['group'] in groups, 'Unknown M7 group')
    selected = set(groups[report['group']])
    for field, required in (('all_collection', nodes), ('collection', selected), ('execution', selected)):
        require(report[field]['exitstatus'] == 0 and unique(report[field]['nodes'], field) == required, 'Missing/substituted M7 ID')
    counts = validate_execution(report['execution'])
    require(not counts.get('skipped'), 'M7 skip cannot satisfy acceptance')
    require(report['preservation']['unexplained_differences'] == 0 and
            report['preservation']['baseline_commit'] == BASE and
            report['preservation']['protected_members'] == 190 and
            report['preservation']['adoption_sources'] == 299 and
            report['preservation']['production_activation'] is False and
            report['preservation']['publication_authorized'] is False, 'Missing preservation checks')
    return dict(counts=counts, seconds=report['execution']['seconds'])


def verify_reports(reports, expected):
    pairs = {(platform, group) for platform in ('Windows', 'Linux') for group in GROUPS}
    require(len(reports) == len(pairs) and {(r['platform'], r['group']) for r in reports} == pairs,
            'Missing/duplicate M7 platform/group')
    return {platform: {group: verify_report(next(r for r in reports if (r['platform'], r['group']) == (platform, group)), expected)
                      for group in GROUPS} for platform in ('Windows', 'Linux')}


def verify_native(proofs, expected, artifacts):
    require(len(proofs) == 2 and {r['platform'] for r in proofs} == {'Windows', 'Linux'}, 'Missing/duplicate native sequence')
    for proof in proofs:
        require(all(proof.get(k) == expected[k] for k in ('head', 'plan_sha256')), 'Stale native sequence')
        require(proof['sha256'] == fingerprint({k: v for k, v in proof.items() if k != 'sha256'}), 'Changed native proof')
        require(proof['kind'] == 'phase4-m7-native-sequence' and
                proof['operations'] == ['ADD', 'UPDATE', 'RENAME', 'DELETE'], 'Incomplete native sequence')
        require(all(proof.get(k) is True for k in ('cold_restart_verified', 'exact_retries_verified', 'history_retained', 'isolated_only'))
                and all(proof.get(k) is False for k in ('authenticated', 'operation_accepted', 'applied',
                    'artwork_approved', 'contract_approved', 'ready', 'active', 'production_enforcement',
                    'publication_authorized')), 'Missing recovery or synthetic boundary')
        require(proof['add_artwork']['sha256'] != proof['update_artwork']['sha256']
                and proof['active_members'] == [] and proof['unrelated_record_preserved'] is True
                and len(proof['mapping_plans']) == 2, 'Missing material update/retention evidence')
        require(proof['permanent_id'] and proof['tombstone_sha256'] and proof['unrelated_record_sha256'], 'Missing stable identity/tombstone')
        require(proof['platform'] in artifacts, 'Missing exported native artwork')
        for name in ('add', 'update'):
            path = Path(artifacts[proof['platform']])/'artwork'/(name+'.jpg')
            require(path.is_file() and not path.is_symlink(), 'Missing exported native artwork')
            raw = path.read_bytes()
            member = proof[name+'_artwork']
            require(hashlib.sha256(raw).hexdigest() == member['sha256'] and len(raw) == member['bytes'],
                    'Changed exported native artwork')
    # JPEG comparison is exact, with no new equivalence threshold. Existing
    # M3 reports retain their separate PNG/native-encoding environment evidence.
    require(all(proofs[0][key]['sha256'] == proofs[1][key]['sha256'] for key in
                ('add_artwork', 'update_artwork')), 'Cross-platform native JPEG difference')
    return {r['platform']: r for r in proofs}


def run(group):
    groups, _ = selections()
    require(group in groups, 'Unknown M7 group')
    coverage()
    out = OUT/group
    report = dict(**identity(), kind='phase4-m7-execution', group=group, success=False,
        ids_sha256=checksum(IDS), coverage_sha256=checksum(COVERAGE), implementation_sha256=implementation())
    try:
        report['preservation'] = preservation()
        report['all_collection'] = pytest_run(['create_defaults/phase4/m7_tests'], out/'m7-all-collection.json', collect=True)
        response = out/'selected.txt'
        response.parent.mkdir(parents=True, exist_ok=True)
        response.write_text('\n'.join(groups[group])+'\n', encoding='utf8', newline='\n')
        report['collection'] = pytest_run(['@'+str(response)], out/'m7-collection.json', collect=True)
        report['execution'] = pytest_run(['@'+str(response)], out/'m7-execution.json')
        require(report['implementation_sha256'] == implementation(), 'Source changed during M7 execution')
        report['success'] = True
        verify_report(report, identity())
    except BaseException:
        report['success'] = False
        raise
    finally:
        write(out/'m7-report.json', report)


def accept():
    import os
    needs = json.loads(os.environ['M7_JOB_RESULTS'])
    require(set(needs) == {'m7'} and needs['m7']['result'] == 'success', 'M7 matrix failed, cancelled or missing')
    directory = ROOT/'config/m7-downloaded'
    reports = [read(p) for p in directory.rglob('m7-report.json')]
    proof_files = list(directory.rglob('m7-native-proof.json'))
    proofs = [read(p) for p in proof_files]
    artifacts = {read(p)['platform']: p.parent for p in proof_files}
    value = dict(**identity(), kind='phase4-m7-acceptance', success=True,
        platforms=verify_reports(reports, identity()), native=verify_native(proofs, identity(), artifacts),
        coverage_sha256=checksum(COVERAGE), operational_authority=False,
        original_validation_required=True, m6_acceptance_required=True)
    write(OUT/'m7-acceptance.json', value)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=['run', 'accept'])
    parser.add_argument('--group', choices=GROUPS)
    args = parser.parse_args()
    if args.action == 'run':
        if args.group is None:
            parser.error('--group required for run')
        run(args.group)
    else:
        accept()
