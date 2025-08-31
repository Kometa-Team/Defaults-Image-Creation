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
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

CATEGORIES = ["bw", "diiivoy", "diiivoycolor", "rainier", "original", "signature", "transparent"]


def run(cmd, cwd: Path, dry: bool, capture=False) -> Tuple[int, str, str]:
    print("→", " ".join(cmd), f"(cwd={cwd})")
    if dry:
        return 0, "", ""
    cp = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=capture)
    return cp.returncode, (cp.stdout or ""), (cp.stderr or "")


def run_ok(cmd, cwd: Path, dry: bool) -> bool:
    rc, _, _ = run(cmd, cwd, dry)
    return rc == 0


def run_cap(cmd, cwd: Path, dry: bool) -> Tuple[bool, str]:
    rc, out, _ = run(cmd, cwd, dry, capture=True)
    return rc == 0, out.strip()


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
                    user_name: str, user_email: str, dry: bool) -> int:
    # set author config if provided
    if user_name:
        run_ok(["git", "config", "user.name", user_name], repo, dry)
    if user_email:
        run_ok(["git", "config", "user.email", user_email], repo, dry)

    # stage everything
    if not run_ok(["git", "add", "-A"], repo, dry):
        return 1

    # any changes?
    ok, status = run_cap(["git", "status", "--porcelain"], repo, dry)
    if not ok:
        return 1
    if not status.strip():
        print("  (no changes to commit)")
        return 0

    # commit
    if not run_ok(["git", "commit", "-m", message], repo, dry):
        return 1

    # ensure branch value
    if not branch:
        ok, cur = run_cap(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo, dry)
        branch = cur if ok and cur else "master"

    # push
    if not run_ok(["git", "push", "origin", "HEAD"], repo, dry):
        # fallback to named branch push
        return 0 if run_ok(["git", "push", "origin", branch], repo, dry) else 1
    return 0


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
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root or os.getenv("PEOPLE_IMAGES_DIR", "")).expanduser().resolve()
    if not repo_root.exists():
        print(f"[ERROR] Repo root not found: {repo_root}")
        sys.exit(2)

    branch_arg = args.branch or os.getenv("PEOPLE_BRANCH")

    rc_total = 0
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
            push_branch = branch_arg
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            msg = args.message or f"chore: sync posters & docs — {now}"
            print(f"=== PUSH {cat} ===")
            rc = commit_and_push(repo, push_branch, msg, args.git_user_name or "", args.git_user_email or "", args.dry_run)
            rc_total |= (rc != 0)

    sys.exit(0 if rc_total == 0 else 1)


if __name__ == "__main__":
    main()