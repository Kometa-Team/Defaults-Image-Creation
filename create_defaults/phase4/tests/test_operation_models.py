"""Closed synthetic operation representation and independent canonical vectors."""
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import pytest

from create_defaults.bulk.common import BulkError,canonical,fingerprint
from create_defaults.bulk.lifecycle.models import Operation,HeadRef,Event,namespace_key
from .samples import sample


@pytest.mark.parametrize('kind',['ADD','UPDATE','RENAME','DELETE'])
def test_each_operation_is_immutable_canonical_record_data_only(kind):
    r=sample(operation=kind,subjects=('a','b'),paths=['posters/Pokémon.jpg'])
    assert Operation.from_bytes(r.encoded).sha256==r.sha256==fingerprint(r.to_dict())
    assert tuple(h.to_dict() for h in r.read_set)==tuple(r.to_dict()['reads'])
    assert tuple(h.to_dict() for h in r.write_set)==tuple(r.to_dict()['writes'])
    v=r.to_dict();v['subjects'][0]['id']='synthetic.foreign';assert r.to_dict()!=v
    with pytest.raises(FrozenInstanceError):r.encoded=b'{}'
    for flag in ['operation_accepted','applied','artwork_approved','contract_approved','ready','active','production_enforcement','publication_authorized']:
        assert r.to_dict()[flag] is False


@pytest.mark.parametrize('field,value',[
 ('schema_version',2),('schema_version',True),('protocol_version','2.0.0'),('kind','maintainer-approval'),
 ('scope','production'),('simulation',False),('record_only',False),('operation','PUBLISH'),
 ('state','approved'),('state','READY'),('state','ACTIVE'),('state','previews_complete'),
 ('state','locally_committed'),('state','unknown'),('id','../../escape'),('id','playlist.real'),
 ('id','synthetic.operation.bad\n'),('revision',0),('revision',True),('content_revision',2),
 ('previous_sha256','f'*64),('previous_event_sha256','f'*64),('request_sha256','A'*64),
 ('request_sha256','f'*63),('reason','not valid in draft'),('operation_accepted',True),
 ('applied',True),('contract_approved',True),('artwork_approved',True),('ready',True),
 ('active',True),('production_enforcement',True),('publication_authorized',True),
 ('actor','maintainer'),('compatibility',True),('approved',True),('renderer','injected'),
 ('subjects',[]),('writes',[]),('reads',[]),
])
def test_unknown_fields_versions_states_grants_and_malformed_headers_fail(field,value):
    v=sample().to_dict();v[field]=value
    with pytest.raises(BulkError):Operation.from_dict(v)


@pytest.mark.parametrize('mutation',['subject-duplicate','subject-order','foreign-subject','before','proposed',
    'read-duplicate','read-order','missing-subject-head','foreign-read-subject','wrong-subject-owner',
    'read-hash','read-revision','write-duplicate','foreign-write','namespace-path','namespace-owner',
    'namespace-missing','namespace-extra','namespace-duplicate','namespace-nfd','reference-owner',
    'reference-duplicate','reference-hash','reference-extra','tombstone-in-update','nested-override'])
def test_nested_reference_membership_namespace_and_override_substitution_fail(mutation):
    v=sample(subjects=('a','b'),paths=['posters/Pokémon.jpg']).to_dict()
    if mutation=='subject-duplicate':v['subjects'].append(v['subjects'][0])
    elif mutation=='subject-order':v['subjects'].reverse()
    elif mutation=='foreign-subject':v['subjects'][0]['id']='playlist.actual'
    elif mutation=='before':v['subjects'][0]['before_sha256']=None
    elif mutation=='proposed':v['subjects'][0]['proposed_sha256']=None
    elif mutation=='read-duplicate':v['reads'].append(v['reads'][0])
    elif mutation=='read-order':v['reads'].reverse()
    elif mutation=='missing-subject-head':v['reads']=[r for r in v['reads'] if r['id']!=v['subjects'][0]['id']]
    elif mutation=='foreign-read-subject':v['reads'][0]['subjects']=['synthetic.foreign']
    elif mutation=='wrong-subject-owner':v['reads'][-1]['subjects']=[v['subjects'][0]['id']]
    elif mutation=='read-hash':v['reads'][0]['sha256']='f'*64
    elif mutation=='read-revision':v['reads'][0]['revision']=1
    elif mutation=='write-duplicate':v['writes'].append(v['writes'][0])
    elif mutation=='foreign-write':v['writes'][0]['id']='synthetic.unknown'
    elif mutation=='namespace-path':v['namespaces'][0]['path']='../escape.jpg'
    elif mutation=='namespace-owner':v['namespaces'][0]['subjects']=['synthetic.foreign']
    elif mutation=='namespace-missing':v['namespaces']=[]
    elif mutation=='namespace-extra':v['reads']=[r for r in v['reads'] if r['kind']!='namespace']
    elif mutation=='namespace-duplicate':v['namespaces']*=2
    elif mutation=='namespace-nfd':v['namespaces'][0]['path']='posters/Poke\u0301mon.jpg'
    elif mutation=='reference-owner':v['references']=[dict(kind='evidence',id='synthetic.ref',subject='synthetic.foreign',sha256='a'*64)]
    elif mutation=='reference-duplicate':
        v['references']=[dict(kind='dependency',id='synthetic.ref',subject=v['subjects'][0]['id'],sha256='a'*64)]*2
    elif mutation=='reference-hash':v['references']=[dict(kind='dependency',id='synthetic.ref',subject=v['subjects'][0]['id'],sha256='a'*63)]
    elif mutation=='reference-extra':v['references']=[dict(kind='evidence',id='synthetic.ref',subject=v['subjects'][0]['id'],sha256='a'*64,approved=True)]
    elif mutation=='tombstone-in-update':v['references']=[dict(kind='tombstone',id='synthetic.ref',subject=v['subjects'][0]['id'],sha256='a'*64)]
    else:v['subjects'][0]['font']='injected-font'
    with pytest.raises(BulkError):Operation.from_dict(v)


@pytest.mark.parametrize('raw',[b'{',b'\xff',b'{"id":"one","id":"two"}',b'NaN',b'Infinity',b'"\\ud800"',b'{}'])
def test_malformed_duplicate_nonfinite_and_invalid_json_is_rejected(raw):
    with pytest.raises(BulkError):Operation.from_bytes(raw)


@pytest.mark.parametrize('field',['before_sha256','proposed_sha256'])
def test_add_and_delete_reference_roles_are_not_interchangeable(field):
    v=sample(operation='ADD' if field=='before_sha256' else 'DELETE').to_dict();v['subjects'][0][field]='f'*64
    with pytest.raises(BulkError):Operation.from_dict(v)


def test_delete_requires_exact_tombstone_reference_for_every_subject():
    v=sample(operation='DELETE',subjects=('a','b')).to_dict();v['references'].pop()
    with pytest.raises(BulkError):Operation.from_dict(v)


def test_namespace_coordination_detects_case_aliases_without_rewriting_names():
    assert namespace_key('synthetic.repo','Posters/Name.jpg')==namespace_key('synthetic.repo','posters/name.jpg')
    assert sample(paths=['Posters/Pokémon.jpg']).to_dict()['namespaces'][0]['path']=='Posters/Pokémon.jpg'


def test_oversize_and_deep_metadata_remains_bounded():
    with pytest.raises(BulkError):Operation.from_bytes(b' '* (8*1024*1024+1))
    with pytest.raises(BulkError):Operation.from_bytes(b'['*100+b'0'+b']'*100)


def test_fixed_cross_platform_records_match_the_complete_frozen_vectors():
    expected=json.loads(Path(__file__).with_name('canonical-v1.json').read_text(encoding='utf8'))
    actual={kind:dict(value=sample(operation=kind,paths=['posters/Pokémon.jpg']).to_dict(),
        sha256=sample(operation=kind,paths=['posters/Pokémon.jpg']).sha256) for kind in ['ADD','UPDATE','RENAME','DELETE']}
    assert actual==expected['records']


@pytest.mark.parametrize('mutation',['global-sequence','operation-sequence','record-parent','event-parent','duplicate-change','head-revision','head-sha','subject','ready'])
def test_journal_values_reject_inconsistent_chain_head_and_subject_fields(mutation):
    fixture=json.loads(Path(__file__).with_name('canonical-v1.json').read_text(encoding='utf8'))
    v=fixture['archive']['events'][0]
    if mutation=='global-sequence':v['sequence']=2
    elif mutation=='operation-sequence':v['operation_revision']=2
    elif mutation=='record-parent':v['previous_record_sha256']='f'*64
    elif mutation=='event-parent':v['previous_operation_event_sha256']='f'*64
    elif mutation=='duplicate-change':v['changes']*=2
    elif mutation=='head-revision':v['changes'][0]['after']['revision']=3
    elif mutation=='head-sha':v['changes'][0]['after']['sha256']='f'*64
    elif mutation=='subject':v['changes'][-1]['subjects']=['synthetic.foreign']
    else:v['ready']=True
    with pytest.raises(BulkError):Event.from_dict(v)
