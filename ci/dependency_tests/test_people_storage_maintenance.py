"""Narrow source transition controls, executed by mandatory dependency CI on both OSes."""
from copy import deepcopy
import json
from pathlib import Path
import stat
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ci import people_storage_maintenance as storage
from ci import dependency_maintenance as dependency
from ci import people_security_maintenance as people

ROOT = Path(__file__).resolve().parents[2]


class PeopleStorageMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.value = storage.manifest()

    def materialize(self, root, active):
        for name, binding in self.value['cohort'].items():
            commit = self.value['source_commit'] if active else self.value['baseline_commit']
            if binding['sha256' if active else 'before_sha256'] is not None:
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(storage.git_bytes(str(ROOT), commit, name))

    def test_historical_manifests_membership_and_exact_reviewed_eight_file_cohort(self):
        self.assertEqual(self.value['production_members'], [storage.SOURCE])
        self.assertEqual(set(self.value['cohort']), storage.COHORT)
        changed = subprocess.check_output(['git', 'diff', '--name-only',
            self.value['source_base_commit'], self.value['source_commit']], cwd=ROOT, text=True).splitlines()
        self.assertEqual(set(changed), storage.COHORT)
        for name, binding in self.value['cohort'].items():
            for field, commit in (('before_sha256', self.value['baseline_commit']),
                                  ('sha256', self.value['source_commit'])):
                if binding[field] is not None:
                    self.assertEqual(storage.sha(storage.git_bytes(str(ROOT), commit, name)), binding[field])
        for name in ('ci/people-security-maintenance.json', 'ci/dependency-maintenance-v1.json',
                     people.PINS, 'create_defaults/bulk/contracts/adoption/source-pins-v1.json',
                     'ci/people-security-test-ids.json', 'ci/phase4-m7-test-ids.json'):
            self.assertEqual(storage.sha((ROOT/name).read_bytes()),
                storage.sha(storage.git_bytes(str(ROOT), self.value['baseline_commit'], name)))
        protected = json.loads((ROOT/people.PINS).read_bytes())['files']
        adopted = json.loads((ROOT/'create_defaults/bulk/contracts/adoption/source-pins-v1.json').read_bytes())['files']
        self.assertEqual(len(protected), 190)
        self.assertEqual(len(adopted), 299)
        self.assertEqual(set(protected)&storage.COHORT, {storage.SOURCE})

    def test_real_git_ancestry_selects_old_until_source_commit_is_integrated(self):
        self.assertFalse(storage._integrated(str(ROOT), self.value['source_commit'], self.value['baseline_commit']))
        self.assertTrue(storage._integrated(str(ROOT), self.value['source_commit'], self.value['source_commit']))
        with self.assertRaises(subprocess.CalledProcessError):
            storage._integrated(str(ROOT), 'f'*40, self.value['baseline_commit'])

    def test_both_complete_cohorts_pass_and_crlf_normalization_is_preserved(self):
        for active in (False, True):
            with self.subTest(active=active), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.materialize(root, active)
                with patch.object(storage, 'integrated', return_value=active):
                    self.assertEqual(storage.verify_cohort(root, self.value), active)
                    target = root/storage.SOURCE
                    target.write_bytes(target.read_bytes().replace(b'\n', b'\r\n'))
                    self.assertEqual(storage.verify_cohort(root, self.value), active)

    def test_unknown_successor_and_deletion_of_every_required_cohort_file_are_rejected(self):
        for active in (False, True):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.materialize(root, active)
                for name, binding in self.value['cohort'].items():
                    if binding['sha256' if active else 'before_sha256'] is None:
                        continue
                    path = root/name
                    before = path.read_bytes()
                    with self.subTest(active=active, name=name), patch.object(storage, 'integrated', return_value=active):
                        path.write_bytes(before+b'\nunreviewed successor\n')
                        with self.assertRaises(ValueError): storage.verify_cohort(root, self.value)
                        path.unlink()  # test-owned temporary fixture only
                        with self.assertRaises(OSError): storage.verify_cohort(root, self.value)
                    path.write_bytes(before)

    def test_integrated_rollback_and_mixed_versions_fail_even_with_known_old_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.materialize(root, True)
            for name, binding in self.value['cohort'].items():
                if binding['before_sha256'] is None:
                    continue
                path = root/name
                after = path.read_bytes()
                path.write_bytes(storage.git_bytes(str(ROOT), self.value['baseline_commit'], name))
                with self.subTest(name=name), patch.object(storage, 'integrated', return_value=True):
                    with self.assertRaises(ValueError): storage.verify_cohort(root, self.value)
                path.write_bytes(after)
            # Full rollback is also rejected, rather than allowing either hash.
            with tempfile.TemporaryDirectory() as old:
                self.materialize(Path(old), False)
                with patch.object(storage, 'integrated', return_value=True):
                    with self.assertRaises((ValueError, OSError)): storage.verify_cohort(Path(old), self.value)

    def test_preintegration_rejects_early_successor_additions_including_dangling_entries(self):
        for kind in ('file', 'directory'):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.materialize(root, False)
                name = next(n for n,b in self.value['cohort'].items() if b['before_sha256'] is None)
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.mkdir() if kind == 'directory' else path.write_bytes(b'unreviewed')
                with patch.object(storage, 'integrated', return_value=False):
                    with self.assertRaises(ValueError): storage.verify_cohort(root, self.value)

    def test_every_cohort_file_and_parent_link_or_reparse_is_rejected(self):
        real = Path.lstat
        for parent, reparse in ((False, False), (True, False), (False, True), (True, True)):
            target = ROOT/storage.SOURCE
            if parent: target = target.parent
            def altered(path, *args, **kwargs):
                info = real(path, *args, **kwargs)
                return SimpleNamespace(st_mode=info.st_mode if reparse else stat.S_IFLNK,
                    st_file_attributes=0x400 if reparse else 0) if path == target else info
            with self.subTest(parent=parent, reparse=reparse), patch.object(Path, 'lstat', altered):
                with self.assertRaisesRegex(ValueError, 'links or reparse'):
                    storage.regular(ROOT, storage.SOURCE)

    def test_unknown_paths_and_unknown_predecessors_cannot_acquire_authority(self):
        before = self.value['cohort'][storage.SOURCE]['before_sha256']
        for name in ('create_defaults/create_poster.py', '../'+storage.SOURCE,
                     '.github/workflows/default-poster-validation.yml'):
            self.assertEqual(storage.selected_hash(name, before), before)
        self.assertEqual(storage.selected_hash(storage.SOURCE, 'f'*64), 'f'*64)

    def test_missing_tampered_manifest_and_cache_replacement_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root/'transition.json'
            with patch.object(storage, 'ROOT', root), patch.object(storage, 'MANIFEST', path):
                with self.assertRaises(OSError): storage.manifest()
                path.write_text(json.dumps(self.value), encoding='utf8')
                storage.manifest()
                for field in ('source_commit', 'baseline_commit', 'cohort', 'production_members', 'storage_test_ids'):
                    value = deepcopy(self.value)
                    value[field] = 'tampered'
                    path.write_text(json.dumps(value), encoding='utf8')
                    with self.subTest(field=field), self.assertRaises(ValueError): storage.manifest()

    def test_exact_current_guards_pass_and_historical_projection_rejects_drift(self):
        storage.verify(ROOT)
        people.verify(ROOT)
        dependency.verify_infrastructure(ROOT)
        from create_defaults.bulk.contracts.activation.protection import verify
        from create_defaults.bulk.contracts.adoption.sources import verify_sources, load_pins
        self.assertEqual(verify(root=ROOT)['production_files_verified'], 190)
        verify_sources(load_pins(), ROOT)
        for name, binding in self.value['infrastructure'].items():
            current = (ROOT/name).read_bytes()
            before = storage.historical_bytes(ROOT, name, current)
            self.assertEqual(storage.sha(before), binding['before_sha256'])
            for bad in (current+b'\ndrift', before):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    storage.historical_bytes(ROOT, name, bad)
        self.assertEqual(storage.historical_bytes(ROOT, 'ci/evidence/before.json', b'history'), b'history')

    def test_every_infrastructure_change_is_rejected_by_people_and_m7(self):
        original = Path.read_bytes
        for name in storage.INFRASTRUCTURE:
            def changed(path):
                raw = original(path)
                return raw+b'\nunapproved infrastructure' if path == ROOT/name else raw
            with self.subTest(name=name), patch.object(Path, 'read_bytes', changed):
                with self.assertRaises(ValueError): people.verify(ROOT)
                from ci.phase4_m7 import preservation
                with self.assertRaises(ValueError): preservation()

    def test_partial_historical_fixture_cannot_bypass_actual_checkout_cohort_checks(self):
        original = Path.read_bytes
        def changed(path):
            raw = original(path)
            return raw+b'\nunreviewed source' if path == ROOT/storage.SOURCE else raw
        with tempfile.TemporaryDirectory() as folder, patch.object(Path, 'read_bytes', changed):
            with self.assertRaisesRegex(ValueError, 'mixed People storage cohort'):
                people.verify(Path(folder))

    def test_all_forty_storage_ids_have_one_executor_and_historical_ids_remain_unchanged(self):
        from ci.people_security import selections
        groups, original = selections()
        frozen = json.loads((ROOT/'ci/people-security-test-ids.json').read_bytes())
        active = storage.integrated(ROOT, self.value)
        ids = self.value['storage_test_ids']
        self.assertEqual(len(ids), 40)
        self.assertEqual(len(set(ids)), 40)
        self.assertTrue(all(n.startswith('create_people_posters/tests/test_people_recovery_storage.py::') for n in ids))
        from ci.people_readme_maintenance import test_ids
        self.assertEqual(groups['compatibility'], frozen['compatibility']+(ids+test_ids() if active else []))
        self.assertFalse(set(ids)&(original | set().union(*map(set, frozen.values()))))

    def test_m7_preserves_all_2927_original_files_and_rejects_unapproved_scope(self):
        from ci.phase4_m7 import preservation
        report = preservation()
        self.assertEqual(report['existing_files_checked'], 2927)
        self.assertEqual(report['unexplained_differences'], 0)
        with self.assertRaises(ValueError): storage.verify_scope(ROOT, self.value['baseline_commit'], {'unauthorized.yml'})

    def test_m7_rejects_unauthorized_yaml_source_historical_and_inventory_drift(self):
        from ci.phase4_m7 import preservation
        original = Path.read_bytes
        for name in ('create_defaults/create_poster.py',
                     '.github/workflows/default-poster-validation.yml',
                     'ci/evidence/before.json', people.PINS,
                     'create_defaults/bulk/contracts/adoption/source-pins-v1.json'):
            def changed(path):
                raw = original(path)
                return raw+b'\nunapproved drift' if path == ROOT/name else raw
            with self.subTest(name=name), patch.object(Path, 'read_bytes', changed):
                with self.assertRaises((ValueError, OSError)): preservation()

    def test_scope_rejects_authorized_path_deletion_rename_and_git_symlink_modes(self):
        name = storage.SOURCE
        for old, new, status in (('100644', '000000', 'D'), ('100644', '120000', 'M'),
                                  ('000000', '100644', 'A'), ('100644', '100644', 'R100')):
            raw = (f':{old} {new} '+ '0'*40+' '+'1'*40+f' {status}\0{name}\0').encode()
            with self.subTest(status=status, mode=new), patch.object(storage, 'verify'), \
                    patch.object(storage.subprocess, 'check_output', return_value=raw):
                with self.assertRaisesRegex(ValueError, 'regular-file'):
                    storage.verify_scope(ROOT, self.value['baseline_commit'], {name})
