"""Exact-ID offline M5 execution and independent native/catalog/Git evidence."""
import argparse
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ci.validation import identity,read,write,require,unique,pytest_run,validate_execution

IDS=ROOT/'ci/phase5-m5-test-ids.json'
OUT=ROOT/'config/ci-validation/phase5-m5'
TESTS='create_defaults/phase5/m5_tests'
GROUPS=tuple(json.loads(IDS.read_bytes()))
NATIVE={'current':'current','multi':'multi','transport':'single'}
SOURCES=tuple(sorted([
    'ci/phase5_m5.py','ci/phase5_m5_maintenance.py','ci/phase5-m5-maintenance-v1.json',
    *('create_defaults/bulk/lifecycle/'+n for n in ('catalog_preparation.py','publication_preparation.py',
        'preparation_models.py','preparation_progress.py','schemas/preparation-v1.schema.json')),
    *(p.relative_to(ROOT).as_posix() for p in (ROOT/TESTS).glob('*.py'))]))


def digest(path):return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
def inputs():return {n:digest(ROOT/n) for n in SOURCES}


def selections():
    groups=read(IDS);require(tuple(groups)==GROUPS and groups,'Missing M5 group')
    seen=set()
    for group,nodes in groups.items():
        selected=unique(nodes,group)
        require(selected and not seen&selected and all(n.startswith(TESTS+'/test_') for n in selected),'Invalid M5 IDs')
        seen|=selected
    return groups


def native_artifacts(directory,label):
    from PIL import Image
    from create_defaults.bulk.common import canonical,fingerprint
    from create_defaults.bulk.contracts.models import decode_json
    from create_defaults.bulk.lifecycle.operations import DefinitionSnapshot,payload
    from create_defaults.bulk.lifecycle.preparation_models import Preparation,FLAGS
    from create_defaults.bulk.lifecycle.catalog_preparation import FILES,patch_yaml,patch_index,git
    from create_defaults.bulk.lifecycle.publication_preparation import tree
    from create_defaults.bulk.definitions import load_definitions
    from create_defaults.bulk.planner import Planner
    from create_defaults.bulk.library_stage import verify_diff
    directory=Path(directory);proof=read(directory/'proof.json')
    require(proof['sha256']==fingerprint({k:v for k,v in proof.items() if k!='sha256'}),'Changed M5 proof')
    require(proof['kind']=='phase5-m5-native-offline-proof' and proof['simulation'] is True
        and proof['publication_authorized'] is False and proof['historical_artwork_regenerated']==0
        and proof['network_writes']==0,'Invalid native authority/history')
    preparation=Preparation.from_dict(proof['preparation']);value=preparation.to_dict()
    require(preparation.sha256==proof['preparation_sha256'],'Changed preparation')
    require(all(value[k] is v for k,v in FLAGS.items()),'Authority-positive preparation')
    catalog=proof['catalog'];require(fingerprint(catalog)==proof['catalog_sha256']==value['catalog_sha256'],'Changed catalog')
    require(catalog['simulation'] is True and catalog['production_authorized'] is False,'Production catalog evidence')
    snapshots=[DefinitionSnapshot.from_dict(s) for s in proof['snapshots']]
    require([s.sha256 for s in snapshots]==proof['snapshot_sha256'] and len(set(proof['snapshot_sha256']))==len(snapshots),'Changed native snapshots')
    require(snapshots[-1].sha256==value['snapshot_sha256'],'Wrong accepted epoch')
    expected={}
    for number,snapshot in enumerate(snapshots):
        s=snapshot.to_dict();composition=json.loads(s['composition_json'])
        require(fingerprint(composition)==s['composition_sha256'],'Changed native composition')
        require({v['appearance'] for v in composition['views']}=={'default','requested'},'Missing full native views')
        require(s['members']==value['required_members'],'Omitted native member')
        for view in composition['views']:
            require({m['identity'] for m in view['members']}==set(s['members']),'Incomplete native view')
            for m in view['members']:expected[f"epoch-{number}-{view['appearance']}-{m['identity']}.jpg"]=m
    require(len(snapshots)==(3 if label=='current' else 1),'Missing native history')
    require(len(value['members'])==(2 if label=='multi' else 1),'Wrong complete operation size')
    if label=='current':
        i=value['required_members'][0];mapping=proof['mapping'];last=snapshots[-1].to_dict()
        require(len({s.to_dict()['artwork'][i]['sha256'] for s in snapshots})==3,'Missing distinct native artwork epochs')
        require(mapping['members']==[i] and mapping['after'][i]['names']['public_path']=='genre/fixture.jpg','Missing case-only retained mapping')
        require(last['expected_snapshots']=={i:snapshots[1].sha256}
            and last['entries'][i]['original_names']==mapping['before'][i]['original_names']
            and all(a in last['entries'][i]['aliases'] for a in mapping['after'][i]['aliases']),'Lost retained aliases/receipt lineage')
    images={}
    for row in proof['rows']:
        name,m,receipt,worker=(row[k] for k in ('file','member','receipt','worker'))
        require(name in expected and name not in images and m==expected[name],'Foreign/duplicate native image')
        raw=(directory/name).read_bytes()
        require(hashlib.sha256(raw).hexdigest()==m['sha256']==receipt['sha256'] and len(raw)==m['bytes']==receipt['size'],'Changed full artwork')
        require(receipt['receipt_sha256']==m['receipt_sha256']==fingerprint({k:v for k,v in receipt.items() if k!='receipt_sha256'}),'Changed receipt')
        require(worker['status']=='verified' and worker['id']==receipt['job_id']
            and worker['receipt']==canonical(receipt).decode()
            and fingerprint(json.loads(worker['spec']))==worker['fingerprint']==receipt['job_fingerprint'],'Foreign owned worker')
        with Image.open(BytesIO(raw)) as image:
            image.load();require((image.format,image.mode,list(image.size))==('JPEG','RGB',[2000,3000]) and m['dimensions']==[2000,3000],'Thumbnail substitution')
        images[name]=dict(sha256=m['sha256'],bytes=len(raw),receipt_sha256=m['receipt_sha256'])
    require(set(images)==set(expected),'Omitted native JPEG')
    desired=payload(snapshots[-1].to_dict()['proposed_json'])['effective_definitions']
    before={n:(directory/(n+'.before')).read_bytes() for n in FILES}
    after={n:(directory/(n+'.after')).read_bytes() for n in FILES}
    for name in FILES:
        require(hashlib.sha256(before[name]).hexdigest()==catalog['files'][name]['before_sha256']
            and hashlib.sha256(after[name]).hexdigest()==catalog['files'][name]['after_sha256'],'Changed catalog pre/postimage')
    require(before['profiles.yml']==after['profiles.yml'] and after['genre.yml']==patch_yaml(before['genre.yml'],desired)
        and after['index-v1.json']==patch_index(before['index-v1.json'],desired),'Unintended catalog bytes')
    with tempfile.TemporaryDirectory(prefix='m5-artifact-') as folder:
        staging=Path(folder);definitions=[]
        for label_,files in [('before',before),('after',after)]:
            path=staging/label_;path.mkdir()
            for name,raw in files.items():(path/name).write_bytes(raw)
            rows=load_definitions([path/'genre.yml'],profiles_path=path/'profiles.yml')
            jobs,families,_=Planner().expand(rows)
            require(not families and set(jobs)=={r.id for r in rows},'Unexpected expanded jobs')
            definitions.append({r.id:r.data for r in rows})
        require(definitions[1]==dict(definitions[0],**desired),'Unrelated effective definition change')
        require(catalog['unchanged_jobs']==len(definitions[0].keys()-desired.keys()),'Wrong unchanged job count')
        old_index,new_index=(decode_json(f['index-v1.json']) for f in (before,after))
        require(all(new_index['posters'][i]==r for i,r in old_index['posters'].items()),'Changed historical lookup')
        require({i for i,r in new_index['posters'].items() if r['category']=='Genre'}==set(definitions[1]),'Incomplete lookup postimage')
        repo=staging/'remote.git'
        subprocess.run(['git','clone','--bare',str((directory/'transport.bundle').resolve()),str(repo)],check=True,capture_output=True,timeout=180)
        base=value['destination']['head'];head=proof['transport']['head'];batches=value['plan']['batches']
        require(git(repo,'rev-parse','refs/heads/library-offline').decode().strip()==head,'Wrong actual remote head')
        initial=tree(repo,base);actual=tree(repo,head);expected_tree=dict(initial)
        require(set(initial)=={'keep.txt','.gitattributes'} and git(repo,'show',base+':keep.txt')==b'Unrelated baseline bytes\n','Foreign baseline tree')
        chain=git(repo,'rev-list','--reverse',base+'..'+head).decode().splitlines()
        require(len(chain)==len(batches)==proof['transport']['verified_batches'],'Missing complete Git prefix')
        parent=base
        for commit,batch in zip(chain,batches):
            require(git(repo,'rev-parse',commit+'^').decode().strip()==parent,'Changed Git ancestry')
            verify_diff(repo,parent,commit,batch['members'])
            for m in batch['members']:expected_tree[m['destination']]=dict(mode='100644',blob=m['git_blob'])
            parent=commit
        require(actual==expected_tree,'Unrelated Git tree changes')
        for member in value['members']:
            raw=git(repo,'show',head+':'+member['destination'])
            require(hashlib.sha256(raw).hexdigest()==member['sha256'] and len(raw)==member['size'],'Wrong remote artwork bytes')
        execution=proof['transport_execution']
        require(execution['network_writes']==0 and execution['complete'] and execution['plan_sha256']==value['plan']['sha256'],'Missing original transport execution')
        require(len(proof['packs'])==len(batches),'Missing actual incremental packs')
        for pack in proof['packs']:
            require(Path(pack['file']).name==pack['file'] and pack['file'].endswith('.pack'),'Unsafe pack name')
            raw=(directory/pack['file']).read_bytes()
            require(len(raw)==pack['bytes']<=value['plan']['max_pack_bytes'] and hashlib.sha256(raw).hexdigest()==pack['sha256'],'Changed/oversized Git pack')
            subprocess.run(['git','-C',str(repo),'index-pack','--strict','--stdin'],input=raw,
                check=True,capture_output=True,timeout=180)
    progress=proof['progress']
    require(proof['transport']['complete'] and progress['state']=='OFFLINE_VERIFIED'
        and progress['verified_batches']==progress['planned_batches']==len(value['plan']['batches'])
        and progress['head']==proof['transport']['head'] and progress['publication_authorized'] is False,'Incomplete progress evidence')
    allowed={'proof.json','transport.bundle',*(n+'.'+suffix for n in FILES for suffix in ('before','after')),*images,*(p['file'] for p in proof['packs'])}
    require({p.name for p in directory.iterdir()}==allowed,'Foreign native evidence file')
    return dict(proof_sha256=digest(directory/'proof.json'),images=images,batches=len(value['plan']['batches']),native_epochs=len(snapshots),historical_artwork_regenerated=0)


def verify(report,expected,*,native_directory=None):
    require(report.get('kind')=='phase5-m5-fixture-execution' and report.get('success') is True,'Missing M5 execution')
    require(all(report.get(k)==expected[k] for k in ('head','plan_sha256')),'Stale M5 identity')
    require(report['ids_sha256']==digest(IDS) and report['inputs']==inputs(),'Changed M5 inputs')
    group=report.get('group');require(group in GROUPS,'Unknown M5 group')
    selected=unique(selections()[group],'M5 expected')
    for field in ('collection','execution'):
        require(report[field]['exitstatus']==0 and unique(report[field]['nodes'],field)==selected,'Missing/substituted M5 ID')
    counts=validate_execution(report['execution'])
    require(not counts.get('skipped') and report['operational_authority'] is False
        and report['real_operations_applied']==0 and report['real_package_approvals']==0,'Skipped or authority-positive M5 execution')
    if group in NATIVE:
        require(report['native_artifacts'] is not None,'Missing M5 native artifact')
        if native_directory is not None:require(report['native_artifacts']==native_artifacts(native_directory,NATIVE[group]),'Changed actual M5 artifacts')
    else:require(report['native_artifacts'] is None,'Unexpected M5 native evidence')
    return counts


def run(group):
    nodes=selections()[group];out=OUT/group
    report=dict(**identity(),kind='phase5-m5-fixture-execution',group=group,success=False,
        ids_sha256=digest(IDS),inputs=inputs(),operational_authority=False,real_operations_applied=0,real_package_approvals=0)
    try:
        os.environ['M5_NATIVE_EXPORT']=str(OUT/'native')
        report['collection']=pytest_run(nodes,out/'collection.json',collect=True)
        report['execution']=pytest_run(nodes,out/'execution.json')
        report['native_artifacts']=native_artifacts(OUT/'native'/NATIVE[group],NATIVE[group]) if group in NATIVE else None
        report['success']=True;verify(report,identity())
    finally:write(out/'report.json',report)


def accept():
    needs=json.loads(os.environ['M5_JOB_RESULTS'])
    require(set(needs)=={'m5'} and needs['m5']['result']=='success','Missing/failed M5 matrix')
    paths=list((ROOT/'config/m5-downloaded').rglob('report.json'))
    pairs={(p,g) for p in ('Windows','Linux') for g in GROUPS}
    require(len(paths)==len(pairs) and {(read(p)['platform'],read(p)['group']) for p in paths}==pairs,'Missing/duplicate M5 platform/group')
    platforms={}
    for path in paths:
        report=read(path);group=report['group']
        native=path.parent.parent/'native'/NATIVE[group] if group in NATIVE else None
        platforms.setdefault(report['platform'],{})[group]=verify(report,identity(),native_directory=native)
    write(OUT/'acceptance.json',dict(**identity(),kind='phase5-m5-fixture-acceptance',success=True,platforms=platforms,
        operational_authority=False,real_operations_applied=0,original_workflows_required=9))


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('action',choices=['run','accept'])
    parser.add_argument('--group',choices=GROUPS);args=parser.parse_args()
    if args.action=='run':
        if args.group is None:parser.error('--group required')
        run(args.group)
    else:accept()
