"""Explicit capability inventory, not a generic category/operation fallback."""

import inspect
import hashlib
import json

from ..common import fingerprint
from ..generators import GENERATORS
from ..overlays import CATALOG, TRANSFORM
from .basis import historical_basis, GENERATORS as EXPECTED_GENERATORS
from .identity_models import HEADER, fail
from ..contracts.adoption.sources import load_pins


def matrix():
    # A self-resealed catalog is not a newly approved category contract.
    pins=load_pins()
    selected={r['path']:r for r in pins['files']}
    for name in ('create_defaults/bulk/catalog/overlays-v1.json','create_defaults/bulk/generators.py'):
        row=selected[name];raw=(CATALOG.parents[3]/name).read_bytes()
        if row['text_lf']:raw=raw.replace(b'\r\n',b'\n')
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:fail('adapter_source_pin')
    actual = {(name,version):fingerprint(inspect.getsource(fn)) for (name,version),fn in GENERATORS.items()}
    if set(actual) != {(name,1) for name in EXPECTED_GENERATORS}:fail("generator_registry_changed")
    basis = historical_basis();categories=[];variants=[]
    for package in basis.implementation.packages:
        c = package.contract.to_dict();rules,_ = package.data()
        for variant in c["variants"]:
            rule=rules[variant["id"]]
            variants.append(dict(category=c["category"],variant=variant["id"],contract_sha256=package.contract.sha256,
                presentation=rule["presentation"],source_kind=rule["source_kind"],treatment=rule["treatment"],
                required_presentations=rule["required_presentations"],
                adapter="overlay-metadata" if c["kind"]=="overlay" else "playlist-m3" if c["category"]=="Playlist" else "m6-effective-poster",
                job_planning="blocked_preseal_identity_hook" if c["kind"]=="overlay" else "conditional_closed_contract",
                limitations=["English only", "No new caption types, styles or exceptions", "All exact contract approvals remain missing"]+
                    (["Existing owned parent artifacts required"] if rule["source_kind"]=="composition" else [])))
        categories.append(dict(category=c["category"],kind=c["kind"],variants=sorted(rules),
            input_shape="paired registry source mappings" if c["kind"]=="overlay" else "actual strict YAML + profiles + persisted member IDs",
            enforcement=False))
    catalog=json.loads(CATALOG.read_text(encoding="utf8"))
    if catalog["sha256"]!=fingerprint({k:v for k,v in catalog.items() if k!="sha256"}) or catalog["transform"]!=TRANSFORM:fail("overlay_catalog")
    overlays=[]
    for group in catalog["groups"]:
        if set(group["sizes"])!={"standard","bigger"}:fail("overlay_catalog_companions")
        overlays.append(dict(branch=group["id"],variant=group["id"].replace("/","."),trim=group["trim"],
            sizes={size:row["box"] for size,row in group["sizes"].items()},source_inputs=len(group["inputs"]),
            relationship_impact="supported",new_job_planning="blocked_preseal_identity_hook",
            transformation="SOURCE_PRESERVING",input_shape="exact registered branch + registry standard/bigger source members"))
    if len(categories)!=22 or len(variants)!=278 or len(overlays)!=18:fail("coverage_membership")
    return dict(**HEADER,kind="prospective-coverage",categories=sorted(categories,key=lambda c:c["category"]),
        variants=sorted(variants,key=lambda v:(v["category"],v["variant"])),overlays=sorted(overlays,key=lambda g:g["branch"]),
        generators=[dict(name=name,version=version,code_sha256=checksum,identity="semantic variable before job sealing",
            job_planning="conditional_closed_contract_and_owned_parents") for (name,version),checksum in sorted(actual.items())],
        unsupported=["new overlay jobs", "unknown generator/version/category/variant", "new language contract", "new caption type",
            "unapproved individual treatment or transparency exception", "unknown or absent owned generated parents"])


def require_variant(category, variant):
    basis=historical_basis()
    return basis.package(category),basis.rule(category,variant)
