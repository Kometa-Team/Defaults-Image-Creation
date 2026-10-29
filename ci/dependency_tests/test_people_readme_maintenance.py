"""Exact README publication transition and unchanged historical controls."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ci import people_readme_maintenance as readme

ROOT = Path(__file__).resolve().parents[2]


class PeopleReadmeMaintenanceTests(unittest.TestCase):
    def test_exact_checkout_and_known_predecessors(self):
        value = readme.verify_checkout()
        for name, binding in value['members'].items():
            if binding['before_sha256'] is not None:
                from ci.dependabot_maintenance import selected_hash
                self.assertEqual(readme.selected_hash(name, binding['before_sha256']), selected_hash(name, binding['sha256']))
            self.assertEqual(readme.selected_hash(name, 'f' * 64), 'f' * 64)
        self.assertEqual(readme.selected_hash('unreviewed.py', 'f' * 64), 'f' * 64)
        self.assertFalse(value['publication_authorized'])

    def test_each_member_rejects_tamper_rollback_and_missing_bytes(self):
        original = Path.read_bytes
        for name, binding in readme.manifest()['members'].items():
            replacements = [original(ROOT / name) + b'\nunreviewed\n']
            if binding['before_sha256'] is not None:
                replacements.append(readme._old(name))
            for replacement in replacements:
                def changed(path):
                    return replacement if path == ROOT / name else original(path)
                with self.subTest(name=name), patch.object(Path, 'read_bytes', changed):
                    with self.assertRaises(ValueError):
                        readme.verify_checkout()
            def missing(path):
                if path == ROOT / name:
                    raise FileNotFoundError(name)
                return original(path)
            with self.subTest(missing=name), patch.object(Path, 'read_bytes', missing):
                with self.assertRaises(OSError):
                    readme.verify_checkout()

    def test_manifest_cannot_refresh_membership_or_predecessors(self):
        value, original = readme.manifest(), Path.read_bytes
        for field in ('members', 'baseline_commit', 'publication_authorized'):
            modified = deepcopy(value)
            modified[field] = 'unreviewed'
            def changed(path):
                return json.dumps(modified).encode() if path == readme.MANIFEST else original(path)
            with self.subTest(field=field), patch.object(Path, 'read_bytes', changed):
                with self.assertRaises(ValueError):
                    readme.manifest()

    def test_cached_manifest_rejects_equal_length_replacement(self):
        value = readme.manifest()
        raw = readme.MANIFEST.read_bytes()
        binding = next(iter(value['members'].values()))['sha256'].encode()
        changed_raw = raw.replace(binding, b'0' * 64, 1)
        self.assertEqual(len(changed_raw), len(raw))
        self.assertNotEqual(changed_raw, raw)
        original = Path.read_bytes
        def changed(path):
            return changed_raw if path == readme.MANIFEST else original(path)
        with patch.object(Path, 'read_bytes', changed):
            with self.assertRaises(ValueError):
                readme.manifest()
        self.assertEqual(readme.manifest(), value)

    def test_shared_parent_checks_are_fresh_and_reject_reparse_points(self):
        names = readme.MEMBERS | readme.ANCHORS
        readme._regular_files(ROOT, names)
        original = Path.lstat
        for target in (ROOT, ROOT / 'ci', ROOT / 'create_people_posters',
                       ROOT / 'create_people_posters/publish_people_github.py'):
            def changed(path):
                info = original(path)
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400) if path == target else info
            with self.subTest(target=target), patch.object(Path, 'lstat', changed):
                with self.assertRaisesRegex(ValueError, 'reparse'):
                    readme._regular_files(ROOT, names)
        with self.assertRaisesRegex(ValueError, 'escaped'):
            readme._regular_files(ROOT, {'../outside.py'})
        with self.assertRaisesRegex(ValueError, 'regular file'):
            readme._regular_files(ROOT, {'ci'})

    def test_storage_and_retention_ancestry_follow_changed_heads(self):
        from ci import people_storage_maintenance as storage, people_retention_maintenance as retention
        heads = ['a' * 40, 'b' * 40]
        with patch('ci.people_colorize_maintenance._head', side_effect=heads), \
                patch.object(storage, '_integrated', return_value=True) as integrated:
            for _ in heads:
                self.assertTrue(storage.integrated(ROOT, {'source_commit': readme.BASE}))
            self.assertEqual([call.args[-1] for call in integrated.call_args_list], heads)
        retention._ancestry.cache_clear()
        try:
            with patch.object(retention.subprocess, 'check_call') as git:
                for head in (heads[0], heads[0], heads[1]):
                    retention._ancestry(str(ROOT), readme.BASE, head)
                self.assertEqual([call.args[0][-1] for call in git.call_args_list], heads)
            with patch.object(retention.subprocess, 'check_call', side_effect=subprocess.CalledProcessError(1, 'git')):
                for _ in range(2):
                    with self.assertRaises(subprocess.CalledProcessError):
                        retention._ancestry(str(ROOT), readme.BASE, 'c' * 40)
        finally:
            retention._ancestry.cache_clear()

    def test_historical_projection_is_exact_and_rejects_rollback(self):
        for name, binding in readme.manifest()['members'].items():
            if binding['before_sha256'] is None:
                continue
            current = (ROOT / name).read_bytes()
            old = readme.historical_bytes(ROOT, name, current)
            self.assertEqual(readme.sha(old), binding['before_sha256'])
            for bad in (current + b'\nunreviewed', old):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    readme.historical_bytes(ROOT, name, bad)

    def test_historical_manifests_and_test_selections_remain_exact(self):
        for name in ('ci/people-security-maintenance.json', 'ci/dependency-maintenance-v1.json',
                     'ci/people-retention-maintenance-v1.json', 'ci/people-storage-maintenance-v1.json',
                     'ci/people-colorize-maintenance-v1.json', 'ci/people-security-test-ids.json',
                     'ci/phase4-m7-test-ids.json',
                     'create_defaults/bulk/contracts/activation/data/production-pins-v1.json',
                     'create_defaults/bulk/contracts/adoption/source-pins-v1.json'):
            old = subprocess.check_output(['git', 'show', readme.BASE + ':' + name], cwd=ROOT)
            self.assertEqual(readme.sha((ROOT / name).read_bytes()), readme.sha(old))

    def test_scope_rejects_unknown_paths_and_nonregular_modes(self):
        name = 'create_people_posters/publish_people_github.py'
        with patch.object(readme, 'verify_checkout'):
            with self.assertRaises(ValueError):
                readme.verify_scope(ROOT, readme.BASE, {'unreviewed.py'})
            for old, new, status in (('100644', '000000', 'D'), ('100644', '120000', 'M'),
                                     ('100644', '100644', 'R100')):
                raw = (f':{old} {new} ' + '0' * 40 + ' ' + '1' * 40 + f' {status}\0{name}\0').encode()
                with self.subTest(status=status), patch.object(readme, '_git', return_value=raw):
                    with self.assertRaisesRegex(ValueError, 'regular-file'):
                        readme.verify_scope(ROOT, readme.BASE, {name})

    def test_incomplete_readmes_cannot_grant_cleanup(self):
        from ci.dependency_tests.test_people_retention import PeopleRetentionTests
        from create_people_posters.people_retention_state import RetentionBlocked
        from create_people_posters.people_github import REPOSITORIES
        case = PeopleRetentionTests('test_exact_publication_and_all_seven_success_receipts_are_required')
        case.setUp()
        try:
            for status in ('dispatched', 'warning', 'unchanged', 'failed', 'waiting'):
                case.db.execute('UPDATE readmes SET status=? WHERE repo=?', (status, REPOSITORIES['bw']))
                case.db.commit()
                with self.subTest(status=status), self.assertRaises(RetentionBlocked):
                    case.plan()
            case.db.execute("UPDATE readmes SET status='verified'")
            case.db.commit()
            self.assertEqual(case.plan()['eligible_files'], 8)
        finally:
            case.doCleanups()
