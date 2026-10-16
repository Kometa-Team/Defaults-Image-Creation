"""Load the checked-in category data without any PowerShell/capture dependency."""

from pathlib import Path

from .common import BulkError
from .config import CATEGORIES, select_categories
from .definitions import load_definitions


CATALOG = Path(__file__).resolve().parent / "catalog"


def load_catalog(categories):
    selected = select_categories(categories)
    if not selected:
        raise BulkError("empty_selection", "Select at least one poster category")
    if "Overlays" in selected and not any(value.casefold() == "all" for value in categories):
        raise BulkError("overlay_not_implemented", "Overlay production is deferred to Package D")
    paths = [CATALOG / (category.lower() + ".yml") for category in CATEGORIES if category in selected and category != "Overlays"]
    return load_definitions(paths, profiles_path=CATALOG / "profiles.yml")
