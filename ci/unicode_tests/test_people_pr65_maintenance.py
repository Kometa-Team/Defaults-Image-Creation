"""Exact PR #65 dependency successor; retained Unicode receipts stay sealed."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from ci import phase5_m6_maintenance as owner
from ci import phase5_m5_maintenance as m5

ROOT = owner.ROOT
NAME = owner.PEOPLE_PR65_REQUIREMENTS


class PeoplePR65Tests(unittest.TestCase):
    def test_actual_unicode_requirements_guard(self):
        adapter = m5.unicode_adapter()
        bindings = adapter.verify(ROOT)
        self.assertEqual(len(bindings), 41)
        self.assertEqual(bindings[NAME]['sha256'], owner.PEOPLE_PR65_BEFORE[NAME])
        self.assertEqual(owner.sha((ROOT/NAME).read_bytes()), owner.people_pr65_bindings()[NAME]['sha256'])
        self.assertIn(b'Pillow==13.0.0', (ROOT/NAME).read_bytes())
        self.assertIn(b'Pillow==12.0.0', owner._people_pr65_before(NAME))

    def test_post_warmup_tamper_rollback_and_missing_rejected(self):
        bindings = owner.people_pr65_bindings()
        read = Path.read_bytes
        for name in bindings:
            target = ROOT/name
            bad = [read(target)+b'\n# unapproved']
            if bindings[name]['before_sha256'] is not None:
                bad.append(owner._people_pr65_before(name))
            if name == NAME:
                bad += [read(target).replace(b'13.0.0', b'13.0.1'), b'\xef\xbb\xbf'+read(target)]
            for raw in bad:
                with self.subTest(path=name, attack=owner.sha(raw)), patch.object(
                        Path, 'read_bytes', lambda p: raw if p == target else read(p)):
                    with self.assertRaises(ValueError): owner.people_pr65_bindings()
            def missing(p):
                if p == target: raise FileNotFoundError(name)
                return read(p)
            with self.subTest(path=name, attack='missing'), patch.object(Path, 'read_bytes', missing):
                with self.assertRaises(OSError): owner.people_pr65_bindings()

    def test_receipt_hash_membership_parent_and_authority_rejected(self):
        target = ROOT/owner.PEOPLE_PR65_RECEIPT
        read = Path.read_bytes
        original = json.loads(read(target))
        for attack in ('hash', 'addition', 'deletion', 'parent', 'baseline', 'ci', 'publication'):
            changed = deepcopy(original)
            if attack == 'hash': changed['files'][NAME]['sha256'] = 'f'*64
            if attack == 'addition': changed['files']['unknown.py'] = changed['files'][NAME]
            if attack == 'deletion': changed['files'].pop(NAME)
            if attack == 'parent': changed['parent_commit'] = 'f'*40
            if attack == 'baseline': changed['baseline_commit'] = 'f'*40
            if attack == 'ci': changed['ci_authorized'] = True
            if attack == 'publication': changed['publication_authorized'] = True
            with self.subTest(attack=attack), patch.object(Path, 'read_bytes',
                    lambda p: json.dumps(changed).encode() if p == target else read(p)):
                with self.assertRaises(ValueError): owner.people_pr65_bindings()

    def test_exact_projection_crlf_and_unknown_bytes(self):
        physical = (ROOT/NAME).read_bytes()
        self.assertEqual(owner.people_pr65_bytes(ROOT, NAME, physical), owner._people_pr65_before(NAME))
        self.assertEqual(owner.people_pr65_bytes(ROOT, NAME, b'forged'), b'forged')
        self.assertEqual(owner.people_pr65_bytes(ROOT, 'unknown.py', physical), physical)
        read = Path.read_bytes
        crlf = physical.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        with patch.object(Path, 'read_bytes', lambda p: crlf if p == ROOT/NAME else read(p)):
            self.assertEqual(owner.people_pr65_bytes(ROOT, NAME, crlf), owner._people_pr65_before(NAME))
        adapter = m5.unicode_adapter()
        self.assertEqual(adapter.historical_bytes(ROOT, NAME, physical), adapter.predecessor(NAME))
        self.assertEqual(adapter.selected_hash(NAME, owner.PEOPLE_PR65_BEFORE[NAME]), owner.sha(physical))
        self.assertEqual(adapter.selected_hash(NAME, 'f'*64), 'f'*64)

    def test_fresh_head_receipt_and_regular_file_guards(self):
        from ci import people_colorize_maintenance as colorize
        head = colorize._head(ROOT)
        with patch.object(colorize, '_head', side_effect=[head, 'f'*40]):
            with self.assertRaisesRegex(ValueError, 'closing People PR65'):
                owner.people_pr65_bindings()
        read = Path.read_bytes
        target = ROOT/owner.PEOPLE_PR65_RECEIPT
        count = 0
        def changed(p):
            nonlocal count
            if p == target:
                count += 1
                if count > 1: return b'{}'
            return read(p)
        with patch.object(Path, 'read_bytes', changed):
            with self.assertRaisesRegex(ValueError, 'closing People PR65'):
                owner.people_pr65_bindings()
        regular = owner.regular
        def linked(root, name):
            if name == NAME: raise ValueError('Not a regular source')
            return regular(root, name)
        with patch.object(owner, 'regular', linked):
            with self.assertRaisesRegex(ValueError, 'regular source'): owner.people_pr65_bindings()

    def test_committed_scope_and_unknown_path(self):
        names = set(owner.PEOPLE_PR65_BEFORE)|{owner.PEOPLE_PR65_RECEIPT}
        self.assertTrue(names <= owner.scope_members())
        owner.verify_people_pr65_scope(ROOT, names)
        run = owner._git
        def forged(root, *args, **kwargs):
            if args[:2] == ('show', 'HEAD:'+NAME): return b'unapproved'
            return run(root, *args, **kwargs)
        with patch.object(owner, '_git', forged):
            with self.assertRaises(ValueError): owner.verify_people_pr65_scope(ROOT, {NAME})
        self.assertNotIn('unknown.py', owner.scope_members())


if __name__ == '__main__': unittest.main()
