"""No provider import, network, rendering, writes or production activation."""

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from create_defaults.bulk.common import BulkError,canonical,fingerprint
from create_defaults.bulk.contracts.destination_preflight import evaluate,DestinationAttestation,DestinationInventory
from create_defaults.phase3.tests.destination_samples import poster,scenario,bound
from create_defaults.phase3.tests.translation_samples import ROOT,CATALOG,real_package,request_for,snapshot_for


def test_cold_import_has_no_io_or_test_authority_dependency():
    code=r'''
import sys
sys.dont_write_bytecode=True
def audit(event,args):
    if event in {'os.mkdir','os.remove','os.rename','sqlite3.connect','socket.connect','socket.bind','subprocess.Popen','os.system'}:
        raise AssertionError('side effect: '+event)
    if event=='open':
        path,mode,flags=args
        if isinstance(mode,str) and any(c in mode for c in 'wax+'):
            raise AssertionError('write')
        if str(path).endswith('.schema.json'):
            raise AssertionError('import-time schema read')
sys.addaudithook(audit)
import create_defaults.bulk.contracts.language_policy
inherited=set(sys.modules)
import create_defaults.bulk.contracts.destination_preflight
assert not any('.simulation' in k or k.startswith('create_defaults.phase3.tests') or k.startswith('create_defaults.bulk.contracts.activation') for k in sys.modules)
assert 'create_defaults.bulk.workers' not in set(sys.modules)-inherited
print('isolated-m3-import-ok')
'''
    result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='isolated-m3-import-ok'


def test_warmed_inspection_is_entirely_read_only_without_clocks(tmp_path,monkeypatch):
    item,lp=poster(tmp_path);s=scenario((item,),lp);expected=evaluate(**s)
    import time,socket,sqlite3,requests
    from PIL import Image
    from create_defaults.bulk import state,workers
    def prohibited(*a,**k):raise AssertionError('Destination inspection invoked an operational effect')
    with monkeypatch.context() as guard:
        for obj,name in [(time,'time'),(time,'monotonic'),(time,'perf_counter'),(socket,'socket'),(sqlite3,'connect'),
                         (requests.Session,'request'),(Image,'open'),(Image,'new'),(Path,'read_bytes'),(Path,'read_text'),
                         (Path,'write_bytes'),(Path,'write_text'),(Path,'mkdir'),(state.Store,'__init__'),(workers.PersistentWorkers,'__init__')]:
            guard.setattr(obj,name,prohibited)
        assert evaluate(**s).encoded==expected.encoded


def test_both_actual_historical_awards_intermediates_remain_private():
    from create_defaults.bulk.contracts.expanded.resolution import resolve
    resolution=resolve([CATALOG/'awards.yml'])
    package=real_package('Awards');_,members=package.data()
    private=[d['id'] for d in resolution.data()['expanded'].values() if d['output']['remote_paths'].get('en') is None]
    assert len(private)==2
    raw=(ROOT/'create_defaults/fixtures/english/en.yml').read_bytes()
    for identity in private:
        request=request_for(resolution,package,identity=identity,variant=members[identity]['variant'])
        item,lp=bound(request,snapshot=snapshot_for({'en':raw}))
        assert item.translation.to_dict()['technical_eligible']
        result=evaluate(**scenario((item,),lp)).to_dict()
        assert result['policy_route']=='private_only' and result['target'] is None
        assert result['outputs'][0]['target_path'] is None and result['complete']
        assert not result['publication_authorized'] and not result['technical_eligible']


@pytest.mark.parametrize('provider',['bool','dict','wrong-pin','no-facts'])
def test_untyped_or_self_signed_provider_outcomes_cannot_grant(tmp_path,provider):
    from create_defaults.bulk.contracts.language_policy import AuthorityResult
    from create_defaults.bulk.contracts.language_policy.authority import AuthorityStatus
    item,lp=poster(tmp_path);s=scenario((item,),lp)
    class Invalid:
        def verify(self,evidence,context):
            if provider=='bool':return True
            if provider=='dict':return dict(status='verified',owner_verified=True)
            return AuthorityResult(AuthorityStatus.SYNTHETIC_ONLY,'f'*64 if provider=='wrong-pin' else evidence.sha256)
    if provider=='no-facts':
        result=evaluate(**(s|dict(verifier=Invalid()))).to_dict()
        assert not result['technical_eligible'] and not result['simulation_eligible']
    else:
        with pytest.raises(BulkError):evaluate(**(s|dict(verifier=Invalid())))


@pytest.mark.parametrize('kind',['attestation','inventory'])
def test_oversized_metadata_returns_no_truncated_report(kind):
    cls=DestinationAttestation if kind=='attestation' else DestinationInventory
    with pytest.raises(BulkError):cls.from_bytes(b' '*(8*1024*1024+1))


def test_all_previous_additive_ids_schemas_vectors_and_workflow_are_preserved():
    base='6add7daa21e0d9570c73be9bae9901baa6047244'
    previous=json.loads(subprocess.check_output(['git','show',base+':ci/phase3-test-ids.json'],cwd=ROOT))
    current=json.loads((ROOT/'ci/phase3-test-ids.json').read_text())
    assert len(previous)==387 and set(previous)<=set(current)
    for name in ['ci/original-test-ids.json','ci/validation-plan.json','ci/phase3.py',
                 '.github/workflows/default-poster-validation.yml',
                 'create_defaults/phase3/tests/golden-v1.json','create_defaults/phase3/tests/translation-preflight-v1.json',
                 'create_defaults/bulk/contracts/language_policy/schemas/foundations-v1.schema.json',
                 'create_defaults/bulk/contracts/translation_preflight/evidence-v1.schema.json',
                 'create_defaults/bulk/contracts/activation/data/production-pins-v1.json']:
        old=subprocess.check_output(['git','show',base+':'+name],cwd=ROOT)
        if name in {'.github/workflows/default-poster-validation.yml',
                    'create_defaults/bulk/contracts/activation/data/production-pins-v1.json'}:
            from hashlib import sha256
            from ci.phase4 import verify_maintenance
            # Verify exact historical bytes AND the narrowly approved current
            # maintenance bytes. Other schema/vector/selection pins stay frozen.
            maintenance=verify_maintenance()
            assert sha256(old.replace(b'\r\n',b'\n')).hexdigest()==maintenance['files'][name]['before_sha256']
        else:
            assert old.replace(b'\r\n',b'\n')==(ROOT/name).read_bytes().replace(b'\r\n',b'\n')


def test_full_canonical_destination_fixture_matches_on_both_platforms(tmp_path):
    item,lp=poster(tmp_path,language='fr',filename='Élan — Noël.jpg')
    result=evaluate(**scenario((item,),lp,root='Reviewed/French'))
    expected=json.loads((ROOT/'create_defaults/phase3/tests/destination-preflight-v1.json').read_text(encoding='utf8'))
    assert result.to_dict()==expected['evidence']
    assert result.sha256==expected['sha256']==fingerprint(expected['evidence'])
