"""Exact Phase 6 provenance, independently fresh physical files and HEAD."""
import unittest
from unittest.mock import patch

from ci import phase6_playlist_maintenance as pilot
from ci.people_colorize_maintenance import _head


class Phase6PlaylistMaintenanceTests(unittest.TestCase):
    def test_exact_committed_pilot_and_receipt(self):
        result = pilot.verify_checkout()
        self.assertEqual(result['head'], _head(pilot.ROOT))
        self.assertFalse(result['production_authorized'])
        self.assertFalse(result['publication_authorized'])

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

    def test_link_and_mode_changes_are_rejected(self):
        name = next(iter(pilot.ADDED))
        for mode in (b'120000', b'100755'):
            row = (b':000000 '+mode+b' '+b'0'*40+b' '+b'1'*40+b' A', name)
            with self.assertRaisesRegex(ValueError, 'rejects links, mode changes'):
                pilot._regular_diff((row,), {name}, exact=True)


if __name__ == '__main__':
    unittest.main()
