# People Posters storage retention: implementation proposal for approval

Status: proposal only. No implementation, deletion, file reorganization, GitHub mutation, scheduler registration or activation is authorized by this document. Phase 5 M2 stays on hold.

## Expected savings and timing

The audited targets contain 4,863,214,315 bytes. The proposed policy can reclaim **3,993,842,141 bytes (3.994 GB / 3.720 GiB)** and retain 869,372,174 bytes in those targets. Keep the separate 3,299,221,330-byte AI model cache. The numbers below are disjoint; the duplicate-content estimate is not added again.

| Candidate cohort | Files | Bytes | Preconditions |
| --- | ---: | ---: | --- |
| Legacy exact published copies | 665 | 1,714,291,208 | Reviewed adoption; fresh exact remote/path proof; no unfinished dependencies |
| Expected obsolete font versions | 264 | 749,344,031 | Explicit old-hash/new-Jost-hash supersession inventory; verified published replacement; no unfinished dependency |
| Successful job image/committed-backup payload | 661 | 1,530,206,902 | Complete seven-style publication proof, no pending work, expired three-day window, fresh locked preflight |

No jobs qualify under the existing age gate at the audit timestamp. The largest job reaches three days on **2026-10-27 at 18:48:16 EDT**, making 1,360,208,375 proposed payload bytes candidates. Two more reach expiry on **2026-10-29 at 00:02:38 and 00:13:07 EDT**, adding 141,035,401 and 28,963,126 bytes. These are earliest times, not deletion promises: any later remote/local/reference failure blocks that job.

Legacy artwork has no managed retention clock. Create a separately reviewed adoption manifest; do not invent publication dates from file modification times. Recommended default: observe the adopted legacy cohort for 72 hours from its first recorded verified snapshot before applying an approved plan. An immediate one-off legacy disposal would require a separately explicit approval of its exact inventory and exception; this audit does not grant it. Future successful jobs retain their existing three-day verified-publication clock.

The two native originals (Andrew Fung Chih-Chiang and BoA, 192,484 bytes total), four legacy base images, sidecar metadata, five failed jobs, validation-only evidence and all job metadata/logs remain. The proposal keeps an additional 323,219 bytes of job metadata compared with the existing cleanup policy.

## Explicit disposal contracts

**Exact published copy.** The plan binds local owner/scope, canonical path, stable file identity, size, SHA-256, Git blob ID, intended repository/branch/path, successful publication proof and verified commit/tree. Re-read the exact current branch tree and the relevant receipt immediately before deletion. Reject missing paths, case/Unicode ambiguity, unexpected modes, replaced blobs, malformed receipts, unknown owners and unsafe files. For legacy artwork, adoption supplies the missing ownership record and a new verification record from live Git proof; it must not fabricate historical batch receipts or completion states. Filenames or mtimes alone are insufficient.

**Reviewed font supersession.** This is an explicitly separate policy, not a relaxed exact-hash check. Bind each of the 264 old local path/SHA-256/blob values to its specific approved Jost replacement path/blob/SHA-256, verified publication commit and approved font/review evidence. Confirm the current replacement is still the intended published version and that no active/failed/retryable operation needs the older file. Retain the old hash and supersession reason after removal. An arbitrary mismatch never qualifies. Never regenerate or republish older font outputs to make the hashes agree. Do not automatically restore an obsolete font output into a current publication source tree.

**Owned successful-job intermediates.** Raw inputs, originals, cutouts, publication-prepared copies and committed rollback payload expire only as part of a completely published, nonretryable job after its three-day window. Verify all seven output styles and the receipt-bound source-to-published hash relationship, even where normalization changed the raw bytes. Preserve all non-image metadata, journals, checkpoint hashes and receipts. Incomplete, failed, partially published, recovery-pending, validation-only, unregistered or actively leased jobs retain everything. A remote match for one file does not make a failed job disposable.

The existing batch policy already allows successful-job raw intermediates to expire. That can intentionally remove native bytes that are not reconstructible from the normalized published poster. Operators must approve this tradeoff. If exact raw-input archival is desired beyond the existing three-day contract, add a separately verified archive tier and recalculate savings; do not imply that the seven presentation repositories preserve every raw input.

## Reuse existing infrastructure with narrow integration

Add a separate retention coordinator and report/plan/apply CLI, plus a durable retention journal under the persistent state root. Proposed modules: `people_retention.py`, `people_retention_state.py` and focused tests. These are proposed names, not existing implemented commands.

Reuse `Workspaces` ownership IDs, manifest validation, job paths and terminal-state rules; `PublicationState` receipt schema and export semantics; authoritative Git tree inventory/path validation; and PR #46's regular-file/link checks, exact inventories, OS cleanup lease pattern and interrupted-file accounting. A report path must open state read-only and must not construct writing state classes or refresh the production cache. An apply path may update only its own reviewed retention journal and the required terminal job status after explicit approval.

Keep `people_recovery_storage.py`'s scratch-only contract unchanged. Do not pass arbitrary artwork roots into its scratch cleaner or manufacture recovery success. Keep the reviewed predecessor/successor provenance, security baselines, approved source inventories, renderer, publication behavior and existing regression IDs unchanged. Any unavoidable production call-site change needs its own narrowly reviewed source transition and mandatory CI; no historical resealing or validation bypass.

Use one coordinator for scheduled and launch-triggered cleanup. The minimal integration should route existing cleanup entry points through the new preflight/journal path, rather than leave a second broad `rmtree` path that bypasses the new remote checks. Review the exact small workspace/orchestrator adapter before implementation; do not rewrite the merged #46 implementation.

## Concurrency, references and interrupted cleanup

1. Planning remains strictly read-only: no processing lease creation, no source movement and no SQLite schema migration. It emits candidate/blocked bytes and a fingerprinted plan.
2. Apply acquires a machine-local OS lease for a single retention worker and a processing-exclusion lease compatible with the existing `state/orchestrator.lock` protocol. Merely checking for `.active` is insufficient. Existing processors and the worker must contend on the same atomic acquisition mechanism. Check every job/person/recovery lease and pending checkpoint again under that exclusion.
3. Treat stale/unknown leases as blockers. A restarted cleaner may reconcile only its own documented dead-process lease, with journal/token identity and an OS lease; never clear another operation's stale lock on age alone. A processing heartbeat/owner change invalidates the plan.
4. Build a reference graph from main and migration publication state, manifests, pending markers, recovery records and transaction journals. Keep unresolved/failed/retryable scopes regardless of age. Completed receipt references remain durable metadata and may point to an expired payload only after its disposal/restore record is committed. Recheck the reference graph under the same exclusion immediately before apply.
5. Persist the complete exact membership, local hashes/file identities, ownership, remote heads/trees/blobs, receipt hashes, disposition, deadlines and metadata-retention list before the first unlink. Flush the journal durably. For terminal jobs retain all metadata in place; do not truncate logs or delete checkpoint/transaction JSON to save trivial space.
6. Remove only inventoried single-link regular files after an immediate hash/identity recheck. Reject links, reparse points, hardlinks, unsafe parents, path escape, additions, ownership changes and mismatches. Do not use recursive directory deletion. Remove only known empty disposable directories after their files are gone, leaving retained metadata directories intact.
7. Journal per-file intent and completion. On interruption, preserve the remaining files and resume the same inventory only after fresh remote, local and reference proof. Count already-missing files separately from files deleted by this execution; never double-count reclaimed bytes. Unknown changes block continuation. Mark a job complete only when all authorized disposable payload has been reconciled and retained records remain readable.
8. Exact-copy restore uses immutable repo/path/commit/blob plus SHA-256 and writes to a new staging destination, not a production publication tree. A future retry must hydrate/validate required files before execution; tombstones are not a successful recovery checkpoint. A reviewed obsolete-font disposal is not permission to republish that obsolete version.

## Scheduling and storage reporting

After implementation validation and separate activation approval, propose one Windows Task Scheduler task on this machine, daily at 03:30 America/Toronto, with missed-run handling and one-instance behavior. Prepare an importable disabled task definition for review first. Do not register or enable it during this audit. The CLI should also work from a Linux timer if the storage host changes; do not schedule the same root from two hosts.

Default the new mechanism to report-only. Activation requires explicit local configuration plus a current reviewed plan/policy version. Keep the already configured existing setting unchanged during this audit; its current value `PEOPLE_AUTO_CLEANUP=true` is not approval to run the proposed mechanism.

Emit structured per-run records and a concise local summary: examined files/bytes, exact published copies, approved supersessions, future eligibility, protected bytes by blocker, files unlinked this run, actual bytes unlinked, already-missing/reconciled files, interruption state and observed free-space delta. Keep daily/weekly trends and a bounded summary history while retaining essential per-file hashes and publication/disposal receipts permanently.

Proposed warnings for review: completed jobs still retained more than 24 hours after expiry; failed/incomplete jobs older than the existing 14-day warning age; job storage approaching the existing 20 GiB budget; repeated cleanup blockers or remote drift; and low disk free space. Suggested soft alerts are 16 GiB of job storage and less than 10 GiB free. These are proposed notifications, not changes to current resource limits or permission to delete protected work. Write local reports first; do not send messages to external services without separate authorization. Model caches are excluded from reclamation and never treated as disposable because of size.

## Risks and controls

| Risk | Required control |
| --- | --- |
| Remote replacement/force-push after an old receipt | Fresh exact branch proof immediately before each cohort; immutable receipt/restore hashes; fail closed on change |
| Deleting a local old-font file merely because the name exists online | Explicit reviewed old/new hash supersession inventory and Jost publication proof; never a generic mismatch allowance |
| Losing unique raw originals or retry inputs | Preserve the two unique legacy originals; retain all failed/incomplete work; separately approve successful-job intermediate expiry |
| Race with processing, cleanup or rollback | Shared exclusion/leases, ownership/token checks and fresh reference graph; no concurrent apply |
| Crash between unlink and receipt update | Durable per-file intent/completion journal; restart reconciliation and separate already-missing accounting |
| SQLite or manifest inconsistency | Consistent read-only planning snapshot; validate IDs/hashes/state; block ambiguous or corrupt records |
| API failure, rate limiting or incomplete trees | GET-only bounded retries and complete-tree fallback; retain everything affected when proof is unavailable |
| Case, Unicode, link or filesystem substitution | Canonical exact paths, mode/file-ID/hash checks, no links or hardlinks, no recursive deletion |
| Remote history loss or inability to restore obsolete versions | Retain their old hash/disposal record; require separate exact archive proof if restoration of superseded versions is required |
| Misstated disk savings | Disjoint per-file plan; no addition of duplicate estimates; report actual unlinked bytes and free-space delta separately |

## Validation and approval sequence

Implement only after approval of this proposal. Keep it on this separate branch/worktree or a directly related implementation branch. Add focused controls for fresh/missing/replaced remote blobs, approved and unapproved supersession, 3-day boundaries, all preservation states, metadata retention, concurrent writer/cleaner contention, stale leases, file/link substitutions and interruption at each journal/unlink boundary. Existing 40 storage controls and historical mandatory inventories remain intact. Validate Windows and Linux, including their real symlink/junction cases and mandatory acceptance gates. Use isolated fixtures; never a production batch or poster publication for validation.

Then present the disabled scheduler definition, exact changes, test results and a fresh machine-specific dry-run inventory for review. Obtain explicit approval before any initial disposal, then separate approval to enable ongoing scheduled apply. Any approved first run should be bounded and produce exact reclaimed-byte evidence. Phase 5 M2 remains on hold until the storage work is addressed.
