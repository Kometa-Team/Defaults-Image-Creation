"""Mandatory M5 exact-ID execution and isolated native transaction acceptance."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ci.validation import identity,read,write,require,unique,pytest_run,validate_execution
from ci.phase4 import checksum,fingerprint

BASE='47e69a59fd1c306789457250ef6493bdfef7fc17'
IDS=ROOT/'ci/phase4-transaction-test-ids.json'
SCHEMA=ROOT/'create_defaults/bulk/lifecycle/schemas/transaction-v1.schema.json'
OUT=ROOT/'config/ci-validation/phase4-m5'
FILES=('operations.py','apply.py','recovery.py','schemas/transaction-v1.schema.json')
JOBS={'atomic':'categories','security':'smoke','concurrency':'core','recovery':'historical'}
MAINTENANCE_PIN='30f2b407bc4f08b890fce653283d7d0cc451bd68d086f94bfe303f0bfbce88a1'


def implementation_checksum():
    return fingerprint({n:(ROOT/'create_defaults/bulk/lifecycle'/n).read_text(encoding='utf-8-sig').replace('\r\n','\n') for n in FILES})


def verify_maintenance(root=ROOT):
    value=read(root/'ci/phase4-m5-maintenance.json')
    require(fingerprint(value)==MAINTENANCE_PIN and value['base']==BASE
        and set(value['files'])=={'ci/validation-plan.json'},'Unexpected M5 CI extension')
    pins=value['files']['ci/validation-plan.json']
    original=subprocess.check_output(['git','show',BASE+':ci/validation-plan.json'],cwd=root).replace(b'\r\n',b'\n')
    require(hashlib.sha256(original).hexdigest()==pins['before_sha256']
        and checksum(root/'ci/validation-plan.json')==pins['sha256'],'Changed M5 CI maintenance')
    return value


def verify_plan(original,*,root=ROOT,current=None):
    baseline=json.loads(subprocess.check_output(['git','show',BASE+':ci/validation-plan.json'],cwd=root))
    require(original==baseline,'Changed M4 validation plan')
    expected=json.loads(json.dumps(baseline))
    for group,job in JOBS.items():
        expected['commands'].setdefault(job,[]).append(['{python}','ci/phase4_transactions.py','run','--group',group])
    require((read(root/'ci/validation-plan.json') if current is None else current)==expected,'Changes beyond exact mandatory M5 commands')


def baseline():
    # Frozen M1/M3 native files keep their existing independent verifiers. M5
    # also preserves every M4 source and original M1-M4 assertion AST exactly.
    for name in ('evidence.py','review.py','review_authority.py','schemas/review-v1.schema.json'):
        path='create_defaults/bulk/lifecycle/'+name
        raw=subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT).replace(b'\r\n',b'\n')
        require(hashlib.sha256(raw).hexdigest()==checksum(ROOT/path),'Changed frozen M4 infrastructure')
    old=json.loads(subprocess.check_output(['git','show',BASE+':ci/phase4-test-ids.json'],cwd=ROOT))
    require(read(ROOT/'ci/phase4-test-ids.json')[:len(old)]==old,'Changed ordered M1-M4 foundation IDs')
    for path in ('ci/phase4-composition-test-ids.json','ci/phase4-review-test-ids.json'):
        require(read(ROOT/path)==json.loads(subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)),'Changed M3/M4 execution IDs')
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'create_defaults/phase4/tests'],cwd=ROOT,text=True).splitlines()
    for path in paths:
        if not Path(path).name.startswith('test_') or not path.endswith('.py'):continue
        old=ast.parse(subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT))
        new=ast.parse((ROOT/path).read_text(encoding='utf-8-sig'))
        tests=lambda t:{n.name:ast.dump(n,include_attributes=False) for n in t.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_')}
        require(tests(old)==tests(new),'Changed original Phase 4 assertions: '+path)


def selections():
    groups=read(IDS)
    require(set(groups)==set(JOBS),'Changed M5 bounded groups')
    all_ids=set()
    for group,ids in groups.items():
        selected=unique(ids,'M5 '+group)
        require(selected and not all_ids&selected,'Duplicate/missing M5 IDs')
        require(all(i.startswith('create_defaults/phase4/tests/test_transactions') for i in selected),'Unexpected M5 native selection')
        all_ids|=selected
        command=['{python}','ci/phase4_transactions.py','run','--group',group]
        require(read(ROOT/'ci/validation-plan.json')['commands'][JOBS[group]].count(command)==1,'Missing mandatory M5 producer')
    return groups


def run(group):
    ids=selections()[group];out=OUT/group
    result=dict(**identity(),kind='phase4-m5-execution',group=group,success=False,
        ids_sha256=checksum(IDS),schema_sha256=checksum(SCHEMA),implementation_sha256=implementation_checksum())
    try:
        baseline();verify_maintenance();verify_plan(json.loads(subprocess.check_output(['git','show',BASE+':ci/validation-plan.json'],cwd=ROOT)))
        collection=pytest_run(ids,out/'collection.json',collect=True)
        execution=pytest_run(ids,out/'execution.json')
        require(collection['exitstatus']==0 and unique(collection['nodes'],'M5 collection')==set(ids),'Changed M5 collection')
        require(unique(execution['nodes'],'M5 execution')==set(ids),'Incomplete M5 execution')
        require(not validate_execution(execution).get('skipped'),'M5 skips cannot satisfy acceptance')
        result.update(collection=collection,execution=execution,success=True)
    finally:write(out/'phase4-m5-execution-report.json',result)


def verify_reports(reports):
    baseline();verify_maintenance()
    expected=identity();groups=selections()
    require(len(reports)==2*len(groups) and {(r['platform'],r['group']) for r in reports}=={(p,g) for p in ('Windows','Linux') for g in groups},'Missing/duplicate M5 execution')
    result={}
    for r in reports:
        require(all(r[k]==expected[k] for k in ('head','plan_sha256')) and r['success'] and r['kind']=='phase4-m5-execution','Failed/stale M5 execution')
        require(r['ids_sha256']==checksum(IDS) and r['schema_sha256']==checksum(SCHEMA)
            and r['implementation_sha256']==implementation_checksum(),'Changed M5 IDs/schema/code')
        ids=set(groups[r['group']])
        require(r['collection']['exitstatus']==0 and unique(r['collection']['nodes'],'M5 collection')==ids
            and unique(r['execution']['nodes'],'M5 execution')==ids,'Missing M5 collected/executed ID')
        counts=validate_execution(r['execution']);require(not counts.get('skipped'),'Skipped M5 ID')
        result.setdefault(r['platform'],{})[r['group']]=dict(counts=counts,seconds=r['execution']['seconds'],collected_ids=sorted(ids),executed_ids=sorted(r['execution']['nodes']))
    proofs=[read(p) for p in (ROOT/'config/ci-downloaded').rglob('phase4-m5-native-proof.json')]
    pixels=[read(p) for p in (ROOT/'config/ci-downloaded').rglob('phase4-m3-composition.json')]
    result['native']=verify_native_proofs(proofs,pixels)
    return result


def verify_native_proofs(proofs,pixels):
    expected=identity();result={}
    require(len(proofs)==2 and {p['platform'] for p in proofs}=={'Windows','Linux'},'Missing M5 native commit proofs')
    for p in proofs:
        require(all(p[k]==expected[k] for k in ('head','plan_sha256')) and p['kind']=='phase4-m5-native-transaction-proof','Stale M5 native proof')
        require(p['schema_sha256']==checksum(SCHEMA) and p['implementation_sha256']==implementation_checksum()
            and p['sha256']==fingerprint({k:v for k,v in p.items() if k!='sha256'}),'Changed M5 native proof')
        require(p['isolated_committed'] is True and p['restart_verified'] is True and p['retry_verified'] is True and p['members'],'Incomplete M5 native proof')
        require(all(p[k] is False for k in ('authenticated','operation_accepted','applied','ready','active','publication_authorized','contract_approved')),'M5 proof grants real authority')
        require(p['contract_approvals_missing']==22 and p['cohort']=='genre','Changed M5 native contract scope')
        native=next((v for v in pixels if v['platform']==p['platform']),None)
        require(native is not None and all(native[k]==expected[k] for k in ('head','plan_sha256')),'Missing/stale independent M3 pixels')
        view=next((v for v in native['groups'][p['cohort']]['views'] if v['appearance']==p['appearance']),None)
        require(view is not None and {i:m['sha256'] for i,m in p['members'].items()}==view['members'],'M5 committed bytes differ from independent native composition')
        result[p['platform']]=p
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('action',choices=['run']);parser.add_argument('--group',required=True,choices=tuple(JOBS));args=parser.parse_args();run(args.group)
