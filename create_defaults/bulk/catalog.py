"""Load the checked-in category data without any PowerShell/capture dependency."""

from pathlib import Path
import json

from .common import BulkError, fingerprint
from .config import CATEGORIES, select_categories
from .definitions import load_definitions


CATALOG = Path(__file__).resolve().parent / "catalog"


def load_catalog(categories=(), *, posters=()):
    selected = select_categories(categories)
    identities = None
    if posters:
        index = json.loads((CATALOG / "index-v1.json").read_text(encoding="utf-8"))
        if index["sha256"] != fingerprint({k: v for k, v in index.items() if k != "sha256"}):
            raise BulkError("corrupt_catalog", "Scoped catalog index hash mismatch")
        identities, needed_categories, visited = set(), set(), set()
        def include(identity):
            if identity in visited:
                return
            item = index["posters"].get(identity)
            if item is None:
                raise BulkError("invalid_selection", "Unknown poster identity")
            visited.add(identity)
            identities.add(item["definition"])
            needed_categories.add(item["category"])
            for dep in item["dependencies"]:
                include(dep)
        for identity in posters:
            include(identity)
        if selected and any(index["posters"][p]["category"] not in selected for p in posters):
            raise BulkError("invalid_selection", "Poster outside selected category")
        selected = tuple(needed_categories)
    if not selected:
        raise BulkError("empty_selection", "Select at least one poster category")
    if "Overlays" in selected and not any(value.casefold() == "all" for value in categories):
        raise BulkError("overlay_not_implemented", "Overlay production is deferred to Package D")
    paths = [CATALOG / (category.lower() + ".yml") for category in CATEGORIES if category in selected and category != "Overlays"]
    return load_definitions(paths, profiles_path=CATALOG / "profiles.yml", identities=identities)
