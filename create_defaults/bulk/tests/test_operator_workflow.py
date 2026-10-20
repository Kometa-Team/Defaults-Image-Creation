"""Real Python rendering, native-cache guards and local Git operator acceptance."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from create_defaults.bulk.common import BulkError, fingerprint, sha256
from create_defaults.bulk.config import Config
from create_defaults.bulk.library_sources import blob_id, load_json, save, sealed
from create_defaults.bulk.operator_publication import prepare, approve, authorize
from create_defaults.bulk.operations import generate, native_guard, preview, validate_generation
from create_defaults.bulk.production_verify import prepare as verification_plan
from create_defaults.bulk.library_stage import gate, run, git
from create_defaults.bulk.tests.test_library_stage import fixture


def proposal(tmp_path, *, addition=False):
    old_plan, _, remote = fixture(tmp_path)
    rows = []
    for batch in old_plan['batches']:
        for m in batch['members']:
            rows.append({'destination': m['destination'], 'candidate_path': m['source'],
                         'candidate_sha256': m['sha256'], 'candidate_blob': m['git_blob'],
                         'candidate_bytes': m['size'], 'published_sha256': m['previous_sha256'],
                         'published_blob': m['previous_git_blob'], 'context_sha256': m['context_sha256'],
                         'technical_valid': True, 'difference_class': 'unexpected_difference', 'hash_state': 'unequal'})
    if addition:
        rows[0].update(destination='genre/New & isolated.png', published_sha256=None,
                       published_blob=None, hash_state='missing_published')
    inventory = sealed({'baseline': old_plan['baseline'], 'rows': rows})
    policy = {'version': 'fixture-v1', 'mode': 'exact-individual-review'}
    manifest = prepare(inventory, policy, tmp_path / 'review')
    return manifest, policy, remote


def decision(manifest, policy, **kwargs):
    return approve(manifest, policy, reviewer='bullmoose20', policy_hash=fingerprint(policy),
                   manifest_hash=manifest['sha256'], decision_text='Synthetic local rehearsal only', **kwargs)


def test_operator_real_git_interruption_resume_and_noop(tmp_path):
    manifest, policy, remote = proposal(tmp_path)
    receipt = decision(manifest, policy, accept_exceptions=True)
    plan, auth = authorize(manifest, policy, receipt)
    auth = sealed({k: v for k, v in dict(auth, test_only=True).items() if k != 'sha256'})
    root = tmp_path / 'transport'
    with pytest.raises(BulkError, match='After push'):
        run(plan, auth, root, test_remote=remote, fail_at='after_push')
    result = run(plan, auth, root, test_remote=remote)
    repeat = run(plan, auth, root, test_remote=remote)
    assert result['complete'] and result['master_unchanged'] and repeat['head'] == result['head']
    assert len(git(root / 'work', 'rev-list', plan['baseline']['head'] + '..HEAD').splitlines()) == 1
    with pytest.raises(BulkError, match='Synthetic authorization'):
        run(plan, auth, tmp_path / 'no-network')


def test_new_destination_requires_its_exact_mapping_approval(tmp_path):
    manifest, policy, remote = proposal(tmp_path, addition=True)
    with pytest.raises(BulkError, match='every approved new destination'):
        decision(manifest, policy, accept_exceptions=True)
    receipt = decision(manifest, policy, accept_exceptions=True, allow_additions=['genre/New & isolated.png'])
    plan, auth = authorize(manifest, policy, receipt)
    auth = sealed({k: v for k, v in dict(auth, test_only=True).items() if k != 'sha256'})
    result = run(plan, auth, tmp_path / 'transport', test_remote=remote)
    assert result['complete'] and result['master_unchanged']
    assert b'genre/New & isolated.png' in git(remote, 'ls-tree', '-r', '--name-only', result['head'])


@pytest.mark.parametrize('change', ['manifest', 'policy', 'scope', 'branch', 'candidate'])
def test_operator_rejects_changed_approval_identity(tmp_path, change):
    manifest, policy, _ = proposal(tmp_path)
    if change == 'scope':
        with pytest.raises(BulkError, match='individual exceptions'):
            decision(manifest, policy)
        return
    receipt = decision(manifest, policy, accept_exceptions=True)
    if change == 'manifest':
        manifest = sealed({k: v for k, v in dict(manifest, policy_sha256='changed').items() if k != 'sha256'})
    elif change == 'policy':
        policy = dict(policy, widened=True)
    if change in {'manifest', 'policy'}:
        with pytest.raises(BulkError, match='Exact policy'):
            authorize(manifest, policy, receipt)
        return
    plan, auth = authorize(manifest, policy, receipt)
    if change == 'branch':
        auth = sealed({k: v for k, v in dict(auth, branch='master').items() if k != 'sha256'})
    else:
        plan = deepcopy(plan)
        plan['batches'][0]['members'][0]['sha256'] = '0' * 64
        plan = sealed({k: v for k, v in plan.items() if k != 'sha256'})
    with pytest.raises(BulkError, match='Transport differs'):
        gate(plan, auth)


def test_native_encoding_change_refuses_cache_reuse(tmp_path, monkeypatch):
    config = Config(cache_dir=tmp_path / 'cache', workspace_dir=tmp_path / 'work', output_dir=tmp_path / 'output')
    native_guard(config)
    monkeypatch.setattr('create_defaults.bulk.operations.runtime_identity', lambda: {'changed_native_encoder': True})
    with pytest.raises(BulkError, match='Native dependencies changed'):
        native_guard(config)


def test_production_verification_is_exact_and_isolates_missing(tmp_path):
    manifest, _, _ = proposal(tmp_path)
    rows, entries = [], []
    for m in manifest['members']:
        rows.append({'destination': m['destination'], 'candidate_path': m['source'],
                     'candidate_sha256': m['sha256'], 'candidate_blob': m['git_blob'], 'candidate_bytes': m['size']})
        entries.append({'path': m['destination'], 'sha': m['git_blob'], 'size': m['size'], 'mode': '100644', 'type': 'blob'})
    inventory = sealed({'rows': rows})
    state = sealed(dict(manifest['baseline'], entries=entries))
    assert not verification_plan(inventory, state)['discrepancies']
    state = sealed(dict(manifest['baseline'], entries=entries[:1]))
    result = verification_plan(inventory, state)
    assert len(result['members']) == 1 and result['discrepancies'][0]['reason'] == 'missing'
    path = tmp_path / 'new-0.jpg'
    path.write_bytes(b'changed same identity claim')
    with pytest.raises(BulkError, match='Validated local output changed'):
        verification_plan(inventory, state)


def test_operator_actual_category_repeat_and_exact_preview(tmp_path):
    config = Config(cache_dir=tmp_path / 'cache', workspace_dir=tmp_path / 'work', output_dir=tmp_path / 'output')
    args = SimpleNamespace(command='generate', definitions=None, profiles=None, category=['Based'],
                           poster=[], workers=1, report=tmp_path / 'first.json')
    first = generate(args, config)
    assert first['executed'] == 4
    report = load_json(args.report)
    state = sealed({'repository': 'Kometa-Team/Default-Images', 'branch': 'master', 'head': '1' * 40,
                    'tree': '2' * 40, 'entries': []})
    initial = preview(report, tmp_path / 'preview-new', state)
    assert len(initial['rows']) == 4 and all(r['hash_state'] == 'missing_published' for r in initial['rows'])
    assert 'Python candidate' in (tmp_path / 'preview-new/review/review.html').read_text()
    entries = []
    import shutil
    for row in initial['rows']:
        entries.append({'path': row['destination'], 'sha': row['candidate_blob'], 'size': row['candidate_bytes'],
                        'mode': '100644', 'type': 'blob'})
        path = tmp_path / 'preview-exact/published' / (row['candidate_blob'] + '.jpg')
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(row['candidate_path'], path)
    state = sealed({k: v for k, v in dict(state, entries=entries).items() if k != 'sha256'})
    exact = preview(report, tmp_path / 'preview-exact', state)
    assert all(r['hash_state'] == 'exact_match' for r in exact['rows'])
    manifest = prepare(exact, {'version': 'exact-v1'}, tmp_path / 'noop')
    assert not manifest['members']
    receipt = decision(manifest, {'version': 'exact-v1'})
    with pytest.raises(BulkError, match='Everything is synchronized'):
        authorize(manifest, {'version': 'exact-v1'}, receipt)
    args.report = tmp_path / 'repeat.json'
    args.cache_only = True
    repeat = generate(args, config)
    assert repeat['executed'] == 0 and repeat['cache_hits'] == 4
    validate_generation(load_json(args.report))
    receipt = next((config.cache_dir / 'worker-receipts').glob('*.json'))
    receipt.write_text('{}')
    with pytest.raises(BulkError, match='Worker receipt'):
        validate_generation(load_json(args.report))


def test_cache_only_refuses_a_cold_identity_without_rendering(tmp_path):
    config = Config(cache_dir=tmp_path / 'cache', workspace_dir=tmp_path / 'work', output_dir=tmp_path / 'output')
    args = SimpleNamespace(command='generate', definitions=None, profiles=None, category=['Based'],
                           poster=[], workers=1, cache_only=True, report=tmp_path / 'cold.json')
    with pytest.raises(BulkError, match='Cache-only execution refuses'):
        generate(args, config)
    assert not list(config.output_dir.rglob('*.jpg'))


def test_new_authored_poster_smoke_is_native_and_incremental(tmp_path):
    import yaml
    from create_defaults.bulk.catalog import load_catalog
    value = load_catalog(['Based'])[0].data
    value.update(id='based.local-operator-acceptance', display_name='Local acceptance fixture',
                 source={'kind': 'authored', 'path': 'local-acceptance.yml', 'line': None, 'row_sha256': None})
    value['composer']['out_name'] = 'Local acceptance fixture'
    value['composer']['base_color'] = '#123457'
    value['layout'] = {'kind': 'fixed', 'measurement': None}
    value['output'] = {'directory': 'based', 'filename': 'Local acceptance fixture.jpg',
                       'remote_paths': {'en': 'based/Local acceptance fixture.jpg'}}
    path = tmp_path / 'new-definition.yml'
    path.write_text(yaml.safe_dump({'schema_version': 1, 'category': 'Based', 'definitions': [value]}))
    config = Config(cache_dir=tmp_path / 'cache', workspace_dir=tmp_path / 'work', output_dir=tmp_path / 'output')
    args = SimpleNamespace(command='generate', definitions=[path], profiles=None, category=[], poster=[],
                           workers=1, report=tmp_path / 'new.json')
    assert generate(args, config)['executed'] == 1
    output = config.output_dir / 'defaults-en/based/Local acceptance fixture.jpg'
    before = sha256(output)
    args.report = tmp_path / 'repeat.json'
    assert generate(args, config)['executed'] == 0 and sha256(output) == before


def test_case_only_rename_requires_exact_decision_and_leaves_one_git_path(tmp_path):
    manifest, policy, remote = proposal(tmp_path)
    base = tmp_path / 'base'
    old = 'network/overlays/standard/tokyo mx.png'
    new = 'network/overlays/standard/Tokyo MX.png'
    source = base / old
    source.parent.mkdir(parents=True)
    source.write_bytes(b'old png bytes')
    git(base, 'add', '.'); git(base, 'commit', '-m', 'case fixture')
    git(base, 'push', str(remote), 'HEAD:refs/heads/master')
    manifest = deepcopy(manifest)
    member = manifest['members'][0]
    member.update(destination=new, rename_from=old, kind='overlay', source_asset='logos_network/Tokyo MX.png',
                  previous_sha256=sha256(source), previous_git_blob=blob_id(source))
    baseline = dict(manifest['baseline'], head=git(base, 'rev-parse', 'HEAD').decode().strip(),
                    tree=git(base, 'rev-parse', 'HEAD^{tree}').decode().strip())
    manifest = sealed({k: v for k, v in dict(manifest, members=[member], baseline=baseline).items() if k != 'sha256'})
    with pytest.raises(BulkError, match='case-only rename'):
        decision(manifest, policy, accept_exceptions=True)
    receipt = decision(manifest, policy, accept_exceptions=True, allow_renames=[old + '=>' + new])
    plan, auth = authorize(manifest, policy, receipt)
    auth = sealed({k: v for k, v in dict(auth, test_only=True).items() if k != 'sha256'})
    result = run(plan, auth, tmp_path / 'case-transport', test_remote=remote)
    paths = git(remote, 'ls-tree', '-r', '--name-only', '-z', result['head']).decode().split('\0')
    assert new in paths and old not in paths and result['master_unchanged']
    assert sum(p.casefold() == new.casefold() for p in paths) == 1
    assert run(plan, auth, tmp_path / 'case-transport', test_remote=remote)['head'] == result['head']


def test_new_overlay_uses_existing_transform_and_repeat_is_noop(tmp_path):
    from PIL import Image
    import yaml
    assets = tmp_path / 'assets'
    assets.mkdir()
    source = assets / 'review-logo.png'
    Image.new('RGBA', (40, 20), (100, 120, 140, 128)).save(source)
    definition = tmp_path / 'new-overlay.yml'
    definition.write_text(yaml.safe_dump({'schema_version': 1, 'overlays': [
        {'source': source.name, 'destination': 'genre/overlays/standard/review-logo.png',
         'box': [285, 85], 'trim': False}]}))
    config = Config(asset_dir=assets, cache_dir=tmp_path / 'cache', workspace_dir=tmp_path / 'work', output_dir=tmp_path / 'output')
    args = SimpleNamespace(command='overlays', definitions=[definition], group=[], source=[], size=[],
                           workers=1, report=tmp_path / 'new.json')
    first = generate(args, config)
    assert first['executed'] == 1
    report = load_json(args.report)
    validate_generation(report)
    output = config.output_dir / 'genre/overlays/standard/review-logo.png'
    with Image.open(output) as image:
        assert image.mode == 'RGBA' and image.size == (170, 85)
        assert image.getchannel('A').getextrema() == (128, 128)
    before = sha256(output)
    args.report = tmp_path / 'repeat.json'
    assert generate(args, config)['executed'] == 0
    assert sha256(output) == before
    # Exact bytes at the wrong Git spelling still require a reviewed rename.
    import shutil
    review_root = tmp_path / 'case-preview'
    cached = review_root / 'published' / (blob_id(output) + '.png')
    cached.parent.mkdir(parents=True)
    shutil.copyfile(output, cached)
    old = 'genre/overlays/standard/Review-logo.png'
    state = sealed({'repository': 'Kometa-Team/Default-Images', 'branch': 'master', 'head': '1' * 40,
                    'tree': '2' * 40, 'entries': [{'path': old, 'sha': blob_id(output),
                    'size': output.stat().st_size, 'mode': '100644', 'type': 'blob'}]})
    inventory = preview(load_json(args.report), review_root, state)
    row = inventory['rows'][0]
    assert row['rename_from'] == old and row['difference_class'] == 'filename_case_only'
    manifest = prepare(inventory, {'version': 'case-fixture-v1'}, tmp_path / 'case-proposal')
    assert len(manifest['members']) == 1 and manifest['members'][0]['rename_from'] == old
    Image.new('RGBA', (40, 20), (10, 20, 30, 128)).save(source)
    with pytest.raises(BulkError, match='source or asset changed'):
        validate_generation(report)
    assert generate(args, config)['executed'] == 1
