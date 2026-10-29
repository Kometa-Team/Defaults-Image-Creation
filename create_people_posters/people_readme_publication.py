"""Wait for correlated README runs and verify indexes before releasing a batch."""

import base64
import math
import os
import re
import time
import uuid
from pathlib import PurePosixPath
from urllib.parse import quote, unquote, urlsplit

from people_github import GitHubError
from people_remote_inventory import blob_sha
from create_people_posters.people_diagnostics import safe_exception


class ReadmePublication:
    def __init__(self, client, inventory, ledger, *, sleep=time.sleep, now=time.time):
        self.client, self.inventory, self.ledger = client, inventory, ledger
        self.sleep, self.now = sleep, now
        self.timeout = float(os.getenv("PEOPLE_README_TIMEOUT", "1800"))
        self.interval = float(os.getenv("PEOPLE_README_POLL_INTERVAL", "10"))
        self.attempts = int(os.getenv("PEOPLE_README_ATTEMPTS", "3"))
        if (not math.isfinite(self.timeout) or not math.isfinite(self.interval)
                or self.timeout <= 0 or self.interval <= 0 or not 1 <= self.attempts <= 10):
            raise ValueError("README timeout/poll interval must be positive; attempts must be between 1 and 10")

    def verify(self, batch, style):
        repo, branch = self.inventory.repositories[style], self.inventory.branch
        head, _ = self.inventory.refresh(style)
        rows = self.ledger.rows(batch, repo)
        indexes = {"README.md": rows}
        for row in rows:
            image = self.inventory.lookup(style, row["path"])
            if not image or image["sha"] != row["blob"] or image["mode"] != "100644" or image["type"] != "blob":
                raise GitHubError(f"README verification: published image changed: {repo}/{row['path']}")
            indexes.setdefault(PurePosixPath(row["path"]).parts[0] + "/README.md", []).append(row)
        for path, expected in indexes.items():
            entry = self.inventory.lookup(style, path)
            if not entry or entry["type"] != "blob" or entry["mode"] != "100644":
                raise GitHubError(f"README index missing: {repo}/{path}")
            blob = self.client.request("GET", f"/repos/{repo}/git/blobs/{entry['sha']}")
            try:
                if blob.get("encoding") != "base64":
                    raise ValueError("Unsupported README encoding")
                data = base64.b64decode(blob["content"])
                if blob_sha(data) != entry["sha"]:
                    raise ValueError("README blob hash mismatch")
                content = data.decode("utf-8")
            except (ValueError, KeyError, UnicodeError) as error:
                raise GitHubError(f"Invalid README blob: {repo}/{path}") from error
            # Check actual Markdown link destinations, including repo, ref, path,
            # case and extension. A name mentioned elsewhere is not evidence.
            links = set()
            for url in re.findall(r"\]\((https://[^\s]+)\)", content):
                parsed = urlsplit(url)
                if parsed.netloc == "raw.githubusercontent.com" and not parsed.query and not parsed.fragment:
                    links.add(unquote(parsed.path))
            for row in expected:
                if f"/{repo}/{branch}/{row['path']}" not in links:
                    raise GitHubError(f"README index omits published image: {repo}/{path}: {row['path']}")
        # Never certify a snapshot which moved during the multi-file checks.
        if self.client.head(repo, branch)[0] != head:
            raise GitHubError(f"README branch advanced during verification: {repo}")
        return head

    def dispatch(self, batch, repo, details=None):
        previous = details or {}
        details = {"dispatch_id": uuid.uuid4().hex, "attempts": previous.get("attempts", 0) + 1,
                   "deadline": previous.get("deadline", self.now() + self.timeout), "dispatched_at": self.now()}
        # Persist before the POST: a lost acknowledgement or process exit can
        # be reconciled using the token without launching another workflow.
        self.ledger.readme(batch, repo, "waiting", details=details)
        try:
            self.client.request("POST", f"/repos/{repo}/actions/workflows/readme.yml/dispatches", {
                "ref": self.inventory.branch, "inputs": {"batch_id": details["dispatch_id"]}})
        except GitHubError as error:
            if error.status not in {0, 429, 500, 502, 503, 504}:
                raise
            # The POST may have succeeded despite losing its response. Poll
            # for its token before deciding the dispatch failed.
            self.ledger.readme(batch, repo, "waiting", safe_exception(error), details=details)
        return details

    def find_run(self, repo, details):
        if details.get("run_id"):
            return self.client.request("GET", f"/repos/{repo}/actions/runs/{details['run_id']}")
        page = 1
        while True:
            data = self.client.request("GET", f"/repos/{repo}/actions/workflows/readme.yml/runs"
                                       f"?event=workflow_dispatch&branch={quote(self.inventory.branch, safe='')}&per_page=100&page={page}")
            runs = data["workflow_runs"]
            for run in runs:
                if (run.get("display_title") == "README batch " + details["dispatch_id"]
                        and run.get("event") == "workflow_dispatch"
                        and run.get("head_branch") == self.inventory.branch):
                    return run
            if len(runs) < 100:
                return None
            page += 1
            if page > 10:
                raise GitHubError("README run discovery exceeded GitHub's 1,000-run search limit")

    def poll(self, batch, style, details):
        repo = self.inventory.repositories[style]
        if self.now() >= details["deadline"]:
            raise GitHubError(f"README workflow timed out: {repo}; resume the same batch")
        run = self.find_run(repo, details)
        if not run:
            if self.now() - details["dispatched_at"] >= 120:
                if details["attempts"] >= self.attempts:
                    raise GitHubError(f"README dispatch produced no discoverable run: {repo}")
                self.dispatch(batch, repo, details)
            return
        if details.get("run_id") != run["id"]:
            details["run_id"] = run["id"]
            self.ledger.readme(batch, repo, "waiting", details=details)
        if run.get("run_attempt", 1) < details.get("min_run_attempt", 1):
            # A process can exit between recording rerun intent and the POST.
            # Reconcile first, then reissue only after GitHub's visibility grace.
            if self.now() - details.get("rerun_requested_at", 0) >= 60:
                self.request_rerun(batch, repo, details)
            return
        if run["status"] != "completed":
            return
        conclusion = run.get("conclusion")
        details["conclusion"] = conclusion if conclusion in {
            "success", "failure", "timed_out", "cancelled", "skipped", "neutral", "action_required", "stale"} else "unknown"
        if conclusion == "success":
            try:
                head = self.verify(batch, style)
            except GitHubError:
                details["verification"] = "failed"
                self.ledger.readme(batch, repo, "waiting", details=details)
                if details["attempts"] >= self.attempts:
                    raise
                self.dispatch(batch, repo, details)
                return
            details["verified_head"] = head
            details["verification"] = "passed"
            self.ledger.readme(batch, repo, "verified", details=details)
            print(f"[OK] README indexes verified: {repo} (run {run['id']})", flush=True)
        elif conclusion in {"failure", "timed_out", "cancelled"} and details["attempts"] < self.attempts:
            # Single-job workflows rerun preparation and commit together, so a
            # fresh snapshot is generated after transient errors or ref races.
            details["attempts"] += 1
            details["min_run_attempt"] = run.get("run_attempt", 1) + 1
            details["rerun_endpoint"] = "rerun" if conclusion == "cancelled" else "rerun-failed-jobs"
            self.request_rerun(batch, repo, details)
            print(f"[WARN] Retrying README workflow: {repo} (attempt {details['attempts']})", flush=True)
        else:
            self.ledger.readme(batch, repo, "waiting", details=details)
            raise GitHubError(f"README workflow {run['id']} ended with {conclusion}: {repo}")

    def request_rerun(self, batch, repo, details):
        details["rerun_requested_at"] = self.now()
        self.ledger.readme(batch, repo, "waiting", details=details)
        try:
            self.client.request("POST", f"/repos/{repo}/actions/runs/{details['run_id']}/{details['rerun_endpoint']}", {})
        except GitHubError as error:
            # A lost acknowledgement or an already queued rerun must be
            # reconciled through run_attempt, rather than charged twice.
            if error.status not in {0, 409, 429, 500, 502, 503, 504}:
                raise

    def publish(self, batch, enabled=True):
        errors, active = [], {}
        deadline = self.now() + self.timeout
        for style, repo in self.inventory.repositories.items():
            if not enabled:
                self.ledger.readme(batch, repo, "disabled", details={})
                continue
            state = self.ledger.readme_state(batch, repo)
            try:
                if state["status"] in {"verified", "unchanged"}:
                    try:
                        head = self.verify(batch, style)
                    except GitHubError:
                        pass
                    else:
                        self.ledger.readme(batch, repo, "verified", details=dict(state["details"], verified_head=head))
                        continue
                if state["status"] == "waiting" and state["details"].get("dispatch_id"):
                    details = state["details"]
                    # A new invocation grants time to resume the exact run.
                    details["deadline"] = deadline
                    self.ledger.readme(batch, repo, "waiting", details=details)
                else:
                    details = self.dispatch(batch, repo, {"deadline": deadline})
                active[style] = details
            except GitHubError as error:
                self.fail(batch, repo, error, errors)
        # Launch every repository before waiting; one failure must not hide
        # the outcomes of the other six workflows.
        while active:
            for style in list(active):
                repo = self.inventory.repositories[style]
                try:
                    self.poll(batch, style, active[style])
                except GitHubError as error:
                    self.fail(batch, repo, error, errors)
                    del active[style]
                    continue
                state = self.ledger.readme_state(batch, repo)
                if state["status"] == "verified":
                    del active[style]
                else:
                    active[style] = state["details"]
            if active:
                self.sleep(min(self.interval, 60))
        if errors:
            raise GitHubError("README verification incomplete; batch files retained. " + "; ".join(errors))

    def fail(self, batch, repo, error, errors):
        # A timeout keeps the run token/ID resumable; other errors can be
        # retried with a fresh bounded budget on the next explicit invocation.
        state = self.ledger.readme_state(batch, repo)
        if self.now() >= state["details"].get("deadline", float("inf")):
            message = "README wait timed out; resume the same batch"
        elif state["details"].get("verification") == "failed":
            message = "README indexes do not verify the batch's published images; files retained"
        elif state["details"].get("conclusion") in {"failure", "timed_out", "cancelled", "skipped", "neutral", "action_required", "stale"}:
            message = "README workflow did not succeed; inspect the recorded run ID"
        else:
            message = safe_exception(error)
        status = "waiting" if state["status"] == "waiting" and (
            self.now() >= state["details"].get("deadline", float("inf")) or error.status in {429, 500, 502, 503, 504}) else "failed"
        self.ledger.readme(batch, repo, status, message)
        errors.append(f"{repo}: {message}")
        print(f"[ERROR] README: {repo}: {message}", flush=True)
