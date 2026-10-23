"""Optional M4 archival is CAS data, never review/activation authority."""

import json
import sqlite3

import pytest

from create_defaults.bulk.common import BulkError,Conflict,canonical,fingerprint
from create_defaults.bulk.contracts.evidence_consumption import consume,RequestContext
from create_defaults.bulk.contracts.evidence_consumption.storage import Archive
from create_defaults.phase3.tests.consumption_samples import example


@pytest.fixture(scope='module')
def chain(tmp_path_factory):return example(tmp_path_factory.mktemp('m4-archive-fixture'))


def append(archive,chain,*,head=None,before_commit=None):
    report=consume(**chain)
    archive.append(report,chain['request_context'],expected_head_sha256=head,
        expected_context_sha256=chain['request_context'].sha256,before_commit=before_commit)
    return report


def next_revision(chain):
    value=chain['request_context'].to_dict()
    value.update(revision=value['revision']+1,previous_sha256=chain['request_context'].sha256)
    ctx=RequestContext.from_dict(value)
    return chain|dict(request_context=ctx,expected_request_context_sha256=ctx.sha256)


def test_append_exact_chain_reopen_and_no_approval_activation_publication_events(chain,tmp_path):
    root=tmp_path/'isolated';a=Archive(root)
    first=append(a,chain);second=append(a,next_revision(chain),head=first.sha256)
    assert [r.sha256 for r in Archive(root).history(chain['request_context'].to_dict()['id'])]==[first.sha256,second.sha256]
    with a.store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM contract_records').fetchone()[0]==0
        names={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert 'contract_activation_revisions' not in names
        events=[r[0] for r in db.execute('SELECT kind FROM events')]
    assert events==['phase3_evidence_archived','phase3_evidence_archived']


@pytest.mark.parametrize('failure',['transaction','first-blob','second-blob'])
def test_partial_or_interrupted_write_never_advances_head(chain,tmp_path,monkeypatch,failure):
    a=Archive(tmp_path/'isolated');first=append(a,chain)
    current=next_revision(chain)
    def interrupted():raise KeyboardInterrupt('synthetic interrupted archival')
    original=a.contracts._write_blob
    count=0
    def write(document):
        nonlocal count
        count+=1
        if count==({'first-blob':1,'second-blob':2}.get(failure,999)):
            interrupted()
        original(document)
    monkeypatch.setattr(a.contracts,'_write_blob',write)
    with pytest.raises(KeyboardInterrupt):append(a,current,head=first.sha256,before_commit=interrupted if failure=='transaction' else None)
    assert [r.sha256 for r in a.history(current['request_context'].to_dict()['id'])]==[first.sha256]
    monkeypatch.setattr(a.contracts,'_write_blob',original)
    second=append(a,current,head=first.sha256)
    assert len(a.history(current['request_context'].to_dict()['id']))==2
    assert first.sha256!=second.sha256


@pytest.mark.parametrize('error',['wrong-head','old-revision','foreign-context','wrong-context-pin'])
def test_replay_and_mismatched_expected_heads_fail(chain,tmp_path,error):
    a=Archive(tmp_path/'isolated');first=append(a,chain)
    current=next_revision(chain);report=consume(**current);ctx=current['request_context']
    head=first.sha256;pin=ctx.sha256
    if error=='wrong-head':head='f'*64
    elif error=='old-revision':ctx=chain['request_context'];report=first;pin=ctx.sha256
    elif error=='foreign-context':ctx=chain['request_context'];pin=ctx.sha256
    else:pin='f'*64
    with pytest.raises((BulkError,Conflict)):a.append(report,ctx,expected_head_sha256=head,expected_context_sha256=pin)
    assert len(a.history(ctx.to_dict()['id']))==1


@pytest.mark.parametrize('target',['context','report'])
@pytest.mark.parametrize('corruption',['partial','substitute','noncanonical','missing'])
def test_missing_corrupted_or_substituted_sidecars_fail_closed(chain,tmp_path,target,corruption):
    a=Archive(tmp_path/'isolated');report=append(a,chain)
    pin=chain['request_context'].sha256 if target=='context' else report.sha256
    path=a.contracts._blob_path(pin)
    if corruption=='missing':path.unlink()
    elif corruption=='partial':path.write_bytes(path.read_bytes()[:-1])
    elif corruption=='noncanonical':path.write_bytes(path.read_bytes()+b'\n')
    else:path.write_bytes(canonical(dict(unrelated='substituted')))
    with pytest.raises(BulkError):a.history(chain['request_context'].to_dict()['id'])


def test_sidecar_namespace_is_versioned_and_immutable(chain,tmp_path):
    root=tmp_path/'isolated';a=Archive(root);append(a,chain)
    with a.store.transaction() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM phase3_consumption')
    with a.store.transaction() as db:db.execute('UPDATE phase3_consumption_schema SET version=99')
    with pytest.raises(BulkError):Archive(root)


@pytest.mark.parametrize('mutation',['foreign-subject','wrong-context','missing-payload','substituted-payload','wrong-revision'])
def test_referenced_reviews_and_receipts_are_exact_scoped_data(chain,mutation):
    subject=chain['inputs'][0].report.to_dict()['subject']
    payload=canonical(dict(id='fixture.receipt',revision=1,kind='synthetic-receipt',evidence='not an approval'))
    ref=dict(role='receipt',id='fixture.receipt',revision=1,sha256=fingerprint(dict(id='fixture.receipt',revision=1,kind='synthetic-receipt',evidence='not an approval')),
        subject_sha256=chain['inputs'][0].request.expand('fr')[0].sha256,review_context_sha256=subject['review_context_sha256'])
    if mutation=='foreign-subject':ref['subject_sha256']='f'*64
    elif mutation=='wrong-context':ref['review_context_sha256']='f'*64
    elif mutation=='wrong-revision':ref['revision']=2
    value=chain['request_context'].to_dict();value['references']=[ref]
    if mutation=='foreign-subject':
        with pytest.raises(BulkError):RequestContext.from_dict(value)
        return
    context=RequestContext.from_dict(value)
    refs=() if mutation=='missing-payload' else (canonical(dict(id='other',revision=1)),) if mutation=='substituted-payload' else (payload,)
    with pytest.raises(BulkError):consume(**(chain|dict(request_context=context,expected_request_context_sha256=context.sha256,references=refs)))


def test_valid_pinned_receipt_remains_unauthenticated_and_cannot_authorize(chain):
    subject=chain['inputs'][0].request.expand('fr')[0]
    payload=canonical(dict(id='fixture.review',revision=1,kind='synthetic-review',decision='approved'))
    ref=dict(role='review',id='fixture.review',revision=1,sha256=fingerprint(dict(id='fixture.review',revision=1,kind='synthetic-review',decision='approved')),
        subject_sha256=subject.sha256,review_context_sha256=subject.to_dict()['review_context_sha256'])
    value=chain['request_context'].to_dict();value['references']=[ref];ctx=RequestContext.from_dict(value)
    result=consume(**(chain|dict(request_context=ctx,expected_request_context_sha256=ctx.sha256,references=(payload,)))).to_dict()
    assert result['references']==[ref]
    assert 'referenced_decisions_not_authenticated' in result['blockers']
    assert not result['ready'] and not result['publication_authorized']


@pytest.mark.parametrize('role',['receipt','review'])
@pytest.mark.parametrize('foreign',[False,True])
def test_existing_package_e_hash_revisions_are_preserved_without_fabricated_records(chain,role,foreign):
    subject=chain['inputs'][0].request.expand('fr')[0]
    revision=fingerprint('existing-native-revision')
    if role=='receipt':
        value=dict(job_id='existing.worker-state',logical_id=subject.to_dict()['id'],job_fingerprint=revision,sha256=fingerprint('synthetic-artifact-not-generated'))
        value['receipt_sha256']=fingerprint(value)
        identity=value['job_id']
    else:
        value=dict(variant=dict(id=subject.to_dict()['id'],validation_fingerprint=revision),registry_sha256=fingerprint('existing-review-registry'))
        identity=value['variant']['id']
    if foreign:
        if role=='receipt':
            value['logical_id']='foreign.poster'
            value['receipt_sha256']=fingerprint({k:v for k,v in value.items() if k!='receipt_sha256'})
        else:
            value['variant']['id']='foreign.poster'
            identity='foreign.poster'
    ref=dict(role=role,id=identity,revision=revision,sha256=fingerprint(value),subject_sha256=subject.sha256,review_context_sha256=subject.to_dict()['review_context_sha256'])
    ctx=chain['request_context'].to_dict();ctx['references']=[ref];ctx=RequestContext.from_dict(ctx)
    current=chain|dict(request_context=ctx,expected_request_context_sha256=ctx.sha256,references=(canonical(value),))
    if foreign:
        with pytest.raises(BulkError):consume(**current)
        return
    result=consume(**current).to_dict()
    assert result['references']==[ref] and not result['ready'] and not result['publication_authorized']


@pytest.mark.parametrize('change',['none','category','variant','identities','context','untyped'])
def test_original_m1_exception_records_are_parsed_and_scoped_without_granting_approval(chain,change):
    from create_defaults.bulk.contracts.models import ExceptionRequest
    subject=chain['inputs'][0].request.expand('fr')[0]
    s=subject.to_dict()
    provenance=chain['inputs'][0].request.package.contract.to_dict()['provenance']
    provenance.update(role='submitter',actor='fixture.submitter')
    context=dict(package=s['contract'],variant=s['variant'],identities=[s['id']],source=dict(path='logos/Fixture.png',sha256=fingerprint('fixture-source')),
        material_context_sha256=s['review_context_sha256'],transformations=[dict(id='whitewash',sha256=fingerprint('unchanged-whitewash'))])
    if change=='category':context['package']=context['package']|dict(category='Studio')
    elif change=='variant':context['variant']='foreign'
    elif change=='identities':context['identities']=['foreign.poster']
    elif change=='context':context['material_context_sha256']='f'*64
    record=ExceptionRequest.from_dict(dict(schema_version=1,kind='logo-exception-request',id='fixture.exception',revision=1,provenance=provenance,
        context=context,justification='Synthetic M4 scope test',requested_treatment='SOURCE_PRESERVING',intentional_background=False))
    payload=record.encoded if change!='untyped' else canonical(dict(id='fixture.exception',revision=1,decision='approved'))
    value=chain['request_context'].to_dict()
    value['references']=[dict(role='exception',id='fixture.exception',revision=1,sha256=fingerprint(json.loads(payload)),
        subject_sha256=subject.sha256,review_context_sha256=s['review_context_sha256'])]
    ctx=RequestContext.from_dict(value)
    current=chain|dict(request_context=ctx,expected_request_context_sha256=ctx.sha256,references=(payload,))
    if change=='none':
        result=consume(**current).to_dict()
        assert 'referenced_decisions_not_authenticated' in result['blockers'] and not result['ready']
    else:
        with pytest.raises(BulkError):consume(**current)
