"""Journaled moves of *copies* in the disposable trial; no catalog/remote IO.

The durable prepare event precedes any move. SQLite recovery decides whether
to restore the old spelling or finish the committed spelling. Archive objects
and receipts are retained, including after definition DELETE.
"""
import os
from pathlib import Path

from ..common import atomic_bytes, canonical, confined, fingerprint, reject_links, sha256
from .package_e import SidecarStore
from .previews import CompositionArchive
from .retirement import fail
from .storage import MAX_EVENTS, MAX_ARCHIVE_BYTES

PREPARE='phase4_mapping_move_prepared'


def _checkpoint(name):
    """Internal interruption seam; not a caller callback."""


def event_budget(db):
    count,size=db.execute("SELECT count(*),coalesce(sum(length(CAST(payload AS BLOB))),0) FROM events WHERE kind GLOB 'phase4_mapping_*'").fetchone()
    if count>MAX_EVENTS or size>MAX_ARCHIVE_BYTES: fail('move_archive_bound')


def _rows(store, db):
    event_budget(db)
    size=db.execute('SELECT coalesce(sum(length(CAST(payload AS BLOB))),0) FROM events WHERE kind=?',(PREPARE,)).fetchone()[0]
    if size>64*1024*1024: fail('move_archive_bound')
    rows=db.execute('SELECT subject,payload FROM events WHERE kind=? ORDER BY sequence LIMIT ?', (PREPARE,MAX_EVENTS+1)).fetchall()
    if len(rows)>MAX_EVENTS: fail('move_archive_bound')
    import json
    values={}
    for identity,raw in map(tuple,rows):
        v=json.loads(raw)
        if canonical(v).decode()!=raw or set(v)!={'plan_sha256','members'} or identity in values:
            fail('move_journal')
        from .mappings import MappingPlan
        plan=MappingPlan.from_bytes(store.read_object(v['plan_sha256']))
        if plan.sha256!=v['plan_sha256'] or plan.to_dict()['operation_id']!=identity or v['members']!=_members(plan):
            fail('move_journal_binding')
        values[identity]=v
    return values


def _root(store, op):
    # Only this operation's directory under the M1-owned isolated state.
    return confined(store.root, 'm6-owned/'+fingerprint(op))


def _path(root, relative):
    # Validate confinement/reparse points without returning Path.resolve()'s
    # case-canonicalized spelling on Windows. Journal paths remain literal.
    confined(root,relative)
    return reject_links(Path(root)/relative)


def _members(plan):
    p=plan.to_dict(); members={}
    for i in p['members']:
        a,b=p['before'][i]['names'],p['after'][i]['names']
        if p['operation']=='DELETE' or a['local_path']==b['local_path']: continue
        m=p['retained'][i]['artwork']
        members[i]=dict(old=a['local_path'],new=b['local_path'],
            temporary='intermediate/'+fingerprint(i)+'.m6',sha256=m['sha256'],object_sha256=m['object_sha256'])
    return members


def stage(store, plan):
    p=plan.to_dict();members=_members(plan)
    if not members: return
    desired=dict(plan_sha256=plan.sha256,members=members)
    writer=SidecarStore(store.root)
    with writer.transaction() as db:
        rows=_rows(writer,db)
        committed={r[0] for r in db.execute("SELECT subject FROM events WHERE kind='phase4_mapping_committed'")}
        if p['operation_id'] in rows:
            if rows[p['operation_id']]!=desired: fail('move_journal_substitution')
            if p['operation_id'] in committed:
                return  # The coordinator independently checks the exact commit.
        else:
            # Other pending operations require explicit recovery/withdrawal.
            from .storage import _replay
            latest=_replay(writer,db)[2]
            cancelled={i for i,(r,e) in latest.items() if r.to_dict()['state']=='cancelled'}
            if set(rows)-committed-cancelled: fail('pending_move_recovery_required')
            for i in members:
                if (_root(writer,p['operation_id'])/fingerprint(i)).exists(): fail('unowned_move_directory')
            writer.event(db,PREPARE,p['operation_id'],desired)
            event_budget(db)
    # The prepare event is durable before any filesystem creation. A second
    # immediate transaction serializes idempotent population for concurrent
    # retries of this exact operation, including the prepare/stage crash gap.
    _checkpoint('journal_prepared')
    archive=CompositionArchive(writer.root,readonly=True)
    with writer.transaction() as db:
        if _rows(writer,db).get(p['operation_id'])!=desired: fail('move_journal_substitution')
        if db.execute("SELECT 1 FROM events WHERE kind='phase4_mapping_committed' AND subject=?",(p['operation_id'],)).fetchone():
            return
        for i,m in members.items():
            root=_root(writer,p['operation_id'])/fingerprint(i)
            old=_path(root,m['old']);new=_path(root,m['new']);temp=_path(root,m['temporary'])
            if _literal(new) or _literal(temp): fail('pending_move_recovery_required')
            if _literal(old):
                if old.stat().st_nlink!=1 or sha256(old)!=m['sha256']: fail('move_bytes')
                continue
            raw=archive.read_bytes(m['object_sha256'])
            from hashlib import sha256 as digest
            if digest(raw).hexdigest()!=m['sha256']: fail('move_bytes')
            old.parent.mkdir(parents=True,exist_ok=True)
            atomic_bytes(old,raw)
    _checkpoint('prepared')


def _literal(path):
    """OS exists() cannot distinguish a case-only path on Windows."""
    reject_links(path)
    return path.parent.is_dir() and path.name in {p.name for p in path.parent.iterdir()}


def _move(source, target, expected):
    reject_links(source);reject_links(target)
    if not _literal(source) or source.stat().st_nlink!=1 or sha256(source)!=expected or _literal(target): fail('occupied_or_changed_move')
    target.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive hard-link creation never replaces an occupied target. The two
    # journaled legs also work for case-only NTFS names. A crash between link
    # and unlink is resolved using inode identity, not just equal bytes.
    os.link(source,target)
    _checkpoint('linked')
    source.unlink()


def execute(store, db, plan):
    p=plan.to_dict();v=_rows(store,db).get(p['operation_id'])
    if v is None: return
    if v['plan_sha256']!=plan.sha256: fail('move_plan')
    for i,m in v['members'].items():
        root=_root(store,p['operation_id'])/fingerprint(i)
        old,new,temp=[_path(root,m[k]) for k in ('old','new','temporary')]
        # Retry after explicit recovery starts from the exact old spelling.
        _move(old,temp,m['sha256']);_checkpoint('intermediate')
        _move(temp,new,m['sha256']);_checkpoint('destination')
        store.event(db,'phase4_mapping_move_finished',p['operation_id'],dict(member=i,plan_sha256=plan.sha256,sha256=m['sha256']))


def inspect(store, db, commits):
    """Read-only physical verification; pending copies never imply a commit."""
    result={}
    for op,v in _rows(store,db).items():
        committed=op in commits
        if committed and commits[op]['plan_sha256']!=v['plan_sha256']: fail('move_commit')
        rows={}
        for i,m in v['members'].items():
            root=_root(store,op)/fingerprint(i)
            paths={k:_path(root,m[k]) for k in ('old','new','temporary')}
            found={k:p for k,p in paths.items() if _literal(p)}
            if any(sha256(p)!=m['sha256'] for p in found.values()): fail('move_inspection_bytes')
            if found:
                first=next(iter(found.values()))
                if first.stat().st_nlink!=len(found) or any(not os.path.samefile(first,p) for p in found.values()):
                    fail('unowned_move_target')
            if committed and set(found)!={'new'}: fail('committed_move_spelling')
            rows[i]=dict(sha256=m['sha256'],positions=sorted(found))
        result[op]=dict(committed=committed,members=rows)
    return result


def recover(store, db, commits, operation_id=None):
    """Restore only owned staged copies for uncommitted operations.

    No bytes are inferred from public files. Unexpected, substituted or unrelated
    targets block recovery. Multiple names are permitted only for one inode,
    proving an interrupted exclusive link/unlink step.
    """
    result={}
    for op,v in _rows(store,db).items():
        if operation_id is not None and op!=operation_id: continue
        committed=op in commits
        if committed and commits[op]['plan_sha256']!=v['plan_sha256']: fail('move_commit')
        for i,m in v['members'].items():
            root=_root(store,op)/fingerprint(i)
            paths={k:_path(root,m[k]) for k in ('old','new','temporary')}
            found=[p for p in paths.values() if _literal(p)]
            if not found:
                if committed: fail('move_recovery_bytes')
                raw=CompositionArchive(store.root,readonly=True).read_bytes(m['object_sha256'])
                from hashlib import sha256 as digest
                if digest(raw).hexdigest()!=m['sha256']: fail('move_recovery_bytes')
                paths['old'].parent.mkdir(parents=True,exist_ok=True)
                atomic_bytes(paths['old'],raw)
                found=[paths['old']]
            if any(sha256(p)!=m['sha256'] for p in found): fail('move_recovery_bytes')
            if found[0].stat().st_nlink!=len(found) or len(found)>1 and any(not os.path.samefile(found[0],p) for p in found[1:]): fail('unowned_recovery_target')
            desired=paths['new' if committed else 'old']
            if not _literal(desired):
                # Always pass through an intermediate for case-only recovery.
                temp=paths['temporary']
                if not _literal(temp): _move(found[0],temp,m['sha256'])
                for path in found:
                    if _literal(path) and path!=temp: path.unlink()
                _move(temp,desired,m['sha256'])
            for path in paths.values():
                if path!=desired and _literal(path):
                    if not os.path.samefile(desired,path): fail('unowned_recovery_target')
                    path.unlink()
        result[op]='committed-spelling' if committed else 'restored-preimage'
    return result
