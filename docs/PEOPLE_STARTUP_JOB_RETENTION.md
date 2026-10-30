# People Posters startup job retention

The startup hook now expires whole owned terminal job directories, including
temporary payloads, logs, manifests and empty directories. Durable publication
receipts remain in state. Deletion intents retain the original job manifest,
lifecycle row and exact file identities outside the expiring directory.

## Policy

| Lifecycle | Clock and default | Expiry |
| --- | --- | --- |
| `published`, `cleanup_eligible`, `complete` | `PEOPLE_BATCH_RETENTION_DAYS=3`, from publication | Require fulfilled image receipts, consistent lifecycle and unchanged remaining catalogued images. |
| `failed` | `PEOPLE_FAILED_BATCH_RETENTION_DAYS=14`, from last lifecycle update | Terminal standalone failures expire, including unpublished temporary inputs. Partial remote publication, recovery leases and rollback transactions override expiry. |
| `validation_only`, `no_work` | `PEOPLE_VALIDATION_BATCH_RETENTION_DAYS`, defaults to the success retention (3) | Terminal temporary work expires without requiring publication. |
| Active or selected resume | No age-based grant | Retain. Both explicit and automatic resume acquire the job lease before cleanup. |
| Pending, processing, generated, validated, recovery pending, partially published | No terminal completion | Retain for recovery. |
| Recovery/rollback, external references, models/vendor/config/Git material, uncertain ownership | Independent protection | Retain with a specific blocker, regardless of terminal status. |

The exact threshold is inclusive. Filesystem creation/modification times never
reset the lifecycle clock. Negative, non-finite and malformed settings fail
closed. Selecting an old failed job for resumption protects it; launching a new
batch allows unrelated expired terminal failures to retire.

Cleanup runs once at ordinary orchestrator startup, under the existing shared
processing lease, before admitting a new batch against the storage budget.
`--dry-run`, `--list` and `PEOPLE_AUTO_CLEANUP=false` retain their existing
non-deletion behavior. No scheduler is introduced. Releasing a job lease no
longer invokes the legacy exact-artwork maintenance worker.

## Growth monitoring and enforced admission

Preservation exceptions are monitored, not silently exempt from capacity limits.
Each startup, processing-step admission and owned job exit refreshes one
`state/job-retention/storage-report.json` with jobs/state bytes, growth since
the previous check, per-job retained bytes/reasons, review deadlines, free disk
space and admission blockers. Startup and exit print totals; warnings appear
at 80% of the configured storage limit. Reports overwrite the same file rather
than accumulating per launch.

`PEOPLE_JOBS_MAX_GIB=20` now covers jobs **and state**, including receipt archives.
It must be finite and positive; zero, negative and NaN values cannot disable the
guard. At the limit, with insufficient free space, or if usage cannot be measured
safely, new batches and subsequent processing steps stop. This is an admission
limit, not an OS disk quota: an already-running child can exceed it before its
next stage/exit check. There is no background monitor when the orchestrator is
not running, and no scheduler has been added.

`PEOPLE_RECOVERY_REVIEW_DAYS=14` gives unresolved retained jobs a review deadline.
An overdue exception blocks **new batches**, while existing recovery can still
resume below the storage limit. A retry does not silently extend the previously
recorded deadline. This forces a visible decision to finish recovery or verify
that retained material can be retired; it never deletes rollback evidence to
make room. The report identifies the exact job, bytes, reason and deadline.

`PEOPLE_CLEANUP_RECEIPT_RETENTION_DAYS=14` expires this worker's completed cleanup
receipts and associated error records only after the job directory is absent
and its terminal ledger status is reconciled. Interrupted intents, live recovery
data, historical approvals and authoritative publication receipts are retained.
Their storage still counts against the combined admission limit.

The historical artwork cleaner remains a separate manual scope. Runtime job
expiry uses durable producer/publication evidence, rather than a hosted CI
receipt pinned to an earlier source checkout. It never sweeps configuration,
published repositories, shared models or unrelated historical directories.
The existing source integrity checks still apply to reviewing/deploying this
source change; this worker does not change those checks or their trust anchors.

## Ownership, interruption and isolation

Require a recognized job ID, matching `managed_by`/ID manifest and lifecycle row.
If an old row is absent from the current DB, only the existing sealed historical
inventory, with its pinned digest/provenance and matching manifest hash, can
supply it. This is read-only evidence, never database reconstruction.

Sealed legacy `dispatched` README receipts represent a completed handoff to a
GitHub workflow that reads remote published blobs. They do not require retaining
local temporary payloads. This exception applies only to jobs adopted from that
verified history; current pending/dispatched README receipts are not upgraded.

All files are inventoried before deletion. Revalidate eligibility, references
and membership immediately before each job, then use the existing pinned-handle
unlink primitive for each unchanged single-link regular file. Reject symlinks,
Windows junctions/reparse points and hardlinks. Remove directories only with
`rmdir` after they are empty; recursive deletion is not used.

Persist an intent before the first unlink and a receipt after each unlink.
Delete the manifest last. Missing files following an intent allow safe retry;
changed, added or reappearing receipted files stop that job. An interruption
after removing the directory is reconciled on the next startup so an expired
failed row cannot be selected again. A bad manifest or locked file does not
stop eligible siblings. Even an invalid automatic resume cannot prevent the
startup cleanup of unrelated eligible jobs before reporting its resume error.

Failures persist safe exception types, stack locations and the same correlation
ID shown on the console in `state/job-retention/*-error.json` or
`launch-error.json`. Exception messages, locals and provider text are excluded.

## October 30 investigation

The runtime checkout was `d013af718881dc5ec82178ee85540e29a0fb7ec3`, with
additional local edits. Its enrollment requires CI for
`36083d9f3b693c54d339e1bedc32e12be07383bd`. The current checkout has one parent
(`deb9a3a2f609600a395c5be8b268805de5a5efa3`), so it is neither that tested HEAD
nor the exact two-parent, identical-tree merge permitted by `validate_ci()`.
That gate raises `RetentionBlocked`, a `ValueError`, reported as `invalid_data`.
Local tracked modifications independently fail its clean-checkout gate.

The supplied ID `bfe93e4a059240bd9a7fc62826fd90c5` was not present in available
runtime jobs/state/logs or repository diagnostic artifacts. The retained
`maintenance-error.json` instead records `invalid_data`, ID
`71b15ca40bda4d349d383f43e9d4bbaa`, at `2026-10-30T03:31:25.885835Z`.
The old handler retained no exception type, stack or original message. Therefore
the exact exception associated with the supplied ID cannot be proved from the
available evidence. The CI mismatch is a verified present blocker and a
plausible explanation, not an asserted reconstruction of that missing event.

The read-only original planner reported zero eligible bytes. It skips old
non-success jobs absent from the DB, retains `complete` metadata forever, and
rejects old successful publication grants because sealed README receipts say
`dispatched`. Its older fallback merely warns after failed retention and leaves
validation/no-work jobs forever; it keeps completed manifests/logs by design.
Whole-pass scans/record loading can also abort on malformed metadata. The
startup hook itself already exists, including resume launches; adding a timer
would leave all these policy/evidence defects unresolved.

## Read-only operator inventory

From the checkout root on Windows:

```powershell
py -3.13 -m create_people_posters.people_job_retention --config C:/path/to/create_people_posters/config --report C:/outside/runtime/new-inventory.json
```

This uses the startup planner without constructing writable managers, migrating
schemas, creating jobs, contacting GitHub or deleting files. The output must be
a new file outside runtime config. Settings are loaded from the existing `.env`
without writing it. Byte totals are logical file lengths; allocation rounding
and filesystem directory metadata are excluded.

## Runtime inventory, October 30

See [the machine-readable snapshot](PEOPLE_JOB_RETENTION_INVENTORY_2026-10-30.json)
for all 32 exact absolute paths, ages, sizes, statuses and eligibility reasons.
The snapshot covers 2,700,492,107 logical bytes. Nineteen directories are older
than three days, totaling 493,384,800 bytes. No active `.active` lease was found
in the snapshot. The current partially published job remains recoverable.

The 13 rows marked **yes** below contain **209,254,958 bytes (199.56 MiB)** and
are eligible under the corrected policy. No production data was deleted during
this investigation. Each directory is beneath exactly:

`C:\Users\bullmoose20\Defaults-Image-Creation\create_people_posters\config\jobs\`

| Exact directory name | Age (days) | Status | Bytes | Eligible / blocker |
| --- | ---: | --- | ---: | --- |
| 20261015T012302-8dd3a8a196b5 | 15.420 | validation_only | 39,025,081 | **yes** |
| 20261015T022054-1f3dd19d9b13 | 15.380 | complete | 26,031 | **yes** |
| 20261015T024133-6a94c50b17f5 | 15.365 | complete | 27,714 | **yes** |
| 20261015T024802-54544c0211fd | 15.361 | no_work | 1,411 | **yes** |
| 20261018T112901-5da1b0cb1051 | 11.999 | no_work | 1,117 | **yes** |
| 20261018T113109-90d66167d868 | 11.997 | complete | 14,783 | **yes** |
| 20261018T115445-c4d1c8f214d5 | 11.981 | complete | 59,293 | **yes** |
| 20261018T202002-f182aee6bbbf | 11.630 | no_work | 3,116 | **yes** |
| 20261021T125017-42f5984a737d | 8.942 | complete | 11,535 | **yes** |
| 20261023T103242-8e1ebc66b31c | 7.038 | failed | 51,235,289 | Within 14 days |
| 20261023T120214-70d00645512c | 6.976 | failed | 29,248,335 | Within 14 days |
| 20261024T211114-d290caa0e40c | 5.595 | failed | 2,530 | Within 14 days |
| 20261024T211204-7ddfd41e3f5f | 5.594 | failed | 19,633,979 | Nested models/vendor; preserve |
| 20261024T220933-a630709ce632 | 5.554 | cleanup_eligible | 179,240,886 | Rollback transaction journals/backups; preserve |
| 20261025T112600-14b8bdba9a34 | 5.001 | failed | 4,768,823 | Within 14 days |
| 20261026T035527-50ecd8edada4 | 4.314 | cleanup_eligible | 141,093,476 | **yes** |
| 20261026T040712-5f311004706e | 4.306 | no_work | 2,001 | **yes** |
| 20261026T040944-cec290e88eff | 4.304 | cleanup_eligible | 28,987,156 | **yes** |
| 20261026T104228-88cf77e523d5 | 4.031 | no_work | 2,244 | **yes** |

The other 13 jobs are younger than three days and retained: eight no-work,
one failed, three successfully published, and one partially published. The
machine-readable snapshot identifies each one. Ages are measured from recorded
creation, while eligibility uses publication/update deadlines as specified above.

## Regression coverage and deployment boundary

The tests exercise startup on new/explicit/automatic resume, inclusive age
thresholds, publication vs folder age, failed/validation/no-work limits,
incomplete/active jobs, partial publication, rollback and cross-job dependencies,
malformed JSON and non-object manifests, sealed history mismatch, interrupted
unlink and manifest removal, crash reconciliation, changed payloads, idempotency,
safe correlation evidence, storage-budget admission and filesystem link guards.
Growth tests cover combined jobs/state accounting, 80% warnings, overdue review
admission, deadlines surviving retries, last-step/exit measurement, unreadable
storage, completed-receipt expiry and preservation of interrupted intents.
The added Windows/Linux PR workflow runs the startup suite; it has no schedule.

This is a reviewable source change, not a production deployment. The repository's
exact-source integrity manifests pin several changed files and their test
inventory. They are intentionally unchanged. An exact predecessor/successor
maintenance transition must be reviewed before this draft can satisfy those
mandatory integrity gates or deploy. Do not merge or run production apply from
this draft until that review and the required hosted checks are complete.
