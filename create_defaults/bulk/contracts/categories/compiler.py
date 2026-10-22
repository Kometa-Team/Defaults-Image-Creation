"""Reproducible data compiler from exact M2 facts, not a drawing engine.

The resulting contracts await exact maintainer approval. Existing renderer
parameters and caption resolution remain Package E's responsibility.
"""

from collections import defaultdict
from pathlib import Path,PurePosixPath

from fontTools.ttLib import TTFont

from ...common import BulkError,canonical,fingerprint,sha256
from ...config import ROOT,CATEGORIES
from ...overlays import identity as overlay_identity,TRANSFORM
from ...planner import renderer_identity
from ..adoption.models import read_canonical,encoded_json
from ..models import Contract,RegistryDocument
from ..playlist.validation import CONTRACT_SHA256,M2_SHA256
from .models import Release,Rules
from .policy import source_kind,treatment,presentation,companions,WHITE_DEFAULTS


HERE=Path(__file__).parent
CONTRACT_ROOT=HERE.parent
BASE_SHA="e611076e23cab31efa578ee92f1514bc993e9f93"
VERSION="1.0.0"
CONTENT_PARAMETERS={"logo","input","base_color","out_name","text"}


def provenance():
    root=ROOT/"lifecycle"
    return {"baseline_source":BASE_SHA,"baseline_registry":M2_SHA256,"compiler_version":1,
        **{key:fingerprint((root/name).read_text(encoding="utf8").replace("\r\n","\n")) for key,name in (
            ("architecture_sha256","PHASE2_DESIGN_PROPOSAL.md"),("matrix_sha256","CATEGORY_RULES_MATRIX.md"),
            ("exceptions_sha256","EXCEPTIONS_REGISTER.md"))}}


def font_facts(reference,root=ROOT):
    path=root/reference["path"]
    if sha256(path)!=reference["sha256"]:
        raise BulkError("category_font","Actual font bytes changed")
    with TTFont(path,lazy=True) as font:
        family=font["name"].getDebugName(16) or font["name"].getDebugName(1)
        return {"family":family,"weight":int(font["OS/2"].usWeightClass)}


def style(job):
    if job["kind"]=="overlay":
        return {k:v for k,v in job["raw_parameters"].items() if k not in {"input","box"}}
    return {k:v for k,v in job["raw_parameters"].items() if k not in CONTENT_PARAMETERS}


def layout_shape(definition):
    layout=definition.get("layout")
    if layout is None:
        return {}
    measurement=layout["measurement"]
    return {"kind":layout["kind"],"bounds":{k:v for k,v in (measurement or {}).items()
        if k not in {"text","evidence_sha256","point_size","font_sha256"}}}


def signature(value,definition,job):
    kind=source_kind(value)
    if job["kind"]=="overlay":
        return {"branch":definition["group"],"style":style(job)}
    caption={k:v for k,v in definition["caption"].items() if k not in {"key","text","suffix"}}
    return {"style":style(job),"caption":caption,"layout":layout_shape(definition),
        "source_kind":kind,"presentation":presentation(value,job),"treatment":treatment(value["identity"]["category"],kind)}


def variant_id(value,definition,job):
    if value["identity"]["category"]=="Playlist":
        return "timeline-order"
    if job["kind"]=="overlay":
        return definition["group"].replace("/",".")
    return source_kind(value)+"-"+presentation(value,job)+"-"+fingerprint(signature(value,definition,job))[:16]


def caption_types(rows,english):
    result={}
    for value,definition,job in rows:
        c=definition["caption"]
        key="caption-"+fingerprint(c)[:20]
        result[key]={"definition_json":encoded_json(c),"text":job["parameters"]["text"],
                     "translation_json":encoded_json(job["translation"])}
    return result


def caption_design(types,english):
    values=[read_canonical(t["definition_json"]) for t in types.values()]
    first=values[0]
    content=[]
    for key,item in sorted(types.items()):
        c=read_canonical(item["definition_json"])
        template=english.lookup("en",c["template_key"])[0] if c["template_key"] else "{value}"
        content.append({"id":key,"mode":c["mode"],"value":c["key"] if c["mode"]=="translation" else c["text"],"template":template})
    return {"requirement":"prohibited" if first["mode"]=="none" else "required","case":first["case"],
        "languages":["en"],"registry_sha256":english.hashes["en"],"content_types":content}


def compile_category(category,rows,pairs,english,font_cache,provenance_value):
    grouped=defaultdict(list)
    for row in rows:
        grouped[variant_id(*row)].append(row)
    variants=[];rules={};members={}
    for key,items in sorted(grouped.items()):
        value,d,j=items[0];p=j["parameters"];kind=source_kind(value)
        policy=treatment(category,kind)
        acceptance=sorted({ref["record_sha256"] for v,_,_ in items for ref in v["evidence"]["approval_refs"]})
        exception_refs=sorted({e["evidence_sha256"] for v,_,_ in items for e in v["historical_exceptions"]})
        roots=sorted({str(PurePosixPath(v["identity"]["source"]["path"]).parent)
                      if kind not in {"placeholder","composition"} else v["identity"]["source"]["path"] for v,_,_ in items})
        if category=="Overlays":
            group=d["group"]
            design={"treatment":"SOURCE_PRESERVING","source_branch":group.replace("/","."),"trim":p["trim"],
                "sizes":{"standard":{"width":285,"height":85},"bigger":{"width":440,"height":100}},
                "rounding":"half-up","resampling":"Lanczos","format":"PNG","mode":"RGBA","color_space":"sRGB",
                "compression":9,"preserve_basename":True,
                "transformation":{"id":"existing-overlay","sha256":overlay_identity()["sources"]["bulk/overlays.py"]}}
            types={};fields=["display_name","source"];role="overlay";required=["standard","bigger"]
        else:
            font_ref=next({"path":a["path"],"sha256":a["sha256"]} for a in j["inputs"] if a["role"]=="font")
            if font_ref["path"] not in font_cache:
                font_cache[font_ref["path"]]=font_facts(font_ref)
            typog={"asset":font_ref,**font_cache[font_ref["path"]],"size":p["font_size"],"color":p["font_color"]}
            measurement=d["layout"]["measurement"]
            fits={v["identity"]["id"]:job["layout_evidence"] for v,_,job in items}
            fitting=None if measurement is None else {"mode":d["layout"]["kind"],"width":measurement["box"][0],
                "height":measurement["box"][1],"minimum_size":measurement["minimum"],"maximum_size":measurement["maximum"],
                "measurement_sha256":fingerprint(fits)}
            types=caption_types(items,english)
            assignments={v["identity"]["id"]:{"color":job["parameters"]["base_color"],"provenance":job["color_assignment"]}
                         for v,_,job in items}
            design={"typography":typog,"fitting":fitting,"caption":caption_design(types,english),
                "logo":{"treatment":policy,"source_preserving_exception":category in WHITE_DEFAULTS and kind=="logo",
                    "transparent_png_default":True,"intentional_background_exception":kind=="logo",
                    "transformation":{"id":"existing-poster-white-wash","sha256":renderer_identity()["sources"]["create_poster.py"]},
                    "historical_acceptance_refs":acceptance},
                "geometry":{"logo_width":p["logo_resize"],"logo_offset":p["logo_offset"],"caption_offset":p["text_offset"],
                    "caption_width":1900,"caption_height":1000},
                "background":{"mode":"average" if p["avg_color"] else "dominant" if p["dom_color"] else "assigned",
                    "assignments_sha256":fingerprint(assignments),"proposals_allowed":False},
                "effects":{k:p[k] for k in ("gradient","border","border_color","border_width","clean")},
                "output":{"width":2000,"height":3000,"format":"JPEG","mode":"RGB","quality":100,"subsampling":0,
                    "encoding_sha256":fingerprint(renderer_identity()["encoding"])}}
            fields=["display_name","content_type"]+(["source"] if kind=="logo" else [])
            if policy=="BOTH_REQUIRED":fields.append("separate_white_source")
            role=presentation(value,j);required=["white","color"] if role in {"white","color"} else ["single"]
        variants.append({"id":key,"contributor_fields":fields,"exception_refs":exception_refs,"design":design})
        rules[key]={"design_sha256":fingerprint(design),"style_json":encoded_json(style(j)),
            "caption_types_json":encoded_json(types),"source_kind":kind,"treatment":policy,"presentation":role,
            "required_presentations":required,"companion_variants":[],"source_roots":roots,"layout_json":encoded_json(layout_shape(d))}
        for v,definition,job in items:
            item=v["identity"]
            members[item["id"]]={"record_sha256":fingerprint(v),"variant":key,"presentation":presentation(v,job),
                "companions":pairs[item["id"]],"source":item["source"],"exceptions":v["historical_exceptions"],
                "context_sha256":fingerprint({"definition":definition,"job":job})}
    for key,rule in rules.items():
        rule["companion_variants"]=sorted({members[c]["variant"] for m in members.values() if m["variant"]==key for c in m["companions"]})
    if category=="Playlist":
        contract=Contract.from_bytes((CONTRACT_ROOT/"playlist/contract-v1.json").read_bytes())
        if contract.sha256!=CONTRACT_SHA256:
            raise BulkError("category_playlist","M3 Playlist must remain exact")
        # Keep the M3 content type name and full design, including its proposal
        # permission and original aggregate fitting/background evidence.
        rules["timeline-order"]["design_sha256"]=fingerprint(contract.to_dict()["variants"][0]["design"])
        rules["timeline-order"]["caption_types_json"]=encoded_json({"timeline-order":next(iter(caption_types(rows,english).values()))})
    else:
        package_prov={"actor":"bullmoose20","role":"maintainer","source":"M6 implementation authorization; exact package awaits separate maintainer decision",
                      "evidence_sha256":fingerprint({"provenance":provenance_value,"category":category,"members":members})}
        contract=Contract.from_dict({"schema_version":1,"category":category,"kind":"overlay" if category=="Overlays" else "poster",
            "version":VERSION,"owner":"bullmoose20","provenance":package_prov,
            "naming":{"new_names":"NFC","historical_names":"exact","collision_key":"NFC+casefold","identity":"persisted"},"variants":variants})
    rules_doc=Rules.from_dict({"schema_version":1,"kind":"category-contract-rules","category":category,"version":VERSION,
        "contract_sha256":contract.sha256,"basis_sha256":M2_SHA256,"rules_json":encoded_json(rules),
        "members_json":encoded_json(members),"provenance_json":encoded_json(provenance_value)})
    return contract,rules_doc


def compile_release(records,english):
    values=[r.to_dict() for r in records]
    pairs=companions(values);groups=defaultdict(list)
    for value in values:
        groups[value["identity"]["category"]].append((value,read_canonical(value["effective_definition_json"]),read_canonical(value["job_json"])))
    if set(groups)!=set(CATEGORIES):
        raise BulkError("category_coverage","Missing or unsupported authoritative selector")
    prov=provenance();font_cache={};artifacts={};entries=[]
    registry=RegistryDocument.from_dict({"schema_version":1,"kind":"category-contract-registry","id":"defaults-category-contracts-review","version":VERSION,
        "owner":"bullmoose20","provenance":{"actor":"bullmoose20","role":"maintainer","source":"M6 review basis; no exact-package approvals included","evidence_sha256":fingerprint(prov)},"entries":[]})
    for category in CATEGORIES:
        contract,rules=compile_category(category,groups[category],pairs,english,font_cache,prov)
        contract_path="playlist/contract-v1.json" if category=="Playlist" else "categories/data/contracts/"+category.lower()+"-v1.json"
        rules_path="categories/data/rules/"+category.lower()+"-v1.json"
        if category!="Playlist":artifacts[contract_path]=contract.encoded
        artifacts[rules_path]=rules.encoded
        entries.append({"id":"defaults."+category.lower()+"."+contract.to_dict()["kind"],"category":category,"kind":contract.to_dict()["kind"],
            "version":VERSION,"contract_path":contract_path,"contract_sha256":contract.sha256,"rules_path":rules_path,"rules_sha256":rules.sha256,
            "approval":"missing_exact_maintainer_decision"})
    release=Release.from_dict({"schema_version":1,"kind":"category-contract-implementation","id":"defaults-category-contracts","version":VERSION,
        "basis_sha256":M2_SHA256,"approval_registry_sha256":registry.sha256,"entries":entries})
    artifacts["categories/data/release-v1.json"]=release.encoded
    artifacts["categories/data/review-registry-v1.json"]=registry.encoded
    return release,artifacts
