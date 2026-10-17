"""Authoritative GitHub tree metadata with a transactional SQLite cache."""

import base64
import hashlib
import os
import sqlite3
import time
import unicodedata
from pathlib import Path, PurePosixPath

from github_inventory_core import blob_sha, complete_tree

from people_github import GitHubClient, GitHubError, REPOSITORIES, branch_name, repository_mapping, sandbox_storage


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def path_key(path):
    if (not path or "\\" in path or any(ord(char) < 32 or ord(char) == 127 for char in path) or path.startswith("/")
            or any(p in {"", ".", ".."} or ":" in p for p in path.split("/"))):
        raise ValueError("Unsafe repository path")
    return unicodedata.normalize("NFC", path).casefold()


def name_key(name):
    return " ".join(unicodedata.normalize("NFC", name).casefold().split())


def default_state_dir():
    storage = sandbox_storage()
    if storage:
        return storage["PEOPLE_STATE_DIR"]
    return Path(os.getenv("PEOPLE_STATE_DIR") or Path(__file__).resolve().parent / "config" / "state")


class RemoteInventory:
    def __init__(self, client, database=None, branch=None):
        self.client = client
        self.repositories = repository_mapping()
        self.branch = branch_name(branch)
        database = Path(database) if database is not None else default_state_dir() / "people_inventory.db"
        from people_workspaces import reject_links
        reject_links(database)
        database.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(database, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS snapshots (
              repo TEXT, branch TEXT, head TEXT, tree TEXT, updated REAL,
              PRIMARY KEY(repo, branch));
            CREATE TABLE IF NOT EXISTS entries (
              repo TEXT, branch TEXT, path TEXT, key TEXT, sha TEXT, size INTEGER, mode TEXT, type TEXT,
              PRIMARY KEY(repo, branch, path));
            CREATE INDEX IF NOT EXISTS inventory_keys ON entries(repo, branch, key);
        """)

    def close(self):
        self.db.close()

    def tree_entries(self, repo, sha, prefix=""):
        def get_tree(tree, recursive):
            suffix = "?recursive=1" if recursive else ""
            return self.client.request("GET", f"/repos/{repo}/git/trees/{tree}{suffix}")
        return [dict(item, path=prefix + item["path"]) for item in complete_tree(get_tree, sha)]

    def refresh(self, style, force=False):
        repo = self.repositories[style]
        head, tree = self.client.head(repo, self.branch)
        old = self.db.execute("SELECT * FROM snapshots WHERE repo=? AND branch=?", (repo, self.branch)).fetchone()
        if force or old is None or old["tree"] != tree:
            print(f"[INFO] Refreshing {repo}@{self.branch} tree metadata", flush=True)
            root = self.client.request("GET", f"/repos/{repo}/git/trees/{tree}")
            if root.get("truncated"):
                raise GitHubError("Root tree truncated; inventory is incomplete")
            previous = [dict(row) for row in self.db.execute("SELECT * FROM entries WHERE repo=? AND branch=?", (repo, self.branch))]
            prior_trees = {row["path"]: row["sha"] for row in previous if row["type"] == "tree"}
            entries = list(root["tree"])
            # Partition by root folder instead of requesting a giant recursive library tree.
            for entry in root["tree"]:
                if entry["type"] != "tree":
                    continue
                prefix = entry["path"] + "/"
                if not force and prior_trees.get(entry["path"]) == entry["sha"]:
                    entries.extend(row for row in previous if row["path"].startswith(prefix))
                else:
                    entries.extend(self.tree_entries(repo, entry["sha"], prefix))
            rows = [(repo, self.branch, e["path"], path_key(e["path"]), e["sha"],
                     e.get("size", 0), e["mode"], e["type"]) for e in entries]
            with self.db:
                self.db.execute("DELETE FROM entries WHERE repo=? AND branch=?", (repo, self.branch))
                self.db.executemany("INSERT INTO entries VALUES (?,?,?,?,?,?,?,?)", rows)
                self.db.execute("INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?)", (repo, self.branch, head, tree, time.time()))
        else:
            with self.db:
                self.db.execute("UPDATE snapshots SET head=?,updated=? WHERE repo=? AND branch=?", (head, time.time(), repo, self.branch))
        return head, tree

    def refresh_all(self, force=False):
        return {style: self.refresh(style, force) for style in self.repositories}

    def lookup(self, style, path):
        rows = self.db.execute("SELECT * FROM entries WHERE repo=? AND branch=? AND key=?",
                               (self.repositories[style], self.branch, path_key(path))).fetchall()
        if len(rows) > 1:
            raise GitHubError(f"Ambiguous Unicode/case destination in {style}: {path}")
        return dict(rows[0]) if rows else None

    def images(self, style):
        rows = self.db.execute("SELECT * FROM entries WHERE repo=? AND branch=? AND type='blob' ORDER BY path",
                               (self.repositories[style], self.branch))
        return [dict(row) for row in rows if PurePosixPath(row["path"]).suffix.lower() in IMAGE_SUFFIXES
                and "/images/" in row["path"].lower()]

    def complete_names(self):
        sets = [self.valid_names(style) for style in self.repositories]
        return set.intersection(*sets)

    def valid_names(self, style):
        counts = {}
        suffix = ".png" if style == "transparent" else ".jpg"
        for row in self.images(style):
            path = PurePosixPath(row["path"])
            if row["mode"] == "100644" and path.suffix.lower() == suffix:
                key = name_key(path.stem)
                counts[key] = counts.get(key, 0) + 1
        return {key for key, count in counts.items() if count == 1}

    def missing_styles(self, name):
        key = name_key(name)
        return [style for style in self.repositories if key not in self.valid_names(style)]

    def fetch_image(self, style, path, destination):
        entry = self.lookup(style, path)
        if not entry or entry["mode"] != "100644" or entry["type"] != "blob":
            raise GitHubError("Remote image missing or is not an ordinary file")
        result = self.client.request("GET", f"/repos/{self.repositories[style]}/git/blobs/{entry['sha']}")
        if result.get("encoding") != "base64":
            raise GitHubError("Unsupported GitHub blob encoding")
        data = base64.b64decode(result["content"])
        if blob_sha(data) != entry["sha"]:
            raise GitHubError("Downloaded image hash mismatch")
        destination = Path(destination)
        from people_workspaces import reject_links
        reject_links(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".tmp")
        reject_links(temporary)
        temporary.write_bytes(data)
        temporary.replace(destination)
        return destination


def online_complete_names():
    inventory = RemoteInventory(GitHubClient())
    try:
        inventory.refresh_all()
        return inventory.complete_names()
    finally:
        inventory.close()


def main():
    import argparse
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / "config" / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--names", nargs="+", help="Fetch only these people for recovery/auditing")
    parser.add_argument("--output", type=Path, help="Explicit temporary image tree for selected names")
    args = parser.parse_args()
    if args.names and args.output is None:
        parser.error("--names requires --output")
    inventory = RemoteInventory(GitHubClient())
    try:
        inventory.refresh_all(force=args.refresh)
        wanted = {name_key(name) for name in args.names or []}
        for style in inventory.repositories:
            entries = inventory.images(style)
            print(f"{style}: {len(entries)} images")
            for entry in entries:
                if name_key(PurePosixPath(entry["path"]).stem) in wanted:
                    path_key(entry["path"])
                    inventory.fetch_image(style, entry["path"], args.output / style / entry["path"])
    finally:
        inventory.close()


if __name__ == "__main__":
    main()
