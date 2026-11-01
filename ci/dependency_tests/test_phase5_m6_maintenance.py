"""Independent exact scope, fresh physical evidence and historical composition."""
import ast,json,unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from ci import phase5_m6_maintenance as m6

ROOT=m6.ROOT


class Phase5M6MaintenanceTests(unittest.TestCase):
    def test_eight_exact_successors_and_30_paths(self):
        value=m6.verify_checkout()
        self.assertEqual(len(m6.MEMBERS|m6.ANCHORS),34)
        self.assertEqual(len(m6.APPROVED),12)
        for name,(old,new) in m6.APPROVED.items():
            self.assertEqual(m6.sha((ROOT/name).read_bytes()),new)
            self.assertEqual(m6.sha(m6._old(name)),old)
            self.assertEqual(value['members'][name],dict(before_sha256=old,sha256=new))

    def test_every_physical_member_rejects_tamper_rollback_missing(self):
        original=Path.read_bytes;value=m6.verify_checkout()
        for name,row in value['members'].items():
            variants=[original(ROOT/name)+b'\nunreviewed']
            if name in m6.APPROVED:variants.append(m6._old(name))
            for raw in variants:
                def changed(path):return raw if path==ROOT/name else original(path)
                with self.subTest(name=name),patch.object(Path,'read_bytes',changed),self.assertRaises(ValueError):m6.verify_checkout()
            def missing(path):
                if path==ROOT/name:raise FileNotFoundError(name)
                return original(path)
            with self.subTest(missing=name),patch.object(Path,'read_bytes',missing),self.assertRaises(OSError):m6.verify_checkout()

    def test_projection_requires_current_physical_successors(self):
        original=Path.read_bytes
        for name in m6.APPROVED:
            before=m6._old(name)
            self.assertEqual(m6.historical_bytes(ROOT,name,original(ROOT/name)),before)
            self.assertEqual(m6.historical_bytes(ROOT,name,before),before)
            with self.assertRaises(ValueError):m6.historical_bytes(ROOT,name,b'forged')
            def rollback(path):return before if path==ROOT/name else original(path)
            with patch.object(Path,'read_bytes',rollback),self.assertRaises(ValueError):m6.historical_bytes(ROOT,name,before)
        unrelated='create_defaults/bulk/lifecycle/draft_models.py'
        def tamper(path):return b'changed' if path==ROOT/unrelated else original(path)
        with patch.object(Path,'read_bytes',tamper),self.assertRaises(ValueError):m6.historical_bytes(ROOT,name,before)

    def test_resealed_unknown_membership_and_successor_rejected(self):
        for attack in ('member','baseline','hash','authority','intersection','extra'):
            v=deepcopy(m6.manifest())
            if attack=='member':v['members']['foreign.py']=dict(before_sha256=None,sha256='a'*64)
            elif attack=='baseline':v['baseline_commit']='a'*40
            elif attack=='hash':v['members'][next(iter(m6.APPROVED))]['sha256']='a'*64
            elif attack=='authority':v['publication_authorized']=True
            elif attack=='intersection':v['production_intersection']=[]
            else:v['unreviewed']=True
            with self.subTest(attack=attack),self.assertRaises(ValueError):m6._decode(json.dumps(v).encode(),m6.fingerprint(v))

    def test_exact_m5_predecessor_view_keeps_physical_and_foreign_guards(self):
        from ci import phase5_m5_maintenance as m5
        name='ci/dependency_tests/test_people_job_retention_maintenance.py'
        pin='c8e03edba1c697e73995d584d5026099273965098479297daf0a7f064fe50258'
        before=m5._old(name)
        self.assertEqual(m6.RETAINED[name],[pin])
        self.assertEqual(m5.APPROVED[name][0],pin)
        self.assertEqual(m5.manifest()['members'][name]['before_sha256'],pin)
        self.assertEqual(m6.sha(m6._git(ROOT,'show',m5.BASE+':'+name)),pin)
        self.assertEqual(m6.sha(before),pin)
        self.assertEqual(m6.historical_bytes(ROOT,name,before),before)
        self.assertEqual(m5.historical_bytes(ROOT,name,before),before)
        for forged in (b'forged',before+b'\n'):
            with self.assertRaises(ValueError):m6.historical_bytes(ROOT,name,forged)
        with self.assertRaises(ValueError):m6.historical_bytes(ROOT/'foreign',name,before)
        with self.assertRaises(ValueError):m6.historical_bytes(ROOT,'create_defaults/lifecycle/ROADMAP.md',before)
        original=Path.read_bytes
        for replacement in (before,m6._old(name),original(ROOT/name)+b'\nunreviewed'):
            def changed(path):return replacement if path==ROOT/name else original(path)
            with patch.object(Path,'read_bytes',changed),self.assertRaises(ValueError):m6.historical_bytes(ROOT,name,before)
        def missing(path):
            if path==ROOT/name:raise FileNotFoundError(name)
            return original(path)
        with patch.object(Path,'read_bytes',missing),self.assertRaises(OSError):m6.historical_bytes(ROOT,name,before)
        other=ROOT/'create_defaults/bulk/lifecycle/draft_models.py'
        def tampered_cohort(path):return b'changed' if path==other else original(path)
        with patch.object(Path,'read_bytes',tampered_cohort),self.assertRaises(ValueError):m6.historical_bytes(ROOT,name,before)

    def test_immutable_batching_and_fresh_head_observations(self):
        from ci import people_colorize_maintenance as color
        m6._baseline_tree.cache_clear();m6._predecessors.cache_clear();m6._old.cache_clear();m6._baseline_entry.cache_clear()
        with patch.object(m6,'_git_raw',wraps=m6._git_raw) as git,patch.object(color,'_head',wraps=color._head) as head:
            m6.verify_checkout();m6.verify_checkout()
        commands=[call.args[1] for call in git.call_args_list]
        self.assertEqual(commands.count('ls-tree'),1);self.assertEqual(commands.count('cat-file'),1)
        self.assertEqual(commands.count('show'),0);self.assertEqual(head.call_count,2)

    def test_foreign_checkout_and_scope_fail_closed(self):
        with self.assertRaises(ValueError):m6.verify_checkout(ROOT/'foreign')
        name=next(iter(m6.APPROVED))
        with self.assertRaises(ValueError):m6.historical_bytes(ROOT/'foreign',name,(ROOT/name).read_bytes())
        from ci import phase4_m7
        with patch.object(phase4_m7,'ROOT',ROOT/'foreign'):self.assertFalse(m6.scope_members())
        with patch.object(m6,'verify_checkout'):
            with self.assertRaises(ValueError):m6.verify_scope(ROOT,m6.BASE,{'foreign.py'})
            for old,new,status in [('100644','000000','D'),('000000','120000','A'),('100644','100644','R100')]:
                raw=(f':{old} {new} '+'0'*40+' '+'1'*40+f' {status}\0{name}\0').encode()
                with patch.object(m6,'_git',return_value=raw),self.assertRaises(ValueError):m6.verify_scope(ROOT,m6.BASE,{name})

    def test_original_inventories_ids_workflows_and_test_names_unchanged(self):
        names=['create_defaults/bulk/contracts/activation/data/production-pins-v1.json',
            'create_defaults/bulk/contracts/adoption/source-pins-v1.json','ci/original-test-ids.json',
            'ci/validation.py','ci/phase4_m7.py','create_defaults/bulk/library_transport.py']
        names+=m6._git(ROOT,'ls-tree','-r','--name-only',m6.BASE,'.github/workflows').decode().splitlines()
        for milestone in ('m2','m3','m4','m5'):names+=['ci/phase5-'+milestone+'-test-ids.json','ci/phase5-'+milestone+'-maintenance-v1.json']
        names+=['ci/people-job-retention-maintenance-v1.json']
        for name in names:self.assertEqual(m6.sha((ROOT/name).read_bytes()),m6.sha(m6._old(name)),name)
        prod=set(json.loads((ROOT/names[0]).read_bytes())['files'])
        adopted={r['path'] for r in json.loads((ROOT/names[1]).read_bytes())['files']}
        frozen=set(m6._git(ROOT,'ls-tree','-r','--name-only','68179d1c568449375ca72b23239b57770dfc229e','ci','.github/workflows','create_defaults').decode().splitlines())-{'create_defaults/lifecycle/ROADMAP.md'}
        self.assertEqual((len(prod),len(adopted),len(frozen)),(190,299,2927))
        for inventory,key in [(prod,'production_intersection'),(adopted,'adoption_intersection'),(frozen,'frozen_m7_intersection')]:
            self.assertEqual(sorted(inventory&(m6.MEMBERS|m6.ANCHORS)),sorted(m6.INTERSECTIONS[key]))
        name='ci/dependency_tests/test_phase5_m5_maintenance.py'
        def tests(raw):return sorted(n.name for n in ast.walk(ast.parse(raw)) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_'))
        self.assertEqual(tests((ROOT/name).read_bytes()),tests(m6._old(name)))

    def test_composed_historical_verifiers_and_selected_pins(self):
        from ci import phase5_m2_maintenance,phase5_m3_maintenance,phase5_m4_maintenance,phase5_m5_maintenance,people_job_retention_maintenance
        for module in (phase5_m2_maintenance,phase5_m3_maintenance,phase5_m4_maintenance,phase5_m5_maintenance,people_job_retention_maintenance):
            self.assertFalse(module.verify_checkout()['publication_authorized'])
        for name,(before,after) in m6.APPROVED.items():
            if name.startswith('create_defaults/bulk/'):
                self.assertEqual(m6.selected_hash(name,before),after)
                self.assertEqual(m6.selected_hash(name,'a'*64),'a'*64)

    def test_storage_pin_reaches_unchanged_historical_guards(self):
        from ci import dependabot_maintenance as audit,people_readme_maintenance as readme
        name='ci/people_storage_maintenance.py';before,after=m6.APPROVED[name]
        self.assertEqual(audit.selected_hash(name,before),after)
        self.assertEqual(readme.selected_hash(name,before),after)
        original=readme.manifest()['members'][name]['before_sha256']
        self.assertEqual(readme.selected_hash(name,original),after)
        for module in (m6,audit,readme):
            self.assertEqual(module.selected_hash(name,'f'*64),'f'*64)
            self.assertEqual(module.selected_hash('foreign.py',before),before)
        # The approved storage historical comparison must retain its old pin.
        dependency='ci/dependency_maintenance.py'
        self.assertEqual(m6.selected_hash(dependency,m6.APPROVED[dependency][0]),m6.APPROVED[dependency][0])
        original_bytes=Path.read_bytes
        for target in (name,'create_defaults/bulk/lifecycle/draft_models.py'):
            def tamper(path):return b'forged' if path==ROOT/target else original_bytes(path)
            with self.subTest(target=target),patch.object(Path,'read_bytes',tamper),self.assertRaises(ValueError):
                audit.selected_hash(name,before)

    def test_shared_operations_schema_cache_is_byte_keyed_and_bounded(self):
        from create_defaults.bulk.lifecycle import models
        raw=(ROOT/'create_defaults/bulk/lifecycle/schemas/operations-v1.schema.json').read_bytes()
        models.validator.cache_clear();models._compiled_schema.cache_clear()
        try:
            with patch.object(models.Draft202012Validator,'check_schema',wraps=models.Draft202012Validator.check_schema) as validate:
                for _ in range(8):
                    for kind in ('head-key','head-reference','operation-record','operation-event'):
                        list(models.validator(kind).iter_errors({}))
                self.assertEqual(validate.call_count,1)
            self.assertEqual(models.validator.cache_info().maxsize,2)
            self.assertEqual(models._compiled_schema.cache_info().maxsize,1)
            previous=models._compiled_schema(raw)
            for invalid in (b'not JSON',b'{"type":"not-a-json-schema-type"}'):
                with self.assertRaises(Exception):models._compiled_schema(invalid)
            self.assertIs(models._compiled_schema(raw),previous)
            # Re-reading a changed physical schema on a validator miss must
            # reject it instead of substituting a cached old observation.
            original=Path.read_bytes;schema=ROOT/'create_defaults/bulk/lifecycle/schemas/operations-v1.schema.json'
            def changed(path):return b'not JSON' if path==schema else original(path)
            models.validator.cache_clear()
            with patch.object(Path,'read_bytes',changed),self.assertRaises(Exception):models.validator('head-reference')
        finally:models.validator.cache_clear();models._compiled_schema.cache_clear()

    def test_actual_storage_infrastructure_and_original_guards(self):
        from ci import people_storage_maintenance as storage
        self.assertTrue(storage.verify(ROOT))
        name='ci/dependency_maintenance.py';actual=(ROOT/name).read_bytes()
        self.assertEqual(m6.sha(actual),m6.APPROVED[name][1])
        self.assertEqual(m6.sha(m6.historical_bytes(ROOT,name,actual)),m6.APPROVED[name][0])
        original=Path.read_bytes
        def changed(path):return b'forged' if path==ROOT/name else original(path)
        with patch.object(Path,'read_bytes',changed),self.assertRaises(ValueError):storage.verify(ROOT)

    def test_json_precheck_preserves_original_errors_and_limits(self):
        import math
        from create_defaults.bulk.contracts import models
        names={'_json_value','_pairs','decode_json'}
        nodes=[n for n in ast.parse(m6._old('create_defaults/bulk/contracts/models.py')).body
            if isinstance(n,ast.FunctionDef) and n.name in names]
        namespace=dict(MAX_DEPTH=models.MAX_DEPTH,MAX_BYTES=models.MAX_BYTES,
            BulkError=models.BulkError,json=json,math=math)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'<pinned-original-json>','exec'),namespace)
        def outcome(function,value):
            try:return ('accepted',function(value))
            except Exception as error:return ('rejected',type(error).__name__,getattr(error,'code',None),str(error))
        vectors=['','ASCII','\x00\x1f\x7f','é','漢字','🐶','e\u0301',chr(0xd7ff),chr(0xe000),chr(0x10ffff)]
        vectors += [chr(n) for n in range(0xd800,0xe000)]
        vectors += [None,True,False,0,-1,1.5,float('inf'),float('-inf'),float('nan'),[],{},(),set(),b'bytes',object(),{1:'bad key'}]
        vectors += [{'nested':[s]} for s in ['',chr(0xd800),chr(0xdfff),'native 日本語']]
        for value in vectors:
            self.assertEqual(outcome(models._json_value,value),outcome(namespace['_json_value'],value))
        raw_vectors=[b'{}',b'{"x":1,"x":2}',b'{"x":NaN}',b'"\\ud800"',b'"\\udfff"',b'"\\ud83d\\udc36"',
            b'"ASCII\\u0000"',b'[]',b'\xff',b'['*42+b'0'+b']'*42,b'"'+b'x'*models.MAX_BYTES+b'"']
        for raw in raw_vectors:self.assertEqual(outcome(models.decode_json,raw),outcome(namespace['decode_json'],raw))

    def test_ascii_avoids_only_redundant_surrogate_scan(self):
        import builtins
        from create_defaults.bulk.contracts import models
        with patch.dict(models.__dict__,ord=unittest.mock.Mock(wraps=builtins.ord)):
            models._json_value('x'*(1024*1024))
            self.assertEqual(models.ord.call_count,0)
            models._json_value('é')
            self.assertEqual(models.ord.call_count,1)
            with self.assertRaises(models.BulkError):models._json_value(chr(0xd800))
            self.assertEqual(models.ord.call_count,2)

    def test_actual_report_requires_every_ID_phase_and_no_authority(self):
        from ci import phase5_m6 as runner
        nodes=runner.selections()['protocol'];expected=dict(head='a'*40,plan_sha256='b'*64)
        reports=[dict(nodeid=n,when=phase,outcome='passed',wasxfail=False,seconds=.001,skip_reason=None)
            for n in nodes for phase in ('setup','call','teardown')]
        report=dict(**expected,kind='phase5-m6-fixture-execution',success=True,group='protocol',
            ids_sha256=runner.digest(runner.IDS),inputs=runner.inputs(),collection=dict(exitstatus=0,nodes=nodes),
            execution=dict(exitstatus=0,nodes=nodes,reports=reports),operational_authority=False,
            real_operations_applied=0,real_package_approvals=0,native_artifacts=None)
        runner.verify(report,expected)
        for attack in ('id','phase','skip','xfail','authority','native'):
            value=deepcopy(report)
            if attack=='id':value['execution']['nodes']=nodes[:-1]
            elif attack=='phase':value['execution']['reports'].pop()
            elif attack=='skip':value['execution']['reports'][1]['outcome']='skipped'
            elif attack=='xfail':value['execution']['reports'][1]['wasxfail']=True
            elif attack=='authority':value['operational_authority']=True
            else:value['native_artifacts']={}
            with self.subTest(attack=attack),self.assertRaises(ValueError):runner.verify(value,expected)

    def test_new_workflow_exact_ID_matrix_readonly_and_bounded(self):
        import yaml
        from ci import phase5_m6 as runner
        value=yaml.safe_load((ROOT/'.github/workflows/phase5-m6-validation.yml').read_bytes())
        self.assertEqual(value['permissions'],{'contents':'read'})
        self.assertEqual(set(value['jobs']['m6']['strategy']['matrix']['os']),{'windows-latest','ubuntu-latest'})
        self.assertEqual(set(value['jobs']['m6']['strategy']['matrix']['group']),set(runner.GROUPS))
        for name,job in value['jobs'].items():
            timeout="${{ matrix.group == 'transport' && 30 || 15 }}" if name=='m6' else 15
            self.assertEqual(job['timeout-minutes'],timeout)
            for step in job['steps']:
                if 'uses' in step:self.assertRegex(step['uses'],r'@[0-9a-f]{40}$')
                if step.get('uses','').startswith('actions/checkout@'):self.assertFalse(step['with']['persist-credentials'])
        self.assertNotIn('GH_TOKEN',json.dumps(value))
        contract=json.loads((ROOT/'create_defaults/lifecycle/PHASE5_M6_ACCEPTANCE.json').read_bytes())
        self.assertEqual(len(contract['required_workflows']),11)
        self.assertEqual(contract['platform_groups'],{p:list(runner.GROUPS) for p in ('Windows','Linux')})
        self.assertEqual(contract['budgets']['job_timeout_minutes'],15)
        self.assertEqual(contract['budgets']['native_transport_integration_timeout_seconds'],1800)
        self.assertEqual(contract['budgets']['native_transport_integration_job_timeout_minutes'],30)
        self.assertEqual(contract['budgets']['native_transport_integration_group'],'transport')
        self.assertEqual(runner.selections()['transport'],[contract['budgets']['native_transport_integration_test']])


if __name__=='__main__':unittest.main()
