import os
import re
import sys
import logging
from pathlib import Path
from timeit import default_timer as timer

import requests
from dotenv import load_dotenv
from alive_progress import alive_bar
from tmdbapis import TMDbAPIs

# ---------- paths + logging ----------
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
POSTERS_DIR = Path(os.getenv("POSTER_DIR") or (CONFIG_DIR / "posters"))
for d in (CONFIG_DIR, LOGS_DIR, POSTERS_DIR):
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

# ---------- env + config ----------
load_dotenv(CONFIG_DIR / ".env")
TMDB_KEY = os.getenv("TMDB_KEY")
if not TMDB_KEY:
    logging.error("TMDB_KEY is required (set it in environment or .env).")
    sys.exit(1)

# people list file: defaults to <scriptdir>/config/people_list.txt (override with PEOPLE_LIST)
people_name_file = Path(os.getenv("PEOPLE_LIST") or (CONFIG_DIR / "people_list.txt"))
people_override_file = Path(os.getenv("PEOPLE_OVERRIDE_LIST") or (CONFIG_DIR / "people_overrides.txt"))

try:
    PERSON_DEPTH = int(os.getenv("PERSON_DEPTH", "0"))
except ValueError:
    PERSON_DEPTH = 0

TMDb = TMDbAPIs(TMDB_KEY, language="en")


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


def save_image(person, file_label: str | None = None) -> bool:
    if not person or not getattr(person, "profile_url", None):
        return False
    try:
        r = requests.get(person.profile_url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        logging.warning("Download failed for %s (%s): %s", person.name, person.id, e)
        return False

    base_name = file_label or person.name
    file_root = f"{base_name}-{person.id}"
    filepath = POSTERS_DIR / f"{safe_filename(file_root)}.jpg"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with filepath.open("wb") as f:
        f.write(r.content)
    logging.info("Saved %s", filepath)
    return True


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

    with alive_bar(len(items), dual_line=True, title="TMDB people") as bar:
        for item in items:
            bar.text = f"->   starting: {item}"
            try:
                lookup_value, file_label = parse_people_item(item)
            except ValueError as ex:
                logging.warning(str(ex))
                bar()
                continue

            # try by TMDB numeric id first
            try:
                person = TMDb.person(int(lookup_value))
                bar.text = f"-> retrieving (id): {lookup_value}"
                save_image(person, file_label=file_label)
                bar()
                continue
            except ValueError:
                pass  # not an int, fall through to search
            except Exception as ex:
                logging.warning("Lookup by id failed for %s: %s", lookup_value, ex)

            # search by name
            try:
                results = TMDb.people_search(str(lookup_value)) or []
                if not results:
                    bar.text = f"->  NOT FOUND: {lookup_value}"
                    logging.info("Not found: %s", lookup_value)
                    bar()
                    continue

                # number of results to fetch (0 means none, matches your original logic)
                upper = min(max(PERSON_DEPTH, 0), len(results))
                if upper == 0:
                    # fetch just the top match if PERSON_DEPTH == 0? comment next line
                    # upper = 1
                    pass

                pulled = 0
                for i in range(upper):
                    try:
                        person = results[i]
                        bar.text = f"-> retrieving: {i + 1}-{lookup_value}"
                        if save_image(person, file_label=file_label):
                            pulled += 1
                    except Exception as ex:
                        logging.warning("Exception on %s[%d]: %s", lookup_value, i, ex)

                if upper == 0:
                    # If you prefer to always get at least the best match:
                    # save_image(results[0])
                    pass

            except Exception as ex:
                logging.warning("Search failed for %s: %s", lookup_value, ex)

            bar()

    elapsed = timer() - start
    logging.info("Done in %.2fs", elapsed)
    print(f"Done in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
