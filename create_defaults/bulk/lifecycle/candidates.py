"""Read-only actual loader/planner adapters with pre-seal semantic identity lookup.

No renderer, worker, historical-record constructor, approval or catalog writer.
The original Planner/generators stay byte-for-byte unchanged. Its public expand
hook resolves owned definitions before its plan method seals any job.
"""

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from ..common import canonical, confined, fingerprint, load_yaml, reject_links, sha256
from ..config import Config
from ..definitions import Definition, load_definitions
from ..generators import GENERATORS
from ..planner import Planner
from ..contracts.models import Identity
from ..contracts.adoption.models import read_canonical
from ..contracts.expanded.resolution import Resolution, contribution
from ..contracts.expanded.graph import Snapshot, node_id
from ..contracts.expanded.validation import approved_english, check_renderer, validate_candidate
from ..contracts.categories.validation import Assignment, check_job, check_membership, check_names
from ..contracts.categories.dependencies import material_design
from .basis import historical_basis, semantic_tokens
from .coverage import matrix, require_variant
from .identities import RegistryHead
from .identity_models import HEADER, fail


def _member(view, identity):
    entry=view.entry(identity)
    if entry["tombstone_sha256"] is not None or entry["semantic"]["role"] in {"group","family"}:fail("retired_or_non_output_identity")
    return entry


class StablePlanner(Planner):
    """Only the public expansion boundary changes; job sealing stays Package E."""
    def __init__(self, view, config):
        super().__init__(config,generators=GENERATORS,scope="isolated P4/M2 prospective plan; no approval")
        self.view=view

    def expand(self, definitions):
        catalog,families,origins=super().expand(definitions)
        remap={};basis=historical_basis();declared={d.id:d.data for d in definitions}
        for parent,children in families.items():
            if parent not in basis.parents:
                e=self.view.entry(parent)
                if e["semantic"]["role"]!="family" or e["category"]!=declared[parent]["category"] or e["tombstone_sha256"] is not None:fail("generator_parent_identity")
            tokens=semantic_tokens(declared[parent])
            if len(tokens)!=len(children):fail("semantic_generator_membership")
            lookup=dict(basis.semantic_index())
            lookup.update({(e["category"],e["semantic"]["parent"],e["semantic"]["key"],e["semantic"]["role"],e["semantic"]["language"]):e["id"] for e in self.view.entries()})
            for raw,token in zip(children,tokens):
                matches={i for (c,p,k,role,lang),i in lookup.items() if c==declared[parent]["category"] and p==parent and k==token and lang=="en"}
                if len(matches)!=1:fail("unallocated_or_ambiguous_generator_child")
                remap[raw]=matches.pop()
        for raw in catalog:
            remap.setdefault(raw,raw)
        result={}
        for raw,definition in catalog.items():
            identity=remap[raw];entry=_member(self.view,identity)
            value=definition.data
            if value["category"]!=entry["category"]:fail("identity_category_substitution")
            value["id"]=identity
            for dependency in value["dependencies"]:
                if dependency["poster_id"] not in remap:fail("missing_private_parent")
                dependency["poster_id"]=remap[dependency["poster_id"]]
            if identity in result:fail("expanded_identity_collision")
            result[identity]=Definition.create(value)
        return result,{p:[remap[c] for c in children] for p,children in families.items()},{remap[i]:v for i,v in origins.items()}


def resolve_stable(paths, profiles_path, view):
    """Original strict YAML loader/profiles, with the reviewed pre-seal adapter."""
    paths=tuple(Path(p) for p in paths);profiles_path=Path(profiles_path)
    all_paths=(*paths,profiles_path)
    if len({p.name for p in all_paths})!=len(all_paths):fail("ambiguous_definition_sources")
    before={}
    for p in all_paths:
        p=reject_links(p)
        if not p.is_file() or p.stat().st_size>2_000_000:fail("definition_source_bound")
        before[str(p)]=p.read_bytes()
    definitions=load_definitions(paths,profiles_path=profiles_path)
    expanded,families,origins=StablePlanner(view,Config()).expand(definitions)
    profiles=load_yaml(profiles_path)["profiles"];provenance={}
    for p in paths:
        for raw in load_yaml(p)["definitions"]:
            parent=raw.get("extends")
            provenance[raw["id"]]=dict(file=p.name,profile_file=profiles_path.name,profile=parent,
                row_sha256=fingerprint({k:v for k,v in raw.items() if k!="extends"}),
                inherited_sha256=fingerprint(contribution(profiles.get(parent,{}),raw)))
    if any(p.read_bytes()!=before[str(p)] for p in all_paths):fail("unstable_definition_source")
    value=dict(schema_version=1,allowlist_version=1,declared={d.id:d.data for d in definitions},
        expanded={i:d.data for i,d in expanded.items()},families=families,origins=origins,provenance=provenance)
    # Reuse M5's cycle/missing-edge validator even before a job can be sealed.
    nodes={node_id("definition",i):dict(kind="definition",identity=i,sha256=d.fingerprint,
        dependencies=sorted(node_id("definition",x["poster_id"]) for x in d.data["dependencies"])) for i,d in expanded.items()}
    Snapshot.create(dict(schema_version=1,kind="m5-dependency-snapshot",basis=view.snapshot.sha256,nodes=nodes,outputs={},unresolved=[]))
    pins=tuple((p.name,str(p.resolve()),hashlib.sha256(before[str(p)]).hexdigest()) for p in all_paths)
    return Resolution(canonical(value),pins)


def _assignment(entry, definition, job, package, rule, content, resolution):
    names=entry["names"];variant=entry["variant"]
    package.contract.validate_content(variant,content)
    for field in ("display_name","source"):
        if field not in content or content[field]!=names[field]:fail("content_identity_substitution")
    if definition["display_name"]!=names["display_name"] or job["parameters"].get("text")!=names["rendered_caption"]:
        fail("caption_or_display_mapping")
    types=read_canonical(rule["caption_types_json"])
    possible=[key for key,t in types.items() if read_canonical(t["definition_json"])==definition["caption"] and t["text"]==job["parameters"]["text"] and read_canonical(t["translation_json"])==job["translation"]]
    caption_type=content.get("content_type")
    if caption_type is None and len(possible)==1:caption_type=possible[0]
    if caption_type not in possible:fail("unsupported_caption_type")
    if "background_proposal" in content:background=content["background_proposal"]
    else:
        # A submitter cannot select a background by hiding it in YAML/profile.
        # Without an explicitly permitted proposal retain the captured template.
        _,members=package.data()
        exemplar=next((i for i,m in members.items() if m["variant"]==variant),None)
        base=historical_basis().resolution.definition(exemplar)
        background=base["composer"]["base_color"]
    if entry["origin"]=="assigned":
        from pathlib import PurePosixPath
        _,members=package.data()
        peers=[historical_basis().row(i)["identity"] for i,m in members.items() if m["variant"]==variant]
        local_roots={str(PurePosixPath(i["local_path"]).parent) for i in peers}
        public_roots={str(PurePosixPath(i["public_path"]).parent) for i in peers if i["public_path"] is not None}
        if str(PurePosixPath(job["local_relative"]).parent) not in local_roots or (job["remote_relative"] is not None and str(PurePosixPath(job["remote_relative"]).parent) not in public_roots):
            fail("unapproved_category_output_route")
    return Assignment(identity=entry["id"],job_id=job["id"],variant=variant,
        local_path=names["local_path"],public_path=names["public_path"],source_json=canonical(names["source"]).decode(),
        background=background,caption_type=caption_type,presentation=entry["semantic"]["role"],
        group=(entry["semantic"]["parent"] or entry["id"])+"/"+entry["semantic"]["key"])


def _graph(resolution,manifest,view,results,baseline):
    value=baseline.data() if baseline else dict(schema_version=1,kind="m5-dependency-snapshot",
        basis=historical_basis().registry_sha256,nodes={},outputs={},unresolved=[])
    nodes,outputs=value["nodes"],value["outputs"];r=resolution.data()
    parent_for={c:p for p,cs in r["families"].items() for c in cs}
    output_for_job={j["id"]:j["poster_id"] for j in manifest["jobs"]}
    groups={}
    for result in results:groups.setdefault((result["contract_sha256"],result["group"]),[]).append(result["identity"])
    checked={x["identity"]:x for x in results}
    def put(kind,identity,checksum,deps=()):
        k=node_id(kind,identity);nodes[k]=dict(kind=kind,identity=identity,sha256=checksum,dependencies=sorted(set(deps)));return k
    for job in manifest["jobs"]:
        identity=job["poster_id"];entry=_member(view,identity);definition=resolution.definition(identity)
        deps=[put("asset",i["path"],i["sha256"]) for i in job["inputs"]]
        for d in job["dependencies"]:
            if d["job_id"] not in output_for_job:fail("missing_private_parent")
            deps.append(node_id("output",output_for_job[d["job_id"]]))
        parent=parent_for.get(identity,identity);p=r["provenance"][parent]
        origins=[put("row",p["file"]+"#"+parent,p["row_sha256"])]
        if p["profile"]:origins.append(put("profile",p["profile_file"]+"#"+p["profile"]+"#"+parent,p["inherited_sha256"]))
        if identity in parent_for:
            origin=r["origins"][identity];name=origin["specification"]["name"]+"@"+str(origin["specification"]["version"])
            origins.append(put("generator",name,origin["code_sha256"]))
            origins.append(put("family",parent,fingerprint(sorted(r["families"][parent]))))
        deps.append(put("definition",identity,fingerprint(definition),origins))
        deps.append(put("transform","poster",fingerprint(manifest["renderer"])))
        deps.append(put("background",identity,fingerprint(dict(color=job["parameters"]["base_color"],assignment=job["color_assignment"]))))
        for trace in job["translation"]["trace"]:deps.append(put("caption",trace["language"]+"/"+trace["key"],fingerprint(trace)))
        package,rule=require_variant(entry["category"],entry["variant"])
        design=next(v["design"] for v in package.contract.to_dict()["variants"] if v["id"]==entry["variant"])
        deps.append(put("rules","m6/"+identity,fingerprint(dict(rule=material_design(design,rule),assignment=checked[identity]))))
        context=fingerprint(dict(identity=entry,definition=definition,job=job,validation=checked[identity],renderer=manifest["renderer"]))
        output=put("output",identity,context,deps)
        prior=outputs.get(identity)
        outputs[identity]=dict(node=output,category=entry["category"],kind="poster",variant=entry["variant"],
            local_path=job["local_relative"],public_path=job["remote_relative"],
            companions=sorted(i for i in groups[(checked[identity]["contract_sha256"],checked[identity]["group"])] if i!=identity),
            context_sha256=context,evidence=prior["evidence"] if prior else {f:[] for f in ("previews","confirmations","decisions","receipts")})
    return Snapshot.create(value)


@dataclass(frozen=True)
class PosterCandidate:
    registry: object
    registry_head: RegistryHead
    paths: tuple
    profiles_path: Path
    posters: tuple
    content_json: str
    config: Config
    artifacts_json: str
    encoded: bytes
    graph: Snapshot

    @property
    def sha256(self):return fingerprint(json.loads(self.encoded))

    def data(self):return json.loads(self.encoded)

    def verify(self):
        fresh=poster_candidate(self.registry,expected=self.registry_head,paths=self.paths,profiles_path=self.profiles_path,
            posters=self.posters,content=json.loads(self.content_json),config=self.config,
            dependency_artifacts=json.loads(self.artifacts_json))
        if fresh.encoded!=self.encoded or fresh.graph.sha256!=self.graph.sha256:fail("stale_or_forged_candidate")
        return fresh


def poster_candidate(registry,*,expected,paths,profiles_path,posters,content,config=None,dependency_artifacts=None):
    matrix()  # Closed source registries and all 278 variants must still match.
    view=next((v for v in registry.history() if v.head==expected),None)
    if view is None:fail("unknown_registry_revision")
    config=config or Config();paths=tuple(Path(p) for p in paths);posters=tuple(sorted(posters))
    resolution=resolve_stable(paths,profiles_path,view)
    resolution.verify_current()
    english=approved_english();definitions=tuple(Definition.create(d) for d in resolution.data()["declared"].values())
    manifest=StablePlanner(view,config).plan(definitions,english,posters=posters,languages=("en",),dependency_artifacts=dependency_artifacts)
    if set(content)!={j["poster_id"] for j in manifest["jobs"]}:fail("candidate_content_membership")
    check_names(manifest["jobs"]);results=[]
    for job in manifest["jobs"]:
        identity=job["poster_id"];entry=_member(view,identity)
        package,rule=require_variant(entry["category"],entry["variant"])
        definition=resolution.definition(identity);check_renderer(package.contract)
        if entry["category"]=="Playlist":
            # The accepted M3 prospective Playlist contract has fixed layout;
            # the M6 historical fitting cohort must not replace that interface.
            names=entry["names"]
            assigned=Identity.from_dict(dict(schema_version=1,kind="item-identity",id=identity,category="Playlist",
                display_name=names["display_name"],rendered_caption=names["rendered_caption"],source=names["source"],
                local_path=names["local_path"],public_path=names["public_path"],semantic_member=None))
            report=validate_candidate(resolution,manifest,identity,english,fixture_only=True,config=config,
                content=content[identity],assigned_identity=assigned)
            results.append(dict(identity=identity,contract_sha256=package.contract.sha256,group=identity,
                presentation="single",context_sha256=report["context_sha256"],source=names["source"],derived_white=False))
        else:
            assignment=_assignment(entry,definition,job,package,rule,content[identity],resolution)
            historical_member=None
            if entry["origin"]=="historical-reference":
                candidate=historical_basis().assignment(identity)
                if candidate["context_sha256"]==fingerprint(dict(definition=definition,job=job)):
                    historical_member=candidate
            results.append(check_job(package,definition,job,assignment,historical_member=historical_member))
    check_membership(results)
    graph=_graph(resolution,manifest,view,results,None)
    value=dict(**HEADER,kind="prospective-poster-plan",registry_sha256=view.snapshot.sha256,
        coverage_sha256=fingerprint(matrix()),resolution_sha256=resolution.sha256,
        source_pins={name:checksum for name,path,checksum in resolution.source_pins},
        effective_definitions=resolution.data()["expanded"],families=resolution.data()["families"],
        manifest=manifest,validation=results,graph_sha256=graph.sha256,complete=True,
        operational_blockers=["live_authority_unavailable","exact_contract_approvals_missing","complete_composition_missing","approval_integration_missing"])
    return PosterCandidate(registry,expected,paths,Path(profiles_path),posters,canonical(content).decode(),config,
        canonical(dependency_artifacts or {}).decode(),canonical(value),graph)
