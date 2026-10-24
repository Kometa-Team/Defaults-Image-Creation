"""Owned full composition through unchanged Package E planner and spawn pool.

No renderer algorithm, human decision, definition exporter or production hook.
M2 remains independently verified; an additive overlay pre-seal adapter resolves
its precise missing interface without rewriting a previously sealed job.
"""
from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
import inspect
import json
from pathlib import Path

from PIL import Image,features
from ..common import canonical,confined,fingerprint,path_key,sha256
from ..config import Config
from ..definitions import Definition
from ..planner import Planner,validate_manifest
from ..overlays import identity as overlay_identity,TRANSFORM
from ..workers import PersistentWorkers,WorkerLimits,tasks_from_manifest,compose as native_compose
from ..contracts.models import ExceptionRequest,Identity,decode_json,read_json_bytes
from ..contracts.registry import package_reference
from ..contracts.logos.assets import inspect_png
from ..contracts.expanded.validation import approved_english
from ..contracts.expanded.graph import Snapshot,compare
from ..typography import evaluate
from .basis import historical_basis
from .candidates import PosterCandidate
from .overlay_candidates import OverlayCandidate
from .identities import IdentityRegistry
from .impact import OperationHead,revalidate
from .package_e import SidecarStore
from .composition_models import HEADER,CompositionEvidence,MAX_MEMBERS,MAX_BINARY,fail


def implementation():
    names=('composition.py','composition_models.py','previews.py','schemas/composition-v1.schema.json')
    return fingerprint({n:(Path(__file__).parent/n).read_text(encoding='utf-8-sig').replace('\r\n','\n') for n in names})


def runtime(renderer):
    return dict(renderer=renderer,native_libraries={n:features.version(n) for n in ('freetype2','jpg','zlib','raqm')},
        implementation_sha256=implementation(),reproducibility='exact-environment-only')


def input_bytes(path):
    with path.open('rb') as stream:raw=stream.read(MAX_BINARY+1)
    if not 0<len(raw)<=MAX_BINARY:fail('input_resource_bound')
    return raw


@dataclass(frozen=True)
class CompositionContext:
    registry: IdentityRegistry
    before: object
    candidate: object
    impact: object
    impact_sha256: str

    def verify(self):
        if type(self.registry) is not IdentityRegistry or type(self.candidate) not in {PosterCandidate,OverlayCandidate}:fail('unsupported_candidate_adapter')
        # HistoricalBasis is an immutable process cache, not proof that its
        # selected on-disk contracts stayed unchanged during a long review.
        from ..contracts.categories.release import ROOT as contracts_root,RELEASE_SHA256
        release=decode_json(read_json_bytes(contracts_root/'categories/data/release-v1.json'))
        if fingerprint(release)!=RELEASE_SHA256:fail('contract_release_drift')
        categories={self.registry.view().entry(i)['category'] for i in self.candidate.graph.index().outputs}
        for entry in release['entries']:
            if entry['category'] not in categories:continue
            for kind in ('contract','rules'):
                if fingerprint(decode_json(read_json_bytes(confined(contracts_root,entry[kind+'_path'],must_exist=True))))!=entry[kind+'_sha256']:fail('category_contract_drift')
        evidence=revalidate(self.impact,expected_sha256=self.impact_sha256,registry=self.registry,before=self.before,after=self.candidate)
        # revalidate -> analyze -> epochs already reconstructs and verifies the
        # complete candidate. Do not repeat that expensive identical replay.
        candidate=self.candidate;view=self.registry.view();details=json.loads(evidence.to_dict()['details_json'])
        required=sorted(candidate.graph.index().outputs)
        if not 0<len(required)<=MAX_MEMBERS:fail('member_resource_bound')
        for children in candidate.data().get('families',{}).values():
            selected=set(children)&set(required)
            if selected and selected!=set(children):fail('incomplete_generated_family')
        if not set(details['affected_outputs'])<=set(required) or set(details['required_companions'])-set(required):fail('impact_member_closure')
        blockers=set(details['blockers'])
        if type(candidate) is OverlayCandidate:
            if blockers!={'overlay_preseal_identity_hook_required'}:fail('unresolved_overlay_impact')
        elif blockers:fail('unresolved_impact')
        for i in required:
            e=view.entry(i)
            if e['origin']!='assigned' or e['tombstone_sha256'] is not None:fail('historical_or_retired_render_forbidden')
        return candidate,view,required,evidence


def exception_context(candidate,identity):
    if type(candidate) is not PosterCandidate:fail('unsupported_exception_adapter')
    e=candidate.registry.view().entry(identity);p=historical_basis().package(e['category'])
    d=next(v['design'] for v in p.contract.to_dict()['variants'] if v['id']==e['variant'])
    return dict(package=package_reference(p.contract),variant=e['variant'],identities=[identity],source=e['names']['source'],
        material_context_sha256=fingerprint(dict(identity=e,content=json.loads(candidate.content_json)[identity],design=d)),
        transformations=[d['logo']['transformation']])


def request_spec(candidate,exceptions=()):
    requests={}
    for r in exceptions:
        if type(r) is not ExceptionRequest:fail('typed_exception_required')
        r=ExceptionRequest.from_bytes(r.encoded);v=r.to_dict();ctx=v['context']
        if len(ctx['identities'])!=1:fail('exception_membership')
        i=ctx['identities'][0]
        if i in requests or i not in candidate.graph.index().outputs:fail('exception_membership')
        if ctx!=exception_context(candidate,i) or not v['justification'].strip():fail('exception_context')
        e=candidate.registry.view().entry(i);p=historical_basis().package(e['category'])
        d=next(v['design'] for v in p.contract.to_dict()['variants'] if v['id']==e['variant'])
        if d['logo']['treatment']!='WHITE_ONLY' or not d['logo']['source_preserving_exception'] or v['requested_treatment']!='SOURCE_PRESERVING' or v['intentional_background']:fail('unsupported_customization')
        requests[i]=r.to_dict()
    return dict(schema_version=1,kind='composition-preview-request',exceptions=requests,
        default='validated-category-default',requested='pending-explicit-logo-treatment-only',approval='not-granted')


def native_overlay_manifest(candidate,view):
    """Missing pre-seal interface: native payload assembly, no image algorithm."""
    data=candidate.data();renderer=overlay_identity();jobs=[]
    for i in data['identities']:
        e=view.entry(i);definition=data['effective_definitions'][i];parameters=definition['parameters'];source=e['names']['source']
        job=dict(id='overlay.'+fingerprint(dict(identity=i,language='en',variant=e['semantic']['role']))[:24],kind='overlay',
            poster_id=i,language='en',variant=e['semantic']['role'],definition_fingerprint=fingerprint(definition),generator_origin=None,
            source=dict(kind='authored',path='isolated-composition-overlay',line=1,row_sha256=fingerprint(definition)),
            raw_parameters=parameters,parameters=parameters,inputs=[dict(role='overlay_source',**source)],dependencies=[],
            translation=dict(mode='none',trace=[],fingerprint=fingerprint(dict(mode='none'))),
            language_behavior=dict(language='shared',direction='auto'),local_relative=e['names']['local_path'],remote_relative=e['names']['public_path'],
            layout_evidence=dict(transform=TRANSFORM),color_assignment=dict(id='overlay.none',origin='template',parent=None,relationship=None,exception=None),status='planned',render_ready=True)
        job['render_fingerprint']=fingerprint({k:job[k] for k in ('kind','parameters','inputs','dependencies','language_behavior')}|dict(renderer=renderer))
        jobs.append(job)
    value=dict(schema_version=1,kind='bulk-plan',renderer=renderer,jobs=jobs,not_applicable=[],
        selection=dict(categories=['Overlays'],posters=sorted(data['identities']),languages=['en']),scope='M3 isolated native overlay; no approval')
    value['sha256']=fingerprint(value)
    return validate_manifest(value)


def definitions_for(candidate,appearance,spec):
    if type(candidate) is OverlayCandidate:return deepcopy(candidate.data()['effective_definitions'])
    values=deepcopy(candidate.data()['effective_definitions'])
    wanted=set(candidate.graph.index().outputs)
    values={i:d for i,d in values.items() if i in wanted}
    if appearance=='requested':
        for i in spec['exceptions']:values[i]['composer']['white_wash']=False
    return values


def validate_native(manifest,config,view,spec):
    """Existing PNG and exact native glyph geometry; no fitting/repair/waiver."""
    validate_manifest(manifest);reports={}
    for job in manifest['jobs']:
        e=view.entry(job['poster_id']);p=historical_basis().package(e['category']);rule=historical_basis().rule(e['category'],e['variant'])
        if job['language']!='en':fail('unsupported_language')
        parameters=job['parameters'];sources=[]
        if job['kind']=='poster':
            if not parameters['base_color'] or parameters['dom_color'] or parameters['avg_color'] or parameters['dom_color_image'] is not None:fail('unresolved_random_colour_dependency')
            font=next((x for x in job['inputs'] if x['role']=='font'),None)
            if font is None:fail('missing_font')
            fontpath=confined(config.asset_dir,font['path'],must_exist=True)
            if sha256(fontpath)!=font['sha256']:fail('font_drift')
            try:fit=evaluate(fontpath,font['sha256'],parameters['text'],parameters['font_size'],parameters['text_offset'],fingerprint(manifest['renderer']),proposals=False)
            except ValueError:fail('missing_glyph')
            if fit['state']!='fits_current':fail('layout_or_clipping')
            reports[job['poster_id']]=fit
        for item in job['inputs']:
            path=confined(config.asset_dir,item['path'],must_exist=True)
            if sha256(path)!=item['sha256']:fail('input_drift')
            if item['role'] in {'logo','overlay_source'} and rule['source_kind'] not in {'placeholder','composition'}:
                report=inspect_png(input_bytes(path)).report()
                if report['default_transparency_blockers'] or report['diagnostics']:fail('source_transparency_or_quality_review_required')
                if rule['treatment']=='BOTH_REQUIRED' and e['semantic']['role']=='white' and not parameters.get('white_wash',False):
                    with Image.open(path) as white:
                        rgba=white.convert('RGBA')
                        if any(a and (r,g,b)!=(255,255,255) for r,g,b,a in rgba.getdata()):fail('white_source_not_white')
                sources.append(report)
        if job['poster_id'] in reports:reports[job['poster_id']]['source_reports']=sources
        else:reports[job['poster_id']]=dict(source_reports=sources)
    return reports


def owned_receipt(store,config,job):
    with store.connection() as db:
        claim=db.execute('SELECT state_id FROM output_claims WHERE root=? AND path_key=?',
            (fingerprint(str(config.output_dir)),path_key(job['local_relative']))).fetchone()
    row=store.job(claim['state_id']) if claim else None
    if not row or row['status']!='verified' or row['receipt'] is None:fail('missing_owned_parent_or_output_receipt')
    receipt=json.loads(row['receipt']);payload={k:v for k,v in receipt.items() if k!='receipt_sha256'}
    if fingerprint(payload)!=receipt['receipt_sha256'] or receipt['logical_id']!=job['id'] or receipt['render_fingerprint']!=job['render_fingerprint'] or receipt['renderer_identity']!=fingerprint(inspect.getsource(native_compose)):fail('receipt_substitution')
    output=confined(config.output_dir,job['local_relative'],must_exist=True)
    if sha256(output)!=receipt['sha256'] or output.stat().st_size!=receipt['size']:fail('output_drift')
    return receipt,output.read_bytes()


def image_properties(raw,job):
    try:
        with Image.open(BytesIO(raw)) as image:
            if image.width*image.height>2000*3000:fail('image_resource_bound')
            image.load();result=dict(format=image.format,mode=image.mode,dimensions=list(image.size))
            if job['kind']=='poster':
                if (image.format,image.mode,image.size)!=('JPEG','RGB',(2000,3000)):fail('complete_poster_required')
            elif image.format!='PNG' or image.mode!='RGBA' or any(not 0<d<=b for d,b in zip(image.size,job['parameters']['box'])):fail('native_overlay_required')
            return result
    except (OSError,ValueError):fail('invalid_encoded_output')


def render_view(candidate,view,config,appearance,spec,store,*,cancel=None):
    definitions=definitions_for(candidate,appearance,spec);artifacts={};final=None;layout={};metrics=[]
    if type(candidate) is OverlayCandidate:
        manifests=[native_overlay_manifest(candidate,view)]
    else:
        catalog={i:Definition.create(d) for i,d in definitions.items()};depths={};visiting=set()
        def depth(i):
            if i in visiting:fail('dependency_cycle')
            if i in depths:return depths[i]
            if i not in catalog:fail('missing_parent')
            visiting.add(i);n=max((depth(d['poster_id'])+1 for d in definitions[i]['dependencies']),default=0);visiting.remove(i);depths[i]=n;return n
        for i in catalog:depth(i)
        manifests=sorted(set(depths.values()))
    limits=WorkerLimits(workers=1,retries=0)
    with PersistentWorkers(store,config,limits) as pool:
        for stage in manifests:
            manifest=stage if type(candidate) is OverlayCandidate else Planner(config,scope='M3 isolated expanded stable identities').plan(
                tuple(catalog.values()),approved_english(),posters=sorted(i for i in catalog if depths[i]==stage),languages=['en'],dependency_artifacts=artifacts)
            layout.update(validate_native(manifest,config,view,spec))
            # Parent inputs are independently checked against owned current
            # receipts before the scheduler can consume them.
            by_id={j['id']:j for j in manifest['jobs']}
            for job in manifest['jobs']:
                for d in job['dependencies']:
                    parent=by_id.get(d['job_id'])
                    if parent is None:fail('missing_parent')
                    receipt,_=owned_receipt(store,config,parent)
                    if receipt['sha256']!=d['sha256']:fail('parent_receipt_substitution')
            execution=pool.run(tasks_from_manifest(manifest),cancel=cancel)
            if set(execution['jobs'])!=set(by_id) or any(x['status'] not in {'rendered','cache_reuse','dedup_reuse'} for x in execution['jobs'].values()):fail('interrupted_or_partial_render')
            for job in manifest['jobs']:
                receipt,_=owned_receipt(store,config,job);artifacts[job['id']]=receipt['sha256']
            metrics.append(execution['metrics']);final=manifest
    pool.workspaces.cleanup(**pool.workspace,retain_seconds=0)
    if type(candidate) is PosterCandidate:
        final=Planner(config,scope='M3 isolated expanded stable identities').plan(tuple(catalog.values()),approved_english(),
            posters=sorted(catalog),languages=['en'],dependency_artifacts=artifacts)
    if final is None or {j['poster_id'] for j in final['jobs']}!=set(definitions):fail('incomplete_render_membership')
    return final,definitions,layout,metrics


def render_parent_inputs(candidate,trial):
    """Owned prerequisite pixels only; not composition evidence or acceptance.

    Allows M2 to hash real generated parents before sealing a full child plan.
    The complete final request must still include and verify every parent.
    """
    from .previews import CompositionTrial
    if type(trial) is not CompositionTrial or type(candidate) is not PosterCandidate:fail('unsupported_parent_adapter')
    trial.require(candidate);candidate.verify();view=candidate.registry.view()
    if any(view.entry(i)['origin']!='assigned' for i in candidate.graph.index().outputs):fail('historical_render_forbidden')
    store=SidecarStore(candidate.registry.operations.root).backend
    manifest,_,_,_=render_view(candidate,view,candidate.config,'default',request_spec(candidate),store)
    return {j['id']:owned_receipt(store,candidate.config,j)[0]['sha256'] for j in manifest['jobs']}


def compose(context,trial,*,exceptions=(),cancel=None):
    from .previews import CompositionTrial,CompositionArchive
    if type(context) is not CompositionContext or type(trial) is not CompositionTrial:fail('typed_composition_context_required')
    candidate,view,required,impact=context.verify();trial.require(candidate)
    spec=request_spec(candidate,exceptions);store=SidecarStore(context.registry.operations.root).backend
    archive=CompositionArchive(context.registry.operations.root);views=[];index=candidate.graph.index()
    for appearance in ('default','requested'):
        config=trial.view_config(appearance)
        manifest,definitions,layout,metrics=render_view(candidate,view,config,appearance,spec,store,cancel=cancel)
        members=[];sources={}
        for job in manifest['jobs']:
            i=job['poster_id'];e=view.entry(i);receipt,raw=owned_receipt(store,config,job)
            output_ref=archive.put_bytes(raw);receipt_ref=archive.put_json(receipt)
            for source in job['inputs']:
                path=confined(config.asset_dir,source['path'],must_exist=True);source_raw=input_bytes(path)
                if sha256(path)!=source['sha256']:fail('input_drift')
                sources[source['path']]=dict(path=source['path'],sha256=source['sha256'],object_sha256=archive.put_bytes(source_raw))
            members.append(dict(identity=i,category=e['category'],variant=e['variant'],presentation=e['semantic']['role'],
                job_id=job['id'],render_fingerprint=job['render_fingerprint'],local_path=job['local_relative'],public_path=job['remote_relative'],
                sha256=receipt['sha256'],bytes=receipt['size'],object_sha256=output_ref,receipt_object_sha256=receipt_ref,
                receipt_sha256=receipt['receipt_sha256'],companions=index.outputs[i]['companions'],parent_jobs=sorted(d['job_id'] for d in job['dependencies']),
                origin_json=canonical(candidate.data().get('families',{})).decode(),**image_properties(raw,job)))
        graph=candidate.graph.data()
        for member in members:
            row=graph['outputs'][member['identity']];checksum=fingerprint(dict(member=member,definition=definitions[member['identity']]))
            row['context_sha256']=checksum;graph['nodes'][row['node']]['sha256']=checksum
        native_graph=Snapshot.create(graph);difference=compare(candidate.graph,native_graph)
        views.append(dict(appearance=appearance,manifest_sha256=manifest['sha256'],manifest_json=canonical(manifest).decode(),
            definitions_json=canonical(definitions).decode(),sources=sorted(sources.values(),key=lambda s:s['path']),
            members=sorted(members,key=lambda m:m['identity']),layout_json=canonical(layout).decode(),impact_json=canonical(difference).decode(),execution_json=canonical(metrics).decode()))
    op=impact.to_dict()['operation'];runtime_value=runtime(json.loads(views[0]['manifest_json'])['renderer'])
    value=CompositionEvidence.from_dict(dict(**HEADER,kind='composition-evidence',complete=True,operation=op,required_members=required,
        context_json=canonical(dict(candidate_sha256=candidate.sha256,impact_sha256=impact.sha256,registry_sha256=candidate.registry_head.snapshot_sha256,
            operation=op,request_json=canonical(spec).decode(),required_members=required,original_outputs=json.loads(impact.to_dict()['details_json'])['before_mappings'],base_graph_sha256=candidate.graph.sha256)).decode(),
        runtime_json=canonical(runtime_value).decode(),views=views))
    archive.save(value,context=context)
    return value
