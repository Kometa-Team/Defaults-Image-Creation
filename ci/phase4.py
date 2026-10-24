"""Mandatory P4/M1 exact-head collection/execution and maintenance proof."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ci.validation import identity,read,write,require,unique,pytest_run,validate_execution

BASE='c33f792992ee704150799fe16536a64630fd8964'
MAINTENANCE_PIN='4344ddf985670bced739fef580cc0ca05cb53718262082e9c5a0cb2a4d9bfd69'
MAINTAINED={'.github/workflows/default-poster-validation.yml','ci/validation.py','ci/tests/test_validation.py',
 'create_defaults/tests/test_validation.py',
 'create_defaults/phase3/tests/test_consumption_boundaries.py',
 'create_defaults/phase3/tests/test_destination_isolation.py',
 'create_defaults/phase3/tests/test_translation_boundaries.py',
 'create_defaults/bulk/contracts/activation/protection.py',
 'create_defaults/bulk/contracts/activation/data/production-pins-v1.json',
 'create_defaults/phase3/tests/test_final_phase3_acceptance.py','create_defaults/phase3/tests/test_isolation_ci.py'}
IDS=ROOT/'ci/phase4-test-ids.json'
SCHEMA=ROOT/'create_defaults/bulk/lifecycle/schemas/operations-v1.schema.json'
GOLDEN=ROOT/'create_defaults/phase4/tests/canonical-v1.json'
OUT=ROOT/'config/phase4-ci'
M2_SCHEMA=ROOT/'create_defaults/bulk/lifecycle/schemas/identity-impact-v1.schema.json'
M2_GOLDEN=ROOT/'create_defaults/phase4/tests/identity-canonical-v1.json'
M2_HISTORICAL=dict(outputs=14079,public_outputs=14077,packages=22,variants=278,protected_sources=190,
    adopted_source_pins=299,generator_kinds=4,overlay_branches=18,
    mapping_sha256='6d1a49062208e8361227942549a4adafb0f2fed63c2f3a9a63c7860845ab876f',
    graph_sha256='93b01e2261249185bd06982a9cb0823a61628104d327958cedefd97788a39d7d')
M1_BASE='5deffb587c92d746a4611939c918ae0e6471ee30'
M2_BASE='33a20c1f5b7a73d672793f1700d48b566789ad32'
M3_MAINTENANCE_PIN='2dc46f2e90737b5a128c788eeec4f17276973a50123e8ee7ffd82c367fef0b14'
M3_MAINTAINED={'ci/validation-plan.json',
 'create_defaults/phase3/tests/test_consumption_boundaries.py',
 'create_defaults/phase3/tests/test_destination_isolation.py',
 'create_defaults/phase3/tests/test_final_phase3_acceptance.py',
 'create_defaults/phase3/tests/test_isolation_ci.py'}


def verify_m2_baseline():
    original=json.loads(subprocess.check_output(['git','show',M1_BASE+':ci/phase4-test-ids.json'],cwd=ROOT))
    require(len(original)==204 and unique(original,'M1 baseline IDs')<=unique(read(IDS),'M2 IDs'),'Missing original M1 test IDs')
    for name in ('models.py','storage.py','package_e.py','schemas/operations-v1.schema.json'):
        path='create_defaults/bulk/lifecycle/'+name
        original=subprocess.check_output(['git','show',M1_BASE+':'+path],cwd=ROOT).replace(b'\r\n',b'\n')
        require(hashlib.sha256(original).hexdigest()==checksum(ROOT/path),'Changed frozen M1 infrastructure: '+path)


def verify_m3_baseline():
    original=json.loads(subprocess.check_output(['git','show',M2_BASE+':ci/phase4-test-ids.json'],cwd=ROOT))
    require(len(original)==258 and unique(original,'M2 baseline IDs')<=unique(read(IDS),'M3 foundation IDs'),'Missing original M1/M2 test IDs')


def verify_historical_reports(reports):
    require(len(reports)==2 and {r['platform'] for r in reports}=={'Windows','Linux'},'Missing M2 historical platforms')
    current=identity()
    for r in reports:
        require(all(r[k]==current[k] for k in ('head','plan_sha256')),'Stale M2 historical proof')
        require(r['evidence']==M2_HISTORICAL and r['evidence_sha256']==fingerprint(M2_HISTORICAL),'Changed M2 historical invariants')
    return M2_HISTORICAL


def checksum(path):return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def fingerprint(value):
    # The acceptance job deliberately has no production dependencies installed.
    # Match Package E canonical JSON exactly, without importing its YAML/Pillow
    # dependency graph into this stdlib-only evidence verifier.
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True,
        separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()


def verify_m3_maintenance(root=ROOT):
    value=read(root/'ci/phase4-m3-maintenance.json')
    require(fingerprint(value)==M3_MAINTENANCE_PIN and value['base']==M2_BASE and set(value['files'])==M3_MAINTAINED,'Unexpected M3 CI maintenance')
    for path,pins in value['files'].items():
        original=subprocess.check_output(['git','show',M2_BASE+':'+path],cwd=root).replace(b'\r\n',b'\n')
        require(hashlib.sha256(original).hexdigest()==pins['before_sha256'] and checksum(root/path)==pins['sha256'],'Changed M3 maintenance: '+path)
    original=subprocess.check_output(['git','show',M2_BASE+':ci/validation-plan.json'],cwd=root)
    verify_original_plan(original,root=root)
    return value


def verify_original_plan(original,*,root=ROOT):
    """Retain the exact original plan and permit only two mandatory commands."""
    baseline=subprocess.check_output(['git','show',M2_BASE+':ci/validation-plan.json'],cwd=root).replace(b'\r\n',b'\n')
    require(original.replace(b'\r\n',b'\n')==baseline,'Changed original validation plan')
    expected=json.loads(baseline)
    for group,part in [('people','pixels'),('review','security')]:
        expected['commands'].setdefault(group,[]).append(['{python}','ci/phase4_composition.py','run','--group',part])
    require(read(root/'ci/validation-plan.json')==expected,'Validation plan changes beyond exact M3 additions')


def verify_maintenance(root=ROOT):
    value=read(root/'ci/phase4-maintenance.json')
    require(fingerprint(value)==MAINTENANCE_PIN,'Unapproved P4/M1 maintenance manifest')
    require(value['base']==BASE and set(value['files'])==MAINTAINED,'Unexpected maintenance scope')
    m3=verify_m3_maintenance(root)
    for path,pins in value['files'].items():
        before=subprocess.check_output(['git','show',BASE+':'+path],cwd=root).replace(b'\r\n',b'\n')
        require(hashlib.sha256(before).hexdigest()==pins['before_sha256'],'Wrong maintenance baseline: '+path)
        if path in m3['files']:
            require(m3['files'][path]['before_sha256']==pins['sha256'],'Broken M1/M3 maintenance chain')
        else:require(checksum(root/path)==pins['sha256'],'Changed authorized maintenance file: '+path)
    protected='create_defaults/bulk/contracts/activation/data/production-pins-v1.json'
    old=json.loads(subprocess.check_output(['git','show',BASE+':'+protected],cwd=root));new=read(root/protected)
    require(len(new['files'])==len(old['files'])==190 and new['files'].keys()==old['files'].keys(),'Protected membership changed')
    require({p for p in old['files'] if old['files'][p]!=new['files'][p]}=={'.github/workflows/default-poster-validation.yml'},'Unexpected protected source change')
    require(new['maintenance_context']['phase4_previous_manifest_sha256']==fingerprint(old) and new['maintenance_context']['phase4_baseline_commit']==BASE,'Missing P4 maintenance provenance')
    return value


def run():
    result={
        **identity(),'kind':'phase4-operation-foundations','success':False,
        'ids_sha256':checksum(IDS),'schema_sha256':checksum(SCHEMA),'golden_sha256':checksum(GOLDEN),
        'm2_schema_sha256':checksum(M2_SCHEMA),'m2_golden_sha256':checksum(M2_GOLDEN)}
    try:
        verify_maintenance()
        verify_m2_baseline()
        verify_m3_baseline()
        from ci.phase4_composition import selections
        m3=selections();all_expected=unique(read(IDS),'P4 foundations')
        for group in m3.values():
            require(not all_expected&unique(group,'M3 group'),'Duplicate P4 execution')
            all_expected|=set(group)
        all_collection=pytest_run(['create_defaults/phase4/tests'],OUT/'phase4-all-collection.json',collect=True)
        require(all_collection['exitstatus']==0 and unique(all_collection['nodes'],'all P4 collection')==all_expected,'Uncovered P4 test ID')
        paths=sorted({n.split('::')[0] for n in read(IDS)})
        collection=pytest_run(paths,OUT/'phase4-collection.json',collect=True)
        execution=pytest_run(paths,OUT/'phase4-execution.json')
        expected=unique(read(IDS),'P4 expected IDs')
        require(unique(collection['nodes'],'P4 collection')==expected and collection['exitstatus']==0,'Changed P4 collection')
        require(unique(execution['nodes'],'P4 execution')==expected,'Incomplete P4 execution')
        require(not validate_execution(execution).get('skipped'),'P4 security skips cannot satisfy acceptance')
        canonical=read(OUT/'phase4-canonical.json')
        require(all(canonical[k]==result[k] for k in ('head','platform','plan_sha256')),'Stale P4 canonical evidence')
        require(canonical['evidence']==read(GOLDEN)['archive'] and canonical['evidence_sha256']==read(GOLDEN)['archive_sha256'],'P4 canonical vector mismatch')
        m2=read(OUT/'phase4-m2-canonical.json')
        require(all(m2[k]==result[k] for k in ('head','platform','plan_sha256')),'Stale M2 canonical proof')
        require(m2['evidence_sha256']==read(M2_GOLDEN)['archive_sha256'],'M2 canonical replay differs')
        result.update(collection=collection,execution=execution,canonical_sha256=canonical['evidence_sha256'],
            m2_canonical_sha256=m2['evidence_sha256'],all_collection=all_collection,success=True)
    finally:write(OUT/'phase4-report.json',result)


def verify_reports(reports):
    verify_m2_baseline()
    verify_m3_baseline()
    require(len(reports)==2 and {r['platform'] for r in reports}=={'Windows','Linux'},'Missing/duplicate P4 platform')
    current=identity();expected=unique(read(IDS),'P4 expected IDs');summary={}
    historical=verify_historical_reports([read(p) for p in (ROOT/'config/ci-downloaded').rglob('phase4-m2-historical.json')])
    from ci.phase4_composition import selections,verify_reports as verify_composition
    m3=selections();all_expected=set(expected)
    for ids in m3.values():
        require(not all_expected&set(ids),'Duplicate P4 test execution');all_expected.update(ids)
    for r in reports:
        require(all(r[k]==current[k] for k in ('head','plan_sha256')),'Stale P4 head/plan')
        require(r['kind']=='phase4-operation-foundations' and r['success'],'P4 job failed')
        require(r['all_collection']['exitstatus']==0 and unique(r['all_collection']['nodes'],'all P4 collection')==all_expected,'Missing P4 namespace collection')
        require(r['ids_sha256']==checksum(IDS) and r['schema_sha256']==checksum(SCHEMA) and r['golden_sha256']==checksum(GOLDEN),'P4 selected IDs/schema/vectors changed')
        require(r['collection']['exitstatus']==0 and unique(r['collection']['nodes'],'P4 collection')==expected,'Missing P4 collection IDs')
        require(unique(r['execution']['nodes'],'P4 execution')==expected,'Missing P4 execution IDs')
        counts=validate_execution(r['execution']);require(not counts.get('skipped'),'P4 skip is not acceptance')
        require(r['canonical_sha256']==read(GOLDEN)['archive_sha256'],'P4 canonical evidence differs')
        require(r['m2_schema_sha256']==checksum(M2_SCHEMA) and r['m2_golden_sha256']==checksum(M2_GOLDEN),'M2 schema/vector differs')
        require(r['m2_canonical_sha256']==read(M2_GOLDEN)['archive_sha256'],'M2 Windows/Linux replay differs')
        summary[r['platform']]=dict(collected_ids=sorted(expected),executed_ids=sorted(r['execution']['nodes']),
            counts=counts,canonical_sha256=r['canonical_sha256'],schema_sha256=r['schema_sha256'],
            m2_canonical_sha256=r['m2_canonical_sha256'],m2_schema_sha256=r['m2_schema_sha256'],m2_historical=historical)
    summary['composition']=verify_composition([read(p) for p in (ROOT/'config/ci-downloaded').rglob('phase4-m3-*-report.json')])
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('action',choices=['run']);parser.parse_args();run()
