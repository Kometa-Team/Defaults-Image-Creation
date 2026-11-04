"""Seal and verify a portable runtime without importing acquisition services."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from bulk_regeneration_state import reject_links

RUNTIME_FILES=(
    'create_people_poster.py','poster_fonts.py','people_workspaces.py',
    'people_diagnostics.py','people_process.py','bulk_regenerate.py',
    'bulk_regeneration_plan.py','bulk_regeneration_state.py','bulk_regeneration_report.py',
    'bulk_source.py','bulk_git_sync.py','bulk_runtime.py','bulk_reconcile.py','bulk_benchmark.py','bulk_zfs_source.py','bulk_validate.py','github_inventory_core.py',
)


def release_digest(path, normalized=True):
    data=Path(path).read_bytes()
    if normalized and Path(path).suffix in {'.py','.txt'}:
        data=data.replace(b'\r\n',b'\n')
    return hashlib.sha256(data).hexdigest()


def release_files(root):
    return [*(root/name for name in RUNTIME_FILES),
            *sorted((root/'fonts').glob('*.ttf')),*sorted((root/'fonts').glob('OFL-*.txt')),
            *sorted((root/'assets/people').glob('*'))]


def verify_release(root,path):
    root=Path(root);reject_links(path)
    value=json.loads(Path(path).read_text(encoding='utf8'))
    if value.get('version') not in {1,2} or value.get('renderer_commit')!='fe59024c53f1bb50cd55d1bf81a3cf8a73339512':
        raise ValueError('Unknown renderer release provenance')
    expected={p.relative_to(root).as_posix() for p in release_files(root) if p.is_file()}
    if set(value['files'])!=expected:
        raise ValueError('Incomplete runtime release inventory')
    for relative,digest in value['files'].items():
        path=root/relative;reject_links(path)
        if release_digest(path, normalized=value['version']==2)!=digest:
            raise ValueError('Runtime release file changed: '+relative)
    return value


def seal(root,target):
    root=Path(root).resolve()
    approved='fe59024c53f1bb50cd55d1bf81a3cf8a73339512'
    result=subprocess.run(['git','-C',str(root.parent),'show',approved+':create_people_posters/create_people_poster.py'],
                          capture_output=True,check=True)
    current=(root/'create_people_poster.py').read_bytes()
    if current.replace(b'\r\n',b'\n')!=result.stdout.replace(b'\r\n',b'\n'):
        raise ValueError('Core renderer differs from approved PR61; review its provenance before sealing')
    files={p.relative_to(root).as_posix():release_digest(p)
           for p in release_files(root) if p.is_file()}
    if any(name not in files for name in RUNTIME_FILES):
        raise ValueError('Missing required runtime module')
    value=dict(version=2,renderer_commit=approved,files=files)
    reject_links(target)
    with Path(target).open('x',encoding='utf8') as stream:
        json.dump(value,stream,sort_keys=True,indent=2)
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['seal','verify'])
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--manifest',type=Path,required=True)
    args=parser.parse_args()
    value=seal(args.root,args.manifest) if args.command=='seal' else verify_release(args.root,args.manifest)
    print(json.dumps(dict(renderer_commit=value['renderer_commit'],verified_files=len(value['files']))))


if __name__=='__main__':main()
