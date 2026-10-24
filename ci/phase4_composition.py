"""Mandatory exact M3 IDs in bounded existing jobs; stdlib-only acceptance."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ci.validation import identity,read,write,require,unique,pytest_run,validate_execution
from ci.phase4 import checksum,fingerprint

IDS=ROOT/'ci/phase4-composition-test-ids.json'
SCHEMA=ROOT/'create_defaults/bulk/lifecycle/schemas/composition-v1.schema.json'
OUT=ROOT/'config/ci-validation/phase4-m3'
KINDS={'playlist':1,'genre':1,'network':2,'overlay':2,'family':2}


def selections():
    groups=read(IDS);require(set(groups)=={'pixels','security'},'Changed M3 partition')
    a,b=(unique(groups[g],g) for g in ('pixels','security'))
    require(a and b and not a&b,'Missing/duplicate M3 partition IDs')
    require(all(n.startswith('create_defaults/phase4/tests/test_composition.py::') for n in a),'Unexpected M3 pixel file')
    require(all(n.startswith(('create_defaults/phase4/tests/test_composition.py::','create_defaults/phase4/tests/test_review.py::')) for n in b),'Unexpected M3/M4 security file')
    from ci.phase4_review import baseline
    baseline()
    plan=read(ROOT/'ci/validation-plan.json')
    for group,part in [('people','pixels'),('review','security')]:
        require(plan['commands'][group].count(['{python}','ci/phase4_composition.py','run','--group',part])==1,'Missing mandatory M3 command')
    return groups


def implementation_checksum():
    names=('composition.py','composition_models.py','previews.py','schemas/composition-v1.schema.json')
    return fingerprint({n:(ROOT/'create_defaults/bulk/lifecycle'/n).read_text(encoding='utf-8-sig').replace('\r\n','\n') for n in names})


def verify_pixels(proof,expected_identity):
    require(all(proof[k]==expected_identity[k] for k in ('head','platform','plan_sha256')),'Stale M3 pixel proof')
    require(proof['kind']=='phase4-m3-composition-proof' and proof['schema_sha256']==checksum(SCHEMA),'Wrong M3 pixel schema')
    require(proof['implementation_sha256']==implementation_checksum(),'Changed M3 implementation')
    require(not proof['approval'] and not proof['activation'] and not proof['publication'] and proof['reuse_scope']=='exact-environment-only','M3 proof grants authority')
    require(proof['evidence_sha256']==fingerprint({k:v for k,v in proof.items() if k!='evidence_sha256'}),'Forged M3 proof hash')
    require(set(proof['groups'])==set(KINDS),'Missing composition category proof')
    for kind,group in proof['groups'].items():
        require(group['runtime']['implementation_sha256']==implementation_checksum() and group['runtime']['renderer']['platform']==proof['platform'],'Wrong rendering environment')
        require(group['runtime']['reproducibility']=='exact-environment-only','Unsupported cross-platform reuse')
        require([v['appearance'] for v in group['views']]==['default','requested'],'Missing appearance')
        for view in group['views']:
            require(len(view['members'])==KINDS[kind] and view['members']==view['repeated_members'],'Incomplete/nondeterministic native bytes')
            metrics=view['execution'];require(metrics and all(m['peak_worker_rss']<=512*1024*1024 and m['peak_workers_rss_sum']<=1024*1024*1024 for m in metrics),'Exceeded original worker budget')
            require(sum(m['executed'] for m in metrics)==2*KINDS[kind] and all(m['cache_hits']==0 for m in metrics),'Reproducibility substituted cache hits')
    return proof


def run(group):
    groups=selections();expected=unique(groups[group],group)
    result=dict(**identity(),kind='phase4-m3-group',group=group,success=False,ids_sha256=checksum(IDS),schema_sha256=checksum(SCHEMA),implementation_sha256=implementation_checksum())
    try:
        collection=pytest_run(groups[group],OUT/(group+'-collection.json'),collect=True)
        execution=pytest_run(groups[group],OUT/(group+'-execution.json'))
        require(collection['exitstatus']==0 and unique(collection['nodes'],'M3 collection')==expected,'Missing M3 collected ID')
        require(unique(execution['nodes'],'M3 execution')==expected,'Missing M3 executed ID')
        require(not validate_execution(execution).get('skipped'),'M3 skips are not acceptance')
        if group=='pixels':result['pixels']=verify_pixels(read(OUT/'phase4-m3-composition.json'),result)
        result.update(collection=collection,execution=execution,success=True)
    finally:write(OUT/('phase4-m3-'+group+'-report.json'),result)


def verify_reports(reports):
    groups=selections();current=identity()
    require(len(reports)==4 and {(r['platform'],r['group']) for r in reports}=={(p,g) for p in ('Windows','Linux') for g in groups},'Missing/duplicate M3 job')
    result={};pixels={}
    for r in reports:
        require(all(r[k]==current[k] for k in ('head','plan_sha256')) and r['success'] and r['kind']=='phase4-m3-group','Failed/stale M3 job')
        require(r['ids_sha256']==checksum(IDS) and r['schema_sha256']==checksum(SCHEMA) and r['implementation_sha256']==implementation_checksum(),'Changed M3 selection/schema/code')
        expected=unique(groups[r['group']],'expected M3')
        require(r['collection']['exitstatus']==0 and unique(r['collection']['nodes'],'collected M3')==expected,'Missing M3 collected ID')
        require(unique(r['execution']['nodes'],'executed M3')==expected,'Missing M3 executed ID')
        counts=validate_execution(r['execution']);require(not counts.get('skipped'),'M3 skip cannot satisfy acceptance')
        result.setdefault(r['platform'],{})[r['group']]=dict(counts=counts,seconds=r['execution']['seconds'],collected_ids=sorted(expected),executed_ids=sorted(r['execution']['nodes']))
        if r['group']=='pixels':pixels[r['platform']]=verify_pixels(r['pixels'],r)
    comparisons=[]
    for kind in KINDS:
        linux=pixels['Linux']['groups'][kind];windows=pixels['Windows']['groups'][kind]
        for a,b in zip(linux['views'],windows['views']):
            require(a['members'].keys()==b['members'].keys(),'Cross-platform membership differs')
            for member in a['members']:
                comparisons.append(dict(kind=kind,appearance=a['appearance'],identity=member,linux_sha256=a['members'][member],windows_sha256=b['members'][member],exact=a['members'][member]==b['members'][member]))
    result['cross_platform']=dict(comparisons=comparisons,exact=sum(r['exact'] for r in comparisons),different=sum(not r['exact'] for r in comparisons),reuse='blocked-across-environments-even-if-bytes-match')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('action',choices=['run']);p.add_argument('--group',required=True,choices=['pixels','security']);args=p.parse_args();run(args.group)
