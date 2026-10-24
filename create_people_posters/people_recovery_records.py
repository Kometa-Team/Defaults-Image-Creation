"""Closed recovery outcomes, per-person checkpoints and orchestrator receipts.

These are local operational records, not publication or authentication grants.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from create_people_posters.people_diagnostics import Diagnostic, sanitize_data, sanitize_text
from create_people_posters.people_workspaces import atomic_json, reject_links

STATUSES = {"recovered", "exhausted", "unresolved", "error", "staged", "audit", "skipped"}
COUNTS = {"attempts", "grayscale_colorized", "grayscale_rejected", "precheck_rejected"}
TEXT = {"name", "status", "chosen_label", "chosen_url", "initial_issues", "final_issues", "precheck_metrics", "final_metrics", "note"}
FIELDS = COUNTS | TEXT | {"diagnostic"}
HEX = re.compile(r"[0-9a-f]{64}")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                                     separators=(",", ":")).encode()).hexdigest()


def row_data(row):
    result = {key: getattr(row, key) for key in TEXT | COUNTS}
    result["diagnostic"] = row.diagnostic.to_dict() if type(row.diagnostic) is Diagnostic else None
    result = sanitize_data(result)
    validate_row(result)
    return result


def validate_row(value):
    if (type(value) is not dict or set(value) != FIELDS or value["status"] not in STATUSES
            or any(type(value[k]) is not int or value[k] < 0 for k in COUNTS)
            or any(type(value[k]) is not str for k in TEXT)):
        raise ValueError("Invalid recovery outcome record")
    if value["diagnostic"] is not None:
        Diagnostic.from_dict(value["diagnostic"])
    if sanitize_data(value) != value:
        raise ValueError("Unsafe recovery outcome record")
    return value


def retryable(value):
    validate_row(value)
    return value["status"] == "unresolved" and value["diagnostic"] is not None and value["diagnostic"]["retryable"]


def status_code(rows):
    if any(r["status"] == "error" for r in rows):return 2
    if any(r["status"] == "unresolved" and not retryable(r) for r in rows):return 1
    if any(retryable(r) for r in rows):return 3
    return 0


def context(args):
    keys = ("bg_engine", "recover_warnings", "report_edges", "retry_edges", "threshold",
            "coverage_threshold", "precheck_threshold", "precheck_coverage_threshold", "precheck_rembg",
            "rembg_model", "reject_grayscale", "colorize_grayscale", "grayscale_sat_threshold",
            "grayscale_sat_quantile", "grayscale_colorfulness_cutoff", "inline",
            "face_crop_side_margin", "face_crop_chin_margin", "tmdb_limit",
            "rembg_alpha_matting", "rembg_post_process_mask")
    values = {key: getattr(args, key, None) for key in keys}
    values["roots"] = {key: hashlib.sha256(str(Path(getattr(args, key)).resolve()).encode()).hexdigest()
                       for key in ("people_root", "transparent_root", "downloads_dir")}
    values["scan_root"] = hashlib.sha256(str(Path(getattr(args, "scan_people_root", args.people_root)).resolve()).encode()).hexdigest()
    from orchestrator import background_fingerprint
    from poster_renderer import poster_fingerprint
    values["background"] = background_fingerprint()
    values["renderer"] = poster_fingerprint()
    # JSON-safe fixed settings only; runtime credentials/config/env never enter.
    return digest(values)


def _read(path):
    reject_links(path)
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Recovery metadata budget exceeded")
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except (ValueError, OSError):
        raise ValueError("Recovery state is unreadable; local artwork retained") from None


class Checkpoints:
    def __init__(self, path, args):
        self.path, self.root, self.context = Path(path), Path(args.people_root).resolve(), context(args)
        self.value = {"schema_version": 1, "kind": "people-recovery-checkpoints", "records": {}}
        if self.path.exists():
            value = _read(self.path)
            if (type(value) is not dict or set(value) != {"schema_version", "kind", "records", "sha256"}
                    or value["schema_version"] != 1 or value["kind"] != self.value["kind"]
                    or value["sha256"] != digest({k: v for k, v in value.items() if k != "sha256"})
                    or type(value["records"]) is not dict or len(value["records"]) > 10000):
                raise ValueError("Recovery checkpoints are corrupt; local artwork retained")
            self.value = {k: v for k, v in value.items() if k != "sha256"}
            for key, record in value["records"].items():
                if type(key) is not str or set(record) != {"context_sha256", "outcome", "outputs"}:
                    raise ValueError("Invalid recovery checkpoint membership")
                if not HEX.fullmatch(record["context_sha256"]):raise ValueError("Invalid recovery context")
                validate_row(record["outcome"])
                if key != record["outcome"]["name"]:raise ValueError("Recovery identity mismatch")
                self._validate_outputs(record["outputs"])

    def _validate_outputs(self, outputs):
        if type(outputs) is not dict or len(outputs) > 64:
            raise ValueError("Invalid recovery output membership")
        for name, checksum in outputs.items():
            relative = Path(name)
            if (type(name) is not str or relative.is_absolute() or ".." in relative.parts
                    or "\\" in name or not HEX.fullmatch(checksum)):
                raise ValueError("Unsafe recovery output record")
            target = self.root / relative
            if not target.resolve().is_relative_to(self.root):raise ValueError("Recovery output escaped its root")
            reject_links(target)

    def completed(self, name):
        record = self.value["records"].get(name)
        if not record or record["context_sha256"] != self.context or record["outcome"]["status"] != "recovered":
            return None
        if not record["outputs"]:
            raise ValueError("Recovered checkpoint has no retained output evidence")
        for relative, expected in record["outputs"].items():
            path = self.root / relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("Recovered checkpoint output changed; operator review required")
        return record["outcome"]

    def validate_retained(self):
        # A missing artifact must not disappear from validation merely because
        # target discovery can no longer find the corresponding image.
        for name in self.value["records"]:
            self.completed(name)

    def save(self, row, paths):
        value = row_data(row)
        if value["name"] != row.name:
            raise ValueError("Sensitive identity cannot be persisted")
        outputs = {}
        if row.status == "recovered":
            for path in paths:
                path = Path(path)
                if path.is_file():
                    reject_links(path)
                    relative = path.resolve().relative_to(self.root).as_posix()
                    outputs[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        self._validate_outputs(outputs)
        if row.status == "recovered" and not outputs:
            raise ValueError("Recovered checkpoint requires retained output evidence")
        self.value["records"][row.name] = dict(context_sha256=self.context, outcome=value, outputs=outputs)
        payload = self.value | {"sha256": digest(self.value)}
        if sanitize_data(payload) != payload:
            raise ValueError("Sensitive recovery state cannot be persisted")
        atomic_json(self.path, payload)


def summary(rows, *, run_id, context_sha256, changed_names=()):
    if type(run_id) is not str or not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise ValueError("Invalid recovery run identity")
    if not HEX.fullmatch(context_sha256):raise ValueError("Invalid recovery context identity")
    outcomes = [row_data(r) for r in rows]
    names = [r["name"] for r in outcomes if r["name"]]
    changed = list(changed_names)
    if len(names) != len(set(names)) or len(changed) != len(set(changed)) or not set(changed) <= set(names):
        raise ValueError("Invalid recovery membership")
    if any(r["status"] != "recovered" for r in outcomes if r["name"] in changed):
        raise ValueError("Changed recovery membership was not accepted")
    payload = dict(schema_version=1, kind="people-recovery-summary", run_id=run_id,
                   context_sha256=context_sha256, exit_code=status_code(outcomes), rows=outcomes,
                   retry_names=[r["name"] for r in outcomes if retryable(r)], changed_names=changed)
    return payload | {"sha256": digest(payload)}


def read_summary(path, *, run_id):
    value = _read(Path(path))
    fields = {"schema_version", "kind", "run_id", "context_sha256", "exit_code", "rows", "retry_names", "changed_names", "sha256"}
    if (type(value) is not dict or set(value) != fields or value["schema_version"] != 1
            or value["kind"] != "people-recovery-summary" or value["run_id"] != run_id
            or value["sha256"] != digest({k: v for k, v in value.items() if k != "sha256"})
            or not HEX.fullmatch(value["context_sha256"]) or type(value["rows"]) is not list):
        raise ValueError("Missing, stale or invalid recovery summary")
    for row in value["rows"]:validate_row(row)
    if (value["exit_code"] != status_code(value["rows"])
            or value["retry_names"] != [r["name"] for r in value["rows"] if retryable(r)]
            or len(value["changed_names"]) != len(set(value["changed_names"]))
            or not set(value["changed_names"]) <= {r["name"] for r in value["rows"] if r["status"] == "recovered"}):
        raise ValueError("Recovery summary contradicts its outcomes")
    return value
