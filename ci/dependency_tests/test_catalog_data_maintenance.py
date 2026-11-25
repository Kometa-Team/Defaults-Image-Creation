"""Exact eight-reservation data successor; historical evidence is immutable."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from ci import phase6_playlist_maintenance as pilot
from ci import phase5_m7_maintenance as m7


class CatalogDataMaintenanceTests(unittest.TestCase):
    def test_exact_data_scope_and_preserved_history(self):
        result=pilot.verify_checkout()
        self.assertFalse(result['publication_authorized'])
        before=dict(pilot._blobs(pilot.DATA_BASE))
        for name in (pilot.RECEIPT,pilot.REGISTRY_RECEIPT,pilot.REGISTRY_PRIOR_RECEIPT):
            self.assertEqual(before[name],(pilot.ROOT/name).read_bytes().replace(b'\r\n',b'\n'))
        self.assertEqual(pilot.git('rev-parse',pilot.DATA_PREDECESSOR+'^').decode().strip(),pilot.DATA_ALLOCATION)
        rows=pilot._diff(result['head'],pilot.DATA_BASE)
        self.assertEqual({name for _,name in rows},pilot.DATA_MODIFIED|pilot.DATA_ADDED|{pilot.OWNER,pilot.DATA_RECEIPT})
        pilot._regular_diff(rows,pilot.DATA_MODIFIED|pilot.DATA_ADDED|{pilot.OWNER,pilot.DATA_RECEIPT},exact=True)
        for metadata,name in rows:
            self.assertEqual(metadata.split()[4],b'M' if name in pilot.DATA_MODIFIED|{pilot.OWNER} else b'A')

    def test_all_eight_mappings_sources_artwork_and_original_nine(self):
        from create_defaults.bulk.catalog import load_catalog
        from create_defaults.bulk.catalog_reservations import LEDGER,INDEX
        from create_defaults.bulk.library_sources import check_seal
        from create_defaults.bulk.catalog_history import resolve_historical
        value=check_seal(json.loads((pilot.ROOT/LEDGER).read_bytes()))
        self.assertFalse(value['publication_authorized'])
        self.assertEqual(len(value['entries']),8);self.assertEqual(len(value['requests']),8)
        current={d.id:d.for_language('en').data for d in load_catalog(('Playlist',))}
        historical=resolve_historical()
        original={key:v for key,v in historical.data()['expanded'].items() if v['category']=='Playlist'}
        self.assertEqual(len(original),9);self.assertEqual(len(current),17)
        self.assertEqual({key:current[key] for key in original},original)
        entries={e['id']:e for e in value['entries']}
        self.assertEqual(set(current),set(original)|set(entries))
        old=check_seal(json.loads(pilot.git('show',pilot.DATA_BASE+':'+INDEX)))['posters']
        index=check_seal(json.loads((pilot.ROOT/INDEX).read_bytes()))['posters']
        self.assertEqual({key:index[key] for key in old},old)
        self.assertEqual(set(index),set(old)|set(entries))
        self.assertEqual(len({r['token'] for r in value['requests']}),8)
        for request in value['requests']:
            entry=entries[request['identity']];names=entry['names'];definition=current[entry['id']]
            self.assertEqual(names,request['request']['names'])
            self.assertEqual(definition['output']['remote_paths'],{'en':names['public_path']})
            self.assertEqual(index[entry['id']],dict(definition=entry['id'],category='Playlist',dependencies=[]))
            logo=(pilot.ROOT/'create_defaults'/names['source']['path']).read_bytes()
            self.assertEqual(hashlib.sha256(logo).hexdigest(),names['source']['sha256'])
            self.assertEqual(logo,(pilot.ROOT/'create_defaults/phase6/assets'/Path(names['source']['path']).name).read_bytes())
            jpeg=(pilot.ROOT/'create_defaults/phase6/staging_fixtures/approved'/names['public_path']).read_bytes()
            self.assertEqual(hashlib.sha256(jpeg).hexdigest(),request['approved_jpeg_sha256'])

    def test_exact_data_rejects_tamper_rollback_missing_and_unapproved_hash(self):
        original=Path.read_bytes
        before=dict(pilot._blobs(pilot.DATA_BASE))
        pilot.verify_checkout()
        for name in pilot.DATA_MODIFIED|pilot.DATA_ADDED|{pilot.DATA_RECEIPT}:
            target=pilot.ROOT/name
            for bad in (original(target)+b'changed',None,*([before[name]] if name in before else [])):
                def read(path):
                    if path==target:
                        if bad is None:raise FileNotFoundError(name)
                        return bad
                    return original(path)
                with self.subTest(path=name,missing=bad is None),patch.object(Path,'read_bytes',read):
                    with self.assertRaises((ValueError,OSError)):pilot.verify_checkout()

    def test_exact_data_receipt_does_not_grant_future_successors_or_publication(self):
        value=json.loads((pilot.ROOT/pilot.DATA_RECEIPT).read_bytes())
        for attack in ('member','hash','predecessor','publication','allocation'):
            bad=deepcopy(value)
            if attack=='member':bad['members']['unapproved.txt']=next(iter(bad['members'].values()))
            elif attack=='hash':next(iter(bad['members'].values()))['sha256']='0'*64
            elif attack=='predecessor':bad['predecessor_commit']='0'*40
            elif attack=='publication':bad['publication_authorized']=True
            else:bad['allocation_commit']='0'*40
            with self.subTest(attack=attack),self.assertRaises(ValueError):pilot._decode_data(json.dumps(bad).encode())

    def test_current_data_selectors_and_historical_views_recheck_leaves(self):
        from ci.dependency_maintenance import selected_hash
        before=dict(pilot._blobs(pilot.DATA_BASE));original=Path.read_bytes
        with m7._invocation(pilot.ROOT),m7._cohort_invocation(pilot.ROOT):
            for name in pilot.DATA_PROTECTED:
                target=pilot.ROOT/name;raw=original(target);expected=pilot.member_sha(name,before[name])
                self.assertEqual(selected_hash(name,expected),pilot.member_sha(name,raw))
                self.assertEqual(selected_hash(name,'0'*64),'0'*64)
                self.assertEqual(pilot.historical_bytes(pilot.ROOT,name,raw),before[name])
                for bad in (raw+b'changed',before[name],None):
                    def read(path):
                        if path==target:
                            if bad is None:raise FileNotFoundError(name)
                            return bad
                        return original(path)
                    with self.subTest(path=name,missing=bad is None),patch.object(Path,'read_bytes',read):
                        with self.assertRaises((ValueError,OSError)):selected_hash(name,expected)
                        with self.assertRaises((ValueError,OSError)):pilot.historical_bytes(pilot.ROOT,name,raw)

    def test_historical_playlist_audit_keeps_exact_nine(self):
        from create_defaults.bulk.contracts.playlist.validation import PlaylistBoundary,CONTRACT_SHA256,REGISTRY_SHA256,M2_SHA256
        with m7._invocation(pilot.ROOT),m7._cohort_invocation(pilot.ROOT):
            report=PlaylistBoundary.load(contract_sha256=CONTRACT_SHA256,registry_sha256=REGISTRY_SHA256,adoption_sha256=M2_SHA256).audit()
        self.assertTrue(report['membership_exact']);self.assertTrue(report['compatible'])
        self.assertEqual(len(report['items']),9)
        self.assertFalse(report['publication_authorized'])

    def test_complete_lifecycle_preservation_with_original_pins(self):
        from ci.phase4_m7 import preservation
        with m7._invocation(pilot.ROOT),m7._cohort_invocation(pilot.ROOT):
            report=preservation()
        self.assertEqual(report['protected_members'],190)
        self.assertEqual(report['adoption_sources'],299)
        self.assertEqual(report['unexplained_differences'],0)


if __name__=='__main__':unittest.main()
