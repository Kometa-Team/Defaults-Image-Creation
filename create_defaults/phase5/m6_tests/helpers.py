"""Isolated native fixtures. These decisions never authorize real transport."""
from create_defaults.phase5.m5_tests.helpers import prepared
from create_defaults.bulk.lifecycle.draft_transport import propose,bind,_context
from create_defaults.bulk.common import fingerprint


def connected(case,*,max_files=300,existing=None):
    from create_defaults.bulk.operator_publication import approve
    selection,patch,target,preparation=prepared(case,max_files=max_files,existing=existing)
    proposal=propose(preparation,selection,patch,target)
    receipt=approve(proposal['manifest'],proposal['policy'],reviewer='bullmoose20',
        policy_hash=fingerprint(proposal['policy']),manifest_hash=proposal['manifest']['sha256'],
        decision_text='ISOLATED M6 FIXTURE ONLY; no real person, contract or operational approval',
        accept_exceptions=True,allow_additions=[m['destination'] for m in proposal['manifest']['members'] if m['previous_sha256'] is None])
    protocol=bind(preparation,selection,patch,target,receipt)
    return protocol,_context(protocol)


def export_native(case,protocol,report,*,name):
    import hashlib,json,os
    from pathlib import Path
    from create_defaults.bulk.lifecycle.previews import CompositionArchive
    from create_defaults.bulk.lifecycle.catalog_preparation import git
    from create_defaults.bulk.lifecycle.draft_progress import DraftProgress
    c=_context(protocol);store=c.selection.registry.operations.contracts
    archive=CompositionArchive(store.root,readonly=True)
    root=Path(os.environ.get('M6_NATIVE_EXPORT','config/ci-validation/phase5-m6/native'))/name
    root.mkdir(parents=True,exist_ok=True)
    snapshots=case.get('snapshots',[case['snapshot']]);rows=[]
    for n,snapshot in enumerate(snapshots):
        for view in json.loads(snapshot.to_dict()['composition_json'])['views']:
            for m in view['members']:
                filename=f"epoch-{n}-{view['appearance']}-{m['identity']}.jpg"
                (root/filename).write_bytes(archive.read_bytes(m['object_sha256']))
                receipt=json.loads(store.read_object(m['receipt_object_sha256']))
                with store.read_connection() as db:
                    worker=dict(db.execute('SELECT id,status,receipt,spec,fingerprint FROM jobs WHERE id=?',(receipt['job_id'],)).fetchone())
                rows.append(dict(file=filename,member=m,receipt=receipt,worker=worker))
    catalog=json.loads(c.patch.document_json)
    for file,b in catalog['files'].items():
        for suffix,key in [('before','before_object'),('after','after_object')]:
            (root/(file+'.'+suffix)).write_bytes(archive.read_bytes(b[key]))
    v=c.binding.to_dict();remote=c.root/'remote.git';packs=[];parent=v['plan']['baseline']['head']
    for n,commit in enumerate(report['commits']):
        from create_defaults.bulk.library_stage import git as transport_git
        raw=transport_git(c.root/'transport/work','pack-objects','--stdout','--revs','--window=0','--no-reuse-delta',data=(commit+'\n^'+parent+'\n').encode())
        filename=f'batch-{n+1}.pack';(root/filename).write_bytes(raw)
        packs.append(dict(file=filename,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        parent=commit
    git(remote,'bundle','create',str((root/'transport.bundle').resolve()),'--all')
    def read(path):return json.loads((c.root/path).read_bytes())
    proof=dict(kind='phase5-m6-native-offline-proof',binding=v,binding_sha256=c.binding.sha256,
        catalog=catalog,catalog_sha256=c.patch.sha256,snapshots=[s.to_dict() for s in snapshots],
        snapshot_sha256=[s.sha256 for s in snapshots],rows=rows,transport=report,packs=packs,
        mapping=None if 'mapping' not in case else case['mapping'].to_dict(),
        progress=DraftProgress(store.root,c.binding).read(),operator_report=read('transport/transport-report.json'),
        original_journal=read('transport/journal.json'),final_remote_diff=read('complete-remote-diff.json'),
        draft_receipt=read('draft-pr.json'),protocol_pr=read('offline-pr.json'),
        pack_measurements=[json.loads(p.read_bytes()) for p in sorted((c.root/'transport/packs').glob('*.json'))],
        native_response_receipts=[json.loads(p.read_bytes()) for p in sorted((c.root/'actual-native-byte-responses').glob('*.json'))],
        simulation=True,publication_authorized=False,historical_artwork_regenerated=0,network_writes=0)
    proof['sha256']=fingerprint(proof)
    (root/'proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf8')
