"""P5-T16: real encoded ADD → UPDATE → RENAME → current UPDATE."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

from create_defaults.bulk.common import fingerprint
from create_defaults.bulk.lifecycle import apply, mappings
from create_defaults.bulk.lifecycle.previews import CompositionArchive
from create_defaults.bulk.lifecycle.recovery import recover
from create_defaults.phase5.m4_tests.helpers import rename, epoch, commit_update


def test_P5_T16_native_current_mapping_sequence(m4_case):
    case=m4_case
    registry=case['row'][1].registry
    original=registry.view().entries()
    plan=rename(case,name='fixture')
    renamed=registry.view().entries()
    before_history=registry.history()
    archive=CompositionArchive(registry.operations.root,readonly=True)
    original_snapshots=[case['add_snapshot'],case['update_snapshot']]
    original_bytes={s.sha256:registry.operations.contracts.read_object(s.sha256) for s in original_snapshots}
    selected=epoch(case)
    native,tx,snapshot,result=commit_update(case,selected)
    assert result['isolated_committed'] and not result['publication_authorized']
    state=mappings.recover(selected.before.registry)
    identity=snapshot.to_dict()['members'][0]
    assert state['retained'][identity]['snapshot_sha256']==snapshot.sha256
    assert len(state['plans'])==1
    entry=registry.view().entry(identity)
    assert entry['id']==original[0]['id'] and entry['semantic']==original[0]['semantic']
    assert all(alias in entry['aliases'] for alias in renamed[0]['aliases'])
    assert entry['original_names']==original[0]['original_names']
    assert dict(namespace='public',value=renamed[0]['names']['public_path']) in entry['aliases']
    assert registry.history()[:len(before_history)]==before_history
    assert all(registry.operations.contracts.read_object(p)==raw for p,raw in original_bytes.items())
    members=[s.to_dict()['artwork'][identity] for s in (*original_snapshots,snapshot)]
    assert len({m['sha256'] for m in members})==3
    for m in members:
        assert sha256(archive.read_bytes(m['object_sha256'])).hexdigest()==m['sha256']
        assert registry.operations.contracts.read_object(m['receipt_object_sha256'])
    retry=apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=native['authority'])
    assert retry['retry'] and retry['snapshot_sha256']==snapshot.sha256
    code='''
import json,sys
from unittest.mock import patch
from create_defaults.bulk.lifecycle.identities import IdentityRegistry
from create_defaults.bulk.lifecycle.mappings import recover
from create_defaults.bulk.lifecycle.package_e import SidecarStore
with patch.object(SidecarStore,'__init__',side_effect=AssertionError('writer on recovery')):
 print(json.dumps(recover(IdentityRegistry(sys.argv[1],sys.argv[2])),sort_keys=True))
'''
    child=subprocess.run([sys.executable,'-c',code,str(registry.operations.root),registry.identity],
                         capture_output=True,text=True,timeout=300)
    assert child.returncode==0,child.stderr
    assert json.loads(child.stdout)==state
    assert len(recover(registry.operations.root)['commits'])==3
    destination=Path(os.environ.get('M4_NATIVE_EXPORT','config/ci-validation/phase5-m4/native'))
    destination.mkdir(parents=True,exist_ok=True)
    rows=[]
    for label,s in zip(('add','update','current-update'),(*original_snapshots,snapshot)):
        for view in json.loads(s.to_dict()['composition_json'])['views']:
            for member in view['members']:
                name=label+'-'+view['appearance']+'.jpg'
                (destination/name).write_bytes(archive.read_bytes(member['object_sha256']))
                receipt=json.loads(registry.operations.contracts.read_object(member['receipt_object_sha256']))
                with registry.operations.contracts.read_connection() as db:
                    worker=dict(db.execute('SELECT id,status,receipt,spec,fingerprint FROM jobs WHERE id=?',(receipt['job_id'],)).fetchone())
                rows.append(dict(file=name,member=member,receipt=receipt,worker=worker))
    proof=dict(kind='phase5-m4-native-sequence',operations=['ADD','UPDATE','RENAME','UPDATE'],
        permanent_id=identity,mapping_plan=plan.to_dict(),mapping_plan_sha256=plan.sha256,
        original_entries=original,renamed_entries=renamed,current_entry=entry,
        snapshots=[s.to_dict() for s in (*original_snapshots,snapshot)],
        snapshot_sha256=[s.sha256 for s in (*original_snapshots,snapshot)],rows=rows,
        cold_restart_verified=True,history_retained=True,exact_retry_verified=True,
        currentness=state['currentness'],isolated_only=True,
        **{k:result[k] for k in ('authenticated','operation_accepted','applied','artwork_approved',
             'contract_approved','ready','active','production_enforcement','publication_authorized')})
    proof['sha256']=fingerprint(proof)
    (destination/'sequence.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf8')
