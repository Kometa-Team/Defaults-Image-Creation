"""Cold imports, real storage under operational fault hooks, and scope preservation."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from create_defaults.bulk.common import BulkError
from create_defaults.bulk.lifecycle.models import Operation
from create_defaults.bulk.lifecycle.storage import OperationStore
from .samples import sample,append,next_record

ROOT=Path(__file__).resolve().parents[3]


def test_cold_import_does_not_read_schema_write_open_state_render_network_or_activate():
    code=r'''
import sys
sys.dont_write_bytecode=True
def guard(event,args):
    if event in {'os.mkdir','os.remove','os.rename','sqlite3.connect','socket.connect','socket.bind','subprocess.Popen','os.system'}:
        raise AssertionError('cold import side effect: '+event)
    if event=='open':
        path,mode,flags=args
        if isinstance(mode,str) and any(c in mode for c in 'wax+'):
            raise AssertionError('cold import write')
        if str(path).endswith('operations-v1.schema.json'):
            raise AssertionError('schema IO at import')
sys.addaudithook(guard)
def profile(frame,event,arg):
    if event=='call':
        module=frame.f_globals.get('__name__','');name=frame.f_code.co_name
        if module=='create_defaults.create_poster' and name in {'render_poster','create_poster','load_image'}:
            raise AssertionError('renderer execution during import')
        if module=='create_defaults.bulk.workers' and name in {'compose','_worker_main','__init__'}:
            raise AssertionError('worker execution during import')
sys.setprofile(profile)
from create_defaults.bulk.lifecycle import models,storage
assert 'create_defaults.bulk.contracts.activation.controller' not in sys.modules
assert 'create_defaults.bulk.operator_publication' not in sys.modules
assert not hasattr(storage,'execute') and not hasattr(storage,'Controller')
sys.setprofile(None)
print('record-foundations-import-isolated')
'''
    result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='record-foundations-import-isolated'


def test_real_append_cancel_restart_and_inspection_cannot_call_operational_interfaces(tmp_path,monkeypatch):
    import requests,socket
    from PIL import Image
    from create_defaults.bulk import workers,remote,operator_publication
    from create_defaults import create_poster
    from create_defaults.bulk.contracts.activation.controller import Controller
    from create_defaults.bulk.contracts.language_policy.authority import AuthorityResult,AuthorityStatus
    def prohibited(*a,**k):raise AssertionError('Record storage invoked an operational interface')
    store=OperationStore.create(tmp_path/'isolated');r=sample();Operation.from_bytes(r.encoded)
    with monkeypatch.context() as guard:
        for obj,name in [(requests.Session,'request'),(socket,'socket'),(Image,'open'),
            (workers.PersistentWorkers,'__init__'),(remote.ReadOnlyGitHub,'__init__'),
            (create_poster,'create_poster'),(create_poster,'render_poster'),
            (operator_publication,'stage'),(operator_publication,'draft'),
            (Controller,'__init__'),(Controller,'transition')]:guard.setattr(obj,name,prohibited)
        append(store,r);cancelled=next_record(store,r,state='cancelled');append(store,cancelled)
        reopened=OperationStore(store.root)
        assert reopened.history(r.to_dict()['id'])==(r,cancelled)
        report=reopened.inspect();assert not report['applied'] and not report['operation_accepted']
        assert report['operations'][0]['state']=='cancelled'
    for status in AuthorityStatus:
        authority=AuthorityResult(status,'f'*64)
        assert not authority.readiness_authorized and not authority.publication_authorized


def test_record_state_cannot_authenticate_actor_or_accept_a_real_subject(tmp_path):
    store=OperationStore.create(tmp_path/'isolated')
    for field,value in [('reviewer','maintainer'),('trusted',True),('synthetic',False),('approval_sha256','f'*64)]:
        v=sample().to_dict();v[field]=value
        with pytest.raises(BulkError):append(store,Operation.from_dict(v))
    v=sample().to_dict();v['subjects'][0]['id']='playlist.playlist-arrowverse-timeline-order.09b7e4b8'
    with pytest.raises(BulkError):Operation.from_dict(v)
    assert store.inspect()['records']==0


def test_immutable_store_uses_one_package_e_database_and_no_private_storage_api(tmp_path):
    import ast
    store=OperationStore.create(tmp_path/'isolated');append(store,sample())
    assert [p.name for p in store.root.glob('*.sqlite*') if p.suffix not in {'.sqlite3-wal','.sqlite3-shm'}]==['state.sqlite3']
    for name in ['storage.py','package_e.py']:
        tree=ast.parse((ROOT/'create_defaults/bulk/lifecycle'/name).read_text(encoding='utf8'))
        assert not any(isinstance(n,ast.Attribute) and n.attr in {'_store','_write_blob','_blob_path'} for n in ast.walk(tree))
    # The additive public bridge must not alter any frozen M2 source pin.
    from create_defaults.bulk.contracts.adoption.sources import load_pins,verify_sources
    verify_sources(load_pins())


def test_archive_event_and_record_vectors_match_fixed_cross_platform_evidence(tmp_path):
    from create_defaults.bulk.common import fingerprint
    from ci.validation import identity,write
    store=OperationStore.create(tmp_path/'isolated')
    records=[];events=[]
    for kind in ['ADD','UPDATE','RENAME','DELETE']:
        r=sample(store,name=kind.lower(),operation=kind,subjects=(kind.lower(),),paths=['posters/Pokémon-'+kind+'.jpg'])
        records.append(r.to_dict());events.append(append(store,r).to_dict())
    evidence=dict(records=records,events=events,inspection=store.inspect())
    fixture=json.loads(Path(__file__).with_name('canonical-v1.json').read_text(encoding='utf8'))
    assert evidence==fixture['archive'] and fingerprint(evidence)==fixture['archive_sha256']
    write(ROOT/'config/phase4-ci/phase4-canonical.json',
        {**identity(),'evidence':evidence,'evidence_sha256':fingerprint(evidence)})
