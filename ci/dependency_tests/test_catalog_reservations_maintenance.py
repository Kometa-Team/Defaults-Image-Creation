"""Exact reservation admission; no relaxation of the historical pilot receipt."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from ci import phase6_playlist_maintenance as pilot


class CatalogReservationMaintenanceTests(unittest.TestCase):
    def test_exact_committed_additions_and_unchanged_historical_receipt(self):
        result=pilot.verify_checkout()
        self.assertFalse(result['production_authorized'])
        before=dict(pilot._blobs(pilot.REGISTRY_BASE))
        self.assertEqual(before[pilot.RECEIPT],pilot.git('show','HEAD:'+pilot.RECEIPT))
        self.assertTrue(pilot.REGISTRY_ADDED.isdisjoint(before))
        self.assertEqual(set(pilot.scope_members()),set(pilot.MODIFIED|pilot.ADDED|pilot.REGISTRY_ADDED|{pilot.OWNER,pilot.RECEIPT,pilot.REGISTRY_RECEIPT}))

    def test_actual_lifecycle_scope_including_registry(self):
        from ci.phase4_m7 import changed_scope
        from ci.phase5_m7_maintenance import owned_call
        @owned_call(cohorts=True)
        def aggregate(root):
            self.assertTrue(pilot.REGISTRY_ADDED <= changed_scope())
        # The aggregate owns only entry proofs, with fresh leaves and complete
        # closing checks; no witness or approval survives this public call.
        aggregate(pilot.ROOT)

    def test_additions_and_receipt_reject_tamper_and_missing_after_prior_proof(self):
        original=Path.read_bytes
        pilot.verify_checkout()
        for name in pilot.REGISTRY_ADDED|{pilot.REGISTRY_RECEIPT}:
            target=pilot.ROOT/name
            for bad in (original(target)+b'changed',None):
                def read(path):
                    if path==target:
                        if bad is None:raise FileNotFoundError(name)
                        return bad
                    return original(path)
                with self.subTest(path=name,missing=bad is None),patch.object(Path,'read_bytes',read):
                    with self.assertRaises((ValueError,OSError)):pilot.verify_checkout()

    def test_prior_owner_rollback_is_rejected(self):
        original=Path.read_bytes;target=pilot.ROOT/pilot.OWNER
        old=dict(pilot._blobs(pilot.REGISTRY_BASE))[pilot.OWNER]
        def read(path):return old if path==target else original(path)
        with patch.object(Path,'read_bytes',read),self.assertRaises(ValueError):pilot.verify_checkout()

    def test_empty_ledger_has_no_allocations_or_publication_authority(self):
        from create_defaults.bulk.library_sources import check_seal
        from create_defaults.bulk.catalog_reservations import LEDGER
        value=check_seal(json.loads((pilot.ROOT/LEDGER).read_bytes()))
        self.assertEqual(value['entries'],[]);self.assertEqual(value['requests'],[])
        self.assertEqual(value['owner'],dict(repository='Kometa-Team/Defaults-Image-Creation',branch='main',environment='production'))
        self.assertFalse(value['publication_authorized'])
        event=pilot.git('log','--no-merges','-1','--format=%H','HEAD','--',LEDGER).decode().strip()
        parent=pilot.git('rev-parse',event+'^').decode().strip()
        self.assertEqual(value['parent'],parent);self.assertEqual(value['base_commit'],parent)
        for name in ('playlist.yml','index-v1.json','profiles.yml'):
            path='create_defaults/bulk/catalog/'+name
            self.assertEqual(pilot.git('show',pilot.REGISTRY_BASE+':'+path),pilot.git('show','HEAD:'+path))

    def test_registration_is_add_only_and_rejects_unknown_modes_and_paths(self):
        for name in pilot.REGISTRY_ADDED|{'unapproved.txt'}:
            for old,new,status in ((b':000000',b'120000',b'A'),(b':000000',b'100755',b'A'),(b':100644',b'100644',b'D')):
                row=(b' '.join((old,new,b'0'*40,b'1'*40,status)),name)
                with self.subTest(name=name,mode=new,status=status),self.assertRaises(ValueError):
                    pilot._regular_diff((row,),pilot.scope_members(),exact=True)
        # A registered new path must remain an addition in the actual complete diff.
        rows=pilot._diff(pilot.git('rev-parse','HEAD').decode().strip())
        for metadata,name in rows:
            if name in pilot.REGISTRY_ADDED:
                self.assertEqual(metadata.split()[:2],[b':000000',b'100644'])
                self.assertEqual(metadata.split()[4],b'A')

    def test_staging_evidence_matches_unchanged_implementation_and_approved_artwork(self):
        import hashlib
        evidence=json.loads((pilot.ROOT/'create_defaults/phase6/review/catalog-reservations-staging.json').read_bytes())
        self.assertTrue(evidence['success'])
        self.assertEqual(evidence['implementation_sha256'],hashlib.sha256((pilot.ROOT/'create_defaults/bulk/catalog_reservations.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest())
        self.assertEqual(evidence['production_uuids_allocated'],0)
        self.assertEqual(evidence['live_catalog_writes'],0);self.assertEqual(evidence['network_writes'],0)
        self.assertEqual(evidence['restart_retry_matches'],8);self.assertEqual(evidence['catalog_mappings_valid'],8)
        self.assertEqual(evidence['exact_release_diff'],dict(additions=8,modifications=0,deletions=0,renames=0))
        self.assertEqual(len(evidence['entries']),8)
        for row in evidence['entries']:
            self.assertIsNone(row['production_identity'])
            path=pilot.ROOT/'create_defaults/phase6/staging_fixtures/approved'/row['public_path']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),row['approved_sha256'])

    def test_hosted_matrix_is_read_only_and_uses_exact_source_head(self):
        import yaml
        value=yaml.safe_load((pilot.ROOT/'.github/workflows/catalog-reservations-validation.yml').read_bytes())
        self.assertEqual(value['permissions'],{'contents':'read'})
        job=value['jobs']['registry']
        self.assertEqual(set(job['strategy']['matrix']['os']),{'ubuntu-latest','windows-latest'})
        self.assertEqual(job['timeout-minutes'],30)
        self.assertEqual(job['steps'][0]['with']['ref'],'${{ github.event.pull_request.head.sha || github.sha }}')
        self.assertFalse(job['steps'][0]['with']['persist-credentials'])
        for step in job['steps']:
            if 'uses' in step:self.assertRegex(step['uses'],r'@[0-9a-f]{40}$')


if __name__=='__main__':unittest.main()
