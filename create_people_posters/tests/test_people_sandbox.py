import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import people_github as github
from people_publication_state import PublicationState
from people_remote_inventory import RemoteInventory, default_state_dir
from people_workspaces import Workspaces
from publish_people_github import Publisher, prepare
from sandbox_people_github import counts, copied_readme_workflow
from test_people_github import FakeGitHub, plan, BATCH


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    for key in ("PEOPLE_STATE_DIR", "PEOPLE_JOBS_DIR", "PEOPLE_SANDBOX_CONFIG", "PEOPLE_GITHUB_TARGET"):
        monkeypatch.delenv(key, raising=False)
    root = tmp_path / "sandboxes"
    monkeypatch.setattr(github, "SANDBOX_ROOT", root)
    targets = root / "test-run/targets.json"
    targets.parent.mkdir(parents=True)
    config = {"version": 1, "owner": "test-user", "branch": "master",
              "repositories": {style: "test-user/kometa-people-sandbox-" + style for style in github.REPOSITORIES}}
    targets.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("PEOPLE_GITHUB_TARGET", "sandbox")
    monkeypatch.setenv("PEOPLE_SANDBOX_CONFIG", str(targets))
    return targets, config


def test_production_defaults_unchanged(monkeypatch):
    monkeypatch.delenv("PEOPLE_GITHUB_TARGET", raising=False)
    monkeypatch.delenv("PEOPLE_SANDBOX_CONFIG", raising=False)
    assert github.repository_mapping() == github.REPOSITORIES


def test_sandbox_mapping_and_branch(sandbox):
    targets, config = sandbox
    assert github.repository_mapping() == config["repositories"]
    assert github.branch_name() == "master"
    with pytest.raises(ValueError, match="differs"):
        github.branch_name("main")
    assert default_state_dir() == targets.parent / "state"


def test_missing_mode_never_falls_back_to_production(sandbox, monkeypatch):
    monkeypatch.delenv("PEOPLE_GITHUB_TARGET")
    with pytest.raises(ValueError, match="production fallback"):
        github.repository_mapping()


def test_missing_config_never_falls_back(sandbox, monkeypatch):
    monkeypatch.delenv("PEOPLE_SANDBOX_CONFIG")
    with pytest.raises(ValueError, match="no production fallback"):
        github.repository_mapping()


@pytest.mark.parametrize("change", ["owner", "repo", "partial", "duplicate", "branch"])
def test_unsafe_profile_rejected_before_auth_or_network(sandbox, monkeypatch, change):
    targets, config = sandbox
    if change == "owner":
        config["owner"] = "Kometa-Team"
    elif change == "repo":
        config["repositories"]["original"] = "Kometa-Team/People-Images"
    elif change == "partial":
        config["repositories"].pop("transparent")
    elif change == "duplicate":
        config["repositories"]["original"] = config["repositories"]["bw"]
    else:
        config["branch"] = "main"
    targets.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(github, "auth_token", lambda: pytest.fail("auth reached before config validation"))
    with pytest.raises(ValueError):
        github.GitHubClient()


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "PUT", "DELETE"])
@pytest.mark.parametrize("path", ["/repos/Kometa-Team/People-Images/git/blobs",
                                  "/repos/test-user/another-repo/git/blobs",
                                  "/repos/test-user/kometa-people-sandbox-bw/../../Kometa-Team/People-Images",
                                  "/repos/test-user/kometa-people-sandbox-bw/%2e%2e/People-Images"])
def test_transport_blocks_non_allowlisted_requests(sandbox, method, path):
    session = SimpleNamespace(headers={}, request=lambda *a, **k: pytest.fail("network reached"))
    client = github.GitHubClient("dummy", session)
    with pytest.raises(ValueError, match="Sandbox transport blocked"):
        client.request(method, path)


def test_allowlisted_request_reaches_transport(sandbox):
    calls = []
    response = SimpleNamespace(status_code=200, json=lambda: {"ok": True})
    session = SimpleNamespace(headers={}, request=lambda *a, **k: calls.append(a) or response)
    client = github.GitHubClient("dummy", session)
    assert client.request("GET", "/repos/test-user/kometa-people-sandbox-bw") == {"ok": True}
    assert len(calls) == 1


def test_workspaces_and_receipts_are_isolated(sandbox, tmp_path):
    targets, _ = sandbox
    manager = Workspaces(tmp_path / "normal-config")
    try:
        assert manager.jobs == targets.parent / "jobs"
        assert manager.state == targets.parent / "state"
        assert manager.jobs != manager.config / "jobs"
    finally:
        manager.close()


@pytest.mark.parametrize("key", ["PEOPLE_STATE_DIR", "PEOPLE_JOBS_DIR"])
def test_shared_production_storage_blocked(sandbox, monkeypatch, tmp_path, key):
    monkeypatch.setenv(key, str(tmp_path / "production"))
    with pytest.raises(ValueError, match="isolated"):
        Workspaces(tmp_path / "normal-config")


def test_cannot_retarget_production_receipts(sandbox, tmp_path):
    _, config = sandbox
    ledger = PublicationState(tmp_path / "ledger")
    inventory = RemoteInventory(FakeGitHub(), tmp_path / "inventory.db", "master")
    try:
        plan(tmp_path, ledger)
        with pytest.raises(ValueError, match="destinations"):
            Publisher(FakeGitHub(), inventory, ledger).publish(BATCH)
        with pytest.raises(ValueError, match="retarget"):
            prepare(tmp_path, BATCH, ledger, "master")
    finally:
        inventory.close()
        ledger.close()


@pytest.mark.parametrize("metadata", [{"private": False}, {"fork": True}, {"full_name": "Kometa-Team/People-Images"}, {"owner": {"type": "Organization"}}])
def test_sandbox_requires_private_personal_nonfork_metadata(sandbox, tmp_path, metadata):
    _, config = sandbox
    repo = config["repositories"]["original"]
    data = dict(full_name=repo, private=True, fork=False, owner={"type": "User"})
    data.update(metadata)
    client = SimpleNamespace(sandbox=True, request=lambda *args: data)
    ledger = PublicationState(tmp_path / "ledger")
    inventory = RemoteInventory(client, tmp_path / "inventory.db", "master")
    try:
        with pytest.raises(github.GitHubError, match="private"):
            Publisher(client, inventory, ledger).validate()
    finally:
        inventory.close()
        ledger.close()


def test_workflow_copy_keeps_scoped_generation_but_removes_notifications(monkeypatch):
    import base64
    import yaml
    workflow = {"on": {"push": None, "workflow_dispatch": None}, "concurrency": {"cancel-in-progress": True},
                "jobs": {"Update-Readmes": {"steps": [
                    {"name": "Generate", "run": "print('unchanged logic')", "env": {"TARGET_REF": "master", "TARGET_REPO": "${{ github.repository }}"}},
                    {"uses": "Kometa-Team/discord-notifications@master"}]}}}
    data = {"content": base64.b64encode(yaml.safe_dump(workflow).encode()).decode()}
    monkeypatch.setattr("sandbox_people_github.gh", lambda *a: json.dumps(data))
    copied = yaml.load(copied_readme_workflow("bw"), Loader=yaml.BaseLoader)
    assert set(copied["on"]) == {"push", "workflow_dispatch"}
    assert len(copied["jobs"]["Update-Readmes"]["steps"]) == 1
    assert copied["jobs"]["Update-Readmes"]["steps"][0]["run"] == "print('unchanged logic')"
