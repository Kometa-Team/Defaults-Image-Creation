"""Real Playlist pixels through the production API and normal bulk worker."""
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys

from PIL import Image
import pytest

from create_defaults.create_poster import ROOT, PosterOptions, create_poster, render_poster
from create_defaults.image_layout import fit_visible_rgba
from create_defaults.poster_styles import PLAYLIST


def options(label='wdu'):
    manifest = json.loads((ROOT/'phase6/PLAYLIST_PILOT_MANIFEST.json').read_text())
    row = next(r for r in manifest['requests'] if r['request'] == label)
    return PosterOptions(logo=ROOT/'phase6'/row['logo']['file'], logo_resize=1600,
        logo_offset=-200, text_offset=450, font_size=154, text='TIMELINE ORDER',
        font='fonts/BebasNeue-Regular.ttf', base_color=row['proposed']['fixture_background'],
        white_wash=True, clean=True, out_name=Path(row['proposed']['public_path']).stem)


def assert_bounds(metadata):
    style = metadata['composition_style']
    left, top, right, bottom = style['logo']['visible_bounds']
    assert 200 <= left < right <= 1800
    assert 850 <= top < bottom <= 1750
    assert abs((left+right)/2-1000) <= .5
    assert abs((top+bottom)/2-1300) <= .5
    assert style['measured_gap'] == style['caption_visible_bounds'][1]-bottom
    assert style['measured_gap'] >= PLAYLIST.minimum_vertical_gap == 100
    assert style['caption_box'] == [50, 1850, 1950, 2050]
    assert metadata['caption']['point_size'] == 154


def test_playlist_boxes_preserve_anchors_and_separate_caption_measurement():
    assert PLAYLIST.logo_box == (200, 850, 1800, 1750)
    assert PLAYLIST.caption_box == (50, 1850, 1950, 2050)
    assert PLAYLIST.caption_box[1]-PLAYLIST.logo_box[3] == PLAYLIST.minimum_vertical_gap
    assert PLAYLIST.caption_measurement == (1900, 1000)
    assert PLAYLIST.caption_offset == 450


@pytest.mark.parametrize('label', ['wdu', 'avp'])
def test_real_portrait_and_wide_logos_fit_through_normal_renderer(tmp_path, label):
    path = tmp_path/(options(label).out_name+'.jpg')
    report = create_poster(options(label), style=PLAYLIST.id, output_path=path)
    assert_bounds(report)
    with Image.open(path) as image:
        assert image.size == (2000, 3000) and image.mode == 'RGB'
    if label == 'wdu':
        _, old = render_poster(options(label))
        assert old['logo_size'][1] > 900
        assert report['logo_size'][1] <= 900
        assert report['caption'] == old['caption']
        assert report['font'] == old['font']


def test_asymmetric_transparent_padding_cannot_change_scale_center_or_jpeg(tmp_path):
    original = options('avp')
    with Image.open(original.logo) as image:
        source = image.convert('RGBA')
    padded = Image.new('RGBA', (source.width+731, source.height+213))
    padded.paste(source, (700, 200))
    source_path = tmp_path/'asymmetric.png'
    padded.save(source_path)
    first, second = tmp_path/'original.jpg', tmp_path/'padded.jpg'
    a = create_poster(original, style=PLAYLIST.id, output_path=first)
    b = create_poster(replace(original, logo=source_path), style=PLAYLIST.id, output_path=second)
    assert_bounds(a);assert_bounds(b)
    assert a['composition_style']['logo']['visible_bounds'] == b['composition_style']['logo']['visible_bounds']
    assert first.read_bytes() == second.read_bytes()


def test_unadopted_calls_retain_the_committed_legacy_renderer(tmp_path):
    # Load the immutable Git blob, not another working copy or a rewritten baseline.
    import subprocess
    raw = subprocess.check_output(['git', 'show',
        'dcbfa072dbedcb0069dd27be920ef3103687b5a4:create_defaults/create_poster.py'])
    name = 'create_defaults._playlist_legacy_control'
    spec = importlib.util.spec_from_loader(name, loader=None, origin=str(ROOT/'create_poster.py'))
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(ROOT/'create_poster.py')
    sys.modules[name] = module
    try:
        exec(compile(raw, str(ROOT/'create_poster.py'), 'exec'), module.__dict__)
        baseline_options = module.PosterOptions(**vars(options()))
        old, old_report = module.render_poster(baseline_options)
        current, current_report = render_poster(options())
        assert old.tobytes() == current.tobytes()
        assert old_report == current_report
    finally:
        sys.modules.pop(name, None)


def test_empty_alpha_and_caption_overflow_are_explicit_errors():
    with pytest.raises(ValueError, match='visible alpha'):
        fit_visible_rgba(Image.new('RGBA', (20, 30)), PLAYLIST.logo_box)
    with pytest.raises(ValueError, match='Caption exceeds'):
        render_poster(replace(options(), text='TIMELINE ORDER\nTIMELINE ORDER\nTIMELINE ORDER'), style=PLAYLIST.id)
    with pytest.raises(ValueError, match='Unknown poster'):
        render_poster(options(), style='unknown')
    with pytest.raises(ValueError, match='border resize'):
        render_poster(replace(options(), border=True), style=PLAYLIST.id)


def test_normal_playlist_plan_and_worker_bind_and_use_the_style(tmp_path):
    from create_defaults.bulk.common import BulkError, fingerprint
    from create_defaults.bulk.config import Config
    from create_defaults.bulk.definitions import load_definitions
    from create_defaults.bulk.planner import Planner
    from create_defaults.bulk.contracts.expanded.validation import approved_english
    from create_defaults.bulk.workers import tasks_from_manifest, compose
    from create_defaults.bulk.planner import validate_manifest
    catalog = ROOT/'bulk/catalog'
    definitions = load_definitions([catalog/'playlist.yml'], profiles_path=catalog/'profiles.yml')
    selected = definitions[0].id
    config = Config(offline=True, output_dir=tmp_path)
    manifest = Planner(config).plan(definitions, approved_english(), posters=[selected], languages=['en'])
    job = manifest['jobs'][0]
    assert job['composition_style'] == PLAYLIST.id
    task = next(tasks_from_manifest(manifest))
    assert task.payload['composition_style'] == PLAYLIST.id
    target = tmp_path/'worker.jpg'
    compose(task.spec(), target, {'config':config})
    direct = tmp_path/'direct.jpg'
    report = create_poster(PosterOptions(**job['parameters']), style=PLAYLIST.id, output_path=direct)
    assert_bounds(report)
    assert target.read_bytes() == direct.read_bytes()
    altered = deepcopy(manifest)
    del altered['jobs'][0]['composition_style']
    altered['sha256'] = fingerprint({k:v for k,v in altered.items() if k!='sha256'})
    with pytest.raises(BulkError) as error:
        validate_manifest(altered)
    assert error.value.code == 'composition_style'
