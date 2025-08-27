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
load_dotenv(SCRIPT_DIR / ".env")  # also picks up process env if .env missing
TMDB_KEY = os.getenv("TMDB_KEY")
if not TMDB_KEY:
    logging.error("TMDB_KEY is required (set it in environment or .env).")
    sys.exit(1)

# people list file: defaults to <scriptdir>/config/people_list.txt (override with PEOPLE_LIST)
people_name_file = Path(os.getenv("PEOPLE_LIST") or (CONFIG_DIR / "people_list.txt"))

try:
    PERSON_DEPTH = int(os.getenv("PERSON_DEPTH", "0"))
except ValueError:
    PERSON_DEPTH = 0

TMDb = TMDbAPIs(TMDB_KEY, language="en")


# ---------- helpers ----------
def safe_filename(s: str) -> str:
    # keep it simple; strip bad path chars
    return re.sub(r'[\\/:*?"<>|]+', "_", s)


def save_image(person) -> bool:
    if not person or not getattr(person, "profile_url", None):
        return False
    try:
        r = requests.get(person.profile_url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        logging.warning("Download failed for %s (%s): %s", person.name, person.id, e)
        return False

    file_root = f"{person.name}-{person.id}"
    filepath = POSTERS_DIR / f"{safe_filename(file_root)}.jpg"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with filepath.open("wb") as f:
        f.write(r.content)
    logging.info("Saved %s", filepath)
    return True


# ---------- main ----------
def main():
    start = timer()

    if not people_name_file.is_file():
        logging.error("People list not found: %s", people_name_file)
        sys.exit(1)

    with people_name_file.open(encoding="utf-8") as fp:
        items = [line.strip() for line in fp if line.strip()]

    logging.info("Loaded %d item(s) from %s", len(items), people_name_file)
    print(f"{len(items)} item(s) retrieved...")

    with alive_bar(len(items), dual_line=True, title="TMDB people") as bar:
        for item in items:
            bar.text = f"->   starting: {item}"

            # try by TMDB numeric id first
            try:
                person = TMDb.person(int(item))
                bar.text = f"-> retrieving (id): {item}"
                save_image(person)
                bar()
                continue
            except ValueError:
                pass  # not an int, fall through to search
            except Exception as ex:
                logging.warning("Lookup by id failed for %s: %s", item, ex)

            # search by name
            try:
                results = TMDb.people_search(str(item)) or []
                if not results:
                    bar.text = f"->  NOT FOUND: {item}"
                    logging.info("Not found: %s", item)
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
                        bar.text = f"-> retrieving: {i + 1}-{item}"
                        if save_image(person):
                            pulled += 1
                    except Exception as ex:
                        logging.warning("Exception on %s[%d]: %s", item, i, ex)

                if upper == 0:
                    # If you prefer to always get at least the best match:
                    # save_image(results[0])
                    pass

            except Exception as ex:
                logging.warning("Search failed for %s: %s", item, ex)

            bar()

    elapsed = timer() - start
    logging.info("Done in %.2fs", elapsed)
    print(f"Done in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
