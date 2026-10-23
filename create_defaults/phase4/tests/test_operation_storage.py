"""Actual Package E SQLite persistence, multi-head CAS and immutable recovery."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from threading import Barrier

import pytest

from create_defaults.bulk.common import BulkError,Conflict,canonical,fingerprint
from create_defaults.bulk.contracts.state import ContractStore
from create_defaults.bulk.lifecycle.models import Operation,Event,key,namespace_key
from create_defaults.bulk.lifecycle.storage import OperationStore,TRIGGERS
from .samples import sample,append,next_record


@pytest.fixture
def store(tmp_path):return OperationStore.create(tmp_path/'isolated')


@pytest.mark.parametrize('kind',['ADD','UPDATE','RENAME','DELETE'])
def test_all_types_persist_as_records_without_applying_proposed_state(store,kind):
    r=sample(operation=kind,subjects=('a','b'));e=append(store,r)
    assert store.history(r.to_dict()['id'])==(r,)
    assert store.journal()==(e,)
    reopened=OperationStore(store.root)
    result=reopened.inspect(expected_journal_sha256=e.sha256)
    assert result['sequence']==1 and result['records']==1
    assert {h['sha256'] for h in result['heads']}=={r.sha256}
    assert r.to_dict()['subjects'][0]['proposed_sha256']!=r.sha256
    assert not any(result[k] for k in ['operation_accepted','applied','ready','active','production_enforcement','publication_authorized','contract_approved','artwork_approved'])


def test_closed_state_transitions_content_revisions_and_cancelled_history(store):
    r=sample();append(store,r)
    validated=next_record(store,r);append(store,validated)
    assert validated.to_dict()['content_revision']==1
    revised=next_record(store,validated,state='draft',change=True);append(store,revised)
    assert revised.to_dict()['content_revision']==2
    stale=next_record(store,revised,state='stale');append(store,stale)
    fresh=next_record(store,stale,state='draft',change=True);append(store,fresh)
    cancelled=next_record(store,fresh,state='cancelled');append(store,cancelled)
    assert [r.to_dict()['revision'] for r in store.history(r.to_dict()['id'])]==list(range(1,7))
    assert store.inspect()['operations'][0]['state']=='cancelled'
    with pytest.raises(BulkError,match='transition'):append(store,next_record(store,cancelled,state='draft',change=True))


@pytest.mark.parametrize('mutation',['initial-state','operation-type','subject-set','revision-jump','bad-previous-record',
    'bad-previous-event','same-content-revision','changed-content-validated','same-state-no-change','content-counter','cancel-transition'])
def test_invalid_operation_identity_revision_and_transition_fails_without_advancing(store,mutation):
    r=sample();append(store,r);before=store.inspect();v=next_record(store,r).to_dict()
    if mutation=='initial-state':
        v=sample(name='another',subjects=('b',)).to_dict();v['state']='structurally_validated'
    elif mutation=='operation-type':v['operation']='RENAME'
    elif mutation=='subject-set':
        v=sample(store,name='one',subjects=('b',)).to_dict()
        v.update(revision=2,previous_sha256=r.sha256,previous_event_sha256=store.journal()[0].sha256)
    elif mutation=='revision-jump':v['revision']=3
    elif mutation=='bad-previous-record':v['previous_sha256']='f'*64
    elif mutation=='bad-previous-event':v['previous_event_sha256']='f'*64
    elif mutation=='same-content-revision':v['request_sha256']='f'*64
    elif mutation=='changed-content-validated':v.update(request_sha256='f'*64,content_revision=2)
    elif mutation=='same-state-no-change':v['state']='draft'
    elif mutation=='content-counter':v['content_revision']=2
    else:
        cancelled=next_record(store,r,state='cancelled');append(store,cancelled);before=store.inspect()
        v=next_record(store,cancelled,state='structurally_validated').to_dict()
    with pytest.raises(BulkError):append(store,Operation.from_dict(v))
    assert store.inspect()==before


def test_exact_retry_after_later_operations_returns_original_event_without_reapplying(store):
    r=sample();e=append(store,r);append(store,next_record(store,r))
    append(store,sample(store,name='independent',subjects=('b',)))
    before=store.inspect();assert append(store,r)==e and store.inspect()==before
    v=r.to_dict();v['request_sha256']='f'*64
    with pytest.raises(Conflict):append(store,Operation.from_dict(v))
    assert store.inspect()==before


@pytest.mark.parametrize('field,value',[('expected_revision',True),('expected_revision',-1),('expected_revision',1),
 ('expected_sha256','f'*64),('expected_event_sha256','f'*64)])
def test_independent_expected_operation_heads_are_mandatory(store,field,value):
    r=sample();args=dict(expected_revision=0,expected_sha256=None,expected_event_sha256=None);args[field]=value
    with pytest.raises(BulkError):store.append(r,**args)
    assert not store.inspect()['records']


@pytest.mark.parametrize('overlap',['subject','output-group','namespace','evidence','dependency'])
def test_stale_multisubject_namespace_and_evidence_heads_reject_unchanged_proposals(store,overlap):
    extra=[dict(kind=overlap,id='synthetic.shared')] if overlap in {'evidence','dependency'} else []
    a=sample(store,name='first',subjects=('a','b') if overlap=='output-group' else ('a',),
        paths=['posters/first.jpg'] if overlap!='namespace' else ['Posters/Same.jpg'],extra_heads=extra,write_extras=True)
    b=sample(store,name='second',subjects=('b','c') if overlap=='output-group' else ('a',) if overlap=='subject' else ('z',),
        paths=['posters/second.jpg'] if overlap!='namespace' else ['posters/same.jpg'],extra_heads=extra)
    old_proposed=b.to_dict()['subjects'];append(store,a);snapshot=store.inspect()
    with pytest.raises(Conflict):append(store,b)
    assert b.to_dict()['subjects']==old_proposed and store.inspect()==snapshot
    assert not store.history(b.to_dict()['id'])


@pytest.mark.parametrize('overlap',[True,False])
def test_actual_concurrent_writers_are_atomic_and_disjoint_requests_proceed(store,overlap):
    barrier=Barrier(2)
    requests=[sample(store,name=n,subjects=('a',) if overlap else (n,)) for n in ['one','two']]
    def run(r):
        local=OperationStore(store.root);barrier.wait(timeout=15)
        try:return append(local,r)
        except Conflict:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,requests))
    assert sum(r is not None for r in results)==(1 if overlap else 2)
    check=OperationStore(store.root).inspect();assert check['records']==check['sequence']==(1 if overlap else 2)
    assert [e.to_dict()['sequence'] for e in store.journal()]==list(range(1,check['sequence']+1))


def test_concurrent_rename_requests_cannot_claim_the_same_casefolded_namespace_head(store):
    barrier=Barrier(2)
    requests=[sample(store,name=name,operation='RENAME',subjects=(name,),paths=[path])
        for name,path in [('one','Posters/Reserved.jpg'),('two','posters/reserved.jpg')]]
    def rename_request(record):
        local=OperationStore(store.root);barrier.wait(timeout=15)
        try:return append(local,record)
        except Conflict:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(rename_request,requests))
    assert sum(event is not None for event in results)==1
    report=OperationStore(store.root).inspect()
    assert report['records']==report['sequence']==1 and not report['applied']
    assert len([h for h in report['heads'] if h['kind']=='namespace'])==1
    # Coordination is not a filesystem move or persistent M2 name allocation.
    assert not (store.root/'Posters').exists() and not (store.root/'posters').exists()


def test_concurrent_identical_requests_are_idempotent_without_double_journal(store):
    r=sample();barrier=Barrier(2)
    def retry(_):
        local=OperationStore(store.root);barrier.wait(timeout=15);return append(local,r)
    with ThreadPoolExecutor(max_workers=2) as pool:events=list(pool.map(retry,range(2)))
    assert events[0].sha256==events[1].sha256 and store.inspect()['records']==store.inspect()['sequence']==1


def test_change_to_read_write_membership_requires_new_draft_content_revision(store):
    r=sample();append(store,r);v=next_record(store,r).to_dict()
    v['reads'].insert(0,dict(kind='dependency',id='synthetic.new',subjects=['synthetic.subject.a'],revision=0,sha256=None))
    v['writes'].insert(0,dict(kind='dependency',id='synthetic.new'))
    with pytest.raises(BulkError,match='content_revision'):append(store,Operation.from_dict(v))
    assert store.inspect()['records']==1


def test_read_only_dependency_head_change_is_checked_even_without_writing_it(store):
    extra=[dict(kind='dependency',id='synthetic.shared')]
    pending=sample(store,name='pending',subjects=('a',),extra_heads=extra)
    changed=sample(store,name='changer',subjects=('b',),extra_heads=extra,write_extras=True);append(store,changed)
    with pytest.raises(Conflict):append(store,pending)
    refreshed=sample(store,name='pending',subjects=('a',),extra_heads=extra)
    append(store,refreshed);assert store.inspect()['records']==2


def test_journal_binds_every_index_head_and_existing_package_e_event(store):
    r=sample(operation='DELETE',subjects=('a','b'));e=append(store,r)
    cancellation=next_record(store,r,state='cancelled');second=append(store,cancellation)
    assert second.to_dict()['previous_sha256']==e.sha256
    assert second.to_dict()['previous_operation_event_sha256']==e.sha256
    assert cancellation.to_dict()['references']==r.to_dict()['references']
    with store.contracts.read_connection() as db:
        assert db.execute('SELECT count(*) FROM events WHERE kind=?',('phase4_operation_recorded',)).fetchone()[0]==2
        assert db.execute('SELECT count(*) FROM p4m1_heads').fetchone()[0]==6
    assert OperationStore(store.root).history(r.to_dict()['id'])[0].to_dict()['references']==r.to_dict()['references']


@pytest.mark.parametrize('table',['p4m1_records','p4m1_heads','p4m1_journal','p4m1_schema'])
@pytest.mark.parametrize('action',['UPDATE','DELETE'])
def test_operation_indexes_are_physically_append_only(store,table,action):
    append(store,sample())
    with sqlite3.connect(store.root/'state.sqlite3') as db:
        sql=f'DELETE FROM {table}' if action=='DELETE' else f'UPDATE {table} SET '+{'p4m1_records':'revision=99','p4m1_heads':'revision=99','p4m1_journal':'sequence=99','p4m1_schema':'version=99'}[table]
        with pytest.raises(sqlite3.IntegrityError):db.execute(sql)
    OperationStore(store.root).inspect()


@pytest.mark.parametrize('stage',['record-blob','event-blob','package-event','index-insert'])
def test_interruption_leaves_no_partial_index_or_event_and_exact_retry_recovers(store,monkeypatch,stage):
    r=sample();original_put=ContractStore.put_object;original_event=ContractStore.event
    count=0
    def interrupted_put(self,*args,**kwargs):
        nonlocal count
        result=original_put(self,*args,**kwargs);count+=1
        if count==(1 if stage=='record-blob' else 2):raise KeyboardInterrupt('synthetic interrupted append')
        return result
    def interrupted_event(self,*args,**kwargs):
        result=original_event(self,*args,**kwargs)
        if stage=='package-event':raise KeyboardInterrupt('synthetic event interruption')
        return result
    with monkeypatch.context() as guard:
        if stage.endswith('blob'):guard.setattr(ContractStore,'put_object',interrupted_put)
        elif stage=='package-event':guard.setattr(ContractStore,'event',interrupted_event)
        else:
            with sqlite3.connect(store.root/'state.sqlite3') as db:
                db.execute("CREATE TRIGGER synthetic_failure BEFORE INSERT ON p4m1_journal BEGIN SELECT RAISE(ABORT,'synthetic interruption'); END")
        with pytest.raises((KeyboardInterrupt,sqlite3.IntegrityError)):append(store,r)
    if stage=='index-insert':
        with sqlite3.connect(store.root/'state.sqlite3') as db:db.execute('DROP TRIGGER synthetic_failure')
    reopened=OperationStore(store.root);assert reopened.inspect()['records']==reopened.inspect()['sequence']==0
    with reopened.contracts.read_connection() as db:
        assert db.execute('SELECT count(*) FROM p4m1_heads').fetchone()[0]==0
        assert db.execute("SELECT count(*) FROM events WHERE kind='phase4_operation_recorded'").fetchone()[0]==0
    event=append(reopened,r);assert reopened.inspect()['sequence']==1 and append(reopened,r)==event


def test_partial_unreferenced_blob_is_retained_but_never_becomes_authoritative(store):
    orphan=store.root/'objects'/('a'*64+'.json');orphan.parent.mkdir(exist_ok=True);orphan.write_bytes(b'{')
    assert OperationStore(store.root).inspect()['records']==0
    append(store,sample());assert orphan.read_bytes()==b'{' and store.inspect()['records']==1


def test_actual_process_death_inside_transaction_recovers_without_partial_authority(store):
    import sys
    code='''import os,sys
from create_defaults.bulk.contracts.state import ContractStore
from create_defaults.bulk.lifecycle.storage import OperationStore
from create_defaults.phase4.tests.samples import sample,append
original=ContractStore.event
def terminated(self,*args,**kwargs):
 original(self,*args,**kwargs)
 os._exit(27)
ContractStore.event=terminated
store=OperationStore(sys.argv[1]);append(store,sample())
'''
    result=subprocess.run([sys.executable,'-c',code,str(store.root)],capture_output=True,text=True,timeout=60)
    assert result.returncode==27,result.stderr
    restarted=OperationStore(store.root);assert restarted.inspect()['records']==restarted.inspect()['sequence']==0
    append(restarted,sample());assert restarted.inspect()['records']==1


@pytest.mark.parametrize('mutation',['record','event','missing-object','noncanonical','record-index','head-index','journal-index','package-event','orphan-record','namespace','version'])
def test_corrupt_substituted_missing_or_foreign_archive_fails_closed(store,mutation):
    r=sample();event=append(store,r)
    def rewrite(table,sql,params=()):
        with sqlite3.connect(store.root/'state.sqlite3') as db:
            trigger=table+'_no_update';statement=next(s for s in TRIGGERS if s.startswith('CREATE TRIGGER '+trigger+' '))
            db.execute('DROP TRIGGER '+trigger);db.execute(sql,params);db.execute(statement)
    if mutation in {'record','event','missing-object','noncanonical'}:
        pin=event.sha256 if mutation=='event' else r.sha256;p=store.root/'objects'/(pin+'.json')
        if mutation=='missing-object':p.unlink()
        elif mutation=='noncanonical':p.write_bytes(json.dumps(r.to_dict(),indent=2).encode())
        else:p.write_bytes(b'{}')
    elif mutation=='record-index':rewrite('p4m1_records','UPDATE p4m1_records SET sha256=?',('f'*64,))
    elif mutation=='head-index':rewrite('p4m1_heads','UPDATE p4m1_heads SET subjects=?',(canonical(['synthetic.foreign']).decode(),))
    elif mutation=='journal-index':rewrite('p4m1_journal','UPDATE p4m1_journal SET package_event=999')
    elif mutation=='package-event':
        with sqlite3.connect(store.root/'state.sqlite3') as db:
            db.execute("INSERT INTO events(kind,subject,created,payload) VALUES ('phase4_operation_recorded','synthetic.forged',0,'{}')")
    elif mutation=='orphan-record':
        other=sample(name='other',subjects=('b',));writer=ContractStore(store.root);writer.put_object(other.encoded,expected_sha256=other.sha256)
        with writer.transaction() as db:db.execute('INSERT INTO p4m1_records VALUES (?,?,?)',(other.to_dict()['id'],1,other.sha256))
    elif mutation=='namespace':
        with sqlite3.connect(store.root/'state.sqlite3') as db:db.execute('DROP TRIGGER p4m1_heads_no_delete')
    else:rewrite('p4m1_schema','UPDATE p4m1_schema SET version=99')
    with pytest.raises(BulkError):OperationStore(store.root)


def test_external_checkpoint_detects_coherent_rollback_and_no_checkpoint_claims_currentness(store,tmp_path):
    r=sample();append(store,r)
    backup=tmp_path/'backup.sqlite'
    with sqlite3.connect(store.root/'state.sqlite3') as source,sqlite3.connect(backup) as dest:source.backup(dest)
    event=append(store,next_record(store,r))
    with sqlite3.connect(backup) as source,sqlite3.connect(store.root/'state.sqlite3') as dest:source.backup(dest)
    reopened=OperationStore(store.root)
    assert reopened.inspect()['currentness']=='integrity-only-currentness-unknown'
    with pytest.raises(Conflict):reopened.inspect(expected_journal_sha256=event.sha256)


@pytest.mark.parametrize('limit',['MAX_EVENTS','MAX_HEAD_VERSIONS','MAX_ARCHIVE_BYTES'])
def test_archive_limits_fail_without_partial_authoritative_changes(store,monkeypatch,limit):
    from create_defaults.bulk.lifecycle import storage
    append(store,sample());before=store.inspect();monkeypatch.setattr(storage,limit,1)
    with pytest.raises(BulkError):append(store,sample(name='new',subjects=('b',)))
    monkeypatch.undo();assert store.inspect()==before


def test_readonly_open_and_inspection_never_initialize_or_allow_writes(store,monkeypatch,tmp_path):
    r=sample();append(store,r)
    missing=tmp_path/'does-not-exist'
    from create_defaults.bulk import state
    def prohibited(*a,**k):raise AssertionError('Read path initialized or wrote state')
    with monkeypatch.context() as guard:
        guard.setattr(state.Store,'__init__',prohibited);guard.setattr(ContractStore,'put_object',prohibited)
        reopened=OperationStore(store.root);assert reopened.history(r.to_dict()['id'])==(r,)
        assert reopened.inspect()['records']==1
        with pytest.raises(BulkError):OperationStore(missing)
    assert not missing.exists()
    with pytest.raises(BulkError):store.contracts.put_object(r.encoded,expected_sha256=r.sha256)
    with pytest.raises(BulkError):
        with store.contracts.transaction():pass


@pytest.mark.parametrize('attack',['foreign','base-only','missing-database','unknown-base','traversal','production','root-file'])
def test_root_and_namespace_attacks_never_initialize_foreign_or_production_state(tmp_path,attack):
    root=tmp_path/'root'
    if attack=='foreign':root.mkdir();(root/'unrelated.txt').write_text('preserve')
    elif attack=='base-only':ContractStore(root)
    elif attack=='missing-database':
        OperationStore.create(root);(root/'state.sqlite3').unlink()
    elif attack=='unknown-base':
        root.mkdir();(root/'contract-state.json').write_bytes(b'{}')
    elif attack=='traversal':root=tmp_path/'a'/'..'/'escape'
    elif attack=='root-file':root.write_bytes(b'preserve this existing file')
    else:
        from create_defaults.bulk.config import Config
        root=Config().asset_dir
    before={p.name for p in root.iterdir()} if root.is_dir() else set()
    with pytest.raises(BulkError):OperationStore.create(root)
    assert ({p.name for p in root.iterdir()} if root.is_dir() else set())==before
    if attack=='root-file':assert root.read_bytes()==b'preserve this existing file'


@pytest.mark.parametrize('part',['root','objects'])
def test_symlink_or_windows_junction_roots_and_blob_namespaces_are_rejected(tmp_path,part):
    target=tmp_path/'target';target.mkdir();sentinel=target/'preserve';sentinel.write_bytes(b'unchanged')
    root=tmp_path/'isolated';link=root if part=='root' else root/'objects'
    if part=='objects':OperationStore.create(root)
    if os.name=='nt':
        result=subprocess.run(['cmd','/c','mklink','/J',str(link),str(target)],capture_output=True)
        assert result.returncode==0,result.stderr
    else:link.symlink_to(target,target_is_directory=True)
    try:
        with pytest.raises(BulkError):OperationStore.create(root) if part=='root' else append(OperationStore(root),sample())
        assert sentinel.read_bytes()==b'unchanged'
    finally:
        # Remove only the owned link itself. Never recurse into its target.
        if os.name=='nt':os.rmdir(link)
        else:link.unlink()


def test_public_bridge_accepts_only_canonical_pinned_blobs_and_owned_transactions(store):
    writer=ContractStore(store.root);r=sample()
    for raw,pin in [(r.encoded,'f'*64),(json.dumps(r.to_dict()).encode(),r.sha256),(b'{',r.sha256)]:
        with pytest.raises(BulkError):writer.put_object(raw,expected_sha256=pin)
    with sqlite3.connect(store.root/'state.sqlite3') as foreign:
        foreign.execute('BEGIN')
        with pytest.raises(BulkError):writer.event(foreign,'forged','synthetic.a',{})
    with writer.transaction() as db:
        writer.event(db,'synthetic_bridge_control','synthetic.subject.a',{'data_only':True})
    assert writer.put_object(r.encoded,expected_sha256=r.sha256)==r.sha256
    assert writer.read_object(r.sha256)==r.encoded


def test_public_bridge_stabilizes_owned_parent_before_new_blob_resolution(store,monkeypatch):
    writer=ContractStore(store.root);original=ContractStore._blob_path
    assert not (store.root/'objects').exists()
    def stable_parent(self,pin):
        assert (self.root/'objects').is_dir()
        return original(self,pin)
    monkeypatch.setattr(ContractStore,'_blob_path',stable_parent)
    r=sample();writer.put_object(r.encoded,expected_sha256=r.sha256)
    assert writer.read_object(r.sha256)==r.encoded
