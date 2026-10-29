"""Exact M2 scope/CI controls; original inventories and pins are immutable."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from ci import phase5_m2_maintenance as maintenance
from ci import phase5_m2 as runner

ROOT = Path(__file__).resolve().parents[2]


class Phase5M2MaintenanceTests(unittest.TestCase):
    def test_exact_cohort_predecessors_and_no_protected_source_transition(self):
        value = maintenance.verify_checkout()
        self.assertEqual(set(value['members']), maintenance.MEMBERS)
        self.assertEqual(value['production_intersection'], [])
        self.assertEqual(value['adoption_intersection'], [])
        self.assertFalse(value['publication_authorized'])
        for name, binding in value['members'].items():
            if binding['before_sha256'] is not None:
                self.assertEqual(maintenance.sha(maintenance._old(name)), binding['before_sha256'])

    def test_each_exact_member_rejects_tamper_rollback_and_deletion(self):
        value = maintenance.verify_checkout()
        original = Path.read_bytes
        for name, binding in value['members'].items():
            replacements = [original(ROOT / name) + b'\nunreviewed']
            if binding['before_sha256'] is not None:
                replacements.append(maintenance._old(name))
            for replacement in replacements:
                def changed(path):
                    return replacement if path == ROOT / name else original(path)
                with self.subTest(name=name), patch.object(Path, 'read_bytes', changed), self.assertRaises(ValueError):
                    maintenance.verify_checkout()
            def missing(path):
                if path == ROOT / name:
                    raise FileNotFoundError(name)
                return original(path)
            with self.subTest(missing=name), patch.object(Path, 'read_bytes', missing), self.assertRaises(OSError):
                maintenance.verify_checkout()

    def test_manifest_rejects_resealed_hashes_membership_and_baseline(self):
        original = Path.read_bytes
        value = maintenance.manifest()
        for field in ('members', 'baseline_commit', 'production_intersection', 'publication_authorized'):
            changed = deepcopy(value); changed[field] = 'unreviewed'
            replacement = json.dumps(changed).encode()
            def read(path):
                return replacement if path == maintenance.MANIFEST else original(path)
            with self.subTest(field=field), patch.object(Path, 'read_bytes', read), self.assertRaises(ValueError):
                maintenance.manifest()

    def test_scope_rejects_unknown_paths_nonregular_modes_and_deletions(self):
        with patch.object(maintenance, 'verify_checkout'):
            with self.assertRaisesRegex(ValueError, 'Unapproved M2 scope'):
                maintenance.verify_scope(ROOT, maintenance.BASE, {'unreviewed.md'})
            name = 'create_defaults/bulk/lifecycle/github_observations.py'
            for old, new, change in (('100644', '000000', 'D'), ('000000', '120000', 'A'),
                                     ('100644', '100644', 'R100')):
                row = (f':{old} {new} ' + '0' * 40 + ' ' + '1' * 40 + f' {change}\0{name}\0').encode()
                with patch.object(maintenance, '_git', return_value=row), self.assertRaisesRegex(ValueError, 'regular-file'):
                    maintenance.verify_scope(ROOT, maintenance.BASE, {name})

    def test_original_workflows_inventories_manifests_and_baselines_unchanged(self):
        names = ('.github/workflows/default-poster-validation.yml',
            '.github/workflows/lifecycle-m6-validation.yml', '.github/workflows/lifecycle-m7-validation.yml',
            '.github/workflows/dependency-provenance-validation.yml',
            '.github/workflows/people-storage-validation.yml',
            'ci/validation.py', 'ci/phase4_m7.py', 'ci/validation-plan.json', 'ci/original-test-ids.json',
            'ci/phase3-test-ids.json', 'ci/phase4-test-ids.json', 'ci/phase4-m7-test-ids.json',
            'ci/dependabot-maintenance-v1.json',
            'create_defaults/bulk/contracts/activation/data/production-pins-v1.json',
            'create_defaults/bulk/contracts/adoption/source-pins-v1.json')
        for name in names:
            old = subprocess.check_output(['git', 'show', maintenance.BASE + ':' + name], cwd=ROOT)
            self.assertEqual(maintenance.sha((ROOT / name).read_bytes()), maintenance.sha(old), name)

    def test_new_workflow_has_pinned_actions_both_platforms_no_credentials_and_same_budgets(self):
        import yaml
        workflow = yaml.safe_load((ROOT / '.github/workflows/phase5-m2-validation.yml').read_text())
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        job = workflow['jobs']['m2']
        self.assertEqual(set(job['strategy']['matrix']['os']), {'ubuntu-latest', 'windows-latest'})
        self.assertEqual(job['timeout-minutes'], 15)
        self.assertNotIn('GH_TOKEN', json.dumps(workflow))
        for job in workflow['jobs'].values():
            for step in job['steps']:
                if 'uses' in step:
                    self.assertRegex(step['uses'], r'@[0-9a-f]{40}$')
                if step.get('uses', '').startswith('actions/checkout@'):
                    self.assertFalse(step['with']['persist-credentials'])

    def test_m2_evidence_requires_exact_ids_three_phases_no_skips_and_current_head(self):
        nodes = json.loads(runner.IDS.read_text())
        expected = dict(head='a' * 40, plan_sha256='b' * 64)
        execution = dict(exitstatus=0, nodes=nodes, seconds=1, reports=[
            dict(nodeid=node, when=phase, outcome='passed', wasxfail=False, seconds=.001, skip_reason=None)
            for node in nodes for phase in ('setup', 'call', 'teardown')])
        report = dict(**expected, kind='phase5-m2-fixture-execution', success=True,
            ids_sha256=runner.digest(runner.IDS), inputs=runner.inputs(),
            collection=dict(exitstatus=0, nodes=nodes), execution=execution,
            authenticated_live_observations=0, operational_authority=False)
        runner.verify(report, expected)
        for change in ('head', 'missing-id', 'missing-phase', 'skipped', 'live', 'authority'):
            altered = deepcopy(report)
            if change == 'head': altered['head'] = 'c' * 40
            if change == 'missing-id': altered['execution']['nodes'] = nodes[:-1]
            if change == 'missing-phase': altered['execution']['reports'].pop()
            if change == 'skipped':
                altered['execution']['reports'][1].update(outcome='skipped', skip_reason='injected skip')
            if change == 'live': altered['authenticated_live_observations'] = 1
            if change == 'authority': altered['operational_authority'] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                runner.verify(altered, expected)
