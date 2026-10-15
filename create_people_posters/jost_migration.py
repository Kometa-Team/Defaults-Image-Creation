"""Read-only source inventory and isolated, receipt-backed Jost maintenance jobs."""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import time
import uuid

from PIL import Image

from create_people_poster import (DIIIVOY_POINT_SIZE, FONTS, SIZE, Renderer, digest, resource_dirs,
                                  normalize_cutout, output_path, renderer_fingerprint,
                                  shifted_cutout)
from people_github import GitHubClient, GitHubError
from people_publication_state import PublicationState
from people_remote_inventory import RemoteInventory, blob_sha, path_key
from people_workspaces import ID_PATTERN, atomic_json, process_alive, reject_links
from publish_people_github import Publisher
from sync_people_images import image_quality_findings

STYLES = ("diiivoy", "diiivoycolor")
TARGETS = {style: "Kometa-Team/People-Images-" + style for style in STYLES}
BRANCH = "master"
DEFAULT_ROOT = Path(__file__).resolve().parent / "config/migrations/jost"
APPROVED_FONT = "564a838df86d075f9ab39e0d1f4cfe4ef90791388988dc8b5fc732f75d1ef8f5"


def migration_fingerprint():
    script = Path(__file__).resolve().parent
    assets, fonts = resource_dirs()
    if assets.resolve() != (script / "assets/people").resolve() or fonts.resolve() != (script / "fonts").resolve():
        raise ValueError("Migration requires bundled assets/fonts, not POSTER_ASSET_DIR/POSTER_FONT_DIR overrides")
    if DIIIVOY_POINT_SIZE != 190 or digest(fonts / FONTS[2]) != APPROVED_FONT:
        raise ValueError("Migration requires the approved bundled Jost 260 font and 190px preferred size")
    return renderer_fingerprint()


def identifier():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S-") + uuid.uuid4().hex[:12]


def json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def disjoint(first, second):
    return first != second and first not in second.parents and second not in first.parents


def safe_relative(value):
    path_key(value)
    return PurePosixPath(value)


def protect_source(value, workspace):
    if not value:
        raise ValueError("Set JOST_MIGRATION_TRANSPARENT_DIR to the existing local transparent collection")
    raw = Path(value).expanduser().absolute()
    reject_links(raw)
    root = raw.resolve()
    if not disjoint(root, Path(workspace).absolute().resolve()):
        raise ValueError("Transparent source and migration workspace must be disjoint")
    return root


def source_root(value, workspace):
    root = protect_source(value, workspace)
    if not root.is_dir():
        raise ValueError(f"Local transparent directory does not exist: {root}")
    return root


def scan_sources(root, exclude_ambiguous=False):
    rows, names, paths, ignored = [], {}, {}, []
    for initial in sorted(root.iterdir(), key=lambda p: p.name):
        if initial.name.startswith("."):
            continue
        reject_links(initial)
        if not initial.is_dir():
            continue
        directory = initial / "Images"
        if not directory.exists():
            continue
        reject_links(directory)
        for source in sorted(directory.iterdir(), key=lambda p: p.name):
            reject_links(source)
            if not source.is_file():
                raise ValueError(f"Unexpected nested directory in source Images: {source}")
            relative = source.relative_to(root).as_posix()
            safe_relative(relative)
            if source.suffix.lower() != ".png":
                ignored.append({"path": relative, "reason": "not a PNG source"})
                continue
            name = source.stem
            clean = name.replace("_ccexpress", "")
            destination = output_path(Path("."), STYLES[0], clean).relative_to(STYLES[0]).as_posix()
            error = ""
            for key, catalog, label in ((path_key(name), names, "person filename"), (path_key(destination), paths, "destination")):
                if key in catalog:
                    error = f"Ambiguous Unicode/case {label}: {catalog[key]} and {relative}"
                    if not exclude_ambiguous:
                        raise ValueError(error)
                    for previous in rows:
                        if previous["relative"] == catalog[key]:
                            previous["source_error"] = error
                    print("[EXCLUDED] " + error, flush=True)
                catalog[key] = relative
            rows.append({"relative": relative, "name": name, "source_hash": "",
                         "size": source.stat().st_size, "source_mtime_ns": source.stat().st_mtime_ns,
                         "destination": destination, "source_error": error})
    if not rows:
        raise ValueError("No transparent PNGs found under INITIAL/Images; source collection is empty")
    rows.sort(key=lambda row: (path_key(row["relative"]), row["relative"]))
    def hash_source(row):
        source = root / Path(*PurePosixPath(row["relative"]).parts)
        reject_links(source)
        return digest(source)
    # Two bounded hashing workers; rendering/decoding remains single-person.
    with ThreadPoolExecutor(max_workers=2) as pool:
        for offset in range(0, len(rows), 32):
            group = rows[offset:offset+32]
            for index, (row, sha) in enumerate(zip(group, pool.map(hash_source, group)), offset):
                row["number"], row["source_hash"] = index, sha
                if (index + 1) % 500 == 0:
                    print(f"[SCAN] Hashed {index + 1} local PNGs", flush=True)
    return rows, ignored


def sample_numbers(rows, count):
    """Name diversity plus evenly spaced letters; image characteristics audited at render."""
    if count < 1:
        raise ValueError("Sample size must be positive")
    selected = []
    orders = [sorted(rows, key=lambda r: len(r["name"])),
              sorted(rows, key=lambda r: -len(r["name"])),
              [r for r in rows if not r["name"].isascii()],
              [r for r in rows if any(c in r["name"] for c in "-'.,()")],
              [r for r in rows if r["name"][-1:].isdigit()],
              [r for r in rows if any(c.islower() for c in r["name"]) and any(c.isupper() for c in r["name"])]]
    for order in orders:
        for row in order[:max(1, count // 6)]:
            if row["number"] not in selected and len(selected) < count:
                selected.append(row["number"])
    for index in range(min(count, len(rows))):
        number = rows[round(index * (len(rows) - 1) / max(1, min(count, len(rows)) - 1))]["number"]
        if number not in selected and len(selected) < count:
            selected.append(number)
    for row in rows:
        if len(selected) >= count:
            break
        if row["number"] not in selected:
            selected.append(row["number"])
    return set(selected)


class MigrationTransport:
    """Hard production allowlist, independent of configurable normal-pipeline targets."""

    def __init__(self, client, writes=False, allowed=None, on_commit=None):
        self.client = client
        self.writes = writes
        self.allowed = allowed or {}
        self.sandbox = None
        self.parents = {}
        self.trees = {}
        self.on_commit = on_commit

    def request(self, method, path, payload=None):
        if method != "GET" and not isinstance(payload, dict):
            raise ValueError("Migration writes require a structured payload")
        match = re.fullmatch(r"/repos/(Kometa-Team/People-Images-(?:diiivoy|diiivoycolor))(/.*)?", path)
        if not match or "\\" in path or "%" in path or any(p in {".", "..", ""} for p in path[1:].split("/")):
            raise ValueError("Jost migration transport blocked a non-allowlisted repository/path")
        repo, route = match.group(1), (match.group(2) or "").lstrip("/")
        if method == "GET":
            if not (not route or route == "git/ref/heads/master" or re.fullmatch(
                    r"git/(?:commits|blobs)/[0-9a-f]{40}|git/trees/[0-9a-f]{40}(?:\?recursive=1)?|compare/[0-9a-f]{40}\.\.\.[0-9a-f]{40}", route)):
                raise ValueError("Jost migration blocked an unexpected read route or branch")
        else:
            if not self.writes:
                raise ValueError("Read-only migration operation blocked a GitHub mutation")
            valid = method == "POST" and route in {"git/blobs", "git/trees", "git/commits", "actions/workflows/readme.yml/dispatches"}
            valid |= method == "PATCH" and route == "git/refs/heads/master" and payload.get("force") is False
            if not valid:
                raise ValueError("Jost migration blocked an unexpected write route/branch or force-push")
            if route == "git/trees":
                if not payload.get("base_tree") or not payload.get("tree"):
                    raise ValueError("Migration trees must preserve an existing base tree")
                for entry in payload["tree"]:
                    key = (repo, entry["path"])
                    if (key not in self.allowed or entry.get("sha") != self.allowed[key]
                            or entry.get("mode") != "100644" or entry.get("type") != "blob"):
                        raise ValueError("Tree write differs from the approved migration manifest")
            if route.endswith("dispatches") and payload != {"ref": BRANCH}:
                raise ValueError("README dispatch must target master")
            if route == "git/commits" and (len(payload.get("parents", [])) != 1 or payload.get("tree") not in self.trees):
                raise ValueError("Migration commits require one existing parent and an approved migration tree")
            if method == "PATCH":
                parent = self.parents.get(payload.get("sha"))
                if not parent:
                    raise ValueError("Ref update must use a commit created from this approved migration tree")
                latest, _ = self.client.head(repo, BRANCH)
                if latest != parent:
                    raise GitHubError("Branch advanced immediately before publication; refresh and retry",409)
        result = self.client.request(method, path, payload)
        if method == "POST" and route == "git/trees":
            self.trees[result["sha"]] = [entry["path"] for entry in payload["tree"]]
        if method == "POST" and route == "git/commits":
            self.parents[result["sha"]] = payload["parents"][0]
            if self.on_commit:
                self.on_commit(repo, self.trees[payload["tree"]], result["sha"])
        return result

    def head(self, repo, branch):
        if branch != BRANCH or repo not in TARGETS.values():
            raise ValueError("Migration targets only the two Diiivoy master branches")
        return self.client.head(repo, branch)


class Migration:
    def __init__(self, root=DEFAULT_ROOT, client=None, source_dir=None):
        self.root = Path(root).expanduser().absolute()
        reject_links(self.root)
        self.root = self.root.resolve()
        configured_source = source_dir or os.getenv("JOST_MIGRATION_TRANSPARENT_DIR")
        if configured_source:
            protect_source(configured_source, self.root)
        if (self.root / ".git").exists() or (self.root.is_dir() and any(
                p.is_dir() and (p / "Images").is_dir() for p in self.root.iterdir())):
            raise ValueError("An existing image collection/Git checkout cannot be a migration workspace")
        self.ledger = PublicationState(self.root / "state")
        self.db = self.ledger.db
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS jost_runs(id TEXT PRIMARY KEY, manifest_hash TEXT, created REAL);
          CREATE TABLE IF NOT EXISTS jost_items(mid TEXT, number INTEGER, status TEXT, error TEXT,
            metrics TEXT, PRIMARY KEY(mid,number));
          CREATE TABLE IF NOT EXISTS jost_outputs(mid TEXT, number INTEGER, style TEXT, state TEXT,
            sha256 TEXT, blob TEXT, commit_sha TEXT, updated REAL, error TEXT,
            rollback_state TEXT, rollback_commit TEXT, PRIMARY KEY(mid,number,style));
          CREATE TABLE IF NOT EXISTS jost_units(mid TEXT, id TEXT PRIMARY KEY, numbers TEXT,
            verified REAL, cleaned INTEGER DEFAULT 0);
          CREATE TABLE IF NOT EXISTS jost_rollback_readmes(mid TEXT, style TEXT, status TEXT, error TEXT,
            PRIMARY KEY(mid,style));
          CREATE TABLE IF NOT EXISTS jost_timings(mid TEXT, operation TEXT, started REAL, seconds REAL, items INTEGER);
          CREATE TABLE IF NOT EXISTS jost_writes(mid TEXT, unit TEXT, repo TEXT, path TEXT, commit_sha TEXT,
            PRIMARY KEY(mid,unit,repo,path,commit_sha));
          CREATE TABLE IF NOT EXISTS jost_quarantines(mid TEXT, unit TEXT PRIMARY KEY, error TEXT, created REAL);
        """)
        self.db.commit()
        self._client = client
        self.inventory = None

    def close(self):
        if self.inventory:
            self.inventory.close()
        self.ledger.close()

    @contextmanager
    def lock(self):
        path = self.root / "state/migration.lock"
        reject_links(path)
        if path.exists():
            old = json.loads(path.read_text(encoding="utf-8"))
            if process_alive(old["pid"]):
                raise ValueError("Another migration command is active")
            path.unlink()
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid()}, handle)
        try:
            yield
        finally:
            path.unlink(missing_ok=True)

    def remote(self):
        if self.inventory is None:
            if os.getenv("PEOPLE_GITHUB_TARGET", "production") != "production" or os.getenv("PEOPLE_SANDBOX_CONFIG"):
                raise ValueError("This migration has fixed production targets; sandbox overrides are not accepted")
            transport = MigrationTransport(self._client or GitHubClient())
            self.inventory = RemoteInventory(transport, self.root / "state/inventory.db", BRANCH)
            self.inventory.repositories = dict(TARGETS)
        return self.inventory

    def job(self, mid):
        if not ID_PATTERN.fullmatch(mid):
            raise ValueError("Invalid migration identifier")
        path = self.root / "jobs" / mid
        reject_links(path)
        return path

    def load(self, mid, current=True):
        path = self.job(mid) / "manifest.json"
        reject_links(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        row = self.db.execute("SELECT * FROM jost_runs WHERE id=?", (mid,)).fetchone()
        if (not row or data.get("managed_by") != "kometa-jost-v1" or data.get("id") != mid
                or data.get("targets") != TARGETS or data.get("branch") != BRANCH
                or json_hash(data) != row["manifest_hash"]):
            raise ValueError("Migration manifest integrity/target check failed; preserve it for reconciliation")
        (source_root if current else protect_source)(data["source_root"], self.root)
        if current and data["renderer"] != migration_fingerprint():
            raise ValueError("Renderer/font fingerprint changed; do not reuse outputs. Reconcile with a new --scan migration")
        return data

    def source(self, manifest, item):
        root = source_root(manifest["source_root"], self.root)
        relative = safe_relative(item["relative"])
        if len(relative.parts) != 3 or relative.parts[1] != "Images" or relative.suffix.lower() != ".png":
            raise ValueError("Unexpected source layout in migration manifest")
        path = root.joinpath(*relative.parts)
        reject_links(path)
        if not path.is_file() or digest(path) != item["source_hash"]:
            raise ValueError("Local source missing/changed since scan; preserve this migration and reconcile with a new --scan")
        return path

    def target(self, mid, item, style):
        if style not in TARGETS:
            raise ValueError("Only Diiivoy styles are allowed")
        relative = safe_relative(item["destination"])
        expected = output_path(Path("."), style, item["name"].replace("_ccexpress", "")).relative_to(style).as_posix()
        if relative.as_posix() != expected:
            raise ValueError("Destination differs from the canonical migration manifest path")
        path = self.job(mid) / style / Path(*relative.parts)
        reject_links(path)
        return path

    def scan(self, source, sample=None, exclude_ambiguous=False):
        root = source_root(source, self.root)
        fingerprint = migration_fingerprint()
        rows, ignored = scan_sources(root, exclude_ambiguous)
        inventory = self.remote()
        heads = {style: inventory.refresh(style) for style in STYLES}
        safe_rows = [row for row in rows if not row["source_error"]]
        selected = sample_numbers(safe_rows, sample) if sample else {row["number"] for row in safe_rows}
        missing = []
        previous_renderers = {}
        destinations = {path_key(row["destination"]) for row in rows}
        for row in rows:
            row["selected"] = row["number"] in selected
            row["destinations"] = {}
            for style in STYLES:
                entry = inventory.lookup(style, row["destination"])
                if entry and (entry["path"] != row["destination"] or entry["mode"] != "100644" or entry["type"] != "blob"):
                    raise ValueError(f"Ambiguous/nonordinary destination: {style}/{row['destination']}")
                sha = entry["sha"] if entry else None
                proofs = self.db.execute("""SELECT DISTINCT u.mid FROM publications p JOIN jost_units u ON u.id=p.batch
                    JOIN jost_outputs o ON o.mid=u.mid AND o.style=p.style AND o.blob=p.blob
                    WHERE p.repo=? AND p.path=? AND p.blob=? AND p.source_hash=? AND p.status='published'
                    AND u.verified IS NOT NULL AND o.rollback_state!='rolled_back'""",
                    (TARGETS[style], row["destination"], sha, row["source_hash"])).fetchall() if sha else []
                proof = False
                for previous in proofs:
                    if previous["mid"] not in previous_renderers:
                        previous_renderers[previous["mid"]] = self.load(previous["mid"], current=False)["renderer"]
                    if previous_renderers[previous["mid"]] == fingerprint:
                        proof = True
                        break
                row["destinations"][style] = {"repo": TARGETS[style], "path": row["destination"],
                    "previous_blob": sha, "baseline_head": heads[style][0], "exists": bool(entry),
                    "classification": "confirmed_jost" if proof else "unknown"}
            if all(d["classification"] == "confirmed_jost" for d in row["destinations"].values()):
                row["selected"] = False
        for style in STYLES:
            for entry in inventory.images(style):
                if path_key(entry["path"]) not in destinations:
                    missing.append({"style": style, "path": entry["path"], "blob": entry["sha"], "status": "missing_local_source"})
        mid = identifier()
        manifest = {"id": mid, "managed_by": "kometa-jost-v1", "created": time.time(),
                    "source_root": str(root), "targets": TARGETS, "branch": BRANCH,
                    "renderer": fingerprint, "font_hash": APPROVED_FONT,
                    "items": rows, "missing_sources": missing, "ignored_sources": ignored,
                    "sample_numbers": sorted(sample_numbers(safe_rows, min(25, len(safe_rows)))) if safe_rows else [],
                    "exclude_ambiguous": exclude_ambiguous,
                    "selection": "name-diverse/even-letter sample; alpha/image properties audited after selection" if sample else "all sources"}
        atomic_json(self.job(mid) / "manifest.json", manifest)
        with self.db:
            self.db.execute("INSERT INTO jost_runs VALUES(?,?,?)", (mid, json_hash(manifest), time.time()))
            for row in rows:
                self.db.execute("INSERT INTO jost_items VALUES(?,?,?,?, '{}')", (mid, row["number"], "conflict" if row["source_error"] else "discovered", row["source_error"]))
                for style in STYLES:
                    self.db.execute("INSERT INTO jost_outputs VALUES(?,?,?,'discovered','','','',0,'','','')", (mid, row["number"], style))
        self.export(mid)
        return mid

    def items(self, mid, manifest=None):
        manifest = manifest or self.load(mid, current=False)
        statuses = {r["number"]: dict(r) for r in self.db.execute("SELECT * FROM jost_items WHERE mid=?", (mid,))}
        return [dict(row, **{k: v for k, v in statuses[row["number"]].items() if k not in {"mid", "number"}}) for row in manifest["items"]]

    def outputs(self, mid, number=None):
        query = "SELECT * FROM jost_outputs WHERE mid=?" + (" AND number=?" if number is not None else "")
        return [dict(row) for row in self.db.execute(query + " ORDER BY number,style", (mid, number) if number is not None else (mid,))]

    def update_output(self, mid, number, style, **values):
        allowed = {"state", "sha256", "blob", "commit_sha", "error", "rollback_state", "rollback_commit"}
        if not values or set(values) - allowed:
            raise ValueError("Unexpected migration status fields")
        values["updated"] = time.time()
        with self.db:
            self.db.execute("UPDATE jost_outputs SET " + ",".join(key + "=?" for key in values) + " WHERE mid=? AND number=? AND style=?",
                            [*values.values(), mid, number, style])

    def record_commit(self, mid, unit, repo, paths, commit):
        with self.db:
            self.db.executemany("INSERT OR IGNORE INTO jost_writes VALUES(?,?,?,?,?)", [(mid,unit,repo,path,commit) for path in paths])

    def render(self, mid, limit=50, failed_only=False, retry_failed=True):
        manifest = self.load(mid)
        states = {"failed"} if failed_only else {"discovered", "failed"} if retry_failed else {"discovered"}
        pending = [r for r in self.items(mid, manifest) if r["selected"] and r["status"] in states]
        priority = set(manifest["sample_numbers"])
        rows = sorted(pending, key=lambda r: (r["number"] not in priority, r["number"]))[:limit]
        renderer = Renderer()
        started = time.monotonic()
        budget = float(os.getenv("JOST_MIGRATION_MAX_GIB", "10")) * 1024**3
        used = 0
        for directory, dirs, files in os.walk(self.root, followlinks=False):
            for name in dirs + files:
                reject_links(Path(directory) / name)
            used += sum((Path(directory) / name).stat().st_size for name in files)
        for row in rows:
            if (budget > 0 and used >= budget) or shutil.disk_usage(self.root).free < 256*1024**2:
                raise ValueError("Migration storage budget/free-space limit reached; publish/clean verified batches or review retained failures")
            try:
                source = self.source(manifest, row)
                with Image.open(source) as image:
                    if image.format != "PNG" or getattr(image, "n_frames", 1) != 1:
                        raise ValueError("Expected a single-frame transparent PNG")
                    image.load()
                    alpha = image.convert("RGBA").getchannel("A")
                    normalized = normalize_cutout(image)
                    normalized_again = normalize_cutout(normalized)
                    equivalent = normalized.tobytes() == normalized_again.tobytes()
                    metrics = {"source_dimensions": list(image.size), "source_mode": image.mode,
                               "source_bbox": alpha.getbbox(), "normalized_bbox": normalized.getchannel("A").getbbox(),
                               "shifted_bbox": shifted_cutout(normalized).getchannel("A").getbbox(),
                               "normalization_idempotent": equivalent, "intermediate_provenance": "unverified historical PNG; no earlier raw-cutout linkage asserted"}
                    outputs, warnings = renderer.render_styles(image, row["name"].replace("_ccexpress", ""))
                    # Equivalent inputs must produce identical pixels through the shared API.
                    repeated, _ = renderer.render_styles(normalized, row["name"].replace("_ccexpress", ""))
                    metrics["equivalent_outputs"] = all(outputs[s].tobytes() == repeated[s].tobytes() for s in STYLES)
                    metrics["requires_individual_review"] = image.size != SIZE or not equivalent or not metrics["equivalent_outputs"]
                    if not equivalent or not metrics["equivalent_outputs"]:
                        warnings.append("Equivalence unavailable: requires explicit visual review")
                    if image.size != SIZE:
                        warnings.append("Noncanonical source dimensions require individual visual approval")
                    metrics["warnings"] = warnings
                if digest(source) != row["source_hash"]:
                    raise ValueError("Source changed while rendering; reconcile with a new --scan")
                for style, image in outputs.items():
                    target = self.target(mid, row, style)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary = None
                    try:
                        with tempfile.NamedTemporaryFile(prefix=".jost-",suffix=".jpg",dir=target.parent,delete=False) as handle:
                            temporary = Path(handle.name)
                            image.save(handle,"JPEG",quality=100,subsampling=0)
                            handle.flush()
                            os.fsync(handle.fileno())
                        with Image.open(temporary) as check:
                            check.load()
                            if check.format != "JPEG" or check.mode != "RGB" or check.size != SIZE:
                                raise ValueError("Invalid rendered JPEG contract")
                        blocking, notes = image_quality_findings(style,temporary)
                        if blocking:
                            raise ValueError("; ".join(blocking))
                        temporary.replace(target)
                    finally:
                        if temporary is not None:
                            temporary.unlink(missing_ok=True)
                    data = target.read_bytes()
                    used += len(data)
                    self.update_output(mid, row["number"], style, state="validated", sha256=hashlib.sha256(data).hexdigest(), blob=blob_sha(data), error="")
                    metrics["warnings"].extend(notes)
                    image.close()
                with self.db:
                    self.db.execute("UPDATE jost_items SET status='validated',error='',metrics=? WHERE mid=? AND number=?", (json.dumps(metrics), mid, row["number"]))
                print(f"[RENDERED] {row['name']}", flush=True)
            except (OSError, ValueError, Image.DecompressionBombError) as error:
                state = "conflict" if "changed" in str(error) or "missing/changed" in str(error) else "failed"
                with self.db:
                    self.db.execute("UPDATE jost_items SET status=?,error=? WHERE mid=? AND number=?", (state, str(error), mid, row["number"]))
                for style in STYLES:
                    self.update_output(mid, row["number"], style, state=state, error=str(error))
                print(f"[ERROR] {row['name']}: {error}", flush=True)
        with self.db:
            successes = sum(self.db.execute("SELECT status FROM jost_items WHERE mid=? AND number=?", (mid,r["number"])).fetchone()[0] == "validated" for r in rows)
            self.db.execute("INSERT INTO jost_timings VALUES(?,?,?,?,?)", (mid,"render",time.time(),time.monotonic()-started,successes))
        self.export(mid)
        return {"attempted": len(rows), "seconds": round(time.monotonic() - started, 3)}

    def export(self, mid):
        manifest = self.load(mid, current=False)
        rows = self.items(mid, manifest)
        outputs = self.outputs(mid)
        selected = [row for row in rows if row["selected"]]
        status = dict(Counter(row["status"] for row in selected))
        used = 0
        for directory, dirs, files in os.walk(self.job(mid), followlinks=False):
            for name in dirs + files:
                reject_links(Path(directory) / name)
            used += sum((Path(directory) / name).stat().st_size for name in files)
        for output in outputs:
            item = manifest["items"][output["number"]]
            baseline = item["destinations"][output["style"]]
            confirmed = (baseline["classification"] == "confirmed_jost" or bool(output["blob"]) and
                         (output["blob"] == baseline["previous_blob"] or output["state"] == "verified")) and output["rollback_state"] != "rolled_back"
            output.update(repo=baseline["repo"], branch=BRANCH, path=baseline["path"], previous_blob=baseline["previous_blob"], baseline_head=baseline["baseline_head"],
                          source_hash=item["source_hash"], classification="confirmed_jost" if confirmed else baseline["classification"], needs_rebuild=not confirmed)
        classifications = Counter(row["classification"] for row in outputs)
        timings = [dict(row) for row in self.db.execute("SELECT * FROM jost_timings WHERE mid=?",(mid,))]
        result = {"id": mid, "discovered": len(rows), "selected": len(selected), "statuses": status,
                  "outputs": dict(Counter(row["state"] for row in outputs if manifest["items"][row["number"]]["selected"])),
                  "missing_local_destinations": len(manifest["missing_sources"]),
                  "classification": {key: classifications[key] for key in ("confirmed_pre_jost", "confirmed_jost", "unknown")},
                  "workspace_bytes": used, "source_bytes": sum(r["size"] for r in rows),
                  "rendered": sum(row["status"] in {"validated","verified"} for row in selected),
                  "remaining": sum(row["status"] != "verified" for row in selected),
                  "not_selected": len(rows)-len(selected),
                  "skipped": sum(not row["selected"] and all(d["classification"]=="confirmed_jost" for d in row["destinations"].values()) for row in rows),
                  "excluded_conflicts": sum(bool(row.get("source_error")) for row in rows), "timings": timings,
                  "elapsed_seconds": round(time.time() - manifest["created"], 3),
                  "items": rows, "destinations": outputs}
        render_times = [row for row in timings if row["operation"] == "render" and row["items"] > 0]
        measured = sum(row["items"] for row in render_times)
        if measured >= 10:
            seconds = sum(row["seconds"] for row in render_times) / measured
            result["rough_render_workload"] = {"measured_people": measured, "seconds_per_person": round(seconds,3),
                "full_local_collection_seconds": round(seconds*len(rows)),
                "basis": "Two-style render, equivalent-input check, JPEG encoding and QA. Excludes source inventory, review, publishing and startup; sample-dependent, not a completion ETA."}
        atomic_json(self.root / "reports" / mid / "progress.json", result)
        return result

    def review(self, mid, token, approved_sample=None):
        origin = approved_sample or mid
        original = self.load(origin)
        path = self.root / "reports" / origin / "review.json"
        reject_links(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if digest(path) != token or data["renderer"] != migration_fingerprint() or data["migration"] != origin or not data["outputs"]:
            raise ValueError("Visual review token missing/stale; generate --compare and explicitly approve its SHA-256")
        manifest = original
        for number, hashes in data["outputs"].items():
            row = manifest["items"][int(number)]
            self.source(manifest, row)
            for style, sha in hashes.items():
                target = self.target(origin, row, style)
                if not target.is_file():
                    target = self.root / "reports" / origin / "samples" / str(number) / (style + "-jost.jpg")
                    reject_links(target)
                if digest(target) != sha:
                    raise ValueError("Reviewed output changed; regenerate the comparison report")
        if data.get("manifest_hash") != json_hash(manifest):
            raise ValueError("Review belongs to a different immutable manifest")
        if origin != mid:
            current = self.load(mid)
            if current["selection"] != "all sources" or current["renderer"] != original["renderer"]:
                raise ValueError("Approved sample requires a full manifest using the identical renderer")
            by_path = {r["destination"]: r for r in current["items"] if not r["source_error"]}
            mapped = {}
            for number, hashes in data["outputs"].items():
                old = original["items"][int(number)]
                new = by_path.get(old["destination"])
                if not new or old["source_hash"] != new["source_hash"]:
                    raise ValueError("Approved sample source differs from the full manifest")
                receipts = {r["style"]:r for r in self.outputs(origin,int(number))}
                if set(hashes) != set(STYLES) or any(
                        receipts[s]["state"] != "verified" or receipts[s]["rollback_state"] == "rolled_back"
                        or receipts[s]["sha256"] != hashes[s]
                        or new["destinations"][s]["previous_blob"] != receipts[s]["blob"]
                        or new["destinations"][s]["classification"] != "confirmed_jost" for s in STYLES):
                    raise ValueError("Approved sample must still match verified publication receipts and scan baselines")
                mapped[str(new["number"])] = hashes
            data = dict(data, outputs=mapped, approved_sample=origin, full_manifest_hash=json_hash(current))
        return data

    def publish(self, mid, limit=50, batch_size=50, dry_run=True, confirm=None, reviewed=None, approved_sample=None):
        started = time.monotonic()
        manifest = self.load(mid)
        if not dry_run:
            if confirm != mid:
                raise ValueError("Publication requires --confirm MIGRATION_ID")
            review = self.review(mid, reviewed, approved_sample)
        inventory = self.remote()
        units = [dict(row) for row in self.db.execute("""SELECT * FROM jost_units u WHERE mid=? AND verified IS NULL
            AND NOT EXISTS (SELECT 1 FROM jost_quarantines q WHERE q.unit=u.id) ORDER BY id""", (mid,))]
        assigned = {number for row in self.db.execute("SELECT numbers FROM jost_units WHERE mid=?", (mid,)) for number in json.loads(row[0])}
        available = max(0,limit-sum(len(json.loads(unit["numbers"])) for unit in units))
        candidates = [r for r in self.items(mid, manifest) if r["selected"] and r["status"] == "validated" and r["number"] not in assigned][:available]
        for offset in range(0, len(candidates), batch_size):
            numbers = [r["number"] for r in candidates[offset:offset+batch_size]]
            unit = manifest["id"][:16] + json_hash([mid, numbers])[:12]
            units.append({"id": unit, "numbers": json.dumps(numbers), "new": True})
        errors, plans = [], []
        remaining = limit
        for unit in units:
            numbers = json.loads(unit["numbers"])
            if len(numbers) > remaining:
                if remaining == limit:
                    raise ValueError(f"Pending publication unit contains {len(numbers)} people; resume with --limit at least that large")
                break
            remaining -= len(numbers)
            entries, allowed = [], {}
            for number in numbers:
                item = manifest["items"][number]
                metrics = self.db.execute("SELECT metrics FROM jost_items WHERE mid=? AND number=?", (mid, number)).fetchone()
                individual = json.loads(metrics[0]).get("requires_individual_review",True)
                if not dry_run and individual and str(number) not in review["outputs"]:
                    raise ValueError("This entry lacks exact input equivalence and needs its own visually approved comparison")
                source = self.source(manifest, item)
                for row in self.outputs(mid, number):
                    if row["state"] not in {"validated", "verified", "failed", "pending", "attempted", "published"} or row["rollback_state"] == "rolled_back":
                        raise ValueError("Output is not ready for publication")
                    target = self.target(mid, item, row["style"])
                    if not target.is_file() or digest(target) != row["sha256"]:
                        raise ValueError("Validated generated image missing/changed; preserve the migration for reconciliation")
                    style = row["style"]
                    allowed[(TARGETS[style], item["destination"])] = row["blob"]
                    entries.append({"style": style, "repo": TARGETS[style], "path": item["destination"],
                        "source": str(source), "source_hash": item["source_hash"], "prepared": str(target),
                        "published_hash": row["sha256"], "blob": row["blob"], "person": item["name"]})
            transport = MigrationTransport(inventory.client.client, writes=not dry_run, allowed=allowed,
                on_commit=lambda repo, paths, commit: self.record_commit(mid,unit["id"],repo,paths,commit))
            publisher = Publisher(transport, inventory, self.ledger)
            if dry_run:
                for style in STYLES:
                    inventory.refresh(style)
                    for entry in (r for r in entries if r["style"] == style):
                        current = publisher.check_destination(style, entry["path"])
                        item = next(manifest["items"][n] for n in numbers if manifest["items"][n]["destination"] == entry["path"])
                        old = item["destinations"][style]["previous_blob"]
                        sha = current["sha"] if current else None
                        action = "unchanged" if sha == entry["blob"] else "replace" if sha == old and old else "create" if sha is None and old is None else "conflict"
                        plans.append({"style": style, "path": entry["path"], "action": action, "previous": old, "current": sha, "new": entry["blob"]})
                continue
            if unit.get("new"):
                with self.db:
                    self.db.execute("INSERT OR IGNORE INTO jost_units(mid,id,numbers) VALUES(?,?,?)", (mid, unit["id"], unit["numbers"]))
            self.ledger.plan(unit["id"], BRANCH, entries)
            for number in numbers:
                for style in STYLES:
                    item = manifest["items"][number]
                    self.ledger.baseline(unit["id"], TARGETS[style], item["destination"], item["destinations"][style]["previous_blob"])
            try:
                publisher.publish(unit["id"])
            except (GitHubError, ValueError, OSError) as error:
                errors.append(str(error))
            receipts = self.ledger.rows(unit["id"])
            ancestry = {}
            for receipt in receipts:
                item = next(manifest["items"][n] for n in numbers if manifest["items"][n]["destination"] == receipt["path"])
                self.update_output(mid, item["number"], receipt["style"], state="verified" if receipt["status"] == "published" else receipt["status"],
                                   commit_sha=receipt["commit_sha"], error=receipt["error"])
                if receipt["status"] == "published":
                    commits = self.db.execute("SELECT commit_sha FROM jost_writes WHERE mid=? AND unit=? AND repo=? AND path=?",
                        (mid,unit["id"],receipt["repo"],receipt["path"])).fetchall()
                    owned = False
                    for record in commits:
                        key = (receipt["repo"],record[0],receipt["commit_sha"])
                        if record[0] == receipt["commit_sha"]:
                            owned = True
                            break
                        if key not in ancestry:
                            comparison = transport.request("GET", f"/repos/{receipt['repo']}/compare/{record[0]}...{receipt['commit_sha']}")
                            ancestry[key] = comparison.get("status") in {"ahead","identical"}
                        if ancestry[key]:
                            owned = True
                            break
                    if not owned:
                        self.update_output(mid,item["number"],receipt["style"],rollback_state="not_changed")
            if self.ledger.verified(unit["id"]):
                with self.db:
                    self.db.execute("UPDATE jost_units SET verified=? WHERE id=?", (time.time(), unit["id"]))
                    self.db.executemany("UPDATE jost_items SET status='verified' WHERE mid=? AND number=?", [(mid, n) for n in numbers])
            if errors:
                break
        atomic_json(self.root / "reports" / mid / "publication-preview.json", {"dry_run": dry_run, "plans": plans, "errors": errors})
        with self.db:
            self.db.execute("INSERT INTO jost_timings VALUES(?,?,?,?,?)", (mid,"publish_dry_run" if dry_run else "publish",time.time(),time.monotonic()-started,limit-remaining))
        self.export(mid)
        if errors:
            raise GitHubError("Partial migration publication; resume the same migration. " + "; ".join(errors))
        return plans

    def rollback(self, mid, limit=50, batch_size=50, dry_run=True, confirm=None):
        started = time.monotonic()
        manifest = self.load(mid, current=False)
        if not dry_run and confirm != "rollback:" + mid:
            raise ValueError("Rollback requires --confirm rollback:MIGRATION_ID")
        inventory = self.remote()
        plans, errors = [], []
        selected = [r for r in self.outputs(mid) if r["state"] == "verified" and r["rollback_state"] not in {"rolled_back","not_changed"}]
        numbers = set(sorted({r["number"] for r in selected})[:limit])
        for style in STYLES:
            rows = [r for r in selected if r["style"] == style and r["number"] in numbers]
            for offset in range(0, len(rows), batch_size):
                chunk = rows[offset:offset+batch_size]
                for attempt in range(3):
                    head, tree = inventory.refresh(style)
                    updates = []
                    for row in chunk:
                        item = manifest["items"][row["number"]]
                        path = self.target(mid, item, style).relative_to(self.job(mid) / style).as_posix()
                        entry = inventory.lookup(style, path)
                        if entry and (entry["path"] != path or entry["mode"] != "100644" or entry["type"] != "blob"):
                            raise ValueError("Rollback destination is ambiguous or not an ordinary file")
                        current = entry["sha"] if entry else None
                        previous = item["destinations"][style]["previous_blob"]
                        # A prior rollback may have succeeded immediately before a crash.
                        if current == previous:
                            if not dry_run:
                                self.update_output(mid, row["number"], style, rollback_state="rolled_back", rollback_commit=head)
                            continue
                        if current != row["blob"]:
                            raise GitHubError(f"Intervening change blocks rollback: {style}/{path}")
                        updates.append({"path": path, "mode": "100644", "type": "blob", "sha": previous})
                        plans.append({"style": style, "path": path, "current": current, "restore": previous})
                    if dry_run or not updates:
                        break
                    transport = MigrationTransport(inventory.client.client, writes=True,
                        allowed={(TARGETS[style], row["path"]): row["sha"] for row in updates})
                    with self.db:
                        self.db.execute("INSERT OR REPLACE INTO jost_rollback_readmes VALUES(?,?,'pending','')", (mid, style))
                    new_tree = transport.request("POST", f"/repos/{TARGETS[style]}/git/trees", {"base_tree": tree, "tree": updates})
                    commit = transport.request("POST", f"/repos/{TARGETS[style]}/git/commits", {
                        "message": f"chore: restore pre-Jost blobs for {mid} [skip readme]", "tree": new_tree["sha"], "parents": [head]})
                    try:
                        transport.request("PATCH", f"/repos/{TARGETS[style]}/git/refs/heads/master", {"sha": commit["sha"], "force": False})
                    except GitHubError:
                        if attempt == 2:
                            raise
                        continue
                    inventory.refresh(style)
                    for row in chunk:
                        item = manifest["items"][row["number"]]
                        current = inventory.lookup(style, item["destination"])
                        sha = current["sha"] if current else None
                        if sha != item["destinations"][style]["previous_blob"]:
                            raise GitHubError("Rollback verification failed; retain receipts and retry")
                        self.update_output(mid, row["number"], style, rollback_state="rolled_back", rollback_commit=commit["sha"])
                    break
            if not dry_run:
                readme = self.db.execute("SELECT status FROM jost_rollback_readmes WHERE mid=? AND style=?", (mid, style)).fetchone()
                if readme and readme[0] != "dispatched":
                    try:
                        MigrationTransport(inventory.client.client, writes=True).request("POST",
                            f"/repos/{TARGETS[style]}/actions/workflows/readme.yml/dispatches", {"ref": BRANCH})
                        with self.db:
                            self.db.execute("UPDATE jost_rollback_readmes SET status='dispatched',error='' WHERE mid=? AND style=?", (mid, style))
                    except GitHubError as error:
                        with self.db:
                            self.db.execute("UPDATE jost_rollback_readmes SET status='failed',error=? WHERE mid=? AND style=?", (str(error), mid, style))
                        errors.append("Rollback README dispatch needs retry: " + str(error))
        atomic_json(self.root / "reports" / mid / "rollback-preview.json", {"dry_run": dry_run, "plans": plans, "errors": errors})
        with self.db:
            self.db.execute("INSERT INTO jost_timings VALUES(?,?,?,?,?)", (mid,"rollback_dry_run" if dry_run else "rollback",time.time(),time.monotonic()-started,len(plans)))
        self.export(mid)
        if errors:
            raise GitHubError("; ".join(errors))
        return plans

    def cleanup(self, mid, dry_run=True, retention=3, now=None):
        if retention < 0:
            raise ValueError("Retention cannot be negative")
        manifest = self.load(mid, current=False)
        now = time.time() if now is None else now
        results = []
        for unit in self.db.execute("SELECT * FROM jost_units WHERE mid=? AND cleaned=0", (mid,)).fetchall():
            if unit["verified"] is None or now - unit["verified"] < retention * 86400 or not self.ledger.verified(unit["id"]):
                continue
            targets = []
            for number in json.loads(unit["numbers"]):
                for row in self.outputs(mid, number):
                    if row["state"] != "verified":
                        raise ValueError("Cleanup blocked: unverified output")
                    path = self.target(mid, manifest["items"][number], row["style"])
                    if path.exists() and digest(path) != row["sha256"]:
                        raise ValueError("Cleanup blocked: generated image changed since verification")
                    targets.append(path)
            results.append({"unit": unit["id"], "files": [str(p) for p in targets], "action": "eligible" if dry_run else "cleaned"})
            if not dry_run:
                # Delete only catalogued, verified JPEGs; no recursive directory removal.
                for path in targets:
                    reject_links(path)
                    path.unlink(missing_ok=True)
                with self.db:
                    self.db.execute("UPDATE jost_units SET cleaned=1 WHERE id=?", (unit["id"],))
        return results
