"""Fresh source/review checks and complete-tree preservation on every resume."""
import json,sqlite3
from pathlib import Path
import pytest
from create_defaults.bulk.common import BulkError
from create_defaults.bulk.lifecycle.draft_transport import run_offline
from create_defaults.bulk.lifecycle.catalog_preparation import git
from create_defaults.phase5.m6_tests.helpers import connected


@pytest.mark.parametrize('attack',['missing','revoked','role','expired'])
def test_M6_fresh_authority_is_required_before_transport(native,attack):
    protocol,c=connected(native);authority=c.selection.authority
    if attack=='missing':authority.grants.clear()
    elif attack=='revoked':authority.revoked.update(authority.grants)
    elif attack=='role':authority.roles['maintainer']=frozenset()
    else:authority.as_of=100
    with pytest.raises(BulkError):run_offline(protocol)
    assert not (c.root/'transport').exists()


@pytest.mark.parametrize('attack',['source','artwork','definition','review','destination','foreign-ref','unrelated-tree','rollback','draft-rollback'])
def test_M6_fresh_context_and_remote_tampering_blocks_resume(native,attack):
    from create_defaults.bulk.lifecycle.package_e import SidecarStore
    protocol,c=connected(native);run_offline(protocol)
    branch=c.binding.to_dict()['authorization']['branch'];remote=c.root/'remote.git'
    corrupted_review=None
    if attack=='source':git(c.patch.source.root,'commit','--allow-empty','-m','Foreign source epoch')
    elif attack=='artwork':Path(c.preparation.to_dict()['members'][0]['source']).write_bytes(b'changed')
    elif attack=='definition':
        path=c.patch.source.root/'create_defaults/bulk/catalog/genre.yml';path.write_bytes(path.read_bytes()+b'\n#changed\n')
    elif attack=='review':
        store=SidecarStore(c.selection.registry.operations.root)
        with store.transaction() as db:
            before=[tuple(r) for r in db.execute('SELECT * FROM p4m4_reviews ORDER BY id,revision')]
            namespace=[tuple(r) for r in db.execute("SELECT name,sql FROM sqlite_master WHERE name LIKE 'p4m4_%' ORDER BY name")]
        with pytest.raises(sqlite3.IntegrityError,match='^immutable complete review$'):
            with store.transaction() as db:db.execute('UPDATE p4m4_reviews SET sha256=?',('a'*64,))
        with store.transaction() as db:
            assert [tuple(r) for r in db.execute('SELECT * FROM p4m4_reviews ORDER BY id,revision')]==before
            assert [tuple(r) for r in db.execute("SELECT name,sql FROM sqlite_master WHERE name LIKE 'p4m4_%' ORDER BY name")]==namespace
        # Corrupt only the disposable fixture's review object, retaining all
        # SQLite triggers/index receipts and restoring bytes even on failure.
        path=store.root/'objects'/(c.preparation.to_dict()['review_sha256']+'.json')
        corrupted_review=(path,path.read_bytes())
    elif attack=='destination':git(remote,'update-ref','refs/heads/master',git(remote,'rev-parse','refs/heads/'+branch).decode().strip())
    elif attack=='foreign-ref':git(remote,'update-ref','refs/heads/unapproved',c.preparation.to_dict()['destination']['head'])
    elif attack=='rollback':git(remote,'update-ref','refs/heads/'+branch,c.preparation.to_dict()['destination']['head'])
    elif attack=='draft-rollback':
        path=c.root/'offline-pr.json';path.rename(c.root/'retained-offline-pr.json')
    else:
        work=c.root/'transport/work';(work/'unexpected.txt').write_bytes(b'unrelated')
        git(work,'add','unexpected.txt');git(work,'commit','-m','Foreign writer');git(work,'push','origin','HEAD:refs/heads/'+branch)
    try:
        if corrupted_review is not None:corrupted_review[0].write_bytes(b'{}')
        refs=git(remote,'show-ref')
        with pytest.raises((BulkError,ValueError)):run_offline(protocol)
        assert git(remote,'show-ref')==refs
    finally:
        if corrupted_review is not None:corrupted_review[0].write_bytes(corrupted_review[1])
