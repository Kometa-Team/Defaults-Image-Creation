"""Exercise the actual inline API helpers shipped to all seven repositories."""

import ast
import io
import json
from pathlib import Path
from unittest.mock import Mock
import urllib.error
import urllib.request

import pytest
import yaml


SOURCES = Path(__file__).resolve().parents[2] / "ci" / "people_readme"
TARGETS = json.loads((SOURCES / "targets.json").read_text())


def workflow(repo):
    return yaml.load((SOURCES / "workflows" / (repo + ".yml")).read_text(), Loader=yaml.BaseLoader)


def api_functions(repo):
    for step in workflow(repo)["jobs"]["Update-Readmes"]["steps"]:
        source = step.get("run", "")
        if source.startswith("python - <<'PY'\n"):
            source = source.split("\n", 1)[1].rsplit("\nPY", 1)[0]
            module = ast.parse(source)
            # Compile the complete step too, including the untouched tree and
            # commit logic, without performing network requests.
            compile(module, str(SOURCES / repo), "exec")
            node = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "api")
            scope = {"json": json, "urllib": urllib, "token": "offline-placeholder", "repo": "test/repo"}
            exec(compile(ast.Module(body=[node], type_ignores=[]), "workflow-api", "exec"), scope)
            yield scope["api"]


@pytest.mark.parametrize("repo", TARGETS)
def test_all_workflows_keep_triggers_styles_and_correlate_runs(repo):
    doc = workflow(repo)
    assert set(doc["on"]) == {"push", "workflow_dispatch"}
    assert doc["on"]["workflow_dispatch"]["inputs"]["batch_id"]["required"] == "false"
    assert "README batch {0}" in doc["run-name"]
    steps = doc["jobs"]["Update-Readmes"]["steps"]
    for step in steps:
        if "TARGET_REF" in step.get("env", {}):
            assert step["env"]["TARGET_REF"] == "${{ github.ref_name }}"
    generate = next(step["run"] for step in steps if step["name"] == "Run Update Readmes")
    style = repo.removeprefix("People-Images-")
    assert ('-s "' + style + '"') in generate if repo != "People-Images" else "-s" not in generate
    assert len(list(api_functions(repo))) == 2


def http_error(code, headers=None):
    return urllib.error.HTTPError("https://api.github.com/repos/test/repo", code, "offline", headers or {}, io.BytesIO(b"temporary"))


@pytest.mark.parametrize("repo", TARGETS)
@pytest.mark.parametrize("code,headers", [(429, {}), (500, {}), (502, {}), (503, {}), (504, {}),
                                          (403, {"X-RateLimit-Remaining": "0", "Retry-After": "120"})])
def test_internal_transient_retries_succeed(repo, code, headers, monkeypatch):
    for api in api_functions(repo):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"sha":"published"}'
        request = Mock(side_effect=[http_error(code, headers), response])
        delays = []
        monkeypatch.setattr(urllib.request, "urlopen", request)
        monkeypatch.setattr("time.sleep", delays.append)
        assert api("/repos/test/repo/git/trees") == {"sha": "published"}
        assert request.call_count == 2
        assert delays == [120 if code == 403 else 60 if code == 429 else 1]
        assert request.call_args.kwargs["timeout"] == 90


@pytest.mark.parametrize("code", [401, 403, 404, 409, 422])
def test_permanent_errors_are_not_retried(code, monkeypatch):
    for api in api_functions("People-Images"):
        request = Mock(side_effect=http_error(code))
        monkeypatch.setattr(urllib.request, "urlopen", request)
        monkeypatch.setattr("time.sleep", lambda _: pytest.fail("permanent error retried"))
        with pytest.raises(urllib.error.HTTPError):
            api("/repos/test/repo/git/trees")
        assert request.call_count == 1


@pytest.mark.parametrize("error", [lambda: http_error(503), lambda: urllib.error.URLError("offline"),
                                   lambda: TimeoutError(), lambda: json.JSONDecodeError("incomplete", "", 0)])
def test_internal_retries_exhaust_with_failure_marker(error, monkeypatch, capsys):
    for api in api_functions("People-Images"):
        request = Mock(side_effect=lambda *a, **k: (_ for _ in ()).throw(error()))
        delays = []
        monkeypatch.setattr(urllib.request, "urlopen", request)
        monkeypatch.setattr("time.sleep", delays.append)
        with pytest.raises(SystemExit, match="Temporary GitHub API failure"):
            api("/repos/test/repo/git/trees")
        assert request.call_count == 4
        assert delays == [1, 2, 4]
        assert "README_TRANSIENT_API_ERROR" in capsys.readouterr().out


def test_excessive_rate_limit_delay_fails_without_sleeping(monkeypatch):
    for api in api_functions("People-Images"):
        request = Mock(side_effect=http_error(429, {"Retry-After": "600"}))
        monkeypatch.setattr(urllib.request, "urlopen", request)
        monkeypatch.setattr("time.sleep", lambda _: pytest.fail("unbounded retry delay"))
        with pytest.raises(SystemExit):
            api("/repos/test/repo/git/trees")
        assert request.call_count == 1


@pytest.mark.parametrize("repo", TARGETS)
def test_generator_links_use_actual_repository_and_branch(repo, tmp_path, monkeypatch):
    steps = workflow(repo)["jobs"]["Update-Readmes"]["steps"]
    source = next(s["run"] for s in steps if s["name"] == "Run Update Readmes")
    source = source.split("python - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    root = tmp_path / "readmeinput"
    root.mkdir()
    readme = root / "README.md"
    readme.write_text(f"[Ada](https://raw.githubusercontent.com/Kometa-Team/{repo}/master/A/Images/Ada%20Lovelace.jpg)")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TARGET_REPO", "test-owner/private-sandbox")
    monkeypatch.setenv("TARGET_REF", "test/images")
    exec(compile(source, "generator-links", "exec"), {})
    assert readme.read_text() == "[Ada](https://raw.githubusercontent.com/test-owner/private-sandbox/test/images/A/Images/Ada%20Lovelace.jpg)"


def test_sandbox_copy_preserves_correlation_contract(monkeypatch):
    import base64
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import sandbox_people_github as sandbox

    content = (SOURCES / "workflows" / "People-Images-bw.yml").read_bytes()
    monkeypatch.setattr(sandbox, "gh", lambda *a: json.dumps({"content": base64.b64encode(content).decode()}))
    copied_bytes = sandbox.copied_readme_workflow("bw")
    copied = yaml.load(copied_bytes, Loader=yaml.BaseLoader)
    assert yaml.safe_load(copied_bytes)["on"]["workflow_dispatch"]["inputs"]["batch_id"]["required"] is False
    assert copied["on"]["workflow_dispatch"]["inputs"]["batch_id"]["type"] == "string"
    assert "README batch {0}" in copied["run-name"]
    assert not any("discord" in step.get("uses", "") for step in copied["jobs"]["Update-Readmes"]["steps"])
