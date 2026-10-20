"""Prepare an unsigned English first-wave proposal; never grants approval or writes remotes."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import subprocess

from .common import BulkError, confined, fingerprint, reject_links, sha256
from .config import ROOT
from .library_publication import validate_paths
from .library_sources import (blob_id, check_seal, load_json, reference,
                              runtime_identity, save, sealed)
from .library_sync import candidate_context, current_catalog, font_impacts
from .library_visual import evaluate


def proposal(inventory, policy, snapshot, expected=9785):
    """Keep screen passage distinct from unresolved layout diagnostics and approval."""
    check_seal(inventory)
    check_seal(snapshot)
    baseline = {k: snapshot[k] for k in ('repository', 'branch', 'head', 'tree')}
    if inventory['kind'] != 'english' or inventory['baseline'] != baseline:
        raise BulkError('baseline_drift', 'English comparison baseline differs from fresh production snapshot')
    if fingerprint(policy) != inventory['policy_sha256']:
        raise BulkError('stale_policy', 'Exact compared English policy required')
    validate_paths(inventory['rows'])
    selected, excluded = [], []
    for row in sorted(inventory['rows'], key=lambda r: r['destination']):
        if row['difference_class'] != 'renderer_equivalence_pending_policy':
            excluded.append({k: row.get(k) for k in ('destination', 'candidate_sha256',
                'published_sha256', 'difference_class', 'context_sha256', 'layout_risks', 'blockers')})
            continue
        required = ('candidate_sha256', 'published_sha256', 'candidate_blob', 'published_blob',
                    'context_sha256', 'render_fingerprint', 'validation_fingerprint', 'receipt_sha256')
        if any(not row.get(k) for k in required):
            raise BulkError('missing_identity', 'Missing first-wave identity: ' + row['destination'])
        if (row['kind'] != 'poster' or '/overlays/' in row['destination']
                or row['hash_state'] != 'unequal' or row['candidate_sha256'] == row['published_sha256']
                or row.get('font_change_expected') or row.get('blockers') or not row['technical_valid']
                or not evaluate(row['metrics'], policy)['screen_pass']):
            raise BulkError('ineligible_member', 'Candidate no longer meets proposed scope: ' + row['destination'])
        selected.append({**{k: row[k] for k in required}, 'destination': row['destination'],
            'size': row['candidate_bytes'], 'layout_risks': row.get('layout_risks', []),
            'approval_state': 'unresolved_layout_diagnostics' if row.get('layout_risks') else 'policy_approval_pending'})
    if expected is not None and len(selected) != expected:
        raise BulkError('membership_drift', f'Expected {expected} screen-pass members, found {len(selected)}; no substitution')
    return sealed({'schema_version': 1, 'kind': 'unsigned-english-first-wave-proposal',
        'inventory_sha256': inventory['sha256'], 'baseline': baseline,
        'policy': policy, 'policy_sha256': fingerprint(policy),
        'members': selected, 'membership_sha256': fingerprint(selected), 'excluded': excluded,
        'scope': 'unchanged-font, unchanged-layout English only; unresolved diagnostics withhold publication',
        'decision': 'pending', 'reviewer': None, 'policy_approved': False,
        'remote_writes_authorized': False, 'merge_authorized': False})


def transport_proposal(candidate):
    """Same technical caps as existing transport, deliberately non-executable kind."""
    check_seal(candidate)
    batches, members, size = [], [], 0
    for member in candidate['members']:
        if member['size'] > 200 * 1024**2:
            raise BulkError('batch_oversize', 'Single candidate exceeds technical data cap')
        if members and (len(members) == 300 or size + member['size'] > 200 * 1024**2):
            batches.append({'members': members, 'bytes': size})
            members, size = [], 0
        members.append(member)
        size += member['size']
    if members:
        batches.append({'members': members, 'bytes': size})
    return sealed({'kind': 'non-executable-first-wave-transport-proposal',
        'candidate_manifest_sha256': candidate['sha256'], 'baseline': candidate['baseline'],
        'logical_publication_groups': 1, 'draft_prs_after_approval': 1,
        'max_files': 300, 'max_bytes': 200 * 1024**2, 'max_pack_bytes': 251 * 1024**2,
        'pack_measurement_required_before_each_push': True, 'measured_pack_bytes': None,
        'batches': [dict(b, sequence=i+1, membership_sha256=fingerprint(b['members'])) for i,b in enumerate(batches)],
        'remote_writes_authorized': False})


def split_populations(candidate):
    """Content-bound disjoint populations; compute counts rather than padding them."""
    check_seal(candidate)
    results = {}
    for name, warning in [('A', False), ('B', True)]:
        members = [m for m in candidate['members'] if bool(m['layout_risks']) == warning]
        results[name] = sealed({'kind': 'unsigned-english-population-'+name,
            'parent_proposal_sha256': candidate['sha256'], 'inventory_sha256': candidate['inventory_sha256'],
            'baseline': candidate['baseline'], 'policy_sha256': candidate['policy_sha256'],
            'members': members, 'membership_sha256': fingerprint(members),
            'excluded_other_populations_sha256': fingerprint(candidate['excluded']),
            'decision': 'pending', 'reviewer': None, 'remote_writes_authorized': False})
    return results


def prepare(root, analysis, output, *, population='all'):
    root, analysis, output = Path(root), Path(analysis), Path(output)
    inventory = check_seal(load_json(analysis / 'english-reconciled-inventory.json'))
    policy = load_json(analysis / 'proposed-tolerance-policy.json')
    snapshot = check_seal(load_json(root / 'production-snapshot.json'))
    candidate = proposal(inventory, policy, snapshot, expected=None if population == 'A' else 9785)
    populations = split_populations(candidate)
    if population == 'A':
        candidate.pop('sha256')
        outside = [dict(m, difference_class='renderer_equivalence_pending_policy')
                   for m in populations['B']['members']]
        candidate = sealed(dict(candidate, kind='unsigned-english-group-a-proposal',
            members=populations['A']['members'], membership_sha256=populations['A']['membership_sha256'],
            excluded=candidate['excluded']+outside, population_sha256=populations['A']['sha256'],
            scope='Group A only: same font, no warning/error diagnostics, unchanged validated layout'))
    git_directory = root / 'baseline.git'
    fetched = subprocess.check_output(['git', '--git-dir='+str(git_directory), 'rev-parse',
        'FETCH_HEAD^{commit}', 'FETCH_HEAD^{tree}'], text=True).splitlines()
    if fetched != [snapshot['head'], snapshot['tree']]:
        raise BulkError('baseline_drift', 'Actual Git fetch differs from fresh API snapshot')
    calibration = check_seal(load_json(analysis / 'tolerance-calibration.json'))
    if (calibration['policy_sha256'] != fingerprint(policy)
            or calibration['in_scope_accepted_positive_rejections'] or calibration['defective_controls_missed']):
        raise BulkError('calibration_drift', 'Exact passing in-scope calibration and rejecting controls required')
    baseline, current = current_catalog(root / 'catalog')
    if baseline['preflight_sha256'] != inventory['catalog_preflight_sha256']:
        raise BulkError('catalog_drift', 'Fresh source/font/layout preflight differs from recorded inventory')
    if runtime_identity() != inventory['runtime']:
        raise BulkError('runtime_drift', 'Renderer or native encoding dependencies changed')
    data = reference('english')
    if data['manifest_header']['sha256'] != inventory['reference_manifest']:
        raise BulkError('reference_drift', 'Validated Python reference changed')
    summary = check_seal(load_json(analysis / 'reconciliation-summary.json'))
    for name, expected_sha in summary['source_files_sha256'].items():
        if sha256(confined(ROOT.parent, name, must_exist=True)) != expected_sha:
            raise BulkError('source_drift', 'Recorded analysis source changed: ' + name)
    jobs = {r['job']['id']: r for r in data['rows']}
    reference_by_path = {r['job']['remote_relative']: r for r in data['rows']}
    impact = font_impacts(data['rows'])
    contexts = sealed({'reference_manifest_sha256': data['manifest_header']['sha256'],
        'renderer': data['manifest_header']['renderer'], 'runtime': inventory['runtime'],
        'members': [{'destination': m['destination'],
            'job': reference_by_path[m['destination']]['job'],
            'receipt': reference_by_path[m['destination']]['receipt'],
            'validation': reference_by_path[m['destination']]['validation'],
            'context_sha256': m['context_sha256']} for m in candidate['members']]})
    candidate.pop('sha256')
    candidate = sealed(dict(candidate, context_identities_sha256=contexts['sha256'],
        reference_manifest_sha256=data['manifest_header']['sha256']))
    public = {r['job']['remote_relative'] for r in data['rows'] if r['job']['remote_relative'] is not None}
    if public != {r['destination'] for r in inventory['rows']}:
        raise BulkError('catalog_drift', 'Complete English destination set changed')
    input_paths = {item['path'] for row in data['rows'] for item in row['job']['inputs']}
    inputs = {path: sha256(confined(ROOT, path, must_exist=True)) for path in input_paths}
    parents = {d['job_id'] for r in data['rows'] for d in r['job']['dependencies']}
    for identity in parents:
        inputs['job:' + identity] = sha256(confined(output, jobs[identity]['job']['local_relative'], must_exist=True))
    entries = {e['path']: e for e in snapshot['entries']}
    by_key = {}
    from .common import path_key
    for e in snapshot['entries']:
        by_key.setdefault(path_key(e['path']), []).append(e['path'])
    def verify(row):
        ref = jobs[row['id']]
        path, variant = candidate_context(ref, output, data, current, inputs)
        warnings = [d['code'] for d in variant.get('diagnostics', []) if d['severity'] == 'warning']
        if population == 'A' and any(d['severity'] in {'warning', 'error'} for d in variant.get('diagnostics', [])):
            raise BulkError('new_diagnostic', 'Group A has a current validation blocker: '+row['destination'])
        expected_context = fingerprint({'job': ref['job'], 'validation': ref['validation'],
            'renderer': data['manifest_header']['renderer'], 'policy': policy, 'baseline': snapshot['head']})
        enriched_context = fingerprint({'analysis_context': expected_context, 'policy': policy})
        if (expected_context != row['analysis_context_sha256'] or enriched_context != row['context_sha256']
                or warnings != row['layout_risks'] or impact[row['id']]['all_fonts']
                or ref['receipt']['sha256'] != row['candidate_sha256']
                or ref['receipt']['size'] != row['candidate_bytes']
                or ref['receipt']['receipt_sha256'] != row['receipt_sha256']
                or ref['job']['render_fingerprint'] != row['render_fingerprint']
                or ref['validation']['fingerprint'] != row['validation_fingerprint']
                or ref['job']['remote_relative'] != row['destination'] or blob_id(path) != row['candidate_blob']):
            raise BulkError('identity_drift', 'Candidate/font/layout/context changed: ' + row['destination'])
        entry = entries.get(row['destination'])
        if (not entry or entry['mode'] != '100644' or entry['type'] != 'blob'
                or entry['sha'] != row['published_blob'] or entry['size'] != row['published_bytes']
                or by_key[path_key(row['destination'])] != [row['destination']]):
            raise BulkError('remote_drift', 'Fresh production destination/blob/mode differs: ' + row['destination'])
        published = reject_links(row['published_path'])
        if sha256(published) != row['published_sha256'] or blob_id(published) != entry['sha']:
            raise BulkError('published_drift', 'Comparison bytes no longer match fresh remote tree: ' + row['destination'])
        return row['destination']
    wanted = {m['destination'] for m in candidate['members']}
    rows = [r for r in inventory['rows'] if r['destination'] in wanted]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for n, _ in enumerate(pool.map(verify, rows), 1):
            if n % 1000 == 0:
                print(f'[VERIFIED] {n}/{len(rows)} candidate, receipt, context and fresh remote identity', flush=True)
    transport = transport_proposal(candidate)
    warnings = [m for m in candidate['members'] if m['layout_risks']]
    free = shutil.disk_usage(root).free
    total = sum(m['size'] for m in candidate['members'])
    reasons = ['explicit_policy_and_manifest_approval_missing']
    if warnings:
        reasons.append('unresolved_layout_diagnostics')
    # A full target clone/repack estimate is unavailable; do not assert disk sufficiency.
    reasons.append('full_staging_repository_disk_and_recovery_preflight_pending')
    request = sealed({'kind': 'unsigned-maintainer-decision-request', 'decision': 'pending', 'reviewer': None,
        'candidate_manifest_sha256': candidate['sha256'], 'membership_sha256': candidate['membership_sha256'],
        'inventory_sha256': inventory['sha256'], 'baseline': candidate['baseline'],
        'policy_sha256': fingerprint(policy), 'exact_thresholds': policy['thresholds'],
        'calibration_sha256': calibration['sha256'], 'positive_count': calibration['in_scope_accepted_positive_count'],
        'negative_count': len(calibration['negative_controls']),
        'excluded_membership_sha256': fingerprint(candidate['excluded']),
        'unresolved_diagnostics_membership_sha256': fingerprint(warnings),
        'blocking_reasons': reasons, 'requested_members': len(rows),
        'diagnostic_free_policy_pending': len(rows)-len(warnings), 'diagnostic_withheld': len(warnings),
        'warning_counts': dict(Counter(w for m in warnings for w in m['layout_risks'])),
        'source_commit': subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
        'source_module_sha256': sha256(Path(__file__)), 'candidate_bytes': total, 'disk_free_bytes': free,
        'transport_plan_sha256': transport['sha256'], 'transport_batches': len(transport['batches']),
        'remote_branch': None, 'publication_pr': None, 'remote_writes': 0, 'uploaded_files': 0,
        'remote_hash_verified_this_wave': 0, 'upload_duration_seconds': 0,
        'failures_or_recovery_events': [], 'status': 'blocked_before_remote_staging'})
    reconciliation = sealed({'expected_english_public_images': inventory['expected'],
        'exact_binary_matches': sum(r['hash_state'] == 'exact_match' for r in inventory['rows']),
        'binary_different_approved_for_replacement': 0, 'published_and_remotely_hash_verified': 0,
        'withheld_or_blocked': sum(r['hash_state'] != 'exact_match' for r in inventory['rows']),
        'remaining_python_published_sha256_mismatches': inventory['remaining_verified_sha256_mismatches'],
        'requested_first_wave': len(rows), 'unresolved_first_wave_layout_diagnostics': len(warnings),
        'scope': 'English only; overlays and private outputs excluded',
        'candidate_manifest_sha256': candidate['sha256'], 'approval_request_sha256': request['sha256'],
        'baseline': candidate['baseline'], 'remote_writes': 0})
    root.mkdir(parents=True, exist_ok=True)
    def immutable_save(path, value):
        if path.exists():
            if load_json(path) != value:
                raise BulkError('immutable_package', 'Existing package differs; use a new preparation root')
        else:
            save(path, value)
    for name, value in [('candidate-manifest',candidate), ('transport-proposal',transport),
            ('approval-request',request), ('calibration',calibration),
            ('reconciliation',reconciliation),
            ('context-identities',contexts),
            ('group-a-population',populations['A']), ('group-b-population',populations['B']),
            ('unresolved-layout-diagnostics',sealed({'members': warnings})),
            ('excluded-candidates',sealed({'members': candidate['excluded']}))]:
        immutable_save(root / (name+'.json'), value)
    journal = sealed({'kind': 'unstarted-first-wave-upload-journal', 'candidate_manifest_sha256': candidate['sha256'],
        'transport_proposal_sha256': transport['sha256'], 'baseline': candidate['baseline'],
        'batches': [{'sequence': b['sequence'], 'membership_sha256': b['membership_sha256'],
            'state': 'blocked_before_commit', 'commit': None, 'measured_pack_bytes': None,
            'members': [{k:m[k] for k in ('destination','candidate_sha256','candidate_blob','published_blob')}
                        for m in b['members']]} for b in transport['batches']], 'remote_writes': 0})
    immutable_save(root / 'upload-journal.json', journal)
    if population == 'A':
        bindings = [{k:r[k] for k in ('destination','candidate_sha256','published_sha256','context_sha256')}
                    for r in rows]
        receipt_request = sealed({'kind': 'unsigned-group-a-approval-request', 'decision': 'pending',
            'reviewer': None, 'scope': 'renderer_equivalent', 'policy_approved': False,
            'policy_sha256': fingerprint(policy), 'inventory_sha256': inventory['sha256'],
            'baseline': candidate['baseline'], 'members': bindings, 'membership_sha256': fingerprint(bindings),
            'candidate_manifest_sha256': candidate['sha256'], 'calibration_sha256': calibration['sha256'],
            'population_sha256': populations['A']['sha256'], 'remote_writes_authorized': False})
        immutable_save(root/'maintainer-approval-request.json', receipt_request)
        lines = ['# Group A: exact policy and membership approval required', '',
            f"Verified eligible count: {len(rows):,}. No recorded font substitutions or warning/error diagnostics.",
            f"Candidate manifest SHA-256: `{candidate['sha256']}`.",
            f"Policy SHA-256: `{fingerprint(policy)}`. Version: `{policy['version']}` (proposed).",
            f"Exact thresholds: `{policy['thresholds']}`.",
            f"Calibration: {calibration['in_scope_accepted_positive_count']} accepted in-scope positives passed; "
            f"{len(calibration['negative_controls'])} defective controls rejected. This is sampled calibration, not exhaustive visual certification.",
            f"Immutable approval-request SHA-256: `{receipt_request['sha256']}`.",
            'Decision required: explicitly approve this policy SHA and this complete Group A candidate manifest SHA for renderer-equivalent replacement. Record the actual maintainer attribution and decision; this package makes neither.',
            f"Upload proposal: {len(transport['batches'])} technical batches; 300 files / 200 MiB candidate data per batch; 251 MiB measured pack cap. One consolidated draft PR, no direct master write or merge.",
            f"Baseline: `{snapshot['head']}`; tree `{snapshot['tree']}`.",
            f"Group B ({len(populations['B']['members']):,}) is separate. The 50 font changes, 113 visual exceptions and seven exact canaries remain outside both groups.",
            'No prior approval is reused; every proposed replacement is binary-different. Eligible renderer-equivalent files must be uploaded once approved.',
            'All candidate artifacts, receipts, generated parents, font/asset inputs, source/comparison code, native dependencies, validation fingerprints, destination modes and fresh Git/API baseline identities were checked.',
            'No remote writes, uploads, reviewer approvals or publication PR were created. Refresh preflight and verify the exact approval again before staging; reconcile every batch and remotely hash-verify final bytes.', '']
    else:
        lines = [
        '# English first wave: approval pending; staging blocked', '',
        f"Candidate manifest: `{candidate['sha256']}`. Inventory: `{inventory['sha256']}`.",
        f"Policy: `{fingerprint(policy)}`; thresholds: `{policy['thresholds']}`.",
        f"{len(rows):,} exact proposed members; {len(warnings):,} have unresolved diagnostics; "
        f"{len(rows)-len(warnings):,} have no recorded warnings and still require explicit policy approval.",
        'The 9,785-member set cannot be approved as unchanged-layout while these diagnostics remain unresolved.',
        'Resolve the listed diagnostics with bound evidence, or explicitly request a new proposal for the diagnostic-free subset. No membership or thresholds were changed.',
        f"Transport proposal: {len(transport['batches'])} technical batches, one logical group and one future draft PR; measured packs pending.",
        'No reviewer decision was recorded. This request and manifest are not executable publication approvals.',
        'All 50 font changes, 113 visual exceptions and seven exact canaries are excluded. No overlays are included.',
        'Production baseline: `'+snapshot['head']+'`; no remote staging, uploads or PR occurred.',
        'Candidate, receipt, input, font, layout, runtime and remote blob/mode identities were freshly checked for every proposed member.',
        'Before an approved staging run: refresh production again, check exact receipt/manifest and disk/recovery capacity, measure each pack before non-force push, reconcile ambiguous outcomes, verify all remote bytes and complete PR diff. Keep both PRs draft; do not merge.',
        'Existing complete English exception gallery: ../library-sync-20261018/english-exceptions/review.html',
        'Existing representative review gallery: ../library-sync-20261018/english-review/review.html', '']
    (root / 'APPROVAL.md').write_text('\n'.join(lines), encoding='utf-8')
    return request


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--analysis', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--population', choices=['all','A'], default='all')
    args = p.parse_args()
    result = prepare(args.root, args.analysis, args.output, population=args.population)
    print({k: result[k] for k in ('status','requested_members','diagnostic_free_policy_pending','diagnostic_withheld','transport_batches','sha256')})


if __name__ == '__main__':
    main()
