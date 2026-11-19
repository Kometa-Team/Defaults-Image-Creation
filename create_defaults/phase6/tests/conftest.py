"""Local fixture transport is the only allowed destination."""
import pytest


def pytest_configure(config):
    config.addinivalue_line('markers', 'cohort: native eight-request pilot and its rejection boundaries')


@pytest.fixture(autouse=True)
def no_http(monkeypatch):
    import requests
    def forbidden(*args, **kwargs):
        raise AssertionError('Phase 6 pilot must not access HTTP')
    monkeypatch.setattr(requests.Session, 'request', forbidden)
