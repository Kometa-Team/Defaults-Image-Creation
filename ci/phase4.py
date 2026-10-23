"""Mandatory P4/M1 exact-head collection/execution and maintenance proof."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ci.validation import identity,read,write,require,unique,pytest_run,validate_execution

BASE='c33f792992ee704150799fe16536a64630fd8964'
MAINTENANCE_PIN='ae7ce352dffc8578ab00ba984cd39a9b099e02ef0e920dbe882fce4d343a407a'
MAINTAINED={'.github/workflows/default-poster-validation.yml','ci/validation.py','ci/tests/test_validation.py',
 'create_defaults/bulk/contracts/activation/protection.py',
 'create_defaults/bulk/contracts/activation/data/production-pins-v1.json',
 'create_defaults/phase3/tests/test_final_phase3_acceptance.py','create_defaults/phase3/tests/test_isolation_ci.py'}
IDS=ROOT/'ci/phase4-test-ids.json'
SCHEMA=ROOT/'create_defaults/bulk/lifecycle/schemas/operations-v1.schema.json'
GOLDEN=ROOT/'create_defaults/phase4/tests/canonical-v1.json'
OUT=ROOT/'config/phase4-ci'


def checksum(path):return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def verify_maintenance(root=ROOT):
    from create_defaults.bulk.common import fingerprint
    value=read(root/'ci/phase4-maintenance.json')
    require(fingerprint(value)==MAINTENANCE_PIN,'Unapproved P4/M1 maintenance manifest')
    require(value['base']==BASE and set(value['files'])==MAINTAINED,'Unexpected maintenance scope')
    for path,pins in value['files'].items():
        before=subprocess.check_output(['git','show',BASE+':'+path],cwd=root).replace(b'\r\n',b'\n')
        require(hashlib.sha256(before).hexdigest()==pins['before_sha256'],'Wrong maintenance baseline: '+path)
        require(checksum(root/path)==pins['sha256'],'Changed authorized maintenance file: '+path)
    protected='create_defaults/bulk/contracts/activation/data/production-pins-v1.json'
    import json
    old=json.loads(subprocess.check_output(['git','show',BASE+':'+protected],cwd=root));new=read(root/protected)
    require(len(new['files'])==len(old['files'])==190 and new['files'].keys()==old['files'].keys(),'Protected membership changed')
    require({p for p in old['files'] if old['files'][p]!=new['files'][p]}=={'.github/workflows/default-poster-validation.yml'},'Unexpected protected source change')
    require(new['maintenance_context']['phase4_previous_manifest_sha256']==fingerprint(old) and new['maintenance_context']['phase4_baseline_commit']==BASE,'Missing P4 maintenance provenance')
    return value


def run():
    result={
        **identity(),'kind':'phase4-operation-foundations','success':False,
        'ids_sha256':checksum(IDS),'schema_sha256':checksum(SCHEMA),'golden_sha256':checksum(GOLDEN)}
    try:
        verify_maintenance()
        paths=['create_defaults/phase4/tests']
        collection=pytest_run(paths,OUT/'phase4-collection.json',collect=True)
        execution=pytest_run(paths,OUT/'phase4-execution.json')
        expected=unique(read(IDS),'P4 expected IDs')
        require(unique(collection['nodes'],'P4 collection')==expected and collection['exitstatus']==0,'Changed P4 collection')
        require(unique(execution['nodes'],'P4 execution')==expected,'Incomplete P4 execution')
        require(not validate_execution(execution).get('skipped'),'P4 security skips cannot satisfy acceptance')
        canonical=read(OUT/'phase4-canonical.json')
        require(all(canonical[k]==result[k] for k in ('head','platform','plan_sha256')),'Stale P4 canonical evidence')
        require(canonical['evidence']==read(GOLDEN)['archive'] and canonical['evidence_sha256']==read(GOLDEN)['archive_sha256'],'P4 canonical vector mismatch')
        result.update(collection=collection,execution=execution,canonical_sha256=canonical['evidence_sha256'],success=True)
    finally:write(OUT/'phase4-report.json',result)


def verify_reports(reports):
    require(len(reports)==2 and {r['platform'] for r in reports}=={'Windows','Linux'},'Missing/duplicate P4 platform')
    current=identity();expected=unique(read(IDS),'P4 expected IDs');summary={}
    for r in reports:
        require(all(r[k]==current[k] for k in ('head','plan_sha256')),'Stale P4 head/plan')
        require(r['kind']=='phase4-operation-foundations' and r['success'],'P4 job failed')
        require(r['ids_sha256']==checksum(IDS) and r['schema_sha256']==checksum(SCHEMA) and r['golden_sha256']==checksum(GOLDEN),'P4 selected IDs/schema/vectors changed')
        require(r['collection']['exitstatus']==0 and unique(r['collection']['nodes'],'P4 collection')==expected,'Missing P4 collection IDs')
        require(unique(r['execution']['nodes'],'P4 execution')==expected,'Missing P4 execution IDs')
        counts=validate_execution(r['execution']);require(not counts.get('skipped'),'P4 skip is not acceptance')
        require(r['canonical_sha256']==read(GOLDEN)['archive_sha256'],'P4 canonical evidence differs')
        summary[r['platform']]=dict(collected_ids=sorted(expected),executed_ids=sorted(r['execution']['nodes']),
            counts=counts,canonical_sha256=r['canonical_sha256'],schema_sha256=r['schema_sha256'])
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('action',choices=['run']);parser.parse_args();run()
