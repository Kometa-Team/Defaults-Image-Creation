"""Strict additive review values and isolation without a raster fixture."""
from copy import deepcopy
import subprocess
import sys

import pytest

from create_defaults.bulk.common import BulkError
from create_defaults.bulk.lifecycle.evidence import HEADER, ReviewDecision, ReviewState
from create_defaults.bulk.lifecycle.review import ReviewArchive
from create_defaults.bulk.lifecycle.storage import OperationStore


def record():
    return dict(**HEADER,kind='composition-review-decision',review_id='synthetic.review.schema',
        bundle_sha256='a'*64,context_sha256='b'*64,previous_sha256='c'*64,
        actor='synthetic.actor.submitter',role='submitter',action='confirm',confirmation_sha256=None)


def test_review_canonical_value_roundtrip_never_authenticates():
    value=ReviewDecision.from_dict(record())
    assert ReviewDecision.from_bytes(value.encoded)==value
    assert value.sha256==ReviewDecision.from_dict(dict(reversed(list(record().items())))).sha256
    assert not value.to_dict()['authenticated'] and not value.to_dict()['artwork_approved']


@pytest.mark.parametrize('attack',['missing','unknown','version','protocol','real-id','actor-newline','wrong-role','skipped-confirmation','authenticated','artwork_approved','contract_approved','ready','active','publication_authorized','production_enforcement','operation_accepted','applied','hash','noncanonical'])
def test_closed_review_schema_cannot_smuggle_authority_or_scope(attack):
    value=record()
    if attack=='missing':value.pop('bundle_sha256')
    elif attack=='unknown':value['approved']=True
    elif attack=='version':value['schema_version']=2
    elif attack=='protocol':value['protocol_version']='latest'
    elif attack=='real-id':value['review_id']='review.actual'
    elif attack=='actor-newline':value['actor']+='\n'
    elif attack=='wrong-role':value['role']='maintainer'
    elif attack=='skipped-confirmation':value.update(role='maintainer',action='approve')
    elif attack=='hash':value['context_sha256']='not-a-hash'
    elif attack=='noncanonical':
        with pytest.raises(BulkError):ReviewDecision.from_bytes(ReviewDecision.from_dict(value).encoded+b'\n')
        return
    else:value[attack]=True
    with pytest.raises(BulkError):ReviewDecision.from_dict(value)


def test_review_namespace_creation_is_explicit_readonly_open_never_repairs(tmp_path):
    root=tmp_path/'state'
    OperationStore.create(root)
    with pytest.raises(BulkError):ReviewArchive(root)
    archive=ReviewArchive.create(root)
    assert archive.history()=={}
    assert OperationStore(root).inspect()['records']==0
    assert ReviewArchive.create(root).history()=={}


def test_partial_review_namespace_is_rejected_without_repair(tmp_path):
    root=tmp_path/'state'
    OperationStore.create(root)
    from create_defaults.bulk.lifecycle.package_e import SidecarStore
    writer=SidecarStore(root)
    with writer.transaction() as db:db.execute('CREATE TABLE p4m4_foreign (value TEXT)')
    with pytest.raises(BulkError,match='archive_namespace'):ReviewArchive.create(root)


def test_review_import_has_no_writes_workers_authority_or_activation():
    script='''
import sys
sys.dont_write_bytecode=True
def guard(event,args):
    if event in ('socket.connect','subprocess.Popen','os.mkdir','os.remove','os.rename'):
        raise AssertionError(event)
    if event=='open' and isinstance(args[1],str) and any(c in args[1] for c in 'wax+'):
        raise AssertionError('write on import')
    if event=='import' and any(s in args[0] for s in ('activation.controller','operator_publication','library_stage')):
        raise AssertionError('production integration imported')
sys.addaudithook(guard)
import create_defaults.bulk.lifecycle.review
import create_defaults.bulk.lifecycle.evidence
import create_defaults.bulk.lifecycle.review_authority
'''
    result=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
