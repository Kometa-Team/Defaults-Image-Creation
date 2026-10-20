"""Exact operator approval binding on the existing resumable Git transport."""

import argparse
from pathlib import Path
import subprocess

from .common import BulkError, fingerprint, sha256
from .library_publication import REVIEWERS, batch_plan, validate_paths
from .library_sources import blob_id, check_seal, load_json, save, sealed


def prepare(inventory, policy, root):
    check_seal(inventory)
    members, withheld = [], []
    for r in inventory['rows']:
        if r['hash_state'] == 'exact_match' and not r.get('rename_from'):
            if r['candidate_sha256'] != r['published_sha256']:
                raise BulkError('false_exact_match', 'Exact SHA-256 is required to skip')
            continue
        if not r.get('technical_valid') or r['difference_class'] == 'blocked':
            withheld.append(r['destination'])
            continue
        path = Path(r['candidate_path'])
        if sha256(path) != r['candidate_sha256'] or blob_id(path) != r['candidate_blob']:
            raise BulkError('candidate_drift', 'Proposed candidate differs from validated output')
        members.append({'destination': r['destination'], 'source': str(path.resolve()),
                        'sha256': r['candidate_sha256'], 'size': path.stat().st_size,
                        'git_blob': r['candidate_blob'], 'previous_sha256': r['published_sha256'],
                        'previous_git_blob': r.get('published_blob') or '0' * 40,
                        'context_sha256': r['context_sha256'], 'difference_class': r['difference_class'],
                        'review_scope': r.get('proposed_review_scope', 'individual')})
        members[-1]['kind'] = r.get('kind', 'poster')
        source_asset = r.get('authoritative_source') or r.get('source_asset')
        if source_asset:
            members[-1]['source_asset'] = source_asset
        if r.get('rename_from'):
            members[-1]['rename_from'] = r['rename_from']
    members.sort(key=lambda m: m['destination'])
    validate_paths(members)
    manifest = sealed({'kind': 'proposed-operator-membership', 'inventory_sha256': inventory['sha256'],
                       'baseline': inventory['baseline'], 'policy_sha256': fingerprint(policy),
                       'members': members, 'withheld': withheld, 'approved': False})
    save(Path(root) / 'candidate-manifest.json', manifest)
    save(Path(root) / 'proposed-policy.json', policy)
    return manifest


def approve(manifest, policy, *, reviewer, policy_hash, manifest_hash, decision_text,
            accept_exceptions=False, allow_additions=(), allow_renames=()):
    """Record an actual explicit maintainer decision; never invoked by generation."""
    check_seal(manifest)
    if (reviewer not in REVIEWERS or policy_hash != fingerprint(policy)
            or manifest_hash != manifest['sha256'] or manifest['policy_sha256'] != policy_hash
            or not decision_text.strip()):
        raise BulkError('approval_binding', 'Actual reviewer, decision and exact policy/membership hashes required')
    if any(m['review_scope'] == 'individual' for m in manifest['members']) and not accept_exceptions:
        raise BulkError('individual_review_required', 'Explicit acceptance of the exact individual exceptions is required')
    additions = {m['destination'] for m in manifest['members'] if m['previous_sha256'] is None and not m.get('rename_from')}
    if additions != set(allow_additions):
        raise BulkError('mapping_approval_required', 'List every approved new destination exactly; no implicit additions')
    renames = {m['rename_from'] + '=>' + m['destination'] for m in manifest['members'] if m.get('rename_from')}
    if renames != set(allow_renames):
        raise BulkError('mapping_approval_required', 'Every exact case-only rename requires explicit approval')
    return sealed({'kind': 'operator-maintainer-decision', 'reviewer': reviewer,
                   'decision': 'approved', 'decision_text': decision_text,
                   'candidate_manifest_sha256': manifest_hash, 'policy_sha256': policy_hash,
                   'baseline': manifest['baseline'], 'accepted_individual_exceptions': accept_exceptions,
                   'allowed_additions': sorted(additions), 'draft_staging_authorized': True,
                   'allowed_renames': sorted(renames),
                   'merge_authorized': False})


def authorize(manifest, policy, receipt):
    check_seal(manifest)
    check_seal(receipt)
    if not manifest.get('members'):
        raise BulkError('empty_publication', 'Everything is synchronized; no upload or PR is necessary')
    if (manifest.get('kind') != 'proposed-operator-membership'
            or receipt.get('kind') != 'operator-maintainer-decision' or receipt.get('decision') != 'approved'
            or receipt.get('reviewer') not in REVIEWERS or not receipt.get('decision_text', '').strip()
            or receipt.get('candidate_manifest_sha256') != manifest['sha256']
            or receipt.get('policy_sha256') != fingerprint(policy)
            or manifest['policy_sha256'] != fingerprint(policy) or receipt['baseline'] != manifest['baseline']
            or not receipt.get('draft_staging_authorized') or receipt.get('merge_authorized')):
        raise BulkError('approval_binding', 'Exact policy, manifest and explicit draft-only maintainer decision required')
    if any(m['review_scope'] == 'individual' for m in manifest['members']) and not receipt.get('accepted_individual_exceptions'):
        raise BulkError('individual_review_required', 'Individual exceptions lack explicit acceptance')
    additions = {m['destination'] for m in manifest['members'] if m['previous_sha256'] is None and not m.get('rename_from')}
    if additions != set(receipt.get('allowed_additions', [])):
        raise BulkError('mapping_approval_required', 'Approved addition membership differs')
    renames = {m['rename_from'] + '=>' + m['destination'] for m in manifest['members'] if m.get('rename_from')}
    if renames != set(receipt.get('allowed_renames', [])):
        raise BulkError('mapping_approval_required', 'Approved case-only rename membership differs')
    for m in manifest['members']:
        if m.get('original_destination'):
            raise BulkError('obsolete_mapping', 'Per-destination basename overrides are unsupported; preserve the authoritative source basename')
        old = m.get('rename_from')
        if old:
            if (m.get('kind') != 'overlay' or not old.endswith('.png') or not m['destination'].endswith('.png')
                    or old == m['destination'] or old.casefold() != m['destination'].casefold()
                    or Path(old).parent != Path(m['destination']).parent
                    or Path(m.get('source_asset', '')).name != Path(m['destination']).name
                    or not m['previous_sha256'] or m['previous_git_blob'] == '0' * 40):
                raise BulkError('rename_scope', 'Only exact approved overlay source-basename case corrections may rename a file')
    members = [dict(m, difference_class='renderer_equivalent') if m['review_scope'] == 'group' else dict(m)
               for m in manifest['members']]
    publication = sealed({'kind': 'approved-library-publication-manifest', 'baseline': manifest['baseline'],
                          'members': members, 'approval_sha256': receipt['sha256'],
                          'candidate_manifest_sha256': manifest['sha256'], 'policy_sha256': fingerprint(policy)})
    plan = batch_plan(publication)
    auth = sealed({'kind': 'approved-operator-draft-staging', 'repository': 'Kometa-Team/Default-Images',
                   'branch': 'migration/python-approved-' + manifest['sha256'][:8],
                   'baseline': manifest['baseline'], 'plan_sha256': plan['sha256'],
                   'publication_manifest_sha256': publication['sha256'], 'candidate_manifest': manifest,
                   'policy': policy, 'approval_receipt': receipt, 'draft_only': True,
                   'remote_writes_authorized': True, 'merge_authorized': False})
    return plan, auth


def gate(plan, auth):
    check_seal(auth)
    wanted_plan, wanted_auth = authorize(auth['candidate_manifest'], auth['policy'], auth['approval_receipt'])
    # Test-only authorizations remain incapable of writing the network remote.
    actual_auth = {k: v for k, v in auth.items() if k not in {'sha256', 'test_only'}}
    if (check_seal(plan) != wanted_plan or sealed(actual_auth) != wanted_auth):
        raise BulkError('approval_binding', 'Transport differs from the exact approved candidate artifacts')
    return [m for b in plan['batches'] for m in b['members']]


def stage(root, *, test_remote=None, fail_at=None):
    from .library_stage import run, RemoteBytes, final_remote_diff
    root = Path(root)
    inventory = check_seal(load_json(root / 'inventory.json'))
    plan = check_seal(load_json(root / 'approved-git-batch-plan.json'))
    auth = check_seal(load_json(root / 'draft-staging-authorization.json'))
    if auth['candidate_manifest']['inventory_sha256'] != inventory['sha256']:
        raise BulkError('stale_inventory', 'Approval inventory differs')
    def guard():
        if inventory.get('generation_report'):
            from .operations import validate_generation
            validate_generation(inventory['generation_report'])
        if inventory.get('runtime'):
            from .library_sources import runtime_identity
            if inventory['runtime'] != runtime_identity():
                raise BulkError('stale_runtime', 'Approved native runtime changed')
        for path, digest in inventory.get('source_hashes', {}).items():
            if sha256(path) != digest:
                raise BulkError('stale_input', 'Approved source changed: ' + path)
    guard()
    if not test_remote:
        from .library_sources import snapshot
        current = snapshot(root)
        if {k: current[k] for k in ('repository', 'branch', 'head', 'tree')} != plan['baseline']:
            raise BulkError('baseline_drift', 'Production changed; preserve review decisions and refresh membership before writes')
    result = run(plan, auth, root / 'transport', test_remote=test_remote, fail_at=fail_at, guard=guard,
                 verify_remote=None if test_remote else RemoteBytes(root / 'actual-remote-verification', plan))
    if result['complete'] and not test_remote:
        final_remote_diff(root, plan, auth, result)
    return result


def draft(root, title):
    from .library_stage import final_remote_diff, git
    root = Path(root)
    plan = check_seal(load_json(root / 'approved-git-batch-plan.json'))
    auth = check_seal(load_json(root / 'draft-staging-authorization.json'))
    report = check_seal(load_json(root / 'transport/transport-report.json'))
    gate(plan, auth)
    if not report['complete']:
        raise BulkError('incomplete_staging', 'Every batch and actual remote hash must be verified first')
    final_remote_diff(root, plan, auth, report)
    import json
    target = auth['repository']
    args = ['gh', 'pr', 'list', '-R', target, '--head', auth['branch'], '--state', 'all',
            '--json', 'number,url,isDraft,state,headRefOid,baseRefName']
    existing = json.loads(subprocess.check_output(args, text=True))
    if not existing:
        body = root / 'pr-body.md'
        body.write_text(f"Stage {sum(len(b['members']) for b in plan['batches'])} exact approved Python outputs.\n\n"
                        f"Candidate manifest: `{auth['candidate_manifest']['sha256']}`.\n"
                        f"Policy: `{fingerprint(auth['policy'])}`.\n"
                        f"All candidate SHA-256 responses and the complete remote tree were verified.\n"
                        f"{len(plan['batches'])} technical batches in one logical draft PR. Separate merge authorization required.\n",
                        encoding='utf-8')
        result = subprocess.run(['gh', 'pr', 'create', '-R', target, '--head', auth['branch'],
                                '--base', 'master', '--draft', '--title', title, '--body-file', str(body)],
                                capture_output=True, text=True)
        existing = json.loads(subprocess.check_output(args, text=True))
        if not existing:
            raise BulkError('draft_creation', result.stderr[-2000:])
    if (len(existing) != 1 or existing[0]['state'] != 'OPEN' or not existing[0]['isDraft']
            or existing[0]['headRefOid'] != report['head'] or existing[0]['baseRefName'] != 'master'):
        raise BulkError('pr_drift', 'Expected exactly one unmerged draft with the verified head')
    pr = existing[0]
    work = root / 'transport/work'
    git(work, 'fetch', '--no-tags', 'origin', f"refs/pull/{pr['number']}/head", timeout=300)
    if git(work, 'rev-parse', 'FETCH_HEAD').decode().strip() != report['head']:
        raise BulkError('pr_drift', 'Fetched PR ref differs from the verified branch')
    from .library_stage import verify_diff
    verify_diff(work, plan['baseline']['head'], report['head'], gate(plan, auth))
    save(root / 'draft-pr.json', sealed(pr))
    return pr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ['prepare', 'approve', 'stage', 'draft', 'verify']:
        p = sub.add_parser(name)
        p.add_argument('--root', type=Path, required=True)
        if name == 'prepare':
            p.add_argument('--inventory', type=Path, required=True)
            p.add_argument('--policy', type=Path, required=True)
        elif name == 'approve':
            p.add_argument('--reviewer', required=True)
            p.add_argument('--policy-sha256', required=True)
            p.add_argument('--manifest-sha256', required=True)
            p.add_argument('--decision-text-file', type=Path, required=True)
            p.add_argument('--accept-exceptions', action='store_true')
            p.add_argument('--allow-addition', action='append', default=[])
            p.add_argument('--allow-rename', action='append', default=[])
        elif name == 'draft':
            p.add_argument('--title', required=True)
    args = parser.parse_args()
    root = args.root
    try:
        if args.command == 'prepare':
            inventory = check_seal(load_json(args.inventory))
            policy = load_json(args.policy)
            result = prepare(inventory, policy, root)
            save(root / 'inventory.json', inventory)
        elif args.command == 'approve':
            manifest = check_seal(load_json(root / 'candidate-manifest.json'))
            policy = load_json(root / 'proposed-policy.json')
            receipt = approve(manifest, policy, reviewer=args.reviewer, policy_hash=args.policy_sha256,
                              manifest_hash=args.manifest_sha256,
                              decision_text=args.decision_text_file.read_text(encoding='utf-8'),
                              accept_exceptions=args.accept_exceptions, allow_additions=args.allow_addition,
                              allow_renames=args.allow_rename)
            plan, auth = authorize(manifest, policy, receipt)
            save(root / 'approval-receipt.json', receipt)
            save(root / 'approved-git-batch-plan.json', plan)
            save(root / 'draft-staging-authorization.json', auth)
            result = {'approved': len(manifest['members']), 'batches': len(plan['batches']), 'remote_writes': 0}
        elif args.command == 'stage':
            result = stage(root)
        elif args.command == 'draft':
            result = draft(root, args.title)
        else:
            from .library_stage import final_remote_diff, RemoteBytes
            plan = check_seal(load_json(root / 'approved-git-batch-plan.json'))
            auth = check_seal(load_json(root / 'draft-staging-authorization.json'))
            report = check_seal(load_json(root / 'transport/transport-report.json'))
            RemoteBytes(root / 'fresh-remote-verification', plan)(report['head'], gate(plan, auth))
            result = final_remote_diff(root, plan, auth, report)
        print({k: v for k, v in result.items() if k != 'members'}, flush=True)
    except BulkError as error:
        parser.exit(2, error.code + ': ' + str(error) + '\n')


if __name__ == '__main__':
    main()
