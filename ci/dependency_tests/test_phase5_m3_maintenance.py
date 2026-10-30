"""Independent exact M3 CI successor controls; no legacy inventory changes."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from ci import phase5_m3_maintenance as maintenance
from ci import phase5_m3 as runner

ROOT = Path(__file__).resolve().parents[2]


class Phase5M3MaintenanceTests(unittest.TestCase):
    def test_exact_cohort_has_no_protected_or_frozen_source_transition(self):
        value = maintenance.verify_checkout()
        self.assertEqual(set(value['members']), maintenance.MEMBERS)
        for key in ('production_intersection', 'adoption_intersection', 'frozen_m7_intersection'):
            self.assertEqual(value[key], [])
        self.assertFalse(value['publication_authorized'])
        self.assertEqual(len(maintenance.MEMBERS | maintenance.ANCHORS), 14)
        changed = {name for name, v in value['members'].items() if v['before_sha256'] is not None}
        self.assertEqual(changed, {'ci/phase5_m2_maintenance.py', 'create_defaults/lifecycle/ROADMAP.md'})

    def test_independently_approved_existing_file_predecessors_and_successors(self):
        expected = {
            'ci/phase5_m2_maintenance.py': ('c76fca14c13dc4d6e6832ea9ef351c9029a5fd70098e1be15b8e633c469a963a', 'e9e514cf8145c3f43893b9a5dfe14543e8287192862d98940f848183189c7f4b'),
            'create_defaults/lifecycle/ROADMAP.md': ('8d15de091e0ff4a75f131b13ff7bce0063eadda8525e895497d190746c32a8fa', 'f776dea7e1d719439df2fb1f6c8ddea30297eda6bf63f30e9f93cea7f502ca96'),
        }
        for name, (before, after) in expected.items():
            self.assertEqual(maintenance.sha(maintenance._old(name)), before)
            raw = (ROOT/name).read_bytes()
            self.assertEqual(maintenance.sha(raw), after)
            self.assertEqual(maintenance.sha(maintenance.historical_bytes(ROOT, name, raw)), before)

    def test_each_exact_member_rejects_tamper_rollback_and_deletion(self):
        value = maintenance.verify_checkout()
        original = Path.read_bytes
        for name, binding in value['members'].items():
            replacements = [original(ROOT/name) + b'\nunreviewed']
            if binding['before_sha256'] is not None:
                replacements.append(maintenance._old(name))
            for replacement in replacements:
                def changed(path):
                    return replacement if path == ROOT/name else original(path)
                with self.subTest(name=name), patch.object(Path, 'read_bytes', changed), self.assertRaises(ValueError):
                    maintenance.verify_checkout()
            def missing(path):
                if path == ROOT/name:
                    raise FileNotFoundError(name)
                return original(path)
            with self.subTest(missing=name), patch.object(Path, 'read_bytes', missing), self.assertRaises(OSError):
                maintenance.verify_checkout()

    def test_manifest_rejects_resealing_membership_baseline_and_scope(self):
        original = Path.read_bytes
        value = maintenance.manifest()
        for key in ('members', 'baseline_commit', 'production_intersection', 'frozen_m7_intersection', 'publication_authorized'):
            altered = deepcopy(value)
            altered[key] = 'unreviewed'
            raw = json.dumps(altered).encode()
            def changed(path):
                return raw if path == maintenance.MANIFEST else original(path)
            with self.subTest(key=key), patch.object(Path, 'read_bytes', changed), self.assertRaises(ValueError):
                maintenance.manifest()

    def test_scope_rejects_unknown_paths_and_unsafe_diff_modes(self):
        with patch.object(maintenance, 'verify_checkout'):
            with self.assertRaisesRegex(ValueError, 'Unapproved M3 scope'):
                maintenance.verify_scope(ROOT, maintenance.BASE, {'future-milestone.py'})
            name = 'create_defaults/bulk/lifecycle/github_decisions.py'
            for old, new, status in [('100644','000000','D'), ('000000','120000','A'), ('100644','100644','R100')]:
                raw = (f':{old} {new} ' + '0'*40 + ' ' + '1'*40 + f' {status}\0{name}\0').encode()
                with patch.object(maintenance, '_git', return_value=raw), self.assertRaisesRegex(ValueError, 'regular-file'):
                    maintenance.verify_scope(ROOT, maintenance.BASE, {name})

    def test_m2_original_manifest_and_m7_allowed_route_are_preserved(self):
        from ci import phase5_m2_maintenance as m2
        from ci.phase4_m7 import ALLOWED
        self.assertFalse(maintenance.scope_members() & ALLOWED)
        self.assertEqual(m2.verify_checkout()['version'], 1)
        for name in ('ci/phase5-m2-maintenance-v1.json', 'ci/phase5-m2-test-ids.json',
                     'ci/dependency_tests/test_phase5_m2_maintenance.py'):
            self.assertEqual(maintenance.sha((ROOT/name).read_bytes()), maintenance.sha(maintenance._old(name)))

    def test_original_workflows_sources_inventories_and_production_pins_unchanged(self):
        names = ['.github/workflows/' + name for name in ('default-poster-validation.yml', 'lifecycle-m6-validation.yml',
            'lifecycle-m7-validation.yml', 'dependency-provenance-validation.yml', 'people-storage-validation.yml', 'phase5-m2-validation.yml')]
        names += ['ci/validation.py', 'ci/phase4_m7.py', 'ci/original-test-ids.json', 'ci/phase3-test-ids.json',
            'ci/phase4-test-ids.json', 'ci/phase4-m7-test-ids.json', 'ci/dependabot-maintenance-v1.json',
            'create_defaults/bulk/contracts/activation/data/production-pins-v1.json',
            'create_defaults/bulk/contracts/adoption/source-pins-v1.json',
            'create_defaults/bulk/contracts/registry.py', 'create_defaults/bulk/contracts/evidence_consumption/engine.py',
            'create_defaults/bulk/lifecycle/github_observations.py', 'create_defaults/bulk/lifecycle/github_observation_transport.py',
            'create_defaults/bulk/lifecycle/review.py', 'create_defaults/bulk/lifecycle/review_authority.py',
            'create_defaults/bulk/lifecycle/evidence.py', 'create_defaults/bulk/lifecycle/previews.py',
            'create_defaults/bulk/contracts/categories/data/review-registry-v1.json']
        for name in names:
            old = subprocess.check_output(['git','show',maintenance.BASE+':'+name], cwd=ROOT)
            self.assertEqual(maintenance.sha((ROOT/name).read_bytes()), maintenance.sha(old), name)

    def test_additive_workflow_is_readonly_pinned_both_platforms_and_bounded(self):
        import yaml
        value = yaml.safe_load((ROOT/'.github/workflows/phase5-m3-validation.yml').read_text())
        self.assertEqual(value['permissions'], {'contents':'read'})
        self.assertEqual(set(value['jobs']['m3']['strategy']['matrix']['os']), {'windows-latest','ubuntu-latest'})
        self.assertNotIn('GH_TOKEN', json.dumps(value))
        for job in value['jobs'].values():
            self.assertEqual(job['timeout-minutes'], 15)
            for step in job['steps']:
                if 'uses' in step:
                    self.assertRegex(step['uses'], r'@[0-9a-f]{40}$')
                if step.get('uses','').startswith('actions/checkout@'):
                    self.assertFalse(step['with']['persist-credentials'])

    def test_new_report_requires_exact_ids_all_phases_no_skips_and_no_real_authority(self):
        nodes = runner.selections()['protocol']
        expected = dict(head='a'*40, plan_sha256='b'*64)
        execution = dict(exitstatus=0,nodes=nodes,seconds=1,reports=[
            dict(nodeid=node,when=phase,outcome='passed',wasxfail=False,seconds=.001,skip_reason=None)
            for node in nodes for phase in ('setup','call','teardown')])
        report = dict(**expected,kind='phase5-m3-fixture-execution',group='protocol',success=True,ids_sha256=runner.digest(runner.IDS),inputs=runner.inputs(),
            collection=dict(exitstatus=0,nodes=nodes),execution=execution,authenticated_live_observations=0,
            real_decisions_consumed=0,real_package_approvals=0,operational_authority=False,
            native_artifacts=None)
        runner.verify(report,expected)
        for attack in ('head','missing-id','missing-phase','skip','xfail','live','decision','approval','authority','native'):
            altered = deepcopy(report)
            if attack == 'head': altered['head']='c'*40
            if attack == 'missing-id': altered['execution']['nodes']=nodes[:-1]
            if attack == 'missing-phase': altered['execution']['reports'].pop()
            if attack == 'skip': altered['execution']['reports'][1].update(outcome='skipped',skip_reason='injected')
            if attack == 'xfail': altered['execution']['reports'][1]['wasxfail']=True
            if attack == 'live': altered['authenticated_live_observations']=1
            if attack == 'decision': altered['real_decisions_consumed']=1
            if attack == 'approval': altered['real_package_approvals']=1
            if attack == 'authority': altered['operational_authority']=True
            if attack == 'native': altered['native_artifacts']={}
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                runner.verify(altered,expected)
