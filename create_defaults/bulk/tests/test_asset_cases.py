from copy import deepcopy
from pathlib import Path

import pytest

from create_defaults.bulk import asset_cases
from create_defaults.bulk.case_audit import collisions
from create_defaults.bulk.common import BulkError, confined, fingerprint, sha256
from create_defaults.bulk.config import Config
from create_defaults.bulk.overlays import plan
from create_defaults.bulk.planner import validate_manifest
from create_defaults.bulk.workers import RenderTask


def test_authority_allows_only_git_line_ending_changes(tmp_path, monkeypatch):
    root = tmp_path / 'assets'
    source = root / 'create_default_posters.ps1'
    source.parent.mkdir()
    source.write_bytes(b'Authoritative Name.png\r\n')
    identity = sha256(source)
    monkeypatch.setattr(asset_cases, 'LEDGER', root / 'bulk/catalog/cases.json')
    monkeypatch.setattr(asset_cases, 'ledger', lambda: {'source_ps1_sha256': identity})
    asset_cases.check_authority.cache_clear()
    assert asset_cases.check_authority()
    source.write_bytes(b'Authoritative Name.png\n')
    asset_cases.check_authority.cache_clear()
    assert asset_cases.check_authority()
    source.write_bytes(b'Authoritative name.png\n')
    asset_cases.check_authority.cache_clear()
    with pytest.raises(BulkError, match='Authoritative PS1 input changed'):
        asset_cases.check_authority()
    asset_cases.check_authority.cache_clear()


def test_windows_accessibility_does_not_satisfy_case_exact_lookup(tmp_path):
    (tmp_path / 'logo.png').write_bytes(b'pixels')
    assert asset_cases.exact(tmp_path, 'logo.png').is_file()
    with pytest.raises(BulkError, match='physical spelling'):
        asset_cases.exact(tmp_path, 'Logo.png')
    with pytest.raises(BulkError):
        confined(tmp_path, 'Logo.png', must_exist=True)


def test_git_spelling_collisions_are_detected_independently_of_host_filesystem():
    result = collisions(['network/overlays/standard/logo.png', 'network/overlays/standard/Logo.png'])
    assert len(result) == 1 and len(next(iter(result.values()))) == 2


def test_historical_alias_is_explicit_and_byte_bound(tmp_path, monkeypatch):
    source = tmp_path / 'Name.png'; source.write_bytes(b'unchanged')
    record = {'from': 'name.png', 'to': 'Name.png', 'sha256': sha256(source)}
    monkeypatch.setattr(asset_cases, 'migrations', lambda: {'name.png': record})
    assert asset_cases.historical(tmp_path, 'name.png', record['sha256']) == source
    source.write_bytes(b'changed')
    with pytest.raises(BulkError, match='Historical case alias bytes differ'):
        asset_cases.historical(tmp_path, 'name.png', record['sha256'])


def test_overlay_identity_case_transition_allows_no_design_or_asset_changes(monkeypatch):
    record = {'from': 'logos/name.png', 'to': 'logos/Name.png', 'sha256': 'a' * 64}
    monkeypatch.setattr(asset_cases, 'migrations', lambda: {'logos/name.png': record})
    payload = {'kind': 'overlay', 'parameters': {'input': 'logos/name.png', 'box': [285, 85]},
               'inputs': [{'role': 'overlay_source', 'path': 'logos/name.png', 'sha256': 'a' * 64}],
               'renderer': {'native': 'same'}}
    before = RenderTask('old', 'b' * 64, 'genre/overlays/standard/name.png', payload, [])
    current = deepcopy(payload)
    current['parameters']['input'] = 'logos/Name.png'; current['inputs'][0]['path'] = 'logos/Name.png'
    after = RenderTask('new', 'c' * 64, 'genre/overlays/standard/Name.png', current, ())
    assert asset_cases.replacement(before, after)
    current['parameters']['box'] = [440, 100]
    assert not asset_cases.replacement(before, after)


def test_generated_overlay_basename_cannot_differ_between_source_and_sizes(tmp_path):
    config = Config(cache_dir=tmp_path / 'cache', workspace_dir=tmp_path / 'work', output_dir=tmp_path / 'output')
    manifest = plan(config, groups=['aspect'], sources=['logos_aspect/1.33.png'])
    manifest['jobs'][0]['remote_relative'] = manifest['jobs'][0]['remote_relative'].replace('1.33.png', 'Other.png')
    manifest['sha256'] = fingerprint({k: v for k, v in manifest.items() if k != 'sha256'})
    with pytest.raises(BulkError, match='preserve the exact authoritative source basename'):
        validate_manifest(manifest)
