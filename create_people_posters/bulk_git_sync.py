"""Explicit source Git maintenance. Never scheduled; never renders or publishes."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from bulk_source import SOURCE_URL, changes, git, source_identity, sync_status
from bulk_regeneration_state import atomic_json, canonical, reject_links


@contextmanager
def source_lock(root):
    """All source mutators/pinners cooperate on one local filesystem lock."""
    root=Path(root);reject_links(root)
    if not (root/'.git').is_dir():
        raise ValueError('Source maintenance requires a standalone checkout, not a linked Git worktree')
    path=root/'.git/people-bulk-source.lock';reject_links(path)
    with path.open('a+b') as stream:
        if stream.tell()==0:stream.write(b'0');stream.flush()
        stream.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def pins(root):
    directory=Path(root)/'.git/people-bulk-pins'
    if not directory.exists():return []
    reject_links(directory)
    result=[]
    for path in directory.iterdir():
        reject_links(path)
        if path.suffix!='.json':
            raise ValueError('Unknown source pin metadata; preserve it')
        value=json.loads(path.read_text(encoding='utf8'))
        expected=value.pop('pin_sha256')
        if canonical(value)!=expected:
            raise ValueError('Source pin digest mismatch; source remains protected')
        result.append(value)
    return result


def pin_source(root,batch_id,audit_report):
    """Persistent cooperative pin survives crashes; release is deliberately separate."""
    if not batch_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in batch_id):
        raise ValueError('Unsafe batch pin identifier')
    with source_lock(root):
        identity=source_identity(root)
        report=json.loads(Path(audit_report).read_text(encoding='utf8'))
        if report.get('failed') or report.get('source')!=identity or report.get('verified')!=report.get('total'):
            raise ValueError('A successful full audit of this exact source revision is required')
        from bulk_source import KNOWN_INPUTS
        if set(report.get('known_inputs',{}))!=set(KNOWN_INPUTS) or any(value!='verified' for value in report['known_inputs'].values()):
            raise ValueError('Known integrity acceptance inputs are missing or unverified')
        if canonical(report['items'])!=report['inventory_sha256']:
            raise ValueError('Audit inventory digest mismatch')
        value=dict(version=1,batch_id=batch_id,source=identity,audit_sha256=canonical(report),
                   inventory_sha256=report['inventory_sha256'],created=time.time(),
                   protection='persistent-cooperative-checkout-pin')
        value['pin_sha256']=canonical(value)
        directory=Path(root)/'.git/people-bulk-pins'
        reject_links(directory);directory.mkdir(exist_ok=True)
        target=directory/(batch_id+'.json')
        if target.exists():
            raise ValueError('Pin already exists; preserve it')
        atomic_json(target,value)
        return value


def initial_clone(root,confirmed_parent,source_budget_gib=128):
    root=Path(root).absolute();parent=Path(confirmed_parent).resolve()
    reject_links(root);reject_links(parent)
    if root.parent.resolve()!=parent or root.exists() and any(root.iterdir()):
        raise ValueError('Initial clone requires a new directory directly under the confirmed destination')
    if not 1<=source_budget_gib<=4096:
        raise ValueError('Source budget must be 1..4096 GiB')
    # Git trees contain paths and blob IDs, not blob sizes. Asking ls-tree -l
    # in a blobless clone would hydrate the entire current payload. Use an
    # explicit conservative checkout budget before any download, then measure
    # the actual pinned checkout. No REST inventory/authentication is needed.
    required=int(source_budget_gib*1024**3*2.15)+4*1024**3
    if shutil.disk_usage(parent).free<required:
        raise ValueError(f'Initial clone needs approximately {required/1024**3:.2f} GiB free for current files, Git objects and reserve')
    environment=dict(os.environ,GIT_TERMINAL_PROMPT='0')
    print(f'[SOURCE] Capacity admitted: {required/1024**3:.2f} GiB free budget for {source_budget_gib} GiB source ceiling',flush=True)
    probe=subprocess.run(['git','-c','protocol.version=2','ls-remote','--exit-code',SOURCE_URL,'refs/heads/master'],
        capture_output=True,env=dict(environment,GIT_TRACE_PACKET='1'))
    if probe.returncode or not any('fetch=' in line and 'filter' in line for line in probe.stderr.decode(errors='replace').splitlines()):
        raise ValueError('Server did not advertise partial-clone filtering; refusing an unbounded historical clone')
    advertised=probe.stdout.decode().split()[0]
    import re
    if not re.fullmatch('[0-9a-f]{40}',advertised):raise ValueError('Unexpected Git master object ID')
    print('[SOURCE] Git master '+advertised+'; cloning commit/tree metadata without historical blobs',flush=True)
    # Keep commit/tree history for ancestry checks, while omitting historical
    # binary payloads. Current checkout contents still download in full.
    result=subprocess.run(['git','-c','core.autocrlf=false','-c','core.hooksPath='+os.devnull,
        'clone','--filter=blob:none','--no-checkout','--single-branch','--branch','master','--no-tags',SOURCE_URL,str(root)],env=environment)
    if result.returncode:
        raise ValueError('Clone failed; preserve the partial directory for diagnosis')
    if git(root,'rev-parse','HEAD').decode().strip()!=advertised:
        raise ValueError('Remote changed after Git advertisement; preserve metadata and re-plan before checkout')
    git(root,'config','gc.auto','0')
    git(root,'config','maintenance.auto','false')
    from bulk_source import tracked_images
    images=tracked_images(root)
    if not images:raise ValueError('No committed PNGs in the advertised source')
    if shutil.disk_usage(parent).free<required:
        raise ValueError('Capacity changed during metadata clone; preserve metadata before hydration')
    marker=root/'.git/people-bulk-initialization.json'
    plan=dict(version=1,commit=advertised,tree=git(root,'rev-parse','HEAD^{tree}').decode().strip(),
        png_count=len(images),source_budget_gib=source_budget_gib,required_free_bytes=required,
        transport='native-git-partial-clone',rest_requests=0,checkout_complete=False)
    atomic_json(marker,plan)
    print(f'[SOURCE] Pinned {len(images)} PNG paths; downloading current committed payload',flush=True)
    git(root,'checkout','master',network=True)
    actual=sum(row['size'] for row in tracked_images(root))
    if actual>source_budget_gib*1024**3:
        raise ValueError('Checkout exceeds the approved source budget; retain all data and review capacity')
    atomic_json(marker,dict(plan,checkout_complete=True,source_bytes=actual))
    with source_lock(root):
        return dict(source_identity(root),initial_clone=dict(plan,checkout_complete=True,source_bytes=actual))


def synchronize(root,fetch_only=False):
    with source_lock(root):
        before=source_identity(root)
        old_remote=git(root,'rev-parse','refs/remotes/origin/master').decode().strip()
        # Explicit fetch may advance metadata while pins protect all source files.
        if git(root,'symbolic-ref','HEAD').decode().strip()!='refs/heads/master':
            raise ValueError('Source synchronization requires the master branch')
        git(root,'fetch','--refmap=','--no-tags','--filter=blob:none','origin','refs/heads/master',network=True)
        fetched=git(root,'rev-parse','FETCH_HEAD').decode().strip()
        git(root,'merge-base','--is-ancestor',old_remote,fetched)
        git(root,'merge-base','--is-ancestor',before['commit'],fetched)
        result=dict(previous=before['commit'],fetched=fetched,changes=changes(root,before['commit'],fetched),
                    source_files_updated=False,pins=pins(root))
        if fetch_only:
            result['deferred']=bool(result['pins'])
            return result
        if result['pins']:
            raise ValueError('Source revision is persistently pinned; fetch-only is available. Prepare a separately approved version before updating files')
        if source_identity(root)!=before:
            raise ValueError('Source changed during fetch')
        git(root,'merge','--ff-only',fetched,network=True)
        git(root,'update-ref','refs/remotes/origin/master',fetched,old_remote)
        after=source_identity(root)
        if after['commit']!=fetched:
            raise ValueError('Fast-forward did not reach verified source head')
        result['source_files_updated']=True
        return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['clone','sync','status','pin'])
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--confirmed-parent',type=Path)
    parser.add_argument('--fetch-only',action='store_true')
    parser.add_argument('--online',action='store_true')
    parser.add_argument('--batch-id')
    parser.add_argument('--audit-report',type=Path)
    parser.add_argument('--source-budget-gib',type=float,default=128,help='Conservative current-source ceiling for initial capacity admission; default 128 GiB, no REST API')
    args=parser.parse_args(argv)
    if args.command=='clone':
        if args.confirmed_parent is None:parser.error('clone requires --confirmed-parent after storage review')
        value=initial_clone(args.source,args.confirmed_parent,args.source_budget_gib)
    elif args.command=='sync':value=synchronize(args.source,args.fetch_only)
    elif args.command=='status':value=sync_status(args.source,args.online)
    else:
        if not args.batch_id or not args.audit_report:parser.error('pin requires --batch-id and --audit-report')
        value=pin_source(args.source,args.batch_id,args.audit_report)
    print(json.dumps(value,indent=2,ensure_ascii=True))
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,KeyError) as error:
        print('ERROR: '+str(error),file=sys.stderr);raise SystemExit(1)
