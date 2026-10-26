"""Offline regression coverage for retained batch failures and retries."""
import io
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import pytest
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from create_people_posters.people_diagnostics import Diagnostic, DiagnosticError, diagnostic_json, register_secret, safe_exception
from create_people_posters.people_failures import failure_boundary, failure_record
from people_batch_safety import IncompleteBatchError, assert_batch_ready


@pytest.mark.parametrize("exception,operation,category,retryable", [
    (requests.Timeout("private request"), "person_details", "network_api", True),
    (MemoryError("private data"), "model_inference", "resource_exhaustion", True),
    (PermissionError("private data"), "output_write", "filesystem", True),
    (FileExistsError("private data"), "checkpoint_reuse", "filesystem", False),
    (OSError("private data"), "image_decode", "image_decode", False),
    (ValueError("private data"), "model_inference", "model_inference", True),
    (TypeError("private data"), "preprocess", "unexpected_exception", True),
    (RuntimeError("private data"), "person_details", "unexpected_exception", True),
])
def test_failure_classification(exception, operation, category, retryable):
    record = failure_record(exception, operation, "15370")
    assert (record["category"], record["retryable"]) == (category, retryable)
    assert record["exception_type"].endswith(type(exception).__name__)
    assert not record["permanent_person_failure"]
    assert "private" not in diagnostic_json(record)
    assert failure_record(exception, operation, "15370")["correlation_id"] == record["correlation_id"]
    assert record["correlation_id"] in safe_exception(exception)


@pytest.mark.parametrize("status,category,retryable", [
    (404, "missing_person", False), (429, "network_api", True), (503, "network_api", True),
    (401, "network_api", False),
])
def test_http_status_and_correlation_preserved(status, category, retryable):
    kind = "client_error" if status == 404 else "rate_limit" if status == 429 else "server_error" if status == 503 else "authentication"
    correlation = "b2fbc943a64c46f6bd14ab342ffe6b00"
    diagnostic = Diagnostic("TMDB", "person_details", kind, status, retryable, "/3/person/{person_id}", correlation)
    record = failure_record(DiagnosticError(diagnostic), "person_details", "15370")
    assert (record["category"], record["retryable"], record["correlation_id"]) == (category, retryable, correlation)
    assert record["permanent_person_failure"] == (status == 404)


def test_safe_chain_locations_and_stage_survive_outer_catch():
    secret = "NOT_A_REAL_PIPELINE_SECRET"
    register_secret(secret)
    try:
        with failure_boundary("preprocess", "Natachai.jpg"):
            try:
                raise TypeError("https://user:" + secret + "@example.test/path?api_key=" + secret)
            except TypeError as cause:
                raise RuntimeError({"request": secret}) from cause
    except RuntimeError as error:
        record = failure_record(error, "model_inference", "outer")
    assert record["operation"] == "preprocess"
    assert record["cause_chain"] == ["builtins.RuntimeError", "builtins.TypeError"]
    assert record["locations"] and all(set(row) == {"file", "function", "line"} for row in record["locations"])
    assert secret not in diagnostic_json(record) and "example.test" not in diagnostic_json(record)


def test_onnx_allocator_failure_is_resource_exhaustion_without_provider_text():
    failure = type("RuntimeException", (RuntimeError,), {"__module__": "onnxruntime.capi.onnxruntime_pybind11_state"})
    error = failure("BFCArena::AllocateRawInternal failed to allocate memory; private tensor contents")
    record = failure_record(error, "model_inference", "Natachai.jpg")
    assert record["category"] == "resource_exhaustion" and record["retryable"]
    assert "private tensor" not in diagnostic_json(record)


@pytest.fixture
def downloader(monkeypatch, tmp_path):
    import tmdbapis
    from dotenv import load_dotenv
    import dotenv
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **kw: None)
    api = SimpleNamespace(calls=[], searches=[])
    def person(identifier, *, partial):
        api.calls.append((identifier, partial))
        if identifier == 15370 and getattr(api, "error", None):
            raise api.error
        return SimpleNamespace(id=identifier, name="Person " + str(identifier), profile_url="https://image.tmdb.org/t/p/original/test.jpg")
    def search(value):
        api.searches.append(value)
        return []
    api.person, api.people_search = person, search
    monkeypatch.setattr(tmdbapis, "TMDbAPIs", lambda *a, **kw: api)
    monkeypatch.setenv("TMDB_KEY", "NOT_A_REAL_LOOKUP_TEST_KEY")
    monkeypatch.setenv("PEOPLE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("POSTER_DIR", str(tmp_path / "posters"))
    monkeypatch.setenv("PEOPLE_WORKSPACE_MODE", "batch")
    monkeypatch.setenv("PEOPLE_PUBLISH_MODE", "local_git")
    namespace = runpy.run_path(str(ROOT / "tmdb_people.py"), run_name="test_downloader")
    yield SimpleNamespace(api=api, ns=namespace, globals=namespace["run_people"].__globals__, root=tmp_path)
    # The CLI installs its own logging handlers; release them for Windows tmpdir cleanup.
    import logging
    for handler in logging.getLogger().handlers[:]:
        if isinstance(handler, logging.FileHandler) and str(tmp_path) in handler.baseFilename:
            handler.close()
            logging.getLogger().removeHandler(handler)


def test_sdk_value_error_never_searches_numeric_id_or_records_permanent_miss(downloader, monkeypatch):
    downloader.api.error = ValueError("Unsupported SDK endpoint")
    monkeypatch.setitem(downloader.globals, "save_image", lambda *a, **kw: "downloaded")
    summary = downloader.ns["run_people"](["15370|Gretchen Mol", "3499270|Natachai Boonprasert"])
    assert summary["failed"] == 1 and summary["downloaded"] == 1 and not summary["complete"]
    assert downloader.api.calls == [(15370, None), (3499270, None)]
    assert downloader.api.searches == []
    failure = summary["files"][0]["failure"]
    assert failure["category"] == "unexpected_exception" and failure["retryable"]
    assert not failure["permanent_person_failure"]
    assert json.loads((downloader.root / "logs/tmdb_people.json").read_text())["exit_code"] == 1


def test_checkpoint_reuse_does_not_call_tmdb_or_rewrite_preserved_source(downloader):
    source = downloader.root / "people_dirs/original/Fuka Izumi.jpg"
    source.parent.mkdir(parents=True)
    Image.new("RGB", (12, 18)).save(source)
    before = source.read_bytes(), source.stat().st_mtime_ns
    (downloader.root / "tmdb_identities.json").write_text(json.dumps({"Fuka Izumi": "3309472"}))
    summary = downloader.ns["run_people"](["3309472|Fuka Izumi"])
    assert summary["complete"] and summary["reused"] == 1 and not downloader.api.calls
    assert (source.read_bytes(), source.stat().st_mtime_ns) == before


def test_name_search_depth_and_per_match_failure_isolation_are_preserved(downloader, monkeypatch):
    class Results:
        def __len__(self):
            return 2
        def __getitem__(self, index):
            if index == 0:
                raise ValueError("bad first match")
            return SimpleNamespace(id=42, name="Chosen person", profile_url="public")
    downloader.api.people_search = lambda value: Results()
    monkeypatch.setitem(downloader.globals, "save_image", lambda *a, **kw: "downloaded")
    assert downloader.ns["process_item"]("Person query")[0]["status"] == "not_selected"
    monkeypatch.setitem(downloader.globals, "PERSON_DEPTH", 2)
    summary = downloader.ns["run_people"](["Person query"])
    assert summary["failed"] == 1 and summary["downloaded"] == 1
    assert summary["files"][0]["failure"]["operation"] == "search_result"


def test_download_retains_raw_input_and_exclusive_write_protects_bytes(downloader, monkeypatch):
    from create_people_posters import people_http
    buffer = io.BytesIO()
    Image.new("RGB", (12, 18)).save(buffer, "JPEG")
    content = buffer.getvalue()
    monkeypatch.setattr(people_http, "image_response", lambda *a, **kw: SimpleNamespace(content=content, close=lambda: None))
    summary = downloader.ns["run_people"](["15370|Gretchen Mol"])
    assert summary["complete"] and summary["downloaded"] == 1
    raw = downloader.root / "input/tmdb/Gretchen Mol-15370.jpg"
    assert raw.read_bytes() == content
    with pytest.raises(FileExistsError):
        downloader.ns["write_preserved"](raw, b"different")
    assert raw.read_bytes() == content


def test_missing_profile_is_explicit_and_blocks_batch(downloader, monkeypatch):
    monkeypatch.setitem(downloader.globals, "save_image", lambda *a, **kw: "missing_profile")
    summary = downloader.ns["run_people"](["15370|Gretchen Mol"])
    assert summary["failed"] == 1 and summary["files"][0]["failure"]["category"] == "missing_profile"
    with pytest.raises(IncompleteBatchError):
        assert_batch_ready(downloader.root)


def test_legacy_done_marker_cannot_hide_unresolved_explicit_selection(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"explicit_people_list": True}))
    (tmp_path / "people_list.txt").write_text("3309472|Fuka Izumi\n15370|Gretchen Mol\n")
    (tmp_path / "tmdb_identities.json").write_text(json.dumps({"Fuka Izumi": "3309472"}))
    (tmp_path / ".orch").mkdir()
    (tmp_path / ".orch/tmdb.done.json").write_text("{}")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(IncompleteBatchError):
        assert_batch_ready(tmp_path)
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.parametrize("name", ["tmdb_people", "remove_bg_birefnet"])
def test_partial_receipt_blocks_publication_even_with_old_success_checkpoint(tmp_path, name):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / (name + ".json")).write_text(json.dumps({"failed": 1, "exit_code": 1, "outcome": "partial_failure"}))
    with pytest.raises(IncompleteBatchError):
        assert_batch_ready(tmp_path)


def test_every_explicit_identity_requires_all_seven_local_styles(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"explicit_people_list": True}))
    (tmp_path / "people_list.txt").write_text("15370|Gretchen Mol\n")
    (tmp_path / "tmdb_identities.json").write_text(json.dumps({"Gretchen Mol": "15370"}))
    styles = ("bw", "diiivoy", "diiivoycolor", "rainier", "original", "signature", "transparent")
    for style in styles[:-1]:
        path = tmp_path / "people_dirs" / style / "G/Images/Gretchen Mol.jpg"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"poster")
    with pytest.raises(IncompleteBatchError, match="seven"):
        assert_batch_ready(tmp_path)
    path = tmp_path / "people_dirs/transparent/G/Images/Gretchen Mol.png"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"cutout")
    assert_batch_ready(tmp_path)
    (tmp_path / "people_list.txt").write_text("15370|Different Alias\n")
    with pytest.raises(IncompleteBatchError):
        assert_batch_ready(tmp_path)


def test_retry_preserves_historical_correlations(downloader, monkeypatch):
    downloader.api.error = TypeError("SDK failure")
    first = downloader.ns["run_people"](["15370|Gretchen Mol"])
    correlation = first["files"][0]["failure"]["correlation_id"]
    downloader.api.error = None
    monkeypatch.setitem(downloader.globals, "save_image", lambda *a, **kw: "downloaded")
    assert downloader.ns["run_people"](["15370|Gretchen Mol"])["complete"]
    history = list((downloader.root / "logs/history").glob("tmdb_people-*.json"))
    assert len(history) == 1 and correlation in history[0].read_text()


def test_publisher_prepare_refuses_partial_batch_before_reading_ledger(tmp_path):
    from publish_people_github import prepare
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs/remove_bg_birefnet.json").write_text(json.dumps({"failed": 1, "exit_code": 1}))
    with pytest.raises(IncompleteBatchError):
        prepare(tmp_path, "existing-batch", None, "master")


def test_pillow_new_and_legacy_pixel_apis_are_compatible(monkeypatch, tmp_path):
    monkeypatch.setenv("PEOPLE_CONFIG_DIR", str(tmp_path))
    namespace = runpy.run_path(str(ROOT / "audit_people_images.py"), run_name="test_audit")
    flattened = namespace["flattened_pixels"]
    assert flattened(SimpleNamespace(get_flattened_data=lambda: (1, 2), getdata=lambda: pytest.fail("Deprecated API called"))) == (1, 2)
    assert flattened(SimpleNamespace(getdata=lambda: (1, 2))) == (1, 2)
    for color, expected in [((50, 50, 50), "Grayscale"), ((50, 80, 50), "Grayscale"), ((50, 81, 50), "RGB")]:
        image = tmp_path / "test.png"
        Image.new("RGB", (2, 2), color).save(image)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            assert namespace["determine_image_mode"](image) == expected
