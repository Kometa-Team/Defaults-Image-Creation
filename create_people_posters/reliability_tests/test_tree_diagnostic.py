"""Candidate-only offline tests; no protected source or real state is modified."""
from pathlib import Path
from types import SimpleNamespace
import ast, builtins, hashlib, importlib.util, json, sys
import pytest
import requests

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'create_people_posters'))
sys.path.insert(0,str(ROOT))
from create_people_posters import people_diagnostics as diagnostics
import people_github as candidate
TARGET='/repos/Kometa-Team/People-Images-bw/git/trees'
SECRET='offline-tree-diagnostic-credential-not-real-39e9f'
SECONDARY='You have exceeded a secondary rate limit. Please wait a few minutes before you try again.'


def response(status,body,headers=None):
    r=requests.Response();r.status_code=status
    r._content=body if type(body) is bytes else json.dumps(body).encode()
    r.headers.update(headers or {})
    return r


def invoke(monkeypatch,r,attempts=1,method='POST',path=TARGET):
    monkeypatch.delenv('PEOPLE_RELIABLE_PUBLISH',raising=False)
    monkeypatch.setenv('PEOPLE_GITHUB_WRITE_INTERVAL','0')
    calls=[];delays=[]
    session=SimpleNamespace(headers={},request=lambda *a,**k:calls.append((a,k)) or r)
    client=candidate.GitHubClient(SECRET,session=session,sleep=delays.append,attempts=attempts)
    with pytest.raises(candidate.GitHubError) as caught:
        client.request(method,path,{'base_tree':'a'*40,'tree':[]})
    return caught.value,calls,delays


def emitted(capsys):
    text=capsys.readouterr().err
    assert SECRET not in text and 'Bearer ' not in text and 'https://' not in text
    return [json.loads(line.split('] ',1)[1]) for line in text.splitlines()]


@pytest.mark.parametrize('status,body,headers,code',[
    (422,{'message':'Validation Failed','errors':[{'resource':'Tree','field':'sha','code':'invalid'}]}, {},'validation_failed'),
    (422,{'message':'unrecognized provider reason'}, {},'unclassified'),
    (422,{'message':SECONDARY}, {},'secondary_rate_limit'),
    (403,{'message':SECONDARY},{'Retry-After':'61','X-RateLimit-Remaining':'999'},'secondary_rate_limit'),
    (429,{'message':'limit'},{'X-RateLimit-Remaining':'0','X-RateLimit-Reset':'1234567890'},'primary_rate_limit'),
])
def test_classification_retains_only_closed_facts(monkeypatch,capsys,status,body,headers,code):
    error,calls,delays=invoke(monkeypatch,response(status,body,headers))
    record,=emitted(capsys)
    assert record['error_code']==code and record['http_status']==status
    assert all(type(v) is int for v in record['rate_limit'].values())
    assert error.status==status and len(calls)==1 and not delays


def test_credentials_and_signed_urls_are_never_emitted(monkeypatch,capsys):
    body={'message':'Authorization: Bearer '+SECRET,'documentation_url':'https://example.invalid/?sig='+SECRET,
          'errors':[{'resource':'Tree','field':'sha','code':'invalid','message':SECRET,'value':SECRET}]}
    error,_,_=invoke(monkeypatch,response(422,body,{'Authorization':'Bearer '+SECRET,'Set-Cookie':SECRET,'Retry-After':'120'}))
    record,=emitted(capsys)
    assert record['errors']==[{'resource':'Tree','field':'sha','code':'invalid'}]
    assert record['rate_limit']=={'retry_after_seconds':120}
    assert SECRET not in str(error) and not hasattr(error,'response')


@pytest.mark.parametrize('body,headers',[
    (b'not JSON',{}),
    ({'message':'Validation Failed','authorization':SECRET},{}),
    ({'message':'Validation Failed','errors':'unexpected'},{}),
    ({'message':'Validation Failed','errors':[{'code':'invalid','authorization':SECRET}]},{}),
    ({'message':'Validation Failed','errors':[{'code':SECRET}]},{}),
    ({'message':'Validation Failed','errors':[{'code':'invalid','field':SECRET}]},{}),
    ({'message':'Validation Failed'},{'Retry-After':SECRET}),
    (b'x'*16385,{}),
])
def test_malformed_or_unexpected_response_fails_closed(monkeypatch,capsys,body,headers):
    invoke(monkeypatch,response(422,body,headers))
    record,=emitted(capsys)
    assert set(record)=={'http_status','error_code','correlation_id'}
    assert record['error_code']=='malformed_response'


def test_diagnostic_survives_unchanged_safe_exception_fallback(monkeypatch,capsys):
    original=builtins.__import__
    def missing(name,*a,**k):
        if name=='create_people_posters.people_failures':raise ImportError('offline missing optional module')
        return original(name,*a,**k)
    monkeypatch.setattr(builtins,'__import__',missing)
    error,_,_=invoke(monkeypatch,response(422,{'message':'Validation Failed','errors':[{'code':'invalid','field':'base_tree'}]}))
    assert diagnostics.safe_exception(error)==diagnostics.WITHHELD
    record,=emitted(capsys)
    assert record['errors'][0]['field']=='base_tree'
    assert 'correlation_id='+record['correlation_id']+']' in diagnostics.WITHHELD


@pytest.mark.parametrize('method,path',[('GET',TARGET),('POST',TARGET.replace('/trees','/blobs'))])
def test_other_operations_are_unchanged(monkeypatch,capsys,method,path):
    invoke(monkeypatch,response(422,{'message':'Validation Failed'}),method=method,path=path)
    assert capsys.readouterr().err==''


def test_retry_counts_and_backoff_are_unchanged(monkeypatch,capsys):
    error,calls,delays=invoke(monkeypatch,response(403,{'message':SECONDARY},{'Retry-After':'61'}),attempts=4)
    assert len(calls)==4 and delays==[61,61,61] and error.status==403
    assert len(emitted(capsys))==4


def test_original_legacy_transport_and_chunk_logic_preserved():
    import subprocess
    def module(name, old=False):
        raw=subprocess.check_output(['git','show','a3c379b0681e583ec4387d83b040b504aa6bc33b:'+name],cwd=ROOT) if old else (ROOT/name).read_bytes()
        return ast.parse(raw)
    def method(tree, cls, name):
        return next(n for c in tree.body if isinstance(c,ast.ClassDef) and c.name==cls for n in c.body if isinstance(n,ast.FunctionDef) and n.name==name)
    current=method(module('create_people_posters/people_github.py'),'GitHubClient','request')
    current.body=[n for n in current.body if not (isinstance(n,ast.If) and ast.unparse(n.test)=='self.reliable')]
    loop=next(n for n in current.body if isinstance(n,ast.For))
    loop.body=[n for n in loop.body if not (isinstance(n,ast.If) and any(isinstance(c,ast.Name) and c.id=='_report_tree_failure' for c in ast.walk(n)))]
    assert ast.dump(current)==ast.dump(method(module('create_people_posters/people_github.py',True),'GitHubClient','request'))
    assert ast.dump(method(module('create_people_posters/publish_people_github.py'),'Publisher','publish_chunk'))==ast.dump(method(module('create_people_posters/publish_people_github.py',True),'Publisher','publish_chunk'))
