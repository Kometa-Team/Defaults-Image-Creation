"""Preserve exact historical pins and reject retention scope/version drift."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ci import people_retention_maintenance as retention
from ci import people_storage_maintenance as storage

ROOT=Path(__file__).resolve().parents[2]


class PeopleRetentionMaintenanceTests(unittest.TestCase):
    def test_exact_checkout_manifest_and_reviewed_ancestry(self):
        value=retention.verify_checkout()
        self.assertEqual(value['production_successors'],[retention.WORKSPACE])
        self.assertFalse(value['publication_authorized'])

    def test_original_eight_cleanup_blobs_and_historical_manifests_stay_exact(self):
        value=storage.manifest()
        for name,binding in value['cohort'].items():
            self.assertEqual(storage.sha((ROOT/name).read_bytes()),binding['sha256'])
        for name in ['ci/people-security-maintenance.json','ci/dependency-maintenance-v1.json','ci/people-security-test-ids.json','ci/phase4-m7-test-ids.json','create_defaults/bulk/contracts/adoption/source-pins-v1.json']:
            old=subprocess.check_output(['git','show','ded9f33759f9fe3ed4ddf5f315dff01b163594ad:'+name],cwd=ROOT)
            self.assertEqual(retention.sha((ROOT/name).read_bytes()),retention.sha(old))

    def test_unknown_paths_and_unknown_predecessors_keep_original_pins(self):
        self.assertEqual(retention.selected_hash('create_defaults/create_poster.py','a'*64),'a'*64)
        self.assertEqual(retention.selected_hash(retention.WORKSPACE,'b'*64),'b'*64)
        value=retention.manifest()['members'][retention.WORKSPACE]
        self.assertEqual(retention.selected_hash(retention.WORKSPACE,value['before_sha256']),value['sha256'])

    def test_every_new_member_tamper_rollback_and_deletion_fails_closed(self):
        value=retention.manifest()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in retention.scope_members():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
            old_bytes={name:subprocess.check_output(['git','show',value['baseline_commit']+':'+name],cwd=ROOT) for name,b in value['members'].items() if b['before_sha256'] is not None}
            with patch.object(retention,'ROOT',root),patch.object(retention,'MANIFEST',root/'ci/people-retention-maintenance-v1.json'),patch.object(retention.subprocess,'check_call'),patch.object(retention.subprocess,'check_output',side_effect=lambda args,**kw:old_bytes[args[-1].split(':',1)[1]]):
                retention.verify_checkout()
                for name,binding in value['members'].items():
                    p=root/name;before=p.read_bytes()
                    p.write_bytes(before+b'\nunreviewed\n')
                    with self.subTest(name=name),self.assertRaises(ValueError):retention.verify_checkout()
                    p.unlink()
                    with self.assertRaises(OSError):retention.verify_checkout()
                    p.write_bytes(before)
                    if binding['before_sha256'] is not None:
                        p.write_bytes(old_bytes[name])
                        with self.assertRaises(ValueError):retention.verify_checkout()
                        p.write_bytes(before)

    def test_modified_manifest_cannot_refresh_approval_or_membership(self):
        value=retention.manifest()
        for field in ['members','production_successors','mandatory_unittest_ids','baseline_commit','audit_ancestor']:
            changed=deepcopy(value);changed[field]='unapproved'
            with patch.object(retention,'regular',return_value=type('P',(),{'read_bytes':lambda self:json.dumps(changed).encode()})()):
                with self.subTest(field=field),self.assertRaises(ValueError):retention.manifest()

    def test_mandatory_ids_are_exact_discovered_controls_on_both_os_jobs(self):
        import unittest as unit
        suite=unit.defaultTestLoader.discover(str(ROOT/'ci/dependency_tests'),pattern='test_people_retention*.py')
        def ids(item):
            if isinstance(item,unit.TestSuite):return [v for child in item for v in ids(child)]
            return [item.id()]
        self.assertEqual(sorted(ids(suite)),sorted(retention.test_ids()))
        self.assertGreaterEqual(len(retention.test_ids()),30)

    def test_scope_has_no_renderer_publisher_inventory_or_workflow_changes(self):
        self.assertEqual(set(storage.manifest()['cohort'])&retention.MEMBERS,set())
        for name in retention.MEMBERS:
            self.assertFalse(name.startswith('.github/'))
            self.assertNotIn(name,{'create_people_posters/poster_renderer.py','create_people_posters/publish_people_github.py'})


if __name__=='__main__':unittest.main()
