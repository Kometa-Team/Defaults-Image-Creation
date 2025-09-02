#!/usr/bin/env python3
"""
orchestrator.py — fixed-order, resumable pipeline runner (replaces runit.cmd)

Key behavior
------------
- Enforces a single, correct step order. Users CANNOT reorder steps.
- Checkpoints each step to allow resume after Ctrl-C/crash.
- Default mode: resume from the first step that isn't completed.
- Tools read defaults from ./config/.env; override some paths via CLI.
- Uses sys.executable so it works the same on Windows/macOS/Linux.

Core steps (order is enforced; do not reorder):
  1) ensure_repo      -> ensure_people_repo.py              (always runs: cheap sanity check)
  2) name_check       -> name_checker_dir.py                (checkpointed)
  3) missing          -> get_missing_people.py              (checkpointed)
  4) tmdb             -> tmdb_people.py                     (checkpointed)
  5) truncate         -> truncate_tmdb_people_names.py      (checkpointed)
  6) missing_dir      -> get_missing_people_dir.py          (checkpointed)
  7) prep_dirs        -> prep_people_dirs.py                (checkpointed)
  8) remove_bg        -> sel_remove_bg.py                   (checkpointed)
  9) poster_ps1       -> create_people_poster.ps1           (checkpointed; requires PowerShell/pwsh)
 10) update           -> update_people_repos.py --op update (ALWAYS runs when reached)
 11) sync_images      -> sync_people_images.py              (checkpointed)
 12) readme           -> auto_readme.py                     (checkpointed)
 13) sync_md          -> sync_md.py                         (checkpointed)
 14) push             -> update_people_repos.py --op push   (ALWAYS runs when reached)

Common CLI usage
----------------
  python orchestrator.py              # resume from the first incomplete step
  python orchestrator.py --from tmdb  # start at a given step (still in fixed order)
  python orchestrator.py --force      # ignore checkpoints and run all steps
  python orchestrator.py --list       # show step status & which step would run next
  python orchestrator.py --redo readme  # re-run from "readme": clears its checkpoint and those after

Environment (./config/.env or process environment)
--------------------------------------------------
  ORCH_LOGS_DIR       — Kometa logs folder for steps 2–3 (optional)
  PEOPLE_IMAGES_DIR   — repo root for steps needing the People-Images repo
  PEOPLE_BRANCH       — git branch for update/push (optional)
  ORCH_STYLE          — style for README & MD sync (default: transparent)
  ORCH_COMMIT_MESSAGE — optional commit message template for push
  ORCH_GIT_USER_NAME  — optional git author.name override for push
  ORCH_GIT_USER_EMAIL — optional git author.email override for push
"""
import os
import sys
import shlex
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"
STATE_DIR = CONFIG_DIR / ".orch"           # checkpoint folder
LOCK_FILE = STATE_DIR / "run.lock"         # crude run lock to prevent concurrent runs


def env_path(key: str, default: str | None = None) -> Optional[Path]:
    value = os.getenv(key, default if default is not None else "")
    return Path(value).expanduser().resolve() if value else None


def load_env_or_bootstrap() -> None:
    """Load ./config/.env; if missing, try to copy from .env.example and exit with guidance."""
    if load_dotenv:
        env_file = CONFIG_DIR / ".env"
        if not env_file.exists():
            example = CONFIG_DIR / ".env.example"
            try:
                example_src = SCRIPT_DIR / ".env.example"  # fallback at repo root
                content = (example.read_text(encoding="utf-8")
                           if example.exists()
                           else example_src.read_text(encoding="utf-8"))
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                env_file.write_text(content, encoding="utf-8")
            except Exception:
                pass
            print(f"Missing ./config/.env — created one from example.\n"
                  f"Please set at least TMDB_KEY inside: {env_file}",
                  file=sys.stderr)
            sys.exit(1)
        load_dotenv(env_file)


def ps_exe() -> Optional[str]:
    """Find a usable PowerShell executable, preferring pwsh (Core)."""
    candidates = ["pwsh"]
    if sys.platform.startswith("win"):
        candidates += ["powershell", "powershell.exe"]
    for exe in candidates:
        try:
            cp = subprocess.run([exe, "-NoLogo", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.Major"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if cp.returncode == 0:
                return exe
        except Exception:
            continue
    return None


# ---------------------- Step registry & helpers ----------------------
class Step:
    def __init__(self, key: str, title: str, builder, marker: Optional[str], always_run: bool = False):
        """
        key: stable identifier (used in CLI and checkpoint filenames)
        title: friendly name
        builder: callable () -> List[str] | None  (argv for subprocess, or None to skip)
        marker: filename under STATE_DIR to mark success (None => never checkpoint)
        always_run: ignore checkpoint (used for cheap validation or volatile ops like git)
        """
        self.key = key
        self.title = title
        self.builder = builder
        self.marker = marker
        self.always_run = always_run

    @property
    def marker_path(self) -> Optional[Path]:
        return (STATE_DIR / self.marker) if self.marker else None


def write_marker(marker: Path, meta: dict) -> None:
    marker.parent.mkdir(parents=True, exist_ok=True)
    tmp = marker.with_suffix(marker.suffix + ".tmp")
    tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(marker)


def clear_from(step_keys: List[str], from_key: str) -> None:
    """Delete checkpoints starting at from_key (inclusive) to allow re-run of downstream steps."""
    do_clear = False
    for k in step_keys:
        if k == from_key:
            do_clear = True
        if do_clear:
            mp = STATE_DIR / f"{k}.done.json"
            if mp.exists():
                try:
                    mp.unlink()
                except Exception:
                    pass


def marker_exists(marker: Optional[Path]) -> bool:
    return bool(marker and marker.exists())


def run_cmd(title: str, argv: List[str]) -> int:
    print(f"\n=== {title} ===")
    print("→", " ".join(shlex.quote(a) for a in argv))
    try:
        cp = subprocess.run(argv, cwd=str(SCRIPT_DIR))
        return cp.returncode
    except FileNotFoundError as e:
        print(f"[ERROR] {title}: {e}", file=sys.stderr)
        return 127
    except Exception as e:
        print(f"[ERROR] {title}: {e}", file=sys.stderr)
        return 1


def acquire_lock() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        print("[ERROR] Another orchestrator run appears to be in progress (lock file present).", file=sys.stderr)
        print(f"If you're sure no other run is active, delete: {LOCK_FILE}", file=sys.stderr)
        sys.exit(3)
    LOCK_FILE.write_text(f"{os.getpid()} @ {datetime.now().isoformat()}", encoding="utf-8")


def release_lock() -> None:
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass


def main():
    import argparse
    load_env_or_bootstrap()

    parser = argparse.ArgumentParser(description="Fixed-order, resumable pipeline runner")
    parser.add_argument("--from", dest="from_key", help="Start at this step key (enforced order).")
    parser.add_argument("--force", action="store_true", help="Ignore checkpoints and run all steps from the beginning.")
    parser.add_argument("--redo", help="Clear checkpoint for this step (and downstream) then run from it.")
    parser.add_argument("--list", action="store_true", help="List step status and exit.")
    parser.add_argument("--logs-dir", help="Kometa logs folder for steps name_check/missing (env ORCH_LOGS_DIR otherwise).")
    parser.add_argument("--repo-root", help="Kometa-People-Images repository root (env PEOPLE_IMAGES_DIR otherwise).")
    parser.add_argument("--branch", help="Git branch for update/push (env PEOPLE_BRANCH or auto-detect).")
    parser.add_argument("--style", help="People-Images style for README & MD sync (env ORCH_STYLE or 'transparent').")
    args = parser.parse_args()

    # Resolve env/args
    logs_dir = Path(args.logs_dir).expanduser().resolve() if args.logs_dir else env_path("ORCH_LOGS_DIR")
    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else env_path("PEOPLE_IMAGES_DIR")
    branch = args.branch or os.getenv("PEOPLE_BRANCH", "")
    style = args.style or os.getenv("ORCH_STYLE", "transparent")
    commit_template = os.getenv("ORCH_COMMIT_MESSAGE", "")
    git_user_name = os.getenv("ORCH_GIT_USER_NAME", "")
    git_user_email = os.getenv("ORCH_GIT_USER_EMAIL", "")

    # Build step builders
    py = sys.executable

    def _ensure_repo():
        args2 = ["--repo-root", str(repo_root)] if repo_root else []
        return [py, "ensure_people_repo.py"] + args2

    def _name_check():
        if not logs_dir or not logs_dir.exists():
            print("[ERROR] ORCH_LOGS_DIR not set or missing. Use --logs-dir.", file=sys.stderr)
            return None
        return [py, "name_checker_dir.py", "--input_directory", str(logs_dir)]

    def _missing():
        if not logs_dir or not logs_dir.exists():
            print("[ERROR] ORCH_LOGS_DIR not set or missing. Use --logs-dir.", file=sys.stderr)
            return None
        return [py, "get_missing_people.py", "--input_directory", str(logs_dir)]

    def _tmdb():
        return [py, "tmdb_people.py"]

    def _truncate():
        return [py, "truncate_tmdb_people_names.py"]

    def _missing_dir():
        return [py, "get_missing_people_dir.py"]

    def _prep_dirs():
        return [py, "prep_people_dirs.py"]

    def _remove_bg():
        return [py, "sel_remove_bg.py"]

    def _poster_ps1():
        ps = ps_exe()
        if not ps:
            print("[WARN] PowerShell (pwsh) not found — skipping create_people_poster.ps1", file=sys.stderr)
            return None
        ps1 = str((SCRIPT_DIR / "create_people_poster.ps1").resolve())
        return [ps, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1]

    def _update_repos():
        args2 = []
        if not repo_root or not repo_root.exists():
            print("[ERROR] PEOPLE_IMAGES_DIR not set or invalid; required by update/push.", file=sys.stderr)
            return None
        args2 += ["--repo-root", str(repo_root)]
        if branch:
            args2 += ["--branch", branch]
        args2 += ["--op", "update", "--mode", "hardreset", "--clean-ignored"]
        return [py, "update_people_repos.py"] + args2

    def _sync_images():
        if not repo_root or not repo_root.exists():
            print("[ERROR] PEOPLE_IMAGES_DIR not set or invalid; required by sync_images.", file=sys.stderr)
            return None
        return [py, "sync_people_images.py", "--dest_root", str(repo_root)]

    def _auto_readme():
        if not repo_root or not repo_root.exists():
            print("[ERROR] PEOPLE_IMAGES_DIR not set or invalid; required by readme.", file=sys.stderr)
            return None
        return [py, "auto_readme.py", "--style", style, "--directory", str((repo_root / style).resolve())]

    def _sync_md():
        if not repo_root or not repo_root.exists():
            print("[ERROR] PEOPLE_IMAGES_DIR not set or invalid; required by sync_md.", file=sys.stderr)
            return None
        src = str((repo_root / style).resolve())
        dst = str((CONFIG_DIR / "people_dirs" / style).resolve())
        return [py, "sync_md.py", "--src", src, "--dst", dst, "--pattern", "*.md"]

    def _push_repos():
        if not repo_root or not repo_root.exists():
            print("[ERROR] PEOPLE_IMAGES_DIR not set or invalid; required by push.", file=sys.stderr)
            return None
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        msg = (os.getenv("ORCH_COMMIT_MESSAGE", "") or f"chore: sync posters & docs [{style}] — {now}").strip()
        args2 = ["--repo-root", str(repo_root)]
        if branch:
            args2 += ["--branch", branch]
        args2 += ["--op", "push", "--message", msg]
        if git_user_name:
            args2 += ["--git-user-name", git_user_name]
        if git_user_email:
            args2 += ["--git-user-email", git_user_email]
        return [py, "update_people_repos.py"] + args2

    # Fixed, enforced order
    steps: List[Step] = [
        Step("ensure_repo", "Validate People-Images repo",          _ensure_repo,   marker=None,              always_run=True),
        Step("name_check",  "Scan Kometa logs for missing names",   _name_check,    marker="name_check.done.json"),
        Step("missing",     "Build missing-people lists",           _missing,       marker="missing.done.json"),
        Step("tmdb",        "Download posters via TMDB",            _tmdb,          marker="tmdb.done.json"),
        Step("truncate",    "Truncate TMDB person names",           _truncate,      marker="truncate.done.json"),
        Step("missing_dir", "Dir-based missing discovery",          _missing_dir,   marker="missing_dir.done.json"),
        Step("prep_dirs",   "Ensure local people_dirs scaffolds",   _prep_dirs,     marker="prep_dirs.done.json"),
        Step("remove_bg",   "Remove backgrounds (Selenium)",        _remove_bg,     marker="remove_bg.done.json"),
        Step("poster_ps1",  "Generate posters via PowerShell",      _poster_ps1,    marker="poster_ps1.done.json"),
        Step("update",      "git fetch/reset category repos",       _update_repos,  marker=None,              always_run=True),
        Step("sync_images", "Sync images to repo folders",          _sync_images,   marker="sync_images.done.json"),
        Step("readme",      "Generate README grid",                 _auto_readme,   marker="readme.done.json"),
        Step("sync_md",     "Mirror *.md back to config",           _sync_md,       marker="sync_md.done.json"),
        Step("push",        "Commit & push changes upstream",       _push_repos,    marker=None,              always_run=True),
    ]

    step_index = {s.key: i for i, s in enumerate(steps)}

    # Status mode
    if args.list:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        print("Step status:")
        for s in steps:
            status = "ALWAYS" if s.always_run else ("DONE" if marker_exists(s.marker_path) else "PENDING")
            print(f" - {s.key:12} : {status}")
        # Show next runnable
        for s in steps:
            if s.always_run or not marker_exists(s.marker_path):
                print(f"\nNext step would be: {s.key} — {s.title}")
                break
        return

    # Handle --redo
    if args.redo:
        if args.redo not in step_index:
            print(f"[ERROR] Unknown step key for --redo: {args.redo}", file=sys.stderr)
            print("Valid keys:", ", ".join(step_index.keys()), file=sys.stderr)
            sys.exit(2)
        clear_from(list(step_index.keys()), args.redo)

    # Compute start index
    start_i = 0
    if args.force:
        # Ignore checkpoints: start from 0 and run through
        start_i = 0
    elif args.from_key:
        if args.from_key not in step_index:
            print(f"[ERROR] Unknown step key for --from: {args.from_key}", file=sys.stderr)
            print("Valid keys:", ", ".join(step_index.keys()), file=sys.stderr)
            sys.exit(2)
        start_i = step_index[args.from_key]
    else:
        # Resume: find first step that must run
        for i, s in enumerate(steps):
            if s.always_run or not marker_exists(s.marker_path):
                start_i = i
                break

    # Acquire lock; ensure state dir exists
    acquire_lock()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        # Execute in order from start_i
        for s in steps[start_i:]:
            argv = s.builder()
            if argv is None:
                # Skipped step (e.g., missing pwsh); treat as completed to not block progress
                if s.marker_path:
                    write_marker(s.marker_path, {"skipped": True, "at": time.time()})
                continue

            rc = run_cmd(s.title, argv)
            if rc != 0:
                print(f"[FAIL] {s.key} exited with code {rc}. Stopping.", file=sys.stderr)
                sys.exit(rc)

            # Write checkpoint if applicable (and not always_run)
            if s.marker_path and not s.always_run:
                write_marker(s.marker_path, {
                    "at": time.time(),
                    "argv": argv,
                })

        print("\nAll steps completed.")
    finally:
        release_lock()


if __name__ == "__main__":
    main()
