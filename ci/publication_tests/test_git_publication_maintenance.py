"""Exact current native bindings, immutable historical v1 evidence and tamper tests."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from ci import people_publication_maintenance as m


class NativeRegistrationTests(unittest.TestCase):
    def test_current_and_historical_bindings(self):
        old=json.loads((m.ROOT/m.RECEIPT).read_bytes())
        current=m.git_bindings();effective=m.verify()
        self.assertEqual(len(effective),7);self.assertEqual(len(current),7)
        for name,binding in current.items():
            self.assertEqual(m.digest((m.ROOT/name).read_bytes()),binding['sha256'])
            if name in old['files']:
                self.assertEqual(m.digest(binding['predecessor_lf'].encode()),old['files'][name]['sha256'])
                self.assertEqual(m.historical_bytes(m.ROOT,name,(m.ROOT/name).read_bytes()),m.predecessor(name))

    def test_every_native_change_deletion_and_rollback_fails_closed(self):
        read=Path.read_bytes
        for name,binding in m.git_bindings().items():
            target=m.ROOT/name;bad=[read(target)+b'\n# unauthorized']
            if binding['predecessor_lf'] is not None:bad.append(binding['predecessor_lf'].encode())
            for raw in bad:
                with self.subTest(name=name),patch.object(Path,'read_bytes',lambda p:raw if p==target else read(p)):
                    with self.assertRaises(ValueError):m.verify()
            def deleted(p):
                if p==target:raise FileNotFoundError(name)
                return read(p)
            with self.subTest(name=name,attack='delete'),patch.object(Path,'read_bytes',deleted):
                with self.assertRaises(FileNotFoundError):m.verify()

    def test_scope_hash_predecessor_and_authority_tampering(self):
        read=Path.read_bytes;target=m.ROOT/m.GIT_RECEIPT;good=json.loads(read(target))
        for kind in ('addition','deletion','hash','predecessor','ci','publication'):
            value=copy.deepcopy(good)
            if kind=='addition':value['files']['unapproved.py']=next(iter(value['files'].values()))
            if kind=='deletion':value['files'].pop(next(iter(value['files'])))
            if kind=='hash':next(iter(value['files'].values()))['sha256']='0'*64
            if kind=='predecessor':value['historical_receipt_sha256']='0'*64
            if kind=='ci':value['ci_authorized']=True
            if kind=='publication':value['publication_authorized']=True
            raw=json.dumps(value).encode()
            with self.subTest(kind=kind),patch.object(Path,'read_bytes',lambda p:raw if p==target else read(p)):
                with self.assertRaises(ValueError):m.verify()

    def test_no_workflow_or_font_scope_expansion(self):
        self.assertEqual(set(m.git_bindings()),m.GIT_MEMBERS)
        self.assertFalse(any(n.startswith('.github/') or '/fonts/' in n for n in m.GIT_MEMBERS))
        from ci import phase5_m5_maintenance as m5
        a=m5.unicode_adapter();self.assertEqual(len(a.verify()),41)
        self.assertEqual(a.publication_adapter().git_bindings(),m.git_bindings())


if __name__=='__main__':unittest.main()
