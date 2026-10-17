import base64
from copy import deepcopy
from dataclasses import replace
from io import BytesIO
import json
import os
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest
import subprocess

from create_defaults.bulk.assets import discover_assets
from create_defaults.bulk.common import BulkError, reject_links
from create_defaults.bulk.config import Config
from create_defaults.bulk.remote import GitHubError, ReadOnlyGitHub, RemoteInventory, blob_sha, compare_local
from create_defaults.bulk.state import Store
from create_people_posters.github_inventory_core import get_json


def png():
    stream = BytesIO()
    Image.new("RGBA", (5, 6), (20, 40, 60, 128)).save(stream, "PNG")
    return stream.getvalue()


class FakeGitHub:
    repo = "Kometa-Team/Default-Images"

    def __init__(self):
        self.data = png()
        self.head_sha, self.tree_sha, self.subtree_sha = "a" * 40, "b" * 40, "c" * 40
        self.calls, self.truncated, self.error = [], False, None

    def head(self, branch):
        self.calls.append(("head", branch))
        if self.error:
            raise GitHubError("Fake inaccessible repository", self.error)
        return self.head_sha, self.tree_sha

    def tree(self, sha, recursive=False):
        self.calls.append(("tree", sha, recursive))
        if sha == self.tree_sha:
            entries = [{"path": "genre", "sha": self.subtree_sha, "type": "tree", "mode": "040000"}]
        else:
            entries = [{"path": "Action.png", "sha": blob_sha(self.data), "type": "blob", "mode": "100644", "size": len(self.data)}]
        if recursive and self.truncated:
            return {"sha": sha, "truncated": True, "tree": [{"path": "WRONG.png"}]}
        return {"sha": sha, "truncated": False, "tree": entries}

    def blob(self, sha):
        self.calls.append(("blob", sha))
        return {"encoding": "base64", "content": base64.b64encode(self.data).decode(), "size": len(self.data), "sha": sha}


@pytest.fixture
def remote(tmp_path):
    config = Config(cache_dir=tmp_path / "cache", workspace_dir=tmp_path / "work", output_dir=tmp_path / "out")
    client = FakeGitHub()
    inventory = RemoteInventory(Store(tmp_path / "remote.sqlite"), config, client)
    return inventory, client


def test_complete_truncated_tree_incremental_snapshot_and_selective_fetch(remote):
    inventory, client = remote
    client.truncated = True
    assert inventory.refresh()["status"] == "complete"
    assert inventory.lookup("genre/Action.png")["status"] == "found"
    assert inventory.lookup("genre/WRONG.png")["status"] == "missing"
    assert any(call == ("tree", client.subtree_sha, False) for call in client.calls)
    assert not any(call[0] == "blob" for call in client.calls)
    target = inventory.fetch_image("genre/Action.png")
    assert target.read_bytes() == client.data
    assert len([call for call in client.calls if call[0] == "blob"]) == 1
    assert inventory.fetch_image("genre/Action.png") == target
    before = len(client.calls)
    assert inventory.refresh()["status"] == "complete"
    assert client.calls[before:] == [("head", "master")]
    client.tree_sha = "d" * 40
    before = len(client.calls)
    inventory.refresh()
    assert ("tree", client.subtree_sha, True) not in client.calls[before:]


def test_incomplete_refresh_preserves_snapshot_and_missing_becomes_unknown(remote):
    inventory, client = remote
    inventory.refresh()
    previous = inventory.snapshot()["tree"]
    client.tree_sha = "d" * 40
    client.tree = lambda *args: {"truncated": True, "tree": []}
    assert inventory.refresh()["status"] == "unknown"
    assert inventory.snapshot()["tree"] == previous
    assert inventory.lookup("genre/Absent.png")["status"] == "unknown"
    assert inventory.lookup("genre/Action.png")["snapshot"]["freshness"] == "stale"


def test_initial_auth_failure_is_inaccessible_not_missing(remote):
    inventory, client = remote
    client.error = 404
    assert inventory.refresh()["status"] == "inaccessible"
    assert inventory.lookup("genre/Absent.png")["status"] == "inaccessible"


def test_offline_and_stale_metadata_do_not_access_network(remote):
    inventory, client = remote
    inventory.refresh()
    inventory.config = replace(inventory.config, offline=True)
    client.head = lambda *args: pytest.fail("offline network access")
    assert inventory.refresh()["status"] == "offline"
    assert inventory.lookup("genre/Absent.png")["status"] == "unknown"
    with pytest.raises(BulkError, match="not in"):
        inventory.fetch_image("genre/Action.png")


def test_case_and_unicode_collisions_not_exact_path_aliases(remote):
    inventory, client = remote
    inventory.refresh()
    assert inventory.lookup("Genre/Action.png")["status"] == "case_conflict"
    snapshot = inventory.snapshot()
    with inventory.store.transaction() as db:
        original = db.execute("SELECT * FROM remote_entries WHERE path='genre/Action.png'").fetchone()
        db.execute("INSERT INTO remote_entries VALUES (?,?,?,?,?,?,?,?)", (original["repo"], original["tree"], "genre/ACTION.png", original["key"], original["sha"], original["size"], original["mode"], original["type"]))
    assert inventory.lookup("genre/Action.png")["status"] == "case_conflict"


def test_blob_sha_size_and_cached_corruption_rejected(remote):
    inventory, client = remote
    inventory.refresh()
    original = client.blob
    client.blob = lambda sha: {**original(sha), "content": base64.b64encode(b"wrong").decode()}
    with pytest.raises(BulkError, match="SHA/size"):
        inventory.fetch_image("genre/Action.png")
    client.blob = original
    target = inventory.fetch_image("genre/Action.png")
    target.write_bytes(b"corrupt")
    with pytest.raises(BulkError, match="corrupt"):
        inventory.fetch_image("genre/Action.png")


def test_unsafe_remote_paths_are_never_fetched(remote):
    inventory, client = remote
    for path in ("../x.png", "C:/x.png", "genre\\x.png"):
        with pytest.raises(BulkError):
            inventory.lookup(path)
    assert not client.calls


class Response:
    def __init__(self, status, payload, headers=None):
        self.status_code, self.payload, self.headers = status, payload, headers or {}
    def iter_content(self, size):
        yield json.dumps(self.payload).encode()
    def close(self):
        pass


class Session:
    def __init__(self, responses):
        self.responses, self.headers, self.calls = iter(responses), {}, []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


def test_get_only_transport_rate_limit_and_sanitized_failures():
    delays = []
    session = Session([Response(429, {}, {"Retry-After": "1"}), Response(200, {"ok": True})])
    assert get_json(session, "https://api.github.com/repos/owner/repo", sleep=delays.append) == {"ok": True}
    assert delays == [60]
    assert all(call[1]["allow_redirects"] is False for call in session.calls)
    with pytest.raises(GitHubError) as error:
        get_json(Session([Response(401, {"message": "secret-token"})]), "https://api.github.com/repos/owner/repo")
    assert "secret-token" not in str(error.value)
    with pytest.raises(GitHubError, match="limit"):
        get_json(Session([Response(200, {"large": "x" * 100})]), "https://api.github.com/repos/owner/repo", max_bytes=20)
    api = ReadOnlyGitHub(session=Session([]))
    assert not any(hasattr(api, method) for method in ("request", "post", "put", "delete", "publish", "patch"))
    with pytest.raises(BulkError):
        ReadOnlyGitHub("https://other.example/repo")


def test_asset_discovery_and_local_checkout_read_only(tmp_path):
    root = tmp_path / "source"
    logos = root / "logos_genre"
    logos.mkdir(parents=True)
    (logos / "Action.png").write_bytes(png())
    (logos / "Duplicate.png").write_bytes(png())
    (logos / "unexpected.txt").write_text("not artwork")
    report = discover_assets(root, ["logos_genre"])
    assert len(report["files"]) == 3 and report["approved_definitions_created"] == 0
    assert {d["code"] for d in report["diagnostics"]} >= {"duplicate_source_identity", "unexpected_format", "invalid_source_image"}
    before = (logos / "Action.png").read_bytes()
    assert compare_local(root, "logos_genre/Action.png", expected_blob_sha=blob_sha(before))["matches_expected_blob"] is True
    assert compare_local(root, "logos_genre/action.png")["status"] == "case_conflict"
    assert (logos / "Action.png").read_bytes() == before


def test_symlinks_and_junctions_are_rejected(tmp_path):
    target, link = tmp_path / "target", tmp_path / "link"
    target.mkdir()
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Windows account cannot create symlinks; portable path checks still run")
    with pytest.raises(BulkError):
        reject_links(link / "child")
    report = discover_assets(tmp_path, ["target"])
    assert report["source_files_deleted"] == 0


@pytest.mark.skipif(os.name != "nt", reason="Windows junction integration test")
def test_windows_junction_rejected_by_discovery_and_cleanup(tmp_path):
    from create_defaults.bulk.workspaces import Workspaces
    store = Store(tmp_path / "state.sqlite")
    manager = Workspaces(store, tmp_path / "work")
    handle = manager.create()
    path = manager.owned(**handle)
    target = tmp_path / "outside"
    target.mkdir()
    important = target / "important.png"
    important.write_bytes(png())
    link = path / "junction"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
    if result.returncode:
        pytest.skip("Account/filesystem cannot create junctions")
    try:
        with pytest.raises(BulkError, match="reparse"):
            manager.cleanup(**handle, retain_seconds=0)
        assert important.read_bytes() == png()
        report = discover_assets(manager.root, [handle["identity"]])
        assert any(item["code"] == "unsafe_source_path" for item in report["diagnostics"])
    finally:
        os.rmdir(link)
