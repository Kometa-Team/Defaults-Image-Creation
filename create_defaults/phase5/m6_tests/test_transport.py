"""Actual native JPEGs, original operator stage/draft and owned local bare Git."""
from create_defaults.bulk.lifecycle.draft_transport import run_offline,OfflineProtocol
from create_defaults.bulk.lifecycle.catalog_preparation import git
from create_defaults.bulk.lifecycle.draft_progress import DraftProgress
from create_defaults.phase5.m6_tests.helpers import connected,export_native


def test_M6_complete_native_operator_transport(native,monkeypatch):
    protocol,c=connected(native)
    result=run_offline(protocol)
    assert result['complete'] and result['draft_verified'] and result['network_writes']==0
    assert not any(result[k] for k in ('publication_authorized','operation_complete','remote_writes_authorized','ready','active'))
    progress=DraftProgress(c.selection.registry.operations.root,c.binding).read()
    assert progress['state']=='OFFLINE_DRAFT_VERIFIED'
    assert git(c.root/'remote.git','rev-parse','refs/heads/master').decode().strip()==c.preparation.to_dict()['destination']['head']
    # Original streaming RemoteBytes, with responses read from actual Git blobs.
    # The network is forbidden by conftest; no arbitrary success provider.
    from urllib.parse import unquote
    import requests
    from create_defaults.bulk.library_stage import RemoteBytes
    class Response:
        def __init__(self,raw):self.raw=raw
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def raise_for_status(self):pass
        def iter_content(self,size):
            for offset in range(0,len(self.raw),size):yield self.raw[offset:offset+size]
    def get(session,url,**kwargs):
        prefix='https://raw.githubusercontent.com/Kometa-Team/Default-Images/'+result['head']+'/'
        assert url.startswith(prefix) and kwargs==dict(stream=True,timeout=(15,90),allow_redirects=False)
        return Response(git(c.root/'remote.git','show',result['head']+':'+unquote(url[len(prefix):])))
    with monkeypatch.context() as context:
        context.setattr(requests.Session,'get',get)
        RemoteBytes(c.root/'actual-native-byte-responses',c.binding.to_dict()['plan'])(result['head'],c.preparation.to_dict()['members'])
    export_native(native,protocol,result,name='single')


def test_M6_multi_member_partial_batches_resume_without_recreating(multi_native):
    protocol,c=connected(multi_native,max_files=1)
    assert len(c.preparation.to_dict()['required_members'])==2
    first=run_offline(protocol,stop_after=1)
    assert first['verified_batches']==1 and not first['complete'] and not first['draft_verified']
    assert not (c.root/'draft-pr.json').exists()
    result=run_offline(protocol)
    assert result['complete'] and result['draft_verified'] and result['verified_batches']==2
    assert result['commits'][0]==first['head']
    again=run_offline(protocol)
    assert again['head']==result['head'] and again['commits']==result['commits']
    assert OfflineProtocol.inspect(protocol)['draft_verified']
    export_native(multi_native,protocol,result,name='multi')


def test_M6_retained_current_mapping_history_is_preserved(current_native):
    protocol,c=connected(current_native)
    assert c.preparation.to_dict()['members'][0]['destination']=='genre/fixture.jpg'
    result=run_offline(protocol)
    assert result['complete'] and result['draft_verified']
    export_native(current_native,protocol,result,name='current')
