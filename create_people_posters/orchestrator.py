#!/usr/bin/env python3
"""
orchestrator.py — fixed-order, resumable pipeline runner (replaces runit.cmd)

Key behavior
------------
- Enforces a single, correct step order. Users CANNOT reorder steps.
- Checkpoints each step to allow resume after Ctrl-C/crash.
- Default mode: resume from the first step that isn't completed.
- Uses clone-free GitHub publishing and isolated batch jobs by default.
- Tools read defaults from ./config/.env; override some paths via CLI.
- Uses sys.executable so it works the same on Windows/macOS/Linux.

Core steps (order is enforced; do not reorder):
  1) ensure_repo               -> ensure_people_repo.py               (always runs: cheap sanity check)
  2) scan_kometa_logs          -> scan_kometa_logs.py                 (checkpointed)
  3) find_and_download_missing -> find_and_download_missing_people.py (checkpointed)
  4) tmdb                      -> tmdb_people.py                      (checkpointed)
  5) truncate                  -> truncate_tmdb_people_names.py       (checkpointed)
  6) audit_people_images       -> audit_people_images.py              (checkpointed)
  7) colorize_noncolor         -> selected COLORIZE_ENGINE script     (checkpointed)
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
  python orchestrator.py --redo remove_bg --stop-after poster_ps1

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
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = Path(os.getenv("PEOPLE_CONFIG_DIR") or SCRIPT_DIR / "config")
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


def background_engine() -> str:
    engine = os.getenv("REMOVE_BG_ENGINE", "birefnet").strip().lower()
    if engine not in {"adobe", "birefnet"}:
        raise ValueError("REMOVE_BG_ENGINE must be adobe or birefnet")
    return engine


def background_python(default_python: str) -> str:
    configured = _python_spec_to_argv(os.getenv("REMOVE_BG_PYTHON", ""))
    if configured:
        executable = configured[0]
        path = Path(executable).expanduser()
        if path.is_file():
            return str(path.resolve())
        resolved = shutil.which(executable)
        if resolved:
            return str(Path(resolved).resolve())
        raise ValueError(f"REMOVE_BG_PYTHON executable is unavailable: {executable}")
    local = SCRIPT_DIR / ".venv-rembg" / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")
    return str(local) if local.is_file() else default_python


def background_fingerprint() -> dict:
    engine = background_engine()
    fingerprint = {"engine": engine}
    if engine == "birefnet":
        from remove_bg_birefnet import Settings
        settings = Settings.from_env()
        fingerprint = settings.fingerprint()
        fingerprint.update({
            "python": background_python(sys.executable),
            "rembg_home": str(settings.home),
        })
    return fingerprint


def build_background_command(default_python: str, script: str | None = None) -> List[str]:
    engine = background_engine()
    python = background_python(default_python) if engine == "birefnet" else default_python
    return [python, script or ("remove_bg_birefnet.py" if engine == "birefnet" else "sel_remove_bg.py")]


def background_checkpoint_changed(fingerprint: dict) -> bool:
    pending = STATE_DIR / "remove_bg.pending.json"
    if pending.exists():
        return True
    marker = STATE_DIR / "remove_bg.done.json"
    if not marker.exists():
        return False
    try:
        meta = json.loads(marker.read_text(encoding="utf-8"))
        previous = meta.get("background_fingerprint", {"engine": "adobe"})
    except (OSError, ValueError, AttributeError):
        return True
    if previous != fingerprint:
        return True
    return (
        fingerprint["engine"] == "birefnet"
        and meta.get("outcome") == "no_work"
        and background_inputs_exist()
    )


def background_inputs_exist() -> bool:
    source = env_path("SEL_SRC_DIR") or (CONFIG_DIR / "people_dirs" / "Downloads")
    exts = {".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".png"}
    if not source.exists():
        return False
    for path in source.iterdir():
        if not path.is_file() or path.suffix.lower() not in exts:
            continue
        # A staged cutout is not a preserved source photograph.
        if path.suffix.lower() == ".png":
            from PIL import Image
            try:
                with Image.open(path) as image:
                    if "A" in image.getbands() and image.getchannel("A").getextrema()[0] < 255:
                        continue
            except OSError:
                pass  # Let the backend report corrupt inputs.
        return True
    return False


def local_background_summary(started: float) -> dict:
    path = CONFIG_DIR / "logs" / "remove_bg_birefnet.json"
    try:
        if path.stat().st_mtime < started - 1.0:
            return {}
        summary = json.loads(path.read_text(encoding="utf-8"))
        return summary if isinstance(summary, dict) else {}
    except (OSError, ValueError):
        return {}


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


def _colorize_engine() -> str:
    engine = os.getenv("COLORIZE_ENGINE", "ddcolor").strip().lower() or "ddcolor"
    if engine != "ddcolor":
        raise ValueError("Only DDColor is supported; set COLORIZE_ENGINE=ddcolor")
    return engine


def _colorize_python_candidates(default_python: str) -> list[tuple[str, List[str]]]:
    configured = _python_spec_to_argv(os.getenv("COLORIZE_PYTHON", ""))
    candidates: list[tuple[str, List[str]]] = []
    if configured:
        candidates.append(("COLORIZE_PYTHON", configured))

    local_venv = SCRIPT_DIR / ".venv-ddcolor" / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")
    candidates.append(("local .venv-ddcolor", [str(local_venv)]))
    if sys.platform.startswith("win"):
        candidates.append(("Python launcher 3.13", ["py", "-3.13"]))
        candidates.append(("Python launcher 3", ["py", "-3"]))
    candidates.append(("python3.13", ["python3.13"]))
    candidates.append(("python3", ["python3"]))
    candidates.append(("orchestrator Python", [default_python]))

    seen: set[tuple[str, ...]] = set()
    unique: list[tuple[str, List[str]]] = []
    for label, prefix in candidates:
        key = tuple(prefix)
        if key in seen:
            continue
        seen.add(key)
        unique.append((label, prefix))
    return unique


def _python_probe(argv_prefix: List[str], require_colorize_deps: bool) -> Tuple[bool, str]:
    if not argv_prefix:
        return False, "empty interpreter command"
    probe = "import sys; print(sys.executable)"
    if require_colorize_deps:
        probe = (
            "import sys; "
            "import torch, torchvision, cv2, numpy, PIL, huggingface_hub; "
            "assert sys.version_info >= (3, 10), 'Python 3.10+ required for DDColor'; "
            "print(sys.executable)"
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


def build_colorize_command(default_python: str) -> List[str]:
    try:
        engine = _colorize_engine()
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)

    require_deps = _colorize_candidates_exist()
    script = "colorize_noncolor_ddcolor.py"
    failures: list[str] = []

    for label, prefix in _colorize_python_candidates(default_python):
        ok, detail = _python_probe(prefix, require_colorize_deps=require_deps)
        if ok:
            if label != "COLORIZE_PYTHON":
                if _clean_env_value(os.getenv("COLORIZE_PYTHON")):
                    print(f"[WARN] COLORIZE_PYTHON is not usable; using {label}: {' '.join(prefix)}")
                else:
                    print(f"[INFO] Using {label}: {' '.join(prefix)}")
            print(f"[INFO] COLORIZE_ENGINE={engine}; script={script}")
            return prefix + [script]
        failures.append(f"{label} ({' '.join(prefix)}): {detail}")

    print("[ERROR] No usable Python interpreter found for the colorize step.", file=sys.stderr)
    if require_deps:
        print("[ERROR] Grayscale files are waiting in config/Downloads/other, so DDColor deps are required.", file=sys.stderr)
    else:
        print("[ERROR] Even the no-op colorize check could not start any Python interpreter.", file=sys.stderr)
    for failure in failures:
        print(f"[ERROR]   {failure}", file=sys.stderr)
    sys.exit(2)


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
    if step_key == "remove_bg" and rc == 4 and background_engine() == "adobe":
        print(
            "[ABORT] Adobe login is required. Completed downloads were kept; "
            "remaining JPGs are still queued for retry.",
            file=sys.stderr,
        )
        print("[NEXT] Run: python sel_remove_bg.py --login-only", file=sys.stderr)
        print("[NEXT] Then resume: python orchestrator.py --redo remove_bg --no-recover-edge-chops", file=sys.stderr)
        return
    if step_key == "remove_bg" and background_engine() == "birefnet":
        print("[NEXT] Check REMOVE_BG_PYTHON, requirements-rembg.txt, REMOVE_BG_MODEL and REMBG_HOME; fix the backend error above. Existing outputs require REMOVE_BG_OVERWRITE=true to replace.", file=sys.stderr)
    print(f"[NEXT] Resume after fixing the issue: python orchestrator.py --redo {step_key}", file=sys.stderr)


def acquire_lock() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        from people_workspaces import process_alive
        try:
            pid = int(LOCK_FILE.read_text(encoding="utf-8").split()[0])
        except (ValueError, OSError, IndexError):
            pid = -1
        if pid < 0 or process_alive(pid):
            print(f"[ERROR] Another run or an unrecognized lock exists: {LOCK_FILE}", file=sys.stderr)
            sys.exit(3)
        LOCK_FILE.unlink()
    try:
        descriptor = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        sys.exit(3)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(f"{os.getpid()} @ {datetime.now().isoformat()}")


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
    m = re.search(r"(?:Files processed:\s*|Summary:\s*processed\s*=\s*)(\d+)", text, flags=re.I)
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
    global CONFIG_DIR, STATE_DIR
    os.environ.setdefault("PYTHONIOENCODING", "utf-8:replace")
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    import argparse
    if "--list" in sys.argv[1:]:
        if load_dotenv:
            load_dotenv(CONFIG_DIR / ".env")
    else:
        load_env_or_bootstrap()
    people_override_file = Path(os.getenv("PEOPLE_OVERRIDE_LIST") or (CONFIG_DIR / "people_overrides.txt"))
    manual_override_count = count_manual_people_overrides(people_override_file)

    parser = argparse.ArgumentParser(description="Fixed-order, resumable pipeline runner")
    parser.add_argument("--force", action="store_true", help="Ignore checkpoints and run all steps from the beginning.")
    parser.add_argument("--redo", help="Clear checkpoint for this step (and downstream) and restart at that step.")
    parser.add_argument("--stop-after", help="Stop cleanly after this step completes; useful for recovery QA gates.")
    parser.add_argument("--list", action="store_true", help="List step status and exit.")
    parser.add_argument("--publish-mode", choices=["local_git", "github_api"], default=os.getenv("PEOPLE_PUBLISH_MODE", "github_api"),
                        help="Publishing backend (default: github_api; local_git requires full image clones)")
    parser.add_argument("--workspace-mode", choices=["persistent", "batch"], default=os.getenv("PEOPLE_WORKSPACE_MODE", "batch"),
                        help="Processing workspace (default: batch; persistent uses legacy staging)")
    parser.add_argument("--batch-id", help="Resume a particular managed batch")
    parser.add_argument("--new-batch", action="store_true", help="Create an isolated batch instead of resuming")
    parser.add_argument("--people-list", type=Path, help="Explicit input list; skip log discovery for this run")
    parser.add_argument("--dry-run", action="store_true", help="API publication preview; generation may write local outputs, never publishes or cleans")
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
    from people_github import sandbox_settings
    if sandbox_settings() and (args.publish_mode != "github_api" or args.workspace_mode != "batch"):
        parser.error("Sandbox requires github_api + batch; local_git/persistent are blocked")
    if args.publish_mode not in {"local_git", "github_api"} or args.workspace_mode not in {"persistent", "batch"}:
        parser.error("Invalid PEOPLE_PUBLISH_MODE or PEOPLE_WORKSPACE_MODE")
    if args.dry_run and args.publish_mode != "github_api":
        parser.error("--dry-run is for github_api publishing; use the legacy tools' dry-run options for local_git")
    if args.people_list and not args.people_list.is_file():
        parser.error("--people-list must be an existing file")
    os.environ["PEOPLE_PUBLISH_MODE"] = args.publish_mode
    os.environ["PEOPLE_WORKSPACE_MODE"] = args.workspace_mode
    manager = None
    batch = None
    if args.workspace_mode == "batch":
        from people_workspaces import Workspaces
        manager = Workspaces(CONFIG_DIR)
        if args.list:
            rows = manager.db.execute("SELECT id,status FROM jobs ORDER BY created DESC").fetchall()
            for row in rows:
                print(f"Batch {row['id']}: {row['status']}")
            manager.close()
            return
        try:
            batch = manager.select(args.batch_id, args.new_batch, args.people_list, cleanup=not args.dry_run)
            CONFIG_DIR = manager.configure(batch)
            STATE_DIR = CONFIG_DIR / ".orch"
            _, batch_manifest = manager.record(batch)
            args.people_list = (CONFIG_DIR / "people_list.txt") if batch_manifest.get("explicit_people_list") else None
            print(f"[INFO] Batch: {batch}; workspace: {CONFIG_DIR}")
        except (OSError, ValueError) as error:
            manager.close()
            parser.error(str(error))
    elif args.batch_id or args.new_batch:
        parser.error("--batch-id and --new-batch require --workspace-mode batch")
    if args.people_list:
        os.environ["PEOPLE_LIST"] = str(args.people_list.resolve())
        manual_override_count += count_manual_people_overrides(args.people_list)
    try:
        bg_fingerprint = background_fingerprint()
    except ValueError as exc:
        parser.error(str(exc))
    bg_changed = background_checkpoint_changed(bg_fingerprint)

    # Resolve env/args
    logs_dir = Path(args.logs_dir).expanduser().resolve() if args.logs_dir else env_path("ORCH_LOGS_DIR")
    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else env_path("PEOPLE_IMAGES_DIR")
    branch = _clean_env_value(args.branch or os.getenv("PEOPLE_BRANCH", ""))
    if args.publish_mode == "github_api":
        from people_github import branch_name
        branch = branch_name(branch)
        os.environ["PEOPLE_BRANCH"] = branch
        if args.generate_readmes or _bool_env("ORCH_GENERATE_READMES", False):
            parser.error("API mode uses destination README Actions; disable ORCH_GENERATE_READMES")
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
        return build_colorize_command(py)

    def _require_repo_or_die():
        if not repo_root or not repo_root.exists():
            print("[ERROR] PEOPLE_IMAGES_DIR not set or invalid; required for this step.", file=sys.stderr)
            sys.exit(2)

    def _ensure_repo():
        if args.publish_mode == "github_api":
            return _api_command("validate")
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
        return build_background_command(py)

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
        args2 = build_background_command(py, "recover_edge_chops.py") + [
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
        if args.publish_mode == "github_api":
            return _api_command("refresh")
        _require_repo_or_die()
        args2 = ["--repo-root", str(repo_root)]
        if branch:
            args2 += ["--branch", branch]
        args2 += ["--op", "update", "--mode", "hardreset", "--clean-ignored"]
        return [py, "update_people_repos.py"] + args2

    def _sync_images():
        if args.publish_mode == "github_api":
            return _api_command("prepare")
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
        if args.publish_mode == "github_api":
            return _api_command("push")
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

    def _api_command(operation):
        command = [py, "publish_people_github.py", "--op", operation, "--config", str(CONFIG_DIR), "--branch", branch]
        if batch:
            command += ["--batch-id", batch]
        if args.dry_run:
            command.append("--dry-run")
        return command

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
        Step("remove_bg",                 f"Remove backgrounds ({bg_fingerprint['engine']})", _remove_bg,              marker="remove_bg.done.json"),
        Step("poster_ps1",                "Generate posters via PowerShell",            _poster_ps1,                marker="poster_ps1.done.json"),
        Step("recover_edge_chops",        "Retry top-edge chops from TMDB alternates",   _recover_edge_chops,        marker="recover_edge_chops.done.json"),
        Step("update",                    "git fetch/reset category repos",             _update_repos,              marker=None,              always_run=True),
        Step("sync_images",               "Sync images to repo folders",                _sync_images,               marker="sync_images.done.json"),
        Step("readme",                    "Generate README files",                      None,                       marker="readme.done.json"),
        Step("sync_md",                   "Mirror *.md back to config (per style)",     None,                       marker="sync_md.done.json"),
        Step("push",                      "Commit & push changes upstream",             _push_repos,                marker=None,              always_run=True),
    ]

    step_index = {s.key: i for i, s in enumerate(steps)}
    if args.stop_after and args.stop_after not in step_index:
        print(f"[ERROR] Unknown step key for --stop-after: {args.stop_after}", file=sys.stderr)
        print("Valid keys:", ", ".join(step_index.keys()), file=sys.stderr)
        sys.exit(2)

    # Status mode
    if args.list:
        print("Step status:")
        for s in steps:
            invalid = bg_changed and step_index[s.key] >= step_index["remove_bg"]
            status = "ALWAYS" if s.always_run else ("DONE" if marker_exists(s.marker_path) and not invalid else "PENDING")
            print(f" - {s.key:12} : {status}")
        for s in steps:
            if s.always_run or not marker_exists(s.marker_path):
                print(f"\nNext step would be: {s.key} - {s.title}")
                break
        return

    # Handle --redo (mutations happen only after acquiring the lock).
    if args.redo:
        if args.redo not in step_index:
            print(f"[ERROR] Unknown step key for --redo: {args.redo}", file=sys.stderr)
            print("Valid keys:", ", ".join(step_index.keys()), file=sys.stderr)
            sys.exit(2)

    # Compute start index
    start_i = 0
    if args.force:
        start_i = 0
    elif args.redo:
        start_i = step_index[args.redo]
        if bg_changed:
            start_i = min(start_i, step_index["remove_bg"])
    else:
        for i, s in enumerate(steps):
            if s.always_run or not marker_exists(s.marker_path):
                start_i = i
                break
    if args.stop_after and step_index[args.stop_after] < start_i:
        print(f"[INFO] --stop-after {args.stop_after} is before the selected start step; nothing to run.")
        return

    # Run
    acquire_lock()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    activated = False
    try:
        if manager:
            manager.activate(batch)
            activated = True
            manager.set_status(batch, "processing")
            if _bool_env("PEOPLE_AUTO_CLEANUP", True) and not args.dry_run:
                for old_batch, outcome in manager.cleanup(dry_run=False):
                    print(f"[CLEANUP] {old_batch}: {outcome}")
        if args.publish_mode == "github_api" and start_i > 0:
            rc, _, _ = run_cmd("Validate GitHub destinations", _api_command("validate"))
            if rc:
                sys.exit(rc)
        if bg_changed:
            clear_from(list(step_index.keys()), "remove_bg")
            write_marker(STATE_DIR / "remove_bg.pending.json", {"background_fingerprint": bg_fingerprint})
            if not background_inputs_exist():
                print("[ERROR] Background engine/config changed but no source photographs are queued. Restage specific preserved inputs from SEL_ORIG_DIR into SEL_SRC_DIR, then run --redo remove_bg. Set REMOVE_BG_OVERWRITE=true explicitly to replace existing local/Adobe outputs.", file=sys.stderr)
                sys.exit(2)
        if args.redo:
            clear_from(list(step_index.keys()), args.redo)
        step_started_at: dict[str, float] = {}
        for s in steps[start_i:]:
            if manager:
                manager.check_budget()
            if args.people_list and s.key in {"scan_kometa_logs", "find_and_download_missing"}:
                write_marker(s.marker_path, {"skipped": True, "reason": "explicit --people-list"})
                continue
            if not args.force and not s.always_run and marker_exists(s.marker_path):
                print(f"[INFO] {s.key} already completed - skipping.")
                if s.key == args.stop_after:
                    return
                continue
            step_started_at[s.key] = time.time()

            # Special multi-style steps handle inside the loop
            if s.key == "readme":
                if not generate_readmes:
                    print("[INFO] local README generation disabled - skipping readme step.")
                    if s.marker_path:
                        write_marker(s.marker_path, {"skipped": True, "at": time.time(), "reason": "ORCH_GENERATE_READMES=false"})
                    if s.key == args.stop_after:
                        print(f"[INFO] Stop requested after {s.key}; exiting before downstream steps.")
                        return
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
                if s.key == args.stop_after:
                    print(f"[INFO] Stop requested after {s.key}; exiting before downstream steps.")
                    return
                continue

            if s.key == "sync_md":
                if not generate_readmes:
                    print("[INFO] local README generation disabled - skipping sync_md step.")
                    if s.marker_path:
                        write_marker(s.marker_path, {"skipped": True, "at": time.time(), "reason": "ORCH_GENERATE_READMES=false"})
                    if s.key == args.stop_after:
                        print(f"[INFO] Stop requested after {s.key}; exiting before downstream steps.")
                        return
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
                if s.key == args.stop_after:
                    print(f"[INFO] Stop requested after {s.key}; exiting before downstream steps.")
                    return
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
                    if s.key == args.stop_after:
                        print(f"[INFO] Stop requested after {s.key}; exiting before downstream steps.")
                        return
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
            if s.key == "ensure_repo" and args.publish_mode == "local_git":
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
                    if manager:
                        manager.set_status(batch, "no_work")
                    print("[INFO] tmdb downloaded 0 posters - stopping.")
                    sys.exit(0)

            # audit_people_images: if processed 0, stop (parse its log rather than filesystem)
            elif s.key == "audit_people_images":
                md_count = parsed_processed_from_audit_people_images(log_path_for("audit_people_images.py"))
                if md_count is not None and md_count == 0:
                    if manager:
                        manager.set_status(batch, "no_work")
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
                local_summary = local_background_summary(started) if bg_fingerprint["engine"] == "birefnet" else {}
                if bg_changed and local_summary.get("outcome") == "no_work":
                    print("[ERROR] Changed background configuration processed no source photographs; restage specific preserved inputs before retrying.", file=sys.stderr)
                    sys.exit(2)
                if REQUIRE_BG_OUTPUT and not bg_output_dir:
                    print("[ERROR] ORCH_REQUIRE_BG_OUTPUT=true but SEL_DOWNLOAD_DIR is unknown.", file=sys.stderr)
                    sys.exit(2)
                processed = count_recent_files([bg_output_dir] if bg_output_dir else [], started, bg_exts)
                if processed == 0 and not continue_if_empty:
                    # If fs says 0, but the tool log shows >0, continue (saves you from dir mismatch).
                    rb_log = log_path_for("remove_bg_birefnet.py" if bg_fingerprint["engine"] == "birefnet" else "sel_remove_bg.py")
                    log_n = parsed_files_processed_from_remove_bg(rb_log)
                    source = env_path("SEL_SRC_DIR") or (CONFIG_DIR / "people_dirs" / "Downloads")
                    ready = bg_fingerprint["engine"] == "birefnet" and source.exists() and any(source.glob("*.png"))
                    if ((log_n is None) or (log_n == 0)) and not ready:
                        if local_summary.get("outcome") == "no_work" and local_summary.get("exit_code") == 0:
                            write_marker(s.marker_path, {
                                "at": time.time(), "argv": argv, "background_fingerprint": bg_fingerprint,
                                "outcome": "no_work", "model_verified": False,
                            })
                        print(f"[INFO] {bg_fingerprint['engine']} produced 0 files in {bg_output_dir} - stopping.")
                        sys.exit(0)

            # sync_images: if copied nothing, stop before readme/sync_md/push (parse its log)
            elif s.key == "sync_images" and args.publish_mode == "local_git":
                sync_log = log_path_for("sync_people_images.py")
                copied_sum = sum_copied_from_sync_log(sync_log)
                if copied_sum is not None and copied_sum == 0 and not manager:
                    print("[INFO] sync_images copied 0 files - stopping before readme/sync_md/push.")
                    sys.exit(0)

            # Write checkpoint if applicable (and not always_run)
            if manager and s.key == "poster_ps1":
                manager.set_status(batch, "generated")
            if manager and s.key == "sync_images":
                manager.set_status(batch, "validated")
            if s.marker_path and not s.always_run and not args.dry_run:
                meta = {"at": time.time(), "argv": argv}
                if s.key == "remove_bg":
                    meta["background_fingerprint"] = bg_fingerprint
                    if bg_fingerprint["engine"] == "birefnet" and local_summary:
                        meta["outcome"] = local_summary.get("outcome")
                        meta["model_verified"] = local_summary.get("processed", 0) > 0
                write_marker(s.marker_path, meta)
                if s.key == "remove_bg":
                    (STATE_DIR / "remove_bg.pending.json").unlink(missing_ok=True)
            if s.key == args.stop_after and s.key != "push":
                print(f"[INFO] Stop requested after {s.key}; exiting before downstream steps.")
                return

        if manager and not args.dry_run:
            from people_publication_state import PublicationState
            ledger = PublicationState(manager.state)
            try:
                if args.publish_mode == "local_git":
                    from publish_people_github import prepare, verify_local_publication
                    prepare(CONFIG_DIR, batch, ledger, branch or "master")
                    verify_local_publication(batch, ledger, repo_root, branch or "master")
                manager.confirm_published(batch, ledger)
            finally:
                ledger.close()
        elif args.publish_mode == "github_api" and not args.dry_run:
            # A completed persistent run gets a new receipt ID on its next generation run.
            (CONFIG_DIR / ".orch" / "api-batch.json").unlink(missing_ok=True)
        print("\nPublication dry-run completed; files retained." if args.dry_run else "\nAll steps completed.")
    except BaseException as error:
        if manager and activated and not (isinstance(error, SystemExit) and error.code in {None, 0}):
            from people_publication_state import PublicationState
            ledger = PublicationState(manager.state)
            try:
                partial = any(row["status"] == "published" for row in ledger.rows(batch))
                manager.set_status(batch, "partially_published" if partial else "failed",
                                   "Interrupted" if isinstance(error, KeyboardInterrupt) else str(error))
            finally:
                ledger.close()
        raise
    finally:
        if manager:
            manager.deactivate(batch)
            manager.close()
        release_lock()


if __name__ == "__main__":
    main()
