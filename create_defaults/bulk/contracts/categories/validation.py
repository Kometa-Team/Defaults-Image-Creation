"""Opt-in final-job checks. No renderer, artifact approval or activation.

Assignments are controlled caller inputs, not fields accepted from YAML. The
M5 adapter replays the real planner before these rules see serialized jobs.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath
import unicodedata

from ...common import BulkError,canonical,fingerprint,path_key,relative_path
from ...definitions import Definition
from ...planner import effective_parameters,validate_manifest
from ..adoption.models import read_canonical
from ..expanded.resolution import plan
from ..expanded.validation import approved_english
from .compiler import style,layout_shape
from .policy import WHITE_DEFAULTS,PAIRED
from .release import authorize


def same(expected,observed,field):
    if canonical(expected)!=canonical(observed):
        raise BulkError("category_effective_mismatch","Protected effective context differs: "+field)


@dataclass(frozen=True)
class Assignment:
    """Controlled identity/presentation/source assignment, never contributor JSON.

    This is integrity context, NOT approval. New sources still need M4 PNG and
    complete composition evidence. Existing historical exceptions cannot be
    transferred to this interface.
    """
    identity: str
    job_id: str
    variant: str
    local_path: str
    public_path: str | None
    source_json: str
    background: str | None
    caption_type: str | None
    presentation: str
    group: str
    derived_white: bool=False


def check_job(package,definition,job,assignment,*,historical_member=None,_prepared=None):
    """Validate one final effective definition/job, including protected raw intent.

    historical_member is only supplied by the pinned full-record audit below;
    normal intake never supplies an exception dictionary.
    """
    if not isinstance(assignment,Assignment):
        raise BulkError("category_assignment","Controlled assignment is required")
    c,rules,members=_prepared[:3] if _prepared is not None else (package.contract.to_dict(),*package.data())
    if assignment.variant not in rules:
        raise BulkError("category_unknown_variant","Contributor cannot invent or switch a closed variant")
    rule=rules[assignment.variant]
    design=next(v["design"] for v in c["variants"] if v["id"]==assignment.variant)
    source=read_canonical(assignment.source_json)
    relative_path(source["path"])
    if historical_member is None and any(p is not None and unicodedata.normalize("NFC",p)!=p
            for p in (source["path"],assignment.local_path,assignment.public_path)):
        raise BulkError("category_non_nfc_name","New mappings must already be NFC; accepted historical names are never rewritten")
    roots=set(rule["source_roots"])
    if assignment.derived_white:
        if c["kind"]!="poster" or rule["treatment"]!="BOTH_REQUIRED" or assignment.presentation!="white":
            raise BulkError("category_source_route","Derived white route is only for paired white output")
        roots.update(root for key in rule["companion_variants"] if rules[key]["presentation"]=="color" for root in rules[key]["source_roots"])
    if str(PurePosixPath(source["path"]).parent) not in roots and source["path"] not in roots:
        raise BulkError("category_source_branch","Source is outside the selected closed historical branch")
    same(job["id"],assignment.job_id,"stable job identity")
    same(job["local_relative"],assignment.local_path,"exact local filename/Unicode")
    same(job["remote_relative"],assignment.public_path,"exact public filename/Unicode")
    same(job["kind"],c["kind"],"poster versus overlay")
    same(job["language"],"en","implemented English scope")
    actual_sources=[{k:i[k] for k in ("path","sha256")} for i in job["inputs"] if i["path"]==source["path"]]
    if source not in actual_sources and rule["source_kind"]!="composition":
        raise BulkError("category_source_substitution","Assigned source path/hash is not the final job input")
    expected=read_canonical(rule["style_json"])
    if c["kind"]=="overlay":
        same(definition["group"].replace("/","."),assignment.variant,"overlay branch")
        same(definition["parameters"],job["parameters"],"overlay final definition")
        same(job["raw_parameters"],job["parameters"],"overlay raw parameters")
        same(job["variant"],assignment.presentation,"overlay size role")
        if assignment.presentation not in design["sizes"]:
            raise BulkError("category_overlay_size","Unknown overlay size")
        box=design["sizes"][assignment.presentation]
        same(job["parameters"]["box"],[box["width"],box["height"]],"overlay box")
        same(job["parameters"]["input"],source["path"],"overlay source")
        if "white_wash" in job["parameters"]:
            raise BulkError("category_overlay_wash","Poster treatment must not enter overlay jobs")
    else:
        same(assignment.presentation,rule["presentation"],"closed presentation role")
        same(definition["category"],c["category"],"expanded category selector")
        same(definition["id"],assignment.identity,"stable definition identity")
        same(job["poster_id"],assignment.identity,"final job owner")
        same(job["definition_fingerprint"],fingerprint({"definition":definition,"generator_origin":job["generator_origin"]}),"effective definition seal")
        same(effective_parameters(job["raw_parameters"]),job["parameters"],"effective composer normalization")
        same(layout_shape(definition),read_canonical(rule["layout_json"]),"captured fitting bounds")
        types=_prepared[3][assignment.variant] if _prepared is not None and len(_prepared)>3 else read_canonical(rule["caption_types_json"])
        if assignment.caption_type not in types:
            raise BulkError("category_caption_type","Unregistered caption content type")
        caption=types[assignment.caption_type]
        same(definition["caption"],read_canonical(caption["definition_json"]),"caption definition")
        same(job["parameters"]["text"],caption["text"],"resolved caption")
        same(job["translation"],read_canonical(caption["translation_json"]),"caption provenance")
        same(job["parameters"]["base_color"],assignment.background,"assigned background")
        same(job["parameters"]["logo"],source["path"],"logo source")
        fonts=[{k:i[k] for k in ("path","sha256")} for i in job["inputs"] if i["role"]=="font"]
        same(fonts,[design["typography"]["asset"]],"actual font hash and identity")
        # Historical exceptions need exact unchanged M2 context. A new item
        # selected into that same design cohort still gets the category default.
        if historical_member is None:
            if c["category"] in WHITE_DEFAULTS and rule["source_kind"]=="logo":
                expected["white_wash"]=True
            if rule["treatment"]=="SOURCE_PRESERVING":
                expected["white_wash"]=False
            if assignment.derived_white:
                if rule["treatment"]!="BOTH_REQUIRED" or assignment.presentation!="white":
                    raise BulkError("category_source_route","Derived white route is only for paired white output")
                expected["white_wash"]=True
        same(job["layout_evidence"],definition["layout"],"final fitting evidence")
        composer=dict(definition["composer"],text=job["parameters"]["text"])
        same(composer,job["raw_parameters"],"definition to serialized worker parameters")
    same(style(job),expected,"all protected style leaves")
    if historical_member is not None:
        same(members.get(assignment.identity),historical_member,"exact historical exception scope")
        same(historical_member["source"],source,"grandfathered source")
        same(historical_member["context_sha256"],fingerprint({"definition":definition,"job":job}),"entire unchanged historical review context")
    return {"identity":assignment.identity,"variant":assignment.variant,"presentation":assignment.presentation,
        "kind":"m5-effective-validation","context_sha256":fingerprint({"assignment":assignment.__dict__,"definition":definition,"job":job,"contract":package.contract.sha256}),
        "group":assignment.group,"source":source,"derived_white":assignment.derived_white,
        "contract_sha256":package.contract.sha256,"definition_sha256":fingerprint(definition),"job_sha256":fingerprint(job),
        "compatibility":"accepted_historical_exception" if historical_member and historical_member["exceptions"] else "compatible",
        "new_asset_review":"not_granted","artifact_approved":False,"publication_authorized":False}


def check_membership(results):
    seen=set();groups={}
    for value in results:
        if value["identity"] in seen:
            raise BulkError("category_duplicate_identity","Duplicate stable item identity")
        seen.add(value["identity"])
        role=value["presentation"]
        key=(value["contract_sha256"],value["group"])
        if role in groups.setdefault(key,{}):
            raise BulkError("category_duplicate_variant","Duplicate required presentation")
        groups[key][role]=value
    for roles in groups.values():
        expected={"standard","bigger"} if set(roles)&{"standard","bigger"} else {"white","color"} if set(roles)&{"white","color"} else {"single"}
        if set(roles)!=expected:
            raise BulkError("category_missing_variant","Required output membership is incomplete")
        if "standard" in roles:
            same(roles["standard"]["source"],roles["bigger"]["source"],"overlay companion source")
        if "white" in roles and roles["white"]["derived_white"]:
            same(roles["white"]["source"],roles["color"]["source"],"derived white master source")


def check_names(jobs):
    for field in ("local_relative","remote_relative"):
        seen=set()
        for job in jobs:
            value=job[field]
            if value is None:continue
            relative_path(value)
            key=path_key(value)
            if key in seen:
                raise BulkError("category_naming_collision","Case/Unicode equivalent output paths collide")
            seen.add(key)


def validate_selection(implementation,resolution,manifest,assignments,*,authorities=None,fixture_only=False,
                       config=None,dependency_artifacts=None):
    """Replay M5/Package E final jobs before opting into category validation.

    No category activation or operations are installed into production. Missing
    contract approval blocks the operational mode. Fixture reports never grant
    contract/artifact/publication authority.
    """
    if fixture_only and authorities:
        raise BulkError("category_authority_mode","Fixture and operational authority cannot be mixed")
    validate_manifest(manifest)
    selection=manifest["selection"]
    english=approved_english()
    replay=plan(resolution,english,config=config,categories=selection["categories"],posters=selection["posters"],
                languages=selection["languages"],dependency_artifacts=dependency_artifacts)
    for field in ("renderer","jobs","selection","not_applicable"):
        same(replay[field],manifest[field],"real Package E replay: "+field)
    if set(assignments)!={j["id"] for j in manifest["jobs"]}:
        raise BulkError("category_assignment","Every final job requires exactly one controlled assignment")
    check_names(manifest["jobs"]);results=[]
    for job in manifest["jobs"]:
        if job["kind"]!="poster":
            raise BulkError("category_overlay_selection","Use the dedicated overlay audit; poster planner cannot infer overlays")
        definition=resolution.definition(job["poster_id"],job["language"])
        package=implementation.select(definition["category"])
        from ..expanded.validation import check_renderer
        check_renderer(package.contract)
        assignment=assignments[job["id"]]
        if not fixture_only:
            authorize(package,assignment.variant,(authorities or {}).get(job["id"]))
        results.append(check_job(package,definition,job,assignment))
    check_membership(results)
    return {"kind":"m6-effective-selection","items":results,"manifest_sha256":fingerprint(manifest),
        "fixture_only":fixture_only,"contract_authorized":not fixture_only,"production_enforcement":False,
        "artifact_approved":False,"publication_authorized":False,"merge_authorized":False}


def validate_overlays(implementation,manifest,assignments,*,groups,sources,config=None,authorities=None,fixture_only=False):
    """Dedicated existing-overlay replay; no poster policy or inferred branches.

    Source selection is supplied by the controlled caller. The actual Package E
    overlay planner checks PNG integrity but never draws or publishes artwork.
    """
    from ... import overlays
    if fixture_only and authorities:
        raise BulkError("category_authority_mode","Fixture and operational authority cannot be mixed")
    validate_manifest(manifest)
    replay=overlays.plan(config,groups=groups,sources=sources,sizes=("standard","bigger"))
    for field in ("renderer","jobs","selection","not_applicable"):
        same(replay[field],manifest[field],"existing overlay planner replay: "+field)
    if set(assignments)!={j["id"] for j in manifest["jobs"]}:
        raise BulkError("category_assignment","Every overlay member needs a controlled assignment")
    package=implementation.select("Overlays");results=[];check_names(manifest["jobs"])
    for job in manifest["jobs"]:
        assignment=assignments[job["id"]]
        if not fixture_only:authorize(package,assignment.variant,(authorities or {}).get(job["id"]))
        group=assignment.variant.replace(".","/")
        definition={"group":group,"parameters":job["parameters"],"transform":overlays.TRANSFORM}
        same(job["definition_fingerprint"],fingerprint(definition),"overlay definition seal")
        results.append(check_job(package,definition,job,assignment))
    check_membership(results)
    return {"kind":"m6-effective-overlay-selection","items":results,"fixture_only":fixture_only,
        "contract_authorized":not fixture_only,"artifact_approved":False,"publication_authorized":False,"production_enforcement":False}
