"""Preserve predecessor evidence and reject unlisted startup-retention changes."""
from copy import deepcopy
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ci import people_job_retention_maintenance as maintenance

ROOT = Path(__file__).resolve().parents[2]


class StartupRetentionMaintenanceTests(unittest.TestCase):
    def test_exact_successors_and_unknown_predecessors(self):
        value = maintenance.verify_checkout()
        self.assertFalse(value['publication_authorized'])
        for name, binding in value['members'].items():
            self.assertEqual(maintenance.selected_hash(name, 'f' * 64), 'f' * 64)
            if binding['before_sha256'] is not None:
                self.assertEqual(maintenance.selected_hash(name, binding['before_sha256']), binding['sha256'])
                old = maintenance.historical_bytes(ROOT, name, (ROOT / name).read_bytes())
                self.assertEqual(maintenance.sha(old), binding['before_sha256'])
                with self.assertRaises(ValueError):
                    maintenance.historical_bytes(ROOT, name, old)
        self.assertEqual(maintenance.selected_hash('unlisted.py', 'f' * 64), 'f' * 64)

    def test_every_member_rejects_tamper_rollback_and_missing_files(self):
        value = maintenance.verify_checkout()
        original = Path.read_bytes
        for name, binding in value['members'].items():
            replacements = [original(ROOT / name) + b'\nunreviewed']
            if binding['before_sha256'] is not None:
                replacements.append(maintenance._old(name))
            for replacement in replacements:
                def changed(path):
                    return replacement if path == ROOT / name else original(path)
                with self.subTest(name=name), patch.object(Path, 'read_bytes', changed), self.assertRaises(ValueError):
                    maintenance.verify_checkout()
            def missing(path):
                if path == ROOT / name:
                    raise FileNotFoundError(name)
                return original(path)
            with self.subTest(missing=name), patch.object(Path, 'read_bytes', missing), self.assertRaises(OSError):
                maintenance.verify_checkout()

    def test_manifest_rejects_resealed_hashes_membership_and_baseline(self):
        original = Path.read_bytes
        for field in ('members', 'baseline_commit', 'publication_authorized', 'pytest_ids'):
            altered = deepcopy(maintenance.manifest())
            altered[field] = 'unreviewed'
            replacement = json.dumps(altered).encode()
            def changed(path):
                return replacement if path == maintenance.MANIFEST else original(path)
            with self.subTest(field=field), patch.object(Path, 'read_bytes', changed), self.assertRaises(ValueError):
                maintenance.manifest()

    def test_each_pass_rechecks_shared_directories_without_caching_metadata(self):
        original = Path.lstat
        calls = []
        def observed(path):
            calls.append(path)
            return original(path)
        for _ in range(2):
            calls.clear()
            with patch.object(Path, 'lstat', observed):
                maintenance.verify_checkout()
            # One manifest-path check and one shared-directory check per pass.
            self.assertEqual(calls.count(ROOT), 2)
            self.assertEqual(calls.count(ROOT / 'create_people_posters'), 1)
        ancestor = ROOT / 'create_people_posters/tests'
        def linked(path):
            if path == ancestor:
                return SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_file_attributes=0)
            return original(path)
        with patch.object(Path, 'lstat', linked), self.assertRaisesRegex(ValueError, 'links or reparse'):
            maintenance.verify_checkout()

    def test_scope_rejects_unlisted_deletions_links_renames_and_incomplete_diff(self):
        with patch.object(maintenance, 'verify_checkout'):
            with self.assertRaisesRegex(ValueError, 'Unapproved startup-retention scope'):
                maintenance.verify_scope(ROOT, maintenance.BASE, {'unlisted.py'})
            name = 'create_people_posters/people_workspaces.py'
            for old, new, change in (('100644', '000000', 'D'), ('000000', '120000', 'A'),
                                     ('100644', '100644', 'R100')):
                row = (f':{old} {new} ' + '0' * 40 + ' ' + '1' * 40 + f' {change}\0{name}\0').encode()
                with patch.object(maintenance, '_git', return_value=row), self.assertRaisesRegex(ValueError, 'regular-file'):
                    maintenance.verify_scope(ROOT, maintenance.BASE, {name})
            with patch.object(maintenance, '_git', return_value=b''), self.assertRaisesRegex(ValueError, 'Incomplete'):
                maintenance.verify_scope(ROOT, maintenance.BASE, {name})

    def test_unrelated_history_is_rejected(self):
        with patch.object(maintenance, '_git', side_effect=ValueError('unrelated history')):
            with self.assertRaises(ValueError):
                maintenance._ancestry(str(ROOT), 'f' * 40)

    def test_m4_predecessor_projection_preserves_both_exact_bindings(self):
        from ci import phase5_m4_maintenance as m4
        retained = maintenance.verify_checkout()
        previous = m4.verify_checkout()
        for name in ('ci/dependabot_maintenance.py', 'ci/phase5_m3_maintenance.py'):
            current = (ROOT / name).read_bytes()
            self.assertEqual(retained['members'][name]['before_sha256'], previous['members'][name]['sha256'])
            self.assertEqual(maintenance.sha(current), retained['members'][name]['sha256'])
            projected = m4.historical_bytes(ROOT, name, current)
            self.assertEqual(m4.sha(projected), previous['members'][name]['before_sha256'])
            self.assertEqual(m4.historical_bytes(ROOT, name, projected), projected)
        for name in ('ci/phase5-m4-maintenance-v1.json', 'ci/phase5-m4-test-ids.json',
                     '.github/workflows/phase5-m4-validation.yml'):
            self.assertEqual(maintenance.sha((ROOT / name).read_bytes()), maintenance.sha(maintenance._old(name)))

    def test_original_collection_and_complete_people_namespace_remain_exact(self):
        from ci.people_security import selections
        groups, original = selections()
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'collection.json'
            def collect(paths):
                subprocess.run([sys.executable, str(ROOT / 'ci/validation.py'), 'pytest',
                                '--collect-only', '--report', str(destination), '--', *paths],
                               cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                return json.loads(destination.read_text(encoding='utf8'))['nodes']
            original_paths = sorted({n.split('::')[0] for n in original})
            self.assertEqual(set(collect(original_paths)), original)
            expected = original | set().union(*map(set, groups.values()))
            complete = collect(['create_people_posters/tests'])
            self.assertEqual(len(complete), len(set(complete)))
            self.assertEqual(set(complete), expected)
            self.assertEqual(set(collect(sorted(maintenance.TEST_MODULES))), set(maintenance.test_ids()))
