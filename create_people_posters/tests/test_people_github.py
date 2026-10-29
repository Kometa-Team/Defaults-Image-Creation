import base64
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from people_github import GitHubClient, GitHubError, REPOSITORIES, auth_token, branch_name
from people_publication_state import PublicationState
from people_remote_inventory import RemoteInventory, blob_sha, path_key
from publish_people_github import Publisher, prepare

BATCH = "20261014T120000-123456abcdef"


class FakeGitHub:
    def __init__(self):
        self.calls = []
        self.heads, self.commits, self.trees = {}, {}, {}
        self.blobs = {}
        self.counter = 0
        self.fail_repo = None
        self.missing_branch = False
        self.conflict = None
        self.runs = {}
        self.readme_outcomes = {}
        self.omit_index = set()
        for repo in REPOSITORIES.values():
            self.blobs[blob_sha(b"")] = b""
            self.advance(repo, {"README.md": {"sha": blob_sha(b""), "type": "blob", "mode": "100644", "size": 0}})

    def generate_readmes(self, repo):
        from urllib.parse import quote
        files = copy.deepcopy(self.trees[self.commits[self.heads[repo]]])
        images = [path for path in files if "/Images/" in path]
        for index in ["README.md"] + sorted({p.split("/")[0] + "/README.md" for p in images}):
            if (repo, index) in self.omit_index:
                continue
            links = [f"* [{Path(p).stem}](https://raw.githubusercontent.com/{repo}/master/{quote(p)})"
                     for p in images if index == "README.md" or p.startswith(index.split("/")[0] + "/")]
            data = "\n".join(links).encode()
            sha = blob_sha(data)
            self.blobs[sha] = data
            files[index] = {"sha": sha, "type": "blob", "mode": "100644", "size": len(data)}
        self.advance(repo, files)

    def finish_readme(self, repo, run):
        if run["conclusion"] == "success" and not run.get("generated"):
            self.generate_readmes(repo)
            run["generated"] = True
        return run

    def new_sha(self):
        self.counter += 1
        return f"{self.counter:040x}"

    def advance(self, repo, files):
        tree, commit = self.new_sha(), self.new_sha()
        self.trees[tree] = copy.deepcopy(files)
        self.commits[commit] = tree
        self.heads[repo] = commit
        return commit

    def head(self, repo, branch):
        if self.missing_branch or branch != "master":
            raise GitHubError("Missing configured branch", 404)
        return self.heads[repo], self.commits[self.heads[repo]]

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        parts = path.split("/")
        repo = "/".join(parts[2:4])
        route = "/".join(parts[4:])
        if not route:
            return {"permissions": {"push": True}}
        if method == "GET" and route.startswith("git/trees/"):
            tree = route.split("/")[2].split("?")[0]
            return {"sha": tree, "tree": [dict(value, path=key) for key, value in self.trees[tree].items()], "truncated": False}
        if method == "POST" and route == "git/blobs":
            if repo == self.fail_repo:
                raise GitHubError("Insufficient permission", 403)
            data = base64.b64decode(payload["content"])
            sha = blob_sha(data)
            self.blobs[sha] = data
            return {"sha": sha}
        if method == "GET" and route.startswith("git/blobs/"):
            data = self.blobs[parts[-1]]
            return {"encoding": "base64", "content": base64.b64encode(data).decode()}
        if method == "POST" and route == "git/trees":
            tree = self.new_sha()
            self.trees[tree] = copy.deepcopy(self.trees[payload["base_tree"]])
            for row in payload["tree"]:
                self.trees[tree][row["path"]] = dict(row, size=len(self.blobs[row["sha"]]))
            return {"sha": tree}
        if method == "POST" and route == "git/commits":
            commit = self.new_sha()
            self.commits[commit] = payload["tree"]
            return {"sha": commit}
        if method == "PATCH" and route.startswith("git/refs/heads/"):
            assert payload["force"] is False
            assert route.endswith("/master")
            if self.conflict:
                hook, self.conflict = self.conflict, None
                hook(self, repo, payload)
                raise GitHubError("non-fast-forward", 409)
            self.heads[repo] = payload["sha"]
            return {"object": {"sha": payload["sha"]}}
        if method == "POST" and "dispatches" in route:
            assert payload["ref"] == "master"
            if "inputs" in payload:
                outcomes = self.readme_outcomes.get(repo, [])
                conclusion = outcomes.pop(0) if outcomes else "success"
                run = {"id": int(self.new_sha(), 16), "display_title": "README batch " + payload["inputs"]["batch_id"],
                       "event": "workflow_dispatch", "head_branch": "master", "status": "completed",
                       "conclusion": conclusion, "run_attempt": 1}
                self.runs.setdefault(repo, []).append(run)
            return {}
        if method == "GET" and route.startswith("actions/workflows/readme.yml/runs"):
            return {"workflow_runs": [self.finish_readme(repo, run) for run in self.runs.get(repo, [])]}
        if route.startswith("actions/runs/"):
            run = next(r for r in self.runs[repo] if r["id"] == int(parts[6]))
            if method == "GET":
                return self.finish_readme(repo, run)
            if method == "POST" and route.endswith(("/rerun-failed-jobs", "/rerun")):
                outcomes = self.readme_outcomes.get(repo, [])
                run.update(run_attempt=run["run_attempt"] + 1, conclusion=outcomes.pop(0) if outcomes else "success")
                return {}
        if method == "GET" and "compare/" in route:
            return {"status": "ahead"}
        raise AssertionError((method, path))


def plan(tmp_path, ledger, people=("Ada",)):
    rows = []
    for style, repo in REPOSITORIES.items():
        for person in people:
            suffix = ".png" if style == "transparent" else ".jpg"
            data = (style + person).encode()
            path = tmp_path / "prepared" / style / (person + suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            rows.append({"style": style, "repo": repo, "path": person[0].upper() + "/Images/" + person + suffix,
                         "source": str(path), "source_hash": digest, "prepared": str(path),
                         "published_hash": digest, "blob": blob_sha(data), "person": person, "tmdb_id": "42"})
    ledger.plan(BATCH, "master", rows)
    return rows


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("PEOPLE_BRANCH", "master")
    monkeypatch.setenv("UPDATE_TRIGGER_READMES", "true")
    monkeypatch.setenv("UPDATE_REQUIRE_README_DISPATCH", "true")
    monkeypatch.setenv("PEOPLE_README_POLL_INTERVAL", "0.001")
    monkeypatch.delenv("ORCH_COMMIT_MESSAGE", raising=False)
    client = FakeGitHub()
    ledger = PublicationState(tmp_path / "state")
    inventory = RemoteInventory(client, tmp_path / "inventory.db", "master")
    yield client, inventory, ledger, Publisher(client, inventory, ledger)
    ledger.close()
    inventory.close()


def test_mapping():
    assert len(REPOSITORIES) == 7
    assert REPOSITORIES["original"] == "Kometa-Team/People-Images"
    for style in set(REPOSITORIES) - {"original"}:
        assert REPOSITORIES[style] == "Kometa-Team/People-Images-" + style


@pytest.mark.parametrize("branch", ["main", "master", "test/images"])
def test_branch_selection(branch):
    assert branch_name(branch) == branch


@pytest.mark.parametrize("branch", ["../main", "a//b", "a b", "a..b", "a.lock", "a\\b"])
def test_unsafe_branches(branch):
    with pytest.raises(ValueError):
        branch_name(branch)


def test_missing_branch(setup):
    client, inventory, _, publisher = setup
    client.missing_branch = True
    with pytest.raises(GitHubError, match="Missing configured branch"):
        publisher.validate()
    assert not any(method != "GET" for method, _, _ in client.calls)


def test_missing_auth(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr("people_github.subprocess.run", lambda *a, **k: SimpleNamespace(returncode=1))
    with pytest.raises(GitHubError, match="authentication missing"):
        auth_token()


def test_env_auth_does_not_call_gh(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-secret")
    monkeypatch.setattr("people_github.subprocess.run", lambda *a, **k: pytest.fail("unexpected gh"))
    assert auth_token() == "test-secret"


def test_publish_multi_image_and_preserve_unrelated(setup, tmp_path):
    client, inventory, ledger, publisher = setup
    rows = plan(tmp_path, ledger, ("Ada", "Amelie"))
    publisher.publish(BATCH)
    assert ledger.verified(BATCH)
    assert len([c for c in client.calls if c[0] == "PATCH"]) == 7
    for repo in REPOSITORIES.values():
        assert "README.md" in client.trees[client.commits[client.heads[repo]]]
    commits = [c for c in client.calls if c[0] == "POST" and c[1].endswith("git/commits")]
    assert all("[skip readme]" in c[2]["message"] for c in commits)
    dispatch_indices = [i for i, c in enumerate(client.calls) if "dispatches" in c[1]]
    assert len(dispatch_indices) == 7
    assert min(dispatch_indices) > max(i for i, c in enumerate(client.calls) if c[0] == "PATCH")
    client.calls.clear()
    publisher.publish(BATCH)
    assert not any(method != "GET" for method, _, _ in client.calls)
    assert all(r["tmdb_id"] == "42" for r in ledger.rows(BATCH))


def test_existing_different_is_updated(setup, tmp_path):
    client, inventory, ledger, publisher = setup
    plan(tmp_path, ledger)
    repo = REPOSITORIES["original"]
    client.advance(repo, {"A/Images/Ada.jpg": {"sha": "old", "type": "blob", "mode": "100644", "size": 10}})
    publisher.publish(BATCH)
    assert ledger.verified(BATCH)




def test_identical_new_batch_does_not_commit_or_dispatch(setup, tmp_path):
    client, inventory, ledger, publisher = setup
    rows = plan(tmp_path, ledger)
    for row in rows:
        files = copy.deepcopy(client.trees[client.commits[client.heads[row["repo"]]]])
        files[row["path"]] = {"sha": row["blob"], "type": "blob", "mode": "100644", "size": 1}
        client.advance(row["repo"], files)
    for repo in REPOSITORIES.values():
        client.generate_readmes(repo)
    publisher.publish(BATCH)
    assert ledger.verified(BATCH)
    assert all(call[0] == "GET" for call in client.calls)


def test_unicode_roundtrip(setup, tmp_path):
    client, inventory, ledger, publisher = setup
    plan(tmp_path, ledger, ("Am\u00e9lie",))
    publisher.publish(BATCH)
    assert inventory.lookup("original", "A/Images/Am\u00e9lie.jpg")
    assert inventory.missing_styles("Am\u00e9lie") == []


def test_partial_success_resumes_only_remaining_uploads(setup, tmp_path):
    client, inventory, ledger, publisher = setup
    plan(tmp_path, ledger)
    client.fail_repo = REPOSITORIES["rainier"]
    with pytest.raises(GitHubError, match="Partial publication"):
        publisher.publish(BATCH)
    assert sum(row["status"] == "published" for row in ledger.rows(BATCH)) == 6
    assert not ledger.verified(BATCH)
    assert not any("dispatches" in c[1] for c in client.calls)
    client.fail_repo = None
    client.calls.clear()
    publisher.publish(BATCH)
    assert len([c for c in client.calls if c[0] == "PATCH"]) == 1
    assert ledger.verified(BATCH)


def test_concurrent_unrelated_update_rebased_safely(setup, tmp_path):
    client, inventory, ledger, publisher = setup
    plan(tmp_path, ledger)
    def concurrent(client, repo, payload):
        files = copy.deepcopy(client.trees[client.commits[client.heads[repo]]])
        files["other.txt"] = {"sha": "other", "type": "blob", "mode": "100644", "size": 1}
        client.advance(repo, files)
    client.conflict = concurrent
    publisher.publish(BATCH)
    repo = REPOSITORIES["original"]
    assert "other.txt" in client.trees[client.commits[client.heads[repo]]]


def test_concurrent_same_path_not_overwritten(setup, tmp_path):
    client, inventory, ledger, publisher = setup
    plan(tmp_path, ledger)
    def concurrent(client, repo, payload):
        client.advance(repo, {"A/Images/Ada.jpg": {"sha": "contributor", "type": "blob", "mode": "100644", "size": 10}})
    client.conflict = concurrent
    with pytest.raises(GitHubError, match="Concurrent edit"):
        publisher.publish(BATCH)
    assert not ledger.verified(BATCH)


def test_crash_after_ref_update_reconciles_without_duplicate_commit(setup, tmp_path):
    client, inventory, ledger, publisher = setup
    plan(tmp_path, ledger)
    def lost_ack(client, repo, payload):
        client.heads[repo] = payload["sha"]
    client.conflict = lost_ack
    publisher.publish(BATCH)
    assert ledger.verified(BATCH)
    assert len([c for c in client.calls if c[1].endswith("git/commits")]) == 7


def test_previously_published_remote_edit_blocks_resume(setup, tmp_path):
    client, inventory, ledger, publisher = setup
    plan(tmp_path, ledger)
    publisher.publish(BATCH)
    repo = REPOSITORIES["bw"]
    files = copy.deepcopy(client.trees[client.commits[client.heads[repo]]])
    files["A/Images/Ada.jpg"]["sha"] = "edited"
    client.advance(repo, files)
    with pytest.raises(GitHubError, match="previously verified"):
        publisher.publish(BATCH)


def test_dry_run_never_posts_or_marks_published(setup, tmp_path):
    client, inventory, ledger, publisher = setup
    plan(tmp_path, ledger)
    publisher.publish(BATCH, dry_run=True)
    assert all(c[0] == "GET" for c in client.calls)
    assert all(row["status"] == "pending" for row in ledger.rows(BATCH))


def test_truncated_inventory_falls_back_atomically(setup):
    client, inventory, ledger, _ = setup
    def request(method, path, payload=None):
        if "recursive=1" in path:
            return {"truncated": True, "tree": []}
        if path.endswith("/root"):
            return {"truncated": False, "tree": [{"path": "A", "sha": "letter", "type": "tree", "mode": "040000"}]}
        if path.endswith("/letter"):
            return {"truncated": False, "tree": [{"path": "Images", "sha": "images", "type": "tree", "mode": "040000"}]}
        return {"truncated": False, "tree": [{"path": "Ada.jpg", "sha": "blob", "type": "blob", "mode": "100644", "size": 1}]}
    client.request = request
    entries = inventory.tree_entries(REPOSITORIES["bw"], "root")
    assert entries[-1]["path"] == "A/Images/Ada.jpg"


def test_failed_refresh_preserves_cache(setup):
    client, inventory, ledger, _ = setup
    inventory.refresh("bw")
    original = inventory.db.execute("SELECT head FROM snapshots").fetchone()[0]
    client.advance(REPOSITORIES["bw"], {})
    client.request = lambda *a, **k: {"truncated": True, "tree": []}
    with pytest.raises(GitHubError, match="incomplete"):
        inventory.refresh("bw")
    assert inventory.db.execute("SELECT head FROM snapshots").fetchone()[0] == original


@pytest.mark.parametrize("path", ["../outside", "A/../b", "A//b", "/absolute", "C:/outside", "A\\b"])
def test_path_safety(path):
    with pytest.raises(ValueError):
        path_key(path)


@pytest.mark.parametrize("code", [401, 403, 404, 422])
def test_authorization_and_validation_not_retried(code):
    calls = []
    response = SimpleNamespace(status_code=code, text="rejected secret-should-not-appear", headers={})
    session = SimpleNamespace(headers={}, request=lambda *a, **k: calls.append(1) or response)
    client = GitHubClient("test-secret", session, sleep=lambda _: pytest.fail("unexpected retry"))
    with pytest.raises(GitHubError) as error:
        client.request("GET", "/repos/owner/repo")
    assert len(calls) == 1
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_transient_retries_bounded(code):
    delays, calls = [], []
    response = SimpleNamespace(status_code=code, text="temporary", headers={})
    session = SimpleNamespace(headers={}, request=lambda *a, **k: calls.append(1) or response)
    client = GitHubClient("NOT_A_REAL_GITHUB_RETRY_TEST_CREDENTIAL", session, sleep=delays.append)
    with pytest.raises(GitHubError):
        client.request("GET", "/repos/owner/repo")
    assert len(calls) == 4
    assert len(delays) == 3


def test_selective_image_download_hash_verified(setup, tmp_path):
    client, inventory, ledger, publisher = setup
    plan(tmp_path, ledger)
    publisher.publish(BATCH)
    target = inventory.fetch_image("bw", "A/Images/Ada.jpg", tmp_path / "download.jpg")
    assert blob_sha(target.read_bytes()) == inventory.lookup("bw", "A/Images/Ada.jpg")["sha"]


def test_readme_error_policy(setup, tmp_path, monkeypatch):
    client, inventory, ledger, publisher = setup
    plan(tmp_path, ledger)
    request = client.request
    def fail_dispatch(method, path, payload=None):
        if "dispatches" in path:
            raise GitHubError("No Actions permission", 403)
        return request(method, path, payload)
    client.request = fail_dispatch
    with pytest.raises(GitHubError, match="README"):
        publisher.publish(BATCH)
    assert not ledger.verified(BATCH)
    monkeypatch.setenv("UPDATE_REQUIRE_README_DISPATCH", "false")
    with pytest.raises(GitHubError, match="README"):
        publisher.publish(BATCH)
    assert not ledger.verified(BATCH)


def test_prepare_matches_existing_normalizers(tmp_path, monkeypatch):
    from PIL import Image
    from sync_people_images import sync_original_presentation, enforce_transparent_canvas
    monkeypatch.setenv("REMOVE_BG_ENGINE", "birefnet")
    for style in REPOSITORIES:
        suffix = ".png" if style == "transparent" else ".jpg"
        path = tmp_path / "people_dirs" / style / "A" / "Images" / ("Ada" + suffix)
        path.parent.mkdir(parents=True)
        size = (20, 30) if style in {"original", "transparent"} else (2000, 3000)
        image = Image.new("RGBA" if style == "transparent" else "RGB", size, (20, 80, 120, 0) if style == "transparent" else (20, 80, 120))
        if style == "transparent":
            image.paste((20, 80, 120, 255), (5, 5, 15, 25))
        image.save(path)
    ledger = PublicationState(tmp_path / "state")
    try:
        rows = prepare(tmp_path, BATCH, ledger, "master")
        golden = tmp_path / "golden.jpg"
        original = tmp_path / "people_dirs/original/A/Images/Ada.jpg"
        before = original.read_bytes()
        sync_original_presentation(original, golden)
        row = next(r for r in rows if r["style"] == "original")
        assert Path(row["prepared"]).read_bytes() == golden.read_bytes()
        assert original.read_bytes() == before
        golden_png = tmp_path / "golden.png"
        golden_png.write_bytes((tmp_path / "people_dirs/transparent/A/Images/Ada.png").read_bytes())
        enforce_transparent_canvas(golden_png)
        row = next(r for r in rows if r["style"] == "transparent")
        assert Path(row["prepared"]).read_bytes() == golden_png.read_bytes()
        for row in rows:
            if row["style"] not in {"original", "transparent"}:
                assert Path(row["source"]).read_bytes() == Path(row["prepared"]).read_bytes()
    finally:
        ledger.close()
