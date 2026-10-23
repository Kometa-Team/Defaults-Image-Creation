"""Synthetic coordination metadata only: no catalog/artwork or actual identity intake."""

from create_defaults.bulk.common import fingerprint
from create_defaults.bulk.lifecycle.models import Operation, namespace_key, key


def sample(store=None, *, name="one", operation="UPDATE", subjects=("a",), paths=None,
           extra_heads=(), write_extras=False):
    subjects=sorted("synthetic.subject."+s for s in subjects)
    heads={key(h):h for h in store.inspect()["heads"]} if store else {}
    spaces=[dict(namespace="synthetic.repository",path=path,subjects=subjects)
            for path in (paths if paths is not None else ["posters/"+name+".jpg"])]
    spaces.sort(key=lambda n:key(namespace_key(n['namespace'],n['path'])))
    selected=[dict(kind="subject",id=s) for s in subjects]
    selected += [namespace_key(n['namespace'],n['path']) for n in spaces]
    selected += list(extra_heads)
    reads=[]
    for k in sorted(selected,key=key):
        current=heads.get(key(k),dict(revision=0,sha256=None))
        reads.append(dict(**k,subjects=[k['id']] if k['kind']=='subject' else subjects,
            revision=current['revision'],sha256=current['sha256']))
    writes=[k for k in selected if k['kind'] in {'subject','namespace'} or write_extras]
    flags=dict(schema_version=1,protocol_version="1.0.0",scope="isolated-synthetic-records",simulation=True,record_only=True,
        operation_accepted=False,applied=False,artwork_approved=False,contract_approved=False,
        ready=False,active=False,production_enforcement=False,publication_authorized=False)
    refs=[dict(kind="tombstone",id=s+".tombstone",subject=s,sha256=fingerprint([s,'retirement-evidence-only'])) for s in subjects] if operation=='DELETE' else []
    value=dict(**flags,kind="operation-record",id="synthetic.operation."+name,operation=operation,
        revision=1,content_revision=1,previous_sha256=None,previous_event_sha256=None,state="draft",reason=None,
        request_sha256=fingerprint(dict(description='explicit synthetic request, no actual operation',name=name)),
        subjects=[dict(id=s,before_sha256=None if operation=='ADD' else fingerprint([s,'before']),
            proposed_sha256=None if operation=='DELETE' else fingerprint([s,'proposed'])) for s in subjects],
        reads=reads,writes=sorted(writes,key=key),namespaces=spaces,references=refs)
    return Operation.from_dict(value)


def append(store, record):
    v=record.to_dict()
    return store.append(record,expected_revision=v['revision']-1,expected_sha256=v['previous_sha256'],expected_event_sha256=v['previous_event_sha256'])


def next_record(store, before, *, state='structurally_validated', change=False):
    v=before.to_dict();events=store.journal();previous=next(e for e in events if e.to_dict()['record_sha256']==before.sha256)
    heads={key(h):h for h in store.inspect()['heads']}
    v.update(revision=v['revision']+1,previous_sha256=before.sha256,previous_event_sha256=previous.sha256,
        state=state,reason='explicit synthetic diagnostic' if state in {'cancelled','conflicted','stale'} else None)
    for r in v['reads']:
        current=heads.get(key(r),dict(revision=0,sha256=None))
        r.update(revision=current['revision'],sha256=current['sha256'])
    if change:
        v['request_sha256']=fingerprint(['new synthetic content',v['revision']]);v['content_revision']+=1
    return Operation.from_dict(v)
