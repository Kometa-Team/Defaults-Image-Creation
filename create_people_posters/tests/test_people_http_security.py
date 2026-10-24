"""Offline provider failures: bounded retries and credential-free exceptions."""
import json
import logging
import os
from pathlib import Path
import sys

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from create_people_posters import people_diagnostics as secure
from create_people_posters import people_http as http

KEY = "NOT_A_REAL_TMDB_V3_TEST_CREDENTIAL"
TOKEN = "NOT_A_REAL_TMDB_READ_TOKEN_TEST_CREDENTIAL"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(secure, "_variants", set())
    for name in tuple(os.environ):
        if secure.sensitive_key(name) or secure._ENV_KEY.search(name):monkeypatch.delenv(name)
    def forbidden(*args, **kwargs):pytest.fail("Live network forbidden", pytrace=False)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


class Response:
    def __init__(self, status=200, payload=None, delay="0"):
        self.status_code = status
        self.payload = {"results": []} if payload is None else payload
        self.headers = {"Retry-After": delay}
        self.closed = False

    def close(self):self.closed = True
    def json(self):
        if isinstance(self.payload, Exception):raise self.payload
        return self.payload


class Transport:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []
        self.auth = None
        self.headers = {}
        self.cookies = {}
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        value = self.outcomes.pop(0)
        if isinstance(value, Exception):raise value
        return value
    def close(self):pass


@pytest.mark.parametrize("failure,category", [
    (requests.exceptions.SSLError, "tls"), (requests.exceptions.ConnectTimeout, "timeout"),
    (requests.exceptions.ReadTimeout, "timeout"), (ConnectionResetError, "connection"),
    (requests.exceptions.ConnectionError, "connection")])
def test_bounded_transient_failures_never_retain_raw_exception_or_request(failure, category):
    transport = Transport(*(failure("https://api.themoviedb.org/3/search/person?api_key=" + KEY) for _ in range(3)))
    sleeps = []
    with pytest.raises(secure.DiagnosticError) as captured:
        http.tmdb_json(transport, KEY, "/3/search/person", operation="search_person", sleep=sleeps.append)
    error = captured.value
    assert len(transport.calls) == 3 and sleeps == [1, 2]
    assert error.__context__ is None and error.__cause__ is None
    assert error.diagnostic.category == category and error.diagnostic.retryable
    assert error.diagnostic.endpoint == "/3/search/person"
    assert KEY not in str(error) and KEY not in repr(error)
    assert set(vars(error)) == {"diagnostic"}


@pytest.mark.parametrize("status,category,retries", [(429, "rate_limit", 3), (500, "server_error", 3),
    (503, "server_error", 3), (401, "authentication", 1), (403, "authentication", 1), (404, "client_error", 1)])
def test_http_failures_are_closed_and_responses_always_closed(status, category, retries):
    responses = [Response(status) for _ in range(retries)]
    transport = Transport(*responses)
    with pytest.raises(secure.DiagnosticError) as captured:
        http.tmdb_json(transport, KEY, "/3/search/person", operation="search_person", sleep=lambda _: None)
    assert captured.value.diagnostic.category == category
    assert captured.value.diagnostic.status == status
    assert len(transport.calls) == retries and all(r.closed for r in responses)


@pytest.mark.parametrize("delay", ["3600", "not-a-number", "nan", "-1"])
def test_long_or_malformed_retry_after_preserves_retry_without_early_request(delay):
    response = Response(429, delay=delay)
    transport = Transport(response)
    with pytest.raises(secure.DiagnosticError) as captured:
        http.tmdb_json(transport, KEY, "/3/search/person", operation="search_person",
                       sleep=lambda _: pytest.fail("Must not retry before provider delay"))
    assert captured.value.diagnostic.retryable and len(transport.calls) == 1 and response.closed


def test_success_after_retry_and_preferred_read_token_has_no_query_credential():
    failed, success = Response(500), Response()
    transport = Transport(failed, success)
    sleeps = []
    assert http.tmdb_json(transport, KEY, "/3/search/person", operation="search_person", read_token=TOKEN,
                          params={"query": "Person"}, sleep=sleeps.append) == {"results": []}
    assert sleeps == [1] and failed.closed and success.closed
    for url, args in transport.calls:
        assert "?" not in url and "api_key" not in args["params"]
        assert args["headers"]["Authorization"] == "Bearer " + TOKEN
        assert args["allow_redirects"] is False


def test_legacy_key_remains_v3_query_authentication_not_bearer():
    transport = Transport(Response())
    http.tmdb_json(transport, KEY, "/3/search/person", operation="search_person", read_token="")
    _, args = transport.calls[0]
    assert args["params"]["api_key"] == KEY and "Authorization" not in args["headers"]


def test_invalid_json_cannot_retain_credential_bearing_decoder_error():
    response = Response(payload=ValueError(KEY))
    with pytest.raises(secure.DiagnosticError) as captured:
        http.tmdb_json(Transport(response), KEY, "/3/search/person", operation="search_person")
    assert response.closed and captured.value.diagnostic.category == "invalid_response"
    assert captured.value.__context__ is None and KEY not in str(captured.value)


@pytest.mark.parametrize("stage", ["decode", "close"])
def test_unexpected_decode_and_cleanup_errors_cannot_escape_raw(stage):
    response = Response(payload=RuntimeError(KEY)) if stage == "decode" else Response()
    if stage == "close":
        def failed_close():raise RuntimeError(KEY)
        response.close = failed_close
    with pytest.raises(secure.DiagnosticError) as captured:
        http.tmdb_json(Transport(response), KEY, "/3/search/person", operation="search_person")
    assert captured.value.diagnostic.category == "invalid_response"
    assert captured.value.__context__ is None and captured.value.__cause__ is None
    assert KEY not in repr(captured.value)


@pytest.mark.parametrize("field", ["auth", "cookies", "headers"])
def test_session_authentication_cannot_be_forwarded_to_image_hosts(field):
    transport = Transport()
    setattr(transport, field, ("user", KEY) if field == "auth" else {"Authorization": KEY})
    with pytest.raises(secure.DiagnosticError):http.image_response(transport, "https://image.tmdb.org/test.jpg")
    assert not transport.calls


@pytest.mark.parametrize("url", ["http://image.tmdb.org/test.jpg", "https://user:password@host/image.jpg",
                                   "https://image.tmdb.org/test.jpg?Api%5FKey=fake", "https://host/a.jpg#token",
                                   "https://example.test/a b.jpg?sig=NOT_A_REAL_SIGNED_SOURCE"],
                         ids=["insecure-scheme", "userinfo", "credential-query", "fragment", "unescaped-space"])
def test_untrusted_image_authentication_urls_fail_closed(url):
    transport = Transport()
    with pytest.raises(ValueError):http.image_response(transport, url)
    assert not transport.calls


def test_existing_sdk_uses_secured_session_for_configuration_and_person_images():
    config = {"images": {"base_url": "http://image.tmdb.org/t/p/", "secure_base_url": "https://image.tmdb.org/t/p/",
        **{kind + "_sizes": ["original"] for kind in ("backdrop", "logo", "poster", "profile", "still")}},
        "change_keys": []}
    transport = Transport(Response(payload=config), Response())
    with http.SecureTMDBSession(KEY, read_token=TOKEN, transport=transport) as session:
        session.get("https://api.themoviedb.org/3/configuration", params={"api_key": KEY})
        session.get("https://api.themoviedb.org/3/person/123/images", params={"api_key": KEY})
        with pytest.raises(ValueError):session.get("https://api.themoviedb.org/3/person/123/images", params={"api_key": "substitute"})
        with pytest.raises(ValueError):session.post("https://api.themoviedb.org/3/person/123/images")
    assert len(transport.calls) == 2
    assert all("api_key" not in args["params"] and args["headers"]["Authorization"] == "Bearer " + TOKEN
               for _, args in transport.calls)


def test_logger_destination_failure_never_uses_standard_raw_fallback(monkeypatch, capsys):
    class BrokenStream:
        def write(self, text):raise OSError(KEY)
        def flush(self):pass
    logger = logging.Logger("broken-sink")
    logger.addHandler(secure.secure_handler(logging.StreamHandler(BrokenStream())))
    logger.error("raw request api_key=%s", KEY)
    output = capsys.readouterr().err
    assert KEY not in output and "diagnostic content withheld" in output
    class UnknownHandler(logging.Handler):pass
    with pytest.raises(ValueError):secure.secure_handler(UnknownHandler())


def test_native_subprocess_writes_are_piped_and_sanitized_before_any_delivery(tmp_path):
    import sys
    from create_people_posters.people_process import run_process
    secret = "NOT_A_REAL_NATIVE_STDERR_TEST_CREDENTIAL"
    environment = dict(os.environ, TMDB_KEY=secret)
    code = "import os;v=os.environ['TMDB_KEY'];os.write(1,('native endpoint=/3/search/person value='+v+'\\n').encode());os.write(2,(v+'\\n').encode())"
    result = run_process([sys.executable, "-c", code], env=environment, log_path=tmp_path / "process.log", timeout=30)
    assert result.returncode == 0
    assert all(secret not in value for value in (result.stdout, result.stderr, (tmp_path / "process.log").read_text()))
    assert "native endpoint=/3/search/person" in result.stdout


def test_direct_orchestrator_cli_uses_guarded_worker_without_recursive_launch(tmp_path):
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[1]
    (tmp_path / ".env").write_text("# Isolated offline CLI fixture\n", encoding="utf8")
    result = subprocess.run([sys.executable, str(root / "orchestrator.py"), "--help"],
                            capture_output=True, text=True, timeout=30,
                            env=dict(os.environ, TMDB_KEY=KEY, PEOPLE_CONFIG_DIR=str(tmp_path)))
    assert result.returncode == 0 and "--stop-after" in result.stdout
    assert KEY not in result.stdout + result.stderr


def test_guarded_unicode_output_is_utf8_even_with_an_ascii_parent_environment():
    import subprocess
    import sys
    label = "Person F\u00e9lix \u9ad8\u9ea5"
    code = "from create_people_posters.people_diagnostics import protect_cli; protect_cli(); print(" + repr(label) + ")"
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, timeout=30,
                            env=dict(os.environ, PYTHONIOENCODING="ascii", PYTHONPATH=str(root)))
    assert result.returncode == 0
    assert result.stdout.decode("utf8").strip() == label
