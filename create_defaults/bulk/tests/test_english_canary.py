"""Canary scope stays bounded even if language, destination or dependency drifts."""
from copy import deepcopy

import pytest

from create_defaults.bulk.common import BulkError
from create_defaults.bulk.e_canary import SELECTION, prepare, validate_scope


@pytest.fixture
def jobs():
    values = [{"id": "job." + key, "poster_id":key, "kind":"poster", "language":"en", "remote_relative":path,
               "local_relative":"defaults-en/" + path, "dependencies":[]} for key,path in SELECTION.items()]
    parent = next(j for j in values if j["poster_id"] == "year.year-2020.83bfe96a")
    child = next(j for j in values if j["poster_id"] == "year.year-best-2020.85b6933b")
    child["dependencies"] = [{"input":"logo", "job_id":parent["id"], "sha256":"a"*64}]
    return values


@pytest.mark.parametrize("field,value", [("language","fr"), ("kind","overlay"),
    ("remote_relative",None), ("remote_relative","genre/Action & adventure.jpg"),
    ("local_relative","defaults-fr/genre/Action & Adventure.jpg")])
def test_rejects_scope_drift(jobs, field, value):
    target = next(j for j in jobs if j["poster_id"] == "genre.genre-action-adventure.96dd0142")
    target[field] = value
    with pytest.raises(BulkError, match="scope|English|Unsafe"):
        validate_scope(jobs)


def test_rejects_added_artwork_or_missing_verified_parent(jobs):
    validate_scope(jobs)
    with pytest.raises(BulkError):
        validate_scope(jobs + [deepcopy(jobs[0])])
    child = next(j for j in jobs if j["poster_id"] == "year.year-best-2020.85b6933b")
    child["dependencies"][0]["sha256"] = None
    with pytest.raises(BulkError, match="parent"):
        validate_scope(jobs)


def test_preparation_refuses_unscoped_output_root(tmp_path):
    with pytest.raises(BulkError, match="fresh child"):
        prepare(tmp_path / "outside-isolated-canary-area")
    assert not (tmp_path / "outside-isolated-canary-area").exists()
