"""
Update each category repo inside the Kometa-People-Images root, like:

  cd <root>/<cat>
  git checkout <branch>
  git -c fetch.parallel=0 -c submodule.fetchJobs=0 fetch --progress --all
  git merge origin/<branch>

Cross-platform, with logging + progress.

Usage:
  python update_people_repos.py --repo-root "D:/bullmoose20/Kometa-People-Images" --branch master

Env overrides:
  PEOPLE_IMAGES_DIR   -> repo root path (default: ./Kometa-People-Images next to this script)
  PEOPLE_BRANCH       -> branch to use (default: master)
"""

import os
import sys
import argparse
import logging
import subprocess
from pathlib import Path
from timeit import default_timer as timer

from dotenv import load_dotenv
from alive_progress import alive_bar

# ---------- paths + logging (same template you shared) ----------
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
for d in (CONFIG_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)


def setup_logging(level=logging.INFO, console=True):
    log_file = LOGS_DIR / f"{SCRIPT_PATH.stem}.log"
    handlers = [logging.FileHandler(log_file, encoding="utf-8", mode="w")]
    if console:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.info("Logging → %s", log_file)
    return log_file


setup_logging()
load_dotenv(CONFIG_DIR / ".env")

# ---------- categories ----------
CATEGORIES = [
    "bw",
    "diiivoy",
    "diiivoycolor",
    "original",
    "rainier",
    "signature",
    "transparent",
]


# ---------- helpers ----------
def run(cmd, cwd: Path) -> subprocess.CompletedProcess:
    """Run a command, return CompletedProcess, log output."""
    logging.debug("RUN (%s): %s", cwd, " ".join(cmd))
    cp = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        shell=False,
        check=False,
    )
    if cp.stdout:
        logging.debug("STDOUT:\n%s", cp.stdout.strip())
    if cp.stderr:
        # git prints progress to stderr; keep it at INFO
        logging.info("STDERR:\n%s", cp.stderr.strip())
    return cp


def ensure_git_available():
    try:
        cp = subprocess.run(["git", "--version"], text=True, capture_output=True)
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr.strip() or "git not found")
        logging.info(cp.stdout.strip())
    except Exception as e:
        logging.error("Git is required but not available: %s", e)
        sys.exit(1)


def is_git_repo(path: Path) -> bool:
    return (path / ".git").is_dir()


def checkout_branch(repo_dir: Path, branch: str) -> bool:
    """
    Try to checkout <branch>. If it doesn't exist locally but exists on origin,
    create it tracking origin/<branch>.
    """
    # Does local branch exist?
    has_local = run(["git", "show-ref", "--verify", f"refs/heads/{branch}"], repo_dir).returncode == 0
    if has_local:
        cp = run(["git", "checkout", branch], repo_dir)
        return cp.returncode == 0

    # Try checkout tracking remote if it exists
    has_remote = run(["git", "ls-remote", "--heads", "origin", branch], repo_dir)
    if has_remote.returncode == 0 and has_remote.stdout.strip():
        cp = run(["git", "checkout", "-B", branch, f"origin/{branch}"], repo_dir)
        return cp.returncode == 0

    # Fallback: try simple checkout anyway
    cp = run(["git", "checkout", branch], repo_dir)
    return cp.returncode == 0


def fetch_all(repo_dir: Path) -> bool:
    cp = run(["git", "-c", "fetch.parallel=0", "-c", "submodule.fetchJobs=0",
              "fetch", "--progress", "--all"], repo_dir)
    return cp.returncode == 0


def merge_origin(repo_dir: Path, branch: str) -> bool:
    cp = run(["git", "merge", f"origin/{branch}"], repo_dir)
    # Non-zero may indicate conflicts; we still report outcome
    return cp.returncode == 0


# ---------- main ----------
def main():
    parser = argparse.ArgumentParser(description="Update per-category repos (checkout/fetch/merge).")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(os.getenv("PEOPLE_IMAGES_DIR") or (SCRIPT_DIR / "Kometa-People-Images")),
        help="Path to Kometa-People-Images root (default: PEOPLE_IMAGES_DIR or ./Kometa-People-Images)",
    )
    parser.add_argument(
        "--branch",
        default=os.getenv("PEOPLE_BRANCH", "master"),
        help="Branch to update (default: env PEOPLE_BRANCH or 'master')",
    )
    args = parser.parse_args()

    ensure_git_available()

    start = timer()
    repo_root = args.repo_root
    branch = args.branch

    logging.info("Repo root : %s", repo_root)
    logging.info("Branch    : %s", branch)

    total = len(CATEGORIES)
    updated_ok = 0
    skipped = 0
    failed = 0

    with alive_bar(total, dual_line=True, title="git update") as bar:
        for cat in CATEGORIES:
            subdir = repo_root / cat
            bar.text = f"-> opening: {subdir}"
            logging.info("------ %s ------", cat)

            if not subdir.exists():
                logging.warning("Missing: %s (skip)", subdir)
                skipped += 1
                bar()
                continue
            if not is_git_repo(subdir):
                logging.warning("Not a git repo: %s (skip)", subdir)
                skipped += 1
                bar()
                continue

            ok = True

            bar.text = f"-> checkout {branch} @ {cat}"
            if not checkout_branch(subdir, branch):
                logging.error("[%s] checkout %s failed", cat, branch)
                ok = False

            if ok:
                bar.text = f"-> fetch --all @ {cat}"
                if not fetch_all(subdir):
                    logging.error("[%s] fetch failed", cat)
                    ok = False

            if ok:
                bar.text = f"-> merge origin/{branch} @ {cat}"
                if not merge_origin(subdir, branch):
                    # Merge conflicts or non-ff merge returns non-zero.
                    logging.error("[%s] merge origin/%s had issues (check logs)", cat, branch)
                    # still count as failed; you can choose to count this separately
                    ok = False

            if ok:
                updated_ok += 1
                logging.info("[%s] OK", cat)
            else:
                failed += 1

            bar()

    elapsed = timer() - start
    logging.info("Summary: ok=%d, skipped=%d, failed=%d", updated_ok, skipped, failed)
    logging.info("Done in %.2fs", elapsed)
    print(f"Done in {elapsed:.2f}s (ok={updated_ok}, skipped={skipped}, failed={failed})")


if __name__ == "__main__":
    main()
