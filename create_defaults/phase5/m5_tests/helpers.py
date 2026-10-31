"""Real native source/catalog/batch fixtures with no publication authority."""
from create_defaults.bulk.lifecycle.catalog_preparation import OwnedCatalog,prepare_catalog
from create_defaults.bulk.lifecycle.publication_preparation import NativeSelection,OfflineDestination,plan_operation


def prepared(case,*,existing=None,max_files=300):
    trial,ctx,_,_=case['row']
    selection=NativeSelection(ctx.registry,case['inputs'],case['snapshot'].sha256,case['authority'])
    source=OwnedCatalog(trial)
    definitions=case['snapshot'].to_dict()
    from create_defaults.bulk.lifecycle.operations import payload
    desired=payload(definitions['proposed_json'])['effective_definitions']
    patch=prepare_catalog(source,desired)
    target=OfflineDestination(trial,existing=existing)
    result=plan_operation(selection,patch,target,max_files=max_files)
    return selection,patch,target,result


def export_native(case,patch,target,result,report,*,name):
    import json
    import os
    from pathlib import Path
    from create_defaults.bulk.common import fingerprint
    from create_defaults.bulk.lifecycle.previews import CompositionArchive
    from create_defaults.bulk.lifecycle.catalog_preparation import git
    from create_defaults.bulk.lifecycle.preparation_progress import Progress
    root=Path(os.environ.get('M5_NATIVE_EXPORT','config/ci-validation/phase5-m5/native'))/name
    root.mkdir(parents=True,exist_ok=True)
    store=case['row'][1].registry.operations.contracts
    archive=CompositionArchive(store.root,readonly=True);rows=[]
    snapshots=case.get('snapshots',[case['snapshot']])
    for number,snapshot in enumerate(snapshots):
        for view in json.loads(snapshot.to_dict()['composition_json'])['views']:
            for member in view['members']:
                filename=f"epoch-{number}-{view['appearance']}-{member['identity']}.jpg"
                (root/filename).write_bytes(archive.read_bytes(member['object_sha256']))
                receipt=json.loads(store.read_object(member['receipt_object_sha256']))
                with store.read_connection() as db:
                    worker=dict(db.execute('SELECT id,status,receipt,spec,fingerprint FROM jobs WHERE id=?',(receipt['job_id'],)).fetchone())
                rows.append(dict(file=filename,member=member,receipt=receipt,worker=worker))
    catalog=json.loads(patch.document_json)
    for file,binding in catalog['files'].items():
        (root/(file+'.before')).write_bytes(archive.read_bytes(binding['before_object']))
        (root/(file+'.after')).write_bytes(archive.read_bytes(binding['after_object']))
    remote=target.trial.root/('m5-transport-'+result.sha256)/'remote.git'
    transport_root=remote.parent
    packs=[]
    import hashlib
    for path in sorted((transport_root/'packs').glob('*.pack')):
        raw=path.read_bytes();filename=path.name
        (root/filename).write_bytes(raw)
        packs.append(dict(file=filename,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    git(remote,'bundle','create',str((root/'transport.bundle').resolve()),'--all')
    proof=dict(kind='phase5-m5-native-offline-proof',preparation=result.to_dict(),preparation_sha256=result.sha256,
        catalog=catalog,catalog_sha256=patch.sha256,snapshots=[s.to_dict() for s in snapshots],
        snapshot_sha256=[s.sha256 for s in snapshots],rows=rows,transport=report,
        mapping=None if 'mapping' not in case else case['mapping'].to_dict(),
        progress=Progress(store.root,result).read(),transport_execution=json.loads((transport_root/'report.json').read_bytes()),
        packs=packs,simulation=True,publication_authorized=False,
        historical_artwork_regenerated=0,network_writes=0)
    proof['sha256']=fingerprint(proof)
    (root/'proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf8')
