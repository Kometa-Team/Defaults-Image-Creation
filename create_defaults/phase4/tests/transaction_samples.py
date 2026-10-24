"""Disposable native M5 fixtures; database resets are test isolation only."""
from copy import deepcopy
from contextlib import closing
from dataclasses import replace
from pathlib import Path
import json
import sqlite3

import pytest
import yaml

from create_defaults.bulk.common import canonical
from create_defaults.bulk.lifecycle.candidates import poster_candidate
from create_defaults.bulk.lifecycle.composition import compose
from create_defaults.bulk.lifecycle.operations import Transaction, propose
from create_defaults.bulk.lifecycle.review import ReviewArchive, decision
from create_defaults.phase4.tests import composition_samples as cs, review_samples as rs


def reviewed(trial,ctx,*,label='transaction',exceptions=()):
    evidence = compose(ctx,trial,exceptions=exceptions)
    row = (trial,ctx,evidence,exceptions)
    inputs = cohort_inputs(row) if len(ctx.candidate.graph.index().outputs)>1 else rs.inputs(row)
    assert inputs.phase3.to_dict()['chain_compatible']
    actor = rs.authority(row)
    archive = ReviewArchive.create(trial.config.cache_dir)
    name = 'synthetic.review.'+label
    state = archive.start(name,submitter=rs.SUBMITTER,inputs=inputs)
    bundle = archive.read(name,expected_sha256=state.sha256)[1]
    decisions = []
    for action,person,role in [('confirm',rs.SUBMITTER,'submitter'),('approve',rs.MAINTAINER,'maintainer')]:
        record = decision(bundle,state,actor=person,action=action)
        actor.authorize(record,actor=person,role=role)
        state = archive.decide(record,expected_sha256=state.sha256,inputs=inputs,authority=actor)
        decisions.append(record)
    return dict(row=row,inputs=inputs,authority=actor,archive=archive,state=state,bundle=bundle,decisions=decisions)


def cohort_inputs(row):
    """One explicit English-only policy covering both existing exact variants.

    M4's single-subject fixture creates a policy per variant; those different
    values cannot stand in for one complete paired cohort. No runtime adapter,
    contract, historical record or production language policy is changed here.
    """
    from create_defaults.bulk.common import fingerprint
    from create_defaults.bulk.lifecycle.basis import historical_basis
    from create_defaults.bulk.lifecycle.candidates import resolve_stable
    from create_defaults.bulk.lifecycle.evidence import ReviewInputs,operation_payload
    from create_defaults.bulk.contracts.translation_preflight import PosterRequest,evaluate
    from create_defaults.bulk.contracts.translation_preflight.engine import prepare
    from create_defaults.bulk.contracts.translation_preflight.sources import selection_value
    from create_defaults.bulk.contracts.language_policy import LanguagePolicy,SourceVerificationContext
    from create_defaults.bulk.contracts.evidence_consumption import TranslationInput,RequestContext,consume
    from create_defaults.phase3.tests.translation_samples import policy_for,SyntheticCurrent
    from create_defaults.phase3.tests.consumption_samples import assemble
    _,ctx,composition,_=row;c=ctx.candidate;view=ctx.registry.view()
    resolution=resolve_stable(c.paths,c.profiles_path,view);requests=[]
    for i in composition.to_dict()['required_members']:
        e=view.entry(i);p=historical_basis().package(e['category'])
        outputs=[dict(id=i,identity_sha256=fingerprint(e),local_path=e['names']['local_path'],public_path=e['names']['public_path'])]
        requests.append(PosterRequest(resolution,i,p,p.contract.sha256,p.rules.sha256,e['variant'],canonical(outputs),c.graph.index().outputs[i]['context_sha256']))
    value=policy_for(requests[0]).to_dict()
    coverage={}
    for request in requests:
        entry=policy_for(request).to_dict()['coverage'][0];entry['languages']=['en'];coverage[fingerprint(entry)]=entry
    value['coverage']=[coverage[k] for k in sorted(coverage)]
    policy=LanguagePolicy.from_dict(value);snapshot=rs.english_snapshot();items=[]
    for request in requests:
        subject,*_,keys=prepare(request,policy,'en')
        selection=selection_value(policy,subject,'en',snapshot,keys,verification=dict(status='verified',issuer='synthetic-source',
            issuer_version='1.0.0',context_sha256=fingerprint('explicit-complete-artwork-reverification'),checked_at='2030-01-01T00:00:00Z',synthetic=True))
        context=None
        if selection is not None:
            v=selection.to_dict();claim=v['verification']
            context=SourceVerificationContext(selection_sha256=selection.sha256,source_sha256=fingerprint(v['source']),
                verification_context_sha256=claim['context_sha256'],commit=v['source']['commit'],tree=v['source']['tree'],
                issuer=claim['issuer'],issuer_version=claim['issuer_version'],as_of=claim['checked_at'])
        verifier=SyntheticCurrent();report=evaluate(request,policy,'en',snapshot,selection,context=context,verifier=verifier)
        items.append(TranslationInput(request,'en',snapshot,selection,report,report.sha256,context,verifier))
    values=assemble(items,policy,graph=c.graph);op=composition.to_dict()['operation']
    request=values['request_context'].to_dict();request.update(id=op['id'],revision=op['revision'],request_payload_sha256=operation_payload(composition))
    context=RequestContext.from_dict(request);values.update(request_context=context,expected_request_context_sha256=context.sha256)
    attestation=consume(**values)
    return ReviewInputs(ctx,composition.sha256,attestation,attestation.sha256,values)


def transaction(case,previous=None):
    ids = case['row'][1].candidate.graph.index().outputs
    expected = {i:None if previous is None else previous[i] for i in ids}
    tx = Transaction(case['inputs'],case['bundle'].to_dict()['id'],case['state'].sha256,canonical(expected).decode())
    return tx,tx.prepare()


@pytest.fixture
def transaction_case(transaction_seed):
    # Restore the owned fixture's SQLite backup between cases, not production
    # state and not a recovery implementation. Orphan blobs intentionally remain.
    case = transaction_seed
    path = case['row'][0].config.cache_dir/'state.sqlite3'
    with closing(sqlite3.connect(path)) as db:
        checkpoint = sqlite3.connect(':memory:')
        db.backup(checkpoint)
    actor = case['authority']
    # A material UPDATE may overwrite the owned source at its exact old name.
    # Preserve the fixture baseline separately from application recovery.
    from create_defaults.bulk.lifecycle.previews import CompositionArchive
    original_sources=case['row'][2].to_dict()['views'][0]['sources']
    archive=CompositionArchive(case['row'][0].config.cache_dir,readonly=True)
    assets={s['path']:archive.read_bytes(s['object_sha256']) for s in original_sources}
    grants, revoked, roles, as_of = dict(actor.grants),set(actor.revoked),dict(actor.roles),actor.as_of
    try:
        yield case
    finally:
        with closing(sqlite3.connect(path)) as db:
            checkpoint.backup(db)
        checkpoint.close()
        actor.grants,actor.revoked,actor.roles,actor.as_of = grants,revoked,roles,as_of
        for name,raw in assets.items():(case['row'][0].config.asset_dir/name).write_bytes(raw)


def update_candidate(case,*,before=None,label='updated'):
    trial, ctx, _, _ = case['row']
    original = ctx.candidate if before is None else before
    registry = ctx.registry
    identity = next(iter(original.graph.index().outputs))
    view = registry.view()
    entry = view.entry(identity)
    raw = cs.png()
    # Different transparent geometry at the exact same logical source filename.
    from PIL import Image, ImageDraw
    from io import BytesIO
    image = Image.open(BytesIO(raw));ImageDraw.Draw(image).rectangle((45,40,175,160),fill=(0,0,0,0))
    out=BytesIO();image.save(out,format='PNG')
    from create_defaults.bulk.lifecycle.operations import stage_source_update
    frozen,source=stage_source_update(original,trial,identity,out.getvalue(),expected_source_sha256=entry['names']['source']['sha256'])
    names=deepcopy(entry['names']);names['source']=source
    registry.revise(identity,names=names,entry_revision=entry['revision'],token=label,expected=view.head)
    definitions=deepcopy(original.data()['effective_definitions'])
    definitions[identity]['composer']['logo']=source['path']
    content=json.loads(original.content_json);content[identity]['source']=source
    path=trial.root/(label+'.yml')
    path.write_text(yaml.safe_dump(dict(schema_version=1,category=entry['category'],definitions=list(definitions.values()))),encoding='utf8')
    candidate=poster_candidate(registry,expected=registry.view().head,paths=[path],profiles_path=original.profiles_path,
        posters=sorted(content),content=content,config=trial.config)
    return candidate,frozen


def additional(case,label,*,shared=False):
    """Allocate a separate Genre identity, using the same closed native design."""
    trial,ctx,_,_=case['row'];r=ctx.registry;old=ctx.candidate
    original=next(iter(old.graph.index().outputs));entry=r.view().entry(original)
    names=deepcopy(entry['names'])
    for f in ('local_path','public_path'):
        names[f]=str(Path(names[f]).parent).replace('\\','/')+'/Fixture '+label+'.jpg'
    names['display_name']='Fixture '+label
    if not shared:
        names['source']=trial.stage(str(Path(names['source']['path']).parent).replace('\\','/')+'/Fixture '+label+'.png',cs.png())
    new=r.allocate(category=entry['category'],semantic=dict(entry['semantic'],key=label),variant=entry['variant'],
        names=names,token=label,expected=r.view().head)
    d=deepcopy(old.data()['effective_definitions'][original]);d.update(id=new['id'],display_name=names['display_name'])
    d['composer'].update(logo=names['source']['path'],out_name='Fixture '+label)
    d['output'].update(filename='Fixture '+label+'.jpg',remote_paths={'en':names['public_path']})
    path=trial.root/(label+'.yml');path.write_text(yaml.safe_dump(dict(schema_version=1,category=entry['category'],definitions=[d])),encoding='utf8')
    content=json.loads(old.content_json)[original];content.update(display_name=names['display_name'],source=names['source'])
    return path,{new['id']:content}


def additional_candidate(case,value):
    path,content=value;trial,ctx,_,_=case['row']
    return poster_candidate(ctx.registry,expected=ctx.registry.view().head,paths=[path],profiles_path=ctx.candidate.profiles_path,
        posters=sorted(content),content=content,config=trial.config)


def shared_cohort(trial):
    """Two real independently contracted Genre members sharing a source edge."""
    first=cs.poster(trial,'Genre');case={'row':(trial,first,None,[])}
    path,added=additional(case,'shared',shared=True)
    definitions=list(first.candidate.data()['effective_definitions'].values())+yaml.safe_load(path.read_text())['definitions']
    content=json.loads(first.candidate.content_json)|added
    source=trial.root/'cohort.yml';source.write_text(yaml.safe_dump(dict(schema_version=1,category='Genre',definitions=definitions)),encoding='utf8')
    candidate=poster_candidate(first.registry,expected=first.registry.view().head,paths=[source],profiles_path=first.candidate.profiles_path,
        posters=sorted(content),content=content,config=trial.config)
    return propose(first.registry,before=None,candidate=candidate,identity='synthetic.operation.multi-member',operation='ADD')


def shared_update(case):
    from create_defaults.bulk.lifecycle.operations import stage_source_update
    trial,ctx,_,_=case['row'];before=ctx.candidate;r=ctx.registry
    first=next(iter(before.graph.index().outputs));entry=r.view().entry(first)
    from PIL import Image,ImageDraw
    from io import BytesIO
    image=Image.open(BytesIO(cs.png()));ImageDraw.Draw(image).rectangle((45,40,175,160),fill=(0,0,0,0))
    output=BytesIO();image.save(output,format='PNG')
    frozen,source=stage_source_update(before,trial,first,output.getvalue(),expected_source_sha256=entry['names']['source']['sha256'])
    content=json.loads(before.content_json)
    for i in before.graph.index().outputs:
        e=r.view().entry(i);assert e['names']['source']['path']==source['path']
        names=deepcopy(e['names']);names['source']=source
        r.revise(i,names=names,entry_revision=e['revision'],token='shared-update-'+i,expected=r.view().head)
        content[i]['source']=source
    path=trial.root/'cohort-update.yml';path.write_text(yaml.safe_dump(dict(schema_version=1,category='Genre',definitions=list(before.data()['effective_definitions'].values()))),encoding='utf8')
    candidate=poster_candidate(r,expected=r.view().head,paths=[path],profiles_path=before.profiles_path,
        posters=sorted(content),content=content,config=trial.config)
    return candidate,frozen
