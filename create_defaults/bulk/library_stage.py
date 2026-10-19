"""Explicitly authorized, non-force draft-branch Git staging with exact recovery.

No command grants visual approval. The supplied authorization must bind an
approved publication plan; production master is checked and never updated.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from urllib.parse import quote

import requests

from .common import BulkError, confined, fingerprint, reject_links, sha256
from .library_publication import validate_paths, REVIEWERS
from .library_sources import check_seal, load_json, save, sealed

REPOSITORY = 'Kometa-Team/Default-Images'
REMOTE = 'https://github.com/'+REPOSITORY+'.git'


def git(repo, *args, data=None, timeout=180):
    result = subprocess.run(['git','-C',str(repo),*args],input=data,capture_output=True,timeout=timeout)
    if result.returncode:
        raise BulkError('git_failed',result.stderr.decode('utf-8',errors='replace')[-3000:])
    return result.stdout


def remote_head(repo, branch):
    output=git(repo,'ls-remote','origin','refs/heads/'+branch,timeout=90).decode().split()
    return output[0] if output else None


def gate(plan, authorization):
    check_seal(plan);check_seal(authorization)
    if (plan.get('kind')!='local-git-batch-plan' or authorization.get('kind')!='approved-draft-staging-authorization'
            or authorization.get('plan_sha256')!=plan['sha256']
            or authorization.get('baseline')!=plan['baseline']
            or authorization.get('publication_manifest_sha256')!=plan['publication_manifest_sha256']
            or not authorization.get('remote_writes_authorized')
            or not authorization.get('draft_only') or authorization.get('merge_authorized')
            or authorization.get('repository')!=REPOSITORY
            or not authorization.get('branch','').startswith('migration/english-python-group-a-')):
        raise BulkError('missing_authorization','Exact approved plan, draft branch and operation authorization required')
    members=[m for b in plan['batches'] for m in b['members']]
    validate_paths(members)
    receipt=check_seal(authorization.get('approval_receipt',{}))
    approved={m['destination']:(m['candidate_sha256'],m['published_sha256'],m['context_sha256']) for m in receipt.get('members',[])}
    actual={m['destination']:(m['sha256'],m['previous_sha256'],m['context_sha256']) for m in members}
    if (receipt.get('decision')!='approved' or receipt.get('reviewer') not in REVIEWERS
            or not receipt.get('policy_approved') or receipt.get('scope')!='renderer_equivalent'
            or receipt.get('candidate_manifest_sha256')!=authorization.get('candidate_manifest_sha256')
            or receipt.get('policy_sha256')!=authorization.get('policy_sha256')
            or receipt.get('baseline')!=plan['baseline'] or approved!=actual
            or receipt.get('membership_sha256')!=fingerprint(receipt.get('members'))):
        raise BulkError('missing_approval','Exact externally approved candidate membership required')
    if any(m['difference_class']!='renderer_equivalent' for m in members):
        raise BulkError('scope','Only exact approved renderer-equivalent members supported')
    for b in plan['batches']:
        if (fingerprint(b['members'])!=b['membership_sha256'] or len(b['members'])>plan['max_files']
                or sum(m['size'] for m in b['members'])!=b['bytes'] or b['bytes']>plan['max_bytes']):
            raise BulkError('corrupt_batch','Technical batch identity or cap differs')
    return members


def verify_diff(repo,before,after,members):
    """Complete raw Git diff, including old/new modes and both blob identities."""
    output=git(repo,'diff-tree','--no-commit-id','--raw','--no-abbrev','--no-renames','-r','-z',before,after).split(b'\0')
    actual={}
    for n in range(0,len(output)-1,2):
        mode1,mode2,old,new,status=output[n].decode().split()
        path=output[n+1].decode('utf-8')
        if (mode1,mode2,status)!=(':100644','100644','M'):
            raise BulkError('unexpected_diff','Only ordinary modified image files may change')
        actual[path]=(old,new)
    expected={m['destination']:(m['previous_git_blob'],m['git_blob']) for m in members}
    if actual!=expected:
        raise BulkError('unexpected_diff','Complete Git diff differs from approved image membership')
    content=git(repo,'cat-file','--batch',data=b''.join((after+':'+m['destination']+'\n').encode('utf-8') for m in members))
    offset=0;view=memoryview(content)
    for m in members:
        end=content.index(b'\n',offset);oid,kind,size=content[offset:end].decode().split();offset=end+1;size=int(size)
        if (oid!=m['git_blob'] or kind!='blob' or size!=m['size']
                or hashlib.sha256(view[offset:offset+size]).hexdigest()!=m['sha256']):
            raise BulkError('git_hash','Git commit bytes differ from the approved exact Python output')
        offset+=size+1
    if offset!=len(content):raise BulkError('git_hash','Unexpected extra Git object data')


def initialize(root,plan,auth,remote):
    work=root/'work'
    if work.exists():
        if (not (work/'.git').is_dir()
                or Path(git(work,'rev-parse','--absolute-git-dir').decode().strip()).resolve()!=work/'.git'
                or git(work,'remote','get-url','origin').decode().strip()!=remote):
            raise BulkError('unsafe_workspace','Owned Git workspace identity differs')
        return work
    subprocess.run(['git','init',str(work)],check=True,capture_output=True)
    for key,value in {'core.autocrlf':'false','core.filemode':'false','core.longpaths':'true',
        'core.hooksPath':str(root/'no-hooks'),'gc.auto':'0','maintenance.auto':'false',
        'pack.window':'0','pack.threads':'2','pack.compression':'1',
        'user.name':'Kometa approved poster migration','user.email':'bullmoose20@users.noreply.github.com'}.items():
        git(work,'config',key,value)
    git(work,'remote','add','origin',remote)
    if remote==REMOTE:
        git(work,'config','remote.origin.promisor','true')
        git(work,'config','remote.origin.partialclonefilter','blob:none')
        git(work,'fetch','--filter=blob:none','--depth=1','--no-tags','origin',plan['baseline']['head'],timeout=300)
    else:
        git(work,'fetch','--no-tags','origin',plan['baseline']['head'])
    git(work,'symbolic-ref','HEAD','refs/heads/'+auth['branch'])
    git(work,'update-ref','refs/heads/'+auth['branch'],plan['baseline']['head'])
    git(work,'read-tree','--reset',plan['baseline']['head'])
    # Preserve all untouched entries without downloading/materializing their blobs.
    paths=git(work,'ls-files','-z')
    git(work,'update-index','--skip-worktree','-z','--stdin',data=paths)
    (work/'.git/info/attributes').write_text('* -filter -text -ident\n',encoding='ascii')
    return work


def run(plan,authorization,root,*,test_remote=None,verify_remote=None,guard=None,stop_after=None,fail_at=None,prepare_only=False):
    """Resume known commit prefixes; ambiguous failures are reconciled, never forced.

    test_remote is restricted to an existing local bare repository and used by
    isolated regression tests. Production always uses the fixed repository URL.
    """
    members=gate(plan,authorization)
    for m in members:
        if sha256(reject_links(m['source']))!=m['sha256']:
            raise BulkError('candidate_drift','Exact candidate bytes changed before staging or resume')
    root=reject_links(root).resolve()
    remote=REMOTE
    if test_remote is not None:
        path=reject_links(test_remote).resolve()
        if not path.is_dir() or not authorization.get('test_only'):
            raise BulkError('test_remote','Local test authorization and existing repository required')
        remote=str(path)
    elif authorization.get('test_only'):
        raise BulkError('test_remote','Synthetic authorization cannot write GitHub')
    marker=root/'ownership.json'
    identity={'plan_sha256':plan['sha256'],'authorization_sha256':authorization['sha256'],'remote':remote}
    if root.exists() and not marker.exists():
        raise BulkError('unowned_workspace','Transport root exists without its exact ownership marker')
    if not root.exists():
        root.mkdir(parents=True)
        save(marker,identity)
    elif load_json(marker)!=identity:
        raise BulkError('stale_plan','Transport belongs to another exact approved plan')
    repo=initialize(root,plan,authorization,remote)
    branch=authorization['branch'];baseline=plan['baseline']['head']
    if remote_head(repo,'master')!=baseline:
        raise BulkError('baseline_drift','Production master changed before staging')
    journal_path=root/'journal.json'
    state=load_json(journal_path) if journal_path.exists() else dict(identity,batches=[],events=[],phase='idle')
    chain=git(repo,'rev-list','--reverse',baseline+'..HEAD').decode().splitlines()
    if len(chain)>len(plan['batches']):
        raise BulkError('unexpected_history','Local branch contains unrelated commits')
    previous=baseline
    for commit,batch in zip(chain,plan['batches']):
        if git(repo,'rev-parse',commit+'^').decode().strip()!=previous:
            raise BulkError('unexpected_history','Unexpected commit parent')
        verify_diff(repo,previous,commit,batch['members']);previous=commit
    if state.get('commits',[])!=chain[:len(state.get('commits',[]))]:
        raise BulkError('journal_drift','Recorded commits differ from the Git branch')
    dirty=git(repo,'status','--porcelain','-z').split(b'\0')
    allowed=({m['destination'] for m in plan['batches'][len(chain)]['members']}
        if len(chain)<len(plan['batches']) and state.get('phase')=='copying'
        and state.get('active_batch')==len(chain)+1 else set())
    if any(item and item[3:].decode('utf-8') not in allowed for item in dirty):
        raise BulkError('unexpected_worktree','Unrelated or unjournalled worktree changes')
    observed=remote_head(repo,branch)
    if observed not in [None,baseline,*chain]:
        raise BulkError('remote_drift','Destination branch contains an unrelated commit')
    if observed and not journal_path.exists():
        raise BulkError('unowned_remote','Existing remote branch has no local upload journal')
    started=time.monotonic()
    for n,batch in enumerate(plan['batches']):
        before=baseline if n==0 else chain[n-1]
        entry=state['batches'][n] if n<len(state['batches']) else {'sequence':n+1,'membership_sha256':batch['membership_sha256']}
        if len(state['batches'])<=n:state['batches'].append(entry)
        if guard:guard()
        if n>=len(chain):
            dirty=git(repo,'status','--porcelain','-z').split(b'\0')
            allowed={m['destination'] for m in batch['members']} if state.get('phase')=='copying' else set()
            if any(item and item[3:].decode('utf-8') not in allowed for item in dirty):
                raise BulkError('unexpected_worktree','Unrelated or unjournalled worktree changes')
            if shutil.disk_usage(root).free<8*1024**3+batch['bytes']*3:
                raise BulkError('disk_floor','Insufficient reserved disk space before batch')
            state.update(phase='copying',active_batch=n+1);save(journal_path,state)
            for m in batch['members']:
                source=reject_links(m['source'])
                if sha256(source)!=m['sha256'] or source.stat().st_size!=m['size']:
                    raise BulkError('candidate_drift','Approved Python bytes changed')
            sources=b''.join((Path(m['source']).as_posix()+'\n').encode('utf-8') for m in batch['members'])
            objects=git(repo,'hash-object','-w','--no-filters','--stdin-paths',data=sources).decode().splitlines()
            if objects!=[m['git_blob'] for m in batch['members']]:
                raise BulkError('copy_hash','Stored Git bytes differ from exact approved candidate blobs')
            # Index-only staging avoids a second full artwork worktree. Every
            # object is independently SHA-256 verified from the resulting commit.
            index=b''.join(('100644 '+m['git_blob']+'\t'+m['destination']).encode('utf-8')+b'\0' for m in batch['members'])
            git(repo,'update-index','-z','--index-info',data=index)
            paths=b''.join(m['destination'].encode('utf-8')+b'\0' for m in batch['members'])
            git(repo,'update-index','--skip-worktree','-z','--stdin',data=paths)
            git(repo,'commit','--quiet','-m',f"Approved English Python replacement batch {n+1}/{len(plan['batches'])}: {batch['membership_sha256']}")
            commit=git(repo,'rev-parse','HEAD').decode().strip();chain.append(commit)
            verify_diff(repo,before,commit,batch['members'])
            if fail_at=='after_commit':raise BulkError('injected_interruption','After commit before checkpoint')
        commit=chain[n];entry['commit']=commit
        measurement=root/'packs'/(commit+'.json');measurement.parent.mkdir(exist_ok=True)
        if measurement.exists():
            pack=check_seal(load_json(measurement))
            if pack['commit']!=commit or pack['before']!=before or pack['plan_sha256']!=plan['sha256']:
                raise BulkError('pack_drift','Measured pack belongs to another commit/plan')
        else:
            process=subprocess.Popen(['git','-C',str(repo),'pack-objects','--stdout','--revs','--window=0','--no-reuse-delta'],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            process.stdin.write((commit+'\n^'+before+'\n').encode());process.stdin.close()
            digest=hashlib.sha256();size=0
            while chunk:=process.stdout.read(1024*1024):
                size+=len(chunk);digest.update(chunk)
            error=process.stderr.read();code=process.wait(timeout=300)
            if code:raise BulkError('pack_failed',error.decode('utf-8',errors='replace')[-2000:])
            pack=sealed({'commit':commit,'before':before,'plan_sha256':plan['sha256'],
                'bytes':size,'sha256_pack_stream':digest.hexdigest(),'measurement':'complete_actual_git_pack_stream',
                'pack_window':0,'pack_compression':1})
            save(measurement,pack)
        entry.update(pack_bytes=pack['bytes'],pack_sha256=pack['sha256_pack_stream'],artifact_bytes=batch['bytes'])
        if entry['pack_bytes']>plan['max_pack_bytes']:
            raise BulkError('pack_limit','Measured incremental pack exceeds approved technical cap')
        state.update(commits=chain,phase='local_verified');save(journal_path,state)
        print(f"[BATCH {n+1}/{len(plan['batches'])}] {len(batch['members'])} images; pack {entry['pack_bytes']} bytes; local diff/hash verified",flush=True)
        if prepare_only:
            entry['state']='local_verified';state['phase']='prepared';save(journal_path,state)
            if stop_after and n+1>=stop_after:break
            continue
        observed=remote_head(repo,branch)
        target_index=chain.index(observed) if observed in chain else -1
        if observed not in [None,baseline,*chain]:raise BulkError('remote_drift','Remote changed during staging')
        if target_index<n:
            if remote_head(repo,'master')!=baseline:raise BulkError('baseline_drift','Production master moved')
            push_started=time.monotonic()
            for attempt in range(3):
                try:
                    git(repo,'push','--porcelain','origin',commit+':refs/heads/'+branch,timeout=1200)
                    break
                except BulkError as error:
                    after=remote_head(repo,branch)
                    state['events'].append({'batch':n+1,'event':'ambiguous_push','remote_head':after,'error':str(error)})
                    save(journal_path,state)
                    if after==commit:break
                    if after not in [None,before] or attempt==2:raise
                    time.sleep(2**attempt)
            entry['push_seconds']=time.monotonic()-push_started
            if remote_head(repo,branch)!=commit:raise BulkError('remote_drift','Push was not reconciled to intended commit')
            if fail_at=='after_push':raise BulkError('injected_interruption','After push before checkpoint')
        state['phase']='pushed_pending_hash_verification';save(journal_path,state)
        verify_started=time.monotonic()
        if verify_remote:verify_remote(commit,batch['members'])
        elif test_remote is not None:verify_diff(Path(test_remote),before,commit,batch['members'])
        else:raise BulkError('verification_required','Actual remote byte verification adapter required')
        entry.update(remote_hash_verified=len(batch['members']),verification_seconds=time.monotonic()-verify_started,state='remote_verified')
        state.update(phase='idle');save(journal_path,state)
        print(f"[BATCH {n+1}] remote commit and all {len(batch['members'])} actual image hashes verified",flush=True)
        if stop_after and n+1>=stop_after:break
    complete=len(state['batches'])==len(plan['batches']) and all(b.get('state')=='remote_verified' for b in state['batches'])
    report=sealed({'plan_sha256':plan['sha256'],'authorization_sha256':authorization['sha256'],
        'complete':complete,'branch':branch,'baseline':baseline,'head':chain[-1] if chain else baseline,
        'batches':state['batches'],'events':state['events'],
        'network_artwork_push_batches':sum('push_seconds' in b for b in state['batches']) if test_remote is None else 0,
        'elapsed_seconds':time.monotonic()-started,'master_unchanged':remote_head(repo,'master')==baseline})
    save(root/'transport-report.json',report)
    return report


class RemoteBytes:
    """Stream actual pinned raw responses; cache only sealed successful downloads."""
    def __init__(self,root,plan):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.plan=plan;self.local=threading.local()

    def one(self,commit,m):
        cache=self.root/(fingerprint([m['destination'],m['git_blob']])+'.json')
        if cache.exists():
            value=check_seal(load_json(cache))
            if (value['plan_sha256']!=self.plan['sha256'] or value['actual_sha256']!=m['sha256']
                    or value['actual_git_blob']!=m['git_blob'] or value['bytes']!=m['size']
                    or value['destination']!=m['destination']):
                raise BulkError('verification_cache_drift','Actual-response receipt differs from approved bytes')
            return value
        if not hasattr(self.local,'session'):
            self.local.session=requests.Session();self.local.session.trust_env=False
        url='https://raw.githubusercontent.com/'+REPOSITORY+'/'+commit+'/'+quote(m['destination'],safe='/')
        for attempt in range(5):
            try:
                digest=hashlib.sha256();blob=hashlib.sha1(f"blob {m['size']}\0".encode());size=0
                with self.local.session.get(url,stream=True,timeout=(15,90),allow_redirects=False) as response:
                    response.raise_for_status()
                    for chunk in response.iter_content(128*1024):
                        size+=len(chunk)
                        if size>m['size']:raise BulkError('remote_hash','Actual remote file exceeds exact approved size')
                        digest.update(chunk);blob.update(chunk)
                if size!=m['size'] or digest.hexdigest()!=m['sha256'] or blob.hexdigest()!=m['git_blob']:
                    raise BulkError('remote_hash','Actual downloaded remote bytes differ from approved Python output')
                value=sealed({'plan_sha256':self.plan['sha256'],'destination':m['destination'],
                    'commit_at_actual_download':commit,'url':url,'actual_sha256':digest.hexdigest(),
                    'actual_git_blob':blob.hexdigest(),'bytes':size,
                    'checked_utc':datetime.now(timezone.utc).isoformat(),'provenance':'actual_pinned_raw_remote_response'})
                save(cache,value);return value
            except requests.RequestException:
                if attempt==4:raise
                time.sleep(2**attempt)

    def __call__(self,commit,members):
        with ThreadPoolExecutor(max_workers=8) as pool:
            for n,_ in enumerate(pool.map(lambda m:self.one(commit,m),members),1):
                if n%75==0:print(f'[REMOTE BYTES] {n}/{len(members)} actual SHA-256 verified',flush=True)


def final_remote_diff(root,plan,auth,report):
    from .remote import ReadOnlyGitHub
    token=subprocess.check_output(['gh','auth','token'],text=True).strip()
    client=ReadOnlyGitHub(REPOSITORY,token=token)
    head,tree=client.head(auth['branch'])
    if head!=report['head'] or client.head('master')[0]!=plan['baseline']['head']:
        raise BulkError('remote_drift','Remote head/master changed before complete diff verification')
    actual=client.tree(tree,recursive=True)
    if actual['truncated']:raise BulkError('incomplete_remote_tree','Complete remote tree required')
    before=check_seal(load_json(Path(root)/'production-snapshot.json'))
    original={e['path']:(e['sha'],e['mode'],e['type']) for e in before['entries'] if e['type']!='tree'}
    after={e['path']:(e['sha'],e['mode'],e['type']) for e in actual['tree'] if e['type']!='tree'}
    members=[m for b in plan['batches'] for m in b['members']]
    expected=dict(original)
    for m in members:expected[m['destination']]=(m['git_blob'],'100644','blob')
    if after!=expected:raise BulkError('unexpected_remote_diff','Complete remote file tree differs from approved modifications')
    changes={p for p in after if after[p]!=original[p]}
    if changes!={m['destination'] for m in members}:raise BulkError('unexpected_remote_diff','Modified file count/membership differs')
    if client.head(auth['branch'])!=(head,tree):raise BulkError('remote_drift','Remote moved during tree audit')
    result=sealed({'baseline':plan['baseline'],'head':head,'tree':tree,'modified':len(changes),
        'additions':0,'deletions':0,'renames':0,'unexpected_paths':[],
        'all_remote_blob_identities_match':True,'actual_response_hash_receipts':len(members)})
    save(Path(root)/'complete-remote-diff.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--execution-version',choices=['v1','v2','v3'],default='v1')
    p.add_argument('--stop-after',type=int)
    args=p.parse_args();root=reject_links(args.root).resolve()
    plan=check_seal(load_json(root/'approved-git-batch-plan.json'))
    suffix='' if args.execution_version=='v1' else '-'+args.execution_version
    auth=check_seal(load_json(root/('draft-staging-authorization'+suffix+'.json')))
    # Fresh source sentinel was created by the final verified publication preflight.
    sentinel=check_seal(load_json(root/('source-sentinel'+suffix+'.json')))
    if sentinel['sha256']!=auth['source_sentinel_sha256']:
        raise BulkError('source_drift','Final publication preflight sentinel differs')
    def guard():
        for item in sentinel['files']:
            path=reject_links(item['path']);stat=path.stat()
            if stat.st_size!=item['size'] or stat.st_mtime_ns!=item['mtime_ns']:
                raise BulkError('source_drift','Source/native/font identity changed during staging: '+item['path'])
    verifier=RemoteBytes(root/'actual-remote-verification',plan)
    result=run(plan,auth,root/('transport'+suffix),verify_remote=verifier,guard=guard,
        prepare_only=args.prepare_only,stop_after=args.stop_after)
    if result['complete']:final_remote_diff(root,plan,auth,result)
    print(json.dumps({'complete':result['complete'],'head':result['head'],'batches':len(result['batches'])}))


if __name__=='__main__':main()
