"""Publish canonical people images with Git Data API commits, without clones."""

# A single canonical diagnostic registry is shared by CLI and imported callers.
import sys as _security_sys
from pathlib import Path as _SecurityPath
_security_root = _SecurityPath(__file__).resolve().parents[1]
if (_security_root / "create_people_posters").is_dir() and str(_security_root) not in _security_sys.path:
    _security_sys.path.insert(0, str(_security_root))
from create_people_posters.people_diagnostics import (protect_cli, safe_exception, sanitize_text,
                                                     sanitize_data, secure_handler, register_environment)
from create_people_posters.people_process import guard_cli
if __name__ == "__main__":
    guard_cli()


import argparse
import base64
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
import random
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from people_github import GitHubClient, GitHubError, REPOSITORIES, branch_name, repository_mapping, sandbox_settings
from people_publication_state import PublicationState
from people_remote_inventory import RemoteInventory, blob_sha, default_state_dir, name_key, path_key
from people_workspaces import atomic_json, reject_links


def env_bool(key, default):
    return os.getenv(key, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class _ReadmePause(Exception):
    def __init__(self, error):
        super().__init__("Durable README transport pause")
        self.error = error


class _ReadmeClient:
    """Keep existing dispatch-token recovery; interrupt before errors aggregate."""
    def __init__(self, client):
        self.client = client

    def request(self, *args, **kwargs):
        try:
            return self.client.request(*args, **kwargs)
        except GitHubError as error:
            raise _ReadmePause(error) from None

    def head(self, *args):
        try:
            return self.client.head(*args)
        except GitHubError as error:
            raise _ReadmePause(error) from None


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def current_batch(config):
    configured = os.getenv("PEOPLE_BATCH_ID")
    if configured:
        return configured
    pointer = config / ".orch" / "api-batch.json"
    if pointer.exists():
        return json.loads(pointer.read_text(encoding="utf-8"))["batch_id"]
    batch = time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + "-" + uuid.uuid4().hex[:12]
    atomic_json(pointer, {"batch_id": batch})
    return batch


def prepare(config, batch, ledger, branch):
    from people_batch_safety import assert_batch_ready
    assert_batch_ready(config)
    # Reuse the exact normalizer and quality checks used by local_git sync.
    from sync_people_images import (IMAGE_EXTENSIONS, enforce_transparent_canvas,
                                    image_quality_findings, iter_files,
                                    original_presentation_path, sync_original_presentation)
    repositories = repository_mapping()
    previous = ledger.rows(batch)
    if previous:
        if any(row["repo"] != repositories.get(row["style"]) for row in previous):
            raise ValueError("Cannot retarget an existing publication batch; create a fresh batch")
        if any(row["branch"] != branch for row in previous):
            raise ValueError("Cannot change the branch of an existing batch")
        for row in previous:
            prepared = Path(row["prepared"])
            reject_links(prepared)
            if not prepared.is_file() or file_hash(prepared) != row["published_hash"]:
                raise ValueError("Validated image is missing/changed; restore it from the retained sources before retrying")
            source = Path(row["source"])
            if source.exists() and file_hash(source) != row["source_hash"]:
                raise ValueError("Batch source changed after validation; preserve this batch and use --new-batch")
        return previous
    source_root = config / "people_dirs"
    if (config / "tmdb_conflicts.json").exists():
        raise ValueError("Ambiguous TMDb identities; use distinct aliases in a new batch before publishing")
    target_root = config / ".publish" / batch
    identities = {}
    identity_file = config / "tmdb_identities.json"
    if identity_file.exists():
        identities = json.loads(identity_file.read_text(encoding="utf-8"))
    normalize_original = os.getenv("REMOVE_BG_ENGINE", "birefnet").strip().lower() == "birefnet"
    plan = []
    names = {}
    person_paths = set()
    seen = set()
    for style, repo in repositories.items():
        root = source_root / style
        reject_links(root)
        # Reject links before iter_files, which deliberately follows file targets in legacy mode.
        for directory, dirs, files in os.walk(root, followlinks=False):
            for filename in dirs + files:
                reject_links(Path(directory) / filename)
        for source in sorted(iter_files(root)):
            if source.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            relative = original_presentation_path(root, source) if style == "original" and normalize_original else source.relative_to(root)
            path = relative.as_posix()
            key = path_key(path)
            if (len(relative.parts) != 3 or relative.parts[1] != "Images"
                    or relative.suffix.lower() != (".png" if style == "transparent" else ".jpg")):
                raise ValueError(f"Unexpected image destination: {style}/{path}")
            if (repo, key) in seen:
                raise ValueError(f"Unicode/case collision: {style}/{path}")
            seen.add((repo, key))
            person = relative.stem
            if (style, name_key(person)) in person_paths:
                raise ValueError(f"Duplicate person name in different output paths: {style}/{person}")
            person_paths.add((style, name_key(person)))
            names.setdefault(name_key(person), set()).add(style)
            target = target_root / style / relative
            reject_links(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            blocking, warnings = image_quality_findings(style, source,
                allow_fixable_dimensions=style == "transparent" or (style == "original" and normalize_original),
                allow_native_original=style == "original" and normalize_original)
            if blocking:
                raise ValueError(f"Invalid {style}/{path}: {'; '.join(blocking)}")
            for warning in warnings:
                print(f"[WARN] {style}/{path}: {warning}")
            if style == "original" and normalize_original:
                sync_original_presentation(source, target)
            else:
                shutil.copy2(source, target)
                if style == "transparent":
                    enforce_transparent_canvas(target)
            blocking, _ = image_quality_findings(style, target)
            if blocking:
                raise ValueError(f"Invalid prepared {style}/{path}: {'; '.join(blocking)}")
            data = target.read_bytes()
            if len(data) > 100 * 1024 ** 2:
                raise ValueError(f"Image exceeds GitHub's 100 MiB blob limit: {style}/{path}")
            plan.append({"style": style, "repo": repo, "path": path, "source": str(source.absolute()),
                         "source_hash": file_hash(source), "prepared": str(target.absolute()),
                         "published_hash": hashlib.sha256(data).hexdigest(), "blob": blob_sha(data),
                         "person": person, "tmdb_id": str(identities.get(person, ""))})
    if not plan:
        raise ValueError("No generated images to publish; batch remains unpublished")
    expected_names = set(names)
    for stage in (source_root / "Downloads", config / "Downloads" / "color", config / "Downloads" / "other"):
        for image in iter_files(stage):
            if image.suffix.lower() in IMAGE_EXTENSIONS and name_key(image.stem) not in expected_names:
                raise ValueError(f"Unprocessed input has no complete publication outputs: {image.name}")
    for person, styles in names.items():
        missing = set(repositories) - styles
        if missing:
            raise ValueError(f"Missing mandatory outputs for {person}: {', '.join(sorted(missing))}")
    ledger.plan(batch, branch, plan)
    return plan


class Publisher:
    def __init__(self, client, inventory, ledger, conflict_attempts=3, clock=time.time, sleep=time.sleep, jitter=None, checkpoint_hook=None):
        self.client, self.inventory, self.ledger = client, inventory, ledger
        self.branch = inventory.branch
        self.repositories = inventory.repositories
        self.conflict_attempts = conflict_attempts
        self.clock, self.sleep = clock, sleep
        self.jitter = jitter or (lambda: random.SystemRandom().uniform(0, 30))
        self.checkpoint_hook = checkpoint_hook or (lambda stage: None)

    @staticmethod
    def git_object(kind, raw):
        return hashlib.sha1(kind.encode() + b" " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

    @classmethod
    def tree_identity(cls, entries):
        ordered = sorted(entries, key=lambda e: e["path"].encode("utf8") + (b"/" if e["type"] == "tree" else b"\0"))
        raw = b"".join(("40000" if e["type"] == "tree" else e["mode"]).encode() + b" " +
            e["path"].encode("utf8") + b"\0" + bytes.fromhex(e["sha"]) for e in ordered)
        return cls.git_object("tree", raw)

    @classmethod
    def commit_identity(cls, payload):
        lines = ["tree " + payload["tree"]] + ["parent " + p for p in payload["parents"]]
        for role in ("author", "committer"):
            person = payload[role]
            epoch = int(datetime.fromisoformat(person["date"].replace("Z", "+00:00")).timestamp())
            lines.append(f"{role} {person['name']} <{person['email']}> {epoch} +0000")
        return cls.git_object("commit", ("\n".join(lines) + "\n\n" + payload["message"]).encode("utf8"))

    def replacement_tree(self, repo, base, updates):
        entries = {r["path"]: dict(r) for r in self.inventory.db.execute(
            "SELECT path,sha,type,mode FROM entries WHERE repo=? AND branch=?", (repo, self.branch))}
        def children(folder):
            prefix = folder + "/" if folder else ""
            return [dict(e, path=p[len(prefix):]) for p, e in entries.items()
                    if p.startswith(prefix) and "/" not in p[len(prefix):]]
        if self.tree_identity(children("")) != base:
            raise ValueError("Cached root tree identity mismatch")
        affected = {""}
        for entry in updates:
            parts = entry["path"].split("/")
            affected.update("/".join(parts[:n]) for n in range(1, len(parts)))
        for folder in affected - {""}:
            if folder in entries and self.tree_identity(children(folder)) != entries[folder]["sha"]:
                raise ValueError("Cached subtree identity mismatch")
        entries.update({e["path"]: e for e in updates})
        for folder in sorted(affected, key=lambda p: (p.count("/"), len(p)), reverse=True):
            identity = self.tree_identity(children(folder))
            if not folder:
                return identity
            entries[folder] = dict(path=folder, mode="040000", type="tree", sha=identity)

    def reliable_settings(self):
        def number(name, default, low, high):
            value = int(os.getenv(name, str(default)))
            if not low <= value <= high:
                raise ValueError("Reliability setting outside reviewed bounds")
            return value
        name = os.getenv("PEOPLE_PUBLICATION_AUTHOR_NAME", "Kometa People Publisher")
        email = os.getenv("PEOPLE_PUBLICATION_AUTHOR_EMAIL", "people-publisher@users.noreply.github.com")
        if (not name or len(name) > 100 or not email or len(email) > 200
                or any(ord(c) < 32 or c in "<>" for c in name + email) or "@" not in email):
            raise ValueError("Invalid explicit publication identity")
        return dict(version=1, unit_size=50, max_attempts=number("PEOPLE_PUBLICATION_MAX_ATTEMPTS", 20, 1, 100),
                    max_wait=number("PEOPLE_PUBLICATION_MAX_WAIT", 86400, 60, 604800),
                    max_elapsed=number("PEOPLE_PUBLICATION_MAX_ELAPSED", 604800, 60, 2592000),
                    author=name, email=email, write_interval=number("PEOPLE_GITHUB_WRITE_INTERVAL", 15, 15, 86400))

    def _save(self, batch, repo, number, state, stage=None):
        if stage:
            state["stage"] = stage
        self.ledger.save_unit(batch, repo, number, state)
        self.checkpoint_hook(state["stage"])

    def _owned_head(self, repo, state):
        head, _ = self.client.head(repo, self.branch)
        if head not in {state["parent"], state["commit"]}:
            raise GitHubError("Unowned remote HEAD; publication stopped", 409)
        return head

    def _object_result(self, repo, route, expected, payload, state, batch, number):
        # Every intent is durable BEFORE a request can reach GitHub.
        intent = dict(route=route, expected=expected)
        if state["intent"]:
            if state["intent"] != intent:
                raise ValueError("Durable write intent differs from resumed operation")
            try:
                found = self.client.request("GET", f"/repos/{repo}/git/{route}/{expected}")
            except GitHubError as error:
                if error.status != 404:
                    raise
            else:
                if found.get("sha") != expected:
                    raise ValueError("Recovered object identity mismatch")
                return found
        state["intent"] = intent
        self._save(batch, repo, number, state)
        result = self.client.request("POST", f"/repos/{repo}/git/{route}", payload)
        if result.get("sha") != expected:
            raise ValueError("GitHub object differs from deterministic write intent")
        self.checkpoint_hook(route + "_ack")
        return result

    def _prepare_unit(self, batch, style, repo, number, rows, control, settings):
        head, base = self.inventory.refresh(style)
        if head != control["head"]:
            raise GitHubError("Unexpected remote HEAD before unit preparation", 409)
        updates = []
        for row in rows:
            if row["status"] == "conflict":
                raise GitHubError("Existing destination conflict requires review", 409)
            current = self.check_destination(style, row["path"])
            actual = current["sha"] if current else None
            if row["status"] == "published" and actual != row["blob"]:
                raise ValueError("Previously verified destination changed")
            if actual != row["blob"]:
                if actual != self.ledger.baseline(batch, repo, row["path"], actual):
                    raise GitHubError("Approved destination baseline changed", 409)
                updates.append(dict(path=row["path"], mode="100644", type="blob", sha=row["blob"]))
        tree = self.replacement_tree(repo, base, updates) if updates else base
        date = datetime.fromtimestamp(int(self.clock()), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        author = dict(name=settings["author"], email=settings["email"], date=date)
        message = f"chore: sync posters - batch {batch} unit {number} [skip readme]\n"
        payload = dict(tree=tree, parents=[head], message=message, author=author, committer=author)
        state = dict(parent=head, base_tree=base, tree=tree, commit=self.commit_identity(payload) if updates else head,
                     commit_payload=payload, updates=updates)
        existing = self.ledger.unit(batch, repo, number, rows)
        existing.update(state)
        self._save(batch, repo, number, existing, "prepared")
        return existing

    def _run_unit(self, batch, style, repo, number, rows, state):
        expected = {r["path"]: r["blob"] for r in rows}
        if (any(set(e) != {"path", "mode", "type", "sha"} or e["mode"] != "100644" or e["type"] != "blob"
                or expected.get(e["path"]) != e["sha"] for e in state["updates"])
                or len({e["path"] for e in state["updates"]}) != len(state["updates"])
                or (state["updates"] and (self.commit_identity(state["commit_payload"]) != state["commit"]
                    or state["commit_payload"]["parents"] != [state["parent"]]
                    or state["commit_payload"]["tree"] != state["tree"]))):
            raise ValueError("Durable unit differs from approved content")
        self._owned_head(repo, state)
        wanted = {r["path"]: r for r in rows}
        if state["stage"] == "prepared":
            for update in state["updates"]:
                row = wanted[update["path"]]
                if row["blob"] in state["done"]:
                    continue
                path = Path(row["prepared"])
                reject_links(path)
                data = path.read_bytes()
                if blob_sha(data) != row["blob"] or hashlib.sha256(data).hexdigest() != row["published_hash"]:
                    raise ValueError("Prepared artwork identity changed")
                source = Path(row["source"])
                reject_links(source)
                if source.exists() and file_hash(source) != row["source_hash"]:
                    raise ValueError("Approved source identity changed")
                self._object_result(repo, "blobs", row["blob"], dict(content=base64.b64encode(data).decode("ascii"), encoding="base64"), state, batch, number)
                state["done"].append(row["blob"])
                state["intent"] = None
                self._save(batch, repo, number, state)
            self._save(batch, repo, number, state, "blobs_uploaded")
        if state["stage"] == "blobs_uploaded":
            if state["updates"]:
                self._object_result(repo, "trees", state["tree"], dict(base_tree=state["base_tree"], tree=state["updates"]), state, batch, number)
            state["intent"] = None
            self._save(batch, repo, number, state, "tree_created")
        if state["stage"] == "tree_created":
            if state["updates"]:
                self._object_result(repo, "commits", state["commit"], state["commit_payload"], state, batch, number)
            state["intent"] = None
            self._save(batch, repo, number, state, "commit_created")
        if state["stage"] == "commit_created":
            state["intent"] = dict(route="ref", expected=state["commit"])
            self._save(batch, repo, number, state)
            head = self._owned_head(repo, state)
            if head != state["commit"]:
                result = self.client.request("PATCH", f"/repos/{repo}/git/refs/heads/{quote(self.branch, safe='/')}",
                                             dict(sha=state["commit"], force=False))
                if result.get("object", {}).get("sha") != state["commit"]:
                    raise ValueError("GitHub did not acknowledge the owned branch update")
                self.checkpoint_hook("ref_ack")
            state["intent"] = None
            self._save(batch, repo, number, state, "branch_updated")
        if state["stage"] == "branch_updated":
            if state["updates"]:
                comparison = self.client.request("GET", f"/repos/{repo}/compare/{state['parent']}...{state['commit']}")
                changed = {e["filename"]: e["sha"] for e in comparison.get("files", [])}
                if (comparison.get("status") != "ahead" or comparison.get("total_commits") != 1
                        or changed != {e["path"]: e["sha"] for e in state["updates"]}
                        or any(e["status"] not in {"added", "modified"} for e in comparison["files"])):
                    raise ValueError("Owned commit contains unapproved changes")
            head, _ = self.inventory.refresh(style)
            if head != state["commit"]:
                raise GitHubError("Unexpected HEAD during remote verification", 409)
            for row in rows:
                actual = self.check_destination(style, row["path"])
                if not actual or actual["sha"] != row["blob"]:
                    raise ValueError("Remote artwork verification failed")
            self._save(batch, repo, number, state, "remote_verified")
        if state["stage"] == "remote_verified":
            if self._owned_head(repo, state) != state["commit"]:
                raise GitHubError("HEAD changed before receipt transaction", 409)
            self.ledger.complete_unit(batch, repo, number, rows, state)
            self.checkpoint_hook("published")

    def _schedule_retry(self, batch, repo, number, state, error, settings):
        now = self.clock()
        state["attempts"] += 1
        state["first_failure"] = state["first_failure"] or now
        rates = getattr(error, "diagnostic", {}).get("rate_limit", {})
        delay = max(min(3600, 60 * 2 ** min(state["attempts"] - 1, 10)) + max(0, min(30, self.jitter())),
                    rates.get("retry_after_seconds", 0), max(0, rates.get("reset", 0) - now) if rates.get("remaining") == 0 else 0)
        if (state["attempts"] >= settings["max_attempts"] or delay > settings["max_wait"]
                or now + delay - state["first_failure"] > settings["max_elapsed"]):
            state.update(status="blocked", error=dict(category="retry_budget_exhausted"))
            self._save(batch, repo, number, state)
            raise GitHubError("Durable retry budget exhausted; preserve this unit")
        state.update(status="retrying", not_before=now + delay,
                     error=dict(category=getattr(error, "category", "unclassified"), http_status=error.status,
                                diagnostic=getattr(error, "diagnostic", {})))
        self._save(batch, repo, number, state)

    def publish_reliable(self, batch, dry_run=False):
        if getattr(self.client, "sandbox", None):
            self.validate()
        if dry_run:
            raise ValueError("Reliable publication requires the existing reviewed read-only reconciliation first")
        settings = self.reliable_settings()
        if len(self.repositories) != 1 or {r["repo"] for r in self.ledger.rows(batch)} != set(self.repositories.values()):
            raise ValueError("Reliable publication requires one existing reviewed repository batch")
        with self.ledger.publication_lock():
            self.ledger.reliability_schema()
            for style, repo in self.repositories.items():
                rows = self.ledger.rows(batch, repo)
                if not rows or any(r["style"] != style or r["branch"] != self.branch for r in rows):
                    raise ValueError("Existing batch destination or branch mismatch")
                control = self.ledger.reliability_control(batch, repo, os.getenv("PEOPLE_PUBLICATION_EXPECTED_HEAD", ""),
                    settings, os.getenv("PEOPLE_PUBLICATION_LEGACY_REVIEW_SHA256", ""))
                self.client.reliable = True
                self.client.write_interval = settings["write_interval"]
                for offset in range(0, len(rows), settings["unit_size"]):
                    group, number = rows[offset:offset + settings["unit_size"]], offset // settings["unit_size"]
                    state = self.ledger.unit(batch, repo, number, group)
                    if state is None and all(r["status"] == "published" for r in group):
                        # Verify remote completed artwork, preserving exact old receipts.
                        head, _ = self.inventory.refresh(style)
                        active = [json.loads(r[0]) for r in self.ledger.db.execute("SELECT data FROM publication_units WHERE batch=? AND repo=?", (batch, repo))]
                        allowed = {control["head"]} | {u["commit"] for u in active if u["parent"] == control["head"] and u["status"] != "completed"}
                        if head not in allowed:
                            raise GitHubError("Unexpected HEAD while checking legacy receipts", 409)
                        for row in group:
                            current = self.check_destination(style, row["path"])
                            if not current or current["sha"] != row["blob"]:
                                raise ValueError("Previously completed artwork changed")
                        continue
                    if state and state["status"] == "completed":
                        continue
                    if state and state["status"] in {"blocked", "permanently_failed"}:
                        raise GitHubError("Stopped unit requires explicit operator review")
                    if state is None:
                        state = self.ledger.unit(batch, repo, number, group, dict(stage="preparing", parent=control["head"],
                            commit=control["head"], tree="", base_tree="", updates=[], commit_payload={}))
                    while True:
                        try:
                            if state["first_failure"] and self.clock() - state["first_failure"] > settings["max_elapsed"]:
                                state.update(status="blocked", error=dict(category="retry_budget_exhausted"))
                                self._save(batch, repo, number, state)
                                raise GitHubError("Durable retry elapsed budget expired during downtime")
                            while self.clock() < state["not_before"]:
                                print(json.dumps(dict(event="retry_wait", unit=number, attempts=state["attempts"], not_before=state["not_before"])), flush=True)
                                self.sleep(min(30, state["not_before"] - self.clock()))
                            if state["stage"] == "preparing":
                                state = self._prepare_unit(batch, style, repo, number, group, control, settings)
                            if state["updates"] and self.ledger.readme_state(batch, repo)["status"] == "unchanged":
                                self.ledger.readme(batch, repo, "pending")
                            self._run_unit(batch, style, repo, number, group, state)
                            control = dict(self.ledger.db.execute("SELECT * FROM publication_controls WHERE batch=? AND repo=?", (batch, repo)).fetchone())
                            print(json.dumps(dict(event="unit_completed", unit=number, **self.ledger.reliability_progress(batch, repo))), flush=True)
                            break
                        except GitHubError as error:
                            if state is not None and getattr(error, "retryable", False):
                                self._schedule_retry(batch, repo, number, state, error, settings)
                                continue
                            if state is not None:
                                state.update(status="permanently_failed" if getattr(error, "category", "") == "validation" else "blocked",
                                             error=dict(category=getattr(error, "category", "unclassified"), http_status=error.status,
                                                        diagnostic=getattr(error, "diagnostic", {})))
                                self._save(batch, repo, number, state)
                            raise
                        except (OSError, ValueError):
                            if state is not None:
                                state.update(status="blocked", error=dict(category="integrity_or_storage"))
                                self._save(batch, repo, number, state)
                            raise
            # Preserve existing README dispatch, approval and verification mechanisms.
            from people_readme_publication import ReadmePublication
            for style, repo in self.repositories.items():
                control = self.ledger.db.execute("SELECT head FROM publication_controls WHERE batch=? AND repo=?", (batch, repo)).fetchone()
                if self.ledger.readme_state(batch, repo)["status"] not in {"waiting", "verified"} and self.client.head(repo, self.branch)[0] != control[0]:
                    raise GitHubError("HEAD changed before README phase", 409)
                state = self.ledger.unit(batch, repo, "readme", [], dict(stage="readme", parent=control[0], commit=control[0]))
                helper = ReadmePublication(_ReadmeClient(self.client), self.inventory, self.ledger, sleep=self.sleep, now=self.clock)
                helper.timeout = float(os.getenv("PEOPLE_README_TIMEOUT", str(settings["max_elapsed"])))
                # Keep the existing correlated dispatch/wait/recovery machinery.
                while True:
                    if state["status"] == "blocked":
                        raise GitHubError("README retry budget requires operator review")
                    while self.clock() < state["not_before"]:
                        self.sleep(min(30, state["not_before"] - self.clock()))
                    try:
                        old_client = self.inventory.client
                        self.inventory.client = helper.client
                        try:
                            helper.publish(batch, enabled=env_bool("UPDATE_TRIGGER_READMES", True))
                        finally:
                            self.inventory.client = old_client
                        state.update(status="completed", not_before=0)
                        self._save(batch, repo, "readme", state)
                        break
                    except _ReadmePause as pause:
                        if not getattr(pause.error, "retryable", False):
                            state.update(status="blocked", error=dict(category=getattr(pause.error, "category", "unclassified"),
                                http_status=pause.error.status, diagnostic=getattr(pause.error, "diagnostic", {})))
                            self._save(batch, repo, "readme", state)
                            raise pause.error
                        self._schedule_retry(batch, repo, "readme", state, pause.error, settings)
            if not self.ledger.verified(batch):
                raise GitHubError("Publication and README receipts are incomplete")

    def validate(self):
        for style, repo in self.repositories.items():
            print(f"[INFO] Validating {repo}@{self.branch}", flush=True)
            metadata = self.client.request("GET", f"/repos/{repo}")
            if getattr(self.client, "sandbox", None):
                if (metadata.get("full_name", "").casefold() != repo.casefold()
                        or metadata.get("private") is not True or metadata.get("fork") is not False
                        or metadata.get("owner", {}).get("type") != "User"):
                    raise GitHubError("Sandbox must be a private, non-fork repository with the expected canonical name")
            if metadata.get("archived") or metadata.get("disabled"):
                raise GitHubError(f"Repository is archived or disabled: {repo}")
            if metadata.get("permissions", {}).get("push") is False:
                raise GitHubError(f"No write access to {repo}; request Contents:write. Community users need an authorized fork/PR workflow.", 403)
            self.inventory.refresh(style)
            print(f"[OK] {repo}@{self.branch}")

    def check_destination(self, style, path):
        parts = path.split("/")
        for length in range(1, len(parts)):
            parent = self.inventory.lookup(style, "/".join(parts[:length]))
            if parent and (parent["type"] != "tree" or parent["path"] != "/".join(parts[:length])):
                raise GitHubError("Destination ancestor conflicts with an existing file or Unicode/case variant")
        old = self.inventory.lookup(style, path)
        if old and (old["path"] != path or old["mode"] != "100644" or old["type"] != "blob"):
            raise GitHubError("Destination conflicts with an existing Unicode/case variant or nonordinary file")
        return old

    def publish_chunk(self, batch, style, rows, dry_run=False):
        repo = self.repositories[style]
        initial = None
        for attempt in range(self.conflict_attempts):
            head, tree = self.inventory.refresh(style)
            old = {row["path"]: self.check_destination(style, row["path"]) for row in rows}
            for row in rows:
                if row["status"] == "conflict":
                    raise GitHubError("Unresolved remote conflict; inspect the destination and create an explicitly reviewed new batch")
                if row["status"] == "published" and (not old[row["path"]] or old[row["path"]]["sha"] != row["blob"]):
                    if not dry_run:
                        self.ledger.mark(batch, repo, [row["path"]], "conflict", error="Previously verified destination edited remotely")
                    raise GitHubError("A previously verified destination was edited remotely; refusing to overwrite it on resume")
            if initial is None:
                initial = {path: (value["sha"] if value else None) if dry_run else
                           self.ledger.baseline(batch, repo, path, value["sha"] if value else None)
                           for path, value in old.items()}
            changed = [row for row in rows if not old[row["path"]] or old[row["path"]]["sha"] != row["blob"]]
            for row in changed:
                current = old[row["path"]]
                if (current["sha"] if current else None) != initial[row["path"]]:
                    if not dry_run:
                        self.ledger.mark(batch, repo, [row["path"]], "conflict", error="Concurrent destination edit")
                    raise GitHubError(f"Concurrent edit of {repo}/{row['path']}; review before overwriting")
            if dry_run:
                print(f"[DRY-RUN] {repo}: {len(changed)} changed, {len(rows) - len(changed)} unchanged")
                return
            if not changed:
                self.ledger.mark(batch, repo, [r["path"] for r in rows], "published", head)
                return
            self.ledger.readme(batch, repo, "pending")
            self.ledger.mark(batch, repo, [r["path"] for r in changed], "attempted")
            updates = []
            for row in changed:
                source = Path(row["prepared"])
                reject_links(source)
                data = source.read_bytes()
                if blob_sha(data) != row["blob"] or hashlib.sha256(data).hexdigest() != row["published_hash"]:
                    raise ValueError("Prepared image changed; refusing to publish mismatched bytes")
                blob = self.client.request("POST", f"/repos/{repo}/git/blobs", {
                    "content": base64.b64encode(data).decode("ascii"), "encoding": "base64"})
                if blob["sha"] != row["blob"]:
                    raise GitHubError("GitHub returned an unexpected blob hash")
                updates.append({"path": row["path"], "mode": "100644", "type": "blob", "sha": blob["sha"]})
            new_tree = self.client.request("POST", f"/repos/{repo}/git/trees", {"base_tree": tree, "tree": updates})
            message = os.getenv("ORCH_COMMIT_MESSAGE", "").strip() or f"chore: sync posters - batch {batch}"
            marker = os.getenv("UPDATE_README_SKIP_MARKER", "[skip readme]").strip()
            if env_bool("UPDATE_TRIGGER_READMES", True) and marker and marker not in message:
                message += " " + marker
            commit = self.client.request("POST", f"/repos/{repo}/git/commits", {
                "message": message, "tree": new_tree["sha"], "parents": [head]})
            try:
                result = self.client.request("PATCH", f"/repos/{repo}/git/refs/heads/{quote(self.branch, safe='/')}",
                                             {"sha": commit["sha"], "force": False})
                if result.get("object", {}).get("sha") != commit["sha"]:
                    raise GitHubError("GitHub did not confirm the expected ref update")
            except GitHubError as error:
                latest, _ = self.client.head(repo, self.branch)
                if latest != head and attempt + 1 < self.conflict_attempts:
                    continue
                raise error
            # Verify branch reachability and path/blob identity before issuing receipts.
            verified_head, _ = self.inventory.refresh(style)
            if verified_head != commit["sha"]:
                comparison = self.client.request("GET", f"/repos/{repo}/compare/{commit['sha']}...{verified_head}")
                if comparison.get("status") not in {"ahead", "identical"}:
                    raise GitHubError("Published commit is not reachable from the configured branch")
            for row in rows:
                entry = self.check_destination(style, row["path"])
                if not entry or entry["sha"] != row["blob"]:
                    raise GitHubError("Published destination verification failed; local batch retained")
            self.ledger.mark(batch, repo, [r["path"] for r in rows], "published", commit["sha"])
            return
        raise GitHubError("Concurrent branch updates exhausted retries; resume this batch later")

    def publish(self, batch, dry_run=False):
        if env_bool("PEOPLE_RELIABLE_PUBLISH", False):
            return self.publish_reliable(batch, dry_run)
        planned = self.ledger.rows(batch)
        if (set(row["repo"] for row in planned) != set(self.repositories.values())
                or any(row["repo"] != self.repositories.get(row["style"]) for row in planned)):
            raise ValueError("Publication destinations do not match this target profile; refusing to retarget receipts")
        if any(row["branch"] != self.branch for row in planned):
            raise ValueError("Configured branch differs from the existing publication plan")
        if getattr(self.client, "sandbox", None):
            self.validate()
        for row in planned:
            for key, digest in (("prepared", "published_hash"), ("source", "source_hash")):
                path = Path(row[key])
                reject_links(path)
                if ((key == "prepared" and not path.is_file())
                        or (path.exists() and file_hash(path) != row[digest])):
                    if not dry_run:
                        self.ledger.mark(batch, row["repo"], [row["path"]], "conflict", error="Local validated image missing/changed")
                    raise ValueError("Validated local image missing/changed; batch retained for review")
        errors = []
        for style, repo in self.repositories.items():
            rows = self.ledger.rows(batch, repo)
            if not rows:
                raise ValueError(f"Missing publication plan for {repo}")
            try:
                # Content comparison makes retries idempotent, including a crash after PATCH.
                chunk, size = [], 0
                for row in rows:
                    image_size = Path(row["prepared"]).stat().st_size
                    if chunk and (len(chunk) >= 100 or size + image_size > 256 * 1024 ** 2):
                        self.publish_chunk(batch, style, chunk, dry_run)
                        chunk, size = [], 0
                    chunk.append(row)
                    size += image_size
                if chunk:
                    self.publish_chunk(batch, style, chunk, dry_run)
            except (GitHubError, OSError, ValueError) as error:
                outstanding = [r["path"] for r in self.ledger.rows(batch, repo) if r["status"] not in {"published", "conflict"}]
                if not dry_run:
                    self.ledger.mark(batch, repo, outstanding, "failed", error=safe_exception(error))
                errors.append(f"{style}: {safe_exception(error)}")
        if errors:
            raise GitHubError("Partial publication; retry the same batch. " + "; ".join(errors))
        if dry_run:
            return
        from people_readme_publication import ReadmePublication
        ReadmePublication(self.client, self.inventory, self.ledger).publish(
            batch, enabled=env_bool("UPDATE_TRIGGER_READMES", True))
        if not self.ledger.verified(batch):
            raise GitHubError("Required publication/README verification incomplete; files retained")


def verify_local_publication(batch, ledger, repo_root, branch):
    """Conservative local_git receipt verification; a changed remote head needs review."""
    import subprocess
    if sandbox_settings():
        raise ValueError("Sandbox testing requires github_api publishing, never local_git")
    def git(root, *args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                                encoding="utf-8", errors="strict", timeout=120)
        if result.returncode:
            raise ValueError("Local Git publication verification failed; retain the batch and inspect remote state")
        return result.stdout
    for style, repo in REPOSITORIES.items():
        root = Path(repo_root) / style
        remote = git(root, "ls-remote", "--exit-code", "origin", "refs/heads/" + branch).split()[0]
        local = git(root, "rev-parse", "HEAD").strip()
        if local != remote:
            raise ValueError("Remote advanced after local push (possibly README generation). Refresh the clone and retry --redo push; files retained")
        entries = {}
        for item in git(root, "ls-tree", "-r", "-z", local).split("\0"):
            if item:
                metadata, path = item.split("\t", 1)
                mode, kind, sha = metadata.split()
                entries[path] = (mode, kind, sha)
        rows = ledger.rows(batch, repo)
        if any(entries.get(r["path"]) != ("100644", "blob", r["blob"]) for r in rows):
            raise ValueError("Local Git published bytes do not match the batch; files retained")
        ledger.mark(batch, repo, [r["path"] for r in rows], "published", remote)
        # update_people_repos has already applied the legacy dispatch/error policy.
        ledger.readme(batch, repo, "disabled")


def main():
    from dotenv import load_dotenv
    root = Path(__file__).resolve().parent / "config"
    load_dotenv(root / ".env")
    register_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--op", choices=["validate", "refresh", "prepare", "push"], default="push")
    parser.add_argument("--config", type=Path, default=Path(os.getenv("PEOPLE_CONFIG_DIR") or root))
    parser.add_argument("--branch")
    parser.add_argument("--batch-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    ledger = None
    inventory = None
    try:
        branch = branch_name(args.branch)
        if args.op in {"prepare", "push"}:
            from people_batch_safety import assert_batch_ready
            assert_batch_ready(args.config)
        manifest_file = args.config / "manifest.json"
        if args.op == "push" and not args.dry_run and manifest_file.exists():
            if json.loads(manifest_file.read_text(encoding="utf-8")).get("status") == "validation_only":
                raise ValueError("Validation-only smoke-test batch cannot be published")
        state = default_state_dir()
        ledger = PublicationState(state)
        if args.op == "prepare":
            batch = args.batch_id or current_batch(args.config)
            prepare(args.config, batch, ledger, branch)
            print(f"[OK] Prepared batch {batch}; nothing published yet")
            return 0
        client = GitHubClient()
        inventory = RemoteInventory(client, branch=branch)
        publisher = Publisher(client, inventory, ledger)
        if args.op == "validate":
            publisher.validate()
        elif args.op == "refresh":
            inventory.refresh_all()
        else:
            batch = args.batch_id or current_batch(args.config)
            if not ledger.rows(batch):
                prepare(args.config, batch, ledger, branch)
            publisher.publish(batch, args.dry_run)
            if not args.dry_run:
                print(f"[OK] All seven destinations verified for {batch}")
        return 0
    except (GitHubError, ValueError, OSError) as error:
        print(f"[ERROR] {safe_exception(error)}", file=sys.stderr)
        return 1
    finally:
        if inventory:
            inventory.close()
        if ledger:
            ledger.close()


if __name__ == "__main__":
    raise SystemExit(main())
