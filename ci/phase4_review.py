"""Stdlib-only mandatory M4 review proof and exact additive ID reconciliation."""
import ast
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from ci.validation import identity, read, require, unique, write, pytest_run, validate_execution
from ci.phase4 import checksum, fingerprint

BASE = 'e0c715f713a630a59d1e83fa30119ffa3997e1cd'
SCHEMA = ROOT/'create_defaults/bulk/lifecycle/schemas/review-v1.schema.json'
FILES = ('evidence.py','review.py','review_authority.py','schemas/review-v1.schema.json')
IDS = ROOT/'ci/phase4-review-test-ids.json'
OUT = ROOT/'config/ci-validation/phase4-m4'
MAINTENANCE_PIN = 'e9f26ef8d54fc9762bdb426f05b8156b9d6af1ef0dca0d234fabf37179e151af'


def verify_maintenance(root=ROOT):
    import hashlib
    value=read(root/'ci/phase4-m4-maintenance.json')
    require(fingerprint(value)==MAINTENANCE_PIN and value['base']==BASE
        and set(value['files'])=={'ci/validation-plan.json'},'Unexpected M4 CI extension')
    path='ci/validation-plan.json';pins=value['files'][path]
    raw=subprocess.check_output(['git','show',BASE+':'+path],cwd=root).replace(b'\r\n',b'\n')
    require(hashlib.sha256(raw).hexdigest()==pins['before_sha256'] and checksum(root/path)==pins['sha256'],'Changed M4 CI maintenance')
    return value


def selections():
    groups=read(IDS);require(set(groups)=={'states','evidence'},'Changed M4 bounded partitions')
    a,b=(unique(groups[g],g) for g in ('states','evidence'))
    require(a and b and not a&b and all(n.startswith('create_defaults/phase4/tests/test_review.py::') for n in a|b),'Invalid/duplicate M4 bounded IDs')
    plan=read(ROOT/'ci/validation-plan.json')
    for job,group in [('contracts','states'),('generation','evidence')]:
        command=['{python}','ci/phase4_review.py','run','--group',group]
        require(plan['commands'][job].count(command)==1,'Missing mandatory M4 bounded command')
    return groups


def run(group):
    ids=selections()[group];out=OUT/group;result=dict(**identity(),kind='phase4-m4-review-execution',group=group,success=False,
        ids_sha256=checksum(IDS),schema_sha256=checksum(SCHEMA),implementation_sha256=implementation_checksum())
    try:
        collection=pytest_run(ids,out/'review-collection.json',collect=True)
        execution=pytest_run(ids,out/'review-execution.json')
        require(collection['exitstatus']==0 and unique(collection['nodes'],'M4 collection')==set(ids),'Changed M4 collection')
        require(unique(execution['nodes'],'M4 execution')==set(ids),'Incomplete M4 execution')
        require(not validate_execution(execution).get('skipped'),'M4 skips are not acceptance')
        result.update(collection=collection,execution=execution,success=True)
    finally:write(out/'phase4-m4-execution-report.json',result)


def verify_group_reports(reports):
    expected=identity();groups=selections()
    require(len(reports)==4 and {(r['platform'],r['group']) for r in reports}=={(p,g) for p in ('Windows','Linux') for g in groups},'Missing/duplicate M4 bounded execution')
    result={}
    for r in reports:
        ids=set(groups[r['group']])
        require(all(r[k]==expected[k] for k in ('head','plan_sha256')) and r['success']
            and r['kind']=='phase4-m4-review-execution','Failed/stale M4 execution')
        require(r['ids_sha256']==checksum(IDS) and r['schema_sha256']==checksum(SCHEMA)
            and r['implementation_sha256']==implementation_checksum(),'Changed M4 bounded selection/code')
        require(r['collection']['exitstatus']==0 and unique(r['collection']['nodes'],'M4 collection')==ids
            and unique(r['execution']['nodes'],'M4 execution')==ids,'Missing M4 bounded IDs')
        counts=validate_execution(r['execution']);require(not counts.get('skipped'),'Skipped M4 bounded ID')
        result.setdefault(r['platform'],{})[r['group']]=dict(counts=counts,seconds=r['execution']['seconds'],collected_ids=sorted(ids),executed_ids=sorted(r['execution']['nodes']))
    return result


def implementation_checksum():
    return fingerprint({p:(ROOT/'create_defaults/bulk/lifecycle'/p).read_text(encoding='utf-8-sig').replace('\r\n','\n') for p in FILES})


def baseline():
    original_foundations=json.loads(subprocess.check_output(['git','show',BASE+':ci/phase4-test-ids.json'],cwd=ROOT))
    require(read(ROOT/'ci/phase4-test-ids.json')[:len(original_foundations)]==original_foundations,
        'Changed original ordered P4 foundation IDs')
    path='ci/phase4-composition-test-ids.json'
    old=json.loads(subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT))
    current=read(ROOT/path)
    require(current['pixels']==old['pixels'],'Changed original M3 pixel IDs')
    require(set(old['security'])<=unique(current['security'],'extended security'),'Missing original M3 security ID')
    added=set(current['security'])-set(old['security'])
    require(added and all(i.startswith('create_defaults/phase4/tests/test_review.py::') for i in added),'Unexpected M4 review selection')
    require(not added&set().union(*map(set,selections().values())),'Duplicate M4 bounded execution')
    for name in ('composition.py','composition_models.py','previews.py','schemas/composition-v1.schema.json'):
        path='create_defaults/bulk/lifecycle/'+name
        raw=subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT).replace(b'\r\n',b'\n')
        import hashlib
        require(hashlib.sha256(raw).hexdigest()==checksum(ROOT/path),'Changed frozen M3 native infrastructure')
    # Moving one shared fixture to conftest must not relax any M3 test body.
    path='create_defaults/phase4/tests/test_composition.py'
    old_ast=ast.parse(subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT))
    new_ast=ast.parse((ROOT/path).read_text(encoding='utf-8-sig'))
    tests=lambda tree:{n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_')}
    require(tests(old_ast)==tests(new_ast),'Changed original M3 assertions')
    return sorted(added)


def verify_reports(reports, pixels):
    require(len(reports)==2 and {r['platform'] for r in reports}=={'Windows','Linux'},'Missing M4 review proof')
    expected=identity();result={}
    for report in reports:
        require(all(report[k]==expected[k] for k in ('head','plan_sha256')),'Stale M4 review proof')
        require(report['kind']=='phase4-m4-complete-review-proof' and report['schema_sha256']==checksum(SCHEMA)
            and report['implementation_sha256']==implementation_checksum(),'Changed M4 code/schema')
        require(report['sha256']==fingerprint({k:v for k,v in report.items() if k!='sha256'}),'Forged M4 proof')
        require(report['authenticated'] is False and report['ready'] is False and report['active'] is False
            and report['publication_authorized'] is False and report['contract_approvals_missing']==22,'M4 proof grants real authority')
        require(report['states']==['PREVIEWS_COMPLETE','SUBMITTER_CONFIRMED','MAINTAINER_APPROVED'],'Incomplete two-stage proof')
        require(report['submitter']!=report['maintainer'] and report['attribution']=='synthetic-only','Missing independent synthetic roles')
        require(report['members'] and report['all_encoded_bytes_verified'] is True and report['immutable_reopen_verified'] is True,'Missing native complete review proof')
        # The separately required M3 pixel producer independently renders these
        # exact members in the same platform environment; compare actual hashes.
        pixel=next((p for p in pixels if p['platform']==report['platform']),None)
        require(pixel is not None,'Missing native M3 pixel proof for M4')
        cohort=pixel['groups'][report['cohort']]
        require(report['members']=={v['appearance']:v['members'] for v in cohort['views']},'M4 native bytes differ from independently rendered M3')
        result[report['platform']]=report
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('action',choices=['run']);parser.add_argument('--group',required=True,choices=['states','evidence']);args=parser.parse_args();run(args.group)
