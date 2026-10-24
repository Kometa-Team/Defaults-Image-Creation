"""M2 read-only planning security: real frozen mappings, isolated metadata only."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import shutil

import pytest
import yaml

from create_defaults.bulk.common import BulkError, Conflict, canonical, fingerprint, sha256
from create_defaults.bulk.config import Config, ROOT
from create_defaults.bulk.lifecycle.basis import historical_basis, semantic_tokens
from create_defaults.bulk.lifecycle.coverage import matrix, require_variant
from create_defaults.bulk.lifecycle.identities import IdentityRegistry, RegistryHead, transition
from create_defaults.bulk.lifecycle.identity_models import RegistrySnapshot, ImpactEvidence
from create_defaults.bulk.lifecycle.candidates import poster_candidate, StablePlanner
from create_defaults.bulk.lifecycle.overlay_candidates import overlay_candidate
from create_defaults.bulk.lifecycle.impact import HistoricalGraph, preview_impact, request_record, operation_head, analyze, revalidate
from create_defaults.phase3.tests.destination_samples import inventory, USER


@pytest.fixture
def registry(tmp_path):
    inv=inventory(USER,'Main',{'existing/Reserved.jpg':'100644'})
    return IdentityRegistry.create(tmp_path/'state','synthetic-registry',inventory=inv,expected_inventory_sha256=inv.sha256)


def names(label='Synthetic', source=None):
    return dict(display_name=label,rendered_caption='TIMELINE ORDER',source=source or dict(path='logos_playlist/Arrowverse.png',sha256='f'*64),
        local_path='defaults-en/playlist/'+label+'.jpg',public_path='playlist/'+label+'.jpg')


def allocate(registry,key='synthetic',**kwargs):
    return registry.allocate(category=kwargs.pop('category','Playlist'),semantic=kwargs.pop('semantic',dict(parent=None,key=key,role='single',language='en')),
        variant=kwargs.pop('variant','timeline-order'),names=kwargs.pop('names',names()),token=kwargs.pop('token',key),expected=kwargs.pop('expected',registry.view().head),**kwargs)


def test_uuid_stable_names_paths_casing_unicode_aliases_restart(registry):
    a=allocate(registry); initial=deepcopy(a['names']);head=registry.view().head
    changed=names('Synthetíc!');changed['public_path']='playlist/synthetíc!.jpg'
    changed['source']=dict(path='logos_playlist/Synthetic Renamed.png',sha256='b'*64)
    changed['rendered_caption']='A RENAMED CAPTION'
    b=registry.revise(a['id'],changed,entry_revision=1,token='rename',expected=head)
    assert a['id']==b['id'] and b['original_names']==initial and b['revision']==2
    assert {('public',initial['public_path']),('local',initial['local_path'])} <= {(r['namespace'],r['value']) for r in b['aliases']}
    reopened=IdentityRegistry(registry.operations.root,registry.identity)
    assert reopened.view().snapshot.encoded==registry.view().snapshot.encoded
    assert reopened.view().lookup('Playlist',None,'synthetic')==a['id']
    assert not reopened.view().snapshot.to_dict()['active']


def test_duplicate_semantic_and_changed_idempotency_token_fail(registry):
    a=allocate(registry);assert allocate(registry)==a
    with pytest.raises(Conflict):allocate(registry,token='another')
    with pytest.raises(Conflict):allocate(registry,key='different',token='synthetic')


def test_concurrent_allocation_exactly_one_wins(registry):
    head=registry.view().head
    def run(n):
        try:return allocate(registry,token='race-'+str(n),expected=head)
        except Conflict:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
    assert sum(r is not None for r in results)==1
    assert len(registry.view().entries())==1


@pytest.mark.parametrize('change',[
    {'public_path':'existing/Reserved.jpg'}, {'public_path':'playlist/../escape.jpg'},
    {'local_path':'defaults-en/playlist/CON.jpg'}, {'public_path':'playlist/Cafe\u0301.jpg'},
    {'public_path':'playlist/a:b.jpg'}, {'public_path':'playlist/X.jpg/child.jpg'},
])
def test_nonportable_external_and_reserved_names_fail(registry,change):
    n=names();n.update(change)
    if 'X.jpg/child.jpg' in n['public_path']:
        first=names('Other');first['public_path']='playlist/X.jpg';allocate(registry,key='first',names=first)
    with pytest.raises((BulkError,Conflict)):allocate(registry,names=n)


@pytest.mark.parametrize('rename',['Synthetic','synthetic'])
def test_alias_and_tombstone_never_release_names(registry,rename):
    a=allocate(registry)
    registry.revise(a['id'],names('Moved'),entry_revision=1,token='move',expected=registry.view().head,tombstone_sha256='a'*64)
    with pytest.raises((BulkError,Conflict)):allocate(registry,key='other',names=names(rename))
    with pytest.raises(BulkError):registry.revise(a['id'],names('Again'),entry_revision=2,token='revive',expected=registry.view().head)


def test_punctuation_distinct_categories_shared_source_and_names(registry):
    a=allocate(registry,names=names('A-B'))
    b=allocate(registry,key='different',names=names('A B'))
    assert a['id']!=b['id'] and a['names']['source']==b['names']['source']
    package=historical_basis().package('Studio');rules,_=package.data()
    variant=next(k for k,r in rules.items() if r['required_presentations']==['single'])
    n=names('A-B');n.update(local_path='defaults-en/studio/A-B.jpg',public_path='studio/A-B.jpg')
    c=allocate(registry,key='studio',category='Studio',variant=variant,names=n)
    assert c['category']!=a['category'] and c['names']['display_name']==a['names']['display_name'] and c['id']!=a['id']


@pytest.mark.parametrize('field,value',[('active',True),('publication_authorized',True),('schema_version',2),('forged',True)])
def test_registry_closed_schema_no_authority(registry,field,value):
    raw=registry.view().snapshot.to_dict();raw[field]=value
    with pytest.raises(BulkError):RegistrySnapshot.from_dict(raw)


def test_forged_historical_reference_and_substitution_fail(registry):
    with pytest.raises(BulkError):registry.reference('playlist.forged',token='fake',expected=registry.view().head)
    historic=next(i for i in sorted(historical_basis().ids) if historical_basis().row(i)['identity']['category']=='Playlist')
    a=registry.reference(historic,token='reference',expected=registry.view().head)
    assert a['id']==historic and a['origin']=='historical-reference'
    from create_defaults.bulk.contracts.playlist import PlaylistBoundary
    from create_defaults.bulk.contracts.playlist.validation import CONTRACT_SHA256,REGISTRY_SHA256,M2_SHA256
    from create_defaults.bulk.lifecycle.candidates import playlist_mapping
    boundary=PlaylistBoundary.load(contract_sha256=CONTRACT_SHA256,registry_sha256=REGISTRY_SHA256,adoption_sha256=M2_SHA256)
    actual=boundary.record(historic).to_dict();definition=json.loads(actual['effective_definition_json']);job=json.loads(actual['job_json'])
    content={k:a['names'][k] for k in ('display_name','source')}
    playlist_mapping(a,definition,job,content)
    for field,value in [('source',dict(path=a['names']['source']['path'],sha256='0'*64)),('public_path','playlist/Substituted.jpg'),('display_name','Substituted'),('rendered_caption','FORGED')]:
        substituted=deepcopy(a);substituted['names'][field]=value
        c={k:substituted['names'][k] for k in ('display_name','source')}
        with pytest.raises(BulkError):playlist_mapping(substituted,definition,job,c)
    before=registry.view().snapshot;v=before.to_dict();v['revision']+=1;v['previous_sha256']=before.sha256
    v['entries'][0]['historical_sha256']='0'*64
    v['requests'].append(dict(token='z-forge',request_sha256='a'*64,result_id=historic))
    with pytest.raises(BulkError):transition(before,RegistrySnapshot.from_dict(v),[])


def test_corrupt_registry_blob_rejected_after_restart(registry):
    a=allocate(registry);head=registry.view().head
    root=registry.operations.root
    candidates=[p for p in Path(root).rglob('*') if p.is_file() and p.name==head.snapshot_sha256]
    if not candidates:
        candidates=[p for p in Path(root).rglob('*') if p.is_file() and p.read_bytes()==registry.view().snapshot.encoded]
    assert len(candidates)==1
    candidates[0].write_bytes(b'{}')
    with pytest.raises(BulkError):IdentityRegistry(root,registry.identity)


def test_stale_registry_head_and_semantic_parent_rejected(registry):
    head=registry.view().head;allocate(registry)
    with pytest.raises(Conflict):allocate(registry,key='next',names=names('Next'),expected=head)
    with pytest.raises(BulkError):allocate(registry,key='child',semantic=dict(parent='playlist.'+'a'*32,key='child',role='single',language='en'),names=names('Child'))


def test_all_frozen_semantic_members_and_coverage_are_exact(monkeypatch):
    b=historical_basis();index=b.semantic_index();assert len(index)==len(b.ids)==14079
    assert set(index.values())==b.ids
    assert sum(b.row(i)['identity']['public_path'] is not None for i in b.ids)==14077
    r=b.resolution.data();kinds=set();inverse={v:k for k,v in index.items()}
    for parent,children in r['families'].items():
        d=r['declared'][parent];kinds.add(d['generator']['name'])
        tokens=semantic_tokens(d);assert len(tokens)==len(children)
        for token,child in zip(tokens,children):
            assert inverse[child][1:3]==(parent,token)
    assert kinds=={'award-years','best-of-years','separator-variants','content-rating-series'}
    m=matrix();assert len(m['categories'])==22 and len(m['variants'])==278 and len(m['overlays'])==18
    assert len(m['generators'])==4 and not m['active']
    from create_defaults.bulk.lifecycle import coverage
    original=Path.read_bytes
    with monkeypatch.context() as guard:
        guard.setattr(Path,'read_bytes',lambda p:b'forged catalog' if p==coverage.CATALOG else original(p))
        with pytest.raises(BulkError):matrix()


@pytest.mark.parametrize('category,variant',[('Playlist','unknown'),('Overlays','fake'),('Unknown','fake')])
def test_unknown_category_adapters_block(category,variant):
    with pytest.raises(BulkError):require_variant(category,variant)


def test_fake_historical_graph_and_unsupported_candidate_block():
    from create_defaults.bulk.contracts.expanded.graph import Snapshot
    fake=Snapshot.create(dict(schema_version=1,kind='m5-dependency-snapshot',basis='a'*64,nodes={},outputs={},unresolved=[]))
    with pytest.raises(BulkError):HistoricalGraph.select(fake)
    with pytest.raises(BulkError):preview_impact(None,object())
    with pytest.raises(BulkError):poster_candidate(object(),expected=None,paths=[],profiles_path=None,posters=[],content={})
    with pytest.raises(BulkError):overlay_candidate(object(),expected=None,identities=[])
    with pytest.raises(BulkError):request_record(object(),None,None,identity='synthetic.operation.forged')
    with pytest.raises(BulkError):analyze(object(),None,None,operation=None,expected_operation_sha256='0'*64)


@pytest.fixture
def playlist(registry,tmp_path):
    from create_defaults.bulk.tests.test_playlist_contract import proposed_definition
    from create_defaults.bulk.contracts.playlist import PlaylistBoundary
    from create_defaults.bulk.contracts.playlist.validation import CONTRACT_SHA256,REGISTRY_SHA256,M2_SHA256
    from create_defaults.bulk.contracts.models import Identity
    boundary=PlaylistBoundary.load(contract_sha256=CONTRACT_SHA256,registry_sha256=REGISTRY_SHA256,adoption_sha256=M2_SHA256)
    config=Config(cache_dir=tmp_path/'cache',workspace_dir=tmp_path/'workspace',output_dir=tmp_path/'output')
    source=dict(path='logos_playlist/Arrowverse.png',sha256=sha256(ROOT/'logos_playlist/Arrowverse.png'))
    n=names('Brand',source);n.update(local_path='defaults-en/playlist/Brand (Timeline Order).jpg',public_path='playlist/Brand (Timeline Order).jpg')
    entry=allocate(registry,names=n)
    identity=Identity.from_dict(dict(schema_version=1,kind='item-identity',id=entry['id'],category='Playlist',semantic_member=None,**n))
    content=dict(display_name='Brand',source=source,background_proposal='#123456',content_type='timeline-order')
    definition=proposed_definition(boundary,content,identity)
    path=tmp_path/'candidate.yml';profiles=tmp_path/'profiles.yml'
    profiles.write_text(yaml.safe_dump(dict(schema_version=1,profiles={})),encoding='utf8')
    def build(mutate=None):
        d=deepcopy(definition)
        if mutate:mutate(d)
        path.write_text(yaml.safe_dump(dict(schema_version=1,category='Playlist',definitions=[d])),encoding='utf8')
        return poster_candidate(registry,expected=registry.view().head,paths=[path],profiles_path=profiles,posters=[entry['id']],content={entry['id']:content},config=config)
    return registry,entry,build,path,profiles,definition,content,config


def test_actual_playlist_plan_operation_bound_impact_and_replay(playlist):
    registry,entry,build,*_=playlist;candidate=build()
    assert candidate.data()['manifest']['jobs'][0]['poster_id']==entry['id']
    assert candidate.verify().sha256==candidate.sha256
    with pytest.raises(BulkError):request_record(registry,None,candidate,identity='synthetic.operation.invalid',operation='RENAME')
    record=request_record(registry,None,candidate,identity='synthetic.operation.proposal',operation='ADD')
    registry.operations.append(record,expected_revision=0,expected_sha256=None,expected_event_sha256=None)
    head=operation_head(registry.operations,'synthetic.operation.proposal')
    evidence=analyze(registry,None,candidate,operation=head,expected_operation_sha256=head.sha256)
    details=json.loads(evidence.to_dict()['details_json'])
    assert details['affected_outputs']==[entry['id']] and details['complete'] and details['reasons'][entry['id']]
    assert details['read_set'] and details['write_set'] and not evidence.to_dict()['operation_accepted']
    assert revalidate(evidence,expected_sha256=evidence.sha256,registry=registry,before=None,after=candidate).encoded==evidence.encoded
    with pytest.raises(BulkError):analyze(registry,None,candidate,operation=replace(head,sha256='0'*64),expected_operation_sha256=head.sha256)
    with pytest.raises(BulkError):revalidate(evidence,expected_sha256='0'*64,registry=registry,before=None,after=candidate)
    forged=evidence.to_dict();detail=json.loads(forged['details_json']);detail['reasons'][entry['id']][0]['cause']='forged'
    forged['details_json']=canonical(detail).decode();forged=ImpactEvidence.from_dict(forged)
    with pytest.raises(BulkError):revalidate(forged,expected_sha256=forged.sha256,registry=registry,before=None,after=candidate)
    from create_defaults.phase4.tests.samples import next_record
    updated=next_record(registry.operations,record,state='cancelled')
    registry.operations.append(updated,expected_revision=1,expected_sha256=record.sha256,expected_event_sha256=head.event_sha256)
    with pytest.raises(Conflict):analyze(registry,None,candidate,operation=head,expected_operation_sha256=head.sha256)
    allocate(registry,key='other',names=names('Other'))
    with pytest.raises(Conflict):revalidate(evidence,expected_sha256=evidence.sha256,registry=registry,before=None,after=candidate)


@pytest.mark.parametrize('attack',[
    lambda d:d['composer'].update(font_size=100),
    lambda d:d['composer'].update(white_wash=False),
    lambda d:d['composer'].update(gradient=99),
    lambda d:d['composer'].update(font='fonts/Missing.ttf'),
    lambda d:d['composer'].update(avg_color_image='missing.png'),
    lambda d:d['overrides'].append(dict(language='en',changes=dict(composer=dict(font_size=100)))),
    lambda d:d.update(languages=['en','fr']),
    lambda d:d['dependencies'].append(dict(poster_id='playlist.forged',input='logo')),
    lambda d:d.update(generator=dict(name='unknown',version=1,parameters={})),
])
def test_actual_expanded_candidate_bypass_rejected(playlist,attack):
    with pytest.raises(BulkError):playlist[2](attack)


def test_candidate_changed_source_context_cannot_replay(playlist):
    candidate=playlist[2]();path=playlist[3]
    path.write_text(path.read_text(encoding='utf8')+'\n# changed source context\n',encoding='utf8')
    # Source bytes are part of Resolution pins even when effective YAML is equal.
    with pytest.raises(BulkError):candidate.verify()


def test_profile_override_cannot_hide_style_changes(playlist):
    profiles=playlist[4]
    profiles.write_text(yaml.safe_dump(dict(schema_version=1,profiles={'attack':{'composer':{'font_size':100}}})),encoding='utf8')
    def attack(d):d.update(extends='attack');d['composer'].pop('font_size')
    with pytest.raises(BulkError):playlist[2](attack)


def test_case_only_rename_retains_exact_stable_identity(registry):
    a=allocate(registry);n=deepcopy(a['names']);n['public_path']='playlist/synthetic.jpg'
    b=registry.revise(a['id'],n,entry_revision=1,token='case',expected=registry.view().head)
    assert a['id']==b['id'] and b['names']['public_path']=='playlist/synthetic.jpg'
    assert dict(namespace='public',value='playlist/Synthetic.jpg') in b['aliases']


def test_actual_generator_semantic_ids_resolved_before_jobs(registry):
    from create_defaults.bulk.definitions import Definition
    b=historical_basis();r=b.resolution.data()
    # Expand the actual four-generator catalog without invoking plan/render.
    definitions=[Definition.create(d) for d in r['declared'].values()]
    expanded,families,origins=StablePlanner(registry.view(),Config()).expand(definitions)
    assert set(expanded)==set(r['expanded']) and families==r['families']
    # A filename-derived intermediate ID changes, but semantic lookup retains
    # the original frozen child identity before the job sealing boundary.
    parent=next(p for p in families if r['declared'][p]['generator']['name']=='award-years')
    d=deepcopy(r['declared'][parent]);d['generator']['parameters']['directory']+='-synthetic'
    changed,children,_=StablePlanner(registry.view(),Config()).expand([Definition.create(d)])
    assert children[parent]==families[parent]
    assert all(changed[i].data['output']['directory'].endswith('-synthetic') for i in children[parent])


def test_original_m5_transitive_fanout_cycles_and_unaffected_proof():
    from create_defaults.bulk.contracts.expanded.graph import Snapshot,compare
    from create_defaults.bulk.lifecycle.impact import _reasons
    def node(kind,identity,sha,deps=()):return dict(kind=kind,identity=identity,sha256=sha,dependencies=list(deps))
    def output(i,deps):
        return dict(node='output:'+i,category='Playlist',kind='poster',variant='timeline-order',local_path='defaults-en/playlist/'+i+'.jpg',public_path='playlist/'+i+'.jpg',companions=[],context_sha256='a'*64,evidence={f:[] for f in ['previews','confirmations','decisions','receipts']})
    nodes={'asset:shared':node('asset','shared','a'*64),'asset:other':node('asset','other','b'*64),
        'output:a':node('output','a','c'*64,['asset:shared']),'output:b':node('output','b','d'*64,['output:a']),
        'output:c':node('output','c','e'*64,['asset:other'])}
    value=dict(schema_version=1,kind='m5-dependency-snapshot',basis='f'*64,nodes=nodes,outputs={i:output(i,[]) for i in ['a','b','c']},unresolved=[])
    old=Snapshot.create(value);value=deepcopy(value);value['nodes']['asset:shared']['sha256']='0'*64;new=Snapshot.create(value)
    result=compare(old,new);assert result['affected_outputs']==['a','b'] and result['unaffected_outputs']==['c']
    assert _reasons(new.index(),['asset:shared'])['b']==[dict(cause='asset:shared',path=['asset:shared','output:a','output:b'])]
    assert old.index().material_context('c')==new.index().material_context('c')
    value['nodes']['asset:shared']['dependencies']=['output:b']
    with pytest.raises(BulkError):Snapshot.create(value)


def test_all_actual_overlay_branches_pairs_and_blocked_jobs(registry,tmp_path):
    basis=historical_basis();pairs={}
    for i in sorted(basis.ids):
        row=basis.row(i)
        if row['identity']['category']=='Overlays':pairs.setdefault(basis.assignment(i)['variant'],i)
    assert len(pairs)==18
    for branch,identity in pairs.items():
        companion=basis.assignment(identity)['companions'];assert len(companion)==1
        candidate=overlay_candidate(registry,expected=registry.view().head,identities=[identity,*companion])
        assert len(candidate.graph.index().outputs)==2
        assert not candidate.data()['job_planning_complete']
        with pytest.raises(BulkError):candidate.jobs()
        with pytest.raises(BulkError):overlay_candidate(registry,expected=registry.view().head,identities=[identity])
    identity=next(iter(pairs.values()));e=registry.reference(identity,token='overlay-reference',expected=registry.view().head)
    changed=deepcopy(e['names']);changed['public_path']='unapproved/Synthetic.png'
    registry.revise(identity,changed,entry_revision=1,token='overlay-route',expected=registry.view().head)
    with pytest.raises(BulkError):overlay_candidate(registry,expected=registry.view().head,identities=[identity,*basis.assignment(identity)['companions']])


def test_fixed_windows_linux_registry_replay_vector(tmp_path):
    from create_defaults.phase4.tests.m2_samples import vector
    from ci.validation import identity,write
    result=vector(tmp_path/'canonical');expected=json.loads(Path(__file__).with_name('identity-canonical-v1.json').read_text(encoding='utf8'))
    assert result==expected['archive'] and fingerprint(result)==expected['archive_sha256']
    write(Path(__file__).parents[3]/'config/phase4-ci/phase4-m2-canonical.json',
        dict(**identity(),evidence_sha256=fingerprint(result)))


@pytest.mark.parametrize('category',['Studio','Genre','Aspect'])
def test_actual_non_playlist_closed_category_adapter(registry,tmp_path,category):
    basis=historical_basis();package=basis.package(category);rules,members=package.data()
    variant=next(v for v in sorted(rules) if rules[v]['required_presentations']==['single'] and rules[v]['source_kind']=='logo')
    old=next(i for i,m in members.items() if m['variant']==variant)
    d=basis.resolution.definition(old);n=deepcopy(basis.entry(old)['names'])
    n['display_name']='Synthetic '+category
    local=str(Path(n['local_path']).parent).replace('\\','/')
    public=str(Path(n['public_path']).parent).replace('\\','/')
    n.update(local_path=local+'/Synthetic.jpg',public_path=public+'/Synthetic.jpg')
    e=allocate(registry,key='synthetic-'+category,category=category,variant=variant,names=n)
    d.update(id=e['id'],display_name=n['display_name'],generator=None,dependencies=[])
    d['output'].update(filename='Synthetic.jpg',remote_paths={'en':n['public_path']})
    d['composer']['out_name']='Synthetic'
    if category=='Genre':d['composer']['white_wash']=True
    content=dict(display_name=n['display_name'],source=n['source'])
    captions=json.loads(rules[variant]['caption_types_json'])
    content['content_type']=next(k for k,t in captions.items() if json.loads(t['definition_json'])==d['caption'] and t['text']==n['rendered_caption'])
    path=tmp_path/'candidate.yml';profiles=tmp_path/'profiles.yml'
    path.write_text(yaml.safe_dump(dict(schema_version=1,category=category,definitions=[d])),encoding='utf8')
    profiles.write_text(yaml.safe_dump(dict(schema_version=1,profiles={})),encoding='utf8')
    candidate=poster_candidate(registry,expected=registry.view().head,paths=[path],profiles_path=profiles,posters=[e['id']],content={e['id']:content},config=Config())
    assert candidate.data()['validation'][0]['identity']==e['id']
    assert candidate.graph.index().outputs[e['id']]['category']==category
