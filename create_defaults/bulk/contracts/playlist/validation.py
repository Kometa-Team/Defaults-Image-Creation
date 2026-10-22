"""Playlist-only validation against exact M1 packages and M2 historical facts.

This module never constructs a trusted decision from JSON, opens Package E
state, renders a preview, or authorizes an output. The bundled registry is an
empty review basis until a genuine decision approves the new exact package.
"""

from dataclasses import dataclass
from enum import Enum
import gzip
from pathlib import Path, PurePosixPath
import unicodedata

from ...common import BulkError, canonical, confined, fingerprint, sha256
from ...config import ROOT
from ...catalog import load_catalog
from ...definitions import Definition
from ...planner import effective_parameters, renderer_identity
from ...translations import Translations
from ..adoption.models import HistoricalOutput, HistoricalRegistry, equal, read_canonical
from ..adoption.sources import load_pins, verify_sources
from ..models import Contract, ContractApproval, ExceptionRequest, Identity, RegistryDocument, check_namespace, decode_json, read_json_bytes
from ..registry import RegistrySnapshot, package_reference, require_hash


HERE = Path(__file__).parent
SOURCE_MAIN = "f2b7843fd1d832e2aecc36d66046b1010ed7fd5d"
# Release pins are review aids; callers must still explicitly supply their pins.
CONTRACT_SHA256 = "5047d834ecd3f8e5a0ed76ae24760b6947ae6b83e95198ce602e1715e445016b"
REGISTRY_SHA256 = "8f653ccd64c0635cebcf148261b7ff48871929eac569a84875d58a334947925b"
M2_SHA256 = "0b0c2af06124379206d43c36a4c12fb456e3861dd335343f4382865a7aab6a05"
HISTORICAL_SHA256 = "dfd5948dd9b80975ee30a58d1cc412232be34702a3d065df5a1eaaba869744d5"
VARIANT = "timeline-order"


class ExceptionState(str, Enum):
    DEFAULT_SELECTED = "default_selected"
    REQUESTED = "source_preserving_requested"
    PENDING = "pending_review"
    # Reserved evidence-interface states: M3 has no transition granting them.
    APPROVED = "approved_by_separately_verified_authority"
    REJECTED = "rejected_by_separately_verified_authority"


@dataclass(frozen=True)
class SubmissionAssessment:
    content_json: bytes
    default_treatment: str
    requested_treatment: str | None
    conditions: tuple[ExceptionState, ...]
    request_sha256: str | None
    background_status: str = "pending_maintainer_approval"
    asset_status: str = "reference_hash_verified_pixels_not_inspected"
    publication_authorized: bool = False

    def to_dict(self):
        return {"content": decode_json(self.content_json), "default_treatment": self.default_treatment,
                "requested_treatment": self.requested_treatment,
                "conditions": [s.value for s in self.conditions], "request_sha256": self.request_sha256,
                "background_status": self.background_status, "asset_status": self.asset_status,
                "publication_authorized": self.publication_authorized}


def _same(expected, observed, identity, path):
    # Canonical comparison distinguishes bool/int, literal case and raw overrides
    # that happen to normalize/clamp to the same renderer value.
    equal(canonical(expected).decode(), canonical(observed).decode(), category="Playlist",
          identity=identity, path=path, code="playlist_material_mismatch")


def _pinned_document(cls, path, checksum):
    document = cls.from_bytes(read_json_bytes(path))
    if document.sha256 != require_hash(checksum):
        raise BulkError("playlist_pin", "Document differs from the externally selected SHA-256")
    return document


@dataclass(frozen=True)
class PlaylistBoundary:
    contract: Contract
    registry: RegistryDocument
    adoption: HistoricalRegistry
    records: tuple[HistoricalOutput, ...]

    @classmethod
    def load(cls, *, contract_sha256, registry_sha256, adoption_sha256, root=HERE):
        """Load a review candidate, NOT an approved/active registry selection.

        An approved registry must instead pass unchanged M1 RegistrySnapshot.load
        with externally attributed decisions. No trust-map default is supplied
        for that path. The empty review basis cannot select a contract.
        """
        root = Path(root)
        contract = _pinned_document(Contract, confined(root, "contract-v1.json", must_exist=True), contract_sha256)
        registry = _pinned_document(RegistryDocument, confined(root, "registry-v1.json", must_exist=True), registry_sha256)
        # Even an empty review basis goes through M1's exact-pinned loader.
        def no_approval(_):
            raise BulkError("playlist_unapproved_registry", "Review loading cannot supply package approval evidence")
        RegistrySnapshot.load(registry.encoded, expected_sha256=registry_sha256,
                              read_object=no_approval, trusted_decisions={})
        _same([], registry.to_dict()["entries"], "registry", "review_basis.entries")
        raw_path = HERE.parent / "adoption/baseline/frozen-registry-v1.json.gz"
        with gzip.open(raw_path, "rb") as stream:
            raw = stream.read(8 * 1024 * 1024 + 1)
        adoption = HistoricalRegistry.from_bytes(raw)
        if adoption.sha256 != require_hash(adoption_sha256) or adoption.sha256 != M2_SHA256:
            raise BulkError("playlist_adoption_pin", "M2 historical identity basis differs")
        adoption.verify_schema_pins()
        values = decode_json(read_json_bytes(confined(root, "historical-outputs-v1.json", must_exist=True)))
        if type(values) is not list or fingerprint(values) != HISTORICAL_SHA256:
            raise BulkError("playlist_historical_pin", "Historical Playlist records differ from the selected M2 extraction")
        records = tuple(HistoricalOutput.from_dict(v) for v in values)
        result = cls(contract, registry, adoption, records)
        result.verify_membership(records)
        result.verify_design()
        return result

    def verify_membership(self, records):
        members = {m["id"]: m for m in self.adoption.to_dict()["members"] if m["id"].startswith("playlist.")}
        _same(9, len(members), "membership", "M2.count")
        _same(sorted(members), sorted(r.to_dict()["identity"]["id"] for r in records), "membership", "complete_nine")
        check_namespace([Identity.from_dict(r.to_dict()["identity"]) for r in records])
        for record in records:
            value = record.to_dict()
            member = members[value["identity"]["id"]]
            _same(member["sha256"], record.sha256, value["identity"]["id"], "M2.record_sha256")
            _same(member["job_id"], value["job_id"], value["identity"]["id"], "M2.job_id")
            _same("Playlist", value["identity"]["category"], value["identity"]["id"], "M2.category")

    def verify_design(self):
        value = self.contract.to_dict()
        _same(("Playlist", "poster"), (value["category"], value["kind"]), "contract", "category/kind")
        _same([VARIANT], [v["id"] for v in value["variants"]], "contract", "closed_variants")
        design = value["variants"][0]["design"]
        _same(["display_name", "source", "content_type", "background_proposal"],
              value["variants"][0]["contributor_fields"], "contract", "permitted_fields")
        measurements, assignments, approvals = {}, {}, set()
        for record in self.records:
            r = record.to_dict()
            identity = r["identity"]["id"]
            job = read_canonical(r["job_json"])
            parameters = job["parameters"]
            font = design["typography"]
            _same(font["asset"], next({"path": i["path"], "sha256": i["sha256"]} for i in job["inputs"] if i["role"] == "font"), identity, "font")
            _same({"font": font["asset"]["path"], "font_size": font["size"], "font_color": font["color"],
                   "logo_resize": design["geometry"]["logo_width"], "logo_offset": design["geometry"]["logo_offset"],
                   "text_offset": design["geometry"]["caption_offset"], **design["effects"], "white_wash": True,
                   "avg_color": False, "avg_color_image": None, "dom_color": False, "dom_color_image": None},
                  {k: v for k, v in parameters.items() if k not in {"logo", "base_color", "out_name", "text"}}, identity, "all_locked_parameters")
            _same("TIMELINE ORDER", parameters["text"], identity, "caption.text")
            _same("key_names.TIMELINE_ORDER", job["translation"]["trace"][0]["key"], identity, "caption.key")
            _same(design["caption"]["registry_sha256"], job["translation"]["trace"][0]["source_sha256"], identity, "caption.resource")
            measurements[identity] = job["layout_evidence"]
            assignments[identity] = {"color": parameters["base_color"], "provenance": job["color_assignment"]}
            approvals.update(a["record_sha256"] for a in r["evidence"]["approval_refs"])
        _same(fingerprint(measurements), design["fitting"]["measurement_sha256"], "contract", "nine_measurement_contexts")
        _same(fingerprint(assignments), design["background"]["assignments_sha256"], "contract", "nine_background_assignments")
        _same(sorted(approvals), design["logo"]["historical_acceptance_refs"], "contract", "historical_acceptance_refs")
        # Check every remaining contract leaf, including policy and provenance,
        # against the authored release. A new external pin cannot weaken v1.
        if self.contract.sha256 != CONTRACT_SHA256:
            raise BulkError("playlist_contract_release", "Changed rules require a new explicitly reviewed release")

    def record(self, identity):
        matches = [r for r in self.records if r.to_dict()["identity"]["id"] == identity]
        if len(matches) != 1:
            raise BulkError("playlist_identity", "Identity does not select one frozen Playlist output")
        return matches[0]

    def registry_for_decision(self, approval: ContractApproval, *, trusted_decisions):
        """M1 handoff ONLY after a real exact-package decision exists.

        Nothing is persisted/activated. An approval-shaped JSON object, matching
        reviewer name or the M3 implementation directive cannot supply trust.
        """
        if not isinstance(approval, ContractApproval):
            raise BulkError("playlist_approval", "Expected a typed, separately attributed exact contract decision")
        document = RegistryDocument.from_dict({"schema_version": 1, "kind": "category-contract-registry",
            "id": "playlist-contracts", "version": "1.0.0", "owner": self.contract.to_dict()["owner"],
            "provenance": self.contract.to_dict()["provenance"],
            "entries": [{"package": package_reference(self.contract), "variants": [VARIANT],
                         "approval_sha256": approval.sha256, "adoption_sha256": []}]})
        objects = {self.contract.sha256: self.contract.encoded, approval.sha256: approval.encoded}
        # Loading is still governed by the existing exact-pinned M1 authority
        # boundary. Caller must externally pin the returned registry before use.
        RegistrySnapshot.load(document.encoded, expected_sha256=document.sha256,
                              read_object=objects.__getitem__, trusted_decisions=trusted_decisions)
        return document

    def validate_existing(self, identity, definition, job):
        """Validate the actual expanded definition AND raw/effective job.

        Whole-object equality rejects inherited/nested overrides, normalized
        aliases and clamped values, as well as missing/unknown context. This is
        deliberately Playlist-specific; it does not install an M5 planner gate.
        """
        reference = self.record(identity).to_dict()
        Definition.create(definition)
        _same(read_canonical(reference["effective_definition_json"]), definition, identity, "effective_definition")
        _same(read_canonical(reference["job_json"]), job, identity, "complete_effective_job")
        _same(effective_parameters(job["raw_parameters"]), job["parameters"], identity, "raw/effective")
        return {"identity": identity, "outcome": "compatible", "historical_record_sha256": fingerprint(reference),
                "fingerprints": reference["fingerprints"], "publication_authorized": False}

    def request_context(self, identity: Identity, content):
        """Evidence interface for an externally assigned identity; never mint one.

        Bind exact original source, contract, default transform and semantic
        content. M4 must extend the context with actual previews/runtime/output
        membership before separately verifying submitter/maintainer decisions.
        """
        return {"package": package_reference(self.contract), "variant": VARIANT,
                "identities": [identity.to_dict()["id"]], "source": content["source"],
                "material_context_sha256": fingerprint({"identity": identity.to_dict(), "content": content,
                    "design": self.contract.to_dict()["variants"][0]["design"]}),
                "transformations": [self.contract.to_dict()["variants"][0]["design"]["logo"]["transformation"]]}

    def validate_proposed_definition(self, identity: Identity, content, definition, *, source_root=ROOT, request=None):
        """Check new effective metadata without accepting a new item or job.

        A prospective authored definition may describe the proposed background,
        but remains pending. No historical measurement/approval is transferred.
        New preview/fit evidence and final background/asset decisions await M4;
        general expansion/dependency attestations await M5.
        """
        assessment = self.validate_submission(content, source_root=source_root, identity=identity, request=request)
        Definition.create(definition)
        assigned = identity.to_dict()
        name = assigned["id"]
        baseline = read_canonical(self.records[0].to_dict()["effective_definition_json"])
        source = decode_json(assessment.content_json)["source"]
        output = PurePosixPath(assigned["local_path"])
        if (str(output.parent) != "defaults-en/playlist" or output.suffix != ".jpg"
                or assigned["public_path"] != "playlist/" + output.name):
            raise BulkError("playlist_mapping", "Assigned new mapping must remain an exact English Playlist JPEG pair")
        composer = dict(baseline["composer"], base_color=content["background_proposal"], logo=source["path"], out_name=output.stem)
        for key, expected in {"id": name, "category": "Playlist", "display_name": content["display_name"],
                "composer": composer, "caption": baseline["caption"], "languages": ["en"],
                "layout": {"kind": "fixed", "measurement": None}, "overrides": [], "dependencies": [], "generator": None,
                "output": {"directory": "playlist", "filename": output.name, "remote_paths": {"en": assigned["public_path"]}},
                "color_assignment": {"id": name + ".background", "origin": "independent", "parent": None,
                                     "relationship": None, "exception": None}}.items():
            _same(expected, definition[key], name, "proposed_definition." + key)
        _same("authored", definition["source"].get("kind"), name, "source.kind")
        _same(["en"], sorted(definition["applicability"]), name, "applicability.languages")
        _same("applicable", definition["applicability"]["en"]["status"], name, "applicability.en")
        # Reject raw changes even if renderer normalization gives the same result.
        raw = dict(definition["composer"], text=assigned["rendered_caption"])
        _same(raw, effective_parameters(raw), name, "proposed_raw/effective")
        return assessment

    def validate_submission(self, content, *, source_root=ROOT, identity=None, request=None):
        """Check proposed content/asset bytes only, not pixels or approval.

        ``identity`` comes from controlled assignment, outside contributor JSON.
        M3 accepts no decision/confirmation/preview input and has no approved or
        rejected transition. Those typed M1 evidence interfaces remain for M4.
        """
        content = self.contract.validate_content(VARIANT, content)
        if not {"display_name", "source", "background_proposal"} <= set(content):
            raise BulkError("playlist_required_content", "Display, source and proposed brand background are mandatory")
        if not content["display_name"].strip() or unicodedata.normalize("NFC", content["display_name"]) != content["display_name"]:
            raise BulkError("playlist_display_name", "New display names must be nonblank NFC")
        source = content["source"]
        if PurePosixPath(source["path"]).suffix.lower() != ".png" or not source["path"].startswith("logos_playlist/"):
            raise BulkError("playlist_source", "New Playlist source references must be exact PNG paths under logos_playlist")
        actual = sha256(confined(Path(source_root), source["path"], must_exist=True))
        _same(source["sha256"], actual, "submission", "source.sha256")
        states = [ExceptionState.DEFAULT_SELECTED]
        request_hash = requested = None
        if identity is not None:
            if not isinstance(identity, Identity):
                raise BulkError("playlist_identity", "Expected a separately assigned typed identity")
            identity.require_new_names()
            data = identity.to_dict()
            _same("Playlist", data["category"], data["id"], "submission.category")
            _same(source, data["source"], data["id"], "submission.source")
            _same(content["display_name"], data["display_name"], data["id"], "submission.display_name")
            _same("TIMELINE ORDER", data["rendered_caption"], data["id"], "submission.caption")
            check_namespace([Identity.from_dict(r.to_dict()["identity"]) for r in self.records] + [identity])
        if request is not None:
            if not isinstance(request, ExceptionRequest) or identity is None:
                raise BulkError("playlist_exception_request", "An M1 request and separately assigned identity are required")
            r = request.to_dict()
            _same(self.request_context(identity, content), r["context"], identity.to_dict()["id"], "request.context")
            if not r["justification"].strip():
                raise BulkError("playlist_exception_request", "Exception requests require a substantive reason")
            requested = r["requested_treatment"]
            if requested not in {"WHITE_ONLY", "SOURCE_PRESERVING"} or (requested == "WHITE_ONLY" and not r["intentional_background"]):
                raise BulkError("playlist_exception_request", "Request must identify an allowed presentation/background departure")
            if requested == "SOURCE_PRESERVING":
                states.append(ExceptionState.REQUESTED)
            states.append(ExceptionState.PENDING)
            request_hash = request.sha256
        return SubmissionAssessment(canonical(content), "WHITE_ONLY", requested, tuple(states), request_hash)

    def audit(self):
        """Reproducible nine-item read-only audit; report all material mismatches."""
        verify_sources(load_pins())
        definitions = {d.id: d.for_language("en").data for d in load_catalog(("Playlist",))}
        expected_ids = sorted(r.to_dict()["identity"]["id"] for r in self.records)
        membership = sorted(definitions) == expected_ids
        translations = Translations({"en": ROOT / "fixtures/english/en.yml"})
        # Source pins above verify raw resource LF bytes before retaining the
        # exact old provenance (as in M2). No translation behavior is changed.
        translations.hashes["en"] = load_pins()["historical_english_sha256"]
        results = []
        for record in sorted(self.records, key=lambda r: r.to_dict()["identity"]["id"]):
            r = record.to_dict()
            identity = r["identity"]["id"]
            try:
                if identity not in definitions:
                    raise BulkError("playlist_missing_definition", "Frozen item is missing from current catalog")
                definition = definitions[identity]
                job = read_canonical(r["job_json"])
                caption = translations.resolve(definition["caption"], "en")
                fresh = dict(job, raw_parameters=dict(definition["composer"], text=caption.text),
                             parameters=effective_parameters(dict(definition["composer"], text=caption.text)),
                             layout_evidence=definition["layout"], color_assignment=definition["color_assignment"],
                             translation={"mode": caption.mode, "trace": list(caption.trace), "fingerprint": caption.fingerprint})
                result = self.validate_existing(identity, definition, fresh)
                for item in job["inputs"]:
                    _same(item["sha256"], sha256(confined(ROOT, item["path"], must_exist=True)), identity, item["path"])
                result.update(source=r["identity"]["source"], local_path=r["identity"]["local_path"],
                              public_path=r["identity"]["public_path"], background=job["parameters"]["base_color"],
                              output_sha256=r["evidence"]["output_sha256"], historical_evidence=r["evidence"],
                              historical_exceptions=r["historical_exceptions"])
            except (BulkError, OSError) as error:
                result = {"identity": identity, "outcome": "incompatible", "code": getattr(error, "code", "playlist_source_io"),
                          "details": str(error), "publication_authorized": False}
            results.append(result)
        renderer = renderer_identity()
        design = self.contract.to_dict()["variants"][0]["design"]
        _same(renderer["sources"]["create_poster.py"], design["logo"]["transformation"]["sha256"], "contract", "wash_implementation")
        _same(fingerprint(renderer["encoding"]), design["output"]["encoding_sha256"], "contract", "encoding")
        return {"source_main": SOURCE_MAIN, "contract_version": self.contract.to_dict()["version"],
                "contract_sha256": self.contract.sha256, "registry_version": self.registry.to_dict()["version"],
                "registry_sha256": self.registry.sha256, "registry_status": "empty_review_basis_exact_package_not_approved",
                "M2_sha256": self.adoption.sha256, "M2_total_outputs": len(self.adoption.to_dict()["members"]),
                "compatible": membership and all(r["outcome"] == "compatible" for r in results),
                "membership_exact": membership, "observed_catalog_ids": sorted(definitions), "items": results,
                "locked_design": design, "contributor_fields": self.contract.to_dict()["variants"][0]["contributor_fields"],
                "production_enforcement": False, "publication_authorized": False,
                "new_asset_pixels_inspected": False, "phase3_translation_gate": False}
