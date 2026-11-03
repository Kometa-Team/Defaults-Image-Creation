"""Additive bulk CI scope; the original People test inventory is not extended."""
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


class BulkMaintenanceTests(unittest.TestCase):
    def test_exact_delivery_and_scope_pass(self):
        adapter = m5.bulk_adapter()
        value = adapter.verify()
        self.assertEqual(set(value['files']), adapter.MEMBERS)
        self.assertFalse(value['publication_authorized'])
        adapter.verify_scope(ROOT, adapter.M7_BASE, adapter.scope_members())

    def test_adapter_source_is_independently_pinned(self):
        original = Path.read_bytes
        target = ROOT/'ci/people_bulk_maintenance.py'
        with patch.object(Path, 'read_bytes', lambda p: original(p)+b'\n# drift' if p==target else original(p)):
            with self.assertRaises(ValueError):m5.bulk_adapter()

    def test_mutable_members_are_rechecked_after_cache_warmup(self):
        adapter=m5.bulk_adapter();adapter.verify();original=Path.read_bytes
        target=ROOT/'create_people_posters/bulk_regenerate.py'
        with patch.object(Path,'read_bytes',lambda p:original(p)+b'\n# drift' if p==target else original(p)):
            with self.assertRaises(ValueError):adapter.verify()

    def test_frozen_renderer_and_inventories_are_rechecked(self):
        adapter=m5.bulk_adapter();value=adapter.verify();original=Path.read_bytes
        for name in value['frozen_files']:
            target=ROOT/name
            with self.subTest(name=name), patch.object(Path,'read_bytes',lambda p:original(p)+b'x' if p==target else original(p)):
                with self.assertRaises(ValueError):adapter.verify()

    def test_manifest_expansion_resealing_and_authority_fail(self):
        adapter=m5.bulk_adapter();value=adapter.verify();original=Path.read_bytes
        for attack in ('scope','hash','authority','baseline'):
            changed=deepcopy(value)
            if attack=='scope':changed['files']['unreviewed.py']=next(iter(changed['files'].values()))
            elif attack=='hash':next(iter(changed['files'].values()))['sha256']='f'*64
            elif attack=='authority':changed['publication_authorized']=True
            else:changed['baseline_commit']='f'*40
            target=ROOT/adapter.MANIFEST
            with self.subTest(attack=attack), patch.object(Path,'read_bytes',lambda p:json.dumps(changed).encode() if p==target else original(p)):
                with self.assertRaises(ValueError):adapter.verify()

    def test_unknown_scope_and_foreign_checkout_fail(self):
        adapter=m5.bulk_adapter()
        with self.assertRaises(ValueError):adapter.verify_scope(ROOT,adapter.M7_BASE,{'unreviewed.py'})
        with self.assertRaises(ValueError):adapter.verify_scope(ROOT,'f'*40,adapter.scope_members())
        with self.assertRaises(ValueError):adapter.verify(ROOT/'foreign')

    def test_original_m5_functions_outside_additive_scope_are_unchanged(self):
        old=subprocess.check_output(['git','show',m5.bulk_adapter().BASE+':ci/phase5_m5_maintenance.py'],cwd=ROOT).decode('utf8')
        current=(ROOT/'ci/phase5_m5_maintenance.py').read_text(encoding='utf8')
        functions=lambda text:{n.name:ast.dump(n) for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        before,after=functions(old),functions(current)
        for name in before.keys()-{'scope_members','verify_scope'}:
            self.assertEqual(before[name],after[name],name)

    def test_bulk_tests_do_not_extend_frozen_people_namespace(self):
        names=subprocess.check_output(['git','ls-files','create_people_posters/tests'],cwd=ROOT).decode().splitlines()
        self.assertFalse(any(Path(name).name.startswith('test_bulk') for name in names))


if __name__=='__main__':unittest.main()
