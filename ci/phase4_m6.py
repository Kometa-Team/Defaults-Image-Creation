"""Additive bounded M6 exact-ID execution; original validation stays frozen."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ci.validation import identity,read,write,require,unique,pytest_run,validate_execution
from ci.phase4 import checksum,fingerprint
IDS=ROOT/'ci/phase4-m6-test-ids.json'
OUT=ROOT/'config/ci-validation/m6'
SOURCE=('mappings.py','mapping_moves.py','retirement.py','apply.py','schemas/mappings-v1.schema.json')
GROUPS=('names','security','recovery','concurrency','restart')

def implementation():
    return fingerprint({n:checksum(ROOT/'create_defaults/bulk/lifecycle'/n) for n in SOURCE})

def selections():
    groups=read(IDS);require(set(groups)==set(GROUPS),'Missing M6 group')
    seen=set()
    for name,ids in groups.items():
        selected=unique(ids,'M6 '+name)
        require(selected and not selected & seen,'Missing/duplicate M6 ID')
        require(all(n.startswith('create_defaults/phase4/m6_tests/test_') for n in selected),'Foreign M6 ID')
        seen |= selected
    return groups,seen

def verify_report(report, expected):
    require(report.get('kind')=='phase4-m6-execution' and report.get('success') is True,'Missing/failed M6 report')
    require(all(report.get(k)==expected[k] for k in ('head','plan_sha256')),'Stale M6 head')
    require(report['ids_sha256']==checksum(IDS) and report['implementation_sha256']==implementation(),'Changed M6 inputs')
    groups,all_ids=selections();require(report['group'] in groups,'Unknown M6 group')
    ids=set(groups[report['group']])
    require(report['all_collection']['exitstatus']==0 and unique(report['all_collection']['nodes'],'M6 complete collection')==all_ids,'Uncovered M6 test ID')
    require(report['collection']['exitstatus']==0 and unique(report['collection']['nodes'],'M6 collection')==ids,'Missing M6 collected ID')
    require(unique(report['execution']['nodes'],'M6 execution')==ids,'Missing M6 executed ID')
    counts=validate_execution(report['execution'])
    require(not counts.get('skipped'),'M6 skip cannot satisfy acceptance')
    return dict(counts=counts,seconds=report['execution']['seconds'])

def run(group):
    groups,_=selections();out=OUT/group
    result=dict(**identity(),kind='phase4-m6-execution',group=group,success=False,
        ids_sha256=checksum(IDS),implementation_sha256=implementation())
    try:
        complete=pytest_run(['create_defaults/phase4/m6_tests'],out/'m6-all-collection.json',collect=True)
        response=out/'selected.txt';response.parent.mkdir(parents=True,exist_ok=True)
        response.write_text('\n'.join(groups[group])+'\n',encoding='utf8',newline='\n')
        collected=pytest_run(['@'+str(response)],out/'m6-collection.json',collect=True)
        executed=pytest_run(['@'+str(response)],out/'m6-execution.json')
        result.update(all_collection=complete,collection=collected,execution=executed,success=True)
        verify_report(result,identity())
    except BaseException:
        result['success']=False
        raise
    finally:write(out/'m6-report.json',result)

def verify_reports(reports,expected):
    expected_pairs={(p,g) for p in ('Windows','Linux') for g in GROUPS}
    require(len(reports)==len(expected_pairs) and {(r['platform'],r['group']) for r in reports}==expected_pairs,'Missing/duplicate M6 platform/group')
    return {p:{g:verify_report(next(r for r in reports if (r['platform'],r['group'])==(p,g)),expected)
        for g in GROUPS} for p in ('Windows','Linux')}

def accept():
    import json,os
    needs=json.loads(os.environ['M6_JOB_RESULTS'])
    require(set(needs)=={'m6'} and needs['m6']['result']=='success','M6 matrix failed, cancelled or missing')
    reports=[read(p) for p in (ROOT/'config/m6-downloaded').rglob('m6-report.json')]
    platforms=verify_reports(reports,identity())
    write(OUT/'acceptance.json',dict(**identity(),kind='phase4-m6-acceptance',success=True,platforms=platforms))

if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('action',choices=['run','accept']);parser.add_argument('--group',choices=GROUPS);args=parser.parse_args()
    if args.action=='run':
        if args.group is None: parser.error('--group required for run')
        run(args.group)
    else:accept()
