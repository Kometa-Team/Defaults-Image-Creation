"""Explicit new-overlay definitions using the existing Pillow transform/workers."""

from pathlib import Path

from .common import BulkError, confined, fingerprint, load_yaml, relative_path, sha256
from .overlays import identity, TRANSFORM
from .planner import validate_manifest


def plan(paths, config):
    jobs = []
    renderer = identity()
    for file in paths:
        document = load_yaml(file)
        if (set(document) != {'schema_version', 'overlays'} or document['schema_version'] != 1
                or not isinstance(document['overlays'], list) or not 0 < len(document['overlays']) <= 100):
            raise BulkError('overlay_definition', 'Expected schema_version 1 and 1..100 explicit overlays')
        for item in document['overlays']:
            if (set(item) != {'source', 'destination', 'box', 'trim'} or type(item['trim']) is not bool
                    or item['box'] not in ([285, 85], [440, 100])):
                raise BulkError('overlay_definition', 'Explicit source, destination, standard/bigger box and boolean trim required')
            source = confined(config.asset_dir, item['source'], must_exist=True)
            destination = relative_path(item['destination'])
            if '/overlays/' not in destination or not destination.endswith('.png'):
                raise BulkError('overlay_destination', 'Canonical public overlay PNG destination required')
            parameters = {'input': item['source'], 'box': item['box'], 'trim': item['trim'],
                          'colorspace': 'sRGB', 'strip_metadata': True, 'format': 'PNG', 'resampling': 'Pillow-LANCZOS'}
            job = {'id': 'overlay.' + fingerprint(destination)[:24], 'kind': 'overlay',
                   'poster_id': 'overlay.custom.' + fingerprint(destination)[:16], 'language': 'en',
                   'variant': 'standard' if item['box'] == [285, 85] else 'bigger',
                   'definition_fingerprint': fingerprint(item), 'generator_origin': None,
                   'source': {'kind': 'authored', 'path': Path(file).name, 'line': 1, 'row_sha256': fingerprint(item)},
                   'raw_parameters': parameters, 'parameters': parameters,
                   'inputs': [{'role': 'overlay_source', 'path': item['source'], 'sha256': sha256(source)}],
                   'dependencies': [], 'translation': {'mode': 'none', 'trace': [], 'fingerprint': fingerprint({'mode': 'none'})},
                   'language_behavior': {'language': 'shared', 'direction': 'auto'},
                   'local_relative': destination, 'remote_relative': destination,
                   'layout_evidence': {'transform': TRANSFORM},
                   'color_assignment': {'id': 'overlay.none', 'origin': 'template', 'parent': None,
                                        'relationship': None, 'exception': None},
                   'status': 'planned', 'render_ready': True}
            job['render_fingerprint'] = fingerprint({k: job[k] for k in
                 ('kind', 'parameters', 'inputs', 'dependencies', 'language_behavior')} | {'renderer': renderer})
            jobs.append(job)
    manifest = {'schema_version': 1, 'kind': 'bulk-plan', 'renderer': renderer, 'jobs': jobs,
                'not_applicable': [], 'selection': {'categories': ['Overlays'], 'posters': [], 'languages': ['en']},
                'scope': 'Explicit new overlay definitions; no mapping or publication approval'}
    manifest['sha256'] = fingerprint(manifest)
    return validate_manifest(manifest)


def generate(paths, config, limits):
    from .preflight import POLICY, export_report
    from .workers import PersistentWorkers, tasks_from_manifest
    from .state import Store
    manifest = plan(paths, config)
    variants = []
    for job in manifest['jobs']:
        variants.append({'id': job['id'], 'poster_id': job['poster_id'], 'kind': 'overlay', 'language': 'en',
                         'category': 'Overlays', 'selected': True, 'private': False, 'status': 'ready_with_warning',
                         'definition_fingerprint': job['definition_fingerprint'], 'caption': None,
                         'validation_fingerprint': fingerprint({'job': job, 'policy': POLICY}),
                         'local_relative': job['local_relative'], 'remote_relative': job['remote_relative'],
                         'dependencies': [], 'translation_dependencies': [],
                         'diagnostics': [{'code': 'overlay_transform_review', 'severity': 'warning',
                                          'message': 'New overlay requires exact visual and destination approval'}],
                         'risk': {'requires_individual': True, 'level': 'high'}})
    report = {'schema_version': 1, 'kind': 'overlay-preflight', 'policy': POLICY, 'execution_policy': 'review',
              'registry_sha256': fingerprint(manifest['selection']), 'translation_hashes': {},
              'renderer': manifest['renderer'], 'languages': [], 'selection': manifest['selection'],
              'variants': variants, 'coverage': {'ready_with_warning': len(variants)},
              'missing_translations': [], 'status': 'complete'}
    report['sha256'] = fingerprint(report)
    export_report(report, config.cache_dir / 'preflight' / report['sha256'])
    with PersistentWorkers(Store(config.cache_dir / 'state.sqlite'), config, limits) as pool:
        execution = pool.run(tasks_from_manifest(manifest))
    success = all(r['status'] in {'rendered', 'cache_reuse', 'dedup_reuse'} for r in execution['jobs'].values())
    if success:
        pool.workspaces.cleanup(**pool.workspace, retain_seconds=0)
    return {'status': 'verified' if success else 'incomplete', 'manifest': manifest, 'preflight': report,
            'stages': [{'depth': 0, 'manifest': manifest, 'execution': execution}]}
