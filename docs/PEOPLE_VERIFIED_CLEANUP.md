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

Optional --approval PLAN.json selects the fixed original legacy-adoption inventory. That mode never expands to unrelated files. It is unnecessary for ordinary managed-job retention.

Ordinary log maintenance is a separate --apply-logs invocation with --ci-receipt. It never rotates sel_remove_bg.log, remove_bg_birefnet.log, audit/scan/prep/sync decision logs, operational CSV sets or checkpoint/receipt JSON. Every caller must hold the same processing exclusion; no rotation during a running stage. Root logs were manually removed by the user in this session, so there is currently no root log payload to rotate.

## Routine launch and scheduling

An enrollment record routes Workspaces.cleanup through this same managed-job planner, replacing the broad recursive pass for that enrolled checkout. Automatic deletion remains disabled unless unattended_reviewed is explicitly set after review of the schedule/locking/CI evidence. No production setting or scheduled task is changed by this PR. Before review, launch cleanup reports eligibility and keeps data; manual apply uses exactly the same predicates.

A Windows task can later run the independent command without starting an orchestrator batch. Use03:30 America/Toronto, a fixed reviewed checkout and execution account, single-instance/IgnoreNew behavior and a unique report path. Start report-only; approve unattended deletion separately. Keep the existing20GiB job budget and disk-space guard. Read-only reports expose accumulating blocked jobs, so they cannot silently disappear from the retention picture.

## Current manual cleanup

The user confirmed manually clearing the old config folders. The remaining jobs/models/vendor/.env are not adopted as disposable based on that action. The source-based strategy is independent of the deleted legacy artwork/audit inventory. Old jobs without their removed central receipts remain protected; newly produced jobs will use their own normal publication ledger and cleanup catalog. Five older jobs already contain only compact logs/manifests. The other three successful payloads were not overdue at the audit snapshot.

The original eight PR46 files,190protected source inventory,299adoption inventory,2927historical files, rendering and publication behavior remain unchanged. Only the exact Workspaces adapter and listed additions are admitted by a new fail-closed CI binding. New unit controls cover source-derived routine cleanup, missing evidence, per-job isolation, three-day boundaries, seven-style/current-remote verification, source/checkpoint/rollback preservation, locks, interruptions, log exclusions, exact scope and historical pin preservation.
