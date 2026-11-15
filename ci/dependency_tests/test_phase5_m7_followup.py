"""Focused M7 provenance/dossier controls; no native M6 execution."""
import copy
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import tempfile
import subprocess
from types import ModuleType, SimpleNamespace
import unittest
import zipfile
from unittest.mock import patch

from ci import phase5_m7_acceptance as acceptance
from ci import phase5_m7_maintenance as maintenance
from ci import phase5_m7_provenance as provenance


class Phase5M7FollowupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m7-review-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def cohort(self):
        m = maintenance
        current = {name: ('new '+name+'\n').encode() for name in m.MODIFIED | m.ADDED}
        before = {name: ('old '+name+'\n').encode() for name in m.MODIFIED}
        receipt = {'version': 1, 'baseline_commit': m.BASE, 'members': {
            n: {'before_sha256': m.sha(before[n]) if n in before else None, 'sha256': m.sha(b)}
            for n, b in current.items()}, 'ci_only': True, 'publication_authorized': False}
        for name, data in {**current, m.OWNER: b'owner',
                           m.RECEIPT: json.dumps(receipt).encode()}.items():
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return current, before, receipt

    def owner(self, before, receipt):
        m = maintenance
        self.enterContext(patch.object(m, 'ROOT', self.root))
        self.enterContext(patch.object(m, 'PIN', m.fingerprint(receipt)))
        self.enterContext(patch.object(m, 'predecessor', side_effect=before.__getitem__))
        self.enterContext(patch.object(m, 'ancestry'))
        helper = ModuleType('ci.people_colorize_maintenance')
        helper._head = lambda root: 'f'*40
        self.enterContext(patch.dict('sys.modules', {'ci.people_colorize_maintenance': helper}))
        def git(root, *args):
            if args[0] == 'ls-tree':
                return b''
            if args[0] == 'show':
                return (self.root/args[1].split(':', 1)[1]).read_bytes()
            raise AssertionError(args)
        self.enterContext(patch.object(m, 'git', side_effect=git))
        return helper

    def test_complete_cohort_projects_only_exact_successors(self):
        current, before, receipt = self.cohort()
        self.owner(before, receipt)
        self.assertEqual(maintenance.verify_checkout()['members'], receipt['members'])
        for name in maintenance.MODIFIED:
            self.assertEqual(maintenance.historical_bytes(self.root, name, current[name]), before[name])
            self.assertEqual(maintenance.historical_bytes(self.root, name, before[name]), before[name])
            with self.assertRaises(ValueError):
                maintenance.historical_bytes(self.root, name, b'forged')
            self.assertEqual(maintenance.historical_bytes(self.root, name, b'opaque', opaque=True), b'opaque')
        self.assertEqual(maintenance.historical_bytes(self.root, 'unlisted', b'opaque'), b'opaque')
        storage = 'ci/people_storage_maintenance.py'
        prior = b'already sealed geometry view'
        with patch.object(maintenance, 'STORAGE_VIEWS', (maintenance.sha(prior),)):
            self.assertEqual(maintenance.historical_bytes(self.root, storage, prior), prior)
            (self.root/storage).write_bytes(prior)
            with self.assertRaises(ValueError):
                maintenance.historical_bytes(self.root, storage, prior)
            (self.root/storage).write_bytes(current[storage])

    def test_every_physical_member_tamper_delete_and_rollback_rejects(self):
        current, before, receipt = self.cohort()
        self.owner(before, receipt)
        for name, good in current.items():
            path = self.root/name
            for bad in (b'changed', before.get(name, b'unexpected predecessor')):
                with self.subTest(name=name, bad=bad):
                    path.write_bytes(bad)
                    with self.assertRaises(ValueError):
                        maintenance.verify_checkout()
                    if name in maintenance.MODIFIED:
                        with self.assertRaises(ValueError):
                            maintenance.historical_bytes(self.root, name, b'opaque', opaque=True)
                    path.write_bytes(good)
            path.unlink()
            with self.assertRaises(OSError):
                maintenance.verify_checkout()
            path.write_bytes(good)

    def test_immutable_git_objects_never_cache_current_owner_head_or_files(self):
        current, before, receipt = self.cohort()
        helper = self.owner(before, receipt)
        maintenance._baseline_entry.cache_clear()
        maintenance._owner_bytes.cache_clear()
        with patch.object(maintenance, 'git', wraps=maintenance.git) as git, \
             patch.object(helper, '_head', wraps=helper._head) as head:
            maintenance.verify_checkout()
            cold = git.call_count
            maintenance.verify_checkout()
        self.assertEqual(cold, len(maintenance.ADDED)+1)
        self.assertEqual(git.call_count, cold)
        self.assertEqual(head.call_count, 4)
        owner = self.root/maintenance.OWNER
        owner.write_bytes(b'uncommitted owner')
        with self.assertRaisesRegex(ValueError, 'uncommitted M7 owner'):
            maintenance.verify_checkout()
        owner.write_bytes(b'owner')
        with patch.object(helper, '_head', side_effect=['f'*40, 'e'*40]), \
             self.assertRaisesRegex(ValueError, 'HEAD moved'):
            maintenance.verify_checkout()
        name = next(iter(maintenance.MODIFIED))
        (self.root/name).write_bytes(before[name])
        with self.assertRaises(ValueError):
            maintenance.verify_checkout()

    def test_resealed_membership_authority_and_predecessor_fail_closed(self):
        current, before, receipt = self.cohort()
        self.owner(before, receipt)
        for attack in ('membership', 'authority', 'baseline', 'predecessor'):
            with self.subTest(attack=attack):
                bad = copy.deepcopy(receipt)
                if attack == 'membership':
                    bad['members']['ci/unapproved.py'] = next(iter(bad['members'].values()))
                elif attack == 'authority':
                    bad['publication_authorized'] = True
                elif attack == 'baseline':
                    bad['baseline_commit'] = '0'*40
                else:
                    bad['members'][next(iter(maintenance.MODIFIED))]['before_sha256'] = '0'*64
                (self.root/maintenance.RECEIPT).write_text(json.dumps(bad))
                with patch.object(maintenance, 'PIN', maintenance.fingerprint(bad)), self.assertRaises(ValueError):
                    maintenance.verify_checkout()
        (self.root/maintenance.RECEIPT).write_text(json.dumps(receipt))

    def test_batched_parent_modes_and_byte_caches_keep_every_input_fresh(self):
        current, before, receipt = self.cohort()
        self.owner(before, receipt)
        maintenance.verify_checkout()  # Warm immutable metadata/Git objects only.
        reads, modes = Counter(), Counter()
        original_read, original_stat = Path.read_bytes, Path.lstat
        def read(path):
            reads[path] += 1
            return original_read(path)
        def lstat(path):
            modes[path] += 1
            return original_stat(path)
        with patch.object(Path, 'read_bytes', read), patch.object(Path, 'lstat', lstat):
            value = maintenance.verify_checkout()
            value['members'][next(iter(current))]['sha256'] = '0'*64
            self.assertEqual(maintenance.verify_checkout()['members'], receipt['members'])
        for name in current:
            self.assertEqual(reads[self.root/name], 2)
            self.assertEqual(modes[self.root/name], 2)
        self.assertEqual(reads[self.root/maintenance.RECEIPT], 4)
        self.assertEqual(reads[self.root/maintenance.OWNER], 2)
        # One shared-parent batch plus fresh owner/closing-receipt mode checks
        # per invocation, rather than one parent walk for each member.
        self.assertEqual(modes[self.root], 6)
        self.assertEqual(maintenance.sha.cache_info().maxsize, 128)
        self.assertEqual(maintenance._decode.cache_info().maxsize, 4)
        for target in (self.root/'ci', self.root/next(iter(current))):
            def reparse(path):
                info = original_stat(path)
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400) if path == target else info
            with self.subTest(path=target), patch.object(Path, 'lstat', reparse), self.assertRaises(ValueError):
                maintenance.verify_checkout()

    def test_foreign_checkout_dirty_owner_and_changed_head_reject(self):
        current, before, receipt = self.cohort()
        helper = self.owner(before, receipt)
        with self.assertRaises(ValueError):
            maintenance.verify_checkout(self.root/'foreign')
        with patch.object(maintenance, 'git', return_value=b'committed owner'), self.assertRaises(ValueError):
            maintenance.verify_checkout()
        with patch.object(helper, '_head', side_effect=['f'*40, 'e'*40]), self.assertRaises(ValueError):
            maintenance.verify_checkout()

    def test_one_invocation_reuses_entry_metadata_and_always_proves_a_fresh_close(self):
        from contextvars import copy_context
        current, before, receipt = self.cohort()
        self.owner(before, receipt)
        captured = []
        @maintenance.owned_call
        def nested(root, name):
            return maintenance.historical_bytes(root, name, current[name])
        @maintenance.owned_call
        def public(root):
            captured.append(copy_context())
            metadata = maintenance._owned_members(root)
            self.assertEqual(metadata, receipt['members'])
            metadata[next(iter(current))]['sha256'] = '0'*64
            for _ in range(2):
                for name in maintenance.MODIFIED:
                    self.assertEqual(nested(root, name), before[name])
        with patch.object(maintenance, 'verify_checkout', wraps=maintenance.verify_checkout) as verify:
            public(self.root)
            self.assertEqual(verify.call_count, 2)
            public(self.root)
            self.assertEqual(verify.call_count, 4)
        with self.assertRaises(ValueError):
            maintenance._owned_members(self.root)
        # A copied context cannot retain the completed invocation's acceptance.
        name = next(iter(maintenance.MODIFIED))
        (self.root/name).write_bytes(before[name])
        with self.assertRaises(ValueError):
            captured[0].run(maintenance.historical_bytes, self.root, name, current[name])
        (self.root/name).write_bytes(current[name])
        public(self.root)

    def test_owned_views_reject_point_of_use_and_closing_changes_without_leaking_proofs(self):
        current, before, receipt = self.cohort()
        helper = self.owner(before, receipt)
        names = sorted(maintenance.MODIFIED)
        target, other = names[:2]
        @maintenance.owned_call
        def public(root, action=lambda: None):
            action()
            return maintenance.historical_bytes(root, target, current[target])
        for bad in (b'tampered', before[target], None):
            def attack():
                path = self.root/target
                path.unlink() if bad is None else path.write_bytes(bad)
            with self.subTest(bad=bad), self.assertRaises((ValueError, OSError)):
                public(self.root, attack)
            (self.root/target).write_bytes(current[target])
            self.assertEqual(public(self.root), before[target])
        # A member that was not projected must still fail the full closing proof.
        with self.assertRaises(ValueError):
            public(self.root, lambda: (self.root/other).write_bytes(before[other]))
        (self.root/other).write_bytes(current[other])
        raw = (self.root/maintenance.RECEIPT).read_bytes()
        with self.assertRaises(ValueError):
            public(self.root, lambda: (self.root/maintenance.RECEIPT).write_bytes(b'{}'))
        (self.root/maintenance.RECEIPT).write_bytes(raw)
        with patch.object(helper, '_head', side_effect=['f'*40, 'f'*40, 'e'*40, 'e'*40]), \
             self.assertRaisesRegex(ValueError, 'HEAD'):
            public(self.root)
        self.assertEqual(public(self.root), before[target])

    def test_actual_public_m6_calls_each_prove_their_own_entry_and_close(self):
        from ci import phase5_m6_maintenance as m6
        with patch.object(maintenance, 'verify_checkout', wraps=maintenance.verify_checkout) as verify:
            self.assertFalse(m6.verify_checkout()['publication_authorized'])
            self.assertEqual(verify.call_count, 2)
            self.assertFalse(m6.verify_checkout()['publication_authorized'])
            self.assertEqual(verify.call_count, 4)

    def test_scope_modes_are_exact_and_dossiers_are_not_maintenance_members(self):
        current, before, receipt = self.cohort()
        self.owner(before, receipt)
        self.assertNotIn('create_defaults/lifecycle/PHASE5_M7_ACCEPTANCE.json', maintenance.scope_members())
        for name in maintenance.scope_members():
            good_mode, good_status = ('100644', 'M') if name in maintenance.MODIFIED else ('000000', 'A')
            for mode, destination, status in ((good_mode, '100644', good_status),
                                               (good_mode, '120000', good_status),
                                               (good_mode, '100755', good_status),
                                               (good_mode, '000000', 'D'),
                                               (good_mode, '100644', 'R100')):
                row = (f':{mode} {destination} '+ '0'*40+' '+'1'*40+f' {status}\0{name}\0').encode()
                original = maintenance.git
                def git(root, *args):
                    return row if args[0] == 'diff' else original(root, *args)
                with self.subTest(name=name, status=status, destination=destination), patch.object(maintenance, 'git', side_effect=git):
                    if destination == '100644' and status == good_status:
                        maintenance.verify_scope(self.root, {name})
                    else:
                        with self.assertRaises(ValueError):
                            maintenance.verify_scope(self.root, {name})

    def dossier(self):
        tests = {f'P5-T{i:02}': {f'test_{i}'} for i in range(1, 35)}
        dossier = {'version': 1, 'operational_authority': False, 'counts': acceptance.COUNTS,
                   'documents': {'support_sha256': '0'*64, 'handoff_sha256': '0'*64},
                   'requirements': [{'id': k, 'tests': sorted(v)} for k, v in tests.items()]}
        original = {'packages': ['exact packages'], 'variants': ['exact variants']}
        coverage = {'version': 1, 'packages': original['packages'], 'variants': original['variants'],
                    'counts': acceptance.COUNTS, 'publication_authorized': False}
        return dossier, coverage, tests, original

    def test_scope_preserves_existing_lf_normalization(self):
        current, before, receipt = self.cohort()
        self.owner(before, receipt)
        name = 'ci/phase4_m7.py'
        (self.root/name).write_bytes(current[name].replace(b'\n', b'\r\n'))
        row = (':100644 100644 '+'0'*40+' '+'1'*40+' M\0'+name+'\0').encode()
        original = maintenance.git
        def git(root, *args):
            if args[0] == 'diff':
                return row
            if args == ('show', 'HEAD:'+name):
                return current[name]
            return original(root, *args)
        with patch.object(maintenance, 'git', side_effect=git):
            maintenance.verify_scope(self.root, {name})

    def test_dossier_requires_all_34_exact_families_and_zero_authority(self):
        dossier, coverage, tests, original = self.dossier()
        executed = set().union(*tests.values())
        with patch.object(acceptance, 'read', return_value=original):
            acceptance.verify_dossier(dossier, coverage, executed, tests)
            for attack in ('missing', 'duplicate', 'foreign-test', 'unexecuted', 'authority', 'coverage'):
                d, c, e = copy.deepcopy(dossier), copy.deepcopy(coverage), set(executed)
                if attack == 'missing':
                    d['requirements'].pop()
                elif attack == 'duplicate':
                    d['requirements'].append(d['requirements'][0])
                elif attack == 'foreign-test':
                    d['requirements'][0]['tests'] = ['other-test']
                elif attack == 'unexecuted':
                    e.remove('test_1')
                elif attack == 'authority':
                    d['operational_authority'] = True
                else:
                    c['variants'] = ['expanded scope']
                with self.subTest(attack=attack), self.assertRaises(ValueError):
                    acceptance.verify_dossier(d, c, e, tests)

    def index(self):
        workflows, files = [], []
        for i, name in enumerate(acceptance.WORKFLOWS, 1):
            path = f'artifact-{i}.bin'
            (self.root/path).write_bytes(b'encoded artifact')
            files.append({'path': path, 'sha256': hashlib.sha256(b'encoded artifact').hexdigest(), 'workflow': name, 'artifact_id': i})
            workflows.append({'name': name, 'head': 'f'*40, 'status': 'completed', 'conclusion': 'success',
                'url': f'https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/{i}',
                'jobs': [{'id': i, 'name': 'exact job', 'status': 'completed', 'conclusion': 'success'}]})
        return {'head': 'f'*40, 'base': 'e'*40, 'plan_sha256': 'p', 'workflows': workflows, 'files': files}

    def test_index_rejects_stale_failed_duplicate_and_substituted_evidence(self):
        index = self.index()
        expected = {'head': 'f'*40, 'plan_sha256': 'p'}
        acceptance.index_files(self.root, index, expected)
        for attack in ('head', 'workflow', 'job', 'duplicate', 'bytes', 'escape', 'omission'):
            bad = copy.deepcopy(index)
            if attack == 'head':
                bad['head'] = 'a'*40
            elif attack == 'workflow':
                bad['workflows'][0]['conclusion'] = 'failure'
            elif attack == 'job':
                bad['workflows'][0]['jobs'][0]['conclusion'] = 'skipped'
            elif attack == 'duplicate':
                bad['files'].append(bad['files'][0])
            elif attack == 'bytes':
                bad['files'][0]['sha256'] = '0'*64
            elif attack == 'escape':
                bad['files'][0]['path'] = '../escape'
            else:
                bad['files'].pop()
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                acceptance.index_files(self.root, bad, expected)

    def test_native_replay_requires_both_platforms_and_actual_directories(self):
        selected, seen = [], []
        for platform in ('Windows', 'Linux'):
            report = self.root/platform/'transport'/'report.json'
            report.parent.mkdir(parents=True)
            native = report.parent.parent/'native'/'single'
            native.mkdir(parents=True)
            selected.append((report, {'platform': platform, 'group': 'transport', 'execution': {'nodes': [platform]}}))
        def verify(report, expected, *, native_directory):
            self.assertTrue(native_directory.is_dir())
            seen.append(native_directory)
        module = SimpleNamespace(GROUPS=('transport',), NATIVE={'transport': 'single'}, verify=verify)
        self.assertEqual(acceptance.replay_phase5(module, 6, selected, {}), {'Windows', 'Linux'})
        self.assertEqual(len(seen), 2)
        with self.assertRaises(ValueError):
            acceptance.replay_phase5(module, 6, selected[:1], {})
        seen[0].rmdir()
        with self.assertRaises(ValueError):
            acceptance.replay_phase5(module, 6, selected, {})

    def test_strict_json_duplicate_and_nonfinite_values_reject(self):
        path = self.root/'strict.json'
        for raw in ('{"a":1,"a":2}', '{"a":NaN}'):
            path.write_text(raw)
            with self.assertRaises(ValueError):
                acceptance.load(path)

    def test_T34_checks_rendered_support_and_handoff_even_when_hashes_are_resealed(self):
        dossier, coverage, tests, original = self.dossier()
        coverage['packages'] = [{'category': 'Genre', 'kind': 'poster', 'variants': 28, 'selected': 27, 'blocked': 1}]
        folder = self.root/'create_defaults/lifecycle'
        folder.mkdir(parents=True)
        texts = {'PHASE5_M7_ACCEPTANCE_REPORT.md': acceptance.support_document(dossier, coverage),
                 'PHASE5_HANDOFF.md': acceptance.handoff_document()}
        labels = ('avp', 'babylon', 'bsg', 'gundam', 'jrrt', 'sao', 'stargate', 'wdu')
        for label in labels:
            self.assertEqual(texts['PHASE5_HANDOFF.md'].count(f'| {label} | {label}.png |'), 1)
        release = {'entries': [{'approval': 'missing_exact_maintainer_decision'} for _ in range(22)]}
        def bind():
            for name, key in (('PHASE5_M7_ACCEPTANCE_REPORT.md', 'support_sha256'), ('PHASE5_HANDOFF.md', 'handoff_sha256')):
                dossier['documents'][key] = hashlib.sha256((folder/name).read_bytes()).hexdigest()
        for name, text in texts.items():
            (folder/name).write_bytes(text.encode())
        bind()
        with patch.object(acceptance, 'read', return_value=release):
            acceptance.verify_documents(self.root, dossier, coverage)
            committed = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in texts.items()}
            acceptance.verify_documents(self.root, dossier, coverage, committed)
            with self.assertRaisesRegex(ValueError, 'Uncommitted M7 document'):
                acceptance.verify_documents(self.root, dossier, coverage,
                                            {**committed, 'PHASE5_HANDOFF.md': '0'*64})
            for name, bad in (('PHASE5_M7_ACCEPTANCE_REPORT.md', texts['PHASE5_M7_ACCEPTANCE_REPORT.md'].replace('| Genre / poster | 28 | 27 | 1 |', '')),
                              ('PHASE5_M7_ACCEPTANCE_REPORT.md', texts['PHASE5_M7_ACCEPTANCE_REPORT.md'].replace('251 blocked', '0 blocked')),
                              ('PHASE5_HANDOFF.md', texts['PHASE5_HANDOFF.md'].replace('NOT STARTED', 'READY')),
                              ('PHASE5_HANDOFF.md', texts['PHASE5_HANDOFF.md'].replace('| wdu | wdu.png |', '')),
                              ('PHASE5_HANDOFF.md', texts['PHASE5_HANDOFF.md'].replace('| avp | avp.png |', '| alien | alien.png |')),
                              ('PHASE5_HANDOFF.md', texts['PHASE5_HANDOFF.md'].replace('all eight listed', 'all six listed')),
                              ('PHASE5_HANDOFF.md', texts['PHASE5_HANDOFF.md'].replace('Assess reuse of', 'Bypass')),
                              ('PHASE5_HANDOFF.md', texts['PHASE5_HANDOFF.md'].replace('Genre only', 'Genre and Playlist')),
                              ('PHASE5_HANDOFF.md', texts['PHASE5_HANDOFF.md'].replace('Obtain each selected exact package approval', 'All packages are approved'))):
                with self.subTest(name=name, bad=bad[:30]):
                    (folder/name).write_bytes(bad.encode())
                    bind()
                    with self.assertRaises(ValueError):
                        acceptance.verify_documents(self.root, dossier, coverage)
                    (folder/name).write_bytes(texts[name].encode())
                    bind()
            (folder/'PHASE5_HANDOFF.md').unlink()
            with self.assertRaises(OSError):
                acceptance.verify_documents(self.root, dossier, coverage)

    def mixed_downloads(self):
        # Real source workflow matrices/upload names and the real mixed-workflow
        # directory layout; payloads are bounded fixtures, never M6 executions.
        repo = Path(__file__).resolve().parents[2]
        for name in provenance.PATHS:
            raw = subprocess.check_output(['git', 'show', maintenance.BASE+':'+name], cwd=repo)
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        expected = {'head': 'f'*40, 'plan_sha256': 'p'}
        plan = provenance.job_plan(self.root, expected['head'])
        downloads, archives = self.root/'config/ci-downloaded', self.root/'config/m7-archives'
        downloads.mkdir(parents=True)
        archives.mkdir(parents=True)
        index = {'head': 'f'*40, 'base': 'e'*40, 'plan_sha256': 'p', 'workflows': [], 'files': []}
        snapshot = {'repository': provenance.REPO, 'pull_request': {
            'number': 99, 'head': {'sha': 'f'*40}, 'base': {'sha': 'e'*40, 'repo': {'full_name': provenance.REPO}},
            'state': 'open', 'draft': True, 'merged': False}, 'runs': []}
        node = 'one.py::test_actual'
        execution = {'nodes': [node], 'exitstatus': 0, 'seconds': 0, 'reports': [
            {'nodeid': node, 'when': phase, 'outcome': 'passed', 'seconds': 0,
             'wasxfail': False, 'skip_reason': None} for phase in ('setup', 'call', 'teardown')]}
        job_id, artifact_id = 0, 0
        for run_id, (workflow, wanted) in enumerate(plan.items(), 1):
            jobs = []
            for title in sorted(wanted['jobs']):
                job_id += 1
                jobs.append({'id': job_id, 'run_id': run_id, 'head_sha': 'f'*40, 'name': title,
                             'status': 'completed', 'conclusion': 'success'})
            url = f'https://github.com/{provenance.REPO}/actions/runs/{run_id}'
            run = {'id': run_id, 'name': workflow, 'head_sha': 'f'*40, 'path': wanted['path'],
                   'event': 'pull_request', 'repository': {'full_name': provenance.REPO},
                   'status': 'completed', 'conclusion': 'success', 'html_url': url, 'pull_requests': [{'number': 99}]}
            index['workflows'].append({'name': workflow, 'head': 'f'*40, 'status': 'completed',
                'conclusion': 'success', 'url': url, 'jobs': [{k: j[k] for k in ('id', 'name', 'status', 'conclusion')} for j in jobs]})
            artifact_metadata = []
            for title in sorted(wanted['artifacts']):
                artifact_id += 1
                payloads = {'metadata.txt': b'bounded offline fixture'}
                platform = 'Windows' if 'windows-latest' in title else 'Linux'
                if title in ('collection-ubuntu-latest', 'collection-windows-latest'):
                    payloads = {'collection.json': json.dumps(dict(expected, platform=platform,
                                kind='collection', original=[node], units={})).encode()}
                elif title in ('validation-ubuntu-latest-core', 'validation-windows-latest-core'):
                    payloads = {'group-core.json': json.dumps(dict(expected, platform=platform, kind='group',
                        group='core', success=True, commands=[], seconds=0, unit_execution={}, pytest=execution)).encode()}
                elif title.startswith('phase5-m') and (title.endswith('-protocol-ubuntu-latest')
                        or title.endswith('-protocol-windows-latest') or title in ('phase5-m2-ubuntu-latest', 'phase5-m2-windows-latest')):
                    group = '' if title.startswith('phase5-m2-') else 'protocol/'
                    payloads = {group+'collection.json': json.dumps({'nodes': [node], 'exitstatus': 0}).encode(),
                                group+'report.json': json.dumps(dict(expected, platform=platform, group='protocol',
                                kind=title[:9]+'-fixture-execution', execution=execution)).encode()}
                encoded = io.BytesIO()
                with zipfile.ZipFile(encoded, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
                    for member, raw in payloads.items():
                        bundle.writestr(member, raw)
                        path = downloads/title/member
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(raw)
                        index['files'].append({'path': title+'/'+member, 'sha256': hashlib.sha256(raw).hexdigest(),
                                               'workflow': workflow, 'artifact_id': artifact_id})
                zip_bytes = encoded.getvalue()
                (archives/f'{artifact_id}.zip').write_bytes(zip_bytes)
                artifact_metadata.append({'id': artifact_id, 'name': title, 'size_in_bytes': len(zip_bytes),
                    'digest': 'sha256:'+hashlib.sha256(zip_bytes).hexdigest(), 'expired': False,
                    'workflow_run': {'id': run_id, 'head_sha': 'f'*40}})
            snapshot['runs'].append({'run': run, 'jobs': {'total_count': len(jobs), 'jobs': jobs},
                                     'artifacts': {'total_count': len(artifact_metadata), 'artifacts': artifact_metadata}})
        snapshot_path = self.root/'config/m7-github-provenance.json'
        snapshot_path.write_bytes(json.dumps(snapshot).encode())
        return downloads, archives, index, snapshot, snapshot_path, provenance.digest(snapshot_path), expected

    def test_actual_mixed_workflow_replay_excludes_raw_phase5_collections_and_rejects_omitted_jobs(self):
        downloads, archives, index, snapshot, path, pin, expected = self.mixed_downloads()
        with patch.object(acceptance, 'ROOT', self.root):
            acceptance.index_files(downloads, index, expected)
            acceptance.provenance_inputs(downloads, index, expected, path, pin, archives)
            reports = acceptance.discover_reports(downloads, index)
            legacy = acceptance.legacy_reports(reports)
            self.assertEqual(len(legacy), 4)
            self.assertGreater(len([p for p, _, _ in reports if p.name == 'collection.json']), 2)
            # Exercise the original reconciliation code, not a mirrored count check.
            from ci import validation
            baseline = {'pytest': ['one.py::test_actual'], 'unittest': {}}
            plan = {'pytest_groups': {'core': ['one.py']}, 'commands': {}}
            with patch.object(validation, 'identity', return_value=expected), patch.object(validation, 'read', return_value=baseline):
                validation.reconcile(plan, legacy, index['base'])
                collided = [r for p, r, _ in reports if p.name == 'collection.json' or p.name.startswith('group-')]
                with self.assertRaises(ValueError):
                    validation.reconcile(plan, collided, index['base'])
            omitted = copy.deepcopy(index)
            omitted['workflows'][0]['jobs'].pop()
            with self.assertRaisesRegex(ValueError, 'Omitted/substituted indexed job'):
                acceptance.provenance_inputs(downloads, omitted, expected, path, pin, archives)
            truncated = copy.deepcopy(snapshot)
            truncated['runs'][0]['jobs']['jobs'].pop()
            truncated['runs'][0]['jobs']['total_count'] -= 1
            # Even a source export with a matching truncated count fails the
            # independently derived workflow job plan.
            with self.assertRaisesRegex(ValueError, 'Missing/extra planned job'):
                provenance.authenticate(self.root, omitted, truncated, expected)
            path.write_bytes(json.dumps(truncated).encode())
            with self.assertRaisesRegex(ValueError, 'Independent provenance digest mismatch'):
                acceptance.provenance_inputs(downloads, omitted, expected, path, pin, archives)

    def test_archive_final_sha_and_digest_cannot_be_replaced_by_index_claims(self):
        downloads, archives, index, snapshot, path, pin, expected = self.mixed_downloads()
        with patch.object(acceptance, 'ROOT', self.root):
            bad = copy.deepcopy(snapshot)
            bad['runs'][0]['artifacts']['artifacts'][0]['workflow_run']['head_sha'] = 'a'*40
            with self.assertRaisesRegex(ValueError, 'final-SHA artifact provenance'):
                provenance.authenticate(self.root, index, bad, expected)
            archive = next(archives.iterdir())
            archive.write_bytes(b'changed ZIP')
            with self.assertRaisesRegex(ValueError, 'Archive provenance digest mismatch'):
                acceptance.provenance_inputs(downloads, index, expected, path, pin, archives)


if __name__ == '__main__':
    unittest.main()
