"""Sealed overlay review proposal; does not approve mappings or perform writes."""

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import csv
import hashlib
import html
import json
from pathlib import Path
import shutil

from PIL import Image, ImageDraw

from .common import BulkError, fingerprint, sha256
from .config import ROOT
from .library_sources import (blob_id, check_seal, load_json, published_file, reference,
                              runtime_identity, save, sealed)
from .library_publication import retained_overlay_decisions
from .library_visual import metadata
from .overlay_review import measure, screen, edge_screen, policy, negative_controls
from .operator_publication import prepare


def gallery(root, rows, *, title):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    cards = []
    for row in rows:
        key = fingerprint(row['destination'])[:20]
        pictures = []
        for label, field in [('Published', 'published_path'), ('Python', 'candidate_path')]:
            if not row.get(field):
                pictures.append('<p>Published destination absent; addition requires approval.</p>')
                continue
            with Image.open(row[field]) as source:
                image = source.convert('RGBA')
            canvas = Image.new('RGB', (480, 260), '#ddd')
            draw = ImageDraw.Draw(canvas)
            draw.text((8, 5), label + ' ' + str(image.size), fill='black')
            for background, top in [(0, 30), (255, 145)]:
                backing = Image.new('RGBA', (460, 105), (background, background, background, 255))
                backing.alpha_composite(image, (0, 0))
                canvas.paste(backing.convert('RGB'), (10, top))
            relative = 'previews/' + key + '-' + label + '.png'
            target = root / relative
            target.parent.mkdir(exist_ok=True)
            canvas.save(target)
            pictures.append('<figure><img loading="lazy" src="' + relative + '" alt="' + label + '"></figure>')
        evidence = {k: row.get(k) for k in ('candidate_sha256', 'published_sha256', 'approval_lane',
                    'review_family', 'additional_screen', 'edge_screen', 'alpha_geometry', 'rename_from',
                    'authoritative_source', 'candidate_image', 'source_image', 'required_publication_action')}
        cards.append('<article><h2>' + html.escape(row['destination']) + '</h2><p>' + html.escape(row['approval_lane'] + ' / ' + row['review_family']) +
                     '</p><div class="pair">' + ''.join(pictures) + '</div><details><summary>Measurements and exact identities</summary><pre>' +
                     html.escape(json.dumps(evidence, indent=2)) + '</pre></details></article>')
    (root / 'review.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<title>' + html.escape(title) + '</title><style>body{font:16px system-ui;background:#eee;margin:20px}'
        'article{background:white;padding:12px;margin:12px 0}h2,pre{overflow-wrap:anywhere}pre{white-space:pre-wrap}'
        '.pair{display:flex;flex-wrap:wrap;gap:10px}figure{margin:0}img{max-width:100%;height:auto}</style><h1>' +
        html.escape(title) + '</h1><p>Proposal only. Pixels remain at their original coordinates on black and white backgrounds. '
        'No visual, mapping or publication approval is inferred.</p>' + ''.join(cards), encoding='utf-8')


def build(inventory_path, measurements_path, root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    original = check_seal(load_json(inventory_path))
    analysis = check_seal(load_json(measurements_path))
    measured = {r['destination']: r for r in analysis['rows']}
    state = check_seal(load_json(Path(inventory_path).parent / 'production-snapshot.json'))
    if original['baseline']['head'] != state['head']:
        raise BulkError('baseline_drift', 'Inventory and production snapshot differ')
    data = reference('overlays')
    previous = check_seal(load_json(ROOT.parent / 'config/library-sync-20261018/overlays-reconciled-inventory.json'))
    if previous.get('runtime') != runtime_identity() or original.get('runtime') != runtime_identity():
        raise BulkError('stale_runtime', 'Native overlay encoding/color runtime differs from the preserved comparisons')
    jobs = {r['job']['id']: r['job'] for r in data['rows']}
    base = load_json(Path(inventory_path).parent / 'proposed-tolerance-policy.json')
    proposed = policy(base)
    if analysis['policy_sha256'] != fingerprint(proposed):
        raise BulkError('stale_measurements', 'Overlay policy or measurement implementation changed')
    profiles = load_json(ROOT.parent / 'config/library-sync-20261018/overlay-source-profiles.json')
    from .asset_cases import canonical as canonical_asset, LEDGER
    profile_by_path = {canonical_asset(p['path']): p for p in profiles['sources']}
    rows = deepcopy(original['rows'])
    inventory = dict(original)
    inventory.pop('sha256')
    inventory['rows'] = rows
    retained = retained_overlay_decisions(inventory)
    groups = defaultdict(list)
    sources, source_metadata = {}, {}
    for row in rows:
        job = jobs[row['id']]
        source = job['parameters']['input']
        profile = profile_by_path[source]
        if sha256(ROOT / source) != profile['sha256']:
            raise BulkError('source_drift', 'Overlay source changed: ' + source)
        sources[str((ROOT / source).resolve())] = profile['sha256']
        if source not in source_metadata:
            with Image.open(ROOT / source) as image:
                icc = image.info.get('icc_profile')
                source_metadata[source] = {'dimensions': list(image.size), 'mode': image.mode, 'format': image.format,
                    'icc_profile': bool(icc), 'icc_sha256': hashlib.sha256(icc).hexdigest() if icc else None,
                    'palette_transparency': 'transparency' in image.info}
        row['source_image'] = source_metadata[source]
        with Image.open(row['candidate_path']) as image:
            row['candidate_image'] = metadata(image)
        cached = measured.get((row.get('identity_correction') or {}).get('old_destination', row['destination']))
        if row.get('published_path'):
            if (cached and cached.get('candidate_sha256') == row['candidate_sha256']
                    and cached.get('published_sha256') == row['published_sha256']
                    and 'interior_rgb_mae' in cached.get('measurements', {})):
                extra = cached['measurements']
            else:
                extra = measure(row['candidate_path'], row['published_path'])
            row['alpha_geometry'] = extra
            row['additional_screen'] = screen(row, extra, proposed)
            row['edge_screen'] = edge_screen(row, extra, proposed)
        if row['difference_class'] == 'blocked' or not row.get('technical_valid'):
            lane = 'blocked'
        elif row['hash_state'] == 'exact_match' and not row.get('rename_from'):
            lane = 'exact_match'
        elif row['hash_state'] == 'exact_match' and row.get('rename_from'):
            lane = 'filename_case_only'
        elif row['destination'] in retained:
            lane = 'retained_individual_approval'
        elif row['hash_state'] == 'missing_published':
            lane = 'new_destination_decision'
        elif row.get('additional_screen', {}).get('screen_pass'):
            lane = 'strict_group_proposal'
        elif row.get('edge_screen', {}).get('screen_pass'):
            lane = 'edge_resampling_group_proposal'
        else:
            lane = 'individual_exception'
        row['approval_lane'] = lane
        row['proposed_review_scope'] = ('group' if lane.endswith('group_proposal') else
                                         'retained_individual' if lane == 'retained_individual_approval' else 'individual')
        failure = row.get('edge_screen', {}).get('failures', [])
        family = next((f for f in ['dimensions', 'alpha_16_bounds', 'unmatched_support_radius_1',
            'alpha_mass_relative_change', 'outside_edge_band_alpha_maximum', 'interior_rgb_mae'] if f in failure),
            'composite_visual_limit' if failure else 'within_measured_bounds')
        row['review_family'] = family
        key = (lane, profile['mode'], source_metadata[source]['icc_sha256'] or 'none', str(job['parameters']['trim']),
               str(job['parameters']['box']), family)
        groups[key].append(row)
        # Seal exact copied artifacts into the review package, without rendering.
        for field, sub in [('candidate_path', 'candidate'), ('published_path', 'published')]:
            if row.get(field):
                target = root / 'artifacts' / sub / row['destination']
                target.parent.mkdir(parents=True, exist_ok=True)
                expected = row['candidate_sha256'] if sub == 'candidate' else row['published_sha256']
                if sha256(row[field]) != expected:
                    raise BulkError('artifact_drift', 'Compared artifact changed')
                if not target.exists():
                    shutil.copyfile(row[field], target)
                if sha256(target) != expected:
                    raise BulkError('artifact_drift', 'Sealed copied artifact changed')
                row[field] = str(target.resolve())
    sources.update({str((ROOT / p).resolve()): sha256(ROOT / p) for p in
                    ('bulk/catalog/overlays-v1.json', 'bulk/catalog/asset-case-migrations-v1.json',
                     'create_default_posters.ps1', 'create_poster.py', 'poster_text.py', 'bulk/overlays.py',
                     'bulk/asset_cases.py', 'bulk/common.py', 'bulk/planner.py', 'bulk/workers.py',
                     'bulk/library_visual.py', 'bulk/overlay_review.py', 'bulk/library_sources.py',
                     'bulk/library_sync.py', 'bulk/library_stage.py', 'bulk/operator_publication.py',
                     'bulk/overlay_package.py')})
    for row in rows:
        row['analysis_context_sha256'] = row['context_sha256']
        row['context_sha256'] = fingerprint({'analysis_context': row['analysis_context_sha256'],
            'policy_sha256': fingerprint(proposed), 'baseline': original['baseline'],
            'candidate_sha256': row['candidate_sha256'], 'published_sha256': row['published_sha256']})
    inventory.update(kind='overlays', runtime=runtime_identity(), source_hashes=sources,
                     counts=dict(Counter(r['difference_class'] for r in rows)),
                     hash_states=dict(Counter(r['hash_state'] for r in rows)),
                     original_current_inventory_sha256=original['sha256'],
                     proposed_case_renames=[{'from': r['rename_from'], 'to': r['destination'], 'approval_required': True}
                                            for r in rows if r.get('rename_from')],
                     policy_sha256=fingerprint(proposed), publication_authorized=False)
    inventory = sealed(inventory)
    save(root / 'inventory.json', inventory)
    save(root / 'production-snapshot.json', state)
    manifest = prepare(inventory, proposed, root)
    save(root / 'retained-individual-approvals.json', sealed({'count': len(retained), 'decisions': retained}))
    focused, group_records = {}, []
    for key, population in sorted(groups.items()):
        selected = {}
        for metric in ('rgb_mae', 'alpha_mae', 'edge_mae'):
            worst = max(population, key=lambda r: r.get('metrics', {}).get(metric, -1))
            selected[worst['destination']] = worst
        for metric in ('alpha_mass_relative_change', 'outside_edge_band_alpha_maximum', 'interior_rgb_mae'):
            worst = max(population, key=lambda r: r.get('alpha_geometry', {}).get(metric, -1))
            selected[worst['destination']] = worst
        selected[population[0]['destination']] = population[0]
        selected[population[-1]['destination']] = population[-1]
        focused.update(selected)
        bindings = [{k: r.get(k) for k in ('destination', 'candidate_sha256', 'published_sha256', 'context_sha256')}
                    for r in sorted(population, key=lambda r: r['destination'])]
        group_records.append({'behavior': list(key), 'count': len(population), 'members': bindings,
                              'membership_sha256': fingerprint(bindings), 'samples': sorted(selected),
                              'approval': 'retained exact individuals' if key[0] == 'retained_individual_approval' else 'pending'})
    save(root / 'approval-groups.json', sealed({'inventory_sha256': inventory['sha256'],
                                               'policy_sha256': fingerprint(proposed), 'groups': group_records}))
    gallery(root / 'focused-review', sorted(focused.values(), key=lambda r: (r['approval_lane'], r['destination'])),
            title='Overlay representative and worst-case review: exact groups remain pending')
    compact_populations = defaultdict(list)
    for row in rows:
        compact_populations[(row['approval_lane'], row['review_family'])].append(row)
    compact = {}
    for population in compact_populations.values():
        for metric in ('rgb_mae', 'alpha_mae', 'edge_mae'):
            worst = max(population, key=lambda r: r.get('metrics', {}).get(metric, -1))
            compact[worst['destination']] = worst
        for metric in ('alpha_mass_relative_change', 'outside_edge_band_alpha_maximum', 'interior_rgb_mae'):
            worst = max(population, key=lambda r: r.get('alpha_geometry', {}).get(metric, -1))
            compact[worst['destination']] = worst
        seen_modes = set()
        for row in population:
            mode = (row['source_image']['mode'], row['source_image']['icc_profile'])
            if mode not in seen_modes:
                compact[row['destination']] = row
                seen_modes.add(mode)
    gallery(root / 'maintainer-review', sorted(compact.values(), key=lambda r: (r['approval_lane'], r['review_family'], r['destination'])),
            title='Compact overlay maintainer review: measured families, worst cases and mode/profile representatives')
    exceptions = [r for r in rows if r['approval_lane'] == 'individual_exception']
    gallery(root / 'individual-exceptions', exceptions, title='Complete overlay exception gallery')
    mapping_rows = [r for r in rows if r['hash_state'] == 'missing_published' or r.get('rename_from')
                    or r.get('alpha_geometry', {}).get('same_dimensions') is False]
    gallery(root / 'geometry-and-mappings', mapping_rows, title='Every dimension change and proposed destination decision')
    calibration_sample = next(r for r in rows if r['destination'] == 'network/overlays/bigger/BBC One.png')
    controls = negative_controls(calibration_sample['candidate_path'], root / 'controls', proposed)
    if not controls['passed']:
        raise BulkError('calibration_failed', 'A deliberately defective control passed the proposed policy')
    positives = [{'destination': r['destination'], 'strict': r.get('additional_screen'), 'edge': r.get('edge_screen')}
                 for r in rows if r['destination'] in retained]
    old_calibration = check_seal(load_json(ROOT.parent / 'config/library-sync-20261018/overlay-tolerance-calibration.json'))
    save(root / 'calibration.json', sealed({'controls': controls, 'actual_previously_accepted_positives': positives,
           'retained_positive_count': len(positives), 'new_policy_approved': False,
           'historical_policy_rejected_accepted_examples': old_calibration['known_accepted_screen_rejections'],
           'explanation': 'Historical global alpha MAE rejected accepted filter/ICC examples; exact individual approvals remain valid. '
                          'The new separate edge-family rule protects opaque interiors, bounds and support; it does not widen global bounds to admit all positives.',
           'strict_screen_positive_passes': sum(bool(p['strict'] and p['strict']['screen_pass']) for p in positives),
           'edge_screen_positive_passes': sum(bool(p['edge'] and p['edge']['screen_pass']) for p in positives)}))
    missing = []
    for r in rows:
        if r['hash_state'] == 'missing_published':
            missing.append({'destination': r['destination'], 'source': jobs[r['id']]['parameters']['input'],
                            'candidate_sha256': r['candidate_sha256'], 'baseline_absent': True,
                            'proposed_disposition': 'Add new generated overlay; existing public subject/logo; no existing overlay rename found',
                            'decision': 'Expected addition confirmed by maintainer; exact visual and staging approval pending'})
    save(root / 'destination-decisions.json', sealed({'expected_additions': missing,
        'expected_additions_confirmed_by_maintainer': True,
        'source_case_ledger_sha256': check_seal(load_json(LEDGER))['sha256'],
        'case_renames': [{'from': r['rename_from'], 'to': r['destination'],
                         'authoritative_source': r['authoritative_source'], 'candidate_sha256': r['candidate_sha256'],
                         'published_sha256': r['published_sha256'], 'visual_and_staging_approval': 'pending'}
                        for r in rows if r.get('rename_from')]}))
    counts = dict(Counter(r['approval_lane'] for r in rows))
    report = sealed({'kind': 'overlay-approval-preparation', 'expected': len(rows), 'baseline': original['baseline'],
                     'counts': counts, 'policy_sha256': fingerprint(proposed), 'manifest_sha256': manifest['sha256'],
                     'inventory_sha256': inventory['sha256'], 'groups': len(group_records), 'focused_samples': len(focused),
                     'compact_review_samples': len(compact),
                     'negative_controls': len(controls['controls']) - 1, 'negative_controls_missed': 0,
                     'positive_exact_control_passed': True, 'retained_individual_approvals': len(retained),
                     'proposed_uploads': len(manifest['members']), 'estimated_batches': (len(manifest['members']) + 299) // 300,
                     'expected_additions': len(missing), 'case_renames': sum(bool(r.get('rename_from')) for r in rows),
                     'proposed_publication_prs': 1, 'remote_writes': 0, 'policy_approved': False,
                     'artwork_regenerated': 0, 'candidate_bytes': sum(m['size'] for m in manifest['members'])})
    save(root / 'APPROVAL-REPORT.json', report)
    write_review_summary(root, report, inventory, proposed)
    return report


def write_review_summary(root, report, inventory, proposed):
    """Readable exact-scope checkpoint alongside the complete machine membership."""
    rows = inventory['rows']
    columns = ['destination', 'authoritative_source', 'output_variant', 'rename_from',
               'candidate_sha256', 'published_sha256', 'approval_lane', 'review_family',
               'required_publication_action', 'source_mode', 'source_icc_sha256',
               'candidate_dimensions', 'published_dimensions', 'layout_risks']
    with (root / 'complete-membership.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            record = {k: row.get(k) for k in columns}
            record.update(source_mode=row['source_image']['mode'],
                          source_icc_sha256=row['source_image']['icc_sha256'],
                          candidate_dimensions=row['candidate_image']['dimensions'],
                          published_dimensions=row.get('metrics', {}).get('published', {}).get('dimensions'))
            writer.writerow(record)
    breakdown = Counter((r['approval_lane'], r['review_family'], r['source_image']['mode'],
                         r['source_image']['icc_sha256'] or 'none', r['category']) for r in rows)
    with (root / 'complete-warning-breakdown.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['lane', 'family', 'source_mode', 'source_icc_sha256', 'category', 'count'])
        writer.writerows([*key, count] for key, count in sorted(breakdown.items()))
    counts = report['counts']
    lines = ['# Overlay exact approval checkpoint', '',
             'Proposal only. No new visual-policy or staging approval has been recorded.', '',
             f"Production baseline: `{report['baseline']['head']}`.", '',
             f"Policy SHA-256 (canonical payload): `{report['policy_sha256']}`.", '',
             f"Complete candidate manifest SHA-256: `{report['manifest_sha256']}`.", '',
             f"All {report['expected']:,} outputs have an explicit disposition. "
             f"{report['proposed_uploads']:,} exact Python files are proposed for one draft PR, "
             f"approximately {report['estimated_batches']} technical batches. "
             f"Includes {report['expected_additions']} expected additions and {report['case_renames']} case-only renames.", '',
             '| Exact population | Images |', '| --- | ---: |']
    lines += [f'| {lane} | {count:,} |' for lane, count in sorted(counts.items())]
    lines += ['', '## Review', '',
              '[Compact measured-family review](maintainer-review/review.html) · '
              '[All profile/transform groups](focused-review/review.html) · '
              '[Complete remaining exceptions](individual-exceptions/review.html) · '
              '[Every dimension change, expected addition and case correction](geometry-and-mappings/review.html)', '',
              'The compact gallery samples measured families and worst cases; it does not claim every '
              'exception has been individually inspected. Exact exception membership remains pending explicit '
              'maintainer acceptance. The 64 prior exact approvals are preserved without another review requirement.', '',
              '## Proposed policy and calibration', '',
              'Both black and white composites retain the original limits: RGB MAE ≤3, p99 ≤32, '
              'fraction changed by >16 ≤0.10, global luminance SSIM ≥0.98, region MAE ≤4 and edge MAE ≤6. '
              'The strict group additionally requires alpha MAE ≤1.5, identical dimensions and alpha≥16 bounds, '
              'alpha mass change ≤1%, no support outside a one-pixel neighborhood, opaque-core RGB/alpha MAE ≤1, '
              'opaque-core alpha error ≤16 and protected-interior alpha error ≤1/RGB MAE ≤1.', '',
              'The separate edge-resampling proposal replaces the global-alpha bound only for its exact measured '
              'members: alpha differences must remain within a two-pixel edge band with maximum error 64, '
              'while the protected interior, bounds, mass, support and composite limits still pass. '
              'Tagged published ICC profiles require separate color-managed exception review; they are not silently waived.', '',
              'The old screen rejected 38 of 64 accepted examples. Global alpha error and color/filter changes '
              'explain these rejections; the retained exact decisions are separate from tolerance qualification. '
              'The new rule does not admit every accepted positive. See calibration.json for each positive result. '
              'All eight deliberate defects fail both proposed screens; the exact positive control passes. '
              'Controls cover lost/faded alpha, displacement, crop, halo, a readability block, interior darkening '
              'and a one-pixel interior alpha hole.', '',
              '## Exact decision required', '',
              'Approve the policy hash and complete manifest hash above for draft staging, explicitly covering '
              'both proposed groups, the exact remaining exception population, the 12 confirmed expected additions '
              'and the 21 source-authoritative case-only renames. Retain the existing 64 decisions. '
              'This grants no merge or direct-master authorization. The uploader will refuse changed bytes, '
              'source context, membership or baseline.', '',
              'All binary-different eligible outputs are uploaded even when visually equivalent. '
              'Only exact SHA-256 matches at the correct filename can be skipped. '
              'Every staged file must pass actual remote SHA-256 and Git-blob verification plus a complete tree audit.', '']
    (root / 'APPROVAL.md').write_text('\n'.join(lines), encoding='utf-8')
    links = [('APPROVAL.md', 'Exact policy, populations and decision'),
             ('maintainer-review/review.html', 'Start here: compact measured-family review'),
             ('focused-review/review.html', 'All measured profile/transform groups'),
             ('geometry-and-mappings/review.html', 'All dimension changes, additions and case corrections'),
             ('individual-exceptions/review.html', 'Complete remaining exception gallery'),
             ('complete-membership.csv', 'Complete 4,122-image membership'),
             ('complete-warning-breakdown.csv', 'Complete warning/profile/category breakdown')]
    (root / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Overlay approval checkpoint</title>'
        '<style>body{font:18px system-ui;max-width:1000px;margin:40px auto}li{margin:16px}</style>'
        '<h1>Overlay approval checkpoint</h1><p>Proposal only; no artwork upload or approval inferred.</p><ul>' +
        ''.join('<li><a href="' + path + '">' + label + '</a></li>' for path, label in links) + '</ul>', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--measurements', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    print(build(args.inventory, args.measurements, args.root), flush=True)
