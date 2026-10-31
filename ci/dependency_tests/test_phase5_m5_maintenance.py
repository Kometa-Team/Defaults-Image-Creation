"""Independently approved M5/PR59 hashes, physical views and exact CI evidence."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from ci import phase5_m5_maintenance as m5
from ci import phase5_m5 as runner

ROOT=Path(__file__).resolve().parents[2]
EXPECTED={
    'ci/phase5_m4_maintenance.py':'fd92f30d1525616b17875595c9a3c1abd59b9440e11c0ac8c5660c4c60c08eee',
    'ci/dependency_tests/test_phase5_m4_maintenance.py':'38d8dde83e2f1a06bf666e476185544ba7c532186d260cd5afa1da56328a3442',
    'ci/people_job_retention_maintenance.py':'c4049fff0510e11591906aa77f99cdce78a7f79699248217659f779a44ee0736',
    'ci/dependency_tests/test_people_job_retention_maintenance.py':'2955e546701a6cb6fc7fc2771952d44dbc9f26350dab21fc76b145e7eda88be6',
    'create_defaults/lifecycle/ROADMAP.md':'79a722ebfd77be147b9375673ea77dbb44e6ef62ac325b6299bd77ec24a690e9',
}


class Phase5M5MaintenanceTests(unittest.TestCase):
    def test_pinned_predecessors_use_one_tree_and_one_blob_batch(self):
        from ci import people_colorize_maintenance as colorize
        m5._baseline_tree.cache_clear();m5._predecessors.cache_clear()
        m5._old.cache_clear();m5._baseline_entry.cache_clear()
        with patch.object(m5,'_git_raw',wraps=m5._git_raw) as git,patch.object(colorize,'_head',wraps=colorize._head) as head:
            first=m5.verify_checkout();m5.verify_checkout()
            commands=[call.args[1] for call in git.call_args_list]
            self.assertEqual(commands.count('ls-tree'),1)
            self.assertEqual(commands.count('cat-file'),1)
            self.assertNotIn('show',commands)
            self.assertEqual(head.call_count,2)
        for name in EXPECTED:self.assertEqual(m5.sha(m5._old(name)),first['members'][name]['before_sha256'])

    def test_batched_predecessors_reject_bad_tree_framing_objects_and_hashes(self):
        original=m5._git_raw
        tree=original(ROOT,'ls-tree','-z',m5.BASE,'--',*sorted(m5.MEMBERS))
        entries=m5._baseline_tree()
        batch=original(ROOT,'cat-file','--batch',input=b''.join(oid+b'\n' for _,oid in entries))
        for attack in (tree[:-1],tree+tree.split(b'\0')[0]+b'\0',tree.replace(b'100644',b'120000',1),
                tree.replace(entries[0][0].encode(),b'ci/unauthorized.py',1),tree.split(b'\0',1)[1]):
            m5._baseline_tree.cache_clear()
            with self.subTest(tree=attack[:70]),patch.object(m5,'_git_raw',return_value=attack),self.assertRaises(ValueError):m5._baseline_tree()
        m5._baseline_tree.cache_clear();m5._baseline_tree()
        header_end=batch.index(b'\n')
        for attack in (batch[:-1],batch+b'extra',batch.replace(b' blob ',b' tree ',1),
                b'f'*40+batch[40:],batch[:header_end+1]+bytes([batch[header_end+1]^1])+batch[header_end+2:]):
            m5._predecessors.cache_clear()
            with self.subTest(batch=attack[:70]),patch.object(m5,'_git_raw',return_value=attack),self.assertRaises(ValueError):m5._predecessors()
        m5._predecessors.cache_clear();m5._predecessors()

    def test_warm_immutable_caches_never_hide_fresh_parent_or_leaf_checks(self):
        import stat
        from types import SimpleNamespace
        m5.verify_checkout()
        name='ci/phase5_m4_maintenance.py';current=(ROOT/name).read_bytes();original=Path.lstat
        for target in (ROOT/'ci',ROOT/name):
            for link,reparse in ((True,False),(False,True)):
                def changed(path,*args,**kwargs):
                    info=original(path,*args,**kwargs)
                    return SimpleNamespace(st_mode=stat.S_IFLNK if link else info.st_mode,st_file_attributes=0x400 if reparse else 0) if path==target else info
                with self.subTest(path=str(target),link=link,reparse=reparse),patch.object(Path,'lstat',changed):
                    with self.assertRaises(ValueError):m5.verify_checkout()
                    with self.assertRaises(ValueError):m5.historical_bytes(ROOT,name,current)
                    raw=(f':100644 100644 '+ '0'*40+' '+'1'*40+f' M\0{name}\0').encode()
                    with patch.object(m5,'verify_checkout'),patch.object(m5,'_git',return_value=raw),self.assertRaises(ValueError):m5.verify_scope(ROOT,m5.BASE,{name})
        m5.verify_checkout()

    def test_five_independent_successors_exact_27_paths_and_predecessors(self):
        value=m5.verify_checkout()
        self.assertEqual(m5.BASE,'3c15fb56b63bababa5d216b8d885e7dee257c11d')
        self.assertEqual(len(m5.MEMBERS|m5.ANCHORS),27)
        self.assertEqual({n:b['sha256'] for n,b in value['members'].items() if b['before_sha256'] is not None},EXPECTED)
        for name,expected in EXPECTED.items():
            self.assertEqual(m5.sha((ROOT/name).read_bytes()),expected)
            self.assertEqual(m5.sha(m5._old(name)),value['members'][name]['before_sha256'])
        for field in ('production_intersection','adoption_intersection','frozen_m7_intersection'):self.assertEqual(value[field],[])
        self.assertIs(value['publication_authorized'],False)

    def test_every_physical_member_rejects_tamper_rollback_and_deletion(self):
        value=m5.verify_checkout();original=Path.read_bytes
        for name,binding in value['members'].items():
            variants=[original(ROOT/name)+b'\nunreviewed']
            if binding['before_sha256'] is not None:variants.append(m5._old(name))
            for replacement in variants:
                def changed(path):return replacement if path==ROOT/name else original(path)
                with self.subTest(name=name),patch.object(Path,'read_bytes',changed),self.assertRaises(ValueError):m5.verify_checkout()
            def missing(path):
                if path==ROOT/name:raise FileNotFoundError(name)
                return original(path)
            with self.subTest(missing=name),patch.object(Path,'read_bytes',missing),self.assertRaises(OSError):m5.verify_checkout()

    def test_historical_views_never_accept_physical_rollback_or_forged_input(self):
        original=Path.read_bytes
        for name in EXPECTED:
            current=original(ROOT/name);before=m5._old(name)
            self.assertEqual(m5.historical_bytes(ROOT,name,current),before)
            self.assertEqual(m5.historical_bytes(ROOT,name,before),before)
            with self.assertRaises(ValueError):m5.historical_bytes(ROOT,name,b'forged')
            def rollback(path):return before if path==ROOT/name else original(path)
            with patch.object(Path,'read_bytes',rollback),self.assertRaises(ValueError):m5.historical_bytes(ROOT,name,before)
        for name,pin in m5.RETAINED.items():
            before=m5._git(ROOT,'show','cd8d4eecd64f5bff201e8ecd7daccebd955f87af:'+name)
            self.assertEqual(m5.sha(before),pin)
            self.assertEqual(m5.historical_bytes(ROOT,name,before),before)

    def test_resealed_expansion_baseline_or_approved_hash_is_rejected(self):
        value=m5.manifest()
        for attack in ('expansion','baseline','approved','authority','intersection'):
            altered=deepcopy(value)
            if attack=='expansion':altered['members']['ci/unreviewed.py']=dict(before_sha256=None,sha256='f'*64)
            elif attack=='baseline':altered['baseline_commit']='f'*40
            elif attack=='approved':altered['members']['ci/phase5_m4_maintenance.py']['sha256']='f'*64
            elif attack=='authority':altered['publication_authorized']=True
            else:altered['production_intersection']=['production.py']
            with self.subTest(attack=attack),self.assertRaises(ValueError):m5._decode(json.dumps(altered).encode(),m5.fingerprint(altered))
        raw=json.dumps(dict(value,extra='unreviewed')).encode()
        with self.assertRaises(ValueError):m5._decode(raw,m5.fingerprint(json.loads(raw)))

    def test_foreign_checkout_and_unknown_or_unsafe_scope_fail(self):
        from ci import phase4_m7
        with self.assertRaises(ValueError):m5.verify_checkout(ROOT/'foreign')
        name='ci/phase5_m4_maintenance.py'
        with self.assertRaises(ValueError):m5.historical_bytes(ROOT/'foreign',name,(ROOT/name).read_bytes())
        with patch.object(phase4_m7,'ROOT',ROOT/'foreign'):self.assertEqual(m5.scope_members(),frozenset())
        with patch.object(m5,'verify_checkout'):
            with self.assertRaises(ValueError):m5.verify_scope(ROOT,m5.BASE,{'unreviewed.py'})
            for old,new,status in [('100644','000000','D'),('000000','120000','A'),('100644','100644','R100')]:
                raw=(f':{old} {new} '+'0'*40+' '+'1'*40+f' {status}\0{name}\0').encode()
                with patch.object(m5,'_git',return_value=raw),self.assertRaisesRegex(ValueError,'regular-file'):m5.verify_scope(ROOT,m5.BASE,{name})
            with patch.object(m5,'_git',return_value=b''),self.assertRaises(ValueError):m5.verify_scope(ROOT,m5.BASE,{name})

    def test_original_inventories_workflows_ids_and_gate_are_unchanged(self):
        names=['ci/phase5-m2-maintenance-v1.json','ci/phase5-m3-maintenance-v1.json','ci/phase5-m4-maintenance-v1.json',
            'ci/people-job-retention-maintenance-v1.json','ci/phase5-m2-test-ids.json','ci/phase5-m3-test-ids.json',
            'ci/phase5-m4-test-ids.json','ci/original-test-ids.json','ci/validation.py','ci/phase4_m7.py',
            'create_defaults/bulk/contracts/activation/data/production-pins-v1.json',
            'create_defaults/bulk/contracts/adoption/source-pins-v1.json',
            'create_defaults/bulk/lifecycle/mappings.py','create_defaults/bulk/library_transport.py']
        names += m5._git(ROOT,'ls-tree','-r','--name-only',m5.BASE,'.github/workflows').decode().splitlines()
        for name in names:self.assertEqual(m5.sha((ROOT/name).read_bytes()),m5.sha(m5._old(name)),name)
        production=set(json.loads((ROOT/names[10]).read_bytes())['files'])
        adopted={r['path'] for r in json.loads((ROOT/names[11]).read_bytes())['files']}
        frozen=set(m5._git(ROOT,'ls-tree','-r','--name-only','68179d1c568449375ca72b23239b57770dfc229e','ci','.github/workflows','create_defaults').decode().splitlines())-{'create_defaults/lifecycle/ROADMAP.md'}
        self.assertEqual((len(production),len(adopted),len(frozen)),(190,299,2927))
        for inventory in (production,adopted,frozen):self.assertFalse(inventory&(m5.MEMBERS|m5.ANCHORS))

    def test_all_original_M4_and_retention_dependency_test_names_are_preserved(self):
        def names(raw):return sorted(n.name for n in ast.walk(ast.parse(raw)) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_'))
        for name,count in [('ci/dependency_tests/test_phase5_m4_maintenance.py',10),('ci/dependency_tests/test_people_job_retention_maintenance.py',8)]:
            self.assertEqual(names((ROOT/name).read_bytes()),names(m5._old(name)))
            self.assertEqual(len(names((ROOT/name).read_bytes())),count)

    def test_composed_M2_M3_M4_and_PR59_actual_verifiers(self):
        from ci import phase5_m2_maintenance,phase5_m3_maintenance,phase5_m4_maintenance,people_job_retention_maintenance
        for module in (phase5_m2_maintenance,phase5_m3_maintenance,phase5_m4_maintenance,people_job_retention_maintenance):
            self.assertFalse(module.verify_checkout()['publication_authorized'])
        name='create_defaults/lifecycle/ROADMAP.md'
        older=phase5_m4_maintenance.historical_bytes(ROOT,name,(ROOT/name).read_bytes())
        self.assertEqual(m5.historical_bytes(ROOT,name,older),older)
        self.assertEqual(phase5_m3_maintenance.sha(phase5_m3_maintenance.historical_bytes(ROOT,name,older)),
            phase5_m3_maintenance.manifest()['members'][name]['before_sha256'])

    def test_workflow_remains_pinned_readonly_bounded_and_both_platforms(self):
        import yaml
        value=yaml.safe_load((ROOT/'.github/workflows/phase5-m5-validation.yml').read_bytes())
        self.assertEqual(value['permissions'],{'contents':'read'})
        self.assertEqual(set(value['jobs']['m5']['strategy']['matrix']['os']),{'windows-latest','ubuntu-latest'})
        self.assertEqual(set(value['jobs']['m5']['strategy']['matrix']['group']),set(runner.GROUPS))
        for job in value['jobs'].values():
            self.assertEqual(job['timeout-minutes'],15)
            for step in job['steps']:
                if 'uses' in step:self.assertRegex(step['uses'],r'@[0-9a-f]{40}$')
                if step.get('uses','').startswith('actions/checkout@'):self.assertFalse(step['with']['persist-credentials'])
        self.assertNotIn('GH_TOKEN',json.dumps(value))
        acceptance=json.loads((ROOT/'create_defaults/lifecycle/PHASE5_M5_ACCEPTANCE.json').read_bytes())
        self.assertEqual(len(acceptance['required_workflows']),10)
        self.assertTrue(all(acceptance['test_requirements'].values()))

    def test_exact_report_rejects_missing_ID_phase_skip_xfail_or_authority(self):
        nodes=runner.selections()['protocol'];expected=dict(head='a'*40,plan_sha256='b'*64)
        execution=dict(exitstatus=0,nodes=nodes,reports=[dict(nodeid=node,when=phase,outcome='passed',
            wasxfail=False,seconds=.001,skip_reason=None) for node in nodes for phase in ('setup','call','teardown')])
        report=dict(**expected,kind='phase5-m5-fixture-execution',success=True,group='protocol',ids_sha256=runner.digest(runner.IDS),
            inputs=runner.inputs(),collection=dict(exitstatus=0,nodes=nodes),execution=execution,
            operational_authority=False,real_operations_applied=0,real_package_approvals=0,native_artifacts=None)
        runner.verify(report,expected)
        for attack in ('head','id','phase','skip','xfail','authority','native'):
            value=deepcopy(report)
            if attack=='head':value['head']='c'*40
            elif attack=='id':value['execution']['nodes']=nodes[:-1]
            elif attack=='phase':value['execution']['reports'].pop()
            elif attack=='skip':value['execution']['reports'][1]['outcome']='skipped'
            elif attack=='xfail':value['execution']['reports'][1]['wasxfail']=True
            elif attack=='authority':value['operational_authority']=True
            else:value['native_artifacts']={}
            with self.subTest(attack=attack),self.assertRaises(ValueError):runner.verify(value,expected)
