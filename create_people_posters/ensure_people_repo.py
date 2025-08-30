#!/usr/bin/env python3
"""
ensure_people_repo.py — detect and validate the Kometa-People-Images repo structure

- Locates repo via (priority):
    1) --repo-root CLI arg
    2) PEOPLE_IMAGES_DIR from ./config/.env (if present) or process env
    3) ./Kometa-People-Images next to this script
- Verifies presence of key subfolders:
    transparent, original, bw, diiivoy, diiivoycolor, rainier, signature

Exit codes:
  0 = repo found and passes checks
  1 = repo missing or invalid
"""
import os
import sys
import logging
import argparse
from pathlib import Path
from timeit import default_timer as timer

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # optional

try:
    from alive_progress import alive_bar  # type: ignore
    HAVE_ALIVE = True
except Exception:
    HAVE_ALIVE = False  # graceful fallback

# ---------- paths + logging ----------
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


def load_env_if_present(override: bool = False):
    if load_dotenv is None:
        return
    env_path = CONFIG_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=override)


DEFAULT_FOLDERS = (
    "transparent",
    "original",
    "bw",
    "diiivoy",
    "diiivoycolor",
    "rainier",
    "signature",
)


def locate_repo(cli_path: str | None) -> Path | None:
    """Return the repo path or None. Logs each attempt."""
    if cli_path:
        p = Path(os.path.expandvars(os.path.expanduser(cli_path))).resolve()
        logging.debug("Trying CLI repo path: %s -> exists=%s", p, p.exists())
        if p.exists():
            return p

    env = os.getenv("PEOPLE_IMAGES_DIR")
    if env:
        p = Path(os.path.expandvars(os.path.expanduser(env))).resolve()
        logging.debug("Trying PEOPLE_IMAGES_DIR: %s -> exists=%s", p, p.exists())
        if p.exists():
            return p

    p = (SCRIPT_DIR / "Kometa-People-Images").resolve()
    logging.debug("Trying sibling repo path: %s -> exists=%s", p, p.exists())
    if p.exists():
        return p

    return None


def validate_structure(repo: Path) -> tuple[bool, list[str]]:
    """Check for expected subfolders; return (ok, missing_list)."""
    missing: list[str] = []
    total = len(DEFAULT_FOLDERS)

    # Progress bar (or no-op fallback)
    if HAVE_ALIVE:
        mgr = alive_bar(total, title="validate repo folders", dual_line=True)
    else:
        class _Dummy:
            def __enter__(self):
                return lambda *a, **k: None
            def __exit__(self, *a):
                return False
        mgr = _Dummy()

    with mgr as bar:
        for d in DEFAULT_FOLDERS:
            path = repo / d
            if path.exists() and path.is_dir():
                logging.debug("OK: %s", path)
                if HAVE_ALIVE:
                    bar.text = f"-> ok: {d}"
            else:
                logging.warning("Missing folder: %s", path)
                missing.append(str(path))
                if HAVE_ALIVE:
                    bar.text = f"-> missing: {d}"
            bar()
    return (len(missing) == 0, missing)


def main():
    setup_logging()
    load_env_if_present()

    ap = argparse.ArgumentParser(description="Detect Kometa-People-Images repo and validate structure")
    ap.add_argument("--repo-root", help="Path to Kometa-People-Images repo")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    start = timer()
    repo = locate_repo(args.repo_root)
    if not repo:
        logging.error("People images repo not found. Set PEOPLE_IMAGES_DIR or pass --repo-root.")
        return 1

    logging.info("Repo: %s", repo)

    ok, missing = validate_structure(repo)
    if not ok:
        logging.error("Repo structure check failed. Missing: %s", ", ".join(missing))
        return 1

    elapsed = timer() - start
    logging.info("Repo OK in %.2fs", elapsed)
    print(f"Repo OK: {repo} ({elapsed:.2f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
