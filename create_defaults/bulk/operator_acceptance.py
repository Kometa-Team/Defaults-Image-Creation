"""Bounded real-catalog Windows acceptance without production writes."""

import argparse
from pathlib import Path
from types import SimpleNamespace

from .common import BulkError, sha256
from .config import Config
from .library_sources import check_seal, load_json, reference, save, sealed
from .operations import generate, validate_generation


def run(root):
    root = Path(root)
    data = reference('english')
    rows = [r for r in data['rows'] if r['job']['remote_relative']]
    by_category, by_font = {}, {}
    for row in sorted(rows, key=lambda r: r['job']['remote_relative']):
        job = row['job']
        by_category.setdefault(job['remote_relative'].split('/')[0], row)
        by_font.setdefault(job['parameters']['font'], row)
    selected = {r['job']['poster_id'] for r in list(by_category.values()) + list(by_font.values())}
    for row in rows:
        job = row['job']
        if job['remote_relative'] in {'decade/best/2020.jpg', 'studio/A.C.G.T..jpg'}:
            selected.add(job['poster_id'])
    selected.add(max(rows, key=lambda r: len(r['job']['parameters']['text']))['job']['poster_id'])
    config = Config(cache_dir=root / 'cache', workspace_dir=root / 'work', output_dir=root / 'output')
    args = SimpleNamespace(command='generate', definitions=None, profiles=None, category=[],
                           poster=sorted(selected), workers=2, report=root / 'first-generation.json')
    first = generate(args, config)
    report = check_seal(load_json(args.report))
    validate_generation(report)
    expected = {r['job']['id']: r['receipt']['sha256'] for r in data['rows']}
    checked, discrepancies = {}, []
    for stage in report['result']['stages']:
        for job in stage['manifest']['jobs']:
            actual = sha256(config.output_dir / job['local_relative'])
            checked[job['id']] = actual
            if actual != expected[job['id']]:
                discrepancies.append({'id': job['id'], 'expected': expected[job['id']], 'actual': actual})
    args.report = root / 'repeat-generation.json'
    repeat = generate(args, config)
    result = sealed({'kind': 'bounded-real-catalog-operator-acceptance',
                     'categories': sorted(by_category), 'fonts': sorted(by_font),
                     'selected_posters': sorted(selected), 'checked_outputs': checked,
                     'first': first, 'repeat': repeat, 'discrepancies': discrepancies,
                     'published': 0, 'powershell_rendering': False,
                     'passed': not discrepancies and repeat['executed'] == 0})
    save(root / 'ACCEPTANCE.json', result)
    if not result['passed']:
        raise BulkError('operator_acceptance', 'Representative output hashes or unchanged no-op acceptance failed')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.root)
    print({k: v for k, v in result.items() if k not in {'checked_outputs', 'selected_posters'}}, flush=True)
