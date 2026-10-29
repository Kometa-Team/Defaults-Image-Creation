"""Alert reconciliation, effective pins and exact provenance preservation."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

from ci import dependabot_maintenance as audit

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / 'docs/dependabot-audit-2026-10-29.json'


def pillow_requirement(name):
    for line in (ROOT / name).read_text(encoding='utf8').splitlines():
        line = line.partition('#')[0].strip()
        if line and not line.startswith('-'):
            requirement = Requirement(line)
            if canonicalize_name(requirement.name) == 'pillow':
                return requirement
    raise AssertionError('Missing explicit Pillow requirement: ' + name)


class DependabotAuditTests(unittest.TestCase):
    def test_all_41_actual_alerts_are_reconciled_against_the_patched_version(self):
        report = json.loads(REPORT.read_text())
        alerts = report['alerts']
        self.assertEqual(len(alerts), 41)
        self.assertEqual(len({row['number'] for row in alerts}), 41)
        self.assertEqual({row['manifest'] for row in alerts}, {'create_defaults/phase2/requirements.txt'})
        self.assertEqual({canonicalize_name(row['package']) for row in alerts}, {'pillow'})
        self.assertEqual({severity: sum(row['severity'] == severity for row in alerts)
                          for severity in ('critical', 'high', 'medium')},
                         {'critical': 5, 'high': 23, 'medium': 13})
        for row in alerts:
            with self.subTest(alert=row['number']):
                affected = SpecifierSet(row['affected_range'])
                self.assertIn(row['detected_version'], affected)
                self.assertNotIn(row['current_main_resolved_version'], affected)
                self.assertEqual(row['first_patched_version'], '13.0.0')
                self.assertEqual(row['current_main_resolved_version'], '13.0.0')
                self.assertTrue(row['advisory_url'].endswith(row['ghsa_id']))

    def test_phase2_pin_matches_the_parent_and_all_supported_people_profiles(self):
        exact = ('create_defaults/requirements.txt', 'create_defaults/phase2/requirements.txt',
                 'create_people_posters/requirements.txt', 'create_people_posters/requirements-rembg.txt')
        for name in exact:
            with self.subTest(manifest=name):
                self.assertEqual(str(pillow_requirement(name).specifier), '==13.0.0')
        requirement = pillow_requirement('create_people_posters/requirements-ddcolor.txt')
        self.assertIn('13.0.0', requirement.specifier)
        self.assertNotIn('12.3.0', requirement.specifier)
        phase2 = (ROOT / 'create_defaults/phase2/requirements.txt').read_text()
        self.assertIn('-r ../requirements.txt', phase2)
        self.assertIn('jsonschema==4.26.0', phase2)

    def test_graph_duplicate_and_python_compatibility_evidence_remain_explicit(self):
        report = json.loads(REPORT.read_text())
        phase2 = next(row for row in report['dependency_graph']
                      if row['manifest'] == 'create_defaults/phase2/requirements.txt')
        self.assertEqual(set(phase2['pillow_requirements']), {'= 12.3.0', '= 13.0.0'})
        supported = SpecifierSet(report['pillow_release']['requires_python'])
        self.assertNotIn('3.10', supported)
        self.assertIn('3.11', supported)
        self.assertIn('3.13', supported)
        self.assertTrue(report['pillow_release']['windows_cp313_wheels'])
        self.assertTrue(report['pillow_release']['linux_cp313_wheels'])

    def test_minimum_rembg_update_allows_patched_pillow_and_preserves_active_code(self):
        report = json.loads(REPORT.read_text())
        rembg = report['rembg_release_comparison']
        old = next(Requirement(line) for line in rembg['versions']['2.0.85']['requires_dist']
                   if line.startswith('pillow'))
        new = next(Requirement(line) for line in rembg['versions']['2.0.86']['requires_dist']
                   if line.startswith('pillow'))
        self.assertNotIn('13.0.0', old.specifier)
        self.assertIn('13.0.0', new.specifier)
        for name in ('requirements.txt', 'requirements-rembg.txt'):
            lines = (ROOT / 'create_people_posters' / name).read_text().splitlines()
            self.assertIn('rembg[cpu]==2.0.86', lines)
        self.assertGreaterEqual(len(rembg['active_runtime_files']), 6)
        for row in rembg['active_runtime_files']:
            self.assertEqual(row['before_sha256'], row['after_sha256'], row['path'])
        self.assertEqual(rembg['active_models'], ['birefnet-portrait', 'birefnet-general', 'isnet-general-use'])

    def test_exact_successors_unknown_predecessors_and_history(self):
        value = audit.verify_checkout()
        for name, binding in value['members'].items():
            self.assertEqual(audit.selected_hash(name, 'f' * 64), 'f' * 64)
            if binding['before_sha256'] is not None:
                self.assertEqual(audit.selected_hash(name, binding['before_sha256']), binding['sha256'])
                current = (ROOT / name).read_bytes()
                old = audit.historical_bytes(ROOT, name, current)
                self.assertEqual(audit.sha(old), binding['before_sha256'])
                for bad in (old, current + b'\nunreviewed'):
                    with self.subTest(name=name), self.assertRaises(ValueError):
                        audit.historical_bytes(ROOT, name, bad)
        self.assertEqual(audit.selected_hash('unreviewed.py', 'f' * 64), 'f' * 64)
        self.assertFalse(value['publication_authorized'])

    def test_every_current_member_rejects_tamper_rollback_and_missing_files(self):
        audit.verify_checkout()  # Warm immutable caches before replacing files.
        original = Path.read_bytes
        for name, binding in audit.manifest()['members'].items():
            replacements = [original(ROOT / name) + b'\nunreviewed\n']
            if binding['before_sha256'] is not None:
                replacements.append(audit._old(name))
            for replacement in replacements:
                def changed(path):
                    return replacement if path == ROOT / name else original(path)
                with self.subTest(name=name), patch.object(Path, 'read_bytes', changed):
                    with self.assertRaises(ValueError):
                        audit.verify_checkout()
            def missing(path):
                if path == ROOT / name:
                    raise FileNotFoundError(name)
                return original(path)
            with self.subTest(missing=name), patch.object(Path, 'read_bytes', missing):
                with self.assertRaises(OSError):
                    audit.verify_checkout()

    def test_manifest_cannot_reseal_members_or_change_equal_length_hashes(self):
        value, original = audit.manifest(), Path.read_bytes
        variants = []
        for field in ('members', 'baseline_commit', 'publication_authorized'):
            changed = deepcopy(value)
            changed[field] = 'unreviewed'
            variants.append(json.dumps(changed).encode())
        raw = audit.MANIFEST.read_bytes()
        digest = next(iter(value['members'].values()))['sha256'].encode()
        variants.append(raw.replace(digest, b'0' * 64, 1))
        self.assertEqual(len(variants[-1]), len(raw))
        for replacement in variants:
            def changed(path):
                return replacement if path == audit.MANIFEST else original(path)
            with patch.object(Path, 'read_bytes', changed), self.assertRaises(ValueError):
                audit.manifest()

    def test_scope_rejects_unlisted_files_deletions_and_links(self):
        name = 'create_defaults/phase2/requirements.txt'
        with patch.object(audit, 'verify_checkout'):
            with self.assertRaises(ValueError):
                audit.verify_scope(ROOT, audit.BASE, {'unreviewed.py'})
            for old, new, status in (('100644', '000000', 'D'), ('100644', '120000', 'M'),
                                     ('100644', '100644', 'R100')):
                raw = (f':{old} {new} ' + '0' * 40 + ' ' + '1' * 40 + f' {status}\0{name}\0').encode()
                with self.subTest(status=status), patch.object(audit, '_git', return_value=raw):
                    with self.assertRaisesRegex(ValueError, 'regular-file'):
                        audit.verify_scope(ROOT, audit.BASE, {name})

    def test_original_manifests_and_test_inventories_are_unchanged(self):
        for name in ('ci/dependency-maintenance-v1.json', 'ci/people-readme-maintenance-v1.json',
                     'ci/people-security-maintenance.json', 'ci/people-security-test-ids.json',
                     'ci/validation-plan.json', 'ci/original-test-ids.json',
                     'ci/phase3-test-ids.json', 'ci/phase4-test-ids.json',
                     'ci/phase4-m7-test-ids.json',
                     'create_defaults/bulk/contracts/activation/data/production-pins-v1.json',
                     'create_defaults/bulk/contracts/adoption/source-pins-v1.json'):
            old = subprocess.check_output(['git', 'show', audit.BASE + ':' + name], cwd=ROOT)
            self.assertEqual(audit.sha((ROOT / name).read_bytes()), audit.sha(old), name)
