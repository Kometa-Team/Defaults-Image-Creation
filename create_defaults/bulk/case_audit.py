"""Audit current PS1/YAML declarations, physical spelling and Git identities."""

import argparse
from collections import defaultdict
from pathlib import Path, PurePosixPath
import subprocess

from create_defaults.poster_fixtures import extract_rows
from .asset_cases import exact
from .catalog import load_catalog
from .common import BulkError, fingerprint, sha256
from .config import ROOT
from .library_sources import blob_id, save, sealed


def collisions(paths):
    grouped = defaultdict(list)
    for path in paths:
        grouped[path.casefold()].append(path)
    return {k: sorted(set(v)) for k, v in grouped.items() if len(set(v)) > 1}


def audit(root=ROOT):
    root = Path(root)
    literal = {r['line']: r for r in extract_rows(root / 'create_default_posters.ps1')}
    references = defaultdict(list)
    mismatches = []
    for definition in load_catalog(['all']):
        value = definition.data
        raw = literal.get(value['source']['line'], {}).get('row', {})
        if raw and fingerprint(raw) != value['source']['row_sha256']:
            raise BulkError('stale_definition', 'Catalog source row differs from authoritative PS1 input: ' + definition.id)
        for role in ('logo', 'avg_color_image', 'dom_color_image'):
            path = value['composer'].get(role)
            if role != 'logo' and not value['composer'].get(role.removesuffix('_image')):
                continue
            if not path or path.startswith('defaults-'):
                continue
            declared = raw.get(role, '').replace('\\', '/')
            if declared and PurePosixPath(declared).name.casefold() == PurePosixPath(path).name.casefold():
                canonical = str(PurePosixPath(path).parent / PurePosixPath(declared).name)
            else:
                canonical = path
            item = {'definition': definition.id, 'role': role, 'catalog_path': path,
                    'authoritative_path': canonical, 'ps1_line': value['source']['line'],
                    'ps1_row_sha256': value['source']['row_sha256']}
            references[path.casefold()].append(item)
            if path != canonical:
                mismatches.append(item)
    git_output = subprocess.check_output(['git', 'ls-files', '-z', '--', 'create_defaults'], cwd=root.parent)
    git_paths = {p.decode().removeprefix('create_defaults/') for p in git_output.split(b'\0') if p}
    duplicates = collisions(p for p in git_paths if p.startswith('logos_'))
    if duplicates:
        raise BulkError('git_case_collision', 'Tracked source paths differ only by capitalization: ' + repr(duplicates))
    migrations = []
    for key, items in sorted(references.items()):
        declared = {i['authoritative_path'] for i in items}
        if len(declared) != 1:
            raise BulkError('conflicting_authority', 'Input definitions disagree about capitalization: ' + repr(sorted(declared)))
        canonical = next(iter(declared))
        tracked = [p for p in git_paths if p.casefold() == key]
        if len(tracked) != 1:
            raise BulkError('git_case_collision', 'Expected one tracked source for ' + canonical)
        physical = tracked[0]
        exact(root, physical)
        if physical != canonical:
            migrations.append({'from': physical, 'to': canonical, 'sha256': sha256(root / physical),
                               'git_blob': blob_id(root / physical), 'authoritative_references': items})
    return sealed({'kind': 'authoritative-asset-case-audit', 'ps1_sha256': sha256(root / 'create_default_posters.ps1'),
                   'catalog_reference_mismatches': mismatches, 'migrations': migrations,
                   'tracked_case_collisions': 0, 'source_content_changes': 0})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    save(args.report, result)
    print({'migrations': len(result['migrations']), 'catalog_references': len(result['catalog_reference_mismatches']),
           'sha256': result['sha256']}, flush=True)
