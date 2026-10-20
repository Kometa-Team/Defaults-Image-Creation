"""D01 color policy, deterministic suggestions and transactional reservations."""

from dataclasses import asdict, dataclass
import colorsys
import hashlib
from io import BytesIO
import json
from math import isfinite
from pathlib import Path
import uuid
import warnings

from PIL import Image

from .color_math import contrast, delta_e_2000, lab, rgb
from .common import BulkError, Conflict, Diagnostic, canonical, fingerprint, normalize_hex, reject_links, sha256
from .config import CATEGORIES


@dataclass(frozen=True)
class ColorPolicy:
    version: str
    near_threshold: float
    readability_threshold: float

    def __post_init__(self):
        if not self.version or any(type(value) not in (float, int) or not isfinite(value) or value < 0 for value in (self.near_threshold, self.readability_threshold)):
            raise BulkError("invalid_policy", "Explicit finite versioned advisory thresholds required")

    @property
    def fingerprint(self):
        return fingerprint(asdict(self) | {"rules": "defaults-colors-v1", "distance": "CIEDE2000-D65-k1"})


class ColorRegistry:
    def __init__(self, store, policy, *, authorized_reviewers=()):
        self.store, self.policy = store, policy
        self.authorized_reviewers = frozenset(authorized_reviewers)

    def import_historical(self, audit):
        records = [*audit["assignments"], *audit["generated_assignments"]]
        with self.store.transaction() as db:
            for item in records:
                identity = "historical:" + item["audit_id"]
                value = (identity, identity, item["category"], normalize_hex(item["hex"]), "historical", canonical(item).decode(), "legacy-preserved-not-exception")
                old = db.execute("SELECT * FROM color_assignments WHERE id=?", (identity,)).fetchone()
                if old is not None:
                    if any(old[key] != expected for key, expected in zip(("id", "category", "hex", "origin", "source", "policy"), (value[0], *value[2:]))):
                        raise Conflict("Historical color import differs from retained evidence")
                else:
                    db.execute("INSERT INTO color_assignments VALUES (?,?,?,?,?,?,?)", value)
            self.store.event(db, "historical_colors_imported", "colors", {"audit_sha256": fingerprint(audit), "assignments": len(records)})
        return len(records)

    def link_historical(self, assignment, poster):
        with self.store.transaction() as db:
            old = db.execute("SELECT * FROM color_assignments WHERE id=? AND origin='historical'", (assignment,)).fetchone()
            if old is None or (old["poster"] != assignment and old["poster"] != poster):
                raise Conflict("Historical identity already mapped or absent")
            db.execute("UPDATE color_assignments SET poster=? WHERE id=?", (poster, assignment))
            self.store.event(db, "historical_logical_identity", assignment, {"poster": poster, "hex": old["hex"]})

    def _authorized(self, reviewer, reason):
        if reviewer not in self.authorized_reviewers or not isinstance(reason, str) or not reason.strip():
            raise BulkError("unauthorized_override", "Authorized reviewer identity and nonempty justification required")

    def relationship(self, identity, members, *, reviewer, reason, expected_version=None):
        self._authorized(reviewer, reason)
        payload = {"members": sorted(set(members)), "reviewer": reviewer, "reason": reason}
        if len(payload["members"]) < 2:
            raise BulkError("invalid_relationship", "Explicit related reuse needs at least two logical posters")
        return self._record("color_relationships", identity, payload, expected_version)

    def exception(self, identity, *, category, color, affected_ids, reviewer, reason, expected_version=None, active=True):
        self._authorized(reviewer, reason)
        payload = {"category": category, "hex": normalize_hex(color), "affected_ids": sorted(set(affected_ids)),
                   "reviewer": reviewer, "reason": reason, "policy": self.policy.fingerprint, "policy_version": self.policy.version,
                   "active": active, "time": self.store.clock()}
        if len(payload["affected_ids"]) < 2 or type(active) is not bool:
            raise BulkError("invalid_exception", "A named exception must enumerate affected logical posters")
        return self._record("color_exceptions", identity, payload, expected_version)

    def _record(self, table, identity, payload, expected_version):
        with self.store.transaction() as db:
            old = db.execute(f"SELECT version FROM {table} WHERE id=?", (identity,)).fetchone()
            if (old["version"] if old else None) != expected_version:
                raise Conflict()
            version = old["version"] + 1 if old else 0
            db.execute(f"INSERT OR REPLACE INTO {table} VALUES (?,?,?)", (identity, version, canonical(payload).decode()))
            self.store.event(db, table, identity, {"version": version, **payload})
        return version

    def _evaluate(self, db, poster, category, color, relationship=None, exception=None):
        color = normalize_hex(color)
        if category not in CATEGORIES or category == "Overlays" or not isinstance(poster, str) or not poster:
            raise BulkError("invalid_assignment", "A logical poster and category are required")
        rows = [dict(row) for row in db.execute("SELECT poster,category,hex FROM color_assignments")]
        rows.extend(dict(row) for row in db.execute("SELECT poster,category,hex FROM color_reservations WHERE expires>?", (self.store.clock(),)))
        rows = [dict(poster=poster_id, category=cat, hex=value) for poster_id, cat, value in sorted({(r["poster"], r["category"], r["hex"]) for r in rows}) if poster_id != poster]
        group = db.execute("SELECT * FROM color_relationships WHERE id=?", (relationship,)).fetchone() if relationship else None
        related = set(json.loads(group["payload"])["members"]) if group else set()
        allowed = db.execute("SELECT * FROM color_exceptions WHERE id=?", (exception,)).fetchone() if exception else None
        permit = json.loads(allowed["payload"]) if allowed else {}
        valid_exception = permit.get("active") is True and permit.get("policy") == self.policy.fingerprint and permit.get("category") == category and permit.get("hex") == color and poster in permit.get("affected_ids", [])
        diagnostics, blocked = [], []
        for row in rows:
            owner = row["poster"]
            linked = poster in related and owner in related
            if row["hex"] == color:
                if linked:
                    continue
                if row["category"] != category:
                    diagnostics.append(Diagnostic("cross_category_exact", "info", "Exact HEX is allowed across categories", (poster, owner), {"hex": color, "category": row["category"]}))
                elif valid_exception and owner in permit["affected_ids"]:
                    diagnostics.append(Diagnostic("approved_exception", "info", "Authorized named color exception", (poster, owner), {"exception": exception, "record": permit}))
                else:
                    blocked.append(owner)
            else:
                distance = delta_e_2000(lab(color), lab(row["hex"]))
                if distance < self.policy.near_threshold:
                    diagnostics.append(Diagnostic("similar_color", "warning", "Perceptually similar color; advisory only", (poster, owner),
                        {"hex": row["hex"], "distance": distance, "threshold": self.policy.near_threshold, "policy_version": self.policy.version}))
        if blocked:
            diagnostics.insert(0, Diagnostic("category_exact_collision", "error", "New unrelated poster requires another exact HEX or authorized exception", (poster, *blocked), {"hex": color, "category": category}))
        if relationship and group is None or exception and not valid_exception:
            diagnostics.insert(0, Diagnostic("invalid_color_permission", "error", "Relationship/exception is missing, stale or invalid", (poster,)))
        return {"allowed": not any(d.severity == "error" for d in diagnostics), "hex": color, "policy": self.policy.fingerprint,
                "relationship_version": group["version"] if group else None, "exception_version": allowed["version"] if allowed else None,
                "diagnostics": [d.to_dict() for d in diagnostics]}

    def evaluate(self, poster, category, color, *, relationship=None, exception=None):
        with self.store.connection() as db:
            return self._evaluate(db, poster, category, color, relationship, exception)

    def reserve(self, poster, category, color, *, owner, relationship=None, exception=None, origin="independent", parent=None, lease_seconds=300):
        if not owner or type(lease_seconds) is not int or lease_seconds <= 0 or origin not in {"independent", "inherited", "template"}:
            raise BulkError("invalid_reservation", "Invalid owner, origin or lease")
        with self.store.transaction() as db:
            if origin in {"inherited", "template"}:
                parent_row = db.execute("SELECT hex FROM color_assignments WHERE id=?", (parent,)).fetchone()
                if not parent_row or parent_row["hex"] != normalize_hex(color):
                    raise BulkError("invalid_parent", "Inherited/template origin requires an exact parent assignment")
            result = self._evaluate(db, poster, category, color, relationship, exception)
            if not result["allowed"]:
                raise BulkError("color_collision", "Category exact collision or invalid explicit permission")
            identity = uuid.uuid4().hex
            payload = {"relationship": relationship, "exception": exception, "origin": origin, "parent": parent,
                       "policy": self.policy.fingerprint, "relationship_version": result["relationship_version"], "exception_version": result["exception_version"]}
            db.execute("INSERT INTO color_reservations VALUES (?,?,?,?,?,?,?)", (identity, poster, category, result["hex"], owner, self.store.clock() + lease_seconds, canonical(payload).decode()))
            self.store.event(db, "color_reserved", identity, {"poster": poster, "category": category, "hex": result["hex"], **payload})
        return {"id": identity, "owner": owner, **result}

    def approve(self, reservation_id, *, owner, reviewer, reason):
        self._authorized(reviewer, reason)
        with self.store.transaction() as db:
            row = db.execute("SELECT * FROM color_reservations WHERE id=?", (reservation_id,)).fetchone()
            if row is None or row["owner"] != owner or row["expires"] <= self.store.clock():
                raise Conflict("Reservation is absent, expired or not owned")
            payload = json.loads(row["payload"])
            result = self._evaluate(db, row["poster"], row["category"], row["hex"], payload["relationship"], payload["exception"])
            if not result["allowed"] or any(payload[key] != result[key] for key in ("policy", "relationship_version", "exception_version")):
                raise Conflict("Color policy/permission changed after reservation")
            assignment = "selected:" + fingerprint({"poster": row["poster"], "category": row["category"], "hex": row["hex"]})[:32]
            source = {**payload, "reviewer": reviewer, "reason": reason, "policy_version": self.policy.version}
            old = db.execute("SELECT * FROM color_assignments WHERE id=?", (assignment,)).fetchone()
            if old is None:
                db.execute("INSERT INTO color_assignments VALUES (?,?,?,?,?,?,?)", (assignment, row["poster"], row["category"], row["hex"], payload["origin"], canonical(source).decode(), self.policy.fingerprint))
            db.execute("DELETE FROM color_reservations WHERE id=?", (reservation_id,))
            self.store.event(db, "color_approved", assignment, {"hex": row["hex"], "poster": row["poster"], **source})
        return assignment

    def assignments(self):
        with self.store.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM color_assignments ORDER BY id")]


def _logo_bytes(path):
    path = reject_links(path)
    with path.open("rb") as stream:
        data = stream.read(30_000_001)
    if len(data) > 30_000_000:
        raise BulkError("invalid_image", "Palette source exceeds byte limit")
    return data


def _palette_data(data):
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(BytesIO(data)) as source:
            if source.width * source.height > 24_000_000 or getattr(source, "n_frames", 1) != 1:
                raise BulkError("invalid_image", "Palette requires a bounded single-frame image")
            image = source.convert("RGBA")
            image.thumbnail((96, 96), Image.Resampling.NEAREST)
    counts = {}
    for r, g, b, alpha in image.getdata():
        if alpha:
            bucket = (r // 16, g // 16, b // 16)
            count, totals = counts.get(bucket, (0, [0, 0, 0]))
            counts[bucket] = (count + alpha, [total + value * alpha for total, value in zip(totals, (r, g, b))])
    colors = [(weight, "#" + bytes(round(total / weight) for total in totals).hex().upper()) for weight, totals in counts.values()]
    return [color for _, color in sorted(colors, key=lambda item: (-item[0], item[1]))[:8]]


def palette(path):
    return _palette_data(_logo_bytes(path))


def suggest_colors(path, registry, poster, category, *, text_color="#FFFFFF", relationship=None, exception=None, limit=8):
    data = _logo_bytes(path)
    visible = _palette_data(data)
    if not visible:
        return {"status": "review_required", "reason": "Logo contains no visible pixels", "candidates": [], "approved": False}
    candidates = set()
    for color in visible:
        hue, _, saturation = colorsys.rgb_to_hls(*(channel / 255 for channel in rgb(color)))
        for shift in (0, .5, -.08, .08):
            for lightness in (.18, .28, .4):
                values = colorsys.hls_to_rgb((hue + shift) % 1, lightness, max(.25, min(.75, saturation)))
                candidates.add("#" + bytes(round(value * 255) for value in values).hex().upper())
    ranked = []
    with registry.store.connection() as db:
        db.execute("BEGIN")
        snapshot = {table: [tuple(row) for row in db.execute("SELECT * FROM " + table + " ORDER BY id")] for table in
                    ("color_assignments", "color_relationships", "color_exceptions", "color_reservations")}
        registry_fingerprint = fingerprint(snapshot)
        for color in sorted(candidates):
            result = registry._evaluate(db, poster, category, color, relationship, exception)
            if not result["allowed"]:
                continue
            readability = contrast(color, text_color)
            visibility = min(delta_e_2000(lab(color), lab(item)) for item in visible)
            diagnostics = list(result["diagnostics"])
            if readability < registry.policy.readability_threshold:
                diagnostics.append(Diagnostic("low_contrast", "warning", "Base/text contrast is low; final gradient/layout requires later verification", (poster,),
                    {"ratio": readability, "threshold": registry.policy.readability_threshold}).to_dict())
            score = round(readability + visibility / 10 - sum(d["severity"] == "warning" for d in diagnostics), 8)
            ranked.append({"hex": color, "score": score, "contrast": readability, "logo_distance": visibility,
                           "diagnostics": diagnostics, "approved": False})
    ranked.sort(key=lambda item: (-item["score"], item["hex"]))
    return {"status": "suggested" if ranked else "review_required", "approved": False, "policy": registry.policy.fingerprint,
            "logo_sha256": hashlib.sha256(data).hexdigest(), "registry_fingerprint": registry_fingerprint,
            "palette": visible, "algorithm": "alpha-weighted-palette-v1", "candidates": ranked[:limit]}
