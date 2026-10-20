"""Python operator workflow; generation, review and publication are separate actions."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess

from .common import BulkError, canonical, confined, fingerprint, sha256
from .config import Config, ROOT
from .library_sources import (blob_id, check_seal, load_json, published_file,
                              runtime_identity, save, sealed, snapshot)


def native_guard(config):
    """Do not reuse a worker cache after a native encoder/font library change."""
    path = config.cache_dir / 'operator-runtime.json'
    current = sealed({'runtime': runtime_identity()})
    if path.exists() and check_seal(load_json(path)) != current:
        raise BulkError('native_runtime_changed',
                        'Native dependencies changed; use a new cache/output/work root and review resulting bytes')
    if not path.exists():
        save(path, current)
    return current


def verified_receipts(result, config):
    """Recheck the existing worker's artifact, input, receipt and finalized state guards."""
    from .state import Store
    from .workers import PersistentWorkers, tasks_from_manifest, _check_inputs
    store = Store(config.cache_dir / 'state.sqlite')
    pool = PersistentWorkers(store, config)
    bindings = {}
    # As in PersistentWorkers.run, keep WAL open across the short reads. Closing
    # the last connection per receipt repeats expensive Windows checkpoints.
    with store.connection() as anchor:
        anchor.execute('SELECT count(*) FROM sqlite_master').fetchone()
        for stage in result['stages']:
            for task in tasks_from_manifest(stage['manifest']):
                state_id = pool._state_id(task)
                receipt = pool._cached(task, state_id)
                state = store.job(state_id)
                if (not receipt or not state or state['status'] != 'verified'
                        or state['receipt'] != canonical(receipt).decode()):
                    raise BulkError('stale_receipt', 'Worker receipt, artifact or finalized state changed')
                _check_inputs(task.payload, config)
                bindings[task.id] = receipt['receipt_sha256']
                if len(bindings) % 1000 == 0:
                    print('[RECEIPTS]', len(bindings), 'verified', flush=True)
    return bindings


def adopt(inventory_path, config, kind, profile_path):
    """Adopt the verified migration cache through a supported command, without rendering."""
    from .library_sources import reference
    inventory = check_seal(load_json(inventory_path))
    if inventory.get('runtime') != runtime_identity():
        raise BulkError('stale_runtime', 'Migration cache native identity differs; do not adopt')
    data = reference(kind)
    expected = {r['job']['remote_relative']: r['receipt']['sha256'] for r in data['rows']
                if r['job']['remote_relative'] is not None}
    if expected != {r['destination']: r['candidate_sha256'] for r in inventory['rows']}:
        raise BulkError('reference_drift', 'Adoption inventory differs from the complete validated ledger')
    manifest = dict(data['manifest_header'], jobs=[r['job'] for r in data['rows']])
    # The additive approved Action & Adventure public-path correction preserves
    # the original ledger/header. Bind that corrected metadata in this new plan.
    manifest['sha256'] = fingerprint({k: v for k, v in manifest.items() if k != 'sha256'})
    bindings = verified_receipts({'stages': [{'manifest': manifest}]}, config)
    native_guard(config)
    profile = sealed({'kind': 'operator-cache-profile', 'runtime': runtime_identity(),
                      'adopted_inventory_sha256': inventory['sha256'],
                      'verified_worker_receipts': len(bindings), 'artwork_regenerated': 0,
                      'config': {k: str(getattr(config, k)) for k in
                                 ('asset_dir', 'cache_dir', 'workspace_dir', 'output_dir', 'translation_dir')}})
    save(profile_path, profile)
    return profile


def generate(args, config):
    from .workers import WorkerLimits
    runtime = native_guard(config)
    if args.command == 'overlays':
        if getattr(args, 'cache_only', False):
            if args.definitions:
                from .overlay_definitions import plan
                manifest = plan(args.definitions, config)
            else:
                from .overlays import plan
                manifest = plan(config, groups=args.group, sources=args.source,
                                sizes=args.size or ['standard', 'bigger'])
            verified_receipts({'stages': [{'manifest': manifest}]}, config)
        if args.definitions:
            if args.group or args.source or args.size:
                raise BulkError('invalid_selection', 'Use explicit definitions or catalog selectors separately')
            from .overlay_definitions import generate as render
            result = render(args.definitions, config, WorkerLimits(workers=args.workers))
            definition_paths = list(args.definitions)
        else:
            from .overlays import generate as render
            result = render(config, groups=args.group, sources=args.source,
                            sizes=args.size or ['standard', 'bigger'], limits=WorkerLimits(workers=args.workers))
            definition_paths = [ROOT / 'bulk/catalog/overlays-v1.json']
    else:
        from .catalog import load_catalog, CATALOG
        from .definitions import load_definitions
        from .d_cli import source
        from .generation import generate as render
        from .generators import GENERATORS
        definitions = (load_definitions(args.definitions, profiles_path=args.profiles) if args.definitions
                       else load_catalog(args.category, posters=args.poster))
        registry, translations = source(config, languages=['en'], definitions=definitions)
        posters = args.poster or ([d.id for d in definitions] if args.definitions and not args.category else [])
        result = render(definitions, translations, config=config, registry=registry,
                        generators=GENERATORS, categories=args.category, posters=posters,
                        languages=['en'], limits=WorkerLimits(workers=args.workers),
                        cache_only=getattr(args, 'cache_only', False))
        definition_paths = (list(args.definitions) + ([args.profiles] if args.profiles else [])
                            if args.definitions else list(CATALOG.glob('*.yml')) + [CATALOG / 'index-v1.json'])
    definition_paths += list(config.translation_dir.glob('en.yml'))
    definition_paths += [p for p in (ROOT / 'create_default_posters.ps1', ROOT / 'bulk/catalog/asset-case-migrations-v1.json') if p.exists()]
    inputs = {str(Path(p).resolve()): sha256(p) for p in definition_paths}
    for stage in result['stages']:
        for job in stage['manifest']['jobs']:
            for item in job['inputs']:
                path = confined(config.asset_dir, item['path'], must_exist=True)
                if sha256(path) != item['sha256']:
                    raise BulkError('changed_input', 'Input changed during generation')
                inputs[str(path)] = item['sha256']
    report = sealed({'kind': 'operator-generation', 'runtime': runtime,
                     'worker_receipts': verified_receipts(result, config),
                     'config': {k: str(getattr(config, k)) for k in
                                ('asset_dir', 'cache_dir', 'workspace_dir', 'output_dir', 'translation_dir')},
                     'definition_and_asset_hashes': inputs, 'result': result,
                     'remote_writes': 0})
    save(args.report, report)
    return {'status': result['status'], 'report_sha256': report['sha256'],
            'executed': sum(s['execution']['metrics']['executed'] for s in result['stages']),
            'cache_hits': sum(s['execution']['metrics']['cache_hits'] for s in result['stages'])}


def validate_generation(report):
    check_seal(report)
    from .planner import renderer_identity, validate_manifest
    from .overlays import identity
    if report['runtime']['runtime'] != runtime_identity():
        raise BulkError('stale_runtime', 'Generation native runtime changed')
    for path, digest in report['definition_and_asset_hashes'].items():
        if sha256(path) != digest:
            raise BulkError('stale_input', 'Generation source or asset changed: ' + path)
    for stage in report['result']['stages']:
        manifest = validate_manifest(stage['manifest'])
        expected = identity() if manifest['jobs'][0]['kind'] == 'overlay' else renderer_identity()
        if manifest['renderer'] != expected:
            raise BulkError('stale_renderer', 'Generation renderer changed')
    config = Config(**{k: Path(v) for k, v in report['config'].items()})
    if verified_receipts(report['result'], config) != report.get('worker_receipts'):
        raise BulkError('stale_receipt', 'Generation receipt membership changed')


def preview(report, root, state):
    """Compare actual bytes; never substitute visual equivalence for exact sync."""
    from .library_visual import PROPOSED_POLICY, compare_images, evaluate
    from .library_sync import gallery
    validate_generation(report)
    check_seal(state)
    config = Config(**{k: Path(v) for k, v in report['config'].items()})
    entries = {e['path']: e for e in state['entries']}
    from .case_audit import collisions
    if collisions(entries):
        raise BulkError('case_collision', 'Production contains Git paths differing only by case')
    folded = {p.casefold(): p for p in entries}
    rows = {}
    preflight = {v['id']: v for v in report['result']['preflight']['variants']}
    for stage in report['result']['stages']:
        for job in stage['manifest']['jobs']:
            destination = job['remote_relative']
            if destination is None:
                continue
            candidate = confined(config.output_dir, job['local_relative'], must_exist=True)
            digest = sha256(candidate)
            if stage['execution']['jobs'][job['id']]['sha256'] != digest:
                raise BulkError('candidate_drift', 'Output changed after verified generation')
            variant = preflight[job['id']]
            row = {'id': job['id'], 'destination': destination, 'kind': job['kind'],
                   'source_asset': job['parameters'].get('input'),
                   'candidate_path': str(candidate), 'candidate_sha256': digest,
                   'candidate_blob': blob_id(candidate), 'candidate_bytes': candidate.stat().st_size,
                   'published_sha256': None, 'technical_valid': True, 'blockers': [],
                   'category': destination.split('/')[0], 'font': job['parameters'].get('font', 'none'),
                   'layout_risks': [d['code'] for d in variant['diagnostics'] if d['severity'] == 'warning'],
                   'difference_class': 'missing_published', 'hash_state': 'missing_published',
                   'context_sha256': fingerprint({'job': job, 'validation': variant['validation_fingerprint'],
                                                  'runtime': report['runtime'], 'baseline': state['head']})}
            actual = destination if destination in entries else folded.get(destination.casefold())
            if actual and actual != destination:
                from pathlib import PurePosixPath
                old, new = PurePosixPath(actual), PurePosixPath(destination)
                if (job['kind'] == 'overlay' and old.parent == new.parent
                        and new.name == PurePosixPath(row['source_asset']).name):
                    row['rename_from'] = actual
                else:
                    row.update(difference_class='blocked', hash_state='case_conflict', technical_valid=False,
                               blockers=[{'code': 'case_conflict', 'actual': actual}])
            if actual and row['technical_valid']:
                published, provenance = published_file(root, state, entries[actual])
                row.update(published_path=str(published), published_sha256=sha256(published),
                           published_blob=entries[actual]['sha'], published_provenance=provenance)
                if digest == row['published_sha256']:
                    row.update(difference_class='filename_case_only' if row.get('rename_from') else 'exact_match',
                               hash_state='exact_match')
                else:
                    metrics = compare_images(candidate, published, job['parameters'])
                    row.update(metrics=metrics, tolerance=evaluate(metrics, PROPOSED_POLICY),
                               difference_class='unexpected_difference', hash_state='unequal')
            rows[destination] = row
    for variant in preflight.values():
        destination = variant.get('remote_relative')
        if (variant.get('selected') and destination and destination not in rows
                and not variant.get('private')):
            rows[destination] = {'id': variant['id'], 'destination': destination,
                                 'kind': variant.get('kind', 'poster'), 'technical_valid': False,
                                 'difference_class': 'blocked', 'hash_state': 'not_generated',
                                 'candidate_sha256': None, 'published_sha256': None,
                                 'blockers': variant.get('diagnostics', []),
                                 'context_sha256': variant['validation_fingerprint']}
    inventory = sealed({'kind': 'operator-preview', 'generation_report_sha256': report['sha256'],
                        'generation_report': report, 'policy_sha256': fingerprint(PROPOSED_POLICY),
                        'baseline': {k: state[k] for k in ('repository', 'branch', 'head', 'tree')},
                        'rows': sorted(rows.values(), key=lambda r: r['destination']),
                        'publication_authorized': False})
    root = Path(root)
    save(root / 'inventory.json', inventory)
    review = root / 'review'
    review.mkdir(parents=True, exist_ok=True)
    gallery(review, list(rows.values()), [{'lane': 'operator', 'category': 'explicit selection',
            'font': 'see per-image evidence', 'membership_sha256': fingerprint(list(rows)),
            'samples': [{'destination': p, 'reasons': [r['difference_class']]} for p, r in rows.items()]}])
    return inventory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('cache-dir', 'workspace-dir', 'output-dir', 'asset-dir', 'translation-dir'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--profile', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('generate', 'overlays'):
        p = commands.add_parser(name)
        p.add_argument('--workers', type=int, choices=[1, 2, 4], default=2)
        p.add_argument('--report', type=Path, required=True)
        p.add_argument('--cache-only', action='store_true')
        if name == 'generate':
            p.add_argument('--category', action='append', default=[])
            p.add_argument('--poster', action='append', default=[])
            p.add_argument('--definitions', type=Path, nargs='+')
            p.add_argument('--profiles', type=Path)
        else:
            p.add_argument('--definitions', type=Path, nargs='+')
            p.add_argument('--group', action='append', default=[])
            p.add_argument('--source', action='append', default=[])
            p.add_argument('--size', action='append', choices=['standard', 'bigger'])
    p = commands.add_parser('preview')
    p.add_argument('--generation', type=Path, required=True)
    p.add_argument('--root', type=Path, required=True)
    p = commands.add_parser('verify-production')
    p.add_argument('--inventory', type=Path, required=True)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--kind', choices=['english', 'overlays'], default='english')
    p = commands.add_parser('adopt')
    p.add_argument('--kind', choices=['english', 'overlays'], required=True)
    p.add_argument('--inventory', type=Path, required=True)
    p.add_argument('--save-profile', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify-production':
            from .production_verify import verify
            result = verify(args.inventory, args.root, kind=args.kind)
            result = {k: v for k, v in result.items() if k != 'response_receipts'}
        elif args.command == 'preview':
            result = preview(check_seal(load_json(args.generation)), args.root, snapshot(args.root))
            result = {'inventory_sha256': result['sha256'], 'expected': len(result['rows']),
                      'exact_matches': sum(r['hash_state'] == 'exact_match' for r in result['rows']),
                      'review_required': sum(r['hash_state'] != 'exact_match' for r in result['rows'])}
        else:
            explicit = {k: getattr(args, k) for k in
                        ('cache_dir', 'workspace_dir', 'output_dir', 'asset_dir', 'translation_dir')}
            if args.profile:
                profile = check_seal(load_json(args.profile))
                if profile.get('kind') != 'operator-cache-profile' or profile.get('runtime') != runtime_identity():
                    raise BulkError('stale_runtime', 'Adopted profile native runtime differs')
                values = {k: Path(v) for k, v in profile['config'].items()}
                values.update({k: v for k, v in explicit.items() if v is not None})
                config = Config.load(**values)
            else:
                config = Config.load(**explicit)
            result = (adopt(args.inventory, config, args.kind, args.save_profile)
                      if args.command == 'adopt' else generate(args, config))
        print(result, flush=True)
    except BulkError as error:
        parser.exit(2, error.code + ': ' + str(error) + '\n')


if __name__ == '__main__':
    main()
