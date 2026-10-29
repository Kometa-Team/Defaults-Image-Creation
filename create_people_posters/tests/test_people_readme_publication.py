"""Offline regression coverage for README completion and batch retention."""

import copy
import sqlite3
import time

import pytest

from test_people_github import BATCH, plan, setup
from test_people_workspaces import manager, published_job
from people_github import GitHubError, REPOSITORIES
from people_publication_state import PublicationState
from people_readme_publication import ReadmePublication
from people_remote_inventory import blob_sha


def test_failed_workflow_retried_and_verified(setup, tmp_path):
    client, _, ledger, publisher = setup
    plan(tmp_path, ledger)
    repo = REPOSITORIES["original"]
    client.readme_outcomes[repo] = ["failure", "success"]
    publisher.publish(BATCH)
    assert ledger.verified(BATCH)
    assert client.runs[repo][0]["run_attempt"] == 2
    assert ledger.readme_state(BATCH, repo)["details"]["attempts"] == 2
    assert sum("dispatches" in path for _, path, _ in client.calls) == 7


def test_exhausted_job_retains_batch_and_finishes_other_six(setup, tmp_path):
    client, _, ledger, publisher = setup
    plan(tmp_path, ledger)
    repo = REPOSITORIES["original"]
    client.readme_outcomes[repo] = ["failure"] * 3
    with pytest.raises(GitHubError, match="README verification incomplete"):
        publisher.publish(BATCH)
    assert not ledger.verified(BATCH)
    assert all(row["status"] == "published" for row in ledger.rows(BATCH))
    assert sum(ledger.readme_state(BATCH, r)["status"] == "verified" for r in REPOSITORIES.values()) == 6
    assert client.runs[repo][0]["run_attempt"] == 3
    assert all(row["prepared"] for row in ledger.rows(BATCH))


@pytest.mark.parametrize("index", ["README.md", "A/README.md"])
def test_successful_workflow_with_missing_index_is_incomplete(setup, tmp_path, index):
    client, _, ledger, publisher = setup
    plan(tmp_path, ledger)
    repo = REPOSITORIES["bw"]
    client.omit_index.add((repo, index))
    with pytest.raises(GitHubError, match="README verification incomplete"):
        publisher.publish(BATCH)
    assert not ledger.verified(BATCH)
    assert len(client.runs[repo]) == 3
    assert len([c for c in client.calls if c[0] == "PATCH"]) == 7
    client.omit_index.clear()
    client.calls.clear()
    publisher.publish(BATCH)
    assert ledger.verified(BATCH)
    assert sum("dispatches" in p for _, p, _ in client.calls) == 1
    assert not any(method == "PATCH" for method, _, _ in client.calls)


def test_stale_index_repaired_automatically_after_success(setup, tmp_path):
    client, _, ledger, publisher = setup
    plan(tmp_path, ledger)
    repo = REPOSITORIES["bw"]
    generate = client.generate_readmes
    count = []

    def once_stale(target):
        if target == repo and not count:
            count.append(1)
            return
        generate(target)

    client.generate_readmes = once_stale
    publisher.publish(BATCH)
    assert ledger.verified(BATCH)
    assert len(client.runs[repo]) == 2


def test_timeout_resumes_exact_run_without_dispatching_again(setup, tmp_path, monkeypatch):
    client, _, ledger, publisher = setup
    plan(tmp_path, ledger)
    monkeypatch.setenv("PEOPLE_README_TIMEOUT", "0.03")
    clock = [1000.0]
    initialize = ReadmePublication.__init__

    def advance(seconds):
        clock[0] += seconds

    def with_clock(self, client, inventory, ledger):
        initialize(self, client, inventory, ledger, now=lambda: clock[0], sleep=advance)

    monkeypatch.setattr(ReadmePublication, "__init__", with_clock)
    find = ReadmePublication.find_run

    def queued(self, repo, details):
        run = find(self, repo, details)
        return dict(run, status="queued") if run else None

    with monkeypatch.context() as delayed:
        delayed.setattr(ReadmePublication, "find_run", queued)
        with pytest.raises(GitHubError, match="README verification incomplete"):
            publisher.publish(BATCH)
    assert not ledger.verified(BATCH)
    assert all(ledger.readme_state(BATCH, r)["status"] == "waiting" for r in REPOSITORIES.values())
    run_ids = {r: ledger.readme_state(BATCH, r)["details"]["run_id"] for r in REPOSITORIES.values()}
    monkeypatch.setenv("PEOPLE_README_TIMEOUT", "10")
    client.calls.clear()
    publisher.publish(BATCH)
    assert ledger.verified(BATCH)
    assert not any(method != "GET" for method, _, _ in client.calls)
    assert all(ledger.readme_state(BATCH, r)["details"]["run_id"] == run_ids[r] for r in REPOSITORIES.values())


def test_lost_dispatch_ack_reconciles_using_dispatch_id(setup, tmp_path):
    client, _, ledger, publisher = setup
    plan(tmp_path, ledger)
    request = client.request

    def lost_ack(method, path, payload=None):
        result = request(method, path, payload)
        if path.endswith("/dispatches"):
            raise GitHubError("Temporary network error")
        return result

    client.request = lost_ack
    publisher.publish(BATCH)
    assert ledger.verified(BATCH)
    assert all(len(runs) == 1 for runs in client.runs.values())


def test_old_failed_attempt_is_not_mistaken_for_rerun_result(setup, tmp_path):
    client, _, ledger, publisher = setup
    plan(tmp_path, ledger)
    repo = REPOSITORIES["original"]
    client.readme_outcomes[repo] = ["failure", "success"]
    request, stale = client.request, []

    def delayed_attempt(method, path, payload=None):
        result = request(method, path, payload)
        if method == "POST" and path.endswith("/rerun-failed-jobs"):
            stale.append(True)
        elif method == "GET" and f"/repos/{repo}/actions/runs/" in path and stale:
            stale.pop()
            return dict(result, conclusion="failure", run_attempt=1)
        return result

    client.request = delayed_attempt
    publisher.publish(BATCH)
    assert ledger.verified(BATCH)
    assert ledger.readme_state(BATCH, repo)["details"]["attempts"] == 2


@pytest.mark.parametrize("replacement", ["People-Images-bw", "main", "Ada.png", "ada.jpg"])
def test_index_requires_exact_repository_branch_and_image_path(setup, tmp_path, replacement):
    client, inventory, ledger, publisher = setup
    plan(tmp_path, ledger)
    publisher.publish(BATCH)
    repo = REPOSITORIES["original"]
    files = copy.deepcopy(client.trees[client.commits[client.heads[repo]]])
    data = client.blobs[files["README.md"]["sha"]]
    needle = b"People-Images" if replacement.startswith("People") else b"master" if replacement == "main" else b"Ada.jpg"
    data = data.replace(needle, replacement.encode())
    sha = blob_sha(data)
    client.blobs[sha] = data
    files["README.md"]["sha"] = sha
    client.advance(repo, files)
    with pytest.raises(GitHubError, match="omits"):
        ReadmePublication(client, inventory, ledger).verify(BATCH, "original")


def test_unicode_spaces_and_parentheses_are_verified(setup, tmp_path):
    _, _, ledger, publisher = setup
    plan(tmp_path, ledger, ("Amélie (Director)", "Ada Lovelace", "Ada#Queen"))
    publisher.publish(BATCH)
    assert ledger.verified(BATCH)


@pytest.mark.parametrize("status", ["dispatched", "warning", "unchanged", "pending", "failed", "waiting"])
def test_unverified_readme_receipt_blocks_completion(setup, tmp_path, status):
    _, _, ledger, _ = setup
    plan(tmp_path, ledger)
    for repo in REPOSITORIES.values():
        rows = ledger.rows(BATCH, repo)
        ledger.mark(BATCH, repo, [r["path"] for r in rows], "published", "confirmed-head")
        ledger.readme(BATCH, repo, "verified")
    assert ledger.verified(BATCH)
    ledger.readme(BATCH, REPOSITORIES["bw"], status)
    assert not ledger.verified(BATCH)


def test_existing_ledger_is_migrated_without_losing_receipts(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    db = sqlite3.connect(state / "publication_state.db")
    db.execute("CREATE TABLE readmes (batch TEXT, repo TEXT, status TEXT, error TEXT, PRIMARY KEY(batch,repo))")
    db.execute("INSERT INTO readmes VALUES (?,?,'dispatched','')", (BATCH, REPOSITORIES["bw"]))
    db.commit()
    db.close()
    ledger = PublicationState(state)
    try:
        receipt = ledger.readme_state(BATCH, REPOSITORIES["bw"])
        assert receipt["status"] == "dispatched"
        assert receipt["details"] == {}
    finally:
        ledger.close()


def test_unrelated_dispatch_does_not_satisfy_discovery(setup, tmp_path):
    client, _, ledger, publisher = setup
    plan(tmp_path, ledger)
    request = client.request

    def unrelated(method, path, payload=None):
        result = request(method, path, payload)
        if method == "GET" and "/workflows/readme.yml/runs" in path:
            runs = result["workflow_runs"]
            result = {"workflow_runs": [dict(runs[0], id=999, display_title="README another batch"),
                                        dict(runs[0], id=998, head_branch="main")] + runs}
        return result

    client.request = unrelated
    publisher.publish(BATCH)
    assert ledger.verified(BATCH)
    assert all(ledger.readme_state(BATCH, r)["details"]["run_id"] not in {998, 999} for r in REPOSITORIES.values())


@pytest.mark.parametrize("endpoint", ["dispatches", "rerun-failed-jobs"])
def test_unaccepted_api_write_is_reconciled_then_retried(setup, tmp_path, monkeypatch, endpoint):
    client, inventory, ledger, publisher = setup
    plan(tmp_path, ledger)
    monkeypatch.setenv("UPDATE_TRIGGER_READMES", "false")
    publisher.publish(BATCH)
    repo = REPOSITORIES["original"]
    if endpoint == "rerun-failed-jobs":
        client.readme_outcomes[repo] = ["failure", "success"]
    request, failed = client.request, []

    def temporary(method, path, payload=None):
        if method == "POST" and f"/repos/{repo}/" in path and path.endswith("/" + endpoint) and not failed:
            failed.append(True)
            raise GitHubError("Temporary GitHub error", 503)
        return request(method, path, payload)

    client.request = temporary
    monkeypatch.setenv("PEOPLE_README_POLL_INTERVAL", "60")
    clock = [1000.0]

    def advance(seconds):
        clock[0] += seconds

    ReadmePublication(client, inventory, ledger, sleep=advance, now=lambda: clock[0]).publish(BATCH)
    assert failed
    assert ledger.verified(BATCH)
    assert ledger.readme_state(BATCH, repo)["details"]["attempts"] == 2
    assert len(client.runs[repo]) == 1


def test_neutral_job_is_incomplete_without_retry(setup, tmp_path):
    client, _, ledger, publisher = setup
    plan(tmp_path, ledger)
    repo = REPOSITORIES["original"]
    client.readme_outcomes[repo] = ["neutral"]
    with pytest.raises(GitHubError, match="README verification incomplete"):
        publisher.publish(BATCH)
    assert not ledger.verified(BATCH)
    assert client.runs[repo][0]["run_attempt"] == 1


@pytest.mark.parametrize("key,value", [("PEOPLE_README_TIMEOUT", "nan"), ("PEOPLE_README_POLL_INTERVAL", "inf"),
                                       ("PEOPLE_README_ATTEMPTS", "0")])
def test_unbounded_configuration_rejected(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        ReadmePublication(None, None, None)


def test_identical_images_with_stale_indexes_still_repair_readmes(setup, tmp_path):
    client, inventory, ledger, publisher = setup
    rows = plan(tmp_path, ledger)
    for row in rows:
        files = copy.deepcopy(client.trees[client.commits[client.heads[row["repo"]]]])
        files[row["path"]] = {"sha": row["blob"], "type": "blob", "mode": "100644", "size": Path(row["prepared"]).stat().st_size}
        client.advance(row["repo"], files)
    publisher.publish(BATCH)
    assert ledger.verified(BATCH)
    assert not any(call[0] == "PATCH" for call in client.calls)
    assert sum("dispatches" in call[1] for call in client.calls) == 7



@pytest.mark.parametrize("status", ["dispatched", "warning", "unchanged", "failed", "waiting"])
def test_cleanup_retains_images_until_readme_verified(manager, monkeypatch, status):
    batch = published_job(manager, monkeypatch)
    ledger = PublicationState(manager.state)
    try:
        ledger.readme(batch, REPOSITORIES["bw"], status)
        assert not ledger.verified(batch)
        assert manager.cleanup(dry_run=False, now=time.time() + 4 * 86400) == [
            (batch, "retained: publication receipts incomplete")]
        assert (manager.path(batch) / "prepared").exists()
    finally:
        ledger.close()

