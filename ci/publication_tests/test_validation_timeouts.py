"""Exact current timeout policy and immutable, independently checked history."""
import copy
import itertools
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from ci import phase5_m6_maintenance as m6

ROOT=m6.ROOT


class ValidationTimeoutTests(unittest.TestCase):
    def test_all_workflows_change_only_timeout_fields(self):
        bindings=m6.verify_timeouts()
        changed_jobs=0
        for path in sorted((ROOT/'.github/workflows').glob('*.yml')):
            name=path.relative_to(ROOT).as_posix()
            before=m6._git(ROOT,'show',m6.TIMEOUT_BASE+':'+name).decode()
            after=path.read_bytes().replace(b'\r\n',b'\n').decode()
            def jobs(raw):
                body=raw.split('\njobs:\n',1)[1]
                entries=list(re.finditer(r'(?m)^  ([a-zA-Z0-9_-]+):\n',body))
                self.assertTrue(entries)
                return {m[1]:body[m.start():entries[i+1].start() if i+1<len(entries) else len(body)] for i,m in enumerate(entries)}
            old_jobs=jobs(before);new_jobs=jobs(after)
            self.assertEqual(set(old_jobs),set(new_jobs))
            restored=after
            for job,old in old_jobs.items():
                new=new_jobs[job]
                def timeout(raw):
                    values=re.findall(r'(?m)^    timeout-minutes: ([^\n]+)$',raw)
                    self.assertEqual(len(values),1)
                    return values[0]
                previous=timeout(old);current=timeout(new)
                if previous!=current:
                    changed_jobs+=1
                    self.assertIn(name,bindings)
                # Existing matrices use bounded inline or block os/group lists.
                # Reject new matrix shapes rather than silently missing cases.
                matrix={}
                if previous!=current and '      matrix:\n' in new:
                    block=new.split('      matrix:\n',1)[1]
                    block=re.split(r'(?m)^ {0,6}[^ \n]',block,maxsplit=1)[0]
                    key=None
                    for line in block.splitlines():
                        if not line.strip():continue
                        match=re.fullmatch(r'        (os|group):(?: \[([a-zA-Z0-9_, -]+)\])?',line)
                        if match:
                            key=match[1]
                            self.assertNotIn(key,matrix)
                            matrix[key]=[s.strip() for s in match[2].split(',')] if match[2] else []
                        else:
                            item=re.fullmatch(r' {8}(?:  )?- ([a-zA-Z0-9_-]+)',line)
                            self.assertIsNotNone(item,line)
                            self.assertIsNotNone(key)
                            matrix[key].append(item[1])
                    self.assertTrue(all(matrix.values()))
                keys=list(matrix)
                for row in itertools.product(*(matrix[k] for k in keys)):
                    values=dict(zip(keys,row))
                    def evaluate(value):
                        if value.isdigit():return int(value)
                        s=value.removeprefix('${{').removesuffix('}}').strip()
                        for k,v in values.items():s=s.replace('matrix.'+k,repr(v))
                        s=s.replace('&&',' and ').replace('||',' or ')
                        return eval(s,{'__builtins__':{},'startsWith':lambda a,b:a.startswith(b)})
                    was,now=evaluate(previous),evaluate(current)
                    self.assertIn(now,(15,60))
                    self.assertGreaterEqual(now,was)
                    if was==60:self.assertEqual(now,60)
                original=new.replace('    timeout-minutes: '+current+'\n','    timeout-minutes: '+previous+'\n',1)
                self.assertEqual(old,original,job)
                self.assertEqual(restored.count(new),1)
                restored=restored.replace(new,original,1)
            # Physical equality also preserves comments, permissions, tests,
            # dependencies, matrix cases, steps and acceptance gate bytes.
            self.assertEqual(before,restored,name)
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
