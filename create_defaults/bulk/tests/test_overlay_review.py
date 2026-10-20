from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from create_defaults.bulk.common import BulkError
from create_defaults.bulk.library_sources import blob_id, published_file
from create_defaults.bulk.library_visual import PROPOSED_POLICY
from create_defaults.bulk.overlay_review import measure, negative_controls, policy


def test_overlay_policy_rejects_deliberate_alpha_color_crop_and_shift_defects(tmp_path):
    image = Image.new('RGBA', (180, 85))
    draw = ImageDraw.Draw(image)
    draw.rectangle((15, 10, 50, 70), fill=(255, 255, 255, 255))
    draw.rectangle((70, 25, 160, 55), fill=(200, 20, 30, 255))
    source = tmp_path / 'source.png'
    image.save(source)
    proposed = policy(PROPOSED_POLICY)
    result = negative_controls(source, tmp_path / 'controls', proposed)
    assert result['passed'] and len(result['controls']) == 9
    assert result['controls'][0]['result']['screen_pass']
    assert all(not r['result']['screen_pass'] for r in result['controls'][1:])
    assert not result['approval_granted']
    assert measure(source, source)['unmatched_support_radius_1'] == 0


@pytest.mark.parametrize('corrupt', [False, True])
def test_shared_remote_blob_concurrent_promotion_requires_exact_bytes(tmp_path, monkeypatch, corrupt):
    image = tmp_path / 'image.png'
    Image.new('RGBA', (20, 20), 'white').save(image)
    payload = image.read_bytes()
    entry = {'path': 'genre/overlays/standard/same.png', 'mode': '100644', 'type': 'blob',
             'sha': blob_id(image), 'size': len(payload)}
    root = tmp_path / 'remote'
    target = root / 'published' / (entry['sha'] + '.png')
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def iter_content(self, size):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'corrupt' if corrupt else payload)
            yield payload
    class Session:
        def get(self, *args, **kwargs): return Response()
    monkeypatch.setattr('create_defaults.bulk.library_sources.requests.Session', Session)
    if corrupt:
        with pytest.raises(BulkError, match='Concurrent published cache bytes differ'):
            published_file(root, {'head': '1' * 40}, entry)
    else:
        path, provenance = published_file(root, {'head': '1' * 40}, entry)
        assert path.read_bytes() == payload and provenance == 'pinned_remote_download'
