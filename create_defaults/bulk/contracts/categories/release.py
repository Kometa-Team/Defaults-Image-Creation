"""Pinned implementation packages; an implementation index grants no authority."""

from dataclasses import dataclass
from pathlib import Path

from ...common import BulkError,confined,fingerprint
from ..adoption.models import read_canonical
from ..models import Contract,RegistryDocument,read_json_bytes
from ..registry import RegistrySnapshot,require_hash
from ..playlist.validation import M2_SHA256,CONTRACT_SHA256
from ..expanded.validation import Authority
from .models import Release,Rules


ROOT=Path(__file__).parents[1]
# Replaced only by an explicitly reviewed implementation change, never latest.
RELEASE_SHA256="926de31d1df4ee90e911c4e91df81ee3ca914f5179df784ff3d41e9b716ada2a"


@dataclass(frozen=True)
class Package:
    contract: Contract
    rules: Rules

    def data(self):
        value=self.rules.to_dict()
        return read_canonical(value["rules_json"]),read_canonical(value["members_json"])


@dataclass(frozen=True)
class Implementation:
    release: Release
    packages: tuple[Package,...]

    @classmethod
    def load(cls,*,expected_sha256,root=ROOT):
        release=Release.from_bytes(read_json_bytes(confined(root,"categories/data/release-v1.json",must_exist=True)))
        if release.sha256!=require_hash(expected_sha256) or release.to_dict()["basis_sha256"]!=M2_SHA256:
            raise BulkError("category_release_pin","Implementation inventory differs from its selected pin")
        registry=RegistryDocument.from_bytes(read_json_bytes(confined(root,"categories/data/review-registry-v1.json",must_exist=True)))
        if registry.sha256!=release.to_dict()["approval_registry_sha256"] or registry.to_dict()["entries"]:
            raise BulkError("category_review_registry","Review basis must not manufacture contract approvals")
        packages=[]
        for entry in release.to_dict()["entries"]:
            contract=Contract.from_bytes(read_json_bytes(confined(root,entry["contract_path"],must_exist=True)))
            rules=Rules.from_bytes(read_json_bytes(confined(root,entry["rules_path"],must_exist=True)))
            c,r=contract.to_dict(),rules.to_dict()
            if (contract.sha256,rules.sha256)!=(entry["contract_sha256"],entry["rules_sha256"]):
                raise BulkError("category_package_pin","Changed contract or membership rules")
            if (c["category"],c["kind"],c["version"])!=(entry["category"],entry["kind"],entry["version"]) or entry["id"]!="defaults."+c["category"].lower()+"."+c["kind"]:
                raise BulkError("category_package_identity","Category, selector, kind and stable package ID differ")
            if (r["category"],r["version"],r["contract_sha256"],r["basis_sha256"])!=(c["category"],c["version"],contract.sha256,M2_SHA256):
                raise BulkError("category_rule_pin","Sidecar is not bound to this exact package and historical baseline")
            design={v["id"]:fingerprint(v["design"]) for v in c["variants"]}
            observed=read_canonical(r["rules_json"])
            if design!={k:v["design_sha256"] for k,v in observed.items()}:
                raise BulkError("category_design_pin","Closed rule variants differ from M1 contract designs")
            if c["category"]=="Playlist" and contract.sha256!=CONTRACT_SHA256:
                raise BulkError("category_playlist","The original M3 contract must remain exact")
            packages.append(Package(contract,rules))
        return cls(release,tuple(packages))

    def select(self,category):
        for package in self.packages:
            if package.contract.to_dict()["category"]==category:
                return package
        raise BulkError("category_unknown_selector","Unknown or unsupported category selector")


def authorize(package,variant,authority):
    """Re-enter unchanged M1 external attribution; JSON flags are never trust."""
    if type(package) is not Package or type(package.contract) is not Contract or type(package.rules) is not Rules:
        raise BulkError("category_package_type","Immutable M1/M6 documents are required")
    # A public Package dataclass is not authority for its sidecar. Pin it back
    # to the actual bundled release before accepting an external M1 decision.
    release=Release.from_bytes(read_json_bytes(confined(ROOT,"categories/data/release-v1.json",must_exist=True)))
    if release.sha256!=RELEASE_SHA256 or not any(e["contract_sha256"]==package.contract.sha256 and e["rules_sha256"]==package.rules.sha256 for e in release.to_dict()["entries"]):
        raise BulkError("category_package_pin","Selected sidecar/package is not the exact implemented release")
    if not isinstance(authority,Authority):
        raise BulkError("category_unapproved","Exact externally attributed M1 contract approval is missing")
    selected=authority.select()
    value=package.contract.to_dict()
    if (selected.sha256,authority.category,authority.kind,authority.version,authority.variant)!=(
            package.contract.sha256,value["category"],value["kind"],value["version"],variant):
        raise BulkError("category_authority_scope","Authority selects a different package or variant")
    return selected
