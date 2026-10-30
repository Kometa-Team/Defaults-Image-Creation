"""M4 fixtures enter the real loaders, native workers, review and commit APIs."""
from copy import deepcopy
from io import BytesIO
import json

from PIL import Image, ImageDraw
import yaml

from create_defaults.bulk.common import canonical
from create_defaults.bulk.lifecycle import apply, mappings
from create_defaults.bulk.lifecycle.candidates import poster_candidate
from create_defaults.bulk.lifecycle.current_mapping import select_current, stage_source, CurrentTransaction, propose_current
from create_defaults.bulk.lifecycle.operations import propose, Transaction
from create_defaults.phase4.m7_tests.helpers import prepare, commit
from create_defaults.phase4.tests.transaction_samples import reviewed, transaction


def rename(case, name='Fixture Current', suffix='-rename'):
    plan=prepare(case,name=name,suffix=suffix)
    commit(case,plan)
    case['definition_hint']=plan.to_dict()['definitions']
    return plan


def epoch(case,label='current'):
    trial,ctx,_,_=case['row'];registry=ctx.registry
    # This is only caller input for the real selector, which independently
    # reconstructs and compares current committed definitions. It grants no
    # authority and avoids a duplicate full recovery merely to serialize YAML.
    definitions=case.get('definition_hint')
    if definitions is None:definitions=mappings.recover(registry)['definitions']
    content=json.loads(ctx.candidate.content_json)
    for i in content:
        names=registry.view().entry(i)['names']
        content[i].update(display_name=names['display_name'],source=names['source'])
    path=trial.root/(label+'.yml')
    path.write_text(yaml.safe_dump(dict(schema_version=1,category='Genre',
        definitions=[definitions[i] for i in sorted(content)])),encoding='utf8')
    return select_current(registry,expected=registry.view().head,paths=[path],
        profiles_path=ctx.candidate.profiles_path,posters=sorted(content),content=content,trial=trial)


def candidate(case,selected,label='m4-update',mutate_source=True):
    trial,ctx,_,_=case['row'];r=ctx.registry
    content=json.loads(selected.before.content_json)
    if mutate_source:
        first=next(iter(content));entry=r.view().entry(first)
        path=trial.config.asset_dir/entry['names']['source']['path']
        image=Image.open(BytesIO(path.read_bytes())).convert('RGBA')
        # M5 already removed the left rectangle. Change the remaining visible
        # blue ellipse so this epoch demonstrates different encoded artwork.
        ImageDraw.Draw(image).ellipse((240,65,325,140),fill=(0,0,0,0))
        out=BytesIO();image.save(out,format='PNG')
        source=stage_source(selected,trial,first,out.getvalue(),expected_source_sha256=entry['names']['source']['sha256'])
        for i in content:
            e=r.view().entry(i)
            if e['names']['source']['path']!=source['path']:continue
            names=deepcopy(e['names']);names['source']=source
            r.revise(i,names=names,entry_revision=e['revision'],token=label+i,expected=r.view().head)
            content[i]['source']=source
    path=trial.root/(label+'.yml')
    path.write_text(yaml.safe_dump(dict(schema_version=1,category='Genre',
        definitions=list(selected.before.data()['effective_definitions'].values()))),encoding='utf8')
    return poster_candidate(r,expected=r.view().head,paths=[path],profiles_path=selected.before.profiles_path,
                            posters=sorted(content),content=content,config=trial.config)


def prepare_update(case,selected,proposed=None,label='m4-updated'):
    trial,ctx,_,_=case['row'];r=ctx.registry
    proposed=proposed or candidate(case,selected,label=label)
    context=propose_current(selected,proposed,identity='synthetic.operation.'+label)
    native=reviewed(trial,context,label=label)
    tx=Transaction(native['inputs'],native['bundle'].to_dict()['id'],native['state'].sha256,
                   canonical(json.loads(selected.lineage_json)['accepted_snapshots']).decode())
    current=CurrentTransaction(tx,selected)
    # Independently pin the original native snapshot. The real coordinator
    # invokes CurrentTransaction.prepare and its current-lineage verification
    # under its lock; repeating that full journal replay here adds no evidence.
    return native,current,tx.prepare()


def commit_update(case,selected,label='m4-updated'):
    native,tx,snapshot=prepare_update(case,selected,label=label)
    result=apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=native['authority'])
    return native,tx,snapshot,result


def add_control(case,*,shared=False):
    from create_defaults.phase4.tests.transaction_samples import additional, additional_candidate
    trial,ctx,_,_=case['row']
    data=additional(case,'control',shared=shared)
    added=additional_candidate(case,data)
    context=propose(ctx.registry,before=None,candidate=added,identity='synthetic.operation.control-add',operation='ADD')
    native=reviewed(trial,context,label='control-add')
    tx,snapshot=transaction(native)
    apply.commit_synthetic(tx,expected_snapshot_sha256=snapshot.sha256,authority=native['authority'])
    return snapshot
