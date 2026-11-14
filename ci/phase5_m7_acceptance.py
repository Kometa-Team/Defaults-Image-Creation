"""Read-only final-head dossier verification; never runs tests or writes inputs."""
import argparse
from collections import defaultdict
import hashlib
import importlib
import json
from pathlib import Path
import re
import stat
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ci.validation import identity, read, require, unique
from ci.people_storage_maintenance import regular

WORKFLOWS = ('Phase 5 M4 Current Mapping Validation', 'Phase 5 M3 Exact Decision Consumption', 'Lifecycle M7 Validation', 'Dependency provenance maintenance', 'Lifecycle M6 Validation', 'Phase 5 M2 Read-only Observations', 'Phase 5 M6 Offline Draft Transport', 'Default Poster Candidate Validation', 'Phase 5 M5 Owned Catalog Preparation', 'People startup job retention', 'People recovery storage regression', 'Portable People bulk validation')
COUNTS = {'packages': 22, 'variants': 278, 'conditional': 27, 'blocked': 251}


def closed(value, keys, label):
    require(isinstance(value, dict) and set(value) == set(keys), 'Invalid '+label)


def safe(root, name):
    require(isinstance(name, str) and name and '\\' not in name
            and not Path(name).is_absolute() and ':' not in name
            and all(p not in ('', '.', '..') for p in name.split('/')), 'Unsafe evidence path')
    return regular(root, name)


def load(path, expected_sha256=None, digest_message='Encoded evidence digest mismatch', text_lf=False):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'Duplicate JSON key')
            result[k] = v
        return result
    require(path.stat().st_size <= 16*1024*1024, 'JSON evidence size bound')
    with path.open('rb') as stream:
        raw = stream.read(16*1024*1024+1)
    require(len(raw) <= 16*1024*1024, 'JSON evidence size bound')
    encoded = raw.replace(b'\r\n', b'\n') if text_lf else raw
    if expected_sha256 is not None:
        require(hashlib.sha256(encoded).hexdigest() == expected_sha256, digest_message)
    return json.loads(raw.decode('utf8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, 'Nonfinite JSON'))


def index_files(root, index, expected):
    closed(index, ('head', 'base', 'plan_sha256', 'workflows', 'files'), 'PR evidence index')
    require(all(index[k] == expected[k] for k in ('head', 'plan_sha256')), 'Stale PR evidence index')
    require(re.fullmatch('[0-9a-f]{40}', index['base']) is not None, 'Invalid PR base')
    rows = index['workflows']
    require(unique([r['name'] for r in rows], 'workflow') == set(WORKFLOWS), 'Missing/extra workflow')
    for row in rows:
        closed(row, ('name', 'head', 'status', 'conclusion', 'url', 'jobs'), 'workflow')
        require(row['head'] == expected['head'] and row['status'] == 'completed'
                and row['conclusion'] == 'success' and row['jobs'], 'Incomplete workflow')
        require(re.fullmatch(r'https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/[0-9]+',
                             row['url']) is not None, 'Invalid run URL')
        unique([j['id'] for j in row['jobs']], 'job')
        for job in row['jobs']:
            closed(job, ('id', 'name', 'status', 'conclusion'), 'job')
            require(type(job['id']) is int and job['id'] > 0 and job['status'] == 'completed'
                    and job['conclusion'] == 'success', 'Incomplete job')
    require(len({r['url'] for r in rows}) == len(rows), 'Reused workflow run')
    names = unique([f['path'] for f in index['files']], 'artifact file')
    actual = set()
    for p in root.rglob('*'):
        info = p.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                'Linked artifact path')
        if p.is_file():
            actual.add(p.relative_to(root).as_posix())
    require(actual == names, 'Missing/extra artifact file')
    for item in index['files']:
        closed(item, ('path', 'sha256', 'workflow', 'artifact_id'), 'artifact file')
        require(item['workflow'] in WORKFLOWS and type(item['artifact_id']) is int
                and item['artifact_id'] > 0, 'Unknown artifact workflow or ID')
        p = safe(root, item['path'])
        # Stream encoded files; the existing native checks retain tighter limits.
        require(p.stat().st_size <= 200*1024*1024, 'Artifact file size bound')
        digest = hashlib.sha256()
        with p.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b''):
                digest.update(chunk)
        require(digest.hexdigest() == item['sha256'], 'Changed artifact bytes')


def verify_dossier(dossier, coverage, executed, expected_tests):
    closed(dossier, ('version', 'operational_authority', 'counts', 'requirements', 'documents'), 'M7 dossier')
    closed(dossier['documents'], ('support_sha256', 'handoff_sha256'), 'M7 document bindings')
    require(all(re.fullmatch('[0-9a-f]{64}', v) for v in dossier['documents'].values()), 'Invalid document digest')
    require(type(dossier['version']) is int and dossier['version'] == 1
            and dossier['operational_authority'] is False and dossier['counts'] == COUNTS,
            'Unsupported authority or coverage claim')
    original = read(ROOT/'create_defaults/lifecycle/PHASE5_M5_COVERAGE.json')
    closed(coverage, ('version', 'packages', 'variants', 'counts', 'publication_authorized'), 'M7 coverage')
    require(type(coverage['version']) is int and coverage['version'] == 1
            and coverage['publication_authorized'] is False and coverage['counts'] == COUNTS
            and coverage['packages'] == original['packages'] and coverage['variants'] == original['variants'],
            'Changed 22/278/27/251 disposition')
    rows = dossier['requirements']
    require(unique([r['id'] for r in rows], 'P5 requirement') == {f'P5-T{i:02}' for i in range(1, 35)},
            'Missing/extra P5 requirement')
    for row in rows:
        closed(row, ('id', 'tests'), 'requirement')
        tests = unique(row['tests'], row['id'])
        require(tests and expected_tests[row['id']] <= tests <= executed,
                'Missing/substituted requirement test IDs: '+row['id'])


def replay_phase5(module, milestone, selected, expected):
    pairs = {(p, g) for p in ('Windows', 'Linux')
             for g in (('all',) if milestone == 2 else module.GROUPS)}
    require(len(selected) == len(pairs)
            and {(r['platform'], r.get('group', 'all')) for _, r in selected} == pairs,
            'Missing/duplicate milestone platform/group')
    executed = set()
    for path, report in selected:
        native = None
        if (milestone == 3 and report['group'] == 'artwork'
                or milestone == 4 and report['group'] == 'sequence'):
            native = path.parent.parent/'native'
        if milestone in (5, 6) and report['group'] in module.NATIVE:
            native = path.parent.parent/'native'/module.NATIVE[report['group']]
        if native is not None:
            require(native.is_dir() and not native.is_symlink(), 'Missing native artifact directory')
        if milestone == 2:
            module.verify(report, expected)
        else:
            module.verify(report, expected, native_directory=native)
        executed.update(report['execution']['nodes'])
    return executed


def support_document(dossier, coverage):
    lines = ['# Phase 5 M7 offline acceptance and support', '',
             'Only active assigned English Genre single-logo variants are conditionally supported offline.',
             'All 22 real package approvals remain outstanding. Production authority: unavailable.',
             '27 conditional variants; 251 blocked variants; 278 variants across 22 packages.', '',
             '| Package / kind | Total | Conditional offline | Blocked |',
             '| --- | ---: | ---: | ---: |']
    for package in coverage['packages']:
        lines.append(f"| {package['category']} / {package['kind']} | {package['variants']} | {package['selected']} | {package['blocked']} |")
    lines += ['| Total | 278 | 27 | 251 |', '',
              'No other category, provider, language, generated family, overlay or retired identity is supported.',
              'Exact variant tuples and complete node IDs are in PHASE5_M7_COVERAGE.json and PHASE5_M7_ACCEPTANCE.json.', '',
              '| Requirement | Exact mapped tests |', '| --- | ---: |']
    for row in sorted(dossier['requirements'], key=lambda r: r['id']):
        lines.append(f"| {row['id']} | {len(row['tests'])} |")
    lines += ['', 'Final SHA and run/artifact links belong in the draft PR evidence index.',
              'Phase 5 acceptance grants no Phase 6 pilot, production write, publication, activation or merge.']
    return '\n'.join(lines)+'\n'


def handoff_document():
    return '''# Phase 6 handoff

Status: NOT STARTED. Pilot authorization: NOT GRANTED.

- Obtain separate pilot and exact operation/destination authorization.
- Obtain independently authenticated current identities, roles, source/destination heads, revision/withdrawal semantics and expiry/revocation policy.
- Obtain each selected exact package approval; all 22 real approvals remain outstanding.
- Keep contract approval, submitter confirmation, independent complete-artwork review, current catalog/source authorization, activation and transport as separate gates.
- Implement and accept the Playlist pilot adapter separately. Only 27 active assigned English Genre single-logo variants are conditionally supported offline; 251 variants remain blocked.
- Keep other categories, pairs, generated dependents, overlays, retired identities and non-English targets blocked pending their exact accepted adapters.
- Authorize any real catalog/destination write and recovery exercise separately; preserve verified successes and use exact forward-reviewed compensation.
- No remote deletion, cleanup, reset, forced push, automatic merge, publication or activation is authorized by Phase 5 completion.
- Keep all six Timeline Order requests deferred to separately authorized Phase 6 work.
- Preserve 9,957 posters, 4,122 overlays, 14,079 outputs, 14,077 public mappings and two private Awards intermediates, 2,106 physical inputs, 190 protected sources and 299 adoption pins, with zero unexplained historical differences.
- Require final-head Windows/Linux evidence and independent native artifact reconciliation; preserve existing read-only CI and sealed memory/process/object/pack/time limits.
- People and Diiivoycolor work remain outside Defaults lifecycle acceptance.

Final SHA and run/artifact links belong in the draft PR evidence index.
'''


def verify_documents(root, dossier, coverage, committed=None):
    release = read(root/'create_defaults/bulk/contracts/categories/data/release-v1.json')
    require(len(release['entries']) == 22 and all(e['approval'] == 'missing_exact_maintainer_decision'
            for e in release['entries']), 'Handoff approval state changed')
    for name, key, rendered in (
            ('PHASE5_M7_ACCEPTANCE_REPORT.md', 'support_sha256', support_document(dossier, coverage)),
            ('PHASE5_HANDOFF.md', 'handoff_sha256', handoff_document())):
        raw = safe(root, 'create_defaults/lifecycle/'+name).read_bytes().replace(b'\r\n', b'\n')
        if committed is not None:
            require(hashlib.sha256(raw).hexdigest() == committed[name], 'Uncommitted M7 document: '+name)
        require(hashlib.sha256(raw).hexdigest() == dossier['documents'][key]
                and raw.decode('utf8') == rendered, 'P5-T34 support/handoff mismatch: '+name)


def provenance_inputs(root, index, expected, provenance_path, provenance_sha256, archive_root):
    from ci import phase5_m7_provenance as provenance
    require(re.fullmatch('[0-9a-f]{64}', provenance_sha256) is not None, 'Missing independent provenance pin')
    # This pin is a trusted invocation input, never read from the index or dossier.
    snapshot = load(provenance_path, provenance_sha256, 'Independent provenance digest mismatch')
    rows = provenance.authenticate(ROOT, index, snapshot, expected)
    provenance.archives(root, archive_root, index, rows, safe)


def discover_reports(artifacts, index):
    reports = []
    owners = {'collection': 'Default Poster Candidate Validation',
              'group': 'Default Poster Candidate Validation',
              'phase3-foundations': 'Default Poster Candidate Validation',
              'phase4-operation-foundations': 'Default Poster Candidate Validation',
              'phase4-m6-execution': 'Lifecycle M6 Validation',
              'phase4-m7-execution': 'Lifecycle M7 Validation',
              'phase4-m7-native-sequence': 'Lifecycle M7 Validation'}
    owners.update({f'phase5-m{m}-fixture-execution': next(n for n in WORKFLOWS if n.startswith(f'Phase 5 M{m} '))
                   for m in range(2, 7)})
    for item in index['files']:
        p = safe(artifacts, item['path'])
        if p.suffix == '.json' and (p.name in (
                'report.json', 'collection.json', 'm6-report.json', 'm7-report.json',
                'm7-native-proof.json', 'phase3-report.json', 'phase4-report.json') or p.name.startswith('group-')):
            report = load(p, item['sha256'])
            if report.get('kind') in owners:
                require(item['workflow'] == owners[report['kind']], 'Artifact workflow substitution')
            reports.append((p, report, item['workflow']))
    return reports


def legacy_reports(reports):
    # Raw pytest collection.json exists in Phase 5 artifacts as well. Filename
    # equality alone must never route it into original Validation acceptance.
    return [r for _, r, owner in reports if owner == 'Default Poster Candidate Validation'
            and r.get('kind') in ('collection', 'group')]


def dossier_pins(root, head):
    from ci.phase5_m7_maintenance import git, sha
    result = {}
    for name in ('PHASE5_M7_ACCEPTANCE_REPORT.md', 'PHASE5_M7_ACCEPTANCE.json',
                 'PHASE5_M7_COVERAGE.json', 'PHASE5_HANDOFF.md'):
        path = 'create_defaults/lifecycle/'+name
        entry = git(root, 'ls-tree', '-z', head, '--', path).split(b'\0')
        require(len(entry) == 2 and entry[1] == b'' and entry[0].endswith(b'\t'+path.encode())
                and entry[0].startswith(b'100644 blob '), 'Missing/nonregular committed M7 dossier')
        result[name] = sha(git(root, 'show', head+':'+path))
    return result


def verify(dossier_path, artifacts, index_path, provenance_path, provenance_sha256, expected_head, archive_root):
    from ci.phase5_m7_maintenance import verify_checkout
    verify_checkout()
    expected = identity()
    require(re.fullmatch('[0-9a-f]{40}', expected_head) is not None and expected['head'] == expected_head,
            'Checkout differs from independently sourced final SHA')
    committed = dossier_pins(ROOT, expected_head)
    # Phase 4's reused verifier intentionally reads this exact existing location.
    artifacts = Path(artifacts).absolute()
    require(artifacts == ROOT/'config/ci-downloaded', 'Use the existing CI artifact download root')
    require(not artifacts.is_symlink() and artifacts.is_dir(), 'Missing artifact directory')
    for part in (artifacts, *artifacts.parents):
        info = part.lstat()
        require(stat.S_ISDIR(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                'Linked artifact parent')
        if part == ROOT:
            break
    dossier_path = safe(ROOT, 'create_defaults/lifecycle/PHASE5_M7_ACCEPTANCE.json') if dossier_path is None else Path(dossier_path).absolute()
    require(dossier_path == ROOT/'create_defaults/lifecycle/PHASE5_M7_ACCEPTANCE.json', 'Wrong dossier path')
    safe(ROOT, dossier_path.relative_to(ROOT).as_posix())
    coverage = load(safe(ROOT, 'create_defaults/lifecycle/PHASE5_M7_COVERAGE.json'),
                    committed['PHASE5_M7_COVERAGE.json'], 'Uncommitted M7 coverage', text_lf=True)
    index_path = Path(index_path).absolute()
    require(index_path == ROOT/'config/m7-pr-evidence-index.json', 'Wrong PR evidence index path')
    index = load(safe(ROOT, index_path.relative_to(ROOT).as_posix()))
    index_files(artifacts, index, expected)
    provenance_path, archive_root = Path(provenance_path).absolute(), Path(archive_root).absolute()
    require(provenance_path == ROOT/'config/m7-github-provenance.json'
            and archive_root == ROOT/'config/m7-archives', 'Wrong independent provenance input paths')
    safe(ROOT, provenance_path.relative_to(ROOT).as_posix())
    for part in (archive_root, *archive_root.parents):
        info = part.lstat()
        require(stat.S_ISDIR(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                'Linked archive parent')
        if part == ROOT:
            break
    provenance_inputs(artifacts, index, expected, provenance_path, provenance_sha256, archive_root)
    owned_reports = discover_reports(artifacts, index)
    reports = [(p, r) for p, r, _ in owned_reports]
    executed = set()
    expected_tests = defaultdict(set)
    for m in range(2, 7):
        module = importlib.import_module(f'ci.phase5_m{m}')
        selected = [(p, r) for p, r in reports if r.get('kind') == f'phase5-m{m}-fixture-execution']
        executed.update(replay_phase5(module, m, selected, expected))
        contract = read(ROOT/f'create_defaults/lifecycle/PHASE5_M{m}_ACCEPTANCE.json')
        families = ({r['id']: r['tests'] for r in contract['requirements']} if 'requirements' in contract
                    else contract.get('families', contract.get('test_requirements', {})))
        for rid, nodes in families.items():
            if rid.startswith('P5-T'):
                expected_tests[rid].update(nodes)
    from ci import validation, phase3, phase4, phase4_m6, phase4_m7
    legacy = legacy_reports(owned_reports)
    validation.reconcile(read(validation.PLAN_PATH), legacy, index['base'])
    phase3.verify_reports([r for _, r in reports if r.get('kind') == 'phase3-foundations'])
    phase4.verify_reports([r for _, r in reports if r.get('kind') == 'phase4-operation-foundations'])
    phase4_m6.verify_reports([r for _, r in reports if r.get('kind') == 'phase4-m6-execution'], expected)
    p4 = [r for _, r in reports if r.get('kind') == 'phase4-m7-execution']
    phase4_m7.verify_reports(p4, expected)
    proofs = [(p, r) for p, r in reports if r.get('kind') == 'phase4-m7-native-sequence']
    phase4_m7.verify_native([r for _, r in proofs], expected, {r['platform']: p.parent for p, r in proofs})
    preservation = phase4_m7.preservation()
    require(preservation['existing_files_checked'] == 2927 and preservation['unexplained_differences'] == 0,
            'Incomplete historical preservation')
    for _, r in reports:
        if r.get('kind') in {'phase3-foundations', 'phase4-operation-foundations',
                              'phase4-m6-execution', 'phase4-m7-execution'}:
            executed.update(r['execution']['nodes'])
    for r in legacy:
        if r.get('kind') == 'group' and 'pytest' in r:
            executed.update(r['pytest']['nodes'])
    plan = read(validation.PLAN_PATH)
    historical = set(plan['pytest_groups']['historical'])
    original_nodes = read(validation.BASELINE_PATH)['pytest']
    transport_limits = {'test_candidate_change_and_measured_pack_cap_stop_before_push',
                        'test_pack_cap_is_enforced_before_remote_branch_creation',
                        'test_incremental_pack_limit_stops_before_offline_push',
                        'test_memory_and_metadata_limits_are_enforced',
                        'test_resource_limits_and_explicit_failed_retry'}
    limit_nodes = {n for n in original_nodes if n.split('::')[-1] in transport_limits}
    require(len(limit_nodes) == len(transport_limits), 'Missing original transport limits')
    expected_tests['P5-T31'].update(limit_nodes)
    expected_tests['P5-T32'].update(n for n in original_nodes if n.split('::')[0] in historical)
    expected_tests['P5-T33'].update(read(phase4_m7.IDS)['controls'])
    expected_tests['P5-T34'].update(expected_tests['P5-T15'])
    require(all(expected_tests[f'P5-T{i:02}'] for i in range(1, 35)), 'Unmapped requirement')
    dossier = load(dossier_path, committed['PHASE5_M7_ACCEPTANCE.json'], 'Uncommitted M7 dossier', text_lf=True)
    verify_dossier(dossier, coverage, executed, expected_tests)
    verify_documents(ROOT, dossier, coverage, committed)
    require(identity() == expected, 'Checkout changed during replay')
    verify_checkout()
    return {'kind': 'phase5-m7-read-only-replay', 'success': True, 'head': expected['head'],
            'operational_authority': False, 'counts': COUNTS}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=('verify',))
    parser.add_argument('--dossier', type=Path)
    parser.add_argument('--artifacts', type=Path, default=ROOT/'config/ci-downloaded')
    parser.add_argument('--evidence-index', type=Path, required=True)
    parser.add_argument('--provenance', type=Path, required=True)
    parser.add_argument('--provenance-sha256', required=True)
    parser.add_argument('--expected-head', required=True)
    parser.add_argument('--archives', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.dossier, args.artifacts, args.evidence_index, args.provenance,
                           args.provenance_sha256, args.expected_head, args.archives), sort_keys=True))


if __name__ == '__main__':
    main()
