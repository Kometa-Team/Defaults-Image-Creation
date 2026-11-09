"""Only local disposable Git remotes; no publication service or credentials."""
from copy import deepcopy
from pathlib import Path
import importlib
import json

import pytest
from people_git_transport import GitTransport, NativePublication, digest, failure, git_diagnostic, safe_git_diagnostic
from people_publication_state import PublicationState
from create_people_posters.reliability_tests import test_git_publication as fixture


def blocked(tmp_path,mp,style='diiivoycolor'):
    x=fixture.setup(tmp_path,mp,count=3,completed=1,style=style)
    push=x.t.push
    def reject(*args):
        error=failure('git_rejected',False,True)
        error.git_diagnostic=git_diagnostic(['push'],1,b'remote: GH013: rule violation')
        raise error
    x.t.push=reject
    with pytest.raises(Exception):fixture.run(x)
    x.t.push=push
    x.ledger.__class__=PublicationState
    x.backend=NativePublication(x.p,transport=x.t,contract=x.a,approval=digest(x.a))
    x.grant=x.backend.recovery_review(fixture.BATCH,0,'a'*64)
    x.before=[r for r in x.ledger.rows(fixture.BATCH) if r['status']=='published']
    x.windows_before=fixture.windows(x)
    mp.setenv('PEOPLE_GIT_RECOVERY_SHA256',digest(x.grant))
    return x


def resume(x):return x.backend.publish(fixture.BATCH,recovery=x.grant)


@pytest.mark.parametrize('style',['diiivoycolor','rainier','signature'])
def test_valid_recovery_preserves_receipts_membership_authority_and_readme(tmp_path,monkeypatch,style):
    x=blocked(tmp_path,monkeypatch,style)
    contract=x.ledger.db.execute('SELECT contract FROM publication_git_controls').fetchone()[0]
    members=[tuple(r) for r in x.ledger.db.execute('SELECT * FROM publication_git_members')]
    assert resume(x)['artwork_verified']
    assert [r for r in x.ledger.rows(fixture.BATCH) if r['path']==x.before[0]['path']]==x.before
    assert members==[tuple(r) for r in x.ledger.db.execute('SELECT * FROM publication_git_members')]
    assert contract==x.ledger.db.execute('SELECT contract FROM publication_git_controls').fetchone()[0]
    record=x.ledger.git_recovery(fixture.BATCH,x.a['repo'],digest(x.grant))
    assert record['before']==x.windows_before[0] and record['state']=='claimed'
    assert len(x.readmes)==1 and fixture.windows(x)[0]['stage']=='completed'


@pytest.mark.parametrize('case',['unapproved','source','membership','remote','published_receipt','backup','style','artifact','object','window','ownership','api_head','stored_blob'])
def test_unsafe_recovery_rejected_before_rearm_or_push(tmp_path,monkeypatch,case):
    x=blocked(tmp_path,monkeypatch)
    if case=='unapproved':monkeypatch.setenv('PEOPLE_GIT_RECOVERY_SHA256','b'*64)
    elif case=='source':x.grant['source_bindings']['people_git_transport.py']='b'*64
    elif case=='backup':x.grant['backup_sha256']='b'*64 # no longer matches the externally approved grant
    elif case=='style':x.grant['repo']='Kometa-Team/People-Images-signature'
    elif case=='artifact':Path(x.ledger.git_members(fixture.BATCH,x.a['repo'],0)[0]['prepared']).write_bytes(b'corrupt')
    elif case=='object':
        monkeypatch.setattr(x.t,'pack_size',lambda *args:0)
    elif case=='window':
        window=x.ledger.git_window(fixture.BATCH,x.a['repo'],0);window['pack_bytes']+=1
        x.ledger.git_window(fixture.BATCH,x.a['repo'],0,window)
    elif case=='ownership':
        with x.ledger.db:x.ledger.db.execute('DELETE FROM publication_git_controls')
    elif case=='api_head':x.p.client.head=lambda *args:('0'*40,'0'*40)
    elif case=='stored_blob':
        git=x.t.git
        x.t.git=lambda *args,**kwargs:b'corrupt' if args[:2]==('cat-file','blob') else git(*args,**kwargs)
    elif case=='membership':
        with x.ledger.db:x.ledger.db.execute("UPDATE publication_git_members SET object_sha=?",('0'*40,))
    elif case=='published_receipt':
        with x.ledger.db:x.ledger.db.execute("UPDATE publications SET commit_sha=? WHERE status='published'",('0'*40,))
    elif case=='remote':
        x.t.remote_head=lambda:'0'*40
    if case=='source':monkeypatch.setenv('PEOPLE_GIT_RECOVERY_SHA256',digest(x.grant))
    before=fixture.windows(x);calls=[];x.t.push=lambda *args:calls.append(args)
    with pytest.raises((ValueError,KeyError)):resume(x)
    assert not calls and fixture.windows(x)==before
    assert x.ledger.git_recovery(fixture.BATCH,x.a['repo'],digest(x.grant)) is None


@pytest.mark.parametrize('stage',['git_recovery_armed','git_recovery_claimed','git_push_ack','git_completed'])
def test_interrupted_recovery_and_no_duplicate_write(tmp_path,monkeypatch,stage):
    x=blocked(tmp_path,monkeypatch);calls=[];push=x.t.push
    def counted(*args):calls.append(args);return push(*args)
    x.t.push=counted
    def hook(event):
        if event==stage:raise fixture.Crash()
    x.p.checkpoint_hook=hook
    with pytest.raises(fixture.Crash):resume(x)
    x.p.checkpoint_hook=lambda event:None
    # Reopen SQLite to prove durability, not just object-local memory.
    state=x.ledger.state;x.ledger.close();x.ledger=PublicationState(state);x.p.ledger=x.ledger
    x.backend=NativePublication(x.p,transport=x.t,contract=x.a,approval=digest(x.a))
    if stage=='git_recovery_claimed':
        with pytest.raises(ValueError):resume(x)
        assert not calls
    else:
        assert resume(x)['artwork_verified'] and len(calls)==1


def test_successful_unacknowledged_push_reconciles_without_replay(tmp_path,monkeypatch):
    x=blocked(tmp_path,monkeypatch);push=x.t.push;calls=[]
    def lost(*args):
        calls.append(args);push(*args);raise failure('git_rejected',False,True)
    x.t.push=lost
    assert resume(x)['artwork_verified'] and len(calls)==1
    assert all(r['status']=='published' for r in x.ledger.rows(fixture.BATCH))


def test_repeat_permanent_rejection_retains_diagnostics_and_stops(tmp_path,monkeypatch):
    x=blocked(tmp_path,monkeypatch);calls=[]
    def rejected(*args):
        calls.append(args);error=failure('git_rejected',False,True)
        error.git_diagnostic=git_diagnostic(['push'],1,b'remote: GH013: rejected; fake-secret-987')
        raise error
    x.t.push=rejected
    with pytest.raises(Exception):resume(x)
    w=fixture.windows(x)[0]
    assert w['status']=='blocked' and w['error']['diagnostic']['reason']=='policy'
    assert 'fake-secret' not in json.dumps(w)
    with pytest.raises(ValueError):resume(x)
    assert len(calls)==1 and len(x.ledger.rows(fixture.BATCH))==3


def test_diagnostics_closed_vocabulary_and_no_provider_text():
    for text,reason in [(b'remote: pack exceeds maximum allowed size','pack_limit'),
                        (b'error: RPC failed; HTTP 503','unknown'),
                        (b'remote: arbitrary provider message fake-secret-987','unknown'),
                        (b'remote: GH013: policy; authentication failed','unknown')]:
        value=git_diagnostic(['push'],1,text,b'https://fake-secret-987@example.invalid')
        assert value['reason']==reason and safe_git_diagnostic(value)==value
        assert 'fake-secret' not in json.dumps(value)
    assert safe_git_diagnostic({'reason':'arbitrary fake-secret-987'})=={}
    assert safe_git_diagnostic(dict(operation='push',exit_code=True,http_status=0,reason='unknown'))=={}


def test_global_writer_lease_rejects_competing_owner(tmp_path,monkeypatch):
    module=importlib.import_module('people_git_recovery')
    path=tmp_path/'existing.lease';path.write_bytes(b'0');monkeypatch.setattr(module,'LEASE',path)
    with module.writer_lease():
        with pytest.raises(OSError):
            with module.writer_lease():pytest.fail('Competing lease admitted')
    with module.writer_lease():pass


def test_cli_never_prints_arbitrary_exception_or_credential(monkeypatch,capsys):
    module=importlib.import_module('people_git_recovery')
    def broken(*args):raise ValueError('Bearer fake-secret-987 https://fake-secret-987@example.invalid')
    monkeypatch.setattr(module,'main',broken)
    assert module.cli([])==1
    captured=capsys.readouterr()
    assert 'fake-secret' not in captured.err+captured.out
    assert 'recovery_authorization_state_or_transport' in captured.err


def test_predecessor_writer_cannot_bypass_consumed_recovery(tmp_path,monkeypatch):
    x=blocked(tmp_path,monkeypatch)
    def crash(event):
        if event=='git_recovery_claimed':raise fixture.Crash()
    x.p.checkpoint_hook=crash
    with pytest.raises(fixture.Crash):resume(x)
    # Predecessor source-bound authority is unchanged, but version 3 is a hard
    # fence in its existing version-2 validation. No downgrade/restore allowed.
    with pytest.raises(ValueError):fixture.run(x)
    assert fixture.windows(x)[0]['version']==3


def test_real_git_process_failure_has_closed_diagnostic(tmp_path,monkeypatch):
    x=fixture.setup(tmp_path,monkeypatch,count=1)
    x.t.__class__=GitTransport
    with pytest.raises(Exception) as caught:x.t.git('not-a-git-command-people-recovery')
    value=caught.value.git_diagnostic
    assert safe_git_diagnostic(value)==value and value['operation']=='other'
    assert value['exit_code']!=0 and value['reason']=='unknown'
    assert x.p.client.token not in json.dumps(value)


def test_backup_receipt_hash_and_stale_metadata_rejected(tmp_path,monkeypatch):
    from types import SimpleNamespace
    module=importlib.import_module('people_git_recovery')
    path=tmp_path/'BACKUP.json'
    value=dict(style='diiivoycolor',repo='Kometa-Team/People-Images-diiivoycolor',batch='fixture',
               source_state_unmodified=True,native_object_workspace_excluded=True,source_checksums={'fixture':'a'*64})
    path.write_bytes(json.dumps(value).encode())
    args=SimpleNamespace(backup_receipt=path,style=value['style'],state=tmp_path,validation=tmp_path/'validation.json')
    info=dict(repo=value['repo'],batch=value['batch'])
    sha=__import__('hashlib').sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(module,'fingerprints',lambda *args:value['source_checksums'])
    module.check_backup(args,info,sha,False)
    with pytest.raises(ValueError):module.check_backup(args,info,'b'*64,False)
    monkeypatch.setattr(module,'fingerprints',lambda *args:{'fixture':'b'*64})
    with pytest.raises(ValueError):module.check_backup(args,info,sha,False)
