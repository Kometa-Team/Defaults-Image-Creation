"""Current successor checks; historical receipts and assertions stay frozen."""
import ast
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from ci import phase5_m5_maintenance as m5


class PublicationMaintenanceTests(unittest.TestCase):
    def adapter(self):return m5.unicode_adapter().publication_adapter()

    def test_all_exact_current_bindings_and_historical_projections(self):
        adapter=self.adapter();bindings=adapter.verify()
        self.assertEqual(len(bindings),7)
        original=m5.unicode_adapter()
        self.assertEqual(len(original.verify()),41)
        for name,binding in bindings.items():
            raw=(ROOT/name).read_bytes()
            self.assertEqual(original.selected_hash(name,binding['before_sha256']),binding['sha256'] if binding['before_sha256'] else binding['before_sha256'])
            if binding['before_sha256']:
                self.assertEqual(adapter.historical_bytes(ROOT,name,raw),adapter.predecessor(name))
        m5.verify_checkout()
        m5.collection_adapter().verify()
        m5.bulk_adapter().verify()
        from ci.people_security_maintenance import verify
        verify(ROOT)

    def test_every_member_tamper_delete_and_rollback_fails_closed(self):
        adapter=self.adapter();bindings=adapter.verify();read=Path.read_bytes
        for name,binding in bindings.items():
            target=ROOT/name
            bads=[read(target)+b'\nunauthorized']
            if binding['before_sha256']:bads.append(adapter.predecessor(name))
            for bad in bads:
                with self.subTest(name=name,attack='bytes'),patch.object(Path,'read_bytes',lambda p:bad if p==target else read(p)):
                    with self.assertRaises(ValueError):adapter.verify()
            def missing(p):
                if p==target:raise FileNotFoundError(name)
                return read(p)
            with self.subTest(name=name,attack='delete'),patch.object(Path,'read_bytes',missing):
                with self.assertRaises(FileNotFoundError):adapter.verify()

    def test_receipt_authority_membership_and_hash_tampering_fail(self):
        adapter=self.adapter();target=ROOT/adapter.RECEIPT;read=Path.read_bytes
        for attack in ('addition','deletion','hash','ci','publication','baseline'):
            value=json.loads(read(target))
            if attack=='addition':value['files']['unreviewed.py']=next(iter(value['files'].values()))
            if attack=='deletion':value['files'].pop(next(iter(value['files'])))
            if attack=='hash':next(iter(value['files'].values()))['sha256']='f'*64
            if attack=='ci':value['ci_authorized']=True
            if attack=='publication':value['publication_authorized']=True
            if attack=='baseline':value['baseline_commit']='f'*40
            raw=json.dumps(value).encode()
            with self.subTest(attack=attack),patch.object(Path,'read_bytes',lambda p:raw if p==target else read(p)):
                with self.assertRaises(ValueError):adapter.verify()

    def test_loader_and_old_security_receipts_remain_exact(self):
        original=m5.unicode_adapter();read=Path.read_bytes
        target=ROOT/'ci/people_publication_maintenance.py'
        with patch.object(Path,'read_bytes',lambda p:read(p)+b'\n# forged' if p==target else read(p)):
            with self.assertRaises(ValueError):original.publication_adapter()
        for name in ('ci/people-security-maintenance.json','ci/people-readme-maintenance-v1.json',
                     'ci/people-unicode-source-v1.json','ci/people-unicode-ci-v1.json',
                     'ci/phase5-m5-maintenance-v1.json'):
            expected=subprocess.check_output(['git','show',self.adapter().BASE+':'+name],cwd=ROOT)
            self.assertEqual(read(ROOT/name).replace(b'\r\n',b'\n'),expected.replace(b'\r\n',b'\n'))

    def test_independent_current_jobs_and_existing_workflow_unchanged(self):
        name='.github/workflows/people-bulk-validation.yml'
        from ci.phase5_m6_maintenance import timeout_bytes
        current=timeout_bytes(ROOT,name,(ROOT/name).read_bytes()).replace(b'\r\n',b'\n')
        old=self.adapter().predecessor(name).replace(b'\r\n',b'\n')
        start=current.index(b'  publication:\n');end=current.index(b'  docker:\n',start)
        job=current[start:end].decode()
        self.assertEqual(current[:start]+current[end:],old)
        for required in ('os: [ubuntu-latest, windows-latest]', 'timeout-minutes: 60', 'fail-fast: false',
                'run: python -m pytest create_people_posters/reliability_tests -q', 'persist-credentials: false',
                'ref: ${{ github.event.pull_request.head.sha }}'):
            self.assertIn(required,job)
        self.assertIn(b'permissions:\n  contents: read\n',current)


if __name__=='__main__':unittest.main()
