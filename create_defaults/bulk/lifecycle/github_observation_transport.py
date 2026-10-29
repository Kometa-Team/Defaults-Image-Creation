"""M2 GET-only bridge to the existing supervised GitHub CLI session.

No token extraction, login, refresh, writes, shell, cache or response persistence.
Only selected response fields leave this module. This is not an authenticator
for hosted/App/delegated execution, nor an operational authorization provider.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import shutil
import subprocess
import time
from urllib.parse import unquote

from ..config import repository
from ..remote import ReadOnlyGitHub


class ObservationFailure(Exception):
    """Closed reason vocabulary: never wrap remote text or exception messages."""

    def __init__(self, status, reason):
        self.status, self.reason = status, reason
        super().__init__(reason)


def _failure(status, reason):
    raise ObservationFailure(status, reason) from None


def _bounded_process(argv, *, limit=12_000_000, timeout=35):
    # gh owns credentials. Disable debug/tracing/paging; never capture stderr,
    # which can contain request bodies or credential-bearing exception chains.
    environment = {k: v for k, v in os.environ.items()
                   if not k.startswith(('GH_DEBUG', 'GIT_TRACE'))}
    environment.update(GH_PROMPT_DISABLED='1', GH_PAGER='cat', NO_COLOR='1',
                       GH_FORCE_TTY='0')
    try:
        with subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, env=environment) as process:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(process.stdout.read, limit + 1)
                try:
                    raw = future.result(timeout=timeout)
                    if len(raw) > limit:
                        _failure('unavailable', 'response_bound')
                    process.wait(timeout=timeout)
                    return process.returncode, raw
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=5)
    except ObservationFailure:
        raise
    except Exception:
        _failure('unavailable', 'cli_unavailable')


def _decode(raw):
    """Discard all but a small header allowlist; raw bytes stay in memory."""
    header, separator, body = raw.partition(b'\r\n\r\n')
    if not separator:
        header, separator, body = raw.partition(b'\n\n')
    try:
        rows = header.decode('ascii').splitlines()
        match = re.fullmatch(r'HTTP/[0-9.]+ ([0-9]{3})(?: .*)?', rows[0])
        if not separator or not match:
            raise ValueError()
        code = int(match[1])
        headers = {}
        for row in rows[1:]:
            key, colon, value = row.partition(':')
            if not colon:
                raise ValueError()
            key = key.lower()
            if key in {'link', 'retry-after', 'x-ratelimit-remaining'}:
                if key in headers:
                    raise ValueError()
                headers[key] = value.strip()
        # Error bodies are never parsed, recorded, matched or emitted.
        return code, headers, json.loads(body) if code == 200 else None
    except Exception:
        _failure('invalid', 'response_invalid')


class _CLI:
    """Fixed host, explicit GET and endpoint allowlist, bounded retries/pages."""

    def __init__(self, repo):
        self.repo = repository(repo)
        self.executable = shutil.which('gh')
        if not self.executable:
            _failure('unavailable', 'cli_unavailable')
        self.begin()

    def begin(self):
        self._deadline = time.monotonic() + 180
        self._calls = 0

    def get(self, endpoint):
        self._calls += 1
        if self._calls > 1024 or time.monotonic() >= self._deadline:
            _failure('unavailable', 'observation_budget')
        prefix = 'repos/' + self.repo
        allowed = endpoint == 'user' or endpoint == prefix
        suffix = endpoint[len(prefix) + 1:] if endpoint.startswith(prefix + '/') else ''
        allowed = allowed or bool(re.fullmatch(
            r'(?:collaborators/[A-Za-z0-9-]{1,39}/permission|'
            r'pulls/[1-9][0-9]*(?:/reviews(?:/[1-9][0-9]*)?)?|'
            r'issues/(?:[1-9][0-9]*/comments|comments/[1-9][0-9]*)|'
            r'git/(?:ref/heads/[A-Za-z0-9%._/-]+|commits/[0-9a-f]{40}|'
            r'trees/[0-9a-f]{40}(?:\?recursive=1)?|blobs/[0-9a-f]{40}))'
            r'(?:\?per_page=100&page=[1-9][0-9]*)?', suffix))
        if not allowed:
            _failure('invalid', 'endpoint_scope')
        for attempt in range(3):
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                _failure('unavailable', 'observation_budget')
            code, headers, value = 0, {}, None
            try:
                returncode, raw = _bounded_process([self.executable, 'api', '--method',
                    'GET', '--hostname', 'github.com', '--include',
                    '--header', 'Accept: application/vnd.github+json',
                    '--header', 'X-GitHub-Api-Version: 2022-11-28',
                    '--header', 'Cache-Control: no-cache', endpoint], timeout=min(35, remaining))
                if returncode != 0 and not raw:
                    _failure('unavailable', 'cli_unavailable')
                code, headers, value = _decode(raw)
                if code == 200 and returncode == 0:
                    return value, headers
            except ObservationFailure as error:
                if error.reason != 'cli_unavailable' or attempt == 2:
                    raise
            rate = code == 429 or (code == 403 and
                (headers.get('x-ratelimit-remaining') == '0' or 'retry-after' in headers))
            if not (code == 0 or rate or code in {500, 502, 503, 504}):
                if code == 401:
                    _failure('revoked', 'credentials_rejected')
                # 403/404 are ambiguous: access denial is never proof of absence.
                _failure('unavailable', 'access_inconclusive')
            if attempt == 2:
                _failure('unavailable', 'retry_exhausted')
            try:
                delay = max(2 ** attempt, 1 if rate else 0,
                            float(headers.get('retry-after', '0')))
                if not 0 <= delay <= 10:
                    _failure('unavailable', 'retry_bound')
            except ValueError:
                _failure('unavailable', 'retry_bound')
            time.sleep(delay)


class _Git(ReadOnlyGitHub):
    """Reuse head/tree/blob validation; transport is the existing CLI session."""

    def __init__(self, transport):
        self.repo, self._transport = transport.repo, transport

    def _get(self, endpoint):
        value, _ = self._transport.get('repos/' + self.repo + '/' + endpoint)
        if type(value) is not dict:
            _failure('invalid', 'response_shape')
        if endpoint.startswith('git/ref/heads/') and (
                value.get('ref') != 'refs/heads/' + unquote(endpoint[len('git/ref/heads/'):])
                or value.get('object', {}).get('type') != 'commit'):
            _failure('invalid', 'branch_ref_binding')
        return value
