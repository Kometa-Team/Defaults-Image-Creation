"""Owned synthetic trials and immutable full-image evidence in Package E.

No review transitions, authority provider, destination access or catalog writes.
Reading an archive replays current M1/M2 context and native plans, and checks
each actual encoded image against the original durable worker receipt.
"""
from dataclasses import replace
from hashlib import sha256 as digest
from html import escape
import inspect
import json
from pathlib import Path
import tempfile

from ..common import atomic_bytes,canonical,confined,fingerprint,reject_links,sha256
from ..config import Config,ROOT
from ..contracts.models import ExceptionRequest
from ..definitions import Definition
from ..planner import Planner,SHARED_ASSETS
from ..contracts.expanded.validation import approved_english
from ..contracts.expanded.graph import Snapshot,compare
from ..workers import tasks_from_manifest,compose as native_compose
from .package_e import SidecarStore
from .composition_models import BytesObject,CompositionEvidence,fail,json_value


class CompositionTrial:
    """Lifetime capability for disposable synthetic assets and output roots.

    The only public constructor creates a new OS temporary directory. Existing
    repository/production roots cannot be adopted as a rendering trial.
    """
    def __init__(self):
        self._temp=tempfile.TemporaryDirectory(prefix='kometa-p4m3-')
        self.root=Path(self._temp.name).resolve();self._closed=False
        self.config=Config(asset_dir=self.root/'assets',cache_dir=self.root/'state',
            workspace_dir=self.root/'workspace',output_dir=self.root/'parent-inputs',offline=True)
        self.config.asset_dir.mkdir()
        fonts=json.loads((ROOT/'bulk/baselines/approved-fonts.json').read_text())['fonts']
        for name in (*SHARED_ASSETS,*fonts):
            source=confined(ROOT,name,must_exist=True);raw=source.read_bytes()
            if name in fonts and sha256(source)!=fonts[name]:fail('support_font_drift')
            target=confined(self.config.asset_dir,name);target.parent.mkdir(parents=True,exist_ok=True);atomic_bytes(target,raw)
        atomic_bytes(self.root/'trial.json',canonical(dict(kind='synthetic-composition-trial',version=1)))

    def __enter__(self):return self
    def __exit__(self,*_):self.close()
    def close(self):self._closed=True;self._temp.cleanup()

    def require(self,candidate):
        if self._closed or not (self.root/'trial.json').is_file():fail('closed_trial')
        c=candidate.config
        if c!=self.config or candidate.registry.operations.root!=self.config.cache_dir:fail('foreign_trial')
        for name in ('asset_dir','cache_dir','workspace_dir','output_dir'):
            p=reject_links(getattr(c,name)).resolve()
            if not p.is_relative_to(self.root):fail('trial_isolation')
        if not c.offline:fail('offline_trial_required')
        for i in candidate.graph.index().outputs:
            source=candidate.registry.view().entry(i)['names']['source']
            if source is not None and not Path(source['path']).name.startswith('Fixture'):
                # The contract can lock a placeholder or generated-family source
                # basename. It must still be inside this owned synthetic root.
                from .basis import historical_basis
                e=candidate.registry.view().entry(i);rule=historical_basis().rule(e['category'],e['variant'])
                if rule['source_kind'] not in {'composition','placeholder'}:fail('synthetic_asset_required')

    def stage(self,name,raw):
        locked_base=name.startswith('@base/') and name.count('/')==1
        if self._closed or not (Path(name).name.startswith('Fixture') or locked_base) or Path(name).suffix!='.png':fail('synthetic_asset_required')
        target=confined(self.config.asset_dir,name);target.parent.mkdir(parents=True,exist_ok=True)
        atomic_bytes(target,raw)
        return dict(path=name,sha256=digest(raw).hexdigest())

    def view_config(self,appearance):
        if self._closed or appearance not in {'default','requested'}:fail('closed_trial')
        # New root for every execution: reproducibility cannot be a cache hit.
        directory=Path(tempfile.mkdtemp(prefix=appearance+'-',dir=self.root))
        return replace(self.config,output_dir=directory/'outputs',workspace_dir=directory/'workspace')


class CompositionArchive:
    def __init__(self,root,*,readonly=False):
        self.store=SidecarStore.open_readonly(root) if readonly else SidecarStore(root)

    def put_bytes(self,raw):
        value=BytesObject.make(raw)
        return self.store.put_object(value.encoded,expected_sha256=value.sha256)

    def read_bytes(self,ref):return BytesObject.from_bytes(self.store.read_object(ref)).raw()

    def put_json(self,value):
        return self.store.put_object(canonical(value),expected_sha256=fingerprint(value))

    def save(self,evidence,*,context):
        evidence=self.verify(evidence,context=context)
        # Single immutable root published LAST. Partial writes are orphan blobs,
        # never a complete candidate, operation transition or approval record.
        return self.store.put_object(evidence.encoded,expected_sha256=evidence.sha256)

    def load(self,ref,*,context):
        value=CompositionEvidence.from_bytes(self.store.read_object(ref))
        if value.sha256!=ref:fail('archive_identity')
        return self.verify(value,context=context)

    def verify(self,evidence,*,context):
        from .composition import CompositionContext,runtime,request_spec,definitions_for,native_overlay_manifest,validate_native,image_properties
        from .overlay_candidates import OverlayCandidate
        if type(evidence) is not CompositionEvidence or type(context) is not CompositionContext:fail('typed_archive_context_required')
        evidence=CompositionEvidence.from_bytes(evidence.encoded);v=evidence.to_dict()
        candidate,view,required,impact=context.verify()
        if self.store.root!=context.registry.operations.root:fail('foreign_archive')
        ctx=json_value(v['context_json']);spec=json_value(ctx['request_json'])
        requests=spec.get('exceptions',{})
        if type(requests) is not dict:fail('request_shape')
        checked=request_spec(candidate,[ExceptionRequest.from_dict(r) for r in requests.values()])
        expected=dict(candidate_sha256=candidate.sha256,impact_sha256=impact.sha256,registry_sha256=candidate.registry_head.snapshot_sha256,
            operation=impact.to_dict()['operation'],request_json=canonical(checked).decode(),required_members=required,
            original_outputs=json.loads(impact.to_dict()['details_json'])['before_mappings'],base_graph_sha256=candidate.graph.sha256)
        if ctx!=expected or v['operation']!=expected['operation'] or v['required_members']!=required:fail('stale_composition_context')
        total=0;seen=set()
        for appearance in v['views']:
            manifest=json_value(appearance['manifest_json'])
            if json_value(v['runtime_json'])!=runtime(manifest['renderer']):fail('environment_or_implementation_drift')
            definitions=definitions_for(candidate,appearance['appearance'],checked)
            if json_value(appearance['definitions_json'])!=definitions:fail('definition_substitution')
            members={m['identity']:m for m in appearance['members']};outputs={}
            for m in members.values():
                raw=self.read_bytes(m['object_sha256']);outputs[m['job_id']]=raw
                if (digest(raw).hexdigest(),len(raw))!=(m['sha256'],m['bytes']):fail('output_bytes_substitution')
                if m['object_sha256'] not in seen:total+=len(raw);seen.add(m['object_sha256'])
                if total>64*1024*1024:fail('archive_resource_bound')
            # Planner's public dependency validation checks real parent bytes.
            # Rehydrate ONLY already archived bytes in an owned temporary root;
            # this is verification, not a second render or a production write.
            with tempfile.TemporaryDirectory(prefix='kometa-p4m3-replay-') as tmp:
                config=replace(candidate.config,output_dir=Path(tmp)/'outputs')
                for m in members.values():
                    p=confined(config.output_dir,m['local_path']);p.parent.mkdir(parents=True,exist_ok=True);atomic_bytes(p,outputs[m['job_id']])
                if type(candidate) is OverlayCandidate:expected_manifest=native_overlay_manifest(candidate,view)
                else:expected_manifest=Planner(config,scope='M3 isolated expanded stable identities').plan(
                    tuple(Definition.create(d) for d in definitions.values()),approved_english(),posters=required,languages=['en'],
                    dependency_artifacts={k:digest(raw).hexdigest() for k,raw in outputs.items()})
                if manifest!=expected_manifest:fail('native_plan_substitution')
                layout=validate_native(manifest,config,view,checked)
                if json_value(appearance['layout_json'])!=layout:fail('layout_evidence_substitution')
            sources={s['path']:s for s in appearance['sources']}
            expected_sources={s['path']:s['sha256'] for j in manifest['jobs'] for s in j['inputs']}
            if len(sources)!=len(appearance['sources']) or {k:s['sha256'] for k,s in sources.items()}!=expected_sources:fail('source_membership')
            for s in sources.values():
                raw=self.read_bytes(s['object_sha256'])
                if digest(raw).hexdigest()!=s['sha256'] or sha256(confined(candidate.config.asset_dir,s['path'],must_exist=True))!=s['sha256']:fail('archived_source_drift')
                if s['object_sha256'] not in seen:total+=len(raw);seen.add(s['object_sha256'])
            if total>64*1024*1024:fail('archive_resource_bound')
            tasks={t.id:t for t in tasks_from_manifest(manifest)}
            graph=candidate.graph.data()
            for job in manifest['jobs']:
                m=members[job['poster_id']];e=view.entry(m['identity']);raw=outputs[job['id']]
                if (m['category'],m['variant'],m['presentation'],m['companions'])!=(e['category'],e['variant'],e['semantic']['role'],candidate.graph.index().outputs[m['identity']]['companions']):fail('member_context_substitution')
                if json_value(m['origin_json'])!=candidate.data().get('families',{}):fail('family_origin_substitution')
                if image_properties(raw,job)!={k:m[k] for k in ('format','mode','dimensions')}:fail('image_geometry_substitution')
                receipt=json.loads(self.store.read_object(m['receipt_object_sha256']))
                with self.store.read_connection() as db:row=db.execute('SELECT * FROM jobs WHERE id=?',(receipt.get('job_id'),)).fetchone()
                renderer_id=fingerprint(inspect.getsource(native_compose))
                task_spec=dict(task=tasks[job['id']].spec(),renderer_identity=renderer_id)
                if not row or row['status']!='verified' or row['receipt']!=canonical(receipt).decode() or row['spec']!=canonical(task_spec).decode() or row['fingerprint']!=fingerprint(task_spec):fail('durable_receipt_substitution')
                if (receipt.get('logical_id'),receipt.get('relative'),receipt.get('render_fingerprint'),receipt.get('renderer_identity'),receipt.get('sha256'),receipt.get('size'),receipt.get('job_fingerprint'),receipt.get('receipt_sha256'))!=(job['id'],m['local_path'],m['render_fingerprint'],renderer_id,m['sha256'],m['bytes'],row['fingerprint'],m['receipt_sha256']):fail('receipt_substitution')
                if fingerprint({k:x for k,x in receipt.items() if k!='receipt_sha256'})!=m['receipt_sha256']:fail('receipt_hash')
                for dep in job['dependencies']:
                    parent=next((x for x in members.values() if x['job_id']==dep['job_id']),None)
                    if parent is None or parent['sha256']!=dep['sha256'] or parent['render_fingerprint']!=dep['render_fingerprint']:fail('parent_receipt_substitution')
                rowgraph=graph['outputs'][m['identity']];checksum=fingerprint(dict(member=m,definition=definitions[m['identity']]))
                rowgraph['context_sha256']=checksum;graph['nodes'][rowgraph['node']]['sha256']=checksum
            if json_value(appearance['impact_json'])!=compare(candidate.graph,Snapshot.create(graph)):fail('composition_impact_substitution')
        context.verify()
        return evidence

    def gallery(self,ref,*,context,directory):
        """Explicit export of verified, exact full-resolution bytes for review.

        Only a fresh child of the repository's ignored CI evidence root is
        allowed; callers cannot overwrite existing artwork or HTML.
        """
        evidence=self.load(ref,context=context);directory=reject_links(directory).resolve()
        allowed=(ROOT.parent/'config/phase4-ci',ROOT.parent/'config/ci-validation/phase4-m3')
        if not any(directory.is_relative_to(p) and directory!=p for p in allowed) or directory.exists():fail('review_export_isolation')
        directory.mkdir(parents=True);rows=[]
        for view in evidence.to_dict()['views']:
            for m in view['members']:
                name=view['appearance']+'-'+fingerprint(m['identity'])+'.'+('jpg' if m['format']=='JPEG' else 'png')
                atomic_bytes(directory/name,self.read_bytes(m['object_sha256']))
                rows.append('<figure><figcaption>'+escape(view['appearance']+' / '+m['identity']+' / '+m['sha256'])+'</figcaption><a href="'+name+'"><img style="max-width:480px" src="'+name+'" alt="Full composed candidate"></a></figure>')
        atomic_bytes(directory/'review.html',('<!doctype html><meta charset="utf-8"><title>Synthetic M3 composition evidence</title><h1>Synthetic candidates — no approval or publication</h1><p>Evidence '+ref+'</p>'+''.join(rows)).encode())
        return directory/'review.html'
