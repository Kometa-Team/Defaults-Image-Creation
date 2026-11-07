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
        from ci import people_colorize_maintenance as colorize,phase5_m6_maintenance as m6
        m5._baseline_tree.cache_clear();m5._predecessors.cache_clear()
        m5._old.cache_clear();m5._baseline_entry.cache_clear()
        with patch.object(m5,'_git_raw',wraps=m5._git_raw) as git,patch.object(colorize,'_head',wraps=colorize._head) as head,patch.object(m6,'verify_checkout',wraps=m6.verify_checkout) as successor:
            first=m5.verify_checkout();m5.verify_checkout()
            commands=[call.args[1] for call in git.call_args_list]
            self.assertEqual(commands.count('ls-tree'),1)
            self.assertEqual(commands.count('cat-file'),1)
            self.assertNotIn('show',commands)
            # Preserve two original fresh M5 observations plus two M6 proofs.
            self.assertEqual(successor.call_count,2)
            self.assertEqual(head.call_count-successor.call_count,2)
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
            from ci.phase5_m6_maintenance import historical_bytes as m6_bytes
            actual = m6_bytes(ROOT,name,(ROOT/name).read_bytes())
            self.assertEqual(m5.sha(m5.collection_view(ROOT,name,actual)),expected)
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


class CollectionCompatibilityTests(unittest.TestCase):
    """Current exact successors add no authority over historical M5/M7 evidence."""

    def adapter(self):
        return m5.collection_adapter()

    def test_exact_committed_renderer_and_eight_individually_pinned_deliveries(self):
        adapter = self.adapter()
        value = adapter.verify()
        self.assertEqual(len(value['delivery_files']), 8)
        self.assertEqual(set(value['delivery_files']), adapter.DELIVERY)
        self.assertIs(value['publication_authorized'], False)
        for name, binding in value['delivery_files'].items():
            self.assertEqual(adapter.digest((ROOT/name).read_bytes(), binding['text_lf']), binding['sha256'])
            self.assertEqual(adapter.digest(adapter._blob(binding['approved_commit'], name), binding['text_lf']), binding['sha256'])
            if binding['before_sha256'] is None:
                self.assertEqual(adapter._entry(binding['before_commit'], name), b'')
            else:
                self.assertEqual(adapter.digest(adapter._blob(binding['before_commit'], name), binding['text_lf']), binding['before_sha256'])
        for name in (adapter.RENDERER, adapter.TEST_MODULE):
            binding = value['files'][name]
            self.assertEqual(adapter.sha(adapter._committed(binding['approved_commit'], name)), binding['sha256'])

    def test_all_1184_historical_ids_plus_exactly_32_disjoint_ids(self):
        from ci import people_security
        adapter = self.adapter()
        added = adapter.test_ids()
        groups, original = people_security.selections()
        actual = [*original, *(node for nodes in groups.values() for node in nodes)]
        self.assertEqual((len(added), len(set(added))), (32, 32))
        self.assertEqual((len(actual), len(set(actual))), (1216, 1216))
        self.assertEqual(len(set(actual)-set(added)), 1184)
        self.assertFalse(set(added) & (set(actual)-set(added)))
        self.assertTrue(all(node.startswith(adapter.TEST_MODULE+'::') for node in added))

    def test_one_fresh_collection_proof_per_m5_call_and_exact_source_dispatch(self):
        from ci import people_job_retention_maintenance as startup
        adapter = self.adapter()
        self.assertEqual(startup.COLLECTION_SOURCES, adapter.SOURCE_PATHS)
        with patch.object(adapter, 'verify', wraps=adapter.verify) as verify:
            m5.verify_checkout()
            self.assertEqual(verify.call_count, 1)
            for name in sorted(adapter.M5_PATHS):
                m5.historical_bytes(ROOT, name, (ROOT/name).read_bytes())
            self.assertEqual(verify.call_count, 3)
        # Unrelated paths receive no COLLECTION authority or adapter load.
        with patch.object(m5, 'collection_adapter', side_effect=AssertionError('unrelated adapter load')):
            self.assertEqual(startup.selected_hash('unreviewed.py', 'f'*64), 'f'*64)
            self.assertEqual(startup.historical_bytes(ROOT, 'unreviewed.py', b'forged'), b'forged')

    def test_m5_local_bindings_reject_rollbacks_after_cohort_verification(self):
        adapter = self.adapter()
        value = adapter.verify()
        original_read, original_verify = Path.read_bytes, adapter.verify
        for name in sorted(adapter.M5_PATHS):
            current = original_read(ROOT/name)
            before = adapter._committed(value['files'][name]['before_commit'], name)
            for operation in ('checkout', 'history'):
                verified = False
                def verify(root):
                    nonlocal verified
                    result = original_verify(root)
                    verified = True
                    return result
                def changed(path):
                    return before if verified and path == ROOT/name else original_read(path)
                with self.subTest(name=name, operation=operation), patch.object(adapter, 'verify', verify), patch.object(Path, 'read_bytes', changed), self.assertRaises(ValueError):
                    if operation == 'checkout':
                        m5.verify_checkout()
                    else:
                        m5.historical_bytes(ROOT, name, current)

    def test_every_current_member_rejects_tamper_missing_and_physical_rollback(self):
        adapter = self.adapter()
        value = adapter.verify()
        original = Path.read_bytes
        for name, binding in {**value['files'], **value['delivery_files']}.items():
            variants = [original(ROOT/name)+b'unreviewed']
            if binding['before_sha256'] not in (None, binding['sha256']):
                variants.append(adapter._blob(binding['before_commit'], name))
            for replacement in variants:
                def changed(path):
                    return replacement if path == ROOT/name else original(path)
                with self.subTest(name=name, attack='bytes'), patch.object(Path, 'read_bytes', changed), self.assertRaises(ValueError):
                    adapter.verify()
            def missing(path):
                if path == ROOT/name:
                    raise FileNotFoundError(name)
                return original(path)
            with self.subTest(name=name, attack='missing'), patch.object(Path, 'read_bytes', missing), self.assertRaises(OSError):
                adapter.verify()

    def test_binary_crlf_changes_are_not_normalized_or_exempted(self):
        adapter = self.adapter()
        original = Path.read_bytes
        for name, binding in adapter.verify()['delivery_files'].items():
            if binding['text_lf']:
                continue
            current = original(ROOT/name)
            replacement = current.replace(b'\r\n', b'\n')
            if replacement == current:
                replacement = current+b'\r\n'
            def changed(path):
                return replacement if path == ROOT/name else original(path)
            with self.subTest(name=name), patch.object(Path, 'read_bytes', changed), self.assertRaises(ValueError):
                adapter.verify()

    def test_all_exact_historical_views_reject_forged_inputs(self):
        adapter = self.adapter()
        value = adapter.verify()
        for name, binding in value['files'].items():
            before = adapter._committed(binding['before_commit'], name)
            self.assertEqual(adapter.historical_bytes(ROOT, name, (ROOT/name).read_bytes()), before)
            self.assertEqual(adapter.historical_bytes(ROOT, name, before), before)
            with self.subTest(name=name), self.assertRaises(ValueError):
                adapter.historical_bytes(ROOT, name, b'forged')
            if name in adapter.M5_PATHS:
                with self.assertRaises(ValueError):
                    m5.historical_bytes(ROOT, name, b'forged')

    def test_unknown_expected_hashes_never_authorize_a_successor(self):
        adapter = self.adapter()
        for name, binding in adapter.verify()['files'].items():
            self.assertEqual(adapter.selected_hash(name, binding['before_sha256']), binding['sha256'])
            self.assertEqual(adapter.selected_hash(name, 'f'*64), 'f'*64)
            self.assertNotEqual(adapter.sha((ROOT/name).read_bytes()), 'f'*64)
        self.assertEqual(adapter.selected_hash('unreviewed.py', 'f'*64), 'f'*64)

    def test_manifest_tamper_expansion_authority_duplicate_and_unknown_hash_fail(self):
        adapter = self.adapter()
        value = adapter.verify()
        original = Path.read_bytes
        for attack in ('expansion', 'hash', 'authority', 'duplicate', 'baseline', 'delivery'):
            altered = deepcopy(value)
            if attack == 'expansion':
                altered['files']['ci/unknown.py'] = dict(altered['files'][adapter.RENDERER])
            elif attack == 'hash':
                altered['files'][adapter.RENDERER]['sha256'] = 'f'*64
            elif attack == 'authority':
                altered['publication_authorized'] = True
            elif attack == 'duplicate':
                altered['pytest_ids'][-1] = altered['pytest_ids'][0]
            elif attack == 'baseline':
                altered['baseline_commit'] = 'f'*40
            else:
                altered['delivery_files'].pop(next(iter(adapter.DELIVERY)))
            def changed(path):
                return json.dumps(altered).encode() if path == ROOT/adapter.MANIFEST else original(path)
            with self.subTest(attack=attack), patch.object(Path, 'read_bytes', changed), self.assertRaises(ValueError):
                adapter.verify()

    def test_independent_adapter_pin_rejects_source_tamper(self):
        original = Path.read_bytes
        name = 'ci/people_collection_maintenance.py'
        def changed(path):
            return original(path)+b'\n# unreviewed' if path == ROOT/name else original(path)
        with patch.object(Path, 'read_bytes', changed), self.assertRaises(ValueError):
            m5.collection_adapter()

    def test_frozen_records_remain_required_after_warming_immutable_caches(self):
        adapter = self.adapter()
        value = adapter.verify()
        original = Path.read_bytes
        for name in value['frozen_files']:
            def changed(path):
                return original(path)+b' ' if path == ROOT/name else original(path)
            with self.subTest(name=name), patch.object(Path, 'read_bytes', changed), self.assertRaises(ValueError):
                adapter.verify()

    def test_fresh_heads_reject_ancestry_rollback_and_foreign_roots(self):
        adapter = self.adapter()
        adapter.verify()
        with self.assertRaises(ValueError):
            adapter.verify(ROOT/'foreign')
        with patch.object(adapter, '_head', return_value='463ba791b77c82c232aead1da218fc0ca0142868'), self.assertRaises(ValueError):
            adapter.verify()
        with patch.object(adapter, '_head', wraps=adapter._head) as head:
            adapter.verify(); adapter.verify()
            self.assertEqual(head.call_count, 2)

    def test_loose_head_resolution_is_fresh_and_unsupported_cases_use_git(self):
        import os
        import tempfile
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, clear=True):
            root = Path(folder)
            metadata = root/'metadata'
            metadata.mkdir()
            marker = root/'.git'
            marker.write_text('gitdir: metadata\n', encoding='utf8')
            head = metadata/'HEAD'
            head.write_text('1'*40+'\n', encoding='ascii')
            with patch.object(adapter, '_git', side_effect=AssertionError('unexpected Git fallback')):
                self.assertEqual(adapter._head(root), '1'*40)
                head.write_text('2'*40+'\n', encoding='ascii')
                self.assertEqual(adapter._head(root), '2'*40)
                common = root/'common'
                (common/'refs/heads').mkdir(parents=True)
                (metadata/'commondir').write_text('../common\n', encoding='utf8')
                head.write_text('ref: refs/heads/fixture\n', encoding='ascii')
                branch = common/'refs/heads/fixture'
                branch.write_text('3'*40+'\n', encoding='ascii')
                self.assertEqual(adapter._head(root), '3'*40)
                branch.write_text('4'*40+'\n', encoding='ascii')
                self.assertEqual(adapter._head(root), '4'*40)
            branch.unlink()
            with patch.object(adapter, '_git', return_value=('5'*40+'\n').encode()) as git:
                self.assertEqual(adapter._head(root), '5'*40)
                self.assertEqual(git.call_args.args, (root, 'rev-parse', 'HEAD'))
                head.write_text('ref: refs/heads/../unsafe\n', encoding='ascii')
                self.assertEqual(adapter._head(root), '5'*40)
                with patch.dict(os.environ, {'GIT_NAMESPACE': 'fixture'}):
                    head.write_text('6'*40+'\n', encoding='ascii')
                    self.assertEqual(adapter._head(root), '5'*40)
            with patch.dict(os.environ, {'GIT_NAMESPACE': 'fixture'}), patch.object(adapter, '_git', return_value=b'not-a-commit\n'), self.assertRaises(ValueError):
                adapter._head(root)

    def test_fresh_leaf_and_parent_checks_reject_links_and_reparse_points(self):
        import stat
        from types import SimpleNamespace
        adapter = self.adapter()
        adapter.verify()
        original = Path.lstat
        name = 'create_people_posters/fonts/Montserrat-Light.ttf'
        for target in (ROOT/'create_people_posters/fonts', ROOT/name):
            for link, reparse in ((True, False), (False, True)):
                def changed(path, *args, **kwargs):
                    info = original(path, *args, **kwargs)
                    if path == target:
                        return SimpleNamespace(st_mode=stat.S_IFLNK if link else info.st_mode, st_file_attributes=0x400 if reparse else 0)
                    return info
                with self.subTest(path=str(target), link=link), patch.object(Path, 'lstat', changed), self.assertRaises(ValueError):
                    adapter.verify()

    def test_committed_delivery_bytes_and_metadata_must_match_the_reviewed_receipt(self):
        adapter = self.adapter()
        value = adapter.verify()
        name = next(iter(adapter.DELIVERY))
        binding = value['delivery_files'][name]
        original_blob, original_entry = adapter._blob, adapter._entry
        def changed_blob(commit, path):
            return b'forged' if (commit, path) == (binding['approved_commit'], name) else original_blob(commit, path)
        with patch.object(adapter, '_blob', changed_blob), self.assertRaises(ValueError):
            adapter.verify()
        def changed_entry(commit, path):
            return b'120000 blob '+'f'.encode()*40+b'\t'+name.encode()+b'\0' if (commit, path) == (binding['approved_commit'], name) else original_entry(commit, path)
        with patch.object(adapter, '_entry', changed_entry), self.assertRaises(ValueError):
            adapter.verify()

    def test_exact_m7_delivery_scope_and_static_enumeration_grant_no_exemption(self):
        adapter = self.adapter()
        adapter.verify_scope(ROOT, adapter.M7_BASE, adapter.DELIVERY)
        with patch.object(adapter, 'verify', side_effect=ValueError('not accepted')):
            self.assertTrue(adapter.DELIVERY <= adapter.scope_members())
            with self.assertRaises(ValueError):
                adapter.verify_scope(ROOT, adapter.M7_BASE, adapter.DELIVERY)
        with self.assertRaises(ValueError):
            adapter.verify_scope(ROOT, adapter.M7_BASE, {'unreviewed.py'})
        with self.assertRaises(ValueError):
            adapter.verify_scope(ROOT, 'f'*40, adapter.DELIVERY)

    def test_scope_rejects_forged_blob_unsafe_modes_renames_deletion_and_incomplete_diff(self):
        adapter = self.adapter()
        value = adapter.verify()
        name = next(iter(adapter.DELIVERY))
        oid = value['delivery_files'][name]['approved_blob']
        attacks = [b'', (f':000000 100644 '+ '0'*40+' '+'f'*40+f' A\0{name}\0').encode()]
        for old, new, status in [('100644', '000000', 'D'), ('000000', '120000', 'A'), ('100644', '100644', 'R100')]:
            attacks.append((f':{old} {new} '+'0'*40+' '+oid+f' {status}\0{name}\0').encode())
        valid = (f':000000 100644 '+'0'*40+' '+oid+f' A\0{name}\0').encode()
        attacks.extend((valid[:-1], valid+valid, valid.replace(name.encode(), b'ci/unknown.py')))
        original = adapter._git
        for raw in attacks:
            def changed(root, *args):
                return raw if args[0] == 'diff' else original(root, *args)
            with self.subTest(raw=raw[:80]), patch.object(adapter, '_git', changed), self.assertRaises(ValueError):
                adapter.verify_scope(ROOT, adapter.M7_BASE, {name})


class FoundationVerifierBoundaryTests(unittest.TestCase):
    """Invocation-local metadata never waives fresh physical or historical checks."""

    def test_boundary_invocations_reverify_security_and_all_190_sources(self):
        from ci import phase4, phase4_transactions as tx, people_security_maintenance as security
        pins=json.loads((ROOT/security.PINS).read_bytes())
        original=Path.read_bytes
        for call in (lambda:phase4.historical_checksum(ROOT,'ci/phase4.py'),
                     lambda:tx.verify_maintenance(ROOT)):
            observed=set()
            def read(path):
                observed.add(path)
                return original(path)
            with self.subTest(operation=call), patch.object(Path,'read_bytes',read), patch.object(security,'verify',wraps=security.verify) as verify:
                call()
                self.assertEqual(verify.call_count,1)
                self.assertTrue({ROOT/n for n in pins['files']}<=observed)
                observed.clear()
                call()
                self.assertEqual(verify.call_count,2)
                self.assertTrue({ROOT/n for n in pins['files']}<=observed)

    def test_checksum_rejects_tamper_and_rollback_after_full_proof(self):
        from ci import phase4, people_security_maintenance as security
        adapter=m5.collection_adapter()
        value=adapter.verify()
        original_read,original_verify=Path.read_bytes,security.verify
        for name in ('ci/phase4.py','ci/phase4_transactions.py'):
            current=original_read(ROOT/name)
            old=adapter._committed(value['files'][name]['before_commit'],name)
            for changed in (current+b'\n# tampered',old):
                proved=False
                def verify(root):
                    nonlocal proved
                    result=original_verify(root);proved=True
                    return result
                def read(path):
                    return changed if proved and path==ROOT/name else original_read(path)
                with self.subTest(name=name,rollback=changed==old),patch.object(security,'verify',verify),patch.object(Path,'read_bytes',read),self.assertRaises(ValueError):
                    phase4.historical_checksum(ROOT,name)

    def test_transaction_views_reject_tamper_and_rollback_after_full_proof(self):
        from ci import phase4_transactions as tx, people_security_maintenance as security
        original_read,original_verify=Path.read_bytes,security.verify
        for name in ('.github/workflows/default-poster-validation.yml',security.PINS,
                     'create_defaults/bulk/contracts/activation/protection.py'):
            current=original_read(ROOT/name)
            old=security._old(ROOT,name)
            for changed in (current+b'\n# tampered',old):
                proved=False
                def verify(root):
                    nonlocal proved
                    result=original_verify(root);proved=True
                    return result
                def read(path):
                    return changed if proved and path==ROOT/name else original_read(path)
                with self.subTest(name=name,rollback=changed==old),patch.object(security,'verify',verify),patch.object(Path,'read_bytes',read),self.assertRaises(ValueError):
                    tx.verify_maintenance(ROOT)

    def test_checksum_hashes_exact_historical_bytes_after_proof(self):
        from ci import phase4, people_security_maintenance as security
        import hashlib
        name='ci/phase4.py'
        self.assertEqual(phase4.historical_checksum(ROOT,name),
                         hashlib.sha256(security._old(ROOT,name)).hexdigest())
        original_verify,original_old=security.verify,security._old
        proved=False
        def verify(root):
            nonlocal proved
            result=original_verify(root);proved=True
            return result
        def old(root,path):
            return b'forged historical bytes' if proved and path==name else original_old(root,path)
        with patch.object(security,'verify',verify),patch.object(security,'_old',old),self.assertRaises(ValueError):
            phase4.historical_checksum(ROOT,name)

    def test_transactions_hash_exact_historical_bytes_after_proof(self):
        from ci import phase4_transactions as tx, people_security_maintenance as security
        original_verify,original_old=security.verify,security._old
        for target in (security.PINS,
                       'create_defaults/bulk/contracts/activation/protection.py'):
            proved=False
            def verify(root):
                nonlocal proved
                result=original_verify(root);proved=True
                return result
            def old(root,path):
                return b'forged historical bytes' if proved and path==target else original_old(root,path)
            with self.subTest(target=target),patch.object(security,'verify',verify),patch.object(security,'_old',old),self.assertRaises(ValueError):
                tx.verify_maintenance(ROOT)

    def test_boundary_source_projections_reject_foreign_and_forged_inputs(self):
        adapter=m5.collection_adapter()
        value=adapter.verify()
        self.assertTrue({'ci/phase4.py','ci/phase4_transactions.py'}<=adapter.SOURCE_PATHS)
        for name in ('ci/phase4.py','ci/phase4_transactions.py'):
            binding=value['files'][name]
            current=(ROOT/name).read_bytes()
            old=adapter._committed(binding['before_commit'],name)
            self.assertEqual(adapter.historical_bytes(ROOT,name,current),old)
            self.assertEqual(adapter.historical_bytes(ROOT,name,old),old)
            self.assertEqual(adapter.selected_hash(name,'f'*64),'f'*64)
            with self.assertRaises(ValueError):
                adapter.historical_bytes(ROOT,name,b'forged')
            with self.assertRaises(ValueError):
                adapter.historical_bytes(ROOT/'foreign',name,current)

    def test_new_boundary_bytes_cannot_roll_back_on_a_later_public_call(self):
        from ci import phase4, phase4_transactions as tx
        adapter=m5.collection_adapter();value=adapter.verify()
        original=Path.read_bytes
        for name in ('ci/phase4.py','ci/phase4_transactions.py'):
            old=adapter._committed(value['files'][name]['before_commit'],name)
            phase4.historical_checksum(ROOT,name)
            tx.verify_maintenance(ROOT)
            def read(path):
                return old if path==ROOT/name else original(path)
            with self.subTest(name=name),patch.object(Path,'read_bytes',read):
                with self.assertRaises(ValueError):phase4.historical_checksum(ROOT,name)
                with self.assertRaises(ValueError):tx.verify_maintenance(ROOT)

    def test_used_paths_recheck_leaf_and_parent_modes_after_the_full_proof(self):
        from ci import phase4, phase4_transactions as tx, people_security_maintenance as security
        from types import SimpleNamespace
        import stat
        original_verify,original_lstat=security.verify,Path.lstat
        operations=(
            (lambda:phase4.historical_checksum(ROOT,'ci/phase4.py'),ROOT/'ci/phase4.py',ROOT/'ci'),
            (lambda:tx.verify_maintenance(ROOT),ROOT/'.github/workflows/default-poster-validation.yml',ROOT/'.github/workflows'),
        )
        for call,leaf,parent in operations:
            for target in (leaf,parent):
                for mode in ('symlink','reparse'):
                    proved=False
                    def verify(root):
                        nonlocal proved
                        result=original_verify(root);proved=True
                        return result
                    def lstat(path,*args,**kwargs):
                        result=original_lstat(path,*args,**kwargs)
                        if proved and path==target:
                            return SimpleNamespace(st_mode=stat.S_IFLNK if mode=='symlink' else result.st_mode,
                                st_file_attributes=0x400 if mode=='reparse' else 0)
                        return result
                    with self.subTest(leaf=str(leaf),target=str(target),mode=mode),patch.object(security,'verify',verify),patch.object(Path,'lstat',lstat),self.assertRaises(ValueError):
                        call()


class FoundationBatchFreshnessTests(unittest.TestCase):
    def test_batch_rechecks_all_190_sources_on_every_invocation(self):
        from ci import phase4,people_security_maintenance as security
        paths=('ci/phase4.py','ci/phase4_transactions.py')
        pins=json.loads((ROOT/security.PINS).read_bytes())
        original=Path.read_bytes
        for unused in range(2):
            seen=set()
            def read(path):
                seen.add(path)
                return original(path)
            with patch.object(Path,'read_bytes',read),patch.object(security,'verify',wraps=security.verify) as verify:
                actual=phase4.historical_checksums(ROOT,paths)
                self.assertEqual(verify.call_count,1)
                self.assertTrue({ROOT/n for n in pins['files']}<=seen)
                self.assertEqual(set(actual),set(paths))

    def test_batch_rejects_tamper_and_rollback_on_later_invocation(self):
        from ci import phase4
        adapter=m5.collection_adapter();value=adapter.verify()
        paths=('ci/phase4.py','ci/phase4_transactions.py')
        original=Path.read_bytes
        phase4.historical_checksums(ROOT,paths)
        for target in paths:
            before=adapter._committed(value['files'][target]['before_commit'],target)
            for replacement in (before,original(ROOT/target)+b'\n# tampered'):
                def read(path):
                    return replacement if path==ROOT/target else original(path)
                with self.subTest(target=target),patch.object(Path,'read_bytes',read),self.assertRaises(ValueError):
                    phase4.historical_checksums(ROOT,paths)

    def test_aggregate_uses_four_fresh_security_proofs_without_caching_acceptance(self):
        from ci import phase4,people_security_maintenance as security
        with patch.object(security,'verify',wraps=security.verify) as verify:
            phase4.verify_maintenance()
            self.assertEqual(verify.call_count,4)
