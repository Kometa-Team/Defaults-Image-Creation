"""Exact spelling is retained. Comparison keys reject aliases, never rename."""

import re
from bisect import bisect_left

from ...common import BulkError, path_key, relative_path


def fail(code):
    raise BulkError("p3m3_"+code, "Destination preflight failed: "+code)


def safe_path(value):
    relative_path(value)
    if (any(p.casefold() == ".git" for p in value.split("/"))
            or re.search(r"%[0-9a-fA-F]{2}", value)
            or any(0xD800 <= ord(c) <= 0xDFFF for c in value)):
        fail("unsafe_path")
    return value


def target_path(root, path):
    safe_path(path)
    if root is not None:
        safe_path(root)
    return safe_path(root+"/"+path if root else path)


def overlaps(a, b):
    # null is an explicitly selected repository root, never an invented prefix.
    a, b = (path_key(v) if v is not None else "" for v in (a, b))
    return not a or not b or a == b or a.startswith(b+"/") or b.startswith(a+"/")


def repository_key(repo):
    return repo["host"], repo["repository_id"], repo["owner_id"]


class CollisionIndex:
    def __init__(self, inventory):
        self.buckets = {}
        for path, entry in inventory.items():
            self.buckets.setdefault(path_key(path), []).append((path, entry))
        self.keys = sorted(self.buckets)

    def diagnostics(self, path):
        key, result = path_key(path), []
        for actual, _ in self.buckets.get(key, []):
            result.append("existing_exact" if path == actual else "existing_alias")
        parts = path.split("/")
        for length in range(1, len(parts)):
            prefix = "/".join(parts[:length])
            for actual, entry in self.buckets.get(path_key(prefix), []):
                if entry["mode"] != "040000":
                    result.append("symlink_ancestor" if entry["mode"] == "120000" else "existing_file_ancestor")
                elif actual != prefix:
                    result.append("existing_ancestor_alias")
        start = bisect_left(self.keys, key+"/")
        if start < len(self.keys) and self.keys[start].startswith(key+"/"):
            result.append("existing_directory")
        return sorted(set(result))
