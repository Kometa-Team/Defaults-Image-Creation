"""Bounded read-only provider requests with credential-free failure records."""
from __future__ import annotations

import os
import logging
import re
import time
from urllib.parse import urlsplit

import requests

from create_people_posters.people_diagnostics import Diagnostic, DiagnosticError, register_environment, register_secret

TMDB_ORIGIN = "https://api.themoviedb.org"
_TMDB_ROUTES = {
    "search_person": r"/3/search/person",
    "person_images": r"/3/person/[0-9]+/images",
    "person_details": r"/3/person/[0-9]+",
    "popular_people": r"/3/person/popular",
}
_ENDPOINTS = {"search_person": "/3/search/person", "person_images": "/3/person/{person_id}/images",
              "person_details": "/3/person/{person_id}", "popular_people": "/3/person/popular"}


def _close(response):
    try:
        response.close()
        return True
    except Exception:
        return False  # Cleanup exceptions never escape with request context.


def failure_diagnostic(provider, operation, endpoint, error=None, status=None):
    if status is None and error is not None:
        candidate = getattr(getattr(error, "response", None), "status_code", None)
        status = candidate if type(candidate) is int and 100 <= candidate <= 599 else None
    if status == 429:
        category, retryable = "rate_limit", True
    elif status in {401, 403}:
        category, retryable = "authentication", False
    elif status is not None and 500 <= status <= 599:
        category, retryable = "server_error", True
    elif status is not None:
        category, retryable = "client_error", False
    elif isinstance(error, requests.exceptions.SSLError):
        category, retryable = "tls", True
    elif isinstance(error, (requests.exceptions.Timeout, TimeoutError)):
        category, retryable = "timeout", True
    elif isinstance(error, (requests.exceptions.ConnectionError, ConnectionResetError)):
        category, retryable = "connection", True
    else:
        category, retryable = "invalid_response", False
    return Diagnostic(provider, operation, category, status, retryable, endpoint)


def request(session, method, url, *, provider, operation, endpoint, params=None, headers=None,
            timeout=(10, 30), attempts=3, sleep=time.sleep):
    """Do not expose raw requests exceptions, responses, headers or causes.

    Response bodies are input data, never diagnostic fields. Authentication is
    registered before the transport can execute. The caller supplies only fixed
    diagnostic descriptors accepted by Diagnostic's closed vocabulary.
    """
    Diagnostic(provider, operation, "configuration", endpoint=endpoint)
    if method != "GET" or type(attempts) is not int or not 1 <= attempts <= 4:
        raise ValueError("Invalid bounded provider request")
    register_environment()
    # Never forward authentication/cookies left on an unrelated caller session.
    # All supported credentials are supplied explicitly for a fixed provider.
    from create_people_posters.people_diagnostics import sensitive_key
    parsed = urlsplit(url)
    origins = {"TMDB": "api.themoviedb.org", "Google": "www.googleapis.com", "GitHub": "api.github.com"}
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or (provider in origins and parsed.hostname != origins[provider])):
        raise DiagnosticError(Diagnostic(provider, operation, "configuration", endpoint=endpoint))
    for fields in (params or {}, headers or {}):
        for key, value in fields.items():
            if sensitive_key(key):
                register_secret(value)
                if type(value) is str and value.lower().startswith(("bearer ", "basic ")):
                    register_secret(value.split(" ", 1)[1])
    if (getattr(session, "auth", None) or getattr(session, "cookies", None)
            or any(sensitive_key(k) for k in getattr(session, "headers", {}))):
        raise DiagnosticError(Diagnostic(provider, operation, "configuration", endpoint=endpoint))
    if isinstance(session, requests.Session):
        # requests otherwise obtains netrc/proxy authentication behind the
        # explicit header/params boundary. Never forward ambient credentials.
        session.trust_env = False
    failure = None
    for attempt in range(attempts):
        response = None
        retry_after = 0.0
        try:
            response = session.get(url, params=params or {}, headers=headers or {}, timeout=timeout,
                                   allow_redirects=False)
            status = response.status_code
            if type(status) is not int or not 100 <= status <= 599:
                failure = Diagnostic(provider, operation, "invalid_response", endpoint=endpoint)
            elif 200 <= status < 300:
                return response
            else:
                failure = failure_diagnostic(provider, operation, endpoint, status=status)
                # Never print provider-supplied header values. A long or malformed
                # Retry-After ends this bounded attempt rather than retrying early.
                raw_delay = response.headers.get("Retry-After", "0")
                try:
                    retry_after = float(raw_delay)
                    if not 0 <= retry_after <= 30:
                        retry_after = 31.0
                except (TypeError, ValueError, OverflowError):
                    retry_after = 31.0
        except (requests.RequestException, TimeoutError, ConnectionResetError) as error:
            candidate_response = getattr(error, "response", None)
            candidate_status = getattr(candidate_response, "status_code", None)
            status = candidate_status if type(candidate_status) is int and 100 <= candidate_status <= 599 else None
            failure = failure_diagnostic(provider, operation, endpoint, error=error, status=status)
            response = candidate_response
        except Exception:
            failure = Diagnostic(provider, operation, "internal_error", endpoint=endpoint)
        finally:
            if response is not None and failure is not None:
                if not _close(response):
                    failure = Diagnostic(provider, operation, "internal_error", endpoint=endpoint)
        if not failure.retryable or attempt + 1 == attempts or retry_after > 30:
            break
        sleep(max(float(2 ** attempt), retry_after))
        failure = None
    # Raise outside the except suite: neither __context__ nor __cause__ retains
    # a third-party request/exception object containing credentials.
    raise DiagnosticError(failure)


def tmdb_json(session, api_key, path, *, operation, params=None, read_token=None, attempts=3, sleep=time.sleep):
    if operation not in _TMDB_ROUTES or not re.fullmatch(_TMDB_ROUTES[operation], path):
        raise ValueError("Unsupported TMDB endpoint")
    register_secret(api_key)
    read_token = read_token if read_token is not None else os.getenv("TMDB_READ_ACCESS_TOKEN", "")
    register_secret(read_token)
    params = dict(params or {})
    if any(k.casefold() in {"api_key", "apikey", "access_token", "token"} for k in params):
        raise ValueError("Authentication is controlled by the provider client")
    headers = {"Accept": "application/json"}
    if read_token:
        headers["Authorization"] = "Bearer " + read_token
    elif api_key:
        # Legacy v3 API keys and Read Access Tokens are different credentials.
        # Never pass a v3 key as a Bearer token. Service callers must supply the
        # read token; the CLI retains legacy v3 compatibility without raw URLs.
        params["api_key"] = api_key
    else:
        raise DiagnosticError(Diagnostic("TMDB", operation, "configuration", endpoint=_ENDPOINTS[operation]))
    response = request(session, "GET", TMDB_ORIGIN + path, provider="TMDB", operation=operation,
                       endpoint=_ENDPOINTS[operation], params=params, headers=headers,
                       attempts=attempts, sleep=sleep)
    return response_json(response, provider="TMDB", operation=operation, endpoint=_ENDPOINTS[operation])


def response_json(response, *, provider, operation, endpoint):
    """Decode API input without retaining provider-supplied decoder errors."""
    failed = False
    try:
        value = response.json()
        if type(value) is not dict:
            failed = True
    except Exception:
        failed = True
    finally:
        if not _close(response):failed = True
    if failed:
        raise DiagnosticError(Diagnostic(provider, operation, "invalid_response", endpoint=endpoint))
    return value


def image_response(session, url, *, attempts=3, sleep=time.sleep):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment
            or any(c.isspace() or ord(c) < 32 for c in url)):
        raise ValueError("Unsafe image source URL")
    # Caller-managed authentication is not embedded in image URLs or persisted
    # candidates. Public TMDB images use a fixed origin and a validated path.
    if parsed.query:
        from create_people_posters.people_diagnostics import sensitive_key
        from urllib.parse import parse_qsl
        if any(sensitive_key(k) for k, _ in parse_qsl(parsed.query, keep_blank_values=True)):
            raise ValueError("Credential-bearing image URL is not a public source")
    return request(session, "GET", url, provider="image", operation="download_image", endpoint="image",
                   timeout=(10, 60), attempts=attempts, sleep=sleep)


def tmdb_image_path(value):
    if type(value) is not str or not re.fullmatch(r"/[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp)", value, re.I):
        raise ValueError("Invalid TMDB profile image path")
    return value


class SecureTMDBSession(requests.Session):
    """Keep the existing SDK's pagination/person/image semantics, safe transport.

    The SDK logs its parameter dictionary before calling the supplied Session.
    Register credentials first and replace that debug path with our structured
    diagnostics. Only the read-only endpoints used by People are supported.
    """
    def __init__(self, api_key, *, read_token=None, transport=None, sleep=time.sleep):
        super().__init__()
        self._api_key = api_key
        self._read_token = read_token if read_token is not None else os.getenv("TMDB_READ_ACCESS_TOKEN", "")
        register_secret(api_key);register_secret(self._read_token)
        self._transport = transport or requests.Session()
        self._sleep = sleep
        for name in ("tmdbapis.api3", "tmdbapis.api4"):
            logging.getLogger(name).setLevel(logging.WARNING)

    def request(self, method, url, **kwargs):
        parsed = urlsplit(url)
        operation = next((op for op, pattern in _TMDB_ROUTES.items() if re.fullmatch(pattern, parsed.path)), None)
        endpoint = _ENDPOINTS.get(operation)
        if re.fullmatch(r"/3/configuration(?:/(?:countries|languages|primary_translations|jobs|timezones))?", parsed.path):
            operation, endpoint = "configuration", "/3/configuration/{resource}"
        if (method.upper() != "GET" or parsed.scheme != "https" or parsed.netloc != "api.themoviedb.org"
                or parsed.query or parsed.fragment or operation is None):
            raise ValueError("Unsupported TMDB SDK request")
        params = dict(kwargs.get("params") or {})
        supplied_key = params.pop("api_key", None)
        if supplied_key is not None and supplied_key != self._api_key:
            raise ValueError("TMDB SDK credential substitution rejected")
        headers = {"Accept": "application/json"}
        if self._read_token:headers["Authorization"] = "Bearer " + self._read_token
        elif self._api_key:params["api_key"] = self._api_key
        else:raise DiagnosticError(Diagnostic("TMDB", operation, "configuration", endpoint=endpoint))
        response = request(self._transport, "GET", url, provider="TMDB", operation=operation, endpoint=endpoint,
                           params=params, headers=headers, sleep=self._sleep)
        failed = False
        try:
            payload = response.json()
            failed = type(payload) is not dict or "errors" in payload or payload.get("success") is False
        except Exception:
            failed = True
        if failed:
            _close(response)
            raise DiagnosticError(Diagnostic("TMDB", operation, "invalid_response", endpoint=endpoint))
        return response

    def close(self):
        self._transport.close()
        super().close()
