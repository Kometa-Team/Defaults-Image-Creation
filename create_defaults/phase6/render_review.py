"""Render the eight offline Playlist proposals and compare all nine baselines.

All output is a new local review directory. Shared #123456 backgrounds are
fixtures. This command creates no registry reservation, catalog write or grant.
"""
import argparse
import hashlib,importlib.util,io,json,os,subprocess,sys
from pathlib import Path
from unittest.mock import patch
import requests


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[2]
    with patch.object(requests.Session,'request',side_effect=AssertionError('Offline review forbids HTTP')):
        from PIL import Image,ImageDraw,ImageFont
        from create_defaults import create_poster as current
        from create_defaults.poster_styles import PLAYLIST
        from create_defaults.bulk.common import fingerprint
        from create_defaults.bulk.config import Config
        from create_defaults.bulk.definitions import Definition,load_definitions
        from create_defaults.bulk.planner import Planner
        from create_defaults.bulk.workers import tasks_from_manifest,compose
        from create_defaults.bulk.contracts.expanded.validation import approved_english
        from create_defaults.bulk.contracts.models import Identity
        from create_defaults.bulk.contracts.playlist.validation import PlaylistBoundary,CONTRACT_SHA256,REGISTRY_SHA256,M2_SHA256
        from create_defaults.bulk.tests.test_playlist_contract import proposed_definition
        env=dict(os.environ,GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='safe.directory',GIT_CONFIG_VALUE_0=root.as_posix())
        def git(*args):return subprocess.check_output(['git',*args],cwd=root,env=env)
        def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
        head=git('rev-parse','HEAD').decode().strip()
        from ci.phase6_playlist_maintenance import verify_checkout
        verify_checkout(expected_head=os.environ.get('EXPECTED_HEAD',head))
        assert not git('status','--porcelain').strip(), 'Commit and verify the style candidate first'
        base='dcbfa072dbedcb0069dd27be920ef3103687b5a4'
        blob=git('show',base+':create_defaults/create_poster.py')
        name='create_defaults._playlist_main_baseline'
        spec=importlib.util.spec_from_loader(name,loader=None,origin=str(current.ROOT/'create_poster.py'))
        legacy=importlib.util.module_from_spec(spec);legacy.__file__=str(current.ROOT/'create_poster.py')
        sys.modules[name]=legacy
        exec(compile(blob,str(current.ROOT/'create_poster.py'),'exec'),legacy.__dict__)
        out=args.output_dir.expanduser().absolute()
        assert not out.exists(),'Keep previous review outputs intact; choose a new revision directory'
        out.mkdir(parents=True)
        manifest=json.loads((current.ROOT/'phase6/PLAYLIST_PILOT_MANIFEST.json').read_text())
        rows=manifest['requests']
        catalog=current.ROOT/'bulk/catalog'
        historical=load_definitions([catalog/'playlist.yml'],profiles_path=catalog/'profiles.yml')
        assert len(historical)==9
        boundary=PlaylistBoundary.load(contract_sha256=CONTRACT_SHA256,registry_sha256=REGISTRY_SHA256,adoption_sha256=M2_SHA256)
        definitions=[]
        for row in rows:
            p=row['proposed'];source=dict(path='phase6/'+row['logo']['file'],sha256=row['logo']['sha256'])
            assigned=Identity.from_dict(dict(schema_version=1,kind='item-identity',id=p['persistent_identity'],
                category='Playlist',semantic_member=None,display_name=p['display_name'],rendered_caption='TIMELINE ORDER',
                source=source,local_path=p['local_path'],public_path=p['public_path']))
            content=dict(display_name=p['display_name'],source=source,background_proposal=p['fixture_background'],content_type='timeline-order')
            definition=proposed_definition(boundary,content,assigned)
            definition['output']['filename']=Path(p['public_path']).name
            definition['composer']['out_name']=Path(p['public_path']).stem
            definitions.append(Definition.create(definition))
        inputs={current.ROOT/'phase6'/r['logo']['file'] for r in rows}
        inputs|={current.ROOT/d.data['composer']['logo'] for d in historical}
        inputs|={catalog/'playlist.yml',catalog/'profiles.yml',catalog/'index-v1.json'}
        source_before={str(p):sha(p) for p in inputs}
        config=Config(offline=True,output_dir=out)
        records={}
        def legacy_bounds(parameters):
            logo=legacy.load_image(current.ROOT/parameters['logo'])
            fitted=legacy.resized_logo(logo,parameters['logo_resize'])
            bounds=fitted.getchannel('A').getbbox()
            x=(2000-fitted.width)//2;y=(3000-fitted.height)//2+parameters['logo_offset']
            return [x+bounds[0],y+bounds[1],x+bounds[2],y+bounds[3]]
        def render_set(definitions,group):
            plan=Planner(config).plan(definitions,approved_english(),categories=['Playlist'],languages=['en'])
            for job,task in zip(plan['jobs'],tasks_from_manifest(plan)):
                relative=Path(job['remote_relative'])
                before=out/group/'before'/relative;after=out/group/'after'/relative
                before.parent.mkdir(parents=True,exist_ok=True);after.parent.mkdir(parents=True,exist_ok=True)
                old=legacy.create_poster(legacy.PosterOptions(**job['parameters']),output_path=before,asset_dir=current.ROOT)
                compose(task.spec(),after,{'config':config})
                image,report=current.render_poster(current.PosterOptions(**job['parameters']),asset_dir=current.ROOT,style=job['composition_style'])
                encoded=io.BytesIO();image.save(encoded,'JPEG',quality=100,subsampling=0)
                assert encoded.getvalue()==after.read_bytes(),'Worker and direct production renderer diverge'
                assert report['caption']==old['caption'] and report['font']==old['font']
                measured=report['composition_style'];bounds=measured['logo']['visible_bounds']
                assert 200<=bounds[0]<bounds[2]<=1800 and 850<=bounds[1]<bounds[3]<=1750
                assert measured['measured_gap']>=100
                previous=legacy_bounds(job['parameters'])
                changed=before.read_bytes()!=after.read_bytes()
                reason=[]
                if old['logo_size'][1]>900:reason.append('full-canvas target-width height exceeded the new safe height')
                source=Image.open(current.ROOT/job['parameters']['logo']).convert('RGBA')
                if source.getchannel('A').getbbox()!=(0,0,*source.size):reason.append('visible-alpha bounds remove transparent padding from fitting/centering')
                if changed and not reason:reason.append('visible-alpha crop and containment resampling change edge pixels')
                if not changed:reason=['identical JPEG; source already fits at the original anchor']
                record=dict(identity=job['poster_id'],filename=relative.name,before=str(before),after=str(after),
                    before_sha256=sha(before),after_sha256=sha(after),changed=changed,
                    before_logo_size=list(old['logo_size']),after_logo_size=list(report['logo_size']),
                    before_visible_bounds=previous,after_visible_bounds=bounds,
                    logo_size_or_position_changed=previous!=bounds,reasons=reason,
                    base_color=job['parameters']['base_color'],gradient=job['parameters']['gradient'],
                    composition_style=measured,caption_unchanged=True)
                records[job['poster_id']]=record
            return plan
        pilot_plan=render_set(definitions,'pilot')
        history_plan=render_set(historical,'historical')
        assert source_before=={str(p):sha(p) for p in inputs}
        font=ImageFont.truetype(str(current.ROOT/'fonts/BebasNeue-Regular.ttf'),24)
        small=ImageFont.truetype(str(current.ROOT/'fonts/BebasNeue-Regular.ttf'),19)
        sheet=Image.new('RGB',(1600,1420),'#EEF0F3');draw=ImageDraw.Draw(sheet)
        draw.text((25,16),'OFFLINE PLAYLIST STYLE REVIEW',font=font,fill='#102030')
        draw.text((25,50),'Shared fixture background #123456 / gradient 1. Names confirmed; live identities, mappings and publication pending.',font=small,fill='#102030')
        for index,row in enumerate(rows):
            record=records[row['proposed']['persistent_identity']]
            x=(index%4)*400+20;y=100+(index//4)*650
            with Image.open(record['after']) as image:preview=image.resize((360,540),Image.Resampling.LANCZOS)
            sheet.paste(preview,(x,y))
            draw.text((x,y+548),row['proposed']['display_name'],font=font,fill='#102030')
            draw.text((x,y+579),'Timeline Order | fixture #123456',font=small,fill='#102030')
            draw.text((x,y+604),'Caption gap: '+str(record['composition_style']['measured_gap'])+' px',font=small,fill='#102030')
        sheet.save(out/'eight-poster-contact-sheet.png')
        wdu=records[rows[-1]['proposed']['persistent_identity']]
        pair=Image.new('RGB',(2080,1680),'#EEF0F3');draw=ImageDraw.Draw(pair)
        for column,key in enumerate(('before','after')):
            with Image.open(wdu[key]) as image:preview=image.resize((1000,1500),Image.Resampling.LANCZOS)
            pair.paste(preview,(20+column*1040,130))
            draw.text((20+column*1040,20),key.upper()+': The Walking Dead Universe (Timeline Order)',font=font,fill='#102030')
        draw.text((20,64),'Unchanged raw PNG and caption. After: visible-alpha contain in 1600 x 900 logo box, minimum gap 100px.',font=small,fill='#102030')
        pair.save(out/'wdu-before-after.png')
        history=[records[d.id] for d in historical]
        record=dict(kind='offline-playlist-style-artwork-review',head=head,baseline=base,
            baseline_renderer_raw_sha256=hashlib.sha256(blob).hexdigest(),
            style=PLAYLIST.__dict__,
            fixture_background='#123456',background_assignment_approved=False,
            pilot=[records[r['proposed']['persistent_identity']] for r in rows],historical=history,
            historical_changed=sum(r['changed'] for r in history),
            historical_geometry_changed=sum(r['logo_size_or_position_changed'] for r in history),
            source_and_catalog_hashes_unchanged=True,source_hashes=source_before,
            contact_sheet=str(out/'eight-poster-contact-sheet.png'),wdu_comparison=str(out/'wdu-before-after.png'),
            live_registry_reservations='PENDING',catalog_mappings='PENDING',production_authorized=False,publication_authorized=False)
        (out/'render-review.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        (out/'pilot-plan.json').write_text(json.dumps(pilot_plan,indent=2)+'\n',encoding='utf8')
        (out/'historical-plan.json').write_text(json.dumps(history_plan,indent=2)+'\n',encoding='utf8')
        print(json.dumps(dict(head=head,pilot=8,historical=9,historical_changed=record['historical_changed'],
            historical_geometry_changed=record['historical_geometry_changed'],wdu=wdu,contact_sheet=record['contact_sheet']),indent=2))

        assert git('rev-parse','HEAD').decode().strip()==head
        verify_checkout(expected_head=head)
        sys.modules.pop(name,None)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
