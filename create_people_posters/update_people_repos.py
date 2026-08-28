#!/usr/bin/env python3
"""
update_people_repos.py — update OR push all category repos under PEOPLE_IMAGES_DIR

Categories: bw, diiivoy, diiivoycolor, rainier, original, signature, transparent

Ops:
  --op update   (default)  → make local exactly match remote:
      git fetch origin
      git switch <branch> (auto-create tracking if needed)
      git reset --hard origin/<branch>
      git clean -fd        (add -x when --clean-ignored)
      (optional LFS pull when --lfs=auto/on and repo uses LFS)
      If anything fails, you can extend with a reclone fallback.

  --op push               → stage, commit (if changes), and push:
      git add -A
      if changes: git commit -m "<message>"
      git push origin HEAD

Usage examples:
  # Update only (remote always wins)
  python update_people_repos.py --op update --repo-root "/path/to/Kometa-People-Images" --mode hardreset --clean-ignored

  # Push only (after sync/images/readme/md)
  python update_people_repos.py --op push --repo-root "/path/to/Kometa-People-Images" --message "chore: sync"

Common options:
  --repo-root PATH
  --branch BRANCH            (auto-detect remote HEAD if omitted)
  --mode {hardreset,ffonly}  (only for --op update; default: hardreset)
  --clean-ignored            (only for --op update; adds -x to git clean)
  --lfs {auto,on,off}        (default: auto; only used by --op update)
  --message MSG              (only for --op push; default auto message)
  --git-user-name NAME       (optional: set user.name before committing)
  --git-user-email EMAIL     (optional: set user.email before committing)
  --dry-run

Environment:
  PEOPLE_IMAGES_DIR, PEOPLE_BRANCH
  UPDATE_MODE=hardreset|ffonly
  UPDATE_CLEAN_IGNORED=true|false
  UPDATE_LFS=auto|on|off
  UPDATE_TRIGGER_READMES=true|false
  UPDATE_REQUIRE_README_DISPATCH=true|false
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

CATEGORIES = ["bw", "diiivoy", "diiivoycolor", "rainier", "original", "signature", "transparent"]
MIN_BATCH_HEADROOM_BYTES = 64 * 1024 * 1024
README_WORKFLOW = "readme.yml"


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024.0 or unit == "TiB":
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{size} B"


def safe_console(text: str) -> str:
    return text.encode("ascii", "backslashreplace").decode("ascii")


def env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def effective_batch_limit(max_push_bytes: int) -> int:
    if max_push_bytes <= 0:
        return 0
    headroom = max(MIN_BATCH_HEADROOM_BYTES, int(max_push_bytes * 0.05))
    if headroom >= max_push_bytes:
        return max_push_bytes
    return max_push_bytes - headroom


def run(cmd, cwd: Path, dry: bool, capture=False) -> Tuple[int, str, str]:
    print("->", safe_console(" ".join(cmd)), safe_console(f"(cwd={cwd})"))
    if dry:
        return 0, "", ""
    cp = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
    )
    return cp.returncode, (cp.stdout or ""), (cp.stderr or "")


def run_ok(cmd, cwd: Path, dry: bool) -> bool:
    rc, _, _ = run(cmd, cwd, dry)
    return rc == 0


def run_cap(cmd, cwd: Path, dry: bool) -> Tuple[bool, str]:
    rc, out, _ = run(cmd, cwd, dry, capture=True)
    return rc == 0, out.strip()


def remote_repo_slug(repo: Path, dry: bool) -> str:
    ok, url = run_cap(["git", "config", "--get", "remote.origin.url"], repo, dry)
    if not ok or not url:
        return ""

    url = url.strip()
    if url.endswith(".git"):
        url = url[:-4]

    lower = url.lower()
    https_marker = "github.com/"
    if https_marker in lower:
        idx = lower.index(https_marker) + len(https_marker)
        return url[idx:].strip("/")

    ssh_marker = "github.com:"
    if ssh_marker in lower:
        idx = lower.index(ssh_marker) + len(ssh_marker)
        return url[idx:].strip("/")

    return ""


def dispatch_readme_workflow(repo: Path, branch: str, dry: bool, required: bool) -> int:
    slug = remote_repo_slug(repo, dry)
    if not slug:
        print(f"[WARN] Could not determine GitHub repo slug for README dispatch: {repo}")
        return 1 if required else 0

    cmd = ["gh", "workflow", "run", README_WORKFLOW, "--repo", slug, "--ref", branch]
    print("->", safe_console(" ".join(cmd)), safe_console(f"(cwd={repo})"))
    if dry:
        return 0

    cp = subprocess.run(
        cmd,
        cwd=str(repo),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if cp.returncode == 0:
        print(f"[INFO] Dispatched {README_WORKFLOW} for {slug}@{branch}")
        return 0

    detail = (cp.stderr or cp.stdout or "").strip()
    print(f"[WARN] README workflow dispatch failed for {slug}@{branch}: {detail}")
    return 1 if required else 0


def estimate_push_payload(repo: Path, branch: str, dry: bool) -> Tuple[bool, int, int, list[tuple[str, int]]]:
    remote_ref = f"origin/{branch}"
    rc, _, _ = run(["git", "rev-parse", "--verify", remote_ref], repo, dry)
    range_expr = f"{remote_ref}..HEAD" if rc == 0 else "HEAD"
    ok, rev_list = run_cap(["git", "rev-list", "--objects", range_expr], repo, dry)
    if not ok:
        return False, 0, 0, []
    if not rev_list.strip():
        return True, 0, 0, []
    if dry:
        return True, 0, 0, []

    cp = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize) %(rest)"],
        cwd=str(repo),
        text=True,
        encoding="utf-8",
        errors="replace",
        input=rev_list + "\n",
        capture_output=True,
    )
    if cp.returncode != 0:
        return False, 0, 0, []

    total_bytes = 0
    object_count = 0
    largest_blobs: list[tuple[str, int]] = []
    for line in cp.stdout.splitlines():
        parts = line.split(" ", 3)
        if len(parts) < 3:
            continue
        object_type = parts[1]
        try:
            object_size = int(parts[2])
        except ValueError:
            continue
        object_count += 1
        total_bytes += object_size
        path_label = parts[3] if len(parts) >= 4 and parts[3].strip() else parts[0]
        if object_type == "blob":
            largest_blobs.append((path_label, object_size))

    largest_blobs.sort(key=lambda item: item[1], reverse=True)
    return True, total_bytes, object_count, largest_blobs[:20]


def remote_ref_exists(repo: Path, branch: str, dry: bool) -> bool:
    rc, _, _ = run(["git", "rev-parse", "--verify", f"origin/{branch}"], repo, dry)
    return rc == 0


def ahead_commit_count(repo: Path, branch: str, dry: bool) -> int:
    if not remote_ref_exists(repo, branch, dry):
        return 0
    ok, out = run_cap(["git", "rev-list", "--count", f"origin/{branch}..HEAD"], repo, dry)
    if not ok:
        return 0
    try:
        return int(out.strip() or "0")
    except ValueError:
        return 0


def get_staged_paths(repo: Path, dry: bool) -> Tuple[bool, list[str]]:
    if dry:
        return True, []
    cp = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--no-renames", "-z"],
        cwd=str(repo),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if cp.returncode != 0:
        return False, []
    return True, [part for part in cp.stdout.split("\0") if part]


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[idx: idx + size] for idx in range(0, len(items), size)]


def build_path_batches(repo: Path, paths: list[str], max_push_bytes: int) -> Tuple[bool, list[tuple[list[str], int]], Optional[tuple[str, int]]]:
    normalized = sorted(set(paths), key=lambda item: item.lower())
    batch_limit = effective_batch_limit(max_push_bytes)
    sized_paths: list[tuple[str, int]] = []
    for rel_path in normalized:
        abs_path = repo / rel_path
        file_size = abs_path.stat().st_size if abs_path.exists() and abs_path.is_file() else 0
        if max_push_bytes > 0 and file_size > max_push_bytes:
            return False, [], (rel_path, file_size)
        sized_paths.append((rel_path, file_size))

    if max_push_bytes <= 0:
        return True, [(normalized, sum(size for _, size in sized_paths))], None

    batches: list[tuple[list[str], int]] = []
    current_paths: list[str] = []
    current_bytes = 0
    for rel_path, file_size in sized_paths:
        if current_paths and current_bytes + file_size > batch_limit:
            batches.append((current_paths, current_bytes))
            current_paths = [rel_path]
            current_bytes = file_size
            continue
        current_paths.append(rel_path)
        current_bytes += file_size
    if current_paths:
        batches.append((current_paths, current_bytes))
    return True, batches, None


def stage_paths(repo: Path, paths: list[str], dry: bool) -> bool:
    for batch in chunked(paths, 100):
        if not run_ok(["git", "add", "-A", "--"] + batch, repo, dry):
            return False
    return True


def push_current_head(repo: Path, branch: str, dry: bool, max_push_bytes: int) -> int:
    ok, payload_bytes, object_count, largest_blobs = estimate_push_payload(repo, branch, dry)
    if not ok:
        return 1
    if max_push_bytes > 0 and payload_bytes > max_push_bytes:
        print(
            f"[ERROR] Refusing push: estimated outbound payload is {format_bytes(payload_bytes)} "
            f"across {object_count} git object(s), which exceeds the limit of {format_bytes(max_push_bytes)}."
        )
        if largest_blobs:
            print("Largest blobs in this push:")
            for path_label, blob_size in largest_blobs:
                print(f"  {format_bytes(blob_size):>10}  {path_label}")
        return 1

    if not run_ok(["git", "push", "origin", "HEAD"], repo, dry):
        return 0 if run_ok(["git", "push", "origin", branch], repo, dry) else 1
    return 0


def reset_ahead_commits_to_worktree(repo: Path, branch: str, dry: bool) -> bool:
    if not remote_ref_exists(repo, branch, dry):
        print(f"[ERROR] Cannot re-batch unpushed commits because origin/{branch} is not available.")
        return False
    print(f"[INFO] Rewriting local-only commits back into the worktree for batched push against origin/{branch}.")
    return run_ok(["git", "reset", "--mixed", f"origin/{branch}"], repo, dry)


def commit_batches(repo: Path, branch: str, message: str, dry: bool, max_push_bytes: int, paths: list[str]) -> int:
    ok, batches, oversized = build_path_batches(repo, paths, max_push_bytes)
    if not ok:
        assert oversized is not None
        rel_path, file_size = oversized
        print(
            f"[ERROR] Cannot batch this push because a single file exceeds the limit: "
            f"{rel_path} ({format_bytes(file_size)} > {format_bytes(max_push_bytes)})."
        )
        return 1
    if not batches:
        print("  (nothing to commit)")
        return 0

    batch_limit = effective_batch_limit(max_push_bytes)
    total_batches = len(batches)
    print(
        f"[INFO] Creating {total_batches} push batch(es) with a {format_bytes(batch_limit)} working-set target "
        f"to stay below the {format_bytes(max_push_bytes)} push limit."
    )
    for idx, (batch_paths, batch_bytes) in enumerate(batches, start=1):
        if not stage_paths(repo, batch_paths, dry):
            return 1
        batch_message = message if total_batches == 1 else f"{message} [batch {idx}/{total_batches}]"
        print(
            f"[INFO] Batch {idx}/{total_batches}: {len(batch_paths)} path(s), "
            f"estimated working-set size {format_bytes(batch_bytes)}."
        )
        if not run_ok(["git", "commit", "-m", batch_message], repo, dry):
            return 1
        rc = push_current_head(repo, branch, dry, max_push_bytes)
        if rc != 0:
            return rc
    return 0


def detect_remote_head_branch(repo: Path, dry: bool) -> str:
    ok, out = run_cap(["git", "remote", "show", "origin"], repo, dry)
    if ok:
        for line in out.splitlines():
            if line.lower().startswith("head branch:"):
                return line.split(":", 1)[1].strip()
    for b in ("main", "master"):
        rc, _, _ = run(["git", "rev-parse", "--verify", f"origin/{b}"], repo, dry)
        if rc == 0:
            return b
    ok, out = run_cap(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo, dry)
    return out or "master"


def current_branch(repo: Path, dry: bool) -> str:
    ok, out = run_cap(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo, dry)
    return out if ok and out else "master"


def repo_uses_lfs(repo: Path, dry: bool) -> bool:
    gattr = repo / ".gitattributes"
    if not gattr.exists():
        return False
    try:
        txt = gattr.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return "filter=lfs" in txt


def git_lfs_available(cwd: Path, dry: bool) -> bool:
    rc, _, _ = run(["git", "lfs", "version"], cwd, dry)
    return rc == 0


def ensure_remote_match(repo: Path, branch: str, mode: str, clean_ignored: bool, lfs_mode: str, dry: bool) -> bool:
    # fetch
    if not run_ok(["git", "fetch", "origin"], repo, dry):
        return False

    # switch (create tracking if needed)
    if not run_ok(["git", "switch", branch], repo, dry):
        run_ok(["git", "switch", "-c", branch, "--track", f"origin/{branch}"], repo, dry)

    if mode == "hardreset":
        if not run_ok(["git", "reset", "--hard", f"origin/{branch}"], repo, dry):
            return False
        clean_args = ["git", "clean", "-fd"]
        if clean_ignored:
            clean_args.append("-x")
        if not run_ok(clean_args, repo, dry):
            return False
    else:
        if not run_ok(["git", "merge", "--ff-only", f"origin/{branch}"], repo, dry):
            return False

    # LFS pull if applicable
    if lfs_mode in ("on", "auto") and repo_uses_lfs(repo, dry) and git_lfs_available(repo, dry):
        run_ok(["git", "lfs", "pull"], repo, dry)

    return True


def commit_and_push(repo: Path, branch: Optional[str], message: str,
                    user_name: str, user_email: str, dry: bool, max_push_bytes: int) -> int:
    # set author config if provided
    if user_name:
        run_ok(["git", "config", "user.name", user_name], repo, dry)
    if user_email:
        run_ok(["git", "config", "user.email", user_email], repo, dry)

    # ensure branch value
    if not branch:
        ok, cur = run_cap(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo, dry)
        branch = cur if ok and cur else "master"

    # stage everything so we can inspect the full pending change set
    if not run_ok(["git", "add", "-A"], repo, dry):
        return 1

    ok, staged_paths = get_staged_paths(repo, dry)
    if not ok:
        return 1
    has_local_changes = bool(staged_paths)
    ahead_count = ahead_commit_count(repo, branch, dry)

    if ahead_count > 0 and (has_local_changes or max_push_bytes > 0):
        ok, payload_bytes, _, _ = estimate_push_payload(repo, branch, dry)
        if not ok:
            return 1
        if has_local_changes or (max_push_bytes > 0 and payload_bytes > max_push_bytes):
            if not reset_ahead_commits_to_worktree(repo, branch, dry):
                return 1
            if not run_ok(["git", "add", "-A"], repo, dry):
                return 1
            ok, staged_paths = get_staged_paths(repo, dry)
            if not ok:
                return 1
            has_local_changes = bool(staged_paths)
            ahead_count = 0

    if has_local_changes:
        if not run_ok(["git", "reset"], repo, dry):
            return 1
        return commit_batches(repo, branch, message, dry, max_push_bytes, staged_paths)

    if ahead_count == 0:
        print("  (no changes to commit)")
        return 0

    print(f"[INFO] No working tree changes, but {ahead_count} local commit(s) are ahead of origin/{branch}.")
    return push_current_head(repo, branch, dry, max_push_bytes)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Update or push category repos")
    parser.add_argument("--op", choices=["update", "push"], default="update")
    parser.add_argument("--repo-root", help="Root folder for category repos (env PEOPLE_IMAGES_DIR)")
    parser.add_argument("--branch", help="Branch to track/push (env PEOPLE_BRANCH; auto-detect if omitted)")
    parser.add_argument("--mode", choices=["hardreset", "ffonly"],
                        default=os.getenv("UPDATE_MODE", "hardreset").lower(),
                        help="Only used with --op update")
    parser.add_argument("--clean-ignored", action="store_true",
                        help="With --op update and hardreset, also remove ignored files (-x)")
    parser.add_argument("--lfs", choices=["auto", "on", "off"],
                        default=os.getenv("UPDATE_LFS", "auto").lower(),
                        help="Only used with --op update; pull LFS files when repo uses LFS")
    parser.add_argument("--message", help="Commit message (only used with --op push)")
    parser.add_argument("--git-user-name", help="Set git user.name locally before commit (push op)")
    parser.add_argument("--git-user-email", help="Set git user.email locally before commit (push op)")
    parser.add_argument(
        "--max-push-bytes",
        type=int,
        default=int(os.getenv("UPDATE_MAX_PUSH_BYTES", str(1024 ** 3))),
        help="Fail push when estimated outbound git payload exceeds this many bytes. Use 0 to disable.",
    )
    parser.add_argument(
        "--trigger-readmes",
        action=argparse.BooleanOptionalAction,
        default=env_bool("UPDATE_TRIGGER_READMES", True),
        help="After --op push, dispatch readme.yml for every category repo. Default: true.",
    )
    parser.add_argument(
        "--require-readme-dispatch",
        action=argparse.BooleanOptionalAction,
        default=env_bool("UPDATE_REQUIRE_README_DISPATCH", False),
        help="Fail --op push if a README workflow dispatch fails. Default: false.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root or os.getenv("PEOPLE_IMAGES_DIR", "")).expanduser().resolve()
    if not repo_root.exists():
        print(f"[ERROR] Repo root not found: {repo_root}")
        sys.exit(2)

    branch_arg = args.branch or os.getenv("PEOPLE_BRANCH")

    rc_total = 0
    pushed_repos: list[tuple[str, Path, str]] = []
    for cat in CATEGORIES:
        repo = repo_root / cat
        if not repo.exists():
            print(f"[WARN] Skipping missing category folder: {repo}")
            continue

        if args.op == "update":
            # determine branch per-repo if not provided
            branch = branch_arg or detect_remote_head_branch(repo, args.dry_run)
            print(f"=== UPDATE {cat} (branch: {branch}, mode: {args.mode}) ===")
            ok = ensure_remote_match(repo, branch, args.mode, args.clean_ignored, args.lfs, args.dry_run)
            rc_total |= (not ok)
        else:
            # push op
            # for push, default to current branch if not specified
            push_branch = branch_arg or current_branch(repo, args.dry_run)
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            msg = args.message or f"chore: sync posters & docs - {now}"
            print(f"=== PUSH {cat} ===")
            rc = commit_and_push(
                repo,
                push_branch,
                msg,
                args.git_user_name or "",
                args.git_user_email or "",
                args.dry_run,
                args.max_push_bytes,
            )
            rc_total |= (rc != 0)
            pushed_repos.append((cat, repo, push_branch))

    if args.op == "push" and args.trigger_readmes and rc_total == 0:
        print("=== DISPATCH README WORKFLOWS ===")
        for cat, repo, branch in pushed_repos:
            print(f"=== README {cat} ===")
            rc = dispatch_readme_workflow(repo, branch, args.dry_run, args.require_readme_dispatch)
            rc_total |= (rc != 0)
    elif args.op == "push" and args.trigger_readmes:
        print("[WARN] Skipping README workflow dispatch because one or more repo pushes failed.")

    sys.exit(0 if rc_total == 0 else 1)


if __name__ == "__main__":
    main()
