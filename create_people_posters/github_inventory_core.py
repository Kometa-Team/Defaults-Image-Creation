"""Repository-neutral GitHub read primitives shared by People and Defaults.

No environment variables, credentials, product routing, writes or workspace policy.
"""

import hashlib
import json
import time

import requests


class GitHubError(RuntimeError):
    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


def blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def complete_tree(get_tree, sha):
    try:
        data = get_tree(sha, True)
    except GitHubError as error:
        if error.status not in {0, 500, 502, 503, 504}:
            raise
        data = {"truncated": True}
    if not data.get("truncated"):
        return data["tree"]
    # Discard the partial recursive response before traversing every subtree.
    pending, result = [(sha, "")], []
    while pending:
        subtree, prefix = pending.pop()
        data = get_tree(subtree, False)
        if data.get("truncated"):
            raise GitHubError("Nonrecursive tree truncated; inventory is incomplete")
        for item in data["tree"]:
            entry = dict(item, path=prefix + item["path"])
            result.append(entry)
            if item["type"] == "tree":
                pending.append((item["sha"], entry["path"] + "/"))
    return result


def get_json(session, url, *, sleep=time.sleep, attempts=4, max_bytes=30_000_000):
    """Bounded GET-only JSON transport; errors never contain response text or tokens."""
    for attempt in range(attempts):
        try:
            response = session.get(url, timeout=(10, 90), allow_redirects=False, stream=True)
            try:
                body = bytearray()
                limit = max_bytes if 200 <= response.status_code < 300 else 4096
                for chunk in response.iter_content(65536):
                    body.extend(chunk)
                    if len(body) > limit:
                        if 200 <= response.status_code < 300:
                            raise GitHubError("GitHub JSON response exceeds the byte limit")
                        del body[limit:]
                        break
            finally:
                response.close()
        except requests.RequestException:
            if attempt + 1 == attempts:
                raise GitHubError("GitHub network request failed") from None
            sleep(2 ** attempt)
            continue
        status = response.status_code
        if 200 <= status < 300:
            try:
                value = json.loads(body)
                if not isinstance(value, dict):
                    raise ValueError()
                return value
            except (ValueError, UnicodeError):
                if attempt + 1 == attempts:
                    raise GitHubError("GitHub returned invalid JSON") from None
                sleep(2 ** attempt)
                continue
        rate = status == 429 or (status == 403 and (response.headers.get("X-RateLimit-Remaining") == "0"
                 or "Retry-After" in response.headers or b"rate limit" in bytes(body).lower()))
        if (rate or status in {500, 502, 503, 504}) and attempt + 1 < attempts:
            try:
                delay = max(2 ** attempt, 60 if rate else 0, float(response.headers.get("Retry-After", "0")),
                            float(response.headers.get("X-RateLimit-Reset", "0")) - time.time() if rate else 0)
            except ValueError:
                delay = max(2 ** attempt, 60 if rate else 0)
            if delay > 300:
                raise GitHubError("GitHub retry exceeds the five-minute limit", status)
            sleep(delay)
            continue
        detail = "authentication/repository access denied" if status in {401, 403, 404} else "request failed"
        raise GitHubError(f"GitHub HTTP {status}: {detail}", status)
    raise GitHubError("GitHub attempts exhausted")
