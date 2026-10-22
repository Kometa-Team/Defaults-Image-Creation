"""Read-only reuse of exact M2 objects with fresh source and M5 checks.

The object directory is an explicit immutable cache, not another database.
Missing bytes fail closed; this reader never opens Package E Store or renders.
"""

import gzip
from pathlib import Path
from collections import defaultdict
import os

from ...common import BulkError,confined,sha256,reject_links,relative_path
from ...config import ROOT
from ..adoption.models import HistoricalOutput,HistoricalRegistry,read_canonical
from ..adoption.sources import load_pins,verify_sources
from ..playlist.validation import M2_SHA256
from ..expanded.resolution import resolve
from ..expanded.historical import build


def objects(path):
    registry=HistoricalRegistry.from_bytes(gzip.decompress((Path(__file__).parents[1]/"adoption/baseline/frozen-registry-v1.json.gz").read_bytes()))
    if registry.sha256!=M2_SHA256:
        raise BulkError("category_adoption_pin","M2 historical registry changed")
    registry.verify_schema_pins()
    root=reject_links(Path(path)).resolve()
    names={p.name for p in root.iterdir()}
    records=[]
    for member in registry.to_dict()["members"]:
        # Names are generated only from the exact M2 registry's schema-checked
        # hashes, never arbitrary cache metadata. Index the directory once;
        # keep exact filename case, link rejection and each full byte hash.
        name=member["sha256"]+".json"
        if name not in names:
            raise BulkError("category_missing_object","Exact historical object filename is missing")
        record=HistoricalOutput.from_bytes(reject_links(root/name).read_bytes())
        if record.sha256!=member["sha256"] or record.to_dict()["identity"]["id"]!=member["id"]:
            raise BulkError("category_adoption_pin","Historical object differs from its M2 member")
        records.append(record)
    return registry,tuple(records)


def verify_inputs(records,root=ROOT):
    """One exact confined path/hash check per actual file, no pixel decoding."""
    found={}
    for record in records:
        for item in read_canonical(record.to_dict()["job_json"])["inputs"]:
            if item["path"] in found and found[item["path"]]!=item["sha256"]:
                raise BulkError("category_source_conflict","Conflicting input hashes")
            found[item["path"]]=item["sha256"]
    # Same exact-case/ledger/link checks as confined+asset_cases.exact, but
    # enumerate each immutable directory once rather than once per asset.
    # Recheck directory identity/mtime at the end to reject a stale name index.
    from ...asset_cases import LEDGER,check_authority,declarations
    root=reject_links(Path(root)).resolve()
    if root==LEDGER.parents[2].resolve():check_authority()
    names={};signatures={}
    def signature(path):
        info=reject_links(path).stat()
        return info.st_dev,info.st_ino,info.st_mtime_ns
    for path,checksum in found.items():
        relative_path(path)
        declared=declarations().get(path.casefold())
        if declared and declared!=path:
            raise BulkError("asset_case","Source spelling differs from the authoritative case ledger")
        current=root
        for part in path.split("/"):
            if current not in names:
                if not current.is_dir():raise BulkError("missing_input","Source parent is missing")
                before=signature(current);index=defaultdict(list)
                with os.scandir(current) as entries:
                    for entry in entries:index[entry.name.casefold()].append(entry.name)
                if signature(current)!=before:
                    raise BulkError("category_unstable_directory","Source directory changed during indexing")
                names[current]=index;signatures[current]=before
            if names[current].get(part.casefold())!=[part]:
                raise BulkError("asset_case","Missing, case-aliased or case-colliding physical source: "+path)
            current=current/part
        current=reject_links(current)
        if not current.is_file() or sha256(current)!=checksum:
            raise BulkError("category_source_changed","Actual source/font/background changed: "+path)
    if any(signature(path)!=old for path,old in signatures.items()):
        raise BulkError("category_unstable_directory","Source directory changed; retry from a stable snapshot")
    return found


def capture(object_root=None,*,dependency_snapshot=None,dependency_sha256=None):
    verify_sources(load_pins())
    if object_root is None:
        from ..adoption.inventory import discover
        registry,records=discover()
    else:
        registry,records=objects(object_root)
    sources=verify_inputs(records)
    resolution=resolve()
    if dependency_snapshot is None:
        if dependency_sha256 is not None:
            raise BulkError("category_graph_pin","Snapshot path and exact SHA must be supplied together")
        graph=build(registry,records,resolution)
    else:
        from ..expanded.__main__ import read_snapshot
        if dependency_sha256 is None:
            raise BulkError("category_graph_pin","An explicit dependency snapshot requires its external pin")
        graph=read_snapshot(dependency_snapshot,dependency_sha256)
    return registry,records,resolution,graph,sources
