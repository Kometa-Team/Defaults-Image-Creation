"""Real renderer and owned-catalog lifecycle integrity (no native/live grants)."""
import json
from pathlib import Path
import tempfile
import unittest

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
        blocked=self.app.request_removal('contributor',self.app.disposable)
        self.assertFalse(blocked['can_approve'])
        with self.assertRaisesRegex(Rejected,'required_check_failed'):
            self.app.approve('maintainer',blocked['id'],blocked['sha256'],blocked['review_digest'])
        self.app.reference('maintainer',False)
        self.assertFalse(self.app.review(self.app.submissions[blocked['id']])['can_approve'])
        removal=self.app.request_removal('contributor',self.app.disposable)
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
        removal=self.app.request_removal('contributor',self.app.disposable)
        self.app.approve('maintainer',removal['id'],removal['sha256'],removal['review_digest'])
        self.app.reference('maintainer',True)
        with self.assertRaisesRegex(Rejected,'required_check_failed'):
            self.app.stage('maintainer',removal['id'],removal['sha256'],removal['review_digest'])


if __name__=='__main__':unittest.main()
