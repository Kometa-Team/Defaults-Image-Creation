"""Pin the reviewed DDColor fix without refreshing historical source inventories."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ci import people_colorize_maintenance as colorize
from ci import dependency_maintenance as dependencies

ROOT = Path(__file__).resolve().parents[2]


class PeopleColorizeMaintenanceTests(unittest.TestCase):
    def test_detached_head_is_fresh_and_git_overrides_keep_authoritative_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.git').mkdir()
            head_file = root / '.git/HEAD'
            environment = {key: value for key, value in os.environ.items()
                           if key not in {'GIT_DIR', 'GIT_COMMON_DIR', 'GIT_WORK_TREE', 'GIT_NAMESPACE'}}
            with patch.dict(os.environ, environment, clear=True):
                with patch.object(colorize, '_git', side_effect=AssertionError('Unexpected Git startup')):
                    head_file.write_text('a' * 40 + '\n')
                    self.assertEqual(colorize._head(root), 'a' * 40)
                    head_file.write_text('b' * 40 + '\n')
                    self.assertEqual(colorize._head(root), 'b' * 40)
                for setting in ('ref: refs/heads/main', 'malformed HEAD'):
                    head_file.write_text(setting)
                    with patch.object(colorize, '_git', return_value=b'c' * 40 + b'\n') as git:
                        self.assertEqual(colorize._head(root), 'c' * 40)
                        git.assert_called_once_with(root, 'rev-parse', 'HEAD')
                head_file.write_text('a' * 40)
                for key in ('GIT_DIR', 'GIT_COMMON_DIR', 'GIT_WORK_TREE', 'GIT_NAMESPACE'):
                    with patch.dict(os.environ, {key: ''}), patch.object(colorize, '_git', return_value=b'd' * 40 + b'\n') as git:
                        self.assertEqual(colorize._head(root), 'd' * 40)
                        git.assert_called_once_with(root, 'rev-parse', 'HEAD')

    def test_exact_checkout_and_known_predecessor_select_successor(self):
        value = colorize.verify_checkout()
        from ci.people_job_retention_maintenance import selected_hash, historical_bytes
        for source in colorize.PINNED:
            binding = value['members'][source]
            expected = selected_hash(source, binding['sha256'])
            self.assertEqual(dependencies.selected_hash(source, binding['before_sha256']), expected)
            current = (ROOT / source).read_bytes()
            self.assertEqual(colorize.sha(current), expected)
            self.assertEqual(colorize.sha(historical_bytes(ROOT, source, current)), binding['sha256'])
        self.assertFalse(value['publication_authorized'])

    def test_unknown_paths_and_predecessors_retain_original_pins(self):
        self.assertEqual(colorize.selected_hash('create_defaults/create_poster.py', 'a' * 64), 'a' * 64)
        self.assertEqual(colorize.selected_hash(colorize.SOURCE, 'b' * 64), 'b' * 64)

    def test_every_member_rejects_tamper_and_rollback(self):
        value = colorize.manifest()
        original = Path.read_bytes
        for name, binding in value['members'].items():
            replacements = [original(ROOT / name) + b'\nunreviewed\n']
            if binding['before_sha256'] is not None:
                replacements.append(colorize._old(str(ROOT), name))
            for replacement in replacements:
                def changed(path):
                    return replacement if path == ROOT / name else original(path)
                with self.subTest(name=name), patch.object(Path, 'read_bytes', changed):
                    with self.assertRaises(ValueError):
                        colorize.verify_checkout()

    def test_manifest_cannot_expand_scope_or_change_hashes(self):
        value = colorize.manifest()
        original = Path.read_bytes
        for field in ('members', 'baseline_commit', 'production_successors', 'publication_authorized'):
            modified = deepcopy(value)
            modified[field] = 'unreviewed'
            def changed(path):
                return json.dumps(modified).encode() if path == colorize.MANIFEST else original(path)
            with self.subTest(field=field), patch.object(Path, 'read_bytes', changed):
                with self.assertRaises(ValueError):
                    colorize.manifest()

    def test_historical_manifests_remain_exact(self):
        for name in ('ci/people-security-maintenance.json', 'ci/dependency-maintenance-v1.json',
                     'ci/people-retention-maintenance-v1.json', 'ci/people-storage-maintenance-v1.json',
                     'create_defaults/bulk/contracts/activation/data/production-pins-v1.json',
                     'create_defaults/bulk/contracts/adoption/source-pins-v1.json'):
            self.assertEqual(colorize.sha((ROOT / name).read_bytes()), colorize.sha(colorize._old(str(ROOT), name)))

    def test_scope_rejects_unknown_paths_and_nonregular_git_modes(self):
        with patch.object(colorize, 'verify_checkout'):
            with self.assertRaises(ValueError):
                colorize.verify_scope(ROOT, colorize.BASE, {'unreviewed.py'})
            for old, new, status in (('100644', '000000', 'D'), ('100644', '120000', 'M'),
                                     ('100644', '100644', 'R100')):
                raw = (f':{old} {new} ' + '0' * 40 + ' ' + '1' * 40 + f' {status}\0{colorize.SOURCE}\0').encode()
                with self.subTest(status=status), patch.object(colorize, '_git', return_value=raw):
                    with self.assertRaisesRegex(ValueError, 'regular-file'):
                        colorize.verify_scope(ROOT, colorize.BASE, {colorize.SOURCE})


if __name__ == '__main__':
    unittest.main()
