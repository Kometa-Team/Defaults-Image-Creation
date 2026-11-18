"""Exact Phase 6 provenance, independently fresh physical files and HEAD."""
import unittest
from unittest.mock import patch

from ci import phase6_playlist_maintenance as pilot
from ci.people_colorize_maintenance import _head


class Phase6PlaylistMaintenanceTests(unittest.TestCase):
    def test_protected_and_adopted_selectors_retain_exact_original_pins(self):
        from ci import phase5_m7_maintenance as m7
        from ci.dependency_maintenance import selected_hash
        from ci.phase5_m6_maintenance import APPROVED
        rows={name:(before,after) for name,before,after in pilot._decode((pilot.ROOT/pilot.RECEIPT).read_bytes())}
        with m7._invocation(pilot.ROOT),m7._cohort_invocation(pilot.ROOT):
            for name in pilot.PROTECTED_SUCCESSORS:
                before,after=rows[name]
                original=APPROVED[name][0] if name in APPROVED else before
                self.assertEqual(selected_hash(name,original),after)
                self.assertEqual(pilot.selected_hash(name,'0'*64),'0'*64)
                self.assertEqual(pilot.selected_hash('foreign.py',before),before)

    def test_protected_successors_recheck_tamper_rollback_and_missing_leaves(self):
        from pathlib import Path
        from ci import phase5_m7_maintenance as m7
        from ci.dependency_maintenance import selected_hash
        original=Path.read_bytes
        before=dict(pilot._blobs(pilot.BASE))
        with m7._invocation(pilot.ROOT),m7._cohort_invocation(pilot.ROOT):
            for name in pilot.PROTECTED_SUCCESSORS-{'create_defaults/bulk/operator_publication.py'}:
                target=pilot.ROOT/name;current=target.read_bytes();expected=pilot.member_sha(name,before[name])
                pilot.selected_hash(name,expected)
                for bad in (current+b'changed',before[name],None):
                    def read(path):
                        if path==target:
                            if bad is None:raise FileNotFoundError(name)
                            return bad
                        return original(path)
                    with self.subTest(path=name,missing=bad is None),patch.object(Path,'read_bytes',read):
                        with self.assertRaises((ValueError,OSError)):selected_hash(name,expected)

    def test_protected_cohort_is_once_per_invocation_with_fresh_leaf_reads(self):
        from pathlib import Path
        from ci import phase5_m7_maintenance as m7
        names=('create_defaults/bulk/planner.py','create_defaults/bulk/workers.py')
        before=dict(pilot._blobs(pilot.BASE));original=Path.read_bytes;reads=[]
        def read(path):reads.append(path);return original(path)
        for _ in range(2):
            with patch.object(pilot,'_protected_cohort_proof',wraps=pilot._protected_cohort_proof) as proof:
                with m7._invocation(pilot.ROOT),m7._cohort_invocation(pilot.ROOT),patch.object(Path,'read_bytes',read):
                    for _ in range(2):
                        for name in names:pilot.selected_hash(name,pilot.member_sha(name,before[name]))
                self.assertEqual(proof.call_count,2)  # entry and closing, no proof survives a call
        for name in names:self.assertGreaterEqual(reads.count(pilot.ROOT/name),4)

    def test_protected_cohort_closing_rechecks_files_and_head(self):
        from ci import phase5_m7_maintenance as m7
        name='create_defaults/bulk/planner.py';target=pilot.ROOT/name;raw=target.read_bytes()
        expected=pilot.member_sha(name,dict(pilot._blobs(pilot.BASE))[name])
        try:
            with self.assertRaises(ValueError):
                with m7._invocation(pilot.ROOT),m7._cohort_invocation(pilot.ROOT):
                    pilot.selected_hash(name,expected)
                    target.write_bytes(raw+b'closing tamper')
        finally:target.write_bytes(raw)
        head=_head(pilot.ROOT)
        with patch('ci.people_colorize_maintenance._head',side_effect=[head,'0'*40]):
            with self.assertRaises(ValueError):pilot.selected_hash(name,expected)

    def test_frozen_historical_and_current_manifests_keep_exact_records(self):
        from create_defaults.bulk import baselines
        from create_defaults import validation_manifest as manifests
        root=pilot.ROOT/'create_defaults'
        path=root/'fixtures/effective-jobs-en-cmap-compat.json.gz'
        before=path.read_bytes()
        self.assertTrue(baselines.verify_historical())
        self.assertTrue(baselines.verify_current())
        self.assertEqual(path.read_bytes(),before)
        value=manifests.load_manifest(root/'bulk/baselines/effective-jobs-en-current.json.gz')
        value['source_text_hashes']['poster_text.py']='0'*64
        with self.assertRaisesRegex(ValueError,'Frozen renderer/source changed: poster_text.py'):
            manifests.validate_manifest(value)

    def test_independent_expected_head_is_required_when_supplied(self):
        with self.assertRaisesRegex(ValueError,'expected HEAD differs'):
            pilot.verify_checkout(expected_head='0'*40)
        self.assertEqual(pilot.verify_checkout(expected_head=_head(pilot.ROOT))['head'],_head(pilot.ROOT))

    def test_exact_committed_pilot_and_receipt(self):
        result = pilot.verify_checkout()
        self.assertEqual(result['head'], _head(pilot.ROOT))
        self.assertFalse(result['production_authorized'])
        self.assertFalse(result['publication_authorized'])

    def test_renderer_successors_preserve_history_and_reject_unapproved_physical_bytes(self):
        from pathlib import Path
        from ci import phase5_m7_maintenance as m7
        before = dict(pilot._blobs(pilot.BASE))
        original = Path.read_bytes
        names = ('create_defaults/create_poster.py', 'create_defaults/bulk/planner.py',
                 'create_defaults/bulk/workers.py', 'create_defaults/bulk/schemas/manifest-v1.json',
                 'create_defaults/bulk/contracts/expanded/validation.py')
        with m7._invocation(pilot.ROOT), m7._cohort_invocation(pilot.ROOT):
            pilot.verify_scope(pilot.ROOT, pilot.scope_members())
            for name in names:
                target = pilot.ROOT/name
                current = target.read_bytes()
                self.assertEqual(m7.historical_bytes(pilot.ROOT, name, current), before[name])
                for bad in (current+b'changed', before[name], None):
                    def read(path):
                        if path == target:
                            if bad is None:raise FileNotFoundError(name)
                            return bad
                        return original(path)
                    with self.subTest(path=name, missing=bad is None), patch.object(Path, 'read_bytes', read):
                        with self.assertRaises((ValueError, OSError)):
                            m7.historical_bytes(pilot.ROOT, name, current)

    def test_immutable_objects_are_batched_but_physical_files_stay_fresh(self):
        for method in (pilot._tree, pilot._blobs, pilot._ancestry, pilot._diff, pilot._immutable_checked):
            method.cache_clear()
        original = pilot.git
        calls = []
        def observed(*args, **kwargs):
            calls.append(args)
            return original(*args, **kwargs)
        with patch.object(pilot, 'git', observed):
            pilot.verify_checkout()
            first = len(calls)
            self.assertLessEqual(first, 8)
            pilot.verify_checkout()
            self.assertEqual(len(calls), first)
        target = pilot.ROOT/'create_defaults/phase6/PLAYLIST_PILOT_MANIFEST.json'
        raw = target.read_bytes()
        try:
            target.write_bytes(raw+b'changed')
            with self.assertRaisesRegex(ValueError, 'Changed physical offline Playlist successor'):
                pilot.verify_checkout()
        finally:
            target.write_bytes(raw)

    def test_missing_member_cannot_use_a_previous_proof(self):
        target = pilot.ROOT/'create_defaults/phase6/assets/avp.png'
        raw = target.read_bytes()
        pilot.verify_checkout()
        try:
            target.unlink()
            with self.assertRaises((ValueError, FileNotFoundError)):
                pilot.verify_checkout()
        finally:
            target.write_bytes(raw)

    def test_roadmap_rollback_is_rejected(self):
        name = 'create_defaults/lifecycle/ROADMAP.md'
        target = pilot.ROOT/name
        raw = target.read_bytes()
        before = dict(pilot._blobs(pilot.BASE))[name]
        try:
            target.write_bytes(before)
            with self.assertRaisesRegex(ValueError, 'Changed physical offline Playlist successor'):
                pilot.verify_checkout()
        finally:
            target.write_bytes(raw)

    def test_fresh_closing_head_is_required(self):
        head = _head(pilot.ROOT)
        with patch('ci.people_colorize_maintenance._head', side_effect=[head, '0'*40]):
            with self.assertRaises(ValueError):
                pilot.verify_checkout()

    def test_unknown_path_is_not_admitted(self):
        row = (b':000000 100644 '+b'0'*40+b' '+b'1'*40+b' A', 'unapproved.txt')
        with self.assertRaisesRegex(ValueError, 'Unapproved offline Playlist path'):
            pilot._regular_diff((row,), pilot.scope_members(), exact=True)

    def test_symbolic_head_is_not_an_immutable_cache_key(self):
        with self.assertRaisesRegex(ValueError, 'full SHA'):
            pilot.proof(pilot.ROOT, 'HEAD')

    def test_physical_closing_bindings_and_historical_views_are_separate(self):
        from ci import phase5_m7_maintenance as m7
        with m7._invocation(pilot.ROOT):
            physical=m7._owned_members(pilot.ROOT)
            legacy=m7._owned_members(pilot.ROOT, physical=False)
            for name, before, after in pilot._decode((pilot.ROOT/pilot.RECEIPT).read_bytes()):
                if name in pilot.MODIFIED:
                    self.assertEqual(physical[name]['sha256'], after)
            name='create_defaults/lifecycle/ROADMAP.md'
            self.assertNotEqual(physical[name]['sha256'], legacy[name]['sha256'])
            name='create_defaults/bulk/operator_publication.py'
            current=(pilot.ROOT/name).read_bytes()
            self.assertEqual(m7.historical_bytes(pilot.ROOT,name,current),dict(pilot._blobs(pilot.BASE))[name])

    def test_aggregate_closing_proof_rechecks_the_full_pilot_cohort(self):
        from ci import phase5_m7_maintenance as m7
        target=pilot.ROOT/'create_defaults/phase6/assets/avp.png'
        raw=target.read_bytes()
        try:
            with self.assertRaisesRegex(ValueError, 'Changed physical offline Playlist successor'):
                with m7._invocation(pilot.ROOT), m7._cohort_invocation(pilot.ROOT):
                    pilot.verify_scope(pilot.ROOT, pilot.scope_members())
                    target.write_bytes(raw+b'changed')
        finally:
            target.write_bytes(raw)

    def test_adoption_selects_only_the_exact_fresh_operator_successor(self):
        from pathlib import Path
        from ci.dependency_maintenance import selected_hash
        from ci.phase5_m6_maintenance import APPROVED
        name='create_defaults/bulk/operator_publication.py'
        before=APPROVED[name][0]
        _, predecessor, after=next(row for row in pilot._decode(
            (pilot.ROOT/pilot.RECEIPT).read_bytes()) if row[0]==name)
        self.assertEqual(predecessor, APPROVED[name][1])
        self.assertEqual(selected_hash(name, before), after)
        self.assertEqual(selected_hash(name, '0'*64), '0'*64)
        self.assertEqual(selected_hash('foreign.py', before), before)
        original=Path.read_bytes
        target=pilot.ROOT/name
        raw=target.read_bytes()
        for bad in (raw+b'changed', dict(pilot._blobs(pilot.BASE))[name], None):
            def read(path):
                if path == target:
                    if bad is None:raise FileNotFoundError(name)
                    return bad
                return original(path)
            with self.subTest(attack=bad is None), patch.object(Path,'read_bytes',read):
                with self.assertRaises((ValueError,OSError)):
                    selected_hash(name, before)

    def test_link_and_mode_changes_are_rejected(self):
        name = next(iter(pilot.ADDED))
        for mode in (b'120000', b'100755'):
            row = (b':000000 '+mode+b' '+b'0'*40+b' '+b'1'*40+b' A', name)
            with self.assertRaisesRegex(ValueError, 'rejects links, mode changes'):
                pilot._regular_diff((row,), {name}, exact=True)


if __name__ == '__main__':
    unittest.main()
