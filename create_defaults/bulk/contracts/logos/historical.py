"""Exact accepted M2 asset uses bypass NEW intake diagnostics, never replacements."""

from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path

from ...common import BulkError, confined, fingerprint, sha256
from ..adoption.sources import load_pins
from ..playlist.validation import M2_SHA256

MAPPING_SHA256 = "6d1a49062208e8361227942549a4adafb0f2fed63c2f3a9a63c7860845ab876f"


@lru_cache(maxsize=1)
def accepted_uses():
    base = Path(__file__).parents[1] / "adoption/baseline"
    with gzip.open(base / "stable-mapping-v1.json.gz", "rb") as stream: raw = stream.read(16*1024*1024+1)
    if hashlib.sha256(raw).hexdigest() != MAPPING_SHA256:
        raise BulkError("logo_historical_pin", "Frozen complete M2 identity mapping differs")
    with gzip.open(base / "frozen-registry-v1.json.gz", "rb") as stream: registry_raw = stream.read(8*1024*1024+1)
    registry = json.loads(registry_raw)
    if fingerprint(registry) != M2_SHA256:
        raise BulkError("logo_historical_pin", "Frozen M2 membership differs")
    members = {m["id"]:m["sha256"] for m in registry["members"]}
    names = set(load_pins()["normal_historical_alpha_assets"])
    uses = []
    for row in json.loads(raw):
        identity = row["identity"]
        if identity["source"]["path"] in names:
            if members.get(identity["id"]) != row["record_sha256"]:
                raise BulkError("logo_historical_pin", "Historical source association is not in the adopted M2 set")
            uses.append((identity["id"], identity["source"]["path"], identity["source"]["sha256"]))
    if {p for _,p,_ in uses} != names:
        raise BulkError("logo_historical_pin", "Accepted historical source membership differs")
    return tuple(uses)


def preserve_existing(*, item_id, source, source_root):
    """Explicit historical-use path, not a caller-supplied 'grandfathered' flag."""
    if (item_id, source["path"], source["sha256"]) not in accepted_uses():
        raise BulkError("logo_not_historical", "Changed bytes or new use must follow current new-source intake")
    if sha256(confined(Path(source_root), source["path"], must_exist=True)) != source["sha256"]:
        raise BulkError("logo_historical_changed", "Replacement bytes are a new submission")
    return {"item_id":item_id,"source":source,"status":"normal_accepted_historical_artwork","diagnostics":[],
            "cleanup_required":False,"regeneration_required":False,"new_approval_required":False}
