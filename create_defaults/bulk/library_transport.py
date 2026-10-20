"""Offline-only Git batching and recovery. Network remotes are not supported."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from .common import BulkError, confined, fingerprint, reject_links, sha256
from .library_publication import validate_paths
from .library_sources import check_seal, load_json, save, sealed


def git(root, *args, binary=False):
    reject_links(root)
    result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                            text=not binary, timeout=180)
    return result.stdout if binary else result.stdout.strip()


def verify_batch(repo, before, after, members):
    changed = set(git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", before, after, binary=True).decode().strip("\0").split("\0"))
    expected = {m["destination"] for m in members}
    if changed != expected:
        raise BulkError("unexpected_diff", "Commit contains missing or unexpected destinations")
    import hashlib
    for member in members:
        data = git(repo, "show", after + ":" + member["destination"], binary=True)
        if hashlib.sha256(data).hexdigest() != member["sha256"]:
            raise BulkError("remote_hash", "Offline Git commit bytes differ from approved Python output")


def run(plan, root, base_repository, *, stop_after=None, fail_at=None):
    """Exercise local commits/pushes; interruption points test ambiguous outcomes.

    Base repository is read-only. All mutable repositories live under the owned
    exercise root. Resuming verifies every prior commit and remote artifact.
    """
    check_seal(plan)
    if plan.get("kind") != "local-git-batch-plan":
        raise BulkError("invalid_plan", "A sealed local Git batch plan is required")
    members = [m for b in plan["batches"] for m in b["members"]]
    validate_paths(members)
    for batch in plan["batches"]:
        if batch["membership_sha256"] != fingerprint(batch["members"]):
            raise BulkError("corrupt_batch", "Batch membership changed")
        if len(batch["members"]) > plan["max_files"] or sum(m["size"] for m in batch["members"]) > plan["max_bytes"]:
            raise BulkError("batch_limits", "Batch exceeds the approved technical limits")
    base_repository = reject_links(base_repository).resolve()
    if not base_repository.is_dir():
        raise BulkError("offline_only", "Base must be an existing local repository directory")
    baseline = plan["baseline"]["head"]
    if git(base_repository, "rev-parse", "HEAD") != baseline:
        raise BulkError("baseline_drift", "Local target baseline moved; prepare a fresh approved manifest")
    root = reject_links(root).resolve()
    if root == base_repository or base_repository.is_relative_to(root) or root.is_relative_to(base_repository):
        raise BulkError("unsafe_workspace", "Offline exercise must be isolated from source repository")
    marker = root / "exercise.json"
    repo, remote = root / "work", root / "remote.git"
    for path in (marker, repo, repo / ".git", remote):
        reject_links(path)
    if root.exists() and not marker.exists():
        raise BulkError("unowned_workspace", "Refusing an existing unowned exercise directory")
    if not marker.exists():
        root.mkdir(parents=True)
        save(marker, {"plan_sha256": plan["sha256"], "baseline": baseline, "commits": []})
        subprocess.run(["git", "clone", "--no-hardlinks", "--no-local", str(base_repository), str(repo)], check=True, capture_output=True, timeout=180)
        git(repo, "remote", "remove", "origin")
        git(repo, "checkout", "-B", "library-offline", baseline)
        git(repo, "config", "user.name", "Library offline exercise")
        git(repo, "config", "user.email", "offline-library@invalid.local")
        git(repo, "config", "core.autocrlf", "false")
        git(repo, "config", "core.hooksPath", str(root / "no-hooks"))
        subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
        git(repo, "push", str(remote), baseline + ":refs/heads/library-offline")
    state = load_json(marker)
    if (not (repo / ".git").is_dir()
            or Path(git(repo, "rev-parse", "--absolute-git-dir")).resolve() != repo / ".git"
            or Path(git(repo, "rev-parse", "--show-toplevel")).resolve() != repo
            or Path(git(remote, "rev-parse", "--absolute-git-dir")).resolve() != remote):
        raise BulkError("unsafe_workspace", "Offline Git directories must stay inside the owned exercise root")
    if state.get("plan_sha256") != plan["sha256"] or state.get("baseline") != baseline:
        raise BulkError("stale_plan", "Exercise belongs to a different approved plan")
    if git(repo, "remote") or git(repo, "status", "--porcelain"):
        raise BulkError("unexpected_worktree", "Exercise contains a configured remote or unrelated modifications")
    chain = git(repo, "rev-list", "--reverse", baseline + "..HEAD").splitlines()
    if len(chain) > len(plan["batches"]):
        raise BulkError("unexpected_commit", "Unexpected commits in offline exercise")
    before = baseline
    # Recover from interruption after a local commit, before checkpoint or push.
    for commit, batch in zip(chain, plan["batches"]):
        if git(repo, "rev-parse", commit + "^") != before:
            raise BulkError("unexpected_history", "Exercise commit ancestry changed")
        verify_batch(repo, before, commit, batch["members"])
        before = commit
    remote_head = git(remote, "rev-parse", "refs/heads/library-offline")
    if remote_head not in [baseline, *chain]:
        raise BulkError("remote_drift", "Offline remote contains unrelated history")
    known = state["commits"]
    if chain[:len(known)] != known:
        raise BulkError("journal_drift", "Recorded commit history differs")
    started = time.monotonic()
    pack_observations = []
    for index, batch in enumerate(plan["batches"]):
        if index < len(chain):
            commit = chain[index]
        else:
            for member in batch["members"]:
                source = reject_links(member["source"])
                if sha256(source) != member["sha256"] or source.stat().st_size != member["size"]:
                    raise BulkError("candidate_hash", "Approved bytes changed before staging")
                target = confined(repo, member["destination"])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            git(repo, "add", "--", *[m["destination"] for m in batch["members"]])
            git(repo, "commit", "-m", f"Offline approved library batch {index + 1}: {batch['membership_sha256']}")
            commit = git(repo, "rev-parse", "HEAD")
            previous = baseline if index == 0 else chain[index - 1]
            verify_batch(repo, previous, commit, batch["members"])
            chain.append(commit)
            if fail_at == "after_commit":
                raise BulkError("injected_interruption", "After commit, before journal and push")
        # Measure an incremental pack against the preceding verified batch. This
        # bounds object transfer separately from approved artwork membership.
        pack = confined(root, "packs/" + commit + ".pack")
        pack.parent.mkdir(exist_ok=True)
        previous = baseline if index == 0 else chain[index - 1]
        with pack.open("wb") as stream:
            subprocess.run(["git", "-C", str(repo), "pack-objects", "--stdout", "--revs"],
                           input=(commit + "\n^" + previous + "\n").encode(), stdout=stream,
                           stderr=subprocess.PIPE, check=True, timeout=180)
        pack_observations.append({"sequence": index + 1, "pack_bytes": pack.stat().st_size,
                                  "artifact_bytes": batch["bytes"]})
        if pack.stat().st_size > plan["max_pack_bytes"]:
            raise BulkError("pack_limit", "Measured incremental Git pack exceeds the technical cap")
        # A normal push reconciles both absent and ambiguously completed pushes.
        current_remote = git(remote, "rev-parse", "refs/heads/library-offline")
        if current_remote in chain[index + 1:]:
            pass  # Remote already includes this verified prefix.
        else:
            git(repo, "push", str(remote), commit + ":refs/heads/library-offline")
        verify_batch(remote, baseline if index == 0 else chain[index - 1], commit, batch["members"])
        if fail_at == "after_push":
            raise BulkError("injected_interruption", "After push, before journal")
        state["commits"] = chain[:index + 1]
        save(marker, state)
        if stop_after and index + 1 >= stop_after:
            break
    report = sealed({"schema_version": 1, "plan_sha256": plan["sha256"], "baseline": baseline,
                     "verified_batches": len(state["commits"]), "planned_batches": len(plan["batches"]),
                     "complete": len(state["commits"]) == len(plan["batches"]),
                     "remote": str(remote), "commits": state["commits"], "network_writes": 0,
                     "incremental_packs": pack_observations,
                     "object_statistics": git(remote, "count-objects", "-v"),
                     "seconds": time.monotonic() - started})
    save(root / "report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base-repository", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(run(load_json(args.plan), args.root, args.base_repository), indent=2))


if __name__ == "__main__":
    main()
