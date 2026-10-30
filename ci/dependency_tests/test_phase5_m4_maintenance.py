"""Independent M4 exact-source successor and unchanged-boundary controls."""
from copy import deepcopy
import ast
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from ci import phase5_m4_maintenance as maintenance
from ci import phase5_m4 as runner

ROOT=Path(__file__).resolve().parents[2]
APPROVED={
    'ci/dependabot_maintenance.py':'b3eaa38e945dcedf39a28578f9ded1fec555c2d909c7aaee4b0712344a8faeb5',
    'ci/dependency_tests/test_phase5_m3_maintenance.py':'159aa71d339c00a11d62adc8be9ec713c2d054c333da2c619bfced51aae59c9e',
    'ci/phase5_m3_maintenance.py':'e449d0fed2bbcddb84027b81198941dfbf03c6af9fe13d1b18bf3fdb7cb0ce7c',
    'create_defaults/bulk/lifecycle/apply.py':'2f43fb9757020d5ba4e576afa0ced6a436dc3e47c8ada7e9d7976795370d6056',
    'create_defaults/bulk/lifecycle/mappings.py':'69ad60140dfec8cdecda9d12d3fac5e40a47e5b69444c43e230945d8abb9f6b8',
    'create_defaults/bulk/lifecycle/recovery.py':'246574f6974363d4f862e9d5e279db724a443537bcb18202de1f50c94dc7097d',
    'create_defaults/lifecycle/ROADMAP.md':'c830b33101d202e6118c84c7d63ccf40b0a7639eefcaa6687d73e2c9469d87fc',
}


class Phase5M4MaintenanceTests(unittest.TestCase):
    def test_exact_cohort_and_seven_independently_reviewed_successors(self):
        value=maintenance.verify_checkout()
        self.assertEqual(len(maintenance.MEMBERS|maintenance.ANCHORS),22)
        self.assertEqual(value['production_intersection'],[])
        self.assertEqual(value['adoption_intersection'],[])
        self.assertEqual(set(value['frozen_m7_intersection']),maintenance.FROZEN)
        changed={n for n,b in value['members'].items() if b['before_sha256'] is not None}
        self.assertEqual(changed,set(APPROVED))
        for name,expected in APPROVED.items():
            self.assertEqual(maintenance.sha((ROOT/name).read_bytes()),expected,name)
            self.assertEqual(value['members'][name]['sha256'],expected)
            self.assertEqual(maintenance.sha(maintenance._old(name)),value['members'][name]['before_sha256'])

    def test_each_member_rejects_tamper_rollback_and_deletion(self):
        value=maintenance.verify_checkout();original=Path.read_bytes
        for name,binding in value['members'].items():
            variants=[original(ROOT/name)+b'\nunreviewed']
            if binding['before_sha256'] is not None:variants.append(maintenance._old(name))
            for replacement in variants:
                def changed(path):return replacement if path==ROOT/name else original(path)
                with self.subTest(name=name),patch.object(Path,'read_bytes',changed),self.assertRaises(ValueError):
                    maintenance.verify_checkout()
            def missing(path):
                if path==ROOT/name:raise FileNotFoundError(name)
                return original(path)
            with self.subTest(missing=name),patch.object(Path,'read_bytes',missing),self.assertRaises(OSError):
                maintenance.verify_checkout()

    def test_historical_projection_verifies_physical_successor_before_double_projection(self):
        for name in APPROVED:
            current=(ROOT/name).read_bytes();before=maintenance._old(name)
            self.assertEqual(maintenance.historical_bytes(ROOT,name,current),before)
            self.assertEqual(maintenance.historical_bytes(ROOT,name,before),before)
            original=Path.read_bytes
            def rollback(path):return before if path==ROOT/name else original(path)
            with self.subTest(name=name),patch.object(Path,'read_bytes',rollback),self.assertRaises(ValueError):
                maintenance.historical_bytes(ROOT,name,before)
            with self.assertRaises(ValueError):maintenance.historical_bytes(ROOT,name,b'forged')

    def test_manifest_rejects_resealing_expansion_baseline_or_authority(self):
        original=Path.read_bytes
        for key in ('members','baseline_commit','production_intersection','adoption_intersection',
                    'frozen_m7_intersection','publication_authorized'):
            value=deepcopy(maintenance.manifest());value[key]='unreviewed';raw=json.dumps(value).encode()
            def changed(path):return raw if path==maintenance.MANIFEST else original(path)
            with self.subTest(key=key),patch.object(Path,'read_bytes',changed),self.assertRaises(ValueError):maintenance.manifest()

    def test_scope_rejects_unknown_paths_delete_rename_and_links(self):
        with patch.object(maintenance,'verify_checkout'):
            with self.assertRaisesRegex(ValueError,'Unapproved M4 scope'):
                maintenance.verify_scope(ROOT,maintenance.BASE,{'future-milestone.py'})
            name='create_defaults/bulk/lifecycle/current_mapping.py'
            for before,after,status in [('100644','000000','D'),('000000','120000','A'),('100644','100644','R100')]:
                raw=(f':{before} {after} '+'0'*40+' '+'1'*40+f' {status}\0{name}\0').encode()
                with patch.object(maintenance,'_git',return_value=raw),self.assertRaisesRegex(ValueError,'regular-file'):
                    maintenance.verify_scope(ROOT,maintenance.BASE,{name})

    def test_original_manifests_workflows_ids_and_M5_gate_stay_unchanged(self):
        names=['ci/phase5-m2-maintenance-v1.json','ci/phase5-m3-maintenance-v1.json',
            'ci/phase5-m2-test-ids.json','ci/phase5-m3-test-ids.json','ci/phase4-m7-test-ids.json',
            'ci/original-test-ids.json','ci/validation.py','ci/phase4_m7.py',
            'create_defaults/bulk/contracts/activation/data/production-pins-v1.json',
            'create_defaults/bulk/contracts/adoption/source-pins-v1.json']
        names += ['.github/workflows/'+n for n in ('default-poster-validation.yml','dependency-provenance-validation.yml',
            'lifecycle-m6-validation.yml','lifecycle-m7-validation.yml','people-storage-validation.yml',
            'phase5-m2-validation.yml','phase5-m3-validation.yml')]
        for name in names:
            self.assertEqual(maintenance.sha((ROOT/name).read_bytes()),maintenance.sha(maintenance._old(name)),name)
        def function(raw,name):
            return ast.dump(next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name==name))
        name='create_defaults/bulk/lifecycle/mappings.py'
        self.assertEqual(function((ROOT/name).read_bytes(),'require_m5_compatible'),function(maintenance._old(name),'require_m5_compatible'))
        from ci.phase4_m7 import ALLOWED
        self.assertFalse(maintenance.scope_members()&ALLOWED)

    def test_foreign_planning_repository_does_not_inherit_runtime_scope(self):
        from ci import phase4_m7
        with patch.object(phase4_m7,'ROOT',ROOT/'unowned-inspection-target'):
            self.assertEqual(maintenance.scope_members(),frozenset())
            with patch.object(maintenance,'verify_checkout'),self.assertRaisesRegex(ValueError,'Unapproved M4 scope'):
                maintenance.verify_scope(ROOT,maintenance.BASE,set(maintenance.FROZEN))

    def test_closed_coverage_has_every_exact_package_and_variant(self):
        value=json.loads((ROOT/'create_defaults/lifecycle/PHASE5_M4_COVERAGE.json').read_bytes())
        release=json.loads((ROOT/'create_defaults/bulk/contracts/categories/data/release-v1.json').read_bytes())
        expected=set()
        for entry in release['entries']:
            contract=json.loads((ROOT/'create_defaults/bulk/contracts'/entry['contract_path']).read_bytes())
            expected.update((entry['category'],entry['kind'],entry['contract_sha256'],v['id']) for v in contract['variants'])
        actual={(r['category'],r['kind'],r['contract_sha256'],r['variant']) for r in value['variants']}
        self.assertEqual(len(expected),278);self.assertEqual(actual,expected)
        self.assertEqual(len(value['packages']),22)
        selected=[r for r in value['variants'] if r['disposition']!='blocked']
        self.assertEqual(len(selected),27)
        self.assertTrue(all(r['category']=='Genre' and r['source_kind']=='logo' and r['required_presentations']==['single'] for r in selected))
        self.assertFalse(value['production_authorized'])

    def test_workflow_is_readonly_bounded_pinned_and_both_platforms(self):
        import yaml
        value=yaml.safe_load((ROOT/'.github/workflows/phase5-m4-validation.yml').read_bytes())
        self.assertEqual(value['permissions'],{'contents':'read'})
        self.assertEqual(set(value['jobs']['m4']['strategy']['matrix']['os']),{'windows-latest','ubuntu-latest'})
        self.assertEqual(set(value['jobs']['m4']['strategy']['matrix']['group']),set(runner.GROUPS))
        for job in value['jobs'].values():
            self.assertEqual(job['timeout-minutes'],15)
            for step in job['steps']:
                if 'uses' in step:self.assertRegex(step['uses'],r'@[0-9a-f]{40}$')
                if step.get('uses','').startswith('actions/checkout@'):self.assertFalse(step['with']['persist-credentials'])
        self.assertNotIn('GH_TOKEN',json.dumps(value))

    def test_report_requires_exact_head_ids_three_phases_and_no_skip_or_authority(self):
        nodes=runner.selections()['protocol'];expected=dict(head='a'*40,plan_sha256='b'*64)
        execution=dict(exitstatus=0,nodes=nodes,reports=[dict(nodeid=node,when=phase,outcome='passed',
            wasxfail=False,seconds=.001,skip_reason=None) for node in nodes for phase in ('setup','call','teardown')])
        report=dict(**expected,kind='phase5-m4-fixture-execution',success=True,group='protocol',
            ids_sha256=runner.digest(runner.IDS),inputs=runner.inputs(),collection=dict(exitstatus=0,nodes=nodes),
            execution=execution,operational_authority=False,real_operations_applied=0,real_package_approvals=0,native_artifacts=None)
        runner.verify(report,expected)
        for attack in ('head','id','phase','skip','xfail','authority','operation','approval','native'):
            value=deepcopy(report)
            if attack=='head':value['head']='c'*40
            if attack=='id':value['execution']['nodes']=nodes[:-1]
            if attack=='phase':value['execution']['reports'].pop()
            if attack=='skip':value['execution']['reports'][1]['outcome']='skipped'
            if attack=='xfail':value['execution']['reports'][1]['wasxfail']=True
            if attack=='authority':value['operational_authority']=True
            if attack=='operation':value['real_operations_applied']=1
            if attack=='approval':value['real_package_approvals']=1
            if attack=='native':value['native_artifacts']={}
            with self.subTest(attack=attack),self.assertRaises(ValueError):runner.verify(value,expected)
