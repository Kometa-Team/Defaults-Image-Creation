# Practical People cleanup

The default command derives retention from the paths and manifests produced by the current code. It does not need either historical audit. It reuses Workspaces, PublicationState, the shared orchestrator lease and PR46 cleanup lease; there is no new database, service or job manager.

| Producer-owned data | Rule |
| --- | --- |
| jobs/ID/.publish/ID/STYLE and jobs/ID/people_dirs/generated-style | Remove only after the existing successful publication timestamp is at least3days old, complete seven-style receipts match current GitHub, the manifest catalog hashes match, and no active/recovery reference requires the image |
| jobs/ID/input, original, .history, edge_chop_recovery, transaction binaries | Preserve original/retry/checkpoint/rollback data; no blanket age expiry |
| Failed, incomplete, active, validation-only or unregistered jobs | Preserve; report the specific blocker without disabling other eligible jobs |
| state SQLite, manifests, checkpoints, attempt/exhaustion sets | Preserve durable operational data; do not treat them as verbose logs |
| models and vendor | Keep reusable caches and dependencies |
| Persistent legacy artwork | No broad directory pruning; optional original approved inventory mode remains separate |
| Ordinary persistent text logs | Explicit whitelist,5MiB tail and3archives during locked maintenance; decision logs/CSV/JSON and existing failed-job logs excluded |
| Historical comparisons, migrations, validations, sandboxes | Outside routine pruning; no automatic deletion |

## Independent report / cleanup

From this implementation checkout:

```powershell
python -B -m create_people_posters.people_verified_cleanup --config C:/Users/bullmoose20/Defaults-Image-Creation/create_people_posters/config --report C:/Users/bullmoose20/Defaults-Image-Creation/config/people-retention-implementation/NEW-report.json
```

A report is read-only, including when state is absent. It does not reconstruct deleted publication records. Missing evidence blocks that job. It reports eligible bytes, reasons, publication deadlines and ordinary-log limits without launching a batch.

Apply adds --apply-plan NEW-report.json and --ci-receipt RECEIPT.json, with a NEW output path. The receipt binds the current implementation HEAD and all five hosted workflow run IDs. All71 mandatory jobs must succeed, every new retention control ID must execute on Windows and Linux, and the unchanged People pytest namespace retains its existing skip counts. The worker rebuilds the same plan under shared locks, requires an identical digest, rechecks current GitHub heads and local identity, and records JSON deletion intent before each unlink. Interrupted work reconciles without double deletion or inventing reclaimed bytes.

The normal local orchestrator also accepts the exact two-parent merge of that tested HEAD when its complete Git file tree is identical to the tested commit. CI remains bound to the original tested SHA; receipts record both SHAs. A different tree, another parent, a regular tracked source edit, or a missing/skipped CI control still blocks deletion. Legacy external Git submodule workspaces are ignored by the source dirty check; they are outside People processing and cleanup scope.

For the original audited jobs whose central database was removed, enrollment may explicitly reference the sealed original read-only audit export. Its exact SHA256 is pinned in the cleanup implementation. Only missing successful-job records with unchanged original manifests can use those existing receipts in memory. The worker still checks the original publication date, every current remote receipt, the seven-style cohort, exact cleanup catalog, local contents and current recovery references. Existing operational records always take priority. No database or historical manifest is reconstructed or refreshed.

Optional --approval PLAN.json selects the fixed original legacy-adoption inventory. That mode never expands to unrelated files. It is unnecessary for ordinary managed-job retention.

Ordinary log maintenance is a separate --apply-logs invocation with --ci-receipt. It never rotates sel_remove_bg.log, remove_bg_birefnet.log, audit/scan/prep/sync decision logs, operational CSV sets or checkpoint/receipt JSON. Every caller must hold the same processing exclusion; no rotation during a running stage. Root logs were manually removed by the user in this session, so there is currently no root log payload to rotate.

## Routine launch and job completion

An enrollment record routes Workspaces.cleanup through this same managed-job planner, replacing the broad recursive pass for that enrolled checkout. Automatic deletion remains disabled unless unattended_reviewed is explicitly set after review of the schedule/locking/CI evidence. No production setting or scheduled task is changed by this PR. Before review, launch cleanup reports eligibility and keeps data; manual apply uses exactly the same predicates.

After an enrolled managed job releases its own active marker, Workspaces runs maintenance while the orchestrator still holds its root processing lease. Successful or no-work exits use the existing verified apply, followed by the existing ordinary-log rotation, only when PEOPLE_AUTO_CLEANUP and the reviewed enrollment permit deletion. Failed and recovery-pending exits report storage and growth while retaining all payloads and logs. Maintenance failures preserve publication status and produce a bounded maintenance-error.json report.

The same ordinary-log whitelist and5MiB/3archive bounds apply to inactive, owned, successfully published/completed job logs during completion maintenance. Failed, retired-failed, incomplete and active job logs remain untouched. Decision logs and JSON/CSV evidence are excluded in every directory.

No Windows scheduled task or service is installed. This completion trigger replaces the previously proposed timer at the user's request. The just-finished successful job retains its full three-day window; older eligible payloads are compacted. With no subsequent job, expiry alone does not run cleanup. Independent manual cleanup remains available.

The latest bounded summary is state/verified-retention/storage-report.json: config folder sizes and file counts, eligible bytes, retained job bytes and reasons, failed-job totals and growth, ordinary-log limits, warnings, and actual cleanup results. Add --storage-report to the independent read-only command for the same summary without changing production state. Keep the existing20GiB job budget and disk-space guard.

Failed status is not an age-based deletion grant. Completion maintenance highlights retained failed payloads and accumulating bytes for review. A later success must be matched by person/TMDb identity and all seven current remote publication receipts. Compaction of an older failed job also requires an exact approved candidate list, a preserved survivor/source and recovery-reference check, and retiring that operation from retries before removing required paths. The five historical failed jobs are not silently adopted or deleted by this hook. Their removed central publication ledger is not reconstructed from status flags.

Separately approved failed compaction uses --apply-failed-plan FILE --failed-approval-sha256 DIGEST --ci-receipt RECEIPT with a new --report output. The exact catalog contains original manifest hashes, every requested person/TMDb identity, complete later seven-style receipts, exact deletion identities, pinned duplicate survivors, and all preserved input/metadata hashes. It admits only exact published generated copies or duplicates with an independently retained identical survivor. The worker rejects active operations, changed evidence, incomplete identities/cohorts, checkpoint/transaction references, missing or reappearing files, disposable survivors and unknown paths. It uses the same processing and cleanup locks, pinned unlink and durable deletion journal as successful-job cleanup. A retention-retired.json marker prevents both explicit and implicit resumption of the superseded failed operation; original manifests, sources and recovery evidence remain available. Interrupted unlink is reconciled without double-counting recovery.

Before approval, --review-failed-plan FILE --failed-approval-sha256 DIGEST --report NEWFILE runs the same file, survivor, receipt and reference preflight read-only. It needs no deletion CI grant and creates no production state, lock, retirement marker or deletion journal. Apply repeats every check under shared locks and additionally requires exact-head hosted CI; a dry run never enables deletion.

To permit this exact approved catalog during subsequent successful job completions, retain it at state/verified-retention/failed-approval.json and bind its reviewed digest as failed_approval_sha256 in the same reviewed enrollment. No digest means no failed-payload deletion. New failed jobs require a new exact review; an existing approval cannot expand to them. Optional per-file not_before deferrals remain enforced. This separate approval does not change the three-day rule for successful jobs. A sealed, explicitly reviewed publication-receipt export can supply historical proof when the user has removed its original database; the worker checks those receipts against current GitHub and never recreates the database.

## Current manual cleanup

The user confirmed manually clearing the old config folders. The remaining jobs/models/vendor/.env are not adopted as disposable based on that action. The source-based strategy is independent of the deleted legacy artwork/audit inventory. Old jobs without their removed central receipts remain protected; newly produced jobs will use their own normal publication ledger and cleanup catalog. Five older jobs already contain only compact logs/manifests. The other three successful payloads were not overdue at the audit snapshot.

The original eight PR46 files,190protected source inventory,299adoption inventory,2927historical files, rendering and publication behavior remain unchanged. Only the exact Workspaces adapter and listed additions are admitted by a new fail-closed CI binding. New unit controls cover source-derived routine cleanup, missing evidence, per-job isolation, three-day boundaries, seven-style/current-remote verification, source/checkpoint/rollback preservation, locks, interruptions, log exclusions, exact scope and historical pin preservation.
