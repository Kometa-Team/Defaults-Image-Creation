"""Full native synthetic pixels and adversarial immutable evidence verification."""
from copy import deepcopy
from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import socket
import subprocess
import sys
import os

from PIL import Image
import pytest

from create_defaults.bulk.common import BulkError,canonical,fingerprint,sha256
from create_defaults.bulk.lifecycle import composition
from create_defaults.bulk.lifecycle.composition_models import CompositionEvidence,BytesObject,FLAGS
from create_defaults.bulk.lifecycle.previews import CompositionTrial,CompositionArchive
from create_defaults.phase4.tests import composition_samples as samples


@pytest.fixture(scope='module')
def composed():
    trials=[]
    class Values(dict):
        def __missing__(self,kind):
            trial=CompositionTrial();trials.append(trial)
            if kind=='overlay':ctx=samples.overlays(trial)
            elif kind=='family':ctx=samples.family(trial)
            else:ctx=samples.poster(trial,{'playlist':'Playlist','genre':'Genre','network':'Network'}[kind],paired=kind=='network')
            requests=[samples.exception(ctx.candidate)] if kind in {'playlist','genre'} else []
            evidence=composition.compose(ctx,trial,exceptions=requests)
            self[kind]=(trial,ctx,evidence,requests)
            return self[kind]
    values=Values();values.replays={}
    try:
        yield values
    finally:
        for trial in reversed(trials):trial.close()


def archive(row,readonly=True):return CompositionArchive(row[1].registry.operations.root,readonly=readonly)


def reject(row,value):
    with pytest.raises(BulkError):archive(row).verify(CompositionEvidence.from_dict(value),context=row[1])


def replay(composed,kind):
    if kind not in composed.replays:
        trial,ctx,_,requests=composed[kind]
        composed.replays[kind]=composition.compose(ctx,trial,exceptions=requests)
    return composed.replays[kind]


@pytest.mark.parametrize('kind',['playlist','genre','network','overlay','family'])
def test_complete_native_composition_and_reopen(composed,kind):
    row=composed[kind];trial,ctx,evidence,_=row;v=evidence.to_dict()
    assert archive(row).load(evidence.sha256,context=ctx).encoded==evidence.encoded
    assert {k:v[k] for k in FLAGS}==FLAGS
    assert len(v['views'])==2 and len(v['required_members'])==(2 if kind in {'network','overlay'} else 1)
    assert len(ctx.registry.operations.history(v['operation']['id']))==1
    for view in v['views']:
        for m in view['members']:
            raw=archive(row).read_bytes(m['object_sha256'])
            assert len(raw)==m['bytes']
            with Image.open(BytesIO(raw)) as image:
                image.load()
                if kind=='overlay':assert image.mode=='RGBA' and image.getchannel('A').getextrema()[0]==0
                else:assert image.mode=='RGB' and image.size==(2000,3000)
        if kind=='family':assert json.loads(view['members'][0]['origin_json'])


@pytest.mark.parametrize('kind',['playlist','genre','network','overlay','family'])
def test_independent_render_same_environment_exact_encoded_bytes(composed,kind,monkeypatch):
    import requests
    from create_defaults.bulk import operator_publication
    from create_defaults.bulk.contracts.activation.controller import Controller
    def prohibited(*a,**k):raise AssertionError('Composition invoked authority or publication')
    for obj,name in [(requests.Session,'request'),(socket.socket,'connect'),(operator_publication,'stage'),(operator_publication,'draft'),(Controller,'transition')]:monkeypatch.setattr(obj,name,prohibited)
    trial,ctx,first,requests=composed[kind]
    second=replay(composed,kind)
    a=first.to_dict();b=second.to_dict()
    assert [[m['sha256'] for m in v['members']] for v in a['views']]==[[m['sha256'] for m in v['members']] for v in b['views']]
    for view in b['views']:
        assert sum(m['executed'] for m in json.loads(view['execution_json']))==len(view['members'])
        assert sum(m['cache_hits'] for m in json.loads(view['execution_json']))==0


@pytest.mark.parametrize('kind',['playlist','genre'])
def test_default_white_wash_and_requested_source_preserving_are_distinct(composed,kind):
    row=composed[kind];a,b=row[2].to_dict()['views'];ma=a['members'][0];mb=b['members'][0]
    assert ma['sha256']!=mb['sha256']
    da=json.loads(a['definitions_json'])[ma['identity']];db=json.loads(b['definitions_json'])[ma['identity']]
    assert da['composer']['white_wash'] and not db['composer']['white_wash']
    da['composer']['white_wash']=False;assert da==db
    # Native JPEG colour observations, not a perceptual approval threshold:
    # the centre of an opaque synthetic logo region is white vs coloured.
    ia=Image.open(BytesIO(archive(row).read_bytes(ma['object_sha256'])));ib=Image.open(BytesIO(archive(row).read_bytes(mb['object_sha256'])))
    assert ia.tobytes()!=ib.tobytes()
    assert json.loads(row[2].to_dict()['context_json'])['request_json'].find('not-granted')>=0


@pytest.mark.parametrize('kind',['network','overlay'])
def test_missing_required_companion_cannot_be_composition_complete(composed,kind):
    row=composed[kind];v=row[2].to_dict()
    for view in v['views']:view['members'].pop()
    reject(row,v)


@pytest.mark.parametrize('field',['active','artwork_approved','operation_accepted','ready','publication_authorized','complete','schema_version','scope','unknown'])
def test_closed_schema_cannot_confer_authority(composed,field):
    row=composed['playlist'];v=row[2].to_dict();v[field]=False if field=='complete' else 2 if field=='schema_version' else 'foreign' if field=='scope' else True
    reject(row,v)


@pytest.mark.parametrize('attack',['candidate','impact','registry','operation','membership','definition','sources','receipt','origin','graph','runtime'])
def test_rehashed_forged_complete_evidence_is_replayed(composed,attack):
    row=composed['playlist'];v=row[2].to_dict();ctx=json.loads(v['context_json']);view=v['views'][0];m=view['members'][0]
    if attack in {'candidate','impact','registry'}:ctx[attack+'_sha256']='0'*64
    elif attack=='operation':v['operation']['sha256']='0'*64;ctx['operation']=v['operation']
    elif attack=='membership':v['required_members']=['playlist.'+'f'*32];ctx['required_members']=v['required_members']
    elif attack=='definition':
        d=json.loads(view['definitions_json']);d[m['identity']]['composer']['gradient']=4;view['definitions_json']=canonical(d).decode()
    elif attack=='sources':view['sources'].pop()
    elif attack=='receipt':m['receipt_sha256']='0'*64
    elif attack=='origin':m['origin_json']='{"forged":true}'
    elif attack=='graph':view['impact_json']='{}'
    else:
        runtime=json.loads(v['runtime_json']);runtime['implementation_sha256']='0'*64;v['runtime_json']=canonical(runtime).decode()
    v['context_json']=canonical(ctx).decode();reject(row,v)


@pytest.mark.parametrize('attack',['corrupted','logo-only','thumbnail','forged-full-canvas'])
def test_actual_encoded_pixels_cannot_be_substituted(composed,attack):
    row=composed['playlist'];v=row[2].to_dict();m=v['views'][0]['members'][0]
    if attack=='corrupted':raw=b'invalid jpeg'
    elif attack=='logo-only':raw=samples.png()
    else:
        image=Image.new('RGB',(100,150) if attack=='thumbnail' else (2000,3000),'white');out=BytesIO();image.save(out,format='JPEG');raw=out.getvalue()
    m['object_sha256']=archive(row,False).put_bytes(raw);m['sha256']=__import__('hashlib').sha256(raw).hexdigest();m['bytes']=len(raw)
    reject(row,v)


@pytest.mark.parametrize('kind',['source','font','definition'])
def test_changed_current_bytes_invalidate_previous_evidence_even_with_old_timestamp(composed,kind):
    row=composed['playlist'];trial,ctx,evidence,_=row
    manifest=json.loads(evidence.to_dict()['views'][0]['manifest_json'])
    if kind=='definition':path=ctx.candidate.paths[0]
    else:
        item=next(i for i in manifest['jobs'][0]['inputs'] if i['role']==('font' if kind=='font' else 'logo'));path=trial.config.asset_dir/item['path']
    original=path.read_bytes();stat=path.stat()
    try:
        path.write_bytes(original[:-1]+bytes([original[-1]^1]));os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns))
        with pytest.raises(BulkError):archive(row).load(evidence.sha256,context=ctx)
    finally:path.write_bytes(original);os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns))


@pytest.mark.parametrize('field',['renderer','contract','operation','registry','impact'])
def test_changed_live_context_cannot_reuse_archive(composed,monkeypatch,field):
    row=composed['playlist'];ctx=row[1]
    if field=='renderer':
        original=composition.implementation;monkeypatch.setattr(composition,'implementation',lambda:'0'*64)
    elif field=='contract':
        # Actual immutable contract bytes differ from the selected package pin.
        from create_defaults.bulk.contracts.categories.release import ROOT
        original=composition.read_json_bytes
        contract_path=ROOT/'categories/data/contracts/playlist-v1.json'
        monkeypatch.setattr(composition,'read_json_bytes',lambda p:b'{}' if p==contract_path else original(p))
    elif field=='operation':
        from create_defaults.bulk.lifecycle import impact
        head=impact.operation_head(ctx.registry.operations,row[2].to_dict()['operation']['id'])
        monkeypatch.setattr(impact,'operation_head',lambda *a:replace(head,revision=head.revision+1))
    elif field=='registry':
        original=ctx.registry.require_head
        def stale(*a,**k):raise BulkError('stale-registry','Registry changed')
        monkeypatch.setattr(ctx.registry,'require_head',stale)
    else:ctx=replace(ctx,impact_sha256='0'*64)
    with pytest.raises(BulkError):archive(row).load(row[2].sha256,context=ctx)


def reseal(manifest):
    for j in manifest['jobs']:j['render_fingerprint']=fingerprint({k:j[k] for k in ('kind','parameters','inputs','dependencies','language_behavior')}|dict(renderer=manifest['renderer']))
    manifest['sha256']=fingerprint({k:v for k,v in manifest.items() if k!='sha256'});return manifest


@pytest.mark.parametrize('attack',['long-text','missing-glyph','random-colour','opaque','invalid-png'])
def test_native_layout_and_source_blockers_are_not_waived(composed,attack):
    row=composed['playlist'];trial,ctx,evidence,_=row;m=json.loads(evidence.to_dict()['views'][0]['manifest_json']);j=m['jobs'][0]
    source=next(x for x in j['inputs'] if x['role']=='logo');path=trial.config.asset_dir/source['path'];raw=path.read_bytes()
    try:
        if attack in {'long-text','missing-glyph'}:
            j['raw_parameters']['text']=j['parameters']['text']='W'*500 if attack=='long-text' else '\U0001f680'
        elif attack=='random-colour':
            for name in ('raw_parameters','parameters'):j[name].update(base_color=None,avg_color=True)
        else:
            path.write_bytes(samples.png(opaque=True) if attack=='opaque' else b'not png');source['sha256']=sha256(path)
        with pytest.raises(BulkError):composition.validate_native(reseal(m),trial.config,ctx.registry.view(),composition.request_spec(ctx.candidate))
    finally:path.write_bytes(raw)


@pytest.mark.parametrize('attack',['wrong-request-context','unsupported-treatment','opaque-exception','untyped-request'])
def test_customization_requires_exact_typed_permitted_request(composed,attack):
    row=composed['playlist'];r=row[3][0].to_dict()
    if attack=='wrong-request-context':r['context']['material_context_sha256']='0'*64
    elif attack=='unsupported-treatment':r['requested_treatment']='COLOR_ONLY'
    elif attack=='opaque-exception':r['intentional_background']=True
    with pytest.raises(BulkError):
        request=r if attack=='untyped-request' else samples.ExceptionRequest.from_dict(r)
        composition.request_spec(row[1].candidate,[request])


def test_corrupt_content_addressed_object_rejected_after_reopen(composed):
    row=composed['playlist'];m=row[2].to_dict()['views'][0]['members'][0];path=row[1].registry.operations.root/'objects'/(m['object_sha256']+'.json');raw=path.read_bytes()
    try:
        path.write_bytes(b'{}')
        with pytest.raises(BulkError):archive(row).load(row[2].sha256,context=row[1])
    finally:path.write_bytes(raw)


@pytest.mark.parametrize('attack',['interrupt','partial-persist'])
def test_interruption_never_publishes_complete_archive_or_advances_operation(attack,monkeypatch):
    with CompositionTrial() as trial:
        ctx=samples.poster(trial);before=ctx.registry.operations.inspect()
        if attack=='partial-persist':
            def interrupted(*a,**k):raise OSError('synthetic interruption before receipt persistence')
            monkeypatch.setattr(CompositionArchive,'put_json',interrupted)
        with pytest.raises((BulkError,OSError)):
            composition.compose(ctx,trial,cancel=(lambda:True) if attack=='interrupt' else None)
        assert ctx.registry.operations.inspect()==before
        assert not any(json.loads(p.read_bytes()).get('kind')=='composition-evidence' for p in (ctx.registry.operations.root/'objects').glob('*.json'))


def test_unsupported_adapter_and_foreign_trial_are_blocked(composed):
    with CompositionTrial() as trial:
        with pytest.raises(BulkError):trial.require(composed['playlist'][1].candidate)
        with pytest.raises(BulkError):composition.compose(object(),trial)
    with pytest.raises(BulkError):composition.CompositionContext(None,None,object(),None,'0'*64).verify()


def test_cold_composition_import_and_runtime_no_authority_or_network(composed,monkeypatch):
    code=r"""
import sys
sys.dont_write_bytecode=True
def guard(event,args):
    if event in {'os.mkdir','os.remove','os.rename','sqlite3.connect','socket.connect','socket.bind','subprocess.Popen','os.system'}:raise AssertionError(event)
    if event=='open' and isinstance(args[1],str) and any(c in args[1] for c in 'wax+'):raise AssertionError('import write')
sys.addaudithook(guard)
from create_defaults.bulk.lifecycle import composition,previews,composition_models
assert 'create_defaults.bulk.contracts.activation.controller' not in sys.modules
assert 'create_defaults.bulk.operator_publication' not in sys.modules
print('isolated')
"""
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='isolated'
    def prohibited(*a,**k):raise AssertionError('Network/production interface invoked')
    import requests
    monkeypatch.setattr(requests.Session,'request',prohibited);monkeypatch.setattr(socket.socket,'connect',prohibited)
    row=composed['playlist'];assert archive(row).load(row[2].sha256,context=row[1])


def test_real_private_parent_before_child_and_receipt_substitution_controls(composed):
    """Actual native DAG pixels, without claiming a new category source route.

    M2's closed composition roots cannot accept arbitrary new private parent
    names. That adapter stays blocked; this proves the underlying owned-parent
    interface rather than fabricating a historical record to bypass it.
    """
    from create_defaults.bulk.definitions import Definition
    from create_defaults.bulk.planner import Planner
    from create_defaults.bulk.workers import PersistentWorkers,WorkerLimits,tasks_from_manifest
    from create_defaults.bulk.contracts.expanded.validation import approved_english
    from create_defaults.bulk.lifecycle.package_e import SidecarStore
    trial,ctx,evidence,_=composed['playlist'];config=trial.view_config('default')
    d=deepcopy(next(iter(ctx.candidate.data()['effective_definitions'].values())))
    parent=Definition.create(d);child=deepcopy(d);child['id']='playlist.synthetic-private-child'
    child['composer'].update(out_name='Fixture Child',logo='defaults-en/playlist/Fixture Brand (Timeline Order).jpg')
    child['output'].update(filename='Fixture Child.jpg',remote_paths={'en':'playlist/Fixture Child.jpg'})
    child['dependencies']=[dict(poster_id=parent.id,input='logo')];child=Definition.create(child)
    planner=Planner(config);store=SidecarStore(ctx.registry.operations.root).backend
    with pytest.raises(BulkError):planner.plan([parent,child],approved_english(),posters=[child.id],languages=['en'])
    with PersistentWorkers(store,config,WorkerLimits(workers=1,retries=0)) as pool:
        first=planner.plan([parent],approved_english(),languages=['en']);parent_job=first['jobs'][0]
        pool.run(tasks_from_manifest(first));receipt,raw=composition.owned_receipt(store,config,parent_job)
        forged=deepcopy(parent_job);forged['render_fingerprint']='0'*64
        with pytest.raises(BulkError):composition.owned_receipt(store,config,forged)
        with store.transaction() as db:db.execute('UPDATE jobs SET receipt=NULL WHERE id=?',(receipt['job_id'],))
        try:
            with pytest.raises(BulkError):composition.owned_receipt(store,config,parent_job)
        finally:
            with store.transaction() as db:db.execute('UPDATE jobs SET receipt=? WHERE id=?',(canonical(receipt).decode(),receipt['job_id']))
        artifact={parent_job['id']:receipt['sha256']}
        final=planner.plan([parent,child],approved_english(),posters=[child.id],languages=['en'],dependency_artifacts=artifact)
        assert final['jobs'][0]['poster_id']==parent.id
        assert final['jobs'][1]['dependencies'][0]['sha256']==receipt['sha256']
        result=pool.run(tasks_from_manifest(final))
        assert len(result['jobs'])==2
        encoded=composition.owned_receipt(store,config,final['jobs'][1])[1]
        assert Image.open(BytesIO(encoded)).size==(2000,3000)
        parent_path=config.output_dir/parent_job['local_relative'];parent_path.unlink()
        with pytest.raises((BulkError,FileNotFoundError)):composition.owned_receipt(store,config,parent_job)
        with pytest.raises(BulkError):planner.plan([parent,child],approved_english(),languages=['en'],dependency_artifacts=artifact)
    pool.workspaces.cleanup(**pool.workspace,retain_seconds=0)


def test_required_family_and_derived_source_cannot_smuggle_submitter_style(composed):
    row=composed['family'];ctx=row[1];candidate=ctx.candidate;content=json.loads(candidate.content_json)
    i=next(iter(content));assert 'source' not in content[i]
    from create_defaults.bulk.lifecycle.candidates import poster_candidate
    for value in [dict(source=ctx.registry.view().entry(i)['names']['source']),dict(font='fonts/BebasNeue-Regular.ttf'),dict(white_wash=False)]:
        bad=deepcopy(content);bad[i].update(value)
        with pytest.raises(BulkError):poster_candidate(ctx.registry,expected=candidate.registry_head,paths=candidate.paths,
            profiles_path=candidate.profiles_path,posters=candidate.posters,content=bad,config=candidate.config)


def test_missing_required_companion_resealed_subset_is_still_rejected(composed):
    row=composed['overlay'];v=row[2].to_dict();selected=v['required_members'][:1];v['required_members']=selected
    ctx=json.loads(v['context_json']);ctx['required_members']=selected;v['context_json']=canonical(ctx).decode()
    for view in v['views']:
        view['members']=[m for m in view['members'] if m['identity'] in selected]
        view['members'][0]['companions']=[]
        definitions=json.loads(view['definitions_json']);view['definitions_json']=canonical({i:d for i,d in definitions.items() if i in selected}).decode()
        manifest=json.loads(view['manifest_json']);manifest['jobs']=[j for j in manifest['jobs'] if j['poster_id'] in selected]
        manifest['selection']['posters']=selected;manifest=reseal(manifest)
        view['manifest_json']=canonical(manifest).decode();view['manifest_sha256']=manifest['sha256']
    subset=CompositionEvidence.from_dict(v)
    with pytest.raises(BulkError,match='stale_composition_context'):archive(row).verify(subset,context=row[1])


def test_m3_exact_head_full_resolution_evidence_and_resource_report(composed):
    from ci.validation import identity,write
    from ci.phase4 import checksum
    from create_defaults.bulk.config import ROOT
    groups={};head=identity();out=ROOT.parent/'config/ci-validation/phase4-m3'
    for kind in ['playlist','genre','network','overlay','family']:
        row=composed[kind];first=row[2].to_dict();second=replay(composed,kind).to_dict()
        views=[]
        for a,b in zip(first['views'],second['views']):
            members={m['identity']:m['sha256'] for m in a['members']}
            assert members=={m['identity']:m['sha256'] for m in b['members']}
            execution=json.loads(a['execution_json'])+json.loads(b['execution_json'])
            assert max(e['peak_worker_rss'] for e in execution)<=512*1024*1024
            assert max(e['peak_workers_rss_sum'] for e in execution)<=1024*1024*1024
            views.append(dict(appearance=a['appearance'],members=members,repeated_members={m['identity']:m['sha256'] for m in b['members']},execution=execution))
        folder=out/('m3-review-'+kind+'-'+head['head'][:12]+'-'+row[2].sha256[:12])
        gallery=archive(row).gallery(row[2].sha256,context=row[1],directory=folder)
        write(folder/'composition-evidence.json',first)
        groups[kind]=dict(evidence_sha256=row[2].sha256,runtime=json.loads(first['runtime_json']),views=views,gallery=str(gallery.relative_to(out)).replace('\\','/'))
    value=dict(**head,kind='phase4-m3-composition-proof',schema_sha256=checksum(ROOT/'bulk/lifecycle/schemas/composition-v1.schema.json'),
        implementation_sha256=composition.implementation(),groups=groups,approval=False,activation=False,publication=False,reuse_scope='exact-environment-only')
    value['evidence_sha256']=fingerprint(value)
    write(out/'phase4-m3-composition.json',value)
