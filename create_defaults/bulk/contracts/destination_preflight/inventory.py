"""Offline Git object verification and complete reachable tree closure; no GETs."""

import hashlib

from .paths import fail, safe_path


def git_object(kind, raw):
    return hashlib.sha1(kind.encode("ascii")+b" "+str(len(raw)).encode("ascii")+b"\0"+raw).hexdigest()


def tree_sha(entries):
    entries = sorted(entries, key=lambda e: (e["name"]+("/" if e["mode"] == "040000" else "")).encode("utf8"))
    raw = b"".join(e["mode"].lstrip("0").encode("ascii")+b" "+e["name"].encode("utf8")+b"\0"+bytes.fromhex(e["sha"]) for e in entries)
    return git_object("tree", raw)


def validate(value):
    raw = bytes.fromhex(value["commit_hex"])
    if git_object("commit", raw) != value["commit"] or not raw.startswith(b"tree "+value["tree"].encode("ascii")+b"\n"):
        fail("inventory_commit")
    seen = set()
    for page in value["pages"]:
        if page["sha"] in seen:
            fail("duplicate_tree")
        seen.add(page["sha"])
        names = [e["name"] for e in page["entries"]]
        if len(names) != len(set(names)):
            fail("duplicate_tree_entry")
        for name in names:
            safe_path(name)
            if "/" in name:
                fail("tree_component")
        if tree_sha(page["entries"]) != page["sha"]:
            fail("inventory_tree_hash")


def expand(value, *, cancel=None):
    pages = {p["sha"]: p["entries"] for p in value["pages"]}
    pending = [("", value["tree"], 0)]
    visited, entries, missing = set(), {}, set()
    while pending:
        prefix, checksum, depth = pending.pop()
        if cancel is not None and cancel():
            fail("interrupted")
        if depth > 40 or len(entries) > 100000:
            fail("inventory_bound")
        if checksum not in pages:
            missing.add(checksum)
            continue
        visited.add(checksum)
        for entry in pages[checksum]:
            path = safe_path(prefix+entry["name"])
            if path in entries:
                fail("inventory_duplicate_path")
            entries[path] = {"mode": entry["mode"], "sha": entry["sha"]}
            if entry["mode"] == "040000":
                pending.append((path+"/", entry["sha"], depth+1))
    if set(pages)-visited:
        fail("inventory_unreachable_tree")
    if len(entries) > 100000:
        fail("inventory_bound")
    return dict(sorted(entries.items())), sorted(missing)
