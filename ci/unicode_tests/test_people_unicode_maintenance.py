"""Versioned CI successor controls, separate from frozen historical test IDs."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ci import phase5_m5_maintenance as m5


class UnicodeMaintenanceTests(unittest.TestCase):
    def adapter(self):
        return m5.unicode_adapter()

    def test_exact_new_cohort_and_all_retained_provenance(self):
        adapter = self.adapter()
        self.assertEqual(len(adapter.verify()), 30)
        for value in adapter.receipts():
            self.assertIs(value['ci_authorized'], False)
            self.assertIs(value['publication_authorized'], False)
        m5.verify_checkout()
        m5.collection_adapter().verify()
        m5.bulk_adapter().verify()
        from ci.people_security_maintenance import verify
        verify(ROOT)

    def test_current_m7_preservation_keeps_all_baseline_members(self):
        from ci.phase4_m7 import preservation
        report = preservation()
        self.assertEqual(report['protected_members'], 190)
        self.assertEqual(report['adoption_sources'], 299)
        self.assertEqual(report['existing_files_checked'], 2927)
        self.assertEqual(report['unexplained_differences'], 0)
        self.assertIs(report['production_activation'], False)
        self.assertIs(report['publication_authorized'], False)

    def test_every_member_tamper_delete_and_rollback_fail_after_warmup(self):
        adapter = self.adapter()
        bindings = adapter.verify()
        read = Path.read_bytes
        for name, binding in bindings.items():
            target = ROOT/name
            variants = [read(target)+b'\nunreviewed']
            if binding['before_sha256'] is not None:
                variants.append(adapter.predecessor(name))
            for raw in variants:
                with self.subTest(name=name, attack='bytes'), patch.object(Path, 'read_bytes',
                        lambda p: raw if p == target else read(p)):
                    with self.assertRaises(ValueError): adapter.verify()
            def missing(path):
                if path == target:
                    raise FileNotFoundError(name)
                return read(path)
            with self.subTest(name=name, attack='delete'), patch.object(Path, 'read_bytes', missing):
                with self.assertRaises(OSError): adapter.verify()

    def test_receipt_expansion_hash_authority_and_baseline_fail(self):
        adapter = self.adapter()
        read = Path.read_bytes
        for receipt, target in zip(adapter.receipts(), (ROOT/adapter.SOURCE, ROOT/adapter.DELIVERY)):
            for attack in ('addition', 'deletion', 'hash', 'ci', 'publication', 'baseline'):
                changed = deepcopy(receipt)
                if attack == 'addition': changed['files']['unreviewed.py'] = next(iter(changed['files'].values()))
                if attack == 'deletion': changed['files'].pop(next(iter(changed['files'])))
                if attack == 'hash': next(iter(changed['files'].values()))['sha256'] = 'f'*64
                if attack == 'ci': changed['ci_authorized'] = True
                if attack == 'publication': changed['publication_authorized'] = True
                if attack == 'baseline': changed['baseline_commit'] = 'f'*40
                raw = json.dumps(changed).encode()
                with self.subTest(receipt=target.name, attack=attack), patch.object(Path, 'read_bytes',
                        lambda p: raw if p == target else read(p)):
                    with self.assertRaises(ValueError): adapter.verify()

    def test_adapter_pin_and_retained_anchors_still_fail_closed(self):
        adapter = self.adapter()
        adapter.verify()
        from ci import people_readme_maintenance as readme
        with patch.object(readme, '_regular_files', side_effect=AssertionError('unverified helper used')):
            adapter.verify()
        read = Path.read_bytes
        for name in ('ci/people_unicode_maintenance.py', 'ci/people_collection_maintenance.py',
                     'ci/people_bulk_maintenance.py', 'ci/people_readme_maintenance.py'):
            target = ROOT/name
            with self.subTest(name=name), patch.object(Path, 'read_bytes',
                    lambda p: read(p)+b'\n# tampered' if p == target else read(p)):
                with self.assertRaises(ValueError): self.adapter().verify()
        for name in ('ci/original-test-ids.json', 'ci/people-security-test-ids.json',
                     'ci/people-collection-maintenance-v1.json', 'ci/phase5-m5-maintenance-v1.json',
                     'ci/people-bulk-maintenance-v1.json'):
            target = ROOT/name
            with self.subTest(name=name), patch.object(Path, 'read_bytes',
                    lambda p: read(p)+b'\n# tampered' if p == target else read(p)):
                with self.assertRaises((ValueError, json.JSONDecodeError)):
                    m5.bulk_adapter().verify()

    def test_scope_additions_deletions_links_renames_and_wrong_commit_fail(self):
        adapter = self.adapter()
        with self.assertRaises(ValueError): adapter.verify_scope(ROOT, adapter.M7_BASE, {'unreviewed.py'})
        with self.assertRaises(ValueError): adapter.verify_scope(ROOT, 'f'*40, set())
        with self.assertRaises(ValueError): adapter.verify(ROOT/'foreign')
        from ci import people_collection_maintenance as collection
        with patch.object(collection, '_head', return_value='f'*40):
            with self.assertRaises(ValueError): adapter.verify()
        name = 'create_people_posters/create_people_poster.py'
        git = adapter.git
        for before, after, status in (('100644', '000000', 'D'), ('100644', '120000', 'M'),
                                      ('100644', '100644', 'R100')):
            raw = (f':{before} {after} '+ '0'*40+' '+'1'*40+f' {status}\0{name}\0').encode()
            def altered(*args):
                return raw if args[0] == 'diff' else git(*args)
            with self.subTest(mode=after, status=status), patch.object(adapter, 'git', altered):
                with self.assertRaises(ValueError): adapter.verify_scope(ROOT, adapter.M7_BASE, {name})
        def committed(*args):
            return b'unreviewed committed bytes' if args[:2] == ('show', 'HEAD:'+name) else git(*args)
        with patch.object(adapter, 'git', committed):
            with self.assertRaises(ValueError): adapter.verify_scope(ROOT, adapter.M7_BASE, {name})

    def test_unknown_predecessor_or_input_gets_no_successor_authority(self):
        adapter = self.adapter()
        name = 'create_people_posters/create_people_poster.py'
        binding = adapter.verify()[name]
        self.assertEqual(adapter.selected_hash(name, binding['before_sha256']), binding['sha256'])
        self.assertEqual(adapter.selected_hash(name, 'f'*64), 'f'*64)
        self.assertEqual(adapter.selected_hash('unknown.py', 'f'*64), 'f'*64)
        self.assertEqual(adapter.historical_bytes(ROOT, name, (ROOT/name).read_bytes()), adapter.predecessor(name))
        self.assertEqual(adapter.historical_bytes(ROOT, name, b'forged'), b'forged')
        with self.assertRaises(ValueError): m5.collection_adapter().historical_bytes(ROOT, name, b'forged')

    def test_original_m5_functions_and_predecessor_pins_preserved(self):
        old = subprocess.check_output(['git', 'show', self.adapter().BASE+':ci/phase5_m5_maintenance.py'],cwd=ROOT)
        current = (ROOT/'ci/phase5_m5_maintenance.py').read_bytes()
        parse = lambda raw: {n.name:ast.dump(n) for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef)}
        before, after = parse(old), parse(current)
        changed = {'collection_adapter', 'bulk_adapter', 'historical_bytes', 'scope_members', 'verify_scope'}
        self.assertEqual({name for name in before if before[name] != after[name]}, changed)
        self.assertEqual(m5.COLLECTION_ADAPTER_SHA256, '6d858ad3f444f33da5fec7a719a5158c5d280aeda6c93f3757f6e341351b1630')
        self.assertEqual(m5.BULK_ADAPTER_SHA256, 'a8c435a6670d0e2e165569566b6bf079e1eba49a6f9e697462edcca8b880c40f')

    def test_profile_selection_is_explicit_and_rejects_new_tests(self):
        from ci.people_unicode_profile import historical_people_profile, selections
        self.assertEqual(selections(['create_people_posters\\tests']), ['create_people_posters/tests'])
        with historical_people_profile(['create_defaults/tests']) as profile:
            self.assertEqual(profile['name'], 'current-checkout')
        with self.assertRaises(ValueError):
            with historical_people_profile(['create_people_posters/unicode/tests']): pass


if __name__ == '__main__': unittest.main()
