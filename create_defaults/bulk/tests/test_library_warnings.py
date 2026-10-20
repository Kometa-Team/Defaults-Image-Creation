"""Image-geometry controls for diagnostic investigation; never artwork approval."""
import numpy as np
import pytest

from create_defaults.bulk.library_warnings import dilate, pair_geometry


def caption():
    mask = np.zeros((200,400),dtype=bool)
    for y in (35,115):
        for x in (50,100,150,200,250,300):
            mask[y:y+30,x:x+20] = True
    return mask


def test_same_geometry_and_small_renderer_edge_variation():
    a = caption()
    b = a.copy()
    b[35,50] = False
    value = pair_geometry(a,b,a)
    assert value['measurement_reliable'] and value['geometry_within_proposed_diagnostic_bounds']
    assert not value['alignment_applied']
    assert len(value['candidate']['row_bands']) == 2


@pytest.mark.parametrize('defect',['shift','wrap','clip','missing','wrong_colour'])
def test_real_geometry_controls_fail(defect):
    a = caption()
    b = a.copy()
    if defect == 'shift':
        b = np.roll(b,8,axis=0)
    elif defect == 'wrap':
        b[115:145] = False
        b[170:195,50:100] = True
    elif defect == 'clip':
        b[:,:60] = False
    elif defect == 'missing':
        b[115:145] = False
    else:
        b[:] = False
    assert not pair_geometry(a,b,a)['geometry_within_proposed_diagnostic_bounds']


def test_foreground_contamination_is_withheld():
    support = caption()
    mask = support.copy()
    mask[0:25,:] = True
    value = pair_geometry(mask,mask,support)
    assert not value['measurement_reliable']
    assert not value['geometry_within_proposed_diagnostic_bounds']


def test_neighbourhood_dilation_does_not_wrap_image_edges():
    mask = np.zeros((5,5),dtype=bool)
    mask[0,0] = True
    result = dilate(mask,1)
    assert result.sum() == 4
    assert not result[-1].any() and not result[:,-1].any()
