
# A single canonical diagnostic registry is shared by CLI and imported callers.
import sys as _security_sys
from pathlib import Path as _SecurityPath
_security_root = _SecurityPath(__file__).resolve().parents[1]
if (_security_root / "create_people_posters").is_dir() and str(_security_root) not in _security_sys.path:
    _security_sys.path.insert(0, str(_security_root))
from create_people_posters.people_diagnostics import (protect_cli, safe_exception, sanitize_text,
                                                     sanitize_data, secure_handler, register_environment)
from create_people_posters.people_process import guard_cli
if __name__ == "__main__":
    guard_cli()

import os
import re
import sys
import logging
import hashlib
import io
import json
import uuid
import tempfile
from pathlib import Path
from timeit import default_timer as timer

import requests
from dotenv import load_dotenv
from alive_progress import alive_bar
from tmdbapis import TMDbAPIs
from PIL import Image
from create_people_posters.people_failures import failure_boundary, failure_record, failure_text, preserve_summary
from people_workspaces import atomic_json

# ---------- paths + logging ----------
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
CONFIG_DIR = Path(os.getenv("PEOPLE_CONFIG_DIR") or SCRIPT_DIR / "config")
LOGS_DIR = CONFIG_DIR / "logs"
POSTERS_DIR = Path(os.getenv("POSTER_DIR") or (CONFIG_DIR / "posters"))
for d in (CONFIG_DIR, LOGS_DIR, POSTERS_DIR):
    d.mkdir(parents=True, exist_ok=True)


def setup_logging(level=logging.INFO, console=True):
    log_file = LOGS_DIR / f"{SCRIPT_PATH.stem}.log"
    handlers = [secure_handler(logging.FileHandler(log_file, encoding="utf-8", mode="a"))]
    if console:
        handlers.append(secure_handler(logging.StreamHandler(sys.stdout)))
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.info("Logging → %s", log_file)
    return log_file


setup_logging()

# ---------- env + config ----------
load_dotenv(CONFIG_DIR / ".env")
register_environment()
TMDB_KEY = os.getenv("TMDB_KEY")
if not TMDB_KEY and not os.getenv("TMDB_READ_ACCESS_TOKEN"):
    logging.error("TMDB_KEY is required (set it in environment or .env).")
    sys.exit(1)

# people list file: defaults to <scriptdir>/config/people_list.txt (override with PEOPLE_LIST)
people_name_file = Path(os.getenv("PEOPLE_LIST") or (CONFIG_DIR / "people_list.txt"))
people_override_file = Path(os.getenv("PEOPLE_OVERRIDE_LIST") or (CONFIG_DIR / "people_overrides.txt"))

try:
    PERSON_DEPTH = int(os.getenv("PERSON_DEPTH", "0"))
except ValueError:
    PERSON_DEPTH = 0

from create_people_posters.people_http import SecureTMDBSession
TMDb = TMDbAPIs(TMDB_KEY or "", language="en", session=SecureTMDBSession(TMDB_KEY or ""))


# ---------- helpers ----------
def safe_filename(s: str) -> str:
    # keep it simple; strip bad path chars
    return re.sub(r'[\\/:*?"<>|]+', "_", s)


def iter_people_items(path: Path) -> list[str]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as fp:
        return [line.strip() for line in fp if line.strip() and not line.lstrip().startswith("#")]


def parse_people_item(item: str) -> tuple[str, str | None]:
    parts = [part.strip() for part in item.split("|") if part.strip()]

    if len(parts) == 1:
        return parts[0], None
    if len(parts) == 2:
        if parts[0].isdigit():
            return parts[0], parts[1]
        if parts[1].isdigit():
            return parts[1], None
        return parts[0], parts[1]
    if len(parts) >= 3 and parts[1].isdigit():
        return parts[1], parts[2]

    raise ValueError(
        f"Unsupported people entry format: {item!r}. "
        "Use NAME, TMDB_ID|ALIAS, or NAME|TMDB_ID|ALIAS."
    )


def write_preserved(path, content):
    """Exclusive writes: existing downloaded bytes are never replaced."""
    from people_workspaces import reject_links
    reject_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise FileExistsError("Existing downloaded input differs; operator review required")
        return
    fd, name = tempfile.mkstemp(prefix=".tmdb-", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            # Atomic creation without replacement, including concurrent retries.
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != content:
                raise FileExistsError("Existing downloaded input differs; operator review required") from None
    finally:
        temporary.unlink(missing_ok=True)


def retained_input(lookup, label):
    """Reuse identity-bound sources even after truncate/audit/prep moved them."""
    from people_remote_inventory import name_key
    receipt = CONFIG_DIR / "tmdb_identities.json"
    identities = json.loads(receipt.read_text(encoding="utf8")) if receipt.exists() else {}
    for name, person_id in identities.items():
        if (lookup.isdigit() and str(person_id) != lookup) or (label and name_key(name) != name_key(safe_filename(label))):
            continue
        if not lookup.isdigit() and name_key(name) != name_key(safe_filename(label or lookup)):
            continue
        filename = safe_filename(name) + ".jpg"
        candidates = [CONFIG_DIR / "input/tmdb" / f"{safe_filename(name)}-{person_id}.jpg",
                      POSTERS_DIR / f"{safe_filename(name)}-{person_id}.jpg", POSTERS_DIR / filename,
                      CONFIG_DIR / "people_dirs/original" / filename,
                      CONFIG_DIR / "people_dirs/original" / name[:1].upper() / "Images" / filename,
                      CONFIG_DIR / "people_dirs/Downloads" / filename]
        for path in candidates:
            if path.is_file():
                with failure_boundary("image_decode", lookup):
                    with Image.open(path) as image:
                        image.load()
                return path
    return None


def save_image(person, file_label: str | None = None) -> str:
    if not person or not getattr(person, "profile_url", None):
        return "missing_profile"
    base_name = file_label or person.name
    if retained_input(str(person.id), base_name):
        return "reused"
    if os.getenv("PEOPLE_PUBLISH_MODE", "local_git") == "github_api":
        from people_remote_inventory import name_key, online_complete_names
        if not hasattr(save_image, "complete_names"):
            save_image.complete_names = online_complete_names()
        if name_key(safe_filename(base_name)) in save_image.complete_names:
            logging.info("All seven styles already exist: %s", base_name)
            return "already_complete"
    with failure_boundary("download_image", str(person.id)):
        from create_people_posters.people_http import image_response
        with requests.Session() as session:
            r = image_response(session, person.profile_url)
            try:
                content = r.content
            finally:
                r.close()

    file_root = f"{base_name}-{person.id}"
    filepath = POSTERS_DIR / f"{safe_filename(file_root)}.jpg"
    with failure_boundary("image_decode", str(person.id)):
        with Image.open(io.BytesIO(content)) as image:
            image.load()
    with failure_boundary("input_write", str(person.id)):
        write_preserved(CONFIG_DIR / "input/tmdb" / filepath.name, content)
        write_preserved(filepath, content)
    if (os.getenv("PEOPLE_PUBLISH_MODE", "local_git") == "github_api"
            or os.getenv("PEOPLE_WORKSPACE_MODE", "persistent") == "batch"):
        from people_remote_inventory import name_key
        receipt = CONFIG_DIR / "tmdb_identities.json"
        identities = json.loads(receipt.read_text(encoding="utf-8")) if receipt.exists() else {}
        identity_name = safe_filename(base_name)
        previous = next((value for name, value in identities.items() if name_key(name) == name_key(identity_name)), None)
        if previous is not None and str(previous) != str(person.id):
            atomic_json(CONFIG_DIR / "tmdb_conflicts.json", {"name": base_name, "ids": [previous, str(person.id)]})
            raise SystemExit(f"Multiple TMDb people map to the same output name: {base_name}; assign distinct aliases")
        identities[identity_name] = str(person.id)
        atomic_json(receipt, identities)
    logging.info("Saved %s", filepath)
    return "downloaded"


def process_item(item):
    lookup, label = parse_people_item(item)
    retained = retained_input(lookup, label) if lookup.isdigit() else None
    if retained:
        return [{"status": "reused", "source": str(retained),
                 "person_id": str(int(lookup)),
                 "source_sha256": hashlib.sha256(retained.read_bytes()).hexdigest()}]
    # Parse the identifier independently: an SDK ValueError must never turn an
    # explicit numeric ID into a name search or a permanent miss.
    if lookup.isdigit():
        with failure_boundary("person_details", lookup):
            # No credits, tagged images, genres or translations are needed to
            # retrieve the established primary profile_url.
            results = [TMDb.person(int(lookup), partial=None)]
        upper = 1
    else:
        with failure_boundary("search_person", lookup):
            results = TMDb.people_search(lookup) or []
            # Preserve PERSON_DEPTH=0 behavior (select no name-search results).
            upper = min(max(PERSON_DEPTH, 0), len(results))
        if not results:
            return [{"status": "missing_person", "retryable": True}]
        if not upper:
            return [{"status": "not_selected", "reason": "PERSON_DEPTH=0"}]
    records = []
    for index in range(upper):
        identifier = lookup + "[" + str(index) + "]"
        try:
            with failure_boundary("search_result", identifier):
                person = results[index]
                identifier = str(person.id)
            records.append({"status": save_image(person, file_label=label), "person_id": str(person.id)})
        except Exception as error:
            records.append({"status": "failed", "failure": failure_record(error, "download_image", identifier)})
    return records


def run_people(items):
    items = list(items)
    preserve_summary(LOGS_DIR / "tmdb_people.json")
    summary = {"files": [], "failed": 0, "downloaded": 0, "reused": 0, "exit_code": 0,
               "selected_inputs": list(items), "complete": False}
    for item in items:
        try:
            records = process_item(item)
        except Exception as error:
            records = [{"status": "failed", "failure": failure_record(error, "person_lookup", item)}]
        for record in records:
            record["input_identifier"] = item
            if record["status"] in {"missing_person", "missing_profile"}:
                record["failure"] = {"category": record["status"], "exception_type": None,
                                     "operation": "person_details" if lookup_is_id(item) else "search_person",
                                     "input_identifier": item, "cause_chain": [], "locations": [],
                                     "retryable": True, "permanent_person_failure": False,
                                     "correlation_id": uuid.uuid4().hex,
                                     "action": "Verify TMDB person/profile availability; retain the selected input for retry."}
            if record["status"] in {"failed", "missing_person", "missing_profile"}:
                summary["failed"] += 1
                logging.warning("Unresolved input %s: %s", item,
                                failure_text(record["failure"]) if "failure" in record else record["status"])
            elif record["status"] in summary:
                summary[record["status"]] += 1
            summary["files"].append(record)
        summary["exit_code"] = 1 if summary["failed"] else 0
        summary["outcome"] = "partial_failure" if summary["failed"] else "success"
        # Persist after every person; retries retain successful per-person work.
        atomic_json(LOGS_DIR / "tmdb_people.json", summary)
    summary["complete"] = not summary["failed"]
    atomic_json(LOGS_DIR / "tmdb_people.json", summary)
    return summary


def lookup_is_id(item):
    return parse_people_item(item)[0].isdigit()


# ---------- main ----------
def main():
    start = timer()

    auto_items = iter_people_items(people_name_file)
    manual_items = iter_people_items(people_override_file)

    if not auto_items and not manual_items:
        logging.error("No people items found in %s or %s", people_name_file, people_override_file)
        sys.exit(1)

    items: list[str] = []
    seen: set[str] = set()
    for source_items in (auto_items, manual_items):
        for item in source_items:
            if item not in seen:
                items.append(item)
                seen.add(item)

    if auto_items:
        logging.info("Loaded %d item(s) from %s", len(auto_items), people_name_file)
    if manual_items:
        logging.info("Loaded %d manual override item(s) from %s", len(manual_items), people_override_file)
    print(f"{len(items)} item(s) retrieved...")

    summary = run_people(items)

    elapsed = timer() - start
    logging.info("Done in %.2fs", elapsed)
    print(f"Done in {elapsed:.2f}s")
    return summary["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
