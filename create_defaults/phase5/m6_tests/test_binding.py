"""Exact lifecycle membership and sealed decisions, with no operational grant."""
from copy import deepcopy
from pathlib import Path
import pytest
from create_defaults.bulk.common import BulkError,fingerprint
from create_defaults.bulk.lifecycle.preparation_models import FLAGS
from create_defaults.bulk.lifecycle.draft_models import DraftBinding
from create_defaults.bulk.lifecycle.draft_transport import propose,bind,publish_operational
from create_defaults.bulk.library_sources import sealed
from create_defaults.phase5.m6_tests.helpers import connected,prepared


def test_M6_exact_binding_rejects_resealed_membership_and_context(native):
    protocol,c=connected(native);v=c.binding.to_dict()
    assert DraftBinding.from_bytes(c.binding.encoded).sha256==c.binding.sha256
    for flag,wanted in FLAGS.items():
        altered=deepcopy(v);altered[flag]=not wanted
        with pytest.raises(BulkError,match='binding_schema'):DraftBinding.from_dict(altered)
    for attack in ('missing','extra','catalog','baseline','plan','manifest','test-only','mode'):
        altered=deepcopy(v)
        if attack=='missing':altered['preparation']['members']=[]
        elif attack=='extra':altered['unreviewed']='extra'
        elif attack=='catalog':altered['catalog_sha256']='a'*64
        elif attack=='baseline':altered['inventory']=sealed(dict(altered['inventory'],baseline={'head':'a'*40}))
        elif attack=='plan':altered['plan']=sealed(dict(altered['plan'],batches=[]))
        elif attack=='manifest':altered['manifest']=sealed(dict(altered['manifest'],members=[]))
        elif attack=='test-only':altered['authorization']=sealed(dict(altered['authorization'],test_only=False))
        else:altered['authorization']['policy']['mode']='normal'
        with pytest.raises((BulkError,ValueError,KeyError)):DraftBinding.from_dict(altered)
    with pytest.raises(BulkError,match='production_unavailable'):publish_operational(protocol)


def test_M6_equal_required_members_produce_no_artwork_draft(native):
    selection,patch,target,prep=prepared(native)
    m=prep.to_dict()['members'][0]
    selection,patch,target,prep=prepared(native,existing={m['destination']:Path(m['source']).read_bytes()})
    proposal=propose(prep,selection,patch,target)
    assert len(prep.to_dict()['required_members'])==1 and not proposal['manifest']['members']
    assert not (proposal['root']/'remote.git').exists()
    with pytest.raises(BulkError,match='no_upload_required'):bind(prep,selection,patch,target,{})
    assert patch.sha256==prep.to_dict()['catalog_sha256']


@pytest.mark.parametrize('target',['arbitrary','subclass'])
def test_M6_unowned_or_subclassed_inputs_rejected_before_io(target):
    from create_defaults.bulk.lifecycle.preparation_models import Preparation
    class Forged(Preparation):pass
    forged=object.__new__(Forged) if target=='subclass' else object()
    with pytest.raises(BulkError,match='typed_binding'):propose(forged,None,None,None)
