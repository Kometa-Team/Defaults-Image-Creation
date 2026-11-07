"""Offline bounded review gallery or inventory text coverage; no publication.

Run with --help. Existing sources and evidence are read-only. Output must be a
new, disjoint directory. Gallery output has no production receipts and is never
a completed regeneration batch. Coverage reads names from an existing audit;
it does not claim to decode or revalidate the PNG inventory.
"""
import argparse
from collections import Counter
import hashlib
import html
import importlib.util
from itertools import islice
import json
from pathlib import Path
import shutil
import sys
import time

from PIL import Image, ImageChops, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import create_people_poster as poster
from bulk_regeneration_state import canonical, reject_links
from unicode_labels import resolve_label, STYLE_FONTS, POLICY_SHA256


def dump(path,value):
    path.write_text(json.dumps(value,ensure_ascii=True,sort_keys=True,indent=2)+'\n',encoding='utf8')


def audit_rows(path):
    value=json.loads(path.read_text(encoding='utf8'))
    assert value['failed']==0 and value['verified']==value['total']
    rows=[row for chunk in value['items']['chunks'] for row in chunk]
    assert len(rows)==value['total']
    return value,rows


def coverage(audit,output):
    value,rows=audit_rows(audit)
    renderer=poster.Renderer()
    counts={style:Counter() for style in STYLE_FONTS}
    adaptations=[]
    tick=time.perf_counter()
    for row in rows:
        name=Path(row['relative']).stem
        for style in STYLE_FONTS:
            try:
                label=resolve_label(name,name,style,renderer.metrics,
                    lettering=poster.label_name(name.replace('_ccexpress','')))
                counts[style][label.resolution_method]+=1
                if label.resolution_method!='original':adaptations.append(label.record())
            except ValueError as error:
                counts[style]['review-required']+=1
                adaptations.append(getattr(error,'record',dict(name=name,style=style,error=str(error))))
    result=dict(purpose='unicode-text-shaping-coverage-v1',publication_authorized=False,
        audit_sha256=poster.digest(audit),audit_canonical_sha256=canonical(value),
        source_inventory_sha256=value['inventory_sha256'],people=len(rows),
        style_checks=len(rows)*len(STYLE_FONTS),counts=counts,adaptations=adaptations,
        unicode_policy_sha256=POLICY_SHA256,renderer=poster.renderer_fingerprint(),
        elapsed_seconds=time.perf_counter()-tick,pngs_read=0)
    dump(output/'coverage.json',result)
    print(json.dumps(dict(people=len(rows),counts=counts,pngs_read=0)))


def legacy_renderer(directory):
    # Isolated import of a retained checkout; no Git checkout/reset or mutation.
    saved=sys.modules.get('poster_fonts')
    try:
        for name in ('poster_fonts','create_people_poster'):
            key=name if name=='poster_fonts' else '_historical_people_poster'
            spec=importlib.util.spec_from_file_location(key,directory/(name+'.py'))
            module=importlib.util.module_from_spec(spec)
            sys.modules[key]=module
            spec.loader.exec_module(module)
        return module.Renderer()
    finally:
        if saved is not None:sys.modules['poster_fonts']=saved


def selected_sources(source):
    paths=list(islice(source.glob('*/Images/*.png'),5))
    if not 1 <= len(paths) <= 4:
        raise ValueError('Visual review requires an explicitly isolated fixture of 1-4 PNGs; full-source rendering is forbidden')
    return sorted(paths)


def gallery(source,audit,reference,baseline,output,paths):
    _,rows=audit_rows(audit)
    expected={row['relative']:row['source_hash'] for row in rows}
    renderer=poster.Renderer()
    old=legacy_renderer(baseline) if baseline else None
    ref=json.loads((reference/'github-reference-manifest.json').read_text(encoding='utf8')) if reference else dict(items=[])
    refs={(r['name'],r['style']):r for r in ref['items']}
    records=[];sections=[];control=[]
    jpg=output/'jpeg';jpg.mkdir()
    detail=output/'labels';detail.mkdir()
    for number,path in enumerate(paths,1):
        relative=path.relative_to(source).as_posix()
        assert relative in expected and poster.digest(path)==expected[relative], 'Source fixture hash differs'
        name=path.stem
        with Image.open(path) as image:
            image.load()
            result=renderer.render_independent(image,name,tuple(STYLE_FONTS),filename=name)
        assert not result['errors'],result['errors']
        cells=[]
        for style,frame in result['outputs'].items():
            label=result['labels'][style]
            filename=f'{number:02}-{style}.REVIEW-ONLY.jpg'
            frame.save(jpg/filename,'JPEG',quality=100,subsampling=0)
            box=(0,2100,2000,2780) if style=='signature' else (0,0,2000,750)
            frame.crop(box).save(detail/(filename+'.png'))
            variants=[('Inter successor / '+label['resolution_method'],jpg/filename)]
            previous=reference/f'{number:02}-{style}.DIAGNOSTIC-ONLY.jpg' if reference else None
            if previous and previous.is_file():
                target=jpg/previous.name;shutil.copyfile(previous,target)
                variants.append(('Previous strict-bypass diagnostic (Jost in diiivoy)',target))
            github=refs.get((name,style))
            if github and github.get('status')=='downloaded':
                target=jpg/Path(github['jpeg']).name
                assert poster.digest(reference/github['jpeg'])==github['sha256']
                shutil.copyfile(reference/github['jpeg'],target)
                variants.append(('Pinned GitHub reference '+github['commit'][:12],target))
            panels=[]
            for title,target in variants:
                crop=detail/(target.name+'.png')
                if not crop.exists():
                    with Image.open(target) as item:item.crop(box).save(crop)
                panels.append('<figure><figcaption>'+html.escape(title)+'</figcaption><a href="'+target.relative_to(output).as_posix()+'"><img src="'+crop.relative_to(output).as_posix()+'"></a></figure>')
            cells.append('<h3>'+style+' · '+html.escape(label['font'])+'</h3><div class="row">'+''.join(panels)+'</div>')
            records.append(dict(name=name,style=style,source=relative,source_sha256=expected[relative],
                label=label,jpeg='jpeg/'+filename,sha256=poster.digest(jpg/filename),
                size=list(frame.size),mode=frame.mode,github=github))
            frame.close()
        sections.append('<section><h2>'+html.escape(name)+'</h2>'+''.join(cells)+'</section>')
    # Supported controls prove legacy three-style outputs and COLLECTION unchanged.
    if old:
        for name in ('Valid Person','Naravit Lertratkosum','Zoë García','Zoe\u0308 Garci\u0301a'):
            image=Image.new('RGBA',(240,360));ImageDraw.Draw(image).rectangle((55,40,185,359),fill=(75,110,155,255))
            previous,_=old.render(image,name)
            current=renderer.render_independent(image,name,('bw','rainier','signature','transparent'))
            assert not current['errors']
            for style,frame in current['outputs'].items():
                equal=frame.mode==previous[style].mode and frame.tobytes()==previous[style].tobytes()
                control.append(dict(name=name,style=style,pixels_identical=equal))
                assert equal,(name,style,'Previously valid output changed')
                frame.close()
            for frame in previous.values():frame.close()
            image.close()
    dump(output/'REVIEW-ONLY.json',dict(validated=False,production_eligible=False,publication_authorized=False,
        purpose='unicode-successor-visual-review-v1',renderer=poster.renderer_fingerprint(),
        records=records,legacy_controls=control,github_reference_heads=ref.get('heads')))
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Unicode / Inter review only</title>'
        '<style>body{background:#171717;color:#eee;font:16px sans-serif;margin:24px}.row{display:flex;gap:12px}figure{margin:0;flex:1;min-width:0}img{width:100%}h3{margin-top:28px}figcaption{min-height:42px}section{border-top:2px solid #555;margin-top:32px}</style>'
        '<h1>REVIEW ONLY — Unicode / Inter Light 300</h1><p>No production receipts. No publication authorized. '
        'Click each label crop to open its full 2000 × 3000 JPEG. All four source hashes match the held snapshot. '
        'GitHub references are pinned historical evidence, not a byte-parity baseline. '
        'Inter changes only diiivoy typography. Catherine’s Signature uses display-only U+02BB → U+2019.</p>'
        +''.join(sections),encoding='utf8')
    print(json.dumps(dict(posters=len(records),legacy_control_checks=len(control),gallery=str(output/'index.html'))))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['coverage','gallery'])
    parser.add_argument('--audit',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--references',type=Path)
    parser.add_argument('--baseline',type=Path)
    args=parser.parse_args()
    reject_links(args.output)
    if args.operation=='gallery' and not args.source:parser.error('gallery requires --source')
    paths=None
    if args.operation=='gallery':
        try:paths=selected_sources(args.source)
        except ValueError as error:parser.error(str(error))
    inputs=[p.resolve() for p in (args.audit,args.source,args.references,args.baseline) if p]
    target=args.output.resolve()
    if any(target==p or p in target.parents or target in p.parents for p in inputs):parser.error('output must be disjoint from inputs')
    args.output.mkdir(parents=True,exist_ok=False)
    if args.operation=='coverage':coverage(args.audit,args.output)
    else:gallery(args.source,args.audit,args.references,args.baseline,args.output,paths)


if __name__=='__main__':main()
