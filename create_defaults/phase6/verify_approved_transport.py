"""Replay the native offline Playlist workflow against approved JPEG bytes.

This invokes the existing owned fixture, reviews and M6 draft transport. The
preview hook adds read-only byte comparisons; it does not replace any proof,
render, gate or approval. The retained destination is a local Git checkout.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from unittest.mock import patch

import requests


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--expected-head', required=True)
    args = parser.parse_args(argv)
    from ci.phase6_playlist_maintenance import verify_checkout
    from create_defaults.bulk.lifecycle import operations
    from create_defaults.bulk.lifecycle.previews import CompositionArchive
    from create_defaults.phase6.fixtures import case
    from create_defaults.phase6.playlist import HERE, REQUESTS, manifest

    started = time.perf_counter()
    root = HERE.parent.parent
    env = dict(os.environ, GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='safe.directory', GIT_CONFIG_VALUE_0=root.as_posix())
    def git(where, *arguments):
        return subprocess.check_output(['git', '-c', 'core.hooksPath=NUL', *arguments], cwd=where, env=env)
    assert git(root, 'rev-parse', 'HEAD').decode().strip() == args.expected_head
    assert not git(root, 'status', '--porcelain').strip()
    verify_checkout(expected_head=args.expected_head)
    approval_path = HERE / 'review/visual-approval.json'
    review_path = HERE / 'review/colour-review.json'
    approval_raw, review_raw = approval_path.read_bytes(), review_path.read_bytes()
    approval, review = json.loads(approval_raw), json.loads(review_raw)
    assert approval['decision'] == 'APPROVED_FOR_OFFLINE_PILOT'
    assert approval['colour_review_sha256'] == digest(review_raw)
    assert approval['contact_sheet_sha256'] == digest((HERE / 'review/eight-poster-colour-proposals.png').read_bytes())
    rows = manifest()['requests']
    approved = {r['display_name']: r for r in approval['posters']}
    assert len(approved) == len(rows) == len(REQUESTS) == 8
    review_rows = {r['display_name']: r for r in review['posters']}
    encoded, by_identity, relative_paths = {}, {}, {}
    for row in rows:
        proposed = row['proposed']
        expected = approved[proposed['display_name']]
        assert expected['base_colour'] == proposed['fixture_background']
        assert review_rows[proposed['display_name']]['sha256'] == expected['sha256']
        relative = proposed['public_path']
        path = args.approved_dir.absolute() / relative
        assert path.is_file() and not path.is_symlink()
        raw = path.read_bytes()
        assert digest(raw) == expected['sha256'], 'Approved JPEG changed: ' + str(path)
        encoded[proposed['persistent_identity']] = raw
        by_identity[proposed['persistent_identity']] = expected
        relative_paths[proposed['persistent_identity']] = relative
    out = args.output_dir.absolute()
    assert not out.exists(), 'Keep prior evidence intact; use a new output directory'
    out.mkdir(parents=True)
    print('ENTRY: committed source and all eight approved JPEGs verified', flush=True)
    native_preview = operations.preview
    rendered = []
    def checked_preview(context, trial, *arguments, **keywords):
        print('COMPOSITION: native rendering and receipt checks started', flush=True)
        evidence = native_preview(context, trial, *arguments, **keywords)
        archive = CompositionArchive(context.registry.operations.root, readonly=True)
        for view in evidence.to_dict()['views']:
            members = view['members']
            assert {m['identity'] for m in members} == set(encoded)
            for member in members:
                raw = archive.read_bytes(member['object_sha256'])
                assert raw == encoded[member['identity']], 'Native render differs from approved JPEG: ' + member['public_path']
                assert member['sha256'] == digest(raw)
            rendered.append(dict(appearance=view['appearance'], matched=8))
        print('COMPOSITION: both native views match all eight approved JPEGs; continuing original review/catalog/draft transport', flush=True)
        return evidence

    with patch.object(requests.Session, 'request', side_effect=AssertionError('Offline approved transport forbids HTTP')):
        with patch.object(operations, 'preview', checked_preview):
            with case(REQUESTS, export=out / 'native') as value:
                assert {r['appearance'] for r in rendered} == {'default', 'requested'}
                remote = value['native'].root / 'remote.git'
                assert remote.resolve().is_relative_to(value['row'][0].root.resolve())
                transported_head = value['report']['head']
                destination = out / 'destination'
                git(out, 'clone', '--no-checkout', '--no-hardlinks', '--no-local', str(remote), str(destination))
                git(destination, 'checkout', '--detach', transported_head)
                results = []
                for identity in encoded:
                    relative = relative_paths[identity]
                    actual = destination / relative
                    raw = actual.read_bytes()
                    blob = git(remote, 'show', transported_head + ':' + relative)
                    expected = by_identity[identity]
                    assert raw == blob == encoded[identity]
                    assert digest(raw) == expected['sha256']
                    results.append(dict(display_name=expected['display_name'], identity=identity,
                        destination=str(actual), relative_path=relative, expected_sha256=expected['sha256'],
                        actual_sha256=digest(raw), remote_blob_sha256=digest(blob), match=True))
                assert not git(destination, 'status', '--porcelain').strip()
                assert value['report']['complete'] and value['report']['draft_verified']
                assert value['report']['network_writes'] == 0
                assert all(value['final_tree'][p] == row for p, row in value['baseline_tree'].items())
                assert len(value['final_tree']) == len(value['baseline_tree']) + 8
                for row in rows:
                    proposed = row['proposed']
                    assert (args.approved_dir.absolute() / proposed['public_path']).read_bytes() == encoded[proposed['persistent_identity']]
                assert approval_path.read_bytes() == approval_raw and review_path.read_bytes() == review_raw
                verify_checkout(expected_head=args.expected_head)
                proof = out / 'native/eight/proof.json'
                bundle = out / 'native/eight/transport.bundle'
                result = dict(kind='phase6-approved-eight-playlist-offline-transport',
                    candidate_commit=args.expected_head, approved_renderer_commit=approval['renderer_head'],
                    visual_approval_sha256=digest(approval_raw), colour_review_sha256=digest(review_raw),
                    contact_sheet_sha256=approval['contact_sheet_sha256'],
                    historical_comparison_sha256=digest((HERE / 'review/nine-poster-historical-comparison.png').read_bytes()),
                    approved_matches=8, composition_views=rendered, destination=str(destination),
                    transported_commit=transported_head, posters=results,
                    preserved_baseline_posters=value['synthetic_baseline_posters'],
                    native_report=value['report'], native_proof_sha256=digest(proof.read_bytes()),
                    transport_bundle_sha256=digest(bundle.read_bytes()), simulation=True,
                    real_operational_approvals=0, live_registry_reservations='PENDING', catalog_mappings='PENDING',
                    publication_authorized=False, activation_authorized=False,
                    elapsed_seconds=round(time.perf_counter() - started, 3))
                (out / 'approved-transport-result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
                print(json.dumps(result, indent=2), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
