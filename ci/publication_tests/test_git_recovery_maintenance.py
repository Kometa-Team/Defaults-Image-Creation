"""Current recovery bytes plus independently preserved historical registrations."""
import copy
import json
from pathlib import Path
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ci import people_publication_maintenance as p
from ci import people_unicode_maintenance as u
from ci import phase5_m5_maintenance as m5
from ci import phase5_m6_maintenance as m6

ROOT=p.ROOT


class RecoveryRegistrationTests(unittest.TestCase):
    def test_exact_current_sources_ci_bindings_and_historical_cohort(self):
        recovery=p.recovery_bindings();native=p.git_bindings();ci=m6.recovery_ci_bindings()
        self.assertEqual(len(recovery),5);self.assertEqual(len(native),7);self.assertEqual(len(ci),4)
        self.assertEqual(set(recovery),p.RECOVERY_MEMBERS)
        for name,b in recovery.items():
            self.assertEqual(p.digest(m6.timeout_bytes(ROOT,name,(ROOT/name).read_bytes())),b['sha256'])
            if name in native:self.assertEqual(native[name]['sha256'],b['sha256'])
        for name,b in ci.items():
            self.assertEqual(m6.sha(m6.timeout_bytes(ROOT,name,(ROOT/name).read_bytes())),b['sha256'])
            self.assertEqual(m6.sha(m6.recovery_ci_bytes(ROOT,name,(ROOT/name).read_bytes())),b['before_sha256'])
            for forged in (b'forged',b['predecessor_lf'].encode()+b'\n'):
                self.assertEqual(m6.recovery_ci_bytes(ROOT,name,forged),forged)
        self.assertEqual(len(m6.verify_checkout()['members']),34)
        self.assertEqual(len(m5.verify_checkout()['members']),25)
        self.assertEqual(len(u.verify()),41)
        self.assertEqual(m5.unicode_adapter().publication_adapter().recovery_bindings(),recovery)

    def test_every_recovery_source_rejects_changes_deletions_and_rollback(self):
        read=Path.read_bytes
        for name,b in p.recovery_bindings().items():
            target=ROOT/name;variants=[read(target)+b'\n# unauthorized']
            if b['predecessor_lf'] is not None:variants.append(b['predecessor_lf'].encode())
            for raw in variants:
                with self.subTest(name=name,attack='change_or_rollback'),patch.object(Path,'read_bytes',lambda q:raw if q==target else read(q)):
                    with self.assertRaises(ValueError):p.verify()
            def missing(q):
                if q==target:raise FileNotFoundError(name)
                return read(q)
            with self.subTest(name=name,attack='deletion'),patch.object(Path,'read_bytes',missing),self.assertRaises(OSError):p.verify()

    def test_receipt_scope_hash_predecessor_and_authority_attacks_fail_closed(self):
        read=Path.read_bytes
        for module,receipt,verify in ((p,p.RECOVERY_RECEIPT,p.recovery_bindings),(m6,m6.RECOVERY_CI_RECEIPT,m6.recovery_ci_bindings)):
            target=ROOT/receipt;good=json.loads(read(target))
            for kind in ('addition','deletion','hash','predecessor','ci','publication','extra'):
                bad=copy.deepcopy(good);row=next(iter(bad['files'].values()))
                if kind=='addition':bad['files']['unapproved.py']=row
                elif kind=='deletion':bad['files'].pop(next(iter(bad['files'])))
                elif kind=='hash':row['sha256']='0'*64
                elif kind=='predecessor':row['before_sha256']='0'*64
                elif kind=='ci':bad['ci_authorized']=True
                elif kind=='publication':bad['publication_authorized']=True
                else:bad['unreviewed']=True
                raw=json.dumps(bad).encode()
                with self.subTest(receipt=receipt,attack=kind),patch.object(Path,'read_bytes',lambda q:raw if q==target else read(q)):
                    with self.assertRaises(ValueError):verify()
                    # Even resealing the mocked receipt pin cannot expand scope,
                    # alter independent predecessor pins or authorize bad bytes.
                    pin_name='RECOVERY_PIN' if module is p else 'RECOVERY_CI_PIN'
                    with patch.object(module,pin_name,module.fingerprint(bad)),self.assertRaises(ValueError):verify()

    def test_current_ci_tamper_rollback_and_deletion_never_project_as_history(self):
        read=Path.read_bytes
        for name,b in m6.recovery_ci_bindings().items():
            target=ROOT/name
            for raw in (read(target)+b'\n# unauthorized',b['predecessor_lf'].encode()):
                with self.subTest(name=name),patch.object(Path,'read_bytes',lambda q:raw if q==target else read(q)),self.assertRaises(ValueError):m6.verify_checkout()
            def missing(q):
                if q==target:raise FileNotFoundError(name)
                return read(q)
            with self.subTest(name=name,attack='missing'),patch.object(Path,'read_bytes',missing),self.assertRaises(OSError):m6.verify_checkout()

    def test_foreign_roots_links_and_reparse_ancestors_rejected(self):
        with self.assertRaises(ValueError):p.recovery_bindings(ROOT/'foreign')
        with self.assertRaises(ValueError):m6.recovery_ci_bindings(ROOT/'foreign')
        lstat=Path.lstat
        for target in (ROOT/'ci',ROOT/'ci/people-publication-git-recovery-v1.json',ROOT/'create_people_posters/people_git_recovery.py'):
            for link,reparse in ((True,False),(False,True)):
                def changed(q,*args,**kwargs):
                    value=lstat(q,*args,**kwargs)
                    if q==target:return SimpleNamespace(st_mode=stat.S_IFLNK if link else value.st_mode,st_file_attributes=0x400 if reparse else 0)
                    return value
                with self.subTest(path=str(target),link=link,reparse=reparse),patch.object(Path,'lstat',changed),self.assertRaises(ValueError):p.recovery_bindings()

    def test_exact_committed_registration_check_and_scope_fail_closed(self):
        names={'ci/phase5_m5_maintenance.py',m6.RECOVERY_CI_RECEIPT}
        def show(root,*args):
            self.assertEqual(args[0],'show')
            return (ROOT/args[1].removeprefix('HEAD:')).read_bytes()
        with patch.object(m6,'_git',side_effect=show):m6.verify_recovery_ci_scope(ROOT,names)
        with patch.object(m6,'_git',return_value=b'forged'),self.assertRaises(ValueError):m6.verify_recovery_ci_scope(ROOT,names)
        for old,new,status in [('100644','000000','D'),('000000','120000','A'),('100644','100644','R100')]:
            name=m6.RECOVERY_CI_RECEIPT;raw=(f':{old} {new} '+'0'*40+' '+'1'*40+f' {status}\0{name}\0').encode()
            with patch.object(m6,'_git',return_value=raw),self.assertRaises(ValueError):m6.verify_scope(ROOT,m6.BASE,{name})
        with self.assertRaises(ValueError):m6.verify_scope(ROOT,m6.BASE,{'ci/unapproved.py'})
        with self.assertRaises(ValueError):u.verify_scope(ROOT,u.M7_BASE,{'ci/unapproved.py'})

    def test_original_inventory_unicode_and_authorities_remain_exact(self):
        names=['create_defaults/bulk/contracts/activation/data/production-pins-v1.json',
               'ci/people-unicode-source-v1.json','ci/people-unicode-ci-v1.json',
               'ci/people-publication-git-v2.json','ci/people-publication-reliability-v1.json',
               'ci/phase5-m5-maintenance-v1.json','ci/phase5-m6-maintenance-v1.json']
        for name in names:self.assertEqual(p.git('show',p.RECOVERY_BASE+':'+name).replace(b'\r\n',b'\n'),(ROOT/name).read_bytes().replace(b'\r\n',b'\n'))
        self.assertEqual(len(json.loads((ROOT/names[0]).read_bytes())['files']),190)
        source,_=u.receipts();self.assertEqual(len(source['files']),22)
        for name,b in source['files'].items():
            current=(ROOT/name).read_bytes()
            if name==m6.PEOPLE_PR65_REQUIREMENTS:
                self.assertEqual(b['sha256'],m6.PEOPLE_PR65_BEFORE[name])
                current=m6.people_pr65_bytes(ROOT,name,current)
            self.assertEqual(u.digest(current,b['text_lf']),b['sha256'])
        for name in (p.RECOVERY_RECEIPT,m6.RECOVERY_CI_RECEIPT):
            v=json.loads((ROOT/name).read_bytes());self.assertIs(v['ci_authorized'],False);self.assertIs(v['publication_authorized'],False)


if __name__=='__main__':unittest.main()
