"""M5 regression: independently bind the original M6 and M5 review namespaces."""

from dataclasses import replace
import json

import pytest

from create_defaults.bulk.common import BulkError,fingerprint
from create_defaults.bulk.contracts.expanded.graph import Snapshot
from create_defaults.bulk.contracts.evidence_consumption import consume
from create_defaults.phase3.tests.consumption_samples import assemble,input_for,graph_for
from create_defaults.phase3.tests.translation_samples import synthetic_overlay


@pytest.fixture(scope='module')
def historical_namespaces():
    from create_defaults.bulk.tests.test_contract_adoption import synthetic
    request=synthetic_overlay();other,_=synthetic('overlay.synthetic-two','Example','bigger')
    one,lp=input_for(request);two,_=input_for(replace(request,record=other,record_sha256=other.sha256))
    inputs=(one,two);data=graph_for(inputs).data()
    for item in inputs:
        value=item.request.record.to_dict();identity=value['identity']['id']
        job=json.loads(value['job_json']);definition=json.loads(value['effective_definition_json'])
        context=fingerprint(dict(identity=value['identity'],definition=definition,job=job,
            exceptions=value['historical_exceptions'],renderer=value['baseline_renderer_sha256']))
        output=data['outputs'][identity];output['context_sha256']=context
        node=data['nodes'][output['node']];node['sha256']=context
        for source in job['inputs']:
            key='asset:'+source['path']
            data['nodes'][key]=dict(kind='asset',identity=source['path'],sha256=source['sha256'],dependencies=[])
            if key not in node['dependencies']:node['dependencies'].append(key)
        key='transform:overlay'
        data['nodes'][key]=dict(kind='transform',identity='overlay',sha256=value['baseline_renderer_sha256'],dependencies=[])
        node['dependencies'].append(key)
    return assemble(inputs,lp,graph=Snapshot.create(data))


def test_both_namespaces_bind_to_the_same_record_without_rewriting_either(historical_namespaces):
    report=consume(**historical_namespaces).to_dict()
    assert report['chain_compatible'] and report['simulation_eligible']
    for item in historical_namespaces['inputs']:
        subject=item.report.to_dict()['subject'];output=historical_namespaces['graph'].index().outputs[subject['id']]
        assert output['context_sha256']!=subject['review_context_sha256']
    assert not report['ready'] and not report['active'] and not report['publication_authorized']


@pytest.mark.parametrize('mutation',['graph_context','output_node_context','record_source','record_renderer','definition','record_pin'])
def test_substitution_in_either_context_or_its_material_dependencies_fails(historical_namespaces,mutation):
    current=historical_namespaces.copy();value=current['graph'].data()
    key=next(iter(value['outputs']));row=value['outputs'][key]
    if mutation=='graph_context':row['context_sha256']='f'*64
    elif mutation=='output_node_context':value['nodes'][row['node']]['sha256']='f'*64
    elif mutation=='record_source':
        first=current['inputs'][0]
        source=json.loads(first.request.record.to_dict()['job_json'])['inputs'][0]['path']
        value['nodes']['asset:'+source]['sha256']='f'*64
    elif mutation=='record_renderer':value['nodes']['transform:overlay']['sha256']='f'*64
    elif mutation=='definition':value['nodes']['definition:'+key]['sha256']='f'*64
    else:
        item=current['inputs'][0]
        current['inputs']=(replace(item,request=replace(item.request,record_sha256='f'*64)),)+current['inputs'][1:]
    graph=Snapshot.create(value);current.update(graph=graph,expected_graph_sha256=graph.sha256)
    with pytest.raises(BulkError):consume(**current)
