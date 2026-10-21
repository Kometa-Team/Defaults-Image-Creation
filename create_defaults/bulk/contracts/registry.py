"""Read-only, exact-pinned registry selection, without activation or publishing."""

from dataclasses import dataclass
import re
from typing import Callable, Mapping

from ..common import BulkError
from ..library_publication import REVIEWERS
from .models import AdoptionRecord, Contract, ContractApproval, RegistryDocument


def require_hash(value):
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise BulkError("invalid_contract_hash", "An exact lowercase SHA-256 is required")
    return value


def package_reference(contract: Contract) -> dict:
    value = contract.to_dict()
    return {key: value[key] for key in ("category", "kind", "version")} | {"sha256": contract.sha256}


@dataclass(frozen=True)
class TrustedDecision:
    """Operator-supplied decision attribution, outside submitted JSON.

    This is not an authenticator. A future controlled intake adapter must obtain
    it from the actual decision. Integrity-only JSON must never construct this
    trust map. Reuse the existing maintainer allowlist, not a new identity system.
    """

    actor: str
    evidence_sha256: str

    def __post_init__(self):
        require_hash(self.evidence_sha256)
        if self.actor not in REVIEWERS:
            raise BulkError("untrusted_contract_actor", "Unknown maintainer")


@dataclass(frozen=True)
class RegistrySnapshot:
    document: RegistryDocument
    contracts: tuple[Contract, ...]

    @classmethod
    def load(cls, encoded: bytes, *, expected_sha256: str,
             read_object: Callable[[str], bytes],
             trusted_decisions: Mapping[str, TrustedDecision]):
        """Verify structure, exact pins and explicit contract decision provenance.

        No latest lookup, inheritance, receipt rewrite or enforcement activation.
        The registry hash itself must be selected by the trusted caller, not read
        from the untrusted registry. Returned metadata is not artwork approval.
        """
        expected_sha256 = require_hash(expected_sha256)
        document = RegistryDocument.from_bytes(encoded)
        if document.sha256 != expected_sha256:
            raise BulkError("contract_hash_mismatch", "Registry differs from the selected pin")
        registry = document.to_dict()
        if registry["owner"] not in REVIEWERS:
            raise BulkError("untrusted_contract_actor", "Registry owner is not an allowed maintainer")
        contracts = []
        for entry in registry["entries"]:
            package = entry["package"]
            contract = Contract.from_bytes(read_object(package["sha256"]))
            if package_reference(contract) != package:
                raise BulkError("contract_hash_mismatch", "Registry package pin or version mismatch")
            value = contract.to_dict()
            if value["owner"] not in REVIEWERS:
                raise BulkError("untrusted_contract_actor", "Contract owner is not an allowed maintainer")
            if set(entry["variants"]) != {v["id"] for v in value["variants"]}:
                raise BulkError("contract_membership_mismatch", "Registry must enumerate the complete closed variant set")
            approval = ContractApproval.from_bytes(read_object(entry["approval_sha256"]))
            if approval.sha256 != entry["approval_sha256"]:
                raise BulkError("contract_hash_mismatch", "Approval differs from its pin")
            decision = approval.to_dict()
            trusted = trusted_decisions.get(approval.sha256)
            if (not isinstance(trusted, TrustedDecision)
                    or decision["provenance"]["actor"] != trusted.actor
                    or decision["provenance"]["evidence_sha256"] != trusted.evidence_sha256
                    or decision["decision"] != "approved"
                    or decision["package"] != package):
                raise BulkError("untrusted_contract_approval", "Missing or mismatched external maintainer decision")
            for adoption_hash in entry["adoption_sha256"]:
                adoption = AdoptionRecord.from_bytes(read_object(adoption_hash))
                if adoption.sha256 != adoption_hash or adoption.to_dict()["package"] != package:
                    raise BulkError("contract_hash_mismatch", "Adoption reference differs from its pinned package")
                # Structural provenance only. Compatibility/owned-receipt proof
                # and adoption authority are M2; this loader never adopts jobs.
            contracts.append(contract)
        return cls(document, tuple(contracts))

    def select(self, category: str, kind: str, version: str, sha256: str, variant: str) -> Contract:
        require_hash(sha256)
        for contract in self.contracts:
            value = contract.to_dict()
            if (value["category"], value["kind"], value["version"], contract.sha256) == (category, kind, version, sha256):
                if variant in {v["id"] for v in value["variants"]}:
                    return contract
        raise BulkError("unknown_contract_pin", "Exact contract/version/hash/variant is not in this snapshot")
