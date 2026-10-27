# People Posters storage retention: read-only audit

Audited source: `ded9f33759f9fe3ed4ddf5f315dff01b163594ad` (merged #46 and #47). Branch: `audit/people-posters-retention`. Worktree: `config/people-retention-audit/worktree`. Inventory started `2026-10-27T04:00:02Z` / `2026-10-27 00:00:02 EDT`. This report applies the user clarification that 264 older DIIIVOY/DIIIVOY Color outputs are intentionally superseded by the approved font replacement.

No existing local file was deleted, moved, reorganized or overwritten. No production batch, renderer run, GitHub write, cleanup application, new scheduler task, cleanup-setting change or Phase 5 M2 work occurred. Audit code reads existing state directly with SQLite `mode=ro` and `query_only`; it does not instantiate writing workspace/publication constructors. Only new audit evidence and these documents were written outside the production data tree.

## Decision-ready totals

| Scope | Files | Exact existing bytes | Proposed disposition |
| --- | ---: | ---: | --- |
| Persistent artwork | 937 | 2,466,139,826 | 929 candidates after reviewed legacy adoption; 8 retained |
| Processing jobs | 1,865 | 2,397,074,489 | 661 payload candidates after expiry; metadata/failed/incomplete evidence retained |
| Combined | 2,802 | 4,863,214,315 | Potential recovery 3,993,842,141 bytes; retain 869,372,174 bytes |
| Reusable model caches, outside requested reclamation scope | 15 | 3,299,221,330 | Retain all |

**Configured-policy eligibility now: 0 bytes.** All three published, uncleaned jobs are younger than three days; persistent artwork is outside the existing policy. This does not mean there are no useful candidates. The reviewed proposal can recover **3,993,842,141 bytes (3.994 GB; 3.720 GiB)** after legacy adoption and the applicable retention deadlines. No deletion is authorized by this report.

Totals are file-content bytes, not an assertion about future filesystem free-space changes. They exclude any double-counting of duplicate groups. Allocation, compression, filesystem metadata and unrelated concurrent disk activity can affect measured free-space recovery; the future worker must separately report bytes unlinked and actual free-space delta.

## Persistent artwork: exact remote copies, expected supersession, protected originals

Seven fresh, complete `master` tree snapshots contain 108,645 entries in aggregate. Each local target file has SHA-256 and Git blob SHA-1; exact matches require the intended repository/path, regular Git mode `100644`, blob identity and size. The existing on-disk inventory cache was not treated as fresh remote proof or updated.

| Persistent group | Files | Bytes | Finding |
| --- | ---: | ---: | --- |
| Exact currently published copies | 665 | 1,714,291,208 | Candidate for lossless offload after reviewed adoption; restore from pinned repo/path/commit/blob |
| Expected old-font DIIIVOY outputs | 264 | 749,344,031 | Candidate superseded artwork; approved Jost replacements verified; no unfinished operation references the old local JPEG paths |
| Unique raw originals | 2 | 192,484 | Preserve; published JPEGs are resized derivatives, not byte-identical backups |
| Legacy template/base artwork | 4 | 2,309,705 | Preserve; unowned template/input material, not publication output |
| Download provenance sidecars | 2 | 2,398 | Preserve metadata |

| Style | Local files | Exact current remote matches | Expected different versions |
| --- | ---: | ---: | ---: |
| original | 133 | 131 | 2 |
| bw | 133 | 133 | 0 |
| diiivoy | 133 | 1 | 132 |
| diiivoycolor | 133 | 1 | 132 |
| rainier | 133 | 133 | 0 |
| signature | 133 | 133 | 0 |
| transparent | 133 | 133 | 0 |

The 264 differences are expected historical rendering differences, not an integrity failure. Four sampled DIIIVOY/DIIIVOY Color comparisons have real decoded-pixel differences, consistent with changed text rendering. No rendering was performed to resolve them, and no remote image was overwritten.

All 264 current replacement paths match `published` receipts with commits in the separate Jost publication ledger. The related immutable migration manifests match their recorded manifest hashes and pin approved Jost-260 SHA-256 `564a838df86d075f9ab39e0d1f4cfe4ef90791388988dc8b5fc732f75d1ef8f5`. The saved visual-review file still matches its recorded approval hash. The migration source roots are the separate People-Images transparent collection and isolated online-recovery sources, not these older persistent DIIIVOY JPEGs. The rollout is `completed_with_exceptions`; its failed/skipped source records and external sources remain preserved. The approval for 264 replacements is not generalized to every image in those repositories.

The sampled old DIIIVOY blob also exists in verified branch history. DIIIVOY Color history lookup found the old sample, but its independent ancestry response was unavailable after bounded retries. Current Jost receipt/replacement proof is complete for all 264; historical reachability of every old JPEG is not assumed or required to classify a specifically approved superseded output. If an operator requires exact restoration of all obsolete versions, obtain complete historical/backup proof before deleting those versions.

The two original mismatches were investigated independently:

| File | Local dimensions | Local bytes | Published dimensions | Finding |
| --- | --- | ---: | --- | --- |
| `original/A/Images/Andrew Fung Chih-Chiang.jpg` | 405 x 607 | 45,665 | 2000 x 3000 | In-memory existing resize/JPEG normalization exactly matches the current remote blob |
| `original/B/Images/BoA.jpg` | 774 x 1161 | 146,819 | 2000 x 3000 | Same exact normalization result |

Both local native files have no other byte-identical copy in the two audited target trees. Their current GitHub presentation JPEGs do not preserve the exact input bytes. Keep both unless a separate exact-source backup is verified and separately approved.

## Processing jobs and retention deadlines

The ledger contains 19 registered job directories; there are no extra orphan job directories in the target inventory. The statuses, not folder age alone, control the current cleanup boundary.

| State | Jobs | Files | Bytes | Interpretation |
| --- | ---: | ---: | ---: | --- |
| cleanup_eligible | 3 | 854 | 1,530,746,367 | Fully published; still in retention window |
| complete | 5 | 70 | 139,356 | Already compacted; retain manifests and logs |
| failed | 5 | 869 | 827,153,796 | Preserve all retry/recovery inputs and outputs |
| no_work | 5 | 32 | 9,889 | Small metadata-only jobs; no published completion grant |
| validation_only | 1 | 40 | 39,025,081 | Preserve validation artifacts; pending receipts do not authorize deletion |

The five older successfully published jobs are already `complete`, retaining only 70 metadata/log files totaling 139,356 bytes. Their three-day retention has elapsed, but their disposable image payload has already been removed by earlier cleanup. There is no backlog of expired published image payload at this snapshot.

The three uncleaned published jobs have 287/287 receipts matching current remote regular-file blobs across all seven repositories. Their local image catalogs and existing publication-source hashes match. There are no active leases, pending orchestrator checkpoint markers or unresolved recovery records in those jobs. The largest job has three recovered checkpoint records covering 21 exact output files and three committed rollback journals; the proposed worker must retain their JSON/hashes, even after successful payload expiry.

| Job | Exact current receipts | Earliest expiry, America/Toronto | Proposed image/committed-backup payload | Retained metadata/logs |
| --- | ---: | --- | ---: | ---: |
| `20261024T220933-a630709ce632` | 252/252 | 2026-10-27 18:48:16 EDT | 1,360,208,375 bytes / 581 files | 457,360 bytes |
| `20261026T035527-50ecd8edada4` | 28/28 | 2026-10-29 00:02:38 EDT | 141,035,401 bytes / 64 files | 58,075 bytes |
| `20261026T040944-cec290e88eff` | 7/7 | 2026-10-29 00:13:07 EDT | 28,963,126 bytes / 16 files | 24,030 bytes |

The existing policy would eventually identify 1,530,530,121 disposable bytes by retaining only the manifest and compact logs. The proposal instead retains every non-image metadata/log file and removes only inventoried images and committed rollback `.bin` payload: **1,530,206,902 bytes**, leaving 539,465 bytes of metadata/logs in these three jobs. The 323,219-byte difference deliberately preserves checkpoints, provenance, source lists and transaction journals.

Every job, including failed and incomplete jobs:

| Job | State | Files | Bytes |
| --- | --- | ---: | ---: |
| `20261015T012302-8dd3a8a196b5` | validation_only | 40 | 39,025,081 |
| `20261015T022054-1f3dd19d9b13` | complete | 14 | 26,031 |
| `20261015T024133-6a94c50b17f5` | complete | 14 | 27,714 |
| `20261015T024802-54544c0211fd` | no_work | 6 | 1,411 |
| `20261018T112901-5da1b0cb1051` | no_work | 6 | 1,117 |
| `20261018T113109-90d66167d868` | complete | 14 | 14,783 |
| `20261018T115445-c4d1c8f214d5` | complete | 14 | 59,293 |
| `20261018T202002-f182aee6bbbf` | no_work | 6 | 3,116 |
| `20261021T125017-42f5984a737d` | complete | 14 | 11,535 |
| `20261023T103242-8e1ebc66b31c` | failed | 196 | 109,510,089 |
| `20261023T120214-70d00645512c` | failed | 406 | 679,998,480 |
| `20261024T211114-d290caa0e40c` | failed | 6 | 2,333 |
| `20261024T211204-7ddfd41e3f5f` | failed | 231 | 28,808,541 |
| `20261024T220933-a630709ce632` | cleanup_eligible | 692 | 1,360,665,735 |
| `20261025T112600-14b8bdba9a34` | failed | 30 | 8,834,353 |
| `20261026T035527-50ecd8edada4` | cleanup_eligible | 108 | 141,093,476 |
| `20261026T040712-5f311004706e` | no_work | 7 | 2,001 |
| `20261026T040944-cec290e88eff` | cleanup_eligible | 54 | 28,987,156 |
| `20261026T104228-88cf77e523d5` | no_work | 7 | 2,244 |

The five failed jobs retain 827,153,796 bytes. The largest is `20261023T120214-70d00645512c` (679,998,480 bytes), followed by `20261023T103242-8e1ebc66b31c` (109,510,089 bytes). They do not have the complete successful publication grant needed for automatic expiry. Keep their raw originals, selected inputs, candidates, partial posters and checkpoints, even when an individual file happens to match an existing remote image. The failed `20261025T112600-14b8bdba9a34` batch retains its Fuka/Joo/Natachai inputs and related artifacts.

## References, redundant copies and preserved evidence

The audit scanned 109 orchestrator checkpoint records plus recovery metadata, main publication receipts, separate Jost migration manifests/controllers and their publication ledgers. Relative recovery output keys were resolved against each job root, rather than mistaken for unrelated paths. There are 588 existing target files referenced directly as publication sources/prepared copies. Those references remain visible in the per-file evidence; a completed, fulfilled receipt is a durable historical reference, not an active processing dependency. Before expiry, it still protects that job.

No audited persistent JPEG/PNG path is referenced by an active, failed or retryable operation. One completed legacy marker records the persistent transparent directory as a historical command argument; it is not a pending lease or an unresolved per-file checkpoint. Separate Jost source roots lie outside these persistent output paths. No People processor or relevant scheduled task was identified in the process/task snapshot, and no job/recovery active leases were present. These observations are not a substitute for acquiring exclusive locks and rebuilding the reference graph immediately before any later deletion.

There are 478 identical-content groups across the two target trees, totaling 1,541,506,372 additional-copy bytes if one copy per group were kept. That is a descriptive redundancy estimate, not another amount to add to projected savings: it overlaps generated/prepared copies, failed jobs and the candidate plan. Cross-job duplicates do not authorize removal from a failed workspace. `file-decisions.csv` and `retention-audit.json` identify input copies, generated posters, publication-prepared copies, originals, rollback binaries, source history and metadata separately.

Retain the complete 3,299,221,330-byte reusable model cache. This audit also leaves existing migration evidence, renderer comparisons, validation evidence, source collections outside the two target roots, attempted/exhausted histories, publication databases, manifests and receipts untouched.

## Why cleanup has not removed these files

1. The 2.466 GB persistent artwork tree predates/exists outside managed batch ownership. `Workspaces.cleanup()` iterates the job ledger and job roots only. It has no authorization to delete that tree.
2. The 264 local old-font posters were intentionally left intact by the Jost migration, which writes only its two approved destinations and explicitly treats source collections as read-only. Normal batch cleanup does not adopt these legacy files.
3. The remaining 1.531 GB of successful-job storage is younger than three days at this snapshot. The `cleanup_eligible` status means verified publication, not that the age gate has elapsed.
4. The five older published jobs have already been compacted. Their tiny retained folders are expected evidence, not a failed cleanup.
5. Failed, validation-only and no-work jobs intentionally fail the successful-publication gate. Fourteen-day failed-job retention is a warning/recovery threshold, not permission to delete failed work.
6. `PEOPLE_AUTO_CLEANUP=true` is already configured, with three-day success retention, fourteen-day failed warning age, 20 GiB job budget and batch/API mode. The audit did not change these settings. Cleanup runs on later non-dry-run orchestrator launches/workspace creation, not on an independent timer. No relevant scheduled task was found.
7. Existing batch cleanup verifies stored receipt completion and local catalog/source hashes. It does not fetch current GitHub publication state during deletion. The future mechanism must add that check before increasing automation.
8. PR #46 intentionally addresses exact owned recovery scratch after QA/checkpoint success. It is not an artwork cache/offload policy and must not be widened to erase original archives or legacy directories.

## Evidence and limits

The before/after audit found zero changed, missing or added existing People files among 16,171 accessible files. All 2,802 target files were SHA-256 hashed again successfully. Three pre-existing inaccessible validation directories are explicitly listed in `preservation-check.json`; they are outside the two fully readable target trees and remain outside readable coverage. No reclaimable bytes are claimed from them.

The remote proof is a pinned-time snapshot, not a guarantee that a branch will remain unchanged until later approval. All candidates need a fresh locked preflight. Font classification is established by the approved migration receipts and the user clarification, not inferred from pixels or timestamps. Historical metadata and image evidence was not rewritten to make any check pass.

Evidence is in `config/people-retention-audit/`: `local-inventory.json`, `retention-audit.json`, `file-decisions.csv`, `references.json`, `remote-snapshots.json`, `remote/*.json`, `variant-samples.json`, `history-probe.json`, `automation-inspection.json`, `preservation-check.json` and `proposed-retention-plan.json`.

The proposal-only plan fingerprint is `a3e61e6b763e154b2d7575cdd12588425847187c709c0be64edc6b446d35cd43`. It binds the 2,802 per-file dispositions, hashes, sizes and expected replacement proof. It is not a deletion token or approval. See `PEOPLE_POSTERS_RETENTION_PROPOSAL.md` for the implementation and approval boundaries.
