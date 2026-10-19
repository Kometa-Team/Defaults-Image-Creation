"""Measure every Group B caption against published pixels; no visual approvals."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3

import numpy as np
from PIL import Image

from create_defaults.poster_text import load_layout
from .common import BulkError, confined, fingerprint, reject_links, sha256
from .config import ROOT
from .library_first_wave import proposal, split_populations
from .library_sources import check_seal, load_json, save, sealed, blob_id
from .library_sync import gallery
from .preflight import _historical_index

DIAGNOSTIC_POLICY = {'version': 'group-b-caption-diagnostic-v1', 'status': 'unapproved-diagnostic-only',
    'white_core_minimum_channel': 250, 'expected_alpha_support': 16,
    'pixel_neighbourhood_radius': 2, 'maximum_bounds_delta_pixels': 2,
    'maximum_unmatched_core_fraction': .005, 'maximum_candidate_noncaption_core_fraction': .03,
    'row_active_minimum_pixels': 10, 'join_row_gap_pixels': 12,
    'minimum_band_height_pixels': 5,
    'limitations': ['White-caption-specific; foreground contamination is withheld',
        'Projection bands are image measurements, not OCR', 'No alignment is applied',
        'Matched geometry does not certify semantic readability or grant warning approval']}


def dilate(mask, radius=2):
    """Boolean square neighbourhood, including image boundaries."""
    h, w = mask.shape
    padded = np.pad(mask, ((0, 0), (radius, radius)))
    horizontal = np.zeros_like(mask)
    for k in range(radius*2+1):
        horizontal |= padded[:, k:k+w]
    padded = np.pad(horizontal, ((radius, radius), (0, 0)))
    result = np.zeros_like(mask)
    for k in range(radius*2+1):
        result |= padded[k:k+h]
    return result


def mask_features(mask):
    yy, xx = np.nonzero(mask)
    bounds = [int(xx.min()), int(yy.min()), int(xx.max()+1), int(yy.max()+1)] if len(xx) else None
    active = np.flatnonzero(mask.sum(axis=1) >= DIAGNOSTIC_POLICY['row_active_minimum_pixels'])
    bands = []
    for y in active.tolist():
        if not bands or y-bands[-1][1] > DIAGNOSTIC_POLICY['join_row_gap_pixels']:
            bands.append([y, y+1])
        else:
            bands[-1][1] = y+1
    bands = [b for b in bands if b[1]-b[0] >= DIAGNOSTIC_POLICY['minimum_band_height_pixels']]
    return {'core_pixels': int(mask.sum()), 'bounds': bounds, 'row_bands': bands,
        'caption_box_margins': ([bounds[0], bounds[1], mask.shape[1]-bounds[2], mask.shape[0]-bounds[3]] if bounds else None)}


def pair_geometry(candidate, published, expected_support):
    ca, pu = mask_features(candidate), mask_features(published)
    contamination = float(np.count_nonzero(candidate & ~dilate(expected_support))/max(1,ca['core_pixels']))
    unmatched = [float(np.count_nonzero(a & ~dilate(b))/max(1,int(a.sum())))
                 for a,b in ((candidate,published),(published,candidate))]
    delta = max(abs(a-b) for a,b in zip(ca['bounds'],pu['bounds'])) if ca['bounds'] and pu['bounds'] else None
    band_delta = (max((abs(a-b) for aa,bb in zip(ca['row_bands'],pu['row_bands']) for a,b in zip(aa,bb)), default=0)
                  if len(ca['row_bands']) == len(pu['row_bands']) else None)
    reliable = bool(ca['core_pixels'] > 100 and pu['core_pixels'] > 100
        and contamination <= DIAGNOSTIC_POLICY['maximum_candidate_noncaption_core_fraction'])
    stable = bool(reliable and delta <= 2 and band_delta is not None and band_delta <= 2
                  and max(unmatched) <= DIAGNOSTIC_POLICY['maximum_unmatched_core_fraction'])
    return {'candidate': ca, 'published': pu, 'candidate_noncaption_core_fraction': contamination,
        'unmatched_core_fraction': unmatched, 'maximum_bounds_delta_pixels': delta,
        'maximum_row_band_delta_pixels': band_delta, 'measurement_reliable': reliable,
        'geometry_within_proposed_diagnostic_bounds': stable, 'alignment_applied': False}


def diagnose(row, job):
    p = job['parameters']
    if p['font_color'] != '#FFFFFF' or p['border']:
        raise BulkError('unsupported_diagnostic', 'This measured population requires white, unbordered captions')
    font = confined(ROOT, p['font'], must_exist=True)
    expected, metadata = load_layout(str(font), font.stat().st_mtime_ns).caption(p['text'],p['font_size'],(255,255,255))
    support = np.asarray(expected.getchannel('A')) > DIAGNOSTIC_POLICY['expected_alpha_support']
    box = (50, 1000+p['text_offset'], 1950, 2000+p['text_offset'])
    masks = []
    for field in ('candidate_path','published_path'):
        with Image.open(reject_links(row[field])) as im:
            masks.append(np.all(np.asarray(im.convert('RGB').crop(box)) >= 250,axis=2))
    geometry = pair_geometry(*masks, support)
    historic = _historical_index().get(job['poster_id'], {})
    unchanged = historic.get('historical_typography') == fingerprint({k:v for k,v in p.items()
        if k in {'font','font_size','text','text_offset'}})
    exact_expected_bands = (len(geometry['candidate']['row_bands']) == len(geometry['published']['row_bands']) == len(metadata['lines']))
    risks = row['layout_risks']
    if not geometry['measurement_reliable']:
        classification = 'foreground_contamination_or_insufficient_measurement'
    elif not geometry['geometry_within_proposed_diagnostic_bounds'] or not exact_expected_bands:
        classification = 'observed_geometry_difference_requires_review'
    elif not unchanged:
        classification = 'historical_typography_provenance_requires_review'
    elif 'caption_clipping' in risks:
        classification = 'same_observed_geometry_with_pretrim_clipping_warning'
    elif 'wrapped_caption' in risks:
        classification = 'legacy_wrapping_observed_in_both'
    else:
        classification = 'near_edge_advisory_without_observed_new_geometry_failure'
    return {'destination': row['destination'], 'candidate_sha256': row['candidate_sha256'],
        'published_sha256': row['published_sha256'], 'context_sha256': row['context_sha256'],
        'diagnostic_codes': risks, 'validation_severity': 'warning',
        'review_severity': 'high' if 'caption_clipping' in risks else 'medium' if 'caption_near_edge' in risks else 'low',
        'category': row['category'], 'font': row['font'], 'poster_id':job['poster_id'],
        'template': f"{job['layout_evidence']['kind']}:text_y={p['text_offset']}:logo_y={p['logo_offset']}",
        'source':job['source'], 'historical_typography_unchanged': unchanged,
        'expected_caption_lines': metadata['lines'], 'pretrim_ink_bounds': metadata['ink_bounds'],
        'observed': geometry, 'classification': classification, 'approval_granted': False,
        'semantic_readability_certified': False}


def build(root, analysis):
    root, analysis = Path(root), Path(analysis)
    inventory = check_seal(load_json(analysis/'english-reconciled-inventory.json'))
    policy = load_json(analysis/'proposed-tolerance-policy.json')
    production = check_seal(load_json(root/'production-snapshot.json'))
    populations = split_populations(proposal(inventory,policy,production,expected=None))
    selected = {m['destination'] for m in populations['B']['members']}
    rows = [r for r in inventory['rows'] if r['destination'] in selected]
    contexts = check_seal(load_json(ROOT.parent/'config/library-first-wave-20261018/context-identities.json'))
    jobs = {r['destination']:r['job'] for r in contexts['members']}
    entries = {e['path']:e for e in production['entries']}
    # This prior validated context is reusable only for these exact source inputs.
    input_paths = {i['path']:i['sha256'] for row in rows for i in jobs[row['destination']]['inputs']}
    for path,expected in input_paths.items():
        if sha256(confined(ROOT,path,must_exist=True)) != expected:
            raise BulkError('stale_input', 'Group B source/font input drift: '+path)
    cache = root/'group-b-diagnostics.sqlite'
    with sqlite3.connect(cache) as db:
        db.execute('CREATE TABLE IF NOT EXISTS measured (identity TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    def one(row):
        job = jobs[row['destination']]
        entry = entries[row['destination']]
        if (entry['sha'] != row['published_blob'] or entry['mode'] != '100644'
                or sha256(row['candidate_path']) != row['candidate_sha256']
                or sha256(row['published_path']) != row['published_sha256']
                or blob_id(row['published_path']) != entry['sha']):
            raise BulkError('comparison_drift','Group B comparison identity changed: '+row['destination'])
        key = fingerprint([row['candidate_sha256'],row['published_sha256'],job,DIAGNOSTIC_POLICY,sha256(Path(__file__))])
        import json
        with sqlite3.connect(cache) as db:
            old = db.execute('SELECT payload FROM measured WHERE identity=?',(key,)).fetchone()
        if old:
            return json.loads(old[0])
        value = diagnose(row,job)
        with sqlite3.connect(cache) as db:
            db.execute('INSERT OR REPLACE INTO measured VALUES (?,?)',(key,json.dumps(value)))
        return value
    measured = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for n,value in enumerate(pool.map(one,rows),1):
            measured.append(value)
            if n % 250 == 0:
                print(f'[GROUP B] {n}/{len(rows)} actual caption-pixel pairs measured',flush=True)
    groups = defaultdict(list)
    for m in measured:
        groups[(tuple(m['diagnostic_codes']),m['classification'])].append(m)
    review_groups = []
    by_path = {r['destination']:r for r in rows}
    for (codes,classification),items in sorted(groups.items()):
        picks = {}
        def pick(m,reason):
            picks.setdefault(m['destination'],set()).add(reason)
        pick(max(items,key=lambda m: max(m['observed']['unmatched_core_fraction'])),'worst core mismatch')
        pick(max(items,key=lambda m:m['observed']['maximum_bounds_delta_pixels'] or 0),'largest bound displacement')
        pick(min(items,key=lambda m:min(m['observed']['candidate']['caption_box_margins'] or [0])),'smallest caption margin')
        pick(max(items,key=lambda m:len(m['expected_caption_lines'])),'most wrapped lines')
        pick(max(items,key=lambda m:by_path[m['destination']]['metrics']['rgb_mae']),'largest full-image RGB difference')
        for category in sorted({m['category'] for m in items}):
            pick(next(m for m in items if m['category']==category),'category '+category)
        review_groups.append({'lane':classification,'category':'+'.join(codes),'font':'Comfortaa Medium',
            'membership_sha256':fingerprint(items), 'samples':[{'destination':d,'reasons':sorted(reasons)} for d,reasons in sorted(picks.items())]})
    review = root/'group-b-review'
    review.mkdir(exist_ok=True)
    for m in measured:
        by_path[m['destination']]['group_b_investigation'] = m
    gallery(review,rows,review_groups)
    report = sealed({'kind':'group-b-measured-warning-investigation',
        'inventory_sha256':inventory['sha256'], 'population_sha256':populations['B']['sha256'],
        'baseline':inventory['baseline'], 'production_snapshot_sha256':production['sha256'],
        'diagnostic_policy':DIAGNOSTIC_POLICY, 'diagnostic_policy_sha256':fingerprint(DIAGNOSTIC_POLICY),
        'count':len(measured), 'members':measured,
        'by_diagnostic':dict(Counter(c for m in measured for c in m['diagnostic_codes'])),
        'by_combination':dict(Counter('+'.join(m['diagnostic_codes']) for m in measured)),
        **{'by_'+key:dict(Counter(m[key] for m in measured)) for key in ('category','font','template','review_severity','classification')},
        'historical_typography_unchanged':sum(m['historical_typography_unchanged'] for m in measured),
        'geometry_diagnostic_passes':sum(m['observed']['geometry_within_proposed_diagnostic_bounds'] for m in measured),
        'semantic_readability_certified':0, 'new_warning_approvals':0,
        'representative_pairs':sum(len(g['samples']) for g in review_groups),
        'review_groups':review_groups, 'source_module_sha256':sha256(Path(__file__))})
    save(root/'group-b-warning-report.json',report)
    save(root/'group-b-population-investigated.json',populations['B'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--analysis',type=Path,required=True)
    args = parser.parse_args()
    r = build(args.root,args.analysis)
    print({k:r[k] for k in ('count','by_classification','geometry_diagnostic_passes','representative_pairs','sha256')})


if __name__=='__main__':
    main()
