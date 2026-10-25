"""Dependency, companion and private-parent negative controls, without pixels."""
from copy import deepcopy

import pytest

from create_defaults.bulk.common import BulkError, fingerprint
from create_defaults.bulk.contracts.expanded.graph import Snapshot
from create_defaults.bulk.lifecycle.retirement import validate_delete


def graph(*,companion=False,dependent=False,unresolved=False):
    nodes={};outputs={}
    for i in ('parent','child'):
        node='output:'+i
        nodes[node]=dict(kind='output',identity=i,sha256=fingerprint(i),
            dependencies=['output:parent'] if i=='child' and dependent else [])
        outputs[i]=dict(node=node,category='Genre',kind='poster',variant='test',
            local_path='defaults-en/genre/'+i+'.jpg',public_path='genre/'+i+'.jpg',
            companions=[('child' if i=='parent' else 'parent')] if companion else [],
            evidence=dict(previews=[],confirmations=[],decisions=[],receipts=[]),context_sha256=fingerprint(i))
    return Snapshot.create(dict(schema_version=1,kind='m5-dependency-snapshot',basis='a'*64,
        nodes=nodes,outputs=outputs,unresolved=['unknown'] if unresolved else []))


def entries():
    return {i:dict(semantic=dict(role='single',key=i,parent=None),tombstone_sha256=None) for i in ('parent','child')}


@pytest.mark.parametrize('attack',['companion','dependent','private-parent','child','generated','container','unknown','unresolved'])
def test_retirement_rejects_incomplete_or_uncertain_impact(attack):
    value=entries();g=graph(companion=attack=='companion',dependent=attack in {'dependent','private-parent'},unresolved=attack=='unresolved')
    if attack=='child':value['child']['semantic']['parent']='parent'
    if attack=='generated':value['parent']['semantic']['key']='year:2026'
    if attack=='container':value['parent']['semantic']['role']='family'
    with pytest.raises(BulkError):validate_delete(g.index(),value,['unknown' if attack=='unknown' else 'parent'])


@pytest.mark.parametrize('paired,dependent',[(True,False),(False,True),(True,True),(False,False)])
def test_complete_retirement_has_no_orphaned_retained_consumer(paired,dependent):
    validate_delete(graph(companion=paired,dependent=dependent).index(),entries(),['parent','child'])


def test_unselected_dependent_identity_and_edge_remain_literal():
    g=graph(dependent=True);before=deepcopy(g.data())
    validate_delete(g.index(),entries(),['child'])
    assert g.data()==before and g.index().nodes['output:child']['dependencies']==['output:parent']


def test_confinement_does_not_canonicalize_case_only_journal_paths(tmp_path):
    from create_defaults.bulk.lifecycle.mapping_moves import _path,_literal,_move
    from create_defaults.bulk.common import sha256
    old=tmp_path/'Fixture.jpg';old.write_bytes(b'fixture')
    pin=sha256(old);temporary=tmp_path/'intermediate.m6'
    _move(_path(tmp_path,'Fixture.jpg'),temporary,pin)
    _move(temporary,_path(tmp_path,'fixture.jpg'),pin)
    assert _path(tmp_path,'Fixture.jpg').name=='Fixture.jpg'
    assert not _literal(_path(tmp_path,'Fixture.jpg'))
    assert _literal(_path(tmp_path,'fixture.jpg'))
