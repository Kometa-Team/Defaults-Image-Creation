"""Dependency-only transition controls; frozen original test IDs stay unchanged."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ci import dependency_maintenance as transition
from ci import people_security_maintenance as people
from create_defaults.bulk.common import BulkError, canonical, fingerprint
from create_defaults.bulk.contracts.activation import protection
from create_defaults.bulk.contracts.adoption.sources import load_pins, verify_sources

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT/'ci/dependency-maintenance-v1.json'


def sha(raw):
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()


class DependencyMaintenanceTests(unittest.TestCase):
    def test_transition_is_exactly_merged_pr23_not_an_unreviewed_hash_refresh(self):
        value = json.loads(MANIFEST.read_text(encoding='utf8'))
        self.assertEqual(fingerprint(value), transition.PIN)
        self.assertEqual(set(value['files']), transition.DEPENDENCIES)
        changes = subprocess.check_output(['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', value['dependency_commit']], cwd=ROOT, text=True).splitlines()
        self.assertEqual(set(changes), transition.DEPENDENCIES)
        for name, binding in value['files'].items():
            before = subprocess.check_output(['git', 'show', value['dependency_commit']+'^:'+name], cwd=ROOT)
            after = subprocess.check_output(['git', 'show', value['dependency_commit']+':'+name], cwd=ROOT)
            self.assertEqual(sha(before), binding['before_sha256'])
            self.assertEqual(sha(after), binding['sha256'])
            self.assertEqual(sha((ROOT/name).read_bytes()), binding['sha256'])
            self.assertEqual(transition.selected_hash(name, binding['before_sha256']), binding['sha256'])
        for name,binding in value['infrastructure'].items():
            old=subprocess.check_output(['git','show',value['baseline_commit']+':'+name],cwd=ROOT)
            self.assertEqual(sha(old),binding['before_sha256'])
            self.assertEqual(sha((ROOT/name).read_bytes()),binding['sha256'])
        pins = json.loads((ROOT/people.PINS).read_text(encoding='utf8'))
        self.assertEqual(fingerprint(pins), value['production_manifest_sha256'])
        self.assertEqual(fingerprint(load_pins()), value['adoption_snapshot_sha256'])
        for name, binding in value['files'].items():
            self.assertEqual(pins['files'][name], binding['before_sha256'])
        adopted = {i['path']: i['sha256'] for i in load_pins()['files']}
        self.assertEqual(set(adopted)&transition.DEPENDENCIES, {'create_defaults/requirements.txt'})
        self.assertEqual(adopted['create_defaults/requirements.txt'], value['files']['create_defaults/requirements.txt']['before_sha256'])

    def test_all_current_source_checks_pass_without_rewriting_history(self):
        self.assertEqual(protection.verify()['production_files_verified'], 190)
        self.assertEqual(len(load_pins()['files']), 299)
        verify_sources(load_pins())
        people.verify(ROOT)
        selected = people.baseline_pins(ROOT)
        self.assertEqual(len(selected['files']), 190)
        # Frozen manifests, historical records, existing CI selection and gates
        # retain exact bytes; this test cannot legitimize changes to them.
        for name in (people.PINS, 'ci/people-security-maintenance.json',
                     'create_defaults/bulk/contracts/adoption/source-pins-v1.json',
                     '.github/workflows/default-poster-validation.yml',
                     'ci/validation-plan.json', 'ci/original-test-ids.json',
                     'ci/phase3-test-ids.json', 'ci/phase4-test-ids.json',
                     'ci/phase4-composition-test-ids.json', 'ci/phase4-review-test-ids.json',
                     'ci/phase4-transaction-test-ids.json'):
            before = subprocess.check_output(['git', 'show', 'd6b039788315f2198304cf05f7efea5addc271c9:'+name], cwd=ROOT)
            self.assertEqual(sha(before), sha((ROOT/name).read_bytes()), name)

    def test_protection_infrastructure_is_exactly_bound_and_unexpected_edits_fail(self):
        value=json.loads(MANIFEST.read_text(encoding='utf8'))
        name=transition.PROTECTION;binding=value['infrastructure'][name]
        before=subprocess.check_output(['git','show',value['baseline_commit']+':'+name],cwd=ROOT)
        self.assertEqual(sha(before),binding['before_sha256'])
        self.assertEqual(sha((ROOT/name).read_bytes()),binding['sha256'])
        original=people._bytes
        def changed(path):
            raw=original(path)
            return raw+b'\n# unexpected protection change\n' if path==ROOT/name else raw
        with patch.object(people,'_bytes',changed):
            with self.assertRaises(ValueError): people.verify(ROOT)

    def test_adoption_rejects_further_dependency_edits_and_rollback(self):
        from create_defaults.bulk.contracts.adoption.models import AdoptionError
        value=json.loads(MANIFEST.read_text(encoding='utf8'))
        name='create_defaults/requirements.txt'
        pins={'source_commit':'synthetic-dependency-case','files':[
            {'path':name,'sha256':value['files'][name]['before_sha256'],'text_lf':True}]}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/name;target.parent.mkdir(parents=True)
            raw=(ROOT/name).read_bytes();target.write_bytes(raw)
            verify_sources(pins,root)
            for bad in (raw+b'\n# unexpected dependency edit\n',
                        subprocess.check_output(['git','show','06e3bc5^:'+name],cwd=ROOT)):
                target.write_bytes(bad)
                with self.assertRaises(AdoptionError):verify_sources(pins,root)

    def test_scope_extension_requires_exact_infrastructure_bytes(self):
        from ci.phase4 import verify_maintenance
        original=Path.read_bytes
        for name in transition.INFRASTRUCTURE:
            with self.subTest(name=name):
                def modified(path):
                    raw=original(path)
                    return raw+b'\n# unapproved maintenance edit\n' if path==ROOT/name else raw
                with patch.object(Path,'read_bytes',modified):
                    with self.assertRaises(ValueError):transition.verify_infrastructure(ROOT)
                    with self.assertRaises(ValueError):verify_maintenance(ROOT)
                    with self.assertRaises(ValueError):people.verify(ROOT)

    def test_historical_dependency_view_verifies_current_and_original_bytes(self):
        value=json.loads(MANIFEST.read_text(encoding='utf8'))
        for name in transition.DEPENDENCIES:
            current=(ROOT/name).read_bytes()
            old=transition.historical_dependency_bytes(name,current,ROOT)
            self.assertEqual(sha(old),value['files'][name]['before_sha256'])
            with self.assertRaises(ValueError):transition.historical_dependency_bytes(name,current+b'\nedit',ROOT)
            with self.assertRaises(ValueError):transition.historical_dependency_bytes(name,old,ROOT)
        with self.assertRaises(ValueError):transition.historical_dependency_bytes('unexpected',b'x',ROOT)

    def test_current_calibration_preserves_measurements_and_separates_provenance(self):
        path=ROOT/'create_defaults/bulk/contracts/logos/calibration-v1.json'
        historical=json.loads(path.read_bytes());before=deepcopy(historical)
        current=transition.current_calibration_expectation(historical)
        value=json.loads(MANIFEST.read_text(encoding='utf8'))['logo_calibration']
        self.assertEqual(historical,before)
        self.assertEqual(fingerprint(current),value['sha256'])
        self.assertNotEqual(fingerprint(current),fingerprint(historical))
        for a,b in zip(historical['measurements'],current['measurements'],strict=True):
            a=deepcopy(a);b=deepcopy(b)
            for row in (a,b):
                row['diagnostics']['settings'].pop('Pillow')
                row['diagnostics'].pop('policy_sha256')
            self.assertEqual(a,b)
        self.assertFalse(current['approved_policy'])
        self.assertFalse(current['automatic_match_enabled'])
        for field in ('grid','approved_policy','family_disjoint'):
            altered=deepcopy(historical);altered[field]='tampered'
            with self.assertRaises(ValueError):transition.current_calibration_expectation(altered)

    def test_unlisted_paths_or_different_predecessors_do_not_acquire_transition(self):
        for name in transition.DEPENDENCIES|{'create_defaults/create_poster.py', '../requirements.txt'}:
            self.assertEqual(transition.selected_hash(name, 'f'*64), 'f'*64)

    def test_missing_tampered_and_cached_manifest_fail_closed(self):
        value = json.loads(MANIFEST.read_text(encoding='utf8'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'transition.json'
            with patch.object(transition, 'MANIFEST', path):
                with self.assertRaises(FileNotFoundError): transition.selected_hash('x', 'f'*64)
                path.write_bytes(canonical(value))
                transition.selected_hash('x', 'f'*64)
                for change in ('sha256', 'before_sha256', 'membership', 'provenance', 'scope'):
                    changed = deepcopy(value)
                    if change in ('sha256', 'before_sha256'):
                        changed['files']['create_defaults/requirements.txt'][change] = 'f'*64
                    elif change == 'membership': changed['files']['unexpected.py'] = {'sha256':'f'*64}
                    elif change == 'provenance': changed['dependency_commit'] = 'f'*40
                    else: changed['scope'] = 'publication approved'
                    path.write_bytes(canonical(changed))
                    with self.assertRaises(ValueError): transition.selected_hash('x', 'f'*64)

    def test_each_dependency_and_unrelated_protected_change_or_rollback_is_rejected(self):
        pins = json.loads((ROOT/people.PINS).read_text(encoding='utf8'))
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            for name in pins['files']:
                target = source/name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/name, target)
            self.assertEqual(protection.verify(root=source)['production_files_verified'], 190)
            for name in sorted(transition.DEPENDENCIES|{'create_defaults/create_poster.py', '.github/workflows/default-poster-validation.yml'}):
                target = source/name; raw = target.read_bytes()
                try:
                    target.write_bytes(raw+b'\n# unexpected edit\n')
                    with self.assertRaises(BulkError) as error: protection.verify(root=source)
                    self.assertEqual(error.exception.code, 'activation_production_changed')
                    if name in transition.DEPENDENCIES:
                        target.write_bytes(subprocess.check_output(['git','show','06e3bc5^:'+name],cwd=ROOT))
                        with self.assertRaises(BulkError): protection.verify(root=source)
                finally: target.write_bytes(raw)
            # Text CRLF is accepted by the original normalization; no case/path
            # aliases or alternate content are admitted.
            for name in transition.DEPENDENCIES:
                target=source/name
                target.write_bytes(target.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
            self.assertEqual(protection.verify(root=source)['production_files_verified'], 190)

    def test_independent_activation_guard_still_rejects_even_a_matching_test_pin(self):
        pins = json.loads((ROOT/people.PINS).read_text(encoding='utf8'))
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'source';here=Path(directory)/'guard'
            for name in pins['files']:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
            name='create_defaults/create_poster.py';path=root/name
            path.write_bytes(path.read_bytes()+b'\nimport create_defaults.bulk.contracts.activation\n')
            pins['files'][name]=sha(path.read_bytes())
            data=here/'data/production-pins-v1.json';data.parent.mkdir(parents=True);data.write_bytes(canonical(pins))
            with patch.object(protection,'HERE',here),patch.object(protection,'PRODUCTION_PINS_SHA256',fingerprint(pins)):
                with self.assertRaises(BulkError) as error: protection.verify(root=root)
            self.assertEqual(error.exception.code,'activation_production_import')


if __name__ == '__main__':
    unittest.main(verbosity=2)
