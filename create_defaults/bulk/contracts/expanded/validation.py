"""Exact M1 authority, actual Package E job replay and Playlist-only rules."""

from dataclasses import dataclass
from functools import lru_cache
import hashlib

from ...common import BulkError, canonical, confined, fingerprint, sha256
from ...config import ROOT
from ...planner import validate_manifest, renderer_identity
from ...translations import Translations
from ..registry import RegistrySnapshot
from ..playlist.validation import (PlaylistBoundary, CONTRACT_SHA256, REGISTRY_SHA256,
                                   M2_SHA256, VARIANT)
from ..adoption.models import read_canonical
from ..adoption.sources import load_pins
from .resolution import ALLOWLIST_VERSION, CONTRIBUTOR_FIELDS, plan


@lru_cache(maxsize=1)
def boundary():
    return PlaylistBoundary.load(contract_sha256=CONTRACT_SHA256,
        registry_sha256=REGISTRY_SHA256,adoption_sha256=M2_SHA256)


def approved_english():
    """Retain M2's exact LF-source bridge; never trust a caller's trace labels."""
    pins=load_pins()
    pin=next(p for p in pins["files"] if p["path"] == "create_defaults/fixtures/english/en.yml")
    path=confined(ROOT,"fixtures/english/en.yml",must_exist=True)
    raw=path.read_bytes()
    if hashlib.sha256(raw.replace(b"\r\n",b"\n")).hexdigest() != pin["sha256"]:
        raise BulkError("m5_caption_source","Authoritative English source changed; no implicit adoption")
    value=Translations({"en":path})
    value.hashes["en"]=pins["historical_english_sha256"]
    return value


def check_renderer(contract):
    current=renderer_identity()
    design=contract.to_dict()["variants"][0]["design"]
    if (current["sources"]["create_poster.py"] != design["logo"]["transformation"]["sha256"]
            or fingerprint(current["encoding"]) != design["output"]["encoding_sha256"]
            or current["canvas"] != [design["output"]["width"],design["output"]["height"]]):
        raise BulkError("m5_renderer","Actual transformation/encoding/canvas differs from the selected contract")


@dataclass(frozen=True)
class Authority:
    """Controlled operator's M1 loader arguments, never constructed from JSON.

    A public Selection/RegistrySnapshot dataclass is not accepted as authority.
    Re-enter M1's loader on every validation, including external attribution.
    """
    encoded_registry: bytes
    registry_sha256: str
    read_object: object
    trusted_decisions: object
    category: str
    kind: str
    version: str
    contract_sha256: str
    variant: str

    def select(self):
        snapshot = RegistrySnapshot.load(self.encoded_registry,expected_sha256=self.registry_sha256,
            read_object=self.read_object,trusted_decisions=self.trusted_decisions)
        return snapshot.select(self.category,self.kind,self.version,self.contract_sha256,self.variant)


def _contract(authority, fixture_only):
    reference = boundary()
    if fixture_only:
        if authority is not None:
            raise BulkError("m5_authority_mode", "Fixture and operational authority cannot be mixed")
        return reference, reference.contract
    if not isinstance(authority,Authority):
        raise BulkError("m5_unapproved_contract", "Operational checks require an exact externally authorized M1 registry")
    contract = authority.select()
    if (contract.sha256 != CONTRACT_SHA256 or authority.category != "Playlist" or authority.kind != "poster"
            or authority.variant != VARIANT):
        raise BulkError("m5_unsupported_contract", "Only the M3 Playlist contract is implemented; M6 categories remain blocked")
    return reference,contract


def validate_existing(record, resolution, *, authority=None, fixture_only=False, source_root=ROOT):
    """Read-only adoption check, including raw intent and exact physical inputs.

    Fixture compatibility is explicitly non-operational. Historical exceptions
    are checked by M2/M3 exact-use records, never applied to a renamed item.
    """
    reference, contract = _contract(authority,fixture_only)
    check_renderer(contract)
    approved_english()
    value = record.to_dict()
    identity = value["identity"]["id"]
    resolution.verify_current([identity])
    if value["identity"]["category"] != "Playlist":
        raise BulkError("m5_category", "Do not switch categories to inherit Playlist approval")
    definition = resolution.definition(identity)
    job = read_canonical(value["job_json"])
    result = reference.validate_existing(identity,definition,job)
    if reference.record(identity).sha256 != record.sha256:
        raise BulkError("m5_historical_context", "Historical exception/evidence/identity mapping differs")
    for item in job["inputs"]:
        if sha256(confined(source_root,item["path"],must_exist=True)) != item["sha256"]:
            raise BulkError("m5_stale_source", "Actual source/font/background bytes changed: "+item["path"])
    context = {"identity":value["identity"],"definition":definition,"job":job,
        "contract_sha256":contract.sha256,"variant":VARIANT,"exceptions":value["historical_exceptions"]}
    return result | {"kind":"m5-effective-validation","allowlist_version":ALLOWLIST_VERSION,
        "context_sha256":fingerprint(context),"definition_sha256":fingerprint(definition),"job_sha256":fingerprint(job),
        "contract_sha256":contract.sha256,"fixture_only":fixture_only,"contract_authorized":not fixture_only,
        "registry_sha256":None if fixture_only else authority.registry_sha256,
        "operational_addition_eligible":False,"publication_authorized":False,"merge_authorized":False}


def validate_candidate(resolution, manifest, identity, translations, *, authority=None, fixture_only=False,
                       config=None, content=None, assigned_identity=None):
    """Replay the actual planner and compare the FINAL serialized worker job.

    Arbitrary manifests cannot grant approval merely by recomputing their seal.
    All jobs in the selection are checked, and stale/post-validation mutations
    require a new validation. No production worker consumes this sidecar yet.
    """
    reference,contract = _contract(authority,fixture_only)
    check_renderer(contract)
    english=approved_english()
    if (type(translations) is not Translations or canonical(translations.sources) != canonical(english.sources)
            or translations.hashes != english.hashes or translations.failures):
        raise BulkError("m5_caption_source","Caller translation data/trace cannot substitute the pinned English input")
    validate_manifest(manifest)
    selection = manifest["selection"]
    replay = plan(resolution,translations,config=config,categories=selection["categories"],
        posters=selection["posters"],languages=selection["languages"])
    # Includes renderer, raw/effective parameters, translation, namespace,
    # dependencies, fitting evidence and complete output membership.
    for field in ("renderer","jobs","selection","not_applicable"):
        if canonical(replay[field]) != canonical(manifest[field]):
            raise BulkError("m5_job_substitution", "Final manifest differs from actual Package E resolution: "+field)
    known = {r.to_dict()["identity"]["id"] for r in reference.records}
    for other in manifest["jobs"]:
        other_definition = resolution.definition(other["poster_id"],other["language"])
        if other_definition["category"] != "Playlist" or other["kind"] != "poster" or other["language"] != "en":
            raise BulkError("m5_unsupported_contract", "Every job in this validation selection needs an implemented exact contract")
        if other["poster_id"] != identity:
            if other["poster_id"] not in known:
                raise BulkError("m5_membership", "Another unvalidated new item cannot hide in the same manifest")
            adopted = reference.record(other["poster_id"]).to_dict()
            reference.validate_existing(other["poster_id"],other_definition,read_canonical(adopted["job_json"]))
    design = contract.to_dict()["variants"][0]["design"]
    for current in manifest["jobs"]:
        font = [a for a in current["inputs"] if a["role"] == "font"]
        if len(font) != 1 or {k:font[0][k] for k in ("path","sha256")} != design["typography"]["asset"]:
            raise BulkError("m5_font", "Actual font identity differs from the exact contract")
        if (current["translation"]["mode"] != "translation" or len(current["translation"]["trace"]) != 1
                or current["translation"]["trace"][0]["source_sha256"] != design["caption"]["registry_sha256"]
                or current["parameters"]["text"] != "TIMELINE ORDER"):
            raise BulkError("m5_caption", "Caption/authoritative resource context differs from the exact contract")
    jobs = [j for j in manifest["jobs"] if j["poster_id"] == identity]
    if len(jobs) != 1 or jobs[0]["language"] != "en" or jobs[0]["kind"] != "poster":
        raise BulkError("m5_membership", "Playlist v1 requires one exact English poster output per item")
    definition = resolution.definition(identity)
    if definition["category"] != "Playlist" or definition["generator"] is not None:
        raise BulkError("m5_category", "Unsupported category/variant or generator pathway")
    if identity in {r.to_dict()["identity"]["id"] for r in reference.records}:
        # New renderer/platform provenance does not rewrite old receipts. Exact
        # design and old job remain separately verified against adopted facts.
        old = reference.record(identity).to_dict()
        reference.validate_existing(identity,definition,read_canonical(old["job_json"]))
    else:
        if content is None or assigned_identity is None:
            raise BulkError("m5_content", "New content needs controlled identity assignment and the closed M3 content interface")
        if assigned_identity.to_dict()["id"] != identity:
            raise BulkError("m5_identity", "A renamed item cannot inherit a different identity's approval")
        reference.validate_proposed_definition(assigned_identity,content,definition,
            source_root=config.asset_dir if config else ROOT)
    # No nested content dictionary, YAML override, or arbitrary source style is
    # merged into the category design. M3 additionally enforces the exact set.
    if content is not None:
        if set(content)-set(CONTRIBUTOR_FIELDS):
            raise BulkError("m5_content", "Protected/unknown contributor field")
        contract.validate_content(VARIANT,content)
    job = jobs[0]
    return {"kind":"m5-effective-validation","identity":identity,"allowlist_version":ALLOWLIST_VERSION,
        "context_sha256":fingerprint({"identity":identity,"definition":definition,"job":job,
            "contract":contract.sha256,"variant":VARIANT}),"definition_sha256":fingerprint(definition),
        "job_sha256":fingerprint(job),"manifest_sha256":manifest["sha256"],"contract_sha256":contract.sha256,
        "registry_sha256":None if fixture_only else authority.registry_sha256,
        "fixture_only":fixture_only,"contract_authorized":not fixture_only,"effective_rules_valid":True,
        "complete_poster_design_approval":False,"operational_addition_eligible":False,
        "blocked":["M4 Playlist evidence is logo-only; complete composition approval is not available",
                   "Production worker/publication gates are not integrated or activated"],
        "publication_authorized":False,"merge_authorized":False}


def require_current(report, *, definition, job, manifest_sha256=None):
    """Read-only consumer guard; an attestation is integrity, not authorization."""
    if (report.get("kind") != "m5-effective-validation" or report.get("definition_sha256") != fingerprint(definition)
            or report.get("job_sha256") != fingerprint(job)
            or ("manifest_sha256" in report and report["manifest_sha256"] != manifest_sha256)):
        raise BulkError("m5_stale_attestation", "Final job/definition/membership changed after validation")
    return {"current":True,"publication_authorized":False,"merge_authorized":False}
