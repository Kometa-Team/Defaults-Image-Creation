"""Synthetic M3 pixels, native plans and real isolated durable receipts."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import PurePosixPath
from unittest.mock import patch
from uuid import UUID

from PIL import Image,ImageDraw
import yaml

from create_defaults.bulk.common import canonical
from create_defaults.bulk.contracts.models import Identity,ExceptionRequest
from create_defaults.bulk.contracts.playlist import PlaylistBoundary
from create_defaults.bulk.contracts.playlist.validation import CONTRACT_SHA256,REGISTRY_SHA256,M2_SHA256
from create_defaults.bulk.lifecycle.basis import historical_basis
from create_defaults.bulk.lifecycle.identities import IdentityRegistry
from create_defaults.bulk.lifecycle.candidates import poster_candidate
from create_defaults.bulk.lifecycle.overlay_candidates import overlay_candidate
from create_defaults.bulk.lifecycle.impact import request_record,operation_head,analyze
from create_defaults.bulk.lifecycle.composition import CompositionContext,exception_context
from create_defaults.phase3.tests.destination_samples import inventory,USER


def png(*,opaque=False,white=False):
    image=Image.new('RGBA',(400,200),(0,0,0,255 if opaque else 0));draw=ImageDraw.Draw(image)
    draw.rectangle((40,40,175,160),fill=(230,45,70,255));draw.ellipse((210,40,355,160),fill=(20,170,240,255))
    draw.rectangle((80,75,130,120),fill=(0,0,0,0));out=BytesIO();image.save(out,format='PNG');return out.getvalue()


def registry(trial):
    inv=inventory(USER,'Main',{})
    return IdentityRegistry.create(trial.config.cache_dir,'synthetic-composition',inventory=inv,expected_inventory_sha256=inv.sha256)


def allocate(r,*,category,variant,names,key,role='single',parent=None):
    # Fixed UUIDs are confined to synthetic tests, for meaningful cross-platform
    # output/manifest comparison. Never derived from real filenames.
    count=len(r.view().entries())+1
    with patch('create_defaults.bulk.lifecycle.identities.uuid4',return_value=UUID(f'{count:08x}-1111-4111-8111-111111111111')):
        return r.allocate(category=category,semantic=dict(parent=parent,key=key,role=role,language='en'),variant=variant,names=names,token=key+'-'+role,expected=r.view().head)


def context(candidate):
    r=candidate.registry;record=request_record(r,None,candidate,identity='synthetic.operation.composition',operation='ADD')
    r.operations.append(record,expected_revision=0,expected_sha256=None,expected_event_sha256=None)
    head=operation_head(r.operations,record.to_dict()['id']);impact=analyze(r,None,candidate,operation=head,expected_operation_sha256=head.sha256)
    return CompositionContext(r,None,candidate,impact,impact.sha256)


def poster(trial,category='Playlist',*,paired=False):
    r=registry(trial);definitions=[];content={};basis=historical_basis()
    if category=='Playlist':
        from create_defaults.bulk.tests.test_playlist_contract import proposed_definition
        boundary=PlaylistBoundary.load(contract_sha256=CONTRACT_SHA256,registry_sha256=REGISTRY_SHA256,adoption_sha256=M2_SHA256)
        source=trial.stage('logos_playlist/Fixture Brand.png',png())
        n=dict(display_name='Fixture Brand',rendered_caption='TIMELINE ORDER',source=source,local_path='defaults-en/playlist/Fixture Brand (Timeline Order).jpg',public_path='playlist/Fixture Brand (Timeline Order).jpg')
        e=allocate(r,category=category,variant='timeline-order',names=n,key='fixture')
        identity=Identity.from_dict(dict(schema_version=1,kind='item-identity',id=e['id'],category=category,semantic_member=None,**n))
        c=dict(display_name=n['display_name'],source=source,background_proposal='#123456',content_type='timeline-order')
        d=proposed_definition(boundary,c,identity)
        d['output']['filename']='Fixture Brand (Timeline Order).jpg';d['composer']['out_name']='Fixture Brand (Timeline Order)'
        definitions=[d];content[e['id']]=c
    else:
        package=basis.package(category);rules,members=package.data()
        variant=next(v for v in sorted(rules) if rules[v]['required_presentations']==(['white','color'] if paired else ['single']) and rules[v]['source_kind']=='logo')
        old=next(i for i,m in members.items() if m['variant']==variant)
        originals=[old,*members[old]['companions']] if paired else [old]
        parent=None
        if paired:
            container=allocate(r,category=category,variant=None,names=dict(display_name='Fixture Group',rendered_caption='',source=None,local_path=None,public_path=None),key='fixture-group',role='group')
            parent=container['id']
        for old in originals:
            a=members[old];d=basis.resolution.definition(old);n=deepcopy(basis.entry(old)['names'])
            raw=png()
            if a['presentation']=='white':
                image=Image.open(BytesIO(raw));alpha=image.getchannel('A');image=Image.new('RGBA',image.size,'white');image.putalpha(alpha)
                buffer=BytesIO();image.save(buffer,format='PNG');raw=buffer.getvalue()
            source=trial.stage(str(PurePosixPath(n['source']['path']).parent)+'/Fixture '+a['presentation']+'.png',raw)
            n.update(display_name='Fixture '+category,source=source,local_path=str(PurePosixPath(n['local_path']).parent)+'/Fixture.jpg',public_path=str(PurePosixPath(n['public_path']).parent)+'/Fixture.jpg')
            selected=a['variant'];rule=rules[selected]
            e=allocate(r,category=category,variant=selected,names=n,key='fixture',role=a['presentation'],parent=parent)
            d.update(id=e['id'],display_name=n['display_name'],generator=None,dependencies=[])
            d['output'].update(filename='Fixture.jpg',remote_paths={'en':n['public_path']})
            d['composer'].update(out_name='Fixture',logo=source['path'])
            if category=='Genre':d['composer']['white_wash']=True
            c=dict(display_name=n['display_name'],source=source)
            exemplar=next(i for i,m in members.items() if m['variant']==selected)
            d['composer']['base_color']=basis.resolution.definition(exemplar)['composer']['base_color']
            captions=json.loads(rule['caption_types_json'])
            c['content_type']=next(k for k,t in captions.items() if json.loads(t['definition_json'])==d['caption'] and t['text']==n['rendered_caption'])
            content[e['id']]=c;definitions.append(d)
    path=trial.root/'candidate.yml';profiles=trial.root/'profiles.yml'
    path.write_text(yaml.safe_dump(dict(schema_version=1,category=category,definitions=definitions)),encoding='utf8')
    profiles.write_text(yaml.safe_dump(dict(schema_version=1,profiles={})),encoding='utf8')
    candidate=poster_candidate(r,expected=r.view().head,paths=[path],profiles_path=profiles,posters=sorted(content),content=content,config=trial.config)
    return context(candidate)


def overlays(trial):
    r=registry(trial);b=historical_basis();rules,members=b.package('Overlays').data();variant=next(iter(rules))
    old=next(i for i,m in members.items() if m['variant']==variant)
    container=allocate(r,category='Overlays',variant=None,names=dict(display_name='Fixture Overlay',rendered_caption='',source=None,local_path=None,public_path=None),key='fixture-group',role='group')
    source=trial.stage(rules[variant]['source_roots'][0]+'/Fixture Mixed Case.png',png());ids=[]
    for original in [old,*members[old]['companions']]:
        n=deepcopy(b.entry(original)['names']);role=b.entry(original)['semantic']['role']
        for field in ('local_path','public_path'):n[field]=str(PurePosixPath(n[field]).parent)+'/Fixture Mixed Case.png'
        n.update(display_name='Fixture Overlay',source=source)
        ids.append(allocate(r,category='Overlays',variant=variant,names=n,key='fixture',role=role,parent=container['id'])['id'])
    candidate=overlay_candidate(r,expected=r.view().head,identities=ids,config=trial.config)
    return context(candidate)


def exception(candidate):
    i=sorted(candidate.graph.index().outputs)[0]
    return ExceptionRequest.from_dict(dict(schema_version=1,kind='logo-exception-request',id='synthetic.exception.logo',revision=1,
        provenance=dict(role='submitter',actor='synthetic-maintainer',source='fixture',evidence_sha256='a'*64),
        context=exception_context(candidate,i),requested_treatment='SOURCE_PRESERVING',intentional_background=False,
        justification='Compare source-preserving brand colours with the category white default.'))


def family(trial):
    """Real registered separator generator, new stable semantic child identity."""
    from create_defaults.bulk.lifecycle.candidates import StablePlanner
    from create_defaults.bulk.definitions import Definition
    r=registry(trial);b=historical_basis();resolution=b.resolution.data();package=b.package('Separators');rules,members=package.data()
    parent=next(p for p,definition in resolution['declared'].items() if definition['category']=='Separators' and definition['generator'] is not None)
    d=deepcopy(resolution['declared'][parent]);old=resolution['families'][parent][0];variant=members[old]['variant']
    family_entry=allocate(r,category='Separators',variant=None,names=dict(display_name='Fixture Family',rendered_caption='',source=None,local_path=None,public_path=None),key='fixture-family',role='family')
    d['id']=family_entry['id'];d['generator']['parameters']['filename']='Fixture Collections.jpg'
    d['generator']['parameters']['variants']=d['generator']['parameters']['variants'][:1]
    item=d['generator']['parameters']['variants'][0]
    # M2's assigned background is the captured cohort template, not an editable
    # submitter field. Use that actual template's first colour.
    exemplar=next(i for i,m in members.items() if m['variant']==variant)
    d['generator']['parameters']['variants'][0]['base_color']=b.resolution.definition(exemplar)['composer']['base_color']
    source=trial.stage('@base/'+item['name']+'.png',png())
    n=dict(display_name='Fixture Collections',rendered_caption=b.entry(old)['names']['rendered_caption'],source=source,
        local_path='defaults-en/separators/'+item['name']+'/Fixture Collections.jpg',public_path='separators/'+item['name']+'/Fixture Collections.jpg')
    e=allocate(r,category='Separators',variant=variant,names=n,key='separator:'+item['name'],role='single',parent=family_entry['id'])
    rule=rules[variant];captions=json.loads(rule['caption_types_json'])
    c=dict(display_name=n['display_name'],content_type=next(k for k,t in captions.items() if json.loads(t['definition_json'])==d['caption']))
    path=trial.root/'candidate.yml';profiles=trial.root/'profiles.yml'
    path.write_text(yaml.safe_dump(dict(schema_version=1,category='Separators',definitions=[d])),encoding='utf8')
    profiles.write_text(yaml.safe_dump(dict(schema_version=1,profiles={})),encoding='utf8')
    candidate=poster_candidate(r,expected=r.view().head,paths=[path],profiles_path=profiles,posters=[e['id']],content={e['id']:c},config=trial.config)
    return context(candidate)
