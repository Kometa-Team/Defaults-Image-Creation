"""Independently approved exact M4 successor; no baseline or authority changes."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess

from ci.people_storage_maintenance import regular

ROOT=Path(__file__).resolve().parents[1]
BASE='120ed09a166ddfdc5380219aad35959c8a0de169'
MANIFEST=ROOT/'ci/phase5-m4-maintenance-v1.json'
PIN='467c0fc8c5dd2f982c43e89b4249f3f75c286c6c9254847c3ba7cbccfc62242c'
MEMBERS=frozenset({
    'ci/phase5_m3_maintenance.py','ci/dependabot_maintenance.py',
    'ci/dependency_tests/test_phase5_m3_maintenance.py',
    'create_defaults/bulk/lifecycle/apply.py','create_defaults/bulk/lifecycle/mappings.py',
    'create_defaults/bulk/lifecycle/recovery.py','create_defaults/lifecycle/ROADMAP.md',
    '.github/workflows/phase5-m4-validation.yml',
    'ci/dependency_tests/test_phase5_m4_maintenance.py','ci/phase5-m4-test-ids.json','ci/phase5_m4.py',
    'create_defaults/bulk/lifecycle/current_mapping.py',
    'create_defaults/lifecycle/PHASE5_M4_ACCEPTANCE.json',
    'create_defaults/lifecycle/PHASE5_M4_CI_MAINTENANCE.md',
    'create_defaults/lifecycle/PHASE5_M4_IMPLEMENTATION.md',
    'create_defaults/lifecycle/PHASE5_M4_COVERAGE.json',
    'create_defaults/phase5/m4_tests/conftest.py','create_defaults/phase5/m4_tests/helpers.py',
    'create_defaults/phase5/m4_tests/test_current_mapping.py','create_defaults/phase5/m4_tests/test_guards.py',
})
ANCHORS=frozenset({'ci/phase5_m4_maintenance.py','ci/phase5-m4-maintenance-v1.json'})
FROZEN=frozenset({'create_defaults/bulk/lifecycle/'+n for n in ('apply.py','mappings.py','recovery.py')})


def sha(raw):
    return hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True,
        allow_nan=False,separators=(',',':')).encode()).hexdigest()


@lru_cache(maxsize=8)
def _decode(raw,pin):
    value=json.loads(raw)
    if (fingerprint(value)!=pin or value['version']!=1 or value['baseline_commit']!=BASE
            or set(value['members'])!=MEMBERS or value['publication_authorized'] is not False
            or value['production_intersection']!=[] or value['adoption_intersection']!=[]
            or set(value['frozen_m7_intersection'])!=FROZEN):
        raise ValueError('Changed exact M4 maintenance transition')
    return value


def manifest():
    return _decode(regular(ROOT,MANIFEST.relative_to(ROOT).as_posix()).read_bytes(),PIN)


def _git(root,*args):
    with subprocess.Popen(['git',*args],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
        raw,_=process.communicate()
        if process.returncode: raise ValueError('Cannot verify M4 maintenance history')
        return raw.replace(b'\r\n',b'\n')


@lru_cache(maxsize=32)
def _old(name):
    return _git(ROOT,'show',BASE+':'+name)


@lru_cache(maxsize=32)
def _ancestry(root,head):
    _git(root,'merge-base','--is-ancestor',BASE,head)


def verify_checkout(root=None):
    root=Path(root or ROOT)
    from ci.people_job_retention_maintenance import verify_checkout as verify_retention, historical_bytes as retention_bytes
    verify_retention(root)
    value=manifest()
    from ci.people_colorize_maintenance import _head
    _ancestry(str(root),_head(root))
    for name,binding in value['members'].items():
        if sha(retention_bytes(root,name,regular(root,name).read_bytes()))!=binding['sha256']:
            raise ValueError('Unreviewed M4 successor: '+name)
        if binding['before_sha256'] is not None and sha(_old(name))!=binding['before_sha256']:
            raise ValueError('Changed M4 predecessor: '+name)
    for name in ANCHORS: regular(root,name)
    return value


def historical_bytes(root,name,current):
    if name not in MEMBERS: return current
    binding=manifest()['members'][name]
    if binding['before_sha256'] is None: return current
    # Verify the physical successor even when several inherited validators
    # project the same in-memory predecessor. A rollback of the actual path
    # never qualifies for this idempotent historical-only projection.
    actual=regular(Path(root),name).read_bytes()
    from ci.people_job_retention_maintenance import historical_bytes as retention_bytes
    physical=retention_bytes(root,name,actual)
    if current==actual: current=physical
    if sha(physical)!=binding['sha256']:
        raise ValueError('Changed M4 physical successor: '+name)
    before=_old(name)
    if sha(before)!=binding['before_sha256']:
        raise ValueError('Changed M4 historical predecessor: '+name)
    if sha(current) not in {binding['sha256'],binding['before_sha256']}:
        raise ValueError('Changed M4 historical input: '+name)
    return before


def scope_members():
    # A caller inspecting a different/minimal repository cannot inherit the
    # runtime allowance owned by this exact source checkout. That repository
    # must load its own reviewed policy from its own checkout.
    from ci.phase4_m7 import ROOT as policy_root
    if Path(policy_root).resolve()!=ROOT.resolve():
        return frozenset()
    return (MEMBERS|ANCHORS)-{'create_defaults/lifecycle/ROADMAP.md'}


def verify_scope(root,baseline,names):
    verify_checkout(root)
    if not names<=scope_members(): raise ValueError('Unapproved M4 scope')
    if not names: return
    rows=_git(root,'diff','--raw','--no-abbrev','--no-renames','-z',baseline,'HEAD','--',*sorted(names)).split(b'\0')
    if rows[-1]!=b'' or len(rows)!=2*len(names)+1: raise ValueError('Incomplete M4 scope diff')
    seen=set()
    for offset in range(0,len(rows)-1,2):
        fields,name=rows[offset].split(),rows[offset+1].decode('utf8')
        if (name not in names or name in seen or len(fields)!=5
                or fields[:2] not in ([b':000000',b'100644'],[b':100644',b'100644'])
                or fields[4]!=(b'A' if fields[0]==b':000000' else b'M')):
            raise ValueError('M4 requires regular-file additions/modifications')
        regular(Path(root),name);seen.add(name)
