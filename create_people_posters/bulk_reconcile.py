"""Read-only publication plans and separately authorized private payload staging.

There is deliberately no commit, push, production replacement, or cleanup mode.
History checks retain the reviewed V2 rule: a reverted change still counts.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
import time

from bulk_source import SOURCE_URL, changes, git, path_key
from bulk_regeneration_state import (STYLES, STATE, MARKER, canonical, database, read_inventory,
    read_json, reject_links, sha, atomic_json, sync_parent, writer_lock)


def pack(rows):
    return dict(count=len(rows),chunks=[rows[n:n+2048] for n in range(0,len(rows),2048)])


def unpack(value):
    rows=[row for chunk in value['chunks'] for row in chunk]
    if len(rows)!=value['count'] or any(len(chunk)>2048 for chunk in value['chunks']):
        raise ValueError('Incomplete bounded inventory')
    return rows


def verify_cache(root,url):
    root=Path(root).resolve();reject_links(root)
    if git(root,'remote','get-url','origin').decode().strip() not in {url,url.removesuffix('.git')}:
        raise ValueError('Unexpected repository origin')
    git(root,'rev-parse','--git-dir')
    return root


def tree(root,ref):
    result={}
    for record in git(root,'ls-tree','-r','-z',ref).split(b'\0'):
        if not record:continue
        attributes,path=record.split(b'\t',1);mode,kind,oid=attributes.split()
        path=path.decode('utf8');path_key(path)
        if kind!=b'blob':
            raise ValueError('Unexpected submodule/tree leaf in publication repository')
        result[path]=dict(mode=mode.decode(),oid=oid.decode())
    return result


def observe(root):
    git(root,'fetch','--refmap=','--filter=blob:none','--no-tags','origin','refs/heads/master',network=True)
    return git(root,'rev-parse','FETCH_HEAD').decode().strip()


def history(root,baseline,latest):
    git(root,'merge-base','--is-ancestor',baseline,latest)
    commits=git(root,'rev-list','--topo-order',baseline+'..'+latest).decode().split()
    if len(commits)>20000:
        raise ValueError('History interval exceeds the review bound; do not truncate it')
    result=[]
    for commit in commits:
        paths=[p.decode('utf8') for p in git(root,'diff-tree','--root','--no-commit-id',
            '--name-only','-r','-m','-z',commit).split(b'\0') if p]
        for path in paths:path_key(path)
        result.append(dict(commit=commit,paths=sorted(set(paths))))
    return result


def image_path(path):
    parts=PurePosixPath(path).parts
    return len(parts)==3 and parts[1]=='Images' and parts[2].lower().endswith('.jpg')


def capture_baseline(destination,style,source_commit,renderer_id):
    if style not in STYLES:raise ValueError('Unknown style')
    root=verify_cache(destination,'https://github.com/Kometa-Team/People-Images-'+style+'.git')
    head=observe(root)
    value=dict(version=1,style=style,repository='Kometa-Team/People-Images-'+style,
        destination_head=head,source_commit=source_commit,renderer_id=renderer_id,
        entries=pack([dict(path=p,**e) for p,e in sorted(tree(root,head).items())]),created=time.time())
    value['baseline_sha256']=canonical(value)
    return value


def checked(value,key):
    value=dict(value);expected=value.pop(key)
    if canonical(value)!=expected:raise ValueError('Review document digest mismatch')
    return dict(value,**{key:expected})


def reconcile(batch,source_cache,destination,baseline,fetch=True):
    from bulk_regenerate import validated_receipt
    from create_people_poster import output_path
    batch=Path(batch).resolve();reject_links(batch)
    baseline=checked(baseline,'baseline_sha256');style=baseline['style']
    if style not in STYLES:raise ValueError('Unsupported publication style')
    with closing(database(batch,readonly=True)) as db:
        db.execute('BEGIN')
        stored=db.execute("SELECT value FROM meta WHERE key='manifest'").fetchone()
        manifest=json.loads(stored[0])
        meta={r[0]:json.loads(r[1]) for r in db.execute("SELECT key,value FROM meta WHERE key IN ('state','manifest_hash')")}
        totals=dict(db.execute('SELECT status,count(*) FROM outputs WHERE style=? GROUP BY status',(style,)))
    if (manifest.get('managed_by')!=MARKER or manifest['output']!=str(batch) or style not in manifest['styles']
            or meta['manifest_hash']!=canonical(manifest) or meta['state']!='completed'):
        raise ValueError('Batch/style identity mismatch')
    from bulk_regeneration_plan import renderer_version
    if manifest['renderer']!=renderer_version():
        raise ValueError('Frozen renderer/workflow differs from the current runtime')
    if totals.get('completed',0)!=manifest['inventory']['selected_input_total'] or any(n for status,n in totals.items() if status!='completed'):
        raise ValueError('All selected style outputs must be verified complete before reconciliation')
    renderer_id=canonical(manifest['renderer'])
    if baseline['source_commit']!=manifest['source_git']['head'] or baseline['renderer_id']!=renderer_id:
        raise ValueError('Baseline does not bind this batch source/renderer')
    source=verify_cache(source_cache,SOURCE_URL)
    destination=verify_cache(destination,'https://github.com/'+baseline['repository']+'.git')
    latest_source=observe(source) if fetch else git(source,'rev-parse','refs/remotes/origin/master').decode().strip()
    latest_dest=observe(destination) if fetch else git(destination,'rev-parse','refs/remotes/origin/master').decode().strip()
    original={r['path']:dict(mode=r['mode'],oid=r['oid']) for r in unpack(baseline['entries'])}
    if original!=tree(destination,baseline['destination_head']):
        raise ValueError('Baseline tree inventory mismatch')
    source_history=history(source,baseline['source_commit'],latest_source)
    dest_history=history(destination,baseline['destination_head'],latest_dest)
    touched_source={path for entry in source_history for path in entry['paths'] if path.lower().endswith('.png')}
    touched_dest={path for entry in dest_history for path in entry['paths'] if image_path(path)}
    readmes={path for path in original if PurePosixPath(path).name=='README.md'}
    blockers=[]
    for entry in dest_history:
        unknown=set(entry['paths'])-{p for p in entry['paths'] if image_path(p)}-readmes
        if unknown:blockers.append(dict(reason='unapproved_destination_history_paths',**entry))
        if set(entry['paths'])&readmes and set(entry['paths'])-readmes:
            blockers.append(dict(reason='mixed_metadata_image_commit_requires_review',**entry))
    current=tree(destination,latest_dest)
    keys={}
    for path in current:
        key=path_key(path)
        if key in keys and keys[key]!=path:
            blockers.append(dict(reason='destination_unicode_case_collision',paths=[keys[key],path]))
        keys[key]=path
        if image_path(path) and current[path]['mode']!='100644':
            blockers.append(dict(reason='unsupported_destination_image_mode',paths=[path]))
    rows=read_inventory(batch)
    if canonical(rows)!=manifest['inventory_sha256']:raise ValueError('Frozen batch inventory changed')
    files=[];excluded=[]
    for item in rows:
        if not item['selected']:continue
        receipt=validated_receipt(batch,item,style,renderer_id,manifest['batch_id'])
        if receipt is None:raise ValueError('Staged receipt no longer verifies: '+item['relative'])
        output=output_path(batch,style,item['name']).relative_to(batch/style).as_posix()
        row=dict(path=output,stage=receipt['output'],source=item['relative'],source_sha256=item['source_hash'],
                 output_sha256=receipt['sha256'],bytes=receipt['bytes'],previous=current.get(output))
        reasons=[]
        if item['relative'] in touched_source:reasons.append('source_history_changed_since_pin')
        if output in touched_dest:reasons.append('destination_history_changed_since_baseline')
        if path_key(output) in keys and keys[path_key(output)]!=output:reasons.append('destination_casing_conflict')
        if reasons:excluded.append(dict(row,reasons=reasons))
        else:files.append(row)
    result=dict(version=1,batch_id=manifest['batch_id'],style=style,batch=str(batch),
        baseline_sha256=baseline['baseline_sha256'],renderer_id=renderer_id,
        source_baseline=baseline['source_commit'],source_head=latest_source,destination_baseline=baseline['destination_head'],
        destination_head=latest_dest,source_cache=str(source),destination_cache=str(destination),
        source_changes=pack(changes(source,baseline['source_commit'],latest_source)),
        source_history=pack(source_history),destination_history=pack(dest_history),
        files=pack(files),excluded=pack(excluded),blockers=pack(blockers),
        publication_authorized=False,baseline_refresh_required=bool(excluded or blockers),created=time.time())
    result['plan_sha256']=canonical(result)
    return result


def stage_payload(plan,destination,authorization):
    """Only a NEW private payload workspace is written; repositories stay untouched."""
    plan=checked(plan,'plan_sha256')
    if authorization!='STAGE:'+plan['plan_sha256']:
        raise ValueError('Exact-plan staging authorization required')
    if plan['baseline_refresh_required']:
        raise ValueError('Conflicts/history require separate approval and a new reviewed baseline/plan')
    target=Path(destination).absolute();batch=Path(plan['batch']).resolve()
    reject_links(target)
    for parent in (target,*target.parents):
        if (parent/'.git').exists():raise ValueError('Private payload must be outside every Git repository')
    for protected in (batch,Path(plan['source_cache']).resolve(),Path(plan['destination_cache']).resolve()):
        if protected==target.resolve() or protected in target.resolve().parents or target.resolve() in protected.parents:
            raise ValueError('Private payload must be disjoint from repositories and render batch')
    for root,key in ((plan['source_cache'],'source_head'),(plan['destination_cache'],'destination_head')):
        head=git(root,'ls-remote','--exit-code','origin','refs/heads/master',network=True).decode().split()[0]
        if head!=plan[key]:raise ValueError('Remote advanced; produce a new reconciliation plan')
    files=unpack(plan['files'])
    for row in files:
        path_key(row['path']);path_key(row['stage'])
        if row['stage']!=plan['style']+'/'+row['path']:
            raise ValueError('Payload row escaped its approved style')
    ancestor=target
    while not ancestor.exists():ancestor=ancestor.parent
    if shutil.disk_usage(ancestor).free<sum(row['bytes'] for row in files)+2*1024**3:
        raise ValueError('Insufficient capacity for private payload and reserve')
    target.mkdir(parents=True,exist_ok=True)
    (target/'.bulk').mkdir(exist_ok=True)
    with writer_lock(target):
        marker=target/'PLAN.json'
        if marker.exists():
            if read_json(marker)!=plan:raise ValueError('Existing payload belongs to a different plan')
        elif any(p.name!='.bulk' for p in target.iterdir()):raise ValueError('Private payload directory is not empty')
        else:atomic_json(marker,plan)
        for row in files:
            source=batch/row['stage'];path=target/'posters'/row['path'];reject_links(source);reject_links(path)
            if sha(source)!=row['output_sha256']:raise ValueError('Staged JPEG changed')
            if path.exists():
                if sha(path)!=row['output_sha256']:raise ValueError('Unknown bytes in private payload; preserve them')
                continue
            path.parent.mkdir(parents=True,exist_ok=True)
            temporary=None
            try:
                with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.payload-',delete=False) as stream:
                    temporary=Path(stream.name)
                    with source.open('rb') as image:shutil.copyfileobj(image,stream)
                    stream.flush();os.fsync(stream.fileno())
                if sha(temporary)!=row['output_sha256']:raise ValueError('Payload copy hash mismatch')
                os.replace(temporary,path);sync_parent(path)
            finally:
                if temporary is not None:temporary.unlink(missing_ok=True)
        atomic_json(target/'READY.json',dict(plan_sha256=plan['plan_sha256'],files=len(files),
            publication_authorized=False,production_files_modified=0))
    return dict(files=len(files),payload=str(target),publication_authorized=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['baseline','plan','stage'])
    parser.add_argument('--style',choices=STYLES)
    parser.add_argument('--source-commit')
    parser.add_argument('--renderer-id')
    parser.add_argument('--batch',type=Path)
    parser.add_argument('--source-cache',type=Path)
    parser.add_argument('--destination-cache',type=Path)
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--plan',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--authorize')
    args=parser.parse_args(argv)
    if args.command=='baseline':
        if not all((args.style,args.destination_cache,args.source_commit,args.renderer_id)):parser.error('baseline needs style, destination cache, source commit and renderer id')
        value=capture_baseline(args.destination_cache,args.style,args.source_commit,args.renderer_id)
    elif args.command=='plan':
        if not all((args.batch,args.source_cache,args.destination_cache,args.baseline)):parser.error('plan needs batch, source/destination caches and baseline')
        value=reconcile(args.batch,args.source_cache,args.destination_cache,read_json(args.baseline))
    else:
        if not args.plan:parser.error('stage needs --plan')
        print(json.dumps(stage_payload(read_json(args.plan),args.output,args.authorize),indent=2));return 0
    reject_links(args.output)
    for protected in (args.batch,args.source_cache,args.destination_cache):
        if protected is not None and (args.output.resolve()==protected.resolve() or protected.resolve() in args.output.resolve().parents):
            raise ValueError('Review reports must be outside repositories and render staging')
    if args.output.exists():raise ValueError('Report already exists; preserve reviewed evidence')
    atomic_json(args.output,value)
    print(json.dumps({k:v for k,v in value.items() if k not in {'entries','files','excluded','source_history','destination_history','source_changes','blockers'}},indent=2))
    return 2 if value.get('baseline_refresh_required') else 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,KeyError) as error:
        print('ERROR: '+str(error),file=sys.stderr);raise SystemExit(1)
