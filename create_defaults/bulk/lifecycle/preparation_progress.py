"""Versioned preparation progress in the original Package E immutable journal."""
import json
import re

from ..common import canonical, fingerprint, Conflict
from ..contracts.models import decode_json
from .package_e import SidecarStore
from .preparation_models import Preparation, MAX_EVENTS, MAX_DOCUMENT, diagnostic, fail

KIND='phase5_offline_preparation'
STATES={'PREPARED','INCOMPLETE','UNKNOWN','OFFLINE_VERIFIED'}
KEYS={'version','kind','preparation_sha256','revision','previous_sha256','state',
    'verified_batches','planned_batches','head','failure','simulation','publication_authorized'}


def _read(store,db,preparation):
    rows=db.execute('SELECT subject,payload FROM events WHERE kind=? ORDER BY sequence',(KIND,)).fetchmany(MAX_EVENTS+1)
    if len(rows)>MAX_EVENTS or sum(len(r['payload']) for r in rows)>MAX_DOCUMENT:fail('journal_bound')
    states={}
    for row in rows:
        payload=decode_json(row['payload'].encode())
        if set(payload)!={'sha256'}:fail('journal_index')
        value=decode_json(store.read_object(payload['sha256']))
        if set(value)!=KEYS or value['version']!=1 or value['kind']!=KIND or value['state'] not in STATES:fail('journal_schema')
        pin=fingerprint(value);identity=value['preparation_sha256'];prior=states.get(identity)
        if pin!=payload['sha256'] or identity!=row['subject'] or value['simulation'] is not True or value['publication_authorized'] is not False:fail('journal_binding')
        if value['revision']!=(1 if prior is None else prior['revision']+1) or value['previous_sha256']!=(None if prior is None else prior['sha256']):fail('journal_chain')
        if (type(value['revision']) is not int or type(value['planned_batches']) is not int
                or type(value['verified_batches']) is not int or not 0<=value['verified_batches']<=value['planned_batches']<=32
                or value['head'] is not None and (not isinstance(value['head'],str) or re.fullmatch('[0-9a-f]{40}',value['head']) is None)):fail('journal_count')
        if prior is None and (value['state']!='PREPARED' or value['verified_batches']!=0):fail('journal_initial')
        if prior is not None and (value['planned_batches']!=prior['planned_batches'] or value['verified_batches']<prior['verified_batches']):fail('journal_regression')
        if value['state']=='OFFLINE_VERIFIED' and value['verified_batches']!=value['planned_batches']:fail('journal_incomplete')
        if value['failure'] is not None:
            failure=value['failure']
            if (type(failure) is not dict or set(failure)!={'category','operation_sha256','correlation_id'}
                    or failure['operation_sha256']!=identity or not isinstance(failure['category'],str)
                    or re.fullmatch('[a-z0-9_]{1,80}',failure['category']) is None or failure['correlation_id']!=fingerprint(dict(operation=identity,category=failure['category']))[:32]):fail('journal_diagnostic')
        states[identity]=dict(value,sha256=pin)
    selected=states.get(preparation.sha256)
    if selected and selected['planned_batches']!=len(preparation.to_dict()['plan']['batches']):fail('journal_plan')
    return selected


class Progress:
    def __init__(self,root,preparation):
        if type(preparation) is not Preparation:fail('typed_preparation')
        self.root=root;self.preparation=preparation

    def read(self):
        store=SidecarStore.open_readonly(self.root)
        if Preparation.from_bytes(store.read_object(self.preparation.sha256)).encoded!=self.preparation.encoded:fail('preparation_object')
        with store.read_connection() as db:return _read(store,db,self.preparation)

    def append(self,state,count,head,*,expected,error=None,target=None,checkpoint=lambda name:None):
        if state not in STATES:fail('journal_state')
        if type(count) is not int or count<0 or head is not None and (not isinstance(head,str) or re.fullmatch('[0-9a-f]{40}',head) is None):fail('journal_count')
        if state in {'INCOMPLETE','OFFLINE_VERIFIED'}:
            from .publication_preparation import OfflineDestination,inspect_transport
            from ..common import confined
            if type(target) is not OfflineDestination:fail('actual_observation_required')
            root=confined(target.trial.root,'m5-transport-'+self.preparation.sha256)
            actual=inspect_transport(self.preparation,target,root)
            if (actual['verified_batches'],actual['head'],actual['complete'])!=(count,head,state=='OFFLINE_VERIFIED'):fail('progress_observation')
        store=SidecarStore(self.root)
        # The complete immutable intent is pinned before, and exposed only by,
        # the successful original Store transaction; orphan objects are retained.
        store.put_object(self.preparation.encoded,expected_sha256=self.preparation.sha256)
        checkpoint('intent_object')
        with store.transaction() as db:
            from .storage import _replay
            heads=_replay(store,db)[3]
            for expected_head in self.preparation.to_dict()['native_heads']:
                k=(expected_head['kind'],expected_head['id'])
                if state!='UNKNOWN' and heads.get(k,dict(kind=k[0],id=k[1],subjects=[],revision=0,sha256=None))!=expected_head:raise Conflict('Native scoped heads changed')
            from .operations import DefinitionSnapshot
            snapshot=DefinitionSnapshot.from_bytes(store.read_object(self.preparation.to_dict()['snapshot_sha256'])).to_dict()
            review=db.execute('SELECT sha256 FROM p4m4_reviews WHERE id=? ORDER BY revision DESC LIMIT 1',(snapshot['review_id'],)).fetchone()
            if state!='UNKNOWN' and (not review or review[0]!=snapshot['review_sha256']):raise Conflict('Native review changed')
            current=_read(store,db,self.preparation)
            if current!=expected:raise Conflict('Preparation progress changed')
            if current is None and state!='PREPARED':fail('journal_initial')
            if state=='PREPARED' and (current is not None or count!=0 or head is not None):fail('journal_initial')
            if current is not None and count<current['verified_batches']:fail('journal_regression')
            if state=='UNKNOWN' and (count,head)!=(current['verified_batches'],current['head']):fail('journal_unknown_observation')
            value=dict(version=1,kind=KIND,preparation_sha256=self.preparation.sha256,
                revision=1 if current is None else current['revision']+1,
                previous_sha256=None if current is None else current['sha256'],state=state,
                verified_batches=count,planned_batches=len(self.preparation.to_dict()['plan']['batches']),head=head,
                failure=None if error is None else diagnostic(error,self.preparation.sha256),
                simulation=True,publication_authorized=False)
            if not 0<=count<=value['planned_batches'] or state=='OFFLINE_VERIFIED' and count!=value['planned_batches']:fail('journal_incomplete')
            pin=fingerprint(value);store.put_object(canonical(value),expected_sha256=pin)
            checkpoint('progress_object')
            store.event(db,KIND,self.preparation.sha256,dict(sha256=pin))
            checkpoint('before_progress_commit')
        checkpoint('after_progress_commit')
        return dict(value,sha256=pin)


def recover(root,preparation_sha256):
    store=SidecarStore.open_readonly(root)
    preparation=Preparation.from_bytes(store.read_object(preparation_sha256))
    return dict(preparation_sha256=preparation.sha256,progress=Progress(root,preparation).read(),
        currentness='integrity-only; fresh source, mapping and permission observation required',
        simulation=True,publication_authorized=False,ready=False,active=False)
