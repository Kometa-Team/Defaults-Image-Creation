"""Approved exact M5 cohort: physical successor checks before historical views."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess

from ci.people_storage_maintenance import regular

ROOT=Path(__file__).resolve().parents[1]
BASE='3c15fb56b63bababa5d216b8d885e7dee257c11d'
MANIFEST=ROOT/'ci/phase5-m5-maintenance-v1.json'
PIN='78a80a6b031d77c3b09e56e9e382bd76cfccd80c7c01e6156999845f48f6f9e5'
MEMBERS=frozenset({
    '.github/workflows/phase5-m5-validation.yml',
    'ci/dependency_tests/test_phase5_m4_maintenance.py','ci/dependency_tests/test_phase5_m5_maintenance.py',
    'ci/people_job_retention_maintenance.py','ci/dependency_tests/test_people_job_retention_maintenance.py',
    'ci/phase5-m5-test-ids.json','ci/phase5_m4_maintenance.py','ci/phase5_m5.py',
    'create_defaults/bulk/lifecycle/catalog_preparation.py','create_defaults/bulk/lifecycle/preparation_models.py',
    'create_defaults/bulk/lifecycle/preparation_progress.py','create_defaults/bulk/lifecycle/publication_preparation.py',
    'create_defaults/bulk/lifecycle/schemas/preparation-v1.schema.json',
    'create_defaults/lifecycle/PHASE5_M5_ACCEPTANCE.json','create_defaults/lifecycle/PHASE5_M5_CI_MAINTENANCE.md',
    'create_defaults/lifecycle/PHASE5_M5_COVERAGE.json','create_defaults/lifecycle/PHASE5_M5_IMPLEMENTATION.md',
    'create_defaults/lifecycle/ROADMAP.md','create_defaults/phase5/m5_tests/conftest.py',
    'create_defaults/phase5/m5_tests/helpers.py','create_defaults/phase5/m5_tests/test_boundaries.py',
    'create_defaults/phase5/m5_tests/test_catalog.py','create_defaults/phase5/m5_tests/test_offline_git.py',
    'create_defaults/phase5/m5_tests/test_publication.py','create_defaults/phase5/m5_tests/test_recovery.py',
})
ANCHORS=frozenset({'ci/phase5_m5_maintenance.py','ci/phase5-m5-maintenance-v1.json'})
APPROVED={
    'ci/phase5_m4_maintenance.py':('4a38d98fb4f96d2886ca5c31aff2bc974120e114e60b94ce012b1f0c12ec1a9c','fd92f30d1525616b17875595c9a3c1abd59b9440e11c0ac8c5660c4c60c08eee'),
    'ci/dependency_tests/test_phase5_m4_maintenance.py':('27c4e891a91880a84235402086b9465b3ff6ebf8d0197e3d7c2c116f387747b4','38d8dde83e2f1a06bf666e476185544ba7c532186d260cd5afa1da56328a3442'),
    'ci/people_job_retention_maintenance.py':('4f8b7e54488f1c9b0103ee75a75c100d4f320d68a9a52008f865125427ae169a','c4049fff0510e11591906aa77f99cdce78a7f79699248217659f779a44ee0736'),
    'ci/dependency_tests/test_people_job_retention_maintenance.py':('c8e03edba1c697e73995d584d5026099273965098479297daf0a7f064fe50258','2955e546701a6cb6fc7fc2771952d44dbc9f26350dab21fc76b145e7eda88be6'),
    'create_defaults/lifecycle/ROADMAP.md':('c830b33101d202e6118c84c7d63ccf40b0a7639eefcaa6687d73e2c9469d87fc','79a722ebfd77be147b9375673ea77dbb44e6ef62ac325b6299bd77ec24a690e9'),
}
# Only the two exact retained pre-PR59 inputs named in the amendment.
# These are in-memory views; actual files must still match APPROVED successors.
RETAINED={
    'ci/phase5_m4_maintenance.py':'9d2cd0f449c701abf05c23763728afcad22d9211ff0e98db812750169e8dbf91',
    'ci/dependency_tests/test_phase5_m4_maintenance.py':'ea0e237accf3fca42c93283cae75009e4fd2b908f7a3b0959f1240c6ec7797da',
}


def sha(raw):return hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()
def fingerprint(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def _git(root,*args):
    result=subprocess.run(['git',*args],cwd=root,capture_output=True)
    if result.returncode:raise ValueError('Cannot verify M5 history')
    return result.stdout.replace(b'\r\n',b'\n')


@lru_cache(maxsize=8)
def _decode(raw,pin):
    v=json.loads(raw)
    if (fingerprint(v)!=pin or set(v)!={'version','baseline_commit','members','publication_authorized','production_intersection','adoption_intersection','frozen_m7_intersection'}
            or v['version']!=1 or v['baseline_commit']!=BASE or set(v['members'])!=MEMBERS
            or v['publication_authorized'] is not False or any(v[k]!=[] for k in ('production_intersection','adoption_intersection','frozen_m7_intersection'))):raise ValueError('Changed exact M5 manifest')
    changed={n for n,b in v['members'].items() if b['before_sha256'] is not None}
    if changed!=set(APPROVED):raise ValueError('Changed M5 predecessor membership')
    for name,(before,after) in APPROVED.items():
        if v['members'][name]!={'before_sha256':before,'sha256':after}:raise ValueError('Changed independently approved M5 successor')
    return v


def manifest():return _decode(regular(ROOT,MANIFEST.relative_to(ROOT).as_posix()).read_bytes(),PIN)


@lru_cache(maxsize=32)
def _old(name):return _git(ROOT,'show',BASE+':'+name)


@lru_cache(maxsize=64)
def _baseline_entry(name):return _git(ROOT,'ls-tree',BASE,'--',name)


@lru_cache(maxsize=32)
def _ancestry(root,head):_git(root,'merge-base','--is-ancestor',BASE,head)


def verify_checkout(root=None):
    root=Path(root or ROOT)
    if root.resolve()!=ROOT.resolve():raise ValueError('Foreign M5 policy checkout')
    value=manifest()
    from ci.people_colorize_maintenance import _head
    _ancestry(str(root),_head(root))
    for name,binding in value['members'].items():
        if sha(regular(root,name).read_bytes())!=binding['sha256']:raise ValueError('Changed physical M5 successor: '+name)
        if binding['before_sha256'] is not None and sha(_old(name))!=binding['before_sha256']:raise ValueError('Changed M5 predecessor')
        if binding['before_sha256'] is None and _baseline_entry(name).strip():raise ValueError('M5 addition exists in predecessor')
    for name in ANCHORS:regular(root,name)
    return value


def historical_bytes(root,name,current):
    if name not in MEMBERS:return current
    root=Path(root)
    if root.resolve()!=ROOT.resolve():raise ValueError('Foreign M5 historical projection')
    binding=manifest()['members'][name]
    actual=regular(root,name).read_bytes()
    if sha(actual)!=binding['sha256']:raise ValueError('Changed M5 physical successor: '+name)
    if binding['before_sha256'] is None:
        if sha(current)!=binding['sha256']:raise ValueError('Changed M5 new member')
        return current
    before=_old(name)
    if name in RETAINED and sha(current)==RETAINED[name]:
        if sha(before)!=binding['before_sha256']:raise ValueError('Changed M5 predecessor')
        return current
    if sha(before)!=binding['before_sha256'] or sha(current) not in {binding['sha256'],binding['before_sha256']}:raise ValueError('Forged M5 projection')
    return before


def scope_members():
    from ci.phase4_m7 import ROOT as policy_root
    if Path(policy_root).resolve()!=ROOT.resolve():return frozenset()
    return (MEMBERS|ANCHORS)-{'create_defaults/lifecycle/ROADMAP.md'}


def verify_scope(root,baseline,names):
    verify_checkout(root)
    if not names<=scope_members():raise ValueError('Unapproved M5 scope')
    if not names:return
    rows=_git(root,'diff','--raw','--no-abbrev','--no-renames','-z',baseline,'HEAD','--',*sorted(names)).split(b'\0')
    if rows[-1]!=b'' or len(rows)!=2*len(names)+1:raise ValueError('Incomplete M5 scope diff')
    seen=set()
    for offset in range(0,len(rows)-1,2):
        fields,name=rows[offset].split(),rows[offset+1].decode('utf8')
        if (name not in names or name in seen or len(fields)!=5 or fields[:2] not in ([b':000000',b'100644'],[b':100644',b'100644'])
                or fields[4]!=(b'A' if fields[0]==b':000000' else b'M')):raise ValueError('M5 requires regular-file additions/modifications')
        regular(Path(root),name);seen.add(name)
