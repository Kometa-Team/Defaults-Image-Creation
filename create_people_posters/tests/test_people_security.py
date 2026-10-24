"""Offline security canaries: failures never echo their credential-bearing input."""
from __future__ import annotations

import base64
import csv
import io
import json
import logging
import os
import re
from pathlib import Path
import subprocess
import sys
import traceback
from urllib.parse import quote
import zipfile

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from create_people_posters import people_diagnostics as secure
from create_people_posters import people_http as http


def canary(label):
    return "NOT_A_REAL_CREDENTIAL_CANARY_" + label + "_END"


def contains_no_secret(value, *secrets):
    value = value.decode("utf8", "replace") if isinstance(value, bytes) else value
    for secret in secrets:
        variants = {secret, quote(secret, safe=""), base64.b64encode(secret.encode()).decode(),
                    base64.urlsafe_b64encode(secret.encode()).decode(), secret.encode().hex()}
        if any(v in value for v in variants):
            pytest.fail("Credential containment check failed", pytrace=False)


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch):
    monkeypatch.setattr(secure, "_variants", set())
    for name in tuple(os.environ):
        if secure.sensitive_key(name) or secure._ENV_KEY.search(name):
            monkeypatch.delenv(name, raising=False)
    def forbidden(*args, **kwargs):
        pytest.fail("Security tests must not contact a live provider", pytrace=False)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


@pytest.mark.parametrize("case", ["query", "ssl", "timeout", "reset", "429", "500", "authentication",
                                 "traceback", "chain", "repr", "percent", "mixed", "bearer", "basic", "userinfo"])
def test_free_form_exception_and_credential_representations_are_contained(case):
    secret = canary(case)
    secure.register_secret(secret)
    url = "https://api.themoviedb.org/3/search/person?api_key=" + secret + "&query=Person"
    if case == "ssl":
        text = str(requests.exceptions.SSLError("EOF occurred in violation of protocol: " + url))
    elif case == "timeout":
        text = str(requests.exceptions.ConnectTimeout("Connection timeout: " + url))
    elif case == "reset":
        text = str(ConnectionResetError("Connection reset: " + url))
    elif case in {"429", "500", "authentication"}:
        text = str(requests.exceptions.HTTPError("HTTP " + case + ": " + url))
    elif case in {"traceback", "chain"}:
        try:
            try:
                raise requests.exceptions.SSLError(url)
            except requests.RequestException as error:
                if case == "chain":
                    raise RuntimeError("upstream " + url) from error
                raise
        except Exception as error:
            text = "".join(traceback.format_exception(error))
    elif case == "repr":
        text = repr(requests.exceptions.ConnectionError(url))
    elif case == "percent":
        text = quote("https://api.themoviedb.org/3/search/person?api_key=" + secret, safe="")
    elif case == "mixed":
        text = "aPi_KeY=" + secret
    elif case == "bearer":
        text = "Authorization: Bearer " + secret
    elif case == "basic":
        text = "Authorization: Basic " + base64.b64encode(("user:" + secret).encode()).decode()
    elif case == "userinfo":
        text = "https://user:" + secret + "@api.themoviedb.org/3/search/person"
    else:
        text = url
    result = secure.sanitize_text(text)
    contains_no_secret(result, secret)
    assert result and ("api.themoviedb.org" in result or secure.REDACTED in result)


@pytest.mark.parametrize("field", ["api_key", "apikey", "access_token", "refresh_token", "token", "client_secret",
                                  "password", "Authorization", "Cookie", "X-Api-Key", "x-plex-token", "session_id",
                                  "AWS_SECRET_ACCESS_KEY", "api%5Fkey", "google_api_key"])
def test_unknown_secret_field_names_are_redacted_without_a_registered_value(field):
    secret = canary("unregistered")
    value = secure.sanitize_text(field + "=" + secret)
    contains_no_secret(value, secret)
    structured = secure.diagnostic_json({"nested": {field: secret}, "safe": "HTTP 429 retryable"})
    contains_no_secret(structured, secret)
    assert "HTTP 429 retryable" in structured


@pytest.mark.parametrize("encoding", ["raw", "url", "double-url", "base64", "base64url", "hex", "unicode", "json"])
def test_configured_secret_is_removed_under_unrelated_fields(encoding):
    secret = canary("representations") + "+/=?"
    secure.register_secret(secret)
    forms = {"raw": secret, "url": quote(secret, safe=""), "double-url": quote(quote(secret, safe=""), safe=""),
             "base64": base64.b64encode(secret.encode()).decode(), "base64url": base64.urlsafe_b64encode(secret.encode()).decode(),
             "hex": secret.encode().hex(), "unicode": "".join(f"\\u{ord(c):04x}" for c in secret),
             "json": json.dumps(secret)[1:-1]}
    text = secure.diagnostic_json({"ordinary": forms[encoding], "safe": "still useful"})
    contains_no_secret(text, secret)
    if forms[encoding] in text:
        pytest.fail("Encoded credential was emitted", pytrace=False)
    assert "still useful" in text


@pytest.mark.parametrize("method", ["exc_info", "exception", "argument", "repr_argument", "extra"])
def test_final_logging_representation_is_safe_including_exception_formatting(method, tmp_path):
    secret = canary("logging")
    secure.register_secret(secret)
    stream = io.StringIO()
    logger = logging.Logger("security-private", level=logging.DEBUG)
    handler = secure.secure_handler(logging.StreamHandler(stream))
    file_handler = secure.secure_handler(logging.FileHandler(tmp_path / "diagnostic.log", encoding="utf8"))
    logger.addHandler(handler); logger.addHandler(file_handler)
    try:
        raise requests.exceptions.SSLError("https://api.themoviedb.org/3/search/person?api_key=" + secret)
    except Exception as error:
        if method == "exception":logger.exception("TMDB search person failed")
        elif method == "exc_info":logger.error("TMDB search person failed", exc_info=True)
        elif method == "argument":logger.error("TMDB search person failed: %s", error)
        elif method == "repr_argument":logger.error("TMDB search person failed: %r", error)
        else:
            handler.setFormatter(secure.RedactingFormatter(logging.Formatter("%(message)s %(payload)s")))
            logger.error("TMDB search person failed", extra={"payload": {"Authorization": secret}})
    file_handler.close()
    contains_no_secret(stream.getvalue(), secret)
    contains_no_secret((tmp_path / "diagnostic.log").read_bytes(), secret)
    assert "TMDB search person failed" in stream.getvalue()


def test_stream_handles_split_text_and_bytes_and_never_flushes_a_partial_secret():
    secret = canary("split")
    secure.register_secret(secret)
    target = io.StringIO(); stream = secure.RedactingStream(target)
    stream.write("safe endpoint /3/search/person value=")
    stream.write(secret[:19]); stream.flush()
    assert target.getvalue() == ""
    stream.buffer.write(secret[19:].encode() + b"\n")
    contains_no_secret(target.getvalue(), secret)
    assert "/3/search/person" in target.getvalue()
    stream.write(secret[:19]); stream.finish()
    assert target.getvalue().endswith(secure.WITHHELD + "\n")


def test_reports_nested_json_csv_html_and_downloadable_bundle_are_safe(tmp_path):
    secret = canary("reports")
    secure.register_secret(secret)
    value = {"provider": "TMDB", "status": 429, "retryable": True,
             "error": requests.exceptions.HTTPError("url?api_key=" + secret),
             "nested": [{"odd_field": secret, "Authorization": "Bearer " + secret}]}
    json_text = secure.diagnostic_json(value)
    html_text = secure.diagnostic_html(value)
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=["note", "provider"])
    writer.writeheader(); writer.writerow(secure.sanitize_data({"note": secret, "provider": "TMDB"}))
    secure.support_bundle(tmp_path / "support.zip", {"diagnostic": value})
    for report in (json_text, html_text, output.getvalue()):contains_no_secret(report, secret)
    with zipfile.ZipFile(tmp_path / "support.zip") as archive:
        for name in archive.namelist():contains_no_secret(archive.read(name), secret)
    assert json.loads(json_text)["status"] == 429
    assert json.loads(json_text)["retryable"] is True


def test_sanitizer_and_formatter_failure_never_reveal_original_record(monkeypatch):
    secret = canary("failure")
    secure.register_secret(secret)
    def broken(*args, **kwargs):raise RuntimeError(secret)
    monkeypatch.setattr(secure, "_sanitize_text", broken)
    assert secure.sanitize_text(secret) == secure.WITHHELD
    assert re.search(r"correlation_id=[0-9a-f]{32}", secure.WITHHELD)
    record = logging.LogRecord("unit", logging.ERROR, "source.py", 1, secret, (), None)
    assert secure.RedactingFormatter().format(record) == secure.WITHHELD
    class Dangerous:
        def __str__(self):raise AssertionError("Arbitrary diagnostic conversion is prohibited")
        def __repr__(self):raise AssertionError("Arbitrary diagnostic conversion is prohibited")
    assert secure.sanitize_data(Dangerous()) == "[unsupported diagnostic object]"


def test_cli_subprocess_stderr_traceback_and_debug_output_are_safe(tmp_path):
    secret = canary("subprocess")
    code = """
import os,sys,logging
from create_people_posters.people_diagnostics import protect_cli
protect_cli()
logging.basicConfig(level=logging.DEBUG,filename=sys.argv[1])
value=os.environ['TMDB_KEY']
try:raise RuntimeError('https://api.themoviedb.org/3/search/person?api_key='+value)
except Exception:logging.exception('TMDB lookup failed')
sys.stderr.buffer.write(('subprocess stderr token='+value+'\\n').encode())
print('safe HTTP status 429')
raise RuntimeError(value)
"""
    environment = {k: v for k, v in os.environ.items() if not secure.sensitive_key(k) and not secure._ENV_KEY.search(k)}
    environment.update(PYTHONPATH=str(ROOT.parent), TMDB_KEY=secret, PYTHONIOENCODING="utf8")
    log = tmp_path / "child.log"
    child = subprocess.run([sys.executable, "-c", code, str(log)], env=environment, capture_output=True, timeout=30)
    assert child.returncode != 0
    for value in (child.stdout, child.stderr, log.read_bytes()):contains_no_secret(value, secret)
    assert b"safe HTTP status 429" in child.stdout


def test_safe_diagnostic_fields_and_immutable_record_are_preserved():
    diagnostic = secure.Diagnostic("TMDB", "search_person", "tls", retryable=True, endpoint="/3/search/person")
    data = json.loads(secure.diagnostic_json(diagnostic))
    assert data["provider"] == "TMDB" and data["category"] == "tls" and data["retryable"]
    assert data["endpoint"] == "/3/search/person"
    assert secure.Diagnostic.from_dict(data) == diagnostic
    with pytest.raises((AttributeError, TypeError)):diagnostic.category = "forged"
    with pytest.raises(ValueError):secure.Diagnostic.from_dict(data | {"request": "forbidden"})
    assert secure.sanitize_text("HTTP status=429 host=api.themoviedb.org endpoint=/3/search/person") == "HTTP status=429 host=api.themoviedb.org endpoint=/3/search/person"


def test_known_password_is_removed_whole_before_generic_field_tokenization():
    first, last = "NOT_A_REAL_FIRST_PASSWORD_SEGMENT", "NOT_A_REAL_LAST_PASSWORD_SEGMENT"
    secret = first + " , " + last
    secure.register_secret(secret)
    for text in ("password=" + secret, "Authorization: Basic " + secret,
                 "password=" + quote(secret, safe="")):
        result = secure.sanitize_text(text)
        assert first not in result and last not in result


def test_public_signature_style_maps_survive_actual_metadata_writers(tmp_path):
    from create_people_posters.people_workspaces import atomic_json
    from create_people_posters.remove_bg_birefnet import atomic_json as model_json
    repositories = {style: "test-owner/kometa-people-sandbox-" + style for style in
                    ("original", "transparent", "bw", "diiivoy", "diiivoycolor", "rainier", "signature")}
    target = tmp_path / "targets.json"
    value = {"version": 1, "owner": "test-owner", "branch": "master", "repositories": repositories}
    atomic_json(target, value)
    assert json.loads(target.read_text()) == value
    output = {"outputs": {"signature": {"path": "signature/P/Images/Person.jpg", "sha256": "a" * 64}}}
    model_json(tmp_path / "render.json", output)
    assert json.loads((tmp_path / "render.json").read_text()) == output
    # Public style labels are not credentials. A configured credential value
    # remains prohibited even under the same ordinary public label.
    secret = canary("public_style_value")
    secure.register_secret(secret)
    with pytest.raises(ValueError):atomic_json(target, {"repositories": {"signature": secret}})
    assert json.loads(target.read_text()) == value


def test_signed_provider_fields_and_encoded_urls_stay_redacted():
    secret = canary("signed_provider")  # Deliberately unregistered.
    for field in ("X-Amz-Signature", "SharedAccessSignature", "SAS_TOKEN", "API_SIGNATURE"):
        contains_no_secret(secure.diagnostic_json({field: secret}), secret)
    url = "https://example.test/image.jpg?sig=" + secret
    spaced_url = "https://example.test/a%20b.jpg?sig=" + secret
    for value in (url, quote(url, safe=""), spaced_url, quote(spaced_url, safe="")):
        result = secure.sanitize_text(value)
        contains_no_secret(result, secret)
        assert "example.test/" in result
    assert secure.sanitize_text(spaced_url) == "https://example.test/a%20b.jpg"


def test_configured_credential_urls_are_removed_before_normalization():
    secret = "https://example.test/webhook/NOT_A_REAL_PATH_CREDENTIAL?mode=private"
    secure.register_secret(secret)
    for value in (secret, secret.split("?", 1)[0], quote(secret, safe="")):
        result = secure.sanitize_text("upstream=" + value)
        assert "NOT_A_REAL_PATH_CREDENTIAL" not in result
        assert secure.REDACTED in result


def test_query_and_fragment_at_signs_never_become_diagnostic_hosts():
    secret = "not_a_real_hostlike_query_credential"  # Deliberately unregistered.
    for suffix in ("?token=alice@", "#alice@", "?other=alice@"):
        url = "https://example.test" + suffix + secret
        for value in (url, quote(url, safe="")):
            result = secure.sanitize_text(value)
            assert secret.casefold() not in result.casefold()
            assert result == "https://example.test"
    assert secure.sanitize_text("https://alice:password@example.test/path?q=private") == "https://example.test/path"


def test_api_fixture_isolates_ambient_credentials_without_weakening_checkpoints(tmp_path, monkeypatch):
    from test_people_api_orchestrator import isolated
    import orchestrator as orch
    interpreter = r"C:\hostedtoolcache\windows\Python\3.13.16\x64\python.exe"
    # Reproduce a false conflict between an unrelated configured/retained value
    # and a public Windows path. Fixture isolation must remove both sources.
    monkeypatch.setenv("TMDB_KEY", interpreter)
    secure.register_secret(interpreter)
    assert secure.sanitize_text(interpreter) != interpreter
    fixture = isolated.__wrapped__(tmp_path, monkeypatch)
    next(fixture)
    try:
        assert "TMDB_KEY" not in os.environ
        marker = tmp_path / "normal.json"
        value = {"argv": [interpreter, "sync_people_images.py", "--dest_root", r"C:\public\repos"]}
        orch.write_marker(marker, value)
        assert json.loads(marker.read_text()) == value
        secret = canary("checkpoint_rejection")
        secure.register_secret(secret)
        with pytest.raises(ValueError, match="Sensitive data"):
            orch.write_marker(marker, {"argv": [interpreter, secret]})
        assert json.loads(marker.read_text()) == value
        assert not marker.with_suffix(".json.tmp").exists()
    finally:
        next(fixture, None)


def test_short_configured_credentials_still_block_paths_and_hash_metadata(tmp_path):
    from create_people_posters.people_workspaces import atomic_json
    # Deliberately tiny dummy value: test isolation must never become a runtime
    # exemption for short secrets that overlap public paths or content hashes.
    secure.register_secret("x")
    for value in ("C:/public/x/image.png", "00" + "x".encode().hex() + "11"):
        assert secure.sanitize_text(value) != value
        target = tmp_path / "blocked.json"
        with pytest.raises(ValueError, match="Sensitive data"):
            atomic_json(target, {"source": value})
        assert not target.exists()
