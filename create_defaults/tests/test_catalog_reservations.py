"""Persistent ownership, request replay, collision and atomic publication inputs."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch

from PIL import Image

from create_defaults.bulk.catalog_reservations import CatalogReservations, CATALOG, LEDGER, PLAYLIST, INDEX, PROFILES, git
from create_defaults.bulk.common import BulkError, Conflict, canonical
from create_defaults.bulk.library_sources import sealed

ROOT=Path(__file__).resolve().parents[2]
OWNER=dict(repository='Kometa-Team/Defaults-Image-Creation',branch='main',environment='staging')


def init_repo(path, files):
    path.mkdir();git(path,'init','-b','main')
    for key,value in {'user.name':'Staging registry tests','user.email':'staging@example.invalid','core.autocrlf':'false','core.hooksPath':str(path/'no-hooks')}.items():
        git(path,'config',key,value)
    for name,body in files.items():
        out=path/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(body)
    git(path,'add','--all');git(path,'commit','-qm','Staging baseline')
    return git(path,'rev-parse','HEAD').decode().strip()


def definition_for(title, logo, colour='#1EAC1B'):
    return dict(id='playlist.'+'1'*32,category='Playlist',display_name=title,
        source=dict(kind='authored',path='catalog/playlist.yml',line=None,row_sha256=None),
        composer=dict(base_color=colour,font='fonts/BebasNeue-Regular.ttf',font_size=154,font_color='#FFFFFF',
            logo=logo,logo_offset=-200,logo_resize=1600,out_name=title+' (Timeline Order)',
            text='',text_offset=450,avg_color=False,avg_color_image=None,dom_color=False,dom_color_image=None,
            gradient=1,white_wash=True,clean=True,border=False,border_color='#FFFFFF',border_width=15),
        caption=dict(mode='translation',key='key_names.TIMELINE_ORDER',text='',template_key=None,fallback=None,case='upper',direction='auto'),
        layout=dict(kind='fixed',measurement=None),output=dict(directory='playlist',filename=title+' (Timeline Order).jpg',remote_paths={'en':'playlist/'+title+' (Timeline Order).jpg'}),
        generator=None,languages=['en'],dependencies=[],overrides=[],
        applicability=dict(en=dict(status='applicable',reason='Approved English Playlist mapping')),
        color_assignment=dict(id='playlist.'+'1'*32+'.background',origin='independent',parent=None,relationship=None,exception=None))


def request_for(title='Registry Example', key='registry-example', logo='logos_playlist/registry-example.png'):
    body=BytesIO();Image.new('RGBA',(20,10),(255,255,255,255)).save(body,format='PNG');raw=body.getvalue()
    import hashlib
    names=dict(display_name=title,rendered_caption='TIMELINE ORDER',source=dict(path=logo,sha256=hashlib.sha256(raw).hexdigest()),
        public_path='playlist/'+title+' (Timeline Order).jpg',local_path='defaults-en/playlist/'+title+' (Timeline Order).jpg')
    return dict(category='Playlist',semantic=dict(parent=None,key=key,role='single',language='en'),variant='timeline-order',
        names=names,token='reservation-'+key,definition=definition_for(title,logo),logo=raw,approved_jpeg_sha256='a'*64)


class CatalogReservationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='catalog-reservation-tests-');self.addCleanup(self.temp.cleanup)
        folder=Path(self.temp.name);self.repo=folder/'catalog';self.destination=folder/'destination'
        files={p:(ROOT/p).read_bytes() for p in (PLAYLIST,INDEX,PROFILES)}
        self.base=init_repo(self.repo,files);self.dest_head=init_repo(self.destination,{'keep.txt':b'unchanged\n'})
        self.registry=self.open();self.registry.bootstrap_staging(expected=self.base)

    def open(self):
        return CatalogReservations(self.repo,ref='refs/heads/main',owner=OWNER,destination_root=self.destination,destination_head=self.dest_head)

    def reserve(self, **changes):
        request=request_for();request.update(changes)
        return self.registry.reserve(expected=self.registry.head(),**request)

    def test_retry_and_restart_preserve_exact_uuid_and_commit(self):
        before=self.registry.head();first=self.reserve();reopened=self.open()
        second=reopened.reserve(expected=before,**request_for())
        self.assertEqual(first['entry'],second['entry']);self.assertEqual(first['commit'],second['commit']);self.assertTrue(second['reused'])

    def test_changed_payload_cannot_reuse_token(self):
        self.reserve()
        with self.assertRaises(Conflict):self.reserve(approved_jpeg_sha256='b'*64)

    def test_semantic_collision_rejected(self):
        self.reserve();other=request_for('Other Registry Title',logo='logos_playlist/other.png');other['token']='other-request'
        with self.assertRaises(Conflict):self.registry.reserve(expected=self.registry.head(),**other)

    def test_case_folded_public_path_collision_rejected(self):
        self.reserve();other=request_for('registry example','another-semantic','logos_playlist/other.png')
        with self.assertRaises(BulkError):self.registry.reserve(expected=self.registry.head(),**other)

    def test_source_path_collision_rejected(self):
        self.reserve();other=request_for('Other Registry Title','another-semantic')
        with self.assertRaises(Conflict):self.registry.reserve(expected=self.registry.head(),**other)

    def test_unicode_source_tree_does_not_break_reservations(self):
        head=self.registry.head()
        self.registry._commit(head,{'create_defaults/logos_playlist/Pokémon.png':request_for()['logo']},'Existing Unicode source')
        self.assertFalse(self.reserve()['reused'])

    def test_historical_destination_cannot_be_reserved(self):
        with self.assertRaises(BulkError):self.registry.reserve(expected=self.registry.head(),**request_for('X-Men'))

    def test_stale_head_rejected_without_new_commit(self):
        old=self.registry.head();self.reserve();head=self.registry.head()
        with self.assertRaises(Conflict):self.registry.reserve(expected=old,**request_for('Other','other','logos_playlist/other.png'))
        self.assertEqual(head,self.registry.head())

    def test_concurrent_writers_have_one_cas_winner(self):
        barrier=Barrier(2);original=CatalogReservations._commit;expected=self.registry.head()
        def synchronized(instance,*args):barrier.wait(timeout=30);return original(instance,*args)
        def run(number):
            try:return self.open().reserve(expected=expected,**request_for('Concurrent '+str(number),'concurrent-'+str(number),'logos_playlist/concurrent-'+str(number)+'.png'))
            except Conflict:return None
        with patch.object(CatalogReservations,'_commit',synchronized),ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(run,(1,2)))
        self.assertEqual(1,sum(r is not None for r in results));self.assertEqual(1,len(self.open().state()[1]['entries']))
        winner=next(r for r in results if r is not None)
        loser=results.index(None)+1
        request=request_for('Concurrent '+str(loser),'concurrent-'+str(loser),'logos_playlist/concurrent-'+str(loser)+'.png')
        retried=self.open().reserve(expected=self.registry.head(),**request)
        head,ledger=self.open().state()
        self.assertEqual({winner['entry']['id'],retried['entry']['id']},{e['id'] for e in ledger['entries']})
        self.assertEqual(2,len(ledger['requests']))
        restarted=self.open().reserve(expected=expected,**request)
        self.assertTrue(restarted['reused']);self.assertEqual(retried['entry'],restarted['entry'])
        self.assertEqual(head,self.registry.head())

    def test_catalog_and_identity_are_committed_together(self):
        result=self.reserve();head,value=self.open().state();identity=result['entry']['id']
        self.assertEqual(head,result['commit']);self.assertIn(identity,self.open()._definitions(head))
        self.assertEqual(identity,value['requests'][0]['identity'])
        paths=git(self.repo,'diff-tree','--no-commit-id','--name-only','-r',head+'^',head).decode().splitlines()
        self.assertEqual({LEDGER,PLAYLIST,INDEX,'create_defaults/logos_playlist/registry-example.png'},set(paths))

    def test_retry_survives_a_catalog_pr_merge_commit(self):
        result=self.reserve();head=self.registry.head();tree=git(self.repo,'rev-parse',head+'^{tree}').decode().strip()
        merge=git(self.repo,'commit-tree',tree,'-p',self.base,'-p',head,data=b'Merge reviewed catalog reservation\n').decode().strip()
        git(self.repo,'update-ref','refs/heads/main',merge,head)
        retry=self.open().reserve(expected=self.base,**request_for())
        self.assertEqual(result['entry'],retry['entry']);self.assertEqual(merge,retry['commit'])

    def test_staging_owner_cannot_invoke_network_stage(self):
        with self.assertRaises(BulkError):self.registry.stage_publication(self.repo,expected=self.registry.head())

    def test_unrelated_catalog_index_addition_rejected(self):
        head,value=self.registry.state();index=json.loads(self.registry.read(head,INDEX));index['posters']['unapproved']=dict(category='Playlist',definition='unapproved',dependencies=[])
        value['parent']=head
        self.registry._commit(head,{INDEX:canonical(sealed({k:v for k,v in index.items() if k!='sha256'}))+b'\n',LEDGER:canonical(sealed({k:v for k,v in value.items() if k!='sha256'}))+b'\n'},'Negative control')
        with self.assertRaises(BulkError):self.open().state()

    def test_reservation_history_cannot_be_erased_with_catalog_rollback(self):
        self.reserve();head,value=self.registry.state();value.update(parent=head,entries=[],requests=[])
        self.registry._commit(head,{PLAYLIST:self.registry.read(self.base,PLAYLIST),INDEX:self.registry.read(self.base,INDEX),
            LEDGER:canonical(sealed({k:v for k,v in value.items() if k!='sha256'}))+b'\n'},'Negative rollback control')
        with self.assertRaises(BulkError):self.open().state()

    def test_changed_approved_jpeg_and_missing_member_rejected(self):
        result=self.reserve();fake=self.repo/'wrong.jpg';fake.write_bytes(b'not approved')
        with self.assertRaises(BulkError):self.registry.publication_inventory({result['entry']['id']:fake},expected=self.registry.head())
        with self.assertRaises(BulkError):self.registry.publication_inventory({},expected=self.registry.head())

    def test_production_owner_cannot_be_bootstrapped_by_staging(self):
        git(self.repo,'remote','add','origin','https://github.com/Kometa-Team/Defaults-Image-Creation.git')
        production=CatalogReservations(self.repo,ref='refs/heads/main',owner=dict(OWNER,environment='production'),destination_root=self.destination,destination_head=self.dest_head)
        with self.assertRaises(BulkError):production.bootstrap_staging(expected=self.registry.head())
        with self.assertRaises(BulkError):production.state()


if __name__=='__main__':unittest.main()
