"""No network or artwork: exercise the complete style-to-state approval bridge."""
from contextlib import closing
from pathlib import Path
import hashlib
import json
import os
import sqlite3
import sys
from unittest.mock import patch

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'create_people_posters'))
import people_native_operator as o


def hashes(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


@pytest.fixture(autouse=True)
def isolated_operator_environment():
    # CLI configuration changes environment directly; restore it between tests.
    # Keep real os.environ semantics and all in-test approval/security checks.
    with patch.dict(os.environ, os.environ.copy(), clear=True):
        yield


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    monkeypatch.setenv('PEOPLE_GITHUB_TARGET','production')
    monkeypatch.delenv('PEOPLE_SANDBOX_CONFIG',raising=False)
    state=tmp_path/'state'; state.mkdir(); styles={}
    for style,repo in o.STYLES.items():
        rows=[]
        for name in ('Ronkẹ Adékoluẹjo','Catherine OʻHara'):
            data=(style+name).encode(); src=tmp_path/style/(name+'.jpg')
            src.parent.mkdir(exist_ok=True); src.write_bytes(data)
            rows.append(dict(style=style,repo=repo,path='A/Images/'+src.name,person=name,
                source=str(src),prepared=str(src),source_hash=hashlib.sha256(data).hexdigest(),
                published_hash=hashlib.sha256(data).hexdigest(),blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()))
        batch='20261106T000000-'+hashlib.sha256(style.encode()).hexdigest()[:12]
        with closing(o.PublicationState(state/style)) as ledger:
            ledger.plan(batch,'master',rows)
            for row in rows:ledger.baseline(batch,repo,row['path'],None)
            styles[style]=dict(unit=batch,head=hashlib.sha1(style.encode()).hexdigest(),
                local_jpegs=2,entries_sha256=ledger.unit_binding(ledger.rows(batch)),
                baselines={r['path']:None for r in rows},filename_case_conflicts=[])
    validation=tmp_path/'validation.json'
    validation.write_bytes(o.canonical(dict(valid=True,read_only=True,verified=10,planned=10,errors=[],
        styles=list(o.STYLES),batch_id='render-fixture',source_commit='a'*40)))
    plan=dict(batch='render-fixture',source_commit='a'*40,styles=styles,
              validation_sha256=hashlib.sha256(validation.read_bytes()).hexdigest())
    (state/'reconciliation.json').write_bytes(o.canonical(plan))
    calls=[]
    class API:
        token='fake-multistyle-private-token-not-real'
        def head(self,repo,branch):
            calls.append(('HEAD',repo)); style=next(s for s,r in o.STYLES.items() if r==repo)
            return styles[style]['head'],'b'*40
        def request(self,method,path):
            calls.append((method,path)); assert method=='GET'
            return dict(state='active',path='.github/workflows/readme.yml')
    monkeypatch.setattr(o,'GitHubClient',API)
    return state,validation,styles,calls


def args(f,style):
    state,validation,_,_=f
    return ['--state',str(state),'--validation',str(validation),'--style',style]


@pytest.mark.parametrize('style',tuple(o.STYLES))
def test_all_styles_review_preflight_backup_register_and_resume_selection(fixture,tmp_path,monkeypatch,style):
    state,validation,plans,calls=fixture; before=hashes(state)
    review=tmp_path/(style+'-review.json'); base=args(fixture,style)
    o.main(['review',*base,'--output',str(review)])
    contract=json.loads(review.read_bytes())
    assert contract['repo']==o.STYLES[style] and contract['batch']==plans[style]['unit']
    assert contract['max_posters']==0 and contract['target_source_bytes']==1_500_000_000 and contract['max_pack_bytes']==1_850_000_000
    assert set(contract['source_bindings'])==set(o.SOURCE_MEMBERS)
    assert hashes(state)==before and not calls
    o.main(['preflight',*base,'--approval',str(review)])
    assert hashes(state)==before and all(method in {'HEAD','GET'} for method,path in calls)
    backup=tmp_path/(style+'-backup');o.main(['backup',*base,'--output',str(backup)])
    assert set(p.name for p in (backup/'state').iterdir())=={style,'reconciliation.json'}
    monkeypatch.setenv('PEOPLE_PUBLICATION_MODE','native-git-v2')
    monkeypatch.setenv('PEOPLE_GIT_APPROVAL_SHA256',hashlib.sha256(review.read_bytes()).hexdigest())
    o.main(['migrate',*base,'--approval',str(review),'--backup-receipt',str(backup/'BACKUP.json')])
    for other in o.STYLES:
        if other!=style:
            assert {n:v for n,v in hashes(state).items() if n.startswith(other+'/')}=={n:v for n,v in before.items() if n.startswith(other+'/')}
    with closing(o.view(state,style)) as ledger:
        assert ledger.db.execute('SELECT count(*) FROM publication_git_controls').fetchone()[0]==1
        assert all(r['status']=='pending' for r in ledger.rows(plans[style]['unit']))
    seen=[]
    def offline_publish(backend,batch):
        assert backend.p.repositories=={style:o.STYLES[style]}
        assert backend.ledger.state==state/style and batch==plans[style]['unit']
        seen.append(batch);return dict(offline=True)
    monkeypatch.setattr(o.NativePublication,'publish',offline_publish)
    o.main(['run',*base,'--approval',str(review)])
    o.main(['run',*base,'--approval',str(review)])
    assert seen==[plans[style]['unit']]*2
    # Existing v2 contract works after registration without adding any new key.
    snapshot=hashes(state);o.main(['preflight',*base,'--approval',str(review)])
    assert hashes(state)==snapshot


@pytest.mark.parametrize('style',['unknown','BW','../bw','original','transparent','bw\nsecret'])
def test_unknown_styles_rejected_before_state_or_network(monkeypatch,style):
    def forbidden(*a,**k):raise AssertionError('No state or API access')
    monkeypatch.setattr(o,'view',forbidden);monkeypatch.setattr(o,'GitHubClient',forbidden)
    with pytest.raises(ValueError):o.main(['status','--style',style])


@pytest.mark.parametrize('attack',['style','repository','inventory','backup'])
def test_cross_style_mismatches_fail_before_network_or_state_writes(fixture,tmp_path,monkeypatch,attack):
    state,_,_,calls=fixture; review=tmp_path/'review.json';base=args(fixture,'diiivoy')
    o.main(['review',*base,'--output',str(review)]); contract=json.loads(review.read_bytes())
    backup=tmp_path/'backup';o.main(['backup',*base,'--output',str(backup)])
    if attack=='style':base=args(fixture,'signature')
    if attack=='repository':contract['repo']=o.STYLES['rainier'];review.write_bytes(o.canonical(contract))
    if attack=='inventory':
        with sqlite3.connect(state/'diiivoy/publication_state.db') as db:
            db.execute("UPDATE publications SET style='rainier'")
    if attack=='backup':
        p=backup/'BACKUP.json';v=json.loads(p.read_bytes());v['style']='bw';p.write_bytes(o.canonical(v))
    before=hashes(state)
    monkeypatch.setenv('PEOPLE_PUBLICATION_MODE','native-git-v2')
    monkeypatch.setenv('PEOPLE_GIT_APPROVAL_SHA256',hashlib.sha256(review.read_bytes()).hexdigest())
    with pytest.raises(ValueError):o.main(['migrate',*base,'--approval',str(review),'--backup-receipt',str(backup/'BACKUP.json')])
    assert not calls and hashes(state)==before


def test_wrong_hash_redaction_and_env_selection(fixture,tmp_path,monkeypatch,capsys):
    state,validation,_,calls=fixture; review=tmp_path/'review.json';base=args(fixture,'signature')
    o.main(['review',*base,'--output',str(review)])
    monkeypatch.setenv('PEOPLE_PUBLICATION_MODE','native-git-v2');monkeypatch.setenv('PEOPLE_GIT_APPROVAL_SHA256','0'*64)
    monkeypatch.setenv('GITHUB_TOKEN','fake-never-emit-credential-7192')
    monkeypatch.setenv('PEOPLE_GIT_STYLE','signature')
    before=hashes(state)
    assert o.cli(['run',*base,'--approval',str(review)])==1
    o.main(['status','--state',str(state),'--validation',str(validation)])
    assert not calls and hashes(state)==before
    assert 'fake-never-emit-credential-7192' not in ''.join(capsys.readouterr())


@pytest.mark.parametrize('style',tuple(o.STYLES))
def test_readme_recovery_audit_is_readonly_and_repository_scoped(fixture,tmp_path,monkeypatch,style):
    state,_,_,calls=fixture;review=tmp_path/'review.json';base=args(fixture,style)
    o.main(['review',*base,'--output',str(review)])
    expected=o.STYLES[style]
    class API:
        def head(self,repo,branch):assert repo==expected;return 'f'*40,'b'*40
        def request(self,method,path):
            calls.append((method,path));assert method=='GET' and expected in path
            return dict(state='active',path='.github/workflows/readme.yml')
    monkeypatch.setattr(o,'GitHubClient',API)
    audited=[]
    def audit(backend,batch):
        assert backend.p.inventory.repositories=={style:expected}
        assert backend.a['repo']==expected and backend.ledger.state==state/style
        audited.append((batch,expected))
    monkeypatch.setattr(o.NativePublication,'audit_artwork',audit)
    before=hashes(state)
    o.main(['preflight',*base,'--approval',str(review)])
    o.main(['preflight',*base,'--approval',str(review)])
    assert len(audited)==2 and hashes(state)==before and all(m=='GET' for m,p in calls)


@pytest.mark.parametrize('style',tuple(o.STYLES))
def test_existing_readme_controller_reconciles_lost_dispatch_per_repository(tmp_path,monkeypatch,style):
    from create_people_posters.reliability_tests import test_publication_reliability as existing
    client,entries,ledger,inventory,clock=existing.setup_run(tmp_path,monkeypatch,style=style)
    client.failures=[dict(method='POST',point='other',after=True,
        error=existing.GitHubClient.reliability_error('network',retryable=True,ambiguous=True))]
    try:
        existing.run(client,ledger,inventory,clock)
        assert ledger.verified(existing.BATCH)
        dispatches=[path for method,path,payload in client.calls if method=='POST' and 'dispatches' in path]
        assert len(dispatches)==1 and '/repos/'+o.STYLES[style]+'/' in dispatches[0]
        assert ledger.readme_state(existing.BATCH,o.STYLES[style])['status']=='verified'
    finally:ledger.close();inventory.close()
