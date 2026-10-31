"""P5-T15/T21/T28/T29/T31 offline authority, safety and unchanged limits."""
from copy import deepcopy
import pytest

from create_defaults.bulk.common import BulkError
from create_defaults.bulk.lifecycle.preparation_models import diagnostic,commit_operational,FLAGS,Preparation,MAX_BYTES,MAX_FILES
from create_defaults.bulk.lifecycle.publication_preparation import publish_operational,plan_operation,run_offline,_lease
from create_defaults.phase5.m5_tests.helpers import prepared


@pytest.mark.parametrize('entrypoint',[commit_operational,publish_operational])
def test_P5_T28_production_entrypoints_remain_unavailable(entrypoint):
    with pytest.raises(BulkError,match='production_unavailable'):entrypoint()


@pytest.mark.parametrize('text',['Authorization: Bearer secret','https://token@github.com/private','password=private '+('x'*100000)],ids=['bearer','url','oversized'])
def test_P5_T29_diagnostics_are_bounded_and_redacted(text):
    result=diagnostic(RuntimeError(text),'1'*64)
    assert set(result)=={'category','operation_sha256','correlation_id'}
    assert len(str(result))<250 and text not in str(result)
    assert result==diagnostic(RuntimeError('different raw cause'),'1'*64)


@pytest.mark.parametrize('flag',[key for key,value in FLAGS.items() if value is False])
def test_P5_T28_no_preparation_flag_can_grant_authority(plan_seed,flag):
    *_,result=plan_seed;value=result.to_dict();value[flag]=True
    with pytest.raises(BulkError,match='schema'):Preparation.from_dict(value)


@pytest.mark.parametrize('files,size',[(301,MAX_BYTES),(MAX_FILES,MAX_BYTES+1),(True,100),(0,100)])
def test_P5_T31_original_batch_caps_cannot_be_enlarged(plan_seed,files,size):
    selection,patch,target,_=plan_seed
    with pytest.raises(BulkError,match='batch_limits'):plan_operation(selection,patch,target,max_files=files,max_bytes=size)


def test_P5_T21_staged_artwork_tampering_is_not_repaired(native):
    from pathlib import Path
    selection,patch,target,result=prepared(native)
    path=Path(result.to_dict()['members'][0]['source']);raw=path.read_bytes()
    try:
        path.write_bytes(b'forged')
        with pytest.raises(BulkError,match='staged_artifact_changed'):run_offline(result,selection,patch,target)
    finally:path.write_bytes(raw)


def test_P5_T22_concurrent_transport_is_blocked_by_OS_lock(native):
    selection,patch,target,result=prepared(native)
    with _lease(target,result):
        with pytest.raises(BulkError,match='concurrent_preparation'):run_offline(result,selection,patch,target)


@pytest.mark.parametrize('target',['source','definition','translation','destination','review'])
def test_P5_T21_fresh_native_permissions_and_context_required(plan_seed,target):
    from dataclasses import replace
    import json
    selection,patch,destination,result=plan_seed
    candidate=selection.inputs.composition.candidate
    if target in {'source','definition'}:
        path=(candidate.config.asset_dir/next(iter(json.loads(candidate.content_json).values()))['source']['path']
            if target=='source' else candidate.paths[0])
        raw=path.read_bytes()
        try:
            path.write_bytes(raw+b'\n')
            with pytest.raises(BulkError):run_offline(result,selection,patch,destination)
        finally:path.write_bytes(raw)
    elif target in {'translation','destination'}:
        values=dict(selection.inputs.phase3_inputs)
        field='expected_language_policy_sha256' if target=='translation' else 'expected_destination_sha256'
        values[field]='f'*64
        changed=replace(selection,inputs=replace(selection.inputs,phase3_inputs=values))
        with pytest.raises(BulkError):run_offline(result,changed,patch,destination)
    else:
        original=set(selection.authority.revoked)
        snapshot=json.loads(selection.registry.operations.contracts.read_object(selection.snapshot_sha256))
        from create_defaults.bulk.lifecycle.review import ReviewArchive
        review,_,_=ReviewArchive(selection.registry.operations.root).read(snapshot['review_id'],expected_sha256=snapshot['review_sha256'])
        try:
            selection.authority.revoked.add(review.to_dict()['decision_sha256'])
            with pytest.raises(BulkError):run_offline(result,selection,patch,destination)
        finally:
            selection.authority.revoked.clear();selection.authority.revoked.update(original)
