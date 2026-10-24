"""Read-only M7 consultation, complete pairs, unchanged guards and no effects."""

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from create_defaults.bulk.common import BulkError,canonical,fingerprint
from create_defaults.bulk.contracts.evidence_consumption import consume,revalidate
from create_defaults.bulk.contracts.destination_preflight import evaluate as destination
from create_defaults.bulk.contracts.language_policy import ValidationSubject
from create_defaults.phase3.tests.consumption_samples import example,input_for,assemble,graph_change
from create_defaults.phase3.tests.translation_samples import ROOT,synthetic_overlay,real_package,real_resolution,request_for


@pytest.fixture(scope='module')
def chain(tmp_path_factory):return example(tmp_path_factory.mktemp('m4-boundary-fixture'))


def test_cold_import_has_no_operational_effect_or_synthetic_provider():
    code=r'''
import sys
sys.dont_write_bytecode=True
def audit(event,args):
    if event in {'os.mkdir','os.remove','os.rename','sqlite3.connect','socket.connect','socket.bind','subprocess.Popen','os.system'}:
        raise AssertionError(event)
    if event=='open':
        path,mode,flags=args
        if isinstance(mode,str) and any(c in mode for c in 'wax+'):
            raise AssertionError('write')
        if str(path).endswith('.schema.json'):
            raise AssertionError('schema read at import')
sys.addaudithook(audit)
import create_defaults.bulk.contracts.language_policy
inherited=set(sys.modules)
import create_defaults.bulk.contracts.evidence_consumption
assert not any('.simulation' in k or k.startswith('create_defaults.phase3.tests') or k.startswith('create_defaults.bulk.contracts.activation') for k in sys.modules)
assert 'create_defaults.bulk.workers' not in set(sys.modules)-inherited
print('isolated-m4-import-ok')
'''
    result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='isolated-m4-import-ok'


def test_warmed_consumption_and_replay_have_no_writes_network_images_workers_clock_or_transitions(chain,monkeypatch):
    import socket,sqlite3,time,requests
    from PIL import Image
    from create_defaults.bulk import state,workers,languages
    from create_defaults.bulk.contracts.state import ContractStore
    from create_defaults.bulk.contracts.activation.controller import Controller
    from create_defaults.bulk.contracts.activation import readiness
    expected=consume(**chain)
    observed=[]
    original=readiness.inventory
    def inspection(implementation,compatibility=None):
        assert compatibility is None
        observed.append(implementation.release.sha256)
        return original(implementation)
    def prohibited(*a,**k):raise AssertionError('M4 crossed a read-only boundary')
    with monkeypatch.context() as guard:
        guard.setattr(readiness,'inventory',inspection)
        for obj,name in [(socket,'socket'),(sqlite3,'connect'),(time,'time'),(time,'monotonic'),(time,'perf_counter'),
                         (requests.Session,'request'),(Image,'open'),(Image,'new'),(Path,'write_bytes'),(Path,'write_text'),
                         (Path,'mkdir'),(state.Store,'__init__'),(ContractStore,'__init__'),(Controller,'__init__'),
                         (workers.PersistentWorkers,'__init__'),(languages,'refresh')]:
            guard.setattr(obj,name,prohibited)
        assert consume(**chain).encoded==expected.encoded
        assert revalidate(expected,expected_sha256=expected.sha256,**chain).encoded==expected.encoded
    assert observed==[chain['expected_release_sha256']]*2


@pytest.mark.parametrize('change',['missing-package','substituted-package','release-pin','caller-bool'])
def test_m7_inventory_cannot_be_replaced_by_synthetic_readiness(chain,change):
    implementation=chain['implementation'];s=chain.copy()
    if change=='missing-package':s['implementation']=replace(implementation,packages=implementation.packages[:-1])
    elif change=='substituted-package':s['implementation']=replace(implementation,packages=(chain['inputs'][0].request.package,)+implementation.packages[1:])
    elif change=='release-pin':s['expected_release_sha256']='f'*64
    else:s['implementation']=dict(ready=True,active=True,all_gates_pass=True)
    with pytest.raises(BulkError):consume(**s)


def test_destination_real_authority_unavailable_is_explicit_not_hash_based(chain):
    ds=chain['destination_inputs']|dict(verifier=None)
    item=chain['inputs'][0]
    from create_defaults.bulk.contracts.destination_preflight import BoundTranslation
    subject=ValidationSubject.from_dict(item.report.to_dict()['subject'])
    bound=BoundTranslation(subject,subject.sha256,item.report,item.report.sha256,item.request.package,item.request.contract_sha256,item.request.rules_sha256)
    report=destination(items=(bound,),language_policy=chain['language_policy'],**ds)
    result=consume(**(chain|dict(destination=report,expected_destination_sha256=report.sha256,destination_inputs=ds))).to_dict()
    assert not result['chain_compatible'] and not result['simulation_eligible']
    assert 'm3:authority:unavailable' in result['blockers']
    assert not result['ready'] and not result['publication_authorized']


def test_complete_overlay_pair_and_partial_pair_rejection():
    from create_defaults.bulk.tests.test_contract_adoption import synthetic
    request=synthetic_overlay();other,_=synthetic('overlay.synthetic-two','Example','bigger')
    one,lp=input_for(request);two,_=input_for(replace(request,record=other,record_sha256=other.sha256))
    complete=assemble((one,two),lp)
    assert consume(**complete).to_dict()['simulation_eligible']
    with pytest.raises(BulkError):assemble((one,),lp)
    # A scoped graph may not silently drop the other member: M5's own closed
    # companion validator rejects it. A full graph plus partial intake blocks.


def test_partial_overlay_intake_with_full_graph_is_blocked():
    from create_defaults.bulk.tests.test_contract_adoption import synthetic
    request=synthetic_overlay();other,_=synthetic('overlay.synthetic-two','Example','bigger')
    one,lp=input_for(request);two,_=input_for(replace(request,record=other,record_sha256=other.sha256))
    complete=assemble((one,two),lp)
    partial=assemble((one,),lp,graph=complete['graph'])
    result=consume(**partial).to_dict()
    assert not result['chain_compatible'] and not result['simulation_eligible']
    assert 'missing_graph_companions' in result['blockers']


def test_private_captionless_context_needs_no_remote_grant_but_preserves_m7_gates(tmp_path):
    result=consume(**example(tmp_path,mode='none',public=False)).to_dict()
    assert result['chain_compatible'] and not result['simulation_eligible']
    assert result['subjects'][0]['selection_sha256'] is None
    assert not result['ready'] and result['m7']['exact_approvals_missing']==22


def test_actual_existing_playlist_contract_remains_unapproved_without_repeating_full_history():
    package=real_package();_,members=package.data()
    resolution=real_resolution()
    identity=next(iter(resolution.data()['expanded']))
    member=members[identity]
    request=request_for(resolution,package,identity=identity,variant=member['variant'])
    request=replace(request,review_context_sha256=member['context_sha256'])
    item,lp=input_for(request)
    # The small graph is explicitly synthetic, using unchanged real definition,
    # selected historical exceptions and review context. This is not a fabricated
    # whole-library audit; the existing mandatory historical job supplies that.
    result=consume(**assemble((item,),lp)).to_dict()
    assert 'm7:selected_package_not_current_m6_release' not in result['blockers']
    assert 'm7:missing_exact_hash_maintainer_approval' in result['blockers']
    assert not result['technical_eligible']


def test_all_prior_test_ids_and_frozen_interfaces_are_preserved():
    base='f8c5782fa0609fe34642f7b0c121538d2c9f7c4c'
    previous=json.loads(subprocess.check_output(['git','show',base+':ci/phase3-test-ids.json'],cwd=ROOT))
    current=json.loads((ROOT/'ci/phase3-test-ids.json').read_text())
    assert len(previous)==529 and set(previous)<=set(current)
    for name in ['ci/original-test-ids.json','ci/validation-plan.json','ci/phase3.py','.github/workflows/default-poster-validation.yml',
                 'create_defaults/phase3/tests/golden-v1.json','create_defaults/phase3/tests/translation-preflight-v1.json',
                 'create_defaults/phase3/tests/destination-preflight-v1.json',
                 'create_defaults/bulk/contracts/language_policy/schemas/foundations-v1.schema.json',
                 'create_defaults/bulk/contracts/translation_preflight/evidence-v1.schema.json',
                 'create_defaults/bulk/contracts/destination_preflight/evidence-v1.schema.json',
                 'create_defaults/bulk/contracts/activation/data/production-pins-v1.json']:
        original=subprocess.check_output(['git','show',base+':'+name],cwd=ROOT)
        if name in {'.github/workflows/default-poster-validation.yml',
                    'create_defaults/bulk/contracts/activation/data/production-pins-v1.json'}:
            from hashlib import sha256
            from ci.phase4 import verify_maintenance
            # Verify exact historical bytes AND the narrowly approved current
            # maintenance bytes. Other schema/vector/selection pins stay frozen.
            maintenance=verify_maintenance()
            assert sha256(original.replace(b'\r\n',b'\n')).hexdigest()==maintenance['files'][name]['before_sha256']
        elif name=='ci/validation-plan.json':
            from ci.phase4 import verify_original_plan
            verify_original_plan(original)
        else:
            assert original.replace(b'\r\n',b'\n')==(ROOT/name).read_bytes().replace(b'\r\n',b'\n')
