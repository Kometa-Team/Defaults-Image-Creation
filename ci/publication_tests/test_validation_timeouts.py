"""Exact current timeout policy and immutable, independently checked history."""
import copy
import itertools
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from ci import phase5_m6_maintenance as m6
from ci import phase5_m7_maintenance as m7

ROOT=m6.ROOT


class ValidationTimeoutTests(unittest.TestCase):
    def test_all_workflows_change_only_timeout_fields(self):
        bindings=m6.verify_timeouts()
        changed_jobs=0
        historical={name for name in m6._git(ROOT,'ls-tree','-r','--name-only',
            m6.TIMEOUT_BASE,'.github/workflows').decode().splitlines() if name.endswith('.yml')}
        current={path.relative_to(ROOT).as_posix() for path in (ROOT/'.github/workflows').glob('*.yml')}
        addition={'.github/workflows/phase6-playlist-validation.yml',
                  '.github/workflows/catalog-reservations-validation.yml'}
        self.assertEqual(current,historical|addition)
        from ci.phase6_playlist_maintenance import verify_scope
        verify_scope(ROOT,addition)
        for name in sorted(historical):
            path=ROOT/name
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
                    if name=='.github/workflows/default-poster-validation.yml' and job=='phase4':
                        self.assertEqual(now,90 if values=={'os':'windows-latest','group':'foundations'} else 60)
                    else:
                        self.assertIn(now,(15,60))
                        if was==60:self.assertEqual(now,60)
                    self.assertGreaterEqual(now,was)
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
            raw=m7.historical_bytes(ROOT,name,(ROOT/name).read_bytes())
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

    def test_windows_foundations_exception_changes_only_its_budget(self):
        name='.github/workflows/default-poster-validation.yml'
        before=m6._git(ROOT,'show','8452b188187ef56d38d8e03cf25a26be9a454fe4:'+name).replace(b'\r\n',b'\n')
        start=before.index(b'  phase4:\n');end=before.index(b'  people_security:\n',start)
        job=before[start:end]
        expression=b"${{ matrix.os == 'windows-latest' && matrix.group == 'foundations' && 90 || 60 }}"
        self.assertEqual(job.count(b'    timeout-minutes: 60\n'),1)
        expected=before[:start]+job.replace(b'    timeout-minutes: 60\n',b'    timeout-minutes: '+expression+b'\n')+before[end:]
        current=(ROOT/name).read_bytes().replace(b'\r\n',b'\n')
        self.assertEqual(current,expected)
        m6.verify_timeout_scope(ROOT,{name})
        read=Path.read_bytes
        for bad in (before,current.replace(b'&& 90 || 60',b'&& 120 || 60'),
                    current.replace(expression,expression.replace(b'windows-latest',b'ubuntu-latest')),
                    current.replace(expression,expression.replace(b'foundations',b'atomic')),
                    current.replace(b'&& 90 || 60',b'&& 90 || 90'),
                    current.replace(b'  contents: read',b'  contents: write'),
                    current.replace(b'run: python ci/phase4.py run',b'run: echo skipped')):
            self.assertNotEqual(bad,current)
            with self.subTest(sha256=m6.sha(bad)),patch.object(Path,'read_bytes',lambda p:bad if p==ROOT/name else read(p)),self.assertRaises(ValueError):
                m6.verify_timeout_scope(ROOT,{name})

    def test_historical_timeout_receipt_scope_is_exact_physical_and_committed(self):
        name=m6.HISTORICAL_TIMEOUT_RECEIPT;target=ROOT/name
        read=Path.read_bytes;good=read(target)
        self.assertEqual(m6.sha(good),m6.HISTORICAL_TIMEOUT_SHA256)
        m6.verify_timeout_scope(ROOT,{name})
        for bad in (good+b'\n',good+b'\n# unapproved',read(ROOT/m6.TIMEOUT_RECEIPT)):
            with self.subTest(sha256=m6.sha(bad)),patch.object(Path,'read_bytes',lambda p:bad if p==target else read(p)),self.assertRaises(ValueError):
                m6.verify_timeout_scope(ROOT,{name})
        def missing(path):
            if path==target:raise FileNotFoundError(name)
            return read(path)
        with patch.object(Path,'read_bytes',missing),self.assertRaises(OSError):m6.verify_timeout_scope(ROOT,{name})
        git=m6._git
        def committed(root,*args):
            return b'forged' if args==('show','HEAD:'+name) else git(root,*args)
        with patch.object(m6,'_git',side_effect=committed),self.assertRaises(ValueError):m6.verify_timeout_scope(ROOT,{name})
        for unknown in ('ci/unapproved-timeout-registration.json','.github/workflows/unrelated.yml'):
            with self.subTest(path=unknown),self.assertRaises(ValueError):m6.verify_timeout_scope(ROOT,{name,unknown})


if __name__=='__main__':unittest.main()
