"""Portable source inventory and PNG audit; no acquisition or renderer construction."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import unicodedata

from bulk_regeneration_state import canonical, reject_links, sha

SOURCE_URL = 'https://github.com/Kometa-Team/People-Images-transparent.git'
KNOWN_INPUTS = (
    'B/Images/Bo Derek.png', 'B/Images/Burak Berkay Akgül.png',
    'C/Images/Can Yaman.png', 'C/Images/Carol Cheng.png',
    'C/Images/Carrie Ng Ka-Lai.png', 'C/Images/Cem Söküt.png',
    'C/Images/Chae Seo-an.png', 'C/Images/Charles Esten.png',
)


def path_key(path):
    if (not path or '\\' in path or path.startswith('/') or
            any(ord(c) < 32 or ord(c) == 127 for c in path) or
            any(p in {'', '.', '..'} or ':' in p for p in path.split('/'))):
        raise ValueError('Unsafe repository path: '+repr(path))
    return unicodedata.normalize('NFC', path).casefold()


def git(root, *args, network=False):
    environment=dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    for key in ('GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','GIT_OBJECT_DIRECTORY','GIT_ALTERNATE_OBJECT_DIRECTORIES'):
        environment.pop(key,None)
    if not network:
        environment['GIT_NO_LAZY_FETCH']='1'
    result=subprocess.run(['git','--no-optional-locks','-c','core.autocrlf=false',
        '-c','core.hooksPath='+os.devnull,'-c','gc.auto=0','-c','maintenance.auto=false',
        '-c','safe.directory='+str(Path(root).resolve()),
        '-C',str(root),*args],capture_output=True,env=environment)
    if result.returncode:
        raise ValueError('Git operation failed: '+' '.join(args[:2]))
    return result.stdout


def tracked_images(root, ref='HEAD'):
    result=[]
    for entry in git(root,'ls-tree','-r','-z',ref).split(b'\0'):
        if not entry:
            continue
        attributes,relative=entry.split(b'\t',1)
        mode,kind,oid=attributes.split()
        path=relative.decode('utf8')
        path_key(path)
        if PurePosixPath(path).suffix.lower()!='.png':
            continue
        if mode!=b'100644' or kind!=b'blob' or len(PurePosixPath(path).parts)!=3 or PurePosixPath(path).parts[1]!='Images':
            raise ValueError('Unexpected tracked PNG layout/mode: '+path)
        local=Path(root)/path;reject_links(local)
        result.append(dict(relative=path,git_blob=oid.decode(),size=local.stat().st_size if local.is_file() else 0))
    return sorted(result,key=lambda row:(path_key(row['relative']),row['relative']))


def source_identity(root):
    root=Path(root).absolute();reject_links(root)
    if Path(git(root,'rev-parse','--show-toplevel').decode().strip()).resolve()!=root.resolve():
        raise ValueError('Source must be the exact repository root')
    url=git(root,'remote','get-url','origin').decode().strip()
    if url not in {SOURCE_URL,SOURCE_URL.removesuffix('.git')}:
        raise ValueError('Unexpected transparent source remote')
    if git(root,'status','--porcelain=v1','--untracked-files=all'):
        raise ValueError('Source working tree is not clean')
    return dict(repository='Kometa-Team/People-Images-transparent',branch='master',
                commit=git(root,'rev-parse','HEAD').decode().strip(),root=str(root.resolve()))


def remote_snapshot():
    """Use the existing bounded GET-only inventory transport, with tree fallback."""
    import requests
    from github_inventory_core import complete_tree, get_json
    with requests.Session() as session:
        session.headers.update({'Accept':'application/vnd.github+json','User-Agent':'kometa-people-bulk'})
        branch=get_json(session,'https://api.github.com/repos/Kometa-Team/People-Images-transparent/branches/master')
        commit=branch['commit']['sha'];tree_id=branch['commit']['commit']['tree']['sha']
        entries=complete_tree(lambda oid,recursive:get_json(session,
            'https://api.github.com/repos/Kometa-Team/People-Images-transparent/git/trees/'+oid+('?recursive=1' if recursive else '')),tree_id)
    images=[]
    for entry in entries:
        if entry['type']=='blob' and entry['path'].lower().endswith('.png'):
            path_key(entry['path'])
            if entry['mode']!='100644':raise ValueError('Unexpected remote source mode')
            images.append(dict(relative=entry['path'],git_blob=entry['sha'],size=entry['size']))
    return dict(commit=commit,tree=tree_id,total=len(images),bytes=sum(r['size'] for r in images),items=images)


def scan_sources(root, exclude_ambiguous=False, hash_sources=True, progress=None):
    """The standalone scanner preserves exact stems, independent of legacy publication."""
    root=Path(root);rows=[];ignored=[]
    committed={r['relative']:r for r in tracked_images(root)} if (root/'.git').exists() else {}
    for initial in sorted(root.iterdir(),key=lambda p:p.name):
        if initial.name.startswith('.'):
            continue
        reject_links(initial)
        directory=initial/'Images'
        if not directory.is_dir():
            continue
        reject_links(directory)
        for path in sorted(directory.iterdir(),key=lambda p:p.name):
            reject_links(path)
            relative=path.relative_to(root).as_posix();path_key(relative)
            if not path.is_file():
                raise ValueError('Unexpected nested directory in source Images: '+relative)
            if path.suffix.lower()!='.png':
                ignored.append(dict(path=relative,reason='not a PNG source'));continue
            info=path.stat()
            if committed and relative not in committed:
                raise ValueError('PNG is not in the pinned Git source: '+relative)
            rows.append(dict(relative=relative,name=path.stem,source_hash='',
                size=info.st_size,source_mtime_ns=info.st_mtime_ns,source_error=''))
            if committed:rows[-1]['git_blob']=committed[relative]['git_blob']
    if not rows:
        raise ValueError('No transparent PNGs under INITIAL/Images')
    rows.sort(key=lambda row:(path_key(row['relative']),row['relative']))
    for number,row in enumerate(rows):
        row['number']=number
        if hash_sources:
            payload,blob=content_hashes(root/row['relative'])
            if row.get('git_blob') and blob!=row['git_blob']:
                raise ValueError('Source bytes differ from pinned Git blob: '+row['relative'])
            row['source_hash']=payload
            if progress and ((number+1)%100==0 or number+1==len(rows)):
                progress(number+1,len(rows),'[hash] '+row['relative'])
    return rows,ignored


def sample_numbers(rows,count):
    if count<1:
        raise ValueError('Sample size must be positive')
    orders=[sorted(rows,key=lambda r:len(r['name'])),sorted(rows,key=lambda r:-len(r['name'])),
            [r for r in rows if not r['name'].isascii()],
            [r for r in rows if any(c in r['name'] for c in "-'.,()")],rows]
    chosen=[]
    for order in orders:
        for row in order[:max(1,count//len(orders))]:
            if row['number'] not in chosen and len(chosen)<count:
                chosen.append(row['number'])
    for index in range(count):
        if rows:
            row=rows[min(len(rows)-1,index*len(rows)//count)]
            if row['number'] not in chosen and len(chosen)<count:
                chosen.append(row['number'])
    return chosen


def verify_png(path):
    from PIL import Image
    from bulk_regeneration_plan import image_header
    attributes=image_header(path,verify=True)
    with Image.open(path) as image:
        image.load()
    return attributes


def content_hashes(path):
    reject_links(path)
    before=path.stat()
    blob=hashlib.sha1(b'blob '+str(before.st_size).encode()+b'\0')
    payload=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(1024*1024):
            blob.update(block);payload.update(block)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError('Source changed while hashing')
    return payload.hexdigest(),blob.hexdigest()


def audit(root, progress=None):
    root=Path(root).resolve();identity=source_identity(root)
    rows=tracked_images(root);errors=[];verified=[]
    if not rows:
        raise ValueError('No tracked PNG sources')
    for number,row in enumerate(rows,1):
        try:
            path=root/row['relative']
            payload,blob=content_hashes(path)
            if blob!=row['git_blob']:
                raise ValueError('Working bytes differ from committed Git blob')
            attributes=verify_png(path)
            verified.append(dict(row,source_hash=payload,attributes=attributes))
        except (OSError,ValueError,SyntaxError) as error:
            errors.append(dict(path=row['relative'],error=str(error)))
        if progress and (number%100==0 or number==len(rows)):
            progress(number,len(rows),row['relative'])
    if source_identity(root)!=identity:
        raise ValueError('Source revision changed during integrity audit')
    catalog={r['relative'] for r in verified}
    result=dict(version=1,source=identity,total=len(rows),verified=len(verified),failed=len(errors),
        bytes=sum(r['size'] for r in rows),errors=errors,items=verified,
        known_inputs={path:('verified' if path in catalog else 'failed_or_missing') for path in KNOWN_INPUTS})
    result['inventory_sha256']=canonical(verified)
    return result


def changes(root,old,new):
    result=[]
    parts=git(root,'diff','--name-status','-z','--find-renames',old,new).split(b'\0')
    i=0
    while i<len(parts) and parts[i]:
        status=parts[i].decode();i+=1
        path=parts[i].decode('utf8');i+=1
        row=dict(status=status,path=path)
        if status[0] in {'R','C'}:
            row.update(old_path=path,path=parts[i].decode('utf8'));i+=1
        for name in (row['path'],row.get('old_path',row['path'])):path_key(name)
        if any(PurePosixPath(row.get(k,'')).suffix.lower()=='.png' for k in ('path','old_path')):
            result.append(row)
    return result


def validate_pin(root,path,require_readonly=False):
    root=Path(root).resolve();path=Path(path)
    reject_links(path)
    value=json.loads(path.read_text(encoding='utf8'))
    digest=value.pop('pin_sha256')
    if canonical(value)!=digest:
        raise ValueError('Source pin digest mismatch')
    if value.get('protection')=='zfs-held-snapshot':
        storage=value['storage']
        if (not str(storage['snapshot_guid']).isdigit() or '@people-' not in storage['snapshot']
                or storage.get('hold_tag')!='kometa-people-bulk' or not require_readonly):
            raise ValueError('ZFS pins require verified snapshot metadata and read-only source enforcement')
        if os.name!='posix' or not os.statvfs(path).f_flag & os.ST_RDONLY:
            raise ValueError('ZFS pin registry must also be mounted read-only')
        audit_path=path.with_name(value['source']['commit']+'.audit.json')
        reject_links(audit_path)
        report=json.loads(audit_path.read_text(encoding='utf8'))
        if (canonical(report)!=value['audit_sha256'] or report.get('failed')
                or report['inventory_sha256']!=value['inventory_sha256']
                or report['total']!=report['verified']):
            raise ValueError('Pinned source audit no longer verifies')
    elif path.resolve().parent != root/'.git/people-bulk-pins':
        raise ValueError('Pin must be registered inside this source repository')
    identity=source_identity(root)
    if value['source']['commit']!=identity['commit'] or value['source']['repository']!=identity['repository']:
        raise ValueError('Pinned source revision differs from the mounted checkout')
    if require_readonly:
        if os.name!='posix' or not os.statvfs(root).f_flag & os.ST_RDONLY:
            raise ValueError('Container source must be a read-only filesystem mount')
    return dict(value,pin_sha256=digest)


def sync_status(root, online=False):
    identity=source_identity(root)
    # Read-only status never fetches, refreshes an index, or auto-downloads blobs.
    ref=git(root,'rev-parse','refs/remotes/origin/master').decode().strip()
    result=dict(read_only=True,source=identity,last_fetched_master=ref)
    if online:
        remote=git(root,'ls-remote','--exit-code','origin','refs/heads/master',network=True).decode().split()[0]
        result['remote_master']=remote
    result['changes']=changes(root,identity['commit'],ref)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['status','audit'])
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--online',action='store_true')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args(argv)
    value=sync_status(args.source,args.online) if args.command=='status' else audit(args.source,
        progress=lambda n,t,c:print(f'[AUDIT] {n}/{t} {c}',file=sys.stderr,flush=True))
    if args.report:
        reject_links(args.report)
        if args.source.resolve()==args.report.resolve() or args.source.resolve() in args.report.resolve().parents:
            raise ValueError('Audit reports must be outside the source')
        if args.report.exists():
            raise ValueError('Report already exists; preserve previous evidence')
        with args.report.open('x',encoding='utf8') as stream:
            json.dump(value,stream,indent=2,ensure_ascii=True)
            stream.flush();os.fsync(stream.fileno())
    print(json.dumps({k:v for k,v in value.items() if k!='items'},indent=2,ensure_ascii=True))
    return 1 if value.get('failed') else 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError) as error:
        print('ERROR: '+str(error),file=sys.stderr);raise SystemExit(1)
