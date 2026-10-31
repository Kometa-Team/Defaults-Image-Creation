"""P5-T13/T14 native complete membership and original Package E batching."""
from create_defaults.bulk.lifecycle.publication_preparation import run_offline
from create_defaults.phase5.m5_tests.helpers import prepared
from copy import deepcopy
import pytest
from create_defaults.bulk.common import BulkError,canonical
from create_defaults.bulk.library_sources import sealed
from create_defaults.bulk.lifecycle.preparation_models import Preparation


def test_P5_T13_T14_native_complete_plan(native):
    selection,patch,target,result=prepared(native)
    value=result.to_dict()
    assert value['required_members']==native['snapshot'].to_dict()['members']
    assert len(value['members'])==len(value['plan']['batches'])==1
    assert patch.verify(selection.verify()[1]['definitions'])['unchanged_jobs']==275
    assert not value['publication_authorized'] and not value['remote_writes_authorized']


def test_P5_T30_native_offline_tree(native):
    selection,patch,target,result=prepared(native)
    report=run_offline(result,selection,patch,target)
    assert report['complete'] and report['network_writes']==0
    assert not report['publication_authorized']
    from create_defaults.bulk.lifecycle.catalog_preparation import git
    from create_defaults.phase5.m5_tests.helpers import export_native
    remote=target.trial.root/('m5-transport-'+result.sha256)/'remote.git'
    assert git(remote,'show',report['head']+':keep.txt')==b'Unrelated baseline bytes\n'
    export_native(native,patch,target,result,report,name='single')


@pytest.mark.parametrize('mutation',['omitted_member','withheld_manifest','omitted_batch','extra_member','foreign_receipt','changed_artifact'])
def test_P5_T13_T14_operator_manifest_cannot_change_native_membership(plan_seed,mutation):
    from create_defaults.bulk.lifecycle.publication_preparation import revalidate
    selection,patch,target,result=plan_seed;value=result.to_dict()
    if mutation=='omitted_member':value['members']=[]
    elif mutation=='withheld_manifest':
        value['manifest']=sealed(dict(value['manifest'],members=[],withheld=['hidden']))
    elif mutation=='omitted_batch':value['plan']=sealed(dict(value['plan'],batches=[]))
    elif mutation=='extra_member':value['members'].append(deepcopy(value['members'][0]))
    elif mutation=='foreign_receipt':value['members'][0]['receipt_sha256']='0'*64
    else:value['members'][0]['sha256']='0'*64
    with pytest.raises(BulkError):revalidate(Preparation.from_dict(value),selection,patch,target)


def test_P5_T21_identical_bytes_keep_required_members_and_revalidate(native):
    from create_defaults.bulk.lifecycle.previews import CompositionArchive
    from create_defaults.bulk.lifecycle.publication_preparation import revalidate
    snapshot=native['snapshot'].to_dict();member=next(iter(snapshot['artwork'].values()))
    raw=CompositionArchive(native['row'][1].registry.operations.root,readonly=True).read_bytes(member['object_sha256'])
    selection,patch,target,result=prepared(native,existing={member['public_path']:raw})
    assert len(result.to_dict()['required_members'])==1 and not result.to_dict()['plan']['batches']
    report=run_offline(result,selection,patch,target)
    assert report['complete'] and report['verified_batches']==0
    from create_defaults.bulk.lifecycle.catalog_preparation import git
    git(patch.source.root,'commit','--allow-empty','-m','Same bytes, changed source authority')
    with pytest.raises(BulkError,match='stale_source'):revalidate(result,selection,patch,target)
