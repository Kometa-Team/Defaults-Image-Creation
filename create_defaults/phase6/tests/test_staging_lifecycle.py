"""Real renderer and owned-catalog lifecycle integrity (no native/live grants)."""
import json
import base64
import io
from pathlib import Path
import tempfile
import unittest
from PIL import Image,ImageDraw

from create_defaults.phase6.staging_app import HERE, Rejected, sha
from create_defaults.phase6.staging_lifecycle import BrowserStaging


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix='browser-lifecycle-')
        self.addCleanup(self.directory.cleanup)
        self.app=BrowserStaging(HERE/'staging_fixtures',Path(self.directory.name)/'owned')

    def generate(self, identity=None, colour=None):
        identity=identity or self.app.disposable
        row=self.app.requests[identity]
        params=row['render_request']['parameters']
        result=self.app.generate('contributor',identity,row['render_request']['composition_style'],
            params['logo'],colour or params['base_color'],params['text'])
        return self.app.submit_generated('contributor',result['id'])

    def stage(self, item):
        self.app.approve('maintainer',item['id'],item['sha256'],item['review_digest'])
        return self.app.stage('maintainer',item['id'],item['sha256'],item['review_digest'])

    def uploaded(self,colour='#2255AA'):
        image=Image.new('RGBA',(640,320),(0,0,0,0))
        draw=ImageDraw.Draw(image)
        # Playlist white-wash intentionally ignores RGB; a new logo must change alpha.
        if colour=='#AA2244':draw.ellipse((40,30,600,290),fill=colour)
        else:draw.rounded_rectangle((40,30,600,290),radius=35,fill=colour)
        encoded=io.BytesIO();image.save(encoded,'PNG')
        return base64.b64encode(encoded.getvalue()).decode()

    def generic(self, **kwargs):
        arguments=dict(intent='add',title='Unmapped browser fixture',style='playlist-contained-v1',
            upload=self.uploaded(),colour='#123456',caption='TIMELINE ORDER')
        arguments.update(kwargs)
        item=self.app.generate_request('contributor',**arguments)
        return self.app.submit_generated('contributor',item['id'])

    def test_unmapped_logo_add_then_recorded_logo_and_uploaded_logo_replacements(self):
        added=self.stage(self.generic())
        identity=added['identity'];destination=added['destination']
        settings=self.app.catalog[identity]['render_request']
        logo=settings['parameters']['logo']
        self.assertTrue(logo.startswith('uploaded:'))
        self.assertNotIn(logo,self.app.logos)
        reused=self.stage(self.generic(intent='replace',identity=identity,title='../ignored',upload=None,logo=logo))
        self.assertEqual(reused['sha256'],added['sha256'])
        different=self.stage(self.generic(intent='replace',identity=identity,upload=self.uploaded('#AA2244')))
        self.assertNotEqual(different['sha256'],reused['sha256'])
        self.assertEqual(different['identity'],identity)
        self.assertEqual(different['destination'],destination)
        self.assertEqual(different['current_preview_sha256'],reused['sha256'])

    def test_catalog_based_removal_without_legacy_render_metadata_preserves_logos(self):
        identity=next(iter(self.app.catalog))
        self.app.catalog[identity].pop('render_request')
        self.app.persist()
        # Catalog metadata is intentionally absent; removal needs only target and reason.
        snapshots={name:sha(self.app.asset(name).read_bytes()) for name in self.app.logos}
        removed=self.stage(self.app.request_removal('contributor',identity,'Retire legacy staging fixture'))
        self.assertTrue(removed['receipt']['file_absent'])
        self.assertEqual(snapshots,{name:sha(self.app.asset(name).read_bytes()) for name in snapshots})
        for reason in ('','  ','x'):
            with self.assertRaisesRegex(Rejected,'removal_reason_required'):
                self.app.request_removal('contributor',next(i for i,r in self.app.catalog.items() if r['status']=='active'),reason)

    def test_newer_replacement_invalidates_approved_removal_even_for_same_path(self):
        added=self.stage(self.generic())
        removal=self.app.request_removal('contributor',added['identity'],'Remove disposable custom fixture')
        self.app.approve('maintainer',removal['id'],removal['sha256'],removal['review_digest'])
        replacement=self.stage(self.generic(intent='replace',identity=added['identity'],upload=self.uploaded('#AA2244')))
        with self.assertRaisesRegex(Rejected,'required_check_failed'):
            self.app.stage('maintainer',removal['id'],removal['sha256'],removal['review_digest'])
        self.assertEqual(sha((self.app.destination/added['destination']).read_bytes()),replacement['sha256'])

    def test_upload_validation_and_uploaded_asset_drift(self):
        for raw in (b'not a PNG',b'',b'x'*(2*1024*1024+1)):
            with self.subTest(size=len(raw)),self.assertRaises(Rejected):
                self.generic(upload=base64.b64encode(raw).decode())
        transparent=io.BytesIO();Image.new('RGBA',(2,2),(0,0,0,0)).save(transparent,'PNG')
        with self.assertRaises(Rejected):self.generic(upload=base64.b64encode(transparent.getvalue()).decode())
        animated=io.BytesIO();Image.new('RGBA',(2,2),'red').save(animated,'PNG',save_all=True,append_images=[Image.new('RGBA',(2,2),'blue')])
        with self.assertRaises(Rejected):self.generic(upload=base64.b64encode(animated.getvalue()).decode())
        item=self.generic()
        logo=item['render']['parameters']['logo'];path=self.app.asset(logo)
        path.write_bytes(path.read_bytes()+b'changed')
        with self.assertRaisesRegex(Rejected,'uploaded_logo_changed'):
            self.app.approve('maintainer',item['id'],item['sha256'],item['review_digest'])

    def test_changed_main_replacement_needs_fresh_approval_of_new_bytes(self):
        identity=next(i for i,r in self.app.entries.items() if r['action']=='REPLACE')
        item=self.generic(intent='replace',identity=identity)
        self.assertIsNone(item['approved_sha256'])
        self.assertIsNone(item['reference_sha256'])
        self.assertEqual(item['prior_visual_reference_sha256'],self.app.entries[identity]['approved_sha256'])
        with self.assertRaisesRegex(Rejected,'exact_render_and_catalog_approval_required'):
            self.app.stage('maintainer',item['id'],item['sha256'],item['review_digest'])
        self.stage(item)

    def test_file_change_during_review_is_rejected_before_overwrite(self):
        added=self.stage(self.generic())
        item=self.generic(intent='replace',identity=added['identity'],upload=self.uploaded('#AA2244'))
        self.app.approve('maintainer',item['id'],item['sha256'],item['review_digest'])
        original=self.app.object_bytes
        target=self.app.destination/item['destination']
        def drift_during_review(submission):
            raw=original(submission)
            target.write_bytes(b'external staging drift')
            return raw
        self.app.object_bytes=drift_during_review
        with self.assertRaisesRegex(Rejected,'destination_preimage_changed'):
            self.app.stage('maintainer',item['id'],item['sha256'],item['review_digest'])
        self.assertEqual(target.read_bytes(),b'external staging drift')

    def test_restoration_keeps_exact_catalog_path_and_preserves_uploaded_logo(self):
        added=self.stage(self.generic())
        logo=added['render']['parameters']['logo'];original=self.app.asset(logo).read_bytes()
        removed=self.stage(self.app.request_removal('contributor',added['identity'],'Retire custom fixture'))
        restored=self.stage(self.generic(title='unmapped browser fixture',upload=None,logo=logo))
        self.assertEqual(restored['action'],'RESTORE')
        self.assertEqual((restored['identity'],restored['destination']),(added['identity'],added['destination']))
        self.assertTrue(removed['receipt']['file_absent'])
        self.assertEqual(self.app.asset(logo).read_bytes(),original)

    def test_unvalidated_owned_file_is_not_an_uploaded_logo(self):
        raw=b'not validated by the upload route';checksum=sha(raw)
        (self.app.uploads/(checksum+'.png')).write_bytes(raw)
        with self.assertRaisesRegex(Rejected,'unknown_uploaded_logo'):
            self.generic(upload=None,logo='uploaded:'+checksum)

    def test_failed_prewrite_guard_does_not_restore_over_an_external_change(self):
        added=self.stage(self.generic())
        item=self.generic(intent='replace',identity=added['identity'])
        self.app.approve('maintainer',item['id'],item['sha256'],item['review_digest'])
        original=self.app.guard;calls=[];target=self.app.destination/item['destination']
        def fail_prewrite():
            calls.append(True)
            if len(calls)==2:target.write_bytes(b'external staging drift')
            original()
        self.app.guard=fail_prewrite
        with self.assertRaisesRegex(Rejected,'staging_or_fixture_drift'):
            self.app.stage('maintainer',item['id'],item['sha256'],item['review_digest'])
        self.assertEqual(target.read_bytes(),b'external staging drift')

    def test_ten_generated_references_match_and_preserve_catalog_identities(self):
        for identity,row in self.app.entries.items():
            with self.subTest(title=row['display_name']):
                item=self.generate(identity)
                self.assertTrue(item['reference_match'],json.dumps(item['render']))
                result=self.stage(item)
                self.assertEqual(sha((self.app.destination/row['destination']).read_bytes()),row['approved_sha256'])
                self.assertEqual(result['receipt']['catalog_entry']['identity'],identity)
                self.assertEqual(result['receipt']['catalog_entry']['destination'],row['destination'])
        self.assertEqual(len(self.app.inventory()),17)
        for identity,before in self.app.catalog_baseline.items():
            if identity not in self.app.entries:self.assertEqual(before,self.app.catalog[identity])

    def test_wrong_reference_blocks_approval_and_does_not_inherit_visual_approval(self):
        item=self.generate(next(iter(self.app.entries)),'#123456')
        self.assertFalse(item['can_approve'])
        self.assertFalse(item['reference_match'])
        with self.assertRaisesRegex(Rejected,'required_check_failed'):
            self.app.approve('maintainer',item['id'],item['sha256'],item['review_digest'])
        self.assertEqual(self.app.inventory(),self.app.baseline)

    def test_remove_dependency_stale_approval_and_same_identity_restoration(self):
        added=self.stage(self.generate())
        replaced=self.stage(self.generate(colour='#556677'))
        self.assertNotEqual(added['sha256'],replaced['sha256'])
        self.app.reference('maintainer',True)
        blocked=self.app.request_removal('contributor',self.app.disposable,'Fixture lifecycle removal')
        self.assertFalse(blocked['can_approve'])
        with self.assertRaisesRegex(Rejected,'required_check_failed'):
            self.app.approve('maintainer',blocked['id'],blocked['sha256'],blocked['review_digest'])
        self.app.reference('maintainer',False)
        self.assertFalse(self.app.review(self.app.submissions[blocked['id']])['can_approve'])
        removal=self.app.request_removal('contributor',self.app.disposable,'Fixture lifecycle removal')
        removed=self.stage(removal)
        self.assertTrue(removed['receipt']['file_absent'])
        self.assertEqual(self.app.catalog[self.app.disposable]['status'],'retired')
        restored=self.stage(self.generate())
        self.assertEqual(restored['action'],'RESTORE')
        self.assertEqual(restored['receipt']['identity'],added['receipt']['identity'])
        self.assertEqual(restored['destination'],added['destination'])

    def test_second_existing_style_adapts_caption_requirements(self):
        item=self.generate(self.app.second)
        self.assertEqual(item['render']['style'],'franchise-legacy')
        self.assertEqual(item['render']['parameters']['text'],'')
        self.stage(item)
        row=self.app.requests[self.app.second]
        with self.assertRaisesRegex(Rejected,'selected_style_caption_requirements'):
            self.app.generate('contributor',self.app.second,'franchise-legacy',row['render_request']['parameters']['logo'],'#123456','CAPTION')

    def test_catalog_tampering_and_changed_objects_fail_closed(self):
        item=self.generate()
        original=(self.app.root/'catalog.json').read_bytes()
        (self.app.root/'catalog.json').write_bytes(b'{}')
        with self.assertRaisesRegex(Rejected,'catalog_drift'):
            self.app.approve('maintainer',item['id'],item['sha256'],item['review_digest'])
        (self.app.root/'catalog.json').write_bytes(original)
        obj=self.app.objects/(item['sha256']+'.jpg')
        obj.write_bytes(obj.read_bytes()+b'tampered')
        with self.assertRaisesRegex(Rejected,'preview_object_changed'):
            self.app.approve('maintainer',item['id'],item['sha256'],item['review_digest'])

    def test_changed_dependencies_after_approval_and_closing_failure_leave_no_partial_write(self):
        item=self.generate()
        self.app.approve('maintainer',item['id'],item['sha256'],item['review_digest'])
        calls=[]
        def closing_failure():
            calls.append(True)
            if len(calls)==2:raise Rejected('closing_source_failure')
        self.app.source_proof=closing_failure
        with self.assertRaisesRegex(Rejected,'closing_source_failure'):
            self.app.stage('maintainer',item['id'],item['sha256'],item['review_digest'])
        self.assertEqual(self.app.inventory(),self.app.baseline)
        self.assertEqual(self.app.catalog,self.app.catalog_baseline)
        self.app.guard()
        self.app.source_proof=lambda:None
        self.app.stage('maintainer',item['id'],item['sha256'],item['review_digest'])
        removal=self.app.request_removal('contributor',self.app.disposable,'Fixture lifecycle removal')
        self.app.approve('maintainer',removal['id'],removal['sha256'],removal['review_digest'])
        self.app.reference('maintainer',True)
        with self.assertRaisesRegex(Rejected,'required_check_failed'):
            self.app.stage('maintainer',removal['id'],removal['sha256'],removal['review_digest'])


if __name__=='__main__':unittest.main()
