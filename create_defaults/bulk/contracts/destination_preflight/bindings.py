"""Exact M2 companions and closed M6 output membership; no M4 readiness checks."""

from dataclasses import dataclass
import json

from ...common import fingerprint
from ..language_policy import ValidationSubject, reference
from ..translation_preflight import TranslationPreflight
from ..translation_preflight.adapters import selected_design, package_ref
from ..registry import require_hash
from .paths import fail


@dataclass(frozen=True)
class BoundTranslation:
    subject: ValidationSubject
    subject_sha256: str
    translation: TranslationPreflight
    translation_sha256: str
    package: object
    contract_sha256: str
    rules_sha256: str

    def inspect(self, language_policy):
        if type(self.subject) is not ValidationSubject or type(self.translation) is not TranslationPreflight:
            fail("translation_type")
        if self.subject.sha256 != require_hash(self.subject_sha256) or self.translation.sha256 != require_hash(self.translation_sha256):
            fail("translation_pin")
        # Reparse closed values, but do not pretend a hash authenticates them or
        # repeat M2 source-verification/readiness consumption (reserved for M4).
        subject = ValidationSubject.from_bytes(self.subject.encoded).to_dict()
        translation = TranslationPreflight.from_bytes(self.translation.encoded).to_dict()
        if translation["subject"] != subject or translation["language_policy"] != reference(language_policy):
            fail("translation_binding")
        if (language_policy.resolve(translation["requested_language"]) != subject["language"]
                or translation["language"] != subject["language"]):
            fail("translation_language")
        contract, design, _ = selected_design(self.package, subject["variant"], self.contract_sha256, self.rules_sha256)
        if subject["contract"] != package_ref(self.package.contract):
            fail("translation_contract")
        allowed = (subject["language"] == "en" if contract["kind"] == "overlay"
                   else subject["language"] in design["caption"]["languages"])
        allowed = allowed and any(row["package"] == subject["contract"] and row["variant"] == subject["variant"]
                                 and subject["language"] in row["languages"] for row in language_policy.to_dict()["coverage"])
        return subject, translation, allowed


def cohort(items, policy):
    if type(items) is not tuple or not items or len(items) > 20000 or any(type(item) is not BoundTranslation for item in items):
        fail("cohort_type")
    records, outputs, blockers, seen = [], [], [], set()
    for item in items:
        subject, translation, allowed = item.inspect(policy)
        if subject["id"] in seen:
            fail("duplicate_subject")
        seen.add(subject["id"])
        if not allowed:
            blockers.append("contract_language_not_permitted")
        if not translation["technical_eligible"]:
            blockers.append("translation_technical_blocked")
        records.append(dict(subject=reference(item.subject), translation=dict(kind="translation-preflight", version="1.0.0", sha256=item.translation.sha256),
            contract=subject["contract"], variant=subject["variant"], language=subject["language"], rules_sha256=item.rules_sha256,
            membership_sha256=subject["membership_sha256"], translation_blockers=translation["blockers"]))
        outputs.extend(subject["outputs"])
    if len({r["language"] for r in records}) != 1 or len({o["id"] for o in outputs}) != len(outputs):
        fail("cohort_membership")
    # M6's exact historical companion mapping owns overlay sizes and paired-logo
    # membership; filenames or matching bytes never invent companion identities.
    missing = []
    output_ids = {o["id"] for o in outputs}
    ownership = {o["id"]: (i.contract_sha256, i.rules_sha256) for i in items for o in i.subject.to_dict()["outputs"]}
    for item in items:
        s = item.subject.to_dict()
        _, members = item.package.data()
        member = members.get(s["id"])
        if member:
            if member["variant"] != s["variant"]:
                fail("member_variant")
            missing.extend(set(member["companions"])-output_ids)
            if any(ownership.get(partner, (item.contract_sha256, item.rules_sha256)) != (item.contract_sha256, item.rules_sha256) for partner in member["companions"]):
                fail("companion_contract")
            if s["contract"]["kind"] == "overlay":
                deps = json.loads(item.translation.to_dict()["definition_dependencies_json"])
                if deps.get("record") != member["record_sha256"] or s["review_context_sha256"] != member["context_sha256"]:
                    fail("overlay_review_context")
        elif s["contract"]["kind"] == "overlay":
            fail("unknown_overlay_membership")
        else:
            rules, _ = item.package.data()
            if set(rules[s["variant"]]["required_presentations"]) != {"single"}:
                blockers.append("unverified_companion_membership")
    if missing:
        blockers.append("missing_required_companions")
    records.sort(key=lambda r: r["subject"]["sha256"])
    outputs.sort(key=lambda r: r["id"])
    return records, outputs, sorted(set(blockers)), sorted(set(missing)), fingerprint(dict(records=records, outputs=outputs))
