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
  1) ensure_repo               -> ensure_people_repo.py               (always runs: cheap sanity check)
  2) scan_kometa_logs          -> scan_kometa_logs.py                 (checkpointed)
  3) find_and_download_missing -> find_and_download_missing_people.py (checkpointed)
  4) tmdb                      -> tmdb_people.py                      (checkpointed)
  5) truncate                  -> truncate_tmdb_people_names.py       (checkpointed)
  6) audit_people_images       -> audit_people_images.py              (checkpointed)
  7) colorize_noncolor         -> colorize_noncolor.py                (checkpointed)
  8) prep_dirs                 -> prep_people_dirs.py                 (checkpointed)
  9) remove_bg                 -> sel_remove_bg.py                    (checkpointed)
 11) recover_edge_chops        -> recover_edge_chops.py               (checkpointed; non-blocking)
 12) update                    -> update_people_repos.py --op update  (ALWAYS runs when reached)
 13) sync_images               -> sync_people_images.py               (checkpointed)
 14) readme                    -> auto_readme.py                      (checkpointed; supports multiple styles)
 15) sync_md                   -> sync_md.py                          (checkpointed; supports multiple styles)
 16) push                      -> update_people_repos.py --op push    (ALWAYS runs when reached)

Fail-fast points
----------------
- Exit 2 if any repo-required step runs without a valid repo path.
- Exit 2 if TMDB_KEY is missing before tmdb.
- Exit 2 if ORCH_REQUIRE_POWERSHELL=true and no PowerShell is available.
- Exit 2 if ORCH_REQUIRE_BG_OUTPUT=true and SEL_DOWNLOAD_DIR is unknown.
- Exit 0 if sync_images copied 0 files (skip readme/sync_md/push).
- Exit 0 when confidently detected:
  scan_kometa_logs=0, find_and_download_missing=0, tmdb=0, audit_people_images=0, prep_dirs=0, remove_bg=0.

Styles
------
- Single style from CLI: --style transparent
- Multiple styles from CLI: --styles transparent,diiivoycolor
- From env:
    ORCH_STYLE=transparent
    # ORCH_STYLES=transparent,diiivoycolor
  README style precedence: --styles > ORCH_STYLES > --style > ORCH_STYLE.

Common CLI usage
----------------
  python orchestrator.py              # resume from the first incomplete step
  python orchestrator.py --redo tmdb  # clear tmdb+downstream checkpoints and restart at tmdb
  python orchestrator.py --force      # ignore checkpoints and run all steps
  python orchestrator.py --list       # show step status & which step would run next
  python orchestrator.py --redo readme  # clear readme+downstream checkpoints and restart at readme

Environment (./config/.env or process environment)
--------------------------------------------------
  ORCH_LOGS_DIR         — Kometa logs folder for steps 2–3 (optional)
  PEOPLE_IMAGES_DIR     — repo root for steps needing the People-Images repo
  PEOPLE_BRANCH         — git branch for update/push (optional)
  ORCH_STYLE            — fallback style for optional local README & MD sync
  ORCH_STYLES           — optional comma list for local README & MD sync only
  ORCH_GENERATE_READMES — when true, run local readme/sync_md steps [default: false]
  ORCH_GRID_IMAGES      — when true, generate/link per-letter grid.jpg images in README step [default: false]
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
  ORCH_RECOVER_EDGE_CHOPS=true        — after poster generation, retry top-edge transparent chops from TMDB alternates
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


def _clean_env_value(value: Optional[str]) -> str:
    if value is None:
        return ""
    cleaned = str(value).strip()
    if not cleaned or cleaned.startswith("#"):
        return ""
    return cleaned


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
            print(f"Missing ./config/.env - created one from example.\n"
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
            cp = subprocess.run(
                [exe, "-NoLogo", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.Major"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if cp.returncode == 0:
                return exe
        except Exception:
            continue
    return None


def _python_spec_to_argv(spec: str) -> List[str]:
    cleaned = _clean_env_value(spec).strip().strip("\"'")
    return [cleaned] if cleaned else []


def _colorize_candidates_exist() -> bool:
    input_dir = Path(os.getenv("COLORIZE_INPUT_OTHER", CONFIG_DIR / "Downloads" / "other"))
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
    try:
        return input_dir.exists() and any(
            p.is_file() and p.suffix.lower() in exts
            for p in input_dir.iterdir()
        )
    except OSError:
        return False


def _python_probe(argv_prefix: List[str], require_colorize_deps: bool) -> Tuple[bool, str]:
    if not argv_prefix:
        return False, "empty interpreter command"
    probe = "import sys; print(sys.executable)"
    if require_colorize_deps:
        probe = (
            "import sys; import numpy as np; "
            "ver=tuple(int(x) for x in np.__version__.split('.', 2)[:2]); "
            "assert ver < (2, 0), 'NumPy '+np.__version__+' detected; requires NumPy < 2'; "
            "import fastai, torch, torchvision; print(sys.executable)"
        )
    try:
        cp = subprocess.run(
            argv_prefix + ["-c", probe],
            cwd=str(SCRIPT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except FileNotFoundError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)
    if cp.returncode == 0:
        return True, (cp.stdout or "").strip()
    combined = ((cp.stdout or "") + ("\n" if cp.stdout and cp.stderr else "") + (cp.stderr or "")).strip()
    return False, combined or f"exit code {cp.returncode}"


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


def run_cmd(
    title: str,
    argv: List[str],
    capture: bool = False,
    log_path: Optional[Path] = None,
) -> Tuple[int, Optional[str], Optional[str]]:
    """Run a subprocess; optionally tee combined output to a log file."""
    print(f"\n=== {title} ===")
    print("->", " ".join(shlex.quote(a) for a in argv))
    try:
        if capture:
            cp = subprocess.run(
                argv,
                cwd=str(SCRIPT_DIR),
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
            )
            if log_path:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                combined = (cp.stdout or "")
                if cp.stderr:
                    if combined and not combined.endswith("\n"):
                        combined += "\n"
                    combined += cp.stderr
                log_path.write_text(combined, encoding="utf-8")
            return cp.returncode, (cp.stdout or ""), (cp.stderr or "")
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("w", encoding="utf-8", errors="replace") as handle:
                cp = subprocess.Popen(
                    argv,
                    cwd=str(SCRIPT_DIR),
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
                assert cp.stdout is not None
                for line in cp.stdout:
                    print(line, end="")
                    handle.write(line)
                cp.stdout.close()
                rc = cp.wait()
            return rc, None, None
        else:
            cp = subprocess.run(argv, cwd=str(SCRIPT_DIR))
            return cp.returncode, None, None
    except FileNotFoundError as e:
        print(f"[ERROR] {title}: {e}", file=sys.stderr)
        return 127, None, None
    except Exception as e:
        print(f"[ERROR] {title}: {e}", file=sys.stderr)
        return 1, None, None


def print_abort_recovery(step_key: str, rc: int) -> None:
    print(f"[ABORT] Orchestrator stopped at step '{step_key}' with exit code {rc}.", file=sys.stderr)
    if step_key == "remove_bg" and rc == 4:
        print(
            "[ABORT] Adobe login is required. Completed downloads were kept; "
            "remaining JPGs are still queued for retry.",
            file=sys.stderr,
        )
        print("[NEXT] Run: python sel_remove_bg.py --login-only", file=sys.stderr)
        print("[NEXT] Then resume: python orchestrator.py --redo remove_bg --no-recover-edge-chops", file=sys.stderr)
        return
    print(f"[NEXT] Resume after fixing the issue: python orchestrator.py --redo {step_key}", file=sys.stderr)


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


def count_manual_people_overrides(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return sum(
            1
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    except Exception:
        return 0


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


def parsed_processed_from_audit_people_images(logfile: Path) -> Optional[int]:
    """Parse audit_people_images.py log for 'Summary: processed=N'."""
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
    people_override_file = Path(os.getenv("PEOPLE_OVERRIDE_LIST") or (CONFIG_DIR / "people_overrides.txt"))
    manual_override_count = count_manual_people_overrides(people_override_file)

    parser = argparse.ArgumentParser(description="Fixed-order, resumable pipeline runner")
    parser.add_argument("--force", action="store_true", help="Ignore checkpoints and run all steps from the beginning.")
    parser.add_argument("--redo", help="Clear checkpoint for this step (and downstream) and restart at that step.")
    parser.add_argument("--list", action="store_true", help="List step status and exit.")
    parser.add_argument("--logs-dir", help="Kometa logs folder for steps scan_kometa_logs/find_and_download_missing (env ORCH_LOGS_DIR otherwise).")
    parser.add_argument("--repo-root", help="Kometa-People-Images repository root (env PEOPLE_IMAGES_DIR otherwise).")
    parser.add_argument("--branch", help="Git branch for update/push (env PEOPLE_BRANCH or auto-detect).")
    parser.add_argument("--style", help="Default style for README/MD if no multi-style is set (env ORCH_STYLE or 'transparent').")
    parser.add_argument("--styles", help="Comma list of styles for README/MD (overrides ORCH_STYLES).")
    parser.add_argument("--generate-readmes", action=argparse.BooleanOptionalAction,
                        default=None,
                        help="Run local README generation and sync_md steps. Default: ORCH_GENERATE_READMES or false.")
    parser.add_argument("--grid-images", action="store_true",
                        help="Generate and link per-letter grid.jpg images during the readme step (default: README-only).")
    # BG verification / early-exit controls
    parser.add_argument("--bg-output-dir", help="Where sel_remove_bg downloads go (env SEL_DOWNLOAD_DIR).")
    parser.add_argument("--bg-exts", default=os.getenv("ORCH_BG_EXTS", "png"),
                        help="Comma list of extensions to count as processed (default: png)")
    parser.add_argument("--continue-if-empty", action="store_true",
                        help="Don't stop even if sel_remove_bg produced nothing (env ORCH_CONTINUE_IF_EMPTY)")
    parser.add_argument("--no-recover-edge-chops", action="store_true",
                        help="Skip non-blocking TMDB alternate retries for top-edge transparent chops.")

    args = parser.parse_args()

    # Resolve env/args
    logs_dir = Path(args.logs_dir).expanduser().resolve() if args.logs_dir else env_path("ORCH_LOGS_DIR")
    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else env_path("PEOPLE_IMAGES_DIR")
    branch = _clean_env_value(args.branch or os.getenv("PEOPLE_BRANCH", ""))
    default_style = args.style or os.getenv("ORCH_STYLE", "transparent")
    styles_env = os.getenv("ORCH_STYLES", "")
    if args.styles:
        styles = [s.strip() for s in args.styles.split(",") if s.strip()]
    elif styles_env:
        styles = [s.strip() for s in styles_env.split(",") if s.strip()]
    else:
        styles = [default_style]

    commit_template = _clean_env_value(os.getenv("ORCH_COMMIT_MESSAGE", ""))
    git_user_name = _clean_env_value(os.getenv("ORCH_GIT_USER_NAME", ""))
    git_user_email = _clean_env_value(os.getenv("ORCH_GIT_USER_EMAIL", ""))
    generate_readmes = (
        args.generate_readmes
        if args.generate_readmes is not None
        else _bool_env("ORCH_GENERATE_READMES", False)
    )
    grid_images = args.grid_images or _bool_env("ORCH_GRID_IMAGES", False)

    bg_output_dir = Path(args.bg_output_dir).expanduser().resolve() if args.bg_output_dir else env_path("SEL_DOWNLOAD_DIR")
    bg_exts = {e.strip().lower().lstrip(".") for e in (args.bg_exts or "png").split(",") if e.strip()}
    continue_if_empty = args.continue_if_empty or _bool_env("ORCH_CONTINUE_IF_EMPTY", False)
    recover_edge_chops = (not args.no_recover_edge_chops) and _bool_env("ORCH_RECOVER_EDGE_CHOPS", True)

    REQUIRE_POWERSHELL = _bool_env("ORCH_REQUIRE_POWERSHELL", False)
    REQUIRE_BG_OUTPUT = _bool_env("ORCH_REQUIRE_BG_OUTPUT", False)

    # Build step builders
    py = sys.executable

    def _colorize():
        # Prefer a separate DeOldify venv, but do not let a stale copied venv
        # stop the no-op case where there are no grayscale files to colorize.
        require_deps = _colorize_candidates_exist()
        configured = _python_spec_to_argv(os.getenv("COLORIZE_PYTHON", ""))
        local_venv = (
            SCRIPT_DIR / ".venv-colorize" / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")
        )
        candidates: list[tuple[str, List[str]]] = []
        if configured:
            candidates.append(("COLORIZE_PYTHON", configured))
        candidates.append(("local .venv-colorize", [str(local_venv)]))
        if sys.platform.startswith("win"):
            candidates.append(("Python launcher 3.10", ["py", "-3.10"]))
        candidates.append(("python3.10", ["python3.10"]))
        candidates.append(("orchestrator Python", [py]))

        seen: set[tuple[str, ...]] = set()
        failures: list[str] = []
        for label, prefix in candidates:
            key = tuple(prefix)
            if key in seen:
                continue
            seen.add(key)
            ok, detail = _python_probe(prefix, require_colorize_deps=require_deps)
            if ok:
                if label != "COLORIZE_PYTHON":
                    print(f"[WARN] COLORIZE_PYTHON is not usable; using {label}: {' '.join(prefix)}")
                return prefix + ["colorize_noncolor.py"]
            failures.append(f"{label} ({' '.join(prefix)}): {detail}")

        print("[ERROR] No usable Python interpreter found for the colorize step.", file=sys.stderr)
        if require_deps:
            print("[ERROR] Grayscale files are waiting in config/Downloads/other, so DeOldify deps are required.", file=sys.stderr)
        else:
            print("[ERROR] Even the no-op colorize check could not start any Python interpreter.", file=sys.stderr)
        for failure in failures:
            print(f"[ERROR]   {failure}", file=sys.stderr)
        sys.exit(2)

    def _require_repo_or_die():
        if not repo_root or not repo_root.exists():
            print("[ERROR] PEOPLE_IMAGES_DIR not set or invalid; required for this step.", file=sys.stderr)
            sys.exit(2)

    def _ensure_repo():
        # Let ensure_people_repo.py figure things out (clone/validate)
        args2 = ["--repo-root", str(repo_root)] if repo_root else []
        return [py, "ensure_people_repo.py"] + args2

    def _scan_kometa_logs():
        if not logs_dir or not logs_dir.exists():
            print("[ERROR] ORCH_LOGS_DIR not set or missing. Use --logs-dir.", file=sys.stderr)
            sys.exit(2)
        return [py, "scan_kometa_logs.py", "--input_directory", str(logs_dir)]

    def _find_and_download_missing():
        if not logs_dir or not logs_dir.exists():
            print("[ERROR] ORCH_LOGS_DIR not set or missing. Use --logs-dir.", file=sys.stderr)
            sys.exit(2)
        return [py, "find_and_download_missing_people.py", "--input_directory", str(logs_dir)]

    def _tmdb():
        if not os.getenv("TMDB_KEY"):
            print("[ERROR] TMDB_KEY not set in ./config/.env; cannot run tmdb step.", file=sys.stderr)
            sys.exit(2)
        return [py, "tmdb_people.py"]

    def _truncate():
        return [py, "truncate_tmdb_people_names.py"]

    def _audit_people_images():
        return [py, "audit_people_images.py"]

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
            print("[WARN] PowerShell (pwsh) not found - skipping create_people_poster.ps1", file=sys.stderr)
            return None
        ps1 = str((SCRIPT_DIR / "create_people_poster.ps1").resolve())
        return [ps, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1]

    def _recover_edge_chops():
        if not recover_edge_chops:
            print("[INFO] recover_edge_chops disabled - skipping.")
            return None
        local_people_root = CONFIG_DIR / "people_dirs"
        args2 = [
            py,
            "recover_edge_chops.py",
            "--inline",
            "--people-root",
            str(local_people_root.resolve()),
            "--transparent-root",
            str((local_people_root / "transparent").resolve()),
        ]
        try:
            poster_started = step_started_at.get("poster_ps1")
        except NameError:
            poster_started = None
        if poster_started:
            args2 += ["--modified-since", str(poster_started - 1.0)]
        return args2

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
        args2 = [py, "auto_readme.py", "--style", style, "--directory", str((repo_root / style).resolve())]
        if grid_images:
            args2.append("--grid")
        return args2

    def _sync_md_for(style: str):
        _require_repo_or_die()
        src = str((repo_root / style).resolve())
        dst = str((CONFIG_DIR / "people_dirs" / style).resolve())
        return [py, "sync_md.py", "--src", src, "--dst", dst, "--pattern", "*.md"]

    def _push_repos():
        _require_repo_or_die()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        msg = (commit_template or f"chore: sync posters - {now}").strip()
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
        Step("ensure_repo",               "Validate People-Images repo",                _ensure_repo,               marker=None,              always_run=True),
        Step("scan_kometa_logs",          "Scan Kometa logs for missing names",         _scan_kometa_logs,          marker="scan_kometa_logs.done.json"),
        Step("find_and_download_missing", "Build missing-people lists",                 _find_and_download_missing, marker="find_and_download_missing.done.json"),
        Step("tmdb",                      "Download posters via TMDB",                  _tmdb,                      marker="tmdb.done.json"),
        Step("truncate",                  "Truncate TMDB person names",                 _truncate,                  marker="truncate.done.json"),
        Step("audit_people_images",       "Dir-based missing discovery",                _audit_people_images,       marker="audit_people_images.done.json"),
        Step("colorize",                  "Colorize non-color images",                  _colorize,                  marker="colorize_noncolor.done.json"),
        Step("prep_dirs",                 "Ensure local people_dirs scaffolds",         _prep_dirs,                 marker="prep_dirs.done.json"),
        Step("remove_bg",                 "Remove backgrounds (Selenium)",              _remove_bg,                 marker="remove_bg.done.json"),
        Step("poster_ps1",                "Generate posters via PowerShell",            _poster_ps1,                marker="poster_ps1.done.json"),
        Step("recover_edge_chops",        "Retry top-edge chops from TMDB alternates",   _recover_edge_chops,        marker="recover_edge_chops.done.json"),
        Step("update",                    "git fetch/reset category repos",             _update_repos,              marker=None,              always_run=True),
        Step("sync_images",               "Sync images to repo folders",                _sync_images,               marker="sync_images.done.json"),
        Step("readme",                    "Generate README files",                      None,                       marker="readme.done.json"),
        Step("sync_md",                   "Mirror *.md back to config (per style)",     None,                       marker="sync_md.done.json"),
        Step("push",                      "Commit & push changes upstream",             _push_repos,                marker=None,              always_run=True),
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
                print(f"\nNext step would be: {s.key} - {s.title}")
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
    elif args.redo:
        start_i = step_index[args.redo]
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
                if not generate_readmes:
                    print("[INFO] local README generation disabled - skipping readme step.")
                    if s.marker_path:
                        write_marker(s.marker_path, {"skipped": True, "at": time.time(), "reason": "ORCH_GENERATE_READMES=false"})
                    continue
                # generate README for each style; grid images are opt-in because they are expensive
                for st in styles:
                    argv = _auto_readme_for(st)
                    title = f"Generate README {'with grids' if grid_images else 'without grids'} [{st}]"
                    rc, _, _ = run_cmd(title, argv)
                    if rc != 0:
                        print(f"[FAIL] readme ({st}) exited with code {rc}. Stopping.", file=sys.stderr)
                        sys.exit(rc)
                # checkpoint once for the whole batch
                if s.marker_path:
                    write_marker(s.marker_path, {"at": time.time(), "styles": styles})
                continue

            if s.key == "sync_md":
                if not generate_readmes:
                    print("[INFO] local README generation disabled - skipping sync_md step.")
                    if s.marker_path:
                        write_marker(s.marker_path, {"skipped": True, "at": time.time(), "reason": "ORCH_GENERATE_READMES=false"})
                    continue
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

            def step_log_path(step_key: str) -> Optional[Path]:
                if step_key == "update":
                    return CONFIG_DIR / "logs" / "update_people_repos_update.log"
                if step_key == "push":
                    return CONFIG_DIR / "logs" / "update_people_repos_push.log"
                return None

            # Normal steps
            builder = s.builder
            if builder is None:
                print(f"[ERROR] Step {s.key} has no builder.", file=sys.stderr)
                sys.exit(2)
            argv = builder()
            if argv is None:
                # Allowed skips: poster_ps1 when pwsh missing, or optional recovery disabled.
                if s.key in {"poster_ps1", "recover_edge_chops"}:
                    if s.marker_path:
                        write_marker(s.marker_path, {"skipped": True, "at": time.time()})
                    continue
                # Any other None means something critical was missing; die
                print(f"[ERROR] Step {s.key} could not build its command.", file=sys.stderr)
                sys.exit(2)

            # ensure_repo must exist AND return success; also sanity-check the repo root afterward
            rc, _, _ = run_cmd(s.title, argv, log_path=step_log_path(s.key))
            if rc != 0:
                print(f"[FAIL] {s.key} exited with code {rc}. Stopping.", file=sys.stderr)
                print_abort_recovery(s.key, rc)
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

            # scan_kometa_logs: if clearly zero, stop
            elif s.key == "scan_kometa_logs":
                zero = parse_zero_from_log(log_path_for("scan_kometa_logs.py"))
                if zero is True:
                    if manual_override_count > 0:
                        print(
                            "[INFO] scan_kometa_logs found 0 auto items, "
                            f"but {manual_override_count} manual override(s) exist in {people_override_file} - continuing."
                        )
                    else:
                        print("[INFO] scan_kometa_logs found 0 items - stopping.")
                        sys.exit(0)

            # find_and_download_missing: if clearly zero, stop
            elif s.key == "find_and_download_missing":
                zero = parse_zero_from_log(log_path_for("find_and_download_missing_people.py"))
                if zero is True:
                    if manual_override_count > 0:
                        print(
                            "[INFO] find_and_download_missing produced 0 auto items, "
                            f"but {manual_override_count} manual override(s) exist in {people_override_file} - continuing."
                        )
                    else:
                        print("[INFO] find_and_download_missing produced 0 items - stopping.")
                        sys.exit(0)

            # tmdb: if no new posters created, stop
            elif s.key == "tmdb":
                created = count_recent_files([CONFIG_DIR], started, {"jpg", "jpeg", "png"})
                if created == 0:
                    print("[INFO] tmdb downloaded 0 posters - stopping.")
                    sys.exit(0)

            # audit_people_images: if processed 0, stop (parse its log rather than filesystem)
            elif s.key == "audit_people_images":
                md_count = parsed_processed_from_audit_people_images(log_path_for("audit_people_images.py"))
                if md_count is not None and md_count == 0:
                    print("[INFO] audit_people_images sorted/moved 0 items - stopping.")
                    sys.exit(0)

            elif s.key == "colorize":
                colored = count_recent_files([CONFIG_DIR / "Downloads" / "color"], started, {"jpg", "jpeg", "png"})
                print(f"[INFO] colorize produced {colored} file(s).")

            # prep_dirs: if established/moved 0 artifacts, stop (use fs heuristic as fallback)
            elif s.key == "prep_dirs":
                pd = CONFIG_DIR / "people_dirs"
                changed = count_recent_files([pd], started, {"jpg", "jpeg", "png", "md"})
                if changed == 0:
                    zero = parse_zero_from_log(log_path_for("prep_people_dirs.py"))
                    if zero is True:
                        print("[INFO] prep_dirs moved 0 items - stopping.")
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
                        print(f"[INFO] sel_remove_bg produced 0 files in {bg_output_dir} - stopping.")
                        sys.exit(0)

            # sync_images: if copied nothing, stop before readme/sync_md/push (parse its log)
            elif s.key == "sync_images":
                sync_log = log_path_for("sync_people_images.py")
                copied_sum = sum_copied_from_sync_log(sync_log)
                if copied_sum is not None and copied_sum == 0:
                    print("[INFO] sync_images copied 0 files - stopping before readme/sync_md/push.")
                    sys.exit(0)

            # Write checkpoint if applicable (and not always_run)
            if s.marker_path and not s.always_run:
                write_marker(s.marker_path, {"at": time.time(), "argv": argv})

        print("\nAll steps completed.")
    finally:
        release_lock()


if __name__ == "__main__":
    main()
