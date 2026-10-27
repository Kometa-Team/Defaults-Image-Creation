"""Narrow reviewed cleanup successor. Historical security inventories stay sealed."""
import hashlib
import json
from pathlib import Path
import stat
import subprocess

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'ci/people-retention-maintenance-v1.json'
PIN='a4dc0c5b30b2ab1da3934c31b28406760a640447c66222a34113c84699e577f1'
WORKSPACE='create_people_posters/people_workspaces.py'
ANCHORS=frozenset({'ci/people_retention_maintenance.py','ci/people-retention-maintenance-v1.json'})
MEMBERS=frozenset({
    WORKSPACE,'ci/people_storage_maintenance.py',
    'create_people_posters/people_retention_state.py','create_people_posters/people_retention_remote.py',
    'create_people_posters/people_verified_cleanup.py',
    'ci/dependency_tests/test_people_retention.py','ci/dependency_tests/test_people_retention_maintenance.py',
    'docs/PEOPLE_POSTERS_RETENTION_AUDIT.md','docs/PEOPLE_POSTERS_RETENTION_PROPOSAL.md',
    'docs/PEOPLE_VERIFIED_CLEANUP.md','docs/PEOPLE_PRACTICAL_STORAGE_FINDINGS.md',
})


def sha(raw):return hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def regular(root,name):
    root=Path(root).absolute();p=root/name
    for item in (p,*p.parents):
        st=item.lstat()
        if stat.S_ISLNK(st.st_mode) or getattr(st,'st_file_attributes',0)&0x400:
            raise ValueError('Retention source link/reparse rejected')
        if item==p and not stat.S_ISREG(st.st_mode):raise ValueError('Retention source not regular')
        if item==root:break
    return p


def manifest():
    value=json.loads(regular(ROOT,MANIFEST.relative_to(ROOT).as_posix()).read_bytes())
    if (canonical(value)!=PIN or set(value['members'])!=MEMBERS or value['baseline_commit']!='ded9f33759f9fe3ed4ddf5f315dff01b163594ad'
            or value['audit_ancestor']!='d4cbb20ff1dbaa77e30c017de9671b85f3355362'
            or value['production_successors']!=[WORKSPACE] or value['publication_authorized'] is not False):
        raise ValueError('Changed exact retention transition')
    return value


def verify_checkout(root=None):
    root=Path(root or ROOT);value=manifest()
    subprocess.check_call(['git','merge-base','--is-ancestor',value['audit_ancestor'],'HEAD'],cwd=root)
    for name,binding in value['members'].items():
        if sha(regular(root,name).read_bytes())!=binding['sha256']:
            raise ValueError('Unreviewed retention successor: '+name)
        if binding['before_sha256'] is not None:
            # Keep new ancestry reads independent of frozen fixtures that patch
            # check_output for their own historical baselines. Never broaden
            # those fixtures or substitute a caller-provided baseline.
            old=subprocess.run(['git','show',value['baseline_commit']+':'+name],
                cwd=root,check=True,stdout=subprocess.PIPE).stdout
            if sha(old)!=binding['before_sha256']:raise ValueError('Changed retention predecessor')
    for name in ANCHORS:regular(root,name)
    return value


def selected_hash(name,expected):
    if name!=WORKSPACE:return expected
    binding=manifest()['members'][name]
    if expected!=binding['before_sha256']:return expected
    verify_checkout()
    return binding['sha256']


def scope_members():return MEMBERS|ANCHORS


def verify_scope(root,baseline,names):
    verify_checkout(root)
    if not names<=scope_members():raise ValueError('Unauthorized retention scope')
    rows=subprocess.check_output(['git','diff','--raw','--no-abbrev','--no-renames','-z',baseline,'HEAD','--',*sorted(names)],cwd=root).split(b'\0')
    if rows[-1]!=b'' or len(rows)!=2*len(names)+1:raise ValueError('Incomplete retention diff')
    seen=set()
    for i in range(0,len(rows)-1,2):
        fields,name=rows[i].split(),rows[i+1].decode('utf8')
        modified=name==WORKSPACE
        if (name not in names or name in seen or len(fields)!=5 or fields[:2]!=([b':100644',b'100644'] if modified else [b':000000',b'100644'])
                or fields[4]!=(b'M' if modified else b'A')):
            raise ValueError('Retention diff must match exact regular-file additions/successor')
        regular(root,name);seen.add(name)


def test_ids():return manifest()['mandatory_unittest_ids']
