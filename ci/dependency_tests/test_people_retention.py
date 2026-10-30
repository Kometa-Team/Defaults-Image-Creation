"""Mandatory cross-platform retention controls; isolated test-owned fixtures only."""
from copy import deepcopy
from contextlib import closing
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from create_people_posters import people_verified_cleanup as worker
from create_people_posters import people_retention_state as local
from create_people_posters import people_retention_remote as network
from create_people_posters.people_workspaces import Workspaces


class Remote:
    def __init__(self,snapshot):self.value=snapshot;self.calls=0;self.fail=False
    def snapshot(self):
        if self.fail:raise local.RetentionBlocked('remote unavailable')
        return deepcopy(self.value)
    def confirm(self,snapshot,repositories=None):
        self.calls+=1
        if self.fail or any(snapshot[r]['head']!=self.value[r]['head'] for r in repositories or snapshot):
            raise local.RetentionBlocked('remote changed')
    def validate_ci(self,receipt,root):
        if receipt!={'head':'a'*40}:raise local.RetentionBlocked('CI mismatch')
        return receipt


class PeopleRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.config=self.root/'config';self.config.mkdir()
        (self.config/'state').mkdir();(self.config/'jobs').mkdir()
        self.snapshot={repo:dict(repo=repo,style=style,head='1'*40,tree='2'*40,entries={}) for style,repo in worker.REPOSITORIES.items()}
        self.rows=[];self.now=time.time();self.job='20261001T000000-123456789abc'
        self.db=sqlite3.connect(self.config/'state/publication_state.db')
        self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE jobs(id TEXT,status TEXT,created REAL,updated REAL,published REAL,error TEXT);
            CREATE TABLE batches(id TEXT,expected INTEGER,branch TEXT);
            CREATE TABLE publications(batch TEXT,style TEXT,repo TEXT,path TEXT,source TEXT,source_hash TEXT,prepared TEXT,published_hash TEXT,blob TEXT,branch TEXT,person TEXT,tmdb_id TEXT,status TEXT,commit_sha TEXT,last_attempt REAL);
            CREATE TABLE readmes(batch TEXT,repo TEXT,status TEXT);''')
        self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?)',(self.job,'cleanup_eligible',self.now-500000,self.now-400000,self.now-4*86400,''))
        self.db.execute('INSERT INTO batches VALUES(?,?,?)',(self.job,7,'master'))
        catalog={}
        for style,repo in worker.REPOSITORIES.items():
            rel=f'jobs/{self.job}/.publish/{self.job}/{style}/A/Images/A.jpg'
            row=self.add_file(rel,('image-'+style).encode(),scope='job',job=self.job,role='prepared_publication_copy',style=style)
            catalog[Path(rel).relative_to(Path('jobs')/self.job).as_posix()]=row['sha256']
            remote_path='A/Images/A.jpg';self.entry(repo,remote_path,row)
            p=str(self.config/rel)
            self.db.execute('INSERT INTO publications VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(self.job,style,repo,remote_path,p,row['sha256'],p,row['sha256'],row['git_blob'],'master','A','1','published','3'*40,self.now))
            self.db.execute('INSERT INTO readmes VALUES(?,?,?)',(self.job,repo,'disabled'))
        self.db.commit()
        manifest=dict(id=self.job,managed_by='kometa-people-v1',status='cleanup_eligible',cleanup_files=catalog)
        self.add_file('jobs/'+self.job+'/manifest.json',json.dumps(manifest).encode(),disposition='preserve',role='metadata_or_other',scope='job',job=self.job)
        row=self.add_file('people_dirs/bw/A/Images/Legacy.jpg',b'legacy artwork',scope='persistent_artwork',style='bw',reason='exact_published_copy',remote_path='A/Images/Legacy.jpg')
        self.entry(worker.REPOSITORIES['bw'],row['remote_path'],row)
        self.add_file('models/model.bin',b'protected-model',disposition='preserve',role='model',scope='protected')
        self.approval=dict(files=self.rows,font_replacement_proof={})
        self.remote=Remote(self.snapshot)
        self.jost=patch.object(worker,'jost_proof',return_value={});self.jost.start();self.addCleanup(self.jost.stop)

    def add_file(self,relative,data,**extra):
        p=self.config/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        h=local.inspect(p)
        row=dict(path=relative,bytes=h['bytes'],sha256=h['sha256'],git_blob=h['git_blob'],scope='job',job=None,
            role='generated_poster',style=None,reason='owned_successful_job_payload',disposition='candidate_after_job_retention_deadline')
        row.update(extra);self.rows.append(row);return row

    def entry(self,repo,path,row):
        self.snapshot[repo]['entries'][path]=dict(path=path,mode='100644',type='blob',sha=row['git_blob'],size=row['bytes'])

    def plan(self):return worker.build_plan(self.config,self.approval,self.remote,now=self.now)[0]

    def test_exact_publication_and_all_seven_success_receipts_are_required(self):
        report=self.plan();self.assertEqual(report['eligible_files'],8)
        self.assertEqual(len(report['snapshot_heads']),7)

    def test_dry_run_has_no_state_or_payload_side_effects(self):
        before={str(p):p.read_bytes() for p in self.config.rglob('*') if p.is_file()}
        self.plan()
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.config.rglob('*') if p.is_file()})
        self.assertFalse((self.config/'state/verified-retention').exists())
        alias=self.config/'..'/self.config.name/'forbidden-report.json'
        with patch.object(worker.sys,'stderr',io.StringIO()),self.assertRaises(SystemExit):
            worker.main(['--config',str(self.config),'--report',str(alias)])
        self.assertFalse(alias.exists())
        outside=self.root/'custom-root-report.json'
        with patch.dict(os.environ,{'PEOPLE_JOBS_DIR':str(self.root/'elsewhere')}),self.assertRaises(local.RetentionBlocked):
            worker.main(['--config',str(self.config),'--report',str(outside)])
        self.assertFalse(outside.exists())
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.config.rglob('*') if p.is_file()})

    def test_three_day_window_uses_publication_not_folder_age(self):
        self.db.execute('UPDATE jobs SET published=?',(self.now-2*86400,));self.db.commit()
        p=self.plan();self.assertEqual(p['eligible_files'],1)
        self.assertEqual(sum(r['reason']=='three_day_window_open' for r in p['skipped']),7)

    def test_exact_retention_boundary_and_longer_configured_retention(self):
        self.db.execute('UPDATE jobs SET published=?',(self.now-3*86400,));self.db.commit()
        self.assertEqual(self.plan()['eligible_files'],8)
        with patch.dict(os.environ,{'PEOPLE_BATCH_RETENTION_DAYS':'5'}):self.assertEqual(self.plan()['eligible_files'],1)

    def test_failed_incomplete_validation_and_no_work_are_never_age_expired(self):
        for status in ['failed','pending','processing','validation_only','no_work','complete']:
            with self.subTest(status=status):
                self.db.execute('UPDATE jobs SET status=?',(status,));self.db.commit()
                self.assertEqual(self.plan()['eligible_files'],1)

    def test_current_remote_missing_blob_wrong_mode_or_size_blocks(self):
        repo=worker.REPOSITORIES['bw'];path='A/Images/Legacy.jpg';old=deepcopy(self.remote.value[repo]['entries'][path])
        for field,value in [('sha','0'*40),('mode','120000'),('size',999)]:
            self.remote.value[repo]['entries'][path]=dict(old,**{field:value})
            with self.subTest(field=field),self.assertRaises(local.RetentionBlocked):self.plan()
        del self.remote.value[repo]['entries'][path]
        with self.assertRaises(local.RetentionBlocked):self.plan()

    def test_remote_failure_never_turns_into_offline_deletion(self):
        self.remote.fail=True
        with self.assertRaises(local.RetentionBlocked):self.plan()

    def test_mixed_local_bytes_unexpected_members_and_missing_files_stop(self):
        p=self.config/self.rows[0]['path'];original=p.read_bytes()
        p.write_bytes(b'unreviewed')
        with self.assertRaises(local.RetentionBlocked):self.plan()
        p.write_bytes(original);extra=p.parent/'unexpected.jpg';extra.write_bytes(b'x')
        with self.assertRaises(local.RetentionBlocked):self.plan()
        extra.unlink();p.unlink()
        with self.assertRaises(local.RetentionBlocked):self.plan()

    def test_incomplete_readme_publication_or_style_grant_blocks(self):
        for sql in ["UPDATE readmes SET status='pending'","UPDATE publications SET status='pending'","UPDATE publications SET commit_sha=''","UPDATE publications SET style='original' WHERE style='bw'"]:
            self.db.execute(sql)
            self.db.commit()
            with self.subTest(sql=sql),self.assertRaises(local.RetentionBlocked):self.plan()
            # Restore test-owned fixture rows through the same persistent file.
            if 'readmes' in sql:self.db.execute("UPDATE readmes SET status='disabled'")
            elif "status='pending'" in sql:self.db.execute("UPDATE publications SET status='published'")
            elif 'commit_sha' in sql:self.db.execute('UPDATE publications SET commit_sha=?',('3'*40,))
            else:self.db.execute('UPDATE publications SET style=? WHERE repo=?',('bw',worker.REPOSITORIES['bw']))
            self.db.commit()

    def test_catalog_and_publication_source_hashes_are_checked(self):
        self.db.execute("UPDATE publications SET source_hash='bad'");self.db.commit()
        with self.assertRaises(local.RetentionBlocked):self.plan()
        self.db.execute('UPDATE publications SET source_hash=published_hash')
        self.db.execute("UPDATE publications SET blob=? WHERE style='bw'",('f'*40,));self.db.commit()
        self.remote.value[worker.REPOSITORIES['bw']]['entries']['A/Images/A.jpg']['sha']='f'*40
        with self.assertRaisesRegex(local.RetentionBlocked,'Prepared publication blob differs'):
            self.plan()

    def test_path_escape_and_source_ownership_are_rejected(self):
        for value in ['../outside','/absolute','a\\b','C:/escape','a//b','a/./b']:
            with self.subTest(path=value),self.assertRaises(local.RetentionBlocked):local.member(self.config,value)
        self.db.execute("UPDATE publications SET source='C:/outside.jpg'");self.db.commit()
        with self.assertRaises(local.RetentionBlocked):self.plan()

    def test_active_and_pending_markers_block_cleanup(self):
        for rel in ['jobs/'+self.job+'/.active','jobs/'+self.job+'/.orch/poster.pending.json','.orch/run.lock']:
            p=self.config/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('1')
            with self.subTest(path=rel),self.assertRaises(local.RetentionBlocked):self.plan()
            p.unlink()

    def test_failed_operation_reference_protects_legacy_file(self):
        alias=self.config/'..'/self.config.name/self.rows[-2]['path']
        p=self.config/'jobs/failure/manifest.json';p.parent.mkdir();p.write_text(json.dumps({'source':str(alias)}))
        self.db.execute("INSERT INTO jobs VALUES('failure','failed',0,0,NULL,'')");self.db.commit()
        with self.assertRaises(local.RetentionBlocked):self.plan()

    def test_recovered_outputs_rollback_and_raw_sources_are_preserved(self):
        self.add_file(f'jobs/{self.job}/edge_chop_recovery/transactions/x/0.bin',b'backup',scope='job',job=self.job,role='rollback_artifact')
        self.add_file(f'jobs/{self.job}/input/tmdb/raw.jpg',b'unique raw',scope='job',job=self.job,role='downloaded_input_or_intermediate')
        relative='bw/A/Images/recovered.jpg'
        row=self.add_file(f'jobs/{self.job}/people_dirs/'+relative,b'accepted',scope='job',job=self.job)
        self.add_file(f'jobs/{self.job}/edge_chop_recovery/recovery-checkpoints.json',json.dumps({'records':{'A':{'outputs':{relative:row['sha256']}}}}).encode(),scope='job',job=self.job,disposition='preserve')
        p=self.plan();reasons={r['path']:r['reason'] for r in p['skipped']}
        self.assertEqual(sum(v=='protected_source_checkpoint_or_rollback' for v in reasons.values()),3)

    def test_processing_lock_and_cleaner_lock_exclude_concurrent_workers(self):
        lease=self.config/'state/orchestrator.lock';lease.write_text('999 @ processor')
        with self.assertRaises(local.RetentionBlocked):self.plan()
        with self.assertRaises(local.RetentionBlocked):
            with local.processing_exclusion(self.config,worker.APPROVAL):pass
        lease.unlink()
        with local.processing_exclusion(self.config,worker.APPROVAL):
            with self.assertRaises((ValueError,OSError)):
                with local.processing_exclusion(self.config,worker.APPROVAL):pass

    def test_apply_deletes_only_approved_images_and_keeps_model_and_metadata(self):
        expected=self.plan();result=worker.apply_plan(self.config,self.approval,self.remote,expected,{'head':'a'*40})
        self.assertEqual(len(result['deleted']),8)
        self.assertEqual(result['recovered_bytes'],expected['eligible_bytes'])
        self.assertTrue((self.config/'models/model.bin').is_file())
        self.assertTrue((self.config/'jobs'/self.job/'manifest.json').is_file())
        self.assertFalse((self.config/'state/orchestrator.lock').exists())
        self.assertFalse((self.config/'state/verified-retention/journal.db').exists())

    def test_interrupted_unlink_is_reconciled_without_deleting_twice(self):
        expected=self.plan();real=worker.unlink_verified
        def interrupted(root,row):real(root,row);raise OSError('simulated interruption after unlink')
        with patch.object(worker,'unlink_verified',side_effect=interrupted),self.assertRaises(OSError):
            worker.apply_plan(self.config,self.approval,self.remote,expected,{'head':'a'*40})
        next_plan=self.plan();self.assertEqual(next_plan['eligible_files'],7)
        result=worker.apply_plan(self.config,self.approval,self.remote,next_plan,{'head':'a'*40})
        self.assertEqual(len(result['deleted']),7)
        journal=local.journal_members(self.config/'state/verified-retention',worker.APPROVAL,self.config)
        self.assertEqual(sum(r['state']=='missing_after_intent' for r in journal.values()),1)

    def test_reappearing_receipted_file_is_unexpected_and_stops(self):
        expected=self.plan();worker.apply_plan(self.config,self.approval,self.remote,expected,{'head':'a'*40})
        (self.config/self.rows[0]['path']).write_bytes(b'image-original')
        with self.assertRaises(local.RetentionBlocked):self.plan()

    def test_changed_dry_run_digest_and_wrong_ci_refuse_any_unlink(self):
        p=self.plan();p['plan_digest']='bad'
        with self.assertRaises(local.RetentionBlocked):worker.apply_plan(self.config,self.approval,self.remote,p,{'head':'a'*40})
        with self.assertRaises(local.RetentionBlocked):worker.apply_plan(self.config,self.approval,self.remote,p,{'head':'b'*40})
        self.assertTrue((self.config/self.rows[0]['path']).exists())

    def test_remote_changes_during_cleanup_stop_remaining_files(self):
        p=self.plan();real=worker.unlink_verified
        def mutate(root,row):real(root,row);self.remote.fail=True
        with patch.object(worker,'unlink_verified',side_effect=mutate),self.assertRaises(local.RetentionBlocked):
            worker.apply_plan(self.config,self.approval,self.remote,p,{'head':'a'*40})
        self.assertTrue((self.config/'people_dirs/bw/A/Images/Legacy.jpg').exists())

    def test_database_reference_changes_during_cleanup_stop_remaining_files(self):
        p=self.plan();real=worker.unlink_verified
        def mutate(root,row):real(root,row);self.db.execute("UPDATE jobs SET status='failed'");self.db.commit()
        with patch.object(worker,'unlink_verified',side_effect=mutate),self.assertRaises(local.RetentionBlocked):
            worker.apply_plan(self.config,self.approval,self.remote,p,{'head':'a'*40})
        self.assertTrue((self.config/'people_dirs/bw/A/Images/Legacy.jpg').exists())

    def test_changed_identity_between_plan_and_unlink_is_blocked(self):
        r=self.plan()['eligible'][0];p=self.config/r['path'];p.write_bytes(b'changed')
        with self.assertRaises(local.RetentionBlocked):local.unlink_verified(self.config,r)

    def test_hardlinks_and_symlinks_are_not_adopted(self):
        p=self.config/self.rows[0]['path'];alias=self.root/'alias';os.link(p,alias)
        with self.assertRaises(local.RetentionBlocked):self.plan()
        alias.unlink()
        with patch.object(Path,'lstat',return_value=type('Info',(),{'st_mode':0o120777,'st_file_attributes':0})()):
            with self.assertRaises(ValueError):local.member(self.config,'people_dirs/x')

    def test_enrolled_workspace_cannot_run_legacy_recursive_cleanup(self):
        # Exercise the same normalization difference as Windows TEMP aliases.
        manager=Workspaces(self.config/'..'/self.config.name)
        self.addCleanup(manager.close)
        p=self.config/'state/verified-retention/enrollment.json';p.parent.mkdir();p.write_text('{}')
        manifest_path=self.config/'jobs'/self.job/'manifest.json'
        manifest=json.loads(manifest_path.read_text());manifest['created']=self.now-500000
        manifest_path.write_text(json.dumps(manifest))
        with patch.object(worker,'apply_plan',side_effect=AssertionError('Legacy artwork cleaner must remain separate')):
            results=manager.cleanup(dry_run=False,now=self.now)
        self.assertEqual(results,[(self.job,'cleaned')])
        self.assertFalse((self.config/'jobs'/self.job).exists())
        self.assertTrue((self.config/'people_dirs/bw/A/Images/Legacy.jpg').exists())
        self.assertEqual(p.read_text(),'{}')

    def test_routine_jobs_plan_uses_producer_catalog_without_audit_inventory(self):
        report,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
        self.assertEqual(report['eligible_files'],7)
        self.assertEqual(report['scope'],worker.MANAGED_SCOPE)
        self.assertNotIn('people_dirs/bw/A/Images/Legacy.jpg',[r['path'] for r in report['eligible']])
        self.assertGreater(report['jobs'][0]['total_bytes'],report['eligible_bytes'])
        self.assertEqual(report['storage']['retained_bytes'],report['storage']['logical_bytes']-report['eligible_bytes'])
        with patch.dict(os.environ,{'PEOPLE_JOBS_MAX_GIB':'0.00000001'}):
            warning,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
        self.assertTrue(warning['storage']['warnings'])

    def test_routine_missing_receipts_retains_job_without_recreating_state(self):
        self.db.close();p=self.config/'state/publication_state.db';p.unlink()
        report,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
        self.assertEqual(report['eligible_files'],0)
        self.assertIn('publication_evidence_missing',report['jobs'][0]['reason'])
        self.assertFalse(p.exists())

    def test_large_batch_proofs_are_linear_and_unpublished_catalog_members_stay(self):
        manifest_path=self.config/'jobs'/self.job/'manifest.json'
        manifest=json.loads(manifest_path.read_text())
        for person in range(1,20):
            for style,repo in worker.REPOSITORIES.items():
                remote_path=f'P{person}/Images/P{person}.jpg'
                rel=f'jobs/{self.job}/.publish/{self.job}/{style}/'+remote_path
                image=self.add_file(rel,f'{person}-{style}'.encode(),job=self.job)
                manifest['cleanup_files'][Path(rel).relative_to(Path('jobs')/self.job).as_posix()]=image['sha256']
                self.entry(repo,remote_path,image);p=str(self.config/rel)
                self.db.execute('INSERT INTO publications VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (self.job,style,repo,remote_path,p,image['sha256'],p,image['sha256'],image['git_blob'],
                     'master',f'P{person}',str(person+1),'published','3'*40,self.now))
        self.db.execute('UPDATE batches SET expected=140');self.db.commit()
        manifest_path.write_text(json.dumps(manifest))
        report,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
        self.assertEqual(report['eligible_files'],140)
        self.assertLess(len(json.dumps(report).encode()),1024*1024)
        for row in report['eligible']:
            self.assertEqual(len(row['proof']['receipts']),1)
            self.assertEqual(row['proof']['verified_batch_receipts'],140)
        # A producer catalog alone cannot authorize unpublished generated art.
        image=self.add_file(f'jobs/{self.job}/people_dirs/bw/Unpublished.jpg',b'unpublished')
        manifest['cleanup_files']['people_dirs/bw/Unpublished.jpg']=image['sha256']
        manifest_path.write_text(json.dumps(manifest))
        report,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
        self.assertEqual(report['eligible_files'],0)
        self.assertIn('no_corresponding_publication_receipt',report['jobs'][0]['reason'])

    def test_routine_failed_job_does_not_block_other_eligible_jobs(self):
        failed=self.config/'jobs/20261002T000000-abcdef123456';failed.mkdir()
        (failed/'manifest.json').write_text(json.dumps(dict(id=failed.name,managed_by='kometa-people-v1',status='failed')))
        (failed/'input.jpg').write_bytes(b'retry source')
        self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?)',(failed.name,'failed',0,0,None,'error'));self.db.commit()
        report,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
        self.assertEqual(report['eligible_files'],7)
        self.assertTrue((failed/'input.jpg').exists())
        self.assertIn('failed_incomplete_or_retryable',report['jobs'][1]['reason'])

    def test_routine_source_checkpoint_and_unknown_paths_are_preserved(self):
        self.add_file(f'jobs/{self.job}/input/raw.jpg',b'source',job=self.job)
        # Unknown image is not adopted just because the job was published.
        report,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
        self.assertEqual(report['eligible_files'],0)
        self.assertEqual(report['jobs'][0]['reason'],'changed_or_unowned_job_image')

    def test_routine_apply_reuses_locked_exact_deletion_receipts(self):
        expected,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
        result=worker.apply_plan(self.config,None,self.remote,expected,{'head':'a'*40})
        self.assertEqual(len(result['deleted']),7)
        self.assertEqual(result['approval'],worker.MANAGED_SCOPE)
        report,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
        self.assertEqual(report['eligible_files'],0)
        self.assertTrue((self.config/'models/model.bin').is_file())

    def test_ordinary_logs_rotation_excludes_decision_logs_and_histories(self):
        logs=self.config/'logs';logs.mkdir()
        for name in ['tmdb_people.log','sel_remove_bg.log','remove_bg_birefnet.log','attempted_candidates.csv','recovery-summary.json']:
            (logs/name).write_bytes(b'x'*100)
        for suffix in ['.1','.2','.3']:(logs/('tmdb_people.log'+suffix)).write_bytes(b'archive')
        with patch.object(worker,'LOG_BYTES',32):
            report=worker.ordinary_logs(self.config)
            self.assertEqual([r['path'] for r in report],['logs/tmdb_people.log'])
            changes=worker.rotate_ordinary_logs(self.config/'..'/self.config.name)
        self.assertEqual((logs/'tmdb_people.log').stat().st_size,0)
        self.assertEqual((logs/'tmdb_people.log.1').stat().st_size,32)
        self.assertEqual((logs/'sel_remove_bg.log').stat().st_size,100)
        self.assertEqual((logs/'remove_bg_birefnet.log').stat().st_size,100)
        self.assertEqual((logs/'attempted_candidates.csv').stat().st_size,100)
        self.assertEqual((logs/'recovery-summary.json').stat().st_size,100)
        self.assertEqual(sum(r['bytes'] for r in changes),68+7)

    def test_routine_interrupted_unlink_reconciles_intent_without_double_counting(self):
        expected,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
        real=worker.unlink_verified
        def interrupted(root,row):real(root,row);raise OSError('interrupted after unlink')
        with patch.object(worker,'unlink_verified',side_effect=interrupted),self.assertRaises(OSError):
            worker.apply_plan(self.config,None,self.remote,expected,{'head':'a'*40})
        plan,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
        self.assertEqual(plan['eligible_files'],6)
        result=worker.apply_plan(self.config,None,self.remote,plan,{'head':'a'*40})
        self.assertEqual(len(result['deleted']),6)
        journal=local.journal_members(self.config/'state/verified-retention',worker.MANAGED_SCOPE,self.config)
        self.assertEqual(sum(r['state']=='missing_after_intent' for r in journal.values()),1)

    def test_routine_reappearing_deleted_file_requires_review(self):
        expected,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
        saved=expected['eligible'][0];p=self.config/saved['path'];data=p.read_bytes()
        worker.apply_plan(self.config,None,self.remote,expected,{'head':'a'*40})
        p.write_bytes(data)
        plan,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
        self.assertEqual(plan['eligible_files'],0)
        self.assertIn('reappeared',plan['jobs'][0]['reason'])

    def test_ordinary_log_dry_report_is_read_only_and_failed_job_logs_untouched(self):
        p=self.config/'logs/tmdb_people.log';p.parent.mkdir();p.write_bytes(b'x'*100)
        q=self.config/'jobs'/self.job/'logs/tmdb_people.log';q.parent.mkdir();q.write_bytes(b'y'*100)
        with patch.object(worker,'LOG_BYTES',32):self.assertTrue(worker.ordinary_logs(self.config)[0]['over_limit'])
        self.assertEqual(p.read_bytes(),b'x'*100)
        self.assertEqual(q.read_bytes(),b'y'*100)

    def enroll(self,reviewed=True):
        directory=self.config/'state/verified-retention';directory.mkdir(exist_ok=True)
        local.atomic_json(directory/'enrollment.json',dict(unattended_reviewed=reviewed,
            head='a'*40,ci_receipt={'head':'a'*40}))
        return type('Manager',(),{'config':self.config})()

    def test_end_of_job_cleanup_reuses_verified_apply_and_same_pid_processing_lease(self):
        manager=self.enroll()
        lease=self.config/'state/orchestrator.lock';token=f'{os.getpid()} @ processor'
        lease.write_text(token,encoding='ascii')
        with patch.dict(os.environ,{'PEOPLE_AUTO_CLEANUP':'true'}):
            result=worker.maintenance_after_job(manager,completed=True,remote=self.remote)
        self.assertEqual(result['cleanup']['deleted_files'],7)
        self.assertGreater(result['cleanup']['recovered_bytes'],0)
        self.assertEqual(lease.read_text(encoding='ascii'),token)
        self.assertTrue((self.config/'models/model.bin').is_file())
        self.assertTrue((self.config/'jobs'/self.job/'manifest.json').is_file())

    def test_end_of_job_retains_new_success_until_three_days_and_rotates_only_ordinary_logs(self):
        manager=self.enroll()
        self.db.execute('UPDATE jobs SET published=?',(time.time(),));self.db.commit()
        logs=self.config/'logs';logs.mkdir()
        (logs/'tmdb_people.log').write_bytes(b'a'*100)
        (logs/'remove_bg_birefnet.log').write_bytes(b'b'*100)
        joblogs=self.config/'jobs'/self.job/'logs';joblogs.mkdir()
        (joblogs/'tmdb_people.log').write_bytes(b'c'*100)
        (joblogs/'remove_bg_birefnet.log').write_bytes(b'd'*100)
        with patch.dict(os.environ,{'PEOPLE_AUTO_CLEANUP':'true'}),patch.object(worker,'LOG_BYTES',32):
            result=worker.maintenance_after_job(manager,completed=True,remote=self.remote)
        self.assertEqual(result['cleanup']['deleted_files'],0)
        self.assertEqual(result['jobs'][0]['reason'],'three_day_window_open')
        self.assertEqual((logs/'remove_bg_birefnet.log').read_bytes(),b'b'*100)
        self.assertEqual((logs/'tmdb_people.log.1').read_bytes(),b'a'*32)
        self.assertEqual((joblogs/'tmdb_people.log.1').read_bytes(),b'c'*32)
        self.assertEqual((joblogs/'remove_bg_birefnet.log').read_bytes(),b'd'*100)

    def test_failed_job_exit_reports_growth_without_deleting_or_rotating_its_logs(self):
        manager=self.enroll()
        self.db.execute("UPDATE jobs SET status='failed',published=NULL");self.db.commit()
        log=self.config/'jobs'/self.job/'logs/tmdb_people.log'
        log.parent.mkdir();log.write_bytes(b'failed evidence'*50)
        with patch.object(worker,'apply_plan',side_effect=AssertionError('failed apply')):
            first=worker.maintenance_after_job(manager,completed=False,remote=self.remote)
            log.write_bytes(log.read_bytes()+b'growth')
            second=worker.maintenance_after_job(manager,completed=False,remote=self.remote)
        self.assertEqual(second['failed_jobs']['growth_bytes'],6)
        self.assertIn('failed_job_storage_grew',second['warnings'])
        self.assertEqual(second['failed_jobs']['jobs'][0]['id'],self.job)
        self.assertTrue(log.read_bytes().endswith(b'growth'))
        self.assertEqual(first['cleanup']['recovered_bytes'],0)

    def test_unreviewed_or_disabled_end_of_job_never_applies(self):
        manager=self.enroll(reviewed=False)
        with patch.object(worker,'apply_plan',side_effect=AssertionError('unapproved apply')):
            self.assertEqual(worker.maintenance_after_job(manager,completed=True,remote=self.remote)['cleanup']['status'],
                'unattended_cleanup_not_reviewed')
        self.enroll(reviewed=True)
        with patch.dict(os.environ,{'PEOPLE_AUTO_CLEANUP':'false'}),patch.object(worker,'apply_plan',side_effect=AssertionError('disabled apply')):
            self.assertEqual(worker.maintenance_after_job(manager,completed=True,remote=self.remote)['cleanup']['status'],
                'automatic_cleanup_disabled')

    def test_end_of_job_ci_or_remote_failure_preserves_publication_and_reports_blocker(self):
        manager=self.enroll()
        with patch.object(self.remote,'validate_ci',side_effect=local.RetentionBlocked('CI verification unavailable')),patch.object(worker.sys,'stderr',io.StringIO()):
            result=worker.maintenance_after_job(manager,completed=True,remote=self.remote)
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(self.db.execute('SELECT status FROM jobs').fetchone()[0],'cleanup_eligible')
        self.assertTrue((self.config/'state/verified-retention/maintenance-error.json').is_file())
        self.assertFalse((self.config/'state/verified-retention/deletions.json').exists())

    def test_deactivation_maintenance_requires_owned_lease_and_enrollment(self):
        from types import SimpleNamespace
        folder=self.config/'jobs'/self.job;lease=folder/'.active'
        manager=SimpleNamespace(config=self.config,jobs=(self.config/'jobs').resolve(),state=(self.config/'state').resolve(),path=lambda batch:folder,
            record=lambda batch:({'status':'cleanup_eligible'},{}))
        with patch.object(worker,'maintenance_after_job') as maintain:
            lease.write_text(str(os.getpid()),encoding='ascii')
            Workspaces.deactivate(manager,self.job);maintain.assert_not_called()
            self.enroll();lease.write_text(str(os.getpid()),encoding='ascii')
            # Startup owns job retention now. Releasing a job lease must not
            # invoke the legacy cleaner with a stale implementation CI receipt.
            Workspaces.deactivate(manager,self.job);maintain.assert_not_called()
            self.assertFalse(lease.exists())
            maintain.reset_mock();lease.write_text('-999',encoding='ascii')
            Workspaces.deactivate(manager,self.job);maintain.assert_not_called()
            manager.jobs=self.config/'custom-jobs';lease.write_text(str(os.getpid()),encoding='ascii')
            with patch('builtins.print'):
                Workspaces.deactivate(manager,self.job)
            maintain.assert_not_called()

    def test_storage_report_missing_evidence_is_read_only_and_exposes_blocked_bytes(self):
        self.db.close();p=self.config/'state/publication_state.db';p.unlink()
        plan,_=worker.build_jobs_plan(self.config,self.remote)
        value=worker.storage_report(self.config,plan)
        self.assertEqual(value['eligible_bytes'],0)
        self.assertEqual(value['blocked_job_bytes'],plan['storage']['logical_bytes'])
        self.assertEqual(value['folders']['models']['bytes'],len(b'protected-model'))
        self.assertFalse(p.exists())

    def failed_catalog(self):
        folder=self.config/'jobs'/self.job
        manifest=local.read_json(folder/'manifest.json')
        manifest.update(status='failed',updated=self.now-800000)
        local.atomic_json(folder/'manifest.json',manifest)
        (folder/'people_list.txt').write_text('1|A\n',encoding='utf8')
        self.db.execute("UPDATE jobs SET status='failed',published=NULL");self.db.commit()
        self.db.row_factory=sqlite3.Row
        receipts=[dict(r) for r in self.db.execute('SELECT * FROM publications')]
        generated=self.add_file('jobs/'+self.job+'/people_dirs/bw/A/Images/A.jpg',b'image-bw')
        survivor=self.add_file('jobs/'+self.job+'/posters/A.png',b'retry source')
        duplicate=self.add_file('jobs/'+self.job+'/Downloads/other/A.png',b'retry source')
        generated.update(identity=local.inspect(self.config/generated['path']),person='A',tmdb_id='1',
            reason='failed_generated_output_exactly_published_by_later_success')
        duplicate.update(identity=local.inspect(self.config/duplicate['path']),retained_survivor=survivor['path'],
            survivor_identity=local.inspect(self.config/survivor['path']),reason='exact_duplicate_with_pinned_retained_failed_job_survivor')
        candidates=[generated,duplicate];names={r['path'] for r in candidates}
        preserve=[dict(path=p.relative_to(self.config).as_posix(),identity=local.inspect(p))
            for p in folder.rglob('*') if p.is_file() and p.relative_to(self.config).as_posix() not in names]
        return dict(version=1,scope=worker.FAILED_SCOPE,root=str(local.canonical_root(self.config)),
            files=candidates,preserve=preserve,operations={self.job:dict(
                manifest_sha256=local.inspect(folder/'manifest.json')['sha256'],
                people=[dict(person='A',tmdb_id='1',published=self.now-400000,receipts=receipts)])})

    def apply_failed(self,plan,digest=None):
        return worker.apply_reviewed_failed(self.config,plan,digest or local.fingerprint(plan),self.remote,{'head':'a'*40})

    def test_failed_catalog_preflight_is_read_only_even_with_missing_central_state(self):
        plan=self.failed_catalog();self.db.close()
        (self.config/'state/publication_state.db').unlink();(self.config/'state').rmdir()
        before={p.relative_to(self.config).as_posix():local.inspect(p) for p in self.config.rglob('*') if p.is_file()}
        with patch.object(self.remote,'validate_ci',side_effect=AssertionError('No deletion CI grant required for read-only review')):
            report=worker.apply_reviewed_failed(self.config,plan,local.fingerprint(plan),self.remote,{},dry_run=True)
        self.assertEqual(report['eligible_files'],2)
        self.assertFalse(report['deletion_authorized_by_dry_run'])
        self.assertFalse((self.config/'state').exists())
        self.assertEqual(before,{p.relative_to(self.config).as_posix():local.inspect(p) for p in self.config.rglob('*') if p.is_file()})

    def test_reviewed_failed_compaction_preserves_unique_sources_metadata_and_stops_resume(self):
        plan=self.failed_catalog();result=self.apply_failed(plan)
        self.assertEqual(len(result['deleted']),2)
        self.assertEqual(result['recovered_bytes'],len(b'image-bw')+len(b'retry source'))
        for row in plan['preserve']:self.assertEqual(local.inspect(self.config/row['path']),row['identity'])
        manager=object.__new__(Workspaces);manager.jobs=self.config/'jobs'
        self.assertTrue(manager.retired(self.job))
        with self.assertRaisesRegex(ValueError,'retired'):manager.select(batch=self.job)

    def test_failed_compaction_requires_exact_approval_current_remote_and_complete_identity_cohort(self):
        plan=self.failed_catalog()
        with self.assertRaises(local.RetentionBlocked):self.apply_failed(plan,'0'*64)
        for mutate in [lambda p:p['operations'][self.job]['people'][0]['receipts'].pop(),
                       lambda p:p['operations'][self.job]['people'][0].update(tmdb_id='99'),
                       lambda p:p['operations'][self.job]['people'][0].update(published=0),
                       lambda p:p['files'][1].update(path='jobs/'+self.job+'/unknown/A.png'),
                       lambda p:p['files'][1].update(retained_survivor='jobs/20261002T000000-aaaaaaaaaaaa/A.png')]:
            bad=deepcopy(plan);mutate(bad)
            with self.assertRaises(local.RetentionBlocked):self.apply_failed(bad)
        self.remote.fail=True
        with self.assertRaises(local.RetentionBlocked):self.apply_failed(plan)
        self.assertFalse((self.config/'jobs'/self.job/'retention-retired.json').exists())

    def test_failed_compaction_never_discards_active_work_or_changed_survivors(self):
        plan=self.failed_catalog();folder=self.config/'jobs'/self.job
        (folder/'.active').write_text(str(os.getpid()),encoding='ascii')
        with self.assertRaises(local.RetentionBlocked):self.apply_failed(plan)
        (folder/'.active').unlink()
        (self.config/plan['files'][1]['retained_survivor']).write_bytes(b'changed')
        with self.assertRaises(local.RetentionBlocked):self.apply_failed(plan)
        self.assertTrue(all((self.config/r['path']).exists() for r in plan['files']))

    def test_failed_compaction_preserves_checkpoint_outputs_and_rejects_disposable_survivor(self):
        plan=self.failed_catalog();bad=deepcopy(plan)
        bad['files'][1]['retained_survivor']=bad['files'][0]['path']
        with self.assertRaises(local.RetentionBlocked):self.apply_failed(bad)
        checkpoint=self.config/'jobs'/self.job/'edge_chop_recovery/recovery-checkpoints.json'
        local.atomic_json(checkpoint,dict(records={'A':dict(outputs={'bw/A/Images/A.jpg':{}})}))
        with self.assertRaisesRegex(local.RetentionBlocked,'referenced'):self.apply_failed(plan)
        self.assertTrue((self.config/plan['files'][0]['path']).is_file())

    def test_failed_compaction_reconciles_interrupted_unlink_without_double_counting(self):
        plan=self.failed_catalog();real=worker.unlink_verified
        def interrupted(root,row):real(root,row);raise OSError('interrupted failed cleanup')
        with patch.object(worker,'unlink_verified',side_effect=interrupted),self.assertRaises(OSError):self.apply_failed(plan)
        result=self.apply_failed(plan)
        self.assertEqual(len(result['deleted']),1)
        again=self.apply_failed(plan);self.assertEqual(again['recovered_bytes'],0)
        receipts=local.journal_members(self.config/'state/verified-retention',worker.FAILED_SCOPE,self.config)
        self.assertEqual(sum(r['state']=='missing_after_intent' for r in receipts.values()),1)

    def test_failed_compaction_respects_explicit_deferral_and_global_processing_lock(self):
        plan=self.failed_catalog()
        for row in plan['files']:row['not_before']=self.now+86400
        result=self.apply_failed(plan)
        self.assertEqual(result['recovered_bytes'],0);self.assertEqual(len(result['waiting']),2)
        lease=self.config/'state/orchestrator.lock';lease.write_text(f'{os.getpid()} @ other',encoding='ascii')
        with self.assertRaises(local.RetentionBlocked):self.apply_failed(plan)

    def test_end_of_job_runs_only_the_separately_enrolled_failed_approval(self):
        plan=self.failed_catalog();manager=self.enroll();directory=self.config/'state/verified-retention'
        marker=local.read_json(directory/'enrollment.json');marker['failed_approval_sha256']=local.fingerprint(plan)
        local.atomic_json(directory/'enrollment.json',marker);local.atomic_json(directory/'failed-approval.json',plan)
        result=worker.maintenance_after_job(manager,completed=True,remote=self.remote)
        self.assertEqual(len(result['cleanup']['failed']['deleted']),2)
        self.assertGreater(result['failed_jobs']['retired_bytes'],0)
        self.assertEqual(local.read_json(directory/'enrollment.json')['failed_approval_sha256'],local.fingerprint(plan))
        again=worker.maintenance_after_job(manager,completed=True,remote=self.remote)
        self.assertEqual(again['cleanup']['failed']['recovered_bytes'],0)

    def test_approval_inventory_tamper_and_unknown_scope_fail(self):
        value={'files':[]};value['sha256']=local.fingerprint(value)
        p=self.root/'plan.json';p.write_text(json.dumps(value))
        with self.assertRaises(local.RetentionBlocked):worker.approved_plan(p)

    def test_jost_requires_exact_authoritative_receipt_for_approved_successor(self):
        row=self.add_file('people_dirs/diiivoy/A/Images/Old.jpg',b'old-font',scope='persistent_artwork',reason='explicit_expected_font_supersession',style='diiivoy',
            replacement=dict(repo=worker.REPOSITORIES['diiivoy'],path='A/Images/New.jpg',blob='4'*40,sha256='5'*64,commit='6'*40))
        self.remote.value[worker.REPOSITORIES['diiivoy']]['entries']['A/Images/New.jpg']=dict(mode='100644',type='blob',sha='4'*40)
        with self.assertRaises(local.RetentionBlocked):self.plan()
        key=tuple(row['replacement'][k] for k in ('repo','path','blob','sha256','commit'))
        with patch.object(worker,'jost_proof',return_value={key:{}}):
            self.assertEqual(self.plan()['eligible_files'],9)

    def test_real_jost_manifest_font_review_and_database_integrity(self):
        self.jost.stop()
        root=self.config/'migrations/jost';(root/'jobs/run').mkdir(parents=True);(root/'state').mkdir()
        manifest={'id':'run','font_hash':worker.FONT}
        path=root/'jobs/run/manifest.json';path.write_text(json.dumps(manifest))
        digest=hashlib.sha256(json.dumps(manifest,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        with closing(sqlite3.connect(root/'state/publication_state.db')) as db:
            db.executescript('CREATE TABLE jost_runs(id TEXT,manifest_hash TEXT); CREATE TABLE publications(status TEXT,commit_sha TEXT,branch TEXT,repo TEXT,path TEXT,blob TEXT,published_hash TEXT);')
            db.execute('INSERT INTO jost_runs VALUES(?,?)',('run',digest))
            db.commit()
        review=root/'reports/sample/review.json';review.parent.mkdir(parents=True);review.write_bytes(b'{"fixture":"approved"}')
        review_hash=hashlib.sha256(review.read_bytes()).hexdigest()
        (root/'state/rollout.json').write_text(json.dumps(dict(approved_sample='sample',review_sha256=review_hash)))
        approval={'font_replacement_proof':dict(approved_font_sha256=worker.FONT,saved_visual_review_sha256=review_hash,
            manifests=[dict(manifest='migrations/jost/jobs/run/manifest.json')])}
        with patch.object(worker,'REVIEW',review_hash):
            self.assertEqual(worker.jost_proof(self.config,approval,self.snapshot),{})
            path.write_text(json.dumps(dict(manifest,font_hash='unapproved')))
            with self.assertRaises(local.RetentionBlocked):worker.jost_proof(self.config,approval,self.snapshot)
            path.write_text(json.dumps(dict(manifest,extra='manifest drift')))
            with self.assertRaises(local.RetentionBlocked):worker.jost_proof(self.config,approval,self.snapshot)
            path.write_text(json.dumps(manifest));review.write_bytes(b'changed')
            with self.assertRaises(local.RetentionBlocked):worker.jost_proof(self.config,approval,self.snapshot)

    def test_missing_authoritative_state_blocks_without_recreating_database(self):
        self.db.close()
        path=self.config/'state/publication_state.db';path.unlink()
        with self.assertRaises(local.RetentionBlocked):self.plan()
        self.assertFalse(path.exists())

    def historical_evidence(self):
        self.db.row_factory=sqlite3.Row
        archived={name:[dict(r) for r in self.db.execute('SELECT * FROM '+name)]
                  for name in ('jobs','batches','publications','readmes')}
        rel='jobs/'+self.job+'/manifest.json'
        value=dict(read_only=True,source_head='ded9f33759f9fe3ed4ddf5f315dff01b163594ad',
                   ledger=archived,files={rel:local.inspect(self.config/rel)})
        path=self.root/'sealed-history.json';local.atomic_json(path,value)
        digest=local.inspect(path)['sha256']
        marker=dict(historical_evidence=dict(path=str(path),sha256=digest))
        local.atomic_json(self.config/'state/verified-retention/enrollment.json',marker)
        for name in archived:self.db.execute('DELETE FROM '+name)
        self.db.commit()
        return path,digest,value

    def test_sealed_historical_receipts_enable_only_verified_expired_payloads_without_database_writes(self):
        path,digest,value=self.historical_evidence()
        before=(self.config/'state/publication_state.db').read_bytes()
        with patch.object(worker,'HISTORICAL_EVIDENCE',digest):
            plan,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
        self.assertEqual(plan['eligible_files'],7)
        self.assertEqual(plan['eligible_bytes'],sum(r['bytes'] for r in plan['eligible']))
        self.assertEqual(self.db.execute('SELECT count(*) FROM jobs').fetchone()[0],0)
        self.assertEqual(before,(self.config/'state/publication_state.db').read_bytes())

    def test_historical_evidence_tampering_and_changed_manifests_fail_closed(self):
        path,digest,value=self.historical_evidence()
        with patch.object(worker,'HISTORICAL_EVIDENCE',digest):
            path.write_bytes(path.read_bytes()+b' ')
            plan,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
            self.assertEqual(plan['eligible_files'],0)
            local.atomic_json(path,value)
            manifest=self.config/'jobs'/self.job/'manifest.json'
            manifest.write_bytes(manifest.read_bytes()+b' ')
            plan,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
            self.assertEqual(plan['eligible_files'],0)

    def test_historical_receipts_respect_retention_and_current_failed_state(self):
        self.db.execute('UPDATE jobs SET published=?',(self.now-2*86400,));self.db.commit()
        path,digest,value=self.historical_evidence()
        with patch.object(worker,'HISTORICAL_EVIDENCE',digest):
            plan,_=worker.build_jobs_plan(self.config,self.remote,now=self.now)
            self.assertEqual(plan['eligible_files'],0)
            self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?)',(self.job,'failed',0,0,None,''));self.db.commit()
            self.assertEqual(worker.ledger(self.config)['jobs'][self.job]['status'],'failed')


class PeopleRetentionRemoteTests(unittest.TestCase):
    def ci_fixture(self):
        client=object.__new__(network.ReadOnlyGitHub)
        runs={i:(name,count) for i,(name,count) in enumerate(network.WORKFLOWS.items(),1)}
        def get(repo,path):
            ident=int(path.split('/')[3].split('?')[0]);name,count=runs[ident]
            if '/jobs?' in path:return dict(total_count=count,jobs=[dict(id=ident*100+j,status='completed',conclusion='success') for j in range(count)])
            return dict(name=name,head_sha='a'*40,status='completed',conclusion='success',event='pull_request')
        client.get=get
        return client,dict(head='a'*40,run_ids=list(runs))

    def merged_git(self, *, changed_tree=False, wrong_parent=False, dirty=False):
        def output(args,**kwargs):
            if args[1]=='rev-list':return 'b'*40+' '+'c'*40+' '+('d' if wrong_parent else 'a')*40
            if args[1]=='status':
                self.assertIn('--ignore-submodules=all',args)
                return b' M create_people_posters/people_verified_cleanup.py' if dirty else b''
            if args[2]=='HEAD':return 'b'*40+'\n'
            return 'e'*40+'\n'+('f' if changed_tree else 'e')*40+'\n'
        return output

    def test_ci_accepts_only_identical_two_parent_merge_of_tested_head(self):
        client,receipt=self.ci_fixture()
        log=type('R',(),dict(returncode=0,stdout='(test_people_retention.X.test_ok) ... ok'))()
        with patch.object(network.subprocess,'check_output',side_effect=self.merged_git()),patch('ci.people_retention_maintenance.verify_checkout'),patch('ci.people_retention_maintenance.test_ids',return_value=['test_people_retention.X.test_ok']),patch.object(network.subprocess,'run',return_value=log):
            result=client.validate_ci(receipt,Path.cwd())
            self.assertEqual(result['head'],'a'*40)
            self.assertEqual(result['implementation_head'],'b'*40)
            self.assertEqual(len(result['workflows']),5)
        for options in [dict(changed_tree=True),dict(wrong_parent=True),dict(dirty=True)]:
            with self.subTest(options=options),patch.object(network.subprocess,'check_output',side_effect=self.merged_git(**options)),self.assertRaises(local.RetentionBlocked):
                client.validate_ci(receipt,Path.cwd())

    def test_merged_checkout_still_rejects_skipped_or_wrong_head_ci(self):
        client,receipt=self.ci_fixture();original=client.get
        for kind in ['head','job']:
            def changed(repo,path):
                value=original(repo,path)
                if kind=='head' and '/jobs?' not in path:value['head_sha']='b'*40
                if kind=='job' and '/jobs?' in path:value['jobs'][0]['conclusion']='skipped'
                return value
            client.get=changed
            with self.subTest(kind=kind),patch.object(network.subprocess,'check_output',side_effect=self.merged_git()),patch('ci.people_retention_maintenance.verify_checkout'),self.assertRaises(local.RetentionBlocked):
                client.validate_ci(receipt,Path.cwd())

    def test_recursive_transport_failure_uses_complete_inventory_fallback_only(self):
        client=object.__new__(network.ReadOnlyGitHub);client.session=object()
        repo=next(iter(worker.REPOSITORIES.values()));route='/git/trees/'+'a'*40+'?recursive=1'
        for status in [0,500,502,503,504]:
            with self.subTest(status=status),patch.object(network,'get_json',side_effect=network.GitHubError('transport failed',status)),self.assertRaises(network.GitHubError):client.get(repo,route)
        for status in [401,403,404]:
            with self.subTest(status=status),patch.object(network,'get_json',side_effect=network.GitHubError('access denied',status)),self.assertRaises(local.RetentionBlocked):client.get(repo,route)
        with patch.object(network,'get_json',side_effect=network.GitHubError('transport failed',0)),self.assertRaises(local.RetentionBlocked):client.get(repo,route.replace('?recursive=1',''))

    def test_get_only_transport_rejects_unapproved_repository_and_path(self):
        with patch.object(network,'auth_token',return_value='test-only-token'):
            client=network.ReadOnlyGitHub()
        for repo,path in [('attacker/repo','/git/trees/x'),(network.SOURCE_REPO,'/../tokens'),(network.SOURCE_REPO,'https://invalid')]:
            with self.subTest(repo=repo,path=path),self.assertRaises(local.RetentionBlocked):client.get(repo,path)

    def test_ci_requires_exact_checkout_all_five_runs_and_no_skipped_job(self):
        client=object.__new__(network.ReadOnlyGitHub)
        runs={i:(name,count) for i,(name,count) in enumerate(network.WORKFLOWS.items(),1)}
        def get(repo,path):
            ident=int(path.split('/')[3].split('?')[0]);name,count=runs[ident]
            if '/jobs?' in path:return dict(total_count=count,jobs=[dict(id=ident*100+j,status='completed',conclusion='success') for j in range(count)])
            return dict(name=name,head_sha='a'*40,status='completed',conclusion='success',event='pull_request')
        client.get=get
        with patch.object(network.subprocess,'check_output',side_effect=['a'*40+'\n',b'']),patch('ci.people_retention_maintenance.verify_checkout'),patch('ci.people_retention_maintenance.test_ids',return_value=['test_people_retention.X.test_ok']),patch.object(network.subprocess,'run',return_value=type('R',(),{'returncode':0,'stdout':'(test_people_retention.X.test_ok) ... ok'})()):
            self.assertEqual(len(client.validate_ci({'head':'a'*40,'run_ids':list(runs)},Path.cwd())['workflows']),5)
        with patch.object(network.subprocess,'check_output',side_effect=['a'*40+'\n',b'']),patch('ci.people_retention_maintenance.verify_checkout'):
            with self.assertRaises(local.RetentionBlocked):client.validate_ci({'head':'b'*40,'run_ids':list(runs)},Path.cwd())


if __name__=='__main__':unittest.main()
