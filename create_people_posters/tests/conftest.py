"""Keep offline People tests independent of runner credentials and test order."""
import os

import pytest

from create_people_posters import people_diagnostics as secure


@pytest.fixture(autouse=True)
def isolated_people_credentials(monkeypatch):
    # Runtime redaction remains strict, including short configured values.
    # Each test registers its own dummy values instead of inheriting a previous
    # test's registry or a developer/CI runner's private authentication settings.
    monkeypatch.setattr(secure, "_variants", set())
    for name in tuple(os.environ):
        # Git's numbered KEY/VALUE pairs describe process configuration, not
        # credential values. Removing only KEY would corrupt GIT_CONFIG_COUNT.
        if name.upper().startswith("GIT_CONFIG_KEY_"):
            continue
        if secure.sensitive_key(name) or secure._ENV_KEY.search(name):
            monkeypatch.delenv(name, raising=False)
