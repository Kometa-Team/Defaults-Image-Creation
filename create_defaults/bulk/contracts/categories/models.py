"""Additive closed M1 documents; implementation inventory is not approval."""

from ...common import BulkError,canonical,relative_path
from ...config import CATEGORIES
from ..adoption.models import read_canonical
from ..models import Document
from ..registry import require_hash
from ...planner import _composer_validator
from ...definitions import schema_validator
from functools import lru_cache
from .policy import treatment


def closed(value,fields):
    if type(value) is not dict or set(value)!=set(fields.split()):
        raise BulkError("category_shape","Unknown or missing category rule fields")


@lru_cache(maxsize=1)
def caption_validator():
    parent=schema_validator("definition-v1.json");s=parent.schema
    return parent.evolve(schema={"$id":s["$id"],"$defs":s["$defs"],"$ref":"#/$defs/caption"})


class Rules(Document):
    SCHEMA="category-rules"
    KIND="category-contract-rules"

    def _check(self,value):
        rules=read_canonical(value["rules_json"])
        members=read_canonical(value["members_json"])
        provenance=read_canonical(value["provenance_json"])
        closed(provenance,"baseline_source baseline_registry architecture_sha256 matrix_sha256 exceptions_sha256 compiler_version")
        for key in ("baseline_registry","architecture_sha256","matrix_sha256","exceptions_sha256"):
            require_hash(provenance[key])
        import re
        if provenance["compiler_version"]!=1 or type(provenance["compiler_version"]) is not int or not re.fullmatch("[0-9a-f]{40}",provenance["baseline_source"]):
            raise BulkError("category_provenance","Unknown compiler version or source commit")
        if type(rules) is not dict or not rules or type(members) is not dict or not members:
            raise BulkError("category_membership","Empty rules or historical membership")
        for key,rule in rules.items():
            closed(rule,"design_sha256 style_json caption_types_json source_kind treatment presentation required_presentations companion_variants source_roots layout_json")
            require_hash(rule["design_sha256"])
            for field in ("style_json","caption_types_json","layout_json"):
                if type(read_canonical(rule[field])) is not dict:
                    raise BulkError("category_shape","Embedded rule fields must be closed objects")
            if rule["source_kind"] not in {"logo","placeholder","composition","overlay_source"} or rule["treatment"] not in {"WHITE_ONLY","SOURCE_PRESERVING","BOTH_REQUIRED","NOT_APPLICABLE","SPECIAL"}:
                raise BulkError("category_policy","Unknown source class or treatment")
            if rule["treatment"]!=treatment(value["category"],rule["source_kind"]):
                raise BulkError("category_policy","Rule conflicts with the confirmed category-specific policy")
            style=read_canonical(rule["style_json"])
            if value["category"]=="Overlays":
                closed(style,"trim colorspace strip_metadata format resampling")
                if type(style["trim"]) is not bool or {k:v for k,v in style.items() if k!="trim"}!={"colorspace":"sRGB","strip_metadata":True,"format":"PNG","resampling":"Pillow-LANCZOS"}:
                    raise BulkError("category_overlay_policy","Unknown overlay processing rules")
            else:
                if set(style)&{"logo","base_color","out_name","text","input"}:
                    raise BulkError("category_style_schema","Content cannot replace protected style fields")
                sample=style | {"logo":"transparent.png","base_color":"#000000","out_name":"M6","text":""}
                if not _composer_validator().is_valid(sample):
                    raise BulkError("category_style_schema","Unknown or malformed protected composer field")
            for item in read_canonical(rule["caption_types_json"]).values():
                closed(item,"definition_json text translation_json")
                if type(item["text"]) is not str:
                    raise BulkError("category_caption","Caption must be exact text")
                caption=read_canonical(item["definition_json"])
                if not caption_validator().is_valid(caption):
                    raise BulkError("category_caption","Caption definition must be an object")
                trace=read_canonical(item["translation_json"])
                closed(trace,"mode trace fingerprint")
                require_hash(trace["fingerprint"])
            if rule["presentation"] not in {"single","white","color","overlay"}:
                raise BulkError("category_presentation","Unknown closed presentation role")
            expected={"standard","bigger"} if value["category"]=="Overlays" else {"white","color"} if rule["presentation"] in {"white","color"} else {"single"}
            if type(rule["required_presentations"]) is not list or set(rule["required_presentations"])!=expected or len(rule["required_presentations"])!=len(expected):
                raise BulkError("category_membership","Incomplete required presentation set")
            if type(rule["companion_variants"]) is not list or any(v not in rules for v in rule["companion_variants"]):
                raise BulkError("category_membership","Unknown required counterpart contract variant")
            if type(rule["source_roots"]) is not list or any(type(p) is not str or not p for p in rule["source_roots"]):
                raise BulkError("category_sources","Invalid source branch roots")
            for root in rule["source_roots"]:relative_path(root)
        for identity,member in members.items():
            closed(member,"record_sha256 variant presentation companions source exceptions context_sha256")
            require_hash(member["record_sha256"])
            require_hash(member["context_sha256"])
            closed(member["source"],"path sha256")
            require_hash(member["source"]["sha256"])
            if member["variant"] not in rules or type(member["companions"]) is not list:
                raise BulkError("category_membership","Unknown member variant")
            rule=rules[member["variant"]]
            roles={"standard","bigger"} if value["category"]=="Overlays" else {rule["presentation"]}
            if member["presentation"] not in roles:
                raise BulkError("category_presentation","Historical member has an unknown or swapped presentation")
            expected_count=1 if value["category"]=="Overlays" or rule["presentation"] in {"white","color"} else 0
            if len(member["companions"])!=expected_count or len(set(member["companions"]))!=expected_count:
                raise BulkError("category_membership","Required historical companion count differs")
            relative_path(member["source"]["path"])
            for partner in member["companions"]:
                if partner not in members or identity not in members[partner]["companions"] or partner==identity:
                    raise BulkError("category_membership","Missing/asymmetric required companion")
                expected_role={"standard":"bigger","bigger":"standard","white":"color","color":"white"}[member["presentation"]]
                if members[partner]["presentation"]!=expected_role or members[partner]["variant"] not in rule["companion_variants"]:
                    raise BulkError("category_membership","Swapped or unsupported required companion")
            if type(member["exceptions"]) is not list:
                raise BulkError("category_exception","Invalid historical exception list")
            for exception in member["exceptions"]:
                closed(exception,"code evidence_sha256")
                require_hash(exception["evidence_sha256"])


class Release(Document):
    SCHEMA="category-release"
    KIND="category-contract-implementation"

    def _check(self,value):
        entries=value["entries"]
        if len(entries)!=len(CATEGORIES) or {e["category"] for e in entries}!=set(CATEGORIES):
            raise BulkError("category_coverage","Every authoritative selector must occur exactly once")
        for entry in entries:
            if (entry["kind"]=="overlay") != (entry["category"]=="Overlays"):
                raise BulkError("category_kind","Poster and overlay membership differ")
