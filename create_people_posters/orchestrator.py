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
 12) readme           -> auto_readme.py                     (checkpointed; supports multiple styles)
 13) sync_md          -> sync_md.py                         (checkpointed; supports multiple styles)
 14) push             -> update_people_repos.py --op push   (ALWAYS runs when reached)

Fail-fast points
----------------
- Exit 2 if any repo-required step runs without a valid repo path.
- Exit 2 if TMDB_KEY is missing before tmdb.
- Exit 2 if ORCH_REQUIRE_POWERSHELL=true and no PowerShell is available.
- Exit 2 if ORCH_REQUIRE_BG_OUTPUT=true and SEL_DOWNLOAD_DIR is unknown.
- Exit 0 if sync_images copied 0 files (skip readme/sync_md/push).
- Exit 0 when confidently detected:
  name_check=0, missing=0, tmdb=0, missing_dir=0, prep_dirs=0, remove_bg=0.

Styles
------
- Single style from CLI: --style transparent
- Multiple styles from CLI: --styles transparent,diiivoycolor
- From env:
    ORCH_STYLE=transparent
    ORCH_STYLES=transparent,diiivoycolor
  Precedence: --styles > ORCH_STYLES > --style > ORCH_STYLE.

Common CLI usage
----------------
  python orchestrator.py              # resume from the first incomplete step
  python orchestrator.py --from tmdb  # start at a given step (still in fixed order)
  python orchestrator.py --force      # ignore checkpoints and run all steps
  python orchestrator.py --list       # show step status & which step would run next
  python orchestrator.py --redo readme  # re-run from "readme": clears its checkpoint and those after

Environment (./config/.env or process environment)
--------------------------------------------------
  ORCH_LOGS_DIR         — Kometa logs folder for steps 2–3 (optional)
  PEOPLE_IMAGES_DIR     — repo root for steps needing the People-Images repo
  PEOPLE_BRANCH         — git branch for update/push (optional)
  ORCH_STYLE            — style for README & MD sync (default: transparent)
  ORCH_STYLES           — comma list of styles for README & MD sync (optional)
  ORCH_COMMIT_MESSAGE   — optional commit message for push (overrides auto)
  ORCH_GIT_USER_NAME    — optional git author.name override for push
  ORCH_GIT_USER_EMAIL   — optional git author.email override for push

  # Background-removal verification
  SEL_DOWNLOAD_DIR      — folder where sel_remove_bg.py writes processed files
  ORCH_BG_EXTS          — extensions to count as processed (e.g. "png" or "png,jpg") [default: "png"]
  ORCH_CONTINUE_IF_EMPTY — if "true", continue even when zero BG files were produced [default: false]

  # Hard requirements (not optional once set to true)
  ORCH_REQUIRE_POWERSHELL=true        — fail if PowerShell isn't available
  ORCH_REQUIRE_BG_OUTPUT=true         — fail if SEL_DOWNLOAD_DIR isn't set/visible
"""
import os
import sys
import shlex
import json
import time
import subprocess
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"
STATE_DIR = CONFIG_DIR / ".orch"           # checkpoint folder
LOCK_FILE = STATE_DIR / "run.lock"         # run lock to prevent concurrent runs

# For basic repo sanity after ensure_repo
CATEGORY_DIRS = ["bw", "diiivoy", "diiivoycolor", "rainier", "original", "signature", "transparent"]


def env_path(key: str, default: str | None = None) -> Optional[Path]:
    value = os.getenv(key, default if default is not None else "")
    return Path(value).expanduser().resolve() if value else None


def _bool_env(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


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


# ---------- helpers: run, markers, fs/log counting, lock ----------
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


def run_cmd(title: str, argv: List[str], capture: bool = False) -> Tuple[int, Optional[str], Optional[str]]:
    """Run a subprocess; return (rc, stdout, stderr) if capture else (rc, None, None)."""
    print(f"\n=== {title} ===")
    print("→", " ".join(shlex.quote(a) for a in argv))
    try:
        if capture:
            cp = subprocess.run(argv, cwd=str(SCRIPT_DIR), text=True, capture_output=True)
            return cp.returncode, (cp.stdout or ""), (cp.stderr or "")
        else:
            cp = subprocess.run(argv, cwd=str(SCRIPT_DIR))
            return cp.returncode, None, None
    except FileNotFoundError as e:
        print(f"[ERROR] {title}: {e}", file=sys.stderr)
        return 127, None, None
    except Exception as e:
        print(f"[ERROR] {title}: {e}", file=sys.stderr)
        return 1, None, None


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


def count_recent_files(paths: list[Path], since_ts: float, suffixes: set[str] | None = None) -> int:
    total = 0
    for base in paths:
        if not base or not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if suffixes and p.suffix.lower().lstrip(".") not in suffixes:
                continue
            try:
                # Some copy routines preserve mtime; don't rely solely on this for critical steps.
                if p.stat().st_mtime >= (since_ts - 1.0):
                    total += 1
            except OSError:
                pass
    return total


def parse_zero_from_log(logfile: Path) -> Optional[bool]:
    """Return True if log strongly indicates zero work; False if >0; None if unknown."""
    if not logfile.exists():
        return None
    try:
        text = logfile.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    # Look for simple signals
    zero_patterns = [
        r"\b0\s+(?:items|people|names|downloads|moved|copied)\b",
        r"\bno\s+(?:items|people|names|downloads|changes|work)\b",
        r"\bnothing\s+(?:to\s+do|moved|copied|processed)\b",
        r"\bSummary:\s*processed\s*=\s*0\b",
        r"\bFiles processed:\s*0\b",
    ]
    nonzero_patterns = [
        r"\b([1-9]\d*)\s+(?:items|people|names|downloads|moved|copied)\b",
        r"\b(total|processed|moved|copied)\s*:\s*([1-9]\d*)\b",
        r"\bSummary:\s*processed\s*=\s*([1-9]\d*)\b",
        r"\bFiles processed:\s*([1-9]\d*)\b",
    ]
    for rgx in nonzero_patterns:
        if re.search(rgx, text, flags=re.I):
            return False
    for rgx in zero_patterns:
        if re.search(rgx, text, flags=re.I):
            return True
    return None


def sum_copied_from_sync_log(logfile: Path) -> Optional[int]:
    """Parse sync_people_images.log and sum 'copied=N' across categories. Return None if not parseable."""
    if not logfile.exists():
        return None
    try:
        text = logfile.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    copied_values = [int(m) for m in re.findall(r"copied\s*=\s*(\d+)", text)]
    return sum(copied_values) if copied_values else 0 if "copied=0" in text else None


def parsed_processed_from_missing_dir(logfile: Path) -> Optional[int]:
    """Parse get_missing_people_dir.py log for 'Summary: processed=N'."""
    if not logfile.exists():
        return None
    try:
        text = logfile.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    m = re.search(r"Summary:\s*processed\s*=\s*(\d+)", text, flags=re.I)
    if m:
        return int(m.group(1))
    # fallback tokens
    m2 = re.search(r"\bprocessed\s*=\s*(\d+)", text, flags=re.I)
    return int(m2.group(1)) if m2 else None


def parsed_files_processed_from_remove_bg(logfile: Path) -> Optional[int]:
    """Parse sel_remove_bg.py log for 'Files processed: N'."""
    if not logfile.exists():
        return None
    try:
        text = logfile.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    m = re.search(r"Files processed:\s*(\d+)", text, flags=re.I)
    return int(m.group(1)) if m else None


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
    parser.add_argument("--style", help="Default style for README/MD if no multi-style is set (env ORCH_STYLE or 'transparent').")
    parser.add_argument("--styles", help="Comma list of styles for README/MD (overrides ORCH_STYLES).")
    # BG verification / early-exit controls
    parser.add_argument("--bg-output-dir", help="Where sel_remove_bg downloads go (env SEL_DOWNLOAD_DIR).")
    parser.add_argument("--bg-exts", default=os.getenv("ORCH_BG_EXTS", "png"),
                        help="Comma list of extensions to count as processed (default: png)")
    parser.add_argument("--continue-if-empty", action="store_true",
                        help="Don't stop even if sel_remove_bg produced nothing (env ORCH_CONTINUE_IF_EMPTY)")

    args = parser.parse_args()

    # Resolve env/args
    logs_dir = Path(args.logs_dir).expanduser().resolve() if args.logs_dir else env_path("ORCH_LOGS_DIR")
    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else env_path("PEOPLE_IMAGES_DIR")
    branch = args.branch or os.getenv("PEOPLE_BRANCH", "")
    default_style = args.style or os.getenv("ORCH_STYLE", "transparent")
    styles_env = os.getenv("ORCH_STYLES", "")
    if args.styles:
        styles = [s.strip() for s in args.styles.split(",") if s.strip()]
    elif styles_env:
        styles = [s.strip() for s in styles_env.split(",") if s.strip()]
    else:
        styles = [default_style]

    commit_template = os.getenv("ORCH_COMMIT_MESSAGE", "")
    git_user_name = os.getenv("ORCH_GIT_USER_NAME", "")
    git_user_email = os.getenv("ORCH_GIT_USER_EMAIL", "")

    bg_output_dir = Path(args.bg_output_dir).expanduser().resolve() if args.bg_output_dir else env_path("SEL_DOWNLOAD_DIR")
    bg_exts = {e.strip().lower().lstrip(".") for e in (args.bg_exts or "png").split(",") if e.strip()}
    continue_if_empty = args.continue_if_empty or _bool_env("ORCH_CONTINUE_IF_EMPTY", False)

    REQUIRE_POWERSHELL = _bool_env("ORCH_REQUIRE_POWERSHELL", False)
    REQUIRE_BG_OUTPUT = _bool_env("ORCH_REQUIRE_BG_OUTPUT", False)

    # Build step builders
    py = sys.executable

    def _require_repo_or_die():
        if not repo_root or not repo_root.exists():
            print("[ERROR] PEOPLE_IMAGES_DIR not set or invalid; required for this step.", file=sys.stderr)
            sys.exit(2)

    def _ensure_repo():
        # Let ensure_people_repo.py figure things out (clone/validate)
        args2 = ["--repo-root", str(repo_root)] if repo_root else []
        return [py, "ensure_people_repo.py"] + args2

    def _name_check():
        if not logs_dir or not logs_dir.exists():
            print("[ERROR] ORCH_LOGS_DIR not set or missing. Use --logs-dir.", file=sys.stderr)
            sys.exit(2)
        return [py, "name_checker_dir.py", "--input_directory", str(logs_dir)]

    def _missing():
        if not logs_dir or not logs_dir.exists():
            print("[ERROR] ORCH_LOGS_DIR not set or missing. Use --logs-dir.", file=sys.stderr)
            sys.exit(2)
        return [py, "get_missing_people.py", "--input_directory", str(logs_dir)]

    def _tmdb():
        if not os.getenv("TMDB_KEY"):
            print("[ERROR] TMDB_KEY not set in ./config/.env; cannot run tmdb step.", file=sys.stderr)
            sys.exit(2)
        return [py, "tmdb_people.py"]

    def _truncate():
        return [py, "truncate_tmdb_people_names.py"]

    def _missing_dir():
        return [py, "get_missing_people_dir.py"]

    def _prep_dirs():
        return [py, "prep_people_dirs.py"]

    def _remove_bg():
        # If caller requires output verification but we cannot locate output dir — fail now.
        if REQUIRE_BG_OUTPUT and not bg_output_dir:
            print("[ERROR] ORCH_REQUIRE_BG_OUTPUT is true but SEL_DOWNLOAD_DIR is not set.", file=sys.stderr)
            sys.exit(2)
        return [py, "sel_remove_bg.py"]

    def _poster_ps1():
        ps = ps_exe()
        if not ps:
            if REQUIRE_POWERSHELL:
                print("[ERROR] ORCH_REQUIRE_POWERSHELL=true but PowerShell (pwsh) not found.", file=sys.stderr)
                sys.exit(2)
            print("[WARN] PowerShell (pwsh) not found — skipping create_people_poster.ps1", file=sys.stderr)
            return None
        ps1 = str((SCRIPT_DIR / "create_people_poster.ps1").resolve())
        return [ps, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1]

    def _update_repos():
        _require_repo_or_die()
        args2 = ["--repo-root", str(repo_root)]
        if branch:
            args2 += ["--branch", branch]
        args2 += ["--op", "update", "--mode", "hardreset", "--clean-ignored"]
        return [py, "update_people_repos.py"] + args2

    def _sync_images():
        _require_repo_or_die()
        return [py, "sync_people_images.py", "--dest_root", str(repo_root)]

    # Per-style builders (used during the run loop)
    def _auto_readme_for(style: str):
        _require_repo_or_die()
        return [py, "auto_readme.py", "--style", style, "--directory", str((repo_root / style).resolve())]

    def _sync_md_for(style: str):
        _require_repo_or_die()
        src = str((repo_root / style).resolve())
        dst = str((CONFIG_DIR / "people_dirs" / style).resolve())
        return [py, "sync_md.py", "--src", src, "--dst", dst, "--pattern", "*.md"]

    def _push_repos():
        _require_repo_or_die()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        styles_tag = ",".join(styles)
        msg = (commit_template or f"chore: sync posters & docs [{styles_tag}] — {now}").strip()
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
        Step("readme",      "Generate README grid(s)",              None,           marker="readme.done.json"),
        Step("sync_md",     "Mirror *.md back to config (per style)", None,         marker="sync_md.done.json"),
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
        start_i = 0
    elif args.from_key:
        if args.from_key not in step_index:
            print(f"[ERROR] Unknown step key for --from: {args.from_key}", file=sys.stderr)
            print("Valid keys:", ", ".join(step_index.keys()), file=sys.stderr)
            sys.exit(2)
        start_i = step_index[args.from_key]
    else:
        for i, s in enumerate(steps):
            if s.always_run or not marker_exists(s.marker_path):
                start_i = i
                break

    # Run
    acquire_lock()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        step_started_at: dict[str, float] = {}
        for s in steps[start_i:]:
            step_started_at[s.key] = time.time()

            # Special multi-style steps handle inside the loop
            if s.key == "readme":
                # generate README for each style
                for st in styles:
                    argv = _auto_readme_for(st)
                    rc, _, _ = run_cmd(f"Generate README grid [{st}]", argv)
                    if rc != 0:
                        print(f"[FAIL] readme ({st}) exited with code {rc}. Stopping.", file=sys.stderr)
                        sys.exit(rc)
                # checkpoint once for the whole batch
                if s.marker_path:
                    write_marker(s.marker_path, {"at": time.time(), "styles": styles})
                continue

            if s.key == "sync_md":
                # sync md for each style
                for st in styles:
                    argv = _sync_md_for(st)
                    rc, _, _ = run_cmd(f"Mirror *.md back to config [{st}]", argv)
                    if rc != 0:
                        print(f"[FAIL] sync_md ({st}) exited with code {rc}. Stopping.", file=sys.stderr)
                        sys.exit(rc)
                if s.marker_path:
                    write_marker(s.marker_path, {"at": time.time(), "styles": styles})
                continue

            # Normal steps
            builder = s.builder
            if builder is None:
                print(f"[ERROR] Step {s.key} has no builder.", file=sys.stderr)
                sys.exit(2)
            argv = builder()
            if argv is None:
                # Only allowed skip is poster_ps1 when pwsh missing & not required
                if s.key == "poster_ps1":
                    if s.marker_path:
                        write_marker(s.marker_path, {"skipped": True, "at": time.time()})
                    continue
                # Any other None means something critical was missing; die
                print(f"[ERROR] Step {s.key} could not build its command.", file=sys.stderr)
                sys.exit(2)

            # ensure_repo must exist AND return success; also sanity-check the repo root afterward
            capture_output = (s.key in {"name_check", "missing"})
            rc, out, _ = run_cmd(s.title, argv, capture=capture_output)
            if rc != 0:
                print(f"[FAIL] {s.key} exited with code {rc}. Stopping.", file=sys.stderr)
                sys.exit(rc)

            # Post-step fail-fast checks (confident zeros -> exit 0; hard requirements -> exit 2)
            started = step_started_at[s.key]

            def log_path_for(script_filename: str) -> Path:
                return CONFIG_DIR / "logs" / f"{Path(script_filename).stem}.log"

            # 1) ensure_repo extra sanity
            if s.key == "ensure_repo":
                if not repo_root or not repo_root.exists():
                    print("[ERROR] ensure_repo finished but PEOPLE_IMAGES_DIR is not set/valid.", file=sys.stderr)
                    sys.exit(2)
                # require at least one expected category dir present
                present = [d for d in CATEGORY_DIRS if (repo_root / d).exists()]
                if not present:
                    print("[ERROR] ensure_repo did not yield expected category folders under repo root.", file=sys.stderr)
                    sys.exit(2)

            # name_check: if clearly zero, stop
            elif s.key == "name_check":
                zero = parse_zero_from_log(log_path_for("name_checker_dir.py"))
                if zero is True:
                    print("[INFO] name_check found 0 items — stopping.")
                    sys.exit(0)

            # missing: if clearly zero, stop
            elif s.key == "missing":
                zero = parse_zero_from_log(log_path_for("get_missing_people.py"))
                if zero is True:
                    print("[INFO] missing produced 0 items — stopping.")
                    sys.exit(0)

            # tmdb: if no new posters created, stop
            elif s.key == "tmdb":
                created = count_recent_files([CONFIG_DIR], started, {"jpg", "jpeg", "png"})
                if created == 0:
                    print("[INFO] tmdb downloaded 0 posters — stopping.")
                    sys.exit(0)

            # missing_dir: if processed 0, stop (parse its log rather than filesystem)
            elif s.key == "missing_dir":
                md_count = parsed_processed_from_missing_dir(log_path_for("get_missing_people_dir.py"))
                if md_count is not None and md_count == 0:
                    print("[INFO] missing_dir sorted/moved 0 items — stopping.")
                    sys.exit(0)

            # prep_dirs: if established/moved 0 artifacts, stop (use fs heuristic as fallback)
            elif s.key == "prep_dirs":
                pd = CONFIG_DIR / "people_dirs"
                changed = count_recent_files([pd], started, {"jpg", "jpeg", "png", "md"})
                if changed == 0:
                    zero = parse_zero_from_log(log_path_for("prep_people_dirs.py"))
                    if zero is True:
                        print("[INFO] prep_dirs moved 0 items — stopping.")
                        sys.exit(0)

            # remove_bg: verify outputs and possibly stop
            elif s.key == "remove_bg":
                if REQUIRE_BG_OUTPUT and not bg_output_dir:
                    print("[ERROR] ORCH_REQUIRE_BG_OUTPUT=true but SEL_DOWNLOAD_DIR is unknown.", file=sys.stderr)
                    sys.exit(2)
                processed = count_recent_files([bg_output_dir] if bg_output_dir else [], started, bg_exts)
                if processed == 0 and not continue_if_empty:
                    # If fs says 0, but the tool log shows >0, continue (saves you from dir mismatch).
                    rb_log = log_path_for("sel_remove_bg.py")
                    log_n = parsed_files_processed_from_remove_bg(rb_log)
                    if (log_n is None) or (log_n == 0):
                        print(f"[INFO] sel_remove_bg produced 0 files in {bg_output_dir} — stopping.")
                        sys.exit(0)

            # sync_images: if copied nothing, stop before readme/sync_md/push (parse its log)
            elif s.key == "sync_images":
                sync_log = log_path_for("sync_people_images.py")
                copied_sum = sum_copied_from_sync_log(sync_log)
                if copied_sum is not None and copied_sum == 0:
                    print("[INFO] sync_images copied 0 files — stopping before readme/sync_md/push.")
                    sys.exit(0)

            # Write checkpoint if applicable (and not always_run)
            if s.marker_path and not s.always_run:
                write_marker(s.marker_path, {"at": time.time(), "argv": argv})

        print("\nAll steps completed.")
    finally:
        release_lock()


if __name__ == "__main__":
    main()