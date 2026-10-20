"""Additional proposal-only PNG alpha/geometry checks; no automatic approval."""

from collections import Counter
from copy import deepcopy
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageStat

from .common import fingerprint, sha256
from .library_sources import check_seal, load_json, save, sealed
from .library_visual import compare_images, evaluate


def policy(base):
    from .asset_cases import ledger
    cases = ledger()
    return {'schema_version': 1, 'version': 'overlay-alpha-composite-review-v1', 'status': 'proposed',
            'measurement_source_sha256': sha256(__file__),
            'visual_source_sha256': sha256(Path(__file__).with_name('library_visual.py')),
            'filename_policy': {'rule': 'Preserve the exact authoritative source asset basename in both sizes and public Git paths',
                'source_case_ledger_sha256': cases.get('sha256'), 'authoritative_ps1_sha256': cases.get('source_ps1_sha256'),
                'independent_basename_overrides': False, 'case_exact_windows_checks': True,
                'published_case_renames': 'Only exact approved source-basename corrections; paired index deletion/addition in one commit'},
            'visual_policy': deepcopy(base), 'alpha_geometry': {
                'dimensions_identical': True, 'alpha_16_bounds_identical': True,
                'maximum_alpha_mass_relative_change': .01, 'support_radius_original_pixels': 1,
                'maximum_unmatched_support_pixels': 0,
                'maximum_opaque_core_rgb_mae': 1.0, 'maximum_opaque_core_alpha_mae': 1.0,
                'maximum_opaque_core_alpha_error': 16, 'maximum_interior_alpha_error': 1,
                'maximum_interior_rgb_mae': 1.0},
            'candidate_contract': 'Single-frame RGBA PNG without ICC; unchanged verified source/renderer/transform',
            'edge_resampling_family': {
                'approval': 'Separate proposed group rule; no approval inferred from the old global-alpha screen',
                'unchanged_visual_thresholds': 'All original black/white composite bounds except global alpha MAE',
                'edge_band_radius_original_pixels': 2, 'maximum_edge_alpha_error': 64,
                'maximum_interior_alpha_error': 1, 'maximum_interior_rgb_mae': 1.0,
                'maximum_alpha_mass_relative_change': .01, 'alpha_16_bounds_identical': True,
                'maximum_unmatched_support_radius_1': 0,
                'reason': 'Allow only measured edge-localized filter differences; reject interior opacity/color, support or geometry changes'},
            'scope': 'Exact measured membership only; both black/white composites must pass original visual bounds',
            'exceptions': 'Outside bounds requires explicit exact individual acceptance; missing/case mappings require separate decisions',
            'approval_granted': False}


def measure(candidate, published):
    with Image.open(candidate) as ca, Image.open(published) as pu:
        contract = ca.format == 'PNG' and ca.mode == 'RGBA' and not ca.info.get('icc_profile') and getattr(ca, 'n_frames', 1) == 1
        profiles = {'candidate': bool(ca.info.get('icc_profile')), 'published': bool(pu.info.get('icc_profile'))}
        a, b = ca.convert('RGBA'), pu.convert('RGBA')
    result = {'candidate_contract': contract, 'icc_profiles': profiles, 'same_dimensions': a.size == b.size}
    if a.size != b.size:
        return result
    aa, bb = np.asarray(a), np.asarray(b)
    alpha_a, alpha_b = aa[:, :, 3].astype(np.int16), bb[:, :, 3].astype(np.int16)
    def mask(image):
        return image.getchannel('A').point(lambda value: 255 if value >= 16 else 0)
    ma, mb = mask(a), mask(b)
    result['alpha_16_bounds'] = [ma.getbbox(), mb.getbbox()]
    result['alpha_mass_relative_change'] = abs(float(alpha_a.sum()) - float(alpha_b.sum())) / max(1, int(alpha_b.sum()))
    result['unmatched_support_radius_1'] = int(sum(np.count_nonzero(np.asarray(x) & ~np.asarray(y.filter(ImageFilter.MaxFilter(3))))
                                              for x, y in [(ma, mb), (mb, ma)]))
    core = (alpha_a >= 240) & (alpha_b >= 240)
    result['opaque_core_pixels'] = int(core.sum())
    color_delta = np.abs(aa[:, :, :3].astype(np.int16) - bb[:, :, :3].astype(np.int16))
    alpha_delta = np.abs(alpha_a - alpha_b)
    result['opaque_core_rgb_mae'] = float(color_delta[core].mean()) if core.any() else 0.0
    result['opaque_core_alpha_mae'] = float(alpha_delta[core].mean()) if core.any() else 0.0
    result['opaque_core_alpha_maximum'] = int(alpha_delta[core].max()) if core.any() else 0
    invisible = (alpha_a == 0) & (alpha_b == 0)
    result['hidden_rgb_different_pixels'] = int(np.count_nonzero(np.any(color_delta > 0, axis=2) & invisible))
    result['alpha_maximum'] = int(alpha_delta.max())
    result['alpha_mae'] = float(alpha_delta.mean())
    inner_a = a.getchannel('A').point(lambda v: 255 if v >= 240 else 0).filter(ImageFilter.MinFilter(5))
    inner_b = b.getchannel('A').point(lambda v: 255 if v >= 240 else 0).filter(ImageFilter.MinFilter(5))
    # Union prevents a newly punched alpha hole from redefining itself as an
    # antialiasing edge. Either image's established opaque interior is protected.
    interior = (np.asarray(inner_a) > 0) | (np.asarray(inner_b) > 0)
    result['interior_pixels'] = int(interior.sum())
    result['interior_rgb_mae'] = float(color_delta[interior].mean()) if interior.any() else 0.0
    outer = (np.asarray(ma.filter(ImageFilter.MaxFilter(5))) > 0) | (np.asarray(mb.filter(ImageFilter.MaxFilter(5))) > 0)
    band = outer & ~interior
    result['outside_edge_band_alpha_maximum'] = int(alpha_delta[~band].max()) if (~band).any() else 0
    result['edge_band_alpha_maximum'] = int(alpha_delta[band].max()) if band.any() else 0
    return result


def screen(row, measured, proposed):
    failures = []
    m = row.get('metrics', {})
    if not measured['candidate_contract']:
        failures.append('candidate_contract')
    if not measured['same_dimensions']:
        failures.append('dimensions')
    else:
        bounds = proposed['alpha_geometry']
        if measured['alpha_16_bounds'][0] != measured['alpha_16_bounds'][1]:
            failures.append('alpha_16_bounds')
        for key, limit in [('alpha_mass_relative_change', bounds['maximum_alpha_mass_relative_change']),
                           ('unmatched_support_radius_1', bounds['maximum_unmatched_support_pixels']),
                           ('opaque_core_rgb_mae', bounds['maximum_opaque_core_rgb_mae']),
                           ('opaque_core_alpha_mae', bounds['maximum_opaque_core_alpha_mae']),
                           ('opaque_core_alpha_maximum', bounds['maximum_opaque_core_alpha_error']),
                           ('outside_edge_band_alpha_maximum', bounds['maximum_interior_alpha_error']),
                           ('interior_rgb_mae', bounds['maximum_interior_rgb_mae'])]:
            if measured[key] > limit:
                failures.append(key)
        if measured['icc_profiles']['published']:
            failures.append('published_profile_requires_color_managed_review')
    visual = evaluate(m, proposed['visual_policy'])
    failures += visual['failures']
    # Check every compositing background, rather than whichever has worst MAE.
    for composite in m.get('composites', []):
        check = evaluate(dict(m, **composite), proposed['visual_policy'])
        failures += ['composite_' + str(composite['background']) + '_' + f for f in check['failures']]
    return {'screen_pass': not failures, 'failures': sorted(set(failures)),
            'policy_sha256': fingerprint(proposed), 'approval_granted': False}


def edge_screen(row, measured, proposed):
    """A separate, narrow edge-resampling proposal, never a waiver of all alpha warnings."""
    original = screen(row, measured, proposed)
    kept = [f for f in original['failures'] if f not in {
        'alpha_mae', 'composite_0_alpha_mae', 'composite_255_alpha_mae',
        'opaque_core_alpha_mae', 'opaque_core_alpha_maximum', 'opaque_core_rgb_mae'}]
    limits = proposed['edge_resampling_family']
    if measured['same_dimensions']:
        for key, threshold in [('outside_edge_band_alpha_maximum', limits['maximum_interior_alpha_error']),
                               ('edge_band_alpha_maximum', limits['maximum_edge_alpha_error']),
                               ('interior_rgb_mae', limits['maximum_interior_rgb_mae'])]:
            if measured[key] > threshold:
                kept.append(key)
    return {'screen_pass': not kept, 'failures': sorted(set(kept)),
            'policy_sha256': fingerprint(proposed), 'approval_granted': False}


def negative_controls(candidate, root, proposed):
    """Deliberate alpha, color, placement, crop and boundary defects."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with Image.open(candidate) as original:
        original = original.convert('RGBA')
    defects = {}
    image = original.copy()
    image.putalpha(Image.new('L', image.size, 255))
    defects['lost_alpha'] = image
    image = original.copy()
    image.putalpha(image.getchannel('A').point(lambda v: max(0, v - 32)))
    defects['faded_alpha'] = image
    image = Image.new('RGBA', original.size)
    image.paste(original, (5, 0))
    defects['shift_5px'] = image
    defects['crop_width'] = original.crop((0, 0, original.width - 2, original.height))
    image = original.copy()
    image.putalpha(original.getchannel('A').filter(ImageFilter.MaxFilter(5)))
    defects['halo_alpha'] = image
    image = original.copy()
    image.paste((255, 0, 255, 255), (0, 0, max(1, image.width // 3), max(1, image.height // 2)))
    defects['colored_readability_block'] = image
    color = ImageChops.subtract(original.convert('RGB'), Image.new('RGB', original.size, (32, 32, 32)))
    color.putalpha(original.getchannel('A'))
    defects['interior_color_darkening'] = color
    image = original.copy()
    interior = np.asarray(original.getchannel('A').filter(ImageFilter.MinFilter(5))) >= 240
    coordinates = np.argwhere(interior)
    if len(coordinates):
        y, x = coordinates[len(coordinates) // 2]
        red, green, blue, alpha = image.getpixel((int(x), int(y)))
        image.putpixel((int(x), int(y)), (red, green, blue, alpha - 32))
    else:
        image.putalpha(image.getchannel('A').point(lambda v: max(0, v - 32)))
    defects['interior_alpha_hole'] = image
    results = []
    for name, image in [('positive_exact', original)] + list(defects.items()):
        path = root / (name + '.png')
        image.save(path)
        row = {'metrics': compare_images(path, candidate)}
        measured = measure(path, candidate)
        result = screen(row, measured, proposed)
        edge = edge_screen(row, measured, proposed)
        results.append({'name': name, 'expected_pass': name == 'positive_exact', 'result': result, 'edge_result': edge,
                        'candidate': str(path), 'baseline': str(candidate)})
    return sealed({'policy_sha256': fingerprint(proposed), 'controls': results,
                   'passed': all(r['result']['screen_pass'] == r['expected_pass'] and
                                 r['edge_result']['screen_pass'] == r['expected_pass'] for r in results),
                   'approval_granted': False})
