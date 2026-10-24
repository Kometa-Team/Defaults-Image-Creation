"""Real TMDbAPIs initialization with fixed offline HTTP responses, never credentials."""
import copy
import json
from pathlib import Path
import runpy
from urllib.parse import urlsplit

import pytest
import requests

from create_people_posters import people_diagnostics as secure
from create_people_posters import people_http as http

KEY = "NOT_A_REAL_SDK_CONFIGURATION_KEY"
TOKEN = "NOT_A_REAL_SDK_CONFIGURATION_TOKEN"
CONFIG = {
    "images": {
        "base_url": "http://image.tmdb.org/t/p/",
        "secure_base_url": "https://image.tmdb.org/t/p/",
        **{name + "_sizes": ["original"] for name in
           ("backdrop", "logo", "poster", "profile", "still")},
    },
    "change_keys": ["images"],
}
PAYLOADS = {
    "/3/configuration": CONFIG,
    "/3/configuration/countries": [{"iso_3166_1": "US", "english_name": "United States of America", "native_name": "United States"}],
    "/3/configuration/jobs": [{"department": "Acting", "jobs": ["Actor"]}],
    "/3/configuration/languages": [{"iso_639_1": "en", "english_name": "English", "name": "English"}],
    "/3/configuration/primary_translations": ["en-US"],
    "/3/configuration/timezones": [{"iso_3166_1": "US", "zones": ["America/New_York"]}],
}
RESOURCES = ("countries", "jobs", "languages", "primary_translations", "timezones")
PATHS = tuple(PAYLOADS)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Live network forbidden", pytrace=False)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


@pytest.fixture
def sdk_class():
    # Required at execution, never an importorskip. Only the mandatory security
    # executor needs this dependency; legacy collect-only jobs stay unchanged.
    from tmdbapis import TMDbAPIs
    return TMDbAPIs


class Transport:
    def __init__(self, overrides=None, status=200):
        self.payloads = copy.deepcopy(PAYLOADS)
        self.payloads.update(overrides or {})
        self.status = status
        self.calls = []
        self.responses = []

    def get(self, url, **kwargs):
        path = urlsplit(url).path
        assert path in PAYLOADS, "Unexpected SDK route"
        self.calls.append((path, kwargs))
        response = requests.Response()
        response.status_code = self.status
        response.reason = "OK" if self.status == 200 else "Unauthorized"
        response.headers = {}
        response._content = json.dumps(self.payloads[path]).encode("utf8")
        response._content_consumed = True
        self.responses.append(response)
        return response

    def close(self):
        for response in self.responses:
            response.close()


@pytest.mark.parametrize("bearer", [False, True], ids=["v3-key", "read-token"])
def test_real_sdk_initialization_and_all_configuration_resources(bearer, capsys, caplog, sdk_class):
    transport = Transport()
    with http.SecureTMDBSession(KEY, read_token=TOKEN if bearer else "", transport=transport) as session:
        sdk = sdk_class(KEY, language="en", session=session)
        config = sdk.configuration()
        assert config.secure_base_image_url == CONFIG["images"]["secure_base_url"]
        assert config.countries[0].iso_3166_1 == "US"
        assert config.languages[0].iso_639_1 == "en"
        assert config.departments[0].department == "Acting"
        assert config.primary_translations == ["en-US"]
        assert config.timezones[0].zones == ["America/New_York"]
        assert [path for path, _ in transport.calls] == list(PATHS)
        assert sdk._api.configuration_get_api_configuration() == CONFIG
        for resource in RESOURCES:
            assert getattr(sdk._api, "configuration_get_" + resource)() == PAYLOADS["/3/configuration/" + resource]
    for _, args in transport.calls:
        assert args["allow_redirects"] is False
        if bearer:
            assert "api_key" not in args["params"]
            assert args["headers"]["Authorization"] == "Bearer " + TOKEN
        else:
            assert args["params"]["api_key"] == KEY
            assert "Authorization" not in args["headers"]
    output = capsys.readouterr()
    assert all(secret not in output.out + output.err + caplog.text for secret in (KEY, TOKEN))


@pytest.mark.parametrize("path", PATHS, ids=["details", *RESOURCES])
@pytest.mark.parametrize("invalid", [None, True, 17, "invalid", {}, {"success": False, "status_message": KEY},
    {"status_code": 7, "status_message": KEY}, {"errors": [KEY]}],
    ids=["null", "boolean", "number", "string", "empty-object", "provider-failure", "provider-code", "provider-errors"])
def test_real_sdk_rejects_malformed_and_provider_configuration_errors(path, invalid, sdk_class):
    transport = Transport({path: invalid})
    with http.SecureTMDBSession(KEY, read_token=TOKEN, transport=transport) as session:
        with pytest.raises(secure.DiagnosticError) as captured:
            sdk_class(KEY, language="en", session=session)
    error = captured.value
    assert error.diagnostic.category == "invalid_response" and not error.diagnostic.retryable
    assert error.__context__ is None and error.__cause__ is None
    assert KEY not in str(error) + repr(error) and TOKEN not in str(error) + repr(error)
    assert transport.calls[-1][0] == path


@pytest.mark.parametrize("resource", RESOURCES)
@pytest.mark.parametrize("row", [None, 17, {}, {"errors": [KEY]}],
                         ids=["null-row", "wrong-row-type", "missing-fields", "provider-error-row"])
def test_configuration_arrays_require_resource_specific_members(resource, row):
    path = "/3/configuration/" + resource
    with http.SecureTMDBSession(KEY, transport=Transport({path: [row]})) as session:
        with pytest.raises(secure.DiagnosticError):
            session.get(http.TMDB_ORIGIN + path)


@pytest.mark.parametrize("path", PATHS, ids=["details", *RESOURCES])
@pytest.mark.parametrize("status", [401, 403])
def test_configuration_authentication_errors_are_never_success(path, status):
    transport = Transport(status=status)
    with http.SecureTMDBSession(KEY, read_token=TOKEN, transport=transport) as session:
        with pytest.raises(secure.DiagnosticError) as captured:
            session.get(http.TMDB_ORIGIN + path)
    assert captured.value.diagnostic.category == "authentication"
    assert captured.value.diagnostic.status == status and not captured.value.diagnostic.retryable
    assert len(transport.calls) == 1


@pytest.mark.parametrize("resource", RESOURCES)
def test_empty_configuration_resource_arrays_are_valid(resource):
    path = "/3/configuration/" + resource
    with http.SecureTMDBSession(KEY, transport=Transport({path: []})) as session:
        assert session.get(http.TMDB_ORIGIN + path).json() == []


@pytest.mark.parametrize("field", ["images", "change_keys", "base_url", "secure_base_url",
    "backdrop_sizes", "logo_sizes", "poster_sizes", "profile_sizes", "still_sizes"])
def test_configuration_details_require_valid_nested_field_types(field, sdk_class):
    config = copy.deepcopy(CONFIG)
    (config if field in {"images", "change_keys"} else config["images"])[field] = 17
    with http.SecureTMDBSession(KEY, transport=Transport({"/3/configuration": config})) as session:
        with pytest.raises(secure.DiagnosticError):
            sdk_class(KEY, language="en", session=session)


@pytest.mark.parametrize("path", ["/3/person/123", "/3/person/123/images", "/3/search/person", "/3/person/popular"])
@pytest.mark.parametrize("payload", [[], {"errors": [KEY]}, {"success": False, "status_message": KEY},
    {"status_code": 7, "status_message": KEY}], ids=["array", "errors", "failure", "provider-code"])
def test_configuration_array_support_does_not_relax_person_or_search_validation(path, payload):
    class PersonTransport(Transport):
        def get(self, url, **kwargs):
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps(payload).encode("utf8")
            response._content_consumed = True
            return response
    with http.SecureTMDBSession(KEY, transport=PersonTransport()) as session:
        with pytest.raises(secure.DiagnosticError):
            session.get(http.TMDB_ORIGIN + path)


def test_orchestrator_tmdb_module_initializes_real_sdk_in_temporary_workspace(monkeypatch, tmp_path, sdk_class):
    # Exercise exactly the constructor used by the orchestrator's TMDB child.
    # Its real config, workspace, people list and checkpoints are never opened.
    transport = Transport()
    session_class = http.SecureTMDBSession
    monkeypatch.setattr(http, "SecureTMDBSession", lambda key: session_class(key, read_token="", transport=transport))
    monkeypatch.setenv("TMDB_KEY", KEY)
    monkeypatch.setenv("PEOPLE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("POSTER_DIR", str(tmp_path / "posters"))
    root = Path(__file__).resolve().parents[1]
    # A non-main name imports/initializes the actual script without processing people.
    namespace = runpy.run_path(str(root / "tmdb_people.py"), run_name="offline_tmdb_configuration")
    assert isinstance(namespace["TMDb"], sdk_class)
    assert namespace["TMDb"].configuration().primary_translations == ["en-US"]
    assert [path for path, _ in transport.calls] == list(PATHS)
    assert not (tmp_path / "posters").exists() or not list((tmp_path / "posters").iterdir())
