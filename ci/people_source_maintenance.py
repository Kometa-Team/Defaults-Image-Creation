"""Exact source-only successor; historical receipts and authority stay unchanged."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess

from ci.people_storage_maintenance import regular
from ci.people_collection_maintenance import _head

ROOT=Path(__file__).resolve().parents[1]
BASE='a89df404a554f648f7f83d119e4af0e34073a866'
RECEIPT='ci/people-source-only-v1.json'
PIN='ca33bbeaceb38fb17145295114e23e951cf2ff934174d84cc55f853487297e69'
OWNER='ci/people_source_maintenance.py'
ENTRY='ci/phase6_playlist_maintenance.py'
MEMBERS=frozenset((
    'create_people_posters/audit_people_images.py',
    'create_people_posters/create_people_poster.py',
    'create_people_posters/find_and_download_missing_people.py',
    'create_people_posters/image_check.py',
    'create_people_posters/orchestrator.py',
    'create_people_posters/people_batch_safety.py',
    'create_people_posters/people_github.py',
    'create_people_posters/people_remote_inventory.py',
    'create_people_posters/people_workspaces.py',
    'create_people_posters/publish_people_github.py',
    'create_people_posters/recover_edge_chops.py',
    'create_people_posters/sel_remove_bg.py',
    'create_people_posters/sync_people_images.py',
    'create_people_posters/tmdb_people.py',
    'create_people_posters/tests/test_people_source_only.py',
    'create_people_posters/tests/test_people_api_orchestrator.py',
    'create_people_posters/tests/test_people_pipeline_failures.py',
    'create_people_posters/tests/test_background_orchestrator.py',
    'create_people_posters/tests/test_people_startup_retention.py',
    'create_people_posters/SOURCE_ONLY.md',
    'ci/people_unicode_maintenance.py',
    'ci/people_publication_maintenance.py',
    'ci/people_readme_maintenance.py',
    'ci/phase5_m7_maintenance.py',
    'ci/phase5_m6_maintenance.py',
    'ci/publication_tests/test_git_publication_maintenance.py',
    'ci/publication_tests/test_git_recovery_maintenance.py',
    'ci/unicode_tests/test_people_unicode_maintenance.py',
    'ci/dependency_tests/test_phase6_playlist_maintenance.py',
    'ci/dependency_tests/test_catalog_reservations_maintenance.py',
    'ci/dependency_tests/test_catalog_data_maintenance.py',
))

def sha(raw):return hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()
def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def scope_members():return MEMBERS|{RECEIPT,OWNER,ENTRY}
def git(*args,data=None):
    result=subprocess.run(['git',*args],cwd=ROOT,input=data,capture_output=True,timeout=180)
    if result.returncode:raise ValueError('Cannot authenticate source-only successor history')
    return result.stdout

@lru_cache(maxsize=16)
def objects(head):
    trees=[];oids=set()
    for commit in (BASE,head):
        tree={}
        for row in filter(None,git('ls-tree','-r','-z',commit,'--',*sorted(scope_members())).split(b'\0')):
            metadata,name=row.split(b'\t');mode,kind,oid=metadata.decode().split();name=name.decode('utf8')
            if mode!='100644' or kind!='blob':raise ValueError('Source-only successor requires regular Git files')
            tree[name]=oid;oids.add(oid)
        trees.append(tree)
    payload=git('cat-file','--batch',data=b''.join((oid+'\n').encode() for oid in sorted(oids)))
    blobs={};offset=0
    for expected in sorted(oids):
        end=payload.index(b'\n',offset);oid,kind,length=payload[offset:end].decode().split();offset=end+1
        size=int(length)
        if oid!=expected or kind!='blob' or not 0<size<4*1024**2:raise ValueError('Invalid source-only Git object')
        raw=payload[offset:offset+size];offset+=size+1
        if hashlib.sha1(b'blob '+str(size).encode()+b'\0'+raw).hexdigest()!=oid:raise ValueError('Changed source-only Git object')
        blobs[oid]=raw
    if offset!=len(payload):raise ValueError('Extra source-only Git object bytes')
    return tuple(tuple((name,blobs[oid]) for name,oid in tree.items()) for tree in trees)

@lru_cache(maxsize=16)
def immutable(head):
    git('merge-base','--is-ancestor',BASE,head)
    before,current=map(dict,objects(head))
    value=json.loads(current[RECEIPT])
    if (fingerprint(value)!=PIN or set(value['files'])!=MEMBERS or value['baseline_commit']!=BASE
            or value['publication_authorized'] is not False or value['version']!=1):
        raise ValueError('Changed exact source-only receipt')
    rows=git('diff','--raw','--no-abbrev','--no-renames','-z',BASE,head).split(b'\0')
    if rows[-1]!=b'' or len(rows)!=2*len(scope_members())+1:raise ValueError('Incomplete source-only successor diff')
    seen=set()
    for offset in range(0,len(rows)-1,2):
        fields=rows[offset].split();name=rows[offset+1].decode('utf8')
        if (name not in scope_members() or name in seen or len(fields)!=5 or fields[1]!=b'100644'
                or fields[0]!=(b':100644' if name in before else b':000000')
                or fields[4]!=(b'M' if name in before else b'A')):
            raise ValueError('Unapproved source-only successor path, mode or operation')
        seen.add(name)
    if seen!=scope_members() or set(current)!=scope_members():raise ValueError('Missing source-only successor member')
    for name,binding in value['files'].items():
        if (set(binding)!={'before_sha256','sha256'} or sha(current[name])!=binding['sha256']
                or (sha(before[name]) if name in before else None)!=binding['before_sha256']):
            raise ValueError('Changed committed source-only predecessor or successor: '+name)
    return value,tuple(sorted(before.items())),tuple(sorted((name,sha(raw)) for name,raw in current.items()))

def verify(root=ROOT):
    if Path(root).resolve()!=ROOT.resolve():raise ValueError('Foreign source-only checkout')
    head=_head(ROOT)
    value,before,current=immutable(head)
    if fingerprint(json.loads(regular(ROOT,RECEIPT).read_bytes()))!=PIN:raise ValueError('Changed physical source-only receipt')
    for name,expected in current:
        if sha(regular(ROOT,name).read_bytes())!=expected:raise ValueError('Changed physical source-only successor: '+name)
    if _head(ROOT)!=head:raise ValueError('HEAD moved during source-only verification')
    return value,dict(before)

def historical_bytes(root,name,current):
    if name not in MEMBERS:return current
    value,before=verify(root);binding=value['files'][name]
    actual=regular(ROOT,name).read_bytes()
    if sha(actual)!=binding['sha256']:raise ValueError('Changed source-only projection input: '+name)
    return before.get(name,current) if sha(current)==binding['sha256'] else current

def selected_hash(name,expected):
    if name not in MEMBERS:return expected
    value,_=verify();binding=value['files'][name]
    return binding['sha256'] if expected==binding['before_sha256'] else expected

def test_ids():return list(verify()[0]['pytest_ids'])
