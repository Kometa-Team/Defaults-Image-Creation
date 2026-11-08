"""Exact current timeout policy and immutable, independently checked history."""
import copy
import itertools
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import yaml
from ci import phase5_m6_maintenance as m6

ROOT=m6.ROOT


class ValidationTimeoutTests(unittest.TestCase):
    def test_all_workflows_change_only_timeout_fields(self):
        bindings=m6.verify_timeouts()
        changed_jobs=0
        for path in sorted((ROOT/'.github/workflows').glob('*.yml')):
            name=path.relative_to(ROOT).as_posix()
            before=yaml.safe_load(m6._git(ROOT,'show',m6.TIMEOUT_BASE+':'+name))
            after=yaml.safe_load(path.read_bytes())
            for job,old in before['jobs'].items():
                new=after['jobs'][job]
                previous=old['timeout-minutes'];current=new['timeout-minutes']
                if previous!=current:
                    changed_jobs+=1
                    self.assertIn(name,bindings)
                matrix=new.get('strategy',{}).get('matrix',{})
                keys=list(matrix)
                for row in itertools.product(*(matrix[k] for k in keys)):
                    values=dict(zip(keys,row))
                    def evaluate(value):
                        if isinstance(value,int):return value
                        s=value.removeprefix('${{').removesuffix('}}').strip()
                        for k,v in values.items():s=s.replace('matrix.'+k,repr(v))
                        s=s.replace('&&',' and ').replace('||',' or ')
                        return eval(s,{'__builtins__':{},'startsWith':lambda a,b:a.startswith(b)})
                    was,now=evaluate(previous),evaluate(current)
                    self.assertIn(now,(15,60))
                    self.assertGreaterEqual(now,was)
                    if was==60:self.assertEqual(now,60)
                new['timeout-minutes']=previous
            self.assertEqual(before,after,name)
        self.assertEqual(changed_jobs,12)

    def test_exact_physical_bindings_and_history(self):
        for name,b in m6.verify_timeouts().items():
            raw=(ROOT/name).read_bytes()
            self.assertEqual(m6.sha(raw),b['sha256'])
            self.assertEqual(m6.timeout_bytes(ROOT,name,raw),
                             b['predecessor_lf'].encode() if b['predecessor_lf'] is not None else raw)
            self.assertEqual(m6.timeout_bytes(ROOT,name,b'forged'),b'forged')

    def test_changes_rollback_and_deletions_fail_closed(self):
        read=Path.read_bytes
        for name,b in m6.timeout_bindings().items():
            target=ROOT/name
            variants=[read(target)+b'\n# unauthorized']
            if b['predecessor_lf'] is not None:variants.append(b['predecessor_lf'].encode())
            for raw in variants:
                with self.subTest(name=name),patch.object(Path,'read_bytes',lambda p:raw if p==target else read(p)),self.assertRaises(ValueError):
                    m6.verify_timeouts()
            def missing(p):
                if p==target:raise FileNotFoundError(name)
                return read(p)
            with self.subTest(name=name,attack='delete'),patch.object(Path,'read_bytes',missing),self.assertRaises(OSError):m6.verify_timeouts()

    def test_receipt_scope_hash_predecessors_and_authority_fail_closed(self):
        read=Path.read_bytes;target=ROOT/m6.TIMEOUT_RECEIPT
        good=json.loads(read(target))
        for attack in ('add','delete','hash','predecessor','baseline','ci','publication'):
            bad=copy.deepcopy(good);row=next(iter(bad['files'].values()))
            if attack=='add':bad['files']['unapproved.py']=row
            elif attack=='delete':bad['files'].pop(next(iter(bad['files'])))
            elif attack=='hash':row['sha256']='0'*64
            elif attack=='predecessor':row['before_sha256']='0'*64
            elif attack=='baseline':bad['baseline_commit']='0'*40
            elif attack=='ci':bad['ci_authorized']=True
            else:bad['publication_authorized']=True
            with self.subTest(attack=attack),patch.object(Path,'read_bytes',lambda p:json.dumps(bad).encode() if p==target else read(p)),self.assertRaises(ValueError):m6.verify_timeouts()

    def test_committed_bytes_and_scope_remain_mandatory(self):
        names={'.github/workflows/default-poster-validation.yml'}
        def show(root,*args):return (ROOT/args[1].removeprefix('HEAD:')).read_bytes()
        with patch.object(m6,'_git',side_effect=show):m6.verify_timeout_scope(ROOT,names)
        with patch.object(m6,'_git',return_value=b'forged'),self.assertRaises(ValueError):m6.verify_timeout_scope(ROOT,names)
        with self.assertRaises(ValueError):m6.verify_timeout_scope(ROOT,{'ci/unapproved.py'})
        with self.assertRaises(ValueError):m6.timeout_bindings(ROOT/'foreign')


if __name__=='__main__':unittest.main()
