"""Preserve exact historical pins and reject retention scope/version drift."""
from copy import deepcopy
import json
import io
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from ci import people_retention_maintenance as retention
from ci import people_storage_maintenance as storage

ROOT=Path(__file__).resolve().parents[2]


class PeopleRetentionMaintenanceTests(unittest.TestCase):
    def test_sanitized_progress_arrives_before_child_exit_through_buffered_parent(self):
        # The child cannot finish until the test has received both progress
        # lines. This checks delivery, rather than eventual captured output.
        secret='NOT_A_REAL_LIVE_PROGRESS_CREDENTIAL_987654321'
        with tempfile.TemporaryDirectory() as directory:
            release=Path(directory)/'release'
            log=Path(directory)/'progress.log'
            child="""import os,sys,time
from pathlib import Path
value=os.environ['TMDB_KEY']
print('first stdout value='+value)
print('first stderr value='+value,file=sys.stderr)
while not Path(sys.argv[1]).exists():time.sleep(.02)
print('last stdout')
print('last stderr',file=sys.stderr)
raise SystemExit(3)
"""
            driver="""import os,sys
from pathlib import Path
from create_people_posters.people_diagnostics import protect_cli
from create_people_posters.people_process import run_process
protect_cli()
result=run_process([sys.executable,'-c',sys.argv[1],sys.argv[2]],cwd=Path.cwd(),
                   env=dict(os.environ,PYTHONUNBUFFERED='0'),tee=True,log_path=sys.argv[3],timeout=30)
raise SystemExit(result.returncode)
"""
            environment=dict(os.environ,PYTHONUNBUFFERED='0',TMDB_KEY=secret,
                             PYTHONDONTWRITEBYTECODE='1')
            process=subprocess.Popen([sys.executable,'-c',driver,child,str(release),str(log)],
                cwd=ROOT,env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                text=True,encoding='utf8')
            received=queue.Queue();lines={'stdout':[],'stderr':[]}
            def read(name):
                for line in getattr(process,name):
                    lines[name].append(line);received.put((name,line))
            threads=[threading.Thread(target=read,args=(name,),daemon=True) for name in lines]
            for thread in threads:thread.start()
            try:
                seen={}
                for _ in range(2):
                    try:name,line=received.get(timeout=10)
                    except queue.Empty:self.fail('Progress was buffered until process exit')
                    seen[name]=line
                self.assertIsNone(process.poll())
                self.assertEqual(set(seen),{'stdout','stderr'})
                self.assertIn('first stdout',seen['stdout'])
                self.assertIn('first stderr',seen['stderr'])
                self.assertNotIn(secret,''.join(seen.values()))
                saved=log.read_text(encoding='utf8')
                self.assertIn('first stdout',saved);self.assertIn('first stderr',saved)
                self.assertNotIn(secret,saved)
            finally:
                release.touch()
                try:process.wait(timeout=30)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
                for thread in threads:thread.join(timeout=5)
                process.stdout.close();process.stderr.close()
            self.assertEqual(process.returncode,3)
            self.assertIn('last stdout',''.join(lines['stdout']))
            self.assertIn('last stderr',''.join(lines['stderr']))
            self.assertNotIn(secret,log.read_text(encoding='utf8'))

    def test_capture_remains_quiet_and_partial_credentials_are_withheld(self):
        from create_people_posters.people_process import run_process
        from create_people_posters.people_diagnostics import WITHHELD
        secret='NOT_A_REAL_CAPTURE_PROGRESS_CREDENTIAL_123456789'
        environment=dict(os.environ,TMDB_KEY=secret,PYTHONUNBUFFERED='0')
        code="import os,sys;print('visible progress');os.write(2,os.environ['TMDB_KEY'][:18].encode());raise SystemExit(4)"
        out=io.StringIO();err=io.StringIO()
        with tempfile.TemporaryDirectory() as directory,patch('sys.stdout',out),patch('sys.stderr',err):
            log=Path(directory)/'capture.log'
            result=run_process([sys.executable,'-c',code],env=environment,log_path=log,timeout=30)
            self.assertEqual(result.returncode,4)
            self.assertIn('visible progress',result.stdout)
            self.assertEqual(result.stderr,WITHHELD+'\n')
            self.assertNotIn(secret[:18],log.read_text(encoding='utf8'))
        self.assertEqual(out.getvalue(),'');self.assertEqual(err.getvalue(),'')
        self.assertEqual(environment['PYTHONUNBUFFERED'],'0')

    def test_exact_checkout_manifest_and_reviewed_ancestry(self):
        with patch.object(retention.subprocess,'check_output',side_effect=AssertionError('Frozen fixture Git interceptor')):
            value=retention.verify_checkout()
        self.assertEqual(value['production_successors'],[retention.WORKSPACE])
        self.assertFalse(value['publication_authorized'])

    def test_original_eight_cleanup_blobs_and_historical_manifests_stay_exact(self):
        value=storage.manifest()
        for name,binding in value['cohort'].items():
            self.assertEqual(storage.sha((ROOT/name).read_bytes()),binding['sha256'])
        for name in ['ci/people-security-maintenance.json','ci/dependency-maintenance-v1.json','ci/people-security-test-ids.json','ci/phase4-m7-test-ids.json','create_defaults/bulk/contracts/adoption/source-pins-v1.json']:
            old=subprocess.check_output(['git','show','ded9f33759f9fe3ed4ddf5f315dff01b163594ad:'+name],cwd=ROOT)
            self.assertEqual(retention.sha((ROOT/name).read_bytes()),retention.sha(old))

    def test_unknown_paths_and_unknown_predecessors_keep_original_pins(self):
        self.assertEqual(retention.selected_hash('create_defaults/create_poster.py','a'*64),'a'*64)
        self.assertEqual(retention.selected_hash(retention.WORKSPACE,'b'*64),'b'*64)
        value=retention.manifest()['members'][retention.WORKSPACE]
        self.assertEqual(retention.selected_hash(retention.WORKSPACE,value['before_sha256']),value['sha256'])
        progress=retention.manifest()['members'][retention.PROCESS]
        self.assertEqual(retention.selected_hash(retention.PROCESS,'b'*64),'b'*64)
        self.assertEqual(retention.selected_hash(retention.PROCESS,progress['before_sha256']),progress['sha256'])

    def test_every_new_member_tamper_rollback_and_deletion_fails_closed(self):
        value=retention.manifest()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in retention.scope_members():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
            old_bytes={name:subprocess.check_output(['git','show',value['baseline_commit']+':'+name],cwd=ROOT) for name,b in value['members'].items() if b['before_sha256'] is not None}
            with patch.object(retention,'ROOT',root),patch.object(retention,'MANIFEST',root/'ci/people-retention-maintenance-v1.json'),patch.object(retention.subprocess,'check_call'),patch.object(retention.subprocess,'run',side_effect=lambda args,**kw:type('Result',(),{'stdout':old_bytes[args[-1].split(':',1)[1]]})()):
                retention.verify_checkout()
                for name,binding in value['members'].items():
                    p=root/name;before=p.read_bytes()
                    p.write_bytes(before+b'\nunreviewed\n')
                    with self.subTest(name=name),self.assertRaises(ValueError):retention.verify_checkout()
                    p.unlink()
                    with self.assertRaises(OSError):retention.verify_checkout()
                    p.write_bytes(before)
                    if binding['before_sha256'] is not None:
                        p.write_bytes(old_bytes[name])
                        with self.assertRaises(ValueError):retention.verify_checkout()
                        p.write_bytes(before)

    def test_modified_manifest_cannot_refresh_approval_or_membership(self):
        value=retention.manifest()
        for field in ['members','production_successors','mandatory_unittest_ids','baseline_commit','audit_ancestor']:
            changed=deepcopy(value);changed[field]='unapproved'
            with patch.object(retention,'regular',return_value=type('P',(),{'read_bytes':lambda self:json.dumps(changed).encode()})()):
                with self.subTest(field=field),self.assertRaises(ValueError):retention.manifest()

    def test_mandatory_ids_are_exact_discovered_controls_on_both_os_jobs(self):
        import unittest as unit
        suite=unit.defaultTestLoader.discover(str(ROOT/'ci/dependency_tests'),pattern='test_people_retention*.py')
        def ids(item):
            if isinstance(item,unit.TestSuite):return [v for child in item for v in ids(child)]
            return [item.id()]
        self.assertEqual(sorted(ids(suite)),sorted(retention.test_ids()))
        self.assertGreaterEqual(len(retention.test_ids()),30)

    def test_scope_has_no_renderer_publisher_inventory_or_workflow_changes(self):
        self.assertEqual(set(storage.manifest()['cohort'])&retention.MEMBERS,set())
        for name in retention.MEMBERS:
            self.assertFalse(name.startswith('.github/'))
            self.assertNotIn(name,{'create_people_posters/poster_renderer.py','create_people_posters/publish_people_github.py'})


if __name__=='__main__':unittest.main()
