"""M5 -> original Package E operator transport, owned local fixtures ONLY."""
from dataclasses import dataclass
from pathlib import Path
import json
import subprocess
import weakref

from ..common import canonical,confined,fingerprint,reject_links
from ..library_sources import check_seal,load_json,save,sealed
from .catalog_preparation import git,sha
from .preparation_models import Preparation
from .publication_preparation import NativeSelection,OfflineDestination,revalidate,tree,_lease
from .catalog_preparation import CatalogPatch
from .draft_models import DraftBinding,HEADER,MODE,fail
from .draft_progress import DraftProgress,native_heads
from .package_e import SidecarStore

_OWNED=weakref.WeakKeyDictionary()


@dataclass(frozen=True)
class _Owned:
    preparation: Preparation
    selection: NativeSelection
    patch: CatalogPatch
    target: OfflineDestination
    root: Path
    binding: DraftBinding


def _context(protocol):
    if type(protocol) is not OfflineProtocol or protocol not in _OWNED:fail('offline_ownership')
    return _OWNED[protocol]


def _native(c):
    if type(c.target) is not OfflineDestination or c.target.trial._closed:fail('offline_ownership')
    if c.root!=confined(c.target.trial.root,'m6-draft-'+c.preparation.sha256):fail('offline_ownership')
    revalidate(c.preparation,c.selection,c.patch,c.target)
    if DraftBinding.from_bytes(c.binding.encoded).sha256!=c.binding.sha256:fail('binding_object')
    store=SidecarStore.open_readonly(c.selection.registry.operations.root)
    if store.read_object(c.binding.sha256)!=c.binding.encoded:fail('binding_object')
    with store.read_connection() as db:native_heads(store,db,c.preparation)


def _remote(c):
    remote=confined(c.root,'remote.git',must_exist=False)
    if not remote.is_dir() or git(remote,'rev-parse','--is-bare-repository').strip()!=b'true':fail('offline_ownership')
    if Path(git(remote,'rev-parse','--absolute-git-dir').decode().strip()).resolve()!=remote:fail('offline_ownership')
    # A bare clone retains a local origin. Bind its exact owned source, never an
    # external URL or an additional remote; no fetch from this origin is needed.
    if git(remote,'remote').decode().splitlines()!=['origin']:fail('offline_ownership')
    origin=git(remote,'config','--get','remote.origin.url').decode().strip()
    if origin!=str(c.target.root):fail('offline_ownership')
    disabled=confined(c.root,'offline-no-hooks')
    if disabled.exists() or git(remote,'config','--get','core.hooksPath').decode().strip()!=str(disabled):fail('offline_ownership')
    v=c.binding.to_dict();base=v['plan']['baseline']['head'];branch=v['authorization']['branch']
    if git(remote,'rev-parse','refs/heads/master').decode().strip()!=base:fail('baseline_drift')
    refs={line.split(' ',1)[0]:line.split(' ',1)[1] for line in git(remote,'for-each-ref','--format=%(refname) %(objectname)').decode().splitlines()}
    if not set(refs)<={'refs/heads/master','refs/heads/'+branch,'refs/pull/1/head'}:fail('foreign_ref')
    observed=refs.get('refs/heads/'+branch)
    if observed is None:chain=[];head=base
    else:
        head=observed;chain=git(remote,'rev-list','--reverse',base+'..'+head).decode().splitlines()
        if not chain or len(chain)>len(v['plan']['batches']) or chain[-1]!=head:fail('foreign_prefix')
    initial=tree(remote,base);expected=dict(initial);parent=base
    from ..library_stage import verify_diff
    for commit,batch in zip(chain,v['plan']['batches']):
        if git(remote,'rev-parse',commit+'^').decode().strip()!=parent:fail('foreign_prefix')
        verify_diff(remote,parent,commit,batch['members'])
        for m in batch['members']:expected[m['destination']]=dict(mode='100644',blob=m['git_blob'])
        parent=commit
    if tree(remote,head)!=expected:fail('unexpected_remote_tree')
    verified={m['destination'] for b in v['plan']['batches'][:len(chain)] for m in b['members']}
    for m in c.preparation.to_dict()['members']:
        if m['sha256']==m['previous_sha256']:verified.add(m['destination'])
        if m['destination'] in verified:
            raw=git(remote,'show',head+':'+m['destination'])
            if sha(raw)!=m['sha256'] or len(raw)!=m['size']:fail('remote_bytes')
    complete=len(chain)==len(v['plan']['batches']) and len(verified)==len(c.preparation.to_dict()['required_members'])
    pr_path=confined(c.root,'offline-pr.json');pr=None
    if pr_path.exists():
        pr=check_seal(load_json(pr_path))
        if (set(pr)!={'kind','simulation','test_only','plan_sha256','authorization_sha256','pr','sha256'}
                or pr['kind']!='phase5-m6-owned-protocol-pr' or pr['simulation'] is not True or pr['test_only'] is not True
                or pr['plan_sha256']!=v['plan']['sha256'] or pr['authorization_sha256']!=v['authorization']['sha256']
                or pr['pr']!=_pr(v,head) or not complete or refs.get('refs/pull/1/head')!=head):fail('foreign_draft')
    elif 'refs/pull/1/head' in refs and (not complete or refs['refs/pull/1/head']!=head):fail('foreign_draft')
    return dict(verified_batches=len(chain),head=head,complete=complete,commits=chain,
                draft_verified=pr is not None,draft_sha256=None if pr is None else pr['sha256'])


def _pr(v,head):return dict(number=1,url='https://example.invalid/offline-m6/1',isDraft=True,state='OPEN',headRefOid=head,baseRefName='master')


class OfflineProtocol:
    """No public constructor, arbitrary root/provider, gh process or HTTP client."""
    __slots__=('__weakref__',)
    def __init__(self,*args,**kwargs):fail('offline_ownership')

    def verify(self,root,plan,auth,report=None,*,test_remote=None):
        c=_context(self)
        from ..operator_publication import gate
        check_seal(auth);check_seal(plan);gate(plan,auth)
        v=c.binding.to_dict()
        if (auth.get('policy',{}).get('mode')!=MODE or auth.get('test_only') is not True
                or plan!=v['plan'] or auth!=v['authorization'] or reject_links(root).resolve()!=c.root):fail('offline_authorization')
        if test_remote is not None and reject_links(test_remote).resolve()!=c.root/'remote.git':fail('foreign_target')
        _native(c)
        actual=_remote(c)
        prior=DraftProgress(c.selection.registry.operations.root,c.binding).read()
        if prior is None:fail('missing_intent')
        if actual['verified_batches']<prior['verified_batches']:fail('remote_rollback')
        if prior['head'] is not None and prior['head'] not in [v['plan']['baseline']['head'],*actual['commits']]:fail('remote_rollback')
        if prior['draft_sha256'] is not None and actual['draft_sha256']!=prior['draft_sha256']:fail('remote_rollback')
        work=confined(c.root,'transport/work')
        if work.exists():
            if not (work/'.git').is_dir() or Path(git(work,'rev-parse','--absolute-git-dir').decode().strip()).resolve()!=work/'.git':fail('foreign_worktree')
            remotes=git(work,'remote','-v').decode().splitlines()
            if remotes and any(line.split()[1]!=str(c.root/'remote.git') for line in remotes):fail('foreign_target')
            disabled=confined(c.root,'transport/no-hooks')
            if disabled.exists():fail('foreign_worktree')
            if remotes and git(work,'config','--get','core.hooksPath').decode().strip()!=str(disabled):fail('foreign_worktree')
        if report is not None:
            check_seal(report)
            if (report.get('plan_sha256')!=plan['sha256'] or report.get('authorization_sha256')!=auth['sha256']
                    or report.get('head')!=actual['head'] or report.get('complete') is not True or not actual['complete']):fail('incomplete_report')
        return actual

    def inspect(self):
        c=_context(self);v=c.binding.to_dict()
        return OfflineProtocol.verify(self,c.root,v['plan'],v['authorization'])

    def client(self,root,plan,auth,report):
        OfflineProtocol.verify(self,root,plan,auth,report)
        return _LocalReader(self,report)

    def observe(self,args,*,text):
        c=_context(self);v=c.binding.to_dict();report=check_seal(load_json(c.root/'transport/transport-report.json'))
        actual=OfflineProtocol.verify(self,c.root,v['plan'],v['authorization'],report)
        expected=['gh','pr','list','-R','Kometa-Team/Default-Images','--head',v['authorization']['branch'],
                  '--state','all','--json','number,url,isDraft,state,headRefOid,baseRefName']
        if args!=expected or text is not True:fail('protocol_command')
        return json.dumps([_pr(v,actual['head'])] if actual['draft_verified'] else [])

    def execute(self,args,*,capture_output,text):
        c=_context(self);v=c.binding.to_dict();report=check_seal(load_json(c.root/'transport/transport-report.json'))
        actual=OfflineProtocol.verify(self,c.root,v['plan'],v['authorization'],report)
        if (type(args) is not list or len(args)!=14 or not isinstance(args[11],str) or not 1<=len(args[11])<=200
                or args!=['gh','pr','create','-R','Kometa-Team/Default-Images','--head',v['authorization']['branch'],
                           '--base','master','--draft','--title',args[11],'--body-file',str(c.root/'pr-body.md')]
                or capture_output is not True or text is not True):fail('protocol_command')
        remote=c.root/'remote.git';ref='refs/pull/1/head'
        refs=git(remote,'for-each-ref','--format=%(refname)','refs/pull').decode().splitlines()
        _native(c)
        if not refs:git(remote,'update-ref',ref,actual['head'],'0'*40)
        elif refs!=[ref] or git(remote,'rev-parse',ref).decode().strip()!=actual['head']:fail('foreign_draft')
        _native(c)
        value=sealed(dict(kind='phase5-m6-owned-protocol-pr',simulation=True,test_only=True,
            plan_sha256=v['plan']['sha256'],authorization_sha256=v['authorization']['sha256'],pr=_pr(v,actual['head'])))
        path=c.root/'offline-pr.json'
        if path.exists() and load_json(path)!=value:fail('foreign_draft')
        save(path,value)
        # Deterministic uncertain acknowledgement: the original operator must
        # discover the actual already-created fixture PR instead of duplicating.
        return subprocess.CompletedProcess(args,1,stdout='',stderr='offline fixture acknowledgement unavailable')


class _LocalReader:
    def __init__(self,protocol,report):self.protocol=protocol;self.report=report
    def _current(self):
        c=_context(self.protocol);v=c.binding.to_dict()
        OfflineProtocol.verify(self.protocol,c.root,v['plan'],v['authorization'],self.report)
        return c
    def head(self,branch):
        c=self._current();v=c.binding.to_dict()
        if branch not in {'master',v['authorization']['branch']}:fail('foreign_ref')
        head=git(c.root/'remote.git','rev-parse','refs/heads/'+branch).decode().strip()
        return head,git(c.root/'remote.git','rev-parse',head+'^{tree}').decode().strip()
    def tree(self,tree_id,*,recursive):
        c=self._current()
        if recursive is not True:fail('incomplete_tree')
        # One independent tree query has one fresh complete authority proof.
        # Read both heads and trees afresh here; calling public head() would
        # replay that same complete proof twice inside this one query.
        remote=c.root/'remote.git'
        allowed=set()
        for branch in ('master',c.binding.to_dict()['authorization']['branch']):
            head=git(remote,'rev-parse','refs/heads/'+branch).decode().strip()
            allowed.add(git(remote,'rev-parse',head+'^{tree}').decode().strip())
        if tree_id not in allowed:fail('foreign_tree')
        rows=tree(c.root/'remote.git',tree_id)
        return dict(truncated=False,tree=[dict(path=p,sha=r['blob'],mode=r['mode'],type='blob') for p,r in rows.items()])


def propose(preparation,selection,patch,target):
    if (type(preparation) is not Preparation or type(selection) is not NativeSelection
            or type(patch) is not CatalogPatch or type(target) is not OfflineDestination):fail('typed_binding')
    revalidate(preparation,selection,patch,target)
    v=preparation.to_dict();root=confined(target.trial.root,'m6-draft-'+preparation.sha256)
    policy=dict(mode=MODE,preparation_sha256=preparation.sha256,catalog_sha256=patch.sha256,
                technical_batch_limits=dict(max_files=v['plan']['max_files'],max_bytes=v['plan']['max_bytes']))
    rows=[dict(destination=m['destination'],candidate_path=m['source'],candidate_sha256=m['sha256'],
        candidate_blob=m['git_blob'],published_sha256=m['previous_sha256'],published_blob=m['previous_git_blob'],
        hash_state='different',technical_valid=True,difference_class='phase5-native-reviewed',
        context_sha256=preparation.sha256,kind='poster') for m in v['members'] if m['sha256']!=m['previous_sha256']]
    inventory=sealed(dict(baseline=v['destination'],rows=rows,preparation_sha256=preparation.sha256))
    if root.exists():
        marker=confined(root,'m6-owned.json',must_exist=True)
        if load_json(marker)!=dict(preparation_sha256=preparation.sha256,simulation=True):fail('foreign_workspace')
    else:
        root.mkdir()
        revalidate(preparation,selection,patch,target)
        save(root/'m6-owned.json',dict(preparation_sha256=preparation.sha256,simulation=True))
    from ..operator_publication import prepare
    manifest=prepare(inventory,policy,root)
    revalidate(preparation,selection,patch,target)
    if manifest['withheld'] or len(manifest['members'])!=len(rows):fail('incomplete_membership')
    return dict(inventory=inventory,manifest=manifest,policy=policy,root=root,
                no_upload_required=not manifest['members'],simulation=True,publication_authorized=False,
                operation_complete=False,network_writes=0)


def bind(preparation,selection,patch,target,fixture_receipt):
    proposal=propose(preparation,selection,patch,target)
    if not proposal['manifest']['members']:fail('no_upload_required')
    from ..operator_publication import authorize
    plan,auth=authorize(proposal['manifest'],proposal['policy'],fixture_receipt)
    binding=DraftBinding.from_dict(dict(**HEADER,preparation=preparation.to_dict(),preparation_sha256=preparation.sha256,
        catalog_sha256=patch.sha256,inventory=proposal['inventory'],manifest=proposal['manifest'],plan=plan,authorization=auth))
    root=proposal['root'];store=SidecarStore(selection.registry.operations.root)
    documents=[('binding.json',binding.to_dict()),('inventory.json',proposal['inventory']),
               ('approved-git-batch-plan.json',plan),('draft-staging-authorization.json',auth)]
    for name,value in documents:
        path=confined(root,name)
        if path.exists() and load_json(path)!=value:fail('changed_authorization')
    revalidate(preparation,selection,patch,target)
    store.put_object(binding.encoded,expected_sha256=binding.sha256)
    progress=DraftProgress(store.root,binding);prior=progress.read()
    if prior is None:
        if (root/'binding.json').exists():fail('missing_intent')
        progress.append('PREPARED',expected=None)
    for name,value in documents:
        revalidate(preparation,selection,patch,target)
        path=confined(root,name)
        if path.exists() and load_json(path)!=value:fail('changed_authorization')
        save(path,value)
    remote=confined(root,'remote.git')
    if not remote.exists():
        revalidate(preparation,selection,patch,target)
        result=subprocess.run(['git','clone','--bare','--config','core.hooksPath='+str(root/'offline-no-hooks'),
                               str(target.root),str(remote)],capture_output=True,timeout=180)
        if result.returncode:fail('offline_clone')
    entries=[dict(path=p,sha=r['blob'],mode=r['mode'],type='blob') for p,r in tree(target.root,plan['baseline']['head']).items()]
    snapshot=sealed(dict(entries=entries))
    path=root/'production-snapshot.json'
    if path.exists() and load_json(path)!=snapshot:fail('destination_binding')
    revalidate(preparation,selection,patch,target);save(path,snapshot)
    protocol=object.__new__(OfflineProtocol)
    _OWNED[protocol]=_Owned(preparation,selection,patch,target,root,binding)
    OfflineProtocol.verify(protocol,root,plan,auth,test_remote=remote)
    return protocol


def run_offline(protocol,*,stop_after=None,fail_at=None,draft=True):
    c=_context(protocol);v=c.binding.to_dict()
    from .. import operator_publication as operator
    from ..library_stage import _offline_protocol
    _offline_protocol(c.root,v['plan'],v['authorization'],protocol,test_remote=c.root/'remote.git')
    progress=DraftProgress(c.selection.registry.operations.root,c.binding)
    def guard(**context):
        # This private callback is invoked only by the sealed Package E stage
        # and draft checkpoints. They independently verify the owned protocol
        # BEFORE and AFTER this callback, including fresh full M5 revalidation.
        # Keep the unique scoped head/CAS checks here; do not replay the same
        # full authority proof a third time between those two fresh checks.
        if context['root']!=c.root/'transport' or context['plan']!=v['plan'] or context['authorization']!=v['authorization']:fail('write_scope')
        work=c.root/'transport/work'
        old=context['expected_local_head']
        if old is not None and git(work,'rev-parse','HEAD').decode().strip()!=old:fail('local_head_drift')
        actual=_remote(c)
        if context['phase']=='push':
            expected=context['expected_remote_head'];observed=None if not actual['commits'] else actual['head']
            if observed!=expected:fail('remote_head_drift')
        store=SidecarStore(c.selection.registry.operations.root)
        with store.transaction() as db:native_heads(store,db,c.preparation)
    with _lease(c.target,c.preparation):
        try:
            report=operator.stage(c.root,test_remote=c.root/'remote.git',offline=protocol,write_guard=guard,
                                  stop_after=stop_after,fail_at=fail_at)
            observation=OfflineProtocol.inspect(protocol)
            if report['complete'] and draft:
                operator.draft(c.root,'Offline M6 lifecycle fixture',offline=protocol,write_guard=guard)
                observation=OfflineProtocol.inspect(protocol)
            progress.append('OFFLINE_DRAFT_VERIFIED' if observation['draft_verified'] else 'INCOMPLETE',
                            expected=progress.read(),observation=observation,protocol=protocol)
            return dict(**observation,binding_sha256=c.binding.sha256,simulation=True,publication_authorized=False,
                        operation_complete=False,remote_writes_authorized=False,network_writes=0,ready=False,active=False)
        except Exception as error:
            current=progress.read()
            progress.append('UNKNOWN',expected=current,error=error)
            raise


def publish_operational(*args,**kwargs):fail('production_unavailable')
