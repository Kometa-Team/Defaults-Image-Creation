"""Development export of metadata-only scoped lookups; never hashes source artwork."""

from .catalog import CATALOG, load_catalog
from .common import atomic_bytes, canonical, fingerprint
from .generators import GENERATORS
from .planner import Planner
import json


def historical_records():
    from .migration import legacy, legacy_destination, stable_id
    return {stable_id(job["category"], legacy_destination(job)):
            {"historical_background": job["parameters"]["base_color"], "source_row": fingerprint(job["source_row"])}
            for job in legacy()["jobs"] if not (job["category"] == "Genre" and job["source"]["definition_line"] == 4883)}


def export_index():
    definitions = load_catalog(["All"])
    catalog, families, _ = Planner(generators=GENERATORS).expand(definitions)
    historical = historical_records()
    parents = {child: parent for parent, children in families.items() for child in children}
    records = {identity: {"definition": parents.get(identity, identity), "category": item.category,
                          "dependencies": [d["poster_id"] for d in item.data["dependencies"]],
                          **historical.get(identity, {})} for identity, item in catalog.items()}
    for item in definitions:
        if item.id not in records:
            records[item.id] = {"definition": item.id, "category": item.category, "dependencies": []}
    value = {"schema_version": 1, "posters": records}
    value["sha256"] = fingerprint(value)
    atomic_bytes(CATALOG / "index-v1.json", canonical(value) + b"\n", replace=True)
    return {"indexed": len(records)}


def refresh_historical_metadata():
    value = json.loads((CATALOG / "index-v1.json").read_text())
    historical = historical_records()
    for identity, record in value["posters"].items():
        record.pop("historical_background", None)
        record.pop("source_row", None)
        record.update(historical.get(identity, {}))
    value.pop("sha256")
    value["sha256"] = fingerprint(value)
    atomic_bytes(CATALOG / "index-v1.json", canonical(value) + b"\n", replace=True)
    return {"indexed": len(value["posters"]), "historical": len(historical)}


if __name__ == "__main__":
    import sys
    print(refresh_historical_metadata() if sys.argv[1:] == ["--refresh-historical"] else export_index())
