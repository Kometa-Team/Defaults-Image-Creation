#!/usr/bin/env python3
"""Prune generated files under create_people_posters/config.

Default mode is a dry run. Pass --apply to delete.

This intentionally preserves live pipeline state by default:
  - .env, people_list.txt, people_overrides.txt
  - checkpoints under .orch
  - browser login profile under chrome-profile
  - model/vendor caches
  - active staging folders under Downloads and people_dirs
  - recovery state files: exhausted_names.txt and attempted_candidates.csv
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"

DEFAULT_DAYS = 14

PRESERVE_ROOT_NAMES = {
    ".env",
    ".orch",
    "chrome-profile",
    "Downloads",
    "dummy",
    "models",
    "people_dirs",
    "people_list.txt",
    "people_overrides.txt",
    "vendor",
}

AGE_PRUNE_ROOT_NAMES = {
    "edge_chop_recovery",
    "logs",
    "original_resolver",
    "parsed_configs",
    "posters",
    "result_images",
    "review_original_candidates",
    "sel_downloads",
}

AGE_PRUNE_FILE_GLOBS = (
    "*.csv",
    "*.log",
    "*.md",
    "*.zip.*",
    "people_list.*.bak.txt",
    "rebuild_since_signature_commit.txt",
    "traceback_summary.txt",
)

PRESERVE_FILES = {
    ".env",
    "people_list.txt",
    "people_overrides.txt",
}

PRESERVE_RECOVERY_STATE = {
    ("edge_chop_recovery", "attempted_candidates.csv"),
    ("edge_chop_recovery", "exhausted_names.txt"),
}


@dataclass
class Candidate:
    path: Path
    kind: str
    bytes: int
    reason: str


def log(message: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    print(message)
    with (LOGS_DIR / "clean_people_config.log").open("a", encoding="utf-8") as fh:
        fh.write(message.rstrip() + "\n")


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def tree_size(path: Path) -> int:
    total = 0
    if path.is_file():
        return file_size(path)
    for item in path.rglob("*"):
        if item.is_file():
            total += file_size(item)
    return total


def older_than(path: Path, cutoff: float) -> bool:
    try:
        return path.stat().st_mtime < cutoff
    except OSError:
        return False


def top_level_name(path: Path, root: Path) -> str:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return ""
    return parts[0] if parts else ""


def recovery_state_file(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    return tuple(parts) in PRESERVE_RECOVERY_STATE


def iter_age_pruned_files(root: Path, cutoff: float) -> Iterable[Candidate]:
    for name in sorted(AGE_PRUNE_ROOT_NAMES):
        base = root / name
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or not older_than(path, cutoff):
                continue
            if recovery_state_file(path, root):
                continue
            yield Candidate(
                path=path,
                kind="file",
                bytes=file_size(path),
                reason=f"older than cutoff under config/{name}",
            )

    for pattern in AGE_PRUNE_FILE_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file() or not older_than(path, cutoff):
                continue
            if path.name in PRESERVE_FILES:
                continue
            if top_level_name(path, root) in PRESERVE_ROOT_NAMES:
                continue
            yield Candidate(
                path=path,
                kind="file",
                bytes=file_size(path),
                reason=f"top-level generated file matching {pattern}",
            )


def iter_optional_heavy_roots(args: argparse.Namespace, root: Path) -> Iterable[Candidate]:
    optional_roots: list[tuple[bool, str, str]] = [
        (args.include_checkpoints, ".orch", "explicit --include-checkpoints"),
        (args.include_chrome_profile, "chrome-profile", "explicit --include-chrome-profile"),
        (args.include_caches, "models", "explicit --include-caches"),
        (args.include_caches, "vendor", "explicit --include-caches"),
        (args.include_staging, "Downloads", "explicit --include-staging"),
        (args.include_staging, "people_dirs/Downloads", "explicit --include-staging"),
        (args.include_staging, "people_dirs/tmppeople", "explicit --include-staging"),
    ]
    for enabled, name, reason in optional_roots:
        path = root / Path(name)
        if enabled and path.exists():
            yield Candidate(path=path, kind="tree", bytes=tree_size(path), reason=reason)

    recovery_dir = root / "edge_chop_recovery"
    if args.include_recovery_state and recovery_dir.exists():
        for filename in ("attempted_candidates.csv", "exhausted_names.txt"):
            path = recovery_dir / filename
            if path.exists() and path.is_file():
                yield Candidate(
                    path=path,
                    kind="file",
                    bytes=file_size(path),
                    reason="explicit --include-recovery-state",
                )


def unique_candidates(candidates: Iterable[Candidate], root: Path) -> list[Candidate]:
    seen: set[Path] = set()
    raw: list[Candidate] = []
    for candidate in candidates:
        path = candidate.path.resolve()
        if path in seen:
            continue
        if not is_within(path, root):
            continue
        if path == root.resolve():
            continue
        seen.add(path)
        raw.append(Candidate(path=path, kind=candidate.kind, bytes=candidate.bytes, reason=candidate.reason))

    tree_roots = [candidate.path for candidate in raw if candidate.kind == "tree"]
    out = [
        candidate for candidate in raw
        if candidate.kind == "tree"
        or not any(candidate.path != tree and is_within(candidate.path, tree) for tree in tree_roots)
    ]
    out.sort(key=lambda item: str(item.path).casefold())
    return out


def remove_empty_dirs(root: Path, protected_roots: set[Path], apply: bool) -> int:
    removed = 0
    for base_name in sorted(AGE_PRUNE_ROOT_NAMES):
        base = root / base_name
        if not base.exists() or not base.is_dir():
            continue
        for path in sorted((p for p in base.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            resolved = path.resolve()
            if any(resolved == protected or is_within(resolved, protected) for protected in protected_roots):
                continue
            try:
                if any(path.iterdir()):
                    continue
            except OSError:
                continue
            if apply:
                path.rmdir()
            removed += 1
    return removed


def delete_candidate(candidate: Candidate) -> None:
    if candidate.kind == "tree":
        shutil.rmtree(candidate.path)
    else:
        candidate.path.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run/apply cleanup for generated create_people_posters config artifacts.")
    parser.add_argument("--config-root", type=Path, default=CONFIG_DIR, help="Config directory to clean. Default: ./config")
    parser.add_argument("--days", type=float, default=float(os.getenv("CLEAN_PEOPLE_CONFIG_DAYS", DEFAULT_DAYS)), help=f"Delete age-pruned files older than this many days. Default: {DEFAULT_DAYS}")
    parser.add_argument("--apply", action="store_true", help="Actually delete files. Without this, only print what would be deleted.")
    parser.add_argument("--include-staging", action="store_true", help="Also delete active staging folders Downloads, people_dirs/Downloads, and people_dirs/tmppeople.")
    parser.add_argument("--include-checkpoints", action="store_true", help="Also delete .orch checkpoints, forcing orchestrator steps to rerun.")
    parser.add_argument("--include-chrome-profile", action="store_true", help="Also delete the Adobe Selenium Chrome profile; you will need to sign in again.")
    parser.add_argument("--include-caches", action="store_true", help="Also delete model/vendor caches; they may need to download again.")
    parser.add_argument("--include-recovery-state", action="store_true", help="Also delete recovery attempted/exhausted files.")
    parser.add_argument("--no-empty-dirs", action="store_true", help="Do not remove empty directories left inside age-pruned roots.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.config_root.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"[ERROR] config root does not exist or is not a directory: {root}", file=sys.stderr)
        return 2
    if not is_within(root, SCRIPT_DIR):
        print(f"[ERROR] refusing to clean a config root outside this script directory: {root}", file=sys.stderr)
        return 2
    if args.days < 0:
        print("[ERROR] --days must be >= 0", file=sys.stderr)
        return 2

    started = time.time()
    cutoff = started - (args.days * 86400.0)
    mode = "APPLY" if args.apply else "DRY-RUN"
    log(f"#### START clean_people_config ({mode}) ####")
    log(f"Config root: {root}")
    log(f"Age cutoff: {args.days:g} day(s)")

    candidates = unique_candidates(
        list(iter_age_pruned_files(root, cutoff)) + list(iter_optional_heavy_roots(args, root)),
        root,
    )
    total_bytes = sum(candidate.bytes for candidate in candidates)
    log(f"Candidates: {len(candidates)}")
    log(f"Bytes: {total_bytes}")

    for candidate in candidates:
        action = "delete" if args.apply else "would delete"
        log(f"[{action}] {candidate.kind:4} {candidate.bytes:12d} {rel(candidate.path, root)} :: {candidate.reason}")

    if args.apply:
        errors = 0
        for candidate in candidates:
            try:
                delete_candidate(candidate)
            except Exception as exc:
                errors += 1
                log(f"[error] failed to delete {rel(candidate.path, root)}: {exc}")
        protected = {root / name for name in PRESERVE_ROOT_NAMES}
        empty_removed = 0 if args.no_empty_dirs else remove_empty_dirs(root, protected, apply=True)
        log(f"Deleted candidates: {len(candidates) - errors}")
        log(f"Delete errors: {errors}")
        log(f"Empty dirs removed: {empty_removed}")
        rc = 1 if errors else 0
    else:
        protected = {root / name for name in PRESERVE_ROOT_NAMES}
        empty_removed = 0 if args.no_empty_dirs else remove_empty_dirs(root, protected, apply=False)
        log(f"Dry run only. Re-run with --apply to delete these candidates.")
        if empty_removed:
            log(f"Empty dirs that would be removed after pruning: {empty_removed}")
        rc = 0

    log("#### END clean_people_config ####")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
