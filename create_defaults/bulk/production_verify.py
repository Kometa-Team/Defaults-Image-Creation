"""Read-only, resumable verification of approved output against production bytes."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess

from .common import BulkError, sha256
from .library_sources import (blob_id, check_seal, load_json, reference, save,
                              sealed, snapshot)
from .library_stage import RemoteBytes


def prepare(inventory, state, *, verify_local=True):
    check_seal(inventory)
    check_seal(state)
    entries = {e['path']: e for e in state['entries']}
    members, discrepancies = [], []
    for row in inventory['rows']:
        entry = entries.get(row['destination'])
        expected = (row['candidate_blob'], row['candidate_bytes'], '100644', 'blob')
        if entry is None:
            discrepancies.append({'destination': row['destination'], 'reason': 'missing'})
            continue
        actual = tuple(entry[k] for k in ('sha', 'size', 'mode', 'type'))
        if actual != expected:
            discrepancies.append({'destination': row['destination'], 'reason': 'production_identity',
                                  'expected': expected, 'actual': actual})
            continue
        if verify_local:
            path = Path(row['candidate_path'])
            if (sha256(path) != row['candidate_sha256'] or blob_id(path) != row['candidate_blob']
                    or path.stat().st_size != row['candidate_bytes']):
                raise BulkError('candidate_hash', 'Validated local output changed: ' + row['destination'])
        members.append({'destination': row['destination'], 'git_blob': row['candidate_blob'],
                        'size': row['candidate_bytes'], 'sha256': row['candidate_sha256']})
    if len({m['destination'] for m in members}) != len(members):
        raise BulkError('duplicate_destination', 'Verification membership is not unique')
    return sealed({'kind': 'read-only-production-verification-plan',
                   'inventory_sha256': inventory['sha256'], 'baseline': {
                       k: state[k] for k in ('repository', 'branch', 'head', 'tree')},
                   'members': members, 'discrepancies': discrepancies})


def verify(inventory_path, root, *, kind='english'):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    state = snapshot(root)
    inventory = check_seal(load_json(inventory_path))
    data = reference(kind)
    expected = {r['job']['remote_relative']: r['receipt']['sha256'] for r in data['rows']
                if r['job']['remote_relative'] is not None}
    if expected != {r['destination']: r['candidate_sha256'] for r in inventory['rows']}:
        raise BulkError('reference_drift', 'Inventory differs from the validated complete output ledger')
    plan = prepare(inventory, state)
    save(root / 'verification-plan.json', plan)
    RemoteBytes(root / 'actual-production-responses', plan)(state['head'], plan['members'])
    receipts = [check_seal(load_json(p)) for p in (root / 'actual-production-responses').glob('*.json')]
    current_receipts = [r for r in receipts if r['plan_sha256'] == plan['sha256']]
    if {r['destination'] for r in current_receipts} != {m['destination'] for m in plan['members']}:
        raise BulkError('incomplete_verification', 'Actual response receipts do not cover the plan')
    head = subprocess.check_output(['gh', 'api', 'repos/' + state['repository'] +
                                    '/git/ref/heads/master', '--jq', '.object.sha'], text=True).strip()
    if head != state['head']:
        raise BulkError('baseline_drift', 'Production moved during verification; retain pinned evidence and refresh')
    result = sealed({'kind': 'final-' + kind + '-production-verification',
                     'checked_utc': datetime.now(timezone.utc).isoformat(),
                     'baseline': plan['baseline'], 'inventory_sha256': inventory['sha256'],
                     'plan_sha256': plan['sha256'], 'expected': len(expected),
                     'exact_sha256_matches': len(current_receipts),
                     'missing': sum(d['reason'] == 'missing' for d in plan['discrepancies']),
                     'remaining_candidates': len(plan['discrepancies']),
                     'discrepancies': plan['discrepancies'], 'production_stable': True,
                     'artwork_regenerated': 0, 'remote_writes': 0,
                     'response_receipts': {r['destination']: r['sha256'] for r in current_receipts}})
    save(root / 'FINAL-PRODUCTION-VERIFICATION.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--kind', choices=['english', 'overlays'], default='english')
    args = parser.parse_args()
    result = verify(args.inventory, args.root, kind=args.kind)
    print({k: v for k, v in result.items() if k != 'response_receipts'}, flush=True)
    return int(bool(result['discrepancies']))


if __name__ == '__main__':
    raise SystemExit(main())
