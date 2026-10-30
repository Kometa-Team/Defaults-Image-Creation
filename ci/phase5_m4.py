"""Bounded exact-ID M4 execution and independently decoded native artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ci.validation import identity, read, write, require, unique, pytest_run, validate_execution

IDS=ROOT/'ci/phase5-m4-test-ids.json'
OUT=ROOT/'config/ci-validation/phase5-m4'
TESTS='create_defaults/phase5/m4_tests'
GROUPS=('protocol','catalog','sequence','lineage','atomic','atomic-tail','recovery','concurrent','closure','control','freshness')
SOURCES=('create_defaults/bulk/lifecycle/current_mapping.py',
    'create_defaults/bulk/lifecycle/apply.py','create_defaults/bulk/lifecycle/recovery.py',
    'create_defaults/bulk/lifecycle/mappings.py',TESTS+'/conftest.py',TESTS+'/helpers.py',
    TESTS+'/test_current_mapping.py',TESTS+'/test_guards.py','ci/phase5_m4.py')


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def inputs(): return {name:digest(ROOT/name) for name in SOURCES}


def selections():
    groups=read(IDS);require(set(groups)==set(GROUPS),'Missing M4 bounded group')
    seen=set()
    for group in GROUPS:
        nodes=unique(groups[group],group)
        require(nodes and not seen&nodes and all(n.startswith(TESTS+'/test_') for n in nodes),'Missing/duplicate/foreign M4 ID')
        seen|=nodes
    return groups


def native_artifacts(directory):
    from io import BytesIO
    from PIL import Image
    from create_defaults.bulk.common import canonical,fingerprint
    directory=Path(directory);proof=read(directory/'sequence.json')
    require(proof['sha256']==fingerprint({k:v for k,v in proof.items() if k!='sha256'}),'Changed M4 proof')
    require(proof['operations']==['ADD','UPDATE','RENAME','UPDATE'] and proof['cold_restart_verified']
        and proof['history_retained'] and proof['exact_retry_verified'] and proof['isolated_only'],'Missing M4 lifecycle proof')
    for key in ('authenticated','operation_accepted','applied','artwork_approved','contract_approved',
                'ready','active','production_enforcement','publication_authorized'):
        require(proof[key] is False,'Native fixture claims authority')
    snapshots=proof['snapshots'];pins=proof['snapshot_sha256']
    require(len(snapshots)==len(pins)==3 and len(set(pins))==3,'Missing immutable artwork epochs')
    i=proof['permanent_id'];plan=proof['mapping_plan']
    require(fingerprint(plan)==proof['mapping_plan_sha256'] and plan['members']==[i], 'Changed mapping plan')
    require(plan['after'][i]['names']['public_path']=='genre/fixture.jpg','Missing literal case-only mapping')
    require(all(a in proof['current_entry']['aliases'] for a in plan['after'][i]['aliases'])
        and proof['current_entry']['original_names']==plan['before'][i]['original_names'],'Changed retained aliases')
    for s,pin in zip(snapshots,pins):
        require(fingerprint(s)==pin and s['members']==[i] and s['entries'][i]['id']==i,'Changed snapshot/identity')
    require(snapshots[-1]['expected_snapshots']=={i:pins[1]},'Lost accepted receipt lineage')
    expected={}
    for label,s in zip(('add','update','current-update'),snapshots):
        composition=json.loads(s['composition_json'])
        require(fingerprint(composition)==s['composition_sha256'],'Changed composition context')
        require({v['appearance'] for v in composition['views']}=={'default','requested'},'Missing native view')
        for view in composition['views']:
            require(len(view['members'])==1 and view['members'][0]['identity']==i,'Missing required member')
            expected[label+'-'+view['appearance']+'.jpg']=view['members'][0]
    images={}
    require(len(proof['rows'])==6,'Incomplete encoded evidence')
    for row in proof['rows']:
        name,member,receipt,worker=(row[k] for k in ('file','member','receipt','worker'))
        require(name in expected and name not in images and member==expected[name],'Foreign/duplicate native member')
        raw=(directory/name).read_bytes()
        require(hashlib.sha256(raw).hexdigest()==member['sha256']==receipt['sha256']
            and len(raw)==member['bytes']==receipt['size'],'Changed encoded artwork')
        require(receipt['receipt_sha256']==member['receipt_sha256']==fingerprint({k:v for k,v in receipt.items() if k!='receipt_sha256'}),'Changed receipt')
        require(worker['status']=='verified' and worker['id']==receipt['job_id']
            and worker['receipt']==canonical(receipt).decode()
            and fingerprint(json.loads(worker['spec']))==worker['fingerprint']==receipt['job_fingerprint'],'Foreign owned worker')
        with Image.open(BytesIO(raw)) as image:
            image.load()
            require((image.format,image.mode,list(image.size))==('JPEG','RGB',[2000,3000])
                and [2000,3000]==member['dimensions'],'Thumbnail/geometry substitution')
        images[name]=dict(sha256=member['sha256'],bytes=len(raw),receipt_sha256=member['receipt_sha256'])
    require({p.name for p in directory.iterdir()}==set(expected)|{'sequence.json'},'Foreign native artifact')
    require(sum(r['bytes'] for r in images.values())<=64*1024*1024,'Oversized native evidence')
    return dict(proof_sha256=digest(directory/'sequence.json'),images=images)


def verify(report,expected,*,native_directory=None):
    require(report.get('kind')=='phase5-m4-fixture-execution' and report.get('success') is True,'Missing/failed M4 execution')
    require(all(report.get(k)==expected[k] for k in ('head','plan_sha256')),'Stale M4 head/plan')
    require(report['ids_sha256']==digest(IDS) and report['inputs']==inputs(),'Changed M4 inputs')
    require(report.get('group') in GROUPS,'Unknown M4 group')
    selected=unique(selections()[report['group']],'M4 expected')
    for field in ('collection','execution'):
        require(report[field]['exitstatus']==0 and unique(report[field]['nodes'],field)==selected,'Missing/substituted M4 ID')
    counts=validate_execution(report['execution'])
    require(not counts.get('skipped') and report['operational_authority'] is False
        and report['real_operations_applied']==0 and report['real_package_approvals']==0,'Skipped test or fixture/production mismatch')
    if report['group']=='sequence':
        require(len(report['native_artifacts']['images'])==6,'Missing native report')
        if native_directory is not None:
            require(report['native_artifacts']==native_artifacts(native_directory),'Changed actual native artifacts')
    else:require(report['native_artifacts'] is None,'Unexpected native artifact group')
    return counts


def run(group):
    nodes=selections()[group];out=OUT/group
    report=dict(**identity(),kind='phase5-m4-fixture-execution',group=group,success=False,
        ids_sha256=digest(IDS),inputs=inputs(),operational_authority=False,
        real_operations_applied=0,real_package_approvals=0)
    try:
        os.environ['M4_NATIVE_EXPORT']='config/ci-validation/phase5-m4/native'
        report['collection']=pytest_run(nodes,out/'collection.json',collect=True)
        report['execution']=pytest_run(nodes,out/'execution.json')
        report['native_artifacts']=native_artifacts(OUT/'native') if group=='sequence' else None
        report['success']=True
        verify(report,identity())
    finally:write(out/'report.json',report)


def accept():
    needs=json.loads(os.environ['M4_JOB_RESULTS'])
    require(set(needs)=={'m4'} and needs['m4']['result']=='success','Missing/failed M4 matrix')
    root=ROOT/'config/m4-downloaded'
    reports=[read(p) for p in root.rglob('report.json')]
    pairs={(p,g) for p in ('Windows','Linux') for g in GROUPS}
    require(len(reports)==len(pairs) and {(r['platform'],r['group']) for r in reports}==pairs,'Missing/duplicate M4 platform/group')
    platforms={}
    for path in root.rglob('report.json'):
        report=read(path)
        directory=path.parent.parent/'native' if report['group']=='sequence' else None
        platforms.setdefault(report['platform'],{})[report['group']]=verify(report,identity(),native_directory=directory)
    write(OUT/'acceptance.json',dict(**identity(),kind='phase5-m4-fixture-acceptance',success=True,
        platforms=platforms,operational_authority=False,real_operations_applied=0,original_workflows_required=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('action',choices=['run','accept'])
    parser.add_argument('--group',choices=GROUPS);args=parser.parse_args()
    if args.action=='run':
        if args.group is None:parser.error('--group required')
        run(args.group)
    else:accept()
