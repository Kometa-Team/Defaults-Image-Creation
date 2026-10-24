"""Additive reconciliation over the existing shared historical capture only."""
from create_defaults.bulk.common import fingerprint


def reconcile(registry,records,resolution,graph,implementation):
    from create_defaults.bulk.lifecycle.basis import MAPPING_SHA256,HISTORICAL_GRAPH_SHA256
    from create_defaults.bulk.contracts.adoption.models import read_canonical
    from create_defaults.bulk.lifecycle.basis import semantic_tokens
    from ci.validation import identity,write,OUTPUT
    from ci.phase4 import M2_HISTORICAL
    from create_defaults.bulk.contracts.adoption.sources import load_pins,verify_sources
    from create_defaults.bulk.contracts.activation.protection import verify
    pins=load_pins();assert len(pins['files'])==299;verify_sources(pins)
    assert verify()['production_files_verified']==190
    index=graph.index();assert graph.sha256==HISTORICAL_GRAPH_SHA256
    assert len(records)==len(index.outputs)==14079
    assert sum(o['public_path'] is not None for o in index.outputs.values())==14077
    assert len(implementation.packages)==22
    assert sum(len(p.contract.to_dict()['variants']) for p in implementation.packages)==278
    import gzip,json
    from pathlib import Path
    path=Path(__file__).parents[2]/'bulk/contracts/adoption/baseline/stable-mapping-v1.json.gz'
    with gzip.open(path,'rb') as f: mapping=json.load(f)
    assert fingerprint(mapping)==MAPPING_SHA256
    mapped={r['identity']['id']:r for r in mapping}
    assignments={i:m for p in implementation.packages for i,m in p.data()[1].items()}
    for record in records:
        r=record.to_dict();i=r['identity']['id'];frozen=mapped[i]
        assert frozen['identity']==r['identity'] and frozen['record_sha256']==record.sha256
        output=index.outputs[i]
        assert (output['local_path'],output['public_path'])==(r['identity']['local_path'],r['identity']['public_path'])
        assert assignments[i]['record_sha256']==record.sha256
        assert output['companions']==assignments[i]['companions']
    data=resolution.data();kinds=set();members=0
    for parent,children in data['families'].items():
        d=data['declared'][parent];kinds.add(d['generator']['name'])
        assert len(semantic_tokens(d))==len(children) and len(set(children))==len(children)
        assert all(child in mapped for child in children);members+=len(children)
    assert kinds=={'award-years','best-of-years','separator-variants','content-rating-series'}
    branches={assignments[i]['variant'] for i,o in index.outputs.items() if o['category']=='Overlays'}
    assert len(branches)==18
    assert {o['variant'] for o in index.outputs.values() if o['category']=='Overlays'}=={'standard','bigger'}
    assert all(index.outputs[i]['variant']==mapped[i]['observed_variant'] for i in mapped)
    assert members>0
    result=dict(M2_HISTORICAL)
    envelope={**identity(), 'evidence':result,'evidence_sha256':fingerprint(result)}
    write(OUTPUT/'phase4-m2-historical.json',envelope)
    return envelope
