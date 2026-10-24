"""Explicit source-preserving overlay membership/impact, without sealed jobs.

The existing overlay planners derive IDs from destination paths. M2 deliberately
does not rewrite sealed jobs or invent HistoricalOutput records. Native preview
job construction remains blocked pending a reviewed pre-seal identity hook.
"""

from dataclasses import dataclass
import json
from pathlib import PurePosixPath

from ..common import canonical,confined,fingerprint,sha256
from ..config import Config
from ..overlays import TRANSFORM,identity as renderer_identity
from ..contracts.expanded.graph import Snapshot,node_id
from .basis import historical_basis
from .coverage import matrix,require_variant
from .identity_models import HEADER,fail


@dataclass(frozen=True)
class OverlayCandidate:
    registry: object
    registry_head: object
    identities: tuple
    config: Config
    encoded: bytes
    graph: Snapshot

    @property
    def sha256(self):return fingerprint(json.loads(self.encoded))

    def data(self):return json.loads(self.encoded)

    def verify(self):
        current=overlay_candidate(self.registry,expected=self.registry_head,identities=self.identities,config=self.config)
        if current.encoded!=self.encoded or current.graph.sha256!=self.graph.sha256:fail("stale_or_forged_overlay_candidate")
        return current

    def jobs(self):fail("overlay_preseal_identity_hook_required")


def overlay_candidate(registry,*,expected,identities,config=None):
    config=config or Config();view=next((v for v in registry.history() if v.head==expected),None)
    if view is None:fail("unknown_registry_revision")
    identities=tuple(sorted(identities))
    if len(set(identities))!=len(identities) or not identities:fail("overlay_membership")
    branches={g["variant"]:g for g in matrix()["overlays"]};entries={i:view.entry(i) for i in identities}
    groups={};nodes={};outputs={};sources={};effective={}
    transform=renderer_identity()
    for i,e in entries.items():
        if e["category"]!="Overlays" or e["tombstone_sha256"] is not None:fail("overlay_identity")
        branch=e["variant"];package,rule=require_variant("Overlays",branch)
        if branch not in branches:fail("unsupported_overlay_branch")
        g=branches[branch];role=e["semantic"]["role"]
        if role not in {"standard","bigger"} or e["semantic"]["parent"] is None:fail("overlay_semantic_role")
        owner=(branch,e["semantic"]["parent"],e["semantic"]["key"])
        if role in groups.setdefault(owner,{}):fail("duplicate_overlay_role")
        groups[owner][role]=i
        source=e["names"]["source"]
        if source is None or source["path"].rsplit("/",1)[0] not in rule["source_roots"]:fail("overlay_source_branch")
        path=confined(config.asset_dir,source["path"],must_exist=True)
        if sha256(path)!=source["sha256"]:fail("overlay_source_hash")
        if path.suffix.lower()!=".png":fail("overlay_png_source")
        design=next(v['design'] for v in package.contract.to_dict()['variants'] if v['id']==branch)
        native={size:[box['width'],box['height']] for size,box in design['sizes'].items()}
        if native!=g['sizes'] or design['trim']!=g['trim'] or design['treatment']!='SOURCE_PRESERVING':fail('overlay_contract_geometry')
        expected_path=g['branch']+'/overlays/'+role+'/'+PurePosixPath(source['path']).name
        if e['names']['local_path']!=expected_path or e['names']['public_path']!=expected_path or e['names']['rendered_caption']!='':fail('overlay_output_mapping')
        parameters=dict(input=source["path"],box=g["sizes"][role],trim=g["trim"],colorspace="sRGB",
            strip_metadata=True,format="PNG",resampling="Pillow-LANCZOS")
        definition=dict(group=g["branch"],parameters=parameters,transform=TRANSFORM)
        effective[i]=definition;sources[i]=source
        asset=node_id("asset",source["path"])
        nodes[asset]=dict(kind="asset",identity=source["path"],sha256=source["sha256"],dependencies=[])
        material=dict(identity=e,definition=definition,contract_sha256=package.contract.sha256,renderer=transform)
        output=node_id("output",i)
        rules_key=node_id("rules","m6/"+i)
        nodes[rules_key]=dict(kind="rules",identity="m6/"+i,sha256=fingerprint(dict(rule=rule,contract=package.contract.sha256)),dependencies=[])
        transform_key=node_id("transform","overlay")
        nodes[transform_key]=dict(kind="transform",identity="overlay",sha256=fingerprint(transform),dependencies=[])
        nodes[output]=dict(kind="output",identity=i,sha256=fingerprint(material),dependencies=sorted([asset,rules_key,transform_key]))
        outputs[i]=dict(node=output,category="Overlays",kind="overlay",variant=branch,
            local_path=e["names"]["local_path"],public_path=e["names"]["public_path"],companions=[],
            context_sha256=fingerprint(material),evidence={f:[] for f in ("previews","confirmations","decisions","receipts")})
    for roles in groups.values():
        if set(roles)!={"standard","bigger"}:fail("incomplete_overlay_companions")
        a,b=roles["standard"],roles["bigger"]
        if sources[a]!=sources[b]:fail("overlay_companion_source_substitution")
        outputs[a]["companions"]=[b];outputs[b]["companions"]=[a]
    graph=Snapshot.create(dict(schema_version=1,kind="m5-dependency-snapshot",basis=historical_basis().registry_sha256,nodes=nodes,outputs=outputs,unresolved=[]))
    value=dict(**HEADER,kind="prospective-overlay-metadata",registry_sha256=view.snapshot.sha256,
        identities=list(identities),effective_definitions=effective,graph_sha256=graph.sha256,complete=True,
        job_planning_complete=False,render_ready=False,operational_blockers=["overlay_preseal_identity_hook_required",
            "live_authority_unavailable","exact_contract_approvals_missing","composition_and_approval_missing"])
    return OverlayCandidate(registry,expected,identities,config,canonical(value),graph)
