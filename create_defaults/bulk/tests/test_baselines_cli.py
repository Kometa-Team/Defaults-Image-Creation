from copy import deepcopy
import json
from pathlib import Path
import tempfile

import pytest

from create_defaults.bulk.__main__ import main
from create_defaults.bulk.baselines import BASE, historical_sources, verify_current, verify_historical
from create_defaults.bulk.common import BulkError
from create_defaults.validation_manifest import load_manifest, validate_manifest


ROOT = BASE.parents[1]


def test_historical_and_corrected_current_baselines_keep_separate_source_checks():
    historical = load_manifest(ROOT / "fixtures/effective-jobs-en-cmap-compat.json.gz")
    current = verify_current()
    assert verify_historical(historical)
    with pytest.raises(ValueError, match="source changed"):
        validate_manifest(historical)
    assert historical["sha256"] != current["sha256"]
    changes = [(old, new) for old, new in zip(historical["jobs"], current["jobs"]) if old["parameters"] != new["parameters"]]
    assert len(changes) == 1
    old, new = changes[0]
    assert old["parameters"]["logo"] == new["parameters"]["logo"]
    assert old["parameters"]["out_name"] == "Death in Paradise (2911)"
    assert new["parameters"]["out_name"] == "Death in Paradise (2011)"


def test_unrelated_source_edits_cannot_hide_in_historical_reconstruction(tmp_path):
    source = tmp_path / "create_default_posters.ps1"
    source.write_text((ROOT / source.name).read_text(encoding="utf-8-sig") + "\n# unexpected edit\n", encoding="utf-8")
    with pytest.raises(BulkError, match="differs"):
        with historical_sources(tmp_path):
            pytest.fail("Unexpected source accepted")


def test_original_font_and_asset_checks_not_removed():
    historical = load_manifest(ROOT / "fixtures/effective-jobs-en-cmap-compat.json.gz")
    historical["fonts"]["fonts/Comfortaa-Medium.ttf"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="font changed"):
        verify_historical(historical)


def test_minimal_cli_lists_and_plans_without_rendering(capsys, tmp_path):
    assert main(["list-categories"]) == 0
    assert "Genre" in json.loads(capsys.readouterr().out)["categories"]
    assert main(["list-languages"]) == 0
    assert len(json.loads(capsys.readouterr().out)["languages"]) == 11
    examples = BASE.parent / "examples"
    files = sorted(str(path) for path in examples.glob("*.yml") if path.name != "profiles.yml")
    manifest = tmp_path / "plan.json"
    assert main(["plan", "--definitions", *files, "--profiles", str(examples / "profiles.yml"), "--category", "All", "--manifest", str(manifest)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert len(result["jobs"]) == 4 and manifest.is_file()
    assert not list(tmp_path.glob("*.jpg"))
