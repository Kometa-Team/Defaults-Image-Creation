"""Small authenticated GitHub transport; no credentials in errors or receipts."""

import os
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests


REPOSITORIES = {
    style: "Kometa-Team/People-Images" + ("" if style == "original" else "-" + style)
    for style in ("original", "transparent", "bw", "diiivoy", "diiivoycolor", "rainier", "signature")
}
SANDBOX_ROOT = Path(__file__).resolve().parent / "config" / "sandboxes"


def sandbox_settings():
    target = os.getenv("PEOPLE_GITHUB_TARGET", "production").strip()
    location = os.getenv("PEOPLE_SANDBOX_CONFIG", "").strip()
    if target not in {"production", "sandbox"}:
        raise ValueError("PEOPLE_GITHUB_TARGET must be production or sandbox")
    if target == "production":
        if location:
            raise ValueError("Sandbox config is set but sandbox mode is not enabled; refusing production fallback")
        return None
    if not location:
        raise ValueError("Sandbox mode requires PEOPLE_SANDBOX_CONFIG; no production fallback")
    from people_workspaces import reject_links
    path = Path(location).expanduser().absolute()
    reject_links(path)
    path = path.resolve()
    try:
        relative = path.relative_to(SANDBOX_ROOT.resolve())
    except ValueError:
        raise ValueError("Sandbox config must be under config/sandboxes/RUN/targets.json") from None
    if len(relative.parts) != 2 or path.name != "targets.json":
        raise ValueError("Sandbox config must be under config/sandboxes/RUN/targets.json")
    if path.stat().st_size > 65536:
        raise ValueError("Sandbox configuration is too large")
    settings = json.loads(path.read_text(encoding="utf-8"))
    owner = settings.get("owner", "")
    if (settings.get("version") != 1 or not isinstance(owner, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", owner)
            or owner.casefold() == "kometa-team" or settings.get("branch") != "master"):
        raise ValueError("Sandbox requires a personal owner, version 1 and an explicit master branch")
    expected = {style: f"{owner}/kometa-people-sandbox-{style}" for style in REPOSITORIES}
    if settings.get("repositories") != expected:
        raise ValueError("Sandbox must name exactly seven distinct personal kometa-people-sandbox-STYLE repositories")
    return dict(settings, root=path.parent)


def repository_mapping():
    settings = sandbox_settings()
    return dict(settings["repositories"] if settings else REPOSITORIES)


def sandbox_storage():
    settings = sandbox_settings()
    if not settings:
        return None
    result = {"PEOPLE_STATE_DIR": settings["root"] / "state", "PEOPLE_JOBS_DIR": settings["root"] / "jobs"}
    for key, expected in result.items():
        value = os.getenv(key, "").strip()
        if value and Path(value).expanduser().resolve() != expected.resolve():
            raise ValueError(f"Sandbox {key} must use its isolated {expected.name} directory")
    return result


class GitHubError(RuntimeError):
    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


def branch_name(value=None):
    settings = sandbox_settings()
    if settings:
        if value and value != settings["branch"]:
            raise ValueError("Sandbox branch differs from targets.json")
        return settings["branch"]
    branch = value or os.getenv("PEOPLE_BRANCH", "master").strip() or "master"
    if (branch.startswith(("-", "/", ".")) or branch.endswith(("/", ".", ".lock"))
            or any(c.isspace() or ord(c) < 32 or c in "~^:?*[\\" for c in branch)
            or any(p in {"", ".", ".."} for p in branch.split("/")) or ".." in branch or "@{" in branch):
        raise ValueError("Invalid PEOPLE_BRANCH")
    return branch


def auth_token():
    token = os.getenv("GITHUB_TOKEN", "").strip() or os.getenv("GH_TOKEN", "").strip()
    if not token:
        try:
            result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                token = result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    if not token:
        raise GitHubError("GitHub authentication missing. Set GITHUB_TOKEN or run gh auth login; select all seven repositories with Contents:write and Actions:write for README dispatch.")
    return token


class GitHubClient:
    def __init__(self, token=None, session=None, sleep=time.sleep, attempts=4):
        self.sandbox = sandbox_settings()
        self.repositories = repository_mapping()
        self.token = token or auth_token()
        self.session = session or requests.Session()
        self.sleep = sleep
        self.attempts = attempts
        self.last_write = 0.0
        self.write_interval = max(0.0, float(os.getenv("PEOPLE_GITHUB_WRITE_INTERVAL", "1")))
        self.session.headers.update({"Authorization": "Bearer " + self.token,
                                     "Accept": "application/vnd.github+json",
                                     "X-GitHub-Api-Version": "2022-11-28"})

    def request(self, method, path, payload=None):
        if not path.startswith("/repos/"):
            raise ValueError("Only repository API paths are supported")
        if self.sandbox:
            parsed = urlsplit(path)
            segments = parsed.path.split("/")
            allowed = {repo.casefold() for repo in self.repositories.values()}
            if (parsed.scheme or parsed.netloc or parsed.fragment or "%" in parsed.path or "\\" in path
                    or any(segment in {".", ".."} for segment in segments)
                    or "/".join(segments[2:4]).casefold() not in allowed):
                raise ValueError("Sandbox transport blocked a request outside its explicit repository allowlist")
        for attempt in range(self.attempts):
            if method != "GET":
                delay = self.write_interval - (time.monotonic() - self.last_write)
                if delay > 0:
                    self.sleep(delay)
                self.last_write = time.monotonic()
            try:
                response = self.session.request(method, "https://api.github.com" + path,
                                                json=payload, timeout=(10, 90), allow_redirects=False)
            except requests.RequestException:
                if attempt + 1 == self.attempts:
                    raise GitHubError("GitHub network request failed; local files retained. Retry after checking connectivity.") from None
                self.sleep(2 ** attempt)
                continue
            if 200 <= response.status_code < 300:
                if response.status_code == 204:
                    return {}
                try:
                    return response.json()
                except ValueError:
                    if attempt + 1 == self.attempts:
                        raise GitHubError("GitHub returned an incomplete JSON response; retry the operation.") from None
                    self.sleep(2 ** attempt)
                    continue
            rate_limited = response.status_code == 429 or (response.status_code == 403 and (
                response.headers.get("X-RateLimit-Remaining") == "0" or "Retry-After" in response.headers
                or "rate limit" in response.text.lower()))
            transient = rate_limited or response.status_code in {500, 502, 503, 504}
            if transient and attempt + 1 < self.attempts:
                delay = max(2 ** attempt, 60 if rate_limited else 0)
                try:
                    delay = max(delay, float(response.headers.get("Retry-After", "0")),
                                float(response.headers.get("X-RateLimit-Reset", "0")) - time.time() if rate_limited else 0)
                except ValueError:
                    pass
                if delay > 300:
                    raise GitHubError("GitHub rate limit reset exceeds five minutes. Retry later; batch files are retained.", response.status_code)
                self.sleep(delay)
                continue
            status = response.status_code
            if status in {401, 403} and not rate_limited:
                detail = "Authentication/permission failure. Check token expiry, repository selection, Contents:write, Actions:write and branch rules."
            elif status == 404:
                detail = "Repository, configured branch or workflow not found (or token cannot access it); no fallback branch is selected."
            elif status in {409, 422}:
                detail = "Conflict or repository validation/rules failure."
            else:
                detail = "Request failed; check GitHub status and API limits."
            raise GitHubError(f"GitHub HTTP {status}: {detail}", status)

    def head(self, repo, branch):
        ref = self.request("GET", f"/repos/{repo}/git/ref/heads/{quote(branch, safe='/')}")
        sha = ref["object"]["sha"]
        commit = self.request("GET", f"/repos/{repo}/git/commits/{sha}")
        return sha, commit["tree"]["sha"]
