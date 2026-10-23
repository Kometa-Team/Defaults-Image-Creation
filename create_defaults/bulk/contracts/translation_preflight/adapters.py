"""Replay real M5 definitions; an intake dictionary is never an expander."""

from dataclasses import dataclass

from ...common import BulkError, canonical, fingerprint
from ..language_policy.models import ValidationSubject
from ..models import Contract
from ..registry import require_hash


def fail(code):
    raise BulkError("p3m2_"+code, "Translation preflight input failed: "+code)


def package_ref(contract):
    value = contract.to_dict()
    return {k: value[k] for k in ("category", "kind", "version")} | {"sha256": contract.sha256}


def selected_design(package, variant, contract_pin, rules_pin):
    from ..categories.release import Package
    if type(package) is not Package or type(package.contract) is not Contract:
        fail("package_type")
    if package.contract.sha256 != require_hash(contract_pin) or package.rules.sha256 != require_hash(rules_pin):
        fail("package_pin")
    c, r = package.contract.to_dict(), package.rules.to_dict()
    if (r["contract_sha256"], r["category"], r["version"]) != (contract_pin, c["category"], c["version"]):
        fail("rules_binding")
    rules, _ = package.data()
    design = next((v["design"] for v in c["variants"] if v["id"] == variant), None)
    if design is None or variant not in rules or rules[variant]["design_sha256"] != fingerprint(design):
        fail("variant")
    return c, design, rules[variant]


def subject(identity, language, package, variant, definition, dependencies, outputs, review):
    return ValidationSubject.from_dict(dict(schema_version=1, kind="validation-subject", stage="subject",
        id=identity, version="1.0.0", language=language, contract=package_ref(package.contract), variant=variant,
        expanded_definition_sha256=fingerprint(definition), dependencies_sha256=fingerprint(dependencies),
        review_context_sha256=require_hash(review), outputs=sorted(outputs, key=lambda o: o["id"]),
        membership_sha256=fingerprint(sorted(outputs, key=lambda o: o["id"]))))


@dataclass(frozen=True)
class PosterRequest:
    """Controlled exact pins and assigned identities, not contributor JSON or approval."""

    resolution: object
    identity: str
    package: object
    contract_sha256: str
    rules_sha256: str
    variant: str
    outputs_json: bytes
    review_context_sha256: str

    def expand(self, language):
        from ..expanded.resolution import Resolution, resolve
        from ..models import decode_json
        if type(self.resolution) is not Resolution:
            fail("resolution_type")
        c, design, rule = selected_design(self.package, self.variant, self.contract_sha256, self.rules_sha256)
        if c["kind"] != "poster":
            fail("poster_kind")
        self.resolution.verify_current([self.identity])
        # Public Resolution values are not authority. Re-enter the real loader
        # and expander; a forged encoded value with authentic file pins fails.
        pins = self.resolution.source_pins
        before = self.resolution.data()
        profile_names = {row["profile_file"] for row in before["provenance"].values()}
        profile = [p for name, p, _ in pins if name in profile_names]
        if len(profile) != 1:
            fail("profile_source")
        replay = resolve([p for name, p, _ in pins if name not in profile_names], profiles_path=profile[0])
        current = replay.data()
        if canonical(before) != canonical(current):
            fail("resolution_replay")
        definition = replay.definition(self.identity, language)
        if definition["category"] != c["category"]:
            fail("category")
        caption = definition["caption"]
        from ..adoption.models import read_canonical
        types = read_canonical(rule["caption_types_json"])
        caption_allowed = any(caption == read_canonical(t["definition_json"]) for t in types.values())
        from ..categories.compiler import layout_shape
        style = {k: v for k, v in definition["composer"].items() if k not in {"logo", "input", "base_color", "out_name", "text"}}
        caption_allowed = (caption_allowed and style == read_canonical(rule["style_json"])
                           and layout_shape(definition) == read_canonical(rule["layout_json"]))
        parent = next((p for p, children in current["families"].items() if self.identity in children), self.identity)
        dependencies = {"definition": fingerprint(definition), "origin": current["provenance"][parent],
            "generator": current["origins"].get(self.identity),
            "family": sorted(current["families"].get(parent, [])), "rules": self.rules_sha256}
        outputs = decode_json(self.outputs_json)
        local = "/".join(filter(None, ("defaults-"+language, definition["output"]["directory"], definition["output"]["filename"])))
        if (len(outputs) != 1 or outputs[0]["id"] != self.identity or outputs[0]["local_path"] != local
                or outputs[0]["public_path"] != definition["output"]["remote_paths"].get(language)):
            fail("output_mapping")
        vs = subject(self.identity, language, self.package, self.variant, definition, dependencies,
                     outputs, self.review_context_sha256)
        applicable = language in definition["languages"] and definition["applicability"].get(language, {}).get("status") == "applicable"
        allowed = language in design["caption"]["languages"]
        return vs, definition, dependencies, caption, applicable, allowed, caption_allowed


@dataclass(frozen=True)
class OverlayRequest:
    """An exact existing M2 overlay record; never inspect image pixels to infer text."""

    record: object
    record_sha256: str
    package: object
    contract_sha256: str
    rules_sha256: str
    variant: str

    def expand(self, language):
        from ..adoption.models import HistoricalOutput, read_canonical
        c, design, _ = selected_design(self.package, self.variant, self.contract_sha256, self.rules_sha256)
        if type(self.record) is not HistoricalOutput or self.record.sha256 != require_hash(self.record_sha256):
            fail("overlay_record")
        record = HistoricalOutput.from_bytes(self.record.encoded).to_dict()
        identity = record["identity"]
        _, members = self.package.data()
        member = members.get(identity["id"])
        if (c["kind"] != "overlay" or design["treatment"] != "SOURCE_PRESERVING" or member is None
                or member["record_sha256"] != self.record_sha256 or member["variant"] != self.variant):
            fail("overlay_membership")
        definition = read_canonical(record["effective_definition_json"])
        if definition["group"].replace("/", ".") != self.variant:
            fail("overlay_variant")
        outputs = [dict(id=identity["id"], identity_sha256=fingerprint(identity),
                        local_path=identity["local_path"], public_path=identity["public_path"])]
        deps = {"record": self.record_sha256, "rules": self.rules_sha256}
        vs = subject(identity["id"], language, self.package, self.variant, definition, deps, outputs, member["context_sha256"])
        caption = dict(mode="none", key=None, template_key=None, text="", case="exact", direction="auto", fallback=None)
        # Current overlay packages have no multilingual contract language field.
        # They establish historical English only; policy coverage cannot widen it.
        return vs, definition, deps, caption, language == "en", language == "en", True
