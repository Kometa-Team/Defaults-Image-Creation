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
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from people_github import GitHubClient, GitHubError, REPOSITORIES, branch_name, repository_mapping, sandbox_settings
from people_publication_state import PublicationState
from people_remote_inventory import RemoteInventory, blob_sha, default_state_dir, name_key, path_key
from people_workspaces import atomic_json, reject_links


def env_bool(key, default):
    return os.getenv(key, str(default)).strip().lower() in {"1", "true", "yes", "on"}


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
    def __init__(self, client, inventory, ledger, conflict_attempts=3):
        self.client, self.inventory, self.ledger = client, inventory, ledger
        self.branch = inventory.branch
        self.repositories = inventory.repositories
        self.conflict_attempts = conflict_attempts

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
        trigger = env_bool("UPDATE_TRIGGER_READMES", True)
        required = env_bool("UPDATE_REQUIRE_README_DISPATCH", False)
        for repo in self.repositories.values():
            previous = self.ledger.db.execute("SELECT status FROM readmes WHERE batch=? AND repo=?", (batch, repo)).fetchone()
            if previous and previous["status"] in {"dispatched", "unchanged"}:
                continue
            if not trigger:
                self.ledger.readme(batch, repo, "disabled")
                continue
            try:
                self.client.request("POST", f"/repos/{repo}/actions/workflows/readme.yml/dispatches", {"ref": self.branch})
                self.ledger.readme(batch, repo, "dispatched")
            except GitHubError as error:
                self.ledger.readme(batch, repo, "failed" if required else "warning", safe_exception(error))
                print(f"[WARN] README dispatch: {repo}: {safe_exception(error)}")
                if required:
                    errors.append(safe_exception(error))
        if errors or not self.ledger.verified(batch):
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
