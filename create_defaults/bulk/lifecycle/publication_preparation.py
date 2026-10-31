"""Complete native lifecycle membership -> existing Package E offline transport."""
from dataclasses import dataclass
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import tempfile
import os

from ..common import atomic_bytes, canonical, confined, fingerprint, path_key, relative_path
from ..library_publication import batch_plan, validate_paths
from ..library_sources import blob_id, sealed
from .catalog_preparation import OwnedCatalog, CatalogPatch, git, sha
from .evidence import ReviewInputs
from .identities import IdentityRegistry
from .operations import DefinitionSnapshot, payload
from .preparation_models import Preparation, HEADER, MAX_FILES, MAX_BYTES, fail
from .previews import CompositionTrial, CompositionArchive


def tree(repo,commit):
    result={};keys=set()
    for row in git(repo,'ls-tree','-r','-z',commit).split(b'\0'):
        if not row:continue
        header,raw=row.split(b'\t',1);mode,kind,oid=header.decode().split();name=raw.decode('utf8')
        relative_path(name);key=path_key(name)
        if mode!='100644' or kind!='blob' or key in keys or any(p.casefold()=='.git' for p in name.split('/')):fail('unsafe_tree')
        keys.add(key);result[name]=dict(mode=mode,blob=oid)
    return result


class OfflineDestination:
    def __init__(self,trial,existing=None):
        if type(trial) is not CompositionTrial or trial._closed:fail('owned_trial_required')
        self.trial=trial
        self.root=Path(tempfile.mkdtemp(prefix='m5-base-',dir=trial.root)).resolve()
        git(self.root,'init','-b','master')
        for key,value in {'user.name':'Offline M5','user.email':'offline@invalid.local','core.autocrlf':'false',
                'core.hooksPath':str(self.root/'no-hooks')}.items():git(self.root,'config',key,value)
        atomic_bytes(self.root/'keep.txt',b'Unrelated baseline bytes\n')
        # The unchanged transport configures autocrlf=false after cloning.
        # Preserve the fixture's bytes during that initial clone as well,
        # independently of the operator's global Windows Git configuration.
        atomic_bytes(self.root/'.gitattributes',b'* -text\n')
        for name,raw in (existing or {}).items():
            validate_paths([dict(destination=name)])
            if not name.startswith('genre/'):fail('destination_scope')
            atomic_bytes(confined(self.root,name),raw)
        git(self.root,'add','--','keep.txt','.gitattributes',*(existing or {}))
        git(self.root,'commit','-m','Owned offline destination base')
        self.base=self.observe()

    def observe(self):
        if type(self.trial) is not CompositionTrial or self.trial._closed or not self.root.is_relative_to(self.trial.root):fail('destination_ownership')
        if git(self.root,'remote').strip() or git(self.root,'status','--porcelain').strip():fail('destination_ownership')
        if Path(git(self.root,'rev-parse','--absolute-git-dir').decode().strip()).resolve()!=self.root/'.git':fail('destination_ownership')
        head=git(self.root,'rev-parse','HEAD').decode().strip();tree(self.root,head)
        return dict(repository='Kometa-Team/Default-Images',branch='master',head=head,
            tree=git(self.root,'rev-parse',head+'^{tree}').decode().strip())


@dataclass(frozen=True)
class NativeSelection:
    registry: IdentityRegistry
    inputs: ReviewInputs
    snapshot_sha256: str
    authority: object

    def verify(self):
        if type(self.registry) is not IdentityRegistry or type(self.inputs) is not ReviewInputs:fail('native_context')
        ctx=self.inputs.composition
        if ctx.registry is not self.registry:fail('native_context')
        ctx.candidate.verify()
        from . import mappings
        store=self.registry.operations.contracts
        with store.read_connection() as db:
            mappings._require_no_pending_moves(store,db)
            state,graph,definitions,keys,retained,plans,_,entries=mappings._state(self.registry,store,db)
        if self.snapshot_sha256 not in state['snapshots']:fail('uncommitted_snapshot')
        snapshot=DefinitionSnapshot.from_bytes(store.read_object(self.snapshot_sha256));s=snapshot.to_dict()
        if snapshot.sha256!=self.snapshot_sha256 or s['composition_sha256']!=self.inputs.composition_sha256:fail('snapshot_binding')
        if s['operation_type'] not in {'ADD','UPDATE'} or ctx.candidate.data()['effective_definitions']!={i:definitions[i] for i in s['members']}:fail('current_definition')
        if set(s['members'])!=set(ctx.candidate.graph.index().outputs):fail('native_membership')
        from .basis import historical_basis
        for identity in s['members']:
            e=entries[identity];rule=historical_basis().rule(e['category'],e['variant'])
            if (e!=s['entries'][identity] or e['origin']!='assigned' or e['category']!='Genre'
                    or e['semantic']['language']!='en' or e['tombstone_sha256'] is not None
                    or rule['source_kind']!='logo' or rule['required_presentations']!=['single']
                    or retained[identity]['snapshot_sha256']!=snapshot.sha256 or keys[identity]!=identity):fail('cohort_or_mapping')
            row=graph.index().outputs[identity]
            if set(row['companions'])-set(s['members']):fail('required_member')
        from .review import ReviewArchive
        archive=ReviewArchive(store.root)
        review,bundle,records=archive.read(s['review_id'],expected_sha256=s['review_sha256'])
        archive._attribution(review,records,self.authority)
        if review.to_dict()['state']!='MAINTAINER_APPROVED' or bundle.sha256!=s['review_bundle_sha256']:fail('current_review')
        from ..contracts.evidence_consumption import ConsumptionAttestation,revalidate
        before=ConsumptionAttestation.from_dict(json.loads(s['phase3_json']))
        current=revalidate(before,expected_sha256=before.sha256,**self.inputs.phase3_inputs)
        if current.encoded!=before.encoded:fail('current_phase3')
        # M4/M6 replay above validates native pixels, original review decisions,
        # immutable snapshots and original owned receipt/job records.
        needed={(r['kind'],r['id']) for r in payload(s['intent_json'])['reads']}
        needed.update((r['kind'],r['id']) for r in payload(s['intent_json'])['writes'])
        needed.add(('evidence',self.registry.subject))
        heads=[state['heads'].get(k,dict(kind=k[0],id=k[1],subjects=[],revision=0,sha256=None)) for k in sorted(needed)]
        return s,dict(registry_sha256=self.registry.view().snapshot.sha256,native_heads=heads,
            native_heads_sha256=fingerprint(heads),definitions={i:definitions[i] for i in s['members']},
            phase3_sha256=current.sha256)


def plan_operation(selection,patch,target,*,max_files=MAX_FILES,max_bytes=MAX_BYTES):
    if type(selection) is not NativeSelection or type(patch) is not CatalogPatch or type(target) is not OfflineDestination:fail('typed_preparation')
    if type(max_files) is not int or type(max_bytes) is not int or not 1<=max_files<=MAX_FILES or not 1<=max_bytes<=MAX_BYTES:fail('batch_limits')
    snapshot,context=selection.verify();catalog=patch.verify(context['definitions'])
    if patch.source.trial is not target.trial or selection.registry.operations.root!=target.trial.config.cache_dir:fail('foreign_preparation')
    if catalog['members']!=snapshot['members'] or catalog['definitions_sha256']!=fingerprint(context['definitions']):fail('catalog_membership')
    if target.observe()!=target.base:fail('destination_changed')
    baseline=target.base;inventory=tree(target.root,baseline['head'])
    archive=CompositionArchive(selection.registry.operations.root,readonly=True);members=[]
    for identity in snapshot['members']:
        member=snapshot['artwork'][identity];entry=snapshot['entries'][identity]
        path=entry['names']['public_path']
        if path!=member['public_path'] or not path.startswith('genre/'):fail('destination_scope')
        raw=archive.read_bytes(member['object_sha256'])
        if sha(raw)!=member['sha256'] or len(raw)!=member['bytes']:fail('artifact_bytes')
        output=confined(target.trial.root,'m5-artwork/'+selection.snapshot_sha256+'/'+identity+'.jpg')
        if output.exists():
            if output.read_bytes()!=raw:fail('staged_artifact_changed')
        else:atomic_bytes(output,raw)
        previous=git(target.root,'show',baseline['head']+':'+path) if path in inventory else None
        if any(path_key(p)==path_key(path) and p!=path for p in inventory):fail('destination_case_collision')
        members.append(dict(identity=identity,destination=path,source=str(output),sha256=member['sha256'],
            size=len(raw),git_blob=blob_id(output),previous_sha256=None if previous is None else sha(previous),
            previous_git_blob=inventory[path]['blob'] if previous is not None else '0'*40,
            object_sha256=member['object_sha256'],receipt_sha256=member['receipt_sha256'],
            receipt_object_sha256=member['receipt_object_sha256']))
    validate_paths(members)
    upload=[dict(destination=m['destination'],source=m['source'],sha256=m['sha256'],size=m['size'],
        previous_sha256=m['previous_sha256'],git_blob=m['git_blob'],previous_git_blob=m['previous_git_blob'],
        context_sha256=selection.snapshot_sha256) for m in members if m['sha256']!=m['previous_sha256']]
    manifest=sealed(dict(kind='approved-library-publication-manifest',baseline=baseline,
        members=sorted(upload,key=lambda m:m['destination']),withheld=[],exact_matches_skipped=[m['destination'] for m in members if m['sha256']==m['previous_sha256']],
        simulation=True,remote_writes_authorized=False,merge_authorized=False))
    plan=batch_plan(manifest,max_files=max_files,max_bytes=max_bytes)
    result=Preparation.from_dict(dict(**HEADER,operation=snapshot['operation'],snapshot_sha256=selection.snapshot_sha256,
        registry_sha256=context['registry_sha256'],native_heads=context['native_heads'],native_heads_sha256=context['native_heads_sha256'],
        review_sha256=snapshot['review_sha256'],phase3_sha256=context['phase3_sha256'],
        catalog_sha256=patch.sha256,source=catalog['source'],required_members=snapshot['members'],
        members=members,destination=baseline,manifest=manifest,plan=plan))
    CompositionArchive(selection.registry.operations.root).put_json(result.to_dict())
    return result


def revalidate(preparation,selection,patch,target):
    if type(preparation) is not Preparation:fail('typed_preparation')
    v=preparation.to_dict()
    current=plan_operation(selection,patch,target,max_files=v['plan']['max_files'],max_bytes=v['plan']['max_bytes'])
    if current.encoded!=preparation.encoded:fail('stale_preparation')
    return current


def inspect_transport(preparation,target,root):
    v=preparation.to_dict();base=v['destination']['head'];remote=root/'remote.git';work=root/'work'
    if not remote.exists():return dict(verified_batches=0,head=base,complete=False,commits=[])
    if Path(git(remote,'rev-parse','--absolute-git-dir').decode().strip()).resolve()!=remote:fail('transport_ownership')
    chain=git(work,'rev-list','--reverse',base+'..HEAD').decode().splitlines()
    observed=git(remote,'rev-parse','refs/heads/library-offline').decode().strip()
    if observed not in [base,*chain] or len(chain)>len(v['plan']['batches']):fail('foreign_prefix')
    count=0 if observed==base else chain.index(observed)+1
    original=tree(target.root,base);actual=tree(remote,observed);expected=dict(original)
    for index,batch in enumerate(v['plan']['batches'][:count]):
        commit=chain[index];parent=base if index==0 else chain[index-1]
        if git(work,'rev-parse',commit+'^').decode().strip()!=parent:fail('commit_parent')
        from ..library_stage import verify_diff
        verify_diff(remote,parent,commit,batch['members'])
        for m in batch['members']:expected[m['destination']]=dict(mode='100644',blob=m['git_blob'])
    if actual!=expected:fail('unrelated_tree_change')
    verified={m['destination'] for b in v['plan']['batches'][:count] for m in b['members']}
    verified.update(m['destination'] for m in v['members'] if m['sha256']==m['previous_sha256'])
    for m in v['members']:
        if m['destination'] in verified:
            if sha(git(remote,'show',observed+':'+m['destination']))!=m['sha256']:fail('remote_bytes')
    return dict(verified_batches=count,head=observed,complete=count==len(v['plan']['batches']) and len(verified)==len(v['members']),commits=chain[:count])


def _finish_owned_staging(preparation,target,root):
    """Forward recovery of uncommitted local files; never reset/delete history.

    Original offline transport rejects any dirty workspace on entry. A failed
    object/commit creation can leave exactly its approved next batch staged.
    Finish that one local commit after fresh guards, then hand back to the
    original transport for its ancestry, pack, push and prefix reconciliation.
    """
    from .. import library_transport
    value=preparation.to_dict();work=root/'work';remote=root/'remote.git'
    if not work.exists():return
    if Path(git(work,'rev-parse','--absolute-git-dir').decode().strip()).resolve()!=work/'.git':fail('transport_ownership')
    if git(work,'remote').strip():fail('transport_ownership')
    identity=json.loads(confined(root,'exercise.json',must_exist=True).read_bytes())
    if identity.get('plan_sha256')!=value['plan']['sha256'] or identity.get('baseline')!=value['destination']['head']:fail('transport_ownership')
    base=value['destination']['head'];chain=git(work,'rev-list','--reverse',base+'..HEAD').decode().splitlines()
    if len(chain)>len(value['plan']['batches']):fail('foreign_prefix')
    previous=base
    from ..library_stage import verify_diff
    for commit,batch in zip(chain,value['plan']['batches']):
        if git(work,'rev-parse',commit+'^').decode().strip()!=previous:fail('commit_parent')
        verify_diff(work,previous,commit,batch['members']);previous=commit
    dirty=[r for r in git(work,'status','--porcelain','-z').split(b'\0') if r]
    if not dirty:return
    if len(chain)==len(value['plan']['batches']):fail('unexpected_worktree')
    batch=value['plan']['batches'][len(chain)];allowed={m['destination']:m for m in batch['members']}
    for row in dirty:
        status,path=row[:2].decode(),row[3:].decode('utf8')
        if path not in allowed or status not in {'??',' A','A ',' M','M ','AM','MM'}:fail('unexpected_worktree')
    for name,member in allowed.items():
        source=Path(member['source']).read_bytes()
        if sha(source)!=member['sha256']:fail('staged_artifact_changed')
        destination=confined(work,name)
        if destination.exists():
            old=destination.read_bytes()
            if sha(old) not in {member['sha256'],member['previous_sha256']} and not source.startswith(old):fail('unexpected_worktree')
        atomic_bytes(destination,source,replace=True)
    library_transport.git(work,'add','--',*allowed)
    library_transport.git(work,'commit','-m',f"Offline approved library batch {len(chain)+1}: {batch['membership_sha256']}")
    commit=git(work,'rev-parse','HEAD').decode().strip()
    verify_diff(work,previous,commit,batch['members'])


def _run_offline(preparation,selection,patch,target,*,stop_after=None,fail_at=None,cancel=None,checkpoint=lambda name:None):
    from .preparation_progress import Progress
    from ..library_transport import run
    revalidate(preparation,selection,patch,target)
    value=preparation.to_dict();root=confined(target.trial.root,'m5-transport-'+preparation.sha256)
    progress=Progress(selection.registry.operations.root,preparation)
    prior=progress.read()
    if prior is None:
        if root.exists():fail('missing_intent')
        checkpoint('before_intent')
        prior=progress.append('PREPARED',0,None,expected=None,checkpoint=checkpoint)
        checkpoint('after_intent')
    planned=len(value['plan']['batches']);report=None
    for number in range(1,max(planned,1)+1):
        revalidate(preparation,selection,patch,target)
        if cancel is not None and cancel():fail('cancelled')
        try:
            checkpoint('before_transport')
            _finish_owned_staging(preparation,target,root)
            run(value['plan'],root,target.root,stop_after=number,fail_at=fail_at)
            checkpoint('after_transport')
            report=inspect_transport(preparation,target,root)
            prior=progress.append('OFFLINE_VERIFIED' if report['complete'] else 'INCOMPLETE',
                report['verified_batches'],report['head'],expected=prior,target=target,checkpoint=checkpoint)
        except Exception as error:
            # Actual refs are observed on resume; the exception is not an answer
            # about whether a push or commit happened. Keep every success.
            latest=progress.read()
            progress.append('UNKNOWN',latest['verified_batches'],latest['head'],expected=latest,error=error)
            raise
        if stop_after is not None and number>=stop_after:break
    return dict(**value_flags(),**report,preparation_sha256=preparation.sha256,progress_sha256=prior['sha256'])


@contextmanager
def _lease(target,preparation):
    path=confined(target.trial.root,'m5-lease-'+preparation.sha256)
    with path.open('a+b') as stream:
        if path.stat().st_size==0:stream.write(b'0');stream.flush()
        stream.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:fail('concurrent_preparation')
        try:yield
        finally:
            stream.seek(0)
            if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def run_offline(preparation,selection,patch,target,*,stop_after=None,fail_at=None,cancel=None,checkpoint=lambda name:None):
    if type(preparation) is not Preparation or type(target) is not OfflineDestination:fail('typed_preparation')
    if stop_after is not None and (type(stop_after) is not int or stop_after<1):fail('batch_limits')
    with _lease(target,preparation):
        return _run_offline(preparation,selection,patch,target,stop_after=stop_after,fail_at=fail_at,cancel=cancel,checkpoint=checkpoint)


def value_flags():
    return dict(simulation=True,publication_authorized=False,remote_writes_authorized=False,ready=False,active=False,network_writes=0)


def publish_operational(*args,**kwargs):fail('production_unavailable')
