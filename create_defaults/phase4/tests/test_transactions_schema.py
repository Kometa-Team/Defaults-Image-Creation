"""M5 protocol closure and equivalence with the frozen original CAS engine."""
from copy import deepcopy
from types import SimpleNamespace
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from create_defaults.bulk.common import BulkError, Conflict, fingerprint
from create_defaults.bulk.lifecycle.operations import HEADER, DefinitionSnapshot, validator
from create_defaults.bulk.lifecycle import apply
from create_defaults.bulk.lifecycle.package_e import SidecarStore
from create_defaults.bulk.lifecycle.storage import OperationStore, _replay
from create_defaults.bulk.lifecycle.recovery import _successor
from create_defaults.phase4.tests.samples import sample,append


def test_closed_versioned_schema_preserves_all_real_authority_blocks():
    schema=validator().schema
    assert schema['additionalProperties'] is False
    assert set(schema['required'])==set(schema['properties'])
    for key,value in HEADER.items():assert schema['properties'][key]=={'const':value}
    assert schema['properties']['operation_type']['enum']==['ADD','UPDATE']
    assert schema['properties']['members']['maxItems']==32
    assert schema['properties']['artwork']['maxProperties']==32


@pytest.mark.parametrize('key',['schema_version','protocol_version','scope','simulation','authenticated','operation_accepted','applied','ready','active','publication_authorized'])
def test_unknown_protocol_and_operational_claims_are_not_values(key):
    # Inspect the actual field validator independently of a missing payload.
    schema=validator().schema['properties'][key]
    from create_defaults.bulk.definitions import StrictValidator
    accepted=HEADER[key]
    wrong=not accepted if type(accepted) is bool else 99 if type(accepted) is int else 'forged'
    assert not list(StrictValidator(schema).iter_errors(accepted))
    assert list(StrictValidator(schema).iter_errors(wrong))


def test_m5_atomic_bridge_produces_exact_original_m1_archive(tmp_path):
    stores=[OperationStore.create(tmp_path/name) for name in ('original','coordinator')]
    event=None
    record=sample(name='equivalence',operation='ADD')
    for store in stores:event=append(store,record)
    pin=SimpleNamespace(sha256=fingerprint('structural-test-only'),to_dict=lambda:{})
    marker=_successor(pin,record,event)
    expected=append(stores[0],marker)
    writer=SidecarStore(stores[1].root)
    with writer.transaction() as db:
        records,events,latest,heads=_replay(writer,db)
        actual=apply._append_m1(writer,db,marker,records,events,latest,heads)
    assert actual==expected
    assert stores[0].inspect()==stores[1].inspect()
    assert stores[0].history(record.to_dict()['id'])==stores[1].history(record.to_dict()['id'])
    assert stores[0].journal()==stores[1].journal()


def test_m5_atomic_bridge_cannot_skip_original_dependency_cas(tmp_path):
    store=OperationStore.create(tmp_path/'state');r=sample(name='cas',operation='ADD');event=append(store,r)
    marker=_successor(SimpleNamespace(sha256=fingerprint('snapshot'),to_dict=lambda:{}),r,event)
    from create_defaults.phase4.tests.samples import next_record
    append(store,next_record(store,r))
    before=store.inspect();writer=SidecarStore(store.root)
    with pytest.raises(Conflict):
        with writer.transaction() as db:
            records,events,latest,heads=_replay(writer,db)
            apply._append_m1(writer,db,marker,records,events,latest,heads)
    assert store.inspect()==before


def test_cold_import_has_no_state_render_network_or_production_hook():
    source='''
import builtins,socket,sqlite3
from unittest.mock import patch
with patch.object(sqlite3,'connect',side_effect=AssertionError('state opened')), patch.object(socket,'socket',side_effect=AssertionError('network')):
 import create_defaults.bulk.lifecycle.operations
 import create_defaults.bulk.lifecycle.apply
 import create_defaults.bulk.lifecycle.recovery
'''
    import sys
    result=subprocess.run([sys.executable,'-c',source],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_operational_path_fails_before_any_storage_or_render():
    with patch.object(SidecarStore,'__init__',side_effect=AssertionError('write')):
        with pytest.raises(BulkError,match='real_authority_unavailable'):
            apply.commit_operational({'actor':'maintainer','authenticated':True})


def test_recovery_bounds_unindexed_commit_events_before_materialization(tmp_path):
    from create_defaults.bulk.lifecycle.recovery import recover,MAX_EVENTS
    store=OperationStore.create(tmp_path/'state');writer=SidecarStore(store.root)
    with writer.transaction() as db:
        for n in range(MAX_EVENTS+1):
            writer.event(db,'phase4_isolated_commit','synthetic.operation.orphan-'+str(n),{'untrusted':'event'})
    with pytest.raises(BulkError,match='archive_limit'):recover(store.root)
