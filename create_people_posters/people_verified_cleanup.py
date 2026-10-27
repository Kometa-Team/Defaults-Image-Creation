"""Exact approved artwork cleanup and conservative existing-job payload compaction.

No rendering, publication, model eviction, failed-job expiry or new database.
Dry-run is read-only. Apply needs hosted CI proof, shared leases and a matching
fresh plan. Scheduling is deliberately an operator-reviewed step.
"""
from __future__ import annotations
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

# Existing People CLIs use sibling imports; bind them to this reviewed checkout.
SCRIPT_DIR=Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:sys.path.insert(0,str(SCRIPT_DIR))

from create_people_posters.people_github import REPOSITORIES
from create_people_posters.people_retention_remote import ReadOnlyGitHub, exact_entry
from create_people_posters.people_retention_state import (RetentionBlocked, Journal,
    atomic_json, fingerprint, inspect, journal_members, member, processing_exclusion,
    read_json, readonly_db, unlink_verified)
from create_people_posters.people_workspaces import reject_links

APPROVAL = 'a3e61e6b763e154b2d7575cdd12588425847187c709c0be64edc6b446d35cd43'
FONT = '564a838df86d075f9ab39e0d1f4cfe4ef90791388988dc8b5fc732f75d1ef8f5'
REVIEW = '7599c4a55ead56cd035c3f735c5106ea7e8c6a56c38e8504dcf8a08882a0f019'
IMAGE = {'.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff'}
SUCCESS = {'published','cleanup_eligible'}


def approved_plan(path):
    value=read_json(path)
    raw={k:v for k,v in value.items() if k!='sha256'}
    if value.get('sha256')!=APPROVAL or fingerprint(raw)!=APPROVAL:
        raise RetentionBlocked('Approval inventory changed; do not expand scope')
    names=[r['path'] for r in value['files']]
    if len(names)!=len(set(names)):
        raise RetentionBlocked('Duplicate approved member')
    return value


def ledger(config):
    with closing(readonly_db(config/'state/publication_state.db')) as db:
        jobs={r['id']:dict(r) for r in db.execute('SELECT * FROM jobs')}
        publications=[dict(r) for r in db.execute('SELECT * FROM publications')]
        batches={r['id']:dict(r) for r in db.execute('SELECT * FROM batches')}
        readmes=[dict(r) for r in db.execute('SELECT * FROM readmes')]
    return dict(jobs=jobs,publications=publications,batches=batches,readmes=readmes)


def job_proof(config, job, state, snapshot, now, retention):
    row=state['jobs'].get(job)
    if not row or row['status'] not in SUCCESS or row['published'] is None:
        return None,'not_successfully_published'
    if (config/'jobs'/job/'.active').exists():return None,'active_job'
    if now-row['published']<max(3,retention)*86400:return None,'three_day_window_open'
    manifest=read_json(config/'jobs'/job/'manifest.json')
    if manifest.get('id')!=job or manifest.get('managed_by')!='kometa-people-v1':
        raise RetentionBlocked('Job ownership mismatch')
    expected=state['batches'].get(job,{}).get('expected',0)
    rows=[r for r in state['publications'] if r['batch']==job]
    readmes=[r['status'] for r in state['readmes'] if r['batch']==job]
    if (not expected or len(rows)!=expected or not readmes
            or any(s not in {'dispatched','disabled','warning','unchanged'} for s in readmes)):
        raise RetentionBlocked('Incomplete successful-job publication grant')
    proof=[]
    people={}
    for r in rows:
        if (r['status']!='published' or not r['commit_sha'] or r['branch']!='master'
                or REPOSITORIES.get(r['style'])!=r['repo']):
            raise RetentionBlocked('Unfulfilled or unauthorized publication receipt')
        proof.append(exact_entry(snapshot,r['repo'],r['path'],r['blob']))
        styles=people.setdefault(r['person'],set())
        if r['style'] in styles:raise RetentionBlocked('Duplicate person/style receipt')
        styles.add(r['style'])
        for key,digest in [('source','source_hash'),('prepared','published_hash')]:
            p=Path(r[key])
            if not p.is_absolute() or not p.resolve().is_relative_to((config/'jobs'/job).resolve()):
                raise RetentionBlocked('Publication source ownership uncertain')
            if p.exists() and inspect(p)['sha256']!=r[digest]:
                raise RetentionBlocked('Publication source/prepared bytes changed')
    if any(styles!=set(REPOSITORIES) for styles in people.values()):
        raise RetentionBlocked('Incomplete seven-style publication cohort')
    if not isinstance(manifest.get('cleanup_files'),dict):
        raise RetentionBlocked('Successful job has no exact cleanup catalog')
    return dict(manifest=manifest,receipts=proof,rows=rows),None


def protected_references(config, state, *, for_jobs=False):
    """Read current operation references; fulfilled historical receipts aren't leases."""
    protected=set(); metadata=[]
    prefix=str(config).replace('\\','/').casefold()+'/'
    def visit(value):
        if isinstance(value,dict):
            for k,v in value.items():visit(k);visit(v)
        elif isinstance(value,list):
            for v in value:visit(v)
        elif isinstance(value,str):
            v=value.replace('\\','/').casefold()
            if v.startswith(prefix):protected.add(v[len(prefix):].rstrip('/'))
    for root in [config/'jobs',config/'state',config/'.orch',config/'edge_chop_recovery']:
        if not root.exists():continue
        for folder,dirs,names in os.walk(root,followlinks=False):
            for name in dirs+names:reject_links(Path(folder)/name)
            for name in names:
                p=Path(folder)/name
                rel=p.relative_to(config).as_posix()
                parts=rel.split('/')
                jid=parts[1] if parts[0]=='jobs' and len(parts)>2 else None
                if name in {'.active','run.lock'} or name.endswith('.pending.json'):
                    if for_jobs and jid:
                        protected.add(('jobs/'+jid).casefold())
                        continue
                    raise RetentionBlocked('Active/pending operation; retain artwork')
                if p.suffix.lower()!='.json' or 'verified-retention' in p.parts:continue
                if p.stat().st_size>32*1024*1024:
                    raise RetentionBlocked('Operational metadata exceeds read budget')
                value=read_json(p);metadata.append((rel,inspect(p)['sha256']))
                status=state['jobs'].get(jid,{}).get('status')
                if name=='recovery-checkpoints.json':
                    for record in value.get('records',{}).values():
                        for output in record.get('outputs',{}):
                            protected.add(('jobs/'+jid+'/people_dirs/'+output).casefold() if jid else ('people_dirs/'+output).casefold())
                    visit(value)
                elif name=='transaction.json':visit(value)
                elif jid and status not in SUCCESS|{'complete','no_work'}:visit(value)
                elif parts[0]=='state' and 'manifests' in parts:
                    for receipt in value.get('publications',[]):
                        if receipt.get('status')!='published':visit(receipt)
                elif parts[0] in {'.orch','edge_chop_recovery'} and not name.endswith('.done.json'):
                    visit(value)
    # Publication database source paths are active dependencies until fulfilled.
    for receipt in state['publications']:
        if receipt['status']!='published':visit(receipt)
    return protected,fingerprint(dict(metadata=sorted(metadata),ledger=state))


def jost_proof(config, approval, snapshot):
    value=approval['font_replacement_proof']
    if value['approved_font_sha256']!=FONT or value['saved_visual_review_sha256']!=REVIEW:
        raise RetentionBlocked('Unexpected font replacement approval')
    result={}
    for record in value['manifests']:
        path=member(config,record['manifest']);manifest=read_json(path)
        if manifest['font_hash']!=FONT:raise RetentionBlocked('Jost manifest font changed')
        dbpath=path.parents[2]/'state/publication_state.db'
        with closing(readonly_db(dbpath)) as db:
            expected=db.execute('SELECT manifest_hash FROM jost_runs WHERE id=?',(manifest['id'],)).fetchone()
            if not expected or expected[0]!=__import__('hashlib').sha256(json.dumps(manifest,sort_keys=True,ensure_ascii=False).encode()).hexdigest():
                raise RetentionBlocked('Jost manifest provenance changed')
            for r in db.execute("SELECT * FROM publications WHERE status='published'"):
                if r['commit_sha'] and r['branch']=='master':
                    result[(r['repo'],r['path'],r['blob'],r['published_hash'],r['commit_sha'])]=dict(r)
    rollout=read_json(config/'migrations/jost/state/rollout.json')
    review=member(config,'migrations/jost/reports/'+rollout['approved_sample']+'/review.json')
    if inspect(review)['sha256']!=REVIEW or rollout['review_sha256']!=REVIEW:
        raise RetentionBlocked('Approved Jost visual review changed')
    return result


def protected_path(row, protected):
    p=row['path'].casefold()
    return any(p==r or p.startswith(r+'/') for r in protected)


def build_plan(config, approval, remote, *, now=None):
    config=Path(config).absolute();reject_links(config)
    now=time.time() if now is None else now
    lease=config/'state/orchestrator.lock'
    if lease.exists() and not lease.read_text(encoding='ascii').startswith(str(os.getpid())+' @ '):
        raise RetentionBlocked('Processing lease present; dry-run/apply retained')
    for root in (config/'migrations').glob('*/state'):
        if any(root.glob('*.lock')):raise RetentionBlocked('Migration lease present; retained')
    snapshot=remote.snapshot();state=ledger(config)
    protected,reference_hash=protected_references(config,state)
    migration=jost_proof(config,approval,snapshot)
    prior=journal_members(config/'state/verified-retention',APPROVAL,config)
    eligible=[];skipped=[];identities={}
    expected_paths={r['path'] for r in approval['files']}
    # An unexplained member in an audited tree is a mismatch, never a new target.
    for root in [config/'people_dirs']+[config/'jobs'/r['job'] for r in approval['files'] if r['scope']=='job']:
        if str(root) in identities:continue
        identities[str(root)]=True
        for folder,dirs,names in os.walk(root,followlinks=False):
            for name in dirs+names:reject_links(Path(folder)/name)
            for name in names:
                rel=(Path(folder)/name).relative_to(config).as_posix()
                if rel not in expected_paths:raise RetentionBlocked('Unexpected path inside approved tree')
    identities={}
    proof_by_job={}
    retention=float(os.getenv('PEOPLE_BATCH_RETENTION_DAYS','3'))
    if retention<3:retention=3
    for row in approval['files']:
        path=member(config,row['path']);old=prior.get(row['path'])
        if not path.exists():
            if old and old['sha256']==row['sha256'] and old['bytes']==row['bytes']:
                skipped.append(dict(path=row['path'],bytes=row['bytes'],reason='already_receipted',state=old['state']))
                continue
            raise RetentionBlocked('Approved file unexpectedly missing')
        if old and old['state'] in {'deleted','missing_after_intent'}:
            raise RetentionBlocked('Deleted file reappeared; review required')
        identity=inspect(path);identities[row['path']]=identity
        if any(identity[k]!=row[k] for k in ('bytes','sha256','git_blob')):
            raise RetentionBlocked('Approved local file bytes changed: '+row['path'])
        if not row['disposition'].startswith('candidate'):
            skipped.append(dict(path=row['path'],bytes=row['bytes'],reason=row['reason']));continue
        if row['scope']=='job':
            if row['job'] not in proof_by_job:
                proof_by_job[row['job']]=job_proof(config,row['job'],state,snapshot,now,retention)
            job,reason=proof_by_job[row['job']]
            if reason:
                skipped.append(dict(path=row['path'],bytes=row['bytes'],reason=reason));continue
            # Preserve rollback, all raw/source-history copies and checkpoints.
            if (row['role'] in {'rollback_artifact','original_archive_or_original_output','preserved_source_history','downloaded_input_or_intermediate'}
                    or '/transactions/' in row['path'] or protected_path(row,protected)):
                skipped.append(dict(path=row['path'],bytes=row['bytes'],reason='protected_source_checkpoint_or_rollback'));continue
            relative=path.relative_to(config/'jobs'/row['job']).as_posix()
            if job['manifest']['cleanup_files'].get(relative)!=row['sha256']:
                raise RetentionBlocked('Successful payload differs from owned cleanup catalog')
            proof=dict(kind='existing_successful_job_receipts',receipts=job['receipts'])
        else:
            if protected_path(row,protected):
                raise RetentionBlocked('Approved persistent image now required by an operation')
            if row['reason']=='exact_published_copy':
                proof=exact_entry(snapshot,REPOSITORIES[row['style']],row['remote_path'],row['git_blob'],row['bytes'])
                proof['kind']='approved_legacy_adoption_current_github_commit_tree_blob'
            elif row['reason']=='explicit_expected_font_supersession':
                replacement=row['replacement']
                key=tuple(replacement[k] for k in ('repo','path','blob','sha256','commit'))
                if key not in migration:raise RetentionBlocked('Authoritative Jost publication receipt missing')
                proof=exact_entry(snapshot,replacement['repo'],replacement['path'],replacement['blob'])
                proof.update(kind='approved_jost_successor_receipt',receipt_commit=replacement['commit'],font_sha256=FONT,review_sha256=REVIEW)
            else:raise RetentionBlocked('Unapproved persistent deletion reason')
        eligible.append(dict(row,identity=identity,proof=proof))
    remote.confirm(snapshot)
    report=dict(version=1,approval=APPROVAL,root=str(config),eligible=eligible,skipped=skipped,
        snapshot_heads={repo:data['head'] for repo,data in snapshot.items()},references=reference_hash)
    report['plan_digest']=fingerprint(report)
    report.update(generated_utc=datetime.now(timezone.utc).isoformat(),eligible_files=len(eligible),
        eligible_bytes=sum(r['bytes'] for r in eligible),deletion_authorized_by_dry_run=False)
    return report,snapshot


MANAGED_SCOPE='managed-jobs-v1'
ORDINARY_LOGS=frozenset({'tmdb_people.log','recover_edge_chops.log',
    'create_people_poster.log','colorize_noncolor_ddcolor.log','tmdb_top_people_list.log'})
LOG_BYTES=5*1024*1024


def build_jobs_plan(config, remote=None, *, now=None):
    """Derive candidates from producer manifests and receipts, not an old audit.

    Only publication staging and generated style outputs can expire. Original,
    input, recovery, checkpoint, transaction, model and unknown paths stay put.
    """
    config=Path(config).absolute();reject_links(config)
    now=time.time() if now is None else now
    state=None;missing_evidence=None
    try:state=ledger(config)
    except (OSError,ValueError,__import__('sqlite3').Error):
        missing_evidence='publication_evidence_missing; retained, not recreated'
    report=dict(version=1,scope=MANAGED_SCOPE,root=str(config),eligible=[],skipped=[],jobs=[],snapshot_heads={},references=None)
    directories=sorted((config/'jobs').iterdir()) if (config/'jobs').is_dir() else []
    snapshot={};protected=set();prior=journal_members(config/'state/verified-retention',MANAGED_SCOPE,config)
    references_ready=False
    retention=max(3,float(os.getenv('PEOPLE_BATCH_RETENTION_DAYS','3')))
    for folder in directories:
        reject_links(folder)
        if not folder.is_dir():continue
        item=dict(id=folder.name,status='unregistered',eligible_files=0,eligible_bytes=0)
        report['jobs'].append(item)
        try:
            manifest=read_json(folder/'manifest.json')
            item['status']=manifest.get('status','unknown')
            from create_people_posters.people_workspaces import ID_PATTERN
            if not ID_PATTERN.fullmatch(folder.name) or manifest.get('id')!=folder.name or manifest.get('managed_by')!='kometa-people-v1':
                raise RetentionBlocked('unrecognized_job_ownership')
            if missing_evidence:raise RetentionBlocked(missing_evidence)
            row=state['jobs'].get(folder.name)
            if not row:raise RetentionBlocked('job_missing_from_publication_ledger')
            item['status']=row['status']
            if row['status'] not in SUCCESS or row['published'] is None:
                raise RetentionBlocked('complete_metadata_retained' if row['status']=='complete' else 'failed_incomplete_or_retryable; retained')
            item['published']=row['published'];item['retention_deadline']=row['published']+retention*86400
            if now<item['retention_deadline']:raise RetentionBlocked('three_day_window_open')
            if (folder/'.active').exists():raise RetentionBlocked('active_job')
            if not references_ready:
                protected,report['references']=protected_references(config,state,for_jobs=True)
                references_ready=True
            if not snapshot:
                remote=remote or ReadOnlyGitHub();snapshot=remote.snapshot()
            proof,reason=job_proof(config,folder.name,state,snapshot,now,retention)
            if reason:raise RetentionBlocked(reason)
            catalog=proof['manifest']['cleanup_files'];images={}
            for root,dirs,names in os.walk(folder,followlinks=False,onerror=lambda e:(_ for _ in ()).throw(e)):
                for name in dirs+names:reject_links(Path(root)/name)
                for name in names:
                    p=Path(root)/name
                    if p.suffix.lower() in IMAGE:
                        identity=inspect(p);rel=p.relative_to(folder).as_posix()
                        if catalog.get(rel)!=identity['sha256']:
                            raise RetentionBlocked('changed_or_unowned_job_image')
                        old=prior.get(p.relative_to(config).as_posix())
                        if old and old['state'] in {'deleted','missing_after_intent'}:
                            raise RetentionBlocked('deleted_job_image_reappeared; review required')
                        images[rel]=identity
            for name,digest in catalog.items():
                p=member(folder,name)
                if not p.exists():
                    old=prior.get(p.relative_to(config).as_posix())
                    if not old or old['sha256']!=digest:
                        raise RetentionBlocked('catalogued_image_missing_without_receipt')
                    report['skipped'].append(dict(path=old['path'],bytes=old['bytes'],
                        reason='already_receipted',state=old['state']))
            candidates=[]
            for name,identity in images.items():
                parts=Path(name).parts;rel=(folder/name).relative_to(config).as_posix()
                generated=(len(parts)>2 and parts[0]=='people_dirs' and parts[1] in set(REPOSITORIES)-{'original'})
                prepared=(len(parts)>3 and parts[:2]==('.publish',folder.name) and parts[2] in REPOSITORIES)
                if not (generated or prepared) or protected_path({'path':rel},protected):continue
                candidates.append(dict(path=rel,bytes=identity['bytes'],sha256=identity['sha256'],git_blob=identity['git_blob'],
                    identity=identity,reason='verified_successful_job_payload',job=folder.name,
                    proof=dict(kind='existing_successful_job_receipts',receipts=proof['receipts'])))
            item.update(eligible_files=len(candidates),eligible_bytes=sum(r['bytes'] for r in candidates),
                        reason='eligible' if candidates else 'protected_sources_and_metadata_only')
            report['eligible'].extend(candidates)
        except (OSError,ValueError,KeyError,TypeError) as error:
            # Missing proof for one job must not disable retention of other jobs.
            item['reason']=str(error) if isinstance(error,RetentionBlocked) else 'unreadable_or_invalid_job_evidence'
    if snapshot:
        remote.confirm(snapshot);report['snapshot_heads']={repo:data['head'] for repo,data in snapshot.items()}
    report['plan_digest']=fingerprint(report)
    report.update(eligible_files=len(report['eligible']),eligible_bytes=sum(r['bytes'] for r in report['eligible']),generated_utc=datetime.now(timezone.utc).isoformat())
    return report,snapshot


def cleanup_managed_jobs(manager, *, dry_run=True, now=None, remote=None):
    """Opt-in launch adapter; same planner as the independent manual command."""
    marker=read_json(manager.state/'verified-retention/enrollment.json')
    if manager.jobs!=manager.config/'jobs' or manager.state!=manager.config/'state':
        raise RetentionBlocked('Custom workspace roots require explicit retention review')
    plan,_=build_jobs_plan(manager.config,remote,now=now)
    eligible=sum(j['eligible_files']>0 for j in plan['jobs'])
    manager.last_cleanup_counts=dict(eligible=eligible,deleted=0,retained=len(plan['jobs']))
    if dry_run or not marker.get('unattended_reviewed',False):
        return [(j['id'],('eligible; automatic deletion awaiting review' if j['eligible_files'] else 'retained: '+j['reason'])) for j in plan['jobs']]
    remote=remote or ReadOnlyGitHub()
    result=apply_plan(manager.config,None,remote,plan,marker['ci_receipt'],allow_existing=True)
    manager.last_cleanup_counts['deleted']=eligible
    return [(j['id'],'compacted; sources/metadata retained' if j['eligible_files'] else 'retained: '+j['reason']) for j in plan['jobs']]


def ordinary_logs(config):
    """Only text diagnostics; decision logs, CSV sets and checkpoint JSON excluded."""
    root=Path(config)/'logs';result=[]
    for name in sorted(ORDINARY_LOGS):
        p=root/name
        if p.exists():
            info=inspect(p)
            result.append(dict(path=p.relative_to(config).as_posix(),bytes=info['bytes'],
                over_limit=info['bytes']>LOG_BYTES,limit_bytes=LOG_BYTES,backups=3,
                writer=name[:-4]+'.py',action='rotate_at_next_writer_start; no rotation during processing'))
    return result


def rotate_ordinary_logs(config):
    """Maintenance under the processing lease; never called during a stage.

    Keep last5MiB of ordinary diagnostics and three numbered archives. The
    explicit whitelist excludes every text log parsed for processing decisions.
    """
    config=Path(config)
    removed=[]
    for row in ordinary_logs(config):
        if not row['over_limit']:continue
        p=member(config,row['path'])
        archive=[p.with_name(p.name+'.'+str(i)) for i in range(1,4)]
        before={q:inspect(q) for q in [p,*archive] if q.exists()}
        # Validate complete ownership before touching any member of this family.
        for q,identity in before.items():
            if inspect(q)!=identity:raise RetentionBlocked('Diagnostic log changed before rotation')
        oldest=archive[-1]
        if oldest.exists():
            identity=before[oldest]
            unlink_verified(config,dict(path=oldest.relative_to(config).as_posix(),identity=identity,sha256=identity['sha256']))
            removed.append(dict(path=oldest.relative_to(config).as_posix(),bytes=identity['bytes'],sha256=identity['sha256'],reason='ordinary_log_archive_limit'))
        for index in (2,1):
            source=archive[index-1];target=archive[index]
            if source.exists():os.replace(source,target)
        # Preserve a bounded tail as newest archive; current writer starts empty.
        with p.open('rb') as stream:
            stream.seek(max(0,before[p]['bytes']-LOG_BYTES));tail=stream.read(LOG_BYTES)
        temporary=archive[0].with_suffix(archive[0].suffix+'.retention-tmp')
        reject_links(temporary)
        with temporary.open('xb') as stream:
            stream.write(tail);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,archive[0])
        if inspect(p)!=before[p]:raise RetentionBlocked('Diagnostic log changed during rotation')
        removed.append(dict(path=row['path'],bytes=before[p]['bytes']-len(tail),sha256=before[p]['sha256'],reason='ordinary_log_tail_limit'))
        with p.open('wb') as stream:stream.flush();os.fsync(stream.fileno())
    return removed


def apply_plan(config, approval, remote, expected, ci_receipt, *, source_root=None,allow_existing=False):
    source_root=Path(source_root or Path(__file__).resolve().parents[1])
    ci=remote.validate_ci(ci_receipt,source_root)
    scope=APPROVAL if approval is not None else MANAGED_SCOPE
    with processing_exclusion(config,scope,allow_existing=allow_existing) as directory:
        report,snapshot=build_plan(config,approval,remote) if approval is not None else build_jobs_plan(config,remote)
        if report['plan_digest']!=expected['plan_digest']:
            raise RetentionBlocked('Fresh eligibility differs from reviewed dry-run')
        # Enrollment prevents the old broad rmtree cleanup from bypassing proof.
        enrollment=directory/'enrollment.json'
        previous=read_json(enrollment) if enrollment.exists() else {}
        reviewed=previous.get('unattended_reviewed',False) and previous.get('head')==ci['head']
        atomic_json(enrollment,dict(version=1,scope=scope,head=ci['head'],
            source_root=str(source_root),ci_receipt=ci_receipt,unattended_reviewed=reviewed))
        journal=Journal(directory);removed=[]
        run_id=str(time.time_ns());run_path=directory/('run-'+run_id+'.json')
        try:
            for row in report['skipped']:
                if row['reason']=='already_receipted' and row['state']=='intent':
                    journal.mark(scope,config,row['path'],'missing_after_intent')
            for row in report['eligible']:
                repositories=[row['proof']['repo']] if 'repo' in row['proof'] else None
                remote.confirm(snapshot,repositories)
                # Local state/reference graph cannot silently change mid-cleanup.
                state=ledger(Path(config))
                _,reference_hash=protected_references(Path(config),state,for_jobs=approval is None)
                if reference_hash!=report['references']:
                    raise RetentionBlocked('Operation metadata changed during cleanup')
                journal.intent(scope,config,row,row['proof'])
                unlink_verified(config,row)
                journal.mark(scope,config,row['path'],'deleted')
                removed.append(dict(path=row['path'],sha256=row['sha256'],git_blob=row['git_blob'],
                    bytes=row['bytes'],deleted_utc=datetime.now(timezone.utc).isoformat(),reason=row['reason']))
        finally:
            atomic_json(run_path,dict(head=ci['head'],approval=scope,root=str(config),
                plan_digest=report['plan_digest'],deleted=removed,recovered_bytes=sum(r['bytes'] for r in removed),
                completed=len(removed)==len(report['eligible']),ci=ci))
            journal.close()
        return read_json(run_path)


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--approval',type=Path,help='Optional fixed legacy adoption inventory; routine job cleanup needs none')
    parser.add_argument('--report',required=True,type=Path,help='NEW output outside production config')
    parser.add_argument('--apply-plan',type=Path)
    parser.add_argument('--ci-receipt',type=Path)
    parser.add_argument('--apply-logs',action='store_true',help='Rotate only ordinary persistent diagnostics under the shared lease')
    args=parser.parse_args(argv)
    config=args.config.absolute();output=args.report.absolute()
    if output==config or config in output.parents or output.exists():
        parser.error('Report must be a new file outside production config')
    from dotenv import load_dotenv
    from create_people_posters.people_diagnostics import register_environment
    reject_links(config/'.env')
    load_dotenv(config/'.env')
    register_environment()
    approval=approved_plan(args.approval) if args.approval else None
    remote=ReadOnlyGitHub() if approval is not None or args.apply_plan or args.apply_logs else None
    if args.apply_logs:
        if not args.ci_receipt or args.apply_plan or approval is not None:parser.error('Log maintenance requires CI receipt and its own invocation')
        ci=remote.validate_ci(read_json(args.ci_receipt),Path(__file__).resolve().parents[1])
        with processing_exclusion(config,MANAGED_SCOPE) as directory:
            changes=rotate_ordinary_logs(config)
            result=dict(head=ci['head'],changes=changes,reclaimed_bytes=sum(r['bytes'] for r in changes))
            atomic_json(directory/('log-run-'+str(time.time_ns())+'.json'),result)
    elif args.apply_plan:
        if not args.ci_receipt:parser.error('Apply requires final HEAD CI receipt')
        result=apply_plan(config,approval,remote,read_json(args.apply_plan),read_json(args.ci_receipt))
    else:
        result=(build_plan(config,approval,remote) if approval is not None else build_jobs_plan(config,remote))[0]
        result['ordinary_logs']=ordinary_logs(config)
    atomic_json(output,result)
    print(json.dumps({k:result[k] for k in ('eligible_files','eligible_bytes','plan_digest','recovered_bytes') if k in result}))


if __name__=='__main__':
    main()
