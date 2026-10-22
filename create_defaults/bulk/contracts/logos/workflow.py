"""Isolated D09 review engine. M1 records, external attribution, no publication."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import platform
import re
import unicodedata

from PIL import __version__ as pillow_version, features

from ...common import BulkError, canonical, confined, fingerprint, path_key, sha256
from ... import overlays
from ..adoption.models import encoded_json, read_canonical
from ..models import Contract, ExceptionDecision, ExceptionRequest, Identity, PreviewManifest, SubmitterConfirmation
from ..registry import RegistrySnapshot, TrustedDecision, package_reference, require_hash
from .assets import Asset, MAX_BYTES, encode_png, inspect_png
from .comparison import compare
from .evidence import Evidence, closed
from .wash import implementation, white_wash


DEFAULTS = {**{c: "WHITE_ONLY" for c in ("Playlist", "Franchise", "Genre", "Seasonal", "Universe")},
            **{c: "BOTH_REQUIRED" for c in ("Chart", "Country", "Network", "Streaming")}, "Studio": "SOURCE_PRESERVING"}


@dataclass(frozen=True)
class Selection:
    contract: Contract
    registry_sha256: str
    variant: str
    fixture_only: bool

    @classmethod
    def approved(cls, encoded, *, registry_sha256, read_object, trusted_decisions,
                 category, kind, version, contract_sha256, variant):
        snapshot = RegistrySnapshot.load(encoded, expected_sha256=registry_sha256, read_object=read_object, trusted_decisions=trusted_decisions)
        contract = snapshot.select(category, kind, version, contract_sha256, variant)
        result = cls(contract, registry_sha256, variant, False)
        result.design()
        return result

    @classmethod
    def fixture(cls, contract, variant):
        """Controlled Python test/evidence scope; never offered via submitter JSON.

        The explicit fixture flag survives every record and can never yield
        operational contract compatibility or publication authority.
        """
        result = cls(Contract.from_bytes(contract.encoded), fingerprint({"isolated_m4_fixture": contract.sha256}), variant, True)
        result.design()
        return result

    def design(self):
        value = self.contract.to_dict()
        found = [v for v in value["variants"] if v["id"] == self.variant]
        if len(found) != 1:
            raise BulkError("logo_variant", "Select one closed contract variant")
        design = found[0]["design"]
        if value["kind"] == "poster":
            treatment = design["logo"]["treatment"]
            if value["category"] in DEFAULTS and treatment != DEFAULTS[value["category"]]:
                raise BulkError("logo_category_policy", "Selected design conflicts with confirmed D09 default")
            if treatment not in {"WHITE_ONLY", "SOURCE_PRESERVING", "BOTH_REQUIRED"}:
                raise BulkError("logo_scope", "Text-only/special designs require their own M6 contract; no logo inferred")
        elif design["treatment"] != "SOURCE_PRESERVING":
            raise BulkError("logo_overlay_wash", "Overlay contracts cannot inherit poster wash")
        return design


@dataclass(frozen=True)
class SubmitterAttribution:
    """Controlled operator's actual confirmation attribution, outside JSON.

    Like M1 TrustedDecision, this is not a new authenticator or public login.
    Deployments need an authorized operator adapter; evidence hashes alone do
    not authenticate people. A stored record never populates the trust map.
    """
    actor: str
    evidence_sha256: str

    def __post_init__(self):
        require_hash(self.evidence_sha256)
        if type(self.actor) is not str or not self.actor.strip():
            raise BulkError("logo_submitter", "Submitter attribution needs a real selected actor")


def read_asset(root, reference):
    closed(reference, "path sha256")
    require_hash(reference["sha256"])
    path = confined(Path(root), reference["path"], must_exist=True)
    with path.open("rb") as stream: raw = stream.read(MAX_BYTES+1)
    asset = inspect_png(raw)
    if asset.sha256 != reference["sha256"]:
        raise BulkError("logo_source_changed", "Source hash or exact path changed")
    return asset


def runtime():
    return {"python": platform.python_version(), "Pillow": pillow_version,
            "png_zlib":features.version("zlib"),"icc_littlecms":features.version("littlecms2"),
            "workflow_source_sha256": fingerprint(Path(__file__).read_text(encoding="utf-8").replace("\r\n", "\n")),
            "analysis_source_sha256": fingerprint(Path(__file__).with_name("comparison.py").read_text(encoding="utf-8").replace("\r\n", "\n")),
            "assets_source_sha256": fingerprint(Path(__file__).with_name("assets.py").read_text(encoding="utf-8").replace("\r\n", "\n")),
            "wash_adapter_source_sha256": fingerprint(Path(__file__).with_name("wash.py").read_text(encoding="utf-8").replace("\r\n", "\n")),
            "overlay_implementation": overlays.identity()["sources"]["bulk/overlays.py"]}


def transform_identity(selection):
    if selection.contract.to_dict()["kind"] == "overlay":
        return {"id":"existing-source-preserving-overlay","version":overlays.TRANSFORM["version"],
                "source_sha256":overlays.identity()["sources"]["bulk/overlays.py"],"parameters":overlays.TRANSFORM}
    return implementation()[1]


def _requirements(selection, sources, exception_types):
    design = selection.design()
    if selection.contract.to_dict()["kind"] == "overlay":
        if sources["white"] is not None or "source_preserving" in exception_types or "brand_lockup" in exception_types:
            raise BulkError("logo_overlay_scope", "Select each approved overlay source branch explicitly; do not derive poster variants")
        return [{"id": selection.variant+"."+size, "treatment": "source", "size": size,
                 "source": "master", "box": design["sizes"][size], "trim": design["trim"]}
                for size in ("standard", "bigger")]
    logo = design["logo"]
    if "source_preserving" in exception_types and (logo["treatment"] != "WHITE_ONLY" or not logo["source_preserving_exception"]):
        raise BulkError("logo_exception_scope", "Contract does not permit this presentation request")
    if "intentional_background" in exception_types and not logo["intentional_background_exception"]:
        raise BulkError("logo_exception_scope", "Contract does not permit intentional-background requests")
    if "brand_lockup" in exception_types and (logo["treatment"] != "BOTH_REQUIRED" or sources["white"] is None):
        raise BulkError("logo_lockup_scope", "Brand-lockup departure must identify a separate required white source")
    treatments = ["white", "source"] if logo["treatment"] == "BOTH_REQUIRED" else ["source"] if "source_preserving" in exception_types or logo["treatment"] == "SOURCE_PRESERVING" else ["white"]
    return [{"id": "logo."+t, "treatment": t, "size": "logo_only", "source": "white" if t == "white" and sources["white"] else "master",
             "box": {"width": 256, "height": 256}, "trim": False} for t in treatments]


def _spec_check(spec, selection):
    closed(spec, "package registry_sha256 variant fixture_only item submitter sources background exceptions reason expires_at transform runtime required_outputs preview_type rules_sha256")
    if (spec["package"] != package_reference(selection.contract) or spec["registry_sha256"] != selection.registry_sha256
            or spec["variant"] != selection.variant or spec["fixture_only"] is not selection.fixture_only
            or spec["rules_sha256"] != fingerprint(selection.design())):
        raise BulkError("logo_contract_context", "Exact contract/registry/variant selection changed")
    closed(spec["sources"], "master white")
    if type(spec["exceptions"]) is not list or len(set(spec["exceptions"])) != len(spec["exceptions"]) or set(spec["exceptions"]) - {"source_preserving", "intentional_background", "brand_lockup"}:
        raise BulkError("logo_exception_scope", "Unknown or duplicate exception types")
    if not spec["reason"].strip() or not spec["submitter"].strip():
        raise BulkError("logo_request", "Exact submitter and justification are required")
    item = Identity.from_dict(spec["item"]).to_dict()
    Identity.from_dict(item).require_new_names()
    for source in spec["sources"].values():
        if source is not None:
            closed(source,"path sha256")
            if unicodedata.normalize("NFC",source["path"]) != source["path"]:
                raise BulkError("logo_new_name","New source names must already be NFC; never normalize silently")
    if spec["sources"]["master"] is None:
        raise BulkError("logo_source","Original master is mandatory")
    if spec["background"] is not None and (type(spec["background"]) is not str or not re.fullmatch(r"#[0-9A-Fa-f]{6}",spec["background"])):
        raise BulkError("logo_background","Expected a proposed RGB background, never styling or approval fields")
    if item["category"] != spec["package"]["category"] or item["source"] != spec["sources"]["master"]:
        raise BulkError("logo_item", "Wrong stable identity/category/source association")
    expected = _requirements(selection, spec["sources"], spec["exceptions"])
    if canonical(expected) != canonical(spec["required_outputs"]):
        raise BulkError("logo_membership", "Required variants, sizes or source branch changed")
    if selection.contract.to_dict()["kind"] == "overlay":
        if spec["background"] is not None or spec["preview_type"] != "complete_overlay":
            raise BulkError("logo_overlay_context", "Overlay previews preserve their original source context")
    elif spec["preview_type"] != "logo_only":
        raise BulkError("logo_preview_completeness", "M4 does not implement full poster composition")
    if spec["expires_at"] is not None:
        from datetime import datetime, timezone
        try: expiry = datetime.fromisoformat(spec["expires_at"].replace("Z", "+00:00"))
        except (TypeError, ValueError) as error: raise BulkError("logo_expiry", "Use an explicit timezone-aware expiry") from error
        if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            raise BulkError("logo_expired", "Review context is expired")
    if spec["runtime"] != runtime() or spec["transform"] != transform_identity(selection):
        raise BulkError("logo_runtime_changed", "Preview/validation implementation changed; review is stale")


def _context(spec):
    return {"package": spec["package"], "variant": spec["variant"], "identities": [spec["item"]["id"]],
            "source": spec["sources"]["master"], "material_context_sha256": fingerprint(spec),
            "transformations": [{"id": spec["transform"]["id"], "sha256": fingerprint(spec["transform"])}]}


@dataclass(frozen=True)
class Prepared:
    bundle: Evidence
    artifacts: tuple[tuple[str, bytes], ...]


def prepare(selection, *, source_root, item, submitter, sources, background=None,
            exception_types=(), reason, request_id, request_revision=1, expires_at=None):
    """Bounded safe previews, not accepted production jobs or publication assets."""
    design = selection.design()
    sources = read_canonical(encoded_json(sources))
    closed(sources, "master white")
    assets = {key: read_asset(source_root, ref) for key, ref in sources.items() if ref is not None}
    comparison = compare(assets["master"], assets["white"]) if "white" in assets else None
    if "white" in assets and (selection.contract.to_dict()["kind"] != "poster" or design["logo"]["treatment"] != "BOTH_REQUIRED"):
        raise BulkError("logo_white_source_scope", "Separate white sources are only supported for selected paired designs")
    spec = {"package": package_reference(selection.contract), "registry_sha256": selection.registry_sha256,
            "variant": selection.variant, "fixture_only": selection.fixture_only, "item": item.to_dict(), "submitter": submitter,
            "sources": sources, "background": background, "exceptions": sorted(exception_types), "reason": reason,
            "expires_at": expires_at, "transform": transform_identity(selection), "runtime": runtime(),
            "required_outputs": _requirements(selection, sources, exception_types),
            "preview_type": "complete_overlay" if selection.contract.to_dict()["kind"] == "overlay" else "logo_only",
            "rules_sha256": fingerprint(design)}
    _spec_check(spec, selection)
    context = _context(spec)
    requested = "SOURCE_PRESERVING" if "source_preserving" in exception_types or selection.contract.to_dict()["kind"] == "overlay" else design["logo"]["treatment"]
    request = ExceptionRequest.from_dict({"schema_version": 1, "kind": "logo-exception-request", "id": request_id, "revision": request_revision,
        "provenance": {"actor": submitter, "role": "submitter", "source": "isolated-M4-request-not-authentication", "evidence_sha256": fingerprint(spec)},
        "context": context, "justification": reason, "requested_treatment": requested,
        "intentional_background": "intentional_background" in exception_types})
    receipts, blobs, members = {}, {}, []
    for asset in assets.values(): blobs[asset.sha256] = asset.encoded

    def render(member):
        source = assets[member["source"]]
        if spec["preview_type"] == "complete_overlay":
            target = BytesIO()
            overlays.render({"trim": member["trim"], "box": [member["box"]["width"], member["box"]["height"]]}, BytesIO(source.encoded), target)
            raw = target.getvalue()
        else:
            image = source.image()
            if member["treatment"] == "white" and member["source"] == "master": image, _ = white_wash(image)
            image.thumbnail((256, 256))
            raw = encode_png(image)
        artifact = inspect_png(raw)
        blobs[artifact.sha256] = raw
        receipt = Evidence.make("isolated-logo-preview-receipt", {"artifact_sha256": artifact.sha256,
            "source_sha256": source.sha256, "context_sha256": fingerprint(spec), "member_json": encoded_json(member),
            "transform_json": encoded_json(spec["transform"] if member["treatment"] == "white" else {"id": "source-preserving", "overlay": overlays.TRANSFORM if spec["preview_type"] == "complete_overlay" else None}),
            "runtime_json": encoded_json(spec["runtime"]), "bytes": len(raw), "preview_type": spec["preview_type"]})
        receipts[receipt.sha256] = receipt.to_dict()
        return {"id": member["id"], "treatment": member["treatment"], "artifact_sha256": artifact.sha256, "worker_receipt_sha256": receipt.sha256}

    for member in spec["required_outputs"]: members.append(render(member))
    # Exact labeled panels. White-default exceptions always retain both views.
    default_treatment = "white" if selection.contract.to_dict()["kind"] == "poster" and design["logo"]["treatment"] in {"WHITE_ONLY", "BOTH_REQUIRED"} else "source"
    panels = {}
    for name, treatment in (("default", default_treatment), ("requested", "source" if "source_preserving" in exception_types else members[0]["treatment"])):
        existing = next((m for m in members if m["treatment"] == treatment), None)
        panel = existing or render({"id": "panel."+name, "treatment": treatment, "source": "master", "size": "logo_only", "box": {"width":256,"height":256}, "trim":False})
        blockers = assets["master"].report()["default_transparency_blockers"]
        panels[name] = {"artifact_sha256": panel["artifact_sha256"], "worker_receipt_sha256": panel["worker_receipt_sha256"],
                        "validation": "blocked" if blockers else "review_required"}
    preview = PreviewManifest.from_dict({"schema_version":1,"kind":"logo-preview-manifest","id":request_id+".preview","revision":request_revision,
        "provenance":{"actor":"isolated-m4-validator","role":"validator","source":"M4-owned-preview-receipts-not-production-worker-receipts","evidence_sha256":fingerprint(spec)},
        "context":context,"request_sha256":request.sha256,"default":panels["default"],"requested":panels["requested"],"members":members,
        "comparison_evidence_sha256":fingerprint(comparison)})
    bundle = Evidence.make("logo-review-bundle", {"spec_json":encoded_json(spec),"request_json":request.encoded.decode(),
        "preview_json":preview.encoded.decode(),"receipts_json":encoded_json(receipts),
        "source_reports_json":encoded_json({k:a.report() for k,a in assets.items()}),"comparison_json":encoded_json(comparison)})
    return Prepared(bundle, tuple(sorted(blobs.items())))


def verify(prepared, selection, source_root):
    """Recheck real sources, exact member receipts and complete review context."""
    payload = prepared.bundle.payload()
    spec = read_canonical(payload["spec_json"])
    _spec_check(spec, selection)
    request = ExceptionRequest.from_dict(read_canonical(payload["request_json"]))
    preview = PreviewManifest.from_dict(read_canonical(payload["preview_json"]))
    q, p = request.to_dict(), preview.to_dict()
    if q["context"] != _context(spec) or p["context"] != q["context"] or p["request_sha256"] != request.sha256:
        raise BulkError("logo_context_binding", "Request, previews or material context changed")
    if q["provenance"]["actor"] != spec["submitter"] or q["intentional_background"] != ("intentional_background" in spec["exceptions"]) or q["justification"] != spec["reason"]:
        raise BulkError("logo_request_binding", "Submitter request differs from the bound scope")
    receipts = read_canonical(payload["receipts_json"])
    reports = read_canonical(payload["source_reports_json"])
    blobs = dict(prepared.artifacts)
    assets = {}
    for key, reference in spec["sources"].items():
        if reference is not None:
            asset = read_asset(source_root, reference)
            assets[key] = asset
            if reports[key] != asset.report() or blobs.get(asset.sha256) != asset.encoded:
                raise BulkError("logo_source_evidence", "Archived source inspection differs")
    expected_comparison = compare(assets["master"], assets["white"]) if "white" in assets else None
    if canonical(read_canonical(payload["comparison_json"])) != canonical(expected_comparison) or p["comparison_evidence_sha256"] != fingerprint(expected_comparison):
        raise BulkError("logo_comparison_binding", "Comparison policy/evidence changed")
    expected = {m["id"]:m for m in spec["required_outputs"]}
    if len(p["members"]) != len(expected) or {m["id"] for m in p["members"]} != set(expected):
        raise BulkError("logo_membership", "Required output membership is incomplete or substituted")
    for member in p["members"] + [dict(panel, id="panel."+name, treatment="panel") for name,panel in (("default",p["default"]),("requested",p["requested"]))]:
        checksum = member["worker_receipt_sha256"]
        if checksum not in receipts:
            raise BulkError("logo_owned_receipt", "Missing owned preview receipt")
        receipt = Evidence.from_dict(receipts[checksum])
        r = receipt.payload()
        if receipt.sha256 != checksum or receipt.to_dict()["kind"] != "isolated-logo-preview-receipt" or r["context_sha256"] != fingerprint(spec) or r["runtime_json"] != encoded_json(spec["runtime"]):
            raise BulkError("logo_owned_receipt", "Preview receipt context or ownership changed")
        data = blobs.get(r["artifact_sha256"])
        if data is None or inspect_png(data).sha256 != r["artifact_sha256"] or len(data) != r["bytes"] or member["artifact_sha256"] != r["artifact_sha256"]:
            raise BulkError("logo_artifact_changed", "Actual preview differs from its receipt")
        if member["id"] in expected and (read_canonical(r["member_json"]) != expected[member["id"]] or member["treatment"] != expected[member["id"]]["treatment"]):
            raise BulkError("logo_membership", "Preview does not own this exact required member")
    # Integrity alone is not worker ownership. Reproduce these small isolated
    # transforms from the verified sources; do not trust a caller-resealed PNG
    # and receipt, even when all of its self-asserted hashes agree.
    replay = prepare(selection, source_root=source_root, item=Identity.from_dict(spec["item"]), submitter=spec["submitter"],
        sources=spec["sources"], background=spec["background"], exception_types=spec["exceptions"], reason=spec["reason"],
        request_id=q["id"], request_revision=q["revision"], expires_at=spec["expires_at"])
    if replay.bundle != prepared.bundle or replay.artifacts != prepared.artifacts:
        raise BulkError("logo_preview_ownership", "Evidence is not the exact result of the owned isolated preview task")
    return spec, request, preview


def approvable(prepared, selection, source_root):
    spec, request, preview = verify(prepared, selection, source_root)
    if spec["preview_type"] != "complete_overlay":
        raise BulkError("logo_incomplete_composition", "Logo-only evidence cannot approve a complete poster addition; M5/M6 composition gate pending")
    reports = read_canonical(prepared.bundle.payload()["source_reports_json"])
    if any(r["default_transparency_blockers"] for r in reports.values()) and "intentional_background" not in spec["exceptions"]:
        raise BulkError("logo_transparency", "Opaque/partial-background input needs an explicit exact transparency exception")
    comparison = read_canonical(prepared.bundle.payload()["comparison_json"])
    if comparison is not None and comparison["outcome"] != "MATCH" and "brand_lockup" not in spec["exceptions"]:
        raise BulkError("logo_comparison_review", "Unresolved paired correspondence requires explicit lockup resolution")
    return spec, request, preview


def confirm_record(prepared, actor, decision):
    """Build an M1 record as DATA. External attribution is checked by the archive."""
    payload = prepared.bundle.payload()
    request = ExceptionRequest.from_dict(read_canonical(payload["request_json"]))
    preview = PreviewManifest.from_dict(read_canonical(payload["preview_json"]))
    return SubmitterConfirmation.from_dict({"schema_version":1,"kind":"submitter-confirmation","id":request.to_dict()["id"]+".confirm","revision":request.to_dict()["revision"],
        "provenance":{"actor":actor.actor,"role":"submitter","source":"controlled-operator-attribution","evidence_sha256":actor.evidence_sha256},
        "context":request.to_dict()["context"],"request_sha256":request.sha256,"preview_sha256":preview.sha256,
        "membership_sha256":fingerprint(preview.to_dict()["members"]),"decision":decision})


def decision_record(prepared, confirmation, actor, decision):
    payload = prepared.bundle.payload()
    request = ExceptionRequest.from_dict(read_canonical(payload["request_json"]))
    preview = PreviewManifest.from_dict(read_canonical(payload["preview_json"]))
    return ExceptionDecision.from_dict({"schema_version":1,"kind":"maintainer-exception-decision","id":request.to_dict()["id"]+".decision","revision":request.to_dict()["revision"],
        "provenance":{"actor":actor.actor,"role":"maintainer","source":"controlled-operator-attribution","evidence_sha256":actor.evidence_sha256},
        "context":request.to_dict()["context"],"request_sha256":request.sha256,"preview_sha256":preview.sha256,
        "confirmation_sha256":confirmation.sha256,"membership_sha256":fingerprint(preview.to_dict()["members"]),
        "selected_treatment":request.to_dict()["requested_treatment"],"intentional_background":request.to_dict()["intentional_background"],"decision":decision})
