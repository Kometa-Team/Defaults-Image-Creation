"""Real Git recovery tests for the authorized draft-branch transport adapter."""
from copy import deepcopy
import hashlib
from pathlib import Path
import subprocess

import pytest

from create_defaults.bulk.common import BulkError, fingerprint, sha256
from create_defaults.bulk.library_sources import blob_id, sealed
from create_defaults.bulk.library_publication import batch_plan
from create_defaults.bulk.library_stage import gate, git, run, remote_head, RemoteBytes


def fixture(tmp_path):
    base=tmp_path/'base';base.mkdir()
    subprocess.run(['git','init','-b','master',str(base)],check=True,capture_output=True)
    git(base,'config','user.name','Local fixture');git(base,'config','user.email','test@invalid.local')
    (base/'genre').mkdir()
    (base/'untouched.txt').write_bytes(b'unchanged')
    members=[]
    for n in range(2):
        path=base/f'genre/{n}.jpg';path.write_bytes(b'old'+bytes([n]))
        source=tmp_path/f'new-{n}.jpg';source.write_bytes(b'new-output'+bytes([n]))
        members.append(dict(destination=f'genre/{n}.jpg',source=str(source),size=source.stat().st_size,
            sha256=sha256(source),previous_sha256=sha256(path),git_blob=blob_id(source),previous_git_blob=blob_id(path),
            context_sha256='context'+str(n),difference_class='renderer_equivalent'))
    git(base,'add','.');git(base,'commit','-m','fixture baseline')
    head=git(base,'rev-parse','HEAD').decode().strip();tree=git(base,'rev-parse','HEAD^{tree}').decode().strip()
    baseline=dict(repository='Kometa-Team/Default-Images',branch='master',head=head,tree=tree)
    manifest=sealed(dict(kind='approved-library-publication-manifest',baseline=baseline,members=members))
    plan=batch_plan(manifest,max_files=1,max_bytes=1024**2)
    bindings=[dict(destination=m['destination'],candidate_sha256=m['sha256'],published_sha256=m['previous_sha256'],context_sha256=m['context_sha256']) for m in members]
    receipt=sealed(dict(decision='approved',reviewer='bullmoose20',policy_approved=True,scope='renderer_equivalent',
        candidate_manifest_sha256='synthetic-candidate',policy_sha256='policy',baseline=baseline,
        members=bindings,membership_sha256=fingerprint(bindings)))
    auth=sealed(dict(kind='approved-draft-staging-authorization',plan_sha256=plan['sha256'],baseline=baseline,
        publication_manifest_sha256=plan['publication_manifest_sha256'],remote_writes_authorized=True,draft_only=True,
        merge_authorized=False,repository='Kometa-Team/Default-Images',branch='migration/english-python-group-a-test',
        approval_receipt=receipt,candidate_manifest_sha256='synthetic-candidate',policy_sha256='policy',test_only=True))
    remote=tmp_path/'remote.git'
    subprocess.run(['git','clone','--bare',str(base),str(remote)],check=True,capture_output=True)
    return plan,auth,remote


def test_real_git_interruptions_reconcile_and_resume_without_extra_commits(tmp_path):
    plan,auth,remote=fixture(tmp_path);root=tmp_path/'transport'
    with pytest.raises(BulkError,match='After commit'):
        run(plan,auth,root,test_remote=remote,fail_at='after_commit')
    assert remote_head(root/'work',auth['branch']) is None
    with pytest.raises(BulkError,match='After push'):
        run(plan,auth,root,test_remote=remote,fail_at='after_push')
    value=run(plan,auth,root,test_remote=remote)
    assert value['complete'] and value['master_unchanged']
    head=value['head'];again=run(plan,auth,root,test_remote=remote)
    assert again['head']==head
    assert len(git(root/'work','rev-list',plan['baseline']['head']+'..HEAD').splitlines())==2
    assert all(b['pack_bytes']<=plan['max_pack_bytes'] for b in value['batches'])
    assert (root/'work/untouched.txt').exists() is False
    (root/'work/unrelated.txt').write_text('do not discard')
    with pytest.raises(BulkError,match='Unrelated'):
        run(plan,auth,root,test_remote=remote)


def test_synthetic_authorization_cannot_use_network_remote(tmp_path):
    plan,auth,_=fixture(tmp_path)
    with pytest.raises(BulkError,match='Synthetic authorization'):
        run(plan,auth,tmp_path/'transport')


def test_prepare_prefix_locally_before_any_remote_write(tmp_path):
    plan,auth,remote=fixture(tmp_path);root=tmp_path/'prepared'
    prepared=run(plan,auth,root,test_remote=remote,prepare_only=True,stop_after=1)
    assert not prepared['complete'] and prepared['network_artwork_push_batches']==0
    assert remote_head(root/'work',auth['branch']) is None
    assert len(prepared['batches'])==1
    completed=run(plan,auth,root,test_remote=remote)
    assert completed['complete'] and completed['master_unchanged']


@pytest.mark.parametrize('field,value',[('decision','pending'),('policy_approved',False),('reviewer',None),('candidate_manifest_sha256','different')])
def test_unapproved_or_drifted_receipt_never_stages(tmp_path,field,value):
    plan,auth,_=fixture(tmp_path)
    receipt=deepcopy(auth['approval_receipt']);receipt.pop('sha256');receipt[field]=value
    auth=deepcopy(auth);auth.pop('sha256');auth['approval_receipt']=sealed(receipt)
    with pytest.raises(BulkError,match='approved candidate'):
        gate(plan,sealed(auth))


def test_candidate_change_and_measured_pack_cap_stop_before_push(tmp_path):
    plan,auth,remote=fixture(tmp_path)
    changed=Path(plan['batches'][0]['members'][0]['source']);changed.write_bytes(b'corrupt')
    with pytest.raises(BulkError,match='candidate bytes'):
        run(plan,auth,tmp_path/'drift',test_remote=remote)


def test_pack_cap_is_enforced_before_remote_branch_creation(tmp_path):
    plan,auth,remote=fixture(tmp_path)
    plan.pop('sha256');plan['max_pack_bytes']=1;plan=sealed(plan)
    auth.pop('sha256');auth['plan_sha256']=plan['sha256'];auth=sealed(auth)
    root=tmp_path/'limited'
    with pytest.raises(BulkError,match='Measured incremental pack'):
        run(plan,auth,root,test_remote=remote)
    assert remote_head(root/'work',auth['branch']) is None


@pytest.mark.parametrize('wrong',[False,True])
def test_remote_verification_hashes_actual_response_bytes(tmp_path,wrong):
    plan,_,_=fixture(tmp_path);member=plan['batches'][0]['members'][0]
    payload=Path(member['source']).read_bytes()
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def raise_for_status(self):pass
        def iter_content(self,size):yield bytes([payload[0]^1])+payload[1:] if wrong else payload
    class Session:
        def get(self,*args,**kwargs):return Response()
    verifier=RemoteBytes(tmp_path/'receipts',plan);verifier.local.session=Session()
    if wrong:
        with pytest.raises(BulkError,match='Actual downloaded remote bytes'):
            verifier.one('a'*40,member)
        assert not list((tmp_path/'receipts').glob('*.json'))
    else:
        receipt=verifier.one('a'*40,member)
        assert receipt['actual_sha256']==member['sha256']
        assert receipt['actual_git_blob']==member['git_blob']
        assert receipt['provenance']=='actual_pinned_raw_remote_response'


def group_b_authorization(auth):
    auth=deepcopy(auth);auth.pop('sha256')
    policy={'rules':{'legacy':'measured only'},'preserved_visual_review_receipt_sha256':'preserved-exact-review'}
    receipt=auth['approval_receipt'];receipt.pop('sha256')
    receipt.update(population='B',candidate_manifest_sha256='b'*64,policy_sha256=fingerprint(policy),
        warning_policy_sha256=fingerprint(policy),preserved_visual_review_receipt_sha256='preserved-exact-review')
    auth.update(population='B',branch='migration/english-python-group-b-bbbbbbbb',
        candidate_manifest_sha256='b'*64,policy_sha256=fingerprint(policy),approved_warning_policy=policy,
        approval_receipt=sealed(receipt))
    return sealed(auth)


def test_group_b_real_git_resume_preserves_master_and_exact_membership(tmp_path):
    plan,auth,remote=fixture(tmp_path);auth=group_b_authorization(auth)
    root=tmp_path/'group-b-transport'
    with pytest.raises(BulkError,match='After push'):
        run(plan,auth,root,test_remote=remote,fail_at='after_push')
    result=run(plan,auth,root,test_remote=remote)
    assert result['complete'] and result['master_unchanged']
    assert sum(b['remote_hash_verified'] for b in result['batches'])==2
    assert run(plan,auth,root,test_remote=remote)['head']==result['head']


@pytest.mark.parametrize('defect',['missing-policy','different-policy','missing-review','different-review',
    'wrong-branch-suffix','group-a-branch','missing-population'])
def test_group_b_cannot_escape_approved_policy_review_or_branch(tmp_path,defect):
    plan,auth,_=fixture(tmp_path);auth=group_b_authorization(auth);auth.pop('sha256')
    if defect=='missing-policy':auth.pop('approved_warning_policy')
    elif defect=='different-policy':auth['approved_warning_policy']['rules']['legacy']='waive everything'
    elif defect in {'missing-review','different-review'}:
        receipt=auth['approval_receipt'];receipt.pop('sha256')
        if defect=='missing-review':receipt.pop('preserved_visual_review_receipt_sha256')
        else:receipt['preserved_visual_review_receipt_sha256']='other-review'
        auth['approval_receipt']=sealed(receipt)
    elif defect=='wrong-branch-suffix':auth['branch']='migration/english-python-group-b-cccccccc'
    elif defect=='group-a-branch':auth['branch']='migration/english-python-group-a-bbbbbbbb'
    else:auth.pop('population')
    with pytest.raises(BulkError,match='Group B'):
        gate(plan,sealed(auth))


def individual_authorization(plan,auth):
    members=deepcopy([m for b in plan['batches'] for m in b['members']])
    for m,kind in zip(members,['font_changed','unexpected_difference']):m['difference_class']=kind
    manifest=sealed(dict(kind='approved-library-publication-manifest',baseline=plan['baseline'],members=members))
    plan=batch_plan(manifest,max_files=1,max_bytes=1024**2)
    auth=deepcopy(auth);auth.pop('sha256');receipt=auth['approval_receipt'];receipt.pop('sha256')
    originals=[dict(m,context_sha256='previous-'+m['context_sha256']) for m in receipt['members']]
    review=sealed(dict(reviewer='bullmoose20',visual_review_accepted=True,members=originals,membership_sha256=fingerprint(originals)))
    bridge=sealed(dict(members=[dict(m,previous_context_sha256='previous-'+m['context_sha256'],
        original_review_receipt_sha256=review['sha256'],material_review_context_unchanged=True,
        difference_class=member['difference_class']) for m,member in zip(receipt['members'],members)]))
    policy={'mode':'exact-individual-visual-acceptance','original_review_receipts':[review['sha256']]}
    receipt.update(population='individual-exceptions',scope='individual',candidate_manifest_sha256='c'*64,
        policy_sha256=fingerprint(policy),preserved_individual_reviews_sha256=bridge['sha256'])
    auth.update(population='individual-exceptions',branch='migration/english-python-exceptions-cccccccc',
        candidate_manifest_sha256='c'*64,policy_sha256=fingerprint(policy),approval_receipt=sealed(receipt),
        approved_individual_policy=policy,preserved_individual_reviews=bridge,original_individual_reviews=[review],
        plan_sha256=plan['sha256'],publication_manifest_sha256=manifest['sha256'])
    return plan,sealed(auth)


def test_individually_reviewed_exceptions_resume_without_reclassifying_as_equivalent(tmp_path):
    plan,auth,remote=fixture(tmp_path);plan,auth=individual_authorization(plan,auth)
    root=tmp_path/'individual-transport'
    with pytest.raises(BulkError,match='After push'):
        run(plan,auth,root,test_remote=remote,fail_at='after_push')
    value=run(plan,auth,root,test_remote=remote)
    assert value['complete'] and value['master_unchanged']
    assert {m['difference_class'] for m in gate(plan,auth)}=={'font_changed','unexpected_difference'}


@pytest.mark.parametrize('defect',['candidate','old-context','changed-material','missing-individual',
    'wrong-branch','policy','branch-suffix'])
def test_individual_acceptance_cannot_be_reused_for_other_bytes_context_or_scope(tmp_path,defect):
    plan,auth,_=fixture(tmp_path);plan,auth=individual_authorization(plan,auth);auth.pop('sha256')
    if defect in {'candidate','old-context','changed-material'}:
        bridge=auth['preserved_individual_reviews'];bridge.pop('sha256')
        field={'candidate':'candidate_sha256','old-context':'previous_context_sha256','changed-material':'material_review_context_unchanged'}[defect]
        bridge['members'][0][field]=False if defect=='changed-material' else 'unreviewed-value'
        auth['preserved_individual_reviews']=sealed(bridge)
        receipt=auth['approval_receipt'];receipt.pop('sha256')
        receipt['preserved_individual_reviews_sha256']=auth['preserved_individual_reviews']['sha256'];auth['approval_receipt']=sealed(receipt)
    elif defect=='missing-individual':
        review=auth['original_individual_reviews'][0];review.pop('sha256');review['members'].pop()
        review['membership_sha256']=fingerprint(review['members']);auth['original_individual_reviews']=[sealed(review)]
    elif defect=='wrong-branch':auth['branch']='migration/english-python-group-a-cccccccc'
    elif defect=='policy':auth['approved_individual_policy']['mode']='blanket-warning-waiver'
    else:auth['branch']='migration/english-python-exceptions-dddddddd'
    with pytest.raises(BulkError):gate(plan,sealed(auth))
