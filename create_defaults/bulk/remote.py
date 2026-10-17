"""Clone-free, GET-only inventory with immutable commit/tree identities."""

import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import quote
import warnings

from PIL import Image
import requests

from create_people_posters.github_inventory_core import GitHubError, blob_sha, complete_tree, get_json
from .common import BulkError, Conflict, atomic_bytes, canonical, confined, fingerprint, path_key, relative_path, sha256
from .config import Config, branch_name, repository


def git_sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise GitHubError("Invalid Git object identity")
    return value


class ReadOnlyGitHub:
    def __init__(self, repo="Kometa-Team/Default-Images", *, token=None, session=None, sleep=time.sleep, max_bytes=30_000_000):
        self.repo = repository(repo)
        self._session = session or requests.Session()
        # Do not inherit ambient requests auth, netrc or proxy credentials.
        self._session.trust_env = False
        self._session.headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
        self._session.headers.pop("Authorization", None)
        if token:
            self._session.headers["Authorization"] = "Bearer " + token
        self.sleep, self.max_bytes = sleep, max_bytes

    def _get(self, endpoint):
        return get_json(self._session, f"https://api.github.com/repos/{self.repo}/{endpoint}", sleep=self.sleep, max_bytes=self.max_bytes)

    def head(self, branch="master"):
        ref = self._get("git/ref/heads/" + quote(branch_name(branch), safe="/"))
        head = git_sha(ref["object"]["sha"])
        commit = self._get("git/commits/" + head)
        if git_sha(commit["sha"]) != head:
            raise GitHubError("Commit identity mismatch")
        return head, git_sha(commit["tree"]["sha"])

    def tree(self, sha, recursive=False):
        result = self._get("git/trees/" + git_sha(sha) + ("?recursive=1" if recursive else ""))
        if result.get("sha") != sha or type(result.get("truncated")) is not bool or not isinstance(result.get("tree"), list):
            raise GitHubError("Incomplete Git tree response")
        return result

    def blob(self, sha):
        return self._get("git/blobs/" + git_sha(sha))


class RemoteInventory:
    def __init__(self, store, config=None, client=None, *, clock=time.time):
        self.store, self.config, self.clock = store, config or Config(), clock
        self.client = client
        if client is not None and getattr(client, "repo", self.config.github_repository) != self.config.github_repository:
            raise BulkError("invalid_repository", "Client repository differs from configuration")

    def snapshot(self):
        with self.store.connection() as db:
            row = db.execute("SELECT * FROM remote_snapshots WHERE repo=? AND branch=?", (self.config.github_repository, self.config.github_branch)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["freshness"] = "fresh" if not self.config.offline and not row["failure"] and self.clock() - row["checked"] <= self.config.remote_ttl else "stale"
        return result

    def refresh(self):
        if self.config.offline:
            return {"status": "offline", "snapshot": self.snapshot()}
        if self.client is None:
            raise BulkError("missing_client", "Explicit read-only GitHub client required for refresh")
        old = self.snapshot()
        repo, branch = self.config.github_repository, self.config.github_branch
        try:
            head, tree = self.client.head(branch)
            git_sha(head), git_sha(tree)
            entries = None
            if old is None or old["tree"] != tree:
                root = self.client.tree(tree, False)
                if root.get("truncated") is not False or not isinstance(root.get("tree"), list):
                    raise GitHubError("Root tree incomplete")
                entries = list(root["tree"])
                previous = []
                if old:
                    with self.store.connection() as db:
                        previous = [dict(row) for row in db.execute("SELECT * FROM remote_entries WHERE repo=? AND tree=?", (repo, old["tree"]))]
                prior = {item["path"]: item["sha"] for item in previous if item["type"] == "tree"}
                for item in root["tree"]:
                    if item["type"] != "tree":
                        continue
                    prefix = item["path"] + "/"
                    if prior.get(item["path"]) == item["sha"]:
                        entries.extend(entry for entry in previous if entry["path"].startswith(prefix))
                    else:
                        entries.extend(dict(entry, path=prefix + entry["path"]) for entry in complete_tree(self.client.tree, item["sha"]))
                seen = set()
                if len(entries) > 1_000_000:
                    raise GitHubError("Inventory entry limit exceeded; inventory unknown")
                for entry in entries:
                    relative_path(entry["path"])
                    git_sha(entry["sha"])
                    if entry["path"] in seen or entry["type"] not in {"blob", "tree", "commit"} or entry.get("mode") not in {"100644", "100755", "120000", "040000", "160000"} or (entry.get("size") is not None and (type(entry["size"]) is not int or entry["size"] < 0)):
                        raise GitHubError("Duplicate or invalid tree entry")
                    seen.add(entry["path"])
            with self.store.transaction() as db:
                current = db.execute("SELECT version FROM remote_snapshots WHERE repo=? AND branch=?", (repo, branch)).fetchone()
                if (current["version"] if current else None) != (old["version"] if old else None):
                    raise Conflict("Another inventory refresh completed; retry")
                if entries is not None:
                    db.execute("DELETE FROM remote_entries WHERE repo=? AND tree=?", (repo, tree))
                    db.executemany("INSERT INTO remote_entries VALUES (?,?,?,?,?,?,?,?)", [
                        (repo, tree, e["path"], path_key(e["path"]), e["sha"], e.get("size"), e["mode"], e["type"]) for e in entries])
                db.execute("INSERT OR REPLACE INTO remote_snapshots VALUES (?,?,?,?,?,?,NULL)", (repo, branch, (old["version"] + 1) if old else 0, head, tree, self.clock()))
                db.execute("DELETE FROM remote_failures WHERE repo=? AND branch=?", (repo, branch))
                self.store.event(db, "remote_snapshot", repo, {"head": head, "tree": tree})
        except Conflict:
            raise
        except (GitHubError, BulkError, KeyError, TypeError, ValueError) as error:
            status = error.status if isinstance(error, GitHubError) else 0
            with self.store.transaction() as db:
                db.execute("UPDATE remote_snapshots SET failure=? WHERE repo=? AND branch=?", (str(status), repo, branch))
                db.execute("INSERT OR REPLACE INTO remote_failures VALUES (?,?,?,?)", (repo, branch, status, self.clock()))
            return {"status": "inaccessible" if status in {401, 403, 404} else "unknown", "snapshot": self.snapshot(), "http_status": status}
        return {"status": "complete", "snapshot": self.snapshot()}

    def lookup(self, path):
        relative_path(path)
        snapshot = self.snapshot()
        if snapshot is None:
            with self.store.connection() as db:
                failure = db.execute("SELECT status FROM remote_failures WHERE repo=? AND branch=?", (self.config.github_repository, self.config.github_branch)).fetchone()
            return {"status": "inaccessible" if failure and failure["status"] in {401, 403, 404} else "unknown", "snapshot": None}
        with self.store.connection() as db:
            rows = [dict(row) for row in db.execute("SELECT * FROM remote_entries WHERE repo=? AND tree=? AND key=?", (snapshot["repo"], snapshot["tree"], path_key(path)))]
        if len(rows) > 1 or (rows and rows[0]["path"] != path):
            return {"status": "case_conflict", "entries": rows, "snapshot": snapshot}
        if rows:
            return {"status": "found", "entry": rows[0], "snapshot": snapshot}
        return {"status": "missing" if snapshot["freshness"] == "fresh" else "unknown", "snapshot": snapshot}

    def fetch_image(self, path):
        result = self.lookup(path)
        if result["status"] != "found":
            raise BulkError("remote_unavailable", "An exact remote file is required")
        entry, snapshot = result["entry"], result["snapshot"]
        if entry["type"] != "blob" or entry["mode"] != "100644" or Path(path).suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            raise BulkError("remote_unavailable", "Only ordinary PNG/JPEG image blobs are supported")
        target = confined(self.config.cache_dir, f"blobs/{entry['sha']}{Path(path).suffix.lower()}")
        if target.is_file():
            data = target.read_bytes() if target.stat().st_size <= self.config.max_blob_bytes else b""
            if blob_sha(data) != entry["sha"]:
                raise BulkError("corrupt_artifact", "Remote image cache is corrupt")
            verify_image(data, self.config.max_blob_bytes, Path(path).suffix.lower())
            self._cache_receipt(target, data, entry, snapshot)
            return target
        if self.config.offline or self.client is None:
            raise BulkError("offline", "Selected blob is not in the verified local cache")
        if entry["size"] is not None and entry["size"] > self.config.max_blob_bytes:
            raise BulkError("oversize_blob", "Remote blob exceeds byte limit")
        value = self.client.blob(entry["sha"])
        if value.get("encoding") != "base64" or value.get("sha") != entry["sha"] or not isinstance(value.get("content"), str) or len(value["content"]) > self.config.max_blob_bytes * 2:
            raise BulkError("invalid_blob", "Invalid remote blob metadata")
        try:
            data = base64.b64decode("".join(value["content"].split()), validate=True)
        except ValueError as error:
            raise BulkError("invalid_blob", "Invalid base64 blob") from error
        if blob_sha(data) != entry["sha"] or value.get("size") != len(data) or (entry["size"] is not None and entry["size"] != len(data)):
            raise BulkError("invalid_blob", "Remote blob SHA/size mismatch")
        verify_image(data, self.config.max_blob_bytes, Path(path).suffix.lower())
        try:
            atomic_bytes(target, data)
        except FileExistsError:
            if target.read_bytes() != data:
                raise BulkError("corrupt_artifact", "Concurrent image cache write differs")
        self._cache_receipt(target, data, entry, snapshot)
        return target

    def _cache_receipt(self, target, data, entry, snapshot):
        path = target.with_name(target.name + ".json")
        expected = {"blob_sha": entry["sha"], "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        if path.exists():
            try:
                receipt = json.loads(confined(self.config.cache_dir, path.relative_to(self.config.cache_dir).as_posix(), must_exist=True).read_text(encoding="utf-8"))
            except (ValueError, OSError) as error:
                raise BulkError("corrupt_receipt", "Cached remote image receipt is corrupt") from error
            if any(receipt.get(key) != value for key, value in expected.items()):
                raise BulkError("corrupt_receipt", "Remote image cache receipt does not match verified bytes")
            return
        payload = {"schema_version": 1, **expected, "source": {key: snapshot[key] for key in ("repo", "branch", "head", "tree")}, "path": entry["path"]}
        try:
            atomic_bytes(path, canonical(payload))
        except FileExistsError:
            self._cache_receipt(target, data, entry, snapshot)


def verify_image(data, limit, suffix=None):
    if len(data) > limit:
        raise BulkError("oversize_blob", "Image exceeds byte limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in {"PNG", "JPEG"} or image.width * image.height > 24_000_000 or getattr(image, "n_frames", 1) != 1:
                    raise BulkError("invalid_image", "Expected bounded single-frame PNG/JPEG")
                if suffix is not None and image.format != ("PNG" if suffix == ".png" else "JPEG"):
                    raise BulkError("invalid_image", "Image format does not match the selected remote extension")
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
    except (OSError, Image.DecompressionBombWarning, Image.DecompressionBombError) as error:
        raise BulkError("invalid_image", "Remote image cannot be verified") from error


def compare_local(checkout, path, *, expected_blob_sha=None):
    """Optional read-only fallback, with exact component matching on Windows too."""
    relative_path(path)
    root = confined(checkout, path)
    current = Path(checkout)
    for component in path.split("/"):
        if not current.is_dir():
            return {"status": "missing", "path": path}
        names = [entry.name for entry in current.iterdir() if path_key(entry.name) == path_key(component)]
        if names != [component]:
            return {"status": "case_conflict" if names else "missing", "path": path}
        current = current / component
    if not root.is_file():
        return {"status": "missing", "path": path}
    data = root.read_bytes() if root.stat().st_size <= 20_000_000 else b""
    verify_image(data, 20_000_000)
    return {"status": "found", "path": path, "blob_sha": blob_sha(data), "sha256": sha256(root),
            "matches_expected_blob": expected_blob_sha == blob_sha(data) if expected_blob_sha else None,
            "provenance": "explicit read-only local bytes; not a verified remote snapshot"}
