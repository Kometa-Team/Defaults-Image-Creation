"""Focused scope-only controls; full sealed provenance checks remain independent."""
import ast
from contextlib import ExitStack
from pathlib import Path
import stat
import subprocess
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

POLICY_SOURCE = (Path(__file__).resolve().parents[2]/'ci/phase4_m7.py').read_text(encoding='utf8')
EXPECTED = frozenset('create_defaults/lifecycle/'+name for name in (
    'PHASE5_M7_ACCEPTANCE_REPORT.md', 'PHASE5_M7_ACCEPTANCE.json',
    'PHASE5_M7_COVERAGE.json', 'PHASE5_HANDOFF.md'))


def policy():
    # Exercise the actual production function, isolated from expensive unrelated
    # provenance imports. This is not proof of the sealed checkout transition.
    selected = []
    for node in ast.parse(POLICY_SOURCE).body:
        if (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in
                {'BASE', 'NEW', 'ALLOWED', 'PLANNING_DOCUMENTS', 'M7_DOSSIER_DOCUMENTS'}
                for t in node.targets)) or (isinstance(node, ast.FunctionDef) and node.name == 'changed_scope'):
            selected.append(node)
    def require(ok, message):
        if not ok:
            raise ValueError(message)
    namespace = dict(Path=Path, stat=stat, subprocess=subprocess, require=require)
    exec(compile(ast.Module(body=selected, type_ignores=[]), '<scope-policy>', 'exec'), namespace)
    return namespace


class Phase5M7AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.storage = ModuleType('ci.people_storage_maintenance')
        self.storage.scope_members = lambda: frozenset()
        self.storage.verify_scope = lambda *args: None
        self.stack.enter_context(patch.dict('sys.modules', {'ci.people_storage_maintenance': self.storage}))

    def repository(self, existing=()):
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='m7-scope-')))
        def git(*args, data=None):
            return subprocess.check_output(['git', '-C', str(root), *args], input=data,
                                           stderr=subprocess.PIPE).decode().strip()
        git('init', '--quiet')
        git('config', 'user.name', 'Scope acceptance')
        git('config', 'user.email', 'scope@invalid.local')
        git('config', 'core.autocrlf', 'false')
        git('config', 'core.ignorecase', 'false')
        git('config', 'core.hooksPath', str(root/'no-hooks'))
        for name in ('README.md', *existing):
            self.write(root, name)
        git('add', '--all')
        git('commit', '--quiet', '-m', 'baseline')
        ns = policy()
        ns.update(ROOT=root, BASE=git('rev-parse', 'HEAD'))
        return root, git, ns['changed_scope']

    @staticmethod
    def write(root, name, value='original\n'):
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding='utf8')

    @staticmethod
    def commit(git):
        git('add', '--all')
        git('commit', '--quiet', '-m', 'scope case')

    def test_exact_four_paths_leave_original_allowances_and_baseline_unchanged(self):
        ns = policy()
        self.assertEqual(ns['M7_DOSSIER_DOCUMENTS'], EXPECTED)
        self.assertEqual(ns['BASE'], '68179d1c568449375ca72b23239b57770dfc229e')
        self.assertEqual(len(ns['ALLOWED']), 15)
        self.assertIn('create_defaults/lifecycle/ROADMAP.md', ns['ALLOWED'])
        self.assertEqual(len(ns['PLANNING_DOCUMENTS']), 5)
        self.assertFalse(EXPECTED & (ns['ALLOWED'] | ns['PLANNING_DOCUMENTS']))

    def test_each_exact_regular_addition(self):
        for name in sorted(EXPECTED):
            with self.subTest(name=name):
                root, git, check = self.repository()
                self.write(root, name)
                self.commit(git)
                self.assertEqual(check(), {name})

    def test_complete_set_with_existing_roadmap_modification(self):
        roadmap = 'create_defaults/lifecycle/ROADMAP.md'
        root, git, check = self.repository([roadmap])
        for name in EXPECTED | {roadmap}:
            self.write(root, name, 'new status\n')
        self.commit(git)
        self.assertEqual(check(), EXPECTED | {roadmap})

    def test_every_dossier_modification_deletion_and_rename_is_rejected(self):
        for name in sorted(EXPECTED):
            for attack in ('modify', 'delete', 'rename'):
                with self.subTest(name=name, attack=attack):
                    root, git, check = self.repository([name])
                    if attack == 'delete':
                        (root/name).unlink()
                    elif attack == 'rename':
                        (root/name).rename(root/next(n for n in sorted(EXPECTED) if n != name))
                    else:
                        self.write(root, name, 'modified\n')
                    self.commit(git)
                    with self.assertRaisesRegex(ValueError, 'regular-file addition'):
                        check()

    def test_each_executable_or_git_symlink_addition_is_rejected(self):
        for name in sorted(EXPECTED):
            for attack in ('executable', 'symlink'):
                with self.subTest(name=name, attack=attack):
                    root, git, check = self.repository()
                    self.write(root, name)
                    git('add', '--all')
                    if attack == 'executable':
                        git('update-index', '--chmod=+x', '--', name)
                    else:
                        blob = git('hash-object', '-w', '--stdin', data=b'README.md')
                        git('update-index', '--cacheinfo', '120000,'+blob+','+name)
                    git('commit', '--quiet', '-m', 'unsafe mode')
                    with self.assertRaisesRegex(ValueError, 'regular-file addition'):
                        check()

    def test_each_physical_file_parent_link_reparse_and_directory_is_rejected(self):
        for name in sorted(EXPECTED):
            for attack in ('file-link', 'parent-link', 'reparse', 'directory'):
                with self.subTest(name=name, attack=attack):
                    root, git, check = self.repository()
                    self.write(root, name)
                    self.commit(git)
                    target = (root/name).parent if attack == 'parent-link' else root/name
                    original = Path.lstat
                    def observed(part, *args, **kwargs):
                        info = original(part, *args, **kwargs)
                        if part != target:
                            return info
                        return SimpleNamespace(st_mode=stat.S_IFLNK if attack.endswith('link') else
                            stat.S_IFDIR if attack == 'directory' else info.st_mode,
                            st_file_attributes=0x400 if attack == 'reparse' else 0)
                    with patch.object(Path, 'lstat', observed), self.assertRaises(ValueError):
                        check()

    def test_unknown_spelling_and_runtime_paths_remain_rejected(self):
        for name in ('create_defaults/lifecycle/PHASE5_M7_OTHER.json',
                     'create_defaults/lifecycle/PHASE5_M7_ACCEPTANCE.JSON',
                     'create_defaults/lifecycle/phase5_HANDOFF.md',
                     'create_defaults/bulk/catalog/genre.yml', '.github/workflows/new-policy.yml'):
            with self.subTest(name=name):
                root, git, check = self.repository()
                self.write(root, name)
                self.commit(git)
                with self.assertRaisesRegex(ValueError, 'existing runtime, policy, workflow or evidence boundary'):
                    check()

    def test_existing_storage_scope_still_delegates_and_failure_propagates(self):
        name = 'ci/existing-approved.py'
        root, git, check = self.repository()
        self.write(root, name)
        self.commit(git)
        self.storage.scope_members = lambda: {name}
        calls = []
        self.storage.verify_scope = lambda *args: calls.append(args)
        self.assertEqual(check(), {name})
        self.assertEqual(calls[0][0], root)
        self.assertEqual(calls[0][2], {name})
        def rejected(*args):
            raise ValueError('sealed guard rejected')
        self.storage.verify_scope = rejected
        with self.assertRaisesRegex(ValueError, 'sealed guard rejected'):
            check()


if __name__ == '__main__':
    unittest.main()
