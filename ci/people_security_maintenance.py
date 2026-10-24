"""Exact authorized People security maintenance; no activation/publication grant."""
import ast
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE='46e1334504fcdd598e0c34fcd45612ff58e91074'
PIN='24d1eaa0d17bdccdf5b14159db5f62d19989ab30f4e42ce9085bc949a448b37d'
EXPECTED_FILES=frozenset(['.github/workflows/default-poster-validation.yml', 'ci/phase4.py', 'ci/phase4_transactions.py', 'ci/tests/test_validation.py', 'ci/validation.py', 'create_defaults/bulk/contracts/activation/data/production-pins-v1.json', 'create_defaults/bulk/contracts/activation/protection.py', 'create_defaults/bulk/tests/test_activation.py', 'create_defaults/phase3/tests/test_isolation_ci.py', 'create_defaults/phase4/tests/test_ci_transactions.py', 'create_defaults/tests/test_validation.py', 'create_people_posters/audit_people_images.py', 'create_people_posters/auto_readme.py', 'create_people_posters/colorize_noncolor_ddcolor.py', 'create_people_posters/ensure_people_repo.py', 'create_people_posters/find_and_download_missing_people.py', 'create_people_posters/orchestrator.py', 'create_people_posters/people_github.py', 'create_people_posters/people_publication_state.py', 'create_people_posters/people_workspaces.py', 'create_people_posters/publish_people_github.py', 'create_people_posters/recover_edge_chops.py', 'create_people_posters/remove_bg_birefnet.py', 'create_people_posters/resolve_original_images.py', 'create_people_posters/review_tmdb_profile_alternates.py', 'create_people_posters/sandbox_people_github.py', 'create_people_posters/scan_kometa_logs.py', 'create_people_posters/sel_remove_bg.py', 'create_people_posters/smoke_people_models.py', 'create_people_posters/stage_original_candidates.py', 'create_people_posters/tests/test_background_orchestrator.py', 'create_people_posters/tests/test_people_api_orchestrator.py', 'create_people_posters/tests/test_people_github.py', 'create_people_posters/tests/test_remove_bg_birefnet.py', 'create_people_posters/tmdb_people.py', 'create_people_posters/tmdb_top_people_list.py', 'create_people_posters/update_people_repos.py'])
PINS='create_defaults/bulk/contracts/activation/data/production-pins-v1.json'
PROTECTION='create_defaults/bulk/contracts/activation/protection.py'

def _require(value,message):
    if not value:raise ValueError(message)
def _fp(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def _bytes(path):return path.read_bytes().replace(b'\r\n',b'\n')
def _sha(path):return hashlib.sha256(_bytes(path)).hexdigest()
@lru_cache(maxsize=2048)
def _old(root,path):return subprocess.check_output(['git','show',BASE+':'+path],cwd=root).replace(b'\r\n',b'\n')

@lru_cache(maxsize=256)
def _no_activation(raw):
    # Cache only exact immutable source bytes. Every call still reads/checks
    # all 190 current hashes; a changed/resealed source has a different key.
    tree=ast.parse(raw)
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):names=[a.name for a in node.names]
        elif isinstance(node,ast.ImportFrom):names=[node.module or '']+[a.name for a in node.names]
        elif isinstance(node,ast.Constant) and isinstance(node.value,str):names=[node.value]
        else:continue
        _require(not any('contracts.activation' in n or 'activation-controller' in n for n in names),
                 'Production activation import is prohibited')
    return True

def verify(root=ROOT):
    root=Path(root)
    value=json.loads((root/'ci/people-security-maintenance.json').read_text(encoding='utf8'))
    _require(_fp(value)==PIN and value['schema_version']==1 and value['base']==BASE
             and set(value['files'])==EXPECTED_FILES,'Unexpected People security maintenance')
    for name,pins in value['files'].items():
        _require(set(pins)=={'before_sha256','sha256'} and hashlib.sha256(_old(root,name)).hexdigest()==pins['before_sha256']
                 and _sha(root/name)==pins['sha256'],'Changed exact People security maintenance: '+name)
    for name,expected in value['additions'].items():
        _require(_sha(root/name)==expected,'Changed new People security source: '+name)
    for name in ('ci/validation-plan.json','ci/original-test-ids.json','ci/phase3-test-ids.json',
                 'ci/phase4-test-ids.json','ci/phase4-composition-test-ids.json','ci/phase4-review-test-ids.json',
                 'ci/phase4-transaction-test-ids.json','ci/phase4-maintenance.json','ci/phase4-m3-maintenance.json',
                 'ci/phase4-m4-maintenance.json','ci/phase4-m5-maintenance.json'):
        _require(_bytes(root/name)==_old(root,name),'Changed frozen CI selection/provenance: '+name)
    before=json.loads(_old(root,PINS));after=json.loads((root/PINS).read_text(encoding='utf8'))
    _require(len(before['files'])==len(after['files'])==190 and before['files'].keys()==after['files'].keys(),
             'Changed 190-file protected membership')
    changed=sorted(n for n in before['files'] if before['files'][n]!=after['files'][n])
    _require(changed==value['protected_changes'] and all(n=='.github/workflows/default-poster-validation.yml'
             or n.startswith('create_people_posters/') for n in changed),'Unexpected protected production change')
    expected_context={**before['maintenance_context'],'people_security_baseline_commit':BASE,
        'people_security_previous_manifest_sha256':_fp(before),'people_security_changed_sources_sha256':_fp(changed)}
    _require(after=={**before,'files':after['files'],'maintenance_context':expected_context},'Changed historical pin structure or provenance')
    for name,expected in after['files'].items():
        source=_bytes(root/name)
        _require(hashlib.sha256(source).hexdigest()==expected,'Changed protected production bytes: '+name)
        if name.endswith('.py'):
            _no_activation(source)
    expected_source=_old(root,PROTECTION).replace(_fp(before).encode(),_fp(after).encode())
    _require(_bytes(root/PROTECTION)==expected_source,'Production protection changed beyond exact manifest hash')
    return value

def baseline_pins(root=ROOT):
    verify(root)
    return json.loads(_old(Path(root),PINS))

def historical_bytes(root,path):
    value=verify(root)
    return _old(Path(root),path) if path in value['files'] else _bytes(Path(root)/path)
