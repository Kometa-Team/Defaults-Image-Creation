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
        with patch.object(worker,'ReadOnlyGitHub',return_value=self.remote):
            results=manager.cleanup(dry_run=False,now=self.now)
        self.assertIn('automatic deletion awaiting review',results[0][1])
        self.assertTrue((self.config/self.rows[0]['path']).exists())

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
            changes=worker.rotate_ordinary_logs(self.config)
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


class PeopleRetentionRemoteTests(unittest.TestCase):
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
