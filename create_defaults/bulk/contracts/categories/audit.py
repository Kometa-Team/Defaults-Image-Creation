"""Complete read-only M2/M5 reconciliation against the M6 implementation."""

from collections import Counter,defaultdict
from time import perf_counter

from ...common import BulkError,fingerprint
from ...definitions import Definition
from ...planner import renderer_identity
from ...overlays import identity as overlay_identity
from ..adoption.models import read_canonical,encoded_json,HistoricalOutput
from ..expanded.validation import boundary,check_renderer
from .compiler import caption_types,layout_shape,font_facts
from .policy import companions,treatment,source_kind
from .validation import Assignment,check_job,check_membership,check_names,same


BASELINE_GRAPH_SHA256="6e23ff33bd3cba5b1bd69914b974ed9e2118b364e8f04b3a841376c1461f4197"


def assignment_for(package,value):
    rules,members=package.data()
    return _assignment(rules,members,value)


def _assignment(rules,members,value,*,_decoded=None,_caption_index=None):
    identity=value["identity"]["id"];member=members[identity];rule=rules[member["variant"]]
    definition,job=_decoded if _decoded is not None else (read_canonical(value["effective_definition_json"]),read_canonical(value["job_json"]))
    caption=None
    if job["kind"]=="poster":
        if _caption_index is not None:
            caption=_caption_index[member["variant"]].get(fingerprint(definition["caption"]))
        else:
            candidates=read_canonical(rule["caption_types_json"])
            caption=next((k for k,v in candidates.items() if read_canonical(v["definition_json"])==definition["caption"]),None)
        if caption is None:raise BulkError("category_caption_type","Historical caption is not covered")
    group=min([identity,*member["companions"]])
    return Assignment(identity,job["id"],member["variant"],job["local_relative"],job["remote_relative"],
        encoded_json(member["source"]),
        job["parameters"].get("base_color"),caption,member["presentation"],group)


def verify_design(contract,variant,definition,job,rule):
    """Independently check explicit M1 design fields against actual jobs.

    Full raw/effective definitions and measurements are additionally bound by
    each M2 member. This does not infer visual equivalence from new pixels.
    """
    c=contract.to_dict();design=next(v["design"] for v in c["variants"] if v["id"]==variant);p=job["parameters"]
    same(rule["source_kind"],source_kind({"identity":{"category":c["category"],"source":{"path":p.get("logo",p.get("input"))}},
        "source_kind":"generated_parent" if rule["source_kind"]=="composition" else "source_asset"}),"source classification")
    same(rule["treatment"],treatment(c["category"],rule["source_kind"]),"confirmed category policy")
    if job["kind"]=="overlay":
        same(design["treatment"],"SOURCE_PRESERVING","overlay independence")
        same(design["trim"],p["trim"],"overlay trim")
        same(design["transformation"]["sha256"],overlay_identity()["sources"]["bulk/overlays.py"],"actual overlay transformation")
        return
    check_renderer(contract)
    for field in ("size","color"):
        same(design["typography"][field],p["font_size" if field=="size" else "font_color"],"typography "+field)
    same(design["logo"]["treatment"],rule["treatment"],"logo category treatment")
    for field,parameter in (("logo_width","logo_resize"),("logo_offset","logo_offset"),("caption_offset","text_offset")):
        same(design["geometry"][field],p[parameter],"geometry "+field)
    for field in ("gradient","border","border_color","border_width","clean"):
        same(design["effects"][field],p[field],"effect "+field)
    same(design["caption"]["requirement"],"prohibited" if definition["caption"]["mode"]=="none" else "required","caption presence")
    same(design["caption"]["case"],definition["caption"]["case"],"caption capitalization")
    measurement=definition["layout"]["measurement"]
    if measurement is None:
        same(design["fitting"],None,"fixed fitting")
    else:
        same({k:design["fitting"][k] for k in ("mode","width","height","minimum_size","maximum_size")},
            {"mode":definition["layout"]["kind"],"width":measurement["box"][0],"height":measurement["box"][1],
             "minimum_size":measurement["minimum"],"maximum_size":measurement["maximum"]},"fitting bounds")


def audit(implementation,registry,records,resolution,graph,*,categories=()):
    start=perf_counter()
    if registry.sha256!=implementation.release.to_dict()["basis_sha256"]:
        raise BulkError("category_basis","Select the complete accepted M2 registry")
    registry.verify_schema_pins()
    expected={m["id"]:m["sha256"] for m in registry.to_dict()["members"]}
    records=tuple(records)
    # Exact immutable M2 object hashes preserve all original relationship and
    # receipt proofs. Do not repeatedly deserialize the entire library merely
    # to validate nine selected items from the same verified snapshot.
    if any(type(r) is not HistoricalOutput for r in records):
        raise BulkError("category_record_type","Expected immutable validated M2 documents")
    by_hash={r.sha256:r for r in records}
    if len(by_hash)!=len(records) or set(by_hash)!=set(expected.values()):
        raise BulkError("category_membership","Complete exact M2 object membership is required")
    graph_index=graph.index()
    same(graph.sha256,BASELINE_GRAPH_SHA256,"exact accepted M5 historical graph")
    same(sorted(graph_index.outputs),sorted(expected),"complete M5 dependency membership")
    resolution.verify_current()
    expanded=resolution.data()["expanded"]
    selected=set(categories) if categories else {p.contract.to_dict()["category"] for p in implementation.packages}
    for category in selected:implementation.select(category)
    report={"kind":"m6-historical-compatibility","release_sha256":implementation.release.sha256,
        "M2_registry_sha256":registry.sha256,"M5_graph_sha256":graph.sha256,"categories":[],"incompatibilities":[],
        "unresolved_design_interpretations":[],"contract_approval":"missing_exact_maintainer_decision",
        "contract_activation":False,"artifact_approval_granted":False,"publication_authorized":False,
        "production_enforcement":False,"artwork_regenerated":0,"remote_writes":0}
    all_jobs=[];all_results=[]
    for package in implementation.packages:
        c=package.contract.to_dict();category=c["category"]
        if category not in selected:continue
        began=perf_counter();rules,members=package.data()
        caption_types_by_variant={k:read_canonical(r["caption_types_json"]) for k,r in rules.items()}
        caption_index={k:{fingerprint(read_canonical(v["definition_json"])):t for t,v in types.items()} for k,types in caption_types_by_variant.items()}
        prepared=(c,rules,members,caption_types_by_variant)
        actual={i:by_hash[expected[i]].to_dict() for i in members if i in expected}
        same(sorted(members),sorted(actual),"complete category membership "+category)
        for identity,value in actual.items():
            same((identity,category),(value["identity"]["id"],value["identity"]["category"]),"exact category owner")
        pairs=companions(list(actual.values()))
        counts=Counter();exceptions=Counter();variants=Counter();sources=set();definitions=set();receipts=Counter()
        first={};assignments=defaultdict(dict);fits=defaultdict(dict);results=[]
        for identity,value in actual.items():
            member=members[identity];variant=member["variant"];rule=rules[variant]
            same(member["record_sha256"],expected[identity],"complete historical record/receipt identity")
            same(member["exceptions"],value["historical_exceptions"],"exact accepted historical exceptions")
            same(member["companions"],pairs[identity],"complete required historical companions")
            same(member["source"],value["identity"]["source"],"historical source hash and case")
            definition=read_canonical(value["effective_definition_json"]);job=read_canonical(value["job_json"])
            if job["kind"]=="poster":
                current=Definition.create(expanded[identity]).for_language(job["language"]).data
                same(definition,current,"current final expanded definition")
                if category=="Playlist":
                    boundary().validate_existing(identity,current,job)
                assignments[variant][identity]={"color":job["parameters"]["base_color"],"provenance":job["color_assignment"]}
                fits[variant][identity]=job["layout_evidence"]
            result=check_job(package,definition,job,_assignment(rules,members,value,_decoded=(definition,job),_caption_index=caption_index),historical_member=member,_prepared=prepared)
            results.append(result);all_jobs.append(job)
            if variant not in first:
                verify_design(package.contract,variant,definition,job,rule)
                first[variant]=True
            counts[result["compatibility"]]+=1;variants[variant]+=1
            exceptions.update(e["code"] for e in value["historical_exceptions"])
            sources.add(value["identity"]["source"]["path"])
            definitions.add(definition.get("source",{}).get("path","overlays-v1.json"))
            for key in ("owned_receipt_sha256","original_receipt_sha256","worker_spec_sha256","response_receipt_sha256"):
                receipts[key]+=value["evidence"][key] is not None
        check_membership(results)
        # Independent aggregate checks preserve per-output colour assignments
        # and captured fitting; Playlist retains its distinct original M3 pins.
        if category not in {"Playlist","Overlays"}:
            for variant in c["variants"]:
                key=variant["id"];d=variant["design"]
                same(d["background"]["assignments_sha256"],fingerprint(assignments[key]),"background assignment aggregate")
                if d["fitting"] is not None:
                    same(d["fitting"]["measurement_sha256"],fingerprint(fits[key]),"captured measurement aggregate")
        report["categories"].append({"category":category,"selector":category,"contract_id":"defaults."+category.lower()+"."+c["kind"],
            "kind":c["kind"],"version":c["version"],"contract_sha256":package.contract.sha256,"rules_sha256":package.rules.sha256,
            "outputs":len(actual),"public_outputs":sum(v["identity"]["public_path"] is not None for v in actual.values()),
            "compatibility":dict(counts),"variants":dict(sorted(variants.items())),"historical_exceptions":dict(sorted(exceptions.items())),
            "source_paths":sorted(sources),"definition_references":sorted(definitions),"receipt_accounting":dict(receipts),
            "required_companion_edges":sum(len(m["companions"]) for m in members.values()),"seconds":perf_counter()-began})
        all_results.extend(results)
    check_names(all_jobs)
    if not categories:
        same(sorted(r["identity"] for r in all_results),sorted(expected),"complete category-to-inventory reconciliation")
    report.update({"outputs":len(all_results),"posters":sum(j["kind"]=="poster" for j in all_jobs),
        "overlays":sum(j["kind"]=="overlay" for j in all_jobs),"public_outputs":sum(j["remote_relative"] is not None for j in all_jobs),
        "compatibility":dict(Counter(r["compatibility"] for r in all_results)),"seconds":perf_counter()-start})
    return report
