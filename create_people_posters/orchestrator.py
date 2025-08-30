#!/usr/bin/env python3
"""
orchestrator.py — cross-platform runner that replaces runit.cmd

It sequences the pipeline with sensible defaults from ./config/.env,
but you can override anything via CLI flags. It uses sys.executable so
it works the same on Windows/macOS/Linux and in virtualenvs.

Default steps (in order):
  1) name_checker_dir.py           — scan Kometa logs for missing names
  2) get_missing_people.py         — download missing people text lists
  3) tmdb_people.py                — pull posters via TMDB API
  4) sel_remove_bg.py              — send posters through Adobe Express (Selenium)
  5) ensure_people_repo.py         — validate Kometa-People-Images repo
  6) sync_people_images.py         — copy images from ./config/people_dirs/* → repo
  7) update_people_repos.py        — git fetch/merge each category repo
  8) auto_readme.py                — generate README grid for chosen style
  9) sync_md.py                    — copy *.md back to ./config/people_dirs/<style>

Examples:
  python orchestrator.py --all
  python orchestrator.py --steps name_check,missing,tmdb,remove_bg --logs-dir "/path/to/kometa/logs"
  python orchestrator.py --repo-root "$PEOPLE_IMAGES_DIR" --style transparent --branch master

Env (from ./config/.env or process environment):
  ORCH_LOGS_DIR       — default logs folder for steps 1–2
  PEOPLE_IMAGES_DIR   — repo root for steps 5–9
  PEOPLE_BRANCH       — git branch for step 7 (default: master)
  ORCH_STYLE          — style for step 8 & 9 (default: transparent)
"""
import os
import sys
import shlex
import subprocess
from pathlib import Path
from typing import List

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"


def env_path(key: str, default: str | None = None):
    value = os.getenv(key, default if default is not None else "")
    return Path(value).expanduser().resolve() if value else None


def load_env():
    if load_dotenv:
        env_file = CONFIG_DIR / ".env"
        if not env_file.exists():
            # bootstrap a minimal .env from example if missing
            example = CONFIG_DIR / ".env.example"
            try:
                example_src = SCRIPT_DIR / ".env.example"  # fallback (repo root)
                content = (example.read_text(encoding="utf-8")
                           if example.exists()
                           else example_src.read_text(encoding="utf-8"))
                (CONFIG_DIR).mkdir(parents=True, exist_ok=True)
                (CONFIG_DIR / ".env").write_text(content, encoding="utf-8")
            except Exception:
                pass
            print(f"Missing ./config/.env — created one from example.\n"
                  f"Please set at least TMDB_KEY inside: {CONFIG_DIR / '.env'}",
                  file=sys.stderr)
            sys.exit(1)
        load_dotenv(env_file)


def run_step(title: str, argv: List[str]) -> int:
    print(f"\n=== {title} ===")
    try:
        cp = subprocess.run(argv, cwd=str(SCRIPT_DIR))
        return cp.returncode
    except FileNotFoundError as e:
        print(f"[ERROR] {title}: {e}", file=sys.stderr)
        return 127
    except Exception as e:
        print(f"[ERROR] {title}: {e}", file=sys.stderr)
        return 1


def main():
    import argparse
    load_env()

    parser = argparse.ArgumentParser(description="Cross-platform pipeline runner")
    parser.add_argument("--all", action="store_true", help="Run all default steps")
    parser.add_argument("--steps", help="Comma list of steps to run (overrides --all).")
    parser.add_argument("--logs-dir", help="Kometa logs folder for steps 1–2 (env ORCH_LOGS_DIR otherwise).")
    parser.add_argument("--repo-root", help="Kometa-People-Images repository root (env PEOPLE_IMAGES_DIR otherwise).")
    parser.add_argument("--branch", help="Git branch for update step (env PEOPLE_BRANCH or 'master').")
    parser.add_argument("--style", help="People-Images style for README & MD sync (env ORCH_STYLE or 'transparent').")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing.")
    args = parser.parse_args()

    # resolve env/args
    logs_dir = Path(args.logs_dir).expanduser().resolve() if args.logs_dir else env_path("ORCH_LOGS_DIR")
    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else env_path("PEOPLE_IMAGES_DIR")
    branch = args.branch or os.getenv("PEOPLE_BRANCH", "master")
    style = args.style or os.getenv("ORCH_STYLE", "transparent")

    # python exec
    py = sys.executable

    # step builders
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

    def _remove_bg():
        return [py, "sel_remove_bg.py"]

    def _ensure_repo():
        args2 = ["--repo-root", str(repo_root)] if repo_root else []
        return [py, "ensure_people_repo.py"] + args2

    def _sync_images():
        args2 = ["--dest_root", str(repo_root)] if repo_root else []
        return [py, "sync_people_images.py"] + args2

    def _update_repos():
        args2 = []
        if repo_root:
            args2 += ["--repo-root", str(repo_root)]
        if branch:
            args2 += ["--branch", branch]
        return [py, "update_people_repos.py"] + args2

    def _auto_readme():
        args2 = ["--style", style]
        if repo_root:
            args2 += ["--directory", str((repo_root / style).resolve())]
        return [py, "auto_readme.py"] + args2

    def _sync_md():
        if not repo_root:
            print("[WARN] --repo-root/PEOPLE_IMAGES_DIR not set; skipping sync_md.", file=sys.stderr)
            return None
        src = str((repo_root / style).resolve())
        dst = str((CONFIG_DIR / "people_dirs" / style).resolve())
        return [py, "sync_md.py", "--src", src, "--dst", dst, "--pattern", "*.md"]

    steps_order = [
        ("name_check", "Scan Kometa logs for missing names", _name_check),
        ("missing", "Build missing-people lists", _missing),
        ("tmdb", "Download posters via TMDB", _tmdb),
        ("remove_bg", "Remove backgrounds (Selenium)", _remove_bg),
        ("ensure_repo", "Validate People-Images repo", _ensure_repo),
        ("sync_images", "Sync images to repo folders", _sync_images),
        ("update", "git fetch/merge category repos", _update_repos),
        ("readme", "Generate README grid", _auto_readme),
        ("sync_md", "Mirror *.md back to config", _sync_md),
    ]

    if args.steps:
        wanted = [s.strip() for s in args.steps.split(",") if s.strip()]
        selected = [item for item in steps_order if item[0] in wanted]
    elif args.all:
        selected = steps_order
    else:
        parser.print_help()
        print("\nTip: run with --all or select with --steps name_check,tmdb,remove_bg …")
        return

    rc_total = 0
    for key, title, builder in selected:
        argv = builder()
        if argv is None:
            rc_total |= 1
            continue
        print("→", " ".join(shlex.quote(a) for a in argv))
        if args.dry_run:
            continue
        rc = run_step(title, argv)
        rc_total |= (rc != 0)

    sys.exit(0 if rc_total == 0 else 1)


if __name__ == "__main__":
    main()
