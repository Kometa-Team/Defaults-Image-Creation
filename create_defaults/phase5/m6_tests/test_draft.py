"""The concrete local protocol cannot authorize production or substitute drafts."""
import json
from pathlib import Path
import pytest
from create_defaults.bulk.common import BulkError
from create_defaults.bulk.lifecycle.draft_transport import run_offline,OfflineProtocol
from create_defaults.bulk.lifecycle.catalog_preparation import git
from create_defaults.bulk.library_sources import sealed,save
from create_defaults.phase5.m6_tests.helpers import connected


@pytest.mark.parametrize('attack',['closed','merged','wrong-head','wrong-base','not-draft','receipt','replayed-auth','foreign-target'])
def test_M6_owned_draft_rejects_changed_context(native,attack):
    protocol,c=connected(native);result=run_offline(protocol)
    assert result['draft_verified']
    path=c.root/'offline-pr.json';value=json.loads(path.read_bytes())
    if attack in {'closed','merged'}:value['pr']['state']=attack.upper()
    elif attack=='wrong-head':value['pr']['headRefOid']='a'*40
    elif attack=='wrong-base':value['pr']['baseRefName']='main'
    elif attack=='not-draft':value['pr']['isDraft']=False
    elif attack=='receipt':
        receipt=json.loads((c.root/'draft-pr.json').read_bytes());receipt['authorization_sha256']='a'*64
        save(c.root/'draft-pr.json',sealed({k:v for k,v in receipt.items() if k!='sha256'}))
    elif attack=='replayed-auth':
        auth=c.binding.to_dict()['authorization'];auth['approval_receipt']['decision_text']='Different decision'
        save(c.root/'draft-staging-authorization.json',auth)
    else:
        with pytest.raises(BulkError,match='foreign_target'):
            OfflineProtocol.verify(protocol,c.root,c.binding.to_dict()['plan'],c.binding.to_dict()['authorization'],test_remote=c.target.root)
        return
    if attack in {'closed','merged','wrong-head','wrong-base','not-draft'}:
        save(path,sealed({k:v for k,v in value.items() if k!='sha256'}))
    head=git(c.root/'remote.git','rev-parse','refs/heads/'+c.binding.to_dict()['authorization']['branch'])
    with pytest.raises(BulkError):run_offline(protocol)
    assert git(c.root/'remote.git','rev-parse','refs/heads/'+c.binding.to_dict()['authorization']['branch'])==head
