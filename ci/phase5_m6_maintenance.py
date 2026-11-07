"""Approved exact M6 cohort: physical successor checks before historical views."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess

from ci.people_storage_maintenance import regular

ROOT=Path(__file__).resolve().parents[1]
BASE='9da96b0df12526daaee6156bc7778bbd57d9e8b6'
MANIFEST=ROOT/'ci/phase5-m6-maintenance-v1.json'
PIN='23db82401a8fea8ae09564b4e3c3c8056abc1dde4e42607af1416e1bff5b74db'
INTERSECTIONS={'production_intersection': ['create_defaults/bulk/library_stage.py', 'create_defaults/bulk/operator_publication.py'], 'adoption_intersection': ['create_defaults/bulk/contracts/models.py', 'create_defaults/bulk/library_stage.py', 'create_defaults/bulk/operator_publication.py'], 'frozen_m7_intersection': ['ci/dependency_maintenance.py', 'ci/phase4.py', 'create_defaults/bulk/contracts/models.py', 'create_defaults/bulk/library_stage.py', 'create_defaults/bulk/lifecycle/models.py', 'create_defaults/bulk/operator_publication.py', 'create_defaults/phase3/tests/test_final_phase3_acceptance.py', 'create_defaults/phase4/tests/test_ci_foundations.py']}
MEMBERS=frozenset(['.github/workflows/phase5-m6-validation.yml', 'ci/dependency_maintenance.py', 'ci/dependency_tests/test_phase5_m5_maintenance.py', 'ci/dependency_tests/test_phase5_m6_maintenance.py', 'ci/phase5-m6-test-ids.json', 'ci/phase5_m5_maintenance.py', 'ci/phase5_m6.py', 'create_defaults/bulk/library_stage.py', 'create_defaults/bulk/lifecycle/draft_models.py', 'create_defaults/bulk/lifecycle/draft_progress.py', 'create_defaults/bulk/lifecycle/draft_transport.py', 'create_defaults/bulk/lifecycle/schemas/draft-transport-v1.schema.json', 'create_defaults/bulk/operator_publication.py', 'create_defaults/lifecycle/PHASE5_M6_ACCEPTANCE.json', 'create_defaults/lifecycle/PHASE5_M6_CI_MAINTENANCE.md', 'create_defaults/lifecycle/PHASE5_M6_COVERAGE.json', 'create_defaults/lifecycle/PHASE5_M6_IMPLEMENTATION.md', 'create_defaults/lifecycle/ROADMAP.md', 'create_defaults/phase5/m6_tests/conftest.py', 'create_defaults/phase5/m6_tests/helpers.py', 'create_defaults/phase5/m6_tests/test_binding.py', 'create_defaults/phase5/m6_tests/test_boundaries.py', 'create_defaults/phase5/m6_tests/test_draft.py', 'create_defaults/phase5/m6_tests/test_preservation.py', 'create_defaults/phase5/m6_tests/test_recovery.py', 'create_defaults/phase5/m6_tests/test_transport.py', 'create_defaults/bulk/contracts/models.py', 'ci/people_storage_maintenance.py', 'ci/dependabot_maintenance.py', 'create_defaults/bulk/lifecycle/models.py', 'ci/phase4.py', 'ci/dependency_tests/test_people_job_retention_maintenance.py', 'create_defaults/phase3/tests/test_final_phase3_acceptance.py', 'create_defaults/phase4/tests/test_ci_foundations.py'])
ANCHORS=frozenset(['ci/phase5-m6-maintenance-v1.json', 'ci/phase5_m6_maintenance.py'])
APPROVED={'ci/dependency_maintenance.py': ('4468fff249d0a0fa7533d8be6102284520594a0470e77968c4c45e8fc239c789', '107ebdfa93cfa78126c2517d95c04c73efeb0d79e7aae1124d3e152a5c7fb662'), 'ci/dependency_tests/test_phase5_m5_maintenance.py': ('b24a74e41af88e3a81f27f0b7a2a58a69bccdea48075446a11bbe0bd876787fd', '2af3fe3303c86b8457d10c34553d0dbb9172071132449861026d78bf8fd19c4c'), 'ci/phase5_m5_maintenance.py': ('9b1ff0afce7318f6eaa08bb098b24444401bb49692211f2c432ac3d7a3a77c74', 'b035c366441315115339a4b8cc12625d9934718de8f2718da2663b528e47b846'), 'create_defaults/bulk/library_stage.py': ('2a521973a04c35f96059430abcee4bc000c4b51b40c902cd50654427571ade2c', 'f528c6b8c5064a00243b5d28900dab0eb68e1a5ad381ab9d46d074239e86e7c7'), 'create_defaults/bulk/operator_publication.py': ('efdaecff2df59d429ba52dda1f3580dfe1953d8138c6131ca59d45ad6a05fa7a', '39e4d54dca3a2954bd09fc41aecc556313f0d5804ffd03ec5c1606144d6f866e'), 'create_defaults/lifecycle/ROADMAP.md': ('79a722ebfd77be147b9375673ea77dbb44e6ef62ac325b6299bd77ec24a690e9', '359d467f601787c4fdf6e369e0971f6fe0a7c49df65114f7aca8c82de0514f82'), 'create_defaults/bulk/contracts/models.py': ('226f42af5aa9e1b79ed569e2e4f459c0737fc39e1e9908417ce0a49b7136602c', '77d5b6a9df1fc342b7ce47748dc22ee5dcd518031c98499c477e3958a8550559'), 'ci/people_storage_maintenance.py': ('af3e037f8b4af95d5c8d096c501b8b8f2b4a9023a7b4a1519a6fd4b46fbd4e3c', '8e2420d6d6868781acea9a9a0806b2bf904ea4027095a1fd61db3885fe8394f7'), 'ci/dependabot_maintenance.py': ('b82b688ca74c180c7d6f78ca7bc66c467ae40b5207e311d41209f080c5f2b1c2', '82900620fdb1b2bcda15b3eb68706a1e5a30725ff391d95c424ca0249c71cb95'), 'create_defaults/bulk/lifecycle/models.py': ('26dc51e272f8d9748d5b763e125872406ac52a1081aa1dddf7bc15f9f3ca9b4a', 'f92610f30a5e67d5613c5f9f7e5a9b4272eb0afd2c12eac2a8ba2ec073ede9f9'), 'ci/phase4.py': ('1ce5155558ffcfb4c6c9f28d0813658df52d4170a6af44022425460951ef7a1d', 'dae564e48195a0fe9d124ab5c12ac19e4bc61062dea823f8dbdd55b6f2506dce'), 'ci/dependency_tests/test_people_job_retention_maintenance.py': ('2955e546701a6cb6fc7fc2771952d44dbc9f26350dab21fc76b145e7eda88be6', '04909acdd3e81b58cbef8631cd1fe2e9df990f65e16a00537efc6e1c05f1fb43'), 'create_defaults/phase3/tests/test_final_phase3_acceptance.py': ('9d7b8f29966b7b7017c5da16ef0aaaa056459b012b8869eba316e8463530f104', '9a6539d75cac6d64a27ab21fd6fdb663f0505bafa95489f5293899c2bff0f143'), 'create_defaults/phase4/tests/test_ci_foundations.py': ('68a9ff7ff545d5d3b8ca137efcd31a57bb6c6471ef40c28646042109944f5289', 'e6abe467a74db91ae359beb9d828939e9ed67634bfa756eb0c15c6b8b5afcfb2')}
RETAINED={'ci/phase4.py':['16e7c89d628f42d719a726b805b578483a76bc5f6183a6dbeed06e0609f24677'],
    'ci/dependency_tests/test_phase5_m5_maintenance.py':['c52e04c1d57d4eccd48155a7da4c8404dc0dba7a9f7be2557e99c33bc092985c'],
    'create_defaults/phase4/tests/test_ci_foundations.py':['54f37e811ceebc40d82f12106e52ef5fd02d98d5369b3d1f73f5118da0c53347'],
    'create_defaults/lifecycle/ROADMAP.md': [
    'c830b33101d202e6118c84c7d63ccf40b0a7639eefcaa6687d73e2c9469d87fc',
    'f776dea7e1d719439df2fb1f6c8ddea30297eda6bf63f30e9f93cea7f502ca96',
],
    # Exact predecessor already bound by M5's immutable manifest and original
    # historical-view test. This is an in-memory view only; historical_bytes
    # still verifies every physical M6 successor before accepting it.
    'ci/dependency_tests/test_people_job_retention_maintenance.py': [
        'c8e03edba1c697e73995d584d5026099273965098479297daf0a7f064fe50258',
    ],
}


@lru_cache(maxsize=128)
def sha(raw):return hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()
def fingerprint(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def _git(root,*args):
    return _git_raw(root,*args).replace(b'\r\n',b'\n')


def _git_raw(root,*args,input=None):
    result=subprocess.run(['git',*args],cwd=root,input=input,capture_output=True)
    if result.returncode:raise ValueError('Cannot verify M6 history')
    return result.stdout


@lru_cache(maxsize=8)
def _decode(raw,pin):
    v=json.loads(raw)
    if (fingerprint(v)!=pin or set(v)!={'version','baseline_commit','members','publication_authorized','production_intersection','adoption_intersection','frozen_m7_intersection'}
            or v['version']!=1 or v['baseline_commit']!=BASE or set(v['members'])!=MEMBERS
            or v['publication_authorized'] is not False or any(v[k]!=INTERSECTIONS[k] for k in INTERSECTIONS)):raise ValueError('Changed exact M6 manifest')
    changed={n for n,b in v['members'].items() if b['before_sha256'] is not None}
    if changed!=set(APPROVED):raise ValueError('Changed M6 predecessor membership')
    for name,(before,after) in APPROVED.items():
        if v['members'][name]!={'before_sha256':before,'sha256':after}:raise ValueError('Changed independently approved M6 successor')
    return v


def manifest():return _decode(regular(ROOT,MANIFEST.relative_to(ROOT).as_posix()).read_bytes(),PIN)


@lru_cache(maxsize=1)
def _baseline_tree():
    # Only immutable objects at the fixed, independently approved BASE are cached.
    raw=_git_raw(ROOT,'ls-tree','-z',BASE,'--',*sorted(MEMBERS))
    if not raw.endswith(b'\0'):raise ValueError('Incomplete M6 predecessor tree')
    entries={}
    for row in raw[:-1].split(b'\0'):
        fields,name=row.split(b'\t',1);name=name.decode('utf8');fields=fields.split()
        if (name not in APPROVED or name in entries or len(fields)!=3 or fields[:2]!=[b'100644',b'blob']
                or len(fields[2])!=40 or any(c not in b'0123456789abcdef' for c in fields[2])):raise ValueError('Changed M6 predecessor tree')
        entries[name]=fields[2]
    if set(entries)!=set(APPROVED):raise ValueError('Changed M6 predecessor membership')
    return tuple(sorted(entries.items()))


@lru_cache(maxsize=1)
def _predecessors():
    entries=_baseline_tree()
    raw=_git_raw(ROOT,'cat-file','--batch',input=b''.join(oid+b'\n' for _,oid in entries))
    values=[];offset=0
    for name,oid in entries:
        end=raw.find(b'\n',offset)
        fields=raw[offset:end].split()
        if end<offset or len(fields)!=3 or fields[:2]!=[oid,b'blob'] or not fields[2].isdigit():raise ValueError('Invalid M6 predecessor batch')
        size=int(fields[2]);start=end+1;end=start+size
        if end>=len(raw) or raw[end:end+1]!=b'\n':raise ValueError('Truncated M6 predecessor batch')
        data=raw[start:end]
        if (hashlib.sha1(b'blob '+str(size).encode()+b'\0'+data).hexdigest().encode()!=oid
                or sha(data)!=APPROVED[name][0]):raise ValueError('Changed M6 predecessor bytes')
        values.append((name,data.replace(b'\r\n',b'\n')));offset=end+1
    if offset!=len(raw):raise ValueError('Unexpected M6 predecessor batch data')
    return tuple(values)


@lru_cache(maxsize=32)
def _old(name):
    if name in APPROVED:return dict(_predecessors())[name]
    return _git(ROOT,'show',BASE+':'+name)


@lru_cache(maxsize=64)
def _baseline_entry(name):
    if name in MEMBERS:
        oid=dict(_baseline_tree()).get(name)
        return b'100644 blob '+oid+b'\t'+name.encode()+b'\n' if oid is not None else b''
    return _git(ROOT,'ls-tree',BASE,'--',name)


@lru_cache(maxsize=32)
def _ancestry(root,head):_git(root,'merge-base','--is-ancestor',BASE,head)


def _physical_paths(root,names):
    from ci.people_readme_maintenance import _regular_files
    # A new lstat of every leaf and shared ancestor on EVERY call. The inherited
    # helper caches path arithmetic only, never filesystem or permission facts.
    return _regular_files(root,names|{MANIFEST.relative_to(ROOT).as_posix()})


def verify_checkout(root=None):
    root=Path(root or ROOT)
    if root.resolve()!=ROOT.resolve():raise ValueError('Foreign M6 policy checkout')
    paths=_physical_paths(root,MEMBERS|ANCHORS)
    value=_decode(paths[MANIFEST.relative_to(ROOT).as_posix()].read_bytes(),PIN)
    from ci.people_colorize_maintenance import _head
    _ancestry(str(root),_head(root))
    for name,binding in value['members'].items():
        if sha(paths[name].read_bytes())!=binding['sha256']:raise ValueError('Changed physical M6 successor: '+name)
        if binding['before_sha256'] is not None and sha(_old(name))!=binding['before_sha256']:raise ValueError('Changed M6 predecessor')
        if binding['before_sha256'] is None and _baseline_entry(name).strip():raise ValueError('M6 addition exists in predecessor')
    return value


def historical_bytes(root,name,current):
    if name not in APPROVED:return current
    root=Path(root)
    if root.resolve()!=ROOT.resolve():raise ValueError('Foreign M6 historical projection')
    paths=_physical_paths(root,MEMBERS|ANCHORS)
    value=_decode(paths[MANIFEST.relative_to(ROOT).as_posix()].read_bytes(),PIN)
    for member,pin in value['members'].items():
        if sha(paths[member].read_bytes())!=pin['sha256']:raise ValueError('Changed physical M6 successor: '+member)
    binding=_decode(paths[MANIFEST.relative_to(ROOT).as_posix()].read_bytes(),PIN)['members'][name]
    actual=paths[name].read_bytes()
    if sha(actual)!=binding['sha256']:raise ValueError('Changed M6 physical successor: '+name)
    if binding['before_sha256'] is None:
        if sha(current)!=binding['sha256']:raise ValueError('Changed M6 new member')
        return current
    before=_old(name)
    if sha(before)!=binding['before_sha256']:raise ValueError('Changed M6 predecessor')
    if sha(current) in RETAINED.get(name,[]):return current
    if sha(before)!=binding['before_sha256'] or sha(current) not in {binding['sha256'],binding['before_sha256']}:raise ValueError('Forged M6 projection')
    return before


def scope_members():
    from ci.phase4_m7 import ROOT as policy_root
    if Path(policy_root).resolve()!=ROOT.resolve():return frozenset()
    return (MEMBERS|ANCHORS)-{'create_defaults/lifecycle/ROADMAP.md'}


def verify_scope(root,baseline,names):
    verify_checkout(root)
    if not names<=scope_members():raise ValueError('Unapproved M6 scope')
    if not names:return
    rows=_git(root,'diff','--raw','--no-abbrev','--no-renames','-z',baseline,'HEAD','--',*sorted(names)).split(b'\0')
    if rows[-1]!=b'' or len(rows)!=2*len(names)+1:raise ValueError('Incomplete M6 scope diff')
    seen=set()
    for offset in range(0,len(rows)-1,2):
        fields,name=rows[offset].split(),rows[offset+1].decode('utf8')
        if (name not in names or name in seen or len(fields)!=5 or fields[:2] not in ([b':000000',b'100644'],[b':100644',b'100644'])
                or fields[4]!=(b'A' if fields[0]==b':000000' else b'M')):raise ValueError('M6 requires regular-file additions/modifications')
        seen.add(name)
    _physical_paths(Path(root),seen)


def selected_hash(name,expected):
    if name not in {'create_defaults/bulk/library_stage.py','create_defaults/bulk/operator_publication.py','create_defaults/bulk/contracts/models.py','ci/people_storage_maintenance.py','ci/phase4.py','create_defaults/bulk/lifecycle/models.py'}:return expected
    if expected!=APPROVED[name][0]:return expected
    verify_checkout()
    return APPROVED[name][1]
