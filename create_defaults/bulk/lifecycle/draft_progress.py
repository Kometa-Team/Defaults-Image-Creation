"""Append-only offline draft progress in the existing Package E database."""
import re
from ..common import canonical,fingerprint,Conflict
from ..contracts.models import decode_json
from .package_e import SidecarStore
from .draft_models import DraftBinding,fail
from .preparation_models import MAX_EVENTS,MAX_DOCUMENT,diagnostic

KIND='phase5_offline_draft'
STATES={'PREPARED','INCOMPLETE','UNKNOWN','OFFLINE_DRAFT_VERIFIED'}
KEYS={'version','kind','binding_sha256','revision','previous_sha256','state','verified_batches',
      'planned_batches','head','draft_sha256','failure','simulation','publication_authorized'}


def native_heads(store,db,preparation):
    from .storage import _replay
    from .operations import DefinitionSnapshot,payload
    heads=_replay(store,db)[3];v=preparation.to_dict()
    snapshot=DefinitionSnapshot.from_bytes(store.read_object(v['snapshot_sha256'])).to_dict()
    refs={(r['kind'],r['id']):r for r in payload(snapshot['intent_json'])['reads']}
    for expected in v['native_heads']:
        key=(expected['kind'],expected['id']);actual=heads.get(key)
        if actual is None:
            actual=refs.get(key)
            if actual is None or (actual['revision'],actual['sha256'])!=(0,None):raise Conflict('Native draft heads changed')
        if actual!=expected:raise Conflict('Native draft heads changed')
    review=db.execute('SELECT sha256 FROM p4m4_reviews WHERE id=? ORDER BY revision DESC LIMIT 1',(snapshot['review_id'],)).fetchone()
    if not review or review[0]!=snapshot['review_sha256']:raise Conflict('Native draft review changed')


def _read(store,db,binding):
    rows=db.execute('SELECT subject,payload FROM events WHERE kind=? ORDER BY sequence',(KIND,)).fetchmany(MAX_EVENTS+1)
    if len(rows)>MAX_EVENTS or sum(len(r['payload']) for r in rows)>MAX_DOCUMENT:fail('journal_bound')
    states={}
    for row in rows:
        index=decode_json(row['payload'].encode())
        if set(index)!={'sha256'}:fail('journal_index')
        value=decode_json(store.read_object(index['sha256']));identity=value.get('binding_sha256');previous=states.get(identity)
        if (set(value)!=KEYS or fingerprint(value)!=index['sha256'] or row['subject']!=identity
                or value['version']!=1 or type(value['version']) is not int or value['kind']!=KIND
                or value['simulation'] is not True or value['publication_authorized'] is not False
                or value['state'] not in STATES):fail('journal_schema')
        if (type(value['revision']) is not int or value['revision']!=(1 if previous is None else previous['revision']+1)
                or value['previous_sha256']!=(None if previous is None else previous['sha256'])):fail('journal_chain')
        if (type(value['verified_batches']) is not int or type(value['planned_batches']) is not int
                or not 0<=value['verified_batches']<=value['planned_batches']<=32):fail('journal_count')
        if not isinstance(identity,str) or re.fullmatch('[0-9a-f]{64}',identity) is None:fail('journal_hash')
        for field,size in [('head',40),('draft_sha256',64)]:
            if value[field] is not None and (not isinstance(value[field],str) or re.fullmatch('[0-9a-f]{'+str(size)+'}',value[field]) is None):fail('journal_hash')
        if value['state'] in {'INCOMPLETE','OFFLINE_DRAFT_VERIFIED'} and value['head'] is None:fail('journal_observation')
        if value['state']=='INCOMPLETE' and value['draft_sha256'] is not None:fail('journal_observation')
        if value['failure'] is not None:
            failure=value['failure']
            if (type(failure) is not dict or set(failure)!={'category','operation_sha256','correlation_id'}
                    or failure['operation_sha256']!=identity or not isinstance(failure['category'],str)
                    or re.fullmatch('[a-z0-9_]{1,80}',failure['category']) is None
                    or failure['correlation_id']!=fingerprint(dict(operation=identity,category=failure['category']))[:32]):fail('journal_diagnostic')
        if previous is None and (value['state']!='PREPARED' or value['verified_batches']!=0
                or value['head'] is not None or value['draft_sha256'] is not None or value['failure'] is not None):fail('journal_initial')
        if previous is not None and (value['state']=='PREPARED' or value['planned_batches']!=previous['planned_batches']
                or value['verified_batches']<previous['verified_batches']):fail('journal_regression')
        if value['state']=='UNKNOWN' and (value['head'],value['verified_batches'],value['draft_sha256'])!=(previous['head'],previous['verified_batches'],previous['draft_sha256']):fail('journal_unknown')
        if value['state']=='OFFLINE_DRAFT_VERIFIED' and (value['verified_batches']!=value['planned_batches'] or value['draft_sha256'] is None):fail('journal_incomplete')
        states[identity]=dict(value,sha256=index['sha256'])
    current=states.get(binding.sha256)
    if current and current['planned_batches']!=len(binding.to_dict()['plan']['batches']):fail('journal_binding')
    return current


class DraftProgress:
    def __init__(self,root,binding):
        if type(binding) is not DraftBinding:fail('binding_type')
        self.root=root;self.binding=binding

    def read(self):
        store=SidecarStore.open_readonly(self.root)
        if store.read_object(self.binding.sha256)!=self.binding.encoded:fail('binding_object')
        with store.read_connection() as db:return _read(store,db,self.binding)

    def append(self,state,*,expected,observation=None,error=None,protocol=None):
        from .preparation_models import Preparation
        if state not in STATES:fail('journal_state')
        if state=='PREPARED' and (expected is not None or observation is not None or error is not None):fail('journal_initial')
        if state=='UNKNOWN' and (expected is None or observation is not None):fail('journal_unknown')
        if state in {'INCOMPLETE','OFFLINE_DRAFT_VERIFIED'}:
            from .draft_transport import OfflineProtocol
            if type(protocol) is not OfflineProtocol or OfflineProtocol.inspect(protocol)!=observation:fail('actual_observation_required')
            if state=='OFFLINE_DRAFT_VERIFIED' and not observation['draft_verified']:fail('journal_incomplete')
            if state=='INCOMPLETE' and observation['draft_verified']:fail('journal_observation')
        store=SidecarStore(self.root);store.put_object(self.binding.encoded,expected_sha256=self.binding.sha256)
        with store.transaction() as db:
            if state!='UNKNOWN':native_heads(store,db,Preparation.from_dict(self.binding.to_dict()['preparation']))
            current=_read(store,db,self.binding)
            if current!=expected:raise Conflict('Draft progress changed')
            if current is None and state!='PREPARED':fail('journal_initial')
            if state=='UNKNOWN':
                if current is None:fail('journal_initial')
                count,head,draft=(current[k] for k in ('verified_batches','head','draft_sha256'))
            elif observation is None:count,head,draft=0,None,None
            else:count,head,draft=(observation[k] for k in ('verified_batches','head','draft_sha256'))
            value=dict(version=1,kind=KIND,binding_sha256=self.binding.sha256,
                revision=1 if current is None else current['revision']+1,
                previous_sha256=None if current is None else current['sha256'],state=state,
                verified_batches=count,planned_batches=len(self.binding.to_dict()['plan']['batches']),
                head=head,draft_sha256=draft,failure=None if error is None else diagnostic(error,self.binding.sha256),
                simulation=True,publication_authorized=False)
            pin=fingerprint(value);store.put_object(canonical(value),expected_sha256=pin)
            store.event(db,KIND,self.binding.sha256,dict(sha256=pin))
        # Re-read using the same strict cold replay, never return an invented state.
        return self.read()


def recover(root,binding_sha256):
    store=SidecarStore.open_readonly(root);binding=DraftBinding.from_bytes(store.read_object(binding_sha256))
    return dict(binding_sha256=binding.sha256,progress=DraftProgress(root,binding).read(),
                currentness='integrity-only; fresh authority required',simulation=True,publication_authorized=False)
