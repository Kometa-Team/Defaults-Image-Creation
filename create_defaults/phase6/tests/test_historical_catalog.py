"""Historical replay and current catalog coexist without rolling history forward."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from create_defaults.bulk import catalog_history as history
from create_defaults.bulk.catalog import load_catalog
from create_defaults.bulk.common import BulkError, fingerprint
from create_defaults.bulk.contracts.adoption.models import read_canonical
from create_defaults.bulk.contracts.expanded.resolution import resolve
from create_defaults.bulk.contracts.playlist.validation import HERE, HISTORICAL_SHA256


class HistoricalCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.historical=history.resolve_historical()
        cls.current=resolve()
        cls.records=json.loads((HERE/'historical-outputs-v1.json').read_bytes())
        if fingerprint(cls.records)!=HISTORICAL_SHA256:
            raise AssertionError('Changed original nine historical Playlist records')

    def test_exact_nine_original_definitions_and_current_seventeen(self):
        before={r['identity']['id']:read_canonical(r['effective_definition_json']) for r in self.records}
        actual={key:value for key,value in self.historical.data()['expanded'].items()
            if value['category']=='Playlist'}
        self.assertEqual(len(before),9)
        self.assertEqual(actual,before)
        current={d.id:d.data for d in load_catalog(('Playlist',))}
        self.assertEqual(len(current),17)
        self.assertEqual({key:current[key] for key in before},before)
        ledger=json.loads((history.ROOT/'create_defaults/bulk/catalog/reservations-v1.json').read_bytes())
        self.assertEqual(set(current)-set(before),{row['id'] for row in ledger['entries']})
        expanded=self.current.data()['expanded']
        self.assertEqual({key:value for key,value in expanded.items() if value['category']=='Playlist'},current)

    def test_historical_loader_keeps_declared_membership_and_closing_file_checks(self):
        definitions=history.load_historical_catalog(('Playlist',))
        self.assertEqual({d.id:d.for_language('en').data for d in definitions},
            {r['identity']['id']:read_canonical(r['effective_definition_json']) for r in self.records})
        original=history.load_definitions
        def changed(paths,**kwargs):
            result=original(paths,**kwargs)
            Path(paths[0]).write_bytes(b'unapproved')
            return result
        with patch.object(history,'load_definitions',changed):
            with self.assertRaisesRegex(BulkError,'changed during definition loading'):
                history.load_historical_catalog(('Playlist',))

    def test_scoped_historical_resolution_keeps_exact_original_playlist(self):
        current=history.resolve_historical(categories=('Playlist',))
        self.assertEqual({Path(path).name for _,path,_ in current.source_pins},
            {'playlist.yml','profiles.yml'})
        expected={r['identity']['id']:read_canonical(r['effective_definition_json']) for r in self.records}
        self.assertEqual(current.data()['expanded'],expected)
        current.verify_current()
        self.assertEqual(len(load_catalog(('Playlist',))),17)

    def test_current_resolution_still_rejects_file_drift(self):
        target=history.ROOT/'create_defaults/bulk/catalog/playlist.yml'
        original=Path.read_bytes;raw=original(target)
        self.current.verify_current()
        for bad in (raw+b'changed',None):
            def read(path):
                if path==target:
                    if bad is None:raise FileNotFoundError(str(target))
                    return bad
                return original(path)
            with self.subTest(missing=bad is None),patch.object(Path,'read_bytes',read):
                with self.assertRaises((BulkError,OSError)):self.current.verify_current()

    def test_snapshot_is_bound_to_original_adoption_commit_and_hashes(self):
        authority=history._bindings()
        self.assertEqual(authority[0],'3d97bb888a2c3787609e4a0c88d5ee3e99bdcae2')
        self.assertEqual(self.historical._authority,authority)
        self.assertEqual({Path(path).name for _,path,_ in self.historical.source_pins},
            {Path(name).name for name,_,_ in authority[1]})
        self.historical.verify_current()
        self.assertTrue(all(Path(path).exists() for _,path,_ in self.historical.source_pins))

    def test_snapshot_rejects_tamper_rollback_and_missing_after_prior_proof(self):
        target=next(Path(path) for name,path,_ in self.historical.source_pins if name=='playlist.yml')
        raw=target.read_bytes()
        current=(history.ROOT/'create_defaults/bulk/catalog/playlist.yml').read_bytes()
        self.assertNotEqual(raw,current)
        try:
            for bad in (raw+b'\nunreviewed',current,None):
                self.historical.verify_current()
                if bad is None:target.unlink()
                else:target.write_bytes(bad)
                try:
                    with self.subTest(missing=bad is None),self.assertRaises((BulkError,OSError)):
                        self.historical.verify_current()
                finally:target.write_bytes(raw)
        finally:target.write_bytes(raw)

    def test_changed_authority_is_rejected_after_prior_proof(self):
        self.historical.verify_current()
        authority=self.historical._authority
        with patch.object(history,'_bindings',return_value=('0'*40,authority[1])):
            with self.assertRaisesRegex(BulkError,'authority changed'):
                self.historical.verify_current()

    def test_unknown_identity_keeps_original_resolution_rejection(self):
        with self.assertRaisesRegex(BulkError,'No actual declared owner'):
            self.historical.verify_current(['playlist.unapproved'])

    def test_immutable_git_objects_reject_wrong_bytes_modes_and_membership(self):
        original=history._git
        authority=history._bindings()
        for attack in ('bytes','mode','missing'):
            history._blobs.cache_clear()
            def git(*args,**kwargs):
                raw=original(*args,**kwargs)
                if args[0]=='ls-tree':
                    if attack=='mode':return raw.replace(b'100644',b'120000',1)
                    if attack=='missing':return b'\0'.join(raw.split(b'\0')[1:])
                if args[0]=='cat-file' and attack=='bytes':
                    end=raw.index(b'\n')+1
                    return raw[:end]+bytes([raw[end]^1])+raw[end+1:]
                return raw
            try:
                with self.subTest(attack=attack),patch.object(history,'_git',git):
                    with self.assertRaises(BulkError):history._blobs(*authority)
            finally:history._blobs.cache_clear()


if __name__=='__main__':unittest.main()
