#!/usr/bin/env python3
"""
Build an orchestrator-ready list from TMDB's popular people endpoint.

Default output:
  ./config/people_list.txt

Each line is written as:
  TMDB_ID|Name

That format lets tmdb_people.py fetch by exact TMDB ID while keeping the
person's display name as the poster filename label.
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
DEFAULT_OUTPUT = CONFIG_DIR / "people_list.txt"
TMDB_POPULAR_PEOPLE_URL = "https://api.themoviedb.org/3/person/popular"
PAGE_SIZE = 20
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_STYLES = (
    "bw",
    "diiivoy",
    "diiivoycolor",
    "original",
    "rainier",
    "signature",
    "transparent",
)


def setup_logging(verbose: bool = False) -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"{SCRIPT_PATH.stem}.log"
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8", mode="w"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
    return log_file


def clean_name(value: str) -> str:
    value = re.sub(r"[\r\n\t|]+", " ", value or "")
    return re.sub(r"\s+", " ", value).strip()


def normalize_name(value: str) -> str:
    return clean_name(value).casefold()


def clean_env_value(value: str | None) -> str:
    if value is None:
        return ""
    cleaned = value.strip()
    if not cleaned or cleaned.startswith("#"):
        return ""
    return cleaned


def resolve_script_path(path: Path) -> Path:
    path = path.expanduser()
    if path.is_absolute():
        return path.resolve()
    return (SCRIPT_DIR / path).resolve()


def poster_stem_to_name(stem: str) -> str:
    """
    Existing raw TMDB downloads are saved as Name-TMDB_ID.jpg before truncate.
    Final People-Images posters are saved as Name.ext. Normalize both forms.
    """
    return re.sub(r"-\d+$", "", stem).strip()


def iter_image_names(root: Path) -> set[str]:
    names: set[str] = set()
    if not root.exists():
        return names

    try:
        files = root.rglob("*")
        for path in files:
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            name = poster_stem_to_name(path.stem)
            normalized = normalize_name(name)
            if normalized:
                names.add(normalized)
    except OSError as exc:
        logging.warning("Could not scan existing images under %s: %s", root, exc)

    return names


def parse_styles(value: str) -> list[str]:
    return [style.strip() for style in value.split(",") if style.strip()]


def default_existing_roots(styles: list[str]) -> list[Path]:
    roots: list[Path] = []

    people_images_dir = clean_env_value(os.getenv("PEOPLE_IMAGES_DIR"))
    if people_images_dir:
        repo_root = Path(people_images_dir).expanduser().resolve()
        roots.extend(repo_root / style for style in styles)

    roots.extend(CONFIG_DIR / "people_dirs" / style for style in styles)
    posters_dir = clean_env_value(os.getenv("POSTER_DIR"))
    roots.append(resolve_script_path(Path(posters_dir)) if posters_dir else (CONFIG_DIR / "posters"))
    return roots


def collect_existing_names(roots: list[Path]) -> set[str]:
    existing: set[str] = set()
    seen_roots: set[Path] = set()

    for root in roots:
        try:
            resolved = root.expanduser().resolve()
        except OSError:
            resolved = root.expanduser()
        if resolved in seen_roots:
            continue
        seen_roots.add(resolved)

        names = iter_image_names(resolved)
        if names:
            logging.info("Found %d existing image name(s) under %s", len(names), resolved)
        else:
            logging.info("Found 0 existing image names under %s", resolved)
        existing.update(names)

    return existing


def tmdb_get(session: requests.Session, api_key: str, page: int, language: str) -> dict[str, Any]:
    params = {"api_key": api_key, "language": language, "page": page}

    for attempt in range(1, 6):
        response = session.get(TMDB_POPULAR_PEOPLE_URL, params=params, timeout=(10, 30))
        if response.status_code != 429:
            response.raise_for_status()
            return response.json()

        retry_after = response.headers.get("Retry-After")
        wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else min(2 * attempt, 10)
        logging.warning("TMDB rate limited page %d; waiting %ds", page, wait_seconds)
        time.sleep(wait_seconds)

    response.raise_for_status()
    return response.json()


def fetch_popular_people(
    api_key: str,
    limit: int,
    language: str,
    require_profile: bool,
    max_pages: int | None,
) -> list[dict[str, Any]]:
    people: list[dict[str, Any]] = []
    seen_ids: set[int] = set()

    with requests.Session() as session:
        page = 1
        total_pages = None
        while len(people) < limit:
            if max_pages is not None and page > max_pages:
                logging.warning("Stopped at --max-pages=%d before collecting %d people.", max_pages, limit)
                break
            if total_pages is not None and page > total_pages:
                break

            data = tmdb_get(session, api_key, page, language)
            total_pages = int(data.get("total_pages") or page)
            results = data.get("results") or []

            logging.info("Fetched page %d/%d (%d result(s))", page, total_pages, len(results))

            for person in results:
                person_id = person.get("id")
                name = clean_name(str(person.get("name") or ""))
                if not isinstance(person_id, int) or not name:
                    continue
                if person_id in seen_ids:
                    continue
                if require_profile and not person.get("profile_path"):
                    logging.debug("Skipping %s (%s): no profile_path", name, person_id)
                    continue

                people.append(person)
                seen_ids.add(person_id)
                if len(people) >= limit:
                    return people

            if not results:
                break
            page += 1

    return people


def render_people_list(people: list[dict[str, Any]]) -> str:
    lines = []
    for person in people:
        person_id = person["id"]
        name = clean_name(str(person["name"]))
        lines.append(f"{person_id}|{name}")
    return "\n".join(lines) + ("\n" if lines else "")


def filter_missing_people(people: list[dict[str, Any]], existing_names: set[str]) -> tuple[list[dict[str, Any]], int]:
    missing: list[dict[str, Any]] = []
    skipped = 0

    for person in people:
        name = clean_name(str(person.get("name") or ""))
        if normalize_name(name) in existing_names:
            skipped += 1
            logging.debug("Skipping existing image: %s (%s)", name, person.get("id"))
            continue
        missing.append(person)

    return missing, skipped


def backup_existing(path: Path) -> Path | None:
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_name(f"{path.stem}.{stamp}.bak{path.suffix}")
    backup_path.write_bytes(path.read_bytes())
    return backup_path


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8", newline="\n")
    tmp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a TMDB popular people list for the poster orchestrator.")
    parser.add_argument("--limit", type=int, default=1000, help="Number of people to write (default: 1000).")
    parser.add_argument("--max-pages", type=int, default=None, help="Stop after this many TMDB pages even if --limit is not reached.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=f"Output list path (default: {DEFAULT_OUTPUT}).")
    parser.add_argument("--language", default="en-US", help="TMDB language parameter (default: en-US).")
    parser.add_argument(
        "--styles",
        default=",".join(DEFAULT_STYLES),
        help="Comma list of People-Images style folders to check for existing images.",
    )
    parser.add_argument(
        "--existing-root",
        action="append",
        type=Path,
        default=[],
        help="Additional folder to scan for existing images. May be used more than once.",
    )
    parser.add_argument("--no-existing-check", action="store_true", help="Write the top list without filtering existing images.")
    parser.add_argument("--require-profile", action="store_true", help="Skip people without a TMDB profile image.")
    parser.add_argument("--no-backup", action="store_true", help="Do not back up an existing output file before replacing it.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report results without writing the list.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.max_pages is not None and args.max_pages < 1:
        parser.error("--max-pages must be at least 1")

    log_file = setup_logging(args.verbose)
    load_dotenv(CONFIG_DIR / ".env")

    api_key = os.getenv("TMDB_KEY", "").strip()
    if not api_key:
        logging.error("TMDB_KEY is required. Set it in ./config/.env or the process environment.")
        return 2

    output = args.output.expanduser()
    if not output.is_absolute():
        output = (SCRIPT_DIR / output).resolve()

    logging.info("Writing up to %d popular TMDB people to %s", args.limit, output)
    people = fetch_popular_people(
        api_key=api_key,
        limit=args.limit,
        language=args.language,
        require_profile=args.require_profile,
        max_pages=args.max_pages,
    )

    missing_people = people
    skipped_existing = 0
    existing_count = 0
    if not args.no_existing_check:
        styles = parse_styles(args.styles)
        roots = default_existing_roots(styles)
        roots.extend(resolve_script_path(root) for root in args.existing_root)
        existing_names = collect_existing_names(roots)
        existing_count = len(existing_names)
        missing_people, skipped_existing = filter_missing_people(people, existing_names)

    content = render_people_list(missing_people)

    if args.dry_run:
        logging.info("Dry run: fetched %d people; no file written.", len(people))
    else:
        backup_path = None if args.no_backup else backup_existing(output)
        if backup_path:
            logging.info("Backed up existing list to %s", backup_path)
        write_text_atomic(output, content)
        logging.info("Wrote %d missing people to %s", len(missing_people), output)

    if len(people) < args.limit:
        logging.warning("Requested %d people, but only collected %d.", args.limit, len(people))

    print(f"People checked        : {len(people)}")
    print(f"Existing image names  : {existing_count if not args.no_existing_check else '(not checked)'}")
    print(f"Skipped existing      : {skipped_existing if not args.no_existing_check else '(not checked)'}")
    print(f"Missing to process    : {len(missing_people)}")
    print(f"Output                : {output if not args.dry_run else '(dry run)'}")
    print(f"Log                   : {log_file}")
    print("Next command          : python orchestrator.py --redo tmdb")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
