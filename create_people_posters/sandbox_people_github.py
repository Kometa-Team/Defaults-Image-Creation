"""Explicit live validation in seven private personal repos, never production."""

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
import subprocess
import time
from pathlib import Path

import yaml

from people_github import GitHubClient, GitHubError, REPOSITORIES, SANDBOX_ROOT, sandbox_settings
from people_publication_state import PublicationState
from people_remote_inventory import RemoteInventory
from people_workspaces import ROOT, Workspaces, atomic_json, reject_links
from publish_people_github import Publisher, file_hash, prepare


MARKER = ".people-sandbox.json"


def gh(*args):
    result = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", timeout=120)
    if result.returncode:
        raise GitHubError("GitHub CLI operation failed; check repository-creation and workflow permissions. " + result.stderr.strip())
    return result.stdout


class RecordingClient(GitHubClient):
    def __init__(self):
        super().__init__()
        if not self.sandbox:
            raise ValueError("Live sandbox runner cannot operate in production mode")
        self.events = []

    def request(self, method, path, payload=None):
        result = super().request(method, path, payload)
        self.events.append({"method": method, "path": path})
        return result


def copied_readme_workflow(style):
    # Copy production logic structurally; never copy secrets or Discord notification steps.
    source = gh("api", f"repos/{REPOSITORIES[style]}/contents/.github/workflows/readme.yml?ref=master")
    document = json.loads(source)
    workflow = yaml.load(base64.b64decode(document["content"]), Loader=yaml.BaseLoader)
    if set(workflow["on"]) != {"workflow_dispatch", "push"}:
        raise ValueError("Production README triggers changed; review before cloning the workflow")
    workflow["on"] = {"workflow_dispatch": {}, "push": {}}
    workflow["concurrency"]["cancel-in-progress"] = True
    for job in workflow["jobs"].values():
        job["steps"] = [step for step in job["steps"] if "discord" not in str(step.get("uses", "")).lower()]
        for step in job["steps"]:
            if "TARGET_REPO" in step.get("env", {}) and step["env"]["TARGET_REPO"] != "${{ github.repository }}":
                raise ValueError("README workflow is not scoped to its own repository")
            if "TARGET_REF" in step.get("env", {}) and step["env"]["TARGET_REF"] != "master":
                raise ValueError("Unexpected production README branch; review required")
    return yaml.safe_dump(workflow, sort_keys=False, allow_unicode=True).encode("utf-8")


def bootstrap(client, owner, create):
    if gh("api", "user", "--jq", ".login").strip().casefold() != owner.casefold():
        raise ValueError("Sandbox owner must match the authenticated gh account")
    created = []
    for style, repo in client.repositories.items():
        new = False
        try:
            metadata = client.request("GET", f"/repos/{repo}")
        except GitHubError as error:
            if error.status != 404 or not create:
                raise
            gh("repo", "create", repo, "--private", "--add-readme", "--description",
               "Isolated Kometa People publisher validation; no production images are modified")
            new = True
            created.append(repo)
            metadata = client.request("GET", f"/repos/{repo}")
        if (metadata.get("private") is not True or metadata.get("fork") is not False
                or metadata.get("owner", {}).get("type") != "User"
                or metadata.get("full_name", "").casefold() != repo.casefold()):
            raise ValueError("Refusing to bootstrap a public, forked or redirected repository")
        marker = {"version": 1, "managed_by": "kometa-people-sandbox-v1", "owner": owner, "style": style}
        if not new:
            existing = client.request("GET", f"/repos/{repo}/contents/{MARKER}?ref=master")
            if json.loads(base64.b64decode(existing["content"])) != marker:
                raise ValueError("Existing repository is not a recognized sandbox; no files changed")
            continue
        branch = metadata["default_branch"]
        if branch != "master":
            client.request("POST", f"/repos/{repo}/branches/{branch}/rename", {"new_name": "master"})
        head, tree = client.head(repo, "master")
        files = {MARKER: json.dumps(marker, indent=2).encode(),
                 "sandbox-preserve.txt": b"Unrelated sandbox sentinel: preserve this file.\n",
                 ".github/workflows/readme.yml": copied_readme_workflow(style)}
        updates = []
        for path, data in files.items():
            blob = client.request("POST", f"/repos/{repo}/git/blobs", {
                "content": base64.b64encode(data).decode("ascii"), "encoding": "base64"})
            updates.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        new_tree = client.request("POST", f"/repos/{repo}/git/trees", {"base_tree": tree, "tree": updates})
        commit = client.request("POST", f"/repos/{repo}/git/commits", {
            "message": "test: initialize private People sandbox [skip readme]", "tree": new_tree["sha"], "parents": [head]})
        client.request("PATCH", f"/repos/{repo}/git/refs/heads/master", {"sha": commit["sha"], "force": False})
        print(f"[SANDBOX] Initialized {repo}", flush=True)
    return created


def production_heads():
    return {style: gh("api", f"repos/{repo}/git/ref/heads/master", "--jq", ".object.sha").strip()
            for style, repo in REPOSITORIES.items()}


def counts(events):
    return {"image_ref_updates": sum(e["method"] == "PATCH" and "/git/refs/" in e["path"] for e in events),
            "readme_dispatches": sum(e["method"] == "POST" and e["path"].endswith("/dispatches") for e in events),
            "mutations": sum(e["method"] != "GET" for e in events)}


def wait_for_readmes(client, previous, timeout):
    deadline = time.monotonic() + timeout
    completed = {}
    while len(completed) < len(client.repositories):
        for repo in client.repositories.values():
            if repo in completed:
                continue
            data = client.request("GET", f"/repos/{repo}/actions/runs?event=workflow_dispatch&branch=master&per_page=30")
            runs = [run for run in data["workflow_runs"] if run["id"] not in previous[repo]
                    and run.get("path") == ".github/workflows/readme.yml"]
            if not runs:
                continue
            run = min(runs, key=lambda item: item["id"])
            if run["status"] == "completed":
                completed[repo] = {"id": run["id"], "conclusion": run["conclusion"], "url": run["html_url"]}
                print(f"[README] {repo}: {run['conclusion']}", flush=True)
                if run["conclusion"] != "success":
                    raise GitHubError(f"Sandbox README workflow failed: {run['html_url']}")
        if len(completed) < len(client.repositories):
            if time.monotonic() >= deadline:
                raise GitHubError("README workflow wait timed out; files retained for inspection")
            time.sleep(10)
    return completed


def live_validation(client, source, root, timeout):
    source = Path(source).resolve()
    reject_links(source)
    source_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if source_manifest.get("status") != "validation_only":
        raise ValueError("Use a retained validation-only source job, never an active production job")
    original_hashes = {str(path): file_hash(path) for path in (source / "people_dirs").rglob("*") if path.is_file()}
    report = {"target": "sandbox", "repositories": client.repositories, "source": str(source),
              "production_heads_before": production_heads()}
    report_path = root / "report.json"
    atomic_json(report_path, report)
    manager = Workspaces(root)
    ledger = None
    inventory = None
    batch = None
    try:
        batch = manager.create(source / "people_list.txt", cleanup=False)
        report["batch_id"] = batch
        manager.activate(batch)
        manager.configure(batch)
        path = manager.path(batch)
        for style in client.repositories:
            shutil.copytree(source / "people_dirs" / style, path / "people_dirs" / style)
        if (source / "tmdb_identities.json").exists():
            shutil.copy2(source / "tmdb_identities.json", path / "tmdb_identities.json")
        ledger = PublicationState(manager.state)
        inventory = RemoteInventory(client, branch="master")
        prepare(path, batch, ledger, "master")
        previous_runs = {repo: {run["id"] for run in client.request("GET", f"/repos/{repo}/actions/runs?event=workflow_dispatch&per_page=100")["workflow_runs"]}
                         for repo in client.repositories.values()}

        class PartialFailure(Publisher):
            def publish_chunk(self, batch, style, rows, dry_run=False):
                if style in {"diiivoycolor", "rainier", "signature"}:
                    raise GitHubError("Intentional sandbox-only failure before upload", 503)
                return super().publish_chunk(batch, style, rows, dry_run)

        begin = len(client.events)
        try:
            PartialFailure(client, inventory, ledger).publish(batch)
        except GitHubError as error:
            if "Intentional sandbox-only failure" not in safe_exception(error):
                raise
        else:
            raise AssertionError("Expected partial publication did not fail")
        rows = ledger.rows(batch)
        confirmed = {row["style"]: row["commit_sha"] for row in rows if row["status"] == "published"}
        if len(confirmed) != 4 or ledger.verified(batch):
            raise AssertionError("Partial publication was incorrectly recorded")
        manager.set_status(batch, "partially_published", "Intentional test interruption")
        if manager.cleanup(dry_run=False) or not (path / "people_dirs").exists():
            raise AssertionError("Partial publication files were not retained")
        report["partial_failure"] = dict(counts(client.events[begin:]), confirmed_styles=sorted(confirmed),
                                         unpublished_styles=[row["style"] for row in rows if row["status"] != "published"], files_retained=True)
        if report["partial_failure"]["readme_dispatches"]:
            raise AssertionError("README workflows were dispatched before all destinations succeeded")
        atomic_json(report_path, report)
        ledger.close()
        inventory.close()
        manager.deactivate(batch)
        manager.close()

        # Reopen durable state, just as a restarted process would.
        manager = Workspaces(root)
        manager.activate(batch)
        ledger = PublicationState(manager.state)
        inventory = RemoteInventory(client, branch="master")
        begin = len(client.events)
        Publisher(client, inventory, ledger).publish(batch)
        report["recovery"] = counts(client.events[begin:])
        if report["recovery"]["readme_dispatches"] != 7:
            raise AssertionError("Expected seven accepted README workflow dispatches")
        if any(row["commit_sha"] != confirmed[row["style"]] for row in ledger.rows(batch) if row["style"] in confirmed):
            raise AssertionError("Recovery replaced already confirmed image commits")
        report["readme_runs"] = wait_for_readmes(client, previous_runs, timeout)

        begin = len(client.events)
        Publisher(client, inventory, ledger).publish(batch)
        report["unchanged_rerun"] = counts(client.events[begin:])
        if report["unchanged_rerun"]["mutations"]:
            raise AssertionError("An unchanged rerun performed GitHub writes")
        verified = []
        for row in ledger.rows(batch):
            target = path / "verification" / row["style"] / Path(row["path"]).name
            inventory.fetch_image(row["style"], row["path"], target)
            if file_hash(target) != row["published_hash"]:
                raise AssertionError("Downloaded sandbox image differs from prepared bytes")
            repo = row["repo"]
            readme = client.request("GET", f"/repos/{repo}/contents/README.md?ref=master")
            if row["person"] not in base64.b64decode(readme["content"]).decode("utf-8"):
                raise AssertionError("Generated README is missing the published person")
            sentinel = client.request("GET", f"/repos/{repo}/contents/sandbox-preserve.txt?ref=master")
            if base64.b64decode(sentinel["content"]) != b"Unrelated sandbox sentinel: preserve this file.\n":
                raise AssertionError("Unrelated sandbox content changed")
            verified.append({"style": row["style"], "path": row["path"], "sha256": row["published_hash"]})
        report["verified_downloads"] = verified
        sentinel = root / "models" / "sandbox-preserve.bin"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_bytes(b"Persistent sandbox model-cache sentinel")
        manager.confirm_published(batch, ledger)
        manager.deactivate(batch)
        os.environ["PEOPLE_BATCH_RETENTION_DAYS"] = "0"
        preview = manager.cleanup(dry_run=True)
        if (batch, "eligible") not in preview or not (path / "people_dirs").exists():
            raise AssertionError("Cleanup preview failed or deleted files")
        applied = manager.cleanup(dry_run=False)
        if (batch, "cleaned") not in applied or (path / "people_dirs").exists():
            raise AssertionError("Completed sandbox images were not cleaned")
        if not ledger.verified(batch) or not (path / "manifest.json").exists() or not sentinel.exists():
            raise AssertionError("Cleanup removed persistent state/models/manifest")
        if any(file_hash(Path(name)) != digest for name, digest in original_hashes.items()):
            raise AssertionError("Source validation images outside sandbox were changed")
        report["cleanup"] = {"dry_run": preview, "applied": applied, "persistent_state_preserved": True,
                             "source_images_preserved": True, "model_cache_preserved": True}
        report["production_heads_after"] = production_heads()
        report["production_heads_unchanged"] = report["production_heads_before"] == report["production_heads_after"]
        report["status"] = "passed"
        atomic_json(report_path, report)
        print(f"[PASSED] Live sandbox validation: {report_path}", flush=True)
        return report
    except BaseException as error:
        report.update(status="failed", error=safe_exception(error))
        atomic_json(report_path, report)
        raise
    finally:
        if batch:
            manager.deactivate(batch)
        if inventory:
            inventory.close()
        if ledger:
            ledger.close()
        manager.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--source-job", required=True, type=Path)
    parser.add_argument("--create-repos", action="store_true", help="Explicit permission to create the seven private test repos")
    parser.add_argument("--run", required=True, help="Unique lowercase sandbox run name")
    parser.add_argument("--workflow-timeout", type=int, default=900)
    args = parser.parse_args()
    import re
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,50}", args.run):
        parser.error("--run must be a simple unique lowercase name")
    root = SANDBOX_ROOT / args.run
    if root.exists():
        parser.error("Run directory already exists; preserve it and select a fresh --run name")
    targets = root / "targets.json"
    atomic_json(targets, {"version": 1, "owner": args.owner, "branch": "master",
                         "repositories": {style: f"{args.owner}/kometa-people-sandbox-{style}" for style in REPOSITORIES}})
    os.environ.update({"PEOPLE_GITHUB_TARGET": "sandbox", "PEOPLE_SANDBOX_CONFIG": str(targets),
                       "PEOPLE_PUBLISH_MODE": "github_api", "PEOPLE_WORKSPACE_MODE": "batch",
                       "PEOPLE_STATE_DIR": str(root / "state"), "PEOPLE_JOBS_DIR": str(root / "jobs"),
                       "UPDATE_TRIGGER_READMES": "true", "UPDATE_REQUIRE_README_DISPATCH": "true",
                       "UPDATE_README_SKIP_MARKER": "[skip readme]", "PEOPLE_AUTO_CLEANUP": "false",
                       "REMOVE_BG_ENGINE": "birefnet"})
    sandbox_settings()
    client = RecordingClient()
    created = bootstrap(client, args.owner, args.create_repos)
    atomic_json(root / "provisioning.json", {"created": created, "repositories": client.repositories})
    live_validation(client, args.source_job, root, args.workflow_timeout)


if __name__ == "__main__":
    main()
