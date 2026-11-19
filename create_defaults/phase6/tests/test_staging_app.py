import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import os

from create_defaults.phase6.staging_app import HERE, Rejected, Staging


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix='playlist-staging-test-')
        self.addCleanup(self.directory.cleanup)
        self.app=Staging(HERE/'staging_fixtures',Path(self.directory.name)/'owned')
        self.create=next(r for r in self.app.entries.values() if r['action']=='CREATE')
        self.replace=next(r for r in self.app.entries.values() if r['action']=='REPLACE')

    def submit(self,row):
        return self.app.submit('contributor',row['identity'],(self.app.fixtures/row['approved_file']).read_bytes())

    def test_ten_exact_outputs_and_seven_unchanged_historical_posters(self):
        for row in self.app.entries.values():
            item=self.submit(row)
            self.app.approve('maintainer',item['id'],item['sha256'])
            self.app.stage('maintainer',item['id'],item['sha256'])
        self.assertEqual(len(self.app.inventory()),17)
        self.assertEqual(sum(r['action']=='CREATE' and r['status']=='staged' for r in self.app.submissions.values()),8)
        self.assertEqual(sum(r['action']=='REPLACE' and r['status']=='staged' for r in self.app.submissions.values()),2)
        replacements={r['destination'] for r in self.app.entries.values() if r['action']=='REPLACE'}
        for path,checksum in self.app.baseline.items():
            if path not in replacements:
                self.assertEqual(self.app.inventory()[path],checksum)

    def test_role_separation_and_exact_render_approval(self):
        item=self.submit(self.create)
        with self.assertRaises(Rejected):self.app.approve('contributor',item['id'],item['sha256'])
        with self.assertRaises(Rejected):self.app.stage('maintainer',item['id'],item['sha256'])
        with self.assertRaises(Rejected):self.app.approve('maintainer',item['id'],'0'*64)
        self.app.approve('maintainer',item['id'],item['sha256'])
        with self.assertRaises(Rejected):self.app.stage('contributor',item['id'],item['sha256'])
        self.assertFalse((self.app.destination/self.create['destination']).exists())

    def test_changed_missing_and_replaced_preview_are_rejected(self):
        item=self.submit(self.replace)
        path=self.app.objects/(item['sha256']+'.jpg')
        raw=path.read_bytes()
        for attack in ('tampered','missing','directory'):
            with self.subTest(attack=attack):
                path.unlink()
                if attack=='tampered':path.write_bytes(raw+b'x')
                if attack=='directory':path.mkdir()
                with self.assertRaises(Rejected):self.app.approve('maintainer',item['id'],item['sha256'])
                if path.is_dir():path.rmdir()
                elif path.exists():path.unlink()
                path.write_bytes(raw)

    def test_create_collision_and_stale_replacement_fail_closed(self):
        for row in (self.create,self.replace):
            with self.subTest(action=row['action']):
                item=self.submit(row)
                self.app.approve('maintainer',item['id'],item['sha256'])
                path=self.app.destination/row['destination']
                original=path.read_bytes() if path.exists() else None
                path.write_bytes(b'foreign bytes')
                with self.assertRaises(Rejected):self.app.stage('maintainer',item['id'],item['sha256'])
                self.assertEqual(path.read_bytes(),b'foreign bytes')
                if original is None:path.unlink()
                else:path.write_bytes(original)

    def test_unknown_identity_and_wrong_jpeg_do_not_create_outputs(self):
        raw=(self.app.fixtures/self.create['approved_file']).read_bytes()
        with self.assertRaises(Rejected):self.app.submit('contributor','another.identity',raw)
        with self.assertRaises(Rejected):self.app.submit('contributor',self.create['identity'],raw+b'changed')
        self.assertFalse(self.app.submissions)

    def test_object_changed_after_approval_cannot_be_staged(self):
        item=self.submit(self.replace)
        self.app.approve('maintainer',item['id'],item['sha256'])
        path=self.app.objects/(item['sha256']+'.jpg')
        path.write_bytes(path.read_bytes()+b'changed-after-approval')
        with self.assertRaises(Rejected):self.app.stage('maintainer',item['id'],item['sha256'])
        self.assertEqual(self.app.inventory(),self.app.baseline)

    def test_existing_destination_cannot_be_adopted(self):
        with self.assertRaises(FileExistsError):Staging(HERE/'staging_fixtures',self.app.root)

    def test_windows_metadata_rename_retry_is_bounded_and_keeps_atomic_bytes(self):
        real=os.replace;calls=[]
        def transient(source,target):
            calls.append(True)
            if len(calls)==1:
                error=PermissionError('Windows sharing violation');error.winerror=5;raise error
            return real(source,target)
        with patch('create_defaults.phase6.staging_app.os.replace',side_effect=transient),patch('create_defaults.phase6.staging_app.time.sleep'):
            self.app._save('retry-probe.json',{'exact':'bytes'})
        self.assertEqual(len(calls),2)
        before=(self.app.root/'retry-probe.json').read_bytes()
        error=PermissionError('Persistent Windows denial');error.winerror=32
        with patch('create_defaults.phase6.staging_app.os.replace',side_effect=error) as replace,patch('create_defaults.phase6.staging_app.time.sleep'):
            with self.assertRaises(PermissionError):self.app._save('retry-probe.json',{'different':'bytes'})
            self.assertEqual(replace.call_count,6)
        self.assertEqual((self.app.root/'retry-probe.json').read_bytes(),before)


if __name__=='__main__':unittest.main()
