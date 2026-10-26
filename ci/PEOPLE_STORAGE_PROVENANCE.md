# People storage integrity prerequisite

This maintenance is separate from draft PR #46. It changes CI provenance only,
with no renderer, cleanup, dependency, publication, resource-limit or artwork
changes. Neither this prerequisite nor #46 may merge without review approval.

## Exact transition and merge order

The baseline is main `5c1a470502b38814b14627f32665d7fd4490bd1d`, including
merged #45 (`d799b481562e823ac86cec0ec86d8d1b1b7ea898`) and #44.
The reviewed cleanup commit is `786bc059df3b3e16cebf68f219961f24a939e380`;
its eight-file delivery starts at `ef3b2713cf5dcab9b92395321c6be3fdf1efdbce`.
The sole production-member transition is:

| File | SHA-256, LF-normalized |
| --- | --- |
| `create_people_posters/recover_edge_chops.py` predecessor | `28685c12ea68fb2e928220669976e795abeae665ecc71e9567d97e96d79dea3a` |
| Same file, reviewed successor | `a945c37104ae4d9b7a8d0c5dddff69da786e3f7b82278819e33729c8e430e16f` |

1. Review and approve this prerequisite **after** #45 and #44. Its normal mode
   still requires the predecessor source, unchanged test fixture and absence
   of all six additive cleanup files. All four mandatory workflows must pass.
2. After approval, merge this prerequisite into main.
3. Merge updated main into the **existing** #46 branch. Do not cherry-pick or
   replace its eight-file implementation. The pinned source commit must be an
   ancestor of the final head. Once integrated, all eight exact successor
   files are mandatory. Old source, mixed versions, missing additions and
   unknown successors fail. There is no runtime toggle or permissive either-hash
   mode. Missing Git history fails closed.
4. Run original validation, M6, M7, dependency provenance and storage workflows
   against the same final #46 commit on Windows/Linux. Reconcile execution IDs,
   skip reasons, receipts and inventories. Obtain separate approval to merge #46.

An isolated integration rehearsal may validate that same source cohort before
either merge. It is not approval and does not replace rerunning at the eventual
#46 head. No merge is authorized by a passing report.

## Prior failures and preserved checks

The original source hash changes intentionally in #46, but neither the
190-member production envelope nor the immutable People maintenance manifest
authorizes its successor. Production protection raises `BulkError: Production
source differs from the approved baseline`; People verification raises
`Changed exact People security maintenance`. M5 wraps that failure as its People
security extension error; original acceptance then rejects failed required jobs.
Dependency provenance calls these same guards, so both platform jobs fail.

M7 also checks People protection before its scope guard. After the source
transition is fixed, its inherited 15-file M7 scope plus #45's five additive
planning documents still rejects the eight cleanup paths. M7 freezes all 2,927
existing baseline files, including three CI files this transition must extend.
The strict People namespace also needs an executor for all 40 new storage IDs.
These are independent latent blockers, not reasons to suppress errors.

`people-storage-maintenance-v1.json` retains exact predecessor and successor
hashes, source ancestry, explicit eight-file membership, separately named CI
infrastructure transitions and an additive 40-ID inventory. Its canonical digest
is pinned in the new reviewed verifier. That verifier and its manifest are
explicit regular-file trust anchors, reviewed with the exact PR head, rather
than recursively self-hashed. Other CI successors, tests and this document are
content-bound by the manifest. No wildcard or directory allowance is introduced.

The dependency selector maps only exact known predecessors. The People guard
verifies the entire atomic cohort and exact CI successors before its existing
checks. The existing People ID manifest is unchanged; the 40 IDs extend only
the compatibility executor after ancestry activation. Original namespace,
exact-head, phase, duplicate, skip, result and acceptance checks remain intact.
The separate storage workflow runs the complete focused storage suite as well.

M7 retains its original `BASE`, 15-file `ALLOWED`, five exact planning additions,
Git-mode/link checks, all 190 production and 299 adoption checks and every
historical comparison. Its extension validates exact named transition paths,
regular Git modes and physical files. For the three frozen CI successors it
first verifies successor bytes, retrieves and checks the exact predecessor
from the pinned main commit, then compares it against the original M7 blob.
All 2,927 historical files are still compared; none is skipped or resealed.
The fourth CI file is the original additive M7 verifier, not a frozen baseline
member. Unlisted history retains physical byte equality.

Unchanged evidence includes `people-security-maintenance.json`, dependency
maintenance, production/adoption manifests, all historical receipts, original
workflows, all historical test-ID inventories, thresholds and resource limits.
The 190 protected inventory and all 299 adoption sources remain intact.

## Validation and implementation scope

Mandatory dependency unittest discovery executes the new positive/negative
controls on Windows and Linux, retaining all previous tests unchanged. Controls
cover exact Git before/after evidence; actual ancestry; both complete cohorts;
CRLF compatibility; every required cohort file's unknown bytes and deletion;
mixed versions and full rollback; premature additions; symlinks/reparse points
on files/parents; unlisted paths and predecessors; missing/tampered/replaced
manifest; all CI successors; historical projection/drift; all forty IDs; all
2,927 frozen files; production/YAML drift; inventory drift; and forbidden Git
deletion/rename/symlink modes. Original #45 controls remain unchanged.

PR #46's eight blobs must remain exact. Its owned scratch protocol, failure
retention, per-person and per-cleaner leases, original/source history, immutable
receipts, seven publication destinations and renderer are not modified here.
Storage tests use isolated fixtures only; no historical local files are deleted.
Seven-style output byte equivalence is checked separately against the unchanged
production predecessor. Actual run IDs, heads, test counts, durations, skips and
changed-file inventories belong in PR validation evidence, not regenerated
historical baseline files.
