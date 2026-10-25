"""Exact-ID CI negative controls and real frozen overlay companion identities."""
from copy import deepcopy
import gzip
import json
from pathlib import Path

import pytest

from ci import phase4_m6 as ci
from create_defaults.bulk.common import BulkError, fingerprint
from create_defaults.bulk.contracts.expanded.graph import Snapshot
from create_defaults.bulk.lifecycle.basis import BASE, MAPPING_SHA256
from create_defaults.bulk.lifecycle.retirement import validate_delete


def reports():
    groups,ids=ci.selections();result=[]
    def collection(values):return dict(exitstatus=0,nodes=sorted(values))
    for platform in ('Windows','Linux'):
        for group,selected in groups.items():
            execution=dict(**collection(selected),seconds=1,reports=[
                dict(nodeid=i,when=when,outcome='passed',wasxfail=False,skip_reason=None)
                for i in selected for when in ('setup','call','teardown')])
            result.append(dict(kind='phase4-m6-execution',success=True,head='exact',plan_sha256='frozen',
                group=group,platform=platform,ids_sha256=ci.checksum(ci.IDS),implementation_sha256=ci.implementation(),
                all_collection=collection(ids),collection=collection(selected),execution=execution))
    return result


@pytest.mark.parametrize('attack',['missing','duplicate','head','failed','ids','implementation','uncollected','unexecuted','skip','xfail','incomplete','namespace'])
def test_m6_acceptance_rejects_missing_stale_or_partial_evidence(attack):
    rows=reports();r=rows[0]
    if attack=='missing':rows.pop()
    elif attack=='duplicate':rows[-1]=rows[0]
    elif attack=='head':r['head']='stale'
    elif attack=='failed':r['success']=False
    elif attack=='ids':r['ids_sha256']='a'*64
    elif attack=='implementation':r['implementation_sha256']='a'*64
    elif attack=='uncollected':r['collection']['nodes'].pop()
    elif attack=='unexecuted':r['execution']['nodes'].pop()
    elif attack=='skip':r['execution']['reports'][0].update(outcome='skipped',skip_reason='deliberate')
    elif attack=='xfail':r['execution']['reports'][0]['wasxfail']=True
    elif attack=='incomplete':r['execution']['reports'].pop()
    elif attack=='namespace':r['all_collection']['nodes'].append('create_defaults/phase4/m6_tests/test_hidden.py::test_hidden')
    with pytest.raises(ValueError):ci.verify_reports(rows,dict(head='exact',plan_sha256='frozen'))


def test_m6_acceptance_requires_every_platform_and_disjoint_id():
    result=ci.verify_reports(reports(),dict(head='exact',plan_sha256='frozen'))
    assert set(result)=={'Windows','Linux'} and all(set(v)==set(ci.GROUPS) for v in result.values())


@pytest.mark.parametrize('result',['failure','cancelled','skipped',None])
def test_failed_or_missing_required_job_cannot_reach_acceptance(monkeypatch,result):
    monkeypatch.setenv('M6_JOB_RESULTS',json.dumps({} if result is None else {'m6':{'result':result}}))
    with pytest.raises(ValueError,match='matrix'):ci.accept()


def test_additive_workflow_retains_exact_head_readonly_and_timeout():
    import yaml
    path=ci.ROOT/'.github/workflows/lifecycle-m6-validation.yml'
    value=yaml.safe_load(path.read_text())
    assert value['permissions']=={'contents':'read'}
    assert value['jobs']['acceptance']['needs']==['m6']
    assert value['jobs']['acceptance']['if']=='${{ always() }}'
    assert value['jobs']['m6']['strategy']['fail-fast'] is False
    assert set(value['jobs']['m6']['strategy']['matrix']['group'])==set(ci.GROUPS)
    for job in value['jobs'].values():
        assert job['timeout-minutes']==15 and 'continue-on-error' not in job
        assert job['env']['EXPECTED_HEAD']=='${{ github.event.pull_request.head.sha }}'
        checkout=next(s for s in job['steps'] if s.get('uses','').startswith('actions/checkout@'))
        assert checkout['with']['ref']=='${{ github.event.pull_request.head.sha }}'
        assert checkout['with']['persist-credentials'] is False


def test_all_historical_mappings_and_actual_overlay_companions_are_retained():
    rows=json.loads(gzip.decompress((BASE/'stable-mapping-v1.json.gz').read_bytes()))
    assert len(rows)==14079 and fingerprint(rows)==MAPPING_SHA256
    assert sum(r['identity']['public_path'] is not None for r in rows)==14077
    assert len({r['identity']['id'] for r in rows})==14079
    # Real frozen standard/bigger IDs, exact source identity, source hash and
    # path spellings. This is a scoped dependency-validator test, not a fake
    # historical cohort supplied to the operation/Phase 3 execution adapters.
    first=next(r for r in rows if r['identity']['category']=='Overlays')
    selected=[r for r in rows if r['identity']['category']=='Overlays'
              and r['identity']['source']['path']==first['identity']['source']['path']]
    assert len(selected)==2 and {r['observed_variant'] for r in selected}=={'standard','bigger'}
    ids=sorted(r['identity']['id'] for r in selected);nodes={};outputs={};entries={}
    for r in selected:
        i=r['identity']['id'];n='output:'+i
        nodes[n]=dict(kind='output',identity=i,sha256=r['record_sha256'],dependencies=[])
        outputs[i]=dict(node=n,category='Overlays',kind='overlay',variant=r['observed_variant'],
            local_path=r['identity']['local_path'],public_path=r['identity']['public_path'],
            companions=[x for x in ids if x!=i],evidence=dict(previews=[],confirmations=[],decisions=[],receipts=[]),context_sha256=r['record_sha256'])
        entries[i]=dict(semantic=dict(role=r['observed_variant'],key='source',parent=r['source_identity']),tombstone_sha256=None)
    graph=Snapshot.create(dict(schema_version=1,kind='m5-dependency-snapshot',basis=MAPPING_SHA256,nodes=nodes,outputs=outputs,unresolved=[]))
    with pytest.raises(BulkError,match='companion'):validate_delete(graph.index(),entries,ids[:1])
    validate_delete(graph.index(),entries,ids)
    assert {i:outputs[i]['variant'] for i in ids}=={r['identity']['id']:r['observed_variant'] for r in selected}
    assert fingerprint(rows)==MAPPING_SHA256


def test_actual_generated_and_overlay_ids_survive_mapping_reservations(tmp_path):
    """Exercise the real M2 identity bridge, without claiming an applied cohort."""
    from create_defaults.bulk.lifecycle.basis import historical_basis
    from create_defaults.bulk.lifecycle.identities import IdentityRegistry
    from create_defaults.phase3.tests.destination_samples import inventory,USER
    basis=historical_basis();rows=basis.rows()
    generated=next(r for r in rows if r['family'])
    overlay=next(r for r in rows if r['identity']['category']=='Overlays')
    pair=[r for r in rows if r['identity']['category']=='Overlays'
          and r['identity']['source']['path']==overlay['identity']['source']['path']]
    inv=inventory(USER,'Main',{})
    registry=IdentityRegistry.create(tmp_path/'state','m6-historical-reservation',inventory=inv,expected_inventory_sha256=inv.sha256)
    for row in [generated,*pair]:
        i=row['identity']['id'];before=registry.reference(i,token='reference-'+fingerprint(i),expected=registry.view().head)
        names=deepcopy(before['names']);names['display_name']+=' M6 reservation'
        for field in ('local_path','public_path'):
            if names[field] is not None:
                path=Path(names[field]);names[field]=path.parent.as_posix()+'/M6 Reference '+path.name
        after=registry.revise(i,names,entry_revision=before['revision'],token='revise-'+fingerprint(i),expected=registry.view().head)
        assert after['id']==i and after['semantic']==before['semantic'] and after['original_names']==before['original_names']
        assert after['names']['source']==before['names']['source'] and after['variant']==before['variant']
        assert any(a['value']==before['names']['local_path'] for a in after['aliases'])
    assert {registry.view().entry(r['identity']['id'])['semantic']['role'] for r in pair}=={'standard','bigger'}
